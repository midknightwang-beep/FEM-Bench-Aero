# -*- coding: utf-8 -*-
"""
trivial_baselines.py — T0/T1/T2 平凡基线（专家第二轮 6.3.1：没有地板，就没有资格谈提升）

T0 常数基线：对每个任务输出 train 里最常见的 spec（不读输入）——测泄漏与先验；T0 高 = 题目泄漏
T1 检索基线：从 train 取最近邻 spec（同族优先 + 参数向量 L2 距离）——测"是否只是背诵"
T2 gold 上界：数据集规范化 spec——上界 100%，验证评测器

判分：spec_fidelity 闸（skip_solve 快通道，秒级）。成绩单 eval_runs/trivial_baselines.json。
红线 R7：T1 的检索库只用 train（split_v2=train），不得含 boundary_holdout/extrapolation_test/val。

W5b-3b（专家第七轮后续，★ 关键修正）：
  v6 的 6 条内插考卷 **split_v2 仍是 train**（只多一个 `exam_stratum`）。若检索库照旧取
  `split_v2 == 'train'`，**T1 会检索到它自己**（gold spec 逐字段相同、距离 0）⇒ interp 栏地板
  100%，value_added 被算成负数——这不是模型差，是检索库漏了考卷。
  故：① 检索库/众数池 = `split_v2=='train'` **且 `exam_stratum` 为空**；
      ② exam 判据改用 `stratum_of`（认 exam_stratum，v4/v5 无字段则回退 split，向后兼容）；
      ③ 三栏各出一份地板（分栏 n 小，只报不判）。
"""
import json, os, sys, collections, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluate import evaluate_one, spec_fidelity, load_tasks, FEA, RUNS
from score_baseline import stratum_of

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
    out_dir = get('--out-dir', RUNS)
    tasks_path = get('--tasks', os.path.join(HERE, 'tasks', 'tasks.jsonl'))
    eng_layer = 'L3' in levels   # W4d：L3 走工程层口径（配置层只报、死字段豁免）

    tasks = [t for t in load_tasks(tasks_path) if t['input_level'] in levels]
    # ★ W5b-3b：考卷任务即使 split_v2=='train'（内插留出）也不得进检索库/众数池
    exam_flags = [stratum_of(t) is not None for t in tasks]
    train = [t for t in tasks if t['split_v2'] == 'train' and stratum_of(t) is None]
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
    # ★ W5b-3b：内插留出可能把某族的 train 抽空（v6 实测 open_hole_panel 2→0）⇒
    #   该族没有「先验众数」可猜，T0 记 False（并记进 t0_families_missing），不得 KeyError 崩掉。
    t0_pass = []
    fam_missing = sorted({t['family'] for t in tasks} - set(t0_spec_by_fam))
    for t in tasks:
        spec0 = t0_spec_by_fam.get(t['family'])
        if spec0 is None:
            t0_pass.append(False)
            continue
        cand = copy.deepcopy(spec0) if (copy := __import__('copy')) else None
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

    # ---- 汇总（考卷 = exam_stratum 非空；老考卷回退 boundary+extrap；train 池单列）----
    exam_idx = [i for i, f in enumerate(exam_flags) if f]
    train_idx = [i for i, t in enumerate(tasks) if t['split_v2'] == 'train' and stratum_of(t) is None]

    def rate(passes, idx):
        return (sum(passes[i] for i in idx), len(idx))

    report = {'note': f'平凡基线地板（levels={levels}, eng_layer={eng_layer}）。考卷 = exam_stratum 非空'
                      '（v6 三栏；老考卷无该字段则 boundary_holdout+extrapolation_test）。'
                      '检索库/众数池已排除考卷任务（W5b-3b：内插题 split_v2 仍是 train，不排除会检索到自己）。'
                      'value_added = TSR_LLM − TSR_T1 ≥ 10 pp 才算 LLM 真有增量。',
              'tasks_path': os.path.relpath(os.path.abspath(tasks_path), HERE).replace('\\', '/'),
              'n_tasks': len(tasks), 'n_exam': len(exam_idx), 'n_train_pool': len(train),
              't0_families_missing': fam_missing,
              'T0_constant': {}, 'T1_retrieval': {}, 'T2_gold': {}, 'per_task': []}
    for name, passes in (('T0_constant', t0_pass), ('T1_retrieval', t1_pass), ('T2_gold', t2_pass)):
        ep, en = rate(passes, exam_idx)
        tp, tn = rate(passes, train_idx)
        rec = {'exam_tsr': f'{ep}/{en}', 'exam_pct': round(100*ep/max(1, en), 1),
               'train_tsr': f'{tp}/{tn}', 'all_pct': round(100*sum(passes)/max(1, len(passes)), 1),
               'by_stratum': {}}
        for s in ('boundary', 'extrapolation', 'interpolation'):
            si = [i for i in exam_idx if stratum_of(tasks[i]) == s]
            p_, n_ = rate(passes, si)
            if n_:
                rec['by_stratum'][s] = {'tsr': f'{p_}/{n_}', 'pct': round(100*p_/n_, 1),
                                        'note': '分栏 n 小，只报不判（R12）'}
        report[name] = rec
    for i, t in enumerate(tasks):
        report['per_task'].append({'task_id': t['task_id'], 'split_v2': t['split_v2'],
                                   'exam_stratum': stratum_of(t), 'is_exam': exam_flags[i],
                                   'family': t['family'],
                                   'T0': t0_pass[i], 'T1': t1_pass[i],
                                   'T1_nn': (t1_hits[i] or {}).get('nn') if t1_hits[i] else None})

    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, out_name)
    json.dump(report, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'== 平凡基线地板（levels={levels}；exam {len(exam_idx)} 条 / 检索库 {len(train)} 条）==')
    for name in ('T0_constant', 'T1_retrieval', 'T2_gold'):
        r = report[name]
        print(f"  {name:14s} 考卷 TSR {r['exam_tsr']} ({r['exam_pct']}%)   全量 {r['all_pct']}%")
        for s, v in r['by_stratum'].items():
            print(f"     - {s:<14} {v['tsr']} ({v['pct']}%)")
    t0, t1 = report['T0_constant'], report['T1_retrieval']
    if fam_missing:
        print(f"\n[WARN] 以下族没有 train 池 ⇒ T0 无从猜（记 FAIL）、T1 无参照（记 FAIL）：{fam_missing}")
        print('       成因：内插留出把该族 train 抽空（RUBRIC §1.1 已预告此代价）')
    print(f"\n泄漏检查: T0 考卷 {t0['exam_pct']}% —— 高则说明边界留出任务可被先验猜中")
    print(f"背诵线:   T1 考卷 {t1['exam_pct']}% —— LLM 基线 value_added 必须 >= 10 pp（>= {t1['exam_pct']+10:.0f}%）")
    print('report ->', out)
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
