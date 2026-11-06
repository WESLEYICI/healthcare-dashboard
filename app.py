
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
    page_title="Dashboard Data Kesehatan",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATA_PATH = "data"

# Kolom yang benar-benar diperlukan oleh dashboard.
# Ini mengurangi penggunaan RAM saat membaca CSV.

DATA_COLUMNS = {
    "patients": [
        "ID",
        "BIRTHDATE",
        "DEATHDATE",
        "GENDER",
        "RACE",
        "MARITAL"
    ],

    "encounters": [
        "ID",
        "PATIENT",
        "START",
        "STOP",
        "ENCOUNTERCLASS",
        "TOTAL_CLAIM_COST"
    ],

    "conditions": [
        "ID",
        "PATIENT",
        "ENCOUNTER",
        "START",
        "STOP",
        "DESCRIPTION"
    ],

    "observations": [
        "ID",
        "PATIENT",
        "ENCOUNTER",
        "DATE",
        "CATEGORY",
        "DESCRIPTION",
        "VALUE"
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
    "#64748B"
]


# ============================================================
# 3. CSS DASHBOARD
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background-color: #F8FAFC;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1450px;
    }

    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }

    [data-testid="stSidebar"] h1 {
        color: #1E3A8A;
        font-size: 22px;
    }

    h1, h2, h3 {
        color: #1E293B;
        font-weight: 650;
    }

    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px;
    }

    [data-testid="stMetricLabel"] {
        color: #64748B;
        font-size: 14px;
    }

    [data-testid="stMetricValue"] {
        color: #1D4ED8;
        font-size: 27px;
        font-weight: 650;
    }

    [data-testid="stDataFrame"] {
        background-color: #FFFFFF;
        border-radius: 8px;
    }

    hr {
        border-color: #E2E8F0;
    }

    .stCaption {
        color: #64748B;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# 4. FUNGSI MEMUAT DATASET
# ============================================================

@st.cache_resource(show_spinner=False)
def load_data(table_name):

    folder = os.path.join(DATA_PATH, table_name)

    # Mencari file hasil ekspor PySpark
    files = sorted(
        glob.glob(os.path.join(folder, "part-*.csv"))
    )

    # Alternatif jika nama file bukan part-*.csv
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

            # Membaca header terlebih dahulu
            available_columns = pd.read_csv(
                file,
                nrows=0
            ).columns.tolist()

            # Memilih kolom yang tersedia dan dibutuhkan
            selected_columns = [
                column
                for column in required_columns
                if column in available_columns
            ]

            if not selected_columns:
                raise ValueError(
                    f"Tidak ada kolom yang sesuai pada file {file}"
                )

            # Membaca hanya kolom yang dibutuhkan
            part = pd.read_csv(
                file,
                usecols=selected_columns,
                low_memory=True,
                on_bad_lines="error"
            )

            data_parts.append(part)

            del part
            gc.collect()

        except Exception as error:

            raise RuntimeError(
                f"Gagal membaca file {file}: {error}"
            ) from error

    # Menggabungkan file jika dataset terdiri dari beberapa bagian
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
# 5. MEMUAT SELURUH DATASET
# ============================================================

st.title("Dashboard Data Kesehatan")

st.caption(
    "Analisis data rekam medis elektronik menggunakan pendekatan Big Data."
)

try:

    with st.spinner("Sedang memuat dataset kesehatan..."):

        patients = load_data("patients")

        encounters = load_data("encounters")

        conditions = load_data("conditions")

        observations = load_data("observations")

except Exception as error:

    st.error("Terjadi kesalahan saat membaca dataset.")

    st.code(str(error))

    st.info(
        "Pastikan folder data berisi file CSV pada setiap dataset "
        "dan ukuran file sesuai dengan kapasitas memori aplikasi."
    )

    st.stop()


# ============================================================
# 6. VALIDASI DATASET
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
        "Dataset kosong atau tidak ditemukan: "
        + ", ".join(missing_tables)
    )

    st.stop()


# ============================================================
# 7. KONVERSI TIPE DATA TANGGAL
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
# 8. FUNGSI BANTU
# ============================================================

def format_number(value):

    return f"{value:,.0f}".replace(",", ".")


def metric_card(title, value, help_text=None):

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
            t=60,
            b=20
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
            )
        ),

        legend_title_text="",

        plot_bgcolor="white",

        paper_bgcolor="white"
    )

    return fig


def show_page_header(title, description):

    st.title(title)

    st.write(description)

    st.divider()


# ============================================================
# 9. SIDEBAR NAVIGASI
# ============================================================

