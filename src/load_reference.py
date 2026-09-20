"""Load WHO reference lists into DuckDB."""

from pathlib import Path

import pandas as pd

from src.db import PROJECT_ROOT, connect, create_tables

CANDIDATE_DATA = PROJECT_ROOT / "candidate_data"
CONFIG = PROJECT_ROOT / "config"


def _replace_from_csv(con, table_name, csv_path: Path):
    df = pd.read_csv(csv_path)
    df = df.where(pd.notnull(df), None)
    con.execute(f"DELETE FROM {table_name}")
    con.register("_load_tmp", df)
    con.execute(f"INSERT INTO {table_name} SELECT * FROM _load_tmp")
    con.unregister("_load_tmp")
    return len(df)


def _insert_dataframe(con, table_name, df: pd.DataFrame):
    df = df.where(pd.notnull(df), None)
    con.execute(f"DELETE FROM {table_name}")
    con.register("_load_tmp", df)
    con.execute(f"INSERT INTO {table_name} SELECT * FROM _load_tmp")
    con.unregister("_load_tmp")
    return len(df)


def load_who_reference_lists():
    create_tables()
    con = connect()
    counts = {
        "ref_country": _replace_from_csv(
            con, "ref_country", CANDIDATE_DATA / "ref_countries.csv"
        ),
        "ref_sha": _replace_from_csv(
            con, "ref_sha", CANDIDATE_DATA / "ref_sha_classification.csv"
        ),
        "ref_srhr": _replace_from_csv(
            con, "ref_srhr", CANDIDATE_DATA / "ref_srhr_classification.csv"
        ),
    }
    con.close()
    return counts


def load_country_coa():
    create_tables()
    con = connect()

    coa_b = pd.read_excel(
        CANDIDATE_DATA / "country_b_depenses.xlsx",
        sheet_name="Plan_comptable",
    )
    coa_b = pd.DataFrame(
        {
            "country_code": "CTB",
            "account_code": coa_b["code_budgetaire"].astype(str).str.strip(),
            "account_label": coa_b["libelle"].astype(str).str.strip(),
        }
    )

    coa_a = pd.read_csv(CONFIG / "coa_country_a.csv", dtype=str)
    coa_c = pd.read_csv(CONFIG / "coa_country_c.csv", dtype=str)
    coa = pd.concat([coa_a, coa_b, coa_c], ignore_index=True)

    count = _insert_dataframe(
        con, "ref_country_coa", coa[["country_code", "account_code", "account_label"]]
    )
    by_country = (
        con.execute(
            "SELECT country_code, COUNT(*) FROM ref_country_coa GROUP BY 1 ORDER BY 1"
        ).fetchall()
    )
    con.close()
    return {"ref_country_coa": count, "by_country": by_country}


def load_account_map():
    create_tables()
    con = connect()
    df = pd.read_csv(CONFIG / "account_mappings.csv", dtype=str)
    df["sha_code"] = df["sha_code"].fillna("")
    count = _insert_dataframe(con, "ref_account_map", df)
    by_country = con.execute(
        "SELECT country_code, COUNT(*) FROM ref_account_map GROUP BY 1 ORDER BY 1"
    ).fetchall()
    review = con.execute(
        "SELECT country_code, account_code FROM ref_account_map WHERE status = 'review' ORDER BY 1, 2"
    ).fetchall()
    con.close()
    return {"ref_account_map": count, "by_country": by_country, "review": review}


if __name__ == "__main__":
    print(load_who_reference_lists())
    print(load_country_coa())
    print(load_account_map())
