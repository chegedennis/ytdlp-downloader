# 🎵 Modern YouTube Downloader

A sleek, feature-rich PyQt5 application for downloading YouTube videos and audio with embedded thumbnails, metadata, and automatic cover art generation.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)
![License](https://img.shields.io/badge/license-MIT-purple.svg)

## ✨ Features

### Core Functionality
- **High-Quality Downloads**: Audio (320kbps MP3) and Video (up to 4K)
- **Playlist Support**: Download entire playlists or single videos
- **Smart Thumbnail Management**: 
  - Embeds artwork into MP3/MP4 files (shows as file icon in file managers)
  - Saves separate `.jpg` cover art file alongside media
  - Per-video thumbnail handling for playlists
- **Live Progress Tracking**: Real-time download progress, speed, and ETA
- **Auto-Clipboard Detection**: Automatically detects YouTube URLs from clipboard

### User Interface
- 🎨 Modern dark theme with responsive design
- 📊 Interactive download history table
- 🖼️ Live thumbnail preview
- 🗂️ Custom download folder selection
- ⚡ Context menu for managing downloads

### Technical Features
- Concurrent downloads with threaded workers
- SQLite database for download history
- FFmpeg integration for format conversion and metadata embedding
- ID3v2.3 tag compatibility (Windows/macOS/Linux file managers)
- Automatic file extension detection and matching

## 📋 Prerequisites

### Required Software
- **Python 3.8+**
- **FFmpeg** (must be in system PATH)

### Python Dependencies
```bash
pip install PyQt5 yt-dlp requests
```

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/chegedennis/ytdlp-downloader.git
cd ytdlp-downloader
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install FFmpeg

#### Windows
Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH, or use Chocolatey:
```bash
choco install ffmpeg
```

#### macOS
```bash
brew install ffmpeg
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install ffmpeg
```

### 4. Run the Application
```bash
python main.py
```

## 📁 Project Structure

```
ytdlp-downloader/
├── main.py              # Main application file
├── db_functions.py      # Database operations
├── requirements.txt     # Python dependencies
├── README.md            # This file
└── .dbs/                # Created automatically
  └── app_db.db        # Download history database
```

## 🎯 Usage Guide

### Basic Download

1. **Paste URL**: Copy a YouTube URL and paste it into the input field (or it auto-fills from clipboard)
2. **Fetch Formats**: Click the "Fetch" button to load available formats
3. **Select Quality**: Choose from:
   - Audio Only (Best Quality) - 320kbps MP3
   - Video 4K/2K/1080p/720p/480p/360p - MP4
4. **Start Download**: Click "START DOWNLOAD"

### Playlist Downloads

1. Check the **"Download Playlist"** checkbox
2. Paste the playlist URL
3. Fetch and select your preferred format
4. All videos will download with individual thumbnails

### Managing Downloads

- **View History**: All downloads appear in the table with progress
- **Delete Entries**: Right-click on any row → "Delete Selected"
- **Change Folder**: Click "Change Folder" to set download location
- **Clear Input**: Click "Clear" to reset the form

## 🖼️ Thumbnail Features Explained

This application handles thumbnails in TWO ways:

### 1. Embedded Thumbnails (File Icon)
- Thumbnails are embedded into MP3/MP4 files using ID3/MP4 metadata
- **Result**: The media file shows the video thumbnail as its icon in file explorers
- **Compatibility**: Works on Windows (Explorer), macOS (Finder), and Linux (Nautilus/Dolphin)

### 2. Cover Art File
- A separate `filename.jpg` is saved next to each media file
- **Purpose**: Backup artwork, easier sharing, better organization
- **Location**: Same folder as the downloaded media

### Viewing Embedded Thumbnails

**Windows:**
- Use "Large Icons" or "Extra Large Icons" view in File Explorer
- Refresh folder with F5 if needed

**macOS:**
- Use "Icon View" (Cmd+1) in Finder
- Increase icon size with Cmd++

**Linux:**
```bash
# Install thumbnail support
sudo apt install ffmpegthumbnailer python3-mutagen

# Clear cache if needed
rm -rf ~/.cache/thumbnails/*
```

## ⚙️ Configuration

### Download Location
Default: Current working directory  
Change via: "Change Folder" button in the UI

### Audio Quality
Default: 320kbps MP3  
Modify in `main.py` → `start_download()` → `'preferredquality': '320'`

### Video Quality
Available options: 4K, 2K, 1080p, 720p, 480p, 360p  
Selected via dropdown in UI

## 🔧 Troubleshooting

### FFmpeg Not Found
**Symptom**: Warning message "FFmpeg not found"  
**Solution**: Install FFmpeg and ensure it's in your system PATH
```bash
# Test FFmpeg installation
ffmpeg -version
```

### Thumbnails Not Showing as File Icons
**Possible Causes**:
1. File manager doesn't support embedded thumbnails
2. View mode is set to "List" instead of "Icons"
3. Thumbnail cache needs refresh

**Solutions**:
- Change view to Large/Extra Large Icons
- Clear thumbnail cache (see platform-specific instructions above)
- Check that the separate `.jpg` file exists next to the media file

### Download Fails
**Common Issues**:
1. Invalid YouTube URL
2. Video is age-restricted or private
3. Network connectivity issues
4. FFmpeg not installed

**Solutions**:
- Verify the URL is accessible in a browser
- Check your internet connection
- Review console output for specific errors

### Wayland Issues (Linux)
The app forces X11 backend. If you encounter display issues:
```bash
# Run with explicit backend
QT_QPA_PLATFORM=xcb python main.py
```

## 🗄️ Database

Download history is stored in `.dbs/app_db.db` (SQLite)

### Schema
```sql
CREATE TABLE completed_downloads (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    size TEXT,
    status TEXT,
    eta TEXT,
    speed TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Accessing the Database
```bash
sqlite3 .dbs/app_db.db
SELECT * FROM completed_downloads;
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This tool is for personal use only. Please respect YouTube's Terms of Service and copyright laws. Only download content you have the right to download.

## 🙏 Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube download engine
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework
- [FFmpeg](https://ffmpeg.org/) - Media processing

## 📧 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions

---

**Made with ❤️ using Python and PyQt5**