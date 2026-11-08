"""collect_to_input.py — 列表卡 + 详情采集 → 合并成 screen.py 的 input.json

用法:
    python3 scripts/collect/collect_to_input.py <列表快照.json|capture导出.json> <详情.json|详情目录> \
        [--only 候选清单.json] [--out input.json]

输入:
    - 列表：IE 列表接口响应（卡片数组）或 ie_capture.js 导出文件（自动取 list）
    - 详情：ie_capture.js 导出文件（自动取 details），或装满详情 json 的目录
      （兼容 {"value": "<json字符串>"} 包裹形式）
    - --only：只转换粗筛候选清单里的卡（prefilter.py 的产物），其余卡不进 rows
输出:
    - input.json：{"rows":[...], "fetch_fail":[...]}，格式见 references/input_schema.md
      fetch_fail = 选中的卡里没有详情采集的（先补采再跑 run.py）
"""
import json
import re
import sys
import datetime as dt
from pathlib import Path

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
PROFILE_RE = re.compile(r"(\d+)/?$")


def profile_id(href):
    """'/wt/employers/2223/enrollment_profiles/102538' -> '102538'"""
    m = PROFILE_RE.search((href or "").rstrip("/"))
    return m.group(1) if m else None


def parse_window(s):
    """'May 01 2027 - Jul 12 2027' -> ['2027-05-01', '2027-07-12']（解析不了返回 None）"""
    if not s:
        return None
    parts = [p.strip() for p in s.split(" - ")]
    out = []
    for p in parts:
        m = re.match(r"^(\w{3})\s+(\d{1,2})\s+(\d{4})$", p)
        if not m or m.group(1) not in MONTHS:
            return None
        out.append(dt.date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2))).isoformat())
    return out if len(out) == 2 else None


def parse_right_col(rc):
    out = {}
    wm = re.search(r"\$([\d.]+)\s*(\+ tips)?\s*/hour", rc)
    if wm:
        out["_wage"] = float(wm.group(1))
        if wm.group(2):
            out["tips"] = True
    hm = re.search(r"(\d+)\s*hours\s*/week", rc)
    if hm:
        out["_hours"] = int(hm.group(1))
    rm = re.search(r"\$([\d.]+)\s*rent\s*/week", rc)
    if rm:
        out["_rent"] = float(rm.group(1))
    return out


def unwrap(d):
    for _ in range(3):
        if isinstance(d, dict) and isinstance(d.get("value"), str):
            try:
                d = json.loads(d["value"])
            except Exception:
                break
        else:
            break
    return d


def load_cards(path):
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("list"), list):
        data = data["list"]
    return [c for c in data if isinstance(c, dict) and c.get("id")]


def load_details(path):
    """支持 capture 导出文件（.details）或详情目录（*.json，逐个 unwrap）"""
    p = Path(path)
    items = []
    if p.is_dir():
        for f in sorted(p.glob("*.json")):
            try:
                d = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            items.append(unwrap(d))
    else:
        data = json.load(open(p, encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("details"), list):
            items = [unwrap(d) for d in data["details"]]
        else:
            items = [unwrap(data)]
    out = {}
    for d in items:
        if not isinstance(d, dict):
            continue
        pid = profile_id(d.get("url") or "")
        if pid:
            out[pid] = d
    return out


def pair(d, label):
    for k, v in (d.get("pairs") or []):
        if k == label:
            return v
    return None


def main():
    argv = sys.argv[1:]
    out_path = "input.json"
    only_path = None
    if "--out" in argv:
        i = argv.index("--out")
        out_path = argv[i + 1]
        del argv[i:i + 2]
    if "--only" in argv:
        i = argv.index("--only")
        only_path = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) < 2:
        print("用法: python3 scripts/collect/collect_to_input.py <列表.json> <详情.json|目录> [--only 候选清单.json] [--out input.json]")
        sys.exit(1)
    list_path, det_path = argv[0], argv[1]

    cards = load_cards(list_path)
    details = load_details(det_path)

    if only_path:
        only = json.load(open(only_path, encoding="utf-8"))
        only_ids = {profile_id(c.get("href")) for c in only.get("candidates") or []}
        only_ids.discard(None)
        cards = [c for c in cards if profile_id(c.get("href")) in only_ids]

    rows, fails = [], []
    for c in cards:
        pid = profile_id(c.get("href"))
        d = details.get(pid) if pid else None
        if d is None:
            fails.append({"id": c.get("id"), "href": c.get("href"),
                          "title": c.get("title"), "reason": "缺详情采集"})
            continue
        meta = {k: v for k, v in c.items()}
        meta.update(parse_right_col(c.get("rightCol") or ""))
        rows.append({
            "slug": pid,
            "meta": meta,
            "pairs": d.get("pairs") or [],
            "posdesc": pair(d, "Position Description") or "",
            "adddesc": pair(d, "Additional Description") or "",
            "housing": " — ".join(x for x in [pair(d, "Housing Type"), pair(d, "Description")] if x),
            "rent": pair(d, "Rent") or "",
            "share": pair(d, "Number of people sharing a bedroom") or "",
            "SW": parse_window(pair(d, "Start")),
            "FW": parse_window(pair(d, "Finish")),
            "listings": len(d.get("listings") or []),
        })

    out = {"rows": rows, "fetch_fail": fails}
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("rows {} 张 | fetch_fail {} 张（先补采详情）".format(len(rows), len(fails)))
    for f in fails[:10]:
        print("  缺详情: {} {} — {}".format(f.get("href"), f.get("title"), f.get("reason")))
    if len(fails) > 10:
        print("  …共 {} 张".format(len(fails)))
    print("输出: {} → 交给 run.py：python3 scripts/run.py config.yaml {}".format(out_path, out_path))


if __name__ == "__main__":
    main()
