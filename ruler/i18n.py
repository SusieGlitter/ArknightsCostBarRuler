import json
import logging
import os
import locale
import sys
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class I18n:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(I18n, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.locale_dir = os.path.join(os.path.dirname(__file__), 'locales')
        self.current_locale: str = 'zh_CN'
        self.translations: Dict[str, str] = {}
        self._initialized = True
        logger.info("I18n module initialized.")

    def load_locale(self, locale_code: str):
        """加载指定的语言文件"""
        self.current_locale = locale_code
        file_path = os.path.join(self.locale_dir, f"{locale_code}.json")
        
        logger.info(f"Loading locale file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.translations = json.load(f)
            logger.info(f"Locale '{locale_code}' loaded successfully.")
        except FileNotFoundError:
            logger.error(f"Locale file not found: {file_path}. Falling back to empty translations.")
            self.translations = {}
        except json.JSONDecodeError:
            logger.error(f"Locale file is invalid JSON: {file_path}. Falling back to empty translations.")
            self.translations = {}
        except Exception as e:
            logger.exception(f"Error loading locale '{locale_code}': {e}")
            self.translations = {}

    def get(self, key: str, default: Optional[str] = None, **kwargs) -> str:
        """
        获取翻译字符串。
        :param key: 键名
        :param default: 默认值（如果为None，则返回key）
        :param kwargs: 格式化参数
        :return: 翻译后的字符串
        """
        val = self.translations.get(key, default if default is not None else key)
        if kwargs:
            try:
                return val.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Missing format key '{e}' in translation for '{key}': {val}")
                return val
        return val

    def auto_detect_language(self):
        """尝试自动检测系统语言"""
        try:
            sys_lang, _ = locale.getdefaultlocale()
            logger.info(f"Detected system language: {sys_lang}")
            if sys_lang and sys_lang.startswith('en'):
                return 'en_US'
            elif sys_lang and (sys_lang.startswith('zh') or sys_lang == 'Chinese'):
                 # Covers zh_CN, zh_TW, zh_HK, etc. defaulting to zh_CN for now as we only have that.
                return 'zh_CN'
        except Exception:
            pass
        return 'zh_CN' # Default fallback

i18n = I18n()
