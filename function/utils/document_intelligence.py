import os
from azure.identity import DefaultAzureCredential
from azure.core.credentials import TokenCredential, AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentAnalysisFeature, ContentFormat

AZURE_DOC_INTELLIGENCE_NAME = os.getenv("AZURE_DOC_INTELLIGENCE_NAME")
AZURE_DOC_INTELLIGENCE_KEY = os.getenv("AZURE_DOC_INTELLIGENCE_KEY")


class DocumentReader:

    def __init__(
        self,
        account_name: str = None,
        credential: TokenCredential = DefaultAzureCredential(),
        key: str = None,
    ):
        account_name = account_name or AZURE_DOC_INTELLIGENCE_NAME
        key = key or AZURE_DOC_INTELLIGENCE_KEY
        if key:
            credential = AzureKeyCredential(key)
        self.client = DocumentIntelligenceClient(
            endpoint=f"https://{account_name}.cognitiveservices.azure.com/",
            credential=credential,
        )

    # ファイルを読み込んで Document Intelligence で解析してHTMLに変換して返す
    def read_document(
        self,
        file_path: str,
        model: str = "prebuilt-layout",
        locale: str = "ja-JP",
        high_resolution: bool = True,
        markdown: bool = False,
        pages: str = None,
    ) -> str:
        result = self.get_ocr_result(file_path, model, locale, high_resolution, markdown, pages)
        return self.get_content_from_ocr_result(result)

    # ファイルを読み込んで Document Intelligence で解析する
    def get_ocr_result(
        self,
        file_path: str,
        model: str = "prebuilt-layout",
        locale: str = "ja-JP",
        high_resolution: bool = True,
        markdown: bool = False,
        pages: str = None,
    ) -> str:
        features = [DocumentAnalysisFeature.OCR_HIGH_RESOLUTION] if high_resolution else []
        output_content_format = ContentFormat.MARKDOWN if markdown else ContentFormat.TEXT
        with open(file_path, "rb") as f:
            poller = self.client.begin_analyze_document(
                model,
                analyze_request=f,
                locale=locale,
                features=features,
                output_content_format=output_content_format,
                content_type="application/octet-stream",
                pages=pages,
            )
        result = poller.result().as_dict()
        return result

    # ファイルを読み込んで Document Intelligence で解析する
    def read_document_by_url(
        self,
        url: str,
        model: str = "prebuilt-layout",
        locale: str = "ja-JP",
        high_resolution: bool = True,
        markdown: bool = False,
        pages: str = None,
    ) -> str:
        result = self.get_ocr_result_by_url(url, model, locale, high_resolution, markdown, pages)
        return self.get_content_from_ocr_result(result)

    # ファイルを読み込んで Document Intelligence で解析する
    def get_ocr_result_by_url(
        self,
        url: str,
        model: str = "prebuilt-layout",
        locale: str = "ja-JP",
        high_resolution: bool = True,
        markdown: bool = False,
        pages: str = None,
    ) -> str:
        features = [DocumentAnalysisFeature.OCR_HIGH_RESOLUTION] if high_resolution else []
        output_content_format = ContentFormat.MARKDOWN if markdown else ContentFormat.TEXT
        poller = self.client.begin_analyze_document(
            model,
            analyze_request=AnalyzeDocumentRequest(url_source=url),
            locale=locale,
            features=features,
            output_content_format=output_content_format,
            pages=pages,
        )
        result = poller.result().as_dict()
        return result

    # Document Intelligence で処理した結果をHTMLに変換する
    def get_content_from_ocr_result(self, result):

        # Document Intelligence で検出したコンテンツのうちテーブルと特定箇所(タイトル等)をHTMLに変換する
        content = result["content"]
        elements = [t | {"type": "table"} for t in result["tables"]]
        elements += [p | {"type": "paragraph"} for p in result["paragraphs"] if "role" in p]
        elements = [e for e in elements if "spans" in e and len(e["spans"]) > 0]
        elements = sorted(elements, key=lambda e: e["spans"][0]["offset"])
        offset_diff = 0

        for elm in elements:
            offset = elm["spans"][0]["offset"]
            length = elm["spans"][0]["length"]
            offset = offset + offset_diff

            elm_content = ""
            if elm["type"] == "table":
                elm_content = self.__convert_table_to_html(elm)
            elif elm["type"] == "paragraph":
                elm_content = self.__convert_paragraph_to_html(elm)

            content = content[:offset] + elm_content + content[offset + length :]
            offset_diff += len(elm_content) - length

        # 特定のワードを除外する
        except_words = [":unselected:", ":selected:"]
        for except_word in except_words:
            content = content.replace(except_word, "")

        return content

    # Document Intelligence で取得したテーブル情報をHTMLに変換する
    def __convert_table_to_html(self, table):
        cells = table["cells"]
        cell_count = 0
        brank_cell_count = 0
        html = "<table>"
        for row_index in range(0, table["rowCount"]):
            # 各行ごとにセルを処理する
            html += "<tr>"
            row_cells = [cell for cell in cells if cell["rowIndex"] == row_index]
            for row_cell in row_cells:
                cell_content = row_cell["content"]
                # cell_content = cell_content.replace("\n", "") # テーブル内の改行を削除する

                # セルの種類によってタグを変える
                tag = "th" if "kind" in row_cell and row_cell["kind"] == "columnHeader" else "td"

                # セルの結合数によってcolspanを設定する
                column_span = f' colspan="{row_cell["columnSpan"]}"' if "columnSpan" in row_cell else ""

                # セルの結合数によってrowspanを設定する
                row_span = f' rowspan="{row_cell["rowSpan"]}"' if "rowSpan" in row_cell else ""

                # セルのHTMLを追記する
                html += f"<{tag}{column_span}{row_span}>{cell_content}</{tag}>"

                # セル数と空白セル数をカウントする
                cell_count += 1
                if len(cell_content) == 0:
                    brank_cell_count += 1

            html += "</tr>"
        html += "</table>"

        # 埋め込まれている画面を無理やりテーブルとして抽出している場合、
        # HTMLテーブルとして成立していないことがあるため、出力しないようにする
        brank_rate = brank_cell_count / cell_count
        if brank_rate > 0.5:
            return ""

        return html

    # Document Intelligence で取得した段落情報をHTMLに変換する
    # タイトル、セクション見出しのみを出力する
    # フッター、ヘッダー、ページ番号、脚注は出力しない
    def __convert_paragraph_to_html(self, paragraph):
        role = paragraph["role"]
        if role == "title":
            return f"<h1>{paragraph['content']}</h1>"
        elif role == "sectionHeading":
            return f"<h2>{paragraph['content']}</h2>"
        else:  # footnote, pageHeader, pageFooter, pageNumber
            return ""
