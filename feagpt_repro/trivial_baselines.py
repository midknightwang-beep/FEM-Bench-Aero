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
from score_baseline import stratum_of, is_exam_legacy, is_exam_full
from _paths import rel   # T-A11a：跨盘符安全（见 _paths.py）

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

def _mode_merge(vals):
    """逐字段众数合并（W5c-5b / R44）。vals = 同层候选值列表。

    全 dict ⇒ 递归到子键（子键只在出现过的值里取众数）；否则取 JSON 规范化后
    出现最多的值。**平局按 key 字典序取第一** —— 保证同一输入两次跑结果一致
    （否则 Counter.most_common 的字典序不稳定，artifact 不可复现）。
    """
    if not vals:
        return None
    if all(isinstance(v, dict) for v in vals):
        out = {}
        for k in sorted(set().union(*[set(v) for v in vals])):
            out[k] = _mode_merge([v[k] for v in vals if k in v])
        return out
    c = collections.Counter(json.dumps(v, sort_keys=True, ensure_ascii=False) for v in vals)
    best = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return json.loads(best)

def field_hit_rate(sf):
    """字段级命中率 —— 用于量化「地板离通过还有多远」。

    ★ 为什么必须报这个：spec_fidelity 是**全或无**（任一字段 FAIL ⇒ 整条 FAIL）。
    地板在 exam 上恰为 0 时，「0」本身不含信息——可能差 1 个字段，也可能全错。
    命中率把「0 是判据严格性的必然」与「地板真的没用」区分开。
    分母取 n_fields_gated（剔除 REPORTED_MATERIAL 这类恒 pass 的「只报不判」项）。
    """
    n = sf.get('n_fields_gated') or sf.get('n_fields') or 0
    if not n:
        return None, 0
    return (n - (sf.get('n_fail') or 0)) / n, n

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
    # ★ T-A11a：exam 判据改用共享函数。原写法 `stratum_of(t) is not None` 在 v7 上
    #   会把 9 条 `interpolation_v11` 当成 legacy exam（地板分母 25→34，与 C-032 不同分母）。
    exam_flags = [is_exam_legacy(t) for t in tasks]
    exam_flags_full = [is_exam_full(t) for t in tasks]
    train = [t for t in tasks if t['split_v2'] == 'train' and stratum_of(t) is None]
    test = [t for t in tasks if t['split_v2'] in ('boundary_holdout', 'extrapolation_test',
                                                   'interpolation_test')]

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
    # W5c-5（专家第八轮 §3.6 / R40）：**必须 leave-one-out**。
    # 旧版检索库含目标自身 ⇒ train 的 12/13「通过」全是 T1_nn == task_id（把题面自己检索回来），
    # 地板 92.3% 是稻草人，value_added 的 Δ≥10 被判据本身满足。现把自身从候选集剔除。
    train_vecs = [(t, spec_vec(gold_of(t), t['family'])) for t in train]
    t1_pass, t1_hits = [], []
    for t in tasks:
        g = gold_of(t)
        v = spec_vec(g, t['family'])
        same_fam = [(tt, dist(vv, v)) for tt, vv in train_vecs
                    if tt['family'] == t['family'] and tt['task_id'] != t['task_id']]
        if not same_fam:
            t1_pass.append(False); t1_hits.append(None); continue
        nn, d = min(same_fam, key=lambda x: x[1])
        nn_spec = gold_of(nn)
        sf = judge(nn_spec, g, t)
        t1_pass.append(sf['pass'])
        t1_hits.append({'nn': nn['task_id'], 'dist': round(d, 4),
                        'self_hit': nn['task_id'] == t['task_id']})

    # ---- T1+：family-mode 地板（W5c-5b / 专家第九轮 §3.3 / R44）----
    # 问题：T1（逐任务 LOO 最近邻）在 exam 上恰为 0/25 ⇒ value_added 的对照是 0 地板，
    #       技术上 PASS、科学上不硬。T1 为什么会 0？因为 spec_fidelity 是**全或无**，
    #       同族不同参的 spec 必然有多字段不符。⇒ 需要两个更强的参照：
    #   ① T1plus_family（可实现、不读输入）：对每个族取 **逐字段众数** 组装成一个 spec，
    #      族内所有任务都用它判分。比 T0（整条 spec 众数）细一档：几何参数各取众数，
    #      材料/分析这类族内常数会命中 ⇒ 这是「不读输入」能拿到的最强地板。
    #      ★ 众数只在 **train 池** 上取（R7 检索库口径），exam 任务只被评、不参与取众数。
    #   ② T1plus_family_oracle（不可实现，只报不判）：每任务在同族 train spec 池里任取
    #      一个能通过的 ⇒ 族内池的**覆盖力上界**。它高说明「族内已存在答案」，但需知道
    #      答案才能选，故不能当基线用，只用来诊断题库是否过窄。
    fam_pool = collections.defaultdict(list)       # family -> [(task, gold spec)]（仅 train 池）
    for t in train:
        fam_pool[t['family']].append((t, gold_of(t)))
    fam_mode_spec = {f: _mode_merge([sp for _, sp in v]) for f, v in fam_pool.items()}

    t1p_pass, t1p_hit = [], []
    t1p_or_pass, t1p_or_wit = [], []
    for t in tasks:
        g = gold_of(t)
        msp = fam_mode_spec.get(t['family'])
        if msp is None:
            t1p_pass.append(False); t1p_hit.append(None)
        else:
            sf = judge(msp, g, t)
            t1p_pass.append(sf['pass'])
            hr, nf = field_hit_rate(sf)
            t1p_hit.append({'hit_rate': round(hr, 4) if hr is not None else None,
                            'n_gated_fields': nf, 'n_fail': sf.get('n_fail')})
        # oracle 上界：同族 train spec 池（排除目标自身任务）里任取一个能通过的
        hit = None
        for tt, sp in fam_pool.get(t['family'], []):
            if tt['task_id'] == t['task_id']:
                continue          # leave-one-out（R40）
            if judge(sp, g, t)['pass']:
                hit = tt['task_id']
                break
        t1p_or_pass.append(hit is not None); t1p_or_wit.append(hit)

    # ---- T2：gold 上界（评测器自检）----
    t2_pass = []
    for t in tasks:
        sf = judge(gold_of(t), gold_of(t), t)
        t2_pass.append(sf['pass'])

    # ---- 汇总（考卷 = exam_stratum 非空；老考卷回退 boundary+extrap；train 池单列）----
    exam_idx = [i for i, f in enumerate(exam_flags) if f]            # legacy 三栏（主口径）
    # ★ T-A11a：分栏必须按 **full** 遍历，否则 `interpolation_v11` 栏永远为空、
    #   四栏加起来 25 而 exam_full 是 34（静默漏 9 条）。
    exam_idx_full = [i for i, f in enumerate(exam_flags_full) if f]
    # 检索库/众数池：既非 legacy 也非 v11（等价于老写法，但语义直说）
    train_idx = [i for i, t in enumerate(tasks)
                 if t['split_v2'] == 'train' and not is_exam_full(t)]

    def rate(passes, idx):
        return (sum(passes[i] for i in idx), len(idx))

    report = {'note': f'平凡基线地板（levels={levels}, eng_layer={eng_layer}）。'
                      '考卷 = exam_stratum ∈ 三栏（legacy，与 C-032 同分母；'
                      '老考卷无该字段则 boundary_holdout+extrapolation_test）；'
                      'v7 起另有 interpolation_v11 一栏并列（exam_full，C-037 双分母、R54 只禁相减）。'
                      '检索库/众数池已排除考卷任务（W5b-3b：内插题 split_v2 仍是 train，不排除会检索到自己）。'
                      '★ W5c-5/R40：T1 已 leave-one-out（检索库剔除目标自身）——旧版 train 12/13 全是自命中。'
                      '★ W5c-5b/R44：新增 T1plus_family（逐字段族级众数，不读输入，可用于 value_added 判据）'
                      ' 与 T1plus_family_oracle（族内 train 池覆盖力**上界**，不可实现 ⇒ 只报不判）。'
                      'value_added = TSR_LLM − TSR_T1* ≥ 10 pp 才算 LLM 真有增量（T1* = T1 与 T1+ 取高者，最保守）。',
              'tasks_path': rel(os.path.abspath(tasks_path)),
              'n_tasks': len(tasks), 'n_exam': len(exam_idx), 'n_train_pool': len(train),
              't0_families_missing': fam_missing, 't1_leave_one_out': True,
              'T0_constant': {}, 'T1_retrieval': {}, 'T1plus_family': {},
              'T1plus_family_oracle': {}, 'T2_gold': {}, 'per_task': []}
    for name, passes in (('T0_constant', t0_pass), ('T1_retrieval', t1_pass),
                         ('T1plus_family', t1p_pass), ('T1plus_family_oracle', t1p_or_pass),
                         ('T2_gold', t2_pass)):
        ep, en = rate(passes, exam_idx)
        tp, tn = rate(passes, train_idx)
        rec = {'exam_tsr': f'{ep}/{en}', 'exam_pct': round(100*ep/max(1, en), 1),
               'train_tsr': f'{tp}/{tn}', 'all_pct': round(100*sum(passes)/max(1, len(passes)), 1),
               'by_stratum': {}, 'train_by_family': {}}
        # ★ T-A11a：遍历四栏（含 interpolation_v11）。若只遍历三栏，v7 会
        #   「四栏明细加起来 25 而 exam 报 34」——静默漏 9 条（R-A5）。
        for s in ('boundary', 'extrapolation', 'interpolation', 'interpolation_v11'):
            si = [i for i in exam_idx_full if stratum_of(tasks[i]) == s]
            p_, n_ = rate(passes, si)
            if n_:
                rec['by_stratum'][s] = {'tsr': f'{p_}/{n_}', 'pct': round(100*p_/n_, 1),
                                        'note': '分栏 n 小，只报不判（R12）'}
        # W5c-5：train 族级地板（value_added 必须对 per-family 非自检索地板比对）
        for fam in sorted({tasks[i]['family'] for i in train_idx}):
            fi = [i for i in train_idx if tasks[i]['family'] == fam]
            p_, n_ = rate(passes, fi)
            rec['train_by_family'][fam] = {'tsr': f'{p_}/{n_}', 'pct': round(100*p_/max(1, n_), 1)}
        report[name] = rec
    # ── T1+ 附加诊断（W5c-5b）───────────────────────────────────────────────
    # ① 字段级命中率：spec_fidelity 全或无，地板 0 条时「0」本身不含信息；
    #    命中率区分「差几个字段」与「完全没命中」。
    hrs = [t1p_hit[i]['hit_rate'] for i in exam_idx
           if t1p_hit[i] and t1p_hit[i]['hit_rate'] is not None]
    report['T1plus_family']['avg_field_hit_rate_exam'] = (
        round(sum(hrs) / len(hrs), 4) if hrs else None)
    report['T1plus_family']['n_fields_gated'] = (
        round(sum(t1p_hit[i]['n_gated_fields'] for i in exam_idx
                  if t1p_hit[i] and t1p_hit[i]['n_gated_fields']) /
              max(1, len([i for i in exam_idx
                          if t1p_hit[i] and t1p_hit[i]['n_gated_fields']])), 1)
        if exam_idx else None)
    report['T1plus_family']['families_missing'] = sorted(
        {t['family'] for t in tasks} - set(fam_mode_spec))
    report['T1plus_family']['oracle_witness_exam'] = (
        f'{sum(1 for i in exam_idx if t1p_or_wit[i])}/{len(exam_idx)}')
    # ② 缺口分布：地板「差几个受判字段才过」。全或无判分下这是 0 地板的唯一量化含义。
    fails_ = [t1p_hit[i]['n_fail'] for i in exam_idx
              if t1p_hit[i] and t1p_hit[i].get('n_fail') is not None]
    if fails_:
        fails_sorted = sorted(fails_)
        report['T1plus_family']['n_fail_exam'] = {
            'min': fails_sorted[0],
            'median': fails_sorted[len(fails_sorted) // 2],
            'max': fails_sorted[-1],
            'n_with_0_fail(T1+ 通过)': sum(1 for x in fails_ if x == 0)}
    report['T1plus_family_oracle']['note'] = (
        '不可实现上界：需知道目标答案才能从族内池里选对 ⇒ 只报不判，'
        '仅用于诊断「族内 train 池是否已覆盖该任务」')
    for i, t in enumerate(tasks):
        report['per_task'].append({'task_id': t['task_id'], 'split_v2': t['split_v2'],
                                   'exam_stratum': stratum_of(t), 'is_exam': exam_flags[i],
                                   'is_exam_full': exam_flags_full[i],
                                   'family': t['family'],
                                   'T0': t0_pass[i], 'T1': t1_pass[i],
                                   'T1_nn': (t1_hits[i] or {}).get('nn') if t1_hits[i] else None,
                                   'T1_self_hit': bool((t1_hits[i] or {}).get('self_hit')),
                                   'T1plus': t1p_pass[i],
                                   'T1plus_field_hit': (t1p_hit[i] or {}).get('hit_rate'),
                                   'T1plus_oracle': t1p_or_pass[i],
                                   'T1plus_oracle_witness': t1p_or_wit[i]})

    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, out_name)
    json.dump(report, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'== 平凡基线地板（levels={levels}；exam {len(exam_idx)} 条 / 检索库 {len(train)} 条）==')
    for name in ('T0_constant', 'T1_retrieval', 'T1plus_family',
                 'T1plus_family_oracle', 'T2_gold'):
        r = report[name]
        print(f"  {name:22s} 考卷 TSR {r['exam_tsr']} ({r['exam_pct']}%)   全量 {r['all_pct']}%")
        for s, v in r['by_stratum'].items():
            print(f"     - {s:<14} {v['tsr']} ({v['pct']}%)")
    t1p = report['T1plus_family']
    print(f"\n  T1+ 字段级命中率（exam 均值）= {t1p.get('avg_field_hit_rate_exam')} "
          f"（{t1p.get('n_fields_gated')} 个受判字段，全或无判分）")
    print(f"  T1+ 族内 oracle 覆盖力上界 = {t1p.get('oracle_witness_exam')}（只报不判）")
    if t1p.get('families_missing'):
        print(f"  [WARN] T1+ 无族内 train 池 ⇒ 记 FAIL 的族：{t1p['families_missing']}")
    t0, t1 = report['T0_constant'], report['T1_retrieval']
    if fam_missing:
        print(f"\n[WARN] 以下族没有 train 池 ⇒ T0 无从猜（记 FAIL）、T1 无参照（记 FAIL）：{fam_missing}")
        print('       成因：内插留出把该族 train 抽空（RUBRIC §1.1 已预告此代价）')
    floor_name, floor_pct = max((('T1', t1['exam_pct']), ('T1+', t1p['exam_pct'])),
                                key=lambda x: x[1])
    print(f"\n泄漏检查: T0 考卷 {t0['exam_pct']}% —— 高则说明边界留出任务可被先验猜中")
    print(f"背诵线:   T1 考卷 {t1['exam_pct']}% / T1+ 考卷 {t1p['exam_pct']}% "
          f"⇒ 对照取高者 {floor_name} = {floor_pct}%")
    print(f"          LLM value_added 必须 >= 10 pp（即 exam TSR >= {floor_pct+10:.0f}%）")
    print('report ->', out)
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
