import asyncio
import json
import logging
import os
from typing import Annotated, Optional, TypedDict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient

# --- Basic Configuration ---
load_dotenv()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


# --- Agent State ---
class AgentState(TypedDict):
    """
    Represents the state of our agent.
    """

    messages: Annotated[list, add_messages]
    # This will be populated by the tools with the results of their work
    eligibility_response: Optional[dict]


# --- Tool Server Configuration ---
_tools_cache: dict[str, list] = {}
_tools_lock = asyncio.Lock()


async def _get_mcp_tools(
    server_url: str,
    server_id: str,
    auth_header: Optional[str],
) -> list:
    """Fetches tools from the MCP server, with caching."""
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
                "terminate_on_close": False,
            }
        }

        client = MultiServerMCPClient(cfg)
        logger.info("Downloading tool list from %s …", server_url)
        tools = await client.get_tools()

        if hasattr(client, "aclose"):
            await client.aclose()
        elif hasattr(client, "close"):
            client.close()

        if not tools:
            raise RuntimeError("Tool-server returned an empty tool list")

        _tools_cache[server_url] = tools
        logger.info("Fetched %s tools from %s", len(tools), server_url)
        return tools


async def call_tool(tool_name: str, **kwargs) -> dict:
    """A helper function to safely call a tool on the MCP server."""
    try:
        logger.info(f"Calling tool '{tool_name}' with args: {kwargs}")
        tools = await _get_mcp_tools(
            server_url=os.getenv("MCP_SERVER_URL"),
            server_id="mcp-server-tmobile",
            auth_header=os.getenv("MCP_AUTH_HEADER"),
        )
        target_tool = next((t for t in tools if t.name == tool_name), None)

        if not target_tool:
            raise ValueError(f"Tool '{tool_name}' not found on the MCP server.")

        result = await target_tool.ainvoke(kwargs)
        logger.info(f"Tool '{tool_name}' returned: {result}")
        # The result from the tool server is often a JSON string, let's handle it safely.
        if isinstance(result, str):
            try:
                return {"success": True, "result": json.loads(result)}
            except json.JSONDecodeError:
                # If it's not a valid JSON string, return it as is.
                return {"success": True, "result": result}
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Error calling tool '{tool_name}': {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# --- Agent Tools ---
@tool
async def geocode_address(query: str) -> dict:
    """
    Verifies a full or partial address string to get standardized address information.

    Args:
        query: The full street address to verify.
    """
    tool_kwargs = {
        "query": query,
        "Content-Type": "application/json",
        "Authorization": "Bearer token",
    }
    return await call_tool("ispApi__getGeocoders", **tool_kwargs)


@tool
async def check_eligibility(verified_address: dict) -> dict:
    """
    Checks T-Mobile Home Internet service eligibility for a verified address.

    Args:
        verified_address: The JSON object returned from the `geocode_address` tool.
    """
    if not isinstance(verified_address, dict):
        return {"error": "Invalid input. `verified_address` must be a dictionary."}

    geocoders = verified_address.get("geocoders", [])
    if not geocoders:
        return {"error": "Geocoders list is empty or missing in the address details."}

    address_data = geocoders[0]
    meta = address_data.get("meta", {})
    fiber_meta = meta.get("fiber", {})
    coordinates = address_data.get("center")

    eligibility_params = {
        "address": address_data.get("address"),
        "city": meta.get("city"),
        "state": meta.get("state"),
        "street1": meta.get("street1"),
        "street2": meta.get("street2", ""),
        "zipCode": meta.get("zipCode"),
        "locationKey": meta.get("locationKey"),
        "fiberLocationKey": fiber_meta.get("fiberLocationKey"),
        "coordinates": coordinates,
        "Authorization": "Bearer token",
        "Content-Type": "application/json",
    }
    eligibility_params = {k: v for k, v in eligibility_params.items() if v is not None}
    return await call_tool("ispApi__checkEligibility", **eligibility_params)


@tool
async def list_available_plans(eligibility_response: dict) -> dict:
    """
    Fetches available internet plans for an eligible address.

    Args:
        eligibility_response: The JSON object returned from the `check_eligibility` tool.
    """
    if not isinstance(eligibility_response, dict):
        return {"error": "Invalid input. `eligibility_response` must be a dictionary."}

    plan_tags = eligibility_response.get("hintEligibleCategories", [])
    geo_segments = eligibility_response.get("geoSegments", [])
    filtered_plan_tags = [tag for tag in plan_tags if tag.lower() not in ["capped", "nomad"]]
    if not geo_segments:
        geo_segments = ["nationwide"]

    plan_params = {
        "transactionType": "ACTIVATION",
        "planType": "ISP",
        "requestedLineNumber": 1,
        "accountSubtype": "INDIVIDUAL_REGULAR",
        "productSubCategories": ["Home Internet"],
        "planTags": filtered_plan_tags,
        "applyDiscount": True,
        "includePromotions": True,
        "geoSegments": geo_segments,
        "Authorization": "Bearer token",
        "Content-Type": "application/json",
    }
    return await call_tool("plans__GetBroadbandPlans", **plan_params)


@tool
async def select_plan(plan_id: str, eligibility_response: dict) -> dict:
    """
    Selects a plan and adds it to the user's cart.

    Args:
        plan_id: The ID of the plan the user wants to select.
        eligibility_response: The original eligibility response from the `check_eligibility` tool.
    """
    cart_token = os.getenv("CART_SESSION_ID")
    if not cart_token:
        return {"error": "CART_SESSION_ID environment variable not set."}

    # 1. Create/Get Cart
    create_cart_result = await call_tool("cart__GetCart", token=cart_token, Authorization="Bearer token", Content_Type="application/json", cartId="")
    if not create_cart_result.get("success"):
        return {"error": f"Failed to create cart: {create_cart_result.get('error')}"}
    
    cart_id = create_cart_result["result"].get("cart", {}).get("cartId")
    if not cart_id:
        return {"error": "Failed to get cartId from cart response."}

    # 2. Add to Cart
    eligibility_id = eligibility_response.get("eligibilityId")
    if not eligibility_id:
        return {"error": "eligibilityId not found in eligibility_response."}
    
    add_to_cart_params = {
        "cartId": cart_id,
        "eligibilityId": eligibility_id,
        "category": "premium,unlimited",
        "deleteLines": True,
        "isAccessory": False,
        "lineType": "ISP",
        "transactionType": "ACTIVATION",
        "fulfillment": [{"auditKey": "FULFILLMENTTYPE", "auditValue": "SHIP-TO"}],
        "Authorization": "Bearer token",
        "Content-Type": "application/json",
    }
    add_to_cart_result = await call_tool("cart__AddToCart", **add_to_cart_params)
    if not add_to_cart_result.get("success"):
        return {"error": f"Failed to add to cart: {add_to_cart_result.get('error')}"}

    try:
        line_id = add_to_cart_result["result"]["cart"]["lines"][0]["id"]
    except (KeyError, IndexError):
        return {"error": "Failed to extract lineId from cart response."}
        
    # 3. Update Plan
    update_plan_params = {
        "Content-Type": "application/json",
        "Authorization": "Bearer token",
        "offerFamilyId": plan_id,
        "cartId": cart_id,
        "lineId": line_id,
    }
    update_result = await call_tool("cart__UpdatePlans", **update_plan_params)
    if update_result.get("success"):
        return {"success": True, "message": f"Successfully added plan {plan_id} to cart {cart_id}."}
    else:
        return {"error": f"Failed to update plan: {update_result.get('error')}"}


# --- Agent Configuration ---
def get_model():
    """Initializes and returns a Chat model based on available API keys."""
    if os.getenv("OPENROUTER_API_KEY"):
        logger.info("Using OpenRouter.")
        return ChatOpenAI(
            model=os.getenv("OPENROUTER_OPENAI_MODEL", "openai/gpt-4o-mini"),
            base_url=os.getenv("OPENROUTER_BASE_URL"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            max_tokens=1024,
            temperature=0.0,
            max_retries=3,
        )
    if os.getenv("ANTHROPIC_API_KEY"):
        logger.info("Using direct Anthropic model (Claude).")
        return ChatAnthropic(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1024,
            temperature=0.0,
            max_retries=3,
        )
    elif os.getenv("OPENAI_API_KEY"):
        logger.info("Using direct OpenAI model.")
        return ChatOpenAI(
            model="gpt-4o-mini",
            max_tokens=1024,
            temperature=0.0,
            max_retries=3,
        )
    else:
        raise ValueError("No LLM API key found. Please set OPENROUTER_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY.")

# The tools our agent has access to
tools = [geocode_address, check_eligibility, list_available_plans, select_plan]
tool_node = ToolNode(tools)

# The agent model, with tools bound to it
llm = get_model().bind_tools(tools)

# --- Graph Definition ---

# The primary node for our graph, running the agent LLM
def agent_node(state: AgentState):
    """Invokes the agentmodel to generate a response based on the current state."""
    logger.info("--- Agent Node ---")
    # The agent is stateless, so we send it the full conversation history
    # The 'messages' state field is managed by the `add_messages` function
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def after_agent_node(state: AgentState) -> dict:
    """
    This node is executed after the main agent node. It processes the agent's
    output, which is expected to be a tool call. It then formats the tool's
    response into a ToolMessage that can be passed back to the agent.
    """
    logger.info("--- Intercepting Agent Response for Tool Call ---")
    last_message = state["messages"][-1]
    logger.info(f"Last message: {last_message}")
    # If the agent has produced a tool call
    if isinstance(last_message, ToolMessage):
        tool_name = last_message.name
        tool_call_id = last_message.tool_call_id
        if last_message.content:
            result = json.loads(last_message.content)
            if result.get("success"):   
                tool_output = result.get("result")
                logger.info(f"Tool result: {tool_output}")
        else:
            tool_output = last_message.content
            logger.info(f"Tool result: {tool_output}")

        # The 'content' of the tool message should be a string. We'll serialize the
        # dictionary from the tool output into a JSON string.
        
        # Ensure tool_output is a string before trying to load it.
        # It might already be a dict if the tool returns one directly.
        if isinstance(tool_output, str):
            try:
                # Attempt to parse it as JSON, but don't fail if it's not.
                tool_output = json.loads(tool_output)
            except json.JSONDecodeError:
                # The content is just a plain string, which is fine.
                pass
        
        # The 'content' of the tool message should be a string. We'll serialize the
        # dictionary from the tool output into a JSON string.
        if isinstance(tool_output, dict):
            content = json.dumps(tool_output, indent=2)
        else:
            content = str(tool_output)

        return {
            "messages": [
                ToolMessage(
                    content=content,
                    tool_call_id=tool_call_id,
                )
            ]
        }
    else:
        # If there's no tool call, we simply end the conversation.
        logger.info("Agent finished. No tool call detected.")
        return {"messages": []}


# The conditional router, deciding whether to call tools or end the conversation
def should_continue(state: AgentState):
    """
    Determines the next step for the graph.
    - If the agent generated a tool call, we execute the tool.
    - Otherwise, we end the conversation.
    """
    logger.info("--- Router ---")
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return "end"


# Define the graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", agent_node)
workflow.add_node("after_agent", after_agent_node)
workflow.add_node("tools", tool_node)

workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {"tools": "tools", "end": "__end__"},
)
workflow.add_edge("tools", "after_agent")
workflow.add_edge("after_agent", "agent")

# Compile the graph into a runnable app
app = workflow.compile()

# --- Main Execution Logic ---
async def run_conversation():
    """Manages the conversational loop with the user."""
    
    system_prompt = """You are a helpful T-Mobile Home Internet assistant.
Your goal is to guide users through the process of checking service eligibility and signing up for a plan.

Follow these steps:
1.  Start by greeting the user and asking for their full service address.
2.  Once you have the address, use the `geocode_address` tool to verify it.
3.  With the verified address, use the `check_eligibility` tool.
4.  Inform the user of their eligibility status.
5.  If they are eligible, use the `list_available_plans` tool and present the options clearly to the user, including name, description, and price.
6.  Ask the user which plan they would like.
7.  Once the user selects a plan, use the `select_plan` tool to add it to their cart. You will need the `plan_id` and the original `eligibility_response` from the state.
8.  Confirm that the plan has been added and ask if there is anything else you can help with.

- Be friendly and conversational.
- If a tool returns an error, inform the user and ask them to try again or provide different information.
- You must get the `eligibility_response` from the state after a successful `check_eligibility` call. Do not try to construct it yourself.
"""
    
    # We use a list to manage the conversation history
    messages = [SystemMessage(content=system_prompt)]

    while True:
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit"]:
            print("Assistant: Goodbye!")
            break

        messages.append(("user", user_input))
        
        # Stream the response from the graph
        final_state = None
        async for event in app.astream(
            {"messages": messages},
        ):
            # The "agent" node is the one that streams the final response
            if "agent" in event:
                final_state = event["agent"]
                # The response is the last message in the state
                response_message = final_state["messages"][-1]
                if response_message.content:
                    print(f"Assistant: {response_message.content}")

        # Update the message history with the final state from the run
        if final_state:
            messages = final_state["messages"]


if __name__ == "__main__":
    asyncio.run(run_conversation()) 