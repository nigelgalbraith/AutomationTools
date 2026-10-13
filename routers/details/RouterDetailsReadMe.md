# Router Details Configuration

Router details tell AutomationLoader which settings to change when creating a router configuration backup.

Each router has its own JSON details file, allowing multiple configurations to be created from the same router model and template.

## Adding Router Details

1. Create a JSON file containing the settings you want to change.
2. Add the file location to `router_details_path` in `config/RouterConfig.json`.
3. Ensure each setting has a corresponding mapping in the router model specifications' `config_fields`.
4. Run the router automation to apply the settings.

## Router Details JSON

Example filename: `router_two_details.json`

```json
{
    "wifi_2g_ssid": "RouterTwo_2G",
    "wifi_2g_password": "password123",
    "wifi_5g_ssid": "RouterTwo_5G",
    "wifi_5g_password": "password456"
}
```

Each entry consists of a setting name and the value to apply.

The JSON can be extended with additional settings as required.

## Configuration Field Mapping

Each setting in the router details JSON must match an entry in the model specifications' `config_fields`.

For example:

```json
"config_fields": {
    "file": "config/.glbcfg",
    "wifi_2g_ssid": "ARC_WLAN_24G_SSID_0_ESSID",
    "wifi_2g_password": "ARC_WLAN_24G_SSID_0_WPA_Passphrase",
    "wifi_5g_ssid": "ARC_WLAN_5G_SSID_0_ESSID",
    "wifi_5g_password": "ARC_WLAN_5G_SSID_0_WPA_Passphrase"
}
```

The left-hand names identify the settings used in the router details JSON.

The right-hand values identify the actual configuration keys inside the router backup.

The `file` entry specifies the configuration file inside the decoded archive and must not be included in the router details JSON.

## Adding Additional Settings

To change additional router settings:

1. Decode an existing router configuration.
2. Identify the actual setting key in the decoded configuration file.
3. Add a mapping for that key in the model specifications' `config_fields`.
4. Add the corresponding setting and replacement value to the router details JSON.
5. Run the automation and verify the edited configuration.

For example, to add a primary DNS setting:

**Model specifications:**

```json
"dns_primary": "ACTUAL_ROUTER_DNS_KEY"
```

**Router details:**

```json
"dns_primary": "1.1.1.1"
```

Replace `ACTUAL_ROUTER_DNS_KEY` with the actual key found in the decoded configuration.

Additional ordinary key-value settings do not require changes to Python code.

## Configuration Behaviour

- Only settings provided in the router details JSON are updated.
- Settings not included in the JSON remain unchanged.
- Unknown settings cause validation errors.
- Missing configuration fields cause errors.
- All configuration values are loaded automatically from JSON.
- No manual setting entry is required.
- Existing output files and directories are not overwritten.
- The original router template remains unchanged.

## Viewing Router Details

AutomationLoader provides options to view:

- Router Details — Displays the replacement values from the router details JSON.
- Decoded Router Configuration — Displays the original configuration values.
- Edited Router Configuration — Displays the values after changes have been applied.

Use these options to verify that the correct settings have been applied before restoring the generated backup.

## Important Notes

- Keep a separate router details JSON for each configuration.
- Ensure all setting names match the model specifications.
- Use valid JSON syntax with correctly quoted keys and string values.
- Do not include settings that you do not want changed.
- Passwords and other credentials are displayed in full by the explicit view actions.
- Protect JSON files containing passwords with appropriate filesystem permissions.
- Verify the generated router configuration before deploying it.

**New configuration → Create a new router details JSON and reference it in RouterConfig.json.**

**New supported setting → Add the mapping to `config_fields` and the value to the router details JSON.**

**No Python changes are required for ordinary supported key-value settings.**
