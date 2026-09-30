# -*- coding: utf-8 -*-

"""
hpe_storage.py -- HPE storage management module for RAID and disk operations
Provides comprehensive storage management functionality for HPE servers (Gen9-Gen12+)

USAGE EXAMPLES:
    from _session import create_requests_retry_session, delete_session
    from hpe_storage import (
        get_disk_info, get_disk_info_list, get_free_drives, get_existing_volumes,
        create_raid1_volume, delete_raid_volume, delete_all_raid_volumes,
        check_raid_creation_status
    )
    
    # Create session
    session = create_requests_retry_session(lom_ip, lom_user, lom_pass)
    generation = "gen11"
    
    # Get disk information (returns list of disk dicts)
    disks = get_disk_info(lom_ip, session, generation)
    root_disks, app_disks = get_disk_info_list(disks)
    
    # Get free drives available for RAID
    free_drives = get_free_drives(lom_ip, session, generation)
    
    # Get existing RAID volumes
    volumes = get_existing_volumes(lom_ip, session, generation)
    
    # Create RAID1 volume
    result = create_raid1_volume(lom_ip, session, generation, free_drives[:2])
    
    # Delete a RAID volume
    delete_result = delete_raid_volume(lom_ip, session, generation, 
                                       volume_endpoint=volumes[0]['Endpoint'])
    
    # Delete all RAID volumes
    delete_all_result = delete_all_raid_volumes(lom_ip, session, generation)
    
    # Cleanup
    delete_session(session)
"""

import copy
import json
import logging
import time
import warnings

import requests
import urllib3

# Suppress InsecureRequestWarning from urllib3 for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

try:
    # Try absolute import first (for running as module)
    from app.ZTP._common import if_resp_not_ok, log_my_msg
except ImportError:
    # Fall back to relative import (for running within ZTP directory)
    from ._common import if_resp_not_ok, log_my_msg

__author__ = "David Blasing, Chirag Patel"
__email__ = "support@example.com"

logger = logging.getLogger(__name__)


def safe_get_with_retry(session, url, max_retries=3):
    """Safely get a URL with retry logic"""
    for attempt in range(max_retries + 1):
        try:
            resp = session.get(url, timeout=30, stream=False)
            
            if resp.ok:
                # Add small delay between successful requests to reduce server load
                time.sleep(0.5)
                return resp
                
        except requests.exceptions.ConnectionError:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                raise
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                raise
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                raise
    
    return None


def safe_get_fast(session, url, timeout=10, max_retries=1):
    """Fast get with shorter timeout and fewer retries - for internal API calls"""
    for attempt in range(max_retries + 1):
        try:
            resp = session.get(url, timeout=timeout, stream=False)
            if resp.ok:
                return resp
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.RequestException):
            if attempt < max_retries:
                time.sleep(1)
            else:
                return None
    return None


