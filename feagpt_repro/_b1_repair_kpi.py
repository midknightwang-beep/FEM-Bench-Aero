#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_b1_repair_kpi.py — B1 补算：修复成功率 / 修复收敛轮数（零重跑，只读既有 artifact）

口径见 reports/diagnostics/task_b1kpi_contract.md §1，三层必须分开报：

  L1 结构层：首轮 schema/contract 未过的题，在 --max-turns 3 内产出**可判记录**
             （spec 非空或 clarify 非空）的比例 —— 这才是「修复成功率」
  L2 产出层：修复成功的题分别产出了 spec 还是 clarify
  L3 语义层：结构修好了，但 spec_fidelity 是否全对（= 成绩单的 TSR）

**为什么必须三层**：所有 spec 题首轮结构校验全部未过（见契约 §0.3），
所以 L1 必然接近 100%，而这个数几乎全由「闸有多严」决定，不由模型能力决定。
只报一个 100% = 自欺。

本脚本不做「重新统计」这件事，而是做**交叉对账**：
  candidates_*/  ← 生成阶段写出（turns_used / validation_history / spec / clarify）
  reports/baseline_scorecard_*.json ← 评分阶段写出（turns_histogram / first_pass_valid /
                                      n_unresolved / per_task.category）
两份是**两个程序**写的，对得上才说明两套口径没漂。

用法:
  python _b1_repair_kpi.py                      # 跑内置 RUNS，打印 + 默认写 JSON
  python _b1_repair_kpi.py --json out.json      # 指定输出
  python _b1_repair_kpi.py --no-json            # 只看输出不落盘
  python _b1_repair_kpi.py --self-test          # 七向构造性自检（造坏数据必须红）

