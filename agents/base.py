"""
ORCA — agents/base.py (NEW)

Every specialized agent (weather, ocean analytics, geo/risk, route, viz,
reporting) is a thin tool-calling wrapper per the build spec's integration
principle: it receives a structured sub-task from the Planner, calls into
existing WaveSafe/ORCA service functions, and returns a small JSON object
shaped {data, explanation, sources}. This file defines that contract once so
every agent file returns a consistent shape instead of inventing its own.

No business logic lives here or in any agents/*.py file — only argument
marshalling into the already-built service layer (zone_service,
geofence_service, safe_harbor_service, risk_engine, route_optimizer) and
shaping the result into AgentResult.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AgentResult:
    data: dict[str, Any]
    explanation: list[str] = field(default_factory=list)  # human-readable reasoning steps, surfaced by the Reporting agent
    sources: list[str] = field(default_factory=list)        # which data sources/services backed this result, for citation

    def to_dict(self) -> dict:
        return {"data": self.data, "explanation": self.explanation, "sources": self.sources}


@dataclass
class ToolSpec:
    """One entry in an agent's tool registry — mirrors the Anthropic Messages
    API's `tools` param shape (name/description/input_schema) so the
    Planner agent can pass agents' registries straight through to the
    tool-use loop without a translation layer."""
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., AgentResult]

    def to_api_tool(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}

    def to_openai_tool(self) -> dict:
        """Same tool spec, shaped for OpenAI-compatible tool calling (Groq,
        OpenAI, etc.) — {"type": "function", "function": {name, description,
        parameters}} instead of Anthropic's flat {name, description,
        input_schema}."""
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.input_schema,
        }}


class ToolRegistry:
    """Collects one agent's ToolSpecs and dispatches by name — used both by
    the Planner (to build the `tools` list for the Anthropic API call) and
    by chat.py (to execute whichever tool_use block Claude returns)."""

    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"duplicate tool name registered: {spec.name}")
        self._tools[spec.name] = spec

    def as_api_tools(self) -> list[dict]:
        return [t.to_api_tool() for t in self._tools.values()]

    def as_openai_tools(self) -> list[dict]:
        return [t.to_openai_tool() for t in self._tools.values()]

    def dispatch(self, tool_name: str, tool_input: dict, **ctx) -> AgentResult:
        spec = self._tools.get(tool_name)
        if spec is None:
            return AgentResult(data={"error": f"unknown tool: {tool_name}"}, explanation=[], sources=[])
        return spec.handler(**tool_input, **ctx)

    def merge(self, other: "ToolRegistry") -> "ToolRegistry":
        merged = ToolRegistry()
        merged._tools = {**self._tools, **other._tools}
        return merged
