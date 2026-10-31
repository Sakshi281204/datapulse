# AI Usage Disclosure

## 1. Purpose

AI tools were used as development assistants during the DataPulse
challenge. They helped accelerate implementation, explain technical
concepts, review errors, and structure the development workflow.

AI assistance was not treated as a replacement for running the
application, checking the results, or testing the implementation.

## 2. Areas Where AI Assistance Was Used

AI assistance was used for:

- Breaking the challenge requirements into manageable development phases.
- Explaining database schema design, relationships, constraints, and indexes.
- Suggesting implementation approaches for synthetic data generation,
  ingestion, validation, transformation, publishing, and pipeline tracking.
- Explaining test failures and helping investigate debugging issues.
- Reviewing validation rules, schema handling, and edge cases.
- Helping organize project documentation and explain design trade-offs.
- Suggesting commands for running tests and verifying project behaviour.

## 3. Representative Prompt Topics

The following are representative summaries of development requests.
They are not presented as a verbatim export of the complete chat history.

1. Design the SQLite database schema for datasets, load events,
   pipeline runs, target tables, quarantine records, and alerts.
2. Implement reproducible synthetic data generation with configurable
   row counts and deterministic seeds.
3. Build CSV ingestion and pipeline tracking while preserving existing
   working functionality.
4. Implement customer and order validation rules, including missing
   values, duplicate identifiers, invalid references, and data types.
5. Add tests for schema drift and unexpected source columns.
6. Diagnose pipeline recovery, retry, and idempotency test failures.
7. Review documentation requirements and prepare reproducible
   installation, testing, and performance evidence.

## 4. Human Review and Validation

The project owner performed the following activities:

- Executed development commands and scripts in the local Windows
  PowerShell environment.
- Reviewed terminal output and investigated errors before proceeding.
- Ran the automated test suite and checked the reported results.
- Verified database and pipeline behaviour through project tests
  and the running dashboard.
- Measured synthetic data generation time using PowerShell
  `Measure-Command`.
- Checked generated CSV row counts, column counts, and file sizes.
- Reviewed project changes and Git status during development.
- Made decisions about which implementation steps to accept and
  when to proceed to the next phase.

AI-generated suggestions were reviewed and tested in the project
environment rather than assumed to be correct.

## 5. Validation Evidence

At the time this document was prepared:

- The automated test suite reported 117 passing tests.
- The synthetic generator successfully generated 100,000 rows
  for each of four datasets in approximately 12.48 seconds.
- The generator benchmark was verified separately from
  end-to-end pipeline performance.
- Schema validation tests covered rejection of unexpected
  customer and order columns.

These results describe checks actually performed during development.
They do not imply that every possible input or production workload
has been tested.

## 6. Limitations

AI assistance can produce incorrect assumptions, code, or explanations.
All important implementation decisions and outputs therefore require
human review and testing.

The representative prompt topics above summarize the development
workflow. They are not a complete transcript of every AI interaction.
