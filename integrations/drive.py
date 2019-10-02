__author__ = "Wren J. R. (uberfastman)"
__email__ = "wrenjr@yahoo.com"
# code snippets taken from: http://stackoverflow.com/questions/24419188/automating-pydrive-verification-process

import datetime
import logging
import os
from configparser import ConfigParser

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.INFO)

# Suppress verbose googleapiclient info/warning logging
logging.getLogger("googleapiclient").setLevel(level=logging.ERROR)
logging.getLogger("googleapiclient.discovery").setLevel(level=logging.ERROR)
logging.getLogger("googleapiclient.discovery_cache").setLevel(level=logging.ERROR)
logging.getLogger("googleapiclient.discovery_cache.file_cache").setLevel(level=logging.ERROR)


class GoogleDriveUploader(object):
    def __init__(self, filename, config):

        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.filename = os.path.join(project_dir, filename)
        self.config = config
        self.gauth = GoogleAuth()

        auth_token = os.path.join(project_dir, self.config.get("Drive", "google_auth_token"))

        # Try to load saved client credentials
        self.gauth.LoadCredentialsFile(auth_token)
        if self.gauth.credentials is None:
            # Authenticate if they're not there
            self.gauth.LocalWebserverAuth()
        elif self.gauth.access_token_expired:
            # Refresh them if expired
            self.gauth.Refresh()
        else:
            # Initialize the saved creds
            self.gauth.Authorize()
        # Save the current credentials to a file
        self.gauth.SaveCredentialsFile(auth_token)

    def upload_file(self, test=False):

        # Create GoogleDrive instance with authenticated GoogleAuth instance.
        drive = GoogleDrive(self.gauth)

        # Get lists of folders
        root_folders = drive.ListFile(
            {"q": "'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"}).GetList()
        all_folders = drive.ListFile({"q": "mimeType='application/vnd.google-apps.folder' and trashed=false"}).GetList()
        all_pdfs = drive.ListFile({"q": "mimeType='application/pdf' and trashed=false"}).GetList()

        # Check for "Fantasy_Football" root folder and create it if it does not exist
        google_drive_root_folder_name = self.config.get("Drive", "google_drive_root_folder_name")
        google_drive_root_folder_id = self.make_root_folder(
            drive,
            self.check_file_existence(google_drive_root_folder_name, root_folders),
            google_drive_root_folder_name)

        if not test:
            # Check for parent folder for league and create it if it does not exist
            league_folder_name = self.filename.split("/")[2].replace("-", "_")
            league_folder_id = self.make_parent_folder(drive,
                                                       self.check_file_existence(league_folder_name, all_folders),
                                                       league_folder_name, google_drive_root_folder_id)

            # Check for league report and create if if it does not exist
            report_file_name = self.filename.split("/")[-1]
            report_file = self.check_file_existence(report_file_name, all_pdfs)
        else:
            report_file_name = self.filename
            report_file = self.check_file_existence(report_file_name, all_pdfs)
            league_folder_id = "root"

        if report_file:
            report_file.Delete()
        upload_file = drive.CreateFile({'title': report_file_name, 'mimeType': 'application/pdf',
                                        "parents": [{"kind": "drive#fileLink", "id": league_folder_id}]})
        upload_file.SetContentFile(self.filename)

        # Upload the file.
        upload_file.Upload()

        upload_file.InsertPermission(
            {
                'type': 'anyone',
                'role': 'reader',
                'withLink': True
            }
        )

        return "\nFantasy Football Report\nGenerated %s\n*%s*\n\n_Google Drive Link:_\n%s" % (
            "{:%Y-%b-%d %H:%M:%S}".format(datetime.datetime.now()), upload_file['title'], upload_file["alternateLink"])

    @staticmethod
    def check_file_existence(file_name, file_list):
        drive_file_name = file_name
        google_drive_file = None

        for drive_file in file_list:
            if drive_file["title"] == drive_file_name:
                google_drive_file = drive_file

        return google_drive_file

    @staticmethod
    def make_root_folder(drive, folder, folder_name):
        if not folder:
            new_root_folder = drive.CreateFile(
                {"title": folder_name, "parents": [{"kind": "drive#fileLink", "isRoot": True}],
                 "mimeType": "application/vnd.google-apps.folder"})
            new_root_folder.Upload()
            root_folder_id = new_root_folder["id"]
        else:
            root_folder_id = folder["id"]

        return root_folder_id

    @staticmethod
    def make_parent_folder(drive, folder, folder_name, root_folder_id):
        if not folder:
            new_parent_folder = drive.CreateFile(
                {"title": folder_name, "parents": [{"kind": "drive#fileLink", "id": root_folder_id}],
                 "mimeType": "application/vnd.google-apps.folder"})
            new_parent_folder.Upload()
            parent_folder_id = new_parent_folder["id"]
        else:
            parent_folder_id = folder["id"]

        return parent_folder_id


if __name__ == '__main__':
    local_config = ConfigParser()
    local_config.read("config.ini")
    local_config.read(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.ini"))
    reupload_file = local_config.get("Drive", "reupload_file")

    google_drive_uploader = GoogleDriveUploader(reupload_file, local_config)
    upload_message = google_drive_uploader.upload_file()
    print(upload_message)
