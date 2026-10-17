
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
- **Router Configuration** — Decodes, extracts, edits and re-encodes router backups using JSON model specifications and configurable paths.

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
- `router_utils.py`
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
│   ├── UbuntuISOEditorConstants.py
│   └── RouterConstants.py
│
├── config/
│   ├── FunctionsConfig.json
│   ├── TextCreator.json
│   ├── WebCrawler.json
│   ├── UbuntuISOEditor.json
│   └── RouterConfig.json
│
├── config-sample/
│   ├── TextCreator.json
│   ├── WebCrawler.json
│   ├── UbuntuISOEditor.json
│   └── RouterConfig.json
│
├── doc/
│   ├── FunctionDoc.json
│   ├── TextCreatorDoc.json
│   ├── WebCrawlerDoc.json
│   ├── UbuntuISOEditorDoc.json
│   └── RouterDoc.json
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
│   ├── router_utils.py
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

Router Configuration:

```bash
python3 AutomationLoader.py --constants constants.RouterConstants
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
5. Start Ollama when required.
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

## Router Configuration

The Router Configuration utility automates decoding, inspecting, editing and re-encoding router configuration backups.

Router models are described using JSON specifications rather than separate Python implementations for each router model.

The Router utility uses configured paths for model specifications, original router templates, passwords, router details and generated output files.

### Features

- Load router model specifications.
- Validate router configuration and model requirements.
- View router model specification documentation.
- View router details and router details documentation.
- Decode encrypted router configuration backups.
- Save decoded configuration archives.
- Extract decoded router configuration files.
- View decoded configuration fields.
- Edit router configuration fields using router details.
- View edited configuration fields.
- Rebuild and encrypt router configuration backups.
- Validate generated encoded configurations.
- Run the complete decode, edit and encode workflow.

### Configuration

Configuration:

```text
config/RouterConfig.json
```

Constants:

```text
constants/RouterConstants.py
```

Documentation:

```text
doc/RouterDoc.json
```

Utility module:

```text
modules/router_utils.py
```

### Router Constants

The Router utility is configured by `constants/RouterConstants.py`.

The constants module defines the JSON configuration paths, required fields, dependencies, actions, execution steps and pipeline states.

#### Configuration Constants

```python
CONFIG_PATH = "config/RouterConfig.json"
TOOL_TYPE = "Router Configuration"
CONFIG_DOC = "doc/RouterDoc.json"
```

These constants identify the router configuration file, tool type and configuration documentation.

#### Router JSON Keys

The following constants identify fields used by the router configuration:

```python
MODEL_SPECS_PATH = "model_specs_path"
MODEL_SPECS_README_PATH = "model_specs_readme_path"
TEMPLATE_CONFIG_PATH = "template_config_path"
TEMPLATE_ROUTER_PASSWORD_PATH = "template_router_password_path"
TARGET_ROUTER_PASSWORD_PATH = "target_router_password_path"
ROUTER_DETAILS_PATH = "router_details_path"
ROUTER_DETAILS_README_PATH = "router_details_readme_path"
DECODED_CONFIG_PATH = "decoded_config_path"
DECODED_CONFIG_ARCHIVE_PATH = "decoded_config_archive_path"
EDITED_CONFIG_PATH = "edited_config_path"
ENCODED_CONFIG_PATH = "encoded_config_path"
```

| Configuration key | Purpose |
|---|---|
| `model_specs_path` | Router model JSON specification |
| `model_specs_readme_path` | Router model specification documentation |
| `template_config_path` | Original encrypted router backup |
| `template_router_password_path` | Password for decrypting the original template |
| `target_router_password_path` | Password used when encrypting the target backup |
| `router_details_path` | Router details used when editing configuration fields |
| `router_details_readme_path` | Documentation describing router details |
| `decoded_config_path` | Extracted decoded configuration directory |
| `decoded_config_archive_path` | Saved decoded configuration archive |
| `edited_config_path` | Edited configuration directory |
| `encoded_config_path` | Final encrypted router configuration backup |

All these paths are configurable through `RouterConfig.json`.

The router processing functions use the configured paths rather than hardcoded router-specific directories.

#### Validation Constants

`VALIDATION_CONFIG` requires all router path fields to be strings.

```python
VALIDATION_CONFIG = {
    "required_job_fields": {
        MODEL_SPECS_PATH: str,
        MODEL_SPECS_README_PATH: str,
        TEMPLATE_CONFIG_PATH: str,
        TEMPLATE_ROUTER_PASSWORD_PATH: str,
        TARGET_ROUTER_PASSWORD_PATH: str,
        ROUTER_DETAILS_PATH: str,
        ROUTER_DETAILS_README_PATH: str,
        DECODED_CONFIG_PATH: str,
        DECODED_CONFIG_ARCHIVE_PATH: str,
        EDITED_CONFIG_PATH: str,
        ENCODED_CONFIG_PATH: str,
    },
}
```

Secondary validation is currently empty:

```python
SECONDARY_VALIDATION = {}
```

Additional runtime validation is performed by the router utility functions.

#### User Requirements

```python
REQUIRED_USER = "standard"
```

The Router utility is configured for standard-user execution.

#### Dependencies

```python
DEPENDENCIES = ["openssl"]
```

OpenSSL is required for supported router encryption and decryption operations.

#### Plan Configuration

```python
PLAN_COLUMN_ORDER = [
    TEMPLATE_CONFIG_PATH,
    ROUTER_DETAILS_PATH,
    ENCODED_CONFIG_PATH,
]

