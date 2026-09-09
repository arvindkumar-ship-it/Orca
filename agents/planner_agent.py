"""
ORCA — agents/planner_agent.py (NEW)

R1/R3/R10: the Orchestrator. Classifies intent, decomposes multi-part
queries, routes sub-tasks to specialist agents via a standard
OpenAI-compatible (Groq) tool-use loop, and reads/writes conversation
memory (session + turn history + resolved entities like "that beach"/
"my last query").

Design: every specialist agent (weather/ocean/geo_risk/route/viz) exposes a
ToolRegistry (agents/base.py). The Planner merges all of them into one
`tools` list for the chat completions call, then loops: call the model ->
if it returns tool_calls, dispatch each to the owning registry, feed
tool-result messages back -> repeat until the model returns a final text
response with no more tool calls. This is the standard agent-as-tool
pattern named in the tech stack (Section 1) — no custom control flow
invented beyond what the chat completions API's tool-use loop already
provides.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import json
import os
from groq import Groq

from sqlalchemy.orm import Session

from agents.base import AgentResult, ToolRegistry
from agents import weather_agent, ocean_analytics_agent, geo_risk_agent, route_agent, viz_agent

_MODEL = "openai/gpt-oss-120b"
_MAX_TOOL_LOOP_ITERATIONS = 8  # hard ceiling — a well-formed query resolves in 1-4 tool calls; this guards against a runaway loop, not normal usage
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client

_SYSTEM_PROMPT = (
    "You are the Planner agent for ORCA, a marine intelligence platform for "
    "Indian coastal stakeholders (fishermen, researchers, coastal "
    "authorities, maritime operators). Decompose the user's question into "
    "the minimum set of tool calls needed to answer it accurately. Call "
    "weather tools for wind/wave/tide/lightning/cyclone questions, ocean "
    "analytics tools for PFZ/SST/chlorophyll questions, geo/risk tools for "
    "safety-verdict and geofence/MPA/boundary questions, and route tools for "
    "navigation/route-planning questions. Use conversation history to "
    "resolve references like 'that zone' or 'my last query'. Once you have "
    "enough tool results to answer, stop calling tools and give a plain-text "
    "summary of what you found — the Reporting agent will phrase the final "
    "user-facing answer from your tool results, so your final text turn only "
    "needs to confirm you're done, not restate everything."
)


@dataclass
class PlannerTurnResult:
    agent_results: list[AgentResult] = field(default_factory=list)
    final_text: str = ""
    tool_call_log: list[dict] = field(default_factory=list)  # for audit/debugging — which tools were called with what args
    resolved_entities: dict = field(default_factory=dict)  # carried forward for "that zone"/"my last query" resolution


# Tool input keys that, when present in a dispatched call, become the new
# "last known" entity for reference resolution in later turns — this is
# the actual mechanism backing the system prompt's claim about resolving
# "that zone"/"my last query" (previously that claim wasn't backed by code).
_ENTITY_TRACKED_KEYS = {"zone_id": "last_zone_id", "lat": "last_lat", "lng": "last_lng",
                        "dest_lat": "last_dest_lat", "dest_lng": "last_dest_lng"}


def _build_merged_registry() -> ToolRegistry:
    reg = weather_agent.build_registry()
    reg = reg.merge(ocean_analytics_agent.build_registry())
    reg = reg.merge(geo_risk_agent.build_registry())
    reg = reg.merge(route_agent.build_registry())
    reg = reg.merge(viz_agent.build_registry())
    return reg


def run_planner_turn(db: Session, english_question: str, conversation_history: list[dict],
                      resolved_entities: dict | None = None) -> PlannerTurnResult:
    """conversation_history is a list of {role, content} dicts in Anthropic
    Messages API format — the caller (chat.py) is responsible for loading
    it from the conversation-memory store and appending this turn back to
    it after the call returns, keeping persistence out of this function so
    it stays a pure orchestration step. resolved_entities carries forward
    "last known" values (e.g. last_zone_id) from prior turns so the system
    prompt's reference-resolution instruction has something real to work
    from, and is updated in place from this turn's tool calls before return."""
    registry = _build_merged_registry()
    tools = registry.as_openai_tools()
    result = PlannerTurnResult(resolved_entities=dict(resolved_entities or {}))

    system = _SYSTEM_PROMPT
    if result.resolved_entities:
        system += f"\n\nKnown context from earlier in this conversation: {result.resolved_entities}"

    messages = [{"role": "system", "content": system}] + list(conversation_history) + \
        [{"role": "user", "content": english_question}]

    for _ in range(_MAX_TOOL_LOOP_ITERATIONS):
        resp = _get_client().chat.completions.create(
            model=_MODEL, max_tokens=1500, tools=tools, messages=messages,
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        tool_calls = msg.tool_calls or []
        if not tool_calls:
            result.final_text = msg.content or ""
            break

        for call in tool_calls:
            tool_input = json.loads(call.function.arguments) if call.function.arguments else {}
            result.tool_call_log.append({"tool": call.function.name, "input": tool_input})
            for arg_key, entity_key in _ENTITY_TRACKED_KEYS.items():
                if arg_key in tool_input:
                    result.resolved_entities[entity_key] = tool_input[arg_key]
            agent_result = registry.dispatch(call.function.name, tool_input, db=db)
            result.agent_results.append(agent_result)
            messages.append({
                "role": "tool", "tool_call_id": call.id, "content": str(agent_result.to_dict()),
            })
    else:
        result.final_text = result.final_text or "Reached the maximum number of reasoning steps for this query."

    return result