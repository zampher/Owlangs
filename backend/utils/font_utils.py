# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Font utilities for multi-language font registration and management.

This module provides unified font-related logic that can be used across
the entire backend application, including PDF rendering, document export,
and any other components that need font support.

Supports multi-language font registration with cross-platform system font detection.
Prioritizes system fonts, falls back to project fonts, and provides automatic
font registration and fallback handling.
"""

import sys
import platform
import threading
from typing import Optional, Tuple, Dict, List
from pathlib import Path
from logger import unified_logger as logger
from logger.logger import LogModule

try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# TODO: Optional support for TTC (TrueType Collection) files
# Future enhancement: Use fonttools to extract fonts from TTC files
# Requires: pip install fonttools
# Implementation: Extract first font from TTC and save as temporary TTF, then register
# This would enable support for Microsoft YaHei (msyh.ttc) and SimSun (simsun.ttc) on Windows

# Global registry for registered fonts
_registered_fonts: Dict[str, bool] = {}

# Thread-safe font registration state
_font_registration_lock = threading.Lock()
_font_registration_thread: Optional[threading.Thread] = None
_font_registration_in_progress = False
_font_registration_complete = False


class FontConfig:
    """Font configuration for a language."""
    
    def __init__(
        self,
        language_code: str,
        system_fonts: List[Tuple[str, str]],  # List of (font_name, font_path_pattern)
        project_fonts: List[Tuple[str, str]],  # List of (font_name, relative_path)
        fallback_font: str = "Helvetica",
    ):
        """
        Initialize font configuration.
        
        Args:
            language_code: Language code (e.g., 'zh', 'ja', 'ko', 'en', 'fr', 'de', etc.)
            system_fonts: List of (font_name, font_path_pattern) for system fonts
            project_fonts: List of (font_name, relative_path) for project fonts
            fallback_font: Fallback font name if no fonts are available
        """
        self.language_code = language_code
        self.system_fonts = system_fonts
        self.project_fonts = project_fonts
        self.fallback_font = fallback_font


class FontUtils:
    """
    Font utilities.
    
    Provides methods for font registration, language-based font selection,
    and font fallback handling with multi-language and cross-platform support.
    """
    
    # Language font configurations
    # Priority: system fonts first, then project fonts, finally fallback
    LANGUAGE_FONT_CONFIGS: Dict[str, FontConfig] = {
        # Chinese (Simplified and Traditional)
        'zh': FontConfig(
            language_code='zh',
            system_fonts=[
                # Windows - Prefer TTF files (ReportLab does not support TTC directly)
                # Note: SimSun and Microsoft YaHei are only available as TTC on Windows
                # If fonttools is installed, TTC files can be extracted and used
                ("SimHei", "C:/Windows/Fonts/simhei.ttf"),
                ("STSong", "C:/Windows/Fonts/stsong.ttf"),
                ("STSong", "C:/Windows/Fonts/STSONG.TTF"),  # Alternative case
                ("Microsoft YaHei", "C:/Windows/Fonts/msyh.ttc"),  # TTC - requires fonttools
                ("SimSun", "C:/Windows/Fonts/simsun.ttc"),  # TTC - requires fonttools
                ("STXiHei", "C:/Windows/Fonts/STXIHEI.TTF"),  # STXiHei (ST细黑)
                ("SimSun Bold", "C:/Windows/Fonts/simsunb.ttf"),  # SimSun Bold variant
                ("SimKai", "C:/Windows/Fonts/simkai.ttf"),  # SimKai (楷体)
                ("SimLi", "C:/Windows/Fonts/SIMLI.TTF"),  # SimLi (隶书)
                ("SimYou", "C:/Windows/Fonts/SIMYOU.TTF"),  # SimYou (幼圆)
                ("STHeiti", "C:/Windows/Fonts/stheiti.ttf"),
                # macOS - Note: macOS fonts are often TTC, but we keep them for reference
                # They will be skipped during registration if TTC format is detected
                ("PingFang SC", "/System/Library/Fonts/PingFang.ttc"),
                ("STHeiti", "/System/Library/Fonts/STHeiti Light.ttc"),
                ("STSong", "/System/Library/Fonts/STSong.ttc"),
                # Linux - Note: Linux fonts may be TTC, but we keep them for reference
                # They will be skipped during registration if TTC format is detected
                ("WenQuanYi Micro Hei", "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc"),
                ("WenQuanYi Zen Hei", "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc"),
                ("Noto Sans CJK SC", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            ],
            project_fonts=[
                ("NotoSansSC", "NotoSansSC-Regular.ttf"),
            ],
            fallback_font="Helvetica",
        ),
        
        # Japanese
        'ja': FontConfig(
            language_code='ja',
            system_fonts=[
                # Windows - Only TTF files (ReportLab does not support TTC)
                # Note: MS Gothic and MS Mincho may only be available as TTC on some systems
                # If TTF versions are not found, these will be skipped
                ("MS Gothic", "C:/Windows/Fonts/msgothic.ttf"),
                ("MS Mincho", "C:/Windows/Fonts/msmincho.ttf"),
                ("Yu Gothic", "C:/Windows/Fonts/yugothic.ttf"),
                # macOS - Note: macOS fonts are often TTC, but we keep them for reference
                ("Hiragino Sans", "/System/Library/Fonts/Hiragino Sans GB.ttc"),
                ("Yu Gothic", "/System/Library/Fonts/Yu Gothic.ttc"),
                # Linux - Note: Linux fonts may be TTC, but we keep them for reference
                ("Noto Sans CJK JP", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            ],
            project_fonts=[
                ("NotoSans", "NotoSans-Regular.ttf"),  # NotoSans supports Japanese
            ],
            fallback_font="Helvetica",
        ),
        
        # Korean
        'ko': FontConfig(
            language_code='ko',
            system_fonts=[
                # Windows - Only TTF files (ReportLab does not support TTC)
                ("Malgun Gothic", "C:/Windows/Fonts/malgun.ttf"),
                ("Batang", "C:/Windows/Fonts/batang.ttf"),
                ("Gulim", "C:/Windows/Fonts/gulim.ttf"),
                # macOS - Note: macOS fonts are often TTC, but we keep them for reference
                ("Apple SD Gothic Neo", "/System/Library/Fonts/AppleSDGothicNeo.ttc"),
                ("Nanum Gothic", "/System/Library/Fonts/NanumGothic.ttc"),
                # Linux - Note: Linux fonts may be TTC, but we keep them for reference
                ("Noto Sans CJK KR", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            ],
            project_fonts=[
                ("NotoSansKR", "NotoSansKR-Regular.ttf"),
                ("NotoSans", "NotoSans-Regular.ttf"),  # Fallback
            ],
            fallback_font="Helvetica",
        ),
        
        # English and other Latin-based languages
        'en': FontConfig(
            language_code='en',
            system_fonts=[
                # Windows
                ("Times New Roman", "C:/Windows/Fonts/times.ttf"),
                ("Arial", "C:/Windows/Fonts/arial.ttf"),
                ("Calibri", "C:/Windows/Fonts/calibri.ttf"),
                # macOS - Note: macOS fonts are often TTC, but we keep them for reference
                ("Times", "/System/Library/Fonts/Times.ttc"),
                ("Arial", "/System/Library/Fonts/Arial.ttf"),
                ("Helvetica", "/System/Library/Fonts/Helvetica.ttc"),
                # Linux
                ("Liberation Serif", "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
                ("DejaVu Serif", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
            ],
            project_fonts=[
                ("NotoSans", "NotoSans-Regular.ttf"),
            ],
            fallback_font="Helvetica",
        ),
        
        # French, German, Spanish, Italian, Portuguese, etc. (Latin-based)
        'fr': FontConfig(
            language_code='fr',
            system_fonts=[
                ("Times New Roman", "C:/Windows/Fonts/times.ttf"),
                ("Arial", "C:/Windows/Fonts/arial.ttf"),
                # macOS - Note: macOS fonts are often TTC, but we keep them for reference
                ("Times", "/System/Library/Fonts/Times.ttc"),
            ],
            project_fonts=[
                ("NotoSans", "NotoSans-Regular.ttf"),
            ],
            fallback_font="Helvetica",
        ),
        
        # Russian
        'ru': FontConfig(
            language_code='ru',
            system_fonts=[
                # Windows
                ("Times New Roman", "C:/Windows/Fonts/times.ttf"),
                ("Arial", "C:/Windows/Fonts/arial.ttf"),
                # macOS/Linux - Note: macOS fonts are often TTC, but we keep them for reference
                ("Times", "/System/Library/Fonts/Times.ttc"),
                ("DejaVu Serif", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
            ],
            project_fonts=[
                ("NotoSans", "NotoSans-Regular.ttf"),
            ],
            fallback_font="Helvetica",
        ),
        
        # Arabic
        'ar': FontConfig(
            language_code='ar',
            system_fonts=[
                # Windows
                ("Arial Unicode MS", "C:/Windows/Fonts/arialuni.ttf"),
                ("Tahoma", "C:/Windows/Fonts/tahoma.ttf"),
                # macOS
                ("Arial Unicode MS", "/System/Library/Fonts/Arial Unicode.ttf"),
                # Linux
                ("Noto Sans Arabic", "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"),
            ],
            project_fonts=[
                ("NotoSans", "NotoSans-Regular.ttf"),  # NotoSans supports Arabic
            ],
            fallback_font="Helvetica",
        ),
        
        # Thai
        'th': FontConfig(
            language_code='th',
            system_fonts=[
                # Windows
                ("Tahoma", "C:/Windows/Fonts/tahoma.ttf"),
                ("Angsana New", "C:/Windows/Fonts/angsana.ttf"),
                # macOS - Note: macOS fonts are often TTC, but we keep them for reference
                ("Thonburi", "/System/Library/Fonts/Thonburi.ttc"),
                # Linux
                ("Noto Sans Thai", "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
            ],
            project_fonts=[
                ("NotoSans", "NotoSans-Regular.ttf"),  # NotoSans supports Thai
            ],
            fallback_font="Helvetica",
        ),
        
        # Vietnamese
        'vi': FontConfig(
            language_code='vi',
            system_fonts=[
                ("Times New Roman", "C:/Windows/Fonts/times.ttf"),
                ("Arial", "C:/Windows/Fonts/arial.ttf"),
            ],
            project_fonts=[
                ("NotoSans", "NotoSans-Regular.ttf"),
            ],
            fallback_font="Helvetica",
        ),
        
        # Hebrew
        'he': FontConfig(
            language_code='he',
            system_fonts=[
                # Windows
                ("Arial Unicode MS", "C:/Windows/Fonts/arialuni.ttf"),
                ("David", "C:/Windows/Fonts/david.ttf"),
                # macOS
                ("Arial Hebrew", "/System/Library/Fonts/Arial Hebrew.ttf"),
                # Linux
                ("Noto Sans Hebrew", "/usr/share/fonts/truetype/noto/NotoSansHebrew-Regular.ttf"),
            ],
            project_fonts=[
                ("NotoSans", "NotoSans-Regular.ttf"),  # NotoSans supports Hebrew
            ],
            fallback_font="Helvetica",
        ),
        
        # Hindi
        'hi': FontConfig(
            language_code='hi',
            system_fonts=[
                # Windows
                ("Mangal", "C:/Windows/Fonts/mangal.ttf"),
                ("Arial Unicode MS", "C:/Windows/Fonts/arialuni.ttf"),
                # Linux
                ("Noto Sans Devanagari", "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
            ],
            project_fonts=[
                ("NotoSans", "NotoSans-Regular.ttf"),  # NotoSans supports Devanagari
            ],
            fallback_font="Helvetica",
        ),
    }
    
    @staticmethod
    def _get_system_font_directories() -> List[Path]:
        """
        Get system font directories based on platform.
        
        Returns:
            List of font directory paths
        """
        system = platform.system()
        font_dirs = []
        
        if system == "Windows":
            font_dirs = [Path("C:/Windows/Fonts")]
        elif system == "Darwin":  # macOS
            font_dirs = [
                Path("/System/Library/Fonts"),
                Path("/Library/Fonts"),
                Path.home() / "Library/Fonts",
            ]
        elif system == "Linux":
            font_dirs = [
                Path("/usr/share/fonts"),
                Path("/usr/local/share/fonts"),
                Path.home() / ".fonts",
                Path.home() / ".local/share/fonts",
            ]
        
        return font_dirs
    
    @staticmethod
    def _find_font_file(font_path_pattern: str) -> Optional[Path]:
        """
        Find font file by path pattern, checking system font directories.
        
        Optimized to avoid slow glob operations on Windows font directories.
        
        Args:
            font_path_pattern: Font path pattern (absolute or relative to system font dirs)
            
        Returns:
            Path to font file if found, None otherwise
        """
        # If absolute path exists, use it
        abs_path = Path(font_path_pattern)
        if abs_path.is_absolute() and abs_path.exists():
            return abs_path
        
        # Try system font directories
        font_name = abs_path.name
        for font_dir in FontUtils._get_system_font_directories():
            if not font_dir.exists():
                continue
            
            # Try exact path first (fastest)
            full_path = font_dir / font_name
            if full_path.exists():
                return full_path
            
            # For Windows, try case-insensitive match (but avoid slow glob)
            if sys.platform == "win32":
                try:
                    # Only try glob if exact match failed and font_name is short (avoid slow operations)
                    if len(font_name) < 50:  # Reasonable limit to avoid slow glob on large directories
                        # Try lowercase and uppercase variants directly (faster than glob)
                        lower_path = font_dir / font_name.lower()
                        upper_path = font_dir / font_name.upper()
                        if lower_path.exists():
                            return lower_path
                        if upper_path.exists():
                            return upper_path
                except Exception:
                    pass
        
        return None
    
    @staticmethod
    def register_fonts_for_language(language_code: str, force_reregister: bool = False) -> None:
        """
        Register fonts for a specific language.
        
        Args:
            language_code: Language code (e.g., 'zh', 'ja', 'ko', 'en', 'fr', etc.)
            force_reregister: If True, re-scan system fonts even if font name is already registered.
                            This is useful when system fonts may have been installed after startup.
        """
        global _registered_fonts
        
        if not REPORTLAB_AVAILABLE:
            return
        
        if language_code not in FontUtils.LANGUAGE_FONT_CONFIGS:
            logger.debug(LogModule.FONT, f" No font configuration for language: {language_code}, using default")
            return
        
        config = FontUtils.LANGUAGE_FONT_CONFIGS[language_code]
        
        # Get project fonts directory
        # From utils/, go up to backend/, then to static/flutter-web/assets/fonts
        current_file = Path(__file__)
        project_fonts_dir = current_file.parent.parent / "static" / "flutter-web" / "assets" / "fonts"
        
        # Register system fonts first (priority 1)
        # Limit the number of attempts to avoid performance issues
        max_attempts = 20  # Reasonable limit per language
        attempts = 0
        for font_name, font_path_pattern in config.system_fonts:
            if attempts >= max_attempts:
                break  # Stop after reasonable number of attempts
            
            # If force_reregister is False and font is already registered, skip
            # If force_reregister is True, always re-scan to find newly installed fonts
            if not force_reregister and font_name in _registered_fonts:
                continue  # Already registered
            
            attempts += 1
            font_path = FontUtils._find_font_file(font_path_pattern)
            if font_path and font_path.exists():
                # ReportLab's TTFont does NOT support TTC (TrueType Collection) files
                # Only TTF (TrueType Font) files are supported
                if font_path.suffix.lower() == '.ttc':
                    # ReportLab's TTFont does NOT support TTC (TrueType Collection) files
                    # TODO: Future enhancement - Use fonttools to extract fonts from TTC files
                    # This would enable support for Microsoft YaHei (msyh.ttc) and SimSun (simsun.ttc) on Windows
                    # Implementation: Extract first font from TTC using fonttools, save as temporary TTF, then register
                    # Note: Removed verbose debug log for TTC skipping (normal case, only log on first occurrence per font)
                    continue  # Skip TTC files, try next font
                
                try:
                    # If font is already registered, unregister it first (for force_reregister case)
                    if font_name in _registered_fonts and force_reregister:
                        try:
                            pdfmetrics.unregisterFont(font_name)
                        except Exception:
                            pass  # Font may not be registered in pdfmetrics yet
                    
                    # TTFont() registers the font to pdfmetrics automatically
                    # TTFont only supports TTF files, not TTC files
                    # Check file size and existence before attempting registration
                    try:
                        font_path.stat().st_size  # Check file exists and is accessible
                    except Exception as stat_error:
                        logger.warning(LogModule.FONT, f" Cannot stat font file {font_path}: {stat_error}")
                        continue
                    
                    try:
                        # Create TTFont object
                        font_obj = TTFont(font_name, str(font_path))
                        # Explicitly register the font with pdfmetrics
                        # TTFont() creates the object but may not automatically register it
                        pdfmetrics.registerFont(font_obj)
                        # Note: Removed verbose debug logs for successful TTFont creation/registration
                    except Exception as ttf_error:
                        logger.warning(LogModule.FONT, f" Failed to create or register TTFont for {font_name} from {font_path}: {ttf_error}")
                        continue
                    
                    # Verify font is actually available in pdfmetrics
                    # Some fonts may fail to register silently
                    font_verified = False
                    try:
                        font_obj = pdfmetrics.getFont(font_name)
                        if font_obj is not None:
                            font_verified = True
                            # Note: Removed verbose debug log for successful verification
                    except Exception as verify_error:
                        # pdfmetrics.getFont() raises exception if font not found
                        # The exception message is usually the font name
                        error_msg = str(verify_error)
                        if error_msg == font_name or f"'{font_name}'" in error_msg:
                            # This is the expected error when font is not found
                            logger.warning(
                                LogModule.FONT,
                                f" TTFont() succeeded but font {font_name} not found in pdfmetrics. "
                                f"TTFont may have failed silently. Error: {verify_error}"
                            )
                        else:
                            logger.warning(LogModule.FONT, f" Unexpected error checking font {font_name} in pdfmetrics: {verify_error}")
                    
                    if font_verified:
                        _registered_fonts[font_name] = True
                        logger.info(LogModule.FONT, f" ✓ Successfully registered system font: {font_name} from {font_path}")
                    else:
                        # Try alternative: check if font is in registered font names list
                        try:
                            registered_names = pdfmetrics.getRegisteredFontNames()
                            if font_name in registered_names:
                                _registered_fonts[font_name] = True
                                logger.info(
                                    LogModule.FONT,
                                    f" ✓ Registered system font: {font_name} from {font_path} "
                                    f"(found in getRegisteredFontNames but getFont failed)"
                                )
                            else:
                                logger.warning(
                                    LogModule.FONT,
                                    f" Font {font_name} not in pdfmetrics.getRegisteredFontNames() either. "
                                    f"TTFont() call succeeded but font was not registered."
                                )
                        except Exception as list_error:
                            logger.warning(
                                LogModule.FONT,
                                f" Error calling getRegisteredFontNames(): {list_error}"
                            )
                    # Continue to try other fonts (we want multiple options for fallback)
                except Exception as e:
                    logger.debug(LogModule.FONT, f" Failed to register system font {font_name} from {font_path_pattern}: {e}")
        
        # Register project fonts (priority 2)
        if project_fonts_dir.exists():
            for font_name, relative_path in config.project_fonts:
                # If force_reregister is False and font is already registered, skip
                if not force_reregister and font_name in _registered_fonts:
                    continue  # Already registered
                
                font_path = project_fonts_dir / relative_path
                if font_path.exists():
                    try:
                        # If font is already registered, unregister it first (for force_reregister case)
                        if font_name in _registered_fonts and force_reregister:
                            try:
                                pdfmetrics.unregisterFont(font_name)
                            except Exception:
                                pass  # Font may not be registered in pdfmetrics yet
                        
                        # Create TTFont object and explicitly register it
                        try:
                            font_obj = TTFont(font_name, str(font_path))
                            # Explicitly register the font with pdfmetrics
                            pdfmetrics.registerFont(font_obj)
                            logger.debug(LogModule.FONT, f" Created and registered project font {font_name} from {font_path}")
                        except Exception as ttf_error:
                            logger.warning(LogModule.FONT, f" Failed to create or register TTFont for {font_name} from {font_path}: {ttf_error}")
                            continue
                        
                        # Verify font is actually available in pdfmetrics
                        font_verified = False
                        try:
                            font_obj = pdfmetrics.getFont(font_name)
                            if font_obj is not None:
                                font_verified = True
                                logger.debug(
                                    LogModule.FONT,
                                    f" Font {font_name} verified in pdfmetrics.getFont()"
                                )
                        except Exception as verify_error:
                            error_msg = str(verify_error)
                            logger.debug(
                                LogModule.FONT,
                                f" pdfmetrics.getFont('{font_name}') raised: {verify_error}"
                            )
                            if error_msg == font_name or f"'{font_name}'" in error_msg:
                                logger.warning(
                                    LogModule.FONT,
                                    f" TTFont() and registerFont() succeeded but font {font_name} not found in pdfmetrics. "
                                    f"Error: {verify_error}"
                                )
                            else:
                                logger.warning(LogModule.FONT, f" Unexpected error checking font {font_name} in pdfmetrics: {verify_error}")
                        
                        if font_verified:
                            _registered_fonts[font_name] = True
                            logger.info(LogModule.FONT, f" ✓ Successfully registered project font: {font_name} from {font_path}")
                        else:
                            # Try alternative: check if font is in registered font names list
                            try:
                                registered_names = pdfmetrics.getRegisteredFontNames()
                                logger.debug(
                                    LogModule.FONT,
                                    f" Checking getRegisteredFontNames() for {font_name}. "
                                    f"Current registered fonts: {registered_names}"
                                )
                                if font_name in registered_names:
                                    _registered_fonts[font_name] = True
                                    logger.info(
                                        LogModule.FONT,
                                        f" ✓ Registered project font: {font_name} from {font_path} "
                                        f"(found in getRegisteredFontNames but getFont failed)"
                                    )
                                else:
                                    logger.warning(
                                        LogModule.FONT,
                                        f" Font {font_name} not in pdfmetrics.getRegisteredFontNames() either. "
                                        f"registerFont() call succeeded but font was not registered."
                                    )
                            except Exception as list_error:
                                logger.warning(
                                    LogModule.FONT,
                                    f" Error calling getRegisteredFontNames(): {list_error}"
                                )
                    except Exception as e:
                        logger.debug(LogModule.FONT, f" Failed to register project font {font_name} from {font_path}: {e}")
    
    @staticmethod
    def register_all_fonts(background: bool = True) -> None:
        """
        Register fonts for all supported languages.
        This is the unified method to replace register_chinese_fonts().
        
        Optimized to register fonts efficiently and log progress.
        Only registers fonts that haven't been registered yet to avoid duplicate work.
        
        Args:
            background: If True, register fonts in a background thread (non-blocking).
                       If False, register fonts synchronously in the current thread.
        """
        global _font_registration_thread, _font_registration_in_progress, _font_registration_complete
        
        with _font_registration_lock:
            # Check if fonts are already registered (avoid re-registration)
            if _font_registration_complete or len(_registered_fonts) > 0:
                logger.debug(
                    LogModule.FONT,
                    f" Fonts already registered ({len(_registered_fonts)} fonts), skipping registration"
                )
                return
            
            # Check if registration is already in progress
            if _font_registration_in_progress:
                logger.debug(LogModule.FONT, " Font registration already in progress in background thread")
                return
        
        if background:
            # Start background thread for font registration
            def _register_fonts_background():
                global _font_registration_in_progress, _font_registration_complete
                try:
                    with _font_registration_lock:
                        _font_registration_in_progress = True
                    
                    FontUtils._register_all_fonts_sync()
                    
                    with _font_registration_lock:
                        _font_registration_complete = True
                        _font_registration_in_progress = False
                except Exception as e:
                    logger.warning(LogModule.SYSTEM, f" Background font registration failed: {e}")
                    with _font_registration_lock:
                        _font_registration_in_progress = False
            
            with _font_registration_lock:
                if _font_registration_thread is None or not _font_registration_thread.is_alive():
                    _font_registration_thread = threading.Thread(
                        target=_register_fonts_background,
                        name="FontRegistration",
                        daemon=True
                    )
                    _font_registration_thread.start()
                    logger.info(
                        LogModule.FONT,
                        " Started background thread for font registration (non-blocking)"
                    )
        else:
            # Synchronous registration
            FontUtils._register_all_fonts_sync()
    
    @staticmethod
    def _register_all_fonts_sync() -> None:
        """
        Internal method to register all fonts synchronously.
        This is called by register_all_fonts() either directly or from background thread.
        """
        logger.info(LogModule.FONT, " _register_all_fonts_sync() called - starting font registration")
        import time
        start_time = time.time()
        
        # Log currently registered fonts in pdfmetrics before registration
        if REPORTLAB_AVAILABLE:
            try:
                # Get all registered font names from pdfmetrics
                registered_in_pdfmetrics = list(pdfmetrics.getRegisteredFontNames())
                logger.debug(LogModule.FONT, f" Fonts already in pdfmetrics before registration: {registered_in_pdfmetrics}")
            except Exception as e:
                logger.debug(LogModule.FONT, f" Could not list fonts in pdfmetrics: {e}")
        
        logger.debug(LogModule.FONT, f" Starting font registration for {len(FontUtils.LANGUAGE_FONT_CONFIGS)} languages")
        
        # Register fonts for all configured languages
        # Priority: Register common languages first (zh, en, ja, ko) for faster initial font availability
        priority_languages = ['zh', 'en', 'ja', 'ko']
        other_languages = [lang for lang in FontUtils.LANGUAGE_FONT_CONFIGS.keys() if lang not in priority_languages]
        
        registered_count = 0
        for language_code in priority_languages + other_languages:
            if language_code not in FontUtils.LANGUAGE_FONT_CONFIGS:
                continue
            try:
                before_count = len(_registered_fonts)
                FontUtils.register_fonts_for_language(language_code)
                after_count = len(_registered_fonts)
                if after_count > before_count:
                    registered_count += (after_count - before_count)
            except Exception as e:
                logger.debug(LogModule.FONT, f" Failed to register fonts for language {language_code}: {e}")
        
        elapsed_time = time.time() - start_time
        
        # Log fonts actually registered in pdfmetrics after registration
        if REPORTLAB_AVAILABLE:
            try:
                registered_in_pdfmetrics_after = list(pdfmetrics.getRegisteredFontNames())
                logger.info(LogModule.SYSTEM, f" Fonts actually in pdfmetrics after registration: {registered_in_pdfmetrics_after}")
            except Exception as e:
                logger.debug(LogModule.FONT, f" Could not list fonts in pdfmetrics after registration: {e}")
        
        logger.info(LogModule.FONT, f" Font registration completed: {registered_count} new fonts registered "
            f"({len(_registered_fonts)} total) in {elapsed_time:.2f}s")
        
        # Send macOS launch complete signal after font registration - outside any try-except to ensure it runs
        logger.info(LogModule.FONT, " ======================================")
        logger.info(LogModule.FONT, " Attempting to send macOS launch complete signal...")
        logger.info(LogModule.FONT, " ======================================")
        
        # Directly send the signal without complex error handling
        import sys
        logger.info(LogModule.FONT, f" Current platform: {sys.platform}")
        if sys.platform == 'darwin':
            logger.info(LogModule.FONT, " Detected macOS, proceeding to send launch signal...")
            
            # Try to import and send the signal
            try:
                from backend.utils.macos_launch_signal import send_launch_complete_signal
                logger.info(LogModule.FONT, " Import successful from backend.utils.macos_launch_signal")
            except ImportError:
                try:
                    from utils.macos_launch_signal import send_launch_complete_signal
                    logger.info(LogModule.FONT, " Import successful from utils.macos_launch_signal")
                except ImportError as e:
                    logger.warning(LogModule.FONT, " ======================================")
                    logger.warning(LogModule.FONT, f" Failed to import macOS launch signal module: {e}")
                    logger.warning(LogModule.FONT, " ======================================")
                    return
            
            try:
                send_launch_complete_signal()
                logger.info(LogModule.FONT, " macOS launch complete signal sent successfully")
            except Exception as e:
                logger.warning(LogModule.FONT, " ======================================")
                logger.warning(LogModule.FONT, f" Failed to send macOS launch signal: {e}")
                logger.warning(LogModule.FONT, " ======================================")
        else:
            logger.info(LogModule.FONT, f" Not on macOS ({sys.platform}), skipping launch signal")
        
        logger.info(LogModule.FONT, " ======================================")
        logger.info(LogModule.FONT, " Launch signal sending attempt completed")
        logger.info(LogModule.FONT, " ======================================")
    
    @staticmethod
    def wait_for_font_registration(timeout: Optional[float] = None) -> bool:
        """
        Wait for background font registration to complete.
        
        Args:
            timeout: Maximum time to wait in seconds. If None, wait indefinitely.
            
        Returns:
            True if registration completed, False if timeout or error occurred.
        """
        global _font_registration_thread, _font_registration_complete
        
        with _font_registration_lock:
            if _font_registration_complete:
                return True
            if not _font_registration_in_progress or _font_registration_thread is None:
                return True  # No registration in progress
        
        if _font_registration_thread:
            _font_registration_thread.join(timeout=timeout)
            with _font_registration_lock:
                return _font_registration_complete
        
        return False
    
    @staticmethod
    def register_chinese_fonts() -> None:
        """
        Register Chinese fonts for ReportLab if available.
        
        DEPRECATED: Use register_all_fonts() instead for multi-language support.
        This method is kept for backward compatibility.
        """
        FontUtils.register_fonts_for_language('zh')
    
    @staticmethod
    def normalize_language_code(lang: str) -> str:
        """
        Normalize language code to standard format.
        
        Args:
            lang: Language code or name (e.g., "Chinese", "zh", "zh-CN", "French", "fr", etc.)
            
        Returns:
            Normalized language code: 'zh', 'ja', 'ko', 'en', 'fr', 'de', 'es', 'it', 'pt', 'ru', 'ar', 'th', 'vi', 'he', 'hi', etc.
        """
        if not lang:
            return 'en'
        
        lang_lower = lang.lower().strip()
        
        # Chinese variants
        if lang_lower in ('chinese', 'zh', 'zh-cn', 'zh-tw', 'zh-hans', 'zh-hant', 'cn'):
            return 'zh'
        # Japanese variants
        elif lang_lower in ('japanese', 'ja', 'ja-jp', 'jp'):
            return 'ja'
        # Korean variants
        elif lang_lower in ('korean', 'ko', 'ko-kr', 'kr'):
            return 'ko'
        # French variants
        elif lang_lower in ('french', 'fr', 'français', 'francais'):
            return 'fr'
        # German variants
        elif lang_lower in ('german', 'de', 'deutsch'):
            return 'de'
        # Spanish variants
        elif lang_lower in ('spanish', 'es', 'español', 'espanol'):
            return 'es'
        # Italian variants
        elif lang_lower in ('italian', 'it', 'italiano'):
            return 'it'
        # Portuguese variants
        elif lang_lower in ('portuguese', 'pt', 'português', 'portugues'):
            return 'pt'
        # Russian variants
        elif lang_lower in ('russian', 'ru', 'русский', 'russkiy'):
            return 'ru'
        # Arabic variants
        elif lang_lower in ('arabic', 'ar', 'العَرَبِيَّة'):
            return 'ar'
        # Thai variants
        elif lang_lower in ('thai', 'th', 'ไทย'):
            return 'th'
        # Vietnamese variants
        elif lang_lower in ('vietnamese', 'vi', 'tiếng việt', 'tieng viet'):
            return 'vi'
        # Hebrew variants
        elif lang_lower in ('hebrew', 'he', 'עברית'):
            return 'he'
        # Hindi variants
        elif lang_lower in ('hindi', 'hi', 'हिन्दी', 'hindī'):
            return 'hi'
        # English (default)
        else:
            return 'en'
    
    @staticmethod
    def get_font_name_for_language(
        lang: str,
        target_language: Optional[str] = None,
        registered_fonts: Optional[Dict[str, bool]] = None,
        auto_register: bool = True,
    ) -> str:
        """
        Get appropriate font name for language.
        
        Args:
            lang: Language code ('zh', 'ja', 'ko', 'en', 'fr', 'de', etc.)
            target_language: Optional target language code/name for fallback
            registered_fonts: Optional dict of registered fonts (defaults to global _registered_fonts)
            auto_register: If True, automatically register fonts for the language if not already registered
            
        Returns:
            Font name to use
        """
        # Always use global _registered_fonts directly to ensure thread-safety
        # and see latest updates from background registration thread
        # (registered_fonts parameter is kept for backward compatibility but not used)
        
        # Normalize language code
        lang_normalized = FontUtils.normalize_language_code(lang) if lang != 'other' else None
        
        # If language is 'other' or not detected, use target_language as fallback
        if not lang_normalized or lang_normalized == 'en':
            if target_language:
                target_lang_normalized = FontUtils.normalize_language_code(target_language)
                if target_lang_normalized != 'en':
                    # Use target language font if it's not English
                    lang_normalized = target_lang_normalized
            else:
                lang_normalized = 'en'
        
        # Get font configuration for language
        if lang_normalized not in FontUtils.LANGUAGE_FONT_CONFIGS:
            # Unknown language, use English config
            lang_normalized = 'en'
        
        # Auto-register fonts for this language if needed
        if auto_register and lang_normalized in FontUtils.LANGUAGE_FONT_CONFIGS:
            # Wait for background font registration to complete before checking
            # Use longer timeout to ensure fonts are available
            FontUtils.wait_for_font_registration(timeout=2.0)
            
            # Check if fonts are already registered before attempting to register again
            config_check = FontUtils.LANGUAGE_FONT_CONFIGS[lang_normalized]
            all_fonts_check = config_check.system_fonts + config_check.project_fonts
            has_registered_font = any(font_name in _registered_fonts for font_name, _ in all_fonts_check)
            
            if not has_registered_font:
                logger.debug(LogModule.FONT, f"No fonts registered for language {lang_normalized}, registering now. "
                    f"Current registered fonts: {list(_registered_fonts.keys())}")
                FontUtils.register_fonts_for_language(lang_normalized)
                # Wait a bit more after registration to ensure fonts are available
                import time
                time.sleep(0.1)  # Small delay to ensure registration completes
            # Note: Removed "Fonts already registered" log to reduce verbosity
            # Refresh registered_fonts reference (always use global dict directly)
            registered_fonts = _registered_fonts
        
        config = FontUtils.LANGUAGE_FONT_CONFIGS[lang_normalized]
        
        # Try system fonts first, then project fonts
        all_fonts = config.system_fonts + config.project_fonts
        
        # Always use global _registered_fonts directly to ensure we see latest updates
        # Note: Removed "Looking for font" log to reduce verbosity (only log on failure)
        
        for font_name, _ in all_fonts:
            if font_name in _registered_fonts:
                # Font is registered (TTFont succeeded), so it's available
                # Note: Removed "Found registered font" log to reduce verbosity (normal case)
                return font_name
            # Note: Removed "Font not in registered fonts" log to reduce verbosity (normal iteration)
        
        # If no font found and auto_register is enabled, try to force re-register
        # This handles the case where system fonts were installed after backend startup
        if auto_register:
            logger.debug(
                LogModule.FONT,
                f" No registered font found for language {lang_normalized}, "
                f"attempting to re-register (may find newly installed system fonts)"
            )
            # Force re-register by temporarily clearing language-specific font cache
            # This will re-scan system font directories for newly installed fonts
            FontUtils.register_fonts_for_language(lang_normalized, force_reregister=True)
            # Always use global _registered_fonts directly to ensure we see latest updates
            
            # Try again after re-registration
            for font_name, _ in all_fonts:
                if font_name in _registered_fonts:
                    # Font is registered (TTFont succeeded), so it's available
                    logger.info(LogModule.FONT, f" Found font {font_name} for language {lang_normalized} after re-registration")
                    return font_name
        
        # Fallback to default font
        return config.fallback_font
    
    @staticmethod
    def detect_and_get_font_for_text(
        text: str,
        target_language: Optional[str] = None,
        text_utils=None,  # Optional TextUtils instance to avoid circular import
    ) -> Tuple[str, str]:
        """
        Detect text language and get appropriate font name.
        
        This is the unified method for language detection and font selection.
        All text rendering should use this method to ensure consistent font handling.
        
        Args:
            text: Text to analyze
            target_language: Optional target language code/name for fallback when language cannot be detected
            text_utils: Optional TextUtils instance (if None, will import dynamically)
            
        Returns:
            Tuple of (detected_language_code, font_name)
            - detected_language_code: 'zh', 'ja', 'ko', 'en', 'fr', etc., or 'other'
            - font_name: Font name to use for rendering
        """
        # Import TextUtils dynamically to avoid circular import
        if text_utils is None:
            try:
                from layout.pdf_renderer.shared.text_utils import TextUtils
                text_utils = TextUtils()
            except ImportError:
                # Fallback if TextUtils is not available
                logger.error(LogModule.FONT, f" TextUtils not available, using default language detection")
                # Simple fallback: return English font
                font_name = FontUtils.get_font_name_for_language('en', target_language)
                return ('en', font_name)
        
        if not text or not text.strip():
            # Empty text, use target language or default to English
            font_name = FontUtils.get_font_name_for_language('en', target_language)
            return ('en', font_name)
        
        # Detect language from text
        detected_lang = text_utils.detect_language(text)
        
        # If detection returns 'en' but we have target_language, check if we should use target language
        if detected_lang == 'en' and target_language:
            target_lang_normalized = FontUtils.normalize_language_code(target_language)
            # If target language is not English, prefer target language font for better rendering
            # This handles cases where text might be detected as English but is actually in target language
            if target_lang_normalized != 'en':
                font_name = FontUtils.get_font_name_for_language(target_lang_normalized, target_language)
                return (target_lang_normalized, font_name)
        
        # Get font for detected language
        font_name = FontUtils.get_font_name_for_language(detected_lang, target_language)
        return (detected_lang, font_name)
    
    @staticmethod
    def set_font_with_fallback(
        canvas_obj,
        font_name: str,
        font_size: float,
        lang: str = None,
    ) -> str:
        """
        Set font on canvas with fallback handling for all languages.
        
        This method ensures fonts are registered before use and provides
        automatic fallback to prevent black squares (missing character glyphs).
        
        Args:
            canvas_obj: ReportLab canvas object
            font_name: Desired font name
            font_size: Font size
            lang: Optional language code (if None, will try to detect from font_name)
            
        Returns:
            Actual font name that was successfully set
        """
        if not REPORTLAB_AVAILABLE:
            return font_name
        
        # If font is not registered, try to register it based on language
        if font_name not in _registered_fonts and lang:
            lang_normalized = FontUtils.normalize_language_code(lang)
            if lang_normalized in FontUtils.LANGUAGE_FONT_CONFIGS:
                FontUtils.register_fonts_for_language(lang_normalized)
                # Refresh _registered_fonts reference after registration
                # Note: We use the global _registered_fonts directly here
        
        # Try to set the requested font if it's registered
        # First verify with pdfmetrics that font is actually available in ReportLab
        if font_name in _registered_fonts:
            # Verify font is actually available in pdfmetrics before trying setFont
            font_available = False
            try:
                font_obj = pdfmetrics.getFont(font_name)
                if font_obj is not None:
                    font_available = True
            except Exception:
                # Font not available in pdfmetrics (even though registered)
                logger.trace(LogModule.FONT, f" Font {font_name} is in registry but not available in pdfmetrics")
            
            if font_available:
                try:
                    canvas_obj.setFont(font_name, font_size)
                    logger.trace(LogModule.FONT, f" Successfully set font {font_name} (size={font_size}) for language {lang}")
                    return font_name
                except Exception as e:
                    # Font is available in pdfmetrics but setFont failed (unusual)
                    logger.warning(LogModule.FONT, f" Font {font_name} is available but setFont failed: {e}")
                    # Continue to fallback logic
            else:
                logger.trace(LogModule.FONT, f" Font {font_name} is registered but not available in pdfmetrics, trying alternatives")
        else:
            logger.trace(LogModule.FONT, f" Font {font_name} not in registered fonts. Registered: {list(_registered_fonts.keys())}")
        
        # Font not found or not available, try alternative fonts from language config
        # Do NOT re-register if fonts are already registered - just try alternatives
        if lang:
            lang_normalized = FontUtils.normalize_language_code(lang)
            if lang_normalized in FontUtils.LANGUAGE_FONT_CONFIGS:
                config = FontUtils.LANGUAGE_FONT_CONFIGS[lang_normalized]
                # Try all fonts in order (system fonts first, then project fonts)
                all_fonts = config.system_fonts + config.project_fonts
                
                for alt_font_name, _ in all_fonts:
                    if alt_font_name == font_name:
                        continue  # Skip the one we already tried
                    
                    # Check if font is registered and available
                    if alt_font_name in _registered_fonts:
                        try:
                            # Verify with pdfmetrics
                            font_obj = pdfmetrics.getFont(alt_font_name)
                            if font_obj is not None:
                                try:
                                    canvas_obj.setFont(alt_font_name, font_size)
                                    logger.debug(LogModule.FONT, f" Fallback to {alt_font_name} for language {lang_normalized}")
                                    return alt_font_name
                                except Exception:
                                    continue  # Try next font
                        except Exception:
                            continue  # Font not available in pdfmetrics, try next
                
                # If no alternative font worked, try fallback font
                fallback_font = config.fallback_font
                # Built-in fonts (Helvetica, Times-Roman, Courier) don't need registration
                builtin_fonts = ['Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica-BoldOblique',
                                'Times-Roman', 'Times-Bold', 'Times-Italic', 'Times-BoldItalic',
                                'Courier', 'Courier-Bold', 'Courier-Oblique', 'Courier-BoldOblique']
                
                if fallback_font in builtin_fonts:
                    # Built-in fonts are always available, try directly
                    try:
                        canvas_obj.setFont(fallback_font, font_size)
                        logger.warning(LogModule.FONT, f" No working font found for language {lang_normalized}, using built-in fallback {fallback_font}")
                        return fallback_font
                    except Exception as e:
                        logger.error(LogModule.FONT, f" Even built-in font {fallback_font} failed: {e}")
                else:
                    # Non-built-in fallback font, check if registered
                    if fallback_font in _registered_fonts:
                        try:
                            font_obj = pdfmetrics.getFont(fallback_font)
                            if font_obj is not None:
                                try:
                                    canvas_obj.setFont(fallback_font, font_size)
                                    logger.warning(LogModule.SYSTEM, f" No working font found for language {lang_normalized}, using fallback {fallback_font}")
                                    return fallback_font
                                except Exception:
                                    pass
                        except Exception:
                            pass
        
        # Final fallback to Helvetica (built-in font, always available)
        logger.warning(
            LogModule.FONT,
            f" Font {font_name} failed, using built-in Helvetica (may show black squares for unsupported characters)"
        )
        try:
            # Helvetica is a built-in font, doesn't need registration
            canvas_obj.setFont("Helvetica", font_size)
            return "Helvetica"
        except Exception as e:
            logger.error(LogModule.FONT, f" Even built-in Helvetica failed: {e}. This is a critical error.")
            # Last resort - return original font name (will likely fail)
            return font_name
    
    @staticmethod
    def get_registered_fonts() -> Dict[str, bool]:
        """
        Get the dictionary of registered fonts.
        
        Returns:
            Dictionary mapping font names to registration status
        """
        return _registered_fonts.copy()
