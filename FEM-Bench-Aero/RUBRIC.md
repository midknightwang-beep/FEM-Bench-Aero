# RUBRIC.md — L3 判分口径预注册（W4e/W4f → W5a，专家第四/五轮 R18）

> **版本**：v6.12（2026-11-01 **F-9 长期解「分发产物新鲜度闸」**）：**只新增一道闸，不改任何判分口径** —— 不改卷/候选/成绩/headline/分母，**对外数字零变动**。起因是 F-9 两次现场：两个分发产物（离线 bundle / 公开快照）**不进 git 历史**，所以「它过期了」不产生任何错误信号 —— 旧快照 `--check` 唯一的红项是「P4b 脱敏不可逆」，**读起来像数据/脱敏问题，实际原因是落后**；而 bundle 侧虽有 C9，却要先 clone 整个包（分钟级），没人会在每次收口时跑。新增 `_f9_artifact_freshness.py`（A0–A4）只做「**便宜地比 HEAD**」（不 clone、不 emit、不写文件）：`public_manifest.json.source_head` 与包内 `refs/heads/main` 各对一次仓库 HEAD，**谓词与 C9 同一条**（落后区间的改动必须全是 metadata，`is_metadata()` 直接 import、不另写一份 —— T-D3「规则只有一处」）。**允许落后、只许落后在 metadata 上**。★ **自指是设计的一部分**：`public_manifest.json` 自己也进公开集、记着 `source_head` ⇒ **记录它的那个提交**必然让它落后 1 ⇒ 恒为**黄**不是红（消掉这个黄的唯一办法是把 manifest 排除出公开集，那读快照的人就再也看不到产地了）。A3 另判「文件名里的 sha == 包内 main」——**改名不等于重打**。**七向自检** + **NC-71**（断言「原样 7/7；把 metadata 谓词改成恒 True / 恒 False 后自检**各须变红**」—— 只断言自检绿等于自证，恒真式同族 N-26）。**为什么不新增 R76**：本闸的口径**完全复用 C9 已有的谓词**，没有引入新纪律；加 R 编号会牵动 S-56 的规则范围断言与红线表升序，等于为一条不存在的口径扩一圈循环依赖（同 v6.11 的判断）。负控 70 → **71**。v6.11 见下。

> **版本**：v6.11（2026-11-01 **T-PSA 阶段 2 收口**）：**只改一条判据的实现口径** —— 不改判分口径、不改卷/候选/成绩/headline/分母，负控**仍 70 条**。**S-44(b) 从「主区间上界 == artifact 最大 NC 编号」改为「结构化清单段内逐条覆盖 + 区间不得虚报」**，两处根因各对应一次实测退化：① **拿「上界」当「最新一条」的代理，隐含要求 NC 编号连续** —— 实测编号一直跳号（`PC-1 + NC-1..67 + NC-15b`，**从无 NC-68/NC-69**；旧文里的「69/69」的 69 是**条数**不是「NC-69 这条」），本轮新增 NC-70 后该代理把「编号不连续」误报成「INDEX 漏报最新一条」，而 INDEX 本身是对的（已写 `NC-23..67 + NC-70`）；② **覆盖关系从含正文的整行提取** —— INDEX 该行在括号里逐条描述每条负控（`**NC-49 四向**`…`**NC-67 五向**`），整行扫会把「提及」当「点名」⇒ **覆盖永远成立**；实测把主区间上界 67→66 后 NC-67 仍靠正文提及判覆盖，**NC-49 的 N-2 向由「红」退化成「漏判」**（这一向是在改判据后的第一次全量负控里露出来的，不是读代码看出来的）。修正：覆盖只从 `C-0xx：` 之后、第一个 `（` 之前的**清单段**读；**找不到清单段判红**（不许回退到整行扫描，否则第二条根因原样复活）；反向新增「区间不得虚报」——区间声称 `NC-a..b` 存在的编号必须真在 artifact 里（防把区间写成 `NC-23..70` 抹平跳号这种编数）。**六向自检**：原样绿 / 漏报最新一条红 / 区间抹平跳号红 / 分子≠分母红 / 主区间上界减 1 红 / 清单段缺失红；**NC-49 恢复「正向过 + 三向全红」**；负控 **70/70**、`check_claims` **33/68/61 连跑两次全过**。**性质**：这是 **R58「只认结构化记号、不按自然语言判读」被自己违反后的回归**，**不新增 R 编号**（新增会把循环依赖扩大一圈）。v6.10 见下。

