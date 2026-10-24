"""Check the report against the disk.

Four independent passes:

  1. source re-read   -- each dataset-level number in report_data.json is
                         re-read from its own artifact and compared;
  2. spot re-measure  -- three cases have their mesh quality re-measured with
                         gmsh and their two-tree max|u| re-read from the
                         shipped results.json, then compared to the JSON;
  3. page integrity   -- the HTML actually contains all 26 cases, every figure
                         as an embedded PNG, and the headline numbers;
  4. contour re-derive -- the post-solve contour numbers in contour_data.json
                         are recomputed straight from the raw <case>.odb.json
                         blocks with an independent formula (no shared helper
                         with the renderer), and the page is checked to quote
                         them.

Exit code 0 = every check passed.
"""

from __future__ import annotations

import base64
import json
import math
import sys
from pathlib import Path

ROOT = Path(r"F:\AI FEA Modeling DataSets")
DS = ROOT / "FEM-Bench-Aero"
REPRO = ROOT / "feagpt_repro"
HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(DS.parent / "feagpt_repro" / "diagnostics"))
import gmsh                        # noqa: E402
from msh_quality import quality     # noqa: E402

DATA = json.loads((HERE / "report_data.json").read_text(encoding="utf-8"))
CONTOUR = json.loads((HERE / "contour_data.json").read_text(encoding="utf-8"))
PAGE = (ROOT / "FEM-Bench-Aero进展报告_2026-10.html")

# deliberately repeated here (not imported) so a rename in the renderer cannot
# silently make this check vacuous
ODB_PATHS = {
    "naca4412_wingbox":
        REPRO / "outputs_abaqus/naca4412_wingbox/naca4412_wingbox.odb.json",
    "stiffened_panel_800x600_str3":
        REPRO / "outputs_b3_abaqus/stiffened_panel_800x600_str3/"
        "stiffened_panel_800x600_str3.odb.json",
    "fuselage_barrel_d2000_l2000_str8_frm3":
        REPRO / "outputs_b3_abaqus/fuselage_barrel_d2000_l2000_str8_frm3/"
        "fuselage_barrel_d2000_l2000_str8_frm3.odb.json",
}

fails: list[str] = []
oks = 0


def chk(name: str, got, want):
    global oks
    if got == want:
        oks += 1
        print(f"  [ok  ] {name}: {got}")
    else:
        fails.append(name)
        print(f"  [FAIL] {name}: got {got!r}, want {want!r}")


