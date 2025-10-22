import customtkinter as ctk
from tkinter import filedialog, messagebox
import requests
import atexit  # <-- We can remove this
import sys     # <-- We can remove this
import os
import time
import threading

# --- Configuration ---
BACKEND_PORT = 8000 # This MUST match the port you run uvicorn on
BASE_URL = f"http://127.0.0.1:{BACKEND_PORT}"

#
# NO MORE PROCESS MANAGEMENT CODE (start_backend, stop_backend, etc.)
#

# --- Main Application Class ---

class App(ctk.CTk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # --- Window Setup ---
        self.title("Chinese CAD Translator (Dev Mode)")
        self.geometry("450x380")
        self.resizable(False, False)
        
        ctk.set_appearance_mode("System")
        
        # --- State Variables ---
        self.current_job_id = None
        self.selected_file_path = None
        self.is_processing = False

        # --- Main Frame ---
        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        self.label_title = ctk.CTkLabel(
            self.main_frame, 
            text="CAD Drawing Translator", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.label_title.pack(pady=(15, 20))

        # --- 1. File Selection ---
        self.button_select = ctk.CTkButton(
            self.main_frame, 
            text="1. Select PDF File", 
            command=self.select_file,
            font=ctk.CTkFont(size=14),
            height=40,
            state="disabled" # Disabled until backend is confirmed running
        )
        self.button_select.pack(pady=10, fill="x", padx=30)
        
        self.label_file = ctk.CTkLabel(self.main_frame, text="No file selected.", text_color="gray")
        self.label_file.pack(pady=5, padx=30)

        # --- 2. Translation ---
        self.button_translate = ctk.CTkButton(
            self.main_frame, 
            text="2. Start Translation", 
            command=self.start_translation,
            font=ctk.CTkFont(size=14),
            height=40,
            state="disabled"
        )
        self.button_translate.pack(pady=10, fill="x", padx=30)
        
        # --- 3. Status & Progress ---
        self.progressbar = ctk.CTkProgressBar(self.main_frame, height=10)
        self.progressbar.set(0)
        self.progressbar.pack_forget()

        self.label_status = ctk.CTkLabel(
            self.main_frame, 
            text="Status: Connecting to backend...", 
            font=ctk.CTkFont(size=12)
        )
        self.label_status.pack(pady=(20, 15))

        # Start backend health check
        threading.Thread(target=self.check_backend_health, daemon=True).start()

    def check_backend_health(self):
        """Polls the /health endpoint until the backend is ready."""
        print(f"Checking for backend at {BASE_URL}/health")
        retries = 0
        while retries < 10: # Try for 5 seconds
            try:
                response = requests.get(f"{BASE_URL}/health", timeout=1)
                if response.status_code == 200 and response.json().get("status") == "ready":
                    print("Backend is healthy. Enabling UI.")
                    self.after(0, self.on_backend_ready)
                    return
            except requests.exceptions.ConnectionError:
                print(f"Connection attempt {retries+1} failed...")
            except Exception as e:
                print(f"Health check failed: {e}")
                
            retries += 1
            time.sleep(0.5)
        
        # Failed to connect
        self.after(0, self.on_backend_failed)

    def on_backend_ready(self):
        """Callback run on the main thread when the backend is healthy."""
        self.label_status.configure(text="Status: Idle (Connected)")
        self.button_select.configure(state="normal")

    def on_backend_failed(self):
        """Callback run on the main thread if the backend can't be reached."""
        self.label_status.configure(text="Status: Backend not found.", text_color="red")
        messagebox.showerror(
            "Connection Error",
            f"Could not connect to the backend at {BASE_URL}\n\n"
            "Please ensure the backend server is running."
        )

    def select_file(self):
        """Opens a dialog to select a PDF file."""
        if self.is_processing:
            return
            
        file_path = filedialog.askopenfilename(filetypes=[("PDF Documents", "*.pdf")])
        if file_path:
            self.selected_file_path = file_path
            self.label_file.configure(text=os.path.basename(file_path), text_color="white")
            self.button_translate.configure(state="normal")
            self.label_status.configure(text="Status: Ready to translate", text_color="white")

    def start_translation(self):
        """Uploads the file to the backend to start the job."""
        if not self.selected_file_path or self.is_processing:
            return

        self.set_processing_state(True)
        self.label_status.configure(text="Status: Uploading file...")
        
        try:
            with open(self.selected_file_path, "rb") as f:
                files = {"file": (os.path.basename(self.selected_file_path), f, "application/pdf")}
                
                response = requests.post(f"{BASE_URL}/start-translation/", files=files, timeout=30)
            
            if response.status_code == 200:
                self.current_job_id = response.json().get("job_id")
                self.label_status.configure(text="Status: Processing... (This may take a while)")
                self.after(2000, self.check_status)
            else:
                self.reset_ui(error=f"Error starting job (Code: {response.status_code}): {response.text}")

        except requests.exceptions.ConnectionError:
             self.reset_ui(error="Error: Cannot connect to backend server. Is it running?")
        except requests.exceptions.ReadTimeout:
             self.reset_ui(error="Error: Upload timed out.")
        except Exception as e:
            self.reset_ui(error=f"An unexpected error occurred: {e}")

    def check_status(self):
        """Polls the backend's /job-status/ endpoint."""
        if not self.current_job_id or not self.is_processing:
            return

        try:
            response = requests.get(f"{BASE_URL}/job-status/{self.current_job_id}", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                
                if status == "complete":
                    self.progressbar.stop()
                    self.progressbar.set(1)
                    self.label_status.configure(text="Status: Translation Complete!", text_color="green")
                    self.download_file()
                
                elif status == "error":
                    self.reset_ui(error=f"Translation failed: {data.get('error')}")
                
                else:
                    self.label_status.configure(text=f"Status: {status}...")
                    self.after(2000, self.check_status)
            
            else:
                self.reset_ui(error=f"Error checking job status (Code: {response.status_code}).")

        except Exception as e:
            self.reset_ui(error=f"Error checking status: {e}")

    def download_file(self):
        """Prompts to save the file, then downloads from the /download/ endpoint."""
        save_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf")],
            initialfile=os.path.basename(self.selected_file_path).replace(".pdf", "_translated.pdf")
        )
        
        if not save_path:
            self.reset_ui() 
            return
        
        self.label_status.configure(text="Status: Downloading...")
        
        try:
            response = requests.get(f"{BASE_URL}/download/{self.current_job_id}", stream=True, timeout=60)
            
            if response.status_code == 200:
                with open(save_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                messagebox.showinfo("Success", f"File saved successfully to:\n{save_path}")
            else:
                messagebox.showerror("Error", "Could not download file from backend.")
            
            self.reset_ui()

        except Exception as e:
            self.reset_ui(error=f"Error saving file: {e}")

    def set_processing_state(self, is_processing: bool):
        """Helper function to lock/unlock the UI."""
        self.is_processing = is_processing
        if is_processing:
            self.button_select.configure(state="disabled")
            self.button_translate.configure(state="disabled")
            self.progressbar.pack(pady=10, fill="x", padx=30)
            self.progressbar.start()
        else:
            self.button_select.configure(state="normal")
            self.button_translate.configure(state="normal" if self.selected_file_path else "disabled")
            self.progressbar.stop()
            self.progressbar.pack_forget()

    def reset_ui(self, error=None):
        """Resets the UI to the idle state, showing an error if one occurred."""
        if error:
            print(f"Error encountered: {error}")
            messagebox.showerror("Error", str(error))
        
        self.current_job_id = None
        self.is_processing = False
        self.set_processing_state(False)
        self.label_status.configure(text="Status: Idle", text_color="gray")
        if not self.selected_file_path:
            self.label_file.configure(text="No file selected.", text_color="gray")


# --- Main execution ---
if __name__ == "__main__":
    
    # We no longer start or stop the backend.
    # We just create and run the GUI app.
    
    app = App()
    app.mainloop()