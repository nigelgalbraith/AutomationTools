#!/usr/bin/env python3
"""
state_machine_utils.py

Small utilities used by the installer state machine: constants loading, CLI parsing,
argument resolution, and step conditions.
"""

from __future__ import annotations

import argparse
import importlib
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------
# COMMAND LINE ARGUMENTS
# ---------------------------------------------------------------------

def load_constants_from_module(module_path: str, required: list[str]):
    """Import a constants module and return a namespace-like object of uppercase attributes"""
    mod = importlib.import_module(module_path)
    consts = {name: getattr(mod, name) for name in dir(mod) if name.isupper()}
    missing = [n for n in required if n not in consts]
    if missing:
        raise SystemExit(
            f"[FATAL] Constants module '{module_path}' is missing: {', '.join(missing)}",
        )
    return type("Constants", (), consts)()


def parse_args_early() -> argparse.Namespace:
    """Parse only the --constants flag early, before full constants-dependent parsing"""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--constants", help="Python module path for constants (e.g. constants.DebConstants)")
    return p.parse_known_args()[0]


def parse_args(consts: Any) -> argparse.Namespace:
    """Parse CLI flags for non-interactive state machine operation"""
    p = argparse.ArgumentParser(description="Installer state machine")
    p.add_argument("--yes", "-y", action="store_true", help="Auto-confirm prompts (non-interactive).")
    action_choices = [k for k in consts.ACTIONS.keys() if k != "_meta"]
    if "Cancel" in action_choices:
        action_choices = [c for c in action_choices if c != "Cancel"] + ["Cancel"]
    p.add_argument(
        "--action", choices=action_choices,
        help="Action to perform non-interactively.",
    )
    p.add_argument("--targets", help="Comma-separated list of job names to operate on (used with --action).")
    p.add_argument("--status", action="store_true", help="Status-only: show installed/uninstalled summary and exit.")
    p.add_argument("--plan-only", action="store_true", help="Print the execution plan and exit without making changes.")
    p.add_argument(
        "--constants", default="constants.DebConstants",
        help="Python module path for constants (e.g. constants.DebConstants)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------
# ARGUMENT RESOLUTION AND CONDITIONS
# ---------------------------------------------------------------------

def resolve_arg(spec: Any, job: str, meta: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
    """Resolve a pipeline arg spec into a concrete value"""
    if callable(spec):
        return spec(job, meta, ctx)
    if isinstance(spec, str):
        if spec in ctx:
            return ctx[spec]
        key = spec.split(".", 1)[-1]
        if key in meta:
            return meta[key]
        if spec == "job":
            return job
    return spec


def check_when(cond: Any, job: str, meta: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
    """Evaluate a step's `when` condition and return True if the step should run"""
    if cond is None:
        return True
    if callable(cond):
        return bool(cond(job, meta, ctx))
    return bool(resolve_arg(cond, job, meta, ctx))


def result_available(ctx: Dict[str, Any], *keys: str) -> bool:
    """Require stored inputs whose latest completed producer succeeded.

    False, None and empty containers are available values. A failed/skipped
    retry invalidates a dependency without destroying an earlier good value.
    Seed values without a producer in this run are also accepted.
    """
    for key in keys:
        if key not in ctx:
            return False
        latest = next((s for s in reversed(ctx.get("steps", []))
                       if s.get("result_key") == key
                       and s["status"] in ("success", "failed", "skipped")), None)
        if latest is not None and latest["status"] != "success":
            return False
    return True


def run_pipeline_steps(
    job: Optional[str], meta: Dict[str, Any], pipeline: List[Dict[str, Any]],
    *, phase: str, label: str, ctx: Dict[str, Any],
) -> bool:
    """Execute one phase; ctx belongs to one run and is shared across phases.

    Both phases continue after exceptions. Loaders block confirmation after pre
    errors; exec always finishes eligible independent and cleanup steps. Only
    exceptions mean execution failure; return-value truthiness is never status.
    """
    if phase not in ("pre", "exec"):
        raise ValueError(f"Unknown pipeline phase: {phase!r}")
    for step in pipeline:
        if step.get("phase") not in ("pre", "exec"):
            raise ValueError("Every pipeline step requires phase pre or exec.")
    history = ctx.setdefault("steps", [])
    scheduled = []
    for step in pipeline:
        if step.get("phase") != phase:
            continue
        entry = {"step": getattr(step.get("fn"), "__name__", "pipeline step"),
                 "phase": phase, "status": "pending",
                 "result_key": step.get("result")}
        history.append(entry)
        scheduled.append((step, entry))
    for step, entry in scheduled:
        try:
            fn = step["fn"]
            if not callable(fn):
                raise TypeError("Pipeline step requires callable 'fn'.")
            if not isinstance(step["args"], list):
                raise TypeError("Pipeline step 'args' must be a list.")
            key = step["result"]
            if not isinstance(key, str) or not key or key == "steps":
                raise ValueError("Pipeline step requires a non-reserved result key.")
            if not check_when(step.get("when"), job, meta, ctx):
                entry.update(status="skipped", reason="when condition was false (dependency unavailable or condition unmet)")
                continue
            entry["status"] = "running"
            args = [resolve_arg(a, job, meta, ctx) for a in step["args"]]
            value = fn(*args)
            ctx[key] = value
            entry["status"] = "success"
        except Exception as exc:
            message = (f"File not found: {exc.filename}"
                       if isinstance(exc, FileNotFoundError) and exc.filename else str(exc))
            entry.update(status="failed", error=message, error_type=type(exc).__name__)
            if not getattr(exc, "reported", False):
                print(f"[ERROR] {entry['step']} failed → {message}")
    success = not any(s["status"] == "failed" for s in history)
    suffix = " (pre)" if phase == "pre" else ""
    print(f"{label}{suffix}: {'Success' if success else 'Failed'}")
    return success
