# -*- coding: utf-8 -*-
"""_verify_tasks_v6c.py — 考卷 v6c 验收（W5c-2，专家第八轮 §5.1）

v6b → v6c 只允许两类改动（R32 补缺 + R36 split 语义），本脚本把「允许」写成断言，
**两端都守**（既防漏改，也防顺手改多了 —— 第八轮的教训是「总数对上 ≠ 复现对了」）：

  ① 4 条 NL 补缺：`str3_T` 补「缘条宽 30 mm」；`web1`/`web1_offcentre`/`web2` 补中间腹板位置
     （旧题面**完全没提**腹板，模型按 SYS prompt「未提 ⇒ []」正确输出却被判 fail）
  ② 6 条内插题 `split_v2: train → interpolation_test`（旧版只加 exam_stratum，任何只用
     split_v2 的下游工具都会当 train 用 ⇒ 泄漏）

其余一律不得变：L1/L2 140 条逐字节、L3 其余 45 条逐字节、exam 仍 25（6/13/6）。

用法：python _verify_tasks_v6c.py [--old reports/papers/tasks_v6b.jsonl]
退出码 0 = PASS，1 = FAIL（并列出每条违规）
"""
import json, sys, collections, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OLD = os.path.join(HERE, 'reports', 'papers', 'tasks_v6b.jsonl')
NEW = os.path.join(HERE, 'tasks', 'tasks.jsonl')

ALLOWED_NL_FIX = {
    'L3_naca4412_wingbox_str3_T': '缘条宽 30 mm',
    'L3_naca4412_wingbox_web1': '中间腹板',
    'L3_naca4412_wingbox_web1_offcentre': '中间腹板',
    'L3_naca4412_wingbox_web2': '中间腹板',
}
INTERP_NEW = {'L3_naca4412_wingbox', 'L3_naca4412_wingbox_n_ribs5_chord800',
              'L3_naca4412_wingbox_recombination_algorithm3', 'L3_naca4412_wingbox_size_skin2',
              'L3_naca4412_wingbox_size_span2400', 'L3_naca4412_wingbox_str3'}


def rd(p):
    return {json.loads(l)['task_id']: json.loads(l) for l in open(p, encoding='utf-8') if l.strip()}


def main():
    old, new = rd(OLD), rd(NEW)
    bad = []

    def chk(cond, msg):
        if not cond:
            bad.append(msg)
        print(('  [ok ] ' if cond else '  [BAD] ') + msg)

    print(f'旧 {len(old)} 行 / 新 {len(new)} 行')
    chk(set(old) == set(new), 'task_id 集合完全一致（165 条，不增不减）')

    changed = {k: sorted(kk for kk in set(old[k]) | set(new[k]) if old[k].get(kk) != new[k].get(kk))
               for k in old if old[k] != new[k]}
    chk(len(changed) == len(ALLOWED_NL_FIX) + len(INTERP_NEW),
        f'变化行数 = {len(ALLOWED_NL_FIX) + len(INTERP_NEW)}（实 {len(changed)}）')

    l12 = [k for k in old if old[k]['input_level'] != 'L3']
    chk(not [k for k in changed if k in l12], f'L1/L2 {len(l12)} 条逐字节未变（改了 {[k for k in changed if k in l12]}）')

    extra = set(changed) - set(ALLOWED_NL_FIX) - INTERP_NEW
    chk(not extra, f'无计划外变化行（多出 {sorted(extra)}）')

    keys_ok = {k: set(v) for k, v in changed.items()
               if set(v) - {'input', 'split_v2', 'split_reason'}}
    chk(not keys_ok, f'变化键只在 input/split_v2/split_reason 内（越界 {keys_ok}）')

    for tid, token in ALLOWED_NL_FIX.items():
        if tid not in changed:
            chk(False, f'{tid} 应有 NL 补缺但没变')
            continue
        o, n = old[tid]['input']['nl'], new[tid]['input']['nl']
        chk(token in n and token not in o, f'{tid} 题面新增「{token}」（旧题面无此依据）')
        # 「只追加不改写」的硬判据：diff 里不得出现 delete/replace（防顺手重写题面 ⇒ 难度漂移）
        import difflib
        ops = [tag for tag, *_ in difflib.SequenceMatcher(None, o, n).get_opcodes() if tag != 'equal']
        chk(set(ops) <= {'insert'},
            f'{tid} 题面只做插入不改写（opcodes {ops}，长度 {len(o)}→{len(n)}）')

    interp_bad = []
    for tid in INTERP_NEW:
        o, n = old[tid]['split_v2'], new[tid]['split_v2']
        if not (o == 'train' and n == 'interpolation_test'):
            interp_bad.append(f'{tid}: {o}→{n}')
    chk(not interp_bad, f'6 条内插题 split_v2: train → interpolation_test（异常 {interp_bad}）')

    # 内插集合与 exam_stratum 必须一一对应（R36：不得再有「exam 却 split=train」）
    new_interp = {k for k, t in new.items() if t.get('exam_stratum') == 'interpolation'}
    chk(new_interp == INTERP_NEW, f'interpolation 集合一致（差集 {new_interp ^ INTERP_NEW}）')
    still_train_exam = [k for k, t in new.items()
                        if t['input_level'] == 'L3' and t.get('exam_stratum') and t['split_v2'] == 'train']
    chk(not still_train_exam, f'无「exam 但 split_v2=train」的行（{still_train_exam}）')

    strata = collections.Counter(t.get('exam_stratum') for t in new.values() if t['input_level'] == 'L3')
    chk(strata.get('boundary') == 6 and strata.get('extrapolation') == 13
        and strata.get('interpolation') == 6 and strata.get(None) == 30,
        f'exam 25 = 6/13/6，dev 30（实 {dict(strata)}）')

    splits = collections.Counter(t['split_v2'] for t in new.values() if t['input_level'] == 'L3')
    chk(splits.get('train') == 13, f'纯 train 池 = 13（实 {splits.get("train")}；S-24 用它）')

    # R33 冻结闸（两端口径）：exam 必须 0 违规；非 exam 只允许**已登记**的 R41 违规，
    # 且 task_id 集必须与白名单逐字相等（白名单只许缩小，防「新缺陷被静默吸收」）。
    PAPER = os.path.join(HERE, 'reports', 'papers', 'tasks_v6c.jsonl')
    from r32_audit import KNOWN_NONEXAM_VIOL   # 唯一出处，见 r32_audit.py 顶部注释
    r_exam = subprocess.run([sys.executable, os.path.join(HERE, 'r32_audit.py'),
                             '--tasks', PAPER, '--scope', 'exam'],
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    chk(r_exam.returncode == 0, 'R32/R41 审计 exam 范围 0 违规（R33 冻结闸·第一端）')
    if r_exam.returncode != 0:
        print(r_exam.stdout[-1500:])
    audit_json = os.path.join(HERE, 'reports', 'r32_audit_v6c.json')
    subprocess.run([sys.executable, os.path.join(HERE, 'r32_audit.py'),
                    '--tasks', PAPER, '--scope', 'all', '--out', audit_json],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
    try:
        got_viol = set(json.load(open(audit_json, encoding='utf-8'))['violations_by_task'])
    except Exception:
        got_viol = {'<读不回>'}
    chk(got_viol == KNOWN_NONEXAM_VIOL,
        f'R32/R41 审计 非 exam 违规集 == 白名单（R33 第二端；实 {sorted(got_viol)}）')

    print('\nVERDICT:', 'PASS' if not bad else f'FAIL（{len(bad)} 项）')
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
