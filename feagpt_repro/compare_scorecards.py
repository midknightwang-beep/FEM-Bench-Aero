# -*- coding: utf-8 -*-
"""compare_scorecards.py — 两份成绩单「能不能直接比」的闸（W5b-3，专家第七轮 NC-29 / R30）

为什么需要它：v6 的 exam 是 **25 条**（boundary 6 + extrap 13 + interp 6），C-021 的 exam 是
**11 条**（boundary 4 + extrap 7）——**不是同一个分母**。把 25 条的 TSR 与 11 条的 45.5% 相减，
立刻就能编出「提升 x pp」的假结论；而 interp 6 条明显更容易，合并数天然偏高。
这类错误在文档里改不掉（人会忘），必须由脚本拒绝。

职责只有一件：判定可比性。不可比 ⇒ rc=3 并强制改报三栏（不给差值）。

  rc=0 可比：打印逐项 diff（TSR/SFR/MSR + 三栏）
  rc=3 不可比：打印拒绝原因 + 两份的三栏明细，不出任何「提升/下降」

用法：
  python compare_scorecards.py --a reports/baseline_scorecard_L3_v4.json \
                               --b reports/baseline_scorecard_L3_v6.json
  python compare_scorecards.py --a X --b X            # 自比，必须 rc=0（负控正控用）
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def signature(sc):
    """成绩单的「口径指纹」：exam 条数 + 定义文本 + 分层构成。"""
    ex = sc.get('exam') or {}
    strata = {}
    for k, v in (sc.get('exam_by_stratum') or {}).items():
        strata[k] = {'n': v.get('n'), 'tsr_pass': (v.get('tsr') or {}).get('pass')}
    return {'n': ex.get('n'), 'definition': sc.get('exam_definition'), 'strata': strata,
            'label': (sc.get('provenance') or {}).get('label') or sc.get('label') or ''}


def comparability(a, b):
    """返回 (ok, reasons)。ok=False 表示只能三栏并列，不得出差值（R30）。"""
    sa, sb = signature(a), signature(b)
    reasons = []
    if sa['n'] is None or sb['n'] is None:
        reasons.append('成绩单缺 exam.n（无法判口径）')
    elif sa['n'] != sb['n']:
        reasons.append(f"exam 条数不同（{sa['n']} vs {sb['n']}）")
    if sa['definition'] != sb['definition']:
        reasons.append('exam_definition 文本不同')
    if sa['strata'] and sb['strata'] and set(sa['strata']) != set(sb['strata']):
        reasons.append(f"exam 分层构成不同（{sorted(sa['strata'])} vs {sorted(sb['strata'])}）")
    if sa['strata'] and sb['strata']:
        for k in set(sa['strata']) & set(sb['strata']):
            if sa['strata'][k]['n'] != sb['strata'][k]['n']:
                reasons.append(f"分层 {k} 条数不同（{sa['strata'][k]['n']} vs {sb['strata'][k]['n']}）")
    return (not reasons), reasons


def _row(name, a, b):
    print(f"  {name:<16} A={a if a is not None else '-':<10} B={b if b is not None else '-':<10}")


def _print_strata(sc, tag):
    st = sc.get('exam_by_stratum') or {}
    if not st:
        print(f"  [{tag}] 无三栏明细")
        return
    for k, v in st.items():
        print(f"  [{tag}] {k:<14} n={v.get('n')}  TSR {(v.get('tsr') or {}).get('pass')}"
              f" ({ (v.get('tsr') or {}).get('pct')}%)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', required=True)
    ap.add_argument('--b', required=True)
    ap.add_argument('--json', default=None, help='把结论写盘（W5b-4 用）')
    args = ap.parse_args()

    a = json.load(open(args.a, encoding='utf-8'))
    b = json.load(open(args.b, encoding='utf-8'))
    ok, reasons = comparability(a, b)

    sa, sb = signature(a), signature(b)
    print('== 成绩单可比性闸（R30）==')
    print(f"  A: {os.path.basename(args.a)}  exam n={sa['n']}  label={sa['label'] or '-'}")
    print(f"  B: {os.path.basename(args.b)}  exam n={sb['n']}  label={sb['label'] or '-'}")
    if not ok:
        print('\n  [REFUSED] 口径不同，不得直接比较（R30）：')
        for r in reasons:
            print(f"    - {r}")
        print('\n  必须改报三栏（分栏各自只报不判）：')
        _print_strata(a, 'A')
        _print_strata(b, 'B')
        print('\n  允许的表述：「口径变了（A 的 n 与 B 的 n 不同），B 的成绩不能与 A 相减」。')
        print('  禁止的表述：「TSR 从 x% 提升/下降到 y%」。')
    else:
        print('\n  [OK] 同口径，可逐项对照：')
        _row('exam TSR pass', (a['exam'].get('tsr') or {}).get('pass'),
             (b['exam'].get('tsr') or {}).get('pass'))
        _row('exam TSR pct', (a['exam'].get('tsr') or {}).get('pct'),
             (b['exam'].get('tsr') or {}).get('pct'))
        _row('exam SFR pct', (a['exam'].get('sfr') or {}).get('pct'),
             (b['exam'].get('sfr') or {}).get('pct'))
        _row('exam MSR', (a['exam'].get('msr')), (b['exam'].get('msr')))
        _print_strata(a, 'A')
        _print_strata(b, 'B')

    out = {'a': os.path.basename(args.a), 'b': os.path.basename(args.b),
           'comparable': ok, 'reasons': reasons,
           'sig_a': sa, 'sig_b': sb}
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)) or '.', exist_ok=True)
        json.dump(out, open(args.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"\nreport -> {args.json}")
    return 0 if ok else 3


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
