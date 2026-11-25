# constants/FileConsolidationConstants.py
from __future__ import annotations

from typing import Dict, Any

from modules.display_utils import display_config_doc
from modules.file_consolidation_utils import (
    validate_consolidation_paths,
    find_archives,
    extract_archives,
    find_files,
    find_extracted_files,
    copy_files,
    move_files,
    cleanup_extracted_directories,
    remove_duplicate_files,
    organize_files,
    organize_files_by_year,
    organize_files_by_month,
)


# ---------------------------------------------------------------------
# CONFIG PATHS
# ---------------------------------------------------------------------

CONFIG_PATH = "config/FileConsolidation.json"
TOOL_TYPE = "FileConsolidation"
CONFIG_DOC = "doc/FileConsolidationDoc.json"


# ---------------------------------------------------------------------
# JSON KEYS
# ---------------------------------------------------------------------

FILE_KEYS_SECTION = "file_keys"
SOURCE_DIRECTORY_KEY = "source_directory"
DESTINATION_DIRECTORY_KEY = "destination_directory"
ARCHIVE_EXTENSIONS_KEY = "archive_extensions"
ORGANIZATION_KEYS_SECTION = "organization_keys"
YEAR_KEYS_SECTION = "year_keys"
DIRECTORIES_KEY = "directories"
MONTH_KEYS_SECTION = "month_keys"
YEAR_PATTERNS_KEY = "year_patterns"

# ---------------------------------------------------------------------
# VALIDATION CONFIG
# ---------------------------------------------------------------------

VALIDATION_CONFIG: Dict[str, Any] = {
    "required_job_fields": {
        FILE_KEYS_SECTION: dict,
        ORGANIZATION_KEYS_SECTION: dict,
        YEAR_KEYS_SECTION: dict,
        MONTH_KEYS_SECTION: dict,
    },
}

# ---------------------------------------------------------------------
# SECONDARY VALIDATION
# ---------------------------------------------------------------------

SECONDARY_VALIDATION: Dict[str, Any] = {
    FILE_KEYS_SECTION: {
        "required_job_fields": {
            SOURCE_DIRECTORY_KEY: str,
            DESTINATION_DIRECTORY_KEY: str,
            ARCHIVE_EXTENSIONS_KEY: list,
        },
    },
    YEAR_KEYS_SECTION: {
        "required_job_fields": {
            DIRECTORIES_KEY: list,
        },
    },
    MONTH_KEYS_SECTION: {
        "required_job_fields": {
            DIRECTORIES_KEY: list,
            YEAR_PATTERNS_KEY: list,
        },
    },
}


# ---------------------------------------------------------------------
# USER REQUIREMENTS
# ---------------------------------------------------------------------

REQUIRED_USER = "standard"

# ---------------------------------------------------------------------
# PLAN CONFIG
# ---------------------------------------------------------------------

PLAN_COLUMN_ORDER = [
    FILE_KEYS_SECTION,
    ORGANIZATION_KEYS_SECTION,
    YEAR_KEYS_SECTION,
    MONTH_KEYS_SECTION,
]

OPTIONAL_PLAN_COLUMNS: Dict[str, Any] = {}


# ---------------------------------------------------------------------
# DEPENDENCIES
# ---------------------------------------------------------------------

DEPENDENCIES = ["7zip"]


# ---------------------------------------------------------------------
# ACTIONS
# ---------------------------------------------------------------------

ACTIONS: Dict[str, Dict[str, Any]] = {
    "_meta": {"title": "File Consolidation"},

    "Extract Archives": {
        "verb": "extract_archives",
        "prompt": "Extract archives and move extracted files to the destination directory? [y/n]: ",
        "execute_state": "EXTRACT_ARCHIVES",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": False,
        "skip_confirm": False,
    },

    "Copy Source Files": {
        "verb": "copy_source_files",
        "prompt": "Copy source files to the destination directory? [y/n]: ",
        "execute_state": "COPY_SOURCE_FILES",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": False,
        "skip_confirm": False,
    },

    "Remove Duplicate Files": {
        "verb": "remove_duplicate_files",
        "prompt": "Remove duplicate files in the destination directory? [y/n]: ",
        "execute_state": "REMOVE_DUPLICATE_FILES",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": False,
        "skip_confirm": False,
    },

    "Organize Files": {
        "verb": "organize_files",
        "prompt": "Organize files into their respective directories? [y/n]: ",
        "execute_state": "ORGANIZE_FILES",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": False,
        "skip_confirm": False,
    },

    "Organize Files by Year": {
        "verb": "organize_files_by_year",
        "prompt": "Organize files into directories by year? [y/n]: ",
        "execute_state": "ORGANIZE_FILES_BY_YEAR",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": False,
        "skip_confirm": False,
    },

    "Organize Files by Month": {
        "verb": "organize_files_by_month",
        "prompt": "Organize files into directories by month? [y/n]: ",
        "execute_state": "ORGANIZE_FILES_BY_MONTH",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": False,
        "skip_confirm": False,
    },

    "Run All": {
        "verb": "run_all",
        "prompt": "Run all file consolidation and organization steps? [y/n]: ",
        "execute_state": "RUN_ALL",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": False,
        "skip_confirm": False,
    },

    "Show config help": {
        "verb": "help",
        "prompt": "Show config help now? [y/n]: ",
        "execute_state": "SHOW_CONFIG_DOC",
        "post_state": "MENU_SELECTION",
        "skip_group_select": True,
        "skip_prepare_plan": True,
        "skip_confirm": True,
    },

    "Cancel": {
        "verb": "cancel",
        "prompt": "",
        "execute_state": "FINALIZE",
        "post_state": "FINALIZE",
        "skip_prepare_plan": True,
    },
}

