# -*- coding: utf-8 -*-
"""_l27c_make_l2_informative.py — 造「L2 层的信息完备题」卷（T-L27c）

为什么需要它（T-L27b 之后的下一步）
----------------------------------
v7 卷的 L2 层 **64 条全是 ec=1**（必缺一个字段），所以「纯列举 k-1 个键名」这条退化策略
在 L2 上永远有分可拿（按族 top2 = 31/64 = 48.4%，见 `l27b_ec0_probe.json`）。
T-L27b 已把判分器的 ec=0 分支补齐，并实测 **ec=0 题上穷举 0/59** ⇒ 题型能根治。
本脚本按老王 2026-11-04 拍板「**先 4 条最小链路**」造独立小卷；
2026-11-04 晚老王拍板「**方案 A：16 条（每族 4 条），只标 diagnostic**」⇒ 用
`--per-family 4` 造 v2。

  ★ 独立小卷，**不动** `tasks/tasks.jsonl`（S-52 冻结件）、**不动** SYS/v7/headline、
    **不进** L2 主分母 ⇒ 结果只能标 `diagnostic`，**不得与 v7 的 L2 分数并列或相减**（R54/R65）。
    这与 T-B2B5 的 `tasks_refuse_v1.jsonl` 同一形态。

派生规则（**可复现，不靠手挑**）
------------------------------
  ① 每族（wingbox / open_hole_panel / fuselage_barrel / stiffened_panel）取 per-family 条 L1 题；
  ② **按 split 轮转取**（v2 起）：
       按 `SPLIT_RANK = boundary_holdout > extrapolation_test > interpolation_test > val > train`
       给 split 排序，每个 split 内按 `task_id` 字典序；
       第 1 轮取每个有题的 split 的第 1 条，第 2 轮取第 2 条……直到凑满。
     ★ **为什么不直接取全局排序前 k 条**（v1 的做法）：`boundary_holdout` 在 wingbox 有 6 条、
       全排在最前 ⇒ 取 4 条会全落在同一个 split 上，测的是「同类结构的 4 个变体」，
       族级代表性是假的。轮转法让每族尽量覆盖多个 split。
     ★ **前 len(splits) 条包含 v1 那几条**（各轮的第 1 条即 v1 全局排序第 1 条）⇒
       **v1 ⊂ v2**，v1 的候选可直接复用，且构成一条天然的「同题跨卷一致」判据。
  ③ 派生字段：`input_level='L2'`；`task_id` 前缀 `L2i_`；`gates` 加 `clarify_then_semantics`；
     `expected_clarifications = []`；`input.spec_normalized` 取 L1 的**完整** spec 并去掉
     `description`（与现有 L2 题同形，避免题面额外提示）；
  ④ 保留 `truth_ref` / `geometry_class` / `split_v2` / `family` 不动 ⇒ spec 保真判分可直接复用。

断言（不满足就 rc=1，不产出卷）
------------------------------
  · 条数 == per_family × 4，每族恰好 per_family 条，无重复 task_id；
  · **族内 spec_normalized 两两不等**（否则两条题实质重复 ⇒ 分母虚增。v1 只有 4 条看不出来，
    v2 16 条必须先查）；
  · 每条的 `input.spec_normalized` 与源 L1 题**除 description 外逐键相等**（防手抖改坏参数）；
  · `expected_clarifications` 必须为空、`input_level` 必须 L2；
  · `truth_ref` 指向的文件必须真实存在（否则判分时会静默变 spec_bad）；
  · **v1 ⊂ v2**（per_family > 1 且 v1 存在时）：v1 的每条在 v2 里**逐字段相同**
    —— 只证「旧的不丢」不够，还要构成「新增只许是新增」的纯增量关系。

用法：
    "$PY" _l27c_make_l2_informative.py                     # v1：每族 1 条 -> tasks_l2_informative_v1.jsonl
    "$PY" _l27c_make_l2_informative.py --per-family 4 --out tasks/tasks_l2_informative_v2.jsonl
    "$PY" _l27c_make_l2_informative.py --check --per-family 4 --out <卷>   # 只校验（不写盘）
退出码：0 ok ／ 1 断言失败 ／ 2 环境错误
"""
import argparse
import collections
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'tasks', 'tasks.jsonl')
V1 = os.path.join(HERE, 'tasks', 'tasks_l2_informative_v1.jsonl')
OUT = V1
# ★ truth_ref 相对 **数据仓** 解析（与 evaluate.py 的 FEA 同一口径），不是相对 feagpt_repro/
DATA_ROOT = os.path.normpath(os.path.join(HERE, '..', 'FEM-Bench-Aero'))

