# Simplified router utilities

The final layout is:

```text
modules/router_utils.py
modules/router_encryption_utils.py
```

The JSON specification supplies mechanism settings. `router_utils.py` selects the
encryption implementation using one `ENCRYPTION_HANDLERS` dictionary and performs the workflow.
Other processing uses direct mechanism checks and actual implementation calls.
`router_encryption_utils.py` owns the actual crypto and encryption-specific key handling.
The encryption module is byte-for-byte unchanged by this simplification.

## Removed machinery

The old multi-registry dispatch system and initialization calls were removed:
`ENCRYPTION_HANDLERS`, `KEY_DERIVATION_HANDLERS`, `ENCODING_HANDLERS`,
`WRAPPER_HANDLERS`, `ARCHIVE_HANDLERS`, and `CONFIGURATION_HANDLERS`.
Only `ENCRYPTION_HANDLERS` is retained, fully populated near the top with imported
callables keyed by `(encryption, key_derivation)`. Validation and both encryption
entry points use it directly. No other registries or registration calls exist.

The generic lookups and unnecessary forwarding functions were removed. Real processing
was merged into the existing public entry points where necessary. Internal callers and
tests now call the actual archive/configuration implementations. Loader-facing function
names and signatures are unchanged.

## Removed functions

- `binary_payload` (binary encode/decode now return the original object directly)

- `read_router_password`
- `validate_router_archive`
- `validate_binary_specs`
- `validate_key_value_content`
- `validate_key_value_edit`
- `load_password_credentials`
- `load_target_password_credentials`
- `mechanism_handler`
- `archive_handler`
- `archive_mode`
- `rebuild_router_archive`
- `configuration_handler`
- `parse_config_fields`
- `load_router_credentials`
- `load_target_router_credentials`

## Changed functions

- `validate_model_specs`
- `extract_tar_archive`
- `rebuild_tar_archive`
- `parse_key_value_fields`
- `validate_edited_fields`
- `validate_tar_specs`
- `validate_tar_gzip_config`
- `read_router_credential`
- `decrypt_router_payload`
- `encrypt_router_payload`
- `encode_router_payload`
- `decode_router_payload`
- `parse_router_wrapper`
- `rebuild_router_wrapper`
- `save_router_config`
- `extract_router_config`
- `view_router_config_fields`
- `edit_router_config_fields`
- `encode_router_config`

## Preserved behavior

The complete canonical JSON schema and existing model specification values are unchanged.
Validation still rejects missing, unexpected, incorrectly typed, and invalid mechanism
settings, accepts non-applicable null values, and identifies invalid JSON paths.

Spark password hashing, passphrase prefix, cipher, OpenSSL legacy derivation, salt,
Base64 output, wrapper checksums, archive processing and configuration mappings are
preserved. The original unsalted ciphertext digest is still checked by regression tests.
Credentials are loaded according to their declared mechanism; password files are never
silently interpreted as binary device keys.

TestingTools keeps interactive password/overwrite handling and model conversion, including
source preservation, destination-only fields and CRLF. AutomationTools keeps details-file
editing, separate template/target credential paths, staged output replacement and its
existing state-machine pipeline. RouterConstants and loader action definitions are unchanged.

## Actual verification

Before this simplification: **29 tests passed in each project, no skips**.
Current result: **30 tests passed in each project, no skips**.
Each suite ran independently using:

```text
python3 -m unittest discover -s tests -v
```

Coverage includes real local Spark backup decoding/editing/encoding and original-backup
preservation, salt/no-salt round trips and golden ciphertext, exact wrapper bytes, schema
validation, direct implementation selection, imports in both orders, two-module layout,
one complete encryption dictionary, absence of forwarding machinery, binary object identity, safe archive handling, TestingTools conversion,
and AutomationTools state-machine integration. Existing registry-injection test doubles
were replaced with direct helper-selection checks and a real-mechanism pipeline for a
different router identity; unsupported mechanism and safety assertions remain.

## Unsupported operations

THENC parsing and structural validation remain available. Vodafone decryption, device-key
derivation, signature verification, encryption/signing and authenticated rebuilding remain
unimplemented and retain explicit failure messages. A password text file is not a device
key. No encryption keys or unknown Vodafone plaintext settings were invented.

The existing automation pipeline generates and locally verifies a backup. Router-side
upload/restore is not implemented or tested. No original backup was overwritten.
