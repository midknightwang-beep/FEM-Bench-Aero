#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""hook_guard.py — 哨兵的哨兵：`pre-commit` hook 还活着吗（T-D5b / R74）

要解决的问题
------------
T-D5 的 `check_commit.py` 靠 `.git/hooks/pre-commit` 触发，而 **hook 不入库**
（`.git/` 不被追踪）。新 clone / 换机 / 重建仓库后，这道闸**静默消失**：

    它不运行 ⇒ 所以不会有任何东西报错 ⇒ 和「没装这道闸」完全等价。

这就是 R58「无工具读的 = 无闸」发生在**闸的触发器**上的形态。本脚本是那个
「不依赖触发器本身」的检查入口。

判据（每条都须能在构造场景里变红，见 --self-test）
--------------------------------------------------
H0  适用性：必须在 git 工作副本内         （否则无对象 ⇒ skip，不判红）
H1  生效 hooks 目录下 `pre-commit` 存在
H2  该文件内容里出现 `check_commit.py`    （不是别的 hook 文件）
H3  内容里那条脚本路径可解析、且等于**当前**脚本
H4  可执行位（**仅 POSIX 且 `core.filemode != false` 时判**；其余平台 skip 并说明）

为什么不「`core.hooksPath` 非空即红」
------------------------------------
实测 `git rev-parse --git-path hooks` **会跟随 `core.hooksPath`**：设成 `.husky`
它就返回 `.husky`。所以判据看「**实际生效的**目录里有没有我们的 hook」，
而不是「配置有没有被动过」—— 把 hook 装进 `.husky` 并纳入版本控制是**更**好的
做法，一刀切判红会误伤（R69：能判的不变量优于需要维护的名单；R73：查实体不是查容器）。

边界（R69）
-----------
- 本判据只保证「哨兵还在、且指向当前脚本」，**不保证哨兵判得对**（那是
  `check_commit.py --self-test` 的事）。
- 不通过「检测 CI 环境变量」之类的方式自动放行；跳过必须由调用方显式声明
  （`check_claims.py --skip-hook-guard`），且须在当次报告里写明原因。
- 本判据不是成绩，**不得进入任何对外数字**。

用法
----
    python hook_guard.py                # 查当前仓库
    python hook_guard.py --self-test    # 八向自检：每向都断言「红的是哪一条」
    python hook_guard.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GIT = shutil.which("git") or "git"
HOOK_NAME = "pre-commit"
GUARD_SCRIPT = "check_commit.py"


# ---------------------------------------------------------------- git helpers

def _git(args, cwd=None):
    """跑一条 git 命令，返回 (rc, stdout+stderr)。永不抛异常。"""
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
        out += p.stderr.decode("utf-8", errors="replace")
    return p.returncode, out


def _hooks_dir(root: Path):
    """返回 (生效 hooks 目录 或 None, core.hooksPath 原值 或 None, 错误 或 None)。

    ★ 用 `--git-path hooks` 而不是写死 `.git/hooks`：它会跟随 `core.hooksPath`
      （实测：设 `.husky` ⇒ 返回 `.husky`；设绝对路径 ⇒ 返回绝对路径）。
      这才是 git 真正会去读的目录。
    """
    rc, out = _git(["rev-parse", "--git-path", "hooks"], root)
    if rc != 0:
        return None, None, f"git rev-parse --git-path hooks 失败: {out.strip()[:160]}"
    raw = out.strip()
    p = Path(raw)
    if not p.is_absolute():
        p = root / raw
    rc2, hp = _git(["config", "--get", "core.hooksPath"], root)
    hp_val = hp.strip() if rc2 == 0 and hp.strip() else None
    return p, hp_val, None


def _parse_script_path(hook_text: str):
    """从 hook 内容里取出调用本闸的那条脚本路径；取不到返回 None。

    生成器（`check_commit.py --install-hook`）写的是：
        "{py}" "{script}" --hook
    Windows 路径含反斜杠与冒号，故只按「引号内、以 check_commit.py 结尾、后接 --hook」匹配。
    """
    m = re.search(r'"([^"]*' + re.escape(GUARD_SCRIPT) + r')"\s+--hook', hook_text)
    return m.group(1) if m else None


# ---------------------------------------------------------------- 判据

