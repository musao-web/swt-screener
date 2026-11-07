#!/usr/bin/env python3
"""
swt-screener HTML 报告生成（Shadcn 风格 + 3D 岗位墙）

用法:
    python3 report.py <config.yaml> <screen_result.json> <report.html>

报告内容:
  - 头部 CTA（IE 预筛深链）+ 分档统计卡 + 筛选口径卡
  - 3D 岗位墙：A/B/C 岗做成倾斜舞台里的竖向滚动卡片列（悬停暂停）
    点击卡片弹出详情（判定理由 / 联系方式 / 邮件草稿 / IE 深链）
  - X 排除档：紧凑表格（排除理由一眼可见，无草稿）
联系方式来源: knowledge/contacts.yaml 命中 → 直接给；未收录 → 渠道建议。
邮件草稿: A/B/C 档生成（X 排除档不生成）。
"""
import sys, json, html, math, os, re, urllib.parse, datetime as dt
from pathlib import Path

IE_BASE = "https://app.interexchange.org"

TIER_META = {
    "A": ("A", "优先", "全部通过 · 可直接申请", "直接申请"),
    "B": ("B", "权衡", "有条件权衡 · 看标注决定", "按标注权衡"),
    "C": ("C", "红线", "不推荐 · 风险需自担", "不推荐"),
    "X": ("X", "排除", "命中硬性排除条件", "硬性排除"),
}
TIER_ORDER = ["A", "B", "C", "X"]
WALL_TIERS = {"A", "B", "C"}

STAGE_H = 560        # 舞台高度 px
CARD_H = 190         # 卡片+间距估算（repeat 计算用）


def load_yaml(path):
    import yaml
    return yaml.safe_load(open(path, encoding="utf-8"))


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=False)


def abs_href(href):
    if not href:
        return ""
    return href if href.startswith("http") else IE_BASE + href


def norm(s):
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def match_contact(employer, contacts):
    emp = norm(employer)
    for key, info in contacts.items():
        base = norm(key.split("(")[0])
        if base and (base in emp or emp in base):
            return info
    return None


def match_safety(location, towns):
    loc = norm(location)
    for key, info in (towns.get("safety") or {}).items():
        if norm(key) in loc:
            return info
    return None


def fmt_window(w):
    if not w:
        return "未标注"
    a, b = dt.date.fromisoformat(w[0]), dt.date.fromisoformat(w[1])
    return f"{a:%m/%d}–{b:%m/%d}"


def deep_link(cfg):
    params = {}
    wh = cfg.get("wage_hours") or {}
    if wh.get("min_wage"):
        params["q[wage_gteq]"] = wh["min_wage"]
    if wh.get("min_hours"):
        params["q[hours_gteq]"] = wh["min_hours"]
    return "https://app.interexchange.org/wt/job_listings?" + urllib.parse.urlencode(params)


def pay_line(job):
    if job["wage"] is None:
        s = '<span class="miss">—</span>'
    else:
        s = f'<b>${esc(job["wage"])}</b>/h'
        if job["tips"]:
            s += ' <span class="tip">+tip</span>'
    if job["hours"] is not None:
        s += f'<span class="dim"> · {esc(job["hours"])}h/周</span>'
    return s


def hou_line(job):
    bits = [esc(job["share"]) if job["share"] else "未标注"]
    if job["rent"] is not None:
        bits.append(f'${esc(job["rent"])}/周')
    return "室友 " + bits[0] + (f' <span class="dim">· 租金 {bits[1]}</span>' if len(bits) > 1 else "")


def safety_chip(job, towns):
    s = match_safety(job["location"], towns)
    if not s:
        return ""
    return f' <span class="safety" title="{esc(s.get("note") or "")}">安全 {esc(s["grade"])}</span>'


def contact_html(job, contacts, fallback):
    info = match_contact(job["employer"], contacts)
    if info:
        bits = []
        if info.get("email"):
            bits.append(f'<div class="cemail">{esc(info["email"])}</div>')
        if info.get("phone"):
            bits.append(f'<div class="cphone">{esc(info["phone"])}</div>')
        if info.get("note"):
            bits.append(f'<div class="cnote">{esc(info["note"])}</div>')
        return "".join(bits) if bits else '<span class="miss">无</span>'
    return '<span class="miss">未收录</span><div class="chbody">' + "<br>".join("· " + esc(c) for c in fallback) + "</div>"


# ---------------- 历轮筛查记录 ----------------

def load_history(cfg):
    """读 config.history.file 的历轮 JSON；无文件/损坏返回空列表"""
    p = (cfg.get("history") or {}).get("file") or ""
    p = Path(os.path.expanduser(p))
    if not p or not p.exists():
        return []
    try:
        return json.load(open(p, encoding="utf-8")).get("rounds") or []
    except Exception:
        return []


