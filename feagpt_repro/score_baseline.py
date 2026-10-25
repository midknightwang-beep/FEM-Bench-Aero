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
输出：eval_runs/baseline_scorecard_L3.json
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluate import evaluate_one, load_tasks, RUNS

EXAM_SPLITS = ('boundary_holdout', 'extrapolation_test')


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
    argv = sys.argv[1:]
    def get(k, d):
        return argv[argv.index(k) + 1] if k in argv else d
    cand_dir = get('--candidates', os.path.join(HERE, 'candidates_l3_v2'))
    report_path = get('--report', os.path.join(RUNS, 'baseline_scorecard_L3.json'))
    trivial_path = get('--trivial', os.path.join(RUNS, 'trivial_baselines_L3.json'))
    n_tasks_exam = int(get('--n-tasks-exam', '11'))

    tasks = {t['task_id']: t for t in load_tasks(os.path.join(HERE, 'tasks', 'tasks.jsonl'))
             if t['input_level'] == 'L3'}
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
        rows.append({'task_id': tid, 'split_v2': t['split_v2'], 'family': t['family'],
                     'category': cat, 'tsr_pass': ok, 'is_exam': t['split_v2'] in EXAM_SPLITS,
                     'ec': bool(t.get('expected_clarifications')),
                     'turns_used': cand.get('turns_used'), **detail})

    exam_rows = [r for r in rows if r['is_exam']]
    dev_rows = [r for r in rows if not r['is_exam']]
    n_exam = len(exam_rows)

    fab = [r for r in rows if r['category'] == 'fabricated']
    clar_wrong = [r for r in rows if r['category'] == 'clarify_wrong']
    n_ec = sum(1 for r in rows if r['ec'])

    scorecard = {
        'note': 'W4d L3 主基线（W4e 修正，专家第四轮 P0-1/R15）：headline=exam（boundary_holdout+'
                'extrapolation_test）；dev（train+val）只作开发诊断。TSR=行为正确性（完备题答对+'
                '澄清题字段级问对 R17）；SFR=字段保真（R20：编造一律不计 PASS）；FPR 双向；'
                'MSR 全链见 msr 节（R14/R16）。',
        'model': 'glm-5.3-flash',
        'decode': 'json_object + schema_task.json 校验 + 错误反馈修复循环（<=3 轮；SDK 无 logits 级 json_schema）',
        'exam_definition': 'exam = boundary_holdout + extrapolation_test；dev = train + val（R15）',
        'n_tasks': len(rows),
        'n_tasks_exam_expected': n_tasks_exam,
        'partial': n_exam < n_tasks_exam,
        'underpowered': n_exam < 20,
        'tsr': agg(rows, 'tsr')['tsr'],
        'exam': agg(exam_rows, 'exam'),
        'dev': {**agg(dev_rows, 'dev'), 'note': '开发集，不进对外（R15）'},
        'sfr_all': agg(rows, 'all')['sfr'],
        'fpr': {'fabricated_on_clarify_tasks': len(fab), 'n_clarify_tasks': n_ec,
                'fabrication_rate_pct': round(100 * len(fab) / max(1, n_ec), 1),
                'overclarify': len([r for r in clar_wrong if not r['ec']]),
                'clarify_wrong_field': len([r for r in clar_wrong if r['ec']])},
        'by_split': {s: agg([r for r in rows if r['split_v2'] == s], s)
                     for s in sorted({r['split_v2'] for r in rows})},
        'per_task': rows,
    }

    # value_added（exam 口径，R15/P1-10：不再用 all_pct）
    if os.path.exists(trivial_path):
        trivial = json.load(open(trivial_path, encoding='utf-8'))
        t1_exam = trivial['T1_retrieval']['exam_pct']
        llm_exam = scorecard['exam']['tsr']['pct']
        scorecard['value_added'] = {
            'basis': 'exam（boundary+extrap）TSR，T1 同任务集 exam_pct',
            'TSR_T1_exam_pct': t1_exam, 'TSR_LLM_exam_pct': llm_exam,
            'delta_pp': round(llm_exam - t1_exam, 1),
            'criterion': '>= 10 pp 才算 LLM 真有增量（专家 6.3.1）；n_exam<20 ⇒ underpowered 不得判 PASS（R12）',
            'verdict': ('PASS' if (llm_exam - t1_exam >= 10 and n_exam >= 20) else
                        'BELOW' if llm_exam - t1_exam < 10 else 'UNDERPOWERED')}

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
    print(f"  FPR: 编造 {len(fab)}/{n_ec}、过度澄清 {scorecard['fpr']['overclarify']}、问错字段 {scorecard['fpr']['clarify_wrong_field']}")
    if 'value_added' in scorecard:
        v = scorecard['value_added']
        print(f"  value_added(exam): T1 {v['TSR_T1_exam_pct']}% -> LLM {v['TSR_LLM_exam_pct']}% "
              f"(Δ{v['delta_pp']}pp, {v['verdict']})")
    print('report ->', report_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