> **版本**：v6.10（2026-10-31 **T-F3「`--public` 显式豁免」**轮）：(1) 新增红线 **R75**（**放宽只能精确到原因，且不得自动生效**）—— 起因是 T-D4 实测公开快照里 `check_claims` 红 7 项，其中 4 项**由 D4 自己引入**（本机外部归档的 `SHA256SUMS.txt` 不在公开集 / INDEX 的 `PY=` 被渲染层脱敏成占位符 / `AGENTS.md`、`CLAUDE.md` 按拍板移出），加上 D5b 的 S-61（公开快照不分发 `.git/hooks`）共 5 项；(2) 这 5 项**不是代码错了，是公开集里没有对应对象**，故按拍板加 `check_claims.py --public`：豁免项标 `exempt` + `reason`、**不计入通过数**、且只在失败原因确实是公开集造成时才生效；(3) 判据在本轮新增的 `_f3_public_exempt_selftest.py` 里六向自检（含三向「本该红」）。**未改任何既有判据的检查逻辑，未改数字 / 口径 / 卷 / 成绩 / headline。**
> **版本**：v6.9（2026-10-30 **T-D5b「给『hook 是否已装』建判据」**轮）：(1) 新增红线 **R74**（**自监督的闸必须有不依赖自身的检查入口**）—— 起因是 T-D5 的 `check_commit.py` 靠 `.git/hooks/pre-commit` 触发，而 hook **不入库**（`.git/` 不被追踪）⇒ 新 clone / 换机 / 重建仓库后这道闸**静默消失、且没有任何东西报错**（R58 落在「触发器」上的形态：它不运行，所以没人报错）；(2) 新增 `hook_guard.py`（判据 H0–H4 + **八向自检**，每向断言「红的**是哪一条**」而非只断言「红了」）+ `check_claims` **S-61** 接线，并加 `--skip-hook-guard` 显式跳过开关（按 R69：跳过后标 `skip`、**语义项计数 61→60 不计入**、须在当次报告写明原因、不得进入对外数字）；(3) 判据用 `git rev-parse --git-path hooks` 取**生效** hooks 目录 —— **实测该命令会跟随 `core.hooksPath`**（设 `.husky` 即返回 `.husky`、设绝对路径即返回绝对路径）⇒ 既不写死 `.git/hooks`，也**不把「`hooksPath` 非空」一刀切判红**（把 hook 装进 `.husky` 并纳入版本控制是**更**好的做法，误红会把人逼去删一个合法配置）；(4) 可执行位判据**只在 POSIX 且 `core.filemode != false` 时判**，其余平台标 `not_run` 并写明「本向在此平台**未被验证**」（本机 Windows 实测即走此分支，`core.filemode=false`）。**★ 边界（本轮承诺）**：**不改 `check_commit.py` 的任何判据（G0–G6 一字未动）、不改任何判分口径 / 卷 / 候选 / 成绩 / headline / 分母、不重跑任何模型**；负控**仍 69 条**（本轮**不加 NC** —— 自检放在 `hook_guard.py --self-test`，从而不牵动 C-019 的 69 链与 S-44/NC-49 的循环依赖）；语义项 60→**61**；claim 33 / artifact 68（以 `check_claims` 实读为准，R63）。**★ 三条现场自纠（都是自检抓出来的，不是读代码看出来的）**：① 自检首版 **8 向「全绿」是假绿** —— 我定义了 `_mk_repo()` 却忘了在 `probe()` 里调用，`applicable=False` 使 8 向全部「红=无」；**通过/失败那一列看不出来**，是**明细行**里那句 `[not_applicable]` 把它抓出来的（同族：判据没跑起来与判据通过，外观完全一样）；② 判据原本打算写成「`core.hooksPath` 非空即红」，**实测后被推翻**（见上）；③ 验证「移走 hook 会红」时第一次 `grep | head -3` 把 S-61 那行截掉了，差点记成「没红」。v6.8 见下。
> **版本**：v6.8（2026-10-30 **T-C1「第三方可用性验收的收口：分发文档 + 前置闸实质化」**轮）：(1) 新增红线 **R73**（**前置闸必须查数据实体，不得只查容器存在**）—— 起因是 T-B1 在真 clone 里实测到 `mkdir modeling` 就能骗过只查 `isdir` 的闸，**静默产出 `exam 3/25 (12.0%)` 的假成绩单且无警告**；(2) `evaluate.require_dataset(fea, expect_ids=None)` 三级化：目录存在 → 里面有 `spec.json` → 覆盖任务卷，三处调用点（`score_baseline` / `msr_l3` / `r32_audit`）传期望集，缺失时报**条数 + 样例**；(3) 新增 **NC-67 五向**（缺失 / 空目录 / 有文件无 spec / 覆盖不全 / 正向不误报，且「没给」与「给错了」**原因必须不同**）；(4) 把散在三处的 `case_id` 转换链统一到 `case_id_of()`，用 `_c1_caseid_equiv.py` 对 **357 条 task_id** 逐条证等价（R67）；(5) 分发文档 **QUICKSTART.md**（5 分钟复现 headline，零第三方依赖、零 API key）+ **DATA.md**（数据获取 / 校验 / **包与卷版本匹配**）+ `_c1_pack_gap.py` 把「包↔卷」覆盖差集**落盘**（v1.0 包 55 条：v6c 卷缺 0、v7 卷缺 9 —— 不再手抄）。**★ 边界（本轮承诺）**：**不改任何判分口径、不重跑任何模型、不动任何已有分数** —— 重跑 C-032 后与入库 artifact **共同叶子改动 0**。**★ 同时更正 T-B1 报告里的一条自身错误**：D-7「环境类失败 `return 2` 没传到退出码」是**测量错误** —— 当时用 `… | tail -3; echo $?` 取到的是 `tail` 的退出码；不用管道实测 `rc=2` 正确，`sys.exit(main())` 一直是对的。负控 68→**69**（实读）；语义项**仍 60 条**（本轮不新增 S 类静态判据 —— 这条规则守的是**行为**，由 NC-67 的五个可执行方向守，见 R69「能判的不变量优于需要维护的名单」）；claim 33 / artifact 68（以 `check_claims` 实读为准，R63）。v6.7 见下。
> **版本**：v6.7（2026-10-30 **T-A14「L2 clarify 按族分层口径说明」**轮）：(1) 新增红线 **R72**（**分层结论必须有分层证据**：凡以「族/桶/子集层面的差异」为论据的结论，该层面的数字必须由 artifact 逐层落盘并可复算，不得只报合计、更不得手抄）；(2) 落盘：`score_l2.py` 三桶各增 `by_family`（每族 `n`/`passed`/`pct`，并按 `Σ族 == 总数` 硬断言，不闭合 rc=5）、`report_l2_clarify.py` 透传到 `by_model.<model>.<bucket>.by_family` 且逐块断言「`Σ族==n/passed`」与「每族 `inf + inv == all`」；(3) 新增 **S-60**（族级落盘 + 闭合 + 按族可加 + **两层不得同名换义**）+ **NC-66 六向**；(4) `l2_clarify_dual.md` 增「按族分层」表，并把原先把数字**写死在模板里**的那句 N-27 说明（15 条 / 16 条 / 36 条）改为**从数据现算** —— 模板里写死数字与手抄 claim 是同一种病，只是藏得更深。**★ 边界（本轮承诺）**：**不重跑任何模型、不改任何判据、不改任何分母** —— 族级数字本来就完全由已入库的 `per_task[].{family,pass,name_leak}` 决定；两份 `l2_scores_v7_*` 各 **+36 叶子（全为 `by_family`）+ `_note` 一处**、`l2_clarify_dual.json` **+75 叶子（3 个 `by_family_note` + 72 个族级）/删 0 / 改 0**；六个既有数字（`49/64`·`30/45`·`19/19`·`36/64`·`21/45`·`15/19`）**逐数未变**，且与既有手抄值**逐个对上**（含 `24/39`、`15/39`、非翼盒 `25/25` 与 `21/25`、泄漏 19 条里 16 条不在最差族）⇒ 这是**「数字对但没有 artifact」**，不是数字错。负控 67→**68**；语义项 59→**60**；claim / artifact 条数以 `check_claims` 实读为准（R63）。**★ 顺手更正上一轮的自身错位**：R71 行此前被插在 R70 之前（升序表被打破），本轮摆回 R70 → R71。v6.6 见下。
>
> **版本（历史）**：v6.6（2026-10-30 **T-P1a「over-clarify 政策预注册 + 判分元数据事实错误修正」**轮）：(1) 新增红线 **R71**（判分元数据只许修**事实错误**、修正必须留痕）；(2) **修掉一处事实错误**：`L3_naca4412_wingbox` 把翼盒族**正确**键 `n_stringers_per_skin` 登记成**错族**键 ⇒ ds 的「先问对 `n_ribs`、又多问一句 `n_stringers_per_skin`」被判 `clarify_wrong`，判分理由与事实相反。修法**不动卷文件**（`tasks.jsonl` 与 `papers/tasks_v7.jsonl` 同 sha，S-52 卷链「只许加行」）、改走**显式修正表** `tasks/clarify_wrong_keys_fix.json`（`from` 必须逐字等于卷现值，否则不应用），并把表记进成绩单 `provenance.judge_overrides`（路径+sha+`applied_to`）；(3) **over-clarify 政策预注册**：「命中 expected + 多问不必要的字段」**不判 FAIL**，但 `per_task.n_questions` 必须落盘、只作交互效率指标、不进任何分母 —— 依据是实测的两条：语义判 **4/4 假阳性**、条数判代价**单侧集中**（L2 glm 0 / ds 8）；(4) 新增 **S-59** + **NC-65 五向**。**★ 结果（bridge，post-hoc）**：ds legacy exam **22/25 (88.0%) → 23/25 (92.0%)**、exam_full **31/34 → 32/34**、2×2 由 `both 22 / only_glm 1` 变 **both 23 / only_glm 0 / only_ds 0 / neither 2**；**glm 一位数字未动**（23/25、32/34）；**MSR 两模型不变**（20/22、19/21，澄清题不进 R23 分母）；**L2 两份 `l2_scores_v7_*` 逐字节不变**。旧 artifact 留档 `reports/archive/baseline_scorecard_L3_v7_{glm,ds}__pre_p1a.json` 与 CI 同名副本（D10）。**★ 边界（不得含糊）**：**L2 全 64 条 `clarify_wrong_keys` 为 `null` ⇒「把字段全问一遍」在 L2 上仍是已知退化解，本轮未堵**，不得据此宣称 L2 抗退化；负控 66→**67**；语义项 / claim / artifact 条数以 `check_claims` 实读为准（R63）。★ 首版方案「三处统一改成 `n_stringers`」**被模拟当场证伪**（会把两条加筋板题判死 —— 它们的 expected 就是 `n_stringers`）⇒ 只有逐题精确改才成立。v6.5 见下。
>
> **版本（历史）**：v6.5（2026-10-30 **T-A13d「N-28 判据边界加固」**轮）：(1) 新增红线 **R70**（判据的字符串匹配必须有边界）—— `score_baseline.judge_clarify_field_level` 的两处裸子串（`hit_wrong` 与 `hit`）改走新的 `_alias_hit`：**ASCII 标识符按 token 边界**、**中文短语仍按子串**；(2) 新增 **S-58**（三层：`_alias_hit` 有 `re.escape`+两侧边界+ASCII/非 ASCII 分流 / 判分函数体零裸子串且两处都调用 / 行为两向不得失效）+ **NC-64 六向**；(3) **N-28 定性更正**：它不是新发现，`_audit_clarify_meta.py`（W5c-6d）早已记下**假红**那一侧，T-A13c 补的是**假通过**那一侧 —— 同一函数的两端。**★ 边界（本轮承诺的证据）**：104 条 clarify 文本 × **三路判据**（旧逻辑逐字副本 / 真新逻辑组合 / 真实调用点）**0 变化**；四份成绩单 **L2 661+660 叶子 / L3 2098+2137 叶子逐叶子零差异且无 allow 项** ⇒ **没有任何对外数字变动**（C-032 / C-040 / C-041 一个数没动）；中文别名 21 个**零变化**（P7/P8 探针守）。**★ 同一处改动是双向的**：它同时修假红（会让数字**上升**）—— 所以契约里「只会变严」的说法当场被 P6 推翻并更正，正因如此必须先有构造性零差异才能动。负控 65→**66**；语义项 57→**58**；v6.4 见下。
>
> **版本（历史）**：v6.4（2026-10-30 **T-A13c「L2 clarify 第二模型 ds」**轮）：(1) 同一卷、同一 L2 prompt（sha `03129c56…`）、同一呈现（不遮 name）下补跑 **`deepseek-v4-pro`**，64/64；`clarify_all` **36/64 = 56.2%** ／ `clarify_informative` **21/45 = 46.7%** ／ `invalid` **15/19**；(2) `report_l2_clarify.py --scores` 支持**多模型并列**（`by_model` 块，第一个为顶层 primary；顶层字段仍向后兼容），S-53 增 **（e）逐块断言**：每个模型块自己都要 `all == informative + invalid`、都要两侧报分、顶层必须就是其中一块且逐数相等；新增 **NC-63 五向**；(3) **N-27 取 (a) 拍板落地**：只如实标注、不动口径 —— 且 ds 给了**独立反证**：同一批泄漏 19 条里 ds 掉 4 条（15/19），掉的 4 条全是「直接给 spec」或「问别的字段」（根本没走追问路径） ⇒ **「泄漏 ⇒ 那 19 条必然全对」被证伪**，glm 的 19/19 是能力 + 族构成；(4) 新增 **N-28**：`judge_clarify_field_level` 用**裸子串** `a in text`，而 L2 无 aliases ⇒ `n_stringers` 会被 `n_stringers_per_skin` 命中、`thickness` 会被 `skin_thickness`/`rib_thickness`/`stringer_thickness` 命中、`width` 会被 `stringer_flange_width` 命中 ⇒ **问错了具体哪个厚度也可能判对**。**本轮实测两模型 0 条触发**（PASS 的 49 + 36 条全部含独立键名命中，因为写的是 `structure.params.n_stringers`）⇒ **数字不假**；但这是潜伏通道，加固排为独立单子（跑前冻结 + 零差异 + 负控），**不在跑后改判据**（R-A2）。**★ 边界**：**判据一行未改**、L3 侧零改动（`SYS`/`score_baseline`/`msr_l3` 未触碰），C-032/C-040 的数字一个没动；**两模型不得据此排名**（R54）；L2 与 L3 不是同一指标，不得并列。负控 64→**65**；语义项 / claim / artifact 条数以 `check_claims` 实读为准（R63）。v6.3 见下。
>
> **版本（历史）**：v6.3（2026-10-30 **T-A13b「L2 clarify 首次跑分」**轮）：(1) L2 澄清层**第一次真的跑模型**（`candidates_l2_v7_glm`，`glm-5.3-flash`，64/64，L2 专用 prompt sha `03129c56…`），`clarify_all` **49/64 = 76.6%** ／ `clarify_informative` **30/45 = 66.7%** ／ `invalid` **19/19**，新增 **C-041**（supporting，不作 headline）；(2) `status` 升 `scored`，S-53 的「两侧都必须有整数 `passed`」**已自动生效**；(3) 新增 **N-27** 并写进 R66 的适用边界：**双口径的差主要是族构成差，不是泄漏净效应** —— 15 条失败全在翼盒（24/39），非翼盒三族全对（13/13、7/7、5/5），而泄漏 19 条里 16 条属这三族 ⇒ `clarify_informative` **不得**当「L2 真信号」单独引用。**★ 边界**：**没改任何判据**（L2 仍是「字面命中键名」，L2 无 `clarify_aliases`，属 R19 的选择）；**没遮 `name`**（冒烟显示遮与不遮判类逐条相同）；L3 侧零改动（`SYS`/`score_baseline`/`msr_l3` 未触碰），C-032/C-040 的数字一个没动。负控仍 **64**；语义项 / claim / artifact 条数以 `check_claims` 实读为准（R63）。v6.2 见下。
>
> **版本（历史）**：v6.2（2026-10-30 **T-A13a「L2 clarify 首次可跑的链路」**轮）：(1) `gen_candidates_v2.js` 增 `SYS_L2 = SYS + 追加段` —— **`SYS` 一字节未动**（L3 prompt sha 仍 `ce225186…`，C-032/C-040 的可比性锚点不受影响），L2 专用 prompt sha = `03129c56…`；(2) 新增 `--mask-name`（把 `spec.name` 换成 `case_<8位>`；N-17 的 19 条泄漏源就是 name 本身），呈现方式落进候选的 `presentation` 字段，事后可分辨这批是遮了还是没遮；(3) 新增 `score_l2.py`：判据 **import 自** `score_baseline.judge_clarify_field_level`、掩码 **import 自** `check_l2_leak.scan`（每个判据只有一处实现，不复制）；(4) `report_l2_clarify.py` 增 `--scores`，**候选不齐 64/64 一律保持 `not_run` + `partial`**，不冒充 `scored`；(5) 新增 **NC-62 五向**。**★ 边界（不含糊）**：本轮**只搭链路、没跑任何模型** —— L2 仍 `status=not_run`、`passed=null`，C-038 的双口径数字一个没动；**L2 的判据仍是「字面命中键名」**（L2 无 `clarify_aliases`），这是 R19 的选择，不是漏配；L3 侧零改动（`SYS` / `score_baseline` / `msr_l3` 均未触碰）。负控 63→**64**；语义项 / claim / artifact 条数以 `check_claims` 实读为准（R63）。v6.1 见下。
>
> **版本（历史）**：v6.1（2026-10-30 **T-A12a/T-A12b「协议去硬编码 + 审计闭合 + R32 两 scope 分口径」**轮）：(1) 新增 **R69**（放宽类判据必须有边界：任何「允许例外」的闸，必须同时写明**哪里仍必须为 0**、**例外必须带 reason**、**例外不得进入对外数字**）；(2) 新增 **S-56**（协议不得硬编码 rubric 版本/规则范围/解释器/当前卷，一律只写指针）+ **NC-59 六向**；(3) 新增 **S-57**（R32 的 exam/all 两 scope 口径可分且不过期）+ **NC-60 五向**；(4) S-54 扩三条：exam_full **任务级总账必须独立复算**（N-26）、`exam_full_msr_excl_solver` 必须存在（R52）、`n_unresolved` 同名不同义必须有说明；**NC-61 四向**；(5) `r32_audit.py --scope all` 口径改为「exam 违规必须 0；dev 违规允许但须带 reason 且不得对外」，并给 artifact 带 `paper_sha256`（防过期 artifact 冒充当前结论）。**★ 边界**：本轮**没有重跑任何模型**，两份 v7 成绩单的 TSR/SFR/MSR **逐数未变**（`--reuse` 重算统计段 + `_regress_scorecard` 逐叶子：2090/2129 叶子只有 audit 那几条声明变更）；**分母口径一个数字都没动**。负控 60→**63**；语义项 / claim / artifact 条数以 `check_claims` 实读为准（R63）。v6.0 见下。
>
> **版本（历史）**：v6.0（2026-10-29 **T-A11b「v7 candidates 全量两模型 + 判失败必须落原因」**轮）：(1) v7 成绩单落地（C-040，两模型 64/64，**supporting 不作 headline**，R48），**双分母都报** —— legacy exam 25 与 exam_full 34 并列、**禁相减**（R54）；(2) 新增 **R68**（判失败必须能说出为什么：原因必须落盘且可审计、兜底不得是空串、建闸前先看那个字段在真实 artifact 里是否非空、历史 artifact 不回填但须承认跨版本不可比）；(3) 新增 **S-54**（v7 双分母成绩单的结构性闸：四桶闭合 / msr 三桶加和 == counted / `exam_full_msr` 分母 == closure / 判 FAIL 必有 `failure_detail` / env 不得留在分母 / solver 诊断不含锁冲突）+ **NC-58 五向**；(4) `bootstrap_ci.py` 补 `exam_full` 的 CI（此前两口径并列而一个有 CI 一个没有，不对称）；(5) `msr_l3.py` 增 `--only` / `--force`：**环境注入的批量删除保护在单次调用累计 50 次删除处拒绝 `unlink()`**，而每条任务释放求解锁就是一次删除 ⇒ 一次跑 59 条必然在 ~第 53 条处把锁删不掉、后续全被锁挡住（N-22），分批是**环境约束**不是偏好。**★ 边界**：`env` 原先留在分母里（N-23，代码印着「不进分母」却没做），本轮按 R16 修到分母上；L2 clarify 双口径仍 `status=not_run`。负控 59→**60/60**；语义项 / claim / artifact 条数以本次 `check_claims` 实读为准（R63）。v5.9 见下。
>
> **版本（历史）**：v5.9（2026-10-29 **T-A11a「exam 双分母口径实现 + 零差异回归」**轮，把 C-037 的双分母落到**判分层**）：v7 的 9 条 `interpolation_v11` 若沿用原谓词 `exam_stratum 非空`，会**同时**在两个方向错 —— exam **25→34**（与 C-032 换分母，R53/R54 禁止并列与相减）、dev **30→39**（那 9 条折进 dev，「dev 只作开发诊断」被污染）。改为**四桶互斥穷尽**：`exam(legacy 25) + exam_v11(9) + dev(30) == 64`，`exam_full = exam + exam_v11 = 34`；`exam` 这个键**仍是 legacy** ⇒ C-032 继续可比。新增 **R67**（改了判分必须证明老数不动：同参数重跑 + 逐**叶子**比 + 三类差异分别记账 + 工具自身可证伪）/ **NC-57 五向**；新增 **C-039**（1607 个既有叶子 0 变动、CI 64 叶子 0 变动）。**★ 边界（不含糊）**：`exam_full` 目前**没有 bootstrap CI**、**S-54（四桶闭合闸）尚未加** —— 现在没有 v7 成绩单可读，加了就是空转（R29），待 T-A11b 落地后再加。负控 58→**59/59**；语义项 / claim / artifact 条数以本次 `check_claims` 实读为准（R63）。v5.8 见下。
>
> **版本**：v5.8（2026-10-28 **T-A10c「L2 clarify 无效子集双口径」**轮，来自 CONFLICT **N-17**，老王拍板 **C'**：L2 的 clarify 判据在 **19/64 条**上**无效** —— `spec.name` 把被省略的值写在自己身上（`name=open_hole_panel_400x200_d30` 而省略 `hole_d`），模型读 name 就知道、不必问；此时判「clarify 失败」是**判据的错**，不是模型的错（M7 同源）。新增 **R66**：**判据在某个子集上无效时，必须隔离 + 双报** —— 不得改题掩盖（会连历史一起废掉、且与 R65 冻结冲突）、不得继续算进单一对外数字；两个分母不同 ⇒ 一并适用 **R54**（禁止相减/排名）。新增 **S-53**（两块必须在 + 闭合 `all−inf==invalid` + **掩码与现算一致**防过期 + `delta_allowed is False` + `status=scored` 时两侧都必须有整数 `passed`）/ **NC-56 四向**（缺一块 / 掩码过期 / 允许相减 / 只报一侧分，四向各自成为唯一失败项）；新增 **C-038**（`clarify_all n=64` ／ `clarify_informative n=45` ／ invalid 19，`status=not_run` 如实）；**★ 顺带更正一条错判**：上一版 `CONFLICT N-17` 写「C-032 的 clarify 被这 19 条污染」——**错**，C-032 的 `n_clarify_tasks=4` 是 **L3 的 4 条**、L3 prompt 只发 `input.nl`（task_id 不进 prompt）⇒ **不污染任何已发布数字**，是 L2 轨道的潜伏缺陷。负控 57→**58/58**、语义 53→**54**、claim 29→**30**、artifact 58→**60**。v5.7 见下。
>
> **版本**：v5.7（2026-10-28 **T-A10b「v7 考卷冻结 + 任务层漂移入闸」**轮，来自 CONFLICT **N-16/N-18/N-19**：新增 **R65**：**任务层的冻结件不得漂移** —— 同一轮里踩了两次「看起来是确定性轮换、实际依赖位置」：`make_tasks.py` 用 `rotate_idx=stats['L1']`（全局累计数）轮换 L2 省略字段 ⇒ 数据集 55→64 时**48/55 条 L2 题目被静默改写**；`make_nl_human.py` 用 `STYLE_CYCLE[i % 3]`（族内序号）轮换笔调 ⇒ **37/55 条 NL 题面被改写**。两次都没有任何闸能发现（S-48/S-49 只比计数、`verify_dataset` 只数目录、`r32_audit` 只查题面可解性）⇒ R58 的正面形态：**没有工具读的东西等于没校验**。新增 **S-52**（当前卷==磁盘 / 已发布 NL 行未改写 / 跨版只许加行）/ **NC-55 三向**（且三向各自成为唯一失败项，否则「跨版只许加行」会一次吃掉另两条变异使它们长期假绿）；新增 **C-037**（v7 考卷冻结，卷层 claim，**exam_legacy 25 / exam_full 34 双分母** = N-15 老王拍板 A）；同轮修 **N-19** 判分口径（v1.1 的 4 个数据集记账键`split_tag`/`v11_*` 原被当判分字段 ⇒ 9 条题必然全 FAIL，已并入 `EXEC_CONFIG_KEYS['extra']`）；负控 56→**57/57**、语义 52→**53**、claim 28→**29**、artifact 54→**58**。v5.6 见下。
>
> v5.6（2026-10-28 **T-A10「闸覆盖补全 + 对外表入闸」**轮，来自 CONFLICT N-12 与第十三轮复评 §3.2/§3.3/§3.4，新增 **R63**：**文档里不得写死可推导的计数**——claims/artifacts/semantic/负控四个数就是两个闸脚本自己的输出，抄进 `AGENTS.md`/`CLAUDE.md` 等于制造第二数据源，而第二数据源**必然**漂（N-1/N-2/N-10/N-12 与 `manifest.xval_cases_available` 停在 55 全是这个形态）⇒ 正解不是加闸核对副本，而是**不产生副本**；新增 **R64**：**对外数字表必须有分母口径且内容必须等于生成器的当前输出**（`external_numbers.md` 是对外唯一数字源，此前无人读：忘重跑 ⇒ 陈旧、手改 ⇒ 假数、「spec 64」与「算例 128」被混用 ⇒ 三套都是「sha 绿但内容错」）。新增 **S-49**（C-001/2/4/5/036 的正文计数 == artifact 实读）/ **S-50**（对外表分母合法性 + 逐字节重生成比对 + source_artifacts 可追溯）/ **S-51**（协议文件不得写死计数）/ **NC-54 十向**（且每向断言「红的原因对」）；新增 **C-036**（v1.1 数据层，数据侧 claim）；负控 55→**56/56**、语义 49→**52**、claim 27→**28**、artifact 50→**54**。v5.5 见下。
>
> v5.5（2026-10-28 **T-A9「claim 计数入闸」**轮，来自 CONFLICT N-10，新增 **R62**：**claim 正文里的计数必须等于 artifact 里的计数**——`sha256` 只能证明「文件没被换」，不能证明「文件里写的数是对的」；`grep "gate3\|C-003" check_claims.py` 曾是 **0 命中**，于是 C-003 的三个计数从 55 条时代的 `34/15/6` 漂到 64 条时代的 `39/18/7`，期间每次收口都是绿的。新增 **S-48**（三个计数逐项相等 + 加和闭合 + field 构成闭合 + 「不说 N/N」分母对齐，**解析不出来一律判红、不得 skip**）/ **NC-53 四向**（field−1 / scalar−2 / d36+1 / 删分母），负控 54→**55/55**、语义 48→**49**。
> v5.4（2026-10-27 **T-A5「求解串行硬约束」**轮，新增 **R61**：`feagpt/solver.py` 的 `run()` 必须经过全局求解锁 `.solve.lock`——**并行跑 ccx/abaqus 会静默空转、返回码仍 0**，所以把「并行」做成不可能，而不是靠纪律；锁超 1 h 视为崩溃残留自动接管。新增 **S-47**（机制在场 + 无残留锁）/ **NC-52 两向**，负控 53→**54/54**、语义 47→**48**。同轮修掉 `check_forms.py` 的 `DEFAULT_REFERENCE` 陈旧路径（原先指向仓库里不存在的 `outputs_str/…` ⇒ T5 恒 FAIL、整份 check_forms VERDICT: FAIL）。v5.3 见下：
> v4.7（2026-10-25 W5c-6c 跨模型对比轮，新增红线 **R47–R49**（分母显式 / 不得事后择优 / 双尺度分裂必须标出）+ **§7.6**（含「跨模型对比作为归因工具」的判读表）；S-33/S-34/S-35 三条语义检查守住；`score_baseline.py` 修字段级命中率**静默排除编造题**的 bug（分母改显式分流 + `verdict_split` 自动落盘）。v4.6 见下：
> v4.6（2026-10-25 W5c-6b，新增红线 **R42–R46** 治理闸（headline 唯一 / 投影不冒充实测 / value_added 双尺度 / MSR 字段齐全 / key 决策留痕）+ **§7.5**；S-29/S-30/S-31 三条语义检查守住前三项；`value_added` 增字段级尺度与 T1+ 地板。v4.5 见下：v4.5（2026-10-25，W5c 新增红线 **R33–R41** + **§7.1 契约登记表** / **§7.2 死字段**（blade 剖面无缘条宽）/ **§7.3 数值角色**（R41）/ **§7.4 契约试建闸边界**（gold 也过闸）+ §1.1.1 改为 A/B/C/D 四类归因；R32 语义收口为「4 类 + 2 处局限」；三栏 exam 见 §1.1；变更记录见文末）。
> **纪律（R18）**：本文件冻结后，跑基线期间不得再改；每次改动必须新开版本号 + 记录原因。
> **post-hoc 声明**：W4d 版口径（EXEC_CONFIG_KEYS / METADATA_KEY_NAMES / bc_skip）是看过
> 30 条候选后调整的，属 **post-hoc**——其成绩（C-020，已 superseded）只能作开发参考；
> v2 口径冻结于 v4 重跑前（C-021）；v3 口径冻结于 v5 考卷重生成（W5b）之前。

