
# Automation Tools Loader

A modular, configuration-driven automation framework built around a single execution loader.

This project provides a structured way to build and run automation tools using:

- A centralized loader
- Tool-specific constants modules
- JSON configuration files
- Structured execution pipelines
- Explicit validation rules
- Dependency management
- Reusable utility modules

---

## Overview

`AutomationLoader.py` is the main execution entry point.

Each automation tool is defined through a constants module that specifies:

- Configuration file paths
- Required dependencies
- Validation rules
- Available actions
- Pipeline execution states
- User requirements

The loader manages common execution tasks while tool-specific functionality remains in separate modules.

### Available Tools

- **Text Creator** — Downloads HTML pages, extracts structured data, generates prompts, and produces text using Ollama.
- **Web Crawler** — Performs web searches and website crawling, processes results, and provides an HTML results viewer.
- **Ubuntu ISO Editor** — Creates customized Ubuntu Desktop installation ISOs using Autoinstall YAML configurations.
- **Function Utility** — Provides function inspection and usage information.

The framework supports additional tools through its constants-module registration system.

---

## Architecture

### 1. Loader

**AutomationLoader.py**

Responsible for:

- Loading registered constants modules
- Checking and installing dependencies
- Loading JSON configuration files
- Validating configuration structure
- Displaying configuration documentation
- Building tool and action menus
- Selecting configuration groups
- Preparing execution plans
- Requesting confirmation
- Executing pipeline states
- Reporting execution results

The loader contains no tool-specific implementation logic.

### 2. Constants Modules

Located in:

```text
constants/
```

Each tool defines its configuration and execution behaviour.

Common constants include:

- `CONFIG_PATH`
- `TOOL_TYPE`
- `CONFIG_DOC`
- `VALIDATION_CONFIG`
- `SECONDARY_VALIDATION`
- `REQUIRED_USER`
- `PLAN_COLUMN_ORDER`
- `OPTIONAL_PLAN_COLUMNS`
- `DEPENDENCIES`
- `ACTIONS`
- `PIPELINE_STATES`

Constants modules connect the loader to functions implemented in the relevant utility modules.

### 3. Configuration

Located in:

```text
config/
```

Each tool has a corresponding JSON configuration file.

Configuration is organized into named groups, with the structure determined by the tool.

For example:

```json
{
  "GNOME": {
    "iso_keys": {
      "source_iso": "~/Downloads/ubuntu-26.04.1-desktop-amd64.iso",
      "autoinstall_path": "ISOEditor/autoInstall/ubuntu2604AutoInstall/ubuntu-26.04.1-desktop-amd64-gnome.yaml",
      "output_iso": "~/Downloads/ubuntu-26.04.1-desktop-amd64-gnome.iso"
    }
  }
}
```

Each group represents a configuration profile that can be selected for execution.

The loader supports selecting individual groups or the `All` option where applicable.

### 4. Documentation

Located in:

```text
doc/
```

Tool documentation is stored in JSON files containing:

- `EXAMPLE`
- `DESCRIPTION`

The loader uses these files to display structured configuration help.

### 5. Utility Modules

Located in:

```text
modules/
```

Utility modules contain reusable functionality used by the constants modules and execution pipelines.

Examples include:

- `browser_utils.py`
- `display_utils.py`
- `docker_utils.py`
- `function_utils.py`
- `iso_utils.py`
- `json_utils.py`
- `ollama_utils.py`
- `package_utils.py`
- `state_machine_utils.py`
- `system_utils.py`
- `web_download_utils.py`
- `web_extract_utils.py`

This separates implementation logic from configuration and execution management.

---

## Pipeline Execution Model

Each action references an execution state defined in `PIPELINE_STATES`.

A pipeline contains an ordered list of steps.

Example:

```python
PIPELINE_STATES = {
    "CREATE_UBUNTU_ISO": {
        "pipeline": [
            *VALIDATE_ISO_PRE,
            *CREATE_ISO_EXEC,
        ],
        "label": "CREATE_UBUNTU_ISO_COMPLETE",
        "success_key": "iso_success",
    },
}
```

Individual pipeline steps specify:

- `phase` — Execution phase
- `fn` — Function to execute
- `args` — Function arguments
- `result` — Context key for the result
- `when` — Optional execution condition

Example:

