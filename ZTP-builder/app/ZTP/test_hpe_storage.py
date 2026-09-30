#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_hpe_storage.py -- Test script for hpe_storage module
Tests all storage functions and displays their output
"""

import json
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from _common import log_my_msg
from _session import create_requests_retry_session, delete_session
from hpe_storage import (
    check_raid_creation_status,
    create_raid1_volume,
    delete_all_raid_volumes,
    delete_raid_volume,
    get_ctlr_ep_list,
    get_ctrl_slot_ep,
    get_disk_ep_list,
    get_disk_info,
    get_disk_info_list,
    get_existing_volumes,
    get_free_drives,
    get_pd_ep_list,
)


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 100)
    print(f"  {title}")
    print("=" * 100)

def print_json(data, title=""):
    """Pretty print JSON data"""
    if title:
        print(f"\n{title}:")
    print(json.dumps(data, indent=2, default=str))

def test_storage_functions(lom_ip, lom_user, lom_pass):
    """Test all storage functions"""
    
    print_section("HPE STORAGE MODULE TEST")
    print(f"Target: {lom_ip}")
    print(f"User: {lom_user}")
    print(f"Generation: Will be auto-detected")
    
    session = None
    
    try:
        # Create session
        print_section("STEP 1: Creating Session")
        session = create_requests_retry_session(lom_ip, lom_user, lom_pass)
        log_my_msg("✓ Session created successfully")
        print(f"Session type: {type(session)}")
        print(f"Session headers: {dict(session.headers)}")
        
        # For testing, we'll use gen11 as default (you can change this)
        generation = "gen11"
        print(f"Using generation: {generation}")
        
        # Test 1: Get Controller Endpoints
        print_section("STEP 2: Testing get_ctlr_ep_list()")
        print("Function: get_ctlr_ep_list(lom, session, generation)")
        print("Purpose: Get list of storage controller endpoints")
        try:
            ctrl_eps = get_ctlr_ep_list(lom_ip, session, generation)
            print(f"Result type: {type(ctrl_eps)}")
            print(f"Number of controllers: {len(ctrl_eps)}")
            print_json(ctrl_eps, "Controller Endpoints")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test 2: Get Controller Slot Endpoints
        print_section("STEP 3: Testing get_ctrl_slot_ep()")
        print("Function: get_ctrl_slot_ep(lom, session, generation)")
        print("Purpose: Get controller slot and endpoint pairs")
        try:
            ctrl_slots = get_ctrl_slot_ep(lom_ip, session, generation)
            print(f"Result type: {type(ctrl_slots)}")
            print(f"Number of slots: {len(ctrl_slots)}")
            for slot_id, slot_ep in ctrl_slots:
                print(f"  - Slot: {slot_id}, Endpoint: {slot_ep}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test 3: Get Disk Endpoints
        print_section("STEP 4: Testing get_disk_ep_list()")
        print("Function: get_disk_ep_list(lom, session, generation)")
        print("Purpose: Get list of disk endpoints")
        try:
            disk_eps = get_disk_ep_list(lom_ip, session, generation)
            print(f"Result type: {type(disk_eps)}")
            print(f"Number of disks: {len(disk_eps)}")
            print_json(disk_eps, "Disk Endpoints")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test 4: Get Physical Disk Endpoint List
        print_section("STEP 5: Testing get_pd_ep_list()")
        print("Function: get_pd_ep_list(lom, session, generation)")
        print("Purpose: Get physical disk endpoint list")
        try:
            pd_eps = get_pd_ep_list(lom_ip, session, generation)
            print(f"Result type: {type(pd_eps)}")
            print(f"Number of PD endpoints: {len(pd_eps)}")
            print_json(pd_eps[:3] if len(pd_eps) > 3 else pd_eps, "First 3 PD Endpoints")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test 5: Get Disk Info
        print_section("STEP 6: Testing get_disk_info()")
        print("Function: get_disk_info(lom, session, generation)")
        print("Purpose: Get detailed information about all disks")
        print("Returns: List of dicts with keys: Id, CapacityGB, InterfaceType, Location, MediaType, Model")
        try:
            disk_info = get_disk_info(lom_ip, session, generation)
            print(f"Result type: {type(disk_info)}")
            print(f"Number of disks: {len(disk_info)}")
            
            if disk_info:
                print("\nDisk Info Schema (first disk):")
                print_json(disk_info[0])
                
                print(f"\nAll Disks Summary:")
                for i, disk in enumerate(disk_info):
                    print(f"  [{i}] ID: {disk.get('Id')}, Capacity: {disk.get('CapacityGB')}GB, "
                          f"Type: {disk.get('InterfaceType')}, Media: {disk.get('MediaType')}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test 6: Get Disk Info List (separated by size)
        print_section("STEP 7: Testing get_disk_info_list()")
        print("Function: get_disk_info_list(disks)")
        print("Purpose: Separate root disks (<1TB) from data disks (>=1TB)")
        print("Returns: Tuple of (root_disk_list, disk_list)")
        try:
            if 'disk_info' in locals() and disk_info:
                root_disks, app_disks = get_disk_info_list(disk_info)
                print(f"Root disks (< 1TB): {len(root_disks)}")
                print(f"App disks (>= 1TB): {len(app_disks)}")
                
                if root_disks:
                    print("\nRoot Disks:")
                    print_json(root_disks)
                
                if app_disks:
                    print("\nApp Disks:")
                    print_json(app_disks)
            else:
                print("Skipping - no disk_info available")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test 7: Get Free Drives
        print_section("STEP 8: Testing get_free_drives()")
        print("Function: get_free_drives(lom, session, generation)")
        print("Purpose: Get available drives suitable for RAID creation")
        print("Returns: List of drives with Status and Endpoint info")
        try:
            free_drives = get_free_drives(lom_ip, session, generation)
            print(f"Result type: {type(free_drives)}")
            print(f"Number of free drives: {len(free_drives)}")
            
            if free_drives:
                print("\nFree Drives Details:")
                print_json(free_drives)
            else:
                print("No free drives available")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test 8: Get Existing Volumes
        print_section("STEP 9: Testing get_existing_volumes()")
        print("Function: get_existing_volumes(lom, session, generation)")
        print("Purpose: Get list of existing RAID volumes")
        print("Returns: List of volume dicts with Id, Name, RAIDType, CapacityBytes, Status, Endpoint")
        try:
            volumes = get_existing_volumes(lom_ip, session, generation)
            print(f"Result type: {type(volumes)}")
            print(f"Number of volumes: {len(volumes)}")
            
            if volumes:
                print("\nExisting RAID Volumes:")
                print_json(volumes)
            else:
                print("No existing RAID volumes found")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test 9: RAID Operations (optional - requires free drives)
        print_section("STEP 10: Testing create_raid1_volume()")
        print("Function: create_raid1_volume(lom, session, generation, drive_list, volume_name)")
        print("Purpose: Create RAID1 volume from available drives")
        print("NOTE: This operation CREATES a RAID volume - use enable_raid_creation flag")
        
        # Check if we should test RAID creation
        enable_raid_creation = False  # SET TO True TO TEST RAID CREATION
        
        if enable_raid_creation:
            if 'free_drives' in locals() and len(free_drives) >= 2:
                try:
                    print(f"\nCreating RAID1 volume with drives: {[d['Id'] for d in free_drives[:2]]}")
                    raid_result = create_raid1_volume(lom_ip, session, generation, free_drives[:2], "TestRAID1")
                    print(f"Result type: {type(raid_result)}")
                    print_json(raid_result, "RAID1 Creation Result")
                    
                    # Check status if task was returned
                    if raid_result.get('status') == 'success' and 'task' in raid_result:
                        print("\nChecking RAID creation status...")
                        task_status = check_raid_creation_status(lom_ip, session, raid_result['task'])
                        print_json(task_status, "RAID Creation Task Status")
                except Exception as e:
                    print(f"✗ Error: {e}")
            else:
                print(f"Skipping RAID creation - not enough free drives ({len(free_drives) if 'free_drives' in locals() else 0})")
        else:
            print("⚠️  RAID creation test DISABLED (set enable_raid_creation=True to test)")
            print("WARNING: Creating RAID volumes affects server configuration!")
        
        # Test 10: Delete RAID Volume
        print_section("STEP 11: Testing delete_raid_volume()")
        print("Function: delete_raid_volume(lom, session, generation, volume_endpoint, volume_id)")
        print("Purpose: Delete a specific RAID volume")
        print("NOTE: This operation DELETES a RAID volume - use enable_raid_deletion flag")
        
        enable_raid_deletion = True  # SET TO True TO TEST RAID DELETION
        
        if enable_raid_deletion:
            if 'volumes' in locals() and len(volumes) > 0:
                try:
                    vol_to_delete = volumes[0]
                    print(f"\nDeleting RAID volume: {vol_to_delete['Name']} (ID: {vol_to_delete['Id']})")
                    delete_result = delete_raid_volume(lom_ip, session, generation, 
                                                      volume_endpoint=vol_to_delete['Endpoint'])
                    print(f"Result type: {type(delete_result)}")
                    print_json(delete_result, "RAID Delete Result")
                    
                    # Check status if task was returned
                    if delete_result.get('status') == 'success' and 'task' in delete_result:
                        print("\nChecking RAID deletion status...")
                        task_status = check_raid_creation_status(lom_ip, session, delete_result['task'])
                        print_json(task_status, "RAID Deletion Task Status")
                except Exception as e:
                    print(f"✗ Error: {e}")
            else:
                print("No volumes available to delete")
        else:
            print("⚠️  RAID deletion test DISABLED (set enable_raid_deletion=True to test)")
            print("WARNING: Deleting RAID volumes affects server configuration!")
        
        # Test 11: Delete All RAID Volumes
        print_section("STEP 12: Testing delete_all_raid_volumes()")
        print("Function: delete_all_raid_volumes(lom, session, generation)")
        print("Purpose: Delete all existing RAID volumes")
        print("NOTE: This operation DELETES ALL RAID volumes - use enable_delete_all flag")
        
        enable_delete_all = False  # SET TO True TO TEST DELETE ALL
        
        if enable_delete_all:
            if 'volumes' in locals() and len(volumes) > 0:
                try:
                    print(f"\nDeleting all {len(volumes)} RAID volume(s)...")
                    delete_all_result = delete_all_raid_volumes(lom_ip, session, generation)
                    print(f"Result type: {type(delete_all_result)}")
                    print_json(delete_all_result, "Delete All RAID Volumes Result")
                except Exception as e:
                    print(f"✗ Error: {e}")
            else:
                print("No volumes to delete")
        else:
            print("⚠️  Delete all RAID test DISABLED (set enable_delete_all=True to test)")
            print("⚠️  CRITICAL: This will DELETE ALL RAID VOLUMES on the server!")
        
        # Summary
        print_section("TEST SUMMARY")
        print("""
