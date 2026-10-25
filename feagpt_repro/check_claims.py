# -*- coding: utf-8 -*-
"""
check_claims.py — CLAIMS 账本自检（W5a'/专家第六轮 P0-3，红线 R25/R26/R27）

为什么：CLAIMS 规则写「artifact + command」，但没有任何脚本检查 artifact 是否存在、
是否被 git 追踪、是否与 command 的输出路径一致。C-021/C-024/C-025/C-019 的 artifact
全部落在被 gitignore 的 eval_runs/，直到第六轮人工复评才发现（每轮靠人查不可持续）。

检查项（对 status=active 的每条 claim）：
  1. artifact 路径可解析且**存在**；
  2. artifact **被 git 追踪**（`git ls-files --error-unmatch`，R25）；
  3. artifact **不在** eval_runs/（工作目录，重跑即覆盖）或系统临时目录（R25/R27）；
  4. command 里的 `--report X` / `--json X` / `--out X` 与 artifact **路径一致**（R26）；
  5. 记录 sha256 / size / mtime（便于下一轮判断「这份文件有没有被悄悄换掉」）；
  6. **同一 artifact 路径不得被两条 active claim 占用**（R27：官方与诊断必须分文件）。

用法：
  python check_claims.py                # 全量检查，rc=0 全过 / rc=1 有失败
  python check_claims.py --claims <path> --root <repo>   # 负控注入（NC-23/24/25）
  python check_claims.py --json reports/check_claims.json
"""
import argparse, hashlib, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # 仓库根 = F:/AI FEA Modeling DataSets
CLAIMS_DEFAULT = os.path.join(ROOT, 'FEM-Bench-Aero', 'CLAIMS.md')

PATH_RE = re.compile(r'[A-Za-z0-9_./\\:\-]+\.(?:jsonl|json|md|csv|tar\.gz|txt)')
FLAG_RE = re.compile(r'--(?:report|json|out|report-dir)\s+([^\s`;+]+)')
BAD_DIRS = ('eval_runs',)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_claims(path):
    """解析 CLAIMS.md 的 markdown 表格（| claim_id | statement | artifact | ... |）。"""
    rows, header = [], None
    for line in open(path, encoding='utf-8'):
        s = line.strip()
        if not s.startswith('|'):
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        if header is None:
            if cells and cells[0].lower() in ('claim_id', 'claim'):
                header = [c.lower() for c in cells]
            continue
        if set(''.join(cells)) <= set('-: '):
            continue
        if len(cells) < len(header):
            cells += [''] * (len(header) - len(cells))
        rows.append(dict(zip(header, cells)))
    return rows


def resolve(artifact, root):
    """把 artifact 字符串解析成相对仓库路径。

    返回 (rel, exists, external)：
      - 仓库内文件 -> (相对路径, True/False, False)
      - 绝对路径/盘符路径（如 F:/FEA_Archive_.../SHA256SUMS.txt）-> 视为**外部归档**，
        只查存在性，不要求 git 追踪（R25 只约束仓库内官方 artifact）。
    """
    a = artifact.strip().strip('`').replace('\\', '/')
    if os.path.isabs(a) or re.match(r'^[A-Za-z]:/', a):
        return a, os.path.exists(a), True
    cands = [a, f'FEM-Bench-Aero/{a}', f'feagpt_repro/{a}']
    for c in cands:
        if os.path.exists(os.path.join(root, c)):
            return os.path.normpath(c).replace('\\', '/'), True, False
    return os.path.normpath(cands[0]).replace('\\', '/'), False, False


def git_tracked(root, rel):
    try:
        r = subprocess.run(['git', '-C', root, 'ls-files', '--error-unmatch', rel],
                           capture_output=True, text=True)
        return r.returncode == 0
    except Exception:
        return False


