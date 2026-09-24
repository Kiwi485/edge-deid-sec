# CVAT 標註與 segmentation 訓練

這份文件說明如何使用 CVAT 建立舌頭 segmentation 資料集，並訓練 `src/seg/train.py` 使用的模型。

## 1. 使用 Docker 開啟 CVAT

Windows 需要先安裝並啟動 Docker Desktop、WSL2 和 Ubuntu（WSL2 distribution）。在 PowerShell 確認：

```powershell
wsl -l -v
docker --version
docker compose version
docker ps
```

在 WSL2 Ubuntu 中下載並啟動 CVAT：

```bash
git clone https://github.com/cvat-ai/cvat.git
cd cvat
docker compose up -d
docker compose ps
```

等主要 container 顯示 `Up` 後，在瀏覽器開啟 `http://localhost:8080`。

如果要讓區域網路其他電腦連線，在 `~/cvat/.env` 加入自己電腦的 IP：

```env
CVAT_HOST=192.168.68.92
```

再重建服務：

```bash
docker compose down
docker compose up -d --force-recreate
```

使用 `http://192.168.68.92:8080` 開啟時，請把 IP 換成實際 IP。停止 CVAT：

```bash
docker compose down
```

## 2. 建立 CVAT 管理員使用者

在 `~/cvat` 執行：

```bash
docker exec -it cvat_server bash -ic 'python3 manage.py createsuperuser'
```

依照提示輸入 Username、Email 和 Password。若找不到 `cvat_server`，先執行 `docker compose ps`，再把指令中的 container 名稱換成實際名稱。

## 3. 在 CVAT 標註

1. 開啟 [CVAT](https://app.cvat.ai) 並登入。
2. 建立 Project，名稱可使用 `tongue-seg-v1`。
3. 建立一個名稱為 `tongue` 的 Polygon 標籤。
4. 建立 Task 並上傳舌頭影像。
5. 開啟 Job，選擇 `tongue`，使用 **Polygon + Shape** 逐張沿著舌頭邊界標註。

建議先標註少量影像確認格式，再擴大到完整資料集。

## 4. 匯出 COCO 格式

在 CVAT 的 Task 頁面選擇 **Export dataset**，格式選擇 **COCO 1.0**（Instance Segmentation），下載並解壓縮。

訓練資料應整理成：

```text
data/cvat/
└── train/
    ├── images/
    │   ├── image_001.jpg
    │   └── image_002.jpg
    └── annotations/
        └── instances_default.json
```

PowerShell 範例：

```powershell
New-Item -ItemType Directory -Path data\cvat\train\images -Force
New-Item -ItemType Directory -Path data\cvat\train\annotations -Force
Copy-Item "C:\path\to\cvat-export\images\default\*" data\cvat\train\images\
Copy-Item "C:\path\to\cvat-export\annotations\*" data\cvat\train\annotations\
```

請把 `C:\path\to\cvat-export` 換成實際的解壓縮位置。原始影像通常不應提交到 Git。

## 5. 安裝訓練套件

```powershell
.\.venv311\Scripts\Activate.ps1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install segmentation-models-pytorch albumentations
```

## 6. 先做小型測試

```powershell
.\.venv311\Scripts\python.exe src\seg\train.py `
  --data-dir data\cvat `
  --epochs 3 `
  --batch-size 2 `
  --no-pretrain
```

小型測試只用來確認資料格式和程式可以啟動，不代表模型品質。

## 7. 正式訓練

```powershell
.\.venv311\Scripts\python.exe src\seg\train.py `
  --data-dir data\cvat `
  --epochs 50 `
  --batch-size 4
```

Windows 建議維持預設 `--num-workers 0`。

訓練完成後，模型會寫入：

```text
models/seg/best.pth
models/seg/last.pth
```

主 pipeline 使用 `models/seg/best.pth`。若該檔案不存在，主 pipeline 會使用 HSV mask fallback。

## 8. 單張推論

```powershell
.\.venv311\Scripts\python.exe src\seg\inference.py `
  --image path\to\photo.jpg `
  --model models\seg\best.pth `
  --out-dir outputs
```

輸出會包含 mask 與舌頭區域影像。完整 pipeline 的執行方式請回到 [README.md](../README.md)。
