# Router schema consolidation

## LOAD → CHECK → PLAN → EXECUTE

Both projects' router constants now define these consecutive PRE operations:

1. LOAD: load_router_model_specs reads the dictionary once.
2. CHECK: validate_json_schema receives the dictionary, the constants-defined
   ROUTER_SCHEMA_PATH string and a model label directly.
3. PLAN preparation: prepare_xml_selectors parses the schema-checked selectors
   into the existing _xml_selectors dictionary before plan display or execution.
4. The existing loader builds/displays the execution plan when configured and
   runs the selected operation. Actions that already skip plan display still
   prepare selectors before execution.

TestingTools applies this order to both source and destination/migration models.
AutomationTools applies it within its existing grouped workflow. PRE exceptions
stop before planning/execution. No additional states or iteration framework were
introduced. Each project retains its own identical RouterSchema.json and shared
json_utils validator implementation, so neither project depends on the other.

## Declarative rules

The schema already defined required keys, types, supported encryption/derivation,
backup/configuration formats, key/IV hexadecimal widths and conditional settings.
Those rules remain. This consolidation adds:

- Configuration paths: reject absolute paths, .. path components, empty/whitespace
  paths and embedded newline/null characters.
- XML selector grammar: element|filter=value[|...]|attribute, optionally with a
  child@attribute target; require valid names and populated filter values.
- RSA modulus: hexadecimal representation, existing 128–2048 character bounds,
  at least 512 significant bits and oddness, including leading-zero forms.
  Although general arithmetic is unavailable in standard JSON Schema, these
  specific properties are expressible as hexadecimal patterns: significant
  length/first digit determines bit length, and the last digit determines parity.
- Private exponent: retain null for decode-only specifications; otherwise require
  nonempty hexadecimal text and reject numeric zero/one including leading zeros.
  No arbitrary minimum RSA private-exponent bit length was imposed: the existing
  supported rule is a number greater than one and smaller than the modulus.

All three existing model specifications in each project continue to pass.

## Checks outside JSON Schema

These remain targeted checks at their point of use, rather than another general
router configuration validator:

- sign_rsa_md5_configuration: require the private exponent for signing and check
  1 < exponent < modulus before exponentiation. A public-key-only spec can decode.
- sign_rsa_md5_configuration and verify_rsa_md5_signature: compare configured
  signature size with the actual modulus size before constructing/recovering the
  signature block. JSON Schema cannot compare these computed values.
- parse_key_value_fields: reject duplicate mapping values across separately
  named labels before using fields. JSON Schema uniqueItems does not apply to
  values of separate object properties.
- parse_xml_field_selector during PLAN preparation: reject duplicate filter names
  before constructing the filter dictionary, avoiding silently overwritten filters.
- safe_relative and existing filesystem/archive checks: retain normalized path,
  traversal, symlink and archive-member safety at filesystem operations. Editing
  now uses safe_relative for its configured file path as well.

Runtime checks on credentials, ciphertext alignment, salted headers, Base64,
checksums, RSA integrity, compression, XML contents, archive safety, allowed edits
and filesystem operations remain. Encryption algorithms and backup formats did
not change. No actual backups were modified.

## Removed duplication and reporting

Removed validate_model_specs from both projects, its constants imports and its
pipeline calls. No replacement general-purpose validator exists. Removed its
schema-success reporting and the shared validator's report_success deferral flag.
The shared validate_json_schema now owns all schema [OK]/[FAILED] messages and
returns its original input unchanged. XML parsing no longer repeats the syntax
rules that CHECK enforces. Preparation only derives selectors and checks filter
ambiguity; it does not emit schema-validation messages. A preparation or crypto
failure reports its actual error, separately from a successful schema check.

Email search pipeline definitions and processing were not changed by this task.
Its use of the shared validator retains the same messages and behavior.

## Files changed for this consolidation

In both projects:

- schemas/RouterSchema.json
- constants/RouterConstants.py
- modules/json_utils.py
- modules/router_utils.py
- modules/router_config_utils.py
- modules/router_encryption_utils.py
- tests/test_router_load_validation.py
- tests/test_pipeline_validation.py

Additionally:

- TestingTools/tests/test_validation_cleanup.py
- AutomationTools/doc/AlignmentNotes.md

## Verification and limitations

- TestingTools: python3 -m unittest discover -s tests -q — 41 passed.
- AutomationTools: python3 -m unittest discover -s tests -q — 44 passed.
- Compilation and each project's router CLI help passed.

Tests cover declarative encryption/key/IV/format rules, unsafe paths, selector
syntax, RSA significant length/parity and private-exponent text; direct pipeline
LOAD/CHECK/preparation ordering; one validation per operation; removed general
validator; selector preparation only once; RSA range/size failures at crypto use;
duplicate mappings/filters; real fixed-key and legacy round trips; corrupt and
malicious backup rejection; email behavior and AutomationTools grouped workflows.

No Git operations, hardware access, package installation or live crawler/browser
services were used. THENC device-key handling/signing remains unavailable as
before. Direct low-level processing callers must supply schema-checked settings;
there is no new provenance wrapper or generic validation layer.
