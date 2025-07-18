from flask import Flask, request, jsonify, g, session, redirect, url_for, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
import functools
import uuid # Для уникальных имен файлов

# Загружаем переменные окружения из .env файла
load_dotenv()

# Импортируем конфигурацию и функции для работы с БД
from config import Config
from database import get_db, close_db, init_app

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    init_app(app)

    # Убедимся, что папка для загрузок существует
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # --- Вспомогательные функции для аутентификации ---
    def login_required(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                return jsonify({'error': 'Требуется аутентификация'}), 401
            return view(**kwargs)
        return wrapped_view

    @app.before_request
    def load_logged_in_user():
        user_id = session.get('user_id')
        if user_id is None:
            g.user = None
        else:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "SELECT id, username, display_name, email, avatar_url, is_deleted FROM users WHERE id = ?", (user_id,)
            )
            user_data = cursor.fetchone()
            cursor.close()

            if user_data and not user_data['is_deleted']:
                g.user = user_data
            else:
                g.user = None
                session.clear()

    # --- Вспомогательная функция для проверки разрешенных расширений файлов ---
    def allowed_file(filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

    # --- Основные маршруты ---
    @app.route('/')
    def index():
        return "Добро пожаловать в Backend Мессенджера!"

    # API для Управления Пользователями
    @app.route('/api/register', methods=['POST'])
    def register_user():
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        display_name = data.get('display_name', username) # Если display_name не указан, используем username

        if not username or not password:
            return jsonify({'error': 'Имя пользователя и пароль обязательны'}), 400

        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                return jsonify({'error': 'Пользователь с таким именем уже существует'}), 409

            hashed_password = generate_password_hash(password)

            cursor.execute(
                "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
                (username, hashed_password, display_name)
            )
            db.commit()
            user_id = cursor.lastrowid
            return jsonify({'message': 'Пользователь успешно зарегистрирован', 'user_id': user_id}), 201
        except Exception as e:
            db.rollback()
            print(f"Ошибка при регистрации пользователя: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/api/login', methods=['POST'])
    def login_user():
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'error': 'Имя пользователя и пароль обязательны'}), 400

        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute("SELECT id, username, password_hash, display_name, is_deleted FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()

            if user is None:
                return jsonify({'error': 'Неверное имя пользователя или пароль'}), 401

            if user['is_deleted']:
                return jsonify({'error': 'Аккаунт пользователя удален. Обратитесь в поддержку, если это ошибка.'}), 403

            if not check_password_hash(user['password_hash'], password):
                return jsonify({'error': 'Неверное имя пользователя или пароль'}), 401

            session.clear()
            session['user_id'] = user['id']

            return jsonify({
                'message': 'Вход выполнен успешно',
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'display_name': user['display_name']
                }
            }), 200
        except Exception as e:
            print(f"Ошибка при входе пользователя: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/api/logout', methods=['POST'])
    @login_required
    def logout_user():
        session.clear()
        return jsonify({'message': 'Выход выполнен успешно'}), 200

    @app.route('/api/users/profile', methods=['GET'])
    @login_required
    def get_user_profile():
        user = g.user
        # Избегаем отправки password_hash
        return jsonify({
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'display_name': user['display_name'],
            'avatar_url': user['avatar_url']
        }), 200

    @app.route('/api/users/profile', methods=['PUT'])
    @login_required
    def update_user_profile():
        user_id = g.user['id']
        data = request.get_json()
        
        display_name = data.get('display_name')
        email = data.get('email')
        avatar_url = data.get('avatar_url')

        # Проверяем, есть ли что-либо для обновления
        if not any([display_name is not None, email is not None, avatar_url is not None]):
            return jsonify({'error': 'Нечего обновлять. Предоставьте display_name, email или avatar_url.'}), 400

        db = get_db()
        cursor = db.cursor()

        try:
            updates = []
            params = []

            if display_name is not None:
                updates.append("display_name = ?")
                params.append(display_name)
            
            if email is not None:
                # Проверяем, не занят ли email другим пользователем
                cursor.execute("SELECT id FROM users WHERE email = ? AND id != ?", (email, user_id))
                if cursor.fetchone():
                    return jsonify({'error': 'Email уже используется другим пользователем'}), 409
                updates.append("email = ?")
                params.append(email)

            if avatar_url is not None:
                updates.append("avatar_url = ?")
                params.append(avatar_url)
            
            updates.append("updated_at = CURRENT_TIMESTAMP") # Обновляем метку времени обновления

            if not updates: # Это должно быть unreachable из-за проверки any() выше, но на всякий случай
                return jsonify({'message': 'Нет данных для обновления.'}), 200

            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            params.append(user_id)

            cursor.execute(query, tuple(params))
            db.commit()

            return jsonify({'message': 'Профиль успешно обновлен'}), 200
        except Exception as e:
            db.rollback()
            print(f"Ошибка при обновлении профиля: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/api/users/password', methods=['PUT'])
    @login_required
    def update_user_password():
        user_id = g.user['id']
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        if not current_password or not new_password:
            return jsonify({'error': 'Требуются текущий и новый пароли'}), 400
        if len(new_password) < 6: # Пример минимальной длины пароля
            return jsonify({'error': 'Новый пароль должен быть не менее 6 символов.'}), 400

        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()

            if user is None: # На всякий случай, если g.user был каким-то образом сброшен
                return jsonify({'error': 'Пользователь не найден'}), 404

            if not check_password_hash(user['password_hash'], current_password):
                return jsonify({'error': 'Неверный текущий пароль'}), 401

            new_hashed_password = generate_password_hash(new_password)

            cursor.execute(
                "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_hashed_password, user_id)
            )
            db.commit()

            return jsonify({'message': 'Пароль успешно обновлен'}), 200
        except Exception as e:
            db.rollback()
            print(f"Ошибка при обновлении пароля: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/api/users/delete', methods=['POST'])
    @login_required
    def delete_user_account():
        user_id = g.user['id']
        
        db = get_db()
        cursor = db.cursor()

        try:
            # Мягкое удаление пользователя: меняем username, сбрасываем email/avatar, помечаем как удаленный
            # Это позволяет сохранить ссылки на сообщения пользователя без раскрытия его данных
            deleted_username = f"deleted_user_{user_id}_{uuid.uuid4().hex[:8]}" # Добавляем UUID для уникальности
            
            cursor.execute(
                """
                UPDATE users
                SET username = ?,
                    display_name = 'Удаленный пользователь',
                    email = NULL,
                    avatar_url = NULL,
                    password_hash = ?, -- Хешируем случайный пароль, чтобы нельзя было войти
                    is_deleted = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (deleted_username, generate_password_hash(os.urandom(16).hex()), user_id)
            )
            db.commit()

            session.clear() # Выходим из системы после удаления аккаунта

            return jsonify({'message': 'Аккаунт успешно удален (помечен как удаленный)'}), 200
        except Exception as e:
            db.rollback()
            print(f"Ошибка при удалении аккаунта: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()
    
    # API для Управления Чатами

    # Вспомогательная функция для создания чата (используется внутренне)
    def _create_chat_logic(user_id, chat_type, name=None, avatar_url=None, member_ids=None):
        db = get_db()
        cursor = db.cursor()
        chat_id = None
        try:
            if chat_type == 'private':
                if not member_ids or len(member_ids) != 1:
                    return jsonify({'error': 'Для личного чата требуется ровно один member_id.'}), 400
                
                other_user_id = member_ids[0]
                if other_user_id == user_id:
                    return jsonify({'error': 'Нельзя создать личный чат с самим собой.'}), 400

                # Проверяем, существует ли пользователь, с которым создается чат
                cursor.execute("SELECT id FROM users WHERE id = ? AND is_deleted = FALSE", (other_user_id,))
                if not cursor.fetchone():
                    return jsonify({'error': 'Целевой пользователь не найден или удален.'}), 404

                # Нормализация порядка user_id для поиска существующих чатов
                sorted_user_ids = sorted([user_id, other_user_id])
                user1, user2 = sorted_user_ids[0], sorted_user_ids[1]

                cursor.execute(
                    "SELECT c.id FROM chats c JOIN private_chats pc ON c.id = pc.chat_id WHERE pc.user1_id = ? AND pc.user2_id = ?",
                    (user1, user2)
                )
                existing_chat = cursor.fetchone()
                if existing_chat:
                    return jsonify({'error': 'Личный чат с этим пользователем уже существует.', 'chat_id': existing_chat['id']}), 409

                cursor.execute(
                    "INSERT INTO chats (type) VALUES (?)",
                    (chat_type,)
                )
                chat_id = cursor.lastrowid
                
                cursor.execute(
                    "INSERT INTO private_chats (chat_id, user1_id, user2_id) VALUES (?, ?, ?)",
                    (chat_id, user1, user2)
                )
                
            elif chat_type in ['group', 'channel']:
                if not name:
                    return jsonify({'error': 'Для групп и каналов требуется имя.'}), 400

                if chat_type == 'channel':
                    # Устанавливаем создателя канала как его владельца
                    cursor.execute(
                        "INSERT INTO chats (type, name, avatar_url, owner_id) VALUES (?, ?, ?, ?)",
                        (chat_type, name, avatar_url, user_id)
                    )
                else: # group
                    cursor.execute(
                        "INSERT INTO chats (type, name, avatar_url) VALUES (?, ?, ?)",
                        (chat_type, name, avatar_url)
                    )
                chat_id = cursor.lastrowid

                # Добавляем создателя как участника/подписчика
                if chat_type == 'group':
                    cursor.execute(
                        "INSERT INTO group_members (group_id, user_id, role) VALUES (?, ?, ?)",
                        (chat_id, user_id, 'admin') # Создатель группы всегда админ
                    )
                else: # channel
                    cursor.execute(
                        "INSERT INTO channel_subscribers (channel_id, user_id) VALUES (?, ?)",
                        (chat_id, user_id)
                    )
                
                # Добавляем дополнительных участников/подписчиков (если есть)
                if member_ids:
                    # Используем set для удаления дубликатов и избегаем добавления создателя снова
                    for member_id in set(member_ids):
                        if member_id == user_id:
                            continue 
                        cursor.execute("SELECT id FROM users WHERE id = ? AND is_deleted = FALSE", (member_id,))
                        if not cursor.fetchone():
                            print(f"Предупреждение: Пользователь с ID {member_id} не существует или удален и не будет добавлен.")
                            continue

                        if chat_type == 'group':
                            cursor.execute(
                                "INSERT INTO group_members (group_id, user_id, role) VALUES (?, ?, ?)",
                                (chat_id, member_id, 'member')
                            )
                        else: # channel
                            cursor.execute(
                                "INSERT INTO channel_subscribers (channel_id, user_id) VALUES (?, ?)",
                                (chat_id, member_id)
                            )
            
            db.commit()
            return jsonify({'message': f'{chat_type.capitalize()} чат успешно создан', 'chat_id': chat_id}), 201

        except Exception as e:
            db.rollback()
            print(f"Ошибка при создании чата: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    # Специфические маршруты для создания чатов
    @app.route('/api/chats/private', methods=['POST'])
    @login_required
    def create_private_chat_api():
        user_id = g.user['id']
        data = request.get_json()
        target_username = data.get('target_username')

        if not target_username:
            return jsonify({'error': 'Требуется имя пользователя для личного чата.'}), 400
        
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute("SELECT id FROM users WHERE username = ? AND is_deleted = FALSE", (target_username,))
            target_user = cursor.fetchone()
            if not target_user:
                return jsonify({'error': 'Пользователь не найден или удален.'}), 404
            
            member_ids = [target_user['id']]
            return _create_chat_logic(user_id, 'private', member_ids=member_ids)
        finally:
            cursor.close()


    @app.route('/api/chats/group', methods=['POST'])
    @login_required
    def create_group_chat_api():
        user_id = g.user['id']
        data = request.get_json()
        name = data.get('name')
        member_usernames = data.get('member_usernames', [])

        if not name:
            return jsonify({'error': 'Требуется имя для группового чата.'}), 400
        
        member_ids = []
        if member_usernames:
            db = get_db()
            cursor = db.cursor()
            try:
                for username in member_usernames:
                    cursor.execute("SELECT id FROM users WHERE username = ? AND is_deleted = FALSE", (username,))
                    user = cursor.fetchone()
                    if user:
                        member_ids.append(user['id'])
                    else:
                        print(f"Предупреждение: Пользователь '{username}' не найден или удален и не будет добавлен в группу.")
            finally:
                cursor.close()
        
        return _create_chat_logic(user_id, 'group', name=name, member_ids=member_ids)

    @app.route('/api/chats/channel', methods=['POST'])
    @login_required
    def create_channel_api():
        user_id = g.user['id']
        data = request.get_json()
        name = data.get('name')
        avatar_url = data.get('avatar_url') # Каналы тоже могут иметь аватар

        if not name:
            return jsonify({'error': 'Требуется имя для канала.'}), 400
        
        return _create_chat_logic(user_id, 'channel', name=name, avatar_url=avatar_url)


    @app.route('/api/chats', methods=['GET'])
    @login_required
    def get_user_chats():
        user_id = g.user['id']
        db = get_db()
        cursor = db.cursor()
        
        chats = []
        try:
            # Получение приватных чатов
            cursor.execute(
                """
                SELECT
                    c.id, c.type, c.created_at, c.updated_at,
                    CASE
                        WHEN pc.user1_id = ? THEN u2.display_name
                        ELSE u1.display_name
                    END AS name,
                    CASE
                        WHEN pc.user1_id = ? THEN u2.avatar_url
                        ELSE u1.avatar_url
                    END AS avatar_url,
                    pc.user1_id, pc.user2_id
                FROM chats c
                JOIN private_chats pc ON c.id = pc.chat_id
                JOIN users u1 ON pc.user1_id = u1.id
                JOIN users u2 ON pc.user2_id = u2.id
                WHERE c.type = 'private' AND (pc.user1_id = ? OR pc.user2_id = ?)
                """,
                (user_id, user_id, user_id, user_id)
            )
            private_chats = cursor.fetchall()
            for chat in private_chats:
                chats.append({
                    'id': chat['id'],
                    'type': chat['type'],
                    'name': chat['name'],
                    'avatar_url': chat['avatar_url'],
                    'created_at': chat['created_at'],
                    'updated_at': chat['updated_at'],
                    'participants': [chat['user1_id'], chat['user2_id']] # Можно добавить список ID участников
                })

            # Получение групповых чатов
            cursor.execute(
                """
                SELECT c.id, c.type, c.name, c.avatar_url, c.created_at, c.updated_at, gm.role
                FROM chats c
                JOIN group_members gm ON c.id = gm.group_id
                WHERE c.type = 'group' AND gm.user_id = ?
                """,
                (user_id,)
            )
            groups = cursor.fetchall()
            for group in groups:
                chats.append({
                    'id': group['id'],
                    'type': group['type'],
                    'name': group['name'],
                    'avatar_url': group['avatar_url'],
                    'created_at': group['created_at'],
                    'updated_at': group['updated_at'],
                    'role': group['role'] # Роль пользователя в группе
                })

            # Получение каналов
            cursor.execute(
                """
                SELECT c.id, c.type, c.name, c.avatar_url, c.created_at, c.updated_at
                FROM chats c
                JOIN channel_subscribers cs ON c.id = cs.channel_id
                WHERE c.type = 'channel' AND cs.user_id = ?
                """,
                (user_id,)
            )
            channels = cursor.fetchall()
            for channel in channels:
                chats.append({
                    'id': channel['id'],
                    'type': channel['type'],
                    'name': channel['name'],
                    'avatar_url': channel['avatar_url'],
                    'created_at': channel['created_at'],
                    'updated_at': channel['updated_at']
                })

            return jsonify({'chats': chats}), 200

        except Exception as e:
            print(f"Ошибка при получении чатов пользователя: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/api/chats/<int:chat_id>', methods=['GET'])
    @login_required
    def get_chat_details(chat_id):
        user_id = g.user['id']
        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute(
                """
                SELECT c.id, c.type, c.name, c.avatar_url, c.created_at, c.updated_at, c.owner_id
                FROM chats c
                WHERE c.id = ?
                """,
                (chat_id,)
            )
            chat = cursor.fetchone()

            if chat is None:
                return jsonify({'error': 'Чат не найден.'}), 404

            is_member = False
            chat_details = {
                'id': chat['id'],
                'type': chat['type'],
                'name': chat['name'], # Для групп и каналов это имя из БД, для приватных - имя собеседника
                'avatar_url': chat['avatar_url'], # Аналогично
                'created_at': chat['created_at'],
                'updated_at': chat['updated_at'],
                'members': [] # Список участников
            }
            
            if chat['type'] == 'private':
                cursor.execute(
                    "SELECT user1_id, user2_id FROM private_chats WHERE chat_id = ?",
                    (chat_id,)
                )
                private_chat_info = cursor.fetchone()
                if private_chat_info:
                    if user_id in [private_chat_info['user1_id'], private_chat_info['user2_id']]:
                        is_member = True
                        # Получаем информацию об обоих участниках
                        cursor.execute("SELECT id, username, display_name, avatar_url, is_deleted FROM users WHERE id IN (?, ?)", (private_chat_info['user1_id'], private_chat_info['user2_id']))
                        participants = cursor.fetchall()
                        # Фильтруем удаленных пользователей, но сохраняем их ID для полноты
                        chat_details['members'] = [{'id': p['id'], 'username': p['username'], 'display_name': p['display_name'], 'avatar_url': p['avatar_url'], 'is_deleted': p['is_deleted']} for p in participants]
                        
                        # Для приватного чата, имя и аватар чата - это имя и аватар собеседника
                        other_user = next((p for p in participants if p['id'] != user_id and not p['is_deleted']), None)
                        if other_user:
                            chat_details['name'] = other_user['display_name']
                            chat_details['avatar_url'] = other_user['avatar_url']
                        else: # Если собеседник удален
                            chat_details['name'] = "Удаленный пользователь"
                            chat_details['avatar_url'] = None # Или заглушка
                    else:
                        return jsonify({'error': 'У вас нет доступа к этому приватному чату.'}), 403

            elif chat['type'] == 'group':
                cursor.execute(
                    "SELECT gm.role, u.id, u.username, u.display_name, u.avatar_url, u.is_deleted FROM group_members gm JOIN users u ON gm.user_id = u.id WHERE gm.group_id = ?",
                    (chat_id,)
                )
                members_data = cursor.fetchall()
                chat_details['members'] = [{'id': m['id'], 'username': m['username'], 'display_name': m['display_name'], 'avatar_url': m['avatar_url'], 'role': m['role'], 'is_deleted': m['is_deleted']} for m in members_data]
                is_member = any(m['id'] == user_id for m in members_data)
                if not is_member:
                    return jsonify({'error': 'Вы не являетесь участником этой группы.'}), 403

            elif chat['type'] == 'channel':
                cursor.execute(
                    "SELECT cs.joined_at, u.id, u.username, u.display_name, u.avatar_url, u.is_deleted FROM channel_subscribers cs JOIN users u ON cs.user_id = u.id WHERE cs.channel_id = ?",
                    (chat_id,)
                )
                subscribers_data = cursor.fetchall()
                chat_details['members'] = [{'id': s['id'], 'username': s['username'], 'display_name': s['display_name'], 'avatar_url': s['avatar_url'], 'is_deleted': s['is_deleted']} for s in subscribers_data]
                is_member = any(s['id'] == user_id for s in subscribers_data)
                if not is_member:
                    return jsonify({'error': 'Вы не подписаны на этот канал.'}), 403
                
                # Добавляем информацию о владельце канала
                if chat['owner_id']:
                    cursor.execute("SELECT id, username, display_name, avatar_url, is_deleted FROM users WHERE id = ?", (chat['owner_id'],))
                    owner_info = cursor.fetchone()
                    if owner_info and not owner_info['is_deleted']:
                        chat_details['owner'] = {'id': owner_info['id'], 'username': owner_info['username'], 'display_name': owner_info['display_name'], 'avatar_url': owner_info['avatar_url']}
                    else: # Если владелец удален
                        chat_details['owner'] = {'id': chat['owner_id'], 'username': 'Удаленный пользователь', 'display_name': 'Удаленный пользователь', 'avatar_url': None}


            if not is_member: # Дублирующая проверка, на всякий случай
                return jsonify({'error': 'У вас нет доступа к этому чату.'}), 403

            return jsonify(chat_details), 200

        except Exception as e:
            print(f"Ошибка при получении деталей чата: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()
    
    @app.route('/api/chats/<int:chat_id>', methods=['PUT'])
    @login_required
    def update_chat_info(chat_id):
        user_id = g.user['id']
        data = request.get_json()
        name = data.get('name')
        avatar_url = data.get('avatar_url')

        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute("SELECT type, owner_id FROM chats WHERE id = ?", (chat_id,))
            chat_info = cursor.fetchone()
            if not chat_info:
                return jsonify({'error': 'Чат не найден.'}), 404
            
            chat_type = chat_info['type']
            owner_id = chat_info['owner_id']

            if chat_type == 'private':
                return jsonify({'error': 'Нельзя обновить информацию личного чата.'}), 400

            if chat_type == 'group':
                cursor.execute(
                    "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
                    (chat_id, user_id)
                )
                member_role = cursor.fetchone()
                if not member_role or member_role['role'] != 'admin':
                    return jsonify({'error': 'Только администратор группы может обновлять информацию о группе.'}), 403
            elif chat_type == 'channel':
                # Только владелец канала может обновлять информацию о канале
                if user_id != owner_id:
                    return jsonify({'error': 'Только владелец канала может обновлять информацию о канале.'}), 403

            updates = []
            params = []

            if name is not None:
                updates.append("name = ?")
                params.append(name)
            
            if avatar_url is not None:
                updates.append("avatar_url = ?")
                params.append(avatar_url)
            
            updates.append("updated_at = CURRENT_TIMESTAMP")

            if not updates:
                return jsonify({'message': 'Нет данных для обновления.'}), 200

            query = f"UPDATE chats SET {', '.join(updates)} WHERE id = ?"
            params.append(chat_id)

            cursor.execute(query, tuple(params))
            db.commit()

            return jsonify({'message': f'Информация о {chat_type} чате успешно обновлена'}), 200
        except Exception as e:
            db.rollback()
            print(f"Ошибка при обновлении информации о чате: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/api/chats/<int:chat_id>', methods=['DELETE'])
    @login_required
    def delete_chat(chat_id):
        user_id = g.user['id']
        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute("SELECT type, owner_id FROM chats WHERE id = ?", (chat_id,))
            chat_info = cursor.fetchone()
            if not chat_info:
                return jsonify({'error': 'Чат не найден.'}), 404
            
            chat_type = chat_info['type']
            owner_id = chat_info['owner_id']
            
            can_delete = False
            if chat_type == 'private':
                # Для приватных чатов удалять может любой из двух участников
                cursor.execute(
                    "SELECT 1 FROM private_chats WHERE chat_id = ? AND (user1_id = ? OR user2_id = ?)",
                    (chat_id, user_id, user_id)
                )
                if cursor.fetchone():
                    can_delete = True
            elif chat_type == 'group':
                # Удалять группу может только админ группы
                cursor.execute(
                    "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
                    (chat_id, user_id)
                )
                member_role = cursor.fetchone()
                if member_role and member_role['role'] == 'admin':
                    can_delete = True
            elif chat_type == 'channel':
                # Удалять канал может только его владелец
                if user_id == owner_id:
                    can_delete = True

            if not can_delete:
                return jsonify({'error': 'У вас нет прав на удаление этого чата.'}), 403

            cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            db.commit()

            return jsonify({'message': f'{chat_type.capitalize()} чат успешно удален.'}), 200
        except Exception as e:
            db.rollback()
            print(f"Ошибка при удалении чата: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    # API для управления участниками групп и каналов
    @app.route('/api/groups/<int:group_id>/members', methods=['POST'])
    @login_required
    def add_group_member(group_id):
        current_user_id = g.user['id']
        data = request.get_json()
        target_username = data.get('username')
        role = data.get('role', 'member')

        if not target_username:
            return jsonify({'error': 'Требуется имя пользователя (username) для добавления.'}), 400
        if role not in ['admin', 'member', 'restricted']:
            return jsonify({'error': 'Неверная роль. Допустимы: admin, member, restricted.'}), 400

        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute("SELECT type FROM chats WHERE id = ?", (group_id,))
            chat_info = cursor.fetchone()
            if not chat_info or chat_info['type'] != 'group':
                return jsonify({'error': 'Чат не найден или не является группой.'}), 404
            
            cursor.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
                (group_id, current_user_id)
            )
            current_user_role = cursor.fetchone()
            if not current_user_role or current_user_role['role'] != 'admin':
                return jsonify({'error': 'У вас нет прав на добавление/изменение участников в этой группе.'}), 403
            
            cursor.execute("SELECT id FROM users WHERE username = ? AND is_deleted = FALSE", (target_username,))
            target_user = cursor.fetchone()
            if not target_user:
                return jsonify({'error': 'Целевой пользователь не найден или удален.'}), 404
            
            target_user_id = target_user['id']

            cursor.execute(
                "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
                (group_id, target_user_id)
            )
            if cursor.fetchone():
                return jsonify({'error': 'Пользователь уже является участником этой группы.'}), 409

            cursor.execute(
                "INSERT INTO group_members (group_id, user_id, role) VALUES (?, ?, ?)",
                (group_id, target_user_id, role)
            )
            db.commit()

            return jsonify({'message': 'Пользователь успешно добавлен в группу.'}), 201
        except Exception as e:
            db.rollback()
            print(f"Ошибка при добавлении участника группы: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/api/groups/<int:group_id>/members/<int:target_user_id>', methods=['PUT'])
    @login_required
    def update_group_member_role(group_id, target_user_id):
        current_user_id = g.user['id']
        data = request.get_json()
        new_role = data.get('role')

        if not new_role or new_role not in ['admin', 'member', 'restricted']:
            return jsonify({'error': 'Неверная роль. Допустимы: admin, member, restricted.'}), 400

        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute("SELECT type FROM chats WHERE id = ?", (group_id,))
            chat_info = cursor.fetchone()
            if not chat_info or chat_info['type'] != 'group':
                return jsonify({'error': 'Чат не найден или не является группой.'}), 404
            
            cursor.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
                (group_id, current_user_id)
            )
            current_user_role = cursor.fetchone()
            if not current_user_role or current_user_role['role'] != 'admin':
                return jsonify({'error': 'У вас нет прав на изменение ролей участников в этой группе.'}), 403
            
            # Нельзя понизить свою роль, если вы единственный админ
            if current_user_id == target_user_id and new_role != 'admin':
                cursor.execute(
                    "SELECT COUNT(*) FROM group_members WHERE group_id = ? AND role = 'admin'",
                    (group_id,)
                )
                admin_count = cursor.fetchone()[0]
                if admin_count == 1:
                    return jsonify({'error': 'Нельзя понизить свою роль, если вы единственный администратор группы.'}), 400

            cursor.execute(
                "UPDATE group_members SET role = ?, joined_at = CURRENT_TIMESTAMP WHERE group_id = ? AND user_id = ?",
                (new_role, group_id, target_user_id)
            )
            if cursor.rowcount == 0:
                return jsonify({'error': 'Пользователь не является участником этой группы.'}), 404
            
            db.commit()

            return jsonify({'message': 'Роль участника успешно обновлена.'}), 200
        except Exception as e:
            db.rollback()
            print(f"Ошибка при изменении роли участника группы: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/api/groups/<int:group_id>/members/<int:target_user_id>', methods=['DELETE'])
    @login_required
    def remove_group_member(group_id, target_user_id):
        current_user_id = g.user['id']
        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute("SELECT type FROM chats WHERE id = ?", (group_id,))
            chat_info = cursor.fetchone()
            if not chat_info or chat_info['type'] != 'group':
                return jsonify({'error': 'Чат не найден или не является группой.'}), 404
            
            cursor.execute(
                "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
                (group_id, current_user_id)
            )
            current_user_role = cursor.fetchone()
            if not current_user_role or current_user_role['role'] != 'admin':
                return jsonify({'error': 'У вас нет прав на удаление участников из этой группы.'}), 403
            
            # Нельзя удалить себя, если вы единственный админ группы
            if current_user_id == target_user_id:
                cursor.execute(
                    "SELECT COUNT(*) FROM group_members WHERE group_id = ? AND role = 'admin'",
                    (group_id,)
                )
                admin_count = cursor.fetchone()[0]
                if admin_count == 1:
                    return jsonify({'error': 'Нельзя удалить себя, если вы единственный администратор группы.'}), 400

            cursor.execute(
                "DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
                (group_id, target_user_id)
            )
            if cursor.rowcount == 0:
                return jsonify({'error': 'Пользователь не является участником этой группы.'}), 404
            
            db.commit()

            return jsonify({'message': 'Участник успешно удален из группы.'}), 200
        except Exception as e:
            db.rollback()
            print(f"Ошибка при удалении участника группы: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/api/channels/<int:channel_id>/subscribers', methods=['POST'])
    @login_required
    def add_channel_subscriber(channel_id):
        current_user_id = g.user['id']
        data = request.get_json()
        target_username = data.get('username')

        if not target_username:
            return jsonify({'error': 'Требуется имя пользователя (username) для добавления.'}), 400

        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute("SELECT type, owner_id FROM chats WHERE id = ?", (channel_id,))
            chat_info = cursor.fetchone()
            if not chat_info or chat_info['type'] != 'channel':
                return jsonify({'error': 'Чат не найден или не является каналом.'}), 404
            
            # Проверка, что текущий пользователь является ВЛАДЕЛЬЦЕМ канала
            if current_user_id != chat_info['owner_id']:
                return jsonify({'error': 'Только владелец канала может добавлять подписчиков.'}), 403
            
            cursor.execute("SELECT id FROM users WHERE username = ? AND is_deleted = FALSE", (target_username,))
            target_user = cursor.fetchone()
            if not target_user:
                return jsonify({'error': 'Целевой пользователь не найден или удален.'}), 404

            target_user_id = target_user['id']

            cursor.execute(
                "SELECT id FROM channel_subscribers WHERE channel_id = ? AND user_id = ?",
                (channel_id, target_user_id)
            )
            if cursor.fetchone():
                return jsonify({'error': 'Пользователь уже подписан на этот канал.'}), 409

            cursor.execute(
                "INSERT INTO channel_subscribers (channel_id, user_id) VALUES (?, ?)",
                (channel_id, target_user_id)
            )
            db.commit()

            return jsonify({'message': 'Пользователь успешно добавлен в канал.'}), 201
        except Exception as e:
            db.rollback()
            print(f"Ошибка при добавлении подписчика канала: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/api/channels/<int:channel_id>/unsubscribe', methods=['DELETE'])
    @login_required
    def unsubscribe_channel(channel_id):
        user_id = g.user['id']
        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute("SELECT type, owner_id FROM chats WHERE id = ?", (channel_id,))
            chat_info = cursor.fetchone()
            if not chat_info or chat_info['type'] != 'channel':
                return jsonify({'error': 'Чат не найден или не является каналом.'}), 404
            
            # Владелец канала не может просто "отписаться" от своего канала; он должен его удалить
            if user_id == chat_info['owner_id']:
                return jsonify({'error': 'Владелец не может отписаться от собственного канала. Для удаления канала используйте DELETE /api/chats/<id>.'}), 403

            cursor.execute(
                "DELETE FROM channel_subscribers WHERE channel_id = ? AND user_id = ?",
                (channel_id, user_id)
            )
            if cursor.rowcount == 0:
                return jsonify({'error': 'Вы не подписаны на этот канал.'}), 404
            
            db.commit()

            return jsonify({'message': 'Вы успешно отписались от канала.'}), 200
        except Exception as e:
            db.rollback()
            print(f"Ошибка при отписке от канала: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/api/channels/<int:channel_id>/subscribe', methods=['POST'])
    @login_required
    def subscribe_channel(channel_id):
        user_id = g.user['id']
        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute("SELECT type FROM chats WHERE id = ?", (channel_id,))
            chat_info = cursor.fetchone()
            if not chat_info or chat_info['type'] != 'channel':
                return jsonify({'error': 'Чат не найден или не является каналом.'}), 404
            
            cursor.execute(
                "SELECT id FROM channel_subscribers WHERE channel_id = ? AND user_id = ?",
                (channel_id, user_id)
            )
            if cursor.fetchone():
                return jsonify({'error': 'Вы уже подписаны на этот канал.'}), 409

            cursor.execute(
                "INSERT INTO channel_subscribers (channel_id, user_id) VALUES (?, ?)",
                (channel_id, user_id)
            )
            db.commit()

            return jsonify({'message': 'Вы успешно подписались на канал.'}), 201
        except Exception as e:
            db.rollback()
            print(f"Ошибка при подписке на канал: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/api/users/search', methods=['GET'])
    @login_required
    def search_users():
        query = request.args.get('query')
        if not query:
            return jsonify({'users': []}), 200 # Возвращаем пустой список, если нет запроса
        
        db = get_db()
        cursor = db.cursor()
        try:
            # Ищем по username или display_name, исключая удаленных пользователей
            cursor.execute(
                "SELECT id, username, display_name, avatar_url FROM users WHERE (username LIKE ? OR display_name LIKE ?) AND is_deleted = FALSE LIMIT 10",
                (f'%{query}%', f'%{query}%')
            )
            users = cursor.fetchall()
            return jsonify({'users': users}), 200
        except Exception as e:
            print(f"Ошибка при поиске пользователей: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()


    # --- API для Управления Сообщениями ---

    @app.route('/api/chats/<int:chat_id>/messages', methods=['POST'])
    @login_required
    def send_message(chat_id):
        sender_id = g.user['id']
        db = get_db()
        cursor = db.cursor()

        try:
            # Проверяем, существует ли чат
            cursor.execute("SELECT type FROM chats WHERE id = ?", (chat_id,))
            chat_info = cursor.fetchone()
            if not chat_info:
                return jsonify({'error': 'Чат не найден.'}), 404
            
            chat_type = chat_info['type']

            # Проверяем, что отправитель является участником чата и имеет право писать
            can_send_message = False
            if chat_type == 'private':
                cursor.execute(
                    "SELECT 1 FROM private_chats WHERE chat_id = ? AND (user1_id = ? OR user2_id = ?)",
                    (chat_id, sender_id, sender_id)
                )
                if cursor.fetchone():
                    can_send_message = True
            elif chat_type == 'group':
                cursor.execute(
                    "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
                    (chat_id, sender_id)
                )
                member_info = cursor.fetchone()
                # Только админы и обычные участники могут писать. 'restricted' не могут.
                if member_info and member_info['role'] in ['admin', 'member']:
                    can_send_message = True
            elif chat_type == 'channel':
                # В канале могут писать только владельцы
                cursor.execute(
                    "SELECT owner_id FROM chats WHERE id = ?",
                    (chat_id,)
                )
                channel_owner_info = cursor.fetchone()
                if channel_owner_info and channel_owner_info['owner_id'] == sender_id:
                    can_send_message = True
                
            if not can_send_message:
                return jsonify({'error': 'У вас нет прав для отправки сообщений в этот чат.'}), 403

            # Обработка текстовых сообщений
            if request.is_json and 'content' in request.json:
                message_type = 'text'
                content = request.json['content']
                if not content or not content.strip():
                    return jsonify({'error': 'Текстовое сообщение не может быть пустым.'}), 400
                
                cursor.execute(
                    "INSERT INTO messages (chat_id, sender_id, message_type, content) VALUES (?, ?, ?, ?)",
                    (chat_id, sender_id, message_type, content.strip())
                )
                db.commit()
                message_id = cursor.lastrowid
                return jsonify({'message': 'Текстовое сообщение отправлено', 'message_id': message_id}), 201

            # Обработка файловых сообщений (если файл загружен)
            elif 'file' in request.files:
                file = request.files['file']
                if file.filename == '':
                    return jsonify({'error': 'Файл не выбран.'}), 400
                
                if file and allowed_file(file.filename):
                    original_filename = file.filename
                    # Генерируем уникальное имя файла для хранения
                    filename = str(uuid.uuid4()) + '.' + original_filename.rsplit('.', 1)[1].lower()
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    
                    file_size = os.path.getsize(file_path) # Получаем размер файла

                    message_type = 'file'
                    # _external=True необходимо для создания полного URL, доступного извне
                    file_url = url_for('uploaded_file', filename=filename, _external=True)

                    cursor.execute(
                        "INSERT INTO messages (chat_id, sender_id, message_type, file_url, file_name, file_size) VALUES (?, ?, ?, ?, ?, ?)",
                        (chat_id, sender_id, message_type, file_url, original_filename, file_size)
                    )
                    db.commit()
                    message_id = cursor.lastrowid
                    return jsonify({'message': 'Файловое сообщение отправлено', 'message_id': message_id, 'file_url': file_url, 'file_name': original_filename, 'file_size': file_size}), 201
                else:
                    return jsonify({'error': 'Недопустимый тип файла или файл слишком большой.'}), 400
            else:
                return jsonify({'error': 'Необходимо предоставить либо "content" (текст), либо "file" (файл).'}), 400

        except Exception as e:
            db.rollback()
            print(f"Ошибка при отправке сообщения: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        """Маршрут для отдачи загруженных файлов."""
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    @app.route('/api/chats/<int:chat_id>/messages', methods=['GET'])
    @login_required
    def get_messages(chat_id):
        user_id = g.user['id']
        db = get_db()
        cursor = db.cursor()

        try:
            # Проверяем доступ пользователя к чату
            is_member = False
            cursor.execute("SELECT type FROM chats WHERE id = ?", (chat_id,))
            chat_info = cursor.fetchone()
            if not chat_info:
                return jsonify({'error': 'Чат не найден.'}), 404
            
            chat_type = chat_info['type']

            if chat_type == 'private':
                cursor.execute(
                    "SELECT 1 FROM private_chats WHERE chat_id = ? AND (user1_id = ? OR user2_id = ?)",
                    (chat_id, user_id, user_id)
                )
                is_member = cursor.fetchone() is not None
            elif chat_type == 'group':
                cursor.execute(
                    "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
                    (chat_id, user_id)
                )
                is_member = cursor.fetchone() is not None
            elif chat_type == 'channel':
                cursor.execute(
                    "SELECT 1 FROM channel_subscribers WHERE channel_id = ? AND user_id = ?",
                    (chat_id, user_id)
                )
                is_member = cursor.fetchone() is not None
            
            if not is_member:
                return jsonify({'error': 'У вас нет доступа к этому чату.'}), 403

            # Получаем сообщения для чата
            # LEFT JOIN с users для получения display_name отправителя.
            # CASE WHEN u.is_deleted = TRUE OR u.id IS NULL для отображения "Удаленный пользователь"
            cursor.execute(
                """
                SELECT
                    m.id,
                    m.chat_id,
                    m.sender_id,
                    CASE
                        WHEN u.is_deleted = TRUE OR u.id IS NULL THEN 'Удаленный пользователь'
                        ELSE u.display_name
                    END AS sender_display_name,
                    CASE
                        WHEN u.is_deleted = TRUE OR u.id IS NULL THEN NULL -- Аватар удаленного пользователя
                        ELSE u.avatar_url
                    END AS sender_avatar_url,
                    m.message_type,
                    m.content,
                    m.file_url,
                    m.file_name,
                    m.file_size,
                    m.sent_at,
                    m.is_deleted
                FROM messages m
                LEFT JOIN users u ON m.sender_id = u.id
                WHERE m.chat_id = ?
                ORDER BY m.sent_at ASC
                """,
                (chat_id,)
            )
            messages = cursor.fetchall()

            # Форматируем сообщения для ответа
            formatted_messages = []
            for msg in messages:
                formatted_msg = {
                    'id': msg['id'],
                    'chat_id': msg['chat_id'],
                    'sender_id': msg['sender_id'],
                    'sender_display_name': msg['sender_display_name'],
                    'sender_avatar_url': msg['sender_avatar_url'],
                    'message_type': msg['message_type'],
                    'sent_at': msg['sent_at'],
                    'is_deleted': bool(msg['is_deleted'])
                }
                if not formatted_msg['is_deleted']: # Отображаем контент, только если сообщение не удалено
                    if msg['message_type'] == 'text':
                        formatted_msg['content'] = msg['content']
                    elif msg['message_type'] == 'file':
                        formatted_msg['file_url'] = msg['file_url']
                        formatted_msg['file_name'] = msg['file_name']
                        formatted_msg['file_size'] = msg['file_size']
                else: # Если сообщение удалено, скрываем контент
                    formatted_msg['content'] = '[Сообщение удалено]'
                    formatted_msg['file_url'] = None
                    formatted_msg['file_name'] = None
                    formatted_msg['file_size'] = None

                formatted_messages.append(formatted_msg)

            return jsonify({'messages': formatted_messages}), 200

        except Exception as e:
            print(f"Ошибка при получении сообщений: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    @app.route('/api/messages/<int:message_id>', methods=['DELETE'])
    @login_required
    def delete_message(message_id):
        user_id = g.user['id']
        db = get_db()
        cursor = db.cursor()

        try:
            # Получаем информацию о сообщении и его отправителе
            cursor.execute(
                "SELECT chat_id, sender_id, is_deleted FROM messages WHERE id = ?",
                (message_id,)
            )
            message_info = cursor.fetchone()

            if not message_info:
                return jsonify({'error': 'Сообщение не найдено.'}), 404
            
            if message_info['is_deleted']:
                return jsonify({'message': 'Сообщение уже удалено.'}), 200

            chat_id = message_info['chat_id']
            sender_id = message_info['sender_id']

            # Проверяем, что пользователь имеет право удалить сообщение:
            # 1. Отправитель может удалить своё сообщение.
            # 2. Админ группы может удалить любое сообщение в своей группе.
            # 3. Владелец канала может удалить любое сообщение в своём канале.

            can_delete = False
            if sender_id == user_id:
                can_delete = True # Отправитель может удалить своё сообщение
            else:
                # Проверяем, является ли пользователь админом группы или владельцем канала
                cursor.execute("SELECT type, owner_id FROM chats WHERE id = ?", (chat_id,))
                chat_details = cursor.fetchone()
                chat_type = chat_details['type']
                owner_id = chat_details['owner_id']
                
                if chat_type == 'group':
                    cursor.execute(
                        "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
                        (chat_id, user_id)
                    )
                    member_role = cursor.fetchone()
                    if member_role and member_role['role'] == 'admin':
                        can_delete = True
                elif chat_type == 'channel':
                    # Только владелец канала может удалять сообщения
                    if user_id == owner_id:
                        can_delete = True

            if not can_delete:
                return jsonify({'error': 'У вас нет прав на удаление этого сообщения.'}), 403

            # Выполняем мягкое удаление сообщения
            # Обнуляем content, file_url, file_name, file_size при удалении
            cursor.execute(
                "UPDATE messages SET is_deleted = TRUE, deleted_by = ?, content = NULL, file_url = NULL, file_name = NULL, file_size = NULL WHERE id = ?",
                (user_id, message_id)
            )
            db.commit()

            return jsonify({'message': 'Сообщение успешно удалено.'}), 200
        except Exception as e:
            db.rollback()
            print(f"Ошибка при удалении сообщения: {e}")
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        finally:
            cursor.close()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', debug=True, port=5125)