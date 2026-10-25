# -*- coding: utf-8 -*-
"""
negative_controls.py — 评测器负控套件（专家第二轮附录 C，W4a P0-②）

红线条 R5/R6：每次改 evaluate.py / spec_fidelity / task 生成器，必须重跑本套件；
负控未全绿，评测器不得用于 LLM 基线。

PC-1  gold spec                          -> PASS
NC-1  rib_thickness 4->8                 -> FAIL（专家实测：旧版保真仅 0.46% 会 PASS）
NC-2  L2 问对问题但填错值 8.0            -> FAIL
NC-3  n_stringers_per_skin 0->3          -> FAIL
NC-4  mesh.size_chord 12->20             -> FAIL
NC-5  load.magnitude 500->600            -> FAIL
NC-6  material.youngs_modulus 73100->60000 -> FAIL
NC-7  L2 静默默认（不提问）              -> FAIL
NC-8  L3 集成自检（nl 行存在 + 走三闸路径）-> INFO（L3 语义由 schema+闸兜底）

输出：eval_runs/negative_controls.json；全部秒级（spec_fidelity 快通道，不起求解器）。
"""
import json, os, sys, copy, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluate import evaluate_one, evaluate_clarification, load_tasks, FEA, RUNS

BASE_TASK = 'L1_naca4412_wingbox'
L2_TASK = 'L2_naca4412_wingbox'


def gold_spec():
    s = json.load(open(os.path.join(FEA, 'modeling', 'naca4412_wingbox', 'spec.json'),
                       encoding='utf-8'))
    s.pop('workdir', None)
    return s


def mutated(fn):
    s = gold_spec()
    fn(s)
    return s


def w_airfoil(s, k, v):
    s['airfoil'][k] = v


