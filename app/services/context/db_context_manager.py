import threading
from typing import Dict, Any, List, Optional
from dependency_injector.wiring import inject, Provide
from app.db.database import Database
from app.interfaces.service import IService
from app.config.service_config import ServiceConfig
from app.logging_config import configure_logger
from app.config.settings import DatabaseSettings, settings

class DBContextManager(IService):
	"""
	DBContextManager is responsible for managing database context operations.
	It provides methods for fetching, saving, updating, and deleting context data in the database.
	"""

	@inject
	def __init__(
		self,
		name: str,
		config: DatabaseSettings,
		database: Database
	):
		"""
		Initialize the DBContextManager.

		Args:
			name (str): The name of the context manager.
			config (ServiceConfig): Configuration for the DB context manager.
			database (Database): Database instance for executing queries.
		"""
		super().__init__(name=name, config = config)
		self.config: DatabaseSettings = config
		self.table_name = config.table_name
		self.allowed_operations = config.allowed_operations
		self.permissions = config.permissions
		self.context_prefix = config.context_prefix
		self.fields = config.fields
		self.queries = config.queries
		self.db = database
		self.service_name = name
		self.logger = configure_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
		
		self._log_initialization()

	def _log_initialization(self):
		"""Log initialization details for debugging."""
		self.logger.info(f"DBContextManager initialized for service: {self.service_name}")
		if settings.DEBUG:
			self.logger.debug(f"Table name: {self.table_name}")
			self.logger.debug(f"Allowed operations: {self.allowed_operations}")
			self.logger.debug(f"Permissions: {self.permissions}")
			self.logger.debug(f"Context prefix: {self.context_prefix}")
			self.logger.debug(f"Fields: {self.fields}")
			self.logger.debug("Available queries:")
			for query_name, query_details in self.queries.items():
				self.logger.debug(f"  {query_name}: {query_details}")

	# Context Retrieval
	# -----------------

	async def get_context(self, key: str, query_name: str) -> Dict[str, Any]:
		"""
		Retrieve context data for a given key using a specified query.

		Args:
			key (str): The context key.
			query_name (str): The name of the query to use for retrieval.

		Returns:
			Dict[str, Any]: The retrieved context data.

		Raises:
			Exception: If there's an error fetching the context.
		"""
		try:
			template_id = key.split(':')[1]
			if settings.DEBUG:
				self.logger.debug(f"Fetching context for key: {key}")
				self.logger.debug(f"Using query: {query_name}")
				self.logger.debug(f"Template ID: {template_id}")

			self.db.fetch_key(key, self.service_name)
			result = await self.db.fetch_all(self.queries[query_name], {'p_id': template_id}, self.service_name)

			if settings.DEBUG:
				self.logger.debug(f"Fetched context result: {result}")

			return result
		except Exception as e:
			self.logger.error(f"Error fetching context for key {template_id}: {str(e)}")
			if settings.DEBUG:
				self.logger.exception("Detailed error traceback:")
			raise

	# Context Saving
	# --------------

	async def save_context(self, key: str, context: Dict[str, Any]) -> None:
		"""
		Save context data for a given key.

		Args:
			key (str): The context key.
			context (Dict[str, Any]): The context data to save.

		Raises:
			ValueError: If the insert query is not found.
			Exception: If there's an error saving the context.
		"""
		self.logger.debug(f"Attempting to save context for key: {key}")
		
		if 'insert' not in self.queries:
			error_msg = f"Insert query not found for service: {self.service_name}"
			self.logger.error(error_msg)
			raise ValueError(error_msg)
		
		try:
			if settings.DEBUG:
				self.logger.debug(f"Using insert query: {self.queries['insert']}")
				self.logger.debug(f"Context data to save: {context}")

			await self.db.execute(self.queries['insert'], {**context, 'id': key}, self.service_name)
			self.logger.debug(f"Context saved successfully for key: {key}")
		except Exception as e:
			self.logger.error(f"Error saving context for key {key}: {str(e)}")
			if settings.DEBUG:
				self.logger.exception("Detailed error traceback:")
			raise

	# Context Updating
	# ----------------

	async def update_context(self, key: str, context: Dict[str, Any]) -> None:
		"""
		Update context data for a given key.

		Args:
			key (str): The context key.
			context (Dict[str, Any]): The updated context data.

		Raises:
			Exception: If there's an error updating the context.
		"""
		try:
			if settings.DEBUG:
				self.logger.debug(f"Updating context for key: {key}")
				self.logger.debug(f"Using update query: {self.queries['update']}")
				self.logger.debug(f"Updated context data: {context}")

			await self.db.execute(self.queries['update'], {**context, 'id': key}, self.service_name)
			self.logger.debug(f"Context updated successfully for key: {key}")
		except Exception as e:
			self.logger.error(f"Error updating context for key {key}: {str(e)}")
			if settings.DEBUG:
				self.logger.exception("Detailed error traceback:")
			raise

	# Context Deletion
	# ----------------

	async def delete_context(self, key: str) -> None:
		"""
		Delete context data for a given key.

		Args:
			key (str): The context key to delete.

		Raises:
			Exception: If there's an error deleting the context.
		"""
		try:
			if settings.DEBUG:
				self.logger.debug(f"Deleting context for key: {key}")
				self.logger.debug(f"Using delete query: {self.queries['delete']}")

			await self.db.execute(self.queries['delete'], {'id': key}, self.service_name)
			self.logger.debug(f"Context deleted successfully for key: {key}")
		except Exception as e:
			self.logger.error(f"Error deleting context for key {key}: {str(e)}")
			if settings.DEBUG:
				self.logger.exception("Detailed error traceback:")
			raise

	# Data Fetching
	# -------------

	async def fetch_data(self, query_name: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
		"""
		Fetch data using a specified query.

		Args:
			query_name (str): The name of the query to use.
			params (Dict[str, Any]): The parameters for the query.

		Returns:
			List[Dict[str, Any]]: The fetched data.

		Raises:
			ValueError: If the specified query is not found.
			Exception: If there's an error fetching the data.
		"""
		query = self.queries.get(query_name)
		if not query:
			error_msg = f"Query '{query_name}' not found"
			self.logger.error(error_msg)
			raise ValueError(error_msg)

		try:
			if settings.DEBUG:
				self.logger.debug(f"Fetching data with query: {query_name}")
				self.logger.debug(f"Query parameters: {params}")

			result = await self.db.fetch_all(query, params, self.service_name)

			if settings.DEBUG:
				self.logger.debug(f"Fetched data result: {result}")

			return result
		except Exception as e:
			self.logger.error(f"Error fetching data with query {query_name}: {str(e)}")
			if settings.DEBUG:
				self.logger.exception("Detailed error traceback:")
			raise

	# Query Execution
	# ---------------

	async def execute_query(self, query_name: str, params: Dict[str, Any]) -> None:
		"""
		Execute a specified query.

		Args:
			query_name (str): The name of the query to execute.
			params (Dict[str, Any]): The parameters for the query.

		Raises:
			ValueError: If the specified query is not found.
			Exception: If there's an error executing the query.
		"""
		query = self.queries.get(query_name)
		if not query:
			error_msg = f"Query '{query_name}' not found"
			self.logger.error(error_msg)
			raise ValueError(error_msg)

		try:
			if settings.DEBUG:
				self.logger.debug(f"Executing query: {query_name}")
				self.logger.debug(f"Query parameters: {params}")

			await self.db.execute(query, params, self.service_name)
			self.logger.debug(f"Query {query_name} executed successfully")
		except Exception as e:
			self.logger.error(f"Error executing query {query_name}: {str(e)}")
			if settings.DEBUG:
				self.logger.exception("Detailed error traceback:")
			raise

	# Service Lifecycle Methods
	# -------------------------

	async def start(self):
		"""Start the DBContextManager service."""
		self.logger.info(f"Starting DBContextManager service: {self.service_name}")
		# Add any startup logic here

	async def stop(self):
		"""Stop the DBContextManager service."""
		self.logger.info(f"Stopping DBContextManager service: {self.service_name}")
		# Add any cleanup logic here
