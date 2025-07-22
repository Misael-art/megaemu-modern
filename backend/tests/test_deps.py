import pytest
from fastapi import Depends, HTTPException, status
from app.core.deps import get_current_active_admin, get_user_with_role
from app.models.user import User, UserRole

@pytest.mark.asyncio
async def test_get_current_active_admin(active_admin_user: User):
    user = await get_current_active_admin(current_user=active_admin_user)
    assert user == active_admin_user
    assert user.is_admin

@pytest.mark.asyncio
async def test_get_current_active_admin_non_admin(inactive_user: User):
    with pytest.raises(HTTPException) as exc:
        await get_current_active_admin(current_user=inactive_user)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_get_user_with_role(active_user: User):
    required_roles = [UserRole.USER]
    user = await get_user_with_role(required_roles)(current_user=active_user)
    assert user == active_user

@pytest.mark.asyncio
async def test_get_user_with_role_unauthorized(active_user: User):
    required_roles = [UserRole.ADMIN]
    with pytest.raises(HTTPException) as exc:
        await get_user_with_role(required_roles)(current_user=active_user)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN