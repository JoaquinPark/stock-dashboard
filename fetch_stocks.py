"""
fetch_stocks.py
네이버 금융에서 전일 종가, 시총, 52주 고저가, PER, PBR을 수집하여
stock-data.json으로 저장합니다.
"""

import json
import time
import re
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

# ── 종목 마스터 ──────────────────────────────────────────
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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Referer": "https://finance.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def parse_number(text):
    """'1,234,567' 또는 '1,234.56' 형태의 문자열을 숫자로 변환"""
    if not text:
        return None
    text = text.strip().replace(",", "").replace("+", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def fetch_stock(code):
    """네이버 금융 종목 페이지에서 데이터 수집"""
    url = f"https://finance.naver.com/item/main.nhn?code={code}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = "euc-kr"
        soup = BeautifulSoup(res.text, "html.parser")

        # ── 현재가(전일 종가) ──
        price_tag = soup.select_one("p.no_today .blind")
        price = parse_number(price_tag.get_text()) if price_tag else None

        # ── 시가총액 ──
        mcap = None
        for dt in soup.select("table.no_info dt"):
            if "시가총액" in dt.get_text():
                dd = dt.find_next_sibling("dd")
                if dd:
                    # "12조 3,456억" 형태 → 조 단위 float
                    raw = dd.get_text(strip=True)
                    match_jo = re.search(r"([\d,]+)조", raw)
                    match_eok = re.search(r"([\d,]+)억", raw)
                    val = 0.0
                    if match_jo:
                        val += float(match_jo.group(1).replace(",", ""))
                    if match_eok:
                        val += float(match_eok.group(1).replace(",", "")) / 10000
                    mcap = round(val, 2) if val > 0 else None
                break

        # ── 52주 최고/최저 ──
        high52 = low52 = None
        for dt in soup.select("table.no_info dt"):
            text = dt.get_text()
            if "52주최고" in text.replace(" ", ""):
                dd = dt.find_next_sibling("dd")
                if dd:
                    high52 = parse_number(dd.get_text())
            if "52주최저" in text.replace(" ", ""):
                dd = dt.find_next_sibling("dd")
                if dd:
                    low52 = parse_number(dd.get_text())

        # ── PER / PBR ──
        per = pbr = None
        for tag in soup.select("em#_per, em#_pbr"):
            val = parse_number(tag.get_text())
            if tag.get("id") == "_per":
                per = val
            elif tag.get("id") == "_pbr":
                pbr = val

        return {
            "price": int(price) if price else None,
            "marketCap": mcap,
            "h52": int(high52) if high52 else None,
            "l52": int(low52) if low52 else None,
            "per": round(per, 2) if per else None,
            "pbr": round(pbr, 2) if pbr else None,
        }

    except Exception as e:
        print(f"  ERROR {code}: {e}")
        return {}


def main():
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    date_str = now.strftime("%Y년 %m월 %d일")

    result = {
        "updated": now.strftime("%Y-%m-%d %H:%M KST"),
        "date_label": date_str,
        "stocks": {},
    }

    all_stocks = []
    for group, items in STOCKS.items():
        for s in items:
            all_stocks.append((group, s))

    print(f"총 {len(all_stocks)}개 종목 수집 시작...")

    for group, s in all_stocks:
        code = s["code"]
        name = s["name"]
        print(f"  [{group}] {name} ({code}) ...", end=" ")
        data = fetch_stock(code)
        result["stocks"][code] = {
            "name": name,
            "group": group,
            **data,
        }
        print(f"종가={data.get('price', '?'):,}" if data.get("price") else "실패")
        time.sleep(0.4)   # 서버 부하 방지

    # stock-data.json 저장
    with open("stock-data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n완료! stock-data.json 저장됨 ({date_str})")


if __name__ == "__main__":
    main()
