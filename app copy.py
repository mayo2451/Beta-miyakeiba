from flask import Flask,render_template,request,redirect, session, url_for, flash # type: ignore
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash # type: ignore
import calendar
from calendar import monthrange
import jpholiday # type: ignore
import sqlite3
import os
import gspread # type: ignore
from gspread.exceptions import SpreadsheetNotFound, APIError 
from oauth2client.service_account import ServiceAccountCredentials # type: ignore
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

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

SHEET_NAME = "miyakeiba_backup"
TABLES = ['race_entries', 'race_result', 'race_schedule', 'raise_horse', 'sqlite_sequence', 'users']
BACKUP_INTERVAL = 600
DB_NAME = "miyakeiba_app.db"
SKIP_STARTUP_BACKUP = os.getenv("SKIP_STARTUP_BACKUP", "false").lower() == "true"
app.secret_key = 'your_secret_key'
app.config.update(
    SESSION_COOKIE_SECURE=True,   # HTTPS を使う場合
    SESSION_COOKIE_HTTPONLY=True, # JS からアクセスできないように
    SESSION_COOKIE_SAMESITE='Lax' # POST リクエストでも送信されるように
)
JAPANESE_WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
JST = pytz.timezone('Asia/Tokyo')
#test_match = [24,25,26,27,28,29,30,31,32,33,34,35,36,37,38]
#placeholders= ', '.join('?' for _ in test_match)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 
login_manager.remember_cookie_duration = timedelta(days=30)

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role
    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (int(user_id),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return User(row['id'], row['username'], row['role'])
    return None
    

def get_sheet_client():
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

def load_backup_from_sheet():
    print("📥 スプレッドシートからバックアップを読み込み中...")
    sheet = get_sheet_client()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    for table in TABLES:
        try:
            print(f"📄 テーブル `{table}` を読み込み中...")
            worksheet = sheet.worksheet(table)
            data = worksheet.get_all_values()

            if not data or len(data) < 2:
                print(f"⚠️ `{table}` にデータがありません。スキップします。")
                continue

            columns = data[0]
            rows = data[1:]

            placeholders = ', '.join(['?'] * len(columns))
            columns_joined = ', '.join(columns)

            cursor.execute(f"DELETE FROM {table}")
            cursor.executemany(
                f"INSERT INTO {table} ({columns_joined}) VALUES ({placeholders})", rows
            )
            print(f"✅ `{table}` 読み込み完了")
        except Exception as e:
            print(f"❌ エラー（{table}）: {e}")
            continue

    conn.commit()
    conn.close()
    print("✅ 全テーブルの読み込み完了")
    
load_backup_from_sheet()

def get_last_backup_time():
    try:
        sheet = get_sheet_client()
        worksheet = sheet.worksheet("timestamp")
        value = worksheet.acell('A1').value
        return float(value) if value else 0.0
    except Exception as e:
        print(f"⚠️ タイムスタンプ取得エラー: {e}")
        return 0.0
        
def update_backup_time():
    try:
        sheet = get_sheet_client()
        worksheet = sheet.worksheet("timestamp")
        now = str(time.time())
        worksheet.update_acell('A1', now)
    except Exception as e:
        print(f"⚠️ タイムスタンプ更新エラー: {e}")

# バックアップ中かどうかのフラグ（グローバル）
is_backup_running = False
def backup_all_tables():
    global is_backup_running

    if is_backup_running:
        print("⚠️ バックアップはすでに実行中です。スキップします。")
        return

    is_backup_running = True
    print(f"✅ バックアップ開始...（{datetime.now()}）")

    try:
        sheet = get_sheet_client()  # ← あなたのGoogle Sheets認証関数
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        for table in TABLES:
            try:
                print(f"📄 テーブル `{table}` の処理中...")
                worksheet = sheet.worksheet(table)

                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description]

                worksheet.clear()
                data = [column_names] + [list(row) for row in rows]
                worksheet.update('A1', data)

            except Exception as e:
                print(f"⚠️ エラー（{table}）: {e}")
                continue

        update_backup_time()
        print(f"✅ バックアップ完了（{datetime.now()}）")

    except Exception as e:
        print(f"❌ バックアップ全体エラー: {e}")

    finally:
        is_backup_running = False
        if conn:
            conn.close()

def run_backup_async():
    thread = threading.Thread(target=backup_all_tables)
    thread.start()
                
def startup_backup_check():
    if SKIP_STARTUP_BACKUP:
        print("🚫 起動時のバックアップはスキップされました。")
        return
    if time.time() - get_last_backup_time() >= BACKUP_INTERVAL:
        run_backup_async()

startup_backup_check()

def backup_on_post(force=False):
    if force or (time.time() - get_last_backup_time() >= BACKUP_INTERVAL):
        run_backup_async()

def connect_db():
    conn = sqlite3.connect('miyakeiba_app.db')
    conn.row_factory = sqlite3.Row
    return conn

def hash_passward(password):
    return hashlib.sha256(passward.encode()).hexdigest()

def set_inistial_passwords(conn):
    cursor = conn.cursor()
    users = cursor.execute("SELECT id FROM users").fetchall()
    for user in users:
        user_id = user[0]
        initial_password = hash_password(f"user{user_id}")
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", (initial_password, user_id))
    conn.commit()

class HolidayCalendar(calendar.HTMLCalendar):
    def __init__(self, race_schedule_str=None, firstweekday=0):
        super().__init__(firstweekday)
        self.year = None
        self.month = None

        if race_schedule_str is not None:
            self.race_schedule = self._prepare_race_schedule(race_schedule_str)
        else:
            self.race_schedule = {}

    def _prepare_race_schedule(self, race_data_str: Dict[str, str]) -> Dict[date, str]:
        prepared_schedule = {}
        for date_str, race_name in race_data_str.items():
            try:
                year, month, day = map(int, date_str.split('-'))
                date_obj = date(year, month, day)
                prepared_schedule[date_obj] = race_name
            except ValueError as e:
                print(f"警告: 不正な日付形式をスキップしました: {date_str} ({e})")
                continue
        return prepared_schedule
        
    def formatmonth(self, year, month, withyear=True):
        self.year = year
        self.month = month
        weeks = self.monthdays2calendar(year, month)

        html = []
        html.append('<table class="calendar-table">')  # ← ここでクラス付与
        html.append('\n' + self.formatmonthname(year, month, withyear=withyear))
        html.append('\n' + self.formatweekheader())

        for week in weeks:
            html.append('\n' + self.formatweek(week))

        html.append('\n</table>')
        return ''.join(html)
    
    def formatday(self, day, weekday):
        if day == 0:
            return '<td class="noday">&nbsp;</td>'
        
        current_date = date(self.year, self.month, day)
        today = date.today()
        is_holiday = jpholiday.is_holiday(current_date)
        race_name = self.race_schedule.get(current_date)

        classes = ['weekday']
        if weekday == 5:
            classes.append('sat')
        elif weekday == 6:
            classes.append('sun')
        if is_holiday:
            classes.append('holiday')
        if current_date == today:
            classes.append('today')
        if race_name:
            classes.append('race-day')

        class_str = ' '.join(classes)

        day_content = f'<span class="day-number">{day}</span>'

        if race_name:
            day_content += f'<div class="race-name">{race_name}</div>'
        return f'<td class="{class_str}">{day_content}</td>'

def get_all_race_data_from_db() -> List[Dict[str, str]]:
    conn = None
    race_data_list = []

    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT race_date, race_name FROM race_schedule ORDER BY race_date ASC"
        cursor.execute(query)
        rows = cursor.fetchall()
        
        for row in rows:
            race_data_list.append({
                "race_date": row["race_date"],
                "race_name": row["race_name"]
            })
            
    except sqlite3.Error as e:
        print(f"SQLiteエラーが発生しました: {e}")
        return []
    finally:
        if conn:
            conn.close()
            
    return race_data_list

