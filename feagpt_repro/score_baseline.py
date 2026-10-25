# -*- coding: utf-8 -*-
"""
score_baseline.py — W4d L3 主基线成绩单（W4e 按专家第四轮修正：exam/dev 分栏）

四指标分层（红线 R9：SFR≠MSR≠TSR）：
  TSR（主 KPI，行为正确性）= 完备题 spec_fidelity PASS + 澄清题字段级问对（clarify_aliases，
        R17：单字关键词不得作为通过依据；含错族键名 clarify_wrong_keys ⇒ FAIL）
        —— 澄清题静默编造 spec = 0 分（拍板「问对=对，编造=错」）
  SFR（字段保真）= spec_fidelity PASS / 产出 spec 的候选
        —— R20（W4e）：fabricated ⇒ SFR FAIL（SFR 与 TSR 编造口径一致，不得并列矛盾报告）
  FPR（双向）= 该澄清不澄清（编造）/ 该答不答（过度澄清）
  MSR（全链可用率）见 msr 节（msr_l3.py 产出，红线 R14/R16）

W4e（专家第四轮 P0-1/R15）：headline 只用 exam = boundary_holdout + extrapolation_test；
train+val 单列 dev（开发/诊断），不进对外。underpowered = n_exam < 20（红线 R12）。
value_added = exam TSR_LLM − exam TSR_T1（地板同任务集 exam 口径，不用 all_pct）。

W5a'（专家第六轮 P0-1/P0-2/P1-8，红线 R25/R27）：
  - 输出默认写 reports/（**入库**，非 eval_runs/），文件名必须带版本；
  - --paper 记录考卷 provenance（tasks 路径 + sha256），成绩单自带溯源；
  - --candidates 默认 candidates_l3_v3，并在输出里显式记录实际目录（不再静默 v2）。
"""
import json, os, sys, hashlib, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluate import evaluate_one, load_tasks, RUNS, require_dataset

EXAM_SPLITS = ('boundary_holdout', 'extrapolation_test')
# W5b（RUBRIC §1.1，老王拍板）：exam 三栏——boundary / extrapolation 来自 dataset split，
# interpolation 是任务层内插留出（split_v2 仍为 train）。headline = 合并 25，三栏明细必须并列。
STRATA = ('boundary', 'extrapolation', 'interpolation')


def scorecard_coverage_problems(sc):
    """成绩单覆盖自检（W5b-3，专家第七轮 NC-28 / R31）。

    为什么：v6 考卷 55 条 L3，若候选只有 30 条（例如只跑了老题）就出成绩单，
    exam 会「看着 n=25、其实只有一部分被打分」，而且**不报错**——静默出半张成绩单。
    返回问题列表；空列表 = 覆盖完整。
    """
    probs = []
    prov = sc.get('provenance') or {}
    n_paper = sc.get('n_tasks_in_paper')
    n_cand = prov.get('n_candidates', sc.get('n_tasks'))
    miss = sc.get('candidates_missing') or []
    if n_paper is None:
        probs.append('成绩单缺 n_tasks_in_paper（旧版成绩单，无法判候选覆盖）')
    elif n_cand is None:
        probs.append('成绩单缺 provenance.n_candidates')
    elif n_cand < n_paper:
        probs.append(f'候选 {n_cand} < 考卷 {n_paper} 条（缺 {len(miss) or n_paper - n_cand} 条'
                     + (f'：{",".join(miss[:5])}{"..." if len(miss) > 5 else ""}' if miss else '') + '）')
    if sc.get('partial_candidates'):
        probs.append('partial_candidates=True（候选未覆盖全卷）')
    if sc.get('partial'):
        probs.append(f"partial=True（exam 实测 {sc.get('exam', {}).get('n')} < 期望 "
                     f"{sc.get('n_tasks_exam_expected')}）")
    return probs


def stratum_of(task):
    """任务的难度分层；老考卷（v4/v5）没有 exam_stratum ⇒ 回退到 split_v2 映射（向后兼容）。"""
    s = task.get('exam_stratum')
    if s:
        return s
    if task.get('split_v2') == 'boundary_holdout':        return 'boundary'
    if task.get('split_v2') == 'extrapolation_test':
        return 'extrapolation'
    # W5c（R36）：v6c 起内插留出在任务层是独立 split（旧卷只有 exam_stratum）
    if task.get('split_v2') == 'interpolation_test':
        return 'interpolation'
    return None

