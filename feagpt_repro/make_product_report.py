#!/usr/bin/env python
"""Generate / verify the PRODUCT_REPORT_V8 number block.

Why this file exists
--------------------
The product scorecard is a *summary* page: five modules, five denominators,
all of them already published in other claims.  Hand-typing those numbers is
exactly how C-041's "second pass glm 48/64" happened - a number nobody could
re-derive from an artifact.  So the numbers are generated here, every cell
carries the source file it was read from plus that file's sha256, and
``--check`` fails when the page and the artifacts disagree.

The page keeps its prose by hand; only the block between the NUMBERS markers
is machine-written.

Usage
-----
  python make_product_report.py --json reports/product_report_v8.json \
                                --out ../FEM-Bench-Aero/PRODUCT_REPORT_V8.md
  python make_product_report.py --check      # rc=1 if the page is stale

Read-only w.r.t. the artifacts: this script never writes a scorecard.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE / "reports"
DIAG = REPORTS / "diagnostics"

BEGIN = "<!-- NUMBERS:BEGIN（机器生成，勿手改；`python make_product_report.py --check` 守新鲜度）-->"
END = "<!-- NUMBERS:END -->"

# --- sources: (label, path) ------------------------------------------------
S_V6C = REPORTS / "baseline_scorecard_L3_v6c_p2.json"          # C-032 headline
S_V7_GLM = REPORTS / "baseline_scorecard_L3_v7sysfix_glm.json"
S_V7_DS1 = REPORTS / "baseline_scorecard_L3_v7sysfix_ds.json"
S_V7_DS2 = REPORTS / "baseline_scorecard_L3_v7sysfix2_ds.json"
S_L2 = REPORTS / "l2_clarify_dual.json"
S_INFO_GLM = DIAG / "l2_v8_scores_glm.json"
S_INFO_DS = DIAG / "l2_v8_scores_ds.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"[FAIL] missing artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def tsr(block: dict | None) -> str:
    t = (block or {}).get("tsr") or {}
    if not t.get("total"):
        return "UNKNOWN"
    return f"{t['pass']}/{t['total']} = {t['pct']:.1f}%"


def msr(block: dict | None) -> str:
    m = (block or {}).get("msr")
    if m in (None, "", {}):
        return "未测"
    return str(m)


def collect() -> dict:
    """Every cell: value + the artifact it was read from + that artifact's sha."""
    v6c = load(S_V6C)
    v7g = load(S_V7_GLM)
    v7d1 = load(S_V7_DS1)
    v7d2 = load(S_V7_DS2)
    l2 = load(S_L2)
    ig = load(S_INFO_GLM)
    idd = load(S_INFO_DS)

    out = {
        "what": "产品成绩单 v8 的数字块（五模块/五分母）；每个格子标注来源 artifact 与 sha256",
        "generated_by": "python make_product_report.py",
        "rule": "五分母不可相减、不可排名、不可跨代引用；L2 与 L3 是两层不可互比",
        "modules": {},
    }

    def cell(v, path):
        return {"value": v, "source": str(path.relative_to(HERE)).replace("\\", "/"),
                "source_sha256": sha(path)}

    # A: L3 legacy exam = 唯一 headline (C-032, v6c x prompt v2f)
    out["modules"]["A_l3_legacy_exam"] = {
        "denominator": 25,
        "note": "唯一 headline（C-032）；prompt v2f（6b90daf0…）",
        "glm_tsr": cell(tsr(v6c.get("exam")), S_V6C),
        "glm_msr": cell(msr(v6c.get("exam")), S_V6C),
        "glm_whole_paper_tsr": cell(tsr(v6c), S_V6C),
        "glm_whole_paper_msr": cell(v6c.get("msr") or "UNKNOWN", S_V6C),
        "prompt_sha256": ((v6c.get("provenance") or {}).get("prompt_sha256") or "")[:8],
    }

    # B: L3 exam_v11 = 9
    out["modules"]["B_l3_exam_v11"] = {
        "denominator": 9,
        "note": "内插 v1.1 新题型；两模型全对 ⇒ exam_full 的抬升来自换分母",
        "glm_tsr": cell(tsr(v7g.get("exam_v11")), S_V7_GLM),
        "glm_msr": cell(msr(v7g.get("exam_v11")), S_V7_GLM),
        "ds_tsr": cell(tsr(v7d2.get("exam_v11")), S_V7_DS2),
        "ds_msr": cell(msr(v7d2.get("exam_v11")), S_V7_DS2),
    }

    # C: L3 exam_full = 34 (25 legacy + 9 v11); ds 两批候选 => 报区间
    d1 = (v7d1.get("exam_full") or {}).get("tsr") or {}
    d2 = (v7d2.get("exam_full") or {}).get("tsr") or {}
    lo, hi = sorted([d1.get("pass"), d2.get("pass")])
    den = d2.get("total")
    ds_range = f"[{lo},{hi}]/{den}" if den else "UNKNOWN"
    out["modules"]["C_l3_exam_full"] = {
        "denominator": 34,
        "note": "legacy 25 + v11 9；ds 为两批候选，报区间",
        "glm_tsr": cell(tsr(v7g.get("exam_full")), S_V7_GLM),
        "glm_msr": cell(msr(v7g.get("exam_full")), S_V7_GLM),
        "ds_tsr": {"value": ds_range,
                   "source": f"{S_V7_DS1.name} + {S_V7_DS2.name}",
                   "source_sha256": sha(S_V7_DS1)[:16] + " + " + sha(S_V7_DS2)[:16]},
        "ds_msr": cell(msr(v7d2.get("exam_full")), S_V7_DS2),
        "ds_by_batch": {"batch1": d1.get("pass"), "batch2": d2.get("pass"),
                        "total": den},
    }

    # D: L2 clarified layer (clarify_all 64 / clarify_informative 45)
    # Denominators are DERIVED, not typed: the clarified stratum is the sum of the
    # invalid subset and the informative subset, both of which carry their own
    # task_ids.  Typing 64/45 here is how a denominator silently drifts later.
    n_invalid = len(((l2.get("invalid") or {}).get("task_ids")) or [])
    n_inf = len(((l2.get("clarify_informative") or {}).get("task_ids")) or [])
    n_all = n_invalid + n_inf

    def l2cell(model, key, denom):
        m = ((l2.get("by_model") or {}).get(model) or {}).get(key) or {}
        return {"value": f"{m.get('passed')}/{denom} = {m.get('pct')}%",
                "source": "reports/l2_clarify_dual.json",
                "source_sha256": sha(S_L2)}

    out["modules"]["D_l2_clarified"] = {
        "denominators": {"clarify_all": n_all, "clarify_informative": n_inf,
                         "invalid": n_invalid,
                         "derivation": "n_all = len(invalid.task_ids) + len(clarify_informative.task_ids)"},
        "note": ("glm 同一批候选两次打分均为 46；ds 是两批候选 52/46 ⇒ "
                 "「ds 高 6 条」恰好等于 ds 自己的批间波动 ⇒ 不得排名"),
        "glm_all": l2cell("glm-5.3-flash", "clarify_all", n_all),
        "glm_inf": l2cell("glm-5.3-flash", "clarify_informative", n_inf),
        "glm_invalid": l2cell("glm-5.3-flash", "invalid", n_invalid),
        "ds_all": l2cell("deepseek-v4-pro", "clarify_all", n_all),
        "ds_inf": l2cell("deepseek-v4-pro", "clarify_informative", n_inf),
        "ds_invalid": l2cell("deepseek-v4-pro", "invalid", n_invalid),
    }

    # E: L2 informative stratum (16) - v8 only
    def infcell(doc, path):
        s = (doc.get("strata") or {}).get("informative") or {}
        return cell(f"{s.get('passed')}/{s.get('n')} = {s.get('pct')}%", path)

    out["modules"]["E_l2_informative"] = {
        "denominator": 16,
        "note": "该答不该问；ds 15 条属「该答却追问」（过度澄清）",
        "glm": infcell(ig, S_INFO_GLM),
        "ds": infcell(idd, S_INFO_DS),
    }
    return out