OPTIONAL_PLAN_COLUMNS = {}
```

The plan identifies the original router template, router details and final encoded configuration path.

### Router Actions

The `ACTIONS` constant defines the operations available through the loader.

| Action | Execution state |
|---|---|
| Validate Router Configuration | `VALIDATE_CONFIG` |
| View Router Model Specifications | `VIEW_MODEL_SPECS` |
| View Router Details | `VIEW_ROUTER_DETAILS` |
| View Router Details Help | `VIEW_ROUTER_DETAILS_HELP` |
| Decode Router Configuration | `DECODE_CONFIG` |
| View Decoded Router Configuration | `VIEW_DECODED_CONFIG` |
| Edit Router Configuration | `EDIT_CONFIG` |
| View Edited Router Configuration | `VIEW_EDITED_CONFIG` |
| Encode Router Configuration | `ENCODE_CONFIG` |
| Run All Steps | `RUN_ALL` |
| Show Config Help | `SHOW_CONFIG_DOC` |
| Cancel | `FINALIZE` |

Actions are connected to pipeline states through their `execute_state` values.

Read-only actions generally skip the loader's execution confirmation.

Decode, edit, encode and Run All actions retain their configured loader confirmation behaviour.

This is separate from automatic overwriting of generated output files.

### Router Execution Steps

The Router constants module defines reusable pipeline step groups.

#### Preparation

`LOAD_MODEL_SPECS_PRE`

Loads the router model specification using `load_router_model_specs()`.

The loaded specification is stored in the pipeline context as `model_specs`.

#### Validation

`VALIDATE_CONFIG_EXEC`

Uses `validate_router_configuration()` to validate the selected router configuration against its model specification.

#### Documentation and Viewing

- `VIEW_MODEL_SPECS_EXEC` — Displays model specification documentation.
- `VIEW_ROUTER_DETAILS_EXEC` — Displays configured router details.
- `VIEW_ROUTER_DETAILS_HELP_EXEC` — Displays router details documentation.
- `VIEW_DECODED_CONFIG_EXEC` — Displays decoded configuration fields.
- `VIEW_EDITED_CONFIG_EXEC` — Displays edited configuration fields.
- `SHOW_CONFIG_DOC_EXEC` — Displays the Router configuration documentation.

#### Decoding

`DECODE_CONFIG_EXEC` performs three operations:

1. `decode_router_config()` — Decrypts the original router configuration.
2. `save_router_config()` — Saves the decoded configuration archive.
3. `extract_router_config()` — Extracts the decoded archive into the configured output directory.

The pipeline uses results from earlier steps to determine whether subsequent steps can execute.

#### Editing

`EDIT_CONFIG_EXEC`

Calls `edit_router_config_fields()` using the decoded configuration directory, edited configuration directory, model specification and router details.

The edited configuration is saved to the configured output directory.

#### Encoding

`ENCODE_CONFIG_EXEC`

Calls `encode_router_config()` using:

- Edited configuration path
- Original template configuration path
- Encoded configuration output path
- Router model specification
- Template router password path
- Target router password path

The function rebuilds and encrypts the router backup for the target configuration.

### Router Pipeline States

`PIPELINE_STATES` connects the preparation and execution steps into actions.

The configured pipeline states are:

```text
VALIDATE_CONFIG
VIEW_MODEL_SPECS
VIEW_DECODED_CONFIG
VIEW_EDITED_CONFIG
VIEW_ROUTER_DETAILS
VIEW_ROUTER_DETAILS_HELP
DECODE_CONFIG
EDIT_CONFIG
ENCODE_CONFIG
RUN_ALL
SHOW_CONFIG_DOC
```

Most router operations load the model specification before executing their corresponding action.

The `RUN_ALL` pipeline executes:

```text
Load Model Specifications
          |
          v