```python
{
    "phase": "pre",
    "fn": validate_ubuntu_iso_plan,
    "args": [
        lambda job, meta, ctx: meta["iso_keys"]["source_iso"],
        lambda job, meta, ctx: meta["iso_keys"]["autoinstall_path"],
        lambda job, meta, ctx: meta["iso_keys"]["output_iso"],
    ],
    "result": "plan_valid",
}
```

Supported pipeline phases include:

- `pre` — Preparation and validation
- `exec` — Main action execution
- `post` — Post-execution processing

The loader executes configured pipeline steps in order and stores their results in the execution context.

---

## Directory Structure

```text
AutomationTools/
│
├── AutomationLoader.py
├── README.md
│
├── constants/
│   ├── FunctionConstants.py
│   ├── TextCreatorConstants.py
│   ├── WebCrawlerConstants.py
│   └── UbuntuISOEditorConstants.py
│
├── config/
│   ├── FunctionsConfig.json
│   ├── TextCreator.json
│   ├── WebCrawler.json
│   └── UbuntuISOEditor.json
│
├── config-sample/
│   ├── TextCreator.json
│   ├── WebCrawler.json
│   └── UbuntuISOEditor.json
│
├── doc/
│   ├── FunctionDoc.json
│   ├── TextCreatorDoc.json
│   ├── WebCrawlerDoc.json
│   └── UbuntuISOEditorDoc.json
│
├── modules/
│   ├── browser_utils.py
│   ├── display_utils.py
│   ├── docker_utils.py
│   ├── function_utils.py
│   ├── iso_utils.py
│   ├── json_utils.py
│   ├── ollama_utils.py
│   ├── package_utils.py
│   ├── state_machine_utils.py
│   ├── system_utils.py
│   ├── web_download_utils.py
│   └── web_extract_utils.py
│
├── textCreator/
│   ├── promptTemplates/
│   └── promptTemplates-sample/
│
├── webCrawler/
│   └── viewer/
│       ├── WebCrawler.html
│       ├── css/
│       ├── images/
│       └── js/
│
├── ISOEditor/
│   └── autoInstall/
│       └── ubuntu2604AutoInstall/
│           ├── ubuntu-26.04.1-desktop-amd64-gnome.yaml
│           └── ubuntu-26.04.1-desktop-amd64-kde.yaml
│
└── docker/
    ├── ollama/
    │   └── docker-compose.yml
    └── scripts/
        └── pull_ollama_models.sh
```

The framework can be extended with additional tools, configurations, documentation and utility modules.

---

## Installation

### Requirements

- Python 3.10+
- Linux environment
- Tool-specific Python and system dependencies
- Docker for functionality that uses containerized services

Dependencies vary depending on the selected tool.

Examples include:

- `xorriso`
- `python3-yaml`
- `python3-selenium`
- `chromium`
- `chromium-driver`

The loader checks declared dependencies and can install missing APT packages when required.

### Setup

Clone or download the project and open its root directory.

Configure the required JSON files and tool-specific resources before execution.

Sample configurations are provided in:

```text
config-sample/
```

---

## Running the Loader

From the project root:

```bash
python3 AutomationLoader.py
```

The loader displays the registered tools.

Select a tool, choose an action, and select the relevant configuration group.

Execution then proceeds through the configured pipeline.

### Direct Tool Selection

A tool can be launched directly using its constants module.

Text Creator:

```bash
python3 AutomationLoader.py --constants constants.TextCreatorConstants
```

Web Crawler:

```bash
python3 AutomationLoader.py --constants constants.WebCrawlerConstants
```

Ubuntu ISO Editor:

```bash
python3 AutomationLoader.py --constants constants.UbuntuISOEditorConstants
```

Function Utility:

```bash
python3 AutomationLoader.py --constants constants.FunctionConstants
```

### Plan-Only Mode

The loader supports plan-only execution:

```bash
python3 AutomationLoader.py --constants constants.UbuntuISOEditorConstants --plan-only
```

This prepares the selected action without performing its main execution phase.

Dependency checks and installations may still occur.

---

## Configuration System

Each tool defines its configuration paths in its constants module.

Example:

```python
CONFIG_PATH = "config/UbuntuISOEditor.json"
TOOL_TYPE = "UbuntuISOEditor"
CONFIG_DOC = "doc/UbuntuISOEditorDoc.json"
```

### Primary Validation

Primary validation checks required configuration sections.

