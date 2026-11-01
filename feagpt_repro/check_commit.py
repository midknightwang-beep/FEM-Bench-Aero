#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_commit.py — 提交前闸（T-D5 / ROADMAP §6 D5）

用途
----
在 `git commit` 之前，机械地确认两件事：

  ① 这次提交**包含了工作区的全部预期改动**；
  ② 没有**夹带**不该入库的文件。

背景（T-C1 事故，2026-10-30）
------------------------------
一次提交只 `add` 了新增文件，**12 个真实改动文件全留在工作区**未暂存 ——
提交里的 `evaluate.py` 仍是旧版，与同一次提交带进来的负控 NC-67 自相矛盾。
发现它的不是任何闸：`git status` 转绿了，门禁跑的也是**工作区**。
⇒ **「工作区绿」和「提交绿」是两件事，之前没有任何东西检查后者。**

用法
----
    python check_commit.py              # 提交前闸（默认）：允许暂存区非空，禁止遗漏
    python check_commit.py --audit      # 日常巡检：只要求「工作区干净（除白名单）」
    python check_commit.py --hook       # 供 pre-commit 调用（= 默认模式 + 短输出）
    python check_commit.py --self-test  # 七向自检：构造场景证明闸会红、且不误报
    python check_commit.py --install-hook   # 把本脚本装成 .git/hooks/pre-commit

判据
----
G0  白名单文件存在、可解析、每条 reason 非空        （缺失判红，不 skip）
G1  未追踪文件必须全部在名单里                      （否则可能漏 add，也可能该入库）
G2  名单里的条目必须处于「未追踪」状态              （已入库 ⇒ 名单腐化，该删这行）
G3  名单里的路径必须真实存在                        （文件没了 ⇒ 名单腐化，该删这行）
G4  除名单外，任何改动都不得停在「未暂存」状态      （Y 位非空 ⇒ 漏 add，T-C1 事故本体）
G5  【仅提交前】暂存区为空时**只报事实、不判红**    （F-8；理由见下面「G5 为什么不再硬红」）
G6  【仅提交前】暂存区不得包含名单内文件            （防误把「不入库」的东西提交）

G5 为什么不再硬红（F-8，2026-11-01 实测）
----------------------------------------
旧版 G5 = 「暂存区不得为空」，本意防空提交。**它把正常操作误判成事故**：改提交信息时
`git commit --amend -F msg` 的暂存区本来就该是空的，T-F7 与 2026-11-01 各撞一次，
每次都只能 `git reset --soft HEAD~1` + 重提来绕。

三条实测证据（`$TEMP/g5probe`，Git 2.x / Windows）：

  ① **hook 内无法识别 amend**：`git commit --amend` 与普通 `git commit` 在 pre-commit
     hook 里的环境变量**逐字节相同**（`env | sort` 逐行 diff 无差异，`GIT_REFLOG_ACTION`
     之类的线索根本不存在），索引树也都等于 HEAD 树 ⇒ 二者在 hook 看来完全同构。
  ② **普通空提交 git 自己就拒绝**：干净工作区下 `git commit -m x` ⇒ `rc=1`
     「nothing to commit, working tree clean」⇒ G5 对这件事是**冗余**的。
  ③ **唯一被 git 放行的是显式 `--allow-empty`**（实测 `rc=0` 直接建成提交）。

⇒ 代价最小且诚实的做法：G5 退回「报事实」。今天仍然成立的那部分是
**`--allow-empty` 不再被拦**，而它是显式参数（不是手滑能撞出来的），且在输出里被点名。

G5 放宽后的边界（R69：放宽必须有边界）
--------------------------------------
- **G4 仍硬红**：真正的事故形态（有改动没 add）没有放宽，G5 的放宽不影响它。
- warn 必须写明 why（含实测依据），不得只印「暂存区为空」让人自己去猜。
- warn **不得被说成「全绿」**：结论行会把 warn 条数单独印出来。
- 若要重新把它变成硬闸，正确做法不是在 pre-commit 里猜，而是移到 **post-commit**
  用 `git reflog -1 --format=%gs` 认 amend（实测能区分：`commit (amend): …` vs
  `commit: …`）—— 但那要新增一个 hook 触发点，且 hook 不入库（R74 的老风险），本轮不做。

