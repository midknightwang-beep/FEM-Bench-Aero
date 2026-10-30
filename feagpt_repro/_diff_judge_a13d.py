# -*- coding: utf-8 -*-
"""_diff_judge_a13d.py — T-A13d 的构造性零差异证据（N-28 / R70）

三路判据并行，逐条比：

  `oracle`   : **旧判据的逐字副本**（裸子串），冻结在本文件里，永不随源码漂移
  `composed` : 用**真实的** `score_baseline._alias_hit` 组合出的判据（非副本）
  `actual`   : **真实的** `score_baseline.judge_clarify_field_level`（最终调用点）

为什么是三路而不是两路（防假绿）：
  只比 `oracle vs actual`，在「改前」两者必然相同 —— 那是自比，证明不了任何东西。
  必须先用 `composed` 证明「新匹配方式确实会与旧的不同」（合成探针 + 真实数据），
  再用 `actual == composed` 证明「最终实现就是被测的那一个」。

用法（venv 解释器）：
  python _diff_judge_a13d.py            # 全量比对 + 探针，写 reports/diagnostics/judge_diff_a13d.json
  python _diff_judge_a13d.py --probe-only   # 只跑探针（改判据前的快速自检）
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from score_baseline import _alias_hit, judge_clarify_field_level  # noqa: E402

TASKS = os.path.join(HERE, 'tasks', 'tasks.jsonl')
OUT = os.path.join(HERE, 'reports', 'diagnostics', 'judge_diff_a13d.json')

# 真实数据：两层的全部候选（L2 是首次跑分的那两批，L3 是 C-032/C-040 那两批）
CAND_DIRS = [
    ('L2', 'glm', 'candidates_l2_v7_glm'),
    ('L2', 'ds', 'candidates_l2_v7_ds'),
    ('L3', 'glm', 'candidates_l3_v7_glm'),
    ('L3', 'ds', 'candidates_l3_v7_ds'),
]


# ---------------------------------------------------------------- oracle（冻结副本）
def judge_oracle(text, task):
    """★ 旧判据逐字副本 —— 唯一用途是当参照物，**不得**被修「好看」。

    与 T-A13d 之前的 `score_baseline.judge_clarify_field_level` 等价（含那段死代码的语义）。
    """
    aliases = task.get('clarify_aliases') or {}
    wrong = task.get('clarify_wrong_keys') or []
    fields = task.get('expected_clarifications') or []
    if not fields:
        return None                      # 无 expected ⇒ 不走本判据（调用方判 clarify_wrong）
    hit_wrong = [k for k in wrong if k in text] if isinstance(wrong, list) else []
    if hit_wrong:
        return False
    ok_all = True
    for i, f in enumerate(fields):
        if isinstance(aliases, dict):
            al = aliases.get(f) or [f]
        else:
            al = aliases or [f]
        if not [a for a in al if a in text]:
            ok_all = False
    return ok_all


# ---------------------------------------------------------------- composed（真实 _alias_hit）
def judge_composed(text, task):
    """用真实 `_alias_hit` 组合的判据 —— 与 oracle 唯一差别就是匹配方式。"""
    aliases = task.get('clarify_aliases') or {}
    wrong = task.get('clarify_wrong_keys') or []
    fields = task.get('expected_clarifications') or []
    if not fields:
        return None
    if [k for k in wrong if _alias_hit(k, text)]:
        return False
    ok_all = True
    for i, f in enumerate(fields):
        if isinstance(aliases, dict):
            al = aliases.get(f) or [f]
        else:
            al = aliases or [f]
        if not [a for a in al if _alias_hit(a, text)]:
            ok_all = False
    return ok_all


# ---------------------------------------------------------------- 合成探针（防假绿核心）
def build_probes():
    """每条探针必须能**逼出 oracle 与 composed 的分歧**，否则它没在测任何东西。

    字段名 `expect` 是**预期的新判据结果**；oracle 的结果必须与它相反才算「有分歧」。
    另有 `same=True` 的探针（P2/P3/P7），用来守「不得过严」。
    """
    S = '请给出 n_stringers 的值'                        # 主语
    return [
        # ---- 假通过通道（旧 True → 新 False）：三个子串字段各一向 ----
        dict(id='P1', kind='fake_pass', alias='n_stringers',
             text='请给出 n_stringers_per_skin 的值', same=False, expect_new=False,
             task={'expected_clarifications': ['n_stringers'], 'clarify_aliases': None,
                   'clarify_wrong_keys': []},
             why='省略 n_stringers，模型只写 n_stringers_per_skin ⇒ 旧判据假通过'),
        dict(id='P2', kind='fake_pass', alias='n_stringers',
             text='structure.params.n_stringers 缺失', same=True, expect_new=True,
             task={'expected_clarifications': ['n_stringers'], 'clarify_aliases': None,
                   'clarify_wrong_keys': []},
             why='前面是点 ⇒ 必须仍命中（边界不得过严）'),
        dict(id='P3', kind='fake_pass', alias='n_stringers',
             text='请给出 n_stringers（根数）', same=True, expect_new=True,
             task={'expected_clarifications': ['n_stringers'], 'clarify_aliases': None,
                   'clarify_wrong_keys': []},
             why='后面是中文括号 ⇒ 必须仍命中（边界只约束标识符字符）'),
        dict(id='P4', kind='fake_pass', alias='thickness',
             text='请给出 rib_thickness 的值', same=False, expect_new=False,
             task={'expected_clarifications': ['thickness'], 'clarify_aliases': None,
                   'clarify_wrong_keys': []},
             why='省略笼统 thickness，模型只写 rib_thickness ⇒ 旧判据假通过'),
        dict(id='P5', kind='fake_pass', alias='width',
             text='stringer_flange_width 是多少', same=False, expect_new=False,
             task={'expected_clarifications': ['width'], 'clarify_aliases': None,
                   'clarify_wrong_keys': []},
             why='省略 width，模型只写 stringer_flange_width ⇒ 旧判据假通过'),
        # ---- 假红通道（旧 False → 新 True）：W5c-6d 记的那一半 ----
        dict(id='P6', kind='fake_red', alias='n_stringers_per_skin',
             text='请给出 n_stringers_per_skin 的值', same=False, expect_new=True,
             task={'expected_clarifications': ['n_stringers_per_skin'],
                   'clarify_aliases': {'n_stringers_per_skin': ['n_stringers_per_skin']},
                   'clarify_wrong_keys': ['n_stringers']},
             why='错族键 n_stringers 被 n_stringers_per_skin 吃掉 ⇒ 旧判据假红'),
        # ---- 中文别名必须零变化 ----
        dict(id='P7', kind='cjk', alias='翼肋',
             text='翼肋数量是多少', same=True, expect_new=True,
             task={'expected_clarifications': ['n_ribs'],
                   'clarify_aliases': {'n_ribs': ['n_ribs', '翼肋', '肋数']},
                   'clarify_wrong_keys': []},
             why='中文别名「翼肋」在「翼肋数量」里 ⇒ 必须仍命中（不得被边界改坏）'),
        dict(id='P8', kind='cjk', alias='多少根长桁',
             text='要多少根长桁？', same=True, expect_new=True,
             task={'expected_clarifications': ['n_stringers'],
                   'clarify_aliases': {'n_stringers': ['n_stringers', '多少根长桁']},
                   'clarify_wrong_keys': []},
             why='中文短语别名含 ASCII 之外字符 ⇒ 走子串分支，行为不变'),
    ]


def run_probes():
    probes = build_probes()
    rows, bad = [], []
    for p in probes:
        o = judge_oracle(p['text'], p['task'])
        c = judge_composed(p['text'], p['task'])
        a = judge_clarify_field_level(p['text'], p['task'])[0] \
            if (p['task'].get('expected_clarifications')) else None
        # ① 新判据结果必须等于预期
        if c != p['expect_new']:
            bad.append(f"{p['id']} 新判据={c} 与预期 {p['expect_new']} 不符（{p['why']}）")
        # ② same=False 的探针必须真的分歧（否则它没在测任何东西）
        if (not p['same']) and (o == c):
            bad.append(f"{p['id']} oracle={o} 与 composed={c} **没有分歧** ⇒ 探针失效（{p['why']}）")
        # ③ same=True 的探针必须不分歧
        if p['same'] and (o != c):
            bad.append(f"{p['id']} 本应不变但变了：oracle={o} composed={c}（{p['why']}）")
        # ④ 真实调用点必须等于 composed（阶段 B 之后才成立；阶段 A 会不相等，由调用方判读）
        rows.append(dict(id=p['id'], kind=p['kind'], why=p['why'], text=p['text'][:60],
                         alias=p['alias'], oracle=o, composed=c, actual=a,
                         expect_new=p['expect_new'], same=p['same']))
    n_diverge = sum(1 for r in rows if r['oracle'] != r['composed'])
    n_same = sum(1 for r in rows if r['same'])
    return rows, bad, n_diverge, n_same


# ---------------------------------------------------------------- 真实数据全量
def load_tasks():
    return {r['task_id']: r
            for r in (json.loads(l) for l in open(TASKS, encoding='utf-8') if l.strip())}


def run_real(tasks):
    rows, bad = [], []
    for lvl, model, d in CAND_DIRS:
        files = sorted(glob.glob(os.path.join(HERE, d, '*.json')))
        if not files:
            bad.append(f'候选目录为空：{d}（不得 skip，R-A5）')
            continue
        for f in files:
            c = json.load(open(f, encoding='utf-8'))
            tid = c.get('task_id') or os.path.basename(f)[:-5]
            t = tasks.get(tid)
            if t is None:
                bad.append(f'{d}: task_id {tid} 不在考卷里')
                continue
            text = c.get('clarify') or ''
            if not text:
                continue                      # 给 spec 的候选不走本判据
            o = judge_oracle(text, t)
            if o is None:
                continue                      # 无 expected_clarifications
            cp = judge_composed(text, t)
            ac = judge_clarify_field_level(text, t)[0]
            rows.append(dict(level=lvl, model=model, task_id=tid, oracle=o,
                             composed=cp, actual=ac, text=text[:160],
                             ec=t.get('expected_clarifications'),
                             wk=t.get('clarify_wrong_keys')))
            if not (o == cp == ac):
                bad.append(f'{d}/{tid}: oracle={o} composed={cp} actual={ac} ★ 判类有变化')
    return rows, bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--probe-only', action='store_true')
    ap.add_argument('--out', default=OUT)
    a = ap.parse_args(argv)

    probes, bad_p, n_div, n_same = run_probes()
    print(f'[探针] {len(probes)} 向：其中须分歧 {len(probes) - n_same} 向、须不变 {n_same} 向；'
          f'实测分歧 {n_div} 向')
    for r in probes:
        print(f"  {r['id']:3s} [{r['kind']:9s}] oracle={str(r['oracle']):5s} "
              f"composed={str(r['composed']):5s} actual={str(r['actual']):5s}  {r['why']}")

    real, bad_r = [], []
    if not a.probe_only:
        tasks = load_tasks()
        real, bad_r = run_real(tasks)

    # ★ 阶段判读：actual 与 composed 是否已一致（一致 ⇒ 调用点已改）
    call_site_moved = all(
        (r['actual'] == r['composed']) for r in probes if r['actual'] is not None)
    n_real = len(real)
    n_real_div = sum(1 for r in real if not (r['oracle'] == r['composed'] == r['actual']))
    n_alias_side = sum(1 for r in real if r['oracle'] != r['composed'])
    n_wrong_side = sum(1 for r in real if r['composed'] != r['actual'])

    rec = {
        'note': ('T-A13d 构造性零差异证据（N-28 / R70）。oracle = 旧判据逐字副本；'
                 'composed = 用真实 _alias_hit 组合；actual = 真实 judge_clarify_field_level。'
                 '★ 三路的意义：oracle vs actual 在改前是自比，不算证据；必须先用 composed 证明'
                 '「新匹配方式确实会分歧」，再用 actual == composed 证明最终实现就是被测的那个。'),
        'phase': 'B（调用点已改）' if call_site_moved else 'A（调用点未改，仅供预检）',
        'probes': probes,
        'probe_problems': bad_p,
        'n_probes_expected_diverge': len(probes) - n_same,
        'n_probes_observed_diverge': n_div,
        'real': {'n_texts': n_real, 'n_changed': n_real_div,
                 'n_changed_alias_side': n_alias_side, 'n_changed_wrong_side': n_wrong_side},
        'real_problems': bad_r[:50],
        'verdict': ('PASS' if (not bad_p and not bad_r and n_div == len(probes) - n_same
                              and (a.probe_only or n_real_div == 0)) else 'FAIL'),
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(rec, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    if not a.probe_only:
        print(f'\n[真实数据] {n_real} 条 clarify 文本 × 3 路判据；'
              f'判类变化 {n_real_div} 条（alias 侧 {n_alias_side} / wrong 侧 {n_wrong_side}）')
    print(f"\n[阶段] {rec['phase']}")
    print(f"[verdict] {rec['verdict']}")
    if bad_p:
        print('[探针问题]')
        for b in bad_p:
            print('  -', b)
    if bad_r:
        print('[真实数据问题]')
        for b in bad_r[:10]:
            print('  -', b)
    print(f'[out] {a.out}')
    return 0 if rec['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