def prepare_race_schedule(race_data_list: List[Dict[str, str]]) -> Dict[str, str]:
    race_schedule_str = {}
    for item in race_data_list:
        race_date = item.get('race_date')
        race_name = item.get('race_name')

        if race_date and race_name:
            if race_date in race_schedule_str:
                race_schedule_str[race_date] += f"<br>{race_name}"
            else:
                race_schedule_str[race_date] = race_name
                
    return race_schedule_str

def get_events_for_month(year, month):
    conn = connect_db()
    cursor = conn.cursor()
    
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1)
    else:
        last_day = date(year, month + 1, 1)

    first_day_str = first_day.strftime("%Y-%m-%d")
    last_day_str = last_day.strftime("%Y-%m-%d")

    query = """
        SELECT id, race_date, race_place, race_ground, race_distance, race_number, race_grade, race_name, start_time
        FROM race_schedule
        WHERE race_date BETWEEN ? AND ?
        ORDER BY race_date ASC, start_time ASC
    """

    cursor.execute(query, (first_day_str, last_day_str))
    rows = cursor.fetchall()
    conn.close()

    events = []
    for row in rows:
        date_str = row['race_date']

        # 月日形式の加工（例：07/15）
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        weekday_jpn = JAPANESE_WEEKDAYS[date_obj.weekday()]
        display_date = date_obj.strftime(f"%m/%d({weekday_jpn})")

        # この行は不要なので削除
        # if display_date not in events:
        #     events = []

        events.append({
            'id': row['id'],
            'race_date': row['race_date'],
            'race_date_display': display_date,
            'race_place': row['race_place'],
            'race_ground': row['race_ground'],
            'race_distance': row['race_distance'],
            'race_number': row['race_number'],
            'race_grade': row['race_grade'],
            'race_name': row['race_name'],
            'start_time': row['start_time']
        })

    return events

def get_this_week_races():
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, race_date, race_name, race_place, race_ground, race_distance, race_grade
        FROM race_schedule
        WHERE race_date BETWEEN ? AND ?
        ORDER BY race_date, start_time
    """,(start_of_week.isoformat(), end_of_week.isoformat()))
    rows = cursor.fetchall()
    conn.close()
    formatted_races = []
    for row in rows:
        date_obj = datetime.strptime(row["race_date"], "%Y-%m-%d")
        weekday_jp = JAPANESE_WEEKDAYS[date_obj.weekday()]
        formatted_date = f"{date_obj.strftime('%m/%d')}（{weekday_jp}）"
        formatted_races.append({
            "id": row["id"],
            "race_date_display": formatted_date,
            "race_name": row["race_name"],
            "race_place": row["race_place"],
            "race_ground": row["race_ground"],
            "race_distance": row["race_distance"],
            "race_grade": row["race_grade"]
        })
    return formatted_races

@app.route('/')
def home():
    JST = pytz.timezone('Asia/Tokyo')
    today = datetime.now(JST).date()
    year = today.year
    month = today.month
    
    events = get_events_for_month(year, month)

    cal = HolidayCalendar(firstweekday=0)
    calendar_html = cal.formatmonth(year,month)

    prev_month = month - 1
    prev_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1

    next_month = month + 1
    next_year = year
    if next_month == 13:
        next_month = 1
        next_year += 1

    start_date = f"{year}-{month:02d}-01"
    end_day = monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{end_day}"

    conn = connect_db()
    cur = conn.cursor()
    if year == 2025 and month == 10:
        query = f"""
            SELECT
                u.id AS user_id,
                rh.username,
                SUM(rh.score) AS total_score,
                SUM(CASE WHEN rh.honmeiba_rank = 1 THEN 1 ELSE 0 END) AS first,
                SUM(CASE WHEN rh.honmeiba_rank = 2 THEN 1 ELSE 0 END) AS second,
                SUM(CASE WHEN rh.honmeiba_rank = 3 THEN 1 ELSE 0 END) AS third
            FROM raise_horse rh
            JOIN race_schedule rs ON rh.race_id = rs.id
            JOIN users u ON rh.username = u.username
            WHERE 
                /* 以下のいずれかを満たすレコードを集計対象とする */
                (
                    /* 1. 通常の集計対象期間内のレコード（除外リスト適用） */
                    rs.race_date BETWEEN ? AND ? 
                    AND rh.race_id NOT IN (24,25,26,27,28,29,30,31,32,33,34,35,36,37,38)
                )
                OR
                (
                    /* 2. 例外として、期間に関係なくレースID 2 を加算 */
                    rh.race_id = 2 
                )
            GROUP BY rh.username
            ORDER BY 
                total_score DESC,
                first DESC,
                second DESC,
                third DESC
            LIMIT 3
        """
        # プレースホルダはWHERE句の BETWEEN ? AND ? で使われる2個のみ
        cur.execute(query, (start_date, end_date))
    else:
        # 2025年10月以外の月は、通常の集計ロジック（レースID 2 は加算しない）
        query = f"""
            SELECT
                u.id AS user_id,
                rh.username,
                SUM(rh.score) AS total_score,
                SUM(CASE WHEN rh.honmeiba_rank = 1 THEN 1 ELSE 0 END) AS first,
                SUM(CASE WHEN rh.honmeiba_rank = 2 THEN 1 ELSE 0 END) AS second,
                SUM(CASE WHEN rh.honmeiba_rank = 3 THEN 1 ELSE 0 END) AS third
            FROM raise_horse rh
            JOIN race_schedule rs ON rh.race_id = rs.id
            JOIN users u ON rh.username = u.username
            WHERE rs.race_date BETWEEN ? AND ? AND rh.race_id NOT IN (24,25,26,27,28,29,30,31,32,33,34,35,36,37,38)
            GROUP BY rh.username
            ORDER BY 
                total_score DESC,
                first DESC,
                second DESC,
                third DESC
            LIMIT 3
        """
        cur.execute(query, (start_date, end_date))
    users = cur.fetchall()
    query_total = f"""
        SELECT
            u.id AS user_id,
            rh.username,
            SUM(rh.score) AS total_score,
            SUM(CASE WHEN rh.honmeiba_rank = 1 THEN 1 ELSE 0 END) AS first,
            SUM(CASE WHEN rh.honmeiba_rank = 2 THEN 1 ELSE 0 END) AS second,
            SUM(CASE WHEN rh.honmeiba_rank = 3 THEN 1 ELSE 0 END) AS third
        FROM raise_horse rh
        JOIN race_schedule rs ON rh.race_id = rs.id
        JOIN users u ON rh.username = u.username
        WHERE rh.race_id NOT IN (24,25,26,27,28,29,30,31,32,33,34,35,36,37,38)
        GROUP BY rh.username
        ORDER BY 
            total_score DESC,
            first DESC,
            second DESC,
            third DESC
        LIMIT 3
    """
    cur.execute(query_total)
    users_total = cur.fetchall()
    conn.close()

    races = get_this_week_races()
    
    return render_template(
        'home.html', 
        calendar_html=calendar_html, 
        year=year, 
        month=month,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        events=events,
        users=users,
        users_total=users_total,
        races=races)


@app.route('/insert_race', methods=['GET', 'POST'])
def insert_race():
    if request.method == 'POST':
        race_dates = request.form.getlist('race_date[]')
        race_places = request.form.getlist('race_place[]')
        race_ground = request.form.getlist('race_ground[]')
        race_distance = request.form.getlist('race_distance[]')
        race_numbers = request.form.getlist('race_number[]')
        race_grades = request.form.getlist('race_grade[]')
        race_names = request.form.getlist('race_name[]')
        start_times = request.form.getlist('start_time[]')

        conn = connect_db()
        cursor = conn.cursor()

        for i in range(len(race_dates)):
            cursor.execute("""
                INSERT INTO race_schedule (race_date, race_place, race_number, race_grade, race_name, start_time, race_ground, race_distance)
                VALUES (?,?,?,?,?,?,?,?)
            """,(
                race_dates[i],
                race_places[i],
                race_numbers[i] if race_numbers[i] else None,
                race_grades[i],
                race_names[i],
                start_times[i] if start_times[i] else None,
                race_ground[i],
                race_distance[i]
            ))

        conn.commit()
        conn.close()

        return redirect('/insert_race')
    
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, race_date, race_place, race_ground, race_distance, race_number, race_grade, race_name, start_time
        FROM race_schedule
        ORDER BY race_date DESC
    """)
    rows = cursor.fetchall()
    backup_on_post(force=True)
    conn.close()

    races = []
    for row in rows:
        races.append({
            "id": row['id'],
            "race_date": row['race_date'],
            "race_place": row['race_place'],
            "race_ground": row['race_ground'],
            "race_distance": row['race_distance'],
            "race_number": row['race_number'],
            "race_grade": row['race_grade'],
            "race_name": row['race_name'],
            "start_time": row['start_time']
        })
    
    races.sort(key=lambda x: x['race_date'], reverse=True)
    races = races[1:]

    return render_template('insert_race.html', races=races)

