# -*- coding: utf-8 -*-
"""T-L27c v3 守卫闸：候选里写的 mesh 键必须真的存在于 gold（CONFLICT N-34）。

## 为什么需要这个闸

`gen_candidates_v2.js` 的 `SYS` 第 40 行写「网格键 size_chord/size_span（翼盒）、
**size（板壳类）**」，但**四族全部 gold 的 mesh 段都没有 `size`**。
模型照 prompt 写 `size` ⇒ `spec_fidelity` 按「自造键」判 FAIL。
⇒ prompt 声明了一个 gold 里不存在的键，**没有任何闸发现**。

更难看的是：p3/p4 确实改对过（`_psa_fix_mesh_keys.py` 的 `OLD1`/`NEW1` 都含
「板壳类也用这两个键名——没有 size 这个键」），但 2026-11-01 把 SYS 回滚到 `ce225186`
时这句话**跟着一起消失** —— 闸只锚「sha 变没变」，不锚「sha 对应的那句话对不对」。

## 判据为什么落在**候选产物**上，不落在 prompt 文本上（这条是本闸最重要的设计决定）

第一版实现读 SYS 文本、抽 `\\bsize\\b` 词元再核 gold，结果 **base 与 meshfix 两个 arm 都判红**：
meshfix 的覆盖段原文是「…**没有 size 这个键**」，这句话**提到**了 `size`，但那是**否定**它。

⇒ 只要判据从**自然语言**里取「声明」，改成「不写 size 这两个字」就能绕过，
   而改成「必须出现 size」又会把否定句判成肯定句。
   **「是否出现某词」这条轴根本无法区分肯定与否定**（R77 ⑧：不做关键字判文本对错的闸）。

⇒ 改判**效果**：候选产物里有没有写出 gold 不存在的 mesh 键。
   这正是伤分的那个东西，与 prompt 怎么措辞无关，且天然双向：
   - base arm 的候选写了 `size` ⇒ 红（缺陷真实存在）
   - meshfix arm 的候选不写 ⇒ 绿（修好了）

## 判据（双向）

① **多余键**：候选 mesh 段里出现、而该族 gold 的 mesh 段没有的键 ⇒ 红。
② **缺失键**：该族 gold 的 mesh 段有、候选不写 ⇒ 红（只核①会漏「整段省略」）。

## 诚实边界

- 只核 mesh 段的**键名**，不核取值、不核别的段。
- 不判断 prompt 措辞对错。prompt 里那句错话本身要靠人读 + CONFLICT N-34 记着。
- 候选为空目录时**判红**（「空的东西最干净」，别让空壳满足闸）。

用法：
  python _l27c_check_mesh_keys.py --candidates candidates_l2i_v2_glm     # 预期红
  python _l27c_check_mesh_keys.py --candidates candidates_l2i_v3sm_glm   # 预期绿
  python _l27c_check_mesh_keys.py --gold                                  # 只打印 gold 键集
  python _l27c_check_mesh_keys.py --self-test                             # 自比 + 三向变异
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FEA = os.path.join(ROOT, 'FEM-Bench-Aero')
sys.path.insert(0, HERE)

import evaluate as ev  # noqa: E402  ★ 金标准定位只有一处（T-L27c）


def _fatal(msg):
    """致命前置失败 ⇒ **退出码 2**（不是 1）。

    ★ 这行是负控 NC-82 抓出来的：原先写 `raise SystemExit('…')`，带字符串参数的
      SystemExit 退出码是 **1**，与「闸判红」的 rc=1 撞车 ⇒ 负控分不出
      「前置条件不满足」与「真的检出问题」，而这两件事要触发不同的动作。
    """
    print(msg, file=sys.stderr)
    raise SystemExit(2)


def gold_mesh_by_case():
    """{case_id: set(mesh keys)}，直接读 gold spec。"""
    out = {}
    for p in sorted(glob.glob(os.path.join(FEA, 'modeling', '*', 'spec.json'))):
        s = json.load(open(p, encoding='utf-8'))
        out[os.path.basename(os.path.dirname(p))] = set((s.get('mesh') or {}).keys())
    return out


def scan_candidates(cdir, gold):
    """返回 (n_spec, 明细列表)。明细只记「有问题的题」。"""
    if not os.path.isdir(cdir):
        _fatal(f'[fatal] 候选目录不存在：{cdir}')
    files = sorted(f for f in os.listdir(cdir) if f.endswith('.json'))
    if not files:
        _fatal(f'[fatal] 候选目录是空的：{cdir}（空壳不许通过）')
    n_spec = 0
    bad = []
    for fn in files:
        c = json.load(open(os.path.join(cdir, fn), encoding='utf-8'))
        spec = c.get('spec')
        if not spec:
            continue          # 没给 spec（追问/失败）不归本闸管
        n_spec += 1
        cid = ev.case_id_of(c['task_id'])
        if cid not in gold:
            _fatal(f'[fatal] 候选 {c["task_id"]} 解析到不存在的 gold case「{cid}」')
        g = gold[cid]
        got = set((spec.get('mesh') or {}).keys())
        extra = sorted(got - g)
        missing = sorted(g - got)
        if extra or missing:
            bad.append({'task_id': c['task_id'], 'case_id': cid,
                        'extra': extra, 'missing': missing})
    if n_spec == 0:
        _fatal(f'[fatal] {cdir} 里没有任何给出 spec 的候选 —— 闸无事可做等于没装')
    return n_spec, bad


def _report(tag, n_spec, bad):
    print(f'== {tag} ==')
    print(f'  给出 spec 的候选 {n_spec}，mesh 键有问题的题 {len(bad)}')
    if not bad:
        print('  [ok ] 候选 mesh 键集 == gold 键集')
        return True
    # ★ 统计**遍历全部**，打印才截断 —— 用 bad[:6] 同时做统计与打印会让合计只覆盖前 6 条
    #   （初版就这么写的，实测把 12 处多余报成 6 处，且无人报错）。
    kb = sum(len(b['extra']) for b in bad)
    mb = sum(len(b['missing']) for b in bad)
    for b in bad[:6]:
        print(f"  {b['task_id']}"
              + (f" 多余={b['extra']}" if b['extra'] else '')
              + (f" 缺失={b['missing']}" if b['missing'] else ''))
    if len(bad) > 6:
        print(f'  …还有 {len(bad) - 6} 条')
    print(f'  [红 ] 合计 多余键 {kb} 处 / 缺失键 {mb} 处（覆盖全部 {len(bad)} 条）')
    return False


def self_test(gold):
    """自比 A==A + 三向变异。不依赖任何真实候选目录的状态。"""
    cid = sorted(gold)[0]
    g = gold[cid]
    if not g:
        _fatal('[fatal] 第一条 gold 的 mesh 段是空的，自检没法构造')
    hits = []

    def fake(mesh_keys):
        return {'task_id': f'L1_{cid}', 'spec': {'mesh': {k: 1 for k in mesh_keys}}}

    # ① 自比：与 gold 完全一致 ⇒ 无问题
    _, b0 = _scan_one(fake, cid, g)
    hits.append(('自比A==A->无问题', b0 == []))

    # ② 变体一：多一个 gold 没有的键 ⇒ 必须报多余
    _, b1 = _scan_one(fake, cid, g, extra='size')
    hits.append(('凭空多 size->报多余',
                 len(b1) == 1 and b1[0]['extra'] == ['size'] and not b1[0]['missing']))

    # ③ 变体二：少一个 ⇒ 必须报缺失
    one = sorted(g)[0]
    _, b2 = _scan_one(fake, cid, g, drop=one)
    hits.append((f'漏写 {one}->报缺失',
                 len(b2) == 1 and b2[0]['missing'] == [one] and not b2[0]['extra']))

    # ④ 变体三：整段 mesh 清空 ⇒ 必须报全部缺失（「整段省略」这条路要挡住）
    _, b3 = _scan_one(fake, cid, g, drop_all=True)
    hits.append(('mesh 整段清空->报缺失',
                 len(b3) == 1 and sorted(b3[0]['missing']) == sorted(g)))

    bad = [h for h, ok in hits if not ok]
    for h, ok in hits:
        print(f"  [{'ok ' if ok else 'BAD!'}] {h}")
    return not bad, hits


def _scan_one(make, cid, g, extra=None, drop=None, drop_all=False):
    """自检用的单条扫描（不碰磁盘）。"""
    keys = set() if drop_all else set(g)
    if drop:
        keys.discard(drop)
    if extra:
        keys.add(extra)
    c = make(keys)
    got = set((c['spec'].get('mesh') or {}).keys())
    e, m = sorted(got - g), sorted(g - got)
    return c, ([{'task_id': c['task_id'], 'case_id': cid, 'extra': e, 'missing': m}]
               if (e or m) else [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidates', nargs='*', default=[])
    ap.add_argument('--gold', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--json', default='')
    a = ap.parse_args()

    gold = gold_mesh_by_case()
    if not gold:
        print('[fatal] 没读到任何 gold spec —— 数据集不在？', file=sys.stderr)
        return 2
    union = set()
    for v in gold.values():
        union |= v
    print(f'gold：{len(gold)} 个 case，mesh 键并集 = {sorted(union)}')

    st_ok, st_hits = self_test(gold)
    print(f'自检：{"过" if st_ok else "失败"}')
    if not st_ok:
        print('[红] 闸自身失效（自检未过），不产出判定。', file=sys.stderr)
        return 2
    if a.self_test or a.gold:
        return 0
    if not a.candidates:
        print('（未给 --candidates，只打印 gold 键集）')
        return 0

    payload = {'_note': 'T-L27c v3 网格键效果闸（CONFLICT N-34）',
               'self_test': [{'case': h, 'ok': o} for h, o in st_hits],
               'gold_union': sorted(union), 'runs': []}
    all_ok = True
    for cdir in a.candidates:
        tag = os.path.basename(cdir.rstrip('/\\'))
        n_spec, bad = scan_candidates(cdir, gold)
        ok = _report(tag, n_spec, bad)
        all_ok = all_ok and ok
        payload['runs'].append({'candidates': tag, 'n_spec': n_spec, 'ok': ok,
                                'n_bad': len(bad),
                                # ★ 合计必须是**全部** bad 的合计，不是打印那 6 条的
                                'n_extra': sum(len(b['extra']) for b in bad),
                                'n_missing': sum(len(b['missing']) for b in bad),
                                'bad': bad})
        print()

    if a.json:
        json.dump(payload, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
