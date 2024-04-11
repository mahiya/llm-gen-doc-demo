import os
import json
import uuid
import base64
import logging
import datetime
import subprocess
from flask_cors import CORS
from flask import Flask, request
from utils.blob import BlobContainer
from utils.cosmos import CosmosContainer
from utils.search import AISearchClient
from opencensus.ext.azure.log_exporter import AzureLogHandler

# サポートするドキュメントファイルの拡張子を定義する
SUPPORT_FILE_EXTENSIONS = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx"]

# Azure Application Insights でのログ出力を有効化する
logger = logging.getLogger(__name__)
APP_INSIGHTS_CONNECTION_STRING = os.getenv("APP_INSIGHTS_CONNECTION_STRING")
logger.addHandler(AzureLogHandler(connection_string=APP_INSIGHTS_CONNECTION_STRING))

# Azure Blob Storage にアクセスするためのインスタンスを生成する
blob_container = BlobContainer()

# Azure Cosmos DB にアクセスするためのインスタンスを生成する
docs_cosmos_container = CosmosContainer(container_name=os.getenv("AZURE_COSMOS_DOCS_CONTAINER_NAME"))
groups_cosmos_container = CosmosContainer(container_name=os.getenv("AZURE_COSMOS_GROUPS_CONTAINER_NAME"))

# Azure AI Search にアクセスするためのインスタンスを生成する
search_client = AISearchClient()

app = Flask(__name__)
CORS(app)


@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def static_file(path):
    return app.send_static_file(path)


# リファレンスドキュメント一覧を取得するAPI
@app.route("/api/reference", methods=["GET"])
def list_ref_docs_api():
    user_id, _ = get_user_info()
    query = """
        SELECT 
            c.id, 
            c.name, 
            c.status, 
            c.created_at, 
            c.file_extention 
        FROM c 
        WHERE 
            c.owner_user_id = @user_id 
            AND c.type = "reference"
    """
    parameters = [{"name": "@user_id", "value": user_id}]
    docs = docs_cosmos_container.query_items(query, parameters)
    return docs, 200


# リファレンスドキュメントをアップロードするAPI
@app.route("/api/reference/upload", methods=["POST"])
def upload_ref_doc_api():

    # リクエストにファイルが含まれていない場合はエラーを返す
    if "file" not in request.files or not request.files["file"].filename:
        return "", 400

    # リクエストからファイル情報を取得する
    file = request.files["file"]
    file_name = file.filename
    if not file_name:
        return "", 400

    # アップロードされたファイルの拡張子を確認する
    file_extention = file.filename.split(".")[-1]
    if file_extention not in SUPPORT_FILE_EXTENSIONS:
        return "", 400

    # ファイルを読み込む
    bytes = file.read()

    # リファレンスドキュメントのIDを生成する
    doc_id = str(uuid.uuid4())

    # ファイルをAzure Blob Storage にアップロードする
    blob_container.upload_bytes(doc_id, bytes)

    # ログインユーザ情報を取得する
    user_id, _ = get_user_info()

    # リファレンスドキュメントのデータを Cosmos DB に保存する
    doc = {
        "id": doc_id,
        "owner_user_id": user_id,
        "type": "reference",
        "name": file_name,
        "file_extention": file_extention,
        "status": "uploaded",
        "created_at": datetime.datetime.now().isoformat(),
    }
    docs_cosmos_container.upsert_item(doc)

    return doc_id, 201


# 指定したリファレンスドキュメントを削除するAPI
@app.route("/api/reference/<doc_id>", methods=["DELETE"])
def delete_ref_doc_api(doc_id):

    # ログインユーザ情報を取得する
    user_id, _ = get_user_info()

    # 指定したドキュメントが存在するかを確認する
    doc = docs_cosmos_container.get_item(doc_id)
    if not doc:
        return "", 404

    # ログインユーザが削除操作ができるかを確認する
    if doc["owner_user_id"] != user_id:
        return "", 403

    # ドキュメントを Cosmos DB から削除する
    docs_cosmos_container.delete_item(doc_id)

    # ドキュメントを Azure Blob Storage から削除する
    blob_container.delete_blob(doc_id)

    return "", 204


