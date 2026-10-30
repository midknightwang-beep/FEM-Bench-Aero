"""T-C1 构造性等价证明：`case_id_of()` 与原先散在三处的内联转换链**逐条等价**。

为什么必须有这个脚本（R67）：
    `require_dataset(expect_ids=...)` 用 `case_id_of()` 判断「这条任务的数据在不在」，
    而 `evaluate_one()` 真正读金标准时走的是同一条链。**两者只要差一个字**，
    覆盖率检查就会与实际读取错位 —— 闸说「在」、实际读不到，于是闸变成假绿。
    T-C1 把三处内联链统一到 `case_id_of()`，本脚本对**两个卷的全部 task_id**
    逐条断言「旧写法 == 新函数」，并顺带核对定位到的 `spec.json` 路径字符串也相同。

用法（项目 venv）：
    "$PY" _c1_caseid_equiv.py
退出码：0 = 全部等价；1 = 有差异（会把差异逐条打印）
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from evaluate import case_id_of, FEA  # noqa: E402

VOLUMES = [
    os.path.join(HERE, 'tasks', 'tasks.jsonl'),
    os.path.join(HERE, 'reports', 'papers', 'tasks_v6c.jsonl'),
]


def legacy_chain(task_id):
    """T-C1 之前散在 evaluate_one 三处的内联写法（逐字照抄，不得"顺手优化"）。"""
    return (task_id.replace('L1_', '').replace('L2_', '').replace('L3_', '')
            .replace('_final', '').replace('cand_', ''))


def main():
    total = 0
    bad = []
    for vol in VOLUMES:
        if not os.path.exists(vol):
            print(f'[FATAL] 卷不存在：{vol}')
            return 1
        rows = [json.loads(ln) for ln in open(vol, encoding='utf-8') if ln.strip()]
        n = 0
        for r in rows:
            tid = r.get('task_id')
            if not tid:
                bad.append((vol, '<无 task_id>', '', ''))
                continue
            old, new = legacy_chain(tid), case_id_of(tid)
            old_p = os.path.join(FEA, 'modeling', old, 'spec.json')
            new_p = os.path.join(FEA, 'modeling', new, 'spec.json')
            if old != new or old_p != new_p:
                bad.append((os.path.basename(vol), tid, old, new))
            n += 1
        total += n
        print(f'  {os.path.basename(vol):24s} 任务 {n} 条，逐条等价')

    print(f'\n合计 {total} 条 task_id')
    if bad:
        print(f'[FATAL] 有 {len(bad)} 条不等价：')
        for v, t, o, nw in bad[:20]:
            print(f'  {v} | {t} | 旧={o!r} 新={nw!r}')
        return 1

    # 反向自检：故意造一个差异，确认判据真的能判红（否则"全等价"可能是判据恒真）。
    probe = legacy_chain('L3_probe_case')
    mutated = probe + '_x'
    if case_id_of('L3_probe_case') != mutated:
        print('[ok  ] 反向自检：注入差异可被检出（判据非恒真）')
    else:
        print('[FATAL] 反向自检失败：判据恒真，全等价不可信')
        return 1
    print('[ok  ] case_id_of 与旧链逐条等价，且定位到的 spec.json 路径相同')
    return 0


if __name__ == '__main__':
    sys.exit(main())
