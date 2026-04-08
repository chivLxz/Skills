#!/usr/bin/env python3
"""
国内AI新闻抓取脚本
从国内科技媒体RSS抓取AI新闻并输出为JSON格式
"""

import argparse
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
import ssl
import re
import html

# 创建忽略SSL验证的上下文
SSL_CONTEXT = ssl._create_unverified_context()

# RSS feeds 配置
RSS_FEEDS = {
    "量子位": "https://www.qbitai.com/feed",
    "36氪": "https://36kr.com/feed",
    "机器之心": "https://www.jiqizhixin.com/rss",
    "InfoQ": "https://www.infoq.cn/feed",
    "爱范儿": "https://www.ifanr.com/feed",
    "钛媒体": "https://www.tmtpost.com/rss",
    "雷锋网": "https://www.leiphone.com/feed"
}

# 宽松AI关键词匹配
AI_KEYWORDS = [
    "ai", "人工智能", "大模型", "gpt", "claude", "llm", "深度学习",
    "机器学习", "神经网络", "自然语言处理", "nlp", "计算机视觉",
    "生成式", "transformer", "bert", "diffusion", "stable diffusion",
    "midjourney", "chatgpt", "智能", "算法", "算力", "芯片", "gpu",
    "芯片ai", "ai芯片", "自动驾驶", "机器人", "语音识别", "图像识别",
    "推荐算法", "强化学习", "aigc", "agi", "多模态", "prompt", "提示词",
    "llama", "mistral", "cohere", "anthropic", "openai", "智谱", "通义千问",
    "文心", "混元", "星火", "月之暗面", "minimax", "阶跃", "deepseek",
    "kimi", "百川", "零一万物", "面壁", "出门问问", "商汤", "旷视", "云",
    "阿里云", "腾讯云", "百度智能云", "华为云", "字节", "ai模型", "模型"
]