st.sidebar.title("Healthcare Analytics")

st.sidebar.caption(
    "Dashboard Analisis Data Kesehatan"
)

st.sidebar.divider()

page = st.sidebar.radio(
    "Menu Dashboard",
    [
        "Ringkasan",
        "Data Pasien",
        "Kunjungan",
        "Diagnosis",
        "Observasi Kesehatan",
        "Kualitas Data",
        "Analisis Big Data 5Vs"
    ]
)

st.sidebar.divider()

st.sidebar.caption("SUMBER DATA")

st.sidebar.write(
    "Synthea Synthetic Patient Records"
)

st.sidebar.caption("TEKNOLOGI")

st.sidebar.write(
    "PySpark, Python, Streamlit, dan Plotly"
)

st.sidebar.divider()

st.sidebar.caption(
    "Proyek UTS Big Data"
)


# ============================================================
# 10. HALAMAN RINGKASAN
# ============================================================

if page == "Ringkasan":

    show_page_header(
        "Ringkasan Data Kesehatan",

        "Gambaran umum data pasien, kunjungan, diagnosis, "
        "dan hasil observasi kesehatan."
    )

    # Statistik utama

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

    st.subheader("Jumlah Data pada Setiap Tabel")

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

        st.caption(
            "Jumlah record yang tersimpan pada setiap tabel."
        )

    with col2:

        fig = px.pie(
            summary,
            names="Dataset",
            values="Jumlah Data",
            title="Persentase Data",
            hole=0.45
        )

        st.plotly_chart(
            chart_layout(fig),
            use_container_width=True
        )

        st.caption(
            "Perbandingan proporsi record dari empat tabel utama."
        )

    st.subheader("Tentang Dataset")

    st.write(
        """
        Dataset berasal dari Synthea Synthetic Patient Records.
        Data ini berisi informasi pasien, riwayat kunjungan medis,
        diagnosis, dan hasil pengukuran kesehatan.

        Synthea menghasilkan data sintetis melalui simulasi,
        sehingga data yang digunakan bukan rekam medis pasien asli.
        """
    )

    st.info(
        "Jumlah record merupakan penjumlahan dari empat tabel, "
        "bukan jumlah pasien unik."
    )


# ============================================================
# 11. HALAMAN DATA PASIEN
# ============================================================

elif page == "Data Pasien":

    show_page_header(
        "Analisis Data Pasien",

        "Karakteristik demografi pasien berdasarkan informasi "
        "yang tersedia dalam dataset."
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
                hole=0.4
            )

            st.plotly_chart(
                chart_layout(fig),
                use_container_width=True
            )

            st.caption(
                "Jumlah pasien berdasarkan kategori jenis kelamin."
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
                title="Distribusi Kelompok Ras"
            )

            st.plotly_chart(
                chart_layout(fig),
                use_container_width=True
            )

            st.caption(
                "Persebaran pasien berdasarkan kategori ras."
            )

    st.subheader("Status Pernikahan")

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
# 12. HALAMAN KUNJUNGAN
# ============================================================

elif page == "Kunjungan":

    show_page_header(
        "Analisis Kunjungan Pasien",

        "Jenis pelayanan dan perubahan jumlah kunjungan "
        "pasien dari waktu ke waktu."
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
            chart_layout(fig),
            use_container_width=True
        )

        st.caption(
            "Jumlah kunjungan untuk setiap jenis pelayanan kesehatan."
        )

    st.divider()

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
            title="Tren Kunjungan Pasien per Bulan"
        )

        fig.update_traces(
            line=dict(width=3),
            marker=dict(size=7)
        )

        st.plotly_chart(
            chart_layout(fig),
            use_container_width=True
        )

        st.caption(
            "Perubahan jumlah kunjungan berdasarkan bulan "
            "pada periode yang tersedia."
        )

    if "TOTAL_CLAIM_COST" in encounters.columns:

        claim_cost = pd.to_numeric(
            encounters["TOTAL_CLAIM_COST"],
            errors="coerce"
        )

        average_cost = claim_cost.mean()

        st.subheader("Rata-rata Biaya Klaim")

        metric_card(
            "Rata-rata Total Biaya Klaim",
            (
                f"${average_cost:,.2f}"
                if pd.notna(average_cost)
                else "Tidak tersedia"
            )
        )

        st.caption(
            "Perhitungan berdasarkan kolom TOTAL_CLAIM_COST."
        )


