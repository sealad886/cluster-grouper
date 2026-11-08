# ADR-002: Memory-only upstream credentials and a local session

Date: 2026-11-08
Status: Accepted

## Context

Footage Review requires a Bearer token on every data request and creates a new token when its listener restarts. Cluster Grouper has one operator on one Mac.

## Decision

Retain the upstream token only in backend memory. Authorize the browser using an HttpOnly SameSite local session cookie and constrain hosts/origins. Validate literal HTTP loopback endpoints and reject redirects. Use an actual single-operator policy instead of a permissive JWT development stub.

## Alternatives considered

- Browser localStorage token: exposes a durable credential to browser scripts and leaves stale tokens behind.
- Database credential storage: unnecessary for the rotating local API and adds secret-at-rest handling.
- Full OIDC user management: outside the single-operator local purpose.

## Consequences

Backend restart requires reconnecting. OS-account access remains a trust boundary. Public exposure and multiple users require a new authentication design.

## References

- [Security design](../security.md)
- [API guide](../api.md)
