# LedgerLense

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
# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows PowerShell

# 2. Install dependencies
pip install -r requirements.txt

# 3. Environment Configuration
# Copy .env.example to .env and configure your database
# Choose between 'local' or 'neon' using DB_TYPE
cp .env.example .env

# 4. Fresh Database Initialization
# This will drop all tables and create them fresh in the 'public' schema
python scripts/run_migration.py

# 5. Start the server (Production/Neon)
$env:APP_ENV="prod"; uvicorn app.main:app --reload

# OR Start the server (Local)
$env:APP_ENV="local"; uvicorn app.main:app --reload
```

### Database & Environment Configuration

LedgerLense supports separate environment files. You can switch between them using the `APP_ENV` variable:

- **Local Development**: Uses `.env` + `.env.local`
  ```bash
  $env:APP_ENV="local"; uvicorn app.main:app --reload
  ```
- **Production/Neon**: Uses `.env` + `.env.prod`
  ```bash
  $env:APP_ENV="prod"; uvicorn app.main:app --reload
  ```

> [!TIP]
> On Windows PowerShell, use `$env:APP_ENV="prod"` before running commands. On Linux/Mac, use `APP_ENV=prod uvicorn ...`.

### Usage Examples

1. **Initializing a Fresh Database**:
   ```bash
   # Initialize local DB
   $env:APP_ENV="local"; python scripts/run_migration.py
   
   # Initialize production DB
   $env:APP_ENV="prod"; python scripts/run_migration.py
   ```

2. **Uploading Statements**:
   - Open `http://localhost:8000`.
   - Drag and drop your bank PDF (e.g., Kotak, HDFC, SBI).
   - The system will detect the bank and extract transactions.
   - Files are automatically archived to Google Drive in the `/statements/` folder.

3. **Verifying Detection**:
   - If a bank is misidentified, check the terminal logs.
   - Detection relies on keywords like "KOTAK MAHINDRA" or "IFSC: KKBK" in the first 3 pages.

### API

- `POST /api/v1/documents/extract` — Upload PDF and extract transactions
- `GET /api/v1/documents` — List uploaded documents
- `GET /api/v1/documents/{id}/transactions` — Get transactions for a document
- `POST /api/v1/transactions/confirm` — Submit corrections
- `POST /api/v1/models/retrain` — Trigger retraining (placeholder)

## Google Drive Archival Setup

LedgerLense automatically archives processed PDFs to Google Drive.

1.  **Service Account**: Place your Google Service Account JSON file in `secrets/ledgerlense.json`.
2.  **Shared Folder**: Create a folder in Google Drive and share it with the service account email as **Editor**.
3.  **Environment Variables**: Update `.env` with:
    - `GOOGLE_DRIVE_CREDENTIALS_PATH=./secrets/ledgerlense.json`
    - `GOOGLE_DRIVE_ROOT_FOLDER_ID=your_folder_id_here`

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
