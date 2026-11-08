"""Validate the artifacts produced by the external Abaqus mode-shape job.

Runs with the PROJECT VENV python (no Abaqus needed): reads meta.json, checks
frame/node counts, verifies the compact binary files are complete and that
their sha256 matches the metadata.  Called by
run_p2_abq_modes_MANUAL.bat after each 'abaqus python' extraction, and can
also be run standalone after all three jobs are done.

Fail-closed: any mismatch returns rc=1, which stops the bat.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_JOBS = _HERE / "_p2_abq_scaling"
_BASE = "fuselage_barrel_d1600_l1600_str8_frm3_buckle"
TAGS = ("p100", "p050", "p020")
EXPECT_MODES = 6


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_one(tag: str) -> dict:
    d = _JOBS / f"{_BASE}_{tag}_abq"
    meta_p = d / f"{tag}_modes.meta.json"
    if not meta_p.is_file():
        raise RuntimeError(f"{tag}: missing {meta_p.name}")
    m = json.loads(meta_p.read_text(encoding="utf-8"))
    nodes_p = d / f"{tag}_modes.nodes.bin"
    u_p = d / f"{tag}_modes.u.bin"
    if not nodes_p.is_file() or not u_p.is_file():
        raise RuntimeError(f"{tag}: missing nodes.bin / u.bin")
    n_nodes = int(m["n_nodes"])
    n_frames = int(m["n_u_frames"])
    assert n_nodes > 0 and n_frames > 0
    assert nodes_p.stat().st_size == n_nodes * 8, f"{tag}: nodes.bin size mismatch"
    assert u_p.stat().st_size == n_frames * n_nodes * 3 * 8, \
        f"{tag}: u.bin size mismatch ({u_p.stat().st_size} vs expected)"
    assert sha(nodes_p) == m["nodes_bin_sha256"], f"{tag}: nodes.bin sha mismatch"
    assert sha(u_p) == m["u_bin_sha256"], f"{tag}: u.bin sha mismatch"
    assert n_frames == EXPECT_MODES, f"{tag}: n_u_frames={n_frames}, expected {EXPECT_MODES}"
    # spot-decode first/last node labels + first frame's first vector
    with nodes_p.open("rb") as fh:
        first = struct.unpack("<q", fh.read(8))[0]
        fh.seek(-8, 2)
        last = struct.unpack("<q", fh.read(8))[0]
    assert first == m["node_label_first"] and last == m["node_label_last"], \
        f"{tag}: node label endpoints mismatch"
    with u_p.open("rb") as fh:
        u0 = struct.unpack("<3d", fh.read(24))
    finite = all(abs(x) < 1e30 for x in u0)
    assert finite, f"{tag}: non-finite displacement in first frame"
    return {"tag": tag, "n_nodes": n_nodes, "n_u_frames": n_frames,
            "node_first": first, "node_last": last,
            "u0": list(u0), "sha_ok": True, "status": "ok"}


def self_test() -> int:
    """Constructive self-test: a synthetic good artifact must pass, and three
    mutations must be rejected.  Uses a temp dir, never touches real jobs."""
    import tempfile
    global _JOBS
    saved = _JOBS
    pins = []

    def pin(name, cond):
        pins.append((name, bool(cond)))

    try:
        with tempfile.TemporaryDirectory() as td:
            _JOBS = Path(td)
            d = _JOBS / f"{_BASE}_p020_abq"
            d.mkdir(parents=True)
            n_nodes, n_frames = 4, 6
            nodes = d / "p020_modes.nodes.bin"
            u = d / "p020_modes.u.bin"
            meta = d / "p020_modes.meta.json"
            with nodes.open("wb") as fh:
                for x in (101, 102, 103, 104):
                    fh.write(struct.pack("<q", x))
            with u.open("wb") as fh:
                for i in range(n_frames):
                    for j in range(n_nodes):
                        fh.write(struct.pack("<3d", 1.0 + i, 0.0, 0.0))
            m = {"n_nodes": n_nodes, "n_u_frames": n_frames,
                 "node_label_first": 101, "node_label_last": 104,
                 "nodes_bin_sha256": sha(nodes), "u_bin_sha256": sha(u)}
            meta.write_text(json.dumps(m), encoding="utf-8")
            pin("good artifact passes", check_one("p020")["status"] == "ok")

            # mutation 1: u.bin sha mismatch
            with u.open("ab") as fh:
                fh.write(b"\x00")
            pin("extra bytes rejected", main(["p020"]) == 1)
            m["u_bin_sha256"] = sha(u)
            meta.write_text(json.dumps(m), encoding="utf-8")
            pin("sha mismatch rejected (size also wrong)", main(["p020"]) == 1)

            # restore size, keep wrong sha in meta
            u.write_bytes(u.read_bytes()[:-1])
            m["u_bin_sha256"] = "0" * 64
            meta.write_text(json.dumps(m), encoding="utf-8")
            pin("sha mismatch rejected (size correct)", main(["p020"]) == 1)

            # mutation 2: frame count wrong
            m["u_bin_sha256"] = sha(u)
            m["n_u_frames"] = 5
            meta.write_text(json.dumps(m), encoding="utf-8")
            pin("n_u_frames != 6 rejected", main(["p020"]) == 1)

            # mutation 3: missing u.bin
            m["n_u_frames"] = 6
            meta.write_text(json.dumps(m), encoding="utf-8")
            u.unlink()
            pin("missing u.bin rejected", main(["p020"]) == 1)
    finally:
        _JOBS = saved
    for name, ok in pins:
        print(f"  [{'ok' if ok else 'FAIL'}] {name}")
    print(f"self-test: {sum(1 for _, ok in pins if ok)}/{len(pins)} pins")
    return 0 if all(ok for _, ok in pins) else 1


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in args:
        return self_test()
    tags = [a for a in args if a in TAGS] or list(TAGS)
    rows = []
    try:
        for t in tags:
            r = check_one(t)
            rows.append(r)
            print(f"  [ok] {t}: nodes={r['n_nodes']} frames={r['n_u_frames']} "
                  f"labels {r['node_first']}..{r['node_last']}")
        # cross-tier: same mesh => identical node-label files
        refs = [(_JOBS / f"{_BASE}_{t}_abq" / f"{t}_modes.nodes.bin").read_bytes()
                for t in tags]
        assert all(x == refs[0] for x in refs), \
            "node-label files differ across tiers -- nodal mapping not shared"
        print(f"VALIDATED {len(rows)}/{len(tags)} mode sets; node labels identical across tiers")
        return 0
    except (AssertionError, RuntimeError, KeyError, ValueError) as e:
        print(f"[FAILED] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
