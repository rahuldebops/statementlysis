"""Test SBI savings parser on the real sample."""
import sys
sys.path.insert(0, ".")

from pathlib import Path
from app.extraction.pdf_engine import PDFEngine
from app.extraction.line_builder import LineBuilder
from app.extraction.bank_detector import BankDetector
from app.parsers.sbi.parser import SBIParser
from app.parsers.base import ParserConfig

# Use the SBI savings statement
pdf_path = Path("samples/54XXXXX477_01-03-2026_16-04-2026.pdf")

engine = PDFEngine()
lb = LineBuilder()

pages = engine.extract(pdf_path)
pages = lb.build_all_pages(pages)

print(f"Pages: {len(pages)}, Total lines: {sum(len(p.lines) for p in pages)}")

# Find the table header line on each page
for p in pages:
    for line in p.lines:
        tl = line.text.lower()
        if "date" in tl and ("debit" in tl or "credit" in tl or "balance" in tl):
            print(f"\nPotential header (page {p.page_number}, line {line.line_number}):")
            print(f"  Text: {line.text[:150]}")
            print(f"  Token positions:")
            for t in line.tokens:
                print(f"    '{t.text}' x0={t.x0:.1f} x1={t.x1:.1f}")

# Parse with SBI parser
config = ParserConfig.from_file(Path("app/parsers/sbi/config.json"))
parser = SBIParser(config)
transactions = parser.parse(pages)

print(f"\nTransactions extracted: {len(transactions)}")
for txn in transactions[:10]:
    print(f"  #{txn.sequence}: date={txn.txn_date}, desc={txn.description[:60]}, "
          f"debit={txn.debit}, credit={txn.credit}, balance={txn.balance}")

if len(transactions) > 10:
    print(f"  ... and {len(transactions) - 10} more")
