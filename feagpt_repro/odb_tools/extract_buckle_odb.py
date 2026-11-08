"""Extract Abaqus *BUCKLE mode shapes from an existing .odb (P0-3 / U14).

RUN WITH ``abaqus python`` (NOT the project venv, NOT the agent sandbox).
Abaqus inside the WorkBuddy agent always fails (tsbx.dll), so the user runs
run_p2_abq_modes_MANUAL.bat OUTSIDE WorkBuddy.  The three .odb files from the
2026-11-08 scaling batch already contain ``*OUTPUT, FIELD / *NODE OUTPUT U``,
so NO re-solve is needed -- this script only reads.

Output per job (compact binary, no giant JSON):
  <prefix>.meta.json  : step/frame metadata, node-label order, sha256 anchors
  <prefix>.nodes.bin  : int64 node labels, ascending order as emitted
  <prefix>.u.bin      : float64 U, frame-major then node-major then xyz

Known Abaqus API traps (see feagpt/abaqus_odb.py):
  * frame.fieldOutputs is a Repository: use [] / keys(), never .get()
  * v.nodeLabel may not be unique across instances -> prefix handled by
    checking for duplicates and failing closed
  * a *BUCKLE step has one frame per eigenvalue, plus possibly a zero frame
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


def _field(frame, name):
    try:
        return frame.fieldOutputs[name]
    except (KeyError, AttributeError):
        return None


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify_frames(u_frames, expect_modes: int):
    """Split U frames into (mode_frames, baseline, count_ok).

    Shared by extract() and the offline self-test (pure logic, no odbAccess).
    A *BUCKLE step carries ONE baseline frame (mode=0: the static base state,
    same role as the lambda=0 static field in frame 1 of a ccx .frd) followed
    by one frame per eigenmode (mode=1..N).  Verified on the real machine
    2026-11-08: 7 U frames -> mode 0..6; frame 0 is the baseline and must NOT
    enter the mode-shape bins.  A missing baseline is tolerated (not every
    solver/version emits one); a U frame without a 'mode' attribute is not
    classifiable -> fail closed.
    """
    baseline, mode_frames = [], []
    for f in u_frames:
        mv = f.get("mode")
        if mv is None:
            raise RuntimeError("U frame without a 'mode' attribute; cannot "
                               "distinguish the baseline frame from eigenmodes")
        (mode_frames if int(mv) >= 1 else baseline).append(f)
    return mode_frames, baseline, len(mode_frames) == expect_modes


def extract(odb_path: Path, prefix: Path, expect_modes: int = 6) -> int:
    from odbAccess import openOdb  # Abaqus Python only

    odb = openOdb(str(odb_path), readOnly=True)
    try:
        step_names = list(odb.steps.keys())
        buckle_steps = [n for n in step_names if "BUCKLE" in n.upper()
                        or "STEP" in n.upper()]
        step_name = buckle_steps[-1] if buckle_steps else step_names[-1]
        step = odb.steps[step_name]
        frames = []
        node_labels: list[int] | None = None
        for i, frame in enumerate(step.frames):
            u = _field(frame, "U")
            if u is None:
                frames.append({"index": i, "has_U": False,
                               "frame_value": getattr(frame, "frameValue", None),
                               "fields": sorted(frame.fieldOutputs.keys())})
                continue
            labels = [int(v.nodeLabel) for v in u.values]
            # Do NOT build a 3*N float list here: the second pass writes the
            # binary straight from u.values.  The first pass is metadata only.
            if len(set(labels)) != len(labels):
                raise RuntimeError("duplicate nodeLabel in U field; refusing to emit "
                                   "ambiguous nodal mapping")
            if node_labels is None:
                node_labels = labels
            elif labels != node_labels:
                raise RuntimeError("U field node order differs between frames; "
                                   "refusing to emit unaligned mode shapes")
            frames.append({"index": i, "has_U": True, "n_values": len(labels),
                           "frame_value": getattr(frame, "frameValue", None),
                           "mode": getattr(frame, "mode", None),
                           "fields": sorted(frame.fieldOutputs.keys())})
        u_frames = [f for f in frames if f["has_U"]]
        if not u_frames:
            raise RuntimeError("no frame contains a U field; is *OUTPUT, FIELD / "
                               "*NODE OUTPUT U present in the *BUCKLE step?")
        # Baseline vs eigenmode split: see classify_frames().  The real-machine
        # evidence for this exact split lives in each job's meta.json.
        mode_frames, baseline, count_ok = classify_frames(u_frames, expect_modes)
        count_bad = not count_ok
        if count_bad:
            print(f"[FAILED] got {len(mode_frames)} eigenmode frames (mode>=1) "
                  f"+ {len(baseline)} baseline frame(s); expected "
                  f"{expect_modes} modes", file=sys.stderr)

        nodes_bin = prefix.with_suffix(".nodes.bin")
        u_bin = prefix.with_suffix(".u.bin")
        meta_path = prefix.with_suffix(".meta.json")
        with nodes_bin.open("wb") as fh:
            for n in node_labels:
                fh.write(struct.pack("<q", n))
        with u_bin.open("wb") as fh:
            for f in mode_frames:
                u = _field(step.frames[f["index"]], "U")
                for v in u.values:
                    d = v.data
                    fh.write(struct.pack("<3d", float(d[0]), float(d[1]), float(d[2])))
        meta = {
            "what": "Abaqus *BUCKLE mode shapes extracted from existing .odb",
            "odb": str(odb_path).replace("\\", "/"),
            "odb_sha256": _sha(odb_path),
            "step": step_name,
            "all_steps": step_names,
            "n_frames_in_step": len(step.frames),
            "frames": frames,
            "n_u_frames": len(mode_frames),
            "n_baseline_frames": len(baseline),
            "baseline_frames": [{"index": f["index"],
                                 "frame_value": f["frame_value"],
                                 "mode": f["mode"]} for f in baseline],
            "n_nodes": len(node_labels),
            "node_label_first": node_labels[0],
            "node_label_last": node_labels[-1],
            "nodes_bin": str(nodes_bin).replace("\\", "/"),
            "nodes_bin_sha256": _sha(nodes_bin),
            "u_bin": str(u_bin).replace("\\", "/"),
            "u_bin_sha256": _sha(u_bin),
            "layout": "u.bin = frame-major, node-major, xyz, little-endian float64; "
                      "nodes.bin = little-endian int64, same order for every frame",
            "note": "u.bin holds ONLY eigenmode frames (mode>=1). The baseline/"
                    "static frame (mode=0, the lambda=0 analogue of the ccx .frd "
                    "first frame) is recorded in baseline_frames but NOT written "
                    "to u.bin. Normalize per frame before MAC (scale invariant).",
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        print(f"OK step={step_name} frames={len(step.frames)} "
              f"u_frames={len(mode_frames)} baseline={len(baseline)} "
              f"nodes={len(node_labels)}")
        print(f"   nodes_bin={nodes_bin.name} u_bin={u_bin.name} meta={meta_path.name}")
        return 1 if count_bad else 0
    finally:
        odb.close()


def self_test() -> int:
    """Offline logic test (no odbAccess).  The test input is the REAL frame
    list recorded by the failed 2026-11-08 manual run (p100 meta.json,
    7 U frames with mode 0..6) -- not a hand-written fragment, so the
    self-test cannot drift from the real machine."""
    pins = []

    def pin(name, cond):
        pins.append((name, bool(cond)))

    real_meta = Path(__file__).resolve().parent.parent / (
        "_p2_abq_scaling/fuselage_barrel_d1600_l1600_str8_frm3_buckle_p100_abq"
        "/p100_modes.meta.json")
    assert real_meta.is_file(), f"self-test needs the real-machine meta: {real_meta}"
    real_frames = json.loads(real_meta.read_text(encoding="utf-8"))["frames"]
    real_u = [f for f in real_frames if f.get("has_U")]
    assert len(real_u) == 7, f"expected the 7-frame real batch, got {len(real_u)}"

    modes, baseline, ok = classify_frames(real_u, 6)
    pin("real 7 frames -> 6 modes + 1 baseline, count ok",
        len(modes) == 6 and len(baseline) == 1 and ok)
    pin("baseline is the mode=0 / frame_value=0.0 frame (real-machine anchor)",
        len(baseline) == 1 and int(baseline[0]["mode"]) == 0
        and float(baseline[0]["frame_value"]) == 0.0
        and int(baseline[0]["index"]) == 0)
    pin("mode frames are mode 1..6 in file order",
        [int(f["mode"]) for f in modes] == [1, 2, 3, 4, 5, 6])

    no_mode = [dict(f, mode=None) for f in real_u]
    try:
        classify_frames(no_mode, 6)
        pin("unclassifiable frame (mode=None) rejected", False)
    except RuntimeError:
        pin("unclassifiable frame (mode=None) rejected", True)

    no_baseline = [f for f in real_u if int(f["mode"]) >= 1]
    m2, b2, ok2 = classify_frames(no_baseline, 6)
    pin("missing baseline tolerated, 6 modes still pass",
        len(m2) == 6 and len(b2) == 0 and ok2)

    short = [f for f in real_u if 1 <= int(f["mode"]) <= 5]
    _, _, ok3 = classify_frames(short, 6)
    pin("5 modes -> count_bad", ok3 is False)

    for name, ok_flag in pins:
        print(f"  [{'ok' if ok_flag else 'FAIL'}] {name}")
    print(f"self-test: {sum(1 for _, o in pins if o)}/{len(pins)} pins")
    return 0 if all(o for _, o in pins) else 1


def main(argv=None) -> int:
    """Accept POSITIONAL args, same as the proven odb_batch.py call:

        abaqus python extract_buckle_odb.py <odb> <prefix> [expect_modes]

    Abaqus' own command layer parses leading options first, so a leading
    ``--odb`` may be swallowed.  odb_batch.py:180 uses plain positionals and
    was verified on the real machine (2026-11-06) -- stay byte-compatible.
    Optional flags are still accepted when run by a normal python.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in args:
        return self_test()
    if len(args) >= 2 and not args[0].startswith("-"):
        expect = int(args[2]) if len(args) > 2 else 6
        return extract(Path(args[0]), Path(args[1]), expect)
    ap = argparse.ArgumentParser()
    ap.add_argument("--odb", required=True)
    ap.add_argument("--prefix", required=True, help="output path prefix (no suffix)")
    ap.add_argument("--expect-modes", type=int, default=6)
    a = ap.parse_args(args)
    return extract(Path(a.odb), Path(a.prefix), a.expect_modes)


if __name__ == "__main__":
    raise SystemExit(main())
