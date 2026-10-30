"""T-C1：数据包 ↔ 任务卷 的**覆盖差集**落盘（R-A3 禁止手抄）。

为什么需要它（T-B1 的 D-5）：
    `fetch_data.py` 解包后只跟**数据包自己的** `manifest.json` 对账（55 == 55 就过），
    完全不知道**任务卷**要几条。于是「用 v1.0 包跑 v7 卷」这件事在 fetch_data 那一步
    看起来一切正常，到打分阶段才表现为 9 条静默 spec_fail —— 看起来像模型变差。
    本脚本把差集算出来落盘，让「缺哪几条」成为可查事实，而不是一句口头说明。

用法（项目 venv）：
    "$PY" _c1_pack_gap.py --src <DATA_DIR>/FEM-Bench-Aero-v1.0-data.tar.gz \
                          --out reports/diagnostics/data_pack_volume_gap.json

不传 `--src` 时只算「本机 modeling 目录 ↔ 各卷」的差集（用于自检覆盖率）。
"""
import argparse
import json
import os
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from evaluate import case_id_of, FEA  # noqa: E402

VOLUMES = [
    ('v7', os.path.join(HERE, 'tasks', 'tasks.jsonl')),
    ('v6c', os.path.join(HERE, 'reports', 'papers', 'tasks_v6c.jsonl')),
]


def l3_case_ids(path):
    rows = [json.loads(ln) for ln in open(path, encoding='utf-8') if ln.strip()]
    return {case_id_of(r['task_id']) for r in rows if r.get('input_level') == 'L3'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=None, help='数据包 tar.gz（不给则用本机 modeling/）')
    ap.add_argument('--out', default=os.path.join(HERE, 'reports', 'diagnostics',
                                                  'data_pack_volume_gap.json'))
    ap.add_argument('--label', default=None)
    args = ap.parse_args()

    if args.src:
        src = os.path.abspath(args.src)
        if not os.path.exists(src):
            print(f'[FATAL] 数据包不存在：{src}')
            return 2
        with tarfile.open(src, 'r:gz') as tf:
            names = tf.getnames()
            have = {n.split('/')[1] for n in names
                    if n.startswith('modeling/') and n.count('/') >= 1 and n.split('/')[1]}
            man = None
            for n in names:
                if n.endswith('manifest.json') and n.count('/') == 0:
                    man = json.loads(tf.extractfile(n).read().decode('utf-8'))
                    break
        source = 'data_pack'
        label = args.label or os.path.basename(src)
    else:
        modeling = os.path.join(FEA, 'modeling')
        if not os.path.isdir(modeling):
            print(f'[FATAL] 本机 modeling 目录不存在：{modeling}')
            return 2
        have = {d for d in os.listdir(modeling)
                if os.path.isfile(os.path.join(modeling, d, 'spec.json'))}
        man = None
        source = 'local_modeling'
        label = args.label or modeling

    vol_report = {}
    for tag, path in VOLUMES:
        need = l3_case_ids(path)
        missing = sorted(need - have)
        vol_report[tag] = {
            'tasks_path': os.path.relpath(path, HERE).replace(os.sep, '/'),
            'n_l3_tasks': len(need),
            'n_covered': len(need & have),
            'n_missing': len(missing),
            'missing': missing,
            'complete': not missing,
        }

    out = {
        '_note': ('数据包/本机数据集 ↔ 任务卷 的 L3 覆盖差集（T-C1，替代手抄说明）。'
                  '调分侧已有硬闸：require_dataset(expect_ids=…) 会在开跑前拦住不全的情形。'),
        '_version': 'c1-1',
        'source': source,
        'label': label,
        'n_have': len(have),
        'pack_manifest_n_cases': (man or {}).get('summary', {}).get('n_cases'),
        'volumes': vol_report,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f'source = {source}（{label}）')
    print(f'可用 spec.json = {len(have)}'
          + (f'，包内 manifest n_cases = {out["pack_manifest_n_cases"]}' if man else ''))
    for tag, blk in vol_report.items():
        flag = 'OK ' if blk['complete'] else 'GAP'
        print(f'  [{flag}] {tag:4s} 卷 {blk["n_l3_tasks"]:3d} 条 → 覆盖 {blk["n_covered"]:3d}，'
              f'缺 {blk["n_missing"]}')
        for m in blk['missing'][:12]:
            print(f'         - {m}')
    print(f'report -> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
