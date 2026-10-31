# Prompt History and AI Usage Record

## 1. How prompts were used (honest summary)

- I used a ChatGPT-provided roadmap that contained suggested prompts for each
  development phase (project setup, database, data generator, ingestion,
  validation and quarantine, transformation, SLA monitoring, freshness,
  alerts, pipeline orchestration, testing, dashboard, performance, final
  documentation).
- I used the roadmap prompts as reference and wrote my own prompts in my own
  words. My development prompts are in section 7. They are reconstructed, human-style versions of the prompts I used, not a verbatim export of the original ChatGPT or Claude conversations. The table in section 2 summarises them by phase.
- The table below is a **reconstruction of what I asked in each phase**, not a
  verbatim log.
- During final submission preparation I also asked an AI assistant to review
  Git changes, audit the code against the challenge requirements, and help
  write documentation. Those requests and their results are in that chat.

## 2. Phases, what I asked, and what I did myself

| Phase | What I asked the AI for (reconstructed) | What I reviewed / ran myself |
|---|---|---|
| Setup | Project structure, virtual environment, dependencies | Ran commands on Windows PowerShell, confirmed packages |
| Database | SQLite schema with seven tables, keys, indexes, seeded dataset configs | Ran schema, verified tables and foreign keys |
| Data generator | Reproducible synthetic data, fixed seed 42, labelled invalid records | Generated data and checked counts |
| Ingestion | CSV reading, run IDs, failed-run recording | Ran success and failure cases |
| Validation and quarantine | Rules for customers and orders, duplicates, invalid references, rejects | Ran tests, checked rejected rows |
| Transformation and publishing | Cleaning, ISO timestamps, idempotent inserts | Checked rerun does not duplicate rows |
| SLA monitoring | Late, missing, completion breach, freshness, alerts | Ran SLA tests with fixed timestamps |
| Testing | Pytest suite for edge cases and retry/restart | Ran the full suite and fixed failures |
| Dashboard | Streamlit monitoring view from SQLite queries | Launched the dashboard |
| Performance | 100,000-record benchmark and reconciliation | Ran benchmark on an isolated database |
| Final review | Git audit, schema-change test, design notes, documentation | Reviewed diffs, ran 118 tests, edited docs |

## 3. Where AI helped most and where I relied on it heavily

- AI generated most first drafts of the modules and tests, and explained
  errors when tests failed.
- I relied heavily on AI for boilerplate (schema SQL, test scaffolding,
  documentation drafts).
- I did not copy the AI's claims about results. I ran the tests and the
  benchmark myself and recorded measured numbers only.

## 4. What I personally reviewed, changed or validated

- Ran the full test suite (118 tests passing at the time of this note).
- Reviewed Git diffs before committing, and caught an encoding problem in the README diff before committing and fixed it with AI assistance.
- Added the unexpected-columns schema check and tests, including a
  pipeline-level test that confirms a FAILED run with the error recorded.
- Checked that products and payments are generated and registered only, and
  documented that limitation.
- Confirmed the benchmark was run on an isolated database and did not touch
  my original database.

## 5. Things I understand and can explain

Pipeline flow, the reconciliation formula (received = inserted + skipped +
rejected), idempotency via primary keys and ON CONFLICT DO NOTHING, the
quarantine path, SLA and freshness logic, why SQLite and pandas were chosen,
and the main limitations (customers and orders only, files read fully into
memory, first write wins).

## 6. Limits of this record

The prompts in section 7 are reconstructed, not verbatim exports. Later follow-up prompts (debugging, test fixes, final review) are not listed.


## 7. Development prompts (reconstructed)

These are reconstructed, human-style versions of the prompts I used. They are not a verbatim export of the original ChatGPT or Claude conversations.

### Prompt 1 - Understanding the challenge and planning the project

I have received a 72-hour technical challenge from YottaFlex.ai for the Associate AI Forward Deployed Engineer role. I want to understand the complete problem before starting development.

Please go through the requirements carefully and explain what exactly needs to be built, what the expected outcome should look like, and which technical concepts I need to understand.

Help me plan the project architecture, database structure, folder organization, development phases, and testing strategy. I want to build something that solves the actual business problem rather than just creating a basic demonstration.

Please explain everything step by step and do not start writing code until the requirements and development plan are clear.

### Prompt 2 - Setting up the development workflow

I want to build this project with your help, but I want to understand what I am doing instead of blindly copying code.

Act as an experienced Python and data engineering developer who can guide me through the project.