def traps_totals(root):
    """解析 knowledge/traps.md 头部「累计 N 处记录 / M 处排除向（截至 …）」"""
    try:
        text = open(root / "knowledge" / "traps.md", encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(r"累计\s*(\d+)\s*处记录\s*/\s*(\d+)\s*处排除向（截至\s*([\d-]+)", text)
    return (int(m.group(1)), int(m.group(2)), m.group(3)) if m else None


def hist_section(cfg, root):
    rounds = sorted(load_history(cfg), key=lambda r: r.get("date") or "")
    tt = traps_totals(root)
    sub = f"{len(rounds)} 轮"
    if tt:
        sub += f" · 陷阱累计 {tt[0]} 处（排除向 {tt[1]}，截至 {tt[2]}）"
    rows = ""
    for r in rounds:
        c = r.get("counts") or {}
        cells = ""
        for t in TIER_ORDER:
            n = c.get(t, 0)
            cls = f"t-{t}" if n else "miss"
            cells += f'<span class="hcell {cls}">{n}</span>'
        traps = '<span class="miss">—</span>'
        if r.get("traps_added") is not None:
            traps = f'<b>{esc(r["traps_added"])}</b>'
            if r.get("traps_exclude") is not None:
                traps += f'<div class="dim">排除向 {esc(r["traps_exclude"])}</div>'
        new = f'<b>{esc(r.get("new") or 0)}</b>'
        if r.get("carried"):
            new += f' <span class="dim">+沿用 {esc(r["carried"])}</span>'
        rows += f"""<tr class="main">
  <td class="c-date">{esc(r.get("date") or "—")}</td>
  <td>{new}</td>
  <td colspan="4">{cells}</td>
  <td>{traps}</td>
  <td class="c-note">{esc(r.get("note") or "—")}</td>
</tr>"""
    if not rows:
        rows = ('<tr class="main"><td colspan="8" class="hist-empty">还没有历史轮次。每次筛查后运行 '
                '<code>python3 scripts/history.py record config.yaml screen_result.json</code>，'
                '这里自动累积。</td></tr>')
    return f"""
  <section class="card">
    <div class="card-head"><h3>历轮筛查记录</h3><span class="card-sub">{esc(sub)}</span></div>
    <div class="tablewrap"><table class="tt hist">
      <thead><tr><th>日期</th><th>新核查</th><th colspan="4">分档</th><th>陷阱新增</th><th>备注</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></div>
  </section>
"""


# ---------------- 3D 岗位墙 ----------------

def wall_card(i, job, towns):
    letter = TIER_META[job["tier"]][0]
    ie = abs_href(job["href"])
    seen_tag = ' <span class="seen-tag">沿用</span>' if job.get("seen") else ""
    return f"""
      <div class="jcard t-{job['tier']}" data-i="{i}">
        <div class="jhead">
          <span class="gcell t-{job['tier']}">{letter}</span>
          <span class="jtitle">{esc(job['title'])}</span>{seen_tag}
        </div>
        <div class="jemp">{esc(job['employer'])}</div>
        <div class="jloc">{esc(job['location'])}{safety_chip(job, towns)}</div>
        <div class="jstats">
          <div class="js">{pay_line(job)}</div>
          <div class="js">到岗 {fmt_window(job['SW'])}</div>
          <div class="js">{hou_line(job)}</div>
          <div class="js">离岗 {fmt_window(job['FW'])}</div>
        </div>
        <div class="jfoot">
          <span class="jhint">点击看理由 · 联系 · 草稿</span>
          <a class="j-ie" href="{esc(ie)}" target="_blank" rel="noopener">IE ↗</a>
        </div>
      </div>"""


def wall_col(cards, direction, repeat, duration):
    copies = "".join(
        f'<div class="mcopy">{"".join(cards)}</div>' for _ in range(repeat))
    return f"""
    <div class="mcol" style="--duration:{duration}s">
      <div class="mgroup{' mrev' if direction else ''}">{copies}</div>
    </div>"""


def modal(i, job, contacts, fallback, towns, draft):
    letter = TIER_META[job["tier"]][0]
    ie = abs_href(job["href"])
    reasons = "".join(f'<span class="chip">{esc(t)}</span>' for t in job["reasons"])
    draft_html = ""
    if draft:
        draft_html = (f'<div class="msec"><div class="mlabel">求职邮件草稿 · 复制即用</div>'
                      f'<pre class="mpre">{esc(draft["subject"])}\n\n{esc(draft["body"])}</pre></div>')
    last = f'<div class="msec"><div class="mlabel">雇主最近登录</div><div class="mval">{esc(job["lastVisited"])}</div></div>' if job.get("lastVisited") else ""
    return f"""
  <div class="moverlay" id="mov-{i}" role="dialog" aria-modal="true">
    <div class="mcard">
      <div class="mhead">
        <span class="gcell t-{job['tier']}">{letter}</span>
        <div class="mh-text">
          <div class="mtitle">{esc(job['title'])}</div>
          <div class="memp">{esc(job['employer'])} · {esc(job['location'])}</div>
        </div>
        <button class="mclose" aria-label="关闭">×</button>
      </div>
      <div class="mstats">
        <div class="ms">{pay_line(job)}</div>
        <div class="ms">到岗 {fmt_window(job['SW'])}</div>
        <div class="ms">{hou_line(job)}</div>
        <div class="ms">离岗 {fmt_window(job['FW'])}</div>
      </div>
      <div class="msec"><div class="mlabel">判定理由</div><div class="chips">{reasons}</div></div>
      <div class="msec"><div class="mlabel">联系方式</div>{contact_html(job, contacts, fallback)}</div>
      {last}
      {draft_html}
      <div class="mactions">
        <a class="cta" href="{esc(ie)}" target="_blank" rel="noopener">在 IE 打开 ↗</a>
        <span class="mhint">正式申请仍走 IE 站内 Apply</span>
      </div>
    </div>
  </div>"""


# ---------------- X 排除表 ----------------

def x_rows(job, contacts, fallback, towns):
    ie = abs_href(job["href"])
    reasons = "".join(f'<span class="chip">{esc(t)}</span>' for t in job["reasons"])
    return f"""
<tr class="main t-X">
  <td class="c-grade"><span class="gcell t-X">X</span></td>
  <td class="c-job">
    <a class="title" href="{esc(ie)}" target="_blank" rel="noopener">{esc(job['title'])}</a>
    <div class="emp">{esc(job['employer'])}</div>
    <div class="loc">{esc(job['location'])}{safety_chip(job, towns)}</div>
  </td>
  <td class="c-pay">{pay_line(job)}</td>
  <td class="c-win"><div>到岗 {fmt_window(job['SW'])}</div><div class="sub">离岗 {fmt_window(job['FW'])}</div></td>
  <td class="c-hou">{hou_line(job)}</td>
  <td class="c-ct">{contact_html(job, contacts, fallback)}</td>
  <td class="c-ie"><a class="ielink" href="{esc(ie)}" target="_blank" rel="noopener">IE ↗</a></td>
</tr>
<tr class="extra">
  <td class="c-extra" colspan="7">
    <div class="reasons"><span class="rlabel">排除理由</span>{reasons}</div>
  </td>
</tr>"""


def main():
    cfg_path, in_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    root = Path(__file__).resolve().parent.parent
    cfg = load_yaml(cfg_path)
    contacts_data = load_yaml(root / "knowledge" / "contacts.yaml")
    contacts = contacts_data.get("employers") or {}
    fallback = contacts_data.get("fallback_channels") or []
    towns = load_yaml(root / "knowledge" / "towns.yaml")
    template = open(root / "assets" / "email_template.md", encoding="utf-8").read()
    data = json.load(open(in_path, encoding="utf-8"))
    jobs = data["jobs"]

    from mailgen import build_draft, load_profile
    profile = load_profile(root, cfg)
    drafts = {}
    if cfg.get("report", {}).get("include_email_drafts", True) and cfg.get("email", {}).get("enabled", True):
        for j in jobs:
            if j["tier"] in WALL_TIERS:
                drafts[id(j)] = build_draft(cfg, profile, j, template)

    # ---- 头图：统计卡 + 口径（只显示已设置的维度） ----
    chips = []
    arr = cfg.get("arrival") or {}
    if arr.get("priority_on_or_after"):
        chips.append(f"到岗 ≥{arr['priority_on_or_after']} 优先")
    dep_cfg = cfg.get("departure") or {}
    if dep_cfg.get("deadline"):
        chips.append(f"离岗 ≤{dep_cfg['deadline']}")
    wh = cfg.get("wage_hours") or {}
    if wh.get("min_wage"):
        chips.append(f"时薪 ≥${wh['min_wage']}")
    if wh.get("min_hours"):
        chips.append(f"工时 ≥{wh['min_hours']}h")
    hou_cfg = cfg.get("housing") or {}
    if hou_cfg.get("max_roommates"):
        chips.append(f"住宿 ≤{hou_cfg['max_roommates']}人/间")
    if hou_cfg.get("max_rent_weekly"):
        chips.append(f"租金 ≤${hou_cfg['max_rent_weekly']}/周")
    if not chips:
        chips.append("未设置筛选线（全部维度不判定）")
    chips_html = "".join(f'<span class="chip">{esc(c)}</span>' for c in chips)

    hist_html = hist_section(cfg, root)

    counts = data["counts"]
    stats_html = "".join(f"""
      <div class="stat">
        <div class="stat-top"><span class="gcell t-{t}">{letter}</span><span class="stat-label">{zh}</span></div>
        <div class="stat-num">{counts.get(t, 0)}</div>
        <div class="stat-cap">{cap}</div>
      </div>""" for t, (letter, zh, _sub, cap) in TIER_META.items())

    # ---- 3D 岗位墙（A/B/C 轮流入 3 列，A 保证第 1 列）----
    wall_jobs = [j for j in jobs if j["tier"] in WALL_TIERS]
    cols = [[], [], []]
    for i, j in enumerate(wall_jobs):
        cols[i % 3].append(j)
    directions = [False, True, False]
    col_html, modals = [], []
    for ci, col in enumerate(cols):
        cards = [wall_card(ci * 1000 + k, j, towns) for k, j in enumerate(col)]
        repeat = min(6, max(2, math.ceil(STAGE_H * 2.6 / (len(col) * CARD_H))))
        copy_h = len(col) * CARD_H
        duration = max(30, round(copy_h * 40 / 1900))
        col_html.append(wall_col(cards, directions[ci], repeat, duration))
        for k, j in enumerate(col):
            modals.append(modal(ci * 1000 + k, j, contacts, fallback, towns, drafts.get(id(j))))
    wall_n = len(wall_jobs)

    # ---- X 排除表 ----
    x_jobs = [j for j in jobs if j["tier"] == "X"]
    x_section = ""
    if x_jobs:
        rows = "".join(x_rows(j, contacts, fallback, towns) for j in x_jobs)
        x_section = f"""
<section class="card">
  <div class="tier-head">
    <span class="gcell t-X">X</span>
    <div><h2>排除</h2><p class="tier-sub">{TIER_META['X'][2]}</p></div>
    <span class="count">{len(x_jobs)} 岗</span>
  </div>
  <div class="tablewrap"><table class="tt">
    <thead><tr>
      <th class="c-grade">评级</th><th>岗位</th><th>薪资 · 工时</th>
      <th>到岗 · 离岗</th><th>住宿</th><th>联系</th><th></th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
</section>"""

    html_doc = f"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SWT 岗位筛查报告 {esc(data['generated'])}</title>
<style>
:root {{
  --bg:#eff1f5; --card:#ffffff; --fg:#4c4f69; --fg2:#6c6f85; --muted:#8c8fa1;
  --line:#ccd0da; --line2:#e6e9ef;
  --accent:#8839ef; --accent-hover:#7a2fe0; --on-accent:#ffffff;
  --accent2:#04a5e5; --accent2-soft:rgba(4,165,229,.10);
  --badge-b:#9ca0b0; --badge-c:#8c8fa1;
  --danger:#d20f39;
  --tier-a:#40a02b; --tier-a-soft:rgba(64,160,43,.10);
  --tier-b:#fe640b; --tier-b-soft:rgba(254,100,11,.10); --on-tier-b:#4c4f69;
  --tier-c:#d20f39; --tier-c-soft:rgba(210,15,57,.10);
  --tier-x:#d20f39; --tier-x-soft:rgba(210,15,57,.07);
  --radius:10px; --radius-s:7px;
  --shadow:0 4px 6px hsl(240 30% 25% / 0.12);
  --shadow-lg:0 4px 6px hsl(240 30% 25% / 0.12), 0 16px 40px hsl(240 30% 25% / 0.16);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#181825; --card:#1e1e2e; --fg:#cdd6f4; --fg2:#a6adc8; --muted:#7f849c;
    --line:#313244; --line2:#292c3c;
    --accent:#cba6f7; --accent-hover:#ddb6f2; --on-accent:#1e1e2e;
    --accent2:#89dceb; --accent2-soft:rgba(137,220,235,.12);
    --badge-b:#6c7086; --badge-c:#585b70;
    --danger:#f38ba8;
    --tier-a:#a6e3a1; --tier-a-soft:rgba(166,227,161,.12);
    --tier-b:#fab387; --tier-b-soft:rgba(250,179,135,.12); --on-tier-b:#1e1e2e;
    --tier-c:#f38ba8; --tier-c-soft:rgba(243,139,168,.12);
    --tier-x:#f38ba8; --tier-x-soft:rgba(243,139,168,.09);
    --shadow:0 4px 6px hsl(240 30% 15% / 0.45);
    --shadow-lg:0 4px 6px hsl(240 30% 15% / 0.45), 0 16px 40px hsl(240 30% 15% / 0.55);
  }}
}}
:root[data-theme="dark"] {{
  --bg:#181825; --card:#1e1e2e; --fg:#cdd6f4; --fg2:#a6adc8; --muted:#7f849c;
  --line:#313244; --line2:#292c3c;
  --accent:#cba6f7; --accent-hover:#ddb6f2; --on-accent:#1e1e2e;
  --accent2:#89dceb; --accent2-soft:rgba(137,220,235,.12);
  --badge-b:#6c7086; --badge-c:#585b70;
  --danger:#f38ba8;
  --tier-a:#a6e3a1; --tier-a-soft:rgba(166,227,161,.12);
  --tier-b:#fab387; --tier-b-soft:rgba(250,179,135,.12); --on-tier-b:#1e1e2e;
  --tier-c:#f38ba8; --tier-c-soft:rgba(243,139,168,.12);
  --tier-x:#f38ba8; --tier-x-soft:rgba(243,139,168,.09);
  --shadow:0 4px 6px hsl(240 30% 15% / 0.45);
  --shadow-lg:0 4px 6px hsl(240 30% 15% / 0.45), 0 16px 40px hsl(240 30% 15% / 0.55);
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg);
       font:14px/1.65 Montserrat,-apple-system,"SF Pro Text","PingFang SC","Microsoft YaHei",sans-serif;
       -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:48px 20px 72px; }}
