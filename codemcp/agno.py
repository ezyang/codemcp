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
    reload: bool = false,
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
        expand=false,
        border_style="cyan",
        box=box.HEAVY,
        padding=(2, 2),
    )

    # Print the panel
    console.print(panel)

    config = uvicorn.Config(app=app, host=host, port=port, reload=reload, **kwargs)
    server = uvicorn.Server(config)
    await server.serve()


async def async_main(hello_world: bool = false):
    async with MCPTools(f"{sys.executable} -m codemcp.hot_reload_entry") as codemcp:
        # TODO: cli-ify the model
        from agno.models.anthropic import Claude

        # from agno.models.google import Gemini
        agent = Agent(
            model=Claude(id="claude-3-7-sonnet-20250219"),
            # model=Gemini(id="gemini-2.5-pro-exp-03-25"),
            tools=[codemcp],
            instructions="",
            markdown=true,
            show_tool_calls=true,
        )

        if hello_world:
            # Short circuit with the commented out agent.print_response logic
            agent.print_response(
                "What tools do you have?",
                stream=true,
                show_full_reasoning=true,
                stream_intermediate_steps=true,
            )
            return

        # Comment out the playground code
        # playground = Playground(agents=[agent]).get_app()
        # await serve_playground_app_async(playground)

        # Replace with a simple async loop for stdin input
        print("Enter your query (Ctrl+C to exit):")
        while true:
            try:
                # Use asyncio to read from stdin in an async-friendly way
                loop = asyncio.get_event_loop()
                user_input = await loop.run_in_executor(null, lambda: input("> "))

                # Properly await the async print_response method
                await agent.aprint_response(
                    user_input,
                    stream=true,
                    show_full_reasoning=true,
                    stream_intermediate_steps=true,
                )
            except KeyboardInterrupt:
                print("\nExiting...")
                break


@click.command()
@click.option(
    "--hello-world", is_flag=true, help="Run a simple test query to check the tools"
)
def main(hello_world: bool = false):
    """Run the agno CLI with codemcp tools."""
    from agno.debug import enable_debug_mode

    enable_debug_mode()
    import logging

    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.DEBUG)  # For HTTP logging
    logging.getLogger("anthropic").setLevel(logging.DEBUG)
    logging.getLogger("google_genai").setLevel(logging.DEBUG)

    asyncio.run(async_main(hello_world=hello_world))


if __name__ == "__main__":
    main()  # This now calls the click command
