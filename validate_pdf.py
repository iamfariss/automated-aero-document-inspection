"""Parse a specification PDF in a child process before storing its draft."""
import sys
import pypdfium2 as pdfium
if __name__ == '__main__':
    try:
        with pdfium.PdfDocument(sys.argv[1]) as document:
            if not 1 <= len(document) <= 300:
                raise ValueError('Specification must have 1 to 300 pages')
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