## 1. 层次（红线 R15）

| 集合 | 定义 | 条数 | 用途 |
|---|---|---:|---|
| **exam（C-021 口径，v4 考卷 / 30 条 L3）** | `boundary_holdout + extrapolation_test` | **11**（boundary 4 + extrap 7） | **历史上唯一对外 headline**（C-021 = TSR 5/11）；**n=11 underpowered** |
| **exam（v6 的 boundary+extrap，55 条 L3 全量）** | `exam_stratum ∈ {boundary, extrapolation}` | **19**（boundary 6 + extrap 13） | **只报不判**（n=19 < 20，不满足 R12/R24） |
| **exam（v6 headline）** | `exam_stratum ∈ {boundary, extrapolation, interpolation}` | **25**（6 + 13 + 6） | **W5b 起的对外 headline**（见 §1.1；R12 分母 = 25） |
| dev | `train + val`（内插留出后） | 30 | 开发/诊断，不进对外 |

> **三个数不许混**（R30）：C-021 = **11**、v6 boundary+extrap = **19**、v6 headline 合并 = **25**。
> 任何「提升/下降」的对比必须同栏同口径；跨栏只能写「口径变了，不可直接比」。

### 1.1 三栏 exam（v6 预注册，2026-10-25 老王拍板）

- **为什么分三栏**：`interpolation_test`（训练包络内的点）明显比 boundary/extrap **更容易**，
  合并报会虚高；但只报 boundary+extrap 又永远只有 **19 条 < 20**，无法满足 R12/R24 的功效门槛
  （6 + 13 = 19 是数据集固定值，不随内插条数变化）⇒ 两者互斥，必须显式取舍。
- **拍板结论**：headline = **合并 25 条**（6 boundary + 13 extrapolation + 6 interpolation），
  **三栏明细必须并列给出**，并在任何对外引用处写明「与 C-021 的 **11 条**口径不可直接比较」（R30）。
- **R12/R24 的分母 = 合并 25**；分栏各自 n 太小（6/13/6）只报不判。
- `exam_stratum` 字段由 `make_nl_human.py --interp-quota` 写入考卷；`score_baseline.py`
  的 `is_exam` 判据 = `split_v2 ∈ exam_splits 或 exam_stratum 非空`（**向后兼容**：
  v4/v5 考卷没有该字段 ⇒ 行为与旧版完全一致，C-021 仍可复现）。
- 内插留出名额（**v6b 定案：全给翼盒 6 条**，`--interp-quota "wingbox:6"`），从 `train` 按 `task_id`
  字典序取前 N 条（**确定性选择，可复现**）。
- **为什么从「按族 2/2/1/1」改成「全翼盒 6」**（v6 → v6b，实测驱动）：
  ① L3 的 train 分布是 wingbox 15 / open_hole 2 / barrel 1 / panel 1，按 2/2/1/1 抽会把
     **barrel、open_hole、panel 三族的 train 抽空**（1→0、2→0、1→0）⇒ train 池只剩翼盒 13 条；
  ② 后果不是「dev 变小」而是**地板算不出来**：`trivial_baselines` 的 T0 众数池缺 3 族、
     T1 检索库只剩翼盒 ⇒ **T1 地板只有 1/4 族可算**，value_added 的对照项失真（T1 记 0 会让任何成绩都"有增量"）；
  ③ 而且 train 只有 1 条的族抽出来当「内插」**本身无意义**——1 个点没有包络可内插。
  ⇒ 改为全翼盒后：train 池 = 9/2/1/1、**4/4 族地板可算**；代价是 exam 族构成更偏翼盒（18/4/2/1）。
  v6 原始稿留档 `papers/tasks_v6.jsonl`，采用版 `papers/tasks_v6b.jsonl`（D10：改划分必须留档旧基线）。

#### 1.1.1 v6b 实测结果（W5b-4，C-028）：三栏**分栏差距巨大**，合并报确实会虚高

| 栏 | n | TSR | CI95（B=4000） | 读法 |
|---|---:|---|---|---|
| boundary | 6 | **5/6 (83.3%)** | [50.0, 100.0] | 分栏 n 小，只报不判（R12） |
| extrapolation | 13 | **7/13 (53.8%)** | [23.1, 76.9] | 最难的一栏，唯一低于合并值 |
| interpolation | 6 | **5/6 (83.3%)** | [50.0, 100.0] | 训练包络内，明显更容易 |
| **合并 headline** | **25** | **17/25 (68.0%)** | **[48.0, 84.0]** | n≥20 ⇒ `underpowered=False`，可判 |

- **实证了 §1.1 的担心**：若只报 boundary+extrap（19 条）会是 12/19 (63.2%)，加内插 6 条后升到 68.0%
  —— 内插确实把合并值抬了 **+4.8pp**。因此三栏并列不是形式要求，是独立信息。
- **★ 难度方向性偏差（必须在任何对外引用处声明）**：v6b 题面相对 v4 做了系统性消歧
  （**26/55 新增「坐标系」约定、25/55 新增显式载荷方向 `[x,y,z]`**，题面均长 161 → 206 字）。
  这是 W5b-3a 为通过语义完备性检查（NC-20/R21）而加的正确改动，但客观上降低了难度
  ⇒ **禁止把 68.0% 与 C-021 的 45.5% 相减表述为「提升」**（R30）。
- **★ 68.0% 是含已知缺陷的下界**（W5b-4 探针 + W5c-0 `r32_audit.py` 实证），8 条 exam 失败**须按四类分开归因，
  不能笼统说「没有一条是模型能力不足」**：

  | 类 | 条数 | 失败字段 | 性质 | W5c 处置 |
  |---|---:|---|---|---|
  | A 契约/键名 | 4（`open_hole_panel` 全族） | `params.hole_d`（4/4）+ `hole_x/hole_y`（2）+ `layup`（1）+ `material.ply_material` 自创键（1）+ `extra.end_tension` 自创键（2） | **harness 侧**：SYS prompt 从未列开孔板键名 | R34 键名表 + 禁用键（NC-31） |
  | B 题面缺依据（R32） | 2 exam / 4 全卷 | `airfoil.stringer_flange_width`（`str3_T`）、`airfoil.web_chordwise`（`web1_offcentre`；dev 的 `web1`/`web2` 同因） | **卷子侧**：gold 有值、题面无依据 | v6c 补题面（C-030），`r32_audit` 4 → 0 |
  | C 模型侧 | 1（`web1_offcentre`） | `extra.end_torque` / `extra.torque_axis_dof` 自创键 | **模型侧**：自创键（键名即契约，R19） | 只靠 R34 明示允许键收窄，不豁免 |
  | D 收敛性 | 1（`str3`） | 3 轮未收敛 | **生成器侧**（孤例） | 记录 `turns_histogram`/`n_unresolved`，不改判据 |

  A/C 在同一题上**有重叠**（`web1_offcentre` 既有 B 也有 C），所以「8 条里 6 条是系统性缺陷」的说法要精确到字段，
  不能按题计。诊断明细 `feagpt_repro/reports/diagnostics/w5b4_defect_analysis_v6b.md`（R37：官方文档不再引 `eval_runs/`）。

## 2. TSR（主 KPI，行为正确性）

- 完备题：`spec_fidelity` PASS ⇒ TSR PASS。
- 澄清题（`expected_clarifications` 非空）：
  - **字段级判据（R17）**：候选 clarify 文本必须命中 `clarify_aliases[field]` 中至少一个别名
    （正确键名或语义短语），**且不含** `clarify_wrong_keys` 中任何错族键名（键名即契约 R19）。
  - 单字关键词（'肋'/'孔'/'框'/'长桁'）**不得**作为通过依据（W4d 版已废弃）。
  - 静默编造 spec ⇒ TSR FAIL（FPR 编造）。
- 3 轮未收敛 / LLM 错误 ⇒ FAIL。

## 3. SFR（字段保真）

- 判层：**工程层**（L3 only）——`GRADED_FIELDS[family]` + material 必判三项 + mesh/load/extra
  gold 权威逐键。
- **R20**：`fabricated`（澄清题静默编造）⇒ SFR 一律 FAIL，与 TSR 编造口径一致。
- 执行配置键 `EXEC_CONFIG_KEYS`（REPORTED NOT GATED，填错单独报告）：
  - `mesh`: algorithm_2d, element_order, leading_edge_threshold, min_jacobian,
    recombination_algorithm, recombine, refine_at_leading_edge
  - `analysis`: incremental, initial_increment, outputs, step_type, total_time
  - `extra`: sweep_index, shear_axis, moment_axis（数据集内部编码键）
  - `load.direction` 且 `kind=pressure`（内压径向为数据集内部约定）
- **死字段豁免**：wingbox 且候选 `n_stringers_per_skin=0/缺` 时 `stringer_*` 四键不判。
- **builder-default 声明（R19）**：barrel 的 `stringer_height=25/stringer_thickness=2.5`、
  panel 的 `20/2.5` 为 builder dataclass 默认，gold params 不含这些键 ⇒ SFR 不判；
  考卷 v4 已在 NL 明示尺寸，模型显式写对/省略均可，**写 0 ⇒ builder 校验拒（真实错误）**。
- **bc 块**：pipeline 不消费 `spec.bc`（边界由各族 builder 代码决定），非翼盒族 gold bc 是
  死模板值 ⇒ bc 键值不判；但 **bc 自创键照罚**（模型写出 builder 不认识的键 = 编造）。
- **自创键白名单（收紧后）**：仅 `note / units / unit_system / description / *_units / *_note`；
  `type / element(s) / order / application / point` 等一律照罚（W4d 版白名单过宽，已收）。
- **material 块自创键**（ply_material 等）照罚。

## 4. MSR（全链可用率，R14/R16）

- 全链 = 契约闸（含 FEASpec 试建）+ ccx 求解 + 关1 网格 + 关4 语义 + fidelity + spec_fidelity。
- **依赖预检（R16）**：gmsh/numpy 缺失 ⇒ 环境错误退出，绝不记候选 FAIL。
- **分母（R23，v3 修订）**：按**任务属性**排除——`expected_clarifications` 非空的澄清题与
  无 spec 产出的未收敛候选一律不计分母，**无论澄清题是否被模型静默编造出 spec**
  （编造已由 FPR 单独计数，双重计数违反 R23）。v2 文字「编造被拒候选不计」按此执行。
- 失败分层 `env / contract / model / solver`；env 单独计数，不进 MSR。
- 汇总：`exam.msr` / `dev.msr` / `by_split` 落盘成绩单（P1-1/P1-2，不再手算；NC-22 检查）。
- **★ solver 单列（R35，v4.5 修）**：solver/算力失败（OOM、超本机内存阈值）**记 `compute_bound`，
  不计模型能力失败**，但**只许单列、不许静默删除**。成绩单必须给齐四行 ——
  `exam_msr` / `exam_msr_excl_solver` / `dev_msr` / `dev_msr_excl_solver`，加全链
  `msr` / `msr_excl_solver`，并标 `solver_in_exam` / `solver_in_dev` 归属。
  **原始口径（含 solver）与剔除口径必须并列**：求解失败对模型确实是失败，剔掉是「能力上限口径」，
  只留一个都会被误读。
  **★ 且 solver 桶是「候选相关」的，不是题目固有属性**：同一题 `barrel_d2000_l2000_str12_frm4`
  在 v6b 旧候选 4.2 s 就被 pipeline 拒（`class=model`），换 v6c 新候选后算到 169,606 节点才撞
  158,548 阈值（`class=solver`）。⇒ **「剔除 solver 后的分母/得分」同样不可跨版本直减**
  （R30/R39 的不可比判定一并适用于剔除口径）。
  *（v4.5 之前的实现缺陷：`msr_l3.py` 注释写「exam MSR 不含 solver」而代码里 `exam_msr` **含**
  solver —— 属于「注释与实现口径相反」，数字本身没错，但会让复核者按注释读出错误结论。）*
