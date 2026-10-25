# -*- coding: utf-8 -*-
"""
evaluate.py — FEM-Bench-Aero 评测器（ROADMAP W2-2，A1 题型最小闭环）

输入：候选 spec.json（A1：NL→FEASpec 的产物）
流程：run_pipeline(ccx) → 关1 网格(batch_summary.min_quality)
      → 关4 语义(topology.compare，复用 feagpt.topology，零逻辑复制)
      → 物理保真(max_disp 相对数据集真值，判据口径对齐双码 <1%)
输出：eval_runs/<task_id>/evaluation.json（逐闸四元组：字段/期望/实测/结论）

用法：
  python evaluate.py --task-id L1_naca4412_wingbox --spec cand.json
  python evaluate.py --batch --tasks tasks/tasks.jsonl --levels L1 --limit 3 --use-gold
      （--use-gold：用数据集规范化 spec 当候选，冒烟用）
"""
import json, os, sys, subprocess, argparse, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FEA = os.path.join(ROOT, 'FEM-Bench-Aero')
RUNS = os.path.join(HERE, 'eval_runs')
PY = sys.executable


def require_dataset(fea=None):
    """前置闸（W5a'）：金标准数据集本体不在 git（`modeling/` 被 .gitignore 排除，由
    fetch_data.py 解包分发）。缺 gold 时 spec_fidelity 会把所有候选判成 spec_fail，
    于是 clean clone 上「0/11」看起来像模型全错——**静默空转必须改成硬错误**。

    返回 None 表示可用；否则返回错误说明字符串。
    """
    fea = fea or FEA
    # 只硬性要求 modeling/（ccx 可发布树，evaluate 用它的 spec.json 作金标准）；
    # _xval/（Abaqus 树）按发布策略不随数据包分发，只有双码交叉校验才需要 ⇒ 不阻断评测。
    need = [os.path.join(fea, 'modeling')]
    missing = [p for p in need if not os.path.isdir(p)]
    if missing:
        return (f'缺少金标准数据集：{missing}（git 里没有数据集本体）。'
                f'先跑 `python fetch_data.py --src <FEM-Bench-Aero-v1.0-data.tar.gz>` 解包后再评测；'
                f'否则所有候选都会被判 spec_fail，看起来像模型全错（W5a\' 已加此闸防静默空转）。')
    return None

MIN_J = 0.30          # 关1 判据（D10）
FID_TOL_PCT = 1.0     # 辅助闸：max_disp 相对偏差（只证"算得像"，不再承担"答案正确"——W4a 纠偏 3.1）
FLOAT_TOL = 1e-6      # spec_fidelity 浮点相对容差（W4a 纠偏 P0-1）

# 字段级真值表（按族）。整数/枚举/字符串/数组：精确相等；浮点：相对误差 < 1e-6。
GRADED_FIELDS = {
    'wingbox': ('airfoil', ['code', 'chord', 'span', 'skin_thickness', 'n_ribs',
                            'rib_thickness', 'spar_chordwise', 'n_stringers_per_skin',
                            'stringer_height', 'stringer_thickness', 'stringer_kind',
                            'stringer_flange_width', 'tip_chord_ratio', 'sweep_deg',
                            'web_chordwise']),
    'open_hole_panel': ('params', ['length', 'width', 'thickness', 'hole_d',
                                   'hole_x', 'hole_y', 'layup']),
    'fuselage_barrel': ('params', ['diameter', 'length', 'thickness',
                                   'n_stringers', 'n_frames']),
    'stiffened_panel': ('params', ['length', 'width', 'thickness', 'n_stringers']),
}
GRADED_MATERIAL = ['name', 'youngs_modulus', 'poisson_ratio']          # 必判
REPORTED_MATERIAL = ['density', 'yield_strength']                      # 只报不判

