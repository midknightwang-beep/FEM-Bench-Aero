# -*- coding: utf-8 -*-
"""T-PSA 阶段 2：把 B+ 变体（C1–C4）**正式写回** gen_candidates_v2.js 的 SYS 常量。

纪律：
  1. 替换文本**不复刻**，全部 import 自 `_psa_build_prompt.py`（规则只有一处实现）；
  2. 写回前断言「当前 SYS 的 sha == 契约前值」，防止对已改过的文件二次施加；
  3. 写回后断言「重新提取的 SYS == 预期新 SYS」，防止行尾处理把字节改坏；
  4. **行尾**：仓库统一 CRLF，写回必须逐字节保持 CRLF；
     但替换按 LF 版做 —— 因为 Node 解析模板字面量时会把 <CR><LF> 规范化为 <LF>
     （ES 规范），所以运行时 SYS 是 LF 版，`--print-prompt-sha` 报的也是 LF 版 sha。

用法：
  python _psa_apply_prompt.py --check     # 只判是否已应用（幂等检查）
  python _psa_apply_prompt.py --apply     # 施加写回
"""
import argparse
import hashlib
import os
import sys

import _psa_build_prompt as B

# 阶段 2 实施后的 SYS sha（2026-11-01 写回时实测）。幂等判据用**这个常量**而不是
# 「文本特征子串」—— 特征子串在 prompt 被再次编辑时会静默失效，而这个 sha 只要对不上
# 就会走 FATAL 分支，不会把「改坏了」误判成「已应用」。
SYS_SHA_AFTER = 'd9c0b02d041190891abd7c01147eb30094a754e27d823aeed6599951a0eb870e'


def sha(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def expected_new(sys_lf):
    """对 LF 版 SYS 施加 bplus 变体，返回新 SYS。任一处不恰好命中 1 次即抛异常。"""
    new = sys_lf
    for tag, old, rep in B.VARIANTS['bplus']:
        n = new.count(old)
        if n != 1:
            raise SystemExit(f'[FATAL] {tag} 命中 {n} 次（必须恰好 1 次）')
        new = new.replace(old, rep)
    return new


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', action='store_true')
    g.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    raw_bytes = open(B.GEN, 'rb').read()
    raw = raw_bytes.decode('utf-8')
    n_crlf = raw.count('\r\n')
    n_lf = raw.count('\n')
    print(f'文件 {os.path.basename(B.GEN)}: {len(raw_bytes)} B, CRLF={n_crlf}, 总换行={n_lf}')
    if n_crlf != n_lf:
        print('[FATAL] 文件行尾不统一（存在裸 LF），拒绝写回：会破坏 R67 零差异')
        return 2

    src_lf = raw.replace('\r\n', '\n')
    cur = B.extract_sys(src_lf)
    cur_sha = sha(cur)

    # 幂等：先认后值，再认前值。顺序不能反 —— 已应用时 expected_new() 会因 C2 命中 0 次而抛异常。
    if cur_sha == SYS_SHA_AFTER:
        print(f'已应用（幂等）：当前 SYS sha = {cur_sha}')
        print('无需写回。')
        return 0
    if cur_sha != B.SYS_SHA_BEFORE:
        print(f'[FATAL] 当前 SYS sha = {cur_sha}')
        print(f'        既不是前值 {B.SYS_SHA_BEFORE}，也不是后值 {SYS_SHA_AFTER}')
        print('        ⇒ 源码被第三方改过，禁止继续')
        return 2

    target = expected_new(cur)
    target_sha = sha(target)
    if target_sha != SYS_SHA_AFTER:
        print(f'[FATAL] 由当前前值算出的后值 sha={target_sha}，与记录的 {SYS_SHA_AFTER} 不符')
        print('        ⇒ 替换语料被改过（_psa_build_prompt.py），禁止继续')
        return 2

    print(f'前值 SYS sha = {cur_sha}')
    print(f'后值 SYS sha = {target_sha}')
    print(f'长度 {len(cur)} → {len(target)} 字符（+{len(target) - len(cur)}）')

    # 判据（写回前先在内存里验，避免落盘后才发现不合格）
    fails = []
    for k in ('youngs_modulus', 'poisson_ratio', 'density', 'yield_strength'):
        if k not in target:
            fails.append(f'P1 缺 {k}')
    if '全部必填' not in target:
        fails.append('P2 无「全部必填」表述')
    for blk in ('material', 'structure', 'mesh', 'load', 'bc', 'analysis'):
        if blk not in target:
            fails.append(f'P2 缺块名 {blk}')
    if '没有 size 这个键' not in target:
        fails.append('P3 未显式否定 size')
    if 'size_chord' not in target or 'size_span' not in target:
        fails.append('P3 缺 size_chord/size_span')
    if '清单外的键一律不写' not in target:
        fails.append('P4 缺 C4 白名单表述')
    if fails:
        print('[FATAL] 文本判据未过：' + '；'.join(fails))
        return 2
    print('文本判据 P1/P2/P3/P4 通过')

    if a.check:
        print('--check：当前源码**尚未**应用阶段 2 改动（上面是应用后会得到的值）')
        return 1

    # 写回：替换 SYS 内容，其余字节不动；LF → CRLF
    head = 'const SYS = `'
    i = src_lf.index(head) + len(head)
    j = src_lf.index('`;', i)
    out_lf = src_lf[:i] + target + src_lf[j:]
    out = out_lf.replace('\n', '\r\n')
    open(B.GEN, 'wb').write(out.encode('utf-8'))

    # 回读复验：必须能提取出 target，且行尾仍全 CRLF
    back = open(B.GEN, 'rb').read().decode('utf-8')
    back_lf = back.replace('\r\n', '\n')
    got = B.extract_sys(back_lf)
    got_sha = sha(got)
    ok_crlf = back.count('\r\n') == back.count('\n')
    print(f'回读 SYS sha = {got_sha}  {"OK" if got_sha == target_sha else "MISMATCH"}')
    print(f'回读行尾全 CRLF = {ok_crlf}')
    if got_sha != target_sha or not ok_crlf:
        print('[FATAL] 回读复验失败')
        return 2
    print(f'已写回 {B.GEN}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
