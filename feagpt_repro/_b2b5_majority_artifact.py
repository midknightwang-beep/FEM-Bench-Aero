#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T-B2B5 v4：k=3 多数表决并列 artifact 生成器

★ 这里**不做任何判定**：单遍判定走 judge_refuse.run()，k 遍聚合走
  judge_refuse_majority.merge()/majority_verdict()，指标一律走 judge_refuse.agg()。
  本文件只负责「把已经算好的东西摆成一张可引用的表」——
  任何一处自己重算，都会让 artifact 与判分器脱钩（第二处实现就是 bug）。

★ 三条口径约束（R54 / R77）沿用 v3：
  ① 两模型 prompt sha 必须相同，否则 problems 里报出来；
  ② 越界/对照各自一个分母，任何时候并列报，不相减；
  ③ 分母不等的那一项不出 Δ（本卷两模型分母相同，故 delta_allowed 全 True）。
★ 另加一条 v4 专属：**k 遍多数与单遍不是同一口径**，artifact 里必须同时留
  per_rep（三遍单次）与 k=3 结果，且写明「单遍数字不得与 k=3 混比」。
"""
import datetime
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge_refuse as J          # noqa: E402
import judge_refuse_majority as M  # noqa: E402

#: 模型 -> 三遍候选目录（第 1 遍是 v3 里被引用的那一遍，保持可追溯）
REPS = {
    'glm-5.3-flash': ['candidates_refuse_v3_glm',
                      'candidates_refuse_v3_glm_rep2',
                      'candidates_refuse_v3_glm_rep3'],
    'deepseek-v4-pro': ['candidates_refuse_v3_ds',
                        'candidates_refuse_v3_ds_rep2',
                        'candidates_refuse_v3_ds_rep3'],
}

TASKS = J.TASKS


def pairwise(rows_by_rep):
    """三遍两两一致率 + 三遍全一致率。用 verdict 判，不用「分对没分对」。"""
    ids = [r['task_id'] for r in rows_by_rep[0]]
    maps = [{r['task_id']: r['verdict'] for r in rows} for rows in rows_by_rep]
    out = {'n_tasks': len(ids), 'pairs': []}
    for i in range(len(maps)):
        for j in range(i + 1, len(maps)):
            same = sum(1 for k in ids if maps[i][k] == maps[j][k])
            out['pairs'].append({'a': i + 1, 'b': j + 1, 'n_agree': same,
                                 'pct': round(100.0 * same / len(ids), 1)})
    allsame = sum(1 for k in ids if len({m[k] for m in maps}) == 1)
    out['n_all_agree'] = allsame
    out['all_agree_pct'] = round(100.0 * allsame / len(ids), 1)
    return out


def main():
    tasks = J.load_tasks(TASKS)
    out = {
        'generated_at': datetime.datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z'),
        'purpose': 'T-B2B5 v4：越界拒答卷 k=3 多数表决（两模型并列）。'
                   '**与 v3 的单遍口径不可混比**：v3 每模型只跑一遍，'
                   '本表每模型跑三遍取多数；单遍数字仅作为稳定性证据保留在 per_rep。',
        'tasks': os.path.basename(TASKS),
        'n_tasks': len(tasks),
        'denominators': {'refuse': sum(1 for t in tasks if t['kind'] == 'refuse'),
                         'build': sum(1 for t in tasks if t['kind'] == 'build')},
        'by_model': {},
        'problems': [],
        'prompt_sha_by_model': {},
        'prompt_sha_consistent': True,
        'delta_allowed': {'refuse': True, 'build': True},
        'why_no_delta': {},
    }

    k_rows = {}
    for model, dirs in REPS.items():
        rows_by_rep, per_rep = [], []
        for d in dirs:
            if not os.path.isdir(os.path.join(HERE, d)):
                out['problems'].append('缺目录：%s' % d)
                continue
            rows, summ, _ = J.run(d, TASKS)
            rows_by_rep.append(rows)
            per_rep.append({'candidates': d,
                            'refuse_pct': summ['refuse']['pct'],
                            'over_refuse_pct': summ['kpi']['over_refuse_pct'],
                            'build_correct_pct': summ['kpi']['build_correct_pct'],
                            'prompt_sha256': J._prompt_sha_of(os.path.join(HERE, d))})
        if len(rows_by_rep) != len(dirs):
            out['problems'].append('%s 只跑到 %d/%d 遍' % (model, len(rows_by_rep), len(dirs)))
            continue

        shas = {p['prompt_sha256'] for p in per_rep}
        if len(shas) > 1:
            out['problems'].append('%s 各遍 prompt sha 不同：%s' % (model, shas))
        out['prompt_sha_by_model'][model] = per_rep[0]['prompt_sha256']

        rows_k, _meta = M.merge(rows_by_rep, tasks)
        summ_k = J.agg(rows_k)          # ★ 指标只走这一处
        k_rows[model] = rows_k
        out['by_model'][model] = {
            'candidates_per_rep': dirs,
            'prompt_sha256': per_rep[0]['prompt_sha256'],
            'per_rep': per_rep,
            'stability': pairwise(rows_by_rep),
            'refuse': summ_k['refuse'],
            'build': summ_k['build'],
            'kpi': summ_k['kpi'],
            'undecided': [r['task_id'] for r in rows_k if r['verdict'] == 'undecided'],
            'rows': rows_k,
        }

    if len(set(out['prompt_sha_by_model'].values())) > 1:
        out['prompt_sha_consistent'] = False
        out['problems'].append('两模型 prompt sha 不同 ⇒ 分数不可比（R53）')

    # 跨模型：k=3 后的逐题分歧（同分母，可比；不做「谁更好」的结论）
    models = list(k_rows)
    if len(models) == 2:
        a, b = models
        ma = {r['task_id']: r['verdict'] for r in k_rows[a]}
        mb = {r['task_id']: r['verdict'] for r in k_rows[b]}
        dis = [{'task_id': k, 'kind': 'refuse' if k.startswith('G_') else 'build',
                a: ma[k], b: mb[k]} for k in ma if ma[k] != mb[k]]
        out['cross_model'] = {'compared': [a, b], 'n_disagree': len(dis), 'disagree': dis}

    out['n_problems'] = len(out['problems'])
    p = os.path.join(HERE, 'reports', 'diagnostics', 'refuse_scores_v4_majority.json')
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))
        f.write('\n')

    for m in out['by_model']:
        d = out['by_model'][m]
        print('%-18s 拒 %5.1f%%  过拒 %5.1f%%  建对 %5.1f%%  三遍全一致 %5.1f%%  undecided %d' % (
            m, d['kpi']['refusal_pct'], d['kpi']['over_refuse_pct'],
            d['kpi']['build_correct_pct'], d['stability']['all_agree_pct'],
            len(d['undecided'])))
    print('问题 %d 条；-> %s' % (out['n_problems'], p))


if __name__ == '__main__':
    main()
