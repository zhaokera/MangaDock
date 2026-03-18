"""认证管理模块

提供平台登录、会话管理和认证支持功能。
"""

import os
import json
import asyncio
import time
import hashlib
import logging
import pickle
from typing import Optional, Dict, Any, Callable
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta

from .registry import get_crawler_by_platform

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """会话信息"""
    platform: str
    session_data: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 86400)
    user_id: Optional[str] = None
    user_name: Optional[str] = None

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        """检查会话是否过期"""
        if current_time is None:
            current_time = time.time()
        return current_time > self.expires_at

    def update_last_used(self):
        """更新最后使用时间"""
        self.last_used = time.time()

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'platform': self.platform,
            'session_data': self.session_data,
            'created_at': self.created_at,
            'last_used': self.last_used,
            'expires_at': self.expires_at,
            'user_id': self.user_id,
            'user_name': self.user_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SessionInfo':
        """从字典创建实例"""
        return cls(
            platform=data['platform'],
            session_data=data.get('session_data', {}),
            created_at=data.get('created_at', time.time()),
            last_used=data.get('last_used', time.time()),
            expires_at=data.get('expires_at', time.time() + 86400),
            user_id=data.get('user_id'),
            user_name=data.get('user_name'),
        )


class SessionManager:
    """会话管理器

    负责管理平台登录会话，包括创建、保存、加载和清理。
    """

    def __init__(self, session_dir: str = "sessions", session_expiry: int = 86400):
        self.session_dir = Path(session_dir)
        self.session_expiry = session_expiry
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: Dict[str, SessionInfo] = {}
        self._lock = asyncio.Lock()

    def _get_session_path(self, platform: str) -> Path:
        """获取会话文件路径"""
        safe_name = hashlib.md5(platform.encode()).hexdigest()[:8]
        return self.session_dir / f"{safe_name}_{platform}.json"

    async def load_session(self, platform: str) -> Optional[SessionInfo]:
        """加载会话"""
        async with self._lock:
            session_path = self._get_session_path(platform)
            if not session_path.exists():
                return None

            try:
                with open(session_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                session = SessionInfo.from_dict(data)
                if session.is_expired():
                    await self.remove_session(platform)
                    return None
                self._sessions[platform] = session
                return session
            except Exception as e:
                logger.error(f"加载会话失败 {platform}: {e}")
                return None

    async def save_session(self, session: SessionInfo):
        """保存会话"""
        async with self._lock:
            self._sessions[session.platform] = session
            session_path = self._get_session_path(session.platform)
            try:
                with open(session_path, 'w', encoding='utf-8') as f:
                    json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
                logger.info(f"会话已保存: {session.platform}")
            except Exception as e:
                logger.error(f"保存会话失败 {session.platform}: {e}")

    async def remove_session(self, platform: str) -> bool:
        """移除会话"""
        async with self._lock:
            if platform in self._sessions:
                del self._sessions[platform]
            session_path = self._get_session_path(platform)
            try:
                if session_path.exists():
                    session_path.unlink()
                return True
            except Exception as e:
                logger.error(f"移除会话失败 {platform}: {e}")
                return False

    async def cleanup_expired(self) -> int:
        """清理过期会话"""
        async with self._lock:
            current_time = time.time()
            expired = []
            for platform, session in self._sessions.items():
                if session.is_expired(current_time):
                    expired.append(platform)

            for platform in expired:
                await self.remove_session(platform)

            return len(expired)

    async def get_session(self, platform: str) -> Optional[SessionInfo]:
        """获取会话（从缓存或磁盘）"""
        async with self._lock:
            if platform in self._sessions:
                session = self._sessions[platform]
                if session.is_expired():
                    del self._sessions[platform]
                    return None
                session.update_last_used()
                return session
            return await self.load_session(platform)

    async def update_session(self, session: SessionInfo):
        """更新会话"""
        async with self._lock:
            self._sessions[session.platform] = session
            await self.save_session(session)


class AuthManager:
    """认证管理器

    提供统一的认证接口，管理所有平台的登录状态。
    """

    def __init__(self, session_dir: str = "sessions", session_expiry: int = 86400):
        self.session_manager = SessionManager(session_dir, session_expiry)
        self._login_callbacks: Dict[str, list] = {}
        self._logout_callbacks: Dict[str, list] = {}

    async def is_logged_in(self, platform: str) -> bool:
        """检查是否已登录"""
        session = await self.session_manager.get_session(platform)
        return session is not None

    async def get_user_info(self, platform: str) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        session = await self.session_manager.get_session(platform)
        if session:
            return {
                'user_id': session.user_id,
                'user_name': session.user_name,
                'platform': session.platform,
                'is_logged_in': True,
            }
        return None

    async def login(
        self,
        platform: str,
        credentials: Dict[str, str],
        browser_factory: Optional[Callable] = None
    ) -> bool:
        """
        登录平台

        Args:
            platform: 平台名称
            credentials: 登录凭据 (username, password等)
            browser_factory: 浏览器工厂函数，用于需要浏览器登录的平台

        Returns:
            bool: 登录是否成功
        """
        # get_crawler_by_platform 返回的是实例，不是类
        crawler = get_crawler_by_platform(platform)
        if crawler is None:
            logger.error(f"不支持的平台: {platform}")
            return False

        try:
            # 检查是否实现了login方法
            if not hasattr(crawler, 'login') or not callable(getattr(crawler, 'login')):
                logger.error(f"平台 {platform} 不支持登录")
                return False

            # 执行登录
            result = await crawler.login(credentials, browser_factory)
            if result:
                # 创建并保存会话
                session = SessionInfo(
                    platform=platform,
                    session_data={'logged_in': True},
                    user_id=credentials.get('user_id') or credentials.get('username'),
                    user_name=credentials.get('user_name') or credentials.get('username'),
                    expires_at=time.time() + self.session_manager.session_expiry,
                )
                await self.session_manager.save_session(session)

                # 触发登录回调
                await self._trigger_callbacks(platform, 'login', result)

                logger.info(f"登录成功: {platform}")
                return True
            else:
                logger.error(f"登录失败: {platform}")
                return False

        except Exception as e:
            logger.error(f"登录异常 {platform}: {e}", exc_info=True)
            return False
        finally:
            await crawler.close_browser()

    async def logout(self, platform: str) -> bool:
        """
        登出平台

        Args:
            platform: 平台名称

        Returns:
            bool: 登出是否成功
        """
        crawler = get_crawler_by_platform(platform)
        if crawler is None:
            logger.error(f"不支持的平台: {platform}")
            return False

        try:
            # 执行登出
            if hasattr(crawler, 'logout') and callable(getattr(crawler, 'logout')):
                await crawler.logout()

            # 移除会话
            result = await self.session_manager.remove_session(platform)

            # 触发登出回调
            await self._trigger_callbacks(platform, 'logout', True)

            logger.info(f"登出成功: {platform}")
            return result

        except Exception as e:
            logger.error(f"登出异常 {platform}: {e}")
            return False
        finally:
            await crawler.close_browser()

    async def _trigger_callbacks(self, platform: str, event: str, data: Any):
        """触发回调"""
        callbacks = self._login_callbacks.get(platform, []) if event == 'login' else self._logout_callbacks.get(platform, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(platform, data)
                else:
                    callback(platform, data)
            except Exception as e:
                logger.error(f"回调执行失败 {platform}.{event}: {e}")

    def on_login(self, platform: str, callback: Callable):
        """注册登录回调"""
        if platform not in self._login_callbacks:
            self._login_callbacks[platform] = []
        self._login_callbacks[platform].append(callback)

    def on_logout(self, platform: str, callback: Callable):
        """注册登出回调"""
        if platform not in self._logout_callbacks:
            self._logout_callbacks[platform] = []
        self._logout_callbacks[platform].append(callback)


# 全局认证管理器实例
_auth_manager: Optional[AuthManager] = None


def get_auth_manager(session_dir: Optional[str] = None, session_expiry: Optional[int] = None) -> AuthManager:
    """获取全局认证管理器实例"""
    global _auth_manager
    if _auth_manager is None:
        session_dir = session_dir or "sessions"
        session_expiry = session_expiry or 86400
        _auth_manager = AuthManager(session_dir, session_expiry)
    return _auth_manager


def reset_auth_manager():
    """重置全局认证管理器（主要用于测试）"""
    global _auth_manager
    _auth_manager = None
