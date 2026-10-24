// DOM-stub harness: actually execute every render function in the dashboard.
// Catches data-field mistakes that eyeballing the HTML would miss.
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(process.argv[2], 'utf8');

// ---- 1. tag balance via a tiny parser -------------------------------------
function balance(src) {
  const void_ = new Set(['br', 'hr', 'img', 'meta', 'link', 'input', 'area', 'base']);
  const re = /<(\/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?(\/?)>/g;
  const stack = [];
  const errs = [];
  let m;
  while ((m = re.exec(src))) {
    const [full, close, name, self] = m;
    const n = name.toLowerCase();
    if (void_.has(n) || self === '/') continue;
    if (!close) stack.push(n);
    else {
      if (stack.length && stack[stack.length - 1] === n) stack.pop();
      else errs.push(`unexpected </${n}> (stack top: ${stack[stack.length - 1] || 'empty'})`);
    }
  }
  return { unclosed: stack, errors: errs };
}

// balance the whole document, but with the <script> body blanked out (it
// contains '<' comparisons that would confuse a naive tag scanner)
const body = html.replace(/<script>[\s\S]*?<\/script>/g, '<script></script>');
const bal = balance(body);
console.log('tag balance: unclosed =', JSON.stringify(bal.unclosed), '| errors =', bal.errors.length ? bal.errors : 'none');

// ---- 2. execute the script against a stub DOM ------------------------------
const script = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'));

const store = {};
const els = {};
function mkEl(id) {
  return els[id] || (els[id] = {
    id, innerHTML: '', textContent: '', value: '', style: {}, dataset: {}, classList: {
      add() {}, remove() {}, toggle() {}, contains() { return false; }
    },
    addEventListener() {}, querySelectorAll() { return []; }, querySelector() { return null; },
    setSelectionRange() {}, select() {}, appendChild() {},
  });
}
const handlers = {};
global.document = {
  addEventListener: (ev, fn) => { (handlers[ev] = handlers[ev] || []).push(fn); },
  querySelector: sel => mkEl(sel),
  getElementById: id => mkEl(id),
  querySelectorAll: () => [],
  execCommand: () => true,
};
global.window = { scrollTo() {} };
global.localStorage = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
global.setTimeout = () => 0;
global.Date = Date;
global.JSON = JSON;
global.Object = Object;
global.console = console;

let failed = 0;
function check(label, cond, extra) {
  console.log(`  [${cond ? 'ok  ' : 'FAIL'}] ${label}${extra ? ' :: ' + extra : ''}`);
  if (!cond) failed++;
}

// Indirect eval -> runs in global scope.  The `const` declarations would be
// invisible to us afterwards, so the script also hands its data back explicitly.
const probe = '\n;globalThis.__D = {CASES, PANELS, FUSELAGE, OPENHOLE, SPLITS, DECISIONS, DECIDED, REVIEW, GATES, MODULES, GAPS, buildReceipt};';
try {
  (0, eval)(script + probe);
} catch (e) {
  console.log('  [FAIL] script threw:', e.message, '\n', e.stack);
  process.exit(1);
}
const D = globalThis.__D;

// run every DOMContentLoaded handler
(handlers['DOMContentLoaded'] || []).forEach(fn => fn());

// ---- 3. inspect what the render functions produced -------------------------
function grab(sel) { return mkEl(sel).innerHTML; }

const statrow = grab('#statrow');
const track = grab('#trackBody');
const gates = grab('#gateBody');
const cases = grab('#caseBody');
const panels = grab('#panelBody');
const fuselages = grab('#fuselageBody');
const openholes = grab('#t4Body');
const splits = grab('#splitBody');
const mods = grab('#modBody');
const gaps = grab('#gapBody');
const decDone = grab('#decDone');
const decs = grab('#decBody');
const rvs = grab('#rvBody');

check('renderStats 4 cards', (statrow.match(/class="stat /g) || []).length === 4, statrow.length + ' chars');
check('renderTrack 13 dots', (track.match(/class="dot"/g) || []).length === 13, track.length + ' chars');
check('renderGates 6 gates', (gates.match(/class="gate"/g) || []).length === 6);
check('renderCases rows = CASES', (cases.match(/class="expander"/g) || []).length === D.CASES.length,
  (cases.match(/class="expander"/g) || []).length + ' rows');
check('renderCases details = CASES', (cases.match(/class="detail"/g) || []).length === D.CASES.length);
check('renderPanels rows = PANELS', (panels.match(/class="expander"/g) || []).length === D.PANELS.length,
  (panels.match(/class="expander"/g) || []).length + ' rows');
check('renderPanels details = PANELS', (panels.match(/class="detail"/g) || []).length === D.PANELS.length);
check('renderFuselage rows = FUSELAGE', (fuselages.match(/class="expander"/g) || []).length === D.FUSELAGE.length,
  (fuselages.match(/class="expander"/g) || []).length + ' rows');
check('renderFuselage details = FUSELAGE', (fuselages.match(/class="detail"/g) || []).length === D.FUSELAGE.length);
check('renderOpenHole rows = OPENHOLE', (openholes.match(/class="expander"/g) || []).length === D.OPENHOLE.length,
  (openholes.match(/class="expander"/g) || []).length + ' rows');
check('renderOpenHole details = OPENHOLE', (openholes.match(/class="detail"/g) || []).length === D.OPENHOLE.length);
check('renderSplits 3 columns', (splits.match(/class="splitcol /g) || []).length === 3, splits.length + ' chars');
check('renderSplits rows = SPLITS.rows', (splits.match(/class="cid"/g) || []).length === D.SPLITS.rows.length,
  (splits.match(/class="cid"/g) || []).length + ' rows');
check('renderSplits states the leakage gate', splits.indexOf('泄漏闸') >= 0);
check('every split row has a valid split',
  D.SPLITS.rows.every(r => ['train', 'val', 'test'].includes(r.split)));

// The dashboard's split table is a *transcription* of manifest.json.  A
// transcription can drift, and a drifted dashboard silently quotes numbers
// nobody measured -- so read the manifest back and compare case by case.
try {
  const root = path.dirname(path.resolve(process.argv[2]));
  const man = JSON.parse(fs.readFileSync(path.join(root, 'FEM-Bench-Aero', 'manifest.json'), 'utf8'));
  const want = new Map(man.cases.map(c => [c.case_id, c.split]));
  const wrong = D.SPLITS.rows.filter(r => want.get(r.id) !== r.split).map(r => r.id);
  const extra = [...want.keys()].filter(id => !D.SPLITS.rows.some(r => r.id === id));
  check('dashboard split table matches manifest.json', wrong.length === 0 && extra.length === 0,
    `wrong: [${wrong.join(',')}] missing: [${extra.join(',')}]`);
  // `why` is now the rule's *output* (manifest.split_reason), so it is a
  // transcription too -- and a transcription can drift.
  const reason = new Map(man.cases.map(c => [c.case_id, c.split_reason]));
  const wrongWhy = D.SPLITS.rows.filter(r => reason.get(r.id) !== r.why).map(r => r.id);
  check('dashboard split reasons match manifest split_reason', wrongWhy.length === 0,
    `wrong: [${wrongWhy.join(',')}]`);
  check('dashboard split counts match manifest summary',
    D.SPLITS.n_cases === man.summary.n_cases &&
    D.SPLITS.n_classes === man.summary.n_geometry_classes &&
    D.SPLITS.n_leaky === man.summary.n_leaky_classes,
    `manifest: ${man.summary.n_cases} cases / ${man.summary.n_geometry_classes} classes / ${man.summary.n_leaky_classes} leaky`);
} catch (e) {
  check('dashboard split table matches manifest.json', false, e.message);
}
check('renderModules 22 bars', (mods.match(/class="mod"/g) || []).length === 22);
check('renderGaps 14 gaps', (gaps.match(/class="gap"/g) || []).length === 14);
check('renderDecided table 37 rows', (decDone.match(/<tr>/g) || []).length === 38, 'header+37');
check('renderDecisions = DECISIONS', (decs.match(/class="dec"/g) || []).length === D.DECISIONS.length);
check('renderReview = REVIEW', (rvs.match(/class="rv /g) || []).length === D.REVIEW.length,
  (rvs.match(/class="rv /g) || []).length + ' cards');

// every review card must have cmd / ev / files populated
const reviewJs = D.REVIEW;
let bad = [];
reviewJs.forEach(r => {
  if (!r.cmd || !r.ev || !r.ev.length || !r.files || !r.files.length || !r.q || !r.c || !r.g) bad.push(r.id);
});
check('every review card has cmd+ev+files+q+c+g', bad.length === 0, bad.length ? 'missing: ' + bad.join(',') : '');

// every case row must carry the fields the template reads
const casesJs = D.CASES;
bad = [];
casesJs.forEach(c => {
  ['id', 'ribs', 'chord', 'shape', 'str', 'faces', 'nodes', 'elems', 'u', 'ua', 'du', 'med', 'eqc', 'eqa',
   'vm', 'vmm', 'vmf', 'srcc', 'srca'].forEach(k => {
    if (c[k] === undefined || c[k] === null || c[k] === '') bad.push(`${c.id}.${k}`);
  });
});
check('every case row has all template fields', bad.length === 0, bad.length ? 'missing: ' + bad.join(',') : '');

// The 平面形状 column is the one that keeps a T1 row from looking like a
// duplicate of the baseline (same 肋/弦长).  A row whose id says sweep/taper but
// whose shape cell says 等直 is a transcription slip, not a model.
const misShape = casesJs.filter(c => /_sweep|_taper/.test(c.id) && c.shape === '等直').map(c => c.id);
const noShape = casesJs.filter(c => c.shape === undefined).map(c => c.id);
check('planform column filled for every swept/tapered row',
  misShape.length === 0 && noShape.length === 0,
  `says 等直: [${misShape.join(',')}] missing: [${noShape.join(',')}]`);

check('per-case source roots are set', casesJs.every(c => c.srcc && c.srca), '');

// the open-hole family (T4) row template
const holesJs = D.OPENHOLE;
bad = [];
holesJs.forEach(g => {
  ['id', 'd', 'lam', 'pos', 'faces', 'curves', 'nodes', 'elems', 'minj',
   'u', 'ua', 'du', 'ktg', 'ktn', 'edge', 'vmC', 'vmA', 'srcc', 'srca',
   'specpath'].forEach(k => {
    if (g[k] === undefined || g[k] === null || g[k] === '') bad.push(`${g.id}.${k}`);
  });
  // how / err are legitimately null on the off-centre coupon - Howland is a
  // centred-hole solution and does not apply - but the keys must be present so
  // the render branch is explicit rather than accidental.
  if (!('how' in g) || !('err' in g)) bad.push(`${g.id}.how/err key missing`);
  if (!g.v || typeof g.v !== 'object') { bad.push(`${g.id}.v`); return; }
  ['kt', 'conv', 'eq', 'trend', 'cross', 'mesh', 'env'].forEach(k => {
    if (!(k in g.v)) bad.push(`${g.id}.v.${k}`);
  });
});
check('every open-hole row has all template fields', bad.length === 0,
  bad.length ? 'missing: ' + bad.join(',') : '');

// The off-centre coupon must *say* that Howland does not apply, instead of
// printing a comparison against a solution for a centred hole.
check('off-centre coupon says Howland does not apply',
  openholes.indexOf('不判 Howland') >= 0);

// A Kt quoted without its convention is not a number, so the printed column
// must name the convention it is on.
check('open-hole render names the Kt convention (gross)',
  openholes.indexOf('Kt_gross') >= 0);

// every panel row must carry its own (different) template fields
const panelsJs = D.PANELS;
bad = [];
panelsJs.forEach(p => {
  ['id', 'n_str', 'faces', 'nodes', 'elems', 'minj', 'u', 'ua', 'du',
   'eqc', 'eqa', 'vm', 'vmm', 'vmf', 'srcc', 'srca'].forEach(k => {
    if (p[k] === undefined || p[k] === null || p[k] === '') bad.push(`${p.id}.${k}`);
  });
  // med / navier are legitimately null on models where the comparison does not
  // apply - but the key must be present so the template branch is explicit.
  if (!('med' in p) || !('navier' in p)) bad.push(`${p.id}.med/navier key missing`);
});
check('every panel row has all template fields', bad.length === 0, bad.length ? 'missing: ' + bad.join(',') : '');

// The panel detail block is now driven by a per-row `v` object (the six
// independent verifications, each measured on that plate).  A row that ships
// without it, or with a missing key, would either throw at render time or --
// worse -- print another plate's number.
bad = [];
panelsJs.forEach(p => {
  if (!p.v || typeof p.v !== 'object') { bad.push(`${p.id}.v`); return; }
  ['navier', 'area', 'sumz', 'react', 'sym', 'outer', 'stiff'].forEach(k => {
    if (!(k in p.v)) bad.push(`${p.id}.v.${k}`);
  });
  if (!p.specpath) bad.push(`${p.id}.specpath`);
  if (p.force === undefined || p.force === null) bad.push(`${p.id}.force`);
});
check('every panel row carries its own verification block (v)', bad.length === 0,
  bad.length ? 'missing: ' + bad.join(',') : '');

// the plain panel is the one model where the per-node stress comparison does
// not apply - the rendered card must say so rather than print a number.
check('plain panel renders the "not comparable" note',
  panels.indexOf('不可比') >= 0 && panels.indexOf('膜场恒为 0') >= 0);

// the tooltip text must actually mention the right roots
check('str3_T repro command uses outputs_T',
  cases.indexOf('--ccx outputs_T --abaqus outputs_T_abaqus --case naca4412_wingbox_str3_T') >= 0);
check('panel repro command uses outputs_panel + _t2_probe spec',
  panels.indexOf('--ccx outputs_panel --abaqus outputs_panel_abaqus') >= 0 &&
  panels.indexOf('_t2_probe/stiffened_panel_600x600.spec.json') >= 0);

const r1 = grab('#rcpt');
// buildReceipt is exercised through the button handler
(handlers['DOMContentLoaded'] || []).forEach(() => {});
try {
  const receipt = D.buildReceipt();
  const lines = receipt.split('\n');
  check('buildReceipt non-empty', lines.length > 20, lines.length + ' lines');
  check('receipt mentions 已拍板', receipt.indexOf('已拍板') >= 0);
  check('receipt lists all DECISIONS', D.DECISIONS.every(d => receipt.indexOf(d.q) >= 0));
} catch (e) {
  check('buildReceipt', false, e.message);
}

console.log(failed === 0 ? '\nALL CHECKS PASS' : `\n${failed} CHECK(S) FAILED`);
process.exit(failed === 0 ? 0 : 2);
