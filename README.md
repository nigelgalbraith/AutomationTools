# Automation Tools Loader

A modular, configuration-driven automation framework built around a single execution loader.

This project provides a structured way to build and run small automation tools using:

- A centralized loader
- Tool-specific constants modules
- JSON configuration files
- Structured pipeline states
- Explicit validation rules


---

## Overview

`AutomationLoader.py` is the execution entry point.

Each automation tool is defined through a **constants module** that specifies:

- Required dependencies
- Configuration file paths
- Validation rules
- Available actions
- Pipeline execution states

The loader dynamically builds a menu from registered tools and executes selected actions through a structured pipeline.

---

## Architecture

### 1. Loader

**AutomationLoader.py**

Responsible for:

- Loading constants modules
- Verifying dependencies
- Loading configuration JSON
- Validating configuration structure
- Displaying config documentation
- Building action menus
- Executing pipeline states

The loader itself contains no tool-specific logic.

---

### 2. Constants Modules

Located in:

```
constants/
```

Each tool defines:

- `CONFIG_PATH`
- `CONFIG_DOC`
- `VALIDATION_CONFIG`
- `ACTIONS`
- `PIPELINE_STATES`
- Optional dependency lists

These modules define behavior declaratively.

---

### 3. Configuration

Located in:

```
config/
```

Each tool has a corresponding JSON configuration file.

Configuration is grouped by profile name:

```json
{
  "Group-A": {
    "base_url": "...",
    "model": "...",
    ...
  }
}
```

Each group represents a runnable configuration profile.

---

### 4. Documentation

Located in:

```
doc/
```

Each tool has a JSON documentation file containing:

- `EXAMPLE`
- `DESCRIPTION`

This allows the loader to display structured help directly from config metadata.

---

### 5. Pipeline Execution Model

Each tool defines:

```python
PIPELINE_STATES = {
  "action_name": [
    {
      "pre": callable,
      "exec": callable,
      "post": callable
    }
  ]
}
```

Each state supports:

- `pre` phase
- `exec` phase
- `post` phase

Execution is deterministic and ordered.

---

## Directory Structure

```
AutomationTools/
│
├── AutomationLoader.py
├── README.md
│
├── constants/
│   └── TextCreatorConstants.py
│
├── config/
│   └── TextCreator.json
│
├── doc/
│   └── TextCreator.json
│
└── (tool-specific folders)
```

---

## Installation

### Requirements

- Python 3.10+
- Required packages defined per tool in constants module

### Setup

Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
```

Install dependencies:

```bash
pip install -r requirements.txt
```

(If no requirements file exists, install dependencies listed in the relevant constants module.)

---

## Running the Loader

From the project root:

```bash
python AutomationLoader.py
```

You will be presented with:

1. Tool selection
2. Action selection
3. Configuration group selection

Execution then proceeds through the defined pipeline states.

---

## Configuration System

Each tool defines:

```python
CONFIG_PATH = "config/ToolName.json"
CONFIG_DOC  = "doc/ToolName.json"
```

### Validation

Validation rules are defined in:

```python
VALIDATION_CONFIG = {
  "required_keys": {...},
  "types": {...}
}
```

Validation ensures:

- Required keys exist
- Correct data types
- Structural integrity

The loader stops execution if validation fails.

---

## Adding a New Tool

To add a new automation tool:

### 1. Create Constants Module

```
constants/MyTool.py
```

Define:

- `CONFIG_PATH`
- `CONFIG_DOC`
- `VALIDATION_CONFIG`
- `ACTIONS`
- `PIPELINE_STATES`

---

### 2. Create Config File

```
config/MyTool.json
```

Define configuration groups.

---

### 3. Create Documentation File

```
doc/MyTool.json
```

Include:

- `EXAMPLE`
- `DESCRIPTION`

---

### 4. Register Tool

Add to `AVAILABLE_CONSTANTS` in `AutomationLoader.py`:

```python
AVAILABLE_CONSTANTS = {
  "TextCreatorConstants": "constants.TextCreatorConstants",
  "MyTool": "constants.MyTool"
}
```

---

## Design Principles

- Loader-driven architecture
- Configuration-first behavior
- Strict validation
- State-based execution pipeline
- No hardcoded tool logic inside the loader
- Modular and extensible

---

## Current Tool

### TextCreatorConstants

A TextCreator automation tool that:

- Scrapes html listings
- Extracts structured links data
- Generates prompts
- Produces tailored Text using an LLM backend

All behavior is defined through configuration and constants modules.

---

## Philosophy

This project favors:

- Explicit structure over magic
- Small, single-responsibility modules
- Deterministic execution
- Clear separation between loader and tool logic
