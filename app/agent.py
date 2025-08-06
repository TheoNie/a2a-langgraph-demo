import os
from collections.abc import AsyncIterable
from typing import Any, Literal, Optional

import httpx
import sqlalchemy as sa
from sqlalchemy import MetaData, Table, Column, String, JSON, create_engine
from sqlalchemy.exc import SQLAlchemyError

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import Checkpointer
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel


class MySQLCheckpointer(Checkpointer):
    """MySQL implementation of the Checkpointer interface for LangGraph."""

    def __init__(self):
        """Initialize the MySQL Checkpointer."""
        # Get MySQL connection information from environment variables
        mysql_host = os.getenv("MYSQL_HOST", "localhost")
        mysql_port = os.getenv("MYSQL_PORT", "3306")
        mysql_user = os.getenv("MYSQL_USER", "root")
        mysql_password = os.getenv("MYSQL_PASSWORD", "")
        mysql_database = os.getenv("MYSQL_DATABASE", "a2a_currency")

        # Create the database connection string
        self.connection_string = (
            f"mysql+pymysql://{mysql_user}:{mysql_password}@"
            f"{mysql_host}:{mysql_port}/{mysql_database}"
        )
        
        # Create the database engine
        self.engine = create_engine(self.connection_string)
        
        # Create table if it doesn't exist
        self._create_table_if_not_exists()
    
    def _create_table_if_not_exists(self) -> None:
        """Create the checkpoint table if it doesn't exist."""
        metadata = MetaData()
        
        Table(
            "langgraph_checkpoints",
            metadata,
            Column("context_id", String(255), primary_key=True),
            Column("checkpoint_data", JSON, nullable=False),
        )
        
        metadata.create_all(self.engine)

    async def get(self, config: dict) -> Optional[dict]:
        """Get a checkpoint for a specific config."""
        try:
            # Extract the thread_id from the config
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                return None
            
            # Query the database for the checkpoint
            with self.engine.connect() as connection:
                result = connection.execute(
                    sa.text(
                        "SELECT checkpoint_data FROM langgraph_checkpoints "
                        "WHERE context_id = :context_id"
                    ),
                    {"context_id": thread_id}
                )
                row = result.fetchone()
                
                if row:
                    return row[0]
                return None
        except SQLAlchemyError:
            # If there's an error, return None
            return None

    async def put(self, config: dict, state: dict) -> None:
        """Save a checkpoint for a specific config."""
        try:
            # Extract the thread_id from the config
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                return
            
            # Save the checkpoint to the database
            with self.engine.connect() as connection:
                # Try to update first
                result = connection.execute(
                    sa.text(
                        "UPDATE langgraph_checkpoints "
                        "SET checkpoint_data = :checkpoint_data "
                        "WHERE context_id = :context_id"
                    ),
                    {
                        "context_id": thread_id,
                        "checkpoint_data": state
                    }
                )
                
                # If no rows were updated, insert a new row
                if result.rowcount == 0:
                    connection.execute(
                        sa.text(
                            "INSERT INTO langgraph_checkpoints "
                            "(context_id, checkpoint_data) "
                            "VALUES (:context_id, :checkpoint_data)"
                        ),
                        {
                            "context_id": thread_id,
                            "checkpoint_data": state
                        }
                    )
                
                connection.commit()
        except SQLAlchemyError:
            # If there's an error, just return
            pass


@tool
def get_exchange_rate(
    currency_from: str = 'USD',
    currency_to: str = 'EUR',
    currency_date: str = 'latest',
):
    """Use this to get current exchange rate.

    Args:
        currency_from: The currency to convert from (e.g., "USD").
        currency_to: The currency to convert to (e.g., "EUR").
        currency_date: The date for the exchange rate or "latest". Defaults to
            "latest".

    Returns:
        A dictionary containing the exchange rate data, or an error message if
        the request fails.
    """
    try:
        response = httpx.get(
            f'https://api.frankfurter.app/{currency_date}',
            params={'from': currency_from, 'to': currency_to},
        )
        response.raise_for_status()

        data = response.json()
        if 'rates' not in data:
            return {'error': 'Invalid API response format.'}
        return data
    except httpx.HTTPError as e:
        return {'error': f'API request failed: {e}'}
    except ValueError:
        return {'error': 'Invalid JSON response from API.'}


class ResponseFormat(BaseModel):
    """Respond to the user in this format."""

    status: Literal['input_required', 'completed', 'error'] = 'input_required'
    message: str


class CurrencyAgent:
    """CurrencyAgent - a specialized assistant for currency convesions."""

    SYSTEM_INSTRUCTION = (
        'You are a specialized assistant for currency conversions. '
        "Your sole purpose is to use the 'get_exchange_rate' tool to answer questions about currency exchange rates. "
        'If the user asks about anything other than currency conversion or exchange rates, '
        'politely state that you cannot help with that topic and can only assist with currency-related queries. '
        'Do not attempt to answer unrelated questions or use tools for other purposes.'
    )

    FORMAT_INSTRUCTION = (
        'Set response status to input_required if the user needs to provide more information to complete the request.'
        'Set response status to error if there is an error while processing the request.'
        'Set response status to completed if the request is complete.'
    )

    def __init__(self):
        model_source = os.getenv('model_source', 'google')
        if model_source == 'google':
            self.model = ChatGoogleGenerativeAI(model='gemini-2.0-flash')
        else:
            self.model = ChatOpenAI(
                model=os.getenv('TOOL_LLM_NAME'),
                openai_api_key=os.getenv('API_KEY', 'EMPTY'),
                openai_api_base=os.getenv('TOOL_LLM_URL'),
                temperature=0,
            )
        self.tools = [get_exchange_rate]
        
        # Initialize the MySQL checkpointer
        self.checkpointer = MySQLCheckpointer()

        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=self.checkpointer,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=(self.FORMAT_INSTRUCTION, ResponseFormat),
        )

    async def stream(self, query, context_id) -> AsyncIterable[dict[str, Any]]:
        inputs = {'messages': [('user', query)]}
        config = {'configurable': {'thread_id': context_id}}

        for item in self.graph.stream(inputs, config, stream_mode='values'):
            message = item['messages'][-1]
            if (
                isinstance(message, AIMessage)
                and message.tool_calls
                and len(message.tool_calls) > 0
            ):
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': 'Looking up the exchange rates...',
                }
            elif isinstance(message, ToolMessage):
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': 'Processing the exchange rates..',
                }

        yield self.get_agent_response(config)

    def get_agent_response(self, config):
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get('structured_response')
        if structured_response and isinstance(
            structured_response, ResponseFormat
        ):
            if structured_response.status == 'input_required':
                return {
                    'is_task_complete': False,
                    'require_user_input': True,
                    'content': structured_response.message,
                }
            if structured_response.status == 'error':
                return {
                    'is_task_complete': False,
                    'require_user_input': True,
                    'content': structured_response.message,
                }
            if structured_response.status == 'completed':
                return {
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': structured_response.message,
                }

        return {
            'is_task_complete': False,
            'require_user_input': True,
            'content': (
                'We are unable to process your request at the moment. '
                'Please try again.'
            ),
        }

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']