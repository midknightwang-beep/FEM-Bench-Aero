# -*- coding: utf-8 -*-
"""_n35_key_guard.py — S-63 的判据本体：判分口径的两类键必须**分离且各自生效**

背景（CONFLICT N-35，老王 2026-11-04 拍板 B）
--------------------------------------------
`EXEC_CONFIG_KEYS` 原来一个集合装了两类来源不同的键，用 `engineering_layer` 一个开关控制：

  类① 真实执行配置（mesh 7 + analysis 5）：题面给了、**该判** —— 逐字转写就是考点；
       在 L3 只在 `engineering_layer=True` 时豁免（W4d 原拍板）。
  类② 数据集构建元信息（extra 7）：`v11_bracket` 值是一句中文描述 ⇒ **任何层都不该判**。

共用开关的后果：`score_l2.py` 不传该开关 ⇒ 要么打开丢掉 mesh 考点（选项 A），
要么关上被元信息压分 ~20 pp（选项 C）。拍板 B = 拆成两个集合。

为什么用**行为判据**而不是「断言集合里是哪几个键」
--------------------------------------------------
「手抄名单」会漂：换个人把 mesh 键挪进 `DATASET_META_KEYS`，名单式判据照样绿
（只要名单自己也跟着改）。这里的判据只问**行为**：

  A 结构：`DATASET_META_KEYS` 的持有者只许是 `extra`
  B 结构：`DATASET_META_KEYS` 与 `EXEC_CONFIG_KEYS['mesh']` 交集为空
  C 行为：L2 语义（`engineering_layer=False`）下，**mesh 键填错必须 FAIL**（考点还在）
  D 行为：L2 语义下，**extra 元信息键填错必须 PASS**（N-35 修好）
  E 行为：L3 语义（`engineering_layer=True`）下，mesh 与 extra **都 PASS**（原行为不变）
  F 行为：extra 键在 L3 豁免**不依赖开关** —— 把 `EXEC_CONFIG_KEYS` 清空后仍 PASS
     （若豁免是被开关顺带带出来的，F 会红：这说明它还是「寄生」在执行配置分支上）

C 与 D 是**一对反向**判据：只测 D 会把「把所有键都豁免」判成通过（放水也是过），
只测 C 会把「一个都不豁免」判成通过。两条同时立，才钉住「分开」。

用法：
    python _n35_key_guard.py                # 人读
    python _n35_key_guard.py --json         # 机器读（check_claims S-63 用）
退出码：0 全过 ／ 1 有判据红
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FAMILY = 'stiffened_panel'      # GRADED_FIELDS 里走 params 的一族，字段最少、最不易受别的分支干扰


def _spec():
    """一份最小但**每个体例都走到**的 gold：params + material + mesh + extra。"""
    return {
        'structure': {'params': {'length': 1000.0, 'width': 600.0}},
        'material': {'name': 'al2024_t3', 'youngs_modulus': 73000.0,
                     'poisson_ratio': 0.33, 'density': 2.78e-09,
                     'yield_strength': 345.0},
        'mesh': {'element_order': 2, 'recombine': True, 'algorithm_2d': 6},
        'extra': {'split_tag': 'v11_interior_holdout', 'v11_bracket': '柱长 1600 ↔ 2000'},
    }


def _with(**changes):
    """把 gold 复制一份并按 holder.key 改值。changes 形如 mesh={'element_order': 1}。"""
    s = copy.deepcopy(_spec())
    for holder, blk in changes.items():
        s.setdefault(holder, {}).update(blk)
    return s


def inspect():
    """返回 (ok, detail, items)。items 是逐条判据的结果，便于负控逐向核。"""
    import evaluate as E

    items, problems = [], []

    def add(tag, ok, msg):
        items.append({'id': tag, 'ok': bool(ok), 'detail': msg})
        if not ok:
            problems.append(f'{tag} {msg}')

    # ---- A 结构：元信息只许落在 extra ----
    holders = sorted(E.DATASET_META_KEYS)
    add('A', holders in ([], ['extra']),
        f'DATASET_META_KEYS 的持有者 = {holders}（只许 [] 或 [extra]）')

    # ---- B 结构：与 mesh 执行配置无交集 ----
    inter = sorted(set(E.DATASET_META_KEYS.get('extra', ())) &
                   set(E.EXEC_CONFIG_KEYS.get('mesh', ())))
    add('B', not inter, f'元信息集 ∩ mesh 执行配置 = {inter or "空"}')

    # 下面的行为判据要求元信息集非空 —— 空集等于「N-35 没修」，不能当通过
    add('B2', bool(E.DATASET_META_KEYS.get('extra')),
        f'元信息集大小 = {len(E.DATASET_META_KEYS.get("extra", ())) }（0 = 豁免未装）')

    gold = _spec()
    mk, lk = sorted(gold['mesh']), []

    def run(cand, eng):
        sf = E.spec_fidelity(cand, gold, FAMILY, input_mesh_keys=mk, input_load_keys=lk,
                             engineering_layer=eng)
        return sf['pass'], [f['field'] for f in (sf.get('failed') or [])]

    # ---- C 行为：L2 语义下 mesh 填错必须 FAIL（转写考点还在）----
    ok_c, fb = run(_with(mesh={'element_order': 1}), False)
    add('C', (not ok_c) and any(f.startswith('mesh.') for f in fb),
        f'L2 语义 + mesh.element_order 填错 ⇒ pass={ok_c}，failed={fb[:3]}（须 FAIL 且点名 mesh 键）')

    # ---- D 行为：L2 语义下 extra 元信息填错必须 PASS ----
    ok_d, fb_d = run(_with(extra={'split_tag': 'train'}), False)
    add('D', ok_d,
        f'L2 语义 + extra.split_tag 填错 ⇒ pass={ok_d}，failed={fb_d[:3]}（须 PASS；N-35 的核心）')

    # ---- E 行为：L3 语义下两者都 PASS（原 W4d 行为不变）----
    ok_e1, fb_e1 = run(_with(mesh={'element_order': 1}), True)
    ok_e2, fb_e2 = run(_with(extra={'split_tag': 'train'}), True)
    add('E', ok_e1 and ok_e2,
        f'L3 语义 ⇒ mesh 填错 pass={ok_e1}、extra 填错 pass={ok_e2}（两者都须 PASS）')

    # ---- F 行为：extra 豁免不得寄生在 EXEC_CONFIG_KEYS 上 ----
    saved = copy.deepcopy(E.EXEC_CONFIG_KEYS)
    try:
        E.EXEC_CONFIG_KEYS.clear()
        ok_f, fb_f = run(_with(extra={'split_tag': 'train'}), False)
        ok_f3, fb_f3 = run(_with(extra={'split_tag': 'train'}), True)
    finally:
        E.EXEC_CONFIG_KEYS.clear()
        E.EXEC_CONFIG_KEYS.update(saved)
    add('F', ok_f and ok_f3,
        f'清空 EXEC_CONFIG_KEYS 后 extra 填错仍 PASS（L2={ok_f} L3={ok_f3}，failed={fb_f[:2]}{fb_f3[:2]}）'
        f' —— 说明豁免不依赖执行配置集合')

    # ---- G 反向：把 gold 的 mesh 键删掉后，候选多写 mesh 键必须仍被当自创键罚 ----
    #      （防「为了让 C 过，把自创键检查也顺手放宽」）
    g2 = copy.deepcopy(gold)
    g2['mesh'] = {}
    sf_g = E.spec_fidelity(_with(), g2, FAMILY, input_mesh_keys=[],
                           input_load_keys=[], engineering_layer=False)
    add('G', not sf_g['pass'],
        f'gold 无 mesh 键、候选多写 ⇒ pass={sf_g["pass"]}（须 FAIL：自创键照罚，未随本次拆分放宽）')

    return (not problems), '；'.join(f'{i["id"]}{"✓" if i["ok"] else "✗"}' for i in items), items


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    ok, detail, items = inspect()
    if '--json' in argv:
        print(json.dumps({'ok': ok, 'detail': detail, 'items': items},
                         ensure_ascii=False, indent=1))
    else:
        for i in items:
            print(f'  [{"ok " if i["ok"] else "BAD"}] {i["id"]}  {i["detail"]}')
        print(f'\nS-63 判据：{"全过" if ok else "有红"}  {detail}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