- 解释器：`C:/Users/22207/.workbuddy/binaries/python/envs/default/Scripts/python.exe`（gmsh 在 venv）。

## 5. value_added

- `exam` TSR_LLM − `exam` TSR_T1（同任务集 exam 口径，**不用 all_pct**）。
- `n_exam < 20` ⇒ `underpowered=true`，**不得判 PASS**（R12/R24）。

## 6. 负控

- 每次改判分/考卷必跑负控套件（R5/R6）；未全绿不得跑基线。
- 套件 = **56 条（当前）**：`PC-1` + `NC-1..22`（W4d 15 / W4e NC-15..19 / W5a NC-20 载荷方向完备、
  NC-21 MSR 分母、NC-22 exam.msr）+ **`NC-15b`**（澄清双向探针，W4e）+ **`NC-23..26`**
  （W5a' artifact 入库 / git 追踪 / 官方·诊断分文件 / **NC-26 缺 gold 数据集必须硬报错**）
  + **`NC-27..29`**（W5b-3：**NC-27** 文本计数漂移必须被语义检查抓到、**NC-28** 候选未覆盖全卷必须标记、**NC-29** 跨口径混比必须拒绝）。
- **计数口径（P1-2/P1-3 修正）**：旧文写「PC-1 + NC-1..22」= 23 是**漏计 NC-15b** 的错账；
  实际为 24（W5a 时）／28（W5a' 收口）／**31**（W5b-3：再补 NC-27..29）／**39**（W5c：再补 NC-30..37）／**41**（W5c-6b：再补 **NC-38** headline 唯一反向、**NC-39** T1+ 地板反向）／**44**（W5c-6c：再补 **NC-40** 分母不闭合、**NC-41** 第二模型抢 headline、**NC-42** 双尺度分裂被隐藏）／**51**（T-A3：NC-49 四向）／**53**（T-A4：NC-50/51 各两向）／**54**（T-A5：NC-52 两向）／**55**（T-A9：**NC-53 四向**——C-003 计数漂移 / field 构成不闭合 / 分母丢失，都必须被 R62/S-48 拒）／**56**（T-A10：**NC-54 十向**——C-001 规模漂移 / C-002 minJ 写错 / C-004 通过数−1 / C-005 删 dup 锚点 / 删整行 C-036 / 对外表分母混写 55 / 删「分母口径」列 / 手改一格数字 / 协议写死三元组 / 协议写死负控数，都必须被 R63/R64 + S-49/S-50/S-51 拒 **且原因命中**）／**57**（T-A10b：**NC-55 三向**——当前卷与磁盘不一致 / 已发布 NL 行被改写 / 跨版改老行，都必须被 R65/S-52 拒，且**三向各自成为唯一失败项**：否则「跨版只许加行」会一次吃掉另两条变异、／**58**（T-A10c：**NC-56 四向**——L2 双口径缺 `clarify_informative` 块 / informative 掩码过期 / `delta_allowed=True` / `status=scored` 但只一侧报分，都必须被 R66/S-53 拒，且**四向各自成为唯一失败项**：否则「缺一块」会一次吃掉后三条、使它们长期假绿）／**59**（T-A11a：**NC-57 五向**——`_regress_scorecard.py` 自比须 PASS / 改值须报 CHANGED / 删键须报 REMOVED / 越界新增须报 ADDED·越界 / `--allow-changed` 只给前缀不得放行；**新判据工具的第一条纪律是先证明自己不误报**，否则它只是个会印 PASS 的印章）。**报负控必须报总数 + 编号集合**，只报「全绿」不算。／**60**（T-A11b：**NC-58 五向**——S-54 闸自身必须能被证伪：正向不误报 / 四桶不闭合须红 / 手改 `exam_full_msr` 分母须红 / 判 FAIL 无 `failure_detail` 须红（N-21）/ env 塞回分母须红（R16），每向断言**红的原因对**）／**63**（T-A12a/T-A12b：**NC-59 六向**——S-56 协议 SOT 闸必须能被证伪（版本 / 范围 / CLAIMS 标题 / 裸解释器 / 当前卷名，每向断言**红的原因对**）；**NC-60 五向**——S-57 R32 两 scope 口径闸（exam 有违规 / all 混 exam 违规 / dev 无 reason / artifact sha 过期）；**NC-61 四向**——S-54 新增三断言（总账退回 counted 的 N-26 / 缺 excl_solver 的 R52 / 缺同名说明）／**64**（T-A13a：**NC-62 五向**——L2 首次跑分器 `score_l2.py` 必须能被证伪：正向 64/45/19 闭合且全过 / 只写中文不写键名须红 / 澄清题给 spec 须红（R20）/ 删一个候选后 `missing` **必须仍进分母**且 `partial`（R-A5）/ 两个分母的**通过数**也须闭合。**★ 一个从没跑过的打分器，最可能的失败形态不是算错，而是「什么都算成通过」或「把没跑的题排除掉」**／**65**（T-A13c：**NC-63 五向**——L2 多模型并列时**每一块自己**都要能证伪：正向（两模型并列且各自闭合）须**绿**（防判据过严）/ 某块 `scored` 但一侧 `passed` 缺失须红（原因须含「只报有利一侧」）/ 某块 `all != inf + inv` 须红（R-A5 逐块）/ 顶层 `model` 不在 `by_model` 里须红（「不同源」）/ 顶层 `passed` 与对应块不等须红（「不一致」）。**★ S-53 原本只断顶层，而顶层天然只有一个模型** ⇒ 这三种形态它一个都发现不了；**★ 闸的边界**：`by_model` 只能保证「在场的块各自自洽」，守不了「该在场的模型缺席」—— 后者靠 claim 文本点名）／**66**（T-A13d：**NC-64 六向**——澄清判据的**字符串匹配边界**必须能被证伪：假通过通道已关（省略 `n_stringers`、文本只写 `n_stringers_per_skin` 须 FAIL，**且原因必须是「未命中」**）/ 两向不过严（`structure.params.n_stringers`、`n_stringers（根数）` 须 PASS）/ **假红已修**（`wrong_keys=[`n_stringers`]` 时写 `n_stringers_per_skin` 须 PASS 且无 `wrong_keys_hit`）/ 中文别名零变化（`翼肋数量` 须 PASS）/ `thickness` 通道已关（只写 `rib_thickness` 须 FAIL）。**★ 同一条通道双向** ⇒「改完只会变严」是错的；**★ 这一条是旧账**（`_audit_clarify_meta.py` W5c-6d 已记假红侧），不是新发现）
- 产物：`reports/negative_controls_66.json`（入库，R25；`_65`/`_64`/`_63`/`_62`/`_61`/`_60`/`_59`/`_58`/`_57`/`_56`/`_55`/`_54`/`_53`/`_51`/`_50`/`_49`/`_48`/`_47`/`_44`/`_41`/`_39`/`_37`/`_31` 已移入 `reports/archive/`，根目录只留最新那份）；`negative_controls.py` 读最新成绩单，
  缺成绩单时相关条目显式记 `skip` 而不是静默消失（W5a 教训：NC-15 曾因澄清题迁移而无声消失）。
- **NC-19 判据已随 v6b 三栏同步（W5b-4）**：原判据「exam 集的 split_v2 必须 ∈ 留出集」
  在 v6b 下**假红**——内插题按设计就是从 `train` 留出的（`split_v2` 仍 `train`、
  `exam_stratum='interpolation'`，见 §1.1）。新不变式：exam 行要么 split 属留出集，
  要么（`split=train` 且 `stratum=interpolation`，**记账为「内插豁免 N」**）；其余组合一律 BAD。
  **核心「不得混入未留出的 train」未放宽**，并已做反向验证（伪造一条 `split=train, stratum=None`
  的 exam 行 ⇒ NC-19 立即 BAD）。
- **NC-19 再随双分母同步（T-A11b / N-24）**：v7 起不变式②改用 **`exam_full`** 而不是 legacy `is_exam` ——
  v11 那 9 条 `is_exam=False` 却**属于** exam_full、`split_v2` 是留出，用 legacy 判会一次假红 9 条（本轮实际撞到）。
  同时加一条 v11 专用不变式：**进了 exam_full 的 v11 行必须是留出**（否则＝dev 混进考卷），
  并把「v11 的 `split_v2` 与 `stratum` 不同名」的条数**计数进 actual**（实测 9/9），条数一变就会被看见 —— 不写死常数（R63）。

## 7. 任务构建期检查（R21 + R32，W5b-4 扩充）

- L3 任务 NL 必须给**坐标系约定 + 载荷方向**（向量或明确轴向文字），禁止「法向」类未定义裸词。
- `tasks.jsonl` 每条 L3 行带 `coordinate_convention` 字段；NC-20 构建期检查。
- **★ R32（W5b-4 新增）：gold 的每个判分字段都必须能从 NL 推出。**
  对 `GRADED_FIELDS[family]` 中在 gold 有非空值的字段，NL 必须给出依据，**或**该字段显式登记为
  「按族默认值」（进默认值表 / `EXEC_CONFIG_KEYS`）。否则该任务是**不可解题**，不得进 exam。
  - 实证来源：`airfoil.stringer_flange_width` 在 gold 有值，题面只写「blade 长桁（高 20 mm、厚 2.5 mm）」，
    模型按系统提示「用户没给的尺寸不得编造」正确省略 ⇒ 被判 `spec_fail`。这不是模型错，是**卷子错**。
  - R21 只覆盖了「载荷方向完备」（NC-20），**未覆盖本类**；R32 是它的补集。
  - **已脚本化（W5c-0）**：`r32_audit.py` 逐 family 遍历 `GRADED_FIELDS` + `mesh/load/bc/analysis/extra`，
    对每个判分字段给出 `derivable_nl` / `derivable_contract`（题面没写但契约唯一确定：材料卡、词汇表、族默认）/
    `exempt:{dead|exec_config|default|clarify|bc_skip}` / **VIOLATION**。有 1 条 VIOLATION ⇒ 不得冻结考卷（**R33**）。
    局限（写在脚本 docstring 里）：数值判据是「题面出现过该数（含单位换算）」，**必要不充分**，是筛查器不是证明器。
  - **实测（W5b-4 卷）**：v6b 上 4 处 VIOLATION —— `str3_T` 缺缘条宽 + **3 条 web 任务题面完全没提中间腹板**
    （旧 `make_nl_human` 从 `structure.params` 取 `n_web/web_pos`，而 gold 的腹板在 `airfoil.web_chordwise`，
    params 是空的 ⇒ 永远取不到）。v6c 修复后 **0 违规**（1812 个判分字段全部分类）。

### 7.1 契约登记表（题面不写也算可推的四种情形，W5c-1）

| 类别 | 内容 | 判据 |
|---|---|---|
| 材料卡 | `Aluminium 2024-T3` ⇒ E=73100 MPa / ν=0.33 / ρ=2.78e-9 / 屈服 345 | 题面只写「铝 2024-T3」即可 |
| 词汇表 | 面内拉伸（端部均布）/ 翼尖集中力 ⇒ `load.kind="tip_force"`；内压/均压 ⇒ `"pressure"`；翼型 `code="4412"`（不是 "NACA4412"）；bc ⇒ `{"root_surface":"root","clamp":true}` | SYS prompt「词汇约定」段 + NC-31 咬键名 |
| 族默认 | 无锥度 ⇒ `tip_chord_ratio=1.0`；无后掠 ⇒ `sweep_deg=0`；无中间腹板 ⇒ `web_chordwise=[]`；无长桁 ⇒ `n_stringers(_per_skin)=0` | 题面无触发词 |
| 执行配置 | `EXEC_CONFIG_KEYS`（网格算法/分析步/内部编码轴向） = REPORTED NOT GATED | 只报不判 |

### 7.2 死字段（W5c 新增一条）

- 无长桁（`n_stringers_per_skin=0`）时的 `stringer_*`：模板默认值，不可知 ⇒ 不判（沿用 W4d）。
- **`blade` 剖面的 `stringer_flange_width`：不判。** 依据不是"模型没写就放过"，而是物理 + 代码：
  `feagpt/sections.py::tee` 在 `flange_width<=0` 时**直接返回 `blade()`**，`geometry.py` 对 blade 只挤出单条竖板，
  flange 完全不参与建模；`check_forms` T5 反向证明 `blade ≡ T(flange=0)`；gold 34 条翼盒该值**全部是模板默认 30.0**。
  判定用 **gold 的 `stringer_kind`**（不用候选的——否则模型写 `kind="blade"` 就能顺手豁免缘条宽）。
  `T` 剖面缘条宽是**真实几何**，必须在题面给出（v6c 的 `str3_T` 已补「缘条宽 30 mm」）。

### 7.3 数值角色（R41，W5c 重打分轮新增）

- **问题**：`length`/`width` 同时判分且值不等时，题面若只写「800 × 600 mm」，两个数**都出现过**（`num_derivable` 判定为 `derivable_nl`），
  但「哪个是 length」**不可判**。模型按工程惯例「长 × 宽」读，若模板写的是 `{width} × {length}`，就会被判错——**错在卷子，不在模型**。
- **实证**：`stiffened_panel_800x600` / `_str3` 旧模板 `f"{width} × {length}"` ⇒ 题面「600 × 800」，gold 是 `length=800, width=600`；
  v6c 的候选把 `length` 写成 600、`width` 写成 800，被判 `params.length/width` 失败（**2 条 dev，0 条 exam**）。
  同类任务里 11 条开孔板恰好是 `length` 在前，所以没暴露——**这不是「已修」，是「恰好没踩」**，故必须升为红线。
- **判据**：审计对 `params.length`/`params.width` 这一对，若两值不等，则要求
  ①题面显式含「长度/宽度」标记，**或** ②两个数在题面里的先后顺序为 `length → width`。都不满足 ⇒ `VIOLATION`。
- **修法**：模板一律显式标注角色（`长度 X mm × 宽度 Y mm（length × width）`），不靠顺序隐含。
- **成本口径**：v6c 已冻结、候选已生成，**不为此重跑**（exam 收益 0，重生成 3 h+）；作为 dev 侧**已知下界**登记在 C-030。
  下一版卷子（若开 v6d）修模板后重生成即可回收 2 条 dev。

### 7.4 契约试建闸（R19）的边界与「gold 也过同一闸」（W5c）

- **它是干什么的**：`FEASpec.from_dict()` 在进求解器之前构造一遍，抓 **未知键（TypeError）** 与 **族/取值非法（ValueError）**。
  失败即 `failure_class=contract`，不浪费求解时间。
- **它不管什么**（实测边界，**别误当 schema required 校验**）：删掉 `material.youngs_modulus` 仍能构造成功。
  缺字段由 `spec_fidelity`（SFR）抓，不靠试建闸。因此「contract PASS」≠「spec 完整」。
- **★ gold 也要过同一闸**（专家第八轮 §3.2 点名的疑问）：C-028 有 3 条 exam 任务 **TSR PASS + SFR PASS 但 MSR contract 失败**，
  只看候选分不清「模型参数错」还是「builder 不支持这个合法组合」。`audit_contract.py` 把 **gold spec** 过同一道闸：

  | 结果 | 判定 |
  |---|---|
  | gold 能建、候选不能建 | **模型 spec 质量问题**（判 model，合理） |
  | gold 也不能建 | **任务/契约缺陷（harness）**，不得计入模型能力，须修 builder 或改卷子 |