# ============================================================
# 13. HALAMAN DIAGNOSIS
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

        fig = px.bar(
            top_conditions.sort_values("Jumlah"),
            x="Jumlah",
            y="Nama Diagnosis",
            orientation="h",
            title="15 Diagnosis Paling Sering Tercatat"
        )

        st.plotly_chart(
            chart_layout(fig, height=550),
            use_container_width=True
        )

        st.caption(
            "Menampilkan 15 kondisi kesehatan dengan "
            "jumlah pencatatan terbanyak."
        )

        st.subheader("Tabel Diagnosis")

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
# 14. HALAMAN OBSERVASI KESEHATAN
# ============================================================

elif page == "Observasi Kesehatan":

    show_page_header(
        "Analisis Hasil Observasi Kesehatan",

        "Kategori dan jenis pengukuran kesehatan yang "
        "tercatat dalam dataset."
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
            hole=0.4
        )

        st.plotly_chart(
            chart_layout(fig),
            use_container_width=True
        )

        st.caption(
            "Pembagian observasi berdasarkan kategori pengukuran."
        )

    st.divider()

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
            title="15 Jenis Observasi Terbanyak"
        )

        st.plotly_chart(
            chart_layout(fig, height=550),
            use_container_width=True
        )

        st.caption(
            "Jenis pengukuran kesehatan yang paling banyak tercatat."
        )

    if "VALUE" in observations.columns:

        numeric_values = pd.to_numeric(
            observations["VALUE"],
            errors="coerce"
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
# 15. HALAMAN KUALITAS DATA
# ============================================================

elif page == "Kualitas Data":

    show_page_header(
        "Pemeriksaan Kualitas Data",

        "Pemeriksaan kelengkapan, nilai kosong, dan duplikasi "
        "pada dataset yang digunakan."
    )

    selected_table = st.selectbox(
        "Pilih Dataset",
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

    col1, col2, col3 = st.columns(3)

    with col1:

        metric_card(
            "Jumlah Record",
            format_number(len(df))
        )

    with col2:

        metric_card(
            "Jumlah Kolom",
            format_number(len(df.columns))
        )

    with col3:

        metric_card(
            "Baris Duplikat",
            format_number(df.duplicated().sum())
        )

    st.subheader("Kelengkapan Setiap Kolom")

    st.dataframe(
        quality,
        use_container_width=True,
        hide_index=True
    )

    st.subheader("Persentase Data Kosong")

    fig = px.bar(
        quality.sort_values(
            "Persentase Kosong",
            ascending=True
        ),
        x="Persentase Kosong",
        y="Nama Kolom",
        orientation="h",
        title="Persentase Data Kosong per Kolom"
    )

    st.plotly_chart(
        chart_layout(fig, height=550),
        use_container_width=True
    )

    st.info(
        "Data kosong tidak selalu berarti kesalahan. "
        "Contohnya, DEATHDATE yang kosong dapat menunjukkan "
        "bahwa informasi tanggal kematian tidak tersedia."
    )


# ============================================================
# 16. HALAMAN ANALISIS BIG DATA 5Vs
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

    st.subheader("1. Volume (Jumlah Data)")

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
        title="Jumlah Data pada Setiap Tabel"
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

    st.subheader("2. Velocity (Kecepatan Data)")

    st.info(
        "Dataset Synthea yang digunakan merupakan data historis "
        "statis. Dashboard ini belum menerima data secara real-time. "
        "Pengukuran ingestion rate dan processing latency dilakukan "
        "pada proses pipeline di notebook PySpark."
    )

    st.divider()

    # --------------------------------------------------------
    # VARIETY
    # --------------------------------------------------------

    st.subheader("3. Variety (Variasi Data)")

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

    st.dataframe(
        variety_data,
        use_container_width=True,
        hide_index=True
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

    st.subheader("4. Veracity (Kualitas Data)")

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
            "Total Data Kosong",
            format_number(missing_total)
        )

    with col2:

        metric_card(
            "Persentase Data Kosong",
            f"{missing_percentage:.2f}%"
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

    st.subheader("5. Value (Nilai Informasi)")

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
            title="10 Diagnosis Paling Sering Tercatat"
        )

        st.plotly_chart(
            chart_layout(fig, height=450),
            use_container_width=True
        )

        st.write(
            "Data diagnosis dapat memberikan gambaran mengenai "
            "kondisi kesehatan yang sering tercatat. Hasil analisis "
            "ini bersifat deskriptif dan bukan sebagai dasar "
            "diagnosis klinis."
        )


# ============================================================
# 17. FOOTER
# ============================================================

st.divider()

st.caption(
    "Dashboard Data Kesehatan | "
    "Proyek UTS Big Data | "
    "Synthea Synthetic Patient Records"
)
