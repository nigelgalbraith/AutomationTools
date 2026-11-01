
# constants/TestConstants.py

from pathlib import Path

from modules.test_utils import (
    load_test_pipelines,
    check_pipeline_structure,
)
from modules.display_utils import display_config_doc


# ---------------------------------------------------------------------
# CONFIG PATHS
# ---------------------------------------------------------------------

CONFIG_PATH = "config/TestsConfig.json"
TOOL_TYPE   = "Tests"
CONFIG_DOC  = "doc/TestsDoc.json"


# ---------------------------------------------------------------------
# JSON KEYS
# ---------------------------------------------------------------------

KEY_TESTS    = "Tests"
KEY_PIPELINE = "pipeline"


# ---------------------------------------------------------------------
# VALIDATION CONFIG
# ---------------------------------------------------------------------

VALIDATION_CONFIG = {
    "required_job_fields": {
        KEY_TESTS: list,
    },
}


# ---------------------------------------------------------------------
# SECONDARY VALIDATION
# ---------------------------------------------------------------------

SECONDARY_VALIDATION = {
    KEY_TESTS: {
        "required_job_fields": {
            KEY_PIPELINE: str,
        },
        "allow_empty": False,
    },
}


# ---------------------------------------------------------------------
# USER / LABELS
# ---------------------------------------------------------------------

REQUIRED_USER = "standard"
TESTED_LABEL  = "TESTED"


# ---------------------------------------------------------------------
# DEPENDENCIES
# ---------------------------------------------------------------------

DEPENDENCIES = []


# ---------------------------------------------------------------------
# COLUMN ORDER
# ---------------------------------------------------------------------

PLAN_COLUMN_ORDER = [
    KEY_TESTS,
]

OPTIONAL_PLAN_COLUMNS = {}


# ---------------------------------------------------------------------
# MENU / ACTIONS
# ---------------------------------------------------------------------

ACTIONS = {
    "_meta": {"title": "Pipeline Tests"},

    "Run Tests": {
        "verb": "test",
        "prompt": "Run selected pipeline tests? [y/n]: ",
        "execute_state": "RUN_TESTS",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
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
    },
}


# ---------------------------------------------------------------------
# PIPELINES
# ---------------------------------------------------------------------

PIPELINE_STATES = {
    "RUN_TESTS": {
        "pipeline": [
            {
                "phase": "exec",
                "fn": load_test_pipelines,
                "args": ["job", KEY_TESTS],
                "result": "pipelines_loaded",
            },
            {
                "phase": "exec",
                "fn": check_pipeline_structure,
                "args": ["pipelines_loaded"],
                "when": "pipelines_loaded",
                "result": "ok",
            },
        ],
        "label": TESTED_LABEL,
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
    },
}
