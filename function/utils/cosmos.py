import os
import uuid
from typing import List, Dict
from azure.identity import DefaultAzureCredential
from azure.core.credentials import TokenCredential
from azure.cosmos.cosmos_client import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

COSMOS_ACCOUNT_NAME = os.getenv("AZURE_COSMOS_ACCOUNT_NAME")
COSMOS_DB_NAME = os.getenv("AZURE_COSMOS_DB_NAME")
COSMOS_CONTAINER_NAME = os.getenv("AZURE_COSMOS_CONTAINER_NAME")
COSMOS_CONNECTION_STRING = os.getenv("AZURE_COSMOS_CONNECTION_STRING")


class CosmosContainer:

    def __init__(
        self,
        account_name: str = None,
        db_name: str = None,
        container_name: str = None,
        credential: TokenCredential = DefaultAzureCredential(),
        connection_string: str = None,
    ):
        account_name = account_name or COSMOS_ACCOUNT_NAME
        db_name = db_name or COSMOS_DB_NAME
        container_name = container_name or COSMOS_CONTAINER_NAME
        connection_string = connection_string or COSMOS_CONNECTION_STRING

        self.partition_key = "0"
        self.partition_key_path = "pk"

        if connection_string:
            client = CosmosClient.from_connection_string(connection_string)
        else:
            client = CosmosClient(url=f"https://{account_name}.documents.azure.com:443/", credential=credential)
        database = client.get_database_client(db_name)
        self.container = database.get_container_client(container_name)

    def query_items(self, query: str, parameters: List[Dict] = None) -> List[Dict]:
        items = self.container.query_items(query, parameters=parameters, enable_cross_partition_query=True)
        return [i for i in items]

    def get_item(self, id: str) -> Dict:
        try:
            return self.container.read_item(item=id, partition_key=self.partition_key)
        except CosmosResourceNotFoundError:
            return None

    def upsert_item(self, item: dict):
        try:
            if "id" not in item:
                item["id"] = str(uuid.uuid4())
            item[self.partition_key_path] = self.partition_key
            item = self.container.upsert_item(item)
            return item
        except CosmosResourceNotFoundError:
            return None

    def delete_item(self, id: str):
        try:
            self.container.delete_item(item=id, partition_key=self.partition_key)
        except CosmosResourceNotFoundError:
            pass
