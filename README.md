# codemcp

Make Claude Desktop a pair programming assistant by installing codemcp.  With
it, you can directly ask Claude to implement features, fix bugs and do
refactors on a codebase on your computer; Claude will directly edit files and
run tests.  Say goodbye to copying code in and out of Claude's chat window!

![Screenshot of Claude Desktop with codemcp](static/screenshot.png?raw=true)

codemcp offers similar functionality to other AI coding software (Claude Code,
Cursor, Cline, Aider), but it occupies a unique point in the design space:

1. It's intended to be used with Claude Pro, Anthropic's $20/mo subscription
   offering.  **Say goodbye to giant API bills**.  (Say hello to time-based rate
   limits.)

2. It's built around **safe agentic AI** by providing a limited set of tools
   that helpful, honest and harmless LLMs are unlikely to misuse, and enforcing
   best practices like use of Git version control to ensure all code changes
   can be rolled back.  As a result, you can safely **unleash the AI** and
   only evaluate at the end if you want to accept the changes or not.

3. It's **IDE agnostic**: you ask Claude to make changes, it makes them, and
   then you can use your favorite IDE setup to review the changes and make
   further edits.


## Installation

First, install `uv` and install git, if they are not installed already (on Windows, if you installed Git, I recommend rebooting).

## Configure codemcp in your Claude Desktop

### For macOS/Linux

Create or edit your `~/.config/anthropic/claude/claude_desktop_config.json` file and add the following:

```json
{
  "mcpServers": {
    "codemcp": {
      "command": "/Users/<USERNAME>/.local/bin/uvx",
      "args": [
        "--from",
        "git+https://github.com/ezyang/codemcp@prod",
        "codemcp"
      ]
    }
  }
}
```

### For Windows

Create or edit your `%USERPROFILE%\.anthropic\claude\claude_desktop_config.json` file and add the following:

```json
{
  "mcpServers": {
    "codemcp": {
      "command": "C:\\Users\\<USERNAME>\\.local\\bin\\uvx.exe",
      "args": [
        "--from",
        "git+https://github.com/ezyang/codemcp@prod",
        "codemcp"
      ]
    }
  }
}
```

### Using with WSL (recommended for Windows users)

If you're using Windows Subsystem for Linux, you can configure codemcp to run within your WSL environment. This is useful if you prefer developing in a Linux environment while on Windows.

Add the following configuration to your `claude_desktop_config.json` file:

```json
{
	"mcpServers": {
		"codemcp": {
			"command": "wsl.exe",
			"args": [
				"bash",
				"-c",
				"/home/NameOfWSLUser/.local/bin/uvx --from git+https://github.com/ezyang/codemcp@prod codemcp"
			]
		}
	}
}
```

Replace `NameOfWSLUser` with your actual WSL username. This configuration runs the `uvx` command inside your WSL environment while allowing Claude Desktop to communicate with it.

This configuration comes with the added benefit of being able to access your Linux filesystem directly. When initializing codemcp in Claude Desktop, you can use a path to your WSL project like:

```
Initialize codemcp with /home/NameOfWSLUser/project_in_wsl_to_work_on
```

Make sure you have installed Python 3.12+ and uv within your WSL distribution. You might need to run the following commands in your WSL terminal:

```bash
# Install Python 3.12 (if not already installed)
sudo apt update
sudo apt install python3.12

# Install uv
curl -sSf https://astral.sh/uv/install.sh | sh
```

After configuring, restart Claude Desktop. The hammer icon should appear, indicating codemcp has loaded successfully.

Restart the Claude Desktop app after modifying the JSON.  If the MCP
successfully loaded, a hammer icon will appear and when you click it "codemcp"
will be visible.

### Global install with pip

If you don't want to use uv, you can also globally pip install the latest
codemcp version, assuming your global Python install is recent enough (Python
3.12) and doesn't have Python dependencies that conflict with codemcp.  Some
users report this is easier to get working on Windows.

1. `pip install git+https://github.com/ezyang/codemcp@prod`
2. Add the following configuration to `claude_desktop_config.json` file
```json
{
    "mcpServers": {
         "codemcp": {
               "command": "python",
               "args": ["-m", "codemcp"]
            }
    }
}
```
3. Restart Claude Desktop

You will need to manually upgrade codemcp to take updates using
`pip install --upgrade git+https://github.com/ezyang/codemcp@prod`

### Other tips

