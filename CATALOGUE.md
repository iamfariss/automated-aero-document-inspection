# Local specification reference catalogue

Import a local ZIP on the offline Windows PC:

```
python tools/import_catalogue.py path/to/specifications.zip
```

An optional second argument selects the catalogue directory. The default is
data/catalogue beside the source app. For a portable installation, run `runtime\python.exe import_catalogue.py path/to/specifications.zip` from the installation folder.
The import does not need a language model or network access.

PDFs are stored under their SHA-256, with original archive/member provenance in
a local SQLite catalogue. Exact PDF duplicates share stored bytes. Reimporting
the same ZIP resumes/skips existing rows; it does not create duplicate entries.
Other formats are inventoried and hashed, not opened, converted or executed.
Nested ZIPs are inventory only. The original ZIP remains unchanged.

Search covers filenames, family folders and at most the first three native-text
PDF pages. It is a partial discovery index, not a complete clause search. Sparse
or image-only pages are marked as needing OCR. PDF indexing runs in child batches
of 20 with a 30-second timeout; errors remain visible in the inventory. Filenames,
document dates, archive timestamps and search matches do not prove an approved
revision or engineering applicability. No current revision is selected for you.

In the administration page, search the local reference catalogue, open a source,
and select it for a draft. Fill in the verified code, revision, title, effective
date, applicability and numerical requirements. Submission from the catalogue
requires admin access and always creates a Draft. Approval remains a separate
controlled step. A source is checksummed before use. Draft import is limited to
validated PDFs up to 30 MB and 300 pages, consistent with manual specification
uploads. Larger references can be viewed but need a controlled import approach.

Archive limits: 20,000 files, 5 GB declared expanded data, 200 MB per member;
encrypted members, duplicate names and unsafe paths are rejected. PDF text and
all embedded document instructions are untrusted reference data.

Back up data/catalogue with the rest of the app's data, with the server stopped.
Never commit the catalogue, PDFs, inventory reports or document text to a public
repository. The portable software ZIP deliberately excludes imported libraries.
