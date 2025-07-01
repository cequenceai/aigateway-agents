"""
T-Mobile Home-Internet eligibility + cart workflow
──────────────────────────────────────────────────
"""

from __future__ import annotations
import asyncio, json, logging, os, re
from typing import Annotated, Literal, Optional, TypedDict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, Field

ADDRESS_HINT = re.compile(r'\d+\s+\w+', re.IGNORECASE)

# ──────────────── setup & logging ────────────────
load_dotenv()
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("tmobile_workflow")

MCP_SERVER_URL  = os.getenv("MCP_SERVER_URL")
MCP_AUTH_HEADER = os.getenv("MCP_AUTH_HEADER", "")
if not MCP_SERVER_URL:
    raise RuntimeError("Environment variable MCP_SERVER_URL is required")

# ──────────────── pydantic helper for geocoder ────────────────
class GeocodersRequest(BaseModel):
    query          : str = Field(..., description="Full or partial address")
    content_type   : str = Field("application/json", alias="Content-Type")
    Authorization  : str = "Bearer token"

# ──────────────── state schema ────────────────
class GraphState(TypedDict):
    ai_messages      : Annotated[list, add_messages]
    user_messages    : Annotated[list, add_messages]
    progress         : Annotated[Literal[
                        "start","address_verified", "awaiting_address",
                        "awaiting_eligibility",
                        "eligibility_checked","plans_presented",
                        "plan_selected","end"],
                        "Current stage"]
    verified_address_details: Optional[dict]
    eligibility_response   : Optional[str]
    available_plans        : Optional[list]
    plans_metadata         : Optional[list]
    cart_id                : Optional[str]
    line_id                : Optional[str]
    selected_plan_id       : Optional[str]
    review_cart_url        : Optional[str]

# ──────────────── LLM selection ────────────────
def _choose_llm():
    if os.getenv("OPENROUTER_API_KEY"):
        return ChatOpenAI(model=os.getenv("OPENROUTER_OPENAI_MODEL","openai/gpt-4o-mini"),
                          base_url=os.getenv("OPENROUTER_BASE_URL","https://openrouter.ai/api/v1"),
                          api_key=os.getenv("OPENROUTER_API_KEY"), temperature=0)
    if os.getenv("ANTHROPIC_API_KEY"):
        return ChatAnthropic(model="claude-3-5-sonnet-20240620", temperature=0)
    if os.getenv("OPENAI_API_KEY"):
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    raise RuntimeError("No LLM key configured")
llm = _choose_llm()

# ──────────────── MCP helper ────────────────
_tools_cache: dict[str, list] = {}
_tools_lock = asyncio.Lock()

async def _get_mcp_tools():
    async with _tools_lock:
        if MCP_SERVER_URL in _tools_cache:
            return _tools_cache[MCP_SERVER_URL]
        client = MultiServerMCPClient({
            "mcp":{"url":MCP_SERVER_URL,"transport":"streamable_http",
                   "headers":{"Authorization":MCP_AUTH_HEADER} if MCP_AUTH_HEADER else {},
                   "timeout":30,"sse_read_timeout":60}})
        logger.info("Downloading tool list …")
        tools = await client.get_tools()
        if hasattr(client,"aclose") and callable(client.aclose):
            await client.aclose()
        elif hasattr(client,"close") and callable(client.close):
            client.close()
        if not tools: raise RuntimeError("Tool server returned empty list")
        _tools_cache[MCP_SERVER_URL]=tools
        return tools

async def _call_tool(name:str, **kwargs):
    try:
        tool = next(t for t in await _get_mcp_tools() if t.name==name)
        res  = await tool.ainvoke(kwargs)
        logger.info("Tool %s → %s", name, res[:200]+"…" if isinstance(res,str) else res)
        return {"success":True,"result":res}
    except Exception as e:
        logger.exception("Tool call failed")
        return {"success":False,"error":str(e)}

# ──────────────── nodes ────────────────
LLM_TEMPLATE = """
You are an expert at processing home-internet requests.
Extract the **full street address** from the user message below and return a
JSON payload for the `ispApi__getGeocoders` tool.

If no address is present leave `"query"` blank.

User message: "{address}"
Format instructions:
{format_instructions}
""".strip()

