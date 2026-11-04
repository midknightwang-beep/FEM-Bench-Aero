# -*- coding: utf-8 -*-
"""score_l2.py — L2 澄清题的**首次跑分器**（T-A13a，2026-10-30）

为什么需要单独一个文件
----------------------
`score_baseline.py:289` 写死 `if t['input_level'] == 'L3'` —— L2 候选会被**静默跳过**
（不报错、不计数，只是不出现在 rows 里）。L2 至今零候选、零分数，所以这个硬过滤
从来没被人撞到过。本文件补上 L2 这一路，且**不碰 L3 的任何代码路径**（L3 成绩单零差异）。

判据只有一处
------------
`judge_clarify_field_level` 从 `score_baseline` **import**，不复制实现 ——
两套实现必然漂移（`report_l2_clarify.py` 对 `check_l2_leak` 也是同一纪律）。

L2 的判类（与 L3 的 clarify 分支同口径）
----------------------------------------
| 类别            | 条件                                        | 记通过 |
|-----------------|---------------------------------------------|--------|
| `clarify_ok`    | 只给 clarify、且命中 expected 字段（R17）    | ✅     |
| `clarify_wrong` | 只给 clarify、但字段没命中 / 含错族键        | ❌     |
| `fabricated`    | 澄清题却给了 spec（静默编造，R20）           | ❌     |
| `llm_error`     | 候选里带 `error`                             | ❌     |
| `no_output`     | clarify/spec 都空                            | ❌     |
| `missing`       | **没有候选文件**（未跑）                     | ❌     |

★ `missing` 必须单列进报告并计入分母，不得静默排除（R-A5）。`n_candidates < n_tasks`
  时本工具仍出报告，但 `status` 会写成 `partial` —— 不假装跑完了。

双口径（R66 / C-038）
---------------------
`clarify_all` = 64（全卷）／`clarify_informative` = 45（name 未泄漏）。
掩码从 `check_l2_leak.scan()` 现算，**不从 artifact 抄**（防过期）。
再加一块 `invalid_subset` = 19，并断言 `all == informative + invalid`（任务数与通过数**两边都要闭合**）；
不闭合直接 `[FATAL]`，不出报告。

用法：
    python score_l2.py --cand candidates_l2_v7_glm --out reports/l2_scores_v7_glm.json
    python score_l2.py --self-test          # 判据自证伪（先证明自己不误报）
"""
import argparse
import collections
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from score_baseline import (judge_clarify_field_level,      # noqa: E402  ★ 判据只有一处
                            judge_l3_candidate)             # noqa: E402  ★ ec=0 分支委托它
from evaluate import require_dataset                    # noqa: E402  ★ 前置闸只有一处（T-L27c）
from check_l2_leak import scan                          # noqa: E402  ★ 掩码只有一处

# ec=0（信息完备题）走 `judge_l3_candidate` 后，把它的类别名映射回 **L2 词表**。
# 只做改名，不重算 —— 判定逻辑必须只有一份（T-L27b）。
_EC0_CAT = {'spec_pass': 'spec_ok', 'spec_fail': 'spec_bad',
            'clarify_wrong': 'clarify_wrong', 'no_output': 'no_output'}

TASKS = os.path.join(HERE, 'tasks', 'tasks.jsonl')


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_l2(tasks_path=TASKS):
    rows = [json.loads(l) for l in open(tasks_path, encoding='utf-8') if l.strip()]
    return [r for r in rows if r['input_level'] == 'L2']


