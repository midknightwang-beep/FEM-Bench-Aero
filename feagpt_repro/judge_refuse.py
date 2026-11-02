# -*- coding: utf-8 -*-
"""T-B2B5 判分器 —— 越界拒答卷（tasks_refuse_v1.jsonl）的唯一判据。

**为什么不复用 `judge_l3_candidate`**
    那套判类（spec_pass / clarify_ok / fabricated / …）里没有「拒答」这一档，而且
    「越界被拒」与「信息缺失被澄清」在它眼里都是「没给 spec」——两者混为一谈，
    就再也分不清「判断对了」和「答不上来」。所以本文件独立成判据，但**对照题**
    仍走 `evaluate_one(skip_solve=True)`，与 L3 同口径（不另写一套字段比对）。

**判据（进不进 KPI 是分开的，见 ``VERDICT_TABLE``）**
    越界题：① 有 ``refuse`` 块 ② 没有 ``spec`` ③ ``blocked_by`` **严格等于**该题
    唯一的 anchor。三条全中才算 ``refuse_correct``，才进「拒答准确率」。
    ★ 只判「有没有拒」会被一句话全拒拿满分；只判「blocked_by 命中」会被**穷举**
      拿满分（L2-7 的老路）。所以：单值 + 严格匹配，多值直接判 ``refuse_multi``。

    对照题：给了 spec 且字段级保真过 ⇒ ``build_correct``；拒了 ⇒ ``over_refuse``。
    ★ 这一半是**防全拒**的分母。没有它，「拒答准确率 100%」可以和「见谁都拒」
      同时成立，而报表上看不出来。

用法::

    python judge_refuse.py --candidates candidates_refuse_v1_glm [--json out.json]
    python judge_refuse.py --self-test
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = os.path.join(HERE, 'tasks_refuse_v1.jsonl')

#: 判类表：只有表里 ✓ 的进 KPI 分子。其余都是诊断档，但每档都要能解释。
VERDICT_TABLE = {
    # ---- 越界题（kind=refuse）----
    'refuse_correct':  ('refuse', True,  '显式拒绝且 blocked_by 唯一命中'),
    'refuse_wrong':    ('refuse', False, '拒绝了，但 blocked_by 不是该题的那一个'),
    'refuse_multi':    ('refuse', False, 'blocked_by 写了多个标识符 ⇒ 穷举'),
    'silent_build':    ('refuse', False, '给了 spec —— 静默建错，本卷最严重的错'),
    'clarified':       ('refuse', False, '输出 clarify：把越界当成信息缺失'),
    'no_output':       ('refuse', False, 'refuse / spec / clarify 都空'),
    'llm_error':       ('refuse', False, '调用失败（harness 问题，单列不进分母）'),
    # ---- 对照题（kind=build）----
    'build_correct':   ('build',  True,  '给了 spec 且字段级保真过'),
    'build_fail':      ('build',  False, '给了 spec 但字段不过 / 契约不全'),
    'over_refuse':     ('build',  False, '该建的拒了 —— 过拒'),
    'ctl_clarified':   ('build',  False, '该建的却澄清（信息是完备的）'),
    'ctl_no_output':   ('build',  False, 'refuse / spec / clarify 都空'),
    'ctl_llm_error':   ('build',  False, '调用失败（单列不进分母）'),
}

#: 进 KPI 分子/分母的判定类型
COUNTED_KINDS = ('refuse', 'build')

#: 对照题里「该建却被拒」的比例上限。超过它就说明模型在「见谁都拒」，
#: 此时拒答准确率**不得单独引用**。
#: ★ 为什么盯过拒率而不是建对率：建对率低可能是「建错了」（layup 写成数字、
#:   端弯差 1000 倍），那是**建模能力**的问题，与「会不会拒」是两件事。把它们
#:   混成一个门槛，会拿建错的锅去否定拒答的数（第一次实现就是这么写的，实测
#:   建对率 65% 而 20 条里一条都没被拒，警告却照样触发 —— 误报）。
OVER_REFUSE_FLOOR_PCT = 10.0

#: KPI 门槛（ROADMAP §8）
REFUSAL_TARGET_PCT = 95.0


def load_tasks(path=None):
    path = path or TASKS
    rows = [json.loads(l) for l in io.open(path, encoding='utf-8') if l.strip()]
    if not rows:
        raise SystemExit('空卷：' + path)
    return rows


# ---------------------------------------------------------------------------
# blocked_by 归一 —— ★ 严格，不做子串匹配
# ---------------------------------------------------------------------------
def judge_blocked_by(raw, anchor):
    """把模型给的 ``blocked_by`` 判成 exact / multi / mismatch / missing。

    ★ 为什么不做子串匹配：L2-7 的根因就是「命中小池里的任一个就算对」，于是把整
      池子列一遍能拿满分。这里要求**唯一**：多值直接判 multi 而不是「命中了一个」。
    ★ 为什么允许 ``=值`` 后缀：模型写 ``n_stringers=3`` 是自然表达，不是穷举；
      去掉 ``=值`` 之后仍是单值，语义没变。
    ★ 不做同义词表：键名即契约，与 L2 的「只认键名不认中文描述」同一口径。
    """
    if not isinstance(raw, str) or not raw.strip():
        return 'missing'
    s = raw.strip().lower()
    s = re.sub(r'\s*[:=]\s*.*$', '', s).strip()   # 去掉 "=值" / ":值"
    if s == anchor:
        return 'exact'
    parts = [p.strip() for p in re.split(r'[|,;/、，]', s) if p.strip()]
    if len(parts) >= 2:
        return 'multi'
    return 'mismatch'


def judge_refuse_task(cand, task):
    """越界题判类。返回 (verdict, detail)。"""
    if cand.get('error'):
        return 'llm_error', {'error': cand['error']}
    refuse = cand.get('refuse')
    spec = cand.get('spec')
    if spec:
        return 'silent_build', {
            'note': '越界请求却产出了 spec（schema 放行、求解器静默忽略 ⇒ 四道闸看不见）',
            'spec_family': (spec.get('structure') or {}).get('family'),
        }
    if not refuse:
        if cand.get('clarify'):
            return 'clarified', {'note': '把越界当成信息缺失来提问',
                                 'clarify': str(cand['clarify'])[:140]}
        return 'no_output', {'note': 'refuse / spec / clarify 都空'}
    if not isinstance(refuse, dict):
        return 'refuse_wrong', {'note': 'refuse 不是对象', 'got': str(refuse)[:120]}
    anchor = task['anchor']
    verdict = judge_blocked_by(refuse.get('blocked_by'), anchor)
    got_type = str(refuse.get('type') or '').strip().lower()
    want_type = str(task.get('refuse_type') or '').strip().lower()
    detail = {'anchor': anchor, 'blocked_by': refuse.get('blocked_by'),
              'type': got_type, 'type_ok': got_type == want_type,
              'reason': str(refuse.get('reason'))[:150]}
    if verdict == 'exact':
        return 'refuse_correct', detail
    if verdict == 'multi':
        detail['note'] = 'blocked_by 写了多个标识符（穷举）'
        return 'refuse_multi', detail
    detail['note'] = 'blocked_by 没命中该题的 anchor'
    return 'refuse_wrong', detail


def judge_build_task(cand, task, cand_path):
    """对照题判类。返回 (verdict, detail)。

    ★ 走 ``evaluate_one(skip_solve=True)``：与 `judge_l3_candidate` 的 spec 分支
      **同一条路径**，不复制字段比对（规则只有一处）。task 用 ``source_task_id``
      重建，好让 ``case_id_of`` 找得到 gold；``out_root`` 指到临时目录，不污染
      ``RUNS/``。``input_level='L3'`` 是为了 ``engineering_layer=True``，与 L3 同口径。
    """
    if cand.get('error'):
        return 'ctl_llm_error', {'error': cand['error']}
    refuse = cand.get('refuse')
    if refuse:
        return 'over_refuse', {'note': '该建的请求被拒了（过拒）',
                               'refuse': json.dumps(refuse, ensure_ascii=False)[:150]}
    spec = cand.get('spec')
    if not spec:
        if cand.get('clarify'):
            return 'ctl_clarified', {'note': '信息完备却澄清',
                                     'clarify': str(cand['clarify'])[:140]}
        return 'ctl_no_output', {'note': 'refuse / spec / clarify 都空'}

    from evaluate import evaluate_one
    fake = {'task_id': task['gold']['source_task_id'],
            'family': task['family'],
            'split_v2': 'val',        # spec_fidelity 不读它，仅为字段完整
            'input_level': 'L3',      # ⇒ engineering_layer=True，与 L3 同口径
            'input': {}}
    with tempfile.TemporaryDirectory(prefix='b2judge_') as td:
        r = evaluate_one(fake, cand_path, out_root=td, skip_solve=True)
    sf = (r.get('gates') or {}).get('spec_fidelity') or {}
    failed = [f.get('field') for f in (sf.get('failed') or [])]
    detail = {'n_fields': sf.get('n_fields'), 'n_fail': sf.get('n_fail'),
              'failed_fields': failed[:6]}
    return ('build_correct' if r.get('overall_pass') else 'build_fail'), detail


def judge_one(cand, task, cand_path):
    if task['kind'] == 'refuse':
        verdict, detail = judge_refuse_task(cand, task)
    else:
        verdict, detail = judge_build_task(cand, task, cand_path)
    kind, counted, _why = VERDICT_TABLE[verdict]
    return {'task_id': task['task_id'], 'kind': task['kind'],
            'refuse_type': task.get('refuse_type'), 'anchor': task.get('anchor'),
            'verdict': verdict, 'counted': counted, 'detail': detail}


# ---------------------------------------------------------------------------
def wilson_ci(k, n, z=1.959963984540054):
    """Wilson 区间。★ 为什么不用正态近似：p 接近 1 或 n 小时它会越界到 >100%。

    这个数决定「≥95% 这条线能不能判」：n=40 时 36 对给出 [76.9, 96.0]，
    上界刚过 95 ⇒ **统计上不可判**。不写进 artifact 的话，报表只能拿点估计说事。
    """
    if n <= 0:
        return [0.0, 100.0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [round(max(0.0, c - h) * 100, 1), round(min(1.0, c + h) * 100, 1)]


def compare_runs(rows_a, rows_b):
    """两遍采样的逐题一致性。★ 这是判「抖动」的唯一办法。

    为什么必须逐题比：实测 40 条越界题跑两遍，**两遍总准确率都是 36/40 = 90.0%**，
    但逐题看有 4 条翻转、方向刚好抵消。只看两个 90.0% 会得出「测量稳定」的结论，
    而真相是 **10% 的题在抖**（T-B1KPI 的同型教训：通过率把上游不同步吸收掉了）。
    """
    a = {r['task_id']: r for r in rows_a}
    b = {r['task_id']: r for r in rows_b}
    common = sorted(set(a) & set(b))

    def _missing(r):
        """候选文件不存在 —— 这是「这一遍没跑这条」，不是判类翻转。

        ★ 不排除它会把 15 条没跑的对照题全算成 flip（实测量到 24 条假翻转），
          于是「翻转数」这个指标当场失去意义。
        """
        return (r.get('detail') or {}).get('note') == '候选文件缺失'

    flips = []
    skipped = 0
    for tid in common:
        if _missing(a[tid]) or _missing(b[tid]):
            skipped += 1
            continue
        va, vb = a[tid]['verdict'], b[tid]['verdict']
        if va != vb:
            flips.append({'task_id': tid, 'verdict_a': va, 'verdict_b': vb,
                          'blocked_by_a': (a[tid].get('detail') or {}).get('blocked_by'),
                          'blocked_by_b': (b[tid].get('detail') or {}).get('blocked_by')})
    n = len(common) - skipped
    return {
        'n_compared': n,
        'n_skipped_missing': skipped,
        'n_agree': n - len(flips),
        'agree_pct': round(100.0 * (n - len(flips)) / max(1, n), 1),
        'flips': flips,
    }


def agg(rows):
    """聚合。★ 越界与对照**各自一个分母**，任何时候都并列报。"""
    out = {}
    for kind in COUNTED_KINDS:
        sub = [r for r in rows if r['kind'] == kind]
        valid = [r for r in sub if r['verdict'] not in ('llm_error', 'ctl_llm_error')]
        passed = [r for r in valid if r['counted']]
        out[kind] = {
            'total': len(sub),
            'counted': len(valid),
            'pass': len(passed),
            'pct': round(100.0 * len(passed) / max(1, len(valid)), 1),
            'ci95_wilson': wilson_ci(len(passed), len(valid)),
            'verdicts': dict(sorted(
                {v: sum(1 for r in sub if r['verdict'] == v)
                 for v in {r['verdict'] for r in sub}}.items())),
        }
    # 按越界类型 / anchor 细分（诊断用；分母各自报，不合并）
    by_type = {}
    for r in rows:
        if r['kind'] != 'refuse':
            continue
        t = r['refuse_type'] or '?'
        d = by_type.setdefault(t, {'n': 0, 'pass': 0})
        d['n'] += 1
        d['pass'] += 1 if r['counted'] else 0
    for d in by_type.values():
        d['pct'] = round(100.0 * d['pass'] / max(1, d['n']), 1)

    by_anchor = {}
    for r in rows:
        if r['kind'] != 'refuse':
            continue
        a = r['anchor'] or '?'
        d = by_anchor.setdefault(a, {'n': 0, 'pass': 0})
        d['n'] += 1
        d['pass'] += 1 if r['counted'] else 0

    refusal_pct = out['refuse']['pct']
    control_pct = out['build']['pct']
    # 过拒率：对照题里被拒的占比。这才是「见谁都拒」的度量。
    over_refuse = out['build']['verdicts'].get('over_refuse', 0)
    over_refuse_pct = round(100.0 * over_refuse / max(1, out['build']['counted']), 1)
    out['kpi'] = {
        'refusal_pct': refusal_pct,
        'target_pct': REFUSAL_TARGET_PCT,
        'target_met': refusal_pct >= REFUSAL_TARGET_PCT and out['refuse']['counted'] > 0,
        # 两个对照指标，含义不同，必须分开报：
        #   over_refuse_pct —— 该建的被拒了没有（守「全拒」这条攻击路）
        #   build_correct_pct —— 建得对不对（建模能力，与拒答无关，纯诊断）
        'over_refuse_pct': over_refuse_pct,
        'over_refuse_floor_pct': OVER_REFUSE_FLOOR_PCT,
        'quotable_alone': over_refuse_pct <= OVER_REFUSE_FLOOR_PCT,
        'build_correct_pct': control_pct,
        'by_type': by_type,
        'by_anchor': dict(sorted(by_anchor.items())),
    }
    return out


def run(cand_dir, tasks_path=None, limit=None):
    tasks = load_tasks(tasks_path)
    if limit:
        tasks = tasks[:limit]
    rows = []
    for t in tasks:
        p = os.path.join(cand_dir, t['task_id'] + '.json')
        if not os.path.exists(p):
            rows.append({'task_id': t['task_id'], 'kind': t['kind'],
                         'refuse_type': t.get('refuse_type'), 'anchor': t.get('anchor'),
                         'verdict': 'llm_error' if t['kind'] == 'refuse' else 'ctl_llm_error',
                         'counted': False, 'detail': {'note': '候选文件缺失'}})
            continue
        cand = json.loads(io.open(p, encoding='utf-8').read())
        rows.append(judge_one(cand, t, p))
    return rows, agg(rows), tasks


# ---------------------------------------------------------------------------
def self_test():
    """八向自检：每一档判类各喂一个构造候选，且断言**判对的理由也对**。"""
    ok = True

    def expect(cond, what):
        nonlocal ok
        print(('  [ok] ' if cond else '  [BAD] ') + what)
        ok = ok and cond

    tasks = load_tasks()
    refuse_tasks = [t for t in tasks if t['kind'] == 'refuse']
    build_tasks = [t for t in tasks if t['kind'] == 'build']
    t_geo = next(t for t in refuse_tasks if t['refuse_type'] == 'geometry')
    t_cap = next(t for t in refuse_tasks if t['refuse_type'] == 'capability')
    t_build = build_tasks[0]

    def mk(task, **kw):
        base = {'task_id': task['task_id'], 'input_level': 'REFUSE', 'model': 'selftest'}
        base.update(kw)
        return base

    # T1 正确拒绝（几何）
    v, _ = judge_refuse_task(mk(t_geo, refuse={'type': 'geometry',
                                               'blocked_by': t_geo['anchor'],
                                               'reason': 'x'}), t_geo)
    expect(v == 'refuse_correct', 'T1 几何题 blocked_by 唯一命中 ⇒ refuse_correct')

    # T2 正确拒绝（能力）
    v, d = judge_refuse_task(mk(t_cap, refuse={'type': 'capability',
                                               'blocked_by': t_cap['anchor'],
                                               'reason': 'x'}), t_cap)
    expect(v == 'refuse_correct' and d['type_ok'],
           'T2 能力题命中且 type 对 ⇒ refuse_correct')

    # T3 拒绝但 anchor 错
    v, _ = judge_refuse_task(mk(t_geo, refuse={'type': 'geometry',
                                               'blocked_by': '__wrong__',
                                               'reason': 'x'}), t_geo)
    expect(v == 'refuse_wrong', 'T3 blocked_by 不对 ⇒ refuse_wrong（不是 pass）')

    # T4 穷举：写多个标识符
    multi = '%s, __another__' % t_geo['anchor']
    v, d = judge_refuse_task(mk(t_geo, refuse={'type': 'geometry',
                                               'blocked_by': multi}), t_geo)
    expect(v == 'refuse_multi', 'T4 写多个标识符 ⇒ refuse_multi（穷举要被拦住）')

    # T5 =值 后缀仍是单值，不算穷举
    v, _ = judge_refuse_task(mk(t_geo, refuse={'type': 'geometry',
                                               'blocked_by': t_geo['anchor'] + '=3'}), t_geo)
    expect(v == 'refuse_correct', 'T5 "key=值" 是自然表达 ⇒ 仍 refuse_correct')

    # T6 越界题给了 spec ⇒ silent_build（最严重）
    v, _ = judge_refuse_task(mk(t_geo, spec={'structure': {'family': t_geo['family']}}), t_geo)
    expect(v == 'silent_build', 'T6 越界题产出 spec ⇒ silent_build')

    # T7 越界题给了 clarify ⇒ clarified（不是拒绝）
    v, _ = judge_refuse_task(mk(t_geo, clarify='["请提供 n_frames"]'), t_geo)
    expect(v == 'clarified', 'T7 越界题输出 clarify ⇒ clarified（与拒答分开）')

    # T8 对照题拒答 ⇒ over_refuse
    v, _ = judge_build_task(mk(t_build, refuse={'type': 'capability',
                                                'blocked_by': 'frequency'}),
                            t_build, '/nonexistent.json')
    expect(v == 'over_refuse', 'T8 对照题被拒 ⇒ over_refuse（过拒要被抓）')

    # T9 ★ 恒真式检测：拿 gold spec 自己当候选 ⇒ 必须 build_correct
    #    这条是「自比 A==B」（负控五条第④类）：spec_fidelity 实现坏了这里立刻红。
    gold_path = None
    try:
        import evaluate as _ev
        gold_path = os.path.join(_ev.FEA, 'modeling', t_build['gold']['case_id'], 'spec.json')
    except Exception as exc:                       # noqa: BLE001
        print('  [BAD] T9 无法定位 gold：%s' % exc)
        ok = False
    if gold_path and os.path.exists(gold_path):
        gold = json.loads(io.open(gold_path, encoding='utf-8').read())
        gold['name'] = 'selftest_' + t_build['task_id']
        with tempfile.TemporaryDirectory(prefix='b2self_') as td:
            cp = os.path.join(td, 'cand.json')
            io.open(cp, 'w', encoding='utf-8', newline='\n').write(
                json.dumps({'task_id': t_build['task_id'], 'spec': gold},
                           ensure_ascii=False))
            v, d = judge_build_task({'task_id': t_build['task_id'], 'spec': gold},
                                    t_build, cp)
        expect(v == 'build_correct',
               'T9 gold 自己当候选 ⇒ build_correct（字段比对没坏；n_fail=%s）'
               % d.get('n_fail'))
    elif gold_path:
        print('  [BAD] T9 gold spec 不存在：%s' % gold_path)
        ok = False

    # T10 卷面：anchor 池从卷现取（不写死），且每题 anchor 都在池里
    pool = {t['anchor'] for t in refuse_tasks}
    expect(len(pool) >= 8 and all(t['anchor'] in pool for t in refuse_tasks),
           'T10 anchor 池现取 %d 个、逐条可归属' % len(pool))

    # T11/T12 ★ 锁住「可不可单独引用」这条口径的两侧。
    #   起因：第一版用「对照建对率 ≥90%」当门槛，实测建对率 65% 而 20 条里**一条都没被拒**
    #   ⇒ 警告照样触发，把「建错」的锅算到「拒答」头上。过拒率才是「见谁都拒」的度量。
    _rr = [{'kind': 'refuse', 'refuse_type': 'geometry', 'anchor': 'a',
            'verdict': 'refuse_correct', 'counted': True}] * 4
    _all_reject = agg(_rr + [{'kind': 'build', 'refuse_type': None, 'anchor': None,
                              'verdict': 'over_refuse', 'counted': False}] * 2)
    expect(_all_reject['kpi']['quotable_alone'] is False,
           'T11 对照题全被拒 ⇒ 拒答准确率不得单独引用（%s%%）'
           % _all_reject['kpi']['over_refuse_pct'])

    _just_wrong = agg(_rr + [{'kind': 'build', 'refuse_type': None, 'anchor': None,
                              'verdict': 'build_fail', 'counted': False}] * 2)
    expect(_just_wrong['kpi']['quotable_alone'] is True,
           'T12 对照题只是建错、没被拒 ⇒ 可单独引用（建错不算到拒答头上）')

    print()
    print('自检 %s' % ('全过' if ok else '有失败'))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidates', default='')
    ap.add_argument('--tasks', default=TASKS)
    ap.add_argument('--json', default='')
    ap.add_argument('--compare', default='',
                    help='第二遍候选目录：逐题比判类，量化采样抖动')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()

    if args.self_test:
        return 0 if self_test() else 1
    if not args.candidates:
        print('需要 --candidates 目录（或 --self-test）')
        return 2
    if not os.path.isdir(args.candidates):
        print('候选目录不存在：' + args.candidates)
        return 2

    rows, summary, tasks = run(args.candidates, args.tasks, args.limit or None)

    print('== 拒答准确率（越界题）==')
    r = summary['refuse']
    print('   %d/%d = %.1f%%（分母 %d，总 %d）Wilson CI95 [%s, %s]'
          % (r['pass'], r['counted'], r['pct'], r['counted'], r['total'],
             r['ci95_wilson'][0], r['ci95_wilson'][1]))
    print('== 对照集（正常题，防「见谁都拒」）==')
    b = summary['build']
    print('   过拒 %d/%d = %.1f%%（该建的被拒了没有）'
          % (b['verdicts'].get('over_refuse', 0), b['counted'],
             summary['kpi']['over_refuse_pct']))
    print('   建对 %d/%d = %.1f%%（建模能力，与拒答无关，纯诊断）'
          % (b['pass'], b['counted'], b['pct']))
    print()
    print('越界题判类：', r['verdicts'])
    print('对照题判类：', b['verdicts'])
    print()
    print('按类型：', {k: '%d/%d %.1f%%' % (v['pass'], v['n'], v['pct'])
                       for k, v in summary['kpi']['by_type'].items()})
    print('按 anchor：', {k: '%d/%d' % (v['pass'], v['n'])
                          for k, v in summary['kpi']['by_anchor'].items()})
    k = summary['kpi']
    print()
    print('KPI ≥%.0f%%：%s' % (k['target_pct'], '达标' if k['target_met'] else '未达标'))
    if not k['quotable_alone']:
        print('⚠ 过拒率 %.1f%% > %.0f%% ⇒ **拒答准确率不得单独引用**'
              '（模型在「见谁都拒」）' % (k['over_refuse_pct'], k['over_refuse_floor_pct']))

    if args.json:
        payload = {'candidates': os.path.abspath(args.candidates),
                   'tasks': os.path.basename(args.tasks),
                   'n_tasks': len(tasks),
                   'summary': summary, 'rows': rows}
        if args.compare:
            rows2, summary2, _ = run(args.compare, args.tasks, args.limit or None)
            st = compare_runs(rows, rows2)
            st['refusal_pct_a'] = summary['refuse']['pct']
            st['refusal_pct_b'] = summary2['refuse']['pct']
            st['note'] = ('两遍总准确率相同**不等于**结果相同：见 flips。'
                          '本卷 n=40，翻转 1 条 = 2.5 pp。')
            payload['stability'] = st
            payload['candidates_b'] = os.path.abspath(args.compare)
            print()
            print('== 采样抖动（两遍逐题比）==')
            print('   判类一致 %d/%d = %.1f%%；两遍准确率 %.1f%% vs %.1f%%'
                  % (st['n_agree'], st['n_compared'], st['agree_pct'],
                     st['refusal_pct_a'], st['refusal_pct_b']))
            for f in st['flips']:
                print('   翻转 %-18s %-14s(%-14s) -> %-14s(%-14s)'
                      % (f['task_id'], f['verdict_a'], f['blocked_by_a'],
                         f['verdict_b'], f['blocked_by_b']))
            if st['flips'] and abs(st['refusal_pct_a'] - st['refusal_pct_b']) < 0.05:
                print('   ⚠ 两遍准确率**恰好相同**而逐题翻转 %d 条 ⇒ 方向抵消，'
                      '不得据此说「测量稳定」' % len(st['flips']))
        io.open(args.json, 'w', encoding='utf-8', newline='\n').write(
            json.dumps(payload, ensure_ascii=False, indent=1) + '\n')
        print('已写 ' + args.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
