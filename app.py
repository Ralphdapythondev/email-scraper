import streamlit as st
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
import pandas as pd
from io import BytesIO
import time
import random
from urllib.parse import urljoin, urlparse
import json
from datetime import datetime, timedelta
import dns.resolver
import logging
import sqlite3
from tenacity import retry, stop_after_attempt, wait_exponential
import enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress debug logs from asyncio
logging.getLogger('asyncio').setLevel(logging.WARNING)

# Setting page configuration
st.set_page_config(page_title='Enhanced Email Harvester', page_icon='⚒️', layout="wide", initial_sidebar_state="auto")
st.title("⚒️ Enhanced Email Harvester with Proxy Support")

# Proxy sources
PROXY_SOURCES = [
    "https://www.proxy-list.download/api/v1/get?type=https",
    "https://www.proxy-list.download/api/v1/get?type=http",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://www.sslproxies.org/",
    "https://free-proxy-list.net/",
    "https://www.us-proxy.org/",
    "https://free-proxy-list.net/uk-proxy.html",
    "https://www.socks-proxy.net/",
    "https://yakumo.rei.my.id/ALL",
    "https://yakumo.rei.my.id/pALL",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/archive/txt/proxies.txt"
]

class AnonymityLevel(enum.IntEnum):
    TRANSPARENT = 1
    ANONYMOUS = 2
    ELITE = 3

