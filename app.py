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
    'salonboard': None,
    'loaded_at': 0,
}

def clear_cache():
    cache['shops'] = None
    cache['stylists'] = None
    cache['coupons'] = None
    cache['salonboard'] = None
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

        if not cache.get('salonboard'):
            try:
                sb_data = spreadsheet.worksheet('SalonBoard').get_all_values()[1:]
                cache['salonboard'] = {
                    row[0].strip(): {
                        'loginId': row[2].strip() if len(row) > 2 else '',
                        'password': row[3].strip() if len(row) > 3 else '',
                        'memo': row[4].strip() if len(row) > 4 else '',
                    }
                    for row in sb_data if row and row[0].strip()
                }
                print(f"  ✓ SalonBoard アカウント情報を読み込み（{len(cache['salonboard'])} 店舗）")
            except Exception:
                cache['salonboard'] = {}
                print("  ℹ️ SalonBoard タブなし（setup_salonboard_sheet.py で作成できます）")

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

# ============================================================
# AI 画像分析（Claude Vision / ANTHROPIC_API_KEY があれば使用）
# ============================================================
import base64
import mimetypes

AI_ANALYSIS_PROMPT = """あなたは美容室のスタイル写真を分析する専門家です。
この髪型写真を見て、以下のJSONだけを出力してください（前置きやコードブロック記号は一切不要）:
{
  "hair_volume": "low|medium|high",
  "hair_texture": "straight|wavy|coarse",
  "hair_thickness": "thin|medium|thick",
  "hair_curl": "none|weak|strong",
  "estimated_age": "10s|20s|30s|40s|50s",
  "face_shape": "oval|round|square|long|triangle",
  "color_tone": "black|brown|beige|ash|blonde",
  "length": "very_short|short|bob|medium|semi_long|long",
  "hair_angle": "front|side|back",
  "style_name": "ホットペッパービューティーに載せる魅力的なスタイル名（25文字以内、日本語）",
  "style_description": "HPBのスタイル紹介文（80〜120文字、日本語。骨格や髪質への似合わせ、お手入れのしやすさなどに触れ、お客様に響く文章）"
}"""


def analyze_with_ai(filepath: str) -> dict | None:
    """Claude Vision で画像を分析。APIキー未設定や失敗時は None を返す"""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None
    try:
        import requests as _requests
        media_type = mimetypes.guess_type(str(filepath))[0] or 'image/jpeg'
        with open(filepath, 'rb') as f:
            image_b64 = base64.standard_b64encode(f.read()).decode()

        res = _requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': 'claude-sonnet-4-6',
                'max_tokens': 1000,
                'messages': [{
                    'role': 'user',
                    'content': [
                        {'type': 'image',
                         'source': {'type': 'base64', 'media_type': media_type, 'data': image_b64}},
                        {'type': 'text', 'text': AI_ANALYSIS_PROMPT},
                    ],
                }],
            },
            timeout=60,
        )
        res.raise_for_status()
        text = ''.join(b.get('text', '') for b in res.json().get('content', []))
        text = text.replace('```json', '').replace('```', '').strip()
        result = json.loads(text)
        result['ai_generated'] = True
        print("🤖 AI 分析成功")
        return result
    except Exception as e:
        print(f"⚠️ AI 分析失敗（簡易分析にフォールバック）: {e}")
        return None


def generate_style_description(analysis, length_jp):
    """ヒューリスティックな紹介文生成（AI未使用時のフォールバック）"""
    texture = jp('hair_texture', analysis.get('hair_texture'))
    tone = jp('color_tone', analysis.get('color_tone'))
    age = jp('estimated_age', analysis.get('estimated_age'))
    return (f"骨格と髪質に合わせた似合わせカットで仕上げた{length_jp}スタイル。"
            f"{tone}の色味で透明感をプラスし、{texture}めの髪質を活かして"
            f"朝のお手入れも簡単に。{age}のお客様に人気のデザインです。")


JP_LABELS['length'] = {
    'very_short': 'ベリーショート', 'short': 'ショート', 'bob': 'ボブ',
    'medium': 'ミディアム', 'semi_long': 'セミロング', 'long': 'ロング',
}


def run_analysis(filepath: str) -> dict:
    """AI 分析（可能なら）→ 簡易分析フォールバックの統合分析"""
    ai_result = analyze_with_ai(filepath)
    if ai_result:
        return ai_result
    from image_analyzer import analyze_image
    result = analyze_image(str(filepath))
    result['ai_generated'] = False
    return result


def safe_filename(name: str) -> str:
    """パストラバーサル防止"""
    return os.path.basename(name or '')


