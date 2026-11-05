# -*- coding: utf-8 -*-
"""_l27d_bridge.py —— v7 → v8 的单变量对照表（R65 / R-A2）

**这是唯一允许「跨版本比较」的场景**（R-A6）：两卷同时在场，逐层比对，
而不是拿两个分数相减。

它回答三个问题，每个都给出**机器复算**而不是叙述：
  B1  老行动没动？      v7 的每一行是否逐字节仍在 v8 里（按层拆开报）
  B2  哪一层没变？      L3 行集合差为空 ⇒ v7 的 L3 成绩单仍代表 v8 的 L3 层
  B3  L2 变了什么？     64 → 80：65 澄清题原样 + 16 信息完备新增；
                       澄清双口径的分母与通过数**逐数未变**（不是「应该没变」）

★ 不做的事：**不给任何 Δ**。v7 与 v8 的分母不同（192 vs 208、L2 64 vs 80），
  按 R54 禁止相减；本表的用途是「证明可比/不可比分别在哪里」，不是算增量。

用法：
    python _l27d_bridge.py                # 打印 + 写 diagnostics/l27d_bridge.{json,md}
    python _l27d_bridge.py --check        # 只判（B1/B2/B3 任一不成立即 rc=2）
"""
import argparse
import collections
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
V7 = os.path.join(HERE, 'reports', 'papers', 'tasks_v7.jsonl')
V8 = os.path.join(HERE, 'reports', 'papers', 'tasks_v8.jsonl')
SC_V7 = os.path.join(HERE, 'reports', 'diagnostics', 'l2_v7sysfix_scores_{m}.json')
SC_V8 = os.path.join(HERE, 'reports', 'diagnostics', 'l2_v8_scores_{m}.json')
OUT_JSON = os.path.join(HERE, 'reports', 'diagnostics', 'l27d_bridge.json')
OUT_MD = os.path.join(HERE, 'reports', 'diagnostics', 'l27d_bridge.md')
MODELS = ('glm', 'ds')


def _rows(p):
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]


def _sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def _by_level(rows):
    out = collections.defaultdict(list)
    for r in rows:
        # 按 task_id 的层前缀归类（L2i_ 也算 L2 层；不能只看 input_level，否则
        # 「新增的是哪一层」会被算进同一个桶里，B1 就检不出信息完备题那 16 条）
        t = r['task_id']
        lv = 'L2' if t.startswith('L2i_') or t.startswith('L2_') else t[:2]
        out[lv].append(r)
    return out


def run():
    v7, v8 = _rows(V7), _rows(V8)
    b7, b8 = _by_level(v7), _by_level(v8)

    # B1：老行逐字节仍在（比 task_id + 整条 JSON 序列化，不比对文件行号——卷是按案例交错的）
    rep = {'v7': {'path': os.path.relpath(V7, HERE).replace('\\', '/'), 'sha256': _sha(V7),
                  'n_rows': len(v7)},
           'v8': {'path': os.path.relpath(V8, HERE).replace('\\', '/'), 'sha256': _sha(V8),
                  'n_rows': len(v8)},
           'by_level': {}, 'checks': {}}

    ok = True
    for lv in ('L1', 'L2', 'L3'):
        s7 = {json.dumps(r, ensure_ascii=False, sort_keys=True) for r in b7[lv]}
        s8 = {json.dumps(r, ensure_ascii=False, sort_keys=True) for r in b8[lv]}
        lost = s7 - s8
        added = s8 - s7
        rep['by_level'][lv] = {'v7_n': len(b7[lv]), 'v8_n': len(b8[lv]),
                               'lost': len(lost), 'added': len(added)}
        if lost:
            ok = False

    # B2：L3 行集合差为空 ⇒ v7 的 L3 成绩单仍代表 v8 的 L3 层
    l3 = rep['by_level']['L3']
    rep['checks']['B1_old_rows_preserved'] = all(v['lost'] == 0 for v in rep['by_level'].values())
    rep['checks']['B2_L3_unchanged'] = (l3['lost'] == 0 and l3['added'] == 0)
    rep['checks']['B2_note'] = ('L3 行集合差为空 ⇒ v7 的 L3 成绩单（C-032/C-033/C-040）'
                                '仍然代表 v8 的 L3 层，**不需要重跑**')

    # B3：L2 —— 新增 16 条必须全是 ec=[] 且前缀 L2i_；澄清层 64 条必须原样
    add_l2 = [r for r in b8['L2']
              if json.dumps(r, ensure_ascii=False, sort_keys=True)
              not in {json.dumps(x, ensure_ascii=False, sort_keys=True) for x in b7['L2']}]
    ec_ok = all((r.get('expected_clarifications') or []) == [] for r in add_l2)
    pfx_ok = all(r['task_id'].startswith('L2i_') for r in add_l2)
    fam = collections.Counter(r['family'] for r in add_l2)
    rep['l2_added'] = {'n': len(add_l2), 'all_ec_empty': ec_ok,
                       'all_prefix_L2i': pfx_ok, 'by_family': dict(fam),
                       'task_ids': [r['task_id'] for r in add_l2]}
    rep['checks']['B3_added_are_informative'] = bool(ec_ok and pfx_ok and len(add_l2) == 16)

    # B3b：澄清双口径逐数未变（现读两份成绩单，不抄数字）
    sc = {}
    for m in MODELS:
        p7, p8 = SC_V7.format(m=m), SC_V8.format(m=m)
        if not (os.path.exists(p7) and os.path.exists(p8)):
            rep['checks']['B3b_clarify_numbers_unchanged'] = False
            rep['checks']['B3b_missing'] = [p for p in (p7, p8) if not os.path.exists(p)]
            ok = False
            break
        a, b = json.load(open(p7, encoding='utf-8')), json.load(open(p8, encoding='utf-8'))
        sc[m] = {
            'v7': {k: [a[k]['passed'], a[k]['n']] for k in
                   ('clarify_all', 'clarify_informative', 'invalid_subset')},
            'v8': {k: [b[k]['passed'], b[k]['n']] for k in
                   ('clarify_all', 'clarify_informative', 'invalid_subset')},
            'v8_informative': [b['strata']['informative']['passed'],
                               b['strata']['informative']['n']],
            'same': all(a[k]['passed'] == b[k]['passed'] and a[k]['n'] == b[k]['n']
                        for k in ('clarify_all', 'clarify_informative', 'invalid_subset')),
        }
        if not sc[m]['same']:
            ok = False
    rep['scores'] = sc
    rep['checks']['B3b_clarify_numbers_unchanged'] = all(v['same'] for v in sc.values())

    rep['_note'] = ('v7 → v8 单变量对照（R-A2）。**本表不给任何 Δ**：两卷分母不同'
                    '（192/208、L2 64/80）⇒ 按 R54 禁止相减。B2 证明 L3 层不需要重跑，'
                    'B3b 证明新增 16 条没有扰动澄清层的任何一个数。')
    return ok, rep


