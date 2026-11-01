# -*- coding: utf-8 -*-
"""T-PSA 阶段 2 的 C5 变体构建器（**只产出影子 prompt 文件，不动源码**）。

背景（p4 全量实测）：
  · p4 把首轮有效题数从 glm 5→47、ds 3→57，效率收益确凿；
  · 但 ds 出现 **1 条 fabricated**（`L3_fuselage_barrel_d1600_l1600_str8_frm3` 把
    题面「若干个普通框」的 `n_frames` 写成 **0**），正是 prompt 自己禁止的「不得填 0」；
  · 同批另 1 条 `L3_stiffened_panel_700x600_str4`（题面「若干根长桁」）直接**漏写** `n_stringers`。
  两条在基线里都是 `clarify_ok`（问得对）。

C5 的作用：把「数量铁律优先于写全」写成硬约束，消掉「必填」与「必须澄清」的冲突。
**不动 SYS 常量**：只在影子文件里插入这一行，用 `--sys-file` 跑；源码 sha 保持 p4 的 `58fca788…`。

用法：
  python _psa_build_p5.py --out <path>     # 产出影子 prompt
  python _psa_build_p5.py --check          # 只核对锚点与 sha，不写文件
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, 'gen_candidates_v2.js')

SYS_SHA_P4 = '58fca788957c50a7915490e525f92ae7bcc01738ca10754fcd3d45e4e7aa6892'

ANCHOR = ('  · material：name / youngs_modulus / poisson_ratio / density / '
          'yield_strength（**五者必填**）')

# p5a：加在 material 白名单之后（实测**无效**，6/6 与 p4 逐条一致 ⇒ 位置太弱）
C5 = (
    '\n★ **数量铁律优先于「写全」**：n_stringers / n_stringers_per_skin / n_frames / n_ribs 这几类'
    '数量字段，题面没给数就【澄清】，**不得填 0、不得按惯例假设**。上面说的「必填」只约束'
    '**块**与**固定键**（material 五键 / mesh 两键 / load 三键 / 顶层七块），**不约束数量字段**。'
)
MARK = '数量铁律优先于「写全」'

# p5b：改在**推压源本身**（C1 的「七个块全部必填」）——这是模型宁编不澄清的直接压力点
C1_ANCHOR = '**name / material / structure / mesh / load / bc / analysis 全部必填**（一个都不能省）；'
C1_WITH = ('**name / material / structure / mesh / load / bc / analysis 全部必填**（一个都不能省）'
           '——**但若按下面「数量类字段铁律」需要澄清，就直接输出 {"clarify":["字段名", …]}，'
           '不要为凑齐七个块而编数、也不要把数量填 0**；')
MARK_B = '不要为凑齐七个块而编数'

# p5c：p5b + 把「四族键名总表」里柱壳那行的 n_frames 也标注清楚
# 依据：p5b 只修好了加筋板（它的表行本来就带「没给根数⇒澄清」的注解），柱壳那行没有，
#       所以模型把那行当「必写清单」，写 0。
BARREL_ANCHOR = '  · fuselage_barrel ⇒ 写 structure.params：diameter/length/thickness/n_stringers/n_frames。'
BARREL_WITH = ('  · fuselage_barrel ⇒ 写 structure.params：diameter/length/thickness/n_stringers/n_frames'
               '（**n_stringers 与 n_frames 题面没给数 ⇒ 澄清，不得填 0、不得按惯例假设**）。')
MARK_C = 'n_frames 题面没给数 ⇒ 澄清'


def extract_sys(src):
    i = src.index('const SYS = `')
    j = src.index('`;', i + len('const SYS = `'))
    return src[i + len('const SYS = `'):j]


def sha(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def build(variant='a'):
    src = open(GEN, 'rb').read().decode('utf-8').replace('\r\n', '\n')
    cur = extract_sys(src)
    if MARK_B in cur or MARK in cur or MARK_C in cur:
        raise SystemExit('[FATAL] SYS 里已有 C5 标记 ⇒ 源码已被改过，本脚本只对 p4 生效')
    new = cur
    if variant in ('b', 'c'):
        if new.count(C1_ANCHOR) != 1:
            raise SystemExit(f'[FATAL] C1 锚点出现 {new.count(C1_ANCHOR)} 次（应为 1）')
        new = new.replace(C1_ANCHOR, C1_WITH)
    if variant == 'c':
        if new.count(BARREL_ANCHOR) != 1:
            raise SystemExit(f'[FATAL] 柱壳行锚点出现 {new.count(BARREL_ANCHOR)} 次（应为 1）')
        new = new.replace(BARREL_ANCHOR, BARREL_WITH)
    if variant == 'a':
        if new.count(ANCHOR) != 1:
            raise SystemExit(f'[FATAL] material 锚点出现 {new.count(ANCHOR)} 次（应为 1）')
        new = new.replace(ANCHOR, ANCHOR + C5)
    marks = {'a': MARK, 'b': MARK_B, 'c': MARK_C}
    if new.count(marks[variant]) != 1:
        raise SystemExit(f'[FATAL] 变体 {variant} 的标记数 != 1')
    return cur, new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--variant', default='a', choices=('a', 'b', 'c'))
    a = ap.parse_args()

    cur, new = build(a.variant)
    cs, ns = sha(cur), sha(new)
    print(f'p4 SYS sha = {cs}  (期望 {SYS_SHA_P4})')
    if cs != SYS_SHA_P4:
        print('[FATAL] 源码不是 p4 状态，禁止继续')
        return 2
    print(f'p5 SYS sha = {ns}')
    print(f'长度 {len(cur)} → {len(new)}（+{len(new) - len(cur)} 字符）')
    if a.check:
        return 0
    if not a.out:
        print('[FATAL] 需要 --out 或 --check')
        return 2
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new)
    print(f'已写 {a.out}（{os.path.getsize(a.out)} 字节）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