# 情報源グループ一覧を取得するAPI
@app.route("/api/sourceGroup", methods=["GET"])
def list_src_groups_api():
    user_id, _ = get_user_info()
    query = """
        SELECT 
            c.id, 
            c.name, 
            c.created_at 
        FROM c 
        WHERE 
            c.owner_user_id = @user_id
    """
    parameters = [{"name": "@user_id", "value": user_id}]
    groups = groups_cosmos_container.query_items(query, parameters)
    return groups, 200


# 情報源グループを作成するAPI
@app.route("/api/sourceGroup", methods=["POST"])
def create_src_group_api():

    # リクエストから情報源グループの名前を取得する
    if "name" not in request.json:
        return "", 400
    name = request.json["name"]

    # ログインユーザ情報を取得する
    user_id, _ = get_user_info()

    # 情報源グループを Cosmos DB に保存する
    group_id = str(uuid.uuid4())
    groups_cosmos_container.upsert_item(
        {
            "id": group_id,
            "owner_user_id": user_id,
            "name": name,
            "created_at": datetime.datetime.now().isoformat(),
            "docs": [],
        }
    )
    return group_id, 201


# 指定した情報源グループを削除するAPI
@app.route("/api/sourceGroup/<group_id>", methods=["DELETE"])
def delete_src_group_api(group_id):

    # ログインユーザ情報を取得する
    user_id, _ = get_user_info()

    # 指定したグループが存在するかを確認する
    group = groups_cosmos_container.get_item(group_id)
    if not group:
        return "", 404

    # ログインユーザが削除操作ができるかを確認する
    if group["owner_user_id"] != user_id:
        return "", 403

    # Azure Cosmos DB から情報源グループを削除する
    groups_cosmos_container.delete_item(group_id)

    # 情報源グループに関連する情報源ドキュメントを削除する
    docs = docs_cosmos_container.query_items(
        "SELECT c.id FROM c WHERE c.group_id = @group_id",
        [{"name": "@group_id", "value": group_id}],
    )
    for doc in docs:
        delete_source_doc(doc["id"])

    return "", 204


# 情報源ドキュメント一覧を取得するAPI
@app.route("/api/sourceGroup/<group_id>/source", methods=["GET"])
def list_src_docs_api(group_id):
    user_id, _ = get_user_info()
    query = """
        SELECT 
            c.id, 
            c.name, 
            c.status, 
            c.created_at, 
            c.file_extention 
        FROM c 
        WHERE 
            c.owner_user_id = @user_id 
            AND c.group_id = @group_id 
            AND c.type = "source"
    """
    parameters = [
        {"name": "@user_id", "value": user_id},
        {"name": "@group_id", "value": group_id},
    ]
    docs = docs_cosmos_container.query_items(query, parameters)
    return docs, 200


# 情報源ドキュメントをアップロードするAPI
@app.route("/api/sourceGroup/<group_id>/source/upload", methods=["POST"])
def upload_src_doc_api(group_id):

    # ログインユーザ情報を取得する
    user_id, _ = get_user_info()

    # リクエストにファイルが含まれていない場合はエラーを返す
    if "file" not in request.files:
        return "", 400

    # リクエストからファイル情報を取得する
    file = request.files["file"]
    file_name = file.filename
    if not file_name:
        return "", 400

    # アップロードされたファイルの拡張子を確認する
    file_extention = file.filename.split(".")[-1]
    if file_extention not in SUPPORT_FILE_EXTENSIONS:
        return "", 400

    # ファイルを読み込む
    bytes = file.read()

    # ドキュメントのIDを生成する
    doc_id = str(uuid.uuid4())

    # ファイルをAzure Blob Storage にアップロードする
    blob_container.upload_bytes(doc_id, bytes)

    # ドキュメントのデータを Cosmos DB に保存する
    doc = {
        "id": doc_id,
        "owner_user_id": user_id,
        "type": "source",
        "name": file_name,
        "file_extention": file_extention,
        "status": "uploaded",
        "group_id": group_id,
        "created_at": datetime.datetime.now().isoformat(),
    }
    docs_cosmos_container.upsert_item(doc)

    return doc_id, 201


