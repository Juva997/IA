import json
import os
import sys
import threading
import time

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.orchestrator import Orchestrator

HISTORY_FILE = "chat_history.json"


class ChatBubble(QFrame):
    def __init__(self, text="", is_user=False):
        super().__init__()

        self.layout = QHBoxLayout(self)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.label.setStyleSheet(
            f"""
            padding: 10px;
            border-radius: 12px;
            max-width: 260px;
            color: white;
            background-color: {'#22c55e' if is_user else '#1e293b'};
            """
        )

        if is_user:
            self.layout.addStretch()
            self.layout.addWidget(self.label)
        else:
            self.layout.addWidget(self.label)
            self.layout.addStretch()

    def update_text(self, text):
        self.label.setText(text)


class JarvisHUD(QWidget):
    response_signal = pyqtSignal(str)
    stream_signal = pyqtSignal(str)
    user_message_signal = pyqtSignal(str)
    notification_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.orch = Orchestrator()
        self._drag_pos = QPoint()
        self.max_messages = 50
        self.current_ai_bubble = None
        self.chat_open = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(0.95)
        self.setGeometry(300, 200, 300, 120)
        self.setStyleSheet(
            """
            QWidget {
                background-color: rgba(15, 23, 42, 220);
                border-radius: 16px;
            }
            QPushButton {
                color: #22c55e;
                border: 1px solid #22c55e;
                border-radius: 10px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #22c55e;
                color: black;
            }
            QLineEdit {
                background-color: #020617;
                color: #22c55e;
                border-radius: 10px;
                padding: 6px;
            }
            """
        )

        self.layout = QVBoxLayout(self)
        self._build_toolbar()
        self._build_chat_area()
        self._connect_signals()
        self._load_history()

    def _build_toolbar(self):
        top = QHBoxLayout()

        self.btn_ai = QPushButton("AI")
        self.btn_ai.clicked.connect(self.toggle_chat)

        self.btn_voice = QPushButton("Voz")
        self.btn_voice.setToolTip("Ouvir comando de voz")
        self.btn_voice.clicked.connect(self._start_voice_input)

        self.btn_vision = QPushButton("Tela")
        self.btn_vision.setToolTip("Capturar tela")
        self.btn_vision.clicked.connect(self._capture_screen)

        top.addWidget(self.btn_ai)
        top.addWidget(self.btn_voice)
        top.addWidget(self.btn_vision)
        top.addStretch()
        self.layout.addLayout(top)

    def _build_chat_area(self):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.hide()

        self.chat_widget = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.addStretch()

        self.scroll.setWidget(self.chat_widget)
        self.layout.addWidget(self.scroll)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Digite...")
        self.input.returnPressed.connect(self._handle_input)
        self.input.hide()
        self.layout.addWidget(self.input)

    def _connect_signals(self):
        self.response_signal.connect(self._finish_ai_message)
        self.stream_signal.connect(self._stream_update)
        self.user_message_signal.connect(self.add_user_message)
        self.notification_signal.connect(self._add_ai_message)

    def _save_history(self):
        messages = []
        for i in range(self.chat_layout.count() - 1):
            item = self.chat_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, ChatBubble):
                messages.append(widget.label.text())

        with open(HISTORY_FILE, "w", encoding="utf-8") as file:
            json.dump(messages, file, ensure_ascii=False, indent=2)

    def _load_history(self):
        if not os.path.exists(HISTORY_FILE):
            return

        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as file:
                messages = json.load(file)
            for msg in messages:
                self._add_ai_message(msg)
        except Exception:
            pass

    def _handle_input(self):
        text = self.input.text().strip()
        if not text:
            return

        self.input.clear()
        self.add_user_message(text)
        threading.Thread(target=self._run_agent, args=(text,), daemon=True).start()

    def _start_voice_input(self):
        threading.Thread(target=self._voice_input_thread, daemon=True).start()

    def _voice_input_thread(self):
        try:
            from interfaces.voice import VoiceInterface

            voice = VoiceInterface()
            text = voice.listen()

            if not text:
                self.notification_signal.emit("Nao consegui ouvir. Tente novamente.")
                return

            self.user_message_signal.emit(text)
            self._run_agent(text)
        except Exception as e:
            self.notification_signal.emit(f"Erro de voz: {e}")

    def _capture_screen(self):
        threading.Thread(target=self._vision_capture_thread, daemon=True).start()

    def _vision_capture_thread(self):
        try:
            from integrations.vision import VisionSystem

            vision = VisionSystem()
            result = vision.capture_screen()

            if isinstance(result, dict) and result.get("status") == "success":
                info = result.get("output", {})
                self.notification_signal.emit(
                    f"Captura realizada. Resolucao: {info.get('size')}"
                )
            else:
                error = result.get("error") if isinstance(result, dict) else str(result)
                self.notification_signal.emit(f"Erro de visao: {error}")
        except Exception as e:
            self.notification_signal.emit(f"Erro de visao: {e}")

    def _run_agent(self, text):
        try:
            response = self.orch.handle_user_query(text)
            if isinstance(response, dict):
                response = response.get("output", "Erro")
            else:
                response = str(response)
        except Exception as e:
            response = f"Erro: {str(e)}"

        current = ""
        for char in response:
            current += char
            self.stream_signal.emit(current)
            time.sleep(0.01)

        self.response_signal.emit(response)

    def add_user_message(self, text):
        bubble = ChatBubble(text, is_user=True)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self._trim_messages()
        self._scroll_to_bottom()
        self._save_history()

    def _add_ai_message(self, text):
        bubble = ChatBubble(text, is_user=False)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self._trim_messages()
        self._scroll_to_bottom()
        self._save_history()

    def _stream_update(self, text):
        if not self.current_ai_bubble:
            self.current_ai_bubble = ChatBubble("", is_user=False)
            self.chat_layout.insertWidget(
                self.chat_layout.count() - 1, self.current_ai_bubble
            )

        self.current_ai_bubble.update_text(text)
        self._scroll_to_bottom()

    def _finish_ai_message(self, text):
        self.current_ai_bubble = None
        self._trim_messages()
        self._save_history()

    def _trim_messages(self):
        while self.chat_layout.count() > self.max_messages:
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _scroll_to_bottom(self):
        QApplication.processEvents()
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def toggle_chat(self):
        self.chat_open = not self.chat_open

        if self.chat_open:
            self.setFixedSize(420, 500)
            self.scroll.show()
            self.input.show()
        else:
            self.setFixedSize(300, 120)
            self.scroll.hide()
            self.input.hide()

        self.update()
        self.repaint()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)


def start_ui():
    app = QApplication(sys.argv)
    hud = JarvisHUD()
    hud.show()
    sys.exit(app.exec())
