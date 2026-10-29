#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""成绩单回归比对：证明「改了判分脚本后，老卷的每个既有数字一个都没动」。

为什么需要这个工具（T-A11a）：
`score_baseline.py` 为了支持 v7 的 exam 双分母（C-037 / R66）改了 exam 谓词与分桶。
「跑出来看着一样」不算证明——**必须把两份 JSON 逐叶子比一遍**，并把新增键单独列出，
否则「新增了键」和「悄悄改了个数」会长得一模一样。

判据（R-A2 / R66）：
  ① `changed == 0` —— old 里存在的每个叶子路径，new 的值必须逐字相等；
  ② `added` 只允许是**预先声明**的新增键（默认前缀 allowlist）；
  ③ `removed` 必须为空（删键 = 悄悄改口径）。

用法：
  python _regress_scorecard.py OLD.json NEW.json [--allow-prefix exam_v11 --allow-prefix ...]
"""
import json, sys, argparse


def flatten(obj, prefix='', out=None):
    """把嵌套结构摊成 {路径: 叶子值}。list 用下标，dict 用点号。"""
    if out is None:
        out = {}
    if isinstance(obj, dict):
        if not obj:
            out[prefix] = {}
        for k, v in obj.items():
            flatten(v, f'{prefix}.{k}' if prefix else str(k), out)
    elif isinstance(obj, list):
        if not obj:
            out[prefix] = []
        for i, v in enumerate(obj):
            flatten(v, f'{prefix}[{i}]', out)
    else:
        out[prefix] = obj
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('old')
    ap.add_argument('new')
    ap.add_argument('--allow-prefix', action='append', default=[],
                    help='允许新增的键前缀（可多次给）；不在 allowlist 的新增也会被判红')
    ap.add_argument('--allow-suffix', action='append', default=[],
                    help='允许新增的键**后缀**（如 .is_exam_full）——用于 per_task[*].xxx 这类'
                         '按下标展开、无法用前缀表达的键。★ 必须是 `.xxx` 形式，防裸词放过全部')
    ap.add_argument('--allow-changed', action='append', default=[],
                    help='允许**值发生变化**的精确路径（可多次给）。'
                         '★ 只接受精确路径、不接受前缀：改值是最危险的一类差异，'
                         '必须逐条声明「我知道这条会变、原因是 X」，不能批量放行')
    ap.add_argument('--max-print', type=int, default=40)
    args = ap.parse_args()

    old = flatten(json.load(open(args.old, encoding='utf-8')))
    new = flatten(json.load(open(args.new, encoding='utf-8')))

    changed, removed, added = [], [], []
    for path, ov in old.items():
        if path not in new:
            removed.append(path)
        elif new[path] != ov:
            changed.append((path, ov, new[path]))
    for path in new:
        if path not in old:
            added.append(path)

    def _allowed(p):
        if any(p == a or p.startswith(a + '.') or p.startswith(a + '[') for a in args.allow_prefix):
            return True
        # 后缀只能匹配「整段结尾」，且必须是 `.xxx` 形式（防 `exam` 这种裸词把 *.exam 全放过）
        return any(s.startswith('.') and p.endswith(s) for s in args.allow_suffix)

    bad_added = [p for p in added if not _allowed(p)]
    # `--allow-changed` 只接受**精确路径**：改值必须逐条声明，不做前缀批量放行
    allowed_chg = [c for c in changed if c[0] in set(args.allow_changed)]
    bad_changed = [c for c in changed if c[0] not in set(args.allow_changed)]

    print(f'old 叶子 {len(old)} 条 ／ new 叶子 {len(new)} 条')
    print(f'  changed = {len(changed)}（声明放行 {len(allowed_chg)}，未声明 {len(bad_changed)}）'
          f'    removed = {len(removed)}    '
          f'added = {len(added)}（allowlist 内 {len(added) - len(bad_added)}，越界 {len(bad_added)}）')

    for path, ov, nv in allowed_chg[:args.max_print]:
        print(f'  [CHANGED·已声明] {path}: {ov!r} -> {nv!r}')
    for path, ov, nv in bad_changed[:args.max_print]:
        print(f'  [CHANGED·越界] {path}: {ov!r} -> {nv!r}')
    for path in removed[:args.max_print]:
        print(f'  [REMOVED] {path}')
    for path in bad_added[:args.max_print]:
        print(f'  [ADDED·越界] {path}')
    if len(added) - len(bad_added) <= args.max_print:
        for path in [p for p in added if _allowed(p)]:
            print(f'  [ADDED·允许] {path} = {new[path]!r}')

    ok = not bad_changed and not removed and not bad_added
    print()
    print('RESULT:', 'PASS —— 除显式声明的变更与 allowlist 内新增键外零差异' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
