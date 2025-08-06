# Setup Instructions for Currency Exchange Agent with MySQL

This guide will help you set up and test the Currency Exchange Agent with MySQL storage.

## Prerequisites

- Python 3.12+
- MySQL server installed and running
- Google Gemini API key or OpenAI API key

## Database Setup

1. Create a MySQL database for the agent:

```sql
CREATE DATABASE a2a_currency;
```

2. Create a MySQL user with appropriate permissions:

```sql
CREATE USER 'a2a_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON a2a_currency.* TO 'a2a_user'@'localhost';
FLUSH PRIVILEGES;
```

## Environment Configuration

1. Copy the `.env.template` file to `.env`:

```bash
cp .env.template .env
```

2. Edit the `.env` file with your actual configuration:

```
# LLM Configuration
model_source=google  # or "openai"
GOOGLE_API_KEY=your_google_api_key  # If using Gemini

# MySQL Configuration
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=a2a_user
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=a2a_currency
```

## Installation

Install the agent package using UV:

```bash
uv install -e .
```

Or using pip:

```bash
pip install -e .
```

## Running the Agent

Start the agent server:

```bash
uv run app
```

The server will start on http://localhost:10000 by default.

## Testing the Agent

Run the test client to interact with the agent:

```bash
uv run app/test_client.py
```

The test client will:
1. Perform a basic currency conversion query
2. Test a multi-turn conversation
3. Test streaming responses

## Verifying MySQL Storage

You can verify that data is being stored in MySQL by checking the tables:

```sql
USE a2a_currency;
SHOW TABLES;
SELECT * FROM langgraph_checkpoints;
SELECT * FROM tasks;
SELECT * FROM push_notification_configs;
```

## Troubleshooting

- If you encounter database connection errors, verify your MySQL credentials and make sure the MySQL server is running.
- If the agent fails to start due to missing API keys, check your `.env` file configuration.
- For Python package issues, try reinstalling the dependencies with `uv sync` or `pip install -e .`.

## Docker Deployment

To run the agent in a Docker container:

```bash
# Build the container
docker build -t a2a-langgraph-demo -f Containerfile .

# Run the container with environment variables
docker run -p 10000:10000 \
  -e MYSQL_HOST=host.docker.internal \
  -e MYSQL_PORT=3306 \
  -e MYSQL_USER=a2a_user \
  -e MYSQL_PASSWORD=your_password \
  -e MYSQL_DATABASE=a2a_currency \
  -e GOOGLE_API_KEY=your_google_api_key \
  a2a-langgraph-demo 
```

Note: When running in Docker, use `host.docker.internal` as the MySQL host to connect to the MySQL server on your host machine.