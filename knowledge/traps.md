# 卡片标题陷阱库

> 累计 278 处记录 / 178 处排除向（截至 2026-11-04，历轮筛查沉淀）。
> 这是本 skill 最有价值的经验资产：**列表页卡片标题常与详情页实岗不符**。

## 判定规则（screen.py 已实现，参数在 config.redline）

1. **实岗判定只看详情页 Position Description 首句**，格式 `"<role> are/will be responsible for..."`，提取 role 后映射 knowledge/position_map.yaml 的 detail_roles。
2. 卡片标题与实岗不一致 → 至少标 B，注明「卡片写 X 实为 Y」（陷阱经典模式）。
3. 首句非标准格式 → 对全文跑 config.redline.free_text_exclude / free_text_redline 关键词。
4. 任何岗位点 Apply 前必须先看详情页 PD 首句——这条对人工筛查同样成立。

## 经典案例（判定规则的来源）

| 雇主 | 卡片标题 | 实岗 | 判定 |
|---|---|---|---|
| White Gull Inn | Host/Hostess | Dishwasher | X（曾在旧版清单列 TOP15） |
| A&W | Cashier | 保洁 | X |
| Peconic / Cambria | Front Desk | Server | B（岗位不符标注） |
| Snug Harbor | Bartender | Front Desk | B |
| Cape Cod National | Server Assistant | Groundskeeping | X（卡片后改为苦力） |
| Indian Hill | Grocery Clerk | 理货（unloading the grocery truck） | X |
| 快餐岗（Fast Food Crew） | — | PD 含 cleaning/cooking | B |
| 综合酒店岗（Hospitality Crew） | — | 洗衣/客房/后厨/前台轮岗 | C |

## 维护方式

- 每轮筛查后，把新案例按 `雇主 | 卡片标题 | 实岗 | 判定` 追加到上表。
- 若新案例暴露新关键词，同步补进 config.redline 的 keyword 列表（两边对照）。
- 案例表是给人看的；判定逻辑以 config + position_map 为准，两者必须一致。
