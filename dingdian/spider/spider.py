# coding=utf-8
import requests
from lxml import etree
from requests.exceptions import ConnectionError
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
"""
爬虫api：
    搜索结果页：get_index_result(search)
    小说章节页：get_chapter(url)
    章节内容：get_article(url)
"""

class DdSpider(object):

    def __init__(self):
        self.url = "https://www.biqukan.co/modules/article/search.php"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded; charset=GBK"
        }

    def is_curent_url(url):
        # 定义正则表达式
        pattern = r"^https://www\.biqukan\.co/book/\d+/?$"
        return bool(re.match(pattern, url))
    
    def parse_url(self, url):
        try:
            resp = requests.get(url, headers=self.headers)
            if resp.status_code == 200:
                resp.encoding = 'gbk'
                return resp.text
            return None
        except ConnectionError:
            print('Error.')
        return None
    
    def handle_task(self,chapter,url0):
        title = chapter.get('title')
        chapter_url = chapter.get('href')
        content = self.get_article(str(url0) + chapter_url)
        data = {
            'url': str(url0) + chapter_url,
            'chapter': title,
            'content': content
        }
        return data


    def work_url(self, url,url0):
        try:
            resp = requests.get(url, headers=self.headers)
            if resp.status_code == 200:
                resp.encoding = 'gbk'
                html_tree = etree.HTML(resp.text)
                chapters = html_tree.xpath('//dl[@class="panel-body panel-chapterlist"]/dd/a') 
                datas = []
                with ThreadPoolExecutor(max_workers = 32) as inner_executor:
                    future_to_sub_task = [inner_executor.submit(self.handle_task,chapter,url0) for chapter in chapters]
                    for future in future_to_sub_task:
                        data = future.result()  
                        datas.append(data)                    
                return datas
            return None
        except ConnectionError:
            print('Error.')
        return None
    
    def search_keyword(self, keyword,search_type):
        try:
            data = {}
            if search_type == 'author':
                data["searchtype"] = "author"
            else:
                data["searchtype"] = "articlename"
            data["searchkey"] = keyword
            data_encoded = {k: v.encode('gbk') for k, v in data.items()}
            resp = requests.post(self.url, data=data_encoded, headers=self.headers)
            if resp.status_code == 200:
                # 处理一下网站打印出来中文乱码的问题
                resp.encoding = 'gbk'
                return resp.text
            return None
        except ConnectionError:
            print('Error.')
        return None

    # 搜索结果页数据
    def get_index_result(self, search,search_type, page=0):
        resp = self.search_keyword(search,search_type)

        html_tree = etree.HTML(resp)
        keywords = html_tree.xpath('//meta[@name="keywords"]/@content')
        if keywords and "搜索" in keywords[0]: 
            rows = html_tree.xpath("//table[@class='table']//tr[position()>1]")  # 略过第一行标题行
            for row in rows:
                book_type = row.xpath("./td[1]/text()")[0].strip() if row.xpath("./td[1]/text()") else ""
                book_name = row.xpath("./td[2]/a/text()")[0].strip()
                book_url = row.xpath("./td[2]/a/@href")[0]
                latest_chapter = row.xpath("./td[3]/a/text()")[0].strip() if row.xpath("./td[3]/a/text()") else ""
                author = row.xpath("./td[4]/text()")[0].strip()
                update_time = row.xpath("./td[5]/text()")[0].strip()
                book_info = {
                    "book_type": book_type,
                    "book_name": book_name,
                    "book_url": book_url,
                    "latest_chapter": latest_chapter,
                    "author": author,
                    "update_time": update_time
                }
                yield book_info
        else:
            if len(keywords) == 0:
                return 
            book_type = html_tree.xpath('//meta[@property="og:novel:category"]/@content')
            book_name = html_tree.xpath('//meta[@property="og:title"]/@content')
            book_url = html_tree.xpath('//meta[@property="og:novel:read_url"]/@content')
            latest_chapter = html_tree.xpath('//meta[@property="og:novel:latest_chapter_name"]/@content')
            author = html_tree.xpath('//meta[@property="og:novel:author"]/@content')
            update_time = html_tree.xpath('//meta[@property="og:novel:update_time"]/@content')
            book_info = {
                "book_type": book_type[0],
                "book_name": book_name[0],
                "book_url": book_url[0],
                "latest_chapter": latest_chapter[0],
                "author": author[0],
                "update_time": update_time[0]
            }
            yield book_info

    def write_2_file(self,url):
        pass
    # 小说章节页数据
    def get_chapter(self, url):

        resp = self.parse_url(url)
        html_tree = etree.HTML(resp)
        # chapters = html_tree.xpath('//dl[@class="panel-body panel-chapterlist"]/dd/a') 
        # current_page = html_tree.xpath('//select[@class="form-control"]/option[@selected]/text()')
        page_links = html_tree.xpath('//select[@class="form-control"]/option/@value')
        url_main = "https://www.biqukan.co"
        datas = []
        if len(page_links) != 0:
            max_workers = len(page_links)
            if max_workers >= 16:
                max_workers = 16
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(self.work_url, url_main + page_link, url_main + page_links[0]) for page_link in page_links]
                for future in futures:
                    datas += future.result()
        else:
            chapters = html_tree.xpath('//dl[@class="panel-body panel-chapterlist"]/dd/a')
            with ThreadPoolExecutor(max_workers = 32) as inner_executor:
                future_to_sub_task = [inner_executor.submit(self.handle_task,chapter,url) for chapter in chapters]
                datas = [future.result() for future in future_to_sub_task]                    
        return datas
    def parser_biqukan_article(self,novel_content,url):
        resp = self.parse_url(url)
        print(f"{url}")
        if resp == None:
            print(f"{url}")
            return novel_content,None
        html = etree.HTML(resp)
        direct_text = ""
        divs = html.xpath('//div[@class="panel-body" and @id="htmlContent"]')[0]
        for div in divs:
            if div.tag == 'br':
                direct_text += '<br />'
                if div.tail != None:
                    direct_text += div.tail

        next_page_url = html.xpath('//a[@id="linkNext"]/@href')
        next_page_url = next_page_url[0] if next_page_url else None
        main_url = html.xpath('//a[@id="linkIndex"]/@href')[0]
        if next_page_url != None:
            next_page_url = main_url + next_page_url
        return novel_content + direct_text.strip(),next_page_url

    # 章节内容页数据
    def get_article(self, url):
        novel_content = ""
        next_page_url = url

        while next_page_url != None :
            novel_content,next_page_url = self.parser_biqukan_article(novel_content,next_page_url)
            if "_" not in next_page_url:
                break
        return novel_content

# dd = DdSpider()
# # for i in dd.get_index_result('诛仙',page=0):
# #     print(i)
# print(dd.get_article('http://www.23us.cc/html/138/138189/7009918.html'))

