#!/usr/bin/env python3
"""
画像分析スクリプト
llama2 を使った簡易版（自動生成による推測）
実装では、HPB からの実データで置き換え可能
"""

import json
from pathlib import Path
from PIL import Image

def analyze_image(image_path: str) -> dict:
    """
    画像を簡易分析
    実装版では Ollama/Claude Vision で動的分析、または HPB スクレイピングで取得
    デモでは、ファイル名やメタデータから推測

    Args:
        image_path: 画像ファイルパス

    Returns:
        分析結果
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"画像ファイルが見つかりません: {image_path}")

    try:
        # 画像メタデータを取得
        img = Image.open(image_path)
        width, height = img.size
        aspect_ratio = width / height if height > 0 else 1.0

        # 簡易的な推測（本実装では Ollama/Vision API を使用）
        analysis = {
            'hair_angle': 'front' if aspect_ratio > 0.8 else 'side',
            'hair_volume': 'medium',
            'hair_texture': 'straight',
            'hair_thickness': 'medium',
            'hair_curl': 'none',
            'estimated_age': '20s',
            'face_shape': 'oval',
            'color_tone': 'brown',
            'image_width': width,
            'image_height': height,
            'image_size_bytes': image_path.stat().st_size
        }
        return analysis

    except Exception as e:
        return {'error': f'分析エラー: {e}'}

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("使用方法: python3 image_analyzer.py <画像ファイルパス>")
        sys.exit(1)

    image_path = sys.argv[1]
    print(f"📸 画像を分析中: {image_path}")

    result = analyze_image(image_path)
    print("\n📊 分析結果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
