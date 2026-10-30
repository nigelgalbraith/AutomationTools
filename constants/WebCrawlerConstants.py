# constants/WebCrawlerConstants.py
from __future__ import annotations

from typing import Dict, Any

from modules.system_utils import expand_path

from modules.display_utils import (
    display_config_doc,
)
from modules.web_extract_utils import (
    crawl_with_photon,
    search_web,
    print_search_results,
    merge_crawl_results,
    print_crawl_results,
    build_crawl_results,
    make_checkpoint,
    save_crawl_results,
)
from modules.web_download_utils import (
    crawl_with_selenium,
)
from modules.json_utils import (
    select_json_file,
)
from modules.browser_utils import (
    open_html_with_json,
)


# ---------------------------------------------------------------------
# CONFIG PATHS
# ---------------------------------------------------------------------

CONFIG_PATH = "config/WebCrawler.json"
TOOL_TYPE = "WebCrawler"
CONFIG_DOC = "doc/WebCrawlerDoc.json"


# ---------------------------------------------------------------------
# PHOTON CONFIG
# ---------------------------------------------------------------------

PHOTON_PYTHON = "~/apps/Photon/.venv/bin/python"
PHOTON_SCRIPT = "~/apps/Photon/photon.py"


# ---------------------------------------------------------------------
# VIEWER CONFIG
# ---------------------------------------------------------------------

WEB_VIEWER = "webCrawler/viewer/WebCrawler.html"
VIEWER_HOST = "127.0.0.1"
VIEWER_PORT = 8765


# ---------------------------------------------------------------------
# BROWSER CONFIG
# ---------------------------------------------------------------------

HEADLESS_MODE = True
MINIMIZED_MODE = True


# ---------------------------------------------------------------------
# JSON KEYS
# ---------------------------------------------------------------------

SEARCH_KEYS_SECTION = "search_keys"
CRAWL_KEYS_SECTION = "crawl_keys"
OUTPUT_KEYS_SECTION = "output_keys"
DOMAIN_KEY = "domain"
TERMS_KEY = "terms"
MAX_RESULTS_KEY = "max_results"
PHOTON_DEPTH_KEY = "photon_depth"
SELENIUM_DEPTH_KEY = "selenium_depth"
SELENIUM_MAX_PAGES_KEY = "selenium_max_pages"
DOWNLOAD_DELAY_KEY = "download_delay"
OUTPUT_DIR_KEY = "output_dir"


# ---------------------------------------------------------------------
# VALIDATION CONFIG
# ---------------------------------------------------------------------

VALIDATION_CONFIG: Dict[str, Any] = {
    "required_job_fields": {
        SEARCH_KEYS_SECTION: dict,
        CRAWL_KEYS_SECTION: dict,
        OUTPUT_KEYS_SECTION: dict,
    },
}


# ---------------------------------------------------------------------
# SECONDARY VALIDATION
# ---------------------------------------------------------------------

