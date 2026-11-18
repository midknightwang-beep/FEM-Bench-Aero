# -*- coding: utf-8 -*-
"""B5 注入缺陷修复题 —— 判分器（tasks_repair_v1.jsonl 的唯一判据）。

**判据（写/验分离：本文件不读 make_repair_tasks.SEEDS 缺陷表，只认 gold）**
    对每条题：
      1) 从卷现场算 diff_fields = deep_diff(gold, broken) —— 缺陷在哪，现场算，不写死。
      2) 模型输出 out 必须满足：
         a) out == gold（逐字段规范化相等）⇒ 缺陷被修回、且没有 collateral 改动；
         b) out != broken（反向闸：原样吐回坏 spec 不算修复）；
         c) 若 out 只改了缺陷字段但值不对 ⇒ repair_wrong；
         d) 若 out 改了 diff_fields 之外的字段 ⇒ collateral_edit（即使缺陷修对也不算 PASS）。
    ★ 为什么不读缺陷表：若判据拿 SEEDS["wrong"] 去比 "模型有没有避开错值"，那就把
      "缺陷长什么样"写进了判据 —— 换一个缺陷算子判据就失效（N-26）。这里只认 gold
      与 broken 两个独立 artifact，diff 现场算。

usage::

    python judge_repair.py --self-test
    python judge_repair.py --candidates candidates_repair_v1_glm --json out.json
"""
from __future__ import annotations

import argparse
import copy
import glob
import io
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE / "tasks_repair_v1.jsonl"


def load_tasks(path=None) -> list[dict]:
    p = Path(path) if path else TASKS
    return [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]


def canonical(obj):
    """只保留参与建模语义的字段，去掉 name/description/workdir 等展示字段。"""
    drop = {"name", "description", "workdir"}
    if isinstance(obj, dict):
        return {k: canonical(v) for k, v in obj.items() if k not in drop}
    if isinstance(obj, list):
        return [canonical(v) for v in obj]
    return obj


def deep_diff(a, b, prefix="") -> list[str]:
    """返回 a、b 之间所有差异字段路径（规范化后）。"""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            out += deep_diff(a.get(k), b.get(k), f"{prefix}.{k}" if prefix else k)
    elif isinstance(a, list) and isinstance(b, list):
        if a != b:
            out.append(prefix or "ROOT")
    elif a != b:
        out.append(prefix or "ROOT")
    return out


def extract_spec(cand: dict):
    """候选行里取 spec。兼容 {spec: {...}} 和顶层即 spec。"""
    if not isinstance(cand, dict):
        return None
    if cand.get("error"):
        return None
    s = cand.get("spec")
    if isinstance(s, dict):
        return s
    return None


def judge_one(row: dict, cand: dict | None) -> dict:
    gold = canonical(row["gold_spec"])
    broken = canonical(row["broken_spec"])
    diff_fields = set(deep_diff(gold, broken))
    spec = extract_spec(cand) if cand else None

    if spec is None:
        return {"verdict": "no_output", "pass": False,
                "diff_fields": sorted(diff_fields), "out_diff_gold": None}

    out = canonical(spec)
    d_gold = set(deep_diff(out, gold))
    d_broken = set(deep_diff(out, broken))

    # 原样吐回坏 spec（一个字段都没动）
    if not d_broken:
        return {"verdict": "repair_none", "pass": False,
                "diff_fields": sorted(diff_fields), "out_diff_gold": sorted(d_gold)}
    # 改了缺陷字段之外的字段 ⇒ 防作弊（含把整个 spec 换掉）
    collateral = d_gold - diff_fields
    if collateral:
        return {"verdict": "collateral_edit", "pass": False,
                "diff_fields": sorted(diff_fields), "out_diff_gold": sorted(d_gold),
                "collateral": sorted(collateral)}
    # 缺陷字段没修对（out 仍与 gold 在缺陷字段上有差异）
    if d_gold:
        return {"verdict": "repair_wrong", "pass": False,
                "diff_fields": sorted(diff_fields), "out_diff_gold": sorted(d_gold)}
    # out == gold 且确实动了缺陷字段
    return {"verdict": "repair_correct", "pass": True,
            "diff_fields": sorted(diff_fields), "out_diff_gold": []}


