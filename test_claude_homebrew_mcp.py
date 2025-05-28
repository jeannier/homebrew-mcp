#!/usr/bin/env python
#
# test_claude_homebrew.py - Interactive test for Homebrew MCP server with Claude API
#
# Features:
# - Launches homebrew_mcp.py via MCP stdio
# - Dynamically lists available Homebrew tools from MCP for Claude
# - Interacts with Claude (Anthropic API) using user input and tool calls
# - Prints all results to stdout
#

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import anthropic
import asyncio
import logging

# Configure logging to suppress INFO messages from the mcp library and httpx
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s', force=True)
logging.getLogger("httpx").setLevel(logging.WARNING) # Also quiet down httpx as it's noisy

# Define server parameters to run the Homebrew MCP server
server_params = StdioServerParameters(
    command="uv",
    args=["run", "python", "homebrew_mcp.py"],
    env=None
)

ANTHROPIC_API_KEY = "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"

# Example prompts to exercise each command
PROMPTS = [
    "install wget if not installed, or uninstall if already installed",
    "restore initial state of wget",
    "check for outdated packages",
    "provide a summary of all installed packages",
    "provide suggestions of other packages to install",
    "use brew doctor to see if there are any issues, try to find a fix for all of these issues",
    'provide a summary of what was done'
]

def format_tools_for_claude(mcp_tools_list):
    """Formats a list of MCP Tool objects to the structure Claude expects."""
    claude_tools = []
    for tool in mcp_tools_list: # Iterate over the list of Tool objects
        properties = {}
        # Safely access inputSchema, defaulting to an empty dict if not present or not a dict.
        # MCP tool.inputSchema contains parameter definitions.
        input_schema_dict = getattr(tool, 'inputSchema', {})
        # Safely access 'properties' within inputSchema, defaulting to empty dict if key is missing.
        # 'properties' holds the actual parameter name-to-definition mappings.
        parameter_definitions = input_schema_dict.get('properties', {})

        for param_name, param_details in parameter_definitions.items():
            # Default to 'string' if 'type' is not specified for a parameter.
            param_type = param_details.get('type', 'string')
            properties[param_name] = {"type": param_type}

        # Construct the tool definition in the JSON Schema format required by Claude API.
        if not tool.description:
            # Fail if a tool has no description.
            raise ValueError(f"Tool '{tool.name}' is missing a description. All tools must have a description.")
        claude_tools.append({
            "name": tool.name,
            "description": tool.description, # Use the validated description.
            "input_schema": {
                "type": "object",
                "properties": properties
            }
        })
    return claude_tools

async def run():
    """Run an interactive Claude + MCP Homebrew test."""
    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # session.list_tools() returns a result object (e.g., ListToolsResult).
            # The actual list of MCP Tool objects is in its .tools attribute.
            mcp_tools_result = await session.list_tools()
            print(f"\033[94m[MCP] Discovered raw tools result from server (MCP format): {mcp_tools_result}\033[0m")
            
            # Extract the list of Tool objects, defaulting to an empty list if not found.
            actual_mcp_tools_list = mcp_tools_result.tools if mcp_tools_result and hasattr(mcp_tools_result, 'tools') else []
            
            # Fail if no tools are discovered from the MCP server.
            if not actual_mcp_tools_list:
                raise RuntimeError("No tools discovered from the MCP server. At least one tool is required.")
            
            print(f"\033[94m[MCP] Number of tools found (MCP server count): {len(actual_mcp_tools_list)}\033[0m")

            # Convert MCP Tool objects to the format expected by the Claude API.
            tools_for_claude = format_tools_for_claude(actual_mcp_tools_list)
            print(f"\033[94m[MCP] Formatted tools for Claude (Claude API format): {tools_for_claude}\033[0m")
            
            print(f"\033[94m[MCP] Number of tools formatted for Claude: {len(tools_for_claude)}\033[0m")

            conversation = []
            total_prompts = len(PROMPTS)
            for idx, prompt in enumerate(PROMPTS, 1):
                print(f"\n\033[1;30m===== Claude Prompt {idx}/{total_prompts} =====\n{prompt}\n========================\033[0m\n")
                conversation.append({"role": "user", "content": prompt})
                
                # Main interaction loop: continues until Claude responds without requesting tools.
                # This allows Claude to make multiple tool calls for a single user prompt.
                while True:
                    response = anthropic_client.messages.create(
                        model="claude-3-7-sonnet-latest",
                        max_tokens=1000,
                        messages=conversation,
                        tools=tools_for_claude,
                    )
                    
                    # Check if Claude's response includes any tool use requests.
                    tool_calls = [block for block in getattr(response, 'content', []) if getattr(block, 'type', None) == "tool_use"]
                    
                    if tool_calls:
                        # Append Claude's response (which includes tool_use blocks) to the conversation history.
                        # This gives Claude context of its own reasoning that led to the tool calls.
                        conversation.append({"role": "assistant", "content": response.content})
                        
                        for tool_call in tool_calls:
                            print(f"\033[92m[MCP] Claude requested tool: {tool_call.name} with input: {tool_call.input}\033[0m")
                            tool_name = tool_call.name
                            tool_input = tool_call.input
                            # Execute the tool call via the MCP session.
                            result = await session.call_tool(tool_name, arguments=tool_input)
                            print(f"\033[92m[MCP] Tool reply: {result}\033[0m")
                            
                            # Extract plain text content from the MCP tool result for Claude.
                            # MCP tool results can be simple strings or structured objects.
                            if isinstance(result, str):
                                tool_content = result
                            elif hasattr(result, "content") and result.content and hasattr(result.content[0], "text"):
                                # Handles results like mcp.types.ToolResult with TextContent.
                                tool_content = result.content[0].text
                            else:
                                # Fallback to string representation for other result types.
                                tool_content = str(result)
                            
                            # Prepare the tool result message in the format Claude expects.
                            tool_result_message = {
                                "role": "user", # Critically, tool results are passed as "user" role messages.
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": tool_call.id, # Link to the specific tool_use request.
                                        "content": tool_content,   # The processed output of the tool.
                                    }
                                ],
                            }
                            conversation.append(tool_result_message)
                        
                        # After processing all tool calls for this turn, send the updated conversation
                        # back to Claude to get its next response (which might be more tool calls or a final answer).
                        continue
                    else:
                        # If there are no tool calls, Claude has provided its final textual answer.
                        print("\033[93m[MCP] Claude made no tool requests.\033[0m")
                        if hasattr(response, 'content') and response.content:
                            print("\n\033[95m=== Claude's Answer ===\033[0m")
                            print(f"\033[95m{response.content[0].text.strip()}\033[0m")
                            print("\033[95m============================\033[0m\n")
                        # Break the inner while loop to move to the next user prompt (if any).
                        break

if __name__ == "__main__":
    asyncio.run(run()) 