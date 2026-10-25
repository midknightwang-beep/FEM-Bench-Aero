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
    # W5a（专家第五轮 P0-1/R21）：载荷方向属任务输入，NL 必须给坐标系与方向向量——
    # 旧版只写「法向」，同一任务模型两次分别猜 [0,1,0]/[0,0,1]（exam 3 条因此失败）
    txt += ("材料铝 2024-T3。坐标系：x 弦向、y 弯曲方向（翼型法向）、z 展向。"
            "工况：翼尖施加 500 N 集中力，方向 [0,1,0]（沿 +y 弯曲方向），根部固支，展向悬臂。"
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
            f"坐标系：x 沿板长（拉伸方向）、y 板宽、z 板面法向。"
            f"两端施加 {fnum(p.get('load_n', 4000))} N 面内拉伸（端部均布），方向 [1,0,0]（沿 +x），横向自由。"
            f"网格尺寸 {fnum(sz)} mm（弦向/展向同值），孔周加密。")

def fb_text(p, style):
    # W4f（专家第四轮 P0-3/R19）：长桁剖面尺寸明示（builder 默认 25/2.5 实读，
    # feagpt/fuselage.py FuselageSpec）——旧版只说 blade 剖面不给尺寸，模型要么编要么填 0
    return (f"机身柱壳段：直径 {fnum(p['diameter'])} mm、长度 {fnum(p['length'])} mm，壳厚 {fnum(p['thickness'])} mm，"
            f"{int(p['n_stringers'])} 根长桁（blade 剖面，高 25 mm、厚 2.5 mm）、"
            f"{int(p['n_frames'])} 个普通框（blade 剖面）。"
            f"坐标系：z 沿壳轴（轴向）、x 水平横向、y 竖直。"
            f"载荷组合：内压 0.05 MPa（作用于壳体内壁，沿壁面内法向）+ 端部剪力 50 kN 沿 +x + 端部弯矩 50 kN·m 绕 y 轴。"
            f"材料铝 2024-T3，壳单元，周向与轴向网格各 25 mm。")

def sp_text(p, style, mesh_size=3.0):
    ns = int(p.get('n_stringers', 0))
    # W4f（P0-3/R19）：长桁尺寸明示（panel builder 默认 20/2.5，feagpt/panel.py）；
    # n_stringers=0 时写「无长桁」而非「0 根」（防模型照抄 0 进 spec）
    if ns > 0:
        st = f"{ns} 根 blade 长桁等距（高 20 mm、厚 2.5 mm）。"
    else:
        st = "无长桁（素板）。"
    return (f"加筋壁板：{fnum(p['width'])} × {fnum(p['length'])} mm，板厚 {fnum(p['thickness'])} mm，"
            f"{st}四边简支，受 {fnum(p.get('pressure_mpa', 0.0001))} MPa 均布面压，"
            f"方向 [0,0,-1]（沿 -z 压向板面；z 为板面法向，板位于 z=0 平面）。"
            f"材料铝 2024-T3，板与筋全壳单元，网格尺寸 {fnum(mesh_size)} mm（弦向/展向同值）。")

STYLE_CYCLE = ['描述', '任务单', '图纸']

