"""
utils/styles.py
===============
Utility to load external CSS stylesheets into Streamlit.
Keeps app.py and UI modules clean and separated from design tokens.
"""

from pathlib import Path
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent.parent
CSS_PATH = BASE_DIR / "static" / "style.css"


def load_css() -> None:
    """Load and inject custom CSS from static/style.css into Streamlit."""
    if CSS_PATH.exists():
        css_content = CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