# W4d 拍板（2026-10-25，工程层判+配置层只报）：
# 执行配置键 = 求解器内部配置，NL 任务书永远不会提及——REPORTED NOT GATED（填错单独报告，不进 TSR）。
EXEC_CONFIG_KEYS = {
    'mesh': {'algorithm_2d', 'element_order', 'leading_edge_threshold',
             'min_jacobian', 'recombination_algorithm', 'recombine',
             'refine_at_leading_edge'},
    'analysis': {'incremental', 'initial_increment', 'outputs', 'step_type',
                 'total_time'},
    # gold 内部编码键（数据集离散索引/方向轴表示，NL 任务书永远不会提及）
    'extra': {'sweep_index', 'shear_axis', 'moment_axis'},
}
# W4e 收紧（专家第四轮 P0-4/R18，预注册于 RUBRIC.md）：纯元数据自创键白名单只保留
# 真正的描述性说明；'type'/'element(s)'/'order'/'application'/'point' 等可承载语义的键
# 一律移出（schema additionalProperties=false 同步拒收，修复循环会删）。
# 白名单外自创键（载荷/几何/边界/材料语义编造）照罚 FAIL。键名即契约，同义键不豁。
METADATA_KEY_NAMES = {'note', 'units', 'unit_system', 'description'}
METADATA_KEY_SUFFIXES = ('_units', '_note')
# 死字段：无长桁（n_stringers_per_skin=0/缺）时 gold 里的模板默认值——不可知，豁免。
DEAD_STRINGER_KEYS = {'stringer_height', 'stringer_thickness', 'stringer_kind',
                      'stringer_flange_width'}


def _field_equal(a, b):
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_field_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
            and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) <= FLOAT_TOL * max(1.0, abs(float(b)))
    return a == b


