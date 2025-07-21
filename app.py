import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app) 

# --- API 密钥与地址配置 ---
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

@app.route('/')
def index():
    return "同声传译后端API代理服务器已启动。"

# --- DeepL 代理接口 (已完成) ---
@app.route('/api/deepl-translate', methods=['POST'])
def proxy_deepl_translate():
    data = request.json
    text_to_translate = data.get('text')
    target_lang = data.get('target_lang', 'ZH')

    if not text_to_translate:
        return jsonify({"error": "缺少 'text' 字段"}), 400

    payload = {
        'auth_key': DEEPL_API_KEY,
        'text': text_to_translate,
        'target_lang': target_lang,
        'source_lang': 'EN'
    }
    
    try:
        response = requests.post(DEEPL_API_URL, data=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response is not None else 500
        error_message = str(e)
        if e.response is not None:
            try:
                error_message = e.response.json()
            except ValueError:
                error_message = e.response.text
        return jsonify({"error": "调用翻译服务失败", "details": error_message}), status_code

# --- 新增：DeepSeek 代理接口 ---
@app.route('/api/deepseek-chat', methods=['POST'])
def proxy_deepseek_chat():
    # 1. 从前端获取完整的请求体 (如 { "model": "...", "messages": [...] })
    request_data = request.json
    
    if not request_data:
        return jsonify({"error": "请求体为空"}), 400

    # 2. 准备发送给真正DeepSeek API的请求头，在这里注入我们的密钥
    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
    }

    try:
        # 3. 将前端发来的数据和我们安全的请求头一起发送给DeepSeek
        response = requests.post(DEEPSEEK_API_URL, json=request_data, headers=headers)
        response.raise_for_status() # 检查错误

        # 4. 将DeepSeek的响应直接返回给前端
        return response.json()
    except requests.exceptions.RequestException as e:
        # 统一的错误处理
        status_code = e.response.status_code if e.response is not None else 500
        error_message = str(e)
        if e.response is not None:
            try:
                error_message = e.response.json()
            except ValueError:
                error_message = e.response.text
        return jsonify({"error": "调用AI服务失败", "details": error_message}), status_code


if __name__ == '__main__':
    app.run(debug=True, port=5001)