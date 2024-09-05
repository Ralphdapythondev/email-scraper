import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from io import BytesIO

# Setting page configuration
st.set_page_config(page_title='Streamlit Cloud Email Harvester', page_icon='⚒️', initial_sidebar_state="auto", menu_items=None)
st.title("⚒️ Email Harvester")

def validate_and_format_url(url):
    """Ensure the URL starts with http:// or https://, otherwise prepend https://."""
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url

def is_valid_email(email):
    """Check if an email address is valid."""
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.match(regex, email) is not None

def scrape_emails_from_url(url):
    """Scrape emails from a single URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', str(soup))
        emails = list(set([email for email in emails if is_valid_email(email)]))
        return emails
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to scrape {url}: {str(e)}")
        return []

# Text area for multiple URLs
urls_input = st.text_area("Enter URLs to scrape emails from (one per line)")

if st.button("Start Scraping"):
    urls = [validate_and_format_url(url.strip()) for url in urls_input.splitlines() if url.strip()]
    all_emails = []
    progress_bar = st.progress(0)
    
    for i, url in enumerate(urls):
        st.write(f"Scraping: {url}")
        emails = scrape_emails_from_url(url)
        all_emails.extend(emails)
        progress_bar.progress((i + 1) / len(urls))

    all_emails = list(set(all_emails))  # Remove duplicates
    st.write(f"Found {len(all_emails)} unique emails.")
    
    if all_emails:
        email_df = pd.DataFrame(all_emails, columns=["Email"])
        st.write(email_df)

        # Export as CSV
        csv_data = email_df.to_csv(index=False).encode('utf-8')
        st.download_button(label="Download as CSV", data=csv_data, file_name='emails.csv', mime='text/csv')

        # Export as Excel
        excel_data = BytesIO()
        email_df.to_excel(excel_data, index=False)
        st.download_button(label="Download as Excel", data=excel_data, file_name='emails.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# Feedback form
st.sidebar.title("Feedback")
feedback_text = st.sidebar.text_area("Submit your feedback or report an issue")
if st.sidebar.button("Submit Feedback"):
    st.sidebar.success("Thank you for your feedback!")
