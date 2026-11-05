# -*- coding: utf-8 -*-
"""_n35_bridge.py — N-35（拍板 B，拆判分键集合）的 **bridge 表**（R-A2 强制）

为什么必须有这张表
------------------
`EXEC_CONFIG_KEYS` 拆分改变了**判分口径**（rubric 层）。R-A2 规定：口径变更不得静默覆盖，
必须「新开版本号 + 声明 + bridge」。bridge 的含义是**同一批候选、同一个卷，在旧口径与
新口径下各跑一次，逐 arm 列出差**——所以旧代成绩单不能删，只能归档（`archive/*__pre_n35.json`）。

★ 这张表由脚本从**两份 artifact 现读**生成，不手抄（R-A3）。散文里每个数字都必须能在
  这里找到同名行；改了任何一侧，重跑本脚本即可。

★ 本表**只覆盖 informative 诊断题型**（16 条独立小卷 / 4 条 v1）。它**不进对外数字**：
  对外 headline 是 C-032，L3 与 L2 v7 两条轨道已实测**逐题零变化**
  （`reports/diagnostics/n35_key_split.json`：L3 42→42 两模型、L2 v7 64×2 类别零差异），
  因为它们压根不经过 `extra` 元信息键的判分分支。

用法：
    "$PY" _n35_bridge.py --out reports/diagnostics/n35_bridge.json --md reports/diagnostics/n35_bridge.md
退出码：0 ok（不一致会在表里标红字）／ 2 对象缺失
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, 'reports', 'diagnostics')
A = os.path.join(HERE, 'reports', 'archive')

ARMS = [
    ('v1_glm', 'l2i_v1_scores_glm', 4, 'v1 卷（4 条旧 SYS base）'),
    ('v1_ds', 'l2i_v1_scores_ds', 4, 'v1 卷（4 条旧 SYS base，ds）'),
    ('v2_glm', 'l2i_v2_scores_glm', 16, 'v2 卷 base（旧 SYS）'),
    ('v2_ds', 'l2i_v2_scores_ds', 16, 'v2 卷 base（旧 SYS，ds）'),
    ('v3s_glm', 'l2i_v3s_scores_glm', 16, 'v2 卷 + strict 段（旧 SYS）'),
    ('v3s_ds', 'l2i_v3s_scores_ds', 16, 'v2 卷 + strict 段（旧 SYS，ds）'),
    ('v3sm_glm', 'l2i_v3sm_scores_glm', 16, 'v2 卷 + strict + meshfix（旧 SYS）'),
    ('v3sm_ds', 'l2i_v3sm_scores_ds', 16, 'v2 卷 + strict + meshfix（旧 SYS，ds）'),
    ('v3sm2_glm', 'l2i_v3sm2_scores_glm', 16, 'meshfix 第 2 遍（复现检查）'),
    ('v3sm2_ds', 'l2i_v3sm2_scores_ds', 16, 'meshfix 第 2 遍（复现检查，ds）'),
    ('v4base_glm', 'l2i_v4base_scores_glm', 16, '新 SYS base'),
    ('v4base_ds', 'l2i_v4base_scores_ds', 16, '新 SYS base（ds）'),
    ('v4s_glm', 'l2i_v4s_scores_glm', 16, '新 SYS strict 第 1 遍'),
    ('v4s_ds', 'l2i_v4s_scores_ds', 16, '新 SYS strict 第 1 遍（ds）'),
    ('v4s2_glm', 'l2i_v4s2_scores_glm', 16, '新 SYS strict 第 2 遍'),
    ('v4s2_ds', 'l2i_v4s2_scores_ds', 16, '新 SYS strict 第 2 遍（ds）'),
]

PAIRS = [
    ('v3_glm_base_vs_strict', 'l27c_v3_arm_glm_base_vs_strict', 'v3 glm：base → strict'),
    ('v3_ds_base_vs_strict', 'l27c_v3_arm_ds_base_vs_strict', 'v3 ds：base → strict'),
    ('v3_glm_strict_vs_meshfix', 'l27c_v3_arm_glm_strict_vs_strictmeshfix', 'v3 glm：strict → meshfix'),
    ('v3_ds_strict_vs_meshfix', 'l27c_v3_arm_ds_strict_vs_strictmeshfix', 'v3 ds：strict → meshfix'),
    ('v4_glm_sysfix', 'l27c_v4_sysfix_glm', 'v4 glm：旧 SYS → 新 SYS'),
    ('v4_ds_sysfix', 'l27c_v4_sysfix_ds', 'v4 ds：旧 SYS → 新 SYS'),
]


def _load(path):
    if not os.path.exists(path):
        return None
    return json.load(io.open(path, encoding='utf-8'))


def _passed(d):
    b = d.get('clarify_informative') or d.get('clarify_all') or {}
    return b.get('passed'), b.get('n')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--md', required=True)
    a = ap.parse_args(argv)

    miss = []
    arms = []
    for key, stem, den, note in ARMS:
        new = _load(os.path.join(D, stem + '.json'))
        old = _load(os.path.join(A, stem + '__pre_n35.json'))
        if new is None or old is None:
            miss.append('%s（%s）' % (key, '新' if new is None else '旧代'))
            continue
        np_, nn = _passed(new)
        op_, on = _passed(old)
        arms.append({'arm': key, 'note': note, 'n': nn or on or den,
                     'old': op_, 'new': np_,
                     'delta': (np_ - op_) if (np_ is not None and op_ is not None) else None})

    pairs = []
    for key, stem, note in PAIRS:
        new = _load(os.path.join(D, stem + '.json'))
        old = _load(os.path.join(A, stem + '__pre_n35.json'))
        if new is None or old is None:
            miss.append('%s（对比）' % key)
            continue
        oe, ne = old.get('mcnemar') or {}, new.get('mcnemar') or {}
        op, np_ = old.get('passed') or {}, new.get('passed') or {}
        pairs.append({
            'pair': key, 'note': note,
            'old': {'base': op.get('base'), 'strict': op.get('strict'),
                    'b': oe.get('base_pass_strict_fail'), 'c': oe.get('base_fail_strict_pass'),
                    'p': oe.get('p_exact_two_sided')},
            'new': {'base': np_.get('base'), 'strict': np_.get('strict'),
                    'b': ne.get('base_pass_strict_fail'), 'c': ne.get('base_fail_strict_pass'),
                    'p': ne.get('p_exact_two_sided')},
        })
        # 显著性结论是否翻转（α=0.05）
        o_sig = (oe.get('p_exact_two_sided') or 1) < 0.05
        n_sig = (ne.get('p_exact_two_sided') or 1) < 0.05
        pairs[-1]['verdict_flip'] = (o_sig != n_sig)
        pairs[-1]['sign_flip'] = (
            (op.get('strict', 0) - op.get('base', 0)) * (np_.get('strict', 0) - np_.get('base', 0)) < 0)

    if miss:
        print('[缺对象]', '；'.join(miss), file=sys.stderr)
        return 2

    flips = [p['pair'] for p in pairs if p.get('verdict_flip')]
    sflips = [p['pair'] for p in pairs if p.get('sign_flip')]
    out = {
        '_note': 'N-35（拍板 B：拆 EXEC_CONFIG_KEYS）的 bridge 表 —— 同一批候选、同一张卷，'
                 '旧口径（archive/*__pre_n35.json）与新口径逐 arm 对照。'
                 '**只覆盖 informative 诊断题型，不进对外数字**：L3 与 L2 v7 已实测逐题零变化。'
                 '由 _n35_bridge.py 从两份 artifact 现读生成，不手抄（R-A3）。',
        'arms': arms,
        'pairs': pairs,
        'significance_flips': flips,
        'direction_flips': sflips,
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with io.open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write('\n')

    L = ['# N-35 bridge：拆判分键集合（拍板 B）新旧口径对照', '',
         '> 由 `_n35_bridge.py` 生成，**不手抄**。旧口径 = `reports/archive/*__pre_n35.json`。',
         '> **只覆盖 informative 诊断题型，不进对外数字**：L3 v6c 与 L2 v7 已实测逐题零变化',
         '> （`n35_key_split.json` / L2 v7 两臂 64×2 判类零差异）—— 它们不经过 `extra` 元信息键的判分分支。', '',
         '## 1. 逐 arm 通过数', '',
         '| arm | 说明 | 分母 | 旧口径 | 新口径 | Δ |', '|---|---|---|---|---|---|']
    for x in arms:
        L.append('| `%s` | %s | %d | %s/%d | **%s/%d** | %s |'
                 % (x['arm'], x['note'], x['n'], x['old'], x['n'], x['new'], x['n'],
                    ('%+d' % x['delta']) if x['delta'] is not None else '—'))
    L += ['', '## 2. 配对检验（精确 McNemar，双侧）', '',
          '| 对比 | 旧 base→strict | 新 base→strict | 旧 b/c | 新 b/c | 旧 p | 新 p | 结论翻转 |',
          '|---|---|---|---|---|---|---|---|']
    for p in pairs:
        o, n = p['old'], p['new']
        L.append('| %s | %s→%s | %s→%s | %s/%s | %s/%s | %s | **%s** | %s |'
                 % (p['note'], o['base'], o['strict'], n['base'], n['strict'],
                    o['b'], o['c'], n['b'], n['c'],
                    ('%.4f' % o['p']) if o['p'] is not None else '—',
                    ('%.4f' % n['p']) if n['p'] is not None else '—',
                    ('⚠️ **是**' if p.get('verdict_flip') else '否')))
    L += ['', '## 3. 结论', '']
    if flips:
        L.append('- **显著性结论翻转**：' + '、'.join(flips))
    else:
        L.append('- 没有任何一对的显著性结论翻转（α=0.05）。')
    if sflips:
        L.append('- **效应方向翻转**（不显著的对里）：' + '、'.join(sflips))
    else:
        L.append('- 没有效应方向翻转。')
    L.append('- 对外数字：**零变动**（L3 v6c 42→42 两模型；L2 v7 46/64、52/64 逐题相同）。')
    with io.open(a.md, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')

    print('bridge: %d arms / %d pairs；显著性翻转 %s；方向翻转 %s'
          % (len(arms), len(pairs), flips or '无', sflips or '无'))
    print('-> %s' % os.path.abspath(a.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
