# -*- coding: utf-8 -*-
"""T-D3：把被追踪的文本文件就地规范化为 CRLF（不动 git 索引、不动 blob）。

为什么不用 `git checkout-index -a -f`：
  实测无效 —— 加了 `* text=auto eol=crlf` 之后跑 `git checkout-index -a -f`，
  工作区 928 个 LF 文件一个都没变（真实字节统计：lf 928 -> 928）。
  ⇒ **不能把「格式化成功」建立在 git 的惰性行为上**，必须自己写字节、自己验字节。

语义（与 _d3_eol_anchor_scan.py 的 variants() 严格一致）：
  crlf = raw.replace(b'\\r\\n', b'\\n').replace(b'\\n', b'\\r\\n')
  即「先归一到 LF、再全部转 CRLF」；末尾无换行的情形天然保留（末尾不是 \\n 就不会被加 \\r）。

扫描源（F-12，2026-11-01）：
  `git ls-files --cached --others --exclude-standard` —— **已追踪 + 未追踪（不含 ignore）**。
  为什么必须含未追踪：只扫已追踪时，**每一个新写出的文件都会漏一次**，而且漏得毫无征兆 ——
  工具自己复验报「待处理 0」、`git status --porcelain` 也干净（`text=auto` 归一后工作区与索引
  无差异）⇒ **两个检查都说没事**，只有跨仓库 clone 的 C7 才看得见。本轮 `_f9_artifact_freshness.py`
  就是这样红的（同一天还复现两次：`cat >>` 追加日志、`newline=''` 写回 md）。
  ⇒ 正确顺序是 `git add` → `--apply` → 提交；而工具不再依赖这个顺序。

自检（--self-test）：六向，全部在内存/临时目录里做，不落主仓库
  T1 幂等：对已是 CRLF 的内容再转一次，字节不变
  T2 无损：转完再归一回 LF，必须与原 LF 版逐字节相等
  T3 末行：不以 \\n 结尾的内容，转换后仍不以 \\n 结尾（不得凭空多出换行）
  T4 空文件：长度为 0 必须原样返回（不得变成 b'\\r\\n'）
  T5 mixed：混行的内容必须被统一成纯 CRLF，且行数不变
  T6 未追踪可见（F-12）：临时仓库里写一个 LF 文件但**不 add**，
     T6a 它必须进入扫描集；T6b 负向（退回只扫已追踪）必须扫不到；T6c 真跑 --apply 后字节必须变 CRLF
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
    return self_test_untracked() and ok


def scan_files(repo: str, include_untracked: bool = True):
    """返回 (待扫文件列表, 已追踪数, 未追踪数)。

    `include_untracked=False` 只给自检做负向用（复现 F-12 的旧行为），CLI 不暴露。
    """
    def ls(args):
        out = subprocess.run(['git', '-c', 'core.quotepath=false', 'ls-files'] + args,
                             cwd=repo, capture_output=True, text=True, encoding='utf-8')
        if out.returncode != 0:
            raise SystemExit(f'git ls-files {" ".join(args)} 失败: {out.stderr}')
        return [f for f in out.stdout.split('\n') if f.strip()]

    cached = ls(['--cached'])
    if not include_untracked:
        return cached, len(cached), 0
    cset = set(cached)
    others = [f for f in ls(['--others', '--exclude-standard']) if f not in cset]
    return cached + others, len(cached), len(others)


def self_test_untracked() -> bool:
    """T6：未追踪文件必须被扫到（F-12）。

    判据落在**根因**（扫描源含不含未追踪）而不是只落在后果（字节变没变）——
    只断后果的话，将来若有人给「已追踪」另开一条补救路径，自检仍会绿而洞还在。
    """
    import os
    import shutil
    import tempfile

    ok = True
    tmp = tempfile.mkdtemp(prefix='d3_untracked_')
    try:
        subprocess.run(['git', 'init', '-q'], cwd=tmp, capture_output=True)
        with open(os.path.join(tmp, '.gitattributes'), 'w', newline='') as fh:
            fh.write('* text=auto eol=crlf\n')
        # 规则文件必须**已追踪**（真实仓库就是这样）—— 否则它自己也算未追踪，
        # 夹具就多出一个成员，断言 untracked==1 会假红（F-9 自检撞过同一个坑）。
        subprocess.run(['git', 'add', '.gitattributes'], cwd=tmp, capture_output=True)
        target = os.path.join(tmp, 'new_file.txt')
        with open(target, 'wb') as fh:
            fh.write(b'alpha\nbeta\n')          # LF，且**不 add**

        files, n_cached, n_untracked = scan_files(tmp)
        if 'new_file.txt' in files and n_untracked == 1:
            print('  [ok  ] T6a 未追踪文件进入扫描集（F-12）')
        else:
            print(f'  [FAIL] T6a 未追踪未进入扫描集: files={files} '
                  f'cached={n_cached} untracked={n_untracked}')
            ok = False

        # 负向：退回「只扫已追踪」（= 修之前的实现）必须扫不到它。
        old_files, _, _ = scan_files(tmp, include_untracked=False)
        if 'new_file.txt' not in old_files:
            print('  [ok  ] T6b 负向：只扫已追踪时该文件确实扫不到（证明 T6a 会红）')
        else:
            print('  [FAIL] T6b 负向失效：只扫已追踪竟然也扫到了')
            ok = False

        # 后果：真跑 --apply，字节必须变成 CRLF（命令行路径也要走通）
        r = subprocess.run([sys.executable, os.path.abspath(__file__),
                            '--repo', tmp, '--apply'],
                           capture_output=True, text=True, encoding='utf-8')
        raw = open(target, 'rb').read()
        if r.returncode == 0 and raw == b'alpha\r\nbeta\r\n':
            print('  [ok  ] T6c --apply 后未追踪文件真的被改成 CRLF')
        else:
            print(f'  [FAIL] T6c rc={r.returncode} 字节={raw!r} 输出={r.stdout[-400:]}')
            ok = False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ok


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
    files, n_cached, n_untracked = scan_files(repo)
    attrs = eol_attrs(repo, files)
    stat = {'lf': 0, 'mixed': 0, 'crlf': 0, 'flat': 0, 'binary': 0, 'empty': 0, 'missing': 0}
    changed = 0
    forced_lf = 0
    touched = []
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
                touched.append((f, 'CRLF->LF'))
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
        touched.append((f, 'LF->CRLF'))
        if args.apply:
            with open(p, 'wb') as fh:
                fh.write(new)
    print(f'扫描 {len(files)} 个（已追踪 {n_cached} + 未追踪 {n_untracked}）；分类 {stat}')
    print(f'{"已处理" if args.apply else "待处理(dry-run)"}: {changed} 个（其中属性要求 LF 的 {forced_lf} 个）')
    # 必须点名 —— 「待处理 N 个」不说是谁，等于还得另找一条路去查，
    # 而 F-12 的教训正是「两条检查都说没事」；明细是第三条、也是最直接的那条。
    for f, how in touched[:10]:
        print(f'   {how}  {f}')
    if len(touched) > 10:
        print(f'   …… 另有 {len(touched) - 10} 个未列出')
    if fails:
        print(f'!! 校验失败 {len(fails)} 个（一律未写）:')
        for f, why in fails[:10]:
            print(f'   {f}  {why}')
        sys.exit(1)
    if not args.apply:
        print('（dry-run，未写盘；加 --apply 执行）')


if __name__ == '__main__':
    main()
