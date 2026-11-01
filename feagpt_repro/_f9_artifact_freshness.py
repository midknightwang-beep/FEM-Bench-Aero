#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F-9 产物新鲜度闸：两个分发产物现在还「代表不代表当前状态」？

为什么需要它（F-9 的两次现场，都是「过期无声」）：
  · 2026-11-01 重建产物时，旧公开快照的 `--check` **只有一条红**，文案是
    「P4b 脱敏不可逆」—— 读起来像数据/脱敏问题，实际原因是快照落后。
    `_d4_public_set.check()` 通篇不看 `manifest.source_head`，**没有任何一条能报「该重建了」**。
  · bundle 侧 C9 判得准，但要先 `clone` 整个包（分钟级）。而真正需要问「新不新」的时刻
    是每次收口、每次提交前 —— 那时没人愿意等一次 clone。

所以这里只做一件事：**便宜地比 HEAD**。不 clone、不 emit、不写任何文件。
  · 公开快照：`public_manifest.json.source_head` ↔ 仓库 HEAD
  · 离线 bundle：包内 `refs/heads/main` ↔ 仓库 HEAD

谓词（与 C9 **同一条**，不自立第二套 —— T-D3「规则只有一处」）：
  允许落后，但**落后区间里改过的文件必须全部是 metadata**（直接复用
  `_d6_bundle_verify.is_metadata`，连规则都不复制）；
  只要有一个 `.py` / `.sh` / 配置 / 数据落在落后区间里 ⇒ 红。
  ★ 比较用 `git diff base head` 而不是「区间内每个提交改过的文件并集」：
    前者答的是「当前内容还一样吗」，那才是「产物代不代表当前状态」的真问题；
    中途改过又改回来的文件，产物并没有失真。

判据
----
A0  manifest 可读、含 40 位 `source_head`                  （缺失判红，不 skip：无基准 = 无闸）
A1  快照与 manifest 同源                                    （成员数 == `n_keep`；
                                                             **快照内那份 manifest 与仓库里那份逐字节一致**）
A2  快照新鲜度                                              （`source_head`..HEAD 的落后区间必须是 metadata）
A3  bundle 存在、唯一、且文件名里的 sha == 包内 main        （缺失 / 多候选 / 名实不符）
A4  bundle 新鲜度                                           （包内 main..HEAD 的落后区间必须是 metadata）

★ 自指是设计的一部分，不是 bug：`public_manifest.json` 自己也进公开集，而它记录
  `source_head` ⇒ **记录它的那个提交**必然让快照落后 ≥1。落到谓词里就是恒为「黄」：
  「允许落后，但只许落后在记录它自己的那一笔上」。若为了消掉这个黄而把 manifest 排除出
  公开集，读快照的人就再也看不到它是从哪个提交来的 —— 那才是真丢信息。

用法（全部命令用 venv 的 python）
  python _f9_artifact_freshness.py                        # 校验当前仓库的两个产物
  python _f9_artifact_freshness.py --bundle <path>        # 指定包
  python _f9_artifact_freshness.py --snap <dir>           # 指定快照目录
  python _f9_artifact_freshness.py --allow-missing-bundle  # 显式声明本机没有包（豁免，不计入通过）
  python _f9_artifact_freshness.py --json out.json        # 证据落盘
  python _f9_artifact_freshness.py --self-test            # 七向构造性验证

退出码：0 = 全过（允许 warn）；2 = 有判据红；1 = 环境/参数错误。
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HANDOFF = os.path.join(ROOT, '_handoff')

# 规则只有一处：manifest 路径取自 D4 生成器，metadata 谓词取自 D6 的 C9。
# 复制一份的代价是「改了规则表却漏改第二处」—— T-D3 已经付过一次学费。
try:
    from _d4_public_set import MANIFEST as PUBLIC_MANIFEST, _walk
    from _d6_bundle_verify import is_metadata, _refs_of
except Exception as e:                                    # pragma: no cover
    print('环境错误：无法导入兄弟模块（本脚本必须与 _d4/_d6 同目录）：%s' % e)
    sys.exit(1)

