# -*- coding: utf-8 -*-
"""
msr_l3.py — W4d 全链 MSR（红线 R14：skip_solve 不得称基线；W4e 按专家第四轮 P0-2 修正）

对 candidates_l3_v2 中产出 spec 的候选逐条走 evaluate_one 全链
（契约闸 → run_pipeline(ccx) → 关1 网格 → 关4 语义 → fidelity_disp → spec_fidelity）。
ccx 串行（绝不并行，环境铁律）。输出合并进 baseline_scorecard_L3.json 的 msr 节。

W4e 修正（专家第四轮 P0-2 / 红线 R16）：
  1. 依赖预检：gmsh/numpy 缺失 ⇒ 环境错误退出（rc=2），绝不把候选记 FAIL；
  2. 失败分层 env / contract / model / solver（按 stderr + 退出路径归类），
     环境失败单独计数、不进 MSR 分母；
  3. 澄清题（无 spec 期望）不计 MSR 分母，分母 = spec-required 任务；
  4. --python 指定子进程解释器（默认 venv，gmsh 在 envs/default）。

W5a'（专家第六轮 P0-1/P0-2/P1-3，红线 R25/R27）：
  - --tasks / --report / --report-dir 全部参数化（原先硬编码 tasks/tasks.jsonl 与
    eval_runs/baseline_scorecard_L3.json ⇒ v4 MSR 无法复现）；
  - 默认报告写 reports/（入库）；msr 节记录考卷 provenance（路径 + sha256）。
"""
import json, os, sys, hashlib, collections, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluate import evaluate_one, load_tasks, RUNS, require_dataset

REPORT_DIR = os.path.join(HERE, 'reports')
REPORT = os.path.join(REPORT_DIR, 'baseline_scorecard_L3.json')

