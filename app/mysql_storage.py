"""MySQL storage implementations for A2A server."""

import datetime
import json
import logging
from typing import Dict, List, Optional, Any

import sqlalchemy as sa
from sqlalchemy import create_engine, MetaData, Table, Column, String, JSON, DateTime
from sqlalchemy.exc import SQLAlchemyError

from a2a.server.tasks import BaseTaskStore, BasePushNotificationConfigStore
from a2a.types import PushNotificationConfig, Task


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MySQLTaskStore(BaseTaskStore):
    """MySQL implementation of the TaskStore interface."""

    def __init__(self, connection_string: str):
        """Initialize the MySQL task store.
        
        Args:
            connection_string: MySQL connection string in the format
                "mysql+pymysql://user:password@host:port/database"
        """
        self.connection_string = connection_string
        self.engine = create_engine(connection_string)
        self._create_table_if_not_exists()
    
    def _create_table_if_not_exists(self) -> None:
        """Create the tasks table if it doesn't exist."""
        metadata = MetaData()
        
        Table(
            "tasks",
            metadata,
            Column("id", String(255), primary_key=True),
            Column("context_id", String(255), nullable=False, index=True),
            Column("data", JSON, nullable=False),
            Column("created_at", DateTime, default=datetime.datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.datetime.utcnow, 
                   onupdate=datetime.datetime.utcnow),
        )
        
        metadata.create_all(self.engine)
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by its ID."""
        try:
            with self.engine.connect() as connection:
                result = connection.execute(
                    sa.text(
                        "SELECT data FROM tasks WHERE id = :task_id"
                    ),
                    {"task_id": task_id}
                )
                row = result.fetchone()
                
                if row:
                    # Convert the JSON data back to a Task object
                    task_dict = row[0]
                    return Task.model_validate(task_dict)
                return None
        except SQLAlchemyError as e:
            logger.error(f"Error getting task: {e}")
            return None
    
    async def create_task(self, task: Task) -> None:
        """Create a new task."""
        try:
            with self.engine.connect() as connection:
                # Convert Task to a dictionary
                task_dict = task.model_dump()
                
                connection.execute(
                    sa.text(
                        "INSERT INTO tasks (id, context_id, data) "
                        "VALUES (:id, :context_id, :data)"
                    ),
                    {
                        "id": task.id,
                        "context_id": task.context_id,
                        "data": task_dict
                    }
                )
                
                connection.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error creating task: {e}")
    
    async def update_task(self, task: Task) -> None:
        """Update an existing task."""
        try:
            with self.engine.connect() as connection:
                # Convert Task to a dictionary
                task_dict = task.model_dump()
                
                connection.execute(
                    sa.text(
                        "UPDATE tasks SET data = :data, context_id = :context_id, "
                        "updated_at = CURRENT_TIMESTAMP "
                        "WHERE id = :id"
                    ),
                    {
                        "id": task.id,
                        "context_id": task.context_id,
                        "data": task_dict
                    }
                )
                
                connection.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error updating task: {e}")
    
    async def list_tasks(
        self, context_id: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[Task]:
        """List tasks, optionally filtered by context_id."""
        tasks = []
        try:
            with self.engine.connect() as connection:
                if context_id:
                    query = sa.text(
                        "SELECT data FROM tasks WHERE context_id = :context_id "
                        "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
                    )
                    result = connection.execute(
                        query, 
                        {"context_id": context_id, "limit": limit, "offset": offset}
                    )
                else:
                    query = sa.text(
                        "SELECT data FROM tasks "
                        "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
                    )
                    result = connection.execute(
                        query, 
                        {"limit": limit, "offset": offset}
                    )
                
                for row in result:
                    task_dict = row[0]
                    tasks.append(Task.model_validate(task_dict))
                
                return tasks
        except SQLAlchemyError as e:
            logger.error(f"Error listing tasks: {e}")
            return []


class MySQLPushNotificationConfigStore(BasePushNotificationConfigStore):
    """MySQL implementation of the PushNotificationConfigStore interface."""

    def __init__(self, connection_string: str):
        """Initialize the MySQL push notification config store.
        
        Args:
            connection_string: MySQL connection string in the format
                "mysql+pymysql://user:password@host:port/database"
        """
        self.connection_string = connection_string
        self.engine = create_engine(connection_string)
        self._create_table_if_not_exists()
    
    def _create_table_if_not_exists(self) -> None:
        """Create the push_notification_configs table if it doesn't exist."""
        metadata = MetaData()
        
        Table(
            "push_notification_configs",
            metadata,
            Column("id", String(255), primary_key=True),
            Column("context_id", String(255), nullable=False, index=True),
            Column("url", String(1024), nullable=False),
            Column("headers", JSON, nullable=True),
            Column("created_at", DateTime, default=datetime.datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.datetime.utcnow, 
                   onupdate=datetime.datetime.utcnow),
        )
        
        metadata.create_all(self.engine)
    
    async def get(self, context_id: str) -> Optional[PushNotificationConfig]:
        """Get a push notification config by context_id."""
        try:
            with self.engine.connect() as connection:
                result = connection.execute(
                    sa.text(
                        "SELECT id, url, headers FROM push_notification_configs "
                        "WHERE context_id = :context_id "
                        "ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"context_id": context_id}
                )
                row = result.fetchone()
                
                if row:
                    # Convert the row to a PushNotificationConfig object
                    config_id, url, headers = row
                    headers_dict = headers if headers else {}
                    
                    return PushNotificationConfig(
                        id=config_id,
                        url=url,
                        headers=headers_dict
                    )
                return None
        except SQLAlchemyError as e:
            logger.error(f"Error getting push notification config: {e}")
            return None
    
    async def create(self, config: PushNotificationConfig, context_id: str) -> None:
        """Create a new push notification config."""
        try:
            with self.engine.connect() as connection:
                # Convert headers to a dictionary if it's not None
                headers_dict = config.headers if config.headers else {}
                
                connection.execute(
                    sa.text(
                        "INSERT INTO push_notification_configs "
                        "(id, context_id, url, headers) "
                        "VALUES (:id, :context_id, :url, :headers)"
                    ),
                    {
                        "id": config.id,
                        "context_id": context_id,
                        "url": config.url,
                        "headers": headers_dict
                    }
                )
                
                connection.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error creating push notification config: {e}")
    
    async def delete(self, context_id: str) -> None:
        """Delete push notification configs for a context_id."""
        try:
            with self.engine.connect() as connection:
                connection.execute(
                    sa.text(
                        "DELETE FROM push_notification_configs "
                        "WHERE context_id = :context_id"
                    ),
                    {"context_id": context_id}
                )
                
                connection.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error deleting push notification config: {e}")