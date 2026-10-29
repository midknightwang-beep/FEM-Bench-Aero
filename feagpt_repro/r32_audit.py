# -*- coding: utf-8 -*-
"""r32_audit.py — R32 审计（W5c-0，专家第八轮 §3.1/§5.1）

R32（RUBRIC v4.3）：**每条 exam 任务里，gold 有值的每个判分字段，题面必须能推出**，
否则任务不可解（模型按「不得编造」正确省略却被判 FAIL = 卷子的问题，不是模型的问题）。

本脚本对每个 (任务, 判分字段) 给出四选一判定：
  derivable_nl        题面里能找到依据（数值 token / 族词 / 载荷词 / 几何词）
  derivable_contract  题面没写，但**契约**唯一确定：材料卡（铝 2024-T3 的 E/ν）、
                      词汇表（面内拉伸 ⇒ load.kind="tip_force"）、族默认（无锥度 ⇒ 1.0）
  exempt:<kind>       本就不判：
                        exec_config —— 求解器内部配置键（EXEC_CONFIG_KEYS，只报不判）
                        dead        —— 死字段（无长桁时的 stringer_*；blade 剖面的
                                       stringer_flange_width —— blade 无物理缘条，
                                       见 feagpt/sections.py:tee 的退化契约 + check_forms T5）
                        bc_skip     —— 非翼盒族不判 bc（pipeline 不消费）
  VIOLATION           两者都不是 ⇒ 任务不可解，不得进 exam（R33 冻结闸）

**局限（必须承认）**：数值派生的判据是「题面里出现过这个数（含单位换算）」，
是**必要不充分**——任何一题里出现过的数字都可能碰巧命中无关数字。
所以本脚本是**筛查器**，不是证明器；它抓的是「题面根本没这个数」这一整类缺陷
（第八轮实测：中间腹板位置 3 条、T 长桁缘条宽 1 条、面板 load.kind 词汇缺口）。

用法：
  python r32_audit.py --tasks reports/papers/tasks_v6c.jsonl --scope exam \
      --out reports/r32_audit_v6c.json
  # 退出码：0 = 无 VIOLATION；1 = 有（NC-30 用它做闸）；2 = 数据缺失
"""
import json, os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluate import (GRADED_FIELDS, GRADED_MATERIAL, EXEC_CONFIG_KEYS,
                      DEAD_STRINGER_KEYS, FEA, load_tasks, require_dataset)
from score_baseline import stratum_of
from _paths import rel   # T-A11a：跨盘符安全（见 _paths.py）

# ---- 契约登记表（RUBRIC §7 / SYS prompt 逐条对应；改这里必须同步改文档与 NC-31）----
MATERIAL_CARD = {
    # SYS prompt 里给出的材料卡：题面只写「铝 2024-T3」就能确定 E/ν/ρ/屈服
    'Aluminium 2024-T3': {'youngs_modulus': 73100.0, 'poisson_ratio': 0.33,
                          'density': 2.78e-09, 'yield_strength': 345.0},
}
FAMILY_TOKENS = {
    'wingbox': ('翼盒',),
    'open_hole_panel': ('开孔', '拉伸板'),
    'fuselage_barrel': ('柱壳', '机身'),
    'stiffened_panel': ('壁板',),
}
LOAD_KIND_TOKENS = {
    # 词汇表（SYS prompt「词汇约定」）：面内拉伸在本数据集里编码为 tip_force
    'tip_force': ('集中力', '翼尖', '面内拉伸', '端部均布'),
    'pressure': ('内压', '面压', '均压', '均布面压', '压力', 'MPa'),
}
STRINGER_KIND_TOKENS = {'blade': ('blade',), 'T': ('T长桁', 'T 长桁', 'T型', 'T 型')}
# 题面里出现这些词 ⇒ 该字段的默认值不再适用（必须显式给值）
TRIGGER = {
    'tip_chord_ratio': ('梢根比', '锥度'),
    'sweep_deg': ('后掠',),
    'web_chordwise': ('中间腹板', '附加腹板', '道腹板', '腹板位于'),
    'n_stringers': ('长桁',),
    'n_stringers_per_skin': ('长桁',),
}
# ★ R33 第二端：非 exam 允许存在的**已登记** VIOLATION（白名单只许缩小，不许扩大）。
# 唯一出处就在这里——negative_controls.py 与 _verify_tasks_v6c.py 都 import 它，
# 免得两处各抄一份、日后改一处忘另一处（「两份白名单漂移」是典型的静默失效）。
# 每条都必须有理由，不许写「以后再说」：
#   stiffened_panel_800x600 / _str3 —— R41 数值角色：旧模板写「{width} × {length}」，
#   题面「600 × 800」与 gold length=800/width=600 角色相反。模板已修，v6c 候选未重生成（dev 侧，exam 0 条）。
KNOWN_NONEXAM_VIOL = {
    'L3_stiffened_panel_800x600',
    'L3_stiffened_panel_800x600_str3',
}