@app.route('/delete_race', methods=['POST'])
def delete_race():
    race_id = request.form.get('race_id')

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM race_schedule WHERE id = ?", (race_id,))
    conn.commit()
    backup_on_post(force=True)
    conn.close()

    return redirect('/insert_race')

@app.route('/login', methods=['GET', 'POST'])
def login():
    print("request.method:", request.method)
    print("request.form:", request.form)
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if not user:
            flash("ユーザーが見つかりません")
            return render_template('login.html')

        if user and check_password_hash(user['password'], password):
            print(User.__init__)
            # User オブジェクトを作る
            user_obj = User(user['id'], user['username'], user['role'])
            login_user(user_obj, remember=True)
            print("login_user 実行後:", current_user.is_authenticated)
            return redirect('/')
        else:
            flash("ユーザー名またはパスワードが違います")
            return render_template('login.html')

    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect('/')

@app.route('/register', methods=['GET', 'POST'])
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

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        user_id = current_user.id
        current_pw = request.form['current_password']
        new_pw = request.form['new_password']
        confirm_pw = request.form['confirm_password']

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("SELECT password FROM users WHERE id = ?", (user_id,))
        user_data = cursor.fetchone()

        if not user_data:
            conn.close()
            flash("ユーザー情報が見つかりません")
            return redirect(url_for('change_password'))

        hashed_current_pw = user_data['password']

        if not check_password_hash(hashed_current_pw, current_pw):
            conn.close()
            flash("現在のパスワードが間違っています")
            return redirect(url_for('change_password'))

        if new_pw != confirm_pw:
            conn.close()
            flash("新しいパスワードと確認用パスワードが一致しませんでした")
            return redirect(url_for('change_password'))

        new_hashed_pw = generate_password_hash(new_pw)

        try:
            cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_hashed_pw, user_id))
            backup_on_post()
            conn.commit()
            flash("パスワードが正常に変更されました")
            run_backup_async()
            return redirect(url_for('home'))
        except Exception as e:
            logging.error(f"パスワード更新エラー：{e}")
            flash("パスワードの更新中にエラーが発生しました")
        finally:
            conn.close()
    return render_template('change_password.html')

def save_to_sheet(sheet_name, race_id, horse_names):
    print(f"🔍 save_to_sheet 実行: {sheet_name}")
    sheet = get_sheet_client()
    worksheet = sheet.worksheet(sheet_name)

    try:
        existing_data = worksheet.get_all_values()
        current_max_id = 0
        if len(existing_data) > 1:
            try:
                current_max_id = max(int(row[0]) for row in existing_data[1:] if row and row[0].isdigit())
            except Exception as e:
                print(f"⚠️ IDの取得に失敗: {e}")
                current_max_id = 0
    except Exception as e:
        print(f"❌ スプレッドシートの取得エラー: {e}")
        return

    
    rows = []
    for i, name in enumerate(horse_names, start=1):
        name = name.strip()
        if name:
            current_max_id += 1
            print(f"📄 書き込み予定: id={current_max_id}, race_id={race_id}, number={i}, name={name}")
            rows.append([current_max_id, race_id, i, name])

    if rows:
        try:
            worksheet.append_rows(rows, value_input_option="USER_ENTERED")
            print("✅ 書き込み成功")
        except Exception as e:
            print(f"❌ append_rows でエラー: {e}")
    else:
        print("⚠️ 書き込む行がありません")

@app.route('/entry_form', methods=['GET', 'POST'])
def entry_form():
    if request.method == 'POST':
        race_id = request.form['race_id']
        mode = request.form.get('mode')
        horse_names = request.form.getlist('horse_name[]')

        try:
            sheet_name = "horseentrybefore" if mode == "before" else "race_entries"
            save_to_sheet(sheet_name, race_id, horse_names)
            if mode == 'before':
                flash("枠順確定前の出馬表をスプレッドシートに保存しました")
            else:
                flash("枠順確定後の出馬表をスプレッドシートに保存しました")
                
            return redirect('/entry_form')

        except Exception as e:
            flash(f"登録エラー: {e}")
            return redirect('/entry_form')

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, race_date, race_place, race_number, race_name
        FROM race_schedule
        ORDER BY race_date DESC
    """)
    races = cursor.fetchall()
    races = races[1:]  # 必要なら

    conn.close()

    return render_template('entry_form.html', races=races)

def get_friday_midnight(race_date_str):
    # race_date_str: 'YYYY-MM-DD' を datetime に変換
    race_date = datetime.strptime(race_date_str, "%Y-%m-%d")
    race_date = JST.localize(race_date)
    # レース日の週の月曜日を基準に取得（weekday(): 月曜0, 日曜6）
    weekday = race_date.weekday()
    monday = race_date - timedelta(days=weekday)
    
    # 金曜の24:00（= 土曜の0:00）
    friday_midnight = monday + timedelta(days=5)  # 月曜+5日 = 土曜
    friday_midnight = friday_midnight.replace(hour=0, minute=0, second=0, microsecond=0)
    
    return friday_midnight

def fetch_entries_from_sheet(race_id):
    try:
        sheet = get_sheet_client()
        worksheet = sheet.worksheet("horseentrybefore")
        all_rows = worksheet.get_all_values()
        
        # ヘッダーを除外
        rows = [row for row in all_rows[1:] if row[1] == str(race_id)]
        # データ整形
        entries = [{"horse_name": row[3]} for row in rows]
        return entries
    except Exception as e:
        print(f"❌ スプレッドシート取得エラー: {e}")
        return []

#@app.route('/entries/<int:race_id>', methods=['GET', 'POST'])
#def show_entries(race_id):
#    conn = connect_db()
#    cursor = conn.cursor()

    # レース情報取得
#    cursor.execute("SELECT id, race_date, race_place, race_name, start_time FROM race_schedule WHERE id = ?", (race_id,))
#    race = cursor.fetchone()

#    if not race:
#        conn.close()
#        flash("指定されたレースが見つかりません")
#        return redirect('/')

#    race = dict(race)
#    now = datetime.now(JST)

#    try:
#        race_datetime_str = f"{race['race_date']} {race['start_time']}"  # "YYYY-MM-DD HH:MM"
#        race_datetime = JST.localize(datetime.strptime(race_datetime_str, "%Y-%m-%d %H:%M"))
#        voting_deadline = race_datetime - timedelta(minutes=1)
#        cutoff_time = get_friday_midnight(race['race_date'])
#    except ValueError:
#        flash("レースの日時情報に誤りがあります。")
#        return redirect('/', current_path=request.path)

#    is_closed = now >= voting_deadline

    # POST処理（本命馬登録）
#    if request.method == 'POST':
#        honmeiba = request.form.get('honmeiba')
#        if honmeiba:
#            cursor.execute("""
#                INSERT INTO raise_horse(race_id, username, honmeiba)
#                VALUES(?,?,?)
#                ON CONFLICT(race_id, username) DO UPDATE SET honmeiba=excluded.honmeiba
#            """, (race_id, current_user.username, honmeiba))
#            backup_on_post()
#            conn.commit()

    # 出馬表取得
