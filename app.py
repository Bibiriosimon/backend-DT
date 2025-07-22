# app.py (最终完整版 - 已添加笔记和单词本功能)

import os
import datetime
import jwt
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

# --- 1. 初始化和配置 ---
app = Flask(__name__)
# 允许所有来源的跨域请求, 并支持 credentials (例如发送cookies或Authorization头)
CORS(app, supports_credentials=True) 

# 数据库URL配置 (适配Render的PostgreSQL)
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-very-strong-default-secret-key-for-local-dev')

db = SQLAlchemy(app)


# --- 2. 数据模型 ---
# 2.1 用户模型
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    
    def to_dict(self):
        return {'id': self.id, 'username': self.username}

# 2.2 [新增] 笔记模型
class Note(db.Model):
    __tablename__ = 'notes'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    # 建立与User模型的关系
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('notes', lazy=True, cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'created_at': self.created_at.isoformat() + 'Z' # 使用ISO 8601格式，方便JS处理
        }

# 2.3 [新增] 单词本模型
class Vocab(db.Model):
    __tablename__ = 'vocabs'
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    phonetic = db.Column(db.String(100))
    meaning = db.Column(db.Text, nullable=False) 
    
    # 建立与User模型的关系
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('vocabs', lazy=True, cascade="all, delete-orphan"))

    # 添加唯一性约束：同一个用户不能重复添加同一个单词
    __table_args__ = (db.UniqueConstraint('user_id', 'word', name='_user_word_uc'),)

    def to_dict(self):
        return {
            'id': self.id,
            'word': self.word,
            'phonetic': self.phonetic,
            'meaning': self.meaning 
        }

# --- 3. 数据库表创建 ---
# 此命令确保在应用启动时，所有定义的模型对应的表都已在数据库中创建
with app.app_context():
    db.create_all()


# --- 4. JWT 身份验证辅助函数 ---
def get_user_from_token():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(" ")[1]
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return {'user_id': data['user_id'], 'username': data['username']}
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# =======================================================
# ==================== API 路由 =========================
# =======================================================

# --- 5. 用户认证 API (保持不变) ---
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': '该用户名已被注册'}), 409
    new_user = User(username=username, password=password) # 注意：生产环境应哈希密码
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
    if user and user.password == password: # 注意：生产环境应验证哈希密码
        token = jwt.encode({
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        return jsonify({'message': '登录成功！', 'token': token, 'username': user.username})
    else:
        return jsonify({'error': '用户名或密码错误'}), 401


# --- 6. [新增] 笔记和单词本 API (受保护的路由) ---

# 6.1 笔记 API
@app.route('/api/notes', methods=['POST'])
def add_note():
    user_info = get_user_from_token()
    if not user_info:
        return jsonify({'error': '未授权或Token无效'}), 401

    data = request.get_json()
    content = data.get('content')
    if not content:
        return jsonify({'error': '笔记内容不能为空'}), 400

    new_note = Note(content=content, user_id=user_info['user_id'])
    db.session.add(new_note)
    db.session.commit()
    return jsonify({'message': '笔记已保存', 'note': new_note.to_dict()}), 201

@app.route('/api/notes', methods=['GET'])
def get_notes():
    user_info = get_user_from_token()
    if not user_info:
        return jsonify({'error': '未授权或Token无效'}), 401
    
    search_query = request.args.get('search', '')
    
    base_query = Note.query.filter_by(user_id=user_info['user_id'])
    
    if search_query:
        notes = base_query.filter(Note.content.ilike(f'%{search_query}%')).order_by(Note.created_at.desc()).all()
    else:
        notes = base_query.order_by(Note.created_at.desc()).all()
        
    return jsonify([note.to_dict() for note in notes])

# 6.2 单词本 API
@app.route('/api/vocab', methods=['POST'])
def add_vocab():
    user_info = get_user_from_token()
    if not user_info:
        return jsonify({'error': '未授权或Token无效'}), 401
    
    data = request.get_json()
    if not data or not data.get('word') or not data.get('meaning'):
        return jsonify({'error': '缺少必要数据'}), 400

    existing_vocab = Vocab.query.filter_by(user_id=user_info['user_id'], word=data['word']).first()
    if existing_vocab:
        return jsonify({'message': '单词已在您的单词本中'}), 200

    new_vocab = Vocab(
        word=data['word'],
        phonetic=data.get('phonetic'),
        meaning=data['meaning'],
        user_id=user_info['user_id']
    )
    db.session.add(new_vocab)
    db.session.commit()
    return jsonify({'message': '单词已添加', 'vocab': new_vocab.to_dict()}), 201

@app.route('/api/vocab', methods=['GET'])
def get_vocab():
    user_info = get_user_from_token()
    if not user_info:
        return jsonify({'error': '未授权或Token无效'}), 401

    vocabs = Vocab.query.filter_by(user_id=user_info['user_id']).order_by(Vocab.word).all()
    return jsonify([v.to_dict() for v in vocabs])


# --- 7. API 代理服务 (保持不变) ---
@app.route('/api/deepl-translate', methods=['POST'])
def deepl_translate_proxy():
    api_key = os.environ.get('DEEPL_API_KEY')
    if not api_key:
        return jsonify({'error': '服务器未配置 DeepL API Key'}), 500
    data = request.get_json()
    # ... (其余逻辑不变)
    try:
        response = requests.post(
            'https://api-free.deepl.com/v2/translate',
            headers={'Authorization': f'DeepL-Auth-Key {api_key}'},
            json={'text': [data.get('text')], 'target_lang': data.get('target_lang', 'ZH')}
        )
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'error': '请求翻译服务失败', 'details': str(e)}), 502

@app.route('/api/deepseek-chat', methods=['POST'])
def deepseek_chat_proxy():
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        return jsonify({'error': '服务器未配置 DeepSeek API Key'}), 500
    data = request.get_json()
    # ... (其余逻辑不变)
    try:
        response = requests.post(
            'https://api.deepseek.com/chat/completions',
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
            json=data
        )
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'error': '请求 AI 服务失败', 'details': str(e)}), 502

@app.route('/api/dictionary-proxy/<word>', methods=['GET'])
def dictionary_proxy(word):
    if not word:
        return jsonify({'error': 'Word parameter is missing'}), 400
    try:
        response = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
        return jsonify(response.json()), response.status_code
    except (requests.exceptions.RequestException, requests.exceptions.JSONDecodeError) as e:
        return jsonify({'error': '词典服务连接或解析失败', 'details': str(e)}), 502


# --- 8. 测试与管理 API (保持不变) ---
@app.route('/test_db')
def test_db():
    try:
        user_count = db.session.query(User.id).count()
        return f"数据库连接成功！当前共有 {user_count} 位用户。"
    except Exception as e:
        return f"数据库连接或查询失败: {e}", 500
        
@app.route('/admin/reset-database/areyousure/<secret_key>')
def reset_database(secret_key):
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

# --- 9. 启动应用 ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    # Render 等生产环境会使用 gunicorn，这里的 app.run 仅用于本地调试
    app.run(host='0.0.0.0', port=port, debug=False)

