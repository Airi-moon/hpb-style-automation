#!/usr/bin/env python3
"""
Selenium を使って HPB Salon Board に自動投稿
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
from pathlib import Path

class HPBPoster:
    def __init__(self, hpb_username: str, hpb_password: str):
        """
        HPB Poster を初期化

        Args:
            hpb_username: HPB ログイン名
            hpb_password: HPB パスワード
        """
        self.username = hpb_username
        self.password = hpb_password
        self.driver = None

    def login(self):
        """HPB にログイン"""
        print("🔐 HPB にログイン中...")

        # Chrome ブラウザを起動
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless')  # ヘッドレスモード（デバッグ時は False）
        self.driver = webdriver.Chrome(options=options)

        # Salon Board ログインページ
        self.driver.get('https://salon.hotpepper.jp/members/')
        time.sleep(2)

        # ログイン情報を入力
        try:
            # ログイン ID
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, 'login_id'))
            )
            username_field.send_keys(self.username)

            # パスワード
            password_field = self.driver.find_element(By.ID, 'password')
            password_field.send_keys(self.password)

            # ログインボタン
            login_button = self.driver.find_element(By.ID, 'submit')
            login_button.click()

            print("✅ ログイン成功")
            time.sleep(3)

        except Exception as e:
            print(f"❌ ログイン失敗: {e}")
            self.close()
            raise

    def post_style(self, salon_id: str, stylist: str, coupon: str, image_path: str) -> bool:
        """
        スタイル画像を投稿

        Args:
            salon_id: HPB 店舗 ID
            stylist: スタイリスト名
            coupon: クーポン名
            image_path: 画像ファイルパス

        Returns:
            成功したかどうか
        """
        image_path = Path(image_path)
        if not image_path.exists():
            print(f"❌ 画像ファイルが見つかりません: {image_path}")
            return False

        print(f"\n📸 投稿中: {salon_id} / {stylist} / {coupon}")

        try:
            # スタイル投稿ページへ移動
            style_url = f'https://salon.hotpepper.jp/members/styles/input/{salon_id}/'
            self.driver.get(style_url)
            time.sleep(2)

            # 画像をアップロード
            image_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, 'style_image'))
            )
            image_input.send_keys(str(image_path.absolute()))
            print("  ✓ 画像アップロード完了")
            time.sleep(2)

            # スタイリスト選択
            stylist_select = Select(self.driver.find_element(By.NAME, 'staff_id'))
            stylist_select.select_by_visible_text(stylist)
            print(f"  ✓ スタイリスト選択: {stylist}")
            time.sleep(1)

            # クーポン選択
            coupon_select = Select(self.driver.find_element(By.NAME, 'coupon_id'))
            coupon_select.select_by_visible_text(coupon)
            print(f"  ✓ クーポン選択: {coupon}")
            time.sleep(1)

            # 投稿ボタン
            submit_button = self.driver.find_element(By.ID, 'submit')
            submit_button.click()
            print("  ✓ 投稿完了")
            time.sleep(2)

            return True

        except Exception as e:
            print(f"  ❌ 投稿失敗: {e}")
            return False

    def close(self):
        """ブラウザを閉じる"""
        if self.driver:
            self.driver.quit()
            print("\n👋 ブラウザを閉じました")

if __name__ == '__main__':
    import sys

    # 設定ファイルから ログイン情報を読み込み
    config_file = Path(__file__).parent / 'hpb_config.json'
    if not config_file.exists():
        print("❌ hpb_config.json が見つかりません")
        print("以下の内容で hpb_config.json を作成してください:")
        print(json.dumps({
            "username": "your_hpb_username",
            "password": "your_hpb_password"
        }, indent=2))
        sys.exit(1)

    with open(config_file) as f:
        config = json.load(f)

    # 投稿テスト
    poster = HPBPoster(config['username'], config['password'])
    try:
        poster.login()
        # poster.post_style('H000394957', '江上 京花', '【全員】似合わせカット+Aujua2stepトリートメント｜銀座', '/path/to/image.jpg')
    finally:
        poster.close()