# ---------------------------------------------------------------------
# VALIDATE PATHS STEPS
# ---------------------------------------------------------------------

VALIDATE_PATHS_PRE = [
    {
        "phase": "pre",
        "fn": validate_consolidation_paths,
        "args": [
            f"meta.{FILE_KEYS_SECTION}.{SOURCE_DIRECTORY_KEY}",
            f"meta.{FILE_KEYS_SECTION}.{DESTINATION_DIRECTORY_KEY}",
        ],
        "result": "paths_valid",
    },
]


# ---------------------------------------------------------------------
# ARCHIVE STEPS
# ---------------------------------------------------------------------


EXTRACT_ARCHIVES_EXEC = [
    {
        "phase": "exec",
        "fn": find_archives,
        "args": [
            f"meta.{FILE_KEYS_SECTION}.{SOURCE_DIRECTORY_KEY}",
            f"meta.{FILE_KEYS_SECTION}.{ARCHIVE_EXTENSIONS_KEY}",
        ],
        "when": "paths_valid",
        "result": "archives",
    },
    {
        "phase": "exec",
        "fn": extract_archives,
        "args": [
            "archives",
            f"meta.{FILE_KEYS_SECTION}.{ARCHIVE_EXTENSIONS_KEY}",
        ],
        "when": ["paths_valid", "archives"],
        "result": "extracted_directories",
    },
]


# ---------------------------------------------------------------------
# MOVE EXTRACTED FILES STEPS
# ---------------------------------------------------------------------

MOVE_EXTRACTED_FILES_EXEC = [
    {
        "phase": "exec",
        "fn": find_extracted_files,
        "args": [
            "extracted_directories",
            f"meta.{FILE_KEYS_SECTION}.{ARCHIVE_EXTENSIONS_KEY}",
        ],
        "when": ["paths_valid", "extracted_directories"],
        "result": "extracted_files",
    },
    {
        "phase": "exec",
        "fn": move_files,
        "args": [
            "extracted_files",
            f"meta.{FILE_KEYS_SECTION}.{DESTINATION_DIRECTORY_KEY}",
        ],
        "when": ["paths_valid", "extracted_files"],
        "result": "moved_files",
    },
]


# ---------------------------------------------------------------------
# CLEANUP EXTRACTED DIRECTORIES STEPS
# ---------------------------------------------------------------------


CLEANUP_EXTRACTED_DIRECTORIES_EXEC = [
    {
        "phase": "exec",
        "fn": cleanup_extracted_directories,
        "args": [
            "extracted_directories",
        ],
        "when": [
            "paths_valid",
            "extracted_directories",
            "moved_files",
        ],
        "result": "removed_directories",
    },
]

# ---------------------------------------------------------------------
# COPY SOURCE FILES STEPS
# ---------------------------------------------------------------------

COPY_SOURCE_FILES_EXEC = [
    {
        "phase": "exec",
        "fn": find_files,
        "args": [
            f"meta.{FILE_KEYS_SECTION}.{SOURCE_DIRECTORY_KEY}",
            f"meta.{FILE_KEYS_SECTION}.{ARCHIVE_EXTENSIONS_KEY}",
        ],
        "when": "paths_valid",
        "result": "files",
    },
    {
        "phase": "exec",
        "fn": copy_files,
        "args": [
            "files",
            f"meta.{FILE_KEYS_SECTION}.{DESTINATION_DIRECTORY_KEY}",
        ],
        "when": "paths_valid",
        "result": "copied_files",
    },
]

# ---------------------------------------------------------------------
# REMOVE DUPLICATE FILES STEPS
# ---------------------------------------------------------------------

REMOVE_DUPLICATE_FILES_EXEC = [
    {
        "phase": "exec",
        "fn": remove_duplicate_files,
        "args": [
            f"meta.{FILE_KEYS_SECTION}.{DESTINATION_DIRECTORY_KEY}",
        ],
        "when": "paths_valid",
        "result": "removed_duplicates",
    },
]

