"""Run offline: python tools/import_catalogue.py path/to/specifications.zip"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from import_catalogue import main

if __name__=='__main__':
    main()
