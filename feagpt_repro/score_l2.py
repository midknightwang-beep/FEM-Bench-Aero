# -*- coding: utf-8 -*-
"""score_l2.py — L2 澄清题的**首次跑分器**（T-A13a，2026-10-30）

为什么需要单独一个文件
----------------------
`score_baseline.py:289` 写死 `if t['input_level'] == 'L3'` —— L2 候选会被**静默跳过**
（不报错、不计数，只是不出现在 rows 里）。L2 至今零候选、零分数，所以这个硬过滤
从来没被人撞到过。本文件补上 L2 这一路，且**不碰 L3 的任何代码路径**（L3 成绩单零差异）。

判据只有一处
------------
`judge_clarify_field_level` 从 `score_baseline` **import**，不复制实现 ——
两套实现必然漂移（`report_l2_clarify.py` 对 `check_l2_leak` 也是同一纪律）。

L2 的判类（与 L3 的 clarify 分支同口径）
----------------------------------------
| 类别            | 条件                                        | 记通过 |
|-----------------|---------------------------------------------|--------|
| `clarify_ok`    | 只给 clarify、且命中 expected 字段（R17）    | ✅     |
| `clarify_wrong` | 只给 clarify、但字段没命中 / 含错族键        | ❌     |
| `fabricated`    | 澄清题却给了 spec（静默编造，R20）           | ❌     |
| `llm_error`     | 候选里带 `error`                             | ❌     |
| `no_output`     | clarify/spec 都空                            | ❌     |
| `missing`       | **没有候选文件**（未跑）                     | ❌     |

★ `missing` 必须单列进报告并计入分母，不得静默排除（R-A5）。`n_candidates < n_tasks`
  时本工具仍出报告，但 `status` 会写成 `partial` —— 不假装跑完了。

双口径（R66 / C-038）
---------------------
`clarify_all` = 64（全卷）／`clarify_informative` = 45（name 未泄漏）。
掩码从 `check_l2_leak.scan()` 现算，**不从 artifact 抄**（防过期）。
再加一块 `invalid_subset` = 19，并断言 `all == informative + invalid`（任务数与通过数**两边都要闭合**）；
不闭合直接 `[FATAL]`，不出报告。

用法：
    python score_l2.py --cand candidates_l2_v7_glm --out reports/l2_scores_v7_glm.json
    python score_l2.py --self-test          # 判据自证伪（先证明自己不误报）
"""
import argparse
import collections
import hashlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from score_baseline import judge_clarify_field_level   # noqa: E402  ★ 判据只有一处
from check_l2_leak import scan                          # noqa: E402  ★ 掩码只有一处

TASKS = os.path.join(HERE, 'tasks', 'tasks.jsonl')


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_l2(tasks_path=TASKS):
    rows = [json.loads(l) for l in open(tasks_path, encoding='utf-8') if l.strip()]
    return [r for r in rows if r['input_level'] == 'L2']


def classify(cand, task):
    """单条 L2 候选判类。返回 (category, pass, detail)。"""
    if cand is None:
        return 'missing', False, {'note': '没有候选文件（该题未跑）'}
    if cand.get('error'):
        return 'llm_error', False, {'detail': cand['error']}
    clarify = cand.get('clarify')
    spec = cand.get('spec')
    if clarify and not spec:
        ok, detail = judge_clarify_field_level(clarify, task)
        return ('clarify_ok' if ok else 'clarify_wrong'), ok, detail
    if spec:
        return 'fabricated', False, {
            'note': '澄清题静默编造 spec（R20）',
            'expected_clarifications': task.get('expected_clarifications')}
    return 'no_output', False, {'note': 'clarify 与 spec 都为空'}


def _pct(p, n):
    return None if not n else round(100.0 * p / n, 1)


def _block(rows, key='pass'):
    n = len(rows)
    p = sum(1 for r in rows if r[key])
    return {'n': n, 'passed': p, 'pct': _pct(p, n)}


