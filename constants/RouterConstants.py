
# constants/RouterConstants.py
from __future__ import annotations

from typing import Any, Dict
from functools import partial

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
    validate_router_settings,
    encode_router_config,
    extract_configuration_file,

)

from modules.router_config_utils import (
    xml_field_values,
    view_key_value_values,
    edit_key_value_values,
    update_xml_fields,
    validate_key_value_settings, 
    validate_xml_field_settings,
)

from modules.router_encryption_utils import (
    decrypt_aes_128_cbc_field, 
    encrypt_aes_128_cbc_field,
    crypt_aes_256_cbc, 
    crypt_aes_256_cbc_fixed_key, 
    crypt_technicolor_thenc,
    calculate_payload_checksum, 
    verify_rsa_md5_signature, 
    sign_rsa_md5_configuration,
    validate_legacy_aes_settings, 
    validate_fixed_key_settings, 
    validate_device_key_settings,
    validate_rsa_md5_settings, 
    validate_rsa_md5_signing_settings, 
    validate_field_encryption_settings,
)

from modules.router_format_utils import (
    rebuild_tar_archive,
    read_tar_files,
    split_line_wrapper, 
    prepare_line_wrapper,
    parse_technicolor_wrapper, 
    parse_encrypted_configuration,
    rebuild_technicolor_wrapper,
    encode_base64_payload, 
    decode_base64_payload,
    unpack_signed_configuration, 
    pack_signed_configuration,
    encode_signed_xml_configuration, 
    decode_xml_configuration,
    validate_signed_configuration_settings, 
    validate_tar_configuration,
    validate_xml_declaration, 
    extract_tar_archive,
    validate_base64_settings, 
    validate_line_wrapper_settings, 
    validate_technicolor_settings,
)

ROUTER_FUNCTIONS = {
    "encode": {
        "functions": {
            "tar.gz": rebuild_tar_archive,
            "rsa-md5": partial(encode_signed_xml_configuration, 
                               signer=sign_rsa_md5_configuration),
            "signed-zlib": pack_signed_configuration,
            "aes-256-cbc": partial(crypt_aes_256_cbc, 
                                   decrypt=False),
            "fixed-key": partial(crypt_aes_256_cbc_fixed_key, 
                                 decrypt=False),
            "device-key": partial(crypt_technicolor_thenc, 
                                  decrypt=False),
            "openssl-legacy": partial(crypt_aes_256_cbc, 
                                      decrypt=False),
            "base64": encode_base64_payload,
            "line-wrapper": prepare_line_wrapper,
            "technicolor-thenc": rebuild_technicolor_wrapper,
            "encrypted-configuration": parse_encrypted_configuration,
            "aes-128-cbc-zero-padded-base64": encrypt_aes_128_cbc_field,
        },
        "validate": {
            "signed-zlib": validate_signed_configuration_settings,
            "aes-256-cbc": validate_legacy_aes_settings,
            "openssl-legacy": validate_legacy_aes_settings,
            "fixed-key": validate_fixed_key_settings,
            "device-key": validate_device_key_settings,
            "base64": validate_base64_settings,
            "line-wrapper": validate_line_wrapper_settings,
            "technicolor-thenc": validate_technicolor_settings,
            "aes-128-cbc-zero-padded-base64": validate_field_encryption_settings,
            "rsa-md5": validate_rsa_md5_signing_settings,
        },
    },
    "decode": {
        "functions": {
            "line-wrapper": split_line_wrapper,
            "technicolor-thenc": parse_technicolor_wrapper,
            "encrypted-configuration": parse_encrypted_configuration,
            "base64": decode_base64_payload,
            "aes-256-cbc": partial(crypt_aes_256_cbc, 
                                   decrypt=True),
            "fixed-key": partial(crypt_aes_256_cbc_fixed_key, 
                                 decrypt=True),
            "device-key": partial(crypt_technicolor_thenc, 
                                  decrypt=True),
            "openssl-legacy": partial(crypt_aes_256_cbc, 
                                      decrypt=True),
            "tar.gz": read_tar_files,
            "signed-zlib": unpack_signed_configuration,
            "rsa-md5": partial(decode_xml_configuration, 
                               verifier=verify_rsa_md5_signature),
            "aes-128-cbc-zero-padded-base64": decrypt_aes_128_cbc_field,
        },
        "validate": {
            "signed-zlib": validate_signed_configuration_settings,
            "aes-256-cbc": validate_legacy_aes_settings,
            "openssl-legacy": validate_legacy_aes_settings,
            "fixed-key": validate_fixed_key_settings,
            "device-key": validate_device_key_settings,
            "base64": validate_base64_settings,
            "line-wrapper": validate_line_wrapper_settings,
            "technicolor-thenc": validate_technicolor_settings,
            "aes-128-cbc-zero-padded-base64": validate_field_encryption_settings,
            "rsa-md5": validate_rsa_md5_settings,
        },
    },
    "extract": {
        "tar.gz": extract_tar_archive,
        "signed-zlib": extract_configuration_file,
    },
    "check": {
        "tar.gz": validate_tar_configuration,
        "signed-zlib": validate_xml_declaration,
    },
    "checksum": {
        "md5": calculate_payload_checksum,
        "sha256": calculate_payload_checksum,
        "sha512": calculate_payload_checksum,
    },
    "edit": {
        "functions": {
            "key-value": edit_key_value_values,
            "xml": update_xml_fields,
        },
        "validate": {
            "key-value": validate_key_value_settings,
            "xml": validate_xml_field_settings,
        },
    },
    "view": {
        "functions": {
            "key-value": view_key_value_values,
            "xml": xml_field_values,
        },
        "validate": {
            "key-value": validate_key_value_settings,
            "xml": validate_xml_field_settings,
        },
    },
}


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
        "verb": "view_details_help",
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
            "model_specs",
            ROUTER_SCHEMA_PATH,
            "Router model specifications",
        ],
        "when": "model_specs",
        "result": "model_specs",
    },
    {
        "phase": "pre",
        "fn": validate_router_settings,
        "args": ["model_specs", ROUTER_FUNCTIONS],
        "when": "model_specs",
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
        "args": ["meta", "model_specs", ROUTER_FUNCTIONS],
        "result": "validated",
    },
]

