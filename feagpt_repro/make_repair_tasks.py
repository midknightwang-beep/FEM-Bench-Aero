# -*- coding: utf-8 -*-
"""B5 注入缺陷修复题 —— 小卷生成器（tasks_repair_v1.jsonl）。

设计（避开 N-26 陷阱）：
  * 缺陷字段 = gold spec 里的一个锚点字段（name 里可见），确定性变异（改成一个错值）。
  * "正确答案" = 原始 gold spec（独立 artifact，不写死在判据里）。
  * 题面给模型的是【带缺陷的 spec】+ 一句"这份 spec 有一个字段与 name/任务描述不自洽，
    请输出修复后的完整 spec JSON"——不告诉它缺陷在哪、原值是多少。
  * 判据 judge_repair.py 现场算 diff，验"输出 == gold"，且反向验"原样吐回坏 spec"判红。

所以本生成器只负责：从 4 族各取 1 条 gold → 注入 1 个 name 锚点字段缺陷 → 落小卷。
缺陷算子表按族写死（哪些字段可以变异、怎么变异），但**判据不读这张表**——判据只认 gold。

用法::

    python make_repair_tasks.py                # 生成 tasks_repair_v1.jsonl
    python make_repair_tasks.py --self-test    # 验注入正确、锚点可见、四族齐全
"""
from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELING = HERE.parent / "FEM-Bench-Aero" / "modeling"
OUT = HERE / "tasks_repair_v1.jsonl"

# 每族选一条 gold + 注入点。缺陷算子：把锚点字段改成"与 name 自洽值不同的错值"。
# 错值确定性写死（可复现），但判据不依赖它——判据只比对 gold。
SEEDS = {
    "open_hole_panel": {
        "case": "open_hole_panel_400x200_d20",
        "path": ("structure", "params", "hole_d"),   # name 里 d20 → 20
        "wrong": 35.0,
    },
    "stiffened_panel": {
        # 选一条 n_stringers>0 的，否则注入"无长桁→有长桁"不够像手误
        "case": None,  # 运行时挑 n_stringers>0 的
        "path": ("structure", "params", "n_stringers"),
        "wrong": None,  # 运行时 = 原值 + 2
    },
    "fuselage_barrel": {
        "case": "fuselage_barrel_d1600_l1600_str8_frm3",
        "path": ("structure", "params", "n_frames"),  # name 里 frm3 → 3
        "wrong": 5,
    },
    "wingbox": {
        "case": "naca4412_wingbox_n_ribs5_chord800",  # name 里 n_ribs5 → 5
        "path": ("airfoil", "n_ribs"),
        "wrong": 7,
    },
}


def _get(d, path):
    for k in path:
        d = d[k]
    return d


def _set(d, path, val):
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = val


def _sha8(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def load_gold(family: str, case: str | None) -> tuple[Path, dict]:
    pattern = f"{case}/spec.json" if case else f"{family}*/spec.json"
    cands = sorted(MODELING.glob(pattern))
    if family and not case:
        # 特殊挑选
        if family == "stiffened_panel":
            cands = [p for p in cands if _get(json.loads(p.read_text(encoding="utf-8")),
                     ("structure", "params", "n_stringers")) > 0] or cands
    if not cands:
        raise SystemExit(f"[FAIL] 找不到 gold: {family}/{case}")
    p = cands[0]
    return p, json.loads(p.read_text(encoding="utf-8"))


def build_rows() -> list[dict]:
    rows = []
    for family, cfg in SEEDS.items():
        p, gold = load_gold(family, cfg["case"])
        path = cfg["path"]
        correct = _get(gold, path)
        wrong = cfg["wrong"]
        if wrong is None:
            wrong = correct + 2
        broken = copy.deepcopy(gold)
        _set(broken, path, wrong)
        assert wrong != correct, f"缺陷没注入进去: {family}"

        row = {
            "task_id": f"REPAIR_{family}",
            "family": family,
            "defect_path": list(path),      # 供 artifact 记录；判据不用它判分
            "correct_value": correct,        # 供 artifact 记录；判据从 gold 现场取
            "wrong_value": wrong,
            "gold_spec": gold,               # 标准答案（独立来源，判据读它）
            "broken_spec": broken,           # 给模型的输入
            "gold_source": str(p.relative_to(HERE.parent)),
            "gold_sha8": _sha8(p),
        }
        rows.append(row)
    return rows


def self_test() -> int:
    rows = build_rows()
    assert len(rows) == 4, f"四族应各一条，实际 {len(rows)}"
    assert {r["family"] for r in rows} == set(SEEDS), "族不齐"
    for r in rows:
        assert r["gold_spec"] != r["broken_spec"], f"{r['family']} 缺陷没注入"
        assert _get(r["broken_spec"], tuple(r["defect_path"])) == r["wrong_value"]
        assert _get(r["gold_spec"], tuple(r["defect_path"])) == r["correct_value"]
        # 只能有一个字段不同（确定性单缺陷）
        diffs = []
        def walk(a, b, prefix=""):
            if isinstance(a, dict) and isinstance(b, dict):
                for k in set(a) | set(b):
                    walk(a.get(k), b.get(k), f"{prefix}.{k}")
            elif isinstance(a, list) and isinstance(b, list):
                if a != b: diffs.append(prefix or "ROOT")
            elif a != b:
                diffs.append(prefix)
        walk(r["gold_spec"], r["broken_spec"])
        assert len(diffs) == 1, f"{r['family']} 应恰好 1 处差异，实际 {diffs}"
        expected = "." + ".".join(r["defect_path"])
        assert diffs[0] == expected, f"{r['family']} 缺陷位置不符: {diffs[0]} != {expected}"
        print(f"  [ok] {r['family']:<18} defect {diffs[0]} {r['correct_value']} -> {r['wrong_value']}")
    print("[self-test] 4/4 pass (四族各 1 处确定性缺陷、锚点正确)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    rows = build_rows()
    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                   encoding="utf-8")
    print(f"[ok] 写入 {OUT} ({len(rows)} 条)")
    for r in rows:
        print(f"  {r['task_id']:<28} {'.'.join(r['defect_path'])}={r['correct_value']}"
              f" -> {r['wrong_value']} (gold {r['gold_sha8']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