def score(cand_dir, tasks_path=TASKS, label=None):
    tasks = load_l2(tasks_path)
    n_l2, leak_hits, n_clean = scan(tasks_path)
    leak_ids = {h['task_id'] for h in leak_hits}

    rows, models, presentations, prompt_shas = [], collections.Counter(), collections.Counter(), collections.Counter()
    for t in tasks:
        p = os.path.join(cand_dir, f"{t['task_id']}.json")
        cand = None
        if os.path.exists(p):
            try:
                cand = json.load(open(p, encoding='utf-8'))
            except Exception as e:                       # 坏文件不得当成"没跑"
                cand = {'error': f'JSON 读不出: {e}'}
        cat, ok, detail = classify(cand, t)
        if cand:
            if cand.get('model'):
                models[cand['model']] += 1
            if cand.get('presentation'):
                presentations[cand['presentation']] += 1
            if cand.get('prompt_sha256'):
                prompt_shas[cand['prompt_sha256']] += 1
        rows.append({
            'task_id': t['task_id'], 'family': t['family'],
            'omitted_field': (t.get('expected_clarifications') or [None])[0],
            'category': cat, 'pass': ok,
            'name_leak': t['task_id'] in leak_ids,
            'clarify_text': (cand or {}).get('clarify'),
            'detail': detail,
        })

    if len(models) > 1:
        print(f'[FATAL] 候选目录里混了多个 model（{dict(models)}）；一批候选只能同一次生成（R51）')
        return None, 3
    model = next(iter(models), None)

    all_rows = rows
    inf_rows = [r for r in rows if not r['name_leak']]
    inv_rows = [r for r in rows if r['name_leak']]

    b_all, b_inf, b_inv = _block(all_rows), _block(inf_rows), _block(inv_rows)
    # R-A5：**任务数与通过数两边都要闭合**，否则双报就是两个对不上的数
    if b_all['n'] != b_inf['n'] + b_inv['n']:
        print(f"[FATAL] 双口径分母不闭合：all {b_all['n']} ≠ informative {b_inf['n']} + invalid {b_inv['n']}")
        return None, 4
    if b_all['passed'] != b_inf['passed'] + b_inv['passed']:
        print(f"[FATAL] 双口径通过数不闭合：all {b_all['passed']} ≠ inf {b_inf['passed']} + inv {b_inv['passed']}")
        return None, 4

    cats = collections.Counter(r['category'] for r in rows)
    n_cand = b_all['n'] - cats.get('missing', 0)
    status = 'scored' if cats.get('missing', 0) == 0 else 'partial'

    return {
        '_note': ('L2 澄清题首次跑分（T-A13a/T-A13b）。判据 import 自 score_baseline.'
                  'judge_clarify_field_level（R17）；双口径掩码 import 自 check_l2_leak.scan（R66）。'
                  '两个分母不同 ⇒ 禁相减、禁据此排名（R54）。'),
        'paper': os.path.basename(tasks_path),
        'tasks_sha256': _sha256(tasks_path),
        'candidates': os.path.basename(os.path.normpath(cand_dir)),
        'label': label,
        'model': model,
        'prompt_sha256': (next(iter(prompt_shas), None) if len(prompt_shas) <= 1
                          else f'MIXED:{sorted(prompt_shas)}'),
        'presentation': (next(iter(presentations), None) if len(presentations) <= 1
                         else f'MIXED:{sorted(presentations)}'),
        'status': status,
        'n_tasks_l2': len(tasks),
        'n_candidates': n_cand,
        'n_missing': cats.get('missing', 0),
        'category_counts': dict(cats),
        'clarify_all': {**b_all, 'denominator': '全卷 L2（含 name 泄漏的无效子集）'},
        'clarify_informative': {**b_inf, 'denominator': 'name 未泄漏的可判子集'},
        'invalid_subset': {**b_inv, 'denominator': 'name 泄漏 ⇒ 判据失效（R66 隔离，不得单独对外）'},
        'closure': {'units': 'tasks', 'all': b_all['n'], 'informative': b_inf['n'],
                    'invalid': b_inv['n'],
                    'formula': 'all == informative + invalid（任务数与通过数两侧都成立）'},
        'per_task': rows,
    }, 0