NUM_RE = re.compile(r'-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?')
UNIT_FACTORS = (1.0, 1e-9, 1e-6, 1e-3, 1e-2, 1e3, 1e6, 1e9)   # 1e-2 = 百分比→占比（25%–70% ⇒ 0.25/0.70）


def num_tokens(nl):
    out = []
    for s in NUM_RE.findall(nl):
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out


def num_derivable(v, toks, rel=1e-6):
    """v 能否由题面里的某个数经单位换算得到（必要不充分，见 docstring）。"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return False, None
    tol = rel * max(1.0, abs(v))
    for t in toks:
        for k in UNIT_FACTORS:
            if abs(t * k - v) <= tol:
                return True, f'{t:g}×{k:g}'
    return False, None


def _role_pos(nl, v, rel=1e-6):
    """R41：数值 v 在题面里**首次出现**的字符位置（含单位换算），定位不到返回 None。
    只认 ×1 / ×1e-3（mm↔m）这几档——够用于尺寸类，避免 1e-9 之类的巧合命中抢位。"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    tol = rel * max(1.0, abs(v))
    best = None
    for m in NUM_RE.finditer(nl):
        try:
            t = float(m.group(0))
        except ValueError:
            continue
        for k in (1.0, 1e-3, 1e3):
            if abs(t * k - v) <= tol:
                if best is None or m.start() < best:
                    best = m.start()
                break
    return best


def gold_of(case_id):
    p = os.path.join(FEA, 'modeling', case_id, 'spec.json')
    if not os.path.exists(p):
        return None
    s = json.load(open(p, encoding='utf-8'))
    s.pop('workdir', None)
    return s


def graded_items(gold, family):
    """该族实际参与判分的 (holder, key) 清单——与 evaluate.spec_fidelity 同口径。"""
    holder_key, keys = GRADED_FIELDS.get(family, ('params', []))
    holder = gold.get('airfoil', {}) if holder_key == 'airfoil' else \
        gold.get('structure', {}).get('params', {})
    items = [(holder_key, k, holder[k]) for k in keys if k in holder]
    for k in GRADED_MATERIAL:
        if k in (gold.get('material') or {}):
            items.append(('material', k, gold['material'][k]))
    for h in ('mesh', 'load', 'bc', 'analysis', 'extra'):
        if h == 'bc' and family != 'wingbox':
            continue          # bc_skip：非翼盒不判（evaluate.py 同口径）
        for k, v in (gold.get(h) or {}).items():
            if h == 'analysis' and k == 'solver':
                continue      # 执行选择，不作真值
            items.append((h, k, gold[h][k]))
    return items


