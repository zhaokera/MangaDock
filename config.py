"""
配置管理模块
支持从 config.yaml 和环境变量加载配置
"""

import os
import logging
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class NetworkConfig:
    proxy: Optional[str] = None
    timeout_connect: int = 30
    timeout_read: int = 60
    timeout_download: int = 300
    retry_max_attempts: int = 5
    retry_initial_delay: float = 1.0
    retry_max_delay: float = 10.0
    retry_exponential_base: float = 2


@dataclass
class DownloadConfig:
    concurrency: int = 5
    output_dir: str = "downloads"
    enable_zip: bool = True
    filename_format: str = "{chapter_name}_{page_number}.jpg"
    # 下载并发配置
    max_concurrent_images: int = 5  # 单个下载任务的最大并发图片数
    enable_chunked_transfer: bool = True  # 是否启用分块传输


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(message)s"
    file: str = "downloads/download.log"


@dataclass
class CrawlerConfig:
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    manhuagui_use_playscript: bool = True
    # 浏览器启动参数
    browser_args: list = field(default_factory=lambda: [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--set-bundle-mapping=chromium,chrome",
    ])
    # 浏览器池配置
    browser_idle_timeout: int = 300  # 浏览器空闲超时（秒），默认 5 分钟
    browser_cleanup_interval: int = 60  # 浏览器池清理检查间隔（秒），默认 60 秒
    # 认证配置
    auth_enabled: bool = False  # 是否启用认证
    auth_platforms: list = field(default_factory=list)  # 需要认证的平台列表


@dataclass
class AuthConfig:
    """认证配置"""
    # 每个平台的认证配置
    platforms: dict = field(default_factory=dict)
    # 会话保存路径
    session_dir: str = "sessions"
    # 会话过期时间（秒）
    session_expiry: int = 86400  # 24 小时


@dataclass
class SSEConfig:
    heartbeat_interval: int = 2
    buffer_size: int = 100


@dataclass
class HistoryConfig:
    max_items: int = 100
    auto_cleanup_days: int = 0


