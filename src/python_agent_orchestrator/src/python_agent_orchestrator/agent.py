import asyncio
from dataclasses import dataclass
from typing import Any

from copilot import CopilotClient, ToolSet, define_tool
from copilot.session import PermissionHandler
from copilot.session_events import AssistantMessageData, SessionIdleData
from copilot.tools import Tool
from pydantic import BaseModel, Field

from python_agent_orchestrator.phase import Phase
from python_agent_orchestrator.property_database import search_properties as search_properties_db


@dataclass
class Agent:
    query_id: str
    query_text: str
    current_phase: Phase = Phase.QUEUED
    current_intent: str = ""
    report_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "queryId": self.query_id,
            "phase": self.current_phase.value,
            "intent": self.current_intent,
            "queryText": self.query_text,
            "reportText": self.report_text,
        }

    async def run(self, client: CopilotClient, db_engine) -> None:
        done = asyncio.Event()
        loop = asyncio.get_running_loop()

        session = await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            available_tools=ToolSet().add_custom("*"),
            tools=create_tools_for_agent(self, db_engine),
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
                            "  - Extract relevant search criteria and search our property listings.\n"
                            "  - To search our property listings, call the search tool.\n"
                            "    You may call it multiple times with different filters to refine "
                            "results.\n"
                            "  - At the end of this phase, if you don't find any relevant properties, "
                            "set phase to \"Rejected\" and stop.\n"
                            "- Report phase\n"
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

        def on_event(event) -> None:
            match event.data:
                case AssistantMessageData() as data:
                    if data.content:
                        self.report_text = data.content
                case SessionIdleData():
                    loop.call_soon_threadsafe(done.set)

        session.on(on_event)
        await session.send(f"<enquiry>{self.query_text}</enquiry>")
        await done.wait()


def create_tools_for_agent(agent: Agent, db_engine) -> list[Tool]:
    class SetCurrentPhaseParams(BaseModel):
        phase: Phase = Field(description="The phase to transition to.")

    @define_tool(description="Sets the current phase of the agent. Use this to report progress.")
    def set_current_phase(params: SetCurrentPhaseParams) -> str:
        agent.current_phase = params.phase
        return f"Phase set to {agent.current_phase.value}"

    class ReportIntentParams(BaseModel):
        intent: str = Field(description="Intent in max 4 words")

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
            db_engine,
            city=params.city,
            min_beds=params.min_bedrooms,
            max_price=params.max_price,
            waterfront=params.waterfront,
        )

    return [set_current_phase, report_intent, search_properties]
