# ADR-005: Maintained lint and HTTP dependencies

Date: 2026-11-08
Status: Accepted

## Context

Setup reported the deprecation of ESLint 9.39.5. Its Next.js lint configuration also brought a moderate minimatch advisory through TypeScript ESLint. At the time of this update, patched minimatch 11 was outside that parent's supported dependency range. Moving to ESLint 10 still left incompatible plugin peer requirements. Separately, Starlette's TestClient deprecated its HTTPX fallback in favor of HTTPX2.

The repository has an npm project in `frontend/`, with no npm manifest at the repository root. Unscoped npm commands from the root can resolve to an unrelated parent project.

## Decision

Use Oxlint's maintained native rules for TypeScript, React hooks, Next.js, imports, and accessibility. Remove ESLint, its Next.js configuration package, and the obsolete configuration file. Keep generated API declarations excluded and retain the intentional allowance for local crop `<img>` elements. TypeScript still checks application types independently.

Replace HTTPX with Pydantic's maintained HTTPX2 client throughout application code and tests. Remove the old HTTPX/HTTPCore dependencies, use the new import names directly, and treat test warnings as failures. Preserve upstream authentication, timeout, loopback, proxy, redirect and replay behavior. HTTPX2 uses the operating system TLS trust store; model downloads remain pinned by SHA256 and size.

Use explicit `npm --prefix` paths in Make targets and CI. Keep the manifest and lockfile together in `frontend/`; do not import or modify a home-directory project's packages. Audits include development dependencies and fail for any reported vulnerability.

## Alternatives considered

- Retain deprecated ESLint 9: leaves both the maintenance warning and vulnerable development dependency chain.
- Force ESLint plugin peers or override minimatch across major versions: bypasses upstream compatibility declarations.
- Introduce a second npm workspace layout: unnecessary for maintaining this application's dependencies.
- Retain both HTTP clients or alias old imports: unnecessary because this application controls all consumers.

## Consequences

- Frontend tooling requires Node.js 22.12 or newer.
- The lint implementation changes; behavioral probes check hooks, accessibility, Next.js navigation and TypeScript rules, rather than claiming identical rule sets.
- Six former rule names have no direct native equivalent. React's JSX-use markers are handled by native unused-variable analysis. The `react/no-deprecated` diagnostic is not replicated: React 19 TypeScript definitions reject removed APIs but do not flag every still-supported deprecated API. Compiler configuration/gating checks do not apply because this app has no compiler configuration, and the Next.js relative `location.assign` guard has no current caller. This is a bounded difference, not a claim of identical compiler diagnostics.
- Lockfile updates are reviewed alongside clean installation, audits, types, builds and existing behavioral tests.
- Parent and global npm projects remain independently managed.

## References

- [Oxlint](https://oxc.rs/docs/guide/usage/linter.html)
- [HTTPX2 migration guide](https://pydantic.dev/docs/httpx2/get-started/migration/)
- [npm prefix configuration](https://docs.npmjs.com/cli/v12/using-npm/config#prefix)
- [minimatch advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249)
