#!/usr/bin/env python3
"""
swt-screener 筛查分档（核心脚本）

用法:
    python3 screen.py <config.yaml> <input.json> <output.json>

输入: 详情页数据 rows（格式见 references/input_schema.md）
输出: 分档结果 JSON（供 report.py 生成 HTML 报告）

口径: 全部来自 config.yaml 与 knowledge/（position_map / towns），不硬编码任何个人标准。
判定顺序: 按 config.tiering.order（默认 X → C → B → A，任何一条 X 即 X，其次 C、B，全过即 A）。
"""
import json, os, re, sys, datetime as dt
from pathlib import Path

MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
          "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

ROLE_RE = re.compile(r"^\s*([A-Z][A-Za-z /&'\-]+?)\s*(?:are|will be) responsible for")


def load_yaml(path):
    try:
        import yaml
    except ImportError:
        sys.exit("缺少 PyYAML，请先运行: pip install pyyaml")
    return yaml.safe_load(open(path, encoding="utf-8"))


def md(s):
    """'MM-DD' -> (month, day)"""
    mm, dd = s.split("-")
    return (int(mm), int(dd))


def parse_win(s):
    """'Jun 1, 2027 - Jul 15, 2027' -> (date, date)；单日期 -> (d, d)；失败 None"""
    if not s:
        return None
    m = re.search(r"([A-Z][a-z]{2}) (\d{1,2}) (\d{4})\s*-\s*([A-Z][a-z]{2}) (\d{1,2}) (\d{4})", s)
    if m:
        try:
            return (dt.date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2))),
                    dt.date(int(m.group(6)), MONTHS[m.group(4)], int(m.group(5))))
        except ValueError:
            return None
    m = re.search(r"([A-Z][a-z]{2}) (\d{1,2}) (\d{4})", s)
    if m:
        try:
            d = dt.date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))
            return (d, d)
        except ValueError:
            return None
    return None


def parse_share(share):
    """'3' / '3 people' / '2-3 per bedroom' -> int（区间取上限）；解析失败 None"""
    if not share:
        return None
    m = re.search(r"(\d+)\s*people", share, re.I) or re.search(r"(\d+)\s*per", share, re.I)
    if not m:
        m = re.match(r"^\s*(\d+)\s*(?:-\s*(\d+))?\s*$", share)
    return int(m.group(2) or m.group(1)) if m else None


def enrich(meta):
    """从卡片 rightCol 解析时薪/工时/小费；缺失时退回 _wage/_hours"""
    rc = meta.get("rightCol") or ""
    wm = re.search(r"\$([\d.]+)\s*(\+ tips)?\s*/hour", rc)
    if wm:
        meta["w"] = float(wm.group(1))
        if wm.group(2):
            meta["tips"] = True
    elif meta.get("_wage") is not None:
        meta["w"] = meta["_wage"]
    hm = re.search(r"(\d+)\s*hours\s*/week", rc)
    if hm:
        meta["h"] = int(hm.group(1))
    elif meta.get("_hours") is not None:
        meta["h"] = meta["_hours"]


def canon_title(t, pmap):
    t = (t or "").lower().strip()
    aliases = pmap.get("canon_titles") or {}
    return aliases.get(t, t)


