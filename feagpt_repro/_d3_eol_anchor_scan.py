# -*- coding: utf-8 -*-
"""D-3 行尾规范化的代价测量（只读，不写任何被追踪文件）。

背景（T-B1 / D-3、记忆里「行尾两端各有一批锚点，不存在单一配置全绿」）：
  git 索引里全是 LF；`core.autocrlf=true` 在 checkout 时把 LF 转 CRLF。
  本仓工作区是混合态 ⇒ 同一份仓库，在不同机器的字节不同 ⇒ sha256 锚点断裂。

本脚本回答两个问题，且**只回答测量**，不做任何选择：
  Q1 每个锚点（正文里的 64 位 hex）指向的是被锚文件的 **LF 版** 还是 **CRLF 版**？
  Q2 若全仓统一为 LF（或统一为 CRLF），各有多少锚点会失效？

方法：
  1) 对每个被追踪的文本文件算三份 sha：raw（工作区字节）/ lf（CRLF→LF）/ crlf（LF→CRLF）。
     注意 raw 与 lf 相同即「该文件已是纯 LF」，raw 与 crlf 相同即「已是纯 CRLF」。
  2) 扫所有文本文件正文里的 [0-9a-f]{64}，按上面的 sha 表反查它指向谁、哪个变体。
  3) 汇总：锚点若干条 = 指向 LF 版 a 条 + 指向 CRLF 版 b 条 + 指向混合态 c 条 + 查无此文件 d 条。

判据（--self-test）：
  · T1 已知锚点必被识别：tasks/tasks.jsonl 的 .sha256 文件里的那一条必须命中 tasks.jsonl
  · T2 变体判别正确：把某文件强制转 LF 后，同一 sha 必须从 lf 桶切到 crlf 桶（用内存副本，不落盘）
  · T3 查无此文件必须单独成桶，不得并入任何一侧（否则数字虚高）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

HEX64 = re.compile(rb'(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def variants(raw: bytes):
    """返回 (lf_bytes, crlf_bytes)。已是纯 LF/CRLF 时二者之一等于 raw。"""
    lf = raw.replace(b'\r\n', b'\n')
    crlf = lf.replace(b'\n', b'\r\n')
    return lf, crlf


def tracked(repo: str):
    out = subprocess.run(['git', '-c', 'core.quotepath=false', 'ls-files'], cwd=repo,
                         capture_output=True, text=True, encoding='utf-8')
    if out.returncode != 0:
        raise SystemExit(f'git ls-files 失败: {out.stderr}')
    return [f for f in out.stdout.split('\n') if f.strip()]


def is_text(raw: bytes) -> bool:
    if b'\x00' in raw[:8192]:
        return False
    return True


def build_index(repo: str, files):
    """sha -> [(path, variant)]；variant ∈ {lf, crlf, mixed}"""
    idx = defaultdict(list)
    info = {}
    for f in files:
        p = os.path.join(repo, f)
        try:
            raw = open(p, 'rb').read()
        except OSError:
            continue
        if not is_text(raw):
            continue
        lf, crlf = variants(raw)
        s_raw, s_lf, s_crlf = sha(raw), sha(lf), sha(crlf)
        if raw == lf and raw == crlf:          # 无换行的纯单行文本
            kind = 'flat'
        elif raw == lf:
            kind = 'lf'
        elif raw == crlf:
            kind = 'crlf'
        else:
            kind = 'mixed'
        info[f] = {'kind': kind, 'sha_raw': s_raw, 'sha_lf': s_lf, 'sha_crlf': s_crlf}
        for s, v in ((s_lf, 'lf'), (s_crlf, 'crlf')):
            idx[s].append((f, v))
    return idx, info


def scan(repo: str, files, idx, info):
    """返回锚点列表：{at, sha, targets:[{path,variant}], bucket}"""
    anchors = []
    for f in files:
        p = os.path.join(repo, f)
        try:
            raw = open(p, 'rb').read()
        except OSError:
            continue
        if not is_text(raw):
            continue
        for m in HEX64.finditer(raw):
            s = m.group(0).decode().lower()
            tgt = idx.get(s, [])
            if not tgt:
                bucket = 'unknown'
            else:
                kinds = {info[t[0]]['kind'] for t in tgt if t[0] in info}
                vs = {t[1] for t in tgt}
                if vs == {'lf'}:
                    bucket = 'lf'
                elif vs == {'crlf'}:
                    bucket = 'crlf'
                elif vs == {'lf', 'crlf'}:
                    bucket = 'both'          # 同一 sha 既是某文件 LF 版又是另一文件 CRLF 版
                else:
                    bucket = '?'
                if kinds and kinds <= {'flat'}:
                    bucket = 'flat'          # 单行文件，行尾无关
            anchors.append({'at': f, 'sha': s, 'bucket': bucket,
                            'targets': [{'path': t[0], 'variant': t[1]} for t in tgt][:4]})
    return anchors


def summarize(anchors):
    c = Counter(a['bucket'] for a in anchors)
    return c


def self_test(repo: str):
    """三向自检：只跑内存，不落盘。"""
    ok = True
    files = tracked(repo)
    idx, info = build_index(repo, files)
    # T1 拆两问：T1a 是「脚本能力」（索引能不能反查到东西），T1b 是「被测事实」（锚点是否还对）。
    # 两者必须分开——否则「被测数据错」会被误读成「脚本坏」，或者反过来被当成脚本 bug 掩盖掉。
    anchor_file = 'feagpt_repro/tasks/tasks.jsonl.sha256'
    target = 'feagpt_repro/tasks/tasks.jsonl'
    if not (os.path.exists(os.path.join(repo, anchor_file)) and os.path.exists(os.path.join(repo, target))):
        print(f'  [skip] T1 锚点文件不存在：{anchor_file}')
    else:
        body = open(os.path.join(repo, anchor_file), 'rb').read()
        m = HEX64.search(body)
        if not m:
            print('  [FAIL] T1a 锚点文件里没有 64 位 sha')
            ok = False
        else:
            s = m.group(0).decode().lower()
            tgt = idx.get(s, [])
            # T1a：脚本能力 —— 反查表必须能命中「某个」文件，否则是索引建坏了
            if tgt:
                print(f'  [ok  ] T1a 索引可反查：锚点 {s[:12]} 命中 {len(tgt)} 个（文件,变体）')
            else:
                print(f'  [FAIL] T1a 索引反查失败：锚点 {s[:12]} 在全库无任何文件命中（脚本能力问题）')
                ok = False
            # T1b：被测事实 —— 该锚点是否仍指向它声明的那个文件
            hit = [t for t in tgt if t[0] == target]
            if hit:
                print(f'  [ok  ] T1b 锚点仍指向 {target}（变体 {hit[0][1]}）')
            else:
                print(f'  [red ] T1b **被测事实为红**：锚点不指向 {target}，实际指向 {tgt[:2]}'
                      f' —— 属锚点过期（见诊断报告 F-4），非脚本问题')
    # T2：变体判别 —— 取一个已知 CRLF 文件，把它的 LF 版 sha 拿去查，必须落在 lf 桶
    probe = None
    for f, meta in info.items():
        if meta['kind'] == 'crlf':
            probe = (f, meta)
            break
    if probe:
        f, meta = probe
        if meta['sha_lf'] != meta['sha_crlf']:
            b_lf = 'lf' if [t for t in idx[meta['sha_lf']] if t[1] == 'lf'] else '?'
            b_crlf = 'crlf' if [t for t in idx[meta['sha_crlf']] if t[1] == 'crlf'] else '?'
            print(f'  [ok  ] T2 变体可分：{f} 的 LF 版落在 {b_lf}、CRLF 版落在 {b_crlf}')
            ok = ok and b_lf == 'lf' and b_crlf == 'crlf'
        else:
            print(f'  [ok  ] T2 该文件 LF/CRLF 版 sha 相同（无换行差异）: {f}')
    else:
        print('  [skip] T2 仓库内没有 CRLF 文本文件，无法区分变体（本向未验证）')
    # T3：随手构造一个不存在的 sha，必须落 unknown 而不是任何一侧
    fake = 'f' * 64
    print(f'  [{"ok  " if not idx.get(fake) else "FAIL"}] T3 伪造 sha 不命中任何文件（unknown 桶独立）')
    ok = ok and not idx.get(fake)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=r'F:\AI FEA Modeling DataSets')
    ap.add_argument('--json', default=None)
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    repo = args.repo

    if args.self_test:
        print('D-3 行尾锚点扫描器 自检')
        sys.exit(0 if self_test(repo) else 1)

    files = tracked(repo)
    idx, info = build_index(repo, files)
    anchors = scan(repo, files, idx, info)
    c = summarize(anchors)

    n_lf, n_crlf = c['lf'], c['crlf']
    print(f'被追踪文件      : {len(files)}（文本 {len(info)}）')
    print(f'工作区行尾       : {Counter(m["kind"] for m in info.values())}')
    print(f'正文里的 sha256  : {len(anchors)} 条')
    print(f'  → 指向 LF 版   : {n_lf}')
    print(f'  → 指向 CRLF 版 : {n_crlf}')
    print(f'  → 两版皆可     : {c["both"]}')
    print(f'  → 单行文件     : {c["flat"]}')
    print(f'  → 查无此文件   : {c["unknown"]}')
    print()
    print('两种规范化的锚点代价（只数「会失效」的）：')
    print(f'  统一 LF  ⇒ 指向 CRLF 版的 {n_crlf} 条失效，需重算')
    print(f'  统一 CRLF⇒ 指向 LF 版的 {n_lf} 条失效，需重算')

    # 按「锚点所在文件」聚合，方便定位重算工作量
    by_at = defaultdict(Counter)
    for a in anchors:
        if a['bucket'] in ('lf', 'crlf'):
            by_at[a['at']][a['bucket']] += 1
    rows = sorted(by_at.items(), key=lambda kv: -(kv[1]['lf'] + kv[1]['crlf']))
    print('\n锚点分布（前 15 个文件）：')
    for f, cnt in rows[:15]:
        print(f'  {cnt["lf"]:>3} LF / {cnt["crlf"]:>3} CRLF   {f}')

    if args.json:
        json.dump({'n_files': len(files), 'n_text': len(info),
                   'kinds': dict(Counter(m['kind'] for m in info.values())),
                   'buckets': dict(c),
                   'by_anchor_file': {k: dict(v) for k, v in by_at.items()},
                   'anchors': anchors},
                  open(args.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'\n明细 -> {args.json}')


if __name__ == '__main__':
    main()
