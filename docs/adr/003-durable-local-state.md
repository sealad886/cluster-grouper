# ADR-003: SQLite and checkpointed local jobs

Date: 2026-11-08
Status: Accepted

## Context

Exports, embeddings, review decisions, and uncertain imports must survive normal app restarts. A local tool should not require an external database or queue service merely to run.

## Decision

Use SQLAlchemy with SQLite, Alembic migrations, JPEG bytes and embedding JSON in the database, and a persistent single-process worker. Checkpoint jobs and leave interrupted work paused for explicit resume. Persist immutable import bytes before any upstream write. Preserve incomplete exports as incomplete.

This is a deliberate exception to the generic Postgres/Redis stack defaults for a single-operator, same-Mac integration.

## Alternatives considered

- Postgres plus Redis/Celery: appropriate for distributed workers, but adds services without serving this deployment.
- Memory-only work queue: loses recovery state and uncertain import evidence.
- Browser-only persistence: cannot reliably own long-running inference and server-side API secrets.

## Consequences

Run one backend process, not multiple workers. Back up the complete stopped state directory. Scaling to concurrent operators or distributed jobs requires a separate design.

## References

- [Data model](../data-model.md)
- [Runbook](../runbook.md)
