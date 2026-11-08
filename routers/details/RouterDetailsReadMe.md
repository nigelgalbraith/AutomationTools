# Router Model Specifications

Router model specifications define the information and processing methods required to decode, view, edit, and encode supported router configuration backups.

AutomationTools and TestingTools use the same specification structure and JSON schema.

Each router model has a JSON specification stored in `routers/model_specs/`.

## Specification Structure

Every specification contains two top-level properties:

| Property | Description |
|---|---|
| `router_specs` | Router identity and backup processing settings |
| `config_fields` | Logical configuration field mappings |

`router_specs` contains these required properties:

| Property | Description |
|---|---|
| `model` | Router model identifier |
| `firmware` | Firmware version |
| `hardware` | Hardware revision |
| `codec` | Backup encryption, encoding, wrapper, archive, and processing settings |
| `encode` | Additional encoding-only settings, or `null` |
| `edit` | Configuration editing settings, or `null` |

The specification is validated against `schemas/RouterSchema.json`, which uses JSON Schema Draft 2020-12.

Required properties must remain present. Use `null` for unused settings where permitted by the schema.

## Specification Example

The following example illustrates the specification structure:

```json
{
  "router_specs": {
    "model": "ExampleRouter",
    "firmware": "1.0",
    "hardware": "R1",
    "codec": {},
    "encode": null,
    "edit": {
      "configuration_file": "config/settings.conf",
      "configuration_format": "key-value",
      "field_encryption": null
    }
  },
  "config_fields": [
    {
      "name": "wifi_2g_ssid",
      "path": "ACTUAL_SSID_KEY"
    },
    {
      "name": "wifi_2g_password",
      "path": "ACTUAL_PASSWORD_KEY"
    }
  ]
}
```

This is a structural example, not a complete working specification.

The required codec properties and valid format combinations are defined by the schema and registered processing functions.

Use `doc/RouterSpecificationTemplate.json` as the starting point for a complete specification.

## Codec Settings

`router_specs.codec` describes how the router backup is processed.

Important properties include:

| Property | Description |
|---|---|
| `encoding` | Payload encoding method |
| `encryption` | Encryption algorithm |
| `key_derivation` | Encryption key derivation method |
| `password_base` | Base password material where required |
| `password_hash` | Password hashing method |
| `key_derivation_digest` | Key derivation digest |
| `salted` | Whether the specified key derivation uses a salt |
| `password_required` | Whether a password file is required |
| `device_key_required` | Whether a binary device key is required |
| `encryption_settings` | Additional encryption parameters |
| `wrapper` | Backup wrapper format |
| `archive` | Archive or compression format |
| `checksum` | Checksum method |
| `signature` | Signature algorithm or settings |
| `decode_order` | Ordered decoding operations |
| `encode_order` | Ordered encoding operations |
| `decoded_extension` | Decoded payload extension |

Additional codec properties describe wrapper formatting and cryptographic parameters, including:

- `header_lines`
- `preserve_header`
- `payload_line_length`
- `newline`
- `checksum_after_payload_lines`
- `checksum_prefix_bytes`
- `trailer_character`
- `trailer_repeat`
- `iv_length`
- `signature_length`
- `preamble`
- `backup_version`
- `header_terminator`

The applicable settings depend on the selected backup format.

Codec properties are declared in the specification. Registered processing functions validate the parameters required by their implementations.

## Encode and Decode Order

Router specifications define the order in which processing mechanisms execute.

For example, Spark SmartModem uses:

```json
"decode_order": [
  "wrapper",
  "encoding",
  "encryption",
  "archive"
],
"encode_order": [
  "archive",
  "encryption",
  "encoding",
  "wrapper"
]
```

Each processing role is resolved to a registered function.

Validation operations are placed before the corresponding transformations.

Signature processing is positioned according to the selected format's signing and verification requirements.

A `null` operation order uses the applicable registered default order.

## Encoding Settings

`router_specs.encode` contains parameters required only when encoding a backup.

For example, Vodafone Huawei HG659 uses:

```text
router_specs.encode.private_exponent_hex
```

This supplies the private exponent required by the supported signing process.

When no additional encoding settings are required, use:

```json
"encode": null
```

## Editing Settings

`router_specs.edit` identifies the configuration file, configuration format, and optional protected fields.

Example:

```json
"edit": {
  "configuration_file": "config/.glbcfg",
  "configuration_format": "key-value",
  "field_encryption": null
}
```

The supported properties are:

| Property | Description |
|---|---|
| `configuration_file` | File containing the editable configuration |
| `configuration_format` | Configuration format, such as `key-value` or `xml` |
| `field_encryption` | Field-level encryption settings, or `null` |

Field encryption settings may specify an algorithm and the logical field names requiring protected-value processing.

If the router's configuration format or editing mechanism is not established, use:

```json
"edit": null
```

## Configuration Field Mappings

`config_fields` maps common logical field names to the keys or selectors used by a router.

Each entry has the form:

```json
{
  "name": "logical_name",
  "path": "actual_configuration_key_or_selector"
}
```

The supplied router models include logical fields such as:

