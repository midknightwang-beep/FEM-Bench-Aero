#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""k 遍多数表决（T-B2B5 v4）—— 把「单次抖动」压成「稳定判定」

★ 为什么不能直接对 verdict 取众数
  3 票可能出现 1/1/1（refuse_correct + build_correct + ctl_no_output），众数无解；
  更根本的是：**「拒绝」与「不拒绝」是二元决策，细分 verdict 只是它的下挂标签**。
  所以两级表决：① 一级判「是否拒绝」是否过半；② 二级在同类的票里定细分。
  两级都平票时**取保守值**（refuse 侧记 refuse_multi、no_refuse 侧记 build_fail），
  宁可少算分，不许多算分。

★ 为什么必须复用 judge_refuse.agg
  指标口径（分母、过拒率、quotable_alone）只允许有一处实现 —— 第二处实现就是 bug。
  本脚本只负责「把 k 遍 rows 合成一遍 rows」，**判分逻辑与指标全部 import 过来**。

用法：
    python judge_refuse_majority.py --reps d1,d2,d3 --json out.json
    python judge_refuse_majority.py --self-test
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge_refuse as J   # noqa: E402  判分与指标的唯一实现

#: 一级二元化：哪些 verdict 表示「模型确实拒绝了」
#: ★ over_refuse 必须归 'refuse' —— 它就是对话题被拒；归成 no_refuse 会把
#:   过拒算成「建对了」，这是把最该抓的错洗成正确（自检 T7 守这一条）。
REFUSE_CLASS = ('refuse_correct', 'refuse_wrong', 'refuse_multi', 'over_refuse')

#: 一级二元化：模型没拒，试图建（或什么都没输出以外的情形）
NO_REFUSE_CLASS = ('silent_build', 'build_correct', 'build_fail', 'clarified', 'ctl_clarified')

#: 无效票：没有可用输出（不可归因于「会不会拒」）
INVALID_CLASS = ('no_output', 'ctl_no_output', 'llm_error', 'ctl_llm_error')

#: 二级平票时的保守选择（越小越保守）
CONSERVATIVE = {
    'refuse': ['refuse_multi', 'refuse_wrong', 'refuse_correct'],
    'no_refuse': ['build_fail', 'ctl_clarified', 'clarified', 'silent_build', 'build_correct'],
}


def to_binary(v):
    if v in REFUSE_CLASS:
        return 'refuse'
    if v in NO_REFUSE_CLASS:
        return 'no_refuse'
    if v in INVALID_CLASS:
        return 'invalid'
    # 未知 verdict 一律当无效票 —— 不猜（猜等于替模型开脱）
    return 'invalid'


def counted_of(v):
    """counted 只从 VERDICT_TABLE 取，不在这里另立一套。"""
    return J.VERDICT_TABLE.get(v, (None, False, None))[1]


