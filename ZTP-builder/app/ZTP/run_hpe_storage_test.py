#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_hpe_storage_test.py -- Interactive test runner for HPE storage operations

This script provides a menu-driven interface to:
1. Run pre-boot checklist (PXE boot, power on, POST wait, disk discovery)
2. Test individual storage functions
3. Test RAID operations
4. Test all servers across generations

The pre-boot checklist is recommended before running storage tests.
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Setup Python path to handle imports whether run from ZTP dir or project root
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent.parent  # Go up to project root
app_dir = project_root / "app"

# Add paths in order of preference
if app_dir not in sys.path:
    sys.path.insert(0, str(app_dir))
if current_dir not in sys.path:
    sys.path.insert(0, str(current_dir))

# Now import - try app.ZTP first (when run from project root), then local (when run from ZTP dir)
try:
    from ZTP.hphpe import HpHpeServer
except ImportError:
    try:
        from hphpe import HpHpeServer
    except ImportError as e:
        raise ImportError(f"Failed to import HpHpeServer: {e}") from e

try:
    from ZTP.hpe_storage import (
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
except ImportError:
    try:
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
    except ImportError as e:
        raise ImportError(f"Failed to import hpe_storage functions: {e}") from e

try:
    from ZTP._common import log_my_msg
except ImportError:
    try:
        from _common import log_my_msg
    except ImportError as e:
        raise ImportError(f"Failed to import _common: {e}") from e

try:
    from ZTP._session import delete_session
except ImportError:
    try:
        from _session import delete_session
    except ImportError as e:
        raise ImportError(f"Failed to import _session: {e}") from e


# Predefined server configurations
SERVERS = {
    "gen10": {
        "name": "Gen10",
        "ip": "lab-dc1-r1-s17-lom.example.com",
        "user": "AdminLO",
        "pass": ''
    },
    "gen11": {
        "name": "Gen11",
        "ip": "lab-dc1-r1-s15-lom.example.com",
        "user": "AdminLO",
        "pass": ''
    },
    "gen12": {
        "name": "Gen12",
        "ip": "lab-dc1-r1-s06-lom.example.com",
        "user": "AdminLO",
        "pass": ''
    }
}


def print_section(title: str) -> None:
    """Print a formatted section header"""
    print("\n" + "=" * 100)
    print(f"  {title}")
    print("=" * 100)


def print_menu() -> None:
    """Print main menu"""
    print("\n" + "=" * 100)
    print("  HPE STORAGE TEST RUNNER - MAIN MENU".center(100))
    print("=" * 100)
    print("""
  1. Run pre-boot checklist (SET PXE BOOT -> POWER ON -> WAIT FOR POST -> DISK CHECK)
  2. Test individual storage discovery functions
  3. Test RAID operations (CREATE, DELETE, LIST)
  4. Run full storage test suite
  5. Custom server connection
  0. Exit
    """)


def print_storage_menu() -> None:
    """Print storage functions menu"""
    print("\n" + "=" * 100)
    print("  STORAGE DISCOVERY FUNCTIONS".center(100))
    print("=" * 100)
    print("""
  1. get_ctlr_ep_list()      - Get storage controller endpoints
  2. get_ctrl_slot_ep()      - Get controller slot pairs
  3. get_disk_ep_list()      - Get disk endpoints
  4. get_pd_ep_list()        - Get physical disk endpoints
  5. get_disk_info()         - Get detailed disk information
  6. get_disk_info_list()    - Separate root/app disks by capacity
  7. get_free_drives()       - Get available drives for RAID
  8. get_existing_volumes()  - Get existing RAID volumes
  9. Run all above tests
  0. Back to main menu
    """)


def print_raid_menu() -> None:
    """Print RAID operations menu"""
    print("\n" + "=" * 100)
    print("  RAID OPERATIONS".center(100))
    print("=" * 100)
    print("""
  ⚠️  WARNING: These operations MODIFY server RAID configuration!
  
  1. create_raid1_volume()    - Create RAID1 volume [DISABLED BY DEFAULT]
  2. delete_raid_volume()     - Delete specific RAID volume [DISABLED BY DEFAULT]
  3. delete_all_raid_volumes() - Delete all RAID volumes [DISABLED BY DEFAULT]
  4. check_raid_creation_status() - Check RAID operation task status
  5. Run all RAID tests
  0. Back to main menu
  
  To enable RAID write operations, modify enable_raid_write flag in code.
    """)


def connect_to_server(ip: str, user: str, passwd: str) -> Optional[HpHpeServer]:
    """Connect to a server and return HpHpeServer instance"""
    print_section(f"Connecting to {ip}")
    
    try:
        server = HpHpeServer(ip, user, passwd)
        log_my_msg(f"✓ Connected to {server.model} ({server.generation})")
        return server
    except Exception as e:
        log_my_msg(f"✗ Connection failed: {e}")
        return None


def test_discovery_functions(server: HpHpeServer, test_num: Optional[int] = None) -> None:
    """Test storage discovery functions"""
    
    if test_num is None:
        print_storage_menu()
        test_num = int(input("Select function (1-9): ").strip()) or 9
    
    tests = {
        1: ("get_ctlr_ep_list", lambda: get_ctlr_ep_list(server.lom, server.sessobj, server.generation)),
        2: ("get_ctrl_slot_ep", lambda: get_ctrl_slot_ep(server.lom, server.sessobj, server.generation)),
        3: ("get_disk_ep_list", lambda: get_disk_ep_list(server.lom, server.sessobj, server.generation)),
        4: ("get_pd_ep_list", lambda: get_pd_ep_list(server.lom, server.sessobj, server.generation)),
        5: ("get_disk_info", lambda: get_disk_info(server.lom, server.sessobj, server.generation)),
        6: ("get_disk_info_list", lambda: get_disk_info_list(get_disk_info(server.lom, server.sessobj, server.generation))),
        7: ("get_free_drives", lambda: get_free_drives(server.lom, server.sessobj, server.generation)),
        8: ("get_existing_volumes", lambda: get_existing_volumes(server.lom, server.sessobj, server.generation)),
    }
    
    if test_num == 9:
        # Run all tests
        print_section("Running All Discovery Tests")
        for test_id, (name, func) in tests.items():
            print(f"\n[{test_id}] Testing {name}()...")
            try:
                result = func()
                if isinstance(result, list):
                    log_my_msg(f"  ✓ Success: {len(result)} items")
                elif isinstance(result, tuple):
                    log_my_msg(f"  ✓ Success: {len(result)} items")
                else:
                    log_my_msg(f"  ✓ Success: {type(result).__name__}")
            except Exception as e:
                log_my_msg(f"  ✗ Failed: {e}")
    elif test_num in tests:
        name, func = tests[test_num]
        print_section(f"Testing {name}()")
        
        try:
            result = func()
            log_my_msg(f"✓ Function executed successfully")
            
            if isinstance(result, list):
                log_my_msg(f"  Result type: list with {len(result)} items")
                if result and isinstance(result[0], dict):
                    log_my_msg(f"  First item keys: {list(result[0].keys())}")
                    log_my_msg(f"  Sample: {result[0]}")
            elif isinstance(result, tuple):
                log_my_msg(f"  Result type: tuple with {len(result)} items")
            else:
                log_my_msg(f"  Result: {result}")
        except Exception as e:
            log_my_msg(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()


def test_raid_operations(server: HpHpeServer, test_num: Optional[int] = None) -> None:
    """Test RAID operations (with safety checks)"""
    
    enable_raid_write = False  # Set to True to enable RAID write operations
    
    if test_num is None:
        print_raid_menu()
        test_num = int(input("Select function (1-5): ").strip()) or 5
    
    print_section("RAID Operations Test")
    
    # First, get current volumes and free drives
    log_my_msg("Fetching current RAID volumes and free drives...")
    
    try:
        volumes = get_existing_volumes(server.lom, server.sessobj, server.generation)
        log_my_msg(f"  Current volumes: {len(volumes)}")
        
        free_drives = get_free_drives(server.lom, server.sessobj, server.generation)
        log_my_msg(f"  Free drives: {len(free_drives)}")
    except Exception as e:
        log_my_msg(f"✗ Error fetching volumes/drives: {e}")
        return
    
    # Run selected tests
    if test_num == 1:
        # Create RAID1 Volume
        print_section("Test 1: create_raid1_volume()")
        
        if not enable_raid_write:
            log_my_msg("⚠️  RAID creation DISABLED (set enable_raid_write=True to enable)")
            log_my_msg("   WARNING: This will CREATE a RAID volume!")
            return
        
        if len(free_drives) < 2:
            log_my_msg(f"✗ Not enough free drives for RAID1 (need 2, have {len(free_drives)})")
            return
        
        log_my_msg(f"Creating RAID1 with drives: {[d.get('Id') for d in free_drives[:2]]}")
        try:
            result = create_raid1_volume(server.lom, server.sessobj, server.generation, free_drives[:2], "TestRAID1")
            log_my_msg(f"✓ RAID creation initiated: {result}")
        except Exception as e:
            log_my_msg(f"✗ Error: {e}")
    
    elif test_num == 2:
        # Delete specific volume
        print_section("Test 2: delete_raid_volume()")
        
        if not enable_raid_write:
            log_my_msg("⚠️  RAID deletion DISABLED (set enable_raid_write=True to enable)")
            log_my_msg("   WARNING: This will DELETE a RAID volume!")
            return
        
        if not volumes:
            log_my_msg("✗ No volumes available to delete")
            return
        
        volume = volumes[0]
        log_my_msg(f"Deleting volume: {volume.get('Name')} ({volume.get('Id')})")
        try:
            result = delete_raid_volume(server.lom, server.sessobj, server.generation, 
                                       volume_endpoint=volume.get('Endpoint'))
            log_my_msg(f"✓ RAID deletion initiated: {result}")
        except Exception as e:
            log_my_msg(f"✗ Error: {e}")
    
    elif test_num == 3:
        # Delete all volumes
        print_section("Test 3: delete_all_raid_volumes()")
        
        if not enable_raid_write:
            log_my_msg("⚠️  Delete all DISABLED (set enable_raid_write=True to enable)")
            log_my_msg("   🔴 CRITICAL WARNING: This will DELETE ALL RAID VOLUMES!")
            return
        
        if not volumes:
            log_my_msg("✗ No volumes available to delete")
            return
        
        log_my_msg(f"⚠️  About to delete ALL {len(volumes)} volume(s)!")
        confirm = input("Type 'DELETE ALL' to confirm: ").strip()
        
        if confirm == "DELETE ALL":
            try:
                result = delete_all_raid_volumes(server.lom, server.sessobj, server.generation)
                log_my_msg(f"✓ Delete all initiated: {result}")
            except Exception as e:
                log_my_msg(f"✗ Error: {e}")
        else:
            log_my_msg("Cancelled")
    
    elif test_num == 4:
        # Check RAID task status
        print_section("Test 4: check_raid_creation_status()")
        
        task_uri = input("Enter task URI: ").strip()
        if task_uri:
            try:
                result = check_raid_creation_status(server.lom, server.sessobj, task_uri)
                log_my_msg(f"✓ Task status: {result}")
            except Exception as e:
                log_my_msg(f"✗ Error: {e}")
        else:
            log_my_msg("No task URI provided")
    
    elif test_num == 5:
        # Run all RAID tests (read-only)
        print_section("Test 5: All RAID Tests (Read-Only)")
        
        log_my_msg(f"Volumes: {len(volumes)}")
        log_my_msg(f"Free drives: {len(free_drives)}")
        
        if volumes:
            log_my_msg("\nExisting volumes:")
            for vol in volumes:
                log_my_msg(f"  - {vol.get('Name')}: {vol.get('RAIDType')}")
        
        if free_drives:
            log_my_msg("\nFree drives:")
            for drive in free_drives:
                log_my_msg(f"  - {drive.get('Id')}: {drive.get('Status')}")


def run_pre_boot_checklist(server: HpHpeServer) -> bool:
    """
    Run the complete pre-boot checklist
    
    Steps:
    1. Set one-time PXE boot
    2. Power on server
    3. Wait for POST completion
    4. Run disk checks
    """
    print_section("PRE-BOOT CHECKLIST")
    
    all_passed = True
    
    try:
        # Step 1: Check if PXE boot needed (skip if already booted)
        print("\n[1/4] Checking if PXE boot needed...")
        try:
            post_state = server.get_post_status()
            log_my_msg(f"  Current POST state: {post_state}")
            
            if post_state in ["FinishedPost", "InPostDiscoveryComplete"]:
                log_my_msg("  Server already booted, skipping PXE boot")
            else:
                print("  Setting one-time PXE boot...")
                try:
                    result = server.set_one_time_pxe_boot()
                    log_my_msg(f"  ✓ PXE boot configured: {result}")
                except Exception as e:
                    log_my_msg(f"  ✗ Error: {e}")
                    all_passed = False
        except Exception as e:
            log_my_msg("  ⚠ Could not check POST status, attempting PXE boot anyway...")
            try:
                result = server.set_one_time_pxe_boot()
                log_my_msg(f"  ✓ PXE boot configured: {result}")
            except Exception as e2:
                log_my_msg(f"  ✗ Error: {e2}")
                all_passed = False
        
        # Step 2: Power on server
        print("[2/4] Powering on server...")
        try:
            power_state = server.get_power_status()
            log_my_msg(f"  Current power state: {power_state}")
            
            if power_state != "on":
                result = server.set_power_on()
                log_my_msg(f"  ✓ Power on command sent")
                time.sleep(5)
            else:
                log_my_msg(f"  Server already powered on")
        except Exception as e:
            log_my_msg(f"  ✗ Error: {e}")
            all_passed = False
        
        # Step 3: Wait for POST
        print("[3/4] Waiting for server to complete POST...")
        start_time = time.time()
        post_state = ""
        timeout = 600  # 10 minutes
        post_complete_states = ["FinishedPost", "InPostDiscoveryComplete"]
        
        try:
            while post_state not in post_complete_states:
                post_state = server.get_post_status()
                log_my_msg(f"  POST state: {post_state}")
                
                if post_state in post_complete_states:
                    break
                
                if time.time() - start_time > timeout:
                    log_my_msg(f"  ✗ POST timeout after 10 minutes")
                    all_passed = False
                    break
                
                time.sleep(10)
            
            if post_state in post_complete_states:
                log_my_msg(f"  ✓ POST completed successfully (state: {post_state})")
        except Exception as e:  # noqa: BLE001
            log_my_msg(f"  ✗ Error: {e}")
            all_passed = False
        
        # Step 4: Run disk checks
        print("[4/4] Running disk discovery checks...")
        try:
            disk_info = get_disk_info(server.lom, server.sessobj, server.generation)
            log_my_msg(f"  ✓ Found {len(disk_info)} disks")
            
            controllers = get_ctlr_ep_list(server.lom, server.sessobj, server.generation)
            log_my_msg(f"  ✓ Found {len(controllers)} controllers")
            
            free_drives = get_free_drives(server.lom, server.sessobj, server.generation)
            log_my_msg(f"  ✓ Found {len(free_drives)} free drives")
        except Exception as e:
            log_my_msg(f"  ✗ Error: {e}")
            all_passed = False
        
        print_section("CHECKLIST SUMMARY")
        
        if all_passed:
            log_my_msg("✓ All checks PASSED - Server ready for storage operations")
        else:
            log_my_msg("✗ Some checks FAILED - See errors above")
        
        return all_passed
        
    except Exception as e:
        log_my_msg(f"✗ Checklist failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main_menu_loop(server: HpHpeServer) -> None:
    """Main interactive menu loop"""
    
    while True:
        print_menu()
        choice = input("Select option: ").strip()
        
        if choice == "1":
            run_pre_boot_checklist(server)
        elif choice == "2":
            test_discovery_functions(server)
        elif choice == "3":
            test_raid_operations(server)
        elif choice == "4":
            print_section("Running Full Storage Test Suite")
            print("This will test all discovery functions...")
            test_discovery_functions(server, test_num=9)
            print("\nAlso testing RAID status functions...")
            test_raid_operations(server, test_num=5)
        elif choice == "0":
            print("\nExiting...")
            break
        else:
            print("Invalid option")


def main():
    """Main entry point"""
    
    print("\n")
    print("╔" + "=" * 98 + "╗")
    print("║" + " " * 98 + "║")
    print("║" + "HPE STORAGE TEST RUNNER".center(98) + "║")
    print("║" + "Interactive menu for storage testing across generations".center(98) + "║")
    print("║" + " " * 98 + "║")
    print("╚" + "=" * 98 + "╝")
    
    print("\nSelect server to test:")
    print("  1. Gen10 (lab-dc1-r1-s17-lom)")
    print("  2. Gen11 (lab-dc1-r1-s15-lom)")
    print("  3. Gen12 (lab-dc1-r1-s06-lom)")
    print("  4. Custom server")
    
    server_choice = input("\nSelect server (1-4): ").strip()
    
    server = None
    
    if server_choice == "1":
        config = SERVERS["gen10"]
        server = connect_to_server(config["ip"], config["user"], config["pass"])
    elif server_choice == "2":
        config = SERVERS["gen11"]
        server = connect_to_server(config["ip"], config["user"], config["pass"])
    elif server_choice == "3":
        config = SERVERS["gen12"]
        server = connect_to_server(config["ip"], config["user"], config["pass"])
    elif server_choice == "4":
        ip = input("Enter server LOM IP: ").strip()
        user = input("Enter username (default: AdminLO): ").strip() or "AdminLO"
        passwd = input("Enter password: ").strip()
        server = connect_to_server(ip, user, passwd)
    else:
        print("Invalid choice")
        return
    
    if not server:
        print("Failed to connect to server")
        return
    
    try:
        main_menu_loop(server)
    finally:
        try:
            delete_session(server.sessobj)
            log_my_msg("Session cleaned up")
        except Exception as e:
            log_my_msg(f"Warning: Error cleaning up session: {e}")


if __name__ == "__main__":
    main()
