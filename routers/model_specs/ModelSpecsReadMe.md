# Router Model Specifications

AutomationTools uses one common JSON schema across its supplied models and direct mechanism selections.
The shared HG659 processing mechanisms and specification structure follow TestingTools;
AutomationTools retains its own workflows and file-based Spark credentials.
`modules/router_utils.py` coordinates workflows, credentials and specification validation.
`modules/router_format_utils.py` implements transport encoding, backup wrappers and archive processing.
`modules/router_config_utils.py` implements configuration parsing, transformations and path checks.
`modules/router_encryption_utils.py` implements encryption and cryptographic checksums.

## Adding a Router Model

Copy `doc/RouterSpecificationTemplate.json`, or an existing model specification, and
populate the settings supported by the exported backup. The template includes every
canonical key and nested object; its null values are placeholders, not a runnable
router configuration. Existing Spark and Vodafone specifications are complete examples.

Every specification must contain exactly the canonical keys, including all keys inside
`config_fields`, `backup_format`, `checksum`, `prefix`, `trailer`, `archive`,
`encryption_settings`, `signature`, and `field_encryption`.
Do not omit inactive fields: use JSON `null`. Empty strings and the string `"unknown"`
are not placeholders for unknown or non-applicable values.

`ROUTER_SPEC_SCHEMA` in `router_utils.py` defines the types and complete structure.
Schema validation rejects missing keys, unexpected keys, incorrectly typed values, and
booleans used as integers. Mechanism validators then require their applicable values.
Errors identify the invalid JSON path. The same model has the same specification values
in both projects, although the configured filenames retain each application's existing names.

The canonical `config_fields` roles are `file`, `wifi_2g_ssid`, `wifi_2g_password`,
`wifi_5g_ssid`, and `wifi_5g_password`. Set unused mappings to null; a known configuration
format requires `file`. Configuration keys are router-specific values, not Python branches.
A new semantic field would require a coordinated canonical-schema update in both projects
and all specifications, rather than adding a one-off JSON key for one router.

## Existing Mechanisms

`router_utils.py` selects encryption using one complete `ENCRYPTION_HANDLERS`
dictionary keyed by `(encryption, key_derivation)`. Its values are imported callables.
Validation and encryption entry points use the same central dictionaries.
`CONFIG_VIEW_HANDLERS`/`CONFIG_EDIT_HANDLERS` select configuration processing;
`FIELD_DECRYPT_HANDLERS`/`FIELD_ENCRYPT_HANDLERS` select protected-field processing. Other processing uses ordinary `if` / `elif` checks. There are no registration calls, function-name
lookup systems, or router-model branches.

| JSON setting | Supported mechanisms |
|---|---|
| `encryption` + `key_derivation` | `aes-256-cbc` + `openssl-legacy`; `aes-256-cbc` + `device-key` (explicitly unavailable); `aes-256-cbc` + `fixed-key` |
| `encoding` | `base64`, `binary` |
| `backup_format.type` | `line-wrapper`, `technicolor-thenc` (structural parsing only), `encrypted-configuration` |
| `archive.format` + `archive.compression` | `tar` + `gzip`; `single-file` + `zlib` |
| `configuration_format` | `key-value`; `xml` (viewing, targeted attribute editing and signed encoding) |

`encrypt_router_payload` and `decrypt_router_payload` select and call the imported
`crypt_aes_256_cbc`, `crypt_technicolor_thenc` or `crypt_aes_256_cbc_fixed_key` directly. The actual algorithms,
key preparation, credential interpretation and unsupported THENC errors remain in
`router_encryption_utils.py`. Workflow path selection and user interaction stay in `router_utils.py`; archive file processing lives in the format module.

Encoding and wrapper entry points select processing mechanisms from the specification.
Their implementations live in `router_format_utils.py`, independently of the orchestrator. Archive
workflows call `read_tar_files`, `extract_tar_archive`, and `rebuild_tar_archive`;
`tar_gzip_mode` validates the configured format/compression and supplies the mode.
Configuration workflows call `router_config_utils.py` functions `parse_key_value_fields`, `key_value_values`,
`update_key_value_fields`, and `normalize_key_value_fields` directly. Unsupported
formats fail explicitly. Archive safety and editable-field integrity checks remain.

