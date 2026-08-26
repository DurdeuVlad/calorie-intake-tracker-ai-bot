# ADR 0006: Python is the canonical implementation

## Status

Accepted

## Context

This repository temporarily contained both a Python successor under `python-app/` and a Java implementation under the repository root. The Java implementation is maintained as the standalone sister repository [`DurdeuVlad/calorie-intake-tracker-ai-bot-java`](https://github.com/DurdeuVlad/calorie-intake-tracker-ai-bot-java).

Maintaining two source trees, build systems, container definitions, CI pipelines, and runtime documentation in one repository created drift and made it unclear which implementation was authoritative.

## Decision

`python-app/` is the only canonical implementation and delivery path in this repository. It owns application code, tests, configuration, Docker packaging, the retained PostgreSQL baseline, and Alembic schema revisions.

The Java source tree, Maven wrapper, Maven build, Java Docker/Compose files, and Java CI workflow are removed from this repository. The Java sister repository remains the location for the Java variant.

## Constraints

- Preserve the existing PostgreSQL V1–V17 baseline needed by current deployments and tests.
- Preserve feature parity for access control, messaging, account linking, journal mutations, undo, media handling, external nutrition tools, scheduling, and evaluations.
- Do not run both implementations as writers against the same journal.
- Treat the Java sister repository as historical/reference context, not a local build dependency.

## Consequences

- Agents and contributors have one local implementation to inspect, test, and change.
- Python CI and Docker builds are the only repository release gates.
- The V1–V17 PostgreSQL baseline is retained under `python-app/alembic/flyway_baseline/`; future schema changes use Alembic.
- Java-specific historical references may remain in comments or ADRs, but active instructions and operational docs must not route work to Java files.
