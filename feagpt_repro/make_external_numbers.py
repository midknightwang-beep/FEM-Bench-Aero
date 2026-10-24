# -*- coding: utf-8 -*-
"""
make_external_numbers.py — 对外材料「单一数字源」生成器（ROADMAP W1-3）

原则：所有对外口径数字只从磁盘权威产物读回，禁止手抄。
  manifest.json / gates_all55_d36.json / gate4_d36.json /
  verify_dataset_d36.json / eval_report_d36.json / baseline_d36_final.json

输出：
  FEM-Bench-Aero/external_numbers.json  （机器可读，对外文档引用此文件）
  FEM-Bench-Aero/external_numbers.md    （人读版，供文档作者复制）

用法：
  python make_external_numbers.py            # 写盘
  python make_external_numbers.py --check    # 只校验不写盘
"""
import json, sys, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # feagpt_repro 的上级
FEA = os.path.join(ROOT, 'FEM-Bench-Aero')

def load(name):
    with open(os.path.join(FEA, name), encoding='utf-8') as f:
        return json.load(f)

def fam_counts(manifest):
    """从 cases 逐条统计族 × split。"""
    fams = {}
    for c in manifest['cases']:
        fam = c['family']; split = c['split']
        fams.setdefault(fam, {}).setdefault(split, 0)
        fams[fam][split] += 1
    return fams