def fetch_rss(url: str, timeout: int = 10) -> Optional[str]:
    """获取RSS feed内容"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; AI-News-Digest/1.1)"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as response:
            return response.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"获取RSS失败 {url}: {e}", file=sys.stderr)
        return None


def parse_rss(xml_content: str, source: str) -> List[Dict]:
    """解析RSS XML内容"""
    articles = []

    # 方法1: 尝试标准XML解析
    try:
        root = ET.fromstring(xml_content)
        # 处理RSS和Atom格式
        items = root.findall(".//item") or root.findall(".//{*}item")

        for item in items:
            try:
                # 获取标题
                title = ""
                title_elem = item.find("title")
                if title_elem is None:
                    title_elem = item.find(".//{*}title")
                if title_elem is not None and title_elem.text:
                    title = title_elem.text

                # 获取链接
                link = ""
                link_elem = item.find("link")
                if link_elem is None:
                    link_elem = item.find(".//{*}link")
                if link_elem is not None:
                    if link_elem.text:
                        link = link_elem.text.strip()
                    elif link_elem.get("href"):
                        link = link_elem.get("href")

                # 获取发布时间
                pub_date = ""
                date_elem = item.find("pubDate")
                if date_elem is None:
                    date_elem = item.find("published")
                if date_elem is None:
                    date_elem = item.find(".//{*}pubDate")
                if date_elem is None:
                    date_elem = item.find(".//{*}published")
                if date_elem is not None and date_elem.text:
                    pub_date = date_elem.text.strip()

                # 获取描述
                description = ""
                desc_elem = item.find("description")
                if desc_elem is None:
                    desc_elem = item.find("summary")
                if desc_elem is None:
                    desc_elem = item.find(".//{*}description")
                if desc_elem is None:
                    desc_elem = item.find(".//{*}summary")
                if desc_elem is not None and desc_elem.text:
                    description = desc_elem.text.strip()

                if title:
                    articles.append({
                        "title": title,
                        "link": link,
                        "source": source,
                        "pub_date": pub_date,
                        "description": description
                    })
            except Exception:
                continue

        if articles:
            return articles
    except Exception as e:
        print(f"XML解析失败 {source}: {e}, 尝试HTML解析", file=sys.stderr)

    # 方法2: 尝试使用html.parser (机器之心等可能需要)
    try:
        from html.parser import HTMLParser
        class RSSParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.items = []
                self.current_item = None
                self.current_tag = None
                self.current_data = ""
                self.in_item = False
                self.in_cdata = False

            def handle_starttag(self, tag, attrs):
                tag_lower = tag.lower()
                if tag_lower == "item":
                    self.in_item = True
                    self.current_item = {}
                elif self.in_item and tag_lower in ["title", "link", "pubdate", "published", "description", "summary"]:
                    self.current_tag = tag_lower
                    self.current_data = ""
                    # 检查是否有href属性（用于link标签）
                    if tag_lower == "link":
                        for attr_name, attr_value in attrs:
                            if attr_name.lower() == "href":
                                self.current_item["link"] = attr_value

            def handle_endtag(self, tag):
                tag_lower = tag.lower()
                if tag_lower == "item":
                    if self.current_item and "title" in self.current_item:
                        self.items.append({
                            "title": self.current_item.get("title", ""),
                            "link": self.current_item.get("link", ""),
                            "pub_date": self.current_item.get("pub_date", ""),
                            "description": self.current_item.get("description", "")
                        })
                    self.current_item = None
                    self.in_item = False
                elif self.in_item and tag_lower == self.current_tag:
                    if self.current_tag and self.current_data:
                        self.current_item[self.current_tag] = self.current_data.strip()
                    self.current_tag = None
                    self.current_data = ""

            def handle_data(self, data):
                if self.in_item and self.current_tag:
                    self.current_data += data

            def handle_entityref(self, name):
                # 处理HTML实体
                entities = {"lt": "<", "gt": ">", "amp": "&", "quot": '"', "apos": "'"}
                if name in entities:
                    if self.in_item and self.current_tag:
                        self.current_data += entities[name]

        parser = RSSParser()
        parser.feed(xml_content)

        for item in parser.items:
            if item["title"]:
                articles.append({
                    "title": item["title"],
                    "link": item["link"],
                    "source": source,
                    "pub_date": item["pub_date"],
                    "description": item["description"]
                })

        if articles:
            return articles
    except Exception as e:
        print(f"HTML解析失败 {source}: {e}, 尝试正则提取", file=sys.stderr)

    # 方法3: 正则提取
    try:
        articles = extract_items_by_regex(xml_content, source)
    except Exception as regex_e:
        print(f"正则提取也失败 {source}: {regex_e}", file=sys.stderr)

    return articles


def extract_items_by_regex(content: str, source: str) -> List[Dict]:
    """使用正则表达式从破损的XML中提取item"""
    articles = []
    # 匹配 <item>...</item> 块
    item_pattern = r'<item[^>]*>.*?</item>'
    items = re.findall(item_pattern, content, re.DOTALL | re.IGNORECASE)

    for item in items:
        try:
            # 提取标题
            title_match = re.search(r'<title[^>]*>(.*?)</title>', item, re.DOTALL | re.IGNORECASE)
            title = ""
            if title_match:
                title = html.unescape(re.sub(r'<[^>]+>', '', title_match.group(1))).strip()
                # CDATA处理
                if '<![CDATA[' in title:
                    title = re.search(r'<!\[CDATA\[(.*?)\]\]>', title, re.DOTALL)
                    if title:
                        title = title.group(1).strip()

            # 提取链接
            link = ""
            link_match = re.search(r'<link[^>]*>(.*?)</link>', item, re.DOTALL | re.IGNORECASE)
            if not link_match:
                link_match = re.search(r'<link[^>]+href=["\']([^"\']+)["\']', item, re.IGNORECASE)
            if link_match:
                link = html.unescape(link_match.group(1).strip())

            # 提取发布时间
            pub_date = ""
            date_match = re.search(r'<pubDate[^>]*>(.*?)</pubDate>', item, re.DOTALL | re.IGNORECASE)
            if not date_match:
                date_match = re.search(r'<published[^>]*>(.*?)</published>', item, re.DOTALL | re.IGNORECASE)
            if date_match:
                pub_date = html.unescape(date_match.group(1).strip())

            # 提取描述
            description = ""
            desc_match = re.search(r'<description[^>]*>(.*?)</description>', item, re.DOTALL | re.IGNORECASE)
            if desc_match:
                description = html.unescape(desc_match.group(1).strip())

            if title:
                articles.append({
                    "title": title,
                    "link": link,
                    "source": source,
                    "pub_date": pub_date,
                    "description": description
                })
        except Exception:
            continue

    return articles


def is_ai_related(text: str) -> bool:
    """检查文本是否包含AI相关关键词（宽松匹配）"""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in AI_KEYWORDS)


def parse_date(date_str: str) -> Optional[datetime]:
    """解析多种日期格式"""
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def filter_by_date(articles: List[Dict], target_date: datetime) -> List[Dict]:
    """按日期过滤文章，如果当天文章不足20篇则逐步放宽到最近3天"""
    target_date_str = target_date.strftime("%Y-%m-%d")
    target_date_obj = target_date.date()

    # 尝试当天
    filtered = []
    for article in articles:
        pub_date = article.get("pub_date", "")
        parsed = parse_date(pub_date) if pub_date else None

        if parsed and parsed.date() == target_date_obj:
            filtered.append(article)
        elif not parsed and target_date_str in pub_date:
            filtered.append(article)

    # 如果当天文章不足20篇，逐步放宽
    if len(filtered) < 20:
        print(f"当天文章仅{len(filtered)}篇，尝试包含前一天", file=sys.stderr)
        yesterday = target_date_obj - timedelta(days=1)

        # 尝试前一天
        extended = filtered.copy()
        for article in articles:
            if article in filtered:
                continue
            pub_date = article.get("pub_date", "")
            parsed = parse_date(pub_date) if pub_date else None

            if parsed and parsed.date() == yesterday:
                extended.append(article)
            elif not parsed and yesterday.strftime("%Y-%m-%d") in pub_date:
                extended.append(article)

        if len(extended) >= 20:
            filtered = extended
        else:
            print(f"加前一天共{len(extended)}篇，尝试包含前天", file=sys.stderr)
            day_before = target_date_obj - timedelta(days=2)

            # 尝试前天
            extended_all = extended.copy()
            for article in articles:
                if article in extended:
                    continue
                pub_date = article.get("pub_date", "")
                parsed = parse_date(pub_date) if pub_date else None

                if parsed and parsed.date() == day_before:
                    extended_all.append(article)
                elif not parsed and day_before.strftime("%Y-%m-%d") in pub_date:
                    extended_all.append(article)

            filtered = extended_all

    return filtered


def deduplicate(articles: List[Dict]) -> List[Dict]:
    """按标题前25字符去重"""
    seen = set()
    result = []
    for article in articles:
        key = article["title"][:25].strip().lower()
        if key not in seen:
            seen.add(key)
            result.append(article)
    return result


def normalize_for_json(article: Dict) -> Dict:
    """将文章数据转换为JSON输出格式"""
    # 清理描述（去除HTML标签）
    description = article.get("description", "")
    if description:
        description = re.sub(r'<[^>]+>', '', description).strip()
        description = html.unescape(description)

    return {
        "title": article.get("title", ""),
        "link": article.get("link", ""),
        "description": description,
        "source": article.get("source", ""),
        "pub_date": article.get("pub_date", "")
    }


def main():
    parser = argparse.ArgumentParser(description="国内AI新闻抓取")
    parser.add_argument("--date", default="today", help="目标日期 (today, yesterday, 或 YYYY-MM-DD)")
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument("--max-articles", type=int, default=100, help="最大文章数")
    args = parser.parse_args()

    # 解析日期
    if args.date == "today":
        target_date = datetime.now()
    elif args.date == "yesterday":
        target_date = datetime.now() - timedelta(days=1)
    else:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(f"无效日期格式: {args.date}", file=sys.stderr)
            sys.exit(1)

    # 抓取RSS feeds
    all_articles = []

    for source, url in RSS_FEEDS.items():
        print(f"抓取 {source}...", file=sys.stderr)
        content = fetch_rss(url)
        if content:
            articles = parse_rss(content, source)
            all_articles.extend(articles)

    # AI关键词预过滤
    ai_articles = [a for a in all_articles if is_ai_related(a["title"])]
    print(f"AI相关文章: {len(ai_articles)}/{len(all_articles)}", file=sys.stderr)

    # 按日期过滤
    date_filtered = filter_by_date(ai_articles, target_date)
    print(f"目标日期文章: {len(date_filtered)}", file=sys.stderr)

    # 去重
    unique_articles = deduplicate(date_filtered)
    print(f"去重后: {len(unique_articles)}", file=sys.stderr)

    # 限制数量
    limited_articles = unique_articles[:args.max_articles]

    # 转换为JSON格式
    json_articles = [normalize_for_json(article) for article in limited_articles]
    output_json = json.dumps(json_articles, ensure_ascii=False, indent=2)

    # 输出
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"已写入: {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
