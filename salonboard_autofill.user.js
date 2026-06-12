// ==UserScript==
// @name         HPB スタイル自動入力（sand）
// @namespace    hpb-style-automation
// @version      1.0
// @description  アプリで確定したスタイル情報をサロンボードのスタイル登録フォームに自動入力する
// @match        https://salon.hotpepper.jp/*
// @grant        GM_xmlhttpRequest
// @connect      hpb-style-automation.onrender.com
// @run-at       document-idle
// ==/UserScript==

(function () {
    'use strict';

    // ============ 設定 ============
    const API_BASE = 'https://hpb-style-automation.onrender.com';

    // アプリの項目名 → サロンボード画面のラベル文字列（部分一致）の対応表
    // ※ 実際の画面のラベルと違っていたら、ここの右側を書き換えるだけで直せます
    const FIELD_LABELS = {
        'スタイル名':   ['スタイル名', 'スタイルタイトル'],
        'スタイル説明': ['スタイルコメント', 'スタイル説明', 'コメント', '説明文'],
        'カテゴリ':     ['カテゴリ', '性別'],
        '長さ':         ['長さ', 'レングス'],
        '髪量':         ['髪量', '髪の量'],
        '髪質':         ['髪質'],
        '太さ':         ['太さ', '髪の太さ'],
        'クセ':         ['クセ', 'くせ'],
        '顔型':         ['顔型', '顔形'],
        'スタイリスト名': ['スタイリスト', '担当'],
        'クーポン':     ['クーポン'],
    };

    // ============ ユーティリティ ============
    function fetchJson(url) {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'GET', url,
                onload: r => {
                    try { resolve(JSON.parse(r.responseText)); }
                    catch (e) { reject(new Error('JSONパース失敗: ' + r.responseText.slice(0, 100))); }
                },
                onerror: () => reject(new Error('通信エラー')),
            });
        });
    }

    function fetchBlob(url) {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'GET', url, responseType: 'blob',
                onload: r => resolve(r.response),
                onerror: () => reject(new Error('画像取得エラー')),
            });
        });
    }

    // ラベル文字列を含む要素（th, label, dt 等）を探し、対応する入力欄を返す
    function findControlByLabel(labelCandidates) {
        const labelEls = [...document.querySelectorAll('th, label, dt, legend, span, p, div')]
            .filter(el => {
                const t = (el.textContent || '').trim();
                return t.length > 0 && t.length < 30 &&
                    labelCandidates.some(c => t.includes(c));
            });

        for (const labelEl of labelEls) {
            // 1) label[for]
            if (labelEl.tagName === 'LABEL' && labelEl.htmlFor) {
                const c = document.getElementById(labelEl.htmlFor);
                if (c) return c;
            }
            // 2) 同じ行（tr）/ 同じ dl / 親ブロック内の入力欄
            const containers = [labelEl.closest('tr'), labelEl.closest('dl'),
                                labelEl.parentElement, labelEl.parentElement?.parentElement];
            for (const box of containers) {
                if (!box) continue;
                const c = box.querySelector('input[type=text], textarea, select, input[type=radio], input[type=checkbox]');
                if (c && !labelEl.contains(c) || c) return c;
            }
        }
        return null;
    }

    // 入力欄の種類に応じて値をセット
    function setControlValue(control, value) {
        if (!control || value == null || value === '') return false;
        const fire = el => ['input', 'change'].forEach(t =>
            el.dispatchEvent(new Event(t, { bubbles: true })));

        if (control.tagName === 'SELECT') {
            const opt = [...control.options].find(o =>
                o.textContent.trim() === value || o.textContent.includes(value) || o.value === value);
            if (!opt) return false;
            control.value = opt.value; fire(control);
            return true;
        }
        if (control.type === 'radio' || control.type === 'checkbox') {
            // 同じ name のグループから、ラベル文字列が一致するものを選ぶ
            const group = document.querySelectorAll(`input[name="${control.name}"]`);
            for (const radio of group) {
                const lbl = radio.closest('label') ||
                    (radio.id && document.querySelector(`label[for="${radio.id}"]`)) ||
                    radio.parentElement;
                const text = (lbl?.textContent || '').trim();
                if (text === value || text.includes(value)) {
                    radio.click(); fire(radio);
                    return true;
                }
            }
            return false;
        }
        // text / textarea
        control.value = value; fire(control);
        return true;
    }

    // 画像をfile inputにセット
    async function setImage(imageUrl, filename) {
        const fileInput = document.querySelector('input[type=file]');
        if (!fileInput) return false;
        try {
            const blob = await fetchBlob(API_BASE + imageUrl);
            const file = new File([blob], filename || 'style.jpg', { type: blob.type || 'image/jpeg' });
            const dt = new DataTransfer();
            dt.items.add(file);
            fileInput.files = dt.files;
            fileInput.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        } catch (e) {
            console.warn('画像セット失敗:', e);
            return false;
        }
    }

    // ============ メイン処理 ============
    async function autofill(statusEl) {
        statusEl.textContent = '⏳ アプリからデータ取得中…';
        let data;
        try {
            data = await fetchJson(API_BASE + '/api/pending');
        } catch (e) {
            statusEl.textContent = '❌ ' + e.message;
            return;
        }
        if (data.error) { statusEl.textContent = '❌ ' + data.error; return; }

        const fields = data.fields || {};
        const report = [];

        for (const [key, labels] of Object.entries(FIELD_LABELS)) {
            const value = fields[key];
            if (!value) continue;
            const control = findControlByLabel(labels);
            if (!control) { report.push(`✗ ${key}: 入力欄が見つからない`); continue; }
            const ok = setControlValue(control, value);
            report.push(ok ? `✓ ${key}: 入力済み` : `△ ${key}: 欄はあるが値「${value}」をセットできず`);
        }

        // 画像
        if (data.image_url) {
            const imgOk = await setImage(data.image_url, data.image_filename);
            report.push(imgOk ? '✓ 画像: セット済み' : '✗ 画像: file入力が見つからない/セット失敗');
        }

        statusEl.innerHTML = report.join('<br>') +
            '<br><b>内容を確認して「登録」を押してください</b>';
        console.log('[HPB自動入力] レポート:\n' + report.join('\n'));
    }

    // ============ フローティングUI ============
    function createUI() {
        if (document.getElementById('hpbAutofillBox')) return;
        const box = document.createElement('div');
        box.id = 'hpbAutofillBox';
        box.style.cssText = `
            position: fixed; bottom: 20px; right: 20px; z-index: 999999;
            background: white; border: 2px solid #667eea; border-radius: 12px;
            padding: 14px; box-shadow: 0 8px 24px rgba(0,0,0,.25);
            font-family: -apple-system, 'Hiragino Sans', sans-serif;
            font-size: 12px; max-width: 300px;`;
        box.innerHTML = `
            <div style="font-weight:700; color:#667eea; margin-bottom:8px;">
                🎨 HPB スタイル自動入力
            </div>
            <button id="hpbAutofillBtn" style="
                width:100%; padding:10px; border:none; border-radius:8px;
                background:linear-gradient(135deg,#667eea,#764ba2); color:white;
                font-weight:700; font-size:13px; cursor:pointer;">
                📥 アプリの内容を自動入力
            </button>
            <div id="hpbAutofillStatus" style="margin-top:8px; color:#444; line-height:1.5;"></div>
        `;
        document.body.appendChild(box);
        document.getElementById('hpbAutofillBtn').addEventListener('click', () =>
            autofill(document.getElementById('hpbAutofillStatus')));
    }

    // ページ遷移（SPA含む）にも対応して常にボタンを出す
    createUI();
    new MutationObserver(() => createUI())
        .observe(document.body, { childList: true });
})();
