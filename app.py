
import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os
import gc
import html
import textwrap

# ============================================================
# 1. KONFIGURASI APLIKASI
# ============================================================

st.set_page_config(
    page_title="Healthcare Analytics Dashboard",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data")

DATA_COLUMNS = {
    "patients": [
        "ID", "BIRTHDATE", "DEATHDATE",
        "GENDER", "RACE", "MARITAL"
    ],
    "encounters": [
        "ID", "PATIENT", "START", "STOP",
        "ENCOUNTERCLASS", "TOTAL_CLAIM_COST"
    ],
    "conditions": [
        "ID", "PATIENT", "ENCOUNTER",
        "START", "STOP", "DESCRIPTION"
    ],
    "observations": [
        "ID", "PATIENT", "ENCOUNTER",
        "DATE", "CATEGORY", "DESCRIPTION", "VALUE"
    ]
}


# ============================================================
# 2. PENGATURAN GRAFIK
# ============================================================

px.defaults.template = "plotly_white"

px.defaults.color_discrete_sequence = [
    "#2563EB",
    "#60A5FA",
    "#93C5FD",
    "#1E40AF",
    "#64748B",
    "#0F766E",
    "#F59E0B"
]


# ============================================================
# 3. CSS GLOBAL
# ============================================================

st.markdown("""
<style>

/* Background */
.stApp {
    background-color: #F4F7FB;
}

/* Main container */
.block-container {
    max-width: 1500px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #FFFFFF;
    border-right: 1px solid #E5EAF2;
}

[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.5rem;
}

[data-testid="stSidebar"] p {
    color: #64748B;
}

/* Typography */
h1 {
    color: #172B4D;
    font-size: 30px !important;
    font-weight: 750 !important;
}

h2 {
    color: #203B63;
    font-size: 23px !important;
    font-weight: 700 !important;
}

h3 {
    color: #334B6B;
    font-size: 18px !important;
    font-weight: 650 !important;
}

p {
    color: #475569;
    line-height: 1.65;
}

/* Metric cards */
[data-testid="stMetric"] {
    background-color: #FFFFFF;
    border: 1px solid #E3EAF3;
    border-radius: 13px;
    padding: 18px 20px;
    min-height: 110px;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.035);
}

[data-testid="stMetricLabel"] {
    color: #64748B;
    font-size: 13px;
    font-weight: 600;
}

[data-testid="stMetricValue"] {
    color: #1D4ED8;
    font-size: 27px;
    font-weight: 750;
}

/* Containers */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FFFFFF;
    border-radius: 13px;
    border-color: #E3EAF3;
}

/* Charts */
[data-testid="stPlotlyChart"] {
    background-color: #FFFFFF;
    border: 1px solid #E3EAF3;
    border-radius: 13px;
    padding: 8px;
}

/* Tables */
[data-testid="stDataFrame"] {
    background-color: #FFFFFF;
    border: 1px solid #E3EAF3;
    border-radius: 10px;
}

/* Inputs */
[data-baseweb="select"] > div {
    border-radius: 8px;
    border-color: #D8E2EF;
}

/* Buttons */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
}

/* Alerts */
[data-testid="stAlert"] {
    border-radius: 10px;
}

/* Divider */
hr {
    border-color: #E2E8F0;
    margin-top: 1.5rem;
    margin-bottom: 1.5rem;
}

/* Caption */
.stCaption {
    color: #8492A6;
    font-size: 12px;
}

/* Footer */
footer {
    visibility: hidden;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# 4. FUNGSI MEMUAT DATASET
# ============================================================

@st.cache_data(show_spinner=False)
def load_data(table_name):

    folder = os.path.join(DATA_PATH, table_name)

    files = sorted(
        glob.glob(os.path.join(folder, "part-*.csv"))
    )

    if not files:
        files = sorted(
            glob.glob(os.path.join(folder, "*.csv"))
        )

    if not files:
        raise FileNotFoundError(
            f"Tidak ditemukan file CSV pada folder: {folder}"
        )

    required_columns = DATA_COLUMNS[table_name]

    data_parts = []

    for file in files:

        try:

            available_columns = pd.read_csv(
                file,
                nrows=0
            ).columns.tolist()

            selected_columns = [
                column
                for column in required_columns
                if column in available_columns
            ]

            if not selected_columns:
                raise ValueError(
                    f"Kolom yang dibutuhkan tidak ditemukan: {file}"
                )

            part = pd.read_csv(
                file,
                usecols=selected_columns,
                low_memory=True,
                on_bad_lines="error"
            )

            data_parts.append(part)

            del part

        except Exception as error:

            raise RuntimeError(
                f"Gagal membaca file {file}: {error}"
            ) from error

    if len(data_parts) == 1:
        data = data_parts[0]
    else:
        data = pd.concat(
            data_parts,
            ignore_index=True,
            copy=False
        )

    del data_parts
    gc.collect()

    return data


# ============================================================
# 5. FUNGSI BANTU
# ============================================================

def format_number(value):
    return f"{value:,.0f}".replace(",", ".")


def metric_card(title, value, help_text=None):

    with st.container(border=True):
        st.metric(
            label=title,
            value=value,
            help=help_text
        )


def safe_value_counts(series, name, limit=None):

    clean_series = (
        series
        .astype("string")
        .fillna("Tidak diketahui")
    )

    result = clean_series.value_counts()

    if limit is not None:
        result = result.head(limit)

    return (
        result
        .rename_axis(name)
        .reset_index(name="Jumlah")
    )


def chart_layout(fig, height=400):

    fig.update_layout(
        height=height,
        margin=dict(
            l=20,
            r=20,
            t=65,
            b=25
        ),
        font=dict(
            family="Arial",
            size=12,
            color="#334155"
        ),
        title=dict(
            font=dict(
                size=17,
                color="#1E293B"
            ),
            x=0.02
        ),
        legend_title_text="",
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            font_size=12,
            font_family="Arial"
        )
    )

    return fig


# ============================================================
# 6. FUNGSI HEADER HALAMAN
# ============================================================

def show_page_header(title, description):

    safe_title = html.escape(title)
    safe_description = html.escape(description)

    header_html = f"""
    <div style="
        background: linear-gradient(110deg, #173B70, #2563EB);
        padding: 28px 30px;
        border-radius: 15px;
        margin-bottom: 25px;
        width: 100%;
        box-sizing: border-box;
    ">

        <div style="
            color: #BFDBFE;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 1.5px;
            margin-bottom: 9px;
        ">
            HEALTHCARE ANALYTICS
        </div>

        <div style="
            color: #FFFFFF;
            font-size: 27px;
            font-weight: 750;
            margin-bottom: 9px;
        ">
            {safe_title}
        </div>

        <div style="
            color: #DBEAFE;
            font-size: 14px;
            line-height: 1.6;
        ">
            {safe_description}
        </div>

    </div>
    """

    # st.html merender HTML secara langsung, sehingga tidak dianggap
    # sebagai blok kode oleh parser Markdown.
    st.html(textwrap.dedent(header_html).strip())


def show_section_title(title, description=None):

    st.subheader(title)

    if description:
        st.caption(description)


# ============================================================
# 7. MEMUAT DATASET
# ============================================================

try:

    with st.spinner("Memuat dataset kesehatan..."):

        patients = load_data("patients")
        encounters = load_data("encounters")
        conditions = load_data("conditions")
        observations = load_data("observations")

except Exception as error:

    st.error("Terjadi kesalahan saat membaca dataset.")
    st.code(str(error))

    st.info(
        "Pastikan folder data berisi file CSV "
        "pada setiap dataset."
    )

    st.stop()


# ============================================================
# 8. VALIDASI DATASET
# ============================================================

required_tables = {
    "Pasien": patients,
    "Kunjungan": encounters,
    "Diagnosis": conditions,
    "Observasi": observations
}

missing_tables = [
    name
    for name, df in required_tables.items()
    if df.empty
]

if missing_tables:

    st.error(
        "Dataset kosong: " + ", ".join(missing_tables)
    )

    st.stop()


# ============================================================
# 9. KONVERSI TIPE DATA TANGGAL
# ============================================================

date_columns = [
    (patients, ["BIRTHDATE", "DEATHDATE"]),
    (encounters, ["START", "STOP"]),
    (conditions, ["START", "STOP"]),
    (observations, ["DATE"])
]

for df, columns in date_columns:

    for column in columns:

        if column in df.columns:

            df[column] = pd.to_datetime(
                df[column],
                errors="coerce"
            )


# ============================================================
# 10. SIDEBAR
# ============================================================

with st.sidebar:
    st.html("""
    <div style="padding: 5px 0 15px 0;">
        <div style="font-size: 25px; font-weight: 800; color: #173B70;">
            HEALTHCARE
        </div>
        <div style="font-size: 13px; color: #64748B; letter-spacing: 1px;">
            ANALYTICS DASHBOARD
        </div>
    </div>
    """)

st.sidebar.divider()

st.sidebar.markdown("**NAVIGASI UTAMA**")

page = st.sidebar.radio(
    "Pilih halaman",
    [
        "Ringkasan",
        "Data Pasien",
        "Kunjungan",
        "Diagnosis",
        "Observasi Kesehatan",
        "Kualitas Data",
        "Analisis Big Data 5Vs"
    ],
    label_visibility="collapsed"
)

st.sidebar.divider()

st.sidebar.markdown("**INFORMASI DATASET**")

st.sidebar.caption(
    "Synthea Synthetic Patient Records"
)

st.sidebar.markdown("**TEKNOLOGI**")

st.sidebar.caption(
    "PySpark · Python · Streamlit · Plotly"
)

st.sidebar.divider()

with st.sidebar:
    st.html("""
    <div style="background: #EFF6FF; padding: 13px; border-radius: 9px;
                color: #1E40AF; font-size: 12px; line-height: 1.6;">
        <b>PROYEK UTS BIG DATA</b><br>
        Analisis Data Rekam Medis Elektronik
    </div>
    """)


# ============================================================
# 11. HALAMAN RINGKASAN
# ============================================================

if page == "Ringkasan":

    show_page_header(
        "Ringkasan Data Kesehatan",
        "Gambaran umum data pasien, kunjungan, diagnosis, "
        "dan observasi kesehatan."
    )

    show_section_title(
        "Statistik Utama",
        "Jumlah record pada empat tabel utama dataset."
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card(
            "Jumlah Pasien",
            format_number(len(patients))
        )

    with col2:
        metric_card(
            "Jumlah Kunjungan",
            format_number(len(encounters))
        )

    with col3:
        metric_card(
            "Jumlah Diagnosis",
            format_number(len(conditions))
        )

    with col4:
        metric_card(
            "Jumlah Observasi",
            format_number(len(observations))
        )

    st.write("")

    show_section_title(
        "Visualisasi Data",
        "Perbandingan jumlah dan proporsi record dari setiap tabel."
    )

    summary = pd.DataFrame({
        "Dataset": [
            "Pasien",
            "Kunjungan",
            "Diagnosis",
            "Observasi"
        ],
        "Jumlah Data": [
            len(patients),
            len(encounters),
            len(conditions),
            len(observations)
        ]
    })

    col1, col2 = st.columns(2)

    with col1:

        fig = px.bar(
            summary,
            x="Dataset",
            y="Jumlah Data",
            color="Dataset",
            text="Jumlah Data",
            title="Perbandingan Jumlah Data"
        )

        fig.update_traces(
            texttemplate="%{text:,.0f}",
            textposition="outside"
        )

        st.plotly_chart(
            chart_layout(fig),
            use_container_width=True
        )

    with col2:

        fig = px.pie(
            summary,
            names="Dataset",
            values="Jumlah Data",
            title="Proporsi Data",
            hole=0.5
        )

        fig.update_traces(
            textposition="inside",
            textinfo="percent+label"
        )

        st.plotly_chart(
            chart_layout(fig),
            use_container_width=True
        )

    st.write("")

    show_section_title("Tentang Dataset")

    with st.container(border=True):

        st.markdown("**Synthea Synthetic Patient Records**")

        st.write(
            """
            Dataset ini berisi informasi pasien, riwayat kunjungan
            medis, diagnosis, dan hasil pengukuran kesehatan.

            Synthea menghasilkan data sintetis melalui simulasi,
            sehingga data yang digunakan bukan rekam medis pasien asli.
            """
        )

        st.info(
            "Jumlah record merupakan penjumlahan dari empat tabel, "
            "bukan jumlah pasien unik."
        )


# ============================================================
# 12. HALAMAN DATA PASIEN
# ============================================================

elif page == "Data Pasien":

    show_page_header(
        "Analisis Data Pasien",
        "Karakteristik demografi pasien berdasarkan informasi "
        "yang tersedia dalam dataset."
    )

    show_section_title(
        "Distribusi Demografi",
        "Persebaran pasien berdasarkan kategori demografi."
    )

    col1, col2 = st.columns(2)

    with col1:

        if "GENDER" in patients.columns:

            gender_data = safe_value_counts(
                patients["GENDER"],
                "Jenis Kelamin"
            )

            fig = px.pie(
                gender_data,
                names="Jenis Kelamin",
                values="Jumlah",
                title="Distribusi Jenis Kelamin",
                hole=0.48
            )

            fig.update_traces(
                textposition="inside",
                textinfo="percent+label"
            )

            st.plotly_chart(
                chart_layout(fig),
                use_container_width=True
            )

    with col2:

        if "RACE" in patients.columns:

            race_data = safe_value_counts(
                patients["RACE"],
                "Kelompok Ras"
            )

            fig = px.bar(
                race_data.sort_values("Jumlah"),
                x="Jumlah",
                y="Kelompok Ras",
                orientation="h",
                title="Distribusi Kelompok Ras",
                color_discrete_sequence=["#2563EB"]
            )

            st.plotly_chart(
                chart_layout(fig, height=420),
                use_container_width=True
            )

    st.write("")

    show_section_title(
        "Status Pernikahan",
        "Jumlah pasien berdasarkan status pernikahan."
    )

    if "MARITAL" in patients.columns:

        marital = safe_value_counts(
            patients["MARITAL"],
            "Status Pernikahan"
        )

        st.dataframe(
            marital,
            use_container_width=True,
            hide_index=True
        )

    st.caption(
        "Analisis ditampilkan dalam bentuk agregat, "
        "bukan identitas pribadi pasien."
    )


# ============================================================
# 13. HALAMAN KUNJUNGAN
# ============================================================

elif page == "Kunjungan":

    show_page_header(
        "Analisis Kunjungan Pasien",
        "Jenis pelayanan dan perubahan jumlah kunjungan "
        "pasien dari waktu ke waktu."
    )

    show_section_title(
        "Jenis Kunjungan",
        "Jumlah kunjungan berdasarkan kategori pelayanan."
    )

    if "ENCOUNTERCLASS" in encounters.columns:

        encounter_class = safe_value_counts(
            encounters["ENCOUNTERCLASS"],
            "Jenis Kunjungan"
        )

        fig = px.bar(
            encounter_class.sort_values("Jumlah"),
            x="Jenis Kunjungan",
            y="Jumlah",
            color="Jenis Kunjungan",
            text="Jumlah",
            title="Jumlah Kunjungan Berdasarkan Jenis"
        )

        fig.update_traces(
            textposition="outside"
        )

        st.plotly_chart(
            chart_layout(fig, height=430),
            use_container_width=True
        )

    st.write("")

    show_section_title(
        "Tren Kunjungan",
        "Perubahan jumlah kunjungan berdasarkan bulan."
    )

    if "START" in encounters.columns:

        monthly = (
            encounters
            .dropna(subset=["START"])
            .assign(
                Bulan=lambda x:
                x["START"].dt.to_period("M").astype(str)
            )
            .groupby("Bulan")
            .size()
            .reset_index(name="Jumlah Kunjungan")
        )

        monthly = monthly.sort_values("Bulan")

        fig = px.line(
            monthly,
            x="Bulan",
            y="Jumlah Kunjungan",
            markers=True,
            title="Tren Kunjungan Pasien per Bulan",
            color_discrete_sequence=["#2563EB"]
        )

        fig.update_traces(
            line=dict(width=3),
            marker=dict(size=7)
        )

        st.plotly_chart(
            chart_layout(fig, height=430),
            use_container_width=True
        )

    if "TOTAL_CLAIM_COST" in encounters.columns:

        claim_cost = pd.to_numeric(
            encounters["TOTAL_CLAIM_COST"],
            errors="coerce"
        )

        average_cost = claim_cost.mean()

        st.write("")

        show_section_title(
            "Informasi Biaya Klaim",
            "Rata-rata nilai pada kolom TOTAL_CLAIM_COST."
        )

        metric_card(
            "Rata-rata Total Biaya Klaim",
            (
                f"${average_cost:,.2f}"
                if pd.notna(average_cost)
                else "Tidak tersedia"
            )
        )


# ============================================================
# 14. HALAMAN DIAGNOSIS
# ============================================================

elif page == "Diagnosis":

    show_page_header(
        "Analisis Diagnosis",
        "Kondisi kesehatan yang paling sering tercatat "
        "dalam data rekam medis."
    )

    if "DESCRIPTION" in conditions.columns:

        top_conditions = safe_value_counts(
            conditions["DESCRIPTION"],
            "Nama Diagnosis",
            limit=15
        )

        show_section_title(
            "Diagnosis Terbanyak",
            "15 kondisi kesehatan dengan jumlah pencatatan tertinggi."
        )

        fig = px.bar(
            top_conditions.sort_values("Jumlah"),
            x="Jumlah",
            y="Nama Diagnosis",
            orientation="h",
            title="15 Diagnosis Paling Sering Tercatat",
            color_discrete_sequence=["#2563EB"]
        )

        st.plotly_chart(
            chart_layout(fig, height=580),
            use_container_width=True
        )

        st.write("")

        show_section_title(
            "Tabel Diagnosis",
            "Rincian jumlah pencatatan diagnosis."
        )

        st.dataframe(
            top_conditions,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.warning(
            "Kolom DESCRIPTION tidak ditemukan pada dataset diagnosis."
        )


# ============================================================
# 15. HALAMAN OBSERVASI KESEHATAN
# ============================================================

elif page == "Observasi Kesehatan":

    show_page_header(
        "Analisis Hasil Observasi Kesehatan",
        "Kategori dan jenis pengukuran kesehatan yang "
        "tercatat dalam dataset."
    )

    show_section_title(
        "Kategori Observasi",
        "Perbandingan kategori pengukuran kesehatan."
    )

    if "CATEGORY" in observations.columns:

        category_data = safe_value_counts(
            observations["CATEGORY"],
            "Kategori"
        )

        fig = px.pie(
            category_data,
            names="Kategori",
            values="Jumlah",
            title="Distribusi Kategori Observasi",
            hole=0.48
        )

        fig.update_traces(
            textposition="inside",
            textinfo="percent+label"
        )

        st.plotly_chart(
            chart_layout(fig),
            use_container_width=True
        )

    st.write("")

    show_section_title(
        "Jenis Observasi",
        "15 jenis pengukuran yang paling sering tercatat."
    )

    if "DESCRIPTION" in observations.columns:

        top_observations = safe_value_counts(
            observations["DESCRIPTION"],
            "Jenis Observasi",
            limit=15
        )

        fig = px.bar(
            top_observations.sort_values("Jumlah"),
            x="Jumlah",
            y="Jenis Observasi",
            orientation="h",
            title="15 Jenis Observasi Terbanyak",
            color_discrete_sequence=["#2563EB"]
        )

        st.plotly_chart(
            chart_layout(fig, height=580),
            use_container_width=True
        )

    if "VALUE" in observations.columns:

        numeric_values = pd.to_numeric(
            observations["VALUE"],
            errors="coerce"
        )

        st.write("")

        show_section_title(
            "Jenis Nilai Observasi",
            "Perbandingan nilai yang dapat dan tidak dapat dikonversi menjadi angka."
        )

        col1, col2 = st.columns(2)

        with col1:

            metric_card(
                "Observasi Numerik",
                format_number(
                    numeric_values.notna().sum()
                )
            )

        with col2:

            metric_card(
                "Observasi Non-Numerik",
                format_number(
                    numeric_values.isna().sum()
                )
            )

        st.caption(
            "Nilai yang tidak dapat dikonversi menjadi angka "
            "dikelompokkan sebagai non-numerik. Hal ini tidak "
            "selalu menunjukkan kesalahan data."
        )


# ============================================================
# 16. HALAMAN KUALITAS DATA
# ============================================================

elif page == "Kualitas Data":

    show_page_header(
        "Pemeriksaan Kualitas Data",
        "Pemeriksaan kelengkapan, nilai kosong, dan duplikasi "
        "pada dataset yang digunakan."
    )

    show_section_title(
        "Pilih Dataset",
        "Tentukan tabel yang ingin diperiksa."
    )

    selected_table = st.selectbox(
        "Dataset",
        list(required_tables.keys())
    )

    df = required_tables[selected_table]

    missing_values = df.isnull().sum()

    quality = pd.DataFrame({
        "Nama Kolom": df.columns,
        "Data Kosong": missing_values.values,
        "Persentase Kosong": (
            df.isnull().mean().values * 100
        ).round(2),
        "Nilai Unik": [
            df[col].nunique(dropna=True)
            for col in df.columns
        ]
    })

    duplicate_count = df.duplicated().sum()

    complete_cells = df.notnull().sum().sum()
    total_cells = df.size

    completeness = (
        complete_cells / total_cells * 100
        if total_cells > 0
        else 0
    )

    st.write("")

    col1, col2, col3 = st.columns(3)

    with col1:

        metric_card(
            "Jumlah Record",
            format_number(len(df))
        )

    with col2:

        metric_card(
            "Baris Duplikat",
            format_number(duplicate_count)
        )

    with col3:

        metric_card(
            "Kelengkapan Data",
            f"{completeness:.2f}%"
        )

    st.write("")

    show_section_title(
        "Kelengkapan Setiap Kolom",
        "Jumlah nilai kosong dan jumlah nilai unik pada setiap kolom."
    )

    st.dataframe(
        quality,
        use_container_width=True,
        hide_index=True
    )

    st.write("")

    show_section_title(
        "Persentase Data Kosong",
        "Persentase nilai kosong berdasarkan masing-masing kolom."
    )

    fig = px.bar(
        quality.sort_values(
            "Persentase Kosong",
            ascending=True
        ),
        x="Persentase Kosong",
        y="Nama Kolom",
        orientation="h",
        title="Persentase Data Kosong per Kolom",
        color_discrete_sequence=["#2563EB"]
    )

    fig.update_layout(
        xaxis_title="Persentase Data Kosong (%)",
        yaxis_title=""
    )

    st.plotly_chart(
        chart_layout(fig, height=500),
        use_container_width=True
    )

    st.info(
        "Data kosong tidak selalu berarti kesalahan. "
        "Contohnya, DEATHDATE yang kosong dapat menunjukkan "
        "bahwa informasi tanggal kematian tidak tersedia."
    )


# ============================================================
# 17. HALAMAN ANALISIS BIG DATA 5Vs
# ============================================================

elif page == "Analisis Big Data 5Vs":

    show_page_header(
        "Karakteristik Big Data (5Vs)",
        "Analisis karakteristik dataset kesehatan berdasarkan "
        "lima aspek utama dalam konsep Big Data."
    )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    st.subheader("01. Volume")

    st.caption(
        "Jumlah record yang dikelola pada empat tabel utama."
    )

    volume_data = pd.DataFrame({
        "Dataset": list(required_tables.keys()),
        "Jumlah Record": [
            len(df)
            for df in required_tables.values()
        ]
    })

    total_records = volume_data["Jumlah Record"].sum()

    metric_card(
        "Total Record Empat Tabel",
        format_number(total_records)
    )

    fig = px.bar(
        volume_data,
        x="Dataset",
        y="Jumlah Record",
        color="Dataset",
        text="Jumlah Record",
        title="Jumlah Data pada Setiap Tabel"
    )

    fig.update_traces(
        textposition="outside"
    )

    st.plotly_chart(
        chart_layout(fig),
        use_container_width=True
    )

    st.write(
        "Volume menunjukkan banyaknya data yang dikelola. "
        "Empat tabel utama memiliki ratusan ribu record "
        "dengan jenis informasi yang berbeda."
    )

    st.divider()

    # --------------------------------------------------------
    # VELOCITY
    # --------------------------------------------------------

    st.subheader("02. Velocity")

    st.caption(
        "Kecepatan pembentukan, pengiriman, dan pemrosesan data."
    )

    with st.container(border=True):

        st.markdown("**Karakteristik kecepatan data**")

        st.write(
            """
            Dataset Synthea yang digunakan merupakan data historis
            statis. Dashboard ini tidak menerima data secara real-time.

            Pengukuran ingestion rate dan processing latency
            dilakukan pada proses pipeline di notebook PySpark.
            """
        )

        st.info(
            "Kecepatan pemrosesan dapat dianalisis melalui waktu "
            "eksekusi setiap tahapan pengolahan data."
        )

    st.divider()

    # --------------------------------------------------------
    # VARIETY
    # --------------------------------------------------------

    st.subheader("03. Variety")

    st.caption(
        "Variasi struktur dan format data yang digunakan."
    )

    variety_data = pd.DataFrame({
        "Dataset": [
            "Pasien",
            "Kunjungan",
            "Diagnosis",
            "Observasi"
        ],
        "Jumlah Kolom": [
            len(patients.columns),
            len(encounters.columns),
            len(conditions.columns),
            len(observations.columns)
        ]
    })

    col1, col2 = st.columns(2)

    with col1:

        st.dataframe(
            variety_data,
            use_container_width=True,
            hide_index=True
        )

    with col2:

        fig = px.bar(
            variety_data,
            x="Dataset",
            y="Jumlah Kolom",
            color="Dataset",
            title="Jumlah Atribut per Tabel"
        )

        st.plotly_chart(
            chart_layout(fig, height=350),
            use_container_width=True
        )

    st.write(
        "Setiap tabel memiliki atribut yang berbeda. "
        "Data CSV digunakan sebagai sumber utama analisis, "
        "sedangkan FHIR JSON menjadi format tambahan "
        "yang dapat diintegrasikan dalam pipeline."
    )

    st.divider()

    # --------------------------------------------------------
    # VERACITY
    # --------------------------------------------------------

    st.subheader("04. Veracity")

    st.caption(
        "Kualitas dan kelengkapan data."
    )

    missing_total = sum(
        int(df.isnull().sum().sum())
        for df in required_tables.values()
    )

    records_total = sum(
        len(df) * len(df.columns)
        for df in required_tables.values()
    )

    missing_percentage = (
        missing_total / records_total * 100
        if records_total > 0
        else 0
    )

    complete_percentage = 100 - missing_percentage

    col1, col2 = st.columns(2)

    with col1:

        metric_card(
            "Total Data Kosong",
            format_number(missing_total)
        )

    with col2:

        metric_card(
            "Persentase Data Kosong",
            f"{missing_percentage:.2f}%"
        )

    veracity_data = pd.DataFrame({
        "Status": ["Terisi", "Kosong"],
        "Persentase": [
            complete_percentage,
            missing_percentage
        ]
    })

    fig = px.pie(
        veracity_data,
        names="Status",
        values="Persentase",
        hole=0.5,
        title="Kelengkapan Seluruh Data"
    )

    st.plotly_chart(
        chart_layout(fig, height=350),
        use_container_width=True
    )

    st.write(
        "Veracity berkaitan dengan kualitas dan tingkat "
        "kepercayaan data. Pemeriksaan dilakukan dengan "
        "melihat nilai kosong pada setiap tabel."
    )

    st.divider()

    # --------------------------------------------------------
    # VALUE
    # --------------------------------------------------------

    st.subheader("05. Value")

    st.caption(
        "Nilai informasi yang dapat diperoleh dari data."
    )

    if "DESCRIPTION" in conditions.columns:

        value_data = safe_value_counts(
            conditions["DESCRIPTION"],
            "Nama Diagnosis",
            limit=10
        )

        fig = px.bar(
            value_data.sort_values("Jumlah"),
            x="Jumlah",
            y="Nama Diagnosis",
            orientation="h",
            title="10 Diagnosis Paling Sering Tercatat",
            color_discrete_sequence=["#2563EB"]
        )

        st.plotly_chart(
            chart_layout(fig, height=450),
            use_container_width=True
        )

        st.write(
            """
            Data diagnosis dapat memberikan gambaran mengenai
            kondisi kesehatan yang sering tercatat.

            Hasil analisis ini bersifat deskriptif dan bukan
            sebagai dasar diagnosis klinis.
            """
        )


# ============================================================
# 18. FOOTER
# ============================================================

st.divider()

st.html("""
<div style="text-align: center; padding: 12px 0; color: #8492A6;
            font-size: 12px; line-height: 1.8;">
    <b>Healthcare Analytics Dashboard</b><br>
    Proyek UTS Big Data · Synthea Synthetic Patient Records
</div>
""")
