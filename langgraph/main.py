import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Optional

from react_agent_with_memory import create_agent_executor, AIMessage

# --- Basic Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# --- In-Memory Cache for Agent Executors ---
# A simple dictionary to cache agent executors based on the conversation ID.
agent_cache = {}

# --- Security and Header Configuration ---
api_key_header = APIKeyHeader(name="X-Conversation-ID", auto_error=False)

# --- FastAPI App Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan. This is a good place for setup and teardown logic.
    """
    logger.info("--- Agent Server is starting up ---")
    yield
    # Clean up resources on shutdown
    agent_cache.clear()
    logger.info("--- Agent Server has shut down ---")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="MCP Agent Server",
    description="A server for initializing and interacting with LangGraph ReAct agents.",
    version="1.0.0",
    lifespan=lifespan,
)

# --- Request and Response Models ---
class InitializeRequest(BaseModel):
    mcp_url: str = Field(..., description="The URL of the MCP-compatible tool server.")

class InitializeResponse(BaseModel):
    conversation_id: str = Field(..., description="A unique ID for the conversation session.")

class InvokeRequest(BaseModel):
    user_message: str = Field(..., description="The user's message to the agent.")

class InvokeResponse(BaseModel):
    ai_response: str

# --- API Endpoints ---
@app.post("/initialize", response_model=InitializeResponse)
async def initialize_agent(request: InitializeRequest):
    """
    Initializes a new agent instance for a given MCP URL and returns a unique conversation ID.
    """
    try:
        conversation_id = str(uuid.uuid4())
        logger.info(f"Initializing new agent for URL: {request.mcp_url} with ID: {conversation_id}")
        
        agent_executor = await create_agent_executor(request.mcp_url)
        if not agent_executor:
            raise HTTPException(status_code=500, detail="Failed to create agent executor.")
            
        agent_cache[conversation_id] = agent_executor
        logger.info(f"Cached new agent for conversation ID: {conversation_id}")
        
        return InitializeResponse(conversation_id=conversation_id)
        
    except Exception as e:
        logger.error(f"An error occurred during agent initialization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/invoke", response_model=InvokeResponse)
async def invoke_agent(
    request: InvokeRequest, 
    conversation_id: Optional[str] = Header(None, alias="X-Conversation-ID")
):
    """
    Invokes an existing agent with a user message using the conversation ID from the header.
    """
    try:
        if not conversation_id:
            raise HTTPException(status_code=400, detail="X-Conversation-ID header is missing.")

        agent_executor = agent_cache.get(conversation_id)
        if not agent_executor:
            raise HTTPException(status_code=404, detail="Conversation ID not found. Please initialize the agent first.")

        logger.info(f"Invoking agent for conversation ID: {conversation_id}")
        config = {"configurable": {"thread_id": conversation_id}}
        inputs = {"messages": [("user", request.user_message)]}
        
        result = await agent_executor.ainvoke(inputs, config=config)

        if result and 'messages' in result and result['messages']:
            last_message = result['messages'][-1]
            if isinstance(last_message, AIMessage):
                ai_content = ""
                if isinstance(last_message.content, str):
                    ai_content = last_message.content
                elif isinstance(last_message.content, list):
                    text_parts = [part.get('text', '') for part in last_message.content if part.get('type') == 'text']
                    ai_content = "\n".join(text_parts)
                
                logger.info(f"Successfully got AI response for conversation: {conversation_id}")
                return InvokeResponse(ai_response=ai_content)

        raise HTTPException(status_code=500, detail="Failed to get a valid AI response from the agent.")

    except Exception as e:
        logger.error(f"An error occurred during agent invocation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    """
    Root endpoint to confirm the server is running.
    """
    return {"status": "MCP Agent Server is running."} 