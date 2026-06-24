const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const dropZonePrompt = document.getElementById('drop-zone-prompt');
const translateBtn = document.getElementById('translate-btn');
const loader = document.getElementById('loader');
const downloadContainer = document.getElementById('download-container');
const downloadLink = document.getElementById('download-link');
const errorBanner = document.getElementById('error-banner');
const targetLangSelect = document.getElementById('target-lang');

let selectedFile = null;

// ドラッグ＆ドロップゾーンをクリックしたときにファイル選択ダイアログを開く
dropZone.addEventListener('click', () => {
    fileInput.click();
});

// ファイル選択ダイアログでファイルが選択されたとき
fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

// ドロップ領域の上にあるときの挙動
dropZone.ondragover = (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
};

dropZone.ondragleave = () => {
    dropZone.classList.remove('drop-zone--over', 'dragover');
};

// ファイルがドロップされたとき
dropZone.ondrop = (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
};

// 共通のファイル処理
function handleFiles(files) {
    if (files.length > 0) {
        const file = files[0];
        if (file.name.endsWith('.md')) {
            selectedFile = file;
            dropZonePrompt.textContent = `選択中: ${file.name}`;
            translateBtn.disabled = false;
            // 以前の結果をリセット
            resetUI();
        } else {
            showError("Markdownファイル (.md) のみアップロード可能である。");
            selectedFile = null;
            translateBtn.disabled = true;
        }
    }
}

// UI状態のリセット
function resetUI() {
    downloadContainer.style.display = 'none';
    errorBanner.style.display = 'none';
}

// エラー表示
function showError(message) {
    errorBanner.textContent = message;
    errorBanner.style.display = 'block';
    downloadContainer.style.display = 'none';
}

// ローディング表示切り替え
function showLoading(isLoading) {
    if (isLoading) {
        loader.style.display = 'block';
        translateBtn.disabled = true;
        dropZone.style.pointerEvents = 'none';
        resetUI();
    } else {
        loader.style.display = 'none';
        translateBtn.disabled = false;
        dropZone.style.pointerEvents = 'auto';
    }
}

// 翻訳ボタンのクリックイベント
translateBtn.addEventListener('click', () => {
    startTranslation();
});

// 翻訳処理の実体
async function startTranslation() {
    if (!selectedFile) {
        showError("翻訳するファイルを選択してほしい。");
        return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("target_lang", targetLangSelect.value);

    showLoading(true);

    try {
        const response = await fetch("/translate", {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            // エラーハンドリング（JSONレスポンスのパースを試みる）
            let errorText = "翻訳リクエストに失敗した。";
            try {
                const errData = await response.json();
                errorText = errData.detail || errorText;
            } catch (_) {}
            throw new Error(errorText);
        }

        // レスポンスをBlob（バイナリ）として受け取る
        const blob = await response.blob();

        // ダウンロード用のURLを生成
        const downloadUrl = URL.createObjectURL(blob);
        downloadLink.href = downloadUrl;
        downloadLink.download = `translated_${selectedFile.name}`;

        // UI表示の更新
        downloadContainer.style.display = 'block';

    } catch (error) {
        showError(error.message || "予期しないエラーが発生した。");
    } finally {
        showLoading(false);
    }
}