.page-head {{ display:flex; justify-content:space-between; align-items:flex-end;
             gap:16px; flex-wrap:wrap; margin-bottom:32px; }}
h1 {{ font-size:26px; font-weight:650; letter-spacing:-0.02em; margin:0; }}
.page-sub {{ color:var(--muted); font-size:13px; margin:8px 0 0; }}
.cta {{ display:inline-flex; align-items:center; gap:7px; background:var(--accent); color:var(--on-accent);
       font-size:13.5px; font-weight:500; padding:10px 18px; border-radius:var(--radius-s);
       text-decoration:none; box-shadow:0 2px 4px hsl(240 30% 25% / .18); white-space:nowrap; }}
.cta:hover {{ background:var(--accent-hover); }}
.theme-btn {{ display:inline-flex; align-items:center; justify-content:center; width:38px; height:38px;
             border:1px solid var(--line); background:var(--card); color:var(--fg2);
             border-radius:var(--radius-s); cursor:pointer; box-shadow:var(--shadow); }}
.theme-btn:hover {{ color:var(--fg); border-color:var(--muted); }}
.head-actions {{ display:flex; align-items:center; gap:10px; }}
.stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:28px; }}
.stat {{ background:var(--card); border:1px solid var(--line); border-radius:var(--radius);
        padding:18px 20px; box-shadow:var(--shadow); }}