#    if now < cutoff_time:
#        entries = fetch_entries_from_sheet(race_id)
#        print("📄 出馬表（確定前）: Google Sheets から取得")
#    else:
#       cursor.execute("SELECT horse_name FROM race_entries WHERE race_id = ?", (race_id,))
#        rows = cursor.fetchall()
#        entries = [{"horse_name":row["horse_name"], "jockey": ""} for row in rows]
#        print("📄 出馬表（確定後）: データベースから取得")

#    cursor.execute("""
#        SELECT rh.username, rh.honmeiba, u.id AS user_id
#        FROM raise_horse rh
#        JOIN users u ON rh.username = u.username
#        WHERE rh.race_id = ?
#    """, (race_id,))
#    votes = cursor.fetchall()

#    vote_map = {}
#    user_map = {}
#    for row in votes:
#        uname = row['username']
#        horse = row['honmeiba']
#        uid = row['user_id']
#        user_map[uname] = uid
#        if horse not in vote_map:
#            vote_map[horse] = []
#        vote_map[horse].append(uname)

#    for entry in entries:
#        horse = entry["horse_name"]
#        entry["voted_by"] = [
#            {
#                "username": uname,
#                "image_url": f"https://raw.githubusercontent.com/mayo2451/miyakeiba/main/01miyakeiba%20-%20v1.1/Miyakeiba_app/image/user/{ user_map.get(uname) }/face.png"
#            }
#            for uname in vote_map.get(horse, [])
#        ]
#    
#    conn.close()

#    is_finalized = now >= cutoff_time
    
#    return render_template('entries.html', entries=entries, race=race, selected_race_id=race_id, is_closed=is_closed, is_finalized=is_finalized)

@app.route('/mypage')
@login_required
def mypage():
#   username = current_user.username
#   conn = connect_db()
#   cursor = conn.cursor()

    # 成績一覧データ（過去の参加レース）
#   cursor.execute("""
#       SELECT r.race_date, r.race_place, r.race_name, h.honmeiba, h.honmeiba_rank, h.score
#       FROM raise_horse h
#       JOIN race_schedule r ON h.race_id = r.id
#       WHERE h.username = ?
#       ORDER BY r.race_date DESC
#   """, (username,))
#   entries = cursor.fetchall()

    # 個人成績集計（横一列に表示する要約）
#   cursor.execute(f"""
#       SELECT
#           COUNT(*) AS total_races,
#           SUM(score) AS total_score,
#           SUM(CASE WHEN honmeiba_rank = 1 THEN 1 ELSE 0 END) AS first,
#           SUM(CASE WHEN honmeiba_rank = 2 THEN 1 ELSE 0 END) AS second,
#           SUM(CASE WHEN honmeiba_rank = 3 THEN 1 ELSE 0 END) AS third,
#           SUM(CASE WHEN honmeiba_rank BETWEEN 4 AND 5 THEN 1 ELSE 0 END) AS bbs,
#           SUM(CASE WHEN honmeiba_rank = 0 THEN 1 ELSE 0 END) AS out_of_place,
#           ROUND(AVG(CASE WHEN honmeiba_rank = 1 THEN 1.00 ELSE 0 END), 4) AS win_rate,
#           ROUND(AVG(CASE WHEN honmeiba_rank BETWEEN 1 AND 3 THEN 1.00 ELSE 0 END), 4) AS placing_bets_rate
#       FROM raise_horse
#       WHERE username = ? AND race_id NOT IN (24,25,26,27,28,29,30,31,32,33,34,35,36,37,38)
#   """, (username,))
#   row = cursor.fetchone()

#   conn.close()

#   user_stats = None
#   if row and row[0] > 0:
#       user_stats = {
#           "total_races": row[0],
#           "total_score": row[1],
#           "first": row[2],
#           "second": row[3],
#           "third": row[4],
#           "bbs": row[5],
#           "out_of_place": row[6],
#           "win_rate": row[7],
#           "placing_bets_rate": row[8],
#       }

    return redirect(url_for('user_profile', user_id=current_user.id))

@app.route('/user/<int:user_id>')
def user_profile(user_id):
    conn = connect_db()
    cursor = conn.cursor()
    # 1. ★★★ ターゲットユーザーの確認とユーザー名の取得 ★★★
    # IDに基づいてユーザー名を取得する (プロフィールページの上部に表示するため)
    cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    if not user_data:
        conn.close()
        # ユーザーIDが存在しない場合は404エラー
        abort(404) 
    username_to_query = user_data['username'] # DBから取得したユーザー名
    # 2. ★★★ 成績一覧データ（過去の参加レース）★★★
    # クエリはIDではなく、取得したユーザー名を使用 (raise_horse が username で管理されているため)
    cursor.execute("""
        SELECT r.race_date, r.race_place, r.race_name, h.honmeiba, h.honmeiba_rank, h.score
        FROM raise_horse h
        JOIN race_schedule r ON h.race_id = r.id
        WHERE h.username = ?
        ORDER BY r.race_date DESC
    """, (username_to_query,))
    entries = cursor.fetchall()
    # 3. ★★★ 個人成績集計（横一列に表示する要約）★★★
    cursor.execute("""
        SELECT
            COUNT(*) AS total_races,
            SUM(score) AS total_score,
            SUM(CASE WHEN honmeiba_rank = 1 THEN 1 ELSE 0 END) AS first,
            SUM(CASE WHEN honmeiba_rank = 2 THEN 1 ELSE 0 END) AS second,
            SUM(CASE WHEN honmeiba_rank = 3 THEN 1 ELSE 0 END) AS third,
            SUM(CASE WHEN honmeiba_rank BETWEEN 4 AND 5 THEN 1 ELSE 0 END) AS bbs,
            SUM(CASE WHEN honmeiba_rank = 0 THEN 1 ELSE 0 END) AS out_of_place,
            ROUND(AVG(CASE WHEN honmeiba_rank = 1 THEN 1.00 ELSE 0 END), 4) AS win_rate,
            ROUND(AVG(CASE WHEN honmeiba_rank BETWEEN 1 AND 3 THEN 1.00 ELSE 0 END), 4) AS placing_bets_rate
        FROM raise_horse
        WHERE username = ? AND race_id NOT IN (24,25,26,27,28,29,30,31,32,33,34,35,36,37,38)
    """, (username_to_query,))
    row = cursor.fetchone()
    user_stats = None
# 5. ★★★ 総合成績集計（NOT IN条件なし）の追加 ★★★
    cursor.execute("""
        SELECT
            COUNT(*) AS total_races,
            SUM(score) AS total_score,
            SUM(CASE WHEN honmeiba_rank = 1 THEN 1 ELSE 0 END) AS first,
            SUM(CASE WHEN honmeiba_rank = 2 THEN 1 ELSE 0 END) AS second,
            SUM(CASE WHEN honmeiba_rank = 3 THEN 1 ELSE 0 END) AS third,
            SUM(CASE WHEN honmeiba_rank BETWEEN 4 AND 5 THEN 1 ELSE 0 END) AS bbs,
            SUM(CASE WHEN honmeiba_rank = 0 THEN 1 ELSE 0 END) AS out_of_place,
            ROUND(AVG(CASE WHEN honmeiba_rank = 1 THEN 1.00 ELSE 0 END), 4) AS win_rate,
            ROUND(AVG(CASE WHEN honmeiba_rank BETWEEN 1 AND 3 THEN 1.00 ELSE 0 END), 4) AS placing_bets_rate
        FROM raise_horse
        WHERE username = ? AND race_id NOT IN (24,25,26,27,28,29,30,31,32,33,34,35,36,37,38)
    """, (username_to_query,))
    row_total = cursor.fetchone()

    total_stats = None
    if row_total and row_total['total_races'] and row_total['total_races'] > 0:
        total_stats = {
            "total_races": row_total['total_races'],
            "total_score": row_total['total_score'],
            "first": row_total['first'],
            "second": row_total['second'],
            "third": row_total['third'],
            "bbs": row_total['bbs'],
            "out_of_place": row_total['out_of_place'],
            "win_rate": row_total['win_rate'],
            "placing_bets_rate": row_total['placing_bets_rate'],
        }

    # 4. ログインユーザーかどうかの判定 (変更なし)
    is_current_user = current_user.is_authenticated and current_user.id == user_id
    
    conn.close()
    
    return render_template('mypage.html', 
                           username=username_to_query,
                           entries=entries,
                           user_stats_filtered=user_stats, # 名前を分かりやすく変更
                           total_stats=total_stats,       # 総合成績
                           is_current_user=is_current_user,
                           user_id=user_id)

