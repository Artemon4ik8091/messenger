import sys
import requests
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QListWidget, QTextEdit, QLineEdit, QPushButton, QLabel,
                             QDialog, QFormLayout, QMessageBox, QFileDialog, QInputDialog, QMenu,
                             QListWidgetItem, QDialogButtonBox)
from PyQt6.QtCore import Qt, QTimer, QUrl, QPoint
from PyQt6.QtGui import QDesktopServices, QAction, QTextCursor, QMouseEvent
import os
import configparser

CONFIG_FILE = 'client_config.ini'

class CustomQTextEdit(QTextEdit):
    def mouseReleaseEvent(self, event: QMouseEvent):
        super().mouseReleaseEvent(event)

        if event.button() == Qt.MouseButton.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            char_format = cursor.charFormat()
            if char_format.anchorHref():
                url = char_format.anchorHref()
                QDesktopServices.openUrl(QUrl(url))
                event.accept()
                return
        event.ignore()

class ApiClient:
    BASE_URL = ""

    def __init__(self):
        self.session = requests.Session()
        self.user_id = None
        self.auth_token = None

    def set_base_url(self, address, port):
        self.BASE_URL = f"http://{address}:{port}"
        print(f"API Base URL установлен на: {self.BASE_URL}")

    def register(self, username, password, display_name):
        url = f"{self.BASE_URL}/api/register"
        data = {
            "username": username,
            "password": password,
            "display_name": display_name
        }
        response = self.session.post(url, json=data)
        return response

    def login(self, username, password):
        url = f"{self.BASE_URL}/api/login"
        data = {"username": username, "password": password}
        response = self.session.post(url, json=data)
        if response.status_code == 200:
            self.user_id = response.json()['user']['id']
        return response

    def logout(self):
        url = f"{self.BASE_URL}/api/logout"
        response = self.session.post(url)
        if response.status_code == 200:
            self.user_id = None
            self.auth_token = None
        return response

    def get_users(self):
        url = f"{self.BASE_URL}/api/users"
        response = self.session.get(url)
        return response.json() if response.status_code == 200 else []

    def get_chats(self):
        url = f"{self.BASE_URL}/api/chats"
        response = self.session.get(url)
        if response.status_code == 200:
            try:
                data = response.json()
                if isinstance(data, dict) and 'chats' in data and isinstance(data['chats'], list):
                    return data['chats']
                elif isinstance(data, list):
                    return data
                else:
                    print(f"Предупреждение: Сервер вернул неожиданный формат чатов: {data}")
                    return []
            except requests.exceptions.JSONDecodeError:
                print(f"Ошибка декодирования JSON для /api/chats: {response.text}")
                return []
        else:
            print(f"Ошибка при получении чатов, статус: {response.status_code}, ответ: {response.text}")
            return []


    def get_chat_messages(self, chat_id):
        url = f"{self.BASE_URL}/api/chats/{chat_id}/messages"
        response = self.session.get(url)
        if response.status_code == 200:
            try:
                data = response.json()
                if isinstance(data, dict) and 'messages' in data and isinstance(data['messages'], list):
                    return data['messages']
                elif isinstance(data, list):
                    return data
                else:
                    print(f"Предупреждение: Сервер вернул неожиданный формат сообщений: {data}")
                    return []
            except requests.exceptions.JSONDecodeError:
                print(f"Ошибка декодирования JSON для /api/chats/{chat_id}/messages: {response.text}")
                return []
        else:
            print(f"Ошибка при получении сообщений для чата {chat_id}, статус: {response.status_code}, ответ: {response.text}")
            return []

    def send_text_message(self, chat_id, content):
        url = f"{self.BASE_URL}/api/chats/{chat_id}/messages"
        data = {"message_type": "text", "content": content}
        response = self.session.post(url, json=data)
        return response

    def send_file_message(self, chat_id, file_path):
        url = f"{self.BASE_URL}/api/chats/{chat_id}/messages"
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
                data = {"message_type": "file"}
                response = self.session.post(url, files=files, data=data)
            return response
        except FileNotFoundError:
            QMessageBox.critical(None, "Ошибка", "Файл не найден.")
            return None

    def get_file_url(self, filename):
        return f"{self.BASE_URL}/uploads/{filename}"

    def create_private_chat(self, username):
        url = f"{self.BASE_URL}/api/chats/private"
        data = {"username": username}
        response = self.session.post(url, json=data)
        return response

    def create_group_chat(self, chat_name, member_ids):
        url = f"{self.BASE_URL}/api/chats/group"
        data = {"name": chat_name, "member_ids": member_ids}
        response = self.session.post(url, json=data)
        return response

    def create_channel(self, channel_name):
        url = f"{self.BASE_URL}/api/chats/channel"
        data = {"name": channel_name}
        response = self.session.post(url, json=data)
        return response

    def add_group_member(self, chat_id, user_id):
        url = f"{self.BASE_URL}/api/chats/{chat_id}/members"
        data = {"user_id": user_id}
        response = self.session.post(url, json=data)
        return response
    
    def leave_chat(self, chat_id):
        url = f"{self.BASE_URL}/api/chats/{chat_id}/leave"
        response = self.session.post(url)
        return response

    def delete_message(self, chat_id, message_id):
        url = f"{self.BASE_URL}/api/chats/{chat_id}/messages/{message_id}"
        response = self.session.delete(url)
        return response

