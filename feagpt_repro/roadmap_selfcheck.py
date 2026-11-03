#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""roadmap_selfcheck.py — 进度看板的算术自洽闸（T-R2 / ROADMAP §13 第 7 项）

要解决的问题
------------
`FEM-Bench-Aero/ROADMAP.md` 的 §1 看板把四段权重、完成度、合计、以及「同一天的
三个口径」写在**散文里**，而**没有任何工具读它们**（R58：无工具读的 = 无闸）。
实测（2026-11-03，本闸立项前）已经漂了三类，且都不是「新发现」，是**一直都在**：

  1. 段 A 写「10 项里 8.5」：§3 明细表实有 **9** 行；且 8.5/10 = 85%，而该格
     显示 **88%** —— 这格自 v2.0（2026-10-30 / T-R1）建表起就与任何可复核基数
     对不上，连续 8 个版本没人发现。
  2. 「同一天的三个口径」里「全量 ROADMAP ~38%」：合计从 38→39→43→44→49 漂了
     **5 个版本**，这张表一次没跟着改（38% 是 v2.1 的合计，抄在那儿当常量了）。
  3. 段 B 写「达标按 glm 记 **8/8**」：与同格的「成绩单 87.5%」自相矛盾
     （87.5% = 7/8），也与 §4 的 B1 行「7/8 达标」矛盾。

共同点：**数字只被人读，不被工具读；而人只在写那一段时读它**。
本闸把「可复核的算式」变成硬约束：数字旁边必须站得下一个算式，且算式要能复算。

判据（每条都须能变红，见 --self-test）
--------------------------------------
R0  适用性：文件在、四段与合计行都能解析出来（**解析不到判红，不是 skip**）
R1  四段权重之和 == 100%
R2  合计 == Σ(权重 x 完成度)；若合计格带了 x 算式，算式复算值也须等于合计
R3  「同一天的三个口径」里，分母为 `A` / `A+B+C+D` 的行必须等于对应数；
    其余行（分母不可复算）必须**显式标 `无算式`**，否则判红
R4  每段声明的项数 == 该段明细表的实际行数（§3/§4/§5/§6，按标题里的「段 X」定位）
R5  每段「完成度是怎么算的」栏里的算式，复算值 == 该段显示的完成度（缺算式判红）
R6  段 B 的「成绩单 X%」== 它的「达标 a/b」（成绩单得分就是达标率，不许两套）

边界（R69）
-----------
- 只判**算术与分母**，不判「完成度估得对不对」。看板自己写着「估算，非 artifact」，
  闸只能保证「估算写得自洽、可复核、可被下一个人重算」。
- 「算到 30 天关键判据（A+D）」那一行**没有可复核算式**（分母不是四段加权），
  本闸**不覆盖**它；但它必须在表里显式写 `无算式`，且由本闸在输出里**单列点名**
  —— 豁免要写出来，不能靠「解析不到就跳过」静默放行。
- 不读 artifact、不碰任何成绩、不产生对外数字；**不得进入任何对外数字**。
- 判据不依赖段号/行号/顺序：段与明细表的对应靠标题里的「段 X」字面，不靠 §N。

用法
----
    python roadmap_selfcheck.py                 # 查当前仓库的 ROADMAP.md
    python roadmap_selfcheck.py --self-test     # 十向自检（每向断言「红的是哪一条」）
    python roadmap_selfcheck.py --json out.json
    python roadmap_selfcheck.py --file X.md     # 指定文件（负控用）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ROADMAP = HERE.parent / 'FEM-Bench-Aero' / 'ROADMAP.md'

SEGS = ('A', 'B', 'C', 'D')
TOL = 0.6            # 显示取整容差（百分比点）
NO_EXPR_TOKEN = '无算式'


# ----------------------------------------------------------------- 解析

def _split_sections(text):
    """按 `## ` 一级标题切段 -> {标题: 正文}。段与明细表靠标题里的「段 X」关联。"""
    secs, cur, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r'^##\s+(.*\S)\s*$', line)
        if m:
            if cur is not None:
                secs[cur] = '\n'.join(buf)
            cur, buf = m.group(1), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        secs[cur] = '\n'.join(buf)
    return secs


def _cells(line):
    """把 `| a | b | c |` 拆成 ['a','b','c']（首尾空串去掉，单元格内不允许裸竖线）。"""
    parts = line.strip().split('|')
    if parts and parts[0].strip() == '':
        parts = parts[1:]
    if parts and parts[-1].strip() == '':
        parts = parts[:-1]
    return [p.strip() for p in parts]


