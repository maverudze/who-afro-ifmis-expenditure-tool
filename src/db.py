"""DuckDB connection for the WHO AFRO expenditure prototype."""

from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "who_expenditure.duckdb"


def connect():
    """Open (or create) the prototype database file."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def create_database():
    """Create the empty DuckDB file."""
    con = connect()
    con.close()
    return DB_PATH


def create_tables(con=None):
    """Create schema tables if they do not already exist."""
    close_after = False
    if con is None:
        con = connect()
        close_after = True

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ingest_batch (
            ingest_id VARCHAR PRIMARY KEY,
            country_code VARCHAR,
            source_file_name VARCHAR,
            loaded_at TIMESTAMP,
            rows_read INTEGER,
            rows_stored INTEGER
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_country_a (
            ingest_id VARCHAR,
            source_file_name VARCHAR,
            loaded_at TIMESTAMP,
            source_row_number INTEGER,
            TXN_ID VARCHAR,
            DATE VARCHAR,
            MINISTRY_CODE VARCHAR,
            MINISTRY_NAME VARCHAR,
            ACCOUNT_CODE VARCHAR,
            DESCRIPTION VARCHAR,
            VENDOR VARCHAR,
            AMOUNT_KES VARCHAR,
            PAYMENT_METHOD VARCHAR
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_country_b (
            ingest_id VARCHAR,
            source_file_name VARCHAR,
            loaded_at TIMESTAMP,
            source_row_number INTEGER,
            id_transaction VARCHAR,
            date_ecriture VARCHAR,
            ministere_code VARCHAR,
            ministere_nom VARCHAR,
            code_budgetaire VARCHAR,
            libelle VARCHAR,
            tiers VARCHAR,
            montant_XOF VARCHAR
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_country_c (
            ingest_id VARCHAR,
            source_file_name VARCHAR,
            loaded_at TIMESTAMP,
            source_row_number INTEGER,
            transactionId VARCHAR,
            postingDate VARCHAR,
            fiscalYear VARCHAR,
            ministryCode VARCHAR,
            ministryName VARCHAR,
            coaCode VARCHAR,
            description VARCHAR,
            supplier VARCHAR,
            amount VARCHAR,
            currency VARCHAR,
            subTransactions VARCHAR
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS expenditure (
            expenditure_id VARCHAR PRIMARY KEY,
            ingest_id VARCHAR,
            country_code VARCHAR,
            source_txn_id VARCHAR,
            txn_date DATE,
            fiscal_year VARCHAR,
            ministry_code VARCHAR,
            ministry_name VARCHAR,
            account_code VARCHAR,
            account_description VARCHAR,
            vendor VARCHAR,
            amount_original DOUBLE,
            currency_original VARCHAR,
            sha_code VARCHAR,
            srhr_code VARCHAR,
            classification_method VARCHAR,
            confidence VARCHAR,
            needs_review BOOLEAN,
            rationale VARCHAR,
            quality_flags VARCHAR,
            raw_table VARCHAR,
            raw_row_id INTEGER
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ref_country (
            country_code VARCHAR PRIMARY KEY,
            country_name VARCHAR,
            primary_currency VARCHAR,
            language VARCHAR
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ref_sha (
            sha_code VARCHAR PRIMARY KEY,
            sha_description VARCHAR,
            notes VARCHAR
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ref_srhr (
            srhr_code VARCHAR PRIMARY KEY,
            srhr_description VARCHAR,
            notes VARCHAR
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ref_country_coa (
            country_code VARCHAR,
            account_code VARCHAR,
            account_label VARCHAR,
            PRIMARY KEY (country_code, account_code)
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ref_account_map (
            country_code VARCHAR,
            account_code VARCHAR,
            sha_code VARCHAR,
            srhr_code VARCHAR,
            status VARCHAR,
            PRIMARY KEY (country_code, account_code)
        )
        """
    )

    if close_after:
        con.close()