@app.route('/api/preview', methods=['POST'])
def preview_style():
    """
    画像を分析して、HPB 掲載イメージのプレビューデータを返す

    リクエスト（multipart/form-data）: salonId, stylist, coupon, image
    """
    try:
        salon_id = request.form.get('salonId')
        stylist = request.form.get('stylist')
        coupon = request.form.get('coupon')
        image_file = request.files.get('image')

        if not all([salon_id, stylist, coupon]) or image_file is None:
            return jsonify({'error': 'すべてのフィールドと画像が必須です'}), 400

        data = load_data()
        salon_name = (data.get('shops') or {}).get(salon_id, salon_id)

        filename = f"{salon_id}_{int(_time.time())}_{safe_filename(image_file.filename)}"
        filepath = UPLOAD_FOLDER / filename
        image_file.save(filepath)

        analysis = run_analysis(str(filepath))
        if 'error' in analysis:
            return jsonify({'error': analysis['error']}), 500

        # 長さ: AI が返せばそれを、なければ縦横比から推測
        length_key = analysis.get('length')
        length_jp = jp('length', length_key) if length_key else estimate_length(analysis)

        style_name = analysis.get('style_name') or generate_style_name(analysis, length_jp)
        description = analysis.get('style_description') or generate_style_description(analysis, length_jp)

        sb_all = data.get('salonboard') or {}
        sb_info = sb_all.get(salon_id) or sb_all.get('*') or {}
        return jsonify({
            'filename': filename,
            'salon_id': salon_id,
            'salon_name': salon_name,
            'stylist': stylist,
            'coupon': coupon,
            'salonboard_login_id': sb_info.get('loginId', ''),
            'ai_generated': analysis.get('ai_generated', False),
            'preview': {
                'スタイル名': style_name,
                'スタイル説明': description,
                'カテゴリ': 'レディース',
                '長さ': length_jp,
                '髪量': jp('hair_volume', analysis.get('hair_volume')),
                '髪質': jp('hair_texture', analysis.get('hair_texture')),
                '太さ': jp('hair_thickness', analysis.get('hair_thickness')),
                'クセ': jp('hair_curl', analysis.get('hair_curl')),
                '顔型': jp('face_shape', analysis.get('face_shape')),
                '推定年代': jp('estimated_age', analysis.get('estimated_age')),
            },
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/submit', methods=['POST'])
def submit_style():
    """
    確認済みの内容でスタイルを投稿する

    リクエスト（JSON）: salonId, stylist, coupon, filename, fields（編集済みプレビュー内容）
    """
    try:
        body = request.get_json(force=True)
        salon_id = body.get('salonId')
        stylist = body.get('stylist')
        coupon = body.get('coupon')
        filename = safe_filename(body.get('filename'))
        fields = body.get('fields') or {}

        if not all([salon_id, stylist, coupon, filename]):
            return jsonify({'error': '必須項目が不足しています'}), 400

        filepath = UPLOAD_FOLDER / filename
        if not filepath.exists():
            return jsonify({'error': '画像が見つかりません。もう一度プレビューからやり直してください'}), 400

        # 確定メタデータを画像と並べて保存（自動投稿・記録用）
        meta = {
            'salon_id': salon_id, 'stylist': stylist, 'coupon': coupon,
            'fields': fields, 'submitted_at': _time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        meta_path = filepath.with_suffix(filepath.suffix + '.meta.json')
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')

        # サロンボード自動投稿（hpb_config.json がある場合のみ）
        hpb_config_file = BASE_DIR / 'hpb_config.json'
        if hpb_config_file.exists():
            try:
                with open(hpb_config_file) as f:
                    hpb_config = json.load(f)
                from hpb_poster import HPBPoster
                poster = HPBPoster(hpb_config['username'], hpb_config['password'])
                try:
                    poster.login()
                    success = poster.post_style(salon_id, stylist, coupon, str(filepath))
                finally:
                    poster.close()
                if success:
                    return jsonify({'success': True, 'hpb_status': 'posted',
                                    'message': '✅ サロンボードに投稿しました！'})
                return jsonify({'success': True, 'hpb_status': 'failed',
                                'message': '⚠️ 内容は保存しましたが、サロンボードへの自動投稿に失敗しました。下のコピー機能で手動投稿してください'})
            except Exception as e:
                print(f"⚠️ 自動投稿エラー: {e}")
                return jsonify({'success': True, 'hpb_status': 'error',
                                'message': f'⚠️ 内容は保存しました。自動投稿エラー: {e}。下のコピー機能で手動投稿してください'})

        # 自動投稿未設定 → 手動投稿モード
        return jsonify({'success': True, 'hpb_status': 'manual',
                        'message': '✅ 内容を確定しました。下のコピー機能を使ってサロンボードに貼り付けてください'})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/pending', methods=['GET'])
def get_pending():
    """
    確定済み（submit 済み）の最新投稿データを返す。
    サロンボード上の Tampermonkey スクリプトが自動入力に使用する。
    """
    try:
        metas = sorted(UPLOAD_FOLDER.glob('*.meta.json'),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if not metas:
            return jsonify({'error': '確定済みの投稿がありません。先にアプリで「この内容で投稿する」を実行してください'}), 404

        meta_path = metas[0]
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        image_filename = meta_path.name.replace('.meta.json', '')
        meta['image_url'] = f"/uploads/{image_filename}"
        meta['image_filename'] = image_filename

        # 店舗に紐づくサロンボードアカウント情報を同梱
        app_token = os.environ.get('APP_TOKEN')
        token_ok = bool(app_token) and request.args.get('token') == app_token
        if app_token and not token_ok:
            return jsonify({'error': 'token が違います。Tampermonkey スクリプトの APP_TOKEN を確認してください'}), 401

        data = load_data()
        sb_all = data.get('salonboard') or {}
        sb_info = dict(sb_all.get(meta.get('salon_id')) or sb_all.get('*') or {})
        if not token_ok:
            # APP_TOKEN 未設定時はパスワードを渡さない（安全側）
            sb_info.pop('password', None)
            sb_info['note'] = 'パスワード自動入力を使うには Render に APP_TOKEN を設定してください'
        meta['salonboard'] = sb_info
        return jsonify(meta)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
