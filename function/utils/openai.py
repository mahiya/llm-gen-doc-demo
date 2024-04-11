import os
import json
import threading
from openai import AzureOpenAI
from typing import List, Callable
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

AZURE_OPENAI_ACCOUNT_NAME = os.getenv("AZURE_OPENAI_ACCOUNT_NAME")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_CHAT_MODEL = os.getenv("AZURE_OPENAI_CHAT_MODEL")
AZURE_OPENAI_EMBED_MODEL = os.getenv("AZURE_OPENAI_EMBED_MODEL")


class ChatCompletionClient:

    def __init__(
        self,
        account_name: str = None,
        model_name: str = None,
        key: str = None,
        max_tokens: int = 4096,
        api_version: str = "2024-02-15-preview",
    ):
        account_name = account_name or AZURE_OPENAI_ACCOUNT_NAME
        model_name = model_name or AZURE_OPENAI_CHAT_MODEL
        key = key or AZURE_OPENAI_KEY

        if key:
            self.client = AzureOpenAI(
                azure_endpoint=f"https://{account_name}.openai.azure.com/",
                api_key=key,
                api_version=api_version,
            )
        else:
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
            self.client = AzureOpenAI(
                azure_endpoint=f"https://{account_name}.openai.azure.com/",
                azure_ad_token_provider=token_provider,
                api_version=api_version,
            )

        self.model_name = model_name
        self.max_tokens = max_tokens

    def get_completion(
        self,
        messages: List[dict],
        temperature: int = 0,
        json_format: bool = False,
        max_tokens: int = None,
    ) -> str:
        """
        Azure OpenAI Service Chat Completion API から Completion を取得します

        :param messages: チャットメッセージのリスト
        :param json_format: JSON形式でのレスポンスを取得するかどうかのフラグ
        :param temperature: Completion の生成に使用される温度パラメータ
        :return: 生成された Completion
        """
        response_format = {"type": "json_object"} if json_format else None
        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            max_tokens=max_tokens if max_tokens else self.max_tokens,
            temperature=temperature,
            response_format=response_format,
        )
        completion = resp.choices[0].message.content
        return completion

    def get_completion_with_tools(
        self,
        messages: List[dict],
        tools: List[dict],
        available_functions: List[Callable],
        temperature: int = 0,
    ) -> str:
        """
        Azure OpenAI Service Chat Completion API から Functions Calling 付きでCompletion を取得します

        :param messages: チャットメッセージのリスト
        :param tools: 使用可能なツール(Function Calling)の定義
        :param available_functions: 使用可能な関数のリスト
        :param temperature: Completion の生成に使用される温度パラメータ
        :return: 生成された Completion
        """
        while True:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=temperature,
                tools=tools,
                tool_choice="auto",
            )
            choice = resp.choices[0]
            if choice.message.tool_calls:
                messages.append(choice.message)
                for tool_call in choice.message.tool_calls:
                    func_name = tool_call.function.name
                    func_to_call = available_functions[func_name]
                    func_args = json.loads(tool_call.function.arguments)
                    func_response = func_to_call(**func_args)
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": func_name,
                            "content": func_response,
                        }
                    )
            else:
                return resp.choices[0].message.content

    def create_message(self, system_message: str, user_message: str) -> List[dict]:
        """
        システムメッセージとユーザーメッセージからチャットメッセージのリストを作成します

        :param system_message: システムからのメッセージ
        :param user_message: ユーザーからのメッセージ
        :return: チャットメッセージのリスト
        """
        return [{"role": "system", "content": system_message}, {"role": "user", "content": user_message}]


class EmbeddingsClient:

    def __init__(
        self,
        acount_name: str = None,
        model_name: str = None,
        key: str = None,
        api_version: str = "2024-02-15-preview",
    ):
        account_name = acount_name or AZURE_OPENAI_ACCOUNT_NAME
        model_name = model_name or AZURE_OPENAI_EMBED_MODEL
        key = key or AZURE_OPENAI_KEY

        if key:
            self.client = AzureOpenAI(
                azure_endpoint=f"https://{account_name}.openai.azure.com/",
                api_key=key,
                api_version=api_version,
            )
        else:
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
            self.client = AzureOpenAI(
                azure_endpoint=f"https://{account_name}.openai.azure.com/",
                azure_ad_token_provider=token_provider,
                api_version=api_version,
            )

        self.model_name = model_name

    def get_embeds(self, text: str) -> List[float]:
        """
        テキストの埋め込みを取得します。

        :param text: 埋め込み取得対象のテキスト
        :return: 埋め込み
        """
        resp = self.client.embeddings.create(model=self.model_name, input=text)
        embed = resp.data[0].embedding
        return embed
