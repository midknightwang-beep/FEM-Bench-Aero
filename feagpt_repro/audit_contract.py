# -*- coding: utf-8 -*-
"""audit_contract.py — W5c 契约试建闸（专家第八轮 §3.2 点名项）

问题：C-028 里有 3 条 exam 任务 TSR PASS、SFR PASS，但**全链 MSR 失败**，失败类 `contract`
（R19 试建闸未过）。这 3 条到底是「模型参数错」还是「builder 不支持这个合法组合」？
只看候选分不出来——必须把 **gold spec 也过同一道闸**：

  gold 能建，候选不能建  ⇒ 模型 spec 质量问题（判 model，合理）
  gold 也不能建         ⇒ **任务/契约缺陷**（判 harness），这类题不该计入模型失败

这就是本脚本的唯一职责。不起求解器，秒级。

用法：
  python audit_contract.py --cases ../FEM-Bench-Aero/modeling \
      --tasks reports/papers/tasks_v6c.jsonl --out reports/contract_audit_v6c.json

退出码：0 = 全部 gold 可建；1 = 有 gold 建不出来的任务（属任务缺陷，须单独登记）
"""
import argparse
import json
import os
import sys
from _paths import rel   # T-A11a：跨盘符安全（见 _paths.py）

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FEA = os.path.join(os.path.dirname(HERE), 'FEM-Bench-Aero')


def _get(argv, flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


def try_build(spec, tag):
    """返回 (ok, err)。两段式：先试 raw，再试 normalize 后的——因为候选走的是 raw 路径，
    gold 在 make_tasks 里走过 normalize；两个都试才分得清是「模型错」还是「口径错」。"""
    from feagpt.spec import FEASpec
    try:
        FEASpec.from_dict(json.loads(json.dumps(spec)))
        return True, None, tag
    except Exception as e:
        err = f'{type(e).__name__}: {e}'
    try:
        from make_tasks import normalize_spec
        fam = ((spec.get('structure') or {}).get('family')) or ''
        norm = normalize_spec(spec, fam)
        FEASpec.from_dict(json.loads(json.dumps(norm)))
        return True, None, tag + '+normalize'
    except Exception as e:
        return False, err + ' | normalize 后仍失败: ' + f'{type(e).__name__}: {e}', tag


def main():
    argv = sys.argv[1:]
    cases_dir = _get(argv, '--cases', os.path.join(FEA, 'modeling'))
    tasks_path = _get(argv, '--tasks', os.path.join(HERE, 'reports', 'papers', 'tasks_v6c.jsonl'))
    out_path = _get(argv, '--out', os.path.join(HERE, 'reports', 'contract_audit_v6c.json'))

    rows = []
    if os.path.exists(tasks_path):
        rows = [json.loads(l) for l in open(tasks_path, encoding='utf-8') if l.strip()]
    l3 = [r for r in rows if r.get('input_level') == 'L3']
    print(f'== 契约试建闸（gold）：{len(l3)} 条 L3 任务 ==')

    results = []
    for t in l3:
        cid = t['task_id'][3:]                      # 去掉 'L3_'
        p = os.path.join(cases_dir, cid, 'spec.json')
        rec = {'task_id': t['task_id'], 'exam_stratum': t.get('exam_stratum'), 'exists': os.path.exists(p)}
        if not rec['exists']:
            rec.update(ok=False, err='spec.json 缺失', class_='missing_gold')
        else:
            gold = json.load(open(p, encoding='utf-8'))
            ok, err, how = try_build(gold, 'raw')
            rec.update(ok=ok, err=err, built_via=how if ok else None,
                       class_=('ok' if ok else 'harness_defect'))
        results.append(rec)

    bad = [r for r in results if not r['ok']]
    n_ok = len(results) - len(bad)
    exam_bad = [r for r in bad if r['exam_stratum']]
    print(f'  gold 可建 {n_ok}/{len(results)}；不可建 {len(bad)}（其中 exam {len(exam_bad)}）')
    for r in bad:
        print(f"    [{'exam ' + str(r['exam_stratum']) if r['exam_stratum'] else 'dev  '}] "
              f"{r['task_id']:<44} {r['class_']:<15} {str(r['err'])[:150]}")

    if n_ok == len(results):
        print('  结论：全部 gold 可建 ⇒ 候选的 contract 失败一律判 model（合理）')
    else:
        print('  ★ 结论：存在 gold 建不出来的任务 ⇒ 这些题的 contract 失败属 **任务/契约缺陷（harness）**，'
              '不得算进模型能力；必须登记后修 builder 或改卷子')

    report = {
        'note': 'W5c 契约试建闸（专家第八轮 §3.2）：把 gold spec 过同一道 R19 试建闸，'
                '用来区分「模型 spec 质量问题」与「builder 不支持这个合法组合」。'
                'gold 建不出来 ⇒ 该任务属 harness 缺陷，不应计入模型失败。不起求解器。',
        'tasks_path': rel(os.path.abspath(tasks_path)),
        'n_tasks': len(results), 'n_ok': n_ok, 'n_bad': len(bad),
        'n_bad_exam': len(exam_bad),
        'all_gold_buildable': n_ok == len(results),
        'per_task': results,
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
    json.dump(report, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\nreport ->', out_path)
    return 0 if n_ok == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
