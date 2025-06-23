#!/usr/bin/env python
#
# homebrew_mcp.py - Homebrew MCP server for package management on macOS
#
# Description:
# A Model Context Protocol (MCP) server that exposes Homebrew package management
# functionality to MCP clients like Claude Desktop. Designed for seamless integration
# with LLMs and AI assistants.
#
# Features:
# - Exposes Homebrew commands as individual MCP tools
# - Runs real 'brew' commands via subprocess for authentic behavior
# - Logs all requests/results as structured JSON to homebrew_mcp.log
# - MCP spec-compliant (stdio, JSON-RPC 2.0, MCP spec 2025-06-18)
# - Functional, declarative Python style (no classes in main logic)
#
# Requirements:
# - Python 3.13+ (uses modern type hints and features)
# - macOS with Homebrew installed
# - MCP Python SDK (>=1.9.4)
#

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# --- Setup Logging ---

class JsonFormatter(logging.Formatter):
    """Formats log records as a single line of JSON."""
    def format(self, record):
        # This custom formatter ensures that all log output is structured as JSON,
        # which is easier for other tools to parse.
        super().format(record)  # This populates record.message and other standard fields.
        # The ** operator unpacks the message if it's a dictionary, allowing
        # structured data to be merged directly into the JSON log.
        return json.dumps({
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "name": record.name,
            **(record.msg if isinstance(record.msg, dict) else {"message": record.message})
        })

# Initialize logger with structured JSON output
logger = logging.getLogger("homebrew_mcp")
logger.setLevel(logging.INFO)
logger.propagate = False  # Avoid duplicate logs to any root logger.

# Set up log file in same directory as script
log_file_path = Path(__file__).parent / "homebrew_mcp.log"
file_handler = logging.FileHandler(log_file_path)
file_handler.setFormatter(JsonFormatter())
logger.addHandler(file_handler)

# Suppress noisy INFO logs from the underlying MCP server library
logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)


# --- Configuration ---

