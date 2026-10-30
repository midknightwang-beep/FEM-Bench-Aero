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
from _paths import rel   # T-A11a：跨盘符安全（见 _paths.py）

REPORT_DIR = os.path.join(HERE, 'reports')
REPORT = os.path.join(REPORT_DIR, 'baseline_scorecard_L3.json')

VENV_PY = 'C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe'


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ★★ T-A11b（N-20 的真正根因）：**失败原因必须整条落盘**。
#   旧实现两个错叠在一起，任何一个单独都不致命、合起来让 artifact 不可审计：
#     ① `gates = {k: bool(v.get('pass'))}` 把每个 gate 压成布尔 —— 结构化诊断全丢；
#     ② `failure_detail` 只取 `gates['pipeline'].detail or .actual`；
#        而 `spec_fidelity` 失败时 pipeline **是 pass**、它的 detail 是 None
#        ⇒ detail 落成 **空字符串**。实测 v7 glm 首跑里 `L3_stiffened_panel_800x600_str3`
#        的 failure_detail 就是 ''，只看得见 `class=model`
#        （事后靠单条探针重算才知道是 `params.length/width` 800↔600 采样反了）。
#   ⇒ 任何闸（含 S-55）都无法从 artifact 复核失败原因，等于**闸建立在空字段上**（R58）。
_DIAG_KEYS = ('field', 'expected', 'actual', 'detail', 'n_fail', 'n_fields',
              'failed', 'exec_config_mismatch', 'metadata_extra',
              'n_tri3', 'n_nodes', 'min_quality', 'label_error_type')


def _gate_diag(result):
    """收集**失败 gate** 的原始诊断字段（pass 的 gate 不收，避免体积膨胀）。"""
    out = {}
    for name, g in (result.get('gates') or {}).items():
        if g.get('pass'):
            continue
        d = {k: g[k] for k in _DIAG_KEYS if k in g and g[k] not in (None, '', [], {})}
        if isinstance(d.get('detail'), str):
            d['detail'] = d['detail'][-1200:]      # 只留尾部（报错总在尾）
        out[name] = d
    return out


def _diag_text(result):
    """把**全部**失败 gate 的诊断摊成一段文本，供关键词归类。

    以前只看 pipeline 一个 gate 的 detail —— 但 `spec_fidelity` / `mesh_quality` /
    `semantics` / `fidelity_disp` 失败时 pipeline 是 pass，detail 是 None
    ⇒ 归类函数实际只对「pipeline 挂掉」这一种情况有输入，其余全靠 `return 'model'` 兜底。
    """
    g = result.get('gates') or {}
    parts = []
    for name, gg in g.items():
        if gg.get('pass'):
            continue
        for k in ('field', 'expected', 'actual', 'detail'):
            v = gg.get(k)
            if isinstance(v, str) and v:
                parts.append(v)
            elif v is not None and k in ('field', 'expected', 'actual'):
                parts.append(str(v))
        if gg.get('failed'):
            try:
                parts.append(json.dumps(gg['failed'][:5], ensure_ascii=False))
            except Exception:
                pass
    return ' '.join(parts)


LOCK_MARKS = ('.solve.lock', '检测到另一个求解正在进行')


def audit_solver_lock_conflict(rows):
    """S-55：返回「被判成 solver、但诊断里其实写着求解锁冲突」的 task_id 列表。

    为什么这条闸必须存在：N-20 的错法是「先把并发事故归成 solver，再当算力不足剔出分母」，
    于是**模型被替它掩盖了真失败**（R16）。而当时没有任何东西会红 —— 因为 detail 根本没落盘（N-21）。
    现在 detail 落了，闸才有对象可查；不装这条，下次 classify 写错照样静默。

    抽成函数而不是内联：内联断言负控**调不到**，而「工具自己不会红等于没判据」是本仓库
    踩过两次的坑（NC-57 的由来）。抽出后 negative_controls 可以直接喂合成 row 看它点不点得出来。
    """
    bad = []
    for r in rows:
        if r.get('failure_class') != 'solver':
            continue
        blob = (json.dumps(r.get('failure_gates') or {}, ensure_ascii=False)
                + (r.get('failure_detail') or ''))
        if any(m in blob for m in LOCK_MARKS):
            bad.append(r['task_id'])
    return bad