def tier(r, cfg, pmap, towns):
    """对一条岗位行产出全部判定理由 [(档位, 理由)]。
    口径全部来自 config（空值 = 该维度未设置，自动跳过不判定）。"""
    rs = []
    meta = r["meta"]
    loc = f"{meta.get('location') or ''} {meta.get('employer') or ''}"
    season = int(cfg["season_year"]) if cfg.get("season_year") else 0
    arr = cfg.get("arrival") or {}
    dep = cfg.get("departure") or {}
    hou = cfg.get("housing") or {}

    # --- 地域：孤岛/偏远镇一刀切 ---
    if (cfg.get("regions") or {}).get("exclude_island_towns"):
        if any(re.search(p, loc, re.I) for p in towns.get("island_patterns") or []):
            rs.append(("X", "孤岛(排除)"))

    # --- 岗位红线：关键词（岗位名/标题词/职责词）命中标题或详情职责 → X / C ---
    pd = (r.get("posdesc") or "").strip()
    red = cfg.get("redline") or {}
    tline = f"{meta.get('title') or ''} {pd}"
    kw_hit = None
    for k in red.get("free_text_exclude") or []:
        if re.search(k, tline, re.I):
            kw_hit = ("X", f"命中排除词 {k} (排除)")
            break
    if not kw_hit:
        for k in red.get("free_text_redline") or []:
            if re.search(k, tline, re.I):
                kw_hit = ("C", f"命中红线词 {k} (红线)")
                break
    if kw_hit:
        rs.append(kw_hit)

    # --- 实岗判定：详情页 Position Description 首句 ---
    droles = pmap.get("detail_roles") or {}
    m = ROLE_RE.match(pd)
    if m:
        role = m.group(1).strip().lower()
        zh = (droles.get("zh") or {}).get(role, role)
        if role == "grocery clerks" and re.search(r"unloading the grocery truck", pd, re.I):
            rs.append(("X", "实为理货上货(排除)"))
        if role == "fast food crews":
            rs.append(("B", "快餐店员(标注:含清洁/备餐职责)"))
        if role in (droles.get("excluded") or []):
            rs.append(("X", f"实为{zh}(排除)"))
        elif role in (droles.get("redlined") or []):
            rs.append(("C", f"综合酒店岗{zh}(红线:洗衣/客房/后厨/前台轮岗)"))
        elif role in (droles.get("noted") or {}):
            rs.append(("B", f"{zh}(标注:{droles['noted'][role]})"))
        else:
            ct = canon_title(meta.get("title") or "", pmap)
            cr = (droles.get("canon") or {}).get(role, role)
            if ct != cr and ct != "attractions attendant":
                rs.append(("B", f"卡片写{meta.get('title')} 实为{zh}"))
            rs.append(("A", zh))
    else:
        if len(pd) < 20:
            rs.append(("B", "职责未标注(需人工看页)"))
        elif not kw_hit:
            rs.append(("A", "自由文本(未命中关键词)"))

    # --- 到岗窗口 ---
    SW, FW = r.get("SW"), r.get("FW")
    if SW:
        S, E = dt.date.fromisoformat(SW[0]), dt.date.fromisoformat(SW[1])
        pri_s = arr.get("priority_on_or_after")
        if not pri_s:
            rs.append(("A", f"到岗 {S:%m/%d}–{E:%m/%d}（未设到岗线，不判定）"))
        elif arr.get("reject_winter") and cfg.get("season_year") and (E.year > season + 1 or S.month >= 9):
            rs.append(("X", "冬季岗(排除)"))
        else:
            acc_s = arr.get("acceptable_on_or_after") or pri_s
            acc, pri = md(acc_s), md(pri_s)
            if (E.month, E.day) < acc:
                rs.append(("X", f"到岗最晚 {E:%m/%d}({acc_s} 前须到岗,排除)"))
            elif (E.month, E.day) < pri:
                rs.append(("B", f"到岗需提前:最晚 {E:%m/%d}"))
            else:
                rs.append(("A", f"到岗 {S:%m/%d}–{E:%m/%d}({pri_s} 后到岗可 ✓)"))
    elif arr.get("priority_on_or_after"):
        rs.append(("B", "到岗窗口未标注"))

    # --- 离岗窗口 ---
    if FW:
        S2, E2 = dt.date.fromisoformat(FW[0]), dt.date.fromisoformat(FW[1])
        dl_s = dep.get("deadline")
        if not dl_s:
            rs.append(("A", f"离岗 {S2:%m/%d}–{E2:%m/%d}（未设离岗线，不判定）"))
        elif dep.get("reject_off_season_year") and cfg.get("season_year") and E2.year > season + 1:
            rs.append(("X", f"离岗延至 {E2.year}(排除)"))
        else:
            dl = md(dl_s)
            if (S2.month, S2.day) > dl:
                rs.append(("X", f"离岗 {S2:%m/%d} 起({dl_s} 前离岗不满足,排除)"))
            else:
                rs.append(("A", f"离岗 {S2:%m/%d}–{E2:%m/%d}({dl_s} 可离 ✓)"))

    # --- 住宿：室友数 ---
    nshare = parse_share(r.get("share") or "")
    ex, wa = hou.get("exclude_roommates"), hou.get("warn_roommates")
    if nshare is None:
        rs.append(("A", "住宿人数未标注(待公布)"))
    elif ex and nshare >= ex:
        rs.append(("X", f"住宿 {nshare} 人/间(排除)"))
    elif wa and nshare >= wa:
        rs.append(("B", f"住宿 {nshare} 人/间(标注)"))
    elif not ex and not wa:
        rs.append(("A", f"住宿 {nshare} 人/间（未设住宿线，不判定）"))
    else:
        rs.append(("A", "单人间 ★" if nshare <= 1 else "双人间"))

    # --- 住房危机镇：必须雇主住宿 ---
    if hou.get("crisis_towns_require_host_housing"):
        crisis = towns.get("crisis_towns") or []
        if any(re.search(p, loc, re.I) for p in crisis):
            ht = (r.get("housing") or "").strip()
            if not ht or re.search(r"^\s*(none|no housing|n/?a|not provided)\s*$", ht, re.I):
                rs.append(("B", "住房危机镇(须雇主住宿,未见住宿信息)"))
            else:
                rs.append(("A", "住房危机镇(已提供雇主住宿)"))

    # --- 薪资工时线 ---
    w = meta.get("w")
    mw = (cfg.get("wage_hours") or {}).get("min_wage")
    if mw and w is not None and w < float(mw):
        rs.append(("B", f"时薪 ${w}(低于 ${mw},标注)"))
    h = meta.get("h")
    mh = (cfg.get("wage_hours") or {}).get("min_hours")
    if mh and h is not None and h < int(mh):
        rs.append(("B", f"周工时 {h}h(低于 {mh}h,标注)"))

    return rs


