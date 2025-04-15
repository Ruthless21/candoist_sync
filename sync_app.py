# --- Standalone Local Desktop Application ---
# Syncs Canvas assignments to Todoist directly.
# Uses CustomTkinter for a modern GUI, requests for API calls, keyring for secure storage.
# Added course selection feature.

import customtkinter as ctk # Use customtkinter instead of tkinter/ttk
import requests # For making HTTP requests to APIs
import keyring # For securely storing API keys in OS credential manager
import json # For handling the config file (course selections)
import threading # To run sync process without freezing GUI
import time
import os
import sys
from datetime import datetime
from tkinter import messagebox # Keep standard messagebox for simple popups

# --- Configuration ---
# Key names for storing credentials in keyring
KEYRING_SERVICE_NAME = "CanvasTodoistSyncApp_Standalone"
KEYRING_USER_CANVAS_URL = "canvas_lms_url"
KEYRING_USER_CANVAS_KEY = "canvas_api_key"
KEYRING_USER_TODOIST_KEY = "todoist_api_key"

# Configuration file name
CONFIG_FILE = "config.json"

# --- Set Appearance ---
ctk.set_appearance_mode("System") # Modes: "System" (default), "Dark", "Light"
ctk.set_default_color_theme("blue") # Themes: "blue" (default), "green", "dark-blue"


