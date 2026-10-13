# Router Model Specifications

Router model specifications tell AutomationLoader how to decode, edit and encode router configuration backups.

Each supported router model requires its own JSON specification.

## Adding a Router Model

1. Export a configuration backup from the router.
2. Copy an existing router model specification JSON.
3. Update the model, firmware, hardware and encryption settings.
4. Create a `.txt` file containing the factory password of the router used to create the master template.
5. Set `template_router_password_path` to that file and `target_router_password_path` to the target router password file.
6. Configure the fields you want to view or edit.
7. Set `model_specs_path` to the model JSON file.
8. Set `template_config_path` to the original backup file.
9. Test decoding, editing, encoding and restoring.

## Model Specification Settings

| Setting | Description |
|---|---|
| `model` | Router model name |
| `firmware` | Firmware version |
| `hardware` | Hardware revision |
| `encryption` | Encryption algorithm |
| `encoding` | Encrypted data encoding |
| `salted` | Whether OpenSSL salt is used |
| `password_required` | Whether the encryption mechanism requires a password |
| `password_base` | Prefix used when deriving the encryption passphrase |
| `password_hash` | Hashing method applied to the router password |
| `key_derivation` | Encryption key and IV derivation method |
| `key_derivation_digest` | Digest used for key derivation |
| `backup_format` | Backup wrapper and checksum structure |
| `archive` | Internal archive format and compression |
| `configuration_format` | Configuration file syntax |
| `config_fields` | Configuration settings available for viewing and editing |

Use an existing model specification as a reference for the complete JSON structure.

## Template Router Passwords

The master template is created from one physical router of a particular model.

Its factory password is stored separately from the model specification in a plain-text `.txt` file.

For example:

**Filename:** `VRV9517.txt`

```text
FACTORY_PASSWORD_OF_TEMPLATE_ROUTER
```

The file contains only the password, without quotation marks or JSON formatting.

Set `template_router_password_path` and `target_router_password_path` to separate password files.

### Processing

AutomationLoader passes each selected group's paths from `config/RouterConfig.json` through `RouterConstants.py`.

1. Decode reads the template CFG and template password, saves the TAR.GZ, and extracts the decoded directory.
2. Edit loads `router_details_path`, maps each setting through `config_fields`, and saves an edited copy. Unspecified values remain unchanged; unknown or missing fields fail the operation.
3. Encode rebuilds the original archive with the edited files and encrypts it using the target password. The generated backup is decrypted locally to verify the result.

Run All performs validation followed by these three actions. No utility prompts are used.

## Configuration Locations

Each top-level group in `config/RouterConfig.json` contains these paths:

| Configuration Key | Purpose |
|---|---|
| `model_specs_path` | Model specification JSON file |
| `model_specs_readme_path` | Model documentation file |
| `template_config_path` | Original encrypted CFG file |
| `template_router_password_path` | Template password file |
| `target_router_password_path` | Target password file |
| `router_details_path` | JSON settings to apply |
| `decoded_config_archive_path` | New decoded TAR.GZ file |
| `decoded_config_path` | New extracted directory |
| `edited_config_path` | New edited directory |
| `encoded_config_path` | New encoded CFG file |

Paths support `~`. Relative paths use AutomationLoader's working directory. Filenames are taken directly from these paths; no suffixes are added. Existing outputs are rejected, and the original configuration is never overwritten.

## Adding Configuration Fields

The `config_fields` section determines which router settings are available in the View and Edit menus.

Each entry maps a display name to the corresponding key in the router's configuration file.

For example:

```json
"config_fields": {
    "file": "config/.glbcfg",
    "wifi_2g_ssid": "ARC_WLAN_24G_SSID_0_ESSID",
    "wifi_2g_password": "ARC_WLAN_24G_SSID_0_WPA_Passphrase"
}
```

The `file` entry identifies the configuration file inside the decoded archive.

Additional fields can be added by mapping their actual configuration keys and adding the corresponding label and value to the router details JSON. Python changes are not required.

## Important Notes

- Keep an unchanged copy of the original router backup.
- Each template password file must match the physical router used to create that template.
- Template passwords are stored separately from model specifications.
- Target router passwords are read from their configured files; explicit view actions display credentials in full.
- Ensure the router model, hardware revision and firmware are compatible.
- Different encryption or archive mechanisms may require additional reusable Python helpers.
- Successfully decoding and re-encoding a backup does not guarantee the target router will accept it.
- Test a generated configuration before deploying it to multiple routers.

**New router with supported mechanisms → Create a new model JSON and template password file.**

**New unsupported mechanism → Add a reusable Python helper.**
