# 外部复现预演记录（external_repro_0_dryrun）

> 日期：2026-11-09 22:45–23:10 · 执行者：蜗子（作者侧）
> 目的：在老王换机器之前，**先在本机扮演一次「外部人」**，把文档里的坑撞出来。
> 这不是 ROADMAP P0-3 的正式记录（那份要由老王的另一台机器产出，见
> `FEM-Bench-Aero/EXTERNAL_REPRO_CARD.md` §5），而是它的**前置预演**。
> 结论：**A 阶段 57 秒可跑出 headline，但 QUICKSTART §4 的候选集参数是错的**（已修）。

## 1. 怎么模拟「外部人」

本机有 venv、有 ccx、有历史缓存 —— 直接用本机环境测等于没测。四个隔离措施：

| 隔离 | 做法 | 目的 |
|---|---|---|
| 代码 | `git clone` 到 `/tmp/ext_repro/repo`（**全新目录、从远端拉**） | 排除「未入库文件被当依赖」 |
| 运行时 | `python -m venv --without-pip` 空 venv（实测 numpy/gmsh/scipy **全 absent**） | 验证「A 阶段只需标准库」这个断言 |
| 数据 | 只给 tar.gz 包，走 `fetch_data.py` 正常解包 | 验证包本身完整 |
| 路径 | 用相对路径 / Git Bash 风格，不碰项目里的 `PY=` 硬编码 | 排除本机 venv 路径依赖 |

clone 后的 HEAD = `1a4c640`（含当天全部提交）。

## 2. 实测结果

| 步骤 | 命令 | 耗时 | 结果 |
|---|---|---|---|
| A1 clone | `git clone …` | **49 s** | rc=0，325 MB 工作区，155 MB `.git` |
| A2 venv | `python -m venv --without-pip` | **1 s** | Python 3.13.14，无第三方包 |
| A3 解包 | `fetch_data.py --src …v1.1…` | **5 s** | SHA256 通过、64 条（manifest 期望 64） |
| A4 判分（**旧参数**） | `--candidates candidates_l3_v6c_glm_p2` | 1 s | `EXAM 23/25 (92.0%)` / `DEV 22/30` ⇒ **与仓库差 1 条** |
| A4 判分（**正确参数**） | `--candidates candidates_l3_v7sysfix_glm` | 1 s | `EXAM 23/25 (92.0%)` / `DEV 23/30` ⇒ **与仓库一致** |
| A5 逐字段比对 | 自写 walk 比对 | <1 s | **6 处差异，全部预期内**（5 处 MSR + 1 处 label） |
| B 证据自检（无 node 依赖） | `check_claims.py --public --brief` | 7 s | 首跑 3 项红 → 第二次 **2 项红**（S-39/S-43） |
| B 证据自检（`npm install` 后） | 同上 | +6 s | **all_ok=True，0 红** |
| **到 A 阶段结束总计** | | **≈ 57 s** | headline 复现成功 |

对照：错误候选跑出 **29 处** leaf 差异，正确候选 **6 处**。这个 29 → 6 的对比就是「参数错」与
「参数对」的可判区别 —— 光看 EXAM 那行看不出来（两个候选的 EXAM 都是 23/25）。

## 3. 撞到的四个坑

### 坑 1（真 bug）：QUICKSTART §4 的候选集参数写错

- **现象**：按文档跑，`EXAM 23/25 (92.0%)` **完全正确**，但 `DEV 22/30`（仓库是 23/30）、
  `first_pass_valid` 3 vs 4。文档却声称「共同字段应当逐字段相同」。
- **根因**：仓库 `baseline_scorecard_L3_v6c_p2.json` 的 `provenance.candidates_dir` 是
  **`candidates_l3_v7sysfix_glm`**（v2f 代候选），而 §4 写的是 `candidates_l3_v6c_glm_p2`
  （更早一代）。**headline 数字恰好相同，把错误掩盖了。**
- **教训（可复用问句）**：**当两个输入给出同一个 headline 时，headline 就不能用来判「输入对不对」** ——
  必须比对 provenance 或做逐字段 diff。文件名里的 `_p2` 也不可信（同名字段不保证同源）。
- **修法**：§4 改用 `candidates_l3_v7sysfix_glm` + `--label l3_v6c_p2_sysfix`；并补了 A5
  逐字段自证片段与「应当恰好 6 处差异」的判据。

### 坑 2：`check_claims --public` 首跑比第二次多红一项

- **现象**：首跑 `semantic fails 3`，第二次起 `2`（装 node 后 `0`）。
- **根因**：语义项会读「上一轮 JSON」，首跑时那份 JSON 是 clone 带来的旧 artifact。
- **状态**：**已知行为**（记忆里记过「首跑红重跑绿」），但 QUICKSTART 没写 ⇒ 外部人会以为是自己环境坏。
  已写进 §6 表。

### 坑 3：数据包条数 ≠ 卷条数

- **现象**：包解出 **64 条**，但 v6c 卷只有 **55 条**任务 ⇒ 容易以为「包和卷不匹配」。
- **实测**：v1.0 = 55 条、v1.1 = 64 条，差集**恰好是** `interpolation_v11` 的 9 个案例名；
  共同 55 条的 `spec.json`/`truth.json`/`model.inp` **逐字节相同（差异 0）** ⇒「v1.1 是超集」成立。
- **连带**：README 里「v1.1 的 9 条内插案例尚未进数据包」是**过时**的，已改。

### 坑 4：Windows 上 `/tmp/x.json` 在两个程序里指的不是同一个文件

- **现象**：`score_baseline.py --report /tmp/x.json` 打印写入成功（Git Bash 把它转成
  `C:\Users\…\Temp\x.json`），紧接着用 python 读 `/tmp/x.json` 却 `FileNotFoundError`
  （python 找 `C:\tmp\x.json`）。
- **修法**：统一用相对路径 `--report my_c032.json`。已写进 QUICKSTART §4 末尾与 §6 表。

## 4. 这次预演证明不了什么（局限，必须说清）

1. **同一台机器、同一套系统** ⇒ 证明不了跨 OS / 跨 CPU 架构可复现（Windows 之外的路径、行尾、
   编码问题都没覆盖）。
2. **ccx 在本机装着** ⇒ C 阶段（求解）没做隔离验证；新机器若没装 CalculiX，MSR 跑不了，但
   A 阶段不受影响。
3. **网络是本人的**（VPN 已开）⇒ clone 49 s 不代表他人网络。慢的话按先前的规矩：**开着 VPN 等，
   不换镜像站**（换镜像就破坏了 sha256 与匿名可复现性）。
4. **我自己写的文档我自己读** ⇒ 理解偏差测不出来。这正是 P0-3 需要真人的原因。

## 5. 复现本文的命令

```bash
rm -rf /tmp/ext_repro && mkdir -p /tmp/ext_repro && cd /tmp/ext_repro
git clone https://github.com/midknightwang-beep/FEM-Bench-Aero.git repo
python -m venv --without-pip cleanenv
PY=/tmp/ext_repro/cleanenv/Scripts/python.exe            # Linux/macOS: cleanenv/bin/python
cd repo/feagpt_repro
"$PY" fetch_data.py --src <DATA>/FEM-Bench-Aero-v1.1-data.tar.gz
"$PY" score_baseline.py --candidates candidates_l3_v7sysfix_glm \
  --tasks reports/papers/tasks_v6c.jsonl \
  --trivial reports/trivial_baselines_L3_v6c.json \
  --report my_c032.json --label l3_v6c_p2_sysfix
"$PY" check_claims.py --public --brief                    # 连跑两次
```