# 情報源ドキュメントを削除するAPI
@app.route("/api/sourceGroup/<group_id>/source/<doc_id>", methods=["DELETE"])
def delete_src_doc_api(group_id, doc_id):

    # ログインユーザ情報を取得する
    user_id, _ = get_user_info()

    # 指定したドキュメントが存在するかを確認する
    doc = docs_cosmos_container.get_item(doc_id)
    if not doc:
        return "", 404

    # ログインユーザが削除操作ができるかを確認する
    if doc["owner_user_id"] != user_id:
        return "", 403

    # Cosmos DB, AI Search, Blob Storage から情報源ドキュメントを削除する
    delete_source_doc(doc_id)

    return "", 204


# Cosmos DB, AI Search, Blob Storage から情報源ドキュメントを削除する
def delete_source_doc(doc_id: str):

    # ドキュメントを Cosmos DB から削除する
    docs_cosmos_container.delete_item(doc_id)

    # ドキュメントを Azure AI Search から削除する
    docs = search_client.search("*", f"sourceDocumentId eq '{doc_id}'", top=1000)
    if len(docs) > 0:
        search_client.delete_documents([d["id"] for d in docs])

    # ドキュメントを Azure Blob Storage から削除する
    blob_container.delete_blob(doc_id)


# 生成したドキュメント一覧を取得するAPI
@app.route("/api/generated", methods=["GET"])
def list_generated_docs_api():
    user_id, _ = get_user_info()
    query = """
        SELECT 
            c.id, 
            c.reference_doc_name, 
            c.source_group_name, 
            c.status, 
            c.created_at
        FROM c 
        WHERE 
            c.owner_user_id = @user_id 
            AND c.type = "generated"
    """
    parameters = [{"name": "@user_id", "value": user_id}]
    docs = docs_cosmos_container.query_items(query, parameters)
    return docs, 200


# 指定した生成ドキュメントを取得するAPI
@app.route("/api/generated/<doc_id>", methods=["GET"])
def get_generated_doc_api(doc_id):

    # ログインユーザ情報を取得する
    user_id, _ = get_user_info()

    # ドキュメントを Cosmos DB から取得する
    doc = docs_cosmos_container.get_item(doc_id)

    # ドキュメントが存在しない場合、ユーザがアクセス権限を持っていない場合はエラーを返す
    if not doc:
        return "", 404
    elif doc["owner_user_id"] != user_id:
        return "", 403

    # 取得したドキュメントを返す
    return doc, 200


# ドキュメントの生成を開始するAPI
@app.route("/api/generated", methods=["POST"])
def request_generating_doc_api():

    # BodyからリファレンスドキュメントのIDと情報源グループのIDを取得する
    if "referenceDocId" not in request.json or "sourceGroupId" not in request.json:
        return "", 400
    ref_doc_id = request.json["referenceDocId"]
    group_id = request.json["sourceGroupId"]

    # Cosmos DB に格納されているドキュメントとグループを取得する
    doc = docs_cosmos_container.get_item(ref_doc_id)
    group = groups_cosmos_container.get_item(group_id)
    if not doc or not group:
        return "", 400

    # ドキュメントのIDを生成する
    doc_id = str(uuid.uuid4())

    # ログインユーザ情報を取得する
    user_id, _ = get_user_info()

    # リファレンスドキュメントのデータを Cosmos DB に保存する
    doc = {
        "id": doc_id,
        "owner_user_id": user_id,
        "type": "generated",
        "reference_doc_id": ref_doc_id,
        "reference_doc_name": doc["name"],
        "source_group_id": group_id,
        "source_group_name": group["name"],
        "status": "requested",
        "created_at": datetime.datetime.now().isoformat(),
    }
    docs_cosmos_container.upsert_item(doc)

    return doc_id, 201


