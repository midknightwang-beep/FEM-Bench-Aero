# -*- coding: utf-8 -*-
"""report_l2_clarify.py — L2 澄清题的**双口径**报告（CONFLICT N-17 老王拍板 C'；R66 / S-53）

为什么需要这个文件
------------------
L2 的出题法是「从 L1 spec 删掉一个字段，要求模型澄清」。但 `spec.name` = case_id，
而 case_id 是人给的**描述性名字**，19/64 条把被删的值写在自己身上：

    name = "open_hole_panel_400x200_d30"   且被删的正是 hole_d(=30)   ⇒ 答案在题面
    name = "fuselage_barrel_..._str8_frm3" 且被删的是 n_frames(=3)    ⇒ 答案在题面

那 19 条的 clarify 判据**无效**：模型读 name 就知道，不必问。
判它「clarify 失败」是判据的错，不是模型的错（与 M7 同源）。判定见 `check_l2_leak.py`。

处置（C'：不改题、只改口径）
--------------------------
- `tasks.jsonl` **零改动** —— 不改题，因为改题会连历史一起废掉（与 C-037 冻结直接冲突）；
- 分数**双报**，两个分母并列：
      clarify_all          n = 64  全卷（含 19 条无效子集）：与旧口径同分母，跨版本可比
      clarify_informative  n = 45  只有 name 没泄漏的可判子集：这才是「会不会追问」的真信号
- ★ **R54**：分母不同（64 ≠ 45）⇒ **禁止相减、禁止据此排名**。本文件把两个都写进
  同一个 artifact，少任何一个 S-53 直接红（R66：无效子集必须隔离并双报）。

边界（写清楚，不含糊）
--------------------
L2 至今**从未跑过模型**（全仓无 `clarification.json`；`score_baseline.py` 只读 L3，
故 C-032 的 `n_clarify_tasks=4` 与本文件的 64 无关）。所以 `status = "not_run"`、
`passed = null` 是**如实**的，不是漏算。S-53 的语义因此是「**口径已就位、两个分母
必须同时在**」；等 L2 首次跑分那一轮，`status` 升为 `scored`，S-53 自动加严为
「两侧都必须有整数 `passed`」——不需要另写一条闸。

用法：
    python report_l2_clarify.py --out reports/l2_clarify_dual.json --md reports/l2_clarify_dual.md
    python report_l2_clarify.py                    # 只打印
"""
import argparse
import collections
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_l2_leak  # noqa: E402  （判据只有一处，避免两套实现漂移）

TASKS = os.path.join(HERE, 'tasks', 'tasks.jsonl')


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _rel(p):
    """相对 HERE 的展示路径；**跨盘符时退回绝对路径**。

    ★ 踩过的坑：负控在 `tempfile.mkdtemp()`（C:）里造变异，而仓库在 F:，
      `os.path.relpath` 会直接抛 `ValueError: path is on mount 'C:', start on mount 'F:'`
      ⇒ 闸在临时目录里根本跑不起来，等于无法被证伪。
    """
    try:
        return os.path.relpath(p, HERE).replace('\\', '/')
    except ValueError:
        return os.path.abspath(p).replace('\\', '/')


