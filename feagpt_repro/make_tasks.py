# -*- coding: utf-8 -*-
"""
make_tasks.py — 任务层生成器（ROADMAP W2-1 / W3 ID test / W2-4 任务层规范化）

设计决策（2026-10-24）：
- 发布数据集本体（modeling/）不动：死 airfoil 块与 chord int 只在【任务层】规范化，
  避免 spec_sha256 变更触发 110 truth 重导（D 系铁律）；dataset_card 登记已知限制。
- split 语义升级放任务层：manifest.split 原样保留（历史报告全部有效），
  tasks 用 split_v2 = train / val / id_test / extrapolation_test。
- ID test：从 train 包络内按参数谓词整类留出（翼盒等价类单例，类=条）。
  只在翼盒族实施（另三族 train ≤2 条，登记限制）。

输出：
  tasks/tasks.jsonl      L1（55）+ L2（55 模板派生）+ L3（人工 NL，另文件合并）
  tasks/nl_human.jsonl   30 条人工 NL 初稿（input_source=human，待老王抽检）

用法：
  python make_tasks.py            # 写盘
  python make_tasks.py --dry      # 只打印统计
"""
import json, os, copy, sys, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEA = os.path.join(ROOT, 'FEM-Bench-Aero')
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tasks')

# ---- ID test 谓词（吃 spec 参数，不吃 case_id；翼盒 train 包络内锚点整类留出）----
# 选轴原则：每条留出代表一个不同的设计轴锚点，5/21 = 23.8%（20–30% 带内）
ID_TEST_REGIONS = [
    {'axis': 'span',          'match': {'span': 1600.0}},
    {'axis': 'skin_thickness', 'match': {'skin_thickness': 4.0}},
    {'axis': 'n_ribs',        'match': {'n_ribs': 3}},        # train 肋轴锚点（chord 800/1000 两条整类）
    {'axis': 'n_stringers',   'match': {'n_stringers_per_skin': 5}},
    {'axis': 'tip_chord_ratio', 'match': {'tip_chord_ratio': 0.9}},
]

# L2 派生：可省略字段池（缺了必须澄清，不能静默默认）
L2_OMITABLE = {
    'wingbox': ['rib_thickness', 'n_stringers_per_skin', 'stringer_height', 'tip_chord_ratio'],
    'open_hole_panel': ['width', 'length'],
    'fuselage_barrel': ['n_stringers', 'n_frames'],
    'stiffened_panel': ['n_stringers'],
}


def load_spec(case_id):
    p = os.path.join(FEA, 'modeling', case_id, 'spec.json')
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def normalize_spec(spec, family):
    """任务层规范化：删 workdir；非翼盒删死 airfoil 块；chord 统一 float。"""
    s = copy.deepcopy(spec)
    s.pop('workdir', None)
    if family != 'wingbox':
        s.pop('airfoil', None)          # 死字段：非翼盒不生效，candidate 看到会被误导
    a = s.get('airfoil')
    if isinstance(a, dict) and 'chord' in a:
        a['chord'] = float(a['chord'])  # chord int → float（实测 5 条 int）
    return s


def airfoil_params(spec):
    a = spec.get('airfoil', {})
    return {k: (float(v) if isinstance(v, (int, float)) else v)
            for k, v in a.items() if isinstance(v, (int, float)) or isinstance(v, str)}


def id_test_hit(spec):
    """翼盒 train 的 ID 留出谓词：参数等值匹配即整类留出。"""
    ap = airfoil_params(spec)
    for region in ID_TEST_REGIONS:
        if all(abs(float(ap.get(k, -1)) - float(v)) < 1e-9 for k, v in region['match'].items()):
            return region['axis']
    return None


