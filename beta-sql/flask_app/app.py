from flask import Flask, render_template, request, redirect, url_for # type: ignore
import sqlite3
import os

app = Flask(__name__)
DB_NAME = "notes.db"

# 初回のみ：DBの初期化
def init_db():
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

# トップページ（メモ一覧）
@app.route('/')
def index():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM notes ORDER BY id DESC')
    notes = c.fetchall()
    conn.close()
    return render_template('index.html', notes=notes)

# 新規メモの追加ページ
@app.route('/add', methods=['GET', 'POST'])
def add_note():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('INSERT INTO notes (title, content) VALUES (?, ?)', (title, content))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('add_note.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
