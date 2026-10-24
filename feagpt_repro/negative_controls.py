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