def get_ctlr_ep_list(lom, session, generation):
    """Fn: get_ctlr_ep_list Get HPE disk controller endpoint list"""
    log_my_msg(f"Getting controller endpoints for {generation}")
    ctrl_ep_list = []
    
    if generation in ["gen11", "gen12"]:
        # Gen11+ uses /redfish/v1/Systems/1/Storage/ API
        url = "/redfish/v1/Systems/1/Storage/"
        log_my_msg(f"Fetching storage systems from: {url}")
        try:
            resp = safe_get_with_retry(session, f"https://{lom}{url}")
            if_resp_not_ok(resp)
            data = resp.json()
            
            # Get storage members (StorageID)
            if "Members" in data:
                log_my_msg(f"Found {len(data['Members'])} storage members")
                for member in data["Members"]:
                    storage_id = member["@odata.id"]
                    log_my_msg(f"Checking storage member: {storage_id}")
                    # Get storage details to check for Controllers property - use fast timeout
                    try:
                        storage_resp = safe_get_fast(session, f"https://{lom}{storage_id}", timeout=5, max_retries=0)
                        if storage_resp is None or not storage_resp.ok:
                            log_my_msg(f"Could not access storage member {storage_id}")
                            continue
                        storage_data = storage_resp.json()
                        
                        # Check if Controllers property exists
                        if "Controllers" in storage_data:
                            controllers_ref = storage_data["Controllers"]["@odata.id"]
                            log_my_msg(f"Found controllers reference: {controllers_ref}")
                            ctrl_ep_list.append(controllers_ref)
                        else:
                            log_my_msg(f"No Controllers property found in {storage_id}")
                        
                    except Exception as e:
                        log_my_msg(f"Error getting storage details for {storage_id}: {str(e)[:50]}")
                        continue
            else:
                log_my_msg("No Members found in storage response")
        except Exception as e:
            log_my_msg(f"Warning: Could not fetch storage endpoints for {generation}: {e}")
            # Return empty list instead of hanging
        return ctrl_ep_list
    else:
        # Gen10 and older use SmartStorage API
        url = "/redfish/v1/Systems/1/SmartStorage/"
        log_my_msg(f"Fetching SmartStorage from: {url}")
        try:
            resp = safe_get_with_retry(session, f"https://{lom}{url}")
            if_resp_not_ok(resp)
            if "gen1" in generation:
                data = resp.json().get("Links", {})
            else:
                data = resp.json().get("links", {})
            if len(data) > 0:
                for val in data.values():
                    if "gen1" in generation:
                        ctrl_ep_list.append(val["@odata.id"])
                    else:
                        ctrl_ep_list.append(val["href"])
        except Exception as e:
            log_my_msg(f"Warning: Could not fetch SmartStorage endpoints: {e}")
            # Return empty list instead of hanging
        return ctrl_ep_list


def get_ctrl_slot_ep(lom, session, generation):
    """Fn: get_ctrl_slot_ep Get HPE disk controller slot and endpoint list"""
    log_my_msg(f"Getting controller slot endpoints for {generation}")
    ctrl_slot_ep_list = []
    ctlr_ep = get_ctlr_ep_list(lom, session, generation)
    
    if len(ctlr_ep) > 0:
        log_my_msg(f"Processing {len(ctlr_ep)} controller endpoints")
        if generation in ["gen11", "gen12"]:
            # For gen11+, the controller endpoints are already direct paths to controllers
            for controller_ep in ctlr_ep:
                log_my_msg(f"Getting controller details from: {controller_ep}")
                try:
                    resp = safe_get_with_retry(session, f"https://{lom}{controller_ep}")
                    if_resp_not_ok(resp)
                    # Extract controller ID from the endpoint
                    ctrl_id = controller_ep.split("/")[-1]
                    log_my_msg(f"Found controller ID: {ctrl_id}")
                    ctrl_slot_ep_list.append((ctrl_id, controller_ep))
                except Exception as e:
                    log_my_msg(f"Error getting controller details for {controller_ep}: {e}")
                    continue
        else:
            # Gen10 and older logic
            for url in ctlr_ep:
                log_my_msg(f"Processing controller endpoint: {url}")
                resp = safe_get_with_retry(session, f"https://{lom}{url}")
                if_resp_not_ok(resp)
                mcount = resp.json().get("Members@odata.count", "0")
                if int(mcount) > 0 and "Array" in resp.json()["Description"]:
                    for x in resp.json()["Members"]:
                        ctrl_slot = x["@odata.id"].split("/")[-2]
                        ctrl_slot_ep_list.append((ctrl_slot, x["@odata.id"]))
        return ctrl_slot_ep_list
    else:
        return []