# R25：官方 artifact 一律写 reports/（被 git 追踪），eval_runs/ 只作工作目录
REPORT_DIR = os.path.join(HERE, 'reports')


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def judge_clarify_field_level(text, task):
    """字段级澄清判分（R17）。返回 (ok, detail)。

    规则（预注册于 RUBRIC.md）：
      - 必须【命中 expected 字段的别名】（clarify_aliases[field] 之一，含正确键名或语义短语）；
      - 且【不含错族键名】（clarify_wrong_keys——其他族的同义键，键名即契约 R19）。
    """
    aliases = task.get('clarify_aliases') or {}
    wrong = task.get('clarify_wrong_keys') or []
    fields = task.get('expected_clarifications') or []
    if not fields:
        return False, {'note': '任务未登记 expected_clarifications'}
    # 任务层两种形态兼容：dict(field→aliases) 或 list（与 expected_clarifications 逐位对齐）
    hit_wrong = [k for k in wrong if k in text] if isinstance(wrong, list) else \
        [k for k in (wrong if isinstance(wrong, list) else []) if k in text]
    detail = {'text': text[:200], 'expected': fields}
    if hit_wrong:
        detail['wrong_keys_hit'] = hit_wrong
        detail['note'] = '问题使用了错族键名（键名即契约，R19）'
        return False, detail
    per_field = {}
    ok_all = True
    for i, f in enumerate(fields):
        if isinstance(aliases, dict):
            al = aliases.get(f) or [f]
        else:
            # list 形态 = 该题别名全集（扁平 str 数组；单/多字段题共用一个池）
            al = aliases or [f]
        hit = [a for a in al if a in text]
        per_field[f] = hit
        if not hit:
            ok_all = False
    detail['alias_hits'] = per_field
    if not ok_all:
        detail['note'] = '存在 expected 字段未被任何别名命中'
    return ok_all, detail


def judge_l3_candidate(cand, task):
    """单条 L3 候选判类。返回 (category, pass_for_tsr, detail)。"""
    tid = task['task_id']
    ec = task.get('expected_clarifications') or []
    if cand.get('error'):
        return 'llm_error', False, {'detail': cand['error']}
    if cand.get('clarify') and not cand.get('spec'):
        if ec:
            ok, detail = judge_clarify_field_level(cand['clarify'], task)
            return ('clarify_ok' if ok else 'clarify_wrong'), ok, detail
        return 'clarify_wrong', False, {'clarify': cand['clarify'][:150],
                                        'note': '该答不答（信息完备却澄清）'}
    if cand.get('spec') and ec:
        return 'fabricated', False, {'note': f"澄清题静默编造 spec（缺 {ec}）",
                                     'expected_clarifications': ec}
    if cand.get('spec'):
        r = evaluate_one(task, cand['_path'], skip_solve=True)
        sf = r['gates'].get('spec_fidelity', {})
        failed = [f['field'] for f in (sf.get('failed') or [])]
        cat = 'spec_pass' if r['overall_pass'] else 'spec_fail'
        return cat, r['overall_pass'], {
            'n_fields': sf.get('n_fields'), 'n_fail': sf.get('n_fail'),
            'failed_fields': failed[:6],
            'exec_config_mismatch': len(sf.get('exec_config_mismatch') or []),
            'dead_fields_skipped': len(sf.get('dead_fields_skipped') or [])}
    return 'no_output', False, {'note': '3 轮修复未收敛（UNRESOLVED）'}


def agg(rows, key):
    """对 rows 子集聚合 tsr/sfr。"""
    n = len(rows)
    tsr_p = sum(1 for r in rows if r['tsr_pass'])
    spec_rows = [r for r in rows if r['category'] in ('spec_pass', 'spec_fail', 'fabricated')]
    # R20：fabricated 一律不计 SFR PASS（与 TSR 编造口径一致）
    sfr_p = sum(1 for r in spec_rows if r['category'] == 'spec_pass')
    return {'n': n,
            'tsr': {'pass': tsr_p, 'total': n, 'pct': round(100 * tsr_p / max(1, n), 1)},
            'sfr': {'pass': sfr_p, 'of_spec_candidates': len(spec_rows),
                    'pct': round(100 * sfr_p / max(1, len(spec_rows)), 1)},
            'categories': dict(collections.Counter(r['category'] for r in rows))}


