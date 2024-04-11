import os
import re
import json
from datetime import datetime, timezone, timedelta
from azure.identity import DefaultAzureCredential
from azure.core.credentials import TokenCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

AZURE_STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")


class BlobContainer:

    def __init__(
        self,
        account_name: str = None,
        container_name: str = None,
        credential: TokenCredential = DefaultAzureCredential(),
        connection_string: str = None,
    ):
        account_name = account_name or AZURE_STORAGE_ACCOUNT_NAME
        container_name = container_name or AZURE_STORAGE_CONTAINER_NAME
        self.connection_string = connection_string or AZURE_CONNECTION_STRING
        if self.connection_string:
            self.blob_client = BlobServiceClient.from_connection_string(connection_string)
        else:
            self.credential = credential
            self.blob_client = BlobServiceClient(
                account_url=f"https://{account_name}.blob.core.windows.net",
                credential=self.credential,
            )
        self.container_client = self.blob_client.get_container_client(container_name)
        if not self.container_client.exists():
            self.container_client.create_container()

    def upload_json(self, blob_name: str, data: object, overwrite: bool = True):
        """
        JSONデータを指定された名前のBlobとしてアップロードします。

        Args:
            blob_name (str): アップロードするBlobの名前。
            data (object): アップロードするJSONデータ。
            overwrite (bool, optional): 既存のBlobを上書きするかどうか。デフォルトはTrue。

        Returns:
            None
        """
        self.upload_string(blob_name, json.dumps(data, indent=2, ensure_ascii=False), overwrite=overwrite)

    def upload_string(self, blob_name: str, s: str, overwrite: bool = True):
        """
        文字列データを指定された名前のBlobとしてアップロードします。

        Args:
            blob_name (str): アップロードするBlobの名前。
            s (str): アップロードする文字列データ。
            overwrite (bool, optional): 既存のBlobを上書きするかどうか。デフォルトはTrue。

        Returns:
            None
        """
        self.upload_bytes(blob_name, s.encode(), overwrite=overwrite)

    def upload_file(self, file_path: str, blob_name: str = None, overwrite: bool = True):
        """
        ファイルを指定された名前のBlobとしてアップロードします。

        Args:
            file_path (str): アップロードするファイルのパス。
            blob_name (str, optional): アップロードするBlobの名前。指定しない場合はファイル名が使用されます。
            overwrite (bool, optional): 既存のBlobを上書きするかどうか。デフォルトはTrue。

        Returns:
            None
        """
        if blob_name is None:
            blob_name = os.path.basename(file_path)
        with open(file_path, "rb") as data:
            self.upload_bytes(blob_name, data, overwrite=overwrite)

    def upload_bytes(self, blob_name: str, data: bytes, overwrite: bool = True):
        """
        バイトデータを指定された名前のBlobとしてアップロードします。

        Args:
            blob_name (str): アップロードするBlobの名前。
            data (bytes): アップロードするバイトデータ。
            overwrite (bool, optional): 既存のBlobを上書きするかどうか。デフォルトはTrue。

        Returns:
            None
        """
        self.container_client.upload_blob(name=blob_name, data=data, overwrite=overwrite)

    def download_bytes(self, blob_name: str) -> bytes:
        """
        指定された名前のBlobからバイトデータをダウンロードします。

        Args:
            blob_name (str): ダウンロードするBlobの名前。

        Returns:
            bytes: ダウンロードしたバイトデータ。
        """
        blob = self.container_client.get_blob_client(blob_name)
        return blob.download_blob().readall()

    def download_string(self, blob_name: str) -> str:
        """
        指定された名前のBlobから文字列データをダウンロードします。

        Args:
            blob_name (str): ダウンロードするBlobの名前。

        Returns:
            str: ダウンロードした文字列データ。
        """
        return self.download_bytes(blob_name).decode()

    def download_json(self, blob_name: str) -> object:
        """
        指定された名前のBlobからJSONデータをダウンロードします。

        Args:
            blob_name (str): ダウンロードするBlobの名前。

        Returns:
            object: ダウンロードしたJSONデータ。
        """
        return json.loads(self.download_string(blob_name))

    def list_blobs(self):
        """
        コンテナ内のすべてのBlobをリストアップします。

        Returns:
            list: コンテナ内のすべてのBlobのリスト。
        """
        return [b for b in self.container_client.list_blobs()]

    def delete_blob(self, blob_name):
        """
        指定された名前のBlobを削除します。

        Args:
            blob_name (str): 削除するBlobの名前。

        Returns:
            None
        """
        if self.container_client.get_blob_client(blob_name).exists():
            self.container_client.delete_blob(blob_name)

    def get_url_with_sas(self, blob_name: str, read: bool = True, write: bool = True, expiry: int = 300):
        """
        SASトークンを使用したBlobのURLを取得します。

        Args:
            blob_name (str): SASトークンを取得するBlobの名前。
            read (bool, optional): 読み取り権限を含めるかどうか。デフォルトはTrue。
            write (bool, optional): 書き込み権限を含めるかどうか。デフォルトはTrue。
            expiry (int, optional): 有効期限（秒単位）。デフォルトは300秒（5分間）。

        Returns:
            str: SASトークンを含むBlobのURL。
        """

        # ユーザー委任キーを生成する
        key_start_time = datetime.now(timezone.utc)
        key_expiry_time = key_start_time + timedelta(seconds=expiry)
        user_delegation_key = self.blob_client.get_user_delegation_key(key_start_time=key_start_time, key_expiry_time=key_expiry_time)

        # SASトークンを生成する
        if self.connection_string:
            blob_url = f"https://{self.blob_client.account_name}.blob.core.windows.net/{self.container_client.container_name}/{blob_name}"
            sas = generate_blob_sas(
                account_name=self.container_client.account_name,
                account_key=re.search(r"AccountKey=([^;]+)", self.connection_string).group(1),
                container_name=self.container_client.container_name,
                blob_name=blob_name,
                permission=BlobSasPermissions(read=read, write=write),
                expiry=datetime.now(timezone.utc) + timedelta(seconds=expiry),
            )
        else:
            blob_url = f"https://{self.blob_client.account_name}.blob.core.windows.net/{self.container_client.container_name}/{blob_name}"
            sas = generate_blob_sas(
                account_name=self.container_client.account_name,
                container_name=self.container_client.container_name,
                blob_name=blob_name,
                user_delegation_key=user_delegation_key,
                permission=BlobSasPermissions(read=read, write=write),
                expiry=datetime.now(timezone.utc) + timedelta(seconds=expiry),
            )

        # SASトークンを含むBlobのURLを返す
        return f"{blob_url}?{sas}"
