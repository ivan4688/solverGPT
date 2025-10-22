#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import time
import re
import os
import sys
from urllib.parse import urlparse
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import functools

# Внимание: требует aiohttp, трafilatura, readability, bs4
import aiohttp
import trafilatura
from readability import Document
from bs4 import BeautifulSoup

# === конфиг ===
api_key = "ff196c6c9c36d7ba9b7514db91daa82faf30bc30"

SERPER_SEARCH_URL = "https://google.serper.dev/search"
DEFAULT_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36")

# Производительность / тайминги
REQUEST_TIMEOUT = 3        # сокращённый таймаут
RETRY_COUNT = 0            # убрать дополнительные ретраи (ускорение)
MIN_TEXT_LEN = 500
MAX_CONNECTIONS = 20       # максимальное одновременно открытых соединений aiohttp
THREADPOOL_WORKERS = 6     # воркеры для блокирующих парсеров
DEFAULT_MAX_LINKS = 10

# Предкомпилированные регэкспы для скорости
_URL_FINDER_RE = re.compile(r'(https?://[^\s\]\)\'"]+)')
_CLEAN_LINE_BAD_RE = re.compile(r'[{}|<>\]\[@#$%^&*\+=\\\/]{3,}')
_COPYRIGHT_RE = re.compile(r'^(©|Copyright|Все права|Политика|Terms|Privacy)', re.IGNORECASE)
_LETTER_RE = re.compile(r'[а-яА-Яa-zA-Z]')

# domains to skip early
BAD_DOMAINS = {'youtube.com', 'youtu.be', 'reddit.com', 'twitter.com',
               'instagram.com', 'facebook.com', 'tiktok.com'}


# ------------------------
# Асинхронный сетевой слой (aiohttp)
# ------------------------

async def serper_search_async(session, query, api_key, gl="ru", hl="ru", tbs="qdr:y"):
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
        "User-Agent": DEFAULT_USER_AGENT
    }
    payload = {"q": query, "gl": gl, "hl": hl, "tbs": tbs}
    try:
        async with session.post(SERPER_SEARCH_URL, json=payload, headers=headers, timeout=REQUEST_TIMEOUT) as r:
            r.raise_for_status()
            return await r.json()
    except Exception:
        return {}

def collect_urls_from_json(obj):
    found = []
    if isinstance(obj, dict):
        for v in obj.values():
            found.extend(collect_urls_from_json(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_urls_from_json(item))
    elif isinstance(obj, str):
        s = obj.strip()
        if s.startswith("http://") or s.startswith("https://"):
            found.append(s)

    seen, out = set(), []
    for u in found:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def extract_urls_from_log_text(log_text):
    urls = _URL_FINDER_RE.findall(log_text or "")
    cleaned = [u.rstrip('.,;)]\'"') for u in urls]
    seen, out = set(), []
    for u in cleaned:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

# ------------------------
# Быстрое извлечение HTML (async)
# ------------------------

async def fetch_html_async(session, url, timeout=REQUEST_TIMEOUT):
    try:
        async with session.get(url, timeout=timeout) as resp:
            if resp.status == 200:
                text = await resp.text(errors='ignore')
                return text, resp.status, None
            else:
                return None, resp.status, f"HTTP {resp.status}"
    except Exception as e:
        return None, None, str(e)


# ------------------------
# Тяжёлые блокирующие операции выполняем в threadpool
# ------------------------

def _extract_text_blocking(html, url=None):
    # оригинальная логика, но в блокирующем режиме
    if url:
        domain = urlparse(url).netloc.lower()
        for bad in BAD_DOMAINS:
            if bad in domain:
                return None

    text = None
    try:
        txt = trafilatura.extract(html, url=url, include_comments=False,
                                  include_tables=False, no_fallback=False)
        if txt and len(txt.strip()) >= MIN_TEXT_LEN:
            return txt.strip()
    except Exception:
        pass

    try:
        doc = Document(html)
        summary_html = doc.summary()
        soup = BeautifulSoup(summary_html, "html.parser")
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
            element.decompose()
        text = soup.get_text(separator='\n').strip()
        if text and len(text) >= MIN_TEXT_LEN:
            return text
    except Exception:
        pass

    try:
        soup = BeautifulSoup(html, 'html.parser')
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'meta', 'link']):
            element.decompose()

        selectors = [
            'article', 'main', '[role="main"]', '.content', '.main-content',
            '.post-content', '.entry-content', '.article-content', '.story-content'
        ]

        for selector in selectors:
            for element in soup.select(selector):
                text_candidate = element.get_text('\n', strip=True)
                if len(text_candidate) >= MIN_TEXT_LEN:
                    return text_candidate

        body = soup.find('body')
        if body:
            text_candidate = body.get_text('\n', strip=True)
            lines = [line for line in text_candidate.split('\n')
                     if len(line.strip()) > 30 and
                     not re.search(r'[{}|<>\]\[@#$%^&*\+=\\\/]', line)]
            text = '\n'.join(lines)
    except Exception:
        pass

    return text if text and len(text) >= MIN_TEXT_LEN else None