Pro tip: If the server fails to load, go to Settings > Developer > codemcp >
Logs to look at the MCP logs, they're very helpful for debugging. The logs on
Windows should be loaded `C:\Users\<user_name>\AppData\Roaming\Claude\logs`
(replace `<user_name>` with your username.

Pro tip: if on Windows, _**try using the [WSL instructions](#using-with-wsl-recommended-for-windows-users) instead**_, but if you insist on using Windows directly: if the logs say "Git executable not found. Ensure that
Git is installed and available", and you *just* installed Git, reboot your
machine (the PATH update hasn't propagated.)  If this still doesn't work, open
System Properties > Environment Variables > System variables > Path and ensure
there is an entry for Git.

Pro tip: if you like to live dangerously, you can change `prod` to `main`.  If
you want to pin to a specific release, replace it with `0.3.0` or similar.

Pro tip: it is supported to specify only `uvx` as the command, but uvx must be
in your global PATH (not just added via a shell profile); on OS X, this is
typically not the case if you used the self installer (unless you installed
into a system location like `/usr/local/bin`).

## Usage

First, you must create a `codemcp.toml` file in the Git repository checkout
you want to work on.  If you want the agent to be able to do things like run
your formatter or run tests, add the commands to execute them in the commands
section (note: these commands need to appropriately setup any virtual
environment they need):

```toml
format = ["./run_format.sh"]
test = ["./run_test.sh"]
```

Next, in Claude Desktop, we recommend creating a Project and putting this in
the Project Instructions:

```
Initialize codemcp with $PROJECT_DIR
```

Where `$PROJECT_DIR` is the path to the project you want to work on.

Then chat with Claude about what changes you want to make to the project.
Every time codemcp makes a change to your code, it will generate a commit.

### Using with claude.ai web interface

You can also use codemcp with the Claude web interface at claude.ai by running the SSE server:

```bash
codemcp serve
```

This will start a local SSE server on port 8000 that can be connected to from claude.ai. The server
has CORS enabled for claude.ai by default. You can customize the host, port, and allowed CORS origins:

```bash
codemcp serve --host 0.0.0.0 --port 8765 --cors-origin https://claude.ai --cors-origin https://example.com
```

To see some sample transcripts using this tool, check out:

- [Implement a new feature](https://claude.ai/share/a229d291-6800-4cb8-a0df-896a47602ca0)
- [Fix failing tests](https://claude.ai/share/2b7161ef-5683-4261-ad45-fabc3708f950)
- [Do a refactor](https://claude.ai/share/f005b43c-a657-43e5-ad9f-4714a5cd746f)

codemcp will generate a commit per chat and amend it as it is working on your feature.

## Philosophy

- When you get rate limited, take the time to do something else (review
  Claude's code, review someone else's code, make plans, do some meetings)

- This is *not* an autonomous agent.  At minimum, you have to intervene after
  every chat to review the changes and request the next change.  While you
  *can* ask for a long list of things to be done in a single chat, you will
  likely hit Claude Desktop's output limit and have to manually "continue" the
  agent anyway.  Embrace it, and use the interruptions to make sure Claude is
  doing the right thing.

- When Claude goes off the rails, it costs you time rather than dollars.
  Behave accordingly: if time is the bottleneck, watch Claude's incremental
  output carefully.

## Configuration

Here are all the config options supported by `codemcp.toml`:

```toml
project_prompt = """
Before beginning work on this feature, write a short haiku.  Do this only once.
"""

[commands]
format = ["./run_format.sh"]
test = ["./run_test.sh"]
```

The `project_prompt` will be loaded when you initialize the project in chats.

The `commands` section allows you to configure commands for specific tools.  The
names are told to the LLM, who will decide when it wants to run them.  You can add
instructions how to use tools in the `project_prompt`; we also support a more verbose
syntax where you can give specific instructions on a tool-by-tool basis:

```
[commands.test]
command = ["./run_test.sh"]
doc = "Accepts a pytest-style test selector as an argument to run a specific test."
```

## Troubleshooting

To run the server with inspector, use:

```
PYTHONPATH=. mcp dev codemcp/__main__.py
```

Logs are written to `~/.codemcp/codemcp.log`. The log level can be set in a global configuration file at `~/.codemcprc`:

```toml
[logger]
verbosity = "INFO"  # Can be DEBUG, INFO, WARNING, ERROR, or CRITICAL
```

Logging is not configurable on a per project basis, but this shouldn't matter
much because it's difficult to use Claude Desktop in parallel on multiple
projects anyway.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Type Checking

This project uses `pyright` for type checking with strict mode enabled. The type checking configuration is in `pyproject.toml`. We use a few strategies to maintain type safety:

1. Type stubs for external libraries:
   - Custom type stubs are in the `stubs/` directory
   - The `stubPackages` configuration in `pyproject.toml` maps libraries to their stub packages

2. File-specific ignores for challenging cases:
   - For some files with complex dynamic typing patterns (particularly testing code), we use file-specific ignores via `tool.pyright.ignoreExtraErrors` in `pyproject.toml`
   - This is preferable to inline ignores and lets us maintain type safety in most of the codebase

When making changes, please ensure type checking passes by running:
```
./run_typecheck.sh
```
