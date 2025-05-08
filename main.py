import sys
import json
import subprocess
import asyncio
import desktop_notify
from desktop_notify import aio
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
)
from PyQt5.QtCore import QTimer, Qt, QEventLoop, pyqtSignal, QObject
from PyQt5.QtMultimedia import QSound
import threading
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='Dynamic Pomodoro Timer')
    parser.add_argument('--config', '-c', 
                      default='pomodoro_config.json',
                      help='Path to the configuration file (default: testing_config.json)')
    return parser.parse_args()

def load_config(config_path):
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file '{config_path}' not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Config file '{config_path}' is not valid JSON")
        sys.exit(1)

class NotificationHandler(QObject):
    action_triggered = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.action_triggered.connect(self.handle_action)
        self.last_action = None  # Track if an action was explicitly triggered

    def handle_action(self, action_id):
        self.last_action = action_id  # Set the last action
        print(f"NotificationHandler: Received action {action_id}")
        if action_id == "focus_yes":
            print("Handling focus_yes action")
            self.parent().work_phase += 1
            if self.parent().work_phase >= len(self.parent().work_phases):
                # If we've completed all phases, start the break
                print("All phases completed, starting break")
                self.parent().handle_session_break()
            else:
                if self.parent().work_phase < len(self.parent().phase_buttons):
                    self.parent().phase_buttons[self.parent().work_phase].show()
                self.parent().highlight_selection()
                self.parent().start_phase(self.parent().work_phase)
        elif action_id == "focus_no":
            print("Handling focus_no action")
            self.parent().handle_session_break()
        elif action_id == "snooze_yes":
            print("Handling snooze_yes action")
            self.parent().snooze_count += 1
            print(f"Snooze count increased to {self.parent().snooze_count}")
            self.parent().start_snooze()
        elif action_id == "snooze_no":
            print("Handling snooze_no action")
            self.parent().handle_session_break()
        self.parent().popup_active = False
        # Reset last_action after handling
        self.last_action = None

