# -*- coding: utf-8 -*-
"""_n35_key_split_check.py — N-35 拍板 B（拆集合）的**零回归 + 等价性 + 正向增量**实测

四个 arm（其它一切不变：同批候选、同份 gold、同一个 `spec_fidelity`）
--------------------------------------------------------------------
  old        复刻 git HEAD 的行为：`EXEC_CONFIG_KEYS['extra']` 装 7 个元信息键，
             `DATASET_META_KEYS` 为空 ⇒ 那 7 键只在 `engineering_layer` 为真时豁免。
             L3 传 True（豁免）、L2 不传（**照判**）—— 这就是 N-35 的现场。
  new        拍板 B：`DATASET_META_KEYS['extra']` 装同样 7 键，**不依赖任何开关**；
             `EXEC_CONFIG_KEYS` 只留 mesh 7 + analysis 5。L3 与 old 等价，L2 不再判那 7 键。
  strip_meta 把 extra 7 键**从 gold 与候选里物理删掉**，再按 old 逻辑判
             ⇒ 语义上等价于「这些键根本不存在」。
  strip_all  把 extra 7 + mesh 7 = **14** 键都物理删掉
             ⇒ 这就是「打开 engineering_layer」的效果（= 选项 A：连 mesh 考点一起丢）。

★ 为什么不用「把 DATASET_META_KEYS 置空」当旧态：那样 L3 的 extra 键会失去豁免
   （它已从 EXEC_CONFIG_KEYS 移走）⇒ 那不是旧行为，比出来的差异是假的。
   旧态必须把 7 键**还回** EXEC_CONFIG_KEYS['extra']。

判据
----
  J0 `DATASET_META_KEYS['extra']` 与 `EXEC_CONFIG_KEYS['mesh']` **交集必须为空**
     （mesh 键进元信息集 = 考点静默消失）
  J1 **L3 零回归**：old 与 new 逐题 `pass` 全同（「没改坏」）
  J2 **等价性**（硬判据）：L2 informative 上 `new` 的通过集 == `strip_meta` 的通过集
     —— 「判分时跳过」必须与「这些键不存在」完全等价，逐题相同
  J3 **只增不减**：new 的通过集 ⊇ old 的通过集；不得有任何一条转红
  J4 **分支真的被触发**：old 的 `n_meta_skipped` 恒为 0，new 恒 > 0
  J5 **判据有对象**：全批次 old 里确有题被元信息键压住（否则在测空气）
  J6 **mesh 考点没有被顺手丢掉**：`strip_all` 的通过集必须 ⊋ `strip_meta`
     —— 若两者相等，说明 mesh 7 键在这批题上从来不影响结果，那 B 与 A 无差别，
     必须显式报告（而不是假装 B 有考点）

用法：
    "$PY" _n35_key_split_check.py
    "$PY" _n35_key_split_check.py --out reports/diagnostics/n35_key_split.json
退出码：0 全过 ／ 1 有判据红 ／ 2 环境错误
"""
import argparse
import copy
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import evaluate as E                                        # noqa: E402
from evaluate import case_id_of                             # noqa: E402

META = set(E.DATASET_META_KEYS['extra'])
MESH = set(E.EXEC_CONFIG_KEYS['mesh'])
ALL_STRIP = META | MESH
N_META, N_MESH = len(META), len(MESH)

BATCHES = [
    ('L3_v6c_glm', 'reports/papers/tasks_v6c.jsonl', 'candidates_l3_v7sysfix_glm',
     'headline 卷（C-032）'),
    ('L3_v6c_ds', 'reports/papers/tasks_v6c.jsonl', 'candidates_l3_v7sysfix_ds',
     'headline 卷（C-033）'),
    ('L2i_v4base_glm', 'tasks/tasks_l2_informative_v2.jsonl', 'candidates_l2i_v4base_glm',
     'informative 新 base'),
    ('L2i_v4base_ds', 'tasks/tasks_l2_informative_v2.jsonl', 'candidates_l2i_v4base_ds',
     'informative 新 base（ds）'),
    ('L2i_v4s_glm', 'tasks/tasks_l2_informative_v2.jsonl', 'candidates_l2i_v4s_glm',
     'informative 新 strict 第 1 遍'),
    ('L2i_v4s_ds', 'tasks/tasks_l2_informative_v2.jsonl', 'candidates_l2i_v4s_ds',
     'informative 新 strict 第 1 遍（ds）'),
    ('L2i_v4s2_glm', 'tasks/tasks_l2_informative_v2.jsonl', 'candidates_l2i_v4s2_glm',
     'informative 新 strict 第 2 遍'),
    ('L2i_v4s2_ds', 'tasks/tasks_l2_informative_v2.jsonl', 'candidates_l2i_v4s2_ds',
     'informative 新 strict 第 2 遍（ds）'),
]


