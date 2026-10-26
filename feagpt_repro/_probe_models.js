// _probe_models.js — W5b-5 前置：实测服务端可用模型 id（R13：可引用 id，不猜）
// 用法：node _probe_models.js [--out reports/diagnostics/models_available.json]
const fs = require('fs');
const path = require('path');
const { createWorkBuddyCloud } = require('@tencent-ai/workbuddy-cloud-sdk');

const publicConfig = {
  endpoint: 'https://fem-bench-baseline.app.workbuddy.host',
  publishableKey: process.env.WORKBUDDY_PUBLISHABLE_KEY,
};

(async () => {
  const argv = process.argv.slice(2);
  const get = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
  const outPath = get('--out', 'reports/diagnostics/models_available.json');

  if (!publicConfig.publishableKey) {
    console.error('!! WORKBUDDY_PUBLISHABLE_KEY 未设置（R31 生成前 key 预检失败）');
    process.exit(3);
  }

  const cloud = createWorkBuddyCloud({
    endpoint: publicConfig.endpoint,
    publishableKey: publicConfig.publishableKey,
    appId: 'wbapp_Tl8jf0GeqRmnK59Hr64PuS',
  });

  const models = await cloud.llm.models.list();
  const rows = (models || []).map(m => ({
    id: m.id, name: m.name, owned_by: m.owned_by || null,
    created: m.created || null,
  }));

  const rec = {
    note: 'W5b-5 前置探针：服务端 llm.models.list() 实测结果。R13 要求模型 id 可引用、不猜。',
    endpoint: publicConfig.endpoint,
    probed_at: new Date().toISOString(),
    n_models: rows.length,
    models: rows,
  };
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(rec, null, 1), 'utf8');

  console.log(`模型数 = ${rows.length}  ->  ${outPath}`);
  for (const r of rows) console.log(`  ${String(r.id).padEnd(34)} ${r.name}`);
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
