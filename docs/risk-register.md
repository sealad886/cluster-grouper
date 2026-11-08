# Risk register

| Risk | Likelihood | Impact | Mitigation | Owner | Status |
|---|---|---|---|---|---|
| False matches or missed matches in poor crops | High | High | Review every suggestion; preserve unusable crops; tune threshold; do not report a unique-person count or measured accuracy. | Operator | Open |
| Existing group members lost through a filtered review | Medium | High | Preserve full upstream membership; complete-membership import semantics; explicit edit and review. | Application + operator | Monitoring |
| Concurrent upstream edits invalidate a draft | Medium | High | Bind library/revision; reject conflict; fresh export and reconciliation without automatic rebasing. | Application + operator | Monitoring |
| Response loss causes duplicate or uncertain import | Medium | Medium | Persist immutable payload before posting; replay exact import UUID/bytes; retain uncertain status. | Application | Monitoring |
| Paused export snapshot expires | Medium | Medium | Preserve partial work as incomplete; surface 410; use a fresh export and verify reviewed IDs. | Operator | Open |
| Crop and embedding disclosure from local storage or backups | Medium | High | Private account, disk encryption, deliberate backup/sharing, documented retention. | Operator | Open |
| Local CPU/disk pressure interrupts large exports or clustering | Medium | Medium | Job counters and checkpoints; pause/cancel; inspect available storage; single process. | Operator | Open |
| Pinned model or dependency vulnerability | Medium | Medium | Hash verification, lockfiles, audit pipeline, reviewed upgrades. | Maintainer | Monitoring |
| Synthetic fixture passes but installed API differs | Medium | High | Distinguish contract tests from live acceptance; perform reviewed end-to-end check against installed Footage Review. | Operator + maintainer | Open |

This register covers the local MVP. Internet hosting, multi-user access, automatic identity decisions, and public sharing are outside its assessed deployment.
