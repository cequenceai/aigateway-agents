import asyncio
import os
import logging
import json
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages.utils import trim_messages, count_tokens_approximately
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Environment Variable and API Key Checks ---
ANTHROPIC_API_KEY_LOADED = bool(os.getenv("ANTHROPIC_API_KEY"))
OPENAI_API_KEY_LOADED = bool(os.getenv("OPENAI_API_KEY"))

if not ANTHROPIC_API_KEY_LOADED and not OPENAI_API_KEY_LOADED:
    logger.error("Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY environment variables found. LLM calls will fail.")
else:
    logger.info(f"Anthropic API Key loaded: {ANTHROPIC_API_KEY_LOADED}")
    logger.info(f"OpenAI API Key loaded: {OPENAI_API_KEY_LOADED}")


# The agent will connect directly to a specific tool server.
# The URL can be configured via this environment variable for standalone testing.
DEFAULT_SERVER_URL = "https://ztaid-35g20z5w-e4l2dawa5a-uc.a.run.app/mcp"
logger.info(f"Default Tool Server URL for testing: {DEFAULT_SERVER_URL}")

# --- Agent Configuration ---
def get_model():
    """
    Initializes and returns a Chat model based on available API keys.
    Prefers Claude (Anthropic) if available, otherwise falls back to OpenAI.
    """
    if ANTHROPIC_API_KEY_LOADED:
        logger.info("Using Anthropic model (Claude).")
        return ChatAnthropic(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1024,
            temperature=0.0,
            max_retries=3,
        )
    elif OPENAI_API_KEY_LOADED:
        logger.info("Using OpenAI model (GPT-4o mini).")
        return ChatOpenAI(
            model="gpt-4o-mini",
            max_tokens=1024,
            temperature=0.0,
            max_retries=3,
        )
    else:
        logger.error("No LLM API key found. Cannot create a model.")
        return None

