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
FLAG_RE = re.compile(r'--(?:report|json|out|report-dir)\s+([^\s`;+]+)')
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
    """
    by = {r.get('claim_id'): r for r in rows if r.get('claim_id')}
    c29, c31 = by.get('C-029'), by.get('C-031')
    if not c31:
        return False, '缺 C-031（第二模型结果必须登记，否则等于没做可重复性验证）'
    s31 = c31.get('status') or ''
    s29 = (c29 or {}).get('status') or ''
    if '（对外 headline）' in s31 or '(对外 headline)' in s31:
        return False, f'C-031 自称 headline —— 跨模型不得事后择优（R48）；status={s31[:60]}'
    if '（对外 headline）' not in s29 and '(对外 headline)' not in s29:
        return False, 'C-029 不再是 headline（主基线地位被动摇，R48/R42）'
    if not any(k in s31 for k in ('supporting', '不作 headline', '可重复性', '第二模型')):
        return False, f'C-031 status 未标明「supporting / 第二模型」定位（R48）：{s31[:80]}'
    return True, 'C-029 仍为唯一 headline；C-031 标为 supporting（第二模型）'


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
    add('S-29', '对外 headline 唯一且为 C-029（R42）', '["C-029"]',
        json.dumps(head_claims, ensure_ascii=False), head_claims == ['C-029'])

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
    _sc_paths = [('C-029', os.path.join(root, 'feagpt_repro', 'reports',
                                        'baseline_scorecard_L3_v6c.json')),
                 ('C-031', os.path.join(root, 'feagpt_repro', 'reports',
                                        'baseline_scorecard_L3_v6c_dsv4pro.json'))]
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
        'C-029 仍标（对外 headline）；C-031 标 supporting/第二模型且不自称 headline',
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
