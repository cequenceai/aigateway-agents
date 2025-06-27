"""
react_agent_with_memory.py
──────────────────────────
Creates a LangGraph ReAct agent that can call MCP tools.

Key points
----------
* Downloads the tool list **once** per MCP server and keeps it in
  `_tools_cache`.
* Immediately closes the `MultiServerMCPClient` after fetching tools, so no
  orphan SSE streams linger (fixes the 5‑minute ReadTimeout issue).
* Sets `terminate_on_close=False` in transport config to mute DELETE /mcp 400s.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

# ────────────────────────── environment & logging ──────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY_LOADED = bool(os.getenv("ANTHROPIC_API_KEY"))
OPENAI_API_KEY_LOADED = bool(os.getenv("OPENAI_API_KEY"))
OPENROUTER_API_KEY_LOADED = bool(os.getenv("OPENROUTER_API_KEY"))

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_ANTHROPIC_MODEL = os.getenv(
    "OPENROUTER_ANTHROPIC_MODEL", "anthropic/claude-sonnet-4"
)
OPENROUTER_OPENAI_MODEL = os.getenv(
    "OPENROUTER_OPENAI_MODEL", "openai/gpt-4o-mini"
)

# --- System Prompt for T-Mobile Home Internet Eligibility Check ---
T_MOBILE_HOME_INTERNET_SYSTEM_PROMPT = """T-Mobile Home Internet Agent System Prompt for LangGraph Framework
==================================================================

Agent Role & Purpose
--------------------
You are a **T-Mobile Home Internet eligibility-verification and plan-selection agent**.  
Your job is to guide customers from address verification through choosing a broadband plan, using the available T-Mobile API tools.

------------------------------------------------------------------
1  ALWAYS Follow This Four-Step Workflow
------------------------------------------------------------------
1. **Address geocoding**  
2. **Eligibility verification**  
3. **Broadband plans retrieval**  
4. **Plan presentation & customer selection**

Do not skip or reorder these steps.

------------------------------------------------------------------
2  ALWAYS Use These Fixed Request Bodies (Templates)
------------------------------------------------------------------

### 2.1 Geocoding Request
```json
{
  "Authorization": "Bearer token",
  "Content-Type": "application/json",
  "qmdu": {
    "city":            "[USER_CITY]",
    "state":           "[USER_STATE]",
    "street1":         "[USER_STREET]",
    "street2":         "[USER_STREET2_OR_EMPTY]",
    "zipCode":         "[USER_ZIP]"
  }
}
```

### 2.2 Eligibility Check
```json
{
  "Authorization":    "Bearer token",
  "Content-Type":     "application/json",
  "address":          "[FULL_ADDRESS_FROM_GEOCODING]",
  "city":             "[CITY_UPPERCASE]",
  "state":            "[STATE_UPPERCASE]",
  "street1":          "[STREET1_FROM_GEOCODING]",
  "street2":          "[STREET2_FROM_GEOCODING_OR_EMPTY]",
  "zipCode":          "[ZIP_FROM_GEOCODING]",
  "coordinates": {
    "lat":            "[LAT_FROM_GEOCODING]",
    "lng":            "[LNG_FROM_GEOCODING]"
  },
  "locationKey":          "[LOCATION_KEY_FROM_GEOCODING]",
  "fiberLocationKey":     "[FIBER_LOCATION_KEY_FROM_GEOCODING]",
  "transactionType":      "new"
}
```

### 2.3 Broadband Plans Request  **(Use this and nothing else)**
```json
{
  "transactionType":      "ACTIVATION",
  "planType":             "ISP",
  "requestedLineNumber":  1,
  "accountSubtype":       "INDIVIDUAL_REGULAR",
  "productSubCategories": ["Home Internet"],
  "planTags":             ["premium", "unlimited"],
  "applyDiscount":        true,
  "includePromotions":    true,
  "geoSegments":          ["nationwide"]
}
```

------------------------------------------------------------------
3  Data Extraction Rules
------------------------------------------------------------------
**From Geocoding** (always read indices `geocoders[0].*`):

* `meta.locationKey`            → `locationKey`  
* `meta.fiber.fiberLocationKey` → `fiberLocationKey`  
* `center.lat`                  → `coordinates.lat`  
* `center.lng`                  → `coordinates.lng`  
* `address`                     → `full address`  
* `meta.street1`                → `street1`  
* `meta.city` (uppercase)       → `city`  
* `meta.state` (uppercase)      → `state`  
* `meta.zipCode`                → `zipCode`

**From Eligibility**:

* Proceed **only if** `status == "eligible"`.  
* Store `eligibilityId`, present `serviceLevel`, show `hintEligibleCategories`.

------------------------------------------------------------------
4  Error Handling Protocol
------------------------------------------------------------------
* **Geocoding fails** → Ask customer to re-enter full address; stop.  
* **Eligibility “not eligible”** → Inform service unavailable, suggest nearby addresses; stop.  
* **Plans call fails** → Inform temporary issue, offer generic info or hand-off.

