import azure.functions as func
import os
import json
import logging
from collections import defaultdict
from utils.blob import BlobContainer
from utils.search import AISearchClient
from utils.cosmos import CosmosContainer
from utils.chunking import chunk_content
from utils.document_intelligence import DocumentReader
from opencensus.ext.azure.log_exporter import AzureLogHandler
from utils.openai import EmbeddingsClient, ChatCompletionClient

app = func.FunctionApp()

# Azure Application Insights でのログ出力を有効化する
logger = logging.getLogger(__name__)
APP_INSIGHTS_CONNECTION_STRING = os.getenv("APP_INSIGHTS_CONNECTION_STRING")
logger.addHandler(AzureLogHandler(connection_string=APP_INSIGHTS_CONNECTION_STRING))

# Azure Blob Storage にアクセスするためのインスタンスを生成する
blob_container = BlobContainer()

# Azure Cosmos DB にアクセスするためのインスタンスを生成する
AZURE_COSMOS_DB_NAME = os.getenv("AZURE_COSMOS_DB_NAME")
AZURE_COSMOS_DOCS_CONTAINER_NAME = os.getenv("AZURE_COSMOS_DOCS_CONTAINER_NAME")
docs_cosmos_container = CosmosContainer(container_name=AZURE_COSMOS_DOCS_CONTAINER_NAME)

# Azure OpenAI Service にアクセスするためのインスタンスを生成する
chat_client = ChatCompletionClient()
embed_client = EmbeddingsClient()

# Azure AI Search にアクセスするためのインスタンスを生成する
search_client = AISearchClient()

# Azure Document Intelligence でドキュメントを解析するためのインスタンスを生成する
doc_reader = DocumentReader()

# チャンク分割の設定を取得する
chunk_size = os.getenv("CHUNK_SIZE", 4096)
chunk_overlap_rate = os.getenv("CHUNK_OVERLAP_RATE", 0.0)
chunk_overlap_strategy = os.getenv("CHUNK_OVERLAP_STRATEGY", "NONE")

# ドキュメントのタイプおよび処理ステータスで呼び出す関数を定義する
process_functions_map = {
    "reference": {
        "uploaded": "__extract_contents",
        "text_extracted": "__extract_chapter_titles",
        "chapter_titles_extracted": "__extract_chapter_contents",
    },
    "source": {
        "uploaded": "__extract_contents",
        "text_extracted": "__index_document",
    },
    "generated": {
        "requested": "__generate_document",
    },
}


# Cosmos DB で管理されているリファレンスドキュメントのメタデータが更新された時に実行される関数
@app.cosmos_db_trigger(
    arg_name="docs",
    container_name=AZURE_COSMOS_DOCS_CONTAINER_NAME,
    database_name=AZURE_COSMOS_DB_NAME,
    connection="AZURE_COSMOS_CONNECTION",
)
def process_documents(docs: func.DocumentList):
    for doc in docs:
        try:
            # ドキュメントのタイプとステータスを取得する
            doc_type = doc["type"]
            doc_status = doc["status"]
            logger.info(f"id: {doc['id']}, type:{doc_type}, status:{doc_status}")

            # 呼び出すべき関数を選択する
            if doc_type not in process_functions_map or doc_status not in process_functions_map[doc_type]:
                logger.warning(f"Unsupported document type or status: {doc_type}, {doc_status}")
                continue
            func_name = process_functions_map[doc_type][doc_status]

            # 関数を実行する
            doc = docs_cosmos_container.get_item(doc["id"])
            doc = eval(func_name)(doc)

            # 関数実行により更新されたドキュメントを Cosmos DB に格納する(Update処理)
            docs_cosmos_container.upsert_item(doc)

        except Exception as e:
            logger.error(f"Failed to process document: {e}")
            doc["status"] = "failed"
            docs_cosmos_container.upsert_item(doc)


# ドキュメントファイルからテキストを抽出する
def __extract_contents(doc: dict) -> dict:
    doc_id = doc["id"]
    file_extention = doc["file_extention"]

    # Azure Blob Storage にアップロードされているドキュメント(Blob)の SAS 付き URL を取得する
    sas_url = blob_container.get_url_with_sas(doc_id)
    logger.info(f"generated sas url: {sas_url}")

    # Azure AI Document Intelligence でドキュメントを解析する(テキスト抽出)
    high_resolution = True if file_extention in ["pdf"] else False
    analysis_result = doc_reader.get_ocr_result_by_url(sas_url, high_resolution=high_resolution)
    content = doc_reader.get_content_from_ocr_result(analysis_result)
    logger.info(f"extracted content: {doc_id} ({len(content)} characters)")

    # ドキュメントのメタデータを更新したものを返す
    doc["status"] = "text_extracted"
    doc["content"] = content
    doc["analysis_result"] = analysis_result
    return doc


