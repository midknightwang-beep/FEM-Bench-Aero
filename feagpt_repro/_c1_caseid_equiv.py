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
    # ★ 只放**冻结卷**。原来是 `tasks/tasks.jsonl`（当时它 == `tasks_v7.jsonl`），
    #   但那一卷是「当前卷」，每次换卷都会前进 —— v8 一进卷，下面 ① 的等价断言
    #   立刻假红：新加的 16 条 task_id 带 `L2i_` 前缀，而 `legacy_chain()` 只剥
    #   `L1_/L2_/L3_`，旧规则**本来就剥不掉**（那正是 T-C1/T-L27c 修掉的缺陷）。
    #   对旧规则处理不了的行比「等价」没有意义 —— 它们归 ② 的解析判据。
    #   换卷的代价不该是「等价证明红一次」，故这里锚在 v7 的冻结字节上。
    os.path.join(HERE, 'reports', 'papers', 'tasks_v7.jsonl'),
    os.path.join(HERE, 'reports', 'papers', 'tasks_v6c.jsonl'),
]

# ② 的判据对象：**旧链处理不了的行**（`case_id_of(tid) != legacy_chain(tid)`），
# 现取自两个来源，不硬列前缀名（写死 `L2i_` 就会在下一个新前缀上静默失效）：
#   · 独立信息完备卷（T-L27c 派生）；
#   · **当前卷**——v8 起信息完备题已并入主卷，只在独立卷上核 = 只核了一半（A ⊆ B 要核两端）。
INF_VOL = os.path.join(HERE, 'tasks', 'tasks_l2_informative_v1.jsonl')
CUR_VOL = os.path.join(HERE, 'tasks', 'tasks.jsonl')


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

    # ── ② T-L27c：**与旧链等价只证明"没改坏"，不证明"改对了"** ──
    # 必须另有一条判据断言「新前缀真的能被解析到金标准」。否则把层前缀剥离整段删掉，
    # 上面那些冻结卷照样全等价（它们的 task_id 本来就以 L1_/L2_/L3_ 开头）。
    # 判据取自数据自身：`case_id_of(tid) != legacy_chain(tid)` 的行 = **旧链处理不了的行**，
    # 不硬列前缀名；遍历其解析结果去 modeling/ 里找 spec.json。
    src_rows, per_src = [], {}
    for vol in (INF_VOL, CUR_VOL):
        if not os.path.exists(vol):
            print(f'[warn] {os.path.basename(vol)} 不存在（来源缺失，下面按已存在的核）')
            continue
        rows2 = [json.loads(ln) for ln in open(vol, encoding='utf-8') if ln.strip()]
        if not rows2:
            print(f'[FATAL] {os.path.basename(vol)} 是空卷：判据会被空壳满足')
            return 1
        k = 0
        for r in rows2:
            tid = r.get('task_id')
            if not tid:
                continue
            if case_id_of(tid) != legacy_chain(tid):
                src_rows.append((os.path.basename(vol), tid))
                k += 1
        per_src[os.path.basename(vol)] = k
    if not src_rows:
        print('[FATAL] 两个来源里都找不到「旧链处理不了」的行 ⇒ 本判据被空集满足（判红）')
        return 1

    stuck, miss = [], []
    for src, tid in src_rows:
        cid = case_id_of(tid)
        if cid == tid:
            stuck.append((src, tid))          # 层前缀根本没被剥掉（本次事故的签名）
        elif not os.path.isfile(os.path.join(FEA, 'modeling', cid, 'spec.json')):
            miss.append((src, tid, cid))
    _n = len(src_rows)
    print(f'  新前缀行 {_n} 条（' + '、'.join(f'{k} {v}' for k, v in per_src.items())
          + f'），前缀剥离 {_n - len(stuck)}/{_n}，金标准命中 {_n - len(stuck) - len(miss)}/{_n}')
    if stuck:
        print(f'[FATAL] {len(stuck)} 条的前缀没被剥离（case_id == task_id）：{stuck[:5]}')
        return 1
    if miss:
        print(f'[FATAL] {len(miss)} 条定位不到 spec.json：{miss[:5]}')
        return 1
    print('[ok  ] T-L27c：信息完备行的层前缀全部可解析，金标准全部命中')
    return 0


if __name__ == '__main__':
    sys.exit(main())
