import hashlib
import hmac
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_session
from app.schemas import LoginIn, RegisterIn, UserOut
from app.settings import settings

router = APIRouter(prefix="/auth")

COOKIE = "access_token"
TOKEN_TTL = timedelta(days=7)
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    _, salt, digest = stored.split("$")
    test = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
    return hmac.compare_digest(test.hex(), digest)


def _set_cookie(response: Response, user_id: int) -> None:
    token = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(UTC) + TOKEN_TTL},
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    # TODO(PRD): secure=True kalau nanti disajikan lewat HTTPS; sekarang localhost.
    response.set_cookie(
        COOKIE, token, httponly=True, samesite="lax", max_age=int(TOKEN_TTL.total_seconds())
    )


async def current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    access_token: Annotated[str | None, Cookie()] = None,
) -> User:
    if not access_token:
        raise HTTPException(401, "not authenticated")
    try:
        user_id = int(jwt.decode(access_token, settings.JWT_SECRET, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "invalid token") from None
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(401, "user not found")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
Session = Annotated[AsyncSession, Depends(get_session)]


def require_role(*roles: str) -> Callable[[User], Awaitable[User]]:
    async def check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(403, "forbidden")
        return user

    return check


@router.post("/register", status_code=201)
async def register(body: RegisterIn, response: Response, session: Session) -> UserOut:
    user = User(
        email=body.email.lower(), password_hash=hash_password(body.password), name=body.name
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        raise HTTPException(409, "email already registered") from None
    _set_cookie(response, user.id)
    return UserOut.model_validate(user, from_attributes=True)


@router.post("/login")
async def login(body: LoginIn, response: Response, session: Session) -> UserOut:
    user = await session.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "invalid email or password")
    _set_cookie(response, user.id)
    return UserOut.model_validate(user, from_attributes=True)


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    response.delete_cookie(COOKIE)


@router.get("/me")
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user, from_attributes=True)
