# WHO AFRO IFMIS Expenditure Tool (Prototype)

Technical assessment prototype for **REQ2602624** (Consultant, IT Systems and Data Extraction Tool Developer).

This prototype shows how a regional organisation could ingest heterogeneous country IFMIS expenditure extracts, store them, harmonise them into one structure, classify records to simplified SHA and SRHR codes, flag data-quality issues, and let an analyst review, download, and trace results back to the original source.

## Author / contact

- **Name:** Shepherd Maverudze  
- **Email:** [shepmave@gmail.com](mailto:shepmave@gmail.com)

## Prerequisites

- Python 3.10+ recommended
- Internet access once (to install packages from `requirements.txt`)

No separate database server is required. DuckDB creates a local file under `database/` on first run.

## Install and run

Clone or download this repository, then open a terminal in the project root.

**Windows**

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open the URL shown in the terminal (usually `http://localhost:8501`).

## How to import the three sample countries

Sample files are in `candidate_data/`. Expected file names:

| Country | File |
|---------|------|
| Country A (CTA) | `country_a_expenditure.csv` |
| Country B (CTB) | `country_b_depenses.xlsx` |
| Country C (CTC) | `country_c_expenditure.json` |

For **each** country (A, then B, then C):

1. Open **Import Data**.
2. Select the country.
3. Click **Load sample file** (or upload the matching file from any folder — the file name must match).
4. Review the **Import summary** (row counts and quality signals).
5. Click **Proceed with import** (or **Cancel import** to discard without saving).

After all three imports, use:

- **Expenditure list** — combined harmonised table, filters, CSV download  
- **Row detail / trace** — one record back to raw source  
- **Dashboard** — overview counts and one-currency charts  
- **Raw Data** — original columns as stored  

## Architecture (overview)

```text
Country file (CSV / Excel / JSON)
    → validate + import summary
    → raw table per country (DuckDB)
    → harmonise to common expenditure rows
    → classify (SHA / SRHR)
    → Streamlit UI (review, download, trace)
```

- **Country adapters** live in `src/ingest_raw.py` and `src/harmonise.py` (format-specific reading and field mapping).
- **Config** is in `config/source_definitions.yml` (file type, dates, currency).
- **Storage** is DuckDB (`database/who_expenditure.duckdb`): raw tables, `expenditure`, `ingest_batch`, and reference tables.
- **UI** is Streamlit (`app.py` + `pages/`).

## Classification approach

1. **Primary:** look up `(country_code, account_code)` in `config/account_mappings.csv` (CoA → SHA + SRHR).
2. **Fallback:** if no CoA map, match description text against `config/keyword_rules.csv` (skipped when description is flagged suspicious).
3. **Otherwise:** leave SHA/SRHR empty, set `classification_method = unmapped`, `confidence = none`, `needs_review = true`.

Confidence and `needs_review` reflect how reliable the assignment is (for example HC.7 and keyword hits are treated more cautiously). The SHA/SRHR lists in `candidate_data/` are the analytical reference dictionaries; the bridge from country accounts to those codes is the mapping CSV (not supplied ready-made in the sample pack).

## Assumptions

- File names must match the expected names above; folder location does not matter.
- Country C parent transaction amounts are used; nested `subTransactions` are stored for context and are not added into totals.
- Currencies are not converted; charts and totals use one currency at a time.
- Account→SHA/SRHR mappings in this prototype are illustrative judgements for the sample data and would be validated by health accounts experts in a real deployment.

## Limitations

- Prototype only: no authentication, no production hosting, no live IFMIS integration.
- Classification maps are small and sample-oriented, not a full national CoA or complete SHA implementation.
- No foreign-exchange conversion across KES / XOF / RWF / USD.
- Automated tests are minimal by design for this assessment.

## What we would change before production

- User authentication, roles, and audit logging  
- Hosted environment, backups, and schema migrations  
- Expert-validated CoA mappings and an approval workflow for uncertain rows  
- Stronger automated testing and CI  
- Hardened file handling and operational monitoring  
- Optional connectors to country systems beyond manual upload  

## Automated checks (optional)

A small smoke suite is included (not exhaustive):

```bash
pytest tests/test_core.py -q
```


| Path | Purpose |
|------|---------|
| `app.py` | Entry point and navigation |
| `pages/` | Analyst UI |
| `src/` | Ingest, quality, harmonise, classify, data access |
| `config/` | Source definitions, account mappings, keyword rules |
| `candidate_data/` | Sample extracts and reference lists |
| `database/` | DuckDB database file (created at runtime) |
| `requirements.txt` | Python dependencies |

## Use of AI-assisted tools

AI-assisted tools were used while completing this assessment:

- **ChatGPT** — for design discussion, structuring the approach, and assisting with implementation

The submitted solution was reviewed and can be explained, navigated, and defended by the candidate. Use of these tools is disclosed as required by the assessment brief.