def spec_fidelity(cand_spec, gold_spec, family, input_mesh_keys=None, input_load_keys=None,
                  engineering_layer=False):
    """W4a P0-1：字段级真值校验（强制闸）。任一字段 FAIL ⇒ 整体 FAIL。

    engineering_layer（W4d 拍板，仅 L3）：
      - 死字段豁免：wingbox 且候选 n_stringers_per_skin=0/缺 时，stringer_* 不判
      - 执行配置键（EXEC_CONFIG_KEYS）：填错 REPORTED NOT GATED，不 FAIL
      - 自创键检查照旧 FAIL（编造语义字段不可豁免）
    """
    fields = []
    dead_skipped, exec_mismatch = [], []
    holder_key, keys = GRADED_FIELDS.get(family, ('params', []))
    cand_holder = (cand_spec.get('airfoil', {}) if holder_key == 'airfoil'
                   else cand_spec.get('structure', {}).get('params', {}))
    gold_holder = (gold_spec.get('airfoil', {}) if holder_key == 'airfoil'
                   else gold_spec.get('structure', {}).get('params', {}))
    # W4d：死字段豁免判定（仅 engineering_layer 且无长桁时生效）
    cand_ns = cand_holder.get('n_stringers_per_skin', 0)
    skip_dead = engineering_layer and holder_key == 'airfoil' and not cand_ns
    # W4d：bc 块只对 wingbox 判——pipeline 不消费 spec.bc（边界由各族 builder 代码决定，
    # 非 wingbox 族 gold bc 是死模板值 {root_surface,clamp}，NL 推不出且语义误导）
    bc_skip = engineering_layer and family != 'wingbox'
    for k in keys:
        if skip_dead and k in DEAD_STRINGER_KEYS:
            dead_skipped.append(f'{holder_key}.{k}')
            continue
        cv, gv = cand_holder.get(k, '<missing>'), gold_holder.get(k, '<missing>')
        if cv == '<missing>' and gv == '<missing>':
            ok = True          # 双方一致缺省（可选字段，如 hole_x 仅偏心孔有）= 一致
        elif cv == '<missing>' or gv == '<missing>':
            ok = False         # 单边缺 = 不一致
        else:
            ok = _field_equal(cv, gv)
        fields.append({'field': f'{holder_key}.{k}', 'expected': gv, 'actual': cv, 'pass': ok})
    # 结构族与材料必判项
    for label, path in (('structure.family', ('structure', 'family')),):
        cv = cand_spec.get(path[0], {}).get(path[1], '<missing>')
        gv = gold_spec.get(path[0], {}).get(path[1], '<missing>')
        fields.append({'field': label, 'expected': gv, 'actual': cv, 'pass': cv == gv})
    for k in GRADED_MATERIAL:
        cv = cand_spec.get('material', {}).get(k, '<missing>')
        gv = gold_spec.get('material', {}).get(k, '<missing>')
        fields.append({'field': f'material.{k}', 'expected': gv, 'actual': cv,
                       'pass': _field_equal(cv, gv) if cv != '<missing>' else False})
    for k in REPORTED_MATERIAL:   # 只报不判（声明）
        cv = cand_spec.get('material', {}).get(k)
        gv = gold_spec.get('material', {}).get(k)
        fields.append({'field': f'material.{k}', 'expected': gv, 'actual': cv,
                       'pass': True, 'reported_not_gated': True})
    # 网格/载荷/边界/分析/extra（W4c 纠偏 P0-2：gold 权威判定，不再按任务输入键集——
    # L3 只有 nl 时旧逻辑完全不判；柱壳 extra={}（端剪/端弯是主载荷）曾 23/23 PASS）。
    # analysis.solver 是执行选择，不作真值（专家 3.2）。
    for holder in ('mesh', 'load', 'bc', 'analysis', 'extra'):
        if holder == 'bc' and bc_skip:
            continue
        gh = gold_spec.get(holder, {})
        ch = cand_spec.get(holder, {})
        for k in sorted(gh.keys()):
            if holder == 'analysis' and k == 'solver':
                continue
            gv = gh[k]
            cv = ch.get(k, '<missing>')
            # W4d：执行配置键 REPORTED NOT GATED（填错单独报告，不 FAIL）
            if engineering_layer and k in EXEC_CONFIG_KEYS.get(holder, ()):
                if cv != '<missing>' and not _field_equal(cv, gv):
                    exec_mismatch.append({'field': f'{holder}.{k}',
                                          'expected': gv, 'actual': cv})
                continue
            # W4d：pressure 的 direction 是数据集内部约定（内压径向，NL 不会给向量）——豁免
            if engineering_layer and holder == 'load' and k == 'direction' \
                    and gh.get('kind') == 'pressure':
                if cv != '<missing>' and not _field_equal(cv, gv):
                    exec_mismatch.append({'field': 'load.direction (pressure)',
                                          'expected': gv, 'actual': cv})
                continue
            ok = _field_equal(cv, gv)
            fields.append({'field': f'{holder}.{k}', 'expected': gv, 'actual': cv, 'pass': ok})
    # 候选自创键（gold 没有、candidate 写了的非空键）：
    #   纯元数据（METADATA_*）REPORTED NOT GATED；载荷/几何/边界语义编造照罚（W4d 拍板）。
    #   W4e（专家第四轮 P0-4）：bc_skip 时仍查 bc 自创键（panel bc.support 曾借 skip 漏判）；
    #   material 块自创键（ply_material 等）照罚——builder 按 TypeError 拒收，SFR 必须同口径。
    metadata_extra = []
    for holder in ('mesh', 'load', 'bc', 'analysis', 'extra'):
        gh, ch = gold_spec.get(holder, {}), cand_spec.get(holder, {})
        for k in sorted(set(ch) - set(gh)):
            if ch[k] in ('', {}, None, []):
                continue
            is_meta = k in METADATA_KEY_NAMES or any(k.endswith(s) for s in METADATA_KEY_SUFFIXES)
            if is_meta:
                metadata_extra.append({'field': f'{holder}.{k}', 'actual': ch[k]})
            else:
                fields.append({'field': f'{holder}.{k} (not in gold)',
                               'expected': '<absent>', 'actual': ch[k], 'pass': False})
    for k in sorted(set(cand_spec.get('material', {})) - set(gold_spec.get('material', {}))):
        if cand_spec['material'][k] in ('', {}, None, []):
            continue
        is_meta = k in METADATA_KEY_NAMES or any(k.endswith(s) for s in METADATA_KEY_SUFFIXES)
        if is_meta:
            metadata_extra.append({'field': f'material.{k}', 'actual': cand_spec['material'][k]})
        else:
            fields.append({'field': f'material.{k} (not in gold)',
                           'expected': '<absent>', 'actual': cand_spec['material'][k],
                           'pass': False})
    fails = [f for f in fields if not f['pass']]
    out = {'pass': not fails, 'n_fields': len(fields), 'n_fail': len(fails),
           'failed': fails[:15]}
    if engineering_layer:
        out['engineering_layer'] = True
        out['dead_fields_skipped'] = dead_skipped
        out['exec_config_mismatch'] = exec_mismatch[:10]
        out['metadata_extra'] = metadata_extra[:10]
    return out


