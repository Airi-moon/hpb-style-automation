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

# ⚠️ 起動時には接続せず、最初のリクエスト時に遅延初期化する
# （認証情報の問題でアプリ全体が起動失敗 → Render が全URLに404を返す事故を防ぐ）
_spreadsheet = None
_sheets_init_error = None

def get_spreadsheet():
    """Google Sheets 接続を遅延初期化して返す。失敗時は None（エラーは _sheets_init_error に保存）"""
    global _spreadsheet, _sheets_init_error
    if _spreadsheet is not None:
        return _spreadsheet
    try:
        google_creds_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
        if google_creds_json:
            credentials = Credentials.from_service_account_info(
                json.loads(google_creds_json),
                scopes=SCOPES
            )
        else:
            # ローカル開発用
            service_account_file = os.path.expanduser('~/Downloads/hpb-style-automation-0311880cf963.json')
            if not os.path.exists(service_account_file):
                raise FileNotFoundError(
                    'GOOGLE_SERVICE_ACCOUNT_JSON 環境変数が未設定で、'
                    f'ローカルの認証ファイルも見つかりません: {service_account_file}'
                )
            credentials = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)

        client = gspread.authorize(credentials)
        _spreadsheet = client.open_by_key(SPREADSHEET_ID)
        _sheets_init_error = None
        print("✅ Google Sheets に接続しました")
        return _spreadsheet
    except Exception as e:
        _sheets_init_error = f"{type(e).__name__}: {e}"
        print(f"❌ Google Sheets 接続エラー: {_sheets_init_error}")
        return None

# キャッシュ（メモリ内、TTL 付き）
import time as _time
CACHE_TTL = 600  # 10 分で自動再読み込み
cache = {
    'shops': None,
    'stylists': None,
    'coupons': None,
    'loaded_at': 0,
}

def clear_cache():
    cache['shops'] = None
    cache['stylists'] = None
    cache['coupons'] = None
    cache['loaded_at'] = 0

def load_data():
    """Google Sheets からデータを読み込み（TTL 付きキャッシュ使用）"""
    global cache

    # TTL 切れなら再読み込み
    if cache['loaded_at'] and (_time.time() - cache['loaded_at'] > CACHE_TTL):
        clear_cache()

    spreadsheet = get_spreadsheet()
    if spreadsheet is None:
        return cache

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

        cache['loaded_at'] = _time.time()
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
    shops_dict = data.get('shops') or {}
    if not shops_dict:
        detail = _sheets_init_error or '原因不明（Render のログを確認してください）'
        return jsonify({'error': f'Google Sheets 接続エラー: {detail}'}), 503
    shops = [{'id': k, 'name': v} for k, v in shops_dict.items()]
    return jsonify(shops)

@app.route('/api/stylists/<salon_id>', methods=['GET'])
def get_stylists(salon_id):
    """店舗ごとのスタイリスト一覧"""
    data = load_data()
    stylists = (data.get('stylists') or {}).get(salon_id, [])
    return jsonify(stylists)

@app.route('/api/coupons/<salon_id>', methods=['GET'])
def get_coupons(salon_id):
    """店舗ごとのクーポン一覧"""
    data = load_data()
    coupons = (data.get('coupons') or {}).get(salon_id, [])
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

# ============================================================
# 手動投稿補助機能（メタデータエクスポート）
# ============================================================

# 分析結果 → 日本語ラベル変換テーブル
JP_LABELS = {
    'hair_volume':    {'low': '少ない', 'medium': '普通', 'high': '多い'},
    'hair_texture':   {'straight': '柔かい', 'wavy': '普通', 'coarse': '硬い'},
    'hair_thickness': {'thin': '細い', 'medium': '普通', 'thick': '太い'},
    'hair_curl':      {'none': 'なし', 'weak': '弱い', 'strong': '強い'},
    'face_shape':     {'oval': '卵型', 'round': '丸型', 'square': 'ベース型',
                       'long': '面長', 'triangle': '逆三角'},
    'estimated_age':  {'10s': '10代', '20s': '20代', '30s': '30代',
                       '40s': '40代', '50s': '50代以上'},
    'hair_angle':     {'front': 'フロント', 'side': 'サイド', 'back': 'バック'},
    'color_tone':     {'black': '黒髪', 'brown': 'ブラウン', 'beige': 'ベージュ',
                       'ash': 'アッシュ', 'blonde': 'ハイトーン'},
}

def jp(key, value):
    """分析結果の値を日本語ラベルに変換（不明な値はそのまま返す）"""
    return JP_LABELS.get(key, {}).get(value, value or '不明')

def estimate_length(analysis):
    """画像の縦横比からおおまかな髪の長さを推測"""
    w = analysis.get('image_width') or 1
    h = analysis.get('image_height') or 1
    ratio = h / w
    if ratio >= 1.4:
        return 'ロング'
    elif ratio >= 1.15:
        return 'ミディアム'
    return 'ショート'

