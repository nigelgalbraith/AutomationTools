
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

The Router Configuration utility automates decoding, viewing, editing, and re-encoding encrypted router configuration backups.

Router processing uses a modular, JSON-driven architecture. The main router utility coordinates operations through centralised dispatchers, while specialised utility modules implement reusable processing functions.

Each router job uses an original router configuration as a template, applies replacement settings from a router details JSON file, and generates an encrypted configuration for the target router.

AutomationTools uses file-driven configuration processing. Router settings and passwords are read from configured files without interactive editing or password prompts.

### Features

- Validate router configuration files and model specifications.
- View router model specifications and documentation.
- View router details and available configuration settings.
- Decode encrypted router configuration backups.
- Save and extract decoded configuration archives or XML files.
- View original key-value and XML configuration fields.
- Decrypt and display protected Wi-Fi passwords.
- Edit router settings using JSON-defined replacement values.
- Encrypt modified configuration fields when required.
- View edited router configuration values.
- Rebuild and encrypt router configuration backups.
- Generate and verify supported RSA signatures.
- Verify generated configurations through local decoding round trips.
- Automatically replace existing generated outputs.
- Run the complete decode, edit, and encode workflow.

### Files and Directories

| File | Purpose |
|---|---|
| `constants/RouterConstants.py` | Router actions, validation, dependencies, and pipelines |
| `schemas/RouterSchema.json` | Shared router model specification validation rules |
| `config/RouterConfig.json` | Router configuration groups and file paths |
| `config-sample/RouterConfig.json` | Example router configuration |
| `doc/RouterDoc.json` | Configuration documentation |
| `modules/router_utils.py` | Main router workflows, validation, orchestration, and centralised handler registrations |
| `modules/router_encryption_utils.py` | Encryption, decryption, field encryption, checksums, and RSA signatures |
| `modules/router_format_utils.py` | Backup wrappers, encoding, decoding, compression, and archive processing |
| `modules/router_config_utils.py` | Configuration field extraction, viewing, editing, and validation |
| `routers/model_specs/` | Router model specifications and the common specification template |
| `routers/model_specs/ModelSpecsReadMe.md` | Model specification documentation |
| `routers/details/RouterDetailsReadMe.md` | Router details documentation |

### Dependencies

The Router utility uses:

- `openssl` — OpenSSL-based router backup encryption and decryption.
- `python3-cryptography` — AES encryption and decryption through Python's cryptography library.
- `python3-jsonschema` — shared validation against external JSON Schema files.

Dependencies are declared in `constants/RouterConstants.py`.

The selected router model specification determines which supported processing mechanisms are used.

### Running the Router Utility

Run AutomationLoader and select **Router Configuration** from the available tools.

```bash
python3 AutomationLoader.py
```

Alternatively, launch the Router Configuration utility directly:

```bash
python3 AutomationLoader.py --constants constants.RouterConstants
```

The loader displays the available router actions and configuration groups.

### Available Actions

| Action | Description |
|---|---|
| Validate Router Configuration | Validate the selected router configuration |
| View Router Model Specifications | Display router model specifications |
| View Router Details | Display configured replacement values |
| View Router Details Help | Display router details documentation |
| Decode Router Configuration | Decrypt, save, and extract a router backup |
| View Decoded Router Configuration | Display original configuration values |
| Edit Router Configuration | Apply replacement settings from JSON |
| View Edited Router Configuration | Display updated configuration values |
| Encode Router Configuration | Rebuild, encrypt, and verify the backup |
| Run All Steps | Execute the complete router workflow |
| Show Config Help | Display configuration documentation |
| Cancel | Exit the router utility |

### Router Architecture

The router utility separates workflow orchestration from processing implementations.

**`router_utils.py`** manages:

- Router workflow execution.
- Router input and output validation for automation.
- Centralised processing dispatcher registrations.
- Selection of processing mechanisms.
- Coordination of decoding, viewing, editing, and encoding.
- Configuration input and output handling.

All processing handler registrations are grouped near the top of `router_utils.py`:

```python
ENCRYPTION_HANDLERS
FIELD_ENCRYPT_HANDLERS
FIELD_DECRYPT_HANDLERS
CONFIG_VIEW_HANDLERS
CONFIG_EDIT_HANDLERS
```

Processing implementations are separated into specialised modules:

