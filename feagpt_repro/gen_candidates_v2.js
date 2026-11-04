// gen_candidates_v2.js — W4d：L3 主基线生成器（schema 校验 + 错误反馈修复循环）
// 与 v1（gen_candidates.js，W4b 用，response_format=json_object 单轮）的差异：
//   1. 模型 id 显式 pin（R13：可引用，不再用 auto）
//   2. ajv 校验 schema_task.json（放宽版：死字段不进 required）——SDK 只支持
//      json_object，无 logits 级 json_schema 约束，故「约束解码」= 校验+反馈修复循环，
//      CLAIMS 如实标注
//   3. CLARIFY 协议改 JSON：{"clarify": ["问题1", ...]}（json_object 模式下不出纯文本）
//   4. 修复循环 ≤3 轮：校验失败把错误清单喂回去重生成，记录 turns_used + validation_history
// 用法：node gen_candidates_v2.js --tasks tasks/tasks.jsonl --levels L3 --out candidates_l3_v2 --limit 2
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const Ajv = require('ajv');
const { createWorkBuddyCloud } = require('@tencent-ai/workbuddy-cloud-sdk');

const publicConfig = {
  endpoint: 'https://fem-bench-baseline.app.workbuddy.host',
  // P1-2（专家第四轮）：只读 env，无 fallback 硬编码 key
  publishableKey: process.env.WORKBUDDY_PUBLISHABLE_KEY,
};

const SYS = `你是飞机结构有限元建模专家。根据用户给出的结构描述，输出一个 FEM-Bench-Aero 规范的 spec JSON（mm-t-s 单位制）：
{"name":"<case名>","description":"<一句话>","material":{...},"structure":{"family":"<wingbox|open_hole_panel|fuselage_barrel|stiffened_panel>","params":{...}},"airfoil":{仅wingbox},"mesh":{},"load":{},"bc":{},"analysis":{},"extra":{}}
★ 铁律：用户给出的每个数值必须【逐字段采用】（键名数值都不许改、不许省略）。
★ 缺失信息处理：用户没给的尺寸参数【不得编造】，输出 {"clarify": ["问题1", ...]} 列出需要澄清的字段（json_object 模式下澄清也必须是这个 JSON 形式）。仅当缺失字段使模型无法定义时才澄清——**但数量字段不受此限，见下条**。
★ 数量类字段铁律（W5c-6d / R50）：题面**提到**某个特征（长桁/加筋、框、肋）却**没给具体数量** ⇒ 该数量就是缺失参数，**必须澄清**（n_stringers / n_stringers_per_skin / n_frames / n_ribs 等），**不得填 0、不得取"惯例值"、不得自行假设根数**。只有题面**明说素板 / 无加筋 / 无长桁**时，长桁数才可以直接写 0。
★ 其余几何惯例（**仅当题面完全没提该特征时**才适用，用来区分"没提"与"提了没给数"）：完全未提长桁/加筋→该族长桁数为 0（等于无此特征，**不要**为此澄清）；未提锥度→tip_chord_ratio=1.0；未提后掠→sweep_deg=0；未提中间腹板→web_chordwise=[]（不要把前后梁位置复制到 web_chordwise）；铺层板基材按用户描述（铝板则 material 用铝）。
★ 长桁键名按族（键名即契约）：翼盒用 n_stringers_per_skin；柱壳与加筋壁板用 n_stringers。长桁细节键（stringer_height/stringer_thickness/stringer_kind/stringer_flange_width）只有当该族确有长桁且用户给出了具体尺寸时才填写；用户没给尺寸时【直接省略这些键】（求解器按族默认取值），绝不要填 0。
★ 四族键名总表（**只能写表里的键**，表外的键一律不写；W5c-1/R34）：
  · wingbox ⇒ 细节写 airfoil 块：code/chord/span/skin_thickness/n_ribs/rib_thickness/spar_chordwise/n_stringers_per_skin/stringer_height/stringer_thickness/stringer_kind/stringer_flange_width/tip_chord_ratio/sweep_deg/web_chordwise；structure.params 写 {}。
    中间腹板：题面给了位置 ⇒ airfoil.web_chordwise=[<弦向占比>, …]（如题面「35% 弦向处一道中间腹板」⇒ [0.35]）；题面没提 ⇒ []（**不要**把前后梁位 0.25/0.70 复制进来）。
    长桁剖面：stringer_kind 只能是 "blade" 或 "T"。**T 剖面必须填 stringer_flange_width（缘条宽）**；blade 剖面没有缘条，**不要**写 stringer_flange_width。
  · open_hole_panel ⇒ 写 structure.params：length/width/thickness/**hole_d**（孔直径）/**hole_x**、**hole_y**（偏心孔的孔心坐标，中心孔时这两个键省略）/ layup（仅铺层板，见下）。
    铺层板：params.layup = {"plies":[{"angle":<度>,"thickness":<单层厚 mm>}, …], "material":{"name","E1","E2","E3","nu12","nu13","nu23","G12","G13","G23","density"}}；
    ★ 铺层板的 material 块仍写**基材**（如铝 2024-T3），CFRP 单层材料卡放进 params.layup.material——**绝不要**写 material.ply_material 这种自创键。
  · fuselage_barrel ⇒ 写 structure.params：diameter/length/thickness/n_stringers/n_frames。
  · stiffened_panel ⇒ 写 structure.params：length/width/thickness/n_stringers（**题面明说素板才写 0**；题面提到长桁/加筋但没给根数 ⇒ 澄清 n_stringers，见数量铁律）。
★ extra 块：**只有** fuselage_barrel 用 end_shear / end_moment（单位 N、N·mm）；其余三族一律 {}。不得写 end_torque / torque_axis_dof / end_tension 之类自创键（键名即契约，自创键按编造判 FAIL）。
★ 载荷词汇（kind 的取值只有两个）：面内拉伸（端部均布拉力）或翼尖集中力 ⇒ kind="tip_force"（magnitude 用 N）；内压/均布面压 ⇒ kind="pressure"（magnitude 用 MPa）。
★ 词汇约定（必须用这些词）：材料名 "Aluminium 2024-T3" 或 "CFRP-LAYUP"；翼型 code "4412"（不是 NACA4412）；载荷 kind "tip_force"（集中力）或 "pressure"（分布压力）；加筋长桁 kind "blade" 或 "T"；边界条件用 {"root_surface":"root","clamp":true}；载荷方向 direction 用 [x,y,z] 数组（法向即 [0,1,0]）；开孔板/加筋板载荷 kind="pressure" 用 magnitude（面压 MPa）或面内拉伸按用户描述；网格键 size_chord/size_span（四族通用）。
★ fuselage_barrel 的载荷组合（端剪/端弯）写进 extra.end_shear / extra.end_moment（数值用 N 和 N·mm）。
材料按名称给出 E/ν/密度/屈服（铝 2024-T3: E=73100 MPa, ν=0.33, ρ=2.78e-9 t/mm^3, 屈服=345 MPa；T300/环氧参考用户给定）。
只输出一个 JSON 对象（spec 或 clarify），不要输出其他文字。`;

