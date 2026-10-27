# Router Model Specifications

Router model specifications describe the settings used to decode, inspect, edit, and encode router configuration backups. Each supported router has a JSON specification, allowing the shared processing functions to work with different backup formats without model-specific logic.

## Specification structure

Every specification contains exactly two top-level properties:

| Property | Description |
|---|---|
| `router_specs` | Router identity and supported backup processing settings |
| `config_fields` | Logical field names mapped to configuration keys or selectors |

The `router_specs` object contains the router identity and the following sections as applicable:

| Section | Description |
|---|---|
| `codec` | Shared decoding and encoding settings |
| `encode` | Additional parameters required only for encoding |
| `edit` | Configuration editing settings, where supported |

Omit unused optional sections and settings rather than adding `null` placeholders. The exception is an existing `config_fields` mapping whose `path` is `null` because the field location is unknown.

### Example

This example illustrates the structure and field mappings. It is **not** a complete working specification; required `codec` properties and identity fields depend on the router and the shared schema.

```json
{
  "router_specs": {
    "codec": {},
    "edit": {
      "configuration_file": "config.xml"
    }
  },
  "config_fields": [
    {
      "name": "wifi_ssid",
      "path": "Wireless|Name=Main|SSID"
    },
    {
      "name": "wifi_password",
      "path": "Wireless|Name=Main|Password"
    }
  ]
}
```

The example selectors are illustrative. Use the actual paths found in the router's decoded configuration. For a complete starting specification, see `doc/RouterSpecificationTemplate.json`.

## Codec settings

`router_specs.codec` defines the shared mechanisms and parameters for decoding and encoding a backup. Depending on the router, these include:

- Encryption algorithms, keys, and initialization vectors (IVs)
- Password derivation parameters
- Backup wrappers, headers, trailers, and random prefixes
- Checksum locations and line lengths
- Compression and archive formats
- Signature verification parameters
- Decode and encode operation order

Wrapper parameters are shared: decoding checks the same checksum location, line length, random prefix, and trailer that encoding writes. These parameters are flat properties of `codec`.

Keys, IVs, and public signature parameters are included only for methods that require them.

The supported archive methods used by the supplied profiles are `tar.gz` and `signed-zlib`.

The supplied profiles use default processing orders. Where necessary, specify independent orders with:

```text
router_specs.codec.decode_order
router_specs.codec.encode_order
```

## Encoding settings

Use `router_specs.encode` only for encoding-specific parameters that are not shared with decoding.

The Vodafone Huawei HG659 profile includes:

```text
router_specs.encode.private_exponent_hex
```

This is the private exponent used by its supported signing process. Public signature parameters remain in `codec` where required.

## Editing settings

Use `router_specs.edit` only when the decoded configuration format and editing mechanism are established.

The configuration file to edit is specified by:

```text
router_specs.edit.configuration_file
```

Protected fields are listed under:

```text
router_specs.edit.field_encryption.fields
```

## Configuration field mappings

`config_fields` is a list of mappings between a logical name and a key or selector in the decoded configuration.

Each entry has this form:

```json
{
  "name": "logical_name",
  "path": "actual_key_or_selector"
}
```

For example, an XML-backed configuration might use:

```json
{
  "config_fields": [
    {
      "name": "wifi_ssid",
      "path": "Wireless|Name=Main|SSID"
    },
    {
      "name": "wifi_password",
      "path": "Wireless|Name=Main|Password"
    }
  ]
}
```

These paths are examples, not confirmed selectors for any supplied router model.

Supported XML selector forms include:

| Form | Purpose |
|---|---|
| `element\|filter=value\|attribute` | Find an element by a filter and select an attribute |
| `child@attribute` | Select an attribute on a child element |

Add mappings as needed without changing Python processing functions. Some existing Ultra Hub mappings have a `null` path because the corresponding configuration location is not yet known; these fields are not currently editable.

## Supplied router profiles

| Router | Specification sections | Notes |
|---|---|---|
| Spark SmartModem VRV9517 | `codec`, `edit` | Complete Spark-format example supplied in the template |
| Vodafone Huawei HG659 | `codec`, `encode`, `edit` | Includes `encode.private_exponent_hex` for signing |
| Vodafone Ultra Hub | `codec` | Configuration format and required cryptographic mechanisms are not fully established |

Supported operations depend on the router model, firmware, and available cryptographic material. A successful local encode/decode round trip does not establish compatibility with every hardware or firmware revision.

## Adding a router model

1. Copy `doc/RouterSpecificationTemplate.json` as a starting point.
2. Set the router identity and supply the required `router_specs.codec` properties for its backup format.
3. Add `router_specs.encode` only if the encoding process requires additional parameters.
4. Add `router_specs.edit` only if configuration editing is supported; specify the configuration file and any protected fields.
5. Add the required `config_fields` name/path mappings using keys or selectors from the decoded configuration.
6. Omit unused optional sections and properties.
7. Validate the specification with `load_router_model_specs(spec_path, schema_path)` using `schemas/RouterSchema.json`.
8. Add the router entry and file paths to the application's `config/RouterConfig.json`, including input and credential files where required.
9. Test the supported decode, inspect, edit, encode, and verification operations.

`RouterSchema.json` uses JSON Schema Draft 2020-12. Required implementation parameters and compatible format combinations are also checked in Python.

A router using already-supported processing methods requires a new specification and application configuration entry, not changes to the Python processing functions.

## Related files

| File | Purpose |
|---|---|
| `doc/RouterSpecificationTemplate.json` | Complete Spark-format specification example |
| `schemas/RouterSchema.json` | Shared specification validation schema |
| `config/RouterConfig.json` | Application router entries and input/output paths |
