"""Benchmark: how slow is matplotlib 3-D polygon rendering at our mesh sizes?

Shell contours are drawn as one coloured quad per element.  The barrel case has
157 972 elements; before committing to a renderer we measure the cost.
"""
from __future__ import annotations

import time

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def bench(nelem: int):
    rng = np.random.default_rng(0)
    # a flat-ish grid of quads
    nx = int(np.sqrt(nelem))
    ny = max(nelem // nx, 1)
    xs = np.linspace(0, 100, nx + 1)
    ys = np.linspace(0, 100, ny + 1)
    X, Y = np.meshgrid(xs, ys)
    Z = np.sin(X / 20) * 5
    pts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    idx = np.arange((nx + 1) * (ny + 1)).reshape(ny + 1, nx + 1)
    quads = []
    for j in range(ny):
        for i in range(nx):
            quads.append([idx[j, i], idx[j, i + 1], idx[j + 1, i + 1], idx[j + 1, i]])
    quads = np.asarray(quads)[:nelem]
    verts = pts[quads]
    cvals = verts[:, :, 2].mean(axis=1)

    t0 = time.time()
    fig = plt.figure(figsize=(7, 6), dpi=110)
    ax = fig.add_subplot(111, projection="3d")
    cmap = plt.get_cmap("turbo")
    norm = plt.Normalize(cvals.min(), cvals.max())
    pc = Poly3DCollection(verts, facecolors=cmap(norm(cvals)), edgecolors="none")
    ax.add_collection3d(pc)
    ax.auto_scale_xyz(pts[:, 0], pts[:, 1], pts[:, 2])
    t1 = time.time()
    fig.savefig(f"_report/figs/_bench_{nelem}.png", dpi=110)
    t2 = time.time()
    plt.close(fig)
    print(f"nelem={len(quads):7d}  build={t1-t0:6.2f}s  save={t2-t1:6.2f}s  total={t2-t0:6.2f}s")


if __name__ == "__main__":
    for n in (5144, 67300, 157972):
        bench(n)
