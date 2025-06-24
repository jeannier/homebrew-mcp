[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/jeannier-homebrew-mcp-badge.png)](https://mseep.ai/app/jeannier-homebrew-mcp)

# Homebrew MCP Python Server

A Model Context Protocol (MCP) server for Homebrew package management **on macOS**, designed for seamless integration with Claude Desktop and other MCP-compatible clients.

- **Language:** Python 3.13
- **MCP:** [Model Context Protocol](https://github.com/modelcontextprotocol/python-sdk)
- **Package Manager:** Homebrew (macOS)
- **Venv/Dependency Manager:** [uv](https://github.com/astral-sh/uv)

---

## Features

- Exposes Homebrew commands as MCP tools. The supported commands are grouped by function:
  - **Package Management:** `install`, `uninstall`, `upgrade`, `cleanup`
  - **Information & Discovery:** `list`, `search`, `info`, `outdated`, `deps`
  - **System Health & Updates:** `doctor`, `update`
  - **Tap & Source Management:** `tap`, `untap`
  - **Version Management:** `pin`, `unpin`
  - **Service Management:** `services`
- Runs real `brew` commands via subprocess (requires Homebrew on macOS).
- Fully MCP spec-compliant (stdio, JSON-RPC 2.0, MCP spec 2025-06-18).
- Designed for Claude Desktop and other LLM clients.
- Functional, declarative Python (no classes).
- Logs all requests/results to `homebrew_mcp.log`.
- Includes an interactive test script (`test_claude_homebrew_mcp.py`) that:
    - Dynamically fetches available tools from the MCP server.
    - Allows Claude to make multiple tool calls for a single user prompt.
    - Demonstrates advanced interaction patterns with the Anthropic API.

---

## Installation

1. **Clone this repository:**
   ```sh
   git clone https://github.com/jeannier/homebrew-mcp
   cd homebrew-mcp
   ```
2. **Install [uv](https://github.com/astral-sh/uv) (if not already):**
   ```sh
   brew install uv
   ```
3. **Create a virtual environment and install dependencies:**
   ```sh
   uv venv
   source .venv/bin/activate  # Activate the virtual environment
   uv pip install -r requirements.txt
   ```
4. **Run the MCP Server (for Local Testing):**
   To test the server locally or during development, you can run it directly:
   ```sh
   uv run python homebrew_mcp.py
   ```
   The server will then start. If successful, there will be no immediate output; it will silently listen for MCP requests over stdio. You can confirm it's running by checking the `homebrew_mcp.log` file.

   > **Note:** If you are integrating with Claude Desktop, you do **not** need to run this command manually. Claude Desktop will start the server automatically based on the configuration provided in the "Claude Desktop Integration" section. This command is for direct testing or development purposes.

---

## Cursor Integration

**Prerequisite:** Before adding the tool, please complete the steps in the **[Installation](#installation)** section to set up the project and its dependencies. The "Add to Cursor" button assumes the project is located at `~/Documents/GitHub/homebrew-mcp`.

<a href="cursor://anysphere.cursor-deeplink/mcp/install?name=homebrew-mcp&config=eyJjb21tYW5kIjoidXYgcnVuIC0tZGlyZWN0b3J5IH4vRG9jdW1lbnRzL0dpdEh1Yi9ob21lYnJldy1tY3AgaG9tZWJyZXdfbWNwLnB5In0=">
  <img src="https://img.shields.io/badge/add%20to-cursor-4285f4" alt="Add to Cursor">
</a>

1. **Install Cursor via Homebrew (macOS):**
   ```sh
   brew install --cask cursor
   ```

2. **Add the Tool to Cursor**:
   - Click the "Add to Cursor" button above. This will open Cursor and automatically install the tool.
   - If your project is not at the location assumed by the button, you will need to edit the generated configuration. On macOS, this file is located at `~/.cursor/mcp.json`. Open it and update the path inside the `command` string for the `homebrew-mcp` entry. The `mcp.json` file in this repository can be used as a reference.

3. **Restart Cursor**:
   - For the tool to become active, restart Cursor after installation.

---

## Claude Desktop Integration

1. **Install Claude Desktop via Homebrew (macOS):**
   ```sh
   brew install --cask claude
   ```

2. **Ensure `uv` is in your PATH and the project is accessible.**

3. **Configure Claude Desktop to use this MCP server:**
   - On macOS, edit or create your user-level MCP configuration file at: `~/Library/Application Support/Claude/claude_desktop.json`.
   - Add the following server definition, replacing `/path/to/your/project/` with the **absolute path** to the directory where you cloned this project. You can refer to the `claude_desktop_config.json` file in this repository for an example.

```json
{
  "mcpServers": {
    "homebrew-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/your/project/",
        "homebrew_mcp.py"
      ],
      "type": "stdio"
    }
  }
}
```
   *The `--directory` argument tells `uv` where to find the `homebrew_mcp.py` script and its context (like the `.venv`).*

4. **Restart Claude Desktop.**

---

## Project Structure

- **Python Scripts**
  - `homebrew_mcp.py` — Main MCP server script.
  - `test_claude_homebrew_mcp.py` — Interactive Claude integration test script.
- **Configuration**
  - `claude_desktop_config.json` — Example configuration for Claude Desktop.
  - `mcp.json` — Example configuration for Cursor.
  - `requirements.txt` — Python project dependencies.
- **Documentation & Metadata**
  - `README.md` — This file.
  - `LICENSE` — The project's MIT license.
  - `.gitignore` — Specifies files for Git to ignore.
- **Generated Files (Not in Git)**
  - `.venv/` — Python virtual environment managed by `uv`.
  - `homebrew_mcp.log` — Log file for the MCP server.

---

## Monitoring Logs

To watch the server log in real time and pretty-print each JSON line:

```sh
tail -f homebrew_mcp.log | jq .
```

---

## Tested Environment

This MCP server and its integration with Claude have been primarily tested on the following environment:

- **macOS:** Sonoma 14.7.5
- **Homebrew:** 4.5.8
- **Python:** 3.13 (managed via `uv`)
  - **mcp module:** 1.9.4 (installed using `uv pip`)
- **anthropic module:** 0.55.0 (installed using `uv pip`)
- **Claude Desktop:** 0.10.38 (installed via Homebrew Cask on macOS).
- **Cursor:** 1.1.4

---

## Example Prompts

Here are some example prompts you can use with Claude (or another MCP client) when interacting with this Homebrew MCP server:

- provide a summary of all installed packages
- check which packages are installed, and provide suggestions for other packages to install
- are there any problems with my homebrew setup? and how can I fix them ?
- show me information about the python 3.13 package
- install the wget package

---

## Interactive Claude Test Script

To run the Claude integration test (`test_claude_homebrew_mcp.py`), you need an Anthropic Claude API key. Set your API key in the `ANTHROPIC_API_KEY` variable at the top of the test script. This script allows you to interact with Claude, which in turn uses the `homebrew_mcp.py` server. It demonstrates dynamic tool discovery and Claude's ability to make multiple tool calls.

```sh
uv run python test_claude_homebrew_mcp.py
```

---

## Example Test Run Output

This section shows an example of the output when running the `test_claude_homebrew_mcp.py` script.
It demonstrates the interaction between Claude and the Homebrew MCP server, including dynamic tool discovery, multiple tool calls, and final responses.

```
$ uv run python test_claude_homebrew_mcp.py

============================== Claude Prompt 1/7 ===============================
install wget if not installed, or uninstall if already installed
================================================================================
============================= Claude's Answer 1/7 ==============================
I've successfully installed wget on your system. Now that wget is installed, if you'd like me to uninstall it instead (as per your request to either install if not present or uninstall if already installed), I can do that for you.

Would you like me to proceed with uninstalling wget now? Please let me know.
================================================================================

============================== Claude Prompt 2/7 ===============================
restore initial state of wget
================================================================================
============================= Claude's Answer 2/7 ==============================
I've successfully uninstalled wget, returning your system to its initial state before our conversation. The wget package has been completely removed from your system.
================================================================================

============================== Claude Prompt 3/7 ===============================
check for outdated packages
================================================================================
============================= Claude's Answer 3/7 ==============================
You have 3 outdated packages:
1. libnghttp2
2. uv
3. yt-dlp

These packages have newer versions available and can be upgraded if you wish.
================================================================================

============================== Claude Prompt 4/7 ===============================
provide a summary of all installed packages
================================================================================
============================= Claude's Answer 4/7 ==============================
Here's a summary of all installed packages on your system:

1. **Command Line Tools & Utilities**: bash, coreutils, curl, git, jq, nmap, grep, watch, etc.
2. **Programming Languages & Tools**: python (multiple versions), node, go, lua
3. **Media Tools & Libraries**: ffmpeg and its dependencies (x264, x265, etc.), yt-dlp
4. **Development Tools**: neovim, tree-sitter, shellcheck
5. **Applications (Casks)**:
   - Browsers: google-chrome, firefox
   - Development: visual-studio-code, iterm2, cursor, github
   - Communication: discord, whatsapp
   - Media: vlc, spotify, stremio
   - Utilities: docker-desktop, keepassxc, alt-tab, disk-inventory-x
   - AI/ML tools: chatgpt, claude, ollama, superwhisper

You have 3 outdated packages (libnghttp2, uv, and yt-dlp) that could be updated.
================================================================================

============================== Claude Prompt 5/7 ===============================
provide 5 suggestions of other packages to install
================================================================================
============================= Claude's Answer 5/7 ==============================
Based on your installed packages and common developer tools, here are 5 suggested packages that would complement your setup:

1. **tmux** - A terminal multiplexer that allows you to manage multiple terminal sessions within a single window. Great companion to your iterm2 and neovim setup.

2. **htop** - An interactive process viewer and system monitor, much more feature-rich than the standard top command.

3. **ripgrep** - A faster alternative to grep, designed for searching code. Works well with your development tools.

4. **fzf** - A command-line fuzzy finder that can dramatically improve your terminal workflow for searching files, command history, and more.

5. **tldr** - Simplified and community-driven man pages with practical examples. Perfect for quickly finding common command usage patterns.

These tools would enhance your command-line productivity and integrate well with your existing development environment. Would you like more information about any of these packages?
================================================================================

============================== Claude Prompt 6/7 ===============================
use brew doctor to see if there are any issues, try to find a fix for all of these issues
================================================================================
============================= Claude's Answer 6/7 ==============================
Based on the complete analysis, here's my recommendation to fix the one minor warning:

Since this is just a warning about having both the core and tap version of nextdns available, and you're actually using the core version (as shown by the info command), this isn't causing any functional problems with your system. The warning is simply informing you that if you want to specifically use the tap version, you need to use the full name.

If you want to fully resolve this warning, you have two options:

1. Continue using the core version of nextdns (which you are currently using) and untap the nextdns tap to remove the ambiguity. This would require identifying the exact tap name and then using the untap command.

2. Keep both versions available and just be aware that you need to use the full name when referring to the tap version.

Since the warning isn't causing any actual issues with your Homebrew installation and everything is functioning correctly, I would recommend option 2 - simply being aware of the naming convention when you need to use the tap version.

The brew doctor results suggest your Homebrew installation is actually in good shape with no critical issues that need fixing!
================================================================================

============================== Claude Prompt 7/7 ===============================
provide a summary of what was done
================================================================================
============================= Claude's Answer 7/7 ==============================
# Homebrew Session Summary

Here's a summary of what was done during our session:

1. **Checked and installed wget**:
   - Initially verified that wget was not installed on your system
   - Installed wget version 1.25.0

2. **Restored initial state**:
   - Uninstalled wget to return to the original system state

3. **Checked for outdated packages**:
   - Found 3 outdated packages: libnghttp2, uv, and yt-dlp

4. **Listed all installed packages**:
   - Displayed a complete list of installed formulae and casks
   - Your system has numerous development tools, utilities, and applications installed

5. **Suggested 5 additional packages**:
   - tmux: Terminal multiplexer
   - htop: Interactive process viewer
   - ripgrep: Fast alternative to grep
   - fzf: Command-line fuzzy finder
   - tldr: Simplified man pages

6. **Ran system diagnostics**:
   - Executed brew doctor to check for issues
   - Found only one minor warning related to the nextdns package having the same name in both core formulae and a custom tap
   - This warning is informational only and doesn't require action unless you experience issues with nextdns

7. **Examined package versions**:
   - Listed all installed packages with their versions to get a better understanding of your system configuration

Overall, your Homebrew installation appears to be in good health with only a minor naming conflict that doesn't impact functionality.
================================================================================
```

---

## License

MIT License