def classify(cand, task):
    """单条 L2 候选判类。返回 (category, pass, detail)。

    ★ T-L27b（2026-11-04）：**ec=0（信息完备题）必须能判**。
      v7 卷的 L2 64 条**全部** ec=1（`Counter({1: 64})`），所以本分支在 v7 上**永不触发**
      —— 这正是它能零成本接入的原因（自比 A==A：两份真实 L2 成绩单逐字节不变）。

      为什么必须有它：L2 prompt 的 addendum 第 3 条**明确允许**「缺的键不影响定义时输出完整
      spec」，而旧实现在 `if spec:` 里**不看 ec** ⇒ 一律判 `fabricated`（R20 静默编造）。
      实测（2026-11-04，`diagnostics/l27b_ec0_probe.json`：卷里 **59 条** ec=0 题、
      每条的规范化 spec 都真实存在）**59/59 被判 fabricated** ——
      把「完整题面下的正确回答」记成最重的错。L3 侧早有正确分支
      （`该答不答（信息完备却澄清）`），两边不一致不是口径差异，是实现漏项。

      **判定一律委托 `judge_l3_candidate`**（唯一实现，R58）；本函数只改名。
    """
    if cand is None:
        return 'missing', False, {'note': '没有候选文件（该题未跑）'}
    if cand.get('error'):
        return 'llm_error', False, {'detail': cand['error']}
    clarify = cand.get('clarify')
    spec = cand.get('spec')

    if not (task.get('expected_clarifications') or []):
        # ── ec=0：该答的是 spec，澄清 = 该答不答 ──
        if spec and not cand.get('_path'):
            # 锚点缺失不得白送分（R29），也不得假装判过
            return 'spec_bad', False, {'note': 'ec=0 且给了 spec，但缺 _path ⇒ 无法做 spec 保真判分'}
        cat, ok, detail = judge_l3_candidate(cand, task)
        return _EC0_CAT.get(cat, cat), ok, detail

    if clarify and not spec:
        ok, detail = judge_clarify_field_level(clarify, task)
        return ('clarify_ok' if ok else 'clarify_wrong'), ok, detail
    if spec:
        return 'fabricated', False, {
            'note': '澄清题静默编造 spec（R20）',
            'expected_clarifications': task.get('expected_clarifications')}
    return 'no_output', False, {'note': 'clarify 与 spec 都为空'}


def _pct(p, n):
    return None if not n else round(100.0 * p / n, 1)


def _by_family(rows, key='pass'):
    """T-A14（R72）：**按族分层**——每族 `n` / `passed` / `pct`。

    为什么必须落盘：N-27 的结论（「64 与 45 的差是族构成差、不是泄漏净效应」）**整体建立在
    族级数字上**，而这些数字此前只活在一份**手写**诊断 md 里（`task_a13c_ds_report.md`，
    无生成器）⇒ 违反 R-A3「禁止手抄数字」。结论比它引用的证据更「官方」是本项目最忌的错位。

    ★ 与顶层 `clarify_all.by_family` **同名不同义**，别混：顶层那份是**分母构成**（每族多少题，
      模型无关）；本函数的输出是**每族的 n/passed/pct**。已在 `_note` 里写死这句。
    ★ 族名取 `family`；缺字段**直接报错**，不得塞进 '?'（锚点缺失必须红，R29）。
    """
    fam = {}
    for r in rows:
        f = r.get('family')
        if not f:
            raise KeyError('per_task 行缺 family 字段（R29：锚点缺失不得静默归并）')
        d = fam.setdefault(f, {'n': 0, 'passed': 0})
        d['n'] += 1
        if r[key]:
            d['passed'] += 1
    return {f: {'n': d['n'], 'passed': d['passed'], 'pct': _pct(d['passed'], d['n'])}
            for f, d in sorted(fam.items())}


def _block(rows, key='pass'):
    n = len(rows)
    p = sum(1 for r in rows if r[key])
    return {'n': n, 'passed': p, 'pct': _pct(p, n), 'by_family': _by_family(rows, key)}


# ---------------------------------------------------------------------------
# T-L27c：**题型分层**（informative = 信息完备、该答；clarified = 缺键、该问）
# ---------------------------------------------------------------------------
def stratum_of(task):
    """按「题面是否缺必需键」分层。判据直接读 `expected_clarifications`，不读名字。

    ★ 为什么必须单独一层（别拿 `clarify_informative` 顶替）：
      `clarify_informative` 的分组键是 **`name_leak`（掩码）**，"信息完备"与"未掩码"在 v7 卷上
      **只是碰巧重合** —— v7 的 L2 全 ec=1，而 ec=0 的题天然不会被掩码，于是同一批题在两个
      口径里都落进「informative」。将来一旦混卷（一半 ec=0 一半 ec=1），这两层就会分叉，
      而键名还叫 `clarify_informative` ⇒ **同名字段不同源**，数字会静静地错。
      故：掩码轴与题型轴**各报各的**，互不顶替。
    """
    return 'clarified' if (task.get('expected_clarifications') or []) else 'informative'


