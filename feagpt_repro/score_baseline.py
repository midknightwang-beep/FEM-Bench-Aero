# -*- coding: utf-8 -*-
"""
score_baseline.py — W4d L3 主基线成绩单（W4e 按专家第四轮修正：exam/dev 分栏）

四指标分层（红线 R9：SFR≠MSR≠TSR）：
  TSR（主 KPI，行为正确性）= 完备题 spec_fidelity PASS + 澄清题字段级问对（clarify_aliases，
        R17：单字关键词不得作为通过依据；含错族键名 clarify_wrong_keys ⇒ FAIL）
        —— 澄清题静默编造 spec = 0 分（拍板「问对=对，编造=错」）
  SFR（字段保真）= spec_fidelity PASS / 产出 spec 的候选
        —— R20（W4e）：fabricated ⇒ SFR FAIL（SFR 与 TSR 编造口径一致，不得并列矛盾报告）
  FPR（双向）= 该澄清不澄清（编造）/ 该答不答（过度澄清）
  MSR（全链可用率）见 msr 节（msr_l3.py 产出，红线 R14/R16）

W4e（专家第四轮 P0-1/R15）：headline 只用 exam = boundary_holdout + extrapolation_test；
train+val 单列 dev（开发/诊断），不进对外。underpowered = n_exam < 20（红线 R12）。
value_added = exam TSR_LLM − exam TSR_T1（地板同任务集 exam 口径，不用 all_pct）。

W5a'（专家第六轮 P0-1/P0-2/P1-8，红线 R25/R27）：
  - 输出默认写 reports/（**入库**，非 eval_runs/），文件名必须带版本；
  - --paper 记录考卷 provenance（tasks 路径 + sha256），成绩单自带溯源；
  - --candidates 默认 candidates_l3_v3，并在输出里显式记录实际目录（不再静默 v2）。
"""
import json, os, sys, re, hashlib, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluate import evaluate_one, load_tasks, RUNS, require_dataset
from _paths import rel   # T-A11a：跨盘符安全（见 _paths.py）

EXAM_SPLITS = ('boundary_holdout', 'extrapolation_test')
# W5b（RUBRIC §1.1，老王拍板）：exam 三栏——boundary / extrapolation 来自 dataset split，
# interpolation 是任务层内插留出（split_v2 仍为 train）。headline = 合并 25，三栏明细必须并列。
STRATA = ('boundary', 'extrapolation', 'interpolation')
# ★ T-A11a（v7 / C-037 双分母，R66）：v1.1 新增 9 条内插考卷的 stratum 是 `interpolation_v11`。
#   它**必须自成一个桶**，三条错路都试过、都不自洽：
#   · 混进 STRATA ⇒ `exam` 变 34，与 C-032 的 25 不同分母 ⇒ R53/R54 禁止并列、禁止相减；
#   · 折进 dev ⇒ dev 从 30 变 39，dev 数字跨版本不可比（R-A6），且「dev 只作开发诊断」被污染；
#   · `is_exam` 改判 `st is not None` 而 `exam_by_stratum` 仍只遍历三栏 ⇒
#     三栏加起来 25 却把 n 报成 34，`exam_definition` 印出「= 34」而明细只有 25 ⇒ 分母不闭合（R-A5）。
#   ⇒ 唯一自洽的记法是四桶互斥且穷尽：
#     exam(legacy) + exam_v11 + dev == n_tasks，且 exam_full == exam + exam_v11。
STRATA_V11 = ('interpolation_v11',)   # v1.1 新增内插（C-037 双分母的 v11 一侧）
STRATA_ALL = STRATA + STRATA_V11


def scorecard_coverage_problems(sc):
    """成绩单覆盖自检（W5b-3，专家第七轮 NC-28 / R31）。

    为什么：v6 考卷 55 条 L3，若候选只有 30 条（例如只跑了老题）就出成绩单，
    exam 会「看着 n=25、其实只有一部分被打分」，而且**不报错**——静默出半张成绩单。
    返回问题列表；空列表 = 覆盖完整。
    """
    probs = []
    prov = sc.get('provenance') or {}
    n_paper = sc.get('n_tasks_in_paper')
    n_cand = prov.get('n_candidates', sc.get('n_tasks'))
    miss = sc.get('candidates_missing') or []
    if n_paper is None:
        probs.append('成绩单缺 n_tasks_in_paper（旧版成绩单，无法判候选覆盖）')
    elif n_cand is None:
        probs.append('成绩单缺 provenance.n_candidates')
    elif n_cand < n_paper:
        probs.append(f'候选 {n_cand} < 考卷 {n_paper} 条（缺 {len(miss) or n_paper - n_cand} 条'
                     + (f'：{",".join(miss[:5])}{"..." if len(miss) > 5 else ""}' if miss else '') + '）')
    if sc.get('partial_candidates'):
        probs.append('partial_candidates=True（候选未覆盖全卷）')
    if sc.get('partial'):
        probs.append(f"partial=True（exam 实测 {sc.get('exam', {}).get('n')} < 期望 "
                     f"{sc.get('n_tasks_exam_expected')}）")
    return probs


def stratum_of(task):
    """任务的难度分层；老考卷（v4/v5）没有 exam_stratum ⇒ 回退到 split_v2 映射（向后兼容）。"""
    s = task.get('exam_stratum')
    if s:
        return s
    if task.get('split_v2') == 'boundary_holdout':        return 'boundary'
    if task.get('split_v2') == 'extrapolation_test':
        return 'extrapolation'
    # W5c（R36）：v6c 起内插留出在任务层是独立 split（旧卷只有 exam_stratum）
    if task.get('split_v2') == 'interpolation_test':
        return 'interpolation'
    return None


def is_exam_legacy(task):
    """**主口径** exam 谓词（三栏 25 条）—— C-032 同分母，对外一切 `exam` 都指这个。

    ★ T-A11a：这个函数是**唯一**的 legacy 判据。改之前，判 exam 的写法散在四处
      （scorecard 的 `st is not None`、msr_l3 的 `bool(exam_stratum)`、
       trivial_baselines 的 `stratum_of is not None`、bootstrap 读 `is_exam` 字段），
      v7 一来四处一起错、错法还不一样（有的把 9 条算进 exam，有的塞进 dev）。
      **判据散着写 = 迟早不一致**（与 relpath 那个坑同型）。
    """
    return stratum_of(task) in STRATA


