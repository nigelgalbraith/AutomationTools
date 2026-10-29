# constants/RouterConstants.py
from __future__ import annotations

from modules.state_machine_utils import result_available

from typing import Any, Dict

from modules.display_utils import display_config_doc
from modules.json_utils import load_json, validate_json_schema
from modules.router_utils import (
    validate_router_configuration,
    view_readme,
    view_router_details,
    decode_router_config,
    save_router_config,
    extract_router_config,
    view_router_config_fields,
    edit_router_config_fields,
    encode_router_config,
    validate_router_settings,
)


# ---------------------------------------------------------------------
# CONFIG PATHS
# ---------------------------------------------------------------------

ROUTER_SCHEMA_PATH = "schemas/RouterSchema.json"
CONFIG_PATH = "config/RouterConfig.json"
TOOL_TYPE = "Router Configuration"
CONFIG_DOC = "doc/RouterDoc.json"


# ---------------------------------------------------------------------
# JSON KEYS
# ---------------------------------------------------------------------

MODEL_SPECS_PATH = "model_specs_path"
MODEL_SPECS_README_PATH = "model_specs_readme_path"
TEMPLATE_CONFIG_PATH = "template_config_path"
TEMPLATE_ROUTER_PASSWORD_PATH = "template_router_password_path"
TARGET_ROUTER_PASSWORD_PATH = "target_router_password_path"
TEMPLATE_DEVICE_KEY_PATH = "template_device_key_path"
TARGET_DEVICE_KEY_PATH = "target_device_key_path"
ROUTER_DETAILS_PATH = "router_details_path"
ROUTER_DETAILS_README_PATH = "router_details_readme_path"
DECODED_CONFIG_PATH = "decoded_config_path"
DECODED_CONFIG_ARCHIVE_PATH = "decoded_config_archive_path"
EDITED_CONFIG_PATH = "edited_config_path"
ENCODED_CONFIG_PATH = "encoded_config_path"


# ---------------------------------------------------------------------
# VALIDATION CONFIG
# ---------------------------------------------------------------------

# Password and device-key fields are optional; credentials follow the model specification.
VALIDATION_CONFIG: Dict[str, Any] = {
    "required_job_fields": {
        MODEL_SPECS_PATH: str,
        MODEL_SPECS_README_PATH: str,
        TEMPLATE_CONFIG_PATH: str,
        ROUTER_DETAILS_PATH: str,
        ROUTER_DETAILS_README_PATH: str,
        DECODED_CONFIG_PATH: str,
        DECODED_CONFIG_ARCHIVE_PATH: str,
        EDITED_CONFIG_PATH: str,
        ENCODED_CONFIG_PATH: str,
    },
}


# ---------------------------------------------------------------------
# SECONDARY VALIDATION
# ---------------------------------------------------------------------

SECONDARY_VALIDATION: Dict[str, Any] = {}


# ---------------------------------------------------------------------
# USER REQUIREMENTS
# ---------------------------------------------------------------------

REQUIRED_USER = "standard"


# ---------------------------------------------------------------------
# DEPENDENCIES
# ---------------------------------------------------------------------

DEPENDENCIES = ["openssl", "python3-cryptography", "python3-jsonschema"]


# ---------------------------------------------------------------------
# PLAN CONFIG
# ---------------------------------------------------------------------

PLAN_COLUMN_ORDER = [
    TEMPLATE_CONFIG_PATH,
    ROUTER_DETAILS_PATH,
    ENCODED_CONFIG_PATH,
]

OPTIONAL_PLAN_COLUMNS: Dict[str, Any] = {}


# ---------------------------------------------------------------------
# ACTIONS
# ---------------------------------------------------------------------

