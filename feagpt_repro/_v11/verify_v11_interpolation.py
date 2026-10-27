# -*- coding: utf-8 -*-
"""v1.1 内插留出的**独立物理校验**：新案例的峰值量必须落在它夹的两个锚点之间。

为什么需要这一层
----------------
"跑通了" 不等于 "对"。新几何是我们自己造的，`make_dataset` 的 gate4 只查语义/拓扑，
不查物理合理性。而"内插点"本身给了我们一个**独立于求解器**的判据：

    若 case X 只在参数轴 a 上位于 A 与 B 之间（其余参数逐项相同），
    且该轴对响应的作用是单调的（壁厚↓⇒更软、肋数↑⇒更刚、孔径↑⇒更软……），
    则 X 的峰值位移必须严格落在 A、B 之间。

这条判据不依赖任何解析解，也不依赖 gold —— 它是**同一求解器在两个锚点上的结果插值**，
所以查到的是"新点有没有算错/建错"（例如参数没生效、单位写错、厚度表没更新）。
历史教训：厚度变体如果 `*SHELL SECTION` 没跟着改，位移会与基准**逐位相同**——那种错误
只有跨案例比较才看得见，单条 case 内部检查永远查不出来。

用法：
  python _v11/verify_v11_interpolation.py            # 写 _v11/v11_interp_check.json
  python _v11/verify_v11_interpolation.py --strict   # 有 FAIL 时 rc=1（进 CI 用）
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODELING = os.path.join(os.path.dirname(ROOT), 'FEM-Bench-Aero', 'modeling')

#: (新 case, 参数轴, 下锚点, 上锚点, 轴方向说明[, 可严格判的指标])
#: 只有「单轴内插、其余参数逐项相同」的才做严格判定；多轴角点只报不判。
#:
#: ★ 末项 `strict_metrics` 不能一刀切：**应力不是在所有轴上单调**。
#:   实证：柱壳 d2000 系列 l=1600/1800/2000 的 max_von_mises = 249.35 / 248.16 / 249.40,
#:   三点基本持平（差 0.5%）——因为根部峰值应力由「端部弯矩 ÷ 截面模量」决定，两者都不随长度变，
#:   长度只挪动框的位置，带来千分之几的波纹。⇒ 长度轴只判 max_disp，应力只报。
#:   第一版对 vM 也判「必须落在两点之间」，于是新点 248.16 低于两端 ⇒ 误报 FAIL（判据错，不是模型错）。
BRACKETS = [
    ('naca4412_wingbox_size_skin2p5', 'airfoil.skin_thickness',
     'naca4412_wingbox_size_skin2', 'naca4412_wingbox',
     '壁厚越小越软（Δ↑）', ('max_disp', 'max_von_mises')),
    ('naca4412_wingbox_n_ribs6_chord1000', 'airfoil.n_ribs',
     'naca4412_wingbox', 'naca4412_wingbox_n_ribs7_chord1000',
     '肋越多越刚（Δ↓）', ('max_disp', 'max_von_mises')),
    ('naca4412_wingbox_str4', 'airfoil.n_stringers_per_skin',
     'naca4412_wingbox_str3', 'naca4412_wingbox_str5',
     '长桁越多越刚（Δ↓）', ('max_disp', 'max_von_mises')),
    ('naca4412_wingbox_size_chord900', 'airfoil.chord',
     'naca4412_wingbox_n_ribs5_chord800', 'naca4412_wingbox',
     '短弦更软（Δ↑）', ('max_disp', 'max_von_mises')),
    ('naca4412_wingbox_taper070', 'airfoil.tip_chord_ratio',
     'naca4412_wingbox_taper060', 'naca4412_wingbox_taper080',
     '锥度越小越软（Δ↑）', ('max_disp', 'max_von_mises')),
    ('open_hole_panel_400x200_d30', 'structure.params.hole_d',
     'open_hole_panel_400x200_d20', 'open_hole_panel_400x200_d40',
     '孔越大越软（Δ↑）', ('max_disp', 'max_von_mises')),
    ('fuselage_barrel_d2000_l1800_str8_frm3', 'structure.params.length',
     'fuselage_barrel_d2000_l1600_str8_frm3', 'fuselage_barrel_d2000_l2000_str8_frm3',
     '柱越长越软（Δ↑）', ('max_disp',)),          # 应力对长度不单调，见上方注释
]
#: 多轴角点：与任何单一锚点都不构成"只差一个参数"，只报数值不作判定
REPORT_ONLY = [
    ('open_hole_panel_500x250_d45', ['open_hole_panel_400x200_d40', 'open_hole_panel_600x300_d60']),
    ('stiffened_panel_700x600_str4', ['stiffened_panel_800x600_str3', 'stiffened_panel_600x600_str3']),
]
METRICS = ['max_disp', 'max_von_mises']


def _scalars(case):
    p = os.path.join(MODELING, case, 'truth.json')
    if not os.path.exists(p):
        return None
    return (json.load(open(p, encoding='utf-8')) or {}).get('scalars') or {}


def _param(case, dotted):
    p = os.path.join(MODELING, case, 'spec.json')
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding='utf-8'))
    cur = d
    for k in dotted.split('.'):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(HERE, 'v11_interp_check.json'))
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args(argv)

    rows, n_fail, n_skip = [], 0, 0
    for case, axis, lo, hi, why, strict_m in BRACKETS:
        s = _scalars(case)
        if not s:
            rows.append({'case': case, 'status': 'SKIP', 'note': '缺 truth.json'})
            n_skip += 1
            continue
        a, b = _scalars(lo), _scalars(hi)
        if not a or not b:
            rows.append({'case': case, 'status': 'SKIP', 'note': f'缺锚点 truth（{lo if not a else hi}）'})
            n_skip += 1
            continue
        rec = {'case': case, 'axis': axis, 'why': why,
               'axis_value': _param(case, axis),
               'anchors': {lo: _param(lo, axis), hi: _param(hi, axis)},
               'checks': {}}
        ok_all = True
        for m in METRICS:
            v, va, vb = s.get(m), a.get(m), b.get(m)
            if v is None or va is None or vb is None:
                rec['checks'][m] = {'status': 'SKIP'}
                continue
            lo_v, hi_v = min(va, vb), max(va, vb)
            inside = lo_v < v < hi_v
            gated = m in strict_m
            rec['checks'][m] = {'value': v, 'anchor_lo': va, 'anchor_hi': vb,
                                'inside': inside, 'gated': gated,
                                'rel_pos': (round((v - va) / (vb - va), 4) if vb != va else None),
                                'status': ('PASS' if inside else 'FAIL') if gated
                                          else ('REPORTED' if inside else 'REPORTED_NOT_MONOTONE')}
            if gated:
                ok_all = ok_all and inside
        rec['status'] = 'PASS' if ok_all else 'FAIL'
        n_fail += 0 if ok_all else 1
        rows.append(rec)

    report = {'schema': 'v11_interp_check/v1',
              'rule': ('新案例只在单轴位于两锚点之间、其余参数相同 ⇒ 该轴**单调的**峰值量必须严格落在两锚点之间；'
                       '非单调指标（如柱壳长度轴上的 max_von_mises）只报不判'),
              'n_checked': len([r for r in rows if r.get('status') in ('PASS', 'FAIL')]),
              'n_fail': n_fail, 'n_skip': n_skip,
              'brackets': rows}

    print(f'v1.1 内插物理校验：{report["n_checked"]} 条判定，FAIL {n_fail}，SKIP {n_skip}')
    for r in rows:
        if r.get('status') in ('PASS', 'FAIL'):
            det = ' '.join(f"{m}={c.get('value')}({c.get('status')})" for m, c in r['checks'].items())
            print(f"  [{r['status']:4}] {r['case']:<44} {det}")
        else:
            print(f"  [SKIP] {r['case']:<44} {r.get('note')}")
    for c, refs in REPORT_ONLY:
        s = _scalars(c)
        if s:
            print(f"  [只报] {c:<44} max_disp={s.get('max_disp')} 参考={[(x, (_scalars(x) or {}).get('max_disp')) for x in refs]}")

    json.dump(report, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'[out] {args.out}')
    return 1 if (args.strict and n_fail) else 0


if __name__ == '__main__':
    sys.exit(main())
