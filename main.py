"""
main.py
-------

A PyQt5 application for downloading videos and audio from YouTube using `yt-dlp`.

Modules:
    os: Provides a way of using operating system-dependent functionality.
    sys: Provides access to some variables used or maintained by the interpreter.
    time: Provides various time-related functions.
    yt_dlp: A command-line program to download videos from YouTube.com and a few more sites.
    subprocess: Allows you to spawn new processes, connect to their input/output/error pipes, and obtain their return codes.
    re: Provides regular expression matching operations.
    datetime: Supplies classes for manipulating dates and times.

Classes:
    DownloadWorker
    MainWindow

Functions:
    create_db_dir()
    parse_formats(output)
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
    Create a directory named '.dbs' if it doesn't exist.
    """
    os.makedirs(".dbs", exist_ok=True)


class DownloadWorker(QThread):
    """
    A worker thread to handle downloading videos in the background.

    Signals:
        progress (dict): Emitted with progress updates.
        finished (): Emitted when the download is finished.
        error (str): Emitted when an error occurs.

    Methods:
        __init__(url, ydl_opts): Initializes the worker with a URL and yt-dlp options.
        run(): Executes the download process.
    """

    progress = pyqtSignal(dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, url, ydl_opts):
        """
        Initialize the worker thread with the given URL and yt-dlp options.

        Args:
            url (str): The URL of the video to download.
            ydl_opts (dict): The yt-dlp options for downloading the video.
        """
        super().__init__()
        self.url = url
        self.ydl_opts = ydl_opts

    def run(self):
        """
        Run the download process and emit signals for progress, completion, and errors.
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
    Parse the format options from the yt-dlp output.

    Args:
        output (str): The output string from yt-dlp.

    Returns:
        dict: A dictionary with audio and video format options.
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
    The main window for the PyQt5 application.

    Methods:
        __init__(): Initializes the main window and sets up the UI and connections.
        clear_input(): Clears the input fields and resets the UI.
        get_formats(): Retrieves the available formats for the provided URL.
        populate_combo_box(formats): Populates the combo box with format options.
        start_download(): Starts the download process for the selected format.
        progress_hook(d): Handles the progress updates during download.
        update_progress(): Updates the progress bar and labels with download status.
        update_table(): Updates the table with download details.
        comboChanged(): Handles changes in the combo box selection.
        on_download_finished(): Handles the completion of the download process.
        on_download_error(error): Handles errors during the download process.
        select_download_folder(): Allows the user to select a download folder.
        open_download_folder(): Opens the selected download folder.
    """

    def __init__(self):
        """
        Initialize the main window, set up the UI, and connect signals.
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
        Clear the input fields and reset the UI elements.
        """
        self.lineEdit.clear()
        self.comboBox.clear()
        self.progressBar.setValue(0)
        self.downloadedLabel.setText("Downloaded")
        self.fileSizeLabel.setText("File Size")
        self.fileNameLabel.setText("File Name")

    def get_formats(self):
        """
        Retrieve the available formats for the provided URL and populate the combo box.
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
        Populate the combo box with the available format options.

        Args:
            formats (dict): The dictionary containing audio and video format options.
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
        Start the download process for the selected format and URL.
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
            "progress_hooks": [self.progress_hook],  # Register the progress hook
        }

        # Update the format option based on selectionType
        if self.selectionType == "audio":
            ydl_opts["format"] = "bestaudio/best"
        elif self.selectionType == "video":
            selected_format = self.comboBox.currentText().split(":")[0]
            ydl_opts["format"] = selected_format

        # Define playlist options if download_playlist is True
        if download_playlist:
            ydl_opts["noplaylist"] = False
            ydl_opts["yes_playlist"] = True
            ydl_opts["playlist_items"] = (
                "1"  # Only fetch the first video in the playlist
            )
        else:
            ydl_opts["noplaylist"] = True

        # Define output directory if download_folder is set
        if self.download_folder:
            ydl_opts["outtmpl"] = os.path.join(
                self.download_folder, "%(title)s.%(ext)s"
            )

        self.download_thread = DownloadWorker(url, ydl_opts)
        self.download_thread.progress.connect(self.progress_hook)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.error.connect(self.on_download_error)
        self.download_thread.start()

    def progress_hook(self, d):
        """
        Handle progress updates during the download process.

        Args:
            d (dict): The dictionary containing progress update information.
        """
        if d["status"] == "downloading":
            self.download_data = d

    def update_progress(self):
        """
        Update the progress bar and labels with the download status.
        """
        if self.download_data:
            self.file_size = self.download_data.get("total_bytes")
            self.downloaded_bytes = self.download_data.get("downloaded_bytes")
            self.status = self.download_data.get("status")
            self.eta = self.download_data.get("eta")
            self.transfer_rate = self.download_data.get("speed")

            if self.file_size:
                progress = (self.downloaded_bytes / self.file_size) * 100
                self.progressBar.setValue(progress)
            if self.downloaded_bytes:
                downloaded_mb = self.downloaded_bytes / (1024 * 1024)
                self.downloadedLabel.setText(f"{downloaded_mb:.2f} MB")
            if self.file_size:
                total_mb = self.file_size / (1024 * 1024)
                self.fileSizeLabel.setText(f"{total_mb:.2f} MB")
            if self.status:
                self.statusLabel.setText(f"Status: {self.status}")
            if self.eta:
                eta_str = str(timedelta(seconds=self.eta))
                self.etaLabel.setText(f"ETA: {eta_str}")
            if self.transfer_rate:
                speed_mb = self.transfer_rate / (1024 * 1024)
                self.speedLabel.setText(f"Speed: {speed_mb:.2f} MB/s")

    def update_table(self):
        """
        Update the table with download details from the database.
        """
        from db_functions import retrieve_all_completed_downloads

        completed_downloads = retrieve_all_completed_downloads()
        self.tableWidget.setRowCount(len(completed_downloads))
        self.tableWidget.setColumnCount(3)
        for row, download in enumerate(completed_downloads):
            for col, data in enumerate(download):
                item = QTableWidgetItem(str(data))
                item.setTextAlignment(Qt.AlignCenter)
                self.tableWidget.setItem(row, col, item)

    def comboChanged(self):
        """
        Handle changes in the combo box selection.
        """
        current_text = self.comboBox.currentText()
        if "audio" in current_text.lower():
            self.selectionType = "audio"
        elif "video" in current_text.lower():
            self.selectionType = "video"
        else:
            self.selectionType = "unknown"

    def on_download_finished(self):
        """
        Handle the completion of the download process.
        """
        QMessageBox.information(self, "Download Finished", "The download is complete.")
        self.download_thread = None
        self.update_table()

    def on_download_error(self, error):
        """
        Handle errors during the download process.

        Args:
            error (str): The error message.
        """
        QMessageBox.critical(self, "Download Error", f"An error occurred: {error}")
        self.download_thread = None

    def select_download_folder(self):
        """
        Allow the user to select a download folder.
        """
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.download_folder = folder
            self.downloadFolderLabel.setText(folder)

    def open_download_folder(self):
        """
        Open the selected download folder in the file explorer.
        """
        if self.download_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.download_folder))
        else:
            QMessageBox.warning(
                self,
                "Folder Error",
                "Please select a download folder first.",
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
