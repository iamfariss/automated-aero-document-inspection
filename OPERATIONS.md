# Local PC handover

1. Extract the portable ZIP into a controlled writable application folder. Keep the full folder together.
2. Start the app and verify an OCR language is already installed. Prepare this before disconnecting the PC from the internet.
3. Create the administrator account. The admin must retain the password using the organisation's approved process; there is no unauthenticated reset route.
4. Upload the governing specifications and exact revisions. Transcribe requirements from their source clauses. Independently check units, alloy/grade, temper/condition and limits before approval.
5. Configure scanner profiles for the intended material/document families. Update profiles when an approved revision changes. The app does not infer engineering applicability from similar part names.
6. Configure the scanner to save one complete delivery per inbox subfolder. Have the scanning workflow write READY.json only after all PDFs are closed. A PDF still being written is not a completed batch.
7. Validate a representative set against inspectors' known results before operational use: correct documents, wrong part/PO, missing certificate, multiple heats, duplicate shipping paperwork, unreadable decimal points, limits and units.
8. Inspectors review machine findings and proposed values beside their source pages, resolve document findings with notes and verify heat coverage. They record the final decision.
9. Download and retain the case evidence package as required. Stop the application before scheduled filesystem backup. Restarting the app preserves completed cases.
10. Keep Windows accounts and application files controlled. The pilot has one admin and recorded inspector names; it does not provide enterprise SSO, legally qualified signatures or tamper-evident regulatory archives.

## Updating the software

Close the app. Back up data, cases and inbox. Extract the next portable version into a new folder and copy these three data folders into it before starting. Keep the previous version and backup for rollback. Earlier analysis-only case folders are discovered on startup and made available for review. No source documents are deleted by scanning or upgrading.

## Accuracy limits

A source-page association proves the page belongs to the case, not that the OCR number is correct. In the supplied chemistry scan, OCR could read 1.1 as 11 and miss a column heading. The app therefore does not automatically verify candidates, even when a value is inside limits. Uncertain table layouts and inequality expressions require an inspector's determination. Do not invent a value or a specification limit to clear a finding.

The supplied PDFs are examples, not the complete approved requirements library. Real specifications, current revisions and inspector-labelled examples are the remaining inputs for qualification.