def is_exam_full(task):
    """**并列口径** exam_full = legacy + v11（C-037 双分母）。与 legacy 只可并列、**不可相减**（R54）。"""
    return stratum_of(task) in STRATA_ALL

# R25：官方 artifact 一律写 reports/（被 git 追踪），eval_runs/ 只作工作目录
REPORT_DIR = os.path.join(HERE, 'reports')


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ══════════════════════════════════════════════════════════════════════════
# 判分元数据修正表（T-P1a / R71）
# ══════════════════════════════════════════════════════════════════════════
# ★ 为什么要有这一层，而不是直接改 `tasks/tasks.jsonl`：
#   `tasks.jsonl` 与 `reports/papers/tasks_v7.jsonl` 同 sha，是**冻结件**；
#   S-52 的卷链语义是「跨版只许加行、不许改老行」⇒ 改一行会让链断，
#   并连带作废所有下游 sha 锚点（r32 artifact 的 `paper_sha256`、成绩单 provenance、S-57）。
#   把修正单独成表：卷不动、sha 不变、修正可审计可回滚，且反过来多一条可判不变量（S-59）。
#
# ★ 用途边界（R71）：**只许修事实错误**（登记与 R34 键名契约矛盾），
#   不得用于改阈值、改口径、或让某个模型好看。每条必须带 reason + evidence，
#   且 `from` 必须逐字等于当前卷现值（卷一变，表自动失效，不会静默留用）。
OVERRIDES_PATH = os.path.join(HERE, 'tasks', 'clarify_wrong_keys_fix.json')
_OV_CACHE = {'path': None, 'mtime': None, 'data': None}


def load_judge_overrides(path=None):
    """→ {(task_id, field): fix_dict}。文件不存在 = 无修正（正常态）。"""
    p = path or OVERRIDES_PATH
    if not os.path.exists(p):
        return {}
    mt = os.path.getmtime(p)
    if _OV_CACHE['path'] == p and _OV_CACHE['mtime'] == mt and _OV_CACHE['data'] is not None:
        return _OV_CACHE['data']
    raw = json.load(open(p, encoding='utf-8'))
    out = {}
    for f in (raw.get('fixes') or []):
        out[(f.get('task_id'), f.get('field'))] = f
    _OV_CACHE.update({'path': p, 'mtime': mt, 'data': out})
    return out


def _effective_wrong_keys(task):
    """→ (wrong_keys, override_applied_or_None)

    应用的充要条件：表里有 (task_id, 'clarify_wrong_keys')，**且** `from` 与卷现值逐字相等。
    `from` 不等 ⇒ 表已过期 ⇒ **不应用**，并在 detail 里如实标 `skipped`（不静默）。
    """
    raw = task.get('clarify_wrong_keys')
    cur = raw if isinstance(raw, list) else []
    ov = load_judge_overrides().get((task.get('task_id'), 'clarify_wrong_keys'))
    if not ov:
        return cur, None
    if sorted(cur) != sorted(ov.get('from') or []):
        return cur, {'skipped': 'from 与当前卷现值不符（修正表已过期，S-59 会报红）',
                     'current': cur, 'table_from': ov.get('from')}
    return list(ov.get('to') or []), {
        'field': 'clarify_wrong_keys',
        'from': cur,
        'to': list(ov.get('to') or []),
        'reason': (ov.get('reason') or '')[:160],
        'table_version': (json.load(open(OVERRIDES_PATH, encoding='utf-8')).get('_version')
                          if os.path.exists(OVERRIDES_PATH) else None),
    }


def judge_overrides_provenance(tasks=None):
    """成绩单里记录「用了哪张修正表、sha 多少、实际应用在哪些题」——防止「用了却没记」。"""
    p = OVERRIDES_PATH
    if not os.path.exists(p):
        return {'path': None, 'sha256': None, 'n_fixes': 0, 'applied_to': []}
    raw = json.load(open(p, encoding='utf-8'))
    fixes = raw.get('fixes') or []
    applied = []
    if tasks:
        for f in fixes:
            t = tasks.get(f.get('task_id'))
            if t is None:
                continue
            cur = t.get('clarify_wrong_keys')
            if isinstance(cur, list) and sorted(cur) == sorted(f.get('from') or []):
                applied.append(f.get('task_id'))
    return {
        'path': rel(os.path.abspath(p)),
        'sha256': sha256_file(p),
        'version': raw.get('_version'),
        'n_fixes': len(fixes),
        'applied_to': sorted(applied),
        'note': ('判分元数据修正表（R71）：只许修「与 R34 键名契约矛盾」的事实错误；'
                 'from 必须等于卷现值，否则不应用（S-59 守）。'),
    }


def _candidate_model(cand_dir):
    """从候选文件里读模型 id（W5c-6c / R48 溯源）。

    为什么不从命令行传：命令行参数是「人声称的」，候选文件里的 `model` 是
    **生成时实际 pin 的 id**，只有后者可验证。一批里出现多个 id ⇒ 返回
    `MIXED:<ids>` 显式标明，不猜、不取多数。
    """
    ids = set()
    try:
        for fn in sorted(os.listdir(cand_dir)):
            if not fn.endswith('.json'):
                continue
            try:
                with open(os.path.join(cand_dir, fn), encoding='utf-8') as f:
                    m = json.load(f).get('model')
            except Exception:
                continue
            if m:
                ids.add(m)
    except Exception:
        return None
    if not ids:
        return None
    return sorted(ids)[0] if len(ids) == 1 else 'MIXED:' + ','.join(sorted(ids))