.stat-top {{ display:flex; align-items:center; gap:9px; }}
.stat-label {{ font-size:12.5px; color:var(--muted); font-weight:500; }}
.stat-num {{ font-size:30px; font-weight:650; letter-spacing:-0.03em; margin-top:12px; line-height:1; }}
.stat-cap {{ font-size:11.5px; color:var(--muted); margin-top:8px; }}
.gcell {{ width:28px; height:28px; border-radius:var(--radius-s); display:inline-flex; align-items:center;
         justify-content:center; font-weight:600; font-size:13.5px; flex:none; }}
.gcell.t-A {{ background:var(--tier-a); color:var(--on-accent); }}
.gcell.t-B {{ background:var(--tier-b); color:var(--on-tier-b); }}
.gcell.t-C {{ background:var(--tier-c); color:var(--on-accent); }}
.gcell.t-X {{ background:transparent; color:var(--tier-x); border:1.5px dashed var(--tier-x); }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:var(--radius);
        box-shadow:var(--shadow); padding:24px 26px; margin-bottom:28px; }}
.card-head {{ display:flex; align-items:baseline; gap:12px; margin-bottom:16px; }}
.card-head h3 {{ font-size:14.5px; font-weight:600; margin:0; letter-spacing:-0.01em; }}
.card-sub {{ font-size:12px; color:var(--muted); }}
.chips {{ display:flex; flex-wrap:wrap; gap:8px; }}
.chip {{ background:var(--bg); border:1px solid var(--line); border-radius:var(--radius-s);
        padding:4px 13px; font-size:12.5px; color:var(--fg2); }}

