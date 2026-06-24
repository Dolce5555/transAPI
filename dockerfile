FROM ghcr.io/astral-sh/uv:0.11.2-python3.13-trixie-slim

RUN apt-get update && apt-get upgrade -y

# 環境変数の設定
# UV_COMPILE_BYTECODE=1: Pythonの起動を速くするためにバイトコードをコンパイル
# UV_LINK_MODE=copy: Docker内ではハードリンクではなくコピーを使う設定
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 依存関係のインストール
# --mount=type=cache: キャッシュを利用してビルドを爆速化
# --frozen: uv.lockの内容を厳密に守る（勝手なアップデートを防ぐ）
# --no-dev: 開発用パッケージ（pytestなど）を含めない
# --no-install-project: この段階ではプロジェクト自体のコードはインストールしない
WORKDIR /app/
COPY pyproject.toml uv.lock README.md /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
COPY . /app/
ENV PATH="/app/.venv/bin:$PATH"

CMD ["uv", "run", "python", "main.py"]