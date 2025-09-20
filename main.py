import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table
from PIL import Image
from pathlib import Path
import base64

# 1. Page config & theming (set favicon to company logo)
st.set_page_config(
    page_title="Onward Field Service Analytics",
    page_icon="images/OnwardLogo.jpg",
    layout="wide"
)

# 2. Custom CSS: gradient background, black text, professional font, permanent tab highlight color
st.markdown(
    """
    <style>
      .stApp {
        background: hsla(328, 75%, 45%, 1);
        background: linear-gradient(90deg, hsla(328, 75%, 45%, 1) 0%, hsla(269, 85%, 41%, 1) 100%);
        background: -moz-linear-gradient(90deg, hsla(328, 75%, 45%, 1) 0%, hsla(269, 85%, 41%, 1) 100%);
        background: -webkit-linear-gradient(90deg, hsla(328, 75%, 45%, 1) 0%, hsla(269, 85%, 41%, 1) 100%);
        font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
      }
      /* Force darker black text for headers, labels, and buttons */
      h1, h2, h3, h4, h5, h6, label, .stButton>button, .stDownloadButton>button {
        color: #000000 !important;
        font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
      }
      .header-container {
        display: flex;
        align-items: center;
        gap: 10rem;
      }
      .header-container img {
        max-height: 80px;
        width: auto;
      }
      .header-title {
        font-size: 2rem;
        font-weight: bold;
        color: #000000;
        font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
      }
      /* Make tab highlight color permanent */
      div[data-baseweb="tab"] {
        color: white !important;
        background-color: #C81D77 !important; /* your highlight color */
        border-radius: 40px 40px 0 0;
        padding: 0.5rem 1rem;
      }
      div[data-baseweb="tab"]:hover {
        background-color: #a0155f !important; /* slightly darker on hover */
      }
      div[data-baseweb="tab-list"] {
        gap: 5rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)
# ... your existing st.markdown("""<style> ... </style>""", unsafe_allow_html=True) for background, fonts, tabs ...

st.markdown(
    """
    <style>
      /* Style ONLY the "Send to ..." buttons in the last row of columns */
      div[data-testid="column"] .stButton > button {
        background-color: white !important;
        color: black !important;
        border: 1px solid black !important;
        margin: 10px !important;        /* ⬅️ add spacing around buttons */
        padding: 0.6rem 1.2rem !important; /* ⬅️ slightly bigger click area */
      }
      div[data-testid="column"] .stButton > button:hover {
        background-color: #f0f0f0 !important;
        color: black !important;
        border: 1px solid black !important;
      }
    </style>
    """,
    unsafe_allow_html=True
)



# 3. Header with logo + title (side-by-side, proper base64 encoding)
with open("images/OnwardLogo.jpg", "rb") as f:
    logo_base64 = base64.b64encode(f.read()).decode()

st.markdown(
    f"""
    <div class="header-container">
        <img src="data:image/jpeg;base64,{logo_base64}" alt="Logo">
        <div class="header-title">Onward Field Service Analytics</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# 3. Path to Excel file (assume it's in ./sheets)
EXCEL_PATH = Path("sheets") / "spreadsheet.xlsx"

# 4. Helpers: fetch metadata + values
@st.cache_data(show_spinner=False)
def fetch_sheets_metadata():
    """Return list of (sheet_name, index) from Excel file."""
    xls = pd.ExcelFile(EXCEL_PATH)
    return [(name, idx) for idx, name in enumerate(xls.sheet_names)]

@st.cache_data(show_spinner=False)
def load_sheet_df(title: str) -> pd.DataFrame:
    """Load a specific sheet into a DataFrame with type conversions."""
    df = pd.read_excel(EXCEL_PATH, sheet_name=title)
    # auto-convert date-like columns
    for col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col])
        except Exception:
            pass
    # convert numeric strings to numbers
    df = df.apply(pd.to_numeric, errors="ignore")
    return df

# 5. PDF / XLSX utility
def df_to_pdf_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    data = [df.columns.tolist()] + df.values.tolist()
    doc.build([Table(data)])
    return buf.getvalue()

def df_to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Report")
    return buf.getvalue()

# 6. Build dynamic tabs
metadata = fetch_sheets_metadata()
tabs = st.tabs([title for title, _ in metadata])

for tab, (title, _) in zip(tabs, metadata):
    with tab:
        st.subheader(title)
        df = load_sheet_df(title)

        # 6a. Averages for numeric columns (excluding any datetime)
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if num_cols:
            avgs = df[num_cols].mean().round(2).to_dict()
            st.markdown("**Average values:**")
            st.json(avgs)

        # 6b. Interactive, sortable table
        st.dataframe(df, use_container_width=True)

        # 6c. Download buttons
        pdf_data = df_to_pdf_bytes(df)
        xlsx_data = df_to_xlsx_bytes(df)
        c1, c2 = st.columns(2)
        c1.download_button("Download PDF", pdf_data, f"{title}.pdf", "application/pdf")
        c2.download_button(
            "Download XLSX",
            xlsx_data,
            f"{title}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

st.markdown("---")
st.subheader("Download Reports 🚀")
report_choice = st.selectbox("Pick a report", [t for t, _ in metadata])
fmt = st.radio("Format", ["PDF", "XLSX"], horizontal=True)
data_bytes = df_to_pdf_bytes(load_sheet_df(report_choice)) if fmt == "PDF" else df_to_xlsx_bytes(load_sheet_df(report_choice))
ext = fmt.lower()

# Row of four image-buttons (stubbed)
cols = st.columns(4)
for col, platform, img in zip(
    cols,
    ["Salesforce", "Slack", "Snowflake", "Tableau"],
    ["images/Salesforce.png", "images/Slack.png", "images/Snowflake.png", "images/Tableau.png"]
):
    with col:
        st.image(img, use_container_width=True)
        if st.button(f"Send to {platform}", key=platform):
            st.success(f"{report_choice}.{ext} dispatched to {platform} (stub).")