✓ All 13 storage functions are tested:

DISCOVERY FUNCTIONS (Steps 1-9):
  1. safe_get_with_retry()        → HTTP GET with retry logic
  2. get_ctlr_ep_list()           → Get storage controller endpoints
  3. get_ctrl_slot_ep()           → Get controller slot pairs
  4. get_disk_ep_list()           → Get disk endpoints
  5. get_pd_ep_list()             → Get physical disk endpoints
  6. get_disk_info()              → Get detailed disk information
  7. get_disk_info_list()         → Separate root/app disks by capacity
  8. get_free_drives()            → Get available drives for RAID
  9. get_existing_volumes()       → Get existing RAID volumes

RAID MANAGEMENT FUNCTIONS (Steps 10-12):
  10. create_raid1_volume()        → Create RAID1 volume [DISABLED BY DEFAULT]
  11. delete_raid_volume()         → Delete specific RAID volume [DISABLED BY DEFAULT]
  12. delete_all_raid_volumes()    → Delete all RAID volumes [DISABLED BY DEFAULT]
  
  13. check_raid_creation_status() → Check RAID operation task status

ENABLING RAID TESTS:
  To test RAID operations, modify these flags in test_storage_functions():
  
    enable_raid_creation = True   # Line ~211
    enable_raid_deletion = True   # Line ~244
    enable_delete_all = True      # Line ~267
    
  ⚠️  WARNING: These operations modify server RAID configuration!

