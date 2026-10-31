# T-D2 报告：数据包下载地址（GitHub Release）

> 收口时间：2026-10-31 21:0x
> 结论：**D 段唯一硬阻断已解除**。第三方 `git clone` + 下载 + 校验 + `fetch_data.py` 全链在**匿名（无凭据）**条件下实测通过。
> 产物：<https://github.com/midknightwang-beep/FEM-Bench-Aero/releases/tag/data-v1.0-v1.1>

---

## 1. 为什么传两个包（而不是只传手里的那个）

老王给的归档在 `F:\FEA_Archive_20261024`，只有一个 `FEM-Bench-Aero-v1.0-data.tar.gz`（55 条）。
若直接传它，会留下一个**永久性错配**：

| 事实 | 实测值 |
|---|---|
| 归档包 `manifest.json` | `n_cases = 55` |
| **仓库** `FEM-Bench-Aero/manifest.json` | `n_cases = 64` |
| 磁盘 `FEM-Bench-Aero/modeling/` | **64 条目录，0 缺文件**，276 MB |
| `modeling/` 被 git 追踪 | **0 个**（`.gitignore` 排除，只能靠 Release） |
| 包内 55 条 vs 磁盘 64 条 | 包是**真子集**，磁盘多 9 条，反向 0 缺失 |

即：仓库的清单说 64、数据只有 55，第三方按 `DATA.md` 落地会撞上「不完整」警告（该警告本身是对的）。
补一个 v1.1 包的成本只是打一次包，而以后补要重走 Release + 文档 + 记忆三处 —— 所以老王拍板**两个都传**。

---

## 2. 验收（V1–V8，逐项实测）

| # | 项 | 结果 |
|---|---|---|
| V1 | 指纹 | v1.0 `8cec47ce…1dd3` == `DATA.md` 记录 == 包内 `SHA256SUMS.txt`，**逐字符一致** |
| V2 | 内容完整 | v1.1 解包后 **384/384 文件**与仓库磁盘 sha256 相同；`manifest.json`/`MANIFEST.md` 也相同；条目 451 = 1+1+65 目录+384 文件（闭合） |
| V3 | 超集关系 | 差集 = 9 条新增（1 barrel + 5 wingbox + 2 hole_panel + 1 stiffened）；`包有磁盘无 = 0` |
| V4 | 资产状态 | 3 个资产全部 `state=uploaded`（85.42 / 100.22 / 0.0002 MiB） |
| V5 | **匿名下载** | 不带 `Authorization` 头：v1.0 36.7s / v1.1 44.5s，sha256 **两个都 PASS** |
| V6 | 清单自洽 | 用**下载来的** `SHA256SUMS.txt` 跑 `sha256sum -c` → 两行 `OK`，**rc=0** |
| V7 | 按文档落地 | 干净 clone 里 `fetch_data.py` → `[OK] SHA256 校验通过`、`modeling 目录条数: 64（manifest 期望 64）`、**rc=0** |
| V8 | 闸 | 负控 **69/69**；claims **33 条 / 68 artifact / 61 语义项全过**（连跑两次 rc=0） |

### 2.1 V7 的完整输出（这是「照文档真能跑通」的唯一硬证据）

```
[OK] SHA256 校验通过: 8b6295d16f8505bc…
解包 … -> <clone>/FEM-Bench-Aero
modeling 目录条数: 64（manifest 期望 64）
[OK] 数据集本体就绪：…/modeling（64 条）—— evaluate.py 可用
rc=0
```

> 附带发现：`fetch_data.py:65` 有 `DeprecationWarning`（Python 3.14 起 `tarfile.extractall` 默认过滤）。
> **不影响 rc**，但升级 Python 后要加 `filter=` 参数，已记入 follow-up。

---

## 3. 顺手修掉的过期表述

`DATA.md` / `QUICKSTART.md` 里有一批「发布前 vs 发布后」的过期话，留着会让第三方**找错方向**：

