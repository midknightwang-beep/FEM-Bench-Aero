# -*- coding: utf-8 -*-
"""_audit_clarify_meta.py — 澄清判分元数据自洽审计（W5c-6d 新发现，P1 待拍板）

起因：C-033（deepseek prompt-v2）在 `L3_naca4412_wingbox` 上被判 `clarify_wrong`，
但它的澄清文本**第一条就命中了期望别名**（`请给出翼肋数量 n_ribs`），第二条问长桁
用了 `n_stringers_per_skin` —— 而这**是翼盒族的正确键名**（R34：翼盒用
`n_stringers_per_skin`，柱壳/加筋板用 `n_stringers`）。
而该任务的 `clarify_wrong_keys` 里写着 `['n_stringers_per_skin']`。

三件事必须分开说清楚（结论不因此改动本轮任何数字，属于「记录缺陷、下轮定夺」）：
  ① **元数据标签错**：翼盒题的「错族键」应是 `n_stringers`（柱壳/板的键），
     把本族正确键登记成错族键，判分理由会指向错误的方向；
  ② **匹配方式有隐患**：`judge_clarify_field_level` 用子串 `in` 判错族键
     ⇒ 若把 `n_stringers` 登记为错族键，它会在 `n_stringers_per_skin` 里**命中**，
     把正确答案判错（与 R17「单字关键词不得作为通过依据」同源）；
  ③ **政策未预注册**：「问对了 + 多问一句不必要但键名正确的」算不算 FAIL，
     RUBRIC 没有写死。这条不先拍板，任何一端改动都是事后改判分（R18）。

用法：venv 解释器 `python _audit_clarify_meta.py`
产物：reports/diagnostics/clarify_meta_audit_v6c.json / .md
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = os.path.join(HERE, 'tasks', 'tasks.jsonl')
OUT_DIR = os.path.join(HERE, 'reports', 'diagnostics')

# R34 键名契约：每族的长桁数键（唯一合法键）
FAMILY_STRINGER_KEY = {
    'wingbox': 'n_stringers_per_skin',
    'fuselage_barrel': 'n_stringers',
    'stiffened_panel': 'n_stringers',
    'open_hole_panel': None,
}


def main(argv=None):
    # ★ 探针输出名必须带里程碑标签且支持 --out/--md（既有纪律，非本脚本特例）：
    #   R26 要求「command 里的输出路径 == artifact」，写死路径的脚本无法进 CLAIMS。
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(OUT_DIR, 'clarify_meta_audit_v6c.json'))
    ap.add_argument('--md', default=os.path.join(OUT_DIR, 'clarify_meta_audit_v6c.md'))
    ap.add_argument('--tasks', default=TASKS)
    _a = ap.parse_args(argv)
    rows = [json.loads(l) for l in open(_a.tasks, encoding='utf-8') if l.strip()]
    findings = []
    for r in rows:
        ec = r.get('expected_clarifications') or []
        if not ec:
            continue
        fam = r.get('family')
        own = FAMILY_STRINGER_KEY.get(fam)
        wk = r.get('clarify_wrong_keys') or []
        al = r.get('clarify_aliases') or []
        al_text = ' '.join(al) if isinstance(al, list) else str(al)
        wrong_as_own = [k for k in wk if own and k == own]
        # 子串隐患：某个错族键是「本族正确键」或「期望别名的子串」⇒ 正确答案会被误杀
        substr_hazard = [k for k in wk
                         if (own and k != own and k in own) or (k in al_text)]
        if wrong_as_own or substr_hazard:
            findings.append({
                'task_id': r['task_id'], 'family': fam,
                'expected_clarifications': ec,
                'clarify_wrong_keys': wk,
                'clarify_aliases': al,
                'family_correct_stringer_key': own,
                'wrong_key_is_own_family_key': wrong_as_own,
                'substring_hazard': substr_hazard,
                'is_exam': bool(r.get('exam_stratum')),
            })

    rec = {
        'note': ('澄清判分元数据自洽审计（W5c-6d）。判据来源：R34 键名契约（翼盒用 '
                 'n_stringers_per_skin；柱壳/加筋板用 n_stringers）+ R17（错族键名 ⇒ FAIL）。'
                 '本文件**只记录缺陷、不改本轮任何数字**（R18：判分口径改动必须先预注册）。'),
        'n_ec_tasks': sum(1 for r in rows if r.get('expected_clarifications')),
        'n_findings': len(findings),
        'n_findings_exam': sum(1 for f in findings if f['is_exam']),
        'findings': findings,
        'policy_open_question': ('「问对了 + 多问一句键名正确但不必要的问题」算 PASS 还是 FAIL？'
                                 'RUBRIC 未预注册。当前实现走 R19 的严格一侧（含任何错族键即 FAIL），'
                                 '但把本族正确键当错族键用，理由写错了。'),
        'do_not_do': ('不得为了让 C-033 从 22/25 变 23/25 而在本轮改元数据 —— 那是事后改判分（R18）。'
                      '正确顺序：老王先拍板 over-clarify 政策 ⇒ 修元数据 + 把子串匹配改成 token 边界匹配'
                      '⇒ 重打分（两模型同规格重打）⇒ 旧数字留档（D10）。'),
    }
    jp = _a.out
    os.makedirs(os.path.dirname(os.path.abspath(jp)), exist_ok=True)
    json.dump(rec, open(jp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    L = ['# 澄清判分元数据审计（v6c，W5c-6d）', '',
         f"- 有 `expected_clarifications` 的题：**{rec['n_ec_tasks']}** 条",
         f"- 命中缺陷：**{rec['n_findings']}** 条（其中 exam **{rec['n_findings_exam']}** 条）", '',
         '| task_id | family | 期望字段 | 现在的 clarify_wrong_keys | 本族正确键 | 问题 |',
         '|---|---|---|---|---|---|']
    for f in findings:
        probs = []
        if f['wrong_key_is_own_family_key']:
            probs.append('**把本族正确键登记成错族键**')
        if f['substring_hazard']:
            probs.append('子串隐患：' + '、'.join(f['substring_hazard']))
        L.append('| `%s` | %s | %s | %s | `%s` | %s |' % (
            f['task_id'], f['family'], f['expected_clarifications'],
            f['clarify_wrong_keys'], f['family_correct_stringer_key'], '；'.join(probs)))
    L += ['', '## 待拍板', '', rec['policy_open_question'], '',
          '## 禁止做法', '', rec['do_not_do'], '']
    mp = _a.md
    os.makedirs(os.path.dirname(os.path.abspath(mp)), exist_ok=True)
    open(mp, 'w', encoding='utf-8').write('\n'.join(L))
    print(f'[out] {jp}\n[out] {mp}')
    print(f"命中缺陷 {len(findings)} 条（exam {rec['n_findings_exam']}）")
    for f in findings:
        print('  -', f['task_id'], '| own_key=', f['family_correct_stringer_key'],
              '| wrong_as_own=', f['wrong_key_is_own_family_key'],
              '| substr=', f['substring_hazard'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