def _candidate_prompt_sha(cand_dir):
    """读候选文件里的 `prompt_sha256`（R53，W5c-6d）。

    ★ 为什么必须有：同一张考卷（`tasks_sha256` 相同）**不代表可比** —— 改 prompt 后
      重生成，卷子一个字没变，但 harness 变了。旧的 `compare_scorecards.py` 只比卷 sha，
      于是「C-029 旧 prompt × C-032 新 prompt」会被判成「可比」，进而允许相减（R53 禁止）。
    旧批次没有这个字段 ⇒ 返回 `UNKNOWN`（**不得当"相同"处理**，UNKNOWN vs 任何值都不可比）。
    """
    ids = set()
    try:
        for fn in sorted(os.listdir(cand_dir)):
            if not fn.endswith('.json'):
                continue
            try:
                with open(os.path.join(cand_dir, fn), encoding='utf-8') as f:
                    ids.add(json.load(f).get('prompt_sha256'))
            except Exception:
                continue
    except Exception:
        return 'UNKNOWN'
    ids.discard(None)
    if not ids:
        return 'UNKNOWN'          # 旧批次：生成时未记录
    if len(ids) > 1:
        return 'MIXED:' + ','.join(sorted(ids))
    return ids.pop()


def _alias_hit(alias, text):
    """别名命中判定（T-A13d / R70）：**纯 ASCII 标识符按 token 边界，其余按子串**。

    为什么需要边界（N-28，旧账见 `_audit_clarify_meta.py` W5c-6d）：
      裸子串 `a in text` 在「键名是另一个键名的前缀/后缀」时会**静默假通过** ——
      `n_stringers` 被 `n_stringers_per_skin` 命中、`thickness` 被
      `skin_thickness`/`rib_thickness`/`stringer_thickness` 命中、
      `width` 被 `stringer_flange_width` 命中。
      **它不留「本该过没过」的痕迹，只让数字偏高**（与 N-26 恒真式、N-17 name 泄漏同族）。

    为什么只约束 ASCII（R69 边界）：
      中文没有词边界概念，且本项目 25 个 alias 里 21 个是中文短语
      （`翼肋`/`孔径`/`多少根长桁`…）。对中文加边界会把「翼肋数量」判成不命中
      —— 那是**把判据改坏**，不是加固。真正的子串风险只在 4 个纯 ASCII 标识符上。

    ★ 仍必须允许的写法（本例就是它们的自证）：`structure.params.n_stringers`（前面是点）、
      `n_stringers（根数）`（后面是中文括号）、`"n_stringers"`（JSON 引号）——
      边界只约束**标识符字符** `[A-Za-z0-9_]`，不约束其它分隔符。
    """
    if re.fullmatch(r'[A-Za-z0-9_]+', alias):
        return re.search(r'(?<![A-Za-z0-9_])' + re.escape(alias) + r'(?![A-Za-z0-9_])',
                         text) is not None
    return alias in text


def _n_questions(cand):
    """问句条数 —— **只观测，不参与任何判定**（P-1 裁定 / R71）。

    ★ 为什么只观测：把「多问」做成判 FAIL 的判据，实测既不可靠也不公平 ——
      ① 按语义判（是否提到别的键名）4/4 假阳性（模型是在解释「题面给了 X 但没给 Y」）；
      ② 按条数判，代价几乎全落在单侧（L2 上 glm 掉 0 条、ds 掉 8 条）⇒ 等于按模型调阈值。
    ★ clarify 是「字符串里装的 JSON 数组」（`'["a","b"]'`）⇒ 必须 json.loads 后再取 len，
      按标点切分会得到假分布（首版 glm 3 / ds 8 的假象即由此而来）。
    """
    cl = cand.get('clarify')
    if cl is None:
        return 0
    if isinstance(cl, list):
        return len(cl)
    try:
        v = json.loads(cl)
        return len(v) if isinstance(v, list) else 1
    except Exception:
        return 1


def judge_clarify_field_level(text, task):
    """字段级澄清判分（R17）。返回 (ok, detail)。

    规则（预注册于 RUBRIC.md）：
      - 必须【命中 expected 字段的别名】（clarify_aliases[field] 之一，含正确键名或语义短语）；
      - 且【不含错族键名】（clarify_wrong_keys——其他族的同义键，键名即契约 R19）。
    """
    aliases = task.get('clarify_aliases') or {}
    # ★ T-P1a / R71：错族键走修正表。判定逻辑本身没变 —— 变的只是「哪几个键算错族」，
    #   而那是 R34 键名契约的事实问题（表里 `from` 必须等于卷现值，否则不应用）。
    wrong, _ov = _effective_wrong_keys(task)
    fields = task.get('expected_clarifications') or []
    if not fields:
        return False, {'note': '任务未登记 expected_clarifications'}
    # 任务层两种形态兼容：dict(field→aliases) 或 list（与 expected_clarifications 逐位对齐）
    # ★ T-A13d / R70：命中判定统一走 `_alias_hit`（ASCII 标识符按 token 边界）。
    #   原式 `[k for k in wrong if k in text] if isinstance(wrong, list) else \
    #          [k for k in (wrong if isinstance(wrong, list) else []) if k in text]`
    #   两个分支**完全等价**（else 分支里 isinstance 必为 False ⇒ 恒空列表）⇒ 是死代码。
    #   这里保留 `isinstance` 守卫：`wrong` 若不是 list（如误写成 str），
    #   必须仍取空列表，**不能**逐字符迭代 —— 否则与旧行为不等价。
    hit_wrong = [k for k in (wrong if isinstance(wrong, list) else []) if _alias_hit(k, text)]
    detail = {'text': text[:200], 'expected': fields}
    if _ov:
        # 留痕：这条题用了修正表（或表已过期被跳过）。不进判定，只进证据。
        detail['wrong_keys_override'] = _ov
    if hit_wrong:
        detail['wrong_keys_hit'] = hit_wrong
        detail['note'] = '问题使用了错族键名（键名即契约，R19）'
        return False, detail
    per_field = {}
    ok_all = True
    for i, f in enumerate(fields):
        if isinstance(aliases, dict):
            al = aliases.get(f) or [f]
        else:
            # list 形态 = 该题别名全集（扁平 str 数组；单/多字段题共用一个池）
            al = aliases or [f]
        hit = [a for a in al if _alias_hit(a, text)]
        per_field[f] = hit
        if not hit:
            ok_all = False
    detail['alias_hits'] = per_field
    if not ok_all:
        detail['note'] = '存在 expected 字段未被任何别名命中'
    return ok_all, detail


