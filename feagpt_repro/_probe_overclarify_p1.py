# -*- coding: utf-8 -*-
"""_probe_overclarify_p1.py — P-1「over-clarify 政策」影响面量化（只读，不改任何判据）

背景：`_audit_clarify_meta.py`（W5c-6d）第 ③ 条提出的政策问题至今未预注册：
「问对了 + 多问一句键名正确但不必要的字段」算 PASS 还是 FAIL？

本脚本只回答「如果改口径，会动多少条」，**不做任何判定、不写回任何 artifact**。
产物落 reports/diagnostics/（R27：诊断不得占用官方路径）。

口径（写死在这里，避免读的人自己猜）：
  · known_keys  = 全部 192 行 task 的 expected_clarifications ∪ clarify_wrong_keys
                  ∪ clarify_aliases 里的**纯 ASCII 标识符**（中文别名不计，因为
                  「多问一句中文」无法与「解释性措辞」区分，见 §3 的诚实边界）
  · mentioned   = 文本中按 **token 边界**命中的 known_keys（R70：_alias_hit 同款判据，
                  不用裸子串 —— 否则 `n_stringers` 会被 `n_stringers_per_skin` 吃掉）
  · over_ask    = mentioned − expected          （多问的键）
  · 对 L2：expected = [omitted_field]
  · 对 L3：expected = expected_clarifications

用法：venv 解释器
  "$PY" _probe_overclarify_p1.py --out reports/diagnostics/overclarify_p1.json \\
      --md reports/diagnostics/overclarify_p1.md
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from score_baseline import _alias_hit  # 判据只有一处实现，不复制（与 score_l2 同纪律）

TASKS = os.path.join(HERE, 'tasks', 'tasks.jsonl')
CAND = {
    'L3': {'glm': 'candidates_l3_v7_glm', 'ds': 'candidates_l3_v7_ds'},
    'L2': {'glm': 'candidates_l2_v7_glm', 'ds': 'candidates_l2_v7_ds'},
}


def load_tasks():
    rows = [json.loads(l) for l in open(TASKS, encoding='utf-8') if l.strip()]
    return {r['task_id']: r for r in rows}


def known_keys(tasks):
    """跨题已知键池（纯 ASCII）。

    ★ T-L27（2026-11-01）：本函数原先是这里的一份**拷贝**，判分侧（`score_baseline`）
      在 T-L27 里也需要同一个池 ⇒ 两处实现会漂移。改为直接调 `clarify_key_pool`，
      规则只有一处。行为等价（同样的三处来源 + 同样的 ASCII 过滤），已用重跑产物逐字节比对。
    """
    from score_baseline import clarify_key_pool
    return clarify_key_pool(list(tasks.values()))


def cand_text(c):
    cl = c.get('clarify')
    if isinstance(cl, list):
        return '\n'.join(str(x) for x in cl)
    if isinstance(cl, str):
        try:
            v = json.loads(cl)
            return '\n'.join(v) if isinstance(v, list) else str(v)
        except Exception:
            return cl
    return ''


def n_questions(c):
    """问句条数。★ clarify 是「字符串里装的 JSON 数组」（`'["a","b"]'`），
    首版按 `。；\\n` 切分得到的是**假分布**（把一句话的从句数成两条）
    ⇒ 必须 json.loads 后再取 len。解析不出数组的按 1 条算（宁少不多）。"""
    cl = c.get('clarify')
    if cl is None:
        return 0
    if isinstance(cl, list):
        return len(cl)
    try:
        v = json.loads(cl)
        return len(v) if isinstance(v, list) else 1
    except Exception:
        return 1


def mentioned_keys(text, keys):
    return [k for k in keys if _alias_hit(k, text)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(HERE, 'reports', 'diagnostics', 'overclarify_p1.json'))
    ap.add_argument('--md', default=os.path.join(HERE, 'reports', 'diagnostics', 'overclarify_p1.md'))
    a = ap.parse_args(argv)

    tasks = load_tasks()
    keys = known_keys(tasks)

    # ---------- L3：有 expected_clarifications 的题，逐模型看是否「多问」 ----------
    l3_tasks = [tid for tid, r in tasks.items()
                if r.get('input_level') == 'L3' and (r.get('expected_clarifications') or [])]
    l3 = {}
    for model, cdir in CAND['L3'].items():
        recs = []
        for tid in sorted(l3_tasks):
            p = os.path.join(HERE, cdir, tid + '.json')
            if not os.path.exists(p):
                recs.append({'task_id': tid, 'missing': True})
                continue
            c = json.load(open(p, encoding='utf-8'))
            r = tasks[tid]
            exp = list(r.get('expected_clarifications') or [])
            wrong = list(r.get('clarify_wrong_keys') or [])
            txt = cand_text(c)
            ment = mentioned_keys(txt, keys)
            over = [k for k in ment if k not in exp]
            recs.append({
                'task_id': tid,
                'family': r.get('family'),
                'exam_stratum': r.get('exam_stratum'),
                'expected': exp,
                'wrong_keys': wrong,
                'mentioned': ment,
                'over_ask': over,
                'has_spec': bool(c.get('spec')),
                'clarify_text': txt[:400],
                'n_questions': n_questions(c),
            })
        l3[model] = recs

    # ---------- L2：expected = [omitted_field] ----------
    # ★ 2026-10-30 P-1 踩坑：`l2_omit_map.json` 的键是**不带 `L2_` 前缀**的 case 名
    #   （`fuselage_barrel_d1600_...`），首版直接 `omit.get('L2_...')` ⇒ 全部 None
    #   ⇒ expected 恒空 ⇒ `n_pass_with_extra` 恒 0、`n_extra_only` 虚高（51/43）。
    #   这类错「不报错、只给好看的数」，故下面加了与官方 `per_task.pass` 的自比断言。
    omit = {}
    mp = os.path.join(HERE, 'tasks', 'l2_omit_map.json')
    if os.path.exists(mp):
        raw = json.load(open(mp, encoding='utf-8'))
        for k, v in (raw.items() if isinstance(raw, dict) else []):
            if k.startswith('_'):
                continue
            omit[k] = v if isinstance(v, str) else (v.get('omitted_field') if isinstance(v, dict) else None)

    def omitted_of(tid):
        return omit.get(tid) or omit.get(tid[3:] if tid.startswith('L2_') else tid)

    l2 = {}
    for model, cdir in CAND['L2'].items():
        recs = []
        for fn in sorted(os.listdir(os.path.join(HERE, cdir))):
            if not fn.endswith('.json'):
                continue
            c = json.load(open(os.path.join(HERE, cdir, fn), encoding='utf-8'))
            tid = c.get('task_id') or fn[:-5]
            om = omitted_of(tid)
            exp = [om] if om else []
            txt = cand_text(c)
            ment = mentioned_keys(txt, keys)
            over = [k for k in ment if k not in exp]
            recs.append({
                'task_id': tid,
                'omitted_field': om,
                'mentioned': ment,
                'over_ask': over,
                'has_spec': bool(c.get('spec')),
                'hit_expected': bool(exp and ment and exp[0] in ment),
                'n_questions': n_questions(c),
            })
        l2[model] = recs

    # ---------- 自比断言：hit_expected 必须与官方 per_task.pass 一致 ----------
    # 官方 pass 就是 judge_clarify_field_level 的结果（L2 无 wrong_keys ⇒ 等价于「命中 expected」）。
    # 不一致 = 我的期望字段还原错了，此时本探针的任何统计都不可信 ⇒ 直接报错，不给数。
    selfcheck = {}
    for model in l2:
        sp = os.path.join(HERE, 'reports', f'l2_scores_v7_{model}.json')
        if not os.path.exists(sp):
            selfcheck[model] = {'skipped': 'no score file'}
            continue
        off = {r['task_id']: r['pass'] for r in json.load(open(sp, encoding='utf-8'))['per_task']}
        mism = [r['task_id'] for r in l2[model]
                if r['task_id'] in off and bool(r['hit_expected']) != bool(off[r['task_id']])]
        selfcheck[model] = {'n_compared': sum(1 for r in l2[model] if r['task_id'] in off),
                            'n_mismatch': len(mism), 'mismatch': mism[:10]}
    bad = [m for m, v in selfcheck.items() if v.get('n_mismatch')]
    if bad:
        print('[FATAL] 探针的 expected 还原与官方判分不一致：', json.dumps(selfcheck, ensure_ascii=False))
        return 2

    # ---------- 汇总 ----------
    def l3_sum(recs):
        return {
            'n_tasks': len(recs),
            'n_with_extra': sum(1 for r in recs if not r.get('missing') and r['over_ask']),
            'n_with_extra_and_hit': sum(1 for r in recs if not r.get('missing') and r['over_ask'] and r['mentioned']
                                        and all(e in r['mentioned'] for e in r['expected'])),
            'n_extra_hits_wrong_key': sum(1 for r in recs if not r.get('missing')
                                          and set(r['over_ask']) & set(r['wrong_keys'])),
        }

    def l2_sum(recs):
        return {
            'n_tasks': len(recs),
            'n_pass_with_extra': sum(1 for r in recs if r['hit_expected'] and r['over_ask']),
            'n_extra_only': sum(1 for r in recs if r['over_ask'] and not r['hit_expected']),
        }

    # ---------- 「条数上限」若被采纳，会打掉谁（P-1 选项 B 的代价） ----------
    # 口径：只统计**当前 PASS** 且 `n_questions > cap` 的题 —— 只有这些会翻成 FAIL。
    cap_impact = {'caps': [2, 3], 'by_model': {}}
    for model in ('glm', 'ds'):
        ent = {}
        # L2：官方 per_task.pass 就是 judge 结果
        sp2 = os.path.join(HERE, 'reports', f'l2_scores_v7_{model}.json')
        if os.path.exists(sp2):
            off = {r['task_id']: r['pass'] for r in json.load(open(sp2, encoding='utf-8'))['per_task']}
            for cap in cap_impact['caps']:
                flip = [r['task_id'] for r in l2[model]
                        if off.get(r['task_id']) and r['n_questions'] > cap]
                ent[f'L2_cap{cap}'] = {'n_flip': len(flip), 'flip': flip}
        # L3：用官方成绩单的 tsr_pass（澄清题的 tsr_pass 就是 judge 结果）
        sp3 = os.path.join(HERE, 'reports', f'baseline_scorecard_L3_v7_{model}.json')
        if os.path.exists(sp3):
            off = {r['task_id']: r['tsr_pass'] for r in json.load(open(sp3, encoding='utf-8'))['per_task']}
            for cap in cap_impact['caps']:
                flip = [r['task_id'] for r in l3[model]
                        if not r.get('missing') and off.get(r['task_id']) and r['n_questions'] > cap]
                ent[f'L3_cap{cap}'] = {'n_flip': len(flip), 'flip': flip}
        cap_impact['by_model'][model] = ent

    rec = {
        'note': ('P-1 over-clarify 政策影响面量化（只读）。判据用 score_baseline._alias_hit（R70 token 边界），'
                 'known_keys = 192 行 task 的 expected ∪ wrong_keys ∪ ASCII aliases。'
                 '本文件不改任何口径，只回答「如果改，会动多少条」。'),
        'known_keys': keys,
        'n_known_keys': len(keys),
        'l3': {'tasks_with_ec': l3_tasks, 'by_model': {m: l3[m] for m in l3},
               'summary': {m: l3_sum(l3[m]) for m in l3}},
        'l2': {'by_model': {m: l2[m] for m in l2}, 'summary': {m: l2_sum(l2[m]) for m in l2},
               'selfcheck_vs_official': selfcheck},
        'cap_impact': cap_impact,
        'honest_boundary': [
            '只统计**纯 ASCII 键名**的「多问」；中文措辞的多问（如「还想确认一下肋壁厚」）不计 ⇒ 本表是**下界**。',
            '★ 「同一文本里提到某键」≠「向用户提问该键」。本次 L2 命中的 4 条（glm 3 / ds 1）**已逐条人工复核，4/4 是假阳性**：'
            '模型写的是「题面给了 stringer_height/stringer_thickness/stringer_kind，但没给根数」= **解释上下文**，不是多问。'
            '⇒ 任何「按语义判多问」的判据都会误伤，这是 P-1 选 A（观测不罚）的主要依据。',
            '★ 条数（`n_questions`）必须 json.loads 后再取 len：`clarify` 是「字符串里装的 JSON 数组」，'
            '按标点切分会得到假分布（首版 glm 3 / ds 8 的假象就是这样来的）。',
            '★ `cap_impact` 只统计「当前 PASS 且超过上限」的题 —— 只有这些会翻 FAIL；非 PASS 的题不受上限影响。',
        ],
    }

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(rec, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    L = ['# P-1 over-clarify 影响面量化（只读探针）', '',
         f"- known_keys：**{len(keys)}** 个纯 ASCII 键名",
         f"- L3 有 `expected_clarifications` 的题：**{len(l3_tasks)}** 条", '',
         '## L3（判据：命中 expected 且不含 wrong_keys）', '',
         '| 模型 | 题数 | 有「多问」 | 多问且命中 expected | 多问撞上 wrong_keys |', '|---|---|---|---|---|']
    for m, s in rec['l3']['summary'].items():
        L.append(f"| {m} | {s['n_tasks']} | {s['n_with_extra']} | {s['n_with_extra_and_hit']} | {s['n_extra_hits_wrong_key']} |")
    L += ['', '## L2（判据：字面命中 omitted_field；L2 无 wrong_keys）', '',
          '| 模型 | 题数 | PASS 且「多问」 | 只多问未命中 expected |', '|---|---|---|---|']
    for m, s in rec['l2']['summary'].items():
        L.append(f"| {m} | {s['n_tasks']} | {s['n_pass_with_extra']} | {s['n_extra_only']} |")
    L += ['', '## 若采纳「问句条数上限」（P-1 选项 B 的代价）', '',
          '单位：**当前 PASS 且超过上限**的题数（只有这些会翻 FAIL）。', '',
          '| 层 | 上限 | glm | ds |', '|---|---|---|---|']
    for cap in rec['cap_impact']['caps']:
        for lv in ('L2', 'L3'):
            g = rec['cap_impact']['by_model']['glm'].get(f'{lv}_cap{cap}', {}).get('n_flip', '?')
            d = rec['cap_impact']['by_model']['ds'].get(f'{lv}_cap{cap}', {}).get('n_flip', '?')
            L.append(f'| {lv} | ≤{cap} | {g} | {d} |')
    L += ['', '> 读法：上限越严，**掉的全在 ds 一侧**（glm 一条都不掉）⇒ 用条数当阈值等于按模型调参，'
          '这正是 P-1 建议「只观测、不设罚」的第二个理由。']
    L += ['', '## L3 逐题（有「多问」的才列）', '',
          '| task | 模型 | expected | wrong_keys | over_ask | 命中 expected |', '|---|---|---|---|---|---|']
    for m in l3:
        for r in l3[m]:
            if r.get('missing') or not r['over_ask']:
                continue
            hit = all(e in r['mentioned'] for e in r['expected'])
            L.append('| `%s` | %s | %s | %s | %s | %s |' % (
                r['task_id'], m, r['expected'], r['wrong_keys'], r['over_ask'], hit))
    L += ['', '## 诚实边界', ''] + ['- ' + x for x in rec['honest_boundary']]
    os.makedirs(os.path.dirname(os.path.abspath(a.md)), exist_ok=True)
    open(a.md, 'w', encoding='utf-8').write('\n'.join(L) + '\n')

    print(f'[out] {a.out}')
    print(f'[out] {a.md}')
    print('L3 有 ec 的题:', len(l3_tasks))
    for m, s in rec['l3']['summary'].items():
        print('  L3', m, s)
    for m, s in rec['l2']['summary'].items():
        print('  L2', m, s)
    return 0


if __name__ == '__main__':
    sys.exit(main())
