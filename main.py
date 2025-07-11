# main.py
import os

from browser_use.llm import BaseChatModel
# Set python's default encoding to utf-8
# This is to fix the issue with the browser_use library not specifying encoding when reading files

from browser_use.llm import ChatOpenAI
from browser_use import Agent, Browser, BrowserConfig, Controller  # Assuming BrowserConfig handles new args
import asyncio
import os
import gc
import sys
import traceback
import threading
import queue  # For thread-safe communication
import platform  # For opening file explorer
import subprocess  # For opening file explorer
import logging
from datetime import datetime  # For timestamping GUI messages

# --- Tkinter specific imports ---
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Menu, font as tkFont  # Added tkFont

from pydantic import SecretStr

# ----------- Action 相关代码全部在 action.py -------------
from actions import register_actions, extend_system_message

# ----------- ConfigTool Import -----------
from ConfigTool import ConfigManager, CONFIG_FILE_NAME
from ConfigTool import (
    DEFAULT_OPENAI_API_KEY, DEFAULT_OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL_NAME,
    DEFAULT_OCR_IMAGE_MODEL_NAME, DEFAULT_OCR_PDF_MODEL_NAME,
    DEFAULT_CHROME_BINARY_PATH, DEFAULT_OUTPUT_DIR, DEFAULT_TASK_PROMPT,
    DEFAULT_LANGUAGE, DEFAULT_BROWSER_CHOICE, DEFAULT_BROWSER_DISABLE_SECURITY,
    DEFAULT_BROWSER_KEEP_ALIVE, DEFAULT_BROWSER_USER_DATA_DIR
)
from tool import can_access_internal_service
from AISystemPrompt import SYSTEM_PROMPT_OPTIMIZE_TASK
from LogTool import LogTool
# ----------- Localization Import -----------
from localization import LanguageManager
from OpenAITool import OpenAITool

openAITool = OpenAITool()

# ----------- Global constants ------------
TASK_TEMPLATE_DIR = "resources/task_template"
LOCALES_DIR = "resources/locales"
LOG_FILENAME = "app.log"

# --- File Logger Setup ---
file_logger = LogTool(name='AgentAppFileLogger', to_file=True, to_stream=True).init_logger()
# --- End File Logger Setup ---

# ---- NEW USER SETTINGS DEFAULTS ----
USER_TYPE = "Personal"  # Enterprise or Personal
ENTERPRISE_NETWORK_CHECK_HOST = "10.0.182.21"
ENTERPRISE_NETWORK_CHECK_PORT = 22
# ---- END NEW USER SETTINGS DEFAULTS ----

# --- Configuration Loading START ---
# Initialize ConfigManager AFTER logger is set up
config_manager = ConfigManager(config_file_path_override=CONFIG_FILE_NAME, logger_instance=file_logger)

# Load effective values using ConfigManager
OPENAI_API_KEY_EFFECTIVE = config_manager.get_value('OPENAI', 'API_KEY', DEFAULT_OPENAI_API_KEY,
                                                    treat_empty_as_default=True)
OPENAI_BASE_URL_EFFECTIVE = config_manager.get_value('OPENAI', 'BASE_URL', DEFAULT_OPENAI_BASE_URL,
                                                     treat_empty_as_default=True)
OPENAI_MODEL_NAME_EFFECTIVE = config_manager.get_value('OPENAI', 'MODEL_NAME', DEFAULT_OPENAI_MODEL_NAME)
OCR_IMAGE_MODEL_EFFECTIVE = config_manager.get_value('OPENAI', 'OCR_IMAGE_MODEL_NAME', DEFAULT_OCR_IMAGE_MODEL_NAME)
OCR_PDF_MODEL_EFFECTIVE = config_manager.get_value('OPENAI', 'OCR_PDF_MODEL_NAME', DEFAULT_OCR_PDF_MODEL_NAME)

INITIAL_CHROME_BINARY_PATH = config_manager.get_value('PATHS', 'CHROME_BINARY_PATH', DEFAULT_CHROME_BINARY_PATH)
INITIAL_OUTPUT_DIR = config_manager.get_value('PATHS', 'OUTPUT_DIR', DEFAULT_OUTPUT_DIR)

# DEFAULT_TASK_PROMPT is already unescaped. get_value will handle unescaping if read from file.
INITIAL_TASK_PROMPT = config_manager.get_value('UI_DEFAULTS', 'TASK_PROMPT', DEFAULT_TASK_PROMPT)
INITIAL_LANGUAGE = config_manager.get_value('UI_DEFAULTS', 'LANGUAGE', DEFAULT_LANGUAGE)

INITIAL_BROWSER_CHOICE = config_manager.get_value('BROWSER_ADVANCED_SETTINGS', 'BROWSER_CHOICE', DEFAULT_BROWSER_CHOICE)
INITIAL_BROWSER_DISABLE_SECURITY = config_manager.get_value('BROWSER_ADVANCED_SETTINGS', 'DISABLE_SECURITY',
                                                            DEFAULT_BROWSER_DISABLE_SECURITY, is_bool=True)
INITIAL_BROWSER_KEEP_ALIVE = config_manager.get_value('BROWSER_ADVANCED_SETTINGS', 'KEEP_ALIVE',
                                                      DEFAULT_BROWSER_KEEP_ALIVE, is_bool=True)
INITIAL_BROWSER_USER_DATA_DIR = config_manager.get_value('BROWSER_ADVANCED_SETTINGS', 'USER_DATA_DIR',
                                                         DEFAULT_BROWSER_USER_DATA_DIR)

# --- Configuration END ---

# ---- Language Manager Initialization ----
lang_manager = LanguageManager(locales_dir=LOCALES_DIR, initial_lang=INITIAL_LANGUAGE, fallback_lang=DEFAULT_LANGUAGE)
# ---- End Language Manager ----

# ----------- 全局变量、控制器 & Action注册 -----------
gui_feedback_queue = queue.Queue()
controller = Controller()
action_config = {
    "default_model_name": OPENAI_MODEL_NAME_EFFECTIVE,
    "ocr_image_model_name": OCR_IMAGE_MODEL_EFFECTIVE,
    "ocr_pdf_model_name": OCR_PDF_MODEL_EFFECTIVE
}
register_actions(controller, gui_feedback_queue, INITIAL_OUTPUT_DIR, file_logger, action_config)


