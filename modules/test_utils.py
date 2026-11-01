
from __future__ import annotations

from pathlib import Path
import importlib.util

from modules.display_utils import print_dict_table


# ---------------------------------------------------------------------
# PIPELINE LOADING
# ---------------------------------------------------------------------

def load_test_pipelines(job: str, tests: list[dict]) -> dict:
    """Load selected pipeline definitions from a constants file."""
    path = Path(job).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Constants file not found: {path}")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    available = module.PIPELINE_STATES
    selected = {}
    for test in tests:
        name = test["pipeline"]
        if name not in available:
            raise ValueError(f"{path.name}: pipeline {name!r} not found")
        selected[name] = available[name]
    print(f"[OK] Loaded {len(selected)} pipelines from {path}")
    return selected


# ---------------------------------------------------------------------
# PIPELINE VALIDATION
# ---------------------------------------------------------------------

def check_pipeline_structure(pipelines: dict) -> bool:
    """Validate pipeline functions, phases, arguments, results and dependencies."""
    all_ok = True
    summary = []
    for name, state in pipelines.items():
        rows = []
        results = set()
        pipeline_ok = True
        steps = state.get("pipeline")
        if not isinstance(steps, list) or not steps:
            rows.append({
                "Function": "PIPELINE",
                "When": "-",
                "Result": "-",
                "Status": "FAIL",
            })
            pipeline_ok = False
        else:
            for step in steps:
                config = step if isinstance(step, dict) else {}
                fn = config.get("fn")
                action_name = getattr(fn, "__name__", str(fn))
                condition = config.get("when")
                result = config.get("result")
                phase = config.get("phase")
                args = config.get("args")
                conditions = condition if isinstance(condition, list) else [condition]
                dependency_ok = all(
                    part is None
                    or callable(part)
                    or (
                        isinstance(part, str)
                        and any(
                            option.strip() in results
                            or option.strip() in ("job", "meta")
                            or option.strip().startswith("meta.")
                            for option in part.split(" or ")
                        )
                    )
                    for part in conditions
                )
                step_ok = (
                    callable(fn)
                    and phase in ("pre", "exec")
                    and isinstance(args, list)
                    and isinstance(result, str)
                    and bool(result)
                    and result != "steps"
                    and dependency_ok
                )
                if not step_ok:
                    pipeline_ok = False
                rows.append({
                    "Function": action_name,
                    "When": str(condition) if condition is not None else "-",
                    "Result": result or "-",
                    "Status": "PASS" if step_ok else "FAIL",
                })
                if isinstance(result, str) and result and result != "steps":
                    results.add(result)
        print_dict_table(
            rows,
            ["Function", "When", "Result", "Status"],
            f"{name} Pipeline Validation",
        )
        summary.append({
            "Pipeline": name,
            "Status": "PASS" if pipeline_ok else "FAIL",
        })
        if not pipeline_ok:
            all_ok = False
    print_dict_table(
        summary,
        ["Pipeline", "Status"],
        "Pipeline Validation Summary",
    )
    passed = sum(row["Status"] == "PASS" for row in summary)
    print(f"[SUMMARY] Passed: {passed}, Failed: {len(summary) - passed}")
    if not all_ok or not summary:
        raise ValueError("Pipeline structural validation failed")
    return True


