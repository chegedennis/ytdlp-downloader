"""
main.py

A PyQt5 application for downloading YouTube videos and audio using yt-dlp. This application allows users to select
video formats, track download progress, and manage completed downloads.

Modules: os sys time re subprocess yt_dlp datetime.timedelta PyQt5.QtCore (QTimer, QThread, pyqtSignal, QObject,
Qt) PyQt5.QtWidgets (QApplication, QMainWindow, QMessageBox, QCheckBox, QLabel, QPushButton, QFileDialog,
QTableWidgetItem) PyQt5.uic (loadUi) db_functions (create_database_or_database_table)

Classes:
    DownloadWorker: A QThread subclass that handles video/audio downloading using yt-dlp.
    MainWindow: A QMainWindow subclass that defines the main window and user interface for the application.

Functions:
    create_db_dir(): Creates a directory named '.dbs' if it doesn't exist.
    normalize_filename(filename): Normalizes filenames by removing unwanted characters and patterns.
    parse_formats(output): Parses the format output from yt-dlp to categorize audio and video formats.
    format_bytes(size): Converts bytes to a human-readable string with appropriate units.
"""

import os
import re
import subprocess
import sys
import time
from datetime import timedelta

import yt_dlp
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QCheckBox,
    QLabel,
    QPushButton,
    QFileDialog,
    QTableWidgetItem,
    QMenu,
)
from PyQt5.uic import loadUi

from db_functions import (
    create_database_or_database_table,
    add_file_to_database_table,
    fetch_entries_from_database,
    delete_files_from_database,
)


def create_db_dir():
    """
    Creates a directory named '.dbs' if it doesn't exist.
    """
    os.makedirs(".dbs", exist_ok=True)


