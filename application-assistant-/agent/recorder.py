import time
import json
import threading

try:
    from pynput import mouse, keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

class ActionRecorder:
    def __init__(self, output_file="recorded_actions.json"):
        self.output_file = output_file
        self.actions = []
        self.start_time = None
        self.is_recording = False
        self.mouse_listener = None
        self.keyboard_listener = None

    def _get_elapsed_time(self):
        return round(time.time() - self.start_time, 2)

    def on_click(self, x, y, button, pressed):
        if not HAS_PYNPUT: return
        if pressed and self.is_recording:
            self.actions.append({
                "action": "click",
                "parameters": {"x": x, "y": y, "button": str(button)},
                "time": self._get_elapsed_time()
            })

    def on_press(self, key):
        if not HAS_PYNPUT: return
        if self.is_recording:
            try:
                char = key.char
            except AttributeError:
                char = str(key)
            
            self.actions.append({
                "action": "type",
                "parameters": {"text": char},
                "time": self._get_elapsed_time()
            })

    def start_recording(self):
        """Starts recording mouse clicks and keyboard input."""
        if not HAS_PYNPUT:
            print("Recording not supported on Vercel.")
            return

        if self.is_recording:
            return
            
        self.actions = []
        self.start_time = time.time()
        self.is_recording = True
        
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press)
        
        self.mouse_listener.start()
        self.keyboard_listener.start()
        print("Recording started...")

    def stop_recording(self):
        """Stops recording and saves data to a JSON file."""
        if not self.is_recording:
            return
            
        self.is_recording = False
        
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            
        # Optional: save to local file for debugging
        try:
            with open(self.output_file, 'w') as f:
                json.dump(self.actions, f, indent=4)
        except:
            pass
            
        # Filter out actions in the last 1 second
        if self.actions:
            end_time = self.actions[-1]["time"]
            self.actions = [a for a in self.actions if end_time - a["time"] > 1.0]
            
        print(f"Recording stopped. {len(self.actions)} actions recorded (last 1s removed).")
        return self.actions

    def get_actions(self):
        return self.actions
