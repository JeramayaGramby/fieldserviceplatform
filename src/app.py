# app.py
# Comment out the first import (Colab only)
# from google.colab import files

import os
import sys
import time
import json
import base64
import logging
import streamlit as st
import pandas as pd
from datetime import timedelta
from decouple import Config, RepositoryEnv
from crypto_utils import load_private_key, rsa_decrypt_env
from google_auth import assert_env_ready, write_client_credentials_json, authenticate_gspread, list_sheets_with_gids
from sheets_utils import validate_gid_or_assert, sheet_to_dataframe
from viz_utils import plot_column, make_pivot, table_to_pdf, chart_png_to_pdf
from scheduler import poll_changes

# Comment this out later on (configure logging in production differently)
logging.basicConfig(stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

st.set_page_config(page_title="GSheets Analyzer", page_icon="📊", layout="wide")
st.title("Google Sheets analyzer")

# App state
if "private_key_loaded" not in st.session_state:
    st.session_state.private_key_loaded = False
if "env_loaded" not in st.session_state:
    st.session_state.env_loaded = False
if "gc" not in st.session_state:
    st.session_state.gc = None
if "sheet_index" not in st.session_state:
    st.session_state.sheet_index = 0
if "sheets" not in st.session_state:
    st.session_state.sheets = []
if "spreadsheet" not in st.session_state:
    st.session_state.spreadsheet = None
if "spreadsheet_id_or_url" not in st.session_state:
    st.session_state.spreadsheet_id_or_url = ""

st.subheader("Step 1: Upload RSA private key")
key_file = st.file_uploader("Upload your RSA private key (.pem)", type=["pem", "key"])
if key_file and not st.session_state.private_key_loaded:
    key_bytes = key_file.read()
    # Optional password input if your key is encrypted
    key_password = st.text_input("Private key password (leave blank if none)", type="password")
    try:
        private_key = load_private_key(key_bytes, password=key_password.encode() if key_password else None)
        st.session_state.private_key_loaded = True
        st.success("Private key loaded.")
        st.session_state.private_key_obj = private_key
    except AssertionError as e:
        st.error(str(e))

st.subheader("Step 2: Upload encrypted .env")
if st.session_state.private_key_loaded:
    enc_env = st.file_uploader("Upload .env.enc (encrypted with corresponding public key)", type=["enc"])
    if enc_env and not st.session_state.env_loaded:
        try:
            decrypted = rsa_decrypt_env(st.session_state.private_key_obj, enc_env.read())
            # Save .env to project root (per requirement)
            with open(".env", "wb") as f:
                f.write(decrypted)
            # Load using decouple
            decouple_cfg = Config(RepositoryEnv(".env"))
            # Validate required keys
            missing = [k for k in ["client_id","project_id","auth_uri","token_uri","auth_provider_x509_cert_url","client_secret"]
                       if not decouple_cfg.get(k, default=None)]
            if missing:
                raise AssertionError(f"Missing required env vars: {', '.join(missing)}")
            # Also set process env for convenience
            for k in decouple_cfg._parser._values:
                os.environ[k] = decouple_cfg(k)
            st.session_state.env_loaded = True
            st.success("Decrypted .env and loaded configuration.")
        except AssertionError as e:
            st.error(str(e))

# After env is loaded, build credentials.json and auth
if st.session_state.env_loaded and st.session_state.gc is None:
    try:
        cred_path = write_client_credentials_json("credentials.json")
        st.session_state.gc = authenticate_gspread(cred_path, "token.json")
        st.success("Authenticated with Google.")
    except Exception as e:
        st.error(f"Google auth failed: {e}")

st.subheader("Step 3: Select spreadsheet")
if st.session_state.gc:
    st.caption("Provide Spreadsheet URL or ID")
    st.session_state.spreadsheet_id_or_url = st.text_input("Spreadsheet URL or ID", value=st.session_state.spreadsheet_id_or_url)
    if st.button("Load sheets"):
        try:
            sheets, sh = list_sheets_with_gids(st.session_state.gc, st.session_state.spreadsheet_id_or_url)
            st.session_state.sheets = sheets
            st.session_state.spreadsheet = sh
            st.session_state.sheet_index = 0
            st.success(f"Loaded {len(sheets)} sheets.")
        except Exception as e:
            st.error(f"Failed to open spreadsheet: {e}")

# Sidebar multipage-like navigation
if st.session_state.sheets:
    st.sidebar.header("Sheets")
    for i, s in enumerate(st.session_state.sheets):
        label = f"{s['title']} (gid={s['gid']})"
        if st.sidebar.button(label, key=f"nav_{i}"):
            st.session_state.sheet_index = i
            # Force rerun to update central view
            st.experimental_rerun()

    # Current sheet
    current_sheet = st.session_state.sheets[st.session_state.sheet_index]
    st.subheader(f"Sheet: {current_sheet['title']} (gid={current_sheet['gid']})")

    # Fetch DataFrame
    try:
        df = sheet_to_dataframe(st.session_state.spreadsheet, current_sheet["gid"])
    except AssertionError as e:
        st.error(str(e))
        df = pd.DataFrame()

    if df.empty:
        st.info("This sheet has no data.")
    else:
        # Toggle Bar/Pie
        st.markdown("#### Column visualization")
        col_left, col_right = st.columns([2, 3])

        with col_left:
            column_choice = st.selectbox("Select column", list(df.columns))
            mode = st.radio("Chart mode", ["Bar", "Pie"], horizontal=True)
            fig, png = plot_column(df, column_choice, mode=mode)
            st.pyplot(fig)

            # Download chart as PDF
            os.makedirs("outputs/pdf", exist_ok=True)
            chart_pdf_path = os.path.join("outputs/pdf", f"{current_sheet['title']}_{column_choice}_{mode}.pdf")
            chart_png_to_pdf(png, chart_pdf_path, title=f"{current_sheet['title']} - {column_choice} - {mode}")
            with open(chart_pdf_path, "rb") as f:
                st.download_button(
                    label="Download chart as PDF",
                    data=f.read(),
                    file_name=os.path.basename(chart_pdf_path),
                    mime="application/pdf"
                )

        with col_right:
            st.markdown("#### Pivot table")
            idx_cols = st.multiselect("Index", list(df.columns))
            col_cols = st.multiselect("Columns", list(df.columns))
            val_col = st.selectbox("Values", [""] + list(df.columns))
            aggfunc = st.selectbox("Aggregation", ["sum", "mean", "count", "max", "min"])

            if st.button("Build pivot"):
                pivot = make_pivot(df, idx_cols, col_cols, val_col if val_col else None, aggfunc)
                if pivot.empty:
                    st.info("Pivot is empty. Choose at least one Index or Column.")
                else:
                    st.dataframe(pivot)
                    # Download pivot as CSV
                    csv_bytes = pivot.to_csv().encode()
                    st.download_button("Download pivot CSV", data=csv_bytes, file_name=f"{current_sheet['title']}_pivot.csv", mime="text/csv")

                    # Download pivot as PDF
                    os.makedirs("outputs/pdf", exist_ok=True)
                    pivot_pdf_path = os.path.join("outputs/pdf", f"{current_sheet['title']}_pivot.pdf")
                    table_to_pdf(pivot if isinstance(pivot, pd.DataFrame) else pivot.to_frame(), pivot_pdf_path, title=f"{current_sheet['title']} - Pivot")
                    with open(pivot_pdf_path, "rb") as f:
                        st.download_button(
                            label="Download pivot as PDF",
                            data=f.read(),
                            file_name=os.path.basename(pivot_pdf_path),
                            mime="application/pdf"
                        )

        st.markdown("---")
        st.markdown("#### Scheduled refresh and change analysis")

        # Timedelta control
        amount = st.number_input("Every N units", min_value=1, value=10)
        unit = st.selectbox("Units", ["seconds", "minutes", "hours"])
        unit_to_kwargs = {"seconds": {"seconds": amount}, "minutes": {"minutes": amount}, "hours": {"hours": amount}}
        td = timedelta(**unit_to_kwargs[unit])

        # GID selection validated against actual workbook gids
        known_gids = set(s["gid"] for s in st.session_state.sheets)
        gid_input = st.text_input("GID to track", value=current_sheet["gid"])

        def fetch_and_analyze(gid: str):
            # Validate GID
            validate_gid_or_assert(gid, known_gids)
            # Re-fetch dataframe and do a very basic “change” check
            new_df = sheet_to_dataframe(st.session_state.spreadsheet, gid)
            st.session_state.setdefault("history", {})
            hist = st.session_state["history"].get(gid)
            if hist is not None:
                # Compare shape as a proxy; you can extend to cell-by-cell diffs
                if new_df.shape != hist["shape"]:
                    st.warning(f"Detected change in gid={gid}: shape {hist['shape']} -> {new_df.shape}")
            st.session_state["history"][gid] = {"shape": new_df.shape, "timestamp": time.time()}

        if st.button("Start demo polling (3 cycles)"):
            try:
                # Cool to use loops for timedelta and maintaining live updates for demos
                poll_changes(td, gid_input, fetch_and_analyze, stop_after=3)
                st.success("Polling completed.")
            except AssertionError as e:
                st.error(str(e))

st.sidebar.markdown("---")
st.sidebar.page_link("pages/mulesoft_hub.py", label="Integration hub 🧩")
st.sidebar.caption("Use the Integration hub to export PDFs to platforms.")

st.markdown("---")
#st.caption("Note: All files are saved locally under outputs/. In production, uncomment Airflow code and replace simulated exports with real API calls.")
st.sidebar.page_link("pages/bot_reports.py", label="Bot Service Reports 🤖")