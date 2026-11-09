"""SOT brief: generate the ONE-PAGE source-of-truth (SOT.md) for this repo.

WHY (expert review 2026-11-09): AGENTS.md §0 used to require reading CLAIMS
(142 KB) + RUBRIC (157 KB) + INDEX (68 KB) + scorecard (68 KB) + the paper
(289 KB) -- about 245k tokens, MORE than a 200k context.  Every session
therefore started near the context limit and drifted.  The fix is a machine-
generated one-pager: everything an agent needs to know BEFORE starting, and
nothing else.  CLAIMS/RUBRIC/paper stay authoritative; this file only points.

Design rules (they are the point):
  * every number is READ from its artifact here, never typed -- with the
    source path AND its mtime printed next to it, so staleness is visible;
  * anything that cannot be parsed prints UNKNOWN with the reason -- silent
    fallback would recreate the "闸没跑起来与闸通过外观一样" failure;
  * output is capped: headings + at most a handful of lines per section.

Usage:
  python sot.py                 # print + write FEM-Bench-Aero/SOT.md
  python sot.py --check         # rc=1 if SOT.md is missing or any source
                                #   file's mtime differs from what it recorded
  python sot.py --stdout-only   # print, do not touch disk
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BENCH = ROOT / "FEM-Bench-Aero"
SOT = BENCH / "SOT.md"
CLAIMS = BENCH / "CLAIMS.md"
RUBRIC = BENCH / "RUBRIC.md"
INDEX = HERE / "reports" / "INDEX.md"
ROADMAP = BENCH / "ROADMAP.md"
DECISION_P2 = BENCH / "DECISION_C6_P2.md"
REPORTS = HERE / "reports"


def _mtime(p: Path) -> str:
    if not p.exists():
        return "missing"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))


def _clip(text: str, n: int = 220) -> str:
    """Cut at the last natural break rather than mid-phrase.

    A hard ``text[:220]`` sliced the headline statement right after
    "唯一变量", which reads like an abandoned sentence.  Cutting at the last
    。/；/—— before the limit keeps the bullet readable; the SOT stays a
    pointer, and the full text is always one artifact away.
    """
    if len(text) <= n:
        return text
    cut = text[:n]
    for sep in ("。", "；", "——", "，"):
        k = cut.rfind(sep)
        if k > n * 0.5:
            return cut[:k + len(sep)] + " …"
    return cut + " …"


def _headline() -> dict:
    """The ONE active claim whose STATUS column says it is the headline.

    R-A7: mentioning the phrase in prose does not count -- only the status
    column.  Negations ("不再是对外 headline") live in the status column of
    historical rows too, so the match requires the positive phrase and
    rejects rows whose status also carries superseded/historical markers.
    """
    sys.path.insert(0, str(HERE))
    from check_claims import parse_claims

    rows = parse_claims(str(CLAIMS))
    hits = []
    for r in rows:
        st = (r.get("status") or "")
        sl = st.lower()
        # R-A7 measured on 2026-11-09: a bare "headline" substring matches EIGHT
        # rows (supporting rows say "不作 headline", historical rows say
        # "当前 headline 见 C-029", C-032 says "active（对外 headline）").
        # Only the exact positive phrase 对外 headline counts, and any negation
        # or cross-reference marker disqualifies the row.
        if "对外 headline" not in st:
            continue
        if any(k in st for k in ("不作", "不再", "不是", "见 C-", "superseded",
                                 "historical", "diagnostic lower")):
            continue
        if "superseded" in sl:
            continue
        hits.append(r)
    if not hits:
        return {"claim_id": "UNKNOWN", "why": "no active row with 'headline' in"
                                               " its status column"}
    if len(hits) > 1:
        return {"claim_id": "MULTIPLE:" + ",".join(
            h.get("claim_id", "?") for h in hits),
            "why": "S-29 requires exactly one headline"}
    r = hits[0]
    stmt = re.sub(r"\s+", " ", (r.get("statement") or "")).strip()
    return {
        "claim_id": r.get("claim_id", "?"),
        "statement_head": _clip(stmt, 220),
        "artifact": (r.get("artifact") or "").strip().strip("`"),
        "status": (r.get("status") or "").strip(),
    }


def _paper() -> dict:
    """Current paper: path + sha + row count, read from INDEX's current-paper row."""
    txt = INDEX.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"`tasks_v(\d+)\.jsonl`（当前考卷，\s*(\d+)\s*条[^|]*?"
                  r"sha\s*`([0-9a-f]{8,})", txt)
    if not m:
        m = re.search(r"`tasks_v(\d+)\.jsonl`[^|]*?(\d+)\s*条[^|]*?sha\s*`([0-9a-f]{8,})",
                      txt)
    if not m:
        return {"path": "UNKNOWN", "why": "INDEX current-paper row not parsed"}
    ver, count, sha = m.groups()
    path = f"reports/papers/tasks_v{ver}.jsonl"
    full = HERE / path
    ok = full.exists()
    actual = None
    if ok:
        actual = hashlib.sha256(full.read_bytes()).hexdigest()
    return {
        "path": path, "version": f"v{ver}", "rows_declared": int(count),
        "sha_declared": sha,
        "sha_actual_prefix": actual[:16] if actual else "UNKNOWN",
        "sha_matches": (actual[:len(sha)] == sha) if actual else None,
        "rows_actual": _count_lines(full) if ok else "UNKNOWN",
    }


