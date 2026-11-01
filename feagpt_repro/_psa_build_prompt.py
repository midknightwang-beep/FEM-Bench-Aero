# -*- coding: utf-8 -*-
"""T-PSA：生成「方案 B」影子 prompt（确定性、可复现）。

做三件事：
  1. 从 gen_candidates_v2.js 里**逐字节**提取 SYS 常量（提取结果 sha256 必须等于契约 §0.1 前值，
     不等就退出 —— 防止定位错位后静默用半截 prompt 去跑模型）；
  2. 对 SYS 施加 C1/C2/C3 三处替换，每处**必须恰好命中 1 次**（0 次 = prompt 已变、脚本过期；
     >1 次 = 替换文本不唯一、会改坏别处）；
  3. 写出影子 prompt 并打印 sha256 与逐行 diff。

用法：
  python _psa_build_prompt.py --out "$TEMP/sys_psa_v1.txt"
  python _psa_build_prompt.py --out "$TEMP/sys_psa_v1.txt" --check   # 只校验，不写
"""
import argparse
import hashlib
import os
import sys

# 契约 §0.1 前值：SYS 的 sha256（R53 口径，node gen_candidates_v2.js --print-prompt-sha）
SYS_SHA_BEFORE = 'ce225186cafa5d55c445e30e201b658a37834ec67be8c80a45201b3508423f22'

GEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen_candidates_v2.js')

# ---- C1：顶层 7 块 required 显式化（插在「铁律」前）----
# 前值：SYS 第 23 行骨架本身没有说明哪些块必填；schema 顶层 required 是 7 个块。
C1_OLD = '★ 铁律：用户给出的每个数值必须【逐字段采用】（键名数值都不许改、不许省略）。'
C1_NEW = ('★ 顶层七个块 **name / material / structure / mesh / load / bc / analysis 全部必填**'
          '（一个都不能省）；description、airfoil（仅 wingbox）、extra 按情形出现。\n'
          + C1_OLD)

# ---- C2：material 的 5 个 required 键名显式列出 ----
# 前值只说「按名称给出 E/ν/密度/屈服」，一个 required 键名都没写 ⇒ v7 glm 58/59 条首轮缺。
C2_OLD = ('材料按名称给出 E/ν/密度/屈服（铝 2024-T3: E=73100 MPa, ν=0.33, '
          'ρ=2.78e-9 t/mm^3, 屈服=345 MPa；T300/环氧参考用户给定）。')
C2_NEW = ('★ material 块 **五个键全部必填**（键名即契约）：name（只能是 '
          '"Aluminium 2024-T3" 或 "CFRP-LAYUP"）/ youngs_modulus（MPa）/ poisson_ratio / '
          'density（t/mm^3）/ yield_strength（MPa）。\n'
          '  铝 2024-T3 取 youngs_modulus=73100、poisson_ratio=0.33、density=2.78e-9、'
          'yield_strength=345；T300/环氧按用户给定。\n'
          '  **五个键一个都不能省**，也不要改用 E / nu / rho 这类自造键名。')

# ---- C3：网格键的族歧义（prompt 教 size，schema 只收 size_chord/size_span 且对所有族生效）----
C3_OLD = '网格键 size_chord/size_span（翼盒）、size（板壳类）。'
C3_NEW = ('网格块 mesh：**所有族都必须写 size_chord 与 size_span 两个键**'
          '（板壳类也用这两个键名——**没有 size 这个键**，写 size 会被拒）；'
          '可选 order（1 或 2）、refine_le（true/false）。')

REPLACEMENTS = [('C1', C1_OLD, C1_NEW), ('C2', C2_OLD, C2_NEW), ('C3', C3_OLD, C3_NEW)]