def load_tasks(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def gold_spec_path(case_id):
    return os.path.join(FEA, 'modeling', case_id, 'spec.json')


def _input_mesh_load_keys(task):
    """任务输入里 mesh/load 出现过的键（考什么判什么；gold 内部默认键不考）。"""
    norm = task.get('input', {}).get('spec_normalized', {})
    return (sorted(norm.get('mesh', {}).keys()), sorted(norm.get('load', {}).keys()))


def evaluate_one(task, cand_spec_path, out_root=RUNS, timeout=1800, skip_solve=False):
    task_id = task['task_id']
    run_dir = os.path.join(out_root, task_id)
    os.makedirs(run_dir, exist_ok=True)
    result = {'task_id': task_id, 'family': task['family'],
              'split_v2': task['split_v2'], 'input_level': task['input_level'],
              'candidate_spec': cand_spec_path, 'gates': {}, 'overall_pass': False}

    if skip_solve:
        # 负控快通道：只跑 spec_fidelity（字段级真值），不起求解器
        case_id = (task['task_id'].replace('L1_', '').replace('L2_', '').replace('L3_', '')
                   .replace('_final', '').replace('cand_', ''))
        gold_spec_path = os.path.join(FEA, 'modeling', case_id, 'spec.json')
        if os.path.exists(gold_spec_path):
            gold_spec = json.load(open(gold_spec_path, encoding='utf-8'))
            gold_spec.pop('workdir', None)
            cand_json = json.load(open(cand_spec_path, encoding='utf-8'))
            if 'spec' in cand_json and 'structure' not in cand_json:
                cand_json = cand_json['spec'] or {}   # gen_candidates 包装结构解包
            cand_json.pop('workdir', None)
            mk, lk = _input_mesh_load_keys(task)
            sf = spec_fidelity(cand_json, gold_spec, task['family'], input_mesh_keys=mk, input_load_keys=lk,
                               engineering_layer=(task.get('input_level') == 'L3'))
        else:
            sf = {'pass': False, 'n_fields': 0, 'n_fail': 1,
                  'failed': [{'field': 'gold spec', 'expected': gold_spec_path, 'actual': 'missing'}]}
        sf['field'] = 'spec_fidelity (field-level, mandatory, skip-solve)'
        sf['expected'] = 'all graded fields equal (float tol 1e-6)'
        sf['actual'] = f"{sf['n_fields'] - sf['n_fail']}/{sf['n_fields']} fields"
        result['gates']['spec_fidelity'] = sf
        result['overall_pass'] = sf['pass']
        out_path = os.path.join(run_dir, 'evaluation.json')
        json.dump(result, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return result

    # ---- 0. W4c P0-1/R10：候选契约校验 + 解包（全链路径不再静默降级）----
    raw_cand = json.load(open(cand_spec_path, encoding='utf-8'))
    if 'spec' in raw_cand and 'structure' not in raw_cand:
        raw_cand = raw_cand['spec'] or {}          # gen_candidates 包装结构解包
    raw_cand.pop('workdir', None)
    contract_fail = None
    fam = (raw_cand.get('structure') or {}).get('family')
    if not fam:
        contract_fail = 'structure.family missing (packaged or incomplete candidate)'
    elif not raw_cand.get('bc'):
        contract_fail = 'bc empty (boundary conditions required)'
    elif fam == 'fuselage_barrel' and not (raw_cand.get('extra') or {}).get('end_shear'):
        contract_fail = 'fuselage_barrel extra.end_shear missing (main load case)'
    if contract_fail:
        result['gates']['pipeline'] = {
            'pass': False, 'field': 'contract_ok', 'expected': 'runnable FEASpec',
            'actual': contract_fail,
            'detail': 'W4c R10: 拒绝静默降级——不进入求解'}
        result['overall_pass'] = False
        out_path = os.path.join(run_dir, 'evaluation.json')
        json.dump(result, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return result
    # 解包后的 spec 落盘，run_pipeline 只见纯 FEASpec。
    # W4d：剥离「gold 没有且属纯元数据」的自创键（FEASpec dataclass 不收未知键，
    # 判分层豁免的元数据不能在全链炸掉模型——两层口径一致）；语义自创键保留，
    # 由 FEASpec/pipeline 拒绝（编造语义候选 MSR 照死）。
    case_id_early = (task_id.replace('L1_', '').replace('L2_', '').replace('L3_', '')
                     .replace('_final', '').replace('cand_', ''))
    gold_early_path = os.path.join(FEA, 'modeling', case_id_early, 'spec.json')
    metadata_stripped = []
    if os.path.exists(gold_early_path):
        gold_early = json.load(open(gold_early_path, encoding='utf-8'))
        for holder in ('mesh', 'load', 'bc', 'analysis', 'extra'):
            gh = gold_early.get(holder, {})
            ch = raw_cand.get(holder)
            if not isinstance(ch, dict):
                continue
            for k in sorted(set(ch) - set(gh)):
                if k in METADATA_KEY_NAMES or any(k.endswith(s) for s in METADATA_KEY_SUFFIXES):
                    ch.pop(k, None)
                    metadata_stripped.append(f'{holder}.{k}')
    cand_spec_path = os.path.join(run_dir, 'candidate.spec.json')
    json.dump(raw_cand, open(cand_spec_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    result['metadata_stripped'] = metadata_stripped

    # ---- 0b. W4f（专家第四轮 P0-4/R19）：契约试建闸——可判的 spec 必须可建。
    # FEASpec 构造 + 族校验在进入 run_pipeline 之前完成；失败 ⇒ contract FAIL，
    # 不浪费求解时间，且失败分层明确（TypeError=自创键 / ValueError=族校验拒收）。
    try:
        from feagpt.spec import FEASpec
        FEASpec.from_dict(json.loads(json.dumps(raw_cand)))
    except Exception as e:      # TypeError/ValueError 都算模型 spec 质量问题
        result['gates']['pipeline'] = {
            'pass': False, 'field': 'contract_buildable', 'expected': 'FEASpec constructable',
            'actual': f'{type(e).__name__}: {e}',
            'detail': 'R19 试建闸：schema/builder/grader 三层一致；构造失败不进入求解'}
        result['failure_class'] = 'model'
        result['overall_pass'] = False
        out_path = os.path.join(run_dir, 'evaluation.json')
        json.dump(result, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return result

    # ---- 1. 跑 pipeline（ccx 全链）----
    t0 = time.time()
    proc = subprocess.run(
        [PY, os.path.join(HERE, 'run_pipeline.py'),
         '--spec', cand_spec_path, '--out', run_dir, '--solver', 'ccx'],
        capture_output=True, text=True, timeout=timeout, cwd=HERE)
    result['pipeline_rc'] = proc.returncode
    result['wall_seconds'] = round(time.time() - t0, 1)
    if proc.returncode != 0:
        result['gates']['pipeline'] = {
            'pass': False, 'field': 'run_pipeline', 'expected': 'rc=0',
            'actual': f'rc={proc.returncode}',
            'detail': (proc.stdout[-800:] + '\n' + proc.stderr[-800:])[-1200:]}
        return result

    # ---- 2. 读 batch_summary → 关1 网格 ----
    bs = json.load(open(os.path.join(run_dir, 'batch_summary.json'), encoding='utf-8'))
    entry = bs[0] if isinstance(bs, list) else bs
    mesh = entry.get('mesh') or {}
    min_q = mesh.get('min_quality')
    result['gates']['mesh_quality'] = {
        'pass': bool(entry.get('ok')) and min_q is not None and min_q >= MIN_J,
        'field': 'mesh.min_quality', 'expected': f'>= {MIN_J}',
        'actual': min_q, 'n_tri3': mesh.get('n_tri3'),
        'n_nodes': (mesh.get('node_count') or (mesh.get('element_types') and None))}

    # ---- 3. 关4 语义（复用 topology.compare，零逻辑复制）----
    case_name = entry.get('name')
    truth_path = os.path.join(run_dir, case_name, f'{case_name}.truth.json')
    if not os.path.exists(truth_path):
        result['gates']['semantics'] = {'pass': False, 'field': 'truth.json',
                                        'expected': 'exists', 'actual': 'missing'}
        return result
    truth = json.load(open(truth_path, encoding='utf-8'))
    topo = truth.get('topology')
    if not topo:
        result['gates']['semantics'] = {'pass': False, 'field': 'topology',
                                        'expected': 'present', 'actual': 'absent'}
        return result
    sys.path.insert(0, HERE)
    from feagpt import topology as topo_mod
    gate4 = topo_mod.compare(topo)
    fails = [c for c in gate4['checks'] if not c['pass']]
    result['gates']['semantics'] = {
        'pass': bool(gate4['pass']), 'field': 'topology.compare',
        'expected': f"{len(gate4['checks'])} checks pass",
        'actual': f"{len(gate4['checks']) - len(fails)}/{len(gate4['checks'])}",
        'failed_checks': [{'key': c['key'], 'expected': c['expected'],
                           'actual': c['actual']} for c in fails][:10]}

    # ---- 4. 物理保真：max_disp vs 数据集真值（辅助闸，W4a 降级：只证"算得像"）----
    ref = json.load(open(os.path.join(FEA, task['truth_ref']), encoding='utf-8'))
    cand_disp = (truth.get('scalars') or {}).get('max_disp')
    gold_disp = (ref.get('scalars') or {}).get('max_disp')
    if cand_disp is None or gold_disp in (None, 0):
        result['gates']['fidelity_disp'] = {'pass': False, 'field': 'scalars.max_disp',
                                            'expected': gold_disp, 'actual': cand_disp}
    else:
        dev_pct = abs(cand_disp - gold_disp) / abs(gold_disp) * 100.0
        result['gates']['fidelity_disp'] = {
            'pass': dev_pct < FID_TOL_PCT, 'field': 'scalars.max_disp',
            'expected': f'{gold_disp:.6f} ±{FID_TOL_PCT}%', 'actual': f'{cand_disp:.6f}',
            'dev_pct': round(dev_pct, 4)}
        result['fidelity_disp_dev_pct'] = round(dev_pct, 4)

    # ---- 4b. spec_fidelity 字段级真值（W4a P0-1 强制闸）----
    case_id = task['task_id']
    case_id = case_id.replace('L1_', '').replace('L2_', '').replace('L3_', '') \
                     .replace('_final', '').replace('cand_', '')
    gold_spec_path = os.path.join(FEA, 'modeling', case_id, 'spec.json')
    if os.path.exists(gold_spec_path):
        gold_spec = json.load(open(gold_spec_path, encoding='utf-8'))
        gold_spec.pop('workdir', None)
        cand_json = json.load(open(cand_spec_path, encoding='utf-8'))
        if 'spec' in cand_json and 'structure' not in cand_json:
            cand_json = cand_json['spec'] or {}   # gen_candidates 包装结构解包
        cand_json.pop('workdir', None)
        mk, lk = _input_mesh_load_keys(task)
        sf = spec_fidelity(cand_json, gold_spec, task['family'], input_mesh_keys=mk, input_load_keys=lk,
                           engineering_layer=(task.get('input_level') == 'L3'))
        sf['field'] = 'spec_fidelity (field-level, mandatory)'
        sf['expected'] = 'all graded fields equal (float tol 1e-6)'
        sf['actual'] = f"{sf['n_fields'] - sf['n_fail']}/{sf['n_fields']} fields"
        result['gates']['spec_fidelity'] = sf
    else:
        result['gates']['spec_fidelity'] = {'pass': False, 'field': 'gold spec',
                                            'expected': gold_spec_path, 'actual': 'missing'}

    # ---- 5. 总判定 ----
    result['overall_pass'] = all(g['pass'] for g in result['gates'].values())
    out_path = os.path.join(run_dir, 'evaluation.json')
    json.dump(result, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    result['evaluation_json'] = out_path
    return result


def evaluate_clarification(task, clar_path, out_root=RUNS, timeout=1800):
    """L2 评测（W3-2）：clarify_then_semantics 闸 + final_spec 三闸。

    clarification.json 协议（candidate 提交）：
      {"task_id": ..., "questions": [{"field": "rib_thickness", "question": "..."}],
       "final_spec": {...补全后的完整 spec...}}
    判分：
      clarify 闸 —— expected_clarifications 里每个缺字段都必须被【显式提问】；
                    若 final_spec 静默填了值而没提问 => FAIL（考「追问」不考「猜」）。
      其余闸    —— 对 final_spec 走 L1 同款三闸（跑 pipeline）。
    """
    task_id = task['task_id']
    clar = json.load(open(clar_path, encoding='utf-8'))
    run_dir = os.path.join(out_root, task_id)
    os.makedirs(run_dir, exist_ok=True)
    result = {'task_id': task_id, 'input_level': 'L2',
              'split_v2': task['split_v2'], 'gates': {}, 'overall_pass': False}

    expected = task.get('expected_clarifications', [])
    asked = {q.get('field') for q in clar.get('questions', []) if isinstance(q, dict)}
    missing_ask = [f for f in expected if f not in asked]
    final_spec = clar.get('final_spec')

    # clarify 闸：缺字段要么被问、要么 final_spec 里【确实没有】该字段（等待用户给）；
    # 静默编造默认值 = FAIL。
    silent = []
    for f in expected:
        if f in asked:
            continue
        # final_spec 是否偷偷补了值？
        a = final_spec.get('airfoil', {}) if isinstance(final_spec, dict) else {}
        p = (final_spec.get('structure', {}) or {}).get('params', {}) if isinstance(final_spec, dict) else {}
        if f in a or f in p:
            silent.append(f)
    result['gates']['clarify'] = {
        'pass': len(missing_ask) == 0 and len(silent) == 0,
        'field': 'expected_clarifications',
        'expected': f'ask about {expected}',
        'actual': f'asked={sorted(asked)} silent_default={silent}',
        'missing_ask': missing_ask, 'silent_default': silent}
    result['clarification_json'] = clar_path

    # final_spec 落盘走 L1 同款三闸；clarify 已 FAIL 则短路（不浪费求解时间）
    if isinstance(final_spec, dict) and result['gates']['clarify']['pass']:
        spec_path = os.path.join(run_dir, 'final_spec.json')
        final_spec.setdefault('name', task['task_id'].replace('L2_', 'cand_', 1))
        json.dump(final_spec, open(spec_path, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        sub = evaluate_one({**task, 'input_level': 'L2-final', 'task_id': task_id + '_final'},
                           spec_path, out_root=out_root, timeout=timeout)
        result['gates'].update(sub['gates'])
        result['gates'].pop('pipeline', None) if sub['gates'].get('pipeline', {}).get('pass', True) else None
        result['fidelity_disp_dev_pct'] = sub.get('fidelity_disp_dev_pct')
        result['overall_pass'] = all(g['pass'] for g in result['gates'].values())
    else:
        result['overall_pass'] = False

    out_path = os.path.join(run_dir, 'evaluation.json')
    json.dump(result, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-id')
    ap.add_argument('--spec')
    ap.add_argument('--batch', action='store_true')
    ap.add_argument('--tasks', default=os.path.join(HERE, 'tasks', 'tasks.jsonl'))
    ap.add_argument('--levels', default='L1', help='逗号分隔：L1,L2')
    ap.add_argument('--splits', default='id_test,extrapolation_test,train,val')
    ap.add_argument('--limit', type=int, default=3)
    ap.add_argument('--use-gold', action='store_true',
                    help='用数据集规范化 spec 冒烟（不产生真实 LLM 候选）')
    args = ap.parse_args()

    if not args.batch:
        if not (args.task_id and args.spec):
            ap.error('单任务模式需要 --task-id 与 --spec')
        tasks = {t['task_id']: t for t in load_tasks(args.tasks)}
        t = tasks[args.task_id]
        if t['input_level'] == 'L2':
            r = evaluate_clarification(t, args.spec)   # --spec 传 clarification.json
        else:
            r = evaluate_one(t, args.spec)
        print(json.dumps(r, ensure_ascii=False, indent=1)[:2000])
        sys.exit(0 if r['overall_pass'] else 2)

    # 批量
    levels = set(args.levels.split(','))
    splits = set(args.splits.split(','))
    sel = [t for t in load_tasks(args.tasks)
           if t['input_level'] in levels and t['split_v2'] in splits]
    sel = sel[:args.limit]
    print(f'批量评测 {len(sel)} 条（levels={sorted(levels)} splits={sorted(splits)}）')
    n_pass = 0
    for t in sel:
        if t['input_level'] == 'L2' and args.use_gold:
            # 理想 candidate：显式提问全部缺字段 + final_spec = 规范化 gold 补全
            expected = t.get('expected_clarifications', [])
            clar = {'task_id': t['task_id'],
                    'questions': [{'field': f, 'question': f'请给出 {f}？'} for f in expected],
                    'final_spec': t['input']['spec_normalized']}
            cand = os.path.join(HERE, 'tasks', f'_clar_{t["task_id"]}.json')
            json.dump(clar, open(cand, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            r = evaluate_clarification(t, cand)
        elif args.use_gold:
            cand = args.spec
            norm = t['input'].get('spec_normalized') or t['input'].get('spec_normalized_from_nl')
            if norm:
                cand = os.path.join(HERE, 'tasks', f'_cand_{t["task_id"]}.json')
                norm = dict(norm)
                norm.setdefault('name', t['task_id'])
                json.dump(norm, open(cand, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            r = evaluate_one(t, cand)
        else:
            cand = args.spec
            r = evaluate_one(t, cand)
        print(f'--- {t["task_id"]} ({t["input_level"]}) ---')
        flag = 'PASS' if r['overall_pass'] else 'FAIL'
        n_pass += r['overall_pass']
        gsum = {k: v['pass'] for k, v in r['gates'].items()}
        print(f'  [{flag}] gates={gsum} '
              f'fidelity={r.get("fidelity_disp_dev_pct", "n/a")}% wall={r.get("wall_seconds")}s')
    print(f'\nTSR = {n_pass}/{len(sel)}')
    sys.exit(0)


if __name__ == '__main__':
    main()
