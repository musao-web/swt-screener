#!/usr/bin/env python3
"""
历轮筛查历史：只筛新卡 + HTML 报告里「历轮筛查记录」表的数据源。

用法:
    python3 history.py record <config.yaml> <screen_result.json>
        # 追加/覆盖本轮（幂等：同日期重跑 = 覆盖该轮，保留已有陷阱数/备注）
    python3 history.py update <config.yaml> <YYYY-MM-DD>
        [--traps-added N] [--traps-exclude N] [--note "…"]
        # 知识库维护后补写：本轮陷阱新增数（排除向）、重点备注
    python3 history.py list <config.yaml>
        # 打印历轮

文件位置: config.history.file（默认 screening_history.json）。
只筛新卡: 开启 history.dedup 后 screen.py 读取这里的 slug 集合，
把已核查过的卡标记 seen（沿用），新卡才重复筛查。
"""
import sys, json, os
from pathlib import Path


def load_yaml(path):
    import yaml
    return yaml.safe_load(open(path, encoding="utf-8"))


def hist_path(cfg):
    p = (cfg.get("history") or {}).get("file") or "screening_history.json"
    return Path(os.path.expanduser(p))


def load(hist):
    if hist.exists():
        return json.load(open(hist, encoding="utf-8"))
    return {"rounds": []}


def save(hist, data):
    hist.parent.mkdir(parents=True, exist_ok=True)
    json.dump(data, open(hist, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def find_round(store, date):
    return next((i for i, r in enumerate(store["rounds"]) if r.get("date") == date), None)


def record(cfg, result_path):
    data = json.load(open(result_path, encoding="utf-8"))
    date = data.get("generated")
    jobs = data["jobs"]
    new_slugs = [j.get("slug") for j in jobs if not j.get("seen") and j.get("slug")]
    all_slugs = [j.get("slug") for j in jobs if j.get("slug")]
    entry = {
        "date": date,
        "new": len(new_slugs),
        "carried": sum(1 for j in jobs if j.get("seen")),
        "counts": data.get("counts") or {},
        # 存全部 slug（含沿用）：dedup 的「已核查」记忆，同日重跑也不会被清空
        "slugs": all_slugs,
    }
    hist = hist_path(cfg)
    store = load(hist)
    idx = find_round(store, date)
    if idx is None:
        store["rounds"].append(entry)
    else:
        old = store["rounds"][idx]
        for k in ("traps_added", "traps_exclude", "note"):
            if k in old:
                entry[k] = old[k]
        store["rounds"][idx] = entry
    save(hist, store)
    c = entry["counts"]
    print(f"已记录 {date}：新核查 {entry['new']} 岗（沿用 {entry['carried']}）"
          f" | A {c.get('A', 0)} B {c.get('B', 0)} C {c.get('C', 0)} X {c.get('X', 0)}"
          + ("（覆盖更新）" if idx is not None else ""))


def update(cfg, date, traps_added=None, traps_exclude=None, note=None):
    hist = hist_path(cfg)
    store = load(hist)
    idx = find_round(store, date)
    if idx is None:
        sys.exit(f"history 里没有 {date} 的轮次，先跑: history.py record")
    r = store["rounds"][idx]
    if traps_added is not None:
        r["traps_added"] = int(traps_added)
    if traps_exclude is not None:
        r["traps_exclude"] = int(traps_exclude)
    if note is not None:
        r["note"] = note
    save(hist, store)
    print(f"已更新 {date}：陷阱新增 {r.get('traps_added')} / 排除向 {r.get('traps_exclude')} / 备注: {r.get('note', '—')}")


def list_rounds(cfg):
    store = load(hist_path(cfg))
    for r in store.get("rounds") or []:
        c = r.get("counts") or {}
        print(f"{r['date']} 新核查 {r.get('new')}（沿用 {r.get('carried', 0)}）"
              f" A {c.get('A', 0)} B {c.get('B', 0)} C {c.get('C', 0)} X {c.get('X', 0)}"
              f" 陷阱 +{r.get('traps_added', '—')} 备注 {r.get('note', '—')}")


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    cmd, args = args[0], args[1:]
    if cmd == "record" and len(args) == 2:
        return record(load_yaml(args[0]), args[1])
    if cmd == "update" and len(args) >= 2:
        cfg = load_yaml(args[0])
        kwargs = {}
        i = 2
        while i < len(args):
            if args[i] == "--traps-added" and i + 1 < len(args):
                kwargs["traps_added"], i = args[i + 1], i + 2
            elif args[i] == "--traps-exclude" and i + 1 < len(args):
                kwargs["traps_exclude"], i = args[i + 1], i + 2
            elif args[i] == "--note" and i + 1 < len(args):
                kwargs["note"], i = args[i + 1], i + 2
            else:
                sys.exit(f"未知参数: {args[i]}")
        return update(cfg, args[1], **kwargs)
    if cmd == "list" and len(args) == 1:
        return list_rounds(load_yaml(args[0]))
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