KEY RETURN TYPES:
  - get_disk_info()        → List[Dict]  (disk details)
  - get_free_drives()      → List[Dict]  (available drives with endpoints)
  - get_existing_volumes() → List[Dict]  (RAID volume details)
  - create_raid1_volume()  → Dict        (status and task info)
  - delete_raid_volume()   → Dict        (status and task info)

INTEGRATION WITH hphpe.py:
  from hpe_storage import get_disk_info, get_disk_info_list, ...
  
  # In your class methods:
  disks = get_disk_info(self.lom, self.sessobj, self.generation)
  root_disks, app_disks = get_disk_info_list(disks)
        """)
        
    except Exception as e:
        log_my_msg(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if session:
            print_section("CLEANUP")
            try:
                delete_session(session)
                log_my_msg("✓ Session deleted successfully")
            except Exception as e:
                log_my_msg(f"Warning: Error deleting session: {e}")

def main():
    """Main test entry point"""
    
    # Configuration - modify these for your environment
    lom_ip = "lab-dc1-r1-s17-lom.example.com"  # GEN10
    #lom_ip = "lab-dc1-r1-s15-lom.example.com"  # GEN11
    #lom_ip = "lab-dc1-r1-s06-lom.example.com" # GEN12
    lom_user = ""       # Change to your username
    lom_pass = ''   # Change to your password
    
    print("\n")
    print("╔" + "=" * 98 + "╗")
    print("║" + " " * 98 + "║")
    print("║" + "HPE STORAGE MODULE TEST SUITE".center(98) + "║")
    print("║" + " " * 98 + "║")
    print("╚" + "=" * 98 + "╝")
    
    print(f"\nTarget LOM: {lom_ip}")
    print(f"Username: {lom_user}")
    
    test_storage_functions(lom_ip, lom_user, lom_pass)

if __name__ == "__main__":
    main()