- `router_encryption_utils.py` — cryptographic algorithms, field encryption, and signature processing.
- `router_format_utils.py` — backup wrappers, compression, encoding, decoding, and archive reconstruction.
- `router_config_utils.py` — configuration field parsing, viewing, editing, and validation.

Dispatchers select reusable functions using values from the router model specification rather than router manufacturer or model names.

If a new router uses an existing mechanism, the existing processing function is reused.

If a new mechanism is required, a generic processing function is implemented in the appropriate utility module and registered in `router_utils.py`.

The main router workflow does not require manufacturer-specific processing implementations.

### Router Configuration

Router jobs are defined in:

```text
config/RouterConfig.json
```

Each configuration group represents a separate router job.

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

Additional router jobs can be created by adding configuration groups with their own model specifications, router details, and file paths.

Password paths are used only when required by the selected encryption mechanism.

For routers using fixed firmware encryption keys, the encryption parameters are stored in the router model specification rather than separate password files.

#### Configuration Fields

| Field | Description |
|---|---|
| `model_specs_path` | Router model specification JSON |
| `model_specs_readme_path` | Model specification documentation |
| `template_config_path` | Original encrypted router backup |
| `template_router_password_path` | Template router password file, when required |
| `target_router_password_path` | Target router password file, when required |
| `router_details_path` | JSON file containing replacement settings |
| `router_details_readme_path` | Router details documentation |
| `decoded_config_archive_path` | Decoded configuration archive or XML output |
| `decoded_config_path` | Extracted decoded configuration directory |
| `edited_config_path` | Edited configuration directory |
| `encoded_config_path` | Final encrypted router backup |

Paths support `~` for the user's home directory.

Relative paths are resolved from the AutomationLoader working directory.

### Configured Router Models

The supplied project includes specifications for:

| Router | Model | Configuration Format | Encryption |
|---|---|---|---|
| Spark SmartModem | VRV9517 | Key-value | AES-256-CBC with OpenSSL legacy key derivation |
| Vodafone Ultra Hub | DGA0130VDF | Technicolor THENC | AES-256-CBC with device-specific key |
| Vodafone Huawei HG659 | HG659 B020 | XML | AES-256-CBC with fixed firmware key |

#### Spark SmartModem

Supports:

- Backup decoding and extraction.
- Key-value configuration viewing.
- JSON-driven Wi-Fi configuration editing.
- Backup encryption and encoding.
- Local decoding and encoding verification.

#### Vodafone Ultra Hub

Uses the Technicolor THENC encrypted backup format.

Complete authenticated decryption and encoding require device-specific cryptographic material and signing support.

These operations remain unavailable until the required device key and cryptographic mechanisms are established.

#### Vodafone Huawei HG659

Supports:

- Fixed-key AES-256-CBC backup encryption and decryption.
- zlib compression and decompression.
- RSA/MD5 signature verification and signing.
- XML configuration extraction.
- XML configuration viewing and editing.
- AES-128-CBC encryption and decryption of protected Wi-Fi passwords.
- Signed backup reconstruction.
- Local decoding and encoding round-trip verification.

Router compatibility depends on the hardware and firmware revision.

### Router Model Specifications

Router model specifications are stored in:

```text
routers/model_specs/
```

Each specification uses the shared JSON schema defined in:

```text
schemas/RouterSchema.json
```

Specifications contain two top-level sections:

- `router_specs` — Router identity and supported processing mechanisms.
- `config_fields` — Logical field names mapped to actual configuration keys or selectors.

The `router_specs` section contains model, hardware, and firmware information, together with:

- `codec` — Shared decoding and encoding settings, including encryption, wrappers, checksums, compression, and archive formats.
- `encode` — Additional encoding settings, only when required.
- `edit` — Configuration editing settings, only when supported.

Unused optional settings and sections are omitted rather than represented by JSON `null`.

The `config_fields` section contains a list of mappings:

```json
{
  "name": "logical_field_name",
  "path": "actual_key_or_selector"
}
```

New field mappings can be added without modifying Python processing functions or other router model specifications.

Router configuration preparation follows **LOAD → CHECK → PLAN → EXECUTE**.

`load_router_model_specs()` loads the specification, and the PRE pipeline validates it against the external schema before preparing any required XML selectors. Additional implementation-specific parameter checks are performed in Python.

Processing functions are selected through registered handlers using the mechanisms defined in the specification rather than router manufacturer or model names.