# This dictionary is the central configuration for dynamic tool generation.
# Each key is a command name, and its value defines the tool's description,
# parameters, and command-line options. The server uses this structure to
# build and register all MCP tools automatically.
COMMANDS = {
    "install": {
        "description": "Installs the given formula or cask.",
        "params": [
            {"name": "names", "type": "list", "required": True, "help": "Name of the formula(e) or cask(s) to install."},
        ],
        "options": [
            {"name": "cask", "flag": "--cask", "type": "bool", "help": "Treat all named arguments as casks."},
            {"name": "force", "flag": "--force", "short_flag": "-f", "type": "bool", "help": "Install without checking for previous installations."},
            {"name": "verbose", "flag": "--verbose", "short_flag": "-v", "type": "bool", "help": "Print verbose output."},
            {"name": "dry_run", "flag": "--dry-run", "type": "bool", "help": "Show what would be installed, but do not actually install anything."},
            {"name": "build_from_source", "flag": "--build-from-source", "short_flag": "-s", "type": "bool", "help": "Compile from source."},
            {"name": "HEAD", "flag": "--HEAD", "type": "bool", "help": "Install the development version."},
        ]
    },
    "uninstall": {
        "description": "Uninstalls the given formula or cask.",
        "params": [
            {"name": "names", "type": "list", "required": True, "help": "Name of the formula(e) or cask(s) to uninstall."},
        ],
        "options": [
            {"name": "cask", "flag": "--cask", "type": "bool", "help": "Treat all named arguments as casks."},
            {"name": "force", "flag": "--force", "short_flag": "-f", "type": "bool", "help": "Force uninstallation."},
            {"name": "zap", "flag": "--zap", "type": "bool", "help": "Remove all files associated with a cask."},
        ]
    },
    "untap": {
        "description": "Removes the given tap(s).",
        "params": [
            {"name": "names", "type": "list", "required": True, "help": "Name of the tap(s) to remove."},
        ],
        "options": []
    },
    "upgrade": {
        "description": "Upgrades outdated casks and formulae.",
        "params": [
            {"name": "names", "type": "list", "required": False, "help": "Name of the specific formula(e) or cask(s) to upgrade."},
        ],
        "options": [
            {"name": "cask", "flag": "--cask", "type": "bool", "help": "Only upgrade casks."},
            {"name": "greedy", "flag": "--greedy", "type": "bool", "help": "Also upgrade casks with `auto_updates` true."},
            {"name": "dry_run", "flag": "--dry-run", "type": "bool", "help": "Show what would be upgraded, without actually upgrading."},
            {"name": "force", "flag": "--force", "short_flag": "-f", "type": "bool", "help": "Force upgrade of casks even if they are already installed."}
        ]
    },
    "list": {
        "description": "Lists installed formulae or casks.",
        "params": [],
        "options": [
            {"name": "cask", "flag": "--cask", "type": "bool", "help": "List only installed casks."},
            {"name": "versions", "flag": "--versions", "type": "bool", "help": "Show the version number for installed formulae."},
            {"name": "pinned", "flag": "--pinned", "type": "bool", "help": "List only pinned formulae."},
        ]
    },
    "search": {
        "description": "Performs a search of formulae and casks.",
        "params": [
            {"name": "query", "type": "str", "required": True, "help": "The search query, can be text or a /regex/."},
        ],
        "options": [
            {"name": "casks", "flag": "--casks", "type": "bool", "help": "Search only casks."},
        ]
    },
    "info": {
        "description": "Displays information about a formula or cask.",
        "params": [
            {"name": "name", "type": "str", "required": True, "help": "Name of the formula or cask."},
        ],
        "options": [
            {"name": "json_format", "flag": "--json", "type": "str", "help": "Output in JSON format. Use 'v2' for the latest version."},
        ]
    },
    "doctor": {
        "description": "Checks your system for potential problems.",
        "params": [],
        "options": []
    },
    "update": {
        "description": "Fetches the newest version of Homebrew and all formulae.",
        "params": [],
        "options": []
    },
    "outdated": {
        "description": "Shows formulae and casks that have an updated version available.",
        "params": [],
        "options": [
             {"name": "cask", "flag": "--cask", "type": "bool", "help": "List only outdated casks."},
             {"name": "greedy", "flag": "--greedy", "type": "bool", "help": "Also list casks with `auto_updates` true."},
        ]
    },
    "cleanup": {
        "description": "Removes stale lock files and outdated downloads for a specific formula or cask, or for all if none is specified.",
        "params": [
            {"name": "name", "type": "str", "required": False, "help": "Specific formula or cask to clean up."},
        ],
        "options": [
            {"name": "dry_run", "flag": "--dry-run", "short_flag": "-n", "type": "bool", "help": "Show what would be removed."},
            {"name": "scrub_cache", "flag": "-s", "type": "bool", "help": "Scrub the cache of downloaded files."},
        ]
    },
    "services": {
        "description": "Manages Homebrew services.",
        # Special case: services command requires subcommand structure
        "base_command": ["services"],
        "params": [
            {"name": "subcommand", "type": "str", "required": True, "help": "The service subcommand to run (e.g., 'list', 'start', 'stop')."},
            {"name": "name", "type": "str", "required": False, "help": "The name of the service to act on."}
        ],
        "options": []
    },
    "tap": {
        "description": "Adds the given tap(s).",
        "params": [
            {"name": "names", "type": "list", "required": True, "help": "Name of the tap(s) to add."},
        ],
        "options": []
    },
    "pin": {
        "description": "Pins the given formula(e), preventing them from being upgraded.",
        "params": [
            {"name": "names", "type": "list", "required": True, "help": "Name of the formula(e) to pin."},
        ],
        "options": []
    },
    "unpin": {
        "description": "Unpins the given formula(e), allowing them to be upgraded.",
        "params": [
            {"name": "names", "type": "list", "required": True, "help": "Name of the formula(e) to unpin."},
        ],
        "options": []
    },
    "deps": {
        "description": "Shows the dependencies for the given formula(e).",
        "params": [
            {"name": "names", "type": "list", "required": True, "help": "Name of the formula(e) to show dependencies for."},
        ],
        "options": []
    }
}


# --- Utility Functions ---

def execute_brew_command(command_list):
    """Executes a brew command, logs the interaction, and returns the result."""
    # Initialize log entry with the command being executed
    log_entry = {"event": "brew_command", "command": command_list}

    try:
        # To ensure `brew` runs in a predictable environment, we create a minimal
        # set of environment variables. This avoids issues from custom shell configs.
        env_path = os.environ.get("PATH", "")
        # `brew doctor` can issue a warning if Homebrew's sbin directory is not in
        # the PATH. We prepend it to proactively resolve this.
        homebrew_sbin = "/opt/homebrew/sbin"
        if homebrew_sbin not in env_path:
            env_path = f"{homebrew_sbin}:{env_path}"
        
        # We only pass essential variables to the subprocess.
        brew_env = {
            "PATH": env_path,
            "HOME": os.environ.get("HOME", ""),
        }

        # Execute the command. `check=False` means we handle non-zero exit codes manually.
        process = subprocess.run(
            command_list,
            capture_output=True,
            text=True,
            check=False,
            env=brew_env,
        )
        # Clean up output by removing leading/trailing whitespace
        stdout = process.stdout.strip()
        stderr = process.stderr.strip()
        
        # Log the complete interaction, including output and return code.
        log_entry["result"] = {"stdout": stdout, "stderr": stderr, "returncode": process.returncode}
        logger.info(log_entry)
        
        # If the command failed, return the error. Prefer stderr, but fall back to stdout.
        if process.returncode != 0:
            return f"Error: {stderr or stdout}"
        # If successful, return stdout or a generic success message if there's no output.
        return stdout or "Command executed successfully."

    except FileNotFoundError:
        # This occurs if 'brew' is not installed or not in the system's PATH.
        error_message = "Error: 'brew' command not found. Make sure Homebrew is installed and in your PATH."
        log_entry["result"] = {"error": error_message}
        logger.error(log_entry)
        return error_message

