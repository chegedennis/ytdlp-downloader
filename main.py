"""
main.py

A PyQt5 application for downloading YouTube videos and audio using yt-dlp. This application allows users to select video formats, track download progress, and manage completed downloads.

Modules:
    os
    sys
    time
    re
    subprocess
    yt_dlp
    datetime.timedelta
    PyQt5.QtCore (QTimer, QThread, pyqtSignal, QObject, QUrl, Qt)
    PyQt5.QtWidgets (QApplication, QMainWindow, QMessageBox, QCheckBox, QLabel, QPushButton, QFileDialog, QTableWidgetItem)
    PyQt5.uic (loadUi)
    db_functions (create_database_or_database_table)

Classes:
    DownloadWorker
    MainWindow

Functions:
    create_db_dir
    parse_formats
"""

import os
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject, QUrl
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QCheckBox,
    QLabel,
    QPushButton,
    QFileDialog,
    QTableWidgetItem,
)
import sys
import time
import yt_dlp
import subprocess
import re
from PyQt5.QtCore import Qt
from PyQt5.uic import loadUi
from datetime import timedelta

from db_functions import create_database_or_database_table


def create_db_dir():
    """
    Create a directory for storing database files if it doesn't exist.
    """
    os.makedirs(".dbs", exist_ok=True)


class DownloadWorker(QThread):
    """
    Worker thread to handle video/audio downloads using yt-dlp.

    Attributes:
        progress (pyqtSignal): Signal emitted to indicate download progress.
        finished (pyqtSignal): Signal emitted when the download is finished.
        error (pyqtSignal): Signal emitted when an error occurs during download.

    Methods:
        __init__(self, url, ydl_opts): Initializes the DownloadWorker with a URL and yt-dlp options.
        run(self): Executes the download process.
    """

    progress = pyqtSignal(dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, url, ydl_opts):
        """
        Initializes the DownloadWorker with a URL and yt-dlp options.

        Args:
            url (str): The URL of the video/audio to download.
            ydl_opts (dict): The options for yt-dlp.
        """
        super().__init__()
        self.url = url
        self.ydl_opts = ydl_opts

    def run(self):
        """
        Executes the download process using yt-dlp.
        """
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                ydl.add_progress_hook(self.progress.emit)
                ydl.download([self.url])
                self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


def parse_formats(output):
    """
    Parses the output of yt-dlp to extract available formats.

    Args:
        output (str): The output from yt-dlp containing format information.

    Returns:
        dict: A dictionary with available audio and video formats.
    """
    lines = output.splitlines()
    formats = {"audio": None, "video": []}

    def resolution_to_label(resolution):
        width, height = map(int, resolution.split("x"))
        if height >= 2160:
            return "4K"
        elif height >= 1440:
            return "2K"
        elif height >= 1080:
            return "1080p"
        elif height >= 720:
            return "720p"
        elif height >= 480:
            return "480p"
        else:
            return "Low Resolution"

    for line in lines:
        video_match = re.match(r"^(\d+)\s+\w+\s+(\d+x\d+)", line)
        if video_match:
            format_code = video_match.group(1)
            resolution = video_match.group(2)
            label = resolution_to_label(resolution)
            formats["video"].append(f"{format_code}: {label}")

        audio_match = re.match(r"^(\d+)\s+\w+\s+audio only", line)
        if audio_match:
            format_code = audio_match.group(1)
            formats["audio"] = f"{format_code}: Audio Only"

    return formats


