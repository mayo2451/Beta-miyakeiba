import os
import csv
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from database import connect_db, get_this_week_races  # app.pyから必要な部品をインポート
import pytz
import datetime
import sqlite3
import logging
from database import get_all_race_data_from_db, get_events_for_month, get_this_week_races, group_events_by_date, HolidayCalendar, prepare_race_schedule, JST, BACKUP_DIR, JAPANESE_WEEKDAYS
from backup import backup_on_post, generate_admin_csv, restore_table_from_csv
from datetime import timedelta

race_bp = Blueprint('race', __name__)

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

@race_bp.route('/race/<int:race_id>')
@login_required
def show_race(race_id):
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
    now = datetime.datetime.now(JST)
    try:
        race_datetime_str = f"{race['race_date']} {race['start_time']}"
        race_datetime = JST.localize(datetime.datetime.strptime(race_datetime_str, "%Y-%m-%d %H:%M"))
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
            "image_url": f"/static/image/user/{uid}/face.png"
        })
    result['voted_by_first'] = vote_map_result.get(result.get('first_place'), [])
    if not result['voted_by_first']:
        result['voted_by_first'].append({
            "username": "dummy",
            "image_url": "/static/image/icon/dummy.png"
        })

    result['voted_by_second'] = vote_map_result.get(result.get('second_place'), [])
    if not result['voted_by_second']:
        result['voted_by_second'].append({
            "username": "dummy",
            "image_url": "/static/image/icon/dummy.png"
        })

    result['voted_by_third'] = vote_map_result.get(result.get('third_place'), [])
    if not result['voted_by_third']:
        result['voted_by_third'].append({
            "username": "dummy",
            "image_url": "/static/image/icon/dummy.png"
        })
        
    result['voted_by_fourth'] = vote_map_result.get(result.get('fourth_place'), [])
    if not result['voted_by_fourth']:
        result['voted_by_fourth'].append({
            "username": "dummy",
            "image_url":"/static/image/icon/dummy.png"
        })

    result['voted_by_fifth'] = vote_map_result.get(result.get('fifth_place'), [])
    if not result['voted_by_fifth']:
        result['voted_by_fifth'].append({
            "username": "dummy",
            "image_url": "/static/image/icon/dummy.png"
        })
    #video_url = get_video_url(race_id)
    #video_url = "https://www.youtube.com/watch?v=R9R63qB3j8k" # ★テスト用★
    #logging.info(f"取得した動画URL: {video_url}")  # ★追加★
    #video_id = None
    #if video_url:
    #    video_id = extract_youtube_id(video_url)
    #logging.info(f"抽出した動画ID: {video_id}")  # ★追加★

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
                           #video_id=video_id,
                           view=view_mode,
                           is_started=is_started,
                           has_result=has_result
                          )

