"""국회 위원회 회의 일정(열린국회정보 nrsldhjpaemrmolla)을 받아 저장한다.
- 결과: 439th_session/data/committee_meetings.json (2026년 10~12월 회의 전체, 날짜순)
- 인증키는 GitHub Secrets의 ASSEMBLY_API_KEY 에서 읽는다.
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

API = "https://open.assembly.go.kr/portal/openapi/nrsldhjpaemrmolla"
KEY = os.environ.get("ASSEMBLY_API_KEY", "").strip()
UNIT_CD = "100022"                      # 제22대 국회
MONTHS = ["2026-10", "2026-11", "2026-12"]
OUT = "439th_session/data/committee_meetings.json"

STATUS = "439th_session/data/fetch_status.json"
LOG = []

def call(params):
    full = {"KEY": KEY, "Type": "json", "pIndex": 1, "pSize": 100, "UNIT_CD": UNIT_CD, **params}
    q = urllib.parse.urlencode(full)
    shown = {k: v for k, v in full.items() if k != "KEY"}
    try:
        req = urllib.request.Request(API + "?" + q, headers={"User-Agent": "Mozilla/5.0 (kptu-board)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "replace")
    except Exception as e:
        LOG.append({"params": shown, "error": repr(e)}); raise
    try:
        data = json.loads(raw)
    except Exception:
        LOG.append({"params": shown, "raw": raw[:800]}); raise SystemExit("JSON이 아닌 응답")
    LOG.append({"params": shown, "head": raw[:400]})
    return data

def fetch_month(month):
    rows, page = [], 1
    while True:
        data = call({"pIndex": page, "pSize": 1000, "MEETING_DATE": month})
        if "RESULT" in data:                       # 자료 없음 등
            code = data["RESULT"].get("CODE")
            if code == "INFO-200": return rows
            raise SystemExit(f"API 오류 {code}: {data['RESULT'].get('MESSAGE')}")
        body = data["nrsldhjpaemrmolla"]
        head = body[0]["head"]
        total = head[0]["list_total_count"]
        res = head[1]["RESULT"]
        if res.get("CODE") != "INFO-000":
            raise SystemExit(f"API 오류 {res.get('CODE')}: {res.get('MESSAGE')}")
        rows += body[1]["row"]
        if len(rows) >= total: return rows
        page += 1; time.sleep(0.5)

def main():
    if not KEY: raise SystemExit("ASSEMBLY_API_KEY 가 설정되지 않았습니다 (Settings → Secrets and variables → Actions).")
    allrows = []
    for m in MONTHS:
        got = fetch_month(m); print(m, len(got), "건"); allrows += got
    allrows.sort(key=lambda r: (str(r.get("MEETING_DATE")), str(r.get("MEETING_TIME")), str(r.get("COMMITTEE_NAME"))))
    kst = timezone(timedelta(hours=9))
    out = {"fetched_at": datetime.now(kst).isoformat(timespec="seconds"), "count": len(allrows), "rows": allrows}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    old = None
    if os.path.exists(OUT):
        try: old = json.load(open(OUT, encoding="utf-8")).get("rows")
        except Exception: old = None
    if old == allrows:
        print("변경 없음"); return
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("저장:", OUT, len(allrows), "건")

def write_status(ok, msg):
    kst = timezone(timedelta(hours=9))
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    json.dump({"at": datetime.now(kst).isoformat(timespec="seconds"), "ok": ok, "message": msg, "calls": LOG[-6:]},
              open(STATUS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    try:
        main(); write_status(True, "성공")
    except BaseException as e:
        print("실패:", e); write_status(False, str(e))
        sys.exit(1)
