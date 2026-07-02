import csv
import html
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "202507-202607 가계부.CSV.csv"
OUT_PATH = ROOT / "2026-07-02-가계부-대시보드-임원보고서-v3.html"

FUEL_KEYWORDS = ("주유소", "에너지", "오일뱅크", "석유", "주유")
TOLL_KEYWORDS = ("대교", "고속도로", "브릿지", "브리지", "도로")
TOLL_PAYMENT_METHOD = "현대카드ZERO Edition2 포인트형 하이패스"
CARD_ISSUER_BY_CONTENT = {
    "하나카드": "하나카드",
    "하나카드결제": "하나카드",
    "현대카드": "현대카드",
    "삼성카드": "삼성카드",
    "삼성카드(주)": "삼성카드",
}


def parse_amount(value):
    if value is None or value == "":
        return None
    return float(str(value).replace(",", ""))


def month_of(row):
    raw = row["날짜"]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m")
    except ValueError:
        return None


def money(value):
    return f"{int(round(value)):,}"


def short_month(month):
    year, mon = month.split("-")
    return f"{year[2:]}-{mon}" if mon in ("07", "01") else mon


def bar_chart(values, color, ymax, ylabels, label):
    months = [v["month"] for v in values]
    plot_x, base_y = 70, 360
    bar_w, step = 43, 63
    top_y, height = 60, 300
    rects = []
    for i, item in enumerate(values):
        h = 0 if ymax == 0 else item[label] / ymax * height
        x = 84 + i * step
        y = base_y - h
        rects.append(f'<rect x="{x}" y="{y:.2f}" width="{bar_w}" height="{h:.2f}" fill="{color}"/>')
    ticks = "".join(
        f'<text x="{105.5 + i * step}" y="383">{short_month(m)}</text>' for i, m in enumerate(months)
    )
    return f"""
      <svg viewBox="0 0 940 430" role="img" aria-label="{html.escape(label)} 월별 막대 차트">
        <line x1="70" y1="360" x2="900" y2="360" stroke="#d7dbe7"/>
        <line x1="70" y1="60" x2="70" y2="360" stroke="#d7dbe7"/>
        <text x="18" y="64" font-size="12" fill="#626b7f">{ylabels[0]}</text>
        <text x="18" y="214" font-size="12" fill="#626b7f">{ylabels[1]}</text>
        <text x="37" y="364" font-size="12" fill="#626b7f">0</text>
        <g>{''.join(rects)}</g>
        <g fill="#1f2430" font-size="11" text-anchor="middle">{ticks}</g>
      </svg>"""


def stacked_card_chart(values, ymax):
    colors = {"하나카드": "#3f7d5a", "현대카드": "#2e4780", "삼성카드": "#a84f4f"}
    base_y, height, bar_w, step = 360, 300, 43, 63
    parts = []
    for i, item in enumerate(values):
        current_y = base_y
        for issuer in ("하나카드", "현대카드", "삼성카드"):
            amount = item[issuer]
            if amount <= 0:
                continue
            h = amount / ymax * height
            y = current_y - h
            x = 84 + i * step
            parts.append(f'<rect x="{x}" y="{y:.2f}" width="{bar_w}" height="{h:.2f}" fill="{colors[issuer]}"/>')
            current_y = y
    ticks = "".join(
        f'<text x="{105.5 + i * step}" y="383">{short_month(item["month"])}</text>'
        for i, item in enumerate(values)
    )
    return f"""
      <svg viewBox="0 0 940 430" role="img" aria-label="월별 카드대금 누적 막대 차트">
        <line x1="70" y1="360" x2="900" y2="360" stroke="#d7dbe7"/>
        <line x1="70" y1="60" x2="70" y2="360" stroke="#d7dbe7"/>
        <text x="18" y="64" font-size="12" fill="#626b7f">4.0M</text>
        <text x="18" y="214" font-size="12" fill="#626b7f">2.0M</text>
        <text x="37" y="364" font-size="12" fill="#626b7f">0</text>
        <g>{''.join(parts)}</g>
        <g fill="#1f2430" font-size="11" text-anchor="middle">{ticks}</g>
        <g font-size="13">
          <rect x="690" y="50" width="12" height="12" fill="#3f7d5a"/><text x="708" y="61">하나카드</text>
          <rect x="780" y="50" width="12" height="12" fill="#2e4780"/><text x="798" y="61">현대카드</text>
          <rect x="870" y="50" width="12" height="12" fill="#a84f4f"/><text x="888" y="61">삼성카드</text>
        </g>
      </svg>"""


