# Generated by https://smithery.ai. See: https://smithery.ai/docs/config#dockerfile
FROM python:3.12-slim

WORKDIR /app

# Copy project files
COPY . /app

# Install build dependencies and compile the project
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir .

# Expose a port if needed (not strictly required for stdio based MCP servers)

# Default command to run the MCP server
CMD ["codemcp"]
