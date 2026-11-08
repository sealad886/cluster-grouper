# ADR-001: Local FastAPI and Next.js application

Date: 2026-11-08
Status: Accepted

## Context

The supplied API is available only on the same Mac as Footage Review. The operator needs an ordinary review UI with crop display and explicit import controls.

## Decision

Use FastAPI, Pydantic, SQLAlchemy 2, Alembic, and a Next.js/TypeScript browser UI. Bind the services to loopback and proxy browser API requests through Next.js. Use uv for the project Python environment and locked installation, matching available tooling.

## Alternatives considered

- Browser-only client: complicates credential handling, durable jobs, model inference, and private local state.
- Hosted service: cannot directly reach the same-Mac API and introduces an unnecessary image-transfer boundary.
- Native-only UI: viable, but not necessary for this API-focused MVP and would increase platform-specific implementation.

## Consequences

The app is runnable locally with normal browser controls. Python and Node runtimes are required. This decision does not provide a remote deployment design.

## References

- [Architecture](../architecture.md)
- [Supplied API quick reference](../../Footage_Review_API_Quick_Reference.pdf)
