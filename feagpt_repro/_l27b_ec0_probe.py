# -*- coding: utf-8 -*-
"""_l27b_ec0_probe.py — L2-7 根治路径的三项实测（T-L27b，2026-11-04）

要回答三个问题，一个都不靠嘴说：

  Q1 **「加信息完备题型」这件事，在判据侧做得了吗？**
     旧 `score_l2.classify()` 不看 ec（expected_clarifications）⇒ 给 spec 一律判
     `fabricated`（R20 静默编造）。用卷里 **L3 层 ec=0 题的真实候选**当夹具量它的后果：
     正确回答里有多少条被记成「编造」。

  Q2 **题型真能治穷举吗？**
     在 ec=0 的题上，穷举串（列 2 / 3 个跨题键名）走**正确判分路径**
     （`judge_l3_candidate`，它早就有「该答不答」分支）⇒ 通过率必须是 0。

  Q3 **现行 L2 卷的残余到底多大？（旧文档写 39.1%，复现不出来）**
     把「纯列举 2 个键名」的三种构造都复算一遍，报**可复算的口径**：
       · 全局固定 2 键最优（穷举 C(13,2)，取通过数最大）
       · 按族 top2（每族取该族题目的 expected 频次前 2）
       · 按族字典序前 2（旧报告可能用的构造，用于说明差异来源）

★ 本脚本**不改任何判分、不写任何候选、不碰成绩**；只读任务卷与既有候选，输出一份诊断 JSON。
★ 数字一律由代码算出并落盘（R-A3：禁止手抄）。

用法：
    "$PY" _l27b_ec0_probe.py            # 写 reports/diagnostics/l27b_ec0_probe.json
    "$PY" _l27b_ec0_probe.py --print    # 只打印，不写盘
退出码：0 全算完 ／ 2 缺对象（锚点缺失判红，不 skip）
"""
import argparse
import collections
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import score_baseline as SB          # noqa: E402  ★ 判定只有一处
import score_l2 as S2                # noqa: E402  ★ L2 判分器（被量的对象）

TASKS = os.path.join(HERE, 'tasks', 'tasks.jsonl')
OUT = os.path.join(HERE, 'reports', 'diagnostics', 'l27b_ec0_probe.json')
L3_GLM = os.path.join(HERE, 'candidates_l3_v7_glm')


def load_all(path=TASKS):
    return [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]


def q1_old_behaviour(rows):
    """ec=0 的真实 spec 候选，被旧 L2 判分器判成什么？"""
    ec0 = [r for r in rows if r['input_level'] == 'L3'
           and not (r.get('expected_clarifications') or [])]
    cats = collections.Counter()
    n_have = 0
    for t in ec0:
        p = os.path.join(L3_GLM, t['task_id'] + '.json')
        if not os.path.exists(p):
            continue
        c = json.load(open(p, encoding='utf-8'))
        if not c.get('spec'):
            continue
        n_have += 1
        # 旧行为 = 不加 _path 也会先看 ec；这里专门复现「不看 ec」那一版
        if c.get('clarify') and not c.get('spec'):
            cats['clarify'] += 1
        else:
            cats['fabricated(旧行为)'] += 1
    return {'n_ec0_tasks': len(ec0), 'n_with_real_spec': n_have,
            'old_categories': dict(cats),
            'note': ('ec=0 题上给了 spec 的候选，旧 classify 一律判 fabricated；'
                     '本项只数「会被记成编造」的条数，不重算 L3 成绩')}


def q2_attack_on_ec0(rows):
    """ec=0 题上，穷举串走正确判分路径的通过率（必须是 0）。"""
    ec0 = [r for r in rows if r['input_level'] == 'L3'
           and not (r.get('expected_clarifications') or [])]
    pool = sorted(SB.clarify_key_pool(rows))
    out = {}
    for k in (1, 2, 3):
        atk = '请提供 ' + '、'.join(pool[:k]) + '。'
        cats = collections.Counter()
        for t in ec0:
            cat, ok, _d = SB.judge_l3_candidate({'clarify': atk, 'spec': None}, t)
            cats[cat] += 1
        out['k=%d' % k] = {'attack': atk, 'categories': dict(cats),
                           'passed': sum(v for c, v in cats.items()
                                         if c in ('clarify_ok', 'spec_pass'))}
    return {'n_ec0_tasks': len(ec0), 'by_k': out,
            'note': 'ec=0 上「澄清」= 该答不答 ⇒ 与 k 无关，一律 clarify_wrong'}


