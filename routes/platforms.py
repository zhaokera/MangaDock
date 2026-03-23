from fastapi import APIRouter

from services.platforms import list_auth_platforms, list_supported_platforms


router = APIRouter()


@router.get("/api/platforms")
async def list_platforms():
    """获取支持的平台列表"""
    return {"platforms": list_supported_platforms()}


@router.get("/api/auth/platforms")
async def auth_platforms():
    """获取支持认证的平台列表"""
    platforms = list_auth_platforms()
    return {"platforms": platforms, "total": len(platforms)}