class StandaloneCanvasTodoistSyncApp(ctk.CTk): # Inherit from CTk
    def __init__(self):
        super().__init__()

        self.title("Canvas -> Todoist Sync (Standalone)")
        self.geometry("750x600") # Increased size slightly for tabs/course list

        # --- Variables ---
        self.canvas_url = ctk.StringVar()
        self.canvas_api_key = ctk.StringVar()
        self.todoist_api_key = ctk.StringVar()
        self.is_syncing = False
        self.is_fetching_courses = False
        self.course_checkboxes = {} # Dictionary to store {course_id: checkbox_widget}
        self.course_checkbox_vars = {} # Dictionary to store {course_id: ctk.BooleanVar}

        # --- Configure grid layout (1x2) ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Create Frames ---
        # Left frame for settings and controls
        self.left_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.left_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.left_frame.grid_rowconfigure(10, weight=1) # Push elements up/down

        # Right frame will now contain tabs
        self.right_frame = ctk.CTkFrame(self, corner_radius=0)
        self.right_frame.grid(row=0, column=1, rowspan=4, sticky="nsew", padx=10, pady=10)
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        # --- Load saved credentials ---
        self.load_credentials() # Load before creating widgets

        # --- Create Widgets ---
        self.create_left_frame_widgets()
        self.create_right_frame_widgets() # This will now create the tab view

        # --- Initial Log Message ---
        self.log("Application started. Fetch courses or enter credentials.")


    # --- Configuration File Handling ---
    def load_course_selection(self):
        """Loads selected course IDs from the config file."""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config_data = json.load(f)
                    selected_ids = config_data.get("selected_course_ids", [])
                    # Ensure IDs are integers if stored as strings, handle potential errors
                    return {int(id_str) for id_str in selected_ids if str(id_str).isdigit()}
            else:
                self.log(f"{CONFIG_FILE} not found. No courses pre-selected.")
        except (json.JSONDecodeError, IOError, ValueError) as e:
            self.log(f"Error loading course selection from {CONFIG_FILE}: {e}")
        return set() # Return empty set on error or if file doesn't exist

    def save_course_selection(self, selected_ids):
        """Saves the list of selected course IDs to the config file."""
        try:
            # Convert set of integers to list of strings for JSON compatibility
            ids_to_save = [str(id_int) for id_int in selected_ids]
            with open(CONFIG_FILE, 'w') as f:
                json.dump({"selected_course_ids": ids_to_save}, f, indent=4)
            self.log(f"Saved course selection to {CONFIG_FILE}.")
        except IOError as e:
            self.log(f"Error saving course selection to {CONFIG_FILE}: {e}")
            messagebox.showerror("Config Error", f"Could not save course selection:\n{e}")

    def get_selected_courses_from_gui(self):
        """Gets the set of course IDs currently checked in the GUI."""
        selected_ids = set()
        for course_id, var in self.course_checkbox_vars.items():
            if var.get(): # Check if the BooleanVar is True
                selected_ids.add(course_id)
        return selected_ids

    # --- Credential Management (No changes needed) ---
    def load_credentials(self):
        """Load credentials securely from keyring"""
        try:
            c_url = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_USER_CANVAS_URL)
            c_key = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_USER_CANVAS_KEY)
            t_key = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_USER_TODOIST_KEY)

            if c_url: self.canvas_url.set(c_url)
            if c_key: self.canvas_api_key.set(c_key)
            if t_key: self.todoist_api_key.set(t_key)
        except Exception as e:
            print(f"Warning: Could not load credentials: {e}")

    def save_credentials(self):
        """Save credentials securely to keyring"""
        if not self.canvas_url.get() or not self.canvas_api_key.get() or not self.todoist_api_key.get():
             messagebox.showwarning("Missing Info", "Please enter Canvas URL, Canvas Key, and Todoist Key before saving.")
             return
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_USER_CANVAS_URL, self.canvas_url.get())
            keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_USER_CANVAS_KEY, self.canvas_api_key.get())
            keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_USER_TODOIST_KEY, self.todoist_api_key.get())
            self.log("Canvas/Todoist credentials saved securely.")
            messagebox.showinfo("Success", "Canvas/Todoist credentials saved securely.")
        except Exception as e:
            self.log(f"Error saving credentials: {e}")
            messagebox.showerror("Error", f"Could not save credentials securely:\n{e}")

    def clear_local_credentials(self):
        """Clear locally stored credentials"""
        if not messagebox.askyesno("Confirm Clear", "Are you sure you want to clear locally stored credentials? You will need to re-enter them."):
            return
        try:
            keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_USER_CANVAS_URL)
            keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_USER_CANVAS_KEY)
            keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_USER_TODOIST_KEY)
            self.canvas_url.set("")
            self.canvas_api_key.set("")
            self.todoist_api_key.set("")
            self.log("Cleared local credentials.")
            messagebox.showinfo("Cleared", "Locally stored credentials have been cleared.")
        except Exception as e:
            self.log(f"Error clearing credentials: {e}")
            messagebox.showerror("Error", f"Could not clear credentials:\n{e}")

    # --- Canvas API Interaction ---
    def get_canvas_courses(self):
        """Fetches active courses from Canvas API."""
        canvas_base = self.canvas_url.get()
        api_key = self.canvas_api_key.get()
        if not canvas_base or not api_key:
            self.log("Canvas URL or API Key missing.")
            return None, "Canvas URL or API Key missing."

        if not canvas_base.endswith('/'): canvas_base += '/'
        headers = {'Authorization': f'Bearer {api_key}'}
        # Fetch only active courses, include term info if needed later
        courses_url = f"{canvas_base}api/v1/courses?enrollment_state=active&per_page=100" # Increased per_page

        try:
            self.log("Fetching active courses from Canvas...")
            courses_response = requests.get(courses_url, headers=headers, timeout=20)
            courses_response.raise_for_status()
            courses = courses_response.json()
            # Filter out courses without an ID or name, sort by name
            valid_courses = [c for c in courses if c.get('id') and c.get('name')]
            valid_courses.sort(key=lambda x: x.get('course_code', x.get('name', '')).lower())
            self.log(f"Found {len(valid_courses)} valid active courses.")
            return valid_courses, None

        except requests.exceptions.RequestException as e:
            error_message = f"Canvas API Error fetching courses: {e}"
            if e.response is not None:
                 try:
                     error_detail = e.response.json().get('errors', [{}])[0].get('message', str(e))
                     status_code = e.response.status_code
                     error_message = f"Canvas API Error: {error_detail} (Status: {status_code})"
                     if status_code == 401: error_message += " - Check API Key/URL."
                 except (json.JSONDecodeError, IndexError, AttributeError):
                     error_message = f"Canvas API Error: {e.response.status_code} - {e.response.text}"
            self.log(error_message)
            return None, error_message
        except Exception as e:
            self.log(f"Unexpected error fetching courses: {e}")
            return None, f"Unexpected error fetching courses: {e}"


    def get_canvas_assignments_for_courses(self, course_ids):
        """Fetches assignments from Canvas API for a specific list of course IDs."""
        canvas_base = self.canvas_url.get()
        api_key = self.canvas_api_key.get()
        if not canvas_base or not api_key:
            self.log("Canvas URL or API Key missing.")
            return None, "Canvas URL or API Key missing."
        if not course_ids:
            self.log("No courses selected for sync.")
            return [], None # Return empty list if no courses selected

        if not canvas_base.endswith('/'): canvas_base += '/'
        headers = {'Authorization': f'Bearer {api_key}'}
        all_assignments = []
        total_courses = len(course_ids)

        for i, course_id in enumerate(course_ids):
            self.log(f"Fetching assignments for selected course {i+1}/{total_courses} (ID: {course_id})...")
            try:
                # Need course name for context - ideally fetch course details once if needed often
                # Or, pass course name along with ID if fetched previously
                # Quick fetch for name here (less efficient if many courses):
                course_info_url = f"{canvas_base}api/v1/courses/{course_id}"
                course_info_resp = requests.get(course_info_url, headers=headers, timeout=10)
                course_info_resp.raise_for_status()
                course_data = course_info_resp.json()
                course_name = course_data.get('course_code', course_data.get('name', f"Course {course_id}"))

                # Fetch assignments for this specific course
                assignments_url = f"{canvas_base}api/v1/courses/{course_id}/assignments?bucket=upcoming&include[]=submission&per_page=100"
                assign_response = requests.get(assignments_url, headers=headers, timeout=20)
                assign_response.raise_for_status()
                assignments = assign_response.json()
                self.log(f"  Found {len(assignments)} upcoming assignments for {course_name}.")

                for assign in assignments:
                    if assign.get('submission') and assign['submission'].get('submitted_at'):
                        self.log(f"  Skipping already submitted assignment: {assign.get('name')}")
                        continue
                    assign['course_name'] = course_name # Add course name context
                    all_assignments.append(assign)

            except requests.exceptions.RequestException as e:
                error_message = f"Canvas API Error for course {course_id}: {e}"
                # Simplified error extraction for loop
                if e.response is not None: error_message = f"Canvas API Error for course {course_id}: {e.response.status_code} - {e.response.text}"
                self.log(error_message)
                # Optionally decide whether to continue with other courses or stop
                # return None, error_message # Stop on first error
                continue # Continue with next course on error
            except Exception as e:
                self.log(f"Unexpected error fetching assignments for course {course_id}: {e}")
                continue # Continue with next course

        self.log(f"Total upcoming, unsubmitted assignments fetched for selected courses: {len(all_assignments)}")
        return all_assignments, None

    # --- Todoist API Interaction (No changes needed) ---
    def create_todoist_task(self, assignment):
        """Creates a single task in Todoist"""
        api_key = self.todoist_api_key.get()
        if not api_key:
            self.log("Todoist API Key missing.")
            return None, "Todoist API Key missing."

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'X-Request-Id': str(hash(assignment.get('html_url', assignment.get('id'))))
        }
        api_url = "https://api.todoist.com/rest/v2/tasks"

        content = f"[{assignment.get('course_name', 'Canvas')}] {assignment.get('name', 'Untitled Assignment')}"
        description = f"Link: {assignment.get('html_url', 'No link available')}"
        due_string = None
        if assignment.get('due_at'):
            try:
                due_date = datetime.fromisoformat(assignment['due_at'].replace('Z', '+00:00'))
                due_string = due_date.strftime('%Y-%m-%d')
            except ValueError:
                self.log(f"Could not parse due date: {assignment['due_at']}")

        task_data = {"content": content, "description": description}
        if due_string: task_data["due_date"] = due_string

        try:
            response = requests.post(api_url, headers=headers, json=task_data, timeout=15)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 10))
                self.log(f"Todoist rate limit hit. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                response = requests.post(api_url, headers=headers, json=task_data, timeout=15)

            response.raise_for_status()
            self.log(f"Successfully created Todoist task for: {assignment.get('name')}")
            return response.json(), None

        except requests.exceptions.RequestException as e:
            error_message = f"Todoist API Error: {e}"
            if e.response is not None:
                 status_code = e.response.status_code
                 try: error_detail = e.response.text
                 except Exception: error_detail = "(Could not decode error response)"
                 error_message = f"Todoist API Error: {error_detail} (Status: {status_code})"
                 if status_code in [401, 403]: error_message += " - Check your Todoist API Key."
            self.log(error_message)
            return None, error_message
        except Exception as e:
             self.log(f"Unexpected error creating Todoist task: {e}")
             return None, f"Unexpected error creating Todoist task: {e}"

    # --- Course Fetching and Display ---
    def fetch_and_display_courses(self):
        """Fetches courses from Canvas and updates the checkboxes in the GUI."""
        if self.is_fetching_courses:
            self.log("Already fetching courses.")
            return

        if not self.canvas_url.get() or not self.canvas_api_key.get():
             messagebox.showerror("Error", "Canvas URL and API Key must be configured first.")
             return

        self.is_fetching_courses = True
        self.fetch_courses_button.configure(text="Fetching...", state="disabled")
        self.log("Fetching courses to display...")

        courses, error = self.get_canvas_courses()

        if error:
            messagebox.showerror("Fetch Error", f"Failed to fetch courses from Canvas:\n{error}")
            self.log(f"Course fetch failed: {error}")
            self.finish_fetch_courses()
            return

        # Clear existing checkboxes before adding new ones
        for widget in self.courses_scrollable_frame.winfo_children():
            widget.destroy()
        self.course_checkboxes.clear()
        self.course_checkbox_vars.clear()

        # Load previously selected courses
        previously_selected_ids = self.load_course_selection()
        self.log(f"Loaded {len(previously_selected_ids)} previously selected course IDs.")

        if not courses:
            self.log("No active courses found.")
            ctk.CTkLabel(self.courses_scrollable_frame, text="No active courses found.").pack(pady=10)
        else:
            self.log(f"Displaying {len(courses)} courses...")
            for course in courses:
                course_id = course['id']
                # Display course code preferentially, fallback to name
                course_display_name = course.get('course_code', course.get('name', f"Unnamed Course {course_id}"))

                # Create a boolean variable for the checkbox state
                var = ctk.BooleanVar()
                # Set initial state based on loaded config
                if course_id in previously_selected_ids:
                    var.set(True)
                else:
                    var.set(False)

                # Store the variable
                self.course_checkbox_vars[course_id] = var

                # Create the checkbox
                checkbox = ctk.CTkCheckBox(self.courses_scrollable_frame,
                                           text=course_display_name,
                                           variable=var,
                                           onvalue=True, offvalue=False)
                checkbox.pack(anchor="w", padx=10, pady=2)

                # Store the checkbox widget itself (optional, might be useful later)
                self.course_checkboxes[course_id] = checkbox

            self.log("Finished displaying courses. Select courses to sync.")

        self.finish_fetch_courses()

    def finish_fetch_courses(self):
        """Resets the state after fetching courses."""
        self.is_fetching_courses = False
        if hasattr(self, 'fetch_courses_button'):
            self.fetch_courses_button.configure(text="Fetch Courses", state="normal")

    def fetch_courses_in_thread(self):
        """Runs the course fetching in a separate thread."""
        if self.is_fetching_courses:
            self.log("Already fetching courses.")
            return
        fetch_thread = threading.Thread(target=self.fetch_and_display_courses, daemon=True)
        fetch_thread.start()


    # --- Sync Logic ---
    def run_sync_process(self):
        """The main logic to sync assignments for SELECTED courses."""
        if self.is_syncing:
            self.log("Sync already in progress.")
            return

        # --- Check Credentials ---
        if not self.canvas_url.get() or not self.canvas_api_key.get() or not self.todoist_api_key.get():
             messagebox.showerror("Error", "Canvas URL, Canvas API Key, and Todoist API Key must be configured and saved.")
             self.log("Sync aborted: Missing credentials.")
             return

        # --- Get and Save Selected Courses ---
        selected_course_ids = self.get_selected_courses_from_gui()
        if not selected_course_ids:
             messagebox.showwarning("No Courses Selected", "Please select at least one course in the 'Courses' tab before syncing.")
             self.log("Sync aborted: No courses selected.")
             return
        self.save_course_selection(selected_course_ids) # Save current selection

        # --- Start Sync ---
        self.is_syncing = True
        self.sync_button.configure(text="Syncing...", state="disabled")
        self.log(f"--- Starting Sync Process for {len(selected_course_ids)} selected courses ---")

        # --- Get Assignments only for Selected Courses ---
        assignments, error = self.get_canvas_assignments_for_courses(selected_course_ids)
        if error:
            # Error already logged in the function
            messagebox.showerror("Sync Error", f"Failed to get assignments from Canvas:\n{error}")
            self.finish_sync()
            return

        if not assignments:
            self.log("No upcoming, unsubmitted assignments found in selected Canvas courses.")
            messagebox.showinfo("Sync Complete", "No new assignments found in selected courses to sync.")
            self.finish_sync()
            return

        self.log("Note: Duplicate checking relies on Todoist idempotency key.")
        synced_count = 0
        error_count = 0
        total_assignments = len(assignments)

        # --- Create Tasks in Todoist ---
        for i, assignment in enumerate(assignments):
            self.log(f"Processing assignment {i+1}/{total_assignments}: {assignment.get('name')} [{assignment.get('course_name')}]")
            task, error = self.create_todoist_task(assignment)
            if error:
                error_count += 1
                self.log(f"  -> Failed to create task: {error}")
            elif task:
                synced_count += 1
            time.sleep(0.5) # Be kind to APIs

        # --- Sync Finished ---
        self.log(f"--- Sync Process Finished ---")
        self.log(f"Successfully synced: {synced_count} assignments from selected courses.")
        if error_count > 0:
             self.log(f"Failed to sync: {error_count} assignments.")
             messagebox.showwarning("Sync Complete with Errors", f"Sync finished.\nSuccessfully created: {synced_count} tasks.\nFailed: {error_count} tasks.\nCheck log for details.")
        else:
             messagebox.showinfo("Sync Complete", f"Sync finished successfully.\nCreated {synced_count} tasks in Todoist from selected courses.")

        self.finish_sync()

    def finish_sync(self):
        """Reset sync state and button"""
        self.is_syncing = False
        if hasattr(self, 'sync_button'):
            self.sync_button.configure(text="Sync Now", state="normal")

    def sync_in_thread(self):
        """Run the sync process in a separate thread"""
        if self.is_syncing:
            self.log("Sync already running.")
            return
        sync_thread = threading.Thread(target=self.run_sync_process, daemon=True)
        sync_thread.start()

    # --- Logging ---
    def log(self, message):
        """Add message to the log CTkTextbox"""
        if hasattr(self, 'log_textbox'):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{now}] {message}\n"
            try:
                self.log_textbox.insert("end", log_entry)
                self.log_textbox.see("end")
            except Exception as e:
                print(f"LOG (Error updating textbox ignored): {message} - {e}")
        print(f"LOG: {message}")


    # --- UI Creation ---
    def create_left_frame_widgets(self):
        """Create widgets for the left settings/controls frame"""
        title_label = ctk.CTkLabel(self.left_frame, text="Settings & Controls", font=ctk.CTkFont(size=16, weight="bold"))
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        # Canvas URL
        canvas_url_label = ctk.CTkLabel(self.left_frame, text="Canvas URL:")
        canvas_url_label.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        canvas_url_entry = ctk.CTkEntry(self.left_frame, textvariable=self.canvas_url, width=200)
        canvas_url_entry.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Canvas API Key
        canvas_key_label = ctk.CTkLabel(self.left_frame, text="Canvas API Key:")
        canvas_key_label.grid(row=3, column=0, padx=20, pady=(5, 0), sticky="w")
        canvas_key_entry = ctk.CTkEntry(self.left_frame, textvariable=self.canvas_api_key, show="*", width=200)
        canvas_key_entry.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Todoist API Key
        todoist_key_label = ctk.CTkLabel(self.left_frame, text="Todoist API Key:")
        todoist_key_label.grid(row=5, column=0, padx=20, pady=(5, 0), sticky="w")
        todoist_key_entry = ctk.CTkEntry(self.left_frame, textvariable=self.todoist_api_key, show="*", width=200)
        todoist_key_entry.grid(row=6, column=0, padx=20, pady=(0, 15), sticky="ew")

        # Save Button
        save_button = ctk.CTkButton(self.left_frame, text="Save Credentials", command=self.save_credentials)
        save_button.grid(row=7, column=0, padx=20, pady=5, sticky="ew")

        # Clear Button
        clear_button = ctk.CTkButton(self.left_frame, text="Clear Credentials", command=self.clear_local_credentials, fg_color="transparent", border_width=1, text_color=("gray10", "#DCE4EE"))
        clear_button.grid(row=8, column=0, padx=20, pady=(5, 15), sticky="ew")

        # Fetch Courses Button (New)
        self.fetch_courses_button = ctk.CTkButton(self.left_frame, text="Fetch Courses", command=self.fetch_courses_in_thread)
        self.fetch_courses_button.grid(row=9, column=0, padx=20, pady=10, sticky="ew")

        # Sync Button
        self.sync_button = ctk.CTkButton(self.left_frame, text="Sync Now", command=self.sync_in_thread, font=ctk.CTkFont(size=14, weight="bold"))
        self.sync_button.grid(row=10, column=0, padx=20, pady=10, sticky="ew")

        # Appearance Mode OptionMenu (Pushed down)
        appearance_label = ctk.CTkLabel(self.left_frame, text="Appearance Mode:", anchor="w")
        appearance_label.grid(row=11, column=0, padx=20, pady=(20, 0), sticky="sw") # Added more padding top
        appearance_optionmenu = ctk.CTkOptionMenu(self.left_frame, values=["Light", "Dark", "System"],
                                                   command=self.change_appearance_mode_event)
        appearance_optionmenu.grid(row=12, column=0, padx=20, pady=10, sticky="sew")
        appearance_optionmenu.set("System") # Set default


    def create_right_frame_widgets(self):
        """Create the tab view for Logs and Courses"""
        self.tab_view = ctk.CTkTabview(self.right_frame, corner_radius=5)
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.tab_view.add("Log")
        self.tab_view.add("Courses")

        # --- Log Tab ---
        # Configure grid for the Log tab frame
        self.tab_view.tab("Log").grid_columnconfigure(0, weight=1)
        self.tab_view.tab("Log").grid_rowconfigure(0, weight=1)
        # Create Log Textbox inside the Log Tab
        self.log_textbox = ctk.CTkTextbox(self.tab_view.tab("Log"), wrap="word", corner_radius=3)
        self.log_textbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # --- Courses Tab ---
        # Configure grid for the Courses tab frame
        self.tab_view.tab("Courses").grid_columnconfigure(0, weight=1)
        self.tab_view.tab("Courses").grid_rowconfigure(0, weight=1) # Make scrollable frame expand
        # Create Scrollable Frame for course checkboxes inside the Courses Tab
        self.courses_scrollable_frame = ctk.CTkScrollableFrame(self.tab_view.tab("Courses"),
                                                               label_text="Select Courses to Sync",
                                                               corner_radius=3)
        self.courses_scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        # Add initial label
        ctk.CTkLabel(self.courses_scrollable_frame, text="Click 'Fetch Courses' in Settings to load.").pack(pady=10)


    def change_appearance_mode_event(self, new_appearance_mode: str):
        """Callback for changing the appearance mode"""
        ctk.set_appearance_mode(new_appearance_mode)


# --- Main Execution ---
if __name__ == "__main__":
    # --- Keyring Backend Setup Check (No changes needed) ---
    if getattr(sys, 'frozen', False):
        try:
            if sys.platform == 'win32': keyring.set_keyring(keyring.backends.Windows.WinVaultKeyring())
            elif sys.platform == 'darwin': keyring.set_keyring(keyring.backends.OS_X.Keyring())
            elif sys.platform.startswith('linux'):
                 try: keyring.set_keyring(keyring.backends.SecretService.Keyring())
                 except Exception: print("SecretService backend not found/failed, trying default...")
            print(f"Running bundled. Keyring backend: {keyring.get_keyring().__class__.__name__}")
        except Exception as e:
            print(f"Warning: Could not explicitly set keyring backend: {e}. Relying on default detection.")
    else:
        print("Running as script.")

    # --- Run the CustomTkinter App ---
    app = StandaloneCanvasTodoistSyncApp()
    app.mainloop()
