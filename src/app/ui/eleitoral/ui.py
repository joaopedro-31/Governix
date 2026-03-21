from __future__ import annotations

import streamlit as st


def set_page():
    st.set_page_config(
        page_title="GOVERNIX • Eleições",
        layout="wide",
        initial_sidebar_state="collapsed",
    )


def inject_css():
    st.markdown(
        """
    <style>
    .block-container {
      padding-top: 0.8rem;
      padding-bottom: 1rem;
      padding-left: 0.8rem;
      padding-right: 0.8rem;
    }

    .metric-card {
      background: #111827;
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 12px;
      padding: 12px 14px;
    }

    .small-muted {
      color: #9ca3af;
      font-size: 0.88rem;
    }

    @media (max-width: 768px) {
      h1 { font-size: 1.25rem; }
      h2, h3 { font-size: 1.05rem; }
      .block-container { padding-left: 0.6rem; padding-right: 0.6rem; }
      div.stButton > button { width: 100%; }
      .stTextInput input { min-height: 44px; }
      div[data-baseweb="select"] { min-height: 44px; }
    }
    </style>
    """,
        unsafe_allow_html=True,
    )