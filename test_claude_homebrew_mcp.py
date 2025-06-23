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
import asyncio
import logging
import sys

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configure logging to show only the message.
logging.basicConfig(level=logging.INFO, format='%(message)s', force=True)
logger = logging.getLogger("claude_test")

# Suppress noisy logs from other libraries by setting their level higher.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("mcp.client.stdio").setLevel(logging.WARNING)
logging.getLogger("mcp.shared.session").setLevel(logging.WARNING)
logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)

# Define server parameters to run the Homebrew MCP server
server_params = StdioServerParameters(
    command="uv",
    args=["run", "python", "homebrew_mcp.py"],
    env=None
)

# --- Anthropic API Key Configuration ---
# IMPORTANT: Replace the dummy key below with your actual Anthropic API key.
ANTHROPIC_API_KEY = "sk-ant-api03-DUMMY_KEY_Abc123_DO_NOT_USE-THIS_IS_A_PLACEHOLDER_DeF456"

# Example prompts to exercise each command
PROMPTS = [
    "install wget if not installed, or uninstall if already installed",
    "restore initial state of wget",
    "check for outdated packages",
    "provide a summary of all installed packages",
    "provide 5 suggestions of other packages to install",
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
    anthropic_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    log_width = 80 # Define a fixed width for aligned logging

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            mcp_tools_result = await session.list_tools()
            logger.debug("Discovered raw tools result from server (MCP format): %s", mcp_tools_result)
            
            actual_mcp_tools_list = mcp_tools_result.tools if mcp_tools_result and hasattr(mcp_tools_result, 'tools') else []
            
            if not actual_mcp_tools_list:
                raise RuntimeError("No tools discovered from the MCP server. At least one tool is required.")
            
            logger.debug("Number of tools found (MCP server count): %d", len(actual_mcp_tools_list))

            tools_for_claude = format_tools_for_claude(actual_mcp_tools_list)
            logger.debug("Formatted tools for Claude (Claude API format): %s", tools_for_claude)
            
            logger.debug("Number of tools formatted for Claude: %d", len(tools_for_claude))

            conversation = []
            total_prompts = len(PROMPTS)
            for idx, prompt in enumerate(PROMPTS, 1):
                prompt_header = f" Claude Prompt {idx}/{total_prompts} ".center(log_width, '=')
                logger.info("\n%s\n%s\n%s", prompt_header, prompt, '=' * log_width)
                conversation.append({"role": "user", "content": prompt})
                
                try:
                    while True:
                        response = await anthropic_client.messages.create(
                            model="claude-3-7-sonnet-latest",
                            max_tokens=1000,
                            messages=conversation,
                            tools=tools_for_claude,
                        )
                        
                        tool_calls = [block for block in getattr(response, 'content', []) if getattr(block, 'type', None) == "tool_use"]
                        
                        if not tool_calls:
                            logger.debug("Claude made no tool requests.")
                            if hasattr(response, 'content') and response.content:
                                answer_text = response.content[0].text.strip()
                                answer_header = f" Claude's Answer {idx}/{total_prompts} ".center(log_width, '=')
                                logger.info("%s\n%s\n%s", answer_header, answer_text, '=' * log_width)
                            break

                        conversation.append({"role": "assistant", "content": response.content})
                        
                        for tool_call in tool_calls:
                            logger.debug("Claude requested tool: %s with input: %s", tool_call.name, tool_call.input)
                            result = await session.call_tool(tool_call.name, arguments=tool_call.input)
                            logger.debug("Tool reply: %s", result)
                            
                            tool_content = str(result)
                            if isinstance(result, str):
                                tool_content = result
                            elif hasattr(result, "content") and result.content and hasattr(result.content[0], "text"):
                                tool_content = result.content[0].text
                            
                            conversation.append({
                                "role": "user",
                                "content": [{"type": "tool_result", "tool_use_id": tool_call.id, "content": tool_content}],
                            })

                except anthropic.AuthenticationError:
                    logger.error("Fatal Error: Authentication failed. The API key is invalid or has expired.")
                    sys.exit(1)
                except Exception as e:
                    logger.exception("An unexpected error occurred during API interaction: %s", e)
                    sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run()) 