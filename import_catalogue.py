"""Portable entry point: runtime/python.exe import_catalogue.py reference.zip"""
import json,sys
from pathlib import Path
from catalogue import Catalogue

def main():
    root=Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).resolve().parent/'data'/'catalogue'
    library=Catalogue(root)
    progress=lambda value: print(json.dumps(value),flush=True)
    progress(library.import_zip(sys.argv[1],progress))
    progress(library.index(progress))

if __name__=='__main__':
    main()
