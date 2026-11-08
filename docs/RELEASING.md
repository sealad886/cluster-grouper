# Cluster Grouper release policy

## Scope and current state

Cluster Grouper is one application released from the repository root. Its Python backend and private browser frontend share one product version. The supported contract includes local API behavior, job controls, review/import semantics, persistent state, setup commands and supported runtimes. Footage Review is a separate application: its native version, bundle build number, source patch and historical validation are outside this release unit.

The initial versioned source release is **`v0.1.0`**, created locally under explicit user authority. `.release-please-manifest.json` tracks `0.1.0` as that first Git baseline; it does not claim hosted or registry publication. There is no configured remote or package registry identity. The initial commit and tag do not enable hosted release automation.

## Version ownership

**Release Please is the sole version writer.** It proposes changes in a release PR; a maintainer reviews and merges that PR. Do not run a second bump tool, manually increment mirrors, or add Changesets/semantic-release for this unit.

| Role | Source | Update/read mechanism |
|---|---|---|
| Canonical application version | `backend/pyproject.toml`, `project.version` | Release Please typed TOML updater |
| Backend lock mirror | `backend/uv.lock`, exact `cluster-grouper-backend` project entry | Scoped TOML updater; dependency versions are excluded |
| Frontend mirror | Private `frontend/package.json`, `version` | JSON updater |
| Frontend lock mirrors | `frontend/package-lock.json`, root `version` and `packages[""].version` | Two scoped JSON updates to the same file |
| Runtime/API documentation | FastAPI/OpenAPI `info.version` | Reads the canonical backend manifest independently of the working directory |
| Tool tracking | `.release-please-manifest.json` | Release Please; tracking/pending version is not proof of publication |
| Release notes | Root `CHANGELOG.md` | Created/updated by the first release PR |

The backend is currently a uv virtual project operated from a source checkout, with no installed Python distribution. Runtime metadata therefore reads the source manifest rather than querying nonexistent installed wheel metadata. This configuration introduces no wheel, npm package, registry publisher or packaging-layout migration.

The Release Please package path is `.` so frontend-only and root-script changes participate in the same release. Its Python strategy uses explicit typed extra-file updates because the canonical manifest is under `backend/`; there is no duplicate root `pyproject.toml`. The Python strategy does not natively update uv locks, so the project-entry selector is essential. Both frontend lock selectors are also required. Release Please 17.6.0's tagged TOML parser needs `@.name.value` in the uv selector; an ordinary `@.name` silently matches nothing. The actual pinned updater was tested against all five fields, preserving unrelated dependency versions. Repeat that engine-level check when upgrading Release Please.

## Versions, channels and review

- Current automation supports stable `X.Y.Z` version syntax only, including pre-1.0 versions. Prerelease channels and PEP 440 mappings need a separately reviewed configuration change.
- Before 1.0, features and breaking changes increment the minor version; compatible fixes increment patch. These are explicit project choices. Declaring 1.0 stability requires an explicit decision.
- Use Conventional Commits to express intent (`feat:`, `fix:`, and `!`/`BREAKING CHANGE:` when appropriate). Review the cumulative behavior change against the last verified release; labels alone do not prove compatibility.
- The pinned Python strategy initializes a first release at `0.1.0`. No artificial baseline or ignored `initial-version` setting is supplied. Before enabling automation, confirm the initial commit history and candidate are still appropriate. The checker rejects a different untracked first candidate.
- Future tags follow `vX.Y.Z`, without a component prefix. Existing published tags and assets are immutable. Calculate a pending version from the verified release baseline; do not repeatedly bump a pending number.
- Release PRs require maintainer approval and the existing backend/frontend checks plus the new `release-metadata` check. Review lockfile diffs and the generated changelog before merge.

## Configured workflow and authority

`.github/workflows/release.yml` runs on `main` pushes or manual dispatch, but its write-capable job is disabled unless repository variable `RELEASE_PLEASE_ENABLED` is exactly `true`. Manual dispatch from another branch cannot run that job. The workflow checks out the exact triggering SHA without persisted credentials, runs the read-only metadata check with `--require-baseline-tag`, then invokes the SHA-pinned Release Please action. Concurrency serializes proposals without cancelling an active proposal.

The baseline guard allows an empty tracking manifest for the first proposal. Once a release PR has merged, it requires that tracking version's `vX.Y.Z` tag to exist, be reachable from the checked-out revision, and contain matching canonical metadata before another proposal may run. This prevents repeatedly bumping an untagged pending candidate. A tag is only a Git baseline; the checker explicitly does not assert provider publication or consumer acceptance. Ordinary PR checks omit this guard so a newly proposed version can pass before its tag exists.

