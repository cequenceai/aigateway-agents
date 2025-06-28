import os
import logging
from typing import TypedDict, Annotated, Literal, Optional, List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import json
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph.message import add_messages
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from langgraph.types import Command
from langgraph.constants import Send
import asyncio


'''
DATA MODELS
'''
class GeocodersRequest(BaseModel):
    """Input model for the ispApi__getGeocoders tool."""
    query: str = Field(..., description="The full or partial address string to search for.")
    content_type: str = Field("application/json", alias="Content-Type", description="The content type of the request.")
    Authorization: str = Field("Bearer token", description="The authorization token.")

class GraphState(TypedDict):
    # The list of messages in the conversation
    ai_messages: Annotated[list, add_messages]
    user_messages: Annotated[list, add_messages]
    # The current step in the workflow
    progress: Annotated[
        Literal[
            "start",
            "address_verified",
            "eligibility_checked",
            "plans_presented",
            "plan_selected",
            "credit_check_complete",
            "end"
        ],
        "The current stage of the T-Mobile Home Internet eligibility workflow.",
    ]
    
    # Data collected during the workflow
    service_address_str: Annotated[list, add_messages]
    verified_address_details: Optional[dict]
    is_eligible: Optional[str]
    eligibility_response: Optional[dict]
    available_plans: Optional[list]
    plans_metadata: Optional[list]
    cart_id: Optional[str]
    line_id: Optional[str]
    selected_plan_id: Optional[str]
    selected_plan_details: Optional[dict]
    credit_check_passed: Optional[bool]


# --- Basic Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# --- MCP Tool Server Configuration ---
async def get_mcp_tools():
    # MCP_SERVER_URL = "https://ztaib-jpuw2rb1-e4l2dawa5a-uc.a.run.app/mcp"
    auth_header = os.getenv("MCP_AUTH_HEADER")
    server_config = {"mcp_server": {"url": os.getenv(MCP_URL), "transport": "streamable_http","headers": {"Authorization": auth_header} if auth_header else {}}}
    mcp_client = MultiServerMCPClient(server_config)
    tools = await mcp_client.get_tools()

    # explicitly close to drop the SSE stream
    if hasattr(client, "aclose") and callable(client.aclose):
        await client.aclose()
    elif hasattr(client, "close") and callable(client.close):
        client.close()
    # print(f"Tools: {tools}")
    return tools
_tools_cache: dict[str, list] = {}
_tools_lock = asyncio.Lock()

logger.info(f"MCP_SERVER_URL: {os.getenv('MCP_SERVER_URL')}")
async def _get_mcp_tools(
    server_url: str,
    server_id: str,
    auth_header: Optional[str],
) -> list:
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
        logger.info(f"Tools: {tools}")
        return tools


