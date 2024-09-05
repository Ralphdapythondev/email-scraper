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
from apscheduler.schedulers.background import BackgroundScheduler
from io import BytesIO
from datetime import datetime
import random

# Configure logging
logging.basicConfig(filename='scraper.log', level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Streamlit page configuration
st.set_page_config(page_title='Enhanced Email Harvester', page_icon='⚒️', layout="wide")
st.title("⚒️ Enhanced Email Harvester with Proxy and Scheduling Support")

# Initialize scheduler
scheduler = BackgroundScheduler()

# Proxy Anonymity Level Enum
class AnonymityLevel(enum.IntEnum):
    TRANSPARENT = 1
    ANONYMOUS = 2
    ELITE = 3

# Proxy Scanner Class
class ProxyScanner:
    def __init__(self):
        self.db_conn = sqlite3.connect('proxy_database.db', check_same_thread=False)
        self.initialize_db()
        self.blacklisted_proxies = set()

    def initialize_db(self):
        cursor = self.db_conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS proxies (
                          id INTEGER PRIMARY KEY,
                          ip TEXT,
                          port INTEGER,
                          anonymity_level INTEGER,
                          last_checked TIMESTAMP
                          )''')
        self.db_conn.commit()

    # Method to fetch proxies, validate them, and remove bad proxies...

# Email Harvester Class
class EmailHarvester:
    def __init__(self, use_proxies):
        self.proxy_scanner = ProxyScanner() if use_proxies else None
        self.session = None
        self.use_proxies = use_proxies

    async def initialize(self):
        self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def fetch_url_with_proxy(self, url, max_depth):
        # If proxy usage is enabled, use proxy rotation, otherwise make a regular request
        if self.use_proxies:
            # Get proxy from proxy scanner, make async request, and handle retries...
            pass
        else:
            async with self.session.get(url) as response:
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', str(soup))
                return list(set(emails))

    async def harvest_emails(self, urls: list, max_depth: int = 2) -> list:
        all_emails = []
        for url in urls:
            emails = await self.fetch_url_with_proxy(url, max_depth=max_depth)
            all_emails.extend(emails)
        return list(set(all_emails))

@st.cache_resource
def get_harvester(use_proxies):
    return EmailHarvester(use_proxies)

# Scheduled scraping task
def scheduled_scraping():
    harvester = get_harvester(st.session_state.use_proxies)
    asyncio.run(run_scheduled_harvest(harvester))

async def run_scheduled_harvest(harvester):
    await harvester.initialize()
    # Define the URLs to be scraped (from saved data, etc.)
    urls = st.session_state.urls
    emails = await harvester.harvest_emails(urls)
    await harvester.close()
    # Log and store the harvested emails

# Main Streamlit App Logic
def main():
    # Toggle proxy usage
    use_proxies = st.sidebar.checkbox("Enable Proxy Usage", value=True)

    harvester = get_harvester(use_proxies)

    st.write("Enter URLs to scrape emails from (one per line):")
    urls_input = st.text_area("URLs")
    max_depth = st.slider("Max Crawl Depth", 0, 5, 2)

    # Sidebar with tools
    st.sidebar.title("🔧 Tools")
    if st.sidebar.button("View Logs"):
        with open('scraper.log') as f:
            st.sidebar.text(f.read())

    # Schedule scraping task
    if st.sidebar.button("Schedule Scraping (Daily at 9 AM)"):
        scheduler.add_job(scheduled_scraping, 'cron', hour=9, minute=0)
        scheduler.start()
        st.sidebar.success("Scheduled scraping task added.")

    if scheduler.get_jobs():
        st.sidebar.write("Scheduled Jobs:")
        for job in scheduler.get_jobs():
            st.sidebar.write(f"- {job}")
    else:
        st.sidebar.write("No jobs scheduled.")

    # Feedback form
    feedback_text = st.sidebar.text_area("Submit your feedback or report an issue")
    if st.sidebar.button("Submit Feedback"):
        logging.info(f"Feedback submitted: {feedback_text}")
        st.sidebar.success("Thank you for your feedback!")

    # Start harvesting emails
    if st.button("Start Harvesting"):
        urls = [url.strip() for url in urls_input.splitlines() if url.strip()]
        if urls:
            with st.spinner('Harvesting emails...'):
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

                    # Export as CSV
                    csv = email_df.to_csv(index=False).encode('utf-8')
                    st.download_button(label="Download as CSV", data=csv, file_name="harvested_emails.csv", mime="text/csv")

                    # Export as Excel
                    excel_data = BytesIO()
                    email_df.to_excel(excel_data, index=False)
                    st.download_button(label="Download as Excel", data=excel_data.getvalue(), file_name='emails.xlsx',
                                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                else:
                    st.write("No emails found.")
        else:
            st.write("Please enter at least one URL.")

if __name__ == "__main__":
    main()
