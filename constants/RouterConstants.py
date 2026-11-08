
# constants/RouterConstants.py
from __future__ import annotations

from typing import Any, Dict

from modules.display_utils import (
    display_config_doc,
    print_dict_table,
    print_router_dictionary,
)

from modules.json_utils import load_json, validate_json_schema
from modules.router_utils import (
    validate_router_inputs,
    validate_router_field_mappings,
    validate_router_details,
    validate_router_output_paths,
    validate_decoded_configuration,
    parse_router_wrapper,
    validate_configuration_changes,
    load_router_details,
    view_readme,
    view_router_details,
    save_router_config,
    extract_router_config,
    extract_configuration_file,
    resolve_router_operations,
    extract_router_settings,
    build_encode_operations,
    build_decode_operations,
    build_edit_operations,
    build_view_operations,
    run_router_operations,
    display_router_operations,
    read_router_input,
    prepare_codec_context,
    read_configuration_source,
    prepare_configuration_context,
    prepare_router_changes,
    display_configuration_values,
    validate_encode_paths,
    load_encode_credentials,
    compare_configuration_files,
    prepare_encode_payload,
    verify_encoded_backup,
    save_encoded_backup,
    save_configuration_directory,
    report_encoded_backup,
    report_edited_backup,

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
    encrypt_aes_256_cbc,
    decrypt_aes_256_cbc,
    encrypt_aes_256_cbc_fixed_key,
    decrypt_aes_256_cbc_fixed_key,
    encrypt_technicolor_thenc,
    decrypt_technicolor_thenc,
    calculate_payload_checksum, 
    decode_rsa_md5_configuration, 
    encode_rsa_md5_configuration,
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
            "rsa-md5": encode_rsa_md5_configuration,
            "signed-zlib": pack_signed_configuration,
            "aes-256-cbc": encrypt_aes_256_cbc,
            "fixed-key": encrypt_aes_256_cbc_fixed_key,
            "device-key": encrypt_technicolor_thenc,
            "openssl-legacy": encrypt_aes_256_cbc,
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
            "aes-256-cbc": decrypt_aes_256_cbc,
            "fixed-key": decrypt_aes_256_cbc_fixed_key,
            "device-key": decrypt_technicolor_thenc,
            "openssl-legacy": decrypt_aes_256_cbc,
            "tar.gz": read_tar_files,
            "signed-zlib": unpack_signed_configuration,
            "rsa-md5": decode_rsa_md5_configuration,
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
        "result": "validated_model_specs",
    },
    {
        "phase": "pre",
        "fn": extract_router_settings,
        "args": ["validated_model_specs"],
        "when": "validated_model_specs",
        "result": "router_settings",
    },
    {
        "phase": "pre",
        "fn": resolve_router_operations,
        "args": [
            "router_settings",
            ROUTER_FUNCTIONS["encode"]["functions"],
            "encode",
        ],
        "when": "router_settings",
        "result": "encode_operations",
    },
    {
        "phase": "pre",
        "fn": resolve_router_operations,
        "args": [
            "router_settings",
            ROUTER_FUNCTIONS["encode"]["validate"],
            "encode",
        ],
        "when": "router_settings",
        "result": "encode_validate_operations",
    },
    {
        "phase": "pre",
        "fn": resolve_router_operations,
        "args": [
            "router_settings",
            ROUTER_FUNCTIONS["decode"]["functions"],
            "decode",
        ],
        "when": "router_settings",
        "result": "decode_operations",
    },
    {
        "phase": "pre",
        "fn": resolve_router_operations,
        "args": [
            "router_settings",
            ROUTER_FUNCTIONS["decode"]["validate"],
            "decode",
        ],
        "when": "router_settings",
        "result": "decode_validate_operations",
    },
    {
        "phase": "pre",
        "fn": resolve_router_operations,
        "args": [
            "router_settings",
            ROUTER_FUNCTIONS["edit"]["functions"],
            "edit",
        ],
        "when": "router_settings",
        "result": "edit_operations",
    },
    {
        "phase": "pre",
        "fn": resolve_router_operations,
        "args": [
            "router_settings",
            ROUTER_FUNCTIONS["edit"]["validate"],
            "edit",
        ],
        "when": "router_settings",
        "result": "edit_validate_operations",
    },
    {
        "phase": "pre",
        "fn": resolve_router_operations,
        "args": [
            "router_settings",
            ROUTER_FUNCTIONS["view"]["functions"],
            "view",
        ],
        "when": "router_settings",
        "result": "view_operations",
    },
    {
        "phase": "pre",
        "fn": resolve_router_operations,
        "args": [
            "router_settings",
            ROUTER_FUNCTIONS["view"]["validate"],
            "view",
        ],
        "when": "router_settings",
        "result": "view_validate_operations",
    },
    {
        "phase": "pre",
        "fn": resolve_router_operations,
        "args": [
            "router_settings",
            ROUTER_FUNCTIONS["extract"],
            "extract",
        ],
        "when": "router_settings",
        "result": "extract_operations",
    },
    {
        "phase": "pre",
        "fn": resolve_router_operations,
        "args": [
            "router_settings",
            ROUTER_FUNCTIONS["check"],
            "check",
        ],
        "when": "router_settings",
        "result": "check_operations",
    },
    {
        "phase": "pre",
        "fn": resolve_router_operations,
        "args": [
            "router_settings",
            ROUTER_FUNCTIONS["checksum"],
            "checksum",
        ],
        "when": "router_settings",
        "result": "checksum_operations",
    },
    {
        "phase": "pre",
        "fn": build_encode_operations,
        "args": [
            "router_settings",
            "encode_operations",
            "encode_validate_operations",
        ],
        "when": "router_settings",
        "result": "encode_operations_list",
    },
    {
        "phase": "pre",
        "fn": build_decode_operations,
        "args": [
            "router_settings",
            "decode_operations",
            "decode_validate_operations",
        ],
        "when": "router_settings",
        "result": "decode_operations_list",
    },
    {
        "phase": "pre",
        "fn": build_edit_operations,
        "args": [
            "router_settings",
            "edit_operations",
            "edit_validate_operations",
        ],
        "when": "router_settings",
        "result": "edit_operations_list",
    },
    {
        "phase": "pre",
        "fn": build_view_operations,
        "args": [
            "router_settings",
            "view_operations",
            "view_validate_operations",
        ],
        "when": "router_settings",
        "result": "view_operations_list",
    },
]