def classify(task, gold, holder, key, val, toks):
    """返回 (klass, reason)。"""
    family = task['family']
    nl = task['input']['nl']
    holder_spec = (gold.get('airfoil') or {}) if holder == 'airfoil' else \
        (gold.get('structure', {}).get('params') or {})
    ns = int(holder_spec.get('n_stringers_per_skin', 0) or 0)
    kind = str(holder_spec.get('stringer_kind', 'blade'))

    # 0) 澄清题：该字段是**故意**不写的（expected_clarifications 登记在案，R17 判追问而非判值）
    if key in (task.get('expected_clarifications') or []):
        return 'exempt:clarify', '该字段是澄清题故意省略（expected_clarifications 已登记）'

    # 1.5) ★ R41 角色顺序：length 与 width 同时判分且值不等时，题面的书写顺序必须与字段角色一致。
    #      反例实证（W5c）：stiffened_panel_800x600 旧模板写「{width} × {length}」⇒「600 × 800」，
    #      gold 是 length=800 / width=600。两个数都在题面出现过（num_derivable 判 derivable），
    #      但顺序与 gold 角色相反 ⇒ 模型按工程惯例「长 × 宽」读成 length=600 被误判错。
    #      这是 R32 的**局限二：数值出现 ≠ 字段角色可判**，故单列成闸而不是塞进数值分支。
    #      判定：能定位到两个数在题面里的先后 ⇒ 要求「长度在前」；定位不到或顺序相反 ⇒ 必须显式标注角色。
    if holder == 'params' and key in ('length', 'width'):
        gl, gw = holder_spec.get('length'), holder_spec.get('width')
        if isinstance(gl, (int, float)) and isinstance(gw, (int, float)) and abs(gl - gw) > 1e-9:
            has_l = ('长度' in nl) or ('length' in nl.lower())
            has_w = ('宽度' in nl) or ('width' in nl.lower())
            if not (has_l and has_w):
                pos_l = _role_pos(nl, gl)
                pos_w = _role_pos(nl, gw)
                if pos_l is not None and pos_w is not None and pos_l < pos_w:
                    return 'derivable_nl', f'数值命中 {gl:g} → {gw:g}（书写顺序 = 长度→宽度，符合惯例）'
                return 'VIOLATION', (f'length/width 同时判分且值不等（{gl:g} vs {gw:g}），题面书写顺序与角色'
                                     f'不一致且未显式标注「长度/宽度」⇒ 字段角色不可判（R41）')

    # 2) 执行配置键：只报不判
    if key in EXEC_CONFIG_KEYS.get(holder, ()):
        return 'exempt:exec_config', 'EXEC_CONFIG_KEYS（只报不判）'
    if holder == 'load' and key == 'direction' and (gold.get('load') or {}).get('kind') == 'pressure':
        return 'exempt:exec_config', '内压方向是数据集内部约定（径向），题面不给向量'

    # 2) 死字段：无长桁时的长桁细节；blade 剖面的缘条宽
    if holder == 'airfoil' and key in DEAD_STRINGER_KEYS:
        if ns == 0:
            return 'exempt:dead', f'n_stringers_per_skin=0，{key} 是模板默认值'
        if key == 'stringer_flange_width' and kind != 'T':
            return 'exempt:dead', ('blade 剖面无物理缘条（sections.tee: flange_width<=0 ⇒ blade；'
                                   'check_forms T5 退化证明），gold 30.0 是模板默认值')

    # 3) 契约唯一确定：材料卡
    if holder == 'material':
        name = str((gold.get('material') or {}).get('name'))
        card = MATERIAL_CARD.get(name)
        if card and key in card and abs(float(card[key]) - float(val)) <= 1e-9 * max(1.0, abs(float(val))):
            return 'derivable_contract', f'材料卡 {name}（SYS prompt）唯一确定 {key}'
        if key == 'name':
            hit = [t for t in ('铝', '2024', '2024-T3') if t in nl]
            if hit:
                return 'derivable_contract', f'题面材料词命中 {hit} ⇒ 词汇表 "Aluminium 2024-T3"'
            return 'VIOLATION', '题面未给材料名'

    # 4) 族默认值（题面无触发词 ⇒ 默认值）
    if key in TRIGGER and not any(t in nl for t in TRIGGER[key]):
        if key in ('tip_chord_ratio', 'sweep_deg') and val in (1.0, 0.0):
            return 'exempt:default', f'题面无「{"或".join(TRIGGER[key])}」⇒ {key}={val:g}'
        if key == 'web_chordwise' and (val == [] or val == {}):
            return 'exempt:default', '题面无中间腹板 ⇒ web_chordwise=[]'
        if key in ('n_stringers', 'n_stringers_per_skin') and int(val or 0) == 0:
            return 'exempt:default', '题面无长桁 ⇒ 该键=0'

    # 5) 词汇表（族/载荷 kind/长桁 kind）
    if holder == 'structure' and key == 'family':
        if any(t in nl for t in FAMILY_TOKENS.get(family, ())):
            return 'derivable_nl', f'题面族词 {FAMILY_TOKENS[family]}'
        return 'VIOLATION', '题面无该族词'
    if holder == 'load' and key == 'kind':
        toks_kw = LOAD_KIND_TOKENS.get(str(val), ())
        hit = [t for t in toks_kw if t in nl]
        if hit:
            return 'derivable_contract' if val == 'tip_force' and '面内拉伸' in hit else 'derivable_nl', \
                f'题面载荷词命中 {hit}（词汇表映射）'
        return 'VIOLATION', f'题面无 {val} 的依据（词汇表 {toks_kw}）'
    if holder == 'airfoil' and key == 'stringer_kind':
        hit = [t for t in STRINGER_KIND_TOKENS.get(str(val), ()) if t in nl]
        if hit:
            return 'derivable_nl', f'题面长桁剖面词命中 {hit}'
        return 'VIOLATION', '题面未给长桁剖面型式'
    if holder == 'bc' and key == 'root_surface':
        if str(val) == 'root' and ('固支' in nl or '根部' in nl or '夹持' in nl):
            return 'derivable_contract', 'bc 契约（SYS prompt：{"root_surface":"root","clamp":true}）+ 题面「根部固支」'
        return 'VIOLATION', f'题面无根面依据（gold root_surface={val!r}）'
    if holder == 'airfoil' and key == 'code':
        if f"NACA{val}" in nl:
            return 'derivable_nl', f'题面 NACA{val}'
        return 'VIOLATION', '题面未给翼型代号'

    # 6) 数值 / 列表 / 嵌套 dict
    if isinstance(val, bool):
        if val and ('固支' in nl or '夹持' in nl or '固接' in nl):
            return 'derivable_nl', '题面「固支/夹持」'
        return 'VIOLATION', f'布尔值 {val} 题面无依据'
    if isinstance(val, (int, float)):
        ok, ev = num_derivable(val, toks)
        if ok:
            return 'derivable_nl', f'数值命中 {ev}'
        return 'VIOLATION', f'题面找不到数值 {val:g}（含单位换算）'
    if isinstance(val, (list, tuple)):
        if not val:
            return 'derivable_nl', '空列表（题面未提该特征）'
        bad = [x for x in val if not (
            num_derivable(x, toks)[0] if isinstance(x, (int, float)) else str(x) in nl)]
        if bad:
            return 'VIOLATION', f'列表元素 {bad} 题面无依据'
        return 'derivable_nl', f'列表 {len(val)} 个元素全部命中'
    if isinstance(val, dict):                    # 例如 params.layup
        flat = []

        def walk(d, pre=''):
            for kk, vv in d.items():
                if isinstance(vv, dict):
                    walk(vv, pre + kk + '.')
                elif isinstance(vv, list):
                    for it in vv:
                        if isinstance(it, dict):
                            walk(it, pre + kk + '[]' + '.')
                        else:
                            flat.append((pre + kk, it))
                else:
                    flat.append((pre + kk, vv))
        walk(val)
        bad = []
        for kk, vv in flat:
            if isinstance(vv, (int, float)) and not isinstance(vv, bool):
                if not num_derivable(vv, toks)[0]:
                    bad.append(f'{kk}={vv}')
            elif str(vv) not in nl:
                bad.append(f'{kk}={vv}')
        if bad:
            return 'VIOLATION', f'嵌套键值题面无依据：{bad[:4]}'
        return 'derivable_nl', f'嵌套 {len(flat)} 项全部命中'
    if isinstance(val, str):
        if val in nl:
            return 'derivable_nl', '字符串原样命中'
        return 'VIOLATION', f'题面无字符串 {val!r}'
    return 'VIOLATION', f'无法判定类型 {type(val).__name__}'