ACTIONS: Dict[str, Dict[str, Any]] = {
    "_meta": {"title": "Router Automation"},
    "Validate Router Configuration": {
        "verb": "validate",
        "prompt": "Validate router configuration? [y/n]: ",
        "execute_state": "VALIDATE_CONFIG",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": True,
    },
    "View Router Model Specifications": {
        "verb": "view_specs",
        "prompt": "View router model specifications? [y/n]: ",
        "execute_state": "VIEW_MODEL_SPECS",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": True,
    },
    "View Router Details": {
        "verb": "view_details",
        "prompt": "View router details? [y/n]: ",
        "execute_state": "VIEW_ROUTER_DETAILS",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": True,
    },
    "View Router Details Help": {
        "verb": "view_details_help",
        "prompt": "View router details help? [y/n]: ",
        "execute_state": "VIEW_ROUTER_DETAILS_HELP",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": True,
    },
    "Decode Router Configuration": {
        "verb": "decode",
        "prompt": "Decode router configuration? [y/n]: ",
        "execute_state": "DECODE_CONFIG",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": False,
    },
    "View Decoded Router Configuration": {
        "verb": "view_decoded",
        "prompt": "View decoded router configuration? [y/n]: ",
        "execute_state": "VIEW_DECODED_CONFIG",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": True,
    },
    "Edit Router Configuration": {
        "verb": "edit",
        "prompt": "Apply router details? [y/n]: ",
        "execute_state": "EDIT_CONFIG",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": False,
    },
    "View Edited Router Configuration": {
        "verb": "view_edited",
        "prompt": "View edited router configuration? [y/n]: ",
        "execute_state": "VIEW_EDITED_CONFIG",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": True,
    },
    "Encode Router Configuration": {
        "verb": "encode",
        "prompt": "Encode router configuration? [y/n]: ",
        "execute_state": "ENCODE_CONFIG",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": False,
    },
    "Run All Steps": {
        "verb": "run_all",
        "prompt": "Decode, edit and encode router configuration? [y/n]: ",
        "execute_state": "RUN_ALL",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": False,
    },
    "Show Config Help": {
        "verb": "help",
        "prompt": "Show router config help? [y/n]: ",
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

LOAD_MODEL_SPECS_PRE = [
    {
        "phase": "pre",
        "fn": load_json,
        "args": [MODEL_SPECS_PATH],
        "result": "model_specs",
    },
    {
        "phase": "pre",
        "fn": validate_json_schema,
        "args": [
            lambda job, meta, ctx: ctx["model_specs"],
            ROUTER_SCHEMA_PATH,
            "Router model specifications",
        ],
        "result": "model_specs",
        "when": lambda job, meta, ctx: result_available(
            ctx, 'model_specs', require_type=dict
        ),
    },
    {
        "phase": "pre",
        "fn": validate_router_settings,
        "args": [
            lambda job, meta, ctx: ctx["model_specs"],
        ],
        "when": lambda job, meta, ctx: result_available(
            ctx, 'model_specs', require_type=dict
        ),
        "result": "validate_router_settings_result",
    },
]


# ---------------------------------------------------------------------
# EXEC PHASE STEPS
# ---------------------------------------------------------------------

VALIDATE_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": validate_router_configuration,
        "args": [
            lambda job, meta, ctx: meta,
            lambda job, meta, ctx: ctx.get("model_specs"),
        ],
        "result": "validated",
        "when": lambda job, meta, ctx: result_available(
            ctx, 'model_specs', require_type=dict
        ),
    },
]


VIEW_MODEL_SPECS_EXEC = [
    {
        "phase": "exec",
        "fn": view_readme,
        "args": [
            lambda job, meta, ctx: ctx.get("model_specs"),
            MODEL_SPECS_README_PATH,
        ],
        "result": 'view_readme_result',
        "when": lambda job, meta, ctx: result_available(
            ctx, 'model_specs', require_type=dict
        ),
    },
]


VIEW_ROUTER_DETAILS_EXEC = [
    {
        "phase": "exec",
        "fn": view_router_details,
        "args": [ROUTER_DETAILS_PATH],
        "result": 'view_router_details_result',
    },
]


VIEW_ROUTER_DETAILS_HELP_EXEC = [
    {
        "phase": "exec",
        "fn": view_readme,
        "args": [None, ROUTER_DETAILS_README_PATH],
        "result": 'view_readme_result',
    },
]


VIEW_DECODED_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": view_router_config_fields,
        "args": [
            DECODED_CONFIG_PATH,
            lambda job, meta, ctx: ctx.get("model_specs"),
        ],
        "result": 'view_router_config_fields_result',
        "when": lambda job, meta, ctx: result_available(
            ctx, 'model_specs', require_type=dict
        ),
    },
]


VIEW_EDITED_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": view_router_config_fields,
        "args": [
            EDITED_CONFIG_PATH,
            lambda job, meta, ctx: ctx.get("model_specs"),
        ],
        "result": 'view_router_config_fields_result',
        "when": lambda job, meta, ctx: result_available(
            ctx, 'model_specs', require_type=dict
        ),
    },
]


DECODE_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": decode_router_config,
        "args": [
            TEMPLATE_CONFIG_PATH,
            lambda job, meta, ctx: ctx.get("model_specs"),
            lambda job, meta, ctx: meta.get(TEMPLATE_ROUTER_PASSWORD_PATH),
            lambda job, meta, ctx: meta.get(TEMPLATE_DEVICE_KEY_PATH),
        ],
        "result": "decoded_data",
        "when": lambda job, meta, ctx: result_available(
            ctx, 'model_specs', require_type=dict
        ),
    },
    {
        "phase": "exec",
        "fn": save_router_config,
        "args": [
            lambda job, meta, ctx: ctx.get("decoded_data"),
            DECODED_CONFIG_ARCHIVE_PATH,
            lambda job, meta, ctx: ctx.get("model_specs"),
        ],
        "result": "archive_saved",
        "when": lambda job, meta, ctx: (
            result_available(ctx, 'decoded_data', require_type=bytes)
            and result_available(ctx, 'model_specs', require_type=dict)
        ),
    },
    {
        "phase": "exec",
        "fn": extract_router_config,
        "args": [
            DECODED_CONFIG_ARCHIVE_PATH,
            DECODED_CONFIG_PATH,
            lambda job, meta, ctx: ctx.get("model_specs"),
        ],
        "result": "decoded_directory",
        "when": lambda job, meta, ctx: (
            result_available(ctx, 'archive_saved', require_type=bool, require_value=True)
            and result_available(ctx, 'model_specs', require_type=dict)
        ),
    },
]


