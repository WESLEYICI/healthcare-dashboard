import pandas as pd
import glob
import os

DATA_PATH = "data"

tables = [
    "patients",
    "encounters",
    "conditions",
    "observations"
]

for table in tables:
    folder = os.path.join(DATA_PATH, table)

    files = glob.glob(
        os.path.join(folder, "*.csv")
    )

    if not files:
        print(f"{table}: FILE CSV TIDAK DITEMUKAN")
        continue

    df = pd.concat(
        [pd.read_csv(file) for file in files],
        ignore_index=True
    )

    print(f"\n{table.upper()}")
    print("Jumlah baris:", len(df))
    print("Jumlah kolom:", len(df.columns))
    print("Kolom:", list(df.columns))