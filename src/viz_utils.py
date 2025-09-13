# viz_utils.py
import io
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

# Generate bar or pie for a single column. Returns Matplotlib fig and a PNG bytes payload.
def plot_column(df: pd.DataFrame, column: str, mode: str = "Bar"):
    series = df[column]
    # Categorical counts or numeric histogram (simple rule)
    if pd.api.types.is_numeric_dtype(series):
        counts = series.dropna()
        fig, ax = plt.subplots(figsize=(6,4))
        if mode == "Bar":
            counts.plot(kind="hist", ax=ax, bins=10, color="#4C78A8")
            ax.set_title(f"{column} - Histogram")
        else:
            # Pie of binned counts
            bins = pd.cut(counts, bins=5)
            pie_counts = bins.value_counts().sort_index()
            pie_counts.plot(kind="pie", ax=ax, autopct="%1.1f%%")
            ax.set_ylabel("")
            ax.set_title(f"{column} - Pie by bins")
    else:
        counts = series.value_counts(dropna=True)
        fig, ax = plt.subplots(figsize=(6,4))
        if mode == "Bar":
            counts.plot(kind="bar", ax=ax, color="#4C78A8")
            ax.set_title(f"{column} - Value Counts")
        else:
            counts.plot(kind="pie", ax=ax, autopct="%1.1f%%")
            ax.set_ylabel("")
            ax.set_title(f"{column} - Pie")
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=200)
    buf.seek(0)
    return fig, buf.getvalue()

# Simple pivot builder
def make_pivot(df: pd.DataFrame, index_cols: list[str], column_cols: list[str], value_col: str, aggfunc: str):
    if not index_cols and not column_cols:
        return pd.DataFrame()
    func = {"sum": "sum", "mean": "mean", "count": "count", "max": "max", "min": "min"}[aggfunc]
    pivot = pd.pivot_table(
        df,
        index=index_cols if index_cols else None,
        columns=column_cols if column_cols else None,
        values=value_col if value_col else None,
        aggfunc=func,
        fill_value=0,
        dropna=True,
    )
    return pivot

# Export a table dataframe to a simple PDF using ReportLab
def table_to_pdf(df: pd.DataFrame, out_path: str, title: str = "Pivot Table"):
    c = canvas.Canvas(out_path, pagesize=LETTER)
    width, height = LETTER
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, height - 40, title)
    c.setFont("Helvetica", 9)

    # Very simple table pagination
    x0, y = 40, height - 70
    max_rows_per_page = 40
    cols = list(map(str, df.columns)) if not isinstance(df.columns, pd.MultiIndex) else ["/".join(map(str, t)) for t in df.columns]
    header_line = [""] + cols
    rows_iter = df.reset_index().astype(str).values.tolist()
    page_rows = []

    def draw_page(rows):
        nonlocal y
        c.setFillColor(colors.black)
        c.drawString(x0, y, " | ".join(header_line))
        y -= 14
        for r in rows:
            c.drawString(x0, y, " | ".join(map(str, r)))
            y -= 12

    for r in rows_iter:
        page_rows.append(r)
        if len(page_rows) >= max_rows_per_page:
            draw_page(page_rows)
            c.showPage()
            c.setFont("Helvetica-Bold", 12)
            c.drawString(40, height - 40, title)
            c.setFont("Helvetica", 9)
            y = height - 70
            page_rows = []

    if page_rows:
        draw_page(page_rows)
    c.save()
    return out_path

# Export a chart PNG bytes to a single-page PDF
def chart_png_to_pdf(png_bytes: bytes, out_path: str, title: str):
    c = canvas.Canvas(out_path, pagesize=LETTER)
    width, height = LETTER
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, height - 40, title)
    # Write PNG to temp and draw; reportlab needs a filename or ImageReader
    img = ImageReader(io.BytesIO(png_bytes))
    # Fit image maintaining aspect
    iw, ih = img.getSize()
    max_w, max_h = width - 80, height - 120
    scale = min(max_w / iw, max_h / ih)
    dw, dh = iw * scale, ih * scale
    c.drawImage(img, 40, height - 80 - dh, width=dw, height=dh, preserveAspectRatio=True, anchor='c')
    c.save()
    return out_path