/* ---------- 3D 岗位墙 ---------- */
.stage {{ position:relative; overflow:hidden; height:{STAGE_H}px; border:1px solid var(--line);
         border-radius:var(--radius); background:var(--card); box-shadow:var(--shadow);
         perspective:300px; margin-bottom:28px; }}
.stage-inner {{ display:flex; gap:24px; padding:0 30px; height:100%;
               transform:translateX(-70px) translateZ(-80px) rotateX(15deg) rotateY(-8deg) rotateZ(9deg); }}
.mcol {{ flex:0 0 242px; overflow:hidden; position:relative; }}
.mgroup {{ display:flex; flex-direction:column; gap:22px; will-change:transform;
          animation:marq var(--duration) linear infinite; }}
.mgroup.mrev {{ animation-direction:reverse; }}
.mcol:hover .mgroup {{ animation-play-state:paused; }}
@keyframes marq {{
  from {{ transform:translateY(0); }}
  to   {{ transform:translateY(calc(-100% - 22px)); }}
}}
.mcopy {{ display:flex; flex-direction:column; gap:22px; }}
.jcard {{ background:var(--card); border:1px solid var(--line); border-radius:var(--radius);
         box-shadow:var(--shadow); padding:16px 16px 12px; cursor:pointer;
         transition:transform .18s ease, box-shadow .18s ease; }}
