"""C5 六环之「澄清环」证据生成器（2026-11-18）。

为什么需要它
------------
ROADMAP §17.3 第 2 条把 C5 记为 5/6，唯一缺的环是「澄清」，并写明现成素材是
`d1600_l1600` 那条「题面说若干个框、模型正确追问 n_frames」的 L2 候选。
本脚本把这条素材接成**可机器复算的 artifact**：

  1. 题面缺口机器核验：spec_normalized.name 含 frm3，但 structure.params 无 n_frames；
  2. 候选追问原文从候选文件实读（不手抄）；
  3. 判定直接调用 score_l2.classify()（唯一判据实现，R58），不复制、不手写结论；
  4. 记录候选/task/判据脚本的 sha256，让数字跟着锚点走。

★ 边界：这条素材是**柱壳 d1600 题**，与 C5 演示的建模 case（开孔板/加筋板/柱壳 d1800）
  不同题不同源。它证明的是「澄清这一环的判据链路可用」，不是「演示 case 现场追问过」。
  报告里必须写明，不许把两件事拼成一条链路。

Usage:
  python make_c5_clarify_artifact.py                 # 写默认 artifact
  python make_c5_clarify_artifact.py --out <path>
  python make_c5_clarify_artifact.py --self-test     # 正例 + 2 反例 + 缺口核验
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK_ID = "L2_fuselage_barrel_d1600_l1600_str8_frm3"
CAND_PATH = HERE / "candidates_l2_v7sysfix2_glm" / f"{TASK_ID}.json"
TASKS_PATH = HERE / "tasks" / "tasks.jsonl"
DEFAULT_OUT = HERE / "reports" / "diagnostics" / "c5_clarify_2026-11-18.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_task() -> dict:
    with TASKS_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            if d.get("task_id") == TASK_ID:
                return d
    raise SystemExit(f"[FAIL] 卷里没有 {TASK_ID}: {TASKS_PATH}")


def _gap(task: dict) -> dict:
    """题面缺口：name 声称 frm3，但参数表没有 n_frames。机器核验，不写死结论。"""
    spec = ((task.get("input") or {}).get("spec_normalized") or {})
    name = str(spec.get("name") or "")
    params = (((spec.get("structure") or {}).get("params")) or {})
    return {
        "name": name,
        "name_mentions_frm3": "frm3" in name,
        "params_keys": sorted(params.keys()),
        "n_frames_in_params": "n_frames" in params,
        "gap_verified": ("frm3" in name) and ("n_frames" not in params),
    }


def build() -> dict:
    sys.path.insert(0, str(HERE))
    from score_l2 import classify  # 唯一判据实现（R58）

    for p in (CAND_PATH, TASKS_PATH):
        if not p.exists():
            raise SystemExit(f"[FAIL] 缺素材: {p}")

    task = _load_task()
    cand = json.loads(CAND_PATH.read_text(encoding="utf-8"))
    category, passed, detail = classify(cand, task)  # ★ 不是手抄 "正确"
    gap = _gap(task)

    return {
        "ring": "clarify",
        "task_id": TASK_ID,
        "family": task.get("family"),
        "input_level": task.get("input_level"),
        "source_scope": ("柱壳 d1600 的 L2 题；与 C5 演示 case 不同题不同源，"
                         "只证明澄清环判据链路可用，不代表演示 case 现场追问过"),
        "gap": gap,
        "expected_clarifications": task.get("expected_clarifications") or [],
        "model_clarify_raw": cand.get("clarify"),
        "model_spec": cand.get("spec"),
        "judgement": {"category": category, "pass": passed, "detail": detail},
        "judge_source": "score_l2.classify -> score_baseline.judge_clarify_field_level (R17/R58)",
        "anchors": {
            "candidate": str(CAND_PATH.relative_to(HERE)),
            "candidate_sha256": _sha(CAND_PATH),
            "tasks": str(TASKS_PATH.relative_to(HERE)),
            "tasks_sha256": _sha(TASKS_PATH),
            "judge_script_sha256": _sha(HERE / "score_l2.py"),
        },
        "model": cand.get("model"),
        "prompt_sha256": cand.get("prompt_sha256"),
    }


def self_test() -> int:
    sys.path.insert(0, str(HERE))
    from score_l2 import classify

    task = _load_task()
    cand = json.loads(CAND_PATH.read_text(encoding="utf-8"))

    cat, ok, _ = classify(cand, task)
    assert ok and cat == "clarify_ok", f"正例必须过: {cat}"

    # 反例 A：什么都不输出 —— 该红，防「全部豁免也是过」
    bad = dict(cand); bad["clarify"] = None; bad["spec"] = None
    ok_a = classify(bad, task)[1]
    assert not ok_a, "无输出必须判红"

    # 反例 B：追问与 expected 无关的键 —— 该红，防「命中任意字符串就过」
    bad = dict(cand); bad["clarify"] = json.dumps(["请提供制造厂家的表面处理颜色"],
                                                  ensure_ascii=False)
    cat_b, ok_b, _ = classify(bad, task)
    assert not ok_b and cat_b == "clarify_wrong", f"错键必须判红: {cat_b}"

    gap = _gap(task)
    assert gap["gap_verified"], f"题面缺口核验失败: {gap}"

    out = build()
    assert out["judgement"]["pass"] and out["judgement"]["category"] == "clarify_ok"
    print("[self-test] 5/5 pass (正例 / 无输出 / 错键 / 题面缺口 / artifact 自洽)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    out = build()
    dst = Path(args.out)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    g = out["judgement"]
    print(f"[clarify] {out['task_id']}: {g['category']} pass={g['pass']}")
    print(f"[gap] name 提 frm3={out['gap']['name_mentions_frm3']} · "
          f"params 无 n_frames={not out['gap']['n_frames_in_params']}")
    print(f"[artifact] {dst} ({dst.stat().st_size} bytes)")
    return 0 if g["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
