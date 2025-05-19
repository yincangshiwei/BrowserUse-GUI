# -*- coding:utf-8 -*-
# @Time: 2025/5/15 0015 16:11
# @Author: cxd
# @File: localization.py
# @Remark:
# localization.py
import json
import os
import logging

# Use the main application's file logger if available, otherwise a local one.
# This assumes file_logger is globally accessible from main.py or configured early.
try:
    from main import file_logger # Try to import from main
except ImportError:
    # Fallback logger if main.file_logger is not available during standalone import
    # or if structure changes. For this setup, main.py will initialize it.
    file_logger = logging.getLogger('LocalizationManager')
    if not file_logger.hasHandlers(): # Basic setup if not configured
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        file_logger.addHandler(handler)
        file_logger.setLevel(logging.INFO)

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
                self.strings = {}
        except json.JSONDecodeError as e:
            file_logger.error(f"LanguageManager: Error decoding JSON from language file '{filepath}': {e}")
            if lang_code != self.fallback_lang:
                file_logger.warning(f"LanguageManager: JSON error. Falling back to language '{self.fallback_lang}'.")
                self.load_language(self.fallback_lang)
            else:
                file_logger.error(f"LanguageManager: Fallback language file '{self.fallback_lang}.json' also has JSON error. No strings available.")
                self.strings = {}
        except Exception as e:
            file_logger.error(f"LanguageManager: Unexpected error loading language file '{filepath}': {e}")
            if lang_code != self.fallback_lang:
                self.load_language(self.fallback_lang)
            else:
                self.strings = {}

    def set_language(self, lang_code):
        """Sets the current language and reloads strings. Updates config."""
        if lang_code != self.current_lang_code or not self.strings:
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