def pre_model_hook(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trims the message history to fit within the model's context window.
    This hook is called before the model is invoked. It keeps the original
    message history in the state unmodified and passes the trimmed history
    to the LLM under the 'llm_input_messages' key.
    """
    trimmed_messages = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=4096,  # A reasonable limit for many models
        start_on="human",
        end_on=("human", "tool"),
    )
    return {"llm_input_messages": trimmed_messages}

SYSTEM_PROMPT = """
Purpose: Guide a customer through the selction of a T-Mobile Home Internet plan.

Process Workflow:

1. When the user prompts that he wants to sign up for a home internet plan, the agent should ask for the home address which includes the house number or apartment number, apartment name, street address, city, state, zip code.

Example entry for the address is: 3636 WARNER DR, SAN JOSE, CA 95127

2. The agent should use the geocoding tool to get the latitude and longitude of the address along with the system generated location key.

Example request json:
{
  "address": "13708 GILLETTE ST, OVERLAND PARK, KS 66221",
  "street1": "13708 GILLETTE ST",
  "street2": "",
  "city": "OVERLAND PARK",
  "state": "KS",
  "zipCode": "66221"
}

3. The agent should use the eligibility tool to check if the address is eligible for T-Mobile Home Internet by using the location key, latitude, longitude, and address. if the address is eligible, the agent should proceed to step 4. if the address is not eligible, the agent should inform the user that the address is not eligible for T-Mobile Home Internet and end the conversation.

Example request JSON:
{
  "city": "OVERLAND PARK",
  "state": "KS",
  "address": "13708 GILLETTE ST, OVERLAND PARK, KS 66221",
  "street1": "13708 GILLETTE ST",
  "street2": "",
  "zipCode": "66221",
  "coordinates": {
    "lat": "38.880704",
    "lng": "-94.736211"
  },
  "locationKey": "P00002T31592",
  "Content-Type": "application/json",
  "Authorization": "Bearer token",
  "fiberLocationKey": "P00002T31592"
}

4. If the address is eligible, the agent should check for the available plans for the address and present the options to the user. The agent should pass along all the details collected from step 3 in the tool call it makes to get the available plans. The agent should also create an empty cart in the background that will be used to add the selected plan to the cart once the user selects the plan in later steps. The agent should provide a nice summary of the plans available to the user along with any comparison of the plans.

Example request json:
{
  "transactionType": "ACTIVATION",
  "planType": "ISP",
  "requestedLineNumber": 1,
  "accountSubtype": "INDIVIDUAL_REGULAR",
  "productSubCategories": [
    "Home Internet"
  ],
  "planTags": [
    "premium",
    "unlimited"
  ],
  "applyDiscount": true,
  "includePromotions": true,
  "geoSegments": [
    "nationwide"
  ]
}

5. The agent should ask the user to select the plan they want to subscribe to. The agent should use the cart tool to add the user selected plan to the cart. The agent should provide the cart id of the empty cart created in step 4, along with all applicable fields collected from steps 3 and 4 in the tool call it makes to add the plan to the cart. The agent should provide a nice summary of the plan selected by the user along with the cost of the plan.

6. The agent should ask the user to provide the personal information required for the credit check. The agent should use the credit check tool to check the credit of the user. The necessary personal information required includes full name, social security number (last 4 digits or full SSN as required), date of birth, valid email address, and billing address (if different from service address). The agent should explain the credit check process and its purpose to the user. 

7. The agent should ask the user to provide consent to run the credit check. The agent should use the credit check tool to run the credit check. If the credit check is successful, the agent should proceed to step 8. If the credit check is not successful, the agent should inform the user that the credit check is not successful and end the conversation. The agent should provide a brief summary of the credit check results to the user. 


It is very important to include all the fields as per above examples in the requests to the MCP tool calls.
"""
async def create_agent_executor(server_url: str, server_id: str = "mcp_server", system_prompt: Optional[str] = SYSTEM_PROMPT):
    """
    Creates and returns a LangGraph agent executor with memory.
    The agent is configured to connect to a given MCP server to fetch tools.
    """
    logger.info(f"Initializing agent executor for server: {server_url}")
    
    model = get_model()
    if not model:
        logger.error("Failed to get a valid model. Agent creation aborted.")
        return None
        
    checkpointer = InMemorySaver()
    
    # Configure the client to connect directly to the tool server.
    server_config = {
        server_id: {
            "url": server_url,
            "transport": "streamable_http"
        }
    }
    
    try:
        # As of langchain-mcp-adapters 0.1.0, MultiServerMCPClient cannot be used
        # as a context manager. It should be instantiated directly.
        client = MultiServerMCPClient(server_config)
        logger.info("Fetching tools from Tool Server...")
        tools = await client.get_tools()
            
        if not tools:
            logger.error("No tools fetched from the server. Agent will not have tool capabilities.")
        else:
            tool_names = [tool.name for tool in tools]
            logger.info(f"Successfully fetched {len(tools)} tools: {tool_names}")

        agent_executor = create_react_agent(
            model,
            tools=tools,
            pre_model_hook=pre_model_hook,
            checkpointer=checkpointer,
        )
        logger.info("Agent executor created successfully.")
        return agent_executor

    except Exception as e:
        logger.error(f"Failed to create agent executor: {e}", exc_info=True)
        return None

async def run_agent_conversation():
    """
    An example function to demonstrate how to use the agent executor.
    It simulates a conversation with the agent.
    """
    # For standalone testing, we use the default server URL.
    agent_executor = await create_agent_executor(DEFAULT_SERVER_URL, "santacruzbank-mcp")
    if not agent_executor:
        logger.error("Exiting due to agent creation failure.")
        return

    # A unique ID for the conversation thread
    conversation_id = "my-conv-123"
    config = {"configurable": {"thread_id": conversation_id}}

    prompts = [
        "Hi there! What are the tools available?",
        "Log into the account for me using the credentials provided: email: saurabhyadgire@gmail.com, password: 12345678",
        "okay great, now get the financial details using my password as user ID [that is my user ID LOL]",
    ]

    for prompt in prompts:
        print(f"\n--- User Prompt: {prompt} ---\n")
        
        # The input to the graph is a list of messages
        inputs = {"messages": [("user", prompt)]}
        result = await agent_executor.ainvoke(inputs, config=config)
        print("--AI Response--")
        
        # The `result` contains the full message history. We only want to print
        # the last message, which is the AI's direct response to the prompt.
        if result and 'messages' in result and result['messages']:
            last_message = result['messages'][-1]

            if isinstance(last_message, AIMessage):
                # AIMessage content can be a string (for simple text responses) or a list
                # (for responses that include text and tool calls). We just print the text.
                if isinstance(last_message.content, str):
                    print(last_message.content)
                elif isinstance(last_message.content, list):
                    for part in last_message.content:
                        if part.get('type') == 'text':
                            print(part.get('text'))
            else:
                # Fallback in case the last message is not from the AI as expected.
                print(last_message)
        else:
            # Fallback if the result format is unexpected.
            print(result)
            
        print("\n--- End of Agent Response ---\n")

    # To show that history is being maintained, let's inspect the state
    final_state = await agent_executor.aget_state(config)
    # print("\n--- Final Conversation State ---")
    # print(json.dumps(final_state.values, indent=2, default=str))

async def main():
    """
    Main asynchronous function to run the agent conversation for testing.
    """
    # To run this example, ensure you have an MCP-compatible server running
    # and the necessary environment variables (.env file) are set.
    await run_agent_conversation()

if __name__ == "__main__":
    # The main entry point of the script for standalone testing.
    asyncio.run(main()) 
    # create react agent with memor
