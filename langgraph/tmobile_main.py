import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional
import json
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage, HumanMessage

# Import the compiled app from the workflow file
from tmobile_workflow import app as tmobile_app

# --- Basic Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI App Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan. This is a good place for setup and teardown logic.
    """
    logger.info("--- T-Mobile Workflow Server is starting up ---")
    yield
    logger.info("--- T-Mobile Workflow Server has shut down ---")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="T-Mobile Workflow Server",
    description="A server for interacting with the T-Mobile Home Internet eligibility workflow.",
    version="1.0.0",
    lifespan=lifespan,
)

# --- Request and Response Models ---
class InitializeResponse(BaseModel):
    conversation_id: str = Field(..., description="A unique ID for the conversation session.")

class InvokeRequest(BaseModel):
    user_message: str = Field(..., description="The user's message to the agent, including the address.")

class InvokeResponse(BaseModel):
    ai_response: Optional[list]
    # progress: Optional[str] = Field(None, description="The current progress step in the workflow.")
    # is_eligible: Optional[bool] = Field(None, description="The eligibility status.")
    # available_plans: Optional[dict] = Field(None, description="The available service plans.")
    # cart_id: Optional[str] = Field(None, description="The ID of the created shopping cart.")


# --- API Endpoints ---
@app.post("/initialize", response_model=InitializeResponse)
async def initialize_session():
    """
    Initializes a new session and returns a unique conversation ID.
    """
    conversation_id = str(uuid.uuid4())
    logger.info(f"Initializing new session with ID: {conversation_id}")
    return InitializeResponse(conversation_id=conversation_id)

@app.post("/invoke", response_model=InvokeResponse)
async def invoke_workflow(
    request: InvokeRequest, 
    conversation_id: Optional[str] = Header(None, alias="X-Conversation-ID")
):
    """
    Invokes the workflow with a user message using the conversation ID from the header.
    """
    try:
        if not conversation_id:
            raise HTTPException(status_code=400, detail="X-Conversation-ID header is missing.")

        logger.info(f"Invoking workflow for conversation ID: {conversation_id}")
        config = {"configurable": {"thread_id": conversation_id}}
        
        # The first node in the workflow expects 'service_address_str'
        inputs = {"user_messages": [HumanMessage(content=request.user_message)]}
        
        # The tmobile_app is stateful when provided with a thread_id
        final_state = await tmobile_app.ainvoke(inputs, config=config)

        # Extract the last AI message from the state
        ai_content = final_state["available_plans"]
        # messages = final_state.get("messages", [])
        # if messages:
        #     last_message = messages[-1]
        #     if isinstance(last_message, AIMessage):
        #         if isinstance(last_message.content, str):
        #             ai_content = last_message.content
        #         elif isinstance(last_message.content, list):
        #             # Handle cases where content is a list of parts (e.g., from vision models)
        #             text_parts = [part.get('text', '') for part in last_message.content if part.get('type') == 'text']
        #             ai_content = "\n".join(text_parts)
        
        logger.info(f"Successfully invoked workflow for conversation: {conversation_id}")
        
        return InvokeResponse(
            ai_response=ai_content
        )

    except Exception as e:
        logger.error(f"An error occurred during workflow invocation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    """
    Root endpoint to confirm the server is running.
    """
    return {"status": "T-Mobile Workflow Server is running."} 