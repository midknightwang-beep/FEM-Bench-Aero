# -*- coding: utf-8 -*-
"""
evaluate.py — FEM-Bench-Aero 评测器（ROADMAP W2-2，A1 题型最小闭环）

输入：候选 spec.json（A1：NL→FEASpec 的产物）
流程：run_pipeline(ccx) → 关1 网格(batch_summary.min_quality)
      → 关4 语义(topology.compare，复用 feagpt.topology，零逻辑复制)
      → 物理保真(max_disp 相对数据集真值，判据口径对齐双码 <1%)
输出：eval_runs/<task_id>/evaluation.json（逐闸四元组：字段/期望/实测/结论）

用法：
  python evaluate.py --task-id L1_naca4412_wingbox --spec cand.json
  python evaluate.py --batch --tasks tasks/tasks.jsonl --levels L1 --limit 3 --use-gold
      （--use-gold：用数据集规范化 spec 当候选，冒烟用）
"""
import json, os, sys, subprocess, argparse, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FEA = os.path.join(ROOT, 'FEM-Bench-Aero')
RUNS = os.path.join(HERE, 'eval_runs')
PY = sys.executable

MIN_J = 0.30          # 关1 判据（D10）
FID_TOL_PCT = 1.0     # 保真判据：max_disp 相对偏差 <1%（双码位移口径）


