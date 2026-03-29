from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is running!", 200

def run_webserver():
    app.run(host='0.0.0.0', port=10000)

def start_webserver():
    thread = threading.Thread(target=run_webserver, daemon=True)
    thread.start()
