# -*- coding: utf-8 -*-
"""Generate all figures for the technical design report."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from pathlib import Path

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

OUT = Path(__file__).parent
BLUE = "#1565C0"
DARK = "#0D47A1"
TEAL = "#00897B"
ORANGE = "#E65100"
GRAY = "#64748B"
LIGHT = "#E3F2FD"
LIGHT2 = "#F1F5F9"
WHITE = "#FFFFFF"
INK = "#1A1A1A"
RED = "#B91C1C"

def new_ax(w=13, h=6):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.97, bottom=0.03)
    return fig, ax

def box(ax, x, y, w, h, text, fc=WHITE, ec=BLUE, fs=11, bold=False, tc=INK, lw=1.6, r=1.6, ls="-"):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                       facecolor=fc, edgecolor=ec, linewidth=lw, linestyle=ls)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", color=tc, linespacing=1.5)

def arrow(ax, x1, y1, x2, y2, color=GRAY, lw=1.8, style="-|>", ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                                 mutation_scale=16, color=color, linewidth=lw,
                                 linestyle=ls, connectionstyle=f"arc3,rad={rad}"))

def title(ax, t, sub=None):
    ax.text(50, 95, t, ha="center", va="center", fontsize=14, fontweight="bold", color=INK)
    if sub:
        ax.text(50, 89.5, sub, ha="center", va="center", fontsize=10, color=GRAY)

def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=220, facecolor="white")
    plt.close(fig)

# ---------- 1. 工时分布 ----------
fig, ax = new_ax(13, 5.6)
title(ax, "建模环节的工时分布与可规则化比例")
rows = [("传统人工流程", [("几何简化", 18, "#90CAF9"), ("网格与属性", 32, BLUE),
                        ("载荷边界", 20, "#1E88E5"), ("求解与后处理", 20, "#B0BEC5"), ("报告", 10, "#CFD8DC")]),
        ("智能生成后（目标）", [("规则化劳动→自动", 50, TEAL), ("工程师判断", 15, "#4DB6AC"),
                            ("求解与后处理", 20, "#B0BEC5"), ("报告", 15, "#CFD8DC")])]
for i, (label, segs) in enumerate(rows):
    y = 62 - i * 22
    ax.text(2, y + 5, label, fontsize=11, fontweight="bold", color=INK, va="center")
    x = 28
    for name, v, c in segs:
        ax.add_patch(Rectangle((x, y), v * 0.68, 12, facecolor=c, edgecolor="white", linewidth=1.5))
        tc = "white" if c in (BLUE, TEAL, "#1E88E5") else INK
        ax.text(x + v * 0.525, y + 6, f"{name}\n{v}%", ha="center", va="center",
                fontsize=9, color=tc, linespacing=1.4)
        x += v * 0.68
ax.annotate("约 70% 的建模工时中，过半是可规则化的重复劳动",
            xy=(50, 44), xytext=(50, 24), fontsize=10, color=RED,
            arrowprops=dict(arrowstyle="-|>", color=RED), ha="center")
save(fig, "pain_ratio")

# ---------- 2. 技术谱系 ----------
fig, ax = new_ax(13, 5.4)
title(ax, "结构建模自动化的三代技术谱系")
gens = [("第一代\n参数化 / 模板化", "尺寸驱动几何与网格\n确定性强、可复现", "覆盖窄 · 维护贵 · 门槛高", LIGHT),
        ("第二代\n脚本化流程自动化", "脚本驱动前处理与批处理\n可复现、可批量化", "要求双技能 · 缺语义", "#E8F5E9"),
        ("第三代\n大模型生成式建模", "自然语言 → 结构化意图 → 可执行输入\n交互自然、可编排", "输出不确定 · 需独立验证", "#FFF3E0")]
for i, (h, body, lim, fc) in enumerate(gens):
    x = 3 + i * 32.5
    box(ax, x, 52, 28, 30, "", fc=fc, ec=BLUE if i < 2 else ORANGE, lw=2)
    ax.text(x + 14, 74, h, ha="center", va="center", fontsize=11.5, fontweight="bold",
            color=DARK if i < 2 else ORANGE, linespacing=1.5)
    ax.text(x + 14, 62, body, ha="center", va="center", fontsize=9.5, color=INK, linespacing=1.6)
    ax.text(x + 14, 47, "局限：" + lim, ha="center", va="center", fontsize=9, color=RED)
    if i < 2:
        arrow(ax, x + 28.6, 67, x + 31.8, 67, color=GRAY, lw=2.2)
ax.text(50, 33, "本框架的定位：继承第二代的确定性与可复现，补上第三代的自然交互，并用「契约 + 验证闸」消除第三代的不确定性",
        ha="center", fontsize=10.5, color=DARK, fontweight="bold")
save(fig, "genealogy")

# ---------- 3. 三条技术路线 ----------
fig, ax = new_ax(13, 6.2)
title(ax, "LLM + CAE 的三条主流技术路线")
cols = [("路线一 · 代码/输入卡生成", ["模型直接写输入文件", "路径最短、通用性最好", "", "实测：零提示成功率≈0", "必须配检索与反馈"], BLUE, LIGHT),
        ("路线二 · Agent 编排", ["多角色分工 + 工具调用", "意图→检索→写卡→求解", "→审查→可视化", "实测：有审查≈90%", "无审查≈45%；RAG 内 92.5%"], TEAL, "#E0F2F1"),
        ("路线三 · 评测基准", ["带真值的任务集 + 统一指标", "把「感觉能用」", "变成「可测量」", "实测：跨 39 基准", "最佳代码级成功≈72%"], ORANGE, "#FFF3E0")]
for i, (h, lines, c, fc) in enumerate(cols):
    x = 3 + i * 32.5
    box(ax, x, 22, 28, 60, "", fc=fc, ec=c, lw=2)
    ax.text(x + 14, 75, h, ha="center", va="center", fontsize=11.5, fontweight="bold", color=c)
    ax.text(x + 14, 52, "\n".join(lines), ha="center", va="center", fontsize=9.5, color=INK, linespacing=1.9)
ax.text(50, 12, "共同缺口：只验「能跑」不验「物理对」 · 无形式化契约 · 单求解器无交叉 · 评测不可复现 · 缺退化自检",
        ha="center", fontsize=10, color=RED, fontweight="bold")
save(fig, "three_routes")

# ---------- 4. 三条设计原则 ----------
fig, ax = new_ax(13, 5.6)
title(ax, "三条设计原则与对应解决的工程问题")
prin = [("契约唯一", "FEASpec 是唯一真相源\n输入卡只是投影", "多求解器口径统一\n过程可追溯 · 参数一处校验"),
        ("求解器先于写卡", "契约内声明求解器\n写卡阶段按声明分派", "避免为迁就语法\n而扭曲模型定义"),
        ("闸即标准", "入库闸 = 放行闸\n同一套代码同一组阈值", "训练合格→上线合格\n能力漂移可被察觉")]
for i, (p, mid, eff) in enumerate(prin):
    x = 3 + i * 32.5
    box(ax, x, 66, 28, 18, p, fc=BLUE, ec=DARK, fs=13, bold=True, tc="white")
    arrow(ax, x + 14, 65, x + 14, 55, color=BLUE, lw=2)
    box(ax, x, 34, 28, 20, mid, fc=LIGHT, ec=BLUE, fs=9.5)
    arrow(ax, x + 14, 33, x + 14, 26, color=TEAL, lw=2)
    box(ax, x, 10, 28, 15, eff, fc="#E0F2F1", ec=TEAL, fs=9, tc="#00695C")
save(fig, "principles")

# ---------- 5. 六层架构 ----------
fig, ax = new_ax(13, 7.4)
title(ax, "技术框架六层总体架构")
layers = [("L1 交互层", "工程口语 → 意图（槽位 + 追问 + 越界识别）", "Intent"),
          ("L2 契约层", "规范化 + 三层校验 + 契约指纹", "FEASpec"),
          ("L3 生成层", "建面打标 → 全四边形网格 → 双方言写卡", "几何 / 网格 / 输入卡"),
          ("L4 求解层", "串行调度 + 结果归一（同一网格、同一契约）", "归一化结果"),
          ("L5 验证层", "九道闸判定：网格·语义·平衡·双码·解析解·退化·指纹·回归·自洽", "验证报告"),
          ("L6 应用回流层", "交付 · 失败样本回流 · 能力统计", "交付物 / 样本")]
for i, (h, body, out) in enumerate(layers):
    y = 76 - i * 11.6
    fc = LIGHT if i % 2 == 0 else "#F1F8FF"
    box(ax, 6, y, 66, 9.6, "", fc=fc, ec=BLUE if i < 5 else TEAL, lw=1.8)
    ax.text(9, y + 4.8, h, ha="left", va="center", fontsize=11, fontweight="bold", color=DARK)
    ax.text(26, y + 4.8, body, ha="left", va="center", fontsize=9.2, color=INK)
    ax.text(74.5, y + 4.8, "→ " + out, ha="left", va="center", fontsize=9, color=GRAY)
    if i < 5:
        arrow(ax, 39, y, 39, y - 1.9, color=GRAY)
ax.annotate("", xy=(4.2, 12.5), xytext=(4.2, 85.6),
            arrowprops=dict(arrowstyle="-|>", color=TEAL, lw=2.2))
ax.text(2.0, 49, "单向主链\n禁止跨层", rotation=90, ha="center", va="center",
        fontsize=9, color=TEAL, fontweight="bold", linespacing=1.6)
ax.text(92, 20, "契约哈希\n= 模型指纹", ha="center", fontsize=9, color=DARK,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#FFF8E1", edgecolor="#F9A825"))
save(fig, "arch")

# ---------- 6. 数据流 ----------
fig, ax = new_ax(13, 5.8)
title(ax, "主链数据流与两条反馈回路")
steps = ["语言", "意图", "契约", "几何", "网格", "输入卡", "结果", "验证"]
for i, s in enumerate(steps):
    x = 2 + i * 12.2
    box(ax, x, 55, 10.5, 14, s, fc=LIGHT if i < 4 else "#E0F2F1",
        ec=BLUE if i < 4 else TEAL, fs=10, bold=True)
    if i < len(steps) - 1:
        arrow(ax, x + 10.6, 62, x + 11.9, 62, color=GRAY)
# short loop
arrow(ax, 88, 54, 30, 46, color=ORANGE, lw=2, rad=-0.18, ls="--")
ax.text(58, 47.5, "修复回路（短环）：拒绝 → 归因 → 局部重做，有限次后转人工",
        ha="center", fontsize=9.5, color=ORANGE, fontweight="bold")
# long loop
arrow(ax, 82, 54, 8, 28, color=TEAL, lw=2, rad=-0.2, ls="--")
ax.text(44, 26, "演进回路（长环）：归因为能力缺口 → 样本回流 → 扩充数据与检索库",
        ha="center", fontsize=9.5, color=TEAL, fontweight="bold")
ax.text(50, 10, "短环解决「这次没做好」，长环解决「这类做不了」",
        ha="center", fontsize=10.5, color=INK)
save(fig, "dataflow")

# ---------- 7. 契约模型 ----------
fig, ax = new_ax(13, 5.8)
title(ax, "契约（FEASpec）的七组字段与三条硬规则")
box(ax, 33, 62, 34, 16, "FEASpec\n与求解器无关的分析中间表示", fc=BLUE, ec=DARK, fs=11.5, bold=True, tc="white")
groups = [("元信息", "名称/族/版本/时间"), ("结构", "族 + 族参数"), ("网格", "尺寸/加密/阈值"),
          ("材料", "本构 + 参数"), ("载荷", "类型/区域/量值"), ("边界", "约束/区域"), ("求解", "后端/分析型/输出")]
for i, (g, d) in enumerate(groups):
    x = 2 + i * 14.0
    box(ax, x, 34, 12.8, 16, f"{g}\n{d}", fc=LIGHT, ec=BLUE, fs=8.6)
    arrow(ax, x + 6.4, 51, min(max(50, x + 6.4), 66), 61, color="#90CAF9", lw=1.2)
rules = ["① 不可变：一经生成即冻结，修改 = 新版本 + 新哈希",
         "② 自包含：不含外部引用，单文件即可重建模型",
         "③ 双真相校验：同一物理量两处出现必须严格一致，否则拒绝"]
ax.text(50, 22, "\n".join(rules), ha="center", va="center", fontsize=9.8,
        color=INK, linespacing=1.9,
        bbox=dict(boxstyle="round,pad=0.6", facecolor="#FFF8E1", edgecolor="#F9A825"))
save(fig, "contract")

# ---------- 8. 三维扩展 ----------
fig, ax = new_ax(13, 5.4)
title(ax, "三个正交扩展维度与注册点")
axes3 = [("结构族维", "新增族 = 参数→几何+打标\n构建器注册", "语义校验随族注册", BLUE, LIGHT),
         ("材料维", "新增本构 = 参数→材料卡\n映射注册", "验证按本构选判据", TEAL, "#E0F2F1"),
         ("求解器维", "新增后端 = 写卡 + 结果归一\n适配器注册", "双码比对自动扩展", ORANGE, "#FFF3E0")]
for i, (h, m, e, c, fc) in enumerate(axes3):
    x = 5 + i * 31
    box(ax, x, 46, 27, 30, "", fc=fc, ec=c, lw=2)
    ax.text(x + 13.5, 68, h, ha="center", fontsize=12.5, fontweight="bold", color=c)
    ax.text(x + 13.5, 56, m, ha="center", va="center", fontsize=9.3, color=INK, linespacing=1.7)
    ax.text(x + 13.5, 41, e, ha="center", fontsize=9, color=GRAY)
box(ax, 27, 16, 46, 12, "统一入口：注册表 + 退化自检（新能力不得牺牲既有能力）",
    fc="#FFF8E1", ec="#F9A825", fs=10, tc=INK)
for i in range(3):
    arrow(ax, 18 + i * 31, 45, 46 + i * 3, 29, color=GRAY)
save(fig, "extension")

# ---------- 9. 九道闸 ----------
fig, ax = new_ax(13, 6.2)
title(ax, "九道验证闸的串联关系与拦截目标")
gates = [("G1 网格质量", "畸形单元"), ("G2 语义一致", "建面与契约不符"), ("G3 载荷平衡", "漏加/重复/方向错"),
         ("G4 双码一致", "方言适配错误"), ("G5 解析解对标", "物理建模错误"), ("G6 退化自检", "新功能破坏旧能力"),
         ("G7 去重指纹", "重复模型"), ("G8 回归基线", "未声明漂移"), ("G9 契约自洽", "参数内部矛盾")]
for i, (g, t) in enumerate(gates):
    r, c = divmod(i, 3)
    x = 6 + c * 31
    y = 62 - r * 18
    box(ax, x, y, 28, 13, "", fc=LIGHT if r < 2 else "#FFF3E0",
        ec=BLUE if r < 2 else ORANGE, lw=1.8)
    ax.text(x + 14, y + 8.6, g, ha="center", fontsize=11, fontweight="bold", color=DARK)
    ax.text(x + 14, y + 4.0, "拦截：" + t, ha="center", fontsize=8.8, color=RED)
    if c < 2:
        arrow(ax, x + 28.3, y + 6.5, x + 30.9, y + 6.5, color=GRAY)
ax.text(50, 6, "任一闸拒绝 → 整体不通过；阈值来自实测收敛链，任何改动须留档并重签基线",
        ha="center", fontsize=9.8, color=DARK, fontweight="bold")
save(fig, "gates")

# ---------- 10. 时序 ----------
fig, ax = new_ax(13, 7.2)
title(ax, "端到端生成与验证时序")
lanes = [("工程师", 12), ("框架", 34), ("验证层", 58), ("求解器", 80)]
for name, x in lanes:
    box(ax, x - 8, 82, 16, 7, name, fc=BLUE, ec=DARK, fs=10, bold=True, tc="white")
    ax.plot([x, x], [82, 8], color="#CBD5E1", lw=1.2, ls="--")
seq = [(12, 34, 74, "① 口语描述结构与工况"),
       (34, 12, 68, "② 缺壁厚，追问一次"),
       (12, 34, 62, "③ 补充参数"),
       (34, 34, 57, "④ 契约规范化 + 三层校验"),
       (34, 34, 52, "⑤ 建面打标 + 网格 + 质量统计"),
       (34, 80, 47, "⑥ 双方言写卡 → 串行求解"),
       (80, 34, 42, "⑦ 归一化结果"),
       (34, 58, 37, "⑧ 九道闸判定"),
       (58, 34, 32, "⑨ 全部通过 / 拒绝并归因"),
       (34, 12, 25, "⑩ 模型 + 云图 + 报告 + 契约指纹"),
       (58, 34, 17, "11) 拒绝时：修复回路，超限转人工")]
for x1, x2, y, label in seq:
    if x1 == x2:
        ax.text(x1 + 1.5, y, label, ha="left", va="center", fontsize=8.8, color=INK)
        ax.add_patch(Rectangle((x1 - 0.6, y - 0.9), 1.2, 1.8, color=BLUE))
    else:
        arrow(ax, x1, y, x2, y, color=BLUE if x2 > x1 else TEAL, lw=1.5)
        ax.text((x1 + x2) / 2, y + 1.6, label, ha="center", fontsize=8.6, color=INK)
save(fig, "sequence")

# ---------- 11. 部署形态 ----------
fig, ax = new_ax(13, 5.6)
title(ax, "两种部署形态共用同一套核心库")
box(ax, 4, 22, 42, 62, "", fc="#F8FAFC", ec=BLUE, lw=2)
ax.text(25, 78, "形态一 · 单机批处理", ha="center", fontsize=12, fontweight="bold", color=DARK)
ax.text(25, 62, "契约清单\n→\n串行生成 / 求解 / 验证\n→\n结果目录 + 报告",
        ha="center", va="center", fontsize=10, color=INK, linespacing=1.7)
ax.text(25, 30, "适用：批量算例、回归测试", ha="center", fontsize=9.2, color=GRAY)
box(ax, 54, 22, 42, 62, "", fc="#F8FAFC", ec=TEAL, lw=2)
ax.text(75, 78, "形态二 · 服务化", ha="center", fontsize=12, fontweight="bold", color=TEAL)
ax.text(75, 62, "前端（语言请求）\n→ API → 任务队列\n→ 求解器资源池\n→ 模型 / 云图 / 报告",
        ha="center", va="center", fontsize=10, color=INK, linespacing=1.7)
ax.text(75, 30, "适用：交互式使用；许可串行调度，队列可见", ha="center", fontsize=9.2, color=GRAY)
ax.text(50, 12, "共同约束：数据不出域 · 中间产物全部落盘 · 支持断点重跑",
        ha="center", fontsize=9.8, color=DARK, fontweight="bold")
save(fig, "deployment")

# ---------- 12. 能力边界 ----------
fig, ax = new_ax(13, 5.6)
title(ax, "能力边界：显式声明，不做静默降级")
box(ax, 4, 20, 44, 60, "", fc="#E8F5E9", ec=TEAL, lw=2)
ax.text(26, 74, "当前覆盖", ha="center", fontsize=12, fontweight="bold", color="#00695C")
ax.text(26, 52, "线性静力\n壳 / 梁 / 杆单元\n金属 + 等效正交异性复材\n典型飞机结构形式参数化族\n多工况线性组合",
        ha="center", va="center", fontsize=10, color=INK, linespacing=1.9)
box(ax, 52, 20, 44, 60, "", fc="#FFF3E0", ec=ORANGE, lw=2)
ax.text(74, 74, "暂不支持", ha="center", fontsize=12, fontweight="bold", color=ORANGE)
ax.text(74, 52, "接触与装配连接\n几何 / 材料非线性\n屈曲 · 瞬态 · 模态\n气动弹性与多物理场\n静默降级",
        ha="center", va="center", fontsize=10, color=INK, linespacing=1.9)
ax.text(50, 12, "边界外请求：显式拒绝 + 原因 + 当前范围 + 替代路径",
        ha="center", fontsize=9.8, color=RED, fontweight="bold")
save(fig, "boundary")

# ---------- 13. 结论 ----------
fig, ax = new_ax(13, 5.4)
title(ax, "三条核心判断与演进路径")
jud = [("约束优于提示", "形式化契约限定生成空间\n而不是要求模型「别编」"),
       ("验证必须独立", "几何实测 · 守恒律 · 解析解\n双求解器互证"),
       ("标准必须同源", "入库闸 = 放行闸\n同代码 · 同阈值 · 同版本")]
for i, (h, d) in enumerate(jud):
    x = 4 + i * 32
    box(ax, x, 52, 28, 26, "", fc=LIGHT, ec=BLUE, lw=1.8)
    ax.text(x + 14, 69, h, ha="center", fontsize=12, fontweight="bold", color=DARK)
    ax.text(x + 14, 58, d, ha="center", va="center", fontsize=9, color=INK, linespacing=1.7)
ax.annotate("", xy=(94, 30), xytext=(6, 30), arrowprops=dict(arrowstyle="-|>", color=TEAL, lw=2.4))
stages = ["现有能力\n（线性静力·典型族）", "扩展一\n材料维深化", "扩展二\n结构族扩展", "扩展三\n求解器与流程"]
for i, s in enumerate(stages):
    ax.text(12 + i * 24, 36, s, ha="center", va="bottom", fontsize=9, color="#00695C", linespacing=1.6)
    ax.plot([12 + i * 24], [30], marker="o", color=TEAL, markersize=8)
ax.text(50, 14, "每次扩展前置条件：退化自检通过（新能力不得以牺牲既有能力为代价）",
        ha="center", fontsize=9.8, color=RED)
save(fig, "closing")

print("figures done:", len(list(OUT.glob("*.png"))))