def _pct(s):
    """从 `**≈ 49%**` / `88%` / `**~38%**` 里取数字。"""
    m = re.search(r'([\d.]+)\s*%', s)
    return float(m.group(1)) if m else None


def _board_sec(text):
    """找到「进度看板」那一节（不靠 § 编号：靠标题字面）。"""
    for k, v in _split_sections(text).items():
        if '进度看板' in k:
            return v
    return None


def parse(text):
    """-> dict(segs={A: {w,pct,cell}, ...}, total={pct,cell}, calib=[{den,pct,raw}], detail={A:n,...})"""
    board = _board_sec(text)
    if board is None:
        raise ValueError('找不到「进度看板」小节')
    segs, total, calib = {}, None, []
    in_calib = False
    for line in board.splitlines():
        if '三个口径' in line:
            in_calib = True
            continue
        if not line.strip().startswith('|'):
            continue
        c = _cells(line)
        if len(c) < 3:
            continue
        head = c[0].replace('*', '').strip()
        if head == '段' or set(head) <= set('-: '):
            continue
        m = re.match(r'^([ABCD])\s', head)
        if m and not in_calib:
            segs[m.group(1)] = {'w': _pct(c[1]), 'pct': _pct(c[2]),
                                'cell': c[3] if len(c) > 3 else ''}
            continue
        if head.startswith('合计') and not in_calib:
            total = {'pct': _pct(c[2]), 'cell': c[3] if len(c) > 3 else ''}
            continue
        if in_calib:
            if c[1].replace('*', '').strip() == '分母':
                continue                     # 表头行（不是数据）
            calib.append({'den': re.sub(r'\s+', '', c[1]), 'pct': _pct(c[2]), 'raw': c})
    if total is None:
        raise ValueError('找不到「合计」行')
    if set(segs) != set(SEGS):
        raise ValueError('四段没解析全，实得 %s' % sorted(segs))

    secs = _split_sections(text)
    detail = {}
    for k, v in secs.items():
        m = re.search(r'段\s*([ABCD])', k)
        if m:
            detail[m.group(1)] = re.findall(r'^\|\s*([ABCD]\d+[a-z]?)\s*\|', v, re.M)
    return {'segs': segs, 'total': total, 'calib': calib, 'detail': detail,
            'sections': secs}


# ------------------------------------------------------- 算式复算（R5）

def _eval_prod_expr(expr):
    """`0.2×0.875 + 0.2×0.6 + ...` -> 数值。只认 × + 数字，别的一律不猜。"""
    total = 0.0
    for term in expr.split('+'):
        term = term.strip()
        if not term:
            continue
        factors = re.split(r'[×x]', term)
        prod = 1.0
        for f in factors:
            prod *= float(f.strip())
        total += prod
    return total


def recompute(cell):
    """从「完成度是怎么算的」栏里抽取**所有**可复核算式 -> [(标签, 百分比值), ...]

    认三种形态（都是本表实际用过的）：
      `9 项里 8.0`          -> 8.0/9*100
      `a×b + c×d = S`       -> 乘积和（S<=1.5 视为比例、x100）
      `6/6 = 100%`          -> 100
    """
    out = []
    for mm in re.finditer(r'([\d.]+)\s*项里\s*([\d.]+)', cell):
        n, x = float(mm.group(1)), float(mm.group(2))
        if n:
            out.append(('项里 %g/%g' % (x, n), x / n * 100.0))
    for mm in re.finditer(r'((?:[\d.]+\s*[×x]\s*[\d.]+)'
                          r'(?:\s*\+\s*[\d.]+\s*[×x]\s*[\d.]+)*)\s*=\s*([\d.]+)', cell):
        v = _eval_prod_expr(mm.group(1))
        if abs(v - float(mm.group(2))) > 1e-9:
            # 算式自己就不成立（左右不等）—— 这是最阴的一种：读者只核等式右边
            out.append(('算式不自洽 %s' % mm.group(0), float('nan')))
            continue
        out.append(('加权 %s' % mm.group(1).strip(), v * 100.0 if v <= 1.5 else v))
    for mm in re.finditer(r'([\d.]+)\s*/\s*([\d.]+)\s*=\s*([\d.]+)\s*%', cell):
        a, b, p = float(mm.group(1)), float(mm.group(2)), float(mm.group(3))
        if b:
            # 两边都核：① 写的比例算出来是多少 ② 写的百分比是不是这个数。
            # 只核 a/b 会漏「a/b 对、右边那个数写错」——自检 T7 就是这么抓到本闸的。
            out.append(('%g/%g 复算' % (a, b), a / b * 100.0))
            out.append(('写的 %g%%' % p, p))
    return out


# ----------------------------------------------------------------- 判定

