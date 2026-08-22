import os
import re
import json
import argparse
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://api.biorxiv.org/details/biorxiv"


def get_json(url):
    req = Request(
        url,
        headers={
            "User-Agent": "daily-arxiv-ai-enhanced-biorxiv/1.0"
        }
    )
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_authors(authors):
    if not authors:
        return []
    return [x.strip() for x in re.split(r";|\|", authors) if x.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    category = os.environ.get("BIORXIV_CATEGORY", "neuroscience").strip()
    days = int(os.environ.get("BIORXIV_DAYS", "2"))

    keywords_raw = os.environ.get("BIORXIV_KEYWORDS", "").strip()
    keywords = [
        k.strip().lower()
        for k in keywords_raw.split(",")
        if k.strip()
    ]

    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=max(days - 1, 0))

    start = start_date.strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    cursor = 0
    fetched = 0
    kept = 0
    papers = []

    while True:
        query = urlencode({"category": category})
        url = f"{API_BASE}/{start}/{end}/{cursor}?{query}"

        print(f"Fetching bioRxiv: {url}")

        data = get_json(url)
        collection = data.get("collection", [])

        if not collection:
            break

        fetched += len(collection)

        for p in collection:
            title = (p.get("title") or "").strip()
            abstract = (p.get("abstract") or "").strip()

            text = f"{title}\n{abstract}".lower()

            # 如果设置了关键词，只保留标题/摘要中至少命中一个关键词的论文
            if keywords and not any(k in text for k in keywords):
                continue

            doi = (p.get("doi") or "").strip()
            if not doi:
                continue

            version = str(p.get("version") or "1")
            authors = parse_authors(p.get("authors", ""))

            abs_url = f"https://www.biorxiv.org/content/{doi}v{version}"
            pdf_url = f"{abs_url}.full.pdf"

            paper = {
                "id": doi,
                "source": "bioRxiv",
                "pdf": pdf_url,
                "abs": abs_url,
                "authors": authors,
                "title": title,
                "categories": ["bioRxiv.Neuroscience"],
                "comment": "bioRxiv preprint",
                "summary": abstract,
                "date": p.get("date", ""),
                "version": version,
                "doi": doi
            }

            papers.append(paper)
            kept += 1

        messages = data.get("messages", [])
        total = 0

        if messages:
            msg = messages[0]
            try:
                total = int(msg.get("total", 0) or 0)
            except Exception:
                total = 0

        cursor += len(collection)

        if len(collection) < 30:
            break

        if total and cursor >= total:
            break

    with open(args.output, "a", encoding="utf-8") as f:
        for paper in papers:
            f.write(json.dumps(paper, ensure_ascii=False) + "\n")

    print(f"bioRxiv fetched: {fetched}")
    print(f"bioRxiv kept: {kept}")
    print(f"Appended to: {args.output}")


if __name__ == "__main__":
    main()