class MainWindow(QMainWindow):
    """
    Main window of the application.

    Attributes:
        selectionType (str): The type of selection (audio or video format).
        status (str): The current status of the download.
        eta (int): The estimated time remaining for the download.
        transfer_rate (float): The current transfer rate of the download.
        downloaded_bytes (int): The number of bytes downloaded.
        file_size (int): The total size of the file being downloaded.
        url (str): The URL of the video/audio to download.
        download_data (dict): Dictionary to store download progress data.
        download_thread (DownloadWorker): The worker thread handling the download.
        download_folder (str): The folder where the downloaded files will be saved.

    Methods:
        __init__(self): Initializes the main window.
        clear_input(self): Clears the input fields and reset labels.
        get_formats(self): Retrieves available formats for the provided URL.
        populate_combo_box(self, formats): Populates the combo box with available formats.
        start_download(self): Starts the download process.
        progress_hook(self, d): Handles download progress updates.
        update_progress(self): Updates the progress bar and labels with the download status.
        update_table(self): Updates the table with download details.
        comboChanged(self): Handles changes in the combo box selection.
        on_download_finished(self): Handles the completion of the download process.
        on_download_error(self, error): Handles errors during the download process.
        select_download_folder(self): Allows the user to select a download folder.
        open_download_folder(self): Opens the selected download folder in the file explorer.
    """

    def __init__(self):
        """
        Initializes the main window.
        """
        super(MainWindow, self).__init__()
        self.selectionType = None
        self.status = None
        self.eta = None
        self.transfer_rate = None
        self.downloaded_bytes = None
        self.file_size = None
        self.url = None
        loadUi("tube.ui", self)

        create_db_dir()
        create_database_or_database_table("completed_downloads")

        self.last_update_time = time.time()
        self.update_interval = 0.5

        self.download_data = {}

        self.update_timer = QTimer()
        self.update_timer.setInterval(int(self.update_interval * 1000))
        self.update_timer.timeout.connect(self.update_progress)
        self.update_timer.start()

        self.pushButton.clicked.connect(self.get_formats)
        self.comboBox.currentIndexChanged.connect(self.comboChanged)
        self.downloadButton.clicked.connect(self.start_download)
        self.clearButton.clicked.connect(self.clear_input)
        self.playlistCheckBox = self.findChild(QCheckBox, "playlistCheckBox")

        self.download_thread = None
        self.download_folder = None

        self.fileNameLabel = self.findChild(QLabel, "fileNameLabel")
        self.downloadFolderButton = self.findChild(QPushButton, "downloadFolderButton")
        self.downloadFolderButton.clicked.connect(self.select_download_folder)

    def clear_input(self):
        """
        Clears the input fields and resets labels.
        """
        self.lineEdit.clear()
        self.comboBox.clear()
        self.progressBar.setValue(0)
        self.downloadedLabel.setText("Downloaded")
        self.fileSizeLabel.setText("File Size")
        self.fileNameLabel.setText("File Name")

    def get_formats(self):
        """
        Retrieves available formats for the provided URL.
        """
        self.url = self.lineEdit.text().strip()

        if not self.url:
            QMessageBox.warning(self, "Input Error", "Please enter a valid URL.")
            return

        self.pushButton.setEnabled(False)

        # Prepare yt-dlp command with playlist options
        command = ["yt-dlp", self.url, "-F"]

        # Add --lazy-playlist option if playlist checkbox is checked
        if self.playlistCheckBox.isChecked():
            command.append("--lazy-playlist")

        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            output = result.stdout
            formats = parse_formats(output)
            self.populate_combo_box(formats)
        except subprocess.CalledProcessError as e:
            output = f"An error occurred: {e.stderr}"
            QMessageBox.critical(self, "Error", output)
        finally:
            self.pushButton.setEnabled(True)

    def populate_combo_box(self, formats):
        """
        Populates the combo box with available formats.

        Args:
            formats (dict): Dictionary containing available audio and video formats.
        """
        self.comboBox.clear()
        self.comboBox.addItem("Select Format")
        self.comboBox.setItemData(0, Qt.AlignCenter, Qt.TextAlignmentRole)
        self.comboBox.setItemData(0, False, Qt.UserRole - 1)
        if formats["audio"]:
            self.comboBox.addItem(formats["audio"])

        sorted_videos = sorted(
            formats["video"], key=lambda x: x.split(":")[1], reverse=True
        )
        for video in sorted_videos:
            self.comboBox.addItem(video)

    def start_download(self):
        """
        Starts the download process.
        """
        url = self.lineEdit.text().strip()
        if not url:
            QMessageBox.warning(self, "URL Error", "Please enter a valid URL.")
            return

        if not hasattr(self, "selectionType") or self.selectionType == "unknown":
            QMessageBox.warning(
                self, "Selection Error", "Please select a valid format."
            )
            return

        download_playlist = self.playlistCheckBox.isChecked()

        # Define options for yt-dlp based on selection type
        ydl_opts = {
            "format": "",  # Default value, will be set based on selection type
            "outtmpl": "%(title)s.%(ext)s",  # Output filename template
            "progress_hooks": [self.progress_hook],  # Add progress hook
        }

        if download_playlist:
            ydl_opts["noplaylist"] = False  # Include playlists if checkbox is checked
        else:
            ydl_opts["noplaylist"] = True  # Exclude playlists otherwise

        # Set format options based on the selected format type
        if self.selectionType == "audio":
            ydl_opts["format"] = "bestaudio/best"  # Download the best audio format
        elif self.selectionType == "video720p":
            ydl_opts["format"] = (
                "bestvideo[height<=720]+bestaudio"  # Best video up to 720p with audio
            )
        elif self.selectionType == "video1080p":
            ydl_opts["format"] = (
                "bestvideo[height=1080]+bestaudio"  # Best video at 1080p with audio
            )
        elif self.selectionType == "video1440p":
            ydl_opts["format"] = (
                "bestvideo[height=1440]+bestaudio"  # Best video at 1440p with audio
            )
        elif self.selectionType == "video2K":
            ydl_opts["format"] = (
                "bestvideo[height=1440]+bestaudio"  # Best video at 2K (1440p) with audio
            )
        elif self.selectionType == "video4K":
            ydl_opts["format"] = (
                "bestvideo[height=2160]+bestaudio"  # Best video at 4K (2160p) with audio
            )
        else:
            QMessageBox.warning(self, "Selection Error", "Invalid selection type.")
            return

        # Start the download operation in a separate thread
        self.download_thread = DownloadWorker(url, ydl_opts)
        self.download_thread.progress.connect(self.progress_hook)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.error.connect(self.on_download_error)
        self.download_thread.start()

    def progress_hook(self, d):
        """
        Handles download progress updates.

        Args:
            d (dict): Dictionary containing download progress data.
        """
        self.download_data = d

        if "entries" not in d:
            self.playlistCheckBox.setChecked(False)
        else:
            self.playlistCheckBox.setChecked(True)

        if "filename" in d:
            filename = d["filename"]  # Get the actual filename from the dictionary
            cleaned_filename = re.sub(r"%\([^)]+\)s", "", filename).strip()
            self.fileNameLabel.setText(f"Downloading: {cleaned_filename}")

        if d["status"] == "downloading":
            self.file_size = d.get("total_bytes", d.get("total_bytes_estimate", 0))
            self.downloaded_bytes = d.get("downloaded_bytes", 0)
            self.transfer_rate = d.get("speed", 0)
            self.eta = d.get("eta", 0)
            self.status = "Downloading"

        elif d["status"] == "finished":
            self.file_size = d.get("total_bytes", d.get("total_bytes_estimate", 0))
            self.downloaded_bytes = self.file_size
            self.transfer_rate = 0
            self.eta = 0
            self.status = "Finished"

    def update_progress(self):
        """
        Updates the progress bar and labels with the download status.
        """
        if self.download_data:
            downloaded_bytes = self.download_data.get("downloaded_bytes", 0)
            total_bytes = self.download_data.get(
                "total_bytes", self.download_data.get("total_bytes_estimate", 1)
            )
            self.downloadedLabel.setText(f"{downloaded_bytes / (1024 * 1024):.2f} MB")
            self.fileSizeLabel.setText(f"{total_bytes / (1024 * 1024):.2f} MB")
            percent = downloaded_bytes / total_bytes * 100 if total_bytes else 0
            self.progressBar.setValue(min(max(int(percent), 0), 100))

            if self.download_data.get("status") != "finished":
                self.update_table()  # Call the update_table method only if download is not finished

    def update_table(self):
        """
        Updates the table with download details.
        """
        if self.download_data:
            downloaded_bytes = self.download_data.get("downloaded_bytes", 0)
            total_bytes = self.download_data.get(
                "total_bytes", self.download_data.get("total_bytes_estimate", 1)
            )
            percent = downloaded_bytes / total_bytes * 100 if total_bytes else 0
            transfer_rate = self.download_data.get("speed", 0)

            # File size in MB
            file_size_mb = total_bytes / (1024 * 1024)
            file_size_str = f"{file_size_mb:.2f} MB"

            # Transfer rate in MB/s
            transfer_rate_mb_s = transfer_rate / (1024 * 1024)
            transfer_rate_str = f"{transfer_rate_mb_s:.2f} MB/s"

            # Download status
            if percent < 100:
                download_status = f"{percent:.2f}%"
            else:
                download_status = "Completed"

            # Time left (ETA) in seconds
            eta_seconds = self.download_data.get("eta", None)
            if eta_seconds is not None:
                time_left = str(timedelta(seconds=eta_seconds)).split(".")[
                    0
                ]  # Remove milliseconds
            else:
                time_left = "N/A"

            # Check if the filename is already in the table
            filename = self.fileNameLabel.text().replace("Downloading: ", "").strip()
            row_count = self.tableWidget.rowCount()
            row_position = -1
            for row in range(row_count):
                if self.tableWidget.item(row, 0).text() == filename:
                    row_position = row
                    break

            # If not found, add a new row
            if row_position == -1:
                row_position = self.tableWidget.rowCount()
                self.tableWidget.insertRow(row_position)

            # Set or update the row with the new values
            self.tableWidget.setItem(row_position, 0, QTableWidgetItem(filename))
            self.tableWidget.setItem(row_position, 1, QTableWidgetItem(file_size_str))
            self.tableWidget.setItem(row_position, 2, QTableWidgetItem(download_status))
            self.tableWidget.setItem(row_position, 3, QTableWidgetItem(time_left))
            self.tableWidget.setItem(
                row_position, 4, QTableWidgetItem(transfer_rate_str)
            )

    def comboChanged(self):
        """
        Handles changes in the combo box selection.
        """
        selected_text = self.comboBox.currentText()
        if selected_text:
            if "Audio Only" in selected_text:
                self.selectionType = "audio"
            elif "1440p" in selected_text or "2K" in selected_text:
                self.selectionType = "video1440p"
            elif "1080p" in selected_text:
                self.selectionType = "video1080p"
            elif "720p" in selected_text:
                self.selectionType = "video720p"
            elif "4K" in selected_text:
                self.selectionType = "video4K"
            else:
                self.selectionType = "unknown"
        else:
            self.selectionType = "unknown"

    def on_download_finished(self):
        """
        Handles the completion of the download process.
        """
        # Ensure table is updated once more for the final status
        self.update_table()
        QMessageBox.information(self, "Download Finished", "The download is complete!")

    def on_download_error(self, error):
        """
        Handles errors during the download process.

        Args:
            error (str): The error message.
        """
        QMessageBox.critical(self, "Download Error", f"An error occurred: {error}")

    def select_download_folder(self):
        """
        Allows the user to select a download folder.
        """
        try:
            savedir = QFileDialog.getExistingDirectory(self, "Select Download Folder")
            if savedir:  # Check if the user did not cancel the dialog
                os.chdir(savedir)
                dirpath = os.path.basename(os.getcwd())
                save_path = dirpath
                self.label.setText(f"Destination Folder = {save_path}")
                self.download_folder = savedir
            else:
                raise ValueError("No directory selected.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to select a directory: {e}")

    def open_download_folder(self):
        """
        Opens the selected download folder in the file explorer.
        """
        if self.download_folder:
            if sys.platform == "win32":
                os.startfile(self.download_folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.download_folder])
            else:
                subprocess.Popen(["xdg-open", self.download_folder])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
