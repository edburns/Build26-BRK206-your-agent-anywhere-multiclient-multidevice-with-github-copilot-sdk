# Spike 2.7: Tool Definition Styles and Agent-Instance Binding

## Question
How should the three demo tools (`set_current_phase`, `report_intent`, `search_properties`) be defined using the Python SDK? Can tools close over agent instance state?

## Run
```bash
python spike_app.py
```

## What It Tests
1. **Decorator style** (`@define_tool`) with Pydantic params -- the headline pattern
2. **Override built-in tool** (`overrides_built_in_tool=True`) for `report_intent`
3. **Multi-field Pydantic model** for `search_properties` -- schema generation
4. **Factory/closure pattern** -- tools defined inside a function closing over `AgentContext`
5. **Function-call style** -- `define_tool("name", handler=..., params_type=...)` for comparison
6. **End-to-end** -- CopilotClient session with all tools, verifying the model calls them

## Key Finding
Tools are plain `Tool` dataclass instances. Defining them inside a factory function that
receives an `AgentContext` creates closures that bind each tool to that specific agent.
Two agents get independent tool sets with no cross-contamination.

### Recommended Pattern
```python
def create_tools_for_agent(agent: AgentContext) -> list[Tool]:
    @define_tool(description="Sets the current phase")
    def set_current_phase(params: SetPhaseParams) -> str:
        agent.current_phase = Phase(params.phase)  # closes over agent
        return "ok"
    return [set_current_phase, ...]
```