// R53（W5c-6d）：把 SYS prompt 的 sha256 写进每条候选 —— 同一张卷换 prompt 后，
// 「同卷 sha 相同」并不代表可比；只有 prompt sha 也相同才可比。旧候选没有这个字段，
// 下游一律当 UNKNOWN（不得当「相同」处理）。
const PROMPT_SHA = crypto.createHash('sha256').update(SYS, 'utf8').digest('hex');

// ---------------------------------------------------------------------------
// L2（澄清题）输入渲染 —— T-A13a（2026-10-30）
// ★★ 纪律：**SYS 一个字节都不许动**。它的 sha 是 L3 跨版本可比性的锚点（R53/S-39），
//    改一个字就会让 C-032/C-040 的 `prompt_sha` 变成历史值。所以 L2 用 SYS + 追加段，
//    不复制、不改写 —— 四族键名总表 / 数量铁律（R50）/ 词汇约定全部原样继承。
// ---------------------------------------------------------------------------
const L2_ADDENDUM = `
★★ 本次任务类型：L2 澄清题（**以下三条优先于上文关于「用户给出结构描述」的全部表述**）
1. 你拿到的**不是**工程描述文字，而是一个 FEM-Bench-Aero spec JSON（mm-t-s 单位制）。
2. **JSON 里缺的键 = 用户没给该参数**：它不是 0、不是默认值，也不等于「没有这个特征」。
   ★ 所以上文的「几何惯例」（完全未提长桁→长桁数写 0、未提锥度→tip_chord_ratio=1.0 等）在本次任务中**一律不适用**。
   ★ 也不得从 name 里的数字反推（如 name 含 d30 就填 hole_d=30）——name 是标签，不是参数。
3. 若缺键导致该族 spec 无法定义，**必须**输出 {"clarify":["…", …]}；**每条问题都必须写出缺失字段的键名**
   （键名只能从上面四族键名总表取，如 n_frames / n_ribs / hole_d / skin_thickness）。
   只写中文描述、不写键名，视为**没有提出**该字段。只有在缺的键不影响定义时才输出完整 spec。`;

