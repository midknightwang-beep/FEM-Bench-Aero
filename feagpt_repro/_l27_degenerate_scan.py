# -*- coding: utf-8 -*-
"""_l27_degenerate_scan.py — L2-7「退化解」量化闸（T-L27）

要回答的唯一问题：**一个不看题面的固定字符串，能不能在澄清题上拿满分？**

2026-11-01 实测：能，而且是 100%。原因不是某一条元数据缺失，是三条叠加：
  ① L2 的 64 条**全部**只有 1 个 expected 字段（`Counter({1: 64})`）；
  ② L2 的 64 条**全部**没有 `clarify_aliases` ⇒ 判分只认 ASCII 键名；
  ③ L2 的 64 条**全部**没有 `clarify_wrong_keys` ⇒ `hit_wrong` 恒空，「多问」零代价。
  ⇒ 判据实际退化为「跨题 13 个键名里出现该题那一个」。把 13 个全列一遍 = 100%。
     （产物：`reports/diagnostics/l27_degenerate_*.json`）

本闸不改任何判分，只做三件事：
  · 把「提及（K）」与「索要（Q）」分开（判据实现唯一来源：`score_baseline.clarify_mention_split`）；
  · 按 `|K| >= kmax` 判「退化」（阈值依据见下）；
  · 扫描任意候选目录，报出「若接入判分会从 PASS 翻 FAIL 的条数」——**这是接入前必须为 0 的数**。

阈值依据（kmax = 3，**不是拍脑袋**）
  · 真实候选（v7 glm/ds 的 L2 128 条 + L3 10 条）中，**当前 PASS 的条目 |K| 上界 = 2**；
  · 最小族池 = 3（`stiffened_panel`）⇒ 要列满整族，至少 3 个键；
  · ⇒ 3 = 实测上界 + 1，且恰好等于「列满最小族」的下界。两侧都有含义。

**已知残余（必须随数字一起报，不得省略）**
  「纯键名列举、不带任何谓语」可以绕开「索要」判定：列 k 个键名 ⇒ 通过率 = k / 族池。
  加固后最优攻击是列 2 个，加权通过率 ≈ 38%（从 100% 降下来，但**不是 0**）。
  根治只能靠题型（加入「信息完备、不该澄清」的 L2 题 ⇒ 穷举在那些题上必错），
  那要改卷（R65：新版本 + 重冻结 + bridge），不在本闸范围。

用法
  "$PY" _l27_degenerate_scan.py                      # 扫真实候选四份
  "$PY" _l27_degenerate_scan.py --cand <DIR> --label degenerate_global
  "$PY" _l27_degenerate_scan.py --self-test          # 构造性自检（六向）
退出码：0 全过 ／ 1 自检红 ／ 2 环境错误
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from score_baseline import (CLARIFY_DEGEN_KMAX, clarify_key_pool,        # noqa: E402
                            clarify_mention_split, judge_clarify_field_level)

TASKS = os.path.join(HERE, 'tasks', 'tasks.jsonl')
KMAX = CLARIFY_DEGEN_KMAX   # 阈值只有一处定义（score_baseline）；改它必须同时改自检边界两向


def load_tasks(path=TASKS):
    return [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]


def _flat(cand):
    """候选的 clarify 是「字符串里装的 JSON 数组」⇒ 取出来拼平（与 P-1 同口径）。"""
    cl = (cand or {}).get('clarify')
    if not cl:
        return None
    if isinstance(cl, list):
        return ' | '.join(str(x) for x in cl)
    try:
        v = json.loads(cl)
        return ' | '.join(str(x) for x in v) if isinstance(v, list) else str(v)
    except Exception:
        return str(cl)


def scan(cand_dir, tasks, pool, kmax=KMAX, label=None):
    """扫一个候选目录。只判「该澄清的题」（expected 非空且候选只给 clarify）。"""
    rows, hist = [], collections.Counter()
    for t in tasks:
        p = os.path.join(cand_dir, t['task_id'] + '.json')
        if not os.path.exists(p):
            continue
        cand = json.load(open(p, encoding='utf-8'))
        txt = _flat(cand)
        if txt is None or cand.get('spec'):
            continue                      # spec 分支不属本闸（那是「该答不答」的判据）
        exp = list(t.get('expected_clarifications') or [])
        if not exp:
            continue                      # 无缺项的题不属 L2-7
        ok_old, _ = judge_clarify_field_level(txt, t, degen_check=False)   # 接入前的口径
        ok_new, _ = judge_clarify_field_level(txt, t, degen_check=True)    # 接入后的口径
        K, Q, ctx = clarify_mention_split(txt, pool)
        degen = len(K) >= kmax
        rows.append({'task_id': t['task_id'], 'family': t['family'],
                     'expected': exp, 'K': K, 'Q': Q, 'ctx': ctx,
                     'nK': len(K), 'degen': degen,
                     'pass_old': ok_old,
                     'pass_new': ok_new,
                     'text': txt})
        hist[len(K)] += 1
    flip = [r for r in rows if r['pass_old'] and not r['pass_new']]
    out = {'label': label or os.path.basename(os.path.normpath(cand_dir)),
           'cand_dir': cand_dir, 'kmax': kmax, 'pool_size': len(pool),
           'n_scored': len(rows), 'nK_hist': dict(sorted(hist.items())),
           'n_degen': sum(1 for r in rows if r['degen']),
           'n_pass_old': sum(1 for r in rows if r['pass_old']),
           'n_pass_new': sum(1 for r in rows if r['pass_new']),
           'n_flip': len(flip),
           'flips': [{'task_id': r['task_id'], 'expected': r['expected'], 'K': r['K']}
                     for r in flip],
           'rows': rows}
    return out


def report(res, say=print):
    say('%-22s 评分 %3d 条  |K| 分布=%s  kmax=%d'
        % (res['label'], res['n_scored'], res['nK_hist'], res['kmax']))
    say('    判退化 %d 条 ／ 旧 PASS %d 条 → 新 PASS %d 条 ／ **翻红 %d 条**'
        % (res['n_degen'], res['n_pass_old'], res['n_pass_new'], res['n_flip']))
    say('    旧通过率 %.1f%% → 新通过率 %.1f%%'
        % (100.0 * res['n_pass_old'] / max(1, res['n_scored']),
           100.0 * res['n_pass_new'] / max(1, res['n_scored'])))
    for f in res['flips'][:8]:
        say('      ! 翻红 %-40s exp=%s K=%s' % (f['task_id'][:40], f['expected'], f['K']))


# ---------------------------------------------------------------------------
# 自检：构造性六向。**每一条都必须能指名它要抓的东西**。
# ---------------------------------------------------------------------------
def self_test(kmax=KMAX):
    pool = ['hole_d', 'length', 'n_frames', 'n_ribs', 'n_stringers',
            'n_stringers_per_skin', 'rib_thickness', 'skin_thickness',
            'stringer_height', 'sweep_deg', 'thickness', 'tip_chord_ratio', 'width']
    cases = []

    def add(name, text, n_expected, want_degen, why):
        K, Q, ctx = clarify_mention_split(text, pool)
        degen = len(K) >= kmax
        cases.append((name, degen == want_degen, len(K), Q, want_degen,
                      '|K|=%d Q=%s' % (len(K), Q), why))

    # ①② 真实形态（必须不判退化）
    add('① 真实单键提问', 'structure.params.n_frames 缺失，请给出框的数量', 1, False,
        '真实的 glm 形态')
    add('② 真实「上下文+索要」', '题面给出了 stringer_height/stringer_thickness，'
        '但缺少每侧蒙皮的 n_stringers_per_skin，请补充该字段', 1, False,
        'P-1 的 4 条假阳性就长这样，判退化等于惩罚好澄清')
    # ③④ 两种穷举（必须判退化）
    add('③ 全局穷举（13 键一句）', '请提供以下参数：' + '、'.join(pool) + '，缺一不可。',
        1, True, '本轮实测拿 64/64 的那个攻击')
    add('④ 按族穷举（最小族池 3）', '请提供以下参数：' + '、'.join(pool[2:5]) + '。',
        1, True, '族池小，绝对阈值必须 <= 最小族池')
    # ⑤ 边界下侧：|K| = kmax-1 必须**不**判退化 —— 钉住阈值，防有人悄悄改成 2
    add('⑤ 边界下侧 |K|=kmax-1', '请提供 ' + '、'.join(pool[:kmax - 1]) + '。', 1, False,
        '真实 PASS 的上界就在这里；改成 kmax-1 会静默改成绩')
    # ⑥ 边界上侧：|K| = kmax 必须判退化
    add('⑥ 边界上侧 |K|=kmax', '请提供 ' + '、'.join(pool[:kmax]) + '。', 1, True,
        '越过阈值一格就该红')

    ok_all = True
    for name, ok, nK, Q, want, detail, why in cases:
        ok_all = ok_all and ok
        print('  [%s] %-26s %-28s 期望退化=%-5s 由 %s'
              % ('ok  ' if ok else 'BAD!', name, detail, want, why))
    print('\n自检 %d/%d' % (sum(1 for c in cases if c[1]), len(cases)))
    return 0 if ok_all else 1


def emit_degenerate(out_dir, tasks, pool, mode='global', k=2):
    """生成退化候选（**可复现的攻击本身**，不是只留一句结论）。

    mode='global'  ⇒ 一句列出全池键名（T-L27 实测拿 100%）
    mode='family'  ⇒ 只列该题所属族的全部键名（同样 100%，且族池最小 3 ⇒ 阈值必须 <= 3）
    mode='list-k'  ⇒ 纯列举 k 个、不带任何谓语（加固后的残余攻击，用来量残余通过率）
    """
    fam = collections.defaultdict(set)
    for t in tasks:
        for kk in (t.get('expected_clarifications') or []):
            if kk in pool:
                fam[t['family']].add(kk)
        for kk in (t.get('clarify_wrong_keys') or []):
            if kk in pool:
                fam[t['family']].add(kk)
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for t in tasks:
        if t['input_level'] != 'L2' or not (t.get('expected_clarifications') or []):
            continue
        if mode == 'global':
            keys, txt = pool, '请提供以下参数：' + '、'.join(pool) + '，缺一不可。'
        elif mode == 'family':
            keys = sorted(fam[t['family']])
            txt = '请提供以下参数：' + '、'.join(keys) + '。'
        elif mode == 'list-k':
            keys = sorted(fam[t['family']])[:k]
            txt = '、'.join(keys)
        else:
            raise SystemExit('[FATAL] 未知 mode: %s' % mode)
        cand = {'task_id': t['task_id'], 'input_level': 'L2',
                'model': 'degenerate-%s' % mode, 'prompt_sha256': 'd' * 64,
                'clarify': json.dumps([txt], ensure_ascii=False), 'spec': None,
                'turns_used': 1, 'validation_history': [], 'raw_len': len(txt),
                'presentation': 'degenerate'}
        json.dump(cand, open(os.path.join(out_dir, t['task_id'] + '.json'), 'w',
                             encoding='utf-8'), ensure_ascii=False, indent=1)
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cand', action='append', default=None,
                    help='候选目录（可重复）；缺省扫 candidates_l{2,3}_v7_{glm,ds}')
    ap.add_argument('--tasks', default=TASKS)
    ap.add_argument('--kmax', type=int, default=KMAX)
    ap.add_argument('--label', default=None)
    ap.add_argument('--out', default=None, help='JSON 落盘路径（缺省不写）')
    ap.add_argument('--emit-degenerate', default=None, metavar='DIR',
                    help='生成退化候选到 DIR（可复现攻击本身）')
    ap.add_argument('--mode', default='global', choices=('global', 'family', 'list-k'))
    ap.add_argument('--k', type=int, default=2, help='--mode list-k 时列举几个键名')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()

    if a.self_test:
        return self_test(a.kmax)

    if not os.path.exists(a.tasks):
        print('[FATAL] 找不到 %s' % a.tasks)
        return 2
    tasks = load_tasks(a.tasks)
    pool = clarify_key_pool(tasks)

    if a.emit_degenerate:
        n = emit_degenerate(a.emit_degenerate, tasks, pool, a.mode, a.k)
        print('已生成 %d 条退化候选（mode=%s, k=%d）-> %s' % (n, a.mode, a.k, a.emit_degenerate))
        return 0

    dirs = a.cand or [os.path.join(HERE, d) for d in
                      ('candidates_l2_v7_glm', 'candidates_l2_v7_ds',
                       'candidates_l3_v7_glm', 'candidates_l3_v7_ds')]
    print('池 %d 个纯 ASCII 键；kmax=%d\n' % (len(pool), a.kmax))
    results = []
    for i, d in enumerate(dirs):
        if not os.path.isdir(d):
            print('[WARN] 跳过不存在的目录 %s' % d)
            continue
        res = scan(d, tasks, pool, a.kmax, a.label if len(dirs) == 1 else None)
        report(res)
        results.append(res)
        print()

    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        slim = [{k: v for k, v in r.items() if k != 'rows'} for r in results]
        json.dump({'kmax': a.kmax, 'pool': pool, 'pool_size': len(pool),
                   'results': slim},
                  open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('-> %s' % a.out)

    # ★ 闸的语义：**「翻红」非 0 不是错**（那是要人拍板的口径变更），但必须报出来。
    return 0


if __name__ == '__main__':
    sys.exit(main())