def get_disk_ep_list(lom, session, generation):
    """Fn: get_disk_ep_list Get HPE disk endpoint list"""
    if generation in ["gen11", "gen12"]:
        # For gen11+, get drives directly from Storage collection
        drive_ep_list = []
        try:
            url = "/redfish/v1/Systems/1/Storage/"
            resp = session.get(f"https://{lom}{url}")
            if_resp_not_ok(resp)
            data = resp.json()
            
            if "Members" in data:
                for member in data["Members"]:
                    storage_id = member["@odata.id"]
                    # Get storage details to get drives
                    try:
                        storage_resp = session.get(f"https://{lom}{storage_id}")
                        if_resp_not_ok(storage_resp)
                        storage_data = storage_resp.json()
                        
                        # Get drives directly from storage object
                        if "Drives" in storage_data:
                            for drive in storage_data["Drives"]:
                                drive_ep_list.append(drive["@odata.id"])
                                
                    except Exception as e:
                        log_my_msg(f"Error getting drives for {storage_id}: {e}")
                        continue
            return drive_ep_list
        except Exception as e:
            log_my_msg(f"Error getting gen11 drives: {e}")
            return []
    else:
        # Gen10 and older logic
        pd_ep = ""
        ep_list = get_ctrl_slot_ep(lom, session, generation)
        if len(ep_list) > 0:
            for _, ep in ep_list:
                resp = session.get(f"https://{lom}{ep}")
                if_resp_not_ok(resp)
                if "gen1" in generation:
                    pd_ep = resp.json()["Links"]["PhysicalDrives"]["@odata.id"]
                else:
                    pd_ep = resp.json()["links"]["PhysicalDrives"]["href"]
            return pd_ep
        else:
            return []


def get_pd_ep_list(lom, session, generation):
    """Fn: get_pd_ep_list Get HPE physical disk endpoint list"""
    if generation in ["gen11", "gen12"]:
        # For gen11+, get_disk_ep_list already returns the drive endpoints
        return get_disk_ep_list(lom, session, generation)
    else:
        # Gen10 and older logic
        my_list = []
        ep = get_disk_ep_list(lom, session, generation)
        if len(ep) > 0:
            resp = session.get(f"https://{lom}{ep}")
            if_resp_not_ok(resp)
            disk_ep_list = resp.json()["Members"]
            for index in range(len(disk_ep_list)):
                for key in disk_ep_list[index]:
                    my_list.append(disk_ep_list[index][key])
            return my_list
        else:
            return []


def get_disk_info(lom, session, generation):
    """Fn: get_disk_info Get HPE physical disk information"""
    tmp_disk_info_dict = {}
    disk_list = []
    ep_list = get_pd_ep_list(lom, session, generation)
    
    if len(ep_list) > 0:
        for i, ep in enumerate(ep_list):
            try:
                resp = safe_get_with_retry(session, f"https://{lom}{ep}")
                if_resp_not_ok(resp)
                disk_data = resp.json()
                
                if generation in ["gen11", "gen12"]:
                    # Gen11+ uses different attribute names
                    capacity_bytes = disk_data.get("CapacityBytes", 0)
                    capacity_gb = int(capacity_bytes / (1024**3)) if capacity_bytes else 0
                    
                    # Handle location - it can be complex in gen11
                    location = "Unknown"
                    if "PhysicalLocation" in disk_data:
                        loc_data = disk_data["PhysicalLocation"]
                        if "PartLocation" in loc_data and "ServiceLabel" in loc_data["PartLocation"]:
                            location = loc_data["PartLocation"]["ServiceLabel"]
                    
                    disk_info = {
                        "Id": disk_data.get("Id", f"Drive-{i+1}"),
                        "CapacityGB": capacity_gb,
                        "InterfaceType": disk_data.get("Protocol", "Unknown"),
                        "Location": location,
                        "MediaType": disk_data.get("MediaType", "Unknown"),
                        "Model": disk_data.get("Model", "Unknown")
                    }
                    disk_list.append(disk_info)
                else:
                    # Gen10 and older logic
                    disk_keys = ["Id", "CapacityGB", "InterfaceType", "Location", "MediaType"]
                    for x in disk_keys:
                        i = {x: disk_data[x]}
                        tmp_disk_info_dict.update(i)
                    disk_list.append(copy.deepcopy(tmp_disk_info_dict))
                    
            except Exception as e:
                log_my_msg(f"Error getting disk info for {ep}: {e}")
                # Continue with other drives
                continue
                
        return disk_list
    else:
        return []


