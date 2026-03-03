# constants/TextCreatorConstants.py
from __future__ import annotations
from typing import Dict, Any

from modules.display_utils import (
  display_config_doc,
)
from modules.web_extract_utils import (
  extract_fields_from_url,
  list_html_files,
)
from modules.json_utils import (
  load_items_from_dir,
  save_items_json_dir,
)
from modules.prompt_utils import (
  write_prompts_from_items,
)
from modules.ollama_utils import (
  generate_text_from_prompts_dir,
)
from modules.docker_utils import (
  start_ollama_compose,
  stop_ollama_compose,
)
from modules.selenium_downloader import (
    download_html_pages,
)

# CONSTANTS
CONFIG_PATH = "config/TextCreator.json"
TOOL_TYPE = "TextCreator"
CONFIG_DOC = "doc/TextCreatorDoc.json"
BASE_URL = "http://localhost:11434"
MODEL = "phi3:latest"
TEMPERATURE = 0.25
OLLAMA_COMPOSE_DIR = "docker/ollama"
HEADLESS_MODE = False
MINIMIZED_MODE = True
SHOW_SOURCE_ON_EXTRACTION = True

# CONSTANTS
DOWNLOAD_KEYS_SECTION = "download_keys"
EXTRACT_KEYS_SECTION = "extract_keys"
PROMPT_KEYS_SECTION = "prompt_keys"
DOWNLOAD_LOC_KEY = "download_loc"
LETTERS_OUT_DIR_KEY = "text_out_dir"
PROMPT_TEMPLATE_PATH_KEY = "prompt_template_path"
PROMPTS_OUT_DIR_KEY = "prompts_out_dir"
PROMPT_INJECTION_KEYS_KEY = "prompt_injection_keys"
HTML_DIR_KEY = "html_dir"
ITEMS_OUT_DIR_KEY = "items_out_dir"
EXTRACT_RULES_KEY = "extract_rules"
BASENAME_KEYS_KEY = "basename_keys"
DL_URLS_KEY = "download_urls"
FOLLOW_LINKS_KEY = "follow_links"
LINK_SELECTOR_KEY = "link_selector"
LINKS_PER_SEARCH_KEY = "links_per_search"
DOWNLOAD_DELAY_KEY = "download_delay"
FILENAME_FROM_URL_REGEX_KEY = "filename_from_url_regex"
TITLE_SELECTORS_KEY = "title_selectors"

# VALIDATION
VALIDATION_CONFIG: Dict[str, Any] = {
  "required_job_fields": {
    DOWNLOAD_KEYS_SECTION: dict,
    EXTRACT_KEYS_SECTION: dict,
    PROMPT_KEYS_SECTION: dict,
  },
}

SECONDARY_VALIDATION: Dict[str, Any] = {
  DOWNLOAD_KEYS_SECTION: {
    "required_job_fields": {
      DOWNLOAD_LOC_KEY: str,
      DL_URLS_KEY: list,
      LINK_SELECTOR_KEY: str,
      LINKS_PER_SEARCH_KEY: int,
      DOWNLOAD_DELAY_KEY: float,
      FOLLOW_LINKS_KEY: bool,
      FILENAME_FROM_URL_REGEX_KEY: str,
      TITLE_SELECTORS_KEY: list,
    },
    "allow_empty": True,
  },

  EXTRACT_KEYS_SECTION: {
    "required_job_fields": {
      HTML_DIR_KEY: str,
      ITEMS_OUT_DIR_KEY: str,
      EXTRACT_RULES_KEY: dict,
      BASENAME_KEYS_KEY: list,
    }
  },

  PROMPT_KEYS_SECTION: {
    "required_job_fields": {
      LETTERS_OUT_DIR_KEY: str,
      PROMPT_TEMPLATE_PATH_KEY: str,
      PROMPTS_OUT_DIR_KEY: str,
      PROMPT_INJECTION_KEYS_KEY: list,
    }
  },
}

REQUIRED_USER = "standard"

# CONSTANTS
PLAN_COLUMN_ORDER = [
  PROMPT_TEMPLATE_PATH_KEY,
  PROMPTS_OUT_DIR_KEY,
  LETTERS_OUT_DIR_KEY,
]
OPTIONAL_PLAN_COLUMNS: Dict[str, Any] = {}
DEPENDENCIES = ["python3-selenium", "chromium-driver"]