EDIT_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": edit_router_config_fields,
        "args": [
            DECODED_CONFIG_PATH,
            EDITED_CONFIG_PATH,
            lambda job, meta, ctx: ctx.get("model_specs"),
            ROUTER_DETAILS_PATH,
        ],
        "result": "edited_directory",
        "when": lambda job, meta, ctx: result_available(
            ctx, 'model_specs', require_type=dict
        ),
    },
]


ENCODE_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": encode_router_config,
        "args": [
            EDITED_CONFIG_PATH,
            TEMPLATE_CONFIG_PATH,
            ENCODED_CONFIG_PATH,
            lambda job, meta, ctx: ctx.get("model_specs"),
            lambda job, meta, ctx: meta.get(TEMPLATE_ROUTER_PASSWORD_PATH),
            lambda job, meta, ctx: meta.get(TARGET_ROUTER_PASSWORD_PATH),
            lambda job, meta, ctx: meta.get(TEMPLATE_DEVICE_KEY_PATH),
            lambda job, meta, ctx: meta.get(TARGET_DEVICE_KEY_PATH),
        ],
        "result": "encoded_config",
        "when": lambda job, meta, ctx: result_available(
            ctx, 'model_specs', require_type=dict
        ),
    },
]


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
    "VALIDATE_CONFIG": {
        "pipeline": [*LOAD_MODEL_SPECS_PRE,
                     *VALIDATE_CONFIG_EXEC],
        "label": "VALIDATION_COMPLETE",
    },
    "VIEW_MODEL_SPECS": {
        "pipeline": [*LOAD_MODEL_SPECS_PRE,
                     *VIEW_MODEL_SPECS_EXEC],
        "label": "VIEW_MODEL_SPECS_COMPLETE",
    },
    "VIEW_DECODED_CONFIG": {
        "pipeline": [*LOAD_MODEL_SPECS_PRE,
                     *VIEW_DECODED_CONFIG_EXEC],
        "label": "VIEW_DECODED_COMPLETE",
    },
    "VIEW_EDITED_CONFIG": {
        "pipeline": [*LOAD_MODEL_SPECS_PRE,
                     *VIEW_EDITED_CONFIG_EXEC],
        "label": "VIEW_EDITED_COMPLETE",
    },
    "VIEW_ROUTER_DETAILS": {
        "pipeline": [*VIEW_ROUTER_DETAILS_EXEC],
        "label": "VIEW_DETAILS_COMPLETE",
    },
    "VIEW_ROUTER_DETAILS_HELP": {
        "pipeline": [*VIEW_ROUTER_DETAILS_HELP_EXEC],
        "label": "VIEW_ROUTER_DETAILS_HELP_COMPLETE",
    },
    "DECODE_CONFIG": {
        "pipeline": [*LOAD_MODEL_SPECS_PRE,
                     *DECODE_CONFIG_EXEC],
        "label": "DECODE_COMPLETE",
    },
    "EDIT_CONFIG": {
        "pipeline": [*LOAD_MODEL_SPECS_PRE,
                     *EDIT_CONFIG_EXEC],
        "label": "EDIT_COMPLETE",
    },
    "ENCODE_CONFIG": {
        "pipeline": [*LOAD_MODEL_SPECS_PRE,
                     *ENCODE_CONFIG_EXEC],
        "label": "ENCODE_COMPLETE",
    },
    "RUN_ALL": {
        "pipeline": [
            *LOAD_MODEL_SPECS_PRE,
            *VALIDATE_CONFIG_EXEC,
            *DECODE_CONFIG_EXEC,
            *VIEW_DECODED_CONFIG_EXEC,
            *EDIT_CONFIG_EXEC,
            *VIEW_EDITED_CONFIG_EXEC,
            *ENCODE_CONFIG_EXEC,
        ],
        "label": "ROUTER_AUTOMATION_COMPLETE",
    },
    "SHOW_CONFIG_DOC": {
        "pipeline": [*SHOW_CONFIG_DOC_EXEC],
        "label": "DONE",
    },
}
