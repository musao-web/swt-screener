# 岗位数据采集教程（首次使用 = 全量筛查）

首次使用时，用户需要把自己在 IE 里**能看到的所有岗位**全部筛一遍。IE 在架卡片量级是四位数，
逐张进详情页不现实，所以采集按两段式进行：

```
① 列表页全量快照（一次拿全所有在架卡）
      ↓
② 粗筛 prefilter.py（只用卡片就有的字段砍掉僵尸岗/标题红线/孤岛镇）
      ↓
③ 只对候选逐个抓详情页（posdesc 首句、Start/Finish、住宿、租金、室友数）
      ↓
④ collect_to_input.py 合并成 input.json → run.py 精筛出报告
```

---

## ⚠️ 采集红线（必须遵守）

1. **只用你自己已登录的 IE 会话采集**——skill 不做自动登录、不碰你的账号密码
2. **只采集你本人登录后能看到的内容**，不要尝试越权/绕过登录态
3. **限速**：人工点看或脚本采集都保持正常浏览节奏，不要高频请求
4. 发现账号异常、验证码、风控提示 → **立即停止采集**
5. 采集下来的数据含你账号可见的岗位信息，不要上传到公开仓库

---

## ① 列表页全量快照

### 方式 A：F12 复制接口响应（默认教程，零依赖）

1. 浏览器登录 IE（app.interexchange.org），打开 Job Listings 岗位列表页
2. 按 F12 打开开发者工具 → 切到 **Network** 标签
3. 刷新列表页，在请求列表里找返回岗位数据的接口：响应是 **JSON 数组**，
   元素长这样（有 `"id": "job_listing_..."`、`title`、`employer`、`lastVisited`、`rightCol` 等字段）
4. 右键该请求 → **Copy** → **Copy response** → 粘贴存成 `all_cards.json`

> 找不到？在 Network 面板的过滤框里输入 `listing` 或 `job` 缩小范围；
> 响应预览里能看到 `job_listing_` 开头 id 的那个就是。

### 方式 B：控制台采集脚本（一次粘贴，自动采集 + 一键导出）

1. 登录 IE 后按 F12 打开 Console
2. 把 `scripts/collect/ie_capture.js` 全部内容粘贴进控制台，回车
   （页面右下角出现「SWT 采集」按钮 = 挂钩成功）
3. 刷新列表页 → 列表接口响应自动入库；随后正常浏览，点开的每个详情页也自动入库
4. 浏览完点右下角按钮，自动下载 `swt_capture_<日期>.json`

> 刷新页面会使挂钩失效，重新粘贴一次即可。SPA 内跳转不受影响。

---

## ② 粗筛出候选

```bash
python3 scripts/collect/prefilter.py config.yaml all_cards.json --out 候选清单.json
```

只用**列表卡片上就有的字段**做第一刀（口径全部来自你的 config.yaml）：

| 维度 | 数据 | 结果 |
|---|---|---|
| 活跃度 | lastVisited 年份 < season_year 或无记录 | 排除（僵尸岗） |
| 标题红线 | free_text_exclude 关键词命中卡片标题 | 排除 |
| 孤岛镇 | exclude_island_towns 且命中 towns.yaml island_patterns | 排除 |
| 薪资工时租金 | 卡片 rightCol 低于/高于你设的线 | **软标注**（不排除，进详情留意） |

产出 `候选清单.json` + 同名 `.txt`（给人看的编号清单）。日期窗口、住宿人数、
陷阱实岗等维度必须进详情页才能判定，粗筛不碰——所以候选**必须**逐个进详情。

---

## ③ 详情页采集（只对候选）

对着候选清单逐个点开详情页，每页采集一次：

- **方式 A（F12）**：详情页 Network 里找该页详情接口（响应是含 `pairs` 数组的对象，
  有 `Start` / `Finish` / `Position Description` 等标签），Copy response 存成一个 json 文件，
  全部放进同一个目录（文件名随意，如 `ie_det_100023.json`）
- **方式 B（脚本）**：如果第①步用了 `ie_capture.js`，详情已自动入库，此步直接跳过

详情页的关键字段：`Position Description` 首句（陷阱实岗判定的唯一依据）、
`Start`/`Finish` 窗口、`Rent`、`Number of people sharing a bedroom`、`Housing Type`。

---

## ④ 合并成 input.json

```bash
python3 scripts/collect/collect_to_input.py all_cards.json 详情目录/ --only 候选清单.json --out input.json
```

- 列表和详情按 profile id 自动配对（`/wt/employers/2223/enrollment_profiles/102538` → `102538`）
- 用 `ie_capture.js` 导出的话，第二个参数直接给导出文件（自动取 details 部分）
- 输出 `{"rows": [...], "fetch_fail": [...]}`：`fetch_fail` 列出**候选里还缺详情**的卡，先补采再跑管线

```bash
python3 scripts/run.py config.yaml input.json
```

跑完自动弹出 HTML 报告。首次筛查没有历轮，全部卡完整判定；之后例行筛查只筛新卡。

---

## 进阶：CDP 半自动采集（可选）

熟悉命令行的用户可以把详情页点击也自动化：自己启动一个挂调试端口的 Chrome 实例
（`--remote-debugging-port=9333 --user-data-dir=<独立目录>`），**自己在里面登录 IE**，
再写 CDP 脚本连上端口、按候选清单逐条打开详情页、限速（如每张 1–2 秒）抓取。
红线同上：不自动登录、限速、发现风控立即停。仓库暂不附带该脚本，避免被误用为批量爬取。

---

## 排错

| 现象 | 处理 |
|---|---|
| Network 里找不到岗位接口 | 清空面板（🚫图标）→ 刷新页面，只留 XHR/Fetch 过滤 |
| 控制台脚本没反应 | 确认粘贴完整后回车；查看 Console 是否输出「挂钩成功」 |
| 导出按钮消失 | 页面被刷新过，重新粘贴脚本 |
| fetch_fail 很多 | 候选清单里点开过的详情还不够，先补采再跑 collect_to_input |
| 候选数过大（>500） | 正常；先按地区/薪资偏好缩小范围，或分批抓详情 |
