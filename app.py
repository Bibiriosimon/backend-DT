import os
import datetime
import jwt
import requests
from flask import Flask, jsonify, request, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, desc
import psycopg2.extras
# --- 1. 初始化和配置 ---
app = Flask(__name__)
CORS(app, supports_credentials=True) 

db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-very-strong-default-secret-key-for-local-dev')

db = SQLAlchemy(app)


# --- 2. 数据模型 ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    likes_received = db.Column(db.Integer, nullable=False, default=0)
    
    def to_dict(self):
        return {'id': self.id, 'username': self.username}

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
    
    # 我们把反馈和用户关联起来，这样就知道是谁提的建议了
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('feedbacks', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': self.user_id
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
# --- 2. 数据模型 ---
# ... 你已有的 User, Like, Note, Vocab, Feedback 模型 ...

# 【【【新增代码】】】
# Plaza 帖子的模型
class PlazaTopic(db.Model):
    __tablename__ = 'plaza_topics'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text)
    image_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    # 【关键】使用 username 作为外键
    author_username = db.Column(db.String(80), db.ForeignKey('users.username', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    
    # 建立关系，这样可以方便地通过 topic.author 访问到 User 对象
    author = db.relationship('User', backref=db.backref('plaza_topics', lazy=True, cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'image_url': self.image_url,
            'created_at': self.created_at.isoformat() + 'Z', # 使用ISO格式，前端兼容性更好
            'author_username': self.author_username
        }
class PlazaComment(db.Model):
    __tablename__ = 'plaza_comments'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    # 关联到发评论的用户
    author_username = db.Column(db.String(80), db.ForeignKey('users.username', ondelete='CASCADE'), nullable=False)
    author = db.relationship('User', backref=db.backref('plaza_comments', lazy=True))
    
    # 关联到被评论的帖子
    topic_id = db.Column(db.Integer, db.ForeignKey('plaza_topics.id', ondelete='CASCADE'), nullable=False)
    topic = db.relationship('PlazaTopic', backref=db.backref('comments', lazy=True, cascade="all, delete-orphan"))

    def to_dict(self):
        # 在返回字典时，一并返回作者的点赞数，方便前端展示
        return {
            'id': self.id,
            'content': self.content,
            'created_at': self.created_at.isoformat() + 'Z',
            'author_username': self.author_username,
            'author_likes': self.author.likes_received, # 通过关系直接获取作者的点赞数
            'topic_id': self.topic_id
        }
# 【【【新增代码：聊天消息模型】】】
class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    # 关联到发送者
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    # 关联到接收者
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    # 建立关系，这里需要用 foreign_keys 来区分 sender 和 receiver
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'created_at': self.created_at.isoformat() + 'Z',
            'sender_id': self.sender_id,
            'receiver_id': self.receiver_id
        }

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
            'message': '登录成功！', 'token': token, 'username': user.username,
            'likes_received': user.likes_received
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
    # 1. 验证用户身份
    user_info = get_user_from_token()
    if not user_info:
        return jsonify({'error': '未授权'}), 401

    # 2. 从数据库中查找属于该用户的特定单词
    vocab_item = Vocab.query.filter_by(id=vocab_id, user_id=user_info['user_id']).first()
    if not vocab_item:
        return jsonify({'error': '单词不存在或无权访问'}), 404

    # 3. 如果是 PUT 请求，则执行更新逻辑
    if request.method == 'PUT':
        try:
            data = request.get_json()
            # 检查前端是否发送了 'word' 字段，如果有就更新它
            if 'word' in data:
                vocab_item.word = data['word']
            
            # (这个接口将来还可以扩展，比如更新 phonetic 或 meaning)
            # if 'phonetic' in data:
            #     vocab_item.phonetic = data['phonetic']

            db.session.commit()
            return jsonify({'message': '单词更新成功'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'更新失败: {str(e)}'}), 500

    # 4. 如果是 DELETE 请求，则执行删除逻辑
    if request.method == 'DELETE':
        try:
            db.session.delete(vocab_item)
            db.session.commit()
            return jsonify({'message': '单词已删除'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'删除失败: {str(e)}'}), 500
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
    
    rank_query = db.session.query(
        User.id, User.username, User.likes_received,
        func.count(Vocab.id).label('vocab_count')
    ).outerjoin(Vocab, User.id == Vocab.user_id)\
     .group_by(User.id, User.username, User.likes_received)\
     .order_by(desc('vocab_count'), desc('likes_received'))\
     .all()

    likes_by_me = Like.query.filter_by(liker_id=current_user_id).all()
    liked_user_ids = {like.liked_user_id for like in likes_by_me}

    rank_list = [{
        'user_id': user.id, 'username': user.username,
        'likes_received': user.likes_received, 'vocab_count': user.vocab_count
    } for user in rank_query]

    # 【【【 关键修复！！！】】】 删除这里多余的右括号
    return jsonify({
        'rankings': rank_list,
        'liked_by_me': list(liked_user_ids)
    })

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
    # 1. 验证用户身份
    user_info = get_user_from_token()
    if not user_info:
        return jsonify({'error': '未授权，请先登录'}), 401

    # 2. 获取前端发来的数据
    data = request.get_json()
    content = data.get('content')
    if not content or not content.strip():
        return jsonify({'error': '反馈内容不能为空'}), 400

    # 3. 创建新的Feedback记录并存入数据库
    new_feedback = Feedback(
        content=content,
        user_id=user_info['user_id']
    )
    db.session.add(new_feedback)
    db.session.commit()

    # 4. 返回成功信息
    return jsonify({'message': '感谢您的反馈！我们已经收到啦！'}), 201
@app.route('/api/test-deploy', methods=['GET'])
def test_deploy_route():
    return jsonify({
        'message': '新代码部署成功！这个测试路由正在工作！',
        'timestamp': datetime.datetime.utcnow().isoformat()
    })
# --- 8. API 代理服务 (省略以保持简洁) ---
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
# (确保你的import语句里有这个，psycopg2.extras，如果没有，请加上)
import psycopg2.extras # 在文件顶部添加这个

# ... 你之前的 /register 和 /login 代码在这里 ...

# --- Plaza API 端点 ---

# 3. 获取所有 Plaza 帖子
@app.route('/api/plaza/topics', methods=['GET'])
def get_plaza_topics():
    try:
        # 使用 SQLAlchemy 查询，并按时间倒序
        topics = PlazaTopic.query.order_by(PlazaTopic.created_at.desc()).all()
        # 将查询到的对象列表转换为字典列表
        return jsonify([topic.to_dict() for topic in topics])
    except Exception as e:
        # 捕获任何可能的数据库错误，并返回一个清晰的JSON错误信息
        print(f"Error fetching plaza topics: {e}") # 在服务器日志中打印详细错误
        return jsonify({'error': '获取帖子列表时发生服务器错误'}), 500

# 发布新帖子
@app.route('/api/plaza/topics', methods=['POST'])
def publish_plaza_topic():
    # 从 token 获取当前用户
    user_info = get_user_from_token()
    if not user_info:
        return jsonify({'error': '未授权，请先登录'}), 401

    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    image_url = data.get('image_url') # 如果没有，默认为 None

    if not title or not content:
        return jsonify({"error": "标题和内容不能为空"}), 400

    try:
        # 创建一个新的 PlazaTopic 对象
        new_topic = PlazaTopic(
            title=title,
            content=content,
            image_url=image_url,
            author_username=user_info['username']  # 【关键】从token中获取用户名
        )
        
        # 使用 SQLAlchemy 的 session 来添加和提交
        db.session.add(new_topic)
        db.session.commit()

        # 返回成功信息和新帖子的数据
        return jsonify(new_topic.to_dict()), 201

    except Exception as e:
        db.session.rollback() # 如果发生错误，回滚事务
        print(f"Error publishing plaza topic: {e}")
        return jsonify({'error': '发布帖子时发生服务器错误'}), 500
# 【【【新增代码：Plaza详情、评论、点赞的API】】】

# 获取单个帖子及其所有评论
@app.route('/api/plaza/topics/<int:topic_id>', methods=['GET'])
def get_topic_details(topic_id):
    # 使用 get_or_404 可以简洁地处理找不到帖子的情况
    topic = PlazaTopic.query.get_or_404(topic_id)
    
    # 查询该帖子的所有评论，并按时间正序排列
    comments = PlazaComment.query.filter_by(topic_id=topic_id).order_by(PlazaComment.created_at.asc()).all()

    return jsonify({
        "topic": topic.to_dict(),
        "comments": [comment.to_dict() for comment in comments]
    })

# 为帖子添加新评论
# 为帖子添加新评论
@app.route('/api/plaza/topics/<int:topic_id>/comments', methods=['POST'])
def post_comment(topic_id):
    try:
        user_info = get_user_from_token()
        if not user_info:
            return jsonify({'error': '未授权，请先登录'}), 401

        data = request.get_json()
        content = data.get('content')
        if not content or not content.strip():
            return jsonify({"error": "评论内容不能为空"}), 400

        # 检查帖子是否存在
        topic = PlazaTopic.query.get(topic_id)
        if not topic:
            return jsonify({"error": "帖子不存在"}), 404

        new_comment = PlazaComment(
            content=content,
            topic_id=topic_id,
            author_username=user_info['username'] # 从Token中获取用户名
        )
        db.session.add(new_comment)
        db.session.commit()
        return jsonify(new_comment.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in post_comment: {e}")
        return jsonify({'error': '评论失败，服务器内部错误'}), 500

# 点赞一个评论（增加评论作者的总获赞数）
@app.route('/api/plaza/comments/<int:comment_id>/like', methods=['POST'])
def like_plaza_comment(comment_id):
    # 点赞也需要登录
    user_info = get_user_from_token()
    if not user_info:
        return jsonify({'error': '未授权，请先登录'}), 401

    # 找到被点赞的评论
    comment = PlazaComment.query.get(comment_id)
    if not comment:
        return jsonify({"error": "评论不存在"}), 404
        
    # 找到评论的作者
    author_to_like = User.query.filter_by(username=comment.author_username).first()
    if not author_to_like:
        return jsonify({"error": "评论作者不存在"}), 404
        
    # 【注意】这里我们不允许给自己点赞，逻辑上更合理
    if author_to_like.id == user_info['user_id']:
        return jsonify({'error': '不能给自己的评论点赞'}), 400

    try:
        author_to_like.likes_received += 1
        db.session.commit()
        return jsonify({
            "message": "点赞成功!", 
            "new_likes_count": author_to_like.likes_received
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '点赞失败，服务器错误'}), 500
# 【【【新增代码：Chat 和 User 相关的API】】】

# 获取所有用户列表（除了自己）
@app.route('/api/users', methods=['GET'])
def get_users():
    user_info = get_user_from_token()
    if not user_info:
        return jsonify({'error': '未授权'}), 401
    
    # 查询除了当前用户以外的所有用户
    users = User.query.filter(User.id != user_info['user_id']).all()
    return jsonify([user.to_dict() for user in users])

# 给某个用户点赞
@app.route('/api/users/<int:user_id>/like', methods=['POST'])
def like_user(user_id):
    user_info = get_user_from_token()
    if not user_info:
        return jsonify({'error': '未授权'}), 401
    
    if user_id == user_info['user_id']:
        return jsonify({'error': '不能给自己点赞'}), 400

    user_to_like = User.query.get(user_id)
    if not user_to_like:
        return jsonify({'error': '用户不存在'}), 404

    try:
        user_to_like.likes_received += 1
        db.session.commit()
        return jsonify({
            'message': '点赞成功',
            'new_likes_count': user_to_like.likes_received
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '服务器错误'}), 500

# 获取与另一个用户的聊天记录
# 获取与另一个用户的聊天记录
@app.route('/api/chat/<int:other_user_id>', methods=['GET'])
def get_chat_history(other_user_id):
    # 【【【修改开始】】】
    try:
        user_info = get_user_from_token()
        if not user_info:
            return jsonify({'error': '未授权'}), 401
      
        current_user_id = user_info['user_id']
      
        messages = ChatMessage.query.filter(
            ((ChatMessage.sender_id == current_user_id) & (ChatMessage.receiver_id == other_user_id)) |
            ((ChatMessage.sender_id == other_user_id) & (ChatMessage.receiver_id == current_user_id))
        ).order_by(ChatMessage.created_at.asc()).all()
      
        return jsonify([message.to_dict() for message in messages])
    except Exception as e:
        print(f"Error in get_chat_history: {e}")
        return jsonify({'error': '获取聊天记录时发生服务器错误'}), 500
# 发送聊天消息
# 发送聊天消息
@app.route('/api/chat/send', methods=['POST'])
def send_chat_message():
    try:
        user_info = get_user_from_token()
        if not user_info:
            return jsonify({'error': '未授权'}), 401

        data = request.get_json()
        receiver_id = data.get('receiver_id')
        content = data.get('content')

        if not receiver_id or not content or not content.strip():
            return jsonify({'error': '接收者ID和内容不能为空'}), 400

        # 检查接收者是否存在
        if not User.query.get(receiver_id):
            return jsonify({'error': '接收用户不存在'}), 404

        new_message = ChatMessage(
            sender_id=user_info['user_id'],
            receiver_id=receiver_id,
            content=content
        )
        db.session.add(new_message)
        db.session.commit()
        return jsonify(new_message.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in send_chat_message: {e}")
        return jsonify({'error': '发送失败，服务器内部错误'}), 500

       
# --- 9. 启动应用 ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
