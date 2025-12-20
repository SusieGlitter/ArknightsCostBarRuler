import tkinter as tk
from tkinter import ttk, simpledialog, TclError
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip
import queue
import logging
import os
from PIL import Image, ImageTk

try:
    import winsound

    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False
    logging.warning("'winsound' 模块未找到，声音提醒功能将不可用。")

import config
from utils import resource_path, format_frame_time
from file_io import load_timeline_from_file, save_timeline_to_file
from websocket_client import WebsocketClient
from i18n import i18n

logger = logging.getLogger(__name__)


class TimelineApp:
    def __init__(self, root, scaling_factor=1.0):
        self.root = root

        # --- 基于缩放比例计算所有UI尺寸 ---
        self.scaling_factor = scaling_factor
        self._calculate_scaled_dimensions()

        self._configure_root_window()

        # --- 核心状态 ---
        self.MODE_LOGGING = "mode.logging"
        self.MODE_ALIGNMENT = "mode.alignment"
        self.mode = tk.StringVar(value=self.MODE_LOGGING)
        self.timeline_data = []
        self.current_game_frame = 0
        self.timeline_offset = 0.0  # 使用浮点数以获得更平滑的拖动
        self.magnet_mode = tk.BooleanVar(value=True)
        self.current_next_node = None

        # --- 提醒功能配置 ---
        self.sound_alert_enabled = tk.BooleanVar(value=True)
        self.visual_alert_enabled = tk.BooleanVar(value=True)
        self.alert_lead_frames = {"sound": 60, "visual": 60}
        self.last_sound_alert_frame = -1
        self.is_flashing = False

        self.alert_lead_var = tk.StringVar()
        self.alert_lead_var.set(str(self.alert_lead_frames["visual"]))
        self.alert_lead_var.trace_add("write", self._update_alert_lead)

        # --- 拖动与动画数据 ---
        self._window_drag_data = {"x": 0, "y": 0}
        self._timeline_drag_data = {"x": 0, "start_x": 0, "is_dragging": False, "last_dx": 0}
        self.is_animating = False
        self.animation_target_frame = 0
        self.is_inertial_scrolling = False
        self.inertia_velocity = 0.0

        # --- 通信队列与图标 ---
        self.ws_queue = queue.Queue()
        self.icons = {}
        self._load_icons()

        # --- UI设置与启动 ---
        self._setup_styles()
        self._setup_ui()
        self.mode.trace_add("write", self._update_ui_for_mode)
        self._update_ui_for_mode()

        # --- 启动后台服务与UI更新循环 ---
        self.ws_client = WebsocketClient(config.WEBSOCKET_URI)
        self.ws_client.start(self.ws_queue)
        self.root.after(config.QUEUE_POLL_INTERVAL, self._process_ws_queue)
        logger.info(f"TimelineApp {config.VERSION} 初始化完成。")

    def _calculate_scaled_dimensions(self):
        """根据缩放因子计算所有UI元素的尺寸。"""
        sf = self.scaling_factor
        # 窗口与图标
        self.scaled_win_width = int(config.WINDOW_WIDTH * sf)
        self.scaled_win_height = int(config.WINDOW_HEIGHT * sf)
        self.scaled_icon_size = (int(config.ICON_SIZE[0] * sf), int(config.ICON_SIZE[1] * sf))

        # 时间轴与节点尺寸
        self.scaled_pixels_per_frame = config.PIXELS_PER_FRAME * sf
        self.scaled_node_diamond_h = int(config.NODE_DIAMOND_SIZE["h"] * sf)
        self.scaled_node_diamond_w = int(config.NODE_DIAMOND_SIZE["w"] * sf)
        self.scaled_track_height = int(config.TIMELINE_TRACK_HEIGHT * sf)
        self.scaled_major_tick_h = int(config.TIMELINE_MAJOR_TICK_H * sf)
        self.scaled_minor_tick_h = int(config.TIMELINE_MINOR_TICK_H * sf)

        # 字体
        self.scaled_font_normal = int(config.FONT_SIZE_NORMAL * sf)
        self.scaled_font_large = int(config.FONT_SIZE_LARGE * sf)

        # 边距和 UI 绘图细节
        self.scaled_pad_xs = int(config.PADDING_XS * sf)
        self.scaled_pad_s = int(config.PADDING_S * sf)
        self.scaled_pad_m = int(config.PADDING_M * sf)
        self.scaled_pad_l = int(config.PADDING_L * sf)
        self.scaled_pad_xl = int(config.PADDING_XL * sf)

        self.scaled_time_label_offset = int(config.TIMELINE_TIME_LABEL_OFFSET_Y * sf)
        self.scaled_node_name_offset = int(config.NODE_NAME_LABEL_OFFSET_Y * sf)
        self.scaled_playhead_h = int(config.PLAYHEAD_TRIANGLE_HEIGHT * sf)
        self.scaled_playhead_w = int(config.PLAYHEAD_TRIANGLE_WIDTH * sf)
        self.scaled_cursor_wing = int(config.CENTER_CURSOR_WING_LENGTH * sf)
        self.scaled_drag_threshold = int(config.DRAG_START_THRESHOLD * sf)

    def _configure_root_window(self):
        """配置根窗口的基本属性。"""
        self.root.title(f"{i18n.get('app.title')} {config.VERSION}")
        self.root.geometry(f"{self.scaled_win_width}x{self.scaled_win_height}+100+100")
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", config.DEFAULT_ALPHA)

    def _load_icons(self):
        """加载所有需要的图标文件。"""
        icon_files = {"open": "open.png", "save": "save.png", "magnet_on": "magnet_on.png",
                      "magnet_off": "magnet_off.png", "add": "add.png", "remove": "remove.png", "color": "color.png",
                      "sound_on": "sound_on.png", "sound_off": "sound_off.png", "visual_on": "visual_on.png",
                      "visual_off": "visual_off.png", "rename": "rename.png"}
        for name, filename in icon_files.items():
            path = resource_path(os.path.join(config.ICON_DIR, filename))
            try:
                img = Image.open(path).resize(self.scaled_icon_size, Image.Resampling.LANCZOS)
                self.icons[name] = ImageTk.PhotoImage(img)
            except FileNotFoundError:
                self.icons[name] = None
                logger.error(f"图标文件未找到: {path}")

    def _setup_styles(self):
        """设置应用程序的ttkbootstrap样式。"""
        style = ttkb.Style.get_instance()
        style.configure("TFrame", background="#282c34")
        style.configure("TLabel", background="#282c34", foreground="#abb2bf")
        style.configure("Tool.TButton", background="#282c34", borderwidth=0, focuscolor="#282c34",
                        padding=config.TOOL_BUTTON_PADDING)
        style.map("Tool.TButton", background=[("active", "#3e4451")])
        style.configure("Info.TLabel", font=(config.FONT_FAMILY, self.scaled_font_normal))
        style.configure("Now.Info.TLabel", foreground="cyan")

    def _setup_ui(self):
        """创建应用程序的主要用户界面。"""
        main_frame = ttk.Frame(self.root, style="TFrame")
        main_frame.pack(expand=True, fill=BOTH)
        self.ops_frame = ttk.Frame(main_frame, width=self.scaled_win_width // 3, style="TFrame")
        self.ops_frame.pack(side=LEFT, fill=Y, padx=self.scaled_pad_m, pady=self.scaled_pad_m)
        self.ops_frame.pack_propagate(False)
        self.dynamic_ops_frame = ttk.Frame(self.ops_frame, style="TFrame")
        self.dynamic_ops_frame.pack(side=TOP, fill=BOTH, expand=True)
        self.dynamic_ops_frame.columnconfigure((0, 1, 2), weight=1)
        display_frame = ttk.Frame(main_frame, style="TFrame")
        display_frame.pack(side=LEFT, expand=True, fill=BOTH)

        self.timeline_canvas = tk.Canvas(display_frame, bg="#21252b", highlightthickness=0)
        self.timeline_canvas.place(relx=0, rely=0, relwidth=1.0, relheight=2 / 3)
        self.timeline_canvas.bind("<ButtonPress-1>", self._on_timeline_drag_start)
        self.timeline_canvas.bind("<B1-Motion>", self._on_timeline_drag_motion)
        self.timeline_canvas.bind("<ButtonRelease-1>", self._on_timeline_release)

        info_frame = ttk.Frame(display_frame, style="TFrame")
        info_frame.place(relx=0, rely=2 / 3, relwidth=1.0, relheight=1 / 3)

        self.info_time_label = ttk.Label(info_frame, text="00:00:00", style="Info.TLabel",
                                         font=(config.FONT_FAMILY, self.scaled_font_large, "bold"))
        self.info_time_label.pack(side=LEFT, padx=(self.scaled_pad_l, 0))
        self.info_diamond_label = ttk.Label(info_frame, text="", style="Info.TLabel")
        self.info_diamond_label.pack(side=LEFT, padx=(self.scaled_pad_m, 0))
        self.info_name_label = ttk.Label(info_frame, text="", style="Info.TLabel", cursor="hand2")
        self.info_name_label.pack(side=LEFT, padx=(0, self.scaled_pad_m))
        self.info_name_label.bind("<Button-1>", self._on_node_name_click)
        self.info_name_label.bind("<B1-Motion>", self._on_window_drag_motion)
        self.info_remaining_label = ttk.Label(info_frame, text="", style="Info.TLabel")
        self.info_remaining_label.pack(side=LEFT, padx=self.scaled_pad_m)

        for widget in (info_frame, self.info_time_label, self.info_diamond_label, self.info_remaining_label):
            widget.bind("<ButtonPress-1>", self._on_window_drag_start)
            widget.bind("<B1-Motion>", self._on_window_drag_motion)

        quit_button = ttk.Button(self.ops_frame, text=i18n.get("op.exit", "退出"), command=self.root.quit, style="Danger.TButton")
        quit_button.pack(side=BOTTOM, fill=X, pady=(0, self.scaled_pad_m))
        switch_frame = ttk.Frame(self.ops_frame, style="TFrame")
        switch_frame.pack(side=BOTTOM, fill=X, pady=self.scaled_pad_m)
        switch_frame.columnconfigure((0, 1), weight=1)
        ttk.Radiobutton(switch_frame, text=i18n.get("mode.logging"), variable=self.mode, value=self.MODE_LOGGING,
                        style="Outline.Toolbutton").grid(row=0, column=0, sticky="ew", padx=self.scaled_pad_xs)
        ttk.Radiobutton(switch_frame, text=i18n.get("mode.alignment"), variable=self.mode, value=self.MODE_ALIGNMENT,
                        style="Outline.Toolbutton").grid(row=0, column=1, sticky="ew", padx=self.scaled_pad_xs)

    def _process_ws_queue(self):
        """处理来自WebSocket的消息队列并更新UI。"""
        try:
            while not self.ws_queue.empty():
                data = self.ws_queue.get_nowait()
                if data.get("isRunning"):
                    self.current_game_frame = data.get("totalElapsedFrames", self.current_game_frame)

            if self.is_animating:
                distance = self.animation_target_frame - self.timeline_offset
                if abs(distance) < 0.5:
                    self.timeline_offset = self.animation_target_frame
                    self.is_animating = False
                else:
                    self.timeline_offset += distance * 0.2
            elif self.is_inertial_scrolling:
                self.timeline_offset -= self.inertia_velocity
                self.inertia_velocity *= config.INERTIA_FRICTION
                if abs(self.inertia_velocity) < 0.1:
                    self.is_inertial_scrolling = False
                    self.inertia_velocity = 0

            self._update_display()
        except queue.Empty:
            pass
        finally:
            self.root.after(config.QUEUE_POLL_INTERVAL, self._process_ws_queue)

    def _update_ui_for_mode(self, *args):
        """根据当前模式（打轴/对轴）更新UI。"""
        if self.is_flashing:
            self.is_flashing = False

        for widget in self.dynamic_ops_frame.winfo_children():
            widget.destroy()
        for i in range(4): self.dynamic_ops_frame.rowconfigure(i, weight=1)
        if self.mode.get() == self.MODE_LOGGING:
            self.magnet_mode.set(False)
            self._create_editing_buttons()
        else:
            self.magnet_mode.set(True)
            self._create_following_buttons()

    def _create_grid_button(self, parent, r, c, text, icon_name, command):
        """在网格布局中创建一个带图标和工具提示的按钮。"""
        icon = self.icons.get(icon_name)
        btn = ttk.Button(parent, command=command, style="Tool.TButton")
        if icon:
            btn.config(image=icon)
            btn.tooltip = ToolTip(btn, text=text)
        else:
            btn.config(text=text)
        btn.grid(row=r, column=c, padx=self.scaled_pad_s, pady=self.scaled_pad_s, sticky="nsew")
        return btn

    def _create_grid_toggle_button(self, parent, r, c, text_on, text_off, var, on_icon, off_icon, command=None):
        """创建一个切换按钮，其外观根据布尔变量的状态而改变。"""
        btn = ttk.Button(parent, style="Tool.TButton")
        tooltip = ToolTip(btn)

        def update_display():
            is_on = var.get()
            icon_name = on_icon if is_on else off_icon
            current_text = text_on if is_on else text_off
            icon = self.icons.get(icon_name)
            tooltip.text = current_text
            if icon:
                btn.config(image=icon, text="")
            else:
                btn.config(text=current_text, image="")

        def toggler():
            var.set(not var.get())
            update_display()
            if command: command()

        btn.config(command=toggler)
        update_display()
        btn.grid(row=r, column=c, padx=self.scaled_pad_s, pady=self.scaled_pad_s, sticky="nsew")
        return btn

    def _create_editing_buttons(self):
        """为“打轴模式”创建操作按钮。"""
        frame = self.dynamic_ops_frame
        self._create_grid_button(frame, 0, 0, i18n.get("op.open"), "open", self._load_timeline)
        self._create_grid_button(frame, 0, 1, i18n.get("op.save"), "save", self._save_timeline)
        self.add_remove_btn = self._create_grid_button(frame, 0, 2, i18n.get("op.add"), "add",
                                                       self._add_or_remove_node_at_cursor)
        self._create_grid_button(frame, 1, 0, i18n.get("op.color"), "color", self._change_node_color_at_cursor)
        self._create_grid_button(frame, 1, 1, i18n.get("op.rename"), "rename", self._rename_node_at_cursor)

        def on_magnet_toggle():
            if not self.magnet_mode.get():
                self.timeline_offset = self.current_game_frame
                logger.debug(i18n.get("log.magnet_off.manual", frame=self.timeline_offset))

        self._create_grid_toggle_button(frame, 1, 2, i18n.get("op.magnet.on"), i18n.get("op.magnet.off"), self.magnet_mode, "magnet_on",
                                        "magnet_off", command=on_magnet_toggle)

    def _create_following_buttons(self):
        """为“对轴模式”创建操作按钮。"""
        frame = self.dynamic_ops_frame
        self._create_grid_button(frame, 0, 0, i18n.get("op.open"), "open", self._load_timeline)
        self._create_grid_toggle_button(frame, 0, 1, i18n.get("op.sound.on"), i18n.get("op.sound.off"), self.sound_alert_enabled,
                                        "sound_on", "sound_off")
        self._create_grid_toggle_button(frame, 0, 2, i18n.get("op.visual.on"), i18n.get("op.visual.off"), self.visual_alert_enabled,
                                        "visual_on", "visual_off")
        lead_frame = ttk.Frame(frame, style="TFrame")
        lead_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(self.scaled_pad_xl, 0))
        ttk.Label(lead_frame, text=i18n.get("label.lead_frames"), font=(config.FONT_FAMILY, self.scaled_font_normal)).pack(side=LEFT, padx=self.scaled_pad_m)
        spinbox = ttk.Spinbox(
            lead_frame,
            from_=0,
            to_=300,
            textvariable=self.alert_lead_var,
            width=5
        )
        spinbox.pack(side=LEFT, padx=self.scaled_pad_m)
        spinbox.bind('<Return>', self._update_alert_lead)

    def _update_alert_lead(self, *args):
        """更新提醒提前的帧数。"""
        try:
            frames_str = self.alert_lead_var.get()
            if frames_str:
                frames = int(frames_str)
                frames = max(0, min(frames, 300))
                self.alert_lead_frames["sound"] = frames
                self.alert_lead_frames["visual"] = frames
                logger.debug(f"提醒提前时间已更新为: {frames} 帧")
        except (ValueError, TclError):
            logger.warning("输入的提醒提前帧数无效。")
            pass

    def _draw_timeline_track(self, canvas, width, height):
        """绘制时间轴的背景轨道。"""
        track_height = self.scaled_track_height
        y0 = (height - track_height) / 2
        y1 = (height + track_height) / 2
        canvas.create_rectangle(0, y0, width, y1, fill=config.TIMELINE_TRACK_COLOR, outline="")

    def _draw_timeline_ticks(self, canvas, center_frame, width, height, pixels_per_frame):
        """绘制时间轴上的刻度线和时间标签。"""
        if pixels_per_frame <= 0: return
        frames_in_view = width / pixels_per_frame
        start_frame = int(center_frame - frames_in_view / 2)
        end_frame = int(center_frame + frames_in_view / 2)

        for frame in range(start_frame, end_frame + 1):
            if frame < 0: continue

            x_pos = width / 2 + (frame - center_frame) * pixels_per_frame

            if frame % config.FPS == 0:
                y0 = height / 2 - self.scaled_major_tick_h
                y1 = height / 2 + self.scaled_major_tick_h
                canvas.create_line(x_pos, y0, x_pos, y1, fill=config.TIMELINE_TICK_COLOR, width=2)

                time_str = f"{frame // (config.FPS * 60):02d}:{(frame // config.FPS) % 60:02d}"
                canvas.create_text(x_pos, y0 - self.scaled_time_label_offset, text=time_str, fill=config.TIMELINE_TICK_COLOR,
                                   font=(config.FONT_FAMILY, self.scaled_font_normal),
                                   anchor="s")

            elif frame % config.TIMELINE_SUBTICK_INTERVAL == 0:
                y0 = height / 2 - self.scaled_minor_tick_h
                y1 = height / 2 + self.scaled_minor_tick_h
                canvas.create_line(x_pos, y0, x_pos, y1, fill=config.TIMELINE_SUBTICK_COLOR, width=1)

    def _draw_nodes(self, canvas, center_frame, width, height, pixels_per_frame, node_on_cursor):
        """在时间轴上绘制所有节点。"""
        for node in self.timeline_data:
            frame_diff = node["frame"] - center_frame
            x_pos = width / 2 + frame_diff * pixels_per_frame
            if not (-self.scaled_node_diamond_w < x_pos < width + self.scaled_node_diamond_w): continue

            scale = config.NODE_SELECTED_SCALE if node == node_on_cursor else 1.0
            outline_color = config.NODE_SELECTED_OUTLINE_COLOR if node == node_on_cursor else config.NODE_OUTLINE_COLOR
            outline_width = 2 if node == node_on_cursor else 1

            h = self.scaled_node_diamond_h * scale
            w = self.scaled_node_diamond_w * scale
            points = [x_pos, height / 2 - h, x_pos + w, height / 2, x_pos, height / 2 + h, x_pos - w, height / 2]

            canvas.create_polygon(points, fill=node["color"], outline=outline_color, width=outline_width,
                                  tags=f"node_{node['frame']}")
            canvas.create_text(x_pos, height / 2 + (h + self.scaled_node_name_offset), text=node["name"], fill="white",
                               font=(config.FONT_FAMILY, self.scaled_font_normal),
                               anchor="n")

    def _draw_playhead(self, canvas, center_frame, width, height, pixels_per_frame):
        """绘制游戏当前时间指示器。"""
        playhead_x = width / 2 + (self.current_game_frame - center_frame) * pixels_per_frame
        if not (0 <= playhead_x <= width): return

        canvas.create_line(playhead_x, 0, playhead_x, height, fill="#ff6347", width=2, dash=(4, 2))
        ph = self.scaled_playhead_h
        pw = self.scaled_playhead_w
        canvas.create_polygon(playhead_x, ph, playhead_x - pw / 2, 0, playhead_x + pw / 2, 0, fill='#ff6347',
                              outline='')

    def _draw_center_cursor(self, canvas, width, height):
        """绘制时间轴的中心标记。"""
        center_x = width / 2
        canvas.create_line(center_x, 0, center_x, height, fill="#00FFFF", width=2)
        wing_len = self.scaled_cursor_wing
        canvas.create_line(center_x - wing_len, 0, center_x + wing_len, 0, fill="#00FFFF", width=2)
        canvas.create_line(center_x - wing_len, height, center_x + wing_len, height, fill="#00FFFF", width=2)

    def _update_display(self):
        """更新整个显示区域，包括时间轴和信息面板。"""
        canvas = self.timeline_canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width <= 1 or height <= 1: return

        center_frame = self.get_current_display_frame()
        pixels_per_frame = self.scaled_pixels_per_frame

        self._draw_timeline_track(canvas, width, height)
        self._draw_timeline_ticks(canvas, center_frame, width, height, pixels_per_frame)

        node_on_cursor = self._find_node_at(center_frame, tolerance=config.NODE_FIND_TOLERANCE)
        self._draw_nodes(canvas, center_frame, width, height, pixels_per_frame, node_on_cursor)

        self._draw_playhead(canvas, center_frame, width, height, pixels_per_frame)
        self._draw_center_cursor(canvas, width, height)

        self.info_time_label.config(text=format_frame_time(center_frame))

        self.current_next_node = self._find_next_node(center_frame)
        node_to_display = node_on_cursor if node_on_cursor else self.current_next_node

        if node_to_display:
            self.info_diamond_label.config(text=" ♦", foreground=node_to_display['color'])
            self.info_name_label.config(
                text=f" {node_to_display['name']}({format_frame_time(node_to_display['frame'])})")
            if node_to_display == node_on_cursor:
                self.info_remaining_label.config(text=i18n.get("info.now"), style="Now.Info.TLabel")
            else:
                time_to_next = node_to_display['frame'] - center_frame
                self.info_remaining_label.config(text=i18n.get("info.later", frames=int(time_to_next)), style="Info.TLabel")
        else:
            self.info_diamond_label.config(text="")
            self.info_name_label.config(text="")
            self.info_remaining_label.config(text="")

        if self.mode.get() == self.MODE_ALIGNMENT:
            if self.current_next_node:
                time_to_alert = self.current_next_node['frame'] - center_frame
                self._handle_alerts(time_to_alert, self.current_next_node['frame'])
            else:
                self._handle_alerts(-1, -1)
        else:
            self._handle_alerts(-1, -1)

        if self.mode.get() == self.MODE_LOGGING and hasattr(self, 'add_remove_btn'):
            icon_name = "remove" if node_on_cursor else "add"
            text = "op.remove" if node_on_cursor else "op.add" # Use key for dynamic text if possible or get valid string
            text_str = i18n.get("op.remove") if node_on_cursor else i18n.get("op.add")
            icon = self.icons.get(icon_name)
            if icon:
                self.add_remove_btn.config(image=icon)
                if hasattr(self.add_remove_btn, 'tooltip'):
                    self.add_remove_btn.tooltip.text = text_str
                else:
                    self.add_remove_btn.tooltip = ToolTip(self.add_remove_btn, text=text_str)

    def _on_timeline_drag_start(self, event):
        """处理时间轴拖动的开始事件。"""
        self.is_animating = False
        self.is_inertial_scrolling = False
        self._timeline_drag_data.update({"x": event.x, "start_x": event.x, "is_dragging": False, "last_dx": 0})

    def _on_timeline_drag_motion(self, event):
        """处理时间轴的拖动事件。"""
        if not self._timeline_drag_data["is_dragging"] and abs(
                event.x - self._timeline_drag_data["start_x"]) > self.scaled_drag_threshold:
            self._timeline_drag_data["is_dragging"] = True

        if not self._timeline_drag_data["is_dragging"]: return

        dx = event.x - self._timeline_drag_data["x"]
        self._timeline_drag_data["last_dx"] = dx
        frame_delta = dx / self.scaled_pixels_per_frame if self.scaled_pixels_per_frame else 0

        if self.magnet_mode.get():
            if abs(dx) > config.MAGNET_BREAK_THRESHOLD:
                logger.info(i18n.get("log.magnet_off"))
                self.magnet_mode.set(False)
                self.timeline_offset = self.current_game_frame - frame_delta
        else:
            self.timeline_offset -= frame_delta
        self._timeline_drag_data["x"] = event.x

    def _on_timeline_release(self, event):
        """处理时间轴上的鼠标释放事件（拖动结束或单击）。"""
        was_dragging = self._timeline_drag_data["is_dragging"]
        self._timeline_drag_data["is_dragging"] = False

        if was_dragging:
            if not self.magnet_mode.get():
                self.inertia_velocity = self._timeline_drag_data["last_dx"] / self.scaled_pixels_per_frame if self.scaled_pixels_per_frame else 0
                self.is_inertial_scrolling = True
        else:
            if not self.magnet_mode.get():
                width = self.timeline_canvas.winfo_width()
                pixels_per_frame = self.scaled_pixels_per_frame
                if pixels_per_frame <= 0: return
                clicked_frame = int(self.timeline_offset + (event.x - width / 2) / pixels_per_frame)
                node_to_snap = self._find_node_at(clicked_frame, tolerance=config.NODE_CLICK_TOLERANCE)
                if node_to_snap:
                    logger.info(i18n.get("log.clicked", name=node_to_snap['name'], frame=node_to_snap['frame']))
                    self._animate_scroll_to(node_to_snap['frame'])

    def _animate_scroll_to(self, target_frame):
        """平滑滚动到指定的目标帧。"""
        if self.is_animating: return
        self.is_inertial_scrolling = False
        self.is_animating = True
        self.animation_target_frame = int(target_frame)

    def _find_node_at(self, frame, tolerance=config.NODE_FIND_TOLERANCE):
        """在指定帧附近查找节点。"""
        closest_node = None
        min_dist = float('inf')
        # 将帧转换为整数进行比较
        int_frame = int(round(frame))
        for node in self.timeline_data:
            dist = abs(node["frame"] - int_frame)
            if dist <= tolerance and dist < min_dist:
                min_dist = dist
                closest_node = node
        return closest_node

    def get_current_display_frame(self):
        """获取当前时间轴中心应该显示的帧。"""
        return self.current_game_frame if self.magnet_mode.get() else int(round(self.timeline_offset))

    def _on_window_drag_start(self, event):
        """处理窗口拖动的开始事件。"""
        self._window_drag_data = {"x": event.x, "y": event.y}

    def _on_window_drag_motion(self, event):
        """处理窗口的拖动事件。"""
        dx = event.x - self._window_drag_data["x"]
        dy = event.y - self._window_drag_data["y"]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")

    def _load_timeline(self):
        """加载时间轴文件。"""
        loaded_data = load_timeline_from_file(self.root)
        if loaded_data is not None:
            self.timeline_data = loaded_data

    def _save_timeline(self):
        """保存当前时间轴数据到文件。"""
        save_timeline_to_file(self.timeline_data, self.root)

    def _find_next_node(self, from_frame):
        """从给定帧开始查找下一个节点。"""
        return next(
            (node for node in sorted(self.timeline_data, key=lambda x: x['frame']) if node['frame'] > from_frame), None)

    def _add_or_remove_node_at_cursor(self):
        """在光标位置添加或移除节点。"""
        current_frame = self.get_current_display_frame()
        node_to_remove = self._find_node_at(current_frame, tolerance=config.NODE_FIND_TOLERANCE)
        if node_to_remove:
            self.timeline_data.remove(node_to_remove)
            logger.info(i18n.get("log.removed", name=node_to_remove['name']))
        else:
            new_node = {"frame": current_frame, "name": f"Node@{format_frame_time(current_frame)}",
                        "color": config.NODE_COLORS[0]}
            self.timeline_data.append(new_node)
            logger.info(i18n.get("log.added", frame=current_frame))

    def _rename_node_logic(self, node_to_rename):
        """重命名指定节点的逻辑。"""
        if not node_to_rename: return
        new_name = simpledialog.askstring(i18n.get("dialog.rename.title"), i18n.get("dialog.rename.prompt"), initialvalue=node_to_rename.get('name', ''),
                                          parent=self.root)
        if new_name and new_name.strip():
            logger.info(i18n.get("log.renamed", old=node_to_rename['name'], new=new_name.strip()))
            node_to_rename['name'] = new_name.strip()

    def _rename_node_at_cursor(self):
        """重命名光标位置的节点。"""
        self._rename_node_logic(
            self._find_node_at(self.get_current_display_frame(), tolerance=config.NODE_FIND_TOLERANCE))

    def _on_node_name_click(self, event):
        """处理信息面板中节点名称标签的点击事件。"""
        if self.mode.get() == self.MODE_LOGGING:
            node_on_cursor = self._find_node_at(self.get_current_display_frame(), tolerance=config.NODE_FIND_TOLERANCE)
            node_to_rename = node_on_cursor if node_on_cursor else self.current_next_node
            if node_to_rename:
                self._rename_node_logic(node_to_rename)
        else:
            self._on_window_drag_start(event)

    def _change_node_color_at_cursor(self):
        """更改光标位置节点的颜色。"""
        node = self._find_node_at(self.get_current_display_frame(), tolerance=config.NODE_FIND_TOLERANCE)
        if node:
            try:
                current_color_index = config.NODE_COLORS.index(node['color'])
                next_color_index = (current_color_index + 1) % len(config.NODE_COLORS)
                node['color'] = config.NODE_COLORS[next_color_index]
            except ValueError:
                node['color'] = config.NODE_COLORS[0]
            logger.debug(f"节点 '{node['name']}' 颜色已更改为 {node['color']}")

    def _handle_alerts(self, time_to_next, node_frame):
        """处理声音和视觉提醒。"""
        if HAS_WINSOUND and self.sound_alert_enabled.get() and \
                0 < time_to_next <= self.alert_lead_frames["sound"] and \
                self.last_sound_alert_frame != node_frame:
            winsound.PlaySound("SystemAsterisk", winsound.SND_ASYNC)
            self.last_sound_alert_frame = node_frame

        should_be_flashing = self.visual_alert_enabled.get() and 0 < time_to_next <= self.alert_lead_frames["visual"]

        if should_be_flashing and not self.is_flashing:
            self.is_flashing = True
            self._flash_loop()
        elif not should_be_flashing and self.is_flashing:
            self.is_flashing = False

    def _flash_loop(self):
        """视觉提醒的闪烁循环。"""
        if not self.is_flashing:
            try:
                style = ttkb.Style.get_instance()
                style.configure("TFrame", background="#282c34")
                style.configure("TLabel", background="#282c34")
                style.configure("Tool.TButton", background="#282c34")
            except tk.TclError:
                pass
            return

        try:
            style = ttkb.Style.get_instance()
            current_bg = style.lookup("TFrame", "background")
            next_bg = "#ff6347" if current_bg == "#282c34" else "#282c34"
            style.configure("TFrame", background=next_bg)
            style.configure("TLabel", background=next_bg)
            style.configure("Tool.TButton", background=next_bg)
            self.root.after(250, self._flash_loop)
        except tk.TclError:
            pass