Firmware-wide encryption and signing parameters are stored directly in the model specification. Device-specific credentials, when required, remain separate.

For detailed information, see:

[Model Specifications Documentation](routers/model_specs/ModelSpecsReadMe.md)

### Router Password Handling

Router backup authentication depends on the selected encryption mechanism.

Supported approaches include:

- Password-based key derivation.
- Device-specific encryption keys.
- Firmware-wide fixed encryption keys.

For password-based configurations, two password paths may be configured:

- `template_router_password_path` — Password used to decrypt the original router backup.
- `target_router_password_path` — Password used to encrypt the generated backup.

These passwords may be different.

Each required password file contains the corresponding password.

AutomationTools reads these files automatically. No interactive password entry is required.

Routers using fixed firmware-wide keys, such as the Huawei HG659, obtain their encryption parameters from the router model specification.

Some routers also encrypt individual configuration values.

For example, the Huawei HG659 stores Wi-Fi passwords as protected AES-128-CBC values inside its decoded XML configuration.

The registered field-decryption handler converts these values into readable passwords for viewing.

The registered field-encryption handler encrypts replacement passwords before they are written into the configuration.

Actual passwords, device-specific credentials, and router backups must be kept private.

### Router Details

Router details define which settings will be changed in the decoded router configuration.

Each router job references a JSON file through:

```text
router_details_path
```

Example:

```json
{
  "wifi_2g_ssid": "RouterOne_2G",
  "wifi_2g_password": "example-password-123",
  "wifi_5g_ssid": "RouterOne_5G",
  "wifi_5g_password": "example-password-456"
}
```

The field names must correspond to entries in the model specification's `config_fields`.

The router details file contains the replacement values. The model specification defines where those values are located in the router configuration.

#### Key-Value Configuration Example

```json
"config_fields": {
  "file": "config/.glbcfg",
  "wifi_2g_ssid": "ARC_WLAN_24G_SSID_0_ESSID",
  "wifi_2g_password": "ARC_WLAN_24G_SSID_0_WPA_Passphrase",
  "wifi_5g_ssid": "ARC_WLAN_5G_SSID_0_ESSID",
  "wifi_5g_password": "ARC_WLAN_5G_SSID_0_WPA_Passphrase"
}
```

#### XML Configuration Example

```json
"config_fields": {
  "file": "config.xml",
  "wifi_2g_ssid": "WLANConfigurationInstance|X_OperatingFrequencyBand=2.4GHz|X_Is_Guest_Network=0|SSID",
  "wifi_2g_password": "WLANConfigurationInstance|X_OperatingFrequencyBand=2.4GHz|X_Is_Guest_Network=0|PreSharedKeyInstance@KeyPassphrase",
  "wifi_5g_ssid": "WLANConfigurationInstance|X_OperatingFrequencyBand=5GHz|X_Is_Guest_Network=0|SSID",
  "wifi_5g_password": "WLANConfigurationInstance|X_OperatingFrequencyBand=5GHz|X_Is_Guest_Network=0|PreSharedKeyInstance@KeyPassphrase"
}
```

XML selectors identify the intended elements and attributes, including parent-child relationships.

The selectors distinguish primary Wi-Fi networks from guest networks.

Only settings included in the router details JSON are modified.

Settings not specified remain unchanged.

Unknown fields, invalid selectors, or missing configuration values cause an error.

The configuration editor uses the registered processing functions to update the correct fields while preserving unrelated configuration content.

Protected values are encrypted using the mechanism declared in the model specification.

Additional editable fields can be supported by defining their mappings when the field name and processing mechanism are already supported.

If a new field name is required, add it to the common schema, specification template, and every router specification, with `null` for unused values.

For detailed instructions, see:

[Router Details Documentation](routers/details/RouterDetailsReadMe.md)

### Router Workflow

The Router Configuration utility supports individual actions or the complete automated workflow.

#### 1. Validate

Load the selected router model specification.

The PRE pipeline checks the model specification against the external schema and prepares XML selectors. The separate `validate_router_configuration()` execution step checks automation input files, credentials, replacement settings, output paths, and the backup wrapper; it does not perform model schema validation.

#### 2. Decode

Read the original encrypted router backup.

Select the registered encryption handler using the model specification.

Decrypt and process the backup using its configured format.

Supported decoded formats include:

