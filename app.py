import streamlit as st
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import pandas as pd
from urllib.parse import urljoin, urlparse
import dns.resolver
import logging
import sqlite3
from tenacity import retry, stop_after_attempt, wait_exponential
import enum
from datetime import datetime, timedelta
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress debug logs from asyncio
logging.getLogger('asyncio').setLevel(logging.WARNING)

# Setting page configuration
st.set_page_config(page_title='Enhanced Email Harvester', page_icon='⚒️', layout="wide", initial_sidebar_state="auto")
st.title("⚒️ Enhanced Email Harvester with Proxy Support")

# Proxy sources and other constants remain the same...

class AnonymityLevel(enum.IntEnum):
    TRANSPARENT = 1
    ANONYMOUS = 2
    ELITE = 3

class ProxyScanner:
    def __init__(self):
        self.db_conn = sqlite3.connect('proxy_database.db', check_same_thread=False)
        self.initialize_db()
        self.blacklisted_proxies = set()

    # Other methods remain the same...

class EmailHarvester:
    def __init__(self):
        self.proxy_scanner = ProxyScanner()
        self.session = None

    # Other methods remain the same...

    async def harvest_emails(self, urls: list, max_depth: int = 2) -> list:
        all_emails = []
        for url in urls:
            emails = await self.fetch_url_with_proxy(url, max_depth=max_depth)
            all_emails.extend(emails)
        return list(set(all_emails))

@st.cache_resource
def get_harvester():
    return EmailHarvester()

def main():
    harvester = get_harvester()

    st.write("Enter URLs to scrape emails from (one per line):")
    urls_input = st.text_area("URLs")
    max_depth = st.slider("Max Crawl Depth", 0, 5, 2)

    if st.button("Start Harvesting"):
        urls = [url.strip() for url in urls_input.splitlines() if url.strip()]
        if urls:
            with st.spinner('Harvesting emails...'):
                # Use asyncio.run in a separate thread to avoid blocking Streamlit
                async def run_harvest():
                    await harvester.initialize()
                    emails = await harvester.harvest_emails(urls, max_depth)
                    await harvester.close()
                    return emails

                emails = asyncio.run(run_harvest())

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

if __name__ == "__main__":
    main()
