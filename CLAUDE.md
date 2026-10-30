# CLAUDE.md

在执行本仓库任何任务前，必须先读并遵守根目录的 `AGENTS.md`（执行规约）。

最小要求：

1. **先跑两道闸，都用项目 venv，顺序固定：负控 → `check_claims`（R59）**：
   `"C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe" negative_controls.py`，然后
   `… check_claims.py --json "$TEMP/check_claims_preflight.json"`。非全绿不开始（**具体条数以本次输出为准，本文件不写死**——写死必漂，见 R63/S-51）。**官方 `reports/check_claims.json` 只在收口时写一次**——否则 pre-flight 自身就会把工作区弄脏（记录的是 artifact `mtime`）。**解释器与顺序都照抄 `AGENTS.md` §0 的命令块，不要凭记忆写 `python`**（T-A12a：旧版本文件这里写裸 `python`，负控必然 `ModuleNotFoundError: numpy`）。
2. 先填 `AGENTS.md` §3 的 `TASK_CONTRACT`；一个任务只改一个变量。**收口顺序固定：负控 → check_claims（R59）。**
3. 官方数字必须有 `feagpt_repro/reports/` 的 artifact + 命令；禁止引用 `eval_runs/`。**dataset/求解类脚本必须用项目 venv**（`envs/default/Scripts/python.exe`；系统 python 缺 numpy/gmsh，R60）。
   **提交前闸（D5）**：`git commit` 会触发 `.git/hooks/pre-commit` 跑 `check_commit.py`，判据是「暂存区 == 工作区全部非白名单改动」——**它是唯一检查「提交内容」而不是「工作区」的闸**，堵 T-C1 那次「只 add 了新增文件、12 个改动漏掉」。**hook 不入库**，新 clone 后先跑 `check_commit.py --install-hook`，否则这道闸不存在。**这条现在有闸守**：`check_claims.py` 的 S-61（判据在 `hook_guard.py`）会查 hook 是否存在、是否指向当前脚本、是否被 `core.hooksPath` 改道；只跑复现的可 `--skip-hook-guard` 显式跳过（标 `skip`，须写明原因）。
4. 分母必须显式闭合；不同 paper/prompt/model/分母不得直接相减。
5. 发现不一致：停下来写 `CONFLICT.md`，不要静默改 claim 或 artifact。
