# -*- coding: utf-8 -*-
"""
validate_schema.py — schema 校验（W4a P1-1：让「55/55 过校验」一条命令可复现）

- schema_truth.json：55 条规范化 spec 必须全过（数据集域校验）；死 airfoil / 越界参数必须拒。
- schema_task.json ：55 条规范化 spec 必须全过（物理范围版，约束解码用）。

用法：python validate_schema.py    # 退出码 0 = 全过
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FEA = os.path.join(ROOT, 'FEM-Bench-Aero')
TASKS = os.path.join(HERE, 'tasks', 'tasks.jsonl')

try:
    import jsonschema
except ImportError:
    print('[FATAL] jsonschema 未安装（pip install jsonschema）')
    sys.exit(3)

def main():
    tasks = [json.loads(ln) for ln in open(TASKS, encoding='utf-8') if ln.strip()]
    l1 = [t for t in tasks if t['input_level'] == 'L1']
    results = {}
    for schema_name in ('schema_truth.json', 'schema_task.json'):
        schema = json.load(open(os.path.join(FEA, schema_name), encoding='utf-8'))
        ok, fails = 0, []
        for t in l1:
            try:
                jsonschema.validate(t['input']['spec_normalized'], schema)
                ok += 1
            except jsonschema.ValidationError as e:
                fails.append((t['task_id'], e.message[:80]))
        results[schema_name] = (ok, fails)
        print(f'{schema_name}: {ok}/{len(l1)}')
        for f in fails[:5]:
            print('  FAIL', f[0], f[1])

    # 反向探针（truth 版）：死 airfoil / 越界参数必须拒
    schema = json.load(open(os.path.join(FEA, 'schema_truth.json'), encoding='utf-8'))
    bad1 = json.loads(json.dumps(l1[0]['input']['spec_normalized']))
    probes_ok = 0
    if bad1['structure']['family'] != 'wingbox':
        bad1['airfoil'] = {'code': '4412', 'chord': 1000.0}
        try:
            jsonschema.validate(bad1, schema); print('反向探针1(死airfoil): 未拒 — BAD'); probes_ok -= 1
        except jsonschema.ValidationError:
            print('反向探针1(死airfoil): 拒 ✅'); probes_ok += 1
    bad2 = json.loads(json.dumps(next(t for t in l1 if t['family'] == 'wingbox')['input']['spec_normalized']))
    bad2['airfoil']['sweep_deg'] = 55.0
    try:
        jsonschema.validate(bad2, schema); print('反向探针2(越界55°): 未拒 — BAD'); probes_ok -= 1
    except jsonschema.ValidationError:
        print('反向探针2(越界55°): 拒 ✅'); probes_ok += 1

    all_ok = all(ok == len(l1) for ok, _ in results.values()) and probes_ok == 2
    print(f"\n{'ALL OK' if all_ok else 'FAILED'}")
    return 0 if all_ok else 2

if __name__ == '__main__':
    sys.exit(main())