def make_l2_input(l1_spec, family):
    """从 L1 规范化 spec 删一个可省字段（轮换），返回 (input, omitted)。"""
    s = copy.deepcopy(l1_spec)
    pool = L2_OMITABLE.get(family, [])
    target = None
    if family == 'wingbox':
        a = s.get('airfoil', {})
        for k in pool:
            if k in a:
                target = ('airfoil', k); break
    else:
        p = s.get('structure', {}).get('params', {})
        for k in pool:
            if k in p:
                target = ('params', k); break
    if target is None:
        return None, None
    holder, key = target
    if holder == 'airfoil':
        del s['airfoil'][key]
    else:
        del s['structure']['params'][key]
    return s, key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    args = ap.parse_args()

    man = json.load(open(os.path.join(FEA, 'manifest.json'), encoding='utf-8'))
    tasks, stats = [], {'L1': 0, 'L2': 0, 'id_test': 0}
    id_assign = {}

    for c in man['cases']:
        if c['tree'] != 'modeling':
            continue
        cid, fam, split = c['case_id'], c['family'], c['split']
        raw = load_spec(cid)
        norm = normalize_spec(raw, fam)

        # split_v2
        if split == 'test':
            sv2, reason = 'extrapolation_test', 'manifest test（外推/新形式）→ extrapolation_test'
        elif split == 'val':
            sv2, reason = 'val', 'manifest val → val'
        else:
            hit = id_test_hit(raw) if fam == 'wingbox' else None
            if hit:
                sv2 = 'id_test'
                reason = f"train 内锚点整类留出（ID_TEST_REGIONS: {hit}）"
                id_assign[hit] = id_assign.get(hit, 0) + 1
            else:
                sv2, reason = 'train', 'train 未命中 ID 谓词'

        # L1
        tasks.append({
            'task_id': f'T{c["role"] and "" or ""}_L1_{cid}' if False else f'L1_{cid}',
            'family': fam, 'input_level': 'L1', 'input_source': 'template',
            'input': {'spec_normalized': norm},
            'truth_ref': f'modeling/{cid}/truth.json',
            'gates': ['mesh_quality', 'semantics', 'equilibrium', 'fidelity_disp'],
            'split_v2': sv2, 'split_reason': reason,
            'geometry_class': c['geometry_class'],
        })
        stats['L1'] += 1
        if sv2 == 'id_test':
            stats['id_test'] += 1

        # L2（模板派生：每 case 轮换省略字段）
        l2, omitted = make_l2_input(norm, fam)
        if l2 is not None:
            tasks.append({
                'task_id': f'L2_{cid}',
                'family': fam, 'input_level': 'L2', 'input_source': 'template',
                'input': {'spec_normalized': l2},
                'truth_ref': f'modeling/{cid}/truth.json',
                'gates': ['clarify_then_semantics', 'mesh_quality', 'semantics', 'fidelity_disp'],
                'split_v2': sv2, 'split_reason': reason + ' | L2 派生',
                'geometry_class': c['geometry_class'],
                'expected_clarifications': [omitted],
            })
            stats['L2'] += 1

    # ID 覆盖统计
    n_train_wb = sum(1 for t in tasks if t['input_level'] == 'L1'
                     and t['family'] == 'wingbox' and t['split_v2'] == 'train')
    n_id_wb = sum(1 for t in tasks if t['input_level'] == 'L1'
                  and t['family'] == 'wingbox' and t['split_v2'] == 'id_test')
    print(f"L1={stats['L1']}  L2={stats['L2']}  id_test={stats['id_test']}")
    print(f"翼盒 ID 留出: {n_id_wb}/{n_id_wb + n_train_wb} = "
          f"{100.0 * n_id_wb / max(1, n_id_wb + n_train_wb):.1f}%（目标 20–30%）")
    print('ID 轴覆盖:', id_assign)

    # 泄漏自检：等价类不得跨 split_v2
    cls = {}
    for t in tasks:
        if t['input_level'] != 'L1':
            continue
        cls.setdefault(t['geometry_class'], set()).add(t['split_v2'])
    leak = {k: v for k, v in cls.items() if len(v) > 1}
    print('等价类跨 split_v2 泄漏:', len(leak), '（应为 0）')
    if leak:
        print(leak)
        sys.exit(2)

    if not args.dry:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(os.path.join(OUT_DIR, 'tasks.jsonl'), 'w', encoding='utf-8') as f:
            for t in tasks:
                f.write(json.dumps(t, ensure_ascii=False) + '\n')
        print(f"[OK] 写盘 tasks/tasks.jsonl（{len(tasks)} 行）")

if __name__ == '__main__':
    main()