class LoginDialog(QDialog):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.setWindowTitle("Вход / Регистрация")
        self.setGeometry(100, 100, 400, 250)

        self.layout = QFormLayout(self)

        self.address_input = QLineEdit("127.0.0.1")
        self.layout.addRow("Адрес сервера:", self.address_input)

        self.port_input = QLineEdit("5125")
        self.layout.addRow("Порт сервера:", self.port_input)

        self.username_input = QLineEdit()
        self.layout.addRow("Имя пользователя:", self.username_input)

        self.display_name_input = QLineEdit()
        self.layout.addRow("Отображаемое имя (для регистрации):", self.display_name_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.layout.addRow("Пароль:", self.password_input)

        self.login_button = QPushButton("Вход")
        self.login_button.clicked.connect(self.login)
        self.layout.addRow(self.login_button)

        self.register_button = QPushButton("Регистрация")
        self.register_button.clicked.connect(self.register)
        self.layout.addRow(self.register_button)

        self.load_config()

    def load_config(self):
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
            if 'Connection' in config:
                self.address_input.setText(config['Connection'].get('address', "127.0.0.1"))
                self.port_input.setText(config['Connection'].get('port', "5125"))
                self.username_input.setText(config['Connection'].get('username', ""))
            print("Конфигурация загружена.")

    def save_config(self, username):
        config = configparser.ConfigParser()
        config['Connection'] = {
            'address': self.address_input.text(),
            'port': self.port_input.text(),
            'username': username
        }
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        print("Конфигурация сохранена.")

    def login(self):
        address = self.address_input.text()
        port = self.port_input.text()
        try:
            port = int(port)
        except ValueError:
            QMessageBox.critical(self, "Ошибка", "Порт должен быть числом.")
            return

        self.api_client.set_base_url(address, port)

        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Ошибка", "Имя пользователя и пароль не могут быть пустыми.")
            return

        response = self.api_client.login(username, password)
        if response.status_code == 200:
            QMessageBox.information(self, "Успех", "Вход выполнен успешно!")
            self.save_config(username)
            self.accept()
        else:
            error = response.json().get('error', 'Неизвестная ошибка входа')
            QMessageBox.critical(self, "Ошибка", f"Ошибка входа: {error}")

    def register(self):
        address = self.address_input.text()
        port = self.port_input.text()
        try:
            port = int(port)
        except ValueError:
            QMessageBox.critical(self, "Ошибка", "Порт должен быть числом.")
            return

        self.api_client.set_base_url(address, port)

        username = self.username_input.text()
        password = self.password_input.text()
        display_name = self.display_name_input.text()

        if not username or not password or not display_name:
            QMessageBox.warning(self, "Ошибка", "Все поля для регистрации должны быть заполнены.")
            return

        response = self.api_client.register(username, password, display_name)
        if response.status_code == 201:
            QMessageBox.information(self, "Успех", "Регистрация успешна! Теперь вы можете войти.")
            self.save_config(username)
        else:
            error = response.json().get('error', 'Неизвестная ошибка регистрации')
            QMessageBox.critical(self, "Ошибка", error)

class ChatWindow(QMainWindow):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.current_chat_id = None
        self.current_chat_type = None
        self.setWindowTitle("Мессенджер")
        self.setGeometry(100, 100, 800, 600)

        self.init_ui()
        self.load_chats()

        self.message_refresh_timer = QTimer(self)
        self.message_refresh_timer.setInterval(3000)
        self.message_refresh_timer.timeout.connect(self.load_messages)
        self.message_refresh_timer.start()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        self.left_panel_layout = QVBoxLayout()
        self.main_layout.addLayout(self.left_panel_layout, 1)

        self.chat_list_label = QLabel("Чаты")
        self.left_panel_layout.addWidget(self.chat_list_label)

        self.chat_list = QListWidget()
        self.chat_list.itemClicked.connect(self.select_chat)
        self.chat_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self.show_chat_context_menu)
        self.left_panel_layout.addWidget(self.chat_list)

        self.create_chat_button = QPushButton("Создать чат")
        self.create_chat_button.clicked.connect(self.show_create_chat_menu)
        self.left_panel_layout.addWidget(self.create_chat_button)

        self.leave_chat_button = QPushButton("Покинуть чат")
        self.leave_chat_button.clicked.connect(self.leave_current_chat)
        self.left_panel_layout.addWidget(self.leave_chat_button)

        self.refresh_chats_button = QPushButton("Обновить чаты")
        self.refresh_chats_button.clicked.connect(self.load_chats)
        self.left_panel_layout.addWidget(self.refresh_chats_button)

        self.right_panel_layout = QVBoxLayout()
        self.main_layout.addLayout(self.right_panel_layout, 3)

        self.current_chat_label = QLabel("Выберите чат")
        self.current_chat_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_panel_layout.addWidget(self.current_chat_label)

        self.messages_display = CustomQTextEdit()
        self.messages_display.setReadOnly(True)
        self.messages_display.setHtml("<h1>Добро пожаловать в мессенджер!</h1>")
        self.messages_display.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | 
            Qt.TextInteractionFlag.TextSelectableByKeyboard |
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.messages_display.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.messages_display.customContextMenuRequested.connect(self.show_message_context_menu)

        self.right_panel_layout.addWidget(self.messages_display)

        self.message_input_layout = QHBoxLayout()
        self.right_panel_layout.addLayout(self.message_input_layout)

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Введите сообщение...")
        self.message_input.returnPressed.connect(self.send_text_message)
        self.message_input_layout.addWidget(self.message_input)

        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send_text_message)
        self.message_input_layout.addWidget(self.send_button)

        self.attach_file_button = QPushButton("Прикрепить файл")
        self.attach_file_button.clicked.connect(self.send_file_message)
        self.message_input_layout.addWidget(self.attach_file_button)

    def show_create_chat_menu(self):
        menu = QMenu(self)
        menu.addAction("Приватный чат", self.create_private_chat_dialog)
        menu.addAction("Групповой чат", self.create_group_chat_dialog)
        menu.addAction("Канал", self.create_channel_dialog)
        menu.exec(self.create_chat_button.mapToGlobal(self.create_chat_button.rect().bottomLeft()))

    def create_private_chat_dialog(self):
        users = self.api_client.get_users()
        print(f"Пользователи, полученные от API: {users}") # ДОБАВЛЕННЫЙ ОТЛАДОЧНЫЙ ВЫВОД

        # Исключаем текущего пользователя из списка
        other_users = [user for user in users if user.get('id') != self.api_client.user_id]

        if not other_users:
            QMessageBox.information(self, "Информация", "Нет других пользователей для создания приватного чата.")
            return

        user_selection_dialog = QDialog(self)
        user_selection_dialog.setWindowTitle("Выберите пользователя для приватного чата")
        user_selection_layout = QVBoxLayout(user_selection_dialog)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Поиск пользователей...")
        user_selection_layout.addWidget(search_input)

        user_list_widget = QListWidget()
        user_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        user_selection_layout.addWidget(user_list_widget)

        # Сохраняем исходный список пользователей для фильтрации
        # В ItemDataRole.UserRole будем хранить username
        for user in other_users:
            display_name = user.get('display_name', 'Неизвестный пользователь')
            username = user.get('username')
            if username: # Убедимся, что username доступен
                item = QListWidgetItem(f"{display_name} (@{username})") # Отображаем display_name и username
                item.setData(Qt.ItemDataRole.UserRole, username) # Сохраняем username
                user_list_widget.addItem(item)
            else:
                print(f"Предупреждение: Пользователь {display_name} не имеет username.")

        def filter_users(text):
            text = text.lower()
            for i in range(user_list_widget.count()):
                item = user_list_widget.item(i)
                # Проверяем как по отображаемому имени, так и по username
                item_text = item.text().lower()
                if text in item_text:
                    item.setHidden(False)
                else:
                    item.setHidden(True)

        search_input.textChanged.connect(filter_users)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(user_selection_dialog.accept)
        button_box.rejected.connect(user_selection_dialog.reject)
        user_selection_layout.addWidget(button_box)

        selected_username = None
        if user_selection_dialog.exec() == QDialog.DialogCode.Accepted:
            selected_items = user_list_widget.selectedItems()
            if selected_items:
                selected_item = selected_items[0]
                selected_username = selected_item.data(Qt.ItemDataRole.UserRole)
                print(f"Попытка создать приватный чат с username: {selected_username}") # Отладочный вывод

        if selected_username:
            response = self.api_client.create_private_chat(selected_username)
            if response.status_code == 201:
                QMessageBox.information(self, "Успех", f"Приватный чат с {selected_username} создан.")
                self.load_chats()
            else:
                error = response.json().get('error', 'Ошибка создания приватного чата')
                QMessageBox.critical(self, "Ошибка", f"Ошибка создания приватного чата: {error}")
        else:
            QMessageBox.information(self, "Отмена", "Создание приватного чата отменено или пользователь не выбран.")


    def create_group_chat_dialog(self):
        chat_name, ok = QInputDialog.getText(self, "Создать групповой чат", "Введите название чата:")
        if not ok or not chat_name:
            return

        users = self.api_client.get_users()
        other_users = [user for user in users if user['id'] != self.api_client.user_id]
        
        member_ids = []
        member_names = [user['display_name'] for user in other_users]
        user_map = {user['display_name']: user['id'] for user in other_users}

        members_dialog = QDialog(self)
        members_dialog.setWindowTitle("Выберите участников (необязательно)")
        members_layout = QVBoxLayout(members_dialog)
        
        member_list_widget = QListWidget()
        member_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for name in member_names:
            member_list_widget.addItem(name)
        members_layout.addWidget(member_list_widget)

        ok_button = QPushButton("ОК")
        ok_button.clicked.connect(members_dialog.accept)
        members_layout.addWidget(ok_button)

        if members_dialog.exec() == QDialog.DialogCode.Accepted:
            selected_items = member_list_widget.selectedItems()
            for item in selected_items:
                member_ids.append(user_map[item.text()])
            
            # Если не выбраны участники, сервер должен сам добавить создателя.
            # Эта проверка теперь не блокирует создание чата, если других пользователей нет.
            
            response = self.api_client.create_group_chat(chat_name, member_ids)
            if response.status_code == 201:
                QMessageBox.information(self, "Успех", "Групповой чат создан.")
                self.load_chats()
            else:
                error = response.json().get('error', 'Ошибка создания группового чата')
                QMessageBox.critical(self, "Ошибка", error)

    def create_channel_dialog(self):
        channel_name, ok = QInputDialog.getText(self, "Создать канал", "Введите название канала:")
        if not ok or not channel_name:
            return

        response = self.api_client.create_channel(channel_name)
        if response.status_code == 201:
            QMessageBox.information(self, "Успех", "Канал создан.")
            self.load_chats()
        else:
            error = response.json().get('error', 'Ошибка создания канала')
            QMessageBox.critical(self, "Ошибка", error)

    def load_chats(self):
        self.chat_list.clear()
        chats = self.api_client.get_chats()
        for chat in chats:
            if isinstance(chat, dict) and 'id' in chat and 'name' in chat and 'type' in chat:
                item = QListWidgetItem(chat['name'])
                item.setData(Qt.ItemDataRole.UserRole, chat['id'])
                item.setData(Qt.ItemDataRole.UserRole + 1, chat['type'])
                self.chat_list.addItem(item)
            else:
                print(f"Предупреждение: Пропущен некорректный элемент чата: {chat}")
        
        if self.current_chat_id:
            for i in range(self.chat_list.count()):
                item = self.chat_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == self.current_chat_id:
                    self.chat_list.setCurrentItem(item)
                    break

    def select_chat(self, item):
        self.current_chat_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_chat_type = item.data(Qt.ItemDataRole.UserRole + 1)
        self.current_chat_label.setText(f"Чат: {item.text()} ({self.current_chat_type})")
        self.load_messages()

    def load_messages(self):
        if not self.current_chat_id:
            self.messages_display.clear()
            return

        messages_data = self.api_client.get_chat_messages(self.current_chat_id)
        self.messages_display.clear()

        current_user_id = self.api_client.user_id

        if not isinstance(messages_data, list):
            print(f"Ошибка: Полученные данные сообщений не являются списком: {messages_data}")
            self.messages_display.setHtml("<p>Ошибка загрузки сообщений: получены некорректные данные.</p>")
            return

        if not messages_data:
            self.messages_display.setHtml("<p>Сообщений пока нет.</p>")
            return

        html_content = ""
        for message in messages_data:
            if not isinstance(message, dict):
                print(f"Предупреждение: Пропущен некорректный элемент сообщения (не словарь): {message}")
                continue

            sender_id = message.get('sender_id')
            sender_display_name = message.get('sender_display_name', 'Неизвестный')
            content = message.get('content')
            sent_at = message.get('sent_at', 'Неизвестно время')
            message_type = message.get('message_type')
            message_id = message.get('id')
            is_deleted = message.get('is_deleted', False)

            if sender_id == current_user_id:
                msg_class = "my-message"
                sender_info = "Я"
            else:
                msg_class = "other-message"
                sender_info = sender_display_name
            
            msg_html = f"<div class='message {msg_class}' data-message-id='{message_id}'>"
            msg_html += f"<div class='message-header'><span class='sender'>{sender_info}</span> <span class='timestamp'>{sent_at}</span></div>"

            if is_deleted:
                msg_html += "<div class='message-content deleted-message'><i>Сообщение удалено.</i></div>"
            elif message_type == 'text':
                msg_html += f"<div class='message-content'>{content}</div>"
            elif message_type == 'file':
                file_name = message.get('file_name', 'файл')
                file_url = message.get('file_url')
                file_size = message.get('file_size')
                
                if file_url:
                    full_file_url = self.api_client.get_file_url(file_name)
                    file_info = f"{file_name} ({file_size / (1024*1024):.2f} MB)" if file_size else file_name 
                    msg_html += f"<div class='message-content file-content'><a href='{full_file_url}'>{file_info}</a></div>"
                else:
                    msg_html += f"<div class='message-content file-content'>[Неизвестный файл]</div>"
            
            msg_html += "</div>"
            html_content += msg_html

        css = """
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 10px; }
            .message {
                border-radius: 10px;
                padding: 8px 12px;
                margin-bottom: 10px;
                max-width: 70%;
                word-wrap: break-word;
                clear: both;
            }
            .my-message {
                margin-left: auto;
                text-align: right;
            }
            .other-message {
                margin-right: auto;
                text-align: left;
            }
            .message-header {
                font-size: 0.8em;
                color: #555;
                margin-bottom: 5px;
            }
            .sender {
                font-weight: bold;
            }
            .timestamp {
                color: #888;
                margin-left: 10px;
            }
            .message-content {
                font-size: 1em;
            }
            .file-content a {
                color: #007bff;
                text-decoration: none;
            }
            .file-content a:hover {
                text-decoration: underline;
            }
            .deleted-message {
                color: #888;
                font-style: italic;
            }
        </style>
        """
        self.messages_display.setHtml(css + html_content)
        self.messages_display.verticalScrollBar().setValue(self.messages_display.verticalScrollBar().maximum())

    def show_message_context_menu(self, pos):
        cursor = self.messages_display.cursorForPosition(pos)
        
        if cursor.charFormat().anchorHref():
            return
            
        block = self.messages_display.document().findBlock(cursor.position())
        line_number = block.blockNumber()

        messages = self.api_client.get_chat_messages(self.current_chat_id)
        
        selected_message = None
        if line_number < len(messages):
            selected_message = messages[line_number]

        can_delete = False
        if selected_message and not selected_message['is_deleted']:
            if selected_message['sender_id'] == self.api_client.user_id:
                can_delete = True
            elif self.current_chat_type in ['group', 'channel']:
                can_delete = True 
        
        if can_delete:
            menu = QMenu(self)
            delete_action = QAction("Удалить сообщение", self)
            delete_action.triggered.connect(lambda: self.delete_selected_message(selected_message['id']))
            menu.addAction(delete_action)
            menu.exec(self.messages_display.mapToGlobal(pos))

    def delete_selected_message(self, message_id):
        if QMessageBox.question(self, "Подтверждение удаления", "Вы уверены, что хотите удалить это сообщение?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            response = self.api_client.delete_message(self.current_chat_id, message_id)
            if response.status_code == 200:
                QMessageBox.information(self, "Успех", "Сообщение успешно удалено.")
                self.load_messages()
            else:
                error = response.json().get('error', 'Ошибка удаления сообщения')
                QMessageBox.critical(self, "Ошибка", error)

    def send_text_message(self):
        if not self.current_chat_id:
            QMessageBox.warning(self, "Ошибка", "Выберите чат для отправки сообщения")
            return

        text = self.message_input.text().strip()
        if not text:
            return

        response = self.api_client.send_text_message(self.current_chat_id, text)

        if response.status_code == 201:
            self.message_input.clear()
            self.load_messages()
        else:
            error = response.json().get('error', 'Ошибка отправки сообщения')
            QMessageBox.critical(self, "Ошибка", error)

    def send_file_message(self):
        if not self.current_chat_id:
            QMessageBox.warning(self, "Ошибка", "Выберите чат для отправки файла")
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите файл")
        if not file_path:
            return

        response = self.api_client.send_file_message(self.current_chat_id, file_path)

        if response and response.status_code == 201:
            self.load_messages()
        elif response:
            error = response.json().get('error', 'Ошибка отправки файла')
            QMessageBox.critical(self, "Ошибка", error)

    def leave_current_chat(self):
        if not self.current_chat_id:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите чат, чтобы покинуть его.")
            return
        
        chat_name = self.current_chat_label.text().replace("Чат: ", "").split(" (")[0]
        
        if QMessageBox.question(self, "Подтверждение", f"Вы уверены, что хотите покинуть чат '{chat_name}'?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._execute_leave_chat(self.current_chat_id, chat_name) # Вызов новой вспомогательной функции

    def _execute_leave_chat(self, chat_id_to_leave, chat_name): # Новая вспомогательная функция
            print(f"DEBUG (Client): Попытка покинуть чат с ID: {chat_id_to_leave} и именем: '{chat_name}'") # ОТЛАДОЧНЫЙ ВЫВОД
            response = self.api_client.leave_chat(chat_id_to_leave)
            if response.status_code == 200:
                if response.text:
                    try:
                        message = response.json().get('message', f"Вы покинули чат '{chat_name}'.")
                    except requests.exceptions.JSONDecodeError:
                        message = f"Вы покинули чат '{chat_name}'. (Сервер вернул неожиданный ответ, но статус 200 OK)"
                else:
                    message = f"Вы покинули чат '{chat_name}'. (Сервер вернул пустой ответ, но статус 200 OK)"

                QMessageBox.information(self, "Успех", message)
                # Если покидаемый чат был текущим выбранным, сбросим выбор
                if self.current_chat_id == chat_id_to_leave:
                    self.current_chat_id = None
                    self.current_chat_type = None
                    self.current_chat_label.setText("Выберите чат")
                    self.messages_display.clear()
                    self.messages_display.setHtml("<h1>Добро пожаловать в мессенджер!</h1>")
                self.load_chats() # Всегда обновляем список чатов, чтобы изменения были видны
            else:
                error = "Неизвестная ошибка при попытке покинуть чат."
                if response.text:
                    try:
                        error = response.json().get('error', response.text)
                    except requests.exceptions.JSONDecodeError:
                        error = f"Сервер вернул ошибку {response.status_code}, но невалидный JSON: {response.text}"
                else:
                    error = f"Сервер вернул ошибку {response.status_code} с пустым ответом."
                QMessageBox.critical(self, "Ошибка", error)

    def show_chat_context_menu(self, pos):
        item = self.chat_list.itemAt(pos)
        if item:
            chat_id = item.data(Qt.ItemDataRole.UserRole)
            chat_type = item.data(Qt.ItemDataRole.UserRole + 1)
            
            menu = QMenu(self)
            
            if chat_type == 'group':
                add_member_action = QAction("Добавить участника", self)
                add_member_action.triggered.connect(lambda: self.add_member_to_group_chat_dialog(chat_id))
                menu.addAction(add_member_action)

            leave_action = QAction("Покинуть чат", self)
            leave_action.triggered.connect(lambda: self.leave_current_chat_from_menu(chat_id))
            menu.addAction(leave_action)
            
            menu.exec(self.chat_list.mapToGlobal(pos))

    def leave_current_chat_from_menu(self, chat_id_to_leave):
        chat_name_to_leave = "Неизвестный чат"
        for i in range(self.chat_list.count()):
            item = self.chat_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == chat_id_to_leave:
                chat_name_to_leave = item.text()
                break # Нашли имя чата, выходим из цикла
        
        if QMessageBox.question(self, "Подтверждение", f"Вы уверены, что хотите покинуть чат '{chat_name_to_leave}'?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._execute_leave_chat(chat_id_to_leave, chat_name_to_leave) # Используем новую вспомогательную функцию

    def add_member_to_group_chat_dialog(self, chat_id):
        users = self.api_client.get_users()
        # Исключаем текущего пользователя из списка
        other_users = [user for user in users if user.get('id') != self.api_client.user_id]

        if not other_users:
            QMessageBox.information(self, "Информация", "Нет других пользователей для добавления.")
            return

        user_selection_dialog = QDialog(self)
        user_selection_dialog.setWindowTitle("Добавить участника в группу")
        user_selection_layout = QVBoxLayout(user_selection_dialog)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Поиск пользователей...")
        user_selection_layout.addWidget(search_input)

        user_list_widget = QListWidget()
        user_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection) # Множественный выбор
        user_selection_layout.addWidget(user_list_widget)

        # Сохраняем исходный список пользователей для фильтрации
        # В ItemDataRole.UserRole будем хранить user_id
        for user in other_users:
            display_name = user.get('display_name', 'Неизвестный пользователь')
            user_id = user.get('id')
            username = user.get('username')
            if user_id:
                item = QListWidgetItem(f"{display_name} (@{username})") # Отображаем display_name и username
                item.setData(Qt.ItemDataRole.UserRole, user_id) # Сохраняем user_id
                user_list_widget.addItem(item)
            else:
                print(f"Предупреждение: Пользователь {display_name} не имеет ID.")


        def filter_users(text):
            text = text.lower()
            for i in range(user_list_widget.count()):
                item = user_list_widget.item(i)
                # Проверяем как по отображаемому имени, так и по username
                item_text = item.text().lower()
                if text in item_text:
                    item.setHidden(False)
                else:
                    item.setHidden(True)

        search_input.textChanged.connect(filter_users)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(user_selection_dialog.accept)
        button_box.rejected.connect(user_selection_dialog.reject)
        user_selection_layout.addWidget(button_box)

        selected_user_ids = []
        if user_selection_dialog.exec() == QDialog.DialogCode.Accepted:
            selected_items = user_list_widget.selectedItems()
            for item in selected_items:
                selected_user_ids.append(item.data(Qt.ItemDataRole.UserRole))

        if selected_user_ids:
            success_count = 0
            fail_count = 0
            for user_id_to_add in selected_user_ids:
                response = self.api_client.add_group_member(chat_id, user_id_to_add)
                if response.status_code == 200:
                    success_count += 1
                else:
                    fail_count += 1
                    error = response.json().get('error', 'Неизвестная ошибка')
                    print(f"Ошибка при добавлении пользователя с ID {user_id_to_add}: {error}")
            
            if success_count > 0:
                QMessageBox.information(self, "Успех", f"Добавлено {success_count} участник(ов).")
                self.load_messages() # Обновляем сообщения, чтобы увидеть добавленных участников
            if fail_count > 0:
                QMessageBox.warning(self, "Предупреждение", f"Не удалось добавить {fail_count} участник(ов).")
        else:
            QMessageBox.information(self, "Отмена", "Добавление участников отменено или никто не выбран.")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    api_client = ApiClient()
    login_dialog = LoginDialog(api_client)

    if login_dialog.exec() == QDialog.DialogCode.Accepted:
        chat_window = ChatWindow(api_client)
        chat_window.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)