def main():
    err = require_dataset()          # W5a'：缺 gold 数据集必须硬报错，不能静默算成 0/11
    if err:
        print('[dataset] ' + err)
        return 2
    argv = sys.argv[1:]
    def get(k, d):
        return argv[argv.index(k) + 1] if k in argv else d
    cand_dir = get('--candidates', os.path.join(HERE, 'candidates_l3_v3'))
    tasks_path = get('--tasks', os.path.join(HERE, 'tasks', 'tasks.jsonl'))
    report_dir = get('--report-dir', REPORT_DIR)
    report_path = get('--report', os.path.join(report_dir, 'baseline_scorecard_L3.json'))
    trivial_path = get('--trivial', os.path.join(report_dir, 'trivial_baselines_L3.json'))
    n_tasks_exam_arg = int(get('--n-tasks-exam', '0'))
    label = get('--label', '')
    os.makedirs(os.path.dirname(os.path.abspath(report_path)) or '.', exist_ok=True)
    print(f'[score_baseline] candidates={os.path.basename(cand_dir)}  tasks={tasks_path}')

    tasks = {t['task_id']: t for t in load_tasks(tasks_path)
             if t['input_level'] == 'L3'}
    # W5b：exam 期望条数从考卷自动推（硬编码 11 在扩到 25 条后会让 partial 判断失真）
    n_tasks_exam = n_tasks_exam_arg or sum(1 for t in tasks.values() if stratum_of(t) is not None)
    rows = []
    for fn in sorted(os.listdir(cand_dir)):
        if not fn.endswith('.json'):
            continue
        cand = json.load(open(os.path.join(cand_dir, fn), encoding='utf-8'))
        tid = cand.get('task_id')
        t = tasks.get(tid)
        if t is None:
            continue
        cand['_path'] = os.path.join(cand_dir, fn)
        cat, ok, detail = judge_l3_candidate(cand, t)
        st = stratum_of(t)
        rows.append({'task_id': tid, 'split_v2': t['split_v2'], 'family': t['family'],
                     'category': cat, 'tsr_pass': ok,
                     'exam_stratum': st, 'is_exam': st is not None,
                     'ec': bool(t.get('expected_clarifications')),
                     'turns_used': cand.get('turns_used'), **detail})

    exam_rows = [r for r in rows if r['is_exam']]
    dev_rows = [r for r in rows if not r['is_exam']]
    n_exam = len(exam_rows)

    fab = [r for r in rows if r['category'] == 'fabricated']
    clar_wrong = [r for r in rows if r['category'] == 'clarify_wrong']
    n_ec = sum(1 for r in rows if r['ec'])

    stratum_counts = collections.Counter(r['exam_stratum'] for r in exam_rows)
    fam_counts = collections.Counter(r['family'] for r in exam_rows)
    dev_split = collections.Counter(r['split_v2'] for r in dev_rows)
    turns_hist = collections.Counter(r['turns_used'] for r in rows if r.get('turns_used'))
    n_unresolved = sum(1 for r in rows if r['category'] == 'no_output')
    paper_tag = os.path.basename(tasks_path).replace('tasks_', '').replace('.jsonl', '')
    exam_ids = sorted(r['task_id'] for r in exam_rows)

    scorecard = {
        # W5c（专家第八轮 §3.7 / R38）：这三条字符串**必须由考卷推出来**，不得再硬编码 W4d 文案
        'note': (f'W5c L3 主基线（考卷 {paper_tag} × 候选 {os.path.basename(cand_dir)}，文案由考卷自动生成）：'
                 f'headline = exam {n_exam} 条（exam_stratum 三栏 '
                 f'boundary {stratum_counts.get("boundary", 0)} / extrapolation '
                 f'{stratum_counts.get("extrapolation", 0)} / interpolation '
                 f'{stratum_counts.get("interpolation", 0)}）；dev（非 exam）{len(dev_rows)} 条只作开发诊断。'
                 f'TSR=行为正确性（完备题答对+澄清题字段级问对 R17）；SFR=字段保真（R20：编造一律不计 PASS）；'
                 f'FPR 双向；MSR 全链见 msr 节（R14/R16/R35：solver 失败单列，不进 exam MSR）。'),
        'model': 'glm-5.3-flash',
        'decode': 'json_object + schema_task.json 校验 + 错误反馈修复循环（<=3 轮；SDK 无 logits 级 json_schema）',
        'exam_definition': (f'exam = exam_stratum 非空 = boundary {stratum_counts.get("boundary", 0)} '
                            f'+ extrapolation {stratum_counts.get("extrapolation", 0)} '
                            f'+ interpolation {stratum_counts.get("interpolation", 0)} = {n_exam}（RUBRIC §1.1；'
                            f'dev = 非 exam {len(dev_rows)} 条 = ' +
                            ' + '.join(f'{k} {v}' for k, v in sorted(dev_split.items())) + '）（R15/R36）'),
        # W5c（R39）：跨卷比较按 task-id 集，不按条数——条数相同也可能换了一批题
        'exam_task_ids_sha256': hashlib.sha256(
            json.dumps(exam_ids, ensure_ascii=False).encode('utf-8')).hexdigest(),
        'exam_by_family': dict(fam_counts),
        'turns_histogram': {str(k): v for k, v in sorted(turns_hist.items())},
        'first_pass_valid': turns_hist.get(1, 0),
        'n_unresolved': n_unresolved,
        'provenance': {   # W5a'（R25/R27）：成绩单自带溯源，替代「靠人记当时跑了什么」
            'label': label,
            'tasks_path': os.path.relpath(os.path.abspath(tasks_path), HERE).replace('\\', '/'),
            'tasks_sha256': sha256_file(tasks_path),
            'candidates_dir': os.path.relpath(os.path.abspath(cand_dir), HERE).replace('\\', '/'),
            'n_candidates': len(rows),
            'generated_by': 'score_baseline.py',
        },
        'n_tasks': len(rows),
        # W5b-3（专家第七轮 NC-28）：候选覆盖必须显式记账——v6 考卷 55 条，
        # 若只拿 30 条候选出成绩单，exam 会「看着 n=25、其实只有 13 条被打分」，
        # 而且不报错（静默出半张成绩单），比报错危险得多。
        'n_tasks_in_paper': len(tasks),
        'candidates_missing': sorted(set(tasks) - {r['task_id'] for r in rows}),
        'n_tasks_exam_expected': n_tasks_exam,
        'partial': n_exam < n_tasks_exam,
        'partial_candidates': len(rows) < len(tasks),
        'underpowered': n_exam < 20,
        'tsr': agg(rows, 'tsr')['tsr'],
        'exam': agg(exam_rows, 'exam'),
        'dev': {**agg(dev_rows, 'dev'), 'note': '开发集，不进对外（R15）'},
        'sfr_all': agg(rows, 'all')['sfr'],
        'fpr': {'fabricated_on_clarify_tasks': len(fab), 'n_clarify_tasks': n_ec,
                'fabrication_rate_pct': round(100 * len(fab) / max(1, n_ec), 1),
                'overclarify': len([r for r in clar_wrong if not r['ec']]),
                'clarify_wrong_field': len([r for r in clar_wrong if r['ec']])},
        'by_split': {s: agg([r for r in dev_rows if r['split_v2'] == s], s)
                     for s in sorted({r['split_v2'] for r in dev_rows})},
        # W5c（专家第八轮 §3.5 / S-24 / R36）：by_split 只统计**非 exam** 行。
        # 旧版把 6 条内插考题算进 train（n=19 = 13 纯 train + 6 内插），
        # 于是「train 15/19」既不是纯 train 也不是 exam，两不像。
        'by_split_note': (f'by_split 仅含非 exam 行（R36）；exam {n_exam} 条另见 exam_by_stratum。'
                          f'纯 train = {dev_split.get("train", 0)} 条。'),
        # W5b：exam 三栏明细（RUBRIC §1.1——合并报会虚高，必须拆开看难度）
        'exam_by_stratum': {s: agg([r for r in exam_rows if r['exam_stratum'] == s], s)
                            for s in STRATA if any(r['exam_stratum'] == s for r in exam_rows)},
        'per_task': rows,
    }

    # value_added（exam 口径，R15/P1-10：不再用 all_pct）
    if os.path.exists(trivial_path):
        trivial = json.load(open(trivial_path, encoding='utf-8'))
        t1_exam = trivial['T1_retrieval']['exam_pct']
        llm_exam = scorecard['exam']['tsr']['pct']
        scorecard['value_added'] = {
            'basis': f'exam 三栏 {n_exam} 条 TSR（T1 同任务集 exam_pct；T1 地板已 leave-one-out，R40）',
            'TSR_T1_exam_pct': t1_exam, 'TSR_LLM_exam_pct': llm_exam,
            'delta_pp': round(llm_exam - t1_exam, 1),
            'criterion': '>= 10 pp 才算 LLM 真有增量（专家 6.3.1）；n_exam<20 ⇒ underpowered 不得判 PASS（R12）',
            'verdict': ('PASS' if (llm_exam - t1_exam >= 10 and n_exam >= 20) else
                        'BELOW' if llm_exam - t1_exam < 10 else 'UNDERPOWERED')}

    # W5a：scorecard 重打分时保留既有 msr_section（MSR 由 msr_l3.py 单独产出，
    # 重打分不得抹掉；NC-22 依赖顶层 exam.msr 存在）
    prev_msr = None
    if os.path.exists(report_path):
        try:
            prev_msr = json.load(open(report_path, encoding='utf-8')).get('msr_section')
        except Exception:
            prev_msr = None
    if prev_msr:
        scorecard['msr_section'] = prev_msr
        # W5c：顶层 msr 也要一并保留 —— 此前顶层 `msr` 一直是 null（没人写），
        # 重打分后又会被写成缺省值，NC-36 因此报 msr=False。
        scorecard['msr'] = prev_msr.get('msr')
        scorecard['msr_pct'] = prev_msr.get('msr_pct')
        scorecard.setdefault('exam', {})['msr'] = prev_msr.get('exam_msr')
        scorecard.setdefault('dev', {})['msr'] = prev_msr.get('dev_msr')

    json.dump(scorecard, open(report_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    e = scorecard['exam']
    print('== L3 主基线成绩单（exam/dev 分栏，W4e）==')
    print(f"  EXAM  TSR {e['tsr']['pass']}/{e['n']} ({e['tsr']['pct']}%)  "
          f"SFR {e['sfr']['pass']}/{e['sfr']['of_spec_candidates']} ({e['sfr']['pct']}%)"
          f"   underpowered={scorecard['underpowered']}")
    d = scorecard['dev']
    print(f"  DEV   TSR {d['tsr']['pass']}/{d['n']} ({d['tsr']['pct']}%)  "
          f"SFR {d['sfr']['pass']}/{d['sfr']['of_spec_candidates']} ({d['sfr']['pct']}%)  (不进对外)")
    print(f"  分类(exam): {e['categories']}")
    for s, a in scorecard['exam_by_stratum'].items():
        print(f"  └ {s:<13} TSR {a['tsr']['pass']}/{a['n']} ({a['tsr']['pct']}%)"
              f"  SFR {a['sfr']['pass']}/{a['sfr']['of_spec_candidates']}")
    print(f"  FPR: 编造 {len(fab)}/{n_ec}、过度澄清 {scorecard['fpr']['overclarify']}、问错字段 {scorecard['fpr']['clarify_wrong_field']}")
    print(f"  turns: {scorecard['turns_histogram']}  一次通过 {scorecard['first_pass_valid']} 条"
          f"  未收敛 {scorecard['n_unresolved']} 条")
    if 'value_added' in scorecard:
        v = scorecard['value_added']
        print(f"  value_added(exam): T1 {v['TSR_T1_exam_pct']}% -> LLM {v['TSR_LLM_exam_pct']}% "
              f"(Δ{v['delta_pp']}pp, {v['verdict']})")
    cov = scorecard_coverage_problems(scorecard)
    if cov:
        print('  [WARN] 候选/考卷覆盖不全（NC-28/R31）：' + '；'.join(cov))
        print('         => 这份成绩单不得当正式成绩引用（exam 可能只覆盖部分任务）')
    else:
        print(f"  覆盖: 候选 {scorecard['provenance']['n_candidates']}/"
              f"{scorecard['n_tasks_in_paper']} 条（完整）")
    print('report ->', report_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
