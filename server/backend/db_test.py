import sqlite3
from datetime import datetime

# ====================== CẤU HÌNH ======================
DB_NAME = "iot_calendar.db"
OUTPUT_FILE = "database_dump.txt"
# =====================================================

def get_column_names(cursor, table_name):
    """Lấy tên các cột của bảng"""
    cursor.execute(f"PRAGMA table_info({table_name});")
    return [col[1] for col in cursor.fetchall()]


def print_table_to_file(f, cursor, table_name):
    """In một bảng ra file với định dạng cột đẹp"""
    f.write(f"\n{'='*80}\n")
    f.write(f"TABLE: {table_name}\n")
    f.write(f"{'='*80}\n\n")

    # Lấy tên cột
    columns = get_column_names(cursor, table_name)
    
    # Lấy dữ liệu
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    if not rows:
        f.write("Bảng không có dữ liệu.\n")
        return

    # Tính độ rộng tối đa cho mỗi cột
    col_widths = [len(str(col)) for col in columns]
    for row in rows:
        for i, value in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(value if value is not None else "NULL")))

    # Header
    header = " | ".join(f"{col:<{width}}" for col, width in zip(columns, col_widths))
    f.write(header + "\n")
    f.write("-" * len(header) + "\n")

    # Data rows
    for row in rows:
        line = " | ".join(
            f"{str(val) if val is not None else 'NULL':<{width}}" 
            for val, width in zip(row, col_widths)
        )
        f.write(line + "\n")

    f.write(f"\nTổng số dòng: {len(rows)}\n")


# ====================== THỰC THI ======================
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(f"DATABASE DUMP - {DB_NAME}\n")
    f.write(f"Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("="*80 + "\n\n")

    # Liệt kê các bảng
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = cursor.fetchall()

    f.write(f"TỔNG SỐ BẢNG: {len(tables)}\n\n")
    for table in tables:
        table_name = table[0]
        f.write(f"- {table_name}\n")

    f.write("\n" + "="*80 + "\n\n")

    # Xuất chi tiết từng bảng
    for table in tables:
        print_table_to_file(f, cursor, table[0])

print(f"✅ Đã xuất dữ liệu thành công ra file: **{OUTPUT_FILE}**")
conn.close()