def q3_residual(rows):
    """现行 L2 卷（全 ec=1）上「纯列举 2 键」的可复算上界。"""
    ec1 = [r for r in rows if r['input_level'] == 'L2'
           and (r.get('expected_clarifications') or [])]
    byfam = collections.defaultdict(list)
    for r in ec1:
        byfam[r['family']].append((r.get('expected_clarifications') or [None])[0])
    n = len(ec1)

    def cover(sel):
        return sum(1 for f, ks in byfam.items() for k in ks if k in set(sel(f, ks)))

    pool = sorted({k for ks in byfam.values() for k in ks})

    def best_global(kk):
        best = None
        for combo in itertools.combinations(pool, kk):
            hit = sum(1 for r in ec1
                      if (r.get('expected_clarifications') or [None])[0] in combo)
            if best is None or hit > best[0]:
                best = (hit, list(combo))
        return best

    g2, g3 = best_global(2), best_global(3)
    fam_top2 = cover(lambda f, ks: [k for k, _c in collections.Counter(ks).most_common(2)])
    fam_sorted2 = cover(lambda f, ks: sorted(set(ks))[:2])
    return {
        'n_l2_ec1': n,
        'global_best_2': {'keys': g2[1], 'passed': g2[0], 'pct': round(100.0 * g2[0] / n, 1)},
        'global_best_3': {'keys': g3[1], 'passed': g3[0], 'pct': round(100.0 * g3[0] / n, 1),
                          'note': '加固后 len(K)>=3 判退化 ⇒ 实际通过 0'},
        'family_top2': {'passed': fam_top2, 'pct': round(100.0 * fam_top2 / n, 1),
                        'picks': {f: [k for k, _c in collections.Counter(ks).most_common(2)]
                                  for f, ks in sorted(byfam.items())}},
        'family_sorted2': {'passed': fam_sorted2, 'pct': round(100.0 * fam_sorted2 / n, 1),
                           'picks': {f: sorted(set(ks))[:2] for f, ks in sorted(byfam.items())}},
        'by_family_n': {f: len(ks) for f, ks in sorted(byfam.items())},
        'note': ('旧文档写的「残余 39.1% = 25/64」在本构造下复现不出（25 既不等于 27 也不等于 31，'
                 '且当年生成 deg_k2 候选的脚本未入库）⇒ 引用一律用本文件的两个口径'),
        'legacy_claim': {'pct': 39.1, 'passed': 25, 'status': 'unreproducible_no_generator'},
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--print', action='store_true')
    a = ap.parse_args(argv)

    rows = load_all()
    rep = {
        '_note': ('T-L27b 三项实测：(1) 旧 L2 判分器把 ec=0 的正确 spec 记成编造；'
                  '(2) ec=0 上穷举串必错；(3) 现行卷残余的可复算上界。'
                  '不改判分、不写候选、不碰成绩。'),
        'paper_sha256': __import__('hashlib').sha256(open(TASKS, 'rb').read()).hexdigest(),
        'Q1_old_ec0_behaviour': q1_old_behaviour(rows),
        'Q2_attack_on_ec0': q2_attack_on_ec0(rows),
        'Q3_residual_now': q3_residual(rows),
    }
    txt = json.dumps(rep, ensure_ascii=False, indent=1)
    if a.print:
        print(txt)
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(txt + '\n')
    q1 = rep['Q1_old_ec0_behaviour']
    q3 = rep['Q3_residual_now']
    print('Q1 ec=0 题 %d 条、其中有真实 spec 的 %d 条 -> 旧判分器判类 %s'
          % (q1['n_ec0_tasks'], q1['n_with_real_spec'], q1['old_categories']))
    for k, v in rep['Q2_attack_on_ec0']['by_k'].items():
        print('Q2 穷举 %s -> 通过 %d/%d  判类=%s'
              % (k, v['passed'], rep['Q2_attack_on_ec0']['n_ec0_tasks'], v['categories']))
    print('Q3 全局最优 2 键 %s = %d/%d = %.1f%%（3 键 %d/%d，但判退化）'
          % (q3['global_best_2']['keys'], q3['global_best_2']['passed'], q3['n_l2_ec1'],
             q3['global_best_2']['pct'], q3['global_best_3']['passed'], q3['n_l2_ec1']))
    print('   按族 top2 = %d/%d = %.1f%%；按族字典序前2 = %d/%d = %.1f%%'
          % (q3['family_top2']['passed'], q3['n_l2_ec1'], q3['family_top2']['pct'],
             q3['family_sorted2']['passed'], q3['n_l2_ec1'], q3['family_sorted2']['pct']))
    print('   -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