FAMILIES = ('wingbox', 'open_hole_panel', 'fuselage_barrel', 'stiffened_panel')
SPLIT_RANK = {'boundary_holdout': 0, 'extrapolation_test': 1,
              'interpolation_test': 2, 'val': 3, 'train': 4}


def load(path):
    return [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]


def pick(fam, rows, k):
    """按 split 轮转取 k 条（规则与当天数据无关，只看 task_id 与 split 标签）。"""
    cand = [r for r in rows if r['input_level'] == 'L1' and r['family'] == fam]
    if not cand:
        raise SystemExit('[FATAL] 族 %s 在 L1 层没有题' % fam)
    by_split = collections.defaultdict(list)
    for r in cand:
        by_split[r.get('split_v2')].append(r)
    order = sorted(by_split, key=lambda s: (SPLIT_RANK.get(s, 99), str(s)))
    for s in order:
        by_split[s].sort(key=lambda r: r['task_id'])
    out, rnd = [], 0
    while len(out) < k:
        added = 0
        for s in order:
            if rnd < len(by_split[s]):
                out.append(by_split[s][rnd])
                added += 1
                if len(out) >= k:
                    break
        if added == 0:
            raise SystemExit('[FATAL] 族 %s 的 L1 题池只有 %d 条，不够 %d 条'
                             % (fam, len(cand), k))
        rnd += 1
    return out


def derive(src):
    spec = json.loads(json.dumps(src['input']['spec_normalized']))   # 深拷贝
    spec.pop('description', None)
    gates = list(src.get('gates') or [])
    if 'clarify_then_semantics' not in gates:
        gates = ['clarify_then_semantics'] + gates
    return {
        'task_id': 'L2i_' + src['task_id'][3:],          # L1_xxx -> L2i_xxx
        'input_level': 'L2',
        'family': src['family'],
        'geometry_class': src['geometry_class'],
        'input_source': src.get('input_source'),
        'split_v2': src.get('split_v2'),
        'gates': gates,
        'truth_ref': src['truth_ref'],
        'expected_clarifications': [],
        'input': {'spec_normalized': spec},
        'input_from': src['task_id'],                     # 溯源：派生自哪条 L1 题
    }


