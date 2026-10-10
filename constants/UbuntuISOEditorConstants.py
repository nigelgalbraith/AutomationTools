
# constants/UbuntuISOEditorConstants.py
from __future__ import annotations

from typing import Dict, Any

from modules.display_utils import display_config_doc
from modules.iso_utils import validate_ubuntu_iso_plan, add_ubuntu_autoinstall


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
    "Create Ubuntu ISO": {
        "verb": "create_ubuntu_iso",
        "prompt": "Create the planned Ubuntu ISO(s)? [y/n]: ",
        "execute_state": "CREATE_UBUNTU_ISO",
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
# PRE PHASE STEPS
# ---------------------------------------------------------------------

VALIDATE_ISO_PRE = [
    {
        "phase": "pre",
        "fn": validate_ubuntu_iso_plan,
        "args": [
            lambda job, meta, ctx: meta[ISO_KEYS_SECTION][SOURCE_ISO_KEY],
            lambda job, meta, ctx: meta[ISO_KEYS_SECTION][AUTOINSTALL_PATH_KEY],
            lambda job, meta, ctx: meta[ISO_KEYS_SECTION][OUTPUT_ISO_KEY],
        ],
        "result": "plan_valid",
    },
    {
        "phase": "pre",
        "fn": bool,
        "args": [lambda job, meta, ctx: bool(ctx.get("plan_valid")) and not ctx.get("errors")],
        "result": "iso_success",
    },
]


# ---------------------------------------------------------------------
# EXEC PHASE STEPS
# ---------------------------------------------------------------------

CREATE_ISO_EXEC = [
    {
        "phase": "exec",
        "fn": add_ubuntu_autoinstall,
        "args": [
            lambda job, meta, ctx: meta[ISO_KEYS_SECTION][SOURCE_ISO_KEY],
            lambda job, meta, ctx: meta[ISO_KEYS_SECTION][AUTOINSTALL_PATH_KEY],
            lambda job, meta, ctx: meta[ISO_KEYS_SECTION][OUTPUT_ISO_KEY],
        ],
        "result": "iso_created",
        "when": lambda job, meta, ctx: bool(ctx.get("plan_valid")) and not ctx.get("errors"),
    },
    {
        "phase": "exec",
        "fn": bool,
        "args": [lambda job, meta, ctx: bool(ctx.get("iso_created")) and not ctx.get("errors")],
        "result": "iso_success",
    },
]


# ---------------------------------------------------------------------
# PIPELINES
# ---------------------------------------------------------------------

PIPELINE_STATES: Dict[str, Dict[str, Any]] = {
    "CREATE_UBUNTU_ISO": {
        "pipeline": [
            *VALIDATE_ISO_PRE,
            *CREATE_ISO_EXEC,
        ],
        "label": "CREATE_UBUNTU_ISO_COMPLETE",
        "success_key": "iso_success",
    },
    "SHOW_CONFIG_DOC": {
        "pipeline": [
            {
                "phase": "exec",
                "fn": display_config_doc,
                "args": [CONFIG_DOC],
                "result": "ok",
            },
        ],
        "label": "DONE",
        "success_key": "ok",
    },
}
