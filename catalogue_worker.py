"""Native PDF text extraction child. Source text is data, never instructions."""
import json, sys
import pypdfium2 as pdfium

def inspect(items):
    result=[]
    for item in items:
        row={'id':item['id']}
        try:
            with pdfium.PdfDocument(item['path']) as pdf:
                if not 0<len(pdf)<=5000:
                    raise ValueError('Unsupported PDF page count')
                texts=[]
                for index in range(min(3,len(pdf))):
                    page=pdf[index]
                    textpage=page.get_textpage()
                    text=textpage.get_text_range()[:16000]
                    texts.append('Page '+str(index+1)+'\n'+text)
                    textpage.close();page.close()
                native='\n\n'.join(texts)
                meaningful=sum(c.isalnum() for t in texts for c in t)-sum(len('Page '+str(i+1)) for i in range(len(texts)))
                row.update(pages=len(pdf),indexed_pages=len(texts),text=native,
                    status='Native text indexed — unreviewed' if meaningful>=80 else 'Scanned / sparse text — needs OCR',
                    detail='Partial index: first three pages only; confirm document identity, revision and applicability manually.')
        except Exception as error:
            row.update(status='PDF indexing error',detail=str(error)[:300])
        result.append(row)
    return result

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(inspect(json.load(sys.stdin)),ensure_ascii=True))
