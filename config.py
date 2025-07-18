import os

class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE = os.getenv('DATABASE_PATH', os.path.join(BASE_DIR, 'messenger.db'))
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_super_secret_key_change_me')
    
    # Добавляем настройку для загрузки файлов
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024 # Максимальный размер файла: 16 МБ
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'mp3', 'mp4'}