def render_markdown(data: dict) -> str:
    m = data["modules"]
    a, b, c, d, e = (m["A_l3_legacy_exam"], m["B_l3_exam_v11"], m["C_l3_exam_full"],
                     m["D_l2_clarified"], m["E_l2_informative"])
    L = [BEGIN, "", "| 模块 | 分母 | `glm-5.3-flash` | `deepseek-v4-pro` |", "|---|---:|---|---|"]
    L.append(f"| A L3 legacy exam（**唯一 headline**） | {a['denominator']} | "
             f"**{a['glm_tsr']['value']}**／MSR {a['glm_msr']['value']} | —（headline 只报 glm） |")
    L.append(f"| B L3 `exam_v11` | {b['denominator']} | {b['glm_tsr']['value']} | {b['ds_tsr']['value']} |")
    L.append(f"| C L3 `exam_full` | {c['denominator']} | {c['glm_tsr']['value']} | {c['ds_tsr']['value']} |")
    L.append(f"| D L2 澄清层（`clarify_all` / `clarify_informative`） | "
             f"{d['denominators']['clarify_all']} / {d['denominators']['clarify_informative']} | "
             f"{d['glm_all']['value']}／{d['glm_inf']['value']} | "
             f"{d['ds_all']['value']}／{d['ds_inf']['value']} |")
    L.append(f"| E L2 信息完备层 | {e['denominator']} | {e['glm']['value']} | {e['ds']['value']} |")
    L += ["", "来源（脚本逐格实读，sha256 见 `reports/product_report_v8.json`）：", ""]
    L.append(f"- A：`{a['glm_tsr']['source']}`（prompt `{a['prompt_sha256']}…` = v2f 代）")
    L.append(f"- B/C：`{b['glm_tsr']['source']}` + `{c['ds_msr']['source']}`（v2f 代试跑；"
             f"该代只重算 TSR ⇒ MSR 未测）")
    L.append(f"- D：`{d['glm_all']['source']}`（prompt `c8de26d4` = v2f 代）")
    L.append(f"- E：`{e['glm']['source']}` + `{e['ds']['source']}`")
    L += ["", f"> 全卷（含 dev 30）参考：A 模型的整卷 TSR {a['glm_whole_paper_tsr']['value']}、"
              f"MSR {a['glm_whole_paper_msr']['value']}（同一 artifact）。", "", END]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="机器可读汇总输出路径")
    ap.add_argument("--out", help="写入页面（只替换 NUMBERS 块）")
    ap.add_argument("--check", action="store_true", help="校验页面数字块是否最新")
    args = ap.parse_args()

    data = collect()
    block = render_markdown(data)

    if args.json:
        dest = Path(args.json)
        if not dest.is_absolute():
            dest = HERE / dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {dest}")

    if args.out:
        page = Path(args.out)
        if not page.is_absolute():
            page = HERE / page
        text = page.read_text(encoding="utf-8")
        i, j = text.find(BEGIN), text.find(END)
        if i < 0 or j < 0:
            raise SystemExit(f"[FAIL] {page.name} has no NUMBERS block markers")
        page.write_text(text[:i] + block + text[j + len(END):], encoding="utf-8")
        print(f"refreshed numbers in {page}")

    if args.check:
        # The page path is fixed: --check is a freshness gate, not a generic diff.
        page = HERE.parent / "FEM-Bench-Aero" / "PRODUCT_REPORT_V8.md"
        text = page.read_text(encoding="utf-8")
        i, j = text.find(BEGIN), text.find(END)
        if i < 0 or j < 0:
            print(f"[FAIL] {page} has no NUMBERS block")
            return 1
        on_page = text[i:j + len(END)]
        if on_page.strip() != block.strip():
            print("[FAIL] 产品成绩单的数字块与 artifact 不一致 —— 跑 --out 重生成")
            import difflib
            for line in difflib.unified_diff(on_page.splitlines(), block.splitlines(),
                                            "page", "artifacts", lineterm="", n=1):
                print(line)
            return 1
        print(f"[ok] 产品成绩单数字块与 5 处 artifact 一致（{len(data['modules'])} 模块）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
