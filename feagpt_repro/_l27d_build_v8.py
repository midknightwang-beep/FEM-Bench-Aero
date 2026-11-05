# -*- coding: utf-8 -*-
"""_l27d_build_v8.py —— §13 第 10 项「L2 信息完备题型进卷」（R65 新卷）

老王 2026-11-05 拍板 **A：+16 条（每族 4 条）**。

本脚本只做一件事：把 v7 卷（192 条）与信息完备诊断卷（16 条）**合成 v8 卷（208 条）**，
老行**逐字节原样搬运**（R65/S-52：跨版本只许加行，不许改老行）。

为什么不能手改题面
------------------
16 条由 `_l27c_make_l2_informative.py` 按 split 轮转生成；手改会让「成因」与「产物」脱钩，
下一轮再生成时对不上（N-18 / N-26 同型坑：一旦生成逻辑依赖位置，手工修一条就漂一片）。

字段对齐（实测差异，不是猜的）
------------------------------
v7 条目的键序：task_id, family, input_level, input_source, input, truth_ref,
                gates, split_v2, split_reason, geometry_class, expected_clarifications
16 条的键序：  （字母序）且**缺** `split_reason`、**多** `input_from`
⇒ 本脚本按 v7 键序重排 16 条，补 `split_reason`（写清来源），把 `input_from` 放在
  truth_ref 之后（它是溯源信息，与 truth_ref 同类）。
  `input_from` 保留而不丢弃：它记录「这条题是从哪条 L1 派生的」，正是 N-18 那类漂移的
  追查依据；丢掉它等于把溯源链剪断。

只写 `reports/papers/tasks_v8.jsonl`，**不动 `tasks/tasks.jsonl`**
（换当前卷是另一条单子：本脚本跑完先验数，再一次性 flip，避免中途半状态让 S-52/S-57 红）。

用法：
    python _l27d_build_v8.py            # 构建 + 自校验
    python _l27d_build_v8.py --check    # 只校验已有 v8 文件
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
V7 = os.path.join(HERE, 'reports', 'papers', 'tasks_v7.jsonl')
INF = os.path.join(HERE, 'tasks', 'tasks_l2_informative_v2.jsonl')
CUR = os.path.join(HERE, 'tasks', 'tasks.jsonl')
V8 = os.path.join(HERE, 'reports', 'papers', 'tasks_v8.jsonl')

# v7 的键序（新行按它重排，读起来与老行一致）
KEY_ORDER = ['task_id', 'family', 'input_level', 'input_source', 'input',
             'truth_ref', 'input_from', 'gates', 'split_v2', 'split_reason',
             'geometry_class', 'expected_clarifications']

SPLIT_REASON = ('信息完备题型进卷（§13 第 10 项 / R65）→ boundary_holdout | '
                'ec=0（该答不该问），来自 tasks_l2_informative_v2')


def _raw(path):
    """按 CRLF 原样取行（不解码行尾），返回 [(bytes_line, obj)]。"""
    b = open(path, 'rb').read()
    out = []
    for ln in b.split(b'\r\n'):
        if not ln.strip():
            continue
        out.append((ln, json.loads(ln.decode('utf-8'))))
    return out


def _sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def build(out=V8):
    v7 = _raw(V7)
    inf = _raw(INF)
    if not os.path.exists(CUR):
        return 2, '找不到当前卷 tasks/tasks.jsonl'
    s_cur, s_v7, s_v8 = _sha(CUR), _sha(V7), _sha(V8)
    # ★ 允许两种合法基线：还没 flip（当前卷 == v7）或已经 flip（当前卷 == v8）。
    #   第一版只允许前者 ⇒ flip 之后脚本自己跑不动了 —— 「前置断言」写成「只能是我
    #   预期的那个状态」就等于把工具变成一次性用品。边界仍是两个已知 sha，不是「随便」。
    if s_cur not in (s_v7, s_v8):
        return 2, (f'当前卷 sha {s_cur[:12]}… 既不是 v7 也不是 v8 ⇒ 基线漂移，'
                   '先修 SOT，不要在这个状态上加题')
    if s_v8 == s_v7:
        return 2, 'v8 与 v7 字节相同（没加成题？）'

    new_lines, added = [], []
    for _, o in inf:
        # 缺 split_reason ⇒ 补；多余键保留（input_from 是溯源链）
        o2 = dict(o)
        if not (o2.get('split_reason') or '').strip():
            o2['split_reason'] = SPLIT_REASON
        # 按 v7 键序重排；KEY_ORDER 之外的键（本卷应是空集）追加在尾部并告警
        ordered = {k: o2[k] for k in KEY_ORDER if k in o2}
        extra = [k for k in o2 if k not in ordered]
        if extra:
            print(f'[WARN] {o2["task_id"]} 有 KEYS_ORDER 之外的键：{extra}（已追加到尾部）')
            for k in extra:
                ordered[k] = o2[k]
        added.append(json.dumps(ordered, ensure_ascii=False))

    lines = [ln.decode('utf-8') for ln, _ in v7] + added
    blob = ('\r\n'.join(lines) + '\r\n').encode('utf-8')
    with open(out, 'wb') as f:
        f.write(blob)
    return 0, f'写出 {out}（{len(lines)} 行 / {_sha(out)[:12]}…）'


def check(out=V8):
    """自校验：老行逐字节保留 / 条数 / 层分布 / 族分布 / task_id 唯一。"""
    probs = []
    v7 = _raw(V7)
    v8 = _raw(out)
    v7b = {ln for ln, _ in v7}
    v8b = {ln for ln, _ in v8}
    lost = v7b - v8b
    if lost:
        probs.append(f'v7 有 {len(lost)} 行在 v8 中不存在（只许加行，不许改老行）')
        for x in list(lost)[:2]:
            try:
                probs.append('    · ' + json.loads(x.decode('utf-8'))['task_id'])
            except Exception:
                pass
    if len(v8b) != len(v8):
        probs.append(f'v8 有重复行（{len(v8)} 行实体化后只剩 {len(v8b)} 条）')
    ids = [o['task_id'] for _, o in v8]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        probs.append(f'v8 里 task_id 重复：{dup[:3]}')

    import collections
    lv = collections.Counter(o['input_level'] for _, o in v8)
    fam = collections.Counter(o['family'] for _, o in v8 if o['input_level'] == 'L2')
    fam7 = collections.Counter(o['family'] for _, o in v7 if o['input_level'] == 'L2')
    # ★ 不写死「每族 20」—— L2 的族分布本来就不均（v7 实测 wingbox 39 / open_hole 13 /
    #   fuselage 7 / stiffened 5）。判据按**增量**取：每族必须 +4。
    #   （第一版就是写死 20，被自己的闸抓住了；这正是「规格常量与生成常量必须分开」。）
    delta = {f: fam[f] - fam7[f] for f in set(fam) | set(fam7)}
    if set(delta.values()) != {4}:
        probs.append(f'L2 每族应各 +4（新题每族 4 条），实测增量 {delta}')
    if lv['L2'] != 80:
        probs.append(f'L2 层应为 80 条，实测 {lv["L2"]}')
    if len(v8) != 208:
        probs.append(f'全卷应为 208 条，实测 {len(v8)}')
    # 16 条新题必须 ec 为空（信息完备的定义）
    bad_ec = [o['task_id'] for _, o in v8
              if o['task_id'].startswith('L2i_') and (o.get('expected_clarifications') or [])]
    if bad_ec:
        probs.append(f'info 题里 ec 非空（不再是信息完备题）：{bad_ec[:3]}')
    if not all(o['task_id'].startswith('L2i_') for _, o in v8[len(v7):]):
        probs.append('新增行里有 task_id 不以 L2i_ 开头的（前缀必须能剥出真实 case）')

    if probs:
        print('[FAIL] v8 自校验')
        for p in probs:
            print('  · ' + p)
        return 2
    print(f'[ok] v8 自校验：{len(v8)} 条（L1 {lv["L1"]} / L2 {lv["L2"]} / L3 {lv["L3"]}）；'
          f'v7 的 {len(v7b)} 行逐字节原样保留；L2 族分布 {dict(fam)}；'
          f'sha {_sha(out)[:12]}…')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--out', default=V8, help='输出去向（默认 reports/papers/tasks_v8.jsonl）')
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    if a.check:
        return check(out)
    rc, msg = build(out)
    print(('[FAIL] ' if rc else '[ok] ') + msg)
    if rc:
        return rc
    return check(out)


if __name__ == '__main__':
    sys.exit(main())
