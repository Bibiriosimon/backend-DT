import os
import datetime
import jwt
import requests
from flask import Flask, jsonify, request, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, desc, or_
import psycopg2.extras
import mistune
# --- 1. 初始化和配置 ---
app = Flask(__name__)
CORS(app, supports_credentials=True) 
markdown_parser = mistune.create_markdown(escape=True, hard_wrap=True)
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-very-strong-default-secret-key-for-local-dev')

db = SQLAlchemy(app)
AVATAR_CHOICES = [
    "https://pic1.imgdb.cn/item/688b193958cb8da5c8f46e6a.jpg",
    "https://pic1.imgdb.cn/item/688b193f58cb8da5c8f46e89.jpg",
    "https://pic1.imgdb.cn/item/688b193b58cb8da5c8f46e75.jpg",
    "https://pic1.imgdb.cn/item/688b193558cb8da5c8f46e53.jpg",
    "https://pic1.imgdb.cn/item/688b193158cb8da5c8f46e38.jpg",
    "https://pic1.imgdb.cn/item/688b192f58cb8da5c8f46e27.jpg",
    "https://pic1.imgdb.cn/item/688b192a58cb8da5c8f46e09.jpg",
    "https://pic1.imgdb.cn/item/688b191f58cb8da5c8f46dd4.jpg",
    "https://pic1.imgdb.cn/item/688b1e6458cb8da5c8f481ed.jpg"
]

# --- 2. 数据模型 ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    likes_received = db.Column(db.Integer, nullable=False, default=0)
    avatar_url = db.Column(db.String(255), nullable=True)
  
    def to_dict(self):
        return {
            'id': self.id, 
            'username': self.username,
            'likes_received': self.likes_received,
            'avatar_url': self.avatar_url or AVATAR_CHOICES[0]
        }

class Like(db.Model):
    __tablename__ = 'likes'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    liker_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    liked_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('liker_id', 'liked_user_id', name='_liker_liked_user_uc'),)

class Note(db.Model):
    __tablename__ = 'notes'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('notes', lazy=True, cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'summary': self.summary,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class Vocab(db.Model):
    __tablename__ = 'vocabs'
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    phonetic = db.Column(db.String(100))
    meaning = db.Column(db.Text, nullable=False) 
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('vocabs', lazy=True, cascade="all, delete-orphan"))
    __table_args__ = (db.UniqueConstraint('user_id', 'word', name='_user_word_uc'),)

    def to_dict(self):
        return {
            'id': self.id,
            'word': self.word,
            'phonetic': self.phonetic,
            'meaning': self.meaning 
        }

class Feedback(db.Model):
    __tablename__ = 'feedbacks'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('feedbacks', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': self.user_id
        }