def _count_lines(p: Path) -> int:
    n = 0
    with p.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.strip():
                n += 1
    return n


def _rubric_version() -> tuple:
    txt = RUBRIC.read_text(encoding="utf-8", errors="replace")[:4000]
    m = re.search(r"\*\*版本\*\*：\s*v([\d.]+)", txt)
    return (m.group(1) if m else "UNKNOWN"), _mtime(RUBRIC)


def _gates() -> dict:
    out = {}
    cp = REPORTS / "check_claims.json"
    if cp.exists():
        d = json.loads(cp.read_text(encoding="utf-8"))
        out["check_claims"] = {
            "all_ok": d.get("all_ok"), "active": d.get("n_active_claims"),
            "artifacts": d.get("n_artifacts"), "n_fail": d.get("n_fail"),
            "file": cp.name, "mtime": _mtime(cp),
        }
    else:
        out["check_claims"] = {"all_ok": "UNKNOWN", "why": "no check_claims.json"}
    cands = sorted(glob.glob(str(REPORTS / "negative_controls_*.json")))
    if cands:
        nc = Path(cands[-1])
        d = json.loads(nc.read_text(encoding="utf-8"))
        out["negative_controls"] = {
            "all_ok": d.get("all_ok"), "n_cases": d.get("n_cases"),
            "n_ok": d.get("n_ok"), "file": nc.name, "mtime": _mtime(nc),
        }
    else:
        out["negative_controls"] = {"all_ok": "UNKNOWN", "why": "no negctl json"}
    return out


def _prompt_sha() -> dict:
    """Prompt sha from the current scorecard's provenance (authoritative), else UNKNOWN."""
    cands = sorted(glob.glob(str(REPORTS / "baseline_scorecard_L3_v*.json")),
                   key=lambda p: os.path.getmtime(p), reverse=True)
    for c in cands:
        try:
            d = json.loads(Path(c).read_text(encoding="utf-8"))
        except Exception:                            # noqa: BLE001
            continue
        prov = d.get("provenance") or {}
        sha = (prov.get("prompt_sha256") or prov.get("prompt_sha")
               or d.get("prompt_sha256") or d.get("prompt_sha"))
        if sha:
            return {"sha": str(sha)[:16], "file": Path(c).name,
                    "mtime": _mtime(Path(c))}
    return {"sha": "UNKNOWN", "why": "no prompt_sha in any scorecard provenance"}


def _milestones() -> list:
    """ROADMAP §1 board rows: segment | weight | completion (as written)."""
    txt = ROADMAP.read_text(encoding="utf-8", errors="replace")
    seg = txt.split("## 1. 进度看板", 1)
    if len(seg) < 2:
        return []
    block = seg[1].split("\n## ", 1)[0]
    rows = []
    for line in block.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or set("".join(cells)) <= set("-: "):
            continue
        name = re.sub(r"\*+", "", cells[0])
        if not re.match(r"^[ABCD] |^合计", name):
            continue
        rows.append((name, cells[1], re.sub(r"\*+", "", cells[2])))
    return rows[:5]


def _next_step() -> tuple:
    """ONE next step, taken from the live plan rather than remembered here.

    ROADMAP §17 (the 2026-11-09 correction plan) is the only execution plan, so
    the next step is "its first P-row that is not done".  The previous version
    hard-coded "外部复现 → headline 决策 → SOT 减重" and kept saying it after all
    three were finished - a next-step line that is typed rather than read is a
    next-step line that lies.
    """
    txt = ROADMAP.read_text(encoding="utf-8", errors="replace")
    seg = txt.split("## 17.", 1)
    if len(seg) == 2:
        for line in seg[1].splitlines():
            s = line.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) < 3 or not re.match(r"^P\d-\d+$", cells[0]):
                continue
            if "✅" in cells[-1]:
                continue
            item = re.sub(r"\*+", "", cells[1])[:150]
            state = re.sub(r"\*+", "", cells[-1])[:70]
            return (f"{cells[0]} {item} —— {state}", "ROADMAP.md §17")
    seg13 = txt.split("## 13. 下一步", 1)
    if len(seg13) < 2:
        return ("UNKNOWN", "ROADMAP §17/§13 not found")
    for line in seg13[1].splitlines():
        s = line.strip()
        if s.startswith(("- ", "* ", "1.")):
            return (re.sub(r"\*+", "", s[:200]), "ROADMAP.md §13")
    return ("UNKNOWN", "ROADMAP §17 has no pending P-row")


