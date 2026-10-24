# -*- coding: utf-8 -*-
"""
fetch_data.py — 数据集本体获取与校验（W4a P0-5：让 v1.0 可复现）

v1.0-rc 标签只含代码+清单+任务层；数据集本体（modeling/，236 MB）以归档包分发：
  F:/FEA_Archive_20261024/FEM-Bench-Aero-v1.0-data.tar.gz + SHA256SUMS.txt

用法：
  python fetch_data.py --src F:/FEA_Archive_20261024/FEM-Bench-Aero-v1.0-data.tar.gz
  python fetch_data.py --src <path> --dest ../FEM-Bench-Aero   # 默认解包到 ../FEM-Bench-Aero/
校验：SHA256 对比 SHA256SUMS.txt（同目录）；解包后核对 modeling/ 目录条数 = manifest.n_cases。
"""
import argparse, hashlib, json, os, sys, tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def sha256(path, buf=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(buf):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='FEM-Bench-Aero-v1.0-data.tar.gz 路径')
    ap.add_argument('--dest', default=os.path.join(ROOT, 'FEM-Bench-Aero'))
    ap.add_argument('--skip-hash', action='store_true', help='跳过 SHA256（调试用，不建议）')
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    if not os.path.exists(src):
        print(f'[FATAL] 归档不存在: {src}')
        return 2
    sums = os.path.join(os.path.dirname(src), 'SHA256SUMS.txt')
    if not args.skip_hash:
        if not os.path.exists(sums):
            print(f'[FATAL] SHA256SUMS 不存在: {sums}')
            return 2
        want = None
        for ln in open(sums, encoding='utf-8'):
            parts = ln.split()
            if len(parts) == 2 and os.path.basename(parts[1]) == os.path.basename(src):
                want = parts[0]
        if want is None:
            print(f'[FATAL] SHA256SUMS 里没有 {os.path.basename(src)} 的记录')
            return 2
        got = sha256(src)
        if got != want:
            print(f'[FATAL] SHA256 不匹配\n  want {want}\n  got  {got}')
            return 2
        print(f'[OK] SHA256 校验通过: {got[:16]}…')

    # 解包（W4c P1-3：Python tarfile——GNU tar 把 F: 当远程主机）
    print(f'解包 {src} -> {args.dest}')
    with tarfile.open(src, 'r:gz') as tf:
        tf.extractall(args.dest)

    # 条数核对
    man = json.load(open(os.path.join(args.dest, 'manifest.json'), encoding='utf-8'))
    n_expect = man['summary']['n_cases']
    n_have = len([d for d in os.listdir(os.path.join(args.dest, 'modeling'))
                  if os.path.isdir(os.path.join(args.dest, 'modeling', d))])
    print(f'modeling 目录条数: {n_have}（manifest 期望 {n_expect}）')
    if n_have != n_expect:
        print('[FATAL] 条数不符')
        return 2
    print(f'[OK] 数据集本体就绪：{args.dest}/modeling（{n_have} 条）—— evaluate.py 可用')
    return 0

if __name__ == '__main__':
    sys.exit(main())
