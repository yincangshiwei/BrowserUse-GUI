# ConfigTool.py
import configparser
import os
import logging
import traceback

# --- SHARED CONSTANTS ---
CONFIG_FILE_NAME = "config.ini"  # Name of the file

# --- DEFAULTS --- (These are the ultimate fallbacks used by ConfigManager)
DEFAULT_OPENAI_API_KEY = ""
DEFAULT_OPENAI_BASE_URL = ""
DEFAULT_OPENAI_MODEL_NAME = 'gpt-4.1-mini'
DEFAULT_OCR_IMAGE_MODEL_NAME = 'gpt-4-vision-preview'
DEFAULT_OCR_PDF_MODEL_NAME = 'gpt-4-vision-preview'

DEFAULT_CHROME_BINARY_PATH = ''
DEFAULT_OUTPUT_DIR = os.path.join("resources", "agent_outputs")  # Use os.path.join for path construction
DEFAULT_TASK_PROMPT = "打开百度 (https://www.baidu.com) 并搜索“今日天气”，然后将搜索结果页面的标题和URL保存到名为 'baidu_search_results.txt' 的文件中。"
DEFAULT_LANGUAGE = "en"

DEFAULT_BROWSER_CHOICE = "playwright_bundled"
DEFAULT_BROWSER_DISABLE_SECURITY = True
DEFAULT_BROWSER_KEEP_ALIVE = True
DEFAULT_BROWSER_USER_DATA_DIR = os.path.join("resources", "User Data")


class ConfigManager:
    def __init__(self, config_file_path_override=None, logger_instance=None):
        self.config_file_path = config_file_path_override or CONFIG_FILE_NAME
        self.logger = logger_instance
        if self.logger is None:
            # Fallback basic logger if none is provided (e.g., for standalone use/testing)
            self.logger = logging.getLogger("ConfigManagerDefaultLogger")
            if not self.logger.hasHandlers():  # Avoid adding multiple handlers if already configured
                self.logger.setLevel(logging.INFO)
                ch = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                ch.setFormatter(formatter)
                self.logger.addHandler(ch)
            self.logger.info("No external logger provided to ConfigManager, using internal fallback.")

        self.config = configparser.ConfigParser()
        self._ensure_default_config_file_exists()  # Creates file with defaults if not exists
        self._load_config_from_file()  # Reads existing file into self.config

    def _ensure_default_config_file_exists(self):
        if not os.path.exists(self.config_file_path):
            self.logger.warning(f"Configuration file '{self.config_file_path}' not found. Creating a default one.")
            default_config = configparser.ConfigParser()
            default_config['OPENAI'] = {
                'API_KEY': DEFAULT_OPENAI_API_KEY,
                'BASE_URL': DEFAULT_OPENAI_BASE_URL,
                'MODEL_NAME': DEFAULT_OPENAI_MODEL_NAME,
                'OCR_IMAGE_MODEL_NAME': DEFAULT_OCR_IMAGE_MODEL_NAME,
                'OCR_PDF_MODEL_NAME': DEFAULT_OCR_PDF_MODEL_NAME
            }
            default_config['PATHS'] = {
                'CHROME_BINARY_PATH': DEFAULT_CHROME_BINARY_PATH,
                'OUTPUT_DIR': DEFAULT_OUTPUT_DIR
            }
            # Escape newlines for storage in .ini for TASK_PROMPT
            escaped_default_task_prompt = DEFAULT_TASK_PROMPT.replace('\r\n', '\n').replace('\n', '\\n')
            default_config['UI_DEFAULTS'] = {
                'TASK_PROMPT': escaped_default_task_prompt,
                'LANGUAGE': DEFAULT_LANGUAGE
            }
            default_config['BROWSER_ADVANCED_SETTINGS'] = {
                'BROWSER_CHOICE': DEFAULT_BROWSER_CHOICE,
                'DISABLE_SECURITY': str(DEFAULT_BROWSER_DISABLE_SECURITY),
                'KEEP_ALIVE': str(DEFAULT_BROWSER_KEEP_ALIVE),
                'USER_DATA_DIR': DEFAULT_BROWSER_USER_DATA_DIR
            }
            try:
                # Ensure parent directory exists for config file if nested
                config_dir = os.path.dirname(self.config_file_path)
                if config_dir and not os.path.exists(config_dir):
                    os.makedirs(config_dir, exist_ok=True)

                with open(self.config_file_path, 'w', encoding='utf-8') as configfile:
                    default_config.write(configfile)
                self.logger.info(f"Default config file '{self.config_file_path}' created.")
            except IOError as e:
                self.logger.error(f"Failed to create default config file '{self.config_file_path}': {e}")
                # Optionally, print to console as logger might not be fully visible yet for critical startup.
                # print(f"ERROR: Failed to create default config file '{self.config_file_path}'. Please check permissions.")

    def _load_config_from_file(self):
        try:
            if os.path.exists(self.config_file_path):
                self.config.read(self.config_file_path, encoding='utf-8')
            else:
                # This case should be handled by _ensure_default_config_file_exists creating it,
                # but if it somehow failed to create, this prevents a read error on non-existent file.
                self.logger.warning(
                    f"Config file '{self.config_file_path}' does not exist at read time, though it should have been created. Using empty config.")
                self.config = configparser.ConfigParser()  # Start with a fresh, empty config if file really isn't there
        except configparser.Error as e:
            self.logger.error(
                f"Error reading config file '{self.config_file_path}': {e}. App will use defaults or previously loaded values if available.")
            # print(f"WARNING: Error reading config file '{self.config_file_path}'. Using defaults where applicable. Details in app.log.")

    def get_value(self, section_name, key_name, default_value, is_bool=False):
        try:
            if self.config.has_option(section_name, key_name):  # Use has_option for more precise check
                value_str = self.config.get(section_name, key_name)  # get always returns string

                if is_bool:
                    return value_str.strip().lower() == 'true'

                # Special handling for TASK_PROMPT to unescape newlines read from file
                if section_name == 'UI_DEFAULTS' and key_name == 'TASK_PROMPT':
                    return value_str.replace('\\r\\n', '\n').replace('\\n', '\n')

                return value_str
            else:
                # Log if specific option is missing, section might exist
                if not self.config.has_section(section_name):
                    self.logger.warning(
                        f"Section '{section_name}' not found in '{self.config_file_path}'. Using default for key '{key_name}'.")
                else:
                    self.logger.warning(
                        f"Key '{key_name}' not found in section '{section_name}' of '{self.config_file_path}'. Using default.")
                return default_value
        except Exception as e:  # Catch any other unexpected errors
            self.logger.error(
                f"Exception getting config value for '{section_name}/{key_name}': {e}\n{traceback.format_exc()}")
            return default_value

    def set_value(self, section_name, key_name, value):
        if not self.config.has_section(section_name):
            self.config.add_section(section_name)

        value_to_set = str(value)  # Default to string conversion
        # Special handling for TASK_PROMPT to escape newlines for saving
        if section_name == 'UI_DEFAULTS' and key_name == 'TASK_PROMPT' and isinstance(value, str):
            value_to_set = value.replace('\r\n', '\n').replace('\n', '\\n')

        self.config.set(section_name, key_name, value_to_set)
        self.logger.debug(
            f"Config manager: set [{section_name}][{key_name}] = {value_to_set[:100]}{'...' if len(value_to_set) > 100 else ''}")

    def save(self):
        try:
            with open(self.config_file_path, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)
            self.logger.info(f"Configuration successfully saved to '{self.config_file_path}'.")
            return True
        except IOError as e:
            self.logger.error(f"Failed to save configuration to '{self.config_file_path}': {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error saving configuration: {e}\n{traceback.format_exc()}")
            return False


