import os
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from dotenv import load_dotenv
import deepl

# .env ファイルから環境変数を読み込む
load_dotenv()

app = FastAPI(
    title="Markdown Translator API",
    description="DeepL APIを利用してMarkdownファイルを翻訳するローカルAPIサーバー",
    version="1.0.0"
)

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

# APIキーの検証と初期化
translator = None
if DEEPL_API_KEY:
    try:
        translator = deepl.Translator(DEEPL_API_KEY)
    except Exception as e:
        print(f"[Warning] DeepL APIの初期化に失敗した: {e}")
else:
    print("[Warning] DEEPL_API_KEY が設定されていない。.env ファイルを作成するか、環境変数を設定してほしい。")

def remove_temp_file(path: str):
    """レスポンス送信後に一時ファイルを削除するクリーンアップ関数"""
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"[Error] 一時ファイルの削除に失敗した: {path}, Error: {e}")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "Markdown Translator API is running. Access /docs for API documentation.",
        "deepl_initialized": translator is not None
    }

@app.post("/translate", summary="Markdownファイルを翻訳する")
async def translate_markdown(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="翻訳するMarkdownファイル (.md)"),
    target_lang: str = "JA"  # デフォルトは日本語。DeepLがサポートする言語コード（EN-US, DE, FRなど）
):
    global translator
    # リクエスト時にもAPIキーが利用可能かチェック（起動後に.envが設定された場合に対応）
    if not translator:
        api_key = os.getenv("DEEPL_API_KEY")
        if api_key:
            try:
                translator = deepl.Translator(api_key)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"DeepL APIの初期化に失敗した: {e}")
        else:
            raise HTTPException(
                status_code=500, 
                detail="DEEPL_API_KEYが設定されていない。環境変数または.envファイルを設定してほしい。"
            )

    if not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Markdownファイル (.md) のみをサポートしている。")

    # 一時フォルダを作成して処理を行う
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, file.filename)
    output_path = os.path.join(temp_dir, f"translated_{file.filename}")

    try:
        # アップロードされたファイルを一時フォルダに保存
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # DeepLドキュメント翻訳を実行 (同期的に完了を待ち、ステータスを監視する)
        # DeepL SDKは内部でアップロード、ポーリング、ダウンロードを自動で処理する
        translator.translate_document_from_filepath(
            input_path,
            output_path,
            target_lang=target_lang
        )

        # 翻訳完了後、レスポンス送信用に退避
        # レスポンス送信後にフォルダごと削除するため、BackgroundTasksに登録する
        background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)

        return FileResponse(
            path=output_path,
            filename=f"translated_{file.filename}",
            media_type="text/markdown"
        )

    except deepl.DeepLException as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"DeepL翻訳エラー: {str(e)}")
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"システムエラー: {str(e)}")
