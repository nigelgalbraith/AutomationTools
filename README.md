
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

The shared `modules/json_utils.py` provides `load_json()` for one file path or an ordered list of file paths, and `validate_json_schema()` for one configuration dictionary or a list of dictionaries. Validation rules come from external JSON Schema files whose paths are passed explicitly by constants. The validator checks the schema, applies the same schema to each supplied configuration, and returns the original data unchanged on success. Configured PRE steps retain loaded and validated configurations in the execution context for later use without unnecessary reloading or schema validation.

`load_json()` propagates file errors and includes the file path in JSON and text decoding errors. Schema validation prints `[OK] <label> schema validated successfully.` by default. Invalid schemas or configurations print `[FAILED] <label>: ...` and raise `ValueError`; configuration errors identify property paths such as `$.field` or `$[0].field`. Validation stops at the first invalid configuration, reporting its schema errors. The pipeline records an already reported validation error without printing it again.

AutomationTools additionally requires each JSON file loaded by `load_json()` to contain an object at its root and raises `TypeError` otherwise.

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

PRE stops at the first exception. The loader records the failing step and error, reports missing files clearly, and returns to the menu when PRE fails instead of proceeding to execution. Exceptions from conditions and argument resolution are handled as step failures too. A truthy `success_key` cannot override recorded errors: success requires no recorded errors and, when present, a truthy success result. EXEC records exceptions and continues with later eligible steps; it does not apply PRE's stop-on-exception behaviour.

AutomationTools retains its callback convention: a `None` return stored under a result key becomes `True`; TestingTools stores the returned value directly. Both loaders prevent PRE failures from reaching execution.

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

The Router Configuration utility automates decoding, viewing, editing, encoding, and verification of supported router configuration backups.

Each router job uses a model specification, an original configuration backup, and a router details file containing replacement values.

AutomationTools processes configured files without interactive editing or credential prompts.

### Features

- Validate router model specifications and configuration paths.
- Display selected router processing operations.
- View router specifications and router details.
- Decode and extract supported router backups.
- View key-value and XML configuration settings.
- Edit supported configuration fields using JSON-defined replacement values.
- View edited settings.
- Encode and verify generated router backups.
- Safely replace generated files and directories.
- Execute the full router workflow using Run All.

### Files and Directories

| File | Purpose |
|---|---|
| `constants/RouterConstants.py` | Router actions, function registry, validation, and pipelines |
| `modules/router_utils.py` | Operation builders, dispatcher, validation, credential handling, and file operations |
| `modules/router_encryption_utils.py` | Encryption, decryption, signatures, and checksums |
| `modules/router_format_utils.py` | Wrappers, encoding, compression, and archive processing |
| `modules/router_config_utils.py` | Configuration viewing, editing, and validation |
| `schemas/RouterSchema.json` | Router model specification schema |
| `config/RouterConfig.json` | Router jobs and configured paths |
| `config-sample/RouterConfig.json` | Example configuration |
| `doc/RouterDoc.json` | Router configuration help |
| `doc/RouterSpecificationTemplate.json` | Router specification template |
| `routers/model_specs/` | Router model specifications |
| `routers/model_specs/ModelSpecsReadMe.md` | Router specification documentation |
| `routers/details/RouterDetailsReadMe.md` | Router details documentation |

### Dependencies

The Router utility declares:

- `openssl`
- `python3-cryptography`
- `python3-jsonschema`

The selected model specification determines which registered mechanisms are used.

### Running the Router Utility

Start AutomationLoader:

```bash
python3 AutomationLoader.py
```

Select **Router Configuration** from the available tools.

Alternatively, launch it directly:

```bash
python3 AutomationLoader.py --constants constants.RouterConstants
```

### Available Actions

| Action | Description |
|---|---|
| Validate Router Configuration | Validate the selected router job and display its operations |
| View Router Model Specifications | Display router model specifications |
| View Router Details | Display configured replacement values |
| View Router Details Help | Display router details documentation |
| Decode Router Configuration | Decode and extract a router backup |
| View Decoded Router Configuration | Display original configuration fields |
| Edit Router Configuration | Apply replacement values |
| View Edited Router Configuration | Display updated fields |
| Encode Router Configuration | Encode and verify the edited backup |
| Run All Steps | Execute the complete configured workflow |
| Show Config Help | Display configuration documentation |
| Cancel | Exit the utility |

The utility can process a selected router group or multiple configured groups, depending on the action.

### Router Architecture

Router processing separates pipeline orchestration from individual processing functions.