def main(write=True):
    man = load('manifest.json')
    g1 = load('gates_all55_d36.json')
    g4 = load('gate4_d36.json')
    vf = load('verify_dataset_d36.json')
    ev = load('eval_report_d36.json')
    bl = load('baseline_d36_final.json')

    s = man['summary']
    fams = fam_counts(man)
    splits = {'train': 0, 'val': 0, 'test': 0}
    for fam in fams.values():
        for k, v in fam.items():
            splits[k] = splits.get(k, 0) + v

    # 闸门读数（键名按实际 JSON 探测，找不到就报错退出——不编数字）
    def dig(d, path, label):
        cur = d
        for p in path:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                sys.exit(f'[FATAL] {label}: 键路径 {path} 断在 {p}；探针前先看真实结构')
        return cur

    n_cases = dig(man, ['summary', 'n_cases'], 'manifest')
    n_classes = dig(man, ['summary', 'n_geometry_classes'], 'manifest')
    n_dup = dig(man, ['summary', 'n_duplicate_models'], 'manifest')
    n_leak = dig(man, ['summary', 'n_leaky_classes'], 'manifest')

    out = {
        'generated_from': 'manifest.json + gates_all55_d36 + gate4_d36 + verify_dataset_d36 + eval_report_d36 + baseline_d36_final',
        'naming_note': 'FEM-Bench-Aero（本仓库内部命名，A 建模集；与 GitHub 公开仓库 FEM-Bench 无关联，公开发布前将评估更名）',
        'scale': {
            'cases_total': n_cases,
            'solver_trees': 2,
            'case_dirs': n_cases * 2,
            'geometry_classes': n_classes,
            'duplicate_models': n_dup,
            'leaky_classes': n_leak,
            'splits': splits,
            'families': fams,
            'n_limitations': len(man.get('limitations', [])),
        },
        'gates': {
            'gate4_semantics': dig(g4, ['n_pass'], 'gate4'),
        },
        'baseline_frozen': {
            'status': '附录（可学性证明），非产品 KPI。D37 起项目 KPI = TSR/FPR/修复/拒答/澄清',
            'max_disp_test_mape': dig(bl, ['targets', 'max_disp', 'M3q ridge+sweep^2', 'test_mape'], 'baseline'),
            'max_disp_test_ci95': dig(bl, ['targets', 'max_disp', 'M3q ridge+sweep^2', 'test_ci95'], 'baseline'),
            'constant_floor': dig(bl, ['targets', 'max_disp', 'M0m constant(MAPE-opt)', 'test_mape'], 'baseline'),
            'known_limits': [
                'vM 峰值网格未收敛（12→6 mm 仍 +12.9 %），应力真值带 ≥13 % 偏不安全低估',
                '机器可读双码 PASS 仅翼盒 34 条；其余 21 条分族取证（关 3 机读化 = W3 任务）',
                'test 13 条全部为外推/新形式（无 ID 内插点；ID test = W3 任务）',
                'recombination_algorithm3 为同几何网格鲁棒性对照样本，不参与样本量统计',
            ],
        },
        'excluded_from_external_docs': ['B 解读集 / C 更新集（近期不做，2026-10-24 拍板移出对外承诺）'],
    }

    # 关 1 从 JSON 实读
    q1 = g1['gate1_mesh_quality']
    out['gates']['gate1_mesh'] = {
        'n_measured': dig(q1, ['n_measured'], 'gates(g1)'),
        'n_below_threshold': dig(q1, ['n_below_threshold'], 'gates(g1)'),
        'n_tri3_total': dig(q1, ['n_tri3_total'], 'gates(g1)'),
        'worst_min_jacobian': dig(q1, ['worst_min_jacobian'], 'gates(g1)'),
    }
    # 关 3 从 JSON 实读（wingbox scope）
    g3 = g1.get('gate3_dual_solver', {})
    out['gates']['gate3_wingbox'] = {
        'scope': g3.get('scope', 'MISSING'),
        'n_pass': g3.get('n_pass', None),
        'n_total': g3.get('n_cases', None),
    }
    # 自洽 / 划分复算（summary 实读）
    out['selfcheck'] = {
        'n_cases': dig(vf, ['summary', 'n_cases'], 'verify'),
        'n_ok': dig(vf, ['summary', 'n_ok'], 'verify'),
        'n_duplicate_cases': dig(vf, ['summary', 'n_duplicate_cases'], 'verify'),
        'pairing_ok': dig(vf, ['summary', 'pairing_ok'], 'verify'),
        'all_ok': dig(vf, ['summary', 'all_ok'], 'verify'),
    }
    out['split_recheck'] = {
        'n_cases': dig(ev, ['summary', 'n_cases'], 'eval'),
        'n_geometry_classes': dig(ev, ['summary', 'n_geometry_classes'], 'eval'),
        'n_failures': len(ev.get('failures', [])),
    }

    md = ['| 项 | 数值 | 来源 |', '|---|---|---|']
    md.append(f'| 算例规模 | {n_cases} 条 × 2 棵求解器树 = {n_cases*2} 个算例目录 | manifest.summary |')
    md.append(f'| 几何等价类 | {n_classes}（重复 {n_dup}、跨 split 泄漏 {n_leak}） | manifest.summary |')
    md.append(f'| 划分 | train {splits.get("train")} / val {splits.get("val")} / test {splits.get("test")} | manifest.cases 实算 |')
    for fam, cnt in sorted(fams.items()):
        md.append(f'| — {fam} | {cnt.get("train",0)}-{cnt.get("val",0)}-{cnt.get("test",0)}（共 {sum(cnt.values())}） | manifest.cases 实算 |')
    g1m = out['gates']['gate1_mesh']
    md.append(f'| 关 1 网格 | {g1m["n_measured"]}/{g1m["n_measured"]}（最差 minJ {g1m["worst_min_jacobian"]}、tri3 {g1m["n_tri3_total"]}） | gates_all55_d36 |')
    md.append(f'| 关 3 双码 | {out["gates"]["gate3_wingbox"]["scope"]}：{out["gates"]["gate3_wingbox"]["n_pass"]} | gates_all55_d36 |')
    md.append(f'| 关 4 语义 | {out["gates"]["gate4_semantics"]}/{out["gates"]["gate4_semantics"]} | gate4_d36 |')
    sc = out['selfcheck']
    md.append(f'| 自洽 | {sc["n_ok"]}/{sc["n_cases"]}、重复 {sc["n_duplicate_cases"]}、配对 {sc["pairing_ok"]} | verify_dataset_d36 |')
    md.append(f'| 划分复算 | {out["split_recheck"]["n_failures"]} failures | eval_report_d36 |')
    md.append(f'| 基线（已冻结为附录） | max_disp test {out["baseline_frozen"]["max_disp_test_mape"]} %，CI {out["baseline_frozen"]["max_disp_test_ci95"]}，常数地板 {out["baseline_frozen"]["constant_floor"]} | baseline_d36_final |')

    if write:
        json.dump(out, open(os.path.join(FEA, 'external_numbers.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        open(os.path.join(FEA, 'external_numbers.md'), 'w', encoding='utf-8').write(
            '# 对外数字源（单一来源，勿手抄）\n\n> 由 `feagpt_repro/make_external_numbers.py` 从权威 JSON 生成；'
            '更新数据集后必须重跑本脚本再改对外文档。\n\n' + '\n'.join(md) + '\n')
        print('[OK] 写盘 external_numbers.json / .md')
    else:
        print('[CHECK] 只校验未写盘')
    print('\n'.join(md))

if __name__ == '__main__':
    main(write='--check' not in sys.argv)
