# 外部复现执行卡（EXTERNAL_REPRO_CARD）

> 用途：在**另一台干净机器**上验证「这个仓库在没有作者帮助的情况下能不能跑出 headline」。
> 走完 A 阶段就算成功；B/C 是可选加练。
> 本卡上的所有耗时都是 **2026-11-09 在本机做的预演实测**（见
> `feagpt_repro/reports/diagnostics/external_repro_0_dryrun.md`），不是估计值。
> 跑完请把结果填进 §5 的表格，落到 `feagpt_repro/reports/diagnostics/external_repro_1.md`。

## 0. 你需要准备（3 件）

| # | 东西 | 说明 |
|---|---|---|
| 1 | 网络（能到 github.com） | clone 要下 **约 150 MB**（仓库 155 MB / 工作区 325 MB）。本机实测 **49 s** |
| 2 | 数据包 `FEM-Bench-Aero-v1.1-data.tar.gz`（100.2 MiB） | 已在 Release；也可从 `_handoff/release/` 直接拷。**sha256 必须等于** `8b6295d16f8505bca80971432c205e819d3e466c2a19a26407c08e2d76af0a4e` |
| 3 | Python 3.10+ | 预演用的是 **3.13.14 空 venv（零第三方包）**，A 阶段不需要 numpy/gmsh |

## A 阶段 —— 复现 headline（必做，本机实测 **≈ 1 分钟**）

### A1. clone（实测 49 s）

```bash
mkdir -p ~/ext_repro && cd ~/ext_repro
git clone https://github.com/midknightwang-beep/FEM-Bench-Aero.git repo
cd repo
git log --oneline -1        # 记下这一行，填进 §5
```

> 不要用「Download ZIP」：不带 `.git`，本项目证据是 sha256 锚定的。

### A2. 空 venv（实测 1 s）

```bash
python -m venv --without-pip .venv
# Linux/macOS
PY=.venv/bin/python
# Windows Git Bash
PY=.venv/Scripts/python.exe
"$PY" --version
```

**不要** `pip install`。A 阶段跑的是纯标准库路径 —— 这正是要被验证的断言之一。

### A3. 解数据包（实测 5 s）

```bash
cd feagpt_repro
"$PY" fetch_data.py --src <你放 tar.gz 的绝对路径>/FEM-Bench-Aero-v1.1-data.tar.gz
```

**预期（逐字）**：
```
[OK] SHA256 校验通过: 8b6295d16f8505bc…
modeling 目录条数: 64（manifest 期望 64）
[OK] 数据集本体就绪：…/repo/FEM-Bench-Aero/modeling（64 条）—— evaluate.py 可用
```

> 解出来的目录是 `repo/FEM-Bench-Aero/modeling`，**不是** `repo/feagpt_repro/modeling`。
> 条数不是 64 就停下，见 §4 的坑 3。

### A4. 复现 headline（实测 1 s）

```bash
"$PY" score_baseline.py \
  --candidates candidates_l3_v7sysfix_glm \
  --tasks      reports/papers/tasks_v6c.jsonl \
  --trivial    reports/trivial_baselines_L3_v6c.json \
  --report     my_c032.json \
  --label      l3_v6c_p2_sysfix
```

**预期（逐字，两行都要对）**：
```
  EXAM  TSR 23/25 (92.0%)  SFR 20/22 (90.9%)   underpowered=False
  DEV   TSR 23/30 (76.7%)  SFR 22/29 (75.9%)  (不进对外)
```

> **★ 候选集必须是 `candidates_l3_v7sysfix_glm`，不是 `candidates_l3_v6c_glm_p2`。**
> 后者跑出来 EXAM 也是 23/25（所以看不出错），但 **DEV 是 22/30**，与仓库成绩单差一条。
> 仓库 `baseline_scorecard_L3_v6c_p2.json` 的 `provenance.candidates_dir` 写的就是 `v7sysfix_glm`。
> `--label` 照抄 `l3_v6c_p2_sysfix` 才能逐字段相同（不传只差这一格）。

### A5. 逐字段自证（实测 < 1 s，可选但强烈建议）

```bash
"$PY" - <<'EOF'
import json
new = json.load(open('my_c032.json', encoding='utf-8'))
old = json.load(open('reports/baseline_scorecard_L3_v6c_p2.json', encoding='utf-8'))
def walk(a, b, p='', d=None):
    d = [] if d is None else d
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a: d.append((p+'/'+k, 'missing', b[k]))
            elif k not in b: d.append((p+'/'+k, a[k], 'missing'))
            else: walk(a[k], b[k], p+'/'+k, d)
    elif a != b: d.append((p, a, b))
    return d
diff = walk(new, old)
print('leaf 差异:', len(diff))
for x in diff: print('  ', x[0], '| new=', str(x[1])[:40], '| old=', str(x[2])[:40])
EOF
```

