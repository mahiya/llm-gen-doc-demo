# ベースイメージを指定
FROM python:3.11

# pandoc をインストール
RUN apt-get update
RUN apt-get install -y pandoc

# 作業ディレクトリを設定
WORKDIR /app

# ホストのカレントディレクトリにあるファイルをコンテナの作業ディレクトリにコピー
COPY . /app

# 必要なパッケージをインストール
RUN pip install --no-cache-dir -r requirements.txt

# Flaskアプリを実行
CMD ["python", "app.py"]