def run_text(text):
    """-> (ok, problems=[{id,msg}], info={})

    判据按「能复算就复算、复算不了就判红」写：解析不到锚点 = 红，不是 skip
    （负控五条 ③：锚点缺失判红不 skip）。
    """
    probs = []

    def bad(cid, msg):
        probs.append({'id': cid, 'msg': msg})

    try:
        p = parse(text)
    except Exception as e:
        bad('R0', '解析失败：%s（格式变了要同步改闸，不许静默跳过）' % (e,))
        return False, probs, {}

    segs, total, detail = p['segs'], p['total'], p['detail']

    # R0 四段明细表都要能定位到
    miss = [s for s in SEGS if s not in detail]
    if miss:
        bad('R0', '明细表定位失败：段 %s 找不到标题里带「段 X」的小节' % '/'.join(miss))

    # R1 权重和
    wsum = sum(segs[s]['w'] or 0 for s in SEGS)
    if abs(wsum - 100.0) > 1e-6:
        bad('R1', '四段权重之和 = %g%%，应为 100%%' % wsum)

    # R2 合计 == Σ(权重 x 完成度)；顺带核合计格里的算式复算值
    calc = sum((segs[s]['w'] or 0) * (segs[s]['pct'] or 0) for s in SEGS) / 100.0
    if total['pct'] is None or abs(calc - total['pct']) > TOL:
        bad('R2', '合计显示 %s%%，按 权重x完成度 复算 = %.2f%%' % (total['pct'], calc))
    for label, v in recompute(total['cell']):
        if v != v or abs(v - (total['pct'] or 0)) > TOL:
            bad('R2', '合计格的算式复算 %.2f != 显示的 %s%%（算式：%s）'
                % (v, total['pct'], label))

    # R3 三口径表：可复算的必须对；不可复算的必须显式标「无算式」
    if not p['calib']:
        bad('R3', '找不到「同一天的三个口径」表')
    uncovered = []
    for row in p['calib']:
        den = row['den']
        if den == 'A':
            if row['pct'] is None or abs(row['pct'] - (segs['A']['pct'] or 0)) > TOL:
                bad('R3', '口径「分母=A」写 %s%%，而段 A 完成度 = %s%%'
                    % (row['pct'], segs['A']['pct']))
        elif den == 'A+B+C+D':
            if row['pct'] is None or abs(row['pct'] - (total['pct'] or 0)) > TOL:
                bad('R3', '口径「分母=A+B+C+D」写 %s%%，而合计 = %s%%（同一个量的两处声明）'
                    % (row['pct'], total['pct']))
        elif NO_EXPR_TOKEN not in ' '.join(row['raw']):
            bad('R3', '口径「分母=%s」没有可复核算式，也未显式标「%s」——'
                      '豁免必须写出来，不能靠解析不到就跳过' % (den, NO_EXPR_TOKEN))
        else:
            uncovered.append(den)

    # R4 声明项数 == 明细行数（扣除段说明里**显式合并**掉的行，如「D5 提交闸（含 D5b）」）
    for s in SEGS:
        cell = segs[s]['cell']
        mm = re.search(r'(\d+)\s*项', cell)
        if not mm:
            bad('R4', '段 %s 没声明「N 项」（无法核分母）' % s)
            continue
        n = int(mm.group(1))
        ids = detail.get(s) or []
        merged = set(re.findall(r'含\s*([ABCD]\d+[a-z]?)', cell))
        ghost = merged - set(ids)
        if ghost:
            bad('R4', '段 %s 说明里写「含 %s」，但明细表里没有这一行' % (s, ','.join(sorted(ghost))))
            continue
        expect = len(ids) - len(merged)
        if n != expect:
            bad('R4', '段 %s 声明 %d 项，明细表实有 %d 行（显式合并 %d：%s）=> 应为 %d'
                % (s, n, len(ids), len(merged), ','.join(sorted(merged)) or '无', expect))

    # R5 每段算式复算 == 完成度
    for s in SEGS:
        cands = recompute(segs[s]['cell'])
        if not cands:
            bad('R5', '段 %s 没给出可复核算式（期望形态：`N 项里 X` / `a×b + ... = S` / '
                      '`x/y = p%%`）' % s)
            continue
        for label, v in cands:
            if v != v or abs(v - (segs[s]['pct'] or 0)) > TOL:
                bad('R5', '段 %s 显示 %s%%，算式「%s」复算 = %.2f'
                    % (s, segs[s]['pct'], label, v))

    # R6 段 B 的成绩单得分 == 达标率
    cellB = segs['B']['cell']
    m_score = re.search(r'成绩单\s*\*\*\s*([\d.]+)\s*%\s*\*\*', cellB)
    m_pass = re.search(r'达标[^0-9]{1,24}?(\d+)\s*/\s*(\d+)', cellB)
    if not m_score or not m_pass:
        bad('R6', '段 B 缺锚点：需同时有「成绩单 **X%%**」与「达标 a/b」'
                  '（成绩单得分 = 达标项/总项，不许两套数）')
    else:
        score = float(m_score.group(1))
        a, b = float(m_pass.group(1)), float(m_pass.group(2))
        rate = a / b * 100.0 if b else float('nan')
        if rate != rate or abs(score - rate) > TOL:
            bad('R6', '段 B 成绩单写 %.1f%%，而其「达标 %g/%g」= %.1f%%' % (score, a, b, rate))

    info = {'wsum': wsum, 'calc': calc, 'total': total['pct'],
            'detail': detail, 'uncovered': uncovered}
    return (not probs), probs, info


