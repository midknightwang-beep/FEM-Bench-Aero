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
FID_TOL_PCT = 1.0     # 辅助闸：max_disp 相对偏差（只证"算得像"，不再承担"答案正确"——W4a 纠偏 3.1）
FLOAT_TOL = 1e-6      # spec_fidelity 浮点相对容差（W4a 纠偏 P0-1）

# 字段级真值表（按族）。整数/枚举/字符串/数组：精确相等；浮点：相对误差 < 1e-6。
GRADED_FIELDS = {
    'wingbox': ('airfoil', ['code', 'chord', 'span', 'skin_thickness', 'n_ribs',
                            'rib_thickness', 'spar_chordwise', 'n_stringers_per_skin',
                            'stringer_height', 'stringer_thickness', 'stringer_kind',
                            'stringer_flange_width', 'tip_chord_ratio', 'sweep_deg',
                            'web_chordwise']),
    'open_hole_panel': ('params', ['length', 'width', 'thickness', 'hole_d',
                                   'hole_x', 'hole_y', 'layup']),
    'fuselage_barrel': ('params', ['diameter', 'length', 'thickness',
                                   'n_stringers', 'n_frames']),
    'stiffened_panel': ('params', ['length', 'width', 'thickness', 'n_stringers']),
}
GRADED_MATERIAL = ['name', 'youngs_modulus', 'poisson_ratio']          # 必判
REPORTED_MATERIAL = ['density', 'yield_strength']                      # 只报不判


def _field_equal(a, b):
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_field_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
            and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) <= FLOAT_TOL * max(1.0, abs(float(b)))
    return a == b


def spec_fidelity(cand_spec, gold_spec, family, input_mesh_keys=None, input_load_keys=None):
    """W4a P0-1：字段级真值校验（强制闸）。任一字段 FAIL ⇒ 整体 FAIL。"""
    fields = []
    holder_key, keys = GRADED_FIELDS.get(family, ('params', []))
    cand_holder = (cand_spec.get('airfoil', {}) if holder_key == 'airfoil'
                   else cand_spec.get('structure', {}).get('params', {}))
    gold_holder = (gold_spec.get('airfoil', {}) if holder_key == 'airfoil'
                   else gold_spec.get('structure', {}).get('params', {}))
    for k in keys:
        cv, gv = cand_holder.get(k, '<missing>'), gold_holder.get(k, '<missing>')
        if cv == '<missing>' and gv == '<missing>':
            ok = True          # 双方一致缺省（可选字段，如 hole_x 仅偏心孔有）= 一致
        elif cv == '<missing>' or gv == '<missing>':
            ok = False         # 单边缺 = 不一致
        else:
            ok = _field_equal(cv, gv)
        fields.append({'field': f'{holder_key}.{k}', 'expected': gv, 'actual': cv, 'pass': ok})
    # 结构族与材料必判项
    for label, path in (('structure.family', ('structure', 'family')),):
        cv = cand_spec.get(path[0], {}).get(path[1], '<missing>')
        gv = gold_spec.get(path[0], {}).get(path[1], '<missing>')
        fields.append({'field': label, 'expected': gv, 'actual': cv, 'pass': cv == gv})
    for k in GRADED_MATERIAL:
        cv = cand_spec.get('material', {}).get(k, '<missing>')
        gv = gold_spec.get('material', {}).get(k, '<missing>')
        fields.append({'field': f'material.{k}', 'expected': gv, 'actual': cv,
                       'pass': _field_equal(cv, gv) if cv != '<missing>' else False})
    for k in REPORTED_MATERIAL:   # 只报不判（声明）
        cv = cand_spec.get('material', {}).get(k)
        gv = gold_spec.get('material', {}).get(k)
        fields.append({'field': f'material.{k}', 'expected': gv, 'actual': cv,
                       'pass': True, 'reported_not_gated': True})
    # 网格与载荷（W4a NC-4/NC-5）。W4b 修正：mesh 双键名问题——任务输入给了什么键就考什么键
    # （gold 的 pipeline 内部键如 algorithm_2d/min_jacobian 任务没给 LLM，考了就是考「猜内部默认值」）。
    for holder, input_keys in (('mesh', input_mesh_keys), ('load', input_load_keys)):
        ch, gh = cand_spec.get(holder, {}), gold_spec.get(holder, {})
        # 键名别名归一（任务输入键 vs gold 内部键）
        MESH_ALIASES = {'order': 'element_order', 'refine_le': 'refine_at_leading_edge',
                        'size_chord': 'size_chord', 'size_span': 'size_span'}
        judge_keys = input_keys if input_keys else sorted(set(ch) & set(gh))
        for k in judge_keys:
            gk = MESH_ALIASES.get(k, k) if holder == 'mesh' else k
            ck = k if k in ch else (MESH_ALIASES.get(k) if MESH_ALIASES.get(k) in ch else k)
            cv = ch.get(ck, ch.get(gk, '<missing>'))
            gv = gh.get(gk, gh.get(k, '<missing>'))
            if cv == '<missing>' and gv == '<missing>':
                ok = True
            elif cv == '<missing>' or gv == '<missing>':
                ok = False
            else:
                ok = _field_equal(cv, gv)
            fields.append({'field': f'{holder}.{k}', 'expected': gv, 'actual': cv, 'pass': ok})
    fails = [f for f in fields if not f['pass']]
    return {'pass': not fails, 'n_fields': len(fields), 'n_fail': len(fails),
            'failed': fails[:15]}


