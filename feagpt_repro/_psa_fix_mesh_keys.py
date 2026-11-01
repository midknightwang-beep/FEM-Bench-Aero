# -*- coding: utf-8 -*-
"""T-PSA 阶段 2 修正 1（p3 → p4）：把 `mesh.order` / `mesh.refine_le` 从 prompt 删除。

为什么必须删（本轮实测，不是推测）：
  这两个键在 `schema_task.json` 的 `mesh.properties` 里**合法**，所以结构校验放行；
  但全部 64 个 gold spec 的 `mesh` **一个都没有它们** —— gold 用的是
  `element_order` / `refine_at_leading_edge`，且这两个在 `evaluate.EXEC_CONFIG_KEYS` 里被
  「REPORTED NOT GATED」豁免。`spec_fidelity` 对候选多写的键按**自创键**判 FAIL。
  ⇒ 全量重跑后 **33 条由 spec_pass 变 spec_fail**（wingbox 25 + open_hole_panel 8），
     新批 59 条 spec 里有 38 条写了 order 和/或 refine_le。
  ⇒ **「schema 允许」不等于「能写」；真正的白名单是 `gold ∩ EXEC 豁免`。**

对照：旧 prompt 只写「网格键 size_chord/size_span（翼盒）、size（板壳类）」，不提 order/refine_le，
所以旧批不写、不挂 —— 这是**本轮改动自身引入的回归**，不是模型变差。

用法：
  python _psa_fix_mesh_keys.py --check
  python _psa_fix_mesh_keys.py --apply
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, 'gen_candidates_v2.js')

# p3（阶段 2 首次写回）的 SYS sha
SHA_P3 = 'd9c0b02d041190891abd7c01147eb30094a754e27d823aeed6599951a0eb870e'
# p4（本次修正后）的 SYS sha，apply 后填
SHA_P4 = ''

OLD1 = ('网格块 mesh：**所有族都必须写 size_chord 与 size_span 两个键**'
        '（板壳类也用这两个键名——**没有 size 这个键**，写 size 会被拒）；'
        '可选 order（1 或 2）、refine_le（true/false）。')
NEW1 = ('网格块 mesh：**只写 size_chord 与 size_span 两个键**'
        '（板壳类也用这两个键名——**没有 size 这个键**）；'
        '**不要写 order、refine_le 或任何别的网格键**（多写的键会被判成自造键）。')

OLD2 = '· mesh：size_chord / size_span（**两者必填**）/ order（1 或 2）/ refine_le（true/false）'
NEW2 = '· mesh：**只有** size_chord / size_span（两者必填），**不要写 order / refine_le 或任何别的网格键**'

REPL = [('MESH-词汇约定', OLD1, NEW1), ('MESH-白名单', OLD2, NEW2)]


def extract(src):
    head = 'const SYS = `'
    i = src.index(head) + len(head)
    j = src.index('`;', i)
    return i, j


def sha(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', action='store_true')
    g.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    raw = open(GEN, 'rb').read().decode('utf-8')
    if raw.count('\r\n') != raw.count('\n'):
        print('[FATAL] 行尾不统一，拒绝处理')
        return 2
    src_lf = raw.replace('\r\n', '\n')
    i, j = extract(src_lf)
    cur = src_lf[i:j]
    cur_sha = sha(cur)

    n_fixed = cur.count('order（1 或 2）') + cur.count('refine_le（true/false）')
    if n_fixed == 0 and '任何别的网格键' in cur:
        print(f'已修正（幂等）：SYS sha = {cur_sha}')
        return 0
    if cur_sha != SHA_P3:
        print(f'[FATAL] 当前 SYS sha = {cur_sha}，期望 p3 = {SHA_P3}')
        return 2

    new = cur
    for tag, old, rep in REPL:
        n = new.count(old)
        if n != 1:
            print(f'[FATAL] {tag} 命中 {n} 次（必须 1 次）')
            return 2
        new = new.replace(old, rep)

    new_sha = sha(new)
    print(f'p3 SYS sha = {cur_sha}')
    print(f'p4 SYS sha = {new_sha}')
    print(f'长度 {len(cur)} → {len(new)}')
    # 残留检查：这两处一旦漏改，重跑会再次全挂，必须在写回前拦住
    for bad in ('可选 order（1 或 2）', 'refine_le（true/false）'):
        if bad in new:
            print(f'[FATAL] 残留未改：{bad}')
            return 2
    if '任何别的网格键' not in new:
        print('[FATAL] 新的否定表述没进去')
        return 2

    if a.check:
        print('--check：尚未修正')
        return 1

    out_lf = src_lf[:i] + new + src_lf[j:]
    out = out_lf.replace('\n', '\r\n')
    open(GEN, 'wb').write(out.encode('utf-8'))

    back = open(GEN, 'rb').read().decode('utf-8')
    bl = back.replace('\r\n', '\n')
    bi, bj = extract(bl)
    got = sha(bl[bi:bj])
    print(f'回读 sha = {got}  {"OK" if got == new_sha else "MISMATCH"}')
    print(f'回读 CRLF 一致 = {back.count(chr(13)+chr(10)) == back.count(chr(10))}')
    if got != new_sha:
        return 2
    print(f'请把 SHA_P4 填为 {new_sha}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