def judge_l3_candidate(cand, task):
    """单条 L3 候选判类。返回 (category, pass_for_tsr, detail)。"""
    tid = task['task_id']
    ec = task.get('expected_clarifications') or []
    if cand.get('error'):
        return 'llm_error', False, {'detail': cand['error']}
    if cand.get('clarify') and not cand.get('spec'):
        if ec:
            ok, detail = judge_clarify_field_level(cand['clarify'], task)
            return ('clarify_ok' if ok else 'clarify_wrong'), ok, detail
        return 'clarify_wrong', False, {'clarify': cand['clarify'][:150],
                                        'note': '该答不答（信息完备却澄清）'}
    if cand.get('spec') and ec:
        return 'fabricated', False, {'note': f"澄清题静默编造 spec（缺 {ec}）",
                                     'expected_clarifications': ec}
    if cand.get('spec'):
        r = evaluate_one(task, cand['_path'], skip_solve=True)
        sf = r['gates'].get('spec_fidelity', {})
        failed = [f['field'] for f in (sf.get('failed') or [])]
        cat = 'spec_pass' if r['overall_pass'] else 'spec_fail'
        return cat, r['overall_pass'], {
            'n_fields': sf.get('n_fields'), 'n_fail': sf.get('n_fail'),
            # W5c-5b（R44）：字段级命中率的分母必须剔除恒 pass 的「只报不判」声明项，
            # 否则与 T1+ 地板的命中率不同口径、不可比。
            'n_fields_gated': sf.get('n_fields_gated'),
            'failed_fields': failed[:6],
            'exec_config_mismatch': len(sf.get('exec_config_mismatch') or []),
            'dead_fields_skipped': len(sf.get('dead_fields_skipped') or [])}
    return 'no_output', False, {'note': '3 轮修复未收敛（UNRESOLVED）'}


def agg(rows, key):
    """对 rows 子集聚合 tsr/sfr。"""
    n = len(rows)
    tsr_p = sum(1 for r in rows if r['tsr_pass'])
    spec_rows = [r for r in rows if r['category'] in ('spec_pass', 'spec_fail', 'fabricated')]
    # R20：fabricated 一律不计 SFR PASS（与 TSR 编造口径一致）
    sfr_p = sum(1 for r in spec_rows if r['category'] == 'spec_pass')
    return {'n': n,
            'tsr': {'pass': tsr_p, 'total': n, 'pct': round(100 * tsr_p / max(1, n), 1)},
            'sfr': {'pass': sfr_p, 'of_spec_candidates': len(spec_rows),
                    'pct': round(100 * sfr_p / max(1, len(spec_rows)), 1)},
            'categories': dict(collections.Counter(r['category'] for r in rows))}


