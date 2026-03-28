# 📚 EPUB to MP3 Converter

A beautiful GUI application that converts EPUB ebooks to MP3 audio files using **Google TTS** or **Microsoft Edge TTS**. Each chapter is converted to a separate MP3 file with proper metadata tags.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)

## ✨ Features

### Core Features
- **📖 Chapter Detection**: Automatically extracts chapters from EPUB table of contents
- **🎵 ID3 Metadata**: Adds proper metadata (title, author, album, track number) to each MP3
- **🌍 Multi-Language**: Supports 15+ languages with various accent options
- **⚡ Progress Tracking**: Real-time progress bar and status updates
- **🛑 Stop Control**: Gracefully stop conversion at any time
- **📝 Logging**: Detailed conversion log for troubleshooting
- **🎨 Native Look**: Uses macOS native Aqua theme for seamless integration

### New Features! 🎉
- **🎙️ Dual TTS Engines**: Choose between Google TTS or Microsoft Edge TTS
- **🗣️ Voice Selection**: 400+ Edge TTS voices with different genders and accents
- **📑 Chapter Selector**: Pick specific chapters to convert with checkbox interface
- **✅ Select All/None/Invert**: Quick chapter selection tools

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd /Volumes/Exthome/John\ Ext/Documents/GITHUBProjects/gtts
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python epub_to_mp3_converter.py
```

### 3. Convert Your First Book

1. Click **Browse** to select an EPUB file
2. Choose an output folder (auto-suggested based on EPUB location)
3. Select your TTS engine (Google TTS or Edge TTS)
4. **📑 Select Chapters** to choose which chapters to convert
5. For Edge TTS: Select a voice from the dropdown
6. Click **▶ Convert to MP3**
7. Wait for conversion to complete
8. Find your MP3 files in the output folder!

## 📋 Requirements

- **Python**: 3.8 or higher
- **Operating System**: macOS (tested on M4), Windows, or Linux
- **Internet Connection**: Required for both TTS APIs

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| gTTS | ≥2.5.0 | Google Text-to-Speech |
| edge-tts | ≥6.1.0 | Microsoft Edge TTS |
| ebooklib | ≥0.18 | EPUB parsing |
| mutagen | ≥1.47.0 | MP3 metadata tagging |
| beautifulsoup4 | ≥4.12.0 | HTML parsing |

## 🎛️ Usage Guide

### Main Window

```
┌─────────────────────────────────────────────────────┐
│           📚 EPUB to MP3 Converter                 │
├─────────────────────────────────────────────────────┤
│ EPUB File:     [path]                  [Browse]     │
│ Output Folder: [path]                  [Browse]     │
├─────────────────────────────────────────────────────┤
│ Conversion Options:                                │
│  ○ Google TTS (gTTS)  ○ Microsoft Edge TTS         │
│                                                     │
│  [Google TTS Options]                               │
│    Language:  [English       ▼]                     │
│    Accent:    [Default       ▼]                     │
│    ☐ Slow speech speed                              │
│                                                     │
│  [Edge TTS Options]                                 │
│    Voice: [en-US-GuyNeural - Male (en-US) ▼]       │
│                                                     │
│  [📑 Select Chapters...]  5/10 chapters selected    │
├─────────────────────────────────────────────────────┤
│ Progress: [████████░░░░] 80%                        │
│ Status: Converting: Chapter 5... (5/10)             │
├─────────────────────────────────────────────────────┤
│ Log:                                                │
│ [Conversion logs appear here]                       │
├─────────────────────────────────────────────────────┤
│ [▶ Convert]  [⏹ Stop]  [🗑 Clear Log]               │
└─────────────────────────────────────────────────────┘
```

### TTS Engine Comparison

| Feature | Google TTS | Edge TTS |
|---------|------------|----------|
| **Voices** | 1 per language | 400+ voices |
| **Quality** | Good | Excellent (neural) |
| **Speed** | Moderate | Fast |
| **Languages** | 15+ | 100+ |
| **Accents** | Limited | Extensive |
| **Best For** | Simple conversions | High-quality audiobooks |

### Edge TTS Voice Selection

Edge TTS offers **400+ voices** in multiple languages. Voices are displayed as:

```
ShortName - Gender (Locale)
Example: en-US-GuyNeural - Male (en-US)
```

**Popular English Voices:**
- `en-US-GuyNeural` - Male (US)
- `en-US-JennyNeural` - Female (US)
- `en-GB-RyanNeural` - Male (UK)
- `en-GB-SoniaNeural` - Female (UK)
- `en-AU-WilliamNeural` - Male (Australian)
- `en-AU-NatashaNeural` - Female (Australian)

### Chapter Selector

Click **📑 Select Chapters...** to open the chapter selection dialog:

```
┌─────────────────────────────────────┐
│     Select Chapters to Convert      │
├─────────────────────────────────────┤
│ ☑ 001. Introduction                 │
│ ☑ 002. Getting Started              │
│ ☐ 003. Advanced Topics              │
│ ☑ 004. Conclusion                   │
├─────────────────────────────────────┤
│ [Select All] [Deselect All] [Invert]│
├─────────────────────────────────────┤
│ Selected: 3 / 4 chapters            │
│      [OK]           [Cancel]        │
└─────────────────────────────────────┘
```

**Features:**
- ✅ Checkboxes for each chapter
- 🔘 **Select All** - Convert all chapters
- ⚪ **Deselect All** - Start fresh
- 🔄 **Invert Selection** - Toggle all selections

### Output File Format

Files are named with chapter numbers for proper ordering:

```
Book_Title_audio/
├── 001_Introduction.mp3
├── 002_Getting_Started.mp3
├── 004_Conclusion.mp3
└── ...
```

Each MP3 includes ID3 tags:
- **Title**: Chapter title
- **Artist**: Book author
- **Album**: Book title
- **Track**: Chapter number
- **Year**: Publication year (if available)

## 🛠️ Troubleshooting

### Common Issues

**1. "No chapters found in EPUB"**
- Some EPUBs have non-standard structures
- Try EPUBs from reputable sources (Project Gutenberg, etc.)

**2. "Failed to parse EPUB file"**
- Ensure the file is a valid EPUB (not DRM-protected)
- Check file extension is `.epub`

**3. Edge TTS voices not loading**
- Check internet connection (voices fetched from Microsoft)
- Verify edge-tts is installed: `pip install edge-tts`

**4. gTTSError: Unable to connect to Google**
- Check your internet connection
- Google may temporarily block excessive requests
- Wait a few minutes and try again

**5. Conversion is slow**
- TTS processes text in chunks; longer chapters take more time
- Internet connection speed affects API response time
- Edge TTS is generally faster than Google TTS

### Logging

The application logs all operations to the log window. For detailed debugging:

```python
# Add this to the top of epub_to_mp3_converter.py
logging.basicConfig(level=logging.DEBUG)
```

## 🎯 Tips for Best Results

### Voice Selection
1. **Preview voices** - Convert a short chapter first to test voice quality
2. **Match voice to content** - Male voices for technical books, female for fiction (personal preference)
3. **Try neural voices** - Edge TTS neural voices sound more natural

### Chapter Management
1. **Skip front/back matter** - Deselect copyright, table of contents chapters
2. **Batch by parts** - Convert Part 1, then Part 2 separately for organization
3. **Test with short chapters** - Verify quality before converting entire book

### Quality Settings
1. **Google TTS**: Use "Slow speed" for clearer narration
2. **Edge TTS**: Neural voices are already high quality at normal speed
3. **Language matching**: Ensure voice locale matches book language

### Organization
1. **Create library folder** - Keep all audiobooks in one place
2. **Use consistent naming** - "Author - Title_audio" format
3. **Backup originals** - Keep EPUB files alongside MP3s

## 🔧 Development

### Project Structure

```
gtts/
├── epub_to_mp3_converter.py   # Main application
├── requirements.txt            # Python dependencies
├── README.md                   # This file
└── .gitignore                  # Git ignore rules
```

### Running from VS Code

1. Open the `gtts` folder in VS Code
2. Open a terminal: `Terminal > New Terminal`
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python epub_to_mp3_converter.py`

