# app.py (最终完整版)

import os
import datetime
import jwt
import requests # <-- 确保导入了 requests 库
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

# --- 1. 初始化和配置 ---
app = Flask(__name__)
CORS(app) # 允许所有来源的跨域请求

# 数据库URL配置 (适配Render的PostgreSQL)
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 从环境变量获取 SECRET_KEY，用于JWT签名
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-very-strong-default-secret-key-for-local-dev')

db = SQLAlchemy(app)

# --- 2. 数据模型 (用户信息) ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False) # 在真实项目中，这里应该是哈希后的密码
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username
        }

# --- 3. 数据库表创建 ---
# 在应用上下文中创建所有定义的数据库表
with app.app_context():
    db.create_all()


# =======================================================
# ==================== API 路由 =========================
# =======================================================

# --- 4. 用户认证 API ---

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': '该用户名已被注册'}), 409

    new_user = User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': '注册成功！', 'user': new_user.to_dict()}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': '请输入用户名和密码'}), 400

    user = User.query.filter_by(username=username).first()

    # 注意：这里是明文密码比较，仅用于演示。生产环境应使用哈希密码。
    if user and user.password == password:
        token = jwt.encode({
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24) # Token有效期24小时
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'message': '登录成功！',
            'token': token,
            'username': user.username
        })
    else:
        return jsonify({'error': '用户名或密码错误'}), 401


# --- 5. 【新增】API 代理服务 ---
# 这个部分是解决您问题的核心

# --- 5.1 DeepL 翻译代理 ---
@app.route('/api/deepl-translate', methods=['POST'])
def deepl_translate_proxy():
    api_key = os.environ.get('DEEPL_API_KEY')
    if not api_key:
        return jsonify({'error': '服务器未配置 DeepL API Key'}), 500

    data = request.get_json()
    text_to_translate = data.get('text')
    target_lang = data.get('target_lang', 'ZH')

    if not text_to_translate:
        return jsonify({'error': '缺少需要翻译的文本'}), 400

    try:
        response = requests.post(
            'https://api-free.deepl.com/v2/translate',
            headers={'Authorization': f'DeepL-Auth-Key {api_key}'},
            json={'text': [text_to_translate], 'target_lang': target_lang}
        )
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        print(f"请求 DeepL API 时发生错误: {e}")
        return jsonify({'error': '请求翻译服务失败'}), 502

# --- 5.2 DeepSeek 聊天代理 ---
@app.route('/api/deepseek-chat', methods=['POST'])
def deepseek_chat_proxy():
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        return jsonify({'error': '服务器未配置 DeepSeek API Key'}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({'error': '缺少请求体'}), 400

    try:
        response = requests.post(
            'https://api.deepseek.com/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            json=data # 直接转发前端发来的JSON数据
        )
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        print(f"请求 DeepSeek API 时发生错误: {e}")
        return jsonify({'error': '请求 AI 服务失败'}), 502


# --- 6. 测试与管理 API ---

@app.route('/test_db')
def test_db():
    """测试数据库连接是否正常。"""
    try:
        user_count = db.session.query(User.id).count()
        return f"数据库连接成功！当前共有 {user_count} 位用户。"
    except Exception as e:
        return f"数据库连接或查询失败: {e}", 500
        
@app.route('/admin/reset-database/areyousure/<secret_key>')
def reset_database(secret_key):
    """【危险操作】重置数据库，仅用于开发调试。"""
    # 从环境变量获取重置密码，增强安全性
    reset_word = os.environ.get('RESET_SECRET_WORD', 'my_default_reset_word')
    if secret_key != reset_word:
        return jsonify({"error": "密码错误，无法执行危险操作"}), 403

    try:
        with app.app_context():
            db.drop_all()
            db.create_all()
        return jsonify({"message": "数据库已成功重置！"}), 200
    except Exception as e:
        return jsonify({"error": f"重置数据库时发生错误: {str(e)}"}), 500

# --- 7. 启动应用 ---
if __name__ == '__main__':
    # Render会通过Gunicorn启动，这里主要用于本地开发
    port = int(os.environ.get('PORT', 5001)) # 使用5001以避免和前端常用端口冲突
    app.run(host='0.0.0.0', port=port, debug=True) # 本地开启debug模式