def dual_clarify(tasks_path=TASKS, paper=None):
    """算出 L2 澄清题的 all / informative 两套分母。

    返回的 dict **同时**含两个块；调用方不得只取其中一块对外（R66）。
    `passed` 恒为 None —— 本函数只负责分母与掩码，跑分结果由 L2 harness 回填。
    """
    n_l2, hits, n_clean = check_l2_leak.scan(tasks_path)
    if n_l2 == 0:
        raise SystemExit(f'{tasks_path} 里没有 L2 任务（先跑 make_tasks.py）')

    rows = [json.loads(l) for l in open(tasks_path, encoding='utf-8') if l.strip()]
    l2_rows = [r for r in rows if r['input_level'] == 'L2']
    invalid_ids = sorted(h['task_id'] for h in hits)
    invalid_set = set(invalid_ids)
    informative_ids = sorted(r['task_id'] for r in l2_rows if r['task_id'] not in invalid_set)

    # 闭合断言：三块必须严丝合缝地对上，否则说明掩码与任务表不同源。
    assert len(l2_rows) == n_l2, f'L2 条数不一致：{len(l2_rows)} vs {n_l2}'
    assert len(invalid_ids) + len(informative_ids) == n_l2, (
        f'掩码不闭合：{len(invalid_ids)} + {len(informative_ids)} != {n_l2}')
    assert not (invalid_set & set(informative_ids)), 'invalid 与 informative 有交集'

    fam_all = collections.Counter(r['family'] for r in l2_rows)
    fam_inf = collections.Counter(r['family'] for r in l2_rows if r['task_id'] not in invalid_set)
    fam_bad = collections.Counter(h['family'] for h in hits)

    return {
        'paper': paper or os.path.basename(tasks_path),
        'tasks': _rel(tasks_path),
        'tasks_sha256': _sha256(tasks_path),
        'criterion': ('check_l2_leak.py 语义前缀匹配（d<N>/frm<N>/str<N>/...）；'
                      '数值撞车不算泄漏（例：str4 揭示 n_stringers，不揭示 rib_thickness）'),
        'status': 'not_run',
        'clarify_all': {
            'n': n_l2, 'passed': None, 'pct': None,
            'denominator': '全卷 L2 澄清题（含 name 泄漏的无效子集）',
            'by_family': dict(sorted(fam_all.items())),
        },
        'clarify_informative': {
            'n': len(informative_ids), 'passed': None, 'pct': None,
            'denominator': 'name 未泄漏被省略值的可判子集（真的在考「会不会追问」）',
            'by_family': dict(sorted(fam_inf.items())),
            'task_ids': informative_ids,
        },
        'invalid': {
            'n': len(invalid_ids),
            'reason': 'spec.name 直接写出被省略值 ⇒ clarify 判据无效（N-17）',
            'by_family': dict(sorted(fam_bad.items())),
            'task_ids': invalid_ids,
            'detail': [{k: h[k] for k in ('case_id', 'family', 'omitted_field',
                                          'name', 'name_evidence')} for h in hits],
        },
        'informative_pct': round(100.0 * len(informative_ids) / n_l2, 1),
        'delta_allowed': False,
        'r54_note': ('两个分母不同（clarify_all %d ≠ clarify_informative %d）⇒ '
                     '禁止相减、禁止据此排名（R54）；R66 要求无效子集隔离并双报，'
                     '只报一侧即 S-53 红。' % (n_l2, len(informative_ids))),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', help='写 JSON（R26：命令行里的路径 == artifact）')
    ap.add_argument('--md', help='同时写 Markdown')
    ap.add_argument('--tasks', default=TASKS)
    ap.add_argument('--paper', help='卷标签（默认取文件名）')
    args = ap.parse_args()

    rep = dual_clarify(args.tasks, paper=args.paper)
    a, inf, inv = rep['clarify_all'], rep['clarify_informative'], rep['invalid']

    print(f"[L2 clarify] 双口径（N-17 / C'）：status={rep['status']}")
    print(f"  clarify_all          n = {a['n']:3d}  by_family={a['by_family']}")
    print(f"  clarify_informative  n = {inf['n']:3d}  by_family={inf['by_family']}")
    print(f"  无效子集（name 泄漏） n = {inv['n']:3d}  by_family={inv['by_family']}")
    print(f"  informative 比例 {rep['informative_pct']}%")
    print(f"  ★ {rep['r54_note']}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        obj = {
            '_note': ('L2 澄清题双口径（CONFLICT N-17 拍板 C\'）。判据见 check_l2_leak.py；'
                      '本文件只给分母与掩码，passed 由 L2 首次跑分回填。'),
            **rep,
        }
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(f'[OK] 写盘 {args.out}')

    if args.md:
        L = ['# L2 澄清题：双口径（CONFLICT N-17 → 拍板 C\'）', '',
             f"- 卷：`{rep['paper']}`　任务表：`{rep['tasks']}`",
             f"- 状态：**{rep['status']}**（L2 至今未跑模型，`passed` 如实为空）",
             f"- 判据：{rep['criterion']}", '',
             '## 两套分母必须并列', '',
             '| 口径 | 分母 n | 含义 |', '|---|---|---|',
             f"| `clarify_all` | **{a['n']}** | {a['denominator']} |",
             f"| `clarify_informative` | **{inf['n']}** | {inf['denominator']} |",
             f"| （无效子集，不进任何单一口径） | {inv['n']} | {inv['reason']} |", '',
             f"> {rep['r54_note']}", '',
             '## 无效子集明细（19 条）', '',
             '| family | case_id | 省略字段 | name 里的证据 |', '|---|---|---|---|']
        for d in inv['detail']:
            L.append(f"| {d['family']} | `{d['case_id']}` | `{d['omitted_field']}` | "
                     f"{', '.join('`' + e + '`' for e in d['name_evidence'])} |")
        with open(args.md, 'w', encoding='utf-8') as f:
            f.write('\n'.join(L) + '\n')
        print(f'[OK] 写盘 {args.md}')


if __name__ == '__main__':
    main()
