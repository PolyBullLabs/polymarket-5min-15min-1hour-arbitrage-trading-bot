"""
Non-blocking keyboard listener for dashboard controls (cross-platform)
"""
import sys
import os
import threading
import time

IS_WINDOWS = os.name == 'nt'

if IS_WINDOWS:
    import msvcrt
else:
    import select
    import termios
    import tty


class KeyboardListener:
    """Non-blocking keyboard listener (Windows & Unix)"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.key_callbacks = {}
        self.last_key = None
        self.last_key_time = 0
        
    def register_callback(self, key: str, callback, description: str = ""):
        """Register a callback for a specific key
        
        Args:
            key: Single character key (e.g., 'm', 'M', 'q')
            callback: Function to call when key is pressed
            description: Optional description for help display
        """
        key = key.lower()
        self.key_callbacks[key] = {
            'callback': callback,
            'description': description
        }
    
    def _get_key_windows(self):
        """Get a single keypress (non-blocking on Windows)"""
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            return ch.lower()
        return None

    def _get_key_unix(self):
        """Get a single keypress (non-blocking on Unix)"""
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1).lower()
        return None
    
    def _listener_loop(self):
        """Main listener loop (runs in thread)"""
        if IS_WINDOWS:
            self._listener_loop_windows()
        else:
            self._listener_loop_unix()

    def _listener_loop_windows(self):
        while self.running:
            key = self._get_key_windows()
            self._handle_key(key)
            time.sleep(0.05)

    def _listener_loop_unix(self):
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            while self.running:
                key = self._get_key_unix()
                self._handle_key(key)
                time.sleep(0.05)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    def _handle_key(self, key):
        if key and key in self.key_callbacks:
            now = time.time()
            if now - self.last_key_time > 0.5 or key != self.last_key:
                self.last_key = key
                self.last_key_time = now
                try:
                    self.key_callbacks[key]['callback']()
                except Exception as e:
                    print(f"\n[KEYBOARD] Error executing callback for '{key}': {e}")
    
    def start(self):
        """Start the keyboard listener in a background thread"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._listener_loop, daemon=True)
        self.thread.start()
        print("[KEYBOARD] Listener started")
    
    def stop(self):
        """Stop the keyboard listener"""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        print("[KEYBOARD] Listener stopped")
    
    def get_help_text(self):
        """Get help text for all registered keys"""
        if not self.key_callbacks:
            return "No keyboard shortcuts registered"
        
        lines = ["Keyboard shortcuts:"]
        for key, info in sorted(self.key_callbacks.items()):
            desc = info['description'] or 'No description'
            lines.append(f"  [{key.upper()}] {desc}")
        
        return "\n".join(lines)
