import sys
import requests
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QListWidget, QTextEdit, QLineEdit, QPushButton, QLabel, 
                             QDialog, QFormLayout, QMessageBox, QFileDialog, QInputDialog, QMenu,
                             QListWidgetItem)
from PyQt6.QtCore import Qt, QTimer

class ApiClient:
    # BASE_URL теперь будет устанавливаться динамически
    BASE_URL = "" 
    
    def __init__(self):
        self.session = requests.Session()
        self.user_id = None
        self.auth_token = None

    # Добавляем метод для установки BASE_URL
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
    
    def get_user_chats(self):
        url = f"{self.BASE_URL}/api/chats"
        response = self.session.get(url)
        return response.json()['chats'] if response.status_code == 200 else []
    
    def get_chat_messages(self, chat_id):
        url = f"{self.BASE_URL}/api/chats/{chat_id}/messages"
        response = self.session.get(url)
        return response.json()['messages'] if response.status_code == 200 else []

    def send_text_message(self, chat_id, content):
        url = f"{self.BASE_URL}/api/chats/{chat_id}/messages"
        data = {"message_type": "text", "content": content}
        response = self.session.post(url, json=data)
        return response

    def send_file_message(self, chat_id, file_path):
        url = f"{self.BASE_URL}/api/chats/{chat_id}/messages"
        files = {'file': open(file_path, 'rb')}
        data = {"message_type": "file"}
        response = self.session.post(url, files=files, data=data)
        return response
    
    def delete_chat(self, chat_id):
        url = f"{self.BASE_URL}/api/chats/{chat_id}"
        response = self.session.delete(url)
        return response

    def delete_message(self, message_id):
        url = f"{self.BASE_URL}/api/messages/{message_id}"
        response = self.session.delete(url)
        return response

    def create_private_chat(self, target_username):
        url = f"{self.BASE_URL}/api/chats/private"
        data = {"target_username": target_username}
        response = self.session.post(url, json=data)
        return response

    def create_group_chat(self, name, member_usernames):
        url = f"{self.BASE_URL}/api/chats/group"
        data = {"name": name, "member_usernames": member_usernames}
        response = self.session.post(url, json=data)
        return response

    def create_channel(self, name):
        url = f"{self.BASE_URL}/api/chats/channel"
        data = {"name": name}
        response = self.session.post(url, json=data)
        return response

    def search_users(self, query):
        url = f"{self.BASE_URL}/api/users/search"
        params = {"query": query}
        response = self.session.get(url, params=params)
        return response.json().get('users', []) if response.status_code == 200 else []

    def add_group_member(self, group_id, username):
        url = f"{self.BASE_URL}/api/groups/{group_id}/members"
        data = {"username": username}
        response = self.session.post(url, json=data)
        return response

    def remove_group_member(self, group_id, user_id):
        url = f"{self.BASE_URL}/api/groups/{group_id}/members/{user_id}"
        response = self.session.delete(url)
        return response
    
    def add_channel_subscriber(self, channel_id, username): 
        url = f"{self.BASE_URL}/api/channels/{channel_id}/subscribers"
        data = {"username": username}
        response = self.session.post(url, json=data)
        return response

    def unsubscribe_channel(self, channel_id):
        url = f"{self.BASE_URL}/api/channels/{channel_id}/unsubscribe"
        response = self.session.delete(url)
        return response

    def get_file_url(self, filename):
        return f"{self.BASE_URL}/uploads/{filename}"

