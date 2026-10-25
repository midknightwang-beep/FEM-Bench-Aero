# -*- coding: utf-8 -*-
"""
make_nl_human.py — 30 条人工 NL 初稿（ROADMAP W2-3）

纪律：NL 里的每个数字都从 tasks.jsonl 的规范化 spec 实读填充（不凭空写），
保证 candidate 产出 spec 跑 pipeline 后能与 truth 对上。
措辞人工多样化（工程口语/任务单/图纸风三种笔调），其中 L2 型故意缺字段
（expected_clarifications 登记缺什么），考「追问澄清」而非「静默默认」。

输出：tasks/nl_human.jsonl（30 行，input_source=human）
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = os.path.join(HERE, 'tasks', 'tasks.jsonl')

def fnum(v):
    return f"{v:g}"

def wb_text(p, style, omit=None):
    """翼盒句式。p = airfoil 参数 dict。omit = 故意略过的字段名。"""
    base = {
        '描述': f"NACA{p['code']} 翼盒：弦长 {fnum(p['chord'])} mm、展长 {fnum(p['span'])} mm，"
                f"蒙皮与前后梁腹板统一壁厚 {fnum(p['skin_thickness'])} mm，肋壁厚 {fnum(p['rib_thickness'])} mm，"
                f"{int(p['n_ribs'])} 道翼肋等距布置，前后梁位于 25%–70% 弦向，",
        '任务单': f"结构：翼盒（NACA{p['code']}）\n弦 {fnum(p['chord'])} / 展 {fnum(p['span'])} mm\n"
                  f"主承力壁厚 {fnum(p['skin_thickness'])} mm；肋 {int(p['n_ribs'])} 根、肋厚 {fnum(p['rib_thickness'])} mm\n"
                  f"梁位 0.25–0.70；",
        '图纸': f"翼盒类，NACA{p['code']} 剖面。弦向尺寸 {fnum(p['chord'])}，展向 {fnum(p['span'])}。"
                f"壁厚：蒙皮/梁 {fnum(p['skin_thickness'])}，肋 {fnum(p['rib_thickness'])}。肋数 {int(p['n_ribs'])}。"
                f"梁位 0.25–0.70。",
    }
    txt = base[style]
    ns = int(p.get('n_stringers_per_skin', 0))
    if ns > 0 and omit != 'n_stringers_per_skin':
        kind = p.get('stringer_kind', 'blade')
        txt += (f"每侧蒙皮 {ns} 根{kind}长桁（高 {fnum(p.get('stringer_height', 0))} mm、"
                f"厚 {fnum(p.get('stringer_thickness', 0))} mm），")
    if omit != 'tip_chord_ratio' and 'tip_chord_ratio' in p and p['tip_chord_ratio'] != 1.0:
        txt += f"梢根比 {p['tip_chord_ratio']:g}，"
    if p.get('sweep_deg', 0) != 0:
        txt += f"后掠 {p['sweep_deg']:g} 度，"
    if int(p.get('n_web', 0) or 0) > 0:
        pos = p.get('web_pos', 'centre')
        txt += f"加 {int(p['n_web'])} 道中间腹板（{pos}），"
    txt += ("材料铝 2024-T3。工况：翼尖施加 500 N 集中力（法向），根部固支，展向悬臂。"
            "单元全四边形壳，网格弦向 12 mm / 展向 25 mm。")
    return txt

def oh_text(p, style, mesh_size=None):
    lay = p.get('layup')
    if lay:
        angles = [int(pl['angle']) for pl in lay['plies']]
        m = lay['material']
        # W4d 考卷 v2：材料卡全键写全（从 gold 实读，不凭空写）——判层 layup 是整块字段，
        # 缺常数模型只能编造（实测 30 条里 cfrp 系全部因此失分）
        mat = (f"板基材铝 2024-T3，铺层 CFRP_T300 单层材料卡：E1={fnum(m['E1'])} MPa、"
               f"E2={fnum(m['E2'])} MPa、E3={fnum(m['E3'])} MPa、nu12={m['nu12']}、nu13={m['nu13']}、"
               f"nu23={m['nu23']}、G12={fnum(m['G12'])} MPa、G13={fnum(m['G13'])} MPa、"
               f"G23={fnum(m['G23'])} MPa、密度={m['density']:g} t/mm^3；"
               f"铺层角度 {angles}（单层 {fnum(lay['plies'][0]['thickness'])} mm）")
    else:
        mat = "铝 2024-T3"
    # W4d 考卷 v3：孔位/网格尺寸从 gold 实读（旧版硬编码「中心孔/网格 3 mm」，
    # offcentre 的 hole_x/hole_y 与 gold 网格 4.0mm 都推不出来）
    hole = f"孔心位于 ({fnum(p['hole_x'])}, {fnum(p['hole_y'])}) mm，" \
        if p.get('hole_x') or p.get('hole_y') else "中心孔"
    sz = mesh_size if mesh_size is not None else 3.0
    return (f"开孔拉伸板：{fnum(p['length'])} × {fnum(p['width'])} mm，厚 {fnum(p['thickness'])} mm，"
            f"{hole}直径 {fnum(p['hole_d'])} mm，{mat}。"
            f"两端施加 {fnum(p.get('load_n', 4000))} N 面内拉伸（端部均布），横向自由。"
            f"网格尺寸 {fnum(sz)} mm（弦向/展向同值），孔周加密。")

def fb_text(p, style):
    return (f"机身柱壳段：直径 {fnum(p['diameter'])} mm、长度 {fnum(p['length'])} mm，壳厚 {fnum(p['thickness'])} mm，"
            f"{int(p['n_stringers'])} 根长桁、{int(p['n_frames'])} 个普通框（blade 剖面）。"
            f"载荷组合：内压 0.05 MPa + 端部剪力 50 kN + 端部弯矩 50 kN·m。"
            f"材料铝 2024-T3，壳单元，周向与轴向网格各 25 mm。")

def sp_text(p, style, mesh_size=3.0):
    return (f"加筋壁板：{fnum(p['width'])} × {fnum(p['length'])} mm，板厚 {fnum(p['thickness'])} mm，"
            f"{int(p['n_stringers'])} 根 blade 长桁等距。四边简支，受 {fnum(p.get('pressure_mpa', 0.0001))} MPa 均布面压。"
            f"材料铝 2024-T3，板与筋全壳单元，网格尺寸 {fnum(mesh_size)} mm（弦向/展向同值）。")

STYLE_CYCLE = ['描述', '任务单', '图纸']

def main():
    tasks = [json.loads(ln) for ln in open(TASKS, encoding='utf-8') if ln.strip()]
    l1 = [t for t in tasks if t['input_level'] == 'L1']
    by_fam = {}
    for t in l1:
        by_fam.setdefault(t['family'], []).append(t)

    # 名额：wingbox 15 / open_hole 6 / fuselage_barrel 5 / stiffened_panel 4 = 30
    quota = {'wingbox': 15, 'open_hole_panel': 6, 'fuselage_barrel': 5, 'stiffened_panel': 4}
    # W4d 修正：omit 池只保留「文本真挖得掉」的字段。
    # rib_thickness 三个句式无条件书写、n_stringers_per_skin/tip_chord_ratio/stringer_height
    # 在「无长桁/无锥度」时本来就不书写（死字段，gold 为模板默认值）——登记它们是伪缺
    # （登记了 omit 但 NL 文本信息完备），历史上产生过 ec 与 NL 不一致的 4 条坏行。
    n_l2 = {'wingbox': 1, 'open_hole_panel': 1, 'fuselage_barrel': 1, 'stiffened_panel': 1}

    out = []
    for fam, n in quota.items():
        cands = by_fam.get(fam, [])
        # 优先挑非锚定基线的（覆盖更多样）
        picked = cands[:n]
        for i, t in enumerate(picked):
            norm = t['input']['spec_normalized']
            fam_ = t['family']
            omit = None
            if i < n_l2.get(fam_, 0):
                pool = {'wingbox': ['n_ribs'],
                        'open_hole_panel': ['hole_d'],
                        'fuselage_barrel': ['n_frames'],
                        'stiffened_panel': ['n_stringers']}[fam_]
                omit = pool[i % len(pool)]
            if fam_ == 'wingbox':
                p = dict(norm.get('airfoil', {}))
                p.setdefault('n_web', 0)
                for k in ('n_web',):
                    if k in norm.get('structure', {}).get('params', {}):
                        p[k] = norm['structure']['params'][k]
                if 'web_pos' in norm.get('structure', {}).get('params', {}):
                    p['web_pos'] = norm['structure']['params']['web_pos']
                txt = wb_text(p, STYLE_CYCLE[i % 3], omit=omit)
                if omit == 'n_ribs':
                    txt = txt.replace(f"{int(p['n_ribs'])} 道翼肋", "若干翼肋").replace(f"肋 {int(p['n_ribs'])} 根、", "").replace(f"肋数 {int(p['n_ribs'])}。", "")
            elif fam_ == 'open_hole_panel':
                pp = dict(norm['structure']['params'])
                pp['load_n'] = float(norm.get('load', {}).get('magnitude', 4000.0))
                ms = float(norm.get('mesh', {}).get('size_chord', 3.0))
                txt = oh_text(pp, STYLE_CYCLE[i % 3], mesh_size=ms)
                if omit == 'hole_d':
                    txt = txt.replace(f"中心孔直径 {fnum(pp['hole_d'])} mm，", "")
            elif fam_ == 'fuselage_barrel':
                txt = fb_text(norm['structure']['params'], STYLE_CYCLE[i % 3])
                if omit == 'n_frames':
                    txt = txt.replace(f"、{int(norm['structure']['params']['n_frames'])} 个普通框（blade 剖面）", "")
            else:
                ms = float(norm.get('mesh', {}).get('size_chord', 3.0))
                txt = sp_text(norm['structure']['params'], STYLE_CYCLE[i % 3], mesh_size=ms)
                if omit == 'n_stringers':
                    txt = txt.replace(f"{int(norm['structure']['params']['n_stringers'])} 根 blade 长桁等距。", "若干根长桁。")
            row = {
                'task_id': f"L3_{t['task_id'][3:]}",
                'family': fam_, 'input_level': 'L3', 'input_source': 'human',
                'input': {'nl': txt},
                'truth_ref': t['truth_ref'], 'gates': t['gates'],
                'split_v2': t['split_v2'], 'split_reason': t['split_reason'] + ' | L3 人工 NL',
                'geometry_class': t['geometry_class'],
            }
            if omit:
                row['expected_clarifications'] = [omit]
                # W4d 拍板：澄清题「问对=对」的判定关键词（人工登记，落盘可审计）
                row['clarify_keywords'] = {'n_ribs': ['肋'], 'hole_d': ['孔'],
                                           'n_frames': ['框'], 'n_stringers': ['长桁']}[omit]
                row['gates'] = ['clarify_then_' + g if g == 'semantics' else g for g in t['gates']]
            out.append(row)

    path = os.path.join(HERE, 'tasks', 'nl_human.jsonl')
    with open(path, 'w', encoding='utf-8') as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    n_l2c = sum(1 for r in out if 'expected_clarifications' in r)
    print(f"[OK] tasks/nl_human.jsonl（{len(out)} 行，其中缺字段澄清型 {n_l2c} 条）")
    for r in out[:3]:
        print(' ', r['task_id'], r['input']['nl'][:60], '...')

if __name__ == '__main__':
    main()