- TAR/GZIP configuration archives.
- Single-file XML configurations.

Apply signature and integrity verification where required.

Save the decoded output and extract its configuration files into the configured directory.

#### 3. View Decoded Configuration

Read the original configuration using its registered configuration viewer.

Supported formats include:

- Key-value configurations.
- XML configurations.

Read the fields defined in `config_fields`.

For protected fields, use the registered field-decryption handler to display their readable values.

#### 4. Edit

Load replacement settings from the router details JSON.

Create an edited copy of the decoded configuration.

Use the registered configuration editor to locate and update the selected fields.

For protected fields, encrypt replacement values using the registered field-encryption mechanism.

Preserve unrelated configuration data.

Unspecified settings remain unchanged.

All replacement values are supplied through files. No interactive editing or password prompts are used.

#### 5. View Edited Configuration

Read the modified configuration fields using the registered viewer.

Display the updated values for verification.

Protected fields are decrypted for display using the configured field-decryption mechanism.

#### 6. Encode

Rebuild the edited configuration using the selected router's backup format.

Apply the registered compression, signing, and encryption mechanisms as required.

Supported processing includes TAR/GZIP archive reconstruction and signed single-file configuration reconstruction.

Verify the generated backup by decoding it locally.

Confirm that the recovered configuration matches the intended edited configuration.

Write the encrypted backup to:

```text
encoded_config_path
```

### Run All Steps

The **Run All Steps** action executes the complete router processing pipeline.

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
Save Decoded Configuration
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
          |
          v
Complete
```

The pipeline uses the following execution state:

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

The loader manages execution order, conditions, and pipeline results.

Processing functions are selected through the registered dispatchers using the router model specification.

### Automatic Output Replacement

Generated router outputs are automatically replaced when an existing output is encountered.

This includes:

- Decoded configuration archives or XML files.
- Extracted decoded configuration directories.
- Edited configuration directories.
- Final encrypted router backups.

Directory replacement removes stale generated content.

The following input files are preserved:

- Original encrypted router templates.
- Router model specifications.
- Router password files, when applicable.
- Router details JSON files.

Output replacement does not require a separate overwrite prompt.

The loader's normal action confirmation is independent of output replacement.

### Adding Another Router Model

To add another router model:

1. Obtain an original configuration backup from the router.
2. Start with `doc/RouterSpecificationTemplate.json`.
3. Populate the router identity and required `router_specs.codec` parameters.
4. Add `router_specs.encode` only if additional encoding parameters are required.
5. Add `router_specs.edit` only if configuration editing is supported.
6. Define the required `config_fields` name/path mappings.
7. Omit unused optional settings and sections.
8. Create a router details JSON containing the replacement settings, where editing is supported.
9. Add a new configuration group to `config/RouterConfig.json`.
10. Configure the required input and output paths.
11. Configure password or device-key files only when required by the encryption mechanism.
12. Reuse existing registered processing functions.
13. If a required mechanism is unsupported, implement a reusable function in the appropriate specialised utility module and register it in `router_utils.py`.
14. Validate the specification and test decoding, viewing, editing, encoding, and local verification where supported.

Router models using existing processing mechanisms can be added through JSON specifications and configuration entries without changing the main router workflow.

All model specifications use the shared JSON schema, but optional sections and parameters depend on the selected router model.

Additional `config_fields` mappings do not require modifications to the schema, template, or other router model specifications.

### Requirements

- Python 3.10+.
- OpenSSL.
- Python cryptography library.
- Compatible router configuration backup.
- Valid router model specification.
- Router details JSON file.
- Template and target password files when required by the selected encryption mechanism.
- Device-specific encryption key when required by the selected router mechanism.

### Important Notes

- Keep an unchanged copy of the original router backup.
- Ensure the model specification matches the router's hardware and firmware.
- Do not use original input paths as generated output destinations.
- Keep actual passwords, device-specific credentials, and personal router configurations private.
- Firmware-wide cryptographic parameters are stored in the model specification.
- Router viewing actions may display passwords and other credentials in full.
- Configuration editing uses values from the router details JSON without interactive prompts.
- Verify replacement settings before restoring a generated backup.
- Unrelated router settings should remain unchanged during editing.
- Successful local decoding, signing, and encoding verification does not guarantee that a physical router will accept the generated backup.
- Test generated configurations carefully before deploying them to additional routers.

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