class ProxyScanner:
    def __init__(self):
        self.db_conn = sqlite3.connect('proxy_database.db')
        self.initialize_db()
        self.blacklisted_proxies = set()

    def initialize_db(self):
        with self.db_conn:
            c = self.db_conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS proxies
                        (proxy TEXT PRIMARY KEY, latency REAL, country TEXT, city TEXT,
                        last_checked TIMESTAMP, successful_checks INTEGER, total_checks INTEGER,
                        anonymity_level INTEGER, isp TEXT)''')
            c.execute('CREATE INDEX IF NOT EXISTS idx_country ON proxies(country)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_latency ON proxies(latency)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_anonymity ON proxies(anonymity_level)')
            self.db_conn.execute('PRAGMA synchronous = OFF')

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def fetch_proxies(self) -> set:
        proxies = set()
        async with aiohttp.ClientSession() as session:
            for url in PROXY_SOURCES:
                try:
                    async with session.get(url, timeout=30) as response:
                        if response.status == 200:
                            text = await response.text()
                            proxies.update(text.splitlines())
                            logger.info(f"Fetched {len(text.splitlines())} proxies from {url}")
                        else:
                            logger.warning(f"Failed to fetch proxies from {url} with status code {response.status}")
                except Exception as e:
                    logger.error(f"Error fetching from {url}: {e}")
        return proxies

    async def check_proxy(self, proxy: str) -> dict:
        async with aiohttp.ClientSession() as session:
            try:
                start_time = time.time()
                async with session.get("http://httpbin.org/ip", proxy=f"http://{proxy}", timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        ip = data['origin'].split(',')[0].strip()
                        latency = time.time() - start_time
                        anonymity_level = await self.check_anonymity_level(proxy)
                        logger.info(f"Proxy {proxy} passed with latency {latency:.2f} seconds")
                        return {
                            'proxy': proxy,
                            'latency': latency,
                            'ip': ip,
                            'anonymity_level': anonymity_level
                        }
                    else:
                        logger.warning(f"Proxy {proxy} failed with status code {response.status}")
            except Exception as e:
                logger.debug(f"Proxy {proxy} failed: {e}")
        return None

    async def check_anonymity_level(self, proxy: str) -> AnonymityLevel:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("http://httpbin.org/headers", proxy=f"http://{proxy}", timeout=10) as response:
                    if response.status == 200:
                        headers = await response.json()
                        if 'X-Forwarded-For' not in headers['headers']:
                            return AnonymityLevel.ELITE
                        elif proxy.split(':')[0] not in headers['headers'].get('X-Forwarded-For', ''):
                            return AnonymityLevel.ANONYMOUS
                        else:
                            return AnonymityLevel.TRANSPARENT
            except Exception:
                pass
        return AnonymityLevel.TRANSPARENT

    def update_proxy_database(self, result: dict):
        try:
            with self.db_conn:
                c = self.db_conn.cursor()
                c.execute('''INSERT OR REPLACE INTO proxies
                            (proxy, latency, last_checked, successful_checks, total_checks, anonymity_level)
                            VALUES (?, ?, ?,
                                    COALESCE((SELECT successful_checks FROM proxies WHERE proxy = ?) + 1, 1),
                                    COALESCE((SELECT total_checks FROM proxies WHERE proxy = ?) + 1, 1),
                                    ?)''',
                          (result['proxy'],
                           result['latency'],
                           datetime.now().isoformat(),
                           result['proxy'],
                           result['proxy'],
                           result['anonymity_level'].value))
                logger.info(f"Updated database with proxy: {result['proxy']}")
        except sqlite3.Error as e:
            logger.error(f"An error occurred while updating the database: {e}")
            logger.error(f"Result data: {result}")

    def get_proxies(self, min_anonymity: AnonymityLevel = AnonymityLevel.ANONYMOUS, max_latency: float = 5.0) -> list:
        c = self.db_conn.cursor()
        query = '''SELECT proxy FROM proxies 
                   WHERE anonymity_level >= ? AND latency <= ? AND last_checked >= ?
                   ORDER BY (successful_checks * 1.0 / total_checks) DESC, latency ASC'''
        c.execute(query, (min_anonymity.value, max_latency, (datetime.now() - timedelta(days=1)).isoformat()))
        return [row[0] for row in c.fetchall() if row[0] not in self.blacklisted_proxies]

class EmailHarvester:
    def __init__(self):
        self.proxy_scanner = ProxyScanner()
        self.session = None

    async def initialize(self):
        await self.refresh_proxies()
        self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()

    async def refresh_proxies(self):
        proxies = await self.proxy_scanner.fetch_proxies()
        for proxy in proxies:
            result = await self.proxy_scanner.check_proxy(proxy)
            if result:
                self.proxy_scanner.update_proxy_database(result)

    async def get_random_proxy(self):
        proxies = self.proxy_scanner.get_proxies()
        return random.choice(proxies) if proxies else None

    async def fetch_url_with_proxy(self, url: str, depth: int = 0, max_depth: int = 2) -> list:
        if depth > max_depth:
            return []

        proxy = await self.get_random_proxy()
        if not proxy:
            logger.warning("No valid proxies available.")
            return []

        try:
            async with self.session.get(url, proxy=f"http://{proxy}", timeout=30) as response:
                if response.status == 200:
                    content = await response.text()
                    soup = BeautifulSoup(content, 'html.parser')
                    emails = set(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content))
                    valid_emails = [email for email in emails if await self.is_valid_email(email)]

                    # Recursively crawl links
                    links = soup.find_all('a', href=True)
                    tasks = []
                    for link in links[:5]:  # Limit to 5 links per page to avoid overloading
                        href = link['href']
                        full_url = urljoin(url, href)
                        if urlparse(full_url).netloc == urlparse(url).netloc:
                            tasks.append(self.fetch_url_with_proxy(full_url, depth + 1, max_depth))
                    
                    results = await asyncio.gather(*tasks)
                    for result in results:
                        valid_emails.extend(result)

                    return list(set(valid_emails))
                else:
                    logger.warning(f"Failed to fetch {url} with status code {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            self.proxy_scanner.blacklisted_proxies.add(proxy)
            return []

    async def is_valid_email(self, email: str) -> bool:
        pattern = r'''(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])'''
        if not re.match(pattern, email, re.IGNORECASE):
            return False
        
        domain = email.split('@')[1]
        try:
            await asyncio.get_event_loop().run_in_executor(None, dns.resolver.resolve, domain, 'MX')
            return True
        except:
            return False

    async def harvest_emails(self, urls: list, max_depth: int = 2) -> list:
        all_emails = []
        for url in urls:
            emails = await self.fetch_url_with_proxy(url, max_depth=max_depth)
            all_emails.extend(emails)
        return list(set(all_emails))

async def main():
    harvester = EmailHarvester()
    await harvester.initialize()

    st.write("Enter URLs to scrape emails from (one per line):")
    urls_input = st.text_area("URLs")
    max_depth = st.slider("Max Crawl Depth", 0, 5, 2)

    if st.button("Start Harvesting"):
        urls = [url.strip() for url in urls_input.splitlines() if url.strip()]
        if urls:
            with st.spinner('Harvesting emails...'):
                emails = await harvester.harvest_emails(urls, max_depth)
                if emails:
                    st.write(f"Found {len(emails)} unique emails:")
                    email_df = pd.DataFrame(emails, columns=["Email"])
                    st.write(email_df)

                    # Export options
                    csv = email_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download as CSV",
                        data=csv,
                        file_name="harvested_emails.csv",
                        mime="text/csv"
                    )
                else:
                    st.write("No emails found.")
        else:
            st.write("Please enter at least one URL.")

    await harvester.close()

if __name__ == "__main__":
    asyncio.run(main())
