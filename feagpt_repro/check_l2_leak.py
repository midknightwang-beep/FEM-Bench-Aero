# -*- coding: utf-8 -*-
"""check_l2_leak.py — L2 澄清题的「name 泄漏」诊断（N-17 / R26）

问题：L2 的做法是从 L1 spec 删掉一个字段，要求模型澄清。但 `spec.name` = case_id，
而 case_id 是人给的描述性名字，**经常把设计变量写在自己身上**：
    name = "open_hole_panel_400x200_d30"  且被删的正是 hole_d(=30)
⇒ 模型读 name 就知道答案，不必澄清。此时判「clarify 失败」是**判据的错**，
   不是模型的错（同 M7：诊断假设与被测对象必须同口径）。

判据（语义前缀，不用裸数字碰撞 —— 撞车不算泄漏）：
    d<N>      -> hole_d / diameter
    frm<N>    -> n_frames
    str<N>    -> n_stringers / n_stringers_per_skin
    n_ribs<N> -> n_ribs
    sweep<N>  -> sweep_deg
    taper<N>  -> tip_chord_ratio
    skin<N>   -> skin_thickness
    l<N>      -> length
    <A>x<B>   -> length=A, width=B
    chord<N>  -> chord
    span<N>   -> span
    t<N>      -> thickness

反例（必须**不**判泄漏）：
    naca4412_wingbox_str4 省略 rib_thickness(=4.0)：str4 揭示的是 n_stringers，
    与 rib_thickness 只是数值撞车 ⇒ 不泄漏。

用法：
    python check_l2_leak.py --out reports/l2_name_leak_2026-10-28.json [--md ...]
    python check_l2_leak.py                      # 只打印
"""
import json, os, re, sys, argparse, collections
from _paths import rel   # T-A11a：跨盘符安全（见 _paths.py）

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = os.path.join(HERE, 'tasks', 'tasks.jsonl')

_B = r'(?:^|_)'
SEM = [
    (_B + r'd(\d+)',            {'hole_d', 'diameter'}),
    (_B + r'frm(\d+)',          {'n_frames'}),
    (_B + r'str(\d+)',          {'n_stringers', 'n_stringers_per_skin'}),
    (_B + r'n_ribs(\d+)',       {'n_ribs'}),
    (_B + r'sweep(\d+)',        {'sweep_deg'}),
    (_B + r'taper(\d+)',        {'tip_chord_ratio'}),
    (_B + r'skin(\d+)',         {'skin_thickness'}),
    (_B + r'l(\d+)',            {'length'}),
    (_B + r'chord(\d+)',        {'chord', 'chord_length'}),
    (_B + r'span(\d+)',         {'span'}),
    (_B + r'(\d+)x\d+',         {'length'}),
    (_B + r'\d+x(\d+)',         {'width'}),
    (_B + r't(\d+)(?:_|$)',     {'thickness'}),
]


def revealed_fields(name):
    """从 case_id / spec.name 里能直接读出的字段 -> 证据片段集合。"""
    out = {}
    for pat, fields in SEM:
        for m in re.finditer(pat, name):
            frag = m.group(0).lstrip('_')
            for f in fields:
                out.setdefault(f, set()).add(frag)
    return {k: sorted(v) for k, v in out.items()}


def scan(tasks_path=TASKS):
    """返回 (总 L2 数, 泄漏明细列表, 干净数)。"""
    if not os.path.exists(tasks_path):
        raise SystemExit(f'找不到 {tasks_path}（先跑 make_tasks.py）')
    rows = [json.loads(l) for l in open(tasks_path, encoding='utf-8') if l.strip()]
    l1 = {r['task_id'][3:]: r['input']['spec_normalized']
          for r in rows if r['input_level'] == 'L1'}
    hits, n_l2 = [], 0
    for r in rows:
        if r['input_level'] != 'L2':
            continue
        n_l2 += 1
        cid = r['task_id'][3:]
        key = r['expected_clarifications'][0]
        name = (l1.get(cid) or {}).get('name') or cid
        rv = revealed_fields(name)
        if key in rv:
            hits.append({
                'case_id': cid,
                'task_id': r['task_id'],
                'family': r['family'],
                'omitted_field': key,
                'name': name,
                'name_evidence': rv[key],
                'split_v2': r.get('split_v2'),
            })
    return n_l2, hits, n_l2 - len(hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', help='写 JSON（R26：命令行里的路径 == artifact）')
    ap.add_argument('--md', help='同时写 Markdown')
    ap.add_argument('--tasks', default=TASKS)
    args = ap.parse_args()

    n_l2, hits, n_clean = scan(args.tasks)
    by_fam = collections.Counter(h['family'] for h in hits)
    print(f'L2 总数 {n_l2}；name 泄漏被省略值 {len(hits)} 条；干净 {n_clean} 条'
          f'（informative 比例 {100.0 * n_clean / max(1, n_l2):.1f}%）')
    print('按族:', dict(by_fam))
    for h in hits:
        print(f"  [{h['family']:16s}] {h['case_id']:42s} 省略={h['omitted_field']:20s}"
              f" name 证据={h['name_evidence']}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        obj = {
            '_note': ('L2 澄清题的 name 泄漏诊断（CONFLICT N-17）。判据见 check_l2_leak.py '
                      'docstring；撞车不算泄漏。可用 check_l2_leak.py 复跑复现。'),
            'tasks': rel(args.tasks),
            'n_l2': n_l2, 'n_leak': len(hits), 'n_clean': n_clean,
            'informative_pct': round(100.0 * n_clean / max(1, n_l2), 1),
            'by_family': dict(by_fam),
            'hits': hits,
        }
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(f'[OK] 写盘 {args.out}')

    if args.md:
        lines = ['# L2 name 泄漏诊断（CONFLICT N-17）', '',
                 f'- L2 总数：**{n_l2}**',
                 f'- name 泄漏被省略值：**{len(hits)}**（干净 {n_clean}，'
                 f'informative {100.0 * n_clean / max(1, n_l2):.1f}%）', '',
                 '| family | case_id | 省略字段 | name 证据 |', '|---|---|---|---|']
        for h in hits:
            lines.append(f"| {h['family']} | `{h['case_id']}` | `{h['omitted_field']}` | "
                         f"{', '.join('`' + e + '`' for e in h['name_evidence'])} |")
        with open(args.md, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
        print(f'[OK] 写盘 {args.md}')


if __name__ == '__main__':
    main()
