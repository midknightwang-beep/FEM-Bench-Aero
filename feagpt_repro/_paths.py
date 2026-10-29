# -*- coding: utf-8 -*-
"""跨盘符安全的「展示用相对路径」助手。

为什么单独成一个文件（而不是各脚本复制一份 `_rel`）：
`os.path.relpath('F:/...', 'C:/Temp')` 在 Windows 上直接抛
`ValueError: path is on mount 'C:', start on mount 'F:'`。

这个坑的复发史（**教训不是「修一下」，是「别只修撞到的那一处」**）：
  · 2026-10-28 在 `check_claims.py` / `report_l2_clarify.py` 撞到 ⇒ 各补了一个 `_rel`；
  · 2026-10-29 跑 `bootstrap_ci.py`（scorecard 在 C:/Temp）⇒ 又炸，因为它没有兜底。
  这说明「点修」必然长回来。收敛到一处，才能真正消掉这个漂移面。

用法：
    from _paths import rel
    'tasks_path': rel(tasks_path, HERE)       # 在 F: 内输出与原 relpath 逐字相同
    'source':     rel(path)                   # start 默认 = 本文件所在目录（feagpt_repro/）
"""
import os

#: 默认起点 = `feagpt_repro/`，与本目录下所有脚本的 `HERE` 相同
HERE = os.path.dirname(os.path.abspath(__file__))


def rel(p, start=None):
    """相对 `start`（默认 `feagpt_repro/`）的展示路径，分隔符统一 `/`。

    跨盘符时**退回绝对路径**而不是抛错：这类字段只用于人读溯源，
    路径在 C: 上并不代表数据错，抛错等于把「展示层的小事」升级成「任务失败」。
    """
    start = start or HERE
    try:
        return os.path.relpath(p, start).replace('\\', '/')
    except ValueError:
        return os.path.abspath(p).replace('\\', '/')