```python
VALIDATION_CONFIG = {
    "required_job_fields": {
        "iso_keys": dict,
    },
}
```

### Secondary Validation

Secondary validation checks required fields within a section.

```python
SECONDARY_VALIDATION = {
    "iso_keys": {
        "required_job_fields": {
            "source_iso": str,
            "autoinstall_path": str,
            "output_iso": str,
        },
    },
}
```

### Runtime Validation

Tools can perform additional validation through their pipeline functions.

For example, Ubuntu ISO Editor validates:

- Source ISO paths
- Autoinstall YAML files
- Output ISO destinations
- Ubuntu Desktop installation metadata
- Required YAML structure
- Existing output files

Validation requirements depend on the selected tool.

---

## Text Creator

The Text Creator automates the collection of HTML content, extraction of structured information, prompt generation and text creation using an LLM backend.

### Features

- Download HTML pages
- Extract structured fields from HTML
- Save extracted information
- Generate prompts from templates
- Start and stop Ollama
- Generate text using configured models
- Execute individual processing stages
- Run the complete workflow

### Configuration

```text
config/TextCreator.json
```

Constants:

```text
constants/TextCreatorConstants.py
```

Documentation:

```text
doc/TextCreatorDoc.json
```

Prompt templates:

```text
textCreator/promptTemplates/
```

Sample templates:

```text
textCreator/promptTemplates-sample/
```

### Available Actions

- Download HTML pages
- Extract fields from HTML
- Update prompts
- Start Ollama
- Generate text
- Stop Ollama
- Run All
- Show config help
- Cancel

### Workflow

1. Download configured HTML pages.
2. Extract structured information from the downloaded content.
3. Save the extracted information.
4. Generate prompts using the configured templates.
5. Start the Ollama service when required.
6. Generate text using the selected model.
7. Save the generated output.
8. Stop Ollama when requested.

Individual actions can be executed independently.

### Ollama Integration

Ollama-related functionality is implemented in:

```text
modules/ollama_utils.py
```

Docker configuration is located in:

```text
docker/ollama/docker-compose.yml
```

Supporting scripts are located in:

```text
docker/scripts/
```

---

## Web Crawler

The Web Crawler provides tools for searching websites, crawling pages, processing collected results and viewing the output.

### Features

- Web search
- Photon-based crawling
- Selenium-based crawling
- Combined crawling workflows
- Result processing and merging
- JSON result generation
- HTML-based results viewer

### Configuration

```text
config/WebCrawler.json
```

Constants:

```text
constants/WebCrawlerConstants.py
```

Documentation:

```text
doc/WebCrawlerDoc.json
```

### Available Actions

- Search Web
- Crawl with Photon
- Crawl with Selenium
- Run All
- View Results
- Show config help
- Cancel

### Workflow

1. Select a configured crawler group.
2. Choose the required search or crawling action.
3. Execute the configured crawler.
4. Process and merge collected results where applicable.
5. Save results in JSON format.
6. Open saved results using the HTML viewer.

### Web Crawler Viewer

The viewer is located in:

```text
webCrawler/viewer/
```

Main page:

```text
webCrawler/viewer/WebCrawler.html
```

Supporting files:

```text
webCrawler/viewer/js/WebCrawler.js
webCrawler/viewer/css/WebCrawler.css
```

The viewer provides a separate interface for inspecting saved crawler results.

### Supporting Modules

Web crawling functionality uses utility modules including:

- `browser_utils.py`
- `web_download_utils.py`
- `web_extract_utils.py`
- `json_utils.py`

---

## Ubuntu ISO Editor

The Ubuntu ISO Editor creates customized Ubuntu Desktop installation ISOs by embedding an Autoinstall YAML configuration.

### Features

- GNOME and KDE configuration groups
- Support for additional compatible Ubuntu Desktop versions
- Explicit source ISO paths
- Explicit Autoinstall YAML paths
- Explicit output ISO filenames
- Interactive storage selection during installation
- Preservation of existing ISO boot configuration
- Embedded YAML verification
- Boot metadata verification
- Protection against overwriting existing files

### Configuration

```text
config/UbuntuISOEditor.json
```

Constants:

```text
constants/UbuntuISOEditorConstants.py
```

Documentation:

```text
doc/UbuntuISOEditorDoc.json
```

Utility module:

```text
modules/iso_utils.py
```

### Available Actions

