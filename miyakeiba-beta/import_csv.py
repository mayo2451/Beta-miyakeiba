import sqlite3
import csv

# SQLiteデータベースへの接続
conn = sqlite3.connect('miyakeiba_app.db')
cursor = conn.cursor()

# CSVファイルのパス（適宜変更）
csv_file_path = 'race_schedule.csv'

# CSVを開いて1行ずつ読み込み、INSERTする
with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile)

    # ヘッダーをスキップ（ある場合）
    # next(reader)

    for row in reader:
        # カラム数と順番に合わせてください
        cursor.execute("""
            INSERT INTO race_schedule (race_date, race_place, race_number, race_grade, race_name, start_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, row)

# コミットして接続終了
conn.commit()
conn.close()

print("CSVからのインポートが完了しました。")