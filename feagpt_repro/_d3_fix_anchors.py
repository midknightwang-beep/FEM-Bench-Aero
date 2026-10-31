# -*- coding: utf-8 -*-
"""T-D3：重算被行尾规范化打断的活锚点（契约 §2 第 3 条）。

原则（为什么不重跑生成器）：
  这些锚点分布在**成绩单 / 论文证据包 / MSR 统计**里，重跑生成器会连带重写分数、分母、时间戳，
  那是 R71 明令禁止的。这里只做**同一字段的旧值 -> 新值**字节级替换，别的一个字节都不碰。

旧值怎么来的（确定性推导，不靠"在文件里猜"）：
  规范化把每个文件从 LF 变异到 CRLF，所以「旧值」恒等于 **该文件当前内容的 LF 版 sha256**，
  「新值」恒等于**当前磁盘字节的 sha256**。两者都可当场重算，不依赖任何中间产物。
  推导完必须过一道闸：旧值在锚点文件里出现的次数 == 预期次数（否则说明推错了文件或推错了版本）。
  F-4 是唯一的例外（锚点记的是更早的 v6b 卷，与行尾无关），单独按「文件里那一条」处理。

不做的事：
  · 不动 21 条历史快照 `_snap_*.json` 里的旧值（无判据读；改了反而让人误以为历史也重新封存过）；
  · 不改任何分数/通过数/分母；
  · 不为「找不到旧值」的锚点补写（那会凭空造锚点）。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

REPO = r'F:\AI FEA Modeling DataSets'
HEX = re.compile(rb'(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])')

# (被锚定文件, 锚点文件, 预期出现次数, 说明)
PLAN = [
    ('feagpt_repro/tasks/clarify_wrong_keys_fix.json',
     'feagpt_repro/reports/baseline_scorecard_L3_v7_glm.json', 1, 'S-59 判分元数据修正表（glm）'),
    ('feagpt_repro/tasks/clarify_wrong_keys_fix.json',
     'feagpt_repro/reports/baseline_scorecard_L3_v7_ds.json', 1, 'S-59 判分元数据修正表（ds）'),
    ('feagpt_repro/reports/papers/tasks_v4.jsonl',
     'feagpt_repro/reports/baseline_scorecard_L3_v4.json', 2, 'v4 历史成绩单里的考卷 sha'),
    ('feagpt_repro/reports/papers/tasks_v4.jsonl',
     'feagpt_repro/reports/msr_l3_v4.json', 1, 'v4 MSR 统计里的考卷 sha'),
    ('feagpt_repro/reports/papers/tasks_v4.jsonl',
     'feagpt_repro/reports/papers/SHA256SUMS', 1, '论文证据包 SHA256SUMS 的考卷行'),
    ('feagpt_repro/reports/papers/nl_human_v4.jsonl',
     'feagpt_repro/reports/papers/SHA256SUMS', 1, '论文证据包 SHA256SUMS 的 nl_human 行'),
]

F4 = ('feagpt_repro/tasks/tasks.jsonl', 'feagpt_repro/tasks/tasks.jsonl.sha256',
      'F-4 考卷 sha 文件过期（记的是 v6b 旧卷）')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    os.chdir(REPO)

    jobs, problems = [], []

    for target, anchor, want_n, why in PLAN:
        if not (os.path.exists(target) and os.path.exists(anchor)):
            problems.append(f'缺文件：{target} / {anchor}')
            continue
        tb = open(target, 'rb').read()
        new_sha = sha(tb)                                   # 当前（CRLF）版
        old_sha = sha(tb.replace(b'\r\n', b'\n'))           # 规范化前的 LF 版
        ab = open(anchor, 'rb').read()
        got_n = ab.count(old_sha.encode())
        if got_n != want_n:
            problems.append(f'{anchor}：旧值 {old_sha[:12]} 出现 {got_n} 次，预期 {want_n} 次')
            continue
        jobs.append((why, target, anchor, old_sha, new_sha, want_n))

    # F-4：旧值是文件里的那一条（与行尾无关，是版本过期）
    t4, a4, why4 = F4
    tb = open(t4, 'rb').read()
    new_sha = sha(tb)
    ab = open(a4, 'rb').read()
    olds = {m.group(0).decode() for m in HEX.finditer(ab)}
    if len(olds) != 1:
        problems.append(f'{a4}：应恰有 1 条 sha，实际 {len(olds)} 条')
    else:
        old_sha = next(iter(olds))
        jobs.append((why4, t4, a4, old_sha, new_sha, ab.count(old_sha.encode())))

    if problems:
        print('!! 预检失败，未写任何文件：')
        for p in problems:
            print('   ', p)
        sys.exit(1)

    print(f'{"执行" if args.apply else "预演（dry-run）"}：共 {len(jobs)} 条')
    for why, target, anchor, old_sha, new_sha, n in jobs:
        print(f'  · {why}')
        print(f'      锚点 {anchor}')
        print(f'      指向 {target}')
        print(f'      {old_sha[:16]}… -> {new_sha[:16]}…（{n} 处）')

    if not args.apply:
        print('\n（未写盘；加 --apply 执行）')
        return

    for why, target, anchor, old_sha, new_sha, n in jobs:
        body = open(anchor, 'rb').read()
        new_body = body.replace(old_sha.encode(), new_sha.encode())
        if new_body.count(b'\r\n') != body.count(b'\r\n'):
            raise SystemExit(f'!! {anchor} 行尾被改，终止')
        if new_body.count(new_sha.encode()) != body.count(old_sha.encode()):
            raise SystemExit(f'!! {anchor} 替换条数不符，终止')
        open(anchor, 'wb').write(new_body)
        print(f'  已写入 {anchor}')

    bad = []
    for target, anchor, _, _ in PLAN + [(t, a, None, None) for t, a, _ in [F4]]:
        if sha(open(target, 'rb').read()) not in open(anchor, 'rb').read().decode('utf-8', 'replace'):
            bad.append((anchor, target))
    if bad:
        print('!! 收尾验证失败：', bad)
        sys.exit(1)
    print(f'收尾验证：{len(PLAN) + 1} 处活锚点现值 == 磁盘重算值')


if __name__ == '__main__':
    main()
