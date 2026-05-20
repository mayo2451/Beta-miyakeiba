import os
import sqlite3
import calendar
from calendar import monthrange
from datetime import date, datetime, timedelta
import jpholiday
import pytz
from typing import List, Dict
from flask_login import UserMixin

SHEET_NAME = "miyakeiba_backup_copy"
TABLES = ['race_entries', 'horseentrybefore', 'race_result', 'race_schedule', 'raise_horse', 'sqlite_sequence', 'users']
BACKUP_INTERVAL = 600
DB_NAME = "miyakeiba_app.db"
SKIP_STARTUP_BACKUP = os.getenv("SKIP_STARTUP_BACKUP", "false").lower() == "true"
JAPANESE_WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
JST = pytz.timezone('Asia/Tokyo')
BACKUP_DIR = r"D:\miyakeiba\Beta-miyakeiba-main\miyakeiba-beta\backups"
#test_match = [24,25,26,27,28,29,30,31,32,33,34,35,36,37,38]
#placeholders= ', '.join('?' for _ in test_match)

def connect_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

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
        SELECT id, race_date, race_place, race_ground, race_distance, race_number, race_grade, race_name, start_time, is_selected
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
            'start_time': row['start_time'],
            'is_selected': row['is_selected']
        })

    return events

def group_events_by_date(events: List[Dict]) -> Dict[str, List[Dict]]:
    grouped = {}
    for e in events:
        d = e['race_date']
        if d not in grouped:
            grouped[d] = []
        grouped[d].append(e)
    return grouped

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

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role