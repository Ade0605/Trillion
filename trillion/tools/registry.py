"""
Tool registry. Register tools here; agent.py calls them by name.
Adding a new capability = write one file + call register() here.
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    fn: Callable
    requires_confirmation: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._config = self._load_config()

    def _load_config(self) -> dict:
        cfg_path = Path(__file__).parent.parent.parent / "config.yml"
        with open(cfg_path) as f:
            return yaml.safe_load(f)

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict,
        fn: Callable,
        requires_confirmation: bool = False,
    ) -> None:
        gate_list = self._config.get("confirmation_required_tools", [])
        needs_gate = requires_confirmation or (name in gate_list)
        self._tools[name] = Tool(name, description, input_schema, fn, needs_gate)

    def as_anthropic_tools(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    def needs_confirmation(self, name: str) -> bool:
        tool = self._tools.get(name)
        return bool(tool and tool.requires_confirmation)

    def run(self, name: str, inputs: dict, skip_confirm: bool = False) -> str:
        from trillion import audit

        # Kill switch: halt every tool call mid-incident (no restart needed).
        try:
            from trillion.security import kill_switch
            if kill_switch.is_active():
                audit.log("kill_switch_block", tool=name)
                return kill_switch.blocked_response(name)
        except Exception:
            pass

        # Anomaly cap: block a runaway loop before it lands its 50th call.
        try:
            from trillion.security import anomaly
            allowed, info = anomaly.check_and_record(name)
            if not allowed:
                audit.log("anomaly_gate_blocked", **info)
                return anomaly.blocked_message(info)
        except Exception:
            pass

        tool = self._tools.get(name)
        if tool is None:
            msg = f"Unknown tool '{name}'. Available: {', '.join(self._tools)}"
            audit.log_error(f"tool_lookup:{name}", msg)
            return msg

        confirmed: bool | None = None
        if tool.requires_confirmation and not skip_confirm:
            confirmed = self._confirm(name, inputs)
            audit.log_confirmation(name, confirmed)
            if not confirmed:
                return f"Action '{name}' was cancelled by the user."

        try:
            result = tool.fn(**inputs)
            result_str = str(result) if result is not None else "Done."
            audit.log_tool(name, inputs, result_str, confirmed)
            return result_str
        except TypeError as e:
            err = f"Tool '{name}' received unexpected arguments: {e}"
            audit.log_error(f"tool_run:{name}", err)
            return err
        except Exception:
            err = f"Tool '{name}' failed: {traceback.format_exc(limit=3)}"
            audit.log_error(f"tool_run:{name}", err)
            return err

    def _confirm(self, name: str, inputs: dict) -> bool:
        print(f"\n[Trillion] About to run '{name}'")
        if inputs:
            for k, v in inputs.items():
                print(f"  {k}: {v}")
        resp = input("  Proceed? (y/n) > ").strip().lower()
        return resp == "y"

    def __len__(self) -> int:
        return len(self._tools)


def build_registry() -> ToolRegistry:
    """Instantiate registry and register all tools."""
    from .reminders import register_reminders
    from .notes import register_notes
    from .draft import register_draft
    from .web_search import register_web_search

    r = ToolRegistry()
    register_reminders(r)
    register_notes(r)
    register_draft(r)
    register_web_search(r)
    try:
        from trillion.design.tool import register_design_tools
        register_design_tools(r)
    except Exception:
        pass  # design agent optional; never break core tools
    try:
        from trillion.factory.tool import register_factory_tools
        register_factory_tools(r)
    except Exception:
        pass  # agent factory optional; never break core tools
    return r
