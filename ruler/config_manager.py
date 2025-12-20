import json
import logging
from tkinter import filedialog

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from typing import Dict, Any, Optional

from i18n import i18n

logger = logging.getLogger(__name__)

CONFIG_FILE = "../config.json"


def load_config() -> Optional[Dict[str, Any]]:
    """加载配置文件"""
    logger.info(f"尝试从 '{CONFIG_FILE}' 加载配置...")
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            if config:
                logger.info("配置加载成功。")
                logger.debug(f"加载的配置内容: {config}")
                
                # Load language preference
                lang = config.get('language')
                if lang:
                     i18n.load_locale(lang)
                else:
                     i18n.load_locale(i18n.auto_detect_language())

                return config
            logger.warning(f"配置文件 '{CONFIG_FILE}' 为空。")
            return None
    except FileNotFoundError:
        logger.info(f"配置文件 '{CONFIG_FILE}' 未找到。")
        return None
    except json.JSONDecodeError:
        logger.error(f"配置文件 '{CONFIG_FILE}' 格式损坏。")
        return None
    except Exception as e:
        logger.exception(f"加载配置文件时发生未知错误: {e}")
        return None


def save_config(config: Dict[str, Any]):
    """保存配置文件"""
    logger.info(f"正在保存配置到 '{CONFIG_FILE}'...")
    logger.debug(f"待保存的配置内容: {config}")
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        logger.info("配置保存成功。")
    except Exception as e:
        logger.exception(f"保存配置文件时发生错误: {e}")