@race_bp.route('/race/<int:race_id>/video')
@login_required
def race_video(race_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM race_schedule WHERE id = ?", (race_id,))
    race = cur.fetchone()
    conn.close()
    if not race:
        abort(404)
    return render_template('race_video.html', race=race)

@race_bp.route('/this_week_races')
@login_required
def this_week_races_page():
    races = get_this_week_races()
    return render_template('ThisWeekRace.html', races=races)

@race_bp.route('/schedule')
def schedule():
    JST = pytz.timezone('Asia/Tokyo')
    today = datetime.datetime.now(JST).date()
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

@race_bp.route('/insert_race', methods=['GET', 'POST'])
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
        SELECT id, race_date, race_place, race_ground, race_distance, race_number, race_grade, race_name, start_time, is_selected
        FROM race_schedule
        ORDER BY race_date DESC
    """)
    rows = cursor.fetchall()
    backup_on_post()
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
            "start_time": row['start_time'],
            "is_selected": row['is_selected']
        })
    
    races.sort(key=lambda x: x['race_date'], reverse=True)
    #races = races[1:]

    return render_template('insert_race.html', races=races)

@race_bp.route('/save_schedule_races', methods=['POST'])
@login_required
def save_schedule_races():
    race_ids = request.form.getlist('race_id[]')
    race_dates = request.form.getlist('race_date[]')
    race_places = request.form.getlist('race_place[]')
    race_ground = request.form.getlist('race_ground[]')
    race_distance = request.form.getlist('race_distance[]')
    race_numbers = request.form.getlist('race_number[]')
    race_grades = request.form.getlist('race_grade[]')
    race_names = request.form.getlist('race_name[]')
    start_times = request.form.getlist('start_time[]')
    selected_ids = request.form.getlist('selected_ids[]')
    try:
        conn = connect_db()
        cursor = conn.cursor()
        for r_id, r_date, r_place, r_ground, r_dist, r_num, r_grade, r_name, r_time in zip(
            race_ids, race_dates, race_places, race_ground, race_distance, race_numbers, race_grades, race_names, start_times
        ):
            is_selected = 1 if str(r_id) in selected_ids else 0

            cursor.execute("""
                UPDATE race_schedule
                SET race_date = ?,
                    race_place= ?,
                    race_ground = ?,
                    race_distance = ?,
                    race_number = ?,
                    race_grade = ?,
                    race_name = ?,
                    start_time = ?,
                    is_selected = ?
                WHERE id = ?
            """, (
                r_date, 
                r_place, 
                r_ground, 
                r_dist, 
                r_num if r_num else None,
                r_grade, 
                r_name, 
                r_time if r_time else None,
                is_selected, 
                r_id
            ))

        conn.commit()

        cursor.execute("""
            SELECT id, race_date, race_place, race_ground, race_distance, race_number, race_grade, race_name, start_time, is_selected
            FROM race_schedule
            ORDER BY race_date DESC
        """)
        all_races = cursor.fetchall()
        conn.close()

        csv_path = os.path.join(BACKUP_DIR, "race_schedule.csv")
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["id", "race_date", "race_place", "race_ground", "race_distance", "race_number", "race_grade", "race_name", "start_time", "is_selected"])
            for row in all_races:
                writer.writerow([
                    row['id'], 
                    row['race_date'], 
                    row['race_place'], 
                    row['race_distance'],
                    row['race_number'], 
                    row['race_grade'], 
                    row['race_name'], 
                    row['start_time'], 
                    row['is_selected']
                ])
        flash("すべてのレース情報を一括更新しました")
        backup_on_post()
    except Exception as e:
        try: conn.close()
        except: pass
        flash(f"保存エラー:{e}")

    return redirect('/insert_race')

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

@race_bp.route('/result_input/<int:race_id>', methods=['GET', 'POST'])
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
        return redirect(url_for('race.show_race', race_id=race_id))

    # GETの場合はレース名を取得してフォーム表示
    cursor.execute("SELECT race_name FROM race_schedule WHERE id = ?", (race_id,))
    race = cursor.fetchone()
    cursor.execute("SELECT horse_name FROM race_entries WHERE race_id = ?", (race_id,))
    horses = [row['horse_name'] for row in cursor.fetchall()]
    conn.close()

    return render_template('insert_result.html', race=race, race_id=race_id, horses=horses)

@race_bp.route('/delete_race', methods=['POST'])
def delete_race():
    race_id = request.form.get('race_id')

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM race_schedule WHERE id = ?", (race_id,))
    conn.commit()
    backup_on_post()
    conn.close()

    return redirect('/insert_race')

@race_bp.route('/entry_form', methods=['GET', 'POST'])
@login_required
def entry_form():
    if request.method == 'POST':
        race_id = request.form['race_id']
        mode = request.form.get('mode')
        horse_names = request.form.getlist('horse_name[]')

        try:
            conn = connect_db()
            cursor = conn.cursor()

            if mode == 'before':
                table_name = "horseentrybefore"
                filename = "horseentrybefore"
                flash_msg = "枠順確定前の出馬表をDBに登録し、horseentrybefore.csvを更新しました"
            else:
                table_name = "race_entries"         # ➔ 枠順確定後のテーブル名
                filename = "race_entries.csv"      # ➔ 枠順確定後のCSV名
                flash_msg = "枠順確定後の出馬表をDBに登録し、race_entries.csvを更新しました"

            for idx, name in enumerate(horse_names):
                if name:  # 馬名が入力されていれば保存
                    horse_number = idx + 1  # ➔ 1行目は馬番1、2行目は馬番2...となる
                    
                    cursor.execute(f"""
                        INSERT INTO {table_name} (race_id, horse_number, horse_name)
                        VALUES (?, ?, ?)
                    """, (race_id, horse_number, name))
            
            conn.commit()

            # 2. SQLへの保存が成功した後、該当テーブルの最新一覧を引っ張ってきてCSVに全上書き保存
            csv_path = os.path.join(BACKUP_DIR, filename)
            
            if not os.path.exists(BACKUP_DIR):
                os.makedirs(BACKUP_DIR)
                
            # CSV出力用にも horse_number を取得
            cursor.execute(f"SELECT id, race_id, horse_number, horse_name FROM {table_name}")
            all_entries = cursor.fetchall()
            
            conn.close()  # データベースをクローズ

            # 'w' (上書きモード) で最新のDBの状態をCSVに保存
            with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["id", "race_id", "mode", "horse_number", "horse_name"])
                
                for row in all_entries:
                    writer.writerow([row['id'], row['race_id'], mode, row['horse_number'], row['row_name'] if 'row_name' in row.keys() else row['horse_name']])

            flash(flash_msg)
            backup_on_post()
            return redirect('/entry_form')

        except Exception as e:
            try: conn.close()
            except: pass
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
    race_date = datetime.datetime.strptime(race_date_str, "%Y-%m-%d")
    race_date = JST.localize(race_date)
    # レース日の週の月曜日を基準に取得（weekday(): 月曜0, 日曜6）
    weekday = race_date.weekday()
    monday = race_date - timedelta(days=weekday)
    
    # 金曜の24:00（= 土曜の0:00）
    friday_midnight = monday + timedelta(days=5)  # 月曜+5日 = 土曜
    friday_midnight = friday_midnight.replace(hour=0, minute=0, second=0, microsecond=0)
    
    return friday_midnight

def fetch_entries_from_sheet(race_id):
    """💡 スプレッドシートの代わりに、ローカルのCSVファイルから出走馬を取得する"""
    try:
        csv_path = os.path.join(BACKUP_DIR, "horseentrybefore.csv")
        if not os.path.exists(csv_path):
            return []
            
        entries = []
        # 💡 CSVを開いて該当する race_id の馬を抽出
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader, None) # ヘッダーを読み飛ばす
            
            for row in reader:
                if len(row) >= 4 and row[1] == str(race_id):
                    entries.append({"horse_name": row[3]})
                    
        return entries
    except Exception as e:
        print(f"❌ ローカルCSV取得エラー: {e}")
        return []

@race_bp.route('/admin/download/<table_name>')
@login_required
def download_admin_csv(table_name):
    if current_user.role != 'admin':
        abort(403)
    return generate_admin_csv(table_name)

@race_bp.route('/admin/restore/<table_name>', methods=['POST'])
@login_required
def admin_restore_csv(table_name):
    if current_user.role != 'admin':
        abort(403)
        
    success, message = restore_table_from_csv(table_name)
    
    if success:
        flash(message, "success")
    else:
        flash(message, "error")
        
    return redirect(url_for('user.user_profile', user_id=current_user.id))