class PomodoroTimer(QWidget):
    def __init__(self, config_path):
        super().__init__()
        self.config = load_config(config_path)
        self.init_state()
        self.init_ui()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)
        self.popup_active = False
        self.break_active = False
        self.session_break_active = False
        self.paused = False
        self.notification_sound = QSound("pling.wav")
        self.break_sound = QSound("gong.wav")
        self.current_notification_process = None
        # Initialize notification server with proper mainloop
        self.notify_server = aio.Server("Dynamic Pomodoro Timer")
        # Create event loop for async operations
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        # Start the event loop in a separate thread
        self.loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.loop_thread.start()
        # Create notification handler
        self.notification_handler = NotificationHandler()
        self.notification_handler.setParent(self)

    def _run_event_loop(self):
        """Run the event loop in a separate thread"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def init_state(self):
        self.work_phases = self.config['work_phases']
        self.breaks = self.config['breaks']
        self.snooze_interval = self.config['snooze_interval']
        self.max_snoozes = self.config['max_snoozes']
        self.daily_sessions = self.config['daily_sessions']
        self.popup_autoconfirm_seconds = self.config.get('popup_autoconfirm_seconds', 30)
        self.popup_warning_seconds = self.config.get('popup_warning_seconds', 5)
        self.session = 0
        self.work_phase = 0
        self.snooze_count = 0
        self.total_phases = len(self.work_phases)
        self.phase_elapsed = 0
        self.session_elapsed = 0
        self.total_work_elapsed = 0
        self.snooze_elapsed = 0
        # Initialize current_phase_duration
        self.current_phase_duration = int(self.work_phases[0] * 60)

    def init_ui(self):
        self.setWindowTitle("Dynamic Pomodoro Timer")
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Calculate minimum width based on max buttons
        button_width = 50  # width of each number button
        arrow_width = 30   # width of arrow button
        spacing = 10       # approximate spacing between buttons
        min_width = (max(self.daily_sessions, self.total_phases) * (button_width + spacing) + arrow_width + 80)  # 40 for padding
        self.setMinimumWidth(min_width)

        # Main control button
        self.main_button = QPushButton("Start Working")
        self.main_button.setStyleSheet("background-color: red; color: white; font-size: 18px;")
        self.main_button.clicked.connect(self.toggle_timer)
        self.layout.addWidget(self.main_button)

        # Pause and Stop buttons
        button_row = QHBoxLayout()
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        button_row.addWidget(self.pause_button)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_session)
        button_row.addWidget(self.stop_button)
        self.layout.addLayout(button_row)

        # Timer labels
        self.slot_timer_label = QLabel("Phase: 00:00")
        self.slot_timer_label.setAlignment(Qt.AlignCenter)
        self.slot_timer_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.layout.addWidget(self.slot_timer_label)
        self.total_timer_label = QLabel("Total: 00:00")
        self.total_timer_label.setAlignment(Qt.AlignCenter)
        self.total_timer_label.setStyleSheet("font-size: 20px;")
        self.layout.addWidget(self.total_timer_label)

        # Session selection buttons
        session_label = QLabel("Session:")
        session_label.setAlignment(Qt.AlignCenter)
        session_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.layout.addWidget(session_label)
        
        self.session_buttons = []
        session_row = QHBoxLayout()
        for i in range(self.daily_sessions):
            btn = QPushButton(f"{i+1}")
            btn.setFixedSize(50, 50)
            btn.setStyleSheet("font-size: 16px; font-weight: bold;")
            btn.clicked.connect(lambda _, idx=i: self.select_session(idx))
            self.session_buttons.append(btn)
            session_row.addWidget(btn)
            if i > 0:  # Hide all but first session button initially
                btn.hide()
        
        self.session_show_more = QPushButton("▶")
        self.session_show_more.setFixedSize(30, 50)
        self.session_show_more.clicked.connect(self.toggle_sessions)
        session_row.addWidget(self.session_show_more)
        self.layout.addLayout(session_row)

        # Phase selection buttons
        phase_label = QLabel("Phase:")
        phase_label.setAlignment(Qt.AlignCenter)
        phase_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.layout.addWidget(phase_label)
        
        self.phase_buttons = []
        phase_row = QHBoxLayout()
        for i in range(self.total_phases):
            btn = QPushButton(f"{i+1}")
            btn.setFixedSize(50, 50)
            btn.setStyleSheet("font-size: 16px; font-weight: bold;")
            btn.clicked.connect(lambda _, idx=i: self.select_phase(idx))
            self.phase_buttons.append(btn)
            phase_row.addWidget(btn)
            if i > 0:  # Hide all but first phase button initially
                btn.hide()
        
        self.phase_show_more = QPushButton("▶")
        self.phase_show_more.setFixedSize(30, 50)
        self.phase_show_more.clicked.connect(self.toggle_phases)
        phase_row.addWidget(self.phase_show_more)
        self.layout.addLayout(phase_row)

        self.highlight_selection()
        self.show()

    def toggle_sessions(self):
        # If expanded, collapse to show only current and previous
        if all(btn.isVisible() for btn in self.session_buttons):
            for i, btn in enumerate(self.session_buttons):
                btn.show() if i <= self.session else btn.hide()
            self.session_show_more.setText("▶")
        else:
            # Show all buttons
            for btn in self.session_buttons:
                btn.show()
            self.session_show_more.setText("▼")

    def toggle_phases(self):
        # If expanded, collapse to show only current and previous
        if all(btn.isVisible() for btn in self.phase_buttons):
            for i, btn in enumerate(self.phase_buttons):
                btn.show() if i <= self.work_phase else btn.hide()
            self.phase_show_more.setText("▶")
        else:
            # Show all buttons
            for btn in self.phase_buttons:
                btn.show()
            self.phase_show_more.setText("▼")

    def highlight_selection(self):
        for idx, btn in enumerate(self.session_buttons):
            btn.setStyleSheet("background-color: green;" if idx == self.session else "")
        for idx, btn in enumerate(self.phase_buttons):
            btn.setStyleSheet("background-color: green;" if idx == self.work_phase else "")

    def select_session(self, idx):
        self.session = idx
        self.work_phase = 0
        self.snooze_count = 0
        self.session_elapsed = 0
        self.total_work_elapsed = 0
        self.phase_elapsed = 0
        self.snooze_elapsed = 0
        self.break_active = False
        self.session_break_active = False
        self.timer.stop()
        self.paused = False
        self.pause_button.setText("Pause")
        # Initialize current_phase_duration for the first phase
        self.current_phase_duration = int(self.work_phases[0] * 60)
        # Show all session buttons up to current session
        for i, btn in enumerate(self.session_buttons):
            btn.show() if i <= idx else btn.hide()
        # Reset phase buttons visibility
        for i, btn in enumerate(self.phase_buttons):
            btn.hide() if i > 0 else btn.show()
        self.session_show_more.setText("▶")
        self.phase_show_more.setText("▶")
        self.highlight_selection()
        self.update_main_button("Start Working", "red")
        self.update_timers()

    def select_phase(self, idx):
        self.work_phase = idx
        self.snooze_count = 0
        self.snooze_elapsed = 0
        self.phase_elapsed = 0
        self.break_active = False
        self.session_break_active = False
        self.timer.stop()
        self.paused = False
        self.pause_button.setText("Pause")
        # Initialize current_phase_duration for the selected phase
        self.current_phase_duration = int(self.work_phases[idx] * 60)
        # Show all phase buttons up to current phase
        for i, btn in enumerate(self.phase_buttons):
            btn.show() if i <= idx else btn.hide()
        self.phase_show_more.setText("▶")
        self.highlight_selection()
        self.update_main_button("Start Working", "red")
        self.update_timers()

    def update_main_button(self, text, color):
        self.main_button.setText(text)
        if "Extended work" in text:
            self.main_button.setStyleSheet(f"background-color: {color}; color: white; font-size: 18px;")
        else:
            self.main_button.setStyleSheet(f"background-color: {color}; color: white; font-size: 18px;")

    def toggle_timer(self):
        if not self.timer.isActive() and not self.paused:
            if self.break_active or self.session_break_active:
                return  # Don't allow starting work during breaks
            self.start_phase(self.work_phase)
        elif self.paused:
            self.toggle_pause()
        else:
            self.toggle_pause()

    def toggle_pause(self):
        if not self.paused:
            # Pause everything
            self.paused = True
            self.timer.stop()
            self.pause_button.setText("Resume")
            self.update_main_button("Paused", "orange")
        else:
            # Resume everything
            self.paused = False
            self.timer.start(1000)
            # Restore main button state
            if self.break_active or self.session_break_active:
                self.update_main_button("Break time", "green")
            elif self.snooze_count > 0 and not self.break_active:
                self.update_main_button(f"Extended work {self.snooze_count}/{self.max_snoozes}", "orange")
            else:
                self.update_main_button("Working...", "purple")
            self.pause_button.setText("Pause")

    def stop_session(self):
        # End current session immediately, skip break, increment session
        self.timer.stop()
        self.paused = False
        self.pause_button.setText("Pause")
        self.break_active = False
        self.session_break_active = False
        self.snooze_count = 0
        self.phase_elapsed = 0
        self.snooze_elapsed = 0
        self.session_elapsed = 0
        self.work_phase = 0
        self.session += 1
        if self.session >= self.daily_sessions:
            self.update_main_button("All sessions complete!", "gray")
            self.slot_timer_label.setText("Done!")
            self.total_timer_label.setText(f"Total: {self.format_time(self.total_work_elapsed)}")
            self.show_notification("Pomodoro Finished", "All sessions complete!")
            return
        self.highlight_selection()
        self.update_main_button("Start Working", "red")
        self.update_timers()

    def start_phase(self, phase_idx):
        if phase_idx >= len(self.work_phases):
            print("Phase index out of range, starting break")
            self.handle_session_break()
            return

        self.break_active = False
        self.session_break_active = False
        self.popup_active = False
        self.current_phase_duration = int(self.work_phases[phase_idx] * 60)
        self.phase_elapsed = 0
        self.update_main_button("Working...", "purple")
        self.timer.start(1000)
        # Show auto-fading notification for phase start with longer duration
        self.show_notification_sync(
            "Work Started",
            f"Only {self.work_phases[phase_idx]} minutes to go",
            timeout=8000  # 8 seconds
        )

    def update_timer(self):
        if self.paused:
            return
        # Timers always count up during popups and work
        if self.break_active or self.session_break_active:
            self.phase_elapsed += 1
            remaining = max(self.current_phase_duration - self.phase_elapsed, 0)
            self.slot_timer_label.setText(
                f"Break: {self.format_time(remaining)}"
                f" / {self.format_time(self.current_phase_duration)}"
            )
            self.total_timer_label.setText(f"Total: {self.format_time(self.total_work_elapsed)}")
            if self.phase_elapsed >= self.current_phase_duration:
                self.timer.stop()
                if self.session_break_active:
                    self.start_next_session()
                    self.show_notification("Break's over", "New session starting!")
        else:
            self.phase_elapsed += 1
            self.session_elapsed += 1
            self.total_work_elapsed += 1
            remaining = max(self.current_phase_duration - self.phase_elapsed, 0)
            self.slot_timer_label.setText(
                f"Only {self.format_time(remaining)} to go"
                f" of {self.format_time(self.current_phase_duration)}!"
            )
            self.total_timer_label.setText(f"Already worked for {self.format_time(self.total_work_elapsed)}! \nKeep it up!")
            if self.phase_elapsed >= self.current_phase_duration:
                self.timer.stop()
                if self.work_phase + 1 < self.total_phases:
                    self.show_work_confirmation()
                else:
                    self.handle_last_phase_end()

    def play_notification_sound(self):
        self.notification_sound.play()

    async def show_notification(self, title, message, actions=None, timeout=None):
        try:
            print(f"Creating notification: {title} - {message}")
            notify = self.notify_server.Notify(title, message)
            # Use provided timeout or default based on whether there are actions
            notify.set_timeout(timeout if timeout is not None else (10000 if actions else 5000))
            
            if actions:
                print(f"Adding actions: {actions}")
                # Store the notification type for the close handler
                notify_type = "focus_check" if "Focus Check" in title else "snooze"
                
                def create_action_callback(action_id):
                    def callback(notification):
                        print(f"Action callback triggered for {action_id}")
                        # Use Qt's signal mechanism to handle the action in the main thread
                        self.notification_handler.action_triggered.emit(action_id)
                        # Set last_action to prevent on_close from triggering
                        self.notification_handler.last_action = action_id
                    return callback
                
                for action_id, action_label in actions:
                    action = desktop_notify.Action(action_label, create_action_callback(action_id))
                    notify.add_action(action)
                
                # Set up close handler for auto-confirm/auto-deny
                def on_close(notification, reason):
                    print(f"Notification closed with reason: {reason}")
                    # Only auto-handle if no explicit action was taken
                    if not self.notification_handler.last_action:
                        if notify_type == "focus_check":
                            print("Auto-confirming focus check as 'yes'")
                            self.notification_handler.action_triggered.emit("focus_yes")
                        elif notify_type == "snooze":
                            print("Auto-denying snooze as 'no'")
                            self.notification_handler.action_triggered.emit("snooze_no")
                
                notify.set_on_close(on_close)
            
            print("Showing notification...")
            await notify.show()
            print("Notification shown")
            
        except Exception as e:
            print(f"Notification error: {e}")
            import traceback
            traceback.print_exc()

    def handle_notification_action(self, action_id):
        # This method is now handled by NotificationHandler
        pass

    def show_work_confirmation(self):
        self.popup_active = True
        self.play_notification_sound()
        # Show interactive notification
        self.show_notification_sync(
            "Focus Check",
            "Did you focus the past minutes?",
            [("focus_yes", "Yes"), ("focus_no", "No")]
        )

    def show_snooze_dialog(self):
        self.popup_active = True
        self.play_notification_sound()
        # Show interactive notification with longer timeout
        self.show_notification_sync(
            "Snooze?",
            f"Continue working for {self.snooze_interval} more minutes?",
            [("snooze_yes", "Yes"), ("snooze_no", "No")],
            timeout=15000  # 15 seconds
        )

    def handle_session_break(self):
        print("Starting break")
        self.break_active = True
        self.session_break_active = True
        self.phase_elapsed = 0
        break_idx = self.session % len(self.breaks)
        self.current_phase_duration = int(self.breaks[break_idx] * 60)
        self.update_main_button("Break time", "green")
        self.slot_timer_label.setText(f"Break: 00:00 / {self.format_time(self.current_phase_duration)}")
        self.break_sound.play()
        self.show_notification_sync("Session complete", "Break started!")
        self.timer.start(1000)
        # Show the next session button if it exists
        if self.session + 1 < len(self.session_buttons):
            self.session_buttons[self.session + 1].show()

    def start_next_session(self):
        print("Starting next session")
        self.break_active = False
        self.session_break_active = False
        self.session += 1
        if self.session >= self.daily_sessions:
            self.update_main_button("All sessions complete!", "gray")
            self.slot_timer_label.setText("Done!")
            self.total_timer_label.setText(f"Total: {self.format_time(self.total_work_elapsed)}")
            self.show_notification_sync("Pomodoro Finished", "All sessions complete!")
            return
        self.work_phase = 0
        self.snooze_count = 0
        self.session_elapsed = 0
        self.phase_elapsed = 0
        self.snooze_elapsed = 0
        # Show the new session button
        if self.session < len(self.session_buttons):
            self.session_buttons[self.session].show()
        # Reset phase buttons visibility
        for i, btn in enumerate(self.phase_buttons):
            btn.hide() if i > 0 else btn.show()
        self.session_show_more.setText("▶")
        self.phase_show_more.setText("▶")
        self.highlight_selection()
        self.update_main_button("Working...", "purple")
        self.update_timers()
        self.notification_sound.play()  # Play pling sound for new session
        self.show_notification_sync("Break's Over", "Break's over, back to work. Session starting now!")
        self.start_phase(self.work_phase)  # Autostart next session!

    def update_timers(self):
        remaining = max(self.current_phase_duration - self.phase_elapsed, 0)
        if self.break_active or self.session_break_active:
            self.slot_timer_label.setText(
                f"Break: {self.format_time(remaining)}"
                f" / {self.format_time(self.current_phase_duration)}"
            )
        else:
            self.slot_timer_label.setText(
                f"Phase: {self.format_time(remaining)}"
                f" / {self.format_time(self.current_phase_duration)}"
            )
        self.total_timer_label.setText(f"Total: {self.format_time(self.total_work_elapsed)}")

    def show_auto_close_popup(self, title, message, duration_ms=3000):
        self.play_notification_sound()
        self.popup = QMessageBox(self)
        self.popup.setWindowTitle(title)
        self.popup.setText(message)
        self.popup.setStandardButtons(QMessageBox.Ok)
        self.popup.setWindowModality(Qt.NonModal)
        self.popup.show()
        QTimer.singleShot(duration_ms, self.popup.close)
        self.popup.finished.connect(lambda: setattr(self, 'popup', None))

    def format_time(self, seconds):
        m, s = divmod(seconds, 60)
        return f"{int(m):02}:{int(s):02}"

    def show_notification_sync(self, title, message, actions=None, timeout=None):
        """Synchronous wrapper for show_notification"""
        async def run_notification():
            await self.show_notification(title, message, actions, timeout)
        
        # Use call_soon_threadsafe to safely run the notification in the event loop
        self.loop.call_soon_threadsafe(lambda: asyncio.create_task(run_notification()))

    def handle_last_phase_end(self):
        """Handle the end of the last phase in a session"""
        if self.snooze_count < self.max_snoozes:
            self.show_snooze_dialog()
        else:
            self.handle_session_break()

    def start_snooze(self):
        """Start an extended work period"""
        print("Starting snooze period")
        self.break_active = False
        self.session_break_active = False
        self.popup_active = False
        self.current_phase_duration = int(self.snooze_interval * 60)
        self.phase_elapsed = 0
        self.snooze_elapsed = 0
        self.update_main_button(f"Extended work {self.snooze_count}/{self.max_snoozes}", "orange")
        self.timer.start(1000)
        # Show auto-fading notification for snooze start
        self.show_notification_sync(
            "Extended Work",
            f"Starting {self.snooze_interval} minutes of extended work",
            timeout=3000  # 3 seconds
        )

if __name__ == "__main__":
    args = parse_args()
    app = QApplication(sys.argv)
    window = PomodoroTimer(args.config)
    sys.exit(app.exec_())