class DownloadWorker(QThread):
    """
    A worker thread for downloading videos using yt-dlp.

    Attributes:
        progress: Signal emitted with download progress information.
        finished: Signal emitted when the download is finished.
        error: Signal emitted if an error occurs during download.
    """

    progress = pyqtSignal(dict)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url, ydl_opts):
        """
        Initializes the DownloadWorker with a URL and yt-dlp options.

        Args:
            url (str): The URL of the video to download.
            ydl_opts (dict): Options for yt-dlp.
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
                info_dict = ydl.extract_info(self.url, download=True)
                video_title = info_dict.get("title", None)

                # Determine the file extension based on whether the download is audio or video
                if "requested_formats" in info_dict:
                    # Video and audio merged
                    merged_filename = f"{video_title}.mp4"
                else:
                    # Audio only
                    audio_extension = info_dict.get("ext", "m4a")
                    merged_filename = f"{video_title}.{audio_extension}"

                self.finished.emit(merged_filename)
        except Exception as e:
            self.error.emit(str(e))


def normalize_filename(filename):
    """
    Normalizes the filename by removing suffixes like .f614 or .f140.

    Args:
        filename (str): The original filename.

    Returns:
        str: The normalized filename.
    """
    base, _ = os.path.splitext(filename)
    # Remove suffixes like .f614 or .f140
    base = base.rsplit(".", 1)[0]
    return base


def parse_formats(output):
    """
    Parses the output from yt-dlp to extract available formats.

    Args:
        output (str): The format output from yt-dlp.

    Returns:
        dict: A dictionary with audio and video formats.
    """
    lines = output.splitlines()
    formats = {"audio": None, "video": []}

    def resolution_to_label(res):
        width, height = map(int, res.split("x"))
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
            video_resolution = video_match.group(
                2
            )  # Changed variable name from 'resolution'
            label = resolution_to_label(video_resolution)
            formats["video"].append(f"{format_code}: {label}")

        audio_match = re.match(r"^(\d+)\s+\w+\s+audio only", line)
        if audio_match:
            format_code = audio_match.group(1)
            formats["audio"] = f"{format_code}: Audio Only"

    return formats


def format_bytes(size):
    """
    Converts a byte size into a human-readable string with appropriate units.

    Args:
        size (int): The size in bytes.

    Returns:
        str: The size formatted as a human-readable string.
    """
    # 2**10 = 1024
    power = 2**10
    n = 0
    power_labels = {0: "", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"


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
        Initializes the main window and sets up the UI and connections.
        """
        super(MainWindow, self).__init__()
        self.table = "completed_downloads"
        self.selectionType = None
        self.status = None
        self.eta = None
        self.transfer_rate = None
        self.downloaded_bytes = None
        self.file_size = None
        self.url = None
        self.current_row_position = None  # Track the current row being updated
        loadUi("tube.ui", self)

        create_db_dir()
        create_database_or_database_table(self.table)

        self.last_update_time = time.time()
        self.update_interval = 0.5

        self.download_data = {}

        self.update_timer = QTimer()
        self.update_timer.setInterval(int(self.update_interval * 1000))
        self.update_timer.timeout.connect(self.update_progress)
        self.update_timer.start()

        self.pushButton.clicked.connect(self.get_formats)
        self.comboBox.currentIndexChanged.connect(self.combo_changed)
        self.downloadButton.clicked.connect(self.start_download)
        self.clearButton.clicked.connect(self.clear_input)
        self.playlistCheckBox = self.findChild(QCheckBox, "playlistCheckBox")

        self.download_thread = None
        self.download_folder = None

        self.fileSizeLabel = self.findChild(QLabel, "fileSizeLabel")
        self.fileNameLabel = self.findChild(QLabel, "fileNameLabel")
        self.downloadFolderButton = self.findChild(QPushButton, "downloadFolderButton")
        self.downloadFolderButton.clicked.connect(self.select_download_folder)

        # Initialize table with existing entries from the database
        self.initialize_table_from_database()

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def initialize_table_from_database(self):
        """
        Initializes the table widget with existing entries from the database.
        """
        table_name = self.table
        entries = fetch_entries_from_database(table_name)

        if entries:
            # Exclude the 'id' column from the table
            num_columns = len(entries[0]) - 1  # Exclude 'id' column
            self.tableWidget.setRowCount(len(entries))
            self.tableWidget.setColumnCount(num_columns)

            for row_idx, row_data in enumerate(entries):
                for col_idx, cell_data in enumerate(
                    row_data[1:]
                ):  # Skip the first column (id)
                    self.tableWidget.setItem(
                        row_idx, col_idx, QTableWidgetItem(str(cell_data))
                    )
        else:
            self.tableWidget.setRowCount(0)  # No entries found
            self.tableWidget.setColumnCount(
                5
            )  # Set column count if needed, e.g., 5 columns

    def clear_input(self):
        """
        Clears the input fields and resets the UI elements.
        """
        self.lineEdit.clear()
        self.comboBox.clear()
        self.progressBar.setValue(0)
        self.downloadedLabel.setText("Downloaded: 0 MB")
        self.fileSizeLabel.setText("File Size: 0 MB")
        self.fileNameLabel.setText("File Name: None")

        # Stop the update timer to prevent immediate UI updates with old values
        self.update_timer.stop()

        # Clear download data
        self.download_data = {}

        # Restart the timer if needed (optional, depending on your application's logic)
        self.update_timer.start()

    def get_highlighted_filenames(self):
        """
        Returns a list of filenames corresponding to highlighted rows in the tableWidget.

        Returns:
            list: List of highlighted filenames.
        """
        highlighted_filenames = []
        selected_rows = self.tableWidget.selectionModel().selectedRows()
        for row in selected_rows:
            filename = self.tableWidget.item(row.row(), 0).text()
            highlighted_filenames.append(filename)
        return highlighted_filenames

    def show_context_menu(self):
        """
        Displays a context menu with an option to delete selected files.

        The context menu appears at the cursor's current position and provides a
        "Delete" option. When the "Delete" option is selected, it triggers the
        `delete_selected_files` method to delete the selected files from the
        table widget and the database.
        """
        menu = QMenu()
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_files)

        menu.exec_(QCursor.pos())

    def delete_selected_files(self):
        """
        Deletes the selected files from the table widget and the database.

        This method retrieves the filenames of the selected rows in the table widget,
        deletes them from the database, and removes the corresponding rows from the
        table widget. If no rows are selected, the method does nothing.
        """
        selected_rows = self.tableWidget.selectionModel().selectedRows()

        if not selected_rows:
            return

        filenames_to_delete = self.get_highlighted_filenames()
        delete_files_from_database(filenames_to_delete, self.table)

        for row in sorted(selected_rows, reverse=True):
            self.tableWidget.removeRow(row.row())

    def get_formats(self):
        """
        Retrieves available formats for the entered URL using yt-dlp.
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
        Populates the format selection combobox with available formats.

        Args:
            formats (dict): A dictionary of available formats.
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
        Starts the download process for the selected URL and format.
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
        self.downloadButton.setEnabled(False)

    def progress_hook(self, d):
        """
        Updates the progress bar and other UI elements based on download progress.

        Args:
            d (dict): Progress information from yt-dlp.
        """
        self.download_data = d

        if "filename" in d:
            filename = d["filename"]  # Get the actual filename from the dictionary
            cleaned_filename = normalize_filename(filename)
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
        Periodically updates the UI elements with download information.
        """
        if not self.download_data:
            # No active download, reset the progress bar and labels
            self.progressBar.setValue(0)
            self.downloadedLabel.setText("Downloaded: 0 MB")
            self.fileSizeLabel.setText("File Size: 0 MB")
            return
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
            if isinstance(eta_seconds, (int, float)) and eta_seconds is not None:
                time_left = str(timedelta(seconds=eta_seconds)).split(".")[
                    0
                ]  # Remove milliseconds
            else:
                time_left = "N/A"

            # Extract and normalize the base name of the file
            filename = self.fileNameLabel.text().replace("Downloading: ", "").strip()
            base_filename = normalize_filename(filename)

            row_count = self.tableWidget.rowCount()
            row_position = -1
            for row in range(row_count):
                item = self.tableWidget.item(row, 0)
                if item is not None:
                    item_text = item.text()
                    item_base_filename = normalize_filename(item_text)

                    if item_base_filename == base_filename:
                        row_position = row
                        break

            # If not found, add a new row
            if row_position == -1:
                row_position = self.tableWidget.rowCount()
                self.tableWidget.insertRow(row_position)
                self.current_row_position = (
                    row_position  # Store the current row position
                )

            # Set or update the row with the new values
            self.tableWidget.setItem(row_position, 0, QTableWidgetItem(filename))
            self.tableWidget.setItem(row_position, 1, QTableWidgetItem(file_size_str))
            self.tableWidget.setItem(row_position, 2, QTableWidgetItem(download_status))
            self.tableWidget.setItem(row_position, 3, QTableWidgetItem(time_left))
            self.tableWidget.setItem(
                row_position, 4, QTableWidgetItem(transfer_rate_str)
            )

    def combo_changed(self):
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

    def on_download_finished(self, merged_filename=None):
        """
        Handles actions when a download is finished.

        Args:
            merged_filename (str): The final merged filename after download (optional).
        """
        self.downloadButton.setEnabled(True)
        try:
            # Determine the correct filename for audio files
            if merged_filename is None:
                filename = (
                    self.fileNameLabel.text().replace("Downloading: ", "").strip()
                )
            else:
                filename = merged_filename

            if os.path.exists(filename):
                file_size_bytes = os.path.getsize(filename)
                file_size_mb = file_size_bytes / (1024 * 1024)  # Convert bytes to MB
                file_size_gb = file_size_bytes / (
                    1024 * 1024 * 1024
                )  # Convert bytes to GB

                # Determine the appropriate unit (MB or GB)
                file_size_str = (
                    f"{file_size_gb:.2f} GB"
                    if file_size_gb >= 1
                    else f"{file_size_mb:.2f} MB"
                )

                # Use the current row position to update the row
                row_position = self.current_row_position
                if row_position is not None:
                    self.tableWidget.setItem(
                        row_position, 0, QTableWidgetItem(filename)
                    )
                    self.tableWidget.setItem(
                        row_position, 1, QTableWidgetItem(file_size_str)
                    )
                    self.tableWidget.setItem(
                        row_position, 2, QTableWidgetItem("Completed")
                    )
                    self.tableWidget.setItem(row_position, 3, QTableWidgetItem("N/A"))
                    self.tableWidget.setItem(
                        row_position, 4, QTableWidgetItem("0.00 MB/S")
                    )

                # Add the completed download to the database
                download_status = "Completed"
                time_left = "N/A"  # Time left is not available after download
                transfer_rate = (
                    "0.00 MB/S"  # Transfer rate is not available after download
                )
                add_file_to_database_table(
                    filename,
                    file_size_str,
                    download_status,
                    time_left,
                    transfer_rate,
                    "completed_downloads",
                )

            QMessageBox.information(
                self, "Download Finished", "The download is complete!"
            )
            self.clear_input()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Download Error",
                f"An error occurred while saving to the database: {e}",
            )
            print(f"Error: {e}")

    def on_download_error(self, error):
        """
        Handles errors that occur during download.

        Args:
            error (str): The error message.
        """
        self.downloadButton.setEnabled(True)
        QMessageBox.critical(self, "Download Error", f"An error occurred: {error}")

    def select_download_folder(self):
        """
        Opens a file dialog to select the download folder.
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