async def geocode_address_node(state:GraphState)->GraphState:
    user_msg = state["user_messages"][-1].content.strip()
    
    # If the message doesn't contain a number and at least two words, it's probably not an address
    if not user_msg or not ADDRESS_HINT.search(user_msg):
        logger.info("Not an address")
        return Command(update={"ai_messages":[AIMessage(content="Could you give me the full service address?")],
                               "progress":"awaiting_address"},
                       goto="router")

    parser = JsonOutputParser(pydantic_object=GeocodersRequest)
    prompt = PromptTemplate.from_template(
        LLM_TEMPLATE,
        partial_variables={"format_instructions":parser.get_format_instructions()}
    )
    params = await (prompt | llm | parser).ainvoke({"address":user_msg})
    logger.info("query=%s", params.get("query"))
    if not params.get("query"):
        logger.info("No address found in user message")
        return {"ai_messages":[AIMessage(content="I didn't catch the address—could you repeat it?")],
                "progress":state.get("progress","start")}
    res = await _call_tool("ispApi__getGeocoders",
                           query=params["query"],
                           **{"Content-Type":"application/json","Authorization":"Bearer token"})
    if res["success"]:
        logger.info("address_verified")
        return {"progress":"address_verified",
                "verified_address_details":json.loads(res["result"])}
    return {"progress":"end",
            "ai_messages":[AIMessage(content=f"Sorry, address verification failed ({res['error']}).")]}

async def check_eligibility_node(state:GraphState)->GraphState:
    data = state.get("verified_address_details",{})
    if not data.get("geocoders"):
        return Command(update={"progress":"awaiting_eligibility","ai_messages":[AIMessage(content="Address not eligible. Please try another address.")],
                               "goto":"router"})

    g      = data["geocoders"][0]
    meta   = g["meta"]
    coords = {k:str(v) for k,v in g["center"].items()}

    res = await _call_tool("ispApi__checkEligibility",
                           address=g["address"], city=meta["city"], state=meta["state"],
                           street1=meta["street1"], street2=meta.get("street2",""),
                           zipCode=meta["zipCode"], locationKey=meta["locationKey"],
                           fiberLocationKey=meta["fiber"]["fiberLocationKey"],
                           coordinates=coords,
                           **{"Authorization":"Bearer token","Content-Type":"application/json"})
    if not res["success"]:
        return {"progress":"end","ai_messages":[AIMessage(content=res["error"])]}
    if json.loads(res["result"])["status"]!="eligible":
        return Command(update={"ai_messages":[AIMessage(content="Unfortunately that address is not eligible.")]},
                       goto=END)
    return {"progress":"eligibility_checked","eligibility_response":res["result"]}

def router_node(state:GraphState):
    """Pure routing – no external calls."""
    last      = state["user_messages"][-1].content.strip()
    plan_ids  = {p["id"] for p in state.get("available_plans",[])}
    if state.get("progress") == "awaiting_address":
        if ADDRESS_HINT.search(last):
            return Command(update={"ai_messages":[AIMessage(content="Rechecking address…")]},
                           goto="geocode_address")
        
        return Command(update={"ai_messages":[AIMessage(content="No address found. Please enter a valid address.")]},
                       goto=END)
    if not last:
        return Command(update={"ai_messages":[AIMessage(content="I didn't catch the address—could you repeat it?")]},
                       goto="router")
    if state.get("progress") == "awaiting_eligibility":
        return Command(update={"ai_messages":[AIMessage(content="Address not eligible. Please try another address.")],
                               "progress":"awaiting_address",
                               "goto":"router"})
    if last in plan_ids:
        # safe log (thread id if provided via config, else 'n/a')
        thread_id = state.get("__run_id__", "n/a")
        logger.info("plan_selected=%s  thread=%s", last, thread_id)
        return Command(update={"selected_plan_id":last,"progress":"plan_selected"},
                       goto="add_plan_to_cart")

    prog = state.get("progress","start")
    return Command(goto={
        "start"              : "geocode_address",
        "address_verified"   : "check_eligibility",
        "eligibility_checked": "list_plans"
    }.get(prog, END))