# ドキュメントのコンテンツ(文章)から章のタイトル一覧を抽出する
def __extract_chapter_titles(doc: dict) -> dict:
    content = doc["content"]
    logger.info(f"extract chapter titles: {doc['id']}")

    # ドキュメントのコンテンツ(文章)から章のタイトル一覧を抽出する
    system_message = """
- ユーザから入力された「ドキュメントコンテンツ」の中から、各章のタイトルを抽出してください。
- 抽出した各章のタイトルは「出力フォーマット」で指定した通りの文字列配列のJSON形式で出力してください。
- ここでの章とは最上レベルの文章の区切りを指します。
- 章タイトルの直下には何かしらの文章があり、章タイトルのすぐ後に次の章タイトルが存在することは絶対にないため、その章タイトルは無視してください。
- 設定されているHTMLタグに囚われず、文章の構成を考慮したうえで、章タイトルを抽出してください。
- 各章タイトルは同じ様な文体(フォーマット)となります

# 出力フォーマット
{
    "titles": [
        "Chapter 1 Title",
        "Chapter 2 Title",
        "Chapter 3 Title",
        ...
    ]
}
    """.strip()

    user_message_template = """
以下の「ドキュメントコンテンツ」から、各章のタイトルを抽出してください。

# ドキュメントコンテンツ
{content}
    """.strip()
    user_message = user_message_template.format(content=content)
    messages = chat_client.create_message(system_message, user_message)
    completion = chat_client.get_completion(messages, json_format=True)
    chapter_titles = json.loads(completion)["titles"]

    # ドキュメントのメタデータを更新したものを返す
    doc["status"] = "chapter_titles_extracted"
    doc["chapter_titles"] = chapter_titles
    return doc


# ドキュメントのコンテンツ(文章)から指定した章のコンテンツ(文書)を抽出する
def __extract_chapter_contents(doc: dict) -> dict:
    content = doc["content"]
    chapter_titles = doc["chapter_titles"]

    # リファレンスドキュメントから各チャプターのテキストを抽出する
    chapter_contents = []
    for chapter_title in chapter_titles:
        logger.info(f"extract chapter content: {chapter_title}")

        system_message_template = """
- 以下の「対象のドキュメント」のうち、ユーザが指定した「対象の章」の箇所の文章のみを抽出してください。
- ユーザは「対象の章」を章のタイトルで指定します。
- 今回の実行だけでなく、全体の実行で抽出する章タイトルの一覧は「章のタイトル一覧」で指定されています
- 抽出は、章タイトルの箇所も含めてください。
- 設定されているHTMLタグに囚われず、文章の構成を考慮したうえで、章の文章を抽出してください。

# 章のタイトル一覧
{chapter_titles}

# 対象のドキュメント
{content}
        """.strip()

        user_message_template = """
「対象の章のタイトル」で指定した章の箇所の文章を抽出して出力してください。
抽出した文章は、「出力フォーマット」通りのJSON形式で出力してください。

# 対象の章のタイトル
{chapter_title}

# 出力フォーマット
{{
    "content": "Extracted Content"
}}
        """.strip()

        system_message = system_message_template.format(content=content, chapter_titles="\n".join([f"- {t}" for t in chapter_titles]))
        user_message = user_message_template.format(chapter_title=chapter_title)
        messages = chat_client.create_message(system_message, user_message)
        completion = chat_client.get_completion(messages, json_format=True)
        chapter_content = json.loads(completion)["content"]
        chapter_contents.append(chapter_content)

    # ドキュメントのメタデータを更新したものを返す
    doc["status"] = "processed"
    doc["chapter_contents"] = chapter_contents
    return doc


# ドキュメントのコンテンツ(文章)をチャンク分割して Azure AI Search のインデックスに格納する
def __index_document(doc: dict) -> dict:
    doc_id = doc["id"]
    src_group_id = doc["group_id"]
    content = doc["content"]

    # チャンク分割をする
    chunks = chunk_content(content, chunk_size, chunk_overlap_rate, chunk_overlap_strategy)

    # Azure AI Search のインデックスに格納する
    index_docs = [
        {
            "id": doc_id,
            "sourceGroupId": src_group_id,
            "sourceDocumentId": doc_id,
            "chunkNo": i,
            "content": chunk,
            "contentVector": embed_client.get_embeds(chunk),
        }
        for i, chunk in enumerate(chunks)
    ]
    search_client.register_documents(index_docs)

    # ドキュメントのステータスを更新する
    doc["status"] = "processed"

    return doc