# ---------------------------------------------------------------------
# EXEC PHASE STEPS
# ---------------------------------------------------------------------

READ_ROUTER_BACKUP_EXEC = [
    {
        "phase": "exec",
        "fn": read_router_input,
        "args": [
            TEMPLATE_CONFIG_PATH,
        ],
        "when": "validated_model_specs",
        "result": "router_backup",
    },
]

LOAD_DECODED_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": read_configuration_source,
        "args": [
            DECODED_CONFIG_PATH,
            "ctx.model_specs.router_specs.edit",
        ],
        "when": "validated_model_specs",
        "result": "decoded_source",
    },
]

LOAD_EDITED_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": read_configuration_source,
        "args": [
            EDITED_CONFIG_PATH,
            "ctx.model_specs.router_specs.edit",
        ],
        "when": "validated_model_specs",
        "result": "edited_source",
    },
]

LOAD_EXTRACTED_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": read_configuration_source,
        "args": [
            "ctx.decoded_directory",
            "ctx.model_specs.router_specs.edit",
        ],
        "when": "decoded_directory",
        "result": "decoded_source",
    },
]

LOAD_SAVED_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": read_configuration_source,
        "args": [
            "ctx.edited_directory",
            "ctx.model_specs.router_specs.edit",
        ],
        "when": "edited_directory",
        "result": "edited_source",
    },
]

