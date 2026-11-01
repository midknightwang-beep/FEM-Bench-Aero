# -*- coding: utf-8 -*-
"""把 p5c 写回 `gen_candidates_v2.js` 的 SYS 常量（阶段 2 第二次改写）。

写回内容与 `_psa_build_p5.py --variant c` **逐字节一致**（同一份常量定义，不另写一套）。

行尾：源码是 CRLF，Node 解析模板字面量时会把 CRLF 规范化为 LF（ES 规范），
所以 **sha 必须按 LF 版算**（`--print-prompt-sha` 的口径）。
两处替换的锚点与替换文本都**不含换行**，因此可以直接在原始文本上 replace，CRLF 不受影响。

用法：
  python _psa_apply_p5.py --check   # 只预演
  python _psa_apply_p5.py --apply
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _psa_build_p5 as B  # noqa: E402

GEN = os.path.join(HERE, 'gen_candidates_v2.js')
SYS_SHA_P4 = B.SYS_SHA_P4
SYS_SHA_P5C = 'c37862f9992c06293fe92da62cb2089598f880c58be398e10cd226055512c979'


def extract_from_raw(raw):
    """从**保留 CRLF 的原始文本**里取 SYS，并把 CRLF 折叠成 LF（与 Node 口径一致）。"""
    lf = raw.replace('\r\n', '\n')
    i = lf.index('const SYS = `')
    j = lf.index('`;', i + len('const SYS = `'))
    return lf[i + len('const SYS = `'):j]


def sha(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()

    raw = open(GEN, 'rb').read().decode('utf-8')
    cur = extract_from_raw(raw)
    cs = sha(cur)
    print(f'当前 SYS sha = {cs}')

    if cs == SYS_SHA_P5C:
        print('已应用（幂等）：SYS 已是 p5c，无需写回。')
        return 0
    if cs != SYS_SHA_P4:
        print(f'[FATAL] 当前既不是 p4({SYS_SHA_P4[:16]}…) 也不是 p5c({SYS_SHA_P5C[:16]}…)')
        print('        ⇒ 源码被第三方改过，禁止继续')
        return 2

    # 断言锚点在原始文本里各出现 1 次，且替换文本不含换行
    for name, s in (('C1_ANCHOR', B.C1_ANCHOR), ('BARREL_ANCHOR', B.BARREL_ANCHOR)):
        n = raw.count(s)
        if n != 1:
            print(f'[FATAL] {name} 在源码里出现 {n} 次（应为 1）')
            return 2
    for name, s in (('C1_WITH', B.C1_WITH), ('BARREL_WITH', B.BARREL_WITH)):
        if '\n' in s or '\r' in s:
            print(f'[FATAL] {name} 含换行 ⇒ 不能直接在 CRLF 原文上替换')
            return 2

    new_raw = raw.replace(B.C1_ANCHOR, B.C1_WITH).replace(B.BARREL_ANCHOR, B.BARREL_WITH)
    new_sys = extract_from_raw(new_raw)
    ns = sha(new_sys)
    print(f'写回后 SYS sha = {ns}（期望 {SYS_SHA_P5C}）')
    print(f'SYS 长度 {len(cur)} → {len(new_sys)}（+{len(new_sys) - len(cur)} 字符）')
    if ns != SYS_SHA_P5C:
        print('[FATAL] 预期后值不匹配，未写盘')
        return 2
    if not (a.apply and not a.check):
        print('预演通过（未写盘）。加 --apply 执行。')
        return 0
    with open(GEN, 'wb') as f:
        f.write(new_raw.encode('utf-8'))
    print(f'已写回 {GEN}')
    # 写回后立刻复验行尾与 sha
    chk = open(GEN, 'rb').read().decode('utf-8')
    print(f'CRLF 行 {chk.count(chr(13) + chr(10))} / 总行 {chk.count(chr(10))}')
    print(f'复验 SYS sha = {sha(extract_from_raw(chk))}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
