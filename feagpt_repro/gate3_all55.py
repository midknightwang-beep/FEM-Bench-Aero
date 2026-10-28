# -*- coding: utf-8 -*-
"""
gate3_all55.py — 关 3 双求解器证据机读化（ROADMAP W3-1；v1.1 起覆盖 64 条）

证据分层（诚实标注，不夸大）。**关键是「等级不得超过证据」**：
- field-level A：翼盒 34 条（v1.0 代）—— 逐节点位移 + vM 中位差，引用
  gates_all55_d36.json::gate3_dual_solver（判据 xval_m8，500 N 端载 + 根截面反力平衡），不重算。
- field-level B：**v1.1 新增的 5 条翼盒 + 2 条开孔板 + 1 条加筋板**（T-A7，2026-10-28）——
  实测由 verify_solvers.py 逐条跑出，落盘 reports/diagnostics/xval_v11_9cases.json，
  本脚本按 case_id 取读数。d36 写于 2026-10-24，这些 case 当时不存在，**必然查不到**。
- scalar-level：其余（双码标量 max_disp / max_w / max_von_mises_midsurface，
  位移差判据 < 1% 与翼盒口径一致）+ 各族解析锚点对标：
    * open_hole_panel  ：Howland Kt（ccx 侧，发布树 truth.scalars）
    * fuselage_barrel  ：薄壁闭式解 w=pR²/Et 量级对标（D18–22 口径内）
    * stiffened_panel  ：Navier w_max 对标
  场级（逐节点中位差）证据在 F:/FEA_Archive_20261024/feagpt_repro_outputs_archive_20261024.tar.gz，
  需要时解包重算；本报告如实标注 evidence_level。

★ T-A7 修的是什么（CONFLICT.md N-6）：旧版翼盒分支在 d36 里查不到明细时 `idx=None`，
于是 `pass` 继承整体 PASS、`disp_gap_pct=None`，**却仍印 field-level** —— 等级高于证据，
是红线 R2「reported-only 不得计入 PASS」的镜像。现在三分支：
  有 d36 明细   -> field-level (d36)
  有实测读数     -> field-level (measured <date>)
  两者都没有     -> pass=False（不设 gate_status ⇒ 按 field-level 参与判定 ⇒ 直接报红）
★ N-8：文件名保留 `all55` 是历史（C-003 的 artifact 指针指向它），内容已是 64 条，note 里写明。

输出：../FEM-Bench-Aero/gate3_all55_d37.json
"""
import json, os, sys, math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FEA = os.path.join(ROOT, 'FEM-Bench-Aero')
TOL_DISP_PCT = 1.0     # 标量位移判据（开孔板/加筋板；与翼盒位移口径同源）
TOL_VM_MEDIAN_PCT = 5.0  # 翼盒 field-level 真判据：与 gates_all55_d36.json 的
                         # stress_field.tol_pct 一致。★ max_disp.gated=false —— 翼盒的
                         # model-wide max|u| 是 REPORTED NOT GATED（峰值是单节点选择）。

#: v1.1 新增 case 的逐条实测读数（verify_solvers 产出，parse_xval_v11_log.py 转录）
MEASURED_JSON = os.path.join(HERE, 'reports', 'diagnostics', 'xval_v11_9cases.json')


