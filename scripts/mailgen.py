#!/usr/bin/env python3
"""
求职邮件草稿生成：profile.yaml（用户记忆）+ 岗位数据 → 填充 assets/email_template.md。

被 report.py 调用；也可单独用：
    python3 mailgen.py <config.yaml> <screen_result.json> <out.txt>

档案来源（记忆模块）：skill 根目录 profile.yaml 优先；不存在时退回 config.profile（旧格式兼容）。
到岗口径（自动按岗位窗口）:
    - 岗位窗口允许你的到岗日 → "by 7/5 (or earlier if needed)"
    - 岗位窗口更早 → 写岗位窗口的最晚日（诚实口径，不硬凑）
底稿只做确定性填充；发送前的逐雇主个性化由 AI 完成（见 SKILL.md「邮件定稿」）。
"""
import sys, json, datetime as dt
from pathlib import Path


def load_yaml(path):
    import yaml
    return yaml.safe_load(open(path, encoding="utf-8"))


def load_profile(root, cfg):
    """记忆模块：优先读 profile.yaml；无则退回 config.profile（旧格式兼容）"""
    prof = root / "profile.yaml"
    if prof.exists():
        return load_yaml(prof)
    return cfg.get("profile") or {}


def fmt_date(iso, with_year=True):
    d = dt.date.fromisoformat(iso)
    return d.strftime("%B %-d, %Y") if with_year else d.strftime("%B %-d")


def contact_block(cfg, p):
    """email.include_contact=true 时生成签名联系方式块（空项跳过）"""
    if not cfg["email"].get("include_contact"):
        return ""
    c = p.get("contact") or {}
    lines = [f"{k.capitalize()}: {c[k]}" for k in ("email", "phone", "whatsapp") if c.get(k)]
    return ("\n" + "\n".join(lines)) if lines else ""


def build_draft(cfg, profile, job, template):
    p = profile
    email_cfg = cfg["email"]
    position = job["title"] or "this position"
    subject = email_cfg.get("subject_template",
                            "Summer Position Application — {position}").replace("{position}", position)

    arrival = p.get("arrival")
    if arrival:
        if job.get("SW"):
            win_end = dt.date.fromisoformat(job["SW"][1])
            if win_end < dt.date.fromisoformat(arrival):
                arrival_phrase = f"by {win_end.strftime('%B %-d')}"
            else:
                arrival_phrase = f"by {fmt_date(arrival)} (or earlier if needed)"
        else:
            arrival_phrase = f"by {fmt_date(arrival)}"
    else:
        arrival_phrase = "as soon as the position requires"

    exps = p.get("experiences") or []
    exp_block = ""
    if exps:
        exp_block = "My relevant experience:\n" + "\n".join(f"- {e}" for e in exps) + "\n\n"

    video = p.get("video_url") or ""
    video_block = f"A short self-introduction video: {video}\n\n" if video else ""

    closing = email_cfg.get("closing_line",
                            "I am very interested in this position and would be glad to provide "
                            "any additional information. I look forward to hearing from you.")

    body = template.replace("{subject}", subject) \
        .replace("{employer}", job["employer"] or "") \
        .replace("{position}", position) \
        .replace("{location}", job["location"] or "") \
        .replace("{name}", p.get("name") or "") \
        .replace("{school}", p.get("school") or "") \
        .replace("{major}", p.get("major") or "") \
        .replace("{sponsor}", p.get("sponsor") or "") \
        .replace("{video_block}", video_block) \
        .replace("{experience_block}", exp_block) \
        .replace("{arrival_phrase}", arrival_phrase) \
        .replace("{departure}", fmt_date(p["departure"]) if p.get("departure") else "") \
        .replace("{closing_line}", " " + closing if closing else "") \
        .replace("{contact_block}", contact_block(cfg, p))
    lines = body.splitlines()
    if lines and lines[0].startswith("Subject:"):
        body = "\n".join(lines[1:])          # 模板首行是 Subject，正文不重复
    return {"subject": subject, "body": body.strip()}


def main():
    cfg_path, in_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    root = Path(__file__).resolve().parent.parent
    cfg = load_yaml(cfg_path)
    profile = load_profile(root, cfg)
    template = open(root / "assets" / "email_template.md", encoding="utf-8").read()
    data = json.load(open(in_path, encoding="utf-8"))
    jobs = data["jobs"]
    lines = []
    for j in jobs:
        d = build_draft(cfg, profile, j, template)
        lines.append(f"### {j['tier']} {j['employer']} — {j['title']}\nSubject: {d['subject']}\n\n{d['body']}\n")
    open(out_path, "w", encoding="utf-8").write("\n".join(lines))
    print(f"{len(jobs)} 封草稿已写入 {out_path}")


if __name__ == "__main__":
    main()