Top-level permissions are read-only. Only the proposal job receives `contents: write` and `pull-requests: write`, which Release Please needs to maintain its PR branch. `skip-github-release: true` is an **action input**, so `createReleases` is never called by this workflow. It creates no release or tag, performs no merge, and runs no package publisher or deploy command. No OIDC, registry credential or signing identity is requested.

This session authorizes local configuration and validation only. Creating/pushing the initial history, setting the remote or repository variable, changing GitHub permissions/protection, opening or merging hosted PRs, creating tags/releases, publishing packages and deploying all require their own authorization. Credentials or this policy do not grant those permissions. Setting the enable variable deliberately permits release-PR automation; it still does not permit publication.

## Hosted prerequisites

1. Review and commit the intended source/configuration under separate authority. Establish the actual remote and a `main` branch; do not infer a repository owner from local directory names.
2. Protect `main` and require successful `release-metadata`, backend and frontend checks plus maintainer review. Require CI for release PRs as well as ordinary PRs.
3. Authorize GitHub Actions to create/update PRs using the scoped `GITHUB_TOKEN`, or deliberately configure a narrowly scoped GitHub App identity if repository policy requires it. With the configured token, automated PR open/update events create CI runs requiring a maintainer to select **Approve workflows to run**. Confirm actual required checks passed before merging; see GitHub's [workflow trigger rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
4. Verify the local `v0.1.0` tag, its signature and canonical metadata, then reconcile any existing remote tags/releases before enabling the workflow. Push or hosted publication requires separate authorization; never replace a conflicting version tag.
5. Only after those choices are approved, enable `RELEASE_PLEASE_ENABLED=true`. Verify the first generated PR's exact base/head, versions, locks and changelog before any merge.

No artifact upload job exists, so CI artifact retention is currently not applicable. Local migration backups remain excluded from source payloads until the operator chooses cleanup. A future authorized publisher must define its protected approval point, exact release commit/tag binding, platform/channel identity, artifact retention, checksums, consumer verification and immutable retry behavior before activation. Hosted publication is intentionally unconfigured.

## Local checks and recovery

```bash
make release-check
make check
uv lock --directory backend --check
actionlint .github/workflows/ci.yml .github/workflows/release.yml
```

`make release-check` uses only the standard library to verify the canonical version, every mirror and the selected release policy. It performs no Git or network writes. `make check` includes it. For an exact approved future version, use:

```bash
backend/.venv/bin/python scripts/check-release.py --expect-version 0.1.0
```

Do not edit the expected version into a second state file. Use the version from the reviewed release PR/tag. Validate native lock maintenance in a disposable copy: run `uv lock --check` and `npm install --package-lock-only --ignore-scripts`, then inspect for unexpected dependency changes. Run the normal application tests/build against the exact release revision, including the native integration consumer when that consumer is in the release acceptance scope.

The runtime-version consolidation backed up the prior backend configuration and API entrypoint, with hashes, under `.release-backups/20261108T210524872358Z/`. The root Makefile, CI and ignore-file originals are under `.release-backups/20261108-release-configuration/`. This is a scoped source change; current manifest/lock versions and Footage Review files were not bumped. To restore, inspect the receipts and current file diffs, copy only the named original files back, and rerun the checks. Preserve subsequent unrelated changes. New release configuration/checker files can be removed through a reviewed local diff if this policy is abandoned.

On a failed proposal, keep the release PR and inspect its state before retrying. Never retry publication blindly, retag an existing version, or recalculate a pending version from itself. After a merged release PR, the proposal-only workflow still leaves publication pending; reconcile the approved revision and actual tag/release state through `verify-release` before authorizing any publisher. Static configuration checks do not establish hosted behavior.

## Upstream version evidence

Verified on 8 November 2026: [Release Please action v5.0.0](https://github.com/googleapis/release-please-action/releases/tag/v5.0.0), pinned at `45996ed1f6d02564a971a2fa1b5860e934307cf7`, bundles Release Please 17.6.0. Its [action inputs and implementation](https://github.com/googleapis/release-please-action/tree/45996ed1f6d02564a971a2fa1b5860e934307cf7) define proposal-only execution. [Typed extra-file updaters](https://github.com/googleapis/release-please/blob/v17.6.0/docs/customizing.md), [Python strategy](https://github.com/googleapis/release-please/blob/v17.6.0/src/strategies/python.ts), and [manifest configuration](https://github.com/googleapis/release-please/blob/v17.6.0/docs/manifest-releaser.md) inform the selected layout. Checkout is pinned to the specific [v7.0.0 release](https://github.com/actions/checkout/releases/tag/v7.0.0), rather than its movable major tag. uv's [build-system behavior](https://docs.astral.sh/uv/concepts/projects/config/#build-systems) explains the source-checkout runtime version read.
