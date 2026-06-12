# 🎨 HPB スタイル自動化

salon board に画像を自動で投稿する完全自動化システム

---

## 📊 システム構成

```
┌─────────────────────────────────────────────────────────┐
│  Web アプリ (index.html)                                │
│  店舗選択 → スタイリスト選択 → クーポン選択 → 画像UP    │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────┐
│  Flask バックエンド (app.py)                             │
│  - 店舗/スタイリスト/クーポンデータ配信                  │
│  - 画像受け取り＆分析                                     │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────┐
│  Google Sheets マスターデータ                            │
│  - Shops: 13 店舗                                        │
│  - Stylists: 97 スタイリスト                             │
│  - Coupons: 172 クーポン                                 │
└──────────────────┬──────────────────────────────────────┘
                   │
         ┌─────────┴─────────┐
         ↓                   ↓
    ┌─────────────────┐   ┌──────────────────────┐
    │ 画像分析        │   │ HPB 自動投稿         │
    │ (Ollama/Vision) │   │ (Selenium)           │
    └─────────────────┘   └────────┬─────────────┘
                                   │
                                   ↓
                          HPB Salon Board に投稿
```

---

## 🚀 クイックスタート

### 1️⃣ HPB ログイン情報を設定

`hpb_config.json` を作成：

```json
{
  "username": "your_salon_id_or_email",
  "password": "your_password"
}
```

### 2️⃣ Web アプリを起動

```bash
# バックエンド（Flask）を起動
python3 app.py

# ブラウザで http://localhost:5000 にアクセス
```

### 3️⃣ スタイル画像を投稿

1. 店舗を選択
2. スタイリストを選択（自動フィルタ）
3. クーポンを選択（自動フィルタ）
4. 画像をドラッグ&ドロップ
5. 「投稿する」をクリック

---

## 📁 ファイル構成

```
HPBスタイル自動化/
├── index.html                      # Web アプリ UI
├── app.py                          # Flask バックエンド
├── image_analyzer.py               # 画像分析スクリプト
├── hpb_poster.py                   # HPB 自動投稿スクリプト
├── coupon_updater.py               # クーポン自動更新スクリプト
├── populate_sheets.py              # Google Sheets にデータ入力
├── hpb_config.json                 # HPB ログイン情報（手動作成）
├── salons_data.json                # 店舗マスターデータ
├── uploads/                        # アップロード済み画像
└── README.md                       # このファイル
```

---

## ⚙️ 各スクリプトの使い方

### 1. `populate_sheets.py` - Google Sheets にデータを入力

```bash
python3 populate_sheets.py
```

**出力例：**
```
✅ Shops シート完了（13 店舗）
✅ Stylists シート完了（全 97 名）
✅ Coupons シート完了（全 172 件）
```

### 2. `coupon_updater.py` - HPB からクーポン&スタイリストを自動取得

```bash
python3 coupon_updater.py
```

**毎日朝に自動実行する場合（cron）：**

```bash
# ターミナルで以下を実行
crontab -e

# 以下を追加（毎日朝 5:00 に実行）
0 5 * * * cd /Users/wakatsukiairi/Downloads/07_バイト・インターン/sand/HPBスタイル自動化 && python3 coupon_updater.py >> /tmp/coupon_update.log 2>&1
```

### 3. `hpb_poster.py` - HPB に直接投稿（テスト用）

```bash
python3 hpb_poster.py
```

---

## 📊 Google Sheets 構成

### Shops シート
| salonId | salonName |
|---------|-----------|
| H000394957 | sand 銀座 【サンド ギンザ】 |
| H000453258 | sand 表参道 【サンド オモテサンドウ】 |
| ... | ... |

### Stylists シート
| salonId | stylistName |
|---------|-------------|
| H000394957 | 指名 なし |
| H000394957 | 江上 京花 |
| H000394957 | 関 好海 |
| ... | ... |

### Coupons シート
| salonId | couponName |
|---------|------------|
| H000394957 | 【全員】似合わせカット+Aujua2stepトリートメント｜銀座 |
| H000394957 | 【全員】似合わせカット+Aujua4stepトリートメント｜銀座 |
| ... | ... |

---

## 🔄 ワークフロー

### 毎日の自動更新（朝 5:00）

```
HPB Salon Board
    ↓ (coupon_updater.py)
Google Sheets を自動更新
    ↓
Web アプリが常に最新データを表示
```

### ユーザーが画像を投稿する場合

```
Web アプリで投稿
    ↓
Flask バックエンド が受け取る
    ↓
画像を分析（角度、髪質など）
    ↓
HPB Salon Board に自動投稿
```

---

## 🛠️ トラブルシューティング

### Q: Web アプリにアクセスできない

```bash
# Flask が起動しているか確認
lsof -i :5000

# 強制終了する場合
lsof -i :5000 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

### Q: Google Sheets に接続できない

- `hpb-style-automation-0311880cf963.json` ファイルが存在するか確認
- Google Sheets を共有ユーザーと共有しているか確認

### Q: HPB にログインできない

- `hpb_config.json` の username/password が正しいか確認
- HPB の画面構造が変更された可能性がある（Selenium スクリプトを調整）

---

## 📱 デプロイ（Render / Replit）

### Render にデプロイ

```bash
# 1. Render アカウント作成
# 2. GitHub に push
# 3. Render で新規 Web Service 作成
# 4. GitHub リポジトリを接続
# 5. Build command: pip install -r requirements.txt
# 6. Start command: python app.py
```

### requirements.txt

```
flask==3.1.3
flask-cors==6.0.5
gspread==6.2.1
google-auth==2.53.0
google-auth-oauthlib==1.4.0
selenium==4.44.0
pillow==10.4.0
requests==2.34.2
```

---

## 📈 次のステップ

- [ ] HPB ログイン情報を `hpb_config.json` に設定
- [ ] `coupon_updater.py` をテスト実行
- [ ] cron で毎日朝に自動実行
- [ ] Render or Replit にデプロイ
- [ ] HPB の画面構造に合わせて Selenium スクリプトを調整

---

## 📞 サポート

問題が発生した場合は、ターミナルのログを確認して、画面構造が変更されていないか確認してください。

HPB の Salon Board は頻繁に更新される可能性があるため、その場合は Selenium スクリプトを調整が必要です。
