# -*- coding: utf-8 -*-
"""_l27d_flip_v8.py —— 把当前卷从 v7 换到 v8（R65 重冻结）

只做三件机械事，**不改任何判据**：
  ① `tasks/tasks.jsonl` ← `reports/papers/tasks_v8.jsonl`（按字节复制）
  ② `tasks/tasks.jsonl.sha256` 重算
  ③ `reports/papers/SHA256SUMS` 补一行 `tasks_v8.jsonl`

`TASK_CHAIN`（check_claims.py）**不在本脚本里改**：那是判据文件，必须留在 diff 里被人看见
（S-52 的链是刻意的手工动作，藏进脚本就没人审了）。

前置断言（重要）：只有当磁盘上的当前卷**仍然是 v7**（sha == v7 落档件）才允许 flip，
否则说明基线已经漂移，先修 SOT 再谈加题。

用法：
    python _l27d_flip_v8.py --check    # 只看现状，不动盘
    python _l27d_flip_v8.py            # 执行
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CUR = os.path.join(HERE, 'tasks', 'tasks.jsonl')
CUR_SHA = os.path.join(HERE, 'tasks', 'tasks.jsonl.sha256')
V7 = os.path.join(HERE, 'reports', 'papers', 'tasks_v7.jsonl')
V8 = os.path.join(HERE, 'reports', 'papers', 'tasks_v8.jsonl')
SUMS = os.path.join(HERE, 'reports', 'papers', 'SHA256SUMS')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()

    for p in (CUR, CUR_SHA, V7, V8, SUMS):
        if not os.path.exists(p):
            print(f'[FAIL] 缺文件 {p}')
            return 2

    s_cur, s_v7, s_v8 = sha(CUR), sha(V7), sha(V8)
    print(f'当前卷 sha {s_cur[:12]}… / v7 {s_v7[:12]}… / v8 {s_v8[:12]}…')
    if s_cur != s_v7:
        print('[FAIL] 当前卷已经不是 v7 —— 基线漂移，先修 SOT，不要在这个状态上加题')
        return 2
    if s_v8 == s_v7:
        print('[FAIL] v8 与 v7 字节相同（没加成题？）')
        return 2
    if a.check:
        print('[ok] 处于可 flip 的基线（当前卷 == v7，v8 是新的）')
        return 0

    # ① 换卷（按字节，不做任何格式化）
    blob = open(V8, 'rb').read()
    open(CUR, 'wb').write(blob)
    if sha(CUR) != s_v8:
        print('[FAIL] 复制后 sha 不符')
        return 2

    # ② 重算 sha 清单（格式与旧文件逐字节一致：<sha>+3 空格+相对路径+CRLF）
    with open(CUR_SHA, 'wb') as f:
        f.write((s_v8 + '   feagpt_repro/tasks/tasks.jsonl\r\n').encode('utf-8'))

    # ③ SHA256SUMS 补行（去掉旧的 tasks_v8 行后追加，不重复）
    lines = [l for l in open(SUMS, encoding='utf-8').read().splitlines() if l.strip()]
    lines = [l for l in lines if 'tasks_v8.jsonl' not in l]
    lines.append(f'{s_v8} *tasks_v8.jsonl')
    with open(SUMS, 'wb') as f:
        f.write(('\r\n'.join(lines) + '\r\n').encode('utf-8'))

    print(f'[ok] 已换卷：tasks/tasks.jsonl -> {len(blob.splitlines())} 行 / {s_v8[:12]}…')
    print('[next] 手工动作：check_claims.py 的 TASK_CHAIN 推一格；'
          '然后重出 r32_audit 两个 scope 与 l2_clarify_dual')
    return 0


if __name__ == '__main__':
    sys.exit(main())
