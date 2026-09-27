"""
file_classifier.py

Production-grade utility for classifying files by extension into broad
categories: image, text, code, executable, compressed, video, audio, or
unidentifiable.

Design goals:
- Deterministic, side-effect-free classification (pure function).
- O(1) lookup performance via a precomputed extension -> category map.
- Explicit, typed contract using an Enum return type (no stringly-typed bugs).
- Defensive input validation with clear, actionable exceptions.
- No reliance on file system access (never opens/stats/reads the file).
- Extensible via a single, centrally maintained set of extension registries.
"""

from __future__ import annotations

import logging
import os
import unicodedata
from enum import Enum
from typing import Final, Mapping

logger = logging.getLogger(__name__)

_MAX_FILENAME_LENGTH: Final[int] = 255  # POSIX NAME_MAX; guards against abuse


class FileCategory(str, Enum):
    """The categories a file name can be classified into."""

    IMAGE = "image"
    TEXT = "text"
    CODE = "code"
    EXECUTABLE = "executable"
    COMPRESSED = "compressed"
    VIDEO = "video"
    AUDIO = "audio"
    UNIDENTIFIABLE = "unidentifiable"


# --- Extension registry ---------------------------------------------------
# Plain frozenset literals so the mapping is easy to unit-test, diff in code
# review, and extend without touching the classification logic below.

_IMAGE_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp",
    ".tiff", ".tif", ".ico", ".heic", ".heif", ".avif",
})

_TEXT_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".txt", ".md", ".rst", ".csv", ".tsv", ".log", ".rtf",
    ".json", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".conf",
})

_CODE_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".java", ".c", ".h",
    ".cpp", ".cc", ".hpp", ".cs", ".rb", ".go", ".rs", ".php",
    ".html", ".htm", ".css", ".scss", ".sql", ".swift", ".kt", ".kts",
    ".sh", ".bash", ".ps1", ".pl", ".lua", ".r", ".scala",
})

_EXECUTABLE_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".exe", ".msi", ".bin", ".app", ".dll", ".so", ".dylib",
    ".apk", ".deb", ".rpm", ".com", ".jar",
})

# Note on compound extensions (e.g. "archive.tar.gz"): os.path.splitext only
# ever returns the final extension (".gz"), so a name like "backup.tar.gz" is
# classified via ".gz" alone. Since ".gz" and ".tar" are both registered
# below, compound archive names are still correctly classified as
# COMPRESSED without any special-casing.
_COMPRESSED_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".zst",
    ".tgz", ".tbz2", ".lz", ".lzma", ".z", ".cab", ".iso",
})

# NOTE: ".ts" is deliberately excluded here. It is ambiguous between an
# MPEG transport-stream video and a TypeScript source file, which is
# already registered under _CODE_EXTENSIONS. TypeScript is the far more
# common case in practice, so ".ts" resolves to CODE; see the collision
# check below, which would otherwise let this ambiguity fail silently.
_VIDEO_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".mp4", ".m4v", ".mkv", ".mov", ".avi", ".wmv", ".flv",
    ".webm", ".mpeg", ".mpg", ".3gp", ".3g2", ".ogv",
})

_AUDIO_EXTENSIONS: Final[frozenset[str]] = frozenset({
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".oga", ".wma",
    ".m4a", ".opus", ".aiff", ".aif", ".alac", ".mid", ".midi",
})

def _build_extension_map(
    registry: tuple[tuple[FileCategory, frozenset[str]], ...]
) -> Mapping[str, FileCategory]:
    """
    Build the extension -> category lookup table, failing loudly (at
    import time) if any extension is registered under more than one
    category. A silent dict-merge would let such a collision resolve to
    whichever category happened to be merged last -- an easy, invisible
    bug to introduce when extending the registries later.
    """
    mapping: dict[str, FileCategory] = {}
    for category, extensions in registry:
        for ext in extensions:
            if ext in mapping and mapping[ext] is not category:
                raise ValueError(
                    f"Extension {ext!r} is registered under both "
                    f"{mapping[ext]!r} and {category!r}. Each extension "
                    f"must map to exactly one FileCategory -- resolve the "
                    f"ambiguity in the registry before proceeding."
                )
            mapping[ext] = category
    return mapping


# Precomputed once, at import time: extension -> category.
# Turns classification into a single O(1) dict lookup instead of iterating
# multiple sets on every call.
_EXTENSION_TO_CATEGORY: Final[Mapping[str, FileCategory]] = _build_extension_map((
    (FileCategory.IMAGE, _IMAGE_EXTENSIONS),
    (FileCategory.TEXT, _TEXT_EXTENSIONS),
    (FileCategory.CODE, _CODE_EXTENSIONS),
    (FileCategory.EXECUTABLE, _EXECUTABLE_EXTENSIONS),
    (FileCategory.COMPRESSED, _COMPRESSED_EXTENSIONS),
    (FileCategory.VIDEO, _VIDEO_EXTENSIONS),
    (FileCategory.AUDIO, _AUDIO_EXTENSIONS),
))


def classify_file(filename: str) -> FileCategory:
    """
    Classify a file by its base name into a FileCategory.

    This function performs no I/O: it never opens, stats, or reads the
    file, and does not require the file to exist. Classification is based
    solely on the filename's extension.

    Args:
        filename: The base name of the file (e.g. "report.pdf"). If a
            full or relative path is passed, only the base name is used.

    Returns:
        A FileCategory enum member.

    Raises:
        TypeError: If `filename` is not a string.
        ValueError: If `filename` is empty/whitespace-only, contains a
            null byte, or exceeds the maximum supported length.

    Examples:
        >>> classify_file("photo.JPG")
        <FileCategory.IMAGE: 'image'>
        >>> classify_file("backup.tar.gz")
        <FileCategory.COMPRESSED: 'compressed'>
        >>> classify_file("report.docx")
        <FileCategory.UNIDENTIFIABLE: 'unidentifiable'>
    """
    if not isinstance(filename, str):
        raise TypeError(f"filename must be a str, got {type(filename).__name__}")

    if "\x00" in filename:
        raise ValueError("filename must not contain a null byte")

    if len(filename) > _MAX_FILENAME_LENGTH:
        raise ValueError(
            f"filename exceeds maximum supported length "
            f"({len(filename)} > {_MAX_FILENAME_LENGTH})"
        )

    # Normalize Unicode (e.g. NFD vs NFC forms of accented characters) so
    # visually identical names classify identically.
    normalized = unicodedata.normalize("NFC", filename).strip()

    if not normalized:
        raise ValueError("filename must not be empty or whitespace-only")

    # Defensive: only ever consider the base name, even if a path slips in,
    # so this never leaks or depends on directory structure.
    base_name = os.path.basename(normalized)

    _, ext = os.path.splitext(base_name)
    ext = ext.lower()

    if not ext:
        logger.debug("No extension found for %r; unidentifiable.", filename)
        return FileCategory.UNIDENTIFIABLE

    category = _EXTENSION_TO_CATEGORY.get(ext, FileCategory.UNIDENTIFIABLE)

    if category is FileCategory.UNIDENTIFIABLE:
        logger.debug("Unrecognized extension %r for %r.", ext, filename)

    return category