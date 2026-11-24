#!/usr/bin/env python3
"""
file_consolidation_utils.py

Extract archives and consolidate files into a flat destination directory.
"""

from __future__ import annotations

import shutil
import zipfile
import tarfile
import hashlib
import filecmp
from pathlib import Path
from typing import List
from datetime import datetime

from modules.system_utils import expand_path


# ---------------------------------------------------------------------
# PATH VALIDATION
# ---------------------------------------------------------------------

def validate_consolidation_paths(
    source_directory: str,
    destination_directory: str,
) -> bool:
    """Validate source and destination directories."""
    source = Path(expand_path(source_directory)).resolve()
    destination = Path(expand_path(destination_directory)).resolve()
    if not source.is_dir():
        raise NotADirectoryError(source)
    if destination == source or destination.is_relative_to(source):
        raise ValueError("Destination must be outside the source directory.")
    if destination.exists() and not destination.is_dir():
        raise NotADirectoryError(destination)
    return True


# ---------------------------------------------------------------------
# ARCHIVE COLLECTION
# ---------------------------------------------------------------------

def find_archives(
    source_directory: str,
    archive_extensions: List[str],
) -> List[Path]:
    """Find all archives within the source directory."""
    source = Path(expand_path(source_directory))
    extensions = tuple(ext.lower() for ext in archive_extensions)
    archives = []
    for path in source.rglob("*"):
        if path.is_file() and not path.is_symlink():
            if path.name.lower().endswith(extensions):
                archives.append(path)
    print(f"[OK] Archives found: {len(archives)}")
    return archives


# ---------------------------------------------------------------------
# ARCHIVE EXTRACTION
# ---------------------------------------------------------------------

def extract_archives(
    archives: List[Path],
    archive_extensions: List[str],
) -> List[Path]:
    """Extract archives and any nested archives."""
    extensions = tuple(ext.lower() for ext in archive_extensions)
    pending = list(archives)
    extracted = []
    while pending:
        archive = pending.pop(0)
        directory = archive.parent / f"{archive.name}_extracted"
        directory.mkdir(exist_ok=True)
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as handle:
                handle.extractall(directory)
        elif tarfile.is_tarfile(archive):
            with tarfile.open(archive, "r:*") as handle:
                handle.extractall(directory, filter="data")
        else:
            raise ValueError(f"Unsupported archive: {archive}")
        extracted.append(directory)
        for path in directory.rglob("*"):
            if path.is_file() and not path.is_symlink():
                if path.name.lower().endswith(extensions):
                    pending.append(path)
    print(f"[OK] Total archives extracted: {len(extracted)}")
    return extracted


# ---------------------------------------------------------------------
# FILE COLLECTION
# ---------------------------------------------------------------------

def find_files(
    source_directory: str,
    archive_extensions: List[str],
) -> List[Path]:
    """Find all files within the source directory, excluding archives."""
    source = Path(expand_path(source_directory))
    extensions = tuple(ext.lower() for ext in archive_extensions)
    files = []
    for path in source.rglob("*"):
        if path.is_file() and not path.is_symlink():
            if not path.name.lower().endswith(extensions):
                files.append(path)
    print(f"[OK] Files found: {len(files)}")
    return files


# ---------------------------------------------------------------------
# FILE CONSOLIDATION
# ---------------------------------------------------------------------

def move_files(
    files: List[Path],
    destination_directory: str,
) -> List[Path]:
    """Move files into a flat destination directory."""
    destination = Path(expand_path(destination_directory))
    destination.mkdir(parents=True, exist_ok=True)
    moved = []
    for source in files:
        target = destination / source.name
        index = 1
        while target.exists() or target.is_symlink():
            target = destination / f"{source.stem}_{index}{source.suffix}"
            index += 1
        shutil.move(str(source), str(target))
        moved.append(target)
    print(f"[OK] Total files moved: {len(moved)}")
    return moved


# ---------------------------------------------------------------------
# DUPLICATE FILE REMOVAL
# ---------------------------------------------------------------------