# manifest 在公开集里的相对路径是**固定的**（由 D4 的白名单决定），
# 不能按「相对当前仓库」现算 —— 自检在临时仓库里跑时，relpath 会算成 `../../..`。
MANIFEST_REL = os.path.relpath(PUBLIC_MANIFEST, ROOT).replace(os.sep, '/')
BUNDLE_GLOB = 'FEM-Bench-Aero_*.bundle'


def _git(args, cwd=None):
    """始终带 core.quotepath=false —— 中文路径被转义会让两侧字符集不同（T-F2 连犯三次）。"""
    cmd = ['git', '-c', 'core.quotepath=false'] + list(args)
    p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, timeout=300)
    return p.returncode, p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace')


def _behind(head, base, repo, is_doc):
    """产物基准 base 相对 head 落后多远、落后区间改了什么。

    返回 (status, n, files, why)：
      status = 'sync' | 'meta' | 'code' | 'unknown'
      'unknown' 一律当红：**算不出来不能当成「没问题」**（R58：无工具读的 = 无闸）。
    """
    if not base:
        return 'unknown', -1, [], '基准提交为空'
    rc, _, err = _git(['cat-file', '-e', base + '^{commit}'], repo)
    if rc != 0:
        return 'unknown', -1, [], ('提交 %s 在本仓库不存在（产物不是从这个仓库打的，'
                                   '或历史已被改写）' % base[:8])
    rc, _, err = _git(['merge-base', '--is-ancestor', base, head], repo)
    if rc == 1:
        return 'unknown', -1, [], '提交 %s 不是 HEAD 的祖先（产物来源不在当前历史线上）' % base[:8]
    if rc != 0:
        return 'unknown', -1, [], 'merge-base 失败：%s' % err.strip()[:120]
    rc, out, err = _git(['rev-list', '--count', '%s..%s' % (base, head)], repo)
    if rc != 0:
        return 'unknown', -1, [], 'rev-list --count 失败：%s' % err.strip()[:120]
    n = int(out.strip() or 0)
    if n == 0:
        return 'sync', 0, [], ''
    rc, out, err = _git(['diff', '--name-only', base, head], repo)
    if rc != 0:
        return 'unknown', -1, [], 'git diff 失败：%s' % err.strip()[:120]
    names = [x for x in out.splitlines() if x.strip()]
    outside = sorted(x for x in set(names) if not is_doc(x))
    if outside:
        return 'code', n, names, '落后 %d 个提交，其中 %d 个非 metadata 文件被改过（%s）' % (
            n, len(outside), ', '.join(outside[:3]))
    return 'meta', n, names, '落后 %d 个提交，但改动全为 metadata（%d 个文件）' % (n, len(names))


def find_bundle():
    """`_handoff/` 下非 `_stale_` 的包。返回 (path 或 None, 候选列表)。

    ★ 多个候选**不选「最新」**：没有可靠的新旧判据（mtime 会被复制/解压改掉；文件名里的
      sha 只能证明「它是那个提交的包」，排不了序）。多份并存时人必须自己清掉一份 ——
      否则「哪份是要发布的」这个决定被脚本悄悄替人做了（T-D6 的老账）。
    """
    if not os.path.isdir(HANDOFF):
        return None, []
    cands = sorted(p for p in glob.glob(os.path.join(HANDOFF, BUNDLE_GLOB))
                   if not os.path.basename(p).startswith('_stale_'))
    return (cands[0] if len(cands) == 1 else None), cands