def set_arm(arm):
    """切换判分口径，返回还原函数。arm ∈ {'old','new'}。"""
    saved_exec = copy.deepcopy(E.EXEC_CONFIG_KEYS)
    saved_meta = copy.deepcopy(E.DATASET_META_KEYS)
    E.DATASET_META_KEYS.clear()
    if arm == 'old':
        E.EXEC_CONFIG_KEYS['extra'] = set(META)
    elif arm == 'new':
        E.EXEC_CONFIG_KEYS.pop('extra', None)
        E.DATASET_META_KEYS['extra'] = set(META)
    else:
        raise ValueError(arm)

    def restore():
        E.EXEC_CONFIG_KEYS.clear()
        E.EXEC_CONFIG_KEYS.update(saved_exec)
        E.DATASET_META_KEYS.clear()
        E.DATASET_META_KEYS.update(saved_meta)
    return restore


def _strip(spec, keys):
    s = copy.deepcopy(spec)
    n = 0
    for holder in ('mesh', 'extra'):
        blk = s.get(holder)
        if isinstance(blk, dict):
            for k in list(blk):
                if k in keys:
                    del blk[k]
                    n += 1
    return s, n


def _load(task, cand_dir):
    tid = task['task_id']
    p = os.path.join(HERE, cand_dir, tid + '.json')
    if not os.path.exists(p):
        return None
    case_id = case_id_of(tid)
    gp = os.path.join(E.FEA, 'modeling', case_id, 'spec.json')
    if not os.path.exists(gp):
        return None
    gold = json.load(io.open(gp, encoding='utf-8'))
    gold.pop('workdir', None)
    cand = json.load(io.open(p, encoding='utf-8'))
    if 'spec' in cand and 'structure' not in cand:
        cand = cand['spec'] or {}
    cand.pop('workdir', None)
    return gold, cand


def _judge(task, gold, cand):
    mk, lk = E._input_mesh_load_keys(task)
    sf = E.spec_fidelity(cand, gold, task['family'], input_mesh_keys=mk, input_load_keys=lk,
                         engineering_layer=(task.get('input_level') == 'L3'))
    return {'pass': bool(sf['pass']), 'n_fail': sf['n_fail'],
            'failed': [f['field'] for f in (sf.get('failed') or [])],
            'n_meta_skipped': sf.get('n_dataset_meta_skipped', 0)}


