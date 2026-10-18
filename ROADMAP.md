# V1 delivery status

Implemented and tested:
- Offline Windows PDF ingestion, OCR, evidence display and original hashes.
- Governed specification PDFs, rule forms, version history and audit events.
- Admin login, password rotation, session expiry and login throttling.
- Multiple frozen approved specifications per inspection.
- Completed scanner-batch markers and admin-controlled scanner profiles.
- Isolated, bounded PDF/OCR queue with persistent cases and restart recovery.
- Labelled and table-column material candidates, always unverified initially.
- Explicit shipping-line quantity comparison without ambiguous summation.
- Per-heat numerical comparisons and document-finding acceptance gates.
- Saved reviews, source snapshots, CSV/HTML reporting and evidence ZIP export.
- 51 regression tests and Windows CI/package build.

Qualification requires user inputs: approved operational specifications and their exact revisions, engineering applicability decisions, PO/drawing clauses and inspector-labelled supplier examples. These are not replaced by synthetic test limits.

Future enterprise extensions, outside this single-PC pilot: authenticated individual inspector accounts/SSO, automatic engineering applicability mapping, calibrated supplier-specific OCR models, tamper-evident archives, qualified digital signatures and direct scanner-vendor integration.