# ---- C4（仅 bplus 变体）：各块允许键白名单，前置到首轮 ----
# 依据：这份清单在 gen_candidates_v2.js:220-227 的 ALLOWED_HINT 里**早就存在**，
# 但只在「修复轮」把错误推回时才给模型 ⇒ 模型必然首轮写自创键、次轮才改对。
# 本次实测：只做 C1-C3 时，目标错误清零但首轮通过率仍 0/4，剩下的全是 analysis.type 这类自创键。
C4_OLD = C1_NEW  # 插在 C1 那段之后
C4_NEW = C1_NEW + (
    '\n★ 各块的键**只能**从下列清单取，清单外的键一律不写（自创键会被拒、白跑一轮）：\n'
    '  · mesh：size_chord / size_span（**两者必填**）/ order（1 或 2）/ refine_le（true/false）\n'
    '  · load：kind / magnitude / direction（**三者必填**）\n'
    '  · bc：root_surface / clamp（如 {"root_surface":"root","clamp":true}），**不要写 edges / type / edge_support**\n'
    '  · analysis：solver / step_type / incremental / initial_increment / total_time / outputs'
    '（**不确定就整体写 {}**，不要写 type / elements / units）\n'
    '  · extra：**只有** fuselage_barrel 写 end_shear / end_moment，其余族写 {}\n'
    '  · material：name / youngs_modulus / poisson_ratio / density / yield_strength（**五者必填**）')
VARIANTS = {'b': REPLACEMENTS, 'bplus': REPLACEMENTS + [('C4', C4_OLD, C4_NEW)]}


def extract_sys(src):
    """从生成器源码提取 SYS 模板字符串的内容（与 JS 解析口径一致：到第一个反引号+分号）。"""
    i = src.index('const SYS = `')
    j = src.index('`;', i + len('const SYS = `'))
    return src[i + len('const SYS = `'):j]


def sha(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--variant', default='b', choices=sorted(VARIANTS),
                    help='b = 只做 C1-C3（契约范围）；bplus = 额外把允许键白名单前置（探查）')
    a = ap.parse_args()
    repls = VARIANTS[a.variant]

    with open(GEN, encoding='utf-8') as f:
        src = f.read()
    sys_prompt = extract_sys(src)

    got = sha(sys_prompt)
    if got != SYS_SHA_BEFORE:
        print(f'[FATAL] 提取到的 SYS sha={got}')
        print(f'        期望前值 {SYS_SHA_BEFORE}')
        print('        ⇒ 源码 SYS 已变或提取定位错位，禁止继续（否则影子批与基线不可比）')
        return 2

    new = sys_prompt
    for tag, old, rep in repls:
        n = new.count(old)
        if n != 1:
            print(f'[FATAL] {tag} 命中 {n} 次（必须恰好 1 次）')
            print(f'        old={old[:70]}…')
            return 2
        new = new.replace(old, rep)

    print(f'前值 SYS  sha = {SYS_SHA_BEFORE}')
    print(f'影子 SYS  sha = {sha(new)}')
    print(f'长度 {len(sys_prompt)} → {len(new)} 字符（+{len(new) - len(sys_prompt)}）')

    # 判据 P1：material 的 5 个 required 键名必须都出现
    for k in ('name', 'youngs_modulus', 'poisson_ratio', 'density', 'yield_strength'):
        if k not in new:
            print(f'[FATAL] P1 失败：影子 prompt 里没有 {k}')
            return 2
    # 判据 P2：顶层 7 个块名必须都出现（且带「必填」）
    for k in ('name', 'material', 'structure', 'mesh', 'load', 'bc', 'analysis'):
        if k not in new:
            print(f'[FATAL] P2 失败：影子 prompt 里没有 {k}')
            return 2
    if '全部必填' not in new:
        print('[FATAL] P2 失败：没有「全部必填」的显式表述')
        return 2
    print('P1/P2（文本层判据）通过')

    if a.check or not a.out:
        if not a.out and not a.check:
            print('（未给 --out，仅校验）')
        return 0

    with open(a.out, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    print(f'已写 {a.out}')

    # 逐行 diff 摘要（只印变更行，便于人工复核改了什么）
    import difflib
    old_l = sys_prompt.splitlines()
    new_l = new.splitlines()
    print('\n--- 变更行 ---')
    for line in difflib.unified_diff(old_l, new_l, 'before', 'after', n=0, lineterm=''):
        if line.startswith(('---', '+++', '@@')):
            continue
        print(line[:200])
    return 0


if __name__ == '__main__':
    sys.exit(main())
