"""committee_meetings.json 에서 '예산안 등 심사' 회의만 골라 위원회별로 정리한다.
결과: 439th_session/data/budget_schedule.json
 상임위  a=전체회의 상정일, b=[소위 첫날, 끝날], c=전체회의 의결일
 예결위  a=[종합정책질의 첫날, 끝날], b=[부처별 심사 첫날, 끝날], c=전체회의 의결일
"""
import json, re

SRC = "439th_session/data/committee_meetings.json"
OUT = "439th_session/data/budget_schedule.json"
FROM = "2026-10-26"   # 국정감사 이후 회의만 본다

def clean(s): return re.sub(r"<br\s*/?>", "\n", s or "")
def is_budget(text): return bool(re.search(r"예산안|기금운용계획안|예비심사", text))
def short(name):
    return re.sub(r"위원회$", "", name or "").strip()

def main():
    src = json.load(open(SRC, encoding="utf-8"))
    by = {}
    for r in src["rows"]:
        d = str(r.get("MEETING_DATE") or "")[:10]
        if d < FROM: continue
        com = short(r.get("COMMITTEE_NAME"))
        title, ang = r.get("TITLE") or "", clean(r.get("ANGUN"))
        by.setdefault(com, []).append({"d": d, "title": title, "ang": ang, "url": r.get("LINK_URL2") or ""})
    out = {}
    for com, ms in by.items():
        ms.sort(key=lambda m: m["d"])
        if com == "예산결산특별":
            pq = [m["d"] for m in ms if "종합정책질의" in m["ang"] + m["title"]]
            dep = [m["d"] for m in ms if re.search(r"부별|부처별|경제부처|비경제부처", m["ang"] + m["title"])]
            fin = [m["d"] for m in ms if "전체회의" in m["title"] and re.search(r"예산안", m["ang"]) and "의결" in m["ang"]]
            e = {}
            if pq: e["a"] = [min(pq), max(pq)]
            if dep: e["b"] = [min(dep), max(dep)]
            if fin: e["c"] = max(fin)
            if e: out[com] = e
            continue
        full = [m for m in ms if "소위" not in m["title"] and is_budget(m["ang"] + m["title"])]
        sub = [m for m in ms if "소위" in m["title"] and (re.search(r"예산|결산", m["title"]) or is_budget(m["ang"]))]
        e = {}
        votes = [m for m in full if "의결" in m["ang"]]
        intro = [m for m in full if m not in votes]
        if intro: e["a"] = intro[0]["d"]
        elif full and len(full) > 1: e["a"] = full[0]["d"]
        if sub: e["b"] = [sub[0]["d"], sub[-1]["d"]]
        if votes and (not e.get("a") or votes[-1]["d"] > e["a"]): e["c"] = votes[-1]["d"]
        if e: out[com] = e
    res = {"fetched_at": src.get("fetched_at"), "committees": out}
    old = None
    try: old = json.load(open(OUT, encoding="utf-8")).get("committees")
    except Exception: pass
    if old == out and old is not None:
        print("예산 일정 변경 없음"); return
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("예산 일정 저장:", json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
