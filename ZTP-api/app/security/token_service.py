import logging
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, OAuth2PasswordBearer

from app.config import config

security = HTTPBasic(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
settings = config.get_setting()

logger = logging.getLogger(__name__)

CHAVI_FOR_TOKEN = "BMIAPIUSERS"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 12 * 60  ## 12 hours


def create_access_token(data: dict) -> str:
    try:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, CHAVI_FOR_TOKEN, algorithm=ALGORITHM)
        logger.info(f"Token created successfully for user: {data['sub']}")
    except Exception as err:
        logger.error(f"Error creating token: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return encoded_jwt


async def validate_access_token(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        exp_time = payload.get("exp")
        token_expiry_time = datetime.utcfromtimestamp(exp_time)
        logger.info(f"username: {username} validated successfully, Token expiry time: {token_expiry_time}")
    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as err:
        logger.error(f"JWT Error: {err}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT Error: {err}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"username": username, "exp": token_expiry_time}
