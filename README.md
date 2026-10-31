DataPulse — Automated Data Pipeline Monitoring and SLA Management



DataPulse is a Python-based data pipeline monitoring system designed to track CSV ingestion, data quality, pipeline execution, load history, and Service Level Agreement (SLA) conditions.



The project demonstrates an end-to-end data engineering workflow using synthetic datasets and a local SQLite database.



## 1. Project Overview



DataPulse provides:



- Synthetic CSV dataset generation.

- CSV ingestion and pipeline run tracking.

- Data validation and transformation.

- Rejected-record quarantine.

- Publishing validated customer and order records.

- Historical load-event tracking and retry attempts.

- SLA monitoring for late arrivals, completion delays, missing loads, and data freshness.

- Alert creation and tracking.

- A Streamlit dashboard for operational visibility.

- Automated tests for core pipeline and monitoring behavior.



## 2. Technology Stack



| Technology | Purpose |

|---|---|

| Python | Pipeline implementation |

| SQLite | Operational database |

| Pandas | CSV processing and data validation |

| PyYAML | Configuration handling |

| Streamlit | Monitoring dashboard |

| Pytest | Automated testing |

| SQL | Database schema, constraints, and indexes |



## 3. Architecture



The main pipeline follows this workflow:



```text

Synthetic CSV Files

&#x20;       |

&#x20;       v

&#x20;    Ingestion

&#x20;       |

&#x20;       v

&#x20; Load Event Registration

&#x20;       |

&#x20;       v

&#x20; Data Validation

&#x20;       |

&#x20;       v

&#x20; Data Transformation

&#x20;       |

&#x20;       +----------------------+

&#x20;       |                      |

&#x20;       v                      v

&#x20; Valid Records          Rejected Records

&#x20;       |                      |

&#x20;       v                      v

&#x20;   Publishing              Quarantine

&#x20;       |                      |

&#x20;       +----------+-----------+

&#x20;                  |

&#x20;                  v

&#x20;         Pipeline Metrics

&#x20;                  |

&#x20;                  v

&#x20;         SQLite Database

&#x20;                  |

&#x20;         +--------+--------+

&#x20;         |                 |

&#x20;         v                 v

&#x20;   SLA Monitoring    Streamlit Dashboard

&#x20;         |

&#x20;         v

&#x20;       Alerts

```



## 4. Database Design



The main operational database is:



`data/datapulse\_phase2.db`



It contains seven tables:



| Table | Purpose |

|---|---|

| datasets | Dataset configuration and SLA settings |

| pipeline\_runs | Pipeline execution history |

| load\_events | File arrival, processing, and retry history |

| customer\_target | Published customer records |

| orders\_target | Published order records |

| quarantine\_records | Rejected records and reasons |

| alerts | SLA and pipeline monitoring alerts |



The schema includes primary keys, foreign keys, uniqueness constraints, validation checks, and indexes.



Foreign-key enforcement is enabled on SQLite connections.



## 5. Project Structure



```text

datapulse/

│

├── app/

│   └── app.py

│

├── config/

│   ├── datasets.yaml

│   └── settings.yaml

│

├── data/

│   ├── sample/

│   ├── expected/

│   └── landing/

│

├── scripts/

│   └── run\_sla\_checks.py

│

├── sql/

│   ├── phase2\_schema.sql

│   ├── phase2\_verify.sql

│   └── schema.sql

│

├── src/

│   └── datapulse/

│       ├── database.py

│       ├── generator.py

│       ├── ingestion.py

│       ├── load\_events.py

│       ├── pipeline.py

│       ├── publishing.py

│       ├── quarantine.py

│       ├── sla\_monitor.py

│       ├── transformation.py

│       └── validation.py

│

├── tests/

├── requirements.txt

├── pyproject.toml

└── README.md

```



## 6. Installation and Setup



### Prerequisites



- Python 3.10 or later

- Git



### Clone the repository



```powershell

git clone https://github.com/Sakshi281204/datapulse.git

cd datapulse

```



### Create a virtual environment



```powershell

python -m venv .venv

```



Activate it:



```powershell

.venv\\Scripts\\Activate.ps1

```



### Install dependencies



```powershell

python -m pip install -r requirements.txt

python -m pip install -e .

```



### Initialize the database



```powershell

python -m datapulse.database

```



