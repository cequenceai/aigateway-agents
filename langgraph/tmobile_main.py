import logging, uuid, json
from contextlib import asynccontextmanager
from typing import Union, List, Annotated, Optional, defaultdict

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

from tmobile_workflow import app as tmobile_app   # compiled graph

# ─────────────── logging ───────────────
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

# ─────────────── FastAPI boilerplate ───────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("--- T-Mobile Workflow Server is starting up ---")
    yield
    logger.info("--- T-Mobile Workflow Server shut down ---")

conversation_state: dict[str, dict] = defaultdict(dict)

app = FastAPI(title="T-Mobile Workflow Server",
              description="Bot/Workflow backend",
              version="1.0.0",
              lifespan=lifespan)

# ─────────────── pydantic I/O models ───────────────
class InitializeResponse(BaseModel):
    conversation_id: str

class InvokeRequest(BaseModel):
    user_message: str

class InvokeResponse(BaseModel):
    ai_response     : Optional[Union[str, List]]
    review_cart_url : Optional[str] = None

# ─────────────── endpoints ───────────────
@app.post("/initialize", response_model=InitializeResponse)
async def initialize_session():
    cid = str(uuid.uuid4())
    logger.info("New session: %s", cid)
    return InitializeResponse(conversation_id=cid)

@app.post("/invoke", response_model=InvokeResponse)
async def invoke_workflow(request: InvokeRequest,
                          conversation_id: Annotated[str, Header(alias="X-Conversation-ID")]):

    if not conversation_id:
        raise HTTPException(400, "X-Conversation-ID header is missing")

    prev = conversation_state.get(conversation_id, {})
    inputs = {**prev,
              "progress": prev.get("progress", "start"),
              "user_messages": prev.get("user_messages", []) +
                               [HumanMessage(content=request.user_message)]}

    try:
        final_state = await tmobile_app.ainvoke(
            inputs,
            config={"configurable":{"thread_id":conversation_id},
                    "recursion_limit":50}
        )
    except Exception as e:
        logger.exception("Graph execution failed")
        raise HTTPException(500, str(e))

    # keep state
    conversation_state[conversation_id] = final_state

    # helpful server-side log
    logger.info("convo=%s  cart_id=%s", conversation_id, final_state.get("cart_id"))

    # choose response payload
    if final_state.get("progress") == "plans_presented" and final_state.get("available_plans"):
        return InvokeResponse(ai_response=final_state["available_plans"])

    return InvokeResponse(
        ai_response = (final_state["ai_messages"][-1].content
                       if final_state.get("ai_messages") else "✓"),
        review_cart_url = final_state.get("review_cart_url")
    )

@app.get("/")
def root():
    return {"status":"T-Mobile Workflow Server is running."}