@app.route('/result_input/<int:race_id>', methods=['GET', 'POST'])
def result_input(race_id):
    conn = connect_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        first_place = request.form.get('first_place')
        second_place = request.form.get('second_place')
        third_place = request.form.get('third_place')
        fourth_place = request.form.get('fourth_place')
        fifth_place = request.form.get('fifth_place')
        odds_first = request.form.get('odds_first')
        odds_second = request.form.get('odds_second')
        odds_third = request.form.get('odds_third')

        cursor.execute("""
            INSERT INTO race_result (
                race_id, first_place, second_place, third_place,
                fourth_place, fifth_place, odds_first, odds_second, odds_third
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(race_id) DO UPDATE SET
                first_place = excluded.first_place,
                second_place = excluded.second_place,
                third_place = excluded.third_place,
                fourth_place = excluded.fourth_place,
                fifth_place = excluded.fifth_place,
                odds_first = excluded.odds_first,
                odds_second = excluded.odds_second,
                odds_third = excluded.odds_third
        """, (
            race_id, first_place, second_place, third_place,
            fourth_place, fifth_place, odds_first, odds_second, odds_third
        ))

        update_scores(conn, race_id)

        backup_on_post(force=True)
        conn.commit()
        conn.close()
        flash("レース結果を登録しました")
        return redirect(url_for('show_race_page', race_id=race_id))

    # GETの場合はレース名を取得してフォーム表示
    cursor.execute("SELECT race_name FROM race_schedule WHERE id = ?", (race_id,))
    race = cursor.fetchone()
    cursor.execute("SELECT horse_name FROM race_entries WHERE race_id = ?", (race_id,))
    horses = [row['horse_name'] for row in cursor.fetchall()]
    conn.close()

    return render_template('insert_result.html', race=race, race_id=race_id, horses=horses)

# @app.route('/update_scores/<int:race_id>', methods=['POST'])
def update_scores(conn, race_id):
    cur = conn.cursor()

    # レース結果取得
    cur.execute("""
        SELECT first_place, second_place, third_place,
        fourth_place, fifth_place,
        odds_first, odds_second, odds_third
        FROM race_result WHERE race_id = ?
    """, (race_id,))
    res = cur.fetchone()
    if not res:
        flash("レース結果が未登録です")
        return
    result = dict(res)

    # 本命馬提出データ取得
    cur.execute("""
        SELECT username, honmeiba FROM raise_horse WHERE race_id = ?
    """, (race_id,))
    rows = cur.fetchall()

    for username, honmeiba in rows:
        rank = 0
        odds = None
        score = 0

        if honmeiba == result['first_place']:
            rank = 1
            odds = result['odds_first']
            score = round(odds * 10)
        elif honmeiba == result['second_place']:
            rank = 2
            odds = result['odds_second']
            score = round(odds * 3)
        elif honmeiba == result['third_place']:
            rank = 3
            odds = result['odds_third']
            score = round(odds * 1)
        elif honmeiba == result['fourth_place']:
            rank = 4
        elif honmeiba == result['fifth_place']:
            rank = 5

        cur.execute("""
            UPDATE raise_horse
            SET honmeiba_rank = ?, honmeiba_odds = ?, score = ?
            WHERE race_id = ? AND username = ?
        """, (rank, odds, score, race_id, username))

        if rank == 1:
            cur.execute("UPDATE users set first = first + 1, score = score + ? WHERE username = ?", (score, username))
        elif rank == 2:
            cur.execute("UPDATE users SET second = second + 1, score = score + ? WHERE username = ?", (score, username))
        elif rank == 3:
            cur.execute("UPDATE users SET third = third + 1, score = score + ? WHERE username = ?", (score, username))
        elif rank in [4, 5]:
            cur.execute("UPDATE users SET bbs = bbs + 1 WHERE username = ?", (username,))
        else:
            cur.execute("UPDATE users SET out_of_place = out_of_place + 1 WHERE username = ?", (username,))
    
    cur.execute("SELECT username, first, second, third FROM users")
    for user in cur.fetchall():
        username = user["username"]
        first = int(user["first"])
        second = int(user["second"])
        third = int(user["third"])

        # raise_horseから提出回数を取得
        cur.execute("SELECT COUNT(*) FROM raise_horse WHERE username = ?", (username,))
        total_entries = cur.fetchone()[0]

        if total_entries > 0:
            win_rate = first / total_entries
            placing_rate = (first + second + third) / total_entries
        else:
            win_rate = 0
            placing_rate = 0

        cur.execute("""
            UPDATE users
            SET win_rate = ?, placing_bets_rate = ?
            WHERE username = ?
        """, (win_rate, placing_rate, username))

    backup_on_post()
    conn.commit()
    flash("得点とユーザー情報を更新しました")

#@app.route('/race_result/<int:race_id>', methods=['GET', 'POST'])
#def show_race_result(race_id):
#    conn = connect_db()
#    cur = conn.cursor()

    # GET時はフォーム表示のために馬一覧を渡す
#    cur.execute("SELECT horse_name FROM race_entries WHERE race_id = ?", (race_id,))
#    horses = [row['horse_name'] for row in cur.fetchall()]
#    cur.execute("SELECT * FROM race_result WHERE race_id = ?", (race_id,))
#    result_row = cur.fetchone()
#    result = dict(result_row) if result_row else {
#        'first_place': '',
#        'second_place': '',
#        'third_place': '',
#        'fourth_place': '',
#        'fifth_place': '',
#        'odds_first': '',
#        'odds_second': '',
#        'odds_third': ''
#    }
#    cur.execute("SELECT race_name FROM race_schedule WHERE id = ?", (race_id,))
#    race = cur.fetchone()
#    cur.execute("""SELECT username, honmeiba, score FROM raise_horse WHERE race_id = ?""", (race_id,))
#    scores = cur.fetchall()
#    sorted_scores = sorted(scores, key=lambda x: x['score'], reverse=True)
#    ranked_scores = []
#    prev_score = None
#    rank = 0
#    count = 0

#    for row in sorted_scores:
#        count += 1
#        if row['score'] != prev_score:
#            rank = count
#        ranked_scores.append({
#            'rank': rank,
#            'username': row['username'],
#            'honmeiba': row['honmeiba'],
#            'score': row['score']
#        })
#        prev_score = row['score']

#    cur.execute("""
#        SELECT rh.username, rh.honmeiba, u.id AS user_id
#        FROM raise_horse rh
#        JOIN users u ON rh.username = u.username
#        WHERE rh.race_id = ?
#    """, (race_id,))
#    votes = cur.fetchall()

#    vote_map = {}
#    for row in votes:
#        uname = row['username']
#        horse = row['honmeiba']
#        uid = row['user_id']
#        if horse not in vote_map:
#            vote_map[horse] = []
#        vote_map[horse].append({
#            "username": uname,
#            "image_url": f"https://raw.githubusercontent.com/mayo2451/miyakeiba/main/01miyakeiba%20-%20v1.1/Miyakeiba_app/image/user/{uid}/face.png"
#        })

#    if result.get('first_place'):
#        result['voted_by_first'] = vote_map.get(result['first_place'], [])
#    if result.get('second_place'):
#        result['voted_by_second'] = vote_map.get(result['second_place'], [])
#    if result.get('third_place'):
#        result['voted_by_third'] = vote_map.get(result['third_place'], [])
        
#    conn.close()

