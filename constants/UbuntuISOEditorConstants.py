
# constants/UbuntuISOEditorConstants.py
from __future__ import annotations

from modules.state_machine_utils import result_available

from typing import Dict, Any

from modules.display_utils import display_config_doc
from modules.iso_utils import (
    validate_iso_paths,
    validate_ubuntu_yaml,
    validate_ubuntu_iso,
    add_ubuntu_autoinstall,
)


# ---------------------------------------------------------------------
# CONFIG PATHS
# ---------------------------------------------------------------------

CONFIG_PATH = "config/UbuntuISOEditor.json"
TOOL_TYPE = "UbuntuISOEditor"
CONFIG_DOC = "doc/UbuntuISOEditorDoc.json"


# ---------------------------------------------------------------------
# JSON KEYS
# ---------------------------------------------------------------------

ISO_KEYS_SECTION = "iso_keys"
SOURCE_ISO_KEY = "source_iso"
AUTOINSTALL_PATH_KEY = "autoinstall_path"
OUTPUT_ISO_KEY = "output_iso"


# ---------------------------------------------------------------------
# VALIDATION CONFIG
# ---------------------------------------------------------------------

VALIDATION_CONFIG: Dict[str, Any] = {
    "required_job_fields": {
        ISO_KEYS_SECTION: dict,
    },
}


# ---------------------------------------------------------------------
# SECONDARY VALIDATION
# ---------------------------------------------------------------------

SECONDARY_VALIDATION: Dict[str, Any] = {
    ISO_KEYS_SECTION: {
        "required_job_fields": {
            SOURCE_ISO_KEY: str,
            AUTOINSTALL_PATH_KEY: str,
            OUTPUT_ISO_KEY: str,
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

PLAN_COLUMN_ORDER = [ISO_KEYS_SECTION]
OPTIONAL_PLAN_COLUMNS: Dict[str, Any] = {}


# ---------------------------------------------------------------------
# DEPENDENCIES
# ---------------------------------------------------------------------

DEPENDENCIES = ["xorriso", "python3-yaml"]


# ---------------------------------------------------------------------
# ACTIONS
# ---------------------------------------------------------------------

ACTIONS: Dict[str, Dict[str, Any]] = {
    "_meta": {"title": "Ubuntu ISO Editor"},

    "Validate YAML": {
        "verb": "validate_yaml",
        "prompt": "Validate autoinstall YAML? [y/n]: ",
        "execute_state": "VALIDATE_YAML",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": False,
    },

    "Validate ISO": {
        "verb": "validate_iso",
        "prompt": "Validate source Ubuntu ISO? [y/n]: ",
        "execute_state": "VALIDATE_ISO",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": False,
    },

    "Create ISO": {
        "verb": "create_ubuntu_iso",
        "prompt": "Create the planned Ubuntu ISO(s)? [y/n]: ",
        "execute_state": "CREATE_UBUNTU_ISO",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": False,
        "skip_confirm": False,
    },

    "Run all steps": {
        "verb": "run_all",
        "prompt": "Validate YAML, validate ISO and create ISO? [y/n]: ",
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
# VALIDATE YAML STEPS
# ---------------------------------------------------------------------

VALIDATE_YAML_EXEC = [
    {
        "phase": "exec",
        "fn": validate_ubuntu_yaml,
        "args": [
            lambda job, meta, ctx:
                meta[ISO_KEYS_SECTION][AUTOINSTALL_PATH_KEY],
        ],
        "result": "yaml_valid",
    },
]


# ---------------------------------------------------------------------
# VALIDATE ISO STEPS
# ---------------------------------------------------------------------

VALIDATE_ISO_EXEC = [
    {
        "phase": "exec",
        "fn": validate_iso_paths,
        "args": [
            lambda job, meta, ctx:
                meta[ISO_KEYS_SECTION][SOURCE_ISO_KEY],
            lambda job, meta, ctx:
                meta[ISO_KEYS_SECTION][AUTOINSTALL_PATH_KEY],
            lambda job, meta, ctx:
                meta[ISO_KEYS_SECTION][OUTPUT_ISO_KEY],
        ],
        "result": "paths_valid",
    },
    {
        "phase": "exec",
        "fn": validate_ubuntu_iso,
        "args": [
            lambda job, meta, ctx:
                meta[ISO_KEYS_SECTION][SOURCE_ISO_KEY],
        ],
        "result": "iso_valid",
        "when": lambda job, meta, ctx: result_available(ctx, 'paths_valid') and (bool(ctx.get('paths_valid'))),
    },
]


# ---------------------------------------------------------------------
# CREATE ISO STEPS
# ---------------------------------------------------------------------

CREATE_ISO_EXEC = [
    {
        "phase": "exec",
        "fn": add_ubuntu_autoinstall,
        "args": [
            lambda job, meta, ctx:
                meta[ISO_KEYS_SECTION][SOURCE_ISO_KEY],
            lambda job, meta, ctx:
                meta[ISO_KEYS_SECTION][AUTOINSTALL_PATH_KEY],
            lambda job, meta, ctx:
                meta[ISO_KEYS_SECTION][OUTPUT_ISO_KEY],
        ],
        "result": "iso_created",
        "when": lambda job, meta, ctx: (
            (not any(s.get("result_key") == 'yaml_valid' for s in ctx.get("steps", []))
                or (result_available(ctx, 'yaml_valid') and ctx['yaml_valid'] is True))
            and (not any(s.get("result_key") == 'paths_valid' for s in ctx.get("steps", []))
                or (result_available(ctx, 'paths_valid') and ctx['paths_valid'] is True))
            and (not any(s.get("result_key") == 'iso_valid' for s in ctx.get("steps", []))
                or (result_available(ctx, 'iso_valid') and ctx['iso_valid'] is True))
        ),
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
        "result": 'display_config_doc_result',
    },
]


# ---------------------------------------------------------------------
# PIPELINES
# ---------------------------------------------------------------------

PIPELINE_STATES: Dict[str, Dict[str, Any]] = {
    "VALIDATE_YAML": {
        "pipeline": [
            *VALIDATE_YAML_EXEC,
        ],
        "label": "VALIDATE_YAML_COMPLETE",
    },

    "VALIDATE_ISO": {
        "pipeline": [
            *VALIDATE_ISO_EXEC,
        ],
        "label": "VALIDATE_ISO_COMPLETE",
    },

    "CREATE_UBUNTU_ISO": {
        "pipeline": [
            *CREATE_ISO_EXEC,
        ],
        "label": "CREATE_UBUNTU_ISO_COMPLETE",
    },

    "RUN_ALL": {
        "pipeline": [
            *VALIDATE_YAML_EXEC,
            *VALIDATE_ISO_EXEC,
            *CREATE_ISO_EXEC,
        ],
        "label": "ALL_STEPS_COMPLETE",
    },

    "SHOW_CONFIG_DOC": {
        "pipeline": [
            *SHOW_CONFIG_DOC_EXEC,
        ],
        "label": "DONE",
    },
}
