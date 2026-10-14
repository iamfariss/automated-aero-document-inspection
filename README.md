# Offline document inspection

Reviewable Windows prototype for scanned goods receipt slips, shipping documents, certificates of conformity and material test reports. Runtime processing uses Windows OCR and a localhost server. It has no cloud inference or telemetry.

## Run

Windows 10/11 x64, Python 3.12, and a Windows OCR language pack are required. Install the pinned dependencies during provisioning, then run `python server.py`. For an isolated PC, transfer a prebuilt runtime or use a wheelhouse prepared on a connected Windows machine:

```
python -m pip download -r requirements.txt -d wheelhouse
python -m pip install --no-index --find-links wheelhouse -r requirements.txt
python server.py
```

Open http://127.0.0.1:8765. Keep the server console open. The code binds to loopback only.

## Specifications and governance

Open Specification library from the inspection screen. On the first run, create the local admin with a password of at least 12 characters. Upload a specification PDF with code, revision, effective date, applicability and uploader. Anyone with access to the local application may upload a Draft. Only the authenticated admin may approve, reject or withdraw a version. Enter a reason for each admin action. Sessions expire after 30 minutes and are invalidated on logout or server restart.

Admin approval confirms the PDF, applicability, revision and any manually entered numerical rules have been reviewed. Approval supersedes the previous approved record for the same specification code. Old records and PDFs remain in SQLite. Multiple draft candidates for the same code/revision are allowed; each gets its own ID and checksum. Submitted candidates are immutable through the application. Correct an erroneous upload by creating a new draft candidate.

Select an approved specification before inspecting a delivery. The inspection stores a metadata/rule snapshot including specification ID, revision, source hash and approval identity. Later approvals do not rewrite completed inspection records. The source PDF remains in the database. Currently one governing specification can be selected per delivery; applicability is confirmed by the inspector, not inferred by the software.

## Implementation status

Working: PDF rendering; Windows OCR; heading-based document classification; supplied GR layout identifier candidates; exact rendered-page duplicate flags; evidence display; inspector decisions; JSON/CSV outputs; local SQLite specification registry; admin approval/rejection/withdrawal; audit events; immutable inspection specification snapshot.

`properties.py` is a separately tested deterministic comparison module. It requires approved rules plus an inspector-verified measurement, source page, material condition and heat identifier. It uses inclusive Decimal comparisons and refuses implicit unit conversions. It is NOT connected to automatic OCR table extraction or the inspection UI yet. No actual specification limits are supplied in this repository.

Pending: automatic material table extraction; certificate-to-heat-to-report linkage; quantity and unit reconciliation across line items; multiple governing specifications per line item; automatic applicability selection; scanner folder ingestion; per-user accounts; robust recovery of old inspection cases in the UI; production qualification against a representative ground-truth dataset.

## Tests

```
python -m unittest discover -s tests -v
```

18 automated tests cover admin authentication, setup, logout, cross-origin rejection, approval gating, replacement, preserved snapshots, withdrawal, invalid limits, future-effective versions, altered-PDF detection and numerical boundaries. Tests use synthetic fixtures, not customer scans. Registry tests do not claim PDF semantics validation; the upload endpoint additionally validates PDFs through PDFium.

An earlier three-page customer sample passed local HTTP upload, OCR, evidence retrieval and review/CSV saving. That was performed before specification integration. Browser layout and this version's complete OCR/governance interaction still need end-to-end review.

## Data and backup

`data/specifications.sqlite3` holds specification PDFs, admin password hash and audit history. `cases/` holds scans, OCR, analysis and review records. Stop the server before copying both directories for backup. Keep these directories outside Git. The database and history are governed through the application, but are not tamper-proof against a Windows account with direct file access. Use Windows file permissions and controlled backups for an operational deployment.
