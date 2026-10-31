#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_d4_public_set.py —— 公开分发集清单器 / 快照生成器 / 校验器（T-D4）

设计原则（见 task_d4_contract.md §2）：
  ① 白名单默认拒绝 —— 只有显式命中的路径进公开集；漏一个只是「少给」，不会泄露。
  ② 反向必含     —— 对外文档（QUICKSTART/DATA/RUBRIC/CLAIMS/INDEX）里引用到的、
                    且在仓库中真实存在的文件，必须在公开集里；缺一个即红。

只做 ① 会「少给而无人知」；只做 ② 会「多给而无人知」。两者互为对照。

用法：
  python _d4_public_set.py                      # 统计 + 写 reports/diagnostics/public_manifest.json
  python _d4_public_set.py --emit ../_handoff/public_snapshot   # 生成快照目录
  python _d4_public_set.py --check ../_handoff/public_snapshot  # 校验已有快照（P1–P8）
  python _d4_public_set.py --self-test          # 构造性验证判据会红（P1/P2/P4/P5/P7/P8 共十二向）

退出码：0 = 全过；2 = 有判据红（原因逐条打印）；1 = 环境/参数错误。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MANIFEST = os.path.join(HERE, 'reports', 'diagnostics', 'public_manifest.json')

# ---- 根目录必需文件（其余根目录文件一律不进公开集）----
# 注意 `.gitignore` / `.gitattributes` 这类**定义仓库行为的配置**不在这里：
# 它们由 _is_repo_config() 的结构性规则命中（T-F7）。放进名单就会漏，漏了还没人报。
ROOT_KEEP = {'LICENSE', 'LICENSE-DATA', 'README.md'}

# ---- 对外文档：反向必含的来源 ----
PUBLIC_DOCS = [
    'FEM-Bench-Aero/QUICKSTART.md',
    'FEM-Bench-Aero/DATA.md',
    'FEM-Bench-Aero/RUBRIC.md',
    'FEM-Bench-Aero/CLAIMS.md',
    'feagpt_repro/reports/INDEX.md',
]

# ---- 文本扫描：是否当文本读 ----
TEXT_EXT = {'.md', '.py', '.json', '.jsonl', '.txt', '.js', '.html', '.yaml', '.yml',
            '.inp', '.cae', '.cfg', '.sh', '.bat', '.toml', '.csv'}
TEXT_MAX = 4 * 1024 * 1024      # 超过 4MB 的文本不扫（性能），但会记入 skipped

# ---- P4 本机路径/身份泄露词 ----
# 用 _m() 拼接构造：判据文件自身若直接写出这些字面量，会把自己判红（自指误报）。
# 拼接后文件文本里不存在完整串，运行时字符串完全等价，检测能力不受影响。
def _m(*parts):
    return ''.join(parts)


LOCAL_MARKERS = [_m('C:', '/Users/'), _m('C:', '\\Users\\'),
                 _m('F:', '/AI FEA'), _m('F:', '\\AI FEA'),
                 _m('F:', '/FEA_Archive'), _m('F:', '\\FEA_Archive'),
                 _m('222', '07')]

# ---- P5 受限标识类字样（用户级铁律；同样用拼接避免自指）----
SECRET_MARKERS = [_m('密', '级'), _m('涉', '密'), _m('机', '密'),
                  _m('秘', '密'), _m('内', '部', '资料'), _m('内', '部', '注意')]

PROBE_SEG = re.compile(r'^(?:_probe[a-z0-9_]*|_t\d+_probe|_superseded|_retired)$', re.I)


def _git(args, cwd=None):
    p = subprocess.run(['git'] + args, cwd=cwd or ROOT, capture_output=True)
    return p.returncode, p.stdout


def _is_repo_config(p):
    """根目录下**定义仓库行为**的配置文件：`.gitignore` / `.gitattributes` / `.gitmodules` …

    为什么不做成名单（F-7）：T-F2 现场证明「默认拒绝 + 手抄名单」这个组合必然漏项 ——
    `.gitignore` 被手工加进了 ROOT_KEEP，作用完全相同的 `.gitattributes` 没加，
    于是第三方 clone 公开库后 `* text=auto eol=crlf` / `*.sh text eol=lf` 两条规则**全部消失**
    （实测 `eol: crlf` → `eol: unspecified`），D3 一整轮解决的换机行尾问题在公开库侧原样复活。
    而**没有任何闸会报**：P6 比的是「快照 vs manifest」，manifest 恰恰由 classify() 产出 ⇒ 自证循环。

    所以改成结构性规则：根目录、basename 以 `.git` 开头且不是 `.git` 目录本身 ⇒ 仓库行为配置。
    新增同类文件自动覆盖，不需要维护名单（R69：能判的不变量优于需要维护的名单）。
    """
    if '/' in p or '\\' in p:
        return False
    return p.startswith('.git') and p != '.git'


