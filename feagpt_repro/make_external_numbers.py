# -*- coding: utf-8 -*-
"""
make_external_numbers.py — 对外材料「单一数字源」生成器（ROADMAP W1-3）

原则：所有对外口径数字只从磁盘权威产物读回，禁止手抄。

数据源（v1.1 起，见 T-A8）：
  manifest.json             算例规模 / 划分 / 族分布 / **关 1 网格**（readings 现算）
  gate3_all55_d37.json      关 3 双码分级
  gate4_v11.json            关 4 语义
  verify_dataset_v11.json   自洽
  eval_report_v11.json      划分复算
  baseline_d36_final.json   基线（**v1 数据集上冻结，见 baseline_frozen.dataset_version**）

★ 为什么关 1 改从 manifest 现算而不再读 gates_all55_d36.json：
  该快照的 gate1_mesh_quality 是 55 条时代的聚合（n_cases=55），而 gate1 的真相
  本来就是逐条 readings（min_jacobian / n_tri3）。这两个读数**每一条**都被
  eval_dataset.py 用 msh_quality 与 model.inp 独立复算过（readings.* 复算项，
  不是抽检）⇒ manifest.readings 是已复算的声明，直接现算聚合不会产生副本，
  而快照会产生副本（R62：闸的覆盖范围外不许复写它守的数字）。

输出：
  FEM-Bench-Aero/external_numbers.json  （机器可读，对外文档引用此文件）
  FEM-Bench-Aero/external_numbers.md    （人读版，供文档作者复制）

用法：
  python make_external_numbers.py            # 写盘
  python make_external_numbers.py --check    # 只校验不写盘
"""
import json, sys, os, re

HERE = os.path.dirname(os.path.abspath(__file__))            # feagpt_repro
ROOT = os.path.dirname(HERE)                                  # 仓库根
FEA = os.path.join(ROOT, 'FEM-Bench-Aero')

def load(name):
    with open(os.path.join(FEA, name), encoding='utf-8') as f:
        return json.load(f)

