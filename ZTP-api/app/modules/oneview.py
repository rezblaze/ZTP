import asyncio
import json
import logging
import os
from datetime import datetime

import httpx
import urllib3

from app.config import config
from app.modules.cache import CREDS, HPE_VARIABLES

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
settings = config.get_setting()


class OneViewAPI:
    def __init__(self, app, username="bmiapi", password=CREDS["satellite"]["bmiapi"]):
        self.adminlo_user = "AdminLO"
        self.adminlo_creds = CREDS["hpe"]["AdminLO"]
        self.base_url = f"https://{app}"
        self.username = username
        self.password = password
        self.session_id = None
        self.spp = HPE_VARIABLES.get("spp", {})
        self.current_baselines = {key: value for key, value in self.spp.items() if "Current" in key}
        logger.info(f"Current baselines: {self.current_baselines}")

    async def login(self):
        url = f"{self.base_url}/rest/login-sessions"
        payload = {"userName": self.username, "password": self.password}
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient(verify=CREDS["verify"]) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            self.session_id = response.json().get("sessionID")
            return self.session_id

    def get_headers(self):
        return {
            "auth": self.session_id,
            "Content-Type": "application/json",
            "X-Api-Version": "4600",
        }

    async def add_server(self, server_name):
        logger.info(f"Adding server '{server_name}' to OneView appliance '{self.base_url}'")
        if not self.session_id:
            await self.login()

        url = f"{self.base_url}/rest/server-hardware"
        headers = self.get_headers()
        payload = {
            "hostname": server_name,
            "username": self.adminlo_user,
            "password": self.adminlo_creds,
            "force": False,
            "licensingIntent": "OneView",
            "configurationState": "Monitored",
            "initialScopeUris": [],
        }

        async with httpx.AsyncClient(verify=CREDS["verify"]) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code not in [200, 202]:
                logger.error(
                    f"Failed to add server '{server_name}'. Status Code: {response.status_code}, Response: {response.text}"
                )
                response.raise_for_status()

            task_url = response.headers.get("Location")
            if task_url:
                while True:
                    task_response = await client.get(f"{self.base_url}{task_url}", headers=headers)
                    task_response.raise_for_status()
                    task_data = task_response.json()
                    task_state = task_data.get("taskState")
                    if task_state in ["Completed", "Error", "Terminated"]:
                        logger.info(f"Task completed with state: {task_state}")
                        if task_state != "Completed":
                            logger.error(f"Task failed. Details: {json.dumps(task_data, indent=4)}")
                            raise Exception(f"Task failed with state: {task_state}")
                        break
                    logger.info(f"Task in progress. Current state: {task_state}")
                    await asyncio.sleep(1)
                return "Server added to oneview and Task completed successfully"

    async def delete_server(self, server_name):
        if not self.session_id:
            await self.login()

        server = await self.search_server(server_name)
        if not server:
            logger.info(f"Server '{server_name}' not found. Cannot delete.")
            return None

        server_id = server.get("uuid")
        if not server_id:
            logger.info(server_id)
            logger.info(f"UUID not found for server '{server_name}'. Cannot delete.")
            return None

        url = f"{self.base_url}/rest/server-hardware/{server_id}"

        async with httpx.AsyncClient(verify=CREDS["verify"]) as client:
            response = await client.delete(url, headers=self.get_headers())
            response.raise_for_status()
            logger.info(f"Server hardware with ID '{server_id}' deleted successfully.")

            task_url = response.headers.get("Location")
            if task_url:
                while True:
                    task_response = await client.get(f"{self.base_url}{task_url}", headers=self.get_headers())
                    task_response.raise_for_status()
                    task_data = task_response.json()
                    task_state = task_data.get("taskState")
                    if task_state in ["Completed", "Error", "Terminated"]:
                        logger.info(f"Task completed with state: {task_state}")
                        if task_state != "Completed":
                            logger.error(f"Task failed. Details: {json.dumps(task_data, indent=4)}")
                            raise Exception(f"Task failed with state: {task_state}")
                        break
                    logger.info(f"Task in progress. Current state: {task_state}")
                    await asyncio.sleep(1)
            return "Server removed from oneview and Task completed successfully"

    async def search_server(self, server_name):
        if not self.session_id:
            await self.login()

        url = f"{self.base_url}/rest/server-hardware"
        members = []

        async with httpx.AsyncClient(verify=CREDS["verify"]) as client:
            while url:
                response = await client.get(url, headers=self.get_headers())
                response.raise_for_status()
                data = response.json()
                members.extend(data.get("members", []))
                url = f"{self.base_url}{data.get('nextPageUri')}" if data.get("nextPageUri") else None

        for member in members:
            if server_name in member.get("name", ""):
                logger.info(f"Server '{server_name}' found.")
                return member
        logger.info(f"Server '{server_name}' not found.")
        return None

    async def search_server_with_index(self, server_name):
        if not self.session_id:
            await self.login()

        url = f"{self.base_url}/rest/index/resources?query=name=/.*{server_name}.*/"

        async with httpx.AsyncClient(verify=CREDS["verify"]) as client:
            response = await client.get(url, headers=self.get_headers())
            response.raise_for_status()
            data = response.json()
            members = data.get("members", [])

        if len(members) > 1:
            logger.info(
                f"Multiple servers ({len(members)}) found with name containing '{server_name}'. Returning the first match."
            )
        logger.info(f"First server found with name containing '{server_name}' is {members[0]}:")
        logger.info(json.dumps(members, indent=4))
        return members[0]

    async def get_firmware_baselines(self):
        if not self.session_id:
            await self.login()

        url = f"{self.base_url}/rest/firmware-drivers"

        async with httpx.AsyncClient(verify=CREDS["verify"]) as client:
            response = await client.get(url, headers=self.get_headers())
            response.raise_for_status()
            firmware_drivers = response.json().get("members", [])

        logger.info(f"Total firmware baselines found: {len(firmware_drivers)}")
        for driver in firmware_drivers:
            logger.info(
                f"Resource ID: {driver.get('resourceId', 'N/A')}, UUID: {driver.get('uuid', 'N/A')}, Version: {driver.get('version', 'N/A')}, Release Date: {driver.get('releaseDate', 'N/A')}"
            )
        return firmware_drivers

    async def search_firmwarebundle_with_index(self, generation):
        if not self.session_id:
            await self.login()

        url = f"{self.base_url}/rest/index/resources?start=0&count=100&userQuery='{generation}Current'"

        async with httpx.AsyncClient(verify=CREDS["verify"]) as client:
            response = await client.get(url, headers=self.get_headers())
            response.raise_for_status()
            members = response.json().get("members", [])

        if len(members) > 1:
            logger.info(
                f"Multiple firmware bundles ({len(members)}) found for generation '{generation}'. Returning the first match."
            )
        bundle = members[0]
        bundle_name = bundle.get("attributes", "N/A").get("fwbaseline_resourceId", "N/A")
        logger.info(f"First firmware bundle found for generation '{generation}' is '{bundle_name}':")
        return bundle_name

    async def get_all_firmwarebundles(self):
        bundles = {}
        for gen in ["gen10", "gen11", "gen12"]:
            logger.info(f"Searching firmware bundle for generation: {gen}")
            bundles[gen] = await self.search_firmwarebundle_with_index(gen)
        return bundles

    async def get_firmware_compliance(self, server_uuid, firmware_baseline_id):
        if not self.session_id:
            await self.login()

        url = f"{self.base_url}/rest/server-hardware/firmware-compliance"
        payload = {
            "firmwareBaselineId": firmware_baseline_id,
            "serverUUID": server_uuid,
        }

        async with httpx.AsyncClient(verify=CREDS["verify"]) as client:
            response = await client.post(url, json=payload, headers=self.get_headers())
            response.raise_for_status()
            return response.json().get("componentMappingList", [])

    @staticmethod
    async def generate_html_report(server_name, ovappliance, firmware_baseline_id, components):
        # This method remains the same as it doesn't involve HTTP requests
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        html = f"""
        <h2>Server Name: {server_name}</h2>
        <h3>OneView Appliance: {ovappliance}</h3>
        <h3>Current Firmware Baseline Resource ID: {firmware_baseline_id}</h3>
        <h4>Report generated on: {timestamp}</h4>
        """
        fw_req = any(comp["componentFirmwareUpdateRequired"] for comp in components)
        if fw_req:
            html += "<h3 style='color: red;'>Firmware updates are required for some components.</h3>"
        else:
            html += "<h3 style='color: green;'>All components are up to date.</h3>"
        html += """
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif;">
            <thead>
            <tr style="background-color: #f2f2f2; text-align: left;">
                <th style="padding: 8px; border: 1px solid #ddd;">Component Location</th>
                <th style="padding: 8px; border: 1px solid #ddd;">Component Name</th>
                <th style="padding: 8px; border: 1px solid #ddd;">Component Type</th>
                <th style="padding: 8px; border: 1px solid #ddd;">Installed Version</th>
                <th style="padding: 8px; border: 1px solid #ddd;">Baseline Version</th>
                <th style="padding: 8px; border: 1px solid #ddd;">Update Required</th>
                <th style="padding: 8px; border: 1px solid #ddd;">Force Update Required</th>
                <th style="padding: 8px; border: 1px solid #ddd;">HPSUM Managed</th>
            </tr>
            </thead>
            <tbody>
        """
        for comp in components:
            row_style = "background-color: #ffcccc;" if comp["componentFirmwareUpdateRequired"] else ""
            html += f"""
            <tr style="{row_style}">
                <td>{comp['componentLocation']}</td>
                <td>{comp['componentName']}</td>
                <td>{comp['componentType']}</td>
                <td>{comp['installedVersion']}</td>
                <td>{comp['baselineVersion']}</td>
                <td>{comp['componentFirmwareUpdateRequired']}</td>
                <td>{comp['componentFirmwareUpdateRequiredWithForce']}</td>
                <td>{comp['hpsumManaged']}</td>
            </tr>
            """
        html += """
            </tbody>
        </table>
       """
        html += "<br><i>Detail Report generated by BMI API in connection with Oneview.</i>"
        return fw_req, html

    async def get_firmware_compliance_report(self, server_name):
        if not self.session_id:
            await self.login()

        server = await self.search_server(server_name)

        if not server:
            logger.info(f"Server '{server_name}' not found.")
            return None

        server_uuid = server.get("uuid")
        if not server_uuid:
            logger.info(f"UUID not found for server '{server_name}'.")
            return None

        generation = server.get("generation", "").lower()
        if not generation:
            logger.info(f"Generation not found for server '{server_name}'.")
            return None

        firmware_baseline_id = await self.search_firmwarebundle_with_index(generation)
        if not firmware_baseline_id:
            logger.info(f"Firmware baseline not found for generation '{generation}'.")
            return None

        components = await self.get_firmware_compliance(server_uuid, firmware_baseline_id)
        fw_req, html_report = await self.generate_html_report(
            server_name, self.base_url, firmware_baseline_id, components
        )

        report_dir = "/pub/reports/OneView" if os.path.exists("/pub/reports/OneView") else os.getcwd()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        report_filename = os.path.join(report_dir, f"{server_name}_fc_report_{timestamp}.html")

        with open(report_filename, "w") as file:
            file.write(html_report)
        logger.info(f"Firmware compliance report generated: {report_filename}")
        return {
            "Server_name": server_name,
            "OneviewAppliance": self.base_url,
            "FirmwareBaselineID": firmware_baseline_id,
            "FirmwareUpdateRequired": fw_req,
            "ReportFile": f"https://{settings.bmi_env}{report_filename}",
            "Details": components,
        }