# --- Agent Logic ---
async def run_agent_async(task_text, openai_api_key, openai_base_url, openai_model_name,
                          chrome_binary_path_or_none, output_dir_for_this_task, stop_event: threading.Event,
                          browser_disable_security: bool,
                          browser_keep_alive: bool,
                          browser_user_data_dir: str,
                          use_vision_param=False, browser_choice_info="Unknown",
                          actual_browser_choice: str = DEFAULT_BROWSER_CHOICE):
    def log_to_gui(message_key, level="INFO_GUI", **kwargs):
        gui_feedback_queue.put({"type": "log", "message": message_key, "level": level, "kwargs": kwargs})

    file_logger.info(f"Agent task started. Task (first 100 chars): '{task_text[:100]}...'")
    file_logger.info(
        f"Config: Model='{openai_model_name}', OCR_Image='{action_config['ocr_image_model_name']}', OCR_PDF='{action_config['ocr_pdf_model_name']}', API_BASE='{openai_base_url}', API_KEY_SET={'Yes' if openai_api_key and openai_api_key != DEFAULT_OPENAI_API_KEY else 'No/Default'}, OutputDir='{output_dir_for_this_task}'")
    file_logger.info(f"Browser choice (from UI for high-level log): {browser_choice_info}")
    os.environ["OPENAI_API_KEY"] = openai_api_key
    os.environ["OPENAI_BASE_URL"] = openai_base_url

    if stop_event.is_set():
        log_to_gui("agent_log_cancelled_before_start", "WARNING_GUI")
        file_logger.warning("Agent run cancelled before start (due to stop request before full initialization)")
        gui_feedback_queue.put({"type": "task_complete", "stopped_by_user": True, "error": False})
        return

    browser_instance = None
    task_completed_successfully_flag = False  # Flag to denote successful agent.run() outcome
    try:
        abs_output_dir = os.path.abspath(output_dir_for_this_task)
        os.makedirs(abs_output_dir, exist_ok=True)
        controller.current_output_dir_from_gui = abs_output_dir

        log_to_gui("agent_log_output_dir_set", abs_output_dir=abs_output_dir)
        file_logger.info(f"Output directory: {abs_output_dir}")
        llm = ChatOpenAI(model=openai_model_name, base_url=openai_base_url, api_key=openai_api_key)
        if stop_event.is_set():
            log_to_gui("agent_log_cancelled_before_browser", "WARNING_GUI")
            file_logger.warning("Agent run cancelled before browser setup (due to stop request)")
            gui_feedback_queue.put({"type": "task_complete", "stopped_by_user": True, "error": False})
            return

        log_to_gui("agent_log_using_default_model", model_name=openai_model_name)
        log_to_gui("agent_log_using_ocr_image_model", model_name=action_config['ocr_image_model_name'])
        log_to_gui("agent_log_using_ocr_pdf_model", model_name=action_config['ocr_pdf_model_name'])

        browser_config_params = {}
        browser_config_params["disable_security"] = browser_disable_security
        browser_config_params["keep_alive"] = browser_keep_alive

        current_extra_args = []
        file_logger.info(f"Agent: Effective browser choice for this run's logic: '{actual_browser_choice}'")
        file_logger.info(
            f"Agent: Raw browser settings from UI: DisableSecurity={browser_disable_security}, KeepAlive={browser_keep_alive}, UserDataDir='{browser_user_data_dir}'")

        if actual_browser_choice == "custom":
            if chrome_binary_path_or_none and chrome_binary_path_or_none.strip():
                file_logger.info(
                    f"Agent: Configuring 'custom' browser with binary path: '{chrome_binary_path_or_none}'")
                browser_config_params["browser_binary_path"] = chrome_binary_path_or_none

                if browser_user_data_dir:
                    try:
                        abs_user_data_dir_path = os.path.abspath(browser_user_data_dir)
                        os.makedirs(abs_user_data_dir_path, exist_ok=True)
                        current_extra_args.append(f'--user-data-dir={abs_user_data_dir_path}')
                        file_logger.info(
                            f"Agent: For custom browser, attempting to add --user-data-dir='{abs_user_data_dir_path}' to extra args.")
                    except Exception as e_mkdir_custom_udd:
                        file_logger.error(
                            f"Agent: Could not create/access user data directory '{browser_user_data_dir}' for custom browser: {e_mkdir_custom_udd}. Proceeding without it for custom browser's extra args.")
                        log_to_gui("agent_log_error_user_data_dir", dir_path=browser_user_data_dir,
                                   error=str(e_mkdir_custom_udd), level="WARNING_GUI")
                else:
                    file_logger.info(
                        "Agent: 'custom' browser choice, but no user_data_dir specified by user. Not adding --user-data-dir.")
            else:
                file_logger.warning(
                    f"Agent: 'custom' browser choice selected, but NO binary path was provided (path: '{chrome_binary_path_or_none}'). "
                    f"The Browser library will likely default to Playwright's bundled browser or try to find a system browser.")
                if browser_user_data_dir:
                    file_logger.info(
                        f"Agent: User data directory '{browser_user_data_dir}' was specified, but might be ignored due to missing custom browser path.")

        elif actual_browser_choice == "playwright_bundled":
            file_logger.info("Agent: 'playwright_bundled' browser choice. Playwright will use its bundled browser. "
                             "Any 'Custom Chrome Binary Path' from UI is ignored.")
            if browser_user_data_dir:
                file_logger.info(
                    f"Agent: 'playwright_bundled' choice. User data directory '{browser_user_data_dir}' was specified in UI. "
                    "This might be used by Playwright if BrowserConfig/Browser lib handles it for persistent_context with bundled browsers. "
                    "If not, it may require specific persistent context setup not covered by 'extra_browser_args' for bundled.")
        else:
            file_logger.warning(
                f"Agent: Unknown actual_browser_choice: '{actual_browser_choice}'. Browser behavior may be unpredictable; likely defaults to bundled.")

        if actual_browser_choice == "playwright_bundled" and browser_user_data_dir:
            try:
                abs_user_data_dir_path = os.path.abspath(browser_user_data_dir)
                os.makedirs(abs_user_data_dir_path, exist_ok=True)
                browser_config_params[
                    "user_data_dir"] = abs_user_data_dir_path  # This key is read by Browser for Playwright context
                file_logger.info(
                    f"Agent: For playwright_bundled, setting user_data_dir for persistent context: '{abs_user_data_dir_path}'")
            except Exception as e_mkdir_bundled_udd:
                file_logger.error(
                    f"Agent: Could not create/access user data directory '{browser_user_data_dir}' for playwright_bundled context: {e_mkdir_bundled_udd}. Proceeding without it.")
                log_to_gui("agent_log_error_user_data_dir", dir_path=browser_user_data_dir,
                           error=str(e_mkdir_bundled_udd), level="WARNING_GUI")

        if current_extra_args:
            browser_config_params["extra_browser_args"] = current_extra_args
            file_logger.info(f"Browser extra arguments prepared for BrowserConfig: {current_extra_args}")
        else:
            file_logger.info(
                "No extra browser arguments (like --user-data-dir for custom browser) added to BrowserConfig construction.")

        file_logger.debug(f"Instantiating Browser with resolved config_params: {browser_config_params}")
        browser_instance = Browser(config=BrowserConfig(**browser_config_params))
        file_logger.info("Browser instantiated.")

        if stop_event.is_set():
            log_to_gui("agent_log_cancelled_before_agent_init", "WARNING_GUI")
            file_logger.warning("Agent run cancelled before agent initialization (due to stop request)")
            gui_feedback_queue.put({"type": "task_complete", "stopped_by_user": True, "error": False})
            if browser_instance: await browser_instance.close()
            return

        agent = Agent(
            task=task_text,
            llm=llm,
            browser=browser_instance,
            controller=controller,
            extend_system_message=extend_system_message,
            override_system_message=SYSTEM_PROMPT_OPTIMIZE_TASK,
            use_vision=use_vision_param,
            generate_gif=True
        )

        log_to_gui("agent_log_executing_task", level="IMPORTANT_GUI")
        file_logger.info("--- Agent core execution started. ---")
        result = await agent.run()
        file_logger.info("--- Agent core execution finished. ---")
        task_completed_successfully_flag = True

        if stop_event.is_set():
            log_to_gui("agent_log_task_completed_stop_requested", level="WARNING_GUI")
            file_logger.warning(
                f"Agent operation completed, but a stop was requested during execution. Result might be partial or reflect state at stop time. Result: {str(result)[:200]}...")
        else:
            log_to_gui("agent_log_execution_finished_processing", level="IMPORTANT_GUI")
            result_str = str(result)
            log_to_gui("agent_log_final_result_summary", summary=f"\n{result.final_result()}")
            file_logger.info(f"--- Agent Execution Result ---:\n{result_str}")
            file_logger.info(f"--- Agent Execution Result(final) ---:\n{result.final_result()}")
            log_to_gui("agent_log_check_output_dir", level="IMPORTANT_GUI", abs_output_dir=abs_output_dir)

        gui_feedback_queue.put({"type": "task_complete", "stopped_by_user": stop_event.is_set(), "error": False})

    except Exception as e:
        traceback.print_exc()
        tb_full = traceback.format_exc()
        error_context_message = lang_manager.get(
            "error_context_agent_stop_requested") if stop_event.is_set() else lang_manager.get(
            "error_context_main_agent_error")
        error_msg_summary = f"{error_context_message}: {type(e).__name__} - {str(e)[:150]}"
        log_to_gui("agent_log_error_main", error_summary=error_msg_summary, level="ERROR_GUI")
        file_logger.error(f"CRITICAL ERROR during agent execution: {e}\n{tb_full}")

        if hasattr(controller, 'current_output_dir_from_gui'):
            del controller.current_output_dir_from_gui
            file_logger.debug("Cleaned up controller.current_output_dir_from_gui.")

        gui_feedback_queue.put({"type": "task_complete", "stopped_by_user": stop_event.is_set(), "error": True})

    finally:
        if browser_instance:
            await browser_instance.close()
            file_logger.info("Browser instance closed in run_agent_async finally block.")

        file_logger.info("Agent run_agent_async finished (successfully or with error).")


# --- OpenAI Configuration Dialog ---
class OpenAIConfigDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.transient(parent)
        self.grab_set()

        self.api_key_var = tk.StringVar()
        self.base_url_var = tk.StringVar()
        self.model_name_var = tk.StringVar()
        self.ocr_image_model_var = tk.StringVar()
        self.ocr_pdf_model_var = tk.StringVar()

        self.load_config_values()
        self.build_ui()
        self.update_ui_text()

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.center_window()
        self.update_idletasks()
        self.minsize(self.winfo_width(), self.winfo_height())

    def build_ui(self):
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(expand=True, fill=tk.BOTH)

        self.basic_config_frame = ttk.LabelFrame(self.main_frame, padding="10")
        self.basic_config_frame.pack(fill=tk.X, expand=True, pady=(0, 10))

        self.api_key_label = ttk.Label(self.basic_config_frame)
        self.api_key_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(self.basic_config_frame, textvariable=self.api_key_var, width=60, show="*").grid(row=0, column=1,
                                                                                                   padx=5, pady=5,
                                                                                                   sticky="ew")

        self.base_url_label = ttk.Label(self.basic_config_frame)
        self.base_url_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(self.basic_config_frame, textvariable=self.base_url_var, width=60).grid(row=1, column=1, padx=5,
                                                                                          pady=5, sticky="ew")

        self.model_name_label = ttk.Label(self.basic_config_frame)
        self.model_name_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(self.basic_config_frame, textvariable=self.model_name_var, width=60).grid(row=2, column=1, padx=5,
                                                                                            pady=5, sticky="ew")
        self.basic_config_frame.columnconfigure(1, weight=1)

        self.ocr_config_frame = ttk.LabelFrame(self.main_frame, padding="10")
        self.ocr_config_frame.pack(fill=tk.X, expand=True)

        self.ocr_image_label = ttk.Label(self.ocr_config_frame)
        self.ocr_image_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(self.ocr_config_frame, textvariable=self.ocr_image_model_var, width=60).grid(row=0, column=1, padx=5,
                                                                                               pady=5, sticky="ew")

        self.ocr_pdf_label = ttk.Label(self.ocr_config_frame)
        self.ocr_pdf_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(self.ocr_config_frame, textvariable=self.ocr_pdf_model_var, width=60).grid(row=1, column=1, padx=5,
                                                                                             pady=5, sticky="ew")
        self.ocr_config_frame.columnconfigure(1, weight=1)

        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.pack(pady=10, fill=tk.X, side=tk.BOTTOM)
        self.cancel_button = ttk.Button(self.button_frame, command=self.destroy)
        self.cancel_button.pack(side=tk.RIGHT, padx=5)
        self.save_button = ttk.Button(self.button_frame, command=self.save_config)
        self.save_button.pack(side=tk.RIGHT, padx=5)

    def update_ui_text(self):
        self.title(lang_manager.get("openai_config_dialog_title"))
        self.basic_config_frame.config(text=lang_manager.get("frame_basic_config"))
        self.api_key_label.config(text=lang_manager.get("label_openai_api_key"))
        self.base_url_label.config(text=lang_manager.get("label_openai_base_url"))
        self.model_name_label.config(text=lang_manager.get("label_default_model_name"))
        self.ocr_config_frame.config(text=lang_manager.get("frame_ocr_config"))
        self.ocr_image_label.config(text=lang_manager.get("label_ocr_image_model"))
        self.ocr_pdf_label.config(text=lang_manager.get("label_ocr_pdf_model"))
        self.save_button.config(text=lang_manager.get("button_save"))
        self.cancel_button.config(text=lang_manager.get("button_cancel"))

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def load_config_values(self):
        self.api_key_var.set(OPENAI_API_KEY_EFFECTIVE)
        self.base_url_var.set(OPENAI_BASE_URL_EFFECTIVE)
        self.model_name_var.set(OPENAI_MODEL_NAME_EFFECTIVE)
        self.ocr_image_model_var.set(OCR_IMAGE_MODEL_EFFECTIVE)
        self.ocr_pdf_model_var.set(OCR_PDF_MODEL_EFFECTIVE)

    def save_config(self):
        global OPENAI_API_KEY_EFFECTIVE, OPENAI_BASE_URL_EFFECTIVE, OPENAI_MODEL_NAME_EFFECTIVE
        global OCR_IMAGE_MODEL_EFFECTIVE, OCR_PDF_MODEL_EFFECTIVE, action_config

        new_api_key = self.api_key_var.get()
        new_base_url = self.base_url_var.get()
        new_model_name = self.model_name_var.get()
        new_ocr_image_model = self.ocr_image_model_var.get()
        new_ocr_pdf_model = self.ocr_pdf_model_var.get()

        try:
            config_manager.set_value('OPENAI', 'API_KEY', new_api_key)
            config_manager.set_value('OPENAI', 'BASE_URL', new_base_url)
            config_manager.set_value('OPENAI', 'MODEL_NAME', new_model_name)
            config_manager.set_value('OPENAI', 'OCR_IMAGE_MODEL_NAME', new_ocr_image_model)
            config_manager.set_value('OPENAI', 'OCR_PDF_MODEL_NAME', new_ocr_pdf_model)

            if config_manager.save():
                OPENAI_API_KEY_EFFECTIVE = new_api_key
                OPENAI_BASE_URL_EFFECTIVE = new_base_url
                OPENAI_MODEL_NAME_EFFECTIVE = new_model_name
                OCR_IMAGE_MODEL_EFFECTIVE = new_ocr_image_model
                OCR_PDF_MODEL_EFFECTIVE = new_ocr_pdf_model

                action_config["default_model_name"] = new_model_name
                action_config["ocr_image_model_name"] = new_ocr_image_model
                action_config["ocr_pdf_model_name"] = new_ocr_pdf_model

                file_logger.info(
                    f"OpenAI configuration saved to '{config_manager.config_file_path}' and updated in current session (incl. OCR models).")
                messagebox.showinfo(lang_manager.get("message_success_title"),
                                    lang_manager.get("openai_config_saved_success"), parent=self)
                self.destroy()
            else:
                messagebox.showerror(lang_manager.get("message_error_title"),
                                     lang_manager.get("openai_config_saved_failed", error="See app.log"), parent=self)

        except Exception as e:
            file_logger.error(f"Unexpected error saving OpenAI config: {e}\n{traceback.format_exc()}")
            messagebox.showerror(lang_manager.get("message_error_title"),
                                 lang_manager.get("openai_config_unexpected_error", error=e), parent=self)