# 指定した生成ドキュメントを削除するAPI
@app.route("/api/generated/<doc_id>", methods=["DELETE"])
def delete_generated_doc_api(doc_id):

    # ログインユーザ情報を取得する
    user_id, _ = get_user_info()

    # 指定したドキュメントが存在するかを確認する
    doc = docs_cosmos_container.get_item(doc_id)
    if not doc:
        return "", 404

    # ログインユーザが削除操作ができるかを確認する
    if doc["owner_user_id"] != user_id:
        return "", 403

    # Cosmos DB からドキュメントを削除する
    docs_cosmos_container.delete_item(doc_id)

    return "", 204


# 指定した生成ドキュメントをWord形式でダウンロードするためのURLを発行するAPI
@app.route("/api/generated/<doc_id>/download", methods=["GET"])
def get_generated_doc_download_url_api(doc_id):

    # ログインユーザ情報を取得する
    user_id, _ = get_user_info()

    # ダウンロード対象のドキュメントを Cosmos DB から取得する
    doc = docs_cosmos_container.get_item(doc_id)

    # ドキュメントが存在するかを確認する
    if not doc:
        return "", 404

    # ログインユーザがダウンロード操作ができるかを確認する
    if doc["owner_user_id"] != user_id:
        return "", 403

    # ドキュメントの生成が完了しているかを確認する
    if doc["status"] != "processed":
        return "", 400

    # 生成したドキュメントをMarkdown形式の一時ファイルとして保存する
    doc_id = doc["id"]
    generated_md_content = "\n\n".join(doc["generated_contents"])
    generated_md_path = f"assets/{doc_id}.md"
    with open(generated_md_path, "w", encoding="utf-8") as f:
        f.write(generated_md_content)

    # Markdown形式のファイルをWord形式に変換する
    reference_docx_path = "assets/reference.docx"
    output_docx_path = f"assets/{doc_id}.docx"
    command = f"pandoc {generated_md_path} --from=markdown --to=docx --standalone --reference-doc={reference_docx_path} --output={output_docx_path}"
    subprocess.run(command, shell=True)

    # 生成したWordファイルを Azure Blob Storage にアップロードする
    blob_name = f"{doc_id}.docx"
    blob_container.upload_file(output_docx_path, blob_name)

    # ダウンロードURLを生成する
    download_url = blob_container.get_url_with_sas(blob_name, write=False)

    # 生成したMarkdownファイルとWordファイルを削除する
    os.remove(generated_md_path)
    os.remove(output_docx_path)

    return download_url, 200


# ログイン中のユーザ情報を取得するAPI
@app.route("/api/user", methods=["GET"])
def get_user_info_api():
    user_id, user_name = get_user_info()
    return {"userId": user_id, "userName": user_name}, 200


# ログイン中のユーザ情報を取得する
def get_user_info():

    # ヘッダーに付与されているEntra認証に関するプリンシパル情報を取得する
    # 参考: http://schemas.microsoft.com/identity/claims/objectidentifier
    principal = request.headers.get("X-Ms-Client-Principal", "")

    # プリンシパルが設定されていない場合のユーザIDとユーザ名を定義
    user_id = "00000000-0000-0000-0000-000000000000"
    user_name = ""
    if principal:
        # プリンシパルをBase64デコードする
        principal = base64.b64decode(principal).decode("utf-8")
        principal = json.loads(principal)

        # プリンシパルから特定のキーの値を取得する関数を定義
        def get_princival_value(key, default):
            claims = [c["val"] for c in principal["claims"] if c["typ"] == key]
            return claims[0] if claims else default

        # ユーザーIDとユーザー名を取得する
        user_id = get_princival_value("http://schemas.microsoft.com/identity/claims/objectidentifier", "00000000-0000-0000-0000-000000000000")
        user_name = get_princival_value("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress", "unknown")

    return (user_id, user_name)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
