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
  python check_claims.py --no-semantic  # 只做结构检查（旧行为）
  python check_claims.py --claims <path> --root <repo>   # 负控注入（NC-23/24/25）
  python check_claims.py --json reports/check_claims.json

### 语义计数自检（W5b-3，专家第七轮 P1-5，红线 R29）

结构检查只问「artifact 在不在、有没有被 git 追踪」，**抓不到文本里的数字**。第七轮复评实测
5 处漂移全部 PASS：C-010 写 140 行（实际 165）、C-011 写「真内插 = v1.1」（v6 已有 interp 6）、
C-019 coverage 写 27（实际 28）、C-027/RUBRIC/W5B_PLAN 写「C-021 的 19 条」（实际 11）、
README 同时写 RUBRIC v3.1 与 v4。**每轮靠人查不可持续 ⇒ 数字也上闸。**

做法：每条期望值都从 artifact **实读**，账本文本里的数字只作「声称值」；
声称值 != 实测值 ⇒ FAIL。注入模式（账本里没有 C-xxx claim，例如 NC-23..25 的临时账本）
自动跳过，只留一条 skip 记录。
"""
import argparse, collections, glob, hashlib, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # 仓库根 = F:/AI FEA Modeling DataSets
CLAIMS_DEFAULT = os.path.join(ROOT, 'FEM-Bench-Aero', 'CLAIMS.md')

PATH_RE = re.compile(r'[A-Za-z0-9_./\\:\-]+\.(?:jsonl|json|md|csv|tar\.gz|txt)')
FLAG_RE = re.compile(r'--(?:report|json|out|report-dir|md)\s+([^\s`;+]+)')
# W5c：产出方式不止 --out/--report。考卷快照是 `cp tasks/tasks.jsonl reports/papers/xxx.jsonl`，
# sha 清单是 `sha256sum … >> reports/papers/SHA256SUMS`。这两种也是**真实产出**，不纳入的话
# 结构检查会误判「artifact 与 command 不一致」（R26）。只补这两种，不引入通配。
CP_RE = re.compile(r'\bcp\s+[^\s`;+]+\s+([^\s`;+]+)')
APPEND_RE = re.compile(r'>>\s*([^\s`;+]+)')
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


# ==================== 语义计数自检（R29，专家第七轮 P1-5） ====================
TASKS_REL = 'feagpt_repro/tasks/tasks.jsonl'
SC_V4_REL = 'feagpt_repro/reports/baseline_scorecard_L3_v4.json'
SC_V6B_REL = 'feagpt_repro/reports/baseline_scorecard_L3_v6b.json'
SC_V6C_REL = 'feagpt_repro/reports/baseline_scorecard_L3_v6c.json'
PAPERS_V4_REL = 'feagpt_repro/reports/papers/tasks_v4.jsonl'
RUBRIC_REL = 'FEM-Bench-Aero/RUBRIC.md'
README_REL = 'FEM-Bench-Aero/README.md'
PLAN_REL = 'FEM-Bench-Aero/W5B_PLAN.md'
CLAIMS_REL_FOR_SEM = 'FEM-Bench-Aero/CLAIMS.md'
REQUIRED_CLAIMS = ('C-010', 'C-011', 'C-019', 'C-021', 'C-027', 'C-028')


def _measures(root):
    """从 artifact 实读所有「可核对的量」。缺文件就留空，由检查项显式报 FAIL。"""
    m = {}
    p = os.path.join(root, TASKS_REL)
    if os.path.exists(p):
        rows = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
        l3 = [r for r in rows if r.get('input_level') == 'L3']
        st = collections.Counter(r.get('exam_stratum') for r in l3)
        m['tasks'] = {'total': len(rows), 'n_l3': len(l3),
                      'boundary': st.get('boundary', 0),
                      'extrapolation': st.get('extrapolation', 0),
                      'interpolation': st.get('interpolation', 0)}
        m['tasks']['exam'] = (m['tasks']['boundary'] + m['tasks']['extrapolation']
                              + m['tasks']['interpolation'])
    p = os.path.join(root, SC_V4_REL)
    if os.path.exists(p):
        m['sc_v4'] = (json.load(open(p, encoding='utf-8')).get('exam') or {})
    p = os.path.join(root, SC_V6B_REL)
    if os.path.exists(p):
        d6 = json.load(open(p, encoding='utf-8'))
        ms6 = d6.get('msr_section') or {}
        m['sc_v6b'] = {'exam': d6.get('exam') or {},
                       'by_stratum': d6.get('exam_by_stratum') or {},
                       'msr': ms6.get('msr') or '',
                       'msr_pct': ms6.get('msr_pct'),
                       'exam_msr': ms6.get('exam_msr') or '',
                       'exam_msr_pct': ms6.get('exam_msr_pct'),
                       'sfr': (d6.get('exam') or {}).get('sfr') or {},
                       'by_split': d6.get('by_split') or {},
                       'exam_definition': d6.get('exam_definition') or '',
                       'value_added_basis': (d6.get('value_added') or {}).get('basis') or '',
                       'raw': d6}
    p = os.path.join(root, SC_V6C_REL)
    if os.path.exists(p):
        d7 = json.load(open(p, encoding='utf-8'))
        ms7 = d7.get('msr_section') or {}
        m['sc_v6c'] = {'exam': d7.get('exam') or {},
                       'by_stratum': d7.get('exam_by_stratum') or {},
                       'msr': ms7.get('msr') or '', 'msr_pct': ms7.get('msr_pct'),
                       'exam_msr': ms7.get('exam_msr') or '',
                       'exam_msr_pct': ms7.get('exam_msr_pct'),
                       'sfr': d7.get('exam', {}).get('sfr') or {},
                       'dev': d7.get('dev') or {}, 'fpr': d7.get('fpr') or {},
                       'n_solver': ms7.get('n_solver_excluded'),
                       'exam_by_family': d7.get('exam_by_family') or {},
                       'exam_task_ids_sha256': d7.get('exam_task_ids_sha256'),
                       'by_split': d7.get('by_split') or {},
                       'exam_definition': d7.get('exam_definition') or '',
                       'value_added_basis': (d7.get('value_added') or {}).get('basis') or '',
                       'raw': d7}
    # W5c（R29/R38）：headline 指针——有 v6c 就用 C-029×v6c，否则 C-028×v6b
    m['headline'] = ('C-029', m['sc_v6c']) if m.get('sc_v6c') else (('C-028', m['sc_v6b'])
                     if m.get('sc_v6b') else (None, {}))
    # W5c（R29/R36/R39）：headline 成绩单 → 对应考卷的 exam id 集 / 纯 train / 内插族分布
    _cid, _hl = m.get('headline') or (None, {})
    _tp = (((_hl.get('raw') or {}).get('provenance') or {}).get('tasks_path') or '')
    if _tp:
        _fp = os.path.join(root, _tp)
        if not os.path.exists(_fp):
            _fp = os.path.join(root, 'feagpt_repro', _tp)
        if os.path.exists(_fp):
            _rows = [json.loads(l) for l in open(_fp, encoding='utf-8') if l.strip()]
            _l3 = [r for r in _rows if r.get('input_level') == 'L3']
            m['paper_exam_ids'] = [r['task_id'] for r in _l3 if r.get('exam_stratum')]
            m.setdefault('tasks', {})
            m['tasks']['pure_train'] = sum(1 for r in _l3
                                           if r['split_v2'] == 'train' and not r.get('exam_stratum'))
            m['tasks']['interp_fams'] = dict(collections.Counter(
                r['family'] for r in _l3 if r.get('exam_stratum') == 'interpolation'))
    # C-028 的题面消歧计数（S-22）必须从 v4 / v6b 两版 paper 实算，不许手抄
    _p4 = os.path.join(root, PAPERS_V4_REL)
    _p6 = os.path.join(root, 'feagpt_repro', 'reports', 'papers', 'tasks_v6b.jsonl')
    if os.path.exists(_p4) and os.path.exists(_p6):
        _l4 = {t['task_id']: t['input']['nl'] for t in
               (json.loads(l) for l in open(_p4, encoding='utf-8') if l.strip())
               if t.get('input_level') == 'L3'}
        _l6 = {t['task_id']: t['input']['nl'] for t in
               (json.loads(l) for l in open(_p6, encoding='utf-8') if l.strip())
               if t.get('input_level') == 'L3'}
        _com = set(_l4) & set(_l6)
        m['nl_diff'] = {
            'coord_added': sum(1 for k in _com if '坐标系' in _l6[k] and '坐标系' not in _l4[k]),
            'dir_added': sum(1 for k in _com if re.search(r'方向\s*\[', _l6[k])
                             and not re.search(r'方向\s*\[', _l4[k])),
            'len_v4': round(sum(len(_l4[k]) for k in _com) / max(1, len(_com))),
            'len_v6b': round(sum(len(_l6[k]) for k in _com) / max(1, len(_com))),
        }
    p = os.path.join(root, PAPERS_V4_REL)
    if os.path.exists(p):
        rows = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
        c = collections.Counter(r.get('split_v2') for r in rows if r.get('input_level') == 'L3')
        m['v4'] = {'boundary': c.get('boundary_holdout', 0),
                   'extrapolation': c.get('extrapolation_test', 0)}
    ncs = glob.glob(os.path.join(root, 'feagpt_repro', 'reports', 'negative_controls_*.json'))
    if ncs:
        def _num(p):
            mm = re.search(r'_(\d+)\.json$', p)
            return int(mm.group(1)) if mm else -1
        best = max(ncs, key=_num)
        m['nc'] = json.load(open(best, encoding='utf-8'))
        m['nc_file'] = os.path.basename(best)
    return m


def _txt(path):
    return open(path, encoding='utf-8').read() if os.path.exists(path) else ''


def t1plus_consistency(trivial, scorecard):
    """R44（专家第九轮 §3.3）：T1+ 地板必须非空，且 value_added 引用的字段级地板必须与它**逐数相等**。

    为什么抽成模块级函数：S-32（正向）与 NC-39（反向注入）必须用**同一份**判据，
    各写一份就会漂（本项目的 R29 老坑：只打印不参与判定的检查不是检查）。
    """
    if not trivial or not isinstance(trivial, dict):
        return False, '缺 trivial_baselines artifact'
    t = trivial.get('T1plus_family')
    if not t:
        return False, 'T1plus_family 缺节（R44：value_added 只能标「技术 PASS、证据弱」）'
    if t.get('exam_pct') is None:
        return False, 'T1plus_family.exam_pct 为空'
    if t.get('avg_field_hit_rate_exam') is None:
        return False, '缺 avg_field_hit_rate_exam（字段级是唯一有区分度的对照尺度）'
    if not t.get('n_fail_exam'):
        return False, '缺 n_fail_exam（地板「差几个字段才过」无法量化）'
    va = ((scorecard or {}).get('value_added') or {}).get('field_level') or {}
    fh = va.get('floor_hit_rate')
    if fh is None:
        return False, 'value_added.field_level 缺 floor_hit_rate（成绩单没引用地板）'
    if abs(float(fh) - float(t['avg_field_hit_rate_exam'])) > 1e-9:
        return False, f'两份 artifact 漂移：value_added={fh} vs trivial={t["avg_field_hit_rate_exam"]}'
    return True, (f'T1+ exam {t.get("exam_tsr")} / 命中率 {t["avg_field_hit_rate_exam"]} / '
                  f'缺口中位 {t["n_fail_exam"].get("median")}；与 value_added 逐数一致')


def model_label_consistent(sc, label=''):
    """R51（专家第十轮 §3.2）：成绩单**顶层 `model` 必须等于 `provenance.model`**。

    实证：C-031（deepseek-v4-pro）的成绩单顶层 `model` 写着 `glm-5.3-flash`
    （score_baseline 里硬编码的默认值），而 provenance.model 才是 deepseek。
    只读顶层的人会以为「第二模型还是 glm」。跨模型 artifact 的模型标签不能靠默认值。
    """
    if not sc:
        return False, f'{label} 缺成绩单'
    top = sc.get('model')
    prov = (sc.get('provenance') or {}).get('model')
    if not top:
        return False, f'{label} 顶层 model 为空'
    if not prov:
        return False, f'{label} provenance.model 为空（无法交叉核对）'
    if top != prov:
        return False, f'{label} ★顶层 model={top} ≠ provenance.model={prov}（R51）'
    if top.startswith('MIXED:'):
        return False, f'{label} 一批候选混了多个模型：{top}'
    return True, f'{label} model={top}（顶层 == provenance）'


def msr_denominator_closure(sc, label=''):
    """R52（专家第十轮 §3.3）：MSR 分母必须**四类拆开**且加和闭合。

    实证：C-031 `n_clarify_excluded=5` 其实是「4 条澄清题 + 1 条 3 轮无输出」，
    而 C-029 的 4 是「4 条纯澄清」——两个数被并排放进对比表就会被读成同口径。
    判据两层（R52 原文把两层混写了，这里按实现分两层，见 msr_l3.py 注释）：
      层A：n_counted + clarify + unresolved + notrun + env + unknown == n_tasks_total
      层B：n_counted == n_solver_excluded + n_counted_excl_solver（solver 仍在原始分母内）
    """
    ms = (sc or {}).get('msr_section') or {}
    if not ms:
        return False, f'{label} 缺 msr_section'
    for key in ('denominator_audit', 'exam_denominator_audit'):
        a = ms.get(key)
        if not a:
            return False, f'{label} 缺 {key}（R52：分母构成未落盘）'
        if not a.get('closure_ok'):
            return False, f'{label} {key} 层A 不闭合：{a.get("closure")}'
        if not a.get('closure_solver_ok'):
            return False, f'{label} {key} 层B 不闭合：{a.get("closure")}'
    a = ms['denominator_audit']
    # 反向守：n_clarify_excluded 必须是**纯澄清**，若它等于「全部排除项」说明又混类了
    if ms.get('n_clarify_excluded') != a['n_clarify_excluded']:
        return False, (f'{label} n_clarify_excluded={ms.get("n_clarify_excluded")} 与拆分出的'
                       f'纯澄清 {a["n_clarify_excluded"]} 不等（混入未收敛？R52）')
    if ms.get('n_unresolved') != a['n_unresolved_excluded']:
        return False, (f'{label} n_unresolved={ms.get("n_unresolved")} ≠ '
                       f'n_unresolved_excluded={a["n_unresolved_excluded"]}')
    ea = ms['exam_denominator_audit']
    return True, (f'{label} 全卷 {a["closure"]}｜exam counted {ea["n_counted"]} + clarify '
                  f'{ea["n_clarify_excluded"]} + unresolved {ea["n_unresolved_excluded"]}')


def msr_conditional_declared(sc, label=''):
    """R54（W5c-6h）：MSR 是**条件通过率**，分母只含「产出 spec 的非澄清题」。

    后果：不同成绩单的分母可以不同（实测 C-032 exam 22 vs C-033 exam 21），
    而裸报 pct 会被读成同口径。实证反直觉：C-033 exam MSR 20/21 = 95.2%
    会「高于」C-032 的 20/22 = 90.9%，差的正是被排除的那条**失败题**
    （`cfrp45s_d40` 模型侧无输出）——分母小的那个 pct 反而更好看。
    ⇒ 闸的两端：①口径必须写进成绩单；②排除了谁必须点名，不得只把分母改小。
    """
    ms = (sc or {}).get('msr_section') or {}
    if not ms:
        return False, f'{label} 缺 msr_section'
    if not (ms.get('msr_definition') or '').strip():
        return False, f'{label} 缺 msr_definition（R54：条件口径必须写进成绩单）'
    ids = ms.get('n_no_spec_excluded_ids')
    if ids is None:
        return False, f'{label} 缺 n_no_spec_excluded_ids（排除项未点名，R54）'
    a = ms.get('denominator_audit') or {}
    n_un = a.get('n_unresolved_excluded')
    if n_un is not None and len(ids) != n_un:
        return False, (f'{label} 点名的无输出 {len(ids)} 条 ≠ 审计里 unresolved '
                       f'{n_un} 条（排除项与审计不一致，R54）')
    if ids:
        return True, f'{label} 口径已声明；条件分母排除 {len(ids)} 条（{ids[0].replace("L3_", "")}…）'
    return True, f'{label} 口径已声明；无模型侧无输出被排除'


def dev_reversal_closed(path):
    """R55（第十一轮 §3.1）：dev 反向变化必须逐题定位且闭环。

    只报「dev 少 1 条」没法判读——净额 −1 可能是「2 条退化 + 1 条修好」，
    而这三条的原因完全不同（采样波动 / 题面修正被兑现 / 真的变差）。
    """
    if not os.path.exists(path):
        return False, '缺 dev_reversal 产物（R55：必须先定位再写榜单）'
    try:
        d = json.load(open(path, encoding='utf-8'))
    except Exception as e:
        return False, f'dev_reversal 读不动：{e}'
    c = d.get('closure') or {}
    cc = d.get('tsr_cross_check') or {}
    n = len(d.get('flips') or [])
    delta = ((d.get('dev_pass') or {}).get('delta'))
    bad = []
    if not c.get('ok'):
        bad.append(f"闭合失败：{c.get('formula')}")
    if cc.get('agree') is False:
        bad.append(f"与成绩单 dev TSR 不一致：{cc.get('scorecard_dev_tsr')} vs {cc.get('recomputed')}")
    if (delta or 0) != 0 and n == 0:
        bad.append(f'dev 变了 {delta} 但翻转列表为空（未定位）')
    for f in (d.get('flips') or []):
        if not f.get('fields'):
            bad.append(f"{f.get('task_id')} 无字段级证据")
        for x in (f.get('fields') or []):
            if x.get('gold') is None and x.get('new_candidate') is None:
                bad.append(f"{f.get('task_id')}:{x.get('field')} 三个值全空")
    if bad:
        return False, '；'.join(bad)
    return True, (f"闭合 {c.get('formula')}；翻转 {n} 条（pass→fail "
                  f"{(d.get('flip_counts') or {}).get('pass->fail')} / fail→pass "
                  f"{(d.get('flip_counts') or {}).get('fail->pass')}），每条带 gold/候选证据")


def w5d_leaderboard_ok(path):
    """R56（第十一轮 §5.1）：跨模型榜单必须三列并排，且分母不等时不出 MSR Δ。

    实证（本基准最难防的坑）：同一对模型，
      - 任务级 TSR：92.0% > 88.0%（glm 领先）
      - 字段级命中率：99.34% > 90.94%（glm 领先）
      - 条件 MSR：90.9% < 95.2%（**deepseek 反而更高**，因为它的分母少 1 条失败题）
    ⇒ 只引任何一列都能得出「某个模型更强」；三列并排才暴露口径冲突。
    """
    if not os.path.exists(path):
        return False, '缺 w5d_leaderboard 产物（R56）'
    try:
        d = json.load(open(path, encoding='utf-8'))
    except Exception as e:
        return False, f'w5d_leaderboard 读不动：{e}'
    bad = []
    if not str(d.get('schema') or '').startswith('w5d_leaderboard'):
        bad.append(f"schema={d.get('schema')}")
    models = d.get('models') or {}
    if len(models) < 2:
        bad.append(f'榜单只有 {len(models)} 个模型')
    for k, m in models.items():
        ex = m.get('exam') or {}
        va = m.get('value_added') or {}
        fu = m.get('full') or {}
        if (ex.get('tsr') or {}).get('pct') is None:
            bad.append(f'{k} 缺任务级 TSR')
        if (va.get('field_llm_hit_rate') is None) or (va.get('field_verdict') is None):
            bad.append(f'{k} 缺字段级命中率/判决')
        if fu.get('failure_class_counts') is None:
            bad.append(f'{k} 缺失败分层')
    pair = d.get('pair') or {}
    if pair:
        da = ((models.get(pair.get('a')) or {}).get('exam') or {}).get('msr') or {}
        db = ((models.get(pair.get('b')) or {}).get('exam') or {}).get('msr') or {}
        same = (da.get('den') is not None and da.get('den') == db.get('den'))
        if bool(pair.get('msr_delta_allowed')) != same:
            bad.append(f"msr_delta_allowed={pair.get('msr_delta_allowed')} 与分母是否相等（{da.get('den')} vs "
                       f"{db.get('den')}）不一致 —— 该字段必须由分母算，不得手填（R54）")
        if not same and pair.get('msr_delta_pp') is not None:
            bad.append(f"分母不等却给出了 MSR Δ={pair.get('msr_delta_pp')}")
    st = d.get('statements') or {}
    if not (st.get('allowed') and st.get('forbidden')):
        bad.append('缺「能说 / 不能说」清单')
    # md 端：分母不等时必须写明不可相减，且 MSR 行不得出现 Δ
    mdp = path[:-5] + '.md'
    if not os.path.exists(mdp):
        bad.append('缺 md')
    else:
        mt = _txt(mdp)
        if pair and not pair.get('msr_delta_allowed') and '不可相减' not in mt:
            bad.append('md 未写明「不可相减」')
        for line in mt.split('\n'):
            if '条件 MSR' in line and 'Δ' in line and '不可相减' not in line:
                bad.append('md 的 MSR 行出现了 Δ（分母不等时禁止）')
                break
        # 有失败就有 FPR，限制段必须提到它（防止只报好看的指标）
        if any(((m.get('fpr') or {}).get('fabrication_rate_pct') or 0) > 0 for m in models.values()):
            if 'FPR' not in mt.split('## 7.')[-1]:
                bad.append('有限制项 FPR>0 但「限制」段未提 FPR')
    if bad:
        return False, '；'.join(bad)
    return True, (f"三列齐（任务级/字段级/失败分层）×{len(models)} 模型；"
                  f"MSR 可减={pair.get('msr_delta_allowed')}（分母 "
                  f"{(models.get(pair.get('a')) or {}).get('exam', {}).get('msr', {}).get('den')} vs "
                  f"{(models.get(pair.get('b')) or {}).get('exam', {}).get('msr', {}).get('den')}）；"
                  f"能说 {len(st.get('allowed') or [])} 条 / 不能说 {len(st.get('forbidden') or [])} 条")


def prompt_ablation_consistent(ablation_path, gen_path, baseline_sha, label=''):
    """R57 补（W5d-1）：**prompt 消融的结论必须与当前 prompt 一致**。

    为什么需要这条：跑完消融写个「否决」很容易，但「写了否决却把 prompt 改回去」或者
    「写了采纳却没重跑候选」都不会有任何报错——上一代成绩单还挂在那儿，读者无法分辨。
    闸的两端：
      - 结论 = 不采纳 ⇒ 当前源码的 SYS sha **必须仍等于**基线成绩单记录的 sha；
      - 结论 = 采纳   ⇒ 当前 sha **必须已变**（且下一轮必须按 R53 全量重跑，S-39 会咬）。
    """
    if not os.path.exists(ablation_path):
        return False, f'{label} 缺 prompt 消融产物（改过 prompt 就必须留档，否则等于没做）'
    try:
        d = json.load(open(ablation_path, encoding='utf-8'))
    except Exception as e:
        return False, f'{label} 消融产物读不动：{e}'
    dec = d.get('decision') or {}
    if dec.get('adopt') is None:
        return False, f'{label} 消融产物没有 decision.adopt（判定未落盘）'
    if not (d.get('variants') or []):
        return False, f'{label} 消融产物没列变体'
    try:
        import subprocess
        cur = (subprocess.run(['node', gen_path, '--print-prompt-sha'],
                              capture_output=True, text=True, timeout=60).stdout or '').strip()
    except Exception as e:
        return False, f'{label} 取当前 prompt sha 失败：{e}'
    if not cur:
        return False, f'{label} node --print-prompt-sha 无输出'
    if dec['adopt']:
        if cur == baseline_sha:
            return False, (f'{label} 消融判「采纳」，但当前 prompt sha 仍 == 基线（{str(cur)[:12]}…）'
                           f'⇒ 没真的换上，或换上了却没重跑')
        return True, f'{label} 采纳态：当前 sha {str(cur)[:12]}… ≠ 基线 {str(baseline_sha)[:12]}…（R53 须全量重跑）'
    if cur != baseline_sha:
        return False, (f'{label} 消融判「否决」，但当前 prompt sha 已变成 {str(cur)[:12]}… '
                       f'（基线 {str(baseline_sha)[:12]}…）⇒ 否决未生效/偷换了 prompt')
    return True, f'{label} 否决态：当前 sha == 基线 {str(cur)[:12]}…（未采用未采纳的变体）'


_HIST_MARKERS = ('historical', '历史', '上一代', 'superseded', '不是当前', '非当前')


def _latest_nc_json(root):
    """最新的 `negative_controls_<N>.json`（取数字最大者；`reports/archive/` 不参与）。"""
    d = os.path.join(root, 'feagpt_repro', 'reports')
    best, best_n = None, -1
    for p in glob.glob(os.path.join(d, 'negative_controls_*.json')):
        m = re.search(r'negative_controls_(\d+)\.json$', p)
        if m and int(m.group(1)) > best_n:
            best, best_n = p, int(m.group(1))
    return best


def index_consistency(index_path, nc_json_path, headline_claim):
    """R58（T-A3，来自 N-1/N-2）：**`reports/INDEX.md` 必须被 gate 读**。

    动机（根因）：S-00..S-43 共 44 项语义检查**没有一条**读 INDEX.md
    （`grep -n INDEX check_claims.py` = 0 命中），于是 §2 的「⓪ 当前官方 headline（C-029）」
    能与 §1 的（C-032）长期并存——而 INDEX 正是 `AGENTS.md` §0 第 3 行要求 agent 去查
    「当前成绩单路径」的文件。后果不是报错，而是**静默重跑错代基线**（两代 exam 同为 23/25）。
    ⇒ **没有任何工具读的官方文档 = 没有闸**。

    两条判据都**只认结构化记号**，不按自然语言判读（S-29 第一版就栽在自然语言判据上）：
      (a) headline 指向唯一：含「官方/当前 headline」且含 claim id 的行，其 id 必须 ⊆
          `{headline_claim}`；**除非**该行带显式历史标记（historical/历史/上一代/superseded/不是当前）。
          不含 claim id 的行不判（如「当前 headline 见 §1」这类纯指针）。
      (b) 负控编号与 artifact 对齐：负控行的 `NC-x..y` 必须与最新 `negative_controls_<N>.json`
          实读一致——上界 == 最大 NC 号、区间内无缺号、`= N/N` 的分母 == 实读条数、分子 == 分母。
    """
    if not headline_claim:
        return False, 'headline claim 不是恰好 1 条（S-29 会先报），S-44 无从比对'
    if not os.path.exists(index_path):
        return False, f'INDEX 不存在（{index_path}）——R58：官方导航文件缺失比写错更危险'
    lines = open(index_path, encoding='utf-8').read().split('\n')
    det, ok = [], True

    # ---- (a) headline 指向 ----
    # ★ 判据要点：**行内出现 headline id ⇒ 放行**（headline 行正文引用别家 claim 是正常的，
    #   例如 §1 那行写「与 C-029 逐字节相同」）。危险的是**出现「当前/官方 headline」却指向
    #   非 headline 的那条**（N-1 的原始形态），此时必须有显式历史标记。
    n_head, n_hist, bad = 0, 0, []
    for i, ln in enumerate(lines, 1):
        if '官方 headline' not in ln and '当前 headline' not in ln:
            continue
        ids = set(re.findall(r'C-\d{3}', ln))
        if not ids:
            continue                      # 纯指针行不参与判定
        if headline_claim in ids:
            n_head += 1
            continue
        if any(mk in ln for mk in _HIST_MARKERS):
            n_hist += 1
            continue
        n_head += 1
        bad.append(f'L{i} 出现「当前/官方 headline」但只指向 {",".join(sorted(ids))}，且未标历史')
    if n_head == 0:
        ok = False
        det.append('(a) ★ 一条「headline + claim id」的行都没有 ⇒ 无法验证指向（不得静默放行）')
    else:
        ok = ok and not bad
        det.append(f'(a) headline 命中 {n_head} 条、显式历史 {n_hist} 条、越权 {len(bad)} 条'
                   + ('' if not bad else '：' + '；'.join(bad)))

    # ---- (b) 负控编号 ----
    if not nc_json_path or not os.path.exists(nc_json_path):
        ok = False
        det.append('(b) 找不到最新 negative_controls_*.json')
    else:
        nc = json.load(open(nc_json_path, encoding='utf-8'))
        ids = [str(r.get('id') or '') for r in (nc.get('results') or [])]
        nums = sorted(int(m.group(1)) for m in
                      (re.match(r'^NC-(\d+)$', s) for s in ids) if m)
        total, mx = len(ids), (max(nums) if nums else None)
        hit = None
        for i, ln in enumerate(lines, 1):
            if 'negative_controls_' in ln and re.search(r'NC-\d+\.\.\d+', ln):
                hit = (i, ln)
                break
        if not hit:
            ok = False
            det.append('(b) 找不到负控行（需同时含 `negative_controls_` 与 `NC-x..y`）')
        else:
            i, ln = hit
            # ★ 该行会列出多个区间（NC-1..22 / NC-23..48 / NC-43..46…）⇒ 取**上界最大的那个**
            #   才是「主区间」。取第一个（NC-1..22）或最后一个（NC-43..46）都会误判。
            rs = [(int(a), int(b)) for a, b in re.findall(r'NC-(\d+)\.\.(\d+)', ln)]
            lo, hi = max(rs, key=lambda t: t[1]) if rs else (None, None)
            tms = re.findall(r'=\s*\**\s*(\d+)/(\d+)', ln)
            probs = []
            if not tms:
                probs.append('行内没有 `= N/N`')
            else:
                a, b = int(tms[-1][0]), int(tms[-1][1])
                if a != b:
                    probs.append(f'分子 {a} ≠ 分母 {b}')
                if b != total:
                    probs.append(f'总数 {b} ≠ artifact {total} 条')
            if mx is not None and hi != mx:
                probs.append(f'主区间上界 NC-{hi} ≠ artifact 最大 NC-{mx}')
            miss = [n for n in range(lo or 0, (hi or 0) + 1) if n not in set(nums)]
            if miss:
                probs.append('主区间内缺号 ' + ','.join('NC-%d' % n for n in miss))
            ok = ok and not probs
            det.append(f'(b) L{i} 主区间 NC-{lo}..{hi} / 总数 {tms[-1][1] if tms else "?"}；'
                       f'artifact 最大 NC-{mx}、共 {total} 条'
                       + ('' if not probs else ' ⇒ ' + '；'.join(probs)))
    return ok, '；'.join(det)


def prompt_no_blind_default(path, label='gen_candidates_v2.js'):
    """R50（专家第十轮 §3.1）：SYS prompt **不得**对题面已提及的特征授权默认值，
    同时**不得**把 `expected_clarifications` 注入 prompt（那等于泄漏答案）。

    反面实证：旧 prompt 写「未提长桁→长桁数=0」，而 `stiffened_panel_600x600_str3`
    的题面是「若干根长桁」且登记了 `expected_clarifications=['n_stringers']`
    ⇒ prompt 直接授权填 0，与题面判据**自相矛盾**。deepseek 被诱导，glm 没有 ⇒
    这条缺陷污染了跨模型对比（不能记成模型错）。
    """
    if not os.path.exists(path):
        return False, f'{label} 不存在'
    src = _txt(path)
    bad = []
    if '未提长桁→长桁数=0' in src:
        bad.append('仍含「未提长桁→长桁数=0」授权（R50 禁止）')
    if '数量类字段铁律' not in src:
        bad.append('缺「数量类字段铁律」段（题面提了特征却没给数量 ⇒ 必须澄清）')
    if 'expected_clarifications' in src:
        bad.append('prompt 里出现 expected_clarifications ⇒ 泄漏答案的风险（R50）')
    if bad:
        return False, f'{label}: ' + '；'.join(bad)
    return True, f'{label}: 无盲填授权、含数量铁律、未注入 expected_clarifications'


def prompt_sha_matches_source(gen_path, expected_sha, label=''):
    """R53（W5c-6d）：成绩单记录的 `prompt_sha256` 必须等于**当前源码**里 SYS 的 sha。

    为什么：改了 prompt 却没重生成 ⇒ 成绩单会挂着一个「已经不存在的 harness」的分数。
    这条闸把「prompt 漂移」从人工纪律变成机器检查（`node gen_candidates_v2.js --print-prompt-sha`）。
    """
    import subprocess
    if not expected_sha or expected_sha == 'UNKNOWN':
        return False, f'{label} provenance.prompt_sha256 = {expected_sha}（旧批次未记录 ⇒ R53 不可比）'
    if str(expected_sha).startswith('MIXED:'):
        return False, f'{label} 一批候选混了多个 prompt sha：{expected_sha}'
    if not gen_path or not os.path.exists(gen_path):
        return False, f'{label} 找不到生成器（{gen_path}）'
    try:
        out = subprocess.run(['node', gen_path, '--print-prompt-sha'],
                             capture_output=True, text=True, timeout=60)
        cur = (out.stdout or '').strip()
    except Exception as e:
        return False, f'{label} 取当前 prompt sha 失败：{e}'
    if not cur:
        return False, f'{label} node --print-prompt-sha 无输出（rc={out.returncode}）'
    if cur != expected_sha:
        return False, (f'{label} ★prompt 已改但成绩单未重生成：artifact={str(expected_sha)[:12]}… '
                       f'vs 源码={cur[:12]}…（R53）')
    return True, f'{label} prompt sha {cur[:12]}… == 源码（未漂移）'


def denominator_accounting(sc, label=''):
    """R47（W5c-6c）：比率指标的**分母构成必须加和**，禁止隐式过滤。

    实证（跨模型对比才暴露）：旧版字段级命中率写
        hits = [... for r in exam_rows if r.get('n_fields_gated')]
    于是 `fabricated`（编造）与 `clarify_wrong` 被**静默排除**。C-029（glm）排除的
    3 条是合法澄清（该排除），C-031（dsv4pro）排除的 3 条是编造（该记 0）⇒
    两份成绩单都算出 **99.34%**，数字相同、含义相反。
    ⇒ 判据：n_exam_counted + n_excluded_clarify_ok 必须 == exam.n（分母闭合），
       且 n_zero_non_spec（记 0 的题）必须 ≤ 计入条数。
    """
    if not sc:
        return False, f'{label} 缺成绩单'
    fl = ((sc.get('value_added') or {}).get('field_level') or {})
    n_exam = (sc.get('exam') or {}).get('n')
    miss = [k for k in ('n_exam_counted', 'n_excluded_clarify_ok', 'n_zero_non_spec')
            if fl.get(k) is None]
    if miss:
        return False, f'{label} 缺分母构成字段 {"、".join(miss)}（R47）'
    tot = fl['n_exam_counted'] + fl['n_excluded_clarify_ok']
    if n_exam is not None and tot != n_exam:
        return False, (f'{label} 分母不闭合：计入 {fl["n_exam_counted"]} + 排除 '
                       f'{fl["n_excluded_clarify_ok"]} = {tot} ≠ exam.n {n_exam}')
    if fl['n_zero_non_spec'] > fl['n_exam_counted']:
        return False, (f'{label} 记 0 的条数 {fl["n_zero_non_spec"]} 超过计入条数 '
                       f'{fl["n_exam_counted"]}')
    return True, (f'{label} 计入 {fl["n_exam_counted"]} + 排除 {fl["n_excluded_clarify_ok"]} '
                  f'= {n_exam}；其中编造记 0 **{fl["n_zero_non_spec"]}** 条')


def verdict_split_recorded(sc, label=''):
    """R49（W5c-6c）：value_added 两个尺度的结论**可能相反**，分裂必须由成绩单自己标出。

    实证：C-031 任务级 Δ80 pp（PASS）、字段级 Δ1.5 pp（BELOW）。若不标，
    文档可以只引任务级那侧 ⇒ 变成 cherry-pick。
    """
    va = (sc or {}).get('value_added') or {}
    tv = va.get('verdict')
    lv = (va.get('field_level') or {}).get('verdict')
    if tv is None or lv is None:
        return False, f'{label} 缺 verdict（{tv}）或 field_level.verdict（{lv}）'
    if (tv == 'PASS') != (lv == 'PASS'):
        ok = bool(va.get('verdict_split'))
        return ok, (f'{label} 双尺度分裂：任务级 {tv} / 字段级 {lv} ⇒ '
                    f'verdict_split {"已落盘" if ok else "★缺失（R49）"}')
    return True, f'{label} 两尺度一致（任务级 {tv} / 字段级 {lv}），无需分裂说明'


def second_model_not_headline(rows):
    """R48（W5c-6c）：第二模型结果**只作可重复性证据**，不得因成绩高低决定 headline。

    跨模型对比最容易出的错是「哪个模型分高就把 headline 换成哪个」——同一张卷上
    试 N 个模型取最好，等于事后挑样本。headline 必须在跑之前就定（主基线模型），
    第二模型无论高低都只能并列报。

    ★ W5c-6d 改为**数据驱动**（原版硬编码 C-029/C-031，换轮次就得改代码，
      S-29 已经因为硬编码错过一次）：headline = 带自指标记的那条；supporting =
      状态列声明 supporting/第二模型 的那些；断言两者交集为空。
    """
    by = {r.get('claim_id'): r for r in rows if r.get('claim_id')}
    marker = lambda s: ('（对外 headline）' in (s or '')) or ('(对外 headline)' in (s or ''))
    heads = [cid for cid, r in by.items() if marker(r.get('status') or '')]
    supp = [cid for cid, r in by.items()
            if any(k in (r.get('status') or '') for k in ('supporting', '不作 headline', '第二模型'))
            and not marker(r.get('status') or '')]
    if not supp:
        return False, '缺第二模型 claim（status 未标 supporting/第二模型）⇒ 可重复性验证没有登记'
    bad = [c for c in supp if marker(by[c].get('status') or '')]
    if bad:
        return False, f'{bad} 自称 headline —— 跨模型不得事后择优（R48）'
    if not heads:
        return False, '没有任何 claim 标（对外 headline）—— 主基线定位丢失（R42/R48）'
    return True, f'唯一 headline = {heads}；supporting = {sorted(supp)}（均未自称 headline）'


def semantic_checks(root, rows):
    """逐条核对：账本文本里声称的数字 vs artifact 实读的数字（R29）。"""
    out, m = [], _measures(root)
    by = {}
    for r in rows:
        cid = (r.get('claim_id') or '').strip()
        by.setdefault(cid, r)
    if not any(k.startswith('C-') for k in by):
        out.append({'id': 'S-0', 'desc': '语义计数检查', 'expect': '-', 'skip': True, 'ok': True,
                    'actual': '注入模式（账本无 C-xxx claim）⇒ 跳过'})
        return out

    def add(sid, desc, expect, actual, ok):
        out.append({'id': sid, 'desc': desc, 'expect': str(expect), 'actual': str(actual),
                    'ok': bool(ok), 'skip': False})

    # 0) 必需 claim 必须还在（整行被删掉比写错数字更危险）
    missing = [c for c in REQUIRED_CLAIMS if c not in by]
    add('S-00', '必需 claim 存在性', '全部在', '无缺失' if not missing else '缺失 ' + ','.join(missing),
        not missing)

    st_of = lambda cid: (by.get(cid) or {}).get('statement', '')

    # 1) C-010 任务层行数 + L3 行数
    t = m.get('tasks') or {}
    txt = st_of('C-010')
    mm = re.search(r'任务层[^0-9]{0,8}(\d+)', txt)
    add('S-01', 'C-010 任务层总行数', t.get('total'), mm.group(1) if mm else '未找到',
        mm and t.get('total') is not None and int(mm.group(1)) == t['total'])
    mm = re.search(r'L3[^0-9]{0,4}(\d+)', txt)
    add('S-02', 'C-010 其中 L3 行数', t.get('n_l3'), mm.group(1) if mm else '未找到',
        mm and t.get('n_l3') is not None and int(mm.group(1)) == t['n_l3'])

    # 2) C-011 内插条数（必须与 v6 的 exam_stratum=interpolation 一致）
    txt = st_of('C-011')
    mm = re.search(r'interpolation[^0-9]{0,6}(\d+)', txt)
    add('S-03', 'C-011 内插 ID test 条数', t.get('interpolation'), mm.group(1) if mm else '未找到',
        mm and t.get('interpolation') is not None and int(mm.group(1)) == t['interpolation'])

    # 3) C-019 负控 n_ok/n_cases（正文 + coverage 列）
    nc = m.get('nc') or {}
    txt = st_of('C-019')
    mm = re.search(r'全绿[：:]?[^\d]{0,6}(\d+)\s*/\s*(\d+)', txt)
    exp = f"{nc.get('n_ok')}/{nc.get('n_cases')}"
    got = f'{mm.group(1)}/{mm.group(2)}' if mm else '未找到'
    add('S-04', f'C-019 负控通过数（源 {m.get("nc_file", "缺")}）', exp, got, got == exp)
    mm = re.search(r'(\d+)', (by.get('C-019') or {}).get('coverage', ''))
    add('S-05', 'C-019 coverage 列', nc.get('n_cases'), mm.group(1) if mm else '未找到',
        mm and nc.get('n_cases') is not None and int(mm.group(1)) == nc['n_cases'])

    # 4) C-021 exam 条数（v4 成绩单实读）
    sc = m.get('sc_v4') or {}
    txt = st_of('C-021')
    mm = re.search(r'exam\s*\**\s*(\d+)\s*\**\s*条', txt)
    add('S-06', 'C-021 exam 条数', sc.get('n'), mm.group(1) if mm else '未找到',
        mm and sc.get('n') is not None and int(mm.group(1)) == sc['n'])

    # 5) C-027 三栏和 exam 合计（v6 考卷实读）
    txt = st_of('C-027')
    mm = re.search(r'boundary\s*(\d+)\s*\+\s*extrapolation\s*(\d+)\s*\+\s*interpolation\s*(\d+)', txt)
    got = tuple(int(x) for x in mm.groups()) if mm else ('未找到',)
    exp = (t.get('boundary'), t.get('extrapolation'), t.get('interpolation'))
    add('S-07', 'C-027 三栏 boundary/extrap/interp', exp, got, got == exp)
    mm = re.search(r'=\s*\**\s*exam\s*\**\s*(\d+)', txt)
    add('S-08', 'C-027 exam 合计', t.get('exam'), mm.group(1) if mm else '未找到',
        mm and t.get('exam') is not None and int(mm.group(1)) == t['exam'])

    # 6) 「C-021 的 N 条」在四处文档里必须都等于 C-021 真实条数（R30 的文本面）
    c021_n = sc.get('n')
    for rel, sid in ((PLAN_REL, 'S-09'), (RUBRIC_REL, 'S-10'), (CLAIMS_REL_FOR_SEM, 'S-11')):
        body = _txt(os.path.join(root, rel))
        nums = {int(x) for x in re.findall(r'C-021\s*的\s*\**\s*(\d+)\s*\**\s*条', body)}
        ok = (not nums) or (c021_n is not None and nums == {c021_n})
        add(sid, f'{os.path.basename(rel)} 里「C-021 的 N 条」', c021_n or '?',
            ','.join(map(str, nums)) or '无此表述', ok)

    # 7) RUBRIC §1 三行条数与 artifact 一致（11 / 19 / 25）
    rub = _txt(os.path.join(root, RUBRIC_REL))
    v4 = m.get('v4') or {}
    n_19 = None
    if t and v4:
        n_19 = t['boundary'] + t['extrapolation']
    wants = []
    if c021_n is not None and v4:
        wants.append(('S-12', f'**{c021_n}**（boundary {v4["boundary"]} + extrap {v4["extrapolation"]}）'))
    if n_19 is not None:
        wants.append(('S-13', f'**{n_19}**（boundary {t["boundary"]} + extrap {t["extrapolation"]}）'))
    if t.get('exam'):
        wants.append(('S-14', f'**{t["exam"]}**（{t["boundary"]} + {t["extrapolation"]} + {t["interpolation"]}）'))
    for sid, s in wants:
        add(sid, 'RUBRIC §1 三栏条数行', '存在', '存在' if s in rub else f'缺「{s}」', s in rub)

    # 8) README 里引用的 RUBRIC 版本必须与 RUBRIC.md 顶部一致
    mm = re.search(r'\*\*版本\*\*[：:]\s*v(\d+(?:\.\d+)?)', rub)
    rub_v = mm.group(1) if mm else None
    rd = _txt(os.path.join(root, README_REL))
    refs = set(re.findall(r'RUBRIC\.md[^\n]{0,40}?v(\d+(?:\.\d+)?)', rd))
    add('S-15', 'README 引用的 RUBRIC 版本', f'全部 = {rub_v}',
        ','.join(sorted(refs)) or '无引用', bool(refs) and refs == {rub_v})

    # 9) README 里的负控通过数
    mm = re.search(r'negative_controls\.py[^\n]{0,20}?\**(\d+)\s*/\s*(\d+)', rd)
    exp = f"{nc.get('n_ok')}/{nc.get('n_cases')}"
    got = f'{mm.group(1)}/{mm.group(2)}' if mm else '未找到'
    add('S-16', 'README 负控通过数', exp, got, got == exp)

    # 10) headline claim（有 v6c 就是 C-029，否则 C-028）核心数字必须等于成绩单实读值（R29/R38）
    cid, hl = m.get('headline') or (None, {})
    cl = _txt(os.path.join(root, CLAIMS_REL_FOR_SEM))
    line = next((l for l in cl.splitlines() if l.startswith(f'| {cid}')), '') if cid else ''
    if cid and hl:
        tsrH = ((hl.get('exam') or {}).get('tsr')) or {}
        if tsrH.get('total'):
            want = f"{tsrH['pass']}/{tsrH['total']} ({tsrH['pct']}%)"
            hit = re.search(r'TSR\s*(\d+/\d+)\s*\(([\d.]+)%\)', line)
            got_s = f'{hit.group(1)} ({hit.group(2)}%)' if hit else '未找到'
            add('S-17', f'{cid} exam TSR 与成绩单一致', want, got_s, got_s == want)
        bs = hl.get('by_stratum') or {}
        ok_s, det = True, []
        for k in ('boundary', 'extrapolation', 'interpolation'):
            blk = ((bs.get(k) or {}).get('tsr')) or {}
            if not blk.get('total'):
                continue
            w = f"{blk['pass']}/{blk['total']}"
            found = re.search(r'\b' + re.escape(w) + r'\b', line) is not None
            ok_s = ok_s and found
            det.append(f'{k}={w}{"" if found else "(缺)"}')
        add('S-18', f'{cid} 三栏条数在 claim 行内', '三栏齐', ','.join(det) or '无三栏数据', ok_s)
        # ★ W5c：MSR 缺失时必须**响亮失败**，不能静默消失——「不参与判定的检查不是检查」。
        # 旧版 `if '/' in msrH` 在成绩单还没跑 MSR 时让 S-19/S-20 直接不出现，
        # 语义项总数从 29 掉到 27 也没人发现。
        msrH = hl.get('msr') or ''
        emH = hl.get('exam_msr') or ''
        if isinstance(msrH, str) and '/' in msrH:
            w = f"{msrH} ({hl.get('msr_pct')}%)"
            add('S-19', f'{cid} 全链 MSR 与成绩单一致', w, '命中' if w in line else '缺', w in line)
        else:
            add('S-19', f'{cid} 全链 MSR 与成绩单一致', '成绩单须有 msr 节',
                f'成绩单缺 msr 节（跑 msr_l3.py 后再自检）', False)
        if isinstance(emH, str) and '/' in emH:
            w = f"{emH} ({hl.get('exam_msr_pct')}%)"
            add('S-20', f'{cid} exam MSR 与成绩单一致', w, '命中' if w in line else '缺', w in line)
        else:
            add('S-20', f'{cid} exam MSR 与成绩单一致', '成绩单须有 exam.msr',
                f'成绩单缺 exam.msr（跑 msr_l3.py 后再自检）', False)
        # S-25：SFR / dev / FPR / solver 四条也必须是实读值（旧版只咬 TSR+MSR，SFR 漂了没人抓）
        sf = hl.get('sfr') or {}
        if sf.get('of_spec_candidates'):
            w = f"{sf['pass']}/{sf['of_spec_candidates']}"
            add('S-25', f'{cid} exam SFR 与成绩单一致', w, '命中' if w in line else '缺', w in line)
        # S-26：候选覆盖必须同时给「文件覆盖」与「产出类型分解」
        prov = ((hl.get('raw') or {}).get('provenance') or {})
        n_cand, n_paper = prov.get('n_candidates'), (hl.get('raw') or {}).get('n_tasks_in_paper')
        unres = (hl.get('raw') or {}).get('n_unresolved')
        cats = (((hl.get('raw') or {}).get('exam') or {}).get('categories') or {})
        add('S-26', f'{cid} 覆盖记账含产出类型分解',
            '行内含 N/N + spec/clarify/unresolved',
            f'{n_cand}/{n_paper} unres={unres} {cats}', bool(n_cand) and 'unresolved' in line)
        # S-23：成绩单口径字符串必须由考卷生成（R38）
        ed, vb = hl.get('exam_definition') or '', hl.get('value_added_basis') or ''
        note = (hl.get('raw') or {}).get('note') or ''
        add('S-23', f'{cid} 成绩单口径字符串由考卷生成（R38）',
            'exam_definition 含 exam_stratum / basis 含三栏 / note 非 W4d',
            f'ed={bool(ed and "exam_stratum" in ed)} vb={bool("三栏" in vb)} w4d={"W4d" in note}',
            bool(ed and 'exam_stratum' in ed) and '三栏' in vb and 'W4d' not in note)
        # S-24：by_split 必须只含非 exam 行，且纯 train 条数与考卷一致
        tinfo = m.get('tasks') or {}
        bsp = hl.get('by_split') or {}
        pure_train = tinfo.get('pure_train')
        got_train = ((bsp.get('train') or {}).get('n'))
        add('S-24', f'{cid} by_split 只含非 exam 行（R36）',
            f'train={pure_train}', f'train={got_train} keys={sorted(bsp)}',
            got_train == pure_train and 'boundary_holdout' not in bsp)
        # S-28：成绩单 exam task-id 集 == 考卷 exam 集（逐 id）
        pexam = set(m.get('paper_exam_ids') or [])
        sexam = {r['task_id'] for r in ((hl.get('raw') or {}).get('per_task') or []) if r.get('is_exam')}
        add('S-28', f'{cid} exam task-id 集与考卷逐 id 相等',
            f'{len(pexam)} 条', f'{len(sexam)} 条 差集={sorted(pexam ^ sexam)[:3]}',
            bool(pexam) and pexam == sexam)

    # S-21：C-011 内插族分布必须是 wingbox 6（v6b 改因后），不得残留 2/2/1/1
    ifams = (m.get('tasks') or {}).get('interp_fams') or {}
    c11 = next((l for l in cl.splitlines() if l.startswith('| C-011')), '')
    nwx = ifams.get('wingbox', 0)
    ok21 = (f'wingbox {nwx}' in c11) and ('open_hole 2' not in c11) and ('barrel 1' not in c11)
    add('S-21', 'C-011 内插族分布', f'wingbox {nwx}', '命中' if ok21 else f'未命中({ifams})', ok21)

    # S-22：C-028 的题面消歧计数（26/55 坐标系、25/55 方向、161→206 字）必须从两版 paper 实算
    if m.get('nl_diff'):
        d = m['nl_diff']
        ok22 = all(str(v) in (line28 := (next((l for l in cl.splitlines()
                                              if l.startswith('| C-028')), '')))
                   for v in (d['coord_added'], d['dir_added']))
        ok22 = ok22 and (f"{d['len_v4']}→{d['len_v6b']}" in line28)
        add('S-22', 'C-028 题面消歧计数（从 paper 实算）',
            f"{d['coord_added']}/55、{d['dir_added']}/55、{d['len_v4']}→{d['len_v6b']}",
            '命中' if ok22 else '未命中', ok22)
    else:
        add('S-22', 'C-028 题面消歧计数（从 paper 实算）', 'paper 齐', '缺 paper', False)

    # S-27（R37）：active claim 引用的路径必须被 git 追踪，且不得指向 eval_runs/
    try:
        tracked = set(subprocess.run(['git', 'ls-files'], cwd=root, capture_output=True,
                                     text=True, encoding='utf-8', errors='replace').stdout.split())
        bad27 = []
        for ln in cl.splitlines():
            if not ln.startswith('| C-'):
                continue
            if 'superseded' in ln or 'retracted' in ln:
                continue
            for tok in PATH_RE.findall(ln):
                tok = tok.replace('\\', '/')
                if tok.startswith('eval_runs/') or '/eval_runs/' in tok:
                    bad27.append(tok)
                elif tok.startswith(('feagpt_repro/', 'FEM-Bench-Aero/')):
                    if tok not in tracked and not any(t.startswith(tok) for t in tracked):
                        bad27.append(tok)
        add('S-27', 'active claim 路径全部被 git 追踪（R37）', 'empty',
            str(sorted(set(bad27))[:3]) or 'empty', not bad27)
    except Exception as e:
        add('S-27', 'active claim 路径全部被 git 追踪（R37）', 'git 可用', f'err={e}', False)

    # S-29（R42，专家第九轮 §3.1/§3.8）：**当前对外 headline 必须唯一**。
    # 动机：W5c 收口后 README 与 C-021/C-025/C-026 仍各自自称 headline，
    #       而 29 项语义检查里**没有一条**检查「headline 是否唯一」⇒ 22 条 active 全过却互相矛盾。
    # ★ 判据用**结构化 status 列**（`status` 含「对外 headline」），不用 statement 自由文本：
    #   第一版用「statement 含该词且不含否定词」判，结果 C-029 自己因为写了
    #   「不是实测 / 不是又一个下界」被自己的否定词过滤掉 ⇒ 判据被行文措辞绑架。这是坑。
    # 只认**自指标记**「（对外 headline）」——C-028 的 status 里写了
    # 「对外 headline = C-029（v6c）」这种**指针**，若只判子串就会把指针当成第二个 headline。
    head_claims = sorted({cid for cid, r in by.items()
                          if '（对外 headline）' in (r.get('status') or '')
                          or '(对外 headline)' in (r.get('status') or '')})
    # ★ W5c-6d：headline 指针随 harness 换代前移（旧 prompt 代 → prompt-v2 代）。
    #   注意 C-032 与 C-029 的 exam TSR **数字相同（23/25）**，所以这里守的是
    #   「哪一条是当前 harness 的成绩」，不是「哪个分数更高」。
    add('S-29', '对外 headline 唯一且为 C-032（R42/R53）', '["C-032"]',
        json.dumps(head_claims, ensure_ascii=False), head_claims == ['C-032'])

    # S-30（R43，专家第九轮 §3.2）：dev 的 paper-clean 数字**不得冒充实测**。
    # C-029 曾写「dev 真实可达 25/30」，但 7 条 dev spec_fail 里只有 2 条是卷子缺陷（R41），
    # 另外 5 条是模型侧（自创键 / layup）——修卷子只能回收 2 条。⇒ 三段必须同现。
    _s29 = st_of('C-029')
    miss30 = [k for k in ('23/30', '25/30', '投影', '5 条') if k not in _s29]
    bad30 = '真实可达' in _s29
    add('S-30', 'C-029 dev 25/30 必须标为投影（R43）',
        '含 23/30 实测 + 25/30 投影 + 5 条模型失败，且不得写「真实可达」',
        f'缺 {"、".join(miss30)}' if miss30 else ('含「真实可达」' if bad30 else 'ok'),
        not miss30 and not bad30)

    # S-31（R45，专家第九轮 §3.5）：MSR 六个口径字段必须**全非空**，别名必须逐字相等。
    # 动机：`msr_excl_solver` 有数、`full_msr_excl_solver`/`dev_msr_pct` 却是缺键 ⇒
    #       复核者按字段名找不到 full 行，只能手算，手算就会漂。别名一律由同一变量写出。
    _ms31 = ((m.get('sc_v6c') or {}).get('raw') or {}).get('msr_section') or {}
    _need31 = ('exam_msr', 'exam_msr_excl_solver', 'dev_msr', 'dev_msr_pct',
               'dev_msr_excl_solver', 'msr', 'msr_excl_solver',
               'full_msr_excl_solver', 'full_msr_excl_solver_pct')
    _miss31 = [k for k in _need31 if _ms31.get(k) in (None, '')]
    _alias31 = (_ms31.get('full_msr_excl_solver') == _ms31.get('msr_excl_solver')
                and _ms31.get('full_msr_excl_solver_pct') == _ms31.get('msr_excl_solver_pct'))
    add('S-31', 'MSR 六口径字段非空 + 别名一致（R45）',
        '九个字段全非空；full_msr_excl_solver ≡ msr_excl_solver',
        (f'缺 {"、".join(_miss31)}' if _miss31 else '全非空') +
        ('' if _alias31 else '；★别名不一致'), not _miss31 and _alias31)

    # S-32（R44）：T1+ 地板非空 + 与 value_added 字段级地板逐数一致（防两份 artifact 漂移）
    _p32t = os.path.join(root, 'feagpt_repro', 'reports', 'trivial_baselines_L3_v6c.json')
    _p32s = os.path.join(root, 'feagpt_repro', 'reports', 'baseline_scorecard_L3_v6c.json')
    _ok32, _det32 = t1plus_consistency(
        json.load(open(_p32t, encoding='utf-8')) if os.path.exists(_p32t) else None,
        json.load(open(_p32s, encoding='utf-8')) if os.path.exists(_p32s) else None)
    add('S-32', 'T1+ 地板非空且与 value_added 字段级一致（R44）',
        'T1plus 非空 + avg_field_hit_rate_exam + n_fail_exam + 与 value_added 相等',
        _det32, _ok32)

    # S-33（R47）：字段级命中率的分母构成必须闭合（计入 + 合法澄清排除 == exam.n）。
    # 两份成绩单都要查 —— C-029 与 C-031 的「同一个 99.34%」就是被这条抓出来的。
    # ★ W5c-6d：四份成绩单全查（旧 prompt 代 C-029/C-031 + prompt-v2 代 C-032/C-033）。
    #   少一份就 FAIL —— R29 的老坑：检查对象必须显式列出，缺了不得静默跳过。
    _sc_paths = [('C-029', os.path.join(root, 'feagpt_repro', 'reports',
                                        'baseline_scorecard_L3_v6c.json')),
                 ('C-031', os.path.join(root, 'feagpt_repro', 'reports',
                                        'baseline_scorecard_L3_v6c_dsv4pro.json')),
                 ('C-032', os.path.join(root, 'feagpt_repro', 'reports',
                                        'baseline_scorecard_L3_v6c_p2.json')),
                 ('C-033', os.path.join(root, 'feagpt_repro', 'reports',
                                        'baseline_scorecard_L3_v6c_ds_p2.json'))]
    _det33, _ok33 = [], True
    for _lab, _p in _sc_paths:
        if not os.path.exists(_p):
            _det33.append(f'{_lab} 缺成绩单'); _ok33 = False; continue
        _o, _d = denominator_accounting(json.load(open(_p, encoding='utf-8')), _lab)
        _det33.append(_d); _ok33 = _ok33 and _o
    add('S-33', '字段级命中率分母构成闭合（R47）',
        'n_exam_counted + n_excluded_clarify_ok == exam.n，且编造记 0 不排除',
        '；'.join(_det33), _ok33)

    # S-34（R48）：第二模型不得事后择优抢走 headline
    _ok34, _det34 = second_model_not_headline(rows)
    add('S-34', '第二模型不取代 headline（R48）',
        '恰有一条 claim 标（对外 headline）（当前 = C-032）；C-031/C-033 等第二模型标 supporting 且不自称 headline',
        _det34, _ok34)

    # S-35（R49）：value_added 双尺度结论分裂时必须由成绩单自己标出
    _det35, _ok35 = [], True
    for _lab, _p in _sc_paths:
        if not os.path.exists(_p):
            _det35.append(f'{_lab} 缺成绩单'); _ok35 = False; continue
        _o, _d = verdict_split_recorded(json.load(open(_p, encoding='utf-8')), _lab)
        _det35.append(_d); _ok35 = _ok35 and _o
    add('S-35', 'value_added 双尺度分裂必须落盘（R49）',
        '任务级 PASS 而字段级 BELOW ⇒ verdict_split 非空（禁止只引有利的一侧）',
        '；'.join(_det35), _ok35)

    # S-36（R51，专家第十轮 §3.2）：顶层 model 必须 == provenance.model
    # 动机：C-031（deepseek）的成绩单顶层写着 glm-5.3-flash —— 36 项语义检查没有一条核对它。
    _det36, _ok36 = [], True
    for _lab, _p in _sc_paths:
        _o, _d = model_label_consistent(
            json.load(open(_p, encoding='utf-8')) if os.path.exists(_p) else None, _lab)
        _det36.append(_d); _ok36 = _ok36 and _o
    add('S-36', '成绩单顶层 model == provenance.model（R51）',
        '两份成绩单顶层 model 与 provenance 逐字相等，且不是默认值',
        '；'.join(_det36), _ok36)

    # S-37（R52，专家第十轮 §3.3）：MSR 分母四类拆开且加和闭合
    _det37, _ok37 = [], True
    for _lab, _p in _sc_paths:
        _o, _d = msr_denominator_closure(
            json.load(open(_p, encoding='utf-8')) if os.path.exists(_p) else None, _lab)
        _det37.append(_d); _ok37 = _ok37 and _o
    add('S-37', 'MSR 分母四类拆分且加和闭合（R52）',
        'counted + clarify + unresolved + notrun + env + unknown == n_tasks_total；'
        'counted == solver + counted_excl_solver；n_clarify_excluded 不得混入未收敛',
        '；'.join(_det37), _ok37)

    # S-38（R50，专家第十轮 §3.1）：prompt 不得对已提及特征授权默认值，也不得注入答案
    _p38 = os.path.join(root, 'feagpt_repro', 'gen_candidates_v2.js')
    _ok38, _det38 = prompt_no_blind_default(_p38)
    add('S-38', 'prompt 无盲填授权且未注入 expected_clarifications（R50）',
        '不含「未提长桁→长桁数=0」；含数量铁律；不含 expected_clarifications',
        _det38, _ok38)

    # S-39（R53，专家第十轮 §5.2）：prompt-v2 代成绩单的 prompt sha 必须与源码一致
    # ——改了 prompt 没重生成，成绩单就挂着一个已经不存在的 harness 的分数。
    _det39, _ok39 = [], True
    _gen39 = os.path.join(root, 'feagpt_repro', 'gen_candidates_v2.js')
    for _lab, _p in [('C-032', _sc_paths[2][1]), ('C-033', _sc_paths[3][1])]:
        _sha = None
        if os.path.exists(_p):
            _sha = (json.load(open(_p, encoding='utf-8')).get('provenance') or {}).get('prompt_sha256')
        _o, _d = prompt_sha_matches_source(_gen39, _sha, _lab)
        _det39.append(_d); _ok39 = _ok39 and _o
    add('S-39', 'prompt-v2 代成绩单的 prompt sha == 当前源码（R53）',
        'C-032/C-033 的 provenance.prompt_sha256 非 UNKNOWN 且等于生成器当前 SYS 的 sha256',
        '；'.join(_det39), _ok39)

    # S-40（R54，W5c-6h）：MSR 是**条件通过率**——分母只含「产出 spec 的非澄清题」，
    # 所以不同成绩单的分母可以不同，裸报 pct 会被读成同口径。
    # 实证：C-033 exam MSR 20/21 = 95.2% 会「高于」C-032 的 20/22 = 90.9%，
    # 差的正是被排除的那条模型侧无输出（cfrp45s_d40）——与那条 MSR 反直觉同源。
    # 闸的两端：①口径必须写进成绩单（msr_definition 非空）；②排除了谁必须点名（不得只降分母）。
    _det40, _ok40 = [], True
    for _lab, _p in _sc_paths:
        if not os.path.exists(_p):
            _det40.append(f'{_lab} 缺成绩单'); _ok40 = False; continue
        _o, _d = msr_conditional_declared(json.load(open(_p, encoding='utf-8')), _lab)
        _det40.append(_d); _ok40 = _ok40 and _o
    add('S-40', 'MSR 条件口径必须写进成绩单且排除项点名（R54）',
        'msr_section.msr_definition 非空；n_no_spec_excluded_ids 与实际排除数一致',
        '；'.join(_det40), _ok40)

    # S-41（R55，第十一轮 §3.1/D4）：prompt 版本变更后，「exam 不变但 dev 变」的**反向变化
    # 必须逐题定位**，且必须闭环。只报净额是不够的——C-032 的 dev −1 实际是 +1/−2，
    # 三种解释（模型退步 / 题面修正被兑现 / 量级采样波动）对应三种处置，混在一起就没法判。
    # 闸分三端：①产物存在且闭合；②每条翻转都带字段级 gold/候选证据；③CLAIMS 里点名了它。
    _p41 = os.path.join(root, 'feagpt_repro', 'reports', 'diagnostics', 'dev_reversal_v6c_p2.json')
    _ok41, _det41 = dev_reversal_closed(_p41)
    _claims_txt = _txt(os.path.join(root, 'FEM-Bench-Aero', 'CLAIMS.md'))
    if 'dev_reversal' not in _claims_txt:
        _ok41 = False
        _det41 += '；★ CLAIMS 未引用该产物（R55：定位结果必须写进 claim）'
    add('S-41', 'prompt 变更后的 dev 反向变化必须逐题定位并联署（R55）',
        'dev_reversal 产物闭合（旧通过 + fail→pass − pass→fail == 新通过）、每条翻转带字段级证据、CLAIMS 引用',
        _det41, _ok41)

    # S-42（R56，第十一轮 §5.1/W5d）：跨模型榜单必须**三列并排**（任务级 / 字段级 / 失败分层），
    # 且 MSR 分母不等时不得出现 Δ。动机：本基准里三个口径会给出**相反排名**
    # （TSR 92>88、字段级 PASS>BELOW、条件 MSR 90.9<95.2），只引一列就能得出任意结论。
    _p42 = os.path.join(root, 'feagpt_repro', 'reports', 'w5d_leaderboard.json')
    _ok42, _det42 = w5d_leaderboard_ok(_p42)
    add('S-42', '跨模型榜单三列并排且分母不等不出 MSR Δ（R56）',
        '榜单含任务级/字段级/失败分层三组；msr_delta_allowed 由分母算；分母不等时 msr_delta_pp 为空且 md 写明不可相减',
        _det42, _ok42)

    # S-43（R57 补，W5d-1）：prompt 消融结论与当前 prompt sha 必须一致。
    # 动机：本轮的 v3/v3b 都被否决（零收益 + 失败点迁移），prompt 已回退到 v2。
    # 若没有这道闸，「写了否决但没回退」或「回退了但没记录」都不会报错。
    _p43_abl = os.path.join(root, 'feagpt_repro', 'reports', 'diagnostics', 'prompt_v3_ablation.json')
    _gen43 = os.path.join(root, 'feagpt_repro', 'gen_candidates_v2.js')
    _base43 = ((json.load(open(_sc_paths[2][1], encoding='utf-8')).get('provenance') or {}
                ).get('prompt_sha256') if os.path.exists(_sc_paths[2][1]) else None)
    _ok43, _det43 = prompt_ablation_consistent(_p43_abl, _gen43, _base43, 'C-035')
    add('S-43', 'prompt 消融结论必须与当前 prompt sha 一致（R57）',
        '消融产物有 decision.adopt 与变体清单；否决 ⇒ 当前 sha == C-032 基线；采纳 ⇒ 当前 sha ≠ 基线',
        _det43, _ok43)

    # S-44（R58，T-A3；来自复核 N-1/N-2）：**官方导航文件必须被 gate 读**。
    # 根因：44 项语义检查没有一条读 `reports/INDEX.md`，于是「⓪ 当前官方 headline（C-029）」
    # 与 §1 的（C-032）长期并存，而 INDEX 正是 AGENTS §0 要求 agent 查「当前成绩单路径」的文件。
    _head44 = sorted({cid for cid, r in by.items()
                      if '（对外 headline）' in (r.get('status') or '')
                      or '(对外 headline)' in (r.get('status') or '')})
    _ok44, _det44 = index_consistency(
        os.path.join(root, 'feagpt_repro', 'reports', 'INDEX.md'),
        _latest_nc_json(root),
        _head44[0] if len(_head44) == 1 else None)
    add('S-44', '官方导航文件 INDEX 的 headline 指向与负控编号必须与 artifact 一致（R58）',
        '含 claim id 的 headline 行全部指向唯一 headline（或显式标 historical）；'
        '负控行的 NC-x..y 与 =N/N 与最新 negative_controls_<N>.json 实读一致',
        _det44, _ok44)

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--claims', default=CLAIMS_DEFAULT)
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--json', default=os.path.join(HERE, 'reports', 'check_claims.json'))
    ap.add_argument('--include-nonactive', action='store_true',
                    help='连 superseded/retracted 一起查（默认只查 active）')
    ap.add_argument('--semantic', dest='semantic', action='store_true', default=True,
                    help='同时核对文本数字 vs artifact 实读（R29，默认开）')
    ap.add_argument('--no-semantic', dest='semantic', action='store_false',
                    help='只做结构检查（旧行为）')
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
        _cmd = r.get('command', '')
        flags = [t.strip('`.,;()（）') for t in
                 (FLAG_RE.findall(_cmd) + CP_RE.findall(_cmd) + APPEND_RE.findall(_cmd))]
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

    # ---- 语义计数（R29）：文本数字必须等于 artifact 实读 ----
    sem = semantic_checks(root, rows) if args.semantic else []
    sem_fails = [f"{s['id']}: {s['desc']} -> 声称 {s['actual']} / 实测 {s['expect']}"
                 for s in sem if not s['ok']]
    fails_all = fails + sem_fails

    report = {'claims_file': os.path.relpath(args.claims, root).replace('\\', '/'),
              'n_active_claims': len({r['claim_id'] for r in results}),
              'n_artifacts': len(results),
              'n_fail': len(fails_all),
              'n_fail_structural': len(fails),
              'n_fail_semantic': len(sem_fails),
              'all_ok': not fails_all, 'fails': fails_all,
              'structural_fails': fails, 'semantic_fails': sem_fails,
              'semantic': sem, 'results': results}
    os.makedirs(os.path.dirname(os.path.abspath(args.json)) or '.', exist_ok=True)
    json.dump(report, open(args.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('== CLAIMS 自检（R25/R26/R27 结构 + R29 语义计数）==')
    for rec in results:
        tag = 'ok  ' if rec['ok'] else 'FAIL'
        extra = '' if rec['ok'] else '  <- ' + '; '.join(rec['problems'])
        print(f"  [{tag}] {rec['claim_id']:<7} {rec['artifact']}{extra}")
    if sem:
        print('-- 语义计数（声称值 vs artifact 实读）--')
        for s in sem:
            if s.get('skip'):
                print(f"  [skip] {s['id']:<5} {s['desc']}: {s['actual']}")
                continue
            tag = 'ok  ' if s['ok'] else 'FAIL'
            print(f"  [{tag}] {s['id']:<5} {s['desc']:<34} 声称={s['actual']} 实测={s['expect']}")
    print(f"\nactive claims {report['n_active_claims']} 条 / artifact {report['n_artifacts']} 个 / "
          f"语义项 {len([s for s in sem if not s.get('skip')])} 条 "
          f"-> {'全过' if report['all_ok'] else f'结构 {len(fails)} 项 + 语义 {len(sem_fails)} 项失败'}")
    print(f"report -> {args.json}")
    if fails_all:
        print('红线条 R26/R29：CLAIMS 自检未过，不得对外引用这些数字。')
        return 1
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