VALIDATE_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": validate_router_inputs,
        "args": [
            "meta",
            "ctx.model_specs",
        ],
        "when": "validated_model_specs",
        "result": "router_inputs_validated",
    },
    {
        "phase": "exec",
        "fn": validate_router_field_mappings,
        "args": [
            "ctx.model_specs",
        ],
        "when": "validated_model_specs",
        "result": "router_fields_validated",
    },
    {
        "phase": "exec",
        "fn": validate_router_details,
        "args": [
            ROUTER_DETAILS_PATH,
            "ctx.model_specs.config_fields",
        ],
        "when": "validated_model_specs",
        "result": "router_details_validated",
    },
    {
        "phase": "exec",
        "fn": validate_router_output_paths,
        "args": [
            "meta",
        ],
        "result": "router_outputs_validated",
    },
    {
        "phase": "exec",
        "fn": read_router_input,
        "args": [
            TEMPLATE_CONFIG_PATH,
        ],
        "when": "router_inputs_validated",
        "result": "validation_input",
    },
    {
        "phase": "exec",
        "fn": parse_router_wrapper,
        "args": [
            "ctx.validation_input.data",
            "ctx.model_specs.router_specs.codec",
            "ctx.model_specs.router_specs.hardware",
            "ctx.model_specs.router_specs.firmware",
            ROUTER_FUNCTIONS["decode"]["functions"],
            ROUTER_FUNCTIONS["checksum"],
        ],
        "when": [
            "router_inputs_validated",
            "router_fields_validated",
            "router_details_validated",
            "router_outputs_validated",
            "validation_input",
        ],
        "result": "router_backup",
    },
    {
        "phase": "exec",
        "fn": print,
        "args": [
            "Router configuration validated.",
        ],
        "when": "router_backup",
        "result": "validation_reported",
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
        "fn": prepare_configuration_context,
        "args": [
            "ctx.decoded_source",
            "ctx.model_specs.router_specs.edit",
            "ctx.model_specs.config_fields",
            "ctx.decode_operations",
            None,
            "ctx.view_operations_list",
        ],
        "when": "decoded_source",
        "result": "decoded_view_context",
    },
    {
        "phase": "exec",
        "fn": run_router_operations,
        "args": [
            "ctx.decoded_view_context.original",
            "ctx.view_operations_list",
            "ctx.decoded_view_context",
        ],
        "when": "decoded_view_context",
        "result": "decoded_view_values",
    },
    {
        "phase": "exec",
        "fn": display_configuration_values,
        "args": [
            "ctx.decoded_view_values",
            "ctx.decoded_view_context",
            "ctx.model_specs.config_fields",
        ],
        "when": "decoded_view_context",
        "result": "decoded_view_displayed",
    },
]

VIEW_EDITED_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": prepare_configuration_context,
        "args": [
            "ctx.edited_source",
            "ctx.model_specs.router_specs.edit",
            "ctx.model_specs.config_fields",
            "ctx.decode_operations",
            None,
            "ctx.view_operations_list",
        ],
        "when": "edited_source",
        "result": "edited_view_context",
    },
    {
        "phase": "exec",
        "fn": run_router_operations,
        "args": [
            "ctx.edited_view_context.original",
            "ctx.view_operations_list",
            "ctx.edited_view_context",
        ],
        "when": "edited_view_context",
        "result": "edited_view_values",
    },
    {
        "phase": "exec",
        "fn": display_configuration_values,
        "args": [
            "ctx.edited_view_values",
            "ctx.edited_view_context",
            "ctx.model_specs.config_fields",
        ],
        "when": "edited_view_context",
        "result": "edited_view_displayed",
    },
]

