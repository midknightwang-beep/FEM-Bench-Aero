# -*- coding: utf-8 -*-
"""parse_xval_v11_log.py — 把 verify_solvers 的 9 条实测输出转录成机读证据。

为什么要这一步：`FEM-Bench-Aero/modeling/` 与 `_xval/` 只存六件套，
**没有 .frd / .odb.json**，所以场级（逐节点）证据不在发布树里。
gate3_all55.py 对翼盒 34 条引用的是 `gates_all55_d36.json` 的既有明细；
v1.1 新增的 5 条翼盒在该文件里**没有明细**，于是被 `idx is None -> pass 继承整体`
误标成 field-level —— 等级高于证据（红线 R2 的镜像）。

本脚本不改任何判定，只把本轮 `_v11_xval_9cases.log` 里的实测数字转录成 JSON，
并逐条断言：四个关键读数齐全、且与 log 原文逐字一致（转录不做算术）。
判据口径按族写死，与 gate3_all55.py 一致：
  - wingbox / open_hole_panel / stiffened_panel：max|u| 差 < 1%（GATED）
  - fuselage_barrel：D20 铁律，model-wide max|u| REPORTED NOT GATED
"""
import json
import os
import re
import sys

LOG = (r"F:\AI FEA Modeling DataSets\feagpt_repro\reports\diagnostics"
       r"\xval_v11_9cases.log")
OUT = (r"F:\AI FEA Modeling DataSets\feagpt_repro\reports\diagnostics"
       r"\xval_v11_9cases.json")

# 判据口径（与 gate3_all55.py 完全一致，不得各自发明）
FAMILY_GATE = {
    "wingbox": ("clamp", 500.0, True),
    "open_hole_panel": ("clamp", 4000.0, True),
    "stiffened_panel": ("all", None, True),
    "fuselage_barrel": ("all", None, False),   # D20：只报不判
}

CASE_HEAD = re.compile(r"^##########\s+(\S+)\s+\(force=(\S+) reaction-set=(\S+)\)")
RE_MAXU = re.compile(
    r"4\) max \|u\|\s+: ccx ([\d.]+) mm vs abaqus ([\d.]+) mm -> diff ([\d.]+) %")
RE_NODE = re.compile(
    r"per-node field \((\d+) nodes\) : median diff ([\d.]+) %, p90 ([\d.]+) %")
RE_VM = re.compile(
    r"outer-fibre peak, ccx vs abaqus: diff ([\d.]+) %")
RE_VERDICT = re.compile(r"VERDICT: (PASS|CHECK|FAIL)")

SPEC_DIR = r"F:\AI FEA Modeling DataSets\feagpt_repro\_v11\runs"


def family_of(cid):
    p = os.path.join(SPEC_DIR, cid, cid + ".spec.json")
    return json.load(open(p, encoding="utf-8"))["structure"]["family"]


def main():
    text = open(LOG, encoding="utf-8", errors="replace").read().splitlines()
    blocks, cur = [], None
    for ln in text:
        m = CASE_HEAD.match(ln)
        if m:
            cur = {"case_id": m.group(1), "cli_force": m.group(2),
                   "cli_reaction_set": m.group(3), "lines": []}
            blocks.append(cur)
            continue
        if cur is not None:
            cur["lines"].append((ln, ))
            if "VERDICT:" in ln:
                cur = None

    cases, problems = [], []
    for b in blocks:
        body = "\n".join(l[0] for l in b["lines"])
        cid = b["case_id"]
        rec = {"case_id": cid, "family": family_of(cid)}

        m = RE_MAXU.search(body)
        n = RE_NODE.search(body)
        v = RE_VM.search(body)
        w = RE_VERDICT.search(body)
        if not (m and n and v and w):
            problems.append("%s: missing reading (maxu=%s node=%s vm=%s verdict=%s)"
                            % (cid, bool(m), bool(n), bool(v), bool(w)))
            continue

        rec["max_u_ccx_mm"] = float(m.group(1))
        rec["max_u_abaqus_mm"] = float(m.group(2))
        rec["max_u_gap_pct"] = float(m.group(3))
        rec["n_nodes_compared"] = int(n.group(1))
        rec["vm_median_gap_pct"] = float(n.group(2))
        rec["vm_p90_gap_pct"] = float(n.group(3))
        rec["vm_peak_gap_pct"] = float(v.group(1))
        rec["verify_solvers_verdict"] = w.group(1)

        rs, force, gated = FAMILY_GATE[rec["family"]]
        rec["gate"] = {
            "reaction_set": rs,
            "force_n": force,
            "max_u_gated": gated,
            "rule": ("D20: model-wide max|u| REPORTED NOT GATED"
                     if not gated else "max|u| gap < 1.0%"),
        }
        rec["moved"] = (rec["max_u_ccx_mm"] > 0 and rec["max_u_abaqus_mm"] > 0
                        and rec["n_nodes_compared"] > 0)
        if gated:
            rec["pass"] = bool(rec["max_u_gap_pct"] < 1.0)
        else:
            rec["pass"] = True     # 不判，只记录
        if not rec["moved"]:
            problems.append("%s: readings not positive (model may be empty)" % cid)
            rec["pass"] = False
        cases.append(rec)

    n_gated = sum(1 for c in cases if c["gate"]["max_u_gated"])
    n_pass = sum(1 for c in cases if c["pass"])
    report = {
        "milestone": "v1.1 close / W5B T-A7 (2026-10-28)",
        "tool": "feagpt_repro/verify_solvers.py",
        "command_root": {
            "ccx": "feagpt_repro/_v11/runs",
            "abaqus": "feagpt_repro/_v11/runs_abaqus",
        },
        "raw_log": "_v11_xval_9cases.log",
        "note": ("场级（逐节点）实测由 verify_solvers 独立计算，本文件只做转录。"
                 "判据口径与 gate3_all55.py 完全一致；柱壳按 D20 只报不判。"),
        "n_cases": len(cases),
        "n_gated": n_gated,
        "n_reported_only": len(cases) - n_gated,
        "n_pass": n_pass,
        "all_pass": n_pass == len(cases) and not problems,
        "problems": problems,
        "cases": cases,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(report, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("cases=%d gated=%d reported_only=%d pass=%d"
          % (len(cases), n_gated, len(cases) - n_gated, n_pass))
    for c in cases:
        print("  %-42s %-16s max|u| %6.3f%%  vm_med %5.2f%%  %s%s"
              % (c["case_id"], c["family"], c["max_u_gap_pct"],
                 c["vm_median_gap_pct"],
                 "PASS" if c["pass"] else "FAIL",
                 "" if c["gate"]["max_u_gated"] else "  (reported only)"))
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  *", p)
    print("out ->", OUT)
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