# CORE
ACTIONS: Dict[str, Dict[str, Any]] = {
  "_meta": {"title": "Text Creator"},
  "Download html": {
    "verb": "download_html_pages",
    "prompt": "Download HTML files from URL? [y/n]: ",
    "execute_state": "DOWNLOAD_HTML_PAGES",
    "post_state": "MENU_SELECTION",
    "skip_prepare_plan": True,
    "skip_confirm": False,
  },
  "Extract fields": {
    "verb": "extract_fields_html",
    "prompt": "Extract fields from saved HTML files? [y/n]: ",
    "execute_state": "EXTRACT_FIELDS_HTML",
    "post_state": "MENU_SELECTION",
    "skip_prepare_plan": True,
    "skip_confirm": False,
  },
  "Update prompts": {
    "verb": "update_prompts",
    "prompt": "Create prompt text files from extracted items? [y/n]: ",
    "execute_state": "UPDATE_PROMPTS",
    "post_state": "MENU_SELECTION",
    "skip_prepare_plan": True,
    "skip_confirm": False,
  },
  "Start Ollama": {
    "verb": "start_ollama",
    "prompt": "Start Ollama Docker compose? [y/n]: ",
    "execute_state": "START_OLLAMA",
    "post_state": "MENU_SELECTION",
    "skip_prepare_plan": True,
    "skip_confirm": False,
    "skip_group_select": True,
  },
  "Generate letters": {
    "verb": "generate_text",
    "prompt": "Generate text from prompt text files? [y/n]: ",
    "execute_state": "GENERATE_TEXT",
    "post_state": "MENU_SELECTION",
    "skip_prepare_plan": True,
    "skip_confirm": False,
  },
  "Stop Ollama": {
    "verb": "stop_ollama",
    "prompt": "Stop Ollama Docker compose? [y/n]: ",
    "execute_state": "STOP_OLLAMA",
    "post_state": "MENU_SELECTION",
    "skip_prepare_plan": True,
    "skip_confirm": False,
    "skip_group_select": True,
  },
  "Run all steps": {
    "verb": "run_all",
    "prompt": "Run all steps in sequence (download, extract, update, start Ollama, generate, stop Ollama)? [y/n]: ",
    "execute_state": "RUN_ALL",
    "post_state": "MENU_SELECTION",
    "skip_prepare_plan": True,
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

# CORE
DOWNLOAD_HTML_EXEC = [
  {
    "phase": "exec",
    "fn": download_html_pages,
    "args": [
      lambda job, meta, ctx: meta[DOWNLOAD_KEYS_SECTION][DL_URLS_KEY],
      lambda job, meta, ctx: meta[DOWNLOAD_KEYS_SECTION][DOWNLOAD_LOC_KEY],
      lambda job, meta, ctx: meta[DOWNLOAD_KEYS_SECTION].get(FOLLOW_LINKS_KEY, True),
      lambda job, meta, ctx: meta[DOWNLOAD_KEYS_SECTION][LINK_SELECTOR_KEY],
      lambda job, meta, ctx: meta[DOWNLOAD_KEYS_SECTION][LINKS_PER_SEARCH_KEY],
      lambda job, meta, ctx: HEADLESS_MODE,
      lambda job, meta, ctx: MINIMIZED_MODE,
      lambda job, meta, ctx: meta[DOWNLOAD_KEYS_SECTION][DOWNLOAD_DELAY_KEY],
      lambda job, meta, ctx: meta[DOWNLOAD_KEYS_SECTION][FILENAME_FROM_URL_REGEX_KEY],
      lambda job, meta, ctx: meta[DOWNLOAD_KEYS_SECTION][TITLE_SELECTORS_KEY],
    ],
    "result": "download_results",
  }
]

EXTRACT_FIELDS_HTML_EXEC = [
  {
    "phase": "exec",
    "fn": list_html_files,
    "args": [
      lambda job, meta, ctx: meta[EXTRACT_KEYS_SECTION][HTML_DIR_KEY],
    ],
    "result": "sources",
  },
  {
    "phase": "exec",
    "fn": extract_fields_from_url,
    "args": [
      lambda job, meta, ctx: ctx.get("sources", []),
      lambda job, meta, ctx: meta[EXTRACT_KEYS_SECTION].get(EXTRACT_RULES_KEY, {}),
      lambda job, meta, ctx: SHOW_SOURCE_ON_EXTRACTION,
    ],
    "result": "items",
    "when": lambda job, meta, ctx: bool(ctx.get("sources")),
  },
  {
    "phase": "exec",
    "fn": save_items_json_dir,
    "args": [
      lambda job, meta, ctx: ctx.get("items", []),
      lambda job, meta, ctx: meta[EXTRACT_KEYS_SECTION][ITEMS_OUT_DIR_KEY],
      lambda job, meta, ctx: meta[EXTRACT_KEYS_SECTION].get(BASENAME_KEYS_KEY, []),
    ],
    "result": "saved_items_ok",
    "when": lambda job, meta, ctx: bool(ctx.get("items")),
  },
]

UPDATE_PROMPTS_EXEC = [
  {
    "phase": "exec",
    "fn": load_items_from_dir,
    "args": [
      lambda job, meta, ctx: meta[EXTRACT_KEYS_SECTION][ITEMS_OUT_DIR_KEY],
    ],
    "result": "items",
  },
  {
    "phase": "exec",
    "fn": write_prompts_from_items,
    "args": [
      lambda job, meta, ctx: meta[PROMPT_KEYS_SECTION][PROMPT_TEMPLATE_PATH_KEY],
      lambda job, meta, ctx: meta[PROMPT_KEYS_SECTION][PROMPTS_OUT_DIR_KEY],
      lambda job, meta, ctx: ctx.get("items", []),
      lambda job, meta, ctx: meta[PROMPT_KEYS_SECTION].get(PROMPT_INJECTION_KEYS_KEY, []),
      lambda job, meta, ctx: meta[EXTRACT_KEYS_SECTION].get(BASENAME_KEYS_KEY, []),
    ],
    "result": "saved_prompts_count",
    "when": lambda job, meta, ctx: bool(ctx.get("items")),
  },
]

START_OLLAMA_EXEC = [
  {
    "phase": "exec",
    "fn": start_ollama_compose,
    "args": [
      lambda job, meta, ctx: OLLAMA_COMPOSE_DIR,
    ],
    "result": "started_ollama_ok",
  },
]

GENERATE_TEXT_EXEC = [
  {
    "phase": "exec",
    "fn": generate_text_from_prompts_dir,
    "args": [
      lambda job, meta, ctx: meta[PROMPT_KEYS_SECTION][PROMPTS_OUT_DIR_KEY],
      lambda job, meta, ctx: meta[PROMPT_KEYS_SECTION][LETTERS_OUT_DIR_KEY],
      lambda job, meta, ctx: BASE_URL,
      lambda job, meta, ctx: MODEL,
      lambda job, meta, ctx: float(TEMPERATURE),
    ],
    "result": "text_summary",
  },
]

STOP_OLLAMA_EXEC = [
  {
    "phase": "exec",
    "fn": stop_ollama_compose,
    "args": [
      lambda job, meta, ctx: OLLAMA_COMPOSE_DIR,
    ],
    "result": "stopped_ollama_ok",
  },
]

SHOW_CONFIG_DOC_EXEC = [
  {
    "phase": "exec",
    "fn": display_config_doc,
    "args": [CONFIG_DOC],
    "result": "ok",
  },
]

# CORE
PIPELINE_STATES: Dict[str, Dict[str, Any]] = {
  "DOWNLOAD_HTML_PAGES": {
    "pipeline": [
      *DOWNLOAD_HTML_EXEC,
    ],
    "label": "DOWNLOAD_HTML_PAGES_COMPLETE",
    "success_key": "download_results",
  },
  "EXTRACT_FIELDS_HTML": {
    "pipeline": [
      *EXTRACT_FIELDS_HTML_EXEC,
    ],
    "label": "EXTRACT_FIELDS_HTML_COMPLETE",
    "success_key": "saved_items_ok",
  },
  "UPDATE_PROMPTS": {
    "pipeline": [
      *UPDATE_PROMPTS_EXEC,
    ],
    "label": "UPDATE_PROMPTS_COMPLETE",
    "success_key": "saved_prompts_count",
  },
  "START_OLLAMA": {
    "pipeline": [
      *START_OLLAMA_EXEC,
    ],
    "label": "START_OLLAMA_COMPLETE",
    "success_key": "started_ollama_ok",
  },
  "GENERATE_TEXT": {
    "pipeline": [
      *GENERATE_TEXT_EXEC,
    ],
    "label": "GENERATE_TEXT_COMPLETE",
    "success_key": "text_summary",
  },
  "STOP_OLLAMA": {
    "pipeline": [
      *STOP_OLLAMA_EXEC,
    ],
    "label": "STOP_OLLAMA_COMPLETE",
    "success_key": "stopped_ollama_ok",
  },
  "RUN_ALL": {
    "pipeline": [
      *DOWNLOAD_HTML_EXEC,
      *EXTRACT_FIELDS_HTML_EXEC,
      *UPDATE_PROMPTS_EXEC,
      *START_OLLAMA_EXEC,
      *GENERATE_TEXT_EXEC,
      *STOP_OLLAMA_EXEC,
    ],
    "label": "ALL_STEPS_COMPLETE",
    "success_key": "stopped_ollama_ok",
  },
  "SHOW_CONFIG_DOC": {
    "pipeline": [
      *SHOW_CONFIG_DOC_EXEC,
    ],
    "label": "DONE",
    "success_key": "ok",
  },
}
