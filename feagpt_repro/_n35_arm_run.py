# -*- coding: utf-8 -*-
"""_n35_arm_run.py — 以指定判分口径跑 `score_l2.py`（N-35 零回归实测用，不改生产代码）

用途：L2 v7 卷的 64 条全是 ec=1（必缺字段），判分走 clarify 分支、**不进** `spec_fidelity`
⇒ 「键拆分」对它是结构性零影响。但「结构性」是推理，必须实测：同一批候选、
同一份卷，分别在 `old`（拆前）与 `new`（拆后）口径下判一次，逐题比类别。

为什么用 wrapper 而不是改 `score_l2.py`：生产代码里加分支 = 给「测试」开洞，
下次有人忘了删就是永久双口径。wrapper 只在进程内 monkeypatch，退出即消失。

用法：
    "$PY" _n35_arm_run.py old --cand candidates_l2_v7sysfix_glm --tasks tasks/tasks.jsonl --out $TEMP/l2_old.json
    "$PY" _n35_arm_run.py new --cand candidates_l2_v7sysfix_glm --tasks tasks/tasks.jsonl --out $TEMP/l2_new.json
退出码同 `score_l2.py`。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import evaluate as E                                        # noqa: E402

if len(sys.argv) < 2 or sys.argv[1] not in ('old', 'new'):
    print('用法：_n35_arm_run.py {old|new} [score_l2 的参数...]')
    sys.exit(2)

arm = sys.argv[1]
META = set(E.DATASET_META_KEYS['extra'])
if arm == 'old':
    # 复刻拆分前的行为：7 键回到 EXEC_CONFIG_KEYS['extra']（只在 L3 豁免）
    E.DATASET_META_KEYS.clear()
    E.EXEC_CONFIG_KEYS['extra'] = META
# new：出厂状态即拍板 B，不动

import score_l2                                            # noqa: E402

sys.exit(score_l2.main(sys.argv[2:]))
