# -*- coding: utf-8 -*-
"""T-PSA：**prompt 提到的键 vs gold 实际存在的键** 一次性审计。

动机（本轮踩到的真坑）：
  C3/C4 教模型写 `mesh.order` / `mesh.refine_le` —— 它们在 `schema_task.json` 里是
  **合法属性**（`mesh.properties` 含它们），所以结构校验放行；但 64 个 gold **一个都没有**
  （gold 用的是 `element_order` / `refine_at_leading_edge`，且这两个在 EXEC 豁免名单里）。
  判分器 `spec_fidelity` 对候选多写的键按「自创键」判 FAIL ⇒ 33 条由 pass 变 fail。
  ⇒ **「schema 允许」不等于「能写」；真正的白名单是 `gold ∩ 豁免名单`。**

所以：任何要写进 prompt 的键名，都必须先过这里。判两类：
  DEAD  = prompt 提到、gold 从未出现、也不在豁免名单 ⇒ 写就 FAIL（必须从 prompt 删除）
  OK    = gold 里出现过，或被豁免

用法：
  python _psa_key_audit.py --sys-file <prompt.txt>
  python _psa_key_audit.py --source          # 直接审计源码里的 SYS
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FEA = os.path.join(os.path.dirname(HERE), 'FEM-Bench-Aero')

# evaluate.py 的执行配置豁免（REPORTED NOT GATED）——从源码读，不手抄
sys.path.insert(0, HERE)
import evaluate as E  # noqa: E402

EXEC = E.EXEC_CONFIG_KEYS
METADATA = getattr(E, 'METADATA_KEYS', {})
METADATA_EXTRA = getattr(E, 'METADATA_EXTRA_KEYS', ())


def gold_keys():
    """{块名: {键: 出现次数}}，外加 family 下的键集合。"""
    per = collections.defaultdict(collections.Counter)
    for p in glob.glob(os.path.join(FEA, 'modeling', '*', 'spec.json')):
        s = json.load(open(p, encoding='utf-8'))
        for blk in ('mesh', 'load', 'bc', 'analysis', 'extra'):
            for k in (s.get(blk) or {}):
                per[blk][k] += 1
        for k in (s.get('material') or {}):
            per['material'][k] += 1
        hold = 'airfoil' if 'airfoil' in s else 'params'
        holder = s.get('airfoil') if hold == 'airfoil' else (s.get('structure') or {}).get('params')
        for k in (holder or {}):
            per[hold][k] += 1
        for k in (s.get('structure') or {}):
            per['structure'][k] += 1
    return per


# prompt 里的非键标识符（英文词/单位/枚举值），不参与审计
WHITELIST = {
    'wingbox', 'open_hole_panel', 'fuselage_barrel', 'stiffened_panel',
    'tip_force', 'pressure', 'blade', 'T', 'root', 'root_surface', 'clamp',
    'Aluminium', 'CFRP', 'LAYUP', 'T300', 'NACA', 'true', 'false', 'null',
    'x', 'y', 'z', 'name', 'description', 'json', 'JSON', 'MPa', 'mm', 'N',
    'static', 'solver', 'code', 'key',
}


def audit(prompt):
    per = gold_keys()
    ids = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]{2,}', prompt))
    allkeys = set()
    for blk, c in per.items():
        allkeys |= set(c)
    dead, ok, unknown = [], [], []
    for k in sorted(ids):
        if k in WHITELIST:
            continue
        if k in allkeys:
            blk_hit = [b for b in per if k in per[b]]
            ok.append((k, blk_hit))
            continue
        exempt = any(k in EXEC.get(b, set()) for b in EXEC) or k in METADATA_EXTRA
        if exempt:
            ok.append((k, ['<豁免>']))
        else:
            dead.append(k)
    return per, dead, ok, unknown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sys-file', default='')
    ap.add_argument('--source', action='store_true')
    a = ap.parse_args()

    if a.source:
        src = open(os.path.join(HERE, 'gen_candidates_v2.js'), encoding='utf-8', newline=None).read()
        i = src.index('const SYS = `') + len('const SYS = `')
        j = src.index('`;', i)
        prompt = src[i:j]
    elif a.sys_file:
        prompt = open(a.sys_file, encoding='utf-8').read()
    else:
        print('需要 --source 或 --sys-file')
        return 2

    per, dead, ok, _ = audit(prompt)
    print('=== gold 里各块键（只列非 EXEC 豁免的）===')
    for blk in ('mesh', 'load', 'bc', 'analysis', 'extra', 'material', 'airfoil', 'params', 'structure'):
        ks = [k for k in per.get(blk, {}) if k not in EXEC.get(blk, set())]
        if ks:
            print(f'  {blk:10s} {sorted(ks)}')
    print()
    print(f'=== prompt 提到、且 gold 里存在（或豁免）的键：{len(ok)} 个 ===')
    for k, b in ok:
        print(f'  OK   {k:26s} {b}')
    print()
    if dead:
        print(f'=== ★ DEAD：prompt 提到但 gold 从未出现、也未豁免：{len(dead)} 个（写就 FAIL）===')
        for k in dead:
            print(f'  DEAD {k}')
    else:
        print('=== 无 DEAD 键 ===')
    return 1 if dead else 0


if __name__ == '__main__':
    sys.exit(main())
