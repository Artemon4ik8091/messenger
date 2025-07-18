import sqlite3
from sqlite3 import Error
from flask import current_app, g
import click
from flask.cli import with_appcontext

def get_db():
    """
    Устанавливает соединение с базой данных, если его еще нет в объекте g.
    """
    if 'db' not in g:
        db_path = current_app.config['DATABASE']
        try:
            g.db = sqlite3.connect(
                db_path,
                detect_types=sqlite3.PARSE_DECLTYPES
            )
            # Устанавливаем режим возврата строк в виде объектов Row (доступ по имени столбца)
            g.db.row_factory = sqlite3.Row
            print(f"Подключение к SQLite успешно установлено: {db_path}")
        except Error as e:
            print(f"Ошибка при подключении к SQLite: {e}")
            raise # Передаем ошибку выше

    return g.db

def close_db(e=None):
    """
    Закрывает соединение с базой данных в конце запроса.
    """
    db = g.pop('db', None)

    if db is not None:
        db.close()
        print("Соединение с SQLite закрыто.")

def init_db():
    """
    Инициализирует базу данных, создавая таблицы из schema.sql.
    """
    db = get_db()
    with current_app.open_resource('schema.sql') as f: # Используем schema.sql для создания таблиц
        db.executescript(f.read().decode('utf8'))
    print("База данных инициализирована.")

def init_app(app):
    """
    Регистрирует функции init_db и close_db с приложением Flask.
    """
    # Регистрируем close_db для выполнения после каждого запроса
    app.teardown_appcontext(close_db)
    # Добавляем команду 'init-db' в CLI Flask
    app.cli.add_command(init_db_command)

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Очищает существующие данные и создает новые таблицы."""
    init_db()
    click.echo('Инициализирована база данных.')

# Дополнительно: Если вы хотите выполнять миграции для уже существующей базы данных,
# вам потребуется более сложная логика миграции, например, с использованием Alembic.
# Для простоты, init_db() здесь очищает и пересоздает все таблицы.