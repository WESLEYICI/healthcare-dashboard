
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import time
import gc
from pathlib import Path

# ============================================================
# 1. KONFIGURASI DASHBOARD
# ============================================================

st.set_page_config(
    page_title="HealthInsight | Healthcare Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent

RAW_CSV_PATH = BASE_DIR / "csv"
FHIR_PATH = BASE_DIR / "fhir"
PROCESSED_PATH = BASE_DIR / "data"
METRICS_PATH = BASE_DIR / "processing_metrics.json"

MAIN_TABLES = [
    "patients",
    "encounters",
    "conditions",
    "observations"
]

# ============================================================
# 2. FUNGSI FORMAT DATA
# ============================================================

def format_number(value):
    try:
        return f"{int(value):,}".replace(",", ".")
    except (ValueError, TypeError, OverflowError):
        return "0"


def format_bytes(size):
    try:
        size = float(size)

        if size <= 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]

        for unit in units:
            if size < 1024:
                return f"{size:.2f} {unit}"

            size /= 1024

        return f"{size:.2f} PB"

    except (ValueError, TypeError):
        return "0 B"


def metric_card(title, value, caption=None):
    caption_html = f"<p>{caption}</p>" if caption else ""

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">{title}</div>
            <div class="metric-value">{value}</div>
            {caption_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def chart_layout(fig, title=None):
    fig.update_layout(
        title=dict(text=title or "", x=0.02, xanchor="left",
                   font=dict(size=17, color="#172033")),
        template="plotly_white",
        font=dict(family="Inter, Arial, sans-serif", size=12, color="#64748B"),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=24, r=24, t=62, b=24),
        height=390,
        hoverlabel=dict(bgcolor="#172033",
                        font=dict(color="#FFFFFF", family="Inter, Arial, sans-serif")),
        legend=dict(bgcolor="rgba(255,255,255,0)", font=dict(color="#64748B"))
    )
    fig.update_xaxes(showgrid=True, gridcolor="#EEF1F5", zeroline=False,
                     linecolor="#E6EAF0", tickfont=dict(color="#64748B"))
    fig.update_yaxes(showgrid=True, gridcolor="#EEF1F5", zeroline=False,
                     linecolor="#E6EAF0", tickfont=dict(color="#64748B"))
    return fig