class ConfigWindow(ttk.Toplevel):
    """
    一个使用 ttkbootstrap 风格的对话框窗口，用于引导用户完成首次配置。
    """

    def __init__(self, parent):
        super().__init__(parent)
        logger.debug("初始化首次配置向导窗口 (ConfigWindow)...")

        self.config_data = None
        self.FONT_NORMAL = ("Microsoft YaHei UI", 10)
        self.title(i18n.get("config.window.title"))
        self.grab_set()  # 模态窗口

        # --- 核心修改：使用字典管理模拟器选项 ---
        self.EMULATOR_OPTIONS = {
            "MuMu模拟器12": "mumu",
            "雷电模拟器": "ldplayer",
            "其他 (通用ADB)": "minicap"
        }
        self.selected_display_name = ttk.StringVar(master=self)

        main_frame = ttk.Frame(self, padding="15 15 15 15")
        main_frame.pack(expand=True, fill="both")

        self._create_widgets(main_frame)
        self._on_selection_change()  # 初始化显示正确的设置
        self.update_idletasks()
        self.center_on_screen()

        self.resizable(False, False)
        logger.debug("ConfigWindow 初始化完成。")

    def center_on_screen(self):
        """将窗口置于屏幕中央。"""
        logger.debug("正在将配置窗口居中...")
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        logger.debug(f"窗口位置设置为: {x}, {y}")

    def _create_widgets(self, parent: ttk.Frame):
        logger.debug("正在创建 ConfigWindow 的控件...")
        parent.columnconfigure(0, weight=1)

        # Language Selection
        lang_frame = ttk.Frame(parent)
        lang_frame.grid(row=0, column=0, pady=(0, 10), sticky="ew")
        
        lang_label = ttk.Label(lang_frame, text=i18n.get("config.language"), font=self.FONT_NORMAL)
        lang_label.pack(side="left", padx=(0, 10))

        self.language_var = ttk.StringVar(value=i18n.current_locale)
        self.language_combo = ttk.Combobox(lang_frame, textvariable=self.language_var, 
                                           values=["zh_CN", "en_US"], state="readonly", width=10)
        self.language_combo.pack(side="left")
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_change)

        self.header_label = ttk.Label(parent, text=i18n.get("config.header"), font=("Microsoft YaHei UI", 14, "bold"))
        self.header_label.grid(row=1, column=0, pady=(0, 20), sticky="w")

        # --- 核心修改：使用下拉框代替单选按钮 ---
        self.type_frame = ttk.Labelframe(parent, text=i18n.get("config.emulator_type"))
        self.type_frame.grid(row=2, column=0, sticky="ew", pady=10)
        self.type_frame.columnconfigure(0, weight=1)

        self.emulator_combobox = ttk.Combobox(
            self.type_frame,
            textvariable=self.selected_display_name,
            values=list(self.EMULATOR_OPTIONS.keys()),
            state="readonly"
        )
        self.emulator_combobox.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.emulator_combobox.set(list(self.EMULATOR_OPTIONS.keys())[0])  # 默认选中第一个
        self.emulator_combobox.bind("<<ComboboxSelected>>", self._on_selection_change)
        # --- 修改结束 ---

        self.options_container = ttk.Frame(parent)
        self.options_container.grid(row=3, column=0, sticky="ew", pady=5)
        self.options_container.columnconfigure(0, weight=1)

        # 创建所有可能的设置框架
        self.mumu_frame = self._create_mumu_frame(self.options_container)
        self.mumu_frame.grid(row=0, column=0, sticky="nsew")

        self.ldplayer_frame = self._create_ldplayer_frame(self.options_container)
        self.ldplayer_frame.grid(row=0, column=0, sticky="nsew")

        self.minicap_frame = self._create_minicap_frame(self.options_container)
        self.minicap_frame.grid(row=0, column=0, sticky="nsew")

        self.save_button = ttk.Button(parent, text=i18n.get("config.btn.save_start"), command=self._save_and_close, bootstyle="success")
        self.save_button.grid(row=4, column=0, pady=(20, 0), ipady=5, sticky="ew")
        logger.debug("控件创建完成。")

    def _create_mumu_frame(self, parent) -> ttk.Frame:
        frame = ttk.Labelframe(parent, text=i18n.get("config.mumu.frame.title"))
        frame.columnconfigure(1, weight=1)

        self.mumu_path_label = ttk.Label(frame, text=i18n.get("config.label.path"), font=self.FONT_NORMAL)
        self.mumu_path_label.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")
        self.mumu_path_entry = ttk.Entry(frame, font=self.FONT_NORMAL)
        self.mumu_path_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        self.mumu_browse_btn = ttk.Button(frame, text=i18n.get("config.btn.browse"), command=self._browse_mumu_path, bootstyle="secondary-outline")
        self.mumu_browse_btn.grid(row=0, column=2, padx=(5, 10), pady=10, sticky="e")

        self.mumu_instance_label = ttk.Label(frame, text=i18n.get("config.label.instance"), font=self.FONT_NORMAL)
        self.mumu_instance_label.grid(row=1, column=0, padx=(10, 5), pady=(0, 10), sticky="w")
        self.mumu_instance_entry = ttk.Entry(frame, font=self.FONT_NORMAL)
        self.mumu_instance_entry.grid(row=1, column=1, padx=5, pady=(0, 10), sticky="ew", columnspan=2)
        self.mumu_instance_entry.insert(0, "0")
        return frame

    def _create_ldplayer_frame(self, parent) -> ttk.Frame:
        frame = ttk.Labelframe(parent, text=i18n.get("config.ldplayer.frame.title"))
        frame.columnconfigure(1, weight=1)

        self.ld_path_label = ttk.Label(frame, text=i18n.get("config.label.path"), font=self.FONT_NORMAL)
        self.ld_path_label.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")
        self.ldplayer_path_entry = ttk.Entry(frame, font=self.FONT_NORMAL)
        self.ldplayer_path_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        self.ld_browse_btn = ttk.Button(frame, text=i18n.get("config.btn.browse"), command=self._browse_ldplayer_path,
                                   bootstyle="secondary-outline")
        self.ld_browse_btn.grid(row=0, column=2, padx=(5, 10), pady=10, sticky="e")

        self.ld_instance_label = ttk.Label(frame, text=i18n.get("config.label.instance"), font=self.FONT_NORMAL)
        self.ld_instance_label.grid(row=1, column=0, padx=(10, 5), pady=10, sticky="w")
        self.ldplayer_instance_entry = ttk.Entry(frame, font=self.FONT_NORMAL)
        self.ldplayer_instance_entry.grid(row=1, column=1, padx=5, pady=10, sticky="ew", columnspan=2)
        self.ldplayer_instance_entry.insert(0, "0")

        self.ld_adb_label = ttk.Label(frame, text=i18n.get("config.label.adb_id_optional"), font=self.FONT_NORMAL)
        self.ld_adb_label.grid(row=2, column=0, padx=(10, 5), pady=(0, 10), sticky="w")
        self.ldplayer_id_entry = ttk.Entry(frame, font=self.FONT_NORMAL)
        self.ldplayer_id_entry.grid(row=2, column=1, padx=5, pady=(0, 10), sticky="ew", columnspan=2)
        return frame

    def _create_minicap_frame(self, parent) -> ttk.Frame:
        frame = ttk.Labelframe(parent, text=i18n.get("config.minicap.frame.title"))
        frame.columnconfigure(0, weight=1)
        self.minicap_adb_label = ttk.Label(frame, text=i18n.get("config.label.adb_id_auto"), font=self.FONT_NORMAL)
        self.minicap_adb_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        self.minicap_id_entry = ttk.Entry(frame, font=self.FONT_NORMAL)
        self.minicap_id_entry.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        return frame

    def _on_language_change(self, event=None):
        """Handle language change"""
        new_lang = self.language_var.get()
        logger.info(f"Language changed to {new_lang}")
        i18n.load_locale(new_lang)
        self._refresh_ui_text()
        
    def _refresh_ui_text(self):
        """Update strings in the UI when language changes"""
        self.title(i18n.get("config.window.title"))
        self.header_label.config(text=i18n.get("config.header"))
        
        # Emulator types
        # Note: We need to update keys to map to values in localized EMULATOR_OPTIONS or just update the dropdown values
        # Since logic relies on the display name to map back to key (mumu, etc), we must be careful.
        # Ideally, we should separate display name from logic key.
        # For now, let's just update the static texts and leave the combobox items alone or rebuild them.
        # But wait, self.EMULATOR_OPTIONS keys are display names! This is bad design in original code but I must work with it.
        # To fix this properly, I'd need to change how EMULATOR_OPTIONS works.
        # Let's try to update display names.
        
        # Re-populate EMULATOR_OPTIONS with translated keys? No, ConfigWindow is short lived.
        # Let's just update labels first.
        
        self.type_frame.config(text=i18n.get("config.emulator_type"))
        self.save_button.config(text=i18n.get("config.btn.save_start"))
        
        self.mumu_frame.config(text=i18n.get("config.mumu.frame.title"))
        self.mumu_path_label.config(text=i18n.get("config.label.path"))
        self.mumu_browse_btn.config(text=i18n.get("config.btn.browse"))
        self.mumu_instance_label.config(text=i18n.get("config.label.instance"))
        
        self.ldplayer_frame.config(text=i18n.get("config.ldplayer.frame.title"))
        self.ld_path_label.config(text=i18n.get("config.label.path"))
        self.ld_browse_btn.config(text=i18n.get("config.btn.browse"))
        self.ld_instance_label.config(text=i18n.get("config.label.instance"))
        self.ld_adb_label.config(text=i18n.get("config.label.adb_id_optional"))
        
        self.minicap_frame.config(text=i18n.get("config.minicap.frame.title"))
        self.minicap_adb_label.config(text=i18n.get("config.label.adb_id_auto"))

        # Refill emulator options with translated strings while keeping the mapping
        # This is tricky because `self.selected_display_name` holds the current display name.
        current_selection_key = self.EMULATOR_OPTIONS.get(self.selected_display_name.get())
        
        self.EMULATOR_OPTIONS = {
            i18n.get("config.type.mumu"): "mumu",
            i18n.get("config.type.ldplayer"): "ldplayer",
            i18n.get("config.type.minicap"): "minicap"
        }
        self.emulator_combobox['values'] = list(self.EMULATOR_OPTIONS.keys())
        
        # Restore selection
        for disp, key in self.EMULATOR_OPTIONS.items():
            if key == current_selection_key:
                self.emulator_combobox.set(disp)
                break

    def _on_selection_change(self, event=None):
        display_name = self.selected_display_name.get()
        selected_type = self.EMULATOR_OPTIONS.get(display_name)
        logger.debug(f"模拟器类型切换为: {selected_type}")

        if selected_type == "mumu":
            self.mumu_frame.tkraise()
        elif selected_type == "ldplayer":
            self.ldplayer_frame.tkraise()
        else:  # minicap
            self.minicap_frame.tkraise()

    def _browse_mumu_path(self):
        logger.debug("打开 '浏览' 对话框以选择MuMu路径。")
        path = filedialog.askdirectory(title=i18n.get("config.browse.title.mumu"))
        if path:
            logger.info(f"用户选择了MuMu路径: {path}")
            self.mumu_path_entry.delete(0, "end")
            self.mumu_path_entry.insert(0, path)
        else:
            logger.debug("用户取消了路径选择。")

    def _browse_ldplayer_path(self):
        logger.debug("打开 '浏览' 对话框以选择雷电模拟器路径。")
        path = filedialog.askdirectory(title=i18n.get("config.browse.title.ldplayer"))
        if path:
            logger.info(f"用户选择了雷电模拟器路径: {path}")
            self.ldplayer_path_entry.delete(0, "end")
            self.ldplayer_path_entry.insert(0, path)
        else:
            logger.debug("用户取消了路径选择。")

    def _save_and_close(self):
        logger.debug("用户点击 '保存并启动' 按钮。")
        display_name = self.selected_display_name.get()
        cfg_type = self.EMULATOR_OPTIONS.get(display_name)

        self.config_data = {"type": cfg_type, "active_calibration_profile": None}

        if cfg_type == "mumu":
            mumu_path = self.mumu_path_entry.get().strip()
            if not mumu_path:
                logger.warning("保存失败：MuMu模拟器安装路径为空。")
                Messagebox.show_error(i18n.get("config.error.mumu_path_empty"), title=i18n.get("config.error.mumu_path_empty.title"), parent=self)
                return
            self.config_data["install_path"] = mumu_path

            instance_str = self.mumu_instance_entry.get().strip()
            try:
                instance_idx = int(instance_str)
            except ValueError:
                logger.warning(f"无效的MuMu实例索引 '{instance_str}'，将使用默认值 0。")
                instance_idx = 0
            self.config_data["instance_index"] = instance_idx

        elif cfg_type == "ldplayer":
            ld_path = self.ldplayer_path_entry.get().strip()
            if not ld_path:
                logger.warning("保存失败：雷电模拟器安装路径为空。")
                Messagebox.show_error(i18n.get("config.error.ld_path_empty"), title=i18n.get("config.error.ld_path_empty.title"), parent=self)
                return
            self.config_data["install_path"] = ld_path

            instance_str = self.ldplayer_instance_entry.get().strip()
            try:
                instance_idx = int(instance_str)
            except ValueError:
                logger.warning(f"无效的雷电实例索引 '{instance_str}'，将使用默认值 0。")
                instance_idx = 0
            self.config_data["instance_index"] = instance_idx

            ld_id = self.ldplayer_id_entry.get().strip()
            if ld_id:
                self.config_data["device_id"] = ld_id

        else:  # minicap
            minicap_id = self.minicap_id_entry.get().strip()
            if minicap_id:
                self.config_data["device_id"] = minicap_id

        self.config_data["language"] = self.language_var.get()

        logger.info(f"生成新配置: {self.config_data}")
        save_config(self.config_data)
        self.destroy()
        logger.debug("ConfigWindow 已销毁。")


def create_config_with_gui(parent) -> Optional[Dict[str, Any]]:
    """启动GUI让用户创建配置。"""
    logger.info("启动配置向导 GUI...")
    window = ConfigWindow(parent)
    parent.wait_window(window)  # 等待窗口关闭
    logger.info(f"配置向导结束。返回的配置数据: {window.config_data}")
    return window.config_data
