# -*- coding: utf-8 -*-
"""_verify_tasks_v7.py — 考卷 v7 验收（T-A10b / N-15 双分母 / N-16 冻结表 / N-18 NL 冻结）

v6c → v7 只允许**加行**，不允许改老行。本脚本把这个「只允许」写成断言，两端都守：

  ★ 核心断言：L1/L2/L3 的老 55 条必须与 v6c 基线**逐字节相同**（按 task_id 比，不按行号）
    这是「v7 vs v6c 同卷可比」的唯一前提 —— 老题被静默改写过一次（N-16：48/55 条 L2），
    所以这里必须逐字节，不能只数字段数。

  ② 老 165 行中**任何一条**在新卷里找不到原样行 ⇒ FAIL（并打印差异键）

  ③ 双分母（N-15 老王拍板 A）：
     exam_legacy = interpolation 6 + boundary 6 + extrapolation 13 = 25
     exam_full   = exam_legacy + interpolation_v11 9 = 34
     ⇒ 两个都必须真的算得出；v11 的 9 条必须**不在** legacy 三栏里

  ④ L2 省略字段必须与 tasks/l2_omit_map.json 逐条一致（N-16 lockfile）

  ⑤ 内插 6 条必须与 v6c 完全相同（不因扩容而换人）

用法：python _verify_tasks_v7.py [--old reports/papers/tasks_v6c.jsonl]
退出码 0 = PASS，1 = FAIL
"""
import json, sys, os, argparse, collections

HERE = os.path.dirname(os.path.abspath(__file__))
OLD = os.path.join(HERE, 'reports', 'papers', 'tasks_v6c.jsonl')
NEW = os.path.join(HERE, 'tasks', 'tasks.jsonl')
L2MAP = os.path.join(HERE, 'tasks', 'l2_omit_map.json')

N_LEGACY = 55
N_V11 = 9
N_TOTAL = 64


def raw_rows(p):
    return [l.rstrip('\n') for l in open(p, encoding='utf-8') if l.strip()]


def by_id(rows):
    return {json.loads(l)['task_id']: json.loads(l) for l in rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', default=OLD)
    ap.add_argument('--new', default=NEW)
    args = ap.parse_args()

    bad = []

    def chk(cond, msg):
        if not cond:
            bad.append(msg)
        print(('  [ok ] ' if cond else '  [BAD] ') + msg)

    old_raw, new_raw = raw_rows(args.old), raw_rows(args.new)
    old, new = by_id(old_raw), by_id(new_raw)
    print(f'旧 {len(old_raw)} 行 / 新 {len(new_raw)} 行（v6c → v7）')

    # ① 行数与 id 集合
    chk(len(new_raw) == N_TOTAL * 3, f'新卷 3 层 × {N_TOTAL} = {N_TOTAL * 3} 行（实得 {len(new_raw)}）')
    chk(set(old) <= set(new), '老 task_id 全部保留（一条不删）')
    chk(len(new) == N_TOTAL * 3, f'task_id 无重复（{len(new)} 个唯一 id）')

    # ② ★ 老 165 行逐字节不变
    new_set = set(new_raw)
    miss = [l for l in old_raw if l not in new_set]
    chk(not miss, f'老 165 行逐字节存在于新卷（差异 {len(miss)} 条）')
    if miss:
        for m in miss[:5]:
            j = json.loads(m)
            k2 = new.get(j['task_id']) or {}
            dk = sorted(x for x in set(j) | set(k2) if j.get(x) != k2.get(x))
            print(f'        · {j["task_id"]} 差异键={dk}')

    # 按层计数（构造性：老 55 + 新 9）
    for L in ('L1', 'L2', 'L3'):
        o = [l for l in old_raw if json.loads(l)['input_level'] == L]
        n = [l for l in new_raw if json.loads(l)['input_level'] == L]
        oset = set(o)
        chk(len(o) == N_LEGACY and len(n) == N_TOTAL and all(l in set(n) for l in o),
            f'{L}: 老 {len(o)} → 新 {len(n)}，老行逐字节全在')

    # ③ 双分母
    l3 = [t for t in new.values() if t['input_level'] == 'L3']
    st = collections.Counter(t.get('exam_stratum') for t in l3)
    legacy = st['interpolation'] + st['boundary'] + st['extrapolation']
    full = legacy + st['interpolation_v11']
    chk(st['interpolation'] == 6, f'interpolation 仍 6（实 {st["interpolation"]}）')
    chk(st['boundary'] == 6, f'boundary 仍 6（实 {st["boundary"]}）')
    chk(st['extrapolation'] == 13, f'extrapolation 仍 13（v11 不得混进来；实 {st["extrapolation"]}）')
    chk(st['interpolation_v11'] == N_V11, f'interpolation_v11 = {N_V11}（实 {st["interpolation_v11"]}）')
    chk(legacy == 25, f'exam_legacy = 25（实 {legacy}）')
    chk(full == 34, f'exam_full = 25 + {N_V11} = 34（实 {full}）')

    # v11 的 9 条必须同时满足：stratum 与 split_reason 都标明来历
    v11 = [t for t in l3 if t.get('exam_stratum') == 'interpolation_v11']
    chk(all('v1.1 内插留出点' in t.get('split_reason', '') for t in v11),
        'v11 的 9 条 split_reason 均注明「v1.1 内插留出点」')

    # ④ L2 省略字段 == 冻结表
    l2map = {k: v for k, v in json.load(open(L2MAP, encoding='utf-8')).items()
             if not k.startswith('_')}
    l2 = [t for t in new.values() if t['input_level'] == 'L2']
    mism = [t['task_id'] for t in l2
            if l2map.get(t['task_id'][3:]) != t['expected_clarifications'][0]]
    chk(len(l2) == N_TOTAL, f'L2 共 {N_TOTAL} 条（实 {len(l2)}）')
    chk(not mism, f'L2 省略字段与冻结表 l2_omit_map.json 逐条一致（不一致 {len(mism)} 条）')
    if mism:
        print('        ·', mism[:8])

    # ⑤ 内插 6 条不因扩容换人
    old_interp = sorted(t['task_id'] for t in old.values()
                        if t.get('exam_stratum') == 'interpolation')
    new_interp = sorted(t['task_id'] for t in new.values()
                        if t.get('exam_stratum') == 'interpolation')
    chk(old_interp == new_interp, f'内插 6 条与 v6c 完全相同（{len(new_interp)} 条）')

    print()
    if bad:
        print(f'VERDICT: FAIL（{len(bad)} 项）')
        for b in bad:
            print('  -', b)
        return 1
    print('VERDICT: PASS —— 老 165 行逐字节未变；'
          f'exam_legacy=25 / exam_full=34；L2 冻结表 64/64 对齐')
    return 0


if __name__ == '__main__':
    sys.exit(main())
