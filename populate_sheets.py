#!/usr/bin/env python3
"""
Google Sheets にサロンデータを入力するスクリプト
salons_data.json から Shops / Stylists / Coupons シートに自動入力
"""

import gspread
from google.oauth2.service_account import Credentials
import json
import os

# Google Sheets API の認証
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = os.path.expanduser('~/Downloads/hpb-style-automation-0311880cf963.json')
SPREADSHEET_ID = '1JwXkoU3-GrfuGmATDwtX6Tq5iRsQGM-HXyIjcEcQZZY'
SALONS_DATA_FILE = os.path.dirname(__file__) + '/salons_data.json'

def get_or_create_worksheet(spreadsheet, title):
    """シートが存在しなければ作成、存在すればそれを返す"""
    try:
        return spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        print(f"  📝 シート '{title}' を作成中...")
        try:
            return spreadsheet.add_worksheet(title=title, rows=1000, cols=5)
        except gspread.exceptions.APIError as e:
            if "already exists" in str(e):
                return spreadsheet.worksheet(title)
            raise

def main():
    print("🔐 Google Sheets に認証中...")
    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    client = gspread.authorize(credentials)
    print("✅ 認証完了")

    print(f"📂 Google Sheets を開く: {SPREADSHEET_ID}")
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    print("✅ スプレッドシートを開きました")

    print(f"📝 salons_data.json を読み込み中: {SALONS_DATA_FILE}")
    with open(SALONS_DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"✅ {len(data['salons'])} 個の店舗データを読み込みました")

    # Shops シートに入力
    print("\n📋 Shops シートに入力中...")
    shops_sheet = get_or_create_worksheet(spreadsheet, 'Shops')
    shops_sheet.clear()
    shops_sheet.append_row(['salonId', 'salonName'])
    for salon in data['salons']:
        shops_sheet.append_row([salon['salonId'], salon['salonName']])
        print(f"  ✓ {salon['salonName']}")
    print(f"✅ Shops シート完了（{len(data['salons'])} 店舗）")

    # Stylists シートに入力
    print("\n👤 Stylists シートに入力中...")
    stylists_sheet = get_or_create_worksheet(spreadsheet, 'Stylists')
    stylists_sheet.clear()
    stylists_rows = [['salonId', 'stylistName']]
    total_stylists = 0
    for salon in data['salons']:
        for stylist in salon['stylists']:
            stylists_rows.append([salon['salonId'], stylist])
            total_stylists += 1
    stylists_sheet.append_rows(stylists_rows)
    print(f"✅ Stylists シート完了（全 {total_stylists} 名）")

    # Coupons シートに入力
    print("\n🎟️ Coupons シートに入力中...")
    coupons_sheet = get_or_create_worksheet(spreadsheet, 'Coupons')
    coupons_sheet.clear()
    coupons_rows = [['salonId', 'couponName']]
    total_coupons = 0
    for salon in data['salons']:
        for coupon in salon['coupons']:
            coupons_rows.append([salon['salonId'], coupon])
            total_coupons += 1
    coupons_sheet.append_rows(coupons_rows)
    print(f"✅ Coupons シート完了（全 {total_coupons} 件）")

    print("\n" + "="*50)
    print("🎉 全データ入力完了！")
    print("="*50)
    print(f"📊 Google Sheets: {SPREADSHEET_ID}")
    print(f"  - 店舗: {len(data['salons'])}")
    print(f"  - スタイリスト: {total_stylists}")
    print(f"  - クーポン: {total_coupons}")

if __name__ == '__main__':
    main()