const SYS_L2 = SYS + '\n' + L2_ADDENDUM;
const PROMPT_SHA_L2 = crypto.createHash('sha256').update(SYS_L2, 'utf8').digest('hex');

// ---------------------------------------------------------------------------
// T-L27c v3（2026-11-04）：L2「逐键转写」加强段 —— **独立 arm，不是替换**
// ★ 为什么是 arm：v2 那 16 条实测把失败模式指到了 prompt（glm 12 条 spec_bad 全在
//   mesh 段「省略/合并」；ds 9 条 clarify_wrong 全在「把 schema 命名/规范意见当澄清
//   理由」），不是能力。要验这一点必须**只改 prompt 一个变量**（R-A1）。
// ★ 为什么不能直接改 L2_ADDENDUM：它的 sha = `03129c56…` 是 C-041（v7 两份 L2 成绩单
//   glm 49/64、ds 36/64）的锚点。改常量 ⇒ 那两份立刻变历史值（S-39 必红）。所以这里
//   追加、且**只在 --l2-strict 时生效**；不传参时逐字节等于旧版。
// ★ 内容是**规则**不是 case 清单：不写任何具体题目的键名/取值，否则等于对这 16 条
//   过拟合（换卷即失效，且违反「判据不能依赖具体值」）。
// ---------------------------------------------------------------------------
const L2_STRICT_ADDENDUM = `
★★ 转写纪律（**最高优先级：与上文任何表述冲突时以本节为准**）
本题考的是「把题面照原样转写清楚」，不是「按你的理解重写一份更规范的 spec」。

A. **逐键照抄**：题面 JSON 里出现的每个键，输出必须**原样保留**——键名一字不改、
   一个不省、不合并、不拆分、不换层级。以下都算改坏：
   - 把两个同级键合成一个（哪怕你觉得它们本就该是一个量）；
   - 把嵌套键提到外层，或塞进别的块；
   - 因为「这个键名不符合本领域惯例」就改成你习惯的名字。
   ★ 键名以**题面**为准，不以你的偏好为准。

B. **不许自创键**：输出的键集合 ⊆（题面已有键 ∪ 上面四族键名总表）。
   总表外的键一个都不写；extra 块除柱壳的 end_shear / end_moment 外一律 {}。

C. **澄清前先逐键核对题面**（这一步不许跳、不许凭记忆）：对你打算追问的每个字段，
   先在题面 JSON 里全文检索这个键名，并确认它属于**本题族**的哪一行键名总表。
   ★ 澄清的**唯一合法理由**是「题面里找不到这个键」。
   ★ 以下理由一律**不合法**，不得据此追问：
     - 键名不符合你的命名习惯（题面写什么就认什么，不同名不等于缺失）；
     - 某个键「按规范应由别处给出」（题面给了就照抄，不给才问）；
     - 你希望把两个键合成一个更规范的表达（B/A 已禁止）；
     - 把**别的族/别的块**的键名拿来问本题（先确认它在本族总表那一行里）。
   ★ 题面按上文规则**故意省略**的键不算缺失（例如中心孔省略孔心坐标、无长桁省略
     长桁细节键）——这类键追问就是错。
D. 仍然只输出一个 JSON 对象（spec 或 {"clarify":[...]}），不要输出其他文字。`;

const L2_STRICT = process.argv.includes('--l2-strict');

