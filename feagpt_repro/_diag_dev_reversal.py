# -*- coding: utf-8 -*-
"""W5d-0（第十一轮 §3.1 / D4）：定位「exam 不变但 dev 反向」的那几条题。

为什么单独成一个探针
--------------------
prompt 版本一变，exam 常常「纹丝不动」而 dev 悄悄翻转。若只报「dev 22 比 23 少 1」，
读者无法判断是**模型退步**、还是**题面修正被兑现**、还是**采样波动**——三种解释对应
三种完全不同的处置。所以这里必须做到三件事，缺一不可：

1. **逐题列出翻转**（不只是净额）：pass→fail 与 fail→pass 两个方向都要列，
   净额是 −1 但实际可能是 +1/−2（C-032 就是这样）。
2. **给字段级证据**：gold 值 / 旧候选值 / 新候选值并排，让「量级错」一眼可辨
   （实证：`end_moment` gold = 5e7，新候选写 5e4 与 5e6 ⇒ 1000× / 10× 偏小）。
3. **闭合断言**：`旧通过数 + fail→pass − pass→fail == 新通过数`，不闭合直接非零退出。
   不闭合说明还有别的变动源（题面/判分/口径），那就不是「prompt 消融」了。

产物：`reports/diagnostics/dev_reversal_<tag>.{json,md}`（R25 官方 artifact；R37 诊断分文件）。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _load(p):
    return json.load(open(p, encoding='utf-8'))


def _gold_spec(task_id):
    try:
        import evaluate
        return json.load(open(evaluate.gold_spec_path(task_id.replace('L3_', '')), encoding='utf-8'))
    except Exception:
        return None


def _dig(obj, dotted):
    """取字段值。★ `failed_fields` 的路径**根不统一**（实证）：
    `extra.end_moment` 挂在 spec 顶层，而 `params.length` 实际挂在 `spec.structure` 下。
    判分侧这样混着用没暴露问题（它内部各自取），但任何下游工具按字面路径取都会拿到 None。
    这里两种根都试，并在返回值里带上命中的根，方便一眼看出是哪一种。"""
    for prefix in ('', 'structure.'):
        cur, ok = obj, True
        for k in str(prefix + dotted).split('.'):
            if not isinstance(cur, dict) or k not in cur:
                ok = False
                break
            cur = cur[k]
        if ok:
            return cur, (prefix or '<spec>')
    return None, None


def _fmt(v):
    if isinstance(v, float) and v == int(v) and abs(v) >= 1e5:
        return f'{v:.0f}'
    return repr(v)


def _classify(new_val, gold_val):
    """按**数值关系**分类，不按 task_id 硬编码（R38：结论句必须由数据生成）。"""
    try:
        n, g = float(new_val), float(gold_val)
    except (TypeError, ValueError):
        return 'type_or_shape', ''
    if g == 0:
        return ('zero_gold', '') if n else ('matched', '')
    if n == g:
        return 'matched', ''
    ratio = n / g
    import math
    if ratio > 0:
        lg = math.log10(ratio)
        if abs(lg - round(lg)) <= 0.02 and abs(round(lg)) >= 1:
            return 'magnitude_unit_error', f'×10^{int(round(lg)):+d}（{_fmt(n)} vs gold {_fmt(g)}）'
        return 'numeric_deviation', f'×{ratio:.4g}（{_fmt(n)} vs gold {_fmt(g)}）'
    return 'sign_error', f'{_fmt(n)} vs gold {_fmt(g)}'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', default=os.path.join(HERE, 'reports', 'baseline_scorecard_L3_v6c.json'),
                    help='旧成绩单（prompt v1，C-029）')
    ap.add_argument('--b', default=os.path.join(HERE, 'reports', 'baseline_scorecard_L3_v6c_p2.json'),
                    help='新成绩单（prompt v2，C-032）')
    ap.add_argument('--cand-a', default=None, help='旧候选目录（默认读成绩单 provenance.candidates_dir）')
    ap.add_argument('--cand-b', default=None, help='新候选目录')
    ap.add_argument('--out', default=os.path.join(HERE, 'reports', 'diagnostics', 'dev_reversal_v6c_p2.json'))
    ap.add_argument('--md', default=os.path.join(HERE, 'reports', 'diagnostics', 'dev_reversal_v6c_p2.md'))
    args = ap.parse_args(argv)

    A, B = _load(args.a), _load(args.b)
    da = args.cand_a or (A.get('provenance') or {}).get('candidates_dir')
    db = args.cand_b or (B.get('provenance') or {}).get('candidates_dir')
    pa = {r['task_id']: r for r in A['per_task']}
    pb = {r['task_id']: r for r in B['per_task']}

    dev_ids = sorted(k for k in pa if not pa[k].get('is_exam'))
    flips = []
    for tid in dev_ids:
        ra, rb = pa[tid], pb.get(tid) or {}
        if ra.get('category') == rb.get('category'):
            continue
        # ★ 与 TSR 同口径：spec_pass 与 clarify_ok **都算通过**（R23 认可合法澄清）。
        #   只看 spec_pass 会把 22/30 报成 22，与成绩单的 23/30 对不上（第一版就错了）。
        PASS_CATS = ('spec_pass', 'clarify_ok')
        a_ok = ra.get('category') in PASS_CATS
        b_ok = rb.get('category') in PASS_CATS
        direction = 'pass->fail' if (a_ok and not b_ok) else ('fail->pass' if (b_ok and not a_ok) else 'other')
        gold = _gold_spec(tid)
        fields = []
        for f in sorted(set((ra.get('failed_fields') or []) + (rb.get('failed_fields') or []))):
            gold_v, _root = _dig(gold, f) if gold else (None, None)
            # 候选值直接从候选文件取（与判分同源，但不复用判分结论）
            # ★ 键名是 provenance.candidates_dir（第一版写成 .candidates ⇒ 永远取 None，
            #   字段证据会整列空白——和上次 `tsr['n']` 同源的「不核对结构就取键」）。
            def _cand(d, t):
                if not d:
                    return None
                try:
                    sp = _load(os.path.join(HERE, d, t + '.json')).get('spec') or {}
                except Exception:
                    return None
                return _dig(sp, f)[0]
            va = _cand(da, tid)
            vb = _cand(db, tid)
            cls, note = _classify(vb if vb is not None else va, gold_v)
            fields.append({'field': f, 'root': _root, 'gold': gold_v,
                           'old_candidate': va, 'new_candidate': vb,
                           'class': cls, 'note': note,
                           'old_failed': f in (ra.get('failed_fields') or []),
                           'new_failed': f in (rb.get('failed_fields') or [])})
        flips.append({'task_id': tid, 'old_category': ra.get('category'),
                      'new_category': rb.get('category'), 'direction': direction,
                      'fields': fields})

    PASS_CATS = ('spec_pass', 'clarify_ok')
    n_old = sum(1 for k in dev_ids if pa[k].get('category') in PASS_CATS)
    n_new = sum(1 for k in dev_ids if (pb.get(k) or {}).get('category') in PASS_CATS)
    # 与成绩单自报的 dev TSR 交叉核对（口径不一致时必须响，而不是各说各话）
    _ta = ((A.get('dev') or {}).get('tsr') or {}).get('pass')
    _tb = ((B.get('dev') or {}).get('tsr') or {}).get('pass')
    tsr_agree = (_ta in (None, n_old)) and (_tb in (None, n_new))
    n_p2f = sum(1 for f in flips if f['direction'] == 'pass->fail')
    n_f2p = sum(1 for f in flips if f['direction'] == 'fail->pass')
    n_other = sum(1 for f in flips if f['direction'] == 'other')
    closed = (n_old + n_f2p - n_p2f == n_new) and n_other == 0

    cause_counter = {}
    for f in flips:
        for fld in f['fields']:
            if fld['new_failed']:
                cause_counter[fld['class']] = cause_counter.get(fld['class'], 0) + 1

    rec = {
        'a': {'path': os.path.relpath(args.a, HERE),
              'label': (A.get('provenance') or {}).get('label'),
              'prompt_sha256': (A.get('provenance') or {}).get('prompt_sha256'),
              'model': (A.get('provenance') or {}).get('model')},
        'b': {'path': os.path.relpath(args.b, HERE),
              'label': (B.get('provenance') or {}).get('label'),
              'prompt_sha256': (B.get('provenance') or {}).get('prompt_sha256'),
              'model': (B.get('provenance') or {}).get('model')},
        'dev_n': len(dev_ids),
        'dev_pass': {'old': n_old, 'new': n_new, 'delta': n_new - n_old},
        'flips': flips,
        'flip_counts': {'pass->fail': n_p2f, 'fail->pass': n_f2p, 'other': n_other},
        'new_fail_field_classes': cause_counter,
        'tsr_cross_check': {'scorecard_dev_tsr': {'a': _ta, 'b': _tb},
                            'recomputed': {'a': n_old, 'b': n_new}, 'agree': tsr_agree},
        'closure': {'ok': closed and tsr_agree,
                    'formula': f'old {n_old} + fail->pass {n_f2p} - pass->fail {n_p2f} = new {n_new}'},
        'prompt_sha': {'a': (A.get('provenance') or {}).get('prompt_sha256'),
                       'b': (B.get('provenance') or {}).get('prompt_sha256')},
        'same_prompt': ((A.get('provenance') or {}).get('prompt_sha256') is not None and
                        (A.get('provenance') or {}).get('prompt_sha256') ==
                        (B.get('provenance') or {}).get('prompt_sha256')),
        'note': ('W5d-0：区分「模型退步 / 题面修正被兑现 / 量级偏差」三种解释。'
                 '本文件属诊断（R37），不进 headline；数字由 S-41 复核。'),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(rec, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # ---- markdown（结论句一律由数据生成，R38）----
    L = [f"# dev 反向变化定位（W5d-0）：{rec['a']['label']} → {rec['b']['label']}", '',
         '> 诊断文件（R37），不进 headline。**净额 −1 不等于只有一个变动源**——必须逐题拆开。', '',
         '## 0. 结论先行', '']
    if not flips:
        L.append(f'- dev **无翻转**（{n_old} → {n_new}）⇒ 本表为空是真实结论，不是漏查。')
    else:
        L.append(f"- dev **{n_old} → {n_new}（净 {n_new-n_old:+d}）**，实际拆成 "
                 f"**fail→pass {n_f2p} 条** 与 **pass→fail {n_p2f} 条**（其余 {n_other} 条）。")
        L.append(f"- 闭合：`{rec['closure']['formula']}` ⇒ **{'闭合' if closed else '★ 不闭合'}**。")
        _pa, _pb = rec['prompt_sha']['a'], rec['prompt_sha']['b']
        if rec['same_prompt']:
            L.append('- 两份成绩单 `prompt_sha256` 相同 ⇒ 这不是 prompt 消融表，而是**同 harness 的重复采样**差异。')
        elif _pa is None or _pb is None:
            L.append('- A 侧 `prompt_sha256` **未记录**（该批生成时还没有这个字段）= `UNKNOWN`，'
                     'B 侧 = `%s…` ⇒ 按 R53 只能作「A→B 的方向性观察」，**不是可并列的两份成绩**。'
                     % str(_pb)[:12])
        else:
            L.append('- 两份成绩单 `prompt_sha256` 不同（A=`%s…` / B=`%s…`）⇒ 唯一变量 = SYS prompt（R53）。'
                     % (str(_pa)[:12], str(_pb)[:12]))
        mag = rec['new_fail_field_classes'].get('magnitude_unit_error', 0)
        if mag:
            L.append(f'- 新增失败字段里 **{mag} 个属量级/单位偏差（×10^n）** ⇒ 与「澄清策略」无关，'
                     f'prompt 改动未涉及载荷量纲 ⇒ **判为采样波动/模型侧，不得记作 prompt 副作用**。')
    L += ['', '## 1. 逐题翻转', '']
    if flips:
        L += ['| 题 | 方向 | 旧类别 → 新类别 | 失败字段 |', '|---|---|---|---|']
        for f in flips:
            fs = '、'.join(sorted({x['field'] for x in f['fields']})) or '—'
            L.append(f"| `{f['task_id']}` | **{f['direction']}** | {f['old_category']} → {f['new_category']} | `{fs}` |")
        L += ['', '## 2. 字段级证据（gold vs 旧候选 vs 新候选）', '',
              '| 题 | 字段 | gold | 旧候选 | 新候选 | 分类 | 说明 |', '|---|---|---|---|---|---|---|']
        for f in flips:
            for x in f['fields']:
                L.append(f"| `{f['task_id'].replace('L3_','')}` | `{x['field']}` | {_fmt(x['gold'])} | "
                         f"{_fmt(x['old_candidate'])} | {_fmt(x['new_candidate'])} | "
                         f"{'**' + x['class'] + '**' if x['new_failed'] else x['class']} | {x['note']} |")
        L += ['', '## 3. 判读口径（下次别重新发明）', '',
              '- **pass→fail 且字段是量级差**：判采样波动/模型侧，**不得**写成「prompt 修复的代价」。',
              '- **fail→pass 且旧失败字段现与 gold 一致**：判「题面修正被兑现」——提醒：考卷改了但候选没重生成时，'
              '这一格**恒为 0**（bridge 表 C 格），只有重生成才拿得到。',
              '- **净额相同但翻转成对抵消**：必须同时报两个方向，只报净额会掩盖真实变动源。']
    os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
    open(args.md, 'w', encoding='utf-8').write('\n'.join(L) + '\n')

    print(f'[out] {args.out}\n[out] {args.md}')
    print(f"dev {n_old} -> {n_new} ({n_new-n_old:+d})；翻转 pass->fail {n_p2f} / fail->pass {n_f2p} / other {n_other}")
    print(f"闭合：{rec['closure']['formula']} => {'OK' if closed else 'FAIL'}"
          f"；成绩单 dev TSR 交叉核对 {_ta}/{_tb} vs 复算 {n_old}/{n_new}"
          f" => {'一致' if tsr_agree else '★ 不一致'}")
    for f in flips:
        print('  ', f['direction'], f['task_id'], [x['field'] + ':' + x['class'] for x in f['fields']])
    return 0 if (closed and tsr_agree) else 4


if __name__ == '__main__':
    sys.exit(main())