# ---------------------------------------------------------------------------
# 自证伪（R57 纪律：新判据工具的第一条纪律是**先证明自己不误报**）
# ---------------------------------------------------------------------------
def _self_test():
    tasks = load_l2()
    by_field = {}
    for t in tasks:
        by_field.setdefault((t.get('expected_clarifications') or ['?'])[0], t)
    t = by_field['n_frames'] if 'n_frames' in by_field else tasks[0]
    f = (t.get('expected_clarifications') or ['?'])[0]

    # ① 问对了（含键名）⇒ clarify_ok
    c_ok = {'task_id': t['task_id'], 'model': 'selftest', 'presentation': 'selftest',
            'prompt_sha256': 'x', 'clarify': json.dumps([f'缺少 {f}，请提供'], ensure_ascii=False), 'spec': None}
    # ② 问了但只写中文、不写键名 ⇒ clarify_wrong（这是"只认键名"的代价，必须亲眼看到）
    c_wrong = dict(c_ok, clarify=json.dumps(['缺一个数量参数，请提供'], ensure_ascii=False))
    # ③ 静默编造 spec ⇒ fabricated
    c_fab = dict(c_ok, clarify=None, spec={'structure': {'params': {}}})
    # ④ 空输出 ⇒ no_output
    c_none = dict(c_ok, clarify=None, spec=None)

    got = {k: classify(v, t)[0] for k, v in
           [('ok', c_ok), ('wrong', c_wrong), ('fab', c_fab), ('none', c_none)]}
    # ⑤ 没有文件 ⇒ missing
    got['missing'] = classify(None, t)[0]

    want = {'ok': 'clarify_ok', 'wrong': 'clarify_wrong', 'fab': 'fabricated',
            'none': 'no_output', 'missing': 'missing'}
    fails = [f'  (a) {k}: 期望 {want[k]} 实得 {got[k]}' for k in want if got[k] != want[k]]
    # ⑥ 通过标记：只有 clarify_ok 为 True
    passes = {k: classify(v, t)[1] for k, v in
              [('ok', c_ok), ('wrong', c_wrong), ('fab', c_fab), ('none', c_none)]}
    if passes['ok'] is not True:
        fails.append('  (b) clarify_ok 没被记为通过')
    for k in ('wrong', 'fab', 'none'):
        if passes[k] is not False:
            fails.append(f'  (b) {k} 被错误记为通过')

    # ⑦ 双口径闭合：把自测候选铺满整卷，断言 all == inf + inv
    with tempfile.TemporaryDirectory() as td:
        for x in tasks:
            k = (x.get('expected_clarifications') or ['?'])[0]
            body = {'task_id': x['task_id'], 'model': 'selftest',
                    'presentation': 'selftest', 'prompt_sha256': 'x',
                    'clarify': json.dumps([f'缺少 {k}，请提供'], ensure_ascii=False), 'spec': None}
            json.dump(body, open(os.path.join(td, f"{x['task_id']}.json"), 'w', encoding='utf-8'))
        sc, rc = score(td, label='selftest')
    if rc != 0 or not sc:
        fails.append(f'  (c) 整卷自测跑分失败 rc={rc}')
    else:
        a, i, v = sc['clarify_all'], sc['clarify_informative'], sc['invalid_subset']
        if a['n'] != i['n'] + v['n'] or a['passed'] != i['passed'] + v['passed']:
            fails.append(f"  (c) 双口径不闭合 all={a} inf={i} inv={v}")
        if a['passed'] != a['n']:
            fails.append(f"  (c) 全对却未全过：{a['passed']}/{a['n']}")
        if v['n'] != 19 or i['n'] != 45 or a['n'] != 64:
            fails.append(f"  (d) 掩码条数不对：all={a['n']} inf={i['n']} inv={v['n']}（应 64/45/19）")

    if fails:
        print('[FAIL] score_l2 自证伪不通过：')
        print('\n'.join(fails))
        return 1
    print('[ok ] score_l2 自证伪通过：')
    print(f'      ① {f} 命中键名 ⇒ clarify_ok（记通过）')
    print('      ② 只写中文不写键名 ⇒ clarify_wrong（"只认键名"的代价，如实可见）')
    print('      ③ 静默给 spec ⇒ fabricated　④ 空输出 ⇒ no_output　⑤ 无文件 ⇒ missing')
    print('      ⑥ 整卷自测：all 64 = informative 45 + invalid 19，两侧闭合，全对即全过')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--cand', help='候选目录')
    ap.add_argument('--tasks', default=TASKS)
    ap.add_argument('--out', help='写 JSON（R26：命令行路径 == artifact）')
    ap.add_argument('--label', default=None)
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args(argv)

    if a.self_test:
        return _self_test()
    if not a.cand:
        ap.error('必须给 --cand（或用 --self-test）')

    sc, rc = score(a.cand, a.tasks, a.label)
    if sc is None:
        return rc

    cats = sc['category_counts']
    print(f"L2 跑分：{sc['candidates']}  model={sc['model']}  呈现={sc['presentation']}")
    print(f"  status={sc['status']}  有候选 {sc['n_candidates']}/{sc['n_tasks_l2']}"
          f"  缺 {sc['n_missing']}")
    print(f"  类别: {cats}")
    print(f"  clarify_all          {sc['clarify_all']['passed']}/{sc['clarify_all']['n']}"
          f" = {sc['clarify_all']['pct']}%")
    print(f"  clarify_informative  {sc['clarify_informative']['passed']}/{sc['clarify_informative']['n']}"
          f" = {sc['clarify_informative']['pct']}%")
    print(f"  invalid_subset       {sc['invalid_subset']['passed']}/{sc['invalid_subset']['n']}"
          f" = {sc['invalid_subset']['pct']}%（R66 隔离，不得单独对外）")
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(sc, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'  -> {a.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