# ドキュメントの生成リクエストに応じて、ドキュメントコンテンツを生成する
def __generate_document(doc: dict) -> dict:
    try:
        ref_doc_id = doc["reference_doc_id"]
        src_group_id = doc["source_group_id"]

        # リファレンスドキュメントのコンテンツを取得する
        ref_doc = docs_cosmos_container.get_item(ref_doc_id)
        chapter_titles = ref_doc["chapter_titles"]
        chapter_contents = ref_doc["chapter_contents"]

        # 生成を開始したステータスに更新する
        doc["status"] = "generating"
        doc["chapter_titles"] = chapter_titles
        doc["generated_contents"] = []
        docs_cosmos_container.upsert_item(doc)

        # 各章ごとにコンテンツを生成する
        generated_contents = []
        for chapter_title, chapter_content in zip(chapter_titles, chapter_contents):
            logger.info(f"generating chapter content: {chapter_title}")

            # 関連ドキュメントを検索する
            query = chapter_title
            docs = search_client.search(query, top=10, filter=f"sourceGroupId eq '{src_group_id}'")
            retrieved_documents = __generate_retrieved_docs_content(docs)

            # 章コンテンツを生成する
            generated_content = __generate_chapter_content(chapter_title, chapter_content, retrieved_documents)
            generated_contents.append(generated_content)
            logger.info(f"generated content: {len(generated_content)} characters")

            # 章コンテンツの生成を行うたびに Cosmos DB のアイテムを更新する
            doc["status"] = "generating"
            doc["chapter_titles"] = chapter_titles
            doc["generated_contents"] = generated_contents
            docs_cosmos_container.upsert_item(doc)

        # ドキュメントのステータスを更新する
        doc["status"] = "processed"
        return doc

    except Exception as e:
        logger.error(f"Failed to generate document: {e}")
        doc["status"] = "failed"
        return doc


# 検索で取得した検索ドキュメントからプロンプトに埋め込むためのテキストを作成する
def __generate_retrieved_docs_content(docs: list[dict]) -> str:

    # ドキュメントごとにまとめる
    docs_groups = defaultdict(list)
    for doc in docs:
        docs_groups[doc["sourceDocumentId"]].append(doc)

    # 各ドキュメントごとにコンテンツをまとめてプロンプトに埋め込む用のテキストを生成
    content = ""
    for i, src_doc_id in enumerate(docs_groups.keys()):
        content += f"## 参考ドキュメント {i+1}"
        docs = docs_groups[src_doc_id]
        docs = sorted(docs, key=lambda x: x["chunkNo"])
        last_chunk_no = -1
        for doc in docs:
            if doc["chunkNo"] != last_chunk_no + 1:
                content += "\n\n...\n"
            content += "\n" + doc["content"]
            last_chunk_no = doc["chunkNo"]
        content += "\n\n"
    content = content.strip()

    return content


# 与えられた章タイトル、参考章コンテンツ、生成のためのドキュメントを使用して、章コンテンツ(文章)を生成する
def __generate_chapter_content(chapter_title: str, chapter_content: str, retrieved_documents) -> str:

    system_message = """
- 与えられた「章のタイトル」から、「章の文章」を生成してください
- 生成する「章の文章」は「参考ドキュメント」の様な文章を書いてください
- ただし、内容は、ユーザメッセージで与えられる「情報源ドキュメント」に則したものとしてください
- 「章の文章」はMarkdown形式の日本語で出力してください

# 章のタイトル
{chapter_title}

# 参考ドキュメント
{chapter_content}
    """.strip().format(
        chapter_title=chapter_title, chapter_content=chapter_content
    )

    user_message = """
- 「情報源ドキュメント」に則して、章の文章を生成してください。
- 生成した文章を「出力フォーマット」で指定したJSONフォーマットで出力してください。

# 情報源ドキュメント
{retrieved_documents}

# 出力フォーマット
{{
    "content": "generated chapter content"
}}
    """.strip().format(
        retrieved_documents=retrieved_documents
    )

    messages = chat_client.create_message(system_message, user_message)
    completion = chat_client.get_completion(messages, json_format=True)
    generated_content = json.loads(completion)["content"]
    return generated_content
