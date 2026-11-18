// gen_repair_candidates.js — B5 注入缺陷修复题生成器（独立 prompt + 双模型）
// 从 tasks_repair_v1.jsonl 读带缺陷 spec，让模型对照 name 找出不自洽字段并输出修复后完整 spec。
// 缺陷位置/正确值不进 prompt——只给 broken_spec + name，考模型能不能定位并改对。
// 用法：
//   node gen_repair_candidates.js --model glm-5.3-flash --out candidates_repair_v1_glm
//   node gen_repair_candidates.js --model deepseek-v4-pro --out candidates_repair_v1_ds

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { createWorkBuddyCloud } = require('@tencent-ai/workbuddy-cloud-sdk');

function get(name, def) {
  const i = process.argv.indexOf('--' + name);
  return i >= 0 && process.argv[i + 1] && !process.argv[i + 1].startsWith('--')
    ? process.argv[i + 1] : def;
}

const publicConfig = {
  endpoint: 'https://fem-bench-baseline.app.workbuddy.host',
  publishableKey: process.env.WORKBUDDY_PUBLISHABLE_KEY,
};

// 独立 REPAIR prompt —— 不动 SYS（sha 6b90daf0 保持）
const SYS_REPAIR = `你是飞机结构有限元建模专家。下面给出一份 FEM-Bench-Aero 规范的 spec JSON（mm-t-s 单位制），
但它有【一个字段被注入了错误】——该字段与 spec 的 name / description 中明示的数值不自洽
（例如 name 里写 d20 但 hole_d 是别的值、name 里写 str3 但 n_stringers 是别的值、
name 里写 frm3 但 n_frames 是别的值、name 里写 n_ribs5 但 airfoil.n_ribs 是别的值）。

请对照 name / description 明示的信息，找出这个不自洽字段，把它改回与 name 一致的正确值，
并输出【修复后的完整 spec JSON】（其余所有字段保持原样，一个都不许改）。

铁律：
1. 只输出一个 JSON 对象，即修复后的完整 spec，不要输出解释、不要输出 clarify、不要包裹在别的键里。
2. 只改那一个不自洽字段的值；其它字段（包括 material、mesh、load、bc、analysis、extra）逐字段照抄输入，不许增删改。
3. name 是权威线索：name 中出现的尺寸/数量数值就是正确值。`;

const PROMPT_SHA = crypto.createHash('sha256').update(SYS_REPAIR, 'utf8').digest('hex');

function buildUser(row) {
  return `name: ${row.name}\n\n带缺陷的 spec JSON:\n${JSON.stringify(row.broken_spec, null, 1)}\n\n请输出修复后的完整 spec JSON。`;
}

function extractJSON(text) {
  if (!text) return { parse_error: 'empty' };
  let s = text.trim();
  const fb = s.indexOf('{'), lb = s.lastIndexOf('}');
  if (fb >= 0 && lb > fb) s = s.slice(fb, lb + 1);
  try { return { spec: JSON.parse(s) }; }
  catch (e) { return { parse_error: String(e.message).slice(0, 120) }; }
}

async function main() {
  const modelPin = get('model', 'glm-5.3-flash');
  const outDir = get('out', 'candidates_repair_v1_' + modelPin);
  const limit = parseInt(get('limit', '99'), 10);
  const tasksPath = get('tasks', 'tasks_repair_v1.jsonl');
  const tasks = fs.readFileSync(path.resolve(tasksPath), 'utf8')
    .split('\n').filter(l => l.trim()).slice(0, limit).map(l => JSON.parse(l));
  fs.mkdirSync(path.resolve(outDir), { recursive: true });

  const cloud = createWorkBuddyCloud(publicConfig);
  const models = await cloud.llm.models.list();
  const model = models.find(m => m.id === modelPin) || models.find(m => m.name === modelPin);
  if (!model) { console.error('模型不在列表: ' + modelPin); process.exit(2); }
  console.log(`模型: ${model.name} (${model.id})  prompt_sha=${PROMPT_SHA.slice(0, 8)}  题数=${tasks.length}`);

  for (const t of tasks) {
    process.stdout.write(`  ${t.task_id} ... `);
    const messages = [
      { role: 'system', content: SYS_REPAIR },
      { role: 'user', content: buildUser(t) },
    ];
    let answer = '';
    try {
      for await (const chunk of cloud.llm.chat.completions.create({
        model: model.id, messages, stream: true, temperature: 0,
        response_format: { type: 'json_object' },
      })) {
        const d = chunk.choices[0] && chunk.choices[0].delta;
        if (d && d.content) answer += d.content;
      }
    } catch (e) {
      const row = { task_id: t.task_id, model: model.id, prompt_sha: PROMPT_SHA,
                    error: (e.error && e.error.code) || String(e.message).slice(0, 160) };
      fs.writeFileSync(path.join(outDir, t.task_id + '.jsonl'), JSON.stringify(row) + '\n');
      console.log('LLM_ERR ' + row.error);
      continue;
    }
    const r = extractJSON(answer);
    const row = { task_id: t.task_id, model: model.id, prompt_sha: PROMPT_SHA,
                  spec: r.spec || null, parse_error: r.parse_error || null,
                  answer_len: answer.length };
    fs.writeFileSync(path.join(outDir, t.task_id + '.jsonl'), JSON.stringify(row) + '\n');
    console.log(r.spec ? 'spec OK' : ('parse ERR ' + r.parse_error));
  }
  console.log(`=== DONE -> ${outDir} ===`);
}
main().catch(e => { console.error('FATAL', e); process.exit(1); });
