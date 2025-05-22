# -*- coding:utf-8 -*-
# @Time: 2025/5/15 0015 16:11
# @Author: cxd
# @File: localization.py
# @Remark:
# localization.py
import json
import os
import logging
from init import LOG_FILENAME

# Use the main application's file logger if available, otherwise a local one.
# This assumes file_logger is globally accessible from main.py or configured early.
try:
    from main import file_logger # Try to import from main
except ImportError:
    # Fallback logger if main.file_logger is not available during standalone import
    # or if structure changes. For this setup, main.py will initialize it.

    # --- File Logger Setup ---
    file_logger = logging.getLogger('LocalizationManager')
    file_logger.setLevel(logging.INFO)
    file_logger.propagate = False

    if not file_logger.hasHandlers():
        fh = logging.FileHandler(LOG_FILENAME, encoding='utf-8', mode='a')
        fh.setLevel(logging.INFO)
        stream_handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter)
        stream_handler.setFormatter(formatter)
        file_logger.addHandler(fh)
        file_logger.addHandler(stream_handler)

class LanguageManager:
    def __init__(self, locales_dir="resources/locales", initial_lang="en", fallback_lang="en"):
        self.locales_dir = locales_dir
        os.makedirs(self.locales_dir, exist_ok=True) # Ensure directory exists
        self.fallback_lang = fallback_lang
        self.current_lang_code = initial_lang
        self.strings = {}
        self.load_language(self.current_lang_code)

    def load_language(self, lang_code):
        self.strings = {}  # Clear previous language
        filepath = os.path.join(self.locales_dir, f"{lang_code}.json")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.strings = json.load(f)
            file_logger.info(f"LanguageManager: Loaded language '{lang_code}' from '{filepath}'")
            self.current_lang_code = lang_code  # Update current_lang_code only on successful load
        except FileNotFoundError:
            file_logger.error(f"LanguageManager: Language file not found: '{filepath}'.")
            if lang_code != self.fallback_lang:
                file_logger.warning(f"LanguageManager: Falling back to language '{self.fallback_lang}'.")
                self.load_language(self.fallback_lang)
            else:
                file_logger.error(f"LanguageManager: Fallback language file '{self.fallback_lang}.json' also not found. No strings will be available.")
                self.strings = {} # Ensure strings is empty
        except json.JSONDecodeError as e:
            file_logger.error(f"LanguageManager: Error decoding JSON from language file '{filepath}': {e}")
            if lang_code != self.fallback_lang:
                file_logger.warning(f"LanguageManager: JSON error. Falling back to language '{self.fallback_lang}'.")
                self.load_language(self.fallback_lang)
            else:
                file_logger.error(f"LanguageManager: Fallback language file '{self.fallback_lang}.json' also has JSON error. No strings available.")
                self.strings = {} # Ensure strings is empty
        except Exception as e:
            file_logger.error(f"LanguageManager: Unexpected error loading language file '{filepath}': {e}")
            if lang_code != self.fallback_lang:
                self.load_language(self.fallback_lang)
            else:
                self.strings = {} # Ensure strings is empty

    def set_language(self, lang_code):
        """Sets the current language and reloads strings. Updates config."""
        if lang_code != self.current_lang_code or not self.strings: # Also reload if strings dict is empty for some reason
            self.load_language(lang_code)
        # Note: Saving to config should ideally be handled by the main app
        # after a successful language switch confirmation.

    def get(self, key, *args, **kwargs):
        """
        Retrieves a string by key for the current language.
        Allows for string formatting using .format().
        Example: lang_manager.get("welcome_message", name="User")
                 where en.json has "welcome_message": "Welcome, {name}!"
        If key is not found, returns the key itself.
        """
        # Ensure strings is populated, e.g. if initial load failed and fallback also failed.
        if not self.strings and self.current_lang_code != self.fallback_lang:
             file_logger.warning(f"LanguageManager: Strings for '{self.current_lang_code}' are not loaded. Attempting to load fallback '{self.fallback_lang}'.")
             self.load_language(self.fallback_lang) # Attempt to load fallback if current strings missing
        elif not self.strings and self.current_lang_code == self.fallback_lang:
             file_logger.error(f"LanguageManager: Strings for fallback language '{self.fallback_lang}' also not loaded. Key '{key}' will not be found.")

        template = self.strings.get(key)
        if template is None:
            file_logger.warning(f"LanguageManager: Localization key '{key}' not found for language '{self.current_lang_code}'. Returning key itself.")
            return key # Return the key if not found

        if args or kwargs:
            try:
                return template.format(*args, **kwargs)
            except KeyError as e_fmt: # Handles missing placeholders in format string
                file_logger.error(f"LanguageManager: Formatting error for key '{key}' (lang: {self.current_lang_code}). Missing placeholder: {e_fmt}. Template: '{template}'. Args: {args}, Kwargs: {kwargs}")
                return template # Return unformatted template on error
            except Exception as e:
                file_logger.error(f"LanguageManager: Error formatting string for key '{key}' (lang: {self.current_lang_code}): {e}. Template: '{template}'. Args: {args}, Kwargs: {kwargs}")
                return template # Fallback to unformatted template on other formatting errors
        return template

    def get_available_languages(self, display_name_key="language_display_name"):
        """
        Scans the locales directory for language files and returns a dictionary
        of available languages.
        The dictionary format is { "lang_code": "Language Display Name", ... }.
        Args:
            display_name_key (str): The key to look for in each JSON language file
                                     to get the human-readable language name.
        Returns:
            dict: A dictionary of language codes to display names.
        """
        available_languages = {}
        if not os.path.isdir(self.locales_dir):
            file_logger.error(f"LanguageManager: Locales directory '{self.locales_dir}' not found. Cannot list available languages.")
            return available_languages

        try:
            for filename in os.listdir(self.locales_dir):
                if filename.endswith(".json"):
                    lang_code = filename[:-5] # Remove .json extension
                    filepath = os.path.join(self.locales_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        # Use the specified key for display name, fallback to lang_code if not found
                        display_name = data.get(display_name_key, lang_code.capitalize())
                        available_languages[lang_code] = display_name
                    except json.JSONDecodeError:
                        file_logger.warning(f"LanguageManager: Could not decode JSON from '{filepath}' while scanning for available languages. Skipping.")
                        available_languages[lang_code] = lang_code.capitalize() + " (Error Reading Name)" # Indicate an issue
                    except FileNotFoundError: # Should not happen if os.listdir worked, but good practice
                        file_logger.warning(f"LanguageManager: File '{filepath}' disappeared while scanning. Skipping.")
                    except Exception as e_scan:
                        file_logger.warning(f"LanguageManager: Unexpected error reading '{filepath}' for language name: {e_scan}. Using code as name.")
                        available_languages[lang_code] = lang_code.capitalize() + " (Scan Error)"

        except Exception as e_listdir:
            file_logger.error(f"LanguageManager: Could not list files in locales directory '{self.locales_dir}': {e_listdir}")

        if not available_languages:
            file_logger.warning("LanguageManager: No language files found or readable in locales directory. Defaulting to current/fallback if set.")
            # Provide at least the current and fallback if they are known, even if files not scanned properly
            if self.current_lang_code:
                 available_languages[self.current_lang_code] = self.strings.get(display_name_key, self.current_lang_code.capitalize()) if self.strings else self.current_lang_code.capitalize()
            if self.fallback_lang and self.fallback_lang not in available_languages:
                 available_languages[self.fallback_lang] = self.fallback_lang.capitalize()

        file_logger.info(f"LanguageManager: Discovered available languages: {available_languages}")
        return available_languages

if __name__ == '__main__':
    lang_manager = LanguageManager(locales_dir="resources/locales", initial_lang="en", fallback_lang="en")
    print(lang_manager.get("app_title"))