def generate_style_name(analysis, length=None):
    """
    分析結果からスタイル名を自動生成
    例：「ナチュラルストレート × ショート（20代向け）」
    """
    length = length or estimate_length(analysis)

    texture_word = {
        'straight': 'ナチュラルストレート',
        'wavy': 'ゆるふわウェーブ',
        'coarse': 'メリハリスタイル',
    }.get(analysis.get('hair_texture'), 'おしゃれスタイル')

    curl = analysis.get('hair_curl')
    if curl == 'strong':
        texture_word = '華やかカール'
    elif curl == 'weak':
        texture_word = 'ゆるめカール'

    tone_word = {
        'brown': '透明感ブラウン',
        'ash': 'くすみアッシュ',
        'beige': 'ミルクベージュ',
        'blonde': 'ハイトーンカラー',
        'black': '艶感黒髪',
    }.get(analysis.get('color_tone'), '')

    age = jp('estimated_age', analysis.get('estimated_age'))

    parts = [texture_word, length]
    name = ' × '.join(parts)
    if tone_word:
        name = f"{tone_word} {name}"
    return f"{name}（{age}向け）"

def build_export(salon_id, salon_name, stylist, coupon, analysis):
    """HPB 入力用のエクスポートデータ（JSON / CSV / プレーンテキスト）を組み立て"""
    length = estimate_length(analysis)
    style_name = generate_style_name(analysis, length)

    fields = {
        '店舗': salon_name,
        'スタイリスト名': stylist,
        'スタイル登録形式': '画像',
        'スタイル名': style_name,
        'カテゴリ': 'レディース',
        '長さ': length,
        'クーポン': coupon,
        '髪量': jp('hair_volume', analysis.get('hair_volume')),
        '髪質': jp('hair_texture', analysis.get('hair_texture')),
        '太さ': jp('hair_thickness', analysis.get('hair_thickness')),
        'クセ': jp('hair_curl', analysis.get('hair_curl')),
        '顔型': jp('face_shape', analysis.get('face_shape')),
        '推定年代': jp('estimated_age', analysis.get('estimated_age')),
        'カラートーン': jp('color_tone', analysis.get('color_tone')),
        '撮影アングル': jp('hair_angle', analysis.get('hair_angle')),
    }

    # CSV（ヘッダー行 + 値行）
    def csv_escape(v):
        v = str(v)
        if any(c in v for c in [',', '"', '\n']):
            v = '"' + v.replace('"', '""') + '"'
        return v
    csv_text = (
        ','.join(csv_escape(k) for k in fields.keys()) + '\n' +
        ','.join(csv_escape(v) for v in fields.values())
    )

    # コピペしやすいプレーンテキスト
    plain_text = '\n'.join(f"{k}: {v}" for k, v in fields.items())

    return {
        'salon_id': salon_id,
        'salon_name': salon_name,
        'stylist': stylist,
        'coupon': coupon,
        'style_name': style_name,
        'analysis': analysis,
        'fields': fields,
        'export_formats': {
            'json': fields,
            'csv': csv_text,
            'text': plain_text,
        },
    }

@app.route('/api/metadata-export', methods=['POST'])
def export_metadata():
    """
    画像分析 + メタデータを HPB 手動投稿用にエクスポート

    リクエスト（multipart/form-data）:
    - salonId: 店舗ID
    - stylist: スタイリスト名
    - coupon: クーポン名
    - image: 画像ファイル
    """
    try:
        salon_id = request.form.get('salonId')
        stylist = request.form.get('stylist')
        coupon = request.form.get('coupon')
        image_file = request.files.get('image')

        if not all([salon_id, stylist, coupon]) or image_file is None:
            return jsonify({'error': 'すべてのフィールドと画像が必須です'}), 400

        data = load_data()
        salon_name = data['shops'].get(salon_id, salon_id)

        # 画像を保存して分析
        filename = f"{salon_id}_{stylist}_{image_file.filename}"
        filepath = UPLOAD_FOLDER / filename
        image_file.save(filepath)

        from image_analyzer import analyze_image
        analysis = analyze_image(str(filepath))
        if 'error' in analysis:
            return jsonify({'error': analysis['error']}), 500

        export_data = build_export(salon_id, salon_name, stylist, coupon, analysis)
        export_data['filename'] = filename
        return jsonify(export_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh', methods=['POST'])
def refresh_cache():
    """Sheets 更新後にキャッシュを即時クリア（hpb_sync.py 実行後に叩く）"""
    clear_cache()
    data = load_data()
    return jsonify({
        'success': True,
        'shops': len(data['shops'] or {}),
        'stylists': sum(len(v) for v in (data['stylists'] or {}).values()),
        'coupons': sum(len(v) for v in (data['coupons'] or {}).values()),
    })

@app.route('/api/health', methods=['GET'])
def health():
    """ヘルスチェック（Sheets 接続状態も返す）"""
    sheets_ok = get_spreadsheet() is not None
    return jsonify({
        'status': 'ok',
        'sheets_connected': sheets_ok,
        'sheets_error': _sheets_init_error,
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