#    return render_template('race_result.html', race_id=race_id, horses=horses, race=race, result=result, scores=ranked_scores)
def get_video_url(race_id):
    try:
        sh = get_sheet_client()
        worksheet_name = 'race_video'
        try:
            worksheet = sh.worksheet(worksheet_name)
        except WorksheetNotFound:
            logging.error(f"シート名 '{worksheet_name}' が見つかりません。シート名を確認してください。")
            return None

        data = worksheet.get_all_records()

        for row in data:
            try:
                if int(row.get('id')) == race_id:
                    video_url = row.get('url')
                    if video_url:
                        logging.info(f"レースID {race_id} の動画URLが見つかりました: {video_url}")
                        return video_url
            except (ValueError, TypeError):
                continue

        logging.warning(f"レースID {race_id} に対応する動画URLがスプレッドシートに見つかりませんでした。")
        return None

    except SpreadsheetNotFound:
        logging.error(f"スプレッドシート名 '{SHEET_NAME}' が見つかりません。名前が正しいか確認してください。")
        return None
    except Exception as e:
        logging.error(f"Google Sheetsへのアクセス中にエラーが発生しました: {e}")
        return None

def extract_youtube_id(url):
    """
    YouTube URLから動画IDを抽出します。
    watch?v=xxx や youtu.be/xxx の両方に対応します。
    """
    youtube_regex = re.compile(
        r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    )
    match = youtube_regex.search(url)
    return match.group(1) if match else None