Or use the Run button (▶) in VS Code!

### Creating a Standalone App (Optional)

You can create a standalone macOS app using PyInstaller:

```bash
pip install pyinstaller
pyinstaller --windowed --name "EPUB_to_MP3" epub_to_mp3_converter.py
```

The app will be in the `dist/` folder.

## 🤝 Future Enhancements

### Planned Features
- [ ] **Voice Preview**: Play a sample before converting
- [ ] **Batch Processing**: Queue multiple EPUBs
- [ ] **Text Preview**: See chapter text before conversion
- [ ] **Speed Control**: Adjust speech rate (0.5x - 2.0x)
- [ ] **Pitch Control**: Modify voice pitch
- [ ] **Dark Mode**: Toggle dark/light theme
- [ ] **Audiobook Chapters**: Add chapter markers for Apple Books
- [ ] **Export Playlist**: Create M3U playlist for audio players
- [ ] **Merge Chapters**: Combine all chapters into single file
- [ ] **Cloud Sync**: Save settings to iCloud/Dropbox

### Recommendations for Power Users

1. **Use Edge TTS for quality** - Neural voices are superior
2. **Organize by series** - Create folders for book series
3. **Tag consistently** - ID3 tags work with all audio players
4. **Convert overnight** - Long books take time
5. **Test voices first** - Convert chapter 1 with different voices
6. **Keep logs** - Troubleshoot failed conversions
7. **Backup settings** - Note your favorite voice choices

## 📝 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- **gTTS**: Google Text-to-Speech Python library
- **edge-tts**: Microsoft Edge TTS Python library
- **ebooklib**: EPUB handling library
- **Project Gutenberg**: Free ebooks for testing

## 📞 Support

For issues or questions:
1. Check the **Troubleshooting** section
2. Review the **Log** window for errors
3. Ensure all dependencies are installed
4. Verify internet connection

---

**Made with ❤️ for macOS M4**

*Last Updated: March 2026*
