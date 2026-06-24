import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
import deepl
import uvicorn
import logging

# .env ファイルから環境変数を読み込む
load_dotenv()

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

logger = logging.getLogger("uvicorn.error")

translator = None
# APIキーの検証と初期化
def init_translator():
    global translator
    if DEEPL_API_KEY:
        try:
            translator = deepl.Translator(DEEPL_API_KEY)
            logger.info("DeepL APIの初期化に成功した")
        except Exception as e:
            logger.error(f"DeepL APIの初期化に失敗した: {e}")
    else:
        logger.error("DEEPL_API_KEY が設定されていない。.env ファイルを作成するか、環境変数を設定してほしい。")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # アプリ起動時に初期化処理を走らせる（Uvicornのロガーセットアップ完了後）
    init_translator()
    yield

app = FastAPI(
    title="Markdown Translator API",
    description="DeepL APIを利用してMarkdownファイルを翻訳するローカルAPIサーバー",
    version="1.0.0",
    lifespan=lifespan
)

def remove_temp_file(path: str):
    """レスポンス送信後に一時ファイルを削除するクリーンアップ関数"""
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            logger.error(f"一時ファイルの削除に失敗した: {path}, Error: {e}")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    # staticフォルダに favicon.ico を置いた場合
    return FileResponse("static/favicon.ico")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

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

        try:
            # 1. まずはレイアウトを最も綺麗に保持できるドキュメント翻訳APIを試す
            translator.translate_document_from_filepath(
                input_path,
                output_path,
                target_lang=target_lang
            )
        except deepl.DeepLException as e:
            err_msg = str(e)
            # APIキーのプランや権限の制限によりMarkdownのドキュメント翻訳が拒否された場合のフォールバック
            if "not allowed to translate" in err_msg or "Authorization failure" in err_msg:
                logger.info("ドキュメント翻訳APIが拒否されたため、テキスト翻訳APIによるフォールバックを実行する。")
                try:
                    with open(input_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # テキスト翻訳APIを使用してMarkdownをテキストとして翻訳
                    # DeepLは優秀なため、記号（#, *, リンク等）をある程度保持したまま翻訳できる
                    result = translator.translate_text(
                        content,
                        target_lang=target_lang
                    )

                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(result.text)
                except Exception as fallback_err:
                    raise HTTPException(
                        status_code=500,
                        detail=f"代替のテキスト翻訳処理にも失敗した: {str(fallback_err)}"
                    )
            else:
                # それ以外のDeepLエラー（通信エラー、制限超過など）はそのまま投げる
                raise HTTPException(status_code=500, detail=f"DeepL翻訳エラー: {err_msg}")

        # 翻訳完了後、レスポンス送信用に退避
        # レスポンス送信後にフォルダごと削除するため、BackgroundTasksに登録する
        background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)

        return FileResponse(
            path=output_path,
            filename=f"translated_{file.filename}",
            media_type="text/markdown"
        )

    except HTTPException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"システムエラー: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)