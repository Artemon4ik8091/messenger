import sqlite3
from sqlite3 import Error

def create_connection(db_file):
    """
    Создает подключение к базе данных SQLite, указанной в db_file.
    Если файл базы данных не существует, он будет создан.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print(f"Подключение к SQLite успешно: {sqlite3.version}")
        return conn
    except Error as e:
        print(f"Ошибка при подключении к SQLite: {e}")
    return conn

def create_users_table_sqlite(db_file):
    """
    Создает таблицу 'users' в базе данных SQLite.
    """
    conn = create_connection(db_file)
    if conn is not None:
        try:
            cursor = conn.cursor()

            # SQL-запрос для создания таблицы users
            create_table_query = """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                avatar_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL,
                is_deleted BOOLEAN DEFAULT FALSE NOT NULL
            );
            """
            cursor.execute(create_table_query)
            print("Таблица 'users' успешно создана или уже существует.")

            # Добавляем индексы для ускорения поиска, если их нет
            # В SQLite достаточно просто выполнить CREATE INDEX IF NOT EXISTS
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);")
            print("Индексы 'idx_users_username' и 'idx_users_email' проверены/созданы.")

            conn.commit() # Сохраняем изменения в базе данных
        except Error as e:
            print(f"Ошибка при создании таблицы или индексов: {e}")
        finally:
            conn.close()
            print("Соединение с SQLite закрыто.")
    else:
        print("Не удалось установить соединение с базой данных.")

if __name__ == "__main__":
    # >>> Укажите путь к файлу вашей базы данных SQLite <<<
    # Он будет создан в той же папке, где запущен скрипт, если его нет.
    DATABASE_FILE = "messenger.db"

    create_users_table_sqlite(DATABASE_FILE)