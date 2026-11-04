#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T-L27c v3：两个 L2 prompt arm 的配对对比（base vs strict）

★ 这个脚本只做**聚合与配对统计**，不重算判分 —— 判类与 pass 一律读 score_l2.py 的产物，
  避免「自己拿自己的解析器验自己」（SOUL 铁律）。

★ 为什么必须配对：同一批 16 题、同一模型、只换系统提示 ⇒ 两列是**配对**数据。
  用独立样本检验（费雪/卡方）在这里是错的（T-L27c v2 已踩过：公式写错 + 方法错，
  结论从「显著」翻成「不可分辨」）。这里只用 McNemar 精确双侧。

★ 四道前置闸（任一不成立直接 rc=2，不产出数字）：
  (i)   两成绩单 tasks_sha256 相同（同卷）
  (ii)  两成绩单 model 相同（同模型）—— 跨模型对比不属于本脚本范畴
  (iii) 两成绩单 prompt_sha256 **不同**（否则根本不是两个 arm）
  (iv)  base 与 strict 的 task_id 集合**双向相等**（A⊆B 与 B⊆A 都核，
        否则「删掉一条」会让配对表静默变小而全部看着正常）

用法：
  "$PY" _l27c_arm_compare.py \
      --base reports/diagnostics/l2i_v2_scores_glm.json \
      --strict reports/diagnostics/l2i_v3s_scores_glm.json \
      --tasks tasks/tasks_l2_informative_v2.jsonl \
      --out reports/diagnostics/l27c_v3_arm_glm.json \
      --md  reports/diagnostics/l27c_v3_arm_glm.md
