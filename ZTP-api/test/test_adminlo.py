import pytest
from unittest.mock import AsyncMock, patch
from app.modules.adminlo import AdminLOManager, Statuses, StatusResponse


@pytest.fixture
def adminlo_manager():
    return AdminLOManager()

@pytest.mark.asyncio
async def test_check_creds_success(adminlo_manager):
    hostname = "192.0.2.101"
    with patch.object(adminlo_manager, "_check_login", new=AsyncMock(return_value="pass")):
        response = await adminlo_manager.check_creds(hostname)
        assert response.status == Statuses.SUCCESS.value
        assert response.host == hostname
        assert response.requestor == adminlo_manager.adminlo_user

@pytest.mark.asyncio
async def test_check_creds_fail(adminlo_manager):
    hostname = "test-host"
    with patch.object(adminlo_manager, "_check_login", new=AsyncMock(return_value="fail")):
        response = await adminlo_manager.check_creds(hostname)
        assert response.status == Statuses.FAIL.value
        assert response.host == hostname
        assert response.requestor == adminlo_manager.adminlo_user

@pytest.mark.asyncio
async def test_check_creds_error(adminlo_manager):
    hostname = "test-host"
    with patch.object(adminlo_manager, "_check_login", new=AsyncMock(side_effect=Exception("Test Exception"))):
        response = await adminlo_manager.check_creds(hostname)
        assert response.status == Statuses.ERROR.value
        assert "Exception: Test Exception" in response.status_detail
        assert response.host == hostname
        assert response.requestor == adminlo_manager.adminlo_user

@pytest.mark.asyncio
async def test_patch_creds_success(adminlo_manager):
    lom = "test-lom"
    with patch("app.modules.adminlo.create_requests_retry_session", new=AsyncMock()), \
         patch.object(adminlo_manager, "_patch_adminlo_account", new=AsyncMock(return_value=StatusResponse(status=Statuses.SUCCESS.value))):
        response = await adminlo_manager.patch_creds(lom)
        assert response.status == Statuses.SUCCESS.value
        assert response.host == lom


@pytest.mark.asyncio
async def test_add_account_success(adminlo_manager):
    lom = "test-lom"
    with patch.object(adminlo_manager, "_add_adminlo_account", new=AsyncMock(return_value="pass")):
        response = await adminlo_manager.add_account(lom)
        assert response.status == Statuses.SUCCESS.value
        assert response.host == lom

@pytest.mark.asyncio
async def test_add_account_fail(adminlo_manager):
    lom = "test-lom"
    with patch.object(adminlo_manager, "_add_adminlo_account", new=AsyncMock(return_value="fail")):
        response = await adminlo_manager.add_account(lom)
        assert response.status == Statuses.FAIL.value
        assert response.host == lom

@pytest.mark.asyncio
async def test_add_account_error(adminlo_manager):
    lom = "test-lom"
    with patch.object(adminlo_manager, "_add_adminlo_account", new=AsyncMock(side_effect=Exception("Test Exception"))):
        response = await adminlo_manager.add_account(lom)
        assert response.status == Statuses.ERROR.value
        assert "Exception: Test Exception" in response.status_detail
        assert response.host == lom