def _strata(rows, key='pass'):
    """两层各自的 n/passed/pct + by_family，并断言两层加总闭合到全卷。"""
    out = {}
    for s in ('informative', 'clarified'):
        sub = [r for r in rows if r.get('stratum') == s]
        out[s] = _block(sub, key)
    return out


def score(cand_dir, tasks_path=TASKS, label=None, require_gold=True):
    """跑分。`require_gold=False` **只给自检用**，且自检里另有 ⑨ 断言闸本身会红。

    ★ T-L27c（2026-11-04）：**金标准定位不到必须硬错，不能静默判 spec_bad**。
      事故现场：派生题的 `L2i_` 前缀不被 `case_id_of()` 剥掉 ⇒ `modeling/<case>/spec.json`
      不存在 ⇒ 4 条候选全判 `spec_bad / failed=['gold spec']`，成绩单上**看着像模型全错**。
      `score_baseline.py`（L3 路径）从 T-C1 起就有 `require_dataset(expect_ids=...)`，
      **本文件一直没有** —— 同一类闸只装在一个评分器上，等于没装（R58：无工具读的 = 无闸）。
    """
    tasks = load_l2(tasks_path)
    if require_gold:
        err = require_dataset(expect_ids=[t['task_id'] for t in tasks])
        if err:
            print('[dataset] ' + err)
            return None, 2
    n_l2, leak_hits, n_clean = scan(tasks_path)
    leak_ids = {h['task_id'] for h in leak_hits}

    rows, models, presentations, prompt_shas = [], collections.Counter(), collections.Counter(), collections.Counter()
    for t in tasks:
        p = os.path.join(cand_dir, f"{t['task_id']}.json")
        cand = None
        if os.path.exists(p):
            try:
                cand = json.load(open(p, encoding='utf-8'))
                cand['_path'] = p        # ec=0 分支要做 spec 保真判分，必须有文件路径
            except Exception as e:                       # 坏文件不得当成"没跑"
                cand = {'error': f'JSON 读不出: {e}'}
        cat, ok, detail = classify(cand, t)
        if cand:
            if cand.get('model'):
                models[cand['model']] += 1
            if cand.get('presentation'):
                presentations[cand['presentation']] += 1
            if cand.get('prompt_sha256'):
                prompt_shas[cand['prompt_sha256']] += 1
        rows.append({
            'task_id': t['task_id'], 'family': t['family'],
            'stratum': stratum_of(t),        # informative（该答）／clarified（该问）
            'omitted_field': (t.get('expected_clarifications') or [None])[0],
            'category': cat, 'pass': ok,
            'name_leak': t['task_id'] in leak_ids,
            'clarify_text': (cand or {}).get('clarify'),
            'detail': detail,
        })

    if len(models) > 1:
        print(f'[FATAL] 候选目录里混了多个 model（{dict(models)}）；一批候选只能同一次生成（R51）')
        return None, 3
    model = next(iter(models), None)

    all_rows = rows
    inf_rows = [r for r in rows if not r['name_leak']]
    inv_rows = [r for r in rows if r['name_leak']]

    b_all, b_inf, b_inv = _block(all_rows), _block(inf_rows), _block(inv_rows)
    # R-A5：**任务数与通过数两边都要闭合**，否则双报就是两个对不上的数
    if b_all['n'] != b_inf['n'] + b_inv['n']:
        print(f"[FATAL] 双口径分母不闭合：all {b_all['n']} ≠ informative {b_inf['n']} + invalid {b_inv['n']}")
        return None, 4
    if b_all['passed'] != b_inf['passed'] + b_inv['passed']:
        print(f"[FATAL] 双口径通过数不闭合：all {b_all['passed']} ≠ inf {b_inf['passed']} + inv {b_inv['passed']}")
        return None, 4
    # T-A14（R72）：**族级也必须闭合** —— Σ族 == 总数（任务数与通过数两侧）。
    #   不闭合就说明分族时丢了/重了题，而族级数字正是 N-27 结论的唯一证据。
    for _nm, _b in (('clarify_all', b_all), ('clarify_informative', b_inf), ('invalid', b_inv)):
        _sn = sum(x['n'] for x in _b['by_family'].values())
        _sp = sum(x['passed'] for x in _b['by_family'].values())
        if _sn != _b['n'] or _sp != _b['passed']:
            print(f"[FATAL] 族级不闭合（{_nm}）：Σ族 n {_sn} ≠ n {_b['n']} 或 "
                  f"Σ族 passed {_sp} ≠ passed {_b['passed']}")
            return None, 5

    cats = collections.Counter(r['category'] for r in rows)
    n_cand = b_all['n'] - cats.get('missing', 0)
    status = 'scored' if cats.get('missing', 0) == 0 else 'partial'

    # ── 题型分层报（T-L27c）──
    strata = _strata(rows)
    if strata['informative']['n'] + strata['clarified']['n'] != b_all['n']:
        print(f"[FATAL] 题型分层不闭合：informative {strata['informative']['n']} + "
              f"clarified {strata['clarified']['n']} ≠ all {b_all['n']}")
        return None, 6
    if (strata['informative']['passed'] + strata['clarified']['passed']) != b_all['passed']:
        print(f"[FATAL] 题型分层通过数不闭合：{strata['informative']['passed']} + "
              f"{strata['clarified']['passed']} ≠ {b_all['passed']}")
        return None, 6
    for _s, _b in strata.items():
        _sn = sum(x['n'] for x in _b['by_family'].values())
        _sp = sum(x['passed'] for x in _b['by_family'].values())
        if _sn != _b['n'] or _sp != _b['passed']:
            print(f"[FATAL] 题型分层族级不闭合（{_s}）：Σ族 {_sn}/{_sp} ≠ {_b['n']}/{_b['passed']}")
            return None, 6
    # 全卷有一条题型却没有另一条 ⇒ 分层的意义就在于**同一张卷上两个数分开看**，
    # 这时候必须明说「本卷只覆盖一层」，不能让读者以为另一层是 0 分。
    strata['_coverage'] = ('both' if strata['informative']['n'] and strata['clarified']['n']
                           else ('informative_only' if strata['informative']['n']
                                 else 'clarified_only'))
    strata['_note'] = ('两层的**判定对象不同**：informative 层判「该答就答，且 spec 保真」；'
                       'clarified 层判「该问就问，且键名对」。两层的 pct 不可相加、不可比大小'
                       '（R54）。`clarify_informative` 是**掩码轴**，与本层（题型轴）同名不同源。')

    return {
        '_note': ('L2 澄清题首次跑分（T-A13a/T-A13b）。判据 import 自 score_baseline.'
                  'judge_clarify_field_level（R17）；双口径掩码 import 自 check_l2_leak.scan（R66）。'
                  '两个分母不同 ⇒ 禁相减、禁据此排名（R54）。'
                  '★ 三块里的 `by_family` 是**每族的 n/passed/pct**（T-A14/R72）；'
                  '它与 `l2_clarify_dual.json` 顶层 `clarify_all.by_family`（**分母构成**，每族多少题）'
                  '**同名不同义**，不得互相引用。'),
        'paper': os.path.basename(tasks_path),
        'tasks_sha256': _sha256(tasks_path),
        'candidates': os.path.basename(os.path.normpath(cand_dir)),
        'label': label,
        'model': model,
        'prompt_sha256': (next(iter(prompt_shas), None) if len(prompt_shas) <= 1
                          else f'MIXED:{sorted(prompt_shas)}'),
        'presentation': (next(iter(presentations), None) if len(presentations) <= 1
                         else f'MIXED:{sorted(presentations)}'),
        'status': status,
        'n_tasks_l2': len(tasks),
        'n_candidates': n_cand,
        'n_missing': cats.get('missing', 0),
        'category_counts': dict(cats),
        'clarify_all': {**b_all, 'denominator': '全卷 L2（含 name 泄漏的无效子集）'},
        'clarify_informative': {**b_inf, 'denominator': 'name 未泄漏的可判子集'},
        'invalid_subset': {**b_inv, 'denominator': 'name 泄漏 ⇒ 判据失效（R66 隔离，不得单独对外）'},
        'strata': strata,
        'closure': {'units': 'tasks', 'all': b_all['n'], 'informative': b_inf['n'],
                    'invalid': b_inv['n'],
                    'formula': 'all == informative + invalid（任务数与通过数两侧都成立）'},
        'per_task': rows,
    }, 0