def get_free_drives(lom, session, generation):
    """Get list of available/free drives that can be used for RAID creation"""
    free_drives = []
    
    try:
        # Get all drives and their endpoints
        disk_info = get_disk_info(lom, session, generation)
        drive_endpoints = get_pd_ep_list(lom, session, generation)
        
        log_my_msg(f"Checking {len(disk_info)} drives for availability")
        
        if generation in ["gen11", "gen12"]:
            # For gen11+, check each drive to see if it's assigned to a volume
            for i, drive in enumerate(disk_info):
                drive_id = drive["Id"]
                
                # Use the actual endpoint from the drive list
                if i < len(drive_endpoints):
                    drive_ep = drive_endpoints[i]
                else:
                    log_my_msg(f"No endpoint found for drive {drive_id}")
                    continue
                
                log_my_msg(f"Checking drive {drive_id} at endpoint: {drive_ep}")
                
                try:
                    resp = safe_get_with_retry(session, f"https://{lom}{drive_ep}")
                    if resp.ok:
                        drive_data = resp.json()
                        
                        # Check if drive is not assigned to any volume
                        # In gen11, free drives typically don't have Links to volumes
                        links = drive_data.get("Links", {})
                        volumes = links.get("Volumes", [])
                        
                        if not volumes or len(volumes) == 0:
                            log_my_msg(f"Drive {drive_id} is available (no volume assignments)")
                            drive["Status"] = "Available"
                            drive["Endpoint"] = drive_ep
                            free_drives.append(drive)
                        else:
                            log_my_msg(f"Drive {drive_id} is assigned to {len(volumes)} volume(s)")
                            drive["Status"] = "Assigned"
                            
                except Exception as e:
                    log_my_msg(f"Error checking drive {drive_id} status: {e}")
                    # If we can't check the status, assume it might be available
                    # This handles cases where the drive exists but volume info isn't accessible
                    log_my_msg(f"Assuming drive {drive_id} is available due to check failure")
                    drive["Status"] = "Unknown-Available"
                    drive["Endpoint"] = drive_ep
                    free_drives.append(drive)
                    continue
        else:
            # For gen10, check SmartStorage logic for free drives
            for drive in disk_info:
                # Add logic here for gen10 free drive detection
                drive["Status"] = "Unknown"
                free_drives.append(drive)  # Assume available for now
        
        # Filter drives for RAID1 criteria: same size, under 1TB, suitable type
        raid_suitable_drives = []
        for drive in free_drives:
            capacity_gb = drive.get("CapacityGB", 0)
            interface_type = drive.get("InterfaceType", "")
            media_type = drive.get("MediaType", "")
            
            # Check criteria: under 1TB (1024 GB) and suitable type
            if (capacity_gb > 0 and capacity_gb < 1024 and 
                interface_type in ["SATA", "SAS", "NVMe"] and 
                media_type in ["SSD", "HDD"]):
                raid_suitable_drives.append(drive)
                log_my_msg(f"Drive {drive['Id']} suitable for RAID: {capacity_gb}GB {interface_type} {media_type}")
            else:
                log_my_msg(f"Drive {drive['Id']} not suitable: {capacity_gb}GB {interface_type} {media_type}")
        
        # Group by size to find matching pairs
        size_groups = {}
        for drive in raid_suitable_drives:
            capacity = drive.get("CapacityGB", 0)
            if capacity not in size_groups:
                size_groups[capacity] = []
            size_groups[capacity].append(drive)
        
        # Find the largest group with at least 2 drives of same size
        best_drives = []
        for capacity, drives in size_groups.items():
            if len(drives) >= 2:
                log_my_msg(f"Found {len(drives)} drives of {capacity}GB - suitable for RAID1")
                best_drives = drives[:2]  # Take first 2 drives of this size
                break
        
        log_my_msg(f"Found {len(free_drives)} free/available drives, {len(best_drives)} suitable for RAID1")
        return best_drives
        
    except Exception as e:
        log_my_msg(f"Error getting free drives: {e}")
        return []


