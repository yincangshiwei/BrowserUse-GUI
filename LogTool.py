import logging
from typing import Optional

class LogTool:
    """
    日志工具类
    支持快速配置文件日志和/或终端日志，避免重复添加handler。
    """

    def __init__(self,
                 name: str,
                 level: int = logging.DEBUG,
                 to_file: bool = True,
                 to_stream: bool = False,
                 log_filename: str = 'app.log',
                 file_level: Optional[int] = None,
                 stream_level: Optional[int] = None,
                 fmt: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                 datefmt: str = '%Y-%m-%d %H:%M:%S'):
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
        """
        self.name = name
        self.level = level
        self.to_file = to_file
        self.to_stream = to_stream
        self.log_filename = log_filename
        self.file_level = file_level or level
        self.stream_level = stream_level or level
        self.fmt = fmt
        self.datefmt = datefmt

    def init_logger(self) -> logging.Logger:
        """
        初始化并返回配置好的logger
        """
        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)
        logger.propagate = False

        formatter = logging.Formatter(self.fmt, datefmt=self.datefmt)

        # 检查是否重复添加同类handler
        handler_types = {type(h) for h in logger.handlers}
        if self.to_file and logging.FileHandler not in handler_types:
            fh = logging.FileHandler(self.log_filename, encoding='utf-8', mode='a')
            fh.setLevel(self.file_level)
            fh.setFormatter(formatter)
            logger.addHandler(fh)

        if self.to_stream and logging.StreamHandler not in handler_types:
            sh = logging.StreamHandler()
            sh.setLevel(self.stream_level)
            sh.setFormatter(formatter)
            logger.addHandler(sh)

        return logger

# 用法示例
if __name__ == '__main__':
    my_logger = LogTool(name='demo', to_file=True, to_stream=True).init_logger()
    my_logger.info('This is an info log. 支持中文。')