// ---------------------------------------------------------------------------
// T-L27c v3 第二跳（2026-11-04）：网格键更正 —— **考的是 SYS 自己的一句错话**
// ★ 来源：SYS 第 40 行**曾**写「网格键 size_chord/size_span（翼盒）、**size（板壳类）**」，
//   但**四族 gold 的 mesh 段完全一致、全部用 size_chord/size_span，没有任何 gold 有 size**
//   （实测 `modeling/*/spec.json`，`_l27c_check_mesh_keys.py` 守这条）。
// ★ 修复确实做过、又被回滚带走：`_psa_fix_mesh_keys.py` 的 `OLD1`（p3 版 SYS 片段）
//   与 `NEW1`（p4 版）**都含**「板壳类也用这两个键名——**没有 size 这个键**」，
//   而 `ce225186` 里**没有**这一句。⇒ 2026-11-01 把 SYS 回滚到 `ce225186`（p5c 作废）时，
//   这句更正**随回滚一起消失，且没有任何闸报错**。
//   （判据只锚 sha 变没变，不锚「sha 对应的那句话对不对」——见 CONFLICT N-34。）
// ⇒ 模型按 prompt 写 `size` 被判「自造键」不是模型的锅。
//
// ★★ 2026-11-04 老王拍板：**SYS 已修正**（第 40 行改为「网格键 size_chord/size_span
//    （四族通用）」，不提 size 这个词，避免重演 ds 在 meshfix 段的反向追问）。
//    下面的 `L2_MESHFIX_ADDENDUM` 因此**只剩历史实验价值**：
//    - 它原本是唯一纠正 SYS 的手段，现在 SYS 自己是对的；
//    - 且实测该段**只对 glm 单向有效、对 ds 引入反向噪声**（T-L27c v3，p=0.73，b=3）。
//    ⇒ **新实验不要再启用 `--l2-meshfix`**；它保留是为了让 T-L27c v3 的产物可复现。
// ---------------------------------------------------------------------------
const L2_MESHFIX_ADDENDUM = `
E. **网格键**：四族的网格块**只有**
   size_chord 与 size_span 两个尺寸键 —— 开孔板与加筋板**也用这两个键名**，
   **没有 size 这个键**。把题面给的 size_chord / size_span 合并成一个 size，
   按「自造键」判错。`;

const L2_MESHFIX = process.argv.includes('--l2-meshfix');
const _L2_PARTS = [SYS_L2]
  .concat(L2_STRICT ? [L2_STRICT_ADDENDUM] : [])
  .concat(L2_MESHFIX ? [L2_MESHFIX_ADDENDUM] : []);
const SYS_L2_EFF = _L2_PARTS.join('\n');
const _L2_ARM_TAG = [L2_STRICT ? 'strict_v1' : null, L2_MESHFIX ? 'meshfix_v1' : null]
  .filter(Boolean).join('+') || 'base';
const PROMPT_SHA_L2_STRICT =
  crypto.createHash('sha256').update(SYS_L2 + '\n' + L2_STRICT_ADDENDUM, 'utf8').digest('hex');
const PROMPT_SHA_L2_MESHFIX =
  crypto.createHash('sha256').update(SYS_L2 + '\n' + L2_MESHFIX_ADDENDUM, 'utf8').digest('hex');
const PROMPT_SHA_L2_STRICT_MESHFIX =
  crypto.createHash('sha256').update(SYS_L2 + '\n' + L2_STRICT_ADDENDUM + '\n' + L2_MESHFIX_ADDENDUM,
    'utf8').digest('hex');
const PROMPT_SHA_L2_EFF = crypto.createHash('sha256').update(SYS_L2_EFF, 'utf8').digest('hex');

// ---------------------------------------------------------------------------
// T-B2B5（2026-11-02）越界拒答题 —— 第三份 SYS：SYS + 追加段
// ★★ 同 L2 的纪律：**SYS 一个字节都不许动**（R53/S-39 的 sha 锚点）。
//    所以这里是追加，不是改写；SYS_REFUSE 的 sha 只锚这一套独立小卷
//    （tasks_refuse_v1.jsonl），不进入任何 v7 成绩。
//
// 为什么必须显式告诉模型「越界要拒」：现有 SYS 只说「用户给的每个数值必须
// 逐字段采用」，于是面对一个做不出来的请求，最省事的做法就是照抄数值产出一个
// spec —— 而它会被 schema 放行（step_type 是自由字符串）、被求解器静默忽略，
// 四道闸全绿却答非所问。拒答不是能力问题，是**被问到才会做的事**。
// ---------------------------------------------------------------------------
// >>> REFUSE_RULES:BEGIN（本区块由 _b2_refuse_rules.py --emit 生成，勿手改）
const REFUSE_RULES_BLOCK = `
   · **几何越界**（该族参数合法范围装不下）：
     - 柱壳：长桁数为 1/2/3/4 时**建不出**（能建的是 0，或 >= 5）；长桁数 < 0；框数 < 2；长桁高 >= 半径；框高 >= 半径；剖面类型只支持 blade，其余一律**建不出**；直径/长度/壁厚/长桁厚 <= 0。
     - 开孔板：孔直径/板长/板宽/板厚 <= 0；孔心使孔不在板内（含贴边）；孔直径 / 板宽 >= 1/3；板长 < 2 倍孔直径。
     - 加筋板：板长/板宽/板厚/长桁高/长桁厚 <= 0；长桁数 < 0；长桁高 >= 板宽。
     - 翼盒：中间腹板位置不在前后梁之间（含正好落在梁上）；腹板落在长桁站位上。
   · **能力越界**（求解器只有线性静力、小变形、金属弹性/铺层线弹性）：
     模态/固有频率、屈曲特征值、瞬态与冲击、接触、塑性/屈服后、疲劳寿命、热-结构耦合、复合材料失效准则（Hashin/Tsai-Wu 等）—— 一个都做不了。
`;
// <<< REFUSE_RULES:END

