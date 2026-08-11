"""
네이버 랭킹뉴스 텔레그램 봇
- 네이버 '언론사별 랭킹뉴스(많이 본 뉴스)' 페이지를 크롤링
- 중복(유사 제목) 제거 후 상위 10개 선별
- 텔레그램으로 발송

필요 환경변수:
  BOT_TOKEN : 텔레그램 봇 토큰 (@BotFather에서 발급)
  CHAT_ID   : 받을 채팅방 ID
"""

import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

RANKING_URL = "https://news.naver.com/main/ranking/popularDay.naver"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0 Safari/537.36"
}

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

KST = timezone(timedelta(hours=9))


def fetch_ranking_articles():
    """랭킹 페이지에서 (제목, 링크) 목록을 순서대로 수집."""
    res = requests.get(RANKING_URL, headers=HEADERS, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    articles = []
    # 언론사별 랭킹 박스 안의 기사 링크들
    for a in soup.select(".rankingnews_box .list_content a"):
        title = a.get_text(strip=True)
        link = a.get("href", "")
        if title and link.startswith("http"):
            articles.append({"title": title, "link": link})
    return articles


def normalize(title: str) -> set:
    """제목을 단어 집합으로 변환 (유사도 비교용)."""
    words = re.sub(r"[^\w\s]", " ", title).split()
    return {w for w in words if len(w) >= 2}


def is_similar(t1: str, t2: str, threshold: float = 0.5) -> bool:
    """두 제목의 단어 겹침 비율(자카드 유사도)로 같은 사건인지 판단."""
    s1, s2 = normalize(t1), normalize(t2)
    if not s1 or not s2:
        return False
    jaccard = len(s1 & s2) / len(s1 | s2)
    return jaccard >= threshold


def select_top(articles: list, n: int = 10) -> list:
    """앞 순서(=랭킹 상위) 우선으로, 유사 제목을 걸러내며 n개 선별."""
    selected = []
    for art in articles:
        if any(is_similar(art["title"], s["title"]) for s in selected):
            continue
        selected.append(art)
        if len(selected) >= n:
            break
    return selected


def build_message(articles: list) -> str:
    today = datetime.now(KST).strftime("%m월 %d일")
    lines = [f"📰 <b>{today} 아침 랭킹뉴스 TOP {len(articles)}</b>\n"]
    for i, art in enumerate(articles, 1):
        lines.append(f'{i}. <a href="{art["link"]}">{art["title"]}</a>')
    return "\n".join(lines)


def send_telegram(text: str):
    res = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    res.raise_for_status()


def main():
    articles = fetch_ranking_articles()
    if not articles:
        send_telegram("⚠️ 오늘은 랭킹뉴스를 가져오지 못했습니다. (페이지 구조 변경 가능성)")
        return
    top10 = select_top(articles, 10)
    send_telegram(build_message(top10))
    print(f"발송 완료: {len(top10)}건")


if __name__ == "__main__":
    main()
