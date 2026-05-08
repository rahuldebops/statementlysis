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

#### 1. Create and Activate Virtual Environment

**Bash (Git Bash, macOS, Linux):**
```bash
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
# OR source venv/bin/activate # macOS/Linux
```

**PowerShell:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 3. Environment Configuration
```bash
# Copy .env.example to .env and configure your database
cp .env.example .env                # Bash
Copy-Item .env.example .env         # PowerShell
```

#### 4. Database Initialization
```bash
# Bash
APP_ENV=local python scripts/run_migration.py

# PowerShell
$env:APP_ENV="local"; python scripts/run_migration.py
```

#### 5. Google Drive Sync (Optional)
To download initial statements and sync your local files to Drive:
```bash
# Bash
APP_ENV=local python scripts/sync_drive.py

# PowerShell
$env:APP_ENV="local"; python scripts/sync_drive.py
```

#### 6. Start the Server
```bash
# Bash
APP_ENV=local uvicorn app.main:app --reload

# PowerShell
$env:APP_ENV="local"; uvicorn app.main:app --reload
```

### Database & Environment Configuration

LedgerLense supports separate environment files. You can switch between them using the `APP_ENV` variable:

- **Local Development**: Uses `.env` + `.env.local`
- **Production/Neon**: Uses `.env` + `.env.prod`

**Setting Environment Variables:**
- **Bash**: `APP_ENV=prod python ...` (prefixing the command)
- **PowerShell**: `$env:APP_ENV="prod"; python ...` (using a semicolon)

### Usage Examples

1. **Initializing a Fresh Database**:
   ```bash
   # Bash
   APP_ENV=local python scripts/run_migration.py
   
   # PowerShell
   $env:APP_ENV="local"; python scripts/run_migration.py
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

LedgerLense automatically archives processed PDFs to your personal Google Drive.

1.  **OAuth Credentials**: Ensure `oauth_client.json` is in the project root.
2.  **First Run**: The first time you run the sync script or upload a file, a browser window will open for authentication.
3.  **Persistance**: Authentication is saved to `secrets/token.json` and will auto-refresh.
4.  **Environment Variables**: Update `.env` with:
    - `GOOGLE_DRIVE_CREDENTIALS_PATH=./oauth_client.json`
    - `GOOGLE_DRIVE_TOKEN_PATH=./secrets/token.json`
    - `GOOGLE_DRIVE_ROOT_FOLDER_ID=` (leave empty to use 'My Drive' root)

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