def create_tool_function(name, config):
    """Dynamically creates a Python function for a given brew command configuration."""
    # This function uses metaprogramming to generate a Python function on the fly.
    # It constructs the function's definition as a string and then uses `exec`
    # to compile and load it into the module's namespace.
    param_list = []
    # Handle positional arguments. Parameters of type 'list' expect a list of values.
    # Non-required parameters get a default value of None.
    for param in config.get("params", []):
        default = '=None' if not param.get('required') else ''
        if not default:
             param_list.append(f"{param['name']}")
        else:
             param_list.append(f"{param['name']}{default}")

    # Keyword-only arguments from 'options'
    if config.get("options"):
        # Force options to be keyword-only arguments for clarity in function calls.
        # An isolated '*' in a function signature separates positional from keyword-only arguments.
        if config.get("params"):
            param_list.append("*")
        # if there are no positional args, all options are keyword-only by default, but we need '*' if we want to enforce it
        elif not config.get("params"):
            param_list.insert(0, "*")

        # Handle options, which will be keyword-only arguments.
        for option in config["options"]:
            if option["type"] == "bool":
                param_list.append(f"{option['name']}=False")
            elif option["type"] == "str":
                 param_list.append(f"{option['name']}=None")

    # The base command can be a single string (like 'install') or a list (like ['services', 'list']).
    base_command = config.get("base_command", [name.replace('_', '-')])

    # Build the function's body as a series of strings.
    # The body constructs the `brew` command list based on arguments.
    lines = [f"    command = ['brew'] + {base_command!r}"]

    # Add parameters to the command list
    for param in config.get("params", []):
        p_name = param['name']
        if param['required']:
            lines.append(f"    if {p_name}:")
        else:
            lines.append(f"    if {p_name} is not None:")

        if param.get("type") == "list":
            # Ensure the argument is a list to handle cases where a single string is passed.
            lines.append(f"        items = {p_name} if isinstance({p_name}, list) else [{p_name}]")
            lines.append(f"        command.extend(map(str, items))")
        else:
            lines.append(f"        command.append(str({p_name}))")

    # Add options (flags) to the command list
    for option in config.get("options", []):
        o_name = option['name']
        flag = option['flag']
        lines.append(f"    if {o_name}:")
        if option["type"] == "bool":
            # Boolean options just add the flag
            lines.append(f"        command.append('{flag}')")
        elif option["type"] == "str":
            # String options add both the flag and its value
            lines.append(f"        command.extend(['{flag}', str({o_name})])")

    # Execute the constructed brew command
    lines.append("    return execute_brew_command(command)")

    # Assemble the complete function definition
    func_body = "\n".join(lines)
    signature = ", ".join(param_list)
    # The full function definition is created as a string.
    func_def = f"def {name}({signature}):\n{func_body}"

    # The `exec` function compiles and runs the string as Python code.
    # The new function is defined within the `local_scope` dictionary.
    local_scope = {}
    exec(func_def, globals(), local_scope)

    # Extract the newly created function from the local scope
    new_func = local_scope[name]
    # Set the docstring for the newly created function from the configuration.
    new_func.__doc__ = config['description']
    return new_func


# --- Main Application ---

def main():
    """Sets up and runs the FastMCP server."""
    logger.info({"event": "server_setup_start", "message": "Starting FastMCP server setup..."})
    start_time = time.time()
    
    # Initialize the FastMCP application with server metadata
    app = FastMCP(
        "homebrew",
        "Homebrew package manager",
        auth_server_provider=None,
        tool_homepage="https://github.com/jeannier/homebrew-mcp",
        auth=None,
    )
    logger.info({
        "event": "app_initialized",
        "message": "FastMCP app initialized.",
        "duration_seconds": round(time.time() - start_time, 2)
    })

    # Dynamically register all brew commands as MCP tools
    logger.info({"event": "tool_registration_start", "message": "Registering all tools..."})
    registration_start_time = time.time()
    for name, config in COMMANDS.items():
        tool_creation_start_time = time.time()
        # Create a function for this specific brew command
        tool_func = create_tool_function(name, config)
        # Register the function as an MCP tool
        app.tool(name)(tool_func)
        logger.info({
            "event": "tool_registered",
            "tool_name": name,
            "duration_seconds": round(time.time() - tool_creation_start_time, 4)
        })

    # Log timing information for performance monitoring
    total_registration_time = time.time() - registration_start_time
    logger.info({
        "event": "tool_registration_end",
        "message": "All tools registered.",
        "duration_seconds": round(total_registration_time, 2)
    })

    total_setup_time = time.time() - start_time
    logger.info({
        "event": "server_setup_end",
        "message": "Total server setup time.",
        "duration_seconds": round(total_setup_time, 2)
    })
    
    # Start the MCP server
    logger.info({"event": "server_run", "message": "Running FastMCP server..."})
    app.run()

# Entry point - run the server when script is executed directly
if __name__ == "__main__":
    main()