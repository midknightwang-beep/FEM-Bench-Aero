#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T-F3 自检：`--public` 的**边界**是否守得住。

为什么单独写：`--public` 是「放宽」，而放宽最容易的错法是**顺手把判定条件也改宽**。
主仓里 5 项本来就绿，所以「改坏了」在主仓完全看不出来（T-F3 首版就在主仓全绿，
到快照里才炸 NameError —— 判据没跑起来与判据通过外观一样）。

所以这里全部在**公开快照的副本**上做，每个场景只改一处，断言：
  ① 该红的仍然红；② 该豁免的仍然豁免；③ **两者不互相串**（红了却没被豁免、或豁免了本该红的）。

用法（在 feagpt_repro/ 下）：
    python _f3_public_exempt_selftest.py                       # 用默认快照路径
    python _f3_public_exempt_selftest.py --snapshot <dir>       # 指定快照

R75 三条边界对应的场景：
  ① 显式        → S6 不加 `--public` 时 C-013 必须红
  ② 精确到原因  → S3 协议文件存在时 S-51 不得豁免
                  S4 `PY=` 是裸 python 时 S-46 不得豁免
                  S5 非 C-013 的 artifact 缺失不得豁免
  ③ 不计入通过  → S1 断言豁免项 skip=True 且带 reason、且不计入语义项通过数
F-6 前提守卫（2026-11-05 拍板 A）对应的场景：
  S7 DATA.md 下载 URL 退化为占位符 ⇒ C-013 不得豁免（前提死亡）
  S8 DATA.md 整个不在公开集 ⇒ 同上
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
DEFAULT_SNAP = os.path.abspath(os.path.join(HERE, '..', '_handoff', 'public_snapshot'))


def _git(cwd, *args):
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)


def _prepare(snap, dest):
    """把快照复制一份并建成 git 仓库（check_claims 要查 git 追踪状态）。"""
    shutil.copytree(snap, dest, ignore=shutil.ignore_patterns('.git'))
    _git(dest, 'init', '-q', '-b', 'main')
    _git(dest, 'config', 'user.email', 't@t')
    _git(dest, 'config', 'user.name', 't')
    _git(dest, 'add', '-A')
    _git(dest, 'commit', '-q', '-m', 'base')
    return dest


def _restore(repo):
    _git(repo, 'checkout', '--', '.')
    # 场景里可能新增了文件，清掉未追踪的（保留 .git）
    _git(repo, 'clean', '-qfd')


