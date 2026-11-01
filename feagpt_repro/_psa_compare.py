# -*- coding: utf-8 -*-
"""T-PSA 阶段 2：批次对比（**结构通过率 + TSR 一起算**）。

★ 为什么要两个口径（本轮血的教训）：
  只算「首轮结构通过」会漏掉最严重的回归——p3 批结构全绿，但把 gold 里不存在的
  `mesh.order` / `mesh.refine_le` 写进了 spec，`spec_fidelity` 判自创键 ⇒ TSR 从
  92% 塌到 36%，而结构口径一个红点都没有。
  ⇒ **「闸通过」和「答案对」是两个判据，必须并列报。**

口径（与 task_b1kpi_report.md §6 一致）：
  · 分母 = 产出 spec 的候选数（澄清题不进结构校验，不得混入分母）
  · 「首轮通过」= 有 spec 且 validation_history 为空（turns_used == 1）
  · 首轮错误按类归属，一条错误只归一类（优先级 M > Z > S > T > O）
  · TSR 直接调 evaluate.spec_fidelity（engineering_layer=True），不另写一套比对

用法：
  python _psa_compare.py --pairs v7glm=candidates_l3_v7_glm:...:candidates_l3_v7_glm_p4
  python _psa_compare.py --json out.json           # 用内置默认批次表
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evaluate as E  # noqa: E402

# 默认批次表：tag -> (基线目录, 待评目录…)
DEFAULT_PAIRS = [
    ('v7  glm', ['candidates_l3_v7_glm', 'candidates_l3_v7_glm_p3', 'candidates_l3_v7_glm_p4']),
    ('v7  ds',  ['candidates_l3_v7_ds',  'candidates_l3_v7_ds_p3',  'candidates_l3_v7_ds_p4']),
    ('v6c glm', ['candidates_l3_v6c_glm_p2', 'candidates_l3_v6c_glm_p3', 'candidates_l3_v6c_glm_p4']),
    ('v6c ds',  ['candidates_l3_v6c_ds_p2',  'candidates_l3_v6c_ds_p3',  'candidates_l3_v6c_ds_p4']),
]


def classify(err):
    """把一条 ajv 错误归到类。顺序即优先级：越具体的越先判。

    ★ 坑（本轮实测）：`size` 那条错误的原文是
        `/mesh 不允许的键 "size"，请删除。mesh 允许键: size_chord/size_span/...`
      它**本身就含 size_chord**，所以不能用「不含 size_chord」来排除；
      必须精确匹配 `不允许的键 "size"`。否则 S 恒为 0，该判据变成空判据（新旧都 0，看着全绿）。
    """
    e = err or ''
    if 'required property' in e and '/material' in e:
        return 'M'                      # material 缺 required 键
    if 'required property' in e and '/mesh' in e:
        return 'Z'                      # mesh 缺 size_chord/size_span
    if '不允许的键 "size"' in e or "不允许的键 'size'" in e:
        return 'S'                      # size 被当自创键
    if '/analysis' in e and 'type' in e:
        return 'T'                      # analysis.type 自创键
    return 'O'


def tsr_of(spec, task_id):
    """调 evaluate.spec_fidelity；gold 缺失或异常时返回 (None, ['<无 gold>'])。"""
    try:
        gold = json.load(open(E.gold_spec_path(E.case_id_of(task_id)), encoding='utf-8'))
    except Exception:
        return None, ['<gold 缺失>']
    fam = (gold.get('structure') or {}).get('family')
    try:
        r = E.spec_fidelity(spec, gold, fam, engineering_layer=True)
    except Exception as exc:                      # 判分器自己崩 = 必须显式暴露
        return None, [f'<judge error: {exc}>']
    return bool(r['pass']), [f['field'] for f in r['failed']]


def scan(d):
    files = sorted(glob.glob(os.path.join(d, '*.json')))
    r = {'dir': os.path.basename(d), 'n_total': len(files),
         'n_spec': 0, 'n_clarify': 0, 'n_null': 0,
         'struct_first_pass': 0, 'turns': {}, 'err1': {},
         'tsr_pass': 0, 'tsr_first_pass': 0,
         'tsr_judged': 0, 'tsr_nogold': 0,
         'fail_fields': {}, 'model': None}
    for p in files:
        c = json.load(open(p, encoding='utf-8'))
        r['model'] = c.get('model') or r['model']
        spec = c.get('spec')
        vh = c.get('validation_history') or []
        if spec is None:
            r['n_clarify' if c.get('clarify') else 'n_null'] += 1
            continue
        r['n_spec'] += 1
        t = c.get('turns_used') or (len(vh) + 1)
        r['turns'][str(t)] = r['turns'].get(str(t), 0) + 1
        if not vh:
            r['struct_first_pass'] += 1
        else:
            for e in (vh[0].get('errors') or []):
                k = classify(e)
                r['err1'][k] = r['err1'].get(k, 0) + 1
        ok, fails = tsr_of(spec, c.get('task_id') or os.path.basename(p)[:-5])
        if ok is None:
            r['tsr_nogold'] += 1
            continue
        r['tsr_judged'] += 1
        if ok:
            r['tsr_pass'] += 1
            if not vh:
                r['tsr_first_pass'] += 1
        else:
            for f in fails:
                r['fail_fields'][f] = r['fail_fields'].get(f, 0) + 1
    return r


def pct(a, b):
    return (100.0 * a / b) if b else 0.0


def line(tag, r):
    e1 = r['err1']
    return (f"{tag:22s} n={r['n_total']:3d} spec={r['n_spec']:3d} clar={r['n_clarify']:2d} | "
            f"结构首过={r['struct_first_pass']:2d}/{r['n_spec']:<2d}({pct(r['struct_first_pass'], r['n_spec']):5.1f}%) | "
            f"TSR(spec题全卷)={r['tsr_pass']:2d}/{r['tsr_judged']:<2d}({pct(r['tsr_pass'], r['tsr_judged']):5.1f}%) "
            f"首轮TSR={r['tsr_first_pass']:2d} | "
            f"M={e1.get('M',0):3d} Z={e1.get('Z',0):3d} S={e1.get('S',0):3d} T={e1.get('T',0):3d} O={e1.get('O',0):3d} "
            f"turns={r['turns']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default='')
    ap.add_argument('--pairs', default='',
                    help='tag=d1:d2:d3（目录名，相对本目录）；缺省用内置表')
    a = ap.parse_args()

    if a.pairs:
        pairs = []
        for spec in a.pairs.split(','):
            tag, dirs = spec.split('=', 1)
            pairs.append((tag, dirs.split(':')))
    else:
        pairs = DEFAULT_PAIRS

    out = {}
    print('=' * 132)
    for tag, dirs in pairs:
        print(f'--- {tag} ---')
        row = []
        for d in dirs:
            pd = os.path.join(HERE, d)
            if not os.path.isdir(pd) or not glob.glob(os.path.join(pd, '*.json')):
                print(f'  {"缺/空：" + d:60s}')
                continue
            r = scan(pd)
            print('  ' + line(d, r))
            row.append(r)
        out[tag] = row
        print()
    print('=' * 132)
    print('说明：结构=ajv 闸通过；TSR(spec题全卷)=spec_fidelity 在**产出 spec 的题**上的通过率；')
    print('      ★ 与 scorecard 的 TSR **不是同一个量**：后者按 exam(25)/dev(30) 分卷、且把澄清题算进分子。')
    print('      M/Z/S/T/O 为首轮错误分类；turns 为 spec 题的轮数分布')
    if a.json:
        json.dump(out, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'已写 {a.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
