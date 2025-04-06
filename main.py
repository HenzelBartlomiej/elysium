import os
import logging
import threading
from bot import run_bot
# from web_dashboard import app

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# def run_flask():
#     app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)

# def run_bot_process():
#     run_bot()

if __name__ == "__main__":
    # Start the Flask application in a separate thread
    # flask_thread = threading.Thread(target=run_flask)
    # flask_thread.daemon = True
    # flask_thread.start()
    
    # Run the Discord bot in the main thread
    # logger.info("Starting Discord bot...")
    run_bot()
    # run_bot_process()

