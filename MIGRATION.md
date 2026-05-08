# Migration Note: Service Account to OAuth2 User Authentication

LedgerLense has migrated from Service Account authentication to OAuth2 User Authentication for Google Drive integration. This allows the application to interact directly with your personal "My Drive".

## Major Changes
1.  **Authentication Flow**: Instead of a fixed service account, the app now uses the "Installed App Flow". The first time you interact with Drive, a browser window will open for you to log in with your Google account.
2.  **Credential Files**:
    -   `secrets/ledgerlense.json` (Service Account) is no longer used.
    -   `oauth_client.json` (OAuth Client Secret) is now required in the root directory.
    -   `secrets/token.json` (User Token) will be automatically generated after first login to persist your session.
3.  **Storage Location**: Processed PDFs will now be stored in your personal "My Drive" instead of a Shared Drive.

## Setup Instructions
1.  **Dependencies**: Ensure all requirements are installed:
    ```bash
    pip install google-api-python-client google-auth-oauthlib google-auth-httplib2 google-auth
    ```
2.  **OAuth Client**: Verify `oauth_client.json` exists in the project root.
3.  **Config**: Update your `.env` file:
    ```env
    GOOGLE_DRIVE_CREDENTIALS_PATH=./oauth_client.json
    GOOGLE_DRIVE_TOKEN_PATH=./secrets/token.json
    GOOGLE_DRIVE_ROOT_FOLDER_ID= # Leave empty for My Drive root
    ```
4.  **First Run**: Execute the sync script to authenticate:
    ```bash
    python scripts/sync_drive.py
    ```
    Follow the prompts in your browser to authorize the application.

## Troubleshooting
- **Port Error**: If `run_local_server` fails, ensure port 0 (random) is available or check your firewall.
- **Refresh Failed**: If you see "Token refresh failed", delete `secrets/token.json` and run the script again to re-authenticate.
