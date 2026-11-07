#!/usr/bin/env python3
"""
生成 webapp/data.js（工作台页面的知识库快照）。
knowledge/ 更新后重跑：python3 scripts/build_site_data.py
"""
import json, re
from pathlib import Path

import yaml

root = Path(__file__).resolve().parent.parent
webapp = root / "webapp"

contacts = yaml.safe_load(open(root / "knowledge" / "contacts.yaml", encoding="utf-8"))
towns = yaml.safe_load(open(root / "knowledge" / "towns.yaml", encoding="utf-8"))
traps_text = open(root / "knowledge" / "traps.md", encoding="utf-8").read()
m = re.search(r"累计\s*(\d+)\s*处记录\s*/\s*(\d+)\s*处排除向（截至\s*([\d-]+)", traps_text)
traps = {"total": int(m.group(1)), "exclude": int(m.group(2)), "asof": m.group(3)} if m else None

data = {
    "contacts": contacts.get("employers") or {},
    "fallback": contacts.get("fallback_channels") or [],
    "safety": towns.get("safety") or {},
    "traps": traps,
}
out = "// 由 scripts/build_site_data.py 生成，勿手改；knowledge/ 更新后重跑\n"
out += "window.SITE_DATA = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n"
webapp.mkdir(exist_ok=True)
open(webapp / "data.js", "w", encoding="utf-8").write(out)
print("webapp/data.js 已生成：", len(data["contacts"]), "雇主联系方式 /",
      len(data["safety"]), "镇治安 / 陷阱", data["traps"])