def load_probe(rel):
    """读 feagpt_repro 下的探针产物（M14 线的留一/收敛）。"""
    with open(os.path.join(HERE, rel), encoding='utf-8') as f:
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
    g4 = load('gate4_v11.json')
    vf = load('verify_dataset_v11.json')
    ev = load('eval_report_v11.json')
    bl = load('baseline_d36_final.json')
    g3all = load('gate3_all55_d37.json')   # W4a 纠偏 P1-2：单一数字源读最新关 3 分级报告
    # gates_all55_d36.json 不再读取：gate3 段已由 d37 取代，gate1 段改为从 manifest 现算
    # （T-A8：那份快照的 gate1 是 55 条聚合，v1.1 后与 manifest 的 64 条并存即自相矛盾）

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
        'generated_from': ('manifest.json + gate3_all55_d37 + gate4_v11 + '
                           'verify_dataset_v11 + eval_report_v11 + baseline_d36_final'),
        'dataset_version': 'v1.1（64 条；train 25 / val 17 / test 22）',
        'naming_note': 'FEM-Bench-Aero（本仓库内部命名，A 建模集；与 GitHub 公开仓库 FEM-Bench 无关联，公开发布前将评估更名）',
        'scale': {
            'cases_total': n_cases,
            'solver_trees': len(vf['trees']),
            'case_dirs': dig(vf, ['summary', 'n_cases'], 'verify'),
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
            'dataset_version': (
                '★ 该基线冻结于 v1（55 条，翼盒族 test 6 条）的 baseline_d36_final.json，'
                'v1.1（64 条，翼盒族 test 11 条）**未重跑**。按 R30/R39 不得与 v1.1 的成绩并列'
                '相减或声称提升——它只证明"这条路线在 v1 上可学"，不是当前数据集的分数'),
            'max_disp_test_mape': dig(bl, ['targets', 'max_disp', 'M3q ridge+sweep^2', 'test_mape'], 'baseline'),
            'max_disp_test_ci95': dig(bl, ['targets', 'max_disp', 'M3q ridge+sweep^2', 'test_ci95'], 'baseline'),
            'constant_floor': dig(bl, ['targets', 'max_disp', 'M0m constant(MAPE-opt)', 'test_mape'], 'baseline'),
            'known_limits': [
                'vM 峰值网格未收敛（12→6 mm 仍 +12.9 %），应力真值带 ≥13 % 偏不安全低估',
                '双码证据分级见 gates.gate3_all55（field / scalar-disp / reported-only 三档），'
                '不宣称全体逐条场级；此处不复写计数',
                'test 13 条全部为外推/新形式（无 ID 内插点；ID test = W3 任务）',
                'recombination_algorithm3 为同几何网格鲁棒性对照样本，不参与样本量统计',
            ],
        },
        'excluded_from_external_docs': ['B 解读集 / C 更新集（近期不做，2026-10-24 拍板移出对外承诺）'],
    }

    # 关 1：从 manifest.readings 现算（T-A8）。这两个读数每条都被 eval_dataset 复算过，
    # 见 docstring；不读 gates_all55_d36.json，避免 55 条聚合与 64 条规模并存。
    THRESH_MINJ = 0.30
    mj = [(c['case_id'], c['readings']['min_jacobian'], c['readings']['n_tri3'])
          for c in man['cases'] if c.get('readings')]
    missing = [c['case_id'] for c in man['cases'] if not c.get('readings')]
    if missing:
        sys.exit(f'[FATAL] 关 1：{len(missing)} 条缺 readings（例：{missing[:3]}）；'
                 f'不得用缺失值算"全过"')
    worst = min(mj, key=lambda x: x[1])
    below = [m for m in mj if m[1] < THRESH_MINJ]
    tri3_cases = [m for m in mj if m[2] != 0]
    out['gates']['gate1_mesh'] = {
        'n_cases': len(mj),
        'n_measured': len(mj),
        'threshold_min_jacobian': THRESH_MINJ,
        'n_below_threshold': len(below),
        'worst_min_jacobian': worst[1],
        'worst_case': worst[0],
        'n_tri3_cases': len(tri3_cases),
        'n_tri3_total': sum(m[2] for m in mj),
        'pass': not below and not tri3_cases,
        # 代表性论证：xval 树 msh 与 modeling 树逐字节相同（verify 已验），故只看 modeling 树即覆盖两树
        'scope_note': ('分母 = 64 条 spec（modeling 树）。两树 msh 逐字节相同'
                       '（verify_dataset cross_tree_mesh），故不按 128 个目录重复计数'),
        'source': 'manifest.json::cases[].readings（min_jacobian / n_tri3，'
                  '已由 eval_dataset.py 逐条复算）',
    }
    # 关 3（W4a：分级口径，来源 gate3_all55_d37）
    out['gates']['gate3_all55'] = {
        'evidence_levels': g3all.get('evidence_levels'),
        'n_gated_pass': g3all.get('n_gated_pass'),
        'n_reported_only': g3all.get('n_reported_only'),
        'n_fail': g3all.get('n_fail'),
        'claim': f"{g3all['evidence_levels']['field']} field + "
                 f"{g3all['evidence_levels']['scalar_disp']} scalar-disp + "
                 f"{g3all['n_reported_only']} reported-only"
                 f"（不说 {g3all['n_cases']}/{g3all['n_cases']}）",
        'source': 'gate3_all55_d37.json',
    }
    # 自洽 / 划分复算（summary 实读）
    out['selfcheck'] = {
        'n_cases': dig(vf, ['summary', 'n_cases'], 'verify'),
        'n_ok': dig(vf, ['summary', 'n_ok'], 'verify'),
        'n_paired': dig(vf, ['pairing', 'paired'], 'verify'),
        'n_duplicate_cases': dig(vf, ['summary', 'n_duplicate_cases'], 'verify'),
        'pairing_ok': dig(vf, ['summary', 'pairing_ok'], 'verify'),
        'all_ok': dig(vf, ['summary', 'all_ok'], 'verify'),
        # R54：n_cases 是「算例目录」口径（= 2 × spec 数），与关 1/关 3 的 spec 口径不同分母
        'scope_note': '分母 = 算例目录数（2 棵求解器树 × spec 数），不是 spec 数',
        'source': 'verify_dataset_v11.json',
    }
    out['split_recheck'] = {
        'n_cases': dig(ev, ['summary', 'n_cases'], 'eval'),
        'n_geometry_classes': dig(ev, ['summary', 'n_geometry_classes'], 'eval'),
        'n_failures': len(ev.get('failures', [])),
        'scope_note': '分母 = spec 数',
        'source': 'eval_report_v11.json',
    }
    # 每个对外数字的出处（单一数字源自证；R-A3 artifact 可追溯）
    out['source_artifacts'] = {
        'scale': 'manifest.json',
        'gate1_mesh': 'manifest.json::cases[].readings（复算见 eval_report_v11）',
        'gate3_all55': 'gate3_all55_d37.json',
        'gate4_semantics': 'gate4_v11.json',
        'selfcheck': 'verify_dataset_v11.json',
        'split_recheck': 'eval_report_v11.json',
        'baseline_frozen': 'baseline_d36_final.json（v1 数据集冻结）',
    }

    md = ['| 项 | 数值 | 分母口径 | 来源 |', '|---|---|---|---|']
    md.append(f'| 算例规模 | {n_cases} 条 × {out["scale"]["solver_trees"]} 棵求解器树'
              f' = {out["scale"]["case_dirs"]} 个算例目录 | {n_cases} 条 spec | manifest.summary |')
    md.append(f'| 几何等价类 | {n_classes}（重复 {n_dup}、跨 split 泄漏 {n_leak}） | {n_cases} 条 spec | manifest.summary |')
    md.append(f'| 划分 | train {splits.get("train")} / val {splits.get("val")} / test {splits.get("test")} | {n_cases} 条 spec | manifest.cases 实算 |')
    for fam, cnt in sorted(fams.items()):
        md.append(f'| — {fam} | {cnt.get("train",0)}-{cnt.get("val",0)}-{cnt.get("test",0)}'
                  f'（共 {sum(cnt.values())}） | {sum(cnt.values())} 条 spec | manifest.cases 实算 |')
    g1m = out['gates']['gate1_mesh']
    md.append(f'| 关 1 网格 | **{g1m["n_measured"]}/{g1m["n_cases"]}**'
              f'（最差 minJ {g1m["worst_min_jacobian"]} @ `{g1m["worst_case"]}`、'
              f'tri3 {g1m["n_tri3_total"]}、阈值 minJ ≥ {g1m["threshold_min_jacobian"]}） '
              f'| {g1m["n_cases"]} 条 spec（两树 msh 逐字节相同，不重复计） '
              f'| manifest.readings（eval_dataset 逐条复算） |')
    # 关 3（W4a 纠偏 P0-2：分级表述，禁止 55/55）
    md.append(f'| 关 3 双码 | **{g3all["evidence_levels"]["field"]} field-level + '
              f'{g3all["evidence_levels"]["scalar_disp"]} scalar-disp-gated + '
              f'{g3all["n_reported_only"]} reported-only**'
              f'（不说 {g3all["n_cases"]}/{g3all["n_cases"]}） '
              f'| {g3all["n_cases"]} 条 spec | gate3_all55_d37 |')
    md.append(f'| 关 4 语义 | {out["gates"]["gate4_semantics"]}/{dig(g4, ["n_cases"], "gate4")} '
              f'| {dig(g4, ["n_cases"], "gate4")} 个算例目录（两树各一份） | gate4_v11 |')
    sc = out['selfcheck']
    md.append(f'| 自洽 | {sc["n_ok"]}/{sc["n_cases"]}、重复 {sc["n_duplicate_cases"]}、'
              f'配对 {sc["n_paired"]}/{n_cases} | {sc["n_cases"]} 个算例目录'
              f'（配对按 {n_cases} 条 spec 计） | verify_dataset_v11 |')
    md.append(f'| 划分复算 | {out["split_recheck"]["n_failures"]} failures '
              f'| {out["split_recheck"]["n_cases"]} 条 spec | eval_report_v11 |')
    md.append(f'| 基线（已冻结为附录） | max_disp test {out["baseline_frozen"]["max_disp_test_mape"]} %，'
              f'CI {out["baseline_frozen"]["max_disp_test_ci95"]}，'
              f'常数地板 {out["baseline_frozen"]["constant_floor"]} '
              f'| **v1（55 条，翼盒 test 6 条）—— 不可与 v1.1 并列** | baseline_d36_final |')
    # ── M14 硬限制（W4a 纠偏 P1-2：对外必读 caveat）────────────────────────────
    # ★ T-A8 溢出发现：这三条原先是硬编码字面量，其中「全体 34 条留一」与 manifest
    #   已 64 条（翼盒 39 条）并存 ⇒ 同一张对外表自相矛盾（表头 64、脚下 34）。
    #   处理：能读 artifact 的现读（不留手抄副本），读不到的如实标证据缺口；
    #   三条一律标注所属数据集版本（v1 口径，v1.1 未重跑）。
    loo = load_probe('_probe_m14/all_loo.json')
    hcv = load_probe('_probe_m14/h_convergence.json')
    loo_d = loo['folds']['max_disp']
    m14_ver = ('v1（55 条时代；翼盒 34 条）。**v1.1（翼盒 39 条）未重跑**，'
               '不可当作 v1.1 成绩，也不可与本表上方任何一格并列相减')
    out['m14_limits'] = {
        'dataset_version': m14_ver,
        'vm_peak_not_converged': {
            'statement': '12→6 mm 仍 +12.9 %，应力真值带 ≥13 % 偏不安全低估',
            'artifact': None,
            'evidence_gap': ('无机器可读 artifact —— h_convergence.json 只记录 max_disp 的收敛；'
                             '该结论目前只在 STAGE_GATE_M14.md 正文，须补 artifact 后才可升为 GATED'),
        },
        'displacement_converged': {
            'statement': '位移良定义（12→6 mm 变化 −0.48 %）',
            'baseline_12mm_error_pct': hcv['richardson_limit']['baseline_12mm_error_pct'],
            'finest_error_pct': hcv['richardson_limit']['finest_error_pct'],
            'artifact': 'feagpt_repro/_probe_m14/h_convergence.json',
        },
        'promise_5_to_9_pct': {
            'statement': '2.63 % 是「组合插值」成绩，不是「新设计」成绩；对外承诺写 5–9 %，不写 3 %',
            'artifact': 'STAGE_GATE_M14.md §4.4',
        },
        'loo_mape': {
            'n_cases': loo['n_cases'],
            'mape': loo_d['mape'], 'median': loo_d['median'],
            'p90': loo_d['p90'], 'max': loo_d['max'],
            'artifact': 'feagpt_repro/_probe_m14/all_loo.json',
        },
    }
    m14 = out['m14_limits']
    md += [
        '',
        '## M14 硬限制（对外承诺必读，W4a 纠偏 P1-2）',
        '',
        f'> **版本**：以下三条全部属于 {m14_ver}。',
        '',
        f'1. **vM 峰值未收敛**：{m14["vm_peak_not_converged"]["statement"]}'
        f' —— ⚠ **证据缺口**：{m14["vm_peak_not_converged"]["evidence_gap"]}',
        f'2. **{m14["displacement_converged"]["statement"]}**（`h_convergence.json`）；'
        f'{m14["promise_5_to_9_pct"]["statement"]} —— STAGE_GATE_M14 §4.4',
        f'3. **全体 {m14["loo_mape"]["n_cases"]} 条留一 '
        f'{m14["loo_mape"]["mape"]:.2f} %**（中位 {m14["loo_mape"]["median"]:.2f} / '
        f'p90 {m14["loo_mape"]["p90"]:.2f} / 最大 {m14["loo_mape"]["max"]:.2f}）'
        f' —— `_probe_m14/all_loo.json`（现读，n_cases={m14["loo_mape"]["n_cases"]}）；'
        f'报数必须带 p90+max',
        '',
        '## 分母口径警告（R54，T-A8）',
        '',
        '- 关 1 / 关 3 / 划分复算的分母是 **spec 数**；关 4 / 自洽的分母是 **算例目录数**（= spec 数 × 2 树）。',
        '- **两套分母不得相减、不得互算百分比差**。本表已单列「分母口径」列，引用时须连同该列一起引。',
        '- 基线段的分母是 **v1 数据集的 v1 划分**，与 v1.1 任何一格都不可比（R30/R39）。',
        '- M14 三条限制的分母是 **v1 翼盒 34 条**，同样与 v1.1 不可比。',
    ]

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
