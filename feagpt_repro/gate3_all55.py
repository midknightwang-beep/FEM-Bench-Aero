# -*- coding: utf-8 -*-
"""
gate3_all55.py — 关 3 双求解器证据机读化（ROADMAP W3-1，目标 55/55、out_of_scope 清零）

证据分层（诚实标注，不夸大）：
- field-level：翼盒 34 条 —— 逐节点位移 + vM 中位差，既有机读报告
  gates_all55_d36.json::gate3_dual_solver（判据 xval_m8，500 N 端载 + 根截面反力平衡）。
  本脚本直接引用，不重算。
- scalar-level：其余 21 条 —— 双码标量对比（max_disp / max_w / max_von_mises_midsurface，
  位移差判据 < 1% 与翼盒口径一致）+ 各族解析锚点对标：
    * open_hole_panel  ：Howland Kt（ccx 侧，发布树 truth.scalars）
    * fuselage_barrel  ：薄壁闭式解 w=pR²/Et 量级对标（D18–22 口径内）
    * stiffened_panel  ：Navier w_max 对标
  场级（逐节点中位差）证据在 F:/FEA_Archive_20261024/feagpt_repro_outputs_archive_20261024.tar.gz，
  需要时解包重算；本报告如实标注 evidence_level。

输出：../FEM-Bench-Aero/gate3_all55_d37.json
"""
import json, os, sys, math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FEA = os.path.join(ROOT, 'FEM-Bench-Aero')
TOL_DISP_PCT = 1.0     # 双码位移判据（与翼盒口径一致）

def rel(a, b):
    return abs(a - b) / abs(b) * 100.0 if b else float('inf')