def main():
    err = require_dataset()          # W5a'：缺 gold 数据集必须硬报错，不能静默算成 0/11
    if err:
        print('[dataset] ' + err)
        return 2
    argv = sys.argv[1:]
    def get(k, d):
        return argv[argv.index(k) + 1] if k in argv else d
    cand_dir = get('--candidates', os.path.join(HERE, 'candidates_l3_v3'))
    tasks_path = get('--tasks', os.path.join(HERE, 'tasks', 'tasks.jsonl'))
    report_dir = get('--report-dir', REPORT_DIR)
    report_path = get('--report', os.path.join(report_dir, 'baseline_scorecard_L3.json'))
    trivial_path = get('--trivial', os.path.join(report_dir, 'trivial_baselines_L3.json'))
    n_tasks_exam_arg = int(get('--n-tasks-exam', '0'))
    label = get('--label', '')
    os.makedirs(os.path.dirname(os.path.abspath(report_path)) or '.', exist_ok=True)
    # ★ W5c-6f（专家第十轮 §3.2 / R51）：顶层 `model` **不得硬编码**。
    #   此前 `'model': 'glm-5.3-flash'` 写死 ⇒ C-031（deepseek-v4-pro）的成绩单顶层也写 glm，
    #   只读模型标签的读者会以为「第二模型还是 glm」，而 provenance.model 才是 deepseek。
    #   跨模型 artifact 的模型标签只能来自**候选文件里生成时实际 pin 的 id**；
    #   命令行 --model 属于「人声称的」，只用来交叉核对，不得覆盖实测值。
    model_measured = _candidate_model(cand_dir)
    model_claim_cli = get('--model', '')
    if model_measured is None:
        print('[FATAL] 候选文件里没有 model 字段 ⇒ 无法溯源是哪个模型生成的；拒绝出成绩单（R51）')
        return 3
    if model_measured.startswith('MIXED:'):
        print(f'[FATAL] 候选目录里混了多个 model（{model_measured}）；一批候选只能是同一次生成（R51）')
        return 3
    if model_claim_cli and model_claim_cli != model_measured:
        print(f'[FATAL] --model={model_claim_cli} 与候选实测 model={model_measured} 不符（R51）')
        return 3
    print(f'[score_baseline] candidates={os.path.basename(cand_dir)}  tasks={tasks_path}')
    print(f'[score_baseline] model={model_measured}（读自候选文件，不是默认值）')

    tasks = {t['task_id']: t for t in load_tasks(tasks_path)
             if t['input_level'] == 'L3'}
    # ★ T-C1（D-6 第二级）：上面那次 `require_dataset()` 只证明「目录在、里面有 spec.json」；
    #   这里再查**覆盖**——目录非空但不全时，缺的那几条会被静默判成 spec_fail。
    #   只对 L3 查（`modeling/` 只覆盖 L3；L1/L2 是纯文本题，不该因缺 gold 而阻断）。
    #   两次调用是有意为之：保留「缺数据优先于其它错误」的既有报错顺序。
    err = require_dataset(expect_ids=sorted(tasks))
    if err:
        print('[dataset] ' + err)
        return 2
    # W5b：exam 期望条数从考卷自动推（硬编码 11 在扩到 25 条后会让 partial 判断失真）
    # ★ T-A11a：必须按 `in STRATA` 数，不能按 `is not None`——v7 里 v11 也非空，
    #   若数成 34 则 `partial = (25 < 34) = True`，成绩单会被自己判成「半张」，误报。
    n_tasks_exam = n_tasks_exam_arg or sum(1 for t in tasks.values() if stratum_of(t) in STRATA)
    n_tasks_exam_full = sum(1 for t in tasks.values() if stratum_of(t) in STRATA_ALL)
    rows = []
    for fn in sorted(os.listdir(cand_dir)):
        if not fn.endswith('.json'):
            continue
        cand = json.load(open(os.path.join(cand_dir, fn), encoding='utf-8'))
        tid = cand.get('task_id')
        t = tasks.get(tid)
        if t is None:
            continue
        cand['_path'] = os.path.join(cand_dir, fn)
        cat, ok, detail = judge_l3_candidate(cand, t)
        st = stratum_of(t)
        rows.append({'task_id': tid, 'split_v2': t['split_v2'], 'family': t['family'],
                     'category': cat, 'tsr_pass': ok,
                     'exam_stratum': st,
                     # R66：`is_exam` 保持 **legacy 语义**（三栏 25 条）——它是历史成绩单的口径，
                     # 也是 bootstrap_ci.py 唯一的输入谓词（`r.get('is_exam')`）。v11 另开
                     # `is_exam_full`，使 bootstrap 零改动即自动只对 legacy 做 CI（不会静默换分母）。
                     'is_exam': st in STRATA,
                     'is_exam_full': st in STRATA_ALL,
                     'ec': bool(t.get('expected_clarifications')),
                     'n_questions': _n_questions(cand),
                     'turns_used': cand.get('turns_used'), **detail})

    exam_rows = [r for r in rows if r['is_exam']]               # legacy 三栏（v6c/v7 都是 25，与 C-032 同口径）
    exam_v11_rows = [r for r in rows if r['exam_stratum'] in STRATA_V11]
    exam_full_rows = [r for r in rows if r['is_exam_full']]      # = legacy + v11
    # ★ 只认 None 才进 dev：v11 绝不能折进 dev（否则 dev 30→39，跨版本不可比，R-A6）
    dev_rows = [r for r in rows if r['exam_stratum'] is None]
    n_exam = len(exam_rows)
    n_exam_v11 = len(exam_v11_rows)
    n_exam_full = len(exam_full_rows)
    # R-A5 / R52：四桶必须互斥且穷尽（`exam_stratum` 只可能是 STRATA / STRATA_V11 / None 之一）
    _buckets = n_exam + n_exam_v11 + len(dev_rows)
    if _buckets != len(rows):
        print(f'[FATAL] exam/dev 桶不闭合：exam {n_exam} + v11 {n_exam_v11} + dev {len(dev_rows)}'
              f' = {_buckets} ≠ 候选 {len(rows)} 条（R-A5/R52）——拒绝出成绩单')
        return 4
    if n_exam_full != n_exam + n_exam_v11:
        print(f'[FATAL] exam_full {n_exam_full} ≠ exam {n_exam} + v11 {n_exam_v11}（R66 双分母不闭合）')
        return 4

    fab = [r for r in rows if r['category'] == 'fabricated']
    clar_wrong = [r for r in rows if r['category'] == 'clarify_wrong']
    n_ec = sum(1 for r in rows if r['ec'])

    stratum_counts = collections.Counter(r['exam_stratum'] for r in exam_rows)
    v11_counts = collections.Counter(r['exam_stratum'] for r in exam_v11_rows)
    fam_counts = collections.Counter(r['family'] for r in exam_rows)
    dev_split = collections.Counter(r['split_v2'] for r in dev_rows)
    turns_hist = collections.Counter(r['turns_used'] for r in rows if r.get('turns_used'))
    n_unresolved = sum(1 for r in rows if r['category'] == 'no_output')
    paper_tag = os.path.basename(tasks_path).replace('tasks_', '').replace('.jsonl', '')
    exam_ids = sorted(r['task_id'] for r in exam_rows)

    scorecard = {
        # W5c（专家第八轮 §3.7 / R38）：这三条字符串**必须由考卷推出来**，不得再硬编码 W4d 文案
        'note': (f'W5c L3 主基线（考卷 {paper_tag} × 候选 {os.path.basename(cand_dir)}，文案由考卷自动生成）：'
                 f'headline = exam {n_exam} 条（exam_stratum 三栏 '
                 f'boundary {stratum_counts.get("boundary", 0)} / extrapolation '
                 f'{stratum_counts.get("extrapolation", 0)} / interpolation '
                 f'{stratum_counts.get("interpolation", 0)}）；dev（非 exam）{len(dev_rows)} 条只作开发诊断。'
                 f'TSR=行为正确性（完备题答对+澄清题字段级问对 R17）；SFR=字段保真（R20：编造一律不计 PASS）；'
                 f'FPR 双向；MSR 全链见 msr 节（R14/R16/R35：solver 失败单列，不进 exam MSR）。')
                 + (f'★ v1.1 双分母（C-037 / R66）：另有 exam_v11 {n_exam_v11} 条（interpolation_v11），'
                    f'exam_full = {n_exam_full} 条；本 note 与顶层 `exam` 一律是 legacy {n_exam} 条'
                    f'（与 C-032 同分母，R53/R54 只禁跨分母相减、不禁并列）。' if n_exam_v11 else ''),
        'model': model_measured,   # R51：实测自候选文件，不再是硬编码默认值
        'model_source': 'candidate files (per-task field `model`), 单一值；非默认、非命令行声称',
        'decode': 'json_object + schema_task.json 校验 + 错误反馈修复循环（<=3 轮；SDK 无 logits 级 json_schema）',
        # ★ T-A11a：老卷（无 v11）**逐字保留原文案**，只在有 v11 时改用修正表述——
        #   否则「exam = exam_stratum 非空」这句在 v7 上就是**错的**（v11 非空但不进 exam）。
        'exam_definition': (
            (f'exam = exam_stratum 非空 = boundary {stratum_counts.get("boundary", 0)} '
             f'+ extrapolation {stratum_counts.get("extrapolation", 0)} '
             f'+ interpolation {stratum_counts.get("interpolation", 0)} = {n_exam}（RUBRIC §1.1；'
             if not n_exam_v11 else
             f'exam(legacy) = exam_stratum ∈ {{boundary, extrapolation, interpolation}} = '
             f'boundary {stratum_counts.get("boundary", 0)} '
             f'+ extrapolation {stratum_counts.get("extrapolation", 0)} '
             f'+ interpolation {stratum_counts.get("interpolation", 0)} = {n_exam}'
             f'（RUBRIC §1.1；exam_full = exam(legacy) + interpolation_v11 '
             f'{v11_counts.get("interpolation_v11", 0)} = {n_exam_full}，C-037 双分母、R54 只禁相减；'
             ) +
            (f'dev = 既非 exam 也非 exam_v11 {len(dev_rows)} 条 = ' if n_exam_v11
             else f'dev = 非 exam {len(dev_rows)} 条 = ') +
            # `or '无'`：冒烟（只跑几条）时 dev 桶可能为空，否则会印出「= ）」
            (' + '.join(f'{k} {v}' for k, v in sorted(dev_split.items())) or '无') + '）（R15/R36）'),
        # W5c（R39）：跨卷比较按 task-id 集，不按条数——条数相同也可能换了一批题
        'exam_task_ids_sha256': hashlib.sha256(
            json.dumps(exam_ids, ensure_ascii=False).encode('utf-8')).hexdigest(),
        'exam_by_family': dict(fam_counts),
        'turns_histogram': {str(k): v for k, v in sorted(turns_hist.items())},
        'first_pass_valid': turns_hist.get(1, 0),
        'n_unresolved': n_unresolved,
        'provenance': {   # W5a'（R25/R27）：成绩单自带溯源，替代「靠人记当时跑了什么」
            'label': label,
            'tasks_path': rel(os.path.abspath(tasks_path)),
            'tasks_sha256': sha256_file(tasks_path),
            'candidates_dir': rel(os.path.abspath(cand_dir)),
            # ★ W5c-6c（R48）：跨模型对比必须能从成绩单**直接看出是哪个模型**。
            # 旧版不记 model ⇒ C-031 的「第二模型」要翻候选目录才能验证，等于不可溯源。
            # 取候选文件里声明的 model；若一批里不一致（混模型）就显式标 MIXED，不猜。
            'model': model_measured,
            # ★ R53：同卷 sha 相同 **不等于** 可比；prompt 也要同源。旧批次无此字段 ⇒ UNKNOWN。
            'prompt_sha256': _candidate_prompt_sha(cand_dir),
            'prompt_sha256_note': ('读自候选文件（生成时对 SYS prompt 取的 sha256）。'
                                   'UNKNOWN = 该批候选生成时未记录 ⇒ 与任何批次都不可比（R53）'),
            'n_candidates': len(rows),
            'generated_by': 'score_baseline.py',
            # ★ T-P1a / R71：判分元数据修正表必须留痕 —— 否则「用了表却没记」，
            #   两份成绩单用不同口径判分而看不出差别（与「prompt sha 未记」同族事故）。
            'judge_overrides': judge_overrides_provenance(tasks),
        },
        'n_tasks': len(rows),
        # W5b-3（专家第七轮 NC-28）：候选覆盖必须显式记账——v6 考卷 55 条，
        # 若只拿 30 条候选出成绩单，exam 会「看着 n=25、其实只有 13 条被打分」，
        # 而且不报错（静默出半张成绩单），比报错危险得多。
        'n_tasks_in_paper': len(tasks),
        'candidates_missing': sorted(set(tasks) - {r['task_id'] for r in rows}),
        'n_tasks_exam_expected': n_tasks_exam,
        'n_tasks_exam_full_expected': n_tasks_exam_full,
        'partial': n_exam < n_tasks_exam,
        'partial_full': n_exam_full < n_tasks_exam_full,
        'partial_candidates': len(rows) < len(tasks),
        'underpowered': n_exam < 20,
        'tsr': agg(rows, 'tsr')['tsr'],
        'exam': agg(exam_rows, 'exam'),
        # ★ T-A11a（C-037 / R66）：v1.1 双分母。`exam` 恒为 legacy（与 C-032 同分母），
        #   `exam_full` = exam + exam_v11。两者**并列可读、禁止相减**（R54：34 ≠ 25）。
        'exam_v11': ({**agg(exam_v11_rows, 'exam_v11'),
                      'note': 'v1.1 新增内插（interpolation_v11）单独成桶：既不是 legacy exam、'
                              '也不是 dev。不单列会污染另一侧（折进 exam ⇒ 换分母，折进 dev ⇒ 30→39）。'}),
        'exam_full': {**agg(exam_full_rows, 'exam_full'),
                      'note': 'exam_full = exam(legacy) + exam_v11（C-037 双分母）。'
                              '与 C-032 的 exam 25 条**不可相减**（R54），只可并列陈述。'},
        # R-A5 闭合：四桶互斥穷尽，且 exam_full == exam + v11
        'exam_denominator_closure': {
            'exam_legacy': n_exam, 'exam_v11': n_exam_v11, 'exam_full': n_exam_full,
            'dev': len(dev_rows), 'n_tasks': len(rows),
            'closure_sum': n_exam + n_exam_v11 + len(dev_rows),
            'ok': (n_exam + n_exam_v11 + len(dev_rows) == len(rows)
                   and n_exam_full == n_exam + n_exam_v11),
        },
        'dev': {**agg(dev_rows, 'dev'), 'note': '开发集，不进对外（R15）'},
        'sfr_all': agg(rows, 'all')['sfr'],
        'fpr': {'fabricated_on_clarify_tasks': len(fab), 'n_clarify_tasks': n_ec,
                'fabrication_rate_pct': round(100 * len(fab) / max(1, n_ec), 1),
                'overclarify': len([r for r in clar_wrong if not r['ec']]),
                'clarify_wrong_field': len([r for r in clar_wrong if r['ec']])},
        'by_split': {s: agg([r for r in dev_rows if r['split_v2'] == s], s)
                     for s in sorted({r['split_v2'] for r in dev_rows})},
        # W5c（专家第八轮 §3.5 / S-24 / R36）：by_split 只统计**非 exam** 行。
        # 旧版把 6 条内插考题算进 train（n=19 = 13 纯 train + 6 内插），
        # 于是「train 15/19」既不是纯 train 也不是 exam，两不像。
        'by_split_note': (f'by_split 仅含非 exam 行（R36）；exam {n_exam} 条另见 exam_by_stratum。'
                          f'纯 train = {dev_split.get("train", 0)} 条。'),
        # W5b：exam 三栏明细（RUBRIC §1.1——合并报会虚高，必须拆开看难度）
        # ★ T-A11a：改成按 **exam_full** 遍历 `STRATA_ALL`（v6c 上等价于三栏 ⇒ 逐字不变），
        #   这样 v7 会多出 `interpolation_v11` 一栏，四栏相加 == exam_full.n ⇒ 明细与总数闭合。
        #   若仍只遍历三栏，会出现「四栏明细加起来 25、exam_full 报 34」的静默漏 9 条。
        'exam_by_stratum': {s: agg([r for r in exam_full_rows if r['exam_stratum'] == s], s)
                            for s in STRATA_ALL if any(r['exam_stratum'] == s for r in exam_full_rows)},
        'exam_by_stratum_note': ('按 exam_full 遍历 STRATA_ALL 分栏；v7 起含 interpolation_v11 一栏。'
                                 '四栏之和 == exam_full.n（R-A5 闭合）'),
        'per_task': rows,
    }

    # value_added（exam 口径，R15/P1-10：不再用 all_pct）
    # ★ W5c-5b（专家第九轮 §3.3 / R44）：TSR 地板在 exam 上恒为 0（T0/T1/T1+ 全 0，族内 oracle 也 0），
    #   原因是 spec_fidelity **全或无** + 族内几何参数逐条唯一 ⇒ 「0 地板」是判据的必然，不是基线太弱。
    #   ⇒ 必须与地板**字段级命中率**并列报（连续尺度，才有区分度）；verdict 仍按 ≥10 pp，但两种尺度都写。
    if os.path.exists(trivial_path):
        trivial = json.load(open(trivial_path, encoding='utf-8'))
        t1p = trivial.get('T1plus_family') or {}
        floors = [(nm, rec.get('exam_pct')) for nm, rec in
                  (('T1_retrieval', trivial['T1_retrieval']), ('T1plus_family', t1p))
                  if rec.get('exam_pct') is not None]
        floor_used, floor_pct = max(floors, key=lambda x: x[1]) if floors else ('T1_retrieval', 0.0)
        llm_exam = scorecard['exam']['tsr']['pct']
        # LLM 字段级命中率（同口径：分母取 n_fields_gated）
        # ★★ W5c-6c（跨模型对比暴露的口径 bug）：旧版写
        #       hits = [... for r in exam_rows if r.get('n_fields_gated')]
        #   这会**静默排除**一切没走 spec_fidelity 的题 —— 包括 `fabricated`（编造）
        #   与 `clarify_wrong`（答非所问）。那些题本该记 0，却被当成"不存在"。
        #   实证：C-029（glm）exam = 20 spec_pass + 2 spec_fail + **3 clarify_ok**；
        #         C-031（dsv4pro）= 20 spec_pass + 2 spec_fail + **3 fabricated**。
        #   两边都被排除 3 条 ⇒ 都算出 99.34%，**数字相同、含义相反**
        #   （C-029 排除的是合法澄清，C-031 排除的是编造）。
        #   修法：按 category 显式分流 + 落盘分母构成，禁止靠 `if 值存在` 隐式过滤。
        #   合法澄清（clarify_ok）不计字段（该答就答，无 spec 可判）；
        #   其余"该判 spec 却没给 spec"的一律记 0（编造/答非所问/空输出）。
        hits, n_excl_clarify, n_zero_nonspec = [], 0, 0
        for r in exam_rows:
            cat = r.get('category')
            if cat == 'clarify_ok':
                n_excl_clarify += 1
                continue
            g = r.get('n_fields_gated')
            if g:
                hits.append((g - (r.get('n_fail') or 0)) / g)
            elif cat in ('fabricated', 'clarify_wrong', 'llm_error', 'no_output',
                         'contract_fail', 'solver', 'env'):
                hits.append(0.0)     # 该判 spec 却没给 spec ⇒ 字段级记 0，不排除
                n_zero_nonspec += 1
            else:
                n_excl_clarify += 1  # 未知类别：排除但计入 n_excluded，便于发现
        llm_hit = round(sum(hits) / len(hits), 4) if hits else None
        floor_hit = t1p.get('avg_field_hit_rate_exam')
        scorecard['value_added'] = {
            'basis': f'exam 三栏 {n_exam} 条 TSR（地板取 T1 与 T1+ 的高者；T1/T1+ 均 leave-one-out，R40/R44）。'
                     '★ TSR 地板恒 0 是全或无判分的必然（族内参数逐条唯一，族内 oracle 0/25）'
                     '⇒ 另报字段级命中率作为连续尺度对照',
            'TSR_floor_used': floor_used,
            'TSR_T1_exam_pct': trivial['T1_retrieval']['exam_pct'],
            'TSR_T1plus_exam_pct': t1p.get('exam_pct'),
            'TSR_LLM_exam_pct': llm_exam,
            'delta_pp': round(llm_exam - floor_pct, 1),
            'field_level': {
                'floor_hit_rate': floor_hit,
                'llm_hit_rate': llm_hit,
                'delta_pp': (round(100 * (llm_hit - floor_hit), 1)
                             if (llm_hit is not None and floor_hit is not None) else None),
                'floor_n_fields_gated_avg': t1p.get('n_fields_gated'),
                'floor_n_fail_exam': t1p.get('n_fail_exam'),
                # R47（W5c-6c）：分母必须显式落盘，禁止隐式过滤
                'n_exam_counted': len(hits),
                'n_excluded_clarify_ok': n_excl_clarify,
                'n_zero_non_spec': n_zero_nonspec,
                'note': '地板 = 逐字段族级众数（不读输入的最强策略）；'
                        'n_fail_exam 是地板「差几个受判字段才过」的分布。'
                        '分母构成：n_exam_counted = 计入题数（含记 0 的编造题），'
                        'n_excluded_clarify_ok = 合法澄清（无 spec 可判，排除），'
                        'n_zero_non_spec = 编造/答非所问（**记 0，不排除**）。'},
            'criterion': '>= 10 pp 才算 LLM 真有增量（专家 6.3.1）；n_exam<20 ⇒ underpowered 不得判 PASS（R12）',
            'verdict': ('PASS' if (llm_exam - floor_pct >= 10 and n_exam >= 20) else
                        'BELOW' if llm_exam - floor_pct < 10 else 'UNDERPOWERED')}

        # ★ W5c-6c / R49：两个尺度**可能给出相反结论**（实证：C-031 任务级 Δ80 pp PASS，
        #   字段级仅 Δ1.5 pp BELOW）。这种分裂必须由成绩单自己标出来，
        #   否则文档可以只引有利的一侧（典型 cherry-pick）。
        _lv_d = scorecard['value_added']['field_level'].get('delta_pp')
        _tv = scorecard['value_added']['verdict']
        _lv = ('PASS' if (_lv_d is not None and _lv_d >= 10) else
               'BELOW' if _lv_d is not None else 'N/A')
        scorecard['value_added']['field_level']['verdict'] = _lv
        scorecard['value_added']['verdict_split'] = (
            f'任务级 {_tv} / 字段级 {_lv}（Δ{_lv_d} pp）—— 两尺度结论相反，'
            '文档必须并列报，禁止只引有利的一侧（R49）'
            if _lv != 'N/A' and ((_tv == 'PASS') != (_lv == 'PASS')) else None)

    # W5a：scorecard 重打分时保留既有 msr_section（MSR 由 msr_l3.py 单独产出，
    # 重打分不得抹掉；NC-22 依赖顶层 exam.msr 存在）
    prev_msr = None
    if os.path.exists(report_path):
        try:
            prev_msr = json.load(open(report_path, encoding='utf-8')).get('msr_section')
        except Exception:
            prev_msr = None
    if prev_msr:
        scorecard['msr_section'] = prev_msr
        # W5c：顶层 msr 也要一并保留 —— 此前顶层 `msr` 一直是 null（没人写），
        # 重打分后又会被写成缺省值，NC-36 因此报 msr=False。
        scorecard['msr'] = prev_msr.get('msr')
        scorecard['msr_pct'] = prev_msr.get('msr_pct')
        scorecard.setdefault('exam', {})['msr'] = prev_msr.get('exam_msr')
        scorecard.setdefault('dev', {})['msr'] = prev_msr.get('dev_msr')

    json.dump(scorecard, open(report_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    e = scorecard['exam']
    print('== L3 主基线成绩单（exam/dev 分栏，W4e）==')
    print(f"  EXAM  TSR {e['tsr']['pass']}/{e['n']} ({e['tsr']['pct']}%)  "
          f"SFR {e['sfr']['pass']}/{e['sfr']['of_spec_candidates']} ({e['sfr']['pct']}%)"
          f"   underpowered={scorecard['underpowered']}")
    d = scorecard['dev']
    print(f"  DEV   TSR {d['tsr']['pass']}/{d['n']} ({d['tsr']['pct']}%)  "
          f"SFR {d['sfr']['pass']}/{d['sfr']['of_spec_candidates']} ({d['sfr']['pct']}%)  (不进对外)")
    print(f"  分类(exam): {e['categories']}")
    for s, a in scorecard['exam_by_stratum'].items():
        print(f"  └ {s:<13} TSR {a['tsr']['pass']}/{a['n']} ({a['tsr']['pct']}%)"
              f"  SFR {a['sfr']['pass']}/{a['sfr']['of_spec_candidates']}")
    print(f"  FPR: 编造 {len(fab)}/{n_ec}、过度澄清 {scorecard['fpr']['overclarify']}、问错字段 {scorecard['fpr']['clarify_wrong_field']}")
    print(f"  turns: {scorecard['turns_histogram']}  一次通过 {scorecard['first_pass_valid']} 条"
          f"  未收敛 {scorecard['n_unresolved']} 条")
    if 'value_added' in scorecard:
        v = scorecard['value_added']
        print(f"  value_added(exam): 地板 {v['TSR_floor_used']} "
              f"(T1 {v['TSR_T1_exam_pct']}% / T1+ {v['TSR_T1plus_exam_pct']}%) "
              f"-> LLM {v['TSR_LLM_exam_pct']}% (Δ{v['delta_pp']}pp, {v['verdict']})")
        fl = v.get('field_level') or {}
        if fl.get('floor_hit_rate') is not None:
            print(f"  value_added(字段级): 地板 {100*fl['floor_hit_rate']:.2f}% "
                  f"-> LLM {100*(fl['llm_hit_rate'] or 0):.2f}% (Δ{fl['delta_pp']}pp；"
                  f"地板缺口中位 {fl['floor_n_fail_exam']['median']} 字段)")
            print(f"    分母构成: 计入 {fl.get('n_exam_counted')} / 合法澄清排除 "
                  f"{fl.get('n_excluded_clarify_ok')} / 编造记 0 {fl.get('n_zero_non_spec')}")
        if v.get('verdict_split'):
            print(f"  ★ 双尺度分裂: {v['verdict_split']}")
    cov = scorecard_coverage_problems(scorecard)
    if cov:
        print('  [WARN] 候选/考卷覆盖不全（NC-28/R31）：' + '；'.join(cov))
        print('         => 这份成绩单不得当正式成绩引用（exam 可能只覆盖部分任务）')
    else:
        print(f"  覆盖: 候选 {scorecard['provenance']['n_candidates']}/"
              f"{scorecard['n_tasks_in_paper']} 条（完整）")
    print('report ->', report_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
