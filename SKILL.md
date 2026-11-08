---
name: swt-screener
description: 帮助 InterExchange (IE) Work & Travel 学生按自设标准筛选岗位：把岗位分档（A 优先 / B 标注 / C 红线 / X 排除），生成带判定理由、雇主联系方式、求职邮件草稿和 IE 深链的 HTML 报告，并按用户档案为每个雇主个性化求职邮件。当用户提到 SWT / Work & Travel / InterExchange 选岗、筛选美国 J-1 打工岗位、把岗位分档、要雇主联系邮件或岗位报告时使用——即使用户没提 skill 字样。
---

# SWT 岗位筛选器

按**用户自设的标准**给 IE Work & Travel 岗位分档，产出 HTML 报告（每岗：判定理由 + 联系方式 + 求职邮件草稿 + 深链），并用用户档案为每个雇主打造个性化求职邮件。

## 核心原则

- **一切标准参数化**：筛选口径全部来自 `config.yaml`；用户个人信息（姓名/联系方式/到岗离岗/经历优势）在 `profile.yaml`。skill 不硬编码任何个人口径。
- **记忆模块**：`profile.yaml` 是用户档案记忆——首次问答收集后持久复用，之后每次筛查自动读取，不再重问。`knowledge/` 是共同知识库（岗位映射 / 城镇 / 陷阱 / 联系方式）。
- **判定必须给理由**：每个岗位都要列出命中了哪条规则，用户要能看懂「为什么进这档」。
- **每轮必须产出并自动弹出 HTML 报告**：筛查结束的默认交付物是 `run.py` 生成的 HTML 报告（岗位墙/判定理由/邮件草稿），由 `run.py` 自动在浏览器打开（`--no-open` 仅限测试/CI）。如果用户还沿用 docx 清单工作流，docx 只能是 HTML 报告**之外**的附加产物，绝不能替代 HTML 报告。用户没看到报告页 = 本轮没结束，不得跳过。
- **陷阱警戒**：IE 列表页卡片标题常与详情页实岗不符（案例持续沉淀）。任何岗位在推荐或申请前，必须核对详情页 Position Description 首句。

## 工作流

### 1. 首次使用：安装 + 设置口径与档案（全部由用户自设，无任何默认口径）

安装 skill 后（如 `~/.claude/skills/swt-screener/`），从模板起步：`cp config.template.yaml config.yaml`、`cp profile.template.yaml profile.yaml`。
**所有筛选口径必须由用户自己设置**，skill 不提供任何「默认口径」；空值 = 该维度不启用，screen.py 自动跳过。

**推荐路径：工作台网页表单**（`webapp/index.html`，浏览器直接打开）：
- 口径页：逐维点选（不想做的岗位关键词、住宿预设档位、薪资工时线、地域州名点选、邮件选项开关），少打字
- 档案页：姓名/联系方式/学校专业/到岗离岗日期（日期选择器）/经历优势
- 填完一键导出 `profile.yaml` / `config.yaml`，放进 skill 根目录即可

**备选路径：终端问答**（全部自设）：
- 口径（写入 `config.yaml`，逐维提问，跳过 = 不启用该维度）：
  - 出发年份（活跃度判定）
  - 到岗：计划到岗日、最早可接受到岗日（直接设日期，映射 arrival 两条线）、是否排除冬季岗
  - 离岗：最晚必须离岗日、是否排除延到下一年的岗
  - 住宿：可接受几人/间、标注线、排除线、周租金线、住房危机镇是否必须雇主住宿
  - 岗位红线：不想做的岗位关键词（命中标题或详情职责 → 排除 X / 红线 C，可参考 IE 偏好页勾选情况）
  - 薪资工时线：最低时薪、最低周工时
  - 地域：白名单 / 黑名单 / 偏好州 / 是否排除孤岛镇
  - 报告与邮件选项
- 档案（写入 `profile.yaml`，只问一次）：姓名 / 联系方式（邮箱、电话、WhatsApp 可选）/ 学校 / 专业 / 到岗日 / 离岗日（硬约束）/ 相关工作经历与优势（逐条，邮件会引用）/ 可选自我介绍视频链接（项目方固定 InterExchange，不用问）

之后每次使用直接进入第 2 步，不再问档案。用户说「更新我的档案」才重新收集；也可以直接编辑两个 yaml 或回网页表单改后重新导出。

### 2. 准备数据

详情页数据文件，格式见 `references/input_schema.md`。没有现成数据时，用浏览器登录 IE 后抓取（列表页卡片 + 每个候选岗详情页），关键字段是 `posdesc` 首句、start/finish 窗口、share/rent。

### 3. 一条命令出报告

```bash
python3 scripts/run.py config.yaml <input.json>
```

自动完成三步：分档筛查（**只筛新卡**：已核查的卡自动标记「沿用」，不再重复筛）→ 记录本轮历轮（幂等，同日重跑=覆盖该轮）→ 生成 HTML 报告并在浏览器打开。默认报告名 `report_YYYY-MM-DD.html`（输出到当前目录），也可加第 3 个参数指定输出名。

