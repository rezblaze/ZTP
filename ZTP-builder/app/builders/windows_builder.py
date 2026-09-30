import base64
import logging

import requests
from ldap3 import ALL, SUBTREE, Connection, Server

import app.build_service.loran_service as loran_service
import app.builders.baseline_hpe as baseline_hpe
import app.ZTP as ZTP
from app.build_service.cache import CREDS, WINDOWS_BUILD

logger = logging.getLogger(__name__)


def run_windows_build(build):
    """Fn: run windows build"""
    hostname = build["build_details"]["host"]
    short_name = build["networkdata"]["SHORT_NAME"]
    check_delete_chef_node(short_name)
    domain = build["build_details"]["attributes"]["computerdomain"].lower()
    if not domain:
        logger.info("Domain is empty, skipping check_delete_ad_node.")
    else:
        check_delete_ad_node(short_name, domain)
    WINDOWS_BUILD["WinAdminPass"] = CREDS["win"]["WinAdminPass"]
    WINDOWS_BUILD["DomainUserPassword"] = CREDS["win"]["DomainUserPassword"]
    build["windows_build"] = WINDOWS_BUILD
    immutable_iso = ZTP.Immutable(build).make_windows_iso()
    logger.info(immutable_iso)
    if build.get("build_details").get("deploy_only") is True:
        logger.info("NOTE: deploy_only is True: Skipping ilo config, hardware prep steps")
    else:
        baseline_hpe.baseline_hpe_prep(build)
    server_action = ZTP.Actions(hostname)
    ztp_deploy_windows = server_action.ztp_deploy_windows(immutable_iso["immutable"])
    loran_service.update_loran_hostdata(hostname, ztp_deploy_windows)
    del server_action


def check_delete_chef_node(hostname):
    """Fn: check and delete chef node if exist"""
    url = "https://chefapi.example.com/app/chefapi/v1/chef_node_information/getnode"
    params = {"node_input": hostname, "chef_server": "auto"}
    token = CREDS["chef_token"]["token"]
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    response = requests.get(url, headers=headers, params=params)
    logger.info(url)
    if response.status_code == 200:
        data = response.json()
        if data["data"] == []:
            logger.info("Chef: The 'data' field is empty so assuming node did not exist")
            return
        else:
            logger.info("- backup and delete chef node")
            chef_server = response.json()["data"]
            server_dict = chef_server[0]
            params = {"nodes": server_dict["name"], "chef_server": server_dict["chef_server"]}
            url = "https://chefapi.example.com/app/chefapi/v1/chef_node_management/backup_and_delete"
            response = requests.post(url, headers=headers, params=params)
            if response.status_code == 200:
                logger.info(response.json())
            else:
                logger.warning(f"Request failed with status code {response.status_code}: {response.text}")
                raise Exception(f"Failed to delete chef node for {hostname}")
    else:
        logger.warning(f"Request failed with status code {response.status_code}: {response.text}")
        raise Exception(f"Failed to fetch chef node info for {hostname}")


def check_delete_ad_node(hostname, domain):
    """Fn: check and delete ad node if exist"""
    # Convert domain to LDAP distinguished name format
    domain_parts = domain.split(".")
    search_base = ",".join([f"DC={part}" for part in domain_parts])
    logger.info(f"- check and delete AD computer object for {hostname} in domain {domain}")
    logger.info(f"Searching in AD base: {search_base}")
    # AD connection settings
    ad_server = f"ldap://{domain}"
    username = "buildservice@ms.ds.example.com"  # or 'DOMAIN\\user'
    password = decode_base64(CREDS["win"]["DomainUserPassword"])
    computer_name = f"{hostname}$"  # AD computer objects end with $
    # Connect to AD
    server = Server(ad_server, get_info=ALL)
    conn = Connection(server, user=username, password=password, auto_bind=True, authentication="SIMPLE")
    # Search for the computer object
    search_filter = f"(&(objectClass=computer)(sAMAccountName={computer_name}))"
    conn.search(search_base, search_filter, search_scope=SUBTREE, attributes=["distinguishedName"])
    if conn.entries:
        dn = conn.entries[0].entry_dn
        logger.info(f"Found computer: {dn}")
        # Delete the object
        if conn.delete(dn):
            logger.info("Computer object deleted successfully.")
        else:
            logger.warning(f"Failed to delete: {conn.result}")
            raise Exception(f"Failed to delete AD computer object for {hostname}")
    else:
        logger.info(f"Computer not found in domain {domain}")
    conn.unbind()


def decode_base64(encoded_string):
    # Decode the Base64 string
    decoded_bytes = base64.b64decode(encoded_string)
    # Convert bytes to string
    decoded_string = decoded_bytes.decode("utf-8")
    return decoded_string
