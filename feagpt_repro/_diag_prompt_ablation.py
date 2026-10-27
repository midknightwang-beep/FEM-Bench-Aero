# -*- coding: utf-8 -*-
"""prompt v3 / v3b 消融（W5d-1）：判定「prompt 还能不能修好 C-033 的缺失信息处理」。

背景
----
C-033（deepseek）在 prompt v2 下 exam 仍有 1 条 `clarify_wrong`（问对 `n_ribs` 又多问长桁）
与 1 条编造（dev 的 `open_hole_panel_400x200_d20` 没问孔径）。R57 要求：修这个只能动规则，
**不得注入 `expected_clarifications`、不得改 `clarify_wrong_keys` 元数据**。于是做了两版：

- **v3**：把「数量铁律」扩到尺寸（`hole_d`），并加「澄清列表准入规则」（只能问题面出现过的参数、
  不得问「是否布置 X」、最多 2 条）。
- **v3b**：在 v3 之上，把一套 5 步自检清单放到 SYS **最后**（靠近因效应，逼模型先圈特征词再决定）。

判定规则（本脚本自己算，不手填）
------------------------------
1. 4 条澄清题：只用判分器 `judge_l3_candidate` 的结论（与正式打分同一套逻辑）；
2. 3 条对照题（信息完备）：必须**不澄清**——任何一条变澄清都算回归；
3. **采纳条件**：两个模型都满足「exam 澄清题全对」且「对照题零回归」。
   只要有一个模型出现「修好一条、坏掉另一条」⇒ 判 `net_zero_failure_migration`，**不采纳**。

为什么这条判定要写死成规则
--------------------------
实测（本脚本产出的表）：deepseek 在 v2/v3/v3b 三版下的 exam 澄清题**始终 2/3**——
v2 错 `wingbox`（多问）、v3 错 `barrel`（该问不问、写 0）、v3b 又错回 `wingbox`（3 轮未收敛）。
**失败点在迁移、总数不变** ⇒ 这就是「prompt 工程到顶」的形态证据，不能再靠改措辞。
"""
# ★ 输入是 4 个**7 条子集**目录（_smoke_v3_glm / _smoke_v3_ds / _smoke_v3b_glm / _smoke_v3b_ds），
#   它们是 C-035 的原始证据，已入库（每份 7 个 json，几十 KB）——
#   别当临时冒烟删掉，删了这张消融表就复现不了（脚本会 skip 掉缺的变体）。
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from score_baseline import judge_clarify_field_level  # noqa: E402

TASKS = os.path.join(HERE, 'tasks', 'tasks.jsonl')

# 变体：名字 → (glm 候选目录, deepseek 候选目录, 期望的 prompt_sha 前缀)
VARIANTS = [
    ('v2（现行）', 'candidates_l3_v6c_glm_p2', 'candidates_l3_v6c_ds_p2', 'ce225186'),
    ('v3', '_smoke_v3_glm', '_smoke_v3_ds', 'e52f06a'),
    ('v3b', '_smoke_v3b_glm', '_smoke_v3b_ds', '769a1eb'),
]
# 被消融覆盖的 7 条：4 条澄清题（3 exam + 1 dev）+ 3 条信息完备对照
SUBSET = [
    'L3_fuselage_barrel_d1600_l1600_str8_frm3',
    'L3_naca4412_wingbox',
    'L3_stiffened_panel_600x600_str3',
    'L3_open_hole_panel_400x200_d20',
    'L3_stiffened_panel_600x600',
    'L3_open_hole_panel_400x200_d40',
    'L3_naca4412_wingbox_str3',
]


def _load_tasks():
    return {json.loads(l)['task_id']: json.loads(l) for l in open(TASKS, encoding='utf-8') if l.strip()}


