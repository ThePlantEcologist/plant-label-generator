"""Plant Label Generator: app entry point.

Streamlit Community Cloud runs this file. It sets up the pages:

    /          the label tool (homepage)
    /privacy   Privacy Policy
    /terms     Terms of Service
"""

import streamlit as st

st.set_page_config(
    page_title="Plant Label Generator",
    page_icon="🌿",
    layout="centered",
)

navigation = st.navigation(
    [
        st.Page("app_pages/label_tool.py", title="Label Generator", icon="🌿", default=True),
        st.Page("app_pages/privacy_policy.py", title="Privacy Policy", url_path="privacy"),
        st.Page("app_pages/terms_of_service.py", title="Terms of Service", url_path="terms"),
    ],
    position="top",
)
navigation.run()
