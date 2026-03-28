#!/usr/bin/env python3
"""
EPUB to MP3 Converter using gTTS and Edge TTS
A GUI application to convert EPUB books to MP3 audio files with chapter detection.
Supports both Google TTS and Microsoft Edge TTS voices.
"""

import os
import sys
import asyncio
import threading
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from ebooklib import epub
from bs4 import BeautifulSoup
from gtts import gTTS, gTTSError
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, TDRC, ID3NoHeaderError

# Edge TTS import
try:
    import edge_tts
    from edge_tts import VoicesManager
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("edge-tts not installed. Edge TTS features disabled.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Chapter:
    """Represents a book chapter with title and content."""
    title: str
    content: str
    index: int


@dataclass
class BookMetadata:
    """Stores EPUB book metadata."""
    title: str = "Unknown Title"
    author: str = "Unknown Author"
    language: str = "en"
    year: str = ""


class EPUBParser:
    """Parses EPUB files and extracts chapters and metadata."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.book: Optional[epub.EpubBook] = None
        self.chapters: List[Chapter] = []
        self.metadata: BookMetadata = BookMetadata()
    
    def parse(self) -> bool:
        """Parse the EPUB file and extract chapters and metadata."""
        try:
            self.book = epub.read_epub(self.filepath)
            self._extract_metadata()
            self._extract_chapters()
            return True
        except Exception as e:
            logger.error(f"Error parsing EPUB: {e}")
            return False
    
    def _extract_metadata(self):
        """Extract metadata from the EPUB book."""
        if not self.book:
            return
        
        # Get title
        title = self.book.get_metadata('DC', 'title')
        if title:
            self.metadata.title = str(title[0][0])
        
        # Get author
        creator = self.book.get_metadata('DC', 'creator')
        if creator:
            self.metadata.author = str(creator[0][0])
        
        # Get language
        language = self.book.get_metadata('DC', 'language')
        if language:
            self.metadata.language = str(language[0][0])
        
        # Get year/date
        date = self.book.get_metadata('DC', 'date')
        if date:
            self.metadata.year = str(date[0][0])
        
        logger.info(f"Extracted metadata: {self.metadata}")
    
    def _extract_chapters(self):
        """Extract chapters from the EPUB using table of contents."""
        if not self.book:
            return
        
        self.chapters = []
        chapter_index = 0
        
        # Try to get chapters from table of contents first
        toc = self.book.toc
        if toc:
            logger.info(f"Found {len(toc)} items in table of contents")
            self._process_toc_items(toc, chapter_index)
        else:
            # Fallback: extract from spine items
            self._extract_from_spine()
        
        logger.info(f"Extracted {len(self.chapters)} chapters")
    
    def _process_toc_items(self, toc: list, start_index: int) -> int:
        """Process table of contents items recursively."""
        chapter_index = start_index
        
        for item in toc:
            if isinstance(item, epub.Section):
                # Section header (may not have content)
                if item.title:
                    # Create a chapter with just the title
                    chapter = Chapter(
                        title=item.title,
                        content=item.title,
                        index=chapter_index
                    )
                    self.chapters.append(chapter)
                    chapter_index += 1
            elif isinstance(item, epub.Link):
                # Link to a chapter
                chapter = self._extract_chapter_content(item.href, item.title, chapter_index)
                if chapter:
                    self.chapters.append(chapter)
                    chapter_index += 1
            elif isinstance(item, (list, tuple)):
                # Nested TOC structure
                chapter_index = self._process_toc_items(item, chapter_index)
        
        return chapter_index
    
    def _extract_from_spine(self):
        """Extract chapters from spine items when TOC is not available."""
        if not self.book:
            return
        
        chapter_index = 0
        for item in self.book.spine:
            if isinstance(item, epub.EpubHtml):
                chapter = self._extract_chapter_content(
                    item.id, 
                    item.title, 
                    chapter_index
                )
                if chapter:
                    self.chapters.append(chapter)
                    chapter_index += 1
    
    def _extract_chapter_content(self, href: str, title: str, index: int) -> Optional[Chapter]:
        """Extract text content from a chapter file."""
        if not self.book:
            return None
        
        try:
            # Find the item by href or id
            item = self.book.get_item_with_href(href) or self.book.get_item_with_id(href)
            
            if not item:
                # Try using title as fallback
                for book_item in self.book.get_items_of_kind('document'):
                    if book_item.title == title:
                        item = book_item
                        break
            
            if not item or not hasattr(item, 'content'):
                return None
            
            # Parse HTML content
            content = item.get_content().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract text, removing scripts and styles
            for script in soup(['script', 'style', 'nav', 'header', 'footer']):
                script.decompose()
            
            text = soup.get_text(separator=' ', strip=True)
            
            # Clean up whitespace
            lines = [line.strip() for line in text.splitlines()]
            text = ' '.join(filter(None, lines))
            
            if text:
                chapter_title = title if title else f"Chapter {index + 1}"
                return Chapter(title=chapter_title, content=text, index=index)
        
        except Exception as e:
            logger.error(f"Error extracting chapter {href}: {e}")
        
        return None


class TTSConverter:
    """Converts text to speech using gTTS."""
    
    def __init__(self, language: str = 'en', tld: str = 'com', slow: bool = False):
        self.language = language
        self.tld = tld
        self.slow = slow
        self.current_chapter = 0
        self.total_chapters = 0
        self.should_stop = False
    
    def convert_chapters(
        self, 
        chapters: List[Chapter], 
        output_dir: str,
        metadata: BookMetadata,
        progress_callback=None
    ) -> Tuple[int, int]:
        """
        Convert all chapters to MP3 files.
        Returns tuple of (successful_count, failed_count).
        """
        self.current_chapter = 0
        self.total_chapters = len(chapters)
        self.should_stop = False
        
        successful = 0
        failed = 0
        
        for chapter in chapters:
            if self.should_stop:
                logger.info("Conversion stopped by user")
                break
            
            try:
                self._convert_chapter(chapter, output_dir, metadata)
                successful += 1
            except Exception as e:
                logger.error(f"Failed to convert chapter {chapter.title}: {e}")
                failed += 1
            
            self.current_chapter += 1
            if progress_callback:
                progress_callback(self.current_chapter, self.total_chapters, chapter.title)
        
        return successful, failed
    
    def _convert_chapter(self, chapter: Chapter, output_dir: str, metadata: BookMetadata):
        """Convert a single chapter to MP3 with ID3 tags."""
        # Create filename from chapter title
        safe_title = self._sanitize_filename(chapter.title)
        filename = f"{chapter.index + 1:03d}_{safe_title}.mp3"
        filepath = os.path.join(output_dir, filename)
        
        logger.info(f"Converting chapter {chapter.index + 1}: {chapter.title}")
        
        # Create gTTS object and save
        tts = gTTS(
            text=chapter.content,
            lang=self.language,
            tld=self.tld,
            slow=self.slow
        )
        tts.save(filepath)
        
        # Add ID3 tags
        self._add_id3_tags(filepath, chapter, metadata)
    
    def _add_id3_tags(self, filepath: str, chapter: Chapter, metadata: BookMetadata):
        """Add ID3 metadata tags to MP3 file."""
        try:
            audio = ID3(filepath)
        except ID3NoHeaderError:
            audio = ID3()
        
        # Set metadata tags
        audio['TIT2'] = TIT2(encoding=3, text=chapter.title)
        audio['TPE1'] = TPE1(encoding=3, text=metadata.author)
        audio['TALB'] = TALB(encoding=3, text=metadata.title)
        audio['TRCK'] = TRCK(encoding=3, text=str(chapter.index + 1))
        
        if metadata.year:
            audio['TDRC'] = TDRC(encoding=3, text=metadata.year)
        
        audio.save(filepath)
        logger.info(f"Added ID3 tags to {filepath}")
    
    def _sanitize_filename(self, title: str) -> str:
        """Sanitize chapter title for use as filename."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|？*'
        for char in invalid_chars:
            title = title.replace(char, '_')
        
        # Limit length
        max_length = 100
        if len(title) > max_length:
            title = title[:max_length]
        
        return title.strip()
    
    def stop(self):
        """Signal the converter to stop."""
        self.should_stop = True


class EdgeTTSConverter:
    """Converts text to speech using Microsoft Edge TTS."""
    
    def __init__(self, voice_name: str = 'en-US-GuyNeural'):
        self.voice_name = voice_name
        self.current_chapter = 0
        self.total_chapters = 0
        self.should_stop = False
    
    @staticmethod
    async def get_voices() -> List[Dict[str, str]]:
        """Fetch available Edge TTS voices."""
        if not EDGE_TTS_AVAILABLE:
            return []
        
        try:
            voices = await edge_tts.list_voices()
            return sorted(voices, key=lambda v: v['Name'])
        except Exception as e:
            logger.error(f"Error fetching Edge TTS voices: {e}")
            return []
    
    @staticmethod
    def get_voices_sync() -> List[Dict[str, str]]:
        """Synchronous wrapper for get_voices."""
        if not EDGE_TTS_AVAILABLE:
            return []
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(EdgeTTSConverter.get_voices())
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error getting voices: {e}")
            return []
    
    def convert_chapters(
        self, 
        chapters: List[Chapter], 
        output_dir: str,
        metadata: BookMetadata,
        progress_callback=None
    ) -> Tuple[int, int]:
        """Convert all chapters to MP3 files using Edge TTS."""
        self.current_chapter = 0
        self.total_chapters = len(chapters)
        self.should_stop = False
        
        successful = 0
        failed = 0
        
        for chapter in chapters:
            if self.should_stop:
                logger.info("Conversion stopped by user")
                break
            
            try:
                self._convert_chapter_sync(chapter, output_dir, metadata)
                successful += 1
            except Exception as e:
                logger.error(f"Failed to convert chapter {chapter.title}: {e}")
                failed += 1
            
            self.current_chapter += 1
            if progress_callback:
                progress_callback(self.current_chapter, self.total_chapters, chapter.title)
        
        return successful, failed
    
    def _convert_chapter_sync(self, chapter: Chapter, output_dir: str, metadata: BookMetadata):
        """Synchronous wrapper for chapter conversion."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._convert_chapter(chapter, output_dir, metadata))
        finally:
            loop.close()
    
    async def _convert_chapter(self, chapter: Chapter, output_dir: str, metadata: BookMetadata):
        """Convert a single chapter to MP3 with ID3 tags using Edge TTS."""
        # Create filename from chapter title
        safe_title = self._sanitize_filename(chapter.title)
        filename = f"{chapter.index + 1:03d}_{safe_title}.mp3"
        filepath = os.path.join(output_dir, filename)
        
        logger.info(f"Converting chapter {chapter.index + 1}: {chapter.title} (Edge TTS)")
        
        # Create Edge TTS communication and save
        communicate = edge_tts.Communicate(chapter.content, self.voice_name)
        await communicate.save(filepath)
        
        # Add ID3 tags
        self._add_id3_tags(filepath, chapter, metadata)
    
    def _add_id3_tags(self, filepath: str, chapter: Chapter, metadata: BookMetadata):
        """Add ID3 metadata tags to MP3 file."""
        try:
            audio = ID3(filepath)
        except ID3NoHeaderError:
            audio = ID3()
        
        # Set metadata tags
        audio['TIT2'] = TIT2(encoding=3, text=chapter.title)
        audio['TPE1'] = TPE1(encoding=3, text=metadata.author)
        audio['TALB'] = TALB(encoding=3, text=metadata.title)
        audio['TRCK'] = TRCK(encoding=3, text=str(chapter.index + 1))
        
        if metadata.year:
            audio['TDRC'] = TDRC(encoding=3, text=metadata.year)
        
        audio.save(filepath)
        logger.info(f"Added ID3 tags to {filepath}")
    
    def _sanitize_filename(self, title: str) -> str:
        """Sanitize chapter title for use as filename."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|？*'
        for char in invalid_chars:
            title = title.replace(char, '_')
        
        # Limit length
        max_length = 100
        if len(title) > max_length:
            title = title[:max_length]
        
        return title.strip()
    
    def stop(self):
        """Signal the converter to stop."""
        self.should_stop = True


class ChapterSelector(tk.Toplevel):
    """Dialog for selecting chapters to convert."""
    
    def __init__(self, parent, chapters: List[Chapter]):
        super().__init__(parent)
        self.title("Select Chapters")
        self.geometry("600x500")
        self.transient(parent)
        self.grab_set()
        
        self.chapters = chapters
        self.selected_indices = set(range(len(chapters)))  # All selected by default
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create chapter selection widgets."""
        # Main frame
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Title
        ttk.Label(
            main_frame,
            text="Select Chapters to Convert",
            font=('Helvetica', 14, 'bold')
        ).grid(row=0, column=0, pady=(0, 10))
        
        # Chapter list with checkboxes
        list_frame = ttk.LabelFrame(main_frame, text="Chapters", padding="5")
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Canvas with scrollbar for chapters
        canvas = tk.Canvas(list_frame, height=300)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        
        chapters_inner_frame = ttk.Frame(canvas)
        
        canvas_window = canvas.create_window((0, 0), window=chapters_inner_frame, anchor="nw")
        
        def configure_canvas(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=event.width)
        
        chapters_inner_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", configure_canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Create checkboxes for each chapter
        self.check_vars = []
        for i, chapter in enumerate(self.chapters):
            var = tk.BooleanVar(value=True)
            self.check_vars.append(var)
            
            cb = ttk.Checkbutton(
                chapters_inner_frame,
                text=f"{i+1:03d}. {chapter.title[:60]}{'...' if len(chapter.title) > 60 else ''}",
                variable=var,
                command=lambda idx=i: self._toggle_chapter(idx)
            )
            cb.grid(row=i, column=0, sticky=tk.W, pady=2)
        
        # Selection buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, pady=10)
        
        ttk.Button(
            btn_frame,
            text="Select All",
            command=self._select_all
        ).grid(row=0, column=0, padx=5)
        
        ttk.Button(
            btn_frame,
            text="Deselect All",
            command=self._deselect_all
        ).grid(row=0, column=1, padx=5)
        
        ttk.Button(
            btn_frame,
            text="Invert Selection",
            command=self._invert_selection
        ).grid(row=0, column=2, padx=5)
        
        # Info label
        self.info_label = ttk.Label(
            main_frame,
            text=f"Selected: {len(self.chapters)} / {len(self.chapters)} chapters",
            font=('Helvetica', 10)
        )
        self.info_label.grid(row=3, column=0, pady=5)
        
        # OK/Cancel buttons
        ok_cancel_frame = ttk.Frame(main_frame)
        ok_cancel_frame.grid(row=4, column=0, pady=10)
        
        ttk.Button(
            ok_cancel_frame,
            text="OK",
            command=self._on_ok,
            width=15
        ).grid(row=0, column=0, padx=10)
        
        ttk.Button(
            ok_cancel_frame,
            text="Cancel",
            command=self._on_cancel,
            width=15
        ).grid(row=0, column=1, padx=10)
    
    def _toggle_chapter(self, index: int):
        """Toggle chapter selection."""
        if index in self.selected_indices:
            self.selected_indices.remove(index)
        else:
            self.selected_indices.add(index)
        self._update_info()
    
    def _select_all(self):
        """Select all chapters."""
        self.selected_indices = set(range(len(self.chapters)))
        for var in self.check_vars:
            var.set(True)
        self._update_info()
    
    def _deselect_all(self):
        """Deselect all chapters."""
        self.selected_indices = set()
        for var in self.check_vars:
            var.set(False)
        self._update_info()
    
    def _invert_selection(self):
        """Invert chapter selection."""
        all_indices = set(range(len(self.chapters)))
        self.selected_indices = all_indices - self.selected_indices
        for i, var in enumerate(self.check_vars):
            var.set(i in self.selected_indices)
        self._update_info()
    
    def _update_info(self):
        """Update info label."""
        count = len(self.selected_indices)
        total = len(self.chapters)
        self.info_label.config(text=f"Selected: {count} / {total} chapters")
    
    def _on_ok(self):
        """Handle OK button."""
        self.destroy()
    
    def _on_cancel(self):
        """Handle Cancel button."""
        self.selected_indices = set()
        self.destroy()
    
    def get_selected_chapters(self) -> List[Chapter]:
        """Return list of selected chapters."""
        return [self.chapters[i] for i in sorted(self.selected_indices)]


class ConverterApp:
    """Main GUI application for EPUB to MP3 conversion."""
    
    # Supported languages (common ones)
    LANGUAGES = {
        'English': 'en',
        'Spanish': 'es',
        'French': 'fr',
        'German': 'de',
        'Italian': 'it',
        'Portuguese': 'pt',
        'Dutch': 'nl',
        'Polish': 'pl',
        'Russian': 'ru',
        'Japanese': 'ja',
        'Korean': 'ko',
        'Chinese (Simplified)': 'zh-CN',
        'Chinese (Traditional)': 'zh-TW',
        'Arabic': 'ar',
        'Hindi': 'hi',
    }
    
    # Google TLD options for accents
    TLD_OPTIONS = {
        'Default': 'com',
        'US English': 'com',
        'UK English': 'co.uk',
        'Australian English': 'com.au',
        'Indian English': 'co.in',
        'Canadian French': 'ca',
        'European Spanish': 'es',
        'Latin American Spanish': 'com.mx',
        'European Portuguese': 'pt',
        'Brazilian Portuguese': 'com.br',
    }
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("EPUB to MP3 Converter")
        self.root.geometry("900x750")
        self.root.minsize(800, 650)
        
        # State variables
        self.epub_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.selected_language = tk.StringVar(value='English')
        self.selected_tld = tk.StringVar(value='Default')
        self.slow_speed = tk.BooleanVar(value=False)
        
        # TTS engine selection
        self.tts_engine = tk.StringVar(value='gTTS')
        self.edge_voice = tk.StringVar(value='')
        self.edge_voices: List[Dict[str, str]] = []
        
        self.parser: Optional[EPUBParser] = None
        self.converter: Optional[Any] = None
        self.conversion_thread: Optional[threading.Thread] = None
        self.selected_chapters: List[Chapter] = []
        
        self._setup_styles()
        self._create_widgets()
        self._setup_logging_handler()
        
        # Load Edge TTS voices in background
        if EDGE_TTS_AVAILABLE:
            self._load_edge_voices_async()
    
    def _load_edge_voices_async(self):
        """Load Edge TTS voices in background thread."""
        def load_voices():
            voices = EdgeTTSConverter.get_voices_sync()
            self.edge_voices = voices
            if voices:
                # Set default voice
                self.root.after(0, lambda: self.edge_voice.set(voices[0]['Name']))
                self.root.after(0, self._update_voice_combo)
        
        thread = threading.Thread(target=load_voices, daemon=True)
        thread.start()
    
    def _update_voice_combo(self):
        """Update the voice combo box with loaded voices."""
        if hasattr(self, 'voice_combo') and self.edge_voices:
            voice_names = [f"{v['ShortName']} - {v['Gender']} ({v['Locale']})" for v in self.edge_voices]
            self.voice_combo['values'] = voice_names
            if self.edge_voices:
                self.voice_combo.current(0)
    
    def _setup_styles(self):
        """Configure ttk styles for better appearance."""
        style = ttk.Style()
        
        # Try to use native theme on macOS
        try:
            style.theme_use('aqua')  # macOS native theme
        except:
            style.theme_use('clam')  # Fallback
        
        # Configure custom styles
        style.configure('Title.TLabel', font=('Helvetica', 16, 'bold'))
        style.configure('Status.TLabel', font=('Helvetica', 10))
        style.configure('Progress.Horizontal.TProgressbar', troughcolor='#e0e0e0')
    
    def _create_widgets(self):
        """Create all GUI widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)
        
        # Title
        title_label = ttk.Label(
            main_frame, 
            text="📚 EPUB to MP3 Converter", 
            style='Title.TLabel'
        )
        title_label.grid(row=0, column=0, pady=(0, 15))
        
        # EPUB File Selection
        self._create_file_selection(main_frame, row=1, label="EPUB File:", 
                                   variable=self.epub_path, command=self._browse_epub)
        
        # Output Directory Selection
        self._create_file_selection(main_frame, row=2, label="Output Folder:", 
                                   variable=self.output_path, command=self._browse_output,
                                   is_directory=True)
        
        # Options Frame
        options_frame = ttk.LabelFrame(main_frame, text="Conversion Options", padding="10")
        options_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
        options_frame.columnconfigure(1, weight=1)
        
        # TTS Engine selection
        engine_frame = ttk.Frame(options_frame)
        engine_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Radiobutton(
            engine_frame,
            text="Google TTS (gTTS)",
            variable=self.tts_engine,
            value='gTTS',
            command=self._on_engine_change
        ).grid(row=0, column=0, padx=10)
        
        ttk.Radiobutton(
            engine_frame,
            text="Microsoft Edge TTS",
            variable=self.tts_engine,
            value='edge',
            command=self._on_engine_change
        ).grid(row=0, column=1, padx=10)
        
        # Google TTS options
        self.gtts_options_frame = ttk.LabelFrame(options_frame, text="Google TTS Options", padding="10")
        self.gtts_options_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.gtts_options_frame.columnconfigure(1, weight=1)
        
        # Language selection
        ttk.Label(self.gtts_options_frame, text="Language:").grid(row=0, column=0, sticky=tk.W, pady=5)
        lang_combo = ttk.Combobox(
            self.gtts_options_frame, 
            textvariable=self.selected_language,
            values=list(self.LANGUAGES.keys()),
            state='readonly',
            width=30
        )
        lang_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=10)
        
        # TLD/Accent selection
        ttk.Label(self.gtts_options_frame, text="Accent:").grid(row=1, column=0, sticky=tk.W, pady=5)
        tld_combo = ttk.Combobox(
            self.gtts_options_frame,
            textvariable=self.selected_tld,
            values=list(self.TLD_OPTIONS.keys()),
            state='readonly',
            width=30
        )
        tld_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=10)
        
        # Slow speed option
        slow_check = ttk.Checkbutton(
            self.gtts_options_frame,
            text="Slow speech speed",
            variable=self.slow_speed
        )
        slow_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Edge TTS options
        self.edge_options_frame = ttk.LabelFrame(options_frame, text="Edge TTS Options", padding="10")
        self.edge_options_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.edge_options_frame.columnconfigure(1, weight=1)
        
        ttk.Label(self.edge_options_frame, text="Voice:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.voice_combo = ttk.Combobox(
            self.edge_options_frame,
            textvariable=self.edge_voice,
            state='readonly',
            width=50
        )
        self.voice_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=10)
        
        if not EDGE_TTS_AVAILABLE:
            ttk.Label(
                self.edge_options_frame,
                text="⚠️ edge-tts not installed. Run: pip install edge-tts",
                foreground='red'
            ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Initially hide Edge options
        self._on_engine_change()
        
        # Chapter Selection Button
        chapter_frame = ttk.Frame(options_frame)
        chapter_frame.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=10)
        
        self.chapter_btn = ttk.Button(
            chapter_frame,
            text="📑 Select Chapters...",
            command=self._open_chapter_selector,
            state=tk.DISABLED
        )
        self.chapter_btn.grid(row=0, column=0, padx=5)
        
        self.chapter_count_label = ttk.Label(
            chapter_frame,
            text="No EPUB loaded",
            font=('Helvetica', 9)
        )
        self.chapter_count_label.grid(row=0, column=1, padx=10)
        
        # Progress Section
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=10)
        progress_frame.columnconfigure(0, weight=1)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate',
            style='Progress.Horizontal.TProgressbar'
        )
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.status_label = ttk.Label(
            progress_frame,
            text="Ready to convert",
            style='Status.TLabel'
        )
        self.status_label.grid(row=1, column=0, sticky=tk.W)
        
        # Log/Output Section
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.grid(row=5, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            wrap=tk.WORD,
            font=('Courier', 9)
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Control Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, pady=10)
        
        self.convert_btn = ttk.Button(
            button_frame,
            text="▶ Convert to MP3",
            command=self._start_conversion,
            width=20
        )
        self.convert_btn.grid(row=0, column=0, padx=5)
        
        self.stop_btn = ttk.Button(
            button_frame,
            text="⏹ Stop",
            command=self._stop_conversion,
            state=tk.DISABLED,
            width=20
        )
        self.stop_btn.grid(row=0, column=1, padx=5)
        
        self.clear_btn = ttk.Button(
            button_frame,
            text="🗑 Clear Log",
            command=self._clear_log,
            width=20
        )
        self.clear_btn.grid(row=0, column=2, padx=5)
    
    def _create_file_selection(self, parent, row: int, label: str, 
                               variable: tk.StringVar, command, 
                               is_directory: bool = False):
        """Create a file/directory selection row."""
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=5)
        frame.columnconfigure(1, weight=1)
        
        ttk.Label(frame, text=label, width=15).grid(row=0, column=0, padx=(0, 10))
        
        entry = ttk.Entry(frame, textvariable=variable)
        entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        btn_text = "Browse Folder" if is_directory else "Browse"
        ttk.Button(frame, text=btn_text, command=command, width=12).grid(row=0, column=2)
    
    def _setup_logging_handler(self):
        """Setup logging handler to redirect logs to GUI."""
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                logging.Handler.__init__(self)
                self.text_widget = text_widget
            
            def emit(self, record):
                msg = self.format(record)
                def append():
                    self.text_widget.insert(tk.END, msg + '\n')
                    self.text_widget.see(tk.END)
                self.text_widget.after(0, append)
        
        gui_handler = TextHandler(self.log_text)
        gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(gui_handler)
    
    def _log(self, message: str):
        """Add message to log."""
        self.log_text.insert(tk.END, message + '\n')
        self.log_text.see(tk.END)
    
    def _clear_log(self):
        """Clear the log text."""
        self.log_text.delete(1.0, tk.END)
    
    def _browse_epub(self):
        """Open file dialog to select EPUB file."""
        filepath = filedialog.askopenfilename(
            title="Select EPUB File",
            filetypes=[("EPUB files", "*.epub"), ("All files", "*.*")]
        )
        if filepath:
            self.epub_path.set(filepath)
            # Auto-set output path to same folder as EPUB
            epub_dir = os.path.dirname(filepath)
            epub_name = os.path.splitext(os.path.basename(filepath))[0]
            self.output_path.set(os.path.join(epub_dir, f"{epub_name}_audio"))
    
    def _browse_output(self):
        """Open directory dialog to select output folder."""
        directory = filedialog.askdirectory(title="Select Output Folder")
        if directory:
            self.output_path.set(directory)
    
    def _on_engine_change(self):
        """Handle TTS engine selection change."""
        if self.tts_engine.get() == 'gTTS':
            self.gtts_options_frame.grid()
            self.edge_options_frame.grid_remove()
        else:
            self.gtts_options_frame.grid_remove()
            self.edge_options_frame.grid()
    
    def _open_chapter_selector(self):
        """Open chapter selection dialog."""
        if not self.parser or not self.parser.chapters:
            messagebox.showwarning("Warning", "Please load an EPUB file first")
            return
        
        dialog = ChapterSelector(self.root, self.parser.chapters)
        self.root.wait_window(dialog)
        self.selected_chapters = dialog.get_selected_chapters()
        
        if self.selected_chapters:
            self.chapter_count_label.config(
                text=f"{len(self.selected_chapters)} / {len(self.parser.chapters)} chapters selected"
            )
        else:
            self.chapter_count_label.config(text="No chapters selected")
    
    def _validate_inputs(self) -> bool:
        """Validate user inputs before conversion."""
        if not self.epub_path.get():
            messagebox.showerror("Error", "Please select an EPUB file")
            return False
        
        if not os.path.exists(self.epub_path.get()):
            messagebox.showerror("Error", "EPUB file does not exist")
            return False
        
        if not self.output_path.get():
            messagebox.showerror("Error", "Please select an output folder")
            return False
        
        # Check chapter selection
        if not self.selected_chapters:
            if self.parser and self.parser.chapters:
                # Auto-select all chapters if none selected
                self.selected_chapters = self.parser.chapters.copy()
                self.chapter_count_label.config(
                    text=f"{len(self.selected_chapters)} / {len(self.parser.chapters)} chapters selected"
                )
            else:
                messagebox.showerror("Error", "No chapters available")
                return False
        
        # Validate Edge TTS voice
        if self.tts_engine.get() == 'edge':
            if not self.edge_voice.get():
                messagebox.showerror("Error", "Please select an Edge TTS voice")
                return False
        
        return True
    
    def _start_conversion(self):
        """Start the conversion process in a background thread."""
        if not self._validate_inputs():
            return
        
        # Disable controls during conversion
        self.convert_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.chapter_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)
        
        # Create output directory
        output_dir = self.output_path.get()
        os.makedirs(output_dir, exist_ok=True)
        
        self._log(f"Starting conversion...")
        self._log(f"EPUB: {self.epub_path.get()}")
        self._log(f"Output: {output_dir}")
        self._log(f"TTS Engine: {self.tts_engine.get()}")
        self._log(f"Chapters: {len(self.selected_chapters)}")
        
        # Start conversion in background thread
        self.conversion_thread = threading.Thread(target=self._run_conversion, args=(output_dir,))
        self.conversion_thread.daemon = True
        self.conversion_thread.start()
    
    def _run_conversion(self, output_dir: str):
        """Run the conversion process (in background thread)."""
        try:
            # Parse EPUB if not already done
            if not self.parser:
                self._update_status("Parsing EPUB file...")
                self.parser = EPUBParser(self.epub_path.get())
                
                if not self.parser.parse():
                    self._on_conversion_complete(0, 0, error="Failed to parse EPUB file")
                    return
            
            if not self.selected_chapters:
                self._on_conversion_complete(0, 0, error="No chapters selected")
                return
            
            self._log(f"Title: {self.parser.metadata.title}")
            self._log(f"Author: {self.parser.metadata.author}")
            self._log(f"Language: {self.parser.metadata.language}")
            
            # Setup converter based on engine selection
            if self.tts_engine.get() == 'edge':
                # Extract voice name from display format
                voice_display = self.edge_voice.get()
                voice_name = voice_display.split(' - ')[0] if ' - ' in voice_display else voice_display
                
                self.converter = EdgeTTSConverter(voice_name=voice_name)
                self._log(f"Voice: {voice_name}")
            else:
                # Google TTS
                lang_code = self.LANGUAGES.get(self.selected_language.get(), 'en')
                tld = self.TLD_OPTIONS.get(self.selected_tld.get(), 'com')
                
                self.converter = TTSConverter(
                    language=lang_code,
                    tld=tld,
                    slow=self.slow_speed.get()
                )
                self._log(f"Language: {lang_code} (TLD: {tld})")
                if self.slow_speed.get():
                    self._log("Slow speed: enabled")
            
            # Convert chapters
            self._update_status(f"Converting chapters (0/{len(self.selected_chapters)})")
            
            successful, failed = self.converter.convert_chapters(
                self.selected_chapters,
                output_dir,
                self.parser.metadata,
                progress_callback=self._on_progress
            )
            
            self._on_conversion_complete(successful, failed)
            
        except Exception as e:
            logger.exception(f"Conversion error: {e}")
            self._on_conversion_complete(0, 0, error=str(e))
    
    def _on_progress(self, current: int, total: int, chapter_title: str):
        """Update progress (called from converter thread)."""
        progress = (current / total) * 100
        self.progress_var.set(progress)
        self._update_status(f"Converting: {chapter_title[:50]}... ({current}/{total})")
    
    def _update_status(self, message: str):
        """Update status label (thread-safe)."""
        def update():
            self.status_label.config(text=message)
        self.root.after(0, update)
    
    def _on_conversion_complete(self, successful: int, failed: int, error: str = None):
        """Handle conversion completion (thread-safe)."""
        def complete():
            if error:
                self._log(f"❌ Error: {error}")
                messagebox.showerror("Conversion Error", error)
            else:
                self._log(f"✅ Conversion complete!")
                self._log(f"   Successful: {successful} chapters")
                self._log(f"   Failed: {failed} chapters")
                self._log(f"   Output: {self.output_path.get()}")
                
                message = f"Conversion complete!\n\n"
                message += f"✅ {successful} chapters converted successfully"
                if failed > 0:
                    message += f"\n❌ {failed} chapters failed"
                message += f"\n\nOutput folder:\n{self.output_path.get()}"
                
                messagebox.showinfo("Conversion Complete", message)
            
            # Reset controls
            self.convert_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.chapter_btn.config(state=tk.NORMAL)
            self._update_status("Ready")
        
        self.root.after(0, complete)
    
    def _stop_conversion(self):
        """Stop the conversion process."""
        if self.converter:
            self.converter.stop()
            self._log("⏹ Stopping conversion...")
            self._update_status("Stopping...")


def main():
    """Main entry point."""
    root = tk.Tk()
    
    # Set application icon (if available)
    try:
        # You can add an icon file here
        pass
    except:
        pass
    
    app = ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
