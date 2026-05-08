import os
import sys
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.google_drive_service import GoogleDriveService
from app.config import settings

def sync():
    """
    Sync logic for Google Drive (OAuth2 User Auth).
    1. Downloads from Drive/statements -> ./statements/
    2. Uploads ./samples/ -> Drive/samples
    3. Uploads ./storage/pdfs/ -> Drive/storage/pdfs
    """
    drive_service = GoogleDriveService()
    
    # We use My Drive root or the configured folder ID
    ROOT_ID = settings.GOOGLE_DRIVE_ROOT_FOLDER_ID or 'root'
    
    print(f"--- Starting Google Drive Sync (User Auth) ---", flush=True)
    
    # 1. Download from Drive/statements
    try:
        root_items = drive_service.list_files(ROOT_ID)
        drive_statements_folder = next((f for f in root_items if f['name'] == 'statements' and f['mimeType'] == 'application/vnd.google-apps.folder'), None)
        
        if drive_statements_folder:
            print(f"Syncing 'statements' from Drive...", flush=True)
            local_statements_dir = Path("./statements")
            local_statements_dir.mkdir(exist_ok=True)
            
            drive_files = drive_service.list_files(drive_statements_folder['id'])
            for f in drive_files:
                if f['mimeType'] != 'application/vnd.google-apps.folder':
                    local_path = local_statements_dir / f['name']
                    if not local_path.exists():
                        print(f" - Downloading {f['name']}...", flush=True)
                        drive_service.download_file(f['id'], local_path)
        else:
            print("Note: 'statements' folder not found in Drive root. Skipping download.", flush=True)
    except Exception as e:
        print(f"Error during download sync: {e}", flush=True)

    # 2. Upload to Drive
    print("\n--- Uploading local files to Drive ---", flush=True)
    try:
        # Create folder structure
        drive_samples_id = drive_service.get_or_create_folder("samples", ROOT_ID)
        drive_storage_id = drive_service.get_or_create_folder("storage", ROOT_ID)
        drive_pdfs_id = drive_service.get_or_create_folder("pdfs", drive_storage_id)
        
        # Sync samples
        local_samples = Path("./samples")
        if local_samples.exists():
            for pdf in local_samples.glob("*.pdf"):
                print(f"Uploading {pdf.name} to samples...", flush=True)
                drive_service.upload_file(pdf, drive_samples_id, pdf.name, retries=1)
                
        # Sync storage
        local_storage_pdfs = Path("./storage/pdfs")
        if local_storage_pdfs.exists():
            for pdf in local_storage_pdfs.rglob("*.pdf"):
                print(f"Uploading {pdf.name} to storage/pdfs...", flush=True)
                drive_service.upload_file(pdf, drive_pdfs_id, pdf.name, retries=1)
                
    except Exception as e:
        print(f"Error during upload sync: {e}", flush=True)

    print("\nSync complete.", flush=True)

if __name__ == "__main__":
    sync()