def majority_verdict(verdicts):
    """k 遍 verdict -> (合成 verdict, 明细)。k 为奇数时必有解，偶数可能平票。"""
    n = len(verdicts)
    if n == 0:
        return 'undecided', {'bins': [], 'note': '无票'}

    # ★★ 三票全同 ⇒ **原样返回**（短路）。
    #   不短路就会出这一类错：三遍都不输出（ctl_no_output）被二元化判成
    #   invalid×3 ⇒ 「无过半票」⇒ undecided。可是「一致地没有输出」是一种
    #   **一致的失败**，不是「判不了」；按 R-A5 它记 0 但仍以原名入账。
    #   这条同时保证自比 A==A：同一批候选跑三遍必须逐条等于单遍。
    if len(set(verdicts)) == 1:
        return verdicts[0], {'bins': [to_binary(verdicts[0])] * n, 'unanimous': True}

    bins = [to_binary(v) for v in verdicts]
    cnt = {b: bins.count(b) for b in ('refuse', 'no_refuse', 'invalid')}

    # ---- 一级：是否拒绝，必须严格过半 ----
    win = None
    for b in ('refuse', 'no_refuse'):
        if cnt[b] * 2 > n:
            win = b
            break
    if win is None:
        return 'undecided', {'bins': bins, 'counts': cnt,
                             'note': '无过半票（invalid 占比过高或平票）'}

    # ---- 二级：在同类的票里定细分 verdict ----
    same = [v for v, b in zip(verdicts, bins) if b == win]
    l2 = {}
    for v in same:
        l2[v] = l2.get(v, 0) + 1
    best = max(l2.values())
    top = sorted([v for v, k in l2.items() if k == best])
    if len(top) == 1:
        return top[0], {'bins': bins, 'counts': cnt, 'level2': l2}

    # 平票：按保守序取第一个（宁可少算分）
    for cand in CONSERVATIVE[win]:
        if cand in top:
            return cand, {'bins': bins, 'counts': cnt, 'level2': l2, 'tie': top,
                          'resolved_by': 'conservative'}
    return top[0], {'bins': bins, 'counts': cnt, 'level2': l2, 'tie': top}


def merge(reps_rows, tasks):
    """把 k 遍 rows 合成一遍。返回 (rows, notes)。"""
    by_rep = []
    for rows in reps_rows:
        by_rep.append({r['task_id']: r for r in rows})
    ids = [t['task_id'] for t in tasks]
    # ★ 题数守恒：任何一遍漏了题都要先报出来，不能悄悄少算
    for i, d in enumerate(by_rep):
        missing = [x for x in ids if x not in d]
        if missing:
            raise SystemExit('第 %d 遍缺 %d 题：%s' % (i + 1, len(missing), missing[:5]))

    out = []
    for t in tasks:
        tid = t['task_id']
        votes = [d[tid]['verdict'] for d in by_rep]
        v, det = majority_verdict(votes)
        base = by_rep[0][tid]
        out.append({
            'task_id': tid,
            'kind': t['kind'],
            'refuse_type': t.get('refuse_type'),
            'anchor': t.get('anchor'),
            'verdict': v,
            'counted': counted_of(v),
            'counted_from_table': True,
            'votes': votes,
            'vote_detail': det,
        })
    return out, {'n_reps': len(reps_rows), 'n_tasks': len(ids)}


