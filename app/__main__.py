import logging
import os
import sys

import click
import httpx
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    DatabasePushNotificationConfigStore,
    DatabaseTaskStore,
)
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from dotenv import load_dotenv

from app.agent import CurrencyAgent
from app.agent_executor import CurrencyAgentExecutor


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""


class MissingMySQLConfigError(Exception):
    """Exception for missing MySQL configuration."""


@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10000)
def main(host, port):
    """Starts the Currency Agent server with MySQL storage."""
    try:
        # Check for LLM API key
        if os.getenv('model_source', 'google') == 'google':
            if not os.getenv('GOOGLE_API_KEY'):
                raise MissingAPIKeyError(
                    'GOOGLE_API_KEY environment variable not set.'
                )
        else:
            if not os.getenv('TOOL_LLM_URL'):
                raise MissingAPIKeyError(
                    'TOOL_LLM_URL environment variable not set.'
                )
            if not os.getenv('TOOL_LLM_NAME'):
                raise MissingAPIKeyError(
                    'TOOL_LLM_NAME environment not variable not set.'
                )
        
        # Check for MySQL configuration
        if not os.getenv('MYSQL_HOST'):
            raise MissingMySQLConfigError('MYSQL_HOST environment variable not set.')
        if not os.getenv('MYSQL_USER'):
            raise MissingMySQLConfigError('MYSQL_USER environment variable not set.')
        if not os.getenv('MYSQL_DATABASE'):
            raise MissingMySQLConfigError('MYSQL_DATABASE environment variable not set.')
        
        # Create MySQL connection string
        mysql_host = os.getenv("MYSQL_HOST", "localhost")
        mysql_port = os.getenv("MYSQL_PORT", "3306")
        mysql_user = os.getenv("MYSQL_USER", "root")
        mysql_password = os.getenv("MYSQL_PASSWORD", "")
        mysql_database = os.getenv("MYSQL_DATABASE", "a2a_currency")
        connection_string = (
            f"mysql+pymysql://{mysql_user}:{mysql_password}@"
            f"{mysql_host}:{mysql_port}/{mysql_database}"
        )

        # Setup agent card
        capabilities = AgentCapabilities(streaming=True, push_notifications=True)
        skill = AgentSkill(
            id='convert_currency',
            name='Currency Exchange Rates Tool',
            description='Helps with exchange values between various currencies',
            tags=['currency conversion', 'currency exchange'],
            examples=['What is exchange rate between USD and GBP?'],
        )
        agent_card = AgentCard(
            name='Currency Agent with MySQL',
            description='Helps with exchange rates for currencies with persistent storage',
            url=f'http://{host}:{port}/',
            version='1.0.0',
            default_input_modes=CurrencyAgent.SUPPORTED_CONTENT_TYPES,
            default_output_modes=CurrencyAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        # Setup A2A server with MySQL storage
        httpx_client = httpx.AsyncClient()
        
        # Initialize MySQL storage classes
        mysql_task_store = DatabaseTaskStore(connection_string=connection_string)
        mysql_push_config_store = DatabasePushNotificationConfigStore(
            connection_string=connection_string
        )
        
        push_sender = BasePushNotificationSender(
            httpx_client=httpx_client,
            config_store=mysql_push_config_store
        )
        
        request_handler = DefaultRequestHandler(
            agent_executor=CurrencyAgentExecutor(),
            task_store=mysql_task_store,
            push_config_store=mysql_push_config_store,
            push_sender=push_sender
        )
        
        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )

        # Start the server
        uvicorn.run(server.build(), host=host, port=port)

    except MissingAPIKeyError as e:
        logger.error(f'Error: {e}')
        sys.exit(1)
    except MissingMySQLConfigError as e:
        logger.error(f'Error: {e}')
        sys.exit(1)
    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