const REFUSE_ADDENDUM = `
★★ 本次任务类型：越界判定题（**以下六条优先于上文全部表述**）
1. 你拿到的是一段工程建模请求。其中**有一部分是当前建模与求解能力做不到的**，
   分两类：
${REFUSE_RULES_BLOCK}
2. 请求越界时**必须显式拒绝**，只输出：
   {"refuse": {"type": "geometry"|"capability", "blocked_by": "<单个标识符>", "reason": "<一句话>"}}
   ★ blocked_by **只能写一个**标识符，且必须是最直接卡住它的那一个：
     几何越界写参数键名，只能从这些里选：n_stringers / n_frames / stringer_height /
     frame_height / stringer_kind / hole_d / hole_x / hole_y / length / width /
     thickness / web_chordwise；
     能力越界写该分析类型的关键字，只能从这些里选：frequency / buckle / dynamic /
     contact / plastic / fatigue / thermal / failure。
   ★ **写多个标识符视为穷举，按错误处理**（这条是硬要求：拒绝的理由必须唯一）。
3. 请求**没有**越界时，按上文正常输出完整 spec JSON —— **不许拒绝**。
   把一个本来做得出来的请求拒掉，与静默建错同样是错。
4. 本次任务**不涉及缺失信息**：请求里的参数都已给全，不要输出 {"clarify":[...]}。
   「参数越界」与「参数缺失」不同：越界是给了一个做不出来的值，不是没给值。
5. 判断越界要**用上面第 1 条的规则去核参数值**，不要凭感觉；但也不要把
   「没见过的组合」当成越界 —— 范围之内的一律要建。
6. 只输出一个 JSON 对象（spec 或 {"refuse":{...}}），不要输出其他文字。`;

const SYS_REFUSE = SYS + '\n' + REFUSE_ADDENDUM;
const PROMPT_SHA_REFUSE = crypto.createHash('sha256').update(SYS_REFUSE, 'utf8').digest('hex');

// --mask-name：把 spec.name 换成中性 ID。N-17 的 19 条泄漏源就是 name 本身
// （name=open_hole_panel_400x200_d30 而省略的正是 hole_d）；遮掉它，题才真的在考「会不会问」。
// 只改**发给模型的呈现**，不改 tasks.jsonl（R65 冻结件）。
function maskName(taskId) {
  return 'case_' + crypto.createHash('sha256').update(String(taskId), 'utf8').digest('hex').slice(0, 8);
}

function buildUser(t, mask) {
  if (t.input_level !== 'L2')
    return `工程任务描述：\n${t.input.nl}\n请据此输出 spec JSON（或 {"clarify":[...]}）。`;
  const s = JSON.parse(JSON.stringify(t.input.spec_normalized || {}));
  if (mask) s.name = maskName(t.task_id);
  return `结构族=${t.family}。下面是一个已给定的 spec JSON（mm-t-s）。\n` +
    '★ 缺的键 = 用户没给该参数（不是 0、不是默认值）。\n' +
    JSON.stringify(s, null, 1) +
    '\n请输出完整 spec JSON；若缺键导致无法定义，输出 {"clarify":["…"]}，每条必须写出缺失字段的键名。';
}

// ---- 放宽版 schema：死字段不进 required（n_stringers_per_skin=0/缺 时 stringer 细节）----
function relaxedSchema(schemaPath) {
  const s = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
  const DEAD = ['stringer_height', 'stringer_thickness', 'stringer_kind', 'stringer_flange_width'];
  for (const cond of (s.allOf || [])) {
    const then = cond.then;
    if (!then || !then.required) continue;
    // 只放宽 wingbox/airfoil 分支（保守：该分支 properties 里含 airfoil）
    const props = (cond.if && cond.if.properties) || {};
    const fam = props.structure && props.structure.properties && props.structure.properties.family;
    const hasAirfoil = then.required.includes('airfoil') ||
                       (then.properties && then.properties.airfoil);
    if (fam || hasAirfoil) {
      then.required = then.required.filter(k => !DEAD.includes(k));
      const af = then.properties && then.properties.airfoil;
      if (af && af.required) af.required = af.required.filter(k => !DEAD.includes(k));
    }
  }
  return s;
}

