import threading
import uvicorn
import sys
import os
import startup


# --- Step 1: Add project subfolders to the Python path ---
# This allows us to use `from frontend` and `from backend`
# no matter how the script is run (as .py or as .exe)
try:
    # If running as a PyInstaller bundle
    base_path = sys._MEIPASS
except Exception:
    # If running as a normal .py script
    base_path = os.path.abspath(".")

# Add both frontend and backend directories to the path
sys.path.append(os.path.join(base_path, 'frontend'))
sys.path.append(os.path.join(base_path, 'backend'))


# --- Step 2: Import the App Objects ---
try:

    from backend.main import logger

    logger.info("Trying to import from backend")
    # Import the FastAPI 'app' object from your backend
    # !! IMPORTANT: I am assuming your file is 'backend/main.py' 
    # !! and your FastAPI object is named 'app'. 
    # !! If not, change 'main' or 'app' to match your code.
    from backend.main import app as backend_app
    
    # Import your CustomTkinter 'App' class from the frontend
    from frontend.gui import App as FrontendApp

except ImportError as e:
    logger.error(f"Error: Failed to import modules. {e}")
    logger.error("Please ensure:")
    logger.error("1. This script is in your root project folder.")
    logger.error("2. You have a 'frontend/main_gui.py' file with your 'App' class.")
    logger.error("3. You have a 'backend/main.py' file (or similar) with your FastAPI 'app'.")
    logger.error("Press Enter to exit...")
    sys.exit(1)


# --- Step 3: Define the Backend Server Thread ---
def start_backend():
    """
    Runs the Uvicorn server in a separate thread.
    `daemon=True` means this thread will exit when the main
    GUI application (main thread) exits.
    """
    logger.info("Starting backend server on thread...")
    try:
        uvicorn.run(
            backend_app,
            host="127.0.0.1",
            port=8000,
            reload=False,
            log_config=None
        )
    except Exception as e:
        logger.error(f"Backend server failed: {e}")
        # We can't easily show this in the GUI, so we print it
        # The GUI's health check will fail, which is what we want.


# --- Step 4: Main Execution ---
if __name__ == "__main__":
    
    # 4a. Start the backend server in a background thread
    # We use daemon=True so it automatically shuts down
    # when the main GUI app is closed.

    logger.info("inside run_app main function")

    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()

    # 4b. Start the frontend GUI on the main thread
    # This is a blocking call. The script will stay here
    # until the user closes the CustomTkinter window.
    logger.info("Starting frontend GUI on main thread...")
    gui = FrontendApp()
    gui.mainloop()

    # 4c. (Implicit)
    # When the GUI window is closed, mainloop() exits.
    # The script ends. The daemon backend thread is killed.
    logger.info("Frontend closed. Exiting application.")