边界（R69：放宽必须有边界）
--------------------------
- 白名单是**例外**，故：每条必须带 `reason`；名单内文件**不得**进入任何对外数字；
  名单**只允许 `??`（未追踪）**，一旦文件被 `git add` 进去，G2 立刻红 —— 强制人来清理，
  不允许名单变成「永久豁免」。
- 本闸**只管「提交内容是否完整」，不管「提交内容是否正确」**：
  代码逻辑对不对、数字对不对，仍由 `negative_controls.py` / `check_claims.py` 负责。

退出码
------
0 全过（**含只有 warn 的情况**）／ 1 有判据红 ／ 2 环境错误（不在 git 仓库、白名单缺失/损坏）
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ALLOWLIST_NAME = "commit_allowlist.json"
GIT = shutil.which("git") or "git"


# ---------------------------------------------------------------- git helpers

def _git(args, cwd=None):
    """跑一条 git 命令，返回 (rc, stdout_text)。永不抛异常。"""
    try:
        p = subprocess.run(
            [GIT, "-c", "core.quotepath=false"] + args,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except OSError as e:
        return 127, f"{e}"
    out = p.stdout.decode("utf-8", errors="replace")
    if p.returncode != 0:
        out = out + p.stderr.decode("utf-8", errors="replace")
    return p.returncode, out


def repo_root(start=None):
    rc, out = _git(["rev-parse", "--show-toplevel"], cwd=start)
    if rc != 0:
        return None
    return Path(out.strip())


def status_entries(root):
    """解析 `git status --porcelain -z` 为 [(X, Y, path)]。

    用 -z：路径里含中文/空格时不会被引号转义（core.quotepath 那类坑，
    T-B1 里已踩过一次），分隔符为 NUL。
    重命名条目（R/C）占两个 NUL 段：'XY new\\0old\\0'，旧路径不入结果。
    """
    rc, out = _git(["status", "--porcelain", "-z", "--untracked-files=all"], cwd=root)
    if rc != 0:
        return None
    parts = out.split("\0")
    entries = []
    i = 0
    while i < len(parts):
        seg = parts[i]
        i += 1
        if not seg:
            continue
        if len(seg) < 4:
            continue
        xy, path = seg[:2], seg[3:]
        entries.append((xy[0], xy[1], path))
        if xy[0] in ("R", "C"):
            i += 1  # 丢弃旧路径段
    return entries


# ---------------------------------------------------------------- allowlist

def load_allowlist(path: Path):
    """返回 (list_of_dict, error_or_None)。缺失/损坏都算错误，不 skip。"""
    if not path.is_file():
        return None, f"白名单文件不存在: {path}（禁止 skip —— 缺锚点即红）"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, f"白名单无法解析: {e}"
    items = data.get("allow_untracked")
    if not isinstance(items, list):
        return None, "白名单缺少 `allow_untracked` 数组"
    return items, None


def norm(p: str) -> str:
    """统一成 git 风格的正斜杠相对路径（便于与 `git status` 对齐）。"""
    return p.replace("\\", "/").strip().strip('"').lstrip("/")


# ---------------------------------------------------------------- check logic

def run_checks(root: Path, allow_path: Path, mode: str):
    """返回 (verdicts, rc)。verdicts = [(gid, ok_or_None, msg)]；None 表示 not_run。"""
    v = []
    entries = status_entries(root)
    if entries is None:
        return [("G0", False, "无法读取 git status（不是 git 仓库？）")], 2

    items, err = load_allowlist(allow_path)
    if err:
        return [("G0", False, err)], 2

    allow_norm = {}
    bad_reason = []
    for it in items:
        if not isinstance(it, dict) or "path" not in it:
            bad_reason.append(f"条目格式错: {it!r}")
            continue
        if not str(it.get("reason", "")).strip():
            bad_reason.append(f"缺 reason: {it.get('path')}")
            continue
        allow_norm[norm(str(it["path"]))] = it
    if bad_reason:
        # G0 失败 => 名单本身不可信，G1/G2/G3/G6 全部没有判定依据。
        # 这里必须标 not_run 而不是让它们跟着红：同一根因报两条红，
        # 会把人引向「去修 G1」而不是「去修名单」（NC-67 的教训：两种失败给不同原因）。
        v.append(("G0", False, "白名单不合规: " + "; ".join(bad_reason)))
        for gid in ("G1", "G2", "G3", "G6"):
            v.append((gid, None, "not_run（G0 未通过，名单不可信）"))
        g0_failed = True
    else:
        v.append(("G0", True, f"白名单 {len(allow_norm)} 条，均带 reason"))
        g0_failed = False

    untracked = {p for (x, y, p) in entries if x == "?" and y == "?"}
    tracked_changes = [(x, y, p) for (x, y, p) in entries if not (x == "?" and y == "?")]
    staged = {p for (x, y, p) in entries if x not in ("?", " ")}

    if not g0_failed:
        g1_bad = sorted(p for p in untracked if norm(p) not in allow_norm)
        v.append(("G1", not g1_bad,
                  "无名单外的未追踪文件" if not g1_bad
                  else "名单外的未追踪文件 %d 个: %s" % (len(g1_bad), ", ".join(g1_bad[:6]))))

        g2_bad = sorted(p for p in allow_norm if p in staged or p in {q for (_, _, q) in tracked_changes})
        v.append(("G2", not g2_bad,
                  "名单内条目全部仍为未追踪" if not g2_bad
                  else "名单内但已入库/已暂存 %d 个（名单腐化，应删该行）: %s"
                       % (len(g2_bad), ", ".join(g2_bad[:6]))))

        g3_bad = sorted(p for p in allow_norm if not (root / p).exists())
        v.append(("G3", not g3_bad,
                  "名单内路径全部存在" if not g3_bad
                  else "名单内但磁盘上已不存在 %d 个（名单腐化，应删该行）: %s"
                       % (len(g3_bad), ", ".join(g3_bad[:6]))))

    g4_bad = sorted(p for (x, y, p) in tracked_changes if y not in (" ", "?"))
    g4_label = "工作区无未暂存改动" if mode == "audit" else "无「漏 add」：工作区改动已全部进入暂存区"
    v.append(("G4", not g4_bad,
              g4_label if not g4_bad
              else "有 %d 个改动停在未暂存状态（提交会漏掉它们）: %s"
                   % (len(g4_bad), ", ".join(g4_bad[:6]))))

    if mode == "audit":
        v.append(("G5", None, "not_run（--audit 不要求暂存区非空）"))
        if not g0_failed:
            v.append(("G6", None, "not_run（--audit 不检查暂存内容）"))
    else:
        if staged:
            v.append(("G5", True, f"暂存区 {len(staged)} 个文件"))
        else:
            # ★ F-8（2026-11-01）：这里**不能**判红 —— `git commit --amend` 改提交信息时
            #   暂存区本来就该是空的，而 amend 与「真空提交」在 pre-commit hook 内
            #   完全同构（环境变量逐字节相同、索引树都等于 HEAD 树，实测见文件头）。
            #   普通空提交 git 自己会 rc=1 拒绝，唯一被放行的是显式 `--allow-empty`。
            v.append(("G5", "warn",
                      "暂存区为空（不判红，F-8）—— 若你是在改提交信息（commit --amend）这是正常的；"
                      "若你以为改了文件，去看 G4：有改动没 add 会红。"
                      "本闸唯一不再拦的是显式 --allow-empty（git 放行、hook 内与 amend 不可区分）"))
        if not g0_failed:
            g6_bad = sorted(p for p in staged if norm(p) in allow_norm)
            v.append(("G6", not g6_bad,
                      "暂存区不含名单内文件" if not g6_bad
                      else "名单内文件被暂存了 %d 个（不该入库）: %s" % (len(g6_bad), ", ".join(g6_bad[:6]))))

    hard_fail = any(ok is False for (_, ok, _) in v)
    return v, (1 if hard_fail else 0)


# ---------------------------------------------------------------- self test

def _allow_text(items):
    return json.dumps({"_note": "t", "allow_untracked": items}, ensure_ascii=False, indent=2)


def _mk_repo(tmp: Path):
    tmp.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], cwd=tmp)
    _git(["config", "user.email", "t@t"], cwd=tmp)
    _git(["config", "user.name", "t"], cwd=tmp)
    (tmp / "a.txt").write_text("a\n", encoding="utf-8")
    # 白名单**必须入库**：它自己若停在未追踪状态，就会被 G1 抓（这是设计意图，
    # 不是 bug —— 名单没入库等于换机就丢，闸配置必须随代码走）。
    d = tmp / "feagpt_repro"
    d.mkdir(exist_ok=True)
    (d / ALLOWLIST_NAME).write_text(_allow_text([]), encoding="utf-8")
    _git(["add", "a.txt", f"feagpt_repro/{ALLOWLIST_NAME}"], cwd=tmp)
    _git(["commit", "-q", "-m", "init"], cwd=tmp)
    return tmp