- Create Ubuntu ISO
- Show config help
- Cancel

### Configuration Groups

Example:

```json
{
  "GNOME": {
    "iso_keys": {
      "source_iso": "~/Downloads/ubuntu-26.04.1-desktop-amd64.iso",
      "autoinstall_path": "ISOEditor/autoInstall/ubuntu2604AutoInstall/ubuntu-26.04.1-desktop-amd64-gnome.yaml",
      "output_iso": "~/Downloads/ubuntu-26.04.1-desktop-amd64-gnome.iso"
    }
  },
  "KDE": {
    "iso_keys": {
      "source_iso": "~/Downloads/ubuntu-26.04.1-desktop-amd64.iso",
      "autoinstall_path": "ISOEditor/autoInstall/ubuntu2604AutoInstall/ubuntu-26.04.1-desktop-amd64-kde.yaml",
      "output_iso": "~/Downloads/ubuntu-26.04.1-desktop-amd64-kde.iso"
    }
  }
}
```

### ISO Creation Process

1. Select `Create Ubuntu ISO`.
2. Select GNOME, KDE or All.
3. Validate the configured source ISO, YAML and output paths.
4. Confirm execution.
5. Create the customized ISO using xorriso.
6. Verify the embedded YAML.
7. Verify the ISO boot metadata.
8. Publish the completed ISO to its configured output path.

Each configuration group defines its own YAML and output ISO.

There is no separate YAML selection menu.

### Adding Another Ubuntu Version

Additional Ubuntu versions can be configured by adding another group to `config/UbuntuISOEditor.json`.

Example:

```json
{
  "GNOME-NewVersion": {
    "iso_keys": {
      "source_iso": "/path/to/source.iso",
      "autoinstall_path": "/path/to/autoinstall.yaml",
      "output_iso": "/path/to/output.iso"
    }
  }
}
```

No changes to the constants or ISO utility modules are required solely to add another configuration group.

Compatibility depends on the Ubuntu Desktop source ISO and installer.

---

## Function Utility

The Function Utility provides functionality for inspecting module functions and their usage.

### Features

- Inspect available module functions
- Display function documentation
- Identify function usage
- Display function usage summaries

### Configuration

```text
config/FunctionsConfig.json
```

Constants:

```text
constants/FunctionConstants.py
```

Documentation:

```text
doc/FunctionDoc.json
```

Utility module:

```text
modules/function_utils.py
```

The Function Utility uses the same loader architecture as the other registered tools.

---

## Adding a New Tool

### 1. Create a Constants Module

```text
constants/MyToolConstants.py
```

Define the required constants, including:

- `CONFIG_PATH`
- `TOOL_TYPE`
- `CONFIG_DOC`
- `VALIDATION_CONFIG`
- `ACTIONS`
- `PIPELINE_STATES`

Add other constants required by the loader.

### 2. Create a Configuration File

```text
config/MyTool.json
```

Define the configuration groups and their required settings.

### 3. Create a Documentation File

```text
doc/MyToolDoc.json
```

Include:

- `EXAMPLE`
- `DESCRIPTION`

### 4. Implement Utility Functions

Create or reuse functions in:

```text
modules/
```

Keep tool-specific implementation separate from the loader.

### 5. Register the Tool

Add the constants module to `AVAILABLE_CONSTANTS` in `AutomationLoader.py`.

For example:

```python
AVAILABLE_CONSTANTS = {
    "Text Creation utility": ("constants.TextCreatorConstants", 1000),
    "Web Crawler utility": ("constants.WebCrawlerConstants", 1000),
    "Ubuntu ISO Editor utility": ("constants.UbuntuISOEditorConstants", 1000),
    "My Tool utility": ("constants.MyToolConstants", 1000),
}
```

The example illustrates the registration format. Preserve the other existing registrations when adding a tool.

---

## Design Principles

- Loader-driven architecture
- Configuration-first behaviour
- Reusable utility modules
- Explicit validation
- Structured execution pipelines
- Clear separation of responsibilities
- No tool-specific implementation inside the loader
- Safe execution and output handling
- Modular and extensible design

---

## Philosophy

The project favors:

- Explicit structure over magic
- Small, single-responsibility modules
- Deterministic execution
- Clear separation between loader and tool logic
- Configuration changes without unnecessary Python modifications

The goal is to provide a reusable automation framework where new tools can be introduced without rewriting the loader.