def judge(root=None, head=None, manifest_path=None, snap=None, bundle_path=None,
          is_doc=None, bundle_required=True, quiet=False):
    """返回 (fails, warns, skips, info)。fails/warns/skips = [(id, 说明)]。"""
    root = root or ROOT
    is_doc = is_doc or is_metadata
    say = (lambda s: None) if quiet else print
    fails, warns, skips = [], [], []
    info = {}

    # 路径一律先转绝对：`_refs_of()` 内部以**仓库根**为 cwd 调 git，命令行走的是
    # **当前目录** —— 传相对路径就会被拼成 `ROOT/../_handoff/...` 而打不开
    # （实测踩到：`--bundle ../_handoff/x.bundle` 报 `could not open`）。
    if manifest_path:
        manifest_path = os.path.abspath(manifest_path)
    if snap:
        snap = os.path.abspath(snap)
    if bundle_path:
        bundle_path = os.path.abspath(bundle_path)

    if head is None:
        rc, out, _ = _git(['rev-parse', 'HEAD'], cwd=root)
        if rc != 0:
            return [('A0', '取不到仓库 HEAD（不在 git 仓库里？）')], warns, skips, info
        head = out.strip()
    info['head'] = head

    # ---- A0 manifest 可读 + source_head 成形 ----
    mpath = manifest_path or PUBLIC_MANIFEST
    info['manifest'] = mpath
    m = None
    try:
        with open(mpath, encoding='utf-8') as f:
            m = json.load(f)
    except Exception as e:
        fails.append(('A0', 'manifest 读不出来（%s）：%s' % (mpath, e)))
    if m is not None:
        src = str(m.get('source_head') or '')
        if len(src) != 40 or any(c not in '0123456789abcdef' for c in src.lower()):
            fails.append(('A0', 'manifest 的 source_head 不是 40 位 sha（实为 %r）⇒ 没有基准'
                          % src[:16]))
            m = None
        else:
            info['source_head'] = src

    # ---- A1 快照与 manifest 同源 ----
    sd = snap or os.path.join(root, '_handoff', 'public_snapshot')
    info['snapshot'] = sd
    if m is None:
        skips.append(('A1', 'A0 已红（没有可信的 manifest 基准），本轮不判'))
    elif not os.path.isdir(sd):
        fails.append(('A1', '快照目录不存在：%s' % sd))
    else:
        have = _walk(sd)
        n_keep = int(m.get('n_keep') or -1)
        info['n_keep'] = n_keep
        info['n_snap'] = len(have)
        probs = []
        # ① 成员数对账。P6 比的是「成员集合 vs **现算** manifest」，这里比的是
        #    「成员数 vs **入库那份** manifest」—— 入库那份才是快照的产地证明。
        if n_keep < 0:
            probs.append('manifest 没有 n_keep ⇒ 无法对账（无基准 = 无闸）')
        elif len(have) != n_keep:
            probs.append('快照 %d 个文件 ≠ manifest 记的 n_keep %d' % (len(have), n_keep))
        # ② 快照自带的那份 manifest 必须与仓库里那份逐字节相同。
        #    这一条抓「manifest 更新了、快照没换」—— T-PSA 收口时我自己踩过一次。
        inner = os.path.join(sd, MANIFEST_REL.replace('/', os.sep))
        if not os.path.exists(inner):
            probs.append('快照里没有 manifest（%s）⇒ 读快照的人看不到产地' % MANIFEST_REL)
        else:
            a = open(inner, 'rb').read()
            b = open(mpath, 'rb').read()
            if a != b:
                probs.append('快照内的 manifest 与仓库那份不一致（%d vs %d 字节）'
                             '⇒ 快照不是这份 manifest 产出的' % (len(a), len(b)))
        if probs:
            fails.append(('A1', '；'.join(probs)))
        else:
            say('  [ok  ] A1  快照 %d 个 == n_keep %d；快照内 manifest 与仓库逐字节一致'
                % (len(have), n_keep))

    # ---- A2 快照新鲜度 ----
    if m is None:
        skips.append(('A2', 'A0 已红，本轮不判'))
    else:
        st, n, files, why = _behind(head, info['source_head'], root, is_doc)
        info['snapshot_freshness'] = {'status': st, 'behind_by': n,
                                      'changed': files, 'why': why}
        if st == 'sync':
            say('  [ok  ] A2  快照与 HEAD 同步（source_head=%s）' % info['source_head'][:8])
        elif st == 'meta':
            warns.append(('A2', '快照' + why))
        elif st == 'code':
            fails.append(('A2', '快照' + why + ' ⇒ 代表不了当前状态，必须重建'))
        else:
            fails.append(('A2', '快照新鲜度算不出来：' + why))

    # ---- A3 bundle 存在 / 唯一 / 名实相符 ----
    bp = bundle_path
    cands = []
    if bp is None:
        bp, cands = find_bundle()
    info['bundle'] = bp
    info['bundle_candidates'] = cands
    if bp is None:
        if bundle_required:
            fails.append(('A3', '没找到唯一的离线 bundle（候选 %d 个%s）'
                          % (len(cands),
                             '：' + ', '.join(os.path.basename(x) for x in cands[:3])
                             if cands else '，_handoff/ 下没有 %s' % BUNDLE_GLOB)))
        else:
            skips.append(('A3', '显式 --allow-missing-bundle，豁免（不计入通过）'))
    elif not os.path.exists(bp):
        fails.append(('A3', 'bundle 不存在：%s' % bp))
    else:
        rc, refs, err = _refs_of(bp)
        main = (refs.get('refs/heads/main') or refs.get('HEAD') or '') if rc == 0 else ''
        info['bundle_main'] = main
        if not main:
            fails.append(('A3', '取不出包内 main（rc=%d %s）⇒ 包可能没写 HEAD'
                          % (rc, err.strip()[:80])))
        else:
            name = os.path.basename(bp)
            stem = name[len('FEM-Bench-Aero_'):-len('.bundle')] if name.startswith('FEM-Bench-Aero_') else ''
            if not stem:
                fails.append(('A3', '包名不合 `FEM-Bench-Aero_<sha>.bundle` 约定：%s' % name))
            elif not main.startswith(stem):
                fails.append(('A3', '文件名写的是 %s，但包内 main 是 %s ⇒ 名实不符'
                                    '（改个名不等于重打）' % (stem, main[:8])))
            else:
                say('  [ok  ] A3  bundle 内 main=%s 与文件名一致' % main[:8])

    # ---- A4 bundle 新鲜度 ----
    if not info.get('bundle_main'):
        skips.append(('A4', 'A3 未给出包内 main，本轮不判'))
    else:
        st, n, files, why = _behind(head, info['bundle_main'], root, is_doc)
        info['bundle_freshness'] = {'status': st, 'behind_by': n,
                                    'changed': files, 'why': why}
        if st == 'sync':
            say('  [ok  ] A4  bundle 与 HEAD 同步（main=%s）' % info['bundle_main'][:8])
        elif st == 'meta':
            warns.append(('A4', 'bundle' + why))
        elif st == 'code':
            fails.append(('A4', 'bundle' + why + ' ⇒ 代表不了当前状态，必须重打'))
        else:
            fails.append(('A4', 'bundle 新鲜度算不出来：' + why))

    info['fail_count'] = len(fails)
    info['warn_count'] = len(warns)
    info['skip_count'] = len(skips)
    return fails, warns, skips, info


