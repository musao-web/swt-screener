# swt-screener — InterExchange Work & Travel 岗位筛选器

![GitHub Repo stars](https://img.shields.io/github/stars/musao-web/swt-screener?style=flat)

一个 Claude Code skill：按**你自己设定的标准**给 InterExchange (IE) Work & Travel 岗位分档筛选，产出带判定理由、雇主联系方式、求职邮件草稿和 IE 深链的 HTML 报告，并按你的个人档案为每个雇主个性化求职邮件。

> ⭐ 用得上就顺手点个 star，是对开源项目最好的支持！

- **A 优先 / B 权衡 / C 红线 / X 排除** 四档，每个岗位都写明「为什么进这档」
- **3D 岗位墙**展示可考虑岗位（点卡片看理由、联系方式和邮件草稿），排除岗一目了然的表格
- **历轮筛查记录表自动更新**：每次筛查记入历史（`history.py`），报告末尾的历轮表自动累积日期/新核查/分档/陷阱/备注；已核查过的卡自动标记「沿用」，**只筛新卡**
- **记忆模块**：个人档案问答一次、永久复用，之后每次筛查直接出结果
- **陷阱警戒**：IE 列表页卡片标题常与详情页实岗不符（案例持续沉淀），推荐前必须核对详情页 Position Description 首句

## 在线演示

- **产品首页**（本仓库根 `index.html`，GitHub Pages 托管后即线上访问）：产品介绍 + 技术亮点 + 合规说明
- **工作台**（`webapp/index.html`）：点「🎬 直接加载演示数据」即可在线体验岗位墙 / 历轮表 / 排除表 / 邮件草稿，无需任何文件
- 用自己的数据：设置页点选口径 → 导出 `config.yaml` / `profile.yaml` → 跑管线 → 把结果 JSON 拖回工作台

## 架构

```
IE 详情页数据(手动采集)
   │
   ▼
run.py（一键：分档 → 记历轮 → 出报告，自动打开）
   │  ├─ screen.py ──── config.yaml(个人口径) + knowledge/(岗位映射/城镇/陷阱/联系方式)
   │  │                   判定顺序 X → C → B → A，每岗列出命中理由
   │  └─ screen_result.json ──┬── history.py → screening_history.json(历轮，只筛新卡)
   │                          ▼
   │                   report.py → HTML 报告(统计/岗位墙·清单/X排除表/邮件草稿)
   ▼
mailgen.py + profile.yaml → 邮件底稿 → AI 逐雇主个性化定稿
```

确定性规则（日期/住宿/薪资/红线/陷阱）由代码判定，创造性工作（邮件个性化、知识库维护）由 AI 完成。

## 快速开始

```bash
pip install pyyaml   # Python 3.10+，唯一依赖
```

首次使用先做两轮问答（之后的每次筛查直接跳过，不再重问）：

1. **筛选口径**（写入 `config.yaml`）：到岗窗口、离岗约束、住宿、岗位红线、薪资工时线、地域等，逐维确认，留空 = 该维度不判定。
2. **个人档案**（写入 `profile.yaml`，只问一次）：姓名、联系方式（邮箱/电话/WhatsApp）、学校、专业、到岗日/离岗日、相关工作经历与优势、可选自我介绍视频链接。说「更新我的档案」才会重新收集。

准备好岗位数据后（格式见 `references/input_schema.md`，需登录 IE 抓取详情页），**一条命令出报告**：

```bash
python3 scripts/run.py config.yaml <input.json>
```

自动完成：筛查分档（history.dedup 开启时自动「只筛新卡」：已核查的卡标记沿用）→ 记录本轮（幂等：同日重跑=覆盖该轮）→ 生成 HTML 报告并在浏览器打开（默认 `report_YYYY-MM-DD.html`，也可加第 3 个参数指定输出名）。

- 复盘/补录旧数据：命令末尾加 `--date 2026-11-04`（生成日期与报告名都用该日期）
- 测试/CI：加 `--no-open` 不自动打开浏览器
- 调试时也可逐步手动跑：`screen.py`（分档）→ `history.py record`（记历轮）→ `report.py`（出报告）

报告里的邮件是**底稿**。挑中岗位后，让 Claude 用档案记忆为每个雇主定稿（加 1–2 句针对性内容，正文 ≤ `email.max_words` 词）。正式申请仍走 IE 站内 Apply。

## 分档体系

| 档 | 含义 | 处理 |
|---|---|---|
| A | 优先 | 全部通过，按 `tiering.sort_by` 排序（时薪 → 工时 → 租金） |
| B | 权衡 | 有条件标注：需提前到岗 / 时薪或工时低于线 / 3 人间 / 卡片实岗不符 / 住房危机镇无住宿信息等 |
| C | 红线 | 不推荐（如 Hospitality Crew 综合酒店岗轮岗） |
| X | 排除 | 命中任一硬红线：到岗/离岗日期不满足、红线岗位、4 人+/间、孤岛镇、实岗为排除类 |

判定顺序 X → C → B → A：任何一条 X 理由即整岗 X（顺序可在 `tiering.order` 改）。

## 筛选维度

全部在 `config.yaml` 参数化（注释即说明），**无内置默认口径**——每个维度由你自己填写，留空 = 不判定：

| 维度 | 配置项 | 说明 |
|---|---|---|
| 活跃度 | `season_year` | 雇主 Last Visited 必须在本季年份，否则是僵尸岗 |
| 到岗 | `arrival` | 到岗窗口结束日 ≥ 计划到岗日 → OK；早于计划日但 ≥ 最早可接受日 → 需提前到岗（B）；更早或冬季岗 → 排除 |
| 离岗 | `departure` | Finish 窗口起始日 ≤ 最晚必须离岗日；延到下一年的排除 |
| 住宿 | `housing` | 可接受人数上限 / 标注线 / 排除线 / 周租金线 / 住房危机镇须雇主住宿 |
| 岗位红线 | `redline` | 不想做的岗位关键词（命中卡片标题或详情页职责文本 → 排除 X / 红线 C） |
| 薪资工时 | `wage_hours` | 时薪 / 周工时低于自设线 → 标注 B |
| 地域 | `regions` | 白/黑名单、偏好州（只影响排序）、孤岛镇一刀切 |
| 陷阱检测 | `traps` | 详情页 Position Description 首句判定实岗，卡片标题对不上即标注 |

## 历轮记录与只筛新卡

- `config.history.file` 存历轮 JSON（`history.py` 维护）。每轮记录：日期、新核查卡数、沿用卡数、A/B/C/X 计数、全部新卡 slug、陷阱新增数（含排除向）、备注。
- HTML 报告末尾的「历轮筛查记录」表自动读取该文件渲染，新轮次跑完表自动多一行；陷阱累计数从 `knowledge/traps.md` 头部解析（单源，不重复维护）。
- `history.dedup: true` 时 `screen.py` 用历轮 slug 自动标记已核查卡为「沿用」——只筛新卡，例行筛查不用再手工比对快照。
- 知识库维护后补写本轮要点：

```bash
python3 scripts/history.py update config.yaml 2026-11-04 --traps-added 18 --traps-exclude 9 --note "重点备注"
```

## 记忆模块

- `profile.yaml` — 你的个人档案（姓名/联系方式/日期/经历优势），首次问答收集后**自动复用**，之后每次筛查和每封邮件都自动引用，不再重问
- `knowledge/` — 共同知识库：岗位映射（`position_map.yaml`）、城镇库（`towns.yaml`）、雇主联系方式（`contacts.yaml`）、陷阱案例（`traps.md`）
- 邮件工作流：`mailgen.py` 按档案 + 模板确定性生成底稿 → 发送前 AI 逐雇主个性化定稿（按 `email.no_questions` / `include_contact` / `closing_line` / `max_words` 口径）

## 文件地图

```
swt-screener/
├── SKILL.md                  # skill 定义与完整工作流
├── README.md                 # 本文件
├── index.html                # 产品首页（landing page，链接工作台与仓库）
├── profile.yaml              # 记忆模块：你的个人档案（首次问答后自动复用；已 gitignore，模板起步）
├── config.yaml               # 全部筛选口径（阈值 + 报告/邮件选项；已 gitignore，模板起步）
├── assets/
│   └── email_template.md     # 求职邮件模板（简约底稿）
├── scripts/
│   ├── run.py                # 一键管线（screen → history → report，自动打开报告）
│   ├── screen.py             # 分档核心（读 config + knowledge → 结果 JSON；只筛新卡）
│   ├── report.py             # HTML 报告（历轮记录表 / 3D 岗位墙 / 联系方式 / 邮件草稿 / 深链）
│   ├── mailgen.py            # 邮件底稿填充（读 profile.yaml + 模板）
│   ├── history.py            # 历轮筛查历史（record 幂等追加 / update 补陷阱数与备注 / list）
│   └── build_site_data.py    # knowledge/ → webapp/data.js（改了知识库后重跑）
├── knowledge/                # 共同知识库（岗位映射 / 城镇 / 陷阱 / 联系方式）
├── webapp/                   # 工作台网页：设置表单（导出 yaml）+ 报告渲染（拖入结果 JSON 在线看）
│   └── demo/                 # 演示数据（中性口径跑出的示例结果 + 示例历轮），工作台「加载演示数据」用
└── references/
    └── input_schema.md       # 岗位数据输入格式
```

## 自定义

skill 不硬编码任何个人口径：换人使用时，替换 `profile.yaml`（档案）和 `config.yaml`（口径）即可，代码零改动。`knowledge/` 里的陷阱库、城镇库、联系方式库属于长期沉淀，建议随使用持续追加（SKILL.md 第 5 步）。

## 隐私提醒

`profile.yaml` 含真实个人信息（姓名、邮箱、学校等）。上传到公开仓库前，请替换为占位符示例。

## 局限

- 岗位数据需登录 IE（app.interexchange.org）后抓取，skill 不做自动登录
- 详情页无雇主联系方式字段，联系方式来自知识库调研积累，未收录时报告会给出渠道建议
- 判定基于已抓取的字段；缺失字段（如到岗窗口未标注）会按「标注 B」处理而不是默认通过