def measured_index():
    """case_id -> 实测记录。文件缺失时返回空字典（不静默放行，见三分支的 else）。"""
    if not os.path.exists(MEASURED_JSON):
        return {}, None
    d = json.load(open(MEASURED_JSON, encoding='utf-8'))
    return {c['case_id']: c for c in d.get('cases', [])}, d.get('milestone')


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
    measured, measured_ms = measured_index()
    measured_tag = (measured_ms or 'unknown').split('(')[0].strip()

    rows, n_pass = [], 0
    for c in man['cases']:
        if c['tree'] != 'modeling':
            continue
        cid, fam = c['case_id'], c['family']
        row = {'case_id': cid, 'family': fam, 'geometry_class': c['geometry_class']}

        if fam == 'wingbox':
            # field-level：先查 d36 明细（v1.0 代 34 条），查不到再查 v1.1 实测读数。
            # ★ 绝不「查不到就继承整体 PASS」——那会让等级高于证据（T-A7 / N-6）。
            idx = None
            for key in ('cases', 'rows', 'detail'):
                if isinstance(wingbox_ref.get(key), list):
                    for item in wingbox_ref[key]:
                        # ★ d36 的明细键是 `case`，不是 `case_id`。按 case_id 找 ⇒ 永远
                        # 命中 0 条 ⇒ 34 条也退化成「继承整体 PASS」（T-A7 查出的真因）。
                        if isinstance(item, dict) and \
                                (item.get('case_id') or item.get('case')) == cid:
                            idx = item
                            break
                if idx: break

            if idx is not None:
                sf = idx.get('stress_field') or {}
                row.update({
                    'evidence_level': 'field-level (displacement nodes + vM median)',
                    'gate_status': 'field-level',
                    'pass': bool(idx.get('pass', True)),
                    'source': 'gates_all55_d36.json::gate3_dual_solver（判据 xval_m8，D18–22）',
                    'disp_gap_pct': (idx.get('max_disp') or {}).get('gap_pct'),
                    'vm_median_gap_pct': sf.get('median_pct'),
                    'vm_p90_gap_pct': sf.get('p90_pct'),
                    'gate_rule': ('vM 逐节点中位差 < %s%%（d36 stress_field.tol_pct）；'
                                  'max|u| 只报不判' % sf.get('tol_pct', TOL_VM_MEDIAN_PCT)),
                })
            elif cid in measured:
                m = measured[cid]
                vm_med = m.get('vm_median_gap_pct')
                row.update({
                    'evidence_level': f'field-level (measured {measured_tag})',
                    'gate_status': 'field-level',
                    # 与 d36 同一判据：vM 场级中位差 < 5%；max|u| 只报不判
                    'pass': bool(m.get('pass')) and vm_med is not None
                            and vm_med < TOL_VM_MEDIAN_PCT,
                    'source': ('reports/diagnostics/xval_v11_9cases.json'
                               '（verify_solvers 逐条实测，判据 clamp/500N）'),
                    'disp_gap_pct': m.get('max_u_gap_pct'),
                    'vm_median_gap_pct': vm_med,
                    'vm_p90_gap_pct': m.get('vm_p90_gap_pct'),
                    'gate_rule': (f'vM 逐节点中位差 < {TOL_VM_MEDIAN_PCT}%'
                                  '（与 d36 stress_field.tol_pct 同口径）；max|u| 只报不判'),
                })
            else:
                # 既无 d36 明细、也无实测读数 ⇒ 不得计入 field-level PASS。
                # 不设 gate_status（默认按 field-level 参与 all_gated_ok）⇒ 直接报红。
                row.update({
                    'evidence_level': 'none (no per-case reading)',
                    'pass': False,
                    'error': ('no field evidence: absent from gates_all55_d36.json '
                              'and from xval_v11_9cases.json'),
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

    # 计数一律现算，不沿用上一版（R-A4）
    lv = {
        'field_d36': sum(1 for r in rows
                         if r.get('evidence_level', '').startswith('field')
                         and 'measured' not in r.get('evidence_level', '')),
        'field_measured': sum(1 for r in rows
                              if 'measured' in r.get('evidence_level', '')),
        'field_no_evidence': sum(1 for r in rows
                                 if r.get('evidence_level', '').startswith('none')),
        'scalar_disp': sum(1 for r in rows
                           if r.get('evidence_level', '').startswith('scalar-level')
                           and r.get('gate_status') == 'GATED'),
        'reported_only': sum(1 for r in rows
                             if r.get('gate_status', '').startswith('REPORTED')),
    }
    n_field_total = lv['field_d36'] + lv['field_measured'] + lv['field_no_evidence']
    headline_txt = (f"{n_field_total} field "
                    f"({lv['field_d36']} d36 + {lv['field_measured']} measured"
                    + (f" + {lv['field_no_evidence']} 无证据" if lv['field_no_evidence'] else "")
                    + f") + {lv['scalar_disp']} scalar-disp + "
                    f"{lv['reported_only']} reported-only")
    report = {
        'milestone': 'M14/D37-W4a + T-A7 (64 cases)',
        'note': '关 3 证据机读化（W4a 状态分级）：禁止把 reported-only 计入 PASS，'
                '也禁止把「继承来的 PASS」计入 field-level（T-A7 / N-6）。'
                f'v1.1 起覆盖 {len(rows)} 条：'
                f"翼盒 field-level {n_field_total} 条（其中 {lv['field_d36']} 条引用 d36 既有明细、"
                f"{lv['field_measured']} 条为 2026-10-28 verify_solvers 实测）"
                f" + {lv['scalar_disp']} 条 scalar-disp-gated（<1%）"
                f" + {lv['reported_only']} 条柱壳 REPORTED-ONLY"
                '（D20 场级判据在归档包 F:/FEA_Archive_20261024/，需时解包重算）。'
                f"对外表述统一为「{headline_txt}」，不说 {len(rows)}/{len(rows)}。"
                '★ N-8：文件名保留 all55 是历史（CLAIMS C-003 的 artifact 指针指向它），'
                f'内容已是 {len(rows)} 条。',
        'headline_cn': headline_txt,
        'n_cases': len(rows),
        'n_gated_pass': sum(1 for r in rows if r['pass'] and r.get('gate_status', 'field-level') in ('GATED', 'field-level')),
        'n_reported_only': lv['reported_only'],
        # n_fail 必须覆盖 field-level（含无证据），不只 GATED —— 旧版会漏掉翼盒的 FAIL
        'n_fail': sum(1 for r in rows
                      if not r['pass']
                      and not r.get('gate_status', '').startswith('REPORTED')),
        'evidence_levels': {
            'field': n_field_total,
            'field_from_d36': lv['field_d36'],
            'field_measured': lv['field_measured'],
            'field_no_evidence': lv['field_no_evidence'],
            'scalar_disp': lv['scalar_disp'],
            'reported_only': lv['reported_only'],
        },
        'measured_source': 'reports/diagnostics/xval_v11_9cases.json' if measured else None,
        'tolerance': {'disp_pct': TOL_DISP_PCT},
        'cases': rows,
        'all_gated_ok': all(r['pass'] for r in rows
                            if r.get('gate_status', 'field-level') in ('GATED', 'field-level')),
    }
    out = os.path.join(FEA, 'gate3_all55_d37.json')
    json.dump(report, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"gate3_all55: cases={report['n_cases']} gated_pass={report['n_gated_pass']} "
          f"reported_only={report['n_reported_only']} fail={report['n_fail']} "
          f"(field={n_field_total}, scalar_disp={lv['scalar_disp']})")
    print(f'对外表述：{headline_txt}（不说 {len(rows)}/{len(rows)}）')
    for r in rows:
        if not r['pass']:
            print('  FAIL', r['case_id'], r.get('error', ''))
    print('report ->', out)
    return 0 if report['all_gated_ok'] else 2

if __name__ == '__main__':
    sys.exit(main())