Validate Router Configuration
          |
          v
Decode Router Configuration
          |
          v
Save Decoded Archive
          |
          v
Extract Decoded Configuration
          |
          v
View Decoded Configuration
          |
          v
Edit Router Configuration
          |
          v
View Edited Configuration
          |
          v
Encode Router Configuration
```

The `RUN_ALL` pipeline uses the following step groups:

```python
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
    "success_key": "encoded_config",
}
```

The loader manages pipeline execution and result tracking.

Router-specific processing remains in `modules/router_utils.py`.

### Router Workflow

The Router utility can execute individual operations or run the complete processing sequence.

A typical workflow is:

1. Load the selected router model specification.
2. Validate the router configuration and configured paths.
3. Decode the original encrypted router backup.
4. Save the decoded archive.
5. Extract the decoded configuration.
6. View decoded configuration fields.
7. Apply the configured router details to the decoded configuration.
8. Save the edited configuration.
9. View edited configuration fields.
10. Rebuild and encrypt the router configuration.
11. Verify and save the encoded backup.

The router model specification determines the supported encryption, archive and configuration formats.

The original router backup is used as an input template and should remain unchanged.

### Automatic Output Overwrite

The Router automation is intended to recreate generated output files and directories on repeated runs.

After the automatic-overwrite change is applied to `modules/router_utils.py`, the expected behaviour is:

- If a generated output does not exist, create it.
- If a generated output already exists, automatically replace it.
- Do not prompt for overwrite confirmation.
- Do not skip processing solely because a generated output exists.
- Preserve the original encrypted template and other input files.

The following functions handle generated router outputs:

| Function | Generated output |
|---|---|
| `save_router_config()` | Decoded configuration archive |
| `extract_router_config()` | Extracted decoded directory |
| `edit_router_config_fields()` | Edited configuration directory |
| `encode_router_config()` | Encoded router backup |

Replacing existing directories should not leave stale files from previous runs.

The automatic overwrite behaviour applies only to generated output destinations, not to original router templates, password files, model specifications or router details.

The loader's existing action confirmation settings are independent of output overwrite handling.

### Router Model Support

Router processing is driven by JSON model specifications.

Model specifications can define:

- Router model and firmware metadata
- Encryption algorithm
- Encrypted payload format
- Password requirements
- Salt and key derivation
- Headers and trailers
- Checksums
- Archive format
- Compression
- Configuration file format
- Editable configuration fields

If another router uses mechanisms already supported by `router_utils.py`, it can be configured using another model specification.

Unsupported encryption or archive mechanisms may require additional reusable utility functionality.

### Router Backup Safety

Router backups may contain sensitive configuration data and credentials.

Recommended precautions:

- Keep original router backups unchanged.
- Store generated outputs separately from original templates.
- Keep router passwords and private backups out of public repositories.
- Retain recovery copies of important router configurations.
- Verify generated backups before restoring them to physical routers.
- Match router hardware and firmware compatibility requirements.
- Ensure configured output paths do not overlap input paths.

A successful local encryption and decryption test does not guarantee that a physical router will accept a generated backup.

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