.jcard:hover {{ transform:translateY(-3px); box-shadow:var(--shadow-lg); }}
.jcard.t-A {{ border-left:3px solid var(--tier-a);
             background:linear-gradient(to right, var(--tier-a-soft), transparent 45%), var(--card); }}
.jcard.t-B {{ border-left:3px solid var(--tier-b);
             background:linear-gradient(to right, var(--tier-b-soft), transparent 45%), var(--card); }}
.jcard.t-C {{ border-left:3px solid var(--tier-c);
             background:linear-gradient(to right, var(--tier-c-soft), transparent 45%), var(--card); }}
.jhead {{ display:flex; align-items:center; gap:9px; }}
.jtitle {{ font-weight:600; font-size:14.5px; letter-spacing:-0.01em;
          overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.jemp {{ font-weight:500; color:var(--fg2); font-size:12.5px; margin-top:8px; }}
.jloc {{ color:var(--muted); font-size:12px; margin-top:1px; }}
.safety {{ border:1px solid var(--line); border-radius:6px; padding:0 6px; margin-left:6px;
          font-size:11px; color:var(--fg2); cursor:help; }}
.jstats {{ display:grid; grid-template-columns:1fr 1fr; gap:6px 10px; margin-top:11px;
           border-top:1px solid var(--line2); padding-top:10px; }}
.js {{ font-size:12px; color:var(--fg2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.js b {{ color:var(--fg); font-weight:650; font-size:13px; }}
.dim {{ color:var(--muted); }}
.tip {{ color:var(--muted); font-size:11.5px; }}
.jfoot {{ display:flex; justify-content:space-between; align-items:center; margin-top:11px; }}
.jhint {{ font-size:11px; color:var(--muted); }}
.j-ie {{ font-size:11.5px; color:var(--accent2); border:1px solid var(--line); border-radius:var(--radius-s);
        padding:2px 9px; text-decoration:none; white-space:nowrap; }}
.j-ie:hover {{ background:var(--accent2-soft); border-color:var(--accent2); }}
.fade {{ position:absolute; pointer-events:none; z-index:2; }}
.fade-t {{ inset:0 0 auto 0; height:72px; background:linear-gradient(to bottom, var(--bg), transparent); }}
.fade-b {{ inset:auto 0 0 0; height:72px; background:linear-gradient(to top, var(--bg), transparent); }}
.fade-l {{ inset:0 auto 0 0; width:56px; background:linear-gradient(to right, var(--bg), transparent); }}
.fade-r {{ inset:0 0 0 auto; width:56px; background:linear-gradient(to left, var(--bg), transparent); }}
@media (prefers-reduced-motion: reduce) {{
  .mgroup {{ animation:none !important; }}
  .stage {{ overflow-y:auto; }}
}}
@media (max-width:640px) {{
  .stats {{ grid-template-columns:repeat(2,1fr); }}
  .stage {{ height:420px; }}
  .mcol {{ flex:0 0 220px; }}
}}

/* ---------- 弹窗 ---------- */
.moverlay {{ display:none; position:fixed; inset:0; z-index:50; align-items:center;
            justify-content:center; padding:24px;
            background:rgba(30,30,46,.45); backdrop-filter:blur(3px); }}
.moverlay.on {{ display:flex; }}
.mcard {{ background:var(--card); border:1px solid var(--line); border-radius:var(--radius);
         box-shadow:var(--shadow-lg); width:min(620px,100%); max-height:86vh;
         overflow-y:auto; padding:22px 24px; }}
.mhead {{ display:flex; align-items:flex-start; gap:11px; }}
.mh-text {{ flex:1; min-width:0; }}
.mtitle {{ font-weight:650; font-size:16.5px; letter-spacing:-0.01em; }}
.memp {{ color:var(--muted); font-size:12.5px; margin-top:2px; }}
.mclose {{ border:1px solid var(--line); background:var(--bg); color:var(--fg2);
          border-radius:var(--radius-s); width:30px; height:30px; font-size:16px; cursor:pointer;
          display:inline-flex; align-items:center; justify-content:center; flex:none; }}
.mclose:hover {{ color:var(--fg); border-color:var(--muted); }}
.mstats {{ display:grid; grid-template-columns:1fr 1fr; gap:8px 12px; margin:16px 0 4px;
           border:1px solid var(--line); border-radius:var(--radius-s); padding:12px 14px; background:var(--bg); }}
.ms {{ font-size:12.5px; color:var(--fg2); }}
.ms b {{ color:var(--fg); font-weight:650; font-size:13.5px; }}
.msec {{ margin-top:16px; }}
.mlabel {{ font-size:11.5px; font-weight:600; color:var(--muted); letter-spacing:.04em;
          text-transform:uppercase; margin-bottom:8px; }}
.mval {{ font-size:13px; color:var(--fg2); }}
.cemail {{ color:var(--fg); font-weight:500; word-break:break-all; }}
.cphone, .cnote {{ color:var(--muted); font-size:12px; margin-top:2px; }}
.chbody {{ color:var(--muted); font-size:12.5px; line-height:1.9; margin-top:4px; }}
.mpre {{ background:var(--bg); border:1px solid var(--line); border-radius:var(--radius-s);
        padding:14px 16px; white-space:pre-wrap; font:12.5px/1.7 "Fira Code",ui-monospace,SFMono-Regular,Menlo,monospace;
        color:var(--fg); margin:0; }}
.mactions {{ display:flex; align-items:center; gap:14px; margin-top:20px; }}
.mhint {{ color:var(--muted); font-size:12px; }}

/* ---------- X 排除表 ---------- */
.tier-head {{ display:flex; align-items:center; gap:13px; margin-bottom:20px; }}
.tier-head h2 {{ font-size:16.5px; font-weight:600; letter-spacing:-0.01em; margin:0; }}
.tier-sub {{ font-size:12.5px; color:var(--muted); margin:3px 0 0; }}
.count {{ margin-left:auto; font-size:12.5px; color:var(--fg2); border:1px solid var(--line);
         padding:4px 13px; border-radius:999px; }}
.tablewrap {{ overflow-x:auto; margin:0 -6px; }}
.tt {{ width:100%; border-collapse:collapse; min-width:860px; }}
.tt thead th {{ text-align:left; font-size:11.5px; color:var(--muted); font-weight:500;
               padding:0 12px 12px; border-bottom:1px solid var(--line); white-space:nowrap; }}
.tt td {{ padding:14px 12px; vertical-align:top; font-size:13px; }}
tr.main td {{ border-bottom:1px solid var(--line2); }}
tr.main.t-X td:first-child {{ background:var(--tier-x-soft); }}
tr.extra td {{ background:var(--bg); border-bottom:1px solid var(--line2);
               padding:10px 12px 14px 52px; }}
.c-grade {{ width:44px; }}
.c-job {{ min-width:190px; }}
.title {{ font-weight:600; font-size:14px; color:var(--fg); text-decoration:none; }}
.title:hover {{ text-decoration:underline; text-underline-offset:3px; }}
.emp {{ font-weight:500; color:var(--fg2); font-size:12.5px; margin-top:2px; }}
.loc {{ color:var(--muted); font-size:12px; margin-top:1px; }}
.c-pay b {{ font-size:15px; font-weight:650; }}
.sub {{ color:var(--muted); font-size:12px; margin-top:3px; }}
.c-win div {{ margin-bottom:2px; }}
.miss {{ color:var(--muted); font-size:12.5px; }}
.ielink {{ display:inline-block; color:var(--accent2); text-decoration:none; font-size:12.5px;
          border:1px solid var(--line); border-radius:var(--radius-s); padding:3px 11px; white-space:nowrap; }}
.ielink:hover {{ background:var(--accent2-soft); border-color:var(--accent2); }}
.reasons {{ display:flex; flex-wrap:wrap; gap:6px; align-items:baseline; }}
.rlabel {{ color:var(--muted); font-size:12px; margin-right:5px; }}
.reasons .chip {{ background:var(--card); border:1px solid var(--line); border-radius:var(--radius-s);
                  padding:2px 10px; font-size:12px; color:var(--fg2); }}

/* ---------- 历轮记录表 ---------- */
.hist {{ min-width:760px; }}
.hist td {{ padding:12px 12px; font-size:12.5px; }}
.c-date {{ font-weight:600; color:var(--fg); white-space:nowrap; }}
.c-note {{ color:var(--fg2); min-width:200px; max-width:360px; }}
.hist .dim {{ color:var(--muted); font-size:11.5px; }}
.hcell {{ display:inline-block; min-width:27px; text-align:center; border-radius:6px;
         padding:2px 8px; font-weight:600; font-size:12px; margin-right:4px; }}
.hcell.t-A {{ background:var(--tier-a-soft); color:var(--tier-a); }}
.hcell.t-B {{ background:var(--tier-b-soft); color:var(--tier-b); }}
.hcell.t-C {{ background:var(--tier-c-soft); color:var(--tier-c); }}
.hcell.t-X {{ background:var(--tier-x-soft); color:var(--tier-x); }}
.hcell.miss {{ background:var(--bg); color:var(--muted); }}
.hist-empty {{ color:var(--muted); font-size:12.5px; padding:14px 12px; }}
.hist-empty code {{ background:var(--bg); border:1px solid var(--line); border-radius:6px;
                    padding:1px 7px; font-size:11.5px; color:var(--fg2); }}
.seen-tag {{ font-size:10.5px; color:var(--muted); border:1px solid var(--line);
            border-radius:6px; padding:0 5px; margin-left:2px; flex:none; }}
.foot {{ color:var(--muted); font-size:12px; line-height:1.9; margin-top:40px; }}
</style>
</head>
<body>
<div class="wrap">
  <header class="page-head">
    <div>
      <h1>SWT 岗位筛查报告</h1>
      <p class="page-sub">生成于 {esc(data['generated'])} · 共 {len(jobs)} 岗 · 口径全部来自 config.yaml 与 knowledge/ 知识库</p>
    </div>
    <div class="head-actions">
      <button class="theme-btn" id="theme-btn" aria-label="切换明暗主题"></button>
      <a class="cta" href="{esc(deep_link(cfg))}" target="_blank" rel="noopener">在 IE 打开预筛列表 ↗</a>
    </div>
  </header>

  <section class="stats">{stats_html}</section>

  <section class="card">
    <div class="card-head"><h3>本次筛选口径</h3><span class="card-sub">config.yaml 当前值</span></div>
    <div class="chips">{chips_html}</div>
  </section>

  {hist_html}

  <section class="card">
    <div class="card-head"><h3>岗位墙</h3><span class="card-sub">A / B / C 共 {wall_n} 岗 · 悬停暂停 · 点击卡片看判定理由、联系方式与邮件草稿</span></div>
    <div class="stage">
      <div class="stage-inner">{''.join(col_html)}</div>
      <div class="fade fade-t"></div><div class="fade fade-b"></div>
      <div class="fade fade-l"></div><div class="fade fade-r"></div>
    </div>
  </section>

  {x_section}

  {''.join(modals)}

  <div class="foot">
    评级：A 优先 · B 权衡（按条件标注）· C 红线（不推荐）· X 排除。判定顺序 X → C → B → A，任何一条 X 理由即整岗 X。<br>
    ⚠ 陷阱警戒：IE 卡片标题常与详情页实岗不符，Apply 前必须核对详情页 Position Description 首句。
  </div>
</div>
<script>
(function () {{
  function show(i) {{
    var m = document.getElementById('mov-' + i);
    if (m) {{ m.classList.add('on'); document.body.style.overflow = 'hidden'; }}
  }}
  function hide() {{
    document.querySelectorAll('.moverlay.on').forEach(function (m) {{ m.classList.remove('on'); }});
    document.body.style.overflow = '';
  }}
  document.addEventListener('click', function (e) {{
    var card = e.target.closest('.jcard');
    if (card) {{ if (!e.target.closest('.j-ie')) show(card.getAttribute('data-i')); return; }}
    if (e.target.classList.contains('moverlay') || e.target.classList.contains('mclose')) hide();
  }});
  document.addEventListener('keydown', function (e) {{ if (e.key === 'Escape') hide(); }});
}})();
(function () {{
  var ICON_SUN = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  var ICON_MOON = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>';
  var btn = document.getElementById('theme-btn');
  var cur = document.documentElement.getAttribute('data-theme');
  if (!cur) {{ try {{ cur = localStorage.getItem('swt-theme'); }} catch (e) {{}} }}
  if (cur) {{
    document.documentElement.setAttribute('data-theme', cur);
    try {{ localStorage.setItem('swt-theme', cur); }} catch (e) {{}}
  }}
  function isDark() {{
    var a = document.documentElement.getAttribute('data-theme');
    if (a === 'light') return false;
    if (a === 'dark') return true;
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  }}
  function render() {{
    btn.innerHTML = isDark() ? ICON_SUN : ICON_MOON;
    btn.title = isDark() ? '切换到浅色' : '切换到深色';
  }}
  btn.addEventListener('click', function () {{
    var next = isDark() ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try {{ localStorage.setItem('swt-theme', next); }} catch (e) {{}}
    render();
  }});
  render();
}})();
</script>
</body>
</html>"""

    open(out_path, "w", encoding="utf-8").write(html_doc)
    print(f"报告已生成: {out_path}")


if __name__ == "__main__":
    main()