def show_page_header(title, description):
    st.markdown(
        f"""
        <div class="page-heading">
            <div class="page-eyebrow">HEALTHCARE INTELLIGENCE / ANALYTICS</div>
            <div class="page-title">{title}</div>
            <div class="page-description">{description}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def show_section_title(title):
    st.markdown(f"### {title}")


def safe_value_counts(data, column, top=10):
    if data.empty or column not in data.columns:
        return pd.Series(dtype="int64")

    return data[column].value_counts().head(top)


def column_count(df, column):
    if df.empty or column not in df.columns:
        return 0

    return df[column].nunique()


def numeric_column(df, column):
    if df.empty or column not in df.columns:
        return pd.Series(dtype="float64")

    return pd.to_numeric(
        df[column],
        errors="coerce"
    ).dropna()


def get_date_column(df, candidates):
    for column in candidates:
        if column in df.columns:
            return column

    return None


# ============================================================
# 3. MEMBACA FILE RAW
# ============================================================

def get_csv_files(folder):
    folder = Path(folder)

    if not folder.exists():
        return []

    return sorted(folder.glob("*.csv"))


def folder_size_bytes(folder):
    folder = Path(folder)

    if not folder.exists():
        return 0

    total_size = 0

    try:
        for file in folder.rglob("*"):
            if file.is_file():
                try:
                    total_size += file.stat().st_size
                except OSError:
                    continue
    except OSError:
        pass

    return total_size


@st.cache_data(ttl=60, show_spinner="Membaca CSV...")
def read_csv_full(file_path):
    try:
        file_path = Path(file_path)

        if not file_path.exists():
            return pd.DataFrame()

        if file_path.stat().st_size == 0:
            return pd.DataFrame()

        return pd.read_csv(
            file_path,
            low_memory=False
        )

    except pd.errors.EmptyDataError:
        return pd.DataFrame()

    except Exception as error:
        print(f"Error membaca CSV {file_path}: {error}")
        return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner="Memuat data raw...")
def load_raw_main():
    data = {}

    for table in MAIN_TABLES:
        file_path = RAW_CSV_PATH / f"{table}.csv"

        if file_path.exists():
            data[table] = read_csv_full(str(file_path))
        else:
            data[table] = pd.DataFrame()

    return data


# ============================================================
# 4. MEMBACA DATA PROCESSED
# ============================================================

def get_part_files(folder):
    folder = Path(folder)

    if not folder.exists():
        return []

    return sorted(folder.glob("part-*.csv"))


@st.cache_data(ttl=60, show_spinner="Memuat hasil processing...")
def load_processed(table_name):
    folder = PROCESSED_PATH / table_name
    files = get_part_files(folder)

    if not files:
        return pd.DataFrame()

    dataframes = []

    for file in files:
        try:
            if file.stat().st_size == 0:
                continue

            df = pd.read_csv(
                file,
                low_memory=False
            )

            if not df.empty:
                dataframes.append(df)

        except Exception as error:
            print(f"Gagal membaca {file.name}: {error}")

    if not dataframes:
        return pd.DataFrame()

    return pd.concat(
        dataframes,
        ignore_index=True
    )


# ============================================================
# 5. INSPEKSI FILE CSV
# ============================================================

@st.cache_data(ttl=60)
def inspect_raw_csv_files():
    results = []

    for file in get_csv_files(RAW_CSV_PATH):
        try:
            header = pd.read_csv(
                file,
                nrows=0
            )

            results.append({
                "Nama File": file.name,
                "Jumlah Kolom": len(header.columns),
                "Nama Kolom": ", ".join(header.columns)
            })

        except Exception as error:
            print(f"Gagal inspeksi {file.name}: {error}")

    return pd.DataFrame(
        results,
        columns=[
            "Nama File",
            "Jumlah Kolom",
            "Nama Kolom"
        ]
    )


# ============================================================
# 6. INSPEKSI FILE FHIR JSON
# ============================================================

def inspect_fhir_files():
    if not FHIR_PATH.exists():
        return {
            "total": 0,
            "sample": None,
            "keys": []
        }

    files = sorted(FHIR_PATH.glob("*.json"))

    sample_data = None
    keys = []

    if files:
        try:
            with open(
                files[0],
                "r",
                encoding="utf-8"
            ) as file:
                sample_data = json.load(file)

            if isinstance(sample_data, dict):
                keys = list(sample_data.keys())

            elif isinstance(sample_data, list) and sample_data:
                if isinstance(sample_data[0], dict):
                    keys = list(sample_data[0].keys())

        except Exception as error:
            print(f"Gagal membaca FHIR JSON: {error}")

    return {
        "total": len(files),
        "sample": sample_data,
        "keys": keys
    }


# ============================================================
# 7. INISIALISASI SELURUH DATA
# ============================================================

raw_data = load_raw_main()

raw_csv_inventory = inspect_raw_csv_files()

fhir_info = inspect_fhir_files()

raw_total_records = sum(
    len(df) for df in raw_data.values()
)

raw_total_columns = sum(
    len(df.columns) for df in raw_data.values()
)

raw_total_size = folder_size_bytes(RAW_CSV_PATH)

fhir_total_size = folder_size_bytes(FHIR_PATH)

# Membaca hasil processing
start_dashboard_time = time.perf_counter()

processed_data = {
    table: load_processed(table)
    for table in MAIN_TABLES
}

dashboard_read_seconds = (
    time.perf_counter() - start_dashboard_time
)

gc.collect()

processed_total_records = sum(
    len(df) for df in processed_data.values()
)

processed_total_columns = sum(
    len(df.columns) for df in processed_data.values()
)

processed_total_size = folder_size_bytes(PROCESSED_PATH)

# ============================================================
# 8. MEMBACA METRIK PROCESSING PYSPARK
# ============================================================

pyspark_runtime = None

if METRICS_PATH.exists():
    try:
        with open(
            METRICS_PATH,
            "r",
            encoding="utf-8"
        ) as file:
            metrics_data = json.load(file)

        pyspark_runtime = float(
            metrics_data.get("processing_seconds")
        )

        if pyspark_runtime < 0:
            pyspark_runtime = None

    except (ValueError, TypeError, OSError, json.JSONDecodeError):
        pyspark_runtime = None


# ============================================================
# 9. PERHITUNGAN KUALITAS DATA
# ============================================================

def calculate_quality(data):
    results = []

    total_cells = 0
    total_missing = 0
    total_duplicates = 0

    for table in MAIN_TABLES:
        df = data[table]

        if df.empty:
            continue

        rows = len(df)
        columns = len(df.columns)
        cells = rows * columns

        missing = int(df.isnull().sum().sum())
        duplicates = int(df.duplicated().sum())

        completeness = (
            ((cells - missing) / cells) * 100
            if cells > 0 else 0
        )

        results.append({
            "Tabel": table.capitalize(),
            "Jumlah Baris": rows,
            "Jumlah Kolom": columns,
            "Data Kosong": missing,
            "Data Duplikat": duplicates,
            "Kelengkapan (%)": round(completeness, 2)
        })

        total_cells += cells
        total_missing += missing
        total_duplicates += duplicates

    total_completeness = (
        ((total_cells - total_missing) / total_cells) * 100
        if total_cells > 0 else 0
    )

    return {
        "dataframe": pd.DataFrame(results),
        "total_cells": total_cells,
        "total_missing": total_missing,
        "total_duplicates": total_duplicates,
        "completeness": total_completeness
    }


quality_info = calculate_quality(processed_data)

# ============================================================
# 10. CSS DASHBOARD
# ============================================================

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root {
        --ink:#172033; --muted:#718096; --navy:#101B2D;
        --gold:#C9A96E; --line:#E8ECF2; --canvas:#F4F6F9;
    }
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
    .stApp {
        background:radial-gradient(circle at 85% 0%,rgba(201,169,110,.09),transparent 26%),var(--canvas);
        color:var(--ink);
    }
    [data-testid="stHeader"] { background:rgba(244,246,249,.82); }
    .block-container { max-width:1500px;padding-top:2.1rem;padding-bottom:3rem; }
    h1,h2,h3,h4 { color:var(--ink);font-family:'Manrope',sans-serif;letter-spacing:-.025em; }
    h2 { font-size:1.45rem !important;font-weight:800 !important; }
    h3 { font-size:1.12rem !important;font-weight:700 !important; }
    p,label,.stMarkdown { color:#526174; }
    .page-heading { padding:8px 0 22px;margin-bottom:12px;border-bottom:1px solid var(--line); }
    .page-eyebrow { color:#A8874F;font-size:10px;font-weight:800;letter-spacing:.18em;margin-bottom:9px; }
    .page-title { color:var(--ink);font-family:'Manrope',sans-serif;font-size:clamp(28px,3vw,39px);line-height:1.16;font-weight:800;letter-spacing:-.045em; }
    .page-description { color:#7B8798;font-size:14px;margin-top:9px;max-width:760px;line-height:1.65; }
    .metric-card {
        position:relative;overflow:hidden;background:linear-gradient(145deg,#FFF,#FBFCFE);
        padding:21px 22px 19px;border-radius:16px;border:1px solid #E8ECF2;
        box-shadow:0 7px 22px rgba(23,32,51,.045);min-height:135px;margin-bottom:12px;
        transition:transform .2s ease,box-shadow .2s ease;
    }
    .metric-card:before { content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--gold); }
    .metric-card:hover { transform:translateY(-2px);box-shadow:0 12px 28px rgba(23,32,51,.08); }
    .metric-title { color:#8994A5;font-size:11px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;margin-bottom:13px; }
    .metric-value { color:var(--ink);font-family:'Manrope',sans-serif;font-size:clamp(23px,2vw,31px);line-height:1.15;font-weight:800;letter-spacing:-.04em;word-break:break-word; }
    .metric-card p { color:#9AA4B2;font-size:11px;margin-top:10px;margin-bottom:0; }
    .info-card {
        background:linear-gradient(120deg,#142238,#20344D);padding:24px 27px;border-radius:18px;
        border:1px solid rgba(201,169,110,.24);box-shadow:0 12px 30px rgba(16,27,45,.12);margin:8px 0 25px;
    }
    .info-card h3 { color:#F5E9D4 !important;margin:0 0 8px; }
    .info-card p { color:#C4CEDA !important;line-height:1.7;margin:0; }
    div[data-testid="stMetric"] { background:#FFF;padding:16px 18px;border-radius:14px;border:1px solid var(--line);box-shadow:0 5px 18px rgba(23,32,51,.035); }
    div[data-testid="stDataFrame"],div[data-testid="stTable"] { border:1px solid var(--line);border-radius:13px;overflow:hidden;background:#FFF; }
    div[data-testid="stPlotlyChart"] { background:rgba(255,255,255,.88);border:1px solid var(--line);border-radius:16px;padding:9px 9px 2px;box-shadow:0 6px 20px rgba(23,32,51,.035);margin:8px 0 16px; }
    div[data-testid="stExpander"] { background:#FFF;border:1px solid var(--line);border-radius:12px; }
    div[data-testid="stAlert"] { border-radius:12px;border:1px solid var(--line); }
    hr { border-color:var(--line) !important;margin:1.5rem 0 !important; }
    section[data-testid="stSidebar"] { background:linear-gradient(180deg,#101B2D 0%,#17263B 100%);border-right:1px solid rgba(255,255,255,.07); }
    section[data-testid="stSidebar"] > div { background:transparent; }
    section[data-testid="stSidebar"] * { color:#D8E0EA; }
    section[data-testid="stSidebar"] h1,section[data-testid="stSidebar"] h2,section[data-testid="stSidebar"] h3 { color:#F6EBDD !important; }
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color:#9EADBF !important; }
    section[data-testid="stSidebar"] hr { border-color:rgba(255,255,255,.12) !important; }
    section[data-testid="stSidebar"] div[role="radiogroup"] { gap:5px; }
    section[data-testid="stSidebar"] div[role="radiogroup"] label {
        background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.055);
        border-radius:10px;padding:9px 11px;transition:all .18s ease;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background:rgba(201,169,110,.13);border-color:rgba(201,169,110,.28); }
    section[data-testid="stSidebar"] div[role="radiogroup"] label p { color:#D8E0EA !important;font-size:13px; }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background:rgba(201,169,110,.16);border-color:rgba(201,169,110,.55); }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p { color:#F4DDB7 !important;font-weight:700; }
    section[data-testid="stSidebar"] .stButton button {
        background:rgba(201,169,110,.14);color:#F4DDB7;border:1px solid rgba(201,169,110,.42);
        border-radius:10px;font-weight:700;
    }
    section[data-testid="stSidebar"] .stButton button:hover { background:rgba(201,169,110,.24);border-color:#C9A96E; }
    .stButton button,.stDownloadButton button { border-radius:10px;font-weight:700; }
    .stSelectbox [data-baseweb="select"] > div,.stTextInput input { border-radius:10px; }
    @media(max-width:768px) {
        .block-container { padding:1.2rem 1rem 2rem; }
        .metric-card { min-height:115px;padding:17px; }
        .page-title { font-size:28px; }
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 11. SIDEBAR NAVIGASI
# ============================================================

st.sidebar.markdown(
    """
    <div style="padding:12px 4px 18px 4px;">
        <div style="display:flex;align-items:center;gap:11px;">
            <div style="width:42px;height:42px;border-radius:13px;
                        background:linear-gradient(145deg,#D8BD8A,#A8874F);
                        display:flex;align-items:center;justify-content:center;
                        color:#142238;font-size:21px;font-weight:900;">✚</div>
            <div>
                <div style="font-family:Manrope,sans-serif;font-size:17px;
                            font-weight:800;color:#F6EBDD;line-height:1.15;">
                    Health<span style="color:#D7B77D;">Insight</span>
                </div>
                <div style="font-size:10px;letter-spacing:.13em;color:#9EADBF;margin-top:4px;">
                    BIG DATA ANALYTICS
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.divider()

menu = st.sidebar.radio(
    "Navigasi Dashboard",
    [
        "Ringkasan",
        "Eksplorasi Raw Data",
        "Data Processing",
        "Perbandingan Raw vs Processed",
        "Data Pasien",
        "Kunjungan",
        "Diagnosis",
        "Observasi Kesehatan",
        "Kualitas Data",
        "Analisis Big Data 5Vs"
    ]
)

st.sidebar.divider()

st.sidebar.markdown("""
**Tentang Dashboard**

Dashboard ini digunakan untuk menganalisis
data rekam medis sintetis menggunakan
pendekatan Big Data 5Vs.

**Dataset:** Synthea Synthetic Patient Records
""")

st.sidebar.divider()

st.sidebar.caption(
    f"Raw Records: {format_number(raw_total_records)}"
)

st.sidebar.caption(
    f"Processed Records: {format_number(processed_total_records)}"
)

if st.sidebar.button("🔄 Refresh Dashboard"):
    st.cache_data.clear()
    st.rerun()


# ============================================================
# 12. HALAMAN RINGKASAN
# ============================================================

if menu == "Ringkasan":

    show_page_header(
        "Healthcare Big Data Dashboard",
        "Analisis data rekam medis menggunakan pendekatan Big Data."
    )

    st.markdown("""
    <div class="info-card">
        <h3>Selamat Datang</h3>
        <p>
        Dashboard ini menampilkan proses pengolahan dan analisis
        data kesehatan menggunakan teknologi Big Data.
        Data yang digunakan berasal dari Synthea dan merupakan
        data pasien sintetis, bukan rekam medis pasien sebenarnya.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Ringkasan Dataset")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card(
            "Total Data Mentah",
            format_number(raw_total_records),
            "4 tabel utama"
        )

    with col2:
        metric_card(
            "Total Data Processed",
            format_number(processed_total_records),
            "Hasil pengolahan PySpark"
        )

    with col3:
        metric_card(
            "File CSV Mentah",
            format_number(len(raw_csv_inventory)),
            "Seluruh file CSV"
        )

    with col4:
        metric_card(
            "File JSON FHIR",
            format_number(fhir_info["total"]),
            "File JSON terdeteksi"
        )

    st.markdown("### Jumlah Data per Tabel")

    summary_data = []

    for table in MAIN_TABLES:
        summary_data.append({
            "Tabel": table.capitalize(),
            "Raw Data": len(raw_data[table]),
            "Processed Data": len(processed_data[table])
        })

    summary_df = pd.DataFrame(summary_data)

    col1, col2 = st.columns(2)

    with col1:
        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True
        )

    with col2:
        fig = px.bar(
            summary_df,
            x="Tabel",
            y=["Raw Data", "Processed Data"],
            barmode="group",
            title="Perbandingan Jumlah Data"
        )

        st.plotly_chart(
            chart_layout(fig),
            use_container_width=True
        )

    st.markdown("### Ukuran Penyimpanan")

    col1, col2 = st.columns(2)

    with col1:
        metric_card(
            "Ukuran Raw Data",
            format_bytes(raw_total_size),
            "Folder csv/"
        )

    with col2:
        metric_card(
            "Ukuran Processed Data",
            format_bytes(processed_total_size),
            "Folder data/"
        )

    st.markdown("### Struktur Dataset")

    st.markdown("""
    | Tabel | Keterangan |
    |---|---|
    | Patients | Informasi identitas pasien sintetis |
    | Encounters | Data kunjungan atau interaksi medis |
    | Conditions | Data diagnosis dan kondisi kesehatan |
    | Observations | Data hasil pengamatan kesehatan |
    """)

    st.info(
        "Gunakan menu navigasi di sebelah kiri untuk melihat "
        "data mentah, hasil processing, perbandingan data, "
        "dan analisis Big Data 5Vs."
    )


# ============================================================
# 13. HALAMAN EKSPLORASI RAW DATA
# ============================================================

elif menu == "Eksplorasi Raw Data":

    show_page_header(
        "Eksplorasi Raw Data",
        "Melihat karakteristik dataset sebelum dilakukan proses pengolahan."
    )

    st.markdown("### Informasi Dataset Mentah")

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_card(
            "Jumlah File CSV",
            format_number(len(raw_csv_inventory)),
            "Dataset mentah"
        )

    with col2:
        metric_card(
            "Jumlah File JSON",
            format_number(fhir_info["total"]),
            "Dataset FHIR"
        )

    with col3:
        metric_card(
            "Ukuran Dataset",
            format_bytes(raw_total_size),
            "Folder csv/"
        )

    st.markdown("### Daftar File CSV")

    if not raw_csv_inventory.empty:

        st.dataframe(
            raw_csv_inventory[["Nama File", "Jumlah Kolom"]],
            use_container_width=True,
            hide_index=True
        )

        selected_file = st.selectbox(
            "Pilih file untuk melihat isi data:",
            raw_csv_inventory["Nama File"].tolist()
        )

        selected_path = RAW_CSV_PATH / selected_file

        selected_df = read_csv_full(str(selected_path))

        st.markdown(f"#### Preview {selected_file}")

        st.dataframe(
            selected_df.head(10),
            use_container_width=True
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            metric_card(
                "Jumlah Baris",
                format_number(len(selected_df))
            )

        with col2:
            metric_card(
                "Jumlah Kolom",
                format_number(len(selected_df.columns))
            )

        with col3:
            metric_card(
                "Data Kosong",
                format_number(selected_df.isnull().sum().sum())
            )

        with st.expander("Lihat Struktur Kolom"):

            column_info = pd.DataFrame({
                "Nama Kolom": selected_df.columns,
                "Tipe Data": selected_df.dtypes.astype(str).values,
                "Data Kosong": selected_df.isnull().sum().values
            })

            st.dataframe(
                column_info,
                use_container_width=True,
                hide_index=True
            )

    else:
        st.warning(
            "Tidak ditemukan file CSV pada folder csv/."
        )

    st.divider()

    st.markdown("### Informasi Dataset FHIR")

    st.write(
        f"Jumlah file JSON yang ditemukan: "
        f"**{format_number(fhir_info['total'])}**"
    )

    if fhir_info["sample"] is not None:

        st.markdown("#### Struktur JSON")

        st.json(fhir_info["sample"])

        st.markdown("#### Key JSON")

        st.write(fhir_info["keys"])

    else:
        st.info(
            "Belum ditemukan file JSON FHIR yang dapat dibaca."
        )


# ============================================================
# 14. HALAMAN DATA PROCESSING
# ============================================================

elif menu == "Data Processing":

    show_page_header(
        "Data Processing",
        "Melihat hasil pengolahan data menggunakan PySpark."
    )

    st.markdown("### Ringkasan Hasil Processing")

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_card(
            "Total Data",
            format_number(processed_total_records),
            "Seluruh tabel hasil processing"
        )

    with col2:
        metric_card(
            "Total Kolom",
            format_number(processed_total_columns),
            "Akumulasi kolom"
        )

    with col3:
        metric_card(
            "Ukuran Data",
            format_bytes(processed_total_size),
            "Folder data/"
        )

    st.markdown("### Hasil Processing per Tabel")

    processing_summary = []

    for table in MAIN_TABLES:

        raw_df = raw_data[table]
        processed_df = processed_data[table]

        processing_summary.append({
            "Nama Tabel": table.capitalize(),
            "Raw Rows": len(raw_df),
            "Processed Rows": len(processed_df),
            "Raw Columns": len(raw_df.columns),
            "Processed Columns": len(processed_df.columns),
            "Processed Files": len(
                get_part_files(PROCESSED_PATH / table)
            )
        })

    processing_df = pd.DataFrame(processing_summary)

    st.dataframe(
        processing_df,
        use_container_width=True,
        hide_index=True
    )

    st.markdown("### Preview Hasil Processing")

    selected_table = st.selectbox(
        "Pilih tabel hasil processing:",
        MAIN_TABLES,
        key="processed_preview"
    )

    selected_processed = processed_data[selected_table]

    if not selected_processed.empty:

        st.dataframe(
            selected_processed.head(10),
            use_container_width=True
        )

        st.markdown("#### Struktur Data")

        structure = pd.DataFrame({
            "Nama Kolom": selected_processed.columns,
            "Tipe Data": selected_processed.dtypes.astype(str).values,
            "Data Kosong": selected_processed.isnull().sum().values
        })

        st.dataframe(
            structure,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.warning(
            f"Data hasil processing untuk tabel {selected_table} "
            "belum ditemukan."
        )

    st.divider()

    st.markdown("### Penjelasan Proses")

    st.markdown("""
    Tahapan pengolahan data dilakukan menggunakan PySpark
    untuk membantu membaca dan memproses dataset kesehatan.

    Secara umum proses yang dilakukan meliputi:

    1. Membaca dataset CSV.
    2. Memeriksa struktur dan tipe data.
    3. Melakukan pengolahan data menggunakan PySpark.
    4. Menyimpan hasil pengolahan ke dalam folder data/.
    5. Menggunakan hasil tersebut untuk analisis lebih lanjut.
    """)

    st.info(
        "Halaman ini menampilkan hasil yang tersedia di folder data/. "
        "Waktu proses PySpark dicatat secara terpisah melalui "
        "processing_metrics.json."
    )


# ============================================================
# 15. HALAMAN PERBANDINGAN RAW VS PROCESSED
# ============================================================

elif menu == "Perbandingan Raw vs Processed":

    show_page_header(
        "Perbandingan Raw vs Processed",
        "Membandingkan kondisi dataset sebelum dan sesudah proses pengolahan."
    )

    st.markdown("### Perbandingan Jumlah Data")

    comparison_data = []

    for table in MAIN_TABLES:

        raw_rows = len(raw_data[table])
        processed_rows = len(processed_data[table])

        difference = processed_rows - raw_rows

        percentage = (
            (difference / raw_rows) * 100
            if raw_rows > 0 else 0
        )

        comparison_data.append({
            "Tabel": table.capitalize(),
            "Raw Data": raw_rows,
            "Processed Data": processed_rows,
            "Selisih": difference,
            "Perubahan (%)": round(percentage, 2)
        })

    comparison_df = pd.DataFrame(comparison_data)

    st.dataframe(
        comparison_df,
        use_container_width=True,
        hide_index=True
    )

    fig = px.bar(
        comparison_df,
        x="Tabel",
        y=["Raw Data", "Processed Data"],
        barmode="group",
        title="Perbandingan Jumlah Baris Raw dan Processed"
    )

    st.plotly_chart(
        chart_layout(fig),
        use_container_width=True
    )

    st.divider()

    st.markdown("### Perbandingan Jumlah Kolom")

    column_comparison = []

    for table in MAIN_TABLES:

        column_comparison.append({
            "Tabel": table.capitalize(),
            "Kolom Raw": len(raw_data[table].columns),
            "Kolom Processed": len(processed_data[table].columns)
        })

    column_df = pd.DataFrame(column_comparison)

    st.dataframe(
        column_df,
        use_container_width=True,
        hide_index=True
    )

    fig = px.bar(
        column_df,
        x="Tabel",
        y=["Kolom Raw", "Kolom Processed"],
        barmode="group",
        title="Perbandingan Jumlah Kolom"
    )

    st.plotly_chart(
        chart_layout(fig),
        use_container_width=True
    )

    st.divider()

    st.markdown("### Perbandingan Ukuran Penyimpanan")

    col1, col2 = st.columns(2)

    with col1:
        metric_card(
            "Ukuran Raw Data",
            format_bytes(raw_total_size),
            "Folder csv/"
        )

    with col2:
        metric_card(
            "Ukuran Processed Data",
            format_bytes(processed_total_size),
            "Folder data/"
        )

    size_comparison = pd.DataFrame({
        "Jenis Data": ["Raw Data", "Processed Data"],
        "Ukuran (Bytes)": [
            raw_total_size,
            processed_total_size
        ]
    })

    fig = px.bar(
        size_comparison,
        x="Jenis Data",
        y="Ukuran (Bytes)",
        title="Perbandingan Ukuran Penyimpanan"
    )

    st.plotly_chart(
        chart_layout(fig),
        use_container_width=True
    )

    st.info(
        "Perbedaan jumlah baris, kolom, dan ukuran penyimpanan "
        "digunakan untuk melihat perubahan dataset setelah "
        "proses pengolahan. Perubahan tersebut tidak otomatis "
        "berarti kualitas data meningkat."
    )


# ============================================================
# 16. HALAMAN DATA PASIEN
# ============================================================

elif menu == "Data Pasien":

    show_page_header(
        "Data Pasien",
        "Eksplorasi informasi pasien dari dataset Synthea."
    )

    patients = processed_data["patients"]

    if patients.empty:
        st.warning(
            "Data pasien hasil processing tidak tersedia."
        )

    else:

        st.markdown("### Ringkasan Data Pasien")

        col1, col2, col3 = st.columns(3)

        with col1:
            metric_card(
                "Total Pasien",
                format_number(len(patients))
            )

        with col2:
            metric_card(
                "Kategori Gender",
                format_number(column_count(patients, "GENDER"))
            )

        with col3:
            metric_card(
                "Jumlah Kota",
                format_number(column_count(patients, "CITY"))
            )

        st.markdown("### Preview Data Pasien")

        st.dataframe(
            patients.head(20),
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.markdown("### Distribusi Gender")

        if "GENDER" in patients.columns:

            gender_data = (
                patients["GENDER"]
                .value_counts()
                .reset_index()
            )

            gender_data.columns = ["Gender", "Jumlah"]

            fig = px.pie(
                gender_data,
                names="Gender",
                values="Jumlah",
                hole=0.4,
                title="Distribusi Gender Pasien"
            )

            st.plotly_chart(
                chart_layout(fig),
                use_container_width=True
            )

        else:
            st.info("Kolom GENDER tidak ditemukan.")

        st.divider()

        st.markdown("### Distribusi Pasien Berdasarkan Kota")

        if "CITY" in patients.columns:

            city_data = (
                patients["CITY"]
                .value_counts()
                .head(10)
                .reset_index()
            )

            city_data.columns = [
                "Kota",
                "Jumlah Pasien"
            ]

            fig = px.bar(
                city_data,
                x="Jumlah Pasien",
                y="Kota",
                orientation="h",
                title="10 Kota dengan Jumlah Pasien Terbanyak"
            )

            fig.update_layout(
                yaxis={"categoryorder": "total ascending"}
            )

            st.plotly_chart(
                chart_layout(fig),
                use_container_width=True
            )

        else:
            st.info("Kolom CITY tidak ditemukan.")

        st.divider()

        st.markdown("### Statistik Usia Pasien")

        if "BIRTHDATE" in patients.columns:

            birthdate = pd.to_datetime(
                patients["BIRTHDATE"],
                errors="coerce"
            )

            reference_date = pd.Timestamp.now().normalize()

            age = (
                reference_date.year - birthdate.dt.year
                - (
                    (birthdate.dt.month > reference_date.month)
                    | (
                        (birthdate.dt.month == reference_date.month)
                        & (birthdate.dt.day > reference_date.day)
                    )
                )
            )

            age = age.dropna()
            age = age[age >= 0]

            if not age.empty:

                age_df = pd.DataFrame({
                    "Usia": age
                })

                fig = px.histogram(
                    age_df,
                    x="Usia",
                    nbins=20,
                    title="Distribusi Usia Pasien"
                )

                st.plotly_chart(
                    chart_layout(fig),
                    use_container_width=True
                )

                col1, col2, col3 = st.columns(3)

                with col1:
                    metric_card(
                        "Usia Rata-rata",
                        f"{age.mean():.1f} tahun"
                    )

                with col2:
                    metric_card(
                        "Usia Minimum",
                        f"{age.min():.0f} tahun"
                    )

                with col3:
                    metric_card(
                        "Usia Maksimum",
                        f"{age.max():.0f} tahun"
                    )

            else:
                st.info("Tidak ditemukan tanggal lahir yang valid.")

        else:
            st.info("Kolom BIRTHDATE tidak ditemukan.")


# ============================================================
# 17. HALAMAN KUNJUNGAN
# ============================================================

elif menu == "Kunjungan":

    show_page_header(
        "Data Kunjungan Pasien",
        "Analisis aktivitas kunjungan atau interaksi medis pasien."
    )

    encounters = processed_data["encounters"]

    if encounters.empty:
        st.warning("Data kunjungan tidak tersedia.")

    else:

        st.markdown("### Ringkasan Kunjungan")

        col1, col2, col3 = st.columns(3)

        with col1:
            metric_card(
                "Total Kunjungan",
                format_number(len(encounters))
            )

        with col2:
            metric_card(
                "Pasien Terdaftar",
                format_number(column_count(encounters, "PATIENT"))
            )

        with col3:
            metric_card(
                "Jenis Kunjungan",
                format_number(column_count(encounters, "ENCOUNTERCLASS"))
            )

        st.markdown("### Preview Data Kunjungan")

        st.dataframe(
            encounters.head(20),
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.markdown("### Distribusi Jenis Kunjungan")

        if "ENCOUNTERCLASS" in encounters.columns:

            class_data = (
                encounters["ENCOUNTERCLASS"]
                .value_counts()
                .reset_index()
            )

            class_data.columns = [
                "Jenis Kunjungan",
                "Jumlah"
            ]

            fig = px.bar(
                class_data,
                x="Jenis Kunjungan",
                y="Jumlah",
                title="Distribusi Jenis Kunjungan Pasien"
            )

            st.plotly_chart(
                chart_layout(fig),
                use_container_width=True
            )

        else:
            st.info("Kolom ENCOUNTERCLASS tidak ditemukan.")

        st.divider()

        st.markdown("### Tren Kunjungan Berdasarkan Waktu")

        date_column = get_date_column(
            encounters,
            ["START", "DATE", "ENCOUNTERDATE"]
        )

        if date_column:

            date_data = encounters.copy()

            date_data[date_column] = pd.to_datetime(
                date_data[date_column],
                errors="coerce"
            )

            date_data = date_data.dropna(
                subset=[date_column]
            )

            if not date_data.empty:

                date_data["Bulan"] = (
                    date_data[date_column]
                    .dt.to_period("M")
                    .astype(str)
                )

                monthly_data = (
                    date_data.groupby("Bulan")
                    .size()
                    .reset_index(name="Jumlah Kunjungan")
                )

                fig = px.line(
                    monthly_data,
                    x="Bulan",
                    y="Jumlah Kunjungan",
                    markers=True,
                    title="Tren Kunjungan per Bulan"
                )

                st.plotly_chart(
                    chart_layout(fig),
                    use_container_width=True
                )

            else:
                st.info(
                    "Tidak ditemukan tanggal kunjungan yang valid."
                )

        else:
            st.info("Kolom tanggal kunjungan tidak ditemukan.")


# ============================================================
# 18. HALAMAN DIAGNOSIS
# ============================================================

elif menu == "Diagnosis":

    show_page_header(
        "Analisis Diagnosis",
        "Melihat kategori kondisi kesehatan yang tercatat pada pasien."
    )

    conditions = processed_data["conditions"]

    if conditions.empty:
        st.warning("Data diagnosis tidak tersedia.")

    else:

        st.markdown("### Ringkasan Diagnosis")

        col1, col2, col3 = st.columns(3)

        with col1:
            metric_card(
                "Total Catatan Diagnosis",
                format_number(len(conditions))
            )

        with col2:
            metric_card(
                "Jenis Diagnosis",
                format_number(column_count(conditions, "DESCRIPTION"))
            )

        with col3:
            metric_card(
                "Pasien dengan Diagnosis",
                format_number(column_count(conditions, "PATIENT"))
            )

        st.markdown("### Preview Data Diagnosis")

        st.dataframe(
            conditions.head(20),
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.markdown("### 10 Diagnosis Terbanyak")

        if "DESCRIPTION" in conditions.columns:

            diagnosis_data = (
                conditions["DESCRIPTION"]
                .value_counts()
                .head(10)
                .reset_index()
            )

            diagnosis_data.columns = [
                "Diagnosis",
                "Jumlah"
            ]

            fig = px.bar(
                diagnosis_data,
                x="Jumlah",
                y="Diagnosis",
                orientation="h",
                title="10 Diagnosis Paling Sering Ditemukan"
            )

            fig.update_layout(
                yaxis={"categoryorder": "total ascending"}
            )

            st.plotly_chart(
                chart_layout(fig),
                use_container_width=True
            )

            st.dataframe(
                diagnosis_data,
                use_container_width=True,
                hide_index=True
            )

        else:
            st.info("Kolom DESCRIPTION tidak ditemukan.")

        st.divider()

        st.markdown("### Distribusi Diagnosis Berdasarkan Waktu")

        if "START" in conditions.columns:

            date_data = conditions.copy()

            date_data["START"] = pd.to_datetime(
                date_data["START"],
                errors="coerce"
            )

            date_data = date_data.dropna(
                subset=["START"]
            )

            if not date_data.empty:

                date_data["Tahun"] = (
                    date_data["START"].dt.year
                )

                yearly_data = (
                    date_data.groupby("Tahun")
                    .size()
                    .reset_index(name="Jumlah Diagnosis")
                )

                fig = px.bar(
                    yearly_data,
                    x="Tahun",
                    y="Jumlah Diagnosis",
                    title="Jumlah Diagnosis per Tahun"
                )

                st.plotly_chart(
                    chart_layout(fig),
                    use_container_width=True
                )

            else:
                st.info("Tidak ditemukan tanggal diagnosis yang valid.")

        else:
            st.info("Kolom START tidak tersedia.")


# ============================================================
# 19. HALAMAN OBSERVASI KESEHATAN
# ============================================================

elif menu == "Observasi Kesehatan":

    show_page_header(
        "Observasi Kesehatan",
        "Analisis hasil pengamatan dan pengukuran kondisi kesehatan pasien."
    )

    observations = processed_data["observations"]

    if observations.empty:
        st.warning(
            "Data observasi kesehatan tidak tersedia."
        )

    else:

        st.markdown("### Ringkasan Observasi")

        col1, col2, col3 = st.columns(3)

        with col1:
            metric_card(
                "Total Observasi",
                format_number(len(observations))
            )

        with col2:
            metric_card(
                "Pasien Terobservasi",
                format_number(column_count(observations, "PATIENT"))
            )

        with col3:
            metric_card(
                "Jenis Observasi",
                format_number(column_count(observations, "DESCRIPTION"))
            )

        st.markdown("### Preview Data Observasi")

        st.dataframe(
            observations.head(20),
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.markdown("### Jenis Observasi Terbanyak")

        if "DESCRIPTION" in observations.columns:

            observation_data = (
                observations["DESCRIPTION"]
                .value_counts()
                .head(10)
                .reset_index()
            )

            observation_data.columns = [
                "Jenis Observasi",
                "Jumlah"
            ]

            fig = px.bar(
                observation_data,
                x="Jumlah",
                y="Jenis Observasi",
                orientation="h",
                title="10 Jenis Observasi Paling Sering"
            )

            fig.update_layout(
                yaxis={"categoryorder": "total ascending"}
            )

            st.plotly_chart(
                chart_layout(fig),
                use_container_width=True
            )

        else:
            st.info("Kolom DESCRIPTION tidak ditemukan.")

        st.divider()

        st.markdown("### Distribusi Nilai Observasi")

        if "VALUE" in observations.columns:

            numeric_values = numeric_column(
                observations,
                "VALUE"
            )

            if not numeric_values.empty:

                value_df = pd.DataFrame({
                    "Nilai": numeric_values
                })

                fig = px.histogram(
                    value_df,
                    x="Nilai",
                    nbins=30,
                    title="Distribusi Nilai Observasi"
                )

                st.plotly_chart(
                    chart_layout(fig),
                    use_container_width=True
                )

                col1, col2, col3 = st.columns(3)

                with col1:
                    metric_card(
                        "Nilai Rata-rata",
                        f"{numeric_values.mean():.2f}"
                    )

                with col2:
                    metric_card(
                        "Nilai Minimum",
                        f"{numeric_values.min():.2f}"
                    )

                with col3:
                    metric_card(
                        "Nilai Maksimum",
                        f"{numeric_values.max():.2f}"
                    )

            else:
                st.info(
                    "Kolom VALUE tidak memiliki nilai numerik "
                    "yang dapat divisualisasikan."
                )

        else:
            st.info("Kolom VALUE tidak ditemukan.")


# ============================================================
# 20. HALAMAN KUALITAS DATA
# ============================================================

elif menu == "Kualitas Data":

    show_page_header(
        "Analisis Kualitas Data",
        "Pemeriksaan kelengkapan, duplikasi, dan konsistensi dataset."
    )

    quality_df = quality_info["dataframe"]

    total_cells = quality_info["total_cells"]
    total_missing = quality_info["total_missing"]
    total_duplicates = quality_info["total_duplicates"]
    total_completeness = quality_info["completeness"]

    missing_percentage = (
        (total_missing / total_cells) * 100
        if total_cells > 0 else 0
    )

    st.markdown("### Ringkasan Kualitas Data")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card(
            "Kelengkapan Data",
            f"{total_completeness:.2f}%"
        )

    with col2:
        metric_card(
            "Data Kosong",
            format_number(total_missing),
            f"{missing_percentage:.2f}% dari seluruh sel"
        )

    with col3:
        metric_card(
            "Data Duplikat",
            format_number(total_duplicates)
        )

    with col4:
        metric_card(
            "Total Sel Data",
            format_number(total_cells)
        )

    st.divider()

    st.markdown("### Kualitas Data per Tabel")

    if not quality_df.empty:

        st.dataframe(
            quality_df,
            use_container_width=True,
            hide_index=True
        )

        fig = px.bar(
            quality_df,
            x="Tabel",
            y="Kelengkapan (%)",
            title="Persentase Kelengkapan Data per Tabel",
            range_y=[0, 100]
        )

        st.plotly_chart(
            chart_layout(fig),
            use_container_width=True
        )

        st.divider()

        st.markdown("### Perbandingan Data Kosong dan Terisi")

        filled_cells = total_cells - total_missing

        missing_chart = pd.DataFrame({
            "Status": ["Data Terisi", "Data Kosong"],
            "Jumlah": [filled_cells, total_missing]
        })

        if missing_chart["Jumlah"].sum() > 0:

            fig = px.pie(
                missing_chart,
                names="Status",
                values="Jumlah",
                hole=0.45,
                title="Proporsi Kelengkapan Dataset"
            )

            st.plotly_chart(
                chart_layout(fig),
                use_container_width=True
            )

        st.divider()

        st.markdown("### Pemeriksaan Data per Kolom")

        available_tables = [
            table for table in MAIN_TABLES
            if not processed_data[table].empty
        ]

        selected_table = st.selectbox(
            "Pilih tabel untuk pemeriksaan:",
            available_tables,
            key="quality_table"
        )

        selected_df = processed_data[selected_table]

        column_quality = pd.DataFrame({
            "Kolom": selected_df.columns,
            "Tipe Data": selected_df.dtypes.astype(str).values,
            "Data Kosong": selected_df.isnull().sum().values,
            "Data Unik": selected_df.nunique().values
        })

        column_quality["Kelengkapan (%)"] = (
            (
                1 - (
                    column_quality["Data Kosong"]
                    / len(selected_df)
                )
            ) * 100
        ).round(2)

        st.dataframe(
            column_quality,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.warning(
            "Data hasil processing tidak tersedia."
        )


# ============================================================
# 21. HALAMAN ANALISIS BIG DATA 5Vs
# ============================================================

elif menu == "Analisis Big Data 5Vs":

    show_page_header(
        "Big Data Executive Summary",
        "Analisis karakteristik dataset kesehatan berdasarkan pendekatan Big Data 5Vs."
    )

    # ========================================================
    # PERHITUNGAN INDIKATOR 5Vs
    # ========================================================

    # VOLUME
    volume_raw = raw_total_records
    volume_processed = processed_total_records

    # VELOCITY
    velocity = dashboard_read_seconds

    # VARIETY
    total_csv = len(raw_csv_inventory)
    total_json = fhir_info["total"]
    total_files = total_csv + total_json

    # VERACITY
    total_cells_5v = quality_info["total_cells"]
    total_missing_5v = quality_info["total_missing"]
    total_duplicates_5v = quality_info["total_duplicates"]
    completeness_5v = quality_info["completeness"]

    quality_5v_df = quality_info["dataframe"].copy()

    # VALUE
    conditions = processed_data["conditions"]
    encounters = processed_data["encounters"]
    observations = processed_data["observations"]

    unique_diagnoses = column_count(
        conditions,
        "DESCRIPTION"
    )

    unique_encounter_types = column_count(
        encounters,
        "ENCOUNTERCLASS"
    )

    unique_observation_types = column_count(
        observations,
        "DESCRIPTION"
    )

    # ========================================================
    # KPI SUMMARY
    # ========================================================

    st.markdown("### Executive KPI Summary")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        metric_card(
            "VOLUME",
            format_number(volume_processed),
            f"Raw: {format_number(volume_raw)} records"
        )

    with col2:
        metric_card(
            "VELOCITY",
            f"{velocity:.2f} detik",
            "Waktu baca data dashboard"
        )

    with col3:
        metric_card(
            "VARIETY",
            format_number(total_files),
            f"{total_csv} CSV + {total_json} JSON"
        )

    with col4:
        metric_card(
            "VERACITY",
            f"{completeness_5v:.2f}%",
            f"{format_number(total_missing_5v)} sel kosong"
        )

    with col5:
        metric_card(
            "VALUE",
            format_number(unique_diagnoses),
            "Kategori diagnosis unik"
        )

    st.divider()

    # ========================================================
    # 1. VOLUME
    # ========================================================

    st.markdown("## 1. Volume")

    st.write(
        "Volume menggambarkan jumlah data yang disimpan dan "
        "diolah dalam sistem Big Data."
    )

    col1, col2 = st.columns(2)

    with col1:
        metric_card(
            "Total Raw Records",
            format_number(volume_raw),
            "Empat tabel utama"
        )

    with col2:
        metric_card(
            "Total Processed Records",
            format_number(volume_processed),
            "Empat tabel hasil PySpark"
        )

    volume_comparison = pd.DataFrame({
        "Jenis Data": ["Raw Data", "Processed Data"],
        "Jumlah Record": [
            volume_raw,
            volume_processed
        ]
    })

    fig = px.bar(
        volume_comparison,
        x="Jenis Data",
        y="Jumlah Record",
        title="Perbandingan Volume Data"
    )

    st.plotly_chart(
        chart_layout(fig),
        use_container_width=True
    )

    st.markdown("### Volume per Tabel")

    volume_table = pd.DataFrame([
        {
            "Tabel": table.capitalize(),
            "Raw Records": len(raw_data[table]),
            "Processed Records": len(processed_data[table])
        }
        for table in MAIN_TABLES
    ])

    st.dataframe(
        volume_table,
        use_container_width=True,
        hide_index=True
    )

    col1, col2 = st.columns(2)

    with col1:
        metric_card(
            "Ukuran Raw Data",
            format_bytes(raw_total_size)
        )

    with col2:
        metric_card(
            "Ukuran Processed Data",
            format_bytes(processed_total_size)
        )

    st.divider()

    # ========================================================
    # 2. VELOCITY
    # ========================================================

    st.markdown("## 2. Velocity")

    st.write(
        "Velocity menggambarkan kecepatan data dibaca, "
        "diproses, dan disediakan untuk analisis."
    )

    col1, col2 = st.columns(2)

    with col1:
        metric_card(
            "Waktu Baca Dashboard",
            f"{velocity:.4f} detik",
            "Waktu pemanggilan data processed"
        )

    with col2:

        if pyspark_runtime is not None:

            metric_card(
                "Waktu Processing PySpark",
                f"{pyspark_runtime:.2f} detik",
                "Waktu dari pipeline Google Colab"
            )

        else:

            metric_card(
                "Waktu Processing PySpark",
                "Belum tersedia",
                "Tambahkan processing_metrics.json"
            )

    st.markdown("### Bukti Pengukuran Velocity")

    velocity_labels = ["Waktu baca dashboard"]
    velocity_values = [velocity]

    if pyspark_runtime is not None:
        velocity_labels.append("Waktu processing PySpark")
        velocity_values.append(pyspark_runtime)

    velocity_df = pd.DataFrame({
        "Pengukuran": velocity_labels,
        "Durasi (detik)": velocity_values
    })

    fig = px.bar(
        velocity_df,
        x="Pengukuran",
        y="Durasi (detik)",
        title="Perbandingan Waktu Pengukuran"
    )

    st.plotly_chart(
        chart_layout(fig),
        use_container_width=True
    )

    st.info(
        "Waktu baca dashboard berbeda dengan waktu pemrosesan PySpark. "
        "Waktu baca dashboard dapat dipengaruhi oleh cache Streamlit. "
        "Untuk mengukur velocity pipeline Big Data, gunakan "
        "waktu processing yang dicatat langsung di Google Colab."
    )

    st.divider()

    # ========================================================
    # 3. VARIETY
    # ========================================================

    st.markdown("## 3. Variety")

    st.write(
        "Variety menggambarkan keberagaman format dan struktur data "
        "yang digunakan dalam sistem."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_card(
            "File CSV",
            format_number(total_csv),
            "Data tabular"
        )

    with col2:
        metric_card(
            "File JSON",
            format_number(total_json),
            "Data FHIR"
        )

    with col3:
        metric_card(
            "Total File",
            format_number(total_files),
            "CSV dan JSON"
        )

    variety_df = pd.DataFrame({
        "Format": ["CSV", "JSON"],
        "Jumlah File": [total_csv, total_json]
    })

    if total_files > 0:

        fig = px.pie(
            variety_df,
            names="Format",
            values="Jumlah File",
            hole=0.4,
            title="Komposisi Format Data"
        )

        st.plotly_chart(
            chart_layout(fig),
            use_container_width=True
        )

    else:
        st.info("Belum ditemukan file CSV maupun JSON.")

    st.markdown("### Jumlah Kolom pada Empat Tabel Utama")

    variety_columns = pd.DataFrame([
        {
            "Tabel": table.capitalize(),
            "Jumlah Kolom Raw": len(raw_data[table].columns),
            "Jumlah Kolom Processed": len(processed_data[table].columns)
        }
        for table in MAIN_TABLES
    ])

    st.dataframe(
        variety_columns,
        use_container_width=True,
        hide_index=True
    )

    if fhir_info["sample"] is not None:

        st.markdown("### Contoh Struktur JSON FHIR")

        st.write("Key yang ditemukan pada sampel JSON:")

        st.write(fhir_info["keys"])

        with st.expander("Lihat Contoh JSON"):
            st.json(fhir_info["sample"])

    st.divider()

    # ========================================================
    # 4. VERACITY
    # ========================================================

    st.markdown("## 4. Veracity")

    st.write(
        "Veracity menggambarkan kualitas dan tingkat kepercayaan "
        "terhadap data yang digunakan."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_card(
            "Kelengkapan Data",
            f"{completeness_5v:.2f}%"
        )

    with col2:
        metric_card(
            "Data Kosong",
            format_number(total_missing_5v)
        )

    with col3:
        metric_card(
            "Data Duplikat",
            format_number(total_duplicates_5v)
        )

    st.markdown("### Kualitas Data per Tabel")

    if not quality_5v_df.empty:

        st.dataframe(
            quality_5v_df,
            use_container_width=True,
            hide_index=True
        )

        fig = px.bar(
            quality_5v_df,
            x="Tabel",
            y="Kelengkapan (%)",
            title="Kelengkapan Data per Tabel",
            range_y=[0, 100]
        )

        st.plotly_chart(
            chart_layout(fig),
            use_container_width=True
        )

        filled_cells = (
            total_cells_5v - total_missing_5v
        )

        veracity_df = pd.DataFrame({
            "Status": ["Data Terisi", "Data Kosong"],
            "Jumlah": [
                filled_cells,
                total_missing_5v
            ]
        })

        if veracity_df["Jumlah"].sum() > 0:

            fig = px.pie(
                veracity_df,
                names="Status",
                values="Jumlah",
                hole=0.4,
                title="Proporsi Data Terisi dan Kosong"
            )

            st.plotly_chart(
                chart_layout(fig),
                use_container_width=True
            )

    else:
        st.warning(
            "Data processed belum tersedia untuk analisis veracity."
        )

    st.divider()

    # ========================================================
    # 5. VALUE
    # ========================================================

    st.markdown("## 5. Value")

    st.write(
        "Value menggambarkan manfaat data yang diperoleh "
        "melalui analisis untuk menghasilkan informasi."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_card(
            "Diagnosis Unik",
            format_number(unique_diagnoses)
        )

    with col2:
        metric_card(
            "Jenis Kunjungan",
            format_number(unique_encounter_types)
        )

    with col3:
        metric_card(
            "Jenis Observasi",
            format_number(unique_observation_types)
        )

    st.markdown("### 10 Diagnosis Terbanyak")

    if "DESCRIPTION" in conditions.columns:

        top_diagnoses = (
            conditions["DESCRIPTION"]
            .value_counts()
            .head(10)
            .reset_index()
        )

        top_diagnoses.columns = [
            "Diagnosis",
            "Jumlah"
        ]

        fig = px.bar(
            top_diagnoses,
            x="Jumlah",
            y="Diagnosis",
            orientation="h",
            title="Diagnosis yang Paling Sering Ditemukan"
        )

        fig.update_layout(
            yaxis={"categoryorder": "total ascending"}
        )

        st.plotly_chart(
            chart_layout(fig),
            use_container_width=True
        )

    else:
        st.info("Kolom DESCRIPTION diagnosis tidak ditemukan.")

    st.markdown("### Distribusi Jenis Kunjungan")

    if "ENCOUNTERCLASS" in encounters.columns:

        top_encounters = (
            encounters["ENCOUNTERCLASS"]
            .value_counts()
            .reset_index()
        )

        top_encounters.columns = [
            "Jenis Kunjungan",
            "Jumlah"
        ]

        fig = px.pie(
            top_encounters,
            names="Jenis Kunjungan",
            values="Jumlah",
            hole=0.4,
            title="Distribusi Jenis Kunjungan"
        )

        st.plotly_chart(
            chart_layout(fig),
            use_container_width=True
        )

    else:
        st.info("Kolom ENCOUNTERCLASS tidak ditemukan.")

    st.markdown("### Interpretasi Value")

    st.markdown(f"""
    Berdasarkan hasil analisis, dataset memiliki
    **{format_number(unique_diagnoses)} kategori diagnosis unik**,
    **{format_number(unique_encounter_types)} jenis kunjungan**,
    dan **{format_number(unique_observation_types)} jenis observasi**.

    Informasi tersebut dapat dimanfaatkan untuk memahami
    pola kunjungan pasien, variasi diagnosis, dan jenis
    pengamatan kesehatan yang tercatat dalam dataset.
    """)

    st.divider()

    st.success(
        "Analisis Big Data 5Vs selesai. "
        "Seluruh indikator ditampilkan berdasarkan data "
        "yang tersedia pada folder proyek."
    )