// ---- 业务契约（与 evaluate.py 契约闸同口径）----
function contractErrors(spec) {
  const errs = [];
  if (!(spec.bc && Object.keys(spec.bc).length))
    errs.push('bc 块为空：必须给出边界条件（如 {"root_surface":"root","clamp":true}）');
  if ((spec.structure || {}).family === 'fuselage_barrel' &&
      !((spec.extra || {}).end_shear))
    errs.push('fuselage_barrel 缺 extra.end_shear（端部剪力是主载荷之一）');
  return errs;
}

function extractJSON(text) {
  const m = text.match(/\{[\s\S]*\}/);
  if (!m) return { clarify: text.trim(), spec: null };
  let obj;
  try { obj = JSON.parse(m[0]); } catch (e) { return { clarify: null, spec: null, parse_error: String(e) }; }
  // T-B2B5：拒答块先于 clarify 判定 —— 两者都是「不给 spec」，但用途完全不同，
  // 混在一起会让「拒对了」与「答不上来」看起来一样。
  if (obj.refuse) return { clarify: null, refuse: obj.refuse, spec: null };
  if (obj.clarify) return { clarify: JSON.stringify(obj.clarify), spec: null };
  return { clarify: null, spec: obj };
}

async function main() {
  const argv = process.argv.slice(2);
  const get = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
  // R53：只打印当前 SYS prompt 的 sha256（给 check_claims.py 的 S-39 做漂移闸用，
  // 不联网、不调模型）。改了 prompt 却没重生成 ⇒ 成绩单里的 sha 会与这里不等。
  if (argv.includes('--print-prompt-sha')) { console.log(PROMPT_SHA); return; }
  // T-A13a：L2 用的是另一份 SYS（SYS + 追加段），sha 必须单独报，不能与 L3 混用（R53）
  // ★ 这里**恒打印基准版**（`03129c56…`）：它是 C-041 的锚点，S-39 靠它做漂移闸。
  //   实验 arm 的 sha 走 --print-prompt-sha-l2-<arm>，两条命令互不干扰。
  if (argv.includes('--print-prompt-sha-l2')) { console.log(PROMPT_SHA_L2); return; }
  for (const [flag, val] of [['--print-prompt-sha-l2-strict', PROMPT_SHA_L2_STRICT],
                             ['--print-prompt-sha-l2-meshfix', PROMPT_SHA_L2_MESHFIX],
                             ['--print-prompt-sha-l2-strict-meshfix', PROMPT_SHA_L2_STRICT_MESHFIX],
                             ['--print-prompt-sha-l2-eff', PROMPT_SHA_L2_EFF]]) {
    if (argv.includes(flag)) { console.log(val); return; }
  }
  // T-B2B5：越界拒答卷同理会多一份 SYS，sha 单独报（R53 同纪律）
  if (argv.includes('--print-prompt-sha-refuse')) { console.log(PROMPT_SHA_REFUSE); return; }
  const tasksPath = get('--tasks', 'tasks/tasks.jsonl');
  const levels = (get('--levels', 'L3')).split(',');
  const splits = (get('--split', '')).split(',').filter(Boolean);
  const limit = parseInt(get('--limit', '30'), 10);
  const outDir = get('--out', 'candidates_l3_v2');
  const modelPin = get('--model', 'glm-5.3-flash');   // R13：可引用 id，不用 auto
  const schemaPath = get('--schema', '../FEM-Bench-Aero/schema_task.json');
  const maxTurns = parseInt(get('--max-turns', '3'), 10);
  // R31/冒烟：按 task_id 精确挑选（逗号分隔），用于改 prompt 后的 1 条/族冒烟，不必跑全卷
  const only = (get('--only', '') || '').split(',').filter(Boolean);
  // T-A13a：L2 呈现开关（默认关 = 与旧行为一致；开了才遮 name）
  const MASK_NAME = argv.includes('--mask-name');
  // T-L27c v3：本轮 L2 prompt 的 arm 标签，写进每条候选供事后分辨（R-A8 可追溯）
  const myArmTag = 'l2_' + _L2_ARM_TAG;
  // ---------------------------------------------------------------------
  // T-PSA（2026-11-01）：影子 prompt 入口。
  // ★ 只给 L3 用，**不改上面的 SYS 常量一个字节** —— 常量 sha 是 R53/S-39 的锚点，
  //   改常量会让四份 prompt-v2 代成绩单立刻与源码不等（S-39 必红）。
  //   本入口用于「先量化收益、后决定是否正式切换」：不传参时行为与旧版逐字节一致。
  // ★ 不接 L2：L2 的正确做法是 SYS + 追加段，用外部文件会把追加段丢掉 ⇒ 直接拒。
  // ---------------------------------------------------------------------
  const sysFile = get('--sys-file', '');
  let SYS_FROM_FILE = null;
  if (sysFile) {
    SYS_FROM_FILE = fs.readFileSync(sysFile, 'utf8');
    console.log(`[影子 prompt] ${sysFile} sha256=${crypto.createHash('sha256')
      .update(SYS_FROM_FILE, 'utf8').digest('hex').slice(0, 16)}…（SYS 常量未变）`);
  }
  fs.mkdirSync(outDir, { recursive: true });

  const ajv = new Ajv({ allErrors: true, strict: false });
  const validate = ajv.compile(relaxedSchema(schemaPath));

  const cloud = createWorkBuddyCloud({
    endpoint: publicConfig.endpoint,
    publishableKey: publicConfig.publishableKey,
  });
  const models = await cloud.llm.models.list();
  const model = models.find(m => m.id === modelPin) ||
                models.find(m => m.name === modelPin);
  if (!model) { console.error(`模型 ${modelPin} 不在列表中`); process.exit(2); }
  console.log(`模型: ${model.name} (${model.id})`);

  const tasks = fs.readFileSync(tasksPath, 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l));
  let sel = tasks.filter(t => levels.includes(t.input_level) &&
                              (!splits.length || splits.includes(t.split_v2)));
  if (only.length) {
    const miss = only.filter(id => !tasks.some(t => t.task_id === id));
    if (miss.length) { console.error(`--only 里这些 task_id 不在任务文件中：${miss.join(',')}`); process.exit(2); }
    sel = tasks.filter(t => only.includes(t.task_id));
  }
  sel = sel.slice(0, limit);
  if (SYS_FROM_FILE && sel.some(t => t.input_level === 'L2')) {
    console.error('--sys-file 不能用于 L2（会把 L2 追加段丢掉）⇒ 请用 --levels L3 或 L1');
    process.exit(2);
  }
  console.log(`生成 ${sel.length} 条候选（levels=${levels} splits=${splits.length ? splits : '全部'}, max_turns=${maxTurns}）`);

  for (const t of sel) {
    const outFile = path.join(outDir, `${t.task_id}.json`);
    if (fs.existsSync(outFile)) { console.log(`跳过（已存在）: ${t.task_id}`); continue; }
    process.stdout.write(`生成 ${t.task_id} … `);
    const sysPrompt = SYS_FROM_FILE || (t.input_level === 'L2' ? SYS_L2_EFF
      : t.input_level === 'REFUSE' ? SYS_REFUSE : SYS);
    const promptSha = SYS_FROM_FILE
      ? crypto.createHash('sha256').update(SYS_FROM_FILE, 'utf8').digest('hex')
      : (t.input_level === 'L2' ? PROMPT_SHA_L2_EFF
        : t.input_level === 'REFUSE' ? PROMPT_SHA_REFUSE : PROMPT_SHA);
    const messages = [{ role: 'system', content: sysPrompt },
                      { role: 'user', content: buildUser(t, MASK_NAME) }];
    const valHistory = [];
    let answer = '', spec = null, clarify = null, refuse = null, turnsUsed = 0;

    for (let turn = 1; turn <= maxTurns; turn++) {
      turnsUsed = turn;
      answer = '';
      try {
        for await (const chunk of cloud.llm.chat.completions.create({
          model: model.id,
          messages,
          stream: true,
          temperature: 0,
          response_format: { type: 'json_object' },
        })) {
          const d = chunk.choices[0]?.delta;
          if (d?.content) answer += d.content;
        }
      } catch (e) {
        console.log(`LLM 错误: ${e.error?.code || e.message}`);
        fs.writeFileSync(outFile, JSON.stringify({ task_id: t.task_id, input_level: t.input_level,
          model: model.id, error: e.error?.code || String(e.message), turns_used: turnsUsed }, null, 1));
        spec = undefined;   // 标记已写盘
        break;
      }
      const r = extractJSON(answer);
      if (r.parse_error) { valHistory.push({ turn, errors: ['JSON parse: ' + r.parse_error] }); }
      else if (r.refuse) { refuse = r.refuse; break; }
      else if (r.clarify && !r.spec) { clarify = r.clarify; break; }
      else {
        spec = r.spec;
        // ★★ L2：schema 校验 + 修复循环必须**关掉**。
        //   理由：澄清题的"正确答案"就是「不产出 spec」；而缺的那个键在 schema 里是 required
        //   ⇒ 修复循环会把「你缺 n_frames」当成错误推回给模型，等于**逼它编造**，
        //   直接污染被测行为（R20 判"静默编造"就再也测不出来了）。
        //   L2 下任何 spec 输出都由打分器记为 fabricated（judge_l3_candidate 的 ec 分支）。
        // ★★ T-B2B5 同一条理由：越界题的"正确答案"是拒绝，修复循环会把
        //   「你给的 spec 不合法」推回去，等于诱导它继续改 spec 而不是改口拒答。
        //   所以 kind==='refuse' 的题一次成型；对照题（kind==='build'）仍走完整
        //   修复循环，与 L3 口径一致才可比。
        if (t.input_level === 'L2' || t.kind === 'refuse') break;
        const ok = validate(spec);
        const cerr = ok ? contractErrors(spec) : [];
        if (ok && !cerr.length) break;
        const ALLOWED_HINT = {
          '/analysis': "analysis 允许键: solver/step_type/incremental/initial_increment/total_time/outputs（建议直接写 {}）",
          '/bc': "bc 允许键: root_surface/clamp（如 {\"root_surface\":\"root\",\"clamp\":true}）",
          '/extra': "extra 允许键: end_shear/end_moment/end_tension（柱壳专用，其余族写 {}）",
          '/mesh': "mesh 允许键: size_chord/size_span/order/refine_le",
          '/structure/params': "params 只允许该族 KNOWN_KEYS 内的键",
          '/material': "material 允许键: name/youngs_modulus/poisson_ratio/density/yield_strength",
        };
        const errors = (ok ? [] : validate.errors.map(e => {
          if (e.keyword === 'enum')
            return `${e.instancePath || '/'} 必须是 ${JSON.stringify(e.params.allowedValues)} 之一`;
          if (e.keyword === 'additionalProperties')
            return `${e.instancePath || '/'} 不允许的键 "${e.params.additionalProperty}"，请删除。${ALLOWED_HINT[e.instancePath] || ''}`;
          return `${e.instancePath || '/'} ${e.message}`;
        })).concat(cerr);
        valHistory.push({ turn, errors: errors.slice(0, 12) });
        spec = null;
        messages.push({ role: 'assistant', content: answer });
        messages.push({ role: 'user', content:
          `你的输出未通过 schema/契约校验，错误如下：\n- ${errors.slice(0, 12).join('\n- ')}\n` +
          `请修正后重新输出完整 spec JSON（仍然只输出一个 JSON 对象）。` });
      }
    }
    if (spec === undefined) continue;   // LLM 错误已写盘
    const row = { task_id: t.task_id, input_level: t.input_level, model: model.id,
                  kind: t.kind || null,
                  prompt_sha256: promptSha,
                  clarify, refuse, spec, turns_used: turnsUsed,
                  validation_history: valHistory, raw_len: answer.length };
    // T-A13a：L2 额外落一条「呈现方式」，否则事后无法分辨这批候选是遮了 name 还是没遮
    if (t.input_level === 'L2') {
      row.presentation = MASK_NAME ? 'spec_json_masked_name' : 'spec_json_raw_name';
      // T-L27c v3：标清哪条 prompt 分支产出的 —— 不同 arm 的分数**不可并列**（R53）
      row.prompt_arm = myArmTag;
    }
    fs.writeFileSync(outFile, JSON.stringify(row, null, 1));
    console.log(refuse ? `[REFUSE] ${JSON.stringify(refuse).slice(0, 70)}` :
                clarify ? `[CLARIFY] ${clarify.slice(0, 70)}` :
                spec ? `[spec] turns=${turnsUsed} fam=${(spec.structure || {}).family || '?'}` : `[UNRESOLVED] turns=${turnsUsed}`);
  }
  console.log('完成 -> ' + outDir);
}

if (require.main === module) {
  main().catch(e => { console.error('FATAL:', e.message); process.exit(2); });
}
module.exports = { relaxedSchema, contractErrors, extractJSON, buildUser, maskName,
                   PROMPT_SHA, PROMPT_SHA_L2, PROMPT_SHA_L2_STRICT, PROMPT_SHA_L2_MESHFIX,
                   PROMPT_SHA_L2_STRICT_MESHFIX, PROMPT_SHA_REFUSE,
                   SYS, SYS_L2, SYS_L2_EFF, L2_ADDENDUM, L2_STRICT_ADDENDUM, L2_MESHFIX_ADDENDUM,
                   SYS_REFUSE };