def get_existing_volumes(lom, session, generation):
    """Get list of existing RAID volumes"""
    volumes = []
    
    try:
        if generation in ["gen11", "gen12"]:
            # Get storage collection
            url = "/redfish/v1/Systems/1/Storage/"
            resp = session.get(f"https://{lom}{url}")
            if_resp_not_ok(resp)
            data = resp.json()
            
            if "Members" in data:
                for member in data["Members"]:
                    storage_id = member["@odata.id"]
                    # Get volumes for this storage
                    volumes_url = f"{storage_id}Volumes/"
                    try:
                        vol_resp = session.get(f"https://{lom}{volumes_url}")
                        if vol_resp.ok:
                            vol_data = vol_resp.json()
                            if "Members" in vol_data:
                                for volume in vol_data["Members"]:
                                    vol_details_resp = session.get(f"https://{lom}{volume['@odata.id']}")
                                    if vol_details_resp.ok:
                                        vol_info = vol_details_resp.json()
                                        volumes.append({
                                            "Id": vol_info.get("Id"),
                                            "Name": vol_info.get("Name"),
                                            "RAIDType": vol_info.get("RAIDType"),
                                            "CapacityBytes": vol_info.get("CapacityBytes"),
                                            "Status": vol_info.get("Status", {}).get("State"),
                                            "Endpoint": volume["@odata.id"]
                                        })
                    except Exception as e:
                        log_my_msg(f"Error getting volumes for {storage_id}: {e}")
                        continue
        
        log_my_msg(f"Found {len(volumes)} existing volumes")
        return volumes
        
    except Exception as e:
        log_my_msg(f"Error getting existing volumes: {e}")
        return []