def load_candidates(pattern: str) -> dict[str, dict]:
    out = {}
    for p in sorted(glob.glob(os.path.join(pattern, "*.jsonl"))):
        for line in io.open(p, encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            tid = d.get("task_id")
            if tid:
                out[tid] = d
    return out


def score(cands: dict[str, dict], tasks: list[dict]) -> dict:
    per = []
    for row in tasks:
        r = judge_one(row, cands.get(row["task_id"]))
        r["task_id"] = row["task_id"]
        r["family"] = row["family"]
        per.append(r)
    n = len(per)
    passed = sum(1 for r in per if r["pass"])
    kinds: dict[str, int] = {}
    for r in per:
        kinds[r["verdict"]] = kinds.get(r["verdict"], 0) + 1
    return {"n": n, "passed": passed,
            "repair_rate_pct": round(100.0 * passed / n, 2) if n else None,
            "verdicts": kinds, "per_task": per}


def self_test() -> int:
    tasks = load_tasks()
    assert len(tasks) == 4, "小卷应 4 条"
    checks = []

    # ① 正例：模型输出 = gold ⇒ PASS（4 条全过）
    ok_gold = {r["task_id"]: {"spec": r["gold_spec"]} for r in tasks}
    s = score(ok_gold, tasks)
    checks.append(("正例 out=gold 全 PASS", s["passed"] == 4 and s["repair_rate_pct"] == 100.0))

    # ② 反向闸：原样吐回 broken ⇒ 全 repair_none、0 分
    ok_broken = {r["task_id"]: {"spec": r["broken_spec"]} for r in tasks}
    s = score(ok_broken, tasks)
    checks.append(("反向 原样吐回 broken 判红", s["passed"] == 0 and
                   all(r["verdict"] == "repair_none" for r in s["per_task"])))

    # ③ 防作弊：改缺陷字段但换成第三个错值 ⇒ repair_wrong
    c3 = {}
    for r in tasks:
        sp = copy.deepcopy(r["broken_spec"])
        path = r["defect_path"]
        cur = sp
        for k in path[:-1]:
            cur = cur[k]
        cur[path[-1]] = r["wrong_value"] + 100  # 又错得更离谱
        c3[r["task_id"]] = {"spec": sp}
    s = score(c3, tasks)
    checks.append(("反向 缺陷字段改错值判红", s["passed"] == 0 and
                   all(r["verdict"] == "repair_wrong" for r in s["per_task"])))

    # ④ 防 collateral：缺陷改对 + 顺手改别的字段 ⇒ collateral_edit
    c4 = {}
    for r in tasks:
        sp = copy.deepcopy(r["gold_spec"])
        sp["material"]["yield_strength"] = sp["material"].get("yield_strength", 345) + 1
        c4[r["task_id"]] = {"spec": sp}
    s = score(c4, tasks)
    checks.append(("反向 缺陷改对但动别处判红", s["passed"] == 0 and
                   all(r["verdict"] == "collateral_edit" for r in s["per_task"])))

    # ⑤ 无输出 ⇒ no_output
    s = score({}, tasks)
    checks.append(("反向 无输出判红", s["passed"] == 0 and
                   all(r["verdict"] == "no_output" for r in s["per_task"])))

    for name, ok in checks:
        print(f"  [{'ok' if ok else 'FAIL'}] {name}")
        assert ok, name
    print(f"[self-test] {len(checks)}/{len(checks)} pass (正例 + 4 反向闸)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--candidates", help="候选目录（含 *.jsonl）")
    ap.add_argument("--json", help="写出成绩 artifact")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.candidates:
        print("usage: judge_repair.py --self-test | --candidates <dir> [--json out.json]")
        return 2
    tasks = load_tasks()
    cands = load_candidates(args.candidates)
    result = score(cands, tasks)
    result["candidates_dir"] = args.candidates
    model_ids = sorted({(v.get("model") or "?") for v in cands.values()})
    result["models"] = model_ids
    print(f"=== repair rate {result['repair_rate_pct']}% ({result['passed']}/{result['n']}) "
          f"models={model_ids} ===")
    for r in result["per_task"]:
        print(f"  {r['task_id']:<28} {r['verdict']:<18} {'PASS' if r['pass'] else 'FAIL'}")
    if args.json:
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[ok] 写出 {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
