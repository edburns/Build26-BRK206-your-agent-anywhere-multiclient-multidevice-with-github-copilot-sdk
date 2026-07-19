import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
from typing import Any

from copilot import CopilotClient, ToolSet, define_tool
from copilot.session import PermissionHandler
from copilot.session_events import (
    AssistantMessageData,
    SessionErrorData,
    SessionIdleData,
    ToolExecutionCompleteData,
    ToolExecutionStartData,
)
from copilot.tools import Tool
from pydantic import BaseModel, Field, field_validator

from python_agent_orchestrator.phase import Phase
from python_agent_orchestrator.property_database import search_properties as search_properties_db
from python_agent_orchestrator.ws_manager import ws_manager

_SESSION_COMPLETION_TIMEOUT_SECONDS = 60.0
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


@dataclass
class Agent:
    query_id: str
    query_text: str
    db_engine: object = None
    current_phase: Phase = Phase.QUEUED
    current_intent: str = ""
    report_text: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "queryId": self.query_id,
            "phase": self.current_phase.value,
            "intent": self.current_intent,
            "queryText": self.query_text,
            "reportText": self.report_text,
            "events": list(self.events),
        }

    async def run(self, client: CopilotClient) -> None:
        done = asyncio.Event()
        loop = asyncio.get_running_loop()
        tool_names_by_call_id: dict[str, str] = {}

        def set_phase(phase: Phase, intent: str | None = None) -> None:
            self.current_phase = phase
            if intent is not None:
                self.current_intent = intent
            entry: dict[str, Any] = {
                "type": "phase_change",
                "timestamp": _now_iso(),
                "phase": self.current_phase.value,
                "intent": self.current_intent,
            }
            self.events.append(entry)
            ws_manager.schedule_broadcast(loop, {
                **entry,
                "queryId": self.query_id,
            })

        def record_error(message: str) -> None:
            entry = {
                "type": "error",
                "timestamp": _now_iso(),
                "message": message,
            }
            self.events.append(entry)
            ws_manager.schedule_broadcast(loop, {
                **entry,
                "queryId": self.query_id,
            })

        try:
            session = await client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                available_tools=ToolSet().add_custom("*"),
                tools=create_tools_for_agent(self, loop=loop),
                system_message={
                    "mode": "customize",
                    "sections": {
                        "identity": {
                            "action": "replace",
                            "content": (
                                "You are part of a real estate recommendation system. You will receive "
                                "enquiries from customers, and you must carry out the following workflow. "
                                "As you proceed, you will update your current phase and intent, which will "
                                "be visible to the user. Do not stop until the phase reaches a final state. "
                                'Start by setting phase to "Validating".\n\n'
                                "- Validation phase\n"
                                "  - Check the enquiry is genuine and not spam, garbage, or off-topic.\n"
                                "  - If it's not genuine, set phase to \"Rejected\" and stop.\n"
                                "- Search phase\n"
                                "  - Set phase to \"Searching\".\n"
                                "  - Extract relevant search criteria and search our property listings.\n"
                                "  - To search our property listings, call the search_properties tool.\n"
                                "    You may call it multiple times with different filters to refine "
                                "results.\n"
                                "  - At the end of this phase, if you don't find any relevant properties, "
                                "set phase to \"NoMatches\" and stop.\n"
                                "- Report phase\n"
                                "  - Set phase to \"WritingReport\".\n"
                                "  - Write up a report for our salesperson to use when calling the "
                                "customer.\n"
                                "  - Your report should include a summary of the customer's needs and the "
                                "top 1-3 matching properties. For each property, include key selling points "
                                "for this customer.\n"
                                "  - At the end of this phase, set phase to \"Done\" and stop.\n\n"
                                "As you go, always use set_current_phase each time you enter a new phase, "
                                "and report your intent at each step."
                            ),
                        },
                    },
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Session creation failed for agent %s", self.query_id)
            set_phase(Phase.REJECTED, intent="Session creation failed")
            record_error(f"Session creation failed ({type(exc).__name__}): {exc}")
            return

        def on_event(event) -> None:
            match event.data:
                case ToolExecutionStartData() as data:
                    args = data.arguments if isinstance(data.arguments, dict) else {}
                    entry: dict[str, Any] = {
                        "type": "tool_start",
                        "timestamp": _now_iso(),
                        "toolName": data.tool_name,
                        "toolCallId": data.tool_call_id,
                        "args": args,
                    }
                    self.events.append(entry)
                    tool_names_by_call_id[data.tool_call_id] = data.tool_name
                    ws_manager.schedule_broadcast(loop, {
                        **entry,
                        "queryId": self.query_id,
                    })
                case ToolExecutionCompleteData() as data:
                    tool_name = tool_names_by_call_id.pop(data.tool_call_id, "unknown_tool")
                    entry = {
                        "type": "tool_complete",
                        "timestamp": _now_iso(),
                        "toolCallId": data.tool_call_id,
                        "toolName": tool_name,
                        "success": data.success,
                    }
                    self.events.append(entry)
                    ws_manager.schedule_broadcast(loop, {
                        **entry,
                        "queryId": self.query_id,
                    })
                    if not data.success:
                        record_error(f"Tool execution failed for {tool_name} ({data.tool_call_id})")
                case AssistantMessageData() as data:
                    if data.content:
                        self.report_text = data.content
                        entry = {
                            "type": "assistant_message",
                            "timestamp": _now_iso(),
                            "content": data.content,
                        }
                        self.events.append(entry)
                        ws_manager.schedule_broadcast(loop, {
                            **entry,
                            "queryId": self.query_id,
                        })
                case SessionIdleData():
                    ws_manager.schedule_broadcast(loop, {
                        "type": "session_idle",
                        "queryId": self.query_id,
                    })
                    loop.call_soon_threadsafe(done.set)
                case SessionErrorData() as data:
                    set_phase(Phase.REJECTED, intent="Session error")
                    record_error(data.error)
                    loop.call_soon_threadsafe(done.set)

        session.on(on_event)
        try:
            await session.send(f"<enquiry>{self.query_text}</enquiry>")
            await asyncio.wait_for(done.wait(), timeout=_SESSION_COMPLETION_TIMEOUT_SECONDS)
        except TimeoutError:
            set_phase(Phase.REJECTED, intent="Timed out")
            record_error(
                f"Agent timed out after {_SESSION_COMPLETION_TIMEOUT_SECONDS:.0f} seconds waiting for completion"
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Session execution failed for agent %s", self.query_id)
            set_phase(Phase.REJECTED, intent="Session failed")
            record_error(f"Session execution failed ({type(exc).__name__}): {exc}")
        finally:
            try:
                await asyncio.shield(session.disconnect())
            except Exception:  # noqa: BLE001
                logger.debug("Ignoring error during session disconnect for agent %s", self.query_id, exc_info=True)


def create_tools_for_agent(
    agent: "Agent",
    db_engine=None,
    loop: asyncio.AbstractEventLoop | None = None,
) -> list[Tool]:
    if db_engine is not None:
        agent.db_engine = db_engine
    if agent.db_engine is None:
        raise ValueError("Agent.db_engine must be set before creating tools")

    class SetCurrentPhaseParams(BaseModel):
        phase: Phase = Field(description="The phase to transition to.")

    @define_tool(description="Sets the current phase of the agent. Use this to report progress.")
    def set_current_phase(params: SetCurrentPhaseParams) -> str:
        agent.current_phase = params.phase
        entry: dict[str, Any] = {
            "type": "phase_change",
            "timestamp": _now_iso(),
            "phase": agent.current_phase.value,
            "intent": agent.current_intent,
        }
        agent.events.append(entry)
        if loop is not None:
            ws_manager.schedule_broadcast(loop, {
                **entry,
                "queryId": agent.query_id,
            })
        return f"Phase set to {agent.current_phase.value}"

    class ReportIntentParams(BaseModel):
        intent: str = Field(description="Intent in max 4 words")

        @field_validator("intent")
        @classmethod
        def validate_intent_length(cls, value: str) -> str:
            word_count = len(value.strip().split())
            if word_count > 4:
                raise ValueError("intent must not exceed 4 words")
            return value

    @define_tool(
        name="report_intent",
        description="Reports the current intent of the agent",
        overrides_built_in_tool=True,
    )
    def report_intent(params: ReportIntentParams) -> str:
        agent.current_intent = params.intent
        return f"Intent set to {agent.current_intent}"

    class SearchPropertiesParams(BaseModel):
        city: str = Field(description="City to search in")
        min_bedrooms: int = Field(default=1, description="Minimum number of bedrooms")
        max_price: int = Field(default=1_000_000, description="Maximum price in CAD")
        waterfront: bool = Field(default=False, description="Whether waterfront is required")

    @define_tool(description="Searches the property database for listings that match user criteria.")
    def search_properties(params: SearchPropertiesParams) -> list[dict[str, Any]]:
        return search_properties_db(
            agent.db_engine,
            city=params.city,
            min_beds=params.min_bedrooms,
            max_price=params.max_price,
            waterfront=True if params.waterfront else None,
        )

    return [set_current_phase, report_intent, search_properties]
