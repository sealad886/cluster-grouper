# DPIA-lite

## Project and purpose

Cluster Grouper assists a local operator in reviewing detections already exported from Footage Review. It computes local face-similarity suggestions, lets the operator correct them, and returns explicitly reviewed groups. It does not scan source footage or make an automated downstream decision about an individual.

## Data subjects and categories

People appearing in exported footage are data subjects; the operator may also enter a reviewer name. Data includes face crops, clip metadata, detection IDs, group names/notes, facial embeddings, and import history. Embeddings used for identification can be biometric data; treat all local review state as sensitive.

## Applicability and lawful basis

No lawful basis is assumed or preselected by the software. Before using real footage, the operator assesses the actual context, Article 6 basis, possible Article 9 condition, and any applicable household limitation or other law. This record does not determine that personal use, local execution, or human review makes processing lawful. Refer to the [GDPR primary text](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng).

## Data flow

Footage Review exports metadata/crops over authenticated loopback HTTP. Cluster Grouper stores them locally, computes embeddings locally, and saves review decisions locally. Only an explicit import sends selected group names, notes, and original appearance IDs back to Footage Review. Model installation retrieves weights; ordinary inference has no external model provider. Sharing a download, backup, or state directory is a separate operator action.

## Risks and mitigations

| Risk to people | Mitigation / remaining action |
|---|---|
| Incorrect association of appearances | Treat suggestions as candidates; inspect groups; no automatic submission or identity-confidence claim. |
| Unexpected secondary use | Keep processing purpose narrow, filter exports, and document any new purpose. |
| Disclosure of images, relationships, or notes | Local-only operation, memory-only token, protected routes; operator controls account, disk, backup, and sharing. |
| Excessive retention | Choose a review-specific retention period and apply it to state, downloads, backups, and source records. |
| Inability to correct source records | Use original IDs and reviewed imports; coordinate corrections with Footage Review. |

## Retention and deletion

The MVP does not enforce a universal retention period or automatically erase drafts. The operator records an appropriate period and follows the [runbook](runbook.md). Stop the services before backing up or retiring the state directory. Deleting local review data does not delete Footage Review's library or browser downloads. Protect backups and apply the same retention decision to them.

## Rights and transparency

The operator provides any required notice and handles access, correction, restriction, objection, portability, and erasure requests across both tools. Names and notes should contain only review information needed for the purpose. Downloaded payloads expose group labels and original IDs and must be shared deliberately.

## Formal DPIA decision

This preliminary assessment does not clear deployment. The operator must determine whether the intended processing is likely to present high risk and whether a formal DPIA, specialist review, or consultation is required. Broad surveillance, sensitive populations, systematic identification, or a changed deployment require reassessment. No legal or compliance acceptance has been recorded in this repository.
