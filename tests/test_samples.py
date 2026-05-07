"""Test extraction on sample PDFs to identify parsing issues."""
import sys
from pathlib import Path
sys.path.insert(0, ".")

from app.extraction.pdf_engine import PDFEngine
from app.extraction.line_builder import LineBuilder
from app.extraction.bank_detector import BankDetector

SAMPLES_DIR = Path("samples")

engine = PDFEngine()
lb = LineBuilder()
bd = BankDetector()

files = sorted(SAMPLES_DIR.glob("*.pdf"))
print(f"Found {len(files)} sample PDFs\n")

for pdf_file in files:
    print(f"\n{'='*80}")
    print(f"FILE: {pdf_file.name} ({pdf_file.stat().st_size // 1024} KB)")
    print(f"{'='*80}")
    
    try:
        pages = engine.extract(pdf_file)
        pages = lb.build_all_pages(pages)
        bank = bd.detect(pages)
        
        print(f"Pages: {len(pages)}, Tokens: {sum(len(p.tokens) for p in pages)}, Lines: {sum(len(p.lines) for p in pages)}")
        print(f"Bank: {bank.bank_name} ({bank.bank_id}) conf={bank.confidence}, type={bank.statement_type.value}")
        
        # Show first 12 lines of page 1
        if pages:
            p1 = pages[0]
            print(f"Page 1 first lines:")
            for line in p1.lines[:12]:
                print(f"  L{line.line_number:3d} [y={line.y_center:6.1f}]: {line.text[:110]}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
    
    print()
