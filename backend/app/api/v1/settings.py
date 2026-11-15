from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    EmailSettingsUpdate,
    EmailTestRequest,
    LLMConfigUpdate,
    LLMTestRequest,
    NetworkSettingsUpdate,
    NotificationPreferencesUpdate,
)
from app.application.email_service import EmailSettingsError, EmailSettingsService
from app.application.llm_provider_service import LLMProviderError, LLMProviderService
from app.application.network_settings_service import (
    NetworkSettingsError,
    NetworkSettingsService,
)
from app.application.notification_service import NotificationService
from app.db.session import get_session
from app.infrastructure.llm.client import LLMNotConfigured

router = APIRouter(prefix="/settings", tags=["settings"])


def _error(exc: LLMProviderError) -> HTTPException:
    status = 400
    if exc.code == "NOT_FOUND":
        status = 404
    elif exc.code == "SECRET_ERROR":
        status = 409
    return HTTPException(status_code=status, detail=f"{exc.code}: {exc.message}")


@router.get("/llm")
async def llm_status(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    try:
        return await LLMProviderService(session).status()
    except LLMProviderError as exc:
        raise _error(exc) from exc


@router.put("/llm")
async def save_llm_config(
    payload: LLMConfigUpdate, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    try:
        return await LLMProviderService(session).save(
            base_url=payload.base_url,
            model=payload.model,
            api_key=payload.api_key,
            clear_api_key=payload.clear_api_key,
        )
    except LLMProviderError as exc:
        raise _error(exc) from exc


@router.post("/llm/test")
async def test_llm_config(
    payload: LLMTestRequest | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    service = LLMProviderService(session)
    try:
        if payload is not None:
            # Test the current form values without persisting them.
            return await service.test_candidate(
                base_url=payload.base_url,
                model=payload.model,
                api_key=payload.api_key,
            )
        return await service.test()
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=503, detail=f"LLM_NOT_CONFIGURED: {exc}") from exc
    except LLMProviderError as exc:
        raise _error(exc) from exc


def _email_error(exc: EmailSettingsError) -> HTTPException:
    status = 400
    if exc.code == "NOT_FOUND":
        status = 404
    elif exc.code == "SECRET_ERROR":
        status = 409
    elif exc.code == "NOT_CONFIGURED":
        status = 503
    return HTTPException(status_code=status, detail=f"{exc.code}: {exc.message}")


@router.get("/email")
async def email_status(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    try:
        return await EmailSettingsService(session).status()
    except EmailSettingsError as exc:
        raise _email_error(exc) from exc


@router.put("/email")
async def save_email_config(
    payload: EmailSettingsUpdate, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    try:
        return await EmailSettingsService(session).save(
            host=payload.host,
            port=payload.port,
            from_address=payload.from_address,
            to_address=payload.to_address,
            from_name=payload.from_name,
            username=payload.username,
            password=payload.password,
            clear_password=payload.clear_password,
            use_tls=payload.use_tls,
            use_ssl=payload.use_ssl,
        )
    except EmailSettingsError as exc:
        raise _email_error(exc) from exc


@router.post("/email/test")
async def test_email_config(
    payload: EmailTestRequest | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    service = EmailSettingsService(session)
    try:
        if payload is not None and (payload.host or payload.from_address):
            if not payload.host or not payload.from_address:
                raise EmailSettingsError(
                    "VALIDATION", "host and from_address are required for a candidate test"
                )
            return await service.test_candidate(
                host=payload.host,
                port=payload.port or 587,
                from_address=payload.from_address,
                to_address=payload.to_address,
                from_name=payload.from_name,
                username=payload.username,
                password=payload.password,
                use_tls=True if payload.use_tls is None else payload.use_tls,
                use_ssl=False if payload.use_ssl is None else payload.use_ssl,
                recipient=payload.recipient,
            )
        return await service.test(recipient=payload.recipient if payload else None)
    except EmailSettingsError as exc:
        raise _email_error(exc) from exc


@router.get("/notifications")
async def notification_preferences(
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    return await NotificationService(session).preferences()


@router.put("/notifications")
async def save_notification_preferences(
    payload: NotificationPreferencesUpdate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    try:
        return await NotificationService(session).save_preferences(
            **payload.model_dump()
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _network_error(exc: NetworkSettingsError) -> HTTPException:
    status = 400
    if exc.code == "NOT_FOUND":
        status = 404
    return HTTPException(status_code=status, detail=f"{exc.code}: {exc.message}")


@router.get("/network")
async def network_status(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    try:
        return await NetworkSettingsService(session).status()
    except NetworkSettingsError as exc:
        raise _network_error(exc) from exc


@router.put("/network")
async def save_network_settings(
    payload: NetworkSettingsUpdate, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    try:
        return await NetworkSettingsService(session).save(
            enabled=payload.market_proxy_enabled,
            url=payload.market_proxy_url,
        )
    except NetworkSettingsError as exc:
        raise _network_error(exc) from exc
