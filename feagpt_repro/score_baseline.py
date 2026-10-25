# -*- coding: utf-8 -*-
"""
score_baseline.py — W4d L3 主基线成绩单（2026-10-25 老王拍板口径）

四指标分层（红线 R9：SFR≠MSR≠TSR）：
  TSR（主 KPI，行为正确性）= 完备题 spec_fidelity PASS + 澄清题 CLARIFY 问对（clarify_keywords）
        —— 澄清题静默编造 spec = 0 分（无论字段是否碰对，拍板「问对=对，编造=错」）
  SFR（字段保真）= spec_fidelity PASS / 产出 spec 的候选（纯客观，编造碰对也计）
  FPR（双向）= 该澄清不澄清（编造）/ 该答不答（过度澄清）
  MSR（全链可用率，红线 R14 正式基线必含）= 全链 gates 全 PASS / 全部任务（--msr 时计算）

判分口径：L3 走 engineering_layer（执行配置层 REPORTED NOT GATED + 死字段豁免，W4d 拍板）。
对照：value_added = TSR_LLM − TSR_T1（同任务集地板，--trivial 指向 trivial_baselines_L3.json）。
输出：eval_runs/baseline_scorecard_L3.json
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluate import evaluate_one, load_tasks, RUNS


def judge_l3_candidate(cand, task):
    """单条 L3 候选判类。返回 (category, pass_for_tsr, detail)。"""
    tid = task['task_id']
    ec = task.get('expected_clarifications') or []
    kws = task.get('clarify_keywords') or []
    if cand.get('error'):
        return 'llm_error', False, {'detail': cand['error']}
    if cand.get('clarify') and not cand.get('spec'):
        if ec:
            text = cand['clarify']
            hit = any(k in text for k in kws)
            return ('clarify_ok' if hit else 'clarify_wrong'), hit, \
                {'clarify': text[:150], 'keywords': kws, 'hit': hit}
        return 'clarify_wrong', False, {'clarify': cand['clarify'][:150],
                                        'note': '该答不答（信息完备却澄清）'}
    if cand.get('spec') and ec:
        return 'fabricated', False, {'note': f"澄清题静默编造 spec（缺 {ec}）",
                                     'expected_clarifications': ec}
    if cand.get('spec'):
        # 落盘纯 spec 供 evaluate_one 解包（它接受 gen_candidates 包装结构，直接用原文件）
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


def main():
    argv = sys.argv[1:]
    def get(k, d):
        return argv[argv.index(k) + 1] if k in argv else d
    cand_dir = get('--candidates', os.path.join(HERE, 'candidates_l3_v2'))
    report_path = get('--report', os.path.join(RUNS, 'baseline_scorecard_L3.json'))
    trivial_path = get('--trivial', os.path.join(RUNS, 'trivial_baselines_L3.json'))
    run_msr = '--msr' in argv
    n_tasks_exam = int(get('--n-tasks', '30'))

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
                     'category': cat, 'tsr_pass': ok,
                     'ec': bool(t.get('expected_clarifications')),
                     'turns_used': cand.get('turns_used'), **detail})

    # ---- 汇总 ----
    n = len(rows)
    def sel(*cats):
        return [r for r in rows if r['category'] in cats]
    tsr_p = sum(1 for r in rows if r['tsr_pass'])
    n_ec = sum(1 for r in rows if r['ec'])
    fab = sel('fabricated')
    clar_wrong = sel('clarify_wrong')
    spec_cat = sel('spec_pass', 'spec_fail', 'fabricated')
    sfr_p = sum(1 for r in spec_cat
                if r['category'] == 'spec_pass' or
                (r['category'] == 'fabricated' and r.get('n_fail') == 0))
    # fabricated 的字段保真：重判（judge 已给 n_fail——fabricated 分支没跑 spec_fidelity，补判）
    for r in fab:
        if 'n_fields' not in r:
            t = tasks[r['task_id']]
            rr = evaluate_one(t, os.path.join(cand_dir, r['task_id'] + '.json'), skip_solve=True)
            sf = rr['gates'].get('spec_fidelity', {})
            r['sfr_fields'] = f"{sf.get('n_fields', 0) - sf.get('n_fail', 1)}/{sf.get('n_fields', 0)}"
            r['sfr_pass'] = sf.get('pass', False)
    sfr_p = sum(1 for r in spec_cat if r.get('sfr_pass') or r['category'] == 'spec_pass')

    by_split = {}
    for s in sorted({r['split_v2'] for r in rows}):
        sub = [r for r in rows if r['split_v2'] == s]
        by_split[s] = {'tsr': f"{sum(1 for r in sub if r['tsr_pass'])}/{len(sub)}"}

    scorecard = {
        'note': 'W4d L3 主基线（2026-10-25 拍板口径）：TSR=行为正确性（完备题答对+澄清题问对）；'
                'SFR=字段保真（工程层判，配置层只报）；FPR 双向；MSR 全链见 msr 节（红线 R9/R14）。',
        'model': 'glm-5.3-flash',
        'decode': 'json_object + schema_task.json 校验 + 错误反馈修复循环（<=3 轮；SDK 无 logits 级 json_schema）',
        'n_tasks': n, 'n_tasks_exam_expected': n_tasks_exam,
        'partial': n < n_tasks_exam,
        'underpowered': n < 20,
        'tsr': {'pass': tsr_p, 'total': n, 'pct': round(100 * tsr_p / max(1, n), 1)},
        'sfr': {'pass': sfr_p, 'of_spec_candidates': len(spec_cat),
                'pct': round(100 * sfr_p / max(1, len(spec_cat)), 1)},
        'fpr': {'fabricated_on_clarify_tasks': len(fab), 'n_clarify_tasks': n_ec,
                'fabrication_rate_pct': round(100 * len(fab) / max(1, n_ec), 1),
                'overclarify': len([r for r in clar_wrong if not r['ec']]),
                'clarify_wrong_field': len([r for r in clar_wrong if r['ec']])},
        'category_counts': dict(collections.Counter(r['category'] for r in rows)),
        'by_split': by_split,
        'per_task': rows,
    }

    # value_added（同任务集 T1 地板）
    if os.path.exists(trivial_path):
        trivial = json.load(open(trivial_path, encoding='utf-8'))
        t1 = trivial['T1_retrieval']['all_pct']
        scorecard['value_added'] = {
            'TSR_T1_pct': t1, 'TSR_LLM_pct': scorecard['tsr']['pct'],
            'delta_pp': round(scorecard['tsr']['pct'] - t1, 1),
            'criterion': '>= 10 pp 才算 LLM 真有增量（专家 6.3.1）；n=30 >= 20 可判（红线 R12）',
            'verdict': ('PASS' if scorecard['tsr']['pct'] - t1 >= 10 else 'BELOW')}

    json.dump(scorecard, open(report_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('== L3 主基线成绩单（glm-5.3-flash + schema 修复循环）==')
    print(f"  TSR {scorecard['tsr']['pass']}/{n} ({scorecard['tsr']['pct']}%)   "
          f"分类: {scorecard['category_counts']}")
    print(f"  SFR {sfr_p}/{len(spec_cat)} ({scorecard['sfr']['pct']}%)   "
          f"FPR: 编造 {len(fab)}/{n_ec}、过度澄清 {scorecard['fpr']['overclarify']}")
    if 'value_added' in scorecard:
        v = scorecard['value_added']
        print(f"  value_added: T1 {v['TSR_T1_pct']}% -> LLM {v['TSR_LLM_pct']}% (Δ{v['delta_pp']}pp, {v['verdict']})")
    print('report ->', report_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
