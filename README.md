# Automated Aero Document Inspection

Offline Windows incoming-document inspection with administrator-governed specifications and inspector review. This is a completed v1 pilot workflow; operational qualification requires your approved specifications and labelled inspection examples.

## Start

For the portable package, extract the complete ZIP and double-click **Start.cmd**. No Python installation, API key or internet connection is required at runtime. Windows 10/11 x64 and an installed Windows OCR language pack are required. The app opens at http://127.0.0.1:8765. Keep the console open while processing scans.

For source development, use Python 3.12 on Windows:

```
python -m pip install -r requirements.txt
python server.py
```

Provision the dependencies and OCR language before taking the PC offline. To prepare Python wheels on a connected Windows PC:

```
python -m pip download -r requirements.txt -d wheelhouse
python -m pip install --no-index --find-links wheelhouse -r requirements.txt
```

## Specification governance

Open Specification library & administration. Create the first admin with a password of at least 12 characters. Upload the controlled PDF, its code/revision, applicability and effective date. Enter each applicable numerical requirement using the form: property, reported unit, material condition, source clause/page, lower/upper bounds and optional supplier OCR aliases. There are no guessed operational material limits. For document-only items, explicitly uncheck the material-property requirement before submission; only admin approval makes that scope usable. Material-required specifications cannot be approved with an empty rule list.

Uploads remain Draft. Only the authenticated admin may approve, reject or withdraw a version. Approval includes a required review reason and confirms that the PDF, revision, applicability and every transcribed rule were checked. Approval supersedes the previous active revision for that code. Earlier versions, PDFs and audit records are retained. Correct a bad draft by submitting a replacement candidate; approved content is not edited in place.

Admin sessions expire after 30 minutes. Password rotation revokes all sessions. Login is limited to five failed attempts per minute. The single-PC model has one administrator; inspector identities are recorded names rather than individually authenticated accounts.

## Scan to review

For manual import, select up to eight approved specifications and the complete PDF set for one delivery. For repeated workflows, an admin may configure a named scanner profile with approved specification IDs. Scan the delivery into `inbox/<delivery-name>/`, then save **READY.json last**:

```
{"profile":"your-admin-profile"}
```

Alternatively supply `{"specification_ids":[1,2]}` using approved IDs from the register. The scanner or its local completion script must create this marker only after every PDF is finished. The app checks every five seconds. `inspection-status.json` beside the scans records the case ID or import error. The same marker is not submitted twice. After correcting an error, save the marker again. If a profile references a withdrawn/superseded revision, processing stops until the admin updates it.

The queue renders and OCRs PDFs in an isolated child process. Limits: 30 files, 100 MB decoded source data, 100 total pages, eight queued batches, one active batch, 90 seconds per OCR call and 15 minutes per batch. Dense COC/test pages receive overlapping enlarged OCR passes. Original source documents are retained and checksummed.

## Inspection behavior

- GR identifiers are extracted using the supplied GR layout. Part, PO and delivery references are compared with supporting document tokens. Other layouts or missing readings remain review findings.
- Exact rendered duplicates are flagged and excluded from supporting quantity/value candidates. Differently scanned copies may still require manual identification.
- Explicit shipping rows produce part/quantity/unit candidates. A single matching line can agree with the GR. Missing/multiple rows remain unresolved; ambiguous copies are never automatically summed.
- Material extraction locates labelled values and measured-row table columns using approved property names/aliases. It proposes values, source pages and boxes. Missing neighbouring headers, uncertain decimal points, inequality values, units and heat links require inspection. OCR confidence is not a calibrated probability.
- Inspectors choose/correct each proposed measurement and verify its unit, condition and heat linkage. Add observations for each received heat as needed. The system compares every applicable approved rule with verified evidence using inclusive decimal bounds and explicit units. It does not silently convert units or turn a supplier's printed PASS into compliance.
- Every document finding must be confirmed or marked not applicable with a note before acceptance. Material results must be within approved limits. Missing requirements, unknown evidence pages, duplicate same-heat observations, unverified values and out-of-limit results block acceptance.
- The inspector confirms applicability, completeness of heat coverage and any physical inspection/release obligations. The software does not independently prove these from OCR.

## Recovery and evidence

Completed cases and their saved reviews survive app restart. Open a saved inspection to restore values, verification, decisions and document resolutions. Interrupted queued/running cases are marked for resubmission, never accepted automatically.

Save review retains the frozen specification sources, rule versions, observations, document resolutions and server-recomputed results. Download case evidence exports original delivery PDFs, selected approved specification PDFs, hashes, OCR, page images, analysis, review history, CSV findings and an HTML report. Source PDF snapshots are preserved even if the registry later activates another revision.

Back up `data/`, `cases/` and `inbox/` with the server stopped. File access must be controlled through Windows permissions. Audit history is append-only through the application, not tamper-proof against direct filesystem/database modification. No customer scans, specifications, credentials or generated cases are committed to Git.

## Validation

```
python -m unittest discover -s tests -v
```

77 automated tests cover governance, authentication, revision retention, bounds, traceability prerequisites, candidate extraction, duplicate/missing shipping evidence, source validation, case persistence, scanner markers/profiles and acceptance gates. Tests use synthetic requirements and fixtures.

Browser validation covered completed-batch ingestion, OCR candidate prefill, source evidence, verified numerical checks, document-finding acceptance gating, saving, server restart/recovery and evidence ZIP provenance. Supplied scan pages were also inspected: small chemistry figures showed OCR decimal/header errors, so extracted values remain explicitly unverified. This is not an accuracy certification across all suppliers.

## Build

```
python tools/build_portable.py release/Aero-Inspection-Windows
```

Run this on a provisioned Windows Python installation. It creates a portable runtime and ZIP with dependency licenses. GitHub Actions runs tests and builds the same downloadable artifact. See OPERATIONS.md for deployment and AUDIT.md for human/Qwen review.

## Optional small local model

See [LOCAL_MODEL.md](LOCAL_MODEL.md) for the experimental Ollama integration, admin setup, evidence checks and correction-example capture. Model weights are installed separately; the baseline remains fully functional without them.

## Local reference library

See [CATALOGUE.md](CATALOGUE.md) for ZIP catalogue import, partial native-text search and admin-controlled promotion to draft specifications. Imported documents and indexes stay local and are excluded from software packages and Git.
