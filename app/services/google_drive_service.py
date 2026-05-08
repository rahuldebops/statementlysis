"""Google Drive Service — handles OAuth2 User authentication, folder creation, and file uploads."""

import logging
import os
import hashlib
import time
import io
from pathlib import Path
from typing import Optional, Dict, Any, List

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

from app.config import settings

logger = logging.getLogger(__name__)

class GoogleDriveService:
    """Service for interacting with Google Drive API v3 using OAuth2 User Auth."""

    def __init__(self):
        self.credentials_path = settings.GOOGLE_DRIVE_CREDENTIALS_PATH
        self.token_path = settings.GOOGLE_DRIVE_TOKEN_PATH
        self.root_folder_id = settings.GOOGLE_DRIVE_ROOT_FOLDER_ID
        self._service = None

    def _get_credentials(self):
        """Get or refresh user credentials."""
        scopes = ['https://www.googleapis.com/auth/drive']
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, scopes)
            except Exception as e:
                logger.warning(f"Failed to load token.json: {e}")
            
        # If no valid credentials, login
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Token refresh failed: {e}. Re-authenticating...")
                    creds = None
            
            if not creds:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"OAuth client secret file not found: {self.credentials_path}")
                
                print("\n" + "="*60)
                print("GOOGLE DRIVE AUTHENTICATION REQUIRED")
                print("="*60)
                print("A browser window should open automatically.")
                print("If it doesn't, please copy and paste the URL below into your browser:")
                
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, scopes)
                # We use a fixed port if you want to whitelist it, or 0 for random
                creds = flow.run_local_server(port=0, open_browser=True)
                
                print("="*60)
                print("AUTHENTICATION SUCCESSFUL")
                print("="*60 + "\n")
                
            # Save token for next time
            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
                
        return creds

    def _get_service(self):
        """Lazy initialization of the Drive service."""
        if self._service is None:
            creds = self._get_credentials()
            self._service = build('drive', 'v3', credentials=creds)
        return self._service

    def get_or_create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> str:
        """Find or create a folder in My Drive."""
        service = self._get_service()
        parent_id = parent_id or self.root_folder_id or 'root'

        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed = false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])

        if files:
            return files[0]['id']

        # Create folder if not found
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id] if parent_id != 'root' else []
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        logger.info(f"Created folder: {folder_name} (ID: {folder['id']})")
        return folder['id']

    def upload_file(
        self,
        file_path: Path,
        folder_id: str,
        filename: str,
        mimetype: str = 'application/pdf',
        retries: int = 3
    ) -> Dict[str, Any]:
        """Upload a file to Google Drive with retry logic."""
        service = self._get_service()

        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        media = MediaFileUpload(str(file_path), mimetype=mimetype, resumable=True)

        last_error = None
        for attempt in range(retries):
            try:
                file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink'
                ).execute()
                
                logger.info(f"Successfully uploaded {filename} to Drive (ID: {file['id']})")
                return {
                    "drive_file_id": file['id'],
                    "web_view_link": file['webViewLink'],
                    "status": "success"
                }
            except HttpError as e:
                last_error = e
                logger.warning(f"Upload attempt {attempt + 1} failed for {filename}: {e}")
                time.sleep(2 ** attempt)

        logger.error(f"Failed to upload {filename} after {retries} attempts: {last_error}")
        return {
            "drive_file_id": None,
            "web_view_link": None,
            "status": "failed",
            "error": str(last_error)
        }

    def list_files(self, folder_id: str) -> List[Dict[str, Any]]:
        """List files in a specific folder."""
        service = self._get_service()
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields='files(id, name, mimeType)').execute()
        return results.get('files', [])

    def download_file(self, file_id: str, local_path: Path):
        """Download a file from Google Drive."""
        service = self._get_service()
        try:
            request = service.files().get_media(fileId=file_id)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            with io.FileIO(str(local_path), 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    if status:
                        logger.debug(f"Download {int(status.progress() * 100)}%.")
            
            logger.info(f"Successfully downloaded file to {local_path}")
        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            raise

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