This creates the Phase 2 database, initializes its tables and indexes, and seeds four dataset configurations:



- Customers

- Products

- Orders

- Payments



The initialization command is safe to rerun for the schema and dataset configuration. It does not reset existing operational records.



## 7. Generate Synthetic Data



DataPulse includes a reproducible synthetic data generator.



Generate datasets using:



```powershell

python -m datapulse.generator --count 100 --seed 42

```



The generator supports:



- Configurable record counts.

- Reproducible output using a seed.

- Customer, product, order, and payment CSV generation.

- Validation labels for generated records.

- Optional clean-data generation.

- Custom output and expected-data directories.



Generate clean data without injected quality issues:



```powershell

python -m datapulse.generator --count 100 --seed 42 --clean

```



\*\*Note:\*\* The generator writes files to its output directories. Review existing files before running it again, particularly if you have modified sample datasets.



## 8. Run the Data Pipeline



The end-to-end pipeline currently supports the customers and orders datasets.



### Process customers



```powershell

python -c "from datapulse.pipeline import run\_dataset\_pipeline; print(run\_dataset\_pipeline('customers', 'data/sample/customers.csv'))"

```



### Process orders



Run customers first so the customer records are available for order-reference validation.



```powershell

python -c "from datapulse.pipeline import run\_dataset\_pipeline; print(run\_dataset\_pipeline('orders', 'data/sample/orders.csv'))"

```



The pipeline performs:



1\. CSV ingestion.

2\. Pipeline run creation.

3\. Load-event registration.

4\. Data validation.

5\. Data transformation.

6\. Rejected-record quarantine.

7\. Valid-record publishing.

8\. Final pipeline and load metrics.



Pipeline outcomes include `SUCCESS`, `PARTIAL`, and `FAILED`.



A partial run means that some records were rejected while valid records could still be published.



## 9. SLA Monitoring



SLA checks are executed manually:



```powershell

python scripts/run\_sla\_checks.py

```



The monitoring logic evaluates:



- Late file arrivals.

- Completion SLA breaches.

- Missing expected loads.

- Dataset freshness.

- Duplicate alert prevention.



Alerts are stored in the SQLite database with severity, status, timestamps, and identifying fingerprints.



\*\*Important:\*\* Running the SLA script can update load-event and alert records. It is not a read-only operation.



## 10. Run the Dashboard



Start the Streamlit dashboard:



```powershell

streamlit run app/app.py

```



The dashboard provides visibility into:



- Dataset configurations.

- Pipeline execution history.

- Load-event history.

- Customer and order record counts.

- Data-quality metrics.

- Rejected records and quarantine reasons.

- Alert summaries and history.

- Arrival, completion, and freshness status.



The dashboard reads from the existing Phase 2 database. Opening or refreshing it does not execute ingestion or SLA checks or create alerts.



## 11. Run Automated Tests



Run the complete test suite:



```powershell

pytest -v

```



The test suite covers database initialization, synthetic data generation, ingestion, validation, transformation, quarantine, publishing, pipeline execution, recovery, load history, and SLA monitoring.



\*\*Latest verified result:\*\* 115 tests passed.



## 12. Current Scope and Limitations



The current implementation has the following boundaries:



- End-to-end publishing supports customers and orders.

- Products and payments are configured and generated as synthetic datasets but are not yet processed by the end-to-end publishing pipeline.

- The operational database uses SQLite and runs locally.

- SLA monitoring is manually triggered rather than running as a scheduled background service.

- The dashboard is for monitoring and does not trigger pipeline execution.

- Synthetic data is used for development and testing; it is not production customer data.



## 13. Design Considerations



Some implementation choices were made to keep the project reproducible and traceable:



- SQLite provides a lightweight local operational database.

- Foreign keys and database constraints protect relationships between records.

- Load events preserve historical attempts instead of overwriting previous attempts.

- Deterministic identifiers support reproducible synthetic data.

- Rejected records are stored separately for investigation.

- Pipeline metrics provide record-level reconciliation.

- SLA checks are separated from dashboard rendering to avoid unintended state changes when the dashboard is refreshed.



## 14. Author



\*\*Sakshi Gurule\*\*



GitHub: https://github.com/Sakshi281204



---



\*DataPulse is a data engineering project developed using synthetic data for pipeline orchestration, data quality, operational monitoring, and SLA management.\*
