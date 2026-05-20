import os
import time
import threading
import logging
import sqlite3
import csv  # 💡 上に移動しました
import io
from flask import Response
from database import connect_db, TABLES

# 💡 必要なものだけインポート
from database import connect_db, SKIP_STARTUP_BACKUP, BACKUP_INTERVAL, BACKUP_DIR

def run_backup_async():
    """テーブルのデータをローカルのCSVファイルにバックアップする"""
    logging.info("Starting local async backup process...")
    
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        
    tables = TABLES
    
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        for table in tables:
            # テーブルが存在するかチェック
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';")
            if not cursor.fetchone():
                continue
                
            # データを取得
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            
            if not rows:
                logging.info(f"Table {table} is empty. Skipping backup.")
                continue
                
            # 列名（ヘッダー）を取得
            cursor.execute(f"PRAGMA table_info({table})")
            headers = [info[1] for info in cursor.fetchall()]
            
            # CSVファイルとして保存
            csv_path = os.path.join(BACKUP_DIR, f"{table}.csv")
            with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(headers) # ヘッダーを書き込み
                # sqlite3.Rowオブジェクトを通常のリスト/タプルに変換して書き込み
                writer.writerows([list(row) for row in rows])
                
            logging.info(f"Successfully backed up {table} to local CSV.")
            
        logging.info("Local async backup process finished.")
        
    except Exception as e:
        logging.error(f"Local backup failed: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def backup_on_post():
    """呼び出し用のラッパー（引数なし）"""
    # 既存の並行処理（Threadなど）の呼び出しがあればそのままこれを動かす
    threading.Thread(target=run_backup_async).start()

def backup_scheduler():
    if not SKIP_STARTUP_BACKUP:
        logging.info("Executing initial startup backup...")
        run_backup_async()
    else:
        logging.info("Skipping startup backup as per environment variable.")
    while True:
        time.sleep(BACKUP_INTERVAL)
        run_backup_async()

def start_backup_scheduler():
    logging.info("Starting backup scheduler thread...")
    threading.Thread(target=backup_scheduler, daemon=True).start()

def generate_admin_csv(table_name: str):
    """管理者用に、指定されたテーブルの最新データをCSV（Response型）として生成する"""
    tables = TABLES
    if table_name not in tables:
        return Response("Invalid table name", status=400)
        
    conn = connect_db()
    # 💡 行名（カラム名）でデータにアクセスできるように Row 形式に設定
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    
    try:
        # データを取得
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        # 列名（ヘッダー）を取得
        cursor.execute(f"PRAGMA table_info({table_name})")
        headers = [info[1] for info in cursor.fetchall()]
        
        # メモリ上にCSVを作成
        output = io.StringIO()
        output.write('\ufeff') # Excel文字化け防止のBOM
        
        writer = csv.writer(output)
        writer.writerow(headers) # ヘッダー書き込み
        
        for row in rows:
            # 💡 sqlite3.Rowオブジェクトを通常のリストにして書き込み
            writer.writerow(list(row))
            
        # Flaskがブラウザに「ファイル」として返すためのレスポンスを作成
        response = Response(output.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=admin_export_{table_name}.csv"
        return response
        
    except Exception as e:
        logging.error(f"Admin CSV generation failed for {table_name}: {e}")
        return Response(f"Error: {e}", status=500)
    finally:
        conn.close()

def restore_table_from_csv(table_name: str):
    csv_path = os.path.join(BACKUP_DIR, f"{table_name}.csv")

    if not os.path.exists(csv_path):
        return False, f"バックアップファイルが見つかりません: {table_name}.csv"
    
    conn = connect_db()
    cursor = conn.cursor()

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            if not headers:
                return False, f"{table_name}.csv が空っぽです"
            
            cursor.execute(f"DELETE FROM {table_name}")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
            if cursor.fetchone():
                cursor.execute("DELETE FROM sqlite_sequence WHERE name=?", (table_name,))

            placeholders = ", ".join(["?"] * len(headers))
            sql = f"INSERT INTO {table_name} ({', '.join(headers)}) VALUES ({placeholders})"

            date_index = headers.index('race_date') if 'race_date' in headers else -1

            inserted_count = 0
            for row in reader:
                if row:  # 空行でなければ
                    if table_name == 'race_schedule' and date_index != -1:
                        raw_date = row[date_index]
                        
                        # スラッシュ区切り（2026/5/18 や 2026/05/18）をハイフンに置換
                        if '/' in raw_date:
                            parts = raw_date.split('/')
                            if len(parts) == 3:
                                # 月と日を 2桁（0埋め）に揃えて YYYY-MM-DD に変換
                                year = parts[0]
                                month = parts[1].zfill(2)
                                day = parts[2].zfill(2)
                                row[date_index] = f"{year}-{month}-{day}"
                    cursor.execute(sql, row)
                    inserted_count += 1
                    
        conn.commit()
        return True, f"{inserted_count} 件のデータを {table_name} に復元しました！"
        
    except Exception as e:
        conn.rollback()
        logging.error(f"CSV import failed for {table_name}: {e}")
        return False, f"復元中にエラーが発生しました: {e}"
    finally:
        conn.close()