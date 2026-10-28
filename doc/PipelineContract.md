# Pipeline execution contract

Each step is a dictionary with `fn` (callable), `phase` (`pre` or `exec`),
`args` (list of argument specifications), `result` (nonempty context key other
than `steps`), and optional `when`. There are no `success_key` overrides or
synthetic status callbacks. Both loaders import the same implementation from
their repository's `modules/state_machine_utils.py`; neither repository needs
the other at runtime.

Argument and condition callables receive `(job, meta, ctx)`. TestingTools uses
`job=None`; AutomationTools uses the selected group name. Existing string
argument resolution remains: context key first, configuration key second,
`job` for the job name, otherwise the literal string. Use callables for
unambiguous context lookups or literal strings that could collide with keys.

## State and dependencies

The loader creates a fresh context for every selected action. AutomationTools
keeps a separate context at `runtime_ctx["groups"][group_name]` for each group.
The same context spans the pre and exec phases. Direct runner callers must
provide a fresh context for each new run; calling another phase continues the
current run.

Successful returns live at `ctx[step["result"]]`, unchanged, including `None`,
`False`, zero and empty containers. Failure or skipping never overwrites a
previous return. `ctx["steps"]` is the only execution history/error store:

```python
{
    "driver": driver,
    "steps": [
        {"step": "open_chrome", "phase": "exec", "status": "success",
         "result_key": "driver"},
        {"step": "discover_urls", "phase": "exec", "status": "failed",
         "result_key": "urls", "error": "Discovery failed",
         "error_type": "RuntimeError"},
    ],
}
```

History contains one entry per invocation, including repeated functions.
Entries start `pending`, become `running` during argument resolution and the
call, then `success` or `failed`. A false condition produces `skipped` with a
reason. Condition exceptions produce `failed`. `result_key` identifies the
configured destination; only `success` means this invocation stored a return.
History never contains a copy of the return or the exception object.

Dependencies use `when`, usually with `result_available(ctx, "input_key")`.
This helper checks presence and the latest completed producer's status. A
successful false/empty/None value is available; an application condition can
add stricter checks. After a failed or skipped retry, an old successful value
remains readable but is unavailable to dependent steps. Explicitly seeded
context inputs without a history entry are accepted. Optional crawl merge
inputs intentionally use defaults so successful partial results can still be
combined after another crawler fails.

## Failure and phases

Both phases continue after individual exceptions. Eligible independent steps
and unconditional exec cleanup still execute. Overall execution succeeds when
history contains no failed steps; return truthiness and skipped steps do not
change execution status. Application outcomes remain available in result keys.

Pre steps run before planning/confirmation. After all pre steps finish, any pre
exception returns the loader to its menu, blocking the exec phase. Thus exec
cleanup is guaranteed after exec failures, not after a rejected pre phase.
Pre steps should not acquire resources requiring exec cleanup. Exec steps run
after confirmation; failures do not prevent later eligible steps or groups.
Run-all pipelines add prerequisite conditions where standalone actions may
legitimately operate on files or services from earlier application runs.

## Verification

Run independently in each repository:

```sh
python3 -m unittest discover -s tests -v
```

Tests cover actual/falsy returns, all statuses, condition and argument errors,
failed retries, dependency skipping, independent steps, cleanup, repeated calls,
phase behavior, loader pre gating, fresh action state, and every configured
pipeline's contract and phase scheduling. AutomationTools additionally exercises
real ISO/text config argument resolution with mocked utility calls and run-all
prerequisite failure. Its fixtures use no external services. The corresponding
AutomationTools-only fixture test is skipped in TestingTools.

No live browser, Docker, device, email or router operations are run by these tests.

## Separate follow-up work

Some business functions catch their own exceptions and return `False` or result
rows describing failure. The runner faithfully records these as successfully
returned values; interpreting those domain outcomes belongs to their callers
and conditions. A later utility-by-utility refactor can standardize that behavior.
The repository-local execution implementations are intentionally identical;
changes should be applied and tested in both repositories. Cancellation or
resource acquisition requiring try/finally across phases would require a
separate lifecycle design.

## Files changed for this task

AutomationTools:

- `AutomationLoader.py`
- `modules/state_machine_utils.py`
- `constants/FunctionConstants.py`
- `constants/RouterConstants.py`
- `constants/TextCreatorConstants.py`
- `constants/UbuntuISOEditorConstants.py`
- `constants/WebCrawlerConstants.py`
- `tests/test_pipeline_contract.py`
- `doc/PipelineContract.md`

TestingTools:

- `ToolLoader.py`
- `modules/state_machine_utils.py`
- `constants/DataRecoveryConstants.py`
- `constants/DiagnosticConstants.py`
- `constants/EmailConstants.py`
- `constants/FileIntegrityConstants.py`
- `constants/FunctionConstants.py`
- `constants/HardDriveConstants.py`
- `constants/NetworkConstants.py`
- `constants/RouterConstants.py`
- `constants/WiFiConstants.py`
- `constants/WindowsInspectionConstants.py`
- `tests/test_pipeline_contract.py`
- `doc/PipelineContract.md`
