# pages/bot_reports.py
import os
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from viz_utils import table_to_pdf
from sheets_utils import sheet_to_dataframe_api
#from crypto_utils import decrypt_log_file  # optional for now

st.set_page_config(page_title="Bot Reports", page_icon="📑", layout="wide")
st.title("Bot Service Reports")

# Ensure outputs/pdf exists
os.makedirs("outputs/pdf", exist_ok=True)

# --- Inputs ---
bot_number = st.text_input("Enter Bot Number (primary key)", "")
report_period = st.selectbox("Select report period", ["Weekly", "Quarterly", "Monthly"])

# --- Helper to get date cutoff ---
def get_date_cutoff(period: str):
    now = datetime.utcnow()
    if period == "Weekly":
        return now - timedelta(weeks=1)
    elif period == "Quarterly":
        return now - timedelta(days=90)
    elif period == "Monthly":
        return now - timedelta(days=30)
    else:
        return None

# --- Fetch and aggregate ---
if st.button("Generate Report"):
    if not bot_number.strip():
        st.error("Please enter a bot number.")
    elif "sheets_service" not in st.session_state or "spreadsheet_id" not in st.session_state:
        st.error("Google Sheets API not initialized. Please authenticate and load sheets first.")
    else:
        service = st.session_state.sheets_service
        spreadsheet_id = st.session_state.spreadsheet_id
        all_data = []
        cutoff = get_date_cutoff(report_period)

        for sheet in st.session_state.sheets:
            df = sheet_to_dataframe_api(service, spreadsheet_id, sheet["title"], sheet["gid"])
            if df.empty or "bot_number" not in [c.lower() for c in df.columns]:
                continue

            # Normalize column names
            df.columns = [c.strip().lower() for c in df.columns]

            # Filter by bot_number
            bot_df = df[df["bot_number"].astype(str) == bot_number.strip()]
            if bot_df.empty:
                continue

            # Optional: filter by date if a date column exists
            date_cols = [c for c in bot_df.columns if "date" in c]
            if cutoff and date_cols:
                try:
                    date_col = date_cols[0]
                    bot_df[date_col] = pd.to_datetime(bot_df[date_col], errors="coerce")
                    bot_df = bot_df[bot_df[date_col] >= cutoff]
                except Exception:
                    pass

            if not bot_df.empty:
                bot_df["source_sheet"] = sheet["title"]
                all_data.append(bot_df)

        if not all_data:
            st.warning(f"No records found for bot number {bot_number} in the selected period.")
        else:
            final_df = pd.concat(all_data, ignore_index=True)

            # --- Display table ---
            st.subheader(f"Service Records for Bot {bot_number}")
            st.dataframe(final_df)

            # --- Basic stats ---
            st.markdown("### Summary Statistics")
            st.write(f"Total records: {len(final_df)}")
            numeric_cols = final_df.select_dtypes(include="number").columns
            if len(numeric_cols) > 0:
                st.write(final_df[numeric_cols].describe())

            # --- Save PDF ---
            pdf_path = os.path.join("outputs/pdf", f"bot_{bot_number}_{report_period.lower()}_report.pdf")
            table_to_pdf(final_df, pdf_path, title=f"Bot {bot_number} - {report_period} Report")
            with open(pdf_path, "rb") as f:
                st.download_button(
                    label="Download PDF Report",
                    data=f.read(),
                    file_name=os.path.basename(pdf_path),
                    mime="application/pdf"
                )