def main():
    err = require_dataset()
    if err:
        print('[dataset] ' + err)
        return 2
    argv = sys.argv[1:]
    def get(k, d):
        return argv[argv.index(k) + 1] if k in argv else d
    tasks_path = get('--tasks', os.path.join(HERE, 'tasks', 'tasks.jsonl'))
    scope = get('--scope', 'exam')          # exam | all
    out_path = get('--out', None)

    tasks = [t for t in load_tasks(tasks_path) if t['input_level'] == 'L3']
    if scope == 'exam':
        tasks = [t for t in tasks if stratum_of(t) is not None]
    rows, viol = [], []
    counts = collections.Counter()
    n_fields = 0
    for t in tasks:
        case_id = t['task_id'].replace('L3_', '')
        gold = gold_of(case_id)
        if gold is None:
            print(f'[WARN] 缺 gold spec：{case_id}')
            continue
        nl = t['input']['nl']
        toks = num_tokens(nl)
        rec = {'task_id': t['task_id'], 'family': t['family'],
               'exam_stratum': stratum_of(t), 'fields': [], 'violations': []}
        for holder, key, val in graded_items(gold, t['family']):
            if holder == 'structure' and key == 'family':
                v = gold['structure']['family']
            else:
                v = val
            klass, reason = classify(t, gold, holder, key, v, toks)
            n_fields += 1
            counts[klass] += 1
            field = f'{holder}.{key}' if holder != 'material' else f'material.{key}'
            rec['fields'].append({'field': field, 'gold': v if not isinstance(v, float) else round(v, 9),
                                  'class': klass, 'reason': reason})
            if klass == 'VIOLATION':
                rec['violations'].append(field)
                viol.append({'task_id': t['task_id'], 'family': t['family'],
                             'exam_stratum': stratum_of(t), 'field': field,
                             'gold': v, 'reason': reason})
        rows.append(rec)

    scope_tasks = len(rows)
    report = {
        'note': 'R32/R41 审计（W5c-0）：每个判分字段是否可从题面(NL)或已登记契约推出。'
                'derivable_nl/derivable_contract/exempt:* 合规；VIOLATION = 任务不可解，不得进 exam（R33）。'
                '★ 两处已知局限：①数值判据是「题面出现过该数（含单位换算）」，必要不充分——本脚本是筛查器不是证明器；'
                '②R41 单列「字段角色可判」：length/width 同时判分且值不等时，题面书写顺序须与角色一致或显式标注，'
                '否则模型按惯例读反了会被误判错（实证 stiffened_panel_800x600 旧模板「{width} × {length}」）。',
        'paper': rel(tasks_path, os.path.dirname(HERE)),
        'scope': scope, 'n_tasks': scope_tasks, 'n_fields': n_fields,
        'counts': dict(counts),
        'n_violations': len(viol),
        'violations_by_task': sorted({r['task_id'] for r in viol}),
        'violations': viol,
        'per_task': rows,
    }
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
        json.dump(report, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'== R32 审计（{scope}，{scope_tasks} 条 × {n_fields} 个判分字段）==')
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f'  {k:<22} {v}')
    print(f'  VIOLATION 合计 {len(viol)}')
    if viol:
        print('\n  违规清单：')
        for r in viol:
            print(f"    [{r['exam_stratum'] or 'dev'}] {r['task_id']:<44} {r['field']:<36} "
                  f"gold={json.dumps(r['gold'], ensure_ascii=False)[:40]} :: {r['reason']}")
    if out_path:
        print('\nreport ->', out_path)
    return 1 if viol else 0


if __name__ == '__main__':
    sys.exit(main())