def create_raid1_volume(lom, session, generation, drive_list, volume_name="RAID1_Volume"):
    """Create a RAID1 volume using the specified drives"""
    
    if len(drive_list) < 2:
        raise ValueError("RAID1 requires at least 2 drives")
    
    if generation != "gen11":
        raise ValueError("RAID1 creation currently only supported for gen11")
    
    try:
        # Get the storage controller ID from the first drive's endpoint
        if not drive_list or "Endpoint" not in drive_list[0]:
            raise ValueError("Drive endpoints not found in drive list")
        
        # Extract storage controller ID from drive endpoint
        # Example: /redfish/v1/Chassis/DE041000/Drives/0 -> DE041000
        first_endpoint = drive_list[0]["Endpoint"]
        if "/Chassis/" in first_endpoint:
            # Extract controller ID from chassis path
            controller_id = first_endpoint.split("/Chassis/")[1].split("/")[0]
            storage_path = f"/redfish/v1/Systems/1/Storage/{controller_id}"
        else:
            # Fallback: try to extract from Systems path
            controller_id = first_endpoint.split("/Storage/")[1].split("/")[0]
            storage_path = f"/redfish/v1/Systems/1/Storage/{controller_id}"
        
        log_my_msg(f"Using storage controller: {controller_id}")
        log_my_msg(f"Storage path: {storage_path}")
        
        # Prepare drive references for RAID creation
        # For HPE Gen11, we need to use the storage controller path, not chassis
        drive_refs = []
        for drive in drive_list[:2]:  # RAID1 uses exactly 2 drives
            # Convert chassis path to storage path if needed
            if "/Chassis/" in drive["Endpoint"]:
                # Convert /redfish/v1/Chassis/DE041000/Drives/0 to /redfish/v1/Systems/1/Storage/DE041000/Drives/0
                drive_id = drive["Endpoint"].split("/Drives/")[1]
                drive_ep = f"{storage_path}/Drives/{drive_id}"
            else:
                drive_ep = drive["Endpoint"]
            
            drive_refs.append({"@odata.id": drive_ep})
            log_my_msg(f"Adding drive to RAID: {drive_ep}")
        
        log_my_msg(f"Creating RAID1 volume with drives: {[d['Id'] for d in drive_list[:2]]}")
        
        # POST to create the volume - use the dynamic storage path
        volumes_url = f"https://{lom}{storage_path}/Volumes/"
        log_my_msg(f"Volumes URL: {volumes_url}")
        
        # Create RAID1 volume payload - try multiple payload formats based on HPE Gen11 iLO6 docs
        raid_payloads = [
            # Format 1: Official HPE Gen11 iLO6 format with CapacityBytes (from documentation)
            {
                "CapacityBytes": 440 * 1024 * 1024 * 1024,  # 440GB for RAID1 (~447GB drives)
                "DisplayName": "RAID1_BootVG",
                "RAIDType": "RAID1",
                "Links": {
                    "Drives": drive_refs
                }
            },
            # Format 2: Minimal HPE Gen11 format (from documentation)
            {
                "RAIDType": "RAID1",
                "Links": {
                    "Drives": drive_refs
                }
            },
            # Format 3: With Name instead of DisplayName
            {
                "CapacityBytes": 440 * 1024 * 1024 * 1024,
                "Name": "RAID1_BootVG", 
                "RAIDType": "RAID1",
                "Links": {
                    "Drives": drive_refs
                }
            },
            # Format 4: Legacy Redfish format (fallback)
            {
                "Name": volume_name,
                "RAIDType": "RAID1",
                "Links": {
                    "Drives": drive_refs
                }
            }
        ]
        
        # Try each payload format
        for i, raid_payload in enumerate(raid_payloads):
            log_my_msg(f"Trying RAID payload format {i+1}/4")
            log_my_msg(f"Payload: {json.dumps(raid_payload, indent=2)}")
            
            resp = session.post(volumes_url, json=raid_payload, timeout=60)
            
            log_my_msg(f"Response status: {resp.status_code}")
            log_my_msg(f"Response: {resp.text[:500]}")
            
            if resp.status_code in [200, 201, 202]:
                log_my_msg(f"RAID1 volume creation successful with format {i+1}")
                
                # Check for task or location header
                if "Location" in resp.headers:
                    task_url = resp.headers["Location"]
                    log_my_msg(f"RAID creation task: {task_url}")
                    return {"status": "success", "task": task_url, "format_used": i+1}
                else:
                    return {"status": "success", "response": resp.json(), "format_used": i+1}
            
            elif resp.status_code == 400:
                log_my_msg(f"Format {i+1} failed with HTTP 400 - trying next format")
                continue
            else:
                error_msg = f"Format {i+1} failed: HTTP {resp.status_code} - {resp.text}"
                log_my_msg(error_msg)
                continue
        
        # If all formats failed
        error_msg = f"All RAID1 creation formats failed. Last response: HTTP {resp.status_code} - {resp.text}"
        log_my_msg(error_msg)
        return {"status": "failed", "error": error_msg}
            
    except Exception as e:
        error_msg = f"Error creating RAID1 volume: {e}"
        log_my_msg(error_msg)
        return {"status": "error", "error": error_msg}


