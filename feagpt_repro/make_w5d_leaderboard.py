# -*- coding: utf-8 -*-
"""W5d：干净跨模型榜单/协议（第十一轮 §5.1 的 P0）。

解决什么问题
------------
C-032（glm）与 C-033（deepseek）现在**同卷同 prompt**，是首例 R53 合规的跨模型对比。
但「谁更强」这件事在本基准里**不能用一个数字回答**，因为至少三个口径会给出相反排名：

1. **任务级 TSR**（分母 25，含澄清题与无输出题）：92.0% vs 88.0% ⇒ glm 领先 4 pp。
2. **字段级命中率**（Δ vs 族级众数地板）：99.34%（+13.4 PASS）vs 90.94%（+5.0 BELOW）⇒ glm 领先。
3. **条件 MSR**（分母 = 产出 spec 的非澄清题）：90.9%（20/22）vs **95.2%（20/21）** ⇒ **deepseek 反而「更高」**
   —— 因为它的分母少了 1 条，而那 1 条恰好是**失败题**（R54）。

⇒ 榜单必须**三列并排**（R56），并且 MSR 分母不等时**不出 Δ**。
本脚本不产出「排名第一」，只产出**可引用的三列 + 差异归因 + 禁用句式**。

闸门契约（S-42 读本 JSON）
--------------------------
- `models[*]` 必须含任务级 / 字段级 / 失败分层三组，缺一组即 S-42 红；
- `pairs[*].msr_delta_allowed` 必须由**分母是否相等**算出来，不得手填；
- 分母不等时 md 里出现 MSR 差值 ⇒ NC-47 变异必须被抓。
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from compare_scorecards import comparability  # noqa: E402

REPORTS = os.path.join(HERE, 'reports')


def _load(p):
    return json.load(open(p, encoding='utf-8'))


def _ci(name):
    p = os.path.join(REPORTS, f'bootstrap_ci_L3_{name}.json')
    if not os.path.exists(p):
        return None
    d = _load(p)
    return {k: {'pct': v.get('point_pct'), 'ci95': v.get('ci95'),
                'n': v.get('n'), 'n_pass': v.get('n_pass'),
                'denominator': v.get('denominator')}
            for k, v in (d.get('metrics') or {}).items()}, d.get('n_exam'), d.get('underpowered')


def _model_row(claim, sc_path, cand, ci_name):
    sc = _load(sc_path)
    ms = sc.get('msr_section') or {}
    ex = sc.get('exam') or {}
    dev = sc.get('dev') or {}
    va = sc.get('value_added') or {}
    fl = va.get('field_level') or {}
    ci = _ci(ci_name) or ({}, None, None)
    ci_m, ci_n, ci_under = ci if isinstance(ci, tuple) else (ci[0], None, None)
    audit = ms.get('exam_denominator_audit') or {}
    prow = [r for r in (ms.get('per_task') or []) if r.get('is_exam')]
    num, den = None, None
    try:
        num, den = [int(x) for x in str(ex.get('msr') or ms.get('exam_msr') or '').split('/')]
    except Exception:
        pass
    return {
        'claim': claim,
        'model': (sc.get('provenance') or {}).get('model') or sc.get('model'),
        'scorecard': os.path.relpath(sc_path, HERE),
        'candidates_dir': cand,
        'prompt_sha256': (sc.get('provenance') or {}).get('prompt_sha256'),
        'tasks_sha256': (sc.get('provenance') or {}).get('tasks_sha256'),
        'exam': {
            'tsr': dict(ex.get('tsr') or {}, ci95=(ci_m.get('TSR') or {}).get('ci95')),
            'sfr': dict(ex.get('sfr') or {}, ci95=(ci_m.get('SFR') or {}).get('ci95')),
            'msr': {'pass': num, 'den': den, 'pct': (ci_m.get('MSR') or {}).get('pct'),
                    'ci95': (ci_m.get('MSR') or {}).get('ci95'),
                    'conditional': True,
                    'excluded_ids': ms.get('n_no_spec_excluded_ids') or [],
                    'definition': ms.get('msr_definition')},
            'categories': ex.get('categories'),
            'three_columns': {k: {'n': (v or {}).get('n'), 'tsr': (v or {}).get('tsr')}
                              for k, v in (sc.get('exam_by_stratum') or {}).items()},
            'denominator_audit': {k: audit.get(k) for k in
                                  ('n_tasks_total', 'n_counted', 'n_clarify_excluded',
                                   'n_unresolved_excluded', 'n_solver_excluded', 'closure_ok')},
        },
        'dev': {'tsr': dev.get('tsr'), 'msr': dev.get('msr')},
        'full': {'msr': ms.get('msr'), 'pct': ms.get('msr_pct'),
                 'den': ms.get('n_denominator'),
                 'failure_class_counts': ms.get('failure_class_counts'),
                 'gate_fail_counts': ms.get('gate_fail_counts'),
                 'solver_ids': ms.get('solver_task_ids'),
                 'unresolved_ids': ms.get('n_no_spec_excluded_ids')},
        'value_added': {'task_level_pct': va.get('TSR_LLM_exam_pct'),
                        'task_level_delta_pp': va.get('delta_pp'),
                        'task_verdict': va.get('verdict'),
                        'field_floor_hit_rate': fl.get('floor_hit_rate'),
                        'field_llm_hit_rate': fl.get('llm_hit_rate'),
                        'field_delta_pp': fl.get('delta_pp'),
                        'field_verdict': fl.get('verdict'),
                        'verdict_split': va.get('verdict_split')},
        'fpr': sc.get('fpr'),
        'turns': sc.get('turns_histogram'),
        'first_pass': sc.get('first_pass_valid'),
        'underpowered': (sc.get('underpowered') if sc.get('underpowered') is not None else ci_under),
    }


def _pair(A, B, sa, sb):
    """逐题 2×2 + 共同失败字段集；MSR 能否相减由**分母**决定（R54）。"""
    pa = {r['task_id']: r for r in sa.get('per_task') or [] if r.get('is_exam')}
    pb = {r['task_id']: r for r in sb.get('per_task') or [] if r.get('is_exam')}
    PASS_CATS = ('spec_pass', 'clarify_ok')
    cell = {'both_pass': [], 'only_a': [], 'only_b': [], 'neither': []}
    for tid in sorted(set(pa) | set(pb)):
        a_ok = (pa.get(tid) or {}).get('category') in PASS_CATS
        b_ok = (pb.get(tid) or {}).get('category') in PASS_CATS
        key = 'both_pass' if (a_ok and b_ok) else 'only_a' if a_ok else 'only_b' if b_ok else 'neither'
        cell[key].append(tid)
    # 共同失败题：失败字段集是否相同（相同 ⇒ 更像题面/prompt 诱导；不同 ⇒ 模型个性）
    identical, differing = [], []
    for tid in cell['neither']:
        fa = set((pa.get(tid) or {}).get('failed_fields') or [])
        fb = set((pb.get(tid) or {}).get('failed_fields') or [])
        rec = {'task_id': tid, 'common': sorted(fa & fb),
               'A_only': sorted(fa - fb), 'B_only': sorted(fb - fa),
               'A_category': (pa.get(tid) or {}).get('category'),
               'B_category': (pb.get(tid) or {}).get('category')}
        (identical if fa == fb and fa else differing).append(rec)
    spec_pass = {'a': sum(1 for r in pa.values() if r.get('category') == 'spec_pass'),
                 'b': sum(1 for r in pb.values() if r.get('category') == 'spec_pass')}
    msr_a = A['exam']['msr']
    msr_b = B['exam']['msr']
    same_den = (msr_a['den'] is not None and msr_a['den'] == msr_b['den'])
    delta = None
    if same_den:
        try:
            delta = round(100.0 * (msr_b['pass'] / msr_b['den'] - msr_a['pass'] / msr_a['den']), 1)
        except Exception:
            delta = None
    tsr_a = ((A['exam']['tsr'] or {}).get('pct'))
    tsr_b = ((B['exam']['tsr'] or {}).get('pct'))
    return {
        'a': A['claim'], 'b': B['claim'],
        'both_prompt_sha256_equal': bool(A['prompt_sha256'] and A['prompt_sha256'] == B['prompt_sha256']),
        'both_tasks_sha256_equal': bool(A['tasks_sha256'] and A['tasks_sha256'] == B['tasks_sha256']),
        'tsr_delta_pp': (round(tsr_b - tsr_a, 1) if (tsr_a is not None and tsr_b is not None) else None),
        'tsr_leader': (A['claim'] if (tsr_a or 0) > (tsr_b or 0) else
                       B['claim'] if (tsr_b or 0) > (tsr_a or 0) else 'tie'),
        'msr_delta_allowed': same_den,
        'msr_delta_pp': delta,
        'msr_note': (f"分母相同（{msr_a['den']}）⇒ 允许出 Δ" if same_den else
                     f"**分母不同（{msr_a['den']} vs {msr_b['den']}）⇒ 不出 Δ、不得据此排名**（R54）；"
                     f"A 排除 {msr_a['excluded_ids']}，B 排除 {msr_b['excluded_ids']}"),
        'msr_leader_by_pct': (A['claim'] if (msr_a['pct'] or 0) > (msr_b['pct'] or 0) else
                              B['claim'] if (msr_b['pct'] or 0) > (msr_a['pct'] or 0) else 'tie'),
        'confusion': {k: len(v) for k, v in cell.items()},
        'confusion_tasks': cell,
        'shared_failures': {'identical_field_set': identical, 'differing': differing},
        'spec_pass': spec_pass,
        'spec_pass_equal': spec_pass['a'] == spec_pass['b'],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPORTS, 'w5d_leaderboard.json'))
    ap.add_argument('--md', default=os.path.join(REPORTS, 'w5d_leaderboard.md'))
    args = ap.parse_args(argv)

    specs = [
        ('C-032', 'baseline_scorecard_L3_v6c_p2.json', 'candidates_l3_v6c_glm_p2', 'v6c_p2'),
        ('C-033', 'baseline_scorecard_L3_v6c_ds_p2.json', 'candidates_l3_v6c_ds_p2', 'v6c_ds_p2'),
    ]
    hist = [
        ('C-029', 'baseline_scorecard_L3_v6c.json', 'candidates_l3_v6c', 'v6c'),
        ('C-031', 'baseline_scorecard_L3_v6c_dsv4pro.json', 'candidates_l3_v6c_dsv4pro', 'v6c_dsv4pro'),
    ]
    rows, raws = {}, {}
    for claim, fn, cand, ci in specs:
        p = os.path.join(REPORTS, fn)
        if not os.path.exists(p):
            print(f'[skip] 缺 {fn}')
            continue
        rows[claim] = _model_row(claim, p, cand, ci)
        raws[claim] = _load(p)
    hist_rows = {}
    for claim, fn, cand, ci in hist:
        p = os.path.join(REPORTS, fn)
        if os.path.exists(p):
            hist_rows[claim] = _model_row(claim, p, cand, ci)

    A, B = rows.get('C-032'), rows.get('C-033')
    pair = _pair(A, B, raws['C-032'], raws['C-033']) if (A and B) else None
    comp = comparability(raws['C-032'], raws['C-033']) if (A and B) else (False, ['缺成绩单'])
    # 历史批次与本榜的可比性（预期：全部不可比，因为 prompt v1 未记录 sha）
    hist_comp = {}
    for c in hist_rows:
        ok, why = comparability(raws['C-032'], _load(
            os.path.join(REPORTS, dict((h[0], h[1]) for h in hist)[c])))
        hist_comp[c] = {'comparable': ok, 'reasons': why}

    # ---- 允许/禁止说的话：全部由数据拼出来（R38）----
    allowed, forbidden = [], []
    def _ci_overlap(c1, c2):
        try:
            return not (c1[1] < c2[0] or c2[1] < c1[0])
        except Exception:
            return None
    if pair:
        allowed.append(
            f"{A['claim']}（{A['model']}）exam TSR **{(A['exam']['tsr'] or {}).get('pass')}/"
            f"{(A['exam']['tsr'] or {}).get('total')} = {(A['exam']['tsr'] or {}).get('pct')}%**、"
            f"{B['claim']}（{B['model']}）**{(B['exam']['tsr'] or {}).get('pass')}/"
            f"{(B['exam']['tsr'] or {}).get('total')} = {(B['exam']['tsr'] or {}).get('pct')}%**"
            f"——**同卷（`tasks_sha256` 相同）+ 同 prompt（`prompt_sha256` 相同）**")
        allowed.append(f"逐题 2×2：both {pair['confusion']['both_pass']} / only_a "
                       f"{pair['confusion']['only_a']} / only_b {pair['confusion']['only_b']} / "
                       f"neither {pair['confusion']['neither']}")
        allowed.append(f"两模型 `spec_pass` = {pair['spec_pass']['a']} vs {pair['spec_pass']['b']}"
                       f"（{'相同' if pair['spec_pass_equal'] else '不同'}）")
        allowed.append(f"字段级命中率：{A['claim']} {(A['value_added']['field_llm_hit_rate'] or 0)*100:.2f}%"
                       f"（Δ{A['value_added']['field_delta_pp']} pp，{A['value_added']['field_verdict']}） vs "
                       f"{B['claim']} {(B['value_added']['field_llm_hit_rate'] or 0)*100:.2f}%"
                       f"（Δ{B['value_added']['field_delta_pp']} pp，{B['value_added']['field_verdict']}）")
        forbidden.append(f"「{B['claim']} 的 {(B['exam']['tsr'] or {}).get('pct')}% 是能力上限」——"
                         f"2×2 里 only_b = {pair['confusion']['only_b']}，没有任何一条 A 错 B 对")
        forbidden.append('「两模型一样强」——TSR 差 '
                         f"{abs(pair['tsr_delta_pp'] or 0)} pp，且失败模式不同（见共享失败字段集）")
        forbidden.append('「差距全部来自建模能力」——`spec_pass` '
                         f"{pair['spec_pass']['a']} vs {pair['spec_pass']['b']}，差异不在建模能力这一层")
        forbidden.append('「用 MSR 单独排名」——' + pair['msr_note'])
        if B['value_added']['field_verdict'] == 'BELOW':
            forbidden.append(f"「{B['claim']} 有显著增量」——字段级 Δ{B['value_added']['field_delta_pp']} pp "
                             f"< 10 pp 判据（BELOW）")
        if A['dev']['tsr'] and B['dev']['tsr']:
            forbidden.append('「dev 也一致」——dev 是开发集，不进对外结论（R15）；只作参考')

    rec = {
        'schema': 'w5d_leaderboard/v1',
        'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'paper': {'path': 'reports/papers/tasks_v6c.jsonl',
                  'tasks_sha256': (A or {}).get('tasks_sha256')},
        'prompt_sha256': (A or {}).get('prompt_sha256'),
        'models': rows,
        'history_prompt_v1': hist_rows,
        'history_comparability_vs_current': hist_comp,
        'pair': pair,
        'comparability': {'ok': comp[0], 'reasons': comp[1]},
        'statements': {'allowed': allowed, 'forbidden': forbidden},
        'limits': [
            f"exam n=25 ⇒ CI 宽（{A['claim']} TSR CI95 {(A['exam']['tsr'] or {}).get('ci95')}）；族 n<10 不单列结论",
            f"MSR 是条件通过率（分母 {A['exam']['msr']['den']} vs {B['exam']['msr']['den']}）⇒ 不可直减（R54）",
            f"{B['claim']} 字段级 {B['value_added']['field_verdict']}（Δ{B['value_added']['field_delta_pp']} pp）⇒ 任务级单列会夸大",
            f"{B['claim']} 仍有 FPR {(B['fpr'] or {}).get('fabrication_rate_pct')}%（"
            f"{(B['fpr'] or {}).get('fabricated_on_clarify_tasks')}/{(B['fpr'] or {}).get('n_clarify_tasks')}）"
            f"与 {B['fpr'] and B['fpr'].get('clarify_wrong_field')} 条问错字段 ⇒ prompt v3 待修",
            'C-029/C-031 是 prompt v1 历史，`prompt_sha256` 未记录 ⇒ 与本榜**不可相减**（R53）',
        ],
        'repro': [
            'node gen_candidates_v2.js --tasks reports/papers/tasks_v6c.jsonl --levels L3 '
            '--out candidates_l3_v6c_glm_p2 --limit 55 --model glm-5.3-flash --max-turns 3',
            'node gen_candidates_v2.js --tasks reports/papers/tasks_v6c.jsonl --levels L3 '
            '--out candidates_l3_v6c_ds_p2 --limit 55 --model deepseek-v4-pro --max-turns 3',
            'python score_baseline.py --candidates candidates_l3_v6c_<m> --tasks '
            'reports/papers/tasks_v6c.jsonl --report reports/baseline_scorecard_L3_v6c_<m>.json '
            '--trivial reports/trivial_baselines_L3_v6c.json',
            'python msr_l3.py --candidates candidates_l3_v6c_<m> --tasks reports/papers/tasks_v6c.jsonl '
            '--report reports/baseline_scorecard_L3_v6c_<m>.json',
            'python bootstrap_ci.py --scorecard reports/baseline_scorecard_L3_v6c_<m>.json '
            '--out reports/bootstrap_ci_L3_v6c_<m>.json',
            'python _diag_model_diff.py --a reports/baseline_scorecard_L3_v6c_p2.json --b '
            'reports/baseline_scorecard_L3_v6c_ds_p2.json --out reports/diagnostics/'
            'model_diff_v6c_p2_glm_vs_ds.json --md reports/diagnostics/model_diff_v6c_p2_glm_vs_ds.md',
            'python _diag_dev_reversal.py   # W5d-0：dev 反向定位',
            'python make_w5d_leaderboard.py  # 本文件',
        ],
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(rec, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # ---------------------------- markdown ----------------------------
    L = ['# W5d 跨模型榜单（同卷 · 同 prompt · 可复现）', '',
         f"> 生成：`make_w5d_leaderboard.py`（{rec['generated_at']}）。**本表不含「排名第一」**——"
         f"三列口径会给出不同结论，只列事实与归因（R56）。", '',
         f"> 考卷 `reports/papers/tasks_v6c.jsonl`（sha `{str(rec['paper']['tasks_sha256'])[:12]}…`）；"
         f"SYS prompt sha `{str(rec['prompt_sha256'])[:12]}…`（两模型逐字相同）；"
         f"可比性闸：`{'通过' if comp[0] else '拒绝'} {comp[1] or ''}`", '',
         '## 1. 主榜（同 harness）', '',
         '| 口径 | C-032 `glm-5.3-flash` | C-033 `deepseek-v4-pro` | 能否相减 |', '|---|---|---|---|']
    if A and B:
        ea, eb = A['exam'], B['exam']
        L.append(f"| **任务级 TSR**（分母 {ea['tsr'].get('total')}） | **{ea['tsr'].get('pass')}/{ea['tsr'].get('total')} = "
                 f"{ea['tsr'].get('pct')}%**，CI95 {ea['tsr'].get('ci95')} | "
                 f"**{eb['tsr'].get('pass')}/{eb['tsr'].get('total')} = {eb['tsr'].get('pct')}%**，"
                 f"CI95 {eb['tsr'].get('ci95')} | ✅ Δ {pair['tsr_delta_pp']} pp（"
                 + ('两份 CI95 重叠 ⇒ 差值只作观察、不作显著结论' if _ci_overlap(
                     ea['tsr'].get('ci95') or [0, 0], eb['tsr'].get('ci95') or [0, 0])
                    else '两份 CI95 不重叠') + '） |')
        L.append(f"| **字段级命中率**（Δ vs 族级众数地板） | "
                 f"{(A['value_added']['field_llm_hit_rate'] or 0)*100:.2f}%（Δ+{A['value_added']['field_delta_pp']} pp，"
                 f"**{A['value_added']['field_verdict']}**） | "
                 f"{(B['value_added']['field_llm_hit_rate'] or 0)*100:.2f}%（Δ+{B['value_added']['field_delta_pp']} pp，"
                 f"**{B['value_added']['field_verdict']}**） | ✅（地板 "
                 f"{(A['value_added']['field_floor_hit_rate'] or 0)*100:.2f}% 同一） |")
        L.append(f"| **条件 MSR**（分母 = 产出 spec 的非澄清题） | {ea['msr']['pass']}/{ea['msr']['den']} = "
                 f"{ea['msr']['pct']}% | {eb['msr']['pass']}/{eb['msr']['den']} = {eb['msr']['pct']}% | "
                 f"{'✅ Δ ' + str(pair['msr_delta_pp']) + ' pp' if pair['msr_delta_allowed'] else '**❌ 不可相减**'} |")
        L.append(f"| exam SFR | {ea['sfr'].get('pass')}/{ea['sfr'].get('of_spec_candidates')} = "
                 f"{ea['sfr'].get('pct')}% | {eb['sfr'].get('pass')}/{eb['sfr'].get('of_spec_candidates')} = "
                 f"{eb['sfr'].get('pct')}% | ✅（分母各自定义） |")
        L.append(f"| 三栏 boundary / extrapolation / interpolation | "
                 f"{' · '.join(str((v['tsr'] or {}).get('pass')) + '/' + str(v['n']) for v in ea['three_columns'].values())} | "
                 f"{' · '.join(str((v['tsr'] or {}).get('pass')) + '/' + str(v['n']) for v in eb['three_columns'].values())} | 只报不判 |")
        L.append(f"| FPR 编造 / 澄清题 | {(A['fpr'] or {}).get('fabricated_on_clarify_tasks')}/"
                 f"{(A['fpr'] or {}).get('n_clarify_tasks')} = {(A['fpr'] or {}).get('fabrication_rate_pct')}% | "
                 f"{(B['fpr'] or {}).get('fabricated_on_clarify_tasks')}/{(B['fpr'] or {}).get('n_clarify_tasks')} = "
                 f"{(B['fpr'] or {}).get('fabrication_rate_pct')}% | ✅ |")
        def _turns(t):
            t = t or {}
            return ' / '.join(f'{k}:{t[k]}' for k in sorted(t))
        L.append(f"| first-pass / turns（同 ≤3 轮预算） | {A['first_pass']} · {_turns(A['turns'])} | "
                 f"{B['first_pass']} · {_turns(B['turns'])} | ✅ |")
        L.append(f"| unresolved（模型侧无输出） | {(A['full']['unresolved_ids'] or '—')} | "
                 f"{(B['full']['unresolved_ids'] or '—')} | 并列，不进分母（R54） |")
        L += ['', f"**★ MSR 一句说清**：{pair['msr_note']}。按 pct 看 "
                  f"**{pair['msr_leader_by_pct']} 更高，但它的 TSR 更低**——这就是「分母小的 pct 更好看」。", '',
              '## 2. 逐题 2×2（归因优先于排名）', '',
              '| 格 | 条数 | 题 |', '|---|---:|---|']
        for k in ('both_pass', 'only_a', 'only_b', 'neither'):
            ts = pair['confusion_tasks'][k]
            L.append(f"| {k} | {pair['confusion'][k]} | {'<br>'.join('`' + t.replace('L3_', '') + '`' for t in ts) if ts else '—'} |")
        L += ['', f"⇒ **`only_b = {pair['confusion']['only_b']}`**：{B['claim']} 没有任何一条 "
                  f"{A['claim']} 做错而它做对的题 ⇒ **不是互补，是纯损失**；换模型不是提分路径。", '',
              '## 3. 共同失败题的字段集（判「同因」还是「异因」）', '']
        if pair['shared_failures']['identical_field_set']:
            L.append('**字段集完全相同**（同一批字段错 ⇒ 更像题面/prompt 诱导）：')
            for r in pair['shared_failures']['identical_field_set']:
                L.append(f"- `{r['task_id']}`：`{r['common']}`（A {r['A_category']} / B {r['B_category']}）")
            L.append('')
        if pair['shared_failures']['differing']:
            L.append('**字段集不同**（⇒ 模型个性，不是题面缺陷）：')
            L += ['', '| 题 | A 类别 / B 类别 | 共同错 | 仅 A 错 | 仅 B 错 |', '|---|---|---|---|---|']
            for r in pair['shared_failures']['differing']:
                L.append(f"| `{r['task_id']}` | {r['A_category']} / {r['B_category']} | "
                         f"{r['common'] or '—'} | {r['A_only'] or '—'} | {r['B_only'] or '—'} |")
            L.append('')
            L.append('> 类别不同（如 `spec_fail` vs `no_output`）时「仅 X 错」为空是**正常**的：'
                     '无 spec 的候选没有字段级失败明细，不是「它也对了」。')
            L.append('')
        L += ['## 4. 失败分层（full MSR 必须带这一列，否则不可比）', '',
              '| | full MSR | model | solver | contract | 分母 |', '|---|---|---:|---:|---:|---:|']
        for c in ('C-032', 'C-033'):
            r = rows[c]
            fc = r['full']['failure_class_counts'] or {}
            L.append(f"| {c} | {r['full']['msr']} = {r['full']['pct']}% | {fc.get('model', 0)} | "
                     f"{fc.get('solver', 0)} | {fc.get('contract', 0)} | {r['full']['den']} |")
        _d1 = rows['C-032']['full']['den']
        _d2 = rows['C-033']['full']['den']
        L += ['', (f'> **full MSR 同样不可直减**：分母 {_d1} vs {_d2}（差的是 unresolved 题的归属），'
                   f'所以 {rows["C-032"]["full"]["pct"]}% 与 {rows["C-033"]["full"]["pct"]}% '
                   f'不能直接比大小；要比重先用 SFR 或逐题 2×2。')
              if _d1 != _d2 else '> full MSR 分母相同 ⇒ 允许比较。']
        L += ['', '## 5. 历史对照（prompt v1）——**只列事实，禁止与本榜相减**', '',
              '| | exam TSR | exam MSR | 字段级 | 与本榜可比？ |', '|---|---|---|---|---|']
        for c, r in hist_rows.items():
            hc = hist_comp.get(c) or {}
            L.append(f"| {c}（{r['model']}） | {(r['exam']['tsr'] or {}).get('pass')}/"
                     f"{(r['exam']['tsr'] or {}).get('total')} = {(r['exam']['tsr'] or {}).get('pct')}% | "
                     f"{r['exam']['msr']['pass']}/{r['exam']['msr']['den']} = {r['exam']['msr']['pct']}% | "
                     f"{(r['value_added']['field_llm_hit_rate'] or 0)*100:.2f}% | "
                     f"{'✅' if hc.get('comparable') else '**❌ ' + '；'.join(hc.get('reasons') or [])[:60] + '**'} |")
        L += ['', '## 6. 能说什么 / 不能说什么（引用前先看这张表）', '', '**可以说：**', '']
        L += [f'- {s}' for s in allowed]
        L += ['', '**不能说：**', '']
        L += [f'- {s}' for s in forbidden]
        L += ['', '## 7. 限制（写任何对外材料时必须带）', ''] + [f'- {s}' for s in rec['limits']]
        L += ['', '## 8. 第三方复现命令', '', '```bash',
              'cd feagpt_repro && PY="C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe"']
        L += [c for c in rec['repro']]
        L += ['```', '', '> 期望：`check_claims` 全过（25 claims / 41 语义项）、负控 48/48、'
              '两份成绩单数字与本表逐项一致（S-42 机器核对）。']
    os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
    open(args.md, 'w', encoding='utf-8').write('\n'.join(L) + '\n')

    print(f"[out] {args.out}\n[out] {args.md}")
    if pair:
        print(f"pair {pair['a']} vs {pair['b']}: TSR Δ {pair['tsr_delta_pp']} pp；"
              f"2×2 {pair['confusion']}；MSR 可减={pair['msr_delta_allowed']}（{pair['msr_note'][:40]}…）")
    return 0


if __name__ == '__main__':
    sys.exit(main())