def main():
    import argparse
    ap = argparse.ArgumentParser()
    # W5b-2 前置（专家第六轮 §5.2 任务 9）：名额可配，才能扩卷到「全 55 条 L3」。
    # 默认值 = 现役 30 条口径，**必须与已冻结的 tasks/nl_human.jsonl 逐字节一致**
    # （验收：--out 到临时路径后 diff，见 W5B_PLAN.md W5b-2）。
    ap.add_argument('--quota', default=None,
                    help='每族名额，如 "wingbox:34,open_hole_panel:11,fuselage_barrel:6,stiffened_panel:4"')
    ap.add_argument('--out', default=None, help='输出路径（默认 tasks/nl_human.jsonl）')
    ap.add_argument('--interp-quota', default=None,
                    help='内插留出名额（W5b/RUBRIC §1.1），如 "wingbox:2,open_hole_panel:2,'
                         'fuselage_barrel:1,stiffened_panel:1"；从 train 里按 task_id 字典序确定性取')
    args = ap.parse_args()

    def parse_q(s):
        d = {}
        for kv in s.split(','):
            k, _, v = kv.partition(':')
            d[k.strip()] = int(v)
        return d

    tasks = [json.loads(ln) for ln in open(TASKS, encoding='utf-8') if ln.strip()]
    l1 = [t for t in tasks if t['input_level'] == 'L1']
    by_fam = {}
    for t in l1:
        by_fam.setdefault(t['family'], []).append(t)

    # 名额：wingbox 15 / open_hole 6 / fuselage_barrel 5 / stiffened_panel 4 = 30
    quota = {'wingbox': 15, 'open_hole_panel': 6, 'fuselage_barrel': 5, 'stiffened_panel': 4}
    if args.quota:
        quota = parse_q(args.quota)

    # W5b（RUBRIC §1.1，老王 2026-10-25 拍板）：内插留出——从各族 train 里确定性取前 N 条，
    # 标 exam_stratum='interpolation'。它**不改 dataset 的 split_v2**（D12 冻结不破），
    # 只在任务层加难度分层；scoring 的 is_exam 认这个字段。
    interp_pick = set()
    if args.interp_quota:
        iq = parse_q(args.interp_quota)
        for fam_, n_i in iq.items():
            train_cases = sorted([t for t in by_fam.get(fam_, []) if t['split_v2'] == 'train'],
                                 key=lambda t: t['task_id'])
            if len(train_cases) < n_i:
                raise SystemExit(f'内插名额不足：{fam_} 只有 {len(train_cases)} 条 train，要 {n_i} 条')
            interp_pick |= {t['task_id'][3:] for t in train_cases[:n_i]}
        print(f'[interp] 内插留出 {len(interp_pick)} 条：{sorted(interp_pick)}')
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
        # W5a（专家第五轮 P0-1 顺带实锤）：panel 素板（n_stringers=0）NL 写「无长桁」信息完备，
        # 登记 ec=['n_stringers'] 是伪缺题——v4 考卷模型如实填 0 被误判「编造」（C-021 FPR 成分）。
        # 澄清名额给 n_stringers>0 的案（挖「N 根」→「若干根」才是真缺）。
        if fam == 'stiffened_panel':
            picked = sorted(picked, key=lambda t: -int(t['input']['spec_normalized']['structure']['params'].get('n_stringers', 0)))
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
                    txt = txt.replace(f"{int(norm['structure']['params']['n_frames'])} 个普通框（blade 剖面）",
                                      "若干个普通框（blade 剖面）")
            else:
                ms = float(norm.get('mesh', {}).get('size_chord', 3.0))
                txt = sp_text(norm['structure']['params'], STYLE_CYCLE[i % 3], mesh_size=ms)
                if omit == 'n_stringers':
                    # W5a：替换串从 gold 实读（旧版硬编码「3 根」对 ns≠3 的案会静默失配）
                    old = f"{int(norm['structure']['params']['n_stringers'])} 根 blade 长桁等距（高 20 mm、厚 2.5 mm）。"
                    assert old in txt, f'panel omit 替换失配: {t["task_id"]}'
                    txt = txt.replace(old, "若干根长桁。")
            row = {
                'task_id': f"L3_{t['task_id'][3:]}",
                'family': fam_, 'input_level': 'L3', 'input_source': 'human',
                'input': {'nl': txt},
                'truth_ref': t['truth_ref'], 'gates': t['gates'],
                'split_v2': t['split_v2'], 'split_reason': t['split_reason'] + ' | L3 人工 NL',
                'geometry_class': t['geometry_class'],
                # W5b（RUBRIC §1.1）：难度分层——boundary/extrapolation 来自 dataset split，
                # interpolation 是任务层内插留出（split_v2 仍为 train，不破 D12）
                'exam_stratum': ('boundary' if t['split_v2'] == 'boundary_holdout' else
                                 'extrapolation' if t['split_v2'] == 'extrapolation_test' else
                                 'interpolation' if t['task_id'][3:] in interp_pick else None),
                # W5a（R21）：坐标系约定随任务落盘——载荷方向属任务输入，不属于隐藏约定
                'coordinate_convention': {
                    'wingbox': 'x=弦向, y=弯曲方向(翼型法向), z=展向; 翼尖载荷 [0,1,0] (+y)',
                    'open_hole_panel': 'x=板长(拉伸方向), y=板宽, z=板面法向; 拉伸载荷 [1,0,0] (+x)',
                    'fuselage_barrel': 'z=壳轴, x=水平横向(端剪沿+x), y=竖直(端弯绕y); 内压沿壁面内法向',
                    'stiffened_panel': 'x/y=板面内, z=板面法向; 面压 [0,0,-1] (-z 压向板面)',
                }[fam_],
            }
            if omit:
                row['expected_clarifications'] = [omit]
                # W4e（专家第四轮 P0-5/R17）：字段级澄清判据——别名表含正确键名+语义短语；
                # wrong_keys = 其他族的同义键名（键名即契约 R19，问错族键 = FAIL）。
                # 旧版单字关键词（'肋'/'孔'/'框'/'长桁'）可被任何顺带提及命中，废弃。
                row['clarify_aliases'] = {
                    'n_ribs': ['n_ribs', '翼肋', '肋数', '多少道肋', '几道翼肋', '肋的数量'],
                    'hole_d': ['hole_d', '孔径', '孔的直径', '开孔直径', '孔直径', '孔洞直径'],
                    'n_frames': ['n_frames', '框数', '普通框', '多少个框', '几个框', '框的数量'],
                    'n_stringers': ['n_stringers', '长桁根数', '多少根长桁', '几根长桁',
                                    '长桁数量', '长桁数目', '筋的数量'],
                }[omit]
                row['clarify_wrong_keys'] = {
                    'n_ribs': ['n_stringers_per_skin'],
                    'hole_d': [],
                    'n_frames': ['n_stringers_per_skin'],
                    'n_stringers': ['n_stringers_per_skin', '每侧蒙皮'],
                }[omit]
                row['gates'] = ['clarify_then_' + g if g == 'semantics' else g for g in t['gates']]
            out.append(row)

    path = args.out or os.path.join(HERE, 'tasks', 'nl_human.jsonl')
    os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
    # 内插名额必须真的落进考卷（否则「留出」是空的，评分时静默少 6 条）
    produced = {r['task_id'][3:] for r in out}
    lost = interp_pick - produced
    assert not lost, f'内插名额未落进考卷（名额大于该族 quota？）：{sorted(lost)}'
    with open(path, 'w', encoding='utf-8') as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    n_l2c = sum(1 for r in out if 'expected_clarifications' in r)
    n_i = sum(1 for r in out if r.get('exam_stratum') == 'interpolation')
    print(f"[OK] {path}（{len(out)} 行，clarify {n_l2c} 条，interp 留出 {n_i} 条）")
    for r in out[:3]:
        print(' ', r['task_id'], r['input']['nl'][:60], '...')

if __name__ == '__main__':
    main()
