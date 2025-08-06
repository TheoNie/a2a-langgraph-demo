# Currency Exchange Agent with MySQL Storage

This sample demonstrates a LangGraph-based A2A agent that performs currency exchange rate lookups with persistent storage in MySQL.

## Features

- Currency exchange rate lookups using the Frankfurter API
- Persistent task state using MySQL storage
- A2A Protocol integration
- Streaming response support
- Push notification support

## Requirements

- Python 3.12+
- MySQL server
- API key for Gemini or OpenAI

## Environment Variables

Create a `.env` file in the project root with the following variables:

```
# LLM Configuration
model_source=google  # or "openai"
GOOGLE_API_KEY=your_google_api_key  # If using Gemini
TOOL_LLM_URL=your_openai_url  # If using OpenAI
TOOL_LLM_NAME=your_openai_model  # If using OpenAI
API_KEY=your_openai_api_key  # If using OpenAI

# MySQL Configuration
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=a2a_currency
```

## Installation

```bash
# Using uv (recommended)
uv install -e .

# Using pip
pip install -e .
```

## Running the Agent

```bash
# Start the agent server
uv run app

# Run with custom host/port
uv run app --host 0.0.0.0 --port 8080

# Run the test client
uv run app/test_client.py
```

## Database Setup

The agent automatically creates the necessary database tables on startup if they don't exist. Make sure the MySQL user has appropriate permissions to create tables and insert/update records.

## Docker Support

```bash
# Build the container
docker build -t a2a-langgraph-demo .

# Run the container
docker run -p 10000:10000 \
  -e MYSQL_HOST=host.docker.internal \
  -e MYSQL_PORT=3306 \
  -e MYSQL_USER=your_mysql_user \
  -e MYSQL_PASSWORD=your_mysql_password \
  -e MYSQL_DATABASE=a2a \
  -e GOOGLE_API_KEY=your_google_api_key \
  a2a-langgraph-demo
```