import requests
from bs4 import BeautifulSoup
import streamlit as st
import re
import pandas as pd

# Set up page configuration
st.set_page_config(page_title='Email Scraper', page_icon='⚒️', initial_sidebar_state="auto")
st.title("⚒️ Email Scraper")

# Input for the URL
url = st.text_input("Enter URL to scrape emails from", "https://stan.store/brydon")

# Button to start scraping
if st.button("Start Scraping"):
    if url:
        try:
            # Show progress spinner while scraping
            with st.spinner("Scraping emails..."):
                response = requests.get(url)
                response.raise_for_status()  # Raise error for bad status codes
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Use regex to find email addresses
                emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', str(soup))
                emails = list(set(emails))  # Remove duplicates
                
                if emails:
                    st.success(f"Found {len(emails)} unique email(s):")
                    st.write(emails)
                    
                    # Convert email list to DataFrame for CSV download
                    email_df = pd.DataFrame(emails, columns=["Email"])
                    
                    # Download button for CSV
                    csv = email_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download as CSV",
                        data=csv,
                        file_name='emails.csv',
                        mime='text/csv'
                    )
                else:
                    st.info("No emails found on the page.")
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching the URL: {e}")
    else:
        st.warning("Please enter a valid URL.")

# Disclaimer
st.warning("⚠️ Warning: Note that not all websites may contain email addresses or allow email harvesting. Harvesting email addresses without permission may be a violation of the website's terms of service or applicable laws. Be sure to read and understand the website's terms of service and any applicable laws or regulations before scraping any website.")