async def list_plans_node(state:GraphState)->GraphState:
    elig = json.loads(state["eligibility_response"])
    tags = [t for t in elig["hintEligibleCategories"] if t.lower() not in ("capped","nomad")]
    geo  = elig.get("geoSegments") or ["nationwide"]

    res = await _call_tool("plans__GetBroadbandPlans",
                           transactionType="ACTIVATION", planType="ISP",
                           requestedLineNumber=1, accountSubtype="INDIVIDUAL_REGULAR",
                           productSubCategories=["Home Internet"], planTags=tags,
                           geoSegments=geo, applyDiscount=True, includePromotions=True,
                           **{"Authorization":"Bearer token","Content-Type":"application/json"})
    if not res["success"]:
        return {"progress":"end","ai_messages":[AIMessage(content=res["error"])]}

    plans = json.loads(res["result"])["plans"]
    brief = [{"id":p["offerFamilyId"],
              "name":p.get("displayName") or p.get("name") or p.get("planName"),
              "price":p["price"]["cartPlanPrice"]["monthlyPrice"]["salePrice"]["amount"]} for p in plans]
    return {"progress":"plans_presented","available_plans":brief,"plans_metadata":plans}

async def add_plan_to_cart_node(state:GraphState)->GraphState:
    token = os.getenv("CART_SESSION_ID")
    if not token:
        return {"progress":"end","ai_messages":[AIMessage(content="Cart token missing")]}

    cart = await _call_tool("cart__GetCart", cartId="", token=token,
                            **{"Authorization":"Bearer token","Content-Type":"application/json"})
    if not cart["success"]:
        return {"progress":"end","ai_messages":[AIMessage(content=cart["error"])]}
    cart_id = json.loads(cart["result"])["cart"]["cartId"]

    elig = json.loads(state["eligibility_response"])
    add  = await _call_tool("cart__AddToCart",
                            cartId=cart_id, eligibilityId=elig["eligibilityId"],
                            category="premium,unlimited", deleteLines=True,
                            isAccessory=False, lineType="ISP", transactionType="ACTIVATION",
                            fulfillment=[{"auditKey":"FULFILLMENTTYPE","auditValue":"SHIP-TO"}],
                            **{"Authorization":"Bearer token","Content-Type":"application/json"})
    if not add["success"]:
        return {"progress":"end","ai_messages":[AIMessage(content=add["error"])]}
    line_id = json.loads(add["result"])["cart"]["lines"][0]["id"]

    upd = await _call_tool("cart__UpdatePlans",
                           cartId=cart_id, lineId=line_id,
                           offerFamilyId=state["selected_plan_id"],
                           **{"Authorization":"Bearer token","Content-Type":"application/json"})
    if not upd["success"]:
        return {"progress":"end","ai_messages":[AIMessage(content=upd["error"])]}

    review_url = f"https://www.t-mobile.com/buy/cart?cartId={cart_id}"
    return {
        "progress"       : "plan_selected",
        "cart_id"        : cart_id,
        "line_id"        : line_id,
        "review_cart_url": review_url,
        "available_plans": None,
        "ai_messages"    : [AIMessage(content="✓ Plan added!")]
    }

# ──────────────── wire graph ────────────────
wf = StateGraph(GraphState)
wf.add_node("router", router_node)
wf.add_node("geocode_address", geocode_address_node)
wf.add_node("check_eligibility", check_eligibility_node)
wf.add_node("list_plans", list_plans_node)
wf.add_node("add_plan_to_cart", add_plan_to_cart_node)

wf.add_edge(START, "router")
for n in ("geocode_address","check_eligibility","list_plans"):
    wf.add_edge(n, "router")
wf.add_edge("add_plan_to_cart", END)

app = wf.compile()


async def main():
    # print(app.get_graph().draw_mermaid())
    result = await app.ainvoke({"user_messages":[HumanMessage(content="I want to get home internet for my new address")]})
    print(result)

if __name__ == "__main__":
    asyncio.run(main())