def delete_raid_volume(lom, session, generation, volume_endpoint=None, volume_id=None):
    """Delete a RAID volume by endpoint or ID"""
    
    if generation != "gen11":
        raise ValueError("RAID deletion currently only supported for gen11")
    
    try:
        # If volume_id provided, construct endpoint
        if volume_id and not volume_endpoint:
            volume_endpoint = f"/redfish/v1/Systems/1/Storage/DE07B000/Volumes/{volume_id}"
        
        if not volume_endpoint:
            raise ValueError("Either volume_endpoint or volume_id must be provided")
        
        log_my_msg(f"Deleting RAID volume: {volume_endpoint}")
        
        # DELETE request to remove the volume
        delete_url = f"https://{lom}{volume_endpoint}"
        resp = session.delete(delete_url, timeout=60)
        
        if resp.status_code in [200, 202, 204]:
            log_my_msg("RAID volume deletion initiated successfully")
            
            # Check for task or completion
            if "Location" in resp.headers:
                task_url = resp.headers["Location"]
                log_my_msg(f"RAID deletion task: {task_url}")
                return {"status": "success", "task": task_url}
            else:
                log_my_msg("RAID volume deleted immediately")
                return {"status": "success", "message": "RAID volume deleted"}
                
        else:
            error_msg = f"RAID deletion failed: HTTP {resp.status_code} - {resp.text}"
            log_my_msg(error_msg)
            return {"status": "failed", "error": error_msg}
            
    except Exception as e:
        error_msg = f"Error deleting RAID volume: {e}"
        log_my_msg(error_msg)
        return {"status": "error", "error": error_msg}


def delete_all_raid_volumes(lom, session, generation):
    """Delete all existing RAID volumes"""
    
    try:
        log_my_msg("Scanning for existing RAID volumes to delete...")
        existing_volumes = get_existing_volumes(lom, session, generation)
        
        if not existing_volumes:
            log_my_msg("No existing RAID volumes found to delete")
            return {"status": "success", "message": "No volumes to delete"}
        
        deletion_results = []
        
        for volume in existing_volumes:
            log_my_msg(f"Deleting volume: {volume['Name']} (ID: {volume['Id']}, Type: {volume['RAIDType']})")
            
            result = delete_raid_volume(lom, session, generation, volume_endpoint=volume['Endpoint'])
            deletion_results.append({
                "volume_name": volume['Name'],
                "volume_id": volume['Id'],
                "result": result
            })
            
            # Wait between deletions to avoid overwhelming the controller
            if result["status"] == "success":
                log_my_msg(f"Successfully initiated deletion of {volume['Name']}")
                time.sleep(5)  # Wait 5 seconds between deletions
            else:
                log_my_msg(f"Failed to delete {volume['Name']}: {result.get('error', 'Unknown error')}")
        
        success_count = sum(1 for r in deletion_results if r["result"]["status"] == "success")
        total_count = len(deletion_results)
        
        if success_count == total_count:
            return {"status": "success", "message": f"All {total_count} volumes deleted successfully", "details": deletion_results}
        else:
            return {"status": "partial", "message": f"{success_count}/{total_count} volumes deleted", "details": deletion_results}
            
    except Exception as e:
        error_msg = f"Error deleting RAID volumes: {e}"
        log_my_msg(error_msg)
        return {"status": "error", "error": error_msg}


def check_raid_creation_status(lom, session, task_url):
    """Check the status of RAID creation or deletion task"""
    try:
        resp = session.get(f"https://{lom}{task_url}")
        if resp.ok:
            task_data = resp.json()
            return {
                "task_state": task_data.get("TaskState"),
                "percent_complete": task_data.get("PercentComplete"),
                "messages": task_data.get("Messages", [])
            }
        else:
            return {"error": f"HTTP {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"error": str(e)}


def get_disk_info_list(disks):
    """fn: get_disk_info_list root disk list is [0], data disk list is [1]"""
    root_disk_list = []
    disk_list = []
    
    if len(disks) > 0:
        for i in disks:
            if int(i["CapacityGB"]) < 1000:
                root_disk_list.append(i)
            else:
                disk_list.append(i)
        return root_disk_list, disk_list
    return []