`constants/RouterConstants.py` defines the declarative pipelines and `ROUTER_FUNCTIONS` registry.

The registry contains functions for:

- Encoding and decoding.
- Encode and decode validation.
- Configuration extraction.
- Format checking.
- Checksums.
- Configuration editing and validation.
- Configuration viewing and validation.

`modules/router_utils.py` contains the operation resolver, builders, and dispatcher:

```python
resolve_router_operations()
build_encode_operations()
build_decode_operations()
build_edit_operations()
build_view_operations()
run_router_operations()
```

`resolve_router_operations()` selects registered functions from the model specification.

The builders arrange the applicable validators and processing operations in the required order.

`run_router_operations()` executes the ordered transformations and passes returned results between them.

The pipelines control the workflow by calling individual functions and passing results through the execution context.

Processing implementations are organised by responsibility:

- `router_encryption_utils.py` — Cryptography, signatures, and checksums.
- `router_format_utils.py` — Backup formats, wrappers, encoding, compression, and archives.
- `router_config_utils.py` — Configuration parsing, viewing, editing, and validation.
- `router_utils.py` — Router preparation, operation building, execution, and safe output handling.

The model specifications select reusable processing mechanisms rather than manufacturer-specific scripts.

### Router Configuration File

Router jobs are defined in:

```text
config/RouterConfig.json
```

Each top-level group represents a configured router job.

Example:

```json
{
  "router_one": {
    "model_specs_path": "routers/model_specs/Spark_SmartModem_VRV9517-spec.json",
    "model_specs_readme_path": "routers/model_specs/ModelSpecsReadMe.md",
    "template_config_path": "~/Documents/AutomationToolsData/routers/templates/router_one.cfg",
    "template_router_password_path": "~/Documents/AutomationToolsData/routers/templatePasswords/router_one_password.txt",
    "target_router_password_path": "~/Documents/AutomationToolsData/routers/targetPasswords/router_one_password.txt",
    "router_details_path": "~/Documents/AutomationToolsData/routers/details/router_one_details.json",
    "router_details_readme_path": "routers/details/RouterDetailsReadMe.md",
    "decoded_config_archive_path": "~/Documents/AutomationToolsData/routers/decoded/router_one_decoded.tar.gz",
    "decoded_config_path": "~/Documents/AutomationToolsData/routers/decoded/router_one_decoded",
    "edited_config_path": "~/Documents/AutomationToolsData/routers/edited/router_one_edited",
    "encoded_config_path": "~/Documents/AutomationToolsData/routers/encoded/router_one_encoded.cfg"
  }
}
```

Additional router jobs use separate groups with their own paths and replacement values.

### Router Configuration Keys

| Key | Description |
|---|---|
| `model_specs_path` | Router model specification JSON |
| `model_specs_readme_path` | Router specification documentation |
| `template_config_path` | Original encrypted router backup |
| `template_router_password_path` | Template password file, when required |
| `target_router_password_path` | Target password file, when required |
| `template_device_key_path` | Template device-key file, when required |
| `target_device_key_path` | Target device-key file, when required |
| `router_details_path` | Replacement settings JSON |
| `router_details_readme_path` | Router details documentation |
| `decoded_config_archive_path` | Saved decoded payload |
| `decoded_config_path` | Extracted configuration directory |
| `edited_config_path` | Edited configuration directory |
| `encoded_config_path` | Final encoded router backup |

Paths may use `~` for the user's home directory.

Password and device-key requirements are determined by the model specification.

### Supported Router Models

| Router | Model | Backup Format | Configuration Format |
|---|---|---|---|
| Spark SmartModem | VRV9517 | Legacy OpenSSL AES-256-CBC, Base64, TAR/GZIP | Key-value |
| Vodafone Ultra Hub | DGA0130VDF | Technicolor THENC | Not established |
| Vodafone Huawei HG659 | HG659 | Fixed-key AES-256-CBC, signed zlib | XML |

**Spark SmartModem VRV9517**

Supports backup decoding, archive extraction, key-value viewing and editing, encoding, and local verification.

**Vodafone Huawei HG659**

Supports fixed-key AES-256-CBC, RSA/MD5 signing and verification, XML configuration processing, and encryption of supported protected Wi-Fi password fields.

**Vodafone Ultra Hub DGA0130VDF**

The specification describes the THENC backup wrapper and device-key requirements.

THENC parsing and relevant validation are implemented. Complete THENC decryption, encryption, authentication, and signing are not established.

The configuration editing format is not established.

Compatibility depends on the router hardware and firmware revision.

### Router Model Specifications

The specification files are stored in:

