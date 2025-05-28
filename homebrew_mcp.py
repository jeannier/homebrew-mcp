#!/usr/bin/env python
#
# homebrew_mcp.py - Homebrew MCP server for package management
#
# Features:
# - Publishes each Homebrew command as a separate MCP tool
# - Runs real 'brew $command' via subprocess for all supported commands
# - Logs all requests/results to homebrew_mcp.log with timestamp
# - MCP spec-compliant, no classes, functional style
#

from mcp.server.fastmcp import FastMCP
import json
import os # Used for path manipulation (e.g., LOG_FILE).
from datetime import datetime, timezone # For timestamping log entries.
import subprocess # For running external Homebrew commands.

# Initialize the FastMCP server instance with a descriptive name and set its log level.
# log_level="WARNING" will suppress INFO messages like "Processing request of type..."
# originating from the FastMCP server itself.
server = FastMCP("Homebrew Package MCP", log_level="WARNING")

# COMMANDS dictionary: Defines the Homebrew commands to be exposed as MCP tools.
# Each key is the command name (e.g., "install").
# The value is a dictionary specifying:
#   "desc": A description for the tool, used by clients like Claude.
#   "takes_package": A boolean indicating if the command requires a package name argument.
COMMANDS = {
    "install": {"desc": "Install a Homebrew package by name.", "takes_package": True},
    "uninstall": {"desc": "Uninstall a Homebrew package by name.", "takes_package": True},
    "info": {"desc": "Fetch Homebrew package info using Homebrew.", "takes_package": True},
    "upgrade": {"desc": "Upgrade a Homebrew package by name.", "takes_package": True},
    "list": {"desc": "List all Homebrew packages using Homebrew.", "takes_package": False},
    "search": {"desc": "Search for a Homebrew package.", "takes_package": True},
    "doctor": {"desc": "Check your system for potential Homebrew problems.", "takes_package": False},
    "reinstall": {"desc": "Reinstall a Homebrew package.", "takes_package": True},
    "outdated": {"desc": "List outdated Homebrew packages.", "takes_package": False},
}

# LOG_FILE: Defines the path to the log file where all server activity is recorded.
# It's placed in the same directory as the script.
LOG_FILE = os.path.join(os.path.dirname(__file__), "homebrew_mcp.log")

def log_request(action: str, package: str, success: bool, output: str, reply: str = None, command: str = None):
    """Log each tool call to homebrew_mcp.log as a JSON line.

    Includes timestamp, action, package (if any), success status, raw output from brew,
    the reply sent to the MCP client (if successful), and the exact brew command executed.
    This structured logging helps in debugging and auditing server operations.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(), # UTC timestamp in ISO format.
        "action": action,       # The Homebrew action (e.g., "install", "list").
        "package": package,     # The package name involved, if applicable.
        "success": success,     # Boolean indicating if the brew command was successful.
        "output": output,       # Raw stdout/stderr from the brew command.
        "reply": reply,         # The content sent back to the MCP client (usually same as output on success).
        "command": command,     # The full 'brew' command string that was executed.
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f: # Append to the log file.
        f.write(json.dumps(entry) + "\n") # Write each log entry as a new JSON line.

def run_brew_command(action: str, package: str = None):
    """Run a real Homebrew command using subprocess and return its success status, output, and the command string.

    Constructs a command list (e.g., ['brew', 'install', 'wget']).
    Executes the command, capturing its stdout and stderr.
    Handles successful execution (returncode 0) and errors.
    A timeout is set for the subprocess to prevent indefinite hanging.
    """
    cmd = ["brew", action] # Base command.
    if package:
        cmd.append(package) # Append package name if the action requires it.
    
    cmd_str = " ".join(cmd) # Create a string version of the command for logging.

    try:
        # Execute the command. capture_output=True gets stdout/stderr.
        # text=True decodes output as text. timeout prevents hanging.
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
        if result.returncode == 0:
            # Command was successful.
            return True, result.stdout.strip(), cmd_str
        # Command failed. Return stderr if available, otherwise stdout (some brew errors go to stdout).
        return False, (result.stderr.strip() or result.stdout.strip()), cmd_str
    except subprocess.TimeoutExpired:
        # Handle command timeout specifically.
        return False, f"Command '{cmd_str}' timed out after 60 seconds.", cmd_str
    except Exception as e:
        # Handle other potential exceptions during subprocess execution.
        return False, f"Command '{cmd_str}' failed with exception: {e}", cmd_str

def make_tool(action: str):
    """Dynamically creates and registers an MCP tool for a given Homebrew action.

    Uses the 'action' (e.g., "install") to look up metadata from the COMMANDS dictionary.
    It defines a nested function ('_tool') which becomes the actual handler for the MCP tool.
    This handler calls 'run_brew_command' and processes its result.
    If the brew command is successful, its output is returned to the MCP client.
    If it fails, a ValueError is raised with the error output, which MCP forwards as an error.
    Two versions of '_tool' are defined based on whether the command 'takes_package'.
    """
    # Get metadata (description, if it takes a package) from COMMANDS.
    # Defaults are provided if the action is not in COMMANDS (though it always should be here).
    meta = COMMANDS.get(action, {"desc": f"Run 'brew {action}' via subprocess.", "takes_package": False})
    desc = meta["desc"]
    takes_package = meta["takes_package"]

    if takes_package:
        # Define a tool handler for commands that require a 'package' argument.
        @server.tool(name=action, description=desc)
        def _tool(package: str) -> str: # Type hint: takes a string, returns a string.
            success, output, command_str = run_brew_command(action, package)
            if success:
                reply = output # On success, the reply is the command's output.
                log_request(action, package, success, output, reply, command_str)
                return reply
            # On failure, log the attempt and raise ValueError.
            # FastMCP catches ValueError and translates it into an MCP error response.
            log_request(action, package, success, output, None, command_str)
            raise ValueError(output)
        return _tool # Return the created tool handler function.
    else:
        # Define a tool handler for commands that do not take any arguments.
        @server.tool(name=action, description=desc)
        def _tool() -> str: # Type hint: takes no arguments, returns a string.
            success, output, command_str = run_brew_command(action)
            if success:
                reply = output
                log_request(action, "", success, output, reply, command_str) # Empty string for package.
                return reply
            log_request(action, "", success, output, None, command_str)
            raise ValueError(output)
        return _tool

# Register all defined Homebrew commands as MCP tools.
# This loop iterates through the keys of the COMMANDS dictionary (e.g., "install", "list")
# and calls make_tool() for each one, which creates and registers the corresponding tool.
for cmd_key in COMMANDS.keys():
    make_tool(cmd_key)

# Standard Python entry point: if this script is run directly, start the MCP server.
# server.run() starts the FastMCP server, listening for requests (e.g., over stdio).
if __name__ == "__main__":
    server.run()