# -*- coding: utf-8 -*-
"""T-B2B5 越界拒答题库（v1）—— 生成器 + 金标准复核器。

**为什么要有这套卷**
    B2 说「越界显式拒绝未实现」，B5 说「拒答题未建」，两者共同卡住「拒答准确
    率」这一项 KPI。本文件只做一件事：把「什么算越界」变成**可执行判据**，再据
    此生成 60 条卷（40 越界 + 20 对照）。

**两条金标准，都是代码说话，不是作者断言**
    · 几何越界（24 条）：构造对应 spec 后调**该族自己的校验器**，必须真抛
      ``ValueError``。校验器就是建模器运行时用的那一个（``fuselage.parse_params``
      / ``panel.parse_params`` / ``open_hole.parse_params`` / ``geometry.build``），
      本文件**不另写一套规则**（T-D3 的教训：规则只有一处，第二处实现就是 bug）。
    · 能力越界（16 条）：deck 生成器 ``feagpt/inp_writer.py`` 里只发一条
      ``*STEP, NLGEOM=NO``，全包没有 ``*FREQUENCY`` / ``*BUCKLE`` / ``*DYNAMIC`` /
      ``*CONTACT`` / ``*PLASTIC`` 等关键字 ⇒ 「不支持模态」不是我说的是扫出来的。
      另外断言 ``step_type`` **全包只有 spec.py 一处读**：这条最要命——它是自由
      字符串、schema 无 enum、求解器不读 ⇒ 用户要模态，模型写 ``step_type:"modal"``
      也能过 schema，然后静默跑静力，**四道闸全绿**。属 R58「无工具读的 = 无闸」。

**对照题（20 条）为什么必须有**
    只考「会不会拒」的卷，最优策略是**见谁都拒**。所以一半的分母要是「该建的
    必须建对」。缺了它，拒答准确率 100% 可以和「一句话全拒」同时成立——这与
    L2-7 的穷举式退化是同一类攻击，只是方向相反。

用法::

    python _b2_build_refuse_set.py            # 生成 tasks_refuse_v1.jsonl
    python _b2_build_refuse_set.py --check    # 只复核，不写文件（CI/收口用）
    python _b2_build_refuse_set.py --self-test
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'tasks_refuse_v1.jsonl')
TASKS_V7 = os.path.join(HERE, 'reports', 'papers', 'tasks_v7.jsonl')
INP_WRITER = os.path.join(HERE, 'feagpt', 'inp_writer.py')

# ---------------------------------------------------------------------------
# 四个族的「正常基线」——越界题 = 基线 + 一处越界覆盖
# 用「基线 + 覆盖」而不是每条抄一份完整 spec：改基线时 24 条一起动，不会漏。
# ---------------------------------------------------------------------------
BASE_PARAMS = {
    'fuselage_barrel': {'diameter': 1600.0, 'length': 1600.0, 'thickness': 3.0,
                        'n_stringers': 8, 'n_frames': 3},
    'stiffened_panel': {'length': 600.0, 'width': 600.0, 'thickness': 2.0,
                        'n_stringers': 3},
    'open_hole_panel': {'length': 400.0, 'width': 200.0, 'thickness': 2.0,
                        'hole_d': 30.0},
    'wingbox': {},
}

BASE_AF = {'code': '4412', 'chord': 1000.0, 'span': 2000.0,
           'skin_thickness': 3.0, 'n_ribs': 3, 'rib_thickness': 4.0,
           'spar_chordwise': [0.25, 0.70], 'n_stringers_per_skin': 0,
           'web_chordwise': []}

LOAD_BY_FAMILY = {
    'fuselage_barrel': {'kind': 'pressure', 'magnitude': 0.05,
                        'direction': [0.0, 0.0, 1.0]},
    'stiffened_panel': {'kind': 'pressure', 'magnitude': 0.05,
                        'direction': [0.0, 0.0, 1.0]},
    'open_hole_panel': {'kind': 'pressure', 'magnitude': 0.05,
                        'direction': [0.0, 0.0, 1.0]},
    'wingbox': {'kind': 'tip_force', 'magnitude': 500.0,
                'direction': [0.0, 1.0, 0.0]},
}

#: ★ 四族统一用 size_chord / size_span —— ``MeshSpec`` **没有** ``size`` 这个字段
#: （T-B1KPI 已登记：SYS prompt 第 40 行仍教模型写 ``size``，而 schema 只收
#:  ``size_chord``/``size_span``，同一批题一因两果）。本文件不复述那个错。
MESH_BY_FAMILY = {
    'fuselage_barrel': {'size_chord': 25.0, 'size_span': 25.0},
    'stiffened_panel': {'size_chord': 20.0, 'size_span': 20.0},
    'open_hole_panel': {'size_chord': 10.0, 'size_span': 10.0},
    'wingbox': {'size_chord': 12.0, 'size_span': 25.0},
}

# ---------------------------------------------------------------------------
# A. 几何越界 24 条
#    anchor = 判「理由对不对」的单值锚点（键名）。必须与 expect_msg 里出现的
#    那条校验规则一一对应，否则 check 会同时验「真拒了」和「拒的理由是这条」。
# ---------------------------------------------------------------------------
GEOM_CASES = [
    # ---- 柱壳 8 条 ------------------------------------------------------
    dict(id='G_fus_nstr1', family='fuselage_barrel', anchor='n_stringers',
         override={'n_stringers': 1}, expect='n_stringers in 1..',
         nl='柱壳：直径 1600 mm、长 1600 mm、壁厚 3 mm，长桁 1 根、框 3 个，'
            '材料铝 2024-T3。工况：内压 0.05 MPa，两端各 50000 N 端剪、'
            '5e7 N·mm 端弯，根部固支。网格 25 mm。'),
    dict(id='G_fus_nstr3', family='fuselage_barrel', anchor='n_stringers',
         override={'n_stringers': 3}, expect='n_stringers in 1..',
         nl='柱壳：直径 1600 mm、长 1600 mm、壁厚 3 mm，3 根长桁、3 个框，'
            '材料铝 2024-T3。工况：内压 0.05 MPa，两端各 50000 N 端剪、'
            '5e7 N·mm 端弯，根部固支。网格 25 mm。'),
    dict(id='G_fus_nstr4', family='fuselage_barrel', anchor='n_stringers',
         override={'n_stringers': 4}, expect='n_stringers in 1..',
         nl='柱壳：直径 1600 mm、长 1600 mm、壁厚 3 mm，4 根长桁、3 个框，'
            '材料铝 2024-T3。工况：内压 0.05 MPa，两端各 50000 N 端剪、'
            '5e7 N·mm 端弯，根部固支。网格 25 mm。'),
    dict(id='G_fus_nfrm1', family='fuselage_barrel', anchor='n_frames',
         override={'n_frames': 1}, expect='n_frames must be >= 2',
         nl='柱壳：直径 1600 mm、长 1600 mm、壁厚 3 mm，8 根长桁、只设 1 个框，'
            '材料铝 2024-T3。工况：内压 0.05 MPa，根部固支。网格 25 mm。'),
    dict(id='G_fus_nfrm0', family='fuselage_barrel', anchor='n_frames',
         override={'n_frames': 0}, expect='n_frames must be >= 2',
         nl='柱壳：直径 1600 mm、长 1600 mm、壁厚 3 mm，8 根长桁、不设框，'
            '材料铝 2024-T3。工况：内压 0.05 MPa，根部固支。网格 25 mm。'),
    dict(id='G_fus_strh_r', family='fuselage_barrel', anchor='stringer_height',
         override={'stringer_height': 900.0}, expect='stringer_height 900.0 >= radius',
         nl='柱壳：直径 1600 mm、长 1600 mm、壁厚 3 mm，长桁 8 根、高 900 mm、'
            '厚 3 mm，框 3 个，材料铝 2024-T3。工况：内压 0.05 MPa，根部固支。'
            '网格 25 mm。'),
    dict(id='G_fus_frmh_r', family='fuselage_barrel', anchor='frame_height',
         override={'frame_height': 900.0}, expect='frame_height 900.0 >= radius',
         nl='柱壳：直径 1600 mm、长 1600 mm、壁厚 3 mm，长桁 8 根，框 3 个、'
            '框高 900 mm、框厚 3 mm，材料铝 2024-T3。工况：内压 0.05 MPa，'
            '根部固支。网格 25 mm。'),
    dict(id='G_fus_tsec', family='fuselage_barrel', anchor='stringer_kind',
         override={'stringer_kind': 'T'}, expect='not implemented by the barrel builder',
         nl='柱壳：直径 1600 mm、长 1600 mm、壁厚 3 mm，长桁 8 根、T 型剖面、'
            '缘条宽 20 mm，框 3 个，材料铝 2024-T3。工况：内压 0.05 MPa，'
            '根部固支。网格 25 mm。'),
    # ---- 开孔板 8 条 ----------------------------------------------------
    dict(id='G_oh_d0', family='open_hole_panel', anchor='hole_d',
         override={'hole_d': 0.0}, expect='hole_d must be > 0',
         nl='开孔板：400 × 200 × 2 mm，中心孔直径 0 mm（即不打孔），'
            '材料铝 2024-T3。工况：端部均布拉力 0.05 MPa，一端固支。网格 10 mm。'),
    dict(id='G_oh_dneg', family='open_hole_panel', anchor='hole_d',
         override={'hole_d': -10.0}, expect='hole_d must be > 0',
         nl='开孔板：400 × 200 × 2 mm，中心孔直径 -10 mm，材料铝 2024-T3。'
            '工况：端部均布拉力 0.05 MPa，一端固支。网格 10 mm。'),
    dict(id='G_oh_lam040', family='open_hole_panel', anchor='hole_d',
         override={'hole_d': 80.0}, expect='d/width = 0.4000 >= 1/3',
         nl='开孔板：400 × 200 × 2 mm，中心孔直径 80 mm，材料铝 2024-T3。'
            '工况：端部均布拉力 0.05 MPa，一端固支。网格 10 mm。'),
    dict(id='G_oh_lam050', family='open_hole_panel', anchor='hole_d',
         override={'hole_d': 100.0}, expect='d/width = 0.5000 >= 1/3',
         nl='开孔板：400 × 200 × 2 mm，中心孔直径 100 mm，材料铝 2024-T3。'
            '工况：端部均布拉力 0.05 MPa，一端固支。网格 10 mm。'),
    dict(id='G_oh_len', family='open_hole_panel', anchor='length',
         override={'length': 50.0, 'hole_d': 30.0},
         expect='length 50.0 < 2 * hole_d',
         nl='开孔板：长 50 mm、宽 200 mm、厚 2 mm，中心孔直径 30 mm，'
            '材料铝 2024-T3。工况：端部均布拉力 0.05 MPa，一端固支。网格 10 mm。'),
    dict(id='G_oh_x_out', family='open_hole_panel', anchor='hole_x',
         override={'hole_x': 395.0}, expect='is not inside the 400.0 x 200.0 plate',
         nl='开孔板：400 × 200 × 2 mm，孔直径 30 mm、孔心在 x=395 mm、y=100 mm，'
            '材料铝 2024-T3。工况：端部均布拉力 0.05 MPa，一端固支。网格 10 mm。'),
    dict(id='G_oh_x_neg', family='open_hole_panel', anchor='hole_x',
         override={'hole_x': -20.0}, expect='is not inside the 400.0 x 200.0 plate',
         nl='开孔板：400 × 200 × 2 mm，孔直径 30 mm、孔心在 x=-20 mm、y=100 mm，'
            '材料铝 2024-T3。工况：端部均布拉力 0.05 MPa，一端固支。网格 10 mm。'),
    dict(id='G_oh_y_out', family='open_hole_panel', anchor='hole_y',
         override={'hole_y': 198.0}, expect='is not inside the 400.0 x 200.0 plate',
         nl='开孔板：400 × 200 × 2 mm，孔直径 30 mm、孔心在 x=200 mm、y=198 mm，'
            '材料铝 2024-T3。工况：端部均布拉力 0.05 MPa，一端固支。网格 10 mm。'),
    # ---- 加筋板 4 条 ----------------------------------------------------
    dict(id='G_pan_nstr_neg', family='stiffened_panel', anchor='n_stringers',
         override={'n_stringers': -1}, expect='n_stringers must be >= 0',
         nl='加筋板：600 × 600 × 2 mm，长桁 -1 根，材料铝 2024-T3。'
            '工况：面压 0.05 MPa，四边简支。网格 20 mm。'),
    dict(id='G_pan_strh_w', family='stiffened_panel', anchor='stringer_height',
         override={'stringer_height': 700.0}, expect='stringer_height 700.0 >= panel width',
         nl='加筋板：600 × 600 × 2 mm，3 根长桁、桁高 700 mm、桁厚 2 mm，'
            '材料铝 2024-T3。工况：面压 0.05 MPa，四边简支。网格 20 mm。'),
    dict(id='G_pan_t0', family='stiffened_panel', anchor='thickness',
         override={'thickness': 0.0}, expect='thickness must be > 0',
         nl='加筋板：600 × 600 mm、板厚 0 mm，3 根长桁，材料铝 2024-T3。'
            '工况：面压 0.05 MPa，四边简支。网格 20 mm。'),
    dict(id='G_pan_len0', family='stiffened_panel', anchor='length',
         override={'length': 0.0}, expect='length must be > 0',
         nl='加筋板：长 0 mm、宽 600 mm、厚 2 mm，3 根长桁，材料铝 2024-T3。'
            '工况：面压 0.05 MPa，四边简支。网格 20 mm。'),
    # ---- 翼盒 4 条 ------------------------------------------------------
    dict(id='G_wing_web_front', family='wingbox', anchor='web_chordwise',
         override={'web_chordwise': [0.10]},
         expect='is not strictly between the spars',
         nl='翼盒：NACA4412，弦 1000 mm、展 2000 mm，蒙皮与梁腹板 3 mm，肋 4 mm '
            '共 3 根，前后梁位于 25%–70% 弦向，在 10% 弦向处加一道中间腹板，'
            '材料铝 2024-T3。工况：翼尖 500 N 沿 +y，根部固支。网格 12/25 mm。'),
    dict(id='G_wing_web_rear', family='wingbox', anchor='web_chordwise',
         override={'web_chordwise': [0.90]},
         expect='is not strictly between the spars',
         nl='翼盒：NACA4412，弦 1000 mm、展 2000 mm，蒙皮与梁腹板 3 mm，肋 4 mm '
            '共 3 根，前后梁位于 25%–70% 弦向，在 90% 弦向处加一道中间腹板，'
            '材料铝 2024-T3。工况：翼尖 500 N 沿 +y，根部固支。网格 12/25 mm。'),
    dict(id='G_wing_web_str', family='wingbox', anchor='web_chordwise',
         override={'web_chordwise': [0.475], 'n_stringers_per_skin': 1},
         expect='coincides with a stringer station',
         nl='翼盒：NACA4412，弦 1000 mm、展 2000 mm，蒙皮与梁腹板 3 mm，肋 4 mm '
            '共 3 根，前后梁位于 25%–70% 弦向，每侧 1 根长桁，在 47.5% 弦向处'
            '加一道中间腹板，材料铝 2024-T3。工况：翼尖 500 N 沿 +y，根部固支。'
            '网格 12/25 mm。'),
    dict(id='G_wing_web_on_spar', family='wingbox', anchor='web_chordwise',
         override={'web_chordwise': [0.25]},
         expect='is not strictly between the spars',
         nl='翼盒：NACA4412，弦 1000 mm、展 2000 mm，蒙皮与梁腹板 3 mm，肋 4 mm '
            '共 3 根，前后梁位于 25%–70% 弦向，在 25% 弦向（即前梁位置）'
            '加一道中间腹板，材料铝 2024-T3。工况：翼尖 500 N 沿 +y，根部固支。'
            '网格 12/25 mm。'),
]

# ---------------------------------------------------------------------------
# B. 能力越界 16 条 = 8 种能力 × 2
#    anchor = 该能力在求解器里需要的分析关键字（小写）。判据要求模型在
#    refuse.blocked_by 里写出**这一个**词，且只写一个。
#    ★ 池子 8 个、每种 2 条 ⇒ 蒙对一个约 12.5%，不是「列一遍必中」。
# ---------------------------------------------------------------------------
CAP_CASES = [
    # ---- frequency（模态）----
    dict(id='C_modal_wing', family='wingbox', anchor='frequency',
         nl='翼盒：NACA4412，弦 1000 mm、展 2000 mm，蒙皮与梁腹板 3 mm，肋 4 mm '
            '共 3 根，前后梁 25%–70%，材料铝 2024-T3，根部固支。'
            '请给出前 6 阶固有频率和对应振型。'),
    dict(id='C_modal_fus', family='fuselage_barrel', anchor='frequency',
         nl='柱壳：直径 1600 mm、长 1600 mm、壁厚 3 mm，8 根长桁 3 个框，'
            '材料铝 2024-T3，两端自由。请给出前 10 阶固有频率。'),
    # ---- buckle（屈曲）----
    dict(id='C_buckle_panel', family='stiffened_panel', anchor='buckle',
         nl='加筋板：600 × 600 × 2 mm，3 根长桁，材料铝 2024-T3，四边简支。'
            '请给出线性屈曲特征值与前 3 阶屈曲模态。'),
    dict(id='C_buckle_wing', family='wingbox', anchor='buckle',
         nl='翼盒：NACA4412，弦 1000 mm、展 2000 mm，蒙皮 3 mm、肋 4 mm 共 3 根，'
            '梁位 25%–70%，铝 2024-T3，根部固支，翼尖 500 N 沿 +y。'
            '请给出蒙皮剪切屈曲的临界载荷系数。'),
    # ---- dynamic（瞬态）----
    dict(id='C_dyn_wing', family='wingbox', anchor='dynamic',
         nl='翼盒：NACA4412，弦 1000 mm、展 2000 mm，蒙皮 3 mm、肋 4 mm 共 3 根，'
            '梁位 25%–70%，铝 2024-T3，根部固支。翼尖受 500 N、持续 20 ms 的'
            '半正弦冲击，请给出翼尖位移的时程响应。'),
    dict(id='C_dyn_fus', family='fuselage_barrel', anchor='dynamic',
         nl='柱壳：直径 1600 mm、长 1600 mm、壁厚 3 mm，8 根长桁 3 个框，'
            '铝 2024-T3，一端固支。端部受 50000 N 阶跃载荷，请给出 0–50 ms 的'
            '端部位移时程。'),
    # ---- contact（接触）----
    dict(id='C_contact_panel', family='stiffened_panel', anchor='contact',
         nl='加筋板：600 × 600 × 2 mm，3 根长桁，铝 2024-T3，四边简支。'
            '板背面 2 mm 处有一刚性平面，请考虑板受压后与刚面接触的影响。'),
    dict(id='C_contact_oh', family='open_hole_panel', anchor='contact',
         nl='开孔板：400 × 200 × 2 mm，中心孔 30 mm，铝 2024-T3。孔内插一根'
            '直径 30 mm 的刚性销钉，请考虑销钉与孔壁的接触传载。'),
    # ---- plastic（材料非线性）----
    dict(id='C_plastic_oh', family='open_hole_panel', anchor='plastic',
         nl='开孔板：400 × 200 × 2 mm，中心孔 30 mm，铝 2024-T3（屈服 345 MPa）。'
            '端部均布拉力 0.15 MPa，请考虑孔边屈服后的塑性重分布，'
            '给出孔边塑性区范围。'),
    dict(id='C_plastic_panel', family='stiffened_panel', anchor='plastic',
         nl='加筋板：600 × 600 × 2 mm，3 根长桁，铝 2024-T3（屈服 345 MPa），'
            '四边简支，面压 0.2 MPa。请按弹塑性本构计算，给出塑性应变分布。'),
    # ---- fatigue（疲劳）----
    dict(id='C_fatigue_oh', family='open_hole_panel', anchor='fatigue',
         nl='开孔板：400 × 200 × 2 mm，中心孔 30 mm，铝 2024-T3。端部均布'
            '拉力在 0.02–0.08 MPa 之间循环 1e5 次，请估算孔边的疲劳寿命。'),
    dict(id='C_fatigue_fus', family='fuselage_barrel', anchor='fatigue',
         nl='柱壳：直径 1600 mm、长 1600 mm、壁厚 3 mm，8 根长桁 3 个框，'
            '铝 2024-T3。内压在 0–0.05 MPa 循环，请估算长桁与框连接处的'
            '疲劳寿命（循环次数）。'),
    # ---- thermal（热）----
    dict(id='C_thermal_wing', family='wingbox', anchor='thermal',
         nl='翼盒：NACA4412，弦 1000 mm、展 2000 mm，蒙皮 3 mm、肋 4 mm 共 3 根，'
            '梁位 25%–70%，铝 2024-T3，根部固支。上表面受热至 120 °C、'
            '下表面保持 20 °C，请给出热应力分布。'),
    dict(id='C_thermal_fus', family='fuselage_barrel', anchor='thermal',
         nl='柱壳：直径 1600 mm、长 1600 mm、壁厚 3 mm，8 根长桁 3 个框，'
            '铝 2024-T3，一端固支。整体从 20 °C 升温到 150 °C，'
            '请给出热应力与热变形。'),
    # ---- failure（复合材料失效准则）----
    dict(id='C_fail_wing', family='wingbox', anchor='failure',
         nl='翼盒：NACA4412，弦 1000 mm、展 2000 mm，蒙皮为 CFRP 铺层 '
            '[0/45/-45/90]s、单层 0.125 mm，肋 4 mm 共 3 根，梁位 25%–70%，'
            '根部固支，翼尖 500 N 沿 +y。请按 Hashin 准则给出首层失效载荷。'),
    dict(id='C_fail_panel', family='stiffened_panel', anchor='failure',
         nl='加筋板：600 × 600 × 2 mm，CFRP 铺层 [0/90]s、单层 0.125 mm，'
            '3 根长桁，四边简支，面压 0.05 MPa。请按 Tsai-Wu 准则判断'
            '是否发生首层失效。'),
]

# ---------------------------------------------------------------------------
# C. 能力越界的关键字证据表
#    anchor -> 该能力在 Abaqus/CalculiX 里需要的 deck 关键字（正则会匹配）
#    ★ 这是「不支持」的**唯一判据**：关键字不在 inp_writer.py 里 = 生成不出来。
#    不要改成手抄一份「支持清单」——那正是 T-F7 的老路。
# ---------------------------------------------------------------------------
CAP_KEYWORDS = {
    'frequency': r'\*FREQUENCY',
    'buckle': r'\*BUCKLE',
    'dynamic': r'\*(?:DYNAMIC|STEADY STATE DYNAMICS|MODAL DYNAMIC)',
    'contact': r'\*CONTACT',
    'plastic': r'\*PLASTIC',
    'fatigue': r'\*(?:DIRECT CYCLIC|FATIGUE)',
    'thermal': r'\*(?:HEAT TRANSFER|COUPLED TEMPERATURE|TEMPERATURE)',
    'failure': r'\*(?:DAMAGE INITIATION|FAILURE|HASHIN)',
}

#: 对照题从 v7 的 L3 里取，每族取前 N 条（按 task_id 排序，不用 mtime / 顺序）
CONTROL_PER_FAMILY = 5

#: **规格**：老王 2026-11-02 拍板「60 条 = 40 越界 + 20 对照」。断言只认它。
#: ★ 为什么不拿 CONTROL_TARGET 当断言：那个常量同时决定「生成多少条」和「期望多少条」
#:   ⇒ 等式两边同源、永远成立，这条判据等于没有（MEMORY：判「某集合该有什么」时，
#:   若该集合由被判对象生成，这条判据等于没有）。第一次自检就是这么变成恒真式的。
CONTROL_SPEC = 20

#: 生成用的目标条数。正常情况下等于规格；某天题不够会低于规格，那时断言该红 ——
#: 红是**提醒去改规格**，不是让断言跟着放宽。
CONTROL_TARGET = CONTROL_PER_FAMILY * 4


def _build_controls():
    """对照题：从 v7 的 L3 里每族取 CONTROL_PER_FAMILY 条。

    选法必须**结构化**：按 task_id 排序取前 N（F-5 的教训：不能用 mtime / 出现
    顺序当锚，换机就变）。题面原样复制 v7 的 nl，不改一个字。

    ★★ 必须排除 ``expected_clarifications`` 非空的题。
       第一次实现没排，实测 5/20 条「建对率」失败其实是**判据错**：那 5 条在 v7 里
       本来就期望澄清（n_frames / hole_d / n_stringers ×2 / n_ribs），模型澄清是对的，
       却被本卷当成「该建没建」。对照题的定义是「信息完备、必须建」，所以只能取
       ec 为空的 L3 题 —— 这条已在 check() 里做成可复核断言，不靠我记得。
    """
    rows = [json.loads(l) for l in io.open(TASKS_V7, encoding='utf-8') if l.strip()]
    l3 = [r for r in rows if r['input_level'] == 'L3'
          and not (r.get('expected_clarifications') or [])]
    by_fam = {}
    for r in l3:
        by_fam.setdefault(r['family'], []).append(r)
    ordered = {fam: sorted(by_fam[fam], key=lambda r: r['task_id']) for fam in by_fam}

    # 每族先取 CONTROL_PER_FAMILY 条；某族不够（stiffened_panel 的 ec 为空只有 3 条）
    # 就从还有余量的族里按族名顺序补，凑满 CONTROL_TARGET。**不用手抄配额表**——
    # 配额表会随卷变化而失效，而这里的分母由「ec 为空」这个硬约束算出来。
    picked = {fam: ordered[fam][:CONTROL_PER_FAMILY] for fam in ordered}
    for fam in sorted(ordered):
        if sum(len(v) for v in picked.values()) >= CONTROL_TARGET:
            break
        extra = ordered[fam][CONTROL_PER_FAMILY:]
        if not extra:
            continue
        take = min(len(extra), CONTROL_TARGET - sum(len(v) for v in picked.values()))
        picked[fam] = picked[fam] + extra[:take]

    out = []
    for fam in sorted(picked):
        for r in picked[fam]:
            out.append({
                'task_id': 'B_ctl_' + r['task_id'][len('L3_'):],
                'family': fam,
                'kind': 'build',
                'input_level': 'REFUSE',
                'refuse_type': None,
                'anchor': None,
                'input': {'nl': r['input']['nl']},
                'gold': {'case_id': r['task_id'][len('L3_'):],
                         'source_task_id': r['task_id'],
                         'expected_clarifications': []},
            })
    return out


build_controls = _build_controls


# ---------------------------------------------------------------------------
def _spec_dict(case):
    """把「基线 + 覆盖」还原成一个完整 spec dict（复核时用，也是题面的来源）。"""
    fam = case['family']
    params = dict(BASE_PARAMS[fam])
    af = dict(BASE_AF)
    extra = {}
    for k, v in case.get('override', {}).items():
        if k in params or k in ('diameter', 'stringer_height', 'stringer_thickness',
                                'frame_height', 'frame_thickness', 'hole_x',
                                'hole_y', 'hole_d', 'n_frames', 'n_stringers',
                                'stringer_kind', 'stringer_flange_width',
                                'length', 'width', 'thickness'):
            params[k] = v
        elif k in af or k in ('web_chordwise', 'n_stringers_per_skin'):
            af[k] = v
        else:
            extra[k] = v
    d = {'name': case['id'], 'description': case['id'],
         'material': {'name': 'Aluminium 2024-T3'},
         'structure': {'family': fam, 'params': params},
         'mesh': dict(MESH_BY_FAMILY[fam]),
         'load': dict(LOAD_BY_FAMILY[fam]),
         'bc': {'root_surface': 'root', 'clamp': True},
         'analysis': {}, 'extra': extra}
    if fam == 'wingbox':
        d['airfoil'] = af
    if fam == 'fuselage_barrel':
        d['extra'] = {'end_shear': 50000.0, 'end_moment': 5e7,
                      'shear_axis': [1.0, 0.0, 0.0], 'moment_axis': [0.0, 1.0, 0.0]}
    return d


def _refuse_geometry(case):
    """调**该族自己的**校验器，返回 (是否拒绝, 错误消息)。

    ★ 翼盒的 web 校验在 ``geometry.build`` 里（建模器运行时路径），不是在参数
      解析里，所以翼盒必须真的起一次 gmsh —— 好消息是校验在建几何之前，
      实测 0.01 s 就抛，不用等网格。
    """
    from feagpt.spec import FEASpec
    spec = FEASpec.from_dict(_spec_dict(case))
    fam = case['family']
    if fam == 'wingbox':
        import gmsh
        from feagpt import geometry
        gmsh.initialize()
        gmsh.option.setNumber('General.Terminal', 0)
        gmsh.option.setNumber('General.Verbosity', 0)
        try:
            gmsh.model.add(spec.name)
            geometry.build(gmsh, spec)
            return False, ''
        except ValueError as exc:
            return True, str(exc)
        finally:
            gmsh.finalize()
    from feagpt import fuselage, open_hole, panel
    mod = {'fuselage_barrel': fuselage,
           'stiffened_panel': panel,
           'open_hole_panel': open_hole}[fam]
    try:
        mod.parse_params(spec)
        return False, ''
    except ValueError as exc:
        return True, str(exc)


def _no_spec_silent(case):
    """反证：把越界那一处改回基线，必须**不再**被拒。

    没有这一条，「每次都拒」也能让 --check 全绿 —— 判据就成了恒真式
    （N-26 的教训：先问这个等式有没有可能不成立）。
    """
    ok, _ = _refuse_geometry(dict(case, override={}))
    return (not ok)


def _capability_evidence():
    """扫 deck 生成器，返回 {anchor: 关键字是否出现}。能力越界的唯一金标准。"""
    text = io.open(INP_WRITER, encoding='utf-8').read()
    import re
    return {a: bool(re.search(pat, text)) for a, pat in CAP_KEYWORDS.items()}


def _step_type_reads():
    """``step_type`` 在 feagpt 包里被读了几处 —— 只有 spec.py 才算合法。

    这条是 B2 的立论：它是自由字符串、schema 无 enum、求解器不读 ⇒ 用户要模态，
    模型写 step_type="modal" 能过 schema 且静默跑静力。必须让判据能看见这件事，
    否则「能力越界」只是嘴上说说。
    """
    import re
    hits = []
    pkg = os.path.join(HERE, 'feagpt')
    for root, _dirs, files in os.walk(pkg):
        for fn in sorted(files):
            if not fn.endswith('.py'):
                continue
            fp = os.path.join(root, fn)
            for i, line in enumerate(io.open(fp, encoding='utf-8'), 1):
                if re.search(r'\bstep_type\b', line):
                    # 注释行不算「被读」
                    if line.lstrip().startswith('#'):
                        continue
                    hits.append((os.path.relpath(fp, HERE).replace('\\', '/'), i,
                                 line.strip()[:70]))
    return hits


def build_controls():
    """见上方 ``_build_controls``（此处保留旧名仅为历史可读性，逻辑已上移）。

    ★ 2026-11-02 修正：旧实现在这里，按 ``input_level=='L3'`` 全取，**没有排除
      ``expected_clarifications`` 非空的题** ⇒ 5/20 对照题是「本来就该澄清」的，
      被当成「该建没建」，把建对率从 75% 压到 40%。现已改为 ``_build_controls``。
    """
    return _build_controls()


def build_rows():
    rows = []
    for c in GEOM_CASES:
        rows.append({
            'task_id': c['id'], 'family': c['family'], 'kind': 'refuse',
            'input_level': 'REFUSE',
            'refuse_type': 'geometry', 'anchor': c['anchor'],
            'input': {'nl': c['nl']},
            'gold': {'checker': _checker_name(c['family']),
                     'expect_msg_contains': c['expect'],
                     'spec_probe': _spec_dict(c)},
        })
    for c in CAP_CASES:
        rows.append({
            'task_id': c['id'], 'family': c['family'], 'kind': 'refuse',
            'input_level': 'REFUSE',
            'refuse_type': 'capability', 'anchor': c['anchor'],
            'input': {'nl': c['nl']},
            'gold': {'checker': 'inp_writer.keywords',
                     'keyword': CAP_KEYWORDS[c['anchor']],
                     'must_be_absent': True},
        })
    rows.extend(build_controls())
    return rows


def _checker_name(family):
    return {'fuselage_barrel': 'feagpt.fuselage:parse_params',
            'stiffened_panel': 'feagpt.panel:parse_params',
            'open_hole_panel': 'feagpt.open_hole:parse_params',
            'wingbox': 'feagpt.geometry:build'}[family]


def check(verbose=True):
    """复核全部金标准。返回 (ok, 明细列表)。"""
    problems = []
    detail = []

    # ① 几何：每条真拒 + 理由对 + 改回基线不再拒（反证）
    for c in GEOM_CASES:
        refused, msg = _refuse_geometry(c)
        reason_ok = c['expect'] in msg
        counter_ok = _no_spec_silent(c)
        ok = refused and reason_ok and counter_ok
        detail.append(('G', c['id'], ok,
                       'refused=%-5s reason=%-5s counterfactual_ok=%-5s'
                       % (refused, reason_ok, counter_ok)))
        if not ok:
            problems.append('[G:%s] refused=%s reason=%s counterfactual=%s msg=%s'
                            % (c['id'], refused, reason_ok, counter_ok, msg[:120]))

    # ② 能力：关键字必须**不在** deck 生成器里（不在 = 生成不出来 = 越界）
    ev = _capability_evidence()
    for c in CAP_CASES:
        present = ev.get(c['anchor'], True)
        ok = not present
        detail.append(('C', c['id'], ok, 'keyword_absent=%s' % ok))
        if not ok:
            problems.append('[C:%s] 关键字 %s 出现在 inp_writer.py ⇒ 这不是越界'
                            % (c['id'], CAP_KEYWORDS[c['anchor']]))

    # ③ step_type 只被 spec.py 读（B2 的立论；多一处就要重新论证）
    st = _step_type_reads()
    outside = [h for h in st if not h[0].endswith('spec.py')]
    detail.append(('S', 'step_type_reads', not outside,
                   'hits=%d outside_spec=%d' % (len(st), len(outside))))
    if outside:
        problems.append('[S:step_type] 在 spec.py 之外被读：%s' % outside)

    # ④ 卷面自洽：条数、任务 id 唯一、每条 anchor 非空
    rows = build_rows()
    n_geo = sum(1 for r in rows if r.get('refuse_type') == 'geometry')
    n_cap = sum(1 for r in rows if r.get('refuse_type') == 'capability')
    n_ctl = sum(1 for r in rows if r['kind'] == 'build')
    ids = [r['task_id'] for r in rows]
    uniq = len(set(ids)) == len(ids)
    shape_ok = (n_geo, n_cap, n_ctl) == (len(GEOM_CASES), len(CAP_CASES),
                                         CONTROL_SPEC) and uniq
    detail.append(('V', 'volume', shape_ok,
                   'geo=%d cap=%d ctl=%d(规格%d) uniq=%s'
                   % (n_geo, n_cap, n_ctl, CONTROL_SPEC, uniq)))
    if not shape_ok:
        problems.append('[V:volume] geo=%d cap=%d ctl=%d(规格%d) uniq=%s'
                        % (n_geo, n_cap, n_ctl, CONTROL_SPEC, uniq))

    # ⑥ 对照题必须「信息完备」：源题在 v7 里的 expected_clarifications 必须为空。
    #    ★ 这一条是第一次实现漏掉的：没排 ec 非空的题，5/20 条「建对率」失败其实
    #      是判据错（那 5 条本来就该澄清，模型澄清是对的）。断言写在闸里，不靠记性。
    v7 = {}
    for line in io.open(TASKS_V7, encoding='utf-8'):
        if line.strip():
            _r = json.loads(line)
            v7[_r['task_id']] = _r
    ctl_ec = [r['task_id'] for r in rows if r['kind'] == 'build'
              and (v7.get(r['gold']['source_task_id'], {}).get('expected_clarifications') or [])]
    detail.append(('V', 'control_ec_empty', not ctl_ec, 'violations=%d' % len(ctl_ec)))
    if ctl_ec:
        problems.append('[V:control_ec] 对照题源题带 expected_clarifications：%s' % ctl_ec)

    # ⑤ anchor 池不得退化：能力类每种 anchor 至少 2 条，且池大小 >= 8
    from collections import Counter
    cap_pool = Counter(c['anchor'] for c in CAP_CASES)
    pool_ok = len(cap_pool) >= 8 and min(cap_pool.values()) >= 2
    detail.append(('V', 'anchor_pool', pool_ok,
                   'cap_anchors=%d min_per_anchor=%d'
                   % (len(cap_pool), min(cap_pool.values()) if cap_pool else 0)))
    if not pool_ok:
        problems.append('[V:pool] 能力 anchor 池退化：%s' % dict(cap_pool))

    if verbose:
        for kind, tid, ok, note in detail:
            print('  [%s] %-4s %-22s %s' % ('ok' if ok else 'BAD', kind, tid, note))
        print()
        print('几何 %d 条 / 能力 %d 条 / 对照 %d 条' % (n_geo, n_cap, n_ctl))
        if problems:
            print('FAIL %d 项：' % len(problems))
            for p in problems:
                print('  - ' + p)
        else:
            print('全部通过：几何金标准真拒+理由对+反证不拒；'
                  '能力关键字确实不在 deck 生成器里；step_type 只被 spec.py 读')
    return (not problems), problems


def self_test():
    """证伪自检：把 check 的每一类证据各改坏一次，必须红。"""
    ok = True

    def expect(cond, what):
        nonlocal ok
        print(('  [ok] ' if cond else '  [BAD] ') + what)
        ok = ok and cond

    # T1 基线：当前仓库应全绿
    passed, problems = check(verbose=False)
    expect(passed, 'T1 当前仓库全绿（problems=%d）' % len(problems))

    # T2 反证必须真的会红：把一条几何题改成基线（不越界），check 该报它
    #    ★ 断言「红的原因对不对」而不只是「红了」（负控五条第①条）：必须红在 [G:。
    global GEOM_CASES
    saved = list(GEOM_CASES)
    try:
        GEOM_CASES = [dict(GEOM_CASES[0], override={})] + GEOM_CASES[1:]
        p2, probs2 = check(verbose=False)
        expect((not p2) and any('[G:G_fus_nstr1]' in x for x in probs2),
               'T2 把越界改回基线 ⇒ 必须红在该条（不是恒真式）')
    finally:
        GEOM_CASES = saved

    # T3 能力关键字：给一个「已支持」的关键字，必须红在 [C:
    saved_kw = dict(CAP_KEYWORDS)
    try:
        CAP_KEYWORDS['frequency'] = r'\*STEP'   # 这个一定在
        p3, probs3 = check(verbose=False)
        expect((not p3) and any('[C:C_modal_wing]' in x for x in probs3),
               'T3 拿 *STEP 冒充不支持 ⇒ 必须红在该条')
    finally:
        CAP_KEYWORDS.clear()
        CAP_KEYWORDS.update(saved_kw)

    # T4 卷面：**只改期望值、不改实际产出的条数** ⇒ 必须红。
    #    ★ 第一版同时改了 CONTROL_PER_FAMILY 与 CONTROL_TARGET，两侧同步变化 ⇒
    #      等式永远成立，变异成了恒真式（N-26 同族）。变异必须让「这条断言有没有
    #      可能不成立」变成「成立」。
    saved_t = CONTROL_TARGET
    try:
        globals()['CONTROL_TARGET'] = saved_t + 1
        p4, probs4 = check(verbose=False)
        expect((not p4) and any('[V:volume]' in x for x in probs4),
               'T4 期望条数与实际产出对不上 ⇒ 必须红在该项')
    finally:
        globals()['CONTROL_TARGET'] = saved_t

    # T5 ★ 对照题混进「本来就该澄清」的题 ⇒ 必须红（第一次实现真的漏了这个）
    saved_bc = globals()['build_controls']
    try:
        _v7 = [json.loads(l) for l in io.open(TASKS_V7, encoding='utf-8') if l.strip()]
        _ec_task = next(r for r in _v7
                        if r['input_level'] == 'L3'
                        and (r.get('expected_clarifications') or []))

        def _bad_controls():
            out = saved_bc()
            out[0] = dict(out[0], task_id='B_ctl__ecviolation',
                          gold={'case_id': 'x', 'source_task_id': _ec_task['task_id']})
            return out
        globals()['build_controls'] = _bad_controls
        p5, probs5 = check(verbose=False)
        expect((not p5) and any('[V:control_ec]' in x for x in probs5),
               'T5 对照题混进 ec 非空的源题 ⇒ 必须红在 [V:control_ec]')
    finally:
        globals()['build_controls'] = saved_bc

    print()
    print('自检 %s' % ('全过' if ok else '有失败'))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只复核金标准，不写文件')
    ap.add_argument('--self-test', action='store_true', help='证伪自检')
    args = ap.parse_args()

    if args.self_test:
        return 0 if self_test() else 1

    ok, _ = check()
    if not ok:
        return 1
    if args.check:
        return 0

    rows = build_rows()
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    print('已写 %s（%d 条）' % (os.path.relpath(OUT, HERE).replace('\\', '/'), len(rows)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
