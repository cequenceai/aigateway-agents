# MCP Agent Server

This project provides a ready-to-use FastAPI server for hosting a conversational LangGraph agent. The agent is capable of connecting to any MCP-compatible tool server, using memory to maintain conversation history, and dynamically selecting a language model (Anthropic's Claude or OpenAI's GPT) based on available API keys.

## Features

- **Conversational Memory**: The agent remembers previous turns in the conversation.
- **Dynamic Tool Connection**: Connect to any MCP tool server by providing its URL.
- **Dynamic Model Selection**: Automatically uses the Claude 3.5 Sonnet model if an `ANTHROPIC_API_KEY` is available, otherwise falls back to GPT-4o Mini if an `OPENAI_API_KEY` is available.
- **FastAPI Server**: Exposes the agent through a robust and easy-to-use REST API.
- **Interactive API Docs**: Test and interact with the agent directly from your browser.

## Prerequisites

- Python 3.9+
- An MCP-compatible tool server to connect to.
- API keys for Anthropic or OpenAI.

## 1. Installation

Clone the repository and install the dependencies. It is recommended to create a virtual environment to manage dependencies.

```bash
# Create and activate a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

# Install the required dependencies
pip install -r requirements.txt
```

## 2. Configuration

Create a `.env` file in the project's root directory. This file will store your secret API keys.

```bash
# Example .env file
# You only need to provide one of the two keys.
# If both are provided, the Anthropic key will be used by default.

ANTHROPIC_API_KEY="sk-ant-..."
OPENAI_API_KEY="sk-..."
```

## 3. Running the Server

Once the dependencies are installed and your `.env` file is configured, you can start the FastAPI server using Uvicorn.

Run the following command from the root of the project directory:

```bash
uvicorn main:app --reload
```

The `--reload` flag enables hot-reloading, so the server will automatically restart when you make code changes. The server will be available at `http://127.0.0.1:8000`.

## 4. Using the API

The best way to interact with the API is through the built-in interactive documentation.

1.  **Open the Docs**: Navigate to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) in your browser.

2.  **Initialize the Agent**:
    - Find the `POST /initialize` endpoint.
    - Click "Try it out".
    - In the `Request body`, enter the URL of your MCP tool server (e.g., `https://ztaid-35g20z5w-e4l2dawa5a-uc.a.run.app/mcp`).
    - Execute the request. You will receive a unique `conversation_id` in the response.

3.  **Authorize Your Session**:
    - At the top of the page, click the green **"Authorize"** button.
    - Paste the `conversation_id` you received into the `X-Conversation-ID` value field and click "Authorize".

4.  **Invoke the Agent**:
    - Find the `POST /invoke` endpoint.
    - Click "Try it out".
    - The `X-Conversation-ID` will now be automatically included in your requests.
    - Enter your message in the `user_message` field in the request body.
    - Execute the request to get the AI's response. You can continue sending messages to this endpoint to carry on the conversation.

## Standalone Testing

You can also test the agent's core logic without running the FastAPI server. The `react_agent_with_memory.py` script can be run directly from the project root.

```bash
python react_agent_with_memory.py
```

This will run a pre-defined sequence of prompts against the default MCP server URL specified in the script and print the conversation to the console. 