def run_batch(tasks, cand_dir, arm, strip=None):
    """strip ∈ {None, 'meta', 'all'}：先物理删键，再按 arm 判。"""
    out = {}
    restore = set_arm(arm)
    try:
        for t in tasks:
            if t.get('input_level') not in ('L2', 'L3'):
                continue
            got = _load(t, cand_dir)
            if got is None:
                continue
            gold, cand = got
            if strip == 'meta':
                gold, _ = _strip(gold, META)
                cand, _ = _strip(cand, META)
            elif strip == 'all':
                gold, _ = _strip(gold, ALL_STRIP)
                cand, _ = _strip(cand, ALL_STRIP)
            out[t['task_id']] = _judge(t, gold, cand)
    finally:
        restore()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', help='写 JSON（R26：命令行路径 == artifact）')
    args = ap.parse_args(argv)

    problems = []
    report = {'arms': 'old / new / strip_meta / strip_all',
              'meta_keys': sorted(META), 'mesh_keys': sorted(MESH),
              'n_meta': N_META, 'n_mesh': N_MESH, 'n_strip_all': N_META + N_MESH,
              'overlap': sorted(META & MESH), 'batches': {}}

    # J0
    if META & MESH:
        problems.append(f'J0 两集合有交集：{sorted(META & MESH)}（mesh 键被误豁免 = 考点静默消失）')

    tot_blocked = 0
    for label, tasks_rel, cand_dir, note in BATCHES:
        cdir = os.path.join(HERE, cand_dir)
        if not os.path.isdir(cdir):
            print(f'  [skip] {label}: 候选目录不存在 {cand_dir}')
            continue
        tasks = E.load_tasks(os.path.join(HERE, tasks_rel))

        old = run_batch(tasks, cand_dir, 'old')
        new = run_batch(tasks, cand_dir, 'new')
        smeta = run_batch(tasks, cand_dir, 'old', strip='meta')
        sall = run_batch(tasks, cand_dir, 'old', strip='all')

        ids = sorted(set(old) & set(new) & set(smeta) & set(sall))
        ok = {a: {i for i in ids if d[i]['pass']} for a, d in
              (('old', old), ('new', new), ('smeta', smeta), ('sall', sall))}
        flips_up = sorted(ok['new'] - ok['old'])
        flips_dn = sorted(ok['old'] - ok['new'])
        neq = sorted(ok['new'] ^ ok['smeta'])          # J2：new 与 strip_meta 必须逐题相同
        meshcost = sorted(ok['sall'] - ok['smeta'])     # J6：mesh 考点真的在起作用（剥掉后多过 = 键在卡人）
        old_blocked = [i for i in ids if old[i]['n_meta_skipped'] == 0 and any(
            f.split('.', 1)[0] == 'extra' and f.split('.', 1)[1] in META for f in old[i]['failed'])]
        tot_blocked += len(old_blocked)
        is_l3 = label.startswith('L3')

        if is_l3:
            if flips_up or flips_dn:
                problems.append(f'J1 {label} 零回归失败：转绿 {len(flips_up)} 转红 {len(flips_dn)}')
            if neq:
                problems.append(f'J2 {label}（L3）new 与 strip_meta 不等价：{neq[:3]}')
        else:
            if neq:
                problems.append(f'J2 {label} new 与 strip_meta 不等价（{len(neq)} 条）：{neq[:3]}')
            if flips_dn:
                problems.append(f'J3 {label} 有 {len(flips_dn)} 条转红：{flips_dn[:3]}')
            # J4：分支必须真的被触发。判据是「本批**至少有一条**跳过 >0」，
            # 不是「每条都 >0」—— gold 里根本没有 extra 元信息键的题，跳过数本就是 0
            # （要求每条都 >0 会把正常情况判红，等于用错误的对象测正确的事）。
            if not any(new[i]['n_meta_skipped'] > 0 for i in ids):
                problems.append(f'J4 {label} 全批 new 的 n_meta_skipped 都是 0（豁免分支没触发）')

        if any(old[i]['n_meta_skipped'] != 0 for i in ids):
            problems.append(f'J4 {label} old 的 n_meta_skipped 不全为 0（旧态不该有该分支）')

        report['batches'][label] = {
            'note': note, 'tasks': tasks_rel, 'candidates': cand_dir, 'n_scored': len(ids),
            'old_pass': len(ok['old']), 'new_pass': len(ok['new']),
            'strip_meta_pass': len(ok['smeta']), 'strip_all_pass': len(ok['sall']),
            'flips_up': flips_up, 'flips_down': flips_dn,
            'new_vs_strip_meta_diff': neq,
            'mesh_keys_cost': meshcost,
            'n_old_blocked_by_meta': len(old_blocked),
            'n_meta_skipped_new': sum(new[i]['n_meta_skipped'] for i in ids),
        }
        print(f'  [{label}] {len(ids)} 条 | old {len(ok["old"])} → new {len(ok["new"])}'
              f'  （strip_meta {len(ok["smeta"])} / strip_all {len(ok["sall"])}）'
              f'  转绿 {len(flips_up)} 转红 {len(flips_dn)}'
              f'  等价差 {len(neq)}  mesh考点 {len(meshcost)}')

    if tot_blocked == 0:
        problems.append('J5 全批次没有一条题被元信息键压住 ⇒ 判据无对象（集合为空或题面缺这些键）')
    _meshcost = sum(len(b['mesh_keys_cost']) for b in report['batches'].values())
    if _meshcost == 0:
        # 不是「必须红」而必须**显式报告**：若 mesh 7 键从不影响结果，
        # 那选 B 与选 A（把 mesh 也豁免）没有差别，不能再宣称「B 保留了转写考点」。
        problems.append('J6 mesh 7 键在全批次上从未改变结果 ⇒ 无法证明 B 比 A 多保留考点')
    report['totals'] = {'old_blocked_by_meta': tot_blocked,
                        'mesh_keys_cost_total': _meshcost}

    report['problems'] = problems
    report['ok'] = not problems
    print()
    if problems:
        for p in problems:
            print(f'  [BAD!] {p}')
        print(f'\nN-35 键拆分：{len(problems)} 条判据红')
    else:
        print(f'N-35 键拆分全过：J0 交集空（{N_META}+{N_MESH}={N_META + N_MESH} 键）'
              f' / J1 L3 零回归 / J2 new ≡ strip_meta / J3 只增不减'
              f' / J4 分支触发 / J5 被压 {tot_blocked} 条 / J6 mesh 考点 {report["totals"]["mesh_keys_cost_total"]} 条起效')

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with io.open(args.out, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
            f.write('\n')
        print(f'report -> {os.path.abspath(args.out)}')
    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main())