def classify_failure(result):
    """失败分层（专家 P0-2：env / contract / model / solver）。

    注：`contract` 分支**故意只认 pipeline 一个 gate**（`contract_ok` / `contract_buildable`
    是 pipeline 的 field）。把它扩到全 gate 会把历史上归 `model` 的条目翻成 `contract`，
    改变跨版本 failure_breakdown 口径 —— 与本轮「只加诊断、不改判分」相冲突。
    """
    g = result.get('gates', {})
    pipe = g.get('pipeline', {})
    pipe_text = (pipe.get('detail') or '') + ' ' + (pipe.get('actual') or '')
    detail = _diag_text(result) or pipe_text        # 全 gate 文本（契约分支仍只看 pipe）
    if 'contract' in pipe.get('field', '') or 'contract' in pipe_text[:120]:
        return 'contract'
    if 'ModuleNotFoundError' in detail or 'ImportError' in detail:
        return 'env'
    # ★ T-A11b（R16）：求解锁冲突是**环境/并发**问题，不是算力不足，更不是模型错。
    #   实测（v7 glm 首跑）：msr 跑到尾部 6 条时，前一条的锁没被释放（持有 pid 已死），
    #   后续每条都抛 `RuntimeError: 检测到另一个求解正在进行…R61 禁止并行`；
    #   而下面 `actual.startswith('rc=')` 把它一并归成 `solver` ⇒ **6 条假 solver 失败**，
    #   等于把环境事故记成「模型能力不足」再剔出分母（R16 明令禁止）。
    #   必须先判锁冲突，再判 rc。
    if '.solve.lock' in detail or '检测到另一个求解正在进行' in detail:
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
    ap.add_argument('--force', default=None,
                    help='T-A11b：逗号分隔的 task_id 列表，**即使 --reuse 里已有结果也重跑这几条**。\n'
                         '用途：一次 msr 里若有个别条目因环境失败被废，不必整卷重跑 50 分钟，\n'
                         '用 `--reuse 本成绩单 --force 这几条` 定点补齐（其余逐字节复用）。\n'
                         '★ 为什么必须定点而不是整卷重跑：环境注入的批量删除保护在「单次调用累计删除 50 个文件」\n'
                         '处会拒绝 unlink，而每条任务释放锁就是一次删除 ⇒ 59 条必然在 ~53 条处炸（N-22）。\n'
                         '分母与闭合仍按**全卷**重算（rows 覆盖全部任务），不会因为只跑 6 条而变小。')
    ap.add_argument('--only', default=None,
                    help='T-A11b（N-22 环境约束）：逗号分隔的 task_id 列表，**本批只跑这些**。\n'
                         '与 --reuse 合用时，其余任务从复用源照抄；没有复用源就记 not_run 待补齐。\n'
                         '为什么要分批：环境注入的批量删除保护在「单次调用累计删除 50 个文件」处拒绝\n'
                         '`unlink()`，而每条任务释放求解锁就是一次删除 ⇒ 一次跑 59 条必然在 ~第 53 条处\n'
                         '把锁删不掉、后续全被锁挡住。分两批（各 ≤40 条）可完全绕开。')
    args = ap.parse_args()
    only_ids = {s.strip() for s in (getattr(args, 'only', None) or '').split(',') if s.strip()}
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
    force_ids = {s.strip() for s in (args.force or '').split(',') if s.strip()}
    if force_ids and not args.reuse:
        print('[msr_l3] --force 必须与 --reuse 同时使用（--force 的含义是「从复用源里挑几条重跑」）')
        return 2
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
        if only_ids and tid not in only_ids:
            # ★ T-A11b（N-22 环境约束）：本批不跑。复用源里有结果就照抄（下面 reuse 分支处理），
            #   没有就记 not_run —— **不能**让它落到 evaluate_one，否则「分批」等于没分。
            _pr = (reuse_map.get(tid) or {}) if reuse_map else {}
            if _pr.get('msr_pass') is None:
                rows.append({'task_id': tid, 'msr_pass': None, 'denominator': False,
                             'reason': 'not-run: not in --only batch（本批未跑，待后续批次补齐）'})
                print(f"  [--] {tid}: 不在本批 --only 内 -> 待补齐")
                continue
        if reuse_map and tid not in force_ids:
            pr = reuse_map.get(tid)
            if not pr or pr.get('msr_pass') is None:
                rows.append({'task_id': tid, 'msr_pass': None, 'denominator': False,
                             'reason': 'not-run in reuse source（该口径下无求解结果，不得计入）'})
                print(f"  [--] {tid}: reuse 源里无求解结果 -> 不进分母")
                continue
            row = dict(pr)
            # ★ 复用不能把 env 条目「洗」回分母：源里是 env 排除的就保持排除（R16）。
            row['denominator'] = False if row.get('failure_class') == 'env' else True
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
            # ★ T-A11b：`failure_gates` 存**结构化**诊断（哪个 gate、field、expected/actual），
            #   `failure_detail` 存摊平文本。两者都必须非空 —— 空 = 这条失败不可审计，
            #   事后只能靠重跑探针猜（N-20 已经这样浪费过一轮 40 min）。
            fg = _gate_diag(r)
            row['failure_gates'] = fg
            row['failure_detail'] = (_diag_text(r) or 'NO_DIAGNOSTIC_CAPTURED')[:2000]
            if not fg:
                print(f"  [!!] {tid}: 判 FAIL 却无任何失败 gate 诊断 —— artifact 不可审计")
            # ★★ T-A11b（R16 落到**分母**上，而不是只写在注释里）：
            #   旧实现只有「evaluate_one 直接抛异常」那条路径设了 denominator=False；
            #   而 `pipeline` rc≠0 这条路径是**先 append(denominator=True) 再 classify**
            #   ⇒ env 条目留在分母里，于是同一次运行里印出两句自相矛盾的话：
            #     「环境失败 6 条——不进 MSR 分母（R16）」 与 「counted 59 + … + env 0」
            #   （v7 glm run2 实测就这样：env 被判成 6 条，闭合式里却是 0，MSR 报 44/59）。
            #   R16 是红线，不是注释 ⇒ env 必须退出分母。
            if row['failure_class'] == 'env':
                row['denominator'] = False
                row['excluded_reason'] = 'env failure（R16：环境事故不计模型失败，退出分母）'
        rows.append(row)
        bad = [k for k, v in gates.items() if not v]
        print(f"  [{'ok' if ok else 'FAIL'}] {tid}: gates={gates} "
              f"fidelity={r.get('fidelity_disp_dev_pct','n/a')}% wall={r.get('wall_seconds')}s"
              + (f" bad={bad} class={row.get('failure_class')}" if bad else ''))

    den_rows = [r for r in rows if r.get('denominator')]
    n, p = len(den_rows), sum(1 for r in den_rows if r['msr_pass'])

    # ★★ S-55（N-20 的闸）：`failure_class == 'solver'` 的条目，诊断里**不得**出现求解锁冲突。
    #   ★ 抽成独立函数（`audit_solver_lock_conflict`）而不是内联 if：
    #     内联断言**没法被负控调用**，而「工具自己不会红等于没判据」是本仓库踩过两次的坑
    #     （NC-57 的由来）。抽出来后 negative_controls 可以直接喂一条合成 row 看它是否点得出来。
    bad_solver = audit_solver_lock_conflict(rows)
    if bad_solver:
        print('[FATAL] S-55：以下条目 class=solver 但诊断含求解锁冲突 —— '
              '并发事故不得记成算力失败（R16）：' + ', '.join(bad_solver))
        return 5

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

    # ★ T-A11a（v7 / C-037 双分母，R66）：`interpolation_v11` 必须自成桶。
    #   旧实现 `_is_exam = bool(t.get('exam_stratum'))` 在 v7 上会**两头都错**：
    #   ① exam_ids 变 34（与 C-032 的 25 不同分母）；② 更隐蔽的是 `dev_ids = not _is_exam`
    #   本来会把 v11 折进 dev，dev 分母 30→39 ⇒ dev MSR 跨版本不可比（R-A6）。
    #   ⇒ 显式三分：legacy 三栏 / v11 / dev，三桶互斥穷尽。
    LEGACY_STRATA = ('boundary', 'extrapolation', 'interpolation')
    V11_STRATA = ('interpolation_v11',)
    OTHER_SPLIT_STRATUM = {'boundary_holdout': 'boundary', 'extrapolation_test': 'extrapolation',
                           'interpolation_test': 'interpolation'}

    def _stratum_of(t):
        s = t.get('exam_stratum')
        if s:
            return s
        return OTHER_SPLIT_STRATUM.get(t.get('split_v2'))

    def _is_exam(t):
        """legacy exam 谓词（三栏 25 条）。v11 不许并进这一侧。"""
        if has_stratum:
            return _stratum_of(t) in LEGACY_STRATA
        return t.get('split_v2') in ('boundary_holdout', 'extrapolation_test')

    def _is_v11(t):
        return has_stratum and _stratum_of(t) in V11_STRATA

    exam_ids = [r['task_id'] for r in den_rows if _is_exam(tasks[r['task_id']])]
    exam_p = sum(1 for tid in exam_ids if next(r for r in den_rows if r['task_id'] == tid)['msr_pass'])
    # ★ dev 必须两边都排除：只写 `not _is_exam` 会把 v11 吞进 dev（30→39）
    dev_ids = [r['task_id'] for r in den_rows
               if not _is_exam(tasks[r['task_id']]) and not _is_v11(tasks[r['task_id']])]
    dev_p = sum(1 for tid in dev_ids if next(r for r in den_rows if r['task_id'] == tid)['msr_pass'])
    v11_ids = [r['task_id'] for r in den_rows if _is_v11(tasks[r['task_id']])]
    v11_p = sum(1 for tid in v11_ids if next(r for r in den_rows if r['task_id'] == tid)['msr_pass'])
    exam_full_ids = exam_ids + v11_ids
    exam_full_p = exam_p + v11_p

    # W5c（专家第八轮 §3.2/§3.3 / R35）：exam MSR 必须能按族/栏拆开看——
    # 「族级 TSR 100%」可能全靠澄清题，MSR 分母为 0；不分列就会被读成「该族全链可用」。
    def _msr_of(ids):
        pp = sum(1 for tid in ids if next(r for r in den_rows if r['task_id'] == tid)['msr_pass'])
        return {'msr': f'{pp}/{len(ids)}', 'pass': pp, 'n': len(ids),
                'pct': round(100 * pp / len(ids), 1) if ids else None}

    exam_by_family = {fam: _msr_of([tid for tid in exam_ids if tasks[tid]['family'] == fam])
                      for fam in sorted({tasks[tid]['family'] for tid in exam_ids})}
    def _stratum(tid):
        return _stratum_of(tasks[tid])
    # ★ T-A11a：分栏按 **exam_full** 遍历四栏（v6c 上等价于三栏 ⇒ 数字逐字不变）；
    #   若仍只遍历三栏，v7 会出现「四栏明细加起来 25 而 exam_msr 报 x/34」——静默漏 9 条（R-A5）。
    exam_by_stratum = {s: _msr_of([tid for tid in exam_full_ids if _stratum(tid) == s])
                       for s in (LEGACY_STRATA + V11_STRATA)
                       if any(_stratum(tid) == s for tid in exam_full_ids)}
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
    # ★ T-A12b（第十四轮 P1-4 / R52）：exam_full 也要有剔除 solver 的口径。
    #   此前只有 legacy exam（`exam_msr_excl_solver`）、dev、全卷有，exam_full 缺 ⇒
    #   两层分母在每个尺度都可见（R52）这条在 exam_full 上是断的。
    #   用 counted 集 `exam_full_ids`（`_msr_excl` 要在 den_rows 里查，不能传全量）。
    ef_excl = _msr_excl(exam_full_ids)
    full_excl = (f'{p}/{n - n_solver}', round(100 * p / max(1, n - n_solver), 1))

    # ★ W5c-6g（R52）：分母构成审计——全卷 + exam 各一份，闭合不成立直接退出（不静默出单）
    _DAUDIT = _denom_audit()
    _EAUDIT = _denom_audit([r['task_id'] for r in rows if _is_exam(tasks[r['task_id']])])
    # ★★ N-26（T-A12b）：分母审计必须用**全量任务集**，不能用 counted 集。
    #   旧写法传 `exam_full_ids`（= exam_ids + v11_ids，两者都取自 `den_rows`）⇒ pool 里
    #   每一行都是 denominator=True ⇒ `n_tasks_total ≡ n_counted`、clarify/unresolved 恒 0
    #   ⇒ **`closure_ok` 是代数恒真式**，而下面那句 `[FATAL] 分母不闭合` 正是靠它把关
    #   ⇒ exam_full 这一路的分母闭合**从未真正被检查过**。
    #   NC-58 也抓不到：它测的是 `exam_full_closure.ok`（另一条真算术路径），两者互不覆盖。
    #   实测（v7 改前）：glm 印 `30 = counted 30 + clarify 0`、ds 印 `29 = counted 29 + clarify 0`；
    #   真值是 glm `34 = 30 + 4 + 0`、ds `34 = 29 + 4 + 1`。
    #   ⇒ 改传全量。**counted 集 `exam_full_ids` 仍专用于 MSR 分母，分数一个数字都不动。**
    exam_full_all_ids = [r['task_id'] for r in rows
                         if _is_exam(tasks[r['task_id']]) or _is_v11(tasks[r['task_id']])]
    _FAUDIT = _denom_audit(exam_full_all_ids) if v11_ids else None
    if _FAUDIT is not None:
        _FAUDIT['units'] = (f'tasks（全量 {len(exam_full_all_ids)} 条，含 clarify/unresolved；'
                            f'与顶层 exam_denominator_closure.exam_full 同口径。'
                            f'MSR 分母用的 counted 集见 exam_full_closure，单位不同、不可互抄）')
    if not (_DAUDIT['closure_ok'] and _DAUDIT['closure_solver_ok'] and _EAUDIT['closure_ok']
            and (_FAUDIT is None or _FAUDIT['closure_ok'])):
        print('[FATAL] 分母不闭合（R52）——拒绝出 MSR：')
        print('  全卷:', _DAUDIT['closure'])
        print('  exam:', _EAUDIT['closure'])
        if _FAUDIT:
            print('  exam_full:', _FAUDIT['closure'])
        return 4
    print(f"[msr_l3] 分母闭合 全卷: {_DAUDIT['closure']}")
    print(f"[msr_l3] 分母闭合 exam: {_EAUDIT['closure']}")

    msr = {'note': '全链 MSR（R14/R16/R23，W5a 修正）：契约闸+ccx 求解+关1+关4+fidelity+spec_fidelity 全 PASS；'
                   '分母 = spec-required 且非澄清题（R23：澄清/未收敛候选不计，编造归 FPR）；'
                   '依赖预检不过即环境退出；失败分层 env/contract/model/solver，env 不计模型失败。',
           'provenance': {'tasks_path': rel(os.path.abspath(tasks_path)),
                          'tasks_sha256': sha256_file(tasks_path),
                          'candidates_dir': rel(os.path.abspath(cand_dir)),
                          'reuse_source': (
                              'self(recompute-only, no re-solve — 统计段由同一成绩单的 per_task 重算，须与实跑逐数一致)'
                              if args.reuse and os.path.abspath(args.reuse) == os.path.abspath(report_path)
                              else (rel(os.path.abspath(args.reuse))
                                    if args.reuse else None))},
           'n_not_run': sum(1 for r in rows if not r.get('denominator')
                            and 'not-run' in (r.get('reason') or '')),
           'msr': f'{p}/{n}', 'msr_pct': round(100 * p / max(1, n), 1),
           'exam_msr': f'{exam_p}/{len(exam_ids)}',
           'exam_msr_pct': round(100 * exam_p / max(1, len(exam_ids)), 1),
           # ★ T-A11a（C-037 / R66）：v1.1 双分母。`exam_msr` 恒为 legacy（与 C-032 同分母），
           #   `exam_full_msr` = legacy + interpolation_v11。二者并列、**禁止相减**（R54）。
           'exam_v11_msr': f'{v11_p}/{len(v11_ids)}',
           'exam_v11_msr_pct': (round(100 * v11_p / len(v11_ids), 1) if v11_ids else None),
           'exam_full_msr': f'{exam_full_p}/{len(exam_full_ids)}',
           'exam_full_msr_pct': round(100 * exam_full_p / max(1, len(exam_full_ids)), 1),
           'exam_full_denominator_audit': _FAUDIT,
           'exam_full_closure': {
               # ★ T-A12b：这个块是 **counted 语境**（MSR 只在可计分子集上算），
               #   里面的 `exam_full` = 30/29 与顶层的 34 **同名不同义**。
               #   不写这行，读者会把 29 当成「exam_full 只有 29 条」——正是 P1-4 的读法。
               'units': 'counted（MSR 可计分子集；任务语境的 34 见顶层 exam_denominator_closure）',
               'exam_legacy': len(exam_ids), 'exam_v11': len(v11_ids),
               'exam_full': len(exam_full_ids), 'dev': len(dev_ids),
               'closure_sum': len(exam_ids) + len(v11_ids) + len(dev_ids),
               'ok': (len(exam_ids) + len(v11_ids) + len(dev_ids) == len(den_rows)
                      and len(exam_full_ids) == len(exam_ids) + len(v11_ids)),
           },
           'exam_by_family': exam_by_family,
           'exam_by_stratum': exam_by_stratum,
           'n_solver_excluded': n_solver,
           'solver_task_ids': [r['task_id'] for r in solver_fails],
           'solver_in_exam': exam_sol,
           'solver_in_dev': dev_sol,
           'exam_msr_excl_solver': ex_excl[0],
           'exam_msr_excl_solver_pct': ex_excl[1],
           'exam_full_msr_excl_solver': ef_excl[0],
           'exam_full_msr_excl_solver_pct': ef_excl[1],
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
           # ★ T-A12b（第十四轮 P1-4）：**同名不同义**必须显式标注。
           #   顶层 `scorecard.n_unresolved` 是**候选层**（`score_baseline.py` 数 `category=='no_output'`），
           #   这里是**任务层**（spec-required 但没产出 spec，含「澄清判错」这种情况）。
           #   v7×ds 实测：顶层 0、本字段 1（`L3_open_hole_panel_400x200_d20_cfrp45s_d40`，
           #   category=clarify_wrong ⇒ 有输出、没 spec）—— 只读顶层的人会得出「ds 没有未收敛」，
           #   与 `denominator_audit.unresolved_task_ids` 直接矛盾。S-54 现在会强制这条说明在场。
           'n_unresolved_note': ('本字段是**任务层**（spec-required 但未产出 spec，含「澄清判错」）；'
                                 '顶层 scorecard.n_unresolved 是**候选层**（category=no_output）。'
                                 '同名不同义，引用时必须写清是哪一层。'),
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
    # ★ T-A11a：v1.1 双分母同步到顶层（老卷 v11 为空 ⇒ exam_full.msr == exam.msr，不新增读数）
    if msr.get('exam_full_closure', {}).get('exam_v11'):
        sc.setdefault('exam_full', {})['msr'] = msr['exam_full_msr']
        sc.setdefault('exam_v11', {})['msr'] = msr['exam_v11_msr']
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