------------------------------------------------------------------
5  Customer Communication Guidelines
------------------------------------------------------------------
* When address is eligible: say **“✅ YOUR ADDRESS IS ELIGIBLE”**, show service level & categories.  
* When presenting plans: list **name, speed, price**, highlight promotions, equipment, install, monthly cost breakdown.  
* After plan list: prompt for selection, explain contract terms & next steps.  
* Do **not** end conversation until customer chooses or declines a plan.

------------------------------------------------------------------
6  Required Tool-Call Sequence
------------------------------------------------------------------
STEP 1  ispApi__getGeocoders  
   ↓  
STEP 2  ispApi__checkEligibility  
   ↓  
STEP 3  plans__GetBroadbandPlans  
   ↓  
STEP 4  Customer plan selection  

------------------------------------------------------------------
7  LangGraph State Management
------------------------------------------------------------------
* Store geocoding results, eligibility data, and customer preferences in state.  
* Maintain context across turns.

------------------------------------------------------------------
8  Response Formatting
------------------------------------------------------------------
* Use clear section headers.  
* Show eligibility status with ✅ / ❌.  
* Format addresses in **ALL CAPS** when inserting into API calls.  
* Use bullet lists or tables for plan details; show prices clearly.

------------------------------------------------------------------
9  Conversation Flow Control
------------------------------------------------------------------
* Never assume customer preferences.  
* Always guide toward an explicit plan choice or graceful exit.  
* Offer to answer questions at every step.

==================================================================
END OF SYSTEM PROMPT
"""

# ────────────────────────── choose an LLM ───────────────────────────────────
def get_model(system_prompt: Optional[str] = None):
    if OPENROUTER_API_KEY_LOADED:
        return ChatOpenAI(
            model=OPENROUTER_ANTHROPIC_MODEL,
            base_url=OPENROUTER_BASE_URL,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            max_tokens=4096,
            temperature=0.0,
            max_retries=3,
        )
    if ANTHROPIC_API_KEY_LOADED:
        return ChatAnthropic(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1024,
            temperature=0.0,
            max_retries=3,
            system_prompt=system_prompt or T_MOBILE_HOME_INTERNET_SYSTEM_PROMPT,
        )
    if OPENAI_API_KEY_LOADED:
        return ChatOpenAI(
            model="gpt-4o",
            max_tokens=1024,
            temperature=0.0,
            max_retries=3,
        )
    logger.error("No LLM API key available.")
    return None

# ────────────────────────── trim history helper ────────────────────────────
def pre_model_hook(state: Dict[str, Any]) -> Dict[str, Any]:
    trimmed = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=4096,
        start_on="human",
        end_on=("human", "tool"),
    )
    return {"llm_input_messages": trimmed}

# ────────────────────────── tool‑list cache ────────────────────────────────
_tools_cache: dict[str, list] = {}
_tools_lock = asyncio.Lock()

async def _load_tools(
    server_url: str,
    server_id: str,
    auth_header: Optional[str],
) -> list:
    """
    Fetch the tool list once per server_url and store it in `_tools_cache`.
    Ensures the underlying SSE connection is closed immediately.
    """
    async with _tools_lock:
        if server_url in _tools_cache:
            return _tools_cache[server_url]

        cfg = {
            server_id: {
                "url": server_url,
                "transport": "streamable_http",
                "headers": {"Authorization": auth_header} if auth_header else {},
                "timeout": 30,
                "sse_read_timeout": 60,
                "terminate_on_close": False,  # skip noisy DELETE /mcp
            }
        }

        client = MultiServerMCPClient(cfg)
        logger.info("Downloading tool list from %s …", server_url)
        tools = await client.get_tools()

        # explicitly close to drop the SSE stream
        if hasattr(client, "aclose") and callable(client.aclose):
            await client.aclose()
        elif hasattr(client, "close") and callable(client.close):
            client.close()

        if not tools:
            raise RuntimeError("Tool‑server returned an empty tool list")

        _tools_cache[server_url] = tools
        logger.info("Fetched %s tools from %s", len(tools), server_url)
        return tools

# ────────────────────────── public factory ─────────────────────────────────
async def create_agent_executor(
    server_url: str,
    server_id: str = "mcp_server",
    auth_header: Optional[str] = None,
    system_prompt: Optional[str] = None,
):
    """Return an AgentExecutor wired to the given MCP server."""
    model = get_model(system_prompt)
    if model is None:
        return None

    try:
        tools = await _load_tools(server_url.rstrip("/"), server_id, auth_header)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Could not load tools: %s", exc)
        return None

    agent = create_react_agent(
        model,
        tools=tools,
        pre_model_hook=pre_model_hook,
        checkpointer=InMemorySaver(),
    )

    # inject system prompt on every call, if provided
    if system_prompt:
        original_ainvoke = agent.ainvoke

        async def ainvoke_with_system_prompt(inputs, config=None):
            msgs = inputs.get("messages", [])
            if not msgs or msgs[0][0] != "system":
                msgs = [("system", system_prompt), *msgs]
            return await original_ainvoke({**inputs, "messages": msgs}, config=config)

        agent.ainvoke = ainvoke_with_system_prompt  # type: ignore[method-assign]

    return agent

# re‑export for main.py
__all__ = ["create_agent_executor", "AIMessage"]