VENV_PY = 'C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe'


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def classify_failure(result):
    """失败分层（专家 P0-2：env / contract / model / solver）。"""
    g = result.get('gates', {})
    pipe = g.get('pipeline', {})
    detail = (pipe.get('detail') or '') + ' ' + (pipe.get('actual') or '')
    if 'contract' in pipe.get('field', '') or 'contract' in detail[:120]:
        return 'contract'
    if 'ModuleNotFoundError' in detail or 'ImportError' in detail:
        return 'env'
    if 'TypeError' in detail or 'ValueError' in detail or 'FEASpec' in detail \
            or 'must be' in detail:
        return 'model'      # spec 被契约/族校验拒收
    if pipe.get('actual', '').startswith('rc='):
        return 'solver'
    return 'model'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidates', default=os.path.join(HERE, 'candidates_l3_v3'),
                    help='候选目录（W5a/R22 教训：目录不得硬编码，改名必须改参数）')
    ap.add_argument('--tasks', default=os.path.join(HERE, 'tasks', 'tasks.jsonl'),
                    help='考卷（W5a\'：v4 复现传 reports/papers/tasks_v4.jsonl）')
    ap.add_argument('--report-dir', default=REPORT_DIR, help='报告目录（默认 reports/，入库）')
    ap.add_argument('--report', default=None,
                    help='要合并 msr_section 的成绩单路径（默认 <report-dir>/baseline_scorecard_L3.json）')
    ap.add_argument('--reuse', default=None,
                    help='W5a\'：复用某份既有成绩单的 per_task 求解结果，只按新考卷**重算分母**'
                         '（求解与考卷无关；用于 v4 分母口径复现，不起求解器）')
    args = ap.parse_args()
    err = require_dataset()          # W5a'：缺 gold 数据集必须硬报错（否则全链会集体假 FAIL）
    if err:
        print('[dataset] ' + err)
        return 2
    cand_dir = args.candidates
    tasks_path = args.tasks
    report_path = args.report or os.path.join(args.report_dir, 'baseline_scorecard_L3.json')
    print(f'[msr_l3] candidates={os.path.basename(cand_dir)}  tasks={tasks_path}')
    print(f'[msr_l3] report={report_path}')

    # ---- R16：依赖预检（本进程 gmsh/numpy 可导入，否则环境错误退出）----
    missing = []
    for mod in ('gmsh', 'numpy'):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print(f'环境错误：缺少依赖 {missing}。全链 MSR 不能在缺 gmsh 的解释器下运行'
              f'（环境失败不得计为模型失败，红线 R16）。'
              f'用 venv 解释器重跑："{VENV_PY}" msr_l3.py')
        return 2

    tasks = {t['task_id']: t for t in load_tasks(tasks_path)
             if t['input_level'] == 'L3'}
    cands = {}
    for fn in sorted(os.listdir(cand_dir)):
        if fn.endswith('.json'):
            c = json.load(open(os.path.join(cand_dir, fn), encoding='utf-8'))
            cands[c['task_id']] = c

    reuse_map = {}
    if args.reuse:
        prev = json.load(open(args.reuse, encoding='utf-8')).get('msr_section', {})
        reuse_map = {r['task_id']: r for r in prev.get('per_task', [])}
        print(f"[msr_l3] REUSE 模式：分母重算自 {args.reuse}（{len(reuse_map)} 条既有结果，不起求解器）")

    rows, n_env_skip = [], 0
    for tid in sorted(tasks):
        t = tasks[tid]
        c = cands.get(tid) or {}
        # W5a（专家第五轮 P0-3/R23）：澄清题一律不计 MSR 分母——即使模型静默编造产出了 spec
        # （编造已由 FPR 单独计数，双重计数违反 R23；分母口径与 RUBRIC §4 一致）
        if t.get('expected_clarifications'):
            rows.append({'task_id': tid, 'msr_pass': None, 'denominator': False,
                         'reason': 'clarify task (expected_clarifications) — R23: 编造归 FPR，不入 MSR'})
            print(f"  [--] {tid}: clarify task -> 不进分母")
            continue
        if not c.get('spec'):
            # 未收敛/无输出候选：无 spec 期望，不计 MSR 分母
            rows.append({'task_id': tid, 'msr_pass': None, 'denominator': False,
                         'reason': 'no spec (unresolved/no-output)'})
            print(f"  [--] {tid}: no spec -> 不进分母")
            continue
        if reuse_map:
            pr = reuse_map.get(tid)
            if not pr or pr.get('msr_pass') is None:
                rows.append({'task_id': tid, 'msr_pass': None, 'denominator': False,
                             'reason': 'not-run in reuse source（该口径下无求解结果，不得计入）'})
                print(f"  [--] {tid}: reuse 源里无求解结果 -> 不进分母")
                continue
            row = dict(pr)
            row['denominator'] = True
            rows.append(row)
            print(f"  [{'ok' if row['msr_pass'] else 'FAIL'}] {tid}: (reuse) msr_pass={row['msr_pass']}")
            continue

        try:
            r = evaluate_one(t, os.path.join(cand_dir, tid + '.json'), skip_solve=False,
                             timeout=1800)
        except Exception as e:
            msg = str(e)
            cat = 'env' if ('gmsh' in msg or 'ModuleNotFound' in msg) else 'exception'
            if cat == 'env':
                n_env_skip += 1
            rows.append({'task_id': tid, 'msr_pass': False, 'denominator': cat != 'env',
                         'failure_class': cat, 'reason': f'exception: {msg[:200]}'})
            print(f"  [!!] {tid}: {cat} {msg[:120]}")
            continue
        gates = {k: bool(v.get('pass')) for k, v in r['gates'].items()}
        ok = bool(r.get('overall_pass'))
        row = {'task_id': tid, 'msr_pass': ok, 'denominator': True, 'gates': gates,
               'pipeline_rc': r.get('pipeline_rc'),
               'wall_seconds': r.get('wall_seconds'),
               'fidelity_dev_pct': r.get('fidelity_disp_dev_pct')}
        if not ok:
            row['failure_class'] = classify_failure(r)
            row['failure_detail'] = (r['gates'].get('pipeline', {}).get('detail')
                                     or r['gates'].get('pipeline', {}).get('actual') or '')[:300]
        rows.append(row)
        bad = [k for k, v in gates.items() if not v]
        print(f"  [{'ok' if ok else 'FAIL'}] {tid}: gates={gates} "
              f"fidelity={r.get('fidelity_disp_dev_pct','n/a')}% wall={r.get('wall_seconds')}s"
              + (f" bad={bad} class={row.get('failure_class')}" if bad else ''))

    den_rows = [r for r in rows if r.get('denominator')]
    n, p = len(den_rows), sum(1 for r in den_rows if r['msr_pass'])
    env_fails = [r for r in rows if r.get('failure_class') == 'env']
    if env_fails:
        print(f'环境失败 {len(env_fails)} 条——不进 MSR 分母（R16），请检查解释器后重跑。')

    # ★★ W5c-6g（专家第十轮 §3.3 / R52）：分母构成**四类显式拆开**并加和闭合。
    #   旧版 `n_clarify_excluded = sum(1 for r in rows if not r.get('denominator'))`
    #   把「合法澄清」和「未收敛/无输出」混成同一个数：
    #     C-029 = 4（4 条纯澄清，0 未收敛）
    #     C-031 = 5（4 条澄清 + 1 条 `cfrp090s` 3 轮无输出）
    #   两个数字**不是同一类**，被并排列进对比表就会被读成「同口径」。
    #   ⇒ 按 reason / failure_class 显式分流，并把闭合关系落盘 + 断言（不闭合直接报错退出）。
    #   注意口径层次（R52 原文把两层混写了，这里按两层实现）：
    #     层A（准入）：n_tasks_total = n_counted + clarify + unresolved + notrun + env
    #     层B（原始分母内部）：n_counted = n_solver_excluded + n_counted_excl_solver
    #   即 solver 失败**仍在**原始分母里（对模型是失败），只是「剔除 solver 口径」把它们拿掉；
    #   所以 n_solver_excluded 不是层A 的排除项，不能和层A 的项相加。
    def _excl_class(r):
        if r.get('denominator'):
            return None
        if r.get('failure_class') == 'env':
            return 'env'
        rs = (r.get('reason') or '')
        if rs.startswith('clarify'):
            return 'clarify'
        if 'no spec' in rs:
            return 'unresolved'
        if 'not-run' in rs:
            return 'notrun'
        return 'unknown'
    _excl = collections.defaultdict(list)
    for r in rows:
        k = _excl_class(r)
        if k:
            _excl[k].append(r['task_id'])
    unresolved_ids = _excl['unresolved']
    n_unresolved = len(unresolved_ids)

    def _denom_audit(ids=None):
        """给定任务集（None = 全部 55/165 条）的分母构成 + 闭合断言。"""
        pool = rows if ids is None else [r for r in rows if r['task_id'] in set(ids)]
        cnt = [r for r in pool if r.get('denominator')]
        ex = collections.Counter(_excl_class(r) for r in pool if not r.get('denominator'))
        sol = [r for r in cnt if not r['msr_pass'] and r.get('failure_class') == 'solver']
        rec = {'n_tasks_total': len(pool),
               'n_counted': len(cnt),
               'n_clarify_excluded': ex.get('clarify', 0),
               'n_unresolved_excluded': ex.get('unresolved', 0),
               'n_notrun_excluded': ex.get('notrun', 0),
               'n_env_excluded': ex.get('env', 0),
               'n_unknown_excluded': ex.get('unknown', 0),
               'n_solver_excluded': len(sol),
               'n_counted_excl_solver': len(cnt) - len(sol),
               'unresolved_task_ids': [r['task_id'] for r in pool
                                       if _excl_class(r) == 'unresolved'],
               'clarify_task_ids': [r['task_id'] for r in pool
                                    if _excl_class(r) == 'clarify']}
        rec['closure_ok'] = (rec['n_tasks_total'] ==
                             rec['n_counted'] + rec['n_clarify_excluded'] +
                             rec['n_unresolved_excluded'] + rec['n_notrun_excluded'] +
                             rec['n_env_excluded'] + rec['n_unknown_excluded'])
        rec['closure_solver_ok'] = (rec['n_counted'] ==
                                    rec['n_solver_excluded'] + rec['n_counted_excl_solver'])
        rec['closure'] = (f"{rec['n_tasks_total']} = counted {rec['n_counted']} + clarify "
                          f"{rec['n_clarify_excluded']} + unresolved {rec['n_unresolved_excluded']} + "
                          f"notrun {rec['n_notrun_excluded']} + env {rec['n_env_excluded']} + "
                          f"unknown {rec['n_unknown_excluded']}；且 counted {rec['n_counted']} = solver "
                          f"{rec['n_solver_excluded']} + counted_excl_solver "
                          f"{rec['n_counted_excl_solver']}")
        return rec

    # W5a（专家第五轮 P1-1/P1-2）：exam/dev MSR 汇总落盘——不再手算；by_split 全指标
    # W5c（R36）：split 取值由数据推（v6c 新增 interpolation_test），不再硬编码 4 个键
    by_split = {}
    for sp in sorted({tasks[r['task_id']]['split_v2'] for r in den_rows}):
        ids = [r['task_id'] for r in den_rows if tasks[r['task_id']]['split_v2'] == sp]
        pp = sum(1 for tid in ids if next(r for r in den_rows if r['task_id'] == tid)['msr_pass'])
        by_split[sp] = {'msr': f'{pp}/{len(ids)}', 'pass': pp, 'n': len(ids)}
    # W5b-4 修：exam 口径必须跟考卷的 exam_stratum（v6b 三栏 = boundary+extrap+interp 共 25 条）；
    # 老考卷（v4/v5）无 exam_stratum ⇒ 回退 split_v2 双栏，数字保持不变。
    # 原实现硬编码 exam_sp 会把内插 6 条算进 dev，导致 exam_msr 报成 x/17（错）而不是 x/21。
    has_stratum = any(t.get('exam_stratum') for t in tasks.values())

    def _is_exam(t):
        if has_stratum:
            return bool(t.get('exam_stratum'))
        return t.get('split_v2') in ('boundary_holdout', 'extrapolation_test')

    exam_ids = [r['task_id'] for r in den_rows if _is_exam(tasks[r['task_id']])]
    exam_p = sum(1 for tid in exam_ids if next(r for r in den_rows if r['task_id'] == tid)['msr_pass'])
    dev_ids = [r['task_id'] for r in den_rows if not _is_exam(tasks[r['task_id']])]
    dev_p = sum(1 for tid in dev_ids if next(r for r in den_rows if r['task_id'] == tid)['msr_pass'])

    # W5c（专家第八轮 §3.2/§3.3 / R35）：exam MSR 必须能按族/栏拆开看——
    # 「族级 TSR 100%」可能全靠澄清题，MSR 分母为 0；不分列就会被读成「该族全链可用」。
    def _msr_of(ids):
        pp = sum(1 for tid in ids if next(r for r in den_rows if r['task_id'] == tid)['msr_pass'])
        return {'msr': f'{pp}/{len(ids)}', 'pass': pp, 'n': len(ids),
                'pct': round(100 * pp / len(ids), 1) if ids else None}

    exam_by_family = {fam: _msr_of([tid for tid in exam_ids if tasks[tid]['family'] == fam])
                      for fam in sorted({tasks[tid]['family'] for tid in exam_ids})}
    def _stratum(tid):
        t = tasks[tid]
        if t.get('exam_stratum'):
            return t['exam_stratum']
        return {'boundary_holdout': 'boundary', 'extrapolation_test': 'extrapolation',
                'interpolation_test': 'interpolation'}.get(t.get('split_v2'))
    exam_by_stratum = {s: _msr_of([tid for tid in exam_ids if _stratum(tid) == s])
                       for s in ('boundary', 'extrapolation', 'interpolation')
                       if any(_stratum(tid) == s for tid in exam_ids)}
    # R35：solver/算力失败必须单列。
    # ★ W5c 修（2026-10-25，审计发现「注释与实现相反」）：原注释写「exam MSR **不含** solver」，
    #   但实现里 exam_msr / dev_msr 都是**原始口径（含 solver）** —— 求解失败对模型确实是失败，
    #   剔掉是「能力上限口径」，两者都必须给，不能只留一个。
    #   ⇒ 现在显式输出四行：exam_msr / exam_msr_excl_solver / dev_msr / dev_msr_excl_solver
    #     + full msr / msr_excl_solver，并在 solver_task_ids 上再标一次归属（exam/dev）。
    #   ★ 附带实证：solver 桶是**候选相关**的 —— 同一题 `barrel_d2000_l2000_str12_frm4`
    #     v6b 旧候选 4.2s 就 pipeline 拒（class=model），v6c 新候选网格 169,606 节点
    #     才撞 158,548 阈值（class=solver）。所以跨版本「剔除 solver 后的分母」也会变，
    #     R30/R39 的不可比判定同样适用于剔除口径。
    solver_fails = [r for r in den_rows if not r['msr_pass'] and r.get('failure_class') == 'solver']
    n_solver = len(solver_fails)
    _sol_set = {r['task_id'] for r in solver_fails}
    exam_sol = [tid for tid in exam_ids if tid in _sol_set]
    dev_sol = [tid for tid in dev_ids if tid in _sol_set]

    def _msr_excl(ids):
        keep = [tid for tid in ids if tid not in _sol_set]
        pp = sum(1 for tid in keep if next(r for r in den_rows if r['task_id'] == tid)['msr_pass'])
        return f'{pp}/{len(keep)}', (round(100 * pp / len(keep), 1) if keep else None)

    # ★ W5c-6b（专家第九轮 §3.5 / R45）：剔除 solver 的三行**先算一次**再复用，
    #   并补两个此前缺失的键：dev_msr_pct、full_msr_excl_solver（= msr_excl_solver 的别名）。
    #   理由：数据一直在、但字段名找不到 ⇒ 复核者只能手算，手算就会与 claim 漂移。
    #   别名字段必须与主字段逐字相等（S-31 / NC-40 守）。
    ex_excl = _msr_excl(exam_ids)
    dv_excl = _msr_excl(dev_ids)
    full_excl = (f'{p}/{n - n_solver}', round(100 * p / max(1, n - n_solver), 1))

    # ★ W5c-6g（R52）：分母构成审计——全卷 + exam 各一份，闭合不成立直接退出（不静默出单）
    _DAUDIT = _denom_audit()
    _EAUDIT = _denom_audit([r['task_id'] for r in rows if _is_exam(tasks[r['task_id']])])
    if not (_DAUDIT['closure_ok'] and _DAUDIT['closure_solver_ok'] and _EAUDIT['closure_ok']):
        print('[FATAL] 分母不闭合（R52）——拒绝出 MSR：')
        print('  全卷:', _DAUDIT['closure'])
        print('  exam:', _EAUDIT['closure'])
        return 4
    print(f"[msr_l3] 分母闭合 全卷: {_DAUDIT['closure']}")
    print(f"[msr_l3] 分母闭合 exam: {_EAUDIT['closure']}")

    msr = {'note': '全链 MSR（R14/R16/R23，W5a 修正）：契约闸+ccx 求解+关1+关4+fidelity+spec_fidelity 全 PASS；'
                   '分母 = spec-required 且非澄清题（R23：澄清/未收敛候选不计，编造归 FPR）；'
                   '依赖预检不过即环境退出；失败分层 env/contract/model/solver，env 不计模型失败。',
           'provenance': {'tasks_path': os.path.relpath(os.path.abspath(tasks_path), HERE).replace('\\', '/'),
                          'tasks_sha256': sha256_file(tasks_path),
                          'candidates_dir': os.path.relpath(os.path.abspath(cand_dir), HERE).replace('\\', '/'),
                          'reuse_source': (
                              'self(recompute-only, no re-solve — 统计段由同一成绩单的 per_task 重算，须与实跑逐数一致)'
                              if args.reuse and os.path.abspath(args.reuse) == os.path.abspath(report_path)
                              else (os.path.relpath(os.path.abspath(args.reuse), HERE).replace('\\', '/')
                                    if args.reuse else None))},
           'n_not_run': sum(1 for r in rows if not r.get('denominator')
                            and 'not-run' in (r.get('reason') or '')),
           'msr': f'{p}/{n}', 'msr_pct': round(100 * p / max(1, n), 1),
           'exam_msr': f'{exam_p}/{len(exam_ids)}',
           'exam_msr_pct': round(100 * exam_p / max(1, len(exam_ids)), 1),
           'exam_by_family': exam_by_family,
           'exam_by_stratum': exam_by_stratum,
           'n_solver_excluded': n_solver,
           'solver_task_ids': [r['task_id'] for r in solver_fails],
           'solver_in_exam': exam_sol,
           'solver_in_dev': dev_sol,
           'exam_msr_excl_solver': ex_excl[0],
           'exam_msr_excl_solver_pct': ex_excl[1],
           'dev_msr_excl_solver': dv_excl[0],
           'dev_msr_excl_solver_pct': dv_excl[1],
           'msr_excl_solver': full_excl[0],
           'msr_excl_solver_pct': full_excl[1],
           'full_msr_excl_solver': full_excl[0],          # 别名（R45，与 msr_excl_solver 逐字相等）
           'full_msr_excl_solver_pct': full_excl[1],
           'dev_msr': f'{dev_p}/{len(dev_ids)}',
           'dev_msr_pct': round(100 * dev_p / max(1, len(dev_ids)), 1),
           'by_split': by_split,
           'denominator_audit': _DAUDIT,   # W5c-6g（R52）：分母四类拆分 + 闭合
           'exam_denominator_audit': _EAUDIT,
           'n_denominator': n, 'n_clarify_excluded': _DAUDIT['n_clarify_excluded'],
           'n_unresolved': n_unresolved,
           'n_unresolved_excluded': _DAUDIT['n_unresolved_excluded'],
           'n_notrun_excluded': _DAUDIT['n_notrun_excluded'],
           'n_env_excluded': _DAUDIT['n_env_excluded'],
           'n_tasks_total': _DAUDIT['n_tasks_total'],
           'denominator_note': ('R52：n_counted + clarify + unresolved + notrun + env + unknown = '
                                'n_tasks_total（层A）；n_counted = n_solver_excluded + '
                                'n_counted_excl_solver（层B，solver 仍在原始分母内）。'
                                'n_clarify_excluded 只含 expected_clarifications 题，'
                                '**不得**混入未收敛/no_output。'),
           # W5c-6h（R54）：MSR 是**条件通过率**——分母只含「产出了 spec 的非澄清题」。
           # 模型侧无输出不进分母（已由 TSR fail / FPR 记过一次，避免双记，W5a 原设计），
           # 后果是**不同成绩单的 MSR 分母可能不同**（C-032 exam 22 vs C-033 exam 21），
           # 裸报 pct 会被读成「同期同口径」，实测 C-033 的 95.2% 就是这样冒出来的。
           # ⇒ 口径写进成绩单，且必须并列 SFR；跨成绩单比 MSR 前先对齐分母与 SFR。
           'msr_definition': ('conditional：分母 = 产出了 spec 且非 expected_clarifications 的题；'
                              '模型侧无输出记 TSR fail / FPR，不计入 MSR（W5a 原设计，避免双记）。'
                              '⇒ **跨成绩单比 MSR 前必须先对齐分母与 SFR（R54）**，'
                              '分母不同时 pct 不得直减、不得据此排名。'),
           'n_no_spec_excluded_ids': [r['task_id'] for r in rows
                                      if (not r.get('denominator')) and 'no spec' in (r.get('reason') or '')],
           'failure_class_counts': dict(collections.Counter(
               r.get('failure_class') for r in den_rows if not r['msr_pass'])),
           'gate_fail_counts': dict(collections.Counter(
               k for r in den_rows for k, v in (r.get('gates') or {}).items() if not v)),
           'per_task': rows}
    sc = json.load(open(report_path, encoding='utf-8'))
    sc['msr_section'] = msr
    # 顶层同步（NC-22 检查点：成绩单必须含 exam.msr）
    sc.setdefault('exam', {})['msr'] = msr['exam_msr']
    sc.setdefault('dev', {})['msr'] = msr['dev_msr']
    # ★ W5c 修（NC-36 抓到）：顶层 `msr` 键此前一直是 **null** —— score_baseline 从不写它，
    #   msr_l3 也只写 msr_section/exam/dev。任何按 `scorecard['msr']` 读的消费者都会拿到
    #   None 而误以为「没跑 MSR」。现在显式同步。
    sc['msr'] = msr['msr']
    sc['msr_pct'] = msr['msr_pct']
    json.dump(sc, open(report_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nMSR = {p}/{n} ({msr['msr_pct']}%)  exam={msr['exam_msr']} dev={msr['dev_msr']}"
          f"  失败分层={msr['failure_class_counts']}")
    _ns = msr.get('n_no_spec_excluded_ids') or []
    if _ns:
        print(f"★ MSR 是条件通过率（R54）：分母已排除模型侧无输出的 {len(_ns)} 条 {_ns}")
        print("  ⇒ 与别的成绩单比 MSR 前先对齐分母与 SFR；分母不同不得直减、不得排名。")
    print('merged ->', report_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
