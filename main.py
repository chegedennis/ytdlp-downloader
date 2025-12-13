"""
main.py - FIXED THUMBNAIL VERSION

A Modern PyQt5 YouTube Downloader.
Features:
- "Cover Art" Mode: Saves a permanent JPG cover art file next to the MP3.
- Embeds metadata and thumbnails into the audio file for file manager display.
- Responsive UI, Dark Theme, and Auto-Clipboard.

FIXES:
- Proper thumbnail handling per video (not shared across playlist)
- Correct filename matching for cover art
- Better error handling for thumbnail operations
- ID3v2.3 tags for maximum compatibility with Windows/macOS/Linux file managers
- High-quality audio encoding (320kbps MP3)
"""

import os
import sys

# Force X11 backend on Linux to prevent Wayland issues
os.environ["QT_QPA_PLATFORM"] = "xcb"

import shutil
import time
import re
from datetime import timedelta
import yt_dlp
import requests

from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt, QSize, QUrl
from PyQt5.QtGui import QIcon, QPixmap, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QMessageBox,
    QCheckBox,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QMenu,
    QAbstractItemView,
    QFrame,
)

from db_functions import (
    create_database_or_database_table,
    add_file_to_database_table,
    fetch_entries_from_database,
    delete_files_from_database,
    create_db_dir,
)

# --- Utility Functions ---


def check_ffmpeg():
    return shutil.which("ffmpeg") is not None