DECODE_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": prepare_codec_context,
        "args": [
            "ctx.model_specs.router_specs.codec",
            "ctx.model_specs.router_specs.hardware",
            "ctx.model_specs.router_specs.firmware",
            f"?{TEMPLATE_ROUTER_PASSWORD_PATH}",
            f"?{TEMPLATE_DEVICE_KEY_PATH}",
            "ctx.checksum_operations",
            "ctx.model_specs.router_specs.edit",
        ],
        "when": "router_backup",
        "result": "decode_context",
    },
    {
        "phase": "exec",
        "fn": run_router_operations,
        "args": [
            "ctx.router_backup.data",
            "ctx.decode_operations_list",
            "ctx.decode_context",
        ],
        "when": "decode_context",
        "result": "decoded_data",
    },
    {
        "phase": "exec",
        "fn": validate_decoded_configuration,
        "args": [
            "ctx.decoded_data",
            "ctx.model_specs",
            "ctx.check_operations",
            "ctx.checksum_operations",
        ],
        "when": "decode_context",
        "result": "decoded_format_validated",
    },
    {
        "phase": "exec",
        "fn": save_router_config,
        "args": [
            "ctx.decoded_data",
            DECODED_CONFIG_ARCHIVE_PATH,
            "ctx.model_specs",
            True,
        ],
        "when": "decoded_format_validated",
        "result": "archive_saved",
    },
    {
        "phase": "exec",
        "fn": extract_router_config,
        "args": [
            DECODED_CONFIG_ARCHIVE_PATH,
            DECODED_CONFIG_PATH,
            "ctx.model_specs",
            "ctx.extract_operations",
            "ctx.checksum_operations",
            True,
        ],
        "when": "archive_saved",
        "result": "decoded_directory",
    },
]

EDIT_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": prepare_configuration_context,
        "args": [
            "ctx.decoded_source",
            "ctx.model_specs.router_specs.edit",
            "ctx.model_specs.config_fields",
            "ctx.decode_operations",
            "ctx.encode_operations",
            "ctx.view_operations_list",
            "ctx.edit_operations_list",
            EDITED_CONFIG_PATH,
        ],
        "when": "decoded_source",
        "result": "edit_context",
    },
    {
        "phase": "exec",
        "fn": run_router_operations,
        "args": [
            "ctx.edit_context.original",
            "ctx.view_operations_list",
            "ctx.edit_context",
        ],
        "when": "edit_context",
        "result": "edit_values",
    },
    {
        "phase": "exec",
        "fn": load_router_details,
        "args": [
            ROUTER_DETAILS_PATH,
        ],
        "result": "edit_details",
    },
    {
        "phase": "exec",
        "fn": prepare_router_changes,
        "args": [
            "ctx.edit_values",
            "ctx.edit_details",
            "ctx.edit_context",
        ],
        "when": "edit_context",
        "result": "edit_changes_context",
    },
    {
        "phase": "exec",
        "fn": run_router_operations,
        "args": [
            "ctx.edit_changes_context.original",
            "ctx.edit_operations_list",
            "ctx.edit_changes_context",
        ],
        "when": "edit_changes_context",
        "result": "edited_text",
    },
    {
        "phase": "exec",
        "fn": validate_configuration_changes,
        "args": [
            "ctx.edit_changes_context.original",
            "ctx.edited_text",
            "ctx.edit_changes_context.specs",
            "ctx.edit_changes_context.viewer",
            "ctx.edit_changes_context.editor",
            "ctx.edit_changes_context.decrypt_handler",
            "ctx.edit_changes_context.encrypt_handler",
        ],
        "when": "edit_changes_context",
        "result": "edit_verified",
    },
    {
        "phase": "exec",
        "fn": save_configuration_directory,
        "args": [
            "ctx.edit_changes_context.source",
            "ctx.edit_changes_context.destination",
            "ctx.edit_changes_context.relative",
            "ctx.edit_changes_context.original_bytes",
            "ctx.edited_text",
            "ctx.model_specs.router_specs.edit",
            "ctx.model_specs.config_fields",
            "ctx.edit_changes_context.changes",
            "ctx.edit_changes_context.decrypt_handler",
            "ctx.edit_changes_context.encrypt_handler",
            "ctx.edit_changes_context.viewer",
            "ctx.edit_changes_context.editor",
        ],
        "when": "edit_verified",
        "result": "edit_saved",
    },
    {
        "phase": "exec",
        "fn": report_edited_backup,
        "args": [
            "ctx.edit_changes_context",
        ],
        "when": "edit_saved",
        "result": "edited_directory",
    },
]

