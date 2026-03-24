"""FastAPI 应用装配辅助。"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def register_root_route(app: FastAPI) -> None:
    @app.get("/")
    async def root():
        return {
            "message": "漫画下载器 API",
            "version": "2.0",
            "description": "支持多平台漫画下载",
        }


def register_routes(
    app: FastAPI,
    *,
    platforms_router: Any,
    download_router_factory: Callable[[], Any],
    history_router_factory: Callable[[], Any],
    queue_router_factory: Callable[[], Any],
    search_router_factory: Callable[[], Any],
    parse_router_factory: Callable[[], Any],
    auth_router_factory: Callable[[], Any],
    resume_router_factory: Callable[[], Any],
) -> None:
    app.include_router(platforms_router)
    app.include_router(download_router_factory())
    app.include_router(history_router_factory())
    app.include_router(queue_router_factory())
    app.include_router(search_router_factory())
    app.include_router(parse_router_factory())
    app.include_router(auth_router_factory())
    app.include_router(resume_router_factory())
    register_root_route(app)


def register_lifecycle(
    app: FastAPI,
    *,
    on_startup: Callable[[], Any],
    on_shutdown: Callable[[], Any],
) -> None:
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def create_application(
    *,
    title: str,
    description: str,
    platforms_router: Any,
    download_router_factory: Callable[[], Any],
    history_router_factory: Callable[[], Any],
    queue_router_factory: Callable[[], Any],
    search_router_factory: Callable[[], Any],
    parse_router_factory: Callable[[], Any],
    auth_router_factory: Callable[[], Any],
    resume_router_factory: Callable[[], Any],
    on_startup: Callable[[], Any],
    on_shutdown: Callable[[], Any],
) -> FastAPI:
    app = FastAPI(title=title, description=description)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_routes(
        app,
        platforms_router=platforms_router,
        download_router_factory=download_router_factory,
        history_router_factory=history_router_factory,
        queue_router_factory=queue_router_factory,
        search_router_factory=search_router_factory,
        parse_router_factory=parse_router_factory,
        auth_router_factory=auth_router_factory,
        resume_router_factory=resume_router_factory,
    )
    register_lifecycle(app, on_startup=on_startup, on_shutdown=on_shutdown)
    return app