- **v6c 实测**：**55/55 gold 全部可建**（`reports/contract_audit_v6c.json`，rc=0）⇒ 那 3 条 contract 失败一律判 model，
  **不是 harness 背锅**。负控 **NC-37** 做反向验证（给 gold 注入 `material.ply_material` ⇒ 必须 rc=1）。

### 7.5 治理闸（R42–R46，W5c-6b 新增）

> 这五条不判模型对不对，判**账本与产物自相矛盾**。四条已有机器闸，R46 只能靠留痕。

| 红线 | 一句话 | 机器闸 | 为什么必须有（实证） |
|---|---|---|---|
| **R42** headline 唯一 | 恰好一条 active claim 的状态列带「（对外 headline）」 | **S-29** | W5c 收口后 README 仍写 C-028 68.0%、C-021/C-025/C-026 各自自称 headline，而 29 项语义检查**没有一条**检查唯一性 ⇒ 22 条 active 全过却互相矛盾 |
| **R43** 投影不冒充实测 | 「可达/paper-clean」必须与实测并列并标投影 | **S-30** | C-029 曾写 dev「真实可达 25/30」，实际 7 条 dev spec_fail 中 **5 条是模型侧**，修卷子只能回收 2 条 |
| **R44** value_added 双尺度 | 任务级 + **字段级**；T1+ 非空 | `trivial_baselines.py` 的 `T1plus_family` / `n_fail_exam` | 三个地板在 exam 上全是 0 ⇒ Δ92pp 对 0 地板，技术上 PASS、科学上不硬；字段级尺度才有区分度（85.93% → 99.34%） |
| **R45** MSR 字段齐全 | 九字段非空，别名由同一变量写出 | **S-31** | `msr_excl_solver` 有数、`full_msr_excl_solver`/`dev_msr_pct` 是**缺键** ⇒ 复核者只能手算，手算就会漂 |
| **R46** key 决策留痕 | 轮换/重建/endpoint/provenance 四项分开评估并记录 | 无（靠 `W5B_PLAN` §6.0b 留痕） | 「轮换 ⇒ provenance 重签 ⇒ 代价高」经复核**错两处**：endpoint 是硬编码常量、provenance 不记 key/endpoint |

**★ R42 的判据形态本身是个坑**：第一版用「正文含『对外 headline』且不含否定词」判，结果 C-029
自己写了「不是实测 / 不是又一个下界」**被自己的否定词过滤掉**（FAKE FAIL）；C-028 的状态列里
写了指针「对外 headline = C-029」又被当成第二个 headline（FAKE PASS 反向）。⇒ **判据要用结构化字段，
不要用自然语言表述**。

### 7.6 跨模型对比：三条闸 + 它作为「归因工具」的用法（R47–R49，W5c-6c 新增）

> 同一张卷跑第二个模型（C-031 `deepseek-v4-pro` vs C-029 `glm-5.3-flash`）暴露了三个口径问题，
> 也顺带证明了跨模型对比最大的价值**不在排名，而在归因**。

| 红线 | 一句话 | 机器闸 | 实证 |
|---|---|---|---|
| **R47** 分母必须显式落盘 | 命中率分母禁止 `if 值存在` 隐式过滤；`n_counted + n_excluded == n_exam` 必须闭合 | **S-33** | C-031 的 3 条 `fabricated` 被静默跳过 ⇒ 算出与 C-029 **一字不差**的 99.34%（87.42% 才对）。同数字、反含意 |
| **R48** 不得事后择优 | headline 开跑前定死；新模型只能并列报 + 标 supporting | **S-34** | 同卷试 N 个模型取最好 = 事后挑样本，与预注册原则冲突 |
| **R49** 分裂必须标出 | 任务级 PASS / 字段级 BELOW（或反之）⇒ 成绩单写 `verdict_split`，文档并列引两侧 | **S-35** | C-031 任务级 Δ80 pp PASS、字段级 Δ**+1.5** pp BELOW |

**★ 跨模型对比是判定「缺陷归谁」的最强工具**（方法论，比分数重要）：

| 观测 | 归因 | 处置 |
|---|---|---|
| 同题、**同失败字段**在两个模型上复现 | **A/B 类**：题面或 prompt 诱导，不是模型个性 | 修 prompt / 修题面 |
| 只有某模型错、另一模型对 | **C 类**：模型能力或指令遵循 | 记为该模型局限，不改卷子 |
| 两模型 `spec_pass` 条数相同、只在某一条腿（澄清/编造）上分叉 | 任务是**可解的**，差距来自「守不守规则」 | 归因到指令遵循，别吹建模能力 |

**实证（C-031）**：两模型 `spec_pass` 都是 **20/25**；两条 `spec_fail` **同题同字段**
（`web1_offcentre` 自创 `extra.end_torque`+`torque_axis_dof`、`cfrp45s_d40` 的 `layup` 标量）
⇒ 这两处是 **prompt 约束仍不够强**，不是"模型太笨"；唯一实质差异是 3 条澄清题
（glm 澄清 3/3、dsv4pro 编造 3/3）。其中 `stiffened_panel_600x600_str3` 的 `n_stringers`
**直接由 SYS prompt 的「未提长桁→长桁数=0」授权** ⇒ 与题面的 `expected_clarifications` 打架，
属**我方 prompt 内部矛盾**，下一轮必修。

### 7.7 生成端 + 产物端：四条闸（R50–R53，W5c-6d/6f/6g 新增）

> §7.5/§7.6 守的是**账本**（文档是否自相矛盾、分母是否闭环）；本节守的是**输入端**——
> prompt 有没有偷偷给答案，以及「改了 harness 之后有没有把被比较的对象全部重跑」。
> 起因：第十轮复评把 C-031 的三个缺口定性为「prompt 授权 + 模型标签 + 分母混类」，
> 三条都不是模型能力问题，而是**我方产物与 harness 的问题**。