class PlazaTopic(db.Model):
    __tablename__ = 'plaza_topics'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text)
    image_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    author_username = db.Column(db.String(80), db.ForeignKey('users.username', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    author = db.relationship('User', backref=db.backref('plaza_topics', lazy=True, cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'image_url': self.image_url,
            'created_at': self.created_at.isoformat() + 'Z',
            'author_username': self.author.username,
            'author_avatar_url': self.author.avatar_url or AVATAR_CHOICES[0]
        }

class PlazaComment(db.Model):
    __tablename__ = 'plaza_comments'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    author_username = db.Column(db.String(80), db.ForeignKey('users.username', ondelete='CASCADE'), nullable=False)
    author = db.relationship('User', backref=db.backref('plaza_comments', lazy=True))
    topic_id = db.Column(db.Integer, db.ForeignKey('plaza_topics.id', ondelete='CASCADE'), nullable=False)
    topic = db.relationship('PlazaTopic', backref=db.backref('comments', lazy=True, cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'created_at': self.created_at.isoformat() + 'Z',
            'author_username': self.author.username,
            'author_likes': self.author.likes_received,
            'author_avatar_url': self.author.avatar_url or AVATAR_CHOICES[0],
            'topic_id': self.topic_id
        }

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    sender_username = db.Column(db.String(80), db.ForeignKey('users.username', ondelete='CASCADE'), nullable=False)
    receiver_username = db.Column(db.String(80), db.ForeignKey('users.username', ondelete='CASCADE'), nullable=False)

    # 【【【核心修复】】】
    # 明确指定每个关系(sender, receiver)对应的外键列，消除歧义。
    sender = db.relationship('User', foreign_keys=[sender_username])
    receiver = db.relationship('User', foreign_keys=[receiver_username])

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'created_at': self.created_at.isoformat() + 'Z',
            'sender_id': self.sender.id,
            'receiver_id': self.receiver.id,
            'sender_username': self.sender.username,
            'receiver_username': self.receiver.username,
            'sender_avatar_url': self.sender.avatar_url or AVATAR_CHOICES[0],
            'receiver_avatar_url': self.receiver.avatar_url or AVATAR_CHOICES[0]
        }

# --- 3. 数据库表创建 ---
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

# --- 5. 用户认证 API ---
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username, password = data.get('username'), data.get('password')
    if not username or not password: return jsonify({'message': '用户名和密码不能为空'}), 400
    if User.query.filter_by(username=username).first(): return jsonify({'message': '该用户名已被注册'}), 409
    new_user = User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': '注册成功！', 'user': new_user.to_dict()}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username, password = data.get('username'), data.get('password')
    user = User.query.filter_by(username=username).first()
    if user and user.password == password:
        token = jwt.encode({
            'user_id': user.id, 'username': user.username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        return jsonify({
            'message': '登录成功！', 
            'token': token, 
            'username': user.username,
            'user_id': user.id,
            'likes_received': user.likes_received,
            'avatar_url': user.avatar_url or AVATAR_CHOICES[0]
        })
    else:
        return jsonify({'message': '用户名或密码错误'}), 401

@app.route('/api/user/stats', methods=['GET'])
def get_user_stats():
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    user = User.query.get(user_info['user_id'])
    if not user: return jsonify({'error': '用户不存在'}), 404
    return jsonify({'likes_received': user.likes_received})

# --- 6. 笔记和单词本 API ---
@app.route('/api/notes', methods=['POST'])
def add_note():
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    data = request.get_json()
    content, summary = data.get('content'), data.get('summary')
    if not content: return jsonify({'error': '内容不能为空'}), 400
    new_note = Note(content=content, summary=summary, user_id=user_info['user_id'])
    db.session.add(new_note)
    db.session.commit()
    return jsonify({'message': '笔记已保存', 'note': new_note.to_dict()}), 201

@app.route('/api/note/<int:note_id>', methods=['GET', 'DELETE'])
def handle_single_note(note_id):
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    note = Note.query.filter_by(id=note_id, user_id=user_info['user_id']).first()
    if not note: return jsonify({'error': '笔记不存在或无权访问'}), 404
    if request.method == 'GET': return jsonify(note.to_dict())
    if request.method == 'DELETE':
        db.session.delete(note)
        db.session.commit()
        return jsonify({'message': '笔记已删除'})

@app.route('/api/notes', methods=['GET'])
def get_notes():
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    notes = Note.query.filter_by(user_id=user_info['user_id']).order_by(desc(Note.created_at)).all()
    return jsonify([n.to_dict() for n in notes])

@app.route('/api/vocab', methods=['POST'])
def add_vocab():
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    data = request.get_json()
    if not data or not data.get('word') or not data.get('meaning'): return jsonify({'error': '缺少必要数据'}), 400
    if Vocab.query.filter_by(user_id=user_info['user_id'], word=data['word']).first(): return jsonify({'message': '单词已在您的单词本中'}), 200
    new_vocab = Vocab(word=data['word'], phonetic=data.get('phonetic'), meaning=data['meaning'], user_id=user_info['user_id'])
    db.session.add(new_vocab)
    db.session.commit()
    return jsonify({'message': '单词已添加', 'vocab': new_vocab.to_dict()}), 201

@app.route('/api/vocab/<int:vocab_id>', methods=['PUT', 'DELETE'])
def handle_single_vocab(vocab_id):
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    vocab_item = Vocab.query.filter_by(id=vocab_id, user_id=user_info['user_id']).first()
    if not vocab_item: return jsonify({'error': '单词不存在或无权访问'}), 404
    if request.method == 'PUT':
        data = request.get_json()
        if 'word' in data: vocab_item.word = data['word']
        db.session.commit()
        return jsonify({'message': '单词更新成功'}), 200
    if request.method == 'DELETE':
        db.session.delete(vocab_item)
        db.session.commit()
        return jsonify({'message': '单词已删除'})

@app.route('/api/vocab', methods=['GET'])
def get_vocab():
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    vocabs = Vocab.query.filter_by(user_id=user_info['user_id']).order_by(Vocab.word).all()
    return jsonify([v.to_dict() for v in vocabs])

# --- 7. 排名与点赞 API ---
@app.route('/api/rank', methods=['GET'])
def get_rank_list():
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    current_user_id = user_info['user_id']
  
    # 【恢复】使用您原来的 group_by 写法，更严谨
    rank_query = db.session.query(
        User.id, User.username, User.likes_received,
        func.count(Vocab.id).label('vocab_count')
    ).outerjoin(Vocab, User.id == Vocab.user_id)\
     .group_by(User.id, User.username, User.likes_received)\
     .order_by(desc('vocab_count'), desc('likes_received'))\
     .all()

    likes_by_me = Like.query.filter_by(liker_id=current_user_id).all()
    liked_user_ids = {like.liked_user_id for like in likes_by_me}
    rank_list = [{'user_id': user.id, 'username': user.username, 'likes_received': user.likes_received, 'vocab_count': user.vocab_count} for user in rank_query]
    return jsonify({'rankings': rank_list, 'liked_by_me': list(liked_user_ids)})

@app.route('/api/user/<int:liked_user_id>/like', methods=['POST'])
def toggle_like(liked_user_id):
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    liker_id = user_info['user_id']
    if liker_id == liked_user_id: return jsonify({'error': '不能给自己点赞'}), 400
    liked_user = User.query.get(liked_user_id)
    if not liked_user: return jsonify({'error': '被点赞的用户不存在'}), 404
    existing_like = Like.query.filter_by(liker_id=liker_id, liked_user_id=liked_user_id).first()
    if existing_like:
        db.session.delete(existing_like)
        liked_user.likes_received = max(0, liked_user.likes_received - 1)
        message = '取消点赞成功'
    else:
        new_like = Like(liker_id=liker_id, liked_user_id=liked_user_id)
        db.session.add(new_like)
        liked_user.likes_received += 1
        message = '点赞成功'
    db.session.commit()
    return jsonify({'message': message, 'new_like_count': liked_user.likes_received})

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权，请先登录'}), 401
    data = request.get_json()
    content = data.get('content')
    if not content or not content.strip(): return jsonify({'error': '反馈内容不能为空'}), 400
    new_feedback = Feedback(content=content, user_id=user_info['user_id'])
    db.session.add(new_feedback)
    db.session.commit()
    return jsonify({'message': '感谢您的反馈！我们已经收到啦！'}), 201

# 【恢复】补上被遗漏的测试路由
@app.route('/api/test-deploy', methods=['GET'])
def test_deploy_route():
    return jsonify({
        'message': '新代码部署成功！这个测试路由正在工作！',
        'timestamp': datetime.datetime.utcnow().isoformat()
    })

# --- 8. API 代理服务 & 其他 ---
@app.route('/api/deepl-translate', methods=['POST'])
def deepl_translate_proxy():
    api_key = os.environ.get('DEEPL_API_KEY')
    if not api_key: return jsonify({'error': '服务器未配置 DeepL API Key'}), 500
    data = request.get_json()
    try:
        response = requests.post('https://api-free.deepl.com/v2/translate', headers={'Authorization': f'DeepL-Auth-Key {api_key}'}, json={'text': [data.get('text')], 'target_lang': data.get('target_lang', 'ZH')})
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'error': '请求翻译服务失败', 'details': str(e)}), 502

@app.route('/api/deepseek-chat', methods=['POST'])
def deepseek_chat_proxy():
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key: return jsonify({'error': '服务器未配置 DeepSeek API Key'}), 500
    data = request.get_json()
    try:
        response = requests.post('https://api.deepseek.com/chat/completions', headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}, json=data)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'error': '请求 AI 服务失败', 'details': str(e)}), 502

