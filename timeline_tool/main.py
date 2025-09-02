import ctypes
import logging
import sys

import ttkbootstrap as ttkb

import utils

utils.setup_logging()

from app import TimelineApp


def main():
    """程序主函数"""
    logger = logging.getLogger(__name__)
    logger.info("应用程序启动...")

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        logger.debug("设置DPI感知成功 (Per Monitor v2)。")
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            logger.debug("设置DPI感知成功 (System DPI Aware)。")
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
                logger.debug("设置DPI感知成功 (兼容模式)。")
            except (AttributeError, OSError):
                logger.warning("设置DPI感知失败。")

    try:
        root = ttkb.Window(themename="darkly")

        scaling_factor = root.tk.call('tk', 'scaling')
        logger.info(f"检测到系统DPI缩放比例为: {scaling_factor:.2f} ({int(scaling_factor * 100)}%)")
        root.tk.call('tk', 'scaling', scaling_factor)

        # 将缩放比例传递给主应用类
        app = TimelineApp(root, scaling_factor=scaling_factor)

        root.mainloop()
        logger.info("应用程序正常关闭。")
    except Exception as e:
        logger.critical(f"应用程序因未捕获的异常而崩溃: {e}", exc_info=True)


if __name__ == "__main__":
    main()

