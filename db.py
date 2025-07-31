import sqlite3
from datetime import datetime, timedelta
import os
DB_NAME = "chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            user_message TEXT,
            ai_response TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()



def save_message(user_email, chat_id, user_message=None, ai_response=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Add title if this is the first message in the chat
    c.execute('SELECT COUNT(*) FROM chat_history WHERE chat_id = ?', (chat_id,))
    count = c.fetchone()[0]

    if count == 0:
        try:
            timestamp = int(chat_id)
            readable_time = datetime.fromtimestamp(timestamp).strftime("%b %d, %Y %H:%M")
        except:
            readable_time = datetime.now().strftime("%b %d, %Y %H:%M")
        c.execute('''
            INSERT INTO chat_history (user_email, chat_id, user_message, ai_response)
            VALUES (?, ?, ?, ?)
        ''', (user_email, chat_id, f"[TITLE]Chat - {readable_time}", None))

    # Insert user-AI pair together in a single row
    if user_message or ai_response:
        c.execute('''
            INSERT INTO chat_history (user_email, chat_id, user_message, ai_response)
            VALUES (?, ?, ?, ?)
        ''', (user_email, chat_id, user_message, ai_response))

    conn.commit()
    conn.close()



def get_user_chats(user_email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute('''
        SELECT DISTINCT chat_id FROM chat_history
        WHERE user_email = ?
        ORDER BY timestamp DESC
    ''', (user_email,))
    chat_ids = [row[0] for row in c.fetchall()]

    results = []
    for chat_id in chat_ids:
        # Get title
        c.execute('''
            SELECT user_message FROM chat_history
            WHERE chat_id = ? AND user_message LIKE '[TITLE]%'
            ORDER BY timestamp ASC LIMIT 1
        ''', (chat_id,))
        row = c.fetchone()
        if row and row[0].startswith("[TITLE]"):
            title = row[0].replace("[TITLE]", "").strip()
        else:
            try:
                title = datetime.fromtimestamp(int(chat_id)).strftime("Chat - %b %d, %Y %H:%M")
            except:
                title = f"Chat {chat_id}"

        # Preview: first AI response
        c.execute('''
            SELECT ai_response FROM chat_history
            WHERE chat_id = ? AND ai_response IS NOT NULL
            ORDER BY timestamp ASC LIMIT 1
        ''', (chat_id,))
        preview_row = c.fetchone()

        results.append({
            "id": chat_id,
            "title": title,
            "preview": preview_row[0] if preview_row else ""
        })

    conn.close()
    return results

def get_chat_messages(chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute('''
        SELECT user_message, ai_response, timestamp
        FROM chat_history
        WHERE chat_id = ?
        ORDER BY timestamp
    ''', (chat_id,))
    rows = c.fetchall()
    conn.close()

    messages = []
    for user_msg, ai_msg, ts in rows:
        if user_msg:
            if user_msg.startswith("[TITLE]"):
                messages.append(("AI", user_msg.replace("[TITLE]", "").strip(), ts))
            else:
                messages.append(("You", user_msg, ts))
        if ai_msg:
            messages.append(("AI", ai_msg, ts))
    return messages

def delete_old_messages(days=3):
    """Delete all messages older than `days` days"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    threshold_date = datetime.now() - timedelta(days=days)
    c.execute('''
        DELETE FROM chat_history WHERE timestamp < ?
    ''', (threshold_date.strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()
    conn.close()

def delete_old_chats(user_email, limit=None):
    """Delete all chats older than `days` days for the user"""
    delete_old_messages(days=3)  # Enforce 3-day time limit
    # No chat count limit
    return