def load_tasks(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def gold_spec_path(case_id):
    return os.path.join(FEA, 'modeling', case_id, 'spec.json')


def _input_mesh_load_keys(task):
    """任务输入里 mesh/load 出现过的键（考什么判什么；gold 内部默认键不考）。"""
    norm = task.get('input', {}).get('spec_normalized', {})
    return (sorted(norm.get('mesh', {}).keys()), sorted(norm.get('load', {}).keys()))


def evaluate_one(task, cand_spec_path, out_root=RUNS, timeout=1800, skip_solve=False):
    task_id = task['task_id']
    run_dir = os.path.join(out_root, task_id)
    os.makedirs(run_dir, exist_ok=True)
    result = {'task_id': task_id, 'family': task['family'],
              'split_v2': task['split_v2'], 'input_level': task['input_level'],
              'candidate_spec': cand_spec_path, 'gates': {}, 'overall_pass': False}

    if skip_solve:
        # 负控快通道：只跑 spec_fidelity（字段级真值），不起求解器
        case_id = (task['task_id'].replace('L1_', '').replace('L2_', '').replace('L3_', '')
                   .replace('_final', '').replace('cand_', ''))
        gold_spec_path = os.path.join(FEA, 'modeling', case_id, 'spec.json')
        if os.path.exists(gold_spec_path):
            gold_spec = json.load(open(gold_spec_path, encoding='utf-8'))
            gold_spec.pop('workdir', None)
            cand_json = json.load(open(cand_spec_path, encoding='utf-8'))
            if 'spec' in cand_json and 'structure' not in cand_json:
                cand_json = cand_json['spec'] or {}   # gen_candidates 包装结构解包
            cand_json.pop('workdir', None)
            mk, lk = _input_mesh_load_keys(task)
            sf = spec_fidelity(cand_json, gold_spec, task['family'], input_mesh_keys=mk, input_load_keys=lk)
        else:
            sf = {'pass': False, 'n_fields': 0, 'n_fail': 1,
                  'failed': [{'field': 'gold spec', 'expected': gold_spec_path, 'actual': 'missing'}]}
        sf['field'] = 'spec_fidelity (field-level, mandatory, skip-solve)'
        sf['expected'] = 'all graded fields equal (float tol 1e-6)'
        sf['actual'] = f"{sf['n_fields'] - sf['n_fail']}/{sf['n_fields']} fields"
        result['gates']['spec_fidelity'] = sf
        result['overall_pass'] = sf['pass']
        out_path = os.path.join(run_dir, 'evaluation.json')
        json.dump(result, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return result

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

    # ---- 4. 物理保真：max_disp vs 数据集真值（辅助闸，W4a 降级：只证"算得像"）----
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

    # ---- 4b. spec_fidelity 字段级真值（W4a P0-1 强制闸）----
    case_id = task['task_id']
    case_id = case_id.replace('L1_', '').replace('L2_', '').replace('L3_', '') \
                     .replace('_final', '').replace('cand_', '')
    gold_spec_path = os.path.join(FEA, 'modeling', case_id, 'spec.json')
    if os.path.exists(gold_spec_path):
        gold_spec = json.load(open(gold_spec_path, encoding='utf-8'))
        gold_spec.pop('workdir', None)
        cand_json = json.load(open(cand_spec_path, encoding='utf-8'))
        if 'spec' in cand_json and 'structure' not in cand_json:
            cand_json = cand_json['spec'] or {}   # gen_candidates 包装结构解包
        cand_json.pop('workdir', None)
        mk, lk = _input_mesh_load_keys(task)
        sf = spec_fidelity(cand_json, gold_spec, task['family'], input_mesh_keys=mk, input_load_keys=lk)
        sf['field'] = 'spec_fidelity (field-level, mandatory)'
        sf['expected'] = 'all graded fields equal (float tol 1e-6)'
        sf['actual'] = f"{sf['n_fields'] - sf['n_fail']}/{sf['n_fields']} fields"
        result['gates']['spec_fidelity'] = sf
    else:
        result['gates']['spec_fidelity'] = {'pass': False, 'field': 'gold spec',
                                            'expected': gold_spec_path, 'actual': 'missing'}

    # ---- 5. 总判定 ----
    result['overall_pass'] = all(g['pass'] for g in result['gates'].values())
    out_path = os.path.join(run_dir, 'evaluation.json')
    json.dump(result, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    result['evaluation_json'] = out_path
    return result


def evaluate_clarification(task, clar_path, out_root=RUNS, timeout=1800):
    """L2 评测（W3-2）：clarify_then_semantics 闸 + final_spec 三闸。

    clarification.json 协议（candidate 提交）：
      {"task_id": ..., "questions": [{"field": "rib_thickness", "question": "..."}],
       "final_spec": {...补全后的完整 spec...}}
    判分：
      clarify 闸 —— expected_clarifications 里每个缺字段都必须被【显式提问】；
                    若 final_spec 静默填了值而没提问 => FAIL（考「追问」不考「猜」）。
      其余闸    —— 对 final_spec 走 L1 同款三闸（跑 pipeline）。
    """
    task_id = task['task_id']
    clar = json.load(open(clar_path, encoding='utf-8'))
    run_dir = os.path.join(out_root, task_id)
    os.makedirs(run_dir, exist_ok=True)
    result = {'task_id': task_id, 'input_level': 'L2',
              'split_v2': task['split_v2'], 'gates': {}, 'overall_pass': False}

    expected = task.get('expected_clarifications', [])
    asked = {q.get('field') for q in clar.get('questions', []) if isinstance(q, dict)}
    missing_ask = [f for f in expected if f not in asked]
    final_spec = clar.get('final_spec')

    # clarify 闸：缺字段要么被问、要么 final_spec 里【确实没有】该字段（等待用户给）；
    # 静默编造默认值 = FAIL。
    silent = []
    for f in expected:
        if f in asked:
            continue
        # final_spec 是否偷偷补了值？
        a = final_spec.get('airfoil', {}) if isinstance(final_spec, dict) else {}
        p = (final_spec.get('structure', {}) or {}).get('params', {}) if isinstance(final_spec, dict) else {}
        if f in a or f in p:
            silent.append(f)
    result['gates']['clarify'] = {
        'pass': len(missing_ask) == 0 and len(silent) == 0,
        'field': 'expected_clarifications',
        'expected': f'ask about {expected}',
        'actual': f'asked={sorted(asked)} silent_default={silent}',
        'missing_ask': missing_ask, 'silent_default': silent}
    result['clarification_json'] = clar_path

    # final_spec 落盘走 L1 同款三闸；clarify 已 FAIL 则短路（不浪费求解时间）
    if isinstance(final_spec, dict) and result['gates']['clarify']['pass']:
        spec_path = os.path.join(run_dir, 'final_spec.json')
        final_spec.setdefault('name', task['task_id'].replace('L2_', 'cand_', 1))
        json.dump(final_spec, open(spec_path, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        sub = evaluate_one({**task, 'input_level': 'L2-final', 'task_id': task_id + '_final'},
                           spec_path, out_root=out_root, timeout=timeout)
        result['gates'].update(sub['gates'])
        result['gates'].pop('pipeline', None) if sub['gates'].get('pipeline', {}).get('pass', True) else None
        result['fidelity_disp_dev_pct'] = sub.get('fidelity_disp_dev_pct')
        result['overall_pass'] = all(g['pass'] for g in result['gates'].values())
    else:
        result['overall_pass'] = False

    out_path = os.path.join(run_dir, 'evaluation.json')
    json.dump(result, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
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
        t = tasks[args.task_id]
        if t['input_level'] == 'L2':
            r = evaluate_clarification(t, args.spec)   # --spec 传 clarification.json
        else:
            r = evaluate_one(t, args.spec)
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
        if t['input_level'] == 'L2' and args.use_gold:
            # 理想 candidate：显式提问全部缺字段 + final_spec = 规范化 gold 补全
            expected = t.get('expected_clarifications', [])
            clar = {'task_id': t['task_id'],
                    'questions': [{'field': f, 'question': f'请给出 {f}？'} for f in expected],
                    'final_spec': t['input']['spec_normalized']}
            cand = os.path.join(HERE, 'tasks', f'_clar_{t["task_id"]}.json')
            json.dump(clar, open(cand, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            r = evaluate_clarification(t, cand)
        elif args.use_gold:
            cand = args.spec
            norm = t['input'].get('spec_normalized') or t['input'].get('spec_normalized_from_nl')
            if norm:
                cand = os.path.join(HERE, 'tasks', f'_cand_{t["task_id"]}.json')
                norm = dict(norm)
                norm.setdefault('name', t['task_id'])
                json.dump(norm, open(cand, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            r = evaluate_one(t, cand)
        else:
            cand = args.spec
            r = evaluate_one(t, cand)
        print(f'--- {t["task_id"]} ({t["input_level"]}) ---')
        flag = 'PASS' if r['overall_pass'] else 'FAIL'
        n_pass += r['overall_pass']
        gsum = {k: v['pass'] for k, v in r['gates'].items()}
        print(f'  [{flag}] gates={gsum} '
              f'fidelity={r.get("fidelity_disp_dev_pct", "n/a")}% wall={r.get("wall_seconds")}s')
    print(f'\nTSR = {n_pass}/{len(sel)}')
    sys.exit(0)


if __name__ == '__main__':
    main()
