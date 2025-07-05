from flask import Flask
import threading
from test2 import run_scraper  # Your logic in scraper.py

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Scraper is running!"

# Start scraper in background thread
def background_task():
    run_scraper()

threading.Thread(target=background_task).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
