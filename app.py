# app.py

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv

# --- 新增的导入 ---
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, JWTManager
import uuid # 用于生成独一无二的用户ID

# 加载环境变量
load_dotenv()

# --- 初始化应用和扩展 ---
app = Flask(__name__)
CORS(app) # 允许所有来源的跨域请求，方便开发

# 1. 配置数据库
#    从环境变量中获取数据库的连接地址
#    我们之前在 Render 后台设置的 DATABASE_URL 就在这里被用上了
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
#    关闭一个不必要的警告信息
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# 2. 配置 JWT
#    设置一个用于签署 JWT 的密钥，防止令牌被篡改
#    在生产环境中，这应该是一个更复杂、更安全的随机字符串
app.config["JWT_SECRET_KEY"] = "your-super-secret-key-change-it-later" # 以后可以换成更复杂的

# 3. 初始化扩展
db = SQLAlchemy(app) # 初始化 SQLAlchemy，把它和我们的 Flask app 关联起来
jwt = JWTManager(app) # 初始化 JWTManager

# --- 数据库模型定义 (The Blueprint) ---
#    我们在这里定义 "User" 这张表长什么样

class User(db.Model):
    __tablename__ = 'users' # 定义在数据库中的表名

    # 定义字段 (列)
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False) # 注意：现在是明文存储

    # 定义一个简单的方法，方便我们把用户信息转换成字典格式
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username
        }

# --- 创建数据库表的命令 ---
# 这个函数只在第一次部署或需要创建新表时手动运行一次
# 它会检查所有的模型（比如User类），并在数据库中创建对应的表
@app.cli.command("create-db")
def create_db():
    """在数据库中创建所有表"""
    with app.app_context():
        db.create_all()
    print("Database tables created!")


# --- 原有的 DeepL 翻译 API ---
# 我们暂时保留这个接口，之后可以学习如何保护它
@app.route('/api/translate', methods=['POST'])
def translate_text():
    data = request.json
    text_to_translate = data.get('text')
    target_lang = data.get('target_lang', 'ZH')

    if not text_to_translate:
        return jsonify({"error": "No text provided"}), 400

    auth_key = os.environ.get("DEEPL_AUTH_KEY")
    if not auth_key:
        return jsonify({"error": "DeepL API key not configured"}), 500

    api_url = "https://api-free.deepl.com/v2/translate"
    
    payload = {
        'auth_key': auth_key,
        'text': text_to_translate,
        'target_lang': target_lang
    }

    try:
        response = requests.post(api_url, data=payload)
        response.raise_for_status() 
        translated_data = response.json()
        return jsonify(translated_data)
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

# --- 根路径 ---
@app.route('/')
def index():
    return "Backend server is running."

if __name__ == '__main__':
    # 使用 app.run() 会启动 Flask 内置的开发服务器
    # 在生产环境中 (比如Render)，我们会用 gunicorn 来启动
    app.run(debug=True, port=5001)