def clean_text_improved_sync(text):
    if not text:
        return text
    lines = text.split('\n')
    out = []
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        if _CLEAN_LINE_BAD_RE.search(line):
            continue
        if _COPYRIGHT_RE.match(line):
            continue
        out.append(line)
    text = '\n'.join(out)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def is_good_quality_text_sync(text, min_paragraphs=2, min_avg_length=50):
    if not text:
        return False
    paragraphs = [p for p in text.split('\n\n') if p.strip()]
    if len(paragraphs) < min_paragraphs:
        return False
    avg_length = sum(len(p) for p in paragraphs) / len(paragraphs)
    if avg_length < min_avg_length:
        return False
    letter_ratio = len(_LETTER_RE.findall(text)) / max(1, len(text))
    if letter_ratio < 0.3:
        return False
    return True

# ------------------------
# Обработка одного URL (async + парсинг в threadpool)
# ------------------------

async def process_single_url_async(url, session, executor):
    html, status, err = await fetch_html_async(session, url)
    if err or not html:
        return {"url": url, "text": None, "error": err, "length": 0, "quality": 0}

    loop = asyncio.get_running_loop()
    # heavy extraction executed in threadpool
    text = await loop.run_in_executor(executor, functools.partial(_extract_text_blocking, html, url))
    if text:
        # очистка и проверка качества в pool (незначительно дешевле, но оставляем в executor для safety)
        text = await loop.run_in_executor(executor, clean_text_improved_sync, text)
        quality_score = 1 if await loop.run_in_executor(executor, is_good_quality_text_sync, text) else 0
        return {"url": url, "text": text, "error": None, "length": len(text), "quality": quality_score}
    else:
        return {"url": url, "text": None, "error": "No text extracted", "length": 0, "quality": 0}

# ------------------------
# Параллельная обработка списка URL (async)
# ------------------------

async def process_urls_parallel_async(urls, max_concurrency=10):
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    conn = aiohttp.TCPConnector(limit=MAX_CONNECTIONS, ttl_dns_cache=300)
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    results = []
    executor = ThreadPoolExecutor(max_workers=THREADPOOL_WORKERS)
    sem = asyncio.Semaphore(max_concurrency)

    async with aiohttp.ClientSession(connector=conn, timeout=timeout, headers=headers) as session:
        tasks = []
        for url in urls:
            # простой ленивый семафор, чтобы не создавать слишком много тасков одновременно
            async def _wrap(u):
                async with sem:
                    return await process_single_url_async(u, session, executor)
            tasks.append(asyncio.create_task(_wrap(url)))

        for task in asyncio.as_completed(tasks):
            try:
                res = await task
                results.append(res)
            except Exception as e:
                results.append({"url": "unknown", "text": None, "error": str(e), "length": 0, "quality": 0})

    executor.shutdown(wait=False)
    return results

# ------------------------
# Основная функция (синхронный API)
# ------------------------

def run_extraction(query=None, log_file=None, max_links=10,
                   threads=6, min_length=MIN_TEXT_LEN, only_good_quality=False):
    """
    Основной интерфейс для вызова из других скриптов.
    Возвращает dict с результатами.
    """
    if not query and not log_file:
        raise ValueError("Нужно указать query или log_file")

    urls = []
    if query:
        if not api_key:
            raise ValueError("При использовании query требуется api_key")
        # используем aiohttp синхронно через asyncio.run
        async def _get_urls():
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            conn = aiohttp.TCPConnector(limit=MAX_CONNECTIONS, ttl_dns_cache=300)
            headers = {"User-Agent": DEFAULT_USER_AGENT}
            async with aiohttp.ClientSession(connector=conn, timeout=timeout, headers=headers) as session:
                js = await serper_search_async(session, query, api_key)
                return collect_urls_from_json(js)
        urls = asyncio.run(_get_urls())
    else:
        if not os.path.isfile(log_file):
            raise FileNotFoundError(f"Файл не найден: {log_file}")
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        urls = extract_urls_from_log_text(txt)

    if max_links > 0:
        urls = urls[:max_links]

    start_time = time.time()
    # запустить асинхронную обработку URLов
    results = asyncio.run(process_urls_parallel_async(urls, max_concurrency=threads))
    processing_time = time.time() - start_time

    valid_texts = []
    for res in results:
        if res["text"] and res["length"] >= min_length:
            if not only_good_quality or res["quality"]:
                valid_texts.append((res["text"], res["length"], res["url"]))

    if not valid_texts:
        fallback_texts = [(res["text"], res["length"], res["url"]) for res in results
                          if res["text"] and res["length"] >= min_length]
        if fallback_texts:
            valid_texts = fallback_texts

    valid_texts.sort(key=lambda x: x[1])
    shortest_text = valid_texts[0] if valid_texts else (None, 0, None)

    return {
        "urls": urls,
        "results": results,
        "valid_texts": valid_texts,
        "shortest_text": shortest_text[0],
        "shortest_length": shortest_text[1],
        "shortest_url": shortest_text[2],
        "processing_time": processing_time,
        "success_count": len(valid_texts)
    }

