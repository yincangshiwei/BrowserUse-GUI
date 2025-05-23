import logging
from typing import Optional, Callable
import sys
import colorlog

class LogListenerHandler(logging.Handler):
    """日志监听器 Handler，将日志消息传递到指定的处理函数"""
    def __init__(self, callback: Callable[[logging.LogRecord], None], level=logging.NOTSET):
        super().__init__(level)
        self.callback = callback

    def emit(self, record: logging.LogRecord):
        self.callback(record)

class LogTool:
    """
    日志工具类
    支持快速配置文件日志、终端日志，避免重复添加handler。
    支持colorlog自动彩色输出。
    支持日志监听功能。
    """

    def __init__(self,
                 name: str,
                 level: int = logging.DEBUG,
                 to_file: bool = True,
                 to_stream: bool = False,
                 log_filename: str = 'app.log',
                 file_level: Optional[int] = None,
                 stream_level: Optional[int] = None,
                 fmt: Optional[str] = None,
                 datefmt: str = '%Y-%m-%d %H:%M:%S',
                 listener: Optional[Callable[[logging.LogRecord], None]] = None,
                 listener_level: Optional[int] = None,
                 use_color: bool = True,                  # 新增: 是否彩色stream日志输出
                 color_fmt: Optional[str] = None
                 ):
        """
        :param name: logger的名称
        :param level: logger日志级别
        :param to_file: 是否记录到文件
        :param to_stream: 是否记录到终端
        :param log_filename: 日志文件路径
        :param file_level: 文件日志的级别（默认同level）
        :param stream_level: 终端日志的级别（默认同level）
        :param fmt: 日志格式
        :param datefmt: 时间格式
        :param listener: 日志监听回调函数(参数为LogRecord)
        :param listener_level: 日志监听器的级别
        :param use_color: 是否在终端日志中使用彩色输出（默认True）
        :param color_fmt: 自定义 colorlog 日志格式。为None时将使用默认格式
        """
        self.name = name
        self.level = level
        self.to_file = to_file
        self.to_stream = to_stream
        self.log_filename = log_filename
        self.file_level = file_level or level
        self.stream_level = stream_level or level
        self.fmt = fmt or '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        self.datefmt = datefmt
        self.listener = listener
        self.listener_level = listener_level or level
        self.use_color = use_color
        self.color_fmt = color_fmt or (
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def init_logger(self) -> logging.Logger:
        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)
        logger.propagate = False

        # 彩色格式设置
        if self.use_color:
            color_formatter = colorlog.ColoredFormatter(
                self.color_fmt,
                datefmt=self.datefmt,
                reset=True,
                log_colors={
                    'DEBUG':    'cyan',
                    'INFO':     'green',
                    'WARNING':  'yellow',
                    'ERROR':    'red',
                    'CRITICAL': 'bold_red'
                }
            )
        # 文件格式
        file_formatter = logging.Formatter(self.fmt, datefmt=self.datefmt)

        handler_types = {type(h) for h in logger.handlers}

        # 文件日志
        if self.to_file and logging.FileHandler not in handler_types:
            fh = logging.FileHandler(self.log_filename, encoding='utf-8', mode='a')
            fh.setLevel(self.file_level)
            fh.setFormatter(file_formatter)
            logger.addHandler(fh)

        # 终端输出
        if self.to_stream and logging.StreamHandler not in handler_types:
            sh = logging.StreamHandler(stream=sys.stdout)
            sh.setLevel(self.stream_level)
            if self.use_color:
                sh.setFormatter(color_formatter)
            else:
                sh.setFormatter(file_formatter)
            logger.addHandler(sh)

        # 日志监听
        if self.listener is not None and LogListenerHandler not in handler_types:
            lh = LogListenerHandler(callback=self.listener, level=self.listener_level)
            # 可以选择是否给监听handler用彩色或普通格式，这里默认普通格式
            lh.setFormatter(file_formatter)
            logger.addHandler(lh)

        return logger

# 用法示例
if __name__ == '__main__':
    def my_log_listener(record: logging.LogRecord):
        print('监听:', record.getMessage())  # 实际应用中可以推送到队列、数据库等

    my_logger = LogTool(
        name='demo',
        to_file=True,
        to_stream=True,      # 会自动用彩色
        listener=my_log_listener
    ).init_logger()

    my_logger.debug('Test: debug日志')
    my_logger.info('This is an info log. 支持中文。')
    my_logger.warning('测试 warning')
    my_logger.error('This is an error! 也会被监听。')
    my_logger.critical('测试 critical!')