def _run(repo, extra, js):
    if os.path.exists(js):
        os.remove(js)
    # ★ 2026-11-05（F-6 途中修）：跑**主仓当前的** check_claims.py（--root/--claims 指向副本），
    #   不再跑副本里冻结的旧版。首版用 cwd=副本 + 相对路径调脚本，跑的是快照冻结时的旧代码
    #   —— 代码演进后自检永远在验旧逻辑（S7/S8 首跑就是被这个坑的：新判据在副本里根本不存在）。
    #   「自检验的是当前代码 × 快照数据」，两样都必须指名道姓。
    r = subprocess.run([PY, os.path.join(HERE, 'check_claims.py'),
                        '--root', repo,
                        '--claims', os.path.join(repo, 'FEM-Bench-Aero', 'CLAIMS.md'),
                        '--json', js] + extra,
                       cwd=HERE,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if not os.path.exists(js):
        # 崩了（rc!=0 且没产出 JSON）也要说清楚，不能当成「没有红项」
        raise RuntimeError('check_claims 未产出 JSON（rc=%s）\n%s'
                           % (r.returncode, (r.stderr or '')[-800:]))
    d = json.load(open(js, encoding='utf-8'))
    red = {x['claim_id'] for x in d['results'] if not x['ok']}
    red |= {s['id'] for s in d['semantic'] if not s['ok']}
    ex = {x['claim_id'] for x in d['results'] if x.get('exempt')}
    ex |= {s['id'] for s in d['semantic'] if s.get('exempt')}
    noreason = [x['claim_id'] for x in d['results'] if x.get('exempt') and not x.get('reason')]
    noreason += [s['id'] for s in d['semantic'] if s.get('exempt') and not s.get('reason')]
    notskip = [s['id'] for s in d['semantic'] if s.get('exempt') and not s.get('skip')]
    return {'red': red, 'ex': ex, 'd': d, 'noreason': noreason, 'notskip': notskip,
            'rc': r.returncode}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot', default=DEFAULT_SNAP)
    a = ap.parse_args()
    snap = os.path.abspath(a.snapshot)
    if not os.path.isdir(snap):
        print('FAIL: 快照不存在 %s' % snap)
        return 2

    results = []
    td = tempfile.mkdtemp(prefix='f3_selftest_')
    repo = os.path.join(td, 'snap')
    js = os.path.join(td, 'cc.json')
    try:
        _prepare(snap, repo)
        print('副本 -> %s' % repo)

        def scenario(name, mutate, extra, must_red, must_ex, must_not_ex=()):
            _restore(repo)
            if mutate:
                mutate(repo)
            info = _run(repo, extra, js)
            ok = True
            why = []
            for x in must_red:
                if x not in info['red']:
                    ok = False
                    why.append('%s 未红' % x)
                if x in info['ex']:
                    ok = False
                    why.append('%s 竟被豁免' % x)
            for x in must_ex:
                if x not in info['ex']:
                    ok = False
                    why.append('%s 未豁免' % x)
            for x in must_not_ex:
                if x in info['ex']:
                    ok = False
                    why.append('%s 不该被豁免' % x)
            if info['noreason']:
                ok = False
                why.append('豁免缺 reason: %s' % info['noreason'])
            if info['notskip']:
                ok = False
                why.append('豁免项 skip!=True: %s' % info['notskip'])
            results.append({'name': name, 'ok': ok, 'why': why,
                            'red': sorted(info['red']), 'ex': sorted(info['ex'])})
            print('  [%s] %-42s 红=%s 豁免=%s%s'
                  % ('ok  ' if ok else 'FAIL', name[:42],
                     ','.join(sorted(info['red'])) or '-',
                     ','.join(sorted(info['ex'])) or '-',
                     '' if ok else '  <- ' + '; '.join(why)))

        FIVE = {'C-013', 'S-46', 'S-51', 'S-56', 'S-61'}

        # S1 正向：快照 + --public ⇒ 恰好这 5 项豁免，S-39/S-43 仍红（不是"全绿"）
        scenario('S1 正向：--public 豁免 5 项，其余仍红',
                 None, ['--public'], must_red={'S-39', 'S-43'}, must_ex=FIVE)

        # S2 基线：快照不带 --public ⇒ 这 5 项一个都不豁免
        scenario('S2 反向：不加 --public 时 5 项一个都不豁免',
                 None, [], must_red=FIVE, must_ex=set(), must_not_ex=FIVE)

        # S3 边界②：协议文件"存在且真的写死计数" ⇒ S-51 不得豁免
        def add_bad_agents(r):
            with open(os.path.join(r, 'AGENTS.md'), 'w', encoding='utf-8') as f:
                f.write('# AGENTS\n\n负控 69/69 ok\n')
        scenario('S3 边界：AGENTS.md 存在且写死负控计数 ⇒ S-51 仍红',
                 add_bad_agents, ['--public'], must_red={'S-51'}, must_ex={'C-013'})

        # S4 边界②：`PY=` 是裸 python（不是占位符）⇒ S-46 不得豁免
        def break_py(r):
            p = os.path.join(r, 'feagpt_repro', 'reports', 'INDEX.md')
            t = open(p, encoding='utf-8').read()
            t2 = t.replace('PY="{{VENV_PY}}"', 'PY="python"', 1)
            assert t2 != t, 'INDEX 里没找到占位符形态，场景无法构造'
            open(p, 'w', encoding='utf-8', newline='').write(t2)
        scenario('S4 边界：PY= 改成裸 python ⇒ S-46 仍红',
                 break_py, ['--public'], must_red={'S-46'}, must_ex={'S-51'})

        # S5 边界②：非 C-013 的 artifact 缺失 ⇒ 引用它的 claim 仍红（豁免不是"整表免检"）
        # C-041 与 C-038 共用 l2_clarify_dual.json，删掉后两条都必须红且不得被豁免。
        def drop_artifact(r):
            p = os.path.join(r, 'feagpt_repro', 'reports', 'l2_clarify_dual.json')
            assert os.path.exists(p), '锚点文件不存在，场景无法构造'
            os.remove(p)
        scenario('S5 边界：删非 C-013 的 artifact ⇒ C-038/C-041 仍红',
                 drop_artifact, ['--public'], must_red={'C-038', 'C-041'}, must_ex={'S-46'})

        # S6 边界①：不加 --public 时 C-013 必须红（豁免不得自动生效）
        scenario('S6 边界：不加 --public 时 C-013 必须红',
                 None, [], must_red={'C-013'}, must_ex=set(), must_not_ex={'C-013'})

        # S7 / S8（F-6 前提守卫，2026-11-05 拍板 A）：C-013 的豁免**有前提** ——
        # DATA.md §2 必须有真实 Release 下载 URL（公开侧替代物在，豁免才有存在理由）。
        # 前提死亡 ⇒ 豁免自动失效 ⇒ C-013 必须红且不得被豁免；其余豁免项不受牵连
        # （前提是 C-013 专属的，不得顺手把别的豁免也关掉）。
        def kill_download_url(r):
            p = os.path.join(r, 'FEM-Bench-Aero', 'DATA.md')
            t = open(p, encoding='utf-8').read()
            t2 = re.sub(r'https?://github\.com/[^\s\)\]>]+/releases/(?:tag|download)/data-v[^\s\)\]>]*',
                        '{{DATA_RELEASE_UNAVAILABLE}}', t)
            assert t2 != t, 'DATA.md 里没找到 Release URL，场景无法构造'
            open(p, 'w', encoding='utf-8', newline='').write(t2)
        scenario('S7 F-6：DATA.md 下载 URL 退化为占位符 ⇒ C-013 不得豁免',
                 kill_download_url, ['--public'],
                 must_red={'C-013'}, must_ex={'S-46'}, must_not_ex={'C-013'})

        def drop_data_md(r):
            p = os.path.join(r, 'FEM-Bench-Aero', 'DATA.md')
            assert os.path.exists(p), 'DATA.md 不在快照里，场景无法构造'
            os.remove(p)
        scenario('S8 F-6：DATA.md 整个不在公开集 ⇒ C-013 不得豁免',
                 drop_data_md, ['--public'],
                 must_red={'C-013'}, must_ex={'S-46'}, must_not_ex={'C-013'})
    finally:
        shutil.rmtree(td, ignore_errors=True)

    # S5 的精确断言：删掉 artifact 后，引用它的 claim 必须从"豁免/通过"变成"红"
    print()
    print('== 结果 ==')
    n_ok = sum(1 for r in results if r['ok'])
    for r in results:
        print('  %-4s %s' % ('ok' if r['ok'] else 'FAIL', r['name']))
        if not r['ok']:
            print('       %s' % '; '.join(r['why']))
    print('%d/%d 通过' % (n_ok, len(results)))
    return 0 if n_ok == len(results) else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
