import sys, asyncio
from dotenv import load_dotenv
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load API key and other variables from .env
load_dotenv()

# Constants: Model name and max token count
MODEL = "claude-3-5-sonnet-20241022"
MAX_TOKENS = 1000

# Retrieve the list of available tools from the session
async def list_tools(session):
    resp = await session.list_tools()
    return [
        {"name": t.name, "description": t.description, "input_schema": t.inputSchema}
        for t in resp.tools
    ]

# Wrapper for calling the Anthropic Messages API
# → system prompts are passed as top-level arguments
def llm_call(anth, messages, tools=None, system=None):
    params = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
    }
    if tools:
        params["tools"] = tools
    if system:
        params["system"] = system
    return anth.messages.create(**params)

# Logic for handling tool usage
async def handle_tool(part, session, anth, messages, llm_text):
    # Add explanation text before calling the tool
    prompt = getattr(part, "text", "")
    if prompt:
        llm_text.append(prompt)
        messages.append({"role": "assistant", "content": prompt})

    # Actually call the tool
    result = await session.call_tool(part.name, part.input)

    # Add the tool result as a user message to the conversation
    if isinstance(result.content, str):
        user_input = result.content
    else:
        user_input = "".join(getattr(item, "text", str(item)) for item in result.content)
    messages.append({"role": "user", "content": user_input})

    # Follow-up call to LLM and process result
    followup = llm_call(anth, messages)
    for p in followup.content:
        if p.type == "text":
            llm_text.append(p.text)
            messages.append({"role": "assistant", "content": p.text})

# Main process: from MCP server connection to interaction loop
async def main(server_script: str, query: str):
    # Determine server execution command (.py → python, .js → node)
    cmd = "python" if server_script.endswith(".py") else "node"
    params = StdioServerParameters(command=cmd, args=[server_script])

    # Connect to the MCP server via stdio and start the session
    async with stdio_client(params) as (stdio, write), ClientSession(stdio, write) as session:
        await session.initialize()

        # Retrieve tools and create LLM client
        tools = await list_tools(session)
        anth = Anthropic()

        # Store initial user query in messages
        messages = [{"role": "user", "content": query}]
        ai_resp = llm_call(anth, messages, tools=tools)

        # Process LLM response parts and print to console
        llm_text: list[str] = []
        for part in ai_resp.content:
            if part.type == "text":
                llm_text.append(part.text)
                messages.append({"role": "assistant", "content": part.text})
            elif part.type == "tool_use":
                await handle_tool(part, session, anth, messages, llm_text)
            # Show the most recent text
            print(llm_text[-1])

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python client.py <path_to_server.py|.js> <query>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))