# --- Tkinter GUI Application ---
class AgentApp:
    # Define a dictionary for log levels and their corresponding tag names and colors
    LOG_LEVEL_CONFIG = {
        "INFO_GUI": {"tag": "info_log", "color": "black"},  # Or your theme's default text color
        "ACTION_GUI": {"tag": "action_log", "color": "green"},
        "WARNING_GUI": {"tag": "warning_log", "color": "darkorange"},
        "ERROR_GUI": {"tag": "error_log", "color": "red"},
        "IMPORTANT_GUI": {"tag": "important_log", "color": "blue"},  # Or "royalblue"
        "AGENT_INTERNAL_LOG": {"tag": "agent_internal_log", "color": "purple"}  # New for agent listener
    }

    def __init__(self, root):
        self.root = root
        root.geometry("1000x850")

        self.stop_event = threading.Event()
        self.agent_thread = None

        self.output_dir_var = tk.StringVar(value=os.path.abspath(INITIAL_OUTPUT_DIR))
        self.chrome_path_var = tk.StringVar(value=INITIAL_CHROME_BINARY_PATH)
        self.browser_choice_var = tk.StringVar(value=INITIAL_BROWSER_CHOICE)
        self.previous_browser_choice = tk.StringVar(value=INITIAL_BROWSER_CHOICE)

        self.language_var = tk.StringVar(value=lang_manager.current_lang_code)

        self.browser_disable_security_var = tk.BooleanVar(value=INITIAL_BROWSER_DISABLE_SECURITY)
        self.browser_keep_alive_var = tk.BooleanVar(value=INITIAL_BROWSER_KEEP_ALIVE)
        self.browser_user_data_dir_var = tk.StringVar(value=INITIAL_BROWSER_USER_DATA_DIR)

        self.saved_files_data = []

        self.build_ui()  # build_ui will now call _configure_log_tags
        self.update_ui_text()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        file_logger.info("GUI Application initialized.")
        self.process_gui_queue()
        self.update_browser_path_state()
        self.previous_browser_choice.set(self.browser_choice_var.get())
        LogTool(name='browser_use.agent.service', to_file=True, to_stream=True,
                listener=self.agent_log_listener).init_logger()

    def _configure_log_tags(self):
        """Configure tags for colored logging in self.log_text."""
        default_font = tkFont.nametofont("TkDefaultFont").actual()

        for level_config in self.LOG_LEVEL_CONFIG.values():
            tag_name = level_config["tag"]
            color = level_config["color"]
            font_config = (default_font['family'], default_font['size'])
            if tag_name == "error_log" or tag_name == "important_log":
                font_config = (default_font['family'], default_font['size'], 'bold')

            self.log_text.tag_configure(tag_name, foreground=color, font=font_config)

        # Example of a more specific tag if needed (e.g., just for timestamp)
        # self.log_text.tag_configure("timestamp", foreground="gray", font=(default_font['family'], default_font['size']-1))

    def agent_log_listener(self, record: logging.LogRecord):
        # Pass a specific level for messages from this listener
        self.log_message_to_gui(record.getMessage(), level="AGENT_INTERNAL_LOG")

    def build_ui(self):
        self.menubar = Menu(self.root)

        self.setting_menu = Menu(self.menubar, tearoff=0)
        self.setting_menu.add_command(command=self.show_openai_config_dialog)
        self.setting_menu.add_command(command=self.view_config_file)
        self.setting_menu.add_command(command=self.view_log_file)
        self.setting_menu.add_separator()
        self.setting_menu.add_command(command=self.on_closing)
        self.menubar.add_cascade(label="_PLACEHOLDER_SETTING_MENU_", menu=self.setting_menu)

        self.language_menu = Menu(self.menubar, tearoff=0)
        self.language_menu.add_radiobutton(variable=self.language_var, value="en", command=self.change_language)
        self.language_menu.add_radiobutton(variable=self.language_var, value="zh", command=self.change_language)
        self.menubar.add_cascade(label="_PLACEHOLDER_LANGUAGE_MENU_", menu=self.language_menu)

        self.root.config(menu=self.menubar)

        self.main_paned_window = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        self.main_paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.top_frame = ttk.Frame(self.main_paned_window, padding="10")
        self.main_paned_window.add(self.top_frame, weight=1)

        self.config_frame_lframe = ttk.LabelFrame(self.top_frame)
        self.config_frame_lframe.pack(fill=tk.X, expand=False, pady=5)
        self.output_dir_label = ttk.Label(self.config_frame_lframe)
        self.output_dir_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.output_dir_entry = ttk.Entry(self.config_frame_lframe, textvariable=self.output_dir_var, width=70)
        self.output_dir_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.choose_dir_button = ttk.Button(self.config_frame_lframe, command=self.choose_output_dir)
        self.choose_dir_button.grid(row=0, column=2, padx=5, pady=5)
        self.config_frame_lframe.columnconfigure(1, weight=1)

        self.browser_frame_lframe = ttk.LabelFrame(self.top_frame)
        self.browser_frame_lframe.pack(fill=tk.X, expand=False, pady=5)

        current_row_browser = 0
        self.custom_chrome_radio = ttk.Radiobutton(self.browser_frame_lframe, variable=self.browser_choice_var,
                                                   value="custom", command=self.on_browser_choice_changed)
        self.custom_chrome_radio.grid(row=current_row_browser, column=0, padx=5, pady=2, sticky="w")
        self.chrome_path_entry = ttk.Entry(self.browser_frame_lframe, textvariable=self.chrome_path_var, width=70)
        self.chrome_path_entry.grid(row=current_row_browser, column=1, padx=5, pady=2, sticky="ew")
        self.browse_exe_button = ttk.Button(self.browser_frame_lframe, command=self.choose_chrome_path)
        self.browse_exe_button.grid(row=current_row_browser, column=2, padx=5, pady=2)
        current_row_browser += 1

        self.playwright_radio = ttk.Radiobutton(self.browser_frame_lframe, variable=self.browser_choice_var,
                                                value="playwright_bundled", command=self.on_browser_choice_changed)
        self.playwright_radio.grid(row=current_row_browser, column=0, columnspan=3, padx=5, pady=2, sticky="w")
        current_row_browser += 1

        self.disable_security_checkbox = ttk.Checkbutton(self.browser_frame_lframe,
                                                         variable=self.browser_disable_security_var)
        self.disable_security_checkbox.grid(row=current_row_browser, column=0, columnspan=3, padx=5, pady=2, sticky="w")
        current_row_browser += 1

        self.keep_alive_checkbox = ttk.Checkbutton(self.browser_frame_lframe,
                                                   variable=self.browser_keep_alive_var)
        self.keep_alive_checkbox.grid(row=current_row_browser, column=0, columnspan=3, padx=5, pady=2, sticky="w")
        current_row_browser += 1

        self.user_data_dir_label = ttk.Label(self.browser_frame_lframe)
        self.user_data_dir_label.grid(row=current_row_browser, column=0, padx=5, pady=2, sticky="w")
        self.user_data_dir_entry = ttk.Entry(self.browser_frame_lframe,
                                             textvariable=self.browser_user_data_dir_var, width=60)
        self.user_data_dir_entry.grid(row=current_row_browser, column=1, padx=5, pady=2, sticky="ew")
        self.browse_user_data_dir_button = ttk.Button(self.browser_frame_lframe,
                                                      command=self.choose_browser_user_data_dir)
        self.browse_user_data_dir_button.grid(row=current_row_browser, column=2, padx=5, pady=2)
        self.browser_frame_lframe.columnconfigure(1, weight=1)

        self.task_frame_lframe = ttk.LabelFrame(self.top_frame)
        self.task_frame_lframe.pack(fill=tk.BOTH, expand=True, pady=5)
        template_button_frame = ttk.Frame(self.task_frame_lframe)
        template_button_frame.pack(fill=tk.X, pady=(5, 5), padx=5)

        self.optimize_prompt_button = ttk.Button(template_button_frame, command=self.optimize_task_prompt)
        self.optimize_prompt_button.pack(side=tk.LEFT, padx=(0, 5))

        self.load_template_button = ttk.Button(template_button_frame, command=self.load_task_template)
        self.load_template_button.pack(side=tk.LEFT, padx=(0, 5))
        self.save_template_button = ttk.Button(template_button_frame, command=self.save_task_template)
        self.save_template_button.pack(side=tk.LEFT, padx=(0, 5))
        self.set_default_button = ttk.Button(template_button_frame, command=self.set_current_task_as_default)
        self.set_default_button.pack(side=tk.LEFT, padx=(0, 5))
        self.task_text = scrolledtext.ScrolledText(self.task_frame_lframe, wrap=tk.WORD, height=10, width=80,
                                                   relief=tk.SOLID, borderwidth=1)
        self.task_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        self.task_text.insert(tk.END, INITIAL_TASK_PROMPT)

        button_frame = ttk.Frame(self.top_frame)
        button_frame.pack(pady=(5, 10), fill=tk.X, expand=False)
        self.run_button = ttk.Button(button_frame, command=self.start_agent_task)
        self.run_button.pack(side=tk.LEFT, padx=10)
        self.stop_button = ttk.Button(button_frame, command=self.request_stop_agent_task, state='disabled')
        self.stop_button.pack(side=tk.LEFT, padx=10)
        self.force_exit_button = ttk.Button(button_frame, command=self.force_exit_app)
        self.force_exit_button.pack(side=tk.LEFT, padx=10)

        self.bottom_paned_window = ttk.PanedWindow(self.main_paned_window, orient=tk.HORIZONTAL)
        self.main_paned_window.add(self.bottom_paned_window, weight=2)

        self.log_frame_lframe = ttk.LabelFrame(self.bottom_paned_window)
        self.bottom_paned_window.add(self.log_frame_lframe, weight=3)
        self.log_text = scrolledtext.ScrolledText(self.log_frame_lframe, wrap=tk.WORD, height=15, state='disabled',
                                                  relief=tk.SOLID, borderwidth=1)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # Configure tags for colored logging
        self._configure_log_tags()  # MOVED here, after log_text is created

        self.files_frame_lframe = ttk.LabelFrame(self.bottom_paned_window)
        self.bottom_paned_window.add(self.files_frame_lframe, weight=1)
        listbox_container = ttk.Frame(self.files_frame_lframe)
        listbox_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 0))
        self.files_listbox_scrollbar = ttk.Scrollbar(listbox_container, orient=tk.VERTICAL)
        self.files_listbox = tk.Listbox(listbox_container, height=10, relief=tk.SOLID, borderwidth=1,
                                        yscrollcommand=self.files_listbox_scrollbar.set)
        self.files_listbox_scrollbar.config(command=self.files_listbox.yview)
        self.files_listbox_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.files_listbox.bind("<Double-Button-1>", self.open_selected_file_directly)
        self.files_listbox.bind("<Return>", self.open_selected_file_directly)
        file_buttons_frame = ttk.Frame(self.files_frame_lframe)
        file_buttons_frame.pack(pady=(5, 5), padx=5, fill=tk.X)
        self.open_file_button = ttk.Button(file_buttons_frame, command=self.open_selected_file_directly)
        self.open_file_button.pack(side=tk.LEFT, padx=(0, 5), fill=tk.X, expand=True)
        self.open_dir_button = ttk.Button(file_buttons_frame, command=self.open_output_directory_explorer)
        self.open_dir_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def update_ui_text(self):
        self.root.title(lang_manager.get("app_title"))
        try:
            setting_cascade_index = self.menubar.index("_PLACEHOLDER_SETTING_MENU_")
            self.menubar.entryconfig(setting_cascade_index, label=lang_manager.get("menu_setting"))
        except tk.TclError as e:
            file_logger.error(f"Error finding/configuring setting menu cascade: {e}")
        self.setting_menu.entryconfig(0, label=lang_manager.get("menu_configure_openai"))
        self.setting_menu.entryconfig(1, label=lang_manager.get("menu_view_config_file"))
        self.setting_menu.entryconfig(2, label=lang_manager.get("menu_view_log_file"))
        self.setting_menu.entryconfig(4, label=lang_manager.get("menu_exit"))
        try:
            language_cascade_index = self.menubar.index("_PLACEHOLDER_LANGUAGE_MENU_")
            self.menubar.entryconfig(language_cascade_index, label=lang_manager.get("menu_language"))
        except tk.TclError as e:
            file_logger.error(f"Error finding/configuring language menu cascade: {e}")
        self.language_menu.entryconfig(0, label=lang_manager.get("lang_en"))
        self.language_menu.entryconfig(1, label=lang_manager.get("lang_zh"))

        self.config_frame_lframe.config(text=lang_manager.get("frame_general_config"))
        self.output_dir_label.config(text=lang_manager.get("label_output_directory"))
        self.choose_dir_button.config(text=lang_manager.get("button_choose_dir"))

        self.browser_frame_lframe.config(text=lang_manager.get("frame_browser_settings"))
        self.custom_chrome_radio.config(text=lang_manager.get("radio_custom_chrome_path"))
        self.browse_exe_button.config(text=lang_manager.get("button_browse_exe"))
        self.playwright_radio.config(text=lang_manager.get("radio_playwright_bundled"))
        self.disable_security_checkbox.config(text=lang_manager.get("checkbox_browser_disable_security"))
        self.keep_alive_checkbox.config(text=lang_manager.get("checkbox_browser_keep_alive"))
        self.user_data_dir_label.config(text=lang_manager.get("label_browser_user_data_dir"))
        self.browse_user_data_dir_button.config(text=lang_manager.get("button_browse_dir"))

        self.task_frame_lframe.config(text=lang_manager.get("frame_task_input"))
        self.optimize_prompt_button.config(text=lang_manager.get("button_optimize_prompt"))
        self.load_template_button.config(text=lang_manager.get("button_load_template"))
        self.save_template_button.config(text=lang_manager.get("button_save_template"))
        self.set_default_button.config(text=lang_manager.get("button_set_default_task"))
        self.run_button.config(text=lang_manager.get("button_run_agent"))
        self.stop_button.config(text=lang_manager.get("button_stop_agent"))
        self.force_exit_button.config(text=lang_manager.get("button_force_exit"))

        self.log_frame_lframe.config(text=lang_manager.get("frame_operation_log"))
        self.files_frame_lframe.config(text=lang_manager.get("frame_saved_files"))
        self.open_file_button.config(text=lang_manager.get("button_open_selected_file"))
        self.open_dir_button.config(text=lang_manager.get("button_open_output_dir"))

    def _threaded_optimize_prompt(self, original_prompt: str):
        try:
            file_logger.info(f"Threaded prompt optimization started for: '{original_prompt[:50]}...'")
            model_to_use = OPENAI_MODEL_NAME_EFFECTIVE
            full_system_prompt = SYSTEM_PROMPT_OPTIMIZE_TASK
            api_key = OPENAI_API_KEY_EFFECTIVE
            base_url = OPENAI_BASE_URL_EFFECTIVE
            os.environ["OPENAI_API_KEY"] = api_key
            os.environ["OPENAI_BASE_URL"] = base_url
            optimized_prompt = openAITool.call_gpt_api(user_content=original_prompt, model=model_to_use,
                                                       system_prompt=full_system_prompt)
            gui_feedback_queue.put({
                "type": "prompt_optimization_result",
                "status": "success",
                "optimized_prompt": optimized_prompt.strip()
            })
            file_logger.info(f"Prompt optimization successful. Result: '{optimized_prompt[:100]}...'")
        except Exception as e:
            tb_str = traceback.format_exc()
            file_logger.error(f"Error during prompt optimization: {e}\n{tb_str}")
            gui_feedback_queue.put({
                "type": "prompt_optimization_result",
                "status": "error",
                "error_message": str(e)
            })

    def optimize_task_prompt(self):
        current_prompt = self.task_text.get("1.0", tk.END).strip()
        if not current_prompt:
            messagebox.showwarning(lang_manager.get("message_warning_title"),
                                   lang_manager.get("warning_prompt_empty_no_optimize"), parent=self.root)
            return

        self.optimize_prompt_button.config(state='disabled')
        self.log_message_to_gui("gui_log_optimizing_prompt", level="IMPORTANT_GUI")  # Will be blue & bold
        self.root.update_idletasks()

        threading.Thread(target=self._threaded_optimize_prompt, args=(current_prompt,), daemon=True).start()

    def show_openai_config_dialog(self):
        dialog = OpenAIConfigDialog(self.root)
        self.root.wait_window(dialog)

    def view_log_file(self):
        log_path = os.path.abspath(LOG_FILENAME)
        if not os.path.exists(log_path):
            messagebox.showinfo(lang_manager.get("message_info_title"),
                                lang_manager.get("log_file_not_found_message", filename=LOG_FILENAME),
                                parent=self.root)
            file_logger.info(f"Attempted to view log file, but '{log_path}' does not exist.")
            return
        try:
            file_logger.info(f"Opening log file: {log_path}")
            if platform.system() == "Windows":
                os.startfile(log_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", log_path])
            else:
                subprocess.Popen(["xdg-open", log_path])
        except Exception as e:
            messagebox.showerror(lang_manager.get("message_error_title"),
                                 lang_manager.get("error_could_not_open_log_file", log_path=log_path, error=e),
                                 parent=self.root)
            file_logger.error(f"Failed to open log file '{log_path}': {e}")

    def view_config_file(self):
        config_path = os.path.abspath(CONFIG_FILE_NAME)
        if not os.path.exists(config_path):
            messagebox.showinfo(lang_manager.get("message_info_title"),
                                lang_manager.get("config_file_not_found", filename=CONFIG_FILE_NAME),
                                parent=self.root)
            file_logger.warning(f"Attempted to view config file, but '{config_path}' does not exist.")
            return
        try:
            file_logger.info(f"Opening configuration file: {config_path}")
            if platform.system() == "Windows":
                os.startfile(config_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", config_path])
            else:
                subprocess.Popen(["xdg-open", config_path])
        except Exception as e:
            messagebox.showerror(lang_manager.get("message_error_title"),
                                 lang_manager.get("error_opening_config_file", config_file=config_path, error=e),
                                 parent=self.root)
            file_logger.error(f"Failed to open configuration file '{config_path}': {e}")

    def force_exit_app(self):
        if messagebox.askyesno(
                title=lang_manager.get("confirm_force_exit_title"),
                message=lang_manager.get("confirm_force_exit_message"),
                parent=self.root
        ):
            file_logger.warning("--- User initiated FORCE EXIT. Application will terminate immediately. ---")
            self.log_message_to_gui("gui_log_force_exit_initiated", level="WARNING_GUI")  # Orange
            self.root.destroy()
            sys.exit(0)
        else:
            file_logger.info("User cancelled force exit.")
            self.log_message_to_gui("gui_log_force_exit_cancelled", level="INFO_GUI")  # Black

    def on_browser_choice_changed(self):
        self.update_browser_path_state()
        self.check_and_prompt_for_restart()

    def check_and_prompt_for_restart(self):
        current_choice = self.browser_choice_var.get()
        previous_choice = self.previous_browser_choice.get()

        if current_choice == previous_choice:
            return

        is_significant_change = (current_choice == "custom" and previous_choice == "playwright_bundled") or \
                                (current_choice == "playwright_bundled" and previous_choice == "custom")

        if is_significant_change:
            file_logger.info(
                f"Significant browser choice change: from '{previous_choice}' to '{current_choice}'. Prompting for restart.")
            if messagebox.askyesno(
                    title=lang_manager.get("restart_required_title"),
                    message=lang_manager.get("restart_required_message_browser_change"),
                    parent=self.root
            ):
                self.previous_browser_choice.set(current_choice)
                if self.save_app_settings_to_config(force_save_browser_choice=True):
                    self.perform_restart()
                else:
                    file_logger.error(
                        "Config save failed during restart preparation. Restart aborted. Reverting UI choice.")
                    messagebox.showerror(
                        title=lang_manager.get("error_saving_browser_choice_for_restart_title"),
                        message=lang_manager.get("error_saving_browser_choice_for_restart_message",
                                                 config_file=config_manager.config_file_path,
                                                 error="[Save failed, see app.log]"),
                        parent=self.root
                    )
                    self.browser_choice_var.set(previous_choice)
                    self.previous_browser_choice.set(previous_choice)
                    self.update_browser_path_state()
            else:
                file_logger.info("User cancelled restart. Reverting browser choice UI.")
                self.browser_choice_var.set(previous_choice)
                self.update_browser_path_state()
                messagebox.showinfo(
                    title=lang_manager.get("change_cancelled_title"),
                    message=lang_manager.get("browser_change_reverted_message"),
                    parent=self.root
                )
        else:
            self.previous_browser_choice.set(current_choice)
            file_logger.debug(
                f"Browser choice changed from '{previous_choice}' to '{current_choice}', but not deemed significant for restart, or already handled. Previous choice updated.")

    def perform_restart(self):
        file_logger.info("--- Application restart sequence initiated by user for browser setting change. ---")

        if self.agent_thread and self.agent_thread.is_alive():
            self.log_message_to_gui("gui_log_restart_requested_stopping_agent", level="IMPORTANT_GUI")  # Blue & bold
            file_logger.warning("GUI: Restart requested while agent running. Signaling agent stop.")
            self.stop_event.set()
        try:
            self.root.destroy()
        except tk.TclError:
            file_logger.warning("TclError during root.destroy() before restart, possibly already destroyed.")
        except Exception as e_destroy:
            file_logger.error(f"Exception during root.destroy() before restart: {e_destroy}")

        python_executable = sys.executable
        script_args = sys.argv
        file_logger.info(f"Executing: {python_executable} {' '.join(script_args)}")
        try:
            os.execv(python_executable, [python_executable] + script_args)
        except Exception as e_exec:
            file_logger.critical(f"FATAL: os.execv failed during restart: {e_exec}")
            temp_root_for_error = tk.Tk()
            temp_root_for_error.withdraw()
            messagebox.showerror("Restart Failed",
                                 f"Could not automatically restart the application: {e_exec}. Please close and restart manually.",
                                 parent=temp_root_for_error)
            temp_root_for_error.destroy()
            sys.exit(1)

    def change_language(self):
        new_lang = self.language_var.get()
        if new_lang != lang_manager.current_lang_code:
            lang_manager.set_language(new_lang)
            self.update_ui_text()
            file_logger.info(f"GUI: Language changed to {new_lang}. Preference will be saved on exit/restart.")

    def log_message_to_gui(self, message_key_or_direct_msg, level="INFO_GUI", **kwargs):
        if lang_manager.strings.get(message_key_or_direct_msg):
            message = lang_manager.get(message_key_or_direct_msg, **kwargs)
        else:
            message = str(message_key_or_direct_msg)
            if kwargs:
                try:
                    message = message.format(**kwargs)
                except Exception:  # pylint: disable=bare-except
                    pass

        display_message = f"{datetime.now().strftime('%H:%M:%S')} - {message}"

        tag_to_apply = None
        level_config = self.LOG_LEVEL_CONFIG.get(level.upper())
        if level_config:
            tag_to_apply = level_config["tag"]
        else:  # Fallback for unknown levels
            tag_to_apply = self.LOG_LEVEL_CONFIG["INFO_GUI"]["tag"]

        self.log_text.configure(state='normal')
        # Example: If you wanted to style only parts, you'd split here
        # self.log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - ", ("timestamp",))
        # self.log_text.insert(tk.END, message + "\n", (tag_to_apply,))
        if tag_to_apply:
            self.log_text.insert(tk.END, display_message + "\n", (tag_to_apply,))
        else:  # Should not happen with fallback, but as a safeguard
            self.log_text.insert(tk.END, display_message + "\n")
        self.log_text.configure(state='disabled')
        self.log_text.see(tk.END)

    def add_saved_file_to_list(self, file_path):
        abs_file_path = os.path.abspath(file_path)
        if abs_file_path not in self.saved_files_data:
            self.saved_files_data.append(abs_file_path)
            self.files_listbox.insert(tk.END, os.path.basename(abs_file_path))
            file_logger.debug(f"GUI: Added to saved files list: {abs_file_path}")

    def choose_output_dir(self):
        directory = filedialog.askdirectory(initialdir=self.output_dir_var.get(),
                                            title=lang_manager.get("choose_output_dir_title"))
        if directory:
            abs_dir = os.path.abspath(directory)
            self.output_dir_var.set(abs_dir)
            file_logger.info(f"GUI: Output directory changed to: {abs_dir}")

    def choose_chrome_path(self):
        initial_dir_guess = os.path.dirname(self.chrome_path_var.get()) if self.chrome_path_var.get() else ""
        if not os.path.isdir(initial_dir_guess):
            if platform.system() == "Windows":
                initial_dir_guess = "C:/Program Files/Google/Chrome/Application"
            elif platform.system() == "Darwin":
                initial_dir_guess = "/Applications/Google Chrome.app/Contents/MacOS"
            else:
                initial_dir_guess = os.path.expanduser("~")

        exe_desc = lang_manager.get("filetype_exe_files");
        app_desc = lang_manager.get("filetype_applications");
        all_desc = lang_manager.get("filetype_all_files")

        if platform.system() == "Windows":
            filetypes = ((exe_desc, "*.exe"), (all_desc, "*.*"))
        elif platform.system() == "Darwin":
            filetypes = ((app_desc, "*.app"), (all_desc, "*.*"))
        else:
            filetypes = ((all_desc, "*.*"),)

        filepath = filedialog.askopenfilename(title=lang_manager.get("choose_chrome_exe_title"),
                                              initialdir=initial_dir_guess, filetypes=filetypes)
        if filepath:
            processed_path = os.path.abspath(filepath)
            if platform.system() == "Darwin" and processed_path.endswith(".app"):
                app_name = os.path.basename(processed_path).replace(".app", "")
                potential_exec = os.path.join(processed_path, "Contents/MacOS", app_name)
                if os.path.isfile(potential_exec) and os.access(potential_exec, os.X_OK):
                    processed_path = potential_exec
                    file_logger.info(f"GUI: Resolved .app bundle to executable: {processed_path}")
                else:
                    macos_dir = os.path.join(processed_path, "Contents/MacOS")
                    if os.path.isdir(macos_dir):
                        execs = [f for f in os.listdir(macos_dir) if
                                 not f.startswith('.') and os.access(os.path.join(macos_dir, f), os.X_OK)]
                        if execs:
                            processed_path = os.path.join(macos_dir, execs[0])
                            file_logger.info(
                                f"GUI: Resolved .app bundle to first executable in MacOS dir: {processed_path}")
                        else:
                            file_logger.warning(
                                f"GUI: Could not find executable in .app bundle's Contents/MacOS: {macos_dir}")
                    else:
                        file_logger.warning(
                            f"GUI: Selected .app bundle does not have a Contents/MacOS directory: {processed_path}")

            self.chrome_path_var.set(processed_path)
            file_logger.info(f"GUI: Chrome path changed to: {processed_path}")

            if self.browser_choice_var.get() != "custom":
                self.browser_choice_var.set("custom")
                self.on_browser_choice_changed()
            else:
                self.update_browser_path_state()
                self.previous_browser_choice.set("custom")

    def choose_browser_user_data_dir(self):
        current_path = self.browser_user_data_dir_var.get()
        initial_dir_candidate = os.path.abspath(current_path) if current_path else os.getcwd()

        directory = filedialog.askdirectory(
            initialdir=initial_dir_candidate if os.path.isdir(initial_dir_candidate) else os.getcwd(),
            title=lang_manager.get("choose_browser_user_data_dir_title")
        )
        if directory:
            abs_dir = os.path.abspath(directory)
            self.browser_user_data_dir_var.set(abs_dir)
            file_logger.info(f"GUI: Browser user data directory changed to: {abs_dir}")

    def update_browser_path_state(self):
        if self.browser_choice_var.get() == "custom":
            self.chrome_path_entry.config(state='normal')
            self.browse_exe_button.config(state='normal')
        else:
            self.chrome_path_entry.config(state='disabled')
            self.browse_exe_button.config(state='disabled')
        file_logger.debug(f"GUI: Browser path state updated for choice: {self.browser_choice_var.get()}")

    def open_output_directory_explorer(self):
        output_dir = self.output_dir_var.get()
        if not output_dir or not os.path.isdir(output_dir):
            output_dir_abs = os.path.abspath(INITIAL_OUTPUT_DIR)
            if not os.path.isdir(output_dir_abs):
                try:
                    os.makedirs(output_dir_abs, exist_ok=True)
                    file_logger.info(f"Created fallback output directory: {output_dir_abs}")
                    output_dir = output_dir_abs
                except Exception as e_mkdir:
                    file_logger.error(
                        f"Failed to create fallback output directory {output_dir_abs}: {e_mkdir}. Using current working directory.")
                    output_dir = os.getcwd()
            else:
                output_dir = output_dir_abs
        else:
            output_dir = os.path.abspath(output_dir)

        file_logger.info(f"GUI: Opening output directory in explorer: {output_dir}")
        try:
            if platform.system() == "Windows":
                os.startfile(output_dir)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", output_dir])
            else:
                subprocess.Popen(["xdg-open", output_dir])
        except Exception as e:
            messagebox.showerror(lang_manager.get("message_error_title"),
                                 lang_manager.get("error_could_not_open_dir", dirpath=output_dir, error=e),
                                 parent=self.root)
            file_logger.error(f"Failed to open directory '{output_dir}' in explorer: {e}")

    def open_selected_file_directly(self, event=None):
        selected_indices = self.files_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo(lang_manager.get("message_info_title"), lang_manager.get("error_no_file_selected"),
                                parent=self.root)
            return
        selected_index = selected_indices[0]

        if 0 <= selected_index < len(self.saved_files_data):
            file_path_to_open = self.saved_files_data[selected_index]
        else:
            messagebox.showerror(lang_manager.get("message_error_title"),
                                 lang_manager.get("error_file_index_out_of_range"), parent=self.root)
            file_logger.error(
                "GUI: Error opening file directly - index out of range. Listbox selections may be desynced from data.")
            return

        if os.path.exists(file_path_to_open):
            file_logger.info(f"GUI: Attempting to open file directly: {file_path_to_open}")
            try:
                if platform.system() == "Windows":
                    os.startfile(file_path_to_open)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", file_path_to_open])
                else:
                    subprocess.Popen(["xdg-open", file_path_to_open])
            except Exception as e:
                messagebox.showerror(lang_manager.get("message_error_title"),
                                     lang_manager.get("error_could_not_open_file", filepath=file_path_to_open, error=e),
                                     parent=self.root)
                file_logger.error(f"Failed to open file '{file_path_to_open}' directly: {e}")
        else:
            messagebox.showerror(lang_manager.get("message_error_title"),
                                 lang_manager.get("error_file_not_found_at_path", filepath=file_path_to_open),
                                 parent=self.root)
            file_logger.warning(
                f"GUI: File not found when trying to open directly (path was '{file_path_to_open}'). It might have been moved or deleted.")

    def load_task_template(self):
        txt_desc = lang_manager.get("filetype_text_files");
        all_desc = lang_manager.get("filetype_all_files")
        filepath = filedialog.askopenfilename(title=lang_manager.get("load_task_template_title"),
                                              initialdir=os.path.abspath(TASK_TEMPLATE_DIR),
                                              filetypes=((txt_desc, "*.txt"), (all_desc, "*.*")), parent=self.root)
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8-sig') as f:  # Corrected from 'utf-f8-sig'
                    content = f.read()
                self.task_text.delete("1.0", tk.END);
                self.task_text.insert("1.0", content)
                self.log_message_to_gui("gui_log_template_loaded", filename=os.path.basename(filepath),
                                        level="INFO_GUI")
                file_logger.info(f"GUI: Task template loaded from '{filepath}'.")
            except Exception as e:
                messagebox.showerror(lang_manager.get("message_error_title"),
                                     lang_manager.get("error_load_task_template", error=e), parent=self.root)
                file_logger.error(f"GUI: Error loading task template from '{filepath}': {e}")

    def save_task_template(self):
        current_task_content = self.task_text.get("1.0", tk.END).strip()
        if not current_task_content:
            messagebox.showwarning(lang_manager.get("message_warning_title"),
                                   lang_manager.get("warning_task_empty_no_save"), parent=self.root);
            return
        txt_desc = lang_manager.get("filetype_text_files");
        all_desc = lang_manager.get("filetype_all_files")
        filepath = filedialog.asksaveasfilename(title=lang_manager.get("save_task_template_title"),
                                                initialdir=os.path.abspath(TASK_TEMPLATE_DIR), defaultextension=".txt",
                                                filetypes=((txt_desc, "*.txt"), (all_desc, "*.*")), parent=self.root)
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(current_task_content)
                self.log_message_to_gui("gui_log_template_saved", filename=os.path.basename(filepath), level="INFO_GUI")
                file_logger.info(f"GUI: Task content saved as template to '{filepath}'.")
                messagebox.showinfo(lang_manager.get("message_success_title"),
                                    lang_manager.get("msgbox_template_saved_success",
                                                     filename=os.path.basename(filepath)), parent=self.root)
            except Exception as e:
                messagebox.showerror(lang_manager.get("message_error_title"),
                                     lang_manager.get("error_save_task_template", error=e), parent=self.root)
                file_logger.error(f"GUI: Error saving task template to '{filepath}': {e}")

    def set_current_task_as_default(self):
        global INITIAL_TASK_PROMPT
        current_task_content = self.task_text.get("1.0", tk.END).strip()
        if not current_task_content:
            messagebox.showwarning(lang_manager.get("message_warning_title"),
                                   lang_manager.get("warning_task_empty_no_default"), parent=self.root);
            return
        if not messagebox.askyesno(lang_manager.get("message_confirm_title"),
                                   lang_manager.get("confirm_set_default_task_message"), parent=self.root): return

        try:
            config_manager.set_value('UI_DEFAULTS', 'TASK_PROMPT', current_task_content)
            if config_manager.save():
                INITIAL_TASK_PROMPT = current_task_content
                msg_success_key = "msgbox_default_task_set_success"
                self.log_message_to_gui(msg_success_key, level="INFO_GUI")
                file_logger.info(
                    f"GUI: Default task prompt updated in '{config_manager.config_file_path}'. New default (first 70 chars): '{current_task_content[:70].replace(os.linesep, ' ')}...'")
                messagebox.showinfo(lang_manager.get("message_success_title"), lang_manager.get(msg_success_key),
                                    parent=self.root)
            else:
                msg_error = lang_manager.get("error_save_default_task_config",
                                             config_file=config_manager.config_file_path, error="Save failed, see log")
                messagebox.showerror(lang_manager.get("message_error_title"), msg_error, parent=self.root);
                file_logger.error(f"GUI: {msg_error}")
        except Exception as e:
            msg_error = lang_manager.get("error_unexpected_set_default_task", error=e)
            messagebox.showerror(lang_manager.get("message_error_title"), msg_error, parent=self.root);
            file_logger.error(f"GUI: {msg_error}\n{traceback.format_exc()}")

    def save_app_settings_to_config(self, force_save_browser_choice=False):
        file_logger.info(f"Attempting to save application settings to '{config_manager.config_file_path}'.")
        try:
            config_manager.set_value('PATHS', 'CHROME_BINARY_PATH', self.chrome_path_var.get())
            config_manager.set_value('PATHS', 'OUTPUT_DIR', self.output_dir_var.get())
            config_manager.set_value('UI_DEFAULTS', 'LANGUAGE', lang_manager.current_lang_code)

            config_manager.set_value('BROWSER_ADVANCED_SETTINGS', 'BROWSER_CHOICE', self.browser_choice_var.get())
            config_manager.set_value('BROWSER_ADVANCED_SETTINGS', 'DISABLE_SECURITY',
                                     str(self.browser_disable_security_var.get()))
            config_manager.set_value('BROWSER_ADVANCED_SETTINGS', 'KEEP_ALIVE', str(self.browser_keep_alive_var.get()))
            config_manager.set_value('BROWSER_ADVANCED_SETTINGS', 'USER_DATA_DIR', self.browser_user_data_dir_var.get())

            if force_save_browser_choice:
                file_logger.info(f"BROWSER_CHOICE '{self.browser_choice_var.get()}' explicitly marked for saving.")

            if config_manager.save():
                file_logger.info(f"Application settings successfully saved to '{config_manager.config_file_path}'.")
                return True
            else:
                return False
        except Exception as e:
            file_logger.error(
                f"Error saving application settings to '{config_manager.config_file_path}': {e}\n{traceback.format_exc()}")
            return False

    def start_agent_task(self):
        task = self.task_text.get("1.0", tk.END).strip()
        if not task:
            messagebox.showerror(lang_manager.get("message_error_title"), lang_manager.get("error_task_input_empty"),
                                 parent=self.root)
            file_logger.warning("GUI: Start task aborted - task input empty.");
            return

        file_logger.info(f"--- GUI: Start Agent Task initiated. Task (first 100): '{task[:100]}...' ---")
        self.stop_event.clear()
        self.run_button.config(state='disabled');
        self.stop_button.config(state='normal')
        self.force_exit_button.config(state='normal')
        self.optimize_prompt_button.config(state='disabled')
        self.log_text.configure(state='normal');
        self.log_text.delete('1.0', tk.END);
        self.log_text.configure(state='disabled')
        self.files_listbox.delete(0, tk.END);
        self.saved_files_data.clear()
        self.log_message_to_gui("agent_task_initializing_log", level="INFO_GUI")  # Black

        current_api_key = OPENAI_API_KEY_EFFECTIVE
        current_base_url = OPENAI_BASE_URL_EFFECTIVE
        current_default_model = OPENAI_MODEL_NAME_EFFECTIVE
        current_output_dir = self.output_dir_var.get()

        current_browser_disable_security = self.browser_disable_security_var.get()
        current_browser_keep_alive = self.browser_keep_alive_var.get()
        current_browser_user_data_dir = self.browser_user_data_dir_var.get()

        file_logger.info(
            f"Task Runtime Config from GUI: DefaultModel='{current_default_model}', "
            f"API_Key_Set={'Yes' if current_api_key and current_api_key != DEFAULT_OPENAI_API_KEY else 'No/Default'}, "
            f"BaseURL='{current_base_url}', OutputDir='{current_output_dir}', "
            f"BrowserChoiceRaw='{self.browser_choice_var.get()}', CustomChromePath='{self.chrome_path_var.get()}', "
            f"DisableSecurity='{current_browser_disable_security}', KeepAlive='{current_browser_keep_alive}', UserDataDir='{current_browser_user_data_dir}'"
        )

        current_chrome_path = None
        browser_choice_raw = self.browser_choice_var.get()
        browser_choice_for_log = lang_manager.get("radio_unknown_browser_choice")
        file_logger.info(f"GUI - Start_Agent_Task: Raw browser_choice_var from UI: '{browser_choice_raw}'")
        file_logger.info(f"GUI - Start_Agent_Task: Raw chrome_path_var from UI: '{self.chrome_path_var.get()}'")

        if browser_choice_raw == "custom":
            current_chrome_path_val_from_ui = self.chrome_path_var.get()
            browser_choice_for_log = f"{lang_manager.get('radio_custom_chrome_path')}: {current_chrome_path_val_from_ui if current_chrome_path_val_from_ui else lang_manager.get('path_not_set')}"

            if not current_chrome_path_val_from_ui or not current_chrome_path_val_from_ui.strip():
                file_logger.warning(
                    f"GUI Action: 'custom' browser selected, but Chrome path is empty or whitespace ('{current_chrome_path_val_from_ui}'). The agent will likely fall back to bundled browser.")
                current_chrome_path = current_chrome_path_val_from_ui
                self.log_message_to_gui(lang_manager.get("warning_custom_browser_no_path_selected"),
                                        level="WARNING_GUI")  # Orange
            elif not os.path.isfile(current_chrome_path_val_from_ui):
                file_logger.error(
                    f"GUI Action: 'custom' browser selected, but path '{current_chrome_path_val_from_ui}' is not a valid file. Agent might fail or fallback.")
                current_chrome_path = current_chrome_path_val_from_ui
                self.log_message_to_gui(
                    lang_manager.get("error_custom_chrome_path_not_file", path=current_chrome_path_val_from_ui),
                    level="ERROR_GUI")  # Red & bold
            else:
                current_chrome_path = current_chrome_path_val_from_ui
                file_logger.info(f"GUI Action: 'custom' browser selected with valid path: '{current_chrome_path}'")

        elif browser_choice_raw == "playwright_bundled":
            browser_choice_for_log = lang_manager.get("radio_playwright_bundled")

        try:
            os.makedirs(current_output_dir, exist_ok=True)
        except Exception as e:
            err_msg = lang_manager.get("error_create_output_dir", path=current_output_dir, error=e)
            messagebox.showerror(lang_manager.get("message_error_title"), err_msg, parent=self.root)
            file_logger.error(f"GUI Validation Error: {err_msg}")
            self.run_button.config(state='normal');
            self.stop_button.config(state='disabled');
            self.force_exit_button.config(state='normal')
            self.optimize_prompt_button.config(state='normal')
            return

        if current_browser_user_data_dir:
            try:
                os.makedirs(os.path.abspath(current_browser_user_data_dir), exist_ok=True)
            except Exception as e_mkdir_gui_udd:
                self.log_message_to_gui(
                    lang_manager.get("warning_gui_could_not_ensure_udd", user_data_dir=current_browser_user_data_dir,
                                     error=e_mkdir_gui_udd),
                    level="WARNING_GUI")  # Orange
                file_logger.warning(
                    f"GUI: Could not ensure user data directory '{current_browser_user_data_dir}': {e_mkdir_gui_udd}")

        self.agent_thread = threading.Thread(
            target=self.run_async_task_in_thread,
            args=(task, current_api_key, current_base_url, current_default_model,
                  current_chrome_path,
                  current_output_dir, self.stop_event,
                  current_browser_disable_security,
                  current_browser_keep_alive,
                  current_browser_user_data_dir,
                  browser_choice_for_log,
                  browser_choice_raw),
            daemon=True
        )
        self.agent_thread.start()

    def request_stop_agent_task(self):
        if self.agent_thread and self.agent_thread.is_alive():
            self.log_message_to_gui("gui_log_agent_stop_requested", level="WARNING_GUI")  # Orange
            file_logger.warning("GUI: User requested agent stop.")
            self.stop_event.set()
            self.stop_button.config(state='disabled')
        else:
            is_running = self.agent_thread and self.agent_thread.is_alive()
            if not is_running and self.stop_button['state'] == 'normal':
                self.log_message_to_gui("gui_log_agent_stop_ignored_not_running", level="INFO_GUI")  # Black
                file_logger.info(f"GUI: Stop request ignored as agent is not running. Resetting button states.")
                self.run_button.config(state='normal')
                self.stop_button.config(state='disabled')
                self.force_exit_button.config(state='normal')
                self.optimize_prompt_button.config(state='normal')
            elif not is_running:
                self.log_message_to_gui("gui_log_agent_already_stopped", level="INFO_GUI")  # Black
                file_logger.info(f"GUI: Agent is not currently running or already stopped.")
                self.force_exit_button.config(state='normal')
                self.optimize_prompt_button.config(state='normal')  # Re-enable here too

    def on_closing(self):
        file_logger.info("--- GUI: Application closing sequence initiated. ---")
        if self.agent_thread and self.agent_thread.is_alive():
            if messagebox.askokcancel(lang_manager.get("message_quit_title"),
                                      lang_manager.get("confirm_quit_agent_running_message"),
                                      parent=self.root):
                self.log_message_to_gui("gui_log_quit_requested_stopping_agent", level="IMPORTANT_GUI")  # Blue & bold
                file_logger.warning("GUI: Quit confirmed by user while agent running. Signaling agent stop.")
                self.stop_event.set()
                file_logger.info("GUI: Proceeding with destroy after signaling stop to running agent.")
                self.root.destroy()
            else:
                file_logger.info("GUI: Quit cancelled by user; application remains open.")
                return
        else:
            self.save_app_settings_to_config(force_save_browser_choice=False)
            self.root.destroy()

    def run_async_task_in_thread(self, task, api_key, base_url, model, chrome_path, output_dir, stop_event_ref,
                                 browser_disable_security_param,
                                 browser_keep_alive_param,
                                 browser_user_data_dir_param,
                                 browser_choice_log_info_param,
                                 browser_choice_raw_param):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        file_logger.info(f"Async task thread started for task (first 50): '{task[:50]}...'")
        try:
            loop.run_until_complete(
                run_agent_async(task, api_key, base_url, model, chrome_path, output_dir, stop_event_ref,
                                browser_disable_security=browser_disable_security_param,
                                browser_keep_alive=browser_keep_alive_param,
                                browser_user_data_dir=browser_user_data_dir_param,
                                use_vision_param=False,
                                browser_choice_info=browser_choice_log_info_param,
                                actual_browser_choice=browser_choice_raw_param))
        except Exception as e:
            tb_str = traceback.format_exc()
            critical_msg_summary = lang_manager.get("critical_thread_error_summary", error_type=type(e).__name__,
                                                    error_msg=str(e)[:100])
            gui_feedback_queue.put({"type": "log", "message": critical_msg_summary, "level": "ERROR_GUI", "kwargs": {}})
            file_logger.critical(f"CRITICAL ERROR in run_async_task_in_thread's run_until_complete: {e}\n{tb_str}")
            gui_feedback_queue.put({"type": "task_complete", "stopped_by_user": stop_event_ref.is_set(), "error": True})
        finally:
            try:
                all_async_tasks = asyncio.all_tasks(loop)
                pending = [t for t in all_async_tasks if not t.done()]
                if pending:
                    file_logger.debug(f"Async thread: Cancelling {len(pending)} pending asyncio tasks.")
                    for t_item in pending: t_item.cancel()
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(asyncio.sleep(0.1))
                gc.collect()
            except RuntimeError as e_runtime:
                file_logger.error(f"Async thread: Runtime error during task cleanup in event loop: {e_runtime}")
            except Exception as eloop_clean:
                file_logger.error(f"Async thread: Exception during task cleanup in event loop: {eloop_clean}")
            finally:
                if not loop.is_closed():
                    loop.close()
                    file_logger.info(f"Async task thread event loop closed.")
                else:
                    file_logger.info(f"Async task thread event loop was already closed.")

    def process_gui_queue(self):
        try:
            while True:
                message_item = gui_feedback_queue.get_nowait()
                msg_type = message_item.get("type")
                msg_content_key_or_direct = message_item.get("message", "")
                msg_level = message_item.get("level", "INFO_GUI").upper()  # Ensure uppercase for dict lookup
                msg_kwargs = message_item.get("kwargs", {})

                processed_message = ""
                if lang_manager.strings.get(str(msg_content_key_or_direct)):
                    processed_message = lang_manager.get(str(msg_content_key_or_direct), **msg_kwargs)
                else:
                    processed_message = str(msg_content_key_or_direct)
                    if msg_kwargs:
                        try:
                            processed_message = processed_message.format(**msg_kwargs)
                        except (KeyError, IndexError, TypeError, ValueError):
                            file_logger.warning(
                                f"GUI Queue: Failed to format direct message '{msg_content_key_or_direct}' with kwargs {msg_kwargs}. Using raw message.")
                            pass

                log_prefix_queue = f"Q->GUI ({msg_level})"
                # Standard file logging (no color here, just severity)
                if "ERROR" in msg_level:
                    file_logger.error(f"{log_prefix_queue}: {processed_message}")
                elif "WARNING" in msg_level:
                    file_logger.warning(f"{log_prefix_queue}: {processed_message}")
                elif msg_type == "log" or msg_type == "prompt_optimization_result":  # Log other relevant types too
                    file_logger.info(f"{log_prefix_queue}: {processed_message}")

                if msg_type == "log":
                    # Let log_message_to_gui handle the display with its defined levels
                    self.log_message_to_gui(processed_message, level=msg_level)
                elif msg_type == "file_saved":
                    self.add_saved_file_to_list(message_item["path"])
                elif msg_type == "prompt_optimization_result":
                    self.optimize_prompt_button.config(state='normal')
                    if message_item["status"] == "success":
                        optimized_prompt = message_item["optimized_prompt"]
                        self.task_text.delete("1.0", tk.END)
                        self.task_text.insert("1.0", optimized_prompt)
                        self.log_message_to_gui("gui_log_prompt_optimized_success", level="INFO_GUI")  # Black
                        messagebox.showinfo(lang_manager.get("message_success_title"),
                                            lang_manager.get("gui_log_prompt_optimized_success"), parent=self.root)
                    else:
                        error_msg = message_item["error_message"]
                        self.log_message_to_gui("gui_log_prompt_optimization_failed", error=error_msg,
                                                level="ERROR_GUI")  # Red & bold
                        messagebox.showerror(lang_manager.get("message_error_title"),
                                             lang_manager.get("gui_log_prompt_optimization_failed", error=error_msg),
                                             parent=self.root)
                elif msg_type == "task_complete":
                    self.run_button.config(state='normal')
                    self.stop_button.config(state='disabled')
                    self.force_exit_button.config(state='normal')
                    self.optimize_prompt_button.config(state='normal')

                    stopped_by_user = message_item.get("stopped_by_user", False)
                    had_critical_error = message_item.get("error", False)

                    title_key = "message_info_title"
                    completion_msg_key_gui = "msgbox_agent_task_complete"
                    log_level_for_gui_msg = "INFO_GUI"  # Black for success message by default

                    if had_critical_error:
                        title_key = "message_error_title"
                        completion_msg_key_gui = "msgbox_agent_task_critical_error"
                        log_level_for_gui_msg = "ERROR_GUI"  # Red & bold for error
                        messagebox.showerror(lang_manager.get(title_key), lang_manager.get(completion_msg_key_gui),
                                             parent=self.root)
                    elif stopped_by_user:
                        title_key = "message_warning_title"
                        completion_msg_key_gui = "msgbox_agent_task_stopped_by_user"
                        log_level_for_gui_msg = "WARNING_GUI"  # Orange for stopped by user
                        messagebox.showwarning(lang_manager.get(title_key), lang_manager.get(completion_msg_key_gui),
                                               parent=self.root)
                    else:  # Successful completion without user stop
                        log_level_for_gui_msg = "IMPORTANT_GUI"  # Blue & bold for success
                        messagebox.showinfo(lang_manager.get(title_key), lang_manager.get(completion_msg_key_gui),
                                            parent=self.root)

                    self.log_message_to_gui(lang_manager.get(completion_msg_key_gui), level=log_level_for_gui_msg)
                    file_logger.info(
                        f"GUI: Task complete signal processed. Final status perceived by GUI (keys): had_error={had_critical_error}, stopped_by_user={stopped_by_user} -> {lang_manager.get(completion_msg_key_gui)}")

        except queue.Empty:
            pass
        except Exception as e_queue:
            error_msg = f"Error in process_gui_queue: {type(e_queue).__name__} - {e_queue}"
            # Attempt to log to GUI with error styling if log_message_to_gui is still working
            try:
                self.log_message_to_gui(error_msg, level="ERROR_GUI")
            except Exception:  # If GUI logging itself is broken, just pass
                pass
            file_logger.critical(f"{error_msg}\n{traceback.format_exc()}")
            try:
                if self.run_button and self.run_button.winfo_exists(): self.run_button.config(state='normal')
                if self.stop_button and self.stop_button.winfo_exists(): self.stop_button.config(state='disabled')
                if self.optimize_prompt_button and self.optimize_prompt_button.winfo_exists(): self.optimize_prompt_button.config(
                    state='normal')
            except Exception as e_reset:
                file_logger.error(f"Failed to reset buttons during GUI queue error handling: {e_reset}")
        finally:
            if self.root.winfo_exists():
                self.root.after(100, self.process_gui_queue)


if __name__ == "__main__":
    file_logger.info("==================== Application Starting ====================")
    os.makedirs(TASK_TEMPLATE_DIR, exist_ok=True)
    file_logger.info(f"Task template directory ensured: {os.path.abspath(TASK_TEMPLATE_DIR)}")
    os.makedirs(LOCALES_DIR, exist_ok=True)
    file_logger.info(f"Locales directory ensured: {os.path.abspath(LOCALES_DIR)}")

    try:
        abs_default_udd = os.path.abspath(DEFAULT_BROWSER_USER_DATA_DIR)
        os.makedirs(abs_default_udd, exist_ok=True)
        file_logger.info(f"Default browser user data directory base ensured: {abs_default_udd}")
    except Exception as e_mkdir_udd:
        file_logger.error(
            f"Could not create default browser user data directory base '{DEFAULT_BROWSER_USER_DATA_DIR}': {e_mkdir_udd}")

    file_logger.info(f"Configured User Type: {USER_TYPE}")
    file_logger.info(f"Configured Enterprise Network Check Host: {ENTERPRISE_NETWORK_CHECK_HOST}")
    file_logger.info(
        f"Initial language from config: {INITIAL_LANGUAGE}, Current Manager Lang: {lang_manager.current_lang_code}")

    perform_exit = False
    if USER_TYPE.lower() == "enterprise":
        file_logger.info("User type is Enterprise. Performing network check.")
        if not can_access_internal_service(ENTERPRISE_NETWORK_CHECK_HOST, ENTERPRISE_NETWORK_CHECK_PORT):
            file_logger.warning(
                "Enterprise user detected, but not on the enterprise network (or host not configured/resolvable).")
            temp_root_for_mb = tk.Tk();
            temp_root_for_mb.withdraw()
            messagebox.showwarning(lang_manager.get("network_access_warning_title"),
                                   lang_manager.get("network_access_warning_message"), parent=temp_root_for_mb)
            temp_root_for_mb.destroy();
            perform_exit = True
        else:
            file_logger.info("Enterprise user detected and on the enterprise network. Proceeding.")
    else:
        file_logger.info("User type is Personal or not specified as Enterprise. Skipping enterprise network check.")

    if perform_exit:
        file_logger.info("Exiting application due to enterprise network check failure or user cancellation.")
        sys.exit(1)

    status_default_loc = lang_manager.get("status_default")
    status_yes_custom_loc = lang_manager.get("status_yes_custom")
    status_not_set_loc = lang_manager.get("status_not_set")

    console_output = [
        f"Initial Effective Config - OpenAI Default Model: {OPENAI_MODEL_NAME_EFFECTIVE}",
        f"Initial Effective Config - OpenAI OCR Image Model: {OCR_IMAGE_MODEL_EFFECTIVE}",
        f"Initial Effective Config - OpenAI OCR PDF Model: {OCR_PDF_MODEL_EFFECTIVE}",
        f"Initial Config - Chrome Binary Path (UI Default from config/default): '{INITIAL_CHROME_BINARY_PATH if INITIAL_CHROME_BINARY_PATH else status_not_set_loc}'",
        f"Initial Config - Output Directory (UI Default from config/default): {os.path.abspath(INITIAL_OUTPUT_DIR)}",
        f"Initial Effective Config - OpenAI API Key Loaded: {status_yes_custom_loc if OPENAI_API_KEY_EFFECTIVE and OPENAI_API_KEY_EFFECTIVE != DEFAULT_OPENAI_API_KEY else status_default_loc}",
        f"Initial Effective Config - OpenAI Base URL: {OPENAI_BASE_URL_EFFECTIVE if OPENAI_BASE_URL_EFFECTIVE else status_default_loc}",
        f"Initial Config - Task Prompt (first 70 chars): {INITIAL_TASK_PROMPT[:70].replace(os.linesep, ' ')}...",
        f"Initial Config - UI Language: {lang_manager.current_lang_code}",
        f"Initial Config - Browser Choice (startup default): {INITIAL_BROWSER_CHOICE}",
        f"Initial Config - Browser Disable Security: {INITIAL_BROWSER_DISABLE_SECURITY}",
        f"Initial Config - Browser Keep Alive: {INITIAL_BROWSER_KEEP_ALIVE}",
        f"Initial Config - Browser User Data Dir: '{INITIAL_BROWSER_USER_DATA_DIR if INITIAL_BROWSER_USER_DATA_DIR else status_not_set_loc}' (Abs: {os.path.abspath(INITIAL_BROWSER_USER_DATA_DIR) if INITIAL_BROWSER_USER_DATA_DIR else 'N/A'})",
        f"Config File Path: {os.path.abspath(config_manager.config_file_path)}"
    ]
    print("-" * 30 + " Initial Configuration " + "-" * 30)
    for line in console_output:
        print(line)
        if "API Key Loaded" not in line:
            file_logger.info(line)
    file_logger.info(
        f"Initial Effective Config - OpenAI API Key Loaded: {status_yes_custom_loc if OPENAI_API_KEY_EFFECTIVE and OPENAI_API_KEY_EFFECTIVE != DEFAULT_OPENAI_API_KEY else status_default_loc}")

    print("-" * (60 + len(" Initial Configuration ")))

    main_root = tk.Tk()
    app = AgentApp(main_root)
    try:
        main_root.mainloop()
    except KeyboardInterrupt:
        file_logger.info("Application terminated by KeyboardInterrupt.")
        print("\nApplication terminated by user.")
    finally:
        if app and hasattr(app, 'root') and app.root.winfo_exists():
            file_logger.info("Mainloop exited, attempting final settings save if not already handled by on_closing.")
            app.save_app_settings_to_config(force_save_browser_choice=False)

        logging.shutdown()
        file_logger.info("==================== Application Exited ====================")
        for handler in list(file_logger.handlers):
            if isinstance(handler, logging.FileHandler):
                try:
                    handler.close()
                except Exception as e_close:
                    print(f"Error closing file handler during final shutdown: {e_close}", file=sys.stderr)