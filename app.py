import requests
from bs4 import BeautifulSoup
import streamlit as st
import re
import json

# Setting page configuration
st.set_page_config(page_title='Email Scraper', page_icon='⚒️', initial_sidebar_state="auto", menu_items=None)
st.title("⚒️ Email Scraper")

# Initialize favorites list in session state if not already present
if 'favorites' not in st.session_state:
    st.session_state.favorites = []

def validate_and_format_url(url):
    """Ensure the URL starts with http:// or https://, otherwise prepend https://."""
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url

# Sidebar for managing favorites
st.sidebar.title("🔖 Favorites")
selected_favorite = st.sidebar.selectbox("Select a favorite URL", options=st.session_state.favorites)

if st.sidebar.button("Remove selected favorite"):
    if selected_favorite in st.session_state.favorites:
        st.session_state.favorites.remove(selected_favorite)
        st.experimental_rerun()  # Refresh the page to update the list

# Input field for the URL
url = st.text_input("Enter URL to scrape emails from", selected_favorite if selected_favorite else "https://stan.store/brydon")

# Button to add the current URL to the favorites list
if st.button("Add to Favorites"):
    url = validate_and_format_url(url)
    if url not in st.session_state.favorites:
        st.session_state.favorites.append(url)
        st.success(f"Added {url} to favorites!")

# Validate and format the URL
url = validate_and_format_url(url)

# Make the request to the provided URL
try:
    response = requests.get(url)
    response.raise_for_status()  # Raise an exception for HTTP errors
except requests.exceptions.RequestException as e:
    st.error(f"An error occurred: {e}")
else:
    # Parse the webpage content
    soup = BeautifulSoup(response.text, 'html.parser')

    # Use regular expressions to find email addresses
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', str(soup))
    emails = list(set(emails))  # Remove duplicates

    # Display the extracted emails
    st.text(f"Found {len(emails)} email(s): {emails}")

    # Warning about legal considerations
    st.warning("⚠️ Warning: Note that not all websites may contain email addresses or allow email harvesting, and harvesting email addresses without permission may be a violation of the website's terms of service or applicable laws. Be sure to read and understand the website's terms of service and any applicable laws or regulations before scraping any website.")

    # Provide an option to download the emails as a .json file
    if emails:
        email_data = {"emails": emails}
        email_json = json.dumps(email_data, indent=4)

        st.download_button(
            label="Download emails as JSON",
            data=email_json,
            file_name="emails.json",
            mime="application/json"
        )
