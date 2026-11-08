"""prefilter.py — 列表页快照粗筛（首次使用全量筛查的第一步）

用法:
    python3 scripts/collect/prefilter.py <config.yaml> <列表快照.json|capture导出.json> [--out 候选清单.json]

输入:
    - 列表快照：IE 岗位列表接口响应（卡片数组），或 ie_capture.js 的导出文件
      （含 list 字段的 capture 文件会自动取 list 部分）
输出:
    - 候选清单.json：{candidates:[卡片+flags], excluded:[卡片+reasons], summary}
    - 同名 .txt：给人看的候选清单（标题/雇主/地点/薪资工时租金/硬伤标注/链接）

粗筛口径（与 screen.py 一致，全部来自 config.yaml，只用列表卡片上就有的字段）:
    - 活跃度：lastVisited 必须存在且年份 ≥ season_year，否则僵尸岗 → 排除
    - 标题红线：free_text_exclude 命中卡片标题 → 排除
    - 孤岛镇：exclude_island_towns 且命中 knowledge/towns.yaml island_patterns → 排除
    - 软标注（不排除，仅标记进详情后留意）：时薪/周工时低于线、周租金高于线
日期窗口、住宿人数、陷阱实岗等维度必须进详情页才能判定，粗筛不碰。
"""
import json
import re
import sys
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def load_yaml(p):
    import yaml
    return yaml.safe_load(open(p, encoding="utf-8")) or {}


MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def parse_last_visited(card):
    """lastVisited 文本 'Nov 08 2026'（或 lv_iso '2026-11-08'）→ date，解析不了返回 None"""
    iso = card.get("lv_iso")
    if iso:
        try:
            return dt.date.fromisoformat(str(iso)[:10])
        except ValueError:
            pass
    lv = (card.get("lastVisited") or "").strip()
    m = re.match(r"^(\w{3})\s+(\d{1,2})\s+(\d{4})$", lv)
    if m and m.group(1) in MONTHS:
        return dt.date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))
    return None


def parse_right_col(rc):
    """从 rightCol 解析 wage/hours/rent（正则与 screen.py enrich 同源）"""
    out = {}
    wm = re.search(r"\$([\d.]+)\s*(\+ tips)?\s*/hour", rc)
    if wm:
        out["w"] = float(wm.group(1))
        if wm.group(2):
            out["tips"] = True
    hm = re.search(r"(\d+)\s*hours\s*/week", rc)
    if hm:
        out["h"] = int(hm.group(1))
    rm = re.search(r"\$([\d.]+)\s*rent\s*/week", rc)
    if rm:
        out["rent"] = float(rm.group(1))
    return out


def load_cards(path):
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("list"), list):
        data = data["list"]                      # capture 导出文件
    if isinstance(data, dict) and "rows" in data:
        data = data["rows"]
    return [c for c in data if isinstance(c, dict) and c.get("id")]


def main():
    argv = sys.argv[1:]
    out_path = "候选清单.json"
    if "--out" in argv:
        i = argv.index("--out")
        out_path = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) < 2:
        print("用法: python3 scripts/collect/prefilter.py <config.yaml> <列表快照.json> [--out 候选清单.json]")
        sys.exit(1)
    cfg_path, list_path = argv[0], argv[1]

    cfg = load_yaml(cfg_path)
    towns = load_yaml(ROOT / "knowledge" / "towns.yaml")
    cards = load_cards(list_path)

    season = int(cfg["season_year"]) if cfg.get("season_year") else 0
    kw_exclude = [str(k) for k in (cfg.get("redline") or {}).get("free_text_exclude") or []]
    excl_island = bool((cfg.get("regions") or {}).get("exclude_island_towns"))
    islands = towns.get("island_patterns") or []
    mw = (cfg.get("wage_hours") or {}).get("min_wage")
    mh = (cfg.get("wage_hours") or {}).get("min_hours")
    mr = (cfg.get("housing") or {}).get("max_rent_weekly")

    candidates, excluded = [], []
    for c in cards:
        loc = f"{c.get('location') or ''} {c.get('employer') or ''}"
        title = c.get("title") or ""
        reasons, flags = [], []

        lv = parse_last_visited(c)
        if season and (lv is None or lv.year < season):
            reasons.append("僵尸岗(最后活跃 {} · 早于 {} 季)".format(lv.isoformat() if lv else "无记录", season))
        if kw_exclude and any(re.search(k, title, re.I) for k in kw_exclude):
            reasons.append("标题命中排除词")
        if excl_island and any(re.search(p, loc, re.I) for p in islands):
            reasons.append("孤岛镇")

        rc = parse_right_col(c.get("rightCol") or "")
        if mw and rc.get("w") is not None and rc["w"] < float(mw):
            flags.append("时薪 ${:.2f} < ${}".format(rc["w"], float(mw)))
        if mh and rc.get("h") is not None and rc["h"] < int(mh):
            flags.append("工时 {}h < {}h".format(rc["h"], int(mh)))
        if mr and rc.get("rent") is not None and rc["rent"] > float(mr):
            flags.append("周租金 ${:.0f} > ${}".format(rc["rent"], float(mr)))

        row = dict(c)
        row.update(rc)                           # 附上解析出的 w/h/rent 供后续使用
        if reasons:
            row["reasons"] = reasons
            excluded.append(row)
        else:
            row["flags"] = flags
            candidates.append(row)

    out = {
        "generated": dt.date.today().isoformat(),
        "source": list_path,
        "summary": {
            "total": len(cards),
            "candidates": len(candidates),
            "excluded": len(excluded),
            "excluded_reasons": {
                k: sum(1 for x in excluded for q in x["reasons"] if re.split(r"[（(]", q)[0] == k)
                for k in sorted({re.split(r"[（(]", q)[0] for x in excluded for q in x["reasons"]})
            },
        },
        "candidates": candidates,
        "excluded": excluded,
    }
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    txt_path = Path(out_path).with_suffix(".txt")
    lines = ["候选清单（{} / 总 {} 张，{} 张已排除）\n".format(len(candidates), len(cards), len(excluded))]
    for i, c in enumerate(candidates, 1):
        w = c.get("w")
        h = c.get("h")
        r = c.get("rent")
        line = "#{} {} — {}，{}".format(i, c.get("title"), c.get("employer"), c.get("location"))
        bits = []
        if w is not None:
            bits.append("${:.2f}/h".format(w))
        if h is not None:
            bits.append("{}h/w".format(h))
        if r is not None:
            bits.append("${:.0f}rent/w".format(r))
        if bits:
            line += "（" + " ".join(bits) + "）"
        if c.get("flags"):
            line += " ⚠ " + "；".join(c["flags"])
        line += "\n  " + c.get("href", "")
        lines.append(line)
    lines.append("\n说明：以上候选需逐个点开详情页采集（ie_capture.js 或 F12），")
    lines.append("详情采集完成后用 collect_to_input.py 合并成 input.json 交给 run.py。")
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    print("总 {} 张 | 候选 {} 张 | 排除 {} 张".format(len(cards), len(candidates), len(excluded)))
    for r, n in out["summary"]["excluded_reasons"].items():
        print("  X-{}: {}".format(r, n))
    print("候选清单: {}\n可读版:   {}".format(out_path, txt_path))


if __name__ == "__main__":
    main()