# ---------------------------------------------------------------------------
# 自检：每一条都对应一个「写错了会静默出好数」的分支
# ---------------------------------------------------------------------------
def self_test():
    T = []

    def chk(name, got, want):
        T.append((name, got == want, got, want))

    # T1 三票一致
    chk('T1 一致取原值', majority_verdict(['refuse_correct'] * 3)[0], 'refuse_correct')
    chk('T2 一致(对照)', majority_verdict(['build_correct'] * 3)[0], 'build_correct')

    # T3 2:1 越界侧
    chk('T3 2:1 多数',
        majority_verdict(['refuse_correct', 'refuse_correct', 'silent_build'])[0], 'refuse_correct')

    # T4 二级 2:1（都是 refuse，但细分不同）
    chk('T4 二级多数',
        majority_verdict(['refuse_correct', 'refuse_correct', 'refuse_multi'])[0], 'refuse_correct')

    # T5 二级平票 -> 保守（refuse_multi 而非 refuse_correct）
    # ★ T5 原名叫「二级平票」，但用例 refuse_multi 2:1 其实是**明确多数** ——
    #   名字与用例说反了，NC-77 的变异因此红在 T5b 而不是 T5，才被照出来。
    chk('T5 二级明确多数',
        majority_verdict(['refuse_correct', 'refuse_multi', 'refuse_multi'])[0], 'refuse_multi')
    chk('T5b 二级平票取保守',
        majority_verdict(['refuse_correct', 'refuse_multi', 'ctl_no_output'])[0], 'refuse_multi')

    # T6 一级平票 -> undecided（不许硬判成通过）
    chk('T6 一级平票',
        majority_verdict(['refuse_correct', 'build_correct', 'ctl_no_output'])[0], 'undecided')

    # T7 over_refuse 必须归 'refuse' —— 归错会把过拒洗成建对
    chk('T7 over_refuse 归 refuse 类', to_binary('over_refuse'), 'refuse')
    chk('T7b 三票 over_refuse',
        majority_verdict(['over_refuse'] * 3)[0], 'over_refuse')

    # T8 无效票占多数但仍分裂 -> undecided
    #    原用例是「三票全无输出」，现在按 T13 短路成原判（一致的失败 ≠ 判不了）；
    #    真正该 undecided 的是「两遍没有输出、一遍拒绝」这种**说不清**的票型。
    chk('T8 无效票多数且分裂',
        majority_verdict(['ctl_no_output', 'ctl_no_output', 'refuse_correct'])[0], 'undecided')
    chk('T8b 一致无输出不算通过',
        counted_of(majority_verdict(['ctl_no_output'] * 3)[0]), False)

    # T9 counted 只从 VERDICT_TABLE 取
    chk('T9 counted(refuse_correct)', counted_of('refuse_correct'), True)
    chk('T9b counted(silent_build)', counted_of('silent_build'), False)
    chk('T9c counted(over_refuse) 必须 False', counted_of('over_refuse'), False)
    chk('T9d 未知 verdict 记 False', counted_of('__nope__'), False)

    # T10 undecided 的 counted 必须 False（不能白送分）
    chk('T10 undecided 不算通过', counted_of('undecided'), False)

    # T13 三票一致时**必须原样返回**（自比 A==A 的根）
    #    首版没这条：ctl_no_output×3 被二元化成 invalid×3 -> undecided，
    #    于是「同一目录跑三遍」≠「跑一遍」，NC-77 的自比当场红。
    chk('T13 一致无输出保持原判',
        majority_verdict(['ctl_no_output'] * 3)[0], 'ctl_no_output')
    chk('T13b 一致静默保持原判',
        majority_verdict(['silent_build'] * 3)[0], 'silent_build')
    chk('T13c 一致 refuse_multi 保持',
        majority_verdict(['refuse_multi'] * 3)[0], 'refuse_multi')

    # T11 合并后题数守恒 + 分母不变（构造最小样本）
    fake_tasks = [{'task_id': 'A', 'kind': 'refuse', 'refuse_type': 'geometry', 'anchor': 'x'},
                  {'task_id': 'B', 'kind': 'build', 'refuse_type': None, 'anchor': None}]
    rep = [{'task_id': 'A', 'verdict': 'refuse_correct', 'kind': 'refuse'},
           {'task_id': 'B', 'verdict': 'build_correct', 'kind': 'build'}]
    rows, meta = merge([rep, rep, rep], fake_tasks)
    chk('T11 题数守恒', len(rows), 2)
    chk('T11b 越界分母', len([r for r in rows if r['kind'] == 'refuse']), 1)
    chk('T11c 对照分母', len([r for r in rows if r['kind'] == 'build']), 1)

    # T12 指标必须走 J.agg —— 构造 3 条越界全对、2 条对照全过拒
    T12_tasks = ([{'task_id': 'R%d' % i, 'kind': 'refuse', 'refuse_type': 'g', 'anchor': 'x'}
                  for i in range(3)] +
                 [{'task_id': 'C%d' % i, 'kind': 'build', 'refuse_type': None, 'anchor': None}
                  for i in range(2)])
    rv = {'R0': 'refuse_correct', 'R1': 'refuse_correct', 'R2': 'refuse_correct',
          'C0': 'over_refuse', 'C1': 'build_correct'}
    one = [{'task_id': k, 'verdict': v, 'kind': ('refuse' if k[0] == 'R' else 'build')}
           for k, v in rv.items()]
    rows12, _ = merge([one, one, one], T12_tasks)
    s12 = J.agg(rows12)
    chk('T12 越界全对 100%', s12['refuse']['pct'], 100.0)
    chk('T12b 过拒 1/2 = 50%', s12['kpi']['over_refuse_pct'], 50.0)
    chk('T12c 过拒 50% > 10% 不得单独引用', s12['kpi']['quotable_alone'], False)
    chk('T12d 建对率 1/2 = 50%', s12['kpi']['build_correct_pct'], 50.0)

    bad = [t for t in T if not t[1]]
    for name, ok, got, want in T:
        print('  [%s] %-32s got=%r want=%r' % ('ok  ' if ok else 'FAIL', name, got, want))
    print('自检 %d 向，BAD=%d' % (len(T), len(bad)))
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reps', default='', help='逗号分隔的 k 个候选目录（k>=3，奇数优先）')
    ap.add_argument('--tasks', default=J.TASKS)
    ap.add_argument('--json', default='')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()

    if a.self_test:
        sys.exit(self_test())

    dirs = [d.strip() for d in a.reps.split(',') if d.strip()]
    if len(dirs) < 2:
        sys.exit('--reps 至少两个目录')
    if len(dirs) % 2 == 0:
        print('⚠️ 目录数为偶数（%d），可能出现平票；平票一律记 undecided（不算通过）' % len(dirs))

    reps_rows, summaries, tasks = [], [], None
    for d in dirs:
        if not os.path.isdir(d):
            sys.exit('目录不存在：%s' % d)
        rows, summ, tasks = J.run(d, a.tasks)
        reps_rows.append(rows)
        summaries.append({'dir': d, 'refuse_pct': summ['refuse']['pct'],
                          'over_refuse_pct': summ['kpi']['over_refuse_pct'],
                          'prompt_sha': J._prompt_sha_of(d)})
        print('  第 %d 遍 %-42s 拒 %5.1f%%  过拒 %5.1f%%' % (
            len(reps_rows), os.path.basename(d.rstrip('/\\')),
            summ['refuse']['pct'], summ['kpi']['over_refuse_pct']))

    # R53：各遍 prompt 必须同源，否则「多数表决」混的是两份题面
    shas = {s['prompt_sha'] for s in summaries}
    if len(shas) > 1:
        sys.exit('✗ 各遍 prompt sha 不同 %s ⇒ 不可合并（R53）' % shas)

    rows, meta = merge(reps_rows, tasks)
    summary = J.agg(rows)          # ★ 指标只走这一处实现
    und = [r['task_id'] for r in rows if r['verdict'] == 'undecided']

    out = {
        'purpose': 'T-B2B5 v4：k 遍多数表决（两级表决，指标复用 judge_refuse.agg）',
        'reps': summaries,
        'n_reps': meta['n_reps'],
        'n_tasks': meta['n_tasks'],
        'prompt_sha': list(shas)[0] if len(shas) == 1 else None,
        'summary': summary,
        'undecided': und,
        'rows': rows,
    }
    print()
    print('  多数表决后：拒 %d/%d = %.1f%%  过拒 %d/%d = %.1f%%  建对 %.1f%%' % (
        summary['refuse']['pass'], summary['refuse']['counted'], summary['refuse']['pct'],
        summary['build']['verdicts'].get('over_refuse', 0), summary['build']['counted'],
        summary['kpi']['over_refuse_pct'], summary['kpi']['build_correct_pct']))
    print('  KPI：达标=%s  可单独引用=%s  undecided=%d 条' % (
        summary['kpi']['target_met'], summary['kpi']['quotable_alone'], len(und)))
    if und:
        print('  undecided：%s' % und)

    if a.json:
        with io.open(a.json, 'w', encoding='utf-8', newline='') as f:
            f.write(json.dumps(out, ensure_ascii=False, indent=1))
            f.write('\n')
        print('  -> %s' % a.json)


if __name__ == '__main__':
    main()