- `wifi_2g_ssid`
- `wifi_2g_password`
- `wifi_5g_ssid`
- `wifi_5g_password`

For key-value configurations, the path identifies the actual configuration key.

For XML configurations, the path identifies an element or attribute selector.

Supported XML selector forms include:

| Selector | Purpose |
|---|---|
| `element\|filter=value\|attribute` | Select an attribute from a matching element |
| `child@attribute` | Select an attribute on a child element |

An example XML mapping is:

```json
{
  "name": "wifi_2g_ssid",
  "path": "WLANConfigurationInstance|X_OperatingFrequencyBand=2.4GHz|X_Is_Guest_Network=0|SSID"
}
```

A `null` field path indicates that the corresponding configuration location is unavailable or unsupported.

Only fields with supported mappings and configuration formats can be edited.

## Registered Operations

Both applications define their router function registry in:

```text
constants/RouterConstants.py
```

The registry is named `ROUTER_FUNCTIONS`.

It contains these categories:

| Category | Purpose |
|---|---|
| `encode` | Encoding functions and validators |
| `decode` | Decoding functions and validators |
| `extract` | Configuration extraction |
| `check` | Configuration format checking |
| `checksum` | Checksum functions |
| `edit` | Configuration editing functions and validators |
| `view` | Configuration viewing functions and validators |

The router utility provides the following operation functions:

```python
resolve_router_operations()
build_encode_operations()
build_decode_operations()
build_edit_operations()
build_view_operations()
run_router_operations()
```

`resolve_router_operations()` selects the applicable functions from `ROUTER_FUNCTIONS`.

The four builders construct ordered operation lists using the model specification and applicable validators.

`run_router_operations()` executes the supplied operations in sequence, passing transformation results between functions.

The application pipeline determines when the operations are built, displayed, and executed.

Individual encryption, format, and configuration functions are implemented in the corresponding router utility modules.

## Router Credentials

A model specification declares credential requirements but does not store credential file paths.

Credential file locations belong in the application's `config/RouterConfig.json`.

Relevant codec properties are:

```text
router_specs.codec.password_required
router_specs.codec.device_key_required
```

Password files and binary device-key files are handled separately.

Fixed-key methods use their supported parameters from the specification.

A missing required credential prevents the corresponding processing operation.

## Supplied Router Profiles

| Router | Model | Processing |
|---|---|---|
| Spark SmartModem | VRV9517 | Legacy OpenSSL AES-256-CBC, Base64, line wrapper, TAR/GZIP |
| Vodafone Huawei HG659 | HG659 | Fixed-key AES-256-CBC, RSA/MD5, signed zlib |
| Vodafone Ultra Hub | DGA0130VDF | Technicolor THENC format and device-key specification |

### Spark SmartModem VRV9517

Supports:

- Password-based backup decryption and encryption.
- Base64 and line-wrapper processing.
- TAR/GZIP archive extraction and reconstruction.
- Key-value configuration viewing and editing.
- Local backup verification.

### Vodafone Huawei HG659

Supports:

- Fixed-key AES-256-CBC encryption and decryption.
- Signed zlib processing.
- RSA/MD5 signature verification and signing.
- XML configuration viewing and editing.
- AES-128-CBC protection of supported Wi-Fi password fields.
- Local backup verification.

### Vodafone Ultra Hub DGA0130VDF

The specification declares the Technicolor THENC wrapper and device-key encryption requirements.

THENC parsing and relevant validation are implemented.

Complete THENC decryption, encryption, authentication, and signing are not implemented because the required cryptographic processing is not established.

Providing a device-key file alone does not make complete THENC processing available.

The configuration editing format is not established.

## Adding Another Router Model

1. Copy `doc/RouterSpecificationTemplate.json`.
2. Enter the router model, firmware, and hardware information.
3. Configure the codec properties for its backup format.
4. Define the correct encode and decode operation order.
5. Supply encoding-only parameters or set `encode` to `null`.
6. Define editing settings or set `edit` to `null`.
7. Map supported configuration fields in `config_fields`.
8. Validate the specification against `schemas/RouterSchema.json`.
9. Add the router and its paths to `config/RouterConfig.json`.
10. Configure any required credential files.
11. Test the supported processing workflows.

A new router using existing registered methods generally requires only a model specification and application configuration entry.

A new encryption algorithm, wrapper, archive format, or configuration mechanism requires an implementation in the appropriate utility module and registration in `ROUTER_FUNCTIONS`.

## Related Files

| File | Purpose |
|---|---|
| `schemas/RouterSchema.json` | Specification validation schema |
| `doc/RouterSpecificationTemplate.json` | Starting specification |
| `constants/RouterConstants.py` | Operation registry and pipelines |
| `config/RouterConfig.json` | Application configuration |
| `modules/router_utils.py` | Operation builders, dispatcher, and supporting functions |
| `modules/router_encryption_utils.py` | Encryption and signature processing |
| `modules/router_format_utils.py` | Backup format processing |
| `modules/router_config_utils.py` | Configuration viewing and editing |

Successful local processing and verification do not guarantee that physical router firmware will accept a generated backup.