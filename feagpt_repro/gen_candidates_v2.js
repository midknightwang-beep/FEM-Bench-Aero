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
★ 缺失信息处理：用户没给的尺寸参数【不得编造】，输出 {"clarify": ["问题1", ...]} 列出需要澄清的字段（json_object 模式下澄清也必须是这个 JSON 形式）。仅当缺失字段使模型无法定义时才澄清；以下工程惯例视为"无该特征"而非缺失：未提锥度→tip_chord_ratio=1.0；未提后掠→sweep_deg=0；未提长桁→长桁数=0；未提中间腹板→web_chordwise=[]（不要把前后梁位置复制到 web_chordwise）；铺层板基材按用户描述（铝板则 material 用铝）。
★ 长桁键名按族（键名即契约）：翼盒用 n_stringers_per_skin；柱壳与加筋壁板用 n_stringers。长桁细节键（stringer_height/stringer_thickness/stringer_kind/stringer_flange_width）只有当该族确有长桁且用户给出了具体尺寸时才填写；用户没给尺寸时【直接省略这些键】（求解器按族默认取值），绝不要填 0。
★ 词汇约定（必须用这些词）：材料名 "Aluminium 2024-T3" 或 "CFRP-LAYUP"；翼型 code "4412"（不是 NACA4412）；载荷 kind "tip_force"（集中力）或 "pressure"（分布压力）；加筋长桁 kind "blade" 或 "T"；边界条件用 {"root_surface":"root","clamp":true}；载荷方向 direction 用 [x,y,z] 数组（法向即 [0,1,0]）；开孔板/加筋板载荷 kind="pressure" 用 magnitude（面压 MPa）或面内拉伸按用户描述；网格键 size_chord/size_span（翼盒）、size（板壳类）。
★ fuselage_barrel 的载荷组合（端剪/端弯）写进 extra.end_shear / extra.end_moment（数值用 N 和 N·mm）。
材料按名称给出 E/ν/密度/屈服（铝 2024-T3: E=73100 MPa, ν=0.33, ρ=2.78e-9 t/mm^3, 屈服=345 MPa；T300/环氧参考用户给定）。
只输出一个 JSON 对象（spec 或 clarify），不要输出其他文字。`;

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
  const tasksPath = get('--tasks', 'tasks/tasks.jsonl');
  const levels = (get('--levels', 'L3')).split(',');
  const splits = (get('--split', '')).split(',').filter(Boolean);
  const limit = parseInt(get('--limit', '30'), 10);
  const outDir = get('--out', 'candidates_l3_v2');
  const modelPin = get('--model', 'glm-5.3-flash');   // R13：可引用 id，不用 auto
  const schemaPath = get('--schema', '../FEM-Bench-Aero/schema_task.json');
  const maxTurns = parseInt(get('--max-turns', '3'), 10);
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
  sel = sel.slice(0, limit);
  console.log(`生成 ${sel.length} 条候选（levels=${levels} splits=${splits.length ? splits : '全部'}, max_turns=${maxTurns}）`);

  for (const t of sel) {
    const outFile = path.join(outDir, `${t.task_id}.json`);
    if (fs.existsSync(outFile)) { console.log(`跳过（已存在）: ${t.task_id}`); continue; }
    process.stdout.write(`生成 ${t.task_id} … `);
    const messages = [{ role: 'system', content: SYS },
                      { role: 'user', content: `工程任务描述：\n${t.input.nl}\n请据此输出 spec JSON（或 {"clarify":[...]}）。` }];
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
                  clarify, spec, turns_used: turnsUsed,
                  validation_history: valHistory, raw_len: answer.length };
    fs.writeFileSync(outFile, JSON.stringify(row, null, 1));
    console.log(clarify ? `[CLARIFY] ${clarify.slice(0, 70)}` :
                spec ? `[spec] turns=${turnsUsed} fam=${(spec.structure || {}).family || '?'}` : `[UNRESOLVED] turns=${turnsUsed}`);
  }
  console.log('完成 -> ' + outDir);
}

if (require.main === module) {
  main().catch(e => { console.error('FATAL:', e.message); process.exit(2); });
}
module.exports = { relaxedSchema, contractErrors, extractJSON };