@dataclass
class Config:
    network: NetworkConfig = field(default_factory=NetworkConfig)
    download: DownloadConfig = field(default_factory=DownloadConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    crawler: CrawlerConfig = field(default_factory=CrawlerConfig)
    sse: SSEConfig = field(default_factory=SSEConfig)
    history: HistoryConfig = field(default_factory=HistoryConfig)
    host: str = "0.0.0.0"
    port: int = 8000


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config = Config()

    def load(self) -> Config:
        """加载配置"""
        # 先加载 YAML 配置
        self._load_yaml_config()

        # 再覆盖环境变量
        self._load_env_config()

        return self.config

    def _load_yaml_config(self):
        """从 YAML 文件加载配置"""
        if not self.config_path.exists():
            logger.debug(f"配置文件不存在: {self.config_path}，使用默认配置")
            return

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if not data:
                return

            # 加载 network 配置
            if 'network' in data:
                net_data = data['network']
                if 'proxy' in net_data:
                    self.config.network.proxy = net_data['proxy']
                if 'timeout' in net_data:
                    timeout = net_data['timeout']
                    if 'connect' in timeout:
                        self.config.network.timeout_connect = timeout['connect']
                    if 'read' in timeout:
                        self.config.network.timeout_read = timeout['read']
                    if 'download' in timeout:
                        self.config.network.timeout_download = timeout['download']
                if 'retry' in net_data:
                    retry = net_data['retry']
                    if 'max_attempts' in retry:
                        self.config.network.retry_max_attempts = retry['max_attempts']
                    if 'initial_delay' in retry:
                        self.config.network.retry_initial_delay = retry['initial_delay']
                    if 'max_delay' in retry:
                        self.config.network.retry_max_delay = retry['max_delay']
                    if 'exponential_base' in retry:
                        self.config.network.retry_exponential_base = retry['exponential_base']

            # 加载 download 配置
            if 'download' in data:
                dl_data = data['download']
                if 'concurrency' in dl_data:
                    self.config.download.concurrency = dl_data['concurrency']
                if 'output_dir' in dl_data:
                    self.config.download.output_dir = dl_data['output_dir']
                if 'enable_zip' in dl_data:
                    self.config.download.enable_zip = dl_data['enable_zip']
                if 'filename_format' in dl_data:
                    self.config.download.filename_format = dl_data['filename_format']

            # 加载 logging 配置
            if 'logging' in data:
                log_data = data['logging']
                if 'level' in log_data:
                    self.config.logging.level = log_data['level']
                if 'format' in log_data:
                    self.config.logging.format = log_data['format']
                if 'file' in log_data:
                    self.config.logging.file = log_data['file']

            # 加载 crawler 配置
            if 'crawler' in data:
                crawl_data = data['crawler']
                if 'user_agent' in crawl_data:
                    self.config.crawler.user_agent = crawl_data['user_agent']
                if 'browser_args' in crawl_data:
                    self.config.crawler.browser_args = crawl_data['browser_args']
                if 'websites' in crawl_data and 'manhuagui' in crawl_data['websites']:
                    mg = crawl_data['websites']['manhuagui']
                    if 'use_playscript' in mg:
                        self.config.crawler.manhuagui_use_playscript = mg['use_playscript']

            # 加载 sse 配置
            if 'sse' in data:
                sse_data = data['sse']
                if 'heartbeat_interval' in sse_data:
                    self.config.sse.heartbeat_interval = sse_data['heartbeat_interval']
                if 'buffer_size' in sse_data:
                    self.config.sse.buffer_size = sse_data['buffer_size']

            # 加载 history 配置
            if 'history' in data:
                hist_data = data['history']
                if 'max_items' in hist_data:
                    self.config.history.max_items = hist_data['max_items']
                if 'auto_cleanup_days' in hist_data:
                    self.config.history.auto_cleanup_days = hist_data['auto_cleanup_days']

            # 加载服务配置
            if 'server' in data:
                server_data = data['server']
                if 'host' in server_data:
                    self.config.host = server_data['host']
                if 'port' in server_data:
                    self.config.port = server_data['port']

        except yaml.YAMLError as e:
            logger.error(f"加载 YAML 配置失败: {e}，使用默认配置")
        except Exception as e:
            logger.error(f"读取配置文件失败: {e}，使用默认配置")

    def _load_env_config(self):
        """从环境变量加载配置（优先级更高）"""
        # 网络配置
        if os.environ.get('PROXY_URL'):
            self.config.network.proxy = os.environ.get('PROXY_URL')

        if os.environ.get('REQUEST_TIMEOUT'):
            self.config.network.timeout_read = int(os.environ.get('REQUEST_TIMEOUT'))

        if os.environ.get('DOWNLOAD_TIMEOUT'):
            self.config.network.timeout_download = int(os.environ.get('DOWNLOAD_TIMEOUT'))

        if os.environ.get('CONNECT_TIMEOUT'):
            self.config.network.timeout_connect = int(os.environ.get('CONNECT_TIMEOUT'))

        # 下载配置
        if os.environ.get('CONCURRENT_DOWNLOADS'):
            self.config.download.concurrency = int(os.environ.get('CONCURRENT_DOWNLOADS'))

        if os.environ.get('OUTPUT_DIR'):
            self.config.download.output_dir = os.environ.get('OUTPUT_DIR')

        if os.environ.get('ENABLE_ZIP') is not None:
            self.config.download.enable_zip = os.environ.get('ENABLE_ZIP').lower() == 'true'

        if os.environ.get('MAX_CONCURRENT_IMAGES'):
            self.config.download.max_concurrent_images = int(os.environ.get('MAX_CONCURRENT_IMAGES'))

        # 日志配置
        if os.environ.get('LOG_LEVEL'):
            self.config.logging.level = os.environ.get('LOG_LEVEL')

        if os.environ.get('LOG_FILE'):
            self.config.logging.file = os.environ.get('LOG_FILE')

        # 服务配置
        if os.environ.get('HOST'):
            self.config.host = os.environ.get('HOST')

        if os.environ.get('PORT'):
            self.config.port = int(os.environ.get('PORT'))

        # SSE 配置
        if os.environ.get('SSE_HEARTBEAT_INTERVAL'):
            self.config.sse.heartbeat_interval = int(os.environ.get('SSE_HEARTBEAT_INTERVAL'))

        if os.environ.get('SSE_BUFFER_SIZE'):
            self.config.sse.buffer_size = int(os.environ.get('SSE_BUFFER_SIZE'))

        # 浏览器配置
        if os.environ.get('BROWSER_IDLE_TIMEOUT'):
            self.config.crawler.browser_idle_timeout = int(os.environ.get('BROWSER_IDLE_TIMEOUT'))

        if os.environ.get('BROWSER_CLEANUP_INTERVAL'):
            self.config.crawler.browser_cleanup_interval = int(os.environ.get('BROWSER_CLEANUP_INTERVAL'))

    def validate(self) -> list[str]:
        """验证配置值的有效性"""
        errors = []
        cfg = self.config

        # 验证下载并发数
        if cfg.download.concurrency < 1:
            errors.append("download.concurrency 必须 >= 1")
        if cfg.download.max_concurrent_images < 1:
            errors.append("download.max_concurrent_images 必须 >= 1")

        # 验证网络超时
        if cfg.network.timeout_connect <= 0:
            errors.append("network.timeout_connect 必须 > 0")
        if cfg.network.timeout_read <= 0:
            errors.append("network.timeout_read 必须 > 0")
        if cfg.network.timeout_download <= 0:
            errors.append("network.timeout_download 必须 > 0")

        # 验证重试参数
        if cfg.network.retry_max_attempts < 1:
            errors.append("network.retry_max_attempts 必须 >= 1")
        if cfg.network.retry_initial_delay <= 0:
            errors.append("network.retry_initial_delay 必须 > 0")
        if cfg.network.retry_max_delay <= 0:
            errors.append("network.retry_max_delay 必须 > 0")
        if cfg.network.retry_exponential_base <= 1:
            errors.append("network.retry_exponential_base 必须 > 1")

        # 验证端口
        if cfg.port < 1 or cfg.port > 65535:
            errors.append("server.port 必须在 1-65535 范围内")

        # 验证浏览器池配置
        if cfg.crawler.browser_idle_timeout < 60:
            errors.append("crawler.browser_idle_timeout 必须 >= 60 秒")
        if cfg.crawler.browser_cleanup_interval < 30:
            errors.append("crawler.browser_cleanup_interval 必须 >= 30 秒")

        return errors


# 全局配置实例（延迟加载）
_config_manager = ConfigManager()
_config = None


def get_config() -> Config:
    """获取全局配置实例（延迟加载）"""
    global _config
    if _config is None:
        _config = _config_manager.load()
        # 验证配置
        errors = _config_manager.validate()
        if errors:
            logger.warning(f"配置警告: {'; '.join(errors)}")
    return _config


def reload_config() -> Config:
    """重新加载配置（重新验证）"""
    global _config
    _config = _config_manager.load()
    # 验证配置
    errors = _config_manager.validate()
    if errors:
        logger.warning(f"配置警告: {'; '.join(errors)}")
    return _config


import threading
import time


class ConfigWatcher:
    """配置文件监听器，支持热重载"""

    def __init__(self, config_path: str = "config.yaml", callback=None, interval: float = 2.0):
        """
        初始化配置监听器

        Args:
            config_path: 配置文件路径
            callback: 配置变化时的回调函数
            interval: 检查间隔（秒）
        """
        self.config_path = Path(config_path)
        self.callback = callback
        self.interval = interval
        self._watching = False
        self._thread = None
        self._last_mtime = None
        self._lock = threading.Lock()

    def _check_config_changed(self) -> bool:
        """检查配置文件是否变化"""
        if not self.config_path.exists():
            return False
        try:
            current_mtime = self.config_path.stat().st_mtime
            with self._lock:
                if self._last_mtime is None:
                    self._last_mtime = current_mtime
                    return False
                if current_mtime > self._last_mtime:
                    self._last_mtime = current_mtime
                    return True
                return False
        except Exception as e:
            logger.debug(f"检查配置文件变化失败: {e}")
            return False

    def _watch_loop(self):
        """监听循环"""
        while self._watching:
            if self._check_config_changed():
                logger.info("检测到配置文件变化，正在重新加载...")
                try:
                    reload_config()
                    if self.callback:
                        self.callback()
                    logger.info("配置重载完成")
                except Exception as e:
                    logger.error(f"配置重载失败: {e}")
            time.sleep(self.interval)

    def start(self):
        """启动监听"""
        if self._watching:
            return
        self._watching = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info(f"配置监听器已启动，监听文件: {self.config_path}")

    def stop(self):
        """停止监听"""
        if not self._watching:
            return
        self._watching = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("配置监听器已停止")


# 全局配置监听器实例
_config_watcher: Optional[ConfigWatcher] = None


def start_config_watcher(callback=None, interval: float = 2.0) -> ConfigWatcher:
    """
    启动配置文件监听器，支持热重载

    Args:
        callback: 配置变化时的回调函数
        interval: 检查间隔（秒）

    Returns:
        ConfigWatcher: 监听器实例
    """
    global _config_watcher
    if _config_watcher:
        _config_watcher.stop()
    _config_watcher = ConfigWatcher(callback=callback, interval=interval)
    _config_watcher.start()
    return _config_watcher


def stop_config_watcher():
    """停止配置文件监听器"""
    global _config_watcher
    if _config_watcher:
        _config_watcher.stop()
        _config_watcher = None
