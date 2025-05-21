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
        self._ensure_default_config_file_exists()  # Creates file with defaults if not exists_
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

    def _load_config_from_file(self):
        try:
            if os.path.exists(self.config_file_path):
                self.config.read(self.config_file_path, encoding='utf-8')
            else:
                self.logger.warning(
                    f"Config file '{self.config_file_path}' does not exist at read time, though it should have been created. Using empty config.")
                self.config = configparser.ConfigParser()
        except configparser.Error as e:
            self.logger.error(
                f"Error reading config file '{self.config_file_path}': {e}. App will use defaults or previously loaded values if available.")

    # 方案一：全局将空字符串视为使用默认值
    # def get_value(self, section_name, key_name, default_value, is_bool=False):
    #     try:
    #         if self.config.has_option(section_name, key_name):
    #             value_str = self.config.get(section_name, key_name)

    #             # 如果值为空字符串，则使用默认值
    #             if not value_str.strip() and not is_bool: # 对于布尔值，空字符串可能不是我们想要的判断方式
    #                 self.logger.warning(
    #                     f"Key '{key_name}' in section '{section_name}' is empty. Using default: '{default_value}'.")
    #                 return default_value

    #             if is_bool:
    #                 return value_str.strip().lower() == 'true'

    #             if section_name == 'UI_DEFAULTS' and key_name == 'TASK_PROMPT':
    #                 return value_str.replace('\\r\\n', '\n').replace('\\n', '\n')

    #             return value_str
    #         else:
    #             if not self.config.has_section(section_name):
    #                 self.logger.warning(
    #                     f"Section '{section_name}' not found in '{self.config_file_path}'. Using default for key '{key_name}': '{default_value}'.")
    #             else:
    #                 self.logger.warning(
    #                     f"Key '{key_name}' not found in section '{section_name}' of '{self.config_file_path}'. Using default: '{default_value}'.")
    #             return default_value
    #     except Exception as e:
    #         self.logger.error(
    #             f"Exception getting config value for '{section_name}/{key_name}': {e}\n{traceback.format_exc()}")
    #         return default_value

    # 方案二：为 get_value 添加一个参数来控制此行为 (推荐)
    def get_value(self, section_name, key_name, default_value, is_bool=False, treat_empty_as_default=False):
        try:
            if self.config.has_option(section_name, key_name):
                value_str = self.config.get(section_name, key_name)

                # 如果指定了 treat_empty_as_default 且值为空字符串 (去除首尾空格后)，则使用默认值
                if treat_empty_as_default and not value_str.strip():
                    self.logger.warning(
                        f"Key '{key_name}' in section '{section_name}' is empty and 'treat_empty_as_default' is True. Using default: '{str(default_value)[:50]}{'...' if len(str(default_value)) > 50 else ''}'.")
                    return default_value

                if is_bool:
                    # 对于布尔值，空字符串通常不等于 'true'，所以会是 False。
                    # 如果希望空字符串对于布尔值也回退到默认值，需要调整这里的逻辑或依赖 treat_empty_as_default
                    return value_str.strip().lower() == 'true'

                if section_name == 'UI_DEFAULTS' and key_name == 'TASK_PROMPT':
                    return value_str.replace('\\r\\n', '\n').replace('\\n', '\n')

                return value_str
            else: # 键不存在
                if not self.config.has_section(section_name):
                    self.logger.warning(
                        f"Section '{section_name}' not found in '{self.config_file_path}'. Using default for key '{key_name}': '{str(default_value)[:50]}{'...' if len(str(default_value)) > 50 else ''}'.")
                else:
                    self.logger.warning(
                        f"Key '{key_name}' not found in section '{section_name}' of '{self.config_file_path}'. Using default: '{str(default_value)[:50]}{'...' if len(str(default_value)) > 50 else ''}'.")
                return default_value
        except Exception as e:
            self.logger.error(
                f"Exception getting config value for '{section_name}/{key_name}': {e}\n{traceback.format_exc()}")
            return default_value

    def set_value(self, section_name, key_name, value):
        if not self.config.has_section(section_name):
            self.config.add_section(section_name)

        value_to_set = str(value)
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
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    test_logger = logging.getLogger("ConfigToolTest")

    test_config_file = "config.ini" # "test_config.ini"

    # 为了测试，确保 config.ini 的 API_KEY 是空的
    # 你可以手动修改 config.ini, 将 OPENAI API_KEY 设置为空，例如:
    # [OPENAI]
    # API_KEY =
    # BASE_URL = ...
    # ...

    cm = ConfigManager(config_file_path_override=test_config_file, logger_instance=test_logger)

    print("--- Testing API Key ---")
    # 使用方案二：
    api_key_from_config = cm.get_value('OPENAI', 'API_KEY', DEFAULT_OPENAI_API_KEY, treat_empty_as_default=True)
    print(f"API Key (treat_empty_as_default=True): '{api_key_from_config}'")
    print(f"Is it default? {api_key_from_config == DEFAULT_OPENAI_API_KEY}")

    # 测试不将空字符串视为默认值的情况 (如果 API_KEY 在文件里确实是空)
    # api_key_raw = cm.get_value('OPENAI', 'API_KEY', DEFAULT_OPENAI_API_KEY, treat_empty_as_default=False)
    # print(f"API Key (treat_empty_as_default=False): '{api_key_raw}'")

    print("\n--- Testing CHROME_BINARY_PATH (typically allows empty) ---")
    # 对于 CHROME_BINARY_PATH, 空字符串可能是有效值 (表示使用系统默认)
    # 所以我们不应该 treat_empty_as_default=True, 或者默认它就是 False
    chrome_path = cm.get_value('PATHS', 'CHROME_BINARY_PATH', DEFAULT_CHROME_BINARY_PATH)
    # 假设 config.ini 中 PATHS CHROME_BINARY_PATH =
    print(f"Chrome Binary Path (default treat_empty behavior): '{chrome_path}'") # 应该会是空 (来自文件)
    print(f"Is it default constant? {chrome_path == DEFAULT_CHROME_BINARY_PATH}") # 如果文件为空，而DEFAULT_CHROME_BINARY_PATH也为空，则为True

    chrome_path_force_default = cm.get_value('PATHS', 'CHROME_BINARY_PATH', "SHOULD_NOT_SEE_THIS_UNLESS_KEY_MISSING", treat_empty_as_default=True)
    # 如果 config.ini 中 PATHS CHROME_BINARY_PATH = "" 并且 DEFAULT_CHROME_BINARY_PATH = ""
    # 那么这里会是 DEFAULT_CHROME_BINARY_PATH (空字符串)
    # 如果 DEFAULT_CHROME_BINARY_PATH = "some_path", 则会返回 "some_path"
    print(f"Chrome Binary Path (treat_empty_as_default=True, assuming file has it empty): '{chrome_path_force_default}'")

    # 测试布尔值行为
    print("\n--- Testing Boolean with empty value in file (if KEEP_ALIVE = ) ---")
    # 假设 config.ini 有 BROWSER_ADVANCED_SETTINGS KEEP_ALIVE =
    # 1. is_bool=True, treat_empty_as_default=False (default)
    #    空字符串.lower() == 'true' -> False
    keep_alive_empty_no_treat = cm.get_value('BROWSER_ADVANCED_SETTINGS', 'KEEP_ALIVE', DEFAULT_BROWSER_KEEP_ALIVE, is_bool=True, treat_empty_as_default=False)
    print(f"Keep Alive (is_bool=True, empty in file, no treat_empty): {keep_alive_empty_no_treat} (Expected: False if file has empty KEEP_ALIVE=)")

    # 2. is_bool=True, treat_empty_as_default=True
    #    空字符串会触发 treat_empty_as_default, 返回 DEFAULT_BROWSER_KEEP_ALIVE
    keep_alive_empty_treat = cm.get_value('BROWSER_ADVANCED_SETTINGS', 'KEEP_ALIVE', DEFAULT_BROWSER_KEEP_ALIVE, is_bool=True, treat_empty_as_default=True)
    print(f"Keep Alive (is_bool=True, empty in file, treat_empty=True): {keep_alive_empty_treat} (Expected: {DEFAULT_BROWSER_KEEP_ALIVE})")

    # # 恢复之前的测试代码 (如果需要)
    # print(f"\nInitial API Key: '{cm.get_value('OPENAI', 'API_KEY', DEFAULT_OPENAI_API_KEY, treat_empty_as_default=True)}'")
    # cm.set_value('OPENAI', 'API_KEY', 'test_key_123')
    # print(f"Set API Key: '{cm.get_value('OPENAI', 'API_KEY', DEFAULT_OPENAI_API_KEY, treat_empty_as_default=True)}'")

    # print(
    #     f"Initial Keep Alive: {cm.get_value('BROWSER_ADVANCED_SETTINGS', 'KEEP_ALIVE', DEFAULT_BROWSER_KEEP_ALIVE, is_bool=True, treat_empty_as_default=True)}")
    # cm.set_value('BROWSER_ADVANCED_SETTINGS', 'KEEP_ALIVE', False)
    # print(
    #     f"Set Keep Alive (bool): {cm.get_value('BROWSER_ADVANCED_SETTINGS', 'KEEP_ALIVE', DEFAULT_BROWSER_KEEP_ALIVE, is_bool=True, treat_empty_as_default=True)}")

    # test_prompt_with_newlines = "Line 1\nLine 2 with CR\r\nLine 3"
    # cm.set_value('UI_DEFAULTS', 'TASK_PROMPT', test_prompt_with_newlines)
    # retrieved_prompt = cm.get_value('UI_DEFAULTS', 'TASK_PROMPT', DEFAULT_TASK_PROMPT)
    # print(f"Set Task Prompt: '{test_prompt_with_newlines}'")
    # print(f"Retrieved Task Prompt: '{retrieved_prompt}'")
    # print(f"Is prompt retrieved correctly? {retrieved_prompt == test_prompt_with_newlines}")

    # cm.save()
    # print(f"Config saved to {test_config_file}")

    # cm_load = ConfigManager(config_file_path_override=test_config_file, logger_instance=test_logger)
    # print(f"Loaded API Key: '{cm_load.get_value('OPENAI', 'API_KEY', DEFAULT_OPENAI_API_KEY, treat_empty_as_default=True)}'")
    # print(
    #     f"Loaded Keep Alive: {cm_load.get_value('BROWSER_ADVANCED_SETTINGS', 'KEEP_ALIVE', DEFAULT_BROWSER_KEEP_ALIVE, is_bool=True, treat_empty_as_default=True)}")
    # loaded_prompt = cm_load.get_value('UI_DEFAULTS', 'TASK_PROMPT', DEFAULT_TASK_PROMPT)
    # print(f"Loaded Task Prompt: '{loaded_prompt}'")
    # print(f"Is loaded prompt correct? {loaded_prompt == test_prompt_with_newlines}")

    # if os.path.exists(test_config_file):
    #     print(f"Test config file '{test_config_file}' left for inspection.")