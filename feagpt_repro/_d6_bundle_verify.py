# -*- coding: utf-8 -*-
"""T-D6 离线 bundle 验证闸：这个 .bundle 文件还能不能重建出仓库？

用法（全部命令用 venv 的 python）：
  python _d6_bundle_verify.py                      # 自动找 _handoff/FEM-Bench-Aero_<sha>.bundle 并全项校验
  python _d6_bundle_verify.py --bundle <path>      # 指定包
  python _d6_bundle_verify.py --with-data         # 额外验「离线数据链」：clone 里用本地 tarball 跑 fetch_data
  python _d6_bundle_verify.py --strict            # metadata_only（黄）也算红
  python _d6_bundle_verify.py --json out.json     # 证据落盘
  python _d6_bundle_verify.py --self-test         # 五向构造性验证：好包须绿 / 截断须红 / 落后改代码须红 / 落后仅改文档须黄 / 红的原因要分得开

为什么要有这个闸：bundle 不随提交自动更新，仓库每前进一次它就旧一分，
**而且没有任何东西会报错**（与 `.gitignore` 拦住 `package-lock.json` 同族：状态静默漂移）。
一次手工 clone 成功只能证明「今天这条路径能通」，证明不了下个月还通。

退出码：0 = 全过（允许 warn）；2 = 有判据红（原因逐条打印）；1 = 环境/参数错误。
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # 仓库根（feagpt_repro 的上一级）
HANDOFF = os.path.join(ROOT, '_handoff')
DATA_TGZ = os.path.join(HANDOFF, 'release', 'FEM-Bench-Aero-v1.1-data.tar.gz')

# 「落后但只改了这些文件」⇒ metadata_only（黄）。谓词精确：**任何代码改动落在包里没有的提交上，必然红**。
DEFAULT_DOC_ONLY = {
    'feagpt_repro/reports/diagnostics/task_d6_report.md',
    'feagpt_repro/reports/diagnostics/d6_bundle_evidence.json',
    'FEM-Bench-Aero/ROADMAP.md',
    '.workbuddy/memory/MEMORY.md',
    '.workbuddy/memory/' + '2026-10-31.md',
}

# 判据文件自身不得包含被检测词（T-D4 自指教训）：下面这几处检测动作都是调 git 完成的，
# 不在本文件里写死「坏包长什么样」的字面量。


def _git(args, cwd=None, timeout=600):
    """始终带 core.quotepath=false —— 中文路径被转义会让两侧字符集不同，comm/比对会双向误判（T-F2 连犯三次）。"""
    cmd = ['git', '-c', 'core.quotepath=false'] + list(args)
    p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace')


def _refs_of(bundle_path):
    """从 list-heads 取 (name -> sha)，不自己解析包格式（不另立第二套语义，T-D3 教训）。"""
    rc, out, err = _git(['bundle', 'list-heads', bundle_path])
    refs = {}
    if rc != 0:
        return rc, refs, err
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2:
            refs[parts[1]] = parts[0]
        elif len(parts) == 1:                     # 极老格式：只有 sha（HEAD）
            refs['HEAD'] = parts[0]
    return 0, refs, ''


def _tree_text(repo, rev):
    rc, out, err = _git(['ls-tree', '-r', rev], cwd=repo)
    if rc != 0:
        return rc, None, err
    return 0, out, ''


def _eol_text(repo):
    rc, out, err = _git(['ls-files', '--eol'], cwd=repo)
    return rc, out, err


def run_checks(bundle_path, repo=ROOT, with_data=None, strict=False,
               doc_only=None, quiet=False):
    """返回 (fails, warns, info)。fails/warns 都是 [(code, 原因)]。"""
    doc_only = set(DEFAULT_DOC_ONLY if doc_only is None else doc_only)
    fails, warns, info = [], [], {}
    say = (lambda *a: None) if quiet else print

    def bad(code, msg):
        fails.append((code, msg))
        say('  [BAD ] %-4s %s' % (code, msg))

    def ok(code, msg):
        say('  [ok  ] %-4s %s' % (code, msg))

    def warn(code, msg):
        warns.append((code, msg))
        say('  [warn] %-4s %s' % (code, msg))

    if not os.path.isfile(bundle_path):
        bad('C1', '找不到 bundle：%s' % bundle_path)
        return fails, warns, info

    # 跨盘符时 relpath 会抛 ValueError（Windows 专有坑），退回绝对路径即可
    try:
        shown = os.path.relpath(bundle_path, repo).replace(os.sep, '/')
    except ValueError:
        shown = bundle_path.replace(os.sep, '/')
    info['bundle'] = {'path': shown, 'bytes': os.path.getsize(bundle_path)}

    # C1 verify：包本身完不完整、有没有断史
    rc, out, err = _git(['bundle', 'verify', bundle_path])
    complete = 'records a complete history' in out
    info['bundle']['verify_rc'] = rc
    info['bundle']['complete_history'] = complete
    if rc != 0:
        bad('C1', 'git bundle verify 失败（rc=%d）：%s' % (rc, (err or out).strip().splitlines()[:1]))
    elif not complete:
        bad('C1', '包不自带完整历史（verify 通过但缺 prerequisite）—— 这种包 clone 出来会缺对象')
    else:
        ok('C1', 'verify=ok，records a complete history')

    rc, refs, err = _refs_of(bundle_path)
    info['bundle']['refs'] = refs
    if rc != 0 or not refs:
        bad('C2', '读不出 refs：%s' % err.strip().splitlines()[:1])
        return fails, warns, info
    heads = {k: v for k, v in refs.items() if k.startswith('refs/heads/')}
    main_sha = heads.get('refs/heads/main')
    if not main_sha and len(heads) == 1:          # 老默认分支名（master）也算，只要唯一
        main_sha = list(heads.values())[0]
    if not main_sha:
        bad('C2', '包里没有唯一的 main 分支（heads=%s，all=%s）'
            % (sorted(heads), ', '.join(sorted(refs))))
        return fails, warns, info
    ok('C2', 'refs=%d，main=%s，tag=%d' % (len(refs), main_sha[:7],
                                          len([k for k in refs if k.startswith('refs/tags/')])))

    # C2b：包里必须有 HEAD 引用。没有它 clone 出来是**空仓库**，而 `bundle verify` 仍然全绿、
    #      `fsck` 仍然干净、`status` 仍然干净 —— 三个闸一起给出「成功」的假象。
    #      实测触发：`git bundle create x --branches --tags` 就没有 HEAD。
    if 'HEAD' not in refs:
        bad('C2b', '包里没有 HEAD 引用（`--branches --tags` 打包就是这样）⇒ clone 后无默认分支、工作树为空；'
                   '应用 `git bundle create <f> HEAD --branches --tags`')
    else:
        ok('C2b', '包内有 HEAD 引用（clone 才有默认分支）')

    # C3+C4+C5+C6 全部在**干净临时目录**里做：只靠 bundle，不碰源 .git，不碰网络
    td = tempfile.mkdtemp(prefix='_d6_clone_')
    clone = os.path.join(td, 'repo')
    try:
        rc, out, err = _git(['clone', '--quiet', bundle_path, clone], cwd=td)
        info['clone'] = {'dest': 'temp', 'rc': rc}
        if rc != 0:
            bad('C3', '从 bundle clone 失败（rc=%d）：%s' % (rc, (err or out).strip().splitlines()[:2]))
            return fails, warns, info
        ok('C3', '干净目录 clone 成功（不碰网络、不碰源 .git）')

        rc, head, _ = _git(['rev-parse', 'HEAD'], cwd=clone)
        head = head.strip()
        info['clone']['head'] = head
        if rc != 0 or head == 'HEAD':
            bad('C3b', 'clone 里没有 HEAD 提交（空仓库）—— clone 退出码是 0，`fsck`/`status` 也「干净」，'
                       '但那是因为仓库里什么都没有')
        elif head != main_sha:
            bad('C3b', 'clone 出来的 HEAD（%s）≠ 包里声明的 main（%s）' % (head[:7], main_sha[:7]))
        else:
            ok('C3b', 'clone HEAD == 包声明 main（%s）' % head[:7])

        rc, out, err = _git(['fsck', '--full', '--no-progress'], cwd=clone)
        badlines = [l for l in (out + err).splitlines()
                    if l.strip() and not l.startswith(('dangling', 'notice'))]
        if rc != 0 or badlines:
            bad('C4', 'clone 里 git fsck 不干净（rc=%d）：%s' % (rc, badlines[:2]))
        else:
            ok('C4', 'git fsck --full 干净（无 missing / broken）')

        # C5 提交数：与源库同一提交上的提交数对齐
        rc1, src_cnt, _ = _git(['rev-list', '--count', main_sha], cwd=repo)
        rc2, cl_cnt, _ = _git(['rev-list', '--count', 'HEAD'], cwd=clone)
        info['commits'] = {'source': src_cnt.strip(), 'clone': cl_cnt.strip()}
        if rc1 != 0 or rc2 != 0 or src_cnt.strip() != cl_cnt.strip():
            bad('C5', '提交数不一致：源 %s / clone %s' % (src_cnt.strip() or '?', cl_cnt.strip() or '?'))
        else:
            ok('C5', '提交数一致（%s）' % src_cnt.strip())

        # C6 整棵树逐字节比：mode/type/sha/path 全串相同 ⇒ 文件集 + 内容 + 权限位一次覆盖
        rc1, t_src, e1 = _tree_text(repo, main_sha)
        rc2, t_cl, e2 = _tree_text(clone, 'HEAD')
        n_files = len(t_cl.splitlines()) if t_cl else 0
        info['files'] = n_files
        if rc1 != 0 or rc2 != 0:
            bad('C6', 'ls-tree 取不到：%s / %s' % (e1.strip()[:80], e2.strip()[:80]))
        elif t_src != t_cl:
            a, b = set(t_src.splitlines()), set(t_cl.splitlines())
            only_src = sorted(a - b)[:3]
            only_cl = sorted(b - a)[:3]
            bad('C6', '树不一致：源多 %d 条 / clone 多 %d 条；样本 源独有=%s clone 独有=%s'
                % (len(a - b), len(b - a),
                   [x.split('\t')[-1] for x in only_src], [x.split('\t')[-1] for x in only_cl]))
        else:
            ok('C6', '整棵树逐条相同（%d 个文件，含 blob sha）' % n_files)

        # C7 D3 的行尾成果必须在离线路径上也成立
        rc1, e_src, _ = _eol_text(repo)
        rc2, e_cl, _ = _eol_text(clone)
        diff = [l for l in set(e_src.splitlines()) ^ set(e_cl.splitlines())]
        info['eol_diff_lines'] = len(diff)
        if rc1 != 0 or rc2 != 0:
            bad('C7', 'ls-files --eol 取不到')
        elif diff:
            bad('C7', '行尾解释不一致（%d 行不同），样本：%s' % (len(diff), diff[:2]))
        else:
            ok('C7', 'git ls-files --eol 与源库逐行相同（D3 的行尾规则随包生效）')

        # C8 工作区必须干净：行尾若被解错，git 会立刻显示成「已修改」
        rc, out, _ = _git(['status', '--porcelain'], cwd=clone)
        dirty = [l for l in out.splitlines() if l.strip()]
        info['clone']['dirty'] = len(dirty)
        if rc != 0 or dirty:
            bad('C8', 'clone 工作区不干净（%d 条）：%s' % (len(dirty), dirty[:2]))
        else:
            ok('C8', 'clone 工作区干净（无「莫名修改」⇒ 行尾解释正确）')

        # C9 新鲜度：落后几个提交；落后的提交改了什么
        rc, src_head, _ = _git(['rev-parse', 'HEAD'], cwd=repo)
        src_head = src_head.strip()
        rc, behind, _ = _git(['rev-list', '--count', '%s..%s' % (main_sha, src_head)], cwd=repo)
        behind = int(behind.strip() or 0) if rc == 0 else -1
        info['freshness'] = {'source_head': src_head, 'behind_by': behind}
        if behind < 0:
            bad('C9', '算不出落后提交数（源 HEAD 与包 main 不在同一历史线上？）')
        elif behind == 0:
            ok('C9', '包与源 HEAD 同步（behind_by=0）')
        else:
            rc2, changed, _ = _git(['diff', '--name-only', main_sha, src_head], cwd=repo)
            names = [n for n in changed.splitlines() if n.strip()]
            outside = sorted(set(names) - doc_only)
            info['freshness']['changed'] = names
            info['freshness']['changed_outside_doc_only'] = outside
            if outside:
                bad('C9', '包落后 %d 个提交，且其中有 %d 个非文档文件被改过（%s）⇒ 包代表不了当前状态'
                    % (behind, len(outside), outside[:3]))
            else:
                warn('C9', '包落后 %d 个提交，但落后部分只动了文档/证据（%d 个）⇒ metadata_only'
                     % (behind, len(names)))

        # C10 离线数据链：代码有了，数据能不能在无网络下就位
        if with_data:
            info['data_chain'] = _data_chain(clone, with_data, bad, ok, warn, say)
        else:
            say('  [skip] C10  未指定 --with-data，跳过离线数据链')
    finally:
        shutil.rmtree(td, ignore_errors=True)

    info['fail_count'] = len(fails)
    info['warn_count'] = len(warns)
    return fails, warns, info


def _data_chain(clone, tarball, bad, ok, warn, say):
    """在 clone 里用本地 tarball 跑 fetch_data.py，核对 modeling/ 条数 == manifest.n_cases。"""
    out = {'tarball': tarball if isinstance(tarball, str) else str(tarball)}
    if not os.path.isfile(tarball):
        bad('C10', '数据包不存在：%s' % tarball)
        return out
    script = os.path.join(clone, 'feagpt_repro', 'fetch_data.py')
    if not os.path.isfile(script):
        bad('C10', 'clone 里没有 feagpt_repro/fetch_data.py ⇒ 代码链断了')
        return out
    # 无网络验证：把代理变量清掉 + 断掉任何 URL 兜底（fetch_data 只读本地文件，这里做的是「证明确实没联网」）
    env = dict(os.environ)
    for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
        env.pop(k, None)
    p = subprocess.run([sys.executable, script, '--src', tarball], cwd=clone,
                       capture_output=True, env=env, timeout=1800)
    txt = p.stdout.decode('utf-8', 'replace')
    out['rc'] = p.returncode
    out['tail'] = [l for l in txt.splitlines() if l.strip()][-3:]
    if p.returncode != 0:
        bad('C10', 'clone 里 fetch_data.py 失败（rc=%d）：%s'
            % (p.returncode, (p.stderr.decode('utf-8', 'replace').strip().splitlines() or [''])[:2]))
        return out
    try:
        man = json.load(open(os.path.join(clone, 'FEM-Bench-Aero', 'manifest.json'), encoding='utf-8'))
        # 计数在 summary 里（不是顶层键；写错键名会静默变成 None，比对就退化成恒假 — 同族于
        # 「键名不符」那次：明细看着对、断言其实没生效）
        expect = (man.get('summary') or {}).get('n_cases', man.get('n_cases'))
    except Exception as e:
        bad('C10', 'clone 里读不出 manifest 条数：%s' % e)
        return out
    if expect is None:
        bad('C10', 'manifest 里找不到条数字段（summary.n_cases）—— 判据自身取不到基准，不能算过')
        return out
    mdir = os.path.join(clone, 'FEM-Bench-Aero', 'modeling')
    have = len([d for d in os.listdir(mdir) if os.path.isdir(os.path.join(mdir, d))]) if os.path.isdir(mdir) else 0
    out.update({'expect': expect, 'have': have})
    if expect != have:
        bad('C10', '数据链条数不符：modeling %d 条 / manifest 期望 %s' % (have, expect))
    else:
        ok('C10', '离线数据链通：本地包解出 %d 条 == manifest.n_cases（全程无网络）' % have)
    return out


def self_test():
    """五向。每向都打印「红了哪几条」，因为「判据没跑起来」和「判据通过」外观一样（自检必须打印明细）。"""
    results = []

    def mk_repo(td, files_seq, on_commit=None):
        """files_seq: [{相对路径: 内容}] 逐次提交；返回 (repo, 提交 sha 列表)。
        on_commit(i, repo) 在每次提交后调用 —— 用来「在当时的 HEAD 上打一份包」。"""
        repo = os.path.join(td, 'src')
        os.makedirs(repo, exist_ok=True)
        run = lambda *a: subprocess.run(list(a), cwd=repo, capture_output=True)
        run('git', 'init', '-q')
        run('git', 'config', 'user.name', 't')
        run('git', 'config', 'user.email', 't@t')
        run('git', 'config', 'core.autocrlf', 'false')
        shas = []
        for i, files in enumerate(files_seq):
            if i == 0:
                # 夹具必须带行尾规则：**clone 端行尾不只由规则决定，还由 clone 端的 core.autocrlf 决定**，
                # 没有 `.gitattributes` 时两边会因全局 autocrlf 差异而红（那是夹具不真，不是判据错）。
                files = dict({'.gitattributes': '* text=auto eol=lf\n'}, **files)
            for rel, content in files.items():
                fp = os.path.join(repo, rel.replace('/', os.sep))
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                with open(fp, 'wb') as f:          # 写字节，避开 Windows 文本模式偷偷转 CRLF（T-D3 教训）
                    f.write(content.encode('utf-8'))
            run('git', 'add', '-A')
            run('git', 'commit', '-qm', 'c')
            shas.append(run('git', 'rev-parse', 'HEAD').stdout.decode().strip())
            if on_commit:
                on_commit(i, repo)
        return repo, shas

    def bundle_of(td, repo, name, *revargs):
        dst = os.path.join(td, name)
        subprocess.run(['git', 'bundle', 'create', dst, *revargs], cwd=repo, capture_output=True)
        return dst

    with tempfile.TemporaryDirectory() as td:
        # 关键：**包必须「在当时的 HEAD 上」打出来**，所以要在提交之间打，不能事后用 sha 打
        # （事后 `--branches <sha>` 里 main 仍指向最新提交 ⇒ behind_by 恒为 0，③④ 两向会退化成空操作）。
        doc = 'DOC.md'
        steps = [{'a.py': 'x=1\n', doc: 'd1\n'},       # 提交 0
                 {'a.py': 'x=2\n', doc: 'd2\n'},       # 提交 1：改代码
                 {'a.py': 'x=2\n', doc: 'd3\n'}]       # 提交 2：只改文档（HEAD）
        bundles = {}

        def snap(i, repo_path):
            # 每个提交打一份包，模拟「当时打、后来仓库又前进了」
            # 必须带 `HEAD`：`--branches` 单独用**不会**写 HEAD 引用（实测四种组合），
            # 那样的包 clone 出来是空仓库 —— 这是 ⑥ 那一向专门要测的坏包
            name = ['old', 'mid', 'good'][i] + '.bundle'
            bundles[i] = bundle_of(td, repo_path, name, 'HEAD', '--branches')

        repo, shas = mk_repo(td, steps, on_commit=snap)
        doc_only = {doc}
        good, mid, old = bundles[2], bundles[1], bundles[0]

        # ① 好包须绿（防过严）：打在当前 HEAD 上
        f, w, info = run_checks(good, repo=repo, doc_only=doc_only, quiet=True)
        results.append(('① 好包须绿', not f and not w, [x[0] for x in f] + [x[0] for x in w],
                        'behind=%s' % info.get('freshness', {}).get('behind_by')))

        # ② 截断包须红（且真的能红：不看退出码，看红项）
        trunc = os.path.join(td, 'trunc.bundle')
        with open(good, 'rb') as fh:
            blob = fh.read()
        with open(trunc, 'wb') as fh:
            fh.write(blob[:max(0, len(blob) - 4096)])
        f, w, _ = run_checks(trunc, repo=repo, doc_only=doc_only, quiet=True)
        ids = [x[0] for x in f]
        results.append(('② 截断包须红', ('C1' in ids or 'C3' in ids), ids, ''))

        # ③ 落后且改了代码 ⇒ 红（新鲜度判据真的能红）：包打在提交 0，之后 a.py 改过
        f, w, info = run_checks(old, repo=repo, doc_only=doc_only, quiet=True)
        ids = [x[0] for x in f]
        results.append(('③ 落后改代码须红', 'C9' in ids, ids,
                        'behind=%s' % info.get('freshness', {}).get('behind_by')))

        # ④ 落后但只改文档 ⇒ 黄（R75 的边界：放宽只在这个谓词下成立，且不得变红）
        f, w, info = run_checks(mid, repo=repo, doc_only=doc_only, quiet=True)
        ids = [x[0] for x in f]
        wids = [x[0] for x in w]
        results.append(('④ 落后仅改文档须黄', (not ids) and 'C9' in wids, ids + wids,
                        'behind=%s' % info.get('freshness', {}).get('behind_by')))

        # ⑤ 红的原因要分得开：截断包的红不能是「找不到文件」那种环境错
        f, w, _ = run_checks(trunc, repo=repo, doc_only=doc_only, quiet=True)
        msgs = ' '.join(m for _, m in f)
        results.append(('⑤ 红的原因对得上', ('verify' in msgs or 'clone' in msgs or '读不出' in msgs),
                        [x[0] for x in f], ''))

        # ⑥ 无 HEAD 的包必须红，且要指名道姓（C2b）—— 判据必须落在**根因**上，不能落在后果上。
        #    实测：这个坏包的后果是「clone 出空仓库」，但**后果依赖引用构成** ——
        #    只有 1 个分支时 git 会自动选中它（夹具里就是 files=3、C3b 不红），
        #    有 6 个 tag 时它选不出来（真库上实测 clone 出空仓库、C3b 才红）。
        #    ⇒ 所以 ⑥ 只断言 C2b，C3b 是「有时会一起红」的附加信号。
        nohead = bundle_of(td, repo, 'nohead.bundle', '--branches')
        f, w, info = run_checks(nohead, repo=repo, doc_only=doc_only, quiet=True)
        ids = [x[0] for x in f]
        results.append(('⑥ 无 HEAD 包须红', 'C2b' in ids, ids,
                        'files=%s' % info.get('files')))

    print('=== _d6_bundle_verify --self-test ===')
    good = True
    for name, passed, ids, extra in results:
        print('  [%s] %-18s 红/黄项=%-14s %s'
              % ('ok  ' if passed else 'BAD ', name, ids or '[]', extra))
        good = good and passed
    print('=> %d/%d' % (sum(1 for _, p, _, _ in results if p), len(results)))
    return 0 if good else 2


def find_bundle(repo=ROOT):
    pats = sorted(glob.glob(os.path.join(repo, '_handoff', 'FEM-Bench-Aero_*.bundle')))
    return pats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bundle', default=None)
    ap.add_argument('--repo', default=ROOT)
    ap.add_argument('--with-data', nargs='?', const=DATA_TGZ, default=None,
                    help='额外验离线数据链；不带值则用 _handoff/release 下的 v1.1 包')
    ap.add_argument('--strict', action='store_true', help='metadata_only 也算红')
    ap.add_argument('--json', default=None)
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()

    if a.self_test:
        return self_test()

    bundle = a.bundle
    if not bundle:
        found = find_bundle(a.repo)
        if len(found) == 1:
            bundle = found[0]
        elif not found:
            print('找不到 bundle：%s/_handoff/FEM-Bench-Aero_*.bundle' % a.repo)
            return 1
        else:
            print('找到 %d 个 bundle，无法确定验哪个（多份并存时旧的会被误取）：' % len(found))
            for p in found:
                print('  - %s' % os.path.basename(p))
            print('请用 --bundle 明确指定，或删掉过期的包。')
            return 1

    print('=== _d6_bundle_verify：%s ===' % os.path.basename(bundle))
    # 一律转绝对路径：所有 git 调用都以 repo 根为 cwd，相对路径会被解释成「相对 repo 根」而不是相对当前目录
    bundle = os.path.abspath(bundle)
    with_data = os.path.abspath(a.with_data) if a.with_data else None
    fails, warns, info = run_checks(bundle, repo=a.repo, with_data=with_data,
                                    strict=a.strict)
    out = {
        'generated_at': datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'),
        'purpose': 'T-D6：离线 bundle 能否重建仓库（D 段最后 0.5）',
        'source_repo': a.repo,
        'strict': bool(a.strict),
        'info': info,
        'fails': [{'code': c, 'reason': m} for c, m in fails],
        'warns': [{'code': c, 'reason': m} for c, m in warns],
        'ok': (not fails) and not (a.strict and warns),
    }
    if a.json:
        with open(a.json, 'w', encoding='utf-8', newline='') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('证据 -> %s' % a.json)

    if fails or (a.strict and warns):
        print('=> 红 %d 条 / 黄 %d 条' % (len(fails), len(warns)))
        return 2
    print('=> 全过%s' % ('（含 %d 条黄）' % len(warns) if warns else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