A router using supported mechanisms requires its JSON specification and configuration
entry/files. A new mechanism requires a substantive implementation and a corresponding
entry in the relevant existing dispatcher. Other new mechanisms use explicit selection
branches; do not introduce additional registries or modules.

## Spark Credentials and Processing

The existing factory Wi-Fi password, passphrase prefix, MD5 password hash, OpenSSL
legacy derivation digest, salt behavior, Base64 layout, checksum, random prefix,
TAR/GZIP archive, and configuration mappings are preserved. Passwords stay in the
existing configured files, separate from model specifications. Login passwords,
Wi-Fi settings being edited, and backup encryption credentials are distinct concepts.

## Vodafone THENC Limitations

Both projects validate the supplied THENC specification and parse the existing header,
16-byte IV, AES block-aligned ciphertext, and configured 20-byte signature boundary.
Parsing establishes structure only; it does not verify the signature or decrypt data.

`password_base`, `password_hash`, `key_derivation_digest`, unknown configuration mappings,
unknown archive settings, and unknown configuration format are null. Non-applicable
line-wrapper fields remain present with null values. The known `salted: false` and
`password_required: false` values and all observed header/key identifiers are preserved.

`CIPHERKEY` and `SIGNATUREKEY` are identifiers, not cryptographic keys. Configured device-key files can now be read as binary. Device-key derivation, signature
verification, signing, and authenticated encryption/rebuilding remain unverified.
Attempting actual cryptographic processing still fails explicitly; even
an explicitly supplied key is rejected until derivation and authentication are verified.
An export-password text file is never read as a binary device key. No router login or
Wi-Fi password is substituted. Archive format and configuration fields remain unknown.

## AutomationTools Workflow

Each top-level job in `config/RouterConfig.json` retains its existing paths:
`model_specs_path`, `model_specs_readme_path`, `template_config_path`,
`template_router_password_path`, `target_router_password_path`, `router_details_path`,
`router_details_readme_path`, `decoded_config_archive_path`, `decoded_config_path`,
`edited_config_path`, and `encoded_config_path`.

RouterConstants and AutomationLoader keep their existing actions and state transitions.
Run All validates the job, decodes the template, applies the declared router details,
and rebuilds/encrypts the target backup. Template and target credentials are loaded
from separate configured paths; automation never prompts for a password. Only populated
field mappings can be edited. Existing staged replacement and failure handling remain.
The result is verified locally by decrypting it with the target credential.

The existing pipeline generates a backup file. It has no implemented device-upload or
router-side restore stage; this refactor does not add one or claim device deployment.

## Optional Device-Key Files

Jobs may include optional `template_device_key_path` and `target_device_key_path`.
Decode appends the template path. Encode appends the template path then the target path
(named `device_key_path`), after the existing six arguments. Target verification uses
the target key. Existing password argument positions are unchanged.

Device-key models require a configured, nonempty binary key file. Spark ignores these
paths. Loading bytes does not implement or verify Vodafone cryptography. THENC
`CIPHERKEY` and `SIGNATUREKEY` values are read from each backup header and preserved
in wrapper metadata and original header bytes; `cipher_key_id` and `signature_key_id`
are no longer static model specification fields.


## Vodafone HG659 V100R001C206B020

The configured `Vodafone_HG659` job supports decoding, viewing, editing, encoding
and **Run All Steps** through the existing actions and pipelines.
Its binary `.conf` template uses the specification's fixed AES-256-CBC key and IV.
The decrypted single-file zlib stream contains null-terminated XML followed by an
RSA/MD5 PKCS#1 v1.5 signature. The complete signature block is verified before any
configuration is saved. Invalid compression, signatures and AES zero padding fail.

`decoded_config_archive_path` ends in `.xml`; `decoded_config_path` is the extracted
directory containing the configured `config.xml`. The authenticated XML bytes are
preserved exactly. Huawei's nonstandard XML syntax produces an advisory warning,
without requiring full strict XML parsing or rewriting the document.

