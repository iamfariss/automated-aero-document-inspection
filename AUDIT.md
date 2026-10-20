# Human / Qwen audit guide

## Source map
- server.py: loopback API, admin session enforcement, exports and authoritative saving.
- registry.py: SQLite registry, approval transitions, password hashing/rotation, scanner profiles and audit records.
- cases.py: bounded persistent queue, interrupted-case recovery and completed inbox markers.
- worker.py / validate_pdf.py: isolated PDF parsing, rendering and OCR work.
- core.py / ocr.ps1: Windows OCR bridge, enlarged certificate tiles, GR template and identifier findings.
- extraction.py: conservative labelled/table-column candidates with original coordinates.
- reconciliation.py: explicit quantity/unit line comparisons and ambiguity handling.
- selection.py: immutable multi-specification context and stable rule IDs.
- properties.py / review.py: per-heat comparison, evidence membership and acceptance gates.
- ui.js / review.js / governance.js: inspector/admin interfaces; edits clear candidate verification.
- tests/: 51 synthetic regression tests.
- tools/build_portable.py: reproducible Windows package with dependency licenses.

## Core invariants
1. Draft/rejected/superseded specifications cannot be newly selected. Scanner profiles revalidate IDs before each batch. Case snapshots retain their originally approved requirements.
2. Approval, rejection, withdrawal, scanner profiles and password rotation require an authenticated admin. Passwords/tokens are never written to audit records.
3. A later revision does not rewrite an existing inspection. Selected specification PDFs and hashes travel with its evidence package.
4. Candidate measurements start unverified. Unknown source pages and requirement IDs are rejected. Wrong units, unknown conditions, missing heat/source, ambiguous same-heat evidence and non-finite/inequality values cannot produce acceptance.
5. All document findings need an explicit resolution and note before acceptance. The inspector confirms applicability and coverage of every received heat.
6. Duplicate pages do not create additional measured or shipped quantities. Ambiguous shipping copies are not summed.
7. Every save recomputes comparisons on the server; client result labels are ignored.
8. Uploaded text is data. No OCR text is executed or sent to an instruction-following model.
9. Jobs are bounded, isolated, persisted and never marked accepted merely because processing finished. Interrupted work is marked as an error.
10. Customer documents, specifications, credentials and results are excluded from Git and build inputs.

## Deliberate limits / residual risks
- OCR can miss decimal points and column headings. Coordinates and source excerpts support human verification; they are not proof of correctness. Confidence labels are not calibrated probabilities.
- Heat/part applicability and completeness remain inspector responsibilities. Profiles choose an admin-controlled set of specifications; they do not independently interpret engineering drawing applicability.
- The pilot has one admin account and recorded inspector names. It does not provide authenticated per-inspector identity or enterprise access control.
- SQLite and review history are governed through the application but can be changed by a Windows account with filesystem write access. PDF hashes detect source changes, not all database/audit modification.
- An inspection keeps its approved snapshot even after a later registry revision. Organisational procedures must decide whether older open cases need reinspection after a revision/withdrawal.
- Completed markers must be created last. Changing source files after a marker is submitted does not silently change the retained case; resubmit a new completed batch.
- Local HTTP uses loopback with Host/Origin checks. There is no remote service, TLS or telemetry. A compromised local Windows account remains outside the application trust boundary.
- Source PDFs are processed in timed child processes. A very large evidence ZIP can still consume local memory/disk; use controlled batch sizes and backups.
- Source metadata labels and rule bounds must be checked by the admin; uploading a PDF does not automatically turn all of its clauses into trusted executable rules.

## Audit prompt
Review for false acceptance, unauthorised specification activation, incorrect rule/heat association, lost historical evidence, duplicate quantity counting, restart errors and scanner profile drift. Cite concrete file/line scenarios and regression tests. Distinguish implementation defects from explicitly human-verified engineering decisions. Never infer real material limits from synthetic fixtures.
