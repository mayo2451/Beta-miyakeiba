from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from database import connect_db  # app.pyから必要な部品をインポート
from werkzeug.exceptions import abort

user_bp = Blueprint('user', __name__)

@user_bp.route('/user/<int:user_id>')
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
        SELECT r.race_date, r.race_place, r.race_name, h.honmeiba, h.honmeiba_rank, h.score, r.is_selected, r.id
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
            SUM(CASE WHEN rh.honmeiba_rank = 1 THEN 1 ELSE 0 END) AS first,
            SUM(CASE WHEN rh.honmeiba_rank = 2 THEN 1 ELSE 0 END) AS second,
            SUM(CASE WHEN rh.honmeiba_rank = 3 THEN 1 ELSE 0 END) AS third,
            SUM(CASE WHEN rh.honmeiba_rank BETWEEN 4 AND 5 THEN 1 ELSE 0 END) AS bbs,
            SUM(CASE WHEN rh.honmeiba_rank = 0 THEN 1 ELSE 0 END) AS out_of_place,
            ROUND(AVG(CASE WHEN rh.honmeiba_rank = 1 THEN 1.00 ELSE 0 END), 4) AS win_rate,
            ROUND(AVG(CASE WHEN rh.honmeiba_rank BETWEEN 1 AND 3 THEN 1.00 ELSE 0 END), 4) AS placing_bets_rate
        FROM raise_horse rh
        JOIN race_schedule rs ON rh.race_id = rs.id
        WHERE rh.username = ? AND rs.is_selected = 1
    """, (username_to_query,))
    row = cursor.fetchone()
    user_stats = None
    if row and row['total_races'] and row['total_races'] > 0:
        user_stats = dict(row)
# 5. ★★★ 総合成績集計（NOT IN条件なし）の追加 ★★★
    cursor.execute("""
        SELECT
            COUNT(*) AS total_races,
            SUM(score) AS total_score,
            SUM(CASE WHEN rh.honmeiba_rank = 1 THEN 1 ELSE 0 END) AS first,
            SUM(CASE WHEN rh.honmeiba_rank = 2 THEN 1 ELSE 0 END) AS second,
            SUM(CASE WHEN rh.honmeiba_rank = 3 THEN 1 ELSE 0 END) AS third,
            SUM(CASE WHEN rh.honmeiba_rank BETWEEN 4 AND 5 THEN 1 ELSE 0 END) AS bbs,
            SUM(CASE WHEN rh.honmeiba_rank = 0 THEN 1 ELSE 0 END) AS out_of_place,
            ROUND(AVG(CASE WHEN rh.honmeiba_rank = 1 THEN 1.00 ELSE 0 END), 4) AS win_rate,
            ROUND(AVG(CASE WHEN rh.honmeiba_rank BETWEEN 1 AND 3 THEN 1.00 ELSE 0 END), 4) AS placing_bets_rate
        FROM raise_horse rh
        JOIN race_schedule rs ON rh.race_id = rs.id
        WHERE rh.username = ?
    """, (username_to_query,))
    row_total = cursor.fetchone()

    total_stats = None
    if row_total and row_total['total_races'] and row_total['total_races'] > 0:
        total_stats = dict(row_total)

    # 4. ログインユーザーかどうかの判定 (変更なし)
    is_current_user = current_user.is_authenticated and current_user.id == user_id
    
    conn.close()
    
    return render_template('user.html', 
                           username=username_to_query,
                           entries=entries,
                           user_stats_filtered=user_stats, # 名前を分かりやすく変更
                           total_stats=total_stats,       # 総合成績
                           is_current_user=is_current_user,
                           user_id=user_id)

@user_bp.route('/allusers')
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

@user_bp.route('/filtered_users')
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