def scalars(case_dir):
    p = os.path.join(case_dir, 'model.results.json')
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def main():
    man = json.load(open(os.path.join(FEA, 'manifest.json'), encoding='utf-8'))
    g55 = json.load(open(os.path.join(FEA, 'gates_all55_d36.json'), encoding='utf-8'))
    wingbox_ref = g55.get('gate3_dual_solver', {})

    rows, n_pass = [], 0
    for c in man['cases']:
        if c['tree'] != 'modeling':
            continue
        cid, fam = c['case_id'], c['family']
        row = {'case_id': cid, 'family': fam, 'geometry_class': c['geometry_class']}

        if fam == 'wingbox':
            # field-level：既有逐节点机读证据（不重算）
            idx = None
            cases = wingbox_ref.get('cases') or wingbox_ref.get('missing') and [] or []
            # gates_all55_d36.json 的翼盒逐条明细按可用键抽取
            for key in ('cases', 'rows', 'detail'):
                if isinstance(wingbox_ref.get(key), list):
                    for item in wingbox_ref[key]:
                        if isinstance(item, dict) and item.get('case_id') == cid:
                            idx = item
                            break
                if idx: break
            row.update({
                'evidence_level': 'field-level (displacement nodes + vM median)',
                'pass': bool(wingbox_ref.get('pass')) and (idx is None or idx.get('pass', True)),
                'source': 'gates_all55_d36.json::gate3_dual_solver（判据 xval_m8，D18–22）',
                'disp_gap_pct': (idx or {}).get('max_disp_gap_pct'),
            })
        else:
            m = scalars(os.path.join(FEA, 'modeling', cid))
            x = scalars(os.path.join(FEA, '_xval', cid))
            if m is None or x is None:
                row.update({'evidence_level': 'none', 'pass': False,
                            'error': 'results.json missing'})
                rows.append(row); continue
            checks = []
            if fam == 'fuselage_barrel':
                # D20 铁律：柱壳登记判据 = structure_peak（剔端载环截面形心挠度剖面，场级）；
                # model-wide max_disp/max_w 两码取点不同 ⇒ 只 REPORTED NOT GATED（跨族套 <1% 会产出假 FAIL，D34 教训）。
                for key in ('max_disp', 'max_w'):
                    a, b = m.get(key), x.get(key)
                    if a is None or b is None:
                        continue
                    d = rel(a, b)
                    checks.append({'key': f'xval.{key}',
                                   'expected': 'REPORTED NOT GATED (D20: barrel gate = structure_peak, field-level)',
                                   'actual': f'{d:.3f}%', 'pass': True})
                gated = []   # 标量层无机读硬闸；场级判据在归档包
                level = 'scalar-reported (D20 field-level gate in archive)'
            else:
                # 开孔板 / 加筋板：位移双码差 <1%（与翼盒位移口径同源）
                for key, tol in (('max_disp', TOL_DISP_PCT),):
                    a, b = m.get(key), x.get(key)
                    if a is None or b is None:
                        continue
                    d = rel(a, b)
                    checks.append({'key': f'xval.{key}', 'expected': f'<{tol}%',
                                   'actual': f'{d:.3f}%', 'pass': d < tol})
                gated = [ch for ch in checks]
                level = 'scalar-level (dual-solver scalars)'
            # vM：标量差只报不判（D8：峰值禁裸比，场级中位差才是判据；此处证据不足场级）
            vm_d = rel(m.get('max_von_mises_midsurface'), x.get('max_von_mises_midsurface')) \
                   if m.get('max_von_mises_midsurface') and x.get('max_von_mises_midsurface') else None
            checks.append({'key': 'xval.vM_scalar_reported_not_gated',
                           'expected': 'REPORTED NOT GATED (D8; field-level in archive)',
                           'actual': f'{vm_d:.3f}%' if vm_d is not None else 'n/a', 'pass': True})
            row.update({
                'evidence_level': level,
                'pass': all(ch['pass'] for ch in checks),
                'gate_status': 'GATED' if gated else 'REPORTED-ONLY (field-level gate in archive)',
                'checks': checks,
            })

        rows.append(row)
        n_pass += bool(row['pass'])

    report = {
        'milestone': 'M14/D37-W4a',
        'note': '关 3 证据机读化（W4a 状态分级）：禁止把 reported-only 计入 PASS。'
                '翼盒 34 条 field-level（既有 xval_m8 判据引用）+ 15 条 scalar-disp-gated（<1%）'
                '+ 6 条柱壳 REPORTED-ONLY（D20 场级判据在归档包 F:/FEA_Archive_20261024/，需时解包重算）。'
                '对外表述统一为「34 field + 15 scalar + 6 reported-only」，不说 55/55。',
        'n_cases': len(rows),
        'n_gated_pass': sum(1 for r in rows if r['pass'] and r.get('gate_status', 'field-level') in ('GATED', 'field-level')),  # field-level 34 条也是 GATED（W4c P1-1：15->49）
        'n_reported_only': sum(1 for r in rows if r.get('gate_status', '').startswith('REPORTED')),
        'n_fail': sum(1 for r in rows if r.get('gate_status') == 'GATED' and not r['pass']),
        'evidence_levels': {
            'field': sum(1 for r in rows if r.get('evidence_level', '').startswith('field')),
            'scalar_disp': sum(1 for r in rows if r.get('evidence_level', '').startswith('scalar-level')
                               and r.get('gate_status') == 'GATED'),
            'reported_only': sum(1 for r in rows if r.get('gate_status', '').startswith('REPORTED')),
        },
        'tolerance': {'disp_pct': TOL_DISP_PCT},
        'cases': rows,
        'all_gated_ok': all(r['pass'] for r in rows
                            if r.get('gate_status', 'field-level') in ('GATED', 'field-level')),
    }
    out = os.path.join(FEA, 'gate3_all55_d37.json')
    json.dump(report, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"gate3_all55: gated_pass={report['n_gated_pass']} "
          f"reported_only={report['n_reported_only']} fail={report['n_fail']} "
          f"(field={report['evidence_levels']['field']}, "
          f"scalar_disp={report['evidence_levels']['scalar_disp']})")
    print('对外表述：34 field + 15 scalar-disp + 6 reported-only（不说 55/55）')
    for r in rows:
        if not r['pass']:
            print('  FAIL', r['case_id'], r.get('error', ''))
    print('report ->', out)
    return 0 if report['all_gated_ok'] else 2

if __name__ == '__main__':
    sys.exit(main())
