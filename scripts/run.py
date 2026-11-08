#!/usr/bin/env python3
"""
swt-screener 一键管线：筛查分档 → 记录历轮 → 生成 HTML 报告并自动打开

用法:
    python3 scripts/run.py <config.yaml> <input.json> [report.html] [--date YYYY-MM-DD] [--no-open]

- 默认报告名 report_YYYY-MM-DD.html，输出到当前目录（也可用第 3 个参数指定）
- --date：复盘/补录旧数据，把生成日期写成实际筛查日（默认写当天）
- --no-open：不自动打开浏览器（测试 / CI 用）
"""
import subprocess, sys, webbrowser, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    argv = sys.argv[1:]
    no_open = "--no-open" in argv
    argv = [a for a in argv if a != "--no-open"]
    date_override = None
    if "--date" in argv:
        i = argv.index("--date")
        date_override = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) < 2:
        print("用法: python3 scripts/run.py <config.yaml> <input.json> [report.html] [--date YYYY-MM-DD] [--no-open]")
        sys.exit(1)
    cfg_path, in_path = argv[0], argv[1]
    out_path = argv[2] if len(argv) > 2 else f"report_{(date_override or dt.date.today().isoformat())}.html"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)  # 输出目录不存在时自动创建
    result_path = "screen_result.json"  # 与手动流程一致：当前目录

    py = sys.executable
    steps = [
        [py, str(ROOT / "scripts" / "screen.py"), cfg_path, in_path, result_path]
        + (["--date", date_override] if date_override else []),
        [py, str(ROOT / "scripts" / "history.py"), "record", cfg_path, result_path],
        [py, str(ROOT / "scripts" / "report.py"), cfg_path, result_path, out_path],
    ]
    for cmd in steps:
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print(f"步骤失败: {' '.join(cmd)}")
            sys.exit(r.returncode)
    print(f"一键完成 → 报告: {out_path}")
    if not no_open:
        webbrowser.open(Path(out_path).resolve().as_uri())


if __name__ == "__main__":
    main()
