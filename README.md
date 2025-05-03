# PTT Beauty 2024 Crawler

This is a Python crawler and analyzer designed for the PTT Beauty board, focusing on posts from the year 2024. It supports large-scale data crawling, push/boo comment analysis, image extraction from popular posts, and keyword-based filtering.

## Features

- Crawl all posts starting from the first 2024 article.
- Save full article list and extract popular ones (based on push count or "爆" marker).
- Analyze top pushers and boo-ers within a date range.
- Extract images from popular articles or posts matching specific keywords.
- Multi-threaded for fast execution.

## Requirements

- Python 3.7+
- httpx
- beautifulsoup4

Install dependencies with:

bash
pip install httpx beautifulsoup4

## Usage
1. Crawl all 2024 posts:
bash
python ptt_beauty_crawler.py crawl

3. Analyze push/boo statistics in a date range (MMDD format):
bash
python ptt_beauty_crawler.py push 0101 0331
4. Extract images from popular articles in a date range:
bash
python 313515035.py popular 0101 0331

6. Search for a keyword and extract matching image URLs:
bash
python ptt_beauty_crawler.py keyword 0101 0331 女神

## Output Files
- articles.jsonl: All 2024 articles.
- popular_articles.jsonl: Filtered list of popular articles.
- push_XXXX_YYYY.json: Push/boo statistics.
- popular_XXXX_YYYY.json: Image URLs from popular posts.
- keyword_XXXX_YYYY_keyword.json: Image URLs for keyword-matched posts.

