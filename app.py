import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from io import BytesIO

# Setting page configuration
st.set_page_config(page_title='Streamlit Cloud Email Harvester', page_icon='🌾', initial_sidebar_state="auto", menu_items=None)
st.title("🌾 Email Harvester")

# Initialize session state for batch processing
if 'urls' not in st.session_state:
    st.session_state.urls = []

def validate_and_format_url(url):
    """Ensure the URL starts with http:// or https://, otherwise prepend https://."""
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url

def is_valid_email(email):
    """Check if an email address is valid using an enhanced regex pattern."""
    pattern = r'''(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])'''
    return re.match(pattern, email, re.IGNORECASE) is not None

def scrape_emails_from_url(url):
    """Scrape emails from a single URL using the enhanced regex pattern."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        pattern = r'''(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])'''
        emails = re.findall(pattern, str(soup), re.IGNORECASE)
        emails = list(set([email for email in emails if is_valid_email(email)]))
        st.info(f"Successfully scraped {len(emails)} emails from {url}")
        return emails
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to scrape {url}: {str(e)}")
        return []

# Text area for multiple URLs
urls_input = st.text_area("Enter URLs to scrape emails from (one per line)")

if st.button("Start Scraping"):
    st.session_state.urls = [validate_and_format_url(url.strip()) for url in urls_input.splitlines() if url.strip()]
    all_emails = []
    progress_bar = st.progress(0)
    
    for i, url in enumerate(st.session_state.urls):
        st.write(f"Scraping: {url}")
        emails = scrape_emails_from_url(url)
        all_emails.extend(emails)
        progress_bar.progress((i + 1) / len(st.session_state.urls))

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
        excel_data.seek(0)
        st.download_button(label="Download as Excel", data=excel_data, file_name='emails.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# Feedback form
st.sidebar.title("Feedback")
feedback_text = st.sidebar.text_area("Submit your feedback or report an issue")
if st.sidebar.button("Submit Feedback"):
    st.sidebar.success("Thank you for your feedback!")
    # Here you would typically send this feedback to a database or email
    # For now, we'll just print it to the Streamlit app
    st.sidebar.write("Feedback received:", feedback_text)

# Display current session state
st.sidebar.title("Debug Information")
st.sidebar.write("Current URLs in session:", st.session_state.urls)
