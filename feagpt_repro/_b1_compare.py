# -*- coding: utf-8 -*-
"""B-1 验收：把第三方复现的成绩单与本仓官方 artifact 逐叶子比对。"""
import json, os, sys

REPO = r'F:\AI FEA Modeling DataSets\feagpt_repro'
TMPD = open(os.path.join(os.environ.get('TEMP', ''), 'b1tmp.txt'), encoding='utf-8').read().strip() \
    if os.path.exists(os.path.join(os.environ.get('TEMP', ''), 'b1tmp.txt')) else None


def leaves(o, p=''):
    if isinstance(o, dict):
        for k, v in o.items():
            for x in leaves(v, p + '/' + str(k)):
                yield x
    elif isinstance(o, list):
        for i, v in enumerate(o):
            for x in leaves(v, p + '/%d' % i):
                yield x
    else:
        yield (p, o)


def main():
    tp = sys.argv[1] if len(sys.argv) > 1 else TMPD
    a_path = os.path.join(REPO, 'reports', 'baseline_scorecard_L3_v6c_p2.json')
    b_path = os.path.join(tp, 'b1_c032.json')
    print('官方 artifact:', a_path)
    print('第三方复现  :', b_path)
    a = json.load(open(a_path, encoding='utf-8'))
    b = json.load(open(b_path, encoding='utf-8'))
    la, lb = dict(leaves(a)), dict(leaves(b))
    added = [k for k in lb if k not in la]
    removed = [k for k in la if k not in lb]
    changed = [(k, la[k], lb[k]) for k in la if k in lb and la[k] != lb[k]]
    print('叶子数：官方 %d / 复现 %d' % (len(la), len(lb)))
    print('新增 %d %s' % (len(added), added[:8]))
    print('删除 %d %s' % (len(removed), removed[:8]))
    print('改动 %d' % len(changed))
    for k, x, y in changed[:20]:
        print('    %s  官方=%r  复现=%r' % (k, x, y))
    ident = not added and not removed and not changed
    print('=> 逐字节等价: %s' % ('是' if ident else '否'))


if __name__ == '__main__':
    main()