| 红线 | 一句话 | 机器闸 | 反面实证 |
|---|---|---|---|
| **R50** prompt 不得盲填、不得泄题 | ① 题面**提到**某特征却没给数量 ⇒ 必须澄清，prompt 不得授权默认值；② prompt **不得**注入 `expected_clarifications`（等于把判据给模型） | **S-38** / **NC-45** | 旧 prompt「未提长桁→长桁数=0」× 题面「若干根长桁」+ 登记 `expected_clarifications=['n_stringers']` ⇒ 自相矛盾。deepseek 被诱导、glm 没被诱导 ⇒ **不能记成模型错** |
| **R51** 模型标签必须是实测值 | 成绩单顶层 `model` == `provenance.model`，两者都读自**候选文件里生成时 pin 的 id**；禁止默认值、禁止命令行声称覆盖 | **S-36** / **NC-43** | C-031（deepseek-v4-pro）顶层 `model` 写着 `glm-5.3-flash` —— 36 项语义检查里**没有一条**核对它 |
| **R52** 分母四类拆开 + 两层闭合 | 层A（准入）：`n_counted + clarify + unresolved + notrun + env + unknown = n_tasks_total`；层B（原始分母内部）：`n_counted = n_solver_excluded + n_counted_excl_solver`。`n_clarify_excluded` **只含** `expected_clarifications` 题 | **S-37** / **NC-44** | C-031 `n_clarify_excluded=5` = 4 条澄清 + 1 条 `cfrp090s` 无输出；C-029 的 4 是 4 条纯澄清 ⇒ **两个数不同类**，并排放就被读成同口径 |
| **R53** harness 变了必须全量重跑 | 改 prompt / 改 decode / 改预算后，**所有被比较的模型都要重新生成**；禁止用「A 模型旧 prompt × B 模型新 prompt」的成绩做对比 | 人工 + `provenance.model` / `tasks_sha256` / `prompt_sha256` 三件对齐 | C-029（旧 prompt）与 C-032（新 prompt）**不可并列**；同理 C-031 不能再与 C-032 拼成「模型对比」 |
| **R54** MSR 是条件通过率，比之前先对齐分母与 SFR | MSR 分母只含「产出 spec 且非 `expected_clarifications` 的题」；`msr_definition` 与 `n_no_spec_excluded_ids` 必须写进成绩单（**不得只把分母改小**）；跨成绩单比 MSR 前先对齐分母，**分母不同时 pct 不得直减、不得据此排名** | **S-40** / **NC-46** | C-033 exam MSR 95.2% > C-032 的 90.9%，但 TSR 低 4 pp——C-033 分母 **21**（排除 `cfrp45s_d40` 无输出），C-032 是 **22**，**被排除的恰好是失败题 ⇒ 分母小的 pct 更好看**（与 C-031「MSR 反直觉」同源，这次发生在 MSR 内部） |
| **R55** prompt 修复必须做逐题回归 | prompt 版本变更后必须对比新旧 `per_task`；**「exam 不变但 dev 变」的反向变化必须逐题定位并写进 claim**，且给出闭合断言（旧通过 + fail→pass − pass→fail == 新通过）。**净额相同也可能是成对抵消** | **S-41** / **NC-47** | C-032 的 dev −1 实为 **+1 / −2**：`stiffened_800x600_str3` 由 `600/800`（读反）纠正为 `800/600`（题面 R41 修正被兑现）；两条柱壳 `extra.end_moment` = `5e4` 与 `5e6` 而 gold `5e7`（×10⁻³ / ×10⁻¹ 量级偏差，与 prompt 无关） |
| **R56** 跨模型榜单必须三列并排 | 任务级 TSR / 字段级命中率 / 失败分层（model·solver·contract·unresolved）**缺一不可**；MSR 分母不等时**不出 Δ、不得据此排名**；表必须带「能说什么/不能说什么」与限制段 | **S-42** / **NC-47** | 同一对模型 TSR 92>88、字段级 PASS>BELOW，而**条件 MSR 90.9<95.2**（分母 22 vs 21，被排除的是失败题）⇒ 只引一列可得出任意结论（C-034 / `make_w5d_leaderboard.py`） |
| **R57** prompt v3 仍不得注入 `expected_clarifications` | ①**不得**注入 `expected_clarifications`；②**不得**靠改 `clarify_wrong_keys` 元数据把 FAIL 变 PASS（那等于事后改判分）；③**prompt 每次变更都必须做消融并落档；净收益 ≤ 0 一律否决，否决后 sha 必须回到基线** | **S-38** / **S-43** / **NC-45** / **NC-48** | C-033 剩余 1 编造 + 1 问错字段；v3/v3b 两版实测**零收益 + 失败点迁移**（glm 3/3/3、deepseek 2/2/2）⇒ 否决、回退 v2（C-035） |
| **R58** 官方文档必须被 gate 读 | 被 §0 指定为「开工必读」的**数据类** SOT（CLAIMS / RUBRIC / `reports/INDEX.md` / 当前成绩单）**必须至少被一条语义检查实读**；`AGENTS.md`/`CLAUDE.md` 属协议文本、由 §7 声明兜底，不在本闸范围；没有闸读它的文件视为未校验，不得当作 SOT | **S-44** / **NC-49** | S-00..S-43 共 44 项里**没有一条读 INDEX.md**（grep = 0），于是 INDEX §2 写「⓪ 当前官方 headline（C-029）」、§1 写（C-032），两处并存；agent 照 INDEX 重跑 v1 代基线**不会报错**（两代 exam 同为 23/25）。**★ 2026-11-01（v6.11）口径修正**：S-44(b) 的覆盖关系**只从 `C-0xx：` 之后、第一个 `（` 之前的清单段读** —— INDEX 该行在括号里逐条描述每条负控（`**NC-49 四向**`…`**NC-67 五向**`），**整行扫会把「提及」当成「点名」**，覆盖恒成立；实测主区间上界 67→66 后 NC-67 仍判覆盖 ⇒ **NC-49 的 N-2 向从「红」退化成「漏判」**。同时删掉「主区间上界 == 最大 NC 编号」这个代理（它隐含要求编号连续，而编号一直跳号：从无 NC-68/NC-69），改为逐条覆盖 + 区间不得虚报 |
| **R59** 收口顺序固定：负控 → check_claims | 官方 `reports/check_claims.json` 必须在 `negative_controls_<N>.json` **之后**写；判据：C-019 记录的 artifact `mtime` == 实际 mtime，且 check_claims.json 的文件 mtime ≥ 负控 json 的 mtime | **S-45** / **NC-50**（★ v6.12 起收口还有**第三道** `_f9_artifact_freshness.py`：负控 → check_claims → 产物新鲜度。它只读 HEAD、**不产生新的 mtime 依赖**，故不进 (a)(b) 两条判据；但它必须在**重建产物之后**跑，否则只会告诉你「刚重建前确实过期」） | 第十二轮 §3.4 实测 check 22:18:28 早于负控 22:19:45，C-019 记录 mtime 差 103 s——**内容与 sha 全对、只有元数据过期**，人工比对才抓到 |
| **R60** dataset/求解类脚本必须用项目 venv | `verify_dataset`/`check_forms`/`score_baseline`/`msr_l3`/`eval_dataset`/`dedup_dataset`/`run_pipeline` 一律用 `…/envs/default/Scripts/python.exe`；缺 numpy/gmsh = **环境问题**，不得记数据失败（R16） | **S-46** / **NC-51** | 第十二轮 §3.5：系统 python 跑 `verify_dataset` 直接 `No module named numpy`，换 venv 才打出 `55 paired + 9 modeling-only` |
| **R61** ccx/abaqus 绝不并行（硬约束） | `solver.run()` 必须经过全局求解锁 `feagpt_repro/.solve.lock`；第二个求解直接抛错；锁超 1 h 视为崩溃残留、自动接管 | **S-47** / **NC-52** | 并行两个 ccx 会**静默空转、返回码仍 0**（结果为空），「返回 0 就算成功」会把它当成功；本仓库踩过两次（`check_forms` 未停就起柱壳 ccx；第十二轮 §3.2） |
| **R62** claim 正文的计数必须等于 artifact 的计数 | claim 行里的分项计数（如 C-003 的 `N field / N scalar-disp / N reported-only`）、构成拆分（`N 条 d36` + `N 条 <日期> 实测`）与分母（`不说 N/N`）**必须与 artifact 实读逐项相等且加和闭合**；`sha256` 只证明文件没被换，**不证明数是对的**；任一计数**解析不出来一律判红**（锚点缺失不得 skip） | **S-48** / **NC-53 四向** | `grep "gate3\|C-003" check_claims.py` 曾是 **0 命中**（N-10）：C-003 从 55 条时代的 `34/15/6` 漂到 64 条时代的 `39/18/7`，期间 48 项语义检查**每次全绿**——数字漂移在 sha 层面完全不可见 |
| **R63** 文档里不得写死可推导的计数 | `AGENTS.md` / `CLAUDE.md`（及同类协议/导航文本）里**不得出现** `N claims / N artifacts / N semantic`、`check_claims N/N/N`、`负控 N/N` 这类**本可由闸脚本直接输出**的数字；一律写「**以 §0 实读为准**」| **S-51** / **NC-54 十向**（写死三元组、写死负控两向） | 写死 = 制造第二数据源 ⇒ **必然漂**。实证四条同型：N-1/N-2（INDEX 两个「当前 headline」）、N-10（C-003 的 `34/15/6` 漂到 `39/18/7` 全程绿灯）、N-12（C-001/2/4/5 与 external 无闸）、以及 T-A10 顺带查出的 `manifest.summary.xval_cases_available` **停在 55**（实测 64，双码早已闭合）。这些都不是「忘了改」，是**结构上允许漂** |
| **R64** 对外数字表必须有分母口径且不得陈旧 | `external_numbers.md` 每一行必须有**分母口径**列，且每个 `A/B` 比值的 `B` ∈ {spec 数, 算例目录数}、`A==B`；两套分母必须都出现；整表必须与 `make_external_numbers.build()` 的当前输出**逐字节相同**；`source_artifacts` 每一项都必须真实存在 | **S-50** / **NC-54 十向**（分母混写 55、删「分母口径」列、手改一格数字三向） | 该表是**对外唯一数字源**，此前 `grep "external_numbers" check_claims.py negative_controls.py` = **0 命中**。三类风险都是「sha 绿但内容错」：忘重跑 ⇒ 陈旧；手改 ⇒ 假数（表头明写「勿手抄」）；「关 1 的 64/64」与「关 4 的 128/128」分母不同却并列 ⇒ 一旦只有一边不全就会被读成矛盾，而「都全过」时看不出（R54 的另一种形态：**分母不等时连并列都不该有**）|
| **R65** 任务层冻结件不得漂移 | (a) `tasks/tasks.jsonl` 必须与 `reports/papers/` **当前卷**逐字节一致；(b) `tasks/nl_frozen.jsonl` 的每一行必须仍在 `tasks/nl_human.jsonl`（已发布题面不得被模板改动连带改写）；(c) `TASK_CHAIN` 里上一版卷的**每一行**必须仍在当前版 —— **跨版本只许加行，不许改老行** | **S-52** / **NC-55 三向**（当前卷不一致 / 已发布 NL 被改写 / 跨版改老行） | 同一轮踩了两次同型缺陷：`make_tasks.py` 的 `rotate_idx=stats['L1']`（**全局累计数**）与 `make_nl_human.py` 的 `STYLE_CYCLE[i % 3]`（**族内序号**）都是「看起来确定性、实际依赖位置」的轮换 ⇒ 数据集 55→64 时 **48/55 条 L2 题目** 与 **37/55 条 NL 题面** 被静默改写，而当时**没有任何闸能发现**（S-48/S-49 只比计数、`verify_dataset` 只数目录、`r32_audit` 只查题面可解性）。★ 处置不是「下次注意」，而是把已发布卷变成**显式冻结件**（`l2_omit_map.json` lockfile + `nl_frozen.jsonl` 整行冻结），并让闸读它们 —— 这正是 R58 的正面形态。★ 边界：`TASK_CHAIN` 是**手工推的**，因为「只许加行」不是天然语义 （v6→v6b→v6c 都是改行），这一步刻意不自动化 |
| **R66** 判据失效子集必须隔离并双报 | 当一条判据在某个**可精确识别的子集**上无效（不是模型做错、是判据测不到）时：①**不得改题掩盖**（改题会连历史一起废掉，且与 R65 任务层冻结直接冲突）；②**不得把无效子集继续算进单一对外数字**（等于知道错了不改）；③必须**隔离 + 双报**，两个分母并列出现，且**一并适用 R54**（分母不等 ⇒ 禁止相减、禁止据此排名）；④「双报」必须有闸实读，否则是文档里的承诺（R58） | **S-53** / **NC-56 四向**（缺一块 / 掩码过期 / 允许相减 / 只报一侧分） | L2 靠「删一个字段、要求模型澄清」出题，但 `spec.name = case_id` 是人给的描述性名字，**19/64 条把被删的值写在自己身上**（`..._d30` 省略 `hole_d`、`..._frm3` 省略 `n_frames`）⇒ 那 19 条的 clarify 判据**失效**。处置取 C'：不动题、只改口径，`clarify_all(64)` 与 `clarify_informative(45)` 并列，`delta_allowed=false` 写进 artifact。★ **判据自己漏了比没判据更危险**：第一版泄漏判据用 `\bd(\d+)` 匹配 `_d30` 失败（`_` 是 word 字符，`\b` 不成立）⇒ **只抓到 5 条、漏了 14 条，给了个好看的假数**；改 `(?:^|_)` 语义前缀才对。★ **边界（T-A13b 已更新）**：L2 已于 2026-10-30 首次跑分（glm，`status=scored`，见 C-041），S-53 的「成绩单必须采用」已自动加严为**两侧都必须有整数 `passed`**。★ **新增适用边界（N-27）**：`clarify_informative` 实测**同时是一个族子集**（36/45 是翼盒）—— 实测 15 条失败**全在翼盒**、非翼盒三族全对，而泄漏 19 条里 16 条属这三族 ⇒ **64 与 45 的差主要是族构成差，不是泄漏净效应**。因此 R66 的双报仍然必须做（不得只报一侧），但**不得把 `clarify_informative` 当「L2 的真信号」单独引用** |
| **R67** 改了判分必须证明老数不动 | 改了判分/口径的**实现**（不是改题、不是换模型、不是换 prompt）后，必须给出「除声明项外零差异」的**构造性**证据：① 用**官方当时的完全同参数**重跑（`--label`/`--trivial`/seed/分母参数一律照抄 —— 漏传参数会造出**假 diff**，而假 diff 会把「真的改错了」一起掩盖）；② 逐**叶子**比对而不是逐键（只比顶层键会漏掉 `per_task[*].x` 这类按下标展开的改动）；③ 三类差异分开记账：`changed`（改值，须逐条 `--allow-changed` **精确路径**声明，**不接受前缀批量放行**——否则「逐条声明」退化成「一次放行一片」）、`removed`（删键 = 悄悄改口径，一律红）、`added`（新增键，须声明 allowlist）；④ 判据工具自身必须能被证伪（自比 A==A 须 PASS + 改值/删键/越界新增/前缀不放行四类各自红） | **NC-57 五向** / `_regress_scorecard.py` / `_regress_task_a11a.py` | T-A11a 为让 v7 支持双分母而改 `score_baseline.py` / `msr_l3.py` 的 exam 谓词。「跑出来看着一样」不是证明 —— **新增键和偷偷改数在肉眼上长得一模一样**。实测 1607 个既有叶子 0 变动、CI 64 叶子 0 变动。★ 同轮还撞到**同一个 bug 的第二次复发**：跨盘符 `os.path.relpath` 在 C 盘临时目录抛 `ValueError: path is on mount 'C:', start on mount 'F:'`，10-28 修过两处、10-29 又在 bootstrap_ci 撞 ⇒ 收敛到 `_paths.rel()` 覆盖 8 个脚本 —— **只修撞到的那一处，它一定会长回来** |
| **R68** 判失败必须能说出为什么 | 任何判 FAIL 的条目，其失败**原因**必须是**落盘且可审计**的：① 至少记下「哪个闸挂了 + field/expected/actual」，不能只剩一个布尔（`gates = {k: bool(v['pass'])}` 这种把结构化诊断压平的写法一律不合格）；② 兜底值**不得是空串** —— 空串会被下游的 `or` / `if` 静默吃掉，要写显式的 `NO_DIAGNOSTIC_CAPTURED`；③ 建闸之前先看**那个字段在真实 artifact 里是不是非空**：建立在可能为空的字段上的闸 ＝ 查空气，必绿（R58 的推论）；④ 历史 artifact **不回填**，但必须承认「跨版本 failure_breakdown 不可比」 | **NC-58 五向** / S-54 / `msr_l3._gate_diag` `_diag_text` | T-A11b 实测：`failure_detail` 在 v6c/v7 所有 `class=model` 条目上**全是空串** —— 两层叠加（`gates` 被压成布尔；`failure_detail` 只取 `pipeline` 一个闸，而 `spec_fidelity`/`mesh_quality`/`semantics`/`fidelity_disp` 失败时 pipeline 是 pass、detail 是 `None`）。后果不是「少个字段」：N-20 的锁冲突就是因此漏掉的（事后只能重跑单条探针才知道它其实是 model 失败），而 S-55（solver 不得含锁冲突）在修之前**必然绿**。修后 `L3_stiffened_panel_800x600_str3` 能直接读出 `params.length` 期望 800 实得 600 / `params.width` 期望 600 实得 800 |
| **R69** 放宽必须有边界 | 任何「允许例外 / 允许违规 / 允许不等」的闸，**必须在同一处写明三件事**：① **哪里仍然必须为 0**（否则放宽会吃掉整条判据）；② **例外必须带 reason**（空口「已知」不算）；③ **例外不得进入对外数字**（对外口径只看「必须为 0」的那一部分）。★ 反例（本轮实证）：`README` 写「`r32_audit --scope all` 必须 rc=0」而 v7 实测 rc=1 —— 一句**字面为假**的闸门口径，照做的 Agent 只能阻塞或静默忽略后者；改成「exam 违规必须 0、dev 违规允许但须带 reason 且不得对外」后，三条边界都在，才算放宽而不是放弃 | **S-57** / **NC-60** / **S-54(e)(f)(g)** / **NC-61** | T-A12b：`--scope all` 由「有违规就 rc=1」改为「exam 违规 >0 才 rc=1」；同时给 artifact 补 `n_exam_violations` / `n_dev_violations` / `gate_ok` / `paper_sha256`，让「放宽」本身可被独立复核 —— 放宽若不可判，就等于没有判据 |
| **R70** 判据的字符串匹配必须有边界 | 任何「键名 / 别名命中」类判据，**不得**用裸子串 `a in text`：当被匹配的串恰是另一个串的前缀或后缀时（`n_stringers` ⊂ `n_stringers_per_skin`、`thickness` ⊂ `rib_thickness`/`skin_thickness`/`stringer_thickness`、`width` ⊂ `stringer_flange_width`），会**静默假通过** —— 它**不留「本该过没过」的痕迹，只让数字偏高**（与 R52 恒真式、N-17 name 泄漏同族：**错的方向都是「看起来更好」**）。★ 同一条通道是**双向**的：反向也会**假红**（把短键登记为错族键时，长键的正确写法会被它吃掉而误判 FAIL）—— 所以「改完只会变严」是错的，必须用零差异证明净效应为 0。★ 修法：**ASCII 标识符按 token 边界** `(?<![A-Za-z0-9_])X(?![A-Za-z0-9_])`，**非 ASCII（中文短语）仍按子串** —— 中文没有词边界，对它加边界等于**把判据改坏**（`翼肋` 会判不中「翼肋数量」）。★ 必须仍然命中的写法（加固的边界本身）：`structure.params.n_stringers`（前是点）、`n_stringers（根数）`（后是中文括号）、`"n_stringers"`（JSON 引号）—— 边界只约束**标识符字符**，不约束其它分隔符。★ 判据改动一律走「跑前冻结 → 零差异（**三路并行**：旧逻辑逐字副本 / 新逻辑用真实 `_alias_hit` 组合 / 真实调用点；只比前两者在改前是自比，不算证据）→ 负控」；**跑完后才发现的问题另立项，不当场改**（R-A2 post-hoc） | **S-58** / **NC-64** / `_diff_judge_a13d.py` | T-A13d：`score_baseline.judge_clarify_field_level` 的两处裸子串（`hit_wrong` 与 `hit`）改走 `_alias_hit`；实测 104 条 clarify 文本 × 三路判据 **0 变化**、四份成绩单 **L2 661/660 + L3 2098/2137 叶子零差异**（无 allow 项）⇒ 本轮**不改任何对外数字**，只消除一个潜伏漂移面。★ 旧账未清的部分：`_audit_clarify_meta.py`（W5c-6d）早已记下**假红**那一侧，本轮补的是**假通过**一侧 —— 两者是同一函数的两端，不是两个发现 |
| **R71** 判分元数据只许修**事实错误**，且修正必须留痕 | 当判分元数据（`clarify_wrong_keys` / `clarify_aliases` / `expected_clarifications`）与 **R34 键名契约矛盾**时（实证：`L3_naca4412_wingbox` 把翼盒族**正确**键 `n_stringers_per_skin` 登记成**错族**键 ⇒ 一条正确答案被判 FAIL、理由与事实相反），**不得直接改已冻结的卷文件** —— `tasks/tasks.jsonl` 与 `reports/papers/tasks_v*.jsonl` 同 sha，S-52 的卷链语义是「跨版只许加行」，改一行会让链断并作废所有下游 sha 锚点（r32 artifact 的 `paper_sha256`、成绩单 provenance、S-57）。★ 修正走**显式修正表** `tasks/clarify_wrong_keys_fix.json`：每条必带 `from`/`to`/`reason`/`evidence`；**`from` 必须逐字等于当前卷现值**（卷一变，表自动失效，不得静默留用）；**`to` 不得包含该族 R34 正确键**（否则等于用修正表再制造一次同样的错）。★ 修正表必须**记进成绩单 `provenance.judge_overrides`**（路径 + sha256 + `applied_to`）—— 否则「用了表却没记」会让两份成绩单口径不同而**看不出差别**（与「prompt sha 未记」同族事故）。★ **用途边界**：只许修**事实错误**，不得改阈值/改口径/让某模型好看；「让数字变好」永远不是理由，**能说清哪一条事实错了**才是。★ **over-clarify 政策（本轮预注册）**：「命中 expected + 多问一个不必要的字段」**不判 FAIL** —— 理由是实测的两条：① 按语义判（是否提到别的键名）**4/4 假阳性**（模型实际在解释「题面给了 X 但没给 Y」）；② 按条数判，代价几乎全落单侧（L2 上 glm 掉 0 条、ds 掉 8 条）⇒ 等于**按模型调阈值**。但它必须**可观测**：`per_task.n_questions` 落盘，只作交互效率指标，**不进 TSR/SFR/MSR 分母**。★ **这条政策的边界（不得含糊）**：L2 全 64 条 `clarify_wrong_keys` 均为 `null` ⇒ **「把字段全问一遍」在 L2 上仍是已知退化解**，该缺口**未堵**，不得据此宣称 L2 抗退化；下一版若要堵，必须用「该字段在 gold 里是否真的未定」这类**可判**判据，**不得**用条数或语义近似 | **S-59** / **NC-65** | T-P1a：ds 在 `L3_naca4412_wingbox` 上「先问对 `n_ribs`、又多问一句 `n_stringers_per_skin`」被判 `clarify_wrong`，而后者恰是**翼盒族正确键** ⇒ 修表后 ds legacy exam **22/25 → 23/25**（88.0%→92.0%）、2×2 由 `only_glm 1` 变 **both 23 / only_glm 0**、glm **一位数字未动**、MSR 两模型不变（澄清题不进 R23 分母）。**post-hoc**：已看过结果才定政策 ⇒ 新版本号 + 旧 artifact 留档（`reports/archive/*__pre_p1a.json`）+ bridge（1 条翻转）。★ 三处同类登记只有 **1 处**是错的（柱壳/加筋板用 `n_stringers`，把 `n_stringers_per_skin` 当错族键是**对的**）⇒ 「统一改成 `n_stringers`」的首版方案会把**两条加筋板题**判死，模拟当场证伪 |
| **R72** 分层结论必须有分层证据 | 凡以**族 / 桶 / 子集层面的差异**为论据的结论（实证：N-27「`clarify_all` 64 与 `clarify_informative` 45 的差主要是**族构成差**、不是泄漏净效应」，该结论**整体建立在族级通过数上** —— 而族级数字此前只活在一份**手写**诊断 md（`task_a13c_ds_report.md`，全仓无生成器）里 ⇒ 违反 R-A3「禁止手抄数字」），**该层面的数字必须由 artifact 逐层落盘并可复算**：①每层都要有 `n` / `passed` / `pct`（族级即每族三件）；②**闭合**：`Σ层 == 总数`，任务数与通过数**两侧**都要；③**可加**：粗桶必须等于细桶之和（本案是每族 `informative + invalid == all`）；④**不得只报合计**：只报 `49/64` 与 `30/45` 而不给族级，等于让结论失去证据，读者无法判断「差」来自构成还是来自能力。★ **模板里写死的数字同样违规**：report 生成器把「实测 15 条失败全部落在 wingbox」这类句子硬编码进 md，与手抄 claim 是**同一种病，只是藏得更深** —— 必须从数据现算。★ **同名不同义必须由闸断言**：`by_family` 在**顶层**是**分母构成**（每族多少题，值为 int），在**模型块**是**统计块**（值为带 n/passed 的 dict）；写反即红（N-26 形态：同一个键在两处含义不同，读的人不会报错、只会读错）。★ **允许什么**：族级样本可以很小、`n` 可以只有 2~3，但**必须如实标 `n`**，只给 `pct` 不给 `n` 等于把 1/1 和 36/36 说成同一件事。★ **这条规则的边界（不得含糊）**：本规则只守「落盘 + 闭合 + 可加 + 不换义」，**守不了「族划分本身是否合理」** —— 族是考卷的属性，改族就是改卷，走 R65（卷链只许加行） | **S-60** / **NC-66** | T-A14：族级数字（glm `wingbox 24/39`、非翼盒 `25/25`；ds `wingbox 15/39`、非翼盒 `21/25`；泄漏 19 条里 16 条不在最差族）此前**只在手写 md 里**。落盘后**六个既有数字逐数未变**、且与手抄值**逐个对上** ⇒ 是「数字对但没有 artifact」，不是数字错；两份 `l2_scores` 各 +36 叶子（全为 `by_family`）、`l2_clarify_dual.json` +75 叶子（3 个 `by_family_note` + 72 个族级）/ 删 0 / 改 0。★ 顺便把上一轮**我自己**把 R71 插到 R70 前面的顺序错位摆回升序 |
| **R73** 前置闸必须查**数据实体**，不得只查容器存在 | 凡以「防静默空转」为目的的前置闸，若只判断目录/文件**存在**，它防的是「一点没给」，防不了「给了但为空 / 解到别处 / 解包失败 / 给了旧版本少几条」。实证（T-B1 在真 clone 里实测）：`evaluate.require_dataset()` 原实现只有 `os.path.isdir(modeling)`，第三方 `mkdir modeling` 就能骗过它 ⇒ 静默跑出 `exam TSR 3/25 (12.0%)` 的**假成绩单且无任何警告**；这比直接缺数据更危险 —— **它带着一张看起来合法的成绩**。要求三级：①容器存在；②容器里有**可判定的实体**（如 `*/spec.json`，而不是「有文件」）；③**覆盖被测总体**（给了期望集就逐条核，缺失时必须报出**缺几条 + 样例**）。★ **两种失败必须给不同原因**：「没给」（目录不存在）与「给错了」（目录在但没有可判定实体）是两件事、下一步动作也不同；给同一句话等于没区分。★ **报错必须可执行**：只说「不完整」却不说缺几条、缺哪几条，使用者无法自救。★ **边界**：本规则只管**闸的检查深度**，管不了「闸该不该存在」；也不保证期望集本身正确（期望集来自任务卷，卷错则闸跟着错）。 | **NC-67** | T-C1：`require_dataset(fea, expect_ids=None)` 三级化；三处真实调用点（`score_baseline` / `msr_l3` / `r32_audit`）传 `expect_ids`。**实测**：空目录 → `rc=2` 报「没有任何 spec.json」、**不再产出任何成绩**；只有 5 条 spec.json 时 → `rc=2` 报「缺 51 条」并给样例；本机 64/64 与 55/55 覆盖 100% ⇒ **不误报**。★ 顺带把散在 `evaluate_one` 三处的 `case_id` 转换链统一到 `case_id_of()`，并由 `_c1_caseid_equiv.py` 对**两个卷 357 条 task_id** 逐条断言新旧结果相等（含「注入差异可被检出」的反向自检，防判据恒真）。 ★ 另把 `case_id` 转换的一致性变成**可执行证明**而不是注释承诺 |
| **R74** 自监督的闸必须有不依赖自身的检查入口 | 任何**在事件发生时自动触发**的闸（git hook / watcher / 定时任务 / 文件监听），其失效**不产生任何错误信号**——它不运行，所以没人报错，与「压根没装这道闸」完全等价（R58 落在**触发器**上的形态）。**实证（T-D5b）**：T-D5 的 `check_commit.py` 靠 `.git/hooks/pre-commit` 触发，而 hook **不入库**（`.git/` 不被追踪）⇒ 新 clone / 换机 / 重建仓库后闸静默消失，而**当时没有任何闸会报**。要求：① 必须有**独立入口**判它还在 —— 判据**不得只写在 hook 里**（那等于「它跑了才检查它有没有跑」，同语反复，且在 hook 内恒真）；② 判据必须查**实体**（引 R73）：文件在 ≠ 内容是本闸 ≠ 指向**当前**脚本 ≠ 未被 `core.hooksPath` 改道；③ **无对象时显式 `not_applicable` 并说明**（如非 git 工作副本 / 解压包），不得静默绿，也不得判红逼人绕过；④ **平台相关判据必须隔离并标注**：可执行位在非 POSIX 平台 git 不追踪，判了只会假红 ⇒ 标 `not_run` 并写明「本向在此平台**未被验证**」，不得假装验过。★ **判据必须能构造出红**：每一条都要有「制造该失效 → 必须红，且红的**是这一条**」的可执行证明（`--self-test`）；只断言「红了」会放过「红的原因不对」，而多红一条同样会把人引去修错的地方。★ **边界**：本规则只保证「哨兵还在、且指向当前脚本」，**不保证哨兵判得对**（那是 `check_commit.py --self-test` 的事）；也管不了钩子链上别的 hook 是否被改。 | **S-61**（判据在 `hook_guard.py`，八向自检） | T-D5b：`hook_guard.py` + `check_claims` S-61 接线 + `--skip-hook-guard` 显式跳过。判据用 `git rev-parse --git-path hooks` 取**生效**目录 —— **实测该命令跟随 `core.hooksPath`**（设 `.husky` 即返回 `.husky`）⇒ 不写死 `.git/hooks`，也不把「hooksPath 非空」一刀切判红（装进 `.husky` 并入库是**更**好的做法）。**八向**：正向①默认路径 / H1 缺失 / H2 是别的钩子 / H3 指向僵尸脚本 / H3 指向另一副本 / H1 改道到空目录 / 正向②改道且已装（**不得误红**）/ H0 非 git。**实测**：移走主仓库 hook ⇒ S-61 红且**只有 1 项失败**（H2/H3/H4 正确 `not_run`，不级联 —— NC-67 的教训）；恢复后 hook 的 sha256 与原来**逐字节一致**；`hook_guard.py` 改名 ⇒ S-61 报「无法导入」判红**不 skip**（缺判据即红，R58）；`--skip-hook-guard` ⇒ 标 skip 且语义项计数 61→60（skip 不计入，不冒充通过）。 |
| **R75** `--public` 只能放宽「公开集里结构上不可能满足」的判据，且必须精确到原因 | 公开分发集与私有仓库的**对象集合不同**：按拍板移出的协议文件、被渲染层脱敏的本机路径、不分发的 `.git/hooks`，在公开集里**不存在**。判据判红**不是因为代码错了，而是因为对象不存在** —— 但也不能就那么红着：第三方第一次照 QUICKSTART 跑就是 5 项红，后面成绩再漂亮也没人信。三条边界（**缺一不可**）：① **显式** —— 只在调用方显式声明 `--public` 时生效，**绝不自动**（不得写成「文件不存在就跳过」，那会让 `rm AGENTS.md` 成为通用的逃避手段）；② **精确到原因** —— 豁免只对「失败原因恰好是公开集造成」成立，判据真的违规（协议文件**存在且**写死计数、`PY=` 是裸 `python`、非目标 claim 的 artifact 缺失）**仍判红**；**只按 `sid` 豁免 = 把判据废掉**（这是本条最容易被写错的地方）；③ **不计入通过** —— 豁免项标 `exempt` + `reason`、单列计数，不得进入任何对外数字，也不得说成「全绿」。**边界**：本条只管「豁免该怎么写」，不管「公开集该含哪些文件」（那是发布决策，归 D4/R-A10）。**实证** `_f3_public_exempt_selftest.py` 六向：正向豁免 5 项且其余仍红 / 不加参数一个都不豁免 / 协议文件存在时 S-51 不得豁免 / `PY=` 裸 `python` 时 S-46 不得豁免 / 删非目标 artifact 时对应 claim 仍红 / 不加参数时 C-013 必须红。**顺序**：R70→R75 严格升序（S-56 会查这张表的编号不跳号、不乱序）。

