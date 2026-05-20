from flask import Blueprint, render_template
from flask_login import current_user
import pytz
from datetime import datetime
from calendar import monthrange

# 💡 循環インポートを防ぐため、共通関数やクラスは database.py から読み込みます
from database import (
    connect_db, 
    get_events_for_month, 
    HolidayCalendar, 
    get_this_week_races
)

# Blueprintの定義
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@main_bp.route('/home')
def home():
    JST = pytz.timezone('Asia/Tokyo')
    today = datetime.now(JST).date()
    year = today.year
    month = today.month
    
    events = get_events_for_month(year, month)

    cal = HolidayCalendar(firstweekday=0)
    calendar_html = cal.formatmonth(year, month)

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
        query = """
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
                (
                    rs.race_date BETWEEN ? AND ? 
                    AND rh.race_id NOT IN (24,25,26,27,28,29,30,31,32,33,34,35,36,37,38)
                )
                OR
                (
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
        cur.execute(query, (start_date, end_date))
    else:
        query = """
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
            WHERE rs.race_date BETWEEN ? AND ? 
              AND rh.race_id NOT IN (24,25,26,27,28,29,30,31,32,33,34,35,36,37,38)
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
    
    query_total = """
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
        races=races,
        current_user=current_user  # 💡ベーステンプレート等で使うため一応追加
    )