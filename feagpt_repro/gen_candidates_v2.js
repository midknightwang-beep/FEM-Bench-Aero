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
★ 词汇约定（必须用这些词）：材料名 "Aluminium 2024-T3" 或 "CFRP-LAYUP"；翼型 code "4412"（不是 NACA4412）；载荷 kind "tip_force"（集中力）或 "pressure"（分布压力）；加筋长桁 kind "blade" 或 "T"；边界条件用 {"root_surface":"root","clamp":true}；载荷方向 direction 用 [x,y,z] 数组（法向即 [0,1,0]）；开孔板/加筋板载荷 kind="pressure" 用 magnitude（面压 MPa）或面内拉伸按用户描述；网格键 size_chord/size_span（翼盒）、size（板壳类）。
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
  if (argv.includes('--print-prompt-sha-l2')) { console.log(PROMPT_SHA_L2); return; }
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
    const sysPrompt = SYS_FROM_FILE || (t.input_level === 'L2' ? SYS_L2 : SYS);
    const promptSha = SYS_FROM_FILE
      ? crypto.createHash('sha256').update(SYS_FROM_FILE, 'utf8').digest('hex')
      : (t.input_level === 'L2' ? PROMPT_SHA_L2 : PROMPT_SHA);
    const messages = [{ role: 'system', content: sysPrompt },
                      { role: 'user', content: buildUser(t, MASK_NAME) }];
    const valHistory = [];
    let answer = '', spec = null, clarify = null, turnsUsed = 0;

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
      else if (r.clarify && !r.spec) { clarify = r.clarify; break; }
      else {
        spec = r.spec;
        // ★★ L2：schema 校验 + 修复循环必须**关掉**。
        //   理由：澄清题的"正确答案"就是「不产出 spec」；而缺的那个键在 schema 里是 required
        //   ⇒ 修复循环会把「你缺 n_frames」当成错误推回给模型，等于**逼它编造**，
        //   直接污染被测行为（R20 判"静默编造"就再也测不出来了）。
        //   L2 下任何 spec 输出都由打分器记为 fabricated（judge_l3_candidate 的 ec 分支）。
        if (t.input_level === 'L2') break;
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
                  prompt_sha256: promptSha,
                  clarify, spec, turns_used: turnsUsed,
                  validation_history: valHistory, raw_len: answer.length };
    // T-A13a：L2 额外落一条「呈现方式」，否则事后无法分辨这批候选是遮了 name 还是没遮
    if (t.input_level === 'L2') row.presentation = MASK_NAME ? 'spec_json_masked_name' : 'spec_json_raw_name';
    fs.writeFileSync(outFile, JSON.stringify(row, null, 1));
    console.log(clarify ? `[CLARIFY] ${clarify.slice(0, 70)}` :
                spec ? `[spec] turns=${turnsUsed} fam=${(spec.structure || {}).family || '?'}` : `[UNRESOLVED] turns=${turnsUsed}`);
  }
  console.log('完成 -> ' + outDir);
}

if (require.main === module) {
  main().catch(e => { console.error('FATAL:', e.message); process.exit(2); });
}
module.exports = { relaxedSchema, contractErrors, extractJSON, buildUser, maskName,
                   PROMPT_SHA, PROMPT_SHA_L2, SYS, SYS_L2 };