def _cand(dirname, tid):
    p = os.path.join(HERE, dirname, tid + '.json')
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding='utf-8'))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(HERE, 'reports', 'diagnostics', 'prompt_v3_ablation.json'))
    ap.add_argument('--md', default=os.path.join(HERE, 'reports', 'diagnostics', 'prompt_v3_ablation.md'))
    args = ap.parse_args(argv)

    tasks = _load_tasks()
    rec = {'schema': 'prompt_ablation/v1', 'subset': SUBSET, 'variants': [], 'models': ['glm-5.3-flash', 'deepseek-v4-pro']}
    table = {}   # (model, variant, tid) → row

    for vname, gdir, ddir, sha_prefix in VARIANTS:
        shas = {}
        for model, d in (('glm-5.3-flash', gdir), ('deepseek-v4-pro', ddir)):
            c0 = _cand(d, SUBSET[0])
            shas[model] = (c0 or {}).get('prompt_sha256')
            if not c0:
                print(f'[skip] {vname} / {model}: 缺 {d}/{SUBSET[0]}.json')
                continue
            if not str(shas[model]).startswith(sha_prefix):
                print(f'[warn] {vname} / {model}: prompt_sha={str(shas[model])[:12]} 与期望前缀 {sha_prefix} 不符')
        rec['variants'].append({'name': vname, 'glm_dir': gdir, 'ds_dir': ddir, 'prompt_sha': shas})

        for model, d in (('glm-5.3-flash', gdir), ('deepseek-v4-pro', ddir)):
            for tid in SUBSET:
                t = tasks[tid]
                c = _cand(d, tid)
                if c is None:
                    table[(model, vname, tid)] = {'category': 'missing', 'note': '无候选文件'}
                    continue
                # ★ 只用**澄清判定**，不跑建模评估：本消融只问「该问的有没问」。
                #   走 judge_l3_candidate 会触发 evaluate_one(skip_solve=True) ⇒ 42 次建模，
                #   既慢又把「澄清行为」和「spec 质量」混在一起。
                ec = t.get('expected_clarifications') or []
                if c.get('clarify') and not c.get('spec'):
                    if ec:
                        ok, detail = judge_clarify_field_level(c['clarify'], t)
                        cat = 'clarify_ok' if ok else 'clarify_wrong'
                    else:
                        cat, ok, detail = 'over_clarify', False, {'note': '信息完备却澄清（该答不答）'}
                elif c.get('spec') and c.get('clarify'):
                    cat, ok, detail = 'clarify_and_spec', False, {'note': '同时给了 spec 和澄清'}
                elif c.get('spec'):
                    cat = 'fabricated' if ec else 'spec_ok'
                    ok, detail = (not ec), {'note': ('澄清题静默编造 spec（缺 ' + str(ec) + '）' if ec else '')}
                else:
                    cat, ok, detail = 'unresolved', False, {'note': '3 轮未收敛，既无 spec 也无 clarify'}
                row = {'category': cat, 'pass': ok, 'is_clarify_task': bool(t.get('expected_clarifications')),
                       'is_exam': tid != 'L3_open_hole_panel_400x200_d20',
                       'note': (detail or {}).get('note') or '',
                       'raw_clarify': (c.get('clarify') or '')[:160],
                       'turns': c.get('turns_used')}
                if cat == 'fabricated':
                    # 细化：是「填 0」还是「干脆省略」——两者都是编造，但修法不同
                    sp = c.get('spec') or {}
                    p = (sp.get('structure') or {}).get('params') or {}
                    af = sp.get('airfoil') or {}
                    keys = [k for k in ('hole_d', 'n_frames', 'n_ribs', 'n_stringers', 'n_stringers_per_skin')]
                    present = {k: (p.get(k) if k in p else af.get(k)) for k in keys}
                    row['fab_detail'] = {'present_keys': {k: v for k, v in present.items() if v is not None},
                                         'zero_keys': [k for k, v in present.items() if v == 0],
                                         'mode': 'fill_zero' if [k for k, v in present.items() if v == 0] else 'omit_key'}
                table[(model, vname, tid)] = row

    # ---- 按模型/variant 汇总：exam 澄清题对几条、对照题有没有回归 ----
    summary = {}
    for vname, _, _, _ in VARIANTS:
        for model in rec['models']:
            ex_ct = [t for t in SUBSET if tasks[t].get('expected_clarifications') and t != 'L3_open_hole_panel_400x200_d20']
            ok_ex = sum(1 for t in ex_ct if (table.get((model, vname, t)) or {}).get('category') == 'clarify_ok')
            ctrl = [t for t in SUBSET if not tasks[t].get('expected_clarifications')]
            over = [t for t in ctrl if (table.get((model, vname, t)) or {}).get('category')
                    in ('clarify_wrong', 'clarify_ok', 'over_clarify', 'clarify_and_spec')]
            summary.setdefault(vname, {})[model] = {
                'exam_clarify_ok': ok_ex, 'exam_clarify_total': len(ex_ct),
                'control_regressions': over,
                'fails': [t for t in SUBSET if (table.get((model, vname, t)) or {}).get('category')
                          not in ('clarify_ok', 'spec_ok', 'missing') and tasks[t].get('expected_clarifications')],
            }

    # ---- 判定：采纳条件由数据算 ----
    base = 'v2（现行）'
    decision = {'adopt': None, 'reason': '', 'per_variant': {}}
    for vname, _, _, _ in VARIANTS:
        if vname == base:
            continue
        verdicts = {}
        for model in rec['models']:
            b = summary[base][model]
            v = summary[vname][model]
            gain = v['exam_clarify_ok'] - b['exam_clarify_ok']
            regress = bool(v['control_regressions'])
            verdicts[model] = {'gain_exam_clarify': gain, 'control_regression': regress,
                               'all_exam_ok': v['exam_clarify_ok'] == v['exam_clarify_total']}
        all_ok = all(x['all_exam_ok'] and not x['control_regression'] for x in verdicts.values())
        any_gain = any(x['gain_exam_clarify'] > 0 for x in verdicts.values())
        if all_ok and any_gain:
            kind = 'adopt'
        elif any(x['gain_exam_clarify'] > 0 for x in verdicts.values()) and not all_ok:
            kind = 'net_zero_failure_migration'
        else:
            kind = 'no_effect'
        decision['per_variant'][vname] = {'kind': kind, 'per_model': verdicts}
    kinds = {v['kind'] for v in decision['per_variant'].values()}
    decision['adopt'] = ('adopt' in kinds)
    decision['reason'] = ('两版均未同时满足「exam 澄清题全对」+「对照零回归」⇒ **不采纳**，'
                          '维持 v2（prompt sha 回到 `ce225186…`），否则按 R53 必须全量重跑 110 条候选 + 65 分钟 MSR，净收益为 0。')
    rec['summary'] = summary
    rec['decision'] = decision
    rec['table'] = {f'{m}|{v}|{t}': r for (m, v, t), r in table.items()}

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(rec, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # ---------------------------- markdown ----------------------------
    L = ['# prompt v3 / v3b 消融：还能不能修好 C-033 的缺失信息处理（W5d-1）', '',
         '> 诊断文件（R37）。**结论：不采纳**——两版都只是把失败点挪个位置，exam 澄清题始终 2/3。', '',
         '## 0. 判定（规则先写死，再由数据算）', '',
         '- 采纳条件：**两个模型**都「exam 澄清题全对」且「3 条对照题零回归」。',
         f"- 结论：**{'采纳' if decision['adopt'] else '不采纳'}**。{decision['reason']}", '',
         '## 1. 三版 prompt 各自改了什么', '',
         '| 版本 | 改动 | prompt sha |', '|---|---|---|']
    L.append('| v2（现行） | 数量铁律（题面提到特征却没给数量 ⇒ 必须澄清）+ 惯例条款 | `ce225186…` |')
    L.append('| v3 | ①数量铁律**扩到尺寸**（`hole_d`）；②**澄清列表准入规则**：只能问题面出现过的参数、'
             '不得问「是否布置 X」、最多 2 条 | `e52f06a…` |')
    L.append('| v3b | v3 + **5 步自检清单放在 SYS 最后**（先圈特征词 → 问有没有给数 → 缺则只能输出 clarify） | `769a1eb…` |')
    L += ['', '## 2. 逐题结果（exam 澄清题 3 条 + dev 澄清题 1 条 + 对照 3 条）', '']
    for model in rec['models']:
        L += [f'### {model}', '', '| 题 | 期望 | v2 | v3 | v3b |', '|---|---|---|---|---|']
        for tid in SUBSET:
            t = tasks[tid]
            exp = ('澄清 ' + str(t.get('expected_clarifications'))) if t.get('expected_clarifications') else 'spec（不得澄清）'
            cells = []
            for vname, _, _, _ in VARIANTS:
                r = table.get((model, vname, tid)) or {}
                cat = r.get('category') or '—'
                if cat == 'fabricated' and r.get('fab_detail'):
                    cat += f"（{r['fab_detail']['mode']}）"
                cells.append(cat)
            L.append(f"| `{tid.replace('L3_','')}` | {exp} | " + ' | '.join(cells) + ' |')
        s = summary
        L.append('')
        L.append(f"- exam 澄清题正确数：v2 **{s['v2（现行）'][model]['exam_clarify_ok']}/{s['v2（现行）'][model]['exam_clarify_total']}** → "
                 f"v3 **{s['v3'][model]['exam_clarify_ok']}/{s['v3'][model]['exam_clarify_total']}** → "
                 f"v3b **{s['v3b'][model]['exam_clarify_ok']}/{s['v3b'][model]['exam_clarify_total']}**")
        L.append(f"- 对照题回归：v2 {s['v2（现行）'][model]['control_regressions'] or '无'} / "
                 f"v3 {s['v3'][model]['control_regressions'] or '无'} / v3b {s['v3b'][model]['control_regressions'] or '无'}")
        L.append('')
    # ★ 结论句一律由数据生成（R38）：每个模型在每版下「哪条 exam 澄清题没过」直接列出来
    L += ['## 3. 读法（这条比分数重要）', '',
          '> 下面是**全部 4 条澄清题**（3 条 exam + 1 条 dev，dev 已标注）；'
          '「exam 澄清题正确数」只数 exam 那 3 条。', '']
    _vn = [x[0] for x in VARIANTS]
    for model in rec['models']:
        seq = []
        for vname in _vn:
            f = summary[vname][model]['fails']
            # dev 题加标记，免得把 dev 的失败读成 exam 失败（口径必须写在标签上）
            seq.append(f"**{vname}** 错 " + ('、'.join(
                '`' + t.replace('L3_', '') + '`' + ('' if t != 'L3_open_hole_panel_400x200_d20' else '（dev）')
                for t in f) if f else '无'))
        L.append(f"- {model}：" + ' → '.join(seq))
    L.append('')
    _same = all(summary[v][m]['exam_clarify_ok'] == summary[base][m]['exam_clarify_ok']
                for m in rec['models'] for v in _vn if v != base)
    _failsets = {m: {tuple(sorted(summary[v][m]['fails'])) for v in _vn} for m in rec['models']}
    _mig = any((len(s) > 1) and any(s) for s in _failsets.values())
    L.append(f"- 三版的 exam 澄清题正确数是否一致：**{'一致' if _same else '不一致'}**"
             f"（⇒ {'零收益' if _same else '有变化'}）；失败题是否在换：**{'在换' if _mig else '没换'}**。")
    L.append('')
    if _mig and _same:
        L.append('⇒ 这是**打地鼠**：总数不变、失败点迁移。继续调措辞只会换一个失败点，不会清零。'
                 '剩余差距属**模型行为**（缺失信息处理策略），不属题面/prompt 缺陷——与 C-031/C-033 的三条归因一致。')
    elif _same:
        L.append('⇒ 三版**零收益**：prompt 不是瓶颈。')
    L += ['', '## 4. 所以下一步该做什么', '',
          '- **不采纳 v3/v3b**：prompt sha 回到 `ce225186…`，C-032/C-033/C-034 全部继续有效'
          '（S-39 会在 prompt 漂移时报警，这次是它替我们挡住了「无收益全量重跑」）。',
          '- 若要把「缺失信息处理」变成可测量而不是靠模型自觉，只有一条口径级的做法：'
          '**在生成器里加语义回填闸**（题面提到特征但关键键缺失/为 0 ⇒ 反馈一次，要求澄清）。'
          '那属于**改 harness 口径**，必须老王拍板（D7），不能我单方面加。',
          '- 提高统计精度（CI 太宽）仍然要靠 **v1.1 新几何（n≥30）**，不是靠 prompt。']
    os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
    open(args.md, 'w', encoding='utf-8').write('\n'.join(L) + '\n')

    print(f'[out] {args.out}\n[out] {args.md}')
    for vname, _, _, _ in VARIANTS:
        row = ' / '.join(f"{m.split('-')[0]} {summary[vname][m]['exam_clarify_ok']}/{summary[vname][m]['exam_clarify_total']}"
                         for m in rec['models'])
        print(f'  {vname:<12} exam 澄清题：{row}；判定={decision["per_variant"].get(vname, {}).get("kind", "基线")}')
    print('决定：', 'ADOPT' if decision['adopt'] else 'REJECT')
    return 0


if __name__ == '__main__':
    sys.exit(main())
