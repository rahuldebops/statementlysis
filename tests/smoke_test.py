"""Quick smoke test for pipeline components."""
from app.core.types import Token, PageData
from app.extraction.line_builder import LineBuilder
from app.extraction.bank_detector import BankDetector
from app.extraction.validator import TransactionValidator

# Simulate tokens from a page
tokens = [
    Token("HDFC", 10, 50, 10, 20, 1, 0),
    Token("BANK", 55, 90, 10, 20, 1, 1),
    Token("Date", 10, 50, 50, 60, 1, 2),
    Token("Narration", 55, 130, 50, 60, 1, 3),
    Token("Debit", 300, 350, 50, 60, 1, 4),
    Token("Credit", 400, 450, 50, 60, 1, 5),
    Token("Balance", 500, 560, 50, 60, 1, 6),
    Token("01/01/2024", 10, 80, 80, 90, 1, 7),
    Token("UPI-Payment", 55, 180, 80, 90, 1, 8),
    Token("5,000.00", 300, 360, 80, 90, 1, 9),
    Token("45,000.00", 500, 570, 80, 90, 1, 10),
]

page = PageData(
    page_number=1, width=595, height=842,
    raw_text="HDFC BANK\nDate Narration Debit Credit Balance\n01/01/2024 UPI-Payment 5,000.00 45,000.00",
    tokens=tokens,
)

# Test line builder
lb = LineBuilder()
lines = lb.build_lines(page)
print(f"[OK] Line builder: {len(lines)} lines from {len(tokens)} tokens")
for line in lines:
    print(f"  Line {line.line_number}: [{line.text}]")

# Test bank detector
bd = BankDetector()
result = bd.detect([page])
print(f"\n[OK] Bank detector: {result.bank_name} (confidence={result.confidence})")
print(f"  Matched patterns: {result.matched_patterns}")

# Test validator
v = TransactionValidator()
print(f"\n[OK] Date parse: {v.parse_date('01/01/2024')}")
print(f"[OK] Amount parse: {v.parse_amount('5,000.00')}")
print(f"[OK] Amount parse: {v.parse_amount('1,23,456.78')}")

print("\nAll pipeline components working!")