# ---------------------------------------------------------------- 自检
def self_test():
    """七向。每向都打印「红了哪几条」——「判据没跑起来」与「判据通过」外观一样
    （T-D6 实测过：8 向全过但每行带 `[not_applicable]`）。
    """
    results = []

    def run(args, cwd):
        return subprocess.run(list(args), cwd=cwd, capture_output=True)

    def mk_repo(td):
        """c0 建文件并**当场打一份包**；c1 改代码；c2 改文档（= HEAD）。"""
        repo = os.path.join(td, 'src')
        os.makedirs(repo)
        run(['git', 'init', '-q'], repo)
        for k, v in (('user.name', 't'), ('user.email', 't@t'), ('core.autocrlf', 'false')):
            run(['git', 'config', k, v], repo)
        code, doc = 'feagpt_repro/a.py', 'feagpt_repro/reports/diagnostics/DOC.md'

        def write(rel, txt):
            fp = os.path.join(repo, rel.replace('/', os.sep))
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, 'wb') as f:            # 写字节，避开 Windows 文本模式偷偷转 CRLF（T-D3）
                f.write(txt.encode('utf-8'))

        def commit():
            run(['git', 'add', '-A'], repo)
            run(['git', 'commit', '-qm', 'c'], repo)
            return run(['git', 'rev-parse', 'HEAD'], repo).stdout.decode().strip()

        def pack(name):
            dst = os.path.join(td, 'FEM-Bench-Aero_%s.bundle' % name)
            # 必须显式带 HEAD：`--branches` 单独用不写 HEAD 引用（T-D6 空仓库之坑）
            run(['git', 'bundle', 'create', dst, 'HEAD', '--branches'], repo)
            return dst

        write(code, 'x=0\n')
        write(doc, 'd0\n')
        c0 = commit()
        b_c0 = pack(c0[:8])
        write(code, 'x=1\n')
        c1 = commit()
        write(doc, 'd1\n')
        c2 = commit()
        b_c2 = pack(c2[:8])
        return repo, c0, c1, c2, b_c0, b_c2, code, doc

    def mk_manifest(td, name, source_head, keep):
        p = os.path.join(td, name)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump({'source_head': source_head, 'n_keep': len(keep), 'keep': keep},
                      f, ensure_ascii=False)
        return p

    def mk_snap(td, name, repo, manifest_path, keep, tamper=False):
        """按 D4 `emit()` 的顺序造快照：KEEP 里的文件 + manifest 自己。

        ★ manifest 必须**最后**写进去（与 emit 一致）—— 否则 `tamper` 那一向会先被
          覆盖再改，测不出「快照里留的是上一版」。
        """
        sd = os.path.join(td, name)
        # `keep` 里本来就含 manifest 自己（它在 reports/diagnostics/ 下，D4 的 classify 会留）
        for q in sorted(set(list(keep) + [MANIFEST_REL])):
            src = manifest_path if q == MANIFEST_REL else os.path.join(repo, q.replace('/', os.sep))
            dst = os.path.join(sd, q.replace('/', os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
        if tamper:
            with open(os.path.join(sd, MANIFEST_REL.replace('/', os.sep)), 'ab') as f:
                f.write(b' ')
        return sd

    def probe(name, want_fail, want_warn, kw):
        f, w, s, _info = judge(quiet=True, **kw)
        ids_f = sorted(x[0] for x in f)
        ids_w = sorted(x[0] for x in w)
        ok = (sorted(want_fail) == ids_f) and (sorted(want_warn) == ids_w)
        results.append((name, ok, '红=' + (','.join(ids_f) or '无')
                        + ' 黄=' + (','.join(ids_w) or '无')
                        + ('' if ok else ' 期望红=%s 期望黄=%s' % (want_fail, want_warn))))

    with tempfile.TemporaryDirectory() as td:
        repo, c0, c1, c2, b_c0, b_c2, code, doc = mk_repo(td)
        # ★ 夹具必须像真的：D4 的 keep 里**含 manifest 自身**（它在 reports/diagnostics/ 下）。
        #   第一版漏了这一点，A1 的「成员数 == n_keep」在七向里红了六向 —— 夹具不真会让判据假红。
        keep = [code, doc, MANIFEST_REL]

        # ① 同步：manifest 与 bundle 都指向 HEAD ⇒ 全绿（防过严）
        m = mk_manifest(td, 'm_sync.json', c2, keep)
        probe('① 同步须绿', [], [],
              dict(root=repo, head=c2, manifest_path=m,
                   snap=mk_snap(td, 's1', repo, m, keep), bundle_path=b_c2))

        # ② 落后仅 metadata（c1→c2 只改文档）⇒ 快照黄；bundle 在 HEAD 上 ⇒ 不黄
        m = mk_manifest(td, 'm_meta.json', c1, keep)
        probe('② 落后仅文档须黄', [], ['A2'],
              dict(root=repo, head=c2, manifest_path=m,
                   snap=mk_snap(td, 's2', repo, m, keep), bundle_path=b_c2))

        # ③ 落后改代码（c0→c2 之间 c1 动了 .py）⇒ 快照与包**各红一条**，
        #    且原因里必须出现具体文件名（强判据吃掉弱判据会让红变假）
        m = mk_manifest(td, 'm_code.json', c0, keep)
        f, w, s, info = judge(root=repo, head=c2, manifest_path=m,
                             snap=mk_snap(td, 's3', repo, m, keep), bundle_path=b_c0, quiet=True)
        why = ' '.join(x[1] for x in f)
        results.append(('③ 落后改代码须红',
                        sorted(x[0] for x in f) == ['A2', 'A4'] and 'a.py' in why,
                        '红=' + (','.join(sorted(x[0] for x in f)) or '无')
                        + ' 原因含 a.py=%s' % ('a.py' in why)))

        # ④ manifest 缺失 ⇒ A0 红，A1/A2 明确 skip（不假装验证过）
        probe('④ manifest 缺失须红', ['A0'], [],
              dict(root=repo, head=c2, manifest_path=os.path.join(td, 'nope.json'),
                   snap=os.path.join(td, 's3'), bundle_path=b_c2))

        # ⑤ source_head 是本地不存在的 sha ⇒ A2 红（算不出来 = 红，不是 skip）
        m = mk_manifest(td, 'm_fake.json', 'f' * 40, keep)
        probe('⑤ 假 source_head 须红', ['A2'], [],
              dict(root=repo, head=c2, manifest_path=m,
                   snap=mk_snap(td, 's5', repo, m, keep), bundle_path=b_c2))

        # ⑥ 名实不符：包内是 c2、文件名写 c0 ⇒ A3 红。
        #    ★ 必须让**内容在 HEAD 上**，否则 A4 也会红，两红叠在一起就证明不了 A3 独立有效。
        os.makedirs(os.path.join(td, 'imp'), exist_ok=True)
        impostor = os.path.join(td, 'imp', 'FEM-Bench-Aero_%s.bundle' % c0[:8])
        shutil.copyfile(b_c2, impostor)
        m = mk_manifest(td, 'm_imp.json', c2, keep)
        probe('⑥ 名实不符须红', ['A3'], [],
              dict(root=repo, head=c2, manifest_path=m,
                   snap=mk_snap(td, 's6', repo, m, keep), bundle_path=impostor))

        # ⑦ 快照里的 manifest 落后一版（manifest 换了、快照没换）⇒ A1 红，A2 仍绿
        m = mk_manifest(td, 'm_stale.json', c2, keep)
        probe('⑦ 快照内 manifest 过期须红', ['A1'], [],
              dict(root=repo, head=c2, manifest_path=m,
                   snap=mk_snap(td, 's7', repo, m, keep, tamper=True), bundle_path=b_c2))

    ok_n = sum(1 for r in results if r[1])
    print('\n=== 自检 ===')
    for name, ok, detail in results:
        print('  [%s] %-26s %s' % ('ok  ' if ok else 'BAD!', name, detail))
    print('\n自检：%d/%d 向通过' % (ok_n, len(results)))
    return 0 if ok_n == len(results) else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bundle', metavar='PATH')
    ap.add_argument('--snap', metavar='DIR')
    ap.add_argument('--manifest', metavar='PATH')
    ap.add_argument('--head', metavar='SHA')
    ap.add_argument('--allow-missing-bundle', action='store_true',
                    help='显式声明本机没有分发包（公开集使用者）；豁免项不计入通过')
    ap.add_argument('--json', metavar='PATH')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    if a.self_test:
        return self_test()

    print('_f9_artifact_freshness.py  仓库=%s' % ROOT)
    fails, warns, skips, info = judge(manifest_path=a.manifest, snap=a.snap,
                                      bundle_path=a.bundle, head=a.head,
                                      bundle_required=not a.allow_missing_bundle)
    for cid, msg in warns:
        print('  [warn] %s  %s' % (cid, msg))
    for cid, msg in skips:
        print('  [skip] %s  %s' % (cid, msg))
    for cid, msg in fails:
        print('  [FAIL] %s  %s' % (cid, msg))
    if a.json:
        json.dump({'info': info, 'fails': fails, 'warns': warns, 'skips': skips},
                  open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('  -> %s' % a.json)
    if fails:
        print('\n结论：不通过 —— %d 条红（产物过期或无法证明新鲜，收口前必须重建）' % len(fails))
        return 2
    print('\n结论：通过 —— 两个产物都代表当前状态%s'
          % ('（%d 条黄：只落后在 metadata 上，属正常）' % len(warns) if warns else '（零黄）'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
