# Dynamic Pomodoro Timer

## Description

**Dynamic Pomodoro Timer** is a customizable productivity tool designed to help you maintain focus and manage your work sessions efficiently.
It follows the Pomodoro Technique, dividing your work into configurable phases and breaks, and supports multiple sessions per day.
The app is optimized for Linux desktops (XFCE-friendly) and provides both system notifications and interactive dialogs to check your concentration.

## License

This project is licensed under the European Union Public Licence v. 1.2 (EUPL-1.2). This license is comparable to the GNU Affero General Public License (AGPL) in terms of network distribution requirements. See the [LICENSE.md](LICENSE.md) file for details.

## Features

- **Configurable Work Phases and Breaks:** Set custom durations for each work phase and break in a JSON file.
- **Multiple Sessions:** Supports several sessions per day; easily switch between them.
- **Session and Phase Selection:** Clear UI for selecting both the current session and the work phase. The number of phases per session is determined by your config.
- **Timers:** Displays both slot (current phase) and total timers.
- **Pause, Resume, and Stop:** Easily pause/resume your session or stop and move to the next session.
- **User Prompts:** At the end of each phase, receive a notification and a popup asking if you stayed focused.
- **Configurable Auto-Confirm:** If you don't respond to the popup within a configurable time (default 30s, warning at 5s), it auto-confirms your focus (useful if you're working away from the computer).
- **Obnoxious Reminder:** If you don't respond, the popup becomes more attention-grabbing before auto-confirming.
- **XFCE Notification Support:** Uses native notifications (`notify-send`) for seamless Linux desktop integration.


## Quickstart

```bash
python3 -m venv venv        # Create a new virtual environment named 'venv'
source venv/bin/activate    # Activate the virtual environment
pip install -r requirements.txt
python main.py [--config CONFIG_FILE]  # Start the timer application with optional config file
```


## Configuration

Edit `pomodoro_config.json` (or specify a different config file using the `--config` parameter) to adjust work phases, breaks, snooze intervals, the number of daily sessions, and popup timing.
Example:

```json
{
    "work_phases": [10, 15, 20, 15],
    "breaks": [5, 20, 5, 60],
    "snooze_interval": 5,
    "max_work": 60,
    "daily_sessions": 4,
    "popup_autoconfirm_seconds": 30,
    "popup_warning_seconds": 5
}
```

You can also use a **testing config** with very short intervals for rapid testing:

```json
{
    "work_phases": [0.083, 0.083, 0.083, 0.083],
    "breaks": [0.083, 0.083, 0.083, 0.083],
    "snooze_interval": 0.083,
    "max_work": 0.3,
    "daily_sessions": 2,
    "popup_autoconfirm_seconds": 5,
    "popup_warning_seconds": 2
}
```


---

## Specifics & Clarifications

### Config Loading

- The application loads configuration from the file specified by the `--config` command-line parameter (default: `pomodoro_config.json`).
- The configuration file must be a valid JSON file containing all required fields.
- No fallback to other config files is performed.


### Session and Phase Selection UI

- Instead of dropdowns, session and phase selections are presented as two rows of buttons:
    - The first row contains buttons for each daily session.
    - The second row contains buttons for each work phase.
- The currently selected session and phase buttons are highlighted in green. Selections update automatically as the timer progresses through phases and sessions.


### State-Driven Main Button

- The main control button dynamically changes its label and color according to the timer state:
    - **Idle (before start):** Displays "Start Working" with a red background.
    - **Working:** Displays "Working..." with a purple background.
    - **Extended Work (Snooze):** Displays "Extended work N/X" with a yellow background, where N is the current snooze count and X is the maximum allowed snoozes based on config.
    - **Break Time:** Displays "Break time" with a green background.


### Pause and Stop Buttons

- **Pause:** Pauses the timer in any state (work, break, popup, etc.). Resume continues from where you left off.
- **Stop:** Instantly ends the current session, skips the break, increments the session counter, and prepares to start the next session.


### Work Confirmation and Snooze Logic

- After every work phase **except the last phase of the last session**, the user is prompted with a "Did you focus during this phase?" popup with auto-confirm timeout.
- After the **last phase of the last session** (or during extended work in the last session), the work confirmation popup is skipped, and only the snooze dialog is shown.
- The snooze dialog offers to continue working for a configurable snooze interval (e.g., 5 minutes), allowing multiple snoozes up to a configurable maximum total work time (`max_work`).
- The snooze count and max snoozes are displayed on the main button during extended work.


### Breaks and Session Flow

- **Only one break per session**: There are no breaks after individual phases. A break is only started after a session is completed (either after the last phase or after the user declines to snooze).
- **Session completion**: A session is considered complete if either the maximum total work time (`max_work`) is reached or the user does not snooze after the last regular work phase.
- **Automatic transitions**: Breaks and sessions start automatically, without any need for user confirmation.
- **After a break ends, the next session starts automatically.**
- **A notification appears after each break**: A system notification informs you that the break is over and the next session is starting.


### Timers

- The session and total work timers count up continuously during all active work phases, snooze periods, and even while confirmation or snooze dialogs are displayed.
- Timers pause only when the user pauses the timer, stops the session, or when a session ends.


### User Experience

- All notifications with auto-confirm behavior close automatically after the configured timeout (`popup_autoconfirm_seconds` in config).
- The UI remains responsive and clearly indicates the current state and timing information.
- System notifications are used for important state changes and user prompts.

---

## What's Different From a "Standard" Pomodoro App?

- **No breaks after phases:** Only a single break after each session, never after individual phases.
- **Session transitions are fully automatic:** No user confirmation is needed to start a break or a new session.
- **Timers keep running during popups:** Timers do not pause for confirmation dialogs or popups.
- **Pause and Stop buttons:** You can pause/resume at any moment or stop a session entirely, skipping the break and moving to the next session.
- **Auto-closing session transition popup:** After each break, a popup appears for a few seconds to inform you that work is resuming, but you never have to click to continue.

---

## Requirements

- Python 3.8 or higher
- PyQt5 5.15.0 or higher
- desktop-notify 1.3.3 or higher
- Linux desktop environment with notification support (DBus)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. By contributing to this project, you agree to license your contributions under the EUPL-1.2 license.

