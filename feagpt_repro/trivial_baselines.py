# -*- coding: utf-8 -*-
"""
trivial_baselines.py — T0/T1/T2 平凡基线（专家第二轮 6.3.1：没有地板，就没有资格谈提升）

T0 常数基线：对每个任务输出 train 里最常见的 spec（不读输入）——测泄漏与先验；T0 高 = 题目泄漏
T1 检索基线：从 train 取最近邻 spec（同族优先 + 参数向量 L2 距离）——测"是否只是背诵"
T2 gold 上界：数据集规范化 spec——上界 100%，验证评测器

判分：spec_fidelity 闸（skip_solve 快通道，秒级）。成绩单 eval_runs/trivial_baselines.json。
红线 R7：T1 的检索库只用 train（split_v2=train），不得含 boundary_holdout/extrapolation_test/val。
"""
import json, os, sys, collections, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluate import evaluate_one, spec_fidelity, load_tasks, FEA, RUNS

def spec_vec(spec, family):
    """参数向量（数值型，用于 T1 最近邻距离）。"""
    a = spec.get('airfoil', {}) if family == 'wingbox' else spec.get('structure', {}).get('params', {})
    return {k: float(v) for k, v in a.items() if isinstance(v, (int, float))}

def dist(v1, v2):
    keys = set(v1) | set(v2)
    # 归一化：每键按全局幅度（用两向量较大绝对值）
    s = 0.0
    for k in keys:
        scale = max(1.0, abs(v1.get(k, 0)), abs(v2.get(k, 0)))
        s += ((v1.get(k, 0) - v2.get(k, 0)) / scale) ** 2
    return math.sqrt(s)

def main():
    ap_args = sys.argv[1:]
    def get(k, d):
        return ap_args[ap_args.index(k) + 1] if k in ap_args else d
    levels = get('--levels', 'L1').split(',')
    out_name = get('--out', 'trivial_baselines.json')
    eng_layer = 'L3' in levels   # W4d：L3 走工程层口径（配置层只报、死字段豁免）

    tasks = [t for t in load_tasks(os.path.join(HERE, 'tasks', 'tasks.jsonl'))
             if t['input_level'] in levels]
    train = [t for t in tasks if t['split_v2'] == 'train']
    test = [t for t in tasks if t['split_v2'] in ('boundary_holdout', 'extrapolation_test')]

    # gold specs
    def gold_of(t):
        cid = t['task_id'].replace('L1_', '').replace('L3_', '')
        s = json.load(open(os.path.join(FEA, 'modeling', cid, 'spec.json'), encoding='utf-8'))
        s.pop('workdir', None)
        return s

    def judge(cand, gold, t):
        return spec_fidelity(cand, gold, t['family'], engineering_layer=eng_layer)

    # ---- T0：train 众数 spec（按族取最常见参数组合，不读任何输入）----
    fam_of_task = {}
    combo_count = collections.Counter()
    for t in train:
        g = gold_of(t)
        combo_count[(t['family'], json.dumps(g, sort_keys=True))] += 1
        fam_of_task[t['family']] = g
    t0_spec_by_fam = {}
    for fam in fam_of_task:
        best = max((c for c in combo_count if c[0] == fam), key=lambda c: combo_count[c])
        t0_spec_by_fam[fam] = json.loads(best[1])
    # T0 计分：对每个任务，候选 = 其族的众数 spec
    t0_pass = []
    for t in tasks:
        cand = copy.deepcopy(t0_spec_by_fam[t['family']]) if (copy := __import__('copy')) else None
        cand.pop('workdir', None)
        gold = gold_of(t)
        sf = judge(cand, gold, t)
        t0_pass.append(sf['pass'])

    # ---- T1：最近邻检索（检索库 = train only，红线 R7）----
    train_vecs = [(t, spec_vec(gold_of(t), t['family'])) for t in train]
    t1_pass, t1_hits = [], []
    for t in tasks:
        g = gold_of(t)
        v = spec_vec(g, t['family'])
        same_fam = [(tt, dist(vv, v)) for tt, vv in train_vecs if tt['family'] == t['family']]
        if not same_fam:
            t1_pass.append(False); t1_hits.append(None); continue
        nn, d = min(same_fam, key=lambda x: x[1])
        nn_spec = gold_of(nn)
        sf = judge(nn_spec, g, t)
        t1_pass.append(sf['pass'])
        t1_hits.append({'nn': nn['task_id'], 'dist': round(d, 4)})

    # ---- T2：gold 上界（评测器自检）----
    t2_pass = []
    for t in tasks:
        sf = judge(gold_of(t), gold_of(t), t)
        t2_pass.append(sf['pass'])

    # ---- 汇总（考卷 = boundary_holdout + extrapolation_test；train 单列）----
    def tsr(passes, subset):
        idx = [i for i, t in enumerate(tasks) if t['split_v2'] in subset]
        return (sum(passes[i] for i in idx), len(idx))

    report = {'note': f'平凡基线地板（levels={levels}, eng_layer={eng_layer}）。考卷 = boundary_holdout + extrapolation_test；'
                      'value_added = TSR_LLM − TSR_T1 ≥ 10 pp 才算 LLM 真有增量。',
              'T0_constant': {}, 'T1_retrieval': {}, 'T2_gold': {}, 'per_task': []}
    for name, passes in (('T0_constant', t0_pass), ('T1_retrieval', t1_pass), ('T2_gold', t2_pass)):
        exam_p, exam_n = tsr(passes, ('boundary_holdout', 'extrapolation_test'))
        train_p, train_n = tsr(passes, ('train',))
        all_p = sum(passes)
        report[name] = {'exam_tsr': f'{exam_p}/{exam_n}', 'exam_pct': round(100*exam_p/max(1,exam_n), 1),
                        'train_tsr': f'{train_p}/{train_n}', 'all_pct': round(100*all_p/len(passes), 1)}
    for i, t in enumerate(tasks):
        report['per_task'].append({'task_id': t['task_id'], 'split_v2': t['split_v2'],
                                   'family': t['family'],
                                   'T0': t0_pass[i], 'T1': t1_pass[i],
                                   'T1_nn': (t1_hits[i] or {}).get('nn') if t1_hits[i] else None})

    out = os.path.join(RUNS, out_name)
    os.makedirs(RUNS, exist_ok=True)
    json.dump(report, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'== 平凡基线地板（levels={levels}）==')
    for name in ('T0_constant', 'T1_retrieval', 'T2_gold'):
        r = report[name]
        print(f"  {name:14s} 考卷 TSR {r['exam_tsr']} ({r['exam_pct']}%)   全量 {r['all_pct']}%")
    t0, t1 = report['T0_constant'], report['T1_retrieval']
    print(f"\n泄漏检查: T0 考卷 {t0['exam_pct']}% —— 高则说明边界留出任务可被先验猜中")
    print(f"背诵线:   T1 考卷 {t1['exam_pct']}% —— LLM 基线 value_added 必须 ≥ 10 pp（≥ {t1['exam_pct']+10:.0f}%）")
    print('report ->', out)
    return 0

if __name__ == '__main__':
    main()
