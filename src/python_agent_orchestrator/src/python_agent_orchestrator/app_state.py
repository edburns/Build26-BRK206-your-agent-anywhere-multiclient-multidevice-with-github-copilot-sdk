import asyncio
from dataclasses import dataclass, field

from copilot import CopilotClient

from python_agent_orchestrator.agent import Agent


@dataclass
class AppState:
    copilot_client: CopilotClient
    db_engine: object
    agents: dict[str, Agent] = field(default_factory=dict)
    next_query_number: int = 1
    query_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
