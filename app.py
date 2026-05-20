from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import calendar
from calendar import monthrange
import jpholiday
import sqlite3
import os
import gspread
from gspread.exceptions import SpreadsheetNotFound, APIError 
from oauth2client.service_account import ServiceAccountCredentials
import time
import json
import hashlib
import threading
from datetime import datetime, date, timedelta
import pytz
import logging
import re
from werkzeug.exceptions import abort
from typing import List, Dict
from database import User, connect_db
from backup import start_backup_scheduler

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

app.secret_key = 'your_secret_key'
app.config.update(SESSION_COOKIE_NAME='miyakeiba_session')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'  # 💡Blueprint化に合わせて変更

@login_manager.user_loader
def load_user(user_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user_row = cur.fetchone()
    conn.close()
    if user_row:
        return User(user_row['id'], user_row['username'], user_row['role'])
    return None

# ==========================================
# 💡 ここで新しく作った全ての Blueprint を登録します
# ==========================================
from blueprints.main import main_bp
from blueprints.auth import auth_bp
from blueprints.race import race_bp
from blueprints.user import user_bp

app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(race_bp)
app.register_blueprint(user_bp)

if __name__ == '__main__':
    start_backup_scheduler()
    app.run(host='192.168.1.8', port=5000, debug=True)