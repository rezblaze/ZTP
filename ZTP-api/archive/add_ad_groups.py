# import json
# import logging
# from typing import Dict, Optional

# import aiohttp
# from fastapi import FastAPI, HTTPException

# from app.modules._session import create_requests_retry_session, delete_session


# logger = logging.getLogger(__name__)

# app = FastAPI()


# async def get_current_config(session, host: str) -> Dict:
#     """Fetch the current Redfish AccountService configuration."""
#     host = host.replace('\n', '').replace('\r', '')
#     url = f"https://{host}/redfish/v1/AccountService/"
#     headers = {"Content-Type": "application/json"}

#     async with session.get(url, headers=headers, ssl=CREDS["verify"]) as response:
#         response_data = await response.json()
#         if response.status != 200:
#             return {
#                 "status": "ERROR",
#                 "status_detail": f"Failed to fetch current configuration. Status code: {response.status}, Response: {response_data}",
#                 "host": host,
#                 "requestor": "AdminLO",
#                 "metadata": {},
#             }
#         return response_data


# def build_new_payload(current_config: Dict, new_group: Dict) -> Dict:
#     """Build the payload for adding a new AD group."""
#     remote_role_mapping = current_config.get("ActiveDirectory", {}).get("RemoteRoleMapping", [])
#     remote_role_mapping.append(new_group)

#     return {"ActiveDirectory": {"RemoteRoleMapping": remote_role_mapping}}


# async def patch_new_payload(session, host: str, new_payload: Dict) -> Dict:
#     """Apply the new payload to update the AccountService."""
#     url = f"https://{host}/redfish/v1/AccountService/"
#     headers = {"Content-Type": "application/json"}

#     async with session.patch(url, headers=headers, data=json.dumps(new_payload), ssl=CREDS["verify"]) as patch_response:
#         response_data = await patch_response.json()
#         if patch_response.status == 200:
#             return {"status": "success", "message": "Active Directory groups updated successfully."}
#         return {
#             "status": "ERROR",
#             "status_detail": f"Failed to update Active Directory groups. Status code: {patch_response.status}, Response: {response_data}",
#             "host": host,
#             "requestor": "AdminLO",
#             "metadata": {},
#         }


# async def update_permissions(session, host: str, current_config: Dict) -> None:
#     """Update permissions for existing RemoteGroups."""
#     remote_role_mapping = current_config.get("ActiveDirectory", {}).get("RemoteRoleMapping", [])
#     headers = {"Content-Type": "application/json"}

#     for group in remote_role_mapping:
#         if "LocalRole" in group:
#             sanitized_group_localrole = group['LocalRole']
#             sanitized_group_localrole = sanitized_group_localrole.replace('\n', '').replace('\r', '')
#             role_url = f"https://{host}/redfish/v1/AccountService/Roles/{sanitized_group_localrole}"

#             async with session.get(role_url, headers=headers, ssl=CREDS["verify"]) as response:
#                 response_data = await response.json()
#                 if response.status == 200:
#                     role_details = response_data

#                     assigned_privileges_payload = {"AssignedPrivileges": role_details.get("AssignedPrivileges", [])}
#                     oem_privileges_payload = {"OemPrivileges": role_details.get("OemPrivileges", [])}

#                     # Apply AssignedPrivileges
#                     async with session.patch(
#                         role_url, headers=headers, data=json.dumps(assigned_privileges_payload), ssl=CREDS["verify"]
#                     ) as patch_response:
#                         logger.info(f"Updating AssignedPrivileges for {sanitized_group_localrole}: {patch_response.status}")

#                     # Apply OemPrivileges
#                     async with session.patch(
#                         role_url, headers=headers, data=json.dumps(oem_privileges_payload), ssl=CREDS["verify"]
#                     ) as patch_response:
#                         logger.info(f"Updating OemPrivileges for {sanitized_group_localrole}: {patch_response.status}")


# @app.post("/add_ad_groups")
# async def add_ad_groups(
#     host: str, new_group: Dict, username: Optional[str] = None, password: Optional[str] = None
# ,  ) -> Dict:
#     """
#     Add a new Active Directory group to the iLO AccountService and update permissions.

#     Args:
#         host: The hostname or IP address of the server.
#         new_group: The new group configuration to add (e.g., {"RemoteGroup": "...", "LocalRole": "..."}).
#         username: Optional username for authentication.
#         password: Optional password for authentication.

#     Returns:
#         Dict containing status and message.
#     """
#     try:
#         session = await create_requests_retry_session(host, username, password)
#         host = host.replace('\n', '').replace('\r', '')
#         try:
#             # Step 1: Fetch current configuration
#             current_config = await get_current_config(session, host)
#             if "status" in current_config and current_config["status"] == "ERROR":
#                 logger.error(f"Failed to fetch current configuration: {current_config['status_detail']}")
#                 raise HTTPException(status_code=400, detail=current_config["status_detail"])

#             # Check if the group already exists
#             remote_role_mapping = current_config.get("ActiveDirectory", {}).get("RemoteRoleMapping", [])
#             for group in remote_role_mapping:
#                 if group.get("RemoteGroup") == new_group.get("RemoteGroup"):
#                     logger.info(f"Group {new_group['RemoteGroup']} already exists for host {host}")
#                     return {"status": "success", "message": f"Group {new_group['RemoteGroup']} is already configured."}

#             # Step 2: Build new payload with the provided new_group
#             new_payload = build_new_payload(current_config, new_group)

#             # Step 3: Apply the new payload
#             patch_response = await patch_new_payload(session, host, new_payload)
#             if patch_response["status"] != "success":
#                 logger.error(f"Failed to update AD groups: {patch_response['status_detail']}")
#                 if "ArrayPropertyAlreadyExists" in patch_response["status_detail"]:
#                     return {"status": "success", "message": f"Group {new_group['RemoteGroup']} is already configured."}
#                 raise HTTPException(status_code=400, detail=patch_response["status_detail"])

#             # Step 4: Update permissions for existing groups
#             await update_permissions(session, host, current_config)

#             logger.info(f"Successfully added AD group {new_group['RemoteGroup']} for host {host}")
#             return {
#                 "status": "success",
#                 "message": "Active Directory group added and permissions updated successfully.",
#             }
#         finally:
#             await delete_session(session)

#     except aiohttp.ClientError as e:
#         logger.error(f"Request timed out: {e}")
#         return {
#             "status": "ERROR",
#             "status_detail": "Request timed out.",
#             "host": host,
#             "requestor": "AdminLO",
#             "metadata": {},
#         }
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         logger.exception(f"Error adding AD group for host {host}: {str(e)}")
#         return {
#             "status": "ERROR",
#             "status_detail": f"Internal server error: {str(e)}",
#             "host": host,
#             "requestor": "AdminLO",
#             "metadata": {},
#         }



# @router.patch(
#     "/iLO/AccountService/ADGroups/{lom_host}",
#     tags=["Bare Metal Operations"],
#     response_description="Add an Active Directory group to iLO AccountService",
# )
# async def add_ad_group(
#     lom_host: str,
#     response: Response,
#     new_group: Dict = Body(
#         ...,
#         example={
#             "RemoteGroup": "CN=APPWIN01_WellMed_T1_WinEng_USA,CN=Users,DC=ms,DC=ds,DC=example,DC=com",
#             "LocalRole": "Operator",
#         },
#     ),
#     username: Optional[str] = None,
#     password: Optional[str] = None,
# ):
#     data = await add_ad_groups(lom_host, new_group, username, password)
#     return data