def fmt_loc(s):
    """'LELAND, MIMidwest' -> 'Leland, MI · Midwest'（修复州码与 IE 区域粘连 + 城市标题大小写）"""
    if not s:
        return ""
    s = re.sub(r"([A-Z]{2})([A-Z][a-z])", r"\1 · \2", s)
    words = []
    for w in s.split():
        words.append(w if re.fullmatch(r"[A-Z]{2}", w) else (w.capitalize() if w.isupper() else w))
    return " ".join(words)


def load_seen(cfg):
    """history.dedup=true 时返回历轮已核查 slug 集合（只筛新卡：已筛的标 seen 沿用）"""
    hist_cfg = cfg.get("history") or {}
    if not hist_cfg.get("dedup", True):
        return set()
    p = Path(os.path.expanduser(hist_cfg.get("file") or ""))
    if not p or not p.exists():
        return set()
    try:
        store = json.load(open(p, encoding="utf-8"))
    except Exception:
        return set()
    seen = set()
    for r in store.get("rounds") or []:
        seen.update(r.get("slugs") or [])
    return seen


def key_of(reasons, order):
    for t in order:
        if any(tt == t for tt, _ in reasons):
            return t
    return order[-1]


def sort_key(job, sort_by):
    def val(spec):
        if spec == "wage_desc":
            return -(job.get("wage") or 0)
        if spec == "hours_desc":
            return -(job.get("hours") or 0)
        if spec == "rent_asc":
            return job.get("rent") if job.get("rent") is not None else 1e9
        return 0
    return tuple(val(s) for s in sort_by)


def main():
    argv = sys.argv[1:]
    date_override = None                    # 复盘/补录旧数据时传 --date 2026-11-04
    if "--date" in argv:
        i = argv.index("--date")
        date_override = argv[i + 1]
        del argv[i:i + 2]
    cfg_path, in_path, out_path = argv[0], argv[1], argv[2]
    root = Path(__file__).resolve().parent.parent
    cfg = load_yaml(cfg_path)
    pmap = load_yaml(root / "knowledge" / "position_map.yaml")
    towns = load_yaml(root / "knowledge" / "towns.yaml")
    data = json.load(open(in_path, encoding="utf-8"))
    rows = data["rows"] if isinstance(data, dict) and "rows" in data else data

    seen = load_seen(cfg)                  # 只筛新卡：历轮已核查 slug
    jobs = []
    for r in rows:
        meta = r.get("meta") or {}
        enrich(meta)
        reasons = tier(r, cfg, pmap, towns)
        t = key_of(reasons, cfg["tiering"]["order"])
        jobs.append({
            "tier": t,
            "slug": r.get("slug"),
            "title": meta.get("title"),
            "employer": meta.get("employer"),
            "location": fmt_loc(meta.get("location") or ""),
            "href": meta.get("href"),
            "lastVisited": meta.get("lastVisited"),
            "wage": meta.get("w"),
            "hours": meta.get("h"),
            "tips": bool(meta.get("tips")),
            "SW": r.get("SW"),
            "FW": r.get("FW"),
            "rent": meta.get("_rent"),
            "share": r.get("share"),
            "housing": r.get("housing"),
            "reasons": [txt for _, txt in reasons],
        })
        if r.get("slug") and r["slug"] in seen:
            jobs[-1]["seen"] = True        # 已核查过：结果沿用，不进历轮新核查计数

    sort_by = cfg["tiering"].get("sort_by") or ["wage_desc"]
    for j in jobs:
        j["_sk"] = sort_key(j, sort_by)
    jobs.sort(key=lambda j: (j["tier"], j["_sk"]))
    for j in jobs:
        del j["_sk"]

    counts = {k: sum(1 for j in jobs if j["tier"] == k) for k in ["A", "B", "C", "X"]}
    out = {"generated": date_override or dt.date.today().isoformat(), "counts": counts, "jobs": jobs}
    seen_n = sum(1 for j in jobs if j.get("seen"))
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    extra = ""
    if cfg.get("history", {}).get("dedup", True):
        extra = (f" | 沿用 {seen_n}" if seen_n else "") + " | 只筛新卡"
    print("A:", counts["A"], "| B:", counts["B"], "| C:", counts["C"], "| X:", counts["X"],
          "| total:", len(jobs), extra)


if __name__ == "__main__":
    main()