def write_cand(name, spec):
    p = os.path.join(HERE, 'tasks', f'_nc_{name}.json')
    spec.setdefault('name', f'nc_{name}')
    json.dump(spec, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tasks', default=os.path.join(HERE, 'tasks', 'tasks.jsonl'))
    ap.add_argument('--full-pc1', action='store_true',
                    help='PC-1 额外跑完整 pipeline（ccx，~3 min）；默认快通道')
    args = ap.parse_args()

    tasks = {t['task_id']: t for t in load_tasks(args.tasks)}
    base = tasks[BASE_TASK]
    l2 = tasks.get(L2_TASK)
    results = []

    def run(nc_id, desc, task, cand, skip_solve=True):
        r = evaluate_one(task, cand, skip_solve=skip_solve)
        row = {'id': nc_id, 'desc': desc, 'expect': 'FAIL' if nc_id != 'PC-1' else 'PASS',
               'actual': 'PASS' if r['overall_pass'] else 'FAIL', 'ok':
               (r['overall_pass'] if nc_id == 'PC-1' else not r['overall_pass'])}
        if not row['ok']:
            sf = r['gates'].get('spec_fidelity', {})
            row['detail'] = sf.get('failed', [])[:3]
        results.append(row)
        print(f"  [{ 'ok ' if row['ok'] else 'BAD!' }] {nc_id:5s} {desc:44s} "
              f"expect={row['expect']} actual={row['actual']}")

    print('== 负控套件（spec_fidelity 快通道）==')
    # PC-1
    p = write_cand('pc1_gold', gold_spec())
    run('PC-1', 'gold spec', base, p, skip_solve=True)
    # NC-1..NC-6：字段注入
    cases = [
        ('NC-1', 'rib_thickness 4->8',        lambda s: w_airfoil(s, 'rib_thickness', 8.0)),
        ('NC-3', 'n_stringers_per_skin 0->3', lambda s: w_airfoil(s, 'n_stringers_per_skin', 3.0)),
        ('NC-4', 'mesh.size_chord 12->20',    lambda s: s['mesh'].__setitem__('size_chord', 20.0)),
        ('NC-5', 'load.magnitude 500->600',   lambda s: s['load'].__setitem__('magnitude', 600.0)),
        ('NC-6', 'E 73100->60000',            lambda s: s['material'].__setitem__('youngs_modulus', 60000.0)),
    ]
    for nc_id, desc, fn in cases:
        p = write_cand(nc_id.lower().replace('-', ''), mutated(fn))
        run(nc_id, desc, base, p)

    # NC-2：L2 问对问题但填错值（走 evaluate_clarification 完整链）
    if l2:
        clar = {'task_id': L2_TASK,
                'questions': [{'field': 'rib_thickness', 'question': '肋壁厚多少？'}],
                'final_spec': mutated(lambda s: w_airfoil(s, 'rib_thickness', 8.0))}
        cp = os.path.join(HERE, 'tasks', '_nc_nc2_l2.json')
        json.dump(clar, open(cp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        r = evaluate_clarification(l2, cp, timeout=600)
        ok = not r['overall_pass']
        results.append({'id': 'NC-2', 'desc': 'L2 问对填错 8.0', 'expect': 'FAIL',
                        'actual': 'PASS' if r['overall_pass'] else 'FAIL', 'ok': ok})
        print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-2  L2 问对填错 8.0                          "
              f"expect=FAIL actual={'PASS' if r['overall_pass'] else 'FAIL'}")

    # NC-7：L2 静默默认（不提问）
    if l2:
        clar = {'task_id': L2_TASK, 'questions': [],
                'final_spec': mutated(lambda s: w_airfoil(s, 'rib_thickness', 8.0))}
        cp = os.path.join(HERE, 'tasks', '_nc_nc7_l2.json')
        json.dump(clar, open(cp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        r = evaluate_clarification(l2, cp, timeout=600)
        ok = not r['overall_pass']
        results.append({'id': 'NC-7', 'desc': 'L2 静默默认', 'expect': 'FAIL',
                        'actual': 'PASS' if r['overall_pass'] else 'FAIL', 'ok': ok})
        print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-7  L2 静默默认                              "
              f"expect=FAIL actual={'PASS' if r['overall_pass'] else 'FAIL'}")

    # NC-8：L3 集成自检（nl 行在任务层、可被评测器索引）
    l3 = [t for t in tasks.values() if t['input_level'] == 'L3']
    ok = len(l3) == 30
    results.append({'id': 'NC-8', 'desc': 'L3 已接入任务层（30 条）', 'expect': '30 条',
                    'actual': str(len(l3)), 'ok': ok})
    print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-8  L3 已接入任务层                           "
          f"expect=30 actual={len(l3)}")

    # ---- W4c 扩展（专家第三轮附录 C）：NC-9..13 ----
    from evaluate import spec_fidelity
    barrel_task = tasks.get('L1_fuselage_barrel_d1600_l1600_str8_frm3') or next(
        t for t in tasks.values() if t['family'] == 'fuselage_barrel')
    barrel_cid = barrel_task['task_id'].replace('L1_', '')
    barrel_gold = json.load(open(os.path.join(FEA, 'modeling', barrel_cid, 'spec.json'),
                                 encoding='utf-8'))
    barrel_gold.pop('workdir', None)

    def sf_run(task, cand):
        cid = task['task_id'].replace('L1_', '')
        g = json.load(open(os.path.join(FEA, 'modeling', cid, 'spec.json'), encoding='utf-8'))
        g.pop('workdir', None)
        return spec_fidelity(cand, g, task['family'])

    # NC-9：删 bc
    c9 = json.loads(json.dumps(barrel_gold)); c9['bc'] = {}
    r9 = sf_run(barrel_task, c9)
    ok = not r9['pass']
    results.append({'id': 'NC-9', 'desc': '删 bc', 'expect': 'FAIL',
                    'actual': 'PASS' if r9['pass'] else 'FAIL', 'ok': ok})
    print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-9  删 bc                                    "
          f"expect=FAIL actual={'PASS' if r9['pass'] else 'FAIL'}")

    # NC-10：删 extra.end_shear（柱壳主载荷）
    c10 = json.loads(json.dumps(barrel_gold)); del c10['extra']['end_shear']
    r10 = sf_run(barrel_task, c10)
    ok = not r10['pass']
    results.append({'id': 'NC-10', 'desc': '删 extra.end_shear', 'expect': 'FAIL',
                    'actual': 'PASS' if r10['pass'] else 'FAIL', 'ok': ok})
    print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-10 删 extra.end_shear                      "
          f"expect=FAIL actual={'PASS' if r10['pass'] else 'FAIL'}")

    # NC-11：包装候选 => FEASpec.from_dict 必须 raise（R10 拒绝静默降级）
    from feagpt.spec import FEASpec
    packaged = {'task_id': 'x', 'spec': barrel_gold}
    try:
        FEASpec.from_dict(packaged)
        ok = False; why = '未拒绝（静默降级仍存在）'
    except ValueError:
        ok = True; why = 'raise ✅'
    results.append({'id': 'NC-11', 'desc': '包装候选拒绝契约', 'expect': 'raise', 'actual': why, 'ok': ok})
    print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-11 包装候选拒绝契约                         expect=raise {why}")

    # NC-12：structure.family 未知 => raise
    try:
        FEASpec.from_dict({'structure': {'family': 'unknown'}, 'name': 'x'})
        ok = False; why = '未拒绝'
    except ValueError:
        ok = True; why = 'raise ✅'
    results.append({'id': 'NC-12', 'desc': 'family=unknown 拒绝', 'expect': 'raise', 'actual': why, 'ok': ok})
    print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-12 family=unknown 拒绝                      expect=raise {why}")

    # NC-13：L3 候选删 mesh/load/bc/extra => spec_fidelity FAIL（L3 gold 权威判定）
    l3t = l3[0]
    l3_cid = l3t['task_id'].replace('L3_', '')
    l3_gold = json.load(open(os.path.join(FEA, 'modeling', l3_cid, 'spec.json'), encoding='utf-8'))
    l3_gold.pop('workdir', None)
    l3_bad = json.loads(json.dumps(l3_gold))
    for blk in ('mesh', 'load', 'bc', 'analysis', 'extra'):
        l3_bad.pop(blk, None)
    r13 = spec_fidelity(l3_bad, l3_gold, l3t['family'])
    ok = not r13['pass']
    results.append({'id': 'NC-13', 'desc': 'L3 删 mesh/load/bc/extra', 'expect': 'FAIL',
                    'actual': 'PASS' if r13['pass'] else 'FAIL', 'ok': ok})
    print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-13 L3 候选删 mesh/load/bc/extra             "
          f"expect=FAIL actual={'PASS' if r13['pass'] else 'FAIL'}")

    # NC-14：工程层口径四探针（W4d 拍板：配置层只报、死字段豁免、语义编造照罚、判层闸不松）
    l3t_eng = tasks.get('L3_naca4412_wingbox_size_skin4')
    if l3t_eng:
        cid_e = l3t_eng['task_id'].replace('L3_', '')
        g_e = json.load(open(os.path.join(FEA, 'modeling', cid_e, 'spec.json'), encoding='utf-8'))
        g_e.pop('workdir', None)

        def sf_eng(cand):
            return spec_fidelity(cand, g_e, l3t_eng['family'], engineering_layer=True)

        probes = []
        # a) 执行配置键错值 => 豁免（PASS）
        c = json.loads(json.dumps(g_e)); c['mesh']['recombine'] = False
        ra = sf_eng(c)
        probes.append(('配置键错值豁免', ra['pass'] and len(ra.get('exec_config_mismatch', [])) == 1,
                       f"pass={ra['pass']} mism={len(ra.get('exec_config_mismatch', []))}"))
        # b) 死字段错值（ns=0）=> 豁免（PASS）
        c = json.loads(json.dumps(g_e)); c['airfoil']['stringer_height'] = 999.0
        rb = sf_eng(c)
        probes.append(('死字段错值豁免', rb['pass'] and 'airfoil.stringer_height' in rb.get('dead_fields_skipped', []),
                       f"pass={rb['pass']} skipped={rb.get('dead_fields_skipped')}"))
        # c) web_chordwise 编值（无腹板任务）=> 照罚（FAIL）
        c = json.loads(json.dumps(g_e)); c['airfoil']['web_chordwise'] = [0.25, 0.7]
        rc = sf_eng(c)
        probes.append(('web_chordwise 编值照罚', not rc['pass'],
                       f"pass={rc['pass']}"))
        # d) 判层字段错（n_ribs 5->7）=> 闸不松（FAIL）
        c = json.loads(json.dumps(g_e)); c['airfoil']['n_ribs'] = 7
        rd = sf_eng(c)
        probes.append(('判层字段错闸不松', not rd['pass'],
                       f"pass={rd['pass']}"))
        ok = all(p[1] for p in probes)
        why = '; '.join(f"{n}={'OK' if good else 'BAD(' + d + ')'}" for n, good, d in probes)
        results.append({'id': 'NC-14', 'desc': '工程层口径四探针', 'expect': '4/4',
                        'actual': why, 'ok': ok})
        print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-14 工程层口径四探针                         "
              f"expect=4/4 actual={why}")

    # ---- W4e/W4f 扩展（专家第四轮附录 C）：NC-15..19 ----
    # NC-15：澄清判分字段级——问错族键名（含关键词'长桁'）必须 FAIL（R17）
    from score_baseline import judge_clarify_field_level
    panel_t = tasks.get('L3_stiffened_panel_600x600')
    if panel_t and panel_t.get('clarify_aliases'):
        ok15, det15 = judge_clarify_field_level(
            "长桁根数 n_stringers_per_skin 具体是多少？", panel_t)
        results.append({'id': 'NC-15', 'desc': '澄清问错族键 n_stringers_per_skin',
                        'expect': 'FAIL', 'actual': 'FAIL' if not ok15 else 'PASS',
                        'ok': not ok15, 'detail': {k: det15.get(k) for k in ('wrong_keys_hit', 'alias_hits')}})
        print(f"  [{ 'ok ' if (not ok15) else 'BAD!' }] NC-15 澄清问错族键（含'长桁'仍须FAIL）       "
              f"expect=FAIL actual={'FAIL' if not ok15 else 'PASS'}")
        # 反向：问对别名（无错键）必须 PASS
        ok15b, _ = judge_clarify_field_level("请问长桁根数是多少？", panel_t)
        results.append({'id': 'NC-15b', 'desc': '澄清问对别名（长桁根数）',
                        'expect': 'PASS', 'actual': 'PASS' if ok15b else 'FAIL',
                        'ok': ok15b})
        print(f"  [{ 'ok ' if ok15b else 'BAD!' }] NC-15b 澄清问对别名                            "
              f"expect=PASS actual={'PASS' if ok15b else 'FAIL'}")

    # NC-16：panel bc.support 自创键（bc_skip 曾漏判）⇒ spec_fidelity FAIL（R19/P0-4）
    panel_l1 = next((t for t in tasks.values() if t['family'] == 'stiffened_panel'), None)
    if panel_l1:
        cid16 = panel_l1['task_id'].replace('L1_', '').replace('L3_', '')
        g16 = json.load(open(os.path.join(FEA, 'modeling', cid16, 'spec.json'), encoding='utf-8'))
        g16.pop('workdir', None)
        c16 = json.loads(json.dumps(g16))
        c16['bc'] = {'root_surface': 'root', 'clamp': True, 'support': 'simply-supported'}
        r16 = spec_fidelity(c16, g16, panel_l1['family'], engineering_layer=True)
        ok = not r16['pass']
        results.append({'id': 'NC-16', 'desc': 'panel bc.support 自创键', 'expect': 'FAIL',
                        'actual': 'PASS' if r16['pass'] else 'FAIL', 'ok': ok})
        print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-16 panel bc.support 自创键                  "
              f"expect=FAIL actual={'PASS' if r16['pass'] else 'FAIL'}")

    # NC-17：open_hole load.distribution / material.ply_material 自创键 ⇒ FAIL（P0-4）
    oh_l1 = next((t for t in tasks.values() if t['family'] == 'open_hole_panel'), None)
    if oh_l1:
        cid17 = oh_l1['task_id'].replace('L1_', '').replace('L3_', '')
        g17 = json.load(open(os.path.join(FEA, 'modeling', cid17, 'spec.json'), encoding='utf-8'))
        g17.pop('workdir', None)
        c17 = json.loads(json.dumps(g17))
        c17['load']['distribution'] = 'uniform'
        r17 = spec_fidelity(c17, g17, oh_l1['family'], engineering_layer=True)
        c17b = json.loads(json.dumps(g17))
        c17b['material']['ply_material'] = 'T300/epoxy'
        r17b = spec_fidelity(c17b, g17, oh_l1['family'], engineering_layer=True)
        ok = (not r17['pass']) and (not r17b['pass'])
        results.append({'id': 'NC-17', 'desc': 'open_hole 自创键 load.distribution+material.ply_material',
                        'expect': 'FAIL/FAIL',
                        'actual': f"{'FAIL' if not r17['pass'] else 'PASS'}/{'FAIL' if not r17b['pass'] else 'PASS'}",
                        'ok': ok})
        print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-17 open_hole 自创键（load/material）         "
              f"expect=FAIL/FAIL actual={'FAIL' if not r17['pass'] else 'PASS'}/{'FAIL' if not r17b['pass'] else 'PASS'}")

    # NC-18：MSR 运行器依赖预检存在（R16）——源码级断言 + 有 gmsh 时 rc 非 1
    msr_src = open(os.path.join(HERE, 'msr_l3.py'), encoding='utf-8').read()
    has_guard = ("import gmsh" in msr_src or "'gmsh'" in msr_src) and 'return 2' in msr_src
    results.append({'id': 'NC-18', 'desc': 'MSR 依赖预检（gmsh 缺失 => 环境退出 rc=2）',
                    'expect': 'guard present', 'actual': 'present' if has_guard else 'missing',
                    'ok': has_guard})
    print(f"  [{ 'ok ' if has_guard else 'BAD!' }] NC-18 MSR 依赖预检存在                         "
          f"expect=guard actual={'present' if has_guard else 'missing'}")

    # NC-19：headline 检查——成绩单 exam 定义不得含 train/val（R15）
    sc_path = os.path.join(RUNS, 'baseline_scorecard_L3.json')
    if os.path.exists(sc_path):
        sc19 = json.load(open(sc_path, encoding='utf-8'))
        exam_rows = [r for r in sc19.get('per_task', []) if r.get('is_exam')]
        bad_splits = {r['split_v2'] for r in exam_rows} - {'boundary_holdout', 'extrapolation_test'}
        ok = not bad_splits
        results.append({'id': 'NC-19', 'desc': 'exam 集不含 train/val（R15）',
                        'expect': 'empty', 'actual': str(sorted(bad_splits)) or 'empty', 'ok': ok})
        print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-19 exam 集不含 train/val                    "
              f"expect=empty actual={sorted(bad_splits) or 'empty'}")
    else:
        results.append({'id': 'NC-19', 'desc': 'exam 集不含 train/val（成绩单未生成，跳过）',
                        'expect': 'skip', 'actual': 'no scorecard', 'ok': True})
        print('  [ ok ] NC-19 exam 集不含 train/val（成绩单未生成，跳过）')


    n_ok = sum(1 for r in results if r['ok'])
    report = {'n_cases': len(results), 'n_ok': n_ok, 'all_ok': n_ok == len(results),
              'results': results}
    os.makedirs(RUNS, exist_ok=True)
    json.dump(report, open(os.path.join(RUNS, 'negative_controls.json'), 'w',
                           encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\n负控: {n_ok}/{len(results)} ok -> eval_runs/negative_controls.json")
    print('红线条 R6：负控未全绿，不得跑 LLM 基线。')
    return 0 if report['all_ok'] else 2

if __name__ == '__main__':
    sys.exit(main())