def inspect(root, expect_script=None):
    """返回 dict：{applicable, reason, hook_dir, hooks_path, expect, checks:[{id,ok,msg}]}

    ok 取值：True 绿 / False 红 / None not_run（无对象或上游已红）。
    """
    root = Path(root).resolve()
    expect = Path(expect_script).resolve() if expect_script \
        else (Path(__file__).resolve().parent / GUARD_SCRIPT)
    res = {"root": str(root), "applicable": False, "reason": "", "hook_dir": None,
           "hooks_path": None, "expect": str(expect), "checks": []}

    def add(cid, ok, msg):
        res["checks"].append({"id": cid, "ok": ok, "msg": msg})

    # ---- H0 适用性 -------------------------------------------------------
    rc, out = _git(["rev-parse", "--is-inside-work-tree"], root)
    if rc != 0 or out.strip() != "true":
        res["reason"] = ("不在 git 工作副本内（解压包 / 只拿数据 / bare repo）"
                         "⇒ 本判据无对象，不是失败")
        return res
    res["applicable"] = True

    hdir, hp_val, err = _hooks_dir(root)
    if err:
        add("H0", False, err)          # 拿不到 hooks 目录 = 判据无锚点 ⇒ 红，不 skip（R58）
        return res
    res["hook_dir"], res["hooks_path"] = str(hdir), hp_val

    hpath = hdir / HOOK_NAME
    hp_note = f"（core.hooksPath={hp_val}）" if hp_val else "（默认 .git/hooks）"

    # ---- H1 hook 文件存在 ------------------------------------------------
    if not hpath.is_file():
        add("H1", False,
            f"生效 hooks 目录 {hpath} 下没有 {HOOK_NAME}{hp_note} ⇒ "
            f"提交闸不会运行；跑 `python feagpt_repro/check_commit.py --install-hook`")
        for cid in ("H2", "H3", "H4"):
            add(cid, None, "not_run（H1 未通过：没有 hook 文件可读）")
        return res
    add("H1", True, f"{hpath} 存在{hp_note}")

    # ---- H2 内容是本闸 ---------------------------------------------------
    try:
        text = hpath.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        add("H2", False, f"hook 文件无法读取: {e}")
        for cid in ("H3", "H4"):
            add(cid, None, "not_run（H2 未通过：内容不可读）")
        return res
    if GUARD_SCRIPT not in text:
        add("H2", False,
            f"hook 内容里没有 `{GUARD_SCRIPT}` ⇒ 这是别的钩子（或被清空了），"
            f"本闸不生效；先备份再 `--install-hook`")
        for cid in ("H3", "H4"):
            add(cid, None, "not_run（H2 未通过：不是本闸的 hook）")
        return res
    add("H2", True, f"内容含 `{GUARD_SCRIPT}`")

    # ---- H3 脚本路径有效且指向当前脚本 ----------------------------------
    raw = _parse_script_path(text)
    if not raw:
        add("H3", False,
            f"hook 里有 `{GUARD_SCRIPT}` 字样但解析不出 `\"<路径>\" --hook` 调用行 ⇒ "
            f"格式已变（旧版生成器？）；重跑 --install-hook")
    else:
        got = Path(raw)
        if not got.is_absolute():
            got = root / raw
        got = got.resolve()
        if not got.is_file():
            add("H3", False,
                f"hook 指向的脚本不存在: {got} ⇒ 提交时会 rc=127 被拦（不静默，但闸已坏）；"
                f"重跑 --install-hook")
        elif got != expect:
            add("H3", False,
                f"hook 指向 {got}，但当前脚本是 {expect} ⇒ "
                f"有另一个副本在跑（脚本搬家/多 clone）；重跑 --install-hook")
        else:
            add("H3", True, f"指向当前脚本 {got}")

    # ---- H4 可执行位（平台相关，隔离并双报）-----------------------------
    rc_fm, fm = _git(["config", "--get", "core.filemode"], root)
    filemode = (fm.strip().lower() != "false") if rc_fm == 0 and fm.strip() else True
    if os.name != "posix":
        add("H4", None,
            f"not_run（平台 {os.name} 非 POSIX：git 在该平台不追踪可执行位，"
            f"判了只会假红 —— 本向在此平台**未被验证**）")
    elif not filemode:
        add("H4", None,
            "not_run（core.filemode=false ⇒ 本仓库不追踪可执行位，判了只会假红）")
    elif os.access(str(hpath), os.X_OK):
        add("H4", True, "hook 可执行")
    else:
        add("H4", False, f"hook 没有可执行位 ⇒ git 会静默跳过它；chmod +x {hpath}")

    return res


