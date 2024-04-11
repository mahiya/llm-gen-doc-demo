import os
from azure.identity import DefaultAzureCredential
from azure.core.credentials import TokenCredential, AzureKeyCredential
from azure.search.documents import SearchClient
from concurrent.futures.thread import ThreadPoolExecutor

AI_SEARCH_ACCOUNT_NAME = os.getenv("AI_SEARCH_ACCOUNT_NAME")
AI_SEARCH_INDEX_NAME = os.getenv("AI_SEARCH_INDEX_NAME")
AI_SEARCH_API_VERSION = os.getenv("AI_SEARCH_API_VERSION", "2023-10-01-Preview")
AI_SEARCH_API_KEY = os.getenv("AI_SEARCH_API_KEY")


class AISearchClient:

    def __init__(
        self,
        account_name: str = None,
        index_name: str = None,
        credential: TokenCredential = DefaultAzureCredential(),
        key: str = None,
    ):
        account_name = account_name or AI_SEARCH_ACCOUNT_NAME
        index_name = index_name or AI_SEARCH_INDEX_NAME
        key = key or AI_SEARCH_API_KEY
        if key:
            credential = AzureKeyCredential(key)
        self.client = SearchClient(
            endpoint=f"https://{account_name}.search.windows.net",
            credential=credential,
            index_name=index_name,
            api_version=AI_SEARCH_API_VERSION,
        )

    # インデックスを検索する
    def search(
        self,
        query: str,
        filter: str = None,
        top: int = 10,
    ) -> list[dict]:
        docs = self.client.search(search_text=query, filter=filter, top=top)
        return [d for d in docs]

    # インデックスにドキュメントを追加する
    def register_documents(self, docs: list[dict], chunk_size: int = 100):
        chunks = [docs[i : i + chunk_size] for i in range(0, len(docs), chunk_size)]
        upload_documents = lambda d: self.client.upload_documents(documents=d)
        with ThreadPoolExecutor(max_workers=4) as executor:
            threads = [executor.submit(upload_documents, c) for c in chunks]
            [t.result() for t in threads]

    # インデックスのドキュメントを削除する
    def delete_documents(self, ids: list[str]):
        docs = [{"id": id} for id in ids]
        self.client.delete_documents(documents=docs)