@app.route('/api/dictionary-proxy/<word>', methods=['GET'])
def dictionary_proxy(word):
    if not word: return jsonify({'error': 'Word parameter is missing'}), 400
    try:
        response = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
        return jsonify(response.json()), response.status_code
    except (requests.exceptions.RequestException, requests.exceptions.JSONDecodeError) as e:
        return jsonify({'error': '词典服务连接或解析失败', 'details': str(e)}), 502

@app.route('/api/plaza/topics', methods=['GET'])
def get_plaza_topics():
    try:
        topics = PlazaTopic.query.order_by(PlazaTopic.created_at.desc()).all()
        return jsonify([topic.to_dict() for topic in topics])
    except Exception as e:
        print(f"Error fetching plaza topics: {e}")
        return jsonify({'error': '获取帖子列表时发生服务器错误'}), 500

@app.route('/api/plaza/topics', methods=['POST'])
@jwt_required()
def publish_plaza_topic():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({'error': '用户未找到'}), 404
        
    data = request.get_json()
    title = data.get('title')
    # 【修改1】获取包含 Markdown 的原始文本
    raw_content = data.get('content') 
    
    # 【删除】不再接收独立的 image_url
    # image_url = data.get('image_url')

    if not title or not raw_content:
        return jsonify({"error": "标题和内容不能为空"}), 400
    
    try:
        # 【修改2】将 Markdown 转换为安全的 HTML
        html_content = markdown_parser(raw_content)

        # 【修改3】创建一个新的 PlazaTopic 实例
        # content 字段现在存储的是转换后的 HTML
        # image_url 字段不再需要手动设置，让它保持数据库的默认值 (NULL)
        new_topic = PlazaTopic(
            title=title, 
            content=html_content, # 存储 HTML
            author_id=user.id
        )
        db.session.add(new_topic)
        db.session.commit()

        # to_dict() 方法会自动返回所有字段，包括新的 HTML content
        return jsonify(new_topic.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/plaza/topics/<int:topic_id>', methods=['GET'])
def get_topic_details(topic_id):
    topic = PlazaTopic.query.get_or_404(topic_id)
    comments = PlazaComment.query.filter_by(topic_id=topic_id).order_by(PlazaComment.created_at.asc()).all()
    return jsonify({"topic": topic.to_dict(), "comments": [comment.to_dict() for comment in comments]})

@app.route('/api/plaza/topics/<int:topic_id>/comments', methods=['POST'])
def post_comment(topic_id):
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权，请先登录'}), 401
    data = request.get_json()
    content = data.get('content')
    if not content or not content.strip(): return jsonify({"error": "评论内容不能为空"}), 400
    topic = PlazaTopic.query.get(topic_id)
    if not topic: return jsonify({"error": "帖子不存在"}), 404
    try:
        new_comment = PlazaComment(content=content, topic_id=topic_id, author_username=user_info['username'])
        db.session.add(new_comment)
        db.session.commit()
        return jsonify(new_comment.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in post_comment: {e}")
        return jsonify({'error': '评论失败，服务器内部错误'}), 500

@app.route('/api/plaza/comments/<int:comment_id>/like', methods=['POST'])
def like_plaza_comment(comment_id):
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权，请先登录'}), 401
    comment = PlazaComment.query.get(comment_id)
    if not comment: return jsonify({"error": "评论不存在"}), 404
    author_to_like = User.query.filter_by(username=comment.author_username).first()
    if not author_to_like: return jsonify({"error": "评论作者不存在"}), 404
    if author_to_like.id == user_info['user_id']: return jsonify({'error': '不能给自己的评论点赞'}), 400
    try:
        author_to_like.likes_received += 1
        db.session.commit()
        return jsonify({"message": "点赞成功!", "new_likes_count": author_to_like.likes_received})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '点赞失败，服务器错误'}), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    users = User.query.filter(User.id != user_info['user_id']).all()
    return jsonify([user.to_dict() for user in users])