```text
routers/model_specs/
```

AutomationTools and TestingTools use the same model specification structure and `schemas/RouterSchema.json`.

Each specification defines:

- Router model, hardware, and firmware.
- Backup codec settings.
- Encryption and key derivation.
- Wrappers, archives, signatures, and checksums.
- Encode and decode processing order.
- Encoding-only parameters where required.
- Configuration format and editing settings.
- Logical configuration field mappings.

The specification's `router_specs` object contains the required `model`, `firmware`, `hardware`, `codec`, `encode`, and `edit` properties.

Unused supported settings are represented by `null` where permitted by the schema.

See `routers/model_specs/ModelSpecsReadMe.md` for the complete explanation.

### Router Credentials

Credential paths are configured in `RouterConfig.json`.

The model specification declares whether a password or binary device key is required.

The supported mechanisms include password-derived encryption, fixed-key encryption, and device-specific key requirements.

Required credentials must be available for the corresponding operation.

Password files and private router backups should not be committed to public repositories.

### Router Details

The router details JSON file contains the replacement configuration values.

For example:

```json
{
  "wifi_2g_ssid": "RouterTwo_2G",
  "wifi_2g_password": "example-password-123",
  "wifi_5g_ssid": "RouterTwo_5G",
  "wifi_5g_password": "example-password-456"
}
```

Each key must correspond to a supported logical field in the router specification's `config_fields` array.

The actual configuration key or XML selector is defined in the model specification, not in the router details file.

Only mapped and supported fields can be modified.

Protected fields are processed using the registered field encryption and decryption functions where applicable.

See `routers/details/RouterDetailsReadMe.md` for details.

### Router Workflow

#### 1. Validate

The utility loads the router model specification and validates it against `schemas/RouterSchema.json`.

It also validates configuration mappings, paths, and applicable router inputs.

Validation displays the selected Encode, Decode, Edit, and View operation lists.

#### 2. Decode

The utility:

1. Loads the model specification.
2. Builds the selected decoding operations.
3. Reads the original router backup and required credentials.
4. Validates and decodes the backup.
5. Saves the decoded payload.
6. Extracts the configuration where the format supports extraction.

#### 3. View Decoded Configuration

The utility reads the supported configuration file and displays the mapped fields.

Protected fields may be decrypted for viewing when the required mechanism is supported.

#### 4. Edit

The utility loads the router details JSON and compares the requested replacements against the decoded configuration.

Supported fields are updated using the selected configuration editor.

Protected replacement values are encrypted where required.

The edited configuration is saved to the configured output.

#### 5. View Edited Configuration

The utility reads the edited configuration and displays the supported mapped fields.

This allows the configured replacements to be checked before encoding.

#### 6. Encode

The utility:

1. Loads and validates the model specification.
2. Builds the selected encoding operations.
3. Reads the edited configuration and required credentials.
4. Reconstructs the required payload format.
5. Applies encryption, encoding, wrappers, and signing where specified.
6. Verifies the generated backup where supported.
7. Saves the final encoded output.

### Run All Steps

**Run All Steps** executes the configured router workflow in pipeline order.

The pipeline coordinates validation, decoding, viewing, editing, encoding, and output handling.

Each step returns its result for use by subsequent steps.

Failures are recorded, and the reported pipeline outcome reflects failed steps.

### Output Handling

AutomationTools writes generated files and directories to the configured destinations.

Existing generated outputs may be replaced automatically.

The save operations use staged output handling and rollback where applicable to avoid leaving partially written results.

Original router backups should be preserved separately.

A locally verified backup is not guaranteed to be accepted by physical router firmware.

### Adding Another Router Model

1. Start with `doc/RouterSpecificationTemplate.json`.
2. Set the router model, firmware, hardware, and codec parameters.
3. Set the encode and decode processing order.
4. Define supported configuration editing settings.
5. Map the supported configuration fields.
6. Validate the specification against `schemas/RouterSchema.json`.
7. Add a corresponding group to `config/RouterConfig.json`.
8. Configure the input, output, and credential paths.
9. Test the required decoding, editing, encoding, and verification operations.

A router using existing registered algorithms generally needs only a new specification and configuration entry.

A new algorithm or backup format requires a reusable implementation in the appropriate utility module and registration in `ROUTER_FUNCTIONS`.

### Important Notes

- Use backups from the correct router hardware and firmware revision.
- Keep original router backups unchanged.
- Keep credential files private.
- Edit only supported mapped fields.
- Verify generated configurations before using them.
- Physical-router restore compatibility requires separate testing.

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
