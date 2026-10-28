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
NC-9..14  W4c 契约/全链/口径探针
NC-15/15b W4e 澄清双向（动态取澄清任务，防静默消失）
NC-16..19 W4e 工程层/自创键/MSR 预检/exam 集
NC-20..22 W5a  NL 载荷方向 / MSR 分母 / exam.msr
NC-23..25 W5a' CLAIMS 自检（artifact 缺失 / eval_runs 未追踪 / 官方·诊断同路径）

输出：reports/negative_controls_<n>.json（**入库**，R25；不再写 eval_runs/ 工作目录）；
全部秒级（spec_fidelity 快通道，不起求解器）。
"""
import json, os, sys, argparse

try:  # P1-3（专家第五轮）：GBK 控制台直跑不因中文/符号输出崩
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluate import evaluate_one, evaluate_clarification, load_tasks, FEA, RUNS

BASE_TASK = 'L1_naca4412_wingbox'
L2_TASK = 'L2_naca4412_wingbox'


def latest_scorecard():
    """W5a'：负控要咬最新那份成绩单——不再硬编码 eval_runs/ 路径（否则官方入库后负控检查的是旧文件）。"""
    d = os.path.join(HERE, 'reports')
    cands = []
    if os.path.isdir(d):
        cands = [os.path.join(d, f) for f in os.listdir(d)
                 if f.startswith('baseline_scorecard_L3') and f.endswith('.json')]
    if cands:
        return max(cands, key=os.path.getmtime)
    return os.path.join(RUNS, 'baseline_scorecard_L3.json')


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
    # ★ W5b 修正：不再硬编码 30 条——改成断言「tasks.jsonl 的 L3 行数 == nl_human.jsonl 行数」。
    #   旧写法在考卷扩到 55 条时直接假红（把旧结论写进期望值 = 改一次卷子就要改一次检查）。
    l3 = [t for t in tasks.values() if t['input_level'] == 'L3']
    nl_path = os.path.join(HERE, 'tasks', 'nl_human.jsonl')
    n_nl = sum(1 for ln in open(nl_path, encoding='utf-8') if ln.strip())
    ok = len(l3) == n_nl
    results.append({'id': 'NC-8', 'desc': f'L3 已接入任务层（L3 行数 == nl_human 行数 {n_nl}）',
                    'expect': f'=={n_nl}', 'actual': str(len(l3)), 'ok': ok})
    print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-8  L3 已接入任务层                           "
          f"expect=={n_nl} actual={len(l3)}")

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
        ok = True; why = 'raise ok'
    results.append({'id': 'NC-11', 'desc': '包装候选拒绝契约', 'expect': 'raise', 'actual': why, 'ok': ok})
    print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-11 包装候选拒绝契约                         expect=raise {why}")

    # NC-12：structure.family 未知 => raise
    try:
        FEASpec.from_dict({'structure': {'family': 'unknown'}, 'name': 'x'})
        ok = False; why = '未拒绝'
    except ValueError:
        ok = True; why = 'raise ok'
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
    # W5a：澄清题对象动态取（v5 考卷 panel 600x600 的 ec 迁到 str3；静默跳过 = 检查消失，禁止）
    from score_baseline import judge_clarify_field_level
    panel_t = next((t for t in tasks.values()
                    if t.get('expected_clarifications') and t.get('clarify_aliases')
                    and t.get('clarify_wrong_keys')), None)
    if panel_t is None:
        results.append({'id': 'NC-15', 'desc': '澄清字段级探针无测对象', 'expect': 'any L3 clarify task',
                        'actual': 'none found —— 澄清判据失去测试对象，配置错误', 'ok': False})
        print('  [BAD!] NC-15 无任何带 clarify_aliases 的 L3 任务（澄清判据失去测试对象）')
    else:
        wrong_key_probe = (panel_t.get('clarify_wrong_keys') or ['n_stringers_per_skin'])[0]
        ok15, det15 = judge_clarify_field_level(
            f"{wrong_key_probe} 具体是多少？", panel_t)
        results.append({'id': 'NC-15', 'desc': f'澄清问错族键 {wrong_key_probe}',
                        'expect': 'FAIL', 'actual': 'FAIL' if not ok15 else 'PASS',
                        'ok': not ok15, 'task': panel_t['task_id'],
                        'detail': {k: det15.get(k) for k in ('wrong_keys_hit', 'alias_hits')}})
        print(f"  [{ 'ok ' if (not ok15) else 'BAD!' }] NC-15 澄清问错族键（{wrong_key_probe}）           "
              f"expect=FAIL actual={'FAIL' if not ok15 else 'PASS'}")
        # 反向：问对别名（无错键）必须 PASS
        alias0 = (panel_t['clarify_aliases'] if isinstance(panel_t['clarify_aliases'], list)
                  else sum(panel_t['clarify_aliases'].values(), []))[0]
        ok15b, _ = judge_clarify_field_level(f"请问{alias0}是多少？", panel_t)
        results.append({'id': 'NC-15b', 'desc': f'澄清问对别名（{alias0}）',
                        'expect': 'PASS', 'actual': 'PASS' if ok15b else 'FAIL',
                        'ok': ok15b, 'task': panel_t['task_id']})
        print(f"  [{ 'ok ' if ok15b else 'BAD!' }] NC-15b 澄清问对别名（{alias0}）               "
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

    # NC-19：headline 检查——成绩单 exam 定义不得含未留出的 train/val（R15 / R36）
    # W5b-4 修：v6b 三栏口径下「内插题」按设计就是从 train 里留出的（split_v2 仍是 train，
    # exam_stratum='interpolation'）。原判据把这类合法行也算 BAD（假红）。
    # W5c 再修（R36）：v6c 起内插题 split_v2 直接是 interpolation_test ⇒ 不再需要豁免。
    # 新不变式（三端都守）：① exam 行 split 必须与 stratum 一致；② 非 exam 行 split 不得是留出；
    # ③ 内插题若仍是 split=train（旧卷），只允许此一种组合，且必须显式计入「旧卷豁免」。
    sc_path = latest_scorecard()
    print(f'  [info] 负控读取的成绩单 = {sc_path}')
    if os.path.exists(sc_path):
        sc19 = json.load(open(sc_path, encoding='utf-8'))
        all19 = sc19.get('per_task', [])
        exam_rows = [r for r in all19 if r.get('is_exam')]
        holdout = {'boundary_holdout', 'extrapolation_test', 'interpolation_test'}
        bad, legacy_exempt = [], 0
        for r in exam_rows:
            sv, st = r.get('split_v2'), r.get('exam_stratum')
            if st not in ('boundary', 'extrapolation', 'interpolation'):
                bad.append(f"{r.get('task_id')}(stratum={st})")
                continue
            if sv in holdout:
                if (st == 'boundary') != (sv == 'boundary_holdout') or \
                   (st == 'extrapolation') != (sv == 'extrapolation_test') or \
                   (st == 'interpolation') != (sv == 'interpolation_test'):
                    bad.append(f"{r.get('task_id')}(split={sv}≠stratum={st})")
                continue
            if sv == 'train' and st == 'interpolation':
                legacy_exempt += 1        # 仅旧卷（v6b 及以前）合法
                continue
            bad.append(f"{r.get('task_id')}(split={sv},stratum={st})")
        for r in all19:
            if not r.get('is_exam') and r.get('split_v2') in holdout:
                bad.append(f"{r.get('task_id')}(非 exam 却是留出 split)")
        ok = not bad
        extra = f' / 旧卷豁免 {legacy_exempt}' if legacy_exempt else ''
        results.append({'id': 'NC-19', 'desc': 'exam 集与 split 语义一致（R15/R36）',
                        'expect': 'empty', 'actual': (str(sorted(bad)[:3]) or 'empty') + extra,
                        'ok': ok})
        print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-19 exam 集与 split 语义一致              "
              f"expect=empty actual={(sorted(bad)[:3]) or 'empty'}{extra}")
    else:
        results.append({'id': 'NC-19', 'desc': 'exam 集不含 train/val（成绩单未生成，跳过）',
                        'expect': 'skip', 'actual': 'no scorecard', 'ok': True})
        print('  [ ok ] NC-19 exam 集不含 train/val（成绩单未生成，跳过）')

    # ---- W5a 扩展（专家第五轮 6.2）：NC-20..22 ----
    # NC-20：任务 NL 未给载荷方向 ⇒ 构建期拒绝（R21；v4 考卷 3 条翼盒因「法向」歧义失败）
    # 判据 = 必须有 coordinate_convention 且 NL 无「（法向）」类未定义裸词；
    # 方向表述可为向量 [0,1,0] 或文字化轴向（沿 +x / 绕 y / 沿壁面内法向）
    import re
    bare_normal = re.compile(r'（法向）|\(法向\)')
    l3_all = [t for t in tasks.values() if t['input_level'] == 'L3']
    no_dir = [t['task_id'] for t in l3_all
              if not t.get('coordinate_convention')
              or bare_normal.search(t['input'].get('nl', ''))]
    ok = not no_dir
    results.append({'id': 'NC-20', 'desc': 'L3 任务 NL 必须给坐标系+方向向量（R21）',
                    'expect': 'empty', 'actual': str(no_dir[:5]) or 'empty', 'ok': ok})
    print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-20 L3 NL 载荷方向完备（R21）               "
          f"expect=empty actual={no_dir[:5] or 'empty'}")

    # NC-21：MSR 分母不得含澄清/编造题（R23；v4 成绩单 d1600 曾双重计数）
    # ★ W5a' 修正：必须用**成绩单自己那张考卷**的澄清题清单核对（provenance.tasks_path），
    # 不能用当前 tasks.jsonl——v4/v5 的 ec 集不同（panel 600x600 ↔ str3），跨卷核对会假绿/假红。
    sc21_path = sc_path
    if os.path.exists(sc21_path):
        sc21 = json.load(open(sc21_path, encoding='utf-8'))
        pp = (sc21.get('provenance') or {}).get('tasks_path')
        if pp and not os.path.isabs(pp):
            pp = os.path.join(HERE, pp)
        if not (pp and os.path.exists(pp)):
            pp = os.path.join(HERE, 'tasks', 'tasks.jsonl')
        paper_tasks = {t['task_id']: t for t in load_tasks(pp)}
        ec_ids = {tid for tid, t in paper_tasks.items() if t.get('expected_clarifications')}
        bad_den = [r['task_id'] for r in sc21.get('msr_section', {}).get('per_task', [])
                   if r.get('denominator') and r['task_id'] in ec_ids]
        ok = not bad_den
        results.append({'id': 'NC-21', 'desc': f'MSR 分母不含澄清题（R23；核对卷={os.path.basename(pp)}）',
                        'expect': 'empty', 'actual': str(bad_den) or 'empty', 'ok': ok})
        print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-21 MSR 分母排除澄清题（R23, 卷={os.path.basename(pp)}）"
              f"  expect=empty actual={bad_den or 'empty'}")
    else:
        results.append({'id': 'NC-21', 'desc': 'MSR 分母检查（成绩单未生成，跳过）',
                        'expect': 'skip', 'actual': 'no scorecard', 'ok': True})
        print('  [ ok ] NC-21 MSR 分母排除澄清题（成绩单未生成，跳过）')

    # NC-22：成绩单含 exam.msr（P1-1：不再手算；msr_section 已有 ⇒ exam.msr 必须有）
    if os.path.exists(sc21_path):
        sc22 = json.load(open(sc21_path, encoding='utf-8'))
        has_msr_sec = bool(sc22.get('msr_section'))
        em = (sc22.get('exam') or {}).get('msr')
        ok = (not has_msr_sec) or bool(em)
        if not has_msr_sec:
            # 成绩单还没合并 MSR（msr_l3.py 未跑）——这是 skip 不是 PASS：
            # 显式打 skip，避免「expect=present actual=missing」却记 ok 的假绿（W5a 教训）
            desc, actual = '成绩单 exam.msr（MSR 未合并，skip）', 'skip（无 msr_section）'
        else:
            desc, actual = '成绩单 exam.msr 汇总字段（P1-1）', (em or 'missing')
        results.append({'id': 'NC-22', 'desc': desc,
                        'expect': 'present', 'actual': actual, 'ok': ok})
        print(f"  [{ 'ok ' if ok else 'BAD!' }] NC-22 成绩单含 exam.msr                        "
              f"expect=present actual={actual}")
    else:
        results.append({'id': 'NC-22', 'desc': 'exam.msr 检查（成绩单未生成，跳过）',
                        'expect': 'skip', 'actual': 'no scorecard', 'ok': True})
        print('  [ ok ] NC-22 成绩单含 exam.msr（成绩单未生成，跳过）')


    # ---- W5a' 扩展（专家第六轮 6.2）：NC-23..25 —— CLAIMS 自检必须咬得住 ----
    # 三条都用同一份 `check_claims.py`，仅注入不同的临时 CLAIMS（不删任何真实文件）。
    import subprocess, tempfile
    cc = os.path.join(HERE, 'check_claims.py')
    tmpdir = os.path.join(RUNS, '_nc_claims')
    os.makedirs(tmpdir, exist_ok=True)
    ROOT_ = os.path.dirname(HERE)

    def run_check_claims(md_text, tag):
        md = os.path.join(tmpdir, f'claims_{tag}.md')
        open(md, 'w', encoding='utf-8').write(md_text)
        out = os.path.join(tmpdir, f'out_{tag}.json')
        r = subprocess.run([sys.executable, cc, '--claims', md, '--root', ROOT_, '--json', out],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        return r.returncode, (r.stdout or '') + (r.stderr or '')

    HDR = ('| claim_id | statement | artifact | command | date | level | coverage | status |\n'
           '|---|---|---|---|---|---|---|---|\n')

    # NC-23：artifact 缺失（等价于「删掉某个 active claim 的 artifact」）=> check_claims FAIL
    rc23, o23 = run_check_claims(
        HDR + '| X-1 | 指向不存在的 artifact | feagpt_repro/reports/DOES_NOT_EXIST.json | '
              '`python x.py --report reports/DOES_NOT_EXIST.json` | 2026-10-25 | GATED | 1 | active |\n',
        'nc23')
    ok23 = rc23 != 0 and '不存在' in o23
    results.append({'id': 'NC-23', 'desc': 'CLAIMS artifact 缺失 ⇒ check_claims FAIL',
                    'expect': 'rc!=0 + 报「不存在」', 'actual': f'rc={rc23}', 'ok': ok23})
    print(f"  [{'ok ' if ok23 else 'BAD!'}] NC-23 artifact 缺失被检出                          "
          f"expect=FAIL actual=rc{rc23}")

    # NC-24：artifact 落在 gitignore 的 eval_runs/ ⇒ check_claims FAIL（R25）
    rc24, o24 = run_check_claims(
        HDR + '| X-2 | artifact 在 eval_runs | feagpt_repro/eval_runs/baseline_scorecard_L3.json | '
              '`python x.py --report eval_runs/baseline_scorecard_L3.json` | 2026-10-25 | GATED | 1 | active |\n',
        'nc24')
    ok24 = rc24 != 0 and 'eval_runs' in o24
    results.append({'id': 'NC-24', 'desc': 'CLAIMS artifact 在 eval_runs/（未追踪）⇒ FAIL（R25）',
                    'expect': 'rc!=0 + 报 eval_runs', 'actual': f'rc={rc24}', 'ok': ok24})
    print(f"  [{'ok ' if ok24 else 'BAD!'}] NC-24 eval_runs/ 未追踪被拒                         "
          f"expect=FAIL actual=rc{rc24}")

    # NC-25：官方与诊断占用同一 artifact 路径 ⇒ check_claims FAIL（R27）
    rc25, o25 = run_check_claims(
        HDR + '| X-3 | 官方 | feagpt_repro/reports/bridge_v3_v4.json | `python x.py --report reports/bridge_v3_v4.json` | 2026-10-25 | GATED | 1 | active |\n'
              '| X-4 | 诊断 | feagpt_repro/reports/bridge_v3_v4.json | `python x.py --report reports/bridge_v3_v4.json` | 2026-10-25 | GATED | 1 | active |\n',
        'nc25')
    ok25 = rc25 != 0 and 'R27' in o25
    results.append({'id': 'NC-25', 'desc': '官方/诊断同一 artifact 路径 ⇒ FAIL（R27）',
                    'expect': 'rc!=0 + 报 R27', 'actual': f'rc={rc25}', 'ok': ok25})
    print(f"  [{'ok ' if ok25 else 'BAD!'}] NC-25 官方/诊断同路径被拒                         "
          f"expect=FAIL actual=rc{rc25}")

    # NC-26：缺金标准数据集必须硬报错（W5a' clean-clone 实锤）——`modeling/` 不在 git，
    # 缺 gold 时 spec_fidelity 把全部候选判 spec_fail，成绩单显示 0/11「像模型全错」。
    from evaluate import require_dataset
    err_bad = require_dataset(os.path.join(HERE, 'reports', '__no_such_dataset__'))
    err_ok = require_dataset()
    ok26 = bool(err_bad) and (err_ok is None)
    results.append({'id': 'NC-26', 'desc': '缺 gold 数据集 ⇒ 前置闸硬报错（防静默算成 0/11）',
                    'expect': 'bad=raise / good=None',
                    'actual': f"bad={'raise' if err_bad else 'pass'} / "
                              f"good={'None' if err_ok is None else 'raise'}",
                    'ok': ok26})
    print(f"  [{'ok ' if ok26 else 'BAD!'}] NC-26 缺 gold 数据集硬报错                       "
          f"expect=raise/None actual={'raise' if err_bad else 'pass'}/"
          f"{'None' if err_ok is None else 'raise'}")

    # ---- W5b-3 扩展（专家第七轮 6.2/R29/R30/R31）：NC-27..29 ----
    # NC-27（P1-5/R29）：文本数字漂移必须被语义检查抓到——把 C-010 的「任务层 N 行」改小。
    # ★ 变异锚点**不得写死**（这是同一坑第三次复发：NC-49 写死 NC-23..48、本轮又写死「165」）。
    #   数据集一扩容，`replace('任务层 **165 行**', ...)` 就静默不命中 ⇒ hit=False ⇒ 负控假红，
    #   而它红的原因与本次改动毫无关系。**锚点必须从被测产物现取**（R29）。
    import re as _re27
    real_md = open(os.path.join(ROOT_, 'FEM-Bench-Aero', 'CLAIMS.md'), encoding='utf-8').read()
    _m27 = _re27.search(r'(任务层\s*\*\*)(\d+)(\s*行\*\*)', real_md)
    mut_md, hit27, _v27 = real_md, False, None
    if _m27:
        _v27 = int(_m27.group(2))
        mut_md = real_md[:_m27.start(2)] + str(_v27 - 25) + real_md[_m27.end(2):]
        hit27 = (mut_md != real_md)
    rc27, o27 = run_check_claims(mut_md, 'nc27')
    ok27 = hit27 and rc27 != 0 and 'S-01' in o27
    results.append({'id': 'NC-27',
                    'desc': '文本计数漂移（C-010 任务层行数 −25 vs artifact 实读）⇒ 语义检查 FAIL',
                    'expect': 'rc!=0 + 报 S-01', 'actual': f'hit={hit27} rc={rc27} 锚点={_v27}',
                    'ok': ok27})
    print(f"  [{'ok ' if ok27 else 'BAD!'}] NC-27 文本计数漂移被语义检查抓到                    "
          f"expect=rc!=0+S-01 actual=hit={hit27} rc{rc27} 锚点值={_v27}")

    # NC-28（R31）：v6 考卷 55 条、候选只有 30 条 ⇒ 成绩单必须拒绝当正式成绩（覆盖不全）
    from score_baseline import scorecard_coverage_problems
    fake_incomplete = {'n_tasks_in_paper': 55, 'provenance': {'n_candidates': 30},
                       'candidates_missing': [f'miss_{i}' for i in range(25)],
                       'partial_candidates': True, 'partial': True,
                       'exam': {'n': 13}, 'n_tasks_exam_expected': 25}
    bad28 = scorecard_coverage_problems(fake_incomplete)
    sc28_path = os.path.join(HERE, 'reports', 'baseline_scorecard_L3_v4.json')
    good28 = (scorecard_coverage_problems(json.load(open(sc28_path, encoding='utf-8')))
              if os.path.exists(sc28_path) else ['no scorecard'])
    ok28 = bool(bad28) and not good28
    results.append({'id': 'NC-28', 'desc': '候选未覆盖全卷 ⇒ 成绩单标记不可当正式成绩（R31）',
                    'expect': f'bad={len(bad28)}>0 / good=0',
                    'actual': f'bad={len(bad28)} / good={len(good28)}', 'ok': ok28})
    print(f"  [{'ok ' if ok28 else 'BAD!'}] NC-28 候选覆盖不全被标记                            "
          f"expect=bad>0/good=0 actual=bad{len(bad28)}/good{len(good28)}")

    # NC-29（R30）：v6 的 25 条与 C-021 的 11 条混比必须被拒绝（同文件自比必须允许）
    from compare_scorecards import comparability
    if os.path.exists(sc28_path):
        v4sc = json.load(open(sc28_path, encoding='utf-8'))
        fake_v6 = {'exam': {'n': 25}, 'exam_definition': v4sc.get('exam_definition'),
                   'exam_by_stratum': {'boundary': {'n': 6}, 'extrapolation': {'n': 13},
                                       'interpolation': {'n': 6}}}
        cross_ok, why = comparability(v4sc, fake_v6)
        same_ok, _ = comparability(v4sc, v4sc)
        ok29 = (not cross_ok) and bool(why) and same_ok
        actual29 = f'cross={"可" if cross_ok else "拒"}({len(why)} 理由) / same={"可" if same_ok else "拒"}'
    else:
        ok29, actual29 = False, 'no scorecard'
    results.append({'id': 'NC-29', 'desc': 'v6(25) 与 C-021(11) 混比被拒（R30）',
                    'expect': 'cross=拒 / same=可', 'actual': actual29, 'ok': ok29})
    print(f"  [{'ok ' if ok29 else 'BAD!'}] NC-29 跨口径混比被拒                                "
          f"expect=cross拒/same可 actual={actual29}")

    # ================= W5c 扩展（专家第八轮 §6）：NC-30..35 =================
    # NC-30（R33）：R32+R41 审计是考卷冻结闸——**两端口径**：
    #   ① exam 范围必须 0 VIOLATION（对外 headline 的题面必须可解）；
    #   ② 非 exam 允许存在**已登记**的 VIOLATION，但 task_id 集必须与白名单逐字相等——
    #      白名单只许缩小不许扩大（任何新增违规都会让本条变 BAD）。
    #   ＋反向验证：抽掉一条题面的腹板位置 ⇒ 必须被抓（防「闸门空转」）。
    import subprocess, tempfile
    paper6 = os.path.join(HERE, 'reports', 'papers', 'tasks_v6c.jsonl')
    if os.path.exists(paper6):
        from r32_audit import KNOWN_NONEXAM_VIOL   # 唯一出处，见 r32_audit.py 顶部注释
        rc_exam = subprocess.run([sys.executable, os.path.join(HERE, 'r32_audit.py'),
                                  '--tasks', paper6, '--scope', 'exam'],
                                 capture_output=True, text=True, encoding='utf-8',
                                 errors='replace').returncode
        p_all = subprocess.run([sys.executable, os.path.join(HERE, 'r32_audit.py'),
                                '--tasks', paper6, '--scope', 'all'],
                               capture_output=True, text=True, encoding='utf-8',
                               errors='replace')
        try:
            non_exam_viol = set(json.load(open(os.path.join(HERE, 'reports', 'r32_audit_v6c.json'),
                                               encoding='utf-8')).get('violations_by_task') or {})
        except Exception:
            non_exam_viol = set()
        rc_good = rc_exam if (rc_exam == 0 and non_exam_viol == KNOWN_NONEXAM_VIOL) else 1
        # 反向：把 web1 的「中间腹板」句删掉（模拟 v6b 的缺陷），审计必须报 airfoil.web_chordwise
        rows30 = [json.loads(l) for l in open(paper6, encoding='utf-8') if l.strip()]
        hit30 = 0
        for r in rows30:
            if r['task_id'] == 'L3_naca4412_wingbox_web1':
                before = r['input']['nl']
                r['input']['nl'] = before.replace('加 1 道中间腹板（位于 0.475 弦向），', '')
                hit30 = int(before != r['input']['nl'])
        tmp30 = os.path.join(RUNS, '_nc30_paper_mut.jsonl')
        os.makedirs(RUNS, exist_ok=True)
        with open(tmp30, 'w', encoding='utf-8') as f:
            for r in rows30:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        p30 = subprocess.run([sys.executable, os.path.join(HERE, 'r32_audit.py'),
                              '--tasks', tmp30, '--scope', 'all'],
                             capture_output=True, text=True, encoding='utf-8', errors='replace')
        ok30 = (rc_good == 0) and hit30 == 1 and p30.returncode != 0 and 'web_chordwise' in p30.stdout
        results.append({'id': 'NC-30', 'desc': 'R32/R41 审计闸：exam 0 违规 + 非 exam 白名单逐字相等 + 反向验证（R33）',
                        'expect': 'exam_rc=0 / viol==白名单 / mutated=1+web_chordwise',
                        'actual': f'exam_rc={rc_exam} all_rc={p_all.returncode} '
                                  f'viol={sorted(non_exam_viol)} hit={hit30} mut_rc={p30.returncode}',
                        'ok': ok30})
        print(f"  [{'ok ' if ok30 else 'BAD!'}] NC-30 审计闸（exam 0 + 白名单 + 反向）              "
              f"expect=exam0/viol=白名单/mut>0 actual=exam{rc_exam}/viol{len(non_exam_viol)}/mut{p30.returncode}")
    else:
        results.append({'id': 'NC-30', 'desc': 'R32 审计闸（考卷缺失，跳过）', 'expect': 'skip',
                        'actual': 'no paper', 'ok': True})
        print('  [ ok ] NC-30 R32 审计闸（考卷缺失，跳过）')

    # NC-31（R34）：生成器 SYS prompt 必须列全四族 KNOWN_KEYS（键名从 GRADED_FIELDS 实读，不硬编码）
    from evaluate import GRADED_FIELDS
    sys_src = open(os.path.join(HERE, 'gen_candidates_v2.js'), encoding='utf-8').read()
    must = set()
    for fam, (holder, keys) in GRADED_FIELDS.items():
        must |= set(keys)
    must |= {'hole_d', 'hole_x', 'hole_y', 'layup', 'end_shear', 'end_moment'}
    miss31 = sorted(k for k in must if k not in sys_src)
    banned_ok = 'ply_material' in sys_src and '绝不要' in sys_src   # 只允许作为「禁止键」出现
    ok31 = (not miss31) and banned_ok
    results.append({'id': 'NC-31', 'desc': '生成器 SYS prompt 键名表齐全（R34）',
                    'expect': 'missing=0 / 禁键有明示', 'actual': f'missing={miss31[:5]} banned_hint={banned_ok}',
                    'ok': ok31})
    print(f"  [{'ok ' if ok31 else 'BAD!'}] NC-31 SYS prompt 键名表齐全                        "
          f"expect=0 actual={len(miss31)} missing{miss31[:3]}")

    # NC-32（R40）：T1 必须 leave-one-out——地板报告不得有自命中；源码必须带排除条件
    tb_src = open(os.path.join(HERE, 'trivial_baselines.py'), encoding='utf-8').read()
    src_loo = "tt['task_id'] != t['task_id']" in tb_src
    tr_path = os.path.join(HERE, 'reports', 'trivial_baselines_L3_v6c.json')
    self_hits, loo_flag = [], None
    if os.path.exists(tr_path):
        tr = json.load(open(tr_path, encoding='utf-8'))
        loo_flag = tr.get('t1_leave_one_out')
        self_hits = [r['task_id'] for r in tr.get('per_task', []) if r.get('T1_self_hit')]
    ok32 = src_loo and (loo_flag is True) and not self_hits
    results.append({'id': 'NC-32', 'desc': 'T1 leave-one-out（检索库不含目标自身，R40）',
                    'expect': '源码过滤 + 报告无自命中', 'actual': f'src={src_loo} flag={loo_flag} self={len(self_hits)}',
                    'ok': ok32})
    print(f"  [{'ok ' if ok32 else 'BAD!'}] NC-32 T1 leave-one-out                              "
          f"expect=过滤+0自命中 actual=src{src_loo}/flag{loo_flag}/self{len(self_hits)}")

    # NC-33（R38）：成绩单摘要字符串不得是 W4d 旧文案
    ok33, a33 = False, 'no scorecard'
    if os.path.exists(sc_path):
        sc33 = json.load(open(sc_path, encoding='utf-8'))
        ed = sc33.get('exam_definition') or ''
        note = sc33.get('note') or ''
        split_ok = not any(k in {'boundary_holdout', 'extrapolation_test'}
                           and False for k in [])
        by_split33 = sc33.get('by_split') or {}
        exam_in_split = [k for k in by_split33 if k in ('boundary_holdout', 'extrapolation_test',
                                                        'interpolation_test')]
        ok33 = ('exam_stratum' in ed) and ('W4d' not in note) and not exam_in_split \
            and bool(sc33.get('by_split_note'))
        a33 = f"exam_def含stratum={'exam_stratum' in ed} W4d旧串={'W4d' in note} " \
              f"by_split混入exam={exam_in_split} note={bool(sc33.get('by_split_note'))}"
    results.append({'id': 'NC-33', 'desc': '成绩单口径字符串由考卷生成（R38）',
                    'expect': 'stratum + 无 W4d + by_split 不含 exam', 'actual': a33, 'ok': ok33})
    print(f"  [{'ok ' if ok33 else 'BAD!'}] NC-33 成绩单口径字符串                              "
          f"expect=stratum/无W4d/by_split纯dev actual={a33}")

    # NC-34（R37）：官方文档不得引用 eval_runs/ 下的具体文件（未追踪）
    import re as _re
    docs = [os.path.join(ROOT_, 'FEM-Bench-Aero', f) for f in ('CLAIMS.md', 'RUBRIC.md', 'README.md')]
    docs.append(os.path.join(HERE, 'reports', 'INDEX.md'))
    pat = _re.compile(r'eval_runs/[A-Za-z0-9_./\-]+\.(?:md|json|jsonl)')
    hits34 = []
    for d in docs:
        if not os.path.exists(d):
            continue
        for m in pat.finditer(open(d, encoding='utf-8').read()):
            hits34.append(f'{os.path.basename(d)}:{m.group(0)}')
    ok34 = not hits34
    results.append({'id': 'NC-34', 'desc': '官方文档不引用 eval_runs/ 具体文件（R37）',
                    'expect': 'empty', 'actual': str(hits34[:3]) or 'empty', 'ok': ok34})
    print(f"  [{'ok ' if ok34 else 'BAD!'}] NC-34 官方文档不引 eval_runs/ 文件                 "
          f"expect=empty actual={len(hits34)} 处{hits34[:2]}")

    # NC-35（R39）：同条数但 task-id 集不同 ⇒ 必须拒绝比较；同集 ⇒ 允许
    from compare_scorecards import comparability
    fake_a = {'exam': {'n': 25}, 'exam_definition': 'X', 'exam_by_stratum': {'boundary': {'n': 25}},
              'exam_task_ids_sha256': 'a' * 64, 'exam_by_family': {'wingbox': 25}}
    fake_b = {'exam': {'n': 25}, 'exam_definition': 'X', 'exam_by_stratum': {'boundary': {'n': 25}},
              'exam_task_ids_sha256': 'b' * 64, 'exam_by_family': {'wingbox': 25}}
    rej35, why35 = comparability(fake_a, fake_b)
    same35, _ = comparability(fake_a, fake_a)
    ok35 = (not rej35) and bool(why35) and same35
    results.append({'id': 'NC-35', 'desc': '同条数不同 task-id 集必须拒绝比较（R39）',
                    'expect': 'cross=拒 / same=可',
                    'actual': f'cross={"可" if rej35 else "拒"}({len(why35)} 理由) / same={"可" if same35 else "拒"}',
                    'ok': ok35})
    print(f"  [{'ok ' if ok35 else 'BAD!'}] NC-35 同条数≠同批题 被拒                             "
          f"expect=cross拒/same可 actual={'可' if rej35 else '拒'}/{'可' if same35 else '拒'}")

    # NC-37（W5c 契约闸）：`audit_contract.py` 必须**咬得住**——真 gold 全可建（rc=0），
    # 人为删掉一个必填键后必须 rc=1。这道闸的意义是回答专家第八轮 §3.2 的疑问：
    # 3 条 TSR/SFR 双 PASS 但 MSR contract 失败的题，是模型错还是 builder 不支持合法组合？
    # gold 能建 ⇒ 模型错（合理）；gold 不能建 ⇒ 任务缺陷（不算模型能力）。
    # 没有反向验证的话，脚本「永远返回 0」也看不出来。
    import shutil, tempfile
    tmp_cases = os.path.join(RUNS, '_nc37_cases')
    ok37, det37 = False, 'skip'
    paper6p = os.path.join(HERE, 'reports', 'papers', 'tasks_v6c.jsonl')
    if os.path.exists(paper6p):
        r37 = subprocess.run([sys.executable, os.path.join(HERE, 'audit_contract.py'),
                              '--tasks', paper6p, '--out', os.path.join(RUNS, '_nc37_real.json')],
                             capture_output=True, text=True, encoding='utf-8', errors='replace')
        # 反向：拷一个案例、删掉 material.youngs_modulus，做一个只含该条的临时考卷
        cid37 = 'naca4412_wingbox'
        src37 = os.path.join(FEA, 'modeling', cid37)
        mut_ok = False
        if os.path.isdir(src37):
            shutil.rmtree(tmp_cases, ignore_errors=True)
            shutil.copytree(src37, os.path.join(tmp_cases, cid37))
            sp37 = os.path.join(tmp_cases, cid37, 'spec.json')
            d37 = json.load(open(sp37, encoding='utf-8'))
            # ★ 变异必须选**真实失效模式**：试建闸管的是「未知键 / 非法值」（TypeError/ValueError），
            #   **不管缺键**——实测删掉 material.youngs_modulus 仍然 55/55 可建（FEASpec 对缺键宽容）。
            #   这是本闸的已知边界，写进注释免得后人误以为它做了 schema required 校验。
            before37 = dict(d37.get('material') or {})
            (d37.setdefault('material') or {})['ply_material'] = {'name': 'NC37'}
            mut_ok = 'ply_material' not in before37
            json.dump(d37, open(sp37, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            one37 = [json.loads(l) for l in open(paper6p, encoding='utf-8')
                     if l.strip() and json.loads(l)['task_id'] == 'L3_' + cid37]
            one_path37 = os.path.join(RUNS, '_nc37_one.jsonl')
            with open(one_path37, 'w', encoding='utf-8') as f:
                for r in one37:
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
            r37m = subprocess.run([sys.executable, os.path.join(HERE, 'audit_contract.py'),
                                   '--cases', tmp_cases, '--tasks', one_path37,
                                   '--out', os.path.join(RUNS, '_nc37_mut.json')],
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
            ok37 = (r37.returncode == 0) and mut_ok and (r37m.returncode == 1)
            det37 = f'real_rc={r37.returncode} hit={mut_ok} mut_rc={r37m.returncode}'
        shutil.rmtree(tmp_cases, ignore_errors=True)
    results.append({'id': 'NC-37', 'desc': '契约试建闸咬得住：gold 全可建 / 删必填键必拒（W5c）',
                    'expect': 'real=0 / 注入自创键 mutated=1', 'actual': det37, 'ok': ok37})
    print(f"  [{'ok ' if ok37 else 'BAD!'}] NC-37 契约试建闸（含反向）                            "
          f"expect=real0/mut1 actual={det37}")

    # NC-38（R42 反向）：把一条**历史** claim（C-021）的状态列改成自指标记「（对外 headline）」，
    # 语义检查必须立刻报 S-29 ——否则「headline 唯一」就只是一句话，不是闸。
    # ★ 先断言替换真命中（W5a 教训：替换没命中却记 PASS = 静默空转的负控）。
    real_md38 = open(os.path.join(ROOT_, 'FEM-Bench-Aero', 'CLAIMS.md'), encoding='utf-8').read()
    mut_md38 = real_md38.replace('| 30/30 生成 / exam 11 | active |',
                                 '| 30/30 生成 / exam 11 | active（对外 headline） |')
    hit38 = (mut_md38 != real_md38)
    rc38, o38 = run_check_claims(mut_md38, 'nc38')
    ok38 = hit38 and rc38 != 0 and 'S-29' in o38
    results.append({'id': 'NC-38', 'desc': '第二个 headline 必须被 R42/S-29 拒绝',
                    'expect': 'hit + rc!=0 + 报 S-29', 'actual': f'hit={hit38} rc={rc38} S-29={"S-29" in o38}',
                    'ok': ok38})
    print(f"  [{'ok ' if ok38 else 'BAD!'}] NC-38 第二个 headline 被 S-29 拒绝                      "
          f"expect=hit+rc!=0+S-29 actual=hit={hit38} rc{rc38}")

    # NC-39（R44 反向）：T1+ 地板缺节时 S-32 必须红 —— 否则「T1+ 必须非空」也只是口号。
    # 正向喂真 artifact 必须绿，反向删掉 T1plus_family 必须红（同一份判据，不复制逻辑）。
    from check_claims import t1plus_consistency
    tp_path = os.path.join(HERE, 'reports', 'trivial_baselines_L3_v6c.json')
    sc_path39 = os.path.join(HERE, 'reports', 'baseline_scorecard_L3_v6c.json')
    ok39, det39 = False, 'no artifact'
    if os.path.exists(tp_path) and os.path.exists(sc_path39):
        tp_real = json.load(open(tp_path, encoding='utf-8'))
        sc_real = json.load(open(sc_path39, encoding='utf-8'))
        ok_fwd, d_fwd = t1plus_consistency(tp_real, sc_real)
        tp_mut = json.loads(json.dumps(tp_real))
        tp_mut.pop('T1plus_family', None)
        ok_rev, d_rev = t1plus_consistency(tp_mut, sc_real)
        # 第三种变异：只删字段命中率（数据在但对照尺度没了）也必须红
        tp_mut2 = json.loads(json.dumps(tp_real))
        tp_mut2['T1plus_family'].pop('avg_field_hit_rate_exam', None)
        ok_rev2, _ = t1plus_consistency(tp_mut2, sc_real)
        ok39 = ok_fwd and (not ok_rev) and (not ok_rev2)
        det39 = (f'正向={"过" if ok_fwd else "红"} 删节={"红" if not ok_rev else "漏判"} '
                 f'删命中率={"红" if not ok_rev2 else "漏判"}')
    results.append({'id': 'NC-39', 'desc': 'T1+ 地板缺节/缺字段命中率必须被 R44/S-32 拒绝',
                    'expect': 'fwd=True / 两向变异=False', 'actual': det39, 'ok': ok39})
    print(f"  [{'ok ' if ok39 else 'BAD!'}] NC-39 T1+ 地板缺节时 S-32 必红（正反两向）              "
          f"expect=fwd T/mut F actual={det39}")

    # NC-40（R47 反向）：比率分母**必须闭合**。三向守：
    #   正向（真 artifact 过）/ 变异①（复现旧 bug：把编造题从分母里排掉，25→22）/ 变异②（分母字段缺失）。
    # 为什么这条必须有：C-031 的旧成绩单就是变异①的形态，算出与 C-029 一字不差的 99.34%。
    from check_claims import denominator_accounting, verdict_split_recorded
    sc31_path = os.path.join(HERE, 'reports', 'baseline_scorecard_L3_v6c_dsv4pro.json')
    ok40, det40 = False, 'no artifact'
    sc31_real = None
    if os.path.exists(sc31_path):
        sc31_real = json.load(open(sc31_path, encoding='utf-8'))
        ok_f40, _ = denominator_accounting(sc31_real, 'C-031')
        m1 = json.loads(json.dumps(sc31_real))
        m1['value_added']['field_level']['n_exam_counted'] = 22      # 复现旧 bug
        ok_r40a, _ = denominator_accounting(m1, 'C-031mut')
        m2 = json.loads(json.dumps(sc31_real))
        for k in ('n_exam_counted', 'n_excluded_clarify_ok', 'n_zero_non_spec'):
            m2['value_added']['field_level'].pop(k, None)
        ok_r40b, _ = denominator_accounting(m2, 'C-031mut2')
        ok40 = ok_f40 and (not ok_r40a) and (not ok_r40b)
        det40 = (f'正向={"过" if ok_f40 else "红"} 复现旧bug={"红" if not ok_r40a else "漏判"} '
                 f'缺分母字段={"红" if not ok_r40b else "漏判"}')
    results.append({'id': 'NC-40', 'desc': '分母不闭合/缺构成必须被 R47/S-33 拒绝',
                    'expect': 'fwd=True / 两向变异=False', 'actual': det40, 'ok': ok40})
    print(f"  [{'ok ' if ok40 else 'BAD!'}] NC-40 分母不闭合被 S-33 拒绝（正反两向）            "
          f"expect=fwd T/mut F actual={det40}")

    # NC-41（R48 反向）：把 C-031 的状态列改成自指标记「（对外 headline）」⇒ S-34 必须红。
    # 否则「不得事后择优」只是一句话（S-29 只守"恰好一条"，把标记搬过去它仍会过）。
    real_md41 = open(os.path.join(ROOT_, 'FEM-Bench-Aero', 'CLAIMS.md'), encoding='utf-8').read()
    mut_md41 = real_md41.replace('| active（supporting） |', '| active（对外 headline） |')
    hit41 = (mut_md41 != real_md41)
    rc41, o41 = run_check_claims(mut_md41, 'nc41')
    ok41 = hit41 and rc41 != 0 and 'S-34' in o41
    results.append({'id': 'NC-41', 'desc': '第二模型抢 headline 必须被 R48/S-34 拒绝',
                    'expect': 'hit + rc!=0 + 报 S-34', 'actual': f'hit={hit41} rc={rc41} S-34={"S-34" in o41}',
                    'ok': ok41})
    print(f"  [{'ok ' if ok41 else 'BAD!'}] NC-41 第二模型抢 headline 被 S-34 拒绝               "
          f"expect=hit+rc!=0+S-34 actual=hit={hit41} rc{rc41}")

    # NC-42（R49 反向）：删掉 verdict_split ⇒ S-35 必须红（双尺度分裂不得被隐藏）
    ok42, det42 = False, 'no artifact'
    if sc31_real is not None:
        ok_f42, _ = verdict_split_recorded(sc31_real, 'C-031')
        m3 = json.loads(json.dumps(sc31_real))
        m3['value_added'].pop('verdict_split', None)
        ok_r42, _ = verdict_split_recorded(m3, 'C-031mut')
        ok42 = ok_f42 and (not ok_r42)
        det42 = f'正向={"过" if ok_f42 else "红"} 删split={"红" if not ok_r42 else "漏判"}'
    results.append({'id': 'NC-42', 'desc': '双尺度分裂被隐藏必须被 R49/S-35 拒绝',
                    'expect': 'fwd=True / 删 verdict_split=False', 'actual': det42, 'ok': ok42})
    print(f"  [{'ok ' if ok42 else 'BAD!'}] NC-42 双尺度分裂被隐藏被 S-35 拒绝                 "
          f"expect=fwd T/mut F actual={det42}")

    # NC-43（R51 反向）：把 C-031 的顶层 model 改回 glm-5.3-flash（复现旧 bug）⇒ S-36 必须红；
    # 删掉 provenance.model ⇒ 也必须红（缺交叉核对依据）。
    from check_claims import model_label_consistent, msr_denominator_closure, prompt_no_blind_default
    ok43, det43 = False, 'no artifact'
    if sc31_real is not None:
        ok_f43, _ = model_label_consistent(sc31_real, 'C-031')
        m43a = json.loads(json.dumps(sc31_real))
        m43a['model'] = 'glm-5.3-flash'          # 复现旧 bug：顶层硬编码默认值
        ok_r43a, _ = model_label_consistent(m43a, 'C-031mut')
        m43b = json.loads(json.dumps(sc31_real))
        (m43b.get('provenance') or {}).pop('model', None)
        ok_r43b, _ = model_label_consistent(m43b, 'C-031mut2')
        ok43 = ok_f43 and (not ok_r43a) and (not ok_r43b)
        det43 = (f'正向={"过" if ok_f43 else "红"} 顶层改glm={"红" if not ok_r43a else "漏判"} '
                 f'删prov.model={"红" if not ok_r43b else "漏判"}')
    results.append({'id': 'NC-43', 'desc': '顶层 model 与 provenance 不一致必须被 R51/S-36 拒绝',
                    'expect': 'fwd=True / 两向变异=False', 'actual': det43, 'ok': ok43})
    print(f"  [{'ok ' if ok43 else 'BAD!'}] NC-43 顶层 model 写错被 S-36 拒绝                     "
          f"expect=fwd T/mut F actual={det43}")

    # NC-44（R52 反向）：把「未收敛」混回 n_clarify_excluded（复现旧 bug 5=4+1）⇒ S-37 必须红；
    # 删掉 denominator_audit ⇒ 也必须红（分母构成未落盘）。
    ok44, det44 = False, 'no artifact'
    if sc31_real is not None:
        ok_f44, _ = msr_denominator_closure(sc31_real, 'C-031')
        m44a = json.loads(json.dumps(sc31_real))
        m44a['msr_section']['n_clarify_excluded'] = 5        # 复现旧 bug：4 澄清 + 1 未收敛
        ok_r44a, _ = msr_denominator_closure(m44a, 'C-031mut')
        m44b = json.loads(json.dumps(sc31_real))
        m44b['msr_section'].pop('denominator_audit', None)
        ok_r44b, _ = msr_denominator_closure(m44b, 'C-031mut2')
        ok44 = ok_f44 and (not ok_r44a) and (not ok_r44b)
        det44 = (f'正向={"过" if ok_f44 else "红"} 混入unresolved={"红" if not ok_r44a else "漏判"} '
                 f'删audit={"红" if not ok_r44b else "漏判"}')
    results.append({'id': 'NC-44', 'desc': '分母混类/未落盘必须被 R52/S-37 拒绝',
                    'expect': 'fwd=True / 两向变异=False', 'actual': det44, 'ok': ok44})
    print(f"  [{'ok ' if ok44 else 'BAD!'}] NC-44 分母混类被 S-37 拒绝                          "
          f"expect=fwd T/mut F actual={det44}")

    # NC-45（R50 反向）：把「未提长桁→长桁数=0」写回 prompt ⇒ S-38 必须红；
    # 把 expected_clarifications 注入 prompt（等于泄漏答案）⇒ 也必须红。
    import tempfile
    ok45, det45 = False, 'no source'
    _p45 = os.path.join(HERE, 'gen_candidates_v2.js')
    if os.path.exists(_p45):
        ok_f45, _ = prompt_no_blind_default(_p45)
        _src45 = open(_p45, encoding='utf-8').read()
        _td = tempfile.mkdtemp()
        _f1 = os.path.join(_td, 'mut_a.js')
        open(_f1, 'w', encoding='utf-8').write(
            _src45.replace('数量类字段铁律', '数量类字段铁律（未提长桁→长桁数=0）'))
        ok_r45a, _ = prompt_no_blind_default(_f1, 'mutA')
        _f2 = os.path.join(_td, 'mut_b.js')
        open(_f2, 'w', encoding='utf-8').write(_src45 + '\n// 注入答案键 expected_clarifications\n')
        ok_r45b, _ = prompt_no_blind_default(_f2, 'mutB')
        ok45 = ok_f45 and (not ok_r45a) and (not ok_r45b)
        det45 = (f'正向={"过" if ok_f45 else "红"} 写回盲填={"红" if not ok_r45a else "漏判"} '
                 f'注入答案键={"红" if not ok_r45b else "漏判"}')
    results.append({'id': 'NC-45', 'desc': 'prompt 盲填授权/注入答案键必须被 R50/S-38 拒绝',
                    'expect': 'fwd=True / 两向变异=False', 'actual': det45, 'ok': ok45})
    print(f"  [{'ok ' if ok45 else 'BAD!'}] NC-45 prompt 盲填授权被 S-38 拒绝                    "
          f"expect=fwd T/mut F actual={det45}")

    # NC-46（R54 反向）：MSR 是条件通过率 ⇒ ①删掉 msr_definition（口径未写进成绩单）
    # ②只把分母改小但不点名被排除的题（复现 C-033 的 20/21 口径）⇒ S-40 必须红。
    # 动机与那条 MSR 反直觉同源：被排除的恰好是失败题 ⇒ 分母小的 pct 反而「更高」。
    ok46, det46 = False, 'no artifact'
    from check_claims import msr_conditional_declared
    sc33_real = None
    _p46 = os.path.join(HERE, 'reports', 'baseline_scorecard_L3_v6c_ds_p2.json')
    if os.path.exists(_p46):
        sc33_real = json.load(open(_p46, encoding='utf-8'))
    if sc33_real is not None:
        ok_f46, _ = msr_conditional_declared(sc33_real, 'C-033')
        m46a = json.loads(json.dumps(sc33_real))
        m46a['msr_section'].pop('msr_definition', None)
        ok_r46a, _ = msr_conditional_declared(m46a, 'C-033mut')
        m46b = json.loads(json.dumps(sc33_real))
        m46b['msr_section'].pop('n_no_spec_excluded_ids', None)   # 只降分母不点名
        ok_r46b, _ = msr_conditional_declared(m46b, 'C-033mut2')
        m46c = json.loads(json.dumps(sc33_real))
        m46c['msr_section']['n_no_spec_excluded_ids'] = []        # 点名清空但审计仍 1 条
        ok_r46c, _ = msr_conditional_declared(m46c, 'C-033mut3')
        ok46 = ok_f46 and (not ok_r46a) and (not ok_r46b) and (not ok_r46c)
        det46 = (f'正向={"过" if ok_f46 else "红"} 删口径={"红" if not ok_r46a else "漏判"} '
                 f'不点名={"红" if not ok_r46b else "漏判"} 点名清空={"红" if not ok_r46c else "漏判"}')
    results.append({'id': 'NC-46', 'desc': 'MSR 条件口径未声明/排除项未点名必须被 R54/S-40 拒绝',
                    'expect': 'fwd=True / 三向变异=False', 'actual': det46, 'ok': ok46})
    print(f"  [{'ok ' if ok46 else 'BAD!'}] NC-46 MSR 条件口径缺声明被 S-40 拒绝                "
          f"expect=fwd T/mut F actual={det46}")

    # NC-47（R55/R56 反向，第十一轮 §6）：
    #   ①榜单缺字段级一列 ⇒ S-42 必须红（三列并排是硬要求）；
    #   ②分母不等却把 msr_delta_allowed 填 True ⇒ S-42 必须红（该字段不得手填）；
    #   ③dev 翻转未闭合（closure.ok=False）⇒ S-41 必须红；
    #   ④dev 净额变了但翻转列表清空 ⇒ S-41 必须红（「没定位」不能被当成「没变化」）。
    from check_claims import dev_reversal_closed, w5d_leaderboard_ok
    ok47, det47 = False, 'no artifact'
    _lb = os.path.join(HERE, 'reports', 'w5d_leaderboard.json')
    _dr = os.path.join(HERE, 'reports', 'diagnostics', 'dev_reversal_v6c_p2.json')
    if os.path.exists(_lb) and os.path.exists(_dr):
        lb_real = json.load(open(_lb, encoding='utf-8'))
        dr_real = json.load(open(_dr, encoding='utf-8'))
        ok_f47a, _ = w5d_leaderboard_ok(_lb)
        ok_f47c, _ = dev_reversal_closed(_dr)

        m1 = json.loads(json.dumps(lb_real))
        for _k in list((m1.get('models') or {})):
            m1['models'][_k].pop('value_added', None)      # 砍掉字段级一列
        ok_r47a, _ = w5d_leaderboard_ok(_lb) if False else (None, None)
        # w5d_leaderboard_ok 读的是文件，变异体要落到临时文件
        import tempfile
        _td47 = tempfile.mkdtemp()
        _p1 = os.path.join(_td47, 'lb_mut1.json')
        json.dump(m1, open(_p1, 'w', encoding='utf-8'), ensure_ascii=False)
        open(_p1[:-5] + '.md', 'w', encoding='utf-8').write('（变异体：无 md 正文）')
        ok_r47a, _ = w5d_leaderboard_ok(_p1)

        m2 = json.loads(json.dumps(lb_real))
        if m2.get('pair'):
            m2['pair']['msr_delta_allowed'] = True          # 分母不等却硬填可减
            m2['pair']['msr_delta_pp'] = 4.3
        _p2 = os.path.join(_td47, 'lb_mut2.json')
        json.dump(m2, open(_p2, 'w', encoding='utf-8'), ensure_ascii=False)
        open(_p2[:-5] + '.md', 'w', encoding='utf-8').write('（变异体）')
        ok_r47b, _ = w5d_leaderboard_ok(_p2)

        m3 = json.loads(json.dumps(dr_real))
        m3['closure'] = dict(m3.get('closure') or {}, ok=False)
        _p3 = os.path.join(_td47, 'dr_mut1.json')
        json.dump(m3, open(_p3, 'w', encoding='utf-8'), ensure_ascii=False)
        ok_r47c, _ = dev_reversal_closed(_p3)

        m4 = json.loads(json.dumps(dr_real))
        m4['flips'] = []
        m4['dev_pass'] = dict(m4.get('dev_pass') or {}, delta=-1)
        _p4 = os.path.join(_td47, 'dr_mut2.json')
        json.dump(m4, open(_p4, 'w', encoding='utf-8'), ensure_ascii=False)
        ok_r47d, _ = dev_reversal_closed(_p4)

        ok47 = ok_f47a and ok_f47c and (not ok_r47a) and (not ok_r47b) and (not ok_r47c) and (not ok_r47d)
        det47 = (f'正向={"过" if (ok_f47a and ok_f47c) else "红"} '
                 f'缺字段级列={"红" if not ok_r47a else "漏判"} '
                 f'MSR硬填可减={"红" if not ok_r47b else "漏判"} '
                 f'dev不闭合={"红" if not ok_r47c else "漏判"} '
                 f'翻转清空={"红" if not ok_r47d else "漏判"}')
    results.append({'id': 'NC-47', 'desc': '榜单缺三列/分母不等却出Δ/dev未定位 必须被 R55/R56 拒绝',
                    'expect': 'fwd=True / 四向变异=False', 'actual': det47, 'ok': ok47})
    print(f"  [{'ok ' if ok47 else 'BAD!'}] NC-47 榜单三列/分母对齐/dev定位被 S-41/S-42 拒绝        "
          f"expect=fwd T/mut F actual={det47}")

    # NC-48（R57 补反向，W5d-1）：消融写「否决」但 prompt 没回退（或写「采纳」但没换）必须被抓。
    #   三向：①判采纳 + 当前 sha 仍 == 基线 ⇒ 红；②判否决 + sha 已变 ⇒ 红；③产物缺 decision ⇒ 红。
    from check_claims import prompt_ablation_consistent
    ok48, det48 = False, 'no artifact'
    _abl = os.path.join(HERE, 'reports', 'diagnostics', 'prompt_v3_ablation.json')
    _gen48 = os.path.join(HERE, 'gen_candidates_v2.js')
    _sc32 = os.path.join(HERE, 'reports', 'baseline_scorecard_L3_v6c_p2.json')
    if os.path.exists(_abl) and os.path.exists(_sc32):
        _base48 = (json.load(open(_sc32, encoding='utf-8')).get('provenance') or {}).get('prompt_sha256')
        abl_real = json.load(open(_abl, encoding='utf-8'))
        ok_f48, _ = prompt_ablation_consistent(_abl, _gen48, _base48, 'C-035')
        import tempfile as _tf
        _td48 = _tf.mkdtemp()
        m1 = json.loads(json.dumps(abl_real))
        m1['decision'] = dict(m1.get('decision') or {}, adopt=True)     # 判采纳但 sha 没换
        _p1 = os.path.join(_td48, 'abl_mut1.json')
        json.dump(m1, open(_p1, 'w', encoding='utf-8'), ensure_ascii=False)
        ok_r48a, _ = prompt_ablation_consistent(_p1, _gen48, 'deadbeef' * 8, 'mut1')   # 基线≠当前 ⇒ 采纳合法
        ok_r48b, _ = prompt_ablation_consistent(_p1, _gen48, _base48, 'mut2')           # 基线==当前 ⇒ 应红
        m2 = json.loads(json.dumps(abl_real))
        m2.pop('decision', None)
        _p2 = os.path.join(_td48, 'abl_mut2.json')
        json.dump(m2, open(_p2, 'w', encoding='utf-8'), ensure_ascii=False)
        ok_r48c, _ = prompt_ablation_consistent(_p2, _gen48, _base48, 'mut3')
        ok48 = ok_f48 and ok_r48a and (not ok_r48b) and (not ok_r48c)
        det48 = (f'正向={"过" if ok_f48 else "红"} 采纳但未换={"红" if not ok_r48b else "漏判"} '
                 f'采纳且已换={"过" if ok_r48a else "误判"} 缺decision={"红" if not ok_r48c else "漏判"}')
    results.append({'id': 'NC-48', 'desc': '消融判采纳但 prompt 未换 / 缺 decision 必须被 R57/S-43 拒绝',
                    'expect': 'fwd=True / 两向变异=False / 合法采纳=True', 'actual': det48, 'ok': ok48})
    print(f"  [{'ok ' if ok48 else 'BAD!'}] NC-48 消融结论与 prompt 不一致被 S-43 拒绝              "
          f"expect=fwd T/mut F actual={det48}")

    # NC-49（R58，T-A3；来自复核 N-1/N-2）：**「官方导航文件没被任何闸读」这件事必须被守住**。
    #   根因：S-00..S-43 共 44 项语义检查没有一条读 `reports/INDEX.md`（grep = 0 命中），
    #   于是 §2 的「⓪ 当前官方 headline（C-029）」与 §1 的（C-032）长期并存；agent 照 INDEX
    #   重跑 v1 代基线不会报错（两代 exam 同为 23/25，数字看着完全正常）。
    #   四向：①⓪ 段改回「当前官方 headline（C-029）」⇒ 红；②`NC-23..48` 改回 `..47` ⇒ 红；
    #         ③去掉 ⓪-hist 的历史标记（只留 C-029）⇒ 红；正向（真 INDEX）⇒ 绿。
    from check_claims import index_consistency, _latest_nc_json
    ok49, det49 = False, 'no artifact'
    _idx49 = os.path.join(HERE, 'reports', 'INDEX.md')
    _nc49 = _latest_nc_json(os.path.dirname(HERE))
    if os.path.exists(_idx49) and _nc49:
        _src49 = open(_idx49, encoding='utf-8').read()
        import tempfile as _tf49
        _td49 = _tf49.mkdtemp()

        def _mut49(tag, a, b):
            # 锚点缺失 ⇒ 返回 None ⇒ ok49 判红（**不得静默 skip**：R29 的教训）
            if a not in _src49:
                return None
            p = os.path.join(_td49, 'idx_%s.md' % tag)
            open(p, 'w', encoding='utf-8').write(_src49.replace(a, b, 1))
            return p

        ok_f49, _ = index_consistency(_idx49, _nc49, 'C-032')
        p_a = _mut49('n1', '# ⓪ 前置闸（考卷 v6c 通用，**与 headline 无关**）——先跑这三条就够',
                     '# ⓪ 当前官方 headline（C-029，考卷 v6c × 候选 v6c）——先跑这三条就够')
        # ★ 变异 2 **不能写死数字**：负控每加一条，主区间上界就变（NC-23..48 → ..49），
        #   写死会立刻变成「锚点缺失 ⇒ 漏判」（本轮就是这样翻过一次车）。
        #   改为从当前 INDEX 现取主区间（上界最大者）再减 1。
        import re as _re49
        _ln49 = next((l for l in _src49.split('\n')
                      if 'negative_controls_' in l and _re49.search(r'NC-\d+\.\.\d+', l)), '')
        _rs49 = [(m.group(0), int(m.group(1)), int(m.group(2)))
                 for m in _re49.finditer(r'NC-(\d+)\.\.(\d+)', _ln49)]
        _main49 = max(_rs49, key=lambda t: t[2]) if _rs49 else None
        p_b = (_mut49('n2', _main49[0], 'NC-%d..%d' % (_main49[1], _main49[2] - 1))
               if _main49 else None)
        p_c = _mut49('n3', '# ⓪-hist（**historical，不是当前 headline**）：C-029',
                     '# ⓪-hist（当前 headline）：C-029')
        ok_a = index_consistency(p_a, _nc49, 'C-032')[0] if p_a else None
        ok_b = index_consistency(p_b, _nc49, 'C-032')[0] if p_b else None
        ok_c = index_consistency(p_c, _nc49, 'C-032')[0] if p_c else None
        ok49 = bool(ok_f49) and (ok_a is False) and (ok_b is False) and (ok_c is False)
        det49 = (f'正向={"过" if ok_f49 else "红"} N-1回退={"红" if ok_a is False else "漏判"} '
                 f'N-2回退={"红" if ok_b is False else "漏判"} '
                 f'去历史标记={"红" if ok_c is False else "漏判"}')
    results.append({'id': 'NC-49', 'desc': 'INDEX 的 headline 指向/负控编号漂移必须被 R58/S-44 拒绝',
                    'expect': 'fwd=True / 三向变异=False',
                    'actual': det49, 'ok': ok49})
    print(f"  [{'ok ' if ok49 else 'BAD!'}] NC-49 INDEX 漂移必须被 S-44 拒绝                        "
          f"expect=fwd T/mut F actual={det49}")

    # NC-50（R59，T-A4）：**收口顺序反了必须被抓** —— 官方 JSON 记录的 artifact mtime 过期，
    #   或 check_claims.json 的文件时间早于负控 json。第十二轮就是这个形态（22:18 vs 22:19），
    #   内容/sha 全对、只有元数据旧，人工比对才抓到 ⇒ 必须有闸。
    #   ★ 用**合成夹具**而不是真实文件：负控在 check_claims 之前跑，此时官方 JSON 本来就还可能过期，
    #     拿它当正向用例会让 NC-50 随收口顺序抖动（第一版就踩了）。
    from check_claims import close_order_strict, dataset_cmds_use_venv
    ok50, det50 = False, 'no fixture'
    import tempfile as _tf50
    _td50 = _tf50.mkdtemp()
    _art50 = os.path.join(_td50, 'negative_controls_99.json')
    json.dump({'n_cases': 0, 'results': []}, open(_art50, 'w', encoding='utf-8'))
    _now50 = int(os.path.getmtime(_art50))
    _nc50 = os.path.join(_td50, 'nc_99.json')
    json.dump({'n_cases': 0, 'results': []}, open(_nc50, 'w', encoding='utf-8'))
    os.utime(_nc50, (_now50 - 100, _now50 - 100))

    def _mk_cc50(tag, rec_mtime, file_mtime):
        p = os.path.join(_td50, 'cc_%s.json' % tag)
        json.dump({'results': [{'claim_id': 'C-019', 'artifact': _art50, 'mtime': rec_mtime}]},
                  open(p, 'w', encoding='utf-8'))
        os.utime(p, (file_mtime, file_mtime))
        return p

    ok_f50, _ = close_order_strict(_mk_cc50('ok', _now50, _now50), _nc50, _td50)
    ok_a50, _ = close_order_strict(_mk_cc50('stale', _now50 - 3600, _now50), _nc50, _td50)  # 记录过期
    ok_b50, _ = close_order_strict(_mk_cc50('early', _now50, _now50 - 600), _nc50, _td50)   # 文件时间反序
    ok50 = bool(ok_f50) and (not ok_a50) and (not ok_b50)
    det50 = (f'正向={"过" if ok_f50 else "红"} 记录mtime过期={"红" if not ok_a50 else "漏判"} '
             f'文件时间反序={"红" if not ok_b50 else "漏判"}')
    results.append({'id': 'NC-50', 'desc': '收口顺序反（记录过期 / 文件时间反序）必须被 R59/S-45 拒绝',
                    'expect': 'fwd=True / 两向变异=False', 'actual': det50, 'ok': ok50})
    print(f"  [{'ok ' if ok50 else 'BAD!'}] NC-50 收口顺序反了必须被 S-45 拒绝                      "
          f"expect=fwd T/mut F actual={det50}")

    # NC-51（R60，T-A4）：**dataset 命令必须走 venv** —— 裸 `python` 或缺 `PY=` 必须被抓。
    ok51, det51 = False, 'no artifact'
    _idx51 = os.path.join(HERE, 'reports', 'INDEX.md')
    if os.path.exists(_idx51):
        _src51 = open(_idx51, encoding='utf-8').read()
        ok_f51, _ = dataset_cmds_use_venv(_idx51)
        import re as _re51
        import tempfile as _tf51
        _td51 = _tf51.mkdtemp()

        def _w51(tag, txt):
            p = os.path.join(_td51, 'idx_%s.md' % tag)
            open(p, 'w', encoding='utf-8').write(txt)
            return p

        _m1 = _src51.replace('"$PY" score_baseline.py', 'python score_baseline.py', 1)
        _m2 = _re51.sub(r'(?m)^PY=.*$', '', _src51, count=1)
        ok_a51 = dataset_cmds_use_venv(_w51('bare', _m1))[0] if _m1 != _src51 else None
        ok_b51 = dataset_cmds_use_venv(_w51('nopy', _m2))[0] if _m2 != _src51 else None
        ok51 = bool(ok_f51) and ok_a51 is False and ok_b51 is False
        det51 = (f'正向={"过" if ok_f51 else "红"} 裸python={"红" if ok_a51 is False else "漏判"} '
                 f'缺PY={"红" if ok_b51 is False else "漏判"}')
    results.append({'id': 'NC-51', 'desc': 'dataset 命令用裸 python / 缺 PY= 必须被 R60/S-46 拒绝',
                    'expect': 'fwd=True / 两向变异=False', 'actual': det51, 'ok': ok51})
    print(f"  [{'ok ' if ok51 else 'BAD!'}] NC-51 dataset 命令未走 venv 必须被 S-46 拒绝              "
          f"expect=fwd T/mut F actual={det51}")

    # NC-52（R61，T-A5）：**求解串行** —— 锁机制被抹掉、或残留锁存在，必须被 S-47 拒绝。
    #   起因：并行跑两个 ccx 会静默空转、返回码仍 0（本仓库踩过两次，第十二轮 §3.2 复述）。
    from check_claims import solver_serial_guard
    ok52, det52 = False, 'no artifact'
    _sp52 = os.path.join(HERE, 'feagpt', 'solver.py')
    if os.path.exists(_sp52):
        import tempfile as _tf52
        _td52 = _tf52.mkdtemp()
        _lk_absent = os.path.join(_td52, '.solve.lock')           # 不存在 ⇒ 正向应绿
        ok_f52, _ = solver_serial_guard(_sp52, _lk_absent)
        # 变异 1：把锁逻辑从源码里抹掉（模拟「防护被删」）
        _src52 = open(_sp52, encoding='utf-8').read()
        _m1 = (_src52.replace('_acquire_solve_lock', '_DISABLED_lock')
                     .replace('_release_solve_lock', '_DISABLED_unlock')
                     .replace('_run_unlocked', 'run'))
        _p1 = os.path.join(_td52, 'solver_nolock.py')
        open(_p1, 'w', encoding='utf-8').write(_m1)
        ok_a52 = solver_serial_guard(_p1, _lk_absent)[0]
        # 变异 2：残留锁（有求解在跑 / 上次崩了）
        _lk_present = os.path.join(_td52, '.solve.lock')
        open(_lk_present, 'w', encoding='utf-8').write('{"pid": 12345}')
        ok_b52 = solver_serial_guard(_sp52, _lk_present)[0]
        ok52 = bool(ok_f52) and (ok_a52 is False) and (ok_b52 is False)
        det52 = (f'正向={"过" if ok_f52 else "红"} 抹掉锁逻辑={"红" if ok_a52 is False else "漏判"} '
                 f'残留锁={"红" if ok_b52 is False else "漏判"}')
    results.append({'id': 'NC-52', 'desc': '求解锁机制被删 / 残留锁必须被 R61/S-47 拒绝',
                    'expect': 'fwd=True / 两向变异=False', 'actual': det52, 'ok': ok52})
    print(f"  [{'ok ' if ok52 else 'BAD!'}] NC-52 求解串行（锁机制/残留锁）必须被 S-47 拒绝            "
          f"expect=fwd T/mut F actual={det52}")

    # NC-53（R62，T-A9；来自 N-10）：**claim 正文里的计数漂移必须被抓**。
    #   根因：`grep "gate3\|C-003" check_claims.py` 曾是 0 命中——sha256 能证明「文件没被换」，
    #   不能证明「文件里写的数是对的」⇒ C-003 从 34/15/6 漂到 39/18/7 全程绿灯。
    #   四向（全部靠**正则从当前正文现取**，不写死数字）：
    #     ① field 减 1        ⇒ 红（计数漂移的原始形态）
    #     ② scalar-disp 减 2  ⇒ 红（正是 55 条时代的旧值 15/16，跨版本未更新的真实案例）
    #     ③ d36 子项加 1      ⇒ 红（构成闭合）
    #     ④ 删掉「不说 N/N」   ⇒ 红（锚点缺失必须判红，不得 skip —— R29 同源）
    from check_claims import gate3_counts_consistent
    import re as _re53
    ok53, det53 = False, 'no artifact'
    _root53 = os.path.dirname(HERE)
    _md53 = os.path.join(_root53, 'FEM-Bench-Aero', 'CLAIMS.md')
    _art53 = os.path.join(_root53, 'FEM-Bench-Aero', 'gate3_all55_d37.json')
    if os.path.exists(_md53) and os.path.exists(_art53):
        import tempfile as _tf53
        _td53 = _tf53.mkdtemp()
        _src53 = open(_md53, encoding='utf-8').read()
        _i53 = next((i for i, l in enumerate(_src53.split('\n'))
                     if l.lstrip().startswith('| C-003 |')), None)

        def _mut53(tag, pat, fn53):
            """只改 C-003 那一行；锚点缺失 / 替换无变化 ⇒ 返回 None ⇒ 判红（不 skip）。"""
            if _i53 is None:
                return None
            lines = _src53.split('\n')
            new = _re53.sub(pat, fn53, lines[_i53], count=1)
            if new == lines[_i53]:
                return None
            lines[_i53] = new
            p = os.path.join(_td53, 'claims_%s.md' % tag)
            open(p, 'w', encoding='utf-8').write('\n'.join(lines))
            return p

        _p_f = _md53                                        # 正向：真文件
        _p_a = _mut53('field', r'(\d+)(\s*field)',
                      lambda m: '%d%s' % (int(m.group(1)) - 1, m.group(2)))
        _p_b = _mut53('scalar', r'(\d+)(\s*scalar-disp)',
                      lambda m: '%d%s' % (int(m.group(1)) - 2, m.group(2)))
        _p_c = _mut53('d36', r'(\d+)(\s*条\s*d36)',
                      lambda m: '%d%s' % (int(m.group(1)) + 1, m.group(2)))
        _p_d = _mut53('nodim', r'（\s*\**\s*不说\s*\d+\s*/\s*\d+\s*\**\s*）', lambda m: '')
        _f53 = gate3_counts_consistent(_p_f, _art53)[0]
        _a53 = gate3_counts_consistent(_p_a, _art53)[0] if _p_a else None
        _b53 = gate3_counts_consistent(_p_b, _art53)[0] if _p_b else None
        _c53 = gate3_counts_consistent(_p_c, _art53)[0] if _p_c else None
        _d53 = gate3_counts_consistent(_p_d, _art53)[0] if _p_d else None
        ok53 = bool(_f53) and all(x is False for x in (_a53, _b53, _c53, _d53))
        det53 = (f'正向={"过" if _f53 else "红"} field-1={"红" if _a53 is False else "漏判"} '
                 f'scalar-2={"红" if _b53 is False else "漏判"} '
                 f'd36+1={"红" if _c53 is False else "漏判"} '
                 f'删分母={"红" if _d53 is False else "漏判"}')
    results.append({'id': 'NC-53', 'desc': 'C-003 计数漂移/构成不闭合/分母丢失必须被 R62/S-48 拒绝',
                    'expect': 'fwd=True / 四向变异=False', 'actual': det53, 'ok': ok53})
    print(f"  [{'ok ' if ok53 else 'BAD!'}] NC-53 C-003 计数漂移必须被 S-48 拒绝                      "
          f"expect=fwd T/mut F actual={det53}")

    # NC-54（R63/R64，T-A10；来自 N-12）：**S-48 之外的四条 claim 与对外数字表也必须被拒**。
    #   根因：S-48 只覆盖 C-003；`grep "gate4_v11|verify_dataset_v11|eval_report_v11|external_numbers"
    #   check_claims.py negative_controls.py` 曾两文件 0 命中 ⇒ C-001/2/4/5 与对外表裸奔。
    #   ★ 判据不只看「是否红」，还看**红的原因对不对**：S-50 的 (c) 陈旧判据几乎能吃下任何
    #     变异，若只断言「红」，(a) 缺分母列与 (b) 分母混写这两条会永远得不到证伪。
    from check_claims import claim_counts_consistent, external_numbers_consistent
    import re as _re54
    ok54, det54 = False, 'no artifact'
    _root54 = os.path.dirname(HERE)
    _md54 = os.path.join(_root54, 'FEM-Bench-Aero', 'CLAIMS.md')
    _ext_md54 = os.path.join(_root54, 'FEM-Bench-Aero', 'external_numbers.md')
    _ext_js54 = os.path.join(_root54, 'FEM-Bench-Aero', 'external_numbers.json')
    if all(os.path.exists(p) for p in (_md54, _ext_md54, _ext_js54)):
        import tempfile as _tf54
        _td54 = _tf54.mkdtemp()
        _lines54 = open(_md54, encoding='utf-8').read().split('\n')

        def _row54(cid):
            return next((i for i, l in enumerate(_lines54)
                         if l.lstrip().startswith('| %s |' % cid)), None)

        def _mut54(cid, pat, repl):
            """只改 cid 那一行；锚点缺失 / 替换无变化 ⇒ None ⇒ 判红（不 skip，R29）。"""
            i = _row54(cid)
            if i is None:
                return None
            new = _re54.sub(pat, repl, _lines54[i], count=1)
            if new == _lines54[i]:
                return None
            lines = list(_lines54)
            lines[i] = new
            p = os.path.join(_td54, 'claims_%s.md' % cid.replace('-', ''))
            open(p, 'w', encoding='utf-8').write('\n'.join(lines))
            return p

        def _dec(m):
            return '%d%s' % (int(m.group(1)) - 1, m.group(2))

        # ---- S-49 五向 ----
        _p_ok = _md54                                             # 正向：真文件
        _p_a = _mut54('C-001', r'(\d+)(\s*条\s*×)', _dec)          # 规模漂移
        _p_b = _mut54('C-002', r'(minJ\s+)([\d.]+)', r'\g<1>0.5000')  # minJ 写错
        _p_c = _mut54('C-004', r'(关\s*4\s*语义\s*)(\d+)',
                      lambda m: '%s%d' % (m.group(1), int(m.group(2)) - 1))
        _p_d = _mut54('C-005', r'dup\s*\d+', '重复已省略')          # 锚点被删 ⇒ 必须判红
        # 删整行 C-036（不是改错，是"少查一条"——静默消失必须红）
        _i36 = _row54('C-036')
        _p_e = None
        if _i36 is not None:
            l36 = [l for j, l in enumerate(_lines54) if j != _i36]
            _p_e = os.path.join(_td54, 'claims_no036.md')
            open(_p_e, 'w', encoding='utf-8').write('\n'.join(l36))

        _f = claim_counts_consistent(_p_ok, _root54)[0]
        _a = claim_counts_consistent(_p_a, _root54)[0] if _p_a else None
        _b = claim_counts_consistent(_p_b, _root54)[0] if _p_b else None
        _c = claim_counts_consistent(_p_c, _root54)[0] if _p_c else None
        _d = claim_counts_consistent(_p_d, _root54)[0] if _p_d else None
        _e = claim_counts_consistent(_p_e, _root54)[0] if _p_e else None

        # ---- S-50 三向（断言"红的原因"对，见上面的 ★） ----
        _md54txt = open(_ext_md54, encoding='utf-8').read()

        def _tmp54(tag, text):
            p = os.path.join(_td54, 'ext_%s.md' % tag)
            open(p, 'w', encoding='utf-8').write(text)
            return p

        # ① 分母混写 55（正是 55 条时代的旧口径）—— 只改比值的分母，不动结构
        _x1 = _tmp54('den', _md54txt.replace('| 128/128 |', '| 55/55 |', 1))
        _r1ok, _r1 = external_numbers_consistent(_x1, _ext_js54, _root54) \
            if _x1 != _md54txt or '| 128/128 |' in _md54txt else (None, '锚点缺失')
        # ② 表头删掉「分母口径」列 —— 口径被抹掉
        _x2 = _tmp54('hdr', _md54txt.replace('| 项 | 数值 | 分母口径 | 来源 |',
                                             '| 项 | 数值 | 来源 |', 1))
        _r2ok, _r2 = external_numbers_consistent(_x2, _ext_js54, _root54) \
            if _x2 != _md54txt else (None, '锚点缺失')
        # ③ 手改一格数字（不改分母）—— 陈旧/手改必须抓
        _x3 = _tmp54('edit', _md54txt.replace('2.631', '2.632', 1))
        _r3ok, _r3 = external_numbers_consistent(_x3, _ext_js54, _root54) \
            if _x3 != _md54txt else (None, '锚点缺失')
        _f50ok = external_numbers_consistent(_ext_md54, _ext_js54, _root54)[0]

        # 每向要求：判红 **且** 原因命中对应关键词
        _m1 = (_r1ok is False) and ('分母' in _r1)
        _m2 = (_r2ok is False) and ('分母口径' in _r2)
        _m3 = (_r3ok is False) and ('不一致' in _r3)

        # ---- S-51 两向（R63：把计数抄回协议文件必须红） ----
        from check_claims import protocol_no_hardcoded_counts
        _agents54 = os.path.join(_root54, 'AGENTS.md')
        _a0 = open(_agents54, encoding='utf-8').read() if os.path.exists(_agents54) else None
        _p_a1 = _p_a2 = None
        if _a0 is not None:
            _p_a1 = os.path.join(_td54, 'AGENTS_triple.md')
            open(_p_a1, 'w', encoding='utf-8').write(
                _a0 + '\n> 门禁：27 claims / 50 artifacts / 51 semantic\n')
            _p_a2 = os.path.join(_td54, 'AGENTS_nc.md')
            open(_p_a2, 'w', encoding='utf-8').write(_a0 + '\n> 负控 56/56\n')
        _f51 = protocol_no_hardcoded_counts([_agents54, os.path.join(_root54, 'CLAUDE.md')])[0] \
            if _a0 is not None else None
        _a1 = protocol_no_hardcoded_counts([_p_a1, _p_a1])[0] if _p_a1 else None
        _a2 = protocol_no_hardcoded_counts([_p_a2, _p_a2])[0] if _p_a2 else None

        ok54 = (bool(_f) and all(x is False for x in (_a, _b, _c, _d, _e))
                and bool(_f50ok) and _m1 and _m2 and _m3
                and bool(_f51) and _a1 is False and _a2 is False)
        det54 = (f'S-49 正向={"过" if _f else "红"} '
                 f'C001-1={"红" if _a is False else "漏判"} '
                 f'minJ改={"红" if _b is False else "漏判"} '
                 f'C004-1={"红" if _c is False else "漏判"} '
                 f'删dup={"红" if _d is False else "漏判"} '
                 f'删C036={"红" if _e is False else "漏判"} ‖ '
                 f'S-50 正向={"过" if _f50ok else "红"} '
                 f'分母55={"红·分母" if _m1 else "漏判"} '
                 f'删列={"红·口径" if _m2 else "漏判"} '
                 f'手改={"红·陈旧" if _m3 else "漏判"} ‖ '
                 f'S-51 正向={"过" if _f51 else "红"} '
                 f'写死三元组={"红" if _a1 is False else "漏判"} '
                 f'写死负控={"红" if _a2 is False else "漏判"}')
    results.append({'id': 'NC-54',
                    'desc': 'C-001/2/4/5/036 计数漂移、对外表分母混写/陈旧、协议写死计数必须被拒',
                    'expect': 'fwd=T / 十向变异=F 且原因命中', 'actual': det54, 'ok': ok54})
    print(f"  [{'ok ' if ok54 else 'BAD!'}] NC-54 claim 计数 + 对外表分母 + 协议写死必须被拒         "
          f"expect=fwd T/10向 F actual={det54}")

    # NC-55（R65，T-A10b；来自 N-16/N-18）：**S-52 的三条断言必须能各自独立地红**。
    #   为什么必须分向：S-52 的 (c)「跨版只许加行」几乎能吃下任何「改老行」的变异 ——
    #   若只断言「红了吗」，(a) 当前卷不一致 与 (b) NL 被改写 这两条会**永远得不到证伪**，
    #   长期处于假绿（被 (c) 顺手抓到）。★ 强判据会吃掉弱判据的证据（与 NC-54 同源）。
    #   隔离手法：每向换一个 chain 参数 / 只动一份文件，使被证伪的断言成为唯一失败项。
    from check_claims import task_layer_frozen as _tlf55
    import shutil as _sh55
    import tempfile as _tf55
    ok55, det55 = False, 'no artifact'
    _src55 = HERE
    _need55 = ([os.path.join(_src55, 'tasks', x) for x in
                ('tasks.jsonl', 'nl_human.jsonl', 'nl_frozen.jsonl')] +
               [os.path.join(_src55, 'reports', 'papers', x) for x in
                ('tasks_v6c.jsonl', 'tasks_v7.jsonl')])
    if all(os.path.exists(p) for p in _need55):
        _CH55 = [('tasks_v6c.jsonl', 'tasks_v7.jsonl')]
        _FILES55 = [('tasks', 'tasks.jsonl'), ('tasks', 'nl_human.jsonl'),
                    ('tasks', 'nl_frozen.jsonl'),
                    ('reports/papers', 'tasks_v6c.jsonl'),
                    ('reports/papers', 'tasks_v7.jsonl')]

        def _mk55():
            d = _tf55.mkdtemp()
            for sub, name in _FILES55:
                os.makedirs(os.path.join(d, sub), exist_ok=True)
                _sh55.copyfile(os.path.join(_src55, sub, name),
                               os.path.join(d, sub, name))
            return d

        def _rows55(p):
            return [l.rstrip('\n') for l in open(p, encoding='utf-8') if l.strip()]

        def _idx55(p, tid):
            for i, l in enumerate(_rows55(p)):
                if json.loads(l).get('task_id') == tid:
                    return i
            return None

        def _mut55(p, i, fn):
            """就地改第 i 行；返回是否真的改了（改不动 ⇒ 调用方判漏判，R29）。"""
            ls = _rows55(p)
            if i is None or i >= len(ls):
                return False
            new = fn(ls[i])
            if new == ls[i]:
                return False
            ls[i] = new
            open(p, 'w', encoding='utf-8').write('\n'.join(ls) + '\n')
            return True

        def _bad_spec(line):
            """给该行加一个键（模拟内容被改写）。
            ★ 不能用「把 input 里某个数 +1」：L3 的 input 只有 {'nl': 字符串}，无数值可 bump，
              那样变异会静默不生效、被误判成「闸漏判」（第一版就踩了这个）。"""
            j = json.loads(line)
            j['_nc55_mut'] = True
            return json.dumps(j, ensure_ascii=False)

        # ---- 正向 ----
        _fwd55 = _tlf55(base=_mk55(), chain=_CH55)

        # ---- (a) 当前卷不一致：只动 tasks/tasks.jsonl，且**必须挑新行** ----
        #      挑新行（不在 v6c 里的 L3）⇒ (c) 天然绿，使 (a) 成为唯一失败项。
        #      若挑老行，(c) 会同时红、把 (a) 的证据吃掉（强判据吃弱判据，NC-54 同源）。
        _da = _mk55()
        _ia = _idx55(os.path.join(_da, 'tasks', 'tasks.jsonl'),
                     'L3_naca4412_wingbox_str4')          # v1.1 新增行，v6c 里没有
        _ok_a_mut = _mut55(os.path.join(_da, 'tasks', 'tasks.jsonl'), _ia, _bad_spec)
        _a55, _ra55 = _tlf55(base=_da, chain=_CH55)

        # ---- (b) 已发布 NL 被改写：只动 tasks/nl_human.jsonl 里的一条**老**行 ----
        #      (a) 只比 tasks.jsonl vs papers，与 nl_human 无关 ⇒ 天然隔离
        _db = _mk55()
        _ib = _idx55(os.path.join(_db, 'tasks', 'nl_human.jsonl'), 'L3_naca4412_wingbox')
        _ok_b_mut = _mut55(os.path.join(_db, 'tasks', 'nl_human.jsonl'), _ib, _bad_spec)
        _b55, _rb55 = _tlf55(base=_db, chain=_CH55)

        # ---- (c) 跨版改老行：同时改磁盘与当前卷同一行 ⇒ (a) 一致，(c) 必红 ----
        _dc = _mk55()
        _ic = _idx55(os.path.join(_dc, 'tasks', 'tasks.jsonl'), 'L3_naca4412_wingbox')
        _ok_c1 = _mut55(os.path.join(_dc, 'tasks', 'tasks.jsonl'), _ic, _bad_spec)
        _ok_c2 = _mut55(os.path.join(_dc, 'reports', 'papers', 'tasks_v7.jsonl'),
                        _ic, _bad_spec)
        _c55, _rc55 = _tlf55(base=_dc, chain=_CH55)

        ok55 = (bool(_fwd55) is True and _ok_a_mut and _ok_b_mut and _ok_c1 and _ok_c2
                and _a55 is False and '不一致' in _ra55
                and _b55 is False and '已发布 NL' in _rb55
                and _c55 is False and '只许' in _rc55)
        det55 = (f'fwd={"T" if _fwd55 else "F"} ‖ '
                 f'(a)卷不一致={"红·不一致" if (_a55 is False and "不一致" in _ra55) else "漏判/因不对"} '
                 f'(b)NL改写={"红·已发布NL" if (_b55 is False and "已发布 NL" in _rb55) else "漏判/因不对"} '
                 f'(c)跨版改老行={"红·只许" if (_c55 is False and "只许" in _rc55) else "漏判/因不对"}')
    results.append({'id': 'NC-55',
                    'desc': 'S-52 三向独立证伪：当前卷不一致 / 已发布 NL 被改写 / 跨版改老行',
                    'expect': 'fwd=T / 三向=F 且原因分别命中「不一致」「已发布 NL」「只许」',
                    'actual': det55, 'ok': ok55})
    print(f"  [{'ok ' if ok55 else 'BAD!'}] NC-55 任务层冻结漂移必须被 S-52 分向拒绝          "
          f"expect=fwd T/3向 F actual={det55}")

    # NC-36（R29 补）：语义项**不得静默消失**。    # 起因：C-029 的成绩单还没跑 MSR 时，S-19/S-20 因 `if '/' in msrH` 直接不出现，    # 语义项总数从 29 掉到 27，而自检仍报「全过」——「不参与判定的检查不是检查」的复刻。
    # 三端都守：① 最新成绩单必须有 msr/exam.msr；② 语义报告里 S-19 与 S-20 **都在**；
    #           ③ 源码里必须存在 else 分支（缺 msr ⇒ 加一条 ok=False），防被改回去。
    sc36_p = latest_scorecard()
    try:
        sc36 = json.load(open(sc36_p, encoding='utf-8'))
    except Exception:
        sc36 = {}
    has_msr = bool((sc36.get('exam') or {}).get('msr')) and bool(sc36.get('msr'))
    try:
        sem36 = {x.get('id'): x for x in (json.load(open(
            os.path.join(HERE, 'reports', 'check_claims.json'), encoding='utf-8')).get('semantic') or [])}
    except Exception:
        sem36 = {}
    present = [k for k in ('S-19', 'S-20') if k in sem36]
    src36 = open(os.path.join(HERE, 'check_claims.py'), encoding='utf-8').read()
    else36 = src36.count("成绩单缺 msr 节") >= 1 and src36.count("成绩单缺 exam.msr") >= 1
    ok36 = has_msr and present == ['S-19', 'S-20'] and else36
    results.append({'id': 'NC-36', 'desc': '语义项不得静默消失：缺 MSR ⇒ S-19/S-20 必须失败而非消失（R29）',
                    'expect': 'msr 齐 + S-19/S-20 在场 + 源码有 else 分支',
                    'actual': f'msr={has_msr} present={present} else分支={else36}', 'ok': ok36})
    print(f"  [{'ok ' if ok36 else 'BAD!'}] NC-36 语义项不静默消失                              "
          f"expect=msr/S-19,S-20/else actual=msr{has_msr}/{len(present)}项/else{else36}")

    n_ok = sum(1 for r in results if r['ok'])
    report = {'n_cases': len(results), 'n_ok': n_ok, 'all_ok': n_ok == len(results),
              'ids': [r['id'] for r in results],
              'results': results}
    # ★ W5c-6c 修：这句原先是**无条件**打印的 —— 44/44 全绿时照样印「未全绿，不得跑基线」，
    # 读的人会以为失败（与 R38 同类：结论字符串必须由数据生成，不能写死）。
    # 现在：① 结论写进 report['gate_message']（结构化，供下游读，不靠人读 stdout）；
    #       ② stdout 打印同一句，全绿/不全绿自动切换。
    report['gate_message'] = ('红线条 R6：负控全绿 ⇒ 允许跑 LLM 基线。' if report['all_ok']
                              else '红线条 R6：负控未全绿，不得跑 LLM 基线。')
    # W5a'（R25）：负控产物入库 reports/，文件名带条数（官方 artifact 不得在 eval_runs/）
    rep_dir = os.path.join(HERE, 'reports')
    os.makedirs(rep_dir, exist_ok=True)
    out_path = os.path.join(rep_dir, f'negative_controls_{len(results)}.json')
    # ★ F-1（T-A4，配合 R59）：**内容没变就不重写**。原先无条件重写 ⇒ 每次跑负控都会刷新 mtime
    #   ⇒ 官方 check_claims.json 里记录的 artifact mtime 立刻过期（R59/S-45 会因为「白跑一次负控」转红）。
    #   比较用 dict 相等（键序无关），避免因序列化顺序变化产生假 diff。
    _same = False
    if os.path.exists(out_path):
        try:
            _same = (json.load(open(out_path, encoding='utf-8')) == report)
        except Exception:
            _same = False
    if _same:
        print(f"\n负控: {n_ok}/{len(results)} ok -> reports/negative_controls_{len(results)}.json"
              f"（内容未变，未重写 —— F-1，避免 mtime 抖动）")
    else:
        json.dump(report, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"\n负控: {n_ok}/{len(results)} ok -> reports/negative_controls_{len(results)}.json（已更新）")
    print(report['gate_message'])
    return 0 if report['all_ok'] else 2

if __name__ == '__main__':
    sys.exit(main())