**预期：6 处差异，全部是「本该如此」**：

| 差异 | 为什么正常 |
|---|---|
| `/exam/msr`、`/dev/msr`、`/msr`、`/msr_pct`、`/msr_section` | MSR 要跑 C 阶段才有（`score_baseline` 只算 TSR/SFR） |
| `/provenance/label` | 只有 `--label` 没照抄时才出现 |

**出现任何其他差异 = 没复现成功**，别继续，按 §5 记下来。

## B 阶段 —— 证据自检（可选，实测 7 s + npm 6 s）

```bash
cd ~/ext_repro/repo/feagpt_repro
"$PY" check_claims.py --public --brief        # 连跑两次，看第二次
```

**没装 Node 依赖时**：第二次开始稳定为
```
[brief] check_claims 37 claims / 85 artifacts / all_ok=False (structural fails 0, semantic fails 2)
```
红的 2 项是 `S-39`/`S-43`，它们要 `node --print-prompt-sha`，而它依赖 `node_modules/ajv`。
**这不是你环境的问题**，装上就好：

```bash
npm install --no-audit --no-fund     # 实测 6 s，只装 package-lock 锁定的依赖
"$PY" check_claims.py --public --brief
```

**装完的预期（逐字，本机实测）**：
```
[brief] check_claims 37 claims / 85 artifacts / all_ok=True (structural fails 0, semantic fails 0)
```

> **★ 首跑会多红一项**（semantic fails 3），第二次才回到 2 —— 这是「读上一轮 JSON」的已知行为。
> 见到 3 不要慌，再跑一次。

## C 阶段 —— 跑一次真求解（可选，需要 CalculiX）

没有 `ccx` 就跳过，A 阶段已经证明核心主张。

```bash
export FEAGPT_CCX=/path/to/ccx
"$PY" msr_l3.py --candidates candidates_l3_v7sysfix_glm \
  --tasks reports/papers/tasks_v6c.jsonl --report my_c032.json \
  --only L3_open_hole_panel_400x200_d40
```

预期 `rc=0` 且印 `MSR = 1/1 (100.0%)`。**`--report` 必须指向 A4 生成的那个文件**（它是读入—合并—写回，不是新建）。

## 4. 已经替你撞过的四个坑

| # | 坑 | 现象 | 正确做法 |
|---|---|---|---|
| 1 | **候选集参数写错**（QUICKSTART 旧版 §4 的 bug） | EXAM 对得上 23/25，但 DEV 22/30 与仓库差 1 条，`first_pass_valid` 3 vs 4 | 用 `candidates_l3_v7sysfix_glm`，见 A4 |
| 2 | **`check_claims --public` 首跑多红一项** | 第一次 3 项红、第二次 2 项 | 连跑两次，以第二次为准 |
| 3 | **v1.1 包与卷的条数** | 数据包 64 条，但 v6c 卷只有 55 条任务 | 正常：v1.1 = v1.0 + 9 条内插案例，共同 55 条**逐字节相同**（已实测） |
| 4 | **Windows 上 `/tmp/...` 在两种程序里语义不同** | Git Bash 会把 `/tmp/x.json` 转成 `C:\Users\…\Temp\x.json` 传给程序，但 python 自己读 `/tmp/x.json` 会找 `C:\tmp\x.json` | 统一用**相对路径**（`--report my_c032.json`）或全用 Windows 路径 |

## 5. 结果记录（跑完填这张表，落 `diagnostics/external_repro_1.md`）

| 步骤 | 你的实测 | 本机预演 | 卡点（一句话） |
|---|---|---|---|
| 环境（OS / Python / 有无 ccx） | | Windows 11 / 3.13.14 空 venv / 有 | |
| A1 clone | | 49 s / 325 MB | |
| A2 venv | | 1 s | |
| A3 解包 | | 5 s / 64 条 | |
| A4 headline | | 1 s，`23/25 (92.0%)` | |
| A5 逐字段比对 | | 6 处差异，全部预期内 | |
| B 证据自检 | | 7 s（+ npm 6 s）→ 装依赖后 **all_ok=True 0 红** | |
| C 单条求解 | | 未做（本机预演略） | |
| **总计到 A 阶段结束** | | **≈ 57 s** | |

另外四句话，比表格更有用：

1. **哪一步你没看懂？**（原文照抄那句看不懂的话）
2. **哪一步你以为自己错了、其实没错？**
3. **有没有哪句话是真的错的？**（像 §4 坑 1 那种）
4. **如果让你给同事跑，你会删掉哪一步？**