# ---------------------------------------------------------------------
# ORGANIZE FILES STEPS
# ---------------------------------------------------------------------

ORGANIZE_FILES_EXEC = [
    {
        "phase": "exec",
        "fn": organize_files,
        "args": [
            f"meta.{FILE_KEYS_SECTION}.{DESTINATION_DIRECTORY_KEY}",
            f"meta.{ORGANIZATION_KEYS_SECTION}",
        ],
        "when": "paths_valid",
        "result": "organized_files",
    },
]

# ---------------------------------------------------------------------
# ORGANIZE FILES BY YEAR STEPS
# ---------------------------------------------------------------------

ORGANIZE_FILES_BY_YEAR_EXEC = [
    {
        "phase": "exec",
        "fn": organize_files_by_year,
        "args": [
            f"meta.{YEAR_KEYS_SECTION}.{DIRECTORIES_KEY}",
        ],
        "when": "paths_valid",
        "result": "organized_year_files",
    },
]

# ---------------------------------------------------------------------
# ORGANIZE FILES BY MONTH STEPS
# ---------------------------------------------------------------------

ORGANIZE_FILES_BY_MONTH_EXEC = [
    {
        "phase": "exec",
        "fn": organize_files_by_month,
        "args": [
            f"meta.{MONTH_KEYS_SECTION}.{DIRECTORIES_KEY}",
            f"meta.{MONTH_KEYS_SECTION}.{YEAR_PATTERNS_KEY}",
        ],
        "when": "paths_valid",
        "result": "organized_month_files",
    },
]

# ---------------------------------------------------------------------
# SHOW CONFIG HELP STEPS
# ---------------------------------------------------------------------

SHOW_CONFIG_DOC_EXEC = [
    {
        "phase": "exec",
        "fn": display_config_doc,
        "args": [CONFIG_DOC],
        "result": "display_config_doc_result",
    },
]


# ---------------------------------------------------------------------
# PIPELINES
# ---------------------------------------------------------------------

PIPELINE_STATES: Dict[str, Dict[str, Any]] = {
    "EXTRACT_ARCHIVES": {
        "pipeline": [
            *VALIDATE_PATHS_PRE,
            *EXTRACT_ARCHIVES_EXEC,
            *MOVE_EXTRACTED_FILES_EXEC,
            *CLEANUP_EXTRACTED_DIRECTORIES_EXEC,
        ],
        "label": "EXTRACT_ARCHIVES_COMPLETE",
    },
    "COPY_SOURCE_FILES": {
        "pipeline": [
            *VALIDATE_PATHS_PRE,
            *COPY_SOURCE_FILES_EXEC,
        ],
        "label": "COPY_SOURCE_FILES_COMPLETE",
    },
    "REMOVE_DUPLICATE_FILES": {
        "pipeline": [
            *VALIDATE_PATHS_PRE,
            *REMOVE_DUPLICATE_FILES_EXEC,
        ],
        "label": "REMOVE_DUPLICATE_FILES_COMPLETE",
    },
    "ORGANIZE_FILES": {
        "pipeline": [
            *VALIDATE_PATHS_PRE,
            *ORGANIZE_FILES_EXEC,
        ],
        "label": "ORGANIZE_FILES_COMPLETE",
    },
    "ORGANIZE_FILES_BY_YEAR": {
        "pipeline": [
            *VALIDATE_PATHS_PRE,
            *ORGANIZE_FILES_BY_YEAR_EXEC,
        ],
        "label": "ORGANIZE_FILES_BY_YEAR_COMPLETE",
    },
    "ORGANIZE_FILES_BY_MONTH": {
        "pipeline": [
            *VALIDATE_PATHS_PRE,
            *ORGANIZE_FILES_BY_MONTH_EXEC,
        ],
        "label": "ORGANIZE_FILES_BY_MONTH_COMPLETE",
    },
    "RUN_ALL": {
        "pipeline": [
            *VALIDATE_PATHS_PRE,
            *EXTRACT_ARCHIVES_EXEC,
            *MOVE_EXTRACTED_FILES_EXEC,
            *CLEANUP_EXTRACTED_DIRECTORIES_EXEC,
            *COPY_SOURCE_FILES_EXEC,
            *REMOVE_DUPLICATE_FILES_EXEC,
            *ORGANIZE_FILES_EXEC,
            *ORGANIZE_FILES_BY_YEAR_EXEC,
            *ORGANIZE_FILES_BY_MONTH_EXEC,
        ],
        "label": "RUN_ALL_COMPLETE",
    },
    "SHOW_CONFIG_DOC": {
        "pipeline": [
            *SHOW_CONFIG_DOC_EXEC,
        ],
        "label": "DONE",
    },
}
