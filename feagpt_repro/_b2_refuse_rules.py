# -*- coding: utf-8 -*-
"""越界规则的**唯一真相源** —— `REFUSE_ADDENDUM` 的规则段落由本表渲染。

为什么要有这个文件（T-B2RULES 的由来）
======================================
2026-11-02 的 T-B2B5 出过一次真实事故：addendum 手写

    柱壳：长桁数在 1..4 之间（只能是 0 或 >= 5）

而代码是「1..4 **越界**」。一句话把越界集合写成了合法域，deepseek 照字面
把 v7 里合法的 8 根柱壳题 6/6 全拒，过拒率被推到 30%，「可单独引用」判否。
glm 同一句下 0/20 过拒 —— 不是它读对了，是它没按字面核。

病根不是笔误，是**结构**：手写文本里的数字和方向，没有任何机器检查它与
`feagpt/*.py` 的 `_validate` 说同一件事。写得再对，下一次改代码就漂了。

所以本表把两件事绑死：

1. 每条规则同时给出 ``outside``（该被拒）与 ``inside``（该放过）两组探针；
2. 规则在 addendum 里的**文字由探针渲染**，数字一律不手写。

于是 ``--check`` 的双向实测**同时就是文本的闸**：

   · ``outside`` 每个值 —— 该族校验器必须抛，且消息必须命中 ``expect_all``；
   · ``inside`` 每个值 —— 必须**不**抛（这一向正是 2026-11-02 漏掉的那一半）；
   · 表与代码不合 ⇒ 红，红的理由直接指出哪条规则、哪个值、期望什么。

方向写反（把 outside/inside 互换）立刻红，因为基线合法值会「应抛而不抛」。
数字写错（比如把 MIN_STRINGERS 抄成 4）也立刻红，因为探针用的是真常量。

还有一道**反向覆盖**闸（``--check`` 里的 ``[F:*]``）：
从族模块源码里把 ``raise ValueError(f"{FAMILY}: ...")` 的字面前缀抽出来，
断言**每一个**都被表里某条规则的 ``expect_all`` 命中 —— 防止「表漏了一条规则
而没人发现」。这条不会按构造恒真：删掉一条规则就红。

不做什么
--------
不做「用关键字判文本对错」的闸。换个说法就绕过去了，那是给未来埋雷。
文本正确的原因是**它的数字与方向都来自被实测的探针**，不是因为它含某个词。
模板措辞收在本文件顶部的 ``TMPL_*`` 常量里，只有几条，人工可审。

用法
----
    python _b2_refuse_rules.py --check        # 双向实测 + 反向覆盖（闸）
    python _b2_refuse_rules.py --render       # 打印渲染出的 addendum 段落
    python _b2_refuse_rules.py --diff         # 与 gen_candidates_v2.js 现状比对
    python _b2_refuse_rules.py --self-test    # 变异自检（各向必须红在指定位置）
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _b2_build_refuse_set import (CAP_KEYWORDS, INP_WRITER, spec_of)  # noqa: E402

JS_PATH = os.path.join(HERE, 'gen_candidates_v2.js')

# addendum 里由本表生成的区块，用这对标记包起来（js 里是注释行）。
BLOCK_BEGIN = '// >>> REFUSE_RULES:BEGIN（本区块由 _b2_refuse_rules.py --emit 生成，勿手改）'
BLOCK_END = '// <<< REFUSE_RULES:END'

# ---------------------------------------------------------------------------
# 渲染模板：**全文件唯一**的措辞来源。
# 每条模板只出现一次，改措辞来这里改一处；数字由探针填。
# ---------------------------------------------------------------------------
TMPL_BAND = '{label}为 {vals} 时**建不出**（能建的是 {zero}，或 >= {lo}）'
TMPL_LT = '{label} < {limit}'
TMPL_GE = '{label} >= {limit}'          # limit 由 outside 最小值取
TMPL_GE_NAME = '{label} >= {limit_name}'  # 同 GE，但把阈值写成名字（"半径"）
TMPL_POS = '{label} <= 0'
TMPL_NE = '{label}只支持 {only}，其余一律**建不出**'

FAMILY_LABEL = {'fuselage_barrel': '柱壳',
                'open_hole_panel': '开孔板',
                'stiffened_panel': '加筋板',
                'wingbox': '翼盒'}

# 能力越界的中文名（anchor → 展示名）。顺序即渲染顺序。
CAP_LABELS = [('frequency', '模态/固有频率'),
              ('buckle', '屈曲特征值'),
              ('dynamic', '瞬态与冲击'),
              ('contact', '接触'),
              ('plastic', '塑性/屈服后'),
              ('fatigue', '疲劳寿命'),
              ('thermal', '热-结构耦合'),
              ('failure', '复合材料失效准则（Hashin/Tsai-Wu 等）')]

GEOM_HEAD = ('   · **几何越界**（该族参数合法范围装不下）：')
CAP_HEAD = ('   · **能力越界**（求解器只有线性静力、小变形、金属弹性/铺层线弹性）：')


# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GeomRule:
    """一条几何越界规则。

    ``outside`` / ``inside`` 都是 override dict 的元组，喂给 ``spec_of`` 造 spec。
    ``expect_all`` 里的每个子串都必须出现在抛出的消息里 —— 这样既钉参数名
    （区分 ``stringer_height`` 与 ``frame_height`` 两条同向规则），也钉方向。
    """
    rid: str
    family: str
    param: str
    label: str
    outside: tuple
    inside: tuple
    expect_all: tuple
    kind: str                      # band | lt | ge | ge_name | pos | ne
    limit_name: str = ''           # ge_name 用
    only: str = ''                 # ne 用
    frag: str = ''                 # 覆盖渲染片段（pos 多参数时用来合并 label）
    in_text: bool = True           # False = 只参与反向覆盖，不写进 addendum
    mutate: object = None          # 可选：造非 override 型探针（如塞未知键）


def _v(o, key):
    return float(o[key])


# ---------------------------------------------------------------------------
# 柱壳（radius = diameter/2 = 800；MIN_STRINGERS = 5）
# ---------------------------------------------------------------------------
FUS = 'fuselage_barrel'
GEOM_RULES = [

    # ---- 柱壳 ------------------------------------------------------------
    GeomRule('fus_nstr_band', FUS, 'n_stringers', '长桁数',
             outside=tuple({'n_stringers': n} for n in (1, 2, 3, 4)),
             inside=tuple({'n_stringers': n} for n in (0, 5, 6, 8, 12)),
             expect_all=("n_stringers in 1..", 'clean-mesh envelope'),
             kind='band'),

    GeomRule('fus_nstr_neg', FUS, 'n_stringers', '长桁数',
             outside=({'n_stringers': -1}, {'n_stringers': -5}),
             inside=({'n_stringers': 0},),
             expect_all=('n_stringers must be >= 0',),
             kind='lt', frag='{label} < 0'),

    GeomRule('fus_nfrm', FUS, 'n_frames', '框数',
             outside=({'n_frames': 0}, {'n_frames': 1}),
             inside=({'n_frames': 2}, {'n_frames': 3}),
             expect_all=('n_frames must be >= 2',),
             kind='lt'),

    GeomRule('fus_strh', FUS, 'stringer_height', '长桁高',
             outside=({'stringer_height': 800.0}, {'stringer_height': 900.0}),
             inside=({'stringer_height': 100.0}, {'stringer_height': 400.0}),
             expect_all=('stringer_height', '>= radius'),
             kind='ge_name', limit_name='半径'),

    GeomRule('fus_frmh', FUS, 'frame_height', '框高',
             outside=({'frame_height': 800.0}, {'frame_height': 900.0}),
             inside=({'frame_height': 100.0}, {'frame_height': 400.0}),
             expect_all=('frame_height', '>= radius'),
             kind='ge_name', limit_name='半径'),

    GeomRule('fus_kind', FUS, 'stringer_kind', '剖面类型',
             outside=({'stringer_kind': 'I'}, {'stringer_kind': 'T'},
                      {'stringer_kind': 'J'}),
             inside=({'stringer_kind': 'blade'},),
             expect_all=('stringer_kind', 'not implemented by'),
             kind='ne', only='blade'),

    # 非正参数：循环里一条 raise 打 7 个键，这里逐个探（漏一个反向覆盖会红）
    GeomRule('fus_pos', FUS, 'diameter', '直径/长度/壁厚/长桁厚',
             outside=({'diameter': 0.0}, {'length': 0.0}, {'thickness': 0.0},
                      {'stringer_thickness': 0.0}, {'diameter': -10.0}),
             inside=({'diameter': 1600.0}, {'thickness': 3.0}),
             expect_all=('must be > 0',),
             kind='pos', frag='直径/长度/壁厚/长桁厚 <= 0'),

    # ---- 开孔板（length 400 / width 200 / hole_d 30）---------------------
    'OPEN_HOLE',

    # ---- 加筋板（600 x 600，n_stringers 3，stringer_height 20）-----------
    'PANEL',

    # ---- 翼盒（梁在 25%–70% 弦向）--------------------------------------
    'WINGBOX',
]


# 开孔板与加筋板、翼盒的定义拆开写，便于阅读（顺序由上面的占位符决定）。
_OPEN_HOLE_RULES = [
    GeomRule('oh_pos', 'open_hole_panel', 'hole_d', '孔直径/板长/板宽/板厚',
             outside=({'hole_d': 0.0}, {'hole_d': -5.0}, {'length': 0.0},
                      {'width': 0.0}, {'thickness': 0.0}),
             inside=({'hole_d': 30.0},),
             expect_all=('must be > 0',),
             kind='pos', frag='孔直径/板长/板宽/板厚 <= 0'),

    GeomRule('oh_inside', 'open_hole_panel', 'hole_x', '孔心使孔不在板内（含贴边）',
             outside=({'hole_x': 10.0}, {'hole_y': 5.0},
                      {'hole_x': 395.0}, {'hole_y': 196.0}),
             inside=({'hole_x': 200.0}, {'hole_y': 100.0}),
             expect_all=('is not inside the', 'edge margin'),
             kind='ne', only='', frag='孔心使孔不在板内（含贴边）'),

    GeomRule('oh_lam', 'open_hole_panel', 'hole_d', '孔直径 / 板宽',
             outside=({'hole_d': 70.0}, {'hole_d': 100.0}),
             inside=({'hole_d': 30.0}, {'hole_d': 60.0}),
             expect_all=('d/width', '>= 1/3'),
             kind='ge_name', limit_name='1/3'),

    GeomRule('oh_len', 'open_hole_panel', 'length', '板长',
             outside=({'length': 50.0}, {'length': 59.0}),
             inside=({'length': 100.0}, {'length': 400.0}),
             expect_all=('< 2 * hole_d',),
             kind='ne', frag='板长 < 2 倍孔直径'),
]

_PANEL_RULES = [
    GeomRule('sp_pos', 'stiffened_panel', 'thickness', '板长/板宽/板厚/长桁高/长桁厚',
             outside=({'thickness': 0.0}, {'length': 0.0}, {'width': 0.0},
                      {'stringer_height': 0.0}, {'stringer_thickness': 0.0}),
             inside=({'thickness': 2.0},),
             expect_all=('must be > 0',),
             kind='pos', frag='板长/板宽/板厚/长桁高/长桁厚 <= 0'),

    GeomRule('sp_nstr_neg', 'stiffened_panel', 'n_stringers', '长桁数',
             outside=({'n_stringers': -1}, {'n_stringers': -3}),
             inside=({'n_stringers': 0}, {'n_stringers': 3}),
             expect_all=('n_stringers must be >= 0',),
             kind='lt', frag='长桁数 < 0'),

    GeomRule('sp_strh', 'stiffened_panel', 'stringer_height', '长桁高',
             outside=({'stringer_height': 600.0}, {'stringer_height': 900.0}),
             inside=({'stringer_height': 20.0}, {'stringer_height': 300.0}),
             expect_all=('>= panel width',),
             kind='ge_name', limit_name='板宽'),
]

_WINGBOX_RULES = [
    GeomRule('wb_web_out', 'wingbox', 'web_chordwise', '中间腹板位置',
             outside=({'web_chordwise': [0.10]}, {'web_chordwise': [0.90]},
                      {'web_chordwise': [0.25]}, {'web_chordwise': [0.70]},
                      {'web_chordwise': [0.0]}, {'web_chordwise': [0.95]}),
             inside=({'web_chordwise': [0.40]}, {'web_chordwise': [0.60]}),
             expect_all=('is not strictly between the spars',),
             kind='ne', frag='中间腹板位置不在前后梁之间（含正好落在梁上）'),

    GeomRule('wb_web_str', 'wingbox', 'web_chordwise', '腹板',
             outside=({'web_chordwise': [0.4], 'n_stringers_per_skin': 2},
                      {'web_chordwise': [0.475], 'n_stringers_per_skin': 1}),
             inside=({'web_chordwise': [0.5], 'n_stringers_per_skin': 1},
                     {'web_chordwise': [0.4], 'n_stringers_per_skin': 1},
                     {'web_chordwise': [0.4], 'n_stringers_per_skin': 3}),
             expect_all=('coincides with a stringer station',),
             kind='ne', frag='腹板落在长桁站位上'),

    # ---- 三族的「未知参数」护栏（不属于越界语义，但有 raise 就必须被覆盖）
    #     不写进 addendum：模型不会凭空造键，这条是 spec 格式的守卫。
    GeomRule('fus_unknown', FUS, 'unknown', '未知参数',
             outside=({},), inside=({},),
             expect_all=('unknown parameter(s)',),
             kind='ne', in_text=False,
             mutate=lambda d: d['structure']['params'].__setitem__('bogus_key', 1)),
    GeomRule('oh_unknown', 'open_hole_panel', 'unknown', '未知参数',
             outside=({},), inside=({},),
             expect_all=('unknown parameter(s)',),
             kind='ne', in_text=False,
             mutate=lambda d: d['structure']['params'].__setitem__('bogus_key', 1)),
    GeomRule('sp_unknown', 'stiffened_panel', 'unknown', '未知参数',
             outside=({},), inside=({},),
             expect_all=('unknown parameter(s)',),
             kind='ne', in_text=False,
             mutate=lambda d: d['structure']['params'].__setitem__('bogus_key', 1)),
]


def _expand():
    """把占位符替换成真实规则列表（保持书写顺序）。"""
    out = []
    for r in GEOM_RULES:
        if r == 'OPEN_HOLE':
            out.extend(_OPEN_HOLE_RULES)
        elif r == 'PANEL':
            out.extend(_PANEL_RULES)
        elif r == 'WINGBOX':
            out.extend(_WINGBOX_RULES)
        else:
            out.append(r)
    return out


RULES = _expand()
RULE_BY_ID = {r.rid: r for r in RULES}


# ---------------------------------------------------------------------------
# 实测
# ---------------------------------------------------------------------------
def _run_family(fam, override, mutate=None):
    """调**该族自己的**校验器，返回 (是否拒绝, 消息)。

    与 ``_b2_build_refuse_set._refuse_geometry`` 同一套路，但这里每条规则
    自己带探针，不复用 GEOM_CASES（那些是题目，不是规则）。
    ``mutate`` 用来造非 override 型探针（例如往 params 里塞一个未知键）。
    """
    from feagpt.spec import FEASpec
    d = spec_of(fam, override, 'probe')
    if mutate:
        mutate(d)
    spec = FEASpec.from_dict(d)
    if fam == 'wingbox':
        import gmsh
        from feagpt import geometry
        gmsh.initialize()
        gmsh.option.setNumber('General.Terminal', 0)
        gmsh.option.setNumber('General.Verbosity', 0)
        try:
            gmsh.model.add('probe')
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


def check(verbose=True):
    """双向实测 + 反向覆盖。返回 (ok, problems, notes)。"""
    problems, notes = [], []

    for r in RULES:
        # ① outside 每个值都必须被拒，且消息命中全部关键字
        for o in r.outside:
            refused, msg = _run_family(r.family, o, r.mutate)
            if not refused:
                problems.append('[%s] outside %r 应当被拒，实际**没抛**（规则方向或阈值错）'
                                % (r.rid, o))
                continue
            for frag in r.expect_all:
                if frag not in msg:
                    problems.append('[%s] outside %r 被拒了，但消息缺 %r：%s'
                                    % (r.rid, o, frag, msg[:120]))
                    break
        # ② inside 每个值都必须放过 —— 2026-11-02 漏掉的那一向
        #    ★ 故意不传 r.mutate：mutate 造的是「越界侧」的畸形 spec（例如塞
        #      未知键），拿它去证明「合法值不抛」是自相矛盾的。
        for o in r.inside:
            refused, msg = _run_family(r.family, o)
            if refused:
                problems.append('[%s] inside %r 应当放过，实际**被拒**：%s'
                                % (r.rid, o, msg[:120]))

    # ③ 反向覆盖：族模块里每条 raise 都必须被某条规则命中（防漏规则）
    for fam, prefixes in _raise_prefixes().items():
        covered = set()
        for r in RULES:
            if r.family != fam:
                continue
            for o in r.outside:
                refused, msg = _run_family(fam, o, r.mutate)
                if refused:
                    covered.update(p for p in prefixes if p in msg)
        missing = sorted(set(prefixes) - covered)
        if missing:
            problems.append('[F:%s] 有 raise 没被任何规则覆盖：%s'
                            % (fam, ' | '.join(missing)))
        else:
            notes.append('[F:%s] raise 前缀 %d 条全部被规则覆盖' % (fam, len(prefixes)))

    # ④ 能力越界：关键字必须**不在** deck 生成器里（R58 同源）
    deck = io.open(INP_WRITER, encoding='utf-8').read()
    for anchor, pat in CAP_KEYWORDS.items():
        if re.search(pat, deck):
            problems.append('[C:%s] 关键字 %r 出现在 inp_writer.py 里 —— '
                            '该能力其实支持，不能再判越界' % (anchor, pat))

    if verbose:
        for n in notes:
            print('  [ok] ' + n)
        for p in problems:
            print('  [BAD] ' + p)
        print('几何规则 %d 条 / 能力 %d 条；探针 %d 个'
              % (len(RULES), len(CAP_KEYWORDS),
                 sum(len(r.outside) + len(r.inside) for r in RULES)))
    return (not problems), problems, notes


def _raise_literals(src, func_names, must_contain=None):
    """抽出指定函数里所有 ``raise ValueError(...)`` 的**字面指纹**。

    ★ 前两版都错在这里，记下来：
      ① 第一版正则 ``f"\\{FAMILY\\}: ([^"{}]+)`` —— 占位符紧贴冒号时整条被跳过，
         三族的 ``must be > 0`` 全漏，于是「删掉 fus_pos」自检照样全绿
         （**判据自己漏了，比没有判据更危险**）；
      ② 第二版按括号配对切 raise —— 字符串里的圆括号会把配对数带偏，抽到跨语句
         的碎片（出现过 ``.make_spec: unknown parameter(s)``）。
      现在用 ``ast``：函数边界由语法树给，占位符由 ``FormattedValue`` 天然切开，
      不猜括号、不跨语句。

    ``must_contain`` 用来在巨型函数（``geometry.build``）里只取某一主题的 raise。
    """
    import ast
    tree = ast.parse(src)
    got = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name in func_names):
            continue
        for sub in ast.walk(node):
            if not (isinstance(sub, ast.Raise) and isinstance(sub.exc, ast.Call)):
                continue
            for arg in sub.exc.args:
                segs = []
                if isinstance(arg, ast.JoinedStr):
                    segs = [v.value for v in arg.values
                            if isinstance(v, ast.Constant) and isinstance(v.value, str)]
                elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    segs = [arg.value]
                # ★ 过滤在**收录之前**：先判整句是否属于本主题，再收它的片段。
                #   前一版把无条件收录写在前面、过滤写成「补加」，结果
                #   must_contain 形同虚设（翼盒抽到了 "unknown structure family"）。
                if must_contain and must_contain not in ''.join(segs):
                    continue
                for seg in segs:
                    seg = seg.strip()
                    if len(seg) >= 8:
                        got.append(seg)
    return sorted(set(got))


def _raise_prefixes():
    """每族**校验路径**上的 raise 字面指纹。

    只抽 ``_validate`` / ``parse_params``（参数校验的所在），翼盒抽 ``build``
    里含 "web" 的那几条。不抽整个模块 —— geometry.py 里还有网格、载荷、
    族名的 raise，与越界规则无关，抽进来只会制造假红。
    """
    from feagpt import fuselage, geometry, open_hole, panel
    out = {}
    for fam, mod in (('fuselage_barrel', fuselage),
                     ('open_hole_panel', open_hole),
                     ('stiffened_panel', panel)):
        src = io.open(mod.__file__, encoding='utf-8').read()
        out[fam] = _raise_literals(src, ('_validate', 'parse_params'))
    src = io.open(geometry.__file__, encoding='utf-8').read()
    out['wingbox'] = _raise_literals(src, ('build', 'build_wingbox'),
                                     must_contain='web')
    return out


# ---------------------------------------------------------------------------
# 渲染：文本由探针派生，数字不手写
# ---------------------------------------------------------------------------
def _frag(r):
    """一条规则 → 一个中文片段。所有数字都从这里算，不手写。"""
    if r.frag:
        # frag 里可能带 {label} 占位（同一句覆盖两种语义时用），要 format
        return r.frag.format(label=r.label)
    if r.kind == 'band':
        vals = sorted({int(_v(o, r.param)) for o in r.outside})
        inside = sorted(int(_v(o, r.param)) for o in r.inside)
        zero = 0 if 0 in inside else None
        lo = min(v for v in inside if v > 0)
        return TMPL_BAND.format(label=r.label,
                                vals='/'.join(str(v) for v in vals),
                                zero=zero, lo=lo)
    if r.kind == 'lt':
        # 越界 = param < limit；limit = max(outside)+1
        limit = max(_v(o, r.param) for o in r.outside) + 1
        return TMPL_LT.format(label=r.label, limit=int(limit))
    if r.kind == 'ge':
        limit = min(_v(o, r.param) for o in r.outside)
        return TMPL_GE.format(label=r.label, limit=('%g' % limit))
    if r.kind == 'ge_name':
        return TMPL_GE_NAME.format(label=r.label, limit_name=r.limit_name)
    if r.kind == 'pos':
        return TMPL_POS.format(label=r.label)
    if r.kind == 'ne':
        if r.only:
            return TMPL_NE.format(label=r.label, only=r.only)
        return r.frag
    raise AssertionError('未处理的 kind: ' + r.kind)


def render_geom_lines():
    """按族分组渲染，一族一行（长行不折 —— 折行是排版，不参与判据）。"""
    lines = [GEOM_HEAD]
    for fam in ('fuselage_barrel', 'open_hole_panel', 'stiffened_panel', 'wingbox'):
        frags = [_frag(r) for r in RULES if r.family == fam and r.in_text]
        if frags:
            lines.append('     - %s：%s。' % (FAMILY_LABEL[fam], '；'.join(frags)))
    return lines


def render_cap_lines():
    names = [label for _a, label in CAP_LABELS]
    body = '、'.join(names)
    return [CAP_HEAD,
            '     %s—— 一个都做不了。' % body]


def render_block():
    """整个由本表生成的区块（几何 + 能力）。"""
    return '\n'.join(render_geom_lines() + render_cap_lines())


def read_js_block(path=JS_PATH):
    """从 js 里取出现有区块的**纯文本内容**（已剥掉 JS 包裹）。找不到返回 None。"""
    txt = io.open(path, encoding='utf-8', newline='').read()
    txt = txt.replace('\r\n', '\n')
    i = txt.find(BLOCK_BEGIN)
    j = txt.find(BLOCK_END)
    if i < 0 or j < 0 or j < i:
        return None
    inner = txt[i + len(BLOCK_BEGIN):j].strip('\n')
    # 剥掉 const ... = ` 与结尾的 `;
    m = re.match(r'const\s+REFUSE_RULES_BLOCK\s*=\s*`\n(.*)\n`;\s*$', inner, re.S)
    if not m:
        return None
    return m.group(1)


def emit(path=JS_PATH):
    """把渲染结果写回 js 的标记区块（唯一入口，禁止手改区块）。"""
    txt = io.open(path, encoding='utf-8', newline='').read().replace('\r\n', '\n')
    i = txt.find(BLOCK_BEGIN)
    j = txt.find(BLOCK_END)
    if i < 0 or j < 0:
        raise SystemExit('js 里找不到标记区块：先在 REFUSE_ADDENDUM 里放好 '
                         + BLOCK_BEGIN + ' / ' + BLOCK_END)
    body = 'const REFUSE_RULES_BLOCK = `\n' + render_block() + '\n`;'
    new = txt[:i + len(BLOCK_BEGIN)] + '\n' + body + '\n' + txt[j:]
    io.open(path, 'w', encoding='utf-8', newline='\n').write(new)
    return new


def diff_block(path=JS_PATH):
    """渲染结果 vs js 现状，返回 (是否一致, 差异行列表)。"""
    import difflib
    cur = read_js_block(path)
    if cur is None:
        return False, ['js 里找不到 REFUSE_RULES 区块标记']
    want = render_block()
    a, b = cur.split('\n'), want.split('\n')
    if a == b:
        return True, []
    return False, list(difflib.unified_diff(a, b, 'js(now)', 'rules(rendered)', lineterm=''))


# ---------------------------------------------------------------------------
def self_test():
    """变异自检：每一向都必须**红在指定位置**，且理由对。

    只跑 ``--check`` 全绿是自证（F-9 的教训）。必须把实现改坏，看闸会不会红。
    """
    ok = True

    def expect_bad(tag, rules, want_frag):
        nonlocal ok
        global RULES
        saved = RULES
        try:
            RULES = rules
            passed, problems, _ = check(verbose=False)
        finally:
            RULES = saved
        hit = any(want_frag in p for p in problems)
        if passed or not hit:
            ok = False
            print('  [BAD] %s：期望红在含 %r 的问题里，实测 passed=%s problems=%s'
                  % (tag, want_frag, passed, problems[:2]))
        else:
            print('  [ok] %s → 红在 %r' % (tag, want_frag))

    def expect_ok(tag, rules):
        nonlocal ok
        global RULES
        saved = RULES
        try:
            RULES = rules
            passed, problems, _ = check(verbose=False)
        finally:
            RULES = saved
        if not passed:
            ok = False
            print('  [BAD] %s：期望全绿，实测红：%s' % (tag, problems[:2]))
        else:
            print('  [ok] %s → 全绿' % tag)

    # T0 本来就应该全绿（否则后面的变异没有对照基线）
    expect_ok('T0 原表', RULES)

    # T1 方向反：把 band 规则的 inside 写成越界值
    r = RULE_BY_ID['fus_nstr_band']
    bad1 = GeomRule(r.rid, r.family, r.param, r.label,
                    outside=r.outside, inside=({'n_stringers': 2},),
                    expect_all=r.expect_all, kind=r.kind)
    expect_bad('T1 band 的 inside 取越界值 2', [bad1], '[fus_nstr_band] inside')

    # T2 阈值漂：把 n_frames 的 outside 从 1 改成 0（0 确实越界，但 1 漏了）
    r = RULE_BY_ID['fus_nfrm']
    bad2 = GeomRule(r.rid, r.family, r.param, r.label,
                    outside=({'n_frames': 2},), inside=r.inside,
                    expect_all=r.expect_all, kind=r.kind)
    expect_bad('T2 n_frames outside 取合法值 2', [bad2], '[fus_nfrm] outside')

    # T3 漏规则：删掉 fus_pos，反向覆盖必须红（这一向守「表不全」）
    expect_bad('T3 删掉 fus_pos', [x for x in RULES if x.rid != 'fus_pos'],
               '[F:fuselage_barrel] 有 raise 没被任何规则覆盖')

    # T4 expect 写松：把 fus_strh 的 expect 改成空元组（判据变成「拒了就算对」）
    r = RULE_BY_ID['fus_strh']
    bad4 = GeomRule(r.rid, r.family, r.param, r.label,
                    outside=r.outside, inside=r.inside,
                    expect_all=('绝不存在的子串',), kind=r.kind)
    expect_bad('T4 fus_strh expect 写了个不存在的子串', [bad4], '消息缺')

    # T5 能力侧：假装 *FREQUENCY 存在（把 CAP_KEYWORDS 换成必然命中的模式）
    #     直接改模板签名不方便，改为断言 _frag 的数字确实来自探针
    r = RULE_BY_ID['fus_nstr_band']
    txt = _frag(r)
    if '1/2/3/4' not in txt or '>= 5' not in txt:
        ok = False
        print('  [BAD] T5 band 渲染文本与探针不符：%r' % txt)
    else:
        print('  [ok] T5 band 渲染 → %r' % txt)

    # T6 渲染的阈值必须随探针变：把 n_frames 的 outside 改成 {0}，文本应变成 "< 1"
    r = RULE_BY_ID['fus_nfrm']
    alt = GeomRule(r.rid, r.family, r.param, r.label,
                   outside=({'n_frames': 0},), inside=r.inside,
                   expect_all=r.expect_all, kind=r.kind)
    if _frag(alt) != '框数 < 1':
        ok = False
        print('  [BAD] T6 阈值没随探针变：%r（应为 "框数 < 1"）' % _frag(alt))
    else:
        print('  [ok] T6 阈值随探针变 → %r' % _frag(alt))

    return ok


# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--render', action='store_true')
    ap.add_argument('--diff', action='store_true')
    ap.add_argument('--emit', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args(argv)

    if a.self_test:
        return 0 if self_test() else 1
    if a.render:
        print(render_block())
        return 0
    if a.emit:
        emit()
        same, lines = diff_block()
        print('已写入 js；写入后复查：' + ('一致' if same else '\n'.join(lines)))
        return 0 if same else 1
    if a.diff:
        same, lines = diff_block()
        print('一致' if same else '\n'.join(lines))
        return 0 if same else 1
    ok, _problems, _notes = check(verbose=True)
    print('全部通过' if ok else '有失败项')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