VIEW_MODEL_SPECS_EXEC = [
    {
        "phase": "exec",
        "fn": view_readme,
        "args": ["model_specs", MODEL_SPECS_README_PATH],
        "result": "view_readme_result",
    },
]

VIEW_ROUTER_DETAILS_EXEC = [
    {
        "phase": "exec",
        "fn": view_router_details,
        "args": [ROUTER_DETAILS_PATH],
        "result": "view_router_details_result",
    },
]

VIEW_ROUTER_DETAILS_HELP_EXEC = [
    {
        "phase": "exec",
        "fn": view_readme,
        "args": [None, ROUTER_DETAILS_README_PATH],
        "result": "view_readme_result",
    },
]

VIEW_DECODED_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": view_router_config_fields,
        "args": [
            DECODED_CONFIG_PATH,
            "ctx.model_specs.router_specs.edit",
            "ctx.model_specs.config_fields",
            ROUTER_FUNCTIONS["view"]["functions"],
            ROUTER_FUNCTIONS["decode"]["functions"],
        ],
        "result": "view_router_config_fields_result",
    },
]

VIEW_EDITED_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": view_router_config_fields,
        "args": [
            EDITED_CONFIG_PATH,
            "ctx.model_specs.router_specs.edit",
            "ctx.model_specs.config_fields",
            ROUTER_FUNCTIONS["view"]["functions"],
            ROUTER_FUNCTIONS["decode"]["functions"],
        ],
        "result": "view_router_config_fields_result",
    },
]

DECODE_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": decode_router_config,
        "args": [
            TEMPLATE_CONFIG_PATH,
            "ctx.model_specs.router_specs.codec",
            "ctx.model_specs.router_specs.hardware",
            "ctx.model_specs.router_specs.firmware",
            f"?{TEMPLATE_ROUTER_PASSWORD_PATH}",
            f"?{TEMPLATE_DEVICE_KEY_PATH}",
            ROUTER_FUNCTIONS["decode"]["functions"],
            ROUTER_FUNCTIONS["decode"]["validate"],
            ROUTER_FUNCTIONS["checksum"],
        ],
        "result": "decoded_data",
    },
    {
        "phase": "exec",
        "fn": save_router_config,
        "args": [
            "decoded_data",
            DECODED_CONFIG_ARCHIVE_PATH,
            "model_specs",
            ROUTER_FUNCTIONS["check"],
            ROUTER_FUNCTIONS["checksum"],
        ],
        "when": "decoded_data",
        "result": "archive_saved",
    },
    {
        "phase": "exec",
        "fn": extract_router_config,
        "args": [
            DECODED_CONFIG_ARCHIVE_PATH,
            DECODED_CONFIG_PATH,
            "model_specs",
            ROUTER_FUNCTIONS["extract"],
            ROUTER_FUNCTIONS["checksum"],
        ],
        "when": "archive_saved",
        "result": "decoded_directory",
    },
]

EDIT_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": edit_router_config_fields,
        "args": [
            DECODED_CONFIG_PATH,
            EDITED_CONFIG_PATH,
            "ctx.model_specs.router_specs.edit",
            "ctx.model_specs.config_fields",
            ROUTER_DETAILS_PATH,
            ROUTER_FUNCTIONS["edit"]["functions"],
            ROUTER_FUNCTIONS["view"]["functions"],
            ROUTER_FUNCTIONS["decode"]["functions"],
            ROUTER_FUNCTIONS["encode"]["functions"],
        ],
        "result": "edited_directory",
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
            "ctx.model_specs.router_specs.codec",
            "ctx.model_specs.router_specs.hardware",
            "ctx.model_specs.router_specs.firmware",
            "ctx.model_specs.router_specs.encode",
            "ctx.model_specs.router_specs.edit",
            "ctx.model_specs.config_fields",
            f"?{TEMPLATE_ROUTER_PASSWORD_PATH}",
            f"?{TARGET_ROUTER_PASSWORD_PATH}",
            f"?{TEMPLATE_DEVICE_KEY_PATH}",
            f"?{TARGET_DEVICE_KEY_PATH}",
            ROUTER_FUNCTIONS["encode"]["functions"],
            ROUTER_FUNCTIONS["encode"]["validate"],
            ROUTER_FUNCTIONS["decode"]["functions"],
            ROUTER_FUNCTIONS["decode"]["validate"],
            ROUTER_FUNCTIONS["checksum"],
            ROUTER_FUNCTIONS["view"]["functions"],
            ROUTER_FUNCTIONS["edit"]["functions"],
        ],
        "result": "encoded_config",
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