**★ R52 的层次修正（本轮实测后改写，专家原稿把两层混写）**：
专家第十轮原文写 `n_counted + n_clarify_excluded + n_unresolved_excluded + n_solver_excluded = n_exam`，
这会把 solver 失败**加两次**——solver 失败在**原始口径下是计入分母的**（对模型确实是失败），
只是在「剔除 solver 口径」里被拿掉。若照原式实现，C-029 会算出 `51 + 4 + 0 + 4 = 59 ≠ 55`。
⇒ 拆成层A（准入排除）与层B（原始分母内部剔除）两条闭合，各自独立断言，实现见 `msr_l3.py::_denom_audit`。

**★ R50 的边界（**没有**采纳「把 `expected_clarifications` 传给生成器」这条建议）**：
第十轮建议里给了「或把 expected_clarifications 直接传给生成器，让模型知道这些字段该问」这个选项。
**否决**：`expected_clarifications` 就是该维度的判据本身，传给生成器等于在 holdout 上泄题，
会把这个维度变成「照着答案念」。改法是**在 prompt 里写通用规则**（题面提了特征却没给数量 ⇒ 必须澄清），
让模型自己判断哪条题触发，规则对全部任务一视同仁。

## 8. 产物纪律（W5a'，R25/R26/R27/R28）

- **官方 artifact 唯一出处 = `feagpt_repro/reports/`**（入库）；`eval_runs/` 是被 gitignore 的
  工作目录，任何写在这里的「官方数字」都不可复现，且重跑即覆盖（C-021 的 v4 成绩单曾因此被 v5 覆盖）。
- 文件名必须带版本：成绩单 `baseline_scorecard_L3_v4.json`（官方）/ `..._v5_rescore.json`（诊断）；
  考卷快照 `papers/tasks_v4.jsonl`、`papers/tasks_v5.jsonl`（+ `SHA256SUMS`）。
- 生成成绩单时脚本自动写入 `provenance`（考卷路径 + sha256 + 候选目录），
  复现时用它对齐「这份数字当时用的是哪张卷子」。
- `python check_claims.py` 每条 active CLAIM 检查：存在 → git 追踪 → 不在 `eval_runs/` →
  与 command 的 `--report/--json` 路径一致 → 同路径不被两条 claim 占用；记录 sha256/mtime。
- 诊断结果（旧候选 × 新考卷）**不得**占用官方路径，且必须在 `reports/INDEX.md` 标 diagnostic。
- **分发产物必须能自证「代表当前状态」**（F-9，v6.12）：`_handoff/` 下的两个产物
  （离线 bundle、公开快照）**不进 git 历史**，所以「它过期了」不产生任何错误信号 ——
  这是本项目里唯一一类「坏了也不报错」的产物。判据是 `_f9_artifact_freshness.py` 的
  **A0–A4**，只做「便宜地比 HEAD」（不 clone、不 emit、不写文件）：
  `public_manifest.json.source_head` 与包内 `refs/heads/main` 各对一次仓库 HEAD；
  谓词与 bundle 闸的 **C9 同一条**（落后区间的改动必须全是 metadata，`is_metadata()`
  **直接 import**，不另写一份）。A0 manifest 缺失判红不 skip；A1 要求「快照成员数 ==
  `n_keep`」**且**「快照里那份 manifest 与仓库里那份逐字节一致」（抓「manifest 换了、
  快照没换」）；A3 要求「文件名里的 sha == 包内 main」（**改名不等于重打**）。
  ★ 边界：本闸只判**新不新**，判不了**内容对不对** —— 内容归 bundle 的 C1–C10 与
  快照的 P0–P8。★ 多份候选包并存时本闸**不替你选「最新」**（mtime 会被复制改掉、
  文件名只证明「它是那个提交的包」），必须人来清掉一份。

## 9. 版本记录

