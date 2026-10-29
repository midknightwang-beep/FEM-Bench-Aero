# -*- coding: utf-8 -*-
"""
export_msr.py — 从成绩单里把 msr_section 单独导出（W5a'，R25 版本化产物）

为什么单独一份：成绩单会随重打分被重写（TSR/SFR 变），而「全链 MSR 逐任务结果」
是**一次求解的既成事实**，值得单独冻结；桥接/复审时直接比对这一份，不必重解。

用法：
  python export_msr.py --scorecard reports/baseline_scorecard_L3_v4.json --out reports/msr_l3_v4.json
"""
import argparse, json, os, sys
from _paths import rel   # T-A11a：跨盘符安全（见 _paths.py）

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scorecard', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    sc = json.load(open(args.scorecard, encoding='utf-8'))
    msr = sc.get('msr_section')
    if not msr:
        print(f'[export_msr] {args.scorecard} 里没有 msr_section —— 先跑 msr_l3.py')
        return 2
    payload = {'source_scorecard': rel(os.path.abspath(args.scorecard)),
               'scorecard_sha256_note': '源码成绩单重打分后会变，本文件冻结当时的 MSR 结果',
               'msr': msr.get('msr'), 'msr_pct': msr.get('msr_pct'),
               'exam_msr': msr.get('exam_msr'), 'dev_msr': msr.get('dev_msr'),
               'by_split': msr.get('by_split'),
               'failure_class_counts': msr.get('failure_class_counts'),
               'gate_fail_counts': msr.get('gate_fail_counts'),
               'provenance': msr.get('provenance'),
               'per_task': msr.get('per_task')}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)
    json.dump(payload, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"[export_msr] {args.out}: MSR={payload['msr']} exam={payload['exam_msr']} dev={payload['dev_msr']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