Please follow these instructions throughout development:
- Explain what we are going to implement before giving me code.
- Tell me which file needs to be created or modified.
- Provide exact commands that I can execute in Windows PowerShell.
- Explain what the expected output should look like.
- Give me one task at a time.
- Wait for me to share the terminal output before moving to the next task.
- If something fails, help me fix it before continuing.
- Do not repeat work that has already been completed.
- Do not assume something is working without verification.

I want the project to be clean, maintainable, and suitable for a technical interview.

### Prompt 3 - Project structure and configuration

Let's start setting up the DataPulse project.

Help me create a proper Python project structure with separate modules for database operations, ingestion, validation, transformation, pipeline execution, monitoring, and other required functionality.

Set up the configuration and dependency management properly. Keep environment-specific settings separate from application logic.

Please explain the purpose of every important folder and file. Give me the commands one by one and verify that the project structure is correct before moving forward.

### Prompt 4 - Database design and implementation

Build the SQLite database for DataPulse.

The database should contain these tables:
- datasets
- load_events
- pipeline_runs
- customer_target
- orders_target
- quarantine_records
- alerts

Please define the primary keys, foreign keys, data types, nullability, unique constraints, and indexes properly.

I also want deterministic IDs, run ID tracking, source file tracking, and historical load attempts to be preserved. Store expected arrival time, actual arrival time, completion time, and SLA configuration wherever required.

Make sure the database design supports the complete pipeline and future monitoring requirements.

Explain the schema first, then implement it step by step. Include database initialization and verification tests.

### Prompt 5 - Synthetic data generation

Now help me implement a synthetic data generator for DataPulse.

I need realistic sample datasets that can be used to test the complete pipeline. Generate customers, products, orders, and payments with proper relationships between them.

The generator should support configurable record counts and use a fixed random seed so that the output is reproducible.

Please make sure the generated records have realistic values and that the relationships between datasets remain consistent.

I also want to generate larger datasets to test performance. Explain how to run the generator and verify the generated files and record counts.

### Prompt 6 - CSV ingestion and load-event tracking

Now let's implement the CSV ingestion functionality.

The system should be able to read incoming CSV files, identify the dataset, register the load event, and track the associated source file and pipeline run.

Make sure every load attempt is recorded, including failed attempts. Historical records should not be overwritten when the same file is processed again.

Track the relevant timestamps and load status. Handle missing files, invalid files, and other ingestion errors properly.

Please implement this in a clean way and add tests for successful ingestion, failed ingestion, and repeated load attempts.

### Prompt 7 - Data validation and quarantine

Now implement the validation module for DataPulse.

I want proper validation rules for both customer and order records.

For customers, validate that:
- customer_id is not null.
- customer_id is unique.
- customer_name is not empty.
- email has a valid format.
- city is not null.

For orders, validate that:
- order_id is not null.
- order_id is unique.
- customer_id exists in the customers dataset.
- order_amount is greater than zero.
- order_timestamp is valid.

Invalid records should not be silently discarded. Store them in the quarantine table along with the reason why each record failed validation.

Valid records should continue through the pipeline wherever appropriate.

Please write focused tests for each validation rule, including valid and invalid examples.

### Prompt 8 - Data transformation and publishing

Now help me implement the transformation and publishing stages.

After ingestion and validation, valid records should be transformed into the required target-table format and published into the SQLite database.

Please make sure that customer and order relationships remain correct.

I also want proper duplicate handling. If the same input is processed multiple times, it should not create unwanted duplicate records.

Implement the logic in a maintainable way and include tests for successful publishing, duplicate records, invalid references, and repeated processing.

### Prompt 9 - Pipeline orchestration

Now connect all the individual stages into one complete DataPulse pipeline.

The pipeline should execute ingestion, validation, transformation, and publishing in the correct order.

Track each pipeline execution with a run ID and store its status, start time, completion time, and relevant information.

Handle failures properly. If one stage fails, the pipeline should record the failure rather than silently continuing.

I also want the pipeline to support recovery and retries without corrupting previously processed data.

Please explain the execution flow and test both successful and failed pipeline runs.

### Prompt 10 - SLA monitoring

Now implement SLA monitoring for DataPulse.

Each dataset has its own expected arrival time and SLA configuration.

The system should compare expected arrival time, actual arrival time, and pipeline completion time to determine whether the dataset was processed within the expected time.

It should identify delayed loads, missing loads, failed loads, and SLA breaches.

Please make the calculations reliable and easy to test. Include different scenarios such as on-time arrival, late arrival, missing data, and delayed processing.

### Prompt 11 - Data freshness monitoring

I also want DataPulse to monitor data freshness.

Help me implement logic that identifies when a dataset has not been updated within its expected freshness window.

