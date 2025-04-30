import asyncio
import sys
from typing import Union
from urllib.parse import quote

import click
from agno.agent import Agent
from agno.api.playground import PlaygroundEndpointCreate, create_playground_endpoint
from agno.cli.console import console
from agno.cli.settings import agno_cli_settings
from agno.tools.mcp import MCPTools
from agno.utils.log import logger
from fastapi import FastAPI
from rich import box
from rich.panel import Panel


async def serve_playground_app_async(
    app: Union[str, FastAPI],
    *,
    scheme: str = "http",
    host: str = "localhost",
    port: int = 7777,
    reload: bool = False,
    prefix="/v1",
    **kwargs,
):
    import uvicorn

    try:
        create_playground_endpoint(
            playground=PlaygroundEndpointCreate(
                endpoint=f"{scheme}://{host}:{port}", playground_data={"prefix": prefix}
            ),
        )
    except Exception as e:
        logger.error(f"Could not create playground endpoint: {e}")
        logger.error("Please try again.")
        return

    logger.info(f"Starting playground on {scheme}://{host}:{port}")
    # Encode the full endpoint (host:port)
    encoded_endpoint = quote(f"{host}:{port}")

    # Create a panel with the playground URL
    url = f"{agno_cli_settings.playground_url}?endpoint={encoded_endpoint}"
    panel = Panel(
        f"[bold green]Playground URL:[/bold green] [link={url}]{url}[/link]",
        title="Agent Playground",
        expand=False,
        border_style="cyan",
        box=box.HEAVY,
        padding=(2, 2),
    )

    # Print the panel
    console.print(panel)

    config = uvicorn.Config(app=app, host=host, port=port, reload=reload, **kwargs)
    server = uvicorn.Server(config)
    await server.serve()


async def main(hello_world: bool = False):
    async with MCPTools(f"{sys.executable} -m codemcp.hot_reload_entry") as codemcp:
        # TODO: cli-ify the model
        from agno.models.anthropic import Claude

        # from agno.models.google import Gemini
        agent = Agent(
            model=Claude(id="claude-3-7-sonnet-20250219"),
            # model=Gemini(id="gemini-2.5-pro-exp-03-25"),
            tools=[codemcp],
            instructions="",
            markdown=True,
            show_tool_calls=True,
        )

        # If --hello-world flag is used, run the short-circuited response and return
        if hello_world:
            await agent.aprint_response(
                "What tools do you have?",
                stream=True,
                show_full_reasoning=True,
                stream_intermediate_steps=True,
            )
            return

        # Comment out the playground code
        # playground = Playground(agents=[agent]).get_app()
        # await serve_playground_app_async(playground)

        # Replace with a simple async loop for stdin input
        print("Enter your query (Ctrl+C to exit):")
        while True:
            try:
                # Use asyncio to read from stdin in an async-friendly way
                loop = asyncio.get_event_loop()
                user_input = await loop.run_in_executor(None, lambda: input("> "))

                # Properly await the async print_response method
                await agent.aprint_response(
                    user_input,
                    stream=True,
                    show_full_reasoning=True,
                    stream_intermediate_steps=True,
                )
            except KeyboardInterrupt:
                print("\nExiting...")
                break


@click.command()
@click.option(
    "--hello-world", is_flag=True, help="Run a simple test query to see available tools"
)
def cli(hello_world: bool = False):
    """CLI for the Agno agent with CodeMCP integration."""
    from agno.debug import enable_debug_mode

    enable_debug_mode()
    import logging

    logging.basicConfig(level=logging.info)
    logging.getLogger("httpx").setLevel(logging.info)  # For HTTP logging
    logging.getLogger("anthropic").setLevel(logging.info)
    logging.getLogger("google_genai").setLevel(logging.info)

    asyncio.run(main(hello_world=hello_world))


if __name__ == "__main__":
    cli()