@app.route('/api/users/<int:user_id>/like', methods=['POST'])
def like_user(user_id):
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    if user_id == user_info['user_id']: return jsonify({'error': '不能给自己点赞'}), 400
    user_to_like = User.query.get(user_id)
    if not user_to_like: return jsonify({'error': '用户不存在'}), 404
    try:
        user_to_like.likes_received += 1
        db.session.commit()
        return jsonify({'message': '点赞成功', 'new_likes_count': user_to_like.likes_received})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '服务器错误'}), 500

@app.route('/api/chat/<int:other_user_id>', methods=['GET'])
def get_chat_history(other_user_id):
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    current_user_username = user_info['username']
    other_user = User.query.get(other_user_id)
    if not other_user: return jsonify({'error': '聊天对象不存在'}), 404
    other_user_username = other_user.username
    messages = ChatMessage.query.filter(
        or_(
            (ChatMessage.sender_username == current_user_username) & (ChatMessage.receiver_username == other_user_username),
            (ChatMessage.sender_username == other_user_username) & (ChatMessage.receiver_username == current_user_username)
        )
    ).order_by(ChatMessage.created_at.asc()).all()
    return jsonify([message.to_dict() for message in messages])

@app.route('/api/chat/send', methods=['POST'])
def send_chat_message():
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    data = request.get_json()
    receiver_id, content = data.get('receiver_id'), data.get('content')
    if not receiver_id or not content or not content.strip(): return jsonify({'error': '接收者ID和内容不能为空'}), 400
    receiver_user = User.query.get(receiver_id)
    if not receiver_user: return jsonify({'error': '接收用户不存在'}), 404
    try:
        new_message = ChatMessage(sender_username=user_info['username'], receiver_username=receiver_user.username, content=content)
        db.session.add(new_message)
        db.session.commit()
        return jsonify(new_message.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in send_chat_message: {e}")
        return jsonify({'error': '发送失败，服务器内部错误'}), 500

@app.route('/api/avatars', methods=['GET'])
def get_avatar_choices():
    return jsonify(AVATAR_CHOICES)

@app.route('/api/user/avatar', methods=['POST'])
def update_user_avatar():
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    data = request.get_json()
    new_avatar_url = data.get('avatar_url')
    if not new_avatar_url or new_avatar_url not in AVATAR_CHOICES: return jsonify({'error': '无效的头像选择'}), 400
    user = User.query.get(user_info['user_id'])
    if not user: return jsonify({'error': '用户不存在'}), 404
    user.avatar_url = new_avatar_url
    db.session.commit()
    return jsonify({'message': '头像更新成功', 'new_avatar_url': new_avatar_url})

@app.route('/api/chat/<int:partner_id>/new', methods=['GET'])
def get_new_chat_messages(partner_id):
    user_info = get_user_from_token()
    if not user_info: return jsonify({'error': '未授权'}), 401
    since_message_id = request.args.get('since', 0, type=int)
    other_user = User.query.get(partner_id)
    if not other_user: return jsonify({'error': '聊天对象不存在'}), 404
    current_user_username = user_info['username']
    other_user_username = other_user.username
    messages = ChatMessage.query.filter(
        ChatMessage.id > since_message_id,
        or_(
            (ChatMessage.sender_username == current_user_username) & (ChatMessage.receiver_username == other_user_username),
            (ChatMessage.sender_username == other_user_username) & (ChatMessage.receiver_username == current_user_username)
        )
    ).order_by(ChatMessage.created_at.asc()).all()
    return jsonify([msg.to_dict() for msg in messages])     

@app.route('/admin/reset-database/areyousure/<secret_key>')
def reset_database(secret_key):
    reset_word = os.environ.get('RESET_SECRET_WORD', 'my_default_reset_word')
    if secret_key != reset_word: return jsonify({"error": "密码错误，无法执行危险操作"}), 403
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
    app.run(host='0.0.0.0', port=port, debug=True)