class LoginDialog(QDialog):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self.setWindowTitle("Вход / Регистрация")
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()

        # Новые поля для адреса и порта сервера
        self.server_address_input = QLineEdit("localhost") # Значение по умолчанию
        self.server_port_input = QLineEdit("5000") # Значение по умолчанию

        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.display_name_input = QLineEdit()

        layout.addRow("Адрес сервера:", self.server_address_input)
        layout.addRow("Порт сервера:", self.server_port_input)
        layout.addRow("Имя пользователя:", self.username_input)
        layout.addRow("Пароль:", self.password_input)
        layout.addRow("Отображаемое имя (для регистрации):", self.display_name_input)

        self.login_button = QPushButton("Вход")
        self.login_button.clicked.connect(self.handle_login)
        layout.addRow(self.login_button)

        self.register_button = QPushButton("Регистрация")
        self.register_button.clicked.connect(self.handle_register)
        layout.addRow(self.register_button)

        self.setLayout(layout)

    def _set_api_base_url(self):
        """Вспомогательная функция для установки BASE_URL перед запросами."""
        address = self.server_address_input.text().strip()
        port = self.server_port_input.text().strip()
        if not address or not port:
            QMessageBox.critical(self, "Ошибка", "Адрес и порт сервера не могут быть пустыми.")
            return False
        self.api_client.set_base_url(address, port)
        return True

    def handle_login(self):
        if not self._set_api_base_url():
            return

        username = self.username_input.text()
        password = self.password_input.text()
        response = self.api_client.login(username, password)
        if response.status_code == 200:
            self.accept()
        else:
            QMessageBox.critical(self, "Ошибка входа", response.json().get('error', 'Неверное имя пользователя или пароль'))

    def handle_register(self):
        if not self._set_api_base_url():
            return

        username = self.username_input.text()
        password = self.password_input.text()
        display_name = self.display_name_input.text()

        if not (username and password and display_name):
            QMessageBox.warning(self, "Ошибка регистрации", "Все обязательные поля для регистрации должны быть заполнены!")
            return

        response = self.api_client.register(username, password, display_name)
        if response.status_code == 201:
            QMessageBox.information(self, "Регистрация успешна", "Вы успешно зарегистрированы! Теперь войдите в систему.")
            self.username_input.clear()
            self.password_input.clear()
            self.display_name_input.clear()
        else:
            QMessageBox.critical(self, "Ошибка регистрации", response.json().get('error', 'Ошибка регистрации'))

