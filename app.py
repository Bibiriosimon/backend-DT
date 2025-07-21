# app.py

import os # 导入 os 模块来读取环境变量
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy # 导入 SQLAlchemy

# 1. 初始化 app
app = Flask(__name__)
CORS(app) # 允许跨域请求

# 2. 配置数据库
#    从环境变量中获取数据库连接 URL
#    os.environ.get('DATABASE_URL') 是关键，它会读取我们在 Render 上设置的环境变量
#    我们还需要对 Render 提供的 URL 做一点小小的修改，因为它以 postgres:// 开头，
#    而 SQLAlchemy 新版本推荐使用 postgresql://
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # 关闭一个不必要的特性，节省资源

# 3. 初始化 SQLAlchemy 对象
db = SQLAlchemy(app)

# 4. 定义数据模型 (Model) - 这就是我们的第一张表！
#    我们会创建一个 User 模型，用来存储用户信息
class User(db.Model):
    __tablename__ = 'users' # 自定义表名，可选
    id = db.Column(db.Integer, primary_key=True) # 用户ID，主键
    username = db.Column(db.String(80), unique=True, nullable=False) # 用户名，唯一且不能为空
    password = db.Column(db.String(120), nullable=False) # 密码，不能为空（我们暂时先存明文）
    
    # 这个方法是为了方便地将对象转换成字典，以便返回 JSON
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username
            # 注意：我们不会在 to_dict 中返回密码！
        }

# -------------------- API 路由 --------------------

# 一个用于测试数据库连接的临时路由
@app.route('/test_db')
def test_db():
    try:
        # 尝试执行一个简单的查询
        # db.session.query(1) 会执行类似 SELECT 1 的SQL语句
        db.session.query(User).all() 
        return "数据库连接成功！User 表也已成功映射！"
    except Exception as e:
        # 如果有任何错误，打印出来，方便调试
        return f"数据库连接失败: {e}"

# 原有的 /api/todos 路由，我们暂时保留
todos = []
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

# -------------------- 数据库表创建 --------------------
# 这是一个非常重要的部分
# 我们需要一种方式来告诉 SQLAlchemy：“请根据我定义的 User 模型，去数据库里创建那张表”
# 下面的代码块实现了这个功能
with app.app_context():
    # 这会检查数据库中是否存在名为 'users' 的表
    # 如果不存在，它会根据上面定义的 User 类创建这张表
    db.create_all()


if __name__ == '__main__':
    # 注意：Render 会用 gunicorn 启动，不会直接运行这里。
    # 但为了本地测试方便，我们保留它。
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