The generic XML reader selects `element|attribute=value|output_attribute` or
`element|attribute=value|child_element@output_attribute`. Multiple conditions must
all match; exactly one parent and, when requested, one child must match. Child
searches stay inside the selected parent. Comments and CDATA are ignored, and
standard XML entities are decoded in displayed attributes. Null mappings are skipped.
HG659 selects each main Wi-Fi network using both its frequency band and non-guest
condition. Passwords come from the selected `PreSharedKeyInstance` child attribute.

The common `field_encryption` object contains `algorithm`, `key_hex`, `iv_hex` and
`fields`. The registered `aes-128-cbc-zero-padded-base64` handler strictly decodes
Base64, applies AES-128-CBC, strips trailing zero padding and returns UTF-8 for the
listed password fields. SSIDs remain unchanged. The existing viewer displays these
readable passwords; viewing never modifies configuration files.

All keys, IVs and RSA verification/signing parameters come from the specification, including the
separate inner field encryption settings. HG659 has no password-file or device-key
entry and does not read external credentials. Spark and Ultra Hub retain their
existing settings; their unused common encryption/signature/field settings are null.
HG659's AES functions use `python3-cryptography`, declared alongside `openssl` in
the existing router dependency list.

XML attribute editing now uses the existing file-driven operation. The configured
`router_details_path` supplies label/value replacements; omitted fields retain their
stored values. Current SSIDs, decrypted passwords and change summaries are displayed
in plaintext. No interactive field prompts or password masking are added. Existing
action confirmation and automation sequencing remain unchanged.

The shared XML selector locates each configured parent/child attribute uniquely.
Only selected value spans change; replacements are escaped, protected fields are
encrypted with the existing AES-128-CBC settings, and all unrelated XML bytes and
guest-network settings must remain identical. Both proposed and staged edited XML
are validated before directory replacement. The original decoded input is preserved.

Every specification and the template now includes `signature.private_exponent_hex`.
It is null for unused models/template and contains the working TestingTools signing
exponent for HG659. Verification-only specifications can omit a populated exponent,
but signing and full automation fail explicitly when it is unavailable.

The existing encoder validates edited XML against the authenticated original,
appends NUL and a verified RSA/MD5 PKCS#1 v1.5 signature, compresses with zlib level 9,
adds 1–16 zero padding bytes and encrypts through the fixed-key AES-256-CBC dispatcher.
The decoder accepts the reference encoder's full padding block when already aligned.
The staged output is decoded again and must recover exactly the edited XML before
atomic publication. Output paths cannot overwrite the original backup or edited input.
The existing `.conf` output and other configured paths remain unchanged; no signing-key,
password or device-key file is used for HG659.

Spark TAR/GZIP editing and encoding retain their existing processing. Technicolor
THENC derivation/authentication/signing remain unavailable and continue to fail
explicitly. Local cryptographic round trips do not establish router acceptance;
no hardware upload or restore is performed.


## Central registrations and processing callbacks

All five handler dictionaries are together under `DISPATCHER HANDLERS` at the top
of `modules/router_utils.py`: `ENCRYPTION_HANDLERS`, `FIELD_ENCRYPT_HANDLERS`,
`FIELD_DECRYPT_HANDLERS`, `CONFIG_VIEW_HANDLERS` and `CONFIG_EDIT_HANDLERS`.
Implementations remain in their specialised encryption, configuration and format
modules, which do not import the orchestrator or contain handler registrations.

The orchestrator selects field callbacks from `field_encryption.algorithm` and
passes them explicitly. `xml_field_values` and the key-value view adapter accept
an optional `decrypt_handler`; `update_xml_fields` and the key-value edit adapter
accept an optional `encrypt_handler`. `validate_xml_field_changes` and
`validate_edited_xml` accept both. Protected fields require the selected callbacks;
there is no hidden registry or fallback in configuration processing. The key-value
adapters accept the same optional arguments without changing their parsing/editing.
Public router workflow signatures are unchanged, and either dependency import order
works without circular imports.

To add a mechanism, implement it in its specialised utility, register it once in
`router_utils.py`, and select it through the common specification. No model-name
checks, new loaders, credential files or separate workflows are needed.
