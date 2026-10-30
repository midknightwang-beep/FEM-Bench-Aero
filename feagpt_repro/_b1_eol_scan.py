# -*- coding: utf-8 -*-
"""B-1：统计「本仓工作区」与「干净 clone 工作区」逐文件 sha256 差异。

用途：量化 `core.autocrlf=true` + 无 .gitattributes 对 sha256 锚点的影响面。
判据：只统计两侧都存在的入库文件；打印差异文件清单（按后缀分组）。
"""
import hashlib, os, subprocess, sys, collections


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    repo = r'F:\AI FEA Modeling DataSets'
    clone = sys.argv[1]
    files = subprocess.run(['git', '-c', 'core.quotepath=false', 'ls-files'], cwd=repo,
                           capture_output=True, text=True, encoding='utf-8').stdout.split('\n')
    files = [f for f in files if f.strip()]
    same = diff = missing = 0
    by_ext = collections.Counter()
    samples = []
    for f in files:
        a = os.path.join(repo, f)
        b = os.path.join(clone, f)
        if not os.path.exists(b):
            missing += 1
            continue
        try:
            sa, sb = sha256(a), sha256(b)
        except OSError:
            missing += 1
            continue
        if sa == sb:
            same += 1
        else:
            diff += 1
            ext = os.path.splitext(f)[1] or '(无后缀)'
            by_ext[ext] += 1
            if len(samples) < 8:
                samples.append(f)
    print('入库文件总数 : %d' % len(files))
    print('两侧 sha 相同: %d' % same)
    print('两侧 sha 不同: %d  <-- 换机后锚点会断' % diff)
    print('clone 缺失   : %d' % missing)
    print('按后缀分布   :', dict(by_ext.most_common(12)))
    print('样例         :', samples)


if __name__ == '__main__':
    main()
