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
        :root {
            --bg: #0F172A;
            --card: #111827;
            --card-2: #1E293B;
            --border: rgba(255,255,255,0.10);
            --text: #FFFFFF;
            --muted: #CBD5E1;

            --blue: #60A5FA;
            --green: #22C55E;
            --yellow: #FACC15;
            --white: #FFFFFF;
        }

        .stApp {
            background-color: var(--bg);
            color: var(--text);
        }

        .block-container {
            padding-top: 0.8rem;
            padding-bottom: 1rem;
            padding-left: 0.8rem;
            padding-right: 0.8rem;
        }

        h1, h2, h3, label, .stMarkdown, p {
            color: var(--text);
        }

        h1 {
            color: var(--blue);
        }

        .stCaption, .small-muted {
            color: var(--muted) !important;
        }

        hr {
            border: none;
            height: 2px;
            background: linear-gradient(90deg, var(--blue), var(--yellow), var(--green));
            border-radius: 999px;
        }

        form[data-testid="stForm"] {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 1rem;
        }

        .streamlit-expanderHeader {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            color: var(--white);
        }

        .stTextInput input,
        .stTextArea textarea,
        .stNumberInput input {
            background: var(--card-2) !important;
            color: var(--white) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
        }

        .stTextInput input:focus,
        .stTextArea textarea:focus,
        .stNumberInput input:focus {
            border: 1px solid var(--blue) !important;
            box-shadow: 0 0 0 1px var(--blue) !important;
        }

        /* SELECTBOX */
        div[data-baseweb="select"] > div {
            background: var(--card-2) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            color: var(--white) !important;
            min-height: 46px !important;
        }

        div[data-baseweb="select"] > div:hover {
            border: 1px solid var(--blue) !important;
        }

        div[data-baseweb="select"] > div:focus-within {
            border: 1px solid var(--blue) !important;
            box-shadow: 0 0 0 1px var(--blue) !important;
        }

        div[data-baseweb="select"] span {
            color: var(--white) !important;
        }

        div[data-baseweb="select"] svg {
            fill: var(--yellow) !important;
        }

        div[role="listbox"] {
            background: var(--card) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
        }

        div[role="option"] {
            background: var(--card) !important;
            color: var(--white) !important;
        }

        div[role="option"]:hover {
            background: rgba(96,165,250,0.18) !important;
            color: var(--white) !important;
        }

        div[aria-selected="true"] {
            background: rgba(34,197,94,0.22) !important;
            color: var(--white) !important;
        }

        /* BOTÕES */
        .stButton > button,
        .stDownloadButton > button,
        div.stFormSubmitButton > button {
            border-radius: 10px !important;
            border: none !important;
            font-weight: 700 !important;
            min-height: 44px !important;
        }

        div.stFormSubmitButton > button[kind="primary"],
        .stButton > button[kind="primary"] {
            background: var(--blue) !important;
            color: #0B1220 !important;
        }

        div.stFormSubmitButton > button[kind="primary"]:hover,
        .stButton > button[kind="primary"]:hover {
            background: #93C5FD !important;
            color: #0B1220 !important;
        }

        div.stFormSubmitButton > button[kind="secondary"],
        .stButton > button[kind="secondary"] {
            background: var(--green) !important;
            color: var(--white) !important;
        }

        div.stFormSubmitButton > button[kind="secondary"]:hover,
        .stButton > button[kind="secondary"]:hover {
            background: #16A34A !important;
            color: var(--white) !important;
        }

        .stDownloadButton > button {
            background: var(--yellow) !important;
            color: #1F2937 !important;
        }

        .stDownloadButton > button:hover {
            background: #FDE047 !important;
            color: #1F2937 !important;
        }

        /* MÉTRICAS */
        div[data-testid="stMetric"] {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px;
        }

        div[data-testid="stMetricLabel"] {
            color: var(--muted) !important;
        }

        div[data-testid="stMetricValue"] {
            color: var(--green) !important;
        }

        /* ALERTAS */
        div[data-testid="stAlert"] {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            color: var(--white);
        }

        /* DATAFRAME */
        div[data-testid="stDataFrame"] {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 14px;
            overflow: hidden;
        }

        /* LOADING */
        .ranking-loading-box {
            min-height: 180px;
            border-radius: 16px;
            border: 1px solid var(--border);
            background: var(--card);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            gap: 14px;
            margin: 8px 0 18px 0;
        }

        .ranking-loading-spinner {
            width: 56px;
            height: 56px;
            border: 6px solid rgba(255,255,255,0.12);
            border-top: 6px solid var(--blue);
            border-right: 6px solid var(--yellow);
            border-bottom: 6px solid var(--green);
            border-radius: 50%;
            animation: ranking-spin 0.9s linear infinite;
        }

        .ranking-loading-text {
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--white);
        }

        .ranking-loading-subtext {
            font-size: 0.95rem;
            color: var(--muted);
        }

        @keyframes ranking-spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        @media (max-width: 768px) {
            h1 { font-size: 1.25rem; }
            h2, h3 { font-size: 1.05rem; }
            .block-container { padding-left: 0.6rem; padding-right: 0.6rem; }
            div.stButton > button,
            div.stFormSubmitButton > button,
            .stDownloadButton > button {
                width: 100%;
            }
            .stTextInput input { min-height: 44px; }
            div[data-baseweb="select"] { min-height: 44px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_ranking_loading():
    placeholder = st.empty()

    placeholder.markdown(
        """
        <div class="ranking-loading-box">
            <div class="ranking-loading-spinner"></div>
            <div class="ranking-loading-text">Carregando ranking...</div>
            <div class="ranking-loading-subtext">Aguarde enquanto os dados são processados</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return placeholder