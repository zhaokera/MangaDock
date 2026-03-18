"""配置管理测试"""

import os
import pytest
from unittest.mock import patch
from pathlib import Path

import config
from config import (
    Config,
    NetworkConfig,
    DownloadConfig,
    CrawlerConfig,
    SSEConfig,
    HistoryConfig,
    ConfigManager,
    get_config,
    reload_config,
)


class TestConfigDataclasses:
    """配置数据类测试"""

    def test_network_config_defaults(self):
        """测试 NetworkConfig 默认值"""
        cfg = NetworkConfig()
        assert cfg.timeout_connect == 30
        assert cfg.timeout_read == 60
        assert cfg.timeout_download == 300
        assert cfg.retry_max_attempts == 5
        assert cfg.retry_initial_delay == 1.0
        assert cfg.retry_max_delay == 10.0
        assert cfg.retry_exponential_base == 2

    def test_download_config_defaults(self):
        """测试 DownloadConfig 默认值"""
        cfg = DownloadConfig()
        assert cfg.concurrency == 5
        assert cfg.output_dir == "downloads"
        assert cfg.enable_zip is True
        assert cfg.filename_format == "{chapter_name}_{page_number}.jpg"

    def test_crawler_config_defaults(self):
        """测试 CrawlerConfig 默认值"""
        cfg = CrawlerConfig()
        assert cfg.user_agent != ""
        assert isinstance(cfg.browser_args, list)
        assert len(cfg.browser_args) > 0

    def test_sse_config_defaults(self):
        """测试 SSEConfig 默认值"""
        cfg = SSEConfig()
        assert cfg.heartbeat_interval == 2
        assert cfg.buffer_size == 100

    def test_history_config_defaults(self):
        """测试 HistoryConfig 默认值"""
        cfg = HistoryConfig()
        assert cfg.max_items == 100
        assert cfg.auto_cleanup_days == 0


class TestConfigManager:
    """ConfigManager 测试"""

    def test_validate_success(self, temp_dir):
        """测试有效配置验证"""
        manager = ConfigManager(config_path=str(temp_dir / "nonexistent.yaml"))
        manager.config = Config()

        errors = manager.validate()
        assert errors == []

    def test_validate_invalid_concurrency(self, temp_dir):
        """测试无效并发数验证"""
        manager = ConfigManager()
        manager.config.download.concurrency = 0

        errors = manager.validate()
        assert any("concurrency" in e for e in errors)

    def test_validate_invalid_timeout(self, temp_dir):
        """测试无效超时验证"""
        manager = ConfigManager()
        manager.config.network.timeout_connect = 0

        errors = manager.validate()
        assert any("timeout" in e for e in errors)

    def test_validate_invalid_retry_base(self, temp_dir):
        """测试无效重试基数验证"""
        manager = ConfigManager()
        manager.config.network.retry_exponential_base = 1

        errors = manager.validate()
        assert any("exponential_base" in e for e in errors)

    def test_validate_invalid_port(self, temp_dir):
        """测试无效端口验证"""
        manager = ConfigManager()
        manager.config.port = 70000

        errors = manager.validate()
        assert any("port" in e for e in errors)


class TestEnvironmentVariables:
    """环境变量覆盖测试"""

    def test_proxy_from_env(self, monkeypatch):
        """测试从环境变量加载代理"""
        monkeypatch.setenv("PROXY_URL", "http://localhost:8080")

        manager = ConfigManager(config_path="nonexistent.yaml")
        cfg = manager.load()

        assert cfg.network.proxy == "http://localhost:8080"

    def test_concurrency_from_env(self, monkeypatch):
        """测试从环境变量加载并发数"""
        monkeypatch.setenv("CONCURRENT_DOWNLOADS", "10")

        manager = ConfigManager(config_path="nonexistent.yaml")
        cfg = manager.load()

        assert cfg.download.concurrency == 10

    def test_timeout_from_env(self, monkeypatch):
        """测试从环境变量加载超时"""
        monkeypatch.setenv("REQUEST_TIMEOUT", "120")

        manager = ConfigManager(config_path="nonexistent.yaml")
        cfg = manager.load()

        assert cfg.network.timeout_read == 120

    def test_host_from_env(self, monkeypatch):
        """测试从环境变量加载主机"""
        monkeypatch.setenv("HOST", "127.0.0.1")

        manager = ConfigManager(config_path="nonexistent.yaml")
        cfg = manager.load()

        assert cfg.host == "127.0.0.1"

    def test_port_from_env(self, monkeypatch):
        """测试从环境变量加载端口"""
        monkeypatch.setenv("PORT", "9000")

        manager = ConfigManager(config_path="nonexistent.yaml")
        cfg = manager.load()

        assert cfg.port == 9000


class TestGetConfig:
    """get_config 函数测试"""

    def test_get_config_returns_config(self):
        """测试 get_config 返回 Config 实例"""
        cfg = get_config()
        assert isinstance(cfg, Config)
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8000

    def test_get_config_has_network_config(self):
        """测试 get_config 包含网络配置"""
        cfg = get_config()
        assert isinstance(cfg.network, NetworkConfig)

    def test_get_config_has_download_config(self):
        """测试 get_config 包含下载配置"""
        cfg = get_config()
        assert isinstance(cfg.download, DownloadConfig)

    def test_get_config_has_crawler_config(self):
        """测试 get_config 包含爬虫配置"""
        cfg = get_config()
        assert isinstance(cfg.crawler, CrawlerConfig)


class TestReloadConfig:
    """reload_config 函数测试"""

    def test_reload_config_return(self):
        """测试 reload_config 返回 Config 实例"""
        cfg = reload_config()
        assert isinstance(cfg, Config)