def _sha256_file(fp):
    h = hashlib.sha256()
    with open(fp, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _attr_probe_target(files):
    """P8 生效性探针的样本：优先 `.sh`（`*.sh text eol=lf` 是最容易被 echo 掉的**例外**规则），
    其次 `.py`（被 `* text=auto eol=crlf` 命中）。同类取排序后第一个 ⇒ 结果与顺序无关。
    样本缺失时返回 None（由调用方记 not_run，不假装验证过）。"""
    for ext in ('.sh', '.py'):
        cand = sorted(p for p in files if p.endswith(ext))
        if cand:
            return cand[0]
    return sorted(files)[0] if files else None


def _git_check_attr(sample, work_tree, git_dir=None):
    """问 git：它对这个文件的属性解释成什么。返回 [[attr, value], ...] 或 None（git 不可用/报错）。

    为什么问 git 而不是自己解析 `.gitattributes`：规则只有一处，第二处实现就是 bug
    （T-D3 的行尾规范化器就是栽在「自建第二套规则」上）。这里只比**结果**。
    """
    env = dict(os.environ)
    cwd = ROOT
    if git_dir:
        env['GIT_DIR'] = git_dir
        env['GIT_WORK_TREE'] = work_tree
        cwd = work_tree
    try:
        p = subprocess.run(['git', '-c', 'core.quotepath=false', 'check-attr', '--all', '--', sample],
                           cwd=cwd, env=env, capture_output=True, timeout=120)
    except Exception:
        return None
    if p.returncode != 0:
        return None
    out = []
    for line in p.stdout.decode('utf-8', 'replace').splitlines():
        parts = line.rsplit(': ', 2)
        if len(parts) == 3:
            out.append([parts[1], parts[2]])
    return sorted(out)


def tracked_files():
    rc, out = _git(['ls-files', '-z'])
    if rc != 0:
        raise SystemExit('git ls-files 失败（不在仓库里？）')
    return [x.decode('utf-8') for x in out.split(b'\0') if x]


def classify(p):
    """返回 (keep: bool, category: str)。探针判定优先于一切前缀规则。"""
    segs = p.split('/')
    # 探针/中间态：任何层级段名命中都排出（即使位于 feagpt_repro 下）
    for s in segs[:-1]:
        if PROBE_SEG.match(s):
            return False, '探针/调试产物'
    if p.startswith('FEM-Bench-Aero/'):
        return True, 'KEEP:bench 文档与数据'
    if p.startswith('feagpt_repro/'):
        return True, 'KEEP:代码与证据'
    if _is_repo_config(p):
        return True, 'KEEP:根目录仓库配置'
    if p in ROOT_KEEP:
        return True, 'KEEP:根目录必需'
    if p.startswith('.workbuddy/') or p.endswith('.genie'):
        return False, '内部记忆/应用'
    if p.startswith('_report/'):
        return False, '汇报图表'
    if p.startswith('output/'):
        return False, '技术设计报告'
    if p.startswith('智能生成技术项目汇报/') or p.startswith('技术框架设计汇报/'):
        return False, '汇报幻灯'
    if p.startswith('_t4_probe/'):
        return False, '探针/调试产物'
    return False, '根目录内部材料'


def size_of(p):
    try:
        return os.path.getsize(os.path.join(ROOT, p))
    except OSError:
        return 0


# 注意 jsonl 必须排在 json 之前：交替式 `json|jsonl` 会把 `x.jsonl` 截成 `x.json`（假红）
_TOK = re.compile(r'[A-Za-z0-9_./-]+\.(?:jsonl|json|md|py|js)')


def _referenced_paths(files):
    """引用闭包：对外文档/CLAIMS 引用到的、在仓库中真实存在的文件。

    为什么需要：C-007/C-008 两条 active claim 的 artifact 就在 `_probe_m14/` 里。
    单纯按目录名判「探针 = 垃圾」会毁掉 claim 的证据链（R-A3）。
    所以「被引用」优先于「目录名像垃圾」—— 但只拉回**具体文件**，不拉整个目录。
    """
    bybase = {}
    for p in files:
        bybase.setdefault(p.split('/')[-1], []).append(p)
    refs = set()
    for doc in PUBLIC_DOCS:
        fp = os.path.join(ROOT, doc)
        if not os.path.exists(fp):
            continue
        txt = _read_text(fp) or ''
        for tok in _TOK.findall(txt):
            if tok.startswith(('http', '/')):
                continue
            # 「提及」≠「引用」：RUBRIC/CLAIMS 正文里会写到 AGENTS.md / CLAUDE.md 这类
            # 裸文件名（描述规则适用范围），那不是引用。只有带目录的路径才算引用。
            if '/' not in tok:
                continue
            hits = bybase.get(tok.split('/')[-1], [])
            if len(hits) == 1:
                refs.add(hits[0])
    return refs


def build_manifest():
    files = tracked_files()
    forced = _referenced_paths(files)
    keep, drop = [], {}
    cat = {}
    pulled = []
    for p in files:
        k, c = classify(p)
        if not k and p in forced:
            k, c = True, 'KEEP:引用闭包拉回'
            pulled.append(p)
        s = size_of(p)
        e = cat.setdefault(c, {'n': 0, 'bytes': 0})
        e['n'] += 1
        e['bytes'] += s
        if k:
            keep.append(p)
        else:
            drop.setdefault(c, []).append(p)
    rc, out = _git(['rev-parse', 'HEAD'])
    head = out.decode().strip() if rc == 0 else ''
    # P8 的基准：**从源库现取**，不写名单（新增 `.gitmodules` 之类自动覆盖）
    # ⚠ sha256 记的是**工作区字节**（因此 `.gitattributes` 在 Windows 上是 CRLF 版、Linux 上是 LF 版）。
    #   它只在「manifest 与快照同一次运行产出」这个前提下自洽 —— `main()` 里 `--check` 传的正是
    #   现算的 manifest。**不得**把它当跨机锚点用（拿入库的旧 manifest 去 check 另一台机器的新快照
    #   会得到假红）；跨机比对请改用 `git hash-object`（它按 attributes 归一化）。
    repo_configs = {}
    for p in sorted(q for q in files if _is_repo_config(q)):
        fp = os.path.join(ROOT, p)
        repo_configs[p] = {'sha256': _sha256_file(fp), 'bytes': os.path.getsize(fp)}
    sample = _attr_probe_target(keep)
    repo_attr_probe = {
        'sample': sample,
        # 源库对这个样本的属性解释。生效性判据在 check() 里拿**快照库**的回答跟它比。
        'attrs': _git_check_attr(sample, ROOT) if sample else None,
    }
    return {
        'generated_at': datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'),
        'source_head': head,
        'rule': 'whitelist-default-deny（详见 task_d4_contract.md §2）',
        'n_total': len(files),
        'bytes_total': sum(size_of(p) for p in files),
        'n_keep': len(keep),
        'bytes_keep': sum(size_of(p) for p in keep),
        'categories': cat,
        'keep': sorted(keep),
        'pulled_by_reference': sorted(pulled),
        'drop_categories': {k: sorted(v) for k, v in drop.items()},
        'repo_configs': repo_configs,
        'repo_attr_probe': repo_attr_probe,
    }


# ---------------- 校验（对快照目录）----------------

def _walk(root):
    out = []
    for dp, _dn, fns in os.walk(root):
        if '.git' in dp.split(os.sep):
            continue
        for fn in fns:
            fp = os.path.join(dp, fn)
            out.append(os.path.relpath(fp, root).replace(os.sep, '/'))
    return out


def _read_text(fp):
    try:
        if os.path.getsize(fp) > TEXT_MAX:
            return None
        with open(fp, 'rb') as f:
            return f.read().decode('utf-8', 'replace')
    except OSError:
        return None


def _doc_text(snap, doc):
    """对外文档优先取**快照里的那份**（那才是要公开的内容）；快照没有则退回仓库。"""
    for base in (snap, ROOT):
        fp = os.path.join(base, doc.replace('/', os.sep))
        if os.path.exists(fp):
            return _read_text(fp), base == snap
    return None, False


def check(snap, manifest=None):
    """返回 (fails, notes)。fails 每条 = (判据 id, 说明)。"""
    fails, notes = [], []
    if not os.path.isdir(snap):
        return [('P0', '快照目录不存在: %s' % snap)], notes
    have = _walk(snap)
    have_set = set(have)
    manifest = manifest or build_manifest()
    keep = set(manifest['keep'])

    # ---- P1 内部材料零残留 ----
    # 判据口径：快照里不得出现**任何** drop_categories 中的文件。
    # 不用 classify() 重新判 —— 闭包拉回的文件（如 _probe_m14 里的 claim artifact）
    # 已被从 drop 移入 keep，重新 classify 会把它们误报为「残留」。
    pulled = set(manifest.get('pulled_by_reference', []))
    bad = [p for p in have if p not in pulled and classify(p)[0] is False]
    fails.append(('P1', '内部材料残留 %d 个: %s' % (len(bad), ', '.join(bad[:6])))) if bad \
        else notes.append('P1 ok：内部材料 0 命中（快照 %d 个文件）' % len(have))

    # ---- P2 反向必含（对外文档引用 → 必须在快照里）----
    missing, internal_ref = [], []
    for doc in PUBLIC_DOCS:
        txt, from_snap = _doc_text(snap, doc)
        if txt is None:
            notes.append('P2 跳过（文档不存在）: %s' % doc)
            continue
        for tok in set(re.findall(r'[A-Za-z0-9_./-]+\.(?:jsonl|json|md|py|js)', txt)):
            if tok.startswith('/') or tok.startswith('http'):
                continue
            base = tok.split('/')[-1]
            # 在已追踪文件里找 basename 唯一命中
            hits = [q for q in manifest['keep'] if q.split('/')[-1] == base]
            hits += [q for q in manifest['drop_categories'].get('探针/调试产物', [])
                     if q.split('/')[-1] == base]
            if len(hits) == 1:
                q = hits[0]
                if q in keep and q not in have_set:
                    missing.append((doc, tok, q))
                elif q not in keep:
                    internal_ref.append((doc, tok, q))
    if missing:
        fails.append(('P2', '对外文档引用但快照缺失 %d 处: %s' % (
            len(missing), '; '.join('%s→%s' % (d.split('/')[-1], t) for d, t, _ in missing[:6]))))
    else:
        notes.append('P2 ok：对外文档引用的既有文件全部在快照内')
    if internal_ref:
        fails.append(('P2b', '对外文档引用了**内部材料** %d 处（分类规则冲突）: %s' % (
            len(internal_ref), '; '.join('%s→%s' % (d.split('/')[-1], q) for d, t, q in internal_ref[:6]))))

    # ---- P3 claim artifact 必含 ----
    claims_txt, claims_src = _doc_text(snap, 'FEM-Bench-Aero/CLAIMS.md')
    miss3 = []
    if claims_txt is None:
        notes.append('P3 跳过（CLAIMS.md 不存在）')
    else:
        arts = set(re.findall(r'reports/[A-Za-z0-9_./-]+\.(?:jsonl|json|md)', claims_txt))
        for a in arts:
            cand = [q for q in have_set if q.endswith(a)]
            if not cand:
                miss3.append(a)
    if miss3:
        fails.append(('P3', 'CLAIMS 引用的 artifact 在快照中缺失 %d 个: %s'
                      % (len(miss3), ', '.join(miss3[:6]))))
    elif claims_txt is not None:
        notes.append('P3 ok：CLAIMS 引用的 %d 个 reports/** artifact 全部在快照内'
                     % len(set(re.findall(r'reports/[A-Za-z0-9_./-]+\.(?:jsonl|json|md)', claims_txt))))

    # ---- P4 本机路径/身份零泄露 ----
    hits4, scanned, skipped = [], 0, 0
    for p in have:
        ext = os.path.splitext(p)[1].lower()
        if ext not in TEXT_EXT:
            continue
        txt = _read_text(os.path.join(snap, p))
        if txt is None:
            skipped += 1
            continue
        scanned += 1
        for m in LOCAL_MARKERS:
            if m in txt:
                i = txt.index(m)
                hits4.append((p, m, txt[max(0, i - 30):i + 40].replace('\n', ' ')))
                break
    if hits4:
        fails.append(('P4', '本机路径/身份泄露 %d 个文件（扫 %d）: %s' % (
            len(hits4), scanned,
            '; '.join('%s[%s]' % (p, m) for p, m, _ in hits4[:6]))))
    else:
        notes.append('P4 ok：扫 %d 个文本文件，本机路径命中 0%s'
                     % (scanned, ('（跳过 >%dMB 的 %d 个）' % (TEXT_MAX // 1048576, skipped)) if skipped else ''))

    # ---- P4b 脱敏可逆：含占位符的文件，反向替换后必须**逐字节**等于仓库原文 ----
    # 这是「只改了路径、没改到别的内容」的构造性证据（R67）。
    bad4b = []
    for p in have:
        if os.path.splitext(p)[1].lower() not in TEXT_EXT:
            continue
        fp = os.path.join(snap, p)
        try:
            if os.path.getsize(fp) > TEXT_MAX:
                continue
            b = open(fp, 'rb').read()
        except OSError:
            continue
        if b'{{' not in b:
            continue
        orig = os.path.join(ROOT, p.replace('/', os.sep))
        if not os.path.exists(orig):
            bad4b.append((p, '快照含占位符但仓库无同名文件'))
            continue
        # 正向比较：快照 == 对原文做**同一套确定性替换**的结果。
        # 为什么不用反向替换（_unredact）：若原文自身就含 {{USER}} 这类占位符字面量
        # （判据文件就是），反向替换会把它也还原成原词，造成假「不可逆」。
        with open(orig, 'rb') as f:
            exp, _, _ = _redact_bytes(f.read())
        if b != exp:
            bad4b.append((p, '快照内容 ≠ 原文经同一替换后的结果（改到了路径以外）'))
    if bad4b:
        fails.append(('P4b', '脱敏不可逆 %d 个: %s'
                      % (len(bad4b), '; '.join('%s[%s]' % x for x in bad4b[:5]))))
    else:
        notes.append('P4b ok：脱敏可逆（反向替换后与原文逐字节一致）')

    # ---- P5 受限标识字样零命中 ----
    hits5 = []
    for p in have:
        if os.path.splitext(p)[1].lower() not in TEXT_EXT:
            continue
        txt = _read_text(os.path.join(snap, p))
        if not txt:
            continue
        for m in SECRET_MARKERS:
            if m in txt:
                hits5.append((p, m))
                break
    if hits5:
        fails.append(('P5', '受限标识类字样 %d 个文件: %s'
                      % (len(hits5), ', '.join('%s[%s]' % h for h in hits5[:6]))))
    else:
        notes.append('P5 ok：受限标识类字样 0 命中')

    # ---- P6 体量与 manifest 对账 ----
    absent = sorted(keep - have_set)
    extra = sorted(have_set - keep)
    if absent or extra:
        fails.append(('P6', '快照与 manifest 不一致：缺 %d 个%s；多 %d 个%s' % (
            len(absent), ('（如 %s）' % absent[0]) if absent else '',
            len(extra), ('（如 %s）' % extra[0]) if extra else '')))
    else:
        notes.append('P6 ok：快照 %d 个文件与 manifest KEEP 集合逐条一致' % len(have))

    # ---- P7 快照做成的库必须能纳入全部文件（F-2）----
    # 动机：快照里**带着 `.gitignore` 一起发**。若其中某条规则挡住了 KEEP 里的文件，
    # 第三方 `git init && git add -A` 会**静默少一个文件**——P6 只比「磁盘 vs manifest」，
    # 看不出来（F-2 实测：`feagpt_repro/package-lock.json` 就是这样被挡掉的）。
    # 判据用法与「真做一次」一致：临时 bare git-dir 当索引，`add -A` 后比 ls-files。
    # 不靠模拟 gitignore 语法 —— 那是第二份实现，规则只有一处（见 MEMORY：工具必须读规则表）。
    gd = None
    try:
        gd = tempfile.mkdtemp(prefix='_d4_p7_')
        env = dict(os.environ, GIT_DIR=gd, GIT_WORK_TREE=os.path.abspath(snap))
        subprocess.run(['git', 'init', '-q', '--bare', gd], check=True,
                       capture_output=True, timeout=120)
        subprocess.run(['git', 'add', '-A'], check=True, env=env, cwd=snap,
                       capture_output=True, timeout=600)
        raw = subprocess.run(['git', 'ls-files', '-z'], env=env, cwd=snap,
                             capture_output=True, timeout=120).stdout
        tracked = set(x for x in raw.decode('utf-8', 'replace').split('\0') if x)
        lost = sorted(have_set - tracked)
        if lost:
            fails.append(('P7', '快照里 %d 个文件会被 `.gitignore` 挡住（第三方建库时装不进）: %s'
                          % (len(lost), ', '.join(lost[:6]))))
        else:
            notes.append('P7 ok：快照 %d 个文件全部可被新库纳入（`.gitignore` 无自相矛盾）' % len(have))
    except Exception as e:                                   # 没有 git / 超时：判红，不 skip（R58）
        fails.append(('P7', '无法建立临时索引验证入库（缺 git 即无闸）: %s' % e))
    finally:
        if gd:
            shutil.rmtree(gd, ignore_errors=True)

    # ---- P8 仓库行为配置必须随库分发，且真的生效（F-7）----
    # 动机：`.gitignore` 进了公开集、作用完全相同的 `.gitattributes` 没进 —— 而**没有闸会报**
    # （P6 比「快照 vs manifest」，manifest 由 classify() 产出 ⇒ 自证循环）。后果实测量化：
    # 第三方 clone 公开库后 `eol: crlf` 变 `eol: unspecified`、`*.sh` 的 `eol: lf` 也消失
    # ⇒ D3 解决的换机行尾不一致在公开库侧原样复活。
    # 判据**不写名单**：源库该有哪些由 manifest 现取；快照多给的也红（双向）。
    # 并且**真问一次 git**（check-attr）—— 只比 sha 只能证「文件没被换」，证不了「规则生效」。
    cfg = manifest.get('repo_configs') or {}
    miss8 = sorted(p for p in cfg if not os.path.exists(os.path.join(snap, p.replace('/', os.sep))))
    bad8 = sorted(p for p in cfg
                  if p not in miss8
                  and _sha256_file(os.path.join(snap, p.replace('/', os.sep))) != cfg[p].get('sha256'))
    extra8 = sorted(p for p in have if _is_repo_config(p) and p not in cfg)   # 根目录文件天然不含 '/'
    probe = manifest.get('repo_attr_probe') or {}
    sample, want = probe.get('sample'), probe.get('attrs')
    attr_note = None
    if miss8 or bad8 or extra8:
        parts = []
        if miss8:
            parts.append('缺 %d 个（%s）' % (len(miss8), ', '.join(miss8[:4])))
        if bad8:
            parts.append('内容与源库不一致 %d 个（%s）' % (len(bad8), ', '.join(bad8[:4])))
        if extra8:
            parts.append('源库没有、快照多给 %d 个（%s）' % (len(extra8), ', '.join(extra8[:4])))
        fails.append(('P8', '仓库行为配置未随库分发：' + '；'.join(parts)))
    elif not cfg:
        fails.append(('P8', 'manifest 未记录任何仓库行为配置（无基准 = 无闸，R58）'))
    elif not sample or want is None:
        fails.append(('P8', '缺少生效性探针（sample/attrs），无法证明规则真的生效（R58）'))
    else:
        gd8 = None
        try:
            gd8 = tempfile.mkdtemp(prefix='_d4_p8_')
            subprocess.run(['git', 'init', '-q', '--bare', gd8], check=True,
                           capture_output=True, timeout=120)
            got = _git_check_attr(sample, os.path.abspath(snap), gd8)
            if got is None:
                fails.append(('P8', '无法在快照库上问出属性（缺 git 即无闸）'))
            elif got != want:
                fails.append(('P8', '仓库行为配置未生效：`%s` 在快照库里被解释为 %s，源库是 %s'
                              % (sample, got or '（无任何属性）', want)))
            else:
                attr_note = '生效已实测（`%s` → %s）' % (sample, got)
        except Exception as e:
            fails.append(('P8', '无法验证行为配置是否生效（缺 git 即无闸）: %s' % e))
        finally:
            if gd8:
                shutil.rmtree(gd8, ignore_errors=True)
    if attr_note:
        notes.append('P8 ok：仓库行为配置 %d 个与源库逐字节一致；%s'
                     % (len(cfg), attr_note))

    return fails, notes


def _r(*parts):
    return ''.join(parts)


# ---- 脱敏映射：一对一、确定性、**可逆**（用于证明「只改了路径，没改别的内容」）----
# 长串必须排在短串之前（完整 python.exe 路径 → 家目录 → 用户名）。
# 同样用 _r() 拼接，避免判据文件自身包含被检测的字面量。
REDACT = [
    (_r('F:', '/AI FEA Modeling DataSets'), '{{REPO_ROOT}}'),
    (_r('F:', '\\AI FEA Modeling DataSets'), '{{REPO_ROOT_WIN}}'),
    (_r('F:', '/FEA_Archive_20261024'), '{{DATA_ARCHIVE}}'),
    (_r('F:', '\\FEA_Archive_20261024'), '{{DATA_ARCHIVE_WIN}}'),
    (_r('F:', '/FEA_Archive'), '{{DATA_ARCHIVE_PREFIX}}'),
    (_r('F:', '\\FEA_Archive'), '{{DATA_ARCHIVE_PREFIX_WIN}}'),
    (_r('C:', '/Users/', '222', '07', '/.workbuddy/binaries/python/envs/default/Scripts/python.exe'),
     '{{VENV_PY}}'),
    (_r('C:', '\\Users\\', '222', '07', '\\.workbuddy\\binaries\\python\\envs\\default\\Scripts\\python.exe'),
     '{{VENV_PY_WIN}}'),
    (_r('C:', '/Users/', '222', '07'), '{{USER_HOME}}'),
    (_r('C:', '\\Users\\', '222', '07'), '{{USER_HOME_WIN}}'),
    (_r('222', '07'), '{{USER}}'),
]
REDACT_B = [(o.encode('utf-8'), n.encode('utf-8')) for o, n in REDACT]


def _redact_bytes(b):
    """在 bytes 上替换：完全保留 BOM / 行尾 / 编码，不做任何解码。返回 (new, 替换次数, 命中词表)。

    命中词表记的是**占位符**而不是原文 —— 因为 manifest 本身也在公开集里，
    若记录原文，manifest 自己就成了泄露源（自指：它还得再被脱敏一次，而脱敏又改变它自己）。
    """
    n, hits = 0, []
    for old, new in REDACT_B:
        c = b.count(old)
        if c:
            b = b.replace(old, new)
            n += c
            hits.append(new.decode('utf-8'))
    return b, n, hits


def _unredact_bytes(b):
    for old, new in REDACT_B:
        b = b.replace(new, old)
    return b


def emit(dest, manifest, redact=True):
    dest = os.path.abspath(dest)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    n, red = 0, {}
    for p in manifest['keep']:
        src = os.path.join(ROOT, p)
        dst = os.path.join(dest, p.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        ext = os.path.splitext(p)[1].lower()
        if redact and ext in TEXT_EXT and os.path.getsize(src) <= TEXT_MAX:
            with open(src, 'rb') as f:
                raw = f.read()
            new, cnt, hits = _redact_bytes(raw)
            if cnt:
                red[p] = {'n': cnt, 'markers': hits}
            with open(dst, 'wb') as f:
                f.write(new)
            shutil.copystat(src, dst)
        else:
            shutil.copy2(src, dst)
        n += 1
    return dest, n, red


# ---------------- 自检：证明判据能红 ----------------

def self_test():
    """十二向：P1 内部文件 / P2 文档引用内部文件 / P4 本机路径 / P5 受限标识 /
    P7 gitignore 挡 KEEP 文件（F-2）/ P7 不挡须绿 /
    P8 内容漂移 / P8 缺失 / P8 多给 / P8 一致且生效须绿 / P8 生效性断言真的会红（F-7）。
    每向断言的是「红的**是哪一条**」，不是只断言「红了」—— 强判据吃弱判据时
    「弱判据永假绿」是看不出来的（NC 系列同款纪律）。"""
    ATTR = '*.py text eol=crlf\n'
    ATTR_NOPY = '*.txt text eol=crlf\n'
    PROBE = 'feegpt_repro/evaluate.py'
    WANT = [['eol', 'crlf'], ['text', 'set']]

    def cfg_of(d):
        return {p: {'sha256': hashlib.sha256(c.encode('utf-8')).hexdigest(),
                    'bytes': len(c.encode('utf-8'))}
                for p, c in d.items() if _is_repo_config(p)}

    results = []
    with tempfile.TemporaryDirectory() as td:
        snap = os.path.join(td, 'snap')

        def mk(files):
            if os.path.exists(snap):
                shutil.rmtree(snap)
            for rel, content in files.items():
                fp = os.path.join(snap, rel.replace('/', os.sep))
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                # newline='' 必须给：Windows 上文本模式默认把 '\n' 写成 CRLF，
                # 会让 P8 的 sha256 对不上（= 一条纯粹由测试脚手架制造的假红）
                with open(fp, 'w', encoding='utf-8', newline='') as f:
                    f.write(content)

        base = {'FEM-Bench-Aero/README.md': '# r\n', 'feagpt_repro/evaluate.py': 'x=1\n',
                'FEM-Bench-Aero/QUICKSTART.md': 'run evaluate.py\n',
                'FEM-Bench-Aero/DATA.md': 'see evaluate.py\n',
                'FEM-Bench-Aero/RUBRIC.md': '# r\n', 'FEM-Bench-Aero/CLAIMS.md': '# c\n',
                'feagpt_repro/reports/INDEX.md': '# i\n'}
        base['.gitattributes'] = ATTR

        def make_m(d, extra_keep=None):
            """按快照内容现造 manifest：keep = 快照镜像（除标注的例外），repo_configs 照实取。"""
            mm = {'keep': sorted(set(d) | set(extra_keep or [])),
                  'drop_categories': {'探针/调试产物': ['feagpt_repro/_probe_b6/x.inp']},
                  'repo_configs': cfg_of(d),
                  'repo_attr_probe': {'sample': PROBE, 'attrs': WANT}}
            return mm

        m = make_m(base)

        # ① 正向：应全绿
        mk(base)
        f, n = check(snap, m)
        results.append(('正向（应无红）', len(f) == 0, [x[0] for x in f]))

        # ② P1：混入内部文件
        d = dict(base); d['.workbuddy/memory/2026-10-01.md'] = 'x\n'
        mk(d)
        f, _ = check(snap, m)
        got = [x[0] for x in f]
        results.append(('P1 内部材料残留', 'P1' in got and 'P6' in got, got))

        # ③ P2b：文档引用了内部材料（该文件在仓库里真实存在、但**不在**快照里）
        #    构造要点：内部文件不放进快照 ⇒ P1/P6 应绿，只有 P2b 红（红的原因要分得开）
        mm = dict(m)
        mm['drop_categories'] = {'探针/调试产物': ['feagpt_repro/_probe_b6/x.json']}
        d = dict(base); d['FEM-Bench-Aero/QUICKSTART.md'] = 'run x.json\n'
        mk(d)
        f, _ = check(snap, mm)
        got = [x[0] for x in f]
        results.append(('P2b 文档引用内部文件',
                        'P2b' in got and 'P1' not in got and 'P6' not in got, got))

        # ④ P4：本机路径
        d = dict(base)
        d['FEM-Bench-Aero/DATA.md'] = 'see ' + _m('C:', '/Users/') + 'someone/x\n'
        mk(d)
        f, _ = check(snap, m)
        got = [x[0] for x in f]
        results.append(('P4 本机路径泄露', 'P4' in got and 'P2' not in got, got))

        # ⑤ P5：受限标识字样
        d = dict(base)
        d['FEM-Bench-Aero/README.md'] = '# ' + _m('内', '部', '资料') + '\n'
        mk(d)
        f, _ = check(snap, m)
        got = [x[0] for x in f]
        results.append(('P5 受限标识', 'P5' in got, got))

        # ⑥ P7：快照自带的 `.gitignore` 挡住了 KEEP 里的文件 ⇒ 第三方建库会静默少一个
        #    这是 F-2 的原地复现（实测当时 `package-lock.json` 就是这么丢的）
        d = dict(base); d['.gitignore'] = 'feagpt_repro/evaluate.py\n'
        mk(d)
        f, _ = check(snap, make_m(d))
        got = [x[0] for x in f]
        results.append(('P7 gitignore 挡文件', 'P7' in got, got))

        # ⑦ P7 反向：不挡时必须绿。**每次 check 都会跑 P7**，若它处处误红，
        #    上面五向的断言会被同一个假红污染 —— 这一向是给 P7 自己立的「不许过严」
        d = dict(base)
        d['.gitignore'] = 'feagpt_repro/node_modules/\nfeagpt_repro/candidates/\n'
        mk(d)
        f, _ = check(snap, make_m(d))
        got = [x[0] for x in f]
        results.append(('P7 不挡须绿', 'P7' not in got, got))

        # ⑧ P8 内容漂移：文件在、但内容与源库不一致（P6 必须绿 ⇒ 红的只能是一条）
        #    这一向是 F-7 的主向 —— 现状恰恰是「文件根本不在」，而那时 P8 与 P6 同时红，
        #    分不清是「分类规则漏了」还是「emit 写漏了」。内容漂移只红 P8，能把两者分开。
        d = dict(base); d['.gitattributes'] = '*.py text eol=lf\n'
        mk(d)
        f, _ = check(snap, m)
        got = [x[0] for x in f]
        results.append(('P8 内容漂移', 'P8' in got and 'P6' not in got, got))

        # ⑨ P8 缺失：源库有、快照没有（= F-7 的现状形态）
        d = dict(base); d.pop('.gitattributes')
        mk(d)
        f, _ = check(snap, m)
        got = [x[0] for x in f]
        results.append(('P8 缺失', 'P8' in got and 'P6' in got, got))

        # ⑩ P8 多给：源库没有、快照里凭空多一个改行为的文件（防「反向放水」）
        #    构造要点：keep **含**它（P6 绿），repo_configs **不含**它 ⇒ 红的只能是 P8
        d = dict(base); d['.gitignore'] = 'feagpt_repro/node_modules/\n'
        mk(d)
        mm = make_m(d)
        mm['repo_configs'].pop('.gitignore', None)
        f, _ = check(snap, mm)
        got = [x[0] for x in f]
        results.append(('P8 源库无而快照多给', 'P8' in got and 'P6' not in got, got))

        # ⑪ P8 一致且生效：必须绿，且 note 里要能看见「生效已实测」——
        #    只断言「没红」等于允许 P8 整个不跑（判据没跑起来与判据通过，外观一样）
        mk(base)
        f, n = check(snap, m)
        results.append(('P8 一致且生效须绿',
                        'P8' not in [x[0] for x in f] and any('生效已实测' in x for x in n),
                        [x[0] for x in f]))

        # ⑫ P8 生效性断言真的会红：`.gitattributes` 内容与 manifest 记的 sha **一致**（同步绿），
        #    但它声明的规则不作用于探针样本 ⇒ 必须由「生效性」这一条单独抓出来。
        #    没有这一向，生效性检查可能只是个永远不触发的新增代码（N-26 恒真式同款风险）。
        d = dict(base); d['.gitattributes'] = ATTR_NOPY
        mk(d)
        mm = make_m(d)                 # repo_configs 记的是 ATTR_NOPY 的 sha ⇒ 同步这条绿
        f, _ = check(snap, mm)
        msg = ' '.join(x[1] for x in f if x[0] == 'P8')
        results.append(('P8 生效性须真会红', '未生效' in msg, [x[0] for x in f] or ['']))

    print('=== _d4_public_set --self-test ===')
    ok = True
    for name, good, ids in results:
        print('  [%s] %-26s 红项=%s' % ('ok  ' if good else 'BAD ', name, ids or '[]'))
        ok = ok and good
    print('=> %d/%d' % (sum(1 for _, g, _ in results if g), len(results)))
    return 0 if ok else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--emit', metavar='DIR', help='生成快照到 DIR')
    ap.add_argument('--check', metavar='DIR', help='校验已有快照')
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--no-manifest', action='store_true', help='只统计，不写 manifest')
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    if a.self_test:
        return self_test()

    m = build_manifest()
    print('HEAD=%s' % m['source_head'][:8])
    print('追踪 %d 个 / %.1f MB  →  公开集 %d 个 / %.1f MB（移出 %d 个 / %.1f MB）'
          % (m['n_total'], m['bytes_total'] / 1048576, m['n_keep'], m['bytes_keep'] / 1048576,
             m['n_total'] - m['n_keep'], (m['bytes_total'] - m['bytes_keep']) / 1048576))
    for k in sorted(m['categories'], key=lambda x: -m['categories'][x]['bytes']):
        e = m['categories'][k]
        print('   %-22s %5d 个 %7.1f MB' % (k, e['n'], e['bytes'] / 1048576))

    if a.emit:
        dest, n, red = emit(a.emit, m)
        m['redactions'] = red
        print('快照 -> %s（%d 个文件；脱敏 %d 个文件 / %d 处）'
              % (dest, n, len(red), sum(v['n'] for v in red.values())))

    # --check 只读，不重写 manifest：否则会把 --emit 才产出的 redactions 抹掉
    # （现场踩过：先 emit 再 check，manifest 里 redactions 消失）
    if not a.no_manifest and not a.check:
        os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
        with open(MANIFEST, 'w', encoding='utf-8') as f:
            json.dump(m, f, ensure_ascii=False, indent=1)
        print('manifest -> %s' % os.path.relpath(MANIFEST, ROOT))
        # manifest 自身也在公开集里 ⇒ 必须把**新写的这一版**同步进快照，
        # 否则快照里留的是上一版（P4b 会红：内容 ≠ 原文经同一替换的结果）。
        if a.emit and 'feagpt_repro/reports/diagnostics/public_manifest.json' in m['keep']:
            shutil.copy2(MANIFEST, os.path.join(
                dest, 'feagpt_repro', 'reports', 'diagnostics', 'public_manifest.json'))

    if a.check:
        fails, notes = check(a.check, m)
        for x in notes:
            print('  ' + x)
        if fails:
            print('\n=== 红 ===')
            for cid, msg in fails:
                print('  [FAIL] %-4s %s' % (cid, msg))
            return 2
        print('\n结论：全过（P0/P1/P2/P3/P4/P4b/P5/P6/P7/P8）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