def verify(rows_out, rows_src, per_family, v1_rows=None):
    """独立复算：不看生成过程，只按契约核卷。"""
    bad = []
    n_exp = per_family * len(FAMILIES)
    if len(rows_out) != n_exp:
        bad.append('条数 %d != %d' % (len(rows_out), n_exp))
    per = collections.Counter(r['family'] for r in rows_out)
    for f in FAMILIES:
        if per.get(f, 0) != per_family:
            bad.append('族 %s 有 %d 条 != %d' % (f, per.get(f, 0), per_family))
    ids = [r['task_id'] for r in rows_out]
    if len(set(ids)) != len(ids):
        bad.append('task_id 重复')
    byid = {r['task_id']: r for r in rows_src}

    # ★ 族内 spec 重复 = 两条题实质相同 ⇒ 分母虚增（v1 只 4 条看不出来，16 条必须先查）
    seen = {}
    for r in rows_out:
        k = json.dumps(r['input']['spec_normalized'], sort_keys=True, ensure_ascii=False)
        if k in seen:
            bad.append('spec 完全重复：%s 与 %s' % (seen[k], r['task_id']))
        else:
            seen[k] = r['task_id']

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

    # ★ v1 ⊂ v2：纯增量关系（旧的一条不丢、一条不改）
    #   ★★ **双向**：只遍历 v1 去 v2 里找是「核了一半」—— v1 自己少一条时，那条就不再被
    #      遍历 ⇒ 断言会静默失效（2026-11-04 实测：删掉 v1 一条，本函数返回 [] 全绿）。
    #      所以先核 **v1 自身的契约**（每族 1 条、共 4 条），再核每条在 v2 里逐字段相同。
    if v1_rows is not None:
        per1 = collections.Counter(r['family'] for r in v1_rows)
        if len(v1_rows) != len(FAMILIES):
            bad.append('基线 v1 自身条数 %d != %d（v1 被删过？基线不完整则本断言无效）'
                       % (len(v1_rows), len(FAMILIES)))
        for f in FAMILIES:
            if per1.get(f, 0) != 1:
                bad.append('基线 v1 的族 %s 有 %d 条 != 1（v1 契约是每族 1 条）'
                           % (f, per1.get(f, 0)))
        cur = {r['task_id']: r for r in rows_out}
        for old in v1_rows:
            got = cur.get(old['task_id'])
            if got is None:
                bad.append('v1 的 %s 在 v2 里丢了' % old['task_id'])
            elif json.dumps(got, sort_keys=True) != json.dumps(old, sort_keys=True):
                bad.append('v1 的 %s 在 v2 里被改了（应逐字段相同）' % old['task_id'])
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--per-family', type=int, default=1)
    ap.add_argument('--out', default=None)
    a = ap.parse_args(argv)
    out_path = a.out or OUT
    k = a.per_family
    if k < 1:
        print('[FATAL] --per-family 必须 >= 1')
        return 2

    rows_src = load(SRC)
    # v1 只在「当前这一份不是 v1」时作为增量基线
    v1_rows = None
    if k > 1 and os.path.exists(V1) and os.path.abspath(V1) != os.path.abspath(out_path):
        v1_rows = load(V1)

    if a.check:
        if not os.path.exists(out_path):
            print('[FATAL] 卷不存在：%s' % out_path)
            return 2
        rows_out = load(out_path)
        bad = verify(rows_out, rows_src, k, v1_rows)
        sha = hashlib.sha256(open(out_path, 'rb').read()).hexdigest()
        if bad:
            print('[FAIL] 校验不通过：')
            for b in bad:
                print('  -', b)
            return 1
        print('[ok ] %s：%d 条（每族 %d）、ec 全空、spec 与源题一致、族内无重复、truth 全在%s；sha256=%s'
              % (os.path.basename(out_path), len(rows_out), k,
                 '、v1 ⊂ 本卷逐字段相同' if v1_rows else '', sha[:12]))
        return 0

    out = []
    for fam in FAMILIES:
        for src in pick(fam, rows_src, k):
            out.append(derive(src))
            print('  %-16s <- %-46s split=%s' % (fam, src['task_id'], src.get('split_v2')))
    bad = verify(out, rows_src, k, v1_rows)
    if bad:
        print('[FAIL] 生成结果不自洽，未写盘：')
        for b in bad:
            print('  -', b)
        return 1
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        for t in out:
            f.write(json.dumps(t, ensure_ascii=False, sort_keys=True) + '\n')
    sha = hashlib.sha256(open(out_path, 'rb').read()).hexdigest()
    cnt = collections.Counter((r['family'], r['split_v2']) for r in out)
    print('\n-> %s\n   %d 条；sha256=%s' % (out_path, len(out), sha))
    for fam in FAMILIES:
        d = {s: c for (f, s), c in cnt.items() if f == fam}
        print('   %-16s split 覆盖 %d 种 %s' % (fam, len(d), d))
    return 0


if __name__ == '__main__':
    sys.exit(main())
