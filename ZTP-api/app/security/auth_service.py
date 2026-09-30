# authenticate_and_get_connection function authenticates the user and returns the LDAP connection.
# The validate_and_get_username function then reuses this connection for the LDAP search.
# This way, the code only authenticates to LDAP once.

import logging

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from ldap3 import ALL, SIMPLE, Connection, Server

from app.config import config

security = HTTPBasic(auto_error=False)
settings = config.get_setting()
logger = logging.getLogger(__name__)


async def authenticate_and_get_connection(username, password):
    try:
        server = Server(settings.ldap_server, port=settings.ldap_port, use_ssl=True, get_info=ALL)
        conn = Connection(
            server,
            user=f"{username}@ms.ds.example.com",
            password=password,
            authentication=SIMPLE,
            auto_bind=True,
        )
        if conn.bound:
            return conn
        else:
            raise ldap3.core.exceptions.LDAPBindError(f"Connection to {settings.ldap_server} failed!")
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during authentication"
        )


async def validate_and_get_username(
    credentials: HTTPBasicCredentials = Security(security),
):
    # if settings.bmi_env not in ("prod", "stage"):
    #     logger.info(f"auth_service: skipping ldap auth for environment {settings.bmi_env}")
    #     return {
    #         "requestor_id": "",
    #         "requestor_mail": "",
    #     }

    if credentials is None:
        logger.warning(f"auth_service: no credentials were provided for environment {settings.bmi_env}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not Authorized, provide primary ms id credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    conn = await authenticate_and_get_connection(credentials.username, credentials.password)

    try:
        conn.search(
            settings.ldap_group_dn,
            "(sAMAccountName={})".format(credentials.username),
            attributes=["cn", "mail", "memberOf"],
        )
        if len(conn.entries) > 0:
            user = conn.entries[0]
            groups = [group.split(",")[0][3:] for group in user.memberOf.values]
            if "bmi_api_users" in groups:
                logger.info(f"{credentials.username} found in bmi_api_users group!")
                return {
                    "requestor_id": user.cn.value,
                    "requestor_mail": user.mail.value,
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"{credentials.username} does not have access to endpoint",
                    headers={"WWW-Authenticate": "Basic"},
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{credentials.username} does not have access to endpoint",
                headers={"WWW-Authenticate": "Basic"},
            )
    except Exception as e:
        logger.error(f"Error during LDAP search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during LDAP search, verify credentials and bmi_api_users group membership",
        )