The monitoring should use the dataset configuration and available load history rather than hardcoded values.

Make sure the system can distinguish fresh data from stale data and provide useful information for monitoring.

Include tests for different freshness scenarios and explain how the freshness result is calculated.

### Prompt 12 - Alert generation

Now implement the alert-generation functionality.

DataPulse should generate alerts for important operational problems, including:
- Missing dataset arrivals.
- Late data arrivals.
- Failed pipeline executions.
- Stale datasets.
- SLA breaches.

Store alert details in the alerts table with the relevant dataset, run, timestamp, and alert information.

Please make sure alerts are useful for investigation and avoid generating misleading or unnecessary duplicate alerts.

Add tests to verify that alerts are generated for the correct conditions.

### Prompt 13 - Automated testing

I want to improve the automated test coverage of the complete DataPulse project.

Please review the existing implementation and identify the important scenarios that should be tested.

Include tests for:
- Database initialization and schema.
- Dataset configuration.
- CSV ingestion.
- Load-event registration.
- Data validation.
- Quarantine handling.
- Transformation and publishing.
- Duplicate handling.
- Idempotency.
- Pipeline execution.
- Failure recovery.
- SLA monitoring.
- Data freshness.
- Alert generation.

Use pytest and make sure tests do not interfere with one another. Use isolated temporary databases wherever necessary.

Please run the tests in manageable groups, explain failures, and fix issues before proceeding.

### Prompt 14 - Dashboard development

Now help me develop the DataPulse dashboard using Streamlit.

I want the dashboard to give a clear overview of pipeline health and operational status.

It should display useful information such as:
- Total datasets.
- Recent pipeline runs.
- Successful and failed executions.
- Dataset freshness.
- SLA breaches.
- Quarantined records.
- Active alerts.
- Relevant pipeline performance information.

All displayed values should come from the database. Do not use hardcoded sample metrics.

Keep the dashboard clean and easy to understand. Explain how to run it locally and verify that the displayed information matches the database.

### Prompt 15 - Performance testing and reconciliation

Now I want to evaluate how DataPulse performs with larger datasets.

Help me create a repeatable performance-testing process that measures processing time for representative data volumes.

Also implement reconciliation checks to verify that records are accounted for correctly across the pipeline.

I want to check:
- Total source records.
- Valid records.
- Invalid records.
- Quarantined records.
- Published records.
- Duplicate records.
- Referential integrity.
- Foreign-key violations.

Please explain the benchmark methodology and record the actual results. Do not invent performance numbers or claim improvements without measurement.

### Prompt 16 - Documentation and GitHub preparation

The main implementation is progressing, and I now want to prepare the project for GitHub and technical review.

Help me create professional documentation that explains:
- What DataPulse does.
- The business problem it solves.
- The architecture and technology stack.
- Project folder structure.
- Database schema.
- Data pipeline workflow.
- Setup and installation instructions.
- How to execute the pipeline.
- How to run the dashboard.
- How to run automated tests.
- Performance and reconciliation results.
- Known limitations.

Also prepare a transparent AI usage document explaining how AI tools supported the development process.

Make sure the documentation only describes features that actually exist in the project.

### Prompt 17 - Continue from the existing project without repeating work

I have already completed several development phases in DataPulse. I want to continue from the exact current project state.

First, inspect the existing files, project structure, Git status, and available test results.

Please identify:
1. What has already been implemented.
2. What has been tested successfully.
3. What is incomplete.
4. What still needs to be corrected.
5. What remains before final submission.

Do not recreate existing files or repeat completed implementation.

Guide me one task at a time. For every task, provide the exact PowerShell commands, explain the expected output, and wait for me to share the actual output before moving forward.

If a test fails, stop and help me fix it first.

Do not commit or push anything without asking me for approval.

### AI tools used during development

The prompts above were prepared with assistance from ChatGPT and then rewritten into my own words before being used during development.

The rewritten instructions were provided to AI development tools, including:
- ChatGPT
- Claude

These tools assisted with implementation guidance, code generation, debugging, testing, and documentation.

The prompts were used as instructions for the development work. The tools' outputs were reviewed and tested in the local DataPulse project environment.

### Developer responsibility and verification

I remained responsible for understanding the challenge, managing the project, executing commands, reviewing outputs, and checking whether the implementation met the requirements.

AI-generated code was not treated as automatically correct. I used terminal outputs, automated tests, database checks, and performance measurements to verify the work.

Transparency note: This section contains reconstructed, human-style versions of the development prompts. It is not a verbatim export of the original ChatGPT or Claude conversations.