# --- Agent Configuration ---
def get_model(system_prompt: Optional[str] = None):
    """
    Initializes and returns a Chat model based on available API keys.
    Accepts an optional system_prompt to inject into the model if supported.
    """
    if bool(os.getenv("OPENROUTER_API_KEY")):
        logger.info("Using OpenRouter.")
        # Try OpenRouter Anthropic first
        try:
            OPENROUTER_OPENAI_MODEL = os.getenv("OPENROUTER_OPENAI_MODEL", "openai/gpt-4o-mini")
            logger.info(f"Using OpenRouter OpenAI model: {OPENROUTER_OPENAI_MODEL}")
            return ChatOpenAI(
                model=OPENROUTER_OPENAI_MODEL,
                base_url=os.getenv("OPENROUTER_BASE_URL"),
                api_key=os.getenv("OPENROUTER_API_KEY"),
                max_tokens=1024,
                temperature=0.0,
                max_retries=3,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize OpenRouter Anthropic model: {e}")
            # Fall back to OpenRouter OpenAI
            try:
                model_name = os.getenv("OPENROUTER_OPENAI_MODEL", "openai/gpt-4o-mini")
                logger.info(f"Falling back to OpenRouter OpenAI model: {model_name}")
                return ChatOpenAI(
                    model=model_name,
                    base_url="https://openrouter.ai/api/v1",
                    api_key=os.getenv("OPENROUTER_API_KEY"),
                    max_tokens=1024,
                    temperature=0.0,
                    max_retries=3,
                )
            except Exception as e_openai:
                logger.warning(f"Failed to initialize OpenRouter OpenAI model: {e_openai}")

    if bool(os.getenv("ANTHROPIC_API_KEY")):
        logger.info("Using direct Anthropic model (Claude).")
        return ChatAnthropic(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1024,
            temperature=0.0,
            max_retries=3,
        )
    elif bool(os.getenv("OPENAI_API_KEY")):
        logger.info("Using direct OpenAI model.")
        return ChatOpenAI(
            model="gpt-4o-mini",
            max_tokens=1024,
            temperature=0.0,
            max_retries=3,
        )
    else:
        logger.error("No LLM API key found. Cannot create a model.")
        return None

# --- LLM for Parsing ---
llm = get_model()
if not llm:
    raise ValueError("LLM could not be initialized. Please check API keys.")


# --- Tool-Calling Functions ---
async def call_tool(tool_name: str, **kwargs) -> dict:
    """A helper function to safely call a tool and handle errors."""
    try:
        logger.info(f"Calling tool '{tool_name}' with args: {kwargs}")
        # The MultiServerMCPClient gives us a list of tools, we find the one we want and run it
        tools = await _get_mcp_tools(server_url=os.getenv("MCP_SERVER_URL"), server_id="mcp-server-tmobile", auth_header=os.getenv("MCP_AUTH_HEADER"))
        target_tool = next((t for t in tools if t.name == tool_name), None)
        
        if not target_tool:
            raise ValueError(f"Tool '{tool_name}' not found on the MCP server.")
            
        result = await target_tool.ainvoke(kwargs)
        logger.info(f"Tool '{tool_name}' returned: {result}")
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Error calling tool '{tool_name}': {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def geocode_address_node(state: GraphState) -> GraphState:
    """
    Parses a raw address string into the required tool format and calls the geocoding tool.
    """
    logger.info("--- Step: Geocode Address ---")
    user_address = state["user_messages"][-1].content

    # This prompt instructs the LLM to extract an address from a user message and format the request.
    template = """
    You are an expert at processing user requests for internet service.
    Your task is to extract the full street address from the following user message.
    Then, create a JSON object for the `ispApi__getGeocoders` tool.
    The 'query' field of the JSON object must contain *only* the extracted address.
    The `Content_Type` and `Authorization` fields must be set to "application/json" and "Bearer token" respectively.
    If the user message does not contain an address, the query field should be an empty ('') string.
    User Message: "{address}"
    
    Format instructions: {format_instructions}
    """
    parser = JsonOutputParser(pydantic_object=GeocodersRequest)
    prompt = PromptTemplate.from_template(template=template, partial_variables={"format_instructions": parser.get_format_instructions()})
    chain = prompt | llm | parser
    
    request_params = await chain.ainvoke({"address": user_address})
    logger.info(f"Request params: {request_params}")
    if request_params["query"] == "":
        return
    tool_kwargs = request_params
    if isinstance(request_params, BaseModel):
        tool_kwargs = request_params.model_dump(by_alias=True)
    elif isinstance(request_params, dict) and "Content_Type" in request_params:
        # The LLM sometimes returns 'Content_Type' instead of 'Content-Type'
        tool_kwargs["Content-Type"] = tool_kwargs.pop("Content_Type")

    tool_result = await call_tool("ispApi__getGeocoders", **tool_kwargs)
    # print(type(tool_result["result"]))
    if tool_result.get("success"):
        return {"progress": "address_verified", "verified_address_details": json.loads(tool_result["result"])}
    else:
        error_message = f"Geocoding failed: {tool_result.get('error')}"
        logger.error(error_message)
        # To retry, we can stay in the same state and just update the messages.
        # The supervisor will then route back to this node if the logic is set up for retries.
        # For now, let's just end the flow with an error message.
        return {"progress": "end", "ai_messages": [AIMessage(content=f"I'm sorry, I couldn't verify that address. Please try again. Error: {error_message}")]}

async def check_eligibility_node(state: GraphState) -> GraphState:
    """
    Checks service eligibility using the verified address details.
    """
    logger.info("--- Step: Check Eligibility ---")
    verified_address_details = state.get("verified_address_details")

    if not verified_address_details or not isinstance(verified_address_details, dict):
        error_message = "No verified address details found to check eligibility."
        logger.error(error_message)
        return {"progress": "end", "is_eligible": False, "messages": [AIMessage(content=error_message)]}

    geocoders = verified_address_details.get("geocoders", [])
    if not geocoders:
        error_message = "Geocoders list is empty or missing in the address details."
        logger.error(error_message)
        return {"progress": "end", "is_eligible": False, "messages": [AIMessage(content=error_message)]}

    # Use the first geocoded result
    address_data = geocoders[0]
    meta = address_data.get("meta", {})
    fiber_meta = meta.get("fiber", {})
    coordinates = address_data.get("center")
    
    # Convert lat/lng to strings as required by the tool
    if isinstance(coordinates, dict):
        if 'lat' in coordinates:
            coordinates['lat'] = str(coordinates['lat'])
        if 'lng' in coordinates:
            coordinates['lng'] = str(coordinates['lng'])

    eligibility_params = {
        "address": address_data.get("address"),
        "city": meta.get("city"),
        "state": meta.get("state"),
        "street1": meta.get("street1"),
        "street2": meta.get("street2", ""),
        "zipCode": meta.get("zipCode"),
        "locationKey": meta.get("locationKey"),
        "fiberLocationKey": fiber_meta.get("fiberLocationKey"),
        "coordinates": coordinates if coordinates else None,
        "Authorization": "Bearer token",
        "Content-Type": "application/json"
    }
    
    eligibility_params = {k: v for k, v in eligibility_params.items() if v is not None}
    
    logger.info(f"Checking eligibility with params: {eligibility_params}")
    tool_result = await call_tool("ispApi__checkEligibility", **eligibility_params)
    logger.info(f"Eligibility response: {tool_result}")
    if tool_result.get("success"):
        is_eligible = json.loads(tool_result["result"]).get("status", "ineligible")
        logger.info(f"Eligibility check successful. Eligible: {is_eligible}")
        if is_eligible == "eligible":
            return {
                "progress": "eligibility_checked",
                "is_eligible": is_eligible,
                "eligibility_response": tool_result["result"]
            }
        else:
            return Command(
                update={"ai_messages": [AIMessage(content= "You are not eligible for a home internet plan. Please try again with a different address.")]},
                goto=END
            )
    else:
        error_message = f"Eligibility check failed: {tool_result.get('error')}"
        logger.error(error_message)
        return {"progress": "end", "is_eligible": "ineligible", "messages": [AIMessage(content=error_message)]}


async def list_plans_node(state: GraphState) -> GraphState:
    """
    Creates a cart, fetches available plans, and summarizes them for the user.
    """
    logger.info("--- Step: List Plans ---")

    # Extract planTags and geoSegments from eligibility response
    eligibility_response_str = state.get("eligibility_response")
    if not eligibility_response_str:
        error_message = "Could not find eligibility information to fetch plans."
        logger.error(error_message)
        return {"progress": "end", "messages": [AIMessage(content=error_message)]}

    try:
        eligibility_data = json.loads(eligibility_response_str)
        logger.debug(f"Successfully parsed eligibility data: {eligibility_data}")
    except json.JSONDecodeError:
        error_message = "Failed to parse eligibility response when fetching plans."
        logger.error(error_message)
        return {"progress": "end", "messages": [AIMessage(content=error_message)]}
    
    plan_tags = eligibility_data.get("planTags", [])
    geo_segments = eligibility_data.get("geoSegments", [])
    
    # Filter out capped and nomad plan tags as per business logic
    filtered_plan_tags = [tag for tag in plan_tags if tag.lower() not in ["capped", "nomad"]]
    
    # Default to nationwide if no geoSegments are returned
    if not geo_segments:
        geo_segments = ["nationwide"]


    # 2. Get available plans
    
    # changes:
    # - plan tags should be picked from check address eligibility api
    # - exclude capped and nomad categories
    # - geoSegments should be picked from check address eligibility api
    # - if empty choose nationwide
    
    logger.info("Fetching available plans...")
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
      "Content-Type": "application/json"
    }
    
    get_plans_result = await call_tool("plans__GetBroadbandPlans", **plan_params)

    if not get_plans_result.get("success"):
        error_message = f"Failed to get plans: {get_plans_result.get('error')}"
        logger.error(error_message)
        return {"progress": "end", "messages": [AIMessage(content=error_message)]}

    available_plans_data = json.loads(get_plans_result["result"]).get("plans", [])
    if available_plans_data:
        available_plans = [
            {   "id": plan.get("offerFamilyId"),
                "name": plan.get("displayName"),
                "price": plan.get("price").get("linePlanPrice")[0].get("monthlyPrice").get("listPrice").get("amount")
            }
            for plan in available_plans_data
        ]
    else:
        available_plans = []
    
    # print(available_plans_data)
    logger.info(f"Successfully fetched plans: {available_plans}")

    return {
        "progress": "plans_presented",
        "available_plans": available_plans,
        "plans_metadata": available_plans_data,
    }


async def add_plan_to_cart_node(state: GraphState) -> GraphState:
    """
    Adds the user's selected plan to the shopping cart.
    """
    logger.info("--- Step: Add Plan to Cart ---")

    logger.info("Initializing a new cart...")
    cart_token = os.getenv("CART_SESSION_ID")
    if not cart_token:
        error_message = "CART_SESSION_ID environment variable not set."
        logger.error(error_message)
        return {"progress": "end", "messages": [AIMessage(content=error_message)]}
        
    cart_params = {
        "Authorization": "Bearer token",
        "Content-Type": "application/json",
        "cartId": "",
        "token": cart_token
    }
    create_cart_result = await call_tool("cart__GetCart", **cart_params)
    
    if not create_cart_result.get("success"):
        error_message = f"Failed to create cart: {create_cart_result.get('error')}"
        logger.error(error_message)
        return {"progress": "end", "messages": [AIMessage(content=error_message)]}
    
    cart_id = json.loads(create_cart_result["result"]).get("cart").get("cartId")
    logger.info(f"Cart created with ID: {cart_id}")
    
    # Retrieve necessary data from state
    eligibility_response_str = state.get("eligibility_response")

    # Validate required data
    if not eligibility_response_str:
        error_message = "Missing eligibility info to add to cart."
        logger.error(error_message)
        return {"progress": "end", "messages": [AIMessage(content=error_message)]}

    try:
        eligibility_data = json.loads(eligibility_response_str)
        eligibility_id = eligibility_data.get("eligibilityId")
        if not eligibility_id:
            raise ValueError("eligibilityId not found in eligibility_response")
    except (json.JSONDecodeError, ValueError) as e:
        error_message = f"Failed to get eligibilityId from response: {e}"
        logger.error(error_message)
        return {"progress": "end", "messages": [AIMessage(content=error_message)]}
    
    # Prepare parameters for the addToCart tool
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
        "Content-Type": "application/json"
    }

    logger.info(f"Adding plan to cart with params: {add_to_cart_params}")
    tool_result = await call_tool("cart__AddToCart", **add_to_cart_params)
    
    if tool_result.get("success"):
        logger.info(f"tool response: {tool_result}")
        try:
            response_data = json.loads(tool_result["result"])
            line_id = response_data["cart"]["lines"][0]["id"]
            logger.info(f"Extracted lineId: {line_id}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            error_message = f"Failed to extract lineId from cart response: {e}"
            logger.error(error_message)
            return {"progress": "end", "messages": [AIMessage(content=error_message)]}

        # --- Now, update the plan in the same node ---
        logger.info("--- Step: Update Plan in Cart ---")
        plan_id = state["available_plans"][0]["id"]
        update_plan_params = {
            "Content-Type": "application/json",
            "Authorization": "Bearer token",
            "offerFamilyId": plan_id,
            "cartId": cart_id,
            "lineId": line_id,
        }
        logger.info(f"Updating plan with params: {update_plan_params}")
        update_tool_result = await call_tool("cart__UpdatePlans", **update_plan_params)

        if update_tool_result.get("success"):
            logger.info(f"Successfully updated plan for line {line_id} in cart {cart_id}.")
            return {
                "progress": "plan_selected",
                "cart_id": cart_id,
                "line_id": line_id,
            }
        else:
            error_message = f"Failed to update plan: {update_tool_result.get('error')}"
            logger.error(error_message)
            return {"progress": "end", "messages": [AIMessage(content=error_message)]}

    else:
        error_message = f"Failed to add plan to cart: {tool_result.get('error')}"
        logger.error(error_message)
        return {"progress": "end", "messages": [AIMessage(content=error_message)]}


# --- Define the Supervisor (Router) ---
def supervisor_node(state: GraphState):
    """
    The central router that directs the workflow based on the current `progress`.
    """
    logger.info(f"--- Supervisor: Current Progress is '{state['progress']}' ---")
    if not state.get("service_address_str"):
        return Command(
            goto=END
        )
    progress = state["progress"]
    
    if progress == "start":
        return "geocode_address"
    elif progress == "address_verified":
        return "check_eligibility"
    elif progress == "eligibility_checked":
        if state.get("is_eligible"):
            return "list_plans"
        else:
            return END
    elif progress == "plans_presented":
        if state.get("selected_plan_id"):
            return "add_plan_to_cart"
        return END
    elif progress == "plan_selected":
        return END

    return END


# --- Build the Graph ---
workflow = StateGraph(GraphState)

# Add the nodes
workflow.add_node("geocode_address", geocode_address_node)
workflow.add_node("check_eligibility", check_eligibility_node)
workflow.add_node("list_plans", list_plans_node)
workflow.add_node("add_plan_to_cart", add_plan_to_cart_node)
# workflow.add_node("supervisor", supervisor_node)


# The supervisor is a conditional edge that routes to the correct node.

workflow.add_edge(START, "geocode_address")
workflow.add_edge("geocode_address", "check_eligibility")
workflow.add_edge("check_eligibility", "list_plans")
workflow.add_edge("list_plans", "add_plan_to_cart")
workflow.add_edge("add_plan_to_cart", END)


# Compile the graph
app = workflow.compile()


async def main():
    """Runs the T-Mobile eligibility workflow."""
    inputs = {"user_messages": [HumanMessage(content="am I eligible for a home internet plan , my address is 5201 great america pkwy, santa clara")]}
    result = await app.ainvoke(inputs)
    print(result["available_plans"])

if __name__ == "__main__":
    asyncio.run(main())


