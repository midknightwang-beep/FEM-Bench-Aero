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
    # NC-27（P1-5/R29）：文本数字漂移必须被语义检查抓到——注入 C-010「140 行」，artifact 仍 165。
    # 先断言替换真的命中：W5a 的教训是「替换没命中却记 PASS」= 静默空转的负控。
    real_md = open(os.path.join(ROOT_, 'FEM-Bench-Aero', 'CLAIMS.md'), encoding='utf-8').read()
    mut_md = real_md.replace('任务层 **165 行**', '任务层 140 行')
    hit27 = (mut_md != real_md)
    rc27, o27 = run_check_claims(mut_md, 'nc27')
    ok27 = hit27 and rc27 != 0 and 'S-01' in o27
    results.append({'id': 'NC-27', 'desc': '文本计数漂移（C-010 140 vs artifact 165）⇒ 语义检查 FAIL',
                    'expect': 'rc!=0 + 报 S-01', 'actual': f'hit={hit27} rc={rc27}', 'ok': ok27})
    print(f"  [{'ok ' if ok27 else 'BAD!'}] NC-27 文本计数漂移被语义检查抓到                    "
          f"expect=rc!=0+S-01 actual=hit={hit27} rc{rc27}")

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

    # NC-36（R29 补）：语义项**不得静默消失**。
    # 起因：C-029 的成绩单还没跑 MSR 时，S-19/S-20 因 `if '/' in msrH` 直接不出现，
    # 语义项总数从 29 掉到 27，而自检仍报「全过」——「不参与判定的检查不是检查」的复刻。
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
    # W5a'（R25）：负控产物入库 reports/，文件名带条数（官方 artifact 不得在 eval_runs/）
    rep_dir = os.path.join(HERE, 'reports')
    os.makedirs(rep_dir, exist_ok=True)
    out_path = os.path.join(rep_dir, f'negative_controls_{len(results)}.json')
    json.dump(report, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\n负控: {n_ok}/{len(results)} ok -> reports/negative_controls_{len(results)}.json")
    print('红线条 R6：负控未全绿，不得跑 LLM 基线。')
    return 0 if report['all_ok'] else 2

if __name__ == '__main__':
    sys.exit(main())