def _write_allow(repo: Path, items):
    p = repo / "feagpt_repro" / ALLOWLIST_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_allow_text(items), encoding="utf-8")
    # 已追踪文件的修改必须暂存，否则本该绿的正向场景会被 G4 判红（那是另一条判据的事）
    _git(["add", f"feagpt_repro/{ALLOWLIST_NAME}"], cwd=repo)
    return p


def self_test() -> int:
    probes = []

    def probe(name, setup, mode, expect_ids_red, expect_ids_green=(),
              expect_warn=(), expect_msg=None, forbid_msg=None):
        with tempfile.TemporaryDirectory() as td:
            repo = _mk_repo(Path(td) / "r")
            allow = setup(repo)
            v, rc = run_checks(repo, allow, mode)
            red = {g for (g, ok, _) in v if ok is False}
            warn = {g for (g, ok, _) in v if ok == "warn"}
            msgs = [m for (_, _, m) in v]
            ok = (expect_ids_red <= red) and (not (set(expect_ids_green) & red)) \
                and (set(expect_warn) <= warn)
            detail = "红=" + (",".join(sorted(red)) or "无")
            if warn:
                detail += " warn=" + ",".join(sorted(warn))
            if expect_ids_red and not (expect_ids_red <= red):
                detail += " 缺红=" + ",".join(sorted(expect_ids_red - red))
            if set(expect_ids_green) & red:
                detail += " 误红=" + ",".join(sorted(set(expect_ids_green) & red))
            if not (set(expect_warn) <= warn):
                detail += " 缺warn=" + ",".join(sorted(set(expect_warn) - warn))
            if expect_msg is not None:
                hit = any(expect_msg in m for m in msgs)
                ok &= hit
                if not hit:
                    detail += " 缺文案:" + expect_msg
            if forbid_msg is not None:
                bad = [m for m in msgs if forbid_msg in m]
                ok &= not bad
                if bad:
                    detail += " 不该出现的文案:" + forbid_msg
            if rc != (0 if not red else 1):
                ok = False
                detail += f" rc不符({rc})"
            probes.append((name, ok, detail))

    def s_clean(repo):
        """正向：干净暂存 + 名单内文件未追踪 + 一条已暂存改动 => 全绿"""
        allow = _write_allow(repo, [{"path": "keep.md", "reason": "测试用不入库"}])
        (repo / "keep.md").write_text("x", encoding="utf-8")
        (repo / "a.txt").write_text("a2\n", encoding="utf-8")
        _git(["add", "a.txt"], cwd=repo)
        return allow

    def s_forgot_add(repo):
        """G4：改了已追踪文件却没 add（T-C1 事故本体）"""
        allow = _write_allow(repo, [])
        (repo / "a.txt").write_text("a3\n", encoding="utf-8")
        (repo / "b.txt").write_text("b\n", encoding="utf-8")
        _git(["add", "b.txt"], cwd=repo)
        return allow

    def s_stray_untracked(repo):
        """G1：有个名单外的未追踪文件"""
        allow = _write_allow(repo, [])
        (repo / "a.txt").write_text("a4\n", encoding="utf-8")
        (repo / "stray.txt").write_text("s\n", encoding="utf-8")
        _git(["add", "a.txt"], cwd=repo)
        return allow

    def s_staged_allowlisted(repo):
        """G6：名单内的文件被 add 了"""
        allow = _write_allow(repo, [{"path": "keep.md", "reason": "测试用不入库"}])
        (repo / "keep.md").write_text("x", encoding="utf-8")
        (repo / "a.txt").write_text("a5\n", encoding="utf-8")
        _git(["add", "a.txt", "keep.md"], cwd=repo)
        return allow

    def s_allowlist_rotted_tracked(repo):
        """G2：名单内文件其实已入库"""
        allow = _write_allow(repo, [{"path": "a.txt", "reason": "已入库却还在名单"}])
        (repo / "a.txt").write_text("a6\n", encoding="utf-8")
        _git(["add", "a.txt"], cwd=repo)
        return allow

    def s_allowlist_rotted_gone(repo):
        """G3：名单内文件磁盘上没了"""
        allow = _write_allow(repo, [{"path": "ghost.md", "reason": "文件已删"}])
        (repo / "a.txt").write_text("a7\n", encoding="utf-8")
        _git(["add", "a.txt"], cwd=repo)
        return allow

    def s_no_reason(repo):
        """G0：条目缺 reason"""
        allow = _write_allow(repo, [{"path": "keep.md", "reason": "  "}])
        (repo / "keep.md").write_text("x", encoding="utf-8")
        (repo / "a.txt").write_text("a8\n", encoding="utf-8")
        _git(["add", "a.txt"], cwd=repo)
        return allow

    def s_empty_staged(repo):
        """G5：没有任何东西被暂存"""
        allow = _write_allow(repo, [])
        return allow

    probe("正向：干净暂存 + 名单内未追踪", s_clean, "pre", set(),
          {"G0", "G1", "G2", "G3", "G4", "G5", "G6"},
          # G5 走 ok 分支：印真实个数、且**不许**出现 warn 的措辞。
          # 不写死个数（=2：a.txt + 被 _write_allow 暂存的白名单），否则改夹具就假红。
          expect_msg="个文件", forbid_msg="不判红")
    probe("G4 改了没 add（T-C1 事故）", s_forgot_add, "pre", {"G4"}, {"G1", "G2", "G3", "G5", "G6"})
    probe("G1 名单外未追踪", s_stray_untracked, "pre", {"G1"}, {"G4"})
    probe("G6 名单内文件被暂存", s_staged_allowlisted, "pre", {"G6"}, {"G1", "G4"})
    probe("G2 名单腐化（已入库）", s_allowlist_rotted_tracked, "pre", {"G2"}, {"G1", "G3"})
    probe("G3 名单腐化（文件没了）", s_allowlist_rotted_gone, "pre", {"G3"}, {"G1", "G2"})
    probe("G0 条目缺 reason", s_no_reason, "pre", {"G0"}, {"G1"})
    # ★ F-8：旧版这里断言「G5 红」。实测 amend 与真空提交在 hook 内不可区分 ⇒ 改成
    #   「一条都不许红 + G5 必须是 warn + 文案必须点出为什么（含『不可区分』与 --allow-empty）」。
    probe("G5 空暂存区 ⇒ warn 不红（F-8）", s_empty_staged, "pre", set(),
          {"G0", "G1", "G2", "G3", "G4", "G5", "G6"},
          expect_warn={"G5"}, expect_msg="不可区分")
    probe("--audit 下 G5/G6 不判", s_stray_untracked, "audit", {"G1"}, {"G5", "G6"})

    print("check_commit.py 自检（%d 向）" % len(probes))
    allok = True
    for name, ok, detail in probes:
        allok &= ok
        print("  [%s] %-28s %s" % ("ok " if ok else "BAD!", name, detail))
    print("\n自检: %d/%d %s" % (sum(1 for _, o, _ in probes if o), len(probes), "ok" if allok else "FAILED"))
    return 0 if allok else 1