if __name__ == '__main__':
    # Example Usage (for testing ConfigTool.py directly)
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    test_logger = logging.getLogger("ConfigToolTest")

    # Create a temporary config file for testing
    test_config_file = "test_config.ini"
    if os.path.exists(test_config_file):
        os.remove(test_config_file)

    cm = ConfigManager(config_file_path_override=test_config_file, logger_instance=test_logger)

    print(f"Initial API Key: '{cm.get_value('OPENAI', 'API_KEY', DEFAULT_OPENAI_API_KEY)}'")
    cm.set_value('OPENAI', 'API_KEY', 'test_key_123')
    print(f"Set API Key: '{cm.get_value('OPENAI', 'API_KEY', DEFAULT_OPENAI_API_KEY)}'")

    print(
        f"Initial Keep Alive: {cm.get_value('BROWSER_ADVANCED_SETTINGS', 'KEEP_ALIVE', DEFAULT_BROWSER_KEEP_ALIVE, is_bool=True)}")
    cm.set_value('BROWSER_ADVANCED_SETTINGS', 'KEEP_ALIVE', False)  # Will be stored as 'False'
    print(
        f"Set Keep Alive (bool): {cm.get_value('BROWSER_ADVANCED_SETTINGS', 'KEEP_ALIVE', DEFAULT_BROWSER_KEEP_ALIVE, is_bool=True)}")

    test_prompt_with_newlines = "Line 1\nLine 2 with CR\r\nLine 3"
    cm.set_value('UI_DEFAULTS', 'TASK_PROMPT', test_prompt_with_newlines)
    retrieved_prompt = cm.get_value('UI_DEFAULTS', 'TASK_PROMPT', DEFAULT_TASK_PROMPT)
    print(f"Set Task Prompt: '{test_prompt_with_newlines}'")
    print(f"Retrieved Task Prompt: '{retrieved_prompt}'")
    print(f"Is prompt retrieved correctly? {retrieved_prompt == test_prompt_with_newlines}")

    cm.save()
    print(f"Config saved to {test_config_file}")

    # Test loading from existing file
    cm_load = ConfigManager(config_file_path_override=test_config_file, logger_instance=test_logger)
    print(f"Loaded API Key: '{cm_load.get_value('OPENAI', 'API_KEY', DEFAULT_OPENAI_API_KEY)}'")
    print(
        f"Loaded Keep Alive: {cm_load.get_value('BROWSER_ADVANCED_SETTINGS', 'KEEP_ALIVE', DEFAULT_BROWSER_KEEP_ALIVE, is_bool=True)}")
    loaded_prompt = cm_load.get_value('UI_DEFAULTS', 'TASK_PROMPT', DEFAULT_TASK_PROMPT)
    print(f"Loaded Task Prompt: '{loaded_prompt}'")
    print(f"Is loaded prompt correct? {loaded_prompt == test_prompt_with_newlines}")

    if os.path.exists(test_config_file):
        pass  # os.remove(test_config_file) # Keep it for inspection
        print(f"Test config file '{test_config_file}' left for inspection.")