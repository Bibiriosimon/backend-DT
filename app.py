# app.py

import os
import datetime # 用于设置 JWT 的过期时间
import jwt # 导入 PyJWT 库
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

# --- 初始化和配置 (和之前一样) ---
app = Flask(__name__)
CORS(app)

db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 新增：从环境变量获取 SECRET_KEY
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'my-default-secret-key') # 提供一个默认值以防万一

db = SQLAlchemy(app)

# --- 数据模型 (和之前一样) ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username
        }

# --- 数据库表创建 (和之前一样，但在部署时不再是必需的) ---
# 这段代码在第一次部署时很有用，之后可以保持原样
with app.app_context():
    db.create_all()


# -------------------- API 路由 --------------------

# --- 新增：注册 API ---
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Do not be blank'}), 400

    # 检查用户名是否已存在
    if User.query.filter_by(username=username).first():
        return jsonify({'error': '有老登比你先来一步，try another user name'}), 409 # 409 Conflict

    # 创建新用户实例 (暂时用明文密码)
    new_user = User(username=username, password=password)
    
    # 添加到数据库会话并提交
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': '欢迎加入我们,welcome to our family', 'user': new_user.to_dict()}), 201


# --- 新增：登录 API ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Please enter user name and secret key'}), 400

    # 在数据库中查找用户
    user = User.query.filter_by(username=username).first()

    # 验证用户是否存在以及密码是否匹配
    if user and user.password == password: # 暂时直接比较明文密码
        # 登录成功，生成 JWT
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24) # Token有效期24小时
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'message': 'Here we go baby!',
            'token': token,
            'user': user.to_dict()
        })
    else:
        return jsonify({'error': 'error,give another try baby!'}), 401 # 401 Unauthorized


# --- 保留的测试和旧的 todos API ---
@app.route('/test_db')
def test_db():
    try:
        db.session.query(User).all() 
        return "数据库连接成功！User 表也已成功映射！"
    except Exception as e:
        return f"数据库连接失败: {e}"

todos = [] # 旧的 todos 我们暂时不动它，之后会改造
@app.route('/api/todos', methods=['GET', 'POST'])
def handle_todos():
    if request.method == 'POST':
        data = request.get_json()
        new_todo = data.get('text')
        if new_todo:
            todos.append(new_todo)
            return jsonify(todos), 201
        return jsonify({'error': 'Todo text is required'}), 400
    else:
        return jsonify(todos)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