"""
import argparse
import json
import math
import sys
from collections import Counter

CATS = ['spec_ok', 'clarify_ok', 'clarify_wrong', 'spec_bad', 'fabricated', 'invalid', 'not_run']


def _load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def _flatten(d, prefix=''):
    """把 spec 展平成 'a.b.c' -> value 的字典（只展到标量与列表为止）。"""
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flatten(v, f'{prefix}.{k}' if prefix else k))
    elif isinstance(d, list):
        # 列表整体算一个叶子（layup.plies 这类按整块比），同时给出下标路径以便定位
        out[prefix] = d
    else:
        out[prefix] = d
    return out


def mcnemar_exact(b, c):
    """精确双侧 McNemar：b = base对&strict错，c = base错&strict对。

    归零假设下 X=b ~ Binom(b+c, 0.5)。双侧 p = min(1, 2*P(X<=min(b,c)))。
    b+c==0 ⇒ 两 arm 完全一致 ⇒ p=1.0（不是 0，也不是「无法计算」）。
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--strict', required=True)
    ap.add_argument('--tasks', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--md', default='')
    # T-L27c v3：两种模式的前置条件**互相排斥**，写死各自一条，不做「差不多就行」的放宽。
    #   ablation（默认）：只许 prompt 不同 ⇒ 这是消融；
    #   repro：只许 prompt **相同** ⇒ 这是「同一 prompt 跑两遍」的复现性检查（N-31：
    #          temperature:0 不等于可复现，所以「一次满分」必须有第二遍撑住）。
    ap.add_argument('--mode', choices=['ablation', 'repro'], default='ablation')
    a = ap.parse_args()

    base, strict = _load(a.base), _load(a.strict)

    # ---- 前置闸（四条，任一不成立即 rc=2，绝不产出数字）----
    errs = []
    if base.get('tasks_sha256') != strict.get('tasks_sha256'):
        errs.append(f"(i) 不是同一张卷：base={base.get('tasks_sha256')} strict={strict.get('tasks_sha256')}")
    if base.get('model') != strict.get('model'):
        errs.append(f"(ii) 不是同一个模型：base={base.get('model')} strict={strict.get('model')}")
    if a.mode == 'ablation' and base.get('prompt_sha256') == strict.get('prompt_sha256'):
        errs.append(f"(iii) 两 arm 的 prompt_sha256 相同（{base.get('prompt_sha256')}）⇒ 根本没有变量，"
                    "这不是一次消融（要做复现性检查请用 --mode repro）")
    if a.mode == 'repro' and base.get('prompt_sha256') != strict.get('prompt_sha256'):
        errs.append(f"(iii-r) 复现性检查要求 prompt_sha256 相同，实际 "
                    f"{base.get('prompt_sha256')} vs {strict.get('prompt_sha256')} ⇒ 这是消融不是复现")
    if a.mode == 'repro' and base.get('candidates') == strict.get('candidates'):
        errs.append(f"(iii-r2) 两侧 candidates 指向同一目录（{base.get('candidates')}）⇒ 不是两次独立跑")
    bt = {r['task_id'] for r in base.get('per_task', [])}
    st = {r['task_id'] for r in strict.get('per_task', [])}
    if bt != st:
        only_b, only_s = sorted(bt - st), sorted(st - bt)
        errs.append(f"(iv) 两 arm 的 task_id 集合不相等：只 base 有 {only_b}，只 strict 有 {only_s}")
    if errs:
        print('[前置闸] 失败，不产出数字：', file=sys.stderr)
        for e in errs:
            print('  - ' + e, file=sys.stderr)
        return 2

    with open(a.tasks, encoding='utf-8') as f:
        tasks = [json.loads(l) for l in f if l.strip()]
    tmap = {t['task_id']: t for t in tasks}
    # 卷里的 task_id 必须覆盖两成绩单（核第三端：卷本身没被改瘦）
    missing = (bt | st) - set(tmap)
    if missing:
        print(f'[前置闸] 成绩单里有卷中不存在的 task_id：{sorted(missing)}', file=sys.stderr)
        return 2

    bmap = {r['task_id']: r for r in base['per_task']}
    smap = {r['task_id']: r for r in strict['per_task']}

    # ---- 配对迁移矩阵 ----
    matrix = Counter()
    rows = []
    for tid in sorted(tmap):
        if tid not in bmap or tid not in smap:
            continue
        br, sr = bmap[tid], smap[tid]
        bc, sc = br.get('category'), sr.get('category')
        matrix[(bc, sc)] += 1
        # 失败字段归属：题面已有该键 = 「转写错误」（strict 想修的），否则「题面没有」
        given = set(_flatten(tmap[tid]['input'].get('spec_normalized') or {}).keys())
        def _fk(r):
            return list(((r.get('detail') or {}).get('failed_fields') or []))
        bf, sf = _fk(br), _fk(sr)
        rows.append({
            'task_id': tid,
            'family': br.get('family'),
            'split_v2': tmap[tid].get('split_v2'),
            'base_category': bc,
            'strict_category': sc,
            'base_pass': bool(br.get('pass')),
            'strict_pass': bool(sr.get('pass')),
            'base_failed_fields': bf,
            'strict_failed_fields': sf,
            'base_failed_given_keys': sorted(set(bf) & given),      # 题面给了却被改坏
            'strict_failed_given_keys': sorted(set(sf) & given),
            'base_failed_absent_keys': sorted(set(bf) - given),     # 题面没有（编造或缺）
            'strict_failed_absent_keys': sorted(set(sf) - given),
            'base_clarify': br.get('clarify_text'),
            'strict_clarify': sr.get('clarify_text'),
            'base_turns': (br.get('detail') or {}).get('turns_used'),
            'strict_turns': (sr.get('detail') or {}).get('turns_used'),
        })

    n = len(rows)
    b_pass = sum(1 for r in rows if r['base_pass'])
    s_pass = sum(1 for r in rows if r['strict_pass'])
    b = sum(1 for r in rows if r['base_pass'] and not r['strict_pass'])   # base 对 strict 错
    c = sum(1 for r in rows if (not r['base_pass']) and r['strict_pass'])  # base 错 strict 对
    p = mcnemar_exact(b, c)

    # 转写错误（题面给了却被改坏）的题数：这是 strict 引导的直接作用面
    def _n_given_fail(prefix):
        return sum(1 for r in rows if r[f'{prefix}_failed_given_keys'])
    # 澄清数（追问 = 在 informative 题上必然错）
    b_clar = sum(1 for r in rows if r['base_category'] in ('clarify_ok', 'clarify_wrong'))
    s_clar = sum(1 for r in rows if r['strict_category'] in ('clarify_ok', 'clarify_wrong'))

    res = {
        '_note': ('T-L27c v3：同一卷同模型，只换 L2 prompt arm（base vs strict）。'
                  '判类与 pass 全部读 score_l2.py 产物，本脚本不重算判分。'
                  if a.mode == 'ablation' else
                  'T-L27c v3 复现性检查：同一卷、同模型、**同 prompt**，两次独立跑。'
                  'N-31：temperature=0 不等于可复现 ⇒ 单次满分不能作为结论，这一列是它的第二遍。'),
        'mode': a.mode,
        'paper': base.get('paper'),
        'tasks_sha256': base.get('tasks_sha256'),
        'model': base.get('model'),
        'arm': {'base': {'candidates': base.get('candidates'), 'prompt_sha256': base.get('prompt_sha256')},
                'strict': {'candidates': strict.get('candidates'), 'prompt_sha256': strict.get('prompt_sha256')}},
        'n_paired': n,
        'passed': {'base': b_pass, 'strict': s_pass,
                   'pct_base': round(100.0 * b_pass / n, 1) if n else None,
                   'pct_strict': round(100.0 * s_pass / n, 1) if n else None},
        # 复现性：判类逐条相同率（比 McNemar 更直白 —— 它直接回答「换一遍会不会换答案」）
        'agreement': {'same_category': sum(1 for r in rows if r['base_category'] == r['strict_category']),
                      'n': n,
                      'pct': round(100.0 * sum(1 for r in rows
                                               if r['base_category'] == r['strict_category']) / n, 1) if n else None,
                      'flipped_pass': sum(1 for r in rows if r['base_pass'] != r['strict_pass'])},
        'matrix': {f'{k[0]}->{k[1]}': v for k, v in sorted(matrix.items())},
        'mcnemar': {'base_pass_strict_fail': b, 'base_fail_strict_pass': c, 'p_exact_two_sided': p,
                    'note': '配对数据用精确 McNemar；b+c==0 时 p=1.0。'},
        'transcription_errors': {
            'base_tasks_with_given_key_broken': _n_given_fail('base'),
            'strict_tasks_with_given_key_broken': _n_given_fail('strict'),
            'note': '「题面已给该键、输出却判错」= 转写错误（strict 引导的直接作用面）。'},
        'clarify_counts': {'base': b_clar, 'strict': s_clar,
                           'note': '本卷 16 条 expected_clarifications 全为空 ⇒ 任何追问都记错。'},
        'per_task': rows,
    }
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    # ---- 人读摘要 ----
    _hd = 'L2 prompt arm 对比' if a.mode == 'ablation' else 'L2 prompt 复现性检查（同一 prompt 两遍）'
    _lb = ('base', 'strict') if a.mode == 'ablation' else ('第1遍', '第2遍')
    lines = [
        f"# {_hd}（{base.get('model')}，n={n}）", '',
        f"- {_lb[0]}：`{base.get('candidates')}` prompt_sha `{str(base.get('prompt_sha256'))[:12]}…`",
        f"- {_lb[1]}：`{strict.get('candidates')}` prompt_sha `{str(strict.get('prompt_sha256'))[:12]}…`",
        f"- 通过：{_lb[0]} **{b_pass}/{n}**（{res['passed']['pct_base']}%）→ {_lb[1]} **{s_pass}/{n}**"
        f"（{res['passed']['pct_strict']}%）",
        f"- 配对：{_lb[0]}对&{_lb[1]}错 **{b}** / {_lb[0]}错&{_lb[1]}对 **{c}** ⇒ McNemar 精确双侧 **p = {p:.4f}**",
        f"- 判类逐条相同 **{res['agreement']['same_category']}/{n}**"
        f"（{res['agreement']['pct']}%），pass 翻转 **{res['agreement']['flipped_pass']}** 条",
        f"- 转写错误（题面已给却被改坏）题数：{_lb[0]} **{_n_given_fail('base')}** → {_lb[1]} **{_n_given_fail('strict')}**",
        f"- 追问数（本卷一律记错）：{_lb[0]} **{b_clar}** → {_lb[1]} **{s_clar}**", '',
        '| task_id | 族 | split | ' + _lb[0] + ' | ' + _lb[1] + ' | ' + _lb[0] + ' 失败字段 | '
        + _lb[1] + ' 失败字段 |',
        '|---|---|---|---|---|---|---|',
    ]
    for r in rows:
        lines.append('| `{}` | {} | {} | {} | {} | {} | {} |'.format(
            r['task_id'], r['family'], r['split_v2'], r['base_category'], r['strict_category'],
            ', '.join(r['base_failed_fields']) or '—', ', '.join(r['strict_failed_fields']) or '—'))
    md = '\n'.join(lines) + '\n'
    if a.md:
        with open(a.md, 'w', encoding='utf-8', newline='\n') as f:
            f.write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