class ChatWindow(QMainWindow):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self.current_chat_id = None
        self.current_chat_type = None 
        self.setWindowTitle("Мессенджер")
        self.setGeometry(100, 100, 1000, 700)
        self.init_ui()
        self.load_chats()

        # Таймер для периодического обновления сообщений
        self.message_timer = QTimer(self)
        self.message_timer.setInterval(3000) # Обновлять каждые 3 секунды
        self.message_timer.timeout.connect(self.load_messages)
        self.message_timer.start()

        # Таймер для периодического обновления списка чатов (опционально)
        self.chat_timer = QTimer(self)
        self.chat_timer.setInterval(10000) # Обновлять каждые 10 секунд
        self.chat_timer.timeout.connect(self.load_chats)
        self.chat_timer.start()


    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Левая панель - список чатов
        left_panel = QVBoxLayout()
        self.chats_list_widget = QListWidget()
        self.chats_list_widget.itemClicked.connect(self.chat_selected)
        left_panel.addWidget(QLabel("Чаты:"))
        left_panel.addWidget(self.chats_list_widget)

        # Кнопки для создания чатов
        create_chat_buttons_layout = QVBoxLayout()
        self.create_private_chat_button = QPushButton("Создать личный чат")
        self.create_private_chat_button.clicked.connect(self.create_private_chat_dialog)
        create_chat_buttons_layout.addWidget(self.create_private_chat_button)

        self.create_group_chat_button = QPushButton("Создать групповой чат")
        self.create_group_chat_button.clicked.connect(self.create_group_chat_dialog)
        create_chat_buttons_layout.addWidget(self.create_group_chat_button)

        self.create_channel_button = QPushButton("Создать канал")
        self.create_channel_button.clicked.connect(self.create_channel_dialog)
        create_chat_buttons_layout.addWidget(self.create_channel_button)

        self.delete_chat_button = QPushButton("Удалить чат")
        self.delete_chat_button.clicked.connect(self.delete_chat)
        self.delete_chat_button.setEnabled(False) # Изначально отключена
        create_chat_buttons_layout.addWidget(self.delete_chat_button)

        # Новая кнопка для добавления участника (для групп)
        self.add_group_member_button = QPushButton("Добавить участника (Группа)")
        self.add_group_member_button.clicked.connect(self.add_member_to_chat_dialog)
        self.add_group_member_button.setEnabled(False) # Изначально отключена
        create_chat_buttons_layout.addWidget(self.add_group_member_button)

        # Новая кнопка для добавления подписчика (для каналов)
        self.add_channel_subscriber_button = QPushButton("Добавить подписчика (Канал)")
        self.add_channel_subscriber_button.clicked.connect(self.add_subscriber_to_channel_dialog)
        self.add_channel_subscriber_button.setEnabled(False) # Изначально отключена
        create_chat_buttons_layout.addWidget(self.add_channel_subscriber_button)


        left_panel.addLayout(create_chat_buttons_layout)
        main_layout.addLayout(left_panel, 1) # Пропорция 1 к 3

        # Правая панель - область сообщений и ввод
        right_panel = QVBoxLayout()
        self.chat_title_label = QLabel("Выберите чат")
        self.chat_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chat_title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        right_panel.addWidget(self.chat_title_label)

        self.messages_display = QTextEdit()
        self.messages_display.setReadOnly(True)
        right_panel.addWidget(self.messages_display)

        # Ввод сообщения и кнопки отправки
        message_input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Введите сообщение...")
        self.message_input.returnPressed.connect(self.send_text_message) # Отправка по Enter
        message_input_layout.addWidget(self.message_input)

        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send_text_message)
        message_input_layout.addWidget(self.send_button)

        self.attach_file_button = QPushButton("Прикрепить файл")
        self.attach_file_button.clicked.connect(self.send_file_message)
        message_input_layout.addWidget(self.attach_file_button)

        right_panel.addLayout(message_input_layout)
        main_layout.addLayout(right_panel, 3) # Пропорция 3 к 1

    def load_chats(self):
        self.chats_list_widget.clear()
        chats = self.api_client.get_user_chats()
        for chat in chats:
            item = QListWidgetItem(chat['name'] or f"Чат {chat['id']}") 
            item.setData(Qt.ItemDataRole.UserRole, chat['id'])
            item.setData(Qt.ItemDataRole.WhatsThisRole, chat['type']) 
            self.chats_list_widget.addItem(item)
        
        self.update_buttons_state()


    def chat_selected(self, item):
        self.current_chat_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_chat_type = item.data(Qt.ItemDataRole.WhatsThisRole)
        self.chat_title_label.setText(item.text())
        self.update_buttons_state()
        self.load_messages()

    def update_buttons_state(self):
        is_chat_selected = self.current_chat_id is not None
        self.delete_chat_button.setEnabled(is_chat_selected)
        
        self.add_group_member_button.setEnabled(is_chat_selected and self.current_chat_type == 'group')
        self.add_channel_subscriber_button.setEnabled(is_chat_selected and self.current_chat_type == 'channel')


    def load_messages(self):
        if not self.current_chat_id:
            self.messages_display.clear()
            return

        messages = self.api_client.get_chat_messages(self.current_chat_id)
        self.messages_display.clear()
        for message in messages:
            sender_display_name = message.get('sender_display_name', 'Неизвестный')
            sent_at = message.get('sent_at', 'Неизвестно время')
            
            if message['is_deleted']:
                self.messages_display.append(f"[{sent_at}] {sender_display_name}: [Сообщение удалено]")
            elif message['message_type'] == 'text':
                self.messages_display.append(f"[{sent_at}] {sender_display_name}: {message['content']}")
            elif message['message_type'] == 'file':
                file_url = self.api_client.get_file_url(message['file_url'])
                self.messages_display.append(f"[{sent_at}] {sender_display_name}: [Файл] <a href='{file_url}'>{message['file_name']}</a> ({message['file_size']} bytes)")
        
        self.messages_display.verticalScrollBar().setValue(self.messages_display.verticalScrollBar().maximum())

    def create_private_chat_dialog(self):
        username, ok = QInputDialog.getText(self, "Создать личный чат", "Введите имя пользователя для личного чата:")
        if ok and username:
            response = self.api_client.create_private_chat(username)
            if response.status_code == 201:
                QMessageBox.information(self, "Успех", f"Личный чат с {username} создан.")
                self.load_chats()
            elif response.status_code == 409:
                QMessageBox.information(self, "Информация", response.json().get('error', 'Личный чат с этим пользователем уже существует.'))
                self.load_chats()
            else:
                QMessageBox.critical(self, "Ошибка", response.json().get('error', 'Не удалось создать личный чат'))

    def create_group_chat_dialog(self):
        name, ok = QInputDialog.getText(self, "Создать групповой чат", "Введите название группового чата:")
        if ok and name:
            members_str, ok_members = QInputDialog.getText(self, "Добавить участников", "Введите имена пользователей участников через запятую (например: user1,user2):")
            if ok_members:
                member_usernames = [u.strip() for u in members_str.split(',') if u.strip()]
                response = self.api_client.create_group_chat(name, member_usernames)
                if response.status_code == 201:
                    QMessageBox.information(self, "Успех", f"Групповой чат '{name}' создан.")
                    self.load_chats()
                else:
                    QMessageBox.critical(self, "Ошибка", response.json().get('error', 'Не удалось создать групповой чат'))

    def create_channel_dialog(self):
        name, ok = QInputDialog.getText(self, "Создать канал", "Введите название канала:")
        if ok and name:
            response = self.api_client.create_channel(name)
            if response.status_code == 201:
                QMessageBox.information(self, "Успех", f"Канал '{name}' создан.")
                self.load_chats()
            else:
                QMessageBox.critical(self, "Ошибка", response.json().get('error', 'Не удалось создать канал'))

    def delete_chat(self):
        if not self.current_chat_id:
            QMessageBox.warning(self, "Ошибка", "Выберите чат для удаления.")
            return

        reply = QMessageBox.question(self, "Подтверждение удаления", 
                                     "Вы уверены, что хотите удалить этот чат? Это действие нельзя отменить.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            response = self.api_client.delete_chat(self.current_chat_id)
            if response.status_code == 200:
                QMessageBox.information(self, "Успех", "Чат успешно удален.")
                self.current_chat_id = None
                self.current_chat_type = None
                self.chat_title_label.setText("Выберите чат")
                self.messages_display.clear()
                self.update_buttons_state()
                self.load_chats()
            else:
                error = response.json().get('error', 'Ошибка при удалении чата.')
                QMessageBox.critical(self, "Ошибка", error)

    def add_member_to_chat_dialog(self):
        if not self.current_chat_id or self.current_chat_type != 'group':
            QMessageBox.warning(self, "Ошибка", "Выберите групповой чат, чтобы добавить участника.")
            return

        username, ok = QInputDialog.getText(self, "Добавить участника в группу", "Введите имя пользователя для добавления:")
        if ok and username:
            response = self.api_client.add_group_member(self.current_chat_id, username)
            if response.status_code == 201:
                QMessageBox.information(self, "Успех", f"Пользователь '{username}' успешно добавлен в группу.")
            else:
                QMessageBox.critical(self, "Ошибка", response.json().get('error', 'Не удалось добавить участника в группу'))

    def add_subscriber_to_channel_dialog(self):
        if not self.current_chat_id or self.current_chat_type != 'channel':
            QMessageBox.warning(self, "Ошибка", "Выберите канал, чтобы добавить подписчика.")
            return

        username, ok = QInputDialog.getText(self, "Добавить подписчика в канал", "Введите имя пользователя для добавления:")
        if ok and username:
            response = self.api_client.add_channel_subscriber(self.current_chat_id, username)
            if response.status_code == 201:
                QMessageBox.information(self, "Успех", f"Пользователь '{username}' успешно добавлен в канал.")
            else:
                QMessageBox.critical(self, "Ошибка", response.json().get('error', 'Не удалось добавить подписчика в канал'))


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
        
        if response.status_code == 201:
            self.load_messages()
        else:
            error = response.json().get('error', 'Ошибка отправки файла')
            QMessageBox.critical(self, "Ошибка", error)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    api_client = ApiClient()
    login_dialog = LoginDialog(api_client)
    
    if login_dialog.exec() == QDialog.DialogCode.Accepted:
        chat_window = ChatWindow(api_client)
        chat_window.show()
        sys.exit(app.exec())