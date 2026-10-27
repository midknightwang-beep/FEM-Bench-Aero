# -*- coding: utf-8 -*-
"""v1.1 新几何：9 条**内插留出**（interior holdout）的 spec 生成器。

为什么要内插留出
----------------
现有 25 条 exam 里，boundary 6 + extrapolation 13 + **interpolation 6**（全在翼盒）。
`manifest.py` 自己也写着：`ID_TEST_RENAME = 'boundary_holdout'`，而**真内插留出 = v1.1**。
缺内插点会带来两个具体后果：
  1. exam 的统计精度不够（n=25 ⇒ CI95 宽到 [80,100]，4 pp 差距被判「不显著」）；
  2. 内插是「同一族参数之间的点」，最能检验**是否真的按参数生成**而不是背样本——
     现有 6 条内插全在翼盒一个族，另三族一条内插都没有。

本批 9 条全部取在**已有锚点之间**（每族标注了它夹在哪两个锚点中间），
spec 上打 `extra.split_tag = "v11_interior_holdout"`，由 manifest 的新谓词整类认领为 test 侧
——不用改任何既有规则，也不会动 D12 锁定的 11 条。

用法：
  python _v11/make_v11_specs.py            # 写 spec 到 staging 目录
  python _v11/make_v11_specs.py --dry      # 只打印计划
"""
import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FEA = os.path.join(os.path.dirname(ROOT), 'FEM-Bench-Aero')
MODELING = os.path.join(FEA, 'modeling')
STAGING = os.path.join(HERE, 'staging')

TAG = 'v11_interior_holdout'

#: (新 case 名, 模板 case, 覆盖的字段(dotted), 夹在哪两个锚点之间)
CASES = [
    ('naca4412_wingbox_size_skin2p5', 'naca4412_wingbox',
     {'airfoil.skin_thickness': 2.5},
     '壁厚 2 ↔ 3（span2000/skin2、skin3 两条已在集）'),
    ('naca4412_wingbox_n_ribs6_chord1000', 'naca4412_wingbox',
     {'airfoil.n_ribs': 6},
     '肋数 5 ↔ 7（chord1000 的 ribs5/ribs7 两条已在集）'),
    ('naca4412_wingbox_str4', 'naca4412_wingbox_str3',
     {'airfoil.n_stringers_per_skin': 4},
     '长桁数 3 ↔ 5（str3/str5 两条已在集）'),
    ('naca4412_wingbox_size_chord900', 'naca4412_wingbox',
     {'airfoil.chord': 900.0},
     '弦长 800 ↔ 1000（ribs3_chord800 与 chord1000 系列已在集）'),
    ('naca4412_wingbox_taper070', 'naca4412_wingbox',
     {'airfoil.tip_chord_ratio': 0.7},
     '锥度 0.6 ↔ 0.8（taper060/taper080 已在集）'),
    ('open_hole_panel_400x200_d30', 'open_hole_panel_400x200_d40',
     {'structure.params.hole_d': 30.0},
     '孔径 20 ↔ 40（d20/d40 已在集）'),
    ('open_hole_panel_500x250_d45', 'open_hole_panel_400x200_d40',
     {'structure.params.length': 500.0, 'structure.params.width': 250.0,
      'structure.params.hole_d': 45.0},
     '板尺寸 400×200 ↔ 600×300；孔径 40 ↔ 50'),
    ('stiffened_panel_700x600_str4', 'stiffened_panel_800x600_str3',
     {'structure.params.length': 700.0, 'structure.params.n_stringers': 4},
     '板长 600 ↔ 800；长桁 3 ↔ 5'),
    # ★ 第一版挑的是 d1800_l1800 —— 但集里**没有 d1800_l1600**，它两端只有 l2000，
    #   构不成「只差一个参数」的严格夹逼（校验器直接 SKIP）。改挑 d2000_l1800：
    #   d2000_l1600 与 d2000_l2000 都在集里 ⇒ 单轴（长度）内插，锚点齐全。
    ('fuselage_barrel_d2000_l1800_str8_frm3', 'fuselage_barrel_d2000_l2000_str8_frm3',
     {'structure.params.length': 1800.0},
     '柱长 1600 ↔ 2000（d2000 系列的 l1600 / l2000 两条都在集）'),
]


def _set(obj, dotted, val):
    cur = obj
    parts = dotted.split('.')
    for k in parts[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    old = cur.get(parts[-1], '<absent>')
    cur[parts[-1]] = val
    return old


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--out', default=STAGING)
    args = ap.parse_args(argv)

    plan = []
    for name, tmpl, overrides, bracket in CASES:
        tp = os.path.join(MODELING, tmpl, 'spec.json')
        if not os.path.exists(tp):
            print(f'[skip] 模板缺 spec：{tmpl}')
            continue
        spec = copy.deepcopy(json.load(open(tp, encoding='utf-8')))
        spec['name'] = name
        spec['description'] = f'v1.1 interior-holdout case ({bracket}); template={tmpl}'
        spec.setdefault('extra', {})['split_tag'] = TAG   # ★ 谓词读的是这个值（不是把 tag 当键）
        spec['extra']['v11_template'] = tmpl
        spec['extra']['v11_bracket'] = bracket
        changes = {}
        for dotted, val in overrides.items():
            changes[dotted] = {'from': _set(spec, dotted, val), 'to': val}
        plan.append({'case': name, 'template': tmpl, 'bracket': bracket, 'changes': changes})

    print(f'计划 {len(plan)} 条（tag={TAG}）：')
    for p in plan:
        ch = '；'.join(f"{k}: {v['from']} → {v['to']}" for k, v in p['changes'].items())
        print(f"  {p['case']:<44} ← {p['template']:<40} {ch}")
    if args.dry:
        return 0

    os.makedirs(args.out, exist_ok=True)
    for p in plan:
        case = p['case']
        d = os.path.join(args.out, case)
        os.makedirs(d, exist_ok=True)
        spec = copy.deepcopy(json.load(open(os.path.join(MODELING, p['template'], 'spec.json'),
                                           encoding='utf-8')))
        spec['name'] = case
        spec['description'] = f"v1.1 interior-holdout case ({p['bracket']}); template={p['template']}"
        spec.setdefault('extra', {})['split_tag'] = TAG   # ★ 谓词读的是这个值（不是把 tag 当键）
        spec['extra']['v11_template'] = p['template']
        spec['extra']['v11_bracket'] = p['bracket']
        for dotted, val in [(k, v['to']) for k, v in p['changes'].items()]:
            _set(spec, dotted, val)
        json.dump(spec, open(os.path.join(d, case + '.spec.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    json.dump(plan, open(os.path.join(args.out, '_v11_plan.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'[out] {args.out}（{len(plan)} 个 spec + _v11_plan.json）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
