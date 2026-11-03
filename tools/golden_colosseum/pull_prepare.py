#!/usr/bin/env python3
"""组装一次攻略 pull 的完整 prompt：PULL_PROMPT 模板 + 攻略页正文 + 本地库目录（服装/庇佑全表）。

用法:
  python3 pull_prepare.py --url https://www.gamekee.com/zsca2/<id>.html [--rules rules.txt] [--out prompt.md]
  python3 pull_prepare.py --guide-file guide.html [--out prompt.md]

产出 prompt.md 交给大模型（或 agent）→ 模型输出 spec JSON → validate_spec.py 校验 → gc_setup.py 执行。
攻略页抓取用本机 curl；gamekee 为 JS 站时改用浏览器导出正文存文件后走 --guide-file。
"""
import argparse, json, os, re, sqlite3, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))

def fetch(url):
    out = subprocess.run(["curl", "-sL", "--max-time", "60", "-A",
                          "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", url],
                         capture_output=True, text=True)
    html = out.stdout
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", "\n", html)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()

def catalogs(db_path):
    con = sqlite3.connect(db_path)
    costumes = [dict(character=r[0], costume_name=r[1], costume_id=r[2], element=r[3], damage_type=r[4])
                for r in con.execute(
                    "SELECT ch.name_cn, c.name_cn, c.costume_id, ch.element, ch.damage_type "
                    "FROM costumes c JOIN characters ch ON ch.id = c.character_id ORDER BY c.costume_id")]
    blessings = [dict(name=r[0], cost=r[1], category=r[2])
                 for r in con.execute("SELECT name, cost, category FROM blessings ORDER BY wall_order")]
    con.close()
    return costumes, blessings

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--guide-file")
    ap.add_argument("--rules", help="本季规则页文本（游戏内规则页转录），缺省则让模型标注须人工现读")
    ap.add_argument("--db", default=os.path.expanduser("~/workspace/bd2-db/bd2.sqlite"))
    ap.add_argument("--out", default="pull-prompt.md")
    a = ap.parse_args()
    if a.guide_file:
        raw = open(a.guide_file, encoding="utf-8", errors="ignore").read()
        guide_text = fetch_text(raw) if "<" in raw[:200] else raw
    elif a.url:
        guide_text = fetch(a.url)
    else:
        sys.exit("需要 --url 或 --guide-file")
    if len(guide_text) < 500:
        print("⚠️ 攻略正文过短（可能被 JS 渲染挡住），建议用浏览器导出正文后走 --guide-file", file=sys.stderr)
    costumes, blessings = catalogs(a.db)
    tpl = open(os.path.join(HERE, "PULL_PROMPT.md"), encoding="utf-8").read()
    spec_fmt = open(os.path.join(HERE, "SPEC_FORMAT.md"), encoding="utf-8").read()
    rules_text = open(a.rules, encoding="utf-8").read() if a.rules else "（未提供：season_rules 中无来源的数值填 null 并记入 unresolved）"
    prompt = (tpl.replace("{{GUIDE_TEXT}}", guide_text)
                 .replace("{{COSTUME_CATALOG}}", json.dumps(costumes, ensure_ascii=False))
                 .replace("{{BLESSING_CATALOG}}", json.dumps(blessings, ensure_ascii=False))
                 .replace("{{SEASON_RULES_TEXT}}", rules_text)
                 .replace("{{SPEC_FORMAT}}", spec_fmt))
    open(a.out, "w", encoding="utf-8").write(prompt)
    print(f"prompt -> {a.out}（{len(prompt)} chars；服装目录 {len(costumes)}、庇佑目录 {len(blessings)}）")

def fetch_text(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", "\n", html)
    return re.sub(r"\n\s*\n+", "\n", text).strip()

if __name__ == "__main__":
    main()