def main():
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8-sig", newline="")))
    monthly = defaultdict(lambda: {
        "fuel": 0.0,
        "toll": 0.0,
        "하나카드": 0.0,
        "현대카드": 0.0,
        "삼성카드": 0.0,
        "card_total": 0.0,
    })
    counts = defaultdict(int)
    failed_dates = 0
    failed_amounts = 0
    non_krw = set()
    overlaps = 0

    for row in rows:
        month = month_of(row)
        if month is None:
            failed_dates += 1
            continue
        amount = parse_amount(row["금액"])
        if amount is None:
            failed_amounts += 1
            continue
        if row.get("화폐") != "KRW":
            non_krw.add(row.get("화폐", ""))
        cost = abs(amount)
        content = row.get("내용", "")
        is_fuel = row.get("타입") == "지출" and row.get("대분류") == "자동차" and any(k in content for k in FUEL_KEYWORDS)
        is_toll = row.get("결제수단") == TOLL_PAYMENT_METHOD or any(k in content for k in TOLL_KEYWORDS)
        if is_fuel and amount < 0:
            monthly[month]["fuel"] += cost
            counts["fuel"] += 1
        if is_toll and amount < 0:
            monthly[month]["toll"] += cost
            counts["toll"] += 1
        if is_fuel and is_toll and amount < 0:
            overlaps += 1
        issuer = CARD_ISSUER_BY_CONTENT.get(content)
        if issuer and amount < 0:
            monthly[month][issuer] += cost
            monthly[month]["card_total"] += cost
            counts["card"] += 1
            counts[f"card_{issuer}"] += 1

    months = sorted(monthly)
    data = []
    for month in months:
        item = {"month": month}
        item.update(monthly[month])
        data.append(item)

    total_fuel = sum(item["fuel"] for item in data)
    total_toll = sum(item["toll"] for item in data)
    total_card = sum(item["card_total"] for item in data)
    peak_card = max(data, key=lambda x: x["card_total"])
    peak_toll = max(data, key=lambda x: x["toll"])
    latest_month = months[-1]

    table_rows = "\n".join(
        f"<tr><td>{item['month']}</td><td>{money(item['fuel'])}</td><td>{money(item['toll'])}</td>"
        f"<td>{money(item['card_total'])}</td><td>{money(item['하나카드'])}</td>"
        f"<td>{money(item['현대카드'])}</td><td>{money(item['삼성카드'])}</td></tr>"
        for item in data
    )

    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>가계부 자동차/카드대금 임원 보고서</title>
  <style>
    :root {{ --surface:#fcfcfd; --ink:#1f2430; --muted:#626b7f; --grid:#e5e8f0; --blue:#2e4780; --gold:#b8a037; --green:#3f7d5a; --red:#a84f4f; }}
    body {{ margin:0; background:var(--surface); color:var(--ink); font-family:"Segoe UI","Noto Sans KR",Arial,sans-serif; line-height:1.55; }}
    main {{ max-width:1120px; margin:0 auto; padding:48px 40px 64px; }}
    h1 {{ font-size:44px; line-height:1.15; margin:0 0 12px; letter-spacing:0; }}
    .subtitle {{ color:var(--muted); font-size:18px; margin:0 0 32px; }}
    h2 {{ font-size:28px; margin:44px 0 14px; letter-spacing:0; }}
    p, li {{ font-size:17px; }}
    .metric-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin:24px 0 20px; }}
    .metric-card {{ border:1px solid var(--grid); border-radius:8px; padding:16px; background:#fff; }}
    .metric-card .label {{ color:var(--muted); font-size:14px; margin-bottom:6px; }}
    .metric-card .value {{ font-size:25px; font-weight:700; }}
    .metric-card .note {{ color:var(--muted); font-size:13px; margin-top:4px; }}
    .chart {{ margin:16px 0 24px; border:1px solid var(--grid); border-radius:8px; background:#fff; padding:14px; }}
    svg {{ width:100%; height:auto; display:block; }}
    table {{ width:100%; border-collapse:collapse; margin:16px 0 24px; background:#fff; border:1px solid var(--grid); font-size:14px; }}
    th, td {{ padding:9px 10px; border-bottom:1px solid var(--grid); text-align:right; white-space:nowrap; }}
    th:first-child, td:first-child {{ text-align:left; }}
    th {{ background:#f3f5f9; font-weight:650; }}
    .source-note {{ color:var(--muted); font-size:14px; }}
    .caveat {{ border-left:4px solid var(--gold); padding:10px 14px; background:#fffaf0; margin:18px 0; }}
  </style>
</head>
<body>
<main>
  <h1>가계부 자동차/카드대금 임원 보고서</h1>
  <p class="subtitle">202507-202607 가계부, 2025-07부터 2026-07까지의 월별 지출 흐름. 금액 단위는 원(KRW).</p>
  <section>
    <h2>Executive Summary</h2>
    <ul>
      <li><strong>자동차 관련 반복 지출은 통행료가 주유비에 근접하거나 일부 월에는 더 큽니다.</strong> 전체 기간 주유비는 {money(total_fuel)}원, 하이패스 통행료는 {money(total_toll)}원입니다.</li>
      <li><strong>{peak_toll['month']}은 통행료가 {money(peak_toll['toll'])}원으로 기간 내 최고치입니다.</strong> 같은 달 주유비도 {money(peak_toll['fuel'])}원으로 높아 자동차 이동 비용이 동시에 커졌습니다.</li>
      <li><strong>카드대금은 변형 표기 반영 후 총 {money(total_card)}원입니다.</strong> 하나카드결제와 삼성카드(주)를 각각 하나카드/삼성카드로 재분류했으며, {peak_card['month']}이 {money(peak_card['card_total'])}원으로 가장 큽니다.</li>
      <li><strong>분류 기준상 일부 주유소명은 통행료 키워드와 겹칩니다.</strong> 내용에 “고속도로”가 들어간 주유소는 주유비와 통행료 규칙이 동시에 걸릴 수 있어 {overlaps}건을 caveat로 표시했습니다.</li>
    </ul>
  </section>
  <section>
    <h2>Topline Metrics</h2>
    <div class="metric-grid">
      <div class="metric-card"><div class="label">집계 기간</div><div class="value">{months[0]} ~ {latest_month}</div><div class="note">원본 {len(rows):,}행</div></div>
      <div class="metric-card"><div class="label">총 주유비</div><div class="value">{money(total_fuel)}원</div><div class="note">{counts['fuel']}건</div></div>
      <div class="metric-card"><div class="label">총 하이패스 통행료</div><div class="value">{money(total_toll)}원</div><div class="note">{counts['toll']}건</div></div>
      <div class="metric-card"><div class="label">총 카드대금</div><div class="value">{money(total_card)}원</div><div class="note">{counts['card']}건</div></div>
    </div>
  </section>
  <section>
    <h2>Fuel spending rose into spring 2026 before dropping in the partial July month</h2>
    <p>주유비는 2026-04에 390,000원으로 정점을 찍었고, 2026-06에도 312,600원으로 높은 수준을 유지했습니다. 2026-07은 7월 2일까지의 부분월이라 비교 시 낮게 보아야 합니다.</p>
    <figure class="chart"><figcaption>월별 주유비, 원(KRW)</figcaption>{bar_chart(data, "#2e4780", 400000, ("400k", "200k"), "fuel")}</figure>
  </section>
  <section>
    <h2>Toll spend peaked in June and should be monitored separately from fuel</h2>
    <p>하이패스 통행료는 월별 건수가 많고 금액 변동도 독립적입니다. 2026-06 통행료는 319,420원으로 가장 높아, 주유비와 합산하지 않고 별도 관리 지표로 보는 것이 적절합니다.</p>
    <figure class="chart"><figcaption>월별 하이패스 통행료, 원(KRW)</figcaption>{bar_chart(data, "#b8a037", 320000, ("320k", "160k"), "toll")}</figure>
  </section>
  <section>
    <h2>Card payments increase materially after mapping variant merchant names</h2>
    <p>하나카드결제 8건과 삼성카드(주) 4건을 카드대금으로 반영했습니다. 이 변경으로 2025-08, 2025-10~2026-05의 카드대금 흐름이 기존 보고서보다 커졌습니다.</p>
    <figure class="chart"><figcaption>월별 신용카드 청구사별 카드대금, 원(KRW)</figcaption>{stacked_card_chart(data, 4000000)}</figure>
  </section>
  <section>
    <h2>Monthly audit table</h2>
    <p>아래 표는 대시보드와 슬라이드의 모든 핵심 수치를 동일한 월별 집계에서 확인할 수 있게 정리한 것입니다.</p>
    <table><thead><tr><th>월</th><th>주유비</th><th>하이패스</th><th>카드대금 합계</th><th>하나카드</th><th>현대카드</th><th>삼성카드</th></tr></thead><tbody>
      {table_rows}
    </tbody></table>
  </section>
  <section>
    <h2>Caveats And Assumptions</h2>
    <div class="caveat"><p><strong>분류 중복 가능성:</strong> 주유비와 통행료 규칙이 동시에 걸린 행은 {overlaps}건입니다. 내용에 “고속도로”가 들어간 주유소명은 주유비 키워드와 통행료 키워드가 동시에 적용될 수 있습니다.</p></div>
    <ul>
      <li>금액은 원(KRW)이며, 지출/이체의 음수 금액만 비용으로 반영하고 절댓값으로 표시했습니다.</li>
      <li>카드대금은 청구사 납부액 기준입니다. 내용 열의 `하나카드/하나카드결제`, `현대카드`, `삼성카드/삼성카드(주)`를 각각 하나카드, 현대카드, 삼성카드로 매핑했습니다.</li>
      <li>2026-07은 2026-07-02까지의 부분월입니다.</li>
      <li>날짜 파싱 실패 {failed_dates}건, 금액 파싱 실패 {failed_amounts}건, KRW 외 통화 {len(non_krw)}건입니다.</li>
    </ul>
  </section>
  <section>
    <h2>Sources And Reproducibility</h2>
    <p class="source-note">Source Google Sheet: <a href="https://docs.google.com/spreadsheets/d/1Qx9rdFlCteVn3vudJ1aJ0IMH8KpF01YtTksyN4fgkX0/edit">202507-202607 가계부 / 시트1!A:J</a>. Local CSV export: 202507-202607 가계부.CSV.csv. Dashboard app artifact: <a href="https://mcp-server-dataanalyticswidgets-d90d6b74b2c37858.web-sandbox.oaiusercontent.com/?app=skybridge">skybridge dashboard app</a>. Generated at: 2026-07-02T12:00:00+09:00.</p>
    <p class="source-note">주유비 규칙: `타입=지출`, `대분류=자동차`, `내용`에 주유소/에너지/오일뱅크/석유/주유 포함. 통행료 규칙: 하이패스 결제수단 또는 내용에 대교/고속도로/브릿지/브리지/도로 포함. 카드대금 규칙: 내용 열의 하나카드/하나카드결제/현대카드/삼성카드/삼성카드(주) 매핑.</p>
  </section>
</main>
</body>
</html>
"""
    OUT_PATH.write_text(html_text, encoding="utf-8")
    print(f"wrote={OUT_PATH}")
    print(f"rows={len(rows)} months={len(months)} fuel={int(total_fuel)} toll={int(total_toll)} card={int(total_card)} card_rows={counts['card']}")
    print(f"hana={int(sum(item['하나카드'] for item in data))} hyundai={int(sum(item['현대카드'] for item in data))} samsung={int(sum(item['삼성카드'] for item in data))}")


if __name__ == "__main__":
    main()
