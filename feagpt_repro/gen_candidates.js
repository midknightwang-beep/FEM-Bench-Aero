// gen_candidates.js — W4b-2：通用大模型生成 spec 候选（keyless 云服务 LLM）
// 用法：node gen_candidates.js --tasks tasks/tasks.jsonl --levels L1 --split extrapolation_test,boundary_holdout --limit 3 --out candidates
// 约束：system 消息必须为 messages[0]（云服务契约）；stream:true 必须；response_format json_object。
const fs = require('fs');
const path = require('path');
const { createWorkBuddyCloud } = require('@tencent-ai/workbuddy-cloud-sdk');

// publicConfig（来自 workbuddy_cloud_service activate；publishableKey 无权限语义，服务器强制 Origin 校验）
const publicConfig = {
  endpoint: 'https://fem-bench-baseline.app.workbuddy.host',
  publishableKey: 'wbpk_Tl8jf0GeqRmnK59Hr64PuS_YbTt47wyoaLYqpM6XxSjSowLCwffsO8Z',
};

const SYS = `你是飞机结构有限元建模专家。根据用户给出的结构描述，输出一个 FEM-Bench-Aero 规范的 spec JSON。
必须严格遵循以下结构（mm-t-s 单位制）：
{"name":"<case名>","description":"<一句话>","material":{...按用户给的...},
"structure":{"family":"<wingbox|open_hole_panel|fuselage_barrel|stiffened_panel>","params":{...}},
"airfoil":{...仅 wingbox 需要...},"mesh":{...},"load":{...},"bc":{},"analysis":{},"extra":{}}
★ 铁律：用户给出的 mesh/load/材料/参数字段必须【逐字段原样照抄】（键名和数值都不许改、不许省略、不许新增默认值）——mesh 块尤其要完整抄写用户给出的全部键。
各族的 params/airfoil 按用户描述填写；用户没给的尺寸参数必须原样保留缺失（不得编造默认值）——如需澄清则先输出 "CLARIFY:" 再列问题。
只输出一个 JSON 对象；数值一律用浮点（如 1000.0 而不是 1000）。`;

function specPrompt(task) {
  const fam = task.family;
  if (task.input_level === 'L1') {
    const s = task.input.spec_normalized;
    return `结构族=${fam}。请严格按以下参数生成 spec JSON（参数必须逐一采用，不得改动任何数值）：\n` +
           JSON.stringify(s.structure && s.structure.family === 'wingbox' ? s.airfoil : s.structure.params, null, 1) +
           `\n载荷: ${JSON.stringify(s.load)}；网格: ${JSON.stringify(s.mesh)}；材料: ${JSON.stringify(s.material)}`;
  }
  if (task.input_level === 'L2') {
    return `结构族=${fam}。以下是含缺失字段的参数（缺失项标 "MISSING"）：\n` +
           JSON.stringify(task.input.spec_normalized, null, 1) +
           `\n请对每个 MISSING 字段先提出澄清问题（不要猜值）。若你能合理推断工程默认值，也请说明假设。输出 spec JSON 或 CLARIFY 问题列表。`;
  }
  return `工程任务描述：\n${task.input.nl}\n请据此生成 spec JSON。`;
}

function extractJSON(text) {
  const m = text.match(/\{[\s\S]*\}/);
  if (!m) return { clarify: text.trim(), spec: null };
  try { return { spec: JSON.parse(m[0]), clarify: null }; }
  catch (e) { return { clarify: 'JSON parse error: ' + text.slice(0, 200), spec: null }; }
}

async function main() {
  const argv = process.argv.slice(2);
  const get = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
  const tasksPath = get('--tasks', 'tasks/tasks.jsonl');
  const levels = (get('--levels', 'L1')).split(',');
  const splits = (get('--split', '')).split(',').filter(Boolean);
  const limit = parseInt(get('--limit', '3'), 10);
  const outDir = get('--out', 'candidates');
  fs.mkdirSync(outDir, { recursive: true });

  const cloud = createWorkBuddyCloud({
    endpoint: publicConfig.endpoint,
    publishableKey: publicConfig.publishableKey,
  });

  const models = await cloud.llm.models.list();
  if (!models.length) { console.error('模型列表为空'); process.exit(2); }
  const model = models.find(m => m.disabled !== true);
  console.log(`模型: ${model.name} (${model.id})`);

  const tasks = fs.readFileSync(tasksPath, 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l));
  let sel = tasks.filter(t => levels.includes(t.input_level) &&
                              (!splits.length || splits.includes(t.split_v2)));
  sel = sel.slice(0, limit);
  console.log(`生成 ${sel.length} 条候选（levels=${levels} splits=${splits.length ? splits : '全部'}）`);

  for (const t of sel) {
    const outFile = path.join(outDir, `${t.task_id}.json`);
    if (fs.existsSync(outFile)) { console.log(`跳过（已存在）: ${t.task_id}`); continue; }
    process.stdout.write(`生成 ${t.task_id} … `);
    let answer = '';
    try {
      for await (const chunk of cloud.llm.chat.completions.create({
        model: model.id,
        messages: [{ role: 'system', content: SYS }, { role: 'user', content: specPrompt(t) }],
        stream: true,
        temperature: 0,
      })) {
        const d = chunk.choices[0]?.delta;
        if (d?.content) answer += d.content;
      }
    } catch (e) {
      console.log(`LLM 错误: ${e.error?.code || e.message}`);
      fs.writeFileSync(outFile, JSON.stringify({ task_id: t.task_id, error: e.error?.code || String(e.message) }, null, 1));
      continue;
    }
    const { spec, clarify } = extractJSON(answer);
    const row = { task_id: t.task_id, input_level: t.input_level, model: model.id,
                  clarify, spec, raw_len: answer.length };
    fs.writeFileSync(outFile, JSON.stringify(row, null, 1));
    console.log(clarify ? `[CLARIFY] ${clarify.slice(0, 60)}` : `[spec] ${(spec?.structure || {}).family || '?'}`);
  }
  console.log('完成 -> ' + outDir);
}

main().catch(e => { console.error('FATAL:', e.message); process.exit(2); });
