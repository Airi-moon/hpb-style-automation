#!/usr/bin/env python3
"""
HPB（ホットペッパービューティー公開ページ）からクーポン情報をスクレイピング
Google Sheets に自動反映（毎日朝に実行）
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import gspread
from google.oauth2.service_account import Credentials
import json
import time
import os
from pathlib import Path

class HPBPublicCouponScraper:
    def __init__(self, gsheet_id: str, service_account_file: str):
        """
        HPB 公開ページからのスクレイパーを初期化

        Args:
            gsheet_id: Google Sheets ID
            service_account_file: Google Service Account JSON ファイルパス
        """
        self.gsheet_id = gsheet_id

        # Google Sheets に接続
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        credentials = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
        self.gspread_client = gspread.authorize(credentials)
        self.spreadsheet = self.gspread_client.open_by_key(gsheet_id)

        self.driver = None

    def init_driver(self):
        """Chrome ドライバーを初期化"""
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless')  # デバッグ時は False
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        self.driver = webdriver.Chrome(options=options)

    def scrape_salon_coupons(self, salon_id: str, salon_name: str) -> dict:
        """
        HPB 公開ページから店舗のクーポン情報をスクレイピング

        Args:
            salon_id: HPB 店舗 ID（例: H000394957）
            salon_name: 店舗名

        Returns:
            クーポンデータ
        """
        print(f"\n📍 {salon_name} ({salon_id}) のクーポンを取得中...")

        data = {
            'salon_id': salon_id,
            'salon_name': salon_name,
            'coupons': []
        }

        try:
            # HPB 公開ページの店舗クーポン一覧
            coupon_url = f'https://beauty.hotpepper.jp/strJ{salon_id[1:]}/?tab=coupon'
            self.driver.get(coupon_url)
            time.sleep(2)

            # クーポンを取得（複数のセレクタを試す）
            try:
                # クーポンタイトルを抽出
                coupon_elements = self.driver.find_elements(By.CLASS_NAME, 'txt_coupon_title')
                for elem in coupon_elements:
                    coupon_text = elem.text.strip()
                    if coupon_text and coupon_text not in data['coupons']:
                        data['coupons'].append(coupon_text)
            except:
                pass

            # 別のセレクタを試す
            try:
                coupon_items = self.driver.find_elements(By.CSS_SELECTOR, '[class*="coupon"]')
                for item in coupon_items:
                    coupon_text = item.text.strip()
                    if coupon_text and len(coupon_text) > 5 and coupon_text not in data['coupons']:
                        # スタイル関連のテキストをフィルタリング
                        if any(keyword in coupon_text for keyword in ['カット', 'カラー', 'パーマ', 'トリートメント', '縮毛', '骨格']):
                            data['coupons'].append(coupon_text)
            except:
                pass

            print(f"  ✓ クーポン: {len(data['coupons'])} 件取得")
            for coupon in data['coupons'][:3]:  # 最初の3つだけ表示
                print(f"    - {coupon[:50]}...")

            return data

        except Exception as e:
            print(f"  ⚠️  クーポン取得エラー: {e}")
            return data

    def update_google_sheets(self, all_coupons: list):
        """
        Google Sheets にスクレイピング結果を反映

        Args:
            all_coupons: 全店舗のクーポンデータリスト
        """
        print("\n📊 Google Sheets を更新中...")

        try:
            # Coupons シートを更新
            coupons_sheet = self.spreadsheet.worksheet('Coupons')
            coupons_sheet.clear()
            coupons_rows = [['salonId', 'couponName']]

            total_coupons = 0
            for salon_data in all_coupons:
                for coupon in salon_data.get('coupons', []):
                    coupons_rows.append([salon_data['salon_id'], coupon])
                    total_coupons += 1

            if total_coupons > 0:
                coupons_sheet.append_rows(coupons_rows)
                print(f"  ✓ Coupons シート更新完了（{total_coupons} 件）")
            else:
                print(f"  ⚠️  クーポンデータが取得できませんでした")

            print("✅ Google Sheets 更新完了")

        except Exception as e:
            print(f"❌ Google Sheets 更新失敗: {e}")
            raise

    def run(self):
        """
        全店舗のクーポン情報を取得＆更新
        """
        try:
            print("🚀 HPB からクーポン情報を取得開始...")
            self.init_driver()

            # Google Sheets から店舗 ID を取得
            shops_sheet = self.spreadsheet.worksheet('Shops')
            shops_data = shops_sheet.get_all_values()[1:]  # ヘッダーをスキップ

            all_coupons = []
            for row in shops_data:
                salon_id = row[0]
                salon_name = row[1] if len(row) > 1 else salon_id

                salon_data = self.scrape_salon_coupons(salon_id, salon_name)
                all_coupons.append(salon_data)
                time.sleep(1)  # サーバー負荷対策

            # Google Sheets に反映
            self.update_google_sheets(all_coupons)

            print("\n" + "="*50)
            print("🎉 クーポン情報の自動更新完了！")
            print("="*50)

        finally:
            self.close()

    def close(self):
        """ブラウザを閉じる"""
        if self.driver:
            self.driver.quit()
            print("\n👋 ブラウザを閉じました")

if __name__ == '__main__':
    # 実行
    scraper = HPBPublicCouponScraper(
        gsheet_id='1JwXkoU3-GrfuGmATDwtX6Tq5iRsQGM-HXyIjcEcQZZY',
        service_account_file=os.path.expanduser('~/Downloads/hpb-style-automation-0311880cf963.json')
    )
    scraper.run()