def format_bytes(size):
    power = 2**10
    n = 0
    power_labels = {0: "", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"


# --- Workers ---


class FormatWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "playlist_items": "1",
            "noplaylist": False,
            "extract_flat": False,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(self.url, download=False)
                if "entries" in info_dict:
                    entries = list(info_dict["entries"])
                    if entries:
                        info_dict = entries[0]

                # Download Thumbnail for Preview
                thumb_url = info_dict.get("thumbnail")
                if thumb_url:
                    try:
                        response = requests.get(thumb_url, timeout=10)
                        if response.status_code == 200:
                            info_dict["thumbnail_bytes"] = response.content
                    except Exception as e:
                        print(f"Thumbnail download failed: {e}")

                self.finished.emit(info_dict)
        except Exception as e:
            self.error.emit(str(e))


class DownloadWorker(QThread):
    progress = pyqtSignal(dict)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    # NEW: Signal to pass thumbnail data per video
    video_info = pyqtSignal(str, bytes)  # (video_id, thumbnail_bytes)

    def __init__(self, url, ydl_opts):
        super().__init__()
        self.url = url
        self.ydl_opts = ydl_opts

    def progress_hook(self, d):
        """Custom progress hook that also captures video info"""
        self.progress.emit(d)

        # Extract thumbnail for each video during download
        if d.get("status") == "downloading":
            info_dict = d.get("info_dict")
            if info_dict:
                video_id = info_dict.get("id", "")
                thumb_url = info_dict.get("thumbnail")

                # Download thumbnail for this specific video
                if thumb_url and video_id:
                    try:
                        response = requests.get(thumb_url, timeout=5)
                        if response.status_code == 200:
                            self.video_info.emit(video_id, response.content)
                    except Exception as e:
                        print(f"Thumbnail fetch error for {video_id}: {e}")

    def run(self):
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                ydl.add_progress_hook(self.progress_hook)
                ydl.extract_info(self.url, download=True)
                self.finished.emit("All Downloads Finished")
        except Exception as e:
            self.error.emit(str(e))


# --- Main Window ---


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.setWindowTitle("Modern YouTube Downloader")
        self.resize(900, 650)

        # Data & Config
        self.table_name = "completed_downloads"
        self.selectionType = None
        self.download_data = {}
        self.download_folder = os.getcwd()
        self.row_cache = {}
        self.processed_files = set()

        # NEW: Store thumbnails per video ID instead of single thumbnail
        self.video_thumbnails = {}  # {video_id: thumbnail_bytes}
        self.preview_thumbnail_data = None  # Just for preview display

        # NEW: Track video IDs to filenames
        self.video_id_to_filename = {}  # {video_id: final_filename}

        # Database Init
        create_db_dir()
        create_database_or_database_table(self.table_name)

        # UI Initialization
        self.init_ui()
        self.apply_styles()
        self.check_clipboard()

        # Load History
        self.initialize_table_from_database()

        # Timers
        self.update_timer = QTimer()
        self.update_timer.setInterval(100)
        self.update_timer.timeout.connect(self.update_progress)
        self.update_timer.start()

        # Check Dependencies
        if not check_ffmpeg():
            self.statusbar.showMessage(
                "Warning: FFmpeg not found. Merging & Embedding will fail."
            )

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # --- Input Section ---
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube Link Here...")
        self.url_input.setMinimumHeight(40)

        self.btn_get = QPushButton("Fetch")
        self.btn_get.setCursor(Qt.PointingHandCursor)
        self.btn_get.setMinimumHeight(40)
        self.btn_get.clicked.connect(self.get_formats)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setMinimumHeight(40)
        self.btn_clear.clicked.connect(self.clear_input)

        input_layout.addWidget(self.url_input, stretch=4)
        input_layout.addWidget(self.btn_get, stretch=1)
        input_layout.addWidget(self.btn_clear, stretch=1)

        # --- Metadata & Controls ---
        meta_layout = QHBoxLayout()

        self.lbl_thumbnail = QLabel()
        self.lbl_thumbnail.setFixedSize(160, 90)
        self.lbl_thumbnail.setStyleSheet(
            "background-color: #222; border: 1px solid #444; color: #888;"
        )
        self.lbl_thumbnail.setAlignment(Qt.AlignCenter)
        self.lbl_thumbnail.setText("No Image")
        self.lbl_thumbnail.setScaledContents(True)

        controls_layout = QVBoxLayout()
        self.combo_formats = QComboBox()
        self.combo_formats.setMinimumHeight(35)
        self.combo_formats.currentIndexChanged.connect(self.combo_changed)

        options_row = QHBoxLayout()
        self.chk_playlist = QCheckBox("Download Playlist")
        self.btn_folder = QPushButton("Change Folder")
        self.btn_folder.clicked.connect(self.select_download_folder)

        options_row.addWidget(self.chk_playlist)
        options_row.addWidget(self.btn_folder)
        options_row.addStretch()

        controls_layout.addWidget(self.combo_formats)
        controls_layout.addLayout(options_row)

        self.btn_download = QPushButton("START DOWNLOAD")
        self.btn_download.setMinimumHeight(50)
        self.btn_download.setStyleSheet(
            "font-size: 14px; font-weight: bold; background-color: #28a745;"
        )
        self.btn_download.clicked.connect(self.start_download)

        meta_layout.addWidget(self.lbl_thumbnail)
        meta_layout.addLayout(controls_layout, stretch=1)
        meta_layout.addWidget(self.btn_download, stretch=1)

        # --- Table ---
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Filename", "Size", "Progress", "ETA", "Speed"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 150)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        self.statusbar = self.statusBar()
        self.statusbar.showMessage(f"Save Location: {self.download_folder}")

        main_layout.addLayout(input_layout)
        main_layout.addLayout(meta_layout)
        main_layout.addWidget(self.table)

    def apply_styles(self):
        self.setStyleSheet(
            """
            QMainWindow { background-color: #2b2b2b; color: #ffffff; }
            QWidget { font-family: 'Segoe UI', sans-serif; font-size: 10pt; }
            QLineEdit { padding: 8px; border-radius: 4px; border: 1px solid #555; background: #333; color: white; }
            QLineEdit:focus { border: 1px solid #0d6efd; }
            QPushButton { padding: 5px; border-radius: 4px; background-color: #0d6efd; color: white; border: none; }
            QPushButton:hover { background-color: #0b5ed7; }
            
            QComboBox { padding: 5px; border: 1px solid #555; border-radius: 4px; background: #333; color: white; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background-color: #333; color: white; selection-background-color: #0d6efd; }
            
            QTableWidget { background-color: #222; gridline-color: #333; color: #eee; border: 1px solid #444; }
            QHeaderView::section { background-color: #333; color: white; padding: 5px; border: 1px solid #444; }
            QProgressBar { border: 1px solid #444; border-radius: 3px; text-align: center; background: #222; color: white; }
            QProgressBar::chunk { background-color: #0d6efd; width: 10px; }
            QStatusBar { background: #222; color: #aaa; }
        """
        )

    def check_clipboard(self):
        clipboard_text = QApplication.clipboard().text()
        if "youtube.com" in clipboard_text or "youtu.be" in clipboard_text:
            self.url_input.setText(clipboard_text)

    # --- Logic ---

    def get_formats(self):
        url = self.url_input.text().strip()
        if not url:
            return

        self.btn_get.setEnabled(False)
        self.combo_formats.clear()
        self.combo_formats.addItem("Fetching...")

        self.format_worker = FormatWorker(url)
        self.format_worker.finished.connect(self.on_formats_fetched)
        self.format_worker.error.connect(
            lambda e: self.combo_formats.setItemText(0, "Error")
        )
        self.format_worker.start()

    def on_formats_fetched(self, info):
        self.btn_get.setEnabled(True)
        self.combo_formats.clear()

        # Store thumbnail just for preview
        thumb_bytes = info.get("thumbnail_bytes")
        if thumb_bytes:
            self.preview_thumbnail_data = thumb_bytes
            pixmap = QPixmap()
            if pixmap.loadFromData(thumb_bytes):
                self.lbl_thumbnail.setPixmap(pixmap)
            else:
                self.lbl_thumbnail.setText("Bad Image")
        else:
            self.lbl_thumbnail.setText("No Image")
            self.preview_thumbnail_data = None

        self.combo_formats.addItem("Select Format", None)
        self.combo_formats.addItem("Audio Only (Best Quality)", "audio")

        unique_resolutions = set()
        for f in info.get("formats", []):
            if f.get("vcodec") != "none" and f.get("height"):
                unique_resolutions.add(f["height"])

        for res in sorted(list(unique_resolutions), reverse=True):
            label = "4K" if res >= 2160 else "2K" if res >= 1440 else f"{res}p"
            self.combo_formats.addItem(f"Video {label} - MP4", res)

    def combo_changed(self):
        self.selectionType = self.combo_formats.currentData()

    def start_download(self):
        url = self.url_input.text().strip()
        if not url or not self.selectionType:
            QMessageBox.warning(self, "Oops", "Please select a format first.")
            return

        # Clear old data
        self.video_thumbnails.clear()
        self.video_id_to_filename.clear()

        ydl_opts = {
            "outtmpl": os.path.join(self.download_folder, "%(title)s.%(ext)s"),
            "noplaylist": not self.chk_playlist.isChecked(),
            "writethumbnail": True,
        }

        postprocessors = []
        if self.selectionType == "audio":
            ydl_opts["format"] = "bestaudio/best"
            postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",  # High quality
                }
            )
        elif isinstance(self.selectionType, int):
            h = self.selectionType
            ydl_opts["format"] = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
            postprocessors.append(
                {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
            )

        # Embed metadata and thumbnail properly
        postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
        postprocessors.append(
            {
                "key": "FFmpegThumbnailsConvertor",
                "format": "jpg",
                "when": "before_dl",  # Convert before embedding
            }
        )
        postprocessors.append(
            {"key": "EmbedThumbnail", "already_have_thumbnail": False}
        )

        # Force ID3v2.3 for better compatibility with Windows/macOS
        ydl_opts["postprocessor_args"] = {"ffmpeg": ["-id3v2_version", "3"]}

        ydl_opts["postprocessors"] = postprocessors

        self.btn_download.setEnabled(False)
        self.btn_download.setText("DOWNLOADING...")

        self.dl_worker = DownloadWorker(url, ydl_opts)
        self.dl_worker.progress.connect(lambda d: setattr(self, "download_data", d))
        self.dl_worker.video_info.connect(self.store_video_thumbnail)
        self.dl_worker.finished.connect(self.on_download_finished)
        self.dl_worker.error.connect(self.on_download_error)
        self.dl_worker.start()

    def store_video_thumbnail(self, video_id, thumbnail_bytes):
        """Store thumbnail data for a specific video"""
        if video_id and thumbnail_bytes:
            self.video_thumbnails[video_id] = thumbnail_bytes
            print(f"Stored thumbnail for video: {video_id}")

    def on_download_error(self, err_msg):
        self.btn_download.setEnabled(True)
        self.btn_download.setText("START DOWNLOAD")
        QMessageBox.critical(self, "Download Failed", f"An error occurred:\n{err_msg}")

    def find_matching_file(self, base_filename):
        """Find the actual downloaded file (handling extension changes)"""
        # Remove extension and search for files with same base name
        base_name = os.path.splitext(base_filename)[0]
        search_path = os.path.join(self.download_folder, base_name)

        # Common extensions after post-processing
        extensions = [".mp3", ".mp4", ".webm", ".m4a", ".mkv"]

        for ext in extensions:
            full_path = search_path + ext
            if os.path.exists(full_path):
                return full_path

        return None

    def save_cover_art(self, filepath, thumbnail_bytes):
        """Save cover art as JPG next to the media file"""
        if not thumbnail_bytes or not filepath:
            return

        base, _ = os.path.splitext(filepath)
        cover_path = base + ".jpg"

        if os.path.exists(cover_path):
            print(f"Cover art already exists: {cover_path}")
            return

        try:
            with open(cover_path, "wb") as f:
                f.write(thumbnail_bytes)
            print(f"✓ Cover art saved: {cover_path}")
        except Exception as e:
            print(f"✗ Could not save cover art: {e}")

    def update_progress(self):
        if not self.download_data:
            return

        raw_name = self.download_data.get("filename")
        if not raw_name:
            return
        filename = os.path.basename(raw_name)

        # Get video info if available
        info_dict = self.download_data.get("info_dict")
        video_id = info_dict.get("id") if info_dict else None

        # Dynamic Row Creation
        if filename not in self.row_cache:
            row = 0
            self.table.insertRow(row)
            pbar = QProgressBar()
            pbar.setValue(0)
            pbar.setStyleSheet("QProgressBar { height: 15px; }")
            item_name = QTableWidgetItem(filename)
            item_size = QTableWidgetItem("--")
            item_eta = QTableWidgetItem("--")
            item_speed = QTableWidgetItem("--")
            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_size)
            self.table.setCellWidget(row, 2, pbar)
            self.table.setItem(row, 3, item_eta)
            self.table.setItem(row, 4, item_speed)
            self.row_cache[filename] = {
                "name_item": item_name,
                "size_item": item_size,
                "eta_item": item_eta,
                "speed_item": item_speed,
                "video_id": video_id,
            }

        # Update
        items = self.row_cache[filename]
        row = self.table.row(items["name_item"])
        status = self.download_data.get("status")
        total = (
            self.download_data.get("total_bytes")
            or self.download_data.get("total_bytes_estimate")
            or 0
        )
        downloaded = self.download_data.get("downloaded_bytes", 0)
        pbar = self.table.cellWidget(row, 2)

        if status == "finished":
            pbar.setValue(100)
            items["eta_item"].setText("Done")
            items["speed_item"].setText("-")

            if filename not in self.processed_files:
                add_file_to_database_table(
                    filename,
                    items["size_item"].text(),
                    "Completed",
                    "0s",
                    "0",
                    self.table_name,
                )
                self.processed_files.add(filename)

                # --- IMPROVED COVER ART SAVING ---
                # Find the actual file (extension may have changed)
                actual_file = self.find_matching_file(raw_name)

                # Get thumbnail for this specific video
                stored_video_id = items.get("video_id")
                thumbnail_data = (
                    self.video_thumbnails.get(stored_video_id)
                    if stored_video_id
                    else None
                )

                # Fallback to preview thumbnail if we don't have video-specific one
                if not thumbnail_data:
                    thumbnail_data = self.preview_thumbnail_data

                if actual_file and thumbnail_data:
                    self.save_cover_art(actual_file, thumbnail_data)
                else:
                    if not actual_file:
                        print(f"Could not find file for: {filename}")
                    if not thumbnail_data:
                        print(f"No thumbnail data for: {filename}")

            return

        if total > 0:
            percent = int((downloaded / total) * 100)
            pbar.setValue(percent)
            items["size_item"].setText(format_bytes(total))
            speed = self.download_data.get("speed", 0) or 0
            items["speed_item"].setText(f"{format_bytes(speed)}/s")
            eta = self.download_data.get("eta", 0)
            if eta:
                items["eta_item"].setText(str(timedelta(seconds=int(eta))))

    def on_download_finished(self, msg):
        self.btn_download.setEnabled(True)
        self.btn_download.setText("START DOWNLOAD")
        QMessageBox.information(self, "Success", "Downloads Completed!")
        self.clear_input()

    def initialize_table_from_database(self):
        entries = fetch_entries_from_database(self.table_name)
        if entries:
            for data in entries:
                row = 0
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(data[1])))
                self.table.setItem(row, 1, QTableWidgetItem(str(data[2])))
                pbar = QProgressBar()
                pbar.setValue(100)
                self.table.setCellWidget(row, 2, pbar)
                self.table.setItem(row, 3, QTableWidgetItem("Done"))
                self.table.setItem(row, 4, QTableWidgetItem("-"))

    def clear_input(self):
        self.url_input.clear()
        self.combo_formats.clear()
        self.lbl_thumbnail.clear()
        self.lbl_thumbnail.setText("No Image")
        self.download_data = {}
        self.preview_thumbnail_data = None
        self.video_thumbnails.clear()

    def select_download_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Select Folder")
        if f:
            self.download_folder = f
            self.statusbar.showMessage(f"Save Location: {f}")

    def show_context_menu(self, pos):
        menu = QMenu()
        delete_act = menu.addAction("Delete Selected")
        if menu.exec_(self.table.mapToGlobal(pos)) == delete_act:
            rows = sorted(
                set(index.row() for index in self.table.selectedIndexes()), reverse=True
            )
            filenames = [self.table.item(r, 0).text() for r in rows]
            delete_files_from_database(filenames, self.table_name)
            for r in rows:
                self.table.removeRow(r)


if __name__ == "__main__":
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