def save_honmeiba(race_id, username, honmeiba):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO raise_horse(race_id, username, honmeiba)
            VALUES(?,?,?)
            ON CONFLICT(race_id, username) DO UPDATE SET honmeiba=excluded.honmeiba
        """, (race_id, username, honmeiba))
        conn.commit()
        print(f"保存するデータ： { race_id },{ username },{ honmeiba }")
        return True
    except sqlite3.Error as e:
        print(f"データベースエラー： {e}")
        conn.rollback()
        return False

def get_waku_number(horse_number, total_entries):
    num = horse_number
    total = total_entries
    waku_num = 0
    if total == 18:
        if num in [1, 2]: waku_num = 1
        elif num in [3, 4]: waku_num = 2
        elif num in [5, 6]: waku_num = 3
        elif num in [7, 8]: waku_num = 4
        elif num in [9, 10]: waku_num = 5
        elif num in [11, 12]: waku_num = 6
        elif num in [13, 14, 15]: waku_num = 7
        elif num in [16, 17, 18]: waku_num = 8
    elif total == 17:
        if num in [1, 2]: waku_num = 1
        elif num in [3, 4]: waku_num = 2
        elif num in [5, 6]: waku_num = 3
        elif num in [7, 8]: waku_num = 4
        elif num in [9, 10]: waku_num = 5
        elif num in [11, 12]: waku_num = 6
        elif num in [13, 14]: waku_num = 7
        elif num in [15, 16, 17]: waku_num = 8
    elif total == 16:
        if num in [1, 2]: waku_num = 1
        elif num in [3, 4]: waku_num = 2
        elif num in [5, 6]: waku_num = 3
        elif num in [7, 8]: waku_num = 4
        elif num in [9, 10]: waku_num = 5
        elif num in [11, 12]: waku_num = 6
        elif num in [13, 14]: waku_num = 7
        elif num in [15, 16]: waku_num = 8
    elif total == 15:
        if num in [1]: waku_num = 1
        elif num in [2, 3]: waku_num = 2
        elif num in [4, 5]: waku_num = 3
        elif num in [6, 7]: waku_num = 4
        elif num in [8, 9]: waku_num = 5
        elif num in [10, 11]: waku_num = 6
        elif num in [12, 13]: waku_num = 7
        elif num in [14, 15]: waku_num = 8
    elif total == 14:
        if num in [1]: waku_num = 1
        elif num in [2]: waku_num = 2
        elif num in [3, 4]: waku_num = 3
        elif num in [5, 6]: waku_num = 4
        elif num in [7, 8]: waku_num = 5
        elif num in [9, 10]: waku_num = 6
        elif num in [11, 12]: waku_num = 7
        elif num in [13, 14]: waku_num = 8
    elif total == 13:
        if num in [1]: waku_num = 1
        elif num in [2]: waku_num = 2
        elif num in [3]: waku_num = 3
        elif num in [4, 5]: waku_num = 4
        elif num in [6, 7]: waku_num = 5
        elif num in [8, 9]: waku_num = 6
        elif num in [10, 11]: waku_num = 7
        elif num in [12, 13]: waku_num = 8
    elif total == 12:
        if num in [1]: waku_num = 1
        elif num in [2]: waku_num = 2
        elif num in [3]: waku_num = 3
        elif num in [4]: waku_num = 4
        elif num in [5, 6]: waku_num = 5
        elif num in [7, 8]: waku_num = 6
        elif num in [9, 10]: waku_num = 7
        elif num in [11, 12]: waku_num = 8
    elif total == 11:
        if num in [1]: waku_num = 1
        elif num in [2]: waku_num = 2
        elif num in [3]: waku_num = 3
        elif num in [4]: waku_num = 4
        elif num in [5]: waku_num = 5
        elif num in [6, 7]: waku_num = 6
        elif num in [8, 9]: waku_num = 7
        elif num in [10, 11]: waku_num = 8
    elif total == 10:
        if num in [1]: waku_num = 1
        elif num in [2]: waku_num = 2
        elif num in [3]: waku_num = 3
        elif num in [4]: waku_num = 4
        elif num in [5]: waku_num = 5
        elif num in [6]: waku_num = 6
        elif num in [7, 8]: waku_num = 7
        elif num in [9, 10]: waku_num = 8
    elif total == 9:
        if num in [1]: waku_num = 1
        elif num in [2]: waku_num = 2
        elif num in [3]: waku_num = 3
        elif num in [4]: waku_num = 4
        elif num in [5]: waku_num = 5
        elif num in [6]: waku_num = 6
        elif num in [7]: waku_num = 7
        elif num in [8, 9]: waku_num = 8
    elif total == 8 or total < 8: # 8頭以下の場合
        # 8頭以下は馬番 = 枠番
        waku_num = num
    
    # ロジックが見つからない場合や範囲外の場合は安全のため 1 を返す
    return waku_num if waku_num > 0 else 1

@app.route('/race/<int:race_id>', methods=['GET', 'POST'])
def show_race_page(race_id):
    conn = connect_db()
    cur = conn.cursor()
    entries = []

    cursor = conn.cursor()
    cursor.execute("SELECT id, race_date, race_place, race_grade, race_name, start_time, race_ground, race_distance FROM race_schedule WHERE id = ?", (race_id,))
    race = cursor.fetchone()
    if not race:
        conn.close()
        flash("指定されたレースが見つかりません")
        return redirect('/')
    race = dict(race)
    now = datetime.now(JST)
    try:
        race_datetime_str = f"{race['race_date']} {race['start_time']}"
        race_datetime = JST.localize(datetime.strptime(race_datetime_str, "%Y-%m-%d %H:%M"))
        voting_deadline = race_datetime - timedelta(minutes=1)
        cutoff_time = get_friday_midnight(race['race_date'])
    except ValueError:
        flash("レースの日時情報に誤りがあります")
        return redirect('/', current_path=request.path)
    weekday_index = race_datetime.weekday()
    formatted_date = race_datetime.strftime("%m/%d")
    race['formatted_date'] = f"{formatted_date}({JAPANESE_WEEKDAYS[weekday_index]})"
    is_closed = now >= voting_deadline
    if request.method == 'POST':
        honmeiba = request.form.get('honmeiba')
        if honmeiba:
            if save_honmeiba(race_id, current_user.username, honmeiba):
                flash("本命馬の登録が完了しました！")
            else:
                flash("本命馬の登録に失敗しました。")
        else:
            flash("本命馬を選択してください。")
        # 保存後、同じレースページにリダイレクト
        return redirect(url_for('show_race_page', race_id=race_id))
    if now < cutoff_time:
        entries = fetch_entries_from_sheet(race_id)
        print("📄 出馬表（確定前）: Google Sheets から取得")
    else:
        cursor.execute("SELECT horse_name FROM race_entries WHERE race_id = ?", (race_id,))
        rows = cursor.fetchall()
        entries = [{"horse_name":row["horse_name"], "jockey": ""} for row in rows]
        print("📄 出馬表（確定後）: データベースから取得")
    cursor.execute("""
        SELECT rh.username, rh.honmeiba, u.id AS user_id
        FROM raise_horse rh
        JOIN users u ON rh.username = u.username
        WHERE rh.race_id = ?
    """, (race_id,))
    votes = cursor.fetchall()
    vote_map = {}
    user_map = {}
    horse = None
    for row in votes:
        uname = row['username']
        horse = row['honmeiba']
        uid = row['user_id']
        user_map[uname] = uid
        if horse not in vote_map:
            vote_map[horse] = []
        vote_map[horse].append(uname)
    is_finalized = now >= cutoff_time
    if is_closed:
        is_finalized = True
    total_entries = len(entries)
    for i, entry in enumerate(entries):
        horse = entry["horse_name"]
        horse_number = i + 1
        if total_entries <= 8:
            waku_number = horse_number
        else:
            waku_number = get_waku_number(horse_number, total_entries)
        voted_users = vote_map.get(horse, [])
        if not voted_users:
            if is_finalized:
                waku_icon_url = f"https://raw.githubusercontent.com/mayo2451/Beta-miyakeiba/main/miyakeiba-beta/image/icon/dummy_waku{waku_number}.png"
            else:
                waku_icon_url = f"https://raw.githubusercontent.com/mayo2451/Beta-miyakeiba/main/miyakeiba-beta/image/icon/dummy.png"
            entry["voted_by"] = [
                {
                    "username": "dummy",
                    "image_url": waku_icon_url
                }
            ]
        else:
            entry["voted_by"] = [
                {
                    "username": uname,
                    "image_url": f"https://raw.githubusercontent.com/mayo2451/Beta-miyakeiba/main/miyakeiba-beta/image/user/{ user_map.get(uname) }/face.png"
                }
                for uname in voted_users
            ]
    cur.execute("SELECT horse_name FROM race_entries WHERE race_id = ?", (race_id,))
    horses = [row['horse_name'] for row in cur.fetchall()]
    cur.execute("SELECT * FROM race_result WHERE race_id = ?", (race_id,))
    result_row = cur.fetchone()
    result = dict(result_row) if result_row else {
        'first_place': '', 'second_place': '', 'third_place': '', 'fourth_place': '', 'fifth_place': '',
        'odds_first': '', 'odds_second': '', 'odds_third': ''
    }
    is_started = now >= race_datetime
    has_result = result_row and result.get('first_place')
    first_place_score = 0
    second_place_score = 0
    third_place_score = 0
    if result.get('first_place') and result.get('odds_first'):
        try:
            first_place_score = round(float(result['odds_first']) * 10)
        except (ValueError, TypeError):
            logging.error(f"オッズ(1着)の形式が不正です: {result['odds_first']}")
            first_place_score = 0
    if result.get('second_place') and result.get('odds_second'):
        try:
            second_place_score = round(float(result['odds_second']) * 3)
        except (ValueError, TypeError):
            logging.error(f"オッズ(2着)の形式が不正です: {result['odds_second']}")
            second_place_score = 0
    if result.get('third_place') and result.get('odds_third'):
        try:
            third_place_score = round(float(result['odds_third']) * 1)
        except (ValueError, TypeError):
            logging.error(f"オッズ(3着)の形式が不正です: {result['odds_third']}")
            third_place_score = 0
            
    if is_finalized and result.get('first_place'):
        cur.execute("SELECT username, honmeiba FROM raise_horse WHERE race_id = ?", (race_id,))
        user_predictions = cur.fetchall()

        for prediction in user_predictions:
            username = prediction['username']
            predicted_horse = prediction['honmeiba']
            score = 0

            if predicted_horse == result['first_place']:
                score = first_place_score
            elif predicted_horse == result['second_place']:
                score = second_place_score
            elif predicted_horse == result['third_place']:
                score = third_place_score

            cur.execute("""
                UPDATE raise_horse
                SET score = ?
                WHERE race_id = ? AND username = ?
            """, (score, race_id, username))
        conn.commit()

    cur.execute("SELECT race_name FROM race_schedule WHERE id = ?", (race_id,))
    race_info = cur.fetchone()
    cur.execute("""SELECT username, honmeiba, score FROM raise_horse WHERE race_id = ?""", (race_id,))
    scores = cur.fetchall()
    sorted_scores = sorted(scores, key=lambda x: x['score'], reverse=True)
    ranked_scores = []
    prev_score = None
    rank = 0
    count = 0
    for row in sorted_scores:
        count += 1
        if row['score'] != prev_score:
            rank = count
        ranked_scores.append({
            'rank': rank,
            'username': row['username'],
            'honmeiba': row['honmeiba'],
            'score' : row['score']
        })
        prev_score = row['score']
    cur.execute("""
        SELECT rh.username, rh.honmeiba, u.id AS user_id
        FROM raise_horse rh
        JOIN users u ON rh.username = u.username
        WHERE rh.race_id = ?
    """, (race_id,))
    votes_result = cur.fetchall()
    vote_map_result = {}
    for row in votes_result:
        uname = row['username']
        horse = row['honmeiba']
        uid = row['user_id']
        if horse not in vote_map_result:
            vote_map_result[horse] = []
        vote_map_result[horse].append({
            "username": uname,
            "image_url": f"https://raw.githubusercontent.com/mayo2451/Beta-miyakeiba/main/miyakeiba-beta/image/user/{uid}/face.png"
        })
    result['voted_by_first'] = vote_map_result.get(result.get('first_place'), [])
    if not result['voted_by_first']:
        result['voted_by_first'].append({
            "username": "dummy",
            "image_url": "https://raw.githubusercontent.com/mayo2451/Beta-miyakeiba/main/miyakeiba-beta/image/icon/dummy.png"
        })

    result['voted_by_second'] = vote_map_result.get(result.get('second_place'), [])
    if not result['voted_by_second']:
        result['voted_by_second'].append({
            "username": "dummy",
            "image_url": "https://raw.githubusercontent.com/mayo2451/Beta-miyakeiba/main/miyakeiba-beta/image/icon/dummy.png"
        })

    result['voted_by_third'] = vote_map_result.get(result.get('third_place'), [])
    if not result['voted_by_third']:
        result['voted_by_third'].append({
            "username": "dummy",
            "image_url": "https://raw.githubusercontent.com/mayo2451/Beta-miyakeiba/main/miyakeiba-beta/image/icon/dummy.png"
        })
        
    result['voted_by_fourth'] = vote_map_result.get(result.get('fourth_place'), [])
    if not result['voted_by_fourth']:
        result['voted_by_fourth'].append({
            "username": "dummy",
            "image_url": "https://raw.githubusercontent.com/mayo2451/Beta-miyakeiba/main/miyakeiba-beta/image/icon/dummy.png"
        })

    result['voted_by_fifth'] = vote_map_result.get(result.get('fifth_place'), [])
    if not result['voted_by_fifth']:
        result['voted_by_fifth'].append({
            "username": "dummy",
            "image_url": "https://raw.githubusercontent.com/mayo2451/Beta-miyakeiba/main/miyakeiba-beta/image/icon/dummy.png"
        })
    video_url = get_video_url(race_id)
    #video_url = "https://www.youtube.com/watch?v=R9R63qB3j8k" # ★テスト用★
    logging.info(f"取得した動画URL: {video_url}")  # ★追加★
    video_id = None
    if video_url:
        video_id = extract_youtube_id(video_url)
    logging.info(f"抽出した動画ID: {video_id}")  # ★追加★

    conn.close()

    view_mode = request.args.get('view', 'entries')

    return render_template('race.html',
                           race_id=race_id,
                           entries=entries,
                           race=race,
                           selected_race_id=race_id,
                           is_closed=is_closed,
                           is_finalized=is_finalized,
                           horse=horse,
                           result=result,
                           first_place_score=first_place_score,
                           second_place_score=second_place_score,
                           third_place_score=third_place_score,
                           scores=ranked_scores,
                           video_id=video_id,
                           view=view_mode,
                           is_started=is_started,
                           has_result=has_result
                          )

@app.route('/allusers')
def allusers():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT race_grade FROM race_schedule ORDER BY race_grade")
    grades = [row[0] for row in cur.fetchall() if row[0] not in ('race_grade',)]
    
    cur.execute("SELECT DISTINCT race_place FROM race_schedule ORDER BY race_place")
    places = [row[0] for row in cur.fetchall() if row[0] not in ('race_place',)]

    cur.execute("""
        SELECT
            rh.username,
            u.id AS user_id,
            COUNT(*) AS total_races,
            SUM(rh.score) AS total_score,
            SUM(CASE WHEN honmeiba_rank = 1 THEN 1 ELSE 0 END) AS first,
            SUM(CASE WHEN honmeiba_rank = 2 THEN 1 ELSE 0 END) AS second,
            SUM(CASE WHEN honmeiba_rank = 3 THEN 1 ELSE 0 END) AS third,
            SUM(CASE WHEN honmeiba_rank BETWEEN 4 AND 5 THEN 1 ELSE 0 END) AS bbs,
            SUM(CASE WHEN honmeiba_rank = 0 THEN 1 ELSE 0 END) AS out_of_place,
            ROUND(AVG(CASE WHEN honmeiba_rank = 1 THEN 1.00 ELSE 0 END), 4) AS win_rate,
            ROUND(AVG(CASE WHEN honmeiba_rank BETWEEN 1 AND 3 THEN 1.00 ELSE 0 END), 4) AS placing_bets_rate
        FROM raise_horse rh
        JOIN race_schedule rs ON rh.race_id = rs.id
        JOIN users u ON rh.username = u.username
        WHERE rh.race_id NOT IN (24,25,26,27,28,29,30,31,32,33,34,35,36,37,38)
        GROUP BY rh.username, u.id
        ORDER BY total_score DESC
    """)
    users = cur.fetchall()
    conn.close()
    return render_template('alluserscore.html', all_users=users, grades=grades, places=places)

@app.route('/filtered_users')
def filtered_users():
    grade = request.args.get('race_type')  # e.g., G1
    venue = request.args.get('venue')      # e.g., 東京
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT race_grade FROM race_schedule ORDER BY race_grade")
    grades = [row[0] for row in cur.fetchall() if row[0] not in ('race_grade',)]
    
    cur.execute("SELECT DISTINCT race_place FROM race_schedule ORDER BY race_place")
    places = [row[0] for row in cur.fetchall() if row[0] not in ('race_place',)]

    all_query = """
        SELECT
            rh.username,
            u.id AS user_id,
            COUNT(*) AS total_races,
            SUM(rh.score) AS total_score,
            SUM(CASE WHEN honmeiba_rank = 1 THEN 1 ELSE 0 END) AS first,
            SUM(CASE WHEN honmeiba_rank = 2 THEN 1 ELSE 0 END) AS second,
            SUM(CASE WHEN honmeiba_rank = 3 THEN 1 ELSE 0 END) AS third,
            SUM(CASE WHEN honmeiba_rank BETWEEN 4 AND 5 THEN 1 ELSE 0 END) AS bbs,
            SUM(CASE WHEN honmeiba_rank = 0 THEN 1 ELSE 0 END) AS out_of_place,
            ROUND(AVG(CASE WHEN honmeiba_rank = 1 THEN 1.00 ELSE 0 END), 4) AS win_rate,
            ROUND(AVG(CASE WHEN honmeiba_rank BETWEEN 1 AND 3 THEN 1.00 ELSE 0 END), 4) AS placing_bets_rate
        FROM raise_horse rh
        JOIN race_schedule rs ON rh.race_id = rs.id
        JOIN users u ON rh.username = u.username
        WHERE rh.race_id NOT IN (24,25,26,27,28,29,30,31,32,33,34,35,36,37,38)
        GROUP BY rh.username, u.id
        ORDER BY total_score DESC
    """
    cur.execute(all_query)
    all_users = cur.fetchall()

    filtered_query = """
        SELECT
            rh.username,
            u.id AS user_id,
            COUNT(*) AS total_races,
            SUM(rh.score) AS total_score,
            SUM(CASE WHEN honmeiba_rank = 1 THEN 1 ELSE 0 END) AS first,
            SUM(CASE WHEN honmeiba_rank = 2 THEN 1 ELSE 0 END) AS second,
            SUM(CASE WHEN honmeiba_rank = 3 THEN 1 ELSE 0 END) AS third,
            SUM(CASE WHEN honmeiba_rank BETWEEN 4 AND 5 THEN 1 ELSE 0 END) AS bbs,
            SUM(CASE WHEN honmeiba_rank = 0 THEN 1 ELSE 0 END) AS out_of_place,
            ROUND(AVG(CASE WHEN honmeiba_rank = 1 THEN 1.00 ELSE 0 END), 4) AS win_rate,
            ROUND(AVG(CASE WHEN honmeiba_rank BETWEEN 1 AND 3 THEN 1.00 ELSE 0 END), 4) AS placing_bets_rate
        FROM raise_horse rh
        JOIN race_schedule rs ON rh.race_id = rs.id
        JOIN users u ON rh.username = u.username
        WHERE rh.race_id NOT IN (24,25,26,27,28,29,30,31,32,33,34,35,36,37,38)
    """
    params = []
    if grade:
        filtered_query += " AND rs.race_grade = ?"
        params.append(grade)
    if venue:
        filtered_query += " AND rs.race_place = ?"
        params.append(venue)

    if start_date:
        filtered_query += " AND rs.race_date >= ?"
        params.append(start_date)

    if end_date:
        filtered_query += " AND rs.race_date <= ?"
        params.append(end_date)

    filtered_query += " GROUP BY rh.username, u.id ORDER BY total_score DESC"

    cur.execute(filtered_query, params)
    filtered_users = cur.fetchall()
    conn.close()

    return render_template(
        'alluserscore.html', 
        all_users=all_users, 
        filtered_users=filtered_users, 
        grades=grades, 
        places=places,
        start_date=start_date,
        end_date=end_date
    )

def group_events_by_date(events):
    grouped = {}
    for event in events:
        race_date = event['race_date']
        if race_date not in grouped:
            grouped[race_date] = []
        grouped[race_date].append(event)
    sorted_grouped = sorted(grouped.items())
    return sorted_grouped

@app.route('/schedule')
def schedule():
    JST = pytz.timezone('Asia/Tokyo')
    today = datetime.now(JST).date()
    year_today = today.year
    month_today = today.month
    
    cal_year = request.args.get('year', default=year_today, type=int)
    cal_month = request.args.get('month', default=month_today, type=int)

    all_race_data_list = get_all_race_data_from_db()
    race_schedule_for_calendar = prepare_race_schedule(all_race_data_list)
    cal = HolidayCalendar(race_schedule_str=race_schedule_for_calendar, firstweekday=0)
    calendar_html = cal.formatmonth(cal_year, cal_month)
    calendar_events = get_events_for_month(cal_year, cal_month)
    calendar_events_sorted = group_events_by_date(calendar_events)
    this_month_events = get_events_for_month(year_today, month_today)
    this_month_events_sorted = group_events_by_date(this_month_events)
    races = get_this_week_races()

    prev_month = cal_month - 1
    prev_year = cal_year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1

    next_month = cal_month + 1
    next_year = cal_year
    if next_month == 13:
        next_month = 1
        next_year += 1

    return render_template(
        'schedule.html',
        races = races,
        this_month_events = this_month_events_sorted,
        calendar_events = calendar_events_sorted,
        calendar_html = calendar_html,
        year = cal_year,
        month = cal_month,
        prev_year = prev_year,
        prev_month = prev_month,
        next_year = next_year,
        next_month = next_month
    )

if __name__ == '__main__':
    app.run(debug=False)














































































































