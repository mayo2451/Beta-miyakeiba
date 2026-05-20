from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import connect_db, User  # app.pyから必要な部品をインポート
import sqlite3
from backup import backup_on_post, run_backup_async

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user_row = cur.fetchone()
        conn.close()

        if user_row and check_password_hash(user_row['password'], password):
            user_obj = User(user_row['id'], user_row['username'], user_row['role'])
            login_user(user_obj)
            return redirect(url_for('main.home'))
        else:
            flash('ユーザー名またはパスワードが間違っています。', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ログアウトしました。', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            flash('新しいパスワードと確認用パスワードが一致しません。', 'danger')
            return redirect(url_for('auth.change_password'))

        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE id = ?", (current_user.id,))
        row = cur.fetchone()

        if row and check_password_hash(row['password_hash'], current_password):
            new_hash = generate_password_hash(new_password)
            cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, current_user.id))
            conn.commit()
            conn.close()
            flash('パスワードを変更しました。', 'success')
            return redirect(url_for('main.home'))
        else:
            conn.close()
            flash('現在のパスワードが間違っています。', 'danger')
    return render_template('change_password.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        hashed_pw = generate_password_hash(password)

        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, hashed_pw, 'user'))
            backup_on_post()
            conn.commit()
        except sqlite3.IntegrityError:
            flash("ユーザー名は既に使われています")
            return redirect('/register')
        finally:
            conn.close()

        flash("登録に成功しました。ログインしてください。")
        run_backup_async()
        return redirect('/login')

    return render_template('register.html')