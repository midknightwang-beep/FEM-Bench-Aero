# -*- coding: utf-8 -*-
"""_l27c_make_l2_informative.py — 造「L2 层的信息完备题」最小卷（T-L27c，4 条）

为什么需要它（T-L27b 之后的下一步）
----------------------------------
v7 卷的 L2 层 **64 条全是 ec=1**（必缺一个字段），所以「纯列举 k-1 个键名」这条退化策略
在 L2 上永远有分可拿（按族 top2 = 31/64 = 48.4%，见 `l27b_ec0_probe.json`）。
T-L27b 已把判分器的 ec=0 分支补齐，并实测 **ec=0 题上穷举 0/59** ⇒ 题型能根治。
本脚本按老王 2026-11-04 拍板「**先 4 条最小链路**」造一份**独立小卷**：

  ★ 独立小卷，**不动** `tasks/tasks.jsonl`（S-52 冻结件）、**不动** SYS/v7/headline、
    **不进** L2 主分母 ⇒ 结果只能标 `diagnostic`，**不得与 v7 的 L2 分数并列或相减**（R54/R65）。
    这与 T-B2B5 的 `tasks_refuse_v1.jsonl` 同一形态。

派生规则（**可复现，不靠手挑**）
------------------------------
  ① 每族（wingbox / open_hole_panel / fuselage_barrel / stiffened_panel）各取 **1 条** L1 题；
  ② 取哪条按 split 优先级 `boundary_holdout > extrapolation_test > interpolation_test > val > train`，
     同 split 内按 `task_id` 字典序取第一条 ⇒ 优先 OOD（更难暴露问题），且规则与当天数据无关；
  ③ 派生字段：`input_level='L2'`；`task_id` 前缀 `L2i_`；`gates` 加 `clarify_then_semantics`；
     `expected_clarifications = []`；`input.spec_normalized` 取 L1 的**完整** spec 并去掉
     `description`（与现有 L2 题同形，避免题面额外提示）；
  ④ 保留 `truth_ref` / `geometry_class` / `split_v2` / `family` 不动 ⇒ spec 保真判分可直接复用。

断言（不满足就 rc=1，不产出卷）
------------------------------
  · 4 条题、4 个族各 1 条，无重复 task_id；
  · 每条的 `input.spec_normalized` 与源 L1 题**除 description 外逐键相等**（防手抖改坏参数）；
  · `expected_clarifications` 必须为空、`input_level` 必须 L2；
  · `truth_ref` 指向的文件必须真实存在（否则判分时会静默变 spec_bad）。

用法：
    "$PY" _l27c_make_l2_informative.py            # 写 tasks/tasks_l2_informative_v1.jsonl
    "$PY" _l27c_make_l2_informative.py --check    # 只校验已有卷（不写盘）
退出码：0 ok ／ 1 断言失败 ／ 2 环境错误
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'tasks', 'tasks.jsonl')
OUT = os.path.join(HERE, 'tasks', 'tasks_l2_informative_v1.jsonl')
# ★ truth_ref 相对 **数据仓** 解析（与 evaluate.py 的 FEA 同一口径），不是相对 feagpt_repro/
DATA_ROOT = os.path.normpath(os.path.join(HERE, '..', 'FEM-Bench-Aero'))

FAMILIES = ('wingbox', 'open_hole_panel', 'fuselage_barrel', 'stiffened_panel')
SPLIT_RANK = {'boundary_holdout': 0, 'extrapolation_test': 1,
              'interpolation_test': 2, 'val': 3, 'train': 4}


def load(path):
    return [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]


def derive_one(fam, rows):
    cand = [r for r in rows if r['input_level'] == 'L1' and r['family'] == fam]
    if not cand:
        raise SystemExit('[FATAL] 族 %s 在 L1 层没有题' % fam)
    cand.sort(key=lambda r: (SPLIT_RANK.get(r.get('split_v2'), 99), r['task_id']))
    src = cand[0]
    spec = json.loads(json.dumps(src['input']['spec_normalized']))   # 深拷贝
    spec.pop('description', None)
    gates = list(src.get('gates') or [])
    if 'clarify_then_semantics' not in gates:
        gates = ['clarify_then_semantics'] + gates
    t = {
        'task_id': 'L2i_' + src['task_id'][3:],          # L1_xxx -> L2i_xxx
        'input_level': 'L2',
        'family': fam,
        'geometry_class': src['geometry_class'],
        'input_source': src.get('input_source'),
        'split_v2': src.get('split_v2'),
        'gates': gates,
        'truth_ref': src['truth_ref'],
        'expected_clarifications': [],
        'input': {'spec_normalized': spec},
        'input_from': src['task_id'],                     # 溯源：派生自哪条 L1 题
    }
    return t, src


def verify(rows_out, rows_src):
    """独立复算：不看生成过程，只按契约核卷。"""
    bad = []
    if len(rows_out) != 4:
        bad.append('条数 %d != 4' % len(rows_out))
    if sorted(r['family'] for r in rows_out) != sorted(FAMILIES):
        bad.append('族不是各 1 条：%s' % [r['family'] for r in rows_out])
    ids = [r['task_id'] for r in rows_out]
    if len(set(ids)) != len(ids):
        bad.append('task_id 重复')
    byid = {r['task_id']: r for r in rows_src}
    for r in rows_out:
        if r['expected_clarifications']:
            bad.append('%s: expected_clarifications 非空' % r['task_id'])
        if r['input_level'] != 'L2':
            bad.append('%s: input_level != L2' % r['task_id'])
        src = byid.get(r.get('input_from'))
        if not src:
            bad.append('%s: input_from 指不到源题' % r['task_id'])
            continue
        a = json.loads(json.dumps(src['input']['spec_normalized']))
        a.pop('description', None)
        if a != r['input']['spec_normalized']:
            bad.append('%s: spec 与源题除 description 外不相等' % r['task_id'])
        if not os.path.exists(os.path.join(DATA_ROOT, r['truth_ref'])):
            bad.append('%s: truth_ref 不存在 %s' % (r['task_id'], r['truth_ref']))
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args(argv)

    rows_src = load(SRC)
    if a.check:
        if not os.path.exists(OUT):
            print('[FATAL] 卷不存在：%s' % OUT)
            return 2
        rows_out = load(OUT)
        bad = verify(rows_out, rows_src)
        sha = hashlib.sha256(open(OUT, 'rb').read()).hexdigest()
        if bad:
            print('[FAIL] 校验不通过：')
            for b in bad:
                print('  -', b)
            return 1
        print('[ok ] %s：4 条（每族 1）、ec 全空、spec 与源题一致、truth 全在；sha256=%s'
              % (os.path.basename(OUT), sha[:12]))
        return 0

    out = []
    for fam in FAMILIES:
        t, src = derive_one(fam, rows_src)
        out.append(t)
        print('  %-16s <- %-46s split=%-18s' % (fam, src['task_id'], src.get('split_v2')))
    bad = verify(out, rows_src)
    if bad:
        print('[FAIL] 生成结果不自洽，未写盘：')
        for b in bad:
            print('  -', b)
        return 1
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        for t in out:
            f.write(json.dumps(t, ensure_ascii=False, sort_keys=True) + '\n')
    sha = hashlib.sha256(open(OUT, 'rb').read()).hexdigest()
    print('-> %s\n   4 条；sha256=%s' % (OUT, sha))
    return 0


if __name__ == '__main__':
    sys.exit(main())