- 复盘/补录旧数据：命令末尾加 `--date 2026-11-04`（生成日期与报告名都用该日期）
- 测试/CI：加 `--no-open` 不自动打开浏览器
- 需要单独重跑某步时（调试）：`screen.py`（分档）→ `history.py record`（记历轮）→ `report.py`（出报告）
- **不要用 docx 管线替代 HTML 报告**：即使本轮数据走的是用户既有的 docx 工作流（选岗清单），也必须再跑一遍 skill 管线（`run.py`）产出 HTML 报告并自动弹出，docx 只作附加产物。docx 落盘后手动 `open "<docx 路径>"` 弹出，并向用户明确说出两个产物的路径。

报告内容：分档统计（**统计卡可点选：岗位墙 ⇄ 该档平面清单视图**）、**历轮筛查记录表**（报告末尾；自动更新：日期/新核查/A·B·C·X/陷阱新增/备注，陷阱累计从 `knowledge/traps.md` 头部解析）、3D 岗位墙（A/B/C，点卡片看判定理由/联系方式/邮件草稿，沿用卡带「沿用」标签，卡片内带该岗位的 IE 深链）、X 排除表（默认收起，点 X 统计卡展开）。邮件底稿由 `profile.yaml` + `assets/email_template.md` 自动生成。

### 4. 交付与邮件定稿（AI 逐雇主个性化）

- 报告里的草稿是**底稿**。用户挑中岗位后，AI 用 profile 记忆为**每个雇主**定稿：在底稿上加 1-2 句针对性内容（岗位特点 / 地点 / 用户与该雇主的匹配点），正文 ≤ `email.max_words` 词，简约明了。
- 邮件口径全部按 `email` 配置：`no_questions`（默认不提问题，住宿细节等雇主回复后再谈）、`include_contact`（签名是否带联系方式）、`closing_line`。
- 提醒：正式申请仍走 IE 站内 Apply。

### 5. 知识库维护（每次筛查后）

- `knowledge/traps.md`：新陷阱案例按表格式追加
- `knowledge/towns.yaml`：新镇治安结论（注明来源与口径冲突）、新孤岛镇 / 住房危机镇
- `knowledge/contacts.yaml`：新调研到的雇主联系方式
- 改了 `knowledge/` 后重跑 `python3 scripts/build_site_data.py`，把最新知识库刷新进 `webapp/data.js`（工作台的报告页/联系卡依赖它）
- 新暴露的岗位/职责关键词同步补进 `config.redline`（free_text_exclude 排除 / free_text_redline 红线）
- 把本轮要点写进历轮（记录表「陷阱新增」「备注」列）：

```bash
python3 scripts/history.py update config.yaml <YYYY-MM-DD> --traps-added 18 --traps-exclude 9 --note "重点备注"
```

## 分档定义

| 档 | 含义 | 处理 |
|---|---|---|
| X | 排除 | 命中任一硬红线：日期（到岗/离岗不满足）、红线岗位、4 人+/间、孤岛镇、实岗为排除类 |
| C | 红线 | 不推荐（如 Hospitality Crew 综合酒店岗轮岗） |
| B | 标注 | 有条件权衡：需提前到岗 / 时薪或工时低于线 / 3 人间 / 卡片实岗不符 / 住房危机镇无住宿信息 |
| A | 优先 | 全部通过，按 `tiering.sort_by` 排序 |

判定顺序 X → C → B → A：任何一条 X 理由即整岗 X（`tiering.order` 可改）。

## 文件地图

- `profile.yaml` — **记忆模块**：用户档案（姓名/联系方式/日期/经历优势），首次设置后自动复用
- `config.yaml` — 全部筛选口径（维度阈值 + 报告与邮件选项），注释即说明；空值 = 该维度不启用
- `profile.template.yaml` / `config.template.yaml` — 中性模板（新用户复制起步，不含任何个人口径）
- `webapp/` — 工作台网页应用：设置表单（导出 yaml）+ 报告渲染（拖入筛查结果 JSON 在线看岗位墙/历轮表）；`webapp/data.js` 由 build_site_data.py 生成，勿手改
- `scripts/build_site_data.py` — 把 knowledge/ 快照成 `webapp/data.js`（knowledge 更新后重跑）
- `scripts/screen.py` — 分档核心（读 config + knowledge，产结果 JSON）
- `scripts/report.py` — HTML 报告（3D 岗位墙 / 联系方式 / 邮件草稿 / 深链）
- `scripts/mailgen.py` — 邮件底稿填充（读 profile.yaml + 模板）
- `scripts/history.py` — 历轮筛查历史（record 幂等追加 / update 补陷阱数与备注 / list），报告历轮表的数据源
- `assets/email_template.md` — 邮件模板（简约底稿，AI 定稿时个性化）
- `knowledge/position_map.yaml` — IE 标准岗位→档位映射、详情页实岗判定表
- `knowledge/towns.yaml` — 孤岛镇 / 住房危机镇 / 治安调研库
- `knowledge/contacts.yaml` — 雇主联系方式库
- `knowledge/traps.md` — 卡片标题陷阱案例库
- `references/input_schema.md` — 输入数据格式
