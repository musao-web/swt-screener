# 输入数据格式（screen.py 的输入）

JSON 文件，含 `rows` 数组（无 `rows` 时整体视为数组）。每行一个岗位，来自 IE 列表页卡片 + 详情页的合并数据。

## 完整格式（详情页抓取流水线产出）

```json
{
  "rows": [
    {
      "slug": "wi-fish-creek-white-gull-inn",
      "meta": {
        "title": "Host/Hostess",                    // 列表页卡片标题（⚠ 常与实岗不符）
        "employer": "White Gull Inn",
        "location": "Fish Creek, WI",
        "href": "https://app.interexchange.org/...", // IE 岗位页链接（报告里可点）
        "lastVisited": "Nov 02, 2026",               // 雇主最后登录（活跃度判定）
        "tips": true,                                // 列表页是否有小费标识
        "rightCol": "$22 + tips /hour | 40 hours /week | $90 rent /week",
        "_wage": 22.0, "_hours": 40, "_rent": 90.0   // 可选：已预解析的数值
      },
      "pairs": [["start", "Jun 1, 2027 - Jul 15, 2027"], ...],  // 详情页原始标签值对
      "posdesc": "Host/Hostesses are responsible for ...",      // 详情页职责描述（陷阱判定唯一依据）
      "adddesc": "",                               // 附加说明
      "housing": "Employer housing, 2 people per bedroom",  // 住宿说明（住房危机镇判定用）
      "rent": "$90 per week",                      // 详情页租金原文
      "share": "2",                                // 室友数原文（"2" / "2 people" / "2-3 per bedroom"）
      "SW": ["2027-06-01", "2027-07-15"],          // 到岗窗口（start 字段解析，可无）
      "FW": ["2027-09-01", "2027-09-15"],          // 离岗窗口（finish 字段解析，可无）
      "listings": 1
    }
  ],
  "fetch_fail": []
}
```

## 最小可用格式

`meta.title / employer / location / href` 必填；其余字段缺省时对应维度给"未标注"类理由，不报错。

## 数据来源要点

- **列表页**：IE Job Listings 的卡片（标题/雇主/地点/薪资工时租金/最后登录/链接）。
- **详情页**：每个候选岗必须抓详情页——`posdesc` 首句是实岗判定的唯一依据（卡片标题陷阱 278 处记录，任何岗位 Apply 前必看）。
- IE 详情页**没有联系方式字段**，雇主联系方式全部来自 `knowledge/contacts.yaml` 与公开来源调研。
- 日期注意：当季窗口是下一年份（2026 季 → 2027 日期），比较按月/日。
