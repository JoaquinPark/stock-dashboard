"""
fetch_stocks.py
네이버 금융 일별시세 API를 사용하여 확정 종가를 수집합니다.

핵심 변경:
  - 종가: finance.naver.com/item/sise_day.naver (일별시세 — 장 종료 후 확정값)
  - 시총/52주/PER/PBR: finance.naver.com/item/main.nhn
"""

import json
import time
import re
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

STOCKS = {
    "hyundai": [
        {"code": "005380", "name": "현대자동차"},
        {"code": "000270", "name": "기아"},
        {"code": "012330", "name": "현대모비스"},
        {"code": "064350", "name": "현대로템"},
        {"code": "000720", "name": "현대건설"},
        {"code": "086280", "name": "현대글로비스"},
        {"code": "307950", "name": "현대오토에버"},
        {"code": "004020", "name": "현대제철"},
        {"code": "011210", "name": "현대위아"},
        {"code": "214320", "name": "이노션"},
        {"code": "001500", "name": "현대차증권"},
        {"code": "004560", "name": "현대비앤지스틸"},
    ],
    "samsung": [
        {"code": "005930", "name": "삼성전자"},
        {"code": "207940", "name": "삼성바이오로직스"},
        {"code": "032830", "name": "삼성생명"},
        {"code": "028260", "name": "삼성물산"},
        {"code": "009150", "name": "삼성전기"},
        {"code": "006400", "name": "삼성SDI"},
        {"code": "010140", "name": "삼성중공업"},
        {"code": "000810", "name": "삼성화재"},
        {"code": "0126Z0", "name": "삼성에피스홀딩스"},
        {"code": "018260", "name": "삼성에스디에스"},
        {"code": "016360", "name": "삼성증권"},
        {"code": "028050", "name": "삼성E&A"},
        {"code": "029780", "name": "삼성카드"},
    ],
    "sk": [
        {"code": "000660", "name": "SK하이닉스"},
        {"code": "402340", "name": "SK스퀘어"},
        {"code": "034730", "name": "SK㈜"},
        {"code": "096770", "name": "SK이노베이션"},
        {"code": "017670", "name": "SK텔레콤"},
        {"code": "326030", "name": "SK바이오팜"},
        {"code": "011790", "name": "SKC"},
        {"code": "302440", "name": "SK바이오사이언스"},
        {"code": "018670", "name": "SK가스"},
        {"code": "361610", "name": "SK아이이테크놀로지"},
        {"code": "395400", "name": "SK리츠"},
        {"code": "475150", "name": "SK이터닉스"},
        {"code": "100090", "name": "SK오션플랜트"},
        {"code": "001740", "name": "SK네트웍스"},
        {"code": "006120", "name": "SK디스커버리"},
        {"code": "285130", "name": "SK케미칼"},
        {"code": "210980", "name": "SK디앤디"},
    ],
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://finance.naver.com/",
})


def parse_num(text):
    if not text:
        return None
    t = text.strip().replace(",", "").replace("+", "").replace("%", "")
    try:
        return float(t)
    except ValueError:
        return None


def fetch_closing_price(code):
    """
    네이버 금융 일별시세에서 가장 최근 거래일 종가(확정값)를 가져옵니다.
    URL: https://finance.naver.com/item/sise_day.naver?code=005380&page=1
    테이블 첫 행 = 가장 최근 거래일, 두 번째 열 = 종가
    """
    url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
    try:
        res = SESSION.get(url, timeout=10)
        res.encoding = "euc-kr"
        soup = BeautifulSoup(res.text, "html.parser")

        for row in soup.select("table.type2 tr"):
            tds = row.select("td")
            if len(tds) < 2:
                continue
            date_txt  = tds[0].get_text(strip=True)
            close_txt = tds[1].get_text(strip=True)
            # 날짜 형식 YYYY.MM.DD 확인
            if re.match(r"\d{4}\.\d{2}\.\d{2}", date_txt):
                price = parse_num(close_txt)
                if price and price > 0:
                    return int(price), date_txt
    except Exception as e:
        print(f"    [종가 오류] {code}: {e}")
    return None, None


def fetch_stock_info(code):
    """
    네이버 금융 종목 메인 페이지에서 시총, 52주 고저가, PER, PBR 수집
    """
    url = f"https://finance.naver.com/item/main.nhn?code={code}"
    mcap = high52 = low52 = per = pbr = None
    try:
        res = SESSION.get(url, timeout=10)
        res.encoding = "euc-kr"
        soup = BeautifulSoup(res.text, "html.parser")

        for dt in soup.select("table.no_info dt"):
            label = dt.get_text().replace(" ", "")
            dd = dt.find_next_sibling("dd")
            if not dd:
                continue
            raw = dd.get_text(strip=True)

            if "시가총액" in label:
                jo  = re.search(r"([\d,]+)조", raw)
                eok = re.search(r"([\d,]+)억", raw)
                val = 0.0
                if jo:
                    val += float(jo.group(1).replace(",", ""))
                if eok:
                    val += float(eok.group(1).replace(",", "")) / 10000
                mcap = round(val, 2) if val > 0 else None

            elif "52주최고" in label:
                high52 = parse_num(raw)

            elif "52주최저" in label:
                low52 = parse_num(raw)

        for tag in soup.select("em#_per, em#_pbr"):
            val = parse_num(tag.get_text())
            if tag.get("id") == "_per":
                per = val
            elif tag.get("id") == "_pbr":
                pbr = val

    except Exception as e:
        print(f"    [종목정보 오류] {code}: {e}")

    return {
        "marketCap": mcap,
        "h52": int(high52) if high52 else None,
        "l52": int(low52) if low52 else None,
        "per": round(per, 2) if per else None,
        "pbr": round(pbr, 2) if pbr else None,
    }


def main():
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)

    result = {
        "updated": now.strftime("%Y-%m-%d %H:%M KST"),
        "date_label": None,
        "stocks": {},
    }

    all_stocks = [(g, s) for g, items in STOCKS.items() for s in items]
    print(f"총 {len(all_stocks)}개 종목 수집 ({now.strftime('%Y-%m-%d %H:%M KST')})\n")

    latest_date = None

    for group, s in all_stocks:
        code, name = s["code"], s["name"]
        print(f"  [{group}] {name} ({code})", end=" ... ")

        price, trade_date = fetch_closing_price(code)
        if trade_date and not latest_date:
            latest_date = trade_date
        time.sleep(0.4)

        info = fetch_stock_info(code)
        time.sleep(0.4)

        result["stocks"][code] = {"name": name, "group": group, "price": price, **info}
        print(f"종가={price:,}원" if price else "종가=수집실패")

    # 날짜 레이블: "2026.04.22" → "2026년 04월 22일"
    if latest_date:
        p = latest_date.split(".")
        result["date_label"] = f"{p[0]}년 {p[1]}월 {p[2]}일"
    else:
        result["date_label"] = now.strftime("%Y년 %m월 %d일")

    with open("stock-data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료! 기준일: {result['date_label']}")


if __name__ == "__main__":
    main()
