"""committee_meetings.json 에서 '예산안 등 심사' 회의만 골라 위원회별로 정리한다.
결과: 439th_session/data/budget_schedule.json
 상임위  a=전체회의 상정일, b=[소위 첫날, 끝날], c=전체회의 의결일
 예결위  a=[종합정책질의 첫날, 끝날], b=[부처별 심사 첫날, 끝날], c=전체회의 의결일
"""
import json, re, os

SRC = "439th_session/data/committee_meetings.json"
OUT = "439th_session/data/budget_schedule.json"
FROM = "2026-10-26"   # 국정감사 이후 회의만 본다

def clean(s): return re.sub(r"<br\s*/?>", "\n", s or "")
def is_budget(text): return bool(re.search(r"예산안|기금운용계획안|예비심사", text))
def short(name):
    return re.sub(r"위원회$", "", name or "").strip()

def rng(ds):
    ds = sorted(set(ds)); return [ds[0], ds[-1]] if ds else None

def yc_extract(ms):
    """예결위 회의를 안건·회의명으로 나눔. 못 고른 항목은 넣지 않음(페이지의 일정표 값 유지)."""
    t = lambda m: m["title"] + " " + m["ang"]
    e = {}
    p = [m["d"] for m in ms if "공청회" in t(m)]
    a = [m["d"] for m in ms if "종합정책질의" in t(m)]
    ec = [m["d"] for m in ms if re.search(r"(?<!비)경제부처", t(m))]
    ne = [m["d"] for m in ms if "비경제부처" in t(m)]
    sub = [m["d"] for m in ms if "소위" in m["title"]]
    fin = [m["d"] for m in ms if "소위" not in m["title"] and "의결" in m["ang"] and re.search(r"예산안", m["ang"])]
    if p: e["p"] = min(p)
    if a: e["a"] = rng(a)
    if ec: e["e"] = rng(ec)
    if ne: e["n"] = rng(ne)
    if ec or ne: e["b"] = rng(ec + ne)
    if sub: e["s"] = min(sub)
    if fin: e["c"] = max(fin)
    return e

def yc_compare(ms, plan, today):
    """일정표와 다른 점을 찾아 문장 목록으로 돌려줌."""
    msgs = []
    if not ms: return msgs
    have = {m["d"] for m in ms}
    plan_days = {plan["p"]}
    for k in ("a", "e", "n"):
        a, b = plan[k]; plan_days |= {a, b}
    s0 = plan.get("s")
    for m in ms:
        if m["d"] not in plan_days and (not s0 or m["d"] < s0):
            msgs.append(f"일정표에 없는 예결위 회의가 국회 일정에 올라왔습니다: {m['d']} {m['title']} ({m['ang'].strip().splitlines()[0] if m['ang'].strip() else '안건 미표기'})")
        if s0 and m["d"] >= s0 and "소위" not in m["title"] and "의결" in m["ang"]:
            msgs.append(f"예결위 전체회의 의결 일정이 국회 일정에 올라왔습니다: {m['d']} {m['title']}")
    for d in sorted(plan_days):
        if d <= today and d not in have:
            msgs.append(f"일정표의 예결위 회의({d})가 국회 일정에 없습니다. 연기·취소되었을 수 있습니다.")
    got = yc_extract(ms); mg = yc_merge(plan, got)
    names = {"p": "공청회", "a": "종합정책질의", "e": "경제부처 부별심사", "n": "비경제부처 부별심사", "s": "조정소위 시작"}
    for k, nm in names.items():
        if mg.get(k) != plan.get(k):
            msgs.append(f"{nm} 일정이 바뀌었습니다: 일정표 {plan.get(k)} → 국회 일정 {mg.get(k)} (현황판에 자동 반영)")
    return msgs

ALERTS = "439th_session/data/yc_alerts.json"
PLAN = "439th_session/data/yc_plan.json"

def days(r):
    from datetime import date, timedelta
    if not r: return set()
    if isinstance(r, str): return {r}
    a, b = (date.fromisoformat(x) for x in r); out = set()
    while a <= b: out.add(a.isoformat()); a += timedelta(days=1)
    return out

def yc_merge(plan, got):
    """일정표를 기본으로 두고, 국회 일정에 일정표 범위를 벗어난 날짜가 나온 항목만 국회 일정으로 바꿈.
    (아직 공지 안 된 날 때문에 범위가 줄어드는 일은 없음)"""
    m = {k: plan.get(k) for k in ("p", "a", "e", "n", "s", "c")}
    for k in ("p", "a", "e", "n", "s"):
        if k in got and not (days(got[k]) <= days(plan.get(k))) and not (k == "s" and got[k] >= (plan.get("s") or "")):
            m[k] = got[k]
    if got.get("c"): m["c"] = got["c"]
    bd = days(m.get("e")) | days(m.get("n"))
    m["b"] = [min(bd), max(bd)] if bd else None
    return {k: v for k, v in m.items() if v}

def main():
    src = json.load(open(SRC, encoding="utf-8"))
    by = {}
    yc_rows = []
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
            yc_rows[:] = ms
            out[com] = yc_merge(json.load(open(PLAN, encoding="utf-8")), yc_extract(ms))
            continue
        full = [m for m in ms if "소위" not in m["title"] and is_budget(m["ang"] + m["title"])]
        sub = [m for m in ms if "소위" in m["title"] and (re.search(r"예산|결산", m["title"]) or is_budget(m["ang"]))]
        e = {}
        # 상정: 예산 안건이 있는 첫 전체회의 / 의결: 안건에 '의결'이 있거나, 소위 심사가 끝난 뒤 열린 예산 안건 전체회의
        sub_last = sub[-1]["d"] if sub else None
        votes = [m for m in full if "의결" in m["ang"] or (sub_last and m["d"] > sub_last)]
        intro = [m for m in full if m not in votes]
        if intro: e["a"] = intro[0]["d"]
        elif full and len(full) > 1: e["a"] = full[0]["d"]
        if sub: e["b"] = [sub[0]["d"], sub[-1]["d"]]
        if votes and (not e.get("a") or votes[-1]["d"] > e["a"]): e["c"] = votes[-1]["d"]
        if e: out[com] = e
    # ---- 예결위 일정 변경 감지 ----
    from datetime import datetime, timezone, timedelta
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    plan = json.load(open(PLAN, encoding="utf-8"))
    msgs = yc_compare(yc_rows, plan, today)
    try: hist = json.load(open(ALERTS, encoding="utf-8"))
    except Exception: hist = {"sent": []}
    new = [m for m in msgs if m not in hist["sent"]]
    if new:
        hist["sent"] += new
        hist["last"] = {"at": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"), "messages": new}
        json.dump(hist, open(ALERTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        body = "현황판이 국회 위원회 일정을 불러오다가 예결위 일정이 일정표와 다른 것을 발견했습니다.\n\n" + "\n".join("- " + m for m in new) + \
               "\n\n바뀐 일정은 현황판(깃허브 페이지)에 자동으로 반영됩니다.\n현황판: https://work-hanthor.github.io/kptu/439th_session/#budget\n"
        path = os.environ.get("YC_ALERT_FILE")
        if path: open(path, "w", encoding="utf-8").write(body)
        print("예결위 알림:", new)
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