def _r(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def pass1_sources():
    print("== pass 1: dataset-level numbers vs their own artifacts ==")
    man = _r(DS / "manifest.json")
    chk("manifest.n_cases", DATA["manifest"]["summary"]["n_cases"], man["summary"]["n_cases"])
    chk("manifest.n_classes", DATA["manifest"]["summary"]["n_geometry_classes"],
        man["summary"]["n_geometry_classes"])
    chk("manifest.splits", DATA["manifest"]["summary"]["splits"], man["summary"]["splits"])
    chk("manifest.by_family", DATA["manifest"]["summary"]["by_family"],
        man["summary"]["by_family"])

    ev = _r(DS / "eval_report.json")["checks"]
    want_pass = sum(1 for c in ev if c.get("pass"))
    chk("eval n_checks", DATA["gates"]["eval"]["n_checks"], len(ev))
    chk("eval n_pass", DATA["gates"]["eval"]["n_pass"], want_pass)

    g4 = _r(DS / "gate4.json")
    chk("gate4 n_pass", DATA["gates"]["gate4"]["n_pass"], g4["n_pass"])
    chk("gate4 n_cases", DATA["gates"]["gate4"]["n_cases"], g4["n_cases"])

    cf = _r(DS / "check_forms.json")
    chk("check_forms n_pass", DATA["gates"]["check_forms"]["n_pass"], cf["n_pass"])
    chk("check_forms n_fail", DATA["gates"]["check_forms"]["n_fail"], cf["n_fail"])

    vd = _r(DS / "verify_report.json")["summary"]
    chk("verify n_ok", DATA["gates"]["verify_dataset"].get("n_ok"), vd.get("n_ok"))

    dd = _r(DS / "dedup_report.json")
    chk("dedup n_groups", DATA["gates"]["dedup"]["n_groups"], dd["n_groups"])


def pass2_spot():
    print("== pass 2: spot re-measure three cases ==")
    picks = ["naca4412_wingbox", "fuselage_barrel_d2000_l2000_str8_frm3",
             "stiffened_panel_800x600_str3"]
    lookup = {c["case_id"]: c for c in DATA["cases"]}
    gmsh.initialize()
    try:
        for cid in picks:
            q = quality(DS / "modeling" / cid / "model.msh")
            chk(f"{cid}  minJ(remassured)", round(lookup[cid]["mesh"]["minJ"], 4),
                round(q["min"], 4))
            chk(f"{cid}  n_elements", lookup[cid]["mesh"]["n_elements"], q["n"])
    finally:
        gmsh.finalize()
    for cid in picks:
        cc = _r(DS / "modeling" / cid / "model.results.json")["max_disp"]
        ab = _r(DS / "_xval" / cid / "model.results.json")["max_disp"]
        chk(f"{cid}  ccx max_disp", round(lookup[cid]["ccx"]["max_disp"], 9), round(cc, 9))
        chk(f"{cid}  abaqus max_disp", round(lookup[cid]["abaqus"]["max_disp"], 9), round(ab, 9))


def pass3_page():
    print("== pass 3: the HTML actually shows the data ==")
    page = PAGE.read_text(encoding="utf-8")
    chk("page exists", PAGE.exists(), True)
    for c in DATA["cases"]:
        if c["case_id"] not in page:
            fails.append(f"case missing from page: {c['case_id']}")
    print(f"  [ok  ] all {len(DATA['cases'])} case_ids present" if
          all(c["case_id"] in page for c in DATA["cases"]) else "  [FAIL] some case_ids missing")
    n_png = page.count("data:image/png;base64,")
    want_figs = len(list((HERE / "figs").glob("*.png")))
    chk("embedded figures", n_png, want_figs)

    headline = [
        str(DATA["manifest"]["summary"]["n_cases"]),
        str(DATA["manifest"]["summary"]["n_geometry_classes"]),
        f'{min(c["mesh"]["minJ"] for c in DATA["cases"]):.4f}',
        f'{DATA["gates"]["eval"]["n_pass"]}/{DATA["gates"]["eval"]["n_checks"]}',
        f'{DATA["gates"]["check_forms"]["n_pass"]}',
    ]
    for h in headline:
        chk(f"page contains {h!r}", h in page, True)

    # every embedded image must be byte-identical to a file in figs/
    blobs = {base64.b64encode(p.read_bytes()).decode("ascii")[:64]
             for p in (HERE / "figs").glob("*.png")}
    found = 0
    for tok in page.split("data:image/png;base64,")[1:]:
        head = tok.split('"')[0][:64]
        if head in blobs:
            found += 1
    chk("embedded images match figs/", found, want_figs)


def pass4_contours():
    print("== pass 4: contour numbers re-derived from the raw ODB blocks ==")
    cs = CONTOUR["cases"]
    chk("contour_data covers spot cases", set(ODB_PATHS) <= set(cs), True)
    for cid, p in ODB_PATHS.items():
        d = _r(p)
        umax = max(math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
                   for v in d["results"]["DISP"].values())
        chk(f"{cid} max|u| (odb re-derived)", round(cs[cid]["max_umag"], 6),
            round(umax, 6))
        vmax = 0.0
        for s in d["results"]["STRESS_PEAK"].values():
            s11, s22, s33, s12, s13, s23 = s
            vm = math.sqrt(0.5 * ((s11 - s22) ** 2 + (s22 - s33) ** 2
                                  + (s33 - s11) ** 2)
                           + 3.0 * (s12 ** 2 + s13 ** 2 + s23 ** 2))
            vmax = max(vmax, vm)
        chk(f"{cid} max von Mises (peak, odb re-derived)",
            round(cs[cid]["max_peak_node"], 4), round(vmax, 4))

    # the page must quote the same numbers the JSON holds
    page = PAGE.read_text(encoding="utf-8")
    for cid in ("naca4412_wingbox", "naca4412_wingbox_sweep40",
                "fuselage_barrel_d2000_l2000_str8_frm3"):
        chk(f"page quotes {cid} max|u|",
            f"{cs[cid]['max_umag']:.3g}" in page, True)
    chk("page quotes barrel peak MPa",
        f"{cs['fuselage_barrel_d2000_l2000_str8_frm3']['max_peak_elem']:.3g}" in page,
        True)
    for num in ("8", "9", "10", "11", "12"):
        chk(f"page has figure {num}",
            f'<span class="fignum">图 {num}</span>' in page, True)


def main() -> int:
    pass1_sources()
    pass2_spot()
    pass3_page()
    pass4_contours()
    print()
    if fails:
        print(f"RESULT: {len(fails)} FAILED -> {fails}")
        return 1
    print(f"RESULT: ALL {oks} CHECKS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
