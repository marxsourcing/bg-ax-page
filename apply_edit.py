#!/usr/bin/env python3
"""구글 폼 중계 반영: 게시된 응답 CSV에서 페이지별 최신 제출을 읽어 해당 페이지의 <main>을 교체한다.
content 맨 앞에 <!--page:program--> 마커가 있으면 program/index.html, 없으면 index.html 대상."""
import csv, io, os, re, sys, urllib.request

CSV_URL = os.environ.get("CSV_URL", "")
PASS = os.environ.get("PASS", "").strip()
if not CSV_URL or not PASS:
    print("시크릿 미설정 — 건너뜀"); sys.exit(0)

with urllib.request.urlopen(CSV_URL, timeout=30) as r:
    raw = r.read().decode("utf-8")

rows = list(csv.reader(io.StringIO(raw)))
if len(rows) < 2:
    print("제출 없음"); sys.exit(0)

passes = {p.strip() for p in PASS.split(",") if p.strip()}
valid = [row for row in rows[1:] if len(row) >= 3 and row[1].strip() in passes]
rejected = len(rows) - 1 - len(valid)
if rejected:
    print(f"암구호 불일치 제출 {rejected}건 무시")
if not valid:
    print("유효한 제출 없음"); sys.exit(0)

PAGES = {
    "index":   {"file": "index.html",         "marker": None,
                "min_len": 5000, "min_sec": 8},
    "program": {"file": "program/index.html", "marker": "<!--page:program-->",
                "min_len": 3000, "min_sec": 5},
}

def page_of(content):
    return "program" if content.lstrip().startswith(PAGES["program"]["marker"]) else "index"

# 페이지별 마지막 유효 제출
latest = {}
for row in valid:
    ts, content = row[0], row[2]
    latest[page_of(content)] = (ts, content)

# 페이지별 반영 시각 기록: "page ts" 줄 단위 (구형식 = index 단독 ts)
last = {}
if os.path.exists(".last-sync"):
    for line in open(".last-sync", encoding="utf-8").read().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[0] in PAGES:
            last[parts[0]] = parts[1]
        else:
            last["index"] = line  # 구형식 호환

applied, failed = [], False
for page, (ts, content) in latest.items():
    cfg = PAGES[page]
    if ts == last.get(page):
        print(f"[{page}] 이미 반영된 제출"); continue
    if cfg["marker"]:
        content = content.lstrip()[len(cfg["marker"]):]
    checks = [len(content) > cfg["min_len"],
              content.count("<section") >= cfg["min_sec"],
              content.count("<section") == content.count("</section>"),
              'class="hero' in content]
    if not all(checks):
        print(f"[{page}] 안전 점검 실패 — 반영 중단 (len={len(content)}, sec={content.count('<section')})")
        failed = True; continue
    content = content.replace("reveal in", "reveal")
    html = open(cfg["file"], encoding="utf-8").read()
    new_html, n = re.subn(r'(<main id="top">).*?(</main>)',
                          lambda m: m.group(1) + "\n" + content.strip() + "\n" + m.group(2),
                          html, count=1, flags=re.S)
    if n != 1:
        print(f"[{page}] main 블록을 찾지 못함"); failed = True; continue
    open(cfg["file"], "w", encoding="utf-8").write(new_html)
    last[page] = ts
    applied.append(page)
    print(f"[{page}] 반영 완료: 제출 시각 {ts}, content {len(content)}자")

open(".last-sync", "w", encoding="utf-8").write("\n".join(f"{p} {t}" for p, t in sorted(last.items())) + "\n")
if failed and not applied:
    sys.exit(1)
