# init_db.py

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# 这是一个独立的脚本，所以我们需要创建一个临时的 Flask app 实例
# 来配置数据库连接，但我们不会运行这个 app。

app = Flask(__name__)

# --- 关键部分：和 app.py 中的数据库配置完全一致 ---
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    raise ValueError("DATABASE_URL environment variable is not set!")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# ----------------------------------------------------

# 初始化 db 对象，但这次是关联到我们临时的 app
db = SQLAlchemy(app)

# --- 关键部分：从 app.py 中复制 User 模型定义 ---
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
# ----------------------------------------------------

def create_tables():
    # 使用 app_context 来确保 SQLAlchemy 有正确的应用上下文
    with app.app_context():
        print("正在创建数据库表...")
        # db.create_all() 会创建所有继承自 db.Model 的模型对应的表
        db.create_all()
        print("数据库表创建成功！")

if __name__ == '__main__':
    create_tables()
