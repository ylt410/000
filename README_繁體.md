# 兩款角色的本機 DLC 適配器

適配器原始碼和 templates 不含兩款模型的二進位、貼圖或作者壓縮檔。發布壓縮包另附 v1.4 的 `script/script_wasm.rpf` 選單覆蓋檔，該檔本身不含這兩款模型。使用者仍須自行取得作者原始 ZIP/RAR；工具會核對檔案與四個模型資源的固定 SHA-256，拒絕其他版本。

作者頁：[Sexy Beauty / KaKa_946](https://www.gta5-mods.com/player/sexy-beauty-kaka_946)、[Tsukushi Fortune Bikini / StrideR](https://www.gta5-mods.com/player/18-tsukushi-fortune-bikini-dead-or-alive-xtreme-addon)。Tsukushi 作者明確禁止未經許可轉載此 MOD。產出的 DLC/OIV 只供本機安裝，不要公開、轉發或上傳。Sexy Beauty 說明頁沒有找到作者重傳許可聲明；仍只在本機使用，並遵守 GTA5-Mods.com 條款。

## 建置

需要 Python 3.10+。ZIP 由 Python 標準函式庫處理。RAR5 另需 `libarchive-c >= 5.3` 與作業系統的 libarchive（需支援 RAR5）：

```sh
python -m pip install -r requirements.txt
python import_models.py \
  --sexy-beauty /path/to/author-sexy-beauty.zip \
  --tsukushi /path/to/author-tsukushi.rar \
  --output ./local-build
```

輸出目錄必須是新目錄或空目錄；有檔案時工具會拒絕覆寫。建置成功後，DLC 位於：

```text
local-build/update/x64/dlcpacks/rdebeauty/dlc.rpf
local-build/update/x64/dlcpacks/rdetfortune/dlc.rpf
```

可將這兩個 DLC 目錄安裝到 GTA V 的 `update/x64/dlcpacks/`。這是裸 DLC 輸出，不會自動編輯遊戲檔或上傳任何內容。輸出 SHA-256 會與已核對的主工程預期值比對；Tsukushi YDD 僅在原始哈希吻合時，將偏移 3707412 的 12 個 `CD` 保留位元組歸零，並確認解壓後只有這 12 bytes 改變；Beauty 不作修改。

## 手機選單與 v1.4 配套腳本

只有兩個 DLC 不會讓角色出現在手機選單。若要使用 13 人選單，須先安裝既有公開的 [v1.3 Rebuilt Full 基底](https://github.com/ylt410/000/releases/tag/rde-wse-fusion-ios-v0.59.68-custom-characters-rebuilt-full-v1.3-weapon-fix-test)（含原 11 個 DLC），再以 v1.4 配套 `script_wasm.rpf` 後置載入。發布壓縮包會附此選單覆蓋檔，路徑為 `script/script_wasm.rpf`；工具固定核對已知 v1.4 檔案的大小與 SHA-256，拒絕其他檔案。可一併產生三目標 NativeOIV：

```sh
python import_models.py \
  --sexy-beauty /path/to/author-sexy-beauty.zip \
  --tsukushi /path/to/author-tsukushi.rar \
  --script-overlay ./script/script_wasm.rpf \
  --output ./local-build
```

OIV 只替換 `x64.rpf/levels/gta5/script/script_wasm.rpf`，並加入上列兩個 DLC；請在既有基底之後安裝。若不提供 `--script-overlay`，工具只生成裸 DLC，不會產生選單更新。NativeOIV 由 `assembly.xml` 加 `content/files/` 組成，包含腳本覆蓋與兩個 DLC；建置時會檢查 ZIP CRC、assembly targets 和三個 payload 的逐項 SHA-256。腳本覆蓋需要在 v1.3 基底之後載入；適配器不修改 v1.3 原始 11 個 DLC。

## 資源限制

模型套件限定為各自原始的 `.ydd`、`.yft`、`.ymt`、`.ytd` 四件組。`peds.meta` 連結遊戲的共享 `comp_peds_generic` TXD；工具不附共享遊戲資源，也不製作缺少的貼圖占位。部分材質引用可能依賴遊戲外部資源，因此本適配器不宣稱完整渲染，也不代表已完成目標手機實機驗收。兩款模型的衣物/裝飾已烘焙在原模型中，這個適配器不增加衣著切換選項。