def remove_duplicate_files(
    destination_directory: str,
) -> List[Path]:
    """Remove duplicate files, prioritizing previously organized files."""
    destination = Path(expand_path(destination_directory))
    hashes = {}
    removed = []
    paths = sorted(destination.rglob("*"))
    organized = [path for path in paths if path.parent != destination]
    unorganized = [path for path in paths if path.parent == destination]
    for path in organized + unorganized:
        if not path.is_file() or path.is_symlink():
            continue
        with path.open("rb") as handle:
            file_hash = hashlib.file_digest(handle, "sha256").hexdigest()
        if file_hash in hashes:
            if filecmp.cmp(path, hashes[file_hash], shallow=False):
                path.unlink()
                removed.append(path)
        else:
            hashes[file_hash] = path
    print(f"[OK] Total duplicate files removed: {len(removed)}")
    return removed


# ---------------------------------------------------------------------
# FILE COLLECTION BY EXTENSION
# ---------------------------------------------------------------------

def find_files_by_extension(
    source_directory: str,
    file_extensions: List[str],
) -> List[Path]:
    """Find files matching extensions or all files if the list is empty."""
    source = Path(expand_path(source_directory))
    extensions = tuple(ext.lower() for ext in file_extensions)
    files = []
    for path in source.iterdir():
        if path.is_file() and not path.is_symlink():
            if not extensions or path.name.lower().endswith(extensions):
                files.append(path)
    return files

# ---------------------------------------------------------------------
# ORGANIZE FILES
# ---------------------------------------------------------------------

def organize_files(
    source_directory: str,
    organization_keys: dict,
) -> List[Path]:
    """Organize files into configured category directories."""
    moved = []
    for category, settings in organization_keys.items():
        files = find_files_by_extension(
            source_directory,
            settings["extensions"],
        )
        if files:
            print(f"[OK] Organizing {category.capitalize()}: {len(files)} files")
            moved.extend(move_files(files, settings["directory"]))
    print(f"[OK] Total files organized: {len(moved)}")
    return moved

# ---------------------------------------------------------------------
# ORGANIZE FILES BY YEAR
# ---------------------------------------------------------------------

def organize_files_by_year(
    directories: List[str],
) -> List[Path]:
    """Organize files into folders by modification year."""
    moved = []
    for directory in directories:
        source = Path(expand_path(directory))
        if not source.is_dir():
            continue
        for path in list(source.iterdir()):
            if not path.is_file() or path.is_symlink():
                continue
            year = datetime.fromtimestamp(path.stat().st_mtime).year
            destination = source / str(year)
            destination.mkdir(exist_ok=True)
            target = destination / path.name
            index = 1
            while target.exists() or target.is_symlink():
                target = destination / f"{path.stem}_{index}{path.suffix}"
                index += 1
            shutil.move(str(path), str(target))
            moved.append(target)
    print(f"[OK] Total files organized by year: {len(moved)}")
    return moved

# ---------------------------------------------------------------------
# ORGANIZE FILES BY MONTH
# ---------------------------------------------------------------------

def organize_files_by_month(
    directories: List[str],
    year_patterns: List[str],
) -> List[Path]:
    """Organize files within year directories by modification month."""
    moved = []
    for directory in directories:
        source = Path(expand_path(directory))
        if not source.is_dir():
            continue
        for pattern in year_patterns:
            for year_directory in source.glob(pattern):
                if not year_directory.is_dir() or year_directory.is_symlink():
                    continue
                for path in list(year_directory.iterdir()):
                    if not path.is_file() or path.is_symlink():
                        continue
                    month = datetime.fromtimestamp(path.stat().st_mtime).strftime("%m-%B")
                    destination = year_directory / month
                    destination.mkdir(exist_ok=True)
                    target = destination / path.name
                    index = 1
                    while target.exists() or target.is_symlink():
                        target = destination / f"{path.stem}_{index}{path.suffix}"
                        index += 1
                    shutil.move(str(path), str(target))
                    moved.append(target)
    print(f"[OK] Total files organized by month: {len(moved)}")
    return moved