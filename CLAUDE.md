# CLAUDE.md

在执行本仓库任何任务前，必须先读并遵守根目录的 `AGENTS.md`（执行规约）。

最小要求：

1. 先跑 `python check_claims.py` + `python negative_controls.py`；非全绿（当前 check_claims 27/49/44、负控 50/50）不开始。
2. 先填 `AGENTS.md` §3 的 `TASK_CONTRACT`；一个任务只改一个变量。
3. 官方数字必须有 `feagpt_repro/reports/` 的 artifact + 命令；禁止引用 `eval_runs/`。
4. 分母必须显式闭合；不同 paper/prompt/model/分母不得直接相减。
5. 发现不一致：停下来写 `CONFLICT.md`，不要静默改 claim 或 artifact。