| 文件 | 原话 | 改成 |
|---|---|---|
| `DATA.md` §2 | 「本仓库不含下载地址…也没有公开的发布页」 | Release 直链 + 双包对照表 |
| `DATA.md` §3.1 | 「`sha256sum -c` 一定会失败，要手工比对」 | 裸文件名清单，`-c` 直接通过（v1.0 包内那份仍提一句） |
| `DATA.md` §6.1 | 「仓库里**没有** `.gitattributes`…不存在单一配置能全绿」 | 已修（T-D3），clone 后 1550/1550 一致 |
| `QUICKSTART.md` §1 | 「本仓库**没有公开远端**」 | 直接 `git clone` |
| `QUICKSTART.md` §6 | 「没有公开远端地址 / 数据包没有公开下载地址 / 仓库无 `.gitattributes`」 | 三条划掉并标「已发布 / 已修」 |

`SHA256SUMS.txt` 的老毛病（记打包机绝对路径 ⇒ `-c` 必失败）在 **Release 层**用裸文件名修掉，没有改动 v1.0 包本身（它的指纹已被历史引用，不能重打）。

---

## 4. 四个坑（都值得记）

### ★★★ 差点直接传 v1.0 —— 「手里的包」不等于「该发的包」
第一反应是「校验通过就传」。实测才发现仓库 `manifest.json` 已经 64 条、磁盘 64 条齐备，
而包是 55 条。**先测「包与仓库是否自洽」再决定发什么**，不是先发再补。

### ★★ 把「网络慢」当成「GitHub 限制」
首次匿名下载 3 分 23 秒只拿到 2 MB，看着像被限速。实际是代理未生效（`http_proxy` 没设）。
老王开 VPN 后同一 URL **1.49 MiB/s**，两个包 81 秒下完。
⇒ **下载慢先查通道，别先归因到对端**。

### ★★★ 我在 §6.1 里编了一行「`S-49`/`S-50` 因缺 `modeling/` 红」
写文档时顺手把「数据不在仓库里 ⇒ 数据相关判据红」当成因果写上去了。实际去干净 clone 里跑，
**只红 3 项**：`S-39` / `S-43`（缺 `node_modules`，`node --print-prompt-sha` 无输出）、`S-61`（hook 不入库）。
而 `S-49` / `S-50` 判的是「正文计数 vs artifact」和「对外数字表」，**跟 `modeling/` 毫无关系**。
已删掉那一行，按实测改成 3 项。
⇒ **同族于「R63 不写死可推导数」：写文档时不许凭结构推断判据行为。**

### ★★ 看板分母漏计了 D2 自己
D 段原记 **84% = 4.2/5**，可那 5 项是「D1 + D3 + D5 + D4 + 离线 bundle」—— **D2 不在里面**，
而同一格正文却写「唯一为 0 的是 D2」。D2 一完成，5.2/5 就超过 100%，矛盾立刻暴露。
本轮补正为 **6 项：5.2/6 ≈ 87%**（合计 43% → 44%）。
⇒ **比率对不上时先核分母，这是第三次了**（MEMORY「并列的比率先核分母」）。

---

## 5. follow-up（不在本任务范围）

| 项 | 说明 |
|---|---|
| **F-2** | `package-lock.json` 被 `.gitignore` 忽略 ⇒ 依赖树不可复现（D4 最后缺口） |
| **F-5** | `latest_scorecard()` 按 `mtime` 选对象 ⇒ clone 后选择退化（`ROADMAP` §13 第 3 位） |
| `fetch_data` 的 `DeprecationWarning` | Python 3.14 起 `extractall` 默认过滤，需加 `filter=` |
| 离线 bundle 未验 | `_handoff/FEM-Bench-Aero_3059d90.bundle` 存在但未在干净环境实测 clone |

---

## 6. 复现命令

```bash
# 1) 匿名下载（不带头）
BASE=https://github.com/midknightwang-beep/FEM-Bench-Aero/releases/download/data-v1.0-v1.1
curl -L -O "$BASE/FEM-Bench-Aero-v1.1-data.tar.gz"
curl -L -O "$BASE/SHA256SUMS.txt"

# 2) 校验
sha256sum -c SHA256SUMS.txt          # 期望两行 OK、rc=0

# 3) 落地
cd feagpt_repro
"$PY" fetch_data.py --src <DATA_DIR>/FEM-Bench-Aero-v1.1-data.tar.gz

# 4) 包↔卷覆盖（不写死数字，现算）
"$PY" _c1_pack_gap.py --src <DATA_DIR>/FEM-Bench-Aero-v1.1-data.tar.gz \
                      --out reports/diagnostics/data_pack_volume_gap.json
```