退出码：0 = 全过；2 = 有判据红（原因逐条打印）；1 = 环境/参数错误。
"""
import argparse
import collections
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))

# 生成器的 `--max-turns` 默认值（gen_candidates_v2.js:143 与 C-032/C-040 的四次调用都用 3）。
# C5 的「耗尽」分支要用它判断「是不是真的跑满了」。
MAX_TURNS = 3

# 每条 run 一份成绩单 + 对应候选目录。v6c 与 v7 **不可相减**（不同卷），只并列。
RUNS = [
    {'label': 'C-040 v7 x glm', 'paper': 'v7',
     'scorecard': 'reports/baseline_scorecard_L3_v7_glm.json',
     'candidates': 'candidates_l3_v7_glm'},
    {'label': 'C-040 v7 x ds', 'paper': 'v7',
     'scorecard': 'reports/baseline_scorecard_L3_v7_ds.json',
     'candidates': 'candidates_l3_v7_ds'},
    {'label': 'C-032 v6c x glm', 'paper': 'v6c',
     'scorecard': 'reports/baseline_scorecard_L3_v6c_p2.json',
     'candidates': 'candidates_l3_v6c_glm_p2'},
    {'label': 'C-033 v6c x ds', 'paper': 'v6c',
     'scorecard': 'reports/baseline_scorecard_L3_v6c_ds_p2.json',
     'candidates': 'candidates_l3_v6c_ds_p2'},
]

# 首轮失败原因的文本特征。**这是对 errors 字符串的粗分类**，只用来回答
# 「首轮失败主要卡在哪一类闸」，不参与任何通过判定。errors 被生成器截到 12 条
# （gen_candidates_v2.js 的 `.slice(0, 12)`）⇒ 这里的计数是**下界**。
REASON_RULES = [
    ('required_missing', 'must have required property'),
    ('extra_key', '不允许的键'),
    ('enum_mismatch', '必须是'),
    ('json_parse', 'JSON parse'),
    ('type_or_value', 'must be'),
    ('contract_other', '必须'),
]

# 首轮失败究竟卡在哪个键。只用于归因，不参与任何通过判定。
# 注意：errors 文本里的引号是英文双引号（`不允许的键 "size"`），别按中文引号去匹配。
MISS_RE = re.compile(r"must have required property '([^']+)'")
EXTRA_RE = re.compile(r'不允许的键 "([^"]+)"')


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _nonempty(v):
    return v not in (None, '', [], {}, 0) and v is not False


def _rel(p):
    """报告里只留相对路径（公开集会检查本机路径）。"""
    try:
        r = os.path.relpath(os.path.abspath(p), HERE)
    except ValueError:                      # 跨盘：relpath 抛 ValueError
        return os.path.basename(p)
    return r.replace(os.sep, '/')


def load_candidates(cdir):
    """读候选目录。返回 (recs, stray)。

    stray = 目录里不是 .json 的文件（实测存在一个 `*.json.bak` 重试残留）。
    **它必须被显式列出来**，否则「目录文件数 == 任务数」这种对账会假绿。
    """
    recs, stray = {}, []
    if not os.path.isdir(cdir):
        raise FileNotFoundError('候选目录不存在: %s' % cdir)
    for fn in sorted(os.listdir(cdir)):
        p = os.path.join(cdir, fn)
        if not os.path.isfile(p):
            continue
        if not fn.endswith('.json'):
            stray.append(fn)
            continue
        with open(p, encoding='utf-8') as f:
            x = json.load(f)
        tid = x.get('task_id') or fn[:-5]
        vh = x.get('validation_history') or []
        recs[tid] = {
            'turns_used': x.get('turns_used') or 0,
            'n_validation': len(vh),
            'has_spec': _nonempty(x.get('spec')),
            'has_clarify': _nonempty(x.get('clarify')),
            'has_error': _nonempty(x.get('error')),
            'first_errors': list(vh[0].get('errors') or []) if vh else [],
            'file': fn,
        }
    return recs, stray


def _classify_reasons(errors):
    """一条题的首轮 errors → 命中的类别集合（多标签，因为一条题常同时踩几个闸）。"""
    hit = set()
    for e in errors:
        for name, needle in REASON_RULES:
            if needle in e:
                hit.add(name)
                break
    return hit


def analyze(scorecard_path, cand_dir):
    """算出 L1/L2/L3 三层 + 收敛轮数 + 首轮失败原因，并做对账判据。"""
    fails, notes = [], []
    with open(scorecard_path, encoding='utf-8') as f:
        sc = json.load(f)
    recs, stray = load_candidates(cand_dir)

    per_task = sc.get('per_task') or []
    by_task = {t['task_id']: t for t in per_task}

    # ---------- 对账 C1：turns_used 直方图 ----------
    live_hist = collections.Counter()
    for tid, c in recs.items():
        if c['has_error']:
            continue
        live_hist[c['turns_used']] += 1
    live_hist = {str(k): v for k, v in sorted(live_hist.items())}
    sc_hist = {str(k): v for k, v in (sc.get('turns_histogram') or {}).items()}
    if live_hist != sc_hist:
        fails.append(('C1', '候选实读 turns 直方图 %s ≠ 成绩单 turns_histogram %s'
                      % (live_hist, sc_hist)))

    # ---------- 对账 C2：first_pass_valid ----------
    fp = live_hist.get('1', 0)
    if fp != sc.get('first_pass_valid'):
        fails.append(('C2', '实读首轮通过 %d ≠ 成绩单 first_pass_valid %s'
                      % (fp, sc.get('first_pass_valid'))))

    # ---------- 对账 C3：n_unresolved ----------
    n_null = sum(1 for c in recs.values()
                 if not c['has_error'] and not c['has_spec'] and not c['has_clarify'])
    if n_null != sc.get('n_unresolved'):
        fails.append(('C3', '实读空产出 %d ≠ 成绩单 n_unresolved %s'
                      % (n_null, sc.get('n_unresolved'))))

    # ---------- 对账 C5：轮次数与校验记录数必须自洽 ----------
    # 生成器的循环只在「通过 / 出澄清」时 break；**跑满 maxTurns 仍失败时不 break**，
    # 第 3 轮失败后自然退出，那一轮的错误也 push 进了 validation_history。
    # 所以正确的不变量是**双分支**，不是单一等式：
    #   有产出（通过或澄清）⇒ len(vh) == turns - 1
    #   无产出（耗尽）      ⇒ turns == MAX_TURNS 且 len(vh) == MAX_TURNS
    # 首版只写了 `turns == len(vh) + 1`，被 `cfrp45s_d40`（3 轮全失败）判红 ——
    # **那是我的判据漏了耗尽分支，不是数据错**。这一版更严：还多抓「提前停止」。
    bad5 = []
    for tid, c in recs.items():
        if c['has_error']:
            continue
        produced = c['has_spec'] or c['has_clarify']
        if produced:
            if c['turns_used'] != c['n_validation'] + 1:
                bad5.append((tid, c['turns_used'], c['n_validation'], '有产出但轮次不符'))
        else:
            if c['turns_used'] != MAX_TURNS or c['n_validation'] != MAX_TURNS:
                bad5.append((tid, c['turns_used'], c['n_validation'],
                             '无产出却不是跑满 %d 轮（提前停止）' % MAX_TURNS))
    if bad5:
        fails.append(('C5', '%d 条轮次/校验史不自洽：%s' % (len(bad5), bad5[:5])))

    # ---------- 对账 C7：逐题大类与判分器一致 ----------
    def implied(has_spec, has_clarify, has_error, ec):
        if has_error:
            return 'llm_error'
        if has_spec and ec:
            return 'fabricated'
        if has_spec:
            return 'spec'
        if has_clarify:
            return 'clarify'
        return 'no_output'

    ALLOWED = {
        'llm_error': {'llm_error'},
        'fabricated': {'fabricated'},
        'spec': {'spec_pass', 'spec_fail'},
        'clarify': {'clarify_ok', 'clarify_wrong'},
        'no_output': {'no_output'},
    }
    mismatch, missing = [], []
    for t in per_task:
        tid = t['task_id']
        c = recs.get(tid)
        if c is None:
            missing.append(tid)
            continue
        # ★ 澄清题判据用判分器自己的布尔 `ec`，不用 `expected`：
        #   `per_task` 的键名**不统一**（澄清题有 `expected`，spec 题没有这个键），
        #   首版用 `t.get('expected') or []` ⇒ spec 题一律被判成「无期望澄清」，
        #   而 `fabricated` 的题（本该澄清却给了 spec）恰好就是那批「没有 expected 键」的，
        #   于是 1 条真的 fabricated 被误判成形态不符。`ec` 是 judge 里
        #   `bool(task.get('expected_clarifications'))` 的结果，权威且键名固定。
        ec = bool(t.get('ec'))
        imp = implied(c['has_spec'], c['has_clarify'], c['has_error'], ec)
        cat = t.get('category')
        if cat not in ALLOWED.get(imp, set()):
            mismatch.append((tid, imp, cat))
    if missing:
        fails.append(('C7a', '成绩单里有、候选目录里没有的题 %d 条：%s'
                      % (len(missing), missing[:5])))
    if mismatch:
        fails.append(('C7b', '%d 条候选形态与 category 不符：%s'
                      % (len(mismatch), mismatch[:5])))

    # ---------- L1 / L2 / L3 ----------
    n_tasks = len(per_task)
    first_pass = [tid for tid, c in recs.items()
                  if not c['has_error'] and c['turns_used'] == 1]
    needing = [tid for tid, c in recs.items()
               if not c['has_error'] and c['turns_used'] >= 2]
    repaired = [tid for tid in needing if recs[tid]['has_spec'] or recs[tid]['has_clarify']]
    exhausted = [tid for tid in needing
                 if not recs[tid]['has_spec'] and not recs[tid]['has_clarify']]

    # 分母为 0 时「100%」毫无意义，必须判红而不是判绿（防空壳）
    if not needing:
        fails.append(('C6', '首轮未过的题数为 0 ⇒ 修复成功率没有分母，这个 KPI 无意义'))

    # L1
    rate = (100.0 * len(repaired) / len(needing)) if needing else None
    # L2
    repaired_spec = [tid for tid in repaired if recs[tid]['has_spec']]
    repaired_clarify = [tid for tid in repaired if not recs[tid]['has_spec']]
    # L3：结构修好之后的语义结果（用成绩单的 category，不重算 TSR）
    #   ★ 首版只数了 spec_pass / spec_fail，结果 ds v7 出现 50+8 = 58 ≠ 59 ——
    #     漏的是 `fabricated`（修出了合法 spec，但那题本该澄清 ⇒ 答错了类型）。
    #     分项和必须等于分母，否则比率是错的分母（R-A5）。
    spec_cat = collections.Counter(by_task.get(tid, {}).get('category') for tid in repaired_spec)
    sem_pass, sem_fail = spec_cat.get('spec_pass', 0), spec_cat.get('spec_fail', 0)
    sem_other = {k: v for k, v in spec_cat.items() if k not in ('spec_pass', 'spec_fail')}
    # ★ 首版的闭合断言写成 `sum(spec_cat.values()) == len(repaired_spec)` ——
    #   那是**恒真式**（Counter 的值之和按定义就等于被计数的元素个数），任何未知类别
    #   都能「闭合」，于是 C8 永远不会红。与 N-26「恒真式外观与正常闭合一样」同族。
    #   真正的判据是：**给了 spec 的题，类别必须落在已知集合里**。
    KNOWN_SPEC_CATS = {'spec_pass', 'spec_fail', 'fabricated'}
    unknown_cats = {k: v for k, v in spec_cat.items() if k not in KNOWN_SPEC_CATS}
    closure_ok = not unknown_cats

    # ---------- 对账 C8：给 spec 的题，类别必须都在已知集合里 ----------
    # 首版写成「值之和 == 元素个数」是**恒真式**，C8 永红不了；ds v7 漏计 fabricated
    # 时它也照样「闭合」，比率照样算得出来、且看起来合理 ⇒ 错的比率不会自己喊疼。
    if unknown_cats:
        fails.append(('C8', '有 %d 个未知类别（不在 spec_pass/spec_fail/fabricated 里）：%s'
                      % (len(unknown_cats), unknown_cats)))

    # ---------- 对账 C9：per_task 的类别计数必须能还原顶层 TSR ----------
    # 这是「判分器的逐题判定」与「判分器的汇总统计」之间的对账 —— 同一个程序的两个出口，
    # 一个漏计（例如把 clarify_ok 忘了算进 TSR 分子）在这里就会被抓。
    tsr_calc = sum(1 for t in per_task if t.get('category') in ('spec_pass', 'clarify_ok'))
    tsr_top = (sc.get('tsr') or {}).get('pass')
    if tsr_calc != tsr_top:
        fails.append(('C9', 'per_task 里 spec_pass+clarify_ok = %d ≠ 顶层 tsr.pass = %s'
                      % (tsr_calc, tsr_top)))

    # ---------- 收敛轮数 ----------
    repair_turns = collections.Counter(recs[tid]['turns_used'] - 1 for tid in needing)
    repair_turns = {str(k): v for k, v in sorted(repair_turns.items())}
    ts = sorted(recs[tid]['turns_used'] - 1 for tid in needing)
    median = ts[len(ts) // 2] if ts else None
    mean = (sum(ts) / len(ts)) if ts else None
    within1 = sum(1 for x in ts if x <= 1)

    # ---------- 首轮失败原因（多标签，下界） ----------
    reason_tasks = collections.Counter()
    missing_keys, extra_keys = collections.Counter(), collections.Counter()
    for tid in needing:
        errs = recs[tid]['first_errors']
        for name in _classify_reasons(errs):
            reason_tasks[name] += 1
        for e in errs:
            for m in MISS_RE.findall(e):
                missing_keys[m] += 1
            for m in EXTRA_RE.findall(e):
                extra_keys[m] += 1
    unclassified = sum(1 for tid in needing
                       if not _classify_reasons(recs[tid]['first_errors']))

    # 首轮通过的题按产出类型拆（回答「为什么 spec 题首轮 0 通过」）
    fp_by_output = collections.Counter()
    for tid in first_pass:
        fp_by_output['spec' if recs[tid]['has_spec'] else 'clarify'] += 1

    record = {
        'label': None,                      # 由调用方填
        'scorecard': _rel(scorecard_path),
        'scorecard_sha256': _sha256(scorecard_path),
        'candidates_dir': _rel(cand_dir),
        'n_tasks_in_scorecard': n_tasks,
        'n_candidates_read': len(recs),
        'n_stray_files': len(stray),
        'stray_files': stray,
        'structure_repair_L1': {
            'denominator_n': len(needing),
            'numerator_n': len(repaired),
            'rate_pct': round(rate, 1) if rate is not None else None,
            'n_exhausted': len(exhausted),
            'exhausted_ids': exhausted,
            'definition': '首轮 schema/contract 未过（turns_used>=2）的题中，在 max_turns=3 内'
                          '产出可判记录（spec 或 clarify 非空）的比例；机械上限 = 2 次修复',
        },
        'repair_outcome_L2': {
            'repaired_to_spec': len(repaired_spec),
            'repaired_to_clarify': len(repaired_clarify),
            'clarify_ids': repaired_clarify,
        },
        'post_repair_semantics_L3': {
            'basis': '成绩单 per_task.category（不重算 TSR，保持单一来源）',
            'repaired_to_spec_n': len(repaired_spec),
            'spec_pass': sem_pass,
            'spec_fail': sem_fail,
            'other_categories': sem_other,
            'closure_ok': closure_ok,
            'closure_expr': '%d = spec_pass %d + spec_fail %d + other %d（已知集合 spec_pass/'
                            'spec_fail/fabricated；出现集合外类别即判红）'
                            % (len(repaired_spec), sem_pass, sem_fail,
                               sum(sem_other.values())),
            'pass_rate_pct': round(100.0 * sem_pass / len(repaired_spec), 1)
            if repaired_spec else None,
            'note': '结构修好 ≠ 内容正确：这一层是「修好格式之后仍然有失败」的证据。'
                    '分母含 other（如 fabricated = 修出合法 spec 但那题本该澄清），'
                    '所以它比「spec 类通过率」更严。',
        },
        'convergence': {
            'all_turns_histogram': sc_hist,
            'repair_turns_histogram': repair_turns,
            'median_repair_turns': median,
            'mean_repair_turns': round(mean, 2) if mean is not None else None,
            'max_repair_turns': max(ts) if ts else None,
            'within_1_repair_n': within1,
            'within_1_repair_pct': round(100.0 * within1 / len(ts), 1) if ts else None,
            'note': '修复轮数 = turns_used - 1（turns_used 含首轮调用，见契约 §0.2）',
        },
        'first_pass': {
            'n': len(first_pass),
            'by_output': dict(fp_by_output),
            'note': '首轮通过的题按产出类型拆开 —— 若 spec 全 0，说明结构闸对 spec 从未一次放过',
        },
        'first_failure_reasons': {
            'n_tasks_needing_repair': len(needing),
            'counts_multilabel': dict(sorted(reason_tasks.items())),
            'n_unclassified': unclassified,
            'top_missing_required': missing_keys.most_common(10),
            'top_extra_keys': extra_keys.most_common(10),
            'note': '多标签（一条题常同时踩几个闸），合计 > 分母；errors 被生成器截到 12 条'
                    '（.slice(0, 12)）⇒ 计数是下界，Top 键同理',
        },
        'refusal_accuracy': {
            'status': 'not_computable',
            'reason': '需要越界题/拒答题题型；B5 五类题只完成了扩族，这类题一条没有',
            'counted_as': None,
            'note': '不印数字（R-A3）；不许填 0 也不许说「通过率 100%」',
        },
    }
    if stray:
        notes.append('候选目录里有 %d 个非 .json 文件（不计入任何统计）：%s'
                     % (len(stray), stray))
    return record, fails, notes


def run_all(runs):
    out, all_fails, all_notes = [], [], []
    for r in runs:
        sc = os.path.join(HERE, r['scorecard'])
        cd = os.path.join(HERE, r['candidates'])
        if not os.path.isfile(sc):
            all_fails.append(('ENV', '%s：成绩单不存在 %s' % (r['label'], r['scorecard'])))
            continue
        rec, fails, notes = analyze(sc, cd)
        rec['label'] = r['label']
        rec['paper'] = r.get('paper')
        out.append(rec)
        for fid, msg in fails:
            all_fails.append(('%s/%s' % (r['label'], fid), msg))
        all_notes += ['%s: %s' % (r['label'], n) for n in notes]
    return out, all_fails, all_notes


def print_report(rows):
    print('=== _b1_repair_kpi：修复成功率 / 收敛轮数（三层分开）===')
    for r in rows:
        L1, L2, L3, cv = (r['structure_repair_L1'], r['repair_outcome_L2'],
                          r['post_repair_semantics_L3'], r['convergence'])
        print()
        print('【%s】 卷=%s  任务 %d 条，候选读入 %d 条'
              % (r['label'], r['paper'], r['n_tasks_in_scorecard'], r['n_candidates_read']))
        print('  L1 结构层修复成功率：%d/%d = %s%%   耗尽未收敛 %d 条'
              % (L1['numerator_n'], L1['denominator_n'], L1['rate_pct'], L1['n_exhausted']))
        print('  L2 修复去向：修成 spec %d / 修成 clarify %d'
              % (L2['repaired_to_spec'], L2['repaired_to_clarify']))
        print('  L3 修好之后：spec_pass %d / spec_fail %d / 其他 %s ⇒ 语义通过率 %s%%'
              % (L3['spec_pass'], L3['spec_fail'], L3['other_categories'] or '{}',
                 L3['pass_rate_pct']))
        print('  收敛：修复轮数分布 %s  中位 %s  均值 %s  最大 %s  ≤1 轮 %s%%'
              % (cv['repair_turns_histogram'], cv['median_repair_turns'],
                 cv['mean_repair_turns'], cv['max_repair_turns'], cv['within_1_repair_pct']))
        fp = r['first_pass']
        print('  首轮通过 %d 条（产出：%s）'
              % (fp['n'], fp['by_output'] or '{}'))
        rs = r['first_failure_reasons']
        print('  首轮失败原因（多标签，下界）：%s  未归类 %d'
              % (rs['counts_multilabel'], rs['n_unclassified']))
        print('    缺 required 最多的键：%s' % (rs['top_missing_required'][:6] or '[]'))
        print('    被拒的自创键 top ：%s' % (rs['top_extra_keys'][:6] or '[]'))
    print()
    print('拒答准确率：not_computable —— 需越界/拒答题型（B5 未建），不印数字')
    print()


def _mk_fixture(td, hist=None, first_pass=None, n_unresolved=None,
                break_turns=None, drop_task=None, all_first_pass=False,
                bad_category=None, early_exhaust=False, bad_closure=None,
                bad_tsr=None):
    """造一对「成绩单 + 候选目录」的最小夹具。

    刻意用**生成器/评分器同样的键名与语义**，这样夹具能真的走到判据里。
    """
    os.makedirs(os.path.join(td, 'cand'), exist_ok=True)
    # 3 条题：t1 首轮澄清（首轮通过）、t2 两轮修成 spec、t3 三轮仍未收敛
    specs = {
        't1': {'turns': 1, 'spec': None, 'clarify': '["n_frames?"]', 'ec': ['n_frames'],
               'cat': 'clarify_ok', 'tsr': True, 'errs': []},
        't2': {'turns': 2, 'spec': {'a': 1}, 'clarify': None, 'ec': [],
               'cat': 'spec_pass', 'tsr': True,
               'errs': ['/material must have required property \'youngs_modulus\'']},
        't3': {'turns': 3, 'spec': None, 'clarify': None, 'ec': [],
               'cat': 'no_output', 'tsr': False,
               'errs': ['/mesh 不允许的键 "size"，请删除。']},
    }
    if all_first_pass:
        # 全首轮通过 ⇒ 分母为 0。ec 也要清空，否则「有 spec 且有 ec」会被 C7b 判成 fabricated，
        # 那样这一向红的就不只是 C6 了（夹具不该给判据塞第二种错）。
        specs = {k: dict(v, turns=1, spec={'a': 1}, cat='spec_pass', errs=[], ec=[])
                 for k, v in specs.items()}
    if bad_category:
        specs['t2']['cat'] = 'fabricated'  # 与「有 spec 且无 ec」不符
    if early_exhaust:
        # 无产出却只跑了 2 轮（本该跑满 3 轮）⇒ C5 的「耗尽」分支必须抓它。
        # 这一向是给 C5 自己立的「不许只测一个分支」：只测「通过」分支，
        # 耗尽分支写错了半年也不会有人发现。
        specs['t3'] = dict(specs['t3'], turns=2)
    if bad_closure:
        # 造一个不在任何映射表里的类别 ⇒ L3 分项和 != 分母（C8）
        specs['t2']['cat'] = 'weird_category'

    per_task, written = [], []
    for tid, s in specs.items():
        # 注意：drop_task 只让**候选文件**缺失，成绩单里这条仍然在 ——
        # 否则「成绩单有、目录没有」这个对账根本走不到（两边一起少了）。
        # vh 条数要按**真实生成器行为**造：通过/出澄清的那轮 break（该轮不留校验记录），
        # 跑满仍失败的那轮也 push 了错误 ⇒ 耗尽时 vh 条数 == turns。首版一律按 turns-1 造，
        # 于是「正常数据」被 C5 判红 —— **夹具不真会伪装成判据有病**（T-D6 同族）。
        has_out = (s['spec'] is not None) or bool(s['clarify'])
        n_vh = s['turns'] - 1 if has_out else s['turns']
        vh = [{'turn': i + 1, 'errors': s['errs']} for i in range(n_vh)]
        if break_turns and tid == 't2':
            # 真正破坏 turns == len(vh)+1：turns 说 2，却留下 2 条校验记录
            vh = vh + [{'turn': 99, 'errors': ['dup']}]
        if tid != drop_task:
            rec = {'task_id': tid, 'turns_used': s['turns'],
                   'spec': s['spec'], 'clarify': s['clarify'],
                   'validation_history': vh}
            with open(os.path.join(td, 'cand', tid + '.json'), 'w',
                      encoding='utf-8', newline='') as f:
                json.dump(rec, f, ensure_ascii=False)
            written.append(tid)
        per_task.append({'task_id': tid, 'category': s['cat'],
                         'ec': bool(s['ec']),          # ★ 判分器的布尔字段，C7 用它
                         'expected': s['ec'],          # 仅澄清题有，保留以便对照键名不统一
                         'tsr_pass': s['tsr']})

    h = hist if hist is not None else dict(collections.Counter(
        str(s['turns']) for s in specs.values()))
    # 顶层 tsr 必须与 per_task 自洽，否则 C9 在**每一向**都会红，
    # 把「好数据须绿」那一向也污染掉（判据处处误红 = 所有断言失效）。
    tsr_pass = sum(1 for p in per_task if p['category'] in ('spec_pass', 'clarify_ok'))
    if bad_tsr:
        tsr_pass += 1
    sc = {
        'turns_histogram': h,
        'first_pass_valid': first_pass if first_pass is not None else h.get('1', 0),
        'n_unresolved': n_unresolved if n_unresolved is not None else
                        sum(1 for s in specs.values() if s['cat'] == 'no_output'),
        'tsr': {'pass': tsr_pass, 'total': len(per_task),
                'pct': round(100.0 * tsr_pass / len(per_task), 1)},
        'per_task': per_task,
    }
    sp = os.path.join(td, 'scorecard.json')
    with open(sp, 'w', encoding='utf-8', newline='') as f:
        json.dump(sc, f, ensure_ascii=False)
    return sp, os.path.join(td, 'cand')


def self_test():
    """七向：好数据须绿 + 六种坏法各自红，且**红的是哪一条要对得上**。"""
    results = []
    with tempfile.TemporaryDirectory() as td:
        def one(name, want_red, **kw):
            d = os.path.join(td, name)
            os.makedirs(d, exist_ok=True)
            sp, cd = _mk_fixture(d, **kw)
            _, fails, _ = analyze(sp, cd)
            ids = [f[0] for f in fails]
            ok = (not ids) if not want_red else (want_red in ids)
            results.append((name, ok, ids))

        # ① 好数据必须绿（防过严：判据处处误红时，下面每一向的断言都会被污染）
        one('good', None)
        # ② 篡改 turns 直方图 ⇒ C1。
        #    ★ 夹具必须造一个**真的不等于实读**的直方图：首版我传了 {1:1,2:1,3:1}，
        #      而那正是实读值 ⇒ 这一向永远绿，看起来像判据坏了，其实是夹具没坏。
        one('bad_hist', 'C1', hist={'1': 2, '2': 1})
        # ③ 篡改 first_pass_valid ⇒ C2
        one('bad_fp', 'C2', first_pass=2)
        # ④ 缺一条候选 ⇒ C7a（覆盖不足；分数单里有、目录里没有）
        one('drop_cand', 'C7a', drop_task='t2')
        # ⑤ 破坏 turns 不变量 ⇒ C5（「通过」分支）
        one('break_turns', 'C5', break_turns=True)
        # ⑤b 无产出却提前停止 ⇒ C5（「耗尽」分支）—— 只测一个分支等于没测
        one('early_exhaust', 'C5', early_exhaust=True)
        # ⑥ 分母为 0（全首轮通过）⇒ C6（防空壳：100% 在分母 0 时无意义）
        one('no_denominator', 'C6', all_first_pass=True)
        # ⑦ category 与候选形态不符 ⇒ C7b（判分器与生成器产物对不上）
        one('bad_category', 'C7b', bad_category=True)
        # ⑧ L3 分项和不闭合 ⇒ C8（错的比率自己不会喊疼：分母漏一项，照样算出个像样的数）
        one('bad_closure', 'C8', bad_closure=True)
        # ⑨ 顶层 TSR 与逐题计数不符 ⇒ C9（判分器两个出口对不上）
        one('bad_tsr', 'C9', bad_tsr=True)

    print('=== _b1_repair_kpi --self-test ===')
    ok_all = True
    for name, good, ids in results:
        print('  [%s] %-18s 红项=%s' % ('ok  ' if good else 'BAD ', name, ids or '[]'))
        ok_all = ok_all and good
    print('=> %d/%d' % (sum(1 for _, g, _ in results if g), len(results)))
    return 0 if ok_all else 2


def main(argv=None):
    ap = argparse.ArgumentParser(description='B1 补算：修复成功率 / 收敛轮数（三层）')
    ap.add_argument('--json', default=os.path.join(
        'reports', 'diagnostics', 'b1_repair_kpi.json'))
    ap.add_argument('--no-json', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args(argv)

    if a.self_test:
        return self_test()

    rows, fails, notes = run_all(RUNS)
    print_report(rows)

    if fails:
        print('--- 判据红 ---')
        for fid, msg in fails:
            print('  [FAIL] %-22s %s' % (fid, msg))
    if notes:
        print('--- 提示 ---')
        for n in notes:
            print('  [note] %s' % n)
    print('\n结论：%s' % ('全过（C1/C2/C3/C5/C6/C7a/C7b/C8/C9 对账一致）' if not fails
                        else '有 %d 条判据红' % len(fails)))

    if not a.no_json:
        out = {
            'generated_at': datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'),
            'purpose': 'B1 补算：修复成功率 / 修复收敛轮数（零重跑，只读既有 artifact）',
            'definition_contract': 'reports/diagnostics/task_b1kpi_contract.md',
            'layers': {
                'L1': '结构层（schema/contract 合法）——「修复成功率」只指这一层',
                'L2': '产出层（修成 spec 还是 clarify）',
                'L3': '语义层（spec_fidelity 全对，取成绩单 category，不重算）',
            },
            'runs': rows,
            'checks_failed': [{'id': i, 'msg': m} for i, m in fails],
            'notes': notes,
            'warnings': [
                'v6c 与 v7 是不同卷（55 vs 64 条）⇒ 两组的任何比率**不可相减**，只可并列陈述。',
                'L1 接近 100% 是「闸严格度」的产物：所有 spec 题首轮结构校验全部未过，'
                '首轮通过的清一色是澄清题。它不证明模型会建模。',
                'L3 才是模型能力那一面，与成绩单 TSR 同源（同一 category 字段）。',
            ],
        }
        p = a.json if os.path.isabs(a.json) else os.path.join(HERE, a.json)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8', newline='') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('JSON -> %s' % _rel(p))

    return 0 if not fails else 2


if __name__ == '__main__':
    sys.exit(main())