# ---------------------------------------------------------------- hook

HOOK_BODY = """#!/bin/sh
# 由 feagpt_repro/check_commit.py --install-hook 生成（T-D5）
# 换机 / 重装 python 后请重跑一次 --install-hook
"{py}" "{script}" --hook
rc=$?
if [ $rc -ne 0 ]; then
  echo ""
  echo "提交被 check_commit.py 拦下（rc=$rc）。按上面的提示修正，或"
  echo "  python feagpt_repro/check_commit.py  # 看完整判据"
  echo "确实要绕过：git commit --no-verify（会留下痕迹，不要常用）"
  exit 1
fi
exit 0
"""


def install_hook(root: Path) -> int:
    hooks = root / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    dst = hooks / "pre-commit"
    script = Path(__file__).resolve()
    py = sys.executable or "python"
    body = HOOK_BODY.replace("{py}", py).replace("{script}", str(script))
    if dst.exists():
        old = dst.read_text(encoding="utf-8", errors="replace")
        if "check_commit.py" not in old:
            bak = dst.with_suffix(".bak.pre-d5")
            bak.write_text(old, encoding="utf-8")
            print(f"已备份原有 hook -> {bak}")
    dst.write_bytes(body.replace("\n", "\n").encode("utf-8"))
    try:
        os.chmod(dst, 0o755)
    except OSError:
        pass
    print(f"已安装 pre-commit hook -> {dst}")
    print(f"  解释器: {py}")
    print(f"  脚本  : {script}")
    return 0


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="提交前闸：暂存区必须等于工作区全部非白名单改动")
    ap.add_argument("--audit", action="store_true", help="日常巡检：只要求工作区干净（除白名单）")
    ap.add_argument("--hook", action="store_true", help="供 pre-commit 调用")
    ap.add_argument("--self-test", action="store_true", help="构造场景自检（七向+）")
    ap.add_argument("--install-hook", action="store_true", help="安装为 .git/hooks/pre-commit")
    ap.add_argument("--allowlist", default=None, help="白名单路径（默认 feagpt_repro/commit_allowlist.json）")
    ap.add_argument("--root", default=None, help="仓库根（默认自动探测）")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    root = Path(args.root).resolve() if args.root else repo_root()
    if root is None:
        print("[FATAL] 不在 git 仓库内（或 git 不可用）")
        return 2

    if args.install_hook:
        return install_hook(root)

    allow_path = Path(args.allowlist).resolve() if args.allowlist else \
        (Path(__file__).resolve().parent / ALLOWLIST_NAME)
    if not allow_path.is_file():
        alt = root / "feagpt_repro" / ALLOWLIST_NAME
        if alt.is_file():
            allow_path = alt

    mode = "audit" if args.audit else "pre"
    verdicts, rc = run_checks(root, allow_path, mode)

    print(f"check_commit.py  [{mode}]  仓库={root}")
    n_warn = 0
    for gid, ok, msg in verdicts:
        if ok is True:
            tag = "ok  "
        elif ok is False:
            tag = "BAD!"
        elif ok == "warn":
            tag = "warn"
            n_warn += 1
        else:
            tag = "skip"
        print(f"  [{tag}] {gid}  {msg}")
    if rc == 0:
        if n_warn:
            # R69 边界③：有 warn 时**不得**说成「全绿」——warn 不是通过，是「这件事本闸不管了」
            print(f"\n结论：无判据红 —— 但有 {n_warn} 条 warn（见上），"
                  f"不等于「全绿」，只是本闸对这些情形不再判定")
        else:
            print("\n结论：通过 —— 提交内容完整，未夹带白名单内文件")
    else:
        print("\n结论：不通过 —— 修正后再提交（不要用 --no-verify 绕过）")
    return rc


if __name__ == "__main__":
    sys.exit(main())
