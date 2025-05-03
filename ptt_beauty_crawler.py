import httpx
from bs4 import BeautifulSoup
import json
import time
import re
import sys
import os
from collections import Counter, defaultdict
from datetime import datetime
import concurrent.futures

class PTTCrawler:
    def __init__(self):
        self.base_url = "https://www.ptt.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.cookies = {"over18": "1"}
        #2024年第一篇文章
        self.first_article_url = "https://www.ptt.cc/bbs/Beauty/M.1704040318.A.E87.html"
        self.image_pattern = re.compile(r'https?://[^\s<>"\']+\.(jpg|jpeg|png|gif)', re.IGNORECASE)
        
    def crawl(self):
        articles = []
        popular_articles = []
        
        client = httpx.Client(headers=self.headers, cookies=self.cookies, timeout=30.0)
        
        # 從2024年第一篇文章開始找他在的頁面，如果找不到就直接從第一頁開始爬
        first_article_page = self._find_page_of_article(client, self.first_article_url)
        if not first_article_page:
            first_article_page = 1
        
    
        current_index = self._get_latest_index(client)
        if current_index is None:
            print("can't find current_index")
            return
        
        print(f"current_index is {current_index}")
        
        # 從current_index爬到2024年第一篇
        page_limit = current_index - first_article_page + 50  # 確保爬到所有2024年文章
        pages_crawled = 0
        reached_2024 = False
        
        if page_limit <= 0:
            page_limit = current_index
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, os.cpu_count() or 1)) as executor:
            while current_index >= first_article_page and pages_crawled < page_limit:
                index_url = f"{self.base_url}/bbs/Beauty/index{current_index}.html"
                print(f"[INFO] 爬取第 {current_index} 頁: {index_url}")
                
                try:
                    res = client.get(index_url)
                    if res.status_code != 200:
                        print(f"[WARN] 頁面 {current_index} 不存在，跳過")
                        current_index -= 1
                        continue
                    
                    soup = BeautifulSoup(res.text, "html.parser")
                    entries = soup.select("div.r-ent")
                    
                    futures = []
                    for entry in entries:
                        title_tag = entry.select_one("div.title a")
                        if not title_tag:
                            continue
                            
                        title = title_tag.text.strip()
                        href = title_tag.get("href")
                        
                        if "[公告]" in title or "Fw:[公告]" in title or not title or not href:
                            continue
                            
                        article_url = self.base_url + href
                        futures.append(executor.submit(self._process_article, client, article_url, title))
                    
                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        if result:
                            article_info, is_popular, is_2024 = result
                            if is_2024:
                                reached_2024 = True
                                articles.append(article_info)
                                if is_popular:
                                    popular_articles.append(article_info)
                    
                    current_index -= 1
                    pages_crawled += 1
                    time.sleep(0.2)
                
                except Exception as e:
                    print(f"error finding {current_index} : {str(e)}")
                    current_index -= 1
                    time.sleep(1) 
            

        with open("articles.jsonl", "w", encoding="utf-8") as f:
            for a in articles:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
        
        with open("popular_articles.jsonl", "w", encoding="utf-8") as f:
            for a in popular_articles:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
        
        print(f"\n爬取共 {len(articles)} 篇2024年文章，其中 {len(popular_articles)} 篇為推爆文章")
    

    def _get_latest_index(self, client):
        url = f"{self.base_url}/bbs/Beauty/index.html"
        try:
            res = client.get(url)
            soup = BeautifulSoup(res.text, "html.parser")
            prev_links = soup.select("div.btn-group-paging a")
            if not prev_links or len(prev_links) < 2:
                return None
                
            href = prev_links[1].get("href", "")
            match = re.search(r"index(\d+)\.html", href)
            if match:
                return int(match.group(1)) + 1
            return None
        except Exception as e:
            return None
    
    def _find_page_of_article(self, client, article_url):
        article_id = article_url.split('/')[-1].split('.html')[0]
        
        try:
            res = client.get(article_url)
            if res.status_code != 200:
                print(f"[WARN] 無法直接訪問文章 {article_url}")
            else:
                # 從頁面中找到該文章所在的index
                soup = BeautifulSoup(res.text, "html.parser")
                link_elements = soup.select("div.btn-group.btn-group-paging a")
                for link in link_elements:
                    href = link.get("href", "")
                    match = re.search(r"index(\d+)\.html", href)
                    if match:
                        page_num = int(match.group(1))
                        return page_num
        except Exception as e:
            print(f"error: {str(e)}")
        

        current_index = self._get_latest_index(client)
        if not current_index:
            return None
     #找不到就全部都找       
        max_pages = 5000
        pages_checked = 0
        
        while current_index > 0 and pages_checked < max_pages:
            index_url = f"{self.base_url}/bbs/Beauty/index{current_index}.html"
            try:
                res = client.get(index_url)
                if res.status_code != 200:
                    current_index -= 1
                    pages_checked += 1
                    continue
                    
                # 檢查這個頁面是否包含目標文章
                if article_id in res.text:
                    return current_index
                
                # 檢查是否已到較早的頁面
                soup = BeautifulSoup(res.text, "html.parser")
                entries = soup.select("div.r-ent a")
                for entry in entries:
                    href = entry.get("href", "")
                    if article_id in href:
                        return current_index
                        
                current_index -= 1
                pages_checked += 1
                if pages_checked % 50 == 0:
                    print(f"已檢查 {pages_checked} 頁")
                time.sleep(0.1)
                
            except Exception as e:
                print(f"檢查頁面 {current_index} 失敗: {str(e)}")
                current_index -= 1
                pages_checked += 1
                time.sleep(0.5)
        
        #找不到就返回 從最早的頁面開始找
        return 1
    
    def _process_article(self, client, article_url, title):
        try:
            res = client.get(article_url)
            if res.status_code != 200:
                return None
                
            soup = BeautifulSoup(res.text, "html.parser")
            
            # 檢查是否為2024年文章
            date_str = ""
            is_2024 = False
            metalines = soup.find_all("div", class_="article-metaline")
            for line in metalines:
                tag = line.find("span", class_="article-meta-tag")
                val = line.find("span", class_="article-meta-value")
                if tag and val and tag.text.strip() == "時間":
                    raw_time = val.text.strip()
                    if "2024" in raw_time:
                        is_2024 = True
                        try:
                            # Mon Jan 1 03:45:18 2024
                            dt = datetime.strptime(raw_time, "%a %b %d %H:%M:%S %Y")
                            date_str = dt.strftime("%m%d")
                        except Exception:

                            month_day = re.search(r"\b([A-Za-z]{3})\s+(\d{1,2})\b", raw_time)
                            if month_day:
                                month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                                             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                                month = month_names.index(month_day.group(1)) + 1
                                day = int(month_day.group(2))
                                date_str = f"{month:02d}{day:02d}"
                    break
            
            if not is_2024 or not date_str:
                return None
                

            is_popular = False
             # 1. 檢查文章標題旁的推文標記是不是"爆"
            push_count_spans = soup.find_all("span", class_="hl push-tag")
            for span in push_count_spans:
                if span and "爆" in span.text:
                    is_popular = True
                    break

             # 2. 計算推文和噓文數量，判斷差值是否達到推爆標準
            if not is_popular:
                push_content = soup.find_all("div", class_="push")
                push_count = 0
                boo_count = 0
                for push in push_content:
                    tag = push.find("span", class_="push-tag")
                    if tag:
                        tag_text = tag.text.strip()
                        if "推" in tag_text:
                            push_count += 1
                        elif "噓" in tag_text:
                            boo_count += 1
                if push_count - boo_count >= 100:
                    is_popular = True

            # 3. 檢查是否有高亮顯示"爆"字的span
            if not is_popular:
                hl_text_spans = soup.find_all("span", class_="hl f1")
                for span in hl_text_spans:
                    if span and "爆" in span.text:
                        is_popular = True
                        break


            # 4. 檢查文章頁面的推噓文標示
            if not is_popular:
                article_meta = soup.find_all("div", class_="article-metaline-right")
                for meta in article_meta:
                    if meta and "爆" in meta.text:
                        is_popular = True
                        break
           

            article_info = {
                "date": date_str,
                "title": title,
                "url": article_url
            }
            

            if is_popular:
                print(f"推爆文章: {title}")
            
            return (article_info, is_popular, is_2024)
            
        except Exception as e:
            return None
    
    def push(self, start_date, end_date):
        if not os.path.exists("articles.jsonl"):
            print("can't find articles.jsonl")
            return
        
        articles = self._load_articles("articles.jsonl")
        
        articles_in_range = [article for article in articles 
                            if self._is_date_in_range(article["date"], start_date, end_date)]
        
        if not articles_in_range:
            print(f"在 {start_date} 至 {end_date} 之間找不到文章")
            return
        

        push_counter = Counter()
        boo_counter = Counter()
        total_push = 0
        total_boo = 0
        
        client = httpx.Client(headers=self.headers, cookies=self.cookies, timeout=30.0)
        
        print(f"正在分析 {len(articles_in_range)} 篇文章的推噓文情況")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, os.cpu_count() or 1)) as executor:
            futures = [executor.submit(self._analyze_pushes, client, article["url"]) for article in articles_in_range]
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    pushes, boos = result
                    for user, count in pushes.items():
                        push_counter[user] += count
                        total_push += count
                    for user, count in boos.items():
                        boo_counter[user] += count
                        total_boo += count
        

        push_top10 = self._get_top_users(push_counter, 10)
        boo_top10 = self._get_top_users(boo_counter, 10)
        
        result = {
            "push": {
                "total": total_push,
                "top10": push_top10
            },
            "boo": {
                "total": total_boo,
                "top10": boo_top10
            }
        }
        

        output_filename = f"push_{start_date}_{end_date}.json"
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"推噓文分析結果存儲至 {output_filename}")
    
    def popular(self, start_date, end_date):
        if not os.path.exists("popular_articles.jsonl"):
            print("can't find popular_articles.jsonl")
            return
        

        popular_articles = self._load_articles("popular_articles.jsonl")
        articles_in_range = [article for article in popular_articles 
                            if self._is_date_in_range(article["date"], start_date, end_date)]
        
        if not articles_in_range:
            print(f"在 {start_date} 至 {end_date} 之間找不到推爆文章")
            return
        
        # 圖片URL
        image_urls = []
        client = httpx.Client(headers=self.headers, cookies=self.cookies, timeout=30.0)
        
        print(f"正在分析 {len(articles_in_range)} 篇推爆文章的圖片")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, os.cpu_count() or 1)) as executor:
            futures = [executor.submit(self._extract_image_urls, client, article["url"]) for article in articles_in_range]
            
            for future in concurrent.futures.as_completed(futures):
                urls = future.result()
                if urls:
                    image_urls.extend(urls)
        
        result = {
            "number_of_popular_articles": len(articles_in_range),
            "image_urls": image_urls
        }
        

        output_filename = f"popular_{start_date}_{end_date}.json"
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"找到 {len(image_urls)} 張圖片存儲至 {output_filename}")
    
    def keyword(self, start_date, end_date, keyword):
        if not os.path.exists("articles.jsonl"):
            print("can't find articles.jsonl")
            return
        
        articles = self._load_articles("articles.jsonl")
        articles_in_range = [article for article in articles 
                            if self._is_date_in_range(article["date"], start_date, end_date)]
        
        if not articles_in_range:
            print(f"在 {start_date} 至 {end_date} 之間找不到文章")
            return
        
        image_urls = []
        client = httpx.Client(headers=self.headers, cookies=self.cookies, timeout=30.0)
        
        print(f"正在搜尋 {len(articles_in_range)} 篇文章中包含關鍵字 '{keyword}' 的內容")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, os.cpu_count() or 1)) as executor:
            futures = [executor.submit(self._find_keyword_and_images, client, article["url"], keyword) 
                      for article in articles_in_range]
            
            for future in concurrent.futures.as_completed(futures):
                urls = future.result()
                if urls:
                    image_urls.extend(urls)
        

        result = {
            "image_urls": image_urls
        }
        
        output_filename = f"keyword_{start_date}_{end_date}_{keyword}.json"
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"找到 {len(image_urls)} 張圖片存儲至 {output_filename}")
    
    def _analyze_pushes(self, client, article_url):
        try:
            res = client.get(article_url)
            if res.status_code != 200:
                return None
                
            soup = BeautifulSoup(res.text, "html.parser")
            push_content = soup.find_all("div", class_="push")
            
            push_users = defaultdict(int)
            boo_users = defaultdict(int)
            
            for push in push_content:
                push_tag = push.find("span", class_="push-tag")
                push_userid = push.find("span", class_="push-userid")
                
                if not push_tag or not push_userid:
                    continue
                    
                tag = push_tag.text.strip()
                userid = push_userid.text.strip()
                
                if "推" in tag:
                    push_users[userid] += 1
                elif "噓" in tag:
                    boo_users[userid] += 1
            
            return (push_users, boo_users)
            
        except Exception as e:
            print(f"分析推文失敗 {article_url}: {str(e)}")
            return None
    
    def _extract_image_urls(self, client, article_url):
        try:
            res = client.get(article_url)
            if res.status_code != 200:
                return []
                
            return self.image_pattern.findall(res.text)
            
        except Exception as e:
            print(f"提取圖片失敗 {article_url}: {str(e)}")
            return []
    
    def _find_keyword_and_images(self, client, article_url, keyword):
        try:
            res = client.get(article_url)
            if res.status_code != 200:
                return []
                
            soup = BeautifulSoup(res.text, "html.parser")
            
            main_content = soup.find("div", id="main-content")
            if not main_content:
                return []
                
            # 檢查是否有發信站標記
            info_station = soup.find("span", class_="f2", string=lambda s: "※ 發信站" in s if s else False)
            if not info_station:
                return []
                
            # 取得作者到發信站之間的文字內容
            content_text = ""
            for element in main_content.contents:
                # 跳過推文部分
                if element.name == "div" and "push" in element.get("class", []):
                    continue
                    
                if isinstance(element, str):
                    content_text += element
                elif element.name != "div" or ("article-metaline" not in element.get("class", [])):
                    content_text += element.get_text()
                    
            # 截止到發信站
            if "※ 發信站" in content_text:
                content_text = content_text.split("※ 發信站")[0]
                
            # 檢查內文是否包含關鍵字
            if keyword not in content_text:
                return []
                
            return self.image_pattern.findall(res.text)
            
        except Exception as e:
            print(f"關鍵字搜尋失敗 {article_url}: {str(e)}")
            return []
    
    def _load_articles(self, filename):
        articles = []
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    articles.append(json.loads(line.strip()))
        return articles
    
    def _is_date_in_range(self, date, start_date, end_date):
        try:
            # MMDD
            month = int(date[:2])
            day = int(date[2:])
            
            start_month = int(start_date[:2])
            start_day = int(start_date[2:])
            
            end_month = int(end_date[:2])
            end_day = int(end_date[2:])
            
            if month < start_month or (month == start_month and day < start_day):
                return False
            if month > end_month or (month == end_month and day > end_day):
                return False
            return True
        except Exception:
            return False
    
    def _get_top_users(self, counter, n):
        sorted_users = sorted(counter.items(), key=lambda x: (-x[1], x[0]), reverse=True)
        top_users = sorted_users[:n]

        return [{"user_id": user, "count": count} for user, count in top_users]

def main():
    if len(sys.argv) < 2:
        print("use command like crawl, push, popular, keyword")
        return
    
    command = sys.argv[1].lower()
    crawler = PTTCrawler()
    
    if command == "crawl":
        crawler.crawl()
    elif command == "push":
        if len(sys.argv) != 4:
            print("use: python {student_id}.py push {start_date} {end_date}")
            return
        crawler.push(sys.argv[2], sys.argv[3])
    elif command == "popular":
        if len(sys.argv) != 4:
            print("use: python {student_id}.py popular {start_date} {end_date}")
            return
        crawler.popular(sys.argv[2], sys.argv[3])
    elif command == "keyword":
        if len(sys.argv) != 5:
            print("use: python {student_id}.py keyword {start_date} {end_date} {keyword}")
            return
        crawler.keyword(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(f"未知命令: {command}")

if __name__ == "__main__":
    main()

