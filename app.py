#!/usr/bin/env python3
"""
HPB Style Automation バックエンド
Flask で REST API を提供
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import json
import os
from pathlib import Path

app = Flask(__name__)
CORS(app)

# 設定
BASE_DIR = Path(__file__).parent
SPREADSHEET_ID = '1JwXkoU3-GrfuGmATDwtX6Tq5iRsQGM-HXyIjcEcQZZY'
UPLOAD_FOLDER = BASE_DIR / 'uploads'
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Google Sheets 初期化
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# 環境変数から Google Service Account JSON を読み込む
google_creds_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
if google_creds_json:
    import io
    from google.oauth2.service_account import Credentials
    credentials = Credentials.from_service_account_info(
        json.loads(google_creds_json),
        scopes=SCOPES
    )
else:
    # ローカル開発用
    SERVICE_ACCOUNT_FILE = os.path.expanduser('~/Downloads/hpb-style-automation-0311880cf963.json')
    credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

gspread_client = gspread.authorize(credentials)
spreadsheet = gspread_client.open_by_key(SPREADSHEET_ID)

# キャッシュ（メモリ内）
cache = {
    'shops': None,
    'stylists': None,
    'coupons': None
}

def load_data():
    """Google Sheets からデータを読み込み（キャッシュ使用）"""
    global cache

    try:
        if not cache['shops']:
            print("📍 Shops を読み込み中...")
            shops_data = spreadsheet.worksheet('Shops').get_all_values()[1:]
            cache['shops'] = {row[0]: row[1] for row in shops_data if len(row) >= 2}
            print(f"  ✓ {len(cache['shops'])} 店舗を読み込み")

        if not cache['stylists']:
            print("👤 Stylists を読み込み中...")
            stylists_data = spreadsheet.worksheet('Stylists').get_all_values()[1:]
            stylists_by_shop = {}
            for row in stylists_data:
                if len(row) >= 2:
                    salon_id, stylist = row[0], row[1]
                    if salon_id not in stylists_by_shop:
                        stylists_by_shop[salon_id] = []
                    stylists_by_shop[salon_id].append(stylist)
            cache['stylists'] = stylists_by_shop
            print(f"  ✓ スタイリスト情報を読み込み")

        if not cache['coupons']:
            print("🎟️ Coupons を読み込み中...")
            coupons_data = spreadsheet.worksheet('Coupons').get_all_values()[1:]
            coupons_by_shop = {}
            for row in coupons_data:
                if len(row) >= 2:
                    salon_id, coupon = row[0], row[1]
                    if salon_id not in coupons_by_shop:
                        coupons_by_shop[salon_id] = []
                    coupons_by_shop[salon_id].append(coupon)
            cache['coupons'] = coupons_by_shop
            print(f"  ✓ {sum(len(v) for v in coupons_by_shop.values())} クーポンを読み込み")

        return cache
    except Exception as e:
        print(f"❌ データ読み込みエラー: {e}")
        import traceback
        traceback.print_exc()
        return cache

@app.route('/')
def serve_index():
    """フロントエンド を提供"""
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """静的ファイルを提供"""
    return send_from_directory(BASE_DIR, path)

@app.route('/api/shops', methods=['GET'])
def get_shops():
    """全店舗一覧"""
    data = load_data()
    shops = [{'id': k, 'name': v} for k, v in data['shops'].items()]
    return jsonify(shops)

@app.route('/api/stylists/<salon_id>', methods=['GET'])
def get_stylists(salon_id):
    """店舗ごとのスタイリスト一覧"""
    data = load_data()
    stylists = data['stylists'].get(salon_id, [])
    return jsonify(stylists)

@app.route('/api/coupons/<salon_id>', methods=['GET'])
def get_coupons(salon_id):
    """店舗ごとのクーポン一覧"""
    data = load_data()
    coupons = data['coupons'].get(salon_id, [])
    return jsonify(coupons)

@app.route('/api/upload', methods=['POST'])
def upload_style():
    """
    スタイル画像をアップロード＆処理

    リクエスト:
    - salonId: 店舗ID
    - stylist: スタイリスト名
    - coupon: クーポン名
    - image: 画像ファイル
    """
    try:
        if 'image' not in request.files:
            return jsonify({'error': '画像ファイルが必須です'}), 400

        salon_id = request.form.get('salonId')
        stylist = request.form.get('stylist')
        coupon = request.form.get('coupon')
        image_file = request.files['image']

        if not all([salon_id, stylist, coupon, image_file]):
            return jsonify({'error': 'すべてのフィールドが必須です'}), 400

        # 画像を保存
        filename = f"{salon_id}_{stylist}_{image_file.filename}"
        filepath = UPLOAD_FOLDER / filename
        image_file.save(filepath)

        # 画像分析
        from image_analyzer import analyze_image
        analysis = analyze_image(str(filepath))

        # HPB に投稿（テスト用：ログに出力）
        print(f"\n🎨 HPB に投稿します")
        print(f"  店舗: {salon_id}")
        print(f"  スタイリスト: {stylist}")
        print(f"  クーポン: {coupon}")
        print(f"  画像: {filepath}")
        print(f"  分析: {analysis}")

        # 実装版：Selenium で HPB に投稿
        try:
            import json
            hpb_config_file = Path(__file__).parent / 'hpb_config.json'
            if hpb_config_file.exists():
                with open(hpb_config_file) as f:
                    hpb_config = json.load(f)

                from hpb_poster import HPBPoster
                poster = HPBPoster(hpb_config['username'], hpb_config['password'])
                try:
                    poster.login()
                    success = poster.post_style(salon_id, stylist, coupon, str(filepath))
                    if success:
                        print("✅ HPB への投稿が完了しました")
                        return jsonify({
                            'success': True,
                            'message': '✅ HPB に投稿されました！',
                            'filename': filename,
                            'analysis': analysis,
                            'hpb_status': 'posted'
                        })
                    else:
                        print("⚠️ HPB への投稿に失敗しました")
                        return jsonify({
                            'success': True,
                            'message': '⚠️ 画像は保存されましたが、HPB への投稿に失敗しました',
                            'filename': filename,
                            'analysis': analysis,
                            'hpb_status': 'failed'
                        })
                finally:
                    poster.close()
            else:
                # hpb_config.json がない場合は、テスト扱い
                print("ℹ️ hpb_config.json がないため、テストモードです")
                return jsonify({
                    'success': True,
                    'message': '✅ テストモード: 画像は保存されました（HPB には投稿されていません）',
                    'filename': filename,
                    'analysis': analysis,
                    'hpb_status': 'test_mode'
                })

        except Exception as hpb_error:
            print(f"⚠️ HPB 投稿エラー: {hpb_error}")
            # エラーでも画像は保存されている
            return jsonify({
                'success': True,
                'message': f'画像は保存されました。HPB 投稿エラー: {str(hpb_error)}',
                'filename': filename,
                'analysis': analysis,
                'hpb_status': 'error'
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """ヘルスチェック"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
