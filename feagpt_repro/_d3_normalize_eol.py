# -*- coding: utf-8 -*-
"""T-D3：把被追踪的文本文件就地规范化为 CRLF（不动 git 索引、不动 blob）。

为什么不用 `git checkout-index -a -f`：
  实测无效 —— 加了 `* text=auto eol=crlf` 之后跑 `git checkout-index -a -f`，
  工作区 928 个 LF 文件一个都没变（真实字节统计：lf 928 -> 928）。
  ⇒ **不能把「格式化成功」建立在 git 的惰性行为上**，必须自己写字节、自己验字节。

语义（与 _d3_eol_anchor_scan.py 的 variants() 严格一致）：
  crlf = raw.replace(b'\\r\\n', b'\\n').replace(b'\\n', b'\\r\\n')
  即「先归一到 LF、再全部转 CRLF」；末尾无换行的情形天然保留（末尾不是 \\n 就不会被加 \\r）。

自检（--self-test）：五向，全部在内存里做，不落盘
  T1 幂等：对已是 CRLF 的内容再转一次，字节不变
  T2 无损：转完再归一回 LF，必须与原 LF 版逐字节相等
  T3 末行：不以 \\n 结尾的内容，转换后仍不以 \\n 结尾（不得凭空多出换行）
  T4 空文件：长度为 0 必须原样返回（不得变成 b'\\r\\n'）
  T5 mixed：混行的内容必须被统一成纯 CRLF，且行数不变
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def to_crlf(raw: bytes) -> bytes:
    if not raw:
        return raw
    return raw.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')


def to_lf(raw: bytes) -> bytes:
    if not raw:
        return raw
    return raw.replace(b'\r\n', b'\n')


def eol_attrs(repo: str, files):
    """批量取 `git check-attr eol` —— 规则以 .gitattributes 为准，工具不得自己另立一套。

    教训：第一版一刀切转 CRLF，把两个 `*.sh` 也转成了 CRLF，而同一批里写的 .gitattributes
    声明 `*.sh text eol=lf` ⇒ **工具与规则自相矛盾**，git 下次 checkout 又会把它写回 LF，
    等于制造了一个「本地改了、clone 没改」的新漂移面。规则只有一处，工具必须读它。
    """
    if not files:
        return {}
    p = subprocess.run(['git', 'check-attr', '--stdin', '-z', 'eol'], cwd=repo,
                       input='\0'.join(files).encode('utf-8'),
                       capture_output=True)
    parts = p.stdout.split(b'\0')
    out = {}
    for i in range(0, len(parts) - 2, 3):
        path = parts[i].decode('utf-8', 'replace')
        val = parts[i + 2].decode('utf-8', 'replace')
        out[path] = val
    return out


def is_binary(raw: bytes) -> bool:
    return b'\x00' in raw[:8192]


def kind(raw: bytes) -> str:
    if not raw:
        return 'empty'
    if is_binary(raw):
        return 'binary'
    crlf = raw.count(b'\r\n')
    lf = raw.count(b'\n')
    if crlf == 0:
        return 'lf' if lf else 'flat'
    if crlf == lf:
        return 'crlf'
    return 'mixed'


def self_test() -> bool:
    ok = True
    cases = [
        ('T1 幂等', b'a\r\nb\r\n', b'a\r\nb\r\n'),
        ('T3 末行无换行', b'a\r\nb', b'a\r\nb'),
        ('T4 空文件', b'', b''),
        ('T5 混行统一', b'a\r\nb\nc', b'a\r\nb\r\nc'),
    ]
    for name, src, want in cases:
        got = to_crlf(src)
        if got == want:
            print(f'  [ok  ] {name}')
        else:
            print(f'  [FAIL] {name}: 得到 {got!r} 期望 {want!r}')
            ok = False
    # T2 无损：CRLF 化 -> 归回 LF 必须等于原 LF 版
    src = b'x\n\ny\r\nz\n'
    lf = src.replace(b'\r\n', b'\n')
    back = to_crlf(src).replace(b'\r\n', b'\n')
    if back == lf:
        print('  [ok  ] T2 无损（转 CRLF 再归回 LF 与原 LF 版逐字节相等）')
    else:
        print(f'  [FAIL] T2 无损: {back!r} != {lf!r}')
        ok = False
    return ok


def tracked(repo: str):
    out = subprocess.run(['git', '-c', 'core.quotepath=false', 'ls-files'], cwd=repo,
                         capture_output=True, text=True, encoding='utf-8')
    if out.returncode != 0:
        raise SystemExit(f'git ls-files 失败: {out.stderr}')
    return [f for f in out.stdout.split('\n') if f.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=r'F:\AI FEA Modeling DataSets')
    ap.add_argument('--apply', action='store_true', help='不带此参数只做 dry-run')
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()

    if args.self_test:
        print('D-3 行尾规范化器 自检')
        sys.exit(0 if self_test() else 1)

    import os
    repo = args.repo
    files = tracked(repo)
    attrs = eol_attrs(repo, files)
    stat = {'lf': 0, 'mixed': 0, 'crlf': 0, 'flat': 0, 'binary': 0, 'empty': 0, 'missing': 0}
    changed = 0
    forced_lf = 0
    fails = []
    for f in files:
        p = os.path.join(repo, f)
        try:
            raw = open(p, 'rb').read()
        except OSError:
            stat['missing'] += 1
            continue
        k = kind(raw)
        stat[k] = stat.get(k, 0) + 1
        want = attrs.get(f, 'unspecified')
        if k in ('binary', 'empty'):
            continue
        if want == 'lf':
            # 属性表说 LF（例如 *.sh）⇒ 必须转回 LF，否则制造「本地 CRLF / clone LF」新漂移
            if k in ('crlf', 'mixed'):
                new = to_lf(raw)
                if new.replace(b'\r\n', b'\n') != raw.replace(b'\r\n', b'\n'):
                    fails.append((f, '转 LF 后内容不等')); continue
                changed += 1; forced_lf += 1
                if args.apply:
                    with open(p, 'wb') as fh:
                        fh.write(new)
            continue
        if k not in ('lf', 'mixed'):
            continue
        new = to_crlf(raw)
        # 转换后必须满足：纯 CRLF、行数与原来 LF 计数一致、归一回 LF 与原 LF 版相等
        if new.count(b'\n') != new.count(b'\r\n'):
            fails.append((f, '转换后不是纯 CRLF')); continue
        if new.replace(b'\r\n', b'\n') != raw.replace(b'\r\n', b'\n'):
            fails.append((f, '转换后归一回 LF 与原文不等')); continue
        changed += 1
        if args.apply:
            with open(p, 'wb') as fh:
                fh.write(new)
    print(f'被追踪文件 {len(files)}；分类 {stat}')
    print(f'{"已处理" if args.apply else "待处理(dry-run)"}: {changed} 个（其中属性要求 LF 的 {forced_lf} 个）')
    if fails:
        print(f'!! 校验失败 {len(fails)} 个（一律未写）:')
        for f, why in fails[:10]:
            print(f'   {f}  {why}')
        sys.exit(1)
    if not args.apply:
        print('（dry-run，未写盘；加 --apply 执行）')


if __name__ == '__main__':
    main()