def check_file(path=None):
    path = Path(path) if path else DEFAULT_ROADMAP
    if not path.exists():
        return False, [{'id': 'R0', 'msg': '文件不存在：%s' % path}], {}
    return run_text(path.read_text(encoding='utf-8'))


def detail_str(ok, probs, info):
    if not info:
        return '解析失败：%s' % '; '.join(x['msg'] for x in probs)
    head = 'R1 权重=%g | R2 合计 显示 %s vs 复算 %.2f | R4 明细 %s' % (
        info['wsum'], info['total'],
        info['calc'],
        '/'.join('%s=%d' % (k, len(info['detail'].get(k) or [])) for k in SEGS))
    if ok:
        tail = ' | 未覆盖（已显式标「%s」）：%s' % (
            NO_EXPR_TOKEN, ','.join(info['uncovered']) or '无')
        return head + tail
    return head + ' | 红项：' + '; '.join('%s %s' % (x['id'], x['msg']) for x in probs)


# --------------------------------------------------------------- 自检

def _mutate(text, kind):
    """从**解析结果**推出变异点（不写死字面），返回 (新文本, 说明)。

    变异锚点若从基线里现取，重排句子不会让自检失效；锚点缺失则直接抛错，
    由调用方判红（负控五条 ③）。
    """
    p = parse(text)
    segs, detail = p['segs'], p['detail']

    if kind == 'A_pct':
        old = '**%.0f%%**' % segs['A']['pct']
        return text.replace(old, '**%.0f%%**' % (segs['A']['pct'] + 5), 1), '段 A 完成度 +5'
    if kind == 'A_items':
        mm = re.search(r'(\d+)\s*项', segs['A']['cell'])
        old = '%s 项' % mm.group(1)
        return text.replace(old, '%d 项' % (int(mm.group(1)) + 1), 1), '段 A 声明项数 +1'
    if kind == 'total_pct':
        old = '≈ %.0f%%' % p['total']['pct']
        return text.replace(old, '≈ %.0f%%' % (p['total']['pct'] - 4), 1), '合计 -4'
    if kind == 'calib_full':
        for row in p['calib']:
            if row['den'] == 'A+B+C+D':
                old = '%.0f%%' % row['pct']
                return text.replace(old, '%.0f%%' % (row['pct'] - 9), 1), '全量口径 -9'
        raise ValueError('找不到「全量 ROADMAP」行')
    if kind == 'A_expr':
        # 把段 A 的 `x/y = p%` 里的 p 改掉（算式仍可解析，但复算对不上）
        mm = re.search(r'([\d.]+)\s*/\s*([\d.]+)\s*=\s*([\d.]+)\s*%', segs['A']['cell'])
        if not mm:
            raise ValueError('段 A 没有 `x/y = p%` 形态的算式')
        new = '%s/%s = %.1f%%' % (mm.group(1), mm.group(2), float(mm.group(3)) + 6)
        return text.replace(mm.group(0), new, 1), '段 A 算式右边 +6'
    if kind == 'B_pass':
        mm = re.search(r'达标[^0-9]{1,24}?(\d+)\s*/\s*(\d+)', segs['B']['cell'])
        if not mm:
            raise ValueError('段 B 没有「达标 a/b」')
        new = '达标按 glm 记 **%d/%s**' % (int(mm.group(1)) + 1, mm.group(2))
        return text.replace(mm.group(0), new, 1), '段 B 达标 +1（分数变 8/8）'
    if kind == 'weight':
        old = '| %g%% |' % segs['A']['w']
        return text.replace(old, '| %g%% |' % (segs['A']['w'] - 5), 1), '段 A 权重 -5'
    if kind == 'C_expr':
        mm = re.search(r'[\d.]+\s*/\s*[\d.]+\s*=\s*[\d.]+\s*%', segs['C']['cell'])
        if not mm:
            raise ValueError('段 C 没有可删的算式')
        return text.replace(mm.group(0), '', 1), '删掉段 C 的算式'
    if kind == 'C_row':
        for k, v in p['sections'].items():
            if re.search(r'段\s*C', k):
                rows = [ln for ln in v.splitlines()
                        if re.match(r'^\|\s*C\d+[a-z]?\s*\|', ln)]
                if not rows:
                    raise ValueError('段 C 明细表没有行')
                return text.replace(rows[-1] + '\n', '', 1), '删掉段 C 明细表最后一行'
        raise ValueError('找不到段 C 小节')
    if kind == 'no_expr_token':
        for row in p['calib']:
            if row['den'] not in ('A', 'A+B+C+D') and NO_EXPR_TOKEN in ' '.join(row['raw']):
                return text.replace(NO_EXPR_TOKEN, '', 1), '去掉「无算式」标记'
        raise ValueError('没有标「无算式」的行可改')
    raise ValueError('未知变异 %s' % kind)


