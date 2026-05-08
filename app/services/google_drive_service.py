"""Google Drive Service — handles authentication, folder creation, and file uploads."""

import logging
import os
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from app.config import settings

logger = logging.getLogger(__name__)

class GoogleDriveService:
    """Service for interacting with Google Drive API v3."""

    def __init__(self):
        self.credentials_path = settings.GOOGLE_DRIVE_CREDENTIALS_PATH
        self.root_folder_id = settings.GOOGLE_DRIVE_ROOT_FOLDER_ID
        self._service = None

    def _get_service(self):
        """Lazy initialization of the Drive service."""
        if self._service is None:
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")

            scopes = ['https://www.googleapis.com/auth/drive.file']
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=scopes
            )
            self._service = build('drive', 'v3', credentials=creds)
        return self._service

    def get_or_create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> str:
        """Find or create a folder in Google Drive."""
        service = self._get_service()
        parent_id = parent_id or self.root_folder_id

        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed = false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])

        if files:
            return files[0]['id']

        # Create folder if not found
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        logger.info(f"Created folder: {folder_name} (ID: {folder['id']})")
        return folder['id']

    def ensure_path(self, path_parts: List[str]) -> str:
        """Ensure a directory path exists in Drive and return the last folder's ID."""
        current_parent = self.root_folder_id
        for part in path_parts:
            current_parent = self.get_or_create_folder(part, current_parent)
        return current_parent

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
                time.sleep(2 ** attempt)  # Exponential backoff

        logger.error(f"Failed to upload {filename} after {retries} attempts: {last_error}")
        return {
            "drive_file_id": None,
            "web_view_link": None,
            "status": "failed",
            "error": str(last_error)
        }

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
