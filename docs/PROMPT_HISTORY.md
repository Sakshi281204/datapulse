# Prompt History and AI Usage Record

## 1. How prompts were used (honest summary)

- I used a ChatGPT-provided roadmap that contained suggested prompts for each
  development phase (project setup, database, data generator, ingestion,
  validation and quarantine, transformation, SLA monitoring, freshness,
  alerts, pipeline orchestration, testing, dashboard, performance, final
  documentation).
- I used the roadmap prompts as reference and wrote my own prompts in my own
  words. My prompts are reproduced verbatim in
  `docs/prompt_exports/chatgpt_prompts.md`.
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
- Reviewed Git diffs before committing, and caught and corrected an encoding
  problem in the README before it was committed.
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

The verbatim export covers my development prompts. Later follow-up prompts
(debugging, test fixes, final review) may be summarised rather than listed.