def build() -> str:
    hl = _headline()
    paper = _paper()
    rub, rub_mt = _rubric_version()
    gates = _gates()
    psha = _prompt_sha()
    board = _milestones()
    nxt, nxt_src = _next_step()

    L = []
    L.append("# SOT（机器生成的一页真相 / 不要手改）")
    L.append("")
    L.append(f"> 生成时间 {time.strftime('%Y-%m-%d %H:%M')} · "
             f"`python sot.py` 重建 · 权威顺序 AGENTS > CLAIMS > RUBRIC > INDEX")
    L.append("> **这一页取代 §0 的五文件整读。** 需要细节时按指针读单个 artifact；"
             "禁止整读 CLAIMS/RUBRIC/tasks*.jsonl。")
    L.append("")
    L.append("## 1. 唯一 headline（对外数字只认这一条）")
    L.append("")
    cid = hl.get("claim_id", "")
    if cid.startswith("UNKNOWN") or cid.startswith("MULTIPLE") or \
            "statement_head" not in hl:
        L.append(f"- **{cid or 'UNKNOWN'}** — {hl.get('why', 'unparsed')}")
    else:
        L.append(f"- **{hl['claim_id']}** · {hl['statement_head']}")
        L.append("- 另有**产品成绩单 v8**（五模块 / 五分母并列，**不是 headline**，"
                 "数字块由 `make_product_report.py --check` 守）："
                 "`FEM-Bench-Aero/PRODUCT_REPORT_V8.md`（C-045）")
        L.append(f"- artifact：`{hl['artifact']}` · status：{hl['status']}")
    L.append("")
    L.append("## 2. 当前考卷（换卷即换 sha，数字不可跨卷相减）")
    L.append("")
    if paper.get("path") == "UNKNOWN":
        L.append(f"- **UNKNOWN** — {paper.get('why')}")
    else:
        L.append(f"- `{paper['path']}` · 声明 {paper['rows_declared']} 条 · "
                 f"实读 {paper['rows_actual']} 条")
        L.append(f"- sha 声明 `{paper['sha_declared']}` · 实读前缀 "
                 f"`{paper['sha_actual_prefix']}` · "
                 f"{'一致' if paper['sha_matches'] else '**不一致（换卷未登记）**'}")
    L.append("")
    L.append("## 3. 版本锚点")
    L.append("")
    L.append(f"- RUBRIC **v{rub}**（mtime {rub_mt}）")
    L.append(f"- prompt sha `{psha.get('sha')}`"
             + (f"（{psha['file']}，mtime {psha['mtime']}）"
                if psha.get("file") else f" — {psha.get('why')}"))
    L.append("")
    L.append("## 4. 两道闸（读缓存，不是本次重跑；收口时必须重跑全量）")
    L.append("")
    cc = gates["check_claims"]
    nc = gates["negative_controls"]
    L.append(f"- check_claims：all_ok={cc.get('all_ok')} · "
             f"{cc.get('active')} claims / {cc.get('artifacts')} artifacts · "
             f"{cc.get('file')} @ {cc.get('mtime')}")
    L.append(f"- negative_controls：all_ok={nc.get('all_ok')} · "
             f"{nc.get('n_ok')}/{nc.get('n_cases')} · "
             f"{nc.get('file')} @ {nc.get('mtime')}")
    L.append("")
    L.append("## 5. 里程碑看板（估算，非 artifact，不得进 claim）")
    L.append("")
    if board:
        L.append("| 段 | 权重 | 完成度 |")
        L.append("|---|---:|---:|")
        for name, w, c in board:
            L.append(f"| {name} | {w} | {c} |")
    else:
        L.append("- UNKNOWN（ROADMAP §1 未解析到）")
    L.append("")
    L.append("## 6. 下一步（只有一条）")
    L.append("")
    L.append(f"- {nxt}")
    L.append(f"- 来源：{nxt_src}")
    L.append("")
    L.append("## 7. 本次任务的读取预算（写进 TASK_CONTRACT）")
    L.append("")
    L.append("- 读取 ≤30k tokens：本页 + 本任务直接相关的 1 个 artifact；"
             "禁止整读 CLAIMS/RUBRIC/tasks*.jsonl。")
    L.append("- 写入 ≤10k tokens：每任务最多 1 条 claim + 1 个 artifact + 1 段记忆（≤2KB）。")
    L.append("- 闸：开工读本页；收口跑全量 `negative_controls.py` → `check_claims.py`。")
    L.append("- 发现新方向 → 写 CONFLICT 并停，不继续挖。")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout-only", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        if not SOT.exists():
            print("[FAILED] SOT.md missing", file=sys.stderr)
            return 1
        old = SOT.read_text(encoding="utf-8", errors="replace")
        new = build()
        # compare the data lines only (the timestamp line always differs)
        def body(t):
            return [ln for ln in t.splitlines()
                    if not ln.startswith("> 生成时间")]
        if body(old) != body(new):
            print("[FAILED] SOT.md stale: run `python sot.py`", file=sys.stderr)
            return 1
        print("[ok] SOT.md is current")
        return 0
    txt = build()
    if a.stdout_only:
        print(txt)
        return 0
    SOT.write_text(txt, encoding="utf-8")
    print(txt)
    print(f"wrote {SOT} ({SOT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