def load_tasks(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def gold_spec_path(case_id):
    return os.path.join(FEA, 'modeling', case_id, 'spec.json')


def evaluate_one(task, cand_spec_path, out_root=RUNS, timeout=1800):
    task_id = task['task_id']
    run_dir = os.path.join(out_root, task_id)
    os.makedirs(run_dir, exist_ok=True)
    result = {'task_id': task_id, 'family': task['family'],
              'split_v2': task['split_v2'], 'input_level': task['input_level'],
              'candidate_spec': cand_spec_path, 'gates': {}, 'overall_pass': False}

    # ---- 1. 跑 pipeline（ccx 全链）----
    t0 = time.time()
    proc = subprocess.run(
        [PY, os.path.join(HERE, 'run_pipeline.py'),
         '--spec', cand_spec_path, '--out', run_dir, '--solver', 'ccx'],
        capture_output=True, text=True, timeout=timeout, cwd=HERE)
    result['pipeline_rc'] = proc.returncode
    result['wall_seconds'] = round(time.time() - t0, 1)
    if proc.returncode != 0:
        result['gates']['pipeline'] = {
            'pass': False, 'field': 'run_pipeline', 'expected': 'rc=0',
            'actual': f'rc={proc.returncode}',
            'detail': (proc.stdout[-800:] + '\n' + proc.stderr[-800:])[-1200:]}
        return result

    # ---- 2. 读 batch_summary → 关1 网格 ----
    bs = json.load(open(os.path.join(run_dir, 'batch_summary.json'), encoding='utf-8'))
    entry = bs[0] if isinstance(bs, list) else bs
    mesh = entry.get('mesh') or {}
    min_q = mesh.get('min_quality')
    result['gates']['mesh_quality'] = {
        'pass': bool(entry.get('ok')) and min_q is not None and min_q >= MIN_J,
        'field': 'mesh.min_quality', 'expected': f'>= {MIN_J}',
        'actual': min_q, 'n_tri3': mesh.get('n_tri3'),
        'n_nodes': (mesh.get('node_count') or (mesh.get('element_types') and None))}

    # ---- 3. 关4 语义（复用 topology.compare，零逻辑复制）----
    case_name = entry.get('name')
    truth_path = os.path.join(run_dir, case_name, f'{case_name}.truth.json')
    if not os.path.exists(truth_path):
        result['gates']['semantics'] = {'pass': False, 'field': 'truth.json',
                                        'expected': 'exists', 'actual': 'missing'}
        return result
    truth = json.load(open(truth_path, encoding='utf-8'))
    topo = truth.get('topology')
    if not topo:
        result['gates']['semantics'] = {'pass': False, 'field': 'topology',
                                        'expected': 'present', 'actual': 'absent'}
        return result
    sys.path.insert(0, HERE)
    from feagpt import topology as topo_mod
    gate4 = topo_mod.compare(topo)
    fails = [c for c in gate4['checks'] if not c['pass']]
    result['gates']['semantics'] = {
        'pass': bool(gate4['pass']), 'field': 'topology.compare',
        'expected': f"{len(gate4['checks'])} checks pass",
        'actual': f"{len(gate4['checks']) - len(fails)}/{len(gate4['checks'])}",
        'failed_checks': [{'key': c['key'], 'expected': c['expected'],
                           'actual': c['actual']} for c in fails][:10]}

    # ---- 4. 物理保真：max_disp vs 数据集真值 ----
    ref = json.load(open(os.path.join(FEA, task['truth_ref']), encoding='utf-8'))
    cand_disp = (truth.get('scalars') or {}).get('max_disp')
    gold_disp = (ref.get('scalars') or {}).get('max_disp')
    if cand_disp is None or gold_disp in (None, 0):
        result['gates']['fidelity_disp'] = {'pass': False, 'field': 'scalars.max_disp',
                                            'expected': gold_disp, 'actual': cand_disp}
    else:
        dev_pct = abs(cand_disp - gold_disp) / abs(gold_disp) * 100.0
        result['gates']['fidelity_disp'] = {
            'pass': dev_pct < FID_TOL_PCT, 'field': 'scalars.max_disp',
            'expected': f'{gold_disp:.6f} ±{FID_TOL_PCT}%', 'actual': f'{cand_disp:.6f}',
            'dev_pct': round(dev_pct, 4)}
        result['fidelity_disp_dev_pct'] = round(dev_pct, 4)

    # ---- 5. 总判定 ----
    result['overall_pass'] = all(g['pass'] for g in result['gates'].values())
    out_path = os.path.join(run_dir, 'evaluation.json')
    json.dump(result, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    result['evaluation_json'] = out_path
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-id')
    ap.add_argument('--spec')
    ap.add_argument('--batch', action='store_true')
    ap.add_argument('--tasks', default=os.path.join(HERE, 'tasks', 'tasks.jsonl'))
    ap.add_argument('--levels', default='L1', help='逗号分隔：L1,L2')
    ap.add_argument('--splits', default='id_test,extrapolation_test,train,val')
    ap.add_argument('--limit', type=int, default=3)
    ap.add_argument('--use-gold', action='store_true',
                    help='用数据集规范化 spec 冒烟（不产生真实 LLM 候选）')
    args = ap.parse_args()

    if not args.batch:
        if not (args.task_id and args.spec):
            ap.error('单任务模式需要 --task-id 与 --spec')
        tasks = {t['task_id']: t for t in load_tasks(args.tasks)}
        r = evaluate_one(tasks[args.task_id], args.spec)
        print(json.dumps(r, ensure_ascii=False, indent=1)[:2000])
        sys.exit(0 if r['overall_pass'] else 2)

    # 批量
    levels = set(args.levels.split(','))
    splits = set(args.splits.split(','))
    sel = [t for t in load_tasks(args.tasks)
           if t['input_level'] in levels and t['split_v2'] in splits]
    sel = sel[:args.limit]
    print(f'批量评测 {len(sel)} 条（levels={sorted(levels)} splits={sorted(splits)}）')
    n_pass = 0
    for t in sel:
        cand = args.spec
        if args.use_gold:
            cand = os.path.join(HERE, 'tasks', f'_cand_{t["task_id"]}.json')
            norm = t['input']['spec_normalized']
            norm.setdefault('name', t['task_id'].split('_', 1)[1] if '_' in t['task_id'] else t['task_id'])
            json.dump(norm, open(cand, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=1)
        print(f'--- {t["task_id"]} ---')
        r = evaluate_one(t, cand)
        flag = 'PASS' if r['overall_pass'] else 'FAIL'
        n_pass += r['overall_pass']
        gsum = {k: v['pass'] for k, v in r['gates'].items()}
        print(f'  [{flag}] gates={gsum} '
              f'fidelity={r.get("fidelity_disp_dev_pct", "n/a")}% wall={r.get("wall_seconds")}s')
    print(f'\nTSR = {n_pass}/{len(sel)}')
    sys.exit(0)


if __name__ == '__main__':
    main()