SECONDARY_VALIDATION: Dict[str, Any] = {
    SEARCH_KEYS_SECTION: {
        "required_job_fields": {
            DOMAIN_KEY: str,
            TERMS_KEY: list,
            MAX_RESULTS_KEY: int,
        },
    },
    CRAWL_KEYS_SECTION: {
        "required_job_fields": {
            PHOTON_DEPTH_KEY: int,
            SELENIUM_DEPTH_KEY: int,
            SELENIUM_MAX_PAGES_KEY: int,
            DOWNLOAD_DELAY_KEY: float,
        },
    },
    OUTPUT_KEYS_SECTION: {
        "required_job_fields": {
            OUTPUT_DIR_KEY: str,
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
    DOMAIN_KEY,
    TERMS_KEY,
    OUTPUT_DIR_KEY,
]


OPTIONAL_PLAN_COLUMNS: Dict[str, Any] = {}


# ---------------------------------------------------------------------
# DEPENDENCIES
# ---------------------------------------------------------------------

DEPENDENCIES = [
    "python3-selenium",
    "chromium",
    "chromium-driver",
]


# ---------------------------------------------------------------------
# ACTIONS
# ---------------------------------------------------------------------

ACTIONS: Dict[str, Dict[str, Any]] = {
    "_meta": {"title": "Web Crawler"},
    "Search web": {
        "verb": "search_web",
        "prompt": "Search web? [y/n]: ",
        "execute_state": "SEARCH_WEB",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": False,
    },
    "Crawl with Photon": {
        "verb": "crawl_photon",
        "prompt": "Search and crawl with Photon? [y/n]: ",
        "execute_state": "CRAWL_PHOTON",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": False,
    },
    "Crawl with Selenium": {
        "verb": "crawl_selenium",
        "prompt": "Search and crawl with Selenium? [y/n]: ",
        "execute_state": "CRAWL_SELENIUM",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": False,
    },
    "Run all steps": {
        "verb": "run_all",
        "prompt": "Search, crawl and save results? [y/n]: ",
        "execute_state": "RUN_ALL",
        "post_state": "MENU_SELECTION",
        "skip_prepare_plan": True,
        "skip_confirm": False,
    },
    "View results": {
        "verb": "view_results",
        "prompt": "View saved crawler results? [y/n]: ",
        "execute_state": "VIEW_RESULTS",
        "post_state": "MENU_SELECTION",
        "skip_group_select": True,
        "skip_prepare_plan": True,
        "skip_confirm": True,
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
# EXEC PHASE STEPS
# ---------------------------------------------------------------------

SEARCH_WEB_EXEC = [
    {
        "phase": "exec",
        "fn": search_web,
        "args": [
            lambda job, meta, ctx: meta[SEARCH_KEYS_SECTION][DOMAIN_KEY],
            lambda job, meta, ctx: meta[SEARCH_KEYS_SECTION][TERMS_KEY],
            lambda job, meta, ctx: meta[SEARCH_KEYS_SECTION][MAX_RESULTS_KEY],
        ],
        "result": "search_results",
    },
]


DISPLAY_SEARCH_RESULTS_EXEC = [
    {
        "phase": "exec",
        "fn": print_search_results,
        "args": [
            lambda job, meta, ctx: ctx.get("search_results", []),
        ],
        "result": "search_displayed",
    },
]


CRAWL_PHOTON_EXEC = [
    {
        "phase": "exec",
        "fn": crawl_with_photon,
        "args": [
            lambda job, meta, ctx: ctx.get("search_results", []),
            lambda job, meta, ctx: meta[SEARCH_KEYS_SECTION][TERMS_KEY],
            lambda job, meta, ctx: PHOTON_PYTHON,
            lambda job, meta, ctx: PHOTON_SCRIPT,
            lambda job, meta, ctx: meta[CRAWL_KEYS_SECTION][PHOTON_DEPTH_KEY],
            lambda job, meta, ctx: make_checkpoint(
                "photon",
                meta[SEARCH_KEYS_SECTION][DOMAIN_KEY],
                job,
                meta[OUTPUT_KEYS_SECTION][OUTPUT_DIR_KEY],
                ctx,
            ),
        ],
        "result": "photon_crawl",
    },
]


CRAWL_SELENIUM_FALLBACK_EXEC = [
    {
        "phase": "exec",
        "fn": crawl_with_selenium,
        "args": [
            lambda job, meta, ctx: ctx.get("photon_crawl", {}).get("fallback_urls", []),
            lambda job, meta, ctx: meta[SEARCH_KEYS_SECTION][TERMS_KEY],
            lambda job, meta, ctx: HEADLESS_MODE,
            lambda job, meta, ctx: MINIMIZED_MODE,
            lambda job, meta, ctx: meta[CRAWL_KEYS_SECTION][DOWNLOAD_DELAY_KEY],
            lambda job, meta, ctx: meta[CRAWL_KEYS_SECTION][SELENIUM_DEPTH_KEY],
            lambda job, meta, ctx: meta[CRAWL_KEYS_SECTION][SELENIUM_MAX_PAGES_KEY],
            lambda job, meta, ctx: make_checkpoint(
                "selenium",
                meta[SEARCH_KEYS_SECTION][DOMAIN_KEY],
                job,
                meta[OUTPUT_KEYS_SECTION][OUTPUT_DIR_KEY],
                ctx,
            ),
        ],
        "result": "selenium_results",
    },
]


CRAWL_SELENIUM_ALL_EXEC = [
    {
        "phase": "exec",
        "fn": crawl_with_selenium,
        "args": [
            lambda job, meta, ctx: ctx.get("search_results", []),
            lambda job, meta, ctx: meta[SEARCH_KEYS_SECTION][TERMS_KEY],
            lambda job, meta, ctx: HEADLESS_MODE,
            lambda job, meta, ctx: MINIMIZED_MODE,
            lambda job, meta, ctx: meta[CRAWL_KEYS_SECTION][DOWNLOAD_DELAY_KEY],
            lambda job, meta, ctx: meta[CRAWL_KEYS_SECTION][SELENIUM_DEPTH_KEY],
            lambda job, meta, ctx: meta[CRAWL_KEYS_SECTION][SELENIUM_MAX_PAGES_KEY],
            lambda job, meta, ctx: make_checkpoint(
                "selenium",
                meta[SEARCH_KEYS_SECTION][DOMAIN_KEY],
                job,
                meta[OUTPUT_KEYS_SECTION][OUTPUT_DIR_KEY],
                ctx,
            ),
        ],
        "result": "selenium_results",
    },
]


OUTPUT_RESULTS_EXEC = [
    {
        "phase": "exec",
        "fn": merge_crawl_results,
        "args": [
            lambda job, meta, ctx: ctx.get("photon_crawl", {}).get("results", []),
            lambda job, meta, ctx: ctx.get("selenium_results", []),
        ],
        "result": "final_results",
    },
    {
        "phase": "exec",
        "fn": print_crawl_results,
        "args": [
            lambda job, meta, ctx: ctx.get("final_results", []),
        ],
        "result": "printed_results",
    },
    {
        "phase": "exec",
        "fn": build_crawl_results,
        "args": [
            lambda job, meta, ctx: meta[SEARCH_KEYS_SECTION][DOMAIN_KEY],
            lambda job, meta, ctx: ctx.get("final_results", []),
        ],
        "result": "result_data",
    },
    {
        "phase": "exec",
        "fn": save_crawl_results,
        "args": [
            lambda job, meta, ctx: ctx.get("result_data", {}),
            lambda job, meta, ctx: meta[OUTPUT_KEYS_SECTION][OUTPUT_DIR_KEY],
            lambda job, meta, ctx: job,
        ],
        "result": "saved_result",
    },
]


OPEN_RESULTS_EXEC = [
    {
        "phase": "exec",
        "fn": open_html_with_json,
        "args": [
            lambda job, meta, ctx: WEB_VIEWER,
            lambda job, meta, ctx: ctx.get("saved_result"),
            lambda job, meta, ctx: VIEWER_HOST,
            lambda job, meta, ctx: VIEWER_PORT,
        ],
        "result": "viewer_opened",
    },
]


VIEW_RESULTS_EXEC = [
    {
        "phase": "exec",
        "fn": select_json_file,
        "args": [
            lambda job, meta, ctx: expand_path(meta[OUTPUT_KEYS_SECTION][OUTPUT_DIR_KEY]),
        ],
        "result": "selected_result",
    },
    {
        "phase": "exec",
        "fn": open_html_with_json,
        "args": [
            lambda job, meta, ctx: WEB_VIEWER,
            lambda job, meta, ctx: ctx.get("selected_result"),
            lambda job, meta, ctx: VIEWER_HOST,
            lambda job, meta, ctx: VIEWER_PORT,
        ],
        "result": "viewer_opened",
    },
]


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
    "SEARCH_WEB": {
        "pipeline": [
            *SEARCH_WEB_EXEC,
            *DISPLAY_SEARCH_RESULTS_EXEC,
        ],
        "label": "SEARCH_WEB_COMPLETE",
    },
    "CRAWL_PHOTON": {
        "pipeline": [
            *SEARCH_WEB_EXEC,
            *CRAWL_PHOTON_EXEC,
            *OUTPUT_RESULTS_EXEC,
            *OPEN_RESULTS_EXEC,
        ],
        "label": "CRAWL_PHOTON_COMPLETE",
    },
    "CRAWL_SELENIUM": {
        "pipeline": [
            *SEARCH_WEB_EXEC,
            *CRAWL_SELENIUM_ALL_EXEC,
            *OUTPUT_RESULTS_EXEC,
            *OPEN_RESULTS_EXEC,
        ],
        "label": "CRAWL_SELENIUM_COMPLETE",
    },
    "RUN_ALL": {
        "pipeline": [
            *SEARCH_WEB_EXEC,
            *CRAWL_PHOTON_EXEC,
            *CRAWL_SELENIUM_FALLBACK_EXEC,
            *OUTPUT_RESULTS_EXEC,
            *OPEN_RESULTS_EXEC,
        ],
        "label": "ALL_STEPS_COMPLETE",
    },
    "VIEW_RESULTS": {
        "pipeline": [
            *VIEW_RESULTS_EXEC,
        ],
        "label": "VIEW_RESULTS_COMPLETE",
    },
    "SHOW_CONFIG_DOC": {
        "pipeline": [
            *SHOW_CONFIG_DOC_EXEC,
        ],
        "label": "DONE",
    },
}