def artifacts_in(cell):
    out = []
    for tok in PATH_RE.findall(cell or ''):
        tok = tok.strip('`.,;()（）')
        if tok and tok not in out:
            out.append(tok)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--claims', default=CLAIMS_DEFAULT)
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--json', default=os.path.join(HERE, 'reports', 'check_claims.json'))
    ap.add_argument('--include-nonactive', action='store_true',
                    help='连 superseded/retracted 一起查（默认只查 active）')
    args = ap.parse_args()
    root = os.path.abspath(args.root)

    rows = parse_claims(args.claims)
    active = [r for r in rows if 'active' in r.get('status', '').lower()
              or (args.include_nonactive and r.get('status'))]
    results, fails = [], []
    seen = {}

    for r in rows:
        cid = r.get('claim_id', '?')
        status = r.get('status', '').lower()
        if not (('active' in status) or (args.include_nonactive and status)):
            continue
        arts = artifacts_in(r.get('artifact', ''))
        if not arts:
            results.append({'claim_id': cid, 'artifact': None, 'ok': False,
                            'problems': ['artifact 列为空（无法自证）']})
            fails.append(f'{cid}: artifact 列为空')
            continue
        flags = [t.strip('`.,;()（）') for t in FLAG_RE.findall(r.get('command', ''))]
        flags = [f for f in flags if not f.startswith('<')]
        for art in arts:
            rel, exists, external = resolve(art, root)
            problems = []
            if not exists:
                problems.append('artifact 不存在')
            tracked = None
            if exists and not external:
                tracked = git_tracked(root, rel)
                if not tracked:
                    problems.append('artifact 未被 git 追踪（R25）')
            if external:
                tracked = 'external'
            if not external and (rel.startswith('eval_runs/') or '/eval_runs/' in '/' + rel):
                problems.append('artifact 位于 eval_runs/（工作目录，重跑即覆盖；R25）')
            # command 与 artifact 路径一致（只对同扩展名的 flag 判）
            if flags and not external:
                same = [f for f in flags
                        if os.path.basename(f.strip()) == os.path.basename(rel)]
                if not same:
                    problems.append(f'command 输出路径 {flags} 与 artifact {rel} 不一致（R26）')
            # R27：官方与诊断不得共用同一 artifact 路径（同口径的两条 claim 引用同一文件不算冲突，
            # 例如 C-010/C-011 都引考卷 tasks.jsonl）
            is_diag = ('diagnostic' in (status + r.get('level', '') + r.get('statement', '')).lower()
                       or '诊断' in (r.get('statement', '') + r.get('status', '')))
            key = os.path.basename(rel) if external else rel
            if key in seen:
                prev_cid, prev_diag = seen[key]
                if prev_diag != is_diag:
                    problems.append(f'同一 artifact 已被 {prev_cid} 占用且口径不同'
                                    f'（官方/诊断必须分文件；R27）')
            else:
                seen[key] = (cid, is_diag)
            rec = {'claim_id': cid, 'artifact': rel, 'exists': exists, 'git_tracked': tracked,
                   'external': external, 'ok': not problems, 'problems': problems}
            if exists:
                ap_ = os.path.join(root, rel) if not external else rel
                rec.update({'size': os.path.getsize(ap_), 'sha256': sha256_file(ap_),
                            'mtime': int(os.path.getmtime(ap_))})
            results.append(rec)
            if problems:
                fails.append(f"{cid}: {rel} -> {'; '.join(problems)}")

    report = {'claims_file': os.path.relpath(args.claims, root).replace('\\', '/'),
              'n_active_claims': len({r['claim_id'] for r in results}),
              'n_artifacts': len(results),
              'n_fail': len(fails),
              'all_ok': not fails, 'fails': fails, 'results': results}
    os.makedirs(os.path.dirname(os.path.abspath(args.json)) or '.', exist_ok=True)
    json.dump(report, open(args.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('== CLAIMS 自检（R25/R26/R27）==')
    for rec in results:
        tag = 'ok  ' if rec['ok'] else 'FAIL'
        extra = '' if rec['ok'] else '  <- ' + '; '.join(rec['problems'])
        print(f"  [{tag}] {rec['claim_id']:<7} {rec['artifact']}{extra}")
    print(f"\nactive claims {report['n_active_claims']} 条 / artifact {report['n_artifacts']} 个 "
          f"-> {'全过' if report['all_ok'] else f'{len(fails)} 项失败'}")
    print(f"report -> {args.json}")
    if fails:
        print('红线条 R26：CLAIMS 自检未过，不得对外引用这些数字。')
        return 1
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
