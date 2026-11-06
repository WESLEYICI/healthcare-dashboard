import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os
import gc

# ============================================================
# 1. KONFIGURASI DASHBOARD
# ============================================================

st.set_page_config(
    page_title="Healthcare Data Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATA_PATH = "data"
CHUNK_SIZE = 10000


# ============================================================
# 2. FUNGSI LOAD DATA HEMAT MEMORI
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

    chunks = []

    for file in files:

        try:
            for chunk in pd.read_csv(
                file,
                chunksize=CHUNK_SIZE,
                low_memory=True,
                on_bad_lines="error"
            ):
                chunks.append(chunk)

        except Exception as error:
            raise RuntimeError(
                f"Gagal membaca file {file}: {error}"
            ) from error

    if not chunks:
        return pd.DataFrame()

    data = pd.concat(
        chunks,
        ignore_index=True,
        copy=False
    )

    del chunks
    gc.collect()

    # Optimasi kolom teks dengan jumlah kategori rendah
    for column in data.select_dtypes(include=["object"]).columns:

        unique_count = data[column].nunique(dropna=True)
        total_count = len(data)

        if total_count > 0 and unique_count <= total_count * 0.5:
            data[column] = data[column].astype("category")

    return data


# ============================================================
# 3. MEMUAT DATASET
# ============================================================

st.title("🏥 Healthcare Data Analytics")

try:

    with st.spinner("Memuat dataset healthcare..."):

        patients = load_data("patients")
        encounters = load_data("encounters")
        conditions = load_data("conditions")
        observations = load_data("observations")

except Exception as error:

    st.error("Terjadi kesalahan saat membaca dataset.")
    st.code(str(error))

    st.info(
        "Periksa folder data dan pastikan seluruh file CSV "
        "hasil ekspor dari Colab tersedia."
    )

    st.stop()


# ============================================================
# 4. VALIDASI DATA
# ============================================================

required_tables = {
    "Patients": patients,
    "Encounters": encounters,
    "Conditions": conditions,
    "Observations": observations
}

missing_tables = [
    name
    for name, df in required_tables.items()
    if df.empty
]

if missing_tables:

    st.error(
        "Dataset kosong atau tidak ditemukan: "
        + ", ".join(missing_tables)
    )

    st.stop()


# ============================================================
# 5. KONVERSI TIPE DATA TANGGAL
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
# 6. HELPER FUNCTIONS
# ============================================================

def metric_card(title, value, help_text=None):

    st.metric(
        label=title,
        value=value,
        help=help_text
    )


def format_number(value):

    return f"{value:,.0f}".replace(",", ".")


def safe_value_counts(series, name, limit=None):

    # Perbaikan: ubah category menjadi string sebelum fillna
    clean_series = (
        series
        .astype("string")
        .fillna("Unknown")
    )

    result = clean_series.value_counts()

    if limit is not None:
        result = result.head(limit)

    return (
        result
        .rename_axis(name)
        .reset_index(name="Total")
    )


# ============================================================
# 7. SIDEBAR NAVIGASI
# ============================================================

st.sidebar.title("🏥 Healthcare Analytics")

st.sidebar.caption(
    "Big Data Project | Synthea Dataset"
)

page = st.sidebar.radio(
    "Navigasi Dashboard",
    [
        "Overview",
        "Patient Analytics",
        "Encounter Analytics",
        "Diagnosis Analytics",
        "Observation Analytics",
        "Data Quality",
        "Big Data 5Vs"
    ]
)

st.sidebar.divider()

st.sidebar.caption("Data Source: Synthea Synthetic Dataset")
st.sidebar.caption("Processing: PySpark + Python")
st.sidebar.caption("Visualization: Streamlit + Plotly")


# ============================================================
# 8. OVERVIEW
# ============================================================

if page == "Overview":

    st.title("Healthcare Data Analytics Dashboard")

    st.write(
        "Visualisasi dan analisis data rekam medis elektronik "
        "menggunakan pendekatan Big Data."
    )

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card(
            "Total Patients",
            format_number(len(patients))
        )

    with col2:
        metric_card(
            "Total Encounters",
            format_number(len(encounters))
        )

    with col3:
        metric_card(
            "Total Conditions",
            format_number(len(conditions))
        )

    with col4:
        metric_card(
            "Total Observations",
            format_number(len(observations))
        )

    st.subheader("Ringkasan Dataset")

    summary = pd.DataFrame({
        "Dataset": [
            "Patients",
            "Encounters",
            "Conditions",
            "Observations"
        ],
        "Total Records": [
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
            y="Total Records",
            color="Dataset",
            title="Jumlah Record Setiap Dataset",
            text_auto=".2s"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with col2:

        fig = px.pie(
            summary,
            names="Dataset",
            values="Total Records",
            title="Distribusi Record Dataset",
            hole=0.45
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    st.subheader("Informasi Dataset")

    st.write("""
    Dataset menggunakan Synthea Synthetic Patient Records,
    yaitu data rekam medis sintetis yang mencakup informasi pasien,
    kunjungan medis, diagnosis, dan hasil observasi kesehatan.

    Data yang digunakan merupakan data sintetis, bukan data pasien asli.
    """)


# ============================================================
# 9. PATIENT ANALYTICS
# ============================================================

elif page == "Patient Analytics":

    st.title("Patient Analytics")

    st.write(
        "Analisis karakteristik demografi pasien."
    )

    col1, col2 = st.columns(2)

    with col1:

        if "GENDER" in patients.columns:

            gender_data = safe_value_counts(
                patients["GENDER"],
                "Gender"
            )

            fig = px.pie(
                gender_data,
                names="Gender",
                values="Total",
                title="Distribusi Gender Pasien",
                hole=0.4
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

    with col2:

        if "RACE" in patients.columns:

            race_data = safe_value_counts(
                patients["RACE"],
                "Race"
            )

            fig = px.bar(
                race_data,
                x="Total",
                y="Race",
                orientation="h",
                title="Distribusi Race Pasien"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

    st.subheader("Ringkasan Pasien")

    if "MARITAL" in patients.columns:

        marital = safe_value_counts(
            patients["MARITAL"],
            "Status"
        )

        marital.columns = [
            "Status",
            "Jumlah Pasien"
        ]

        st.dataframe(
            marital,
            use_container_width=True,
            hide_index=True
        )

    st.caption(
        "Dashboard hanya menampilkan data agregat, "
        "bukan identitas pribadi pasien."
    )


# ============================================================
# 10. ENCOUNTER ANALYTICS
# ============================================================

elif page == "Encounter Analytics":

    st.title("Encounter Analytics")

    st.write(
        "Analisis aktivitas kunjungan dan pelayanan kesehatan."
    )

    if "ENCOUNTERCLASS" in encounters.columns:

        encounter_class = safe_value_counts(
            encounters["ENCOUNTERCLASS"],
            "Encounter Class"
        )

        fig = px.bar(
            encounter_class,
            x="Encounter Class",
            y="Total",
            color="Encounter Class",
            title="Distribusi Jenis Kunjungan",
            text_auto=True
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    if "START" in encounters.columns:

        monthly = (
            encounters
            .dropna(subset=["START"])
            .assign(
                Month=lambda x:
                x["START"].dt.to_period("M").astype(str)
            )
            .groupby("Month")
            .size()
            .reset_index(name="Total Visits")
        )

        monthly = monthly.sort_values("Month")

        fig = px.line(
            monthly,
            x="Month",
            y="Total Visits",
            markers=True,
            title="Tren Kunjungan Berdasarkan Bulan"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    if "TOTAL_CLAIM_COST" in encounters.columns:

        claim_cost = pd.to_numeric(
            encounters["TOTAL_CLAIM_COST"],
            errors="coerce"
        )

        average_cost = claim_cost.mean()

        st.metric(
            "Rata-rata Total Claim Cost",
            (
                f"${average_cost:,.2f}"
                if pd.notna(average_cost)
                else "N/A"
            )
        )


# ============================================================
# 11. DIAGNOSIS ANALYTICS
# ============================================================

elif page == "Diagnosis Analytics":

    st.title("Diagnosis Analytics")

    st.write(
        "Analisis distribusi kondisi dan diagnosis pasien."
    )

    if "DESCRIPTION" in conditions.columns:

        top_conditions = safe_value_counts(
            conditions["DESCRIPTION"],
            "Diagnosis",
            limit=15
        )

        fig = px.bar(
            top_conditions.sort_values("Total"),
            x="Total",
            y="Diagnosis",
            orientation="h",
            title="15 Diagnosis Paling Sering Ditemukan"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        st.subheader("Data Diagnosis")

        st.dataframe(
            top_conditions,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# 12. OBSERVATION ANALYTICS
# ============================================================

elif page == "Observation Analytics":

    st.title("Observation Analytics")

    st.write(
        "Analisis hasil pengukuran dan observasi kesehatan."
    )

    if "CATEGORY" in observations.columns:

        category_data = safe_value_counts(
            observations["CATEGORY"],
            "Category"
        )

        fig = px.pie(
            category_data,
            names="Category",
            values="Total",
            title="Distribusi Kategori Observasi",
            hole=0.4
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    if "DESCRIPTION" in observations.columns:

        top_observations = safe_value_counts(
            observations["DESCRIPTION"],
            "Observation",
            limit=15
        )

        fig = px.bar(
            top_observations.sort_values("Total"),
            x="Total",
            y="Observation",
            orientation="h",
            title="15 Jenis Observasi Terbanyak"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    if "VALUE" in observations.columns:

        numeric_values = pd.to_numeric(
            observations["VALUE"].astype("string"),
            errors="coerce"
        )

        col1, col2 = st.columns(2)

        with col1:

            metric_card(
                "Total Observasi Numerik",
                format_number(
                    numeric_values.notna().sum()
                )
            )

        with col2:

            metric_card(
                "Total Observasi Non-Numerik",
                format_number(
                    numeric_values.isna().sum()
                )
            )

        st.caption(
            "Nilai yang tidak dapat dikonversi menjadi angka "
            "dikelompokkan sebagai non-numerik. "
            "Hal ini tidak otomatis berarti data salah."
        )


# ============================================================
# 13. DATA QUALITY
# ============================================================

elif page == "Data Quality":

    st.title("Data Quality Analysis")

    st.write(
        "Pemeriksaan kelengkapan dan konsistensi data."
    )

    selected_table = st.selectbox(
        "Pilih Dataset",
        list(required_tables.keys())
    )

    df = required_tables[selected_table]

    missing_values = df.isnull().sum()

    quality = pd.DataFrame({
        "Column": df.columns,
        "Missing Values": missing_values.values,
        "Missing (%)": (
            df.isnull().mean().values * 100
        ).round(2),
        "Unique Values": [
            df[col].nunique(dropna=True)
            for col in df.columns
        ]
    })

    st.subheader("Kelengkapan Data")

    st.dataframe(
        quality,
        use_container_width=True,
        hide_index=True
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        metric_card(
            "Total Records",
            format_number(len(df))
        )

    with col2:

        metric_card(
            "Total Columns",
            format_number(len(df.columns))
        )

    with col3:

        metric_card(
            "Duplicate Rows",
            format_number(df.duplicated().sum())
        )

    fig = px.bar(
        quality.sort_values(
            "Missing (%)",
            ascending=False
        ),
        x="Missing (%)",
        y="Column",
        orientation="h",
        title="Persentase Missing Values per Kolom"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.info(
        "Nilai kosong perlu ditafsirkan berdasarkan konteks. "
        "Contohnya, DEATHDATE yang kosong dapat berarti pasien masih hidup."
    )


# ============================================================
# 14. BIG DATA 5Vs
# ============================================================

elif page == "Big Data 5Vs":

    st.title("Big Data 5Vs Analysis")

    st.write(
        "Evaluasi karakteristik Big Data pada dataset kesehatan."
    )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    st.subheader("1. Volume")

    volume_data = pd.DataFrame({
        "Dataset": list(required_tables.keys()),
        "Records": [
            len(df)
            for df in required_tables.values()
        ]
    })

    total_records = volume_data["Records"].sum()

    st.metric(
        "Total Records Empat Tabel",
        format_number(total_records)
    )

    fig = px.bar(
        volume_data,
        x="Dataset",
        y="Records",
        color="Dataset",
        title="Volume Data per Tabel",
        text_auto=True
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.write(
        "Volume menunjukkan jumlah dan skala data yang diproses. "
        "Empat tabel utama memiliki lebih dari 600 ribu record "
        "dengan struktur dan hubungan data yang berbeda."
    )

    # --------------------------------------------------------
    # VELOCITY
    # --------------------------------------------------------

    st.subheader("2. Velocity")

    st.info(
        "Dataset Synthea yang digunakan merupakan data historis statis. "
        "Dashboard ini belum mengukur kecepatan kedatangan data secara "
        "real-time. Pengukuran ingestion rate dan processing latency "
        "dilakukan pada proses pipeline di notebook PySpark."
    )

    # --------------------------------------------------------
    # VARIETY
    # --------------------------------------------------------

    st.subheader("3. Variety")

    variety_data = pd.DataFrame({
        "Dataset": [
            "Patients",
            "Encounters",
            "Conditions",
            "Observations"
        ],
        "Columns": [
            len(patients.columns),
            len(encounters.columns),
            len(conditions.columns),
            len(observations.columns)
        ]
    })

    st.dataframe(
        variety_data,
        use_container_width=True,
        hide_index=True
    )

    st.write(
        "Data CSV memiliki variasi atribut dan relasi antar tabel. "
        "Dataset FHIR JSON menjadi representasi tambahan yang "
        "dapat diintegrasikan dalam pipeline."
    )

    # --------------------------------------------------------
    # VERACITY
    # --------------------------------------------------------

    st.subheader("4. Veracity")

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
        if records_total
        else 0
    )

    col1, col2 = st.columns(2)

    with col1:

        metric_card(
            "Total Missing Values",
            format_number(missing_total)
        )

    with col2:

        metric_card(
            "Missing Value Percentage",
            f"{missing_percentage:.2f}%"
        )

    st.write(
        "Veracity berkaitan dengan kualitas dan kepercayaan data. "
        "Nilai kosong perlu diperiksa berdasarkan konteks atribut "
        "dan tidak selalu dianggap sebagai kesalahan."
    )

    # --------------------------------------------------------
    # VALUE
    # --------------------------------------------------------

    st.subheader("5. Value")

    if "DESCRIPTION" in conditions.columns:

        value_data = safe_value_counts(
            conditions["DESCRIPTION"],
            "Diagnosis",
            limit=10
        )

        fig = px.bar(
            value_data.sort_values("Total"),
            x="Total",
            y="Diagnosis",
            orientation="h",
            title="10 Diagnosis Terbanyak"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        st.write(
            "Informasi diagnosis dapat membantu memahami pola "
            "kondisi kesehatan yang tercatat dalam dataset. "
            "Hasil ini bersifat deskriptif dan tidak digunakan "
            "sebagai diagnosis klinis."
        )


# ============================================================
# 15. FOOTER
# ============================================================

st.divider()

st.caption(
    "Healthcare Data Analytics Dashboard | "
    "Big Data Project | Synthea Synthetic Dataset"
)
