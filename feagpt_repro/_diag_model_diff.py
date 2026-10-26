# -*- coding: utf-8 -*-
"""_diag_model_diff.py — 第二模型对比诊断（W5b-5，C-031 vs C-029）

为什么单独写一个：`compare_scorecards.py` 只判「能不能比 + 总分 diff」。
跨模型对比真正有信息量的部分是 **失败模式**：
  · 两个模型是否在同一批题上失败？（题目难度 vs 模型个性）
  · 是否在同一批**字段**上失败？（`failed_fields` 交集）
  · 翻转题的分布（只有 A 过 / 只有 B 过）落在哪个 stratum？
这些都不进 claim 的判分，属**诊断**（R37：只落 reports/diagnostics/）。

★ 硬约束（R30/R39）：本脚本**先过 compare_scorecards.comparability**，
  不可比就 rc=3 直接退出、**一个差值都不打**。

用法：
  python _diag_model_diff.py --a reports/baseline_scorecard_L3_v6c.json \
                             --b reports/baseline_scorecard_L3_v6c_dsv4pro.json \
                             --out reports/diagnostics/model_diff_v6c_dsv4pro.json \
                             --md  reports/diagnostics/model_diff_v6c_dsv4pro.md
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from compare_scorecards import comparability  # noqa: E402  R30 闸的唯一出处


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def per_task_map(sc):
    return {r['task_id']: r for r in sc.get('per_task') or []}


def split_of(sc):
    """按 is_exam 切两桶（不重建规则，只读成绩单既有标记）。"""
    rows = sc.get('per_task') or []
    return ([r for r in rows if r.get('is_exam')],
            [r for r in rows if not r.get('is_exam')])


def conf_matrix(a_rows, b_map):
    """2×2：both / only_a / only_b / neither。"""
    cell = collections.Counter()
    detail = collections.defaultdict(list)
    for r in a_rows:
        t = r['task_id']
        pb = bool((b_map.get(t) or {}).get('tsr_pass'))
        pa = bool(r.get('tsr_pass'))
        k = ('both_pass' if pa and pb else
             'only_a' if pa else
             'only_b' if pb else 'neither')
        cell[k] += 1
        detail[k].append(t)
    return dict(cell), {k: sorted(v) for k, v in detail.items()}


def fail_field_overlap(a_rows, b_map):
    """两个模型都失败的题里，错的是不是同一批字段。

    ★ 这个指标的价值：若 9 条共同失败里 8 条错**同一批字段**，
      说明错因来自「题面/prompt 诱导」而非模型个性 ⇒ 该修 prompt 而不是换模型。
    """
    both_fail = [r for r in a_rows
                 if not r.get('tsr_pass') and not bool((b_map.get(r['task_id']) or {}).get('tsr_pass'))]
    same_fields, diff_fields, no_detail = [], [], []
    for r in both_fail:
        t = r['task_id']
        fa = set(r.get('failed_fields') or [])
        fb = set((b_map.get(t) or {}).get('failed_fields') or [])
        rec = {'task_id': t, 'A_only': sorted(fa - fb), 'B_only': sorted(fb - fa),
               'common': sorted(fa & fb)}
        if not fa and not fb:
            no_detail.append(rec)
        elif fa and fa == fb:
            same_fields.append(rec)
        else:
            diff_fields.append(rec)
    return {'n_both_fail': len(both_fail), 'identical_field_set': same_fields,
            'differing': diff_fields, 'no_field_detail': no_detail}


def category_dist(rows):
    return dict(collections.Counter(r.get('category') for r in rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', required=True, help='基准成绩单（C-029，glm-5.3-flash）')
    ap.add_argument('--b', required=True, help='对照成绩单（C-031，第二模型）')
    ap.add_argument('--out', default=None)
    ap.add_argument('--md', default=None)
    # R53 补丁（W5c-6d）：改 prompt 后的重生成与旧批次**不可比**（同卷 ≠ 同 harness）。
    # 但「prompt 改动究竟改了哪几条题」这个诊断本身必须能跑 ⇒ 显式开关，
    # 且产出的 rec 里强制标 diagnostic_only + 不可比原因，禁止被当成绩引用。
    ap.add_argument('--allow-incomparable', action='store_true',
                    help='仅用于「同一模型换 prompt」的逐题诊断：允许跨 harness 出逐题差异，'
                         '但结果强制标 diagnostic_only（不得当成绩/涨幅引用，R53）')
    args = ap.parse_args()

    a, b = load(args.a), load(args.b)

    ok, reasons = comparability(a, b)
    if not ok and not args.allow_incomparable:
        print('[REJECT] 两份成绩单不可比，按 R30 不出任何差值：')
        for r in reasons:
            print('   -', r)
        sys.exit(3)
    if not ok:
        print('[DIAGNOSTIC] 两份不可比，按 --allow-incomparable 只出逐题差异（R53）：')
        for r in reasons:
            print('   -', r)

    ea, da = split_of(a)
    eb, db = split_of(b)
    ma, mb = per_task_map(a), per_task_map(b)

    # 同卷但候选集必须不同，否则「跨模型」是假的
    ca = (a.get('provenance') or {}).get('candidates_dir')
    cb = (b.get('provenance') or {}).get('candidates_dir')
    if ca and cb and ca == cb:
        print('[REJECT] 两份成绩单用的候选目录相同 ⇒ 不是跨模型对比')
        sys.exit(3)

    cell_e, det_e = conf_matrix(ea, mb)
    cell_d, det_d = conf_matrix(da, mb)
    ov = fail_field_overlap(ea, mb)

    rec = {
        'note': 'A vs B 逐题诊断：按 A/B 的 provenance.model 判定是「同模型 prompt 消融」还是「跨模型诊断」；'
                '两代 prompt_sha256 不同时按 R53 只作消融证据、不得并列作成绩。本文件属诊断（R37），不进 headline。',
        'a': {'path': os.path.relpath(os.path.abspath(args.a), HERE).replace('\\', '/'),
              'label': (a.get('provenance') or {}).get('label'),
              'tasks_sha256': (a.get('provenance') or {}).get('tasks_sha256'),
              'candidates_dir': ca,
              'exam_tsr': (a.get('exam') or {}).get('tsr')},
        'b': {'path': os.path.relpath(os.path.abspath(args.b), HERE).replace('\\', '/'),
              'label': (b.get('provenance') or {}).get('label'),
              'tasks_sha256': (b.get('provenance') or {}).get('tasks_sha256'),
              'candidates_dir': cb,
              'exam_tsr': (b.get('exam') or {}).get('tsr')},
        'comparability': {'ok': ok, 'reasons': reasons},
        'diagnostic_only': (not ok),
        'diagnostic_note': (None if ok else
                            'R53：两份不是同一 harness（prompt 不同/未记录）⇒ 本文件只作逐题诊断，'
                            '不得作为成绩、涨幅或模型排名引用'),
        'exam_confusion': cell_e, 'exam_confusion_tasks': det_e,
        'dev_confusion': cell_d, 'dev_confusion_tasks': det_d,
        'exam_fail_field_overlap': ov,
        'exam_category_dist': {'A': category_dist(ea), 'B': category_dist(eb)},
    }

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        print(f'[out] {args.out}')

    ta = (a.get('exam') or {}).get('tsr') or {}
    tb = (b.get('exam') or {}).get('tsr') or {}
    # ★ 字段名是 total，不是 n（第一版读 n 拿到 None ⇒ Δ 印成 -300 pp —— 分母取错就是这个下场，
    #   正好是 R47 要防的那类错误；此处显式取不到就不出 Δ，宁可空着也不印荒谬数）。
    _na, _nb = ta.get('total'), tb.get('total')
    _pa, _pb = ta.get('pass'), tb.get('pass')
    if _na and _nb and _pa is not None and _pb is not None:
        _delta = f'{100 * (_pb / _nb - _pa / _na):+.1f} pp'
    else:
        _delta = 'N/A（缺 total/pass）'
    print(f"exam TSR: A {_pa}/{_na} vs B {_pb}/{_nb} (Δ {_delta})")
    print('exam 2x2:', cell_e)
    print('dev  2x2:', cell_d)
    print(f"共同失败 {ov['n_both_fail']} 条：字段集全同 {len(ov['identical_field_set'])} / "
          f"不同 {len(ov['differing'])} / 无明细 {len(ov['no_field_detail'])}")

    if args.md:
        L = []
        # ★ W5c-6d：标题与导语**按 A/B 是否同一模型自动选措辞**。
        #   旧版写死「C-029 vs C-031 跨模型诊断」，用它跑 C-029 vs C-032（同模型 prompt 消融）
        #   会在文件头留下「跨模型」四个字 —— 正是 R38 那类「结论句不按数据生成」的复发。
        # ★ rec['a'] 里只有 label（原版取 rec['a']['raw'] ⇒ 永远读到 '?'，又是一次
        #   「不核对结构就取键」——和 Δ 印 -300 pp 同源）；成绩单本体在 a / b。
        _ma = (a.get('provenance') or {}).get('model') or a.get('model') or '?'
        _mb = (b.get('provenance') or {}).get('model') or b.get('model') or '?'
        _same_model = (_ma == _mb)
        _kind = 'prompt/harness 消融（同模型）' if _same_model else '跨模型诊断'
        _sa = (a.get('provenance') or {}).get('prompt_sha256') or 'UNKNOWN'
        _sb = (b.get('provenance') or {}).get('prompt_sha256') or 'UNKNOWN'
        L.append(f'# {rec["a"]["label"]} vs {rec["b"]["label"]} —— {_kind}\n')
        L.append('> 诊断文件（R37）。**不进 headline**。\n')
        L.append(f'> 模型：A `{_ma}` / B `{_mb}`；prompt_sha256：A `{_sa[:12]}…` / B `{_sb[:12]}…`\n')
        if _sa != _sb:
            L.append('> **★ R53：两代 prompt_sha256 不同 ⇒ 本表只能作同一 harness 变量的消融证据，'
                     '不得把 A/B 当作两份可并列引用的成绩，更不得跨模型拼比。**\n')
        else:
            L.append('> **R30：同 paper sha / 同 prompt sha / 同判据 ⇒ 允许出差值。**\n')
        L.append(f"- A = `{rec['a']['label']}`（{ca}）exam TSR **{ta.get('pass')}/{ta.get('total')}**")
        L.append(f"- B = `{rec['b']['label']}`（{cb}）exam TSR **{tb.get('pass')}/{tb.get('total')}**\n")

        # ── R54（W5c-6h）：MSR 是**条件通过率**（分母 = 产出了 spec 的非澄清题），
        #    不同成绩单的分母可以不同（实测 C-032 exam 22 vs C-033 exam 21）⇒ 裸比 pct
        #    会被读成同口径。此处强制并列「分母 + SFR」，分母不等就明确写「不可直减」。
        #    动机与那条 MSR 反直觉同源：被排除的那条恰好是失败题 ⇒ 分母小的 pct 反而更高。
        _ea = a.get('exam') or {}
        _eb = b.get('exam') or {}
        _sa_ = (_ea.get('sfr') or {})
        _sb_ = (_eb.get('sfr') or {})
        _msA = (a.get('msr_section') or {})
        _msB = (b.get('msr_section') or {})
        _dA = _msA.get('n_denominator')
        _dB = _msB.get('n_denominator')
        _xA = _msA.get('n_no_spec_excluded_ids') or []
        _xB = _msB.get('n_no_spec_excluded_ids') or []

        def _split_num(s):
            try:
                return tuple(int(v) for v in str(s).split('/'))
            except Exception:
                return (None, None)

        _pa, _ta2 = _split_num(_msA.get('exam_msr'))
        _pb, _tb2 = _split_num(_msB.get('exam_msr'))
        L.append('## 0. exam MSR 口径对齐（R54）\n')
        L.append('| | MSR（条件） | MSR 分母 | exam SFR | 被排除的模型侧无输出 |')
        L.append('|---|---|---:|---|---|')
        L.append(f"| A | {_msA.get('exam_msr')} | {_msA.get('exam_denominator_audit', {}).get('n_counted')} | "
                 f"{_sa_.get('pass')}/{_sa_.get('of_spec_candidates')} | {('、'.join(_xA) or '—')} |")
        L.append(f"| B | {_msB.get('exam_msr')} | {_msB.get('exam_denominator_audit', {}).get('n_counted')} | "
                 f"{_sb_.get('pass')}/{_sb_.get('of_spec_candidates')} | {('、'.join(_xB) or '—')} |")
        L.append('')
        if _ta2 and _tb2 and _ta2 != _tb2:
            L.append(f'> **★ R54：两侧 exam MSR 分母不同（{_ta2} vs {_tb2}）⇒ pct 不得直减、'
                     f'不得据此排名。** 分母只含「产出 spec 的非澄清题」，模型侧无输出已在 '
                     f'TSR/FPR 记过；A/B 的差异中有一半可能只是分母不同造成的。'
                     f'若必须比，先对齐分母（用 SFR + 逐题 2×2）或改用 full MSR 同分母口径。\n')
        elif _ta2:
            L.append(f'> R54：两侧 exam MSR 分母相同（{_ta2}）⇒ 允许出 Δ。\n')
        if _pa is not None and _pb is not None and _ta2 and _tb2:
            L.append(f'- exam MSR：A {_pa}/{_ta2} · B {_pb}/{_tb2}'
                     + (f'（Δ {round(100.0*(_pb/_tb2 - _pa/_ta2), 1):+} pp）' if _ta2 == _tb2 else '（分母不同，不出 Δ）'))
            L.append('')

        L.append('## 1. exam 逐题 2×2\n')
        L.append('| 格 | 条数 | 题 |')
        L.append('|---|---:|---|')
        for k in ('both_pass', 'only_a', 'only_b', 'neither'):
            ts = det_e.get(k) or []
            L.append(f"| {k} | {cell_e.get(k, 0)} | {'<br>'.join(ts) if ts else '—'} |")
        L.append('\n## 2. dev 逐题 2×2\n')
        L.append('| 格 | 条数 |')
        L.append('|---|---:|')
        for k in ('both_pass', 'only_a', 'only_b', 'neither'):
            L.append(f"| {k} | {cell_d.get(k, 0)} |")
        L.append('\n## 3. 共同失败题的失败字段（判「同因」还是「异因」）\n')
        if ov['identical_field_set']:
            L.append('**字段集完全相同**（同一批字段错 ⇒ 更像题面/prompt 诱导）：\n')
            for r in ov['identical_field_set']:
                L.append(f"- `{r['task_id']}`：{r['common']}")
            L.append('')
        if ov['differing']:
            L.append('**字段集不同**：\n')
            L.append('| 题 | 共同错 | 仅 A 错 | 仅 B 错 |')
            L.append('|---|---|---|---|')
            for r in ov['differing']:
                L.append(f"| `{r['task_id']}` | {r['common']} | {r['A_only']} | {r['B_only']} |")
            L.append('')
        if ov['no_field_detail']:
            L.append('**无字段明细**（clarify/contract/solver 类，不过 spec_fidelity）：\n')
            for r in ov['no_field_detail']:
                L.append(f"- `{r['task_id']}`")
            L.append('')
        L.append('## 4. category 分布\n')
        L.append('| category | A | B |')
        L.append('|---|---:|---:|')
        ka = rec['exam_category_dist']['A']
        kb = rec['exam_category_dist']['B']
        for k in sorted(set(ka) | set(kb)):
            L.append(f"| {k} | {ka.get(k, 0)} | {kb.get(k, 0)} |")
        with open(args.md, 'w', encoding='utf-8') as f:
            f.write('\n'.join(L) + '\n')
        print(f'[md]  {args.md}')


if __name__ == '__main__':
    main()
