import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from io import BytesIO
import time
import random
import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
import json
from datetime import datetime, timedelta

# Setting page configuration
st.set_page_config(page_title='Robust Email Harvester', page_icon='⚒️', layout="wide", initial_sidebar_state="auto")
st.title("⚒️ Robust Email Harvester")

# Initialize session state
if 'urls' not in st.session_state:
    st.session_state.urls = []
if 'results_cache' not in st.session_state:
    st.session_state.results_cache = {}

# User agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
]

def validate_and_format_url(url):
    """Ensure the URL starts with http:// or https://, otherwise prepend https://."""
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url

def is_valid_email(email):
    """Check if an email address is valid using an enhanced regex pattern."""
    pattern = r'''(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])'''
    return re.match(pattern, email, re.IGNORECASE) is not None

async def fetch_url(session, url, depth=0, max_depth=2):
    """Fetch a URL and return its content."""
    if depth > max_depth:
        return []

    try:
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        async with session.get(url, headers=headers) as response:
            content = await response.text()
            soup = BeautifulSoup(content, 'html.parser')
            emails = set(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content))
            valid_emails = [email for email in emails if is_valid_email(email)]

            # Recursively crawl links
            links = soup.find_all('a', href=True)
            tasks = []
            for link in links[:5]:  # Limit to 5 links per page to avoid overloading
                href = link['href']
                full_url = urljoin(url, href)
                if urlparse(full_url).netloc == urlparse(url).netloc:
                    tasks.append(fetch_url(session, full_url, depth + 1, max_depth))
            
            results = await asyncio.gather(*tasks)
            for result in results:
                valid_emails.extend(result)

            return list(set(valid_emails))
    except Exception as e:
        st.error(f"Error fetching {url}: {str(e)}")
        return []

async def scrape_emails_from_urls(urls):
    """Scrape emails from multiple URLs asynchronously."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
    return [email for sublist in results for email in sublist]

# Streamlit interface
st.sidebar.title("⚙️ Configuration")
max_depth = st.sidebar.slider("Max Crawl Depth", 0, 5, 2)
rate_limit = st.sidebar.number_input("Rate Limit (requests per second)", min_value=0.1, max_value=10.0, value=1.0, step=0.1)

urls_input = st.text_area("Enter URLs to scrape emails from (one per line)")

if st.button("Start Scraping"):
    st.session_state.urls = [validate_and_format_url(url.strip()) for url in urls_input.splitlines() if url.strip()]
    
    # Check cache and filter out recently scraped URLs
    current_time = datetime.now()
    urls_to_scrape = []
    for url in st.session_state.urls:
        if url in st.session_state.results_cache:
            cache_time, _ = st.session_state.results_cache[url]
            if current_time - cache_time < timedelta(hours=1):  # Cache for 1 hour
                st.info(f"Using cached results for {url}")
                continue
        urls_to_scrape.append(url)
    
    if urls_to_scrape:
        progress_bar = st.progress(0)
        status_text = st.empty()

        async def main():
            all_emails = await scrape_emails_from_urls(urls_to_scrape)
            return all_emails

        all_emails = asyncio.run(main())

        # Update cache
        for url in urls_to_scrape:
            st.session_state.results_cache[url] = (current_time, all_emails)

        st.write(f"Found {len(all_emails)} unique emails.")
        
        if all_emails:
            email_df = pd.DataFrame(all_emails, columns=["Email"])
            st.write(email_df)

            # Export options
            col1, col2, col3 = st.columns(3)
            with col1:
                csv_data = email_df.to_csv(index=False).encode('utf-8')
                st.download_button(label="Download as CSV", data=csv_data, file_name='emails.csv', mime='text/csv')
            with col2:
                excel_data = BytesIO()
                email_df.to_excel(excel_data, index=False)
                excel_data.seek(0)
                st.download_button(label="Download as Excel", data=excel_data, file_name='emails.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            with col3:
                json_data = email_df.to_json(orient='records')
                st.download_button(label="Download as JSON", data=json_data, file_name='emails.json', mime='application/json')

# Feedback form using Formspree
st.sidebar.title("Feedback")
with st.sidebar.form(key='feedback_form'):
    feedback_text = st.text_area("Submit your feedback or report an issue")
    submit_button = st.form_submit_button(label='Submit Feedback')

    if submit_button:
        response = requests.post(
            'https://formspree.io/f/manwkbny',
            data={'message': feedback_text}
        )
        if response.ok:
            st.success("Thank you for your feedback! It has been sent successfully.")
        else:
            st.error("There was an issue sending your feedback. Please try again later.")

# Display current session state and cache info
st.sidebar.title("Debug Information")
st.sidebar.write("Current URLs in session:", st.session_state.urls)
st.sidebar.write("Cache size:", len(st.session_state.results_cache))