def ok_of(res):
    """(是否通过, 红条 id 列表)。skip 不算红，但也不等于「验证过」。"""
    red = [c["id"] for c in res.get("checks", []) if c["ok"] is False]
    return (not red), red


# ---------------------------------------------------------------- 自检

HOOK_TMPL = '#!/bin/sh\n"{py}" "{script}" --hook\n'
ALT_HOOK = '#!/bin/sh\n# husky\nnpx husky run pre-commit\n'


def _mk_repo(tmp: Path):
    tmp.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], cwd=tmp)
    _git(["config", "user.email", "t@t"], cwd=tmp)
    _git(["config", "user.name", "t"], cwd=tmp)
    return tmp


def _write_hook(repo: Path, text: str, hdir: Path = None):
    d = hdir if hdir is not None else (repo / ".git" / "hooks")
    d.mkdir(parents=True, exist_ok=True)
    p = d / HOOK_NAME
    p.write_text(text, encoding="utf-8")
    try:
        os.chmod(p, 0o755)
    except OSError:
        pass
    return p


def self_test() -> int:
    probes = []

    def probe(name, setup, expect_red, expect_green=(), msg_has=(), is_git=True):
        """expect_red 是**精确**集合：多红也算错 —— 只断言「红了」会放过『红的原因不对』。"""
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "r"
            # ★ 首版忘了这一步：8 向全部 applicable=False、全部「红=无」⇒ 7 向假通过。
            #   自检的详细行把它抓出来了 —— 判据没跑起来与判据通过，外观完全一样。
            if is_git:
                _mk_repo(repo)
            else:
                repo.mkdir(parents=True, exist_ok=True)
            script = setup(repo)
            res = inspect(repo, expect_script=script)
            red = {c["id"] for c in res["checks"] if c["ok"] is False}
            msg = " | ".join(c["msg"] for c in res["checks"])
            ok = (red == set(expect_red)) and not (set(expect_green) & red)
            for kw in msg_has:
                if kw not in msg:
                    ok = False
            detail = "红=" + (",".join(sorted(red)) or "无")
            if red != set(expect_red):
                detail += f" 期望={sorted(expect_red) or '无'}"
            miss = [k for k in msg_has if k not in msg]
            if miss:
                detail += " 缺关键字=" + ",".join(miss)
            if res["applicable"] is False:
                detail += " [not_applicable]"
            probes.append((name, ok, detail))

    def s_ok(repo):
        script = repo / "fake" / GUARD_SCRIPT
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# fake\n", encoding="utf-8")
        _write_hook(repo, HOOK_TMPL.replace("{py}", "python").replace("{script}", str(script)))
        return script

    def s_missing(repo):
        script = repo / "fake" / GUARD_SCRIPT
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# fake\n", encoding="utf-8")
        return script

    def s_other_hook(repo):
        script = repo / "fake" / GUARD_SCRIPT
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# fake\n", encoding="utf-8")
        _write_hook(repo, ALT_HOOK)
        return script

    def s_zombie(repo):
        script = repo / "fake" / GUARD_SCRIPT
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# fake\n", encoding="utf-8")
        _write_hook(repo, HOOK_TMPL.replace("{py}", "python")
                    .replace("{script}", str(repo / "gone" / GUARD_SCRIPT)))
        return script

    def s_wrong_script(repo):
        """H3：指向另一个存在但不是当前脚本的副本（多 clone / 脚本搬家）"""
        script = repo / "fake" / GUARD_SCRIPT
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# fake\n", encoding="utf-8")
        other = repo / "other" / GUARD_SCRIPT
        other.parent.mkdir(parents=True, exist_ok=True)
        other.write_text("# stale copy\n", encoding="utf-8")
        _write_hook(repo, HOOK_TMPL.replace("{py}", "python").replace("{script}", str(other)))
        return script

    def s_hookspath_empty(repo):
        """H1：hooksPath 改道到一个空目录（我们装的那份不会被读）"""
        script = repo / "fake" / GUARD_SCRIPT
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# fake\n", encoding="utf-8")
        _git(["config", "core.hooksPath", ".husky"], cwd=repo)
        (repo / ".husky").mkdir(exist_ok=True)
        return script

    def s_hookspath_installed(repo):
        """正向②：hooksPath 改道但那里**装了**我们的 hook ⇒ 合法配置，不得误红"""
        script = repo / "fake" / GUARD_SCRIPT
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# fake\n", encoding="utf-8")
        _git(["config", "core.hooksPath", ".husky"], cwd=repo)
        _write_hook(repo, HOOK_TMPL.replace("{py}", "python").replace("{script}", str(script)),
                    hdir=repo / ".husky")
        return script

    def s_not_git(repo):
        repo.mkdir(parents=True, exist_ok=True)
        return repo / "fake" / GUARD_SCRIPT

    probe("正向①默认路径装了", s_ok, set(), {"H1", "H2", "H3"})
    probe("H1 hook 缺失（新 clone）", s_missing, {"H1"}, {"H2", "H3", "H4"}, msg_has=["--install-hook"])
    probe("H2 是别的钩子", s_other_hook, {"H2"}, {"H1", "H3", "H4"})
    probe("H3 指向僵尸脚本", s_zombie, {"H3"}, {"H1", "H2"}, msg_has=["不存在"])
    probe("H3 指向另一个副本", s_wrong_script, {"H3"}, {"H1", "H2"}, msg_has=["当前脚本是"])
    probe("H1 hooksPath 改道到空目录", s_hookspath_empty, {"H1"}, {"H2", "H3"}, msg_has=["core.hooksPath"])
    probe("正向②hooksPath 改道且已装", s_hookspath_installed, set(), {"H1", "H2", "H3"})
    probe("H0 非 git 目录 ⇒ 无对象", s_not_git, set(), {"H1", "H2", "H3"}, is_git=False)

    print("hook_guard.py 自检（%d 向）" % len(probes))
    allok = True
    for name, ok, detail in probes:
        allok &= ok
        print("  [%s] %-30s %s" % ("ok " if ok else "BAD!", name, detail))

    # 平台相关性必须显式报出来，不得假装验证过（R69 / S-53 隔离+双报）
    with tempfile.TemporaryDirectory() as td:
        repo = _mk_repo(Path(td) / "r")
        script = repo / "fake" / GUARD_SCRIPT
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# fake\n", encoding="utf-8")
        _write_hook(repo, HOOK_TMPL.replace("{py}", "python").replace("{script}", str(script)))
        res = inspect(repo, expect_script=script)
        h4 = [c for c in res["checks"] if c["id"] == "H4"][0]
        print("\n  H4 在本机（os.name=%s）: ok=%r  %s" % (os.name, h4["ok"], h4["msg"]))
        if os.name != "posix" and h4["ok"] is not None:
            allok = False
            print("  [BAD!] 非 POSIX 平台上 H4 必须 not_run，实为 %r" % (h4["ok"],))

    print("\n自检: %d/%d %s" % (sum(1 for _, o, _ in probes if o), len(probes),
                               "ok" if allok else "FAILED"))
    return 0 if allok else 1


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="pre-commit hook 存活判据（R74）")
    ap.add_argument("--root", default=None, help="仓库根（默认自动探测）")
    ap.add_argument("--expect-script", default=None, help="期望 hook 指向的脚本（默认同目录 check_commit.py）")
    ap.add_argument("--self-test", action="store_true", help="八向自检")
    ap.add_argument("--json", default=None, help="把结果写成 JSON")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    root = Path(args.root).resolve() if args.root else None
    if root is None:
        rc, out = _git(["rev-parse", "--show-toplevel"])
        if rc != 0:
            print("[skip] 不在 git 工作副本内 ⇒ 本判据无对象（不是失败）")
            return 0
        root = Path(out.strip())

    res = inspect(root, expect_script=args.expect_script)
    ok, red = ok_of(res)

    if not res["applicable"]:
        print(f"[skip] {res['reason']}")
    else:
        print(f"hook_guard.py  仓库={res['root']}")
        print(f"  生效 hooks 目录 = {res['hook_dir']}"
              + (f"（core.hooksPath={res['hooks_path']}）" if res["hooks_path"] else ""))
        for c in res["checks"]:
            tag = "ok  " if c["ok"] else ("skip" if c["ok"] is None else "BAD!")
            print(f"  [{tag}] {c['id']}  {c['msg']}")
        print("\n结论：" + ("通过 —— 提交闸已装且指向当前脚本" if ok
                          else "不通过 —— 提交闸当前**不会运行**（见上面 BAD! 行）"))

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"ok": ok, "red": red, **res}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report -> {args.json}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
