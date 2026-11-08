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
        good = [f for f in frames if f["has_U"]]
        if not good:
            raise RuntimeError("no frame contains a U field; is *OUTPUT, FIELD / "
                               "*NODE OUTPUT U present in the *BUCKLE step?")
        if len(good) != expect_modes:
            print(f"WARNING: got {len(good)} U frames, expected {expect_modes}",
                  file=sys.stderr)

        nodes_bin = prefix.with_suffix(".nodes.bin")
        u_bin = prefix.with_suffix(".u.bin")
        meta_path = prefix.with_suffix(".meta.json")
        with nodes_bin.open("wb") as fh:
            for n in node_labels:
                fh.write(struct.pack("<q", n))
        with u_bin.open("wb") as fh:
            for f in good:
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
            "n_u_frames": len(good),
            "n_nodes": len(node_labels),
            "node_label_first": node_labels[0],
            "node_label_last": node_labels[-1],
            "nodes_bin": str(nodes_bin).replace("\\", "/"),
            "nodes_bin_sha256": _sha(nodes_bin),
            "u_bin": str(u_bin).replace("\\", "/"),
            "u_bin_sha256": _sha(u_bin),
            "layout": "u.bin = frame-major, node-major, xyz, little-endian float64; "
                      "nodes.bin = little-endian int64, same order for every frame",
            "note": "U frames here are mode shapes, NOT static displacements. "
                    "Normalize per frame before MAC (scale invariant).",
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        print(f"OK step={step_name} frames={len(step.frames)} "
              f"u_frames={len(good)} nodes={len(node_labels)}")
        print(f"   nodes_bin={nodes_bin.name} u_bin={u_bin.name} meta={meta_path.name}")
        return 0
    finally:
        odb.close()


def main(argv=None) -> int:
    """Accept POSITIONAL args, same as the proven odb_batch.py call:

        abaqus python extract_buckle_odb.py <odb> <prefix> [expect_modes]

    Abaqus' own command layer parses leading options first, so a leading
    ``--odb`` may be swallowed.  odb_batch.py:180 uses plain positionals and
    was verified on the real machine (2026-11-06) -- stay byte-compatible.
    Optional flags are still accepted when run by a normal python.
    """
    args = list(sys.argv[1:] if argv is None else argv)
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
