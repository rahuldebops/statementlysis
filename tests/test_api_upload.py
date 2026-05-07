"""Test upload via API."""
import requests
import json

r = requests.post(
    'http://localhost:8000/api/v1/documents/extract',
    files={'file': ('54XXXXX477_01-03-2026_16-04-2026.pdf',
                     open('samples/54XXXXX477_01-03-2026_16-04-2026.pdf', 'rb'),
                     'application/pdf')}
)

print(f"Status: {r.status_code}")

if r.status_code != 200:
    print(f"Error: {r.text[:500]}")
else:
    data = r.json()
    print(f"Doc ID: {data.get('document_id')}")
    print(f"Bank: {data.get('bank_detected')}")
    print(f"Pages: {data.get('total_pages')}")
    print(f"Status: {data.get('status')}")
    print(f"Txn Count: {data.get('transaction_count')}")
    
    txns = data.get('transactions', [])
    print(f"\nFirst 10 transactions:")
    for t in txns[:10]:
        desc = t['description'][:50] if t.get('description') else ''
        print(f"  #{t['sequence']:3d}: {t.get('txn_date',''):15s} | {desc:50s} | D={t.get('debit'):>10s} C={t.get('credit'):>10s} B={t.get('balance'):>10s}"
              .replace("D=      None", "D=          ").replace("C=      None", "C=          "))
    
    if len(txns) > 10:
        print(f"  ... and {len(txns) - 10} more")