| 版本 | 时间 | 变更 | 原因 |
|---|---|---|---|
| v1（post-hoc） | 2026-10-25 W4d | 初版（工程层口径） | 看过 30 条候选后调整 |
| v2 | 2026-10-25 W4e/f | exam/dev 分栏 + 澄清字段级 + SFR 编造对齐 + 试建闸 | 专家第四轮 R15-R20 |
| v3 | 2026-10-25 W5a | MSR 分母按任务属性排除（R23）+ R21 任务构建期方向检查 + NC-20..22 + exam.msr/dev.msr 汇总 | 专家第五轮 P0-1/P0-3/P1-1/P1-2；考卷 v5（坐标系写死 + panel 澄清题迁移 str3） |
| **v3.1** | 2026-10-25 W5a' | **仅文档/计数/产物纪律**：负控计数 23→24→**28**（补 NC-15b、NC-23..26）+ 新增 §8 产物纪律；**判分口径零改动** | 专家第六轮 P1-2（RUBRIC 说 NC-1..22 = 23，实为 24）+ R25–R28。**不触发重跑**（口径未变，C-021 仍有效） |
| **v4** | 2026-10-25 W5b | **§1.1 三栏 exam 预注册**：headline = 合并 25（boundary 6 + extrap 13 + interp 6）、三栏明细并列、R12 分母 = 25；新增 `exam_stratum` 字段约定；**判分细则未动** | 老王拍板「扩卷路径 A + headline 全 exam 25」；发现「headline=boundary+extrap 恒为 19」与 R12 的 n≥20 互斥，必须显式取舍 |
| **v4.1** | 2026-10-25 W5b-3 | **仍无判分口径改动**：§1 表拆成 11 / 19 / 25 三行；§6 负控 28→**31**（NC-27..29）；新增 R29 语义计数 / R30 跨口径不可比 / R31 生成前预检。**C-021 与 C-027 均不需重跑** | 专家第七轮 P1-1..P1-6（5 处语义计数漂移 + `check_claims` 只做结构检查抓不到） |
| **v4.2** | 2026-10-25 W5b-3b | §1.1 内插名额由「按族 2/2/1/1」改为「全翼盒 6」（v6 → v6b）：原名额把 barrel/open_hole/panel 三族 train 抽空 ⇒ T1 地板只有 1/4 族可算。**exam 仍 25、判分口径零改动** | 老王拍板 A；实测 `_probe_interp_w5b3b.py` + `trivial_baselines` v6b（T1 0/25、四族齐全） |
| **v4.3** | 2026-10-25 W5b-4 | ①新增红线 **R32**（考卷构建期必须断言 gold 的每个判分字段都能从 NL 推出，否则属不可解题、不得进 exam）；②新增 §1.1.1 登记 v6b 实测三栏（boundary 5/6、extrap 7/13、interp 5/6）+ 难度方向性偏差声明；③**判分细则仍零改动** | W5b-4 探针实证：`stringer_flange_width` gold 有值但题面未给 ⇒ 模型无解却被判 fail（2 条 exam）；`open_hole_panel` 4/4 全败于 prompt 未给键名 |
| **v4.4** | 2026-10-25 W5c 修复轮 | R33–R40 八条新红线；§7 契约登记表 + §7.2 死字段（`blade` 无缘条宽）；§1.1.1 归因细化（A/C 混合，web1_offcentre 补列）；负控 31 → **39**（NC-30..37）；语义检查 21 → **29** 项（S-21..S-28 + 复活的 S-19/S-20 由「静默消失」改为响亮失败） | 第八轮复评 24/30；`r32_audit.py` 4→0 违规、T1 leave-one-out（train 12/13 全是自命中）、成绩单文案由考卷生成 |
| **v5.7** | 2026-10-28 T-A10b | 新增 **R65**（任务层冻结件不得漂移：当前卷==磁盘、已发布 NL 行未改写、跨版只许加行）；**S-52** / **NC-55 三向**（三向各自成为唯一失败项）；新增 **C-037**（v7 考卷冻结，**exam_legacy 25 / exam_full 34** 双分母）；处置 N-19（v1.1 元数据并入 `EXEC_CONFIG_KEYS`，4 键只在新增 9 条出现 ⇒ 不改历史数字）；负控 56→**57**、语义 52→**53**、claim 28→**29**、artifact 54→**58**；旧负控 `_56` 归档，根目录只留 `_57` |
| **v6.6** | 2026-10-30 T-P1a | 新增 **R71**（判分元数据只许修事实错误 + 修正表 `from` 必须等于卷现值 + 必须记进 provenance）+ **S-59** + **NC-65 五向**；修 `L3_naca4412_wingbox` 的错族键登记（`n_stringers_per_skin` → `n_stringers`，走修正表不动卷）；over-clarify 政策预注册（不判 FAIL、`per_task.n_questions` 只观测）；负控 66→**67**。**数字变动仅 1 条**：ds legacy exam 22/25→**23/25**、exam_full 31/34→**32/34**，2×2 → both 23 / 0 / 0 / 2；glm 与两模型 MSR、L2 全部不变 | P-1 拍板 A；`_audit_clarify_meta.py`（W5c-6d）第 ① 条的旧账收口 |
| **v5.8** | 2026-10-28 T-A10c | 新增 **R66**（判据失效子集必须隔离并双报：不得改题掩盖、不得算进单一数字、分母不等禁止相减）；**S-53** / **NC-56 四向**（缺一块 / 掩码过期 / 允许相减 / 只报一侧分，四向各自成为唯一失败项）；新增 **C-038**（`clarify_all 64` ／ `clarify_informative 45` ／ invalid 19，`status=not_run`）；新增 `report_l2_clarify.py` → `reports/l2_clarify_dual.{json,md}`；**更正**上版「C-032 clarify 被 19 条污染」的错判（C-032 分母是 L3 的 4 条）；负控 57→**58**、语义 53→**54**、claim 29→**30**、artifact 58→**60**；旧负控 `_57` 归档，根目录只留 `_58` |
| **v6.5** | 2026-10-30 T-A13d | 新增 **R70**（判据字符串匹配必须有边界）+ **S-58** + **NC-64 六向**；`judge_clarify_field_level` 两处裸子串改走 `_alias_hit`（ASCII 按 token 边界、中文仍按子串）；**N-28 定性更正为「旧账」（W5c-6d 已记假红侧，本轮补假通过侧）**；三路判据 104 条文本 0 变化 + 四份成绩单逐叶子零差异（无 allow 项）⇒ **对外数字零变动** |
| **v6.4** | 2026-10-30 T-A13c | L2 clarify **第二模型 ds**（同卷同 prompt 同呈现，64/64）：`clarify_all` **36/64 (56.2%)** ／ `clarify_informative` **21/45 (46.7%)** ／ `invalid` **15/19**；`report_l2_clarify.py` 支持多模型并列（`by_model`）+ S-53 (e) 逐块断言 + **NC-63 五向**；**N-27 拍板 (a) 落地**，且 ds 在泄漏 19 条上掉 4 条（掉的都不是走追问路径）⇒ **「泄漏 ⇒ 必然全对」被证伪**；新增 **N-28**（判据裸子串的潜伏假通过通道：`n_stringers`/`thickness`/`width`，本轮 0 条触发、数字不假，加固另立项）。**判据一行未改、L3 零改动** |
| **v6.3** | 2026-10-30 T-A13b | L2 clarify **首次跑分**（glm，64/64）：`clarify_all` **49/64 (76.6%)** ／ `clarify_informative` **30/45 (66.7%)** ／ `invalid` **19/19**；`status=scored` ⇒ S-53 加严生效；新增 **C-041**（supporting）+ **N-27**（双口径的差主要是族构成差：15 条失败全在翼盒、非翼盒三族全对），并把该边界写进 R66。**没改判据、没遮 name、L3 零改动** |
| **v6.2** | 2026-10-30 T-A13a | L2 clarify 首次可跑的链路：`SYS_L2 = SYS + 追加段`（**`SYS` 未动**，L3 prompt sha 仍 `ce225186…`；L2 sha `03129c56…`）+ `--mask-name`（遮 `spec.name`，候选记 `presentation`）+ `score_l2.py`（判据/掩码各自 import，不复制）+ `report_l2_clarify.py --scores`（**不齐 64/64 保持 `not_run`+`partial`**）+ **NC-62 五向**。**只搭链路、没跑模型**：L2 仍 `not_run`，C-038 数字零变化 |
| **v6.1** | 2026-10-30 T-A12a/T-A12b | 新增 **R69**（放宽必须有边界）+ **S-56/NC-59 六向**（协议去硬编码）+ **S-57/NC-60 五向**（R32 两 scope 分口径）；S-54 扩 N-26 总账独立复算 / R52 excl_solver / n_unresolved 同名说明（**NC-61 四向**）；`r32_audit` 加 `paper_sha256` 防过期；`_regress_scorecard` 加 `--allow-removed`（只认精确路径）；**未重跑模型、成绩数字零变化** |
| **v6.0** | 2026-10-29 T-A11b | 新增 **R68**（判失败必须能说出为什么：原因落盘 / 兜底非空串 / 建闸前验字段非空 / 历史不回填但承认不可比）；新增 **S-54**（v7 双分母结构性闸）与 **NC-58 五向**；新增 **C-040**（v7 两模型 64/64；legacy exam glm 23/25·20/22·20/22、ds 22/25·20/21·19/21；exam_full glm 32/34、ds 31/34；四桶 25+9+30=64）；`bootstrap_ci.py` 补 `exam_full` CI；`msr_l3.py` 增 `--only`/`--force` 分批（N-22 环境约束）、`_gate_diag`/`_diag_text` 落结构化失败原因（N-21）、env 退出分母（N-23）、S-55 出口断言；旧负控 `_59` 归档，根目录只留 `_60` |
| **v5.9** | 2026-10-29 T-A11a | 新增 **R67**（改了判分必须证明老数不动：同参数重跑 / 逐叶子比 / 三类差异分别记账 / 工具自身可证伪）；**NC-57 五向**；新增 **C-039**（四桶 25+9+30 == 64、1607 既有叶子 0 变动）；新增 `_paths.py`（跨盘符 relpath 收敛，覆盖 8 脚本）、`_regress_scorecard.py`、`_regress_task_a11a.py` → `reports/diagnostics/task_a11a_regression.md`；`score_baseline.py` / `msr_l3.py` 出 `exam_v11` / `exam_full` 两块并加桶闭合断言；**S-54（四桶闭合闸）未加**（无 v7 成绩单可读，加了是空转）；旧负控 `_58` 归档，根目录只留 `_59` |
| **v5.6** | 2026-10-28 T-A10 | 新增 **R63**（文档不得写死可推导计数，一律「以 §0 实读为准」）/ **R64**（对外数字表必须有分母口径且 == 生成器当前输出）；**S-49**（C-001/2/4/5/036 正文计数 == artifact，锚点缺失判红）/ **S-50**（分母合法性 + 逐字节重生成比对 + source_artifacts 可追溯）/ **S-51**（协议文件不得写死计数）/ **NC-54 十向**（且断言「红的原因对」，防陈旧判据吃掉 (a)(b)）；新增 **C-036**（v1.1 数据层）；负控 55→**56**、语义 49→**52**、claim 27→**28**、artifact 50→**54**；旧的十四份负控全归档，根目录只留 `_56` |
| **v5.5** | 2026-10-28 T-A9 | 新增 **R62**（claim 正文计数 == artifact 计数；sha 只证「文件没被换」不证「数字对」）；**S-48**（三计数逐项相等 + 加和闭合 + 构成闭合 + 分母对齐，锚点缺失判红）/ **NC-53 四向**；负控 54→**55**、语义 48→**49**；修 C-003 从 34/15/6 漂到 39/18/7 无闸的漏洞（N-10） |
| **v5.4** | 2026-10-27 T-A5 | 新增 **R61**（求解串行硬约束：`solver.run()` 加全局锁 `.solve.lock`；超 1 h 自动接管）；**S-47**（机制在场 + 无残留锁）/ **NC-52 两向**；负控 53→**54**、语义 47→**48**；修 `check_forms.py` `DEFAULT_REFERENCE`（`outputs_str/…` 不存在 ⇒ T5 恒 FAIL）并让 `_reference_spec` 同时认 `<dir>/spec.json`；旧负控 `_51` 归档 |
| **v5.3** | 2026-10-27 T-A4 | 新增 **R59**（收口顺序固定）/ **R60**（dataset 用 venv）；**S-45**（C-019 记录 mtime == 实际 + 文件时间顺序）/ **S-46**（INDEX bash 块 `PY=` 指向 venv、dataset 调用走 `$PY`）/ **NC-50 两向** / **NC-51 两向**；负控 51→**53**、语义 45→**47**；**F-1**：负控内容不变不重写 json；旧负控 `_50` 归档 |
| **v5.2** | 2026-10-27 T-A3 | 新增 **R58**（官方导航必须被 gate 读）；**S-44**（INDEX 的 headline 指向唯一 + 负控编号/总数与最新 `negative_controls_<N>.json` 实读对齐，均只认结构化记号）/ **NC-49 四向**（⓪ 段指回 C-029 / NC 区间回退 / 去掉历史标记 / 锚点缺失）；负控 50→**51**；语义项 44→**45**；`check_claims.py` 增 `index_consistency` / `_latest_nc_json`；旧负控 `_48`、`_49` 归档 |
| **v5.1** | 2026-10-27 W5d-1 | **R57 扩写**（prompt 变更必须消融留档、净收益 ≤0 否决、否决后 sha 回基线）；**S-43**（消融结论 vs 当前 prompt sha 必须一致）/ **NC-48**（采纳但未换 / 采纳且已换合法 / 缺 decision）；负控 49→**50**；新产物 `diagnostics/prompt_v3_ablation.{json,md}`（C-035）+ `_diag_prompt_ablation.py`；旧负控 `_49` 归档 |
| **v5.0** | 2026-10-27 W5d | 新增 **R55**（prompt 修复逐题回归 + 闭合断言）/ **R56**（榜单三列并排、分母不等不出 Δ）/ **R57**（prompt v3 不得注入 `expected_clarifications`）；**S-41**（dev 反向必须定位且 CLAIMS 引用）/ **S-42**（三列齐 + `msr_delta_allowed` 必须由分母算）；**NC-47**（四向变异）；负控 48→**49**；新产物 `w5d_leaderboard.{json,md}`（C-034）与 `diagnostics/dev_reversal_v6c_p2.{json,md}`；`_diag_dev_reversal.py`（新）/ `make_w5d_leaderboard.py`（新）；旧负控 `{31,37,39,41,44,47}` 归档到 `reports/archive/` |
| **v4.9** | 2026-10-26 W5c-6h | 新增 **R54**（MSR 条件通过率：口径落盘 + 排除项点名 + 分母不同禁止直减/排名）；**S-40** / **NC-46**（三向变异：删口径 / 只改小分母不点名 / 点名清空）；负控 47→**48**；`msr_l3.py` 增 `msr_definition` 与 `n_no_spec_excluded_ids` 并在打印时提示条件分母；`_diag_model_diff.py` 增「§0 MSR 口径对齐」段，分母不等时明确写「不出 Δ」；`compare_scorecards.comparability` 放行**自比**（R53 误伤，NC-29/NC-35 曾因此转红） |
| **v4.8** | 2026-10-26 W5c-6d/6f/6g | 新增 **R50**（prompt 不得盲填、不得注入 `expected_clarifications`）/ **R51**（顶层 `model` == `provenance.model`，读实测值）/ **R52**（MSR 分母四类拆开 + 两层闭合，**修正专家原稿把 solver 加两次的写法**）/ **R53**（改 harness 后所有被比较的模型必须重跑，不得混两代 prompt）+ **§7.7**；S-36/S-37/S-38；负控 44→**47**；`gen_candidates_v2.js` 删「未提长桁→长桁数=0」授权、增「数量类字段铁律」与 `--only` 冒烟口；`score_baseline.py` 顶层 `model` 改读候选文件；`msr_l3.py` 增 `denominator_audit` / `exam_denominator_audit` 且不闭合即退出 |
| **v4.7** | 2026-10-25 W5c-6c 跨模型轮 | 新增 **R47**（比率分母必须显式落盘、加和闭合）/ **R48**（第二模型只作可重复性证据，不得事后择优）/ **R49**（value_added 双尺度结论相反必须标 `verdict_split`）+ **§7.6**；S-33/S-34/S-35；`score_baseline.py` 修口径 bug：字段级命中率旧版用 `if r.get('n_fields_gated')` 隐式过滤，把 `fabricated`/`clarify_wrong` 当成「不存在」⇒ C-029 与 C-031 算出同一个 99.34%（C-031 实为 87.42%）|
| **v4.6** | 2026-10-25 W5c-6b 收口轮 | 新增 **R42–R46** 五条治理红线 + **§7.5 治理闸表**；S-29（headline 唯一，**只认状态列自指标记**——按正文判会被 C-029 自己的否定词过滤）/ S-30（dev 投影不冒充实测）/ S-31（MSR 九字段齐 + 别名一致）；`value_added` 增**字段级**尺度（地板 85.93% → LLM 99.34%，Δ+13.4 pp）与 **T1+ family-mode** 地板（含 `n_fail_exam` 缺口分布）；§6 负控 37→**41** 条计数（含新增 NC-38/NC-39）；`evaluate.py` 增 `n_fields_gated`（剔除恒 pass 的只报不判项，否则命中率口径不可比） |
| **v4.5** | 2026-10-25 W5c 重打分轮 | 新增 **R41 数值角色**（+ §7.3）+ §7.4 契约试建闸边界（gold 55/55 可建）；R33 改**两端口径**（exam 0 违规 + 非 exam 白名单逐字相等）；R32 局限补第二处「数值出现 ≠ 字段角色可判」；**§4 / R35 补四行口径**（`exam_msr` 与 `exam_msr_excl_solver` 并列，原注释「exam MSR 不含 solver」与实现相反）+ 修顶层 `msr` 一直为 null（NC-36 抓到） | v6c 自查发现 `stiffened_panel_800x600`/`_str3` 旧模板 `{width} × {length}` 使题面「600 × 800」与 gold `length=800` 角色相反 ⇒ 模型正确读法被判错（2 条 dev，0 条 exam） |