# (变异种类, 期望红的判据, 说明)
SELFTEST = [
    ('A_items', 'R4', '段 A 声明项数 +1 须红在 R4（分母 == 明细行数）'),
    ('C_row', 'R4', '删段 C 一行明细须红在 R4'),
    ('A_pct', 'R2', '段 A 完成度 +5 须红在 R2（合计复算）'),
    ('total_pct', 'R2', '合计显示 -4 须红在 R2'),
    ('calib_full', 'R3', '全量口径 -9 须红在 R3（同一个量的两处声明）'),
    ('no_expr_token', 'R3', '去掉「无算式」标记须红在 R3（豁免要写出来）'),
    ('A_expr', 'R5', '段 A 算式右边改错须红在 R5'),
    ('C_expr', 'R5', '删掉段 C 算式须红在 R5（缺算式也判红）'),
    ('B_pass', 'R6', '段 B 达标 7/8 写成 8/8 须红在 R6'),
    ('weight', 'R1', '段 A 权重 -5 须红在 R1（权重和 != 100）'),
]


def self_test(path=None):
    path = Path(path) if path else DEFAULT_ROADMAP
    base = path.read_text(encoding='utf-8')
    ok0, pr0, info0 = run_text(base)
    print('[T0] 原样                %s  %s' % ('ok ' if ok0 else 'FAIL', detail_str(ok0, pr0, info0)))
    bad = 0 if ok0 else 1
    if not ok0:
        print('     原样就该是绿的 —— 先修文档再跑自检（自检不是修文档的工具）')
        return False
    print('     T0 覆盖 %d 段明细、%d 行口径' % (len(info0['detail']), len(info0['uncovered']) + 2))
    for i, (kind, expect, desc) in enumerate(SELFTEST, start=1):
        try:
            mut, note = _mutate(base, kind)
        except Exception as e:
            print('[T%d] %-20s BAD!  变异锚点缺失：%r（锚点缺失判红不 skip）' % (i, kind, e))
            bad += 1
            continue
        if mut == base:
            print('[T%d] %-20s BAD!  变异没改到任何字节（%s）' % (i, kind, note))
            bad += 1
            continue
        ok1, pr1, _ = run_text(mut)
        hit = [x['id'] for x in pr1]
        good = (not ok1) and (expect in hit)
        if not good:
            bad += 1
        print('[T%d] %-20s %s  %s | 期望 %s 红，实得 %s'
              % (i, kind, 'ok ' if good else 'BAD!', note, expect, ','.join(hit) or '全绿'))
    print('\n自检：%d 向，BAD=%d' % (len(SELFTEST) + 1, bad))
    return bad == 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='ROADMAP 进度看板算术自洽闸')
    ap.add_argument('--file', default=None, help='指定 ROADMAP.md（默认仓库内那份）')
    ap.add_argument('--self-test', action='store_true', help='十向自检（断言红的是哪一条）')
    ap.add_argument('--json', default=None, help='把结果写成 JSON')
    a = ap.parse_args(argv)

    if a.self_test:
        ok = self_test(a.file)
        return 0 if ok else 1

    ok, probs, info = check_file(a.file)
    print('ROADMAP 自洽闸：%s' % ('ok' if ok else 'FAIL'))
    print('  ' + detail_str(ok, probs, info))
    for x in probs:
        print('  - %s %s' % (x['id'], x['msg']))
    if a.json:
        Path(a.json).write_text(json.dumps({'ok': ok, 'problems': probs, 'info': info},
                                           ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
