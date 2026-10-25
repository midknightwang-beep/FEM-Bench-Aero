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
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluate import evaluate_one, load_tasks, RUNS

CAND_DIR = os.path.join(HERE, 'candidates_l3_v3')   # W4e：考卷 v4 候选目录
REPORT = os.path.join(RUNS, 'baseline_scorecard_L3.json')

VENV_PY = 'C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe'


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

    tasks = {t['task_id']: t for t in load_tasks(os.path.join(HERE, 'tasks', 'tasks.jsonl'))
             if t['input_level'] == 'L3'}
    cands = {}
    for fn in sorted(os.listdir(CAND_DIR)):
        if fn.endswith('.json'):
            c = json.load(open(os.path.join(CAND_DIR, fn), encoding='utf-8'))
            cands[c['task_id']] = c

    rows, n_env_skip = [], 0
    for tid in sorted(tasks):
        t = tasks[tid]
        c = cands.get(tid) or {}
        if not c.get('spec'):
            # 澄清/未收敛/编造被拒候选：无 spec 期望，不计 MSR 分母（P1-4）
            rows.append({'task_id': tid, 'msr_pass': None, 'denominator': False,
                         'reason': 'no spec (clarify/unresolved/fabricated-rejected)'})
            print(f"  [--] {tid}: no spec -> 不进分母")
            continue
        try:
            r = evaluate_one(t, os.path.join(CAND_DIR, tid + '.json'), skip_solve=False,
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
    msr = {'note': '全链 MSR（R14/R16，W4e 修正）：契约闸+ccx 求解+关1+关4+fidelity+spec_fidelity 全 PASS；'
                   '分母 = spec-required 任务（澄清/未收敛候选不计）；依赖预检不过即环境退出；'
                   '失败分层 env/contract/model/solver，env 不计模型失败。',
           'msr': f'{p}/{n}', 'msr_pct': round(100 * p / max(1, n), 1),
           'n_denominator': n, 'n_clarify_excluded': sum(1 for r in rows if not r.get('denominator')),
           'failure_class_counts': dict(collections.Counter(
               r.get('failure_class') for r in den_rows if not r['msr_pass'])),
           'gate_fail_counts': dict(collections.Counter(
               k for r in den_rows for k, v in (r.get('gates') or {}).items() if not v)),
           'per_task': rows}
    sc = json.load(open(REPORT, encoding='utf-8'))
    sc['msr_section'] = msr
    json.dump(sc, open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nMSR = {p}/{n} ({msr['msr_pct']}%)  失败分层={msr['failure_class_counts']}")
    print('merged ->', REPORT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