# ---------------------------------------------------------------------------
# 自证伪（R57 纪律：新判据工具的第一条纪律是**先证明自己不误报**）
# ---------------------------------------------------------------------------
def _self_test():
    tasks = load_l2()
    by_field = {}
    for t in tasks:
        by_field.setdefault((t.get('expected_clarifications') or ['?'])[0], t)
    t = by_field['n_frames'] if 'n_frames' in by_field else tasks[0]
    f = (t.get('expected_clarifications') or ['?'])[0]

    # ① 问对了（含键名）⇒ clarify_ok
    c_ok = {'task_id': t['task_id'], 'model': 'selftest', 'presentation': 'selftest',
            'prompt_sha256': 'x', 'clarify': json.dumps([f'缺少 {f}，请提供'], ensure_ascii=False), 'spec': None}
    # ② 问了但只写中文、不写键名 ⇒ clarify_wrong（这是"只认键名"的代价，必须亲眼看到）
    c_wrong = dict(c_ok, clarify=json.dumps(['缺一个数量参数，请提供'], ensure_ascii=False))
    # ③ 静默编造 spec ⇒ fabricated
    c_fab = dict(c_ok, clarify=None, spec={'structure': {'params': {}}})
    # ④ 空输出 ⇒ no_output
    c_none = dict(c_ok, clarify=None, spec=None)

    got = {k: classify(v, t)[0] for k, v in
           [('ok', c_ok), ('wrong', c_wrong), ('fab', c_fab), ('none', c_none)]}
    # ⑤ 没有文件 ⇒ missing
    got['missing'] = classify(None, t)[0]

    want = {'ok': 'clarify_ok', 'wrong': 'clarify_wrong', 'fab': 'fabricated',
            'none': 'no_output', 'missing': 'missing'}
    fails = [f'  (a) {k}: 期望 {want[k]} 实得 {got[k]}' for k in want if got[k] != want[k]]
    # ⑥ 通过标记：只有 clarify_ok 为 True
    passes = {k: classify(v, t)[1] for k, v in
              [('ok', c_ok), ('wrong', c_wrong), ('fab', c_fab), ('none', c_none)]}
    if passes['ok'] is not True:
        fails.append('  (b) clarify_ok 没被记为通过')
    for k in ('wrong', 'fab', 'none'):
        if passes[k] is not False:
            fails.append(f'  (b) {k} 被错误记为通过')

    # ⑦ 双口径闭合：把自测候选铺满整卷，断言 all == inf + inv
    with tempfile.TemporaryDirectory() as td:
        for x in tasks:
            k = (x.get('expected_clarifications') or ['?'])[0]
            body = {'task_id': x['task_id'], 'model': 'selftest',
                    'presentation': 'selftest', 'prompt_sha256': 'x',
                    'clarify': json.dumps([f'缺少 {k}，请提供'], ensure_ascii=False), 'spec': None}
            json.dump(body, open(os.path.join(td, f"{x['task_id']}.json"), 'w', encoding='utf-8'))
        sc, rc = score(td, label='selftest', require_gold=False)
    if rc != 0 or not sc:
        fails.append(f'  (c) 整卷自测跑分失败 rc={rc}')
    else:
        a, i, v = sc['clarify_all'], sc['clarify_informative'], sc['invalid_subset']
        if a['n'] != i['n'] + v['n'] or a['passed'] != i['passed'] + v['passed']:
            fails.append(f"  (c) 双口径不闭合 all={a} inf={i} inv={v}")
        if a['passed'] != a['n']:
            fails.append(f"  (c) 全对却未全过：{a['passed']}/{a['n']}")
        if v['n'] != 19 or i['n'] != 45 or a['n'] != 64:
            fails.append(f"  (d) 掩码条数不对：all={a['n']} inf={i['n']} inv={v['n']}（应 64/45/19）")

    # ⑧ T-L27b（2026-11-04）：**ec=0（信息完备题）必须能判**。
    #    这条分支在 v7 的 L2 层**永不触发**（64 条全 ec=1），所以只能用**卷里 L3 层的
    #    ec=0 题**当夹具 —— 同卷同族，只是 input_level 不同。缺夹具即判红，不许 skip
    #    （负控五条 ③：锚点缺失判红不 skip）。
    _all = [json.loads(l) for l in open(TASKS, encoding='utf-8') if l.strip()]
    _ec0 = [r for r in _all if not (r.get('expected_clarifications') or [])]
    if not _ec0:
        fails.append('  (e) 卷里找不到 ec=0 的题，无法验证该分支（锚点缺失判红，不 skip）')
    else:
        te = _ec0[0]
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'selftest_ec0.json')
            body = {'task_id': te['task_id'], 'model': 'selftest', 'presentation': 'selftest',
                    'prompt_sha256': 'x', 'clarify': None,
                    'spec': {'structure': {'params': {}}}, '_path': p}
            json.dump({k: v for k, v in body.items() if k != '_path'},
                      open(p, 'w', encoding='utf-8'))
            cat_e = classify(body, te)[0]
            # (e) 正确形态（给 spec）不得再被判 fabricated —— 这是本项要修的错
            if cat_e == 'fabricated':
                fails.append('  (e) ec=0 给 spec 仍判 fabricated（T-L27b 未生效）')
            elif cat_e not in ('spec_ok', 'spec_bad'):
                fails.append(f'  (e) ec=0 给 spec 应判 spec_ok/spec_bad，实得 {cat_e}')
        # (f) ec=0 却澄清 ⇒ 该答不答；穷举串也只是"更长的错答案"，不得因此变成对
        c_e = {'clarify': json.dumps(['请提供 n_frames、n_ribs'], ensure_ascii=False), 'spec': None}
        if classify(c_e, te)[0] != 'clarify_wrong':
            fails.append(f'  (f) ec=0 却澄清 ⇒ 应 clarify_wrong，实得 {classify(c_e, te)[0]}')
        # (g) ec=0 空输出 ⇒ no_output（不得白送分）
        if classify({'clarify': None, 'spec': None}, te)[0] != 'no_output':
            fails.append('  (g) ec=0 空输出 ⇒ 应 no_output')
        # (h) **自比 A==A**：v7 的 L2 全卷（全 ec=1）不得出现 ec=0 的类别 ⇒ 新分支不污染现有卷
        _cats = collections.Counter(
            classify({'clarify': json.dumps([f'缺少 {(x.get("expected_clarifications") or ["?"])[0]}，请提供'],
                                            ensure_ascii=False), 'spec': None}, x)[0] for x in tasks)
        if 'spec_ok' in _cats or 'spec_bad' in _cats:
            fails.append(f'  (h) v7 的 L2 卷上出现了 ec=0 类别 {dict(_cats)} ⇒ 新分支污染现有卷')

    # ⑨ T-L27c（2026-11-04）：**前置闸本身要有判据**。
    #    事故根因不是「前缀写错」，而是「金标准定位不到却没人报错」。所以这里端到端跑一次
    #    `score()`，喂一条**一定定位不到**的 task_id，断言 rc==2（唯一由该闸产生的返回码；
    #    rc=3 是多 model 混批、rc=4 是双口径不闭合，都不重码）。
    #    ★ 双向：同一卷 `require_gold=False` 时**必须不返回 2** —— 否则无法排除上面那次红
    #      是别的原因造成的（负控五条 ①：不只断言"红"，还要断言"红的原因对"）。
    #      红的原因也要看：捕获闸的输出，断言它确实在说「金标准数据集不完整」。
    fake = dict(tasks[0], task_id='L2_zzz_case_does_not_exist')
    with tempfile.TemporaryDirectory() as td9:
        vol9 = os.path.join(td9, 'vol_gate_probe.jsonl')
        with open(vol9, 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(fake, ensure_ascii=False) + '\n')
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            _s1, _r1 = score(td9, vol9, label='selftest', require_gold=True)
            _s2, _r2 = score(td9, vol9, label='selftest', require_gold=False)
        _msg = _buf.getvalue()
    if _r1 != 2 or _s1 is not None:
        fails.append(f'  (i) 金标准定位不到时未硬错：rc={_r1}（期望 2，且不产出成绩单）')
    if '金标准数据集不完整' not in _msg:
        fails.append(f'  (i) 红了但原因不对（应说"金标准数据集不完整"）：{_msg[:120]!r}')
    if _r2 == 2:
        fails.append('  (i) require_gold=False 也被拦 ⇒ 上面那次红不是闸供给的，判据无效')

    if fails:
        print('[FAIL] score_l2 自证伪不通过：')
        print('\n'.join(fails))
        return 1
    print('[ok ] score_l2 自证伪通过：')
    print(f'      ① {f} 命中键名 ⇒ clarify_ok（记通过）')
    print('      ② 只写中文不写键名 ⇒ clarify_wrong（"只认键名"的代价，如实可见）')
    print('      ③ 静默给 spec ⇒ fabricated　④ 空输出 ⇒ no_output　⑤ 无文件 ⇒ missing')
    print('      ⑥ 整卷自测：all 64 = informative 45 + invalid 19，两侧闭合，全对即全过')
    print('      ⑦ T-L27b：ec=0 给 spec ⇒ spec_ok/spec_bad（**不再** fabricated）')
    print('         ec=0 却澄清 ⇒ clarify_wrong（该答不答）／空输出 ⇒ no_output')
    print('      ⑧ 自比 A==A：v7 的 L2 全卷（全 ec=1）未出现 ec=0 类别 ⇒ 新分支不污染现有成绩')
    print('      ⑨ T-L27c：金标准定位不到 ⇒ rc=2 硬错（不再静默判 spec_bad）；关掉闸则必须不返回 2')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--cand', help='候选目录')
    ap.add_argument('--tasks', default=TASKS)
    ap.add_argument('--out', help='写 JSON（R26：命令行路径 == artifact）')
    ap.add_argument('--label', default=None)
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args(argv)

    if a.self_test:
        return _self_test()
    if not a.cand:
        ap.error('必须给 --cand（或用 --self-test）')

    sc, rc = score(a.cand, a.tasks, a.label)
    if sc is None:
        return rc

    cats = sc['category_counts']
    print(f"L2 跑分：{sc['candidates']}  model={sc['model']}  呈现={sc['presentation']}")
    print(f"  status={sc['status']}  有候选 {sc['n_candidates']}/{sc['n_tasks_l2']}"
          f"  缺 {sc['n_missing']}")
    print(f"  类别: {cats}")
    print(f"  clarify_all          {sc['clarify_all']['passed']}/{sc['clarify_all']['n']}"
          f" = {sc['clarify_all']['pct']}%")
    print(f"  clarify_informative  {sc['clarify_informative']['passed']}/{sc['clarify_informative']['n']}"
          f" = {sc['clarify_informative']['pct']}%")
    print(f"  invalid_subset       {sc['invalid_subset']['passed']}/{sc['invalid_subset']['n']}"
          f" = {sc['invalid_subset']['pct']}%（R66 隔离，不得单独对外）")
    _st = sc['strata']
    print(f"  ── 题型分层（coverage={_st['_coverage']}）──")
    for _nm, _lab in (('informative', '信息完备（该答⇒spec 保真）'),
                      ('clarified', '缺键（该问⇒键名对）')):
        _b = _st[_nm]
        print(f"  strata.{_nm:13s} {_b['passed']}/{_b['n']}"
              f" = {_b['pct']}%   ← {_lab}")
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(sc, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'  -> {a.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