def _md(rep):
    L = ['# v7 → v8 单变量对照（L27d / R65）', '',
         '> 本表**不给任何 Δ** —— 两卷分母不同（全卷 192/208、L2 64/80），按 R54 禁止相减。', '',
         '## 卷', '',
         '| | 文件 | sha256 | 行数 |', '|---|---|---|---|',
         f"| v7 | `{rep['v7']['path']}` | `{rep['v7']['sha256'][:12]}…` | {rep['v7']['n_rows']} |",
         f"| v8 | `{rep['v8']['path']}` | `{rep['v8']['sha256'][:12]}…` | {rep['v8']['n_rows']} |", '',
         '## B1 老行有没有动（逐层）', '',
         '| 层 | v7 | v8 | 丢失 | 新增 |', '|---|---:|---:|---:|---:|']
    for lv, v in rep['by_level'].items():
        L.append(f"| {lv} | {v['v7_n']} | {v['v8_n']} | **{v['lost']}** | {v['added']} |")
    L += ['', '## B2 L3 层', '',
          f"- L3 行集合差：丢失 {rep['by_level']['L3']['lost']} / 新增 {rep['by_level']['L3']['added']}",
          f"- {rep['checks']['B2_note']}", '',
          '## B3 L2 层新增了什么', '']
    a = rep['l2_added']
    L += [f"- 新增 **{a['n']}** 条；全部 `expected_clarifications == []`：{a['all_ec_empty']}；"
          f"全部 `L2i_` 前缀：{a['all_prefix_L2i']}",
          f"- 每族：{a['by_family']}", '',
          '## B3b 澄清层数字有没有变（现读两份成绩单）', '',
          '| 模型 | 块 | v7 | v8 |', '|---|---|---:|---:|']
    for m, v in rep['scores'].items():
        for blk in ('clarify_all', 'clarify_informative', 'invalid_subset'):
            L.append(f"| {m} | `{blk}` | {v['v7'][blk][0]}/{v['v7'][blk][1]} | "
                     f"{v['v8'][blk][0]}/{v['v8'][blk][1]} |")
        L.append(f"| {m} | `strata.informative`（新增层） | — | "
                 f"{v['v8_informative'][0]}/{v['v8_informative'][1]} |")
    L += ['', '## 判据', '']
    for k, v in rep['checks'].items():
        if k.endswith('_note') or k.endswith('_missing'):
            continue
        L.append(f"- `{k}` = **{v}**")
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--out', default=OUT_JSON)
    ap.add_argument('--md', default=OUT_MD)
    a = ap.parse_args()
    ok, rep = run()
    if not a.check:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
            f.write('\n')
        with open(a.md, 'w', encoding='utf-8', newline='\n') as f:
            f.write(_md(rep))
        print(f'[OK] {a.out}\n[OK] {a.md}')
    bad = [k for k, v in rep['checks'].items() if v is False]
    for k, v in rep['checks'].items():
        if k.endswith(('_note', '_missing')):
            continue
        print(f'  [{"ok " if v else "FAIL"}] {k}')
    if bad:
        print('[FAIL] bridge 判据未过：' + ', '.join(bad))
        return 2
    print('[ok] bridge：老行未动、L3 层未变、新增全是信息完备题、澄清层逐数未变')
    return 0


if __name__ == '__main__':
    sys.exit(main())
