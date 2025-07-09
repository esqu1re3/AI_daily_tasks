# Экспорт в CSV / PDF
import pandas as pd
import sqlite3
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os

# Путь к базе
DB_PATH = "data/reports_backup.sqlite"

def load_reports_with_users():
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT 
        reports.id,
        users.name as employee,
        reports.type,
        reports.content,
        reports.created_at
    FROM reports
    JOIN users ON reports.user_id = users.id
    ORDER BY reports.created_at DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def export_to_csv(df: pd.DataFrame, filename: str = None):
    if not filename:
        filename = f"data/exported/reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(filename, index=False)
    return filename

def export_to_pdf(df: pd.DataFrame, filename: str = None):
    if not filename:
        filename = f"data/exported/reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    margin = 50
    y = height - margin

    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, "AI Daily Tasks — Отчёты сотрудников")
    y -= 30
    c.setFont("Helvetica", 10)

    for _, row in df.iterrows():
        report_str = f"[{row['created_at']}] {row['employee']} ({row['type']}): {row['content']}"
        lines = split_text(report_str, width - 2 * margin, c)
        for line in lines:
            if y < margin:
                c.showPage()
                y = height - margin
                c.setFont("Helvetica", 10)
            c.drawString(margin, y, line)
            y -= 15
        y -= 10

    c.save()
    return filename

def split_text(text, max_width, canvas_obj):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + " " + word if current_line else word
        if canvas_obj.stringWidth(test_line, "Helvetica", 10) < max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

# Пример использования (можно вызывать из dashboard.py)
if __name__ == "__main__":
    df = load_reports_with_users()
    print("CSV:", export_to_csv(df))
    print("PDF:", export_to_pdf(df))
