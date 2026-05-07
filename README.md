# Statementlysis

**AI/ML-ready bank statement extraction platform for Indian banks.**

## Features

- **PDF → Transactions**: Upload bank statement PDFs, get structured transaction data
- **Multi-bank support**: HDFC, SBI, ICICI with generic fallback
- **Coordinate-based parsing**: Token-level extraction with bounding box coordinates
- **Editable grid UI**: Inline editing, add/delete rows, keyboard navigation
- **Training data generation**: Corrections automatically become training samples
- **ML-ready architecture**: Designed for future model integration (Phase 6)

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 14+

### Setup

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Create database
createdb statementlysis

# Copy and edit environment variables
cp .env.example .env

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Usage

1. Open `http://localhost:8000` in your browser
2. Upload a bank statement PDF
3. Review extracted transactions in the editable grid
4. Make corrections if needed
5. Click "Confirm" to save corrections as training data

### API

- `POST /api/v1/documents/extract` — Upload PDF and extract transactions
- `GET /api/v1/documents` — List uploaded documents
- `GET /api/v1/documents/{id}/transactions` — Get transactions for a document
- `POST /api/v1/transactions/confirm` — Submit corrections
- `POST /api/v1/models/retrain` — Trigger retraining (placeholder)

## Architecture

```
PDF → Token Extraction → Line Reconstruction → Bank Detection
    → Parser Selection → Transaction Reconstruction → Validation
    → Correction UI → Training Data
```

## Supported Banks

| Bank | Parser | Status |
|------|--------|--------|
| HDFC | HDFCParser v1.0.0 | Active |
| SBI  | SBIParser v1.0.0 | Active |
| ICICI | ICICIParser v1.0.0 | Active |
| Generic | GenericParser v1.0.0 | Fallback |

## License

Private — All rights reserved.