ENCODE_CONFIG_EXEC = [
    {
        "phase": "exec",
        "fn": validate_encode_paths,
        "args": [
            "ctx.edited_source.source",
            TEMPLATE_CONFIG_PATH,
            ENCODED_CONFIG_PATH,
        ],
        "when": "edited_source",
        "result": "encode_paths",
    },
    {
        "phase": "exec",
        "fn": read_router_input,
        "args": [
            TEMPLATE_CONFIG_PATH,
        ],
        "when": "encode_paths",
        "result": "encode_original_input",
    },
    {
        "phase": "exec",
        "fn": prepare_codec_context,
        "args": [
            "ctx.model_specs.router_specs.codec",
            "ctx.model_specs.router_specs.hardware",
            "ctx.model_specs.router_specs.firmware",
            f"?{TEMPLATE_ROUTER_PASSWORD_PATH}",
            f"?{TEMPLATE_DEVICE_KEY_PATH}",
            "ctx.checksum_operations",
            "ctx.model_specs.router_specs.edit",
        ],
        "when": "encode_original_input",
        "result": "encode_original_context",
    },
    {
        "phase": "exec",
        "fn": run_router_operations,
        "args": [
            "ctx.encode_original_input.data",
            "ctx.decode_operations_list",
            "ctx.encode_original_context",
        ],
        "when": "encode_original_context",
        "result": "encode_original_archive",
    },
    {
        "phase": "exec",
        "fn": validate_decoded_configuration,
        "args": [
            "ctx.encode_original_archive",
            "ctx.model_specs",
            "ctx.check_operations",
            "ctx.checksum_operations",
        ],
        "when": "encode_original_context",
        "result": "encode_original_validated",
    },
    {
        "phase": "exec",
        "fn": load_encode_credentials,
        "args": [
            "ctx.model_specs.router_specs.codec",
            f"?{TARGET_ROUTER_PASSWORD_PATH}",
            f"?{TARGET_DEVICE_KEY_PATH}",
        ],
        "when": "encode_paths",
        "result": "encode_credentials",
    },
    {
        "phase": "exec",
        "fn": compare_configuration_files,
        "args": [
            "ctx.encode_paths.directory",
            "ctx.encode_original_context.files",
            "ctx.model_specs.router_specs.edit",
        ],
        "when": ["encode_paths", "encode_original_validated"],
        "result": "encode_files",
    },
    {
        "phase": "exec",
        "fn": prepare_configuration_context,
        "args": [
            "ctx.edited_source",
            "ctx.model_specs.router_specs.edit",
            "ctx.model_specs.config_fields",
            "ctx.decode_operations",
            "ctx.encode_operations",
            "ctx.view_operations_list",
            "ctx.edit_operations_list",
        ],
        "when": ["edited_source", "encode_paths"],
        "result": "encode_configuration_context",
    },
    {
        "phase": "exec",
        "fn": validate_configuration_changes,
        "args": [
            "ctx.encode_files.original",
            "ctx.encode_files.edited",
            "ctx.encode_configuration_context.specs",
            "ctx.encode_configuration_context.viewer",
            "ctx.encode_configuration_context.editor",
            "ctx.encode_configuration_context.decrypt_handler",
            "ctx.encode_configuration_context.encrypt_handler",
        ],
        "when": ["encode_files", "encode_configuration_context"],
        "result": "encode_edits_verified",
    },
    {
        "phase": "exec",
        "fn": prepare_encode_payload,
        "args": [
            "ctx.encode_original_archive",
            "ctx.encode_original_context",
            "ctx.encode_files",
            "ctx.encode_credentials",
            "ctx.model_specs.router_specs.encode",
            "ctx.encode_paths.directory",
        ],
        "when": [
            "encode_original_validated",
            "encode_files",
            "encode_edits_verified",
            "encode_credentials",
        ],
        "result": "encode_context",
    },
    {
        "phase": "exec",
        "fn": run_router_operations,
        "args": [
            "ctx.encode_context.data",
            "ctx.encode_operations_list",
            "ctx.encode_context",
        ],
        "when": "encode_context",
        "result": "encoded_data",
    },
    {
        "phase": "exec",
        "fn": prepare_codec_context,
        "args": [
            "ctx.model_specs.router_specs.codec",
            "ctx.model_specs.router_specs.hardware",
            "ctx.model_specs.router_specs.firmware",
            f"?{TARGET_ROUTER_PASSWORD_PATH}",
            f"?{TARGET_DEVICE_KEY_PATH}",
            "ctx.checksum_operations",
        ],
        "when": "encoded_data",
        "result": "encode_verify_context",
    },
    {
        "phase": "exec",
        "fn": run_router_operations,
        "args": [
            "ctx.encoded_data",
            "ctx.decode_operations_list",
            "ctx.encode_verify_context",
        ],
        "when": ["encoded_data", "encode_verify_context"],
        "result": "encode_recovered",
    },
    {
        "phase": "exec",
        "fn": verify_encoded_backup,
        "args": [
            "ctx.encode_recovered",
            "ctx.encode_context.expected",
        ],
        "when": ["encoded_data", "encode_verify_context", "encode_context"],
        "result": "encode_verified",
    },
    {
        "phase": "exec",
        "fn": save_encoded_backup,
        "args": [
            "ctx.encode_paths.output",
            "ctx.encoded_data",
        ],
        "when": ["encode_verified", "encode_edits_verified"],
        "result": "encode_saved",
    },
    {
        "phase": "exec",
        "fn": report_encoded_backup,
        "args": [
            "ctx.encode_paths.output",
            "ctx.encode_context",
        ],
        "when": "encode_saved",
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
# ACTION OPERATION DISPLAYS
# ---------------------------------------------------------------------

DISPLAY_ENCODE_OPERATIONS_PRE = [
    {
        "phase": "pre",
        "fn": display_router_operations,
        "args": ["encode_operations_list", "Encode Operations"],
        "when": "encode_operations_list",
        "result": "encode_operations_displayed",
    },
]


DISPLAY_DECODE_OPERATIONS_PRE = [
    {
        "phase": "pre",
        "fn": display_router_operations,
        "args": ["decode_operations_list", "Decode Operations"],
        "when": "decode_operations_list",
        "result": "decode_operations_displayed",
    },
]


DISPLAY_EDIT_OPERATIONS_PRE = [
    {
        "phase": "pre",
        "fn": display_router_operations,
        "args": ["edit_operations_list", "Edit Operations"],
        "when": "edit_operations_list",
        "result": "edit_operations_displayed",
    },
]


DISPLAY_VIEW_OPERATIONS_PRE = [
    {
        "phase": "pre",
        "fn": display_router_operations,
        "args": ["view_operations_list", "View Operations"],
        "when": "view_operations_list",
        "result": "view_operations_displayed",
    },
]


# ---------------------------------------------------------------------
# PIPELINES
# ---------------------------------------------------------------------

PIPELINE_STATES: Dict[str, Dict[str, Any]] = {
    "VALIDATE_CONFIG": {
        "pipeline": [
            *LOAD_MODEL_SPECS_PRE,
            *DISPLAY_ENCODE_OPERATIONS_PRE,
            *DISPLAY_DECODE_OPERATIONS_PRE,
            *DISPLAY_EDIT_OPERATIONS_PRE,
            *DISPLAY_VIEW_OPERATIONS_PRE,
            *VALIDATE_CONFIG_EXEC,
        ],
        "label": "VALIDATION_COMPLETE",
    },
    "VIEW_MODEL_SPECS": {
        "pipeline": [
            *LOAD_MODEL_SPECS_PRE,
            *VIEW_MODEL_SPECS_EXEC,
        ],
        "label": "VIEW_MODEL_SPECS_COMPLETE",
    },
    "VIEW_DECODED_CONFIG": {
        "pipeline": [
            *LOAD_MODEL_SPECS_PRE,
            *DISPLAY_VIEW_OPERATIONS_PRE,
            *LOAD_DECODED_CONFIG_EXEC,
            *VIEW_DECODED_CONFIG_EXEC,
        ],
        "label": "VIEW_DECODED_COMPLETE",
    },
    "VIEW_EDITED_CONFIG": {
        "pipeline": [
            *LOAD_MODEL_SPECS_PRE,
            *DISPLAY_VIEW_OPERATIONS_PRE,
            *LOAD_EDITED_CONFIG_EXEC,
            *VIEW_EDITED_CONFIG_EXEC,
        ],
        "label": "VIEW_EDITED_COMPLETE",
    },
    "VIEW_ROUTER_DETAILS": {
        "pipeline": [
            *VIEW_ROUTER_DETAILS_EXEC,
        ],
        "label": "VIEW_DETAILS_COMPLETE",
    },
    "VIEW_ROUTER_DETAILS_HELP": {
        "pipeline": [
            *VIEW_ROUTER_DETAILS_HELP_EXEC,
        ],
        "label": "VIEW_ROUTER_DETAILS_HELP_COMPLETE",
    },
    "DECODE_CONFIG": {
        "pipeline": [
            *LOAD_MODEL_SPECS_PRE,
            *DISPLAY_DECODE_OPERATIONS_PRE,
            *READ_ROUTER_BACKUP_EXEC,
            *DECODE_CONFIG_EXEC,
        ],
        "label": "DECODE_COMPLETE",
    },
    "EDIT_CONFIG": {
        "pipeline": [
            *LOAD_MODEL_SPECS_PRE,
            *DISPLAY_EDIT_OPERATIONS_PRE,
            *LOAD_DECODED_CONFIG_EXEC,
            *EDIT_CONFIG_EXEC,
        ],
        "label": "EDIT_COMPLETE",
    },
    "ENCODE_CONFIG": {
        "pipeline": [
            *LOAD_MODEL_SPECS_PRE,
            *DISPLAY_ENCODE_OPERATIONS_PRE,
            *LOAD_EDITED_CONFIG_EXEC,
            *ENCODE_CONFIG_EXEC,
        ],
        "label": "ENCODE_COMPLETE",
    },
    "RUN_ALL": {
        "pipeline": [
            *LOAD_MODEL_SPECS_PRE,
            *DISPLAY_DECODE_OPERATIONS_PRE,
            *DISPLAY_VIEW_OPERATIONS_PRE,
            *DISPLAY_EDIT_OPERATIONS_PRE,
            *DISPLAY_ENCODE_OPERATIONS_PRE,
            *VALIDATE_CONFIG_EXEC,
            *DECODE_CONFIG_EXEC,
            *LOAD_EXTRACTED_CONFIG_EXEC,
            *VIEW_DECODED_CONFIG_EXEC,
            *EDIT_CONFIG_EXEC,
            *LOAD_SAVED_CONFIG_EXEC,
            *VIEW_EDITED_CONFIG_EXEC,
            *ENCODE_CONFIG_EXEC,
        ],
        "label": "ROUTER_AUTOMATION_COMPLETE",
    },
    "SHOW_CONFIG_DOC": {
        "pipeline": [
            *SHOW_CONFIG_DOC_EXEC,
        ],
        "label": "DONE",
    },
}
