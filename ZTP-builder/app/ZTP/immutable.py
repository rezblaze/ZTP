# -*- coding: utf-8 -*-

"""Immutable module provide custom ISO creation functions"""

import fileinput
import json
import logging
import os
import re
import shutil
import socket
import ssl
import time
from importlib import resources

import wget

from . import templates
from ._common import log_my_msg
from ._hardware import get_primary_ethernet_mac
from ._session import create_requests_retry_no_token_auth
from .exception import PrimaryMacNotFound, ServerPingsException
from .sanitycheck import check_if_host_ping

__author__ = "David Blasing, Chirag Patel, Joel E Carlson"
__email__ = "support@example.com"

logger = logging.getLogger(__name__)

no_token_sessobj = create_requests_retry_no_token_auth()

# Global variable set for filesystem where immutable uses the space
PUBDIR = "/pub"
HOSTDIR = "/pub/hostdir"
ISODIR = "/pub/hostiso"


class Immutable:
    """Class: Immutable image functionality"""

    def __init__(self, build):
        """Immutable: Host ISO provider

        Args:
            build: BMI build data collection

        Note: This module design to run on linux server also requires
                - genisoimage  & supported tools installed
                - /pub NAS share being mounted with lots of space
        """
        log_my_msg("*** ZTP Immutable module ***")
        self.build = build
        self.build_details = build["build_details"]
        self.networkdata = build["networkdata"]
        if self.networkdata["HARDWARE"].lower() == "hp":
            self.networkdata["GENERATION"] = "gen9"
        if self.networkdata["HARDWARE"].lower() == "dell":
            self.networkdata["GENERATION"] = "gen_dell"
        osname = build["build_details"]["os"]
        os_type = osname.split("-")[0].lower()
        if os_type == "esxi":
            self.osname = osname
        elif os_type.startswith("win"):
            self.osname = "windows"
        else:
            self.osname = build["build_details"]["isoimage"]
        self.attributes = build["build_details"]["attributes"]
        self.vlan = self.attributes.get("vlan", "")

    def __repr__(self):
        return f"Immutable ({self})"

    def make_rhel_iso(self):
        """Method: make_rhel_iso for rhel & centos
        Returns: iso_url (str) : host iso url
        """
        log_my_msg("(Immutable) make_rhel_iso")
        hostiso_dict = {}
        networkdata = self.networkdata
        override = self.build_details["override"]
        if bool(override):
            for key in override.keys():
                if key.upper() in networkdata.keys():
                    networkdata[key.upper()] = override[key]
                    log_my_msg(f"*** override networkdata for {key}: {override[key]} ***")
        log_my_msg("setting primay network mac address")
        if "mac" in override.keys():
            pri_mac = override["mac"]
            log_my_msg(f"*** override primary mac {pri_mac} ***")
            log_my_msg(
                "*** Warning: Bonding/Teaming config in post build will be disable due to mac override! if necessary apply config manually! ***"
            )
            nobonding = {"bonding": False}
            self.build["build_details"]["override"].update(nobonding)
        else:
            pri_mac = get_primary_ethernet_mac(networkdata["HARDWARE"], networkdata["GENERATION"], networkdata["LOMIP"])
        log_my_msg(f"\noverride: {override} \nos: {self.osname} \nmac: {pri_mac}")
        if pri_mac is None:
            raise PrimaryMacNotFound
        if "ks_url" in override.keys():
            ks_url = override["ks_url"]
            log_my_msg(f"*** override KS_URL {ks_url} ***")
        else:
            ks_url = resources.files(templates) / "ks_rhel.cfg"
            ks_url = str(ks_url)
            log_my_msg(f"INFO - Using KS file {ks_url}")
        prepare_iso_workspace(self.osname, networkdata["SHORT_NAME"])
        host_url = make_rhel_iso(networkdata, ks_url, pri_mac, self.osname, self.build)
        hostiso_dict.update({"status": "created", "hostiso_url": host_url})
        return {"immutable": hostiso_dict}

    def make_esxi_iso(self):
        """Method: make_esxi_iso for esxi
        Returns: iso_url (str) : host iso url
        """
        log_my_msg("(Immutable) make_esxi_iso")
        hostiso_dict = {}
        networkdata = self.networkdata
        override = self.build_details["override"]
        if bool(override):
            for key in override.keys():
                if key.upper() in networkdata.keys():
                    networkdata[key.upper()] = override[key]
                    log_my_msg(f"*** override networkdata for {key}: {override[key]} ***")
        log_my_msg("setting primay network mac address")
        if "mac" in override.keys():
            pri_mac = override["mac"]
            log_my_msg(f"*** override primary mac {pri_mac} ***")
        else:
            pri_mac = get_primary_ethernet_mac(networkdata["HARDWARE"], networkdata["GENERATION"], networkdata["LOMIP"])
        if check_if_host_ping(networkdata["IP"]):
            raise ServerPingsException
        # pri_mac = get_primary_ethernet_mac(networkdata["HARDWARE"], networkdata["LOMIP"])
        log_my_msg(f"\nos: {self.osname} \nvlan:{self.vlan} \nmac: {pri_mac}")
        if pri_mac is None:
            raise PrimaryMacNotFound
        ks_url = resources.files(templates) / "ks_esxi.cfg"
        ks_url = str(ks_url)
        log_my_msg(f"ks: {ks_url}")
        prepare_iso_workspace(self.osname, networkdata["SHORT_NAME"])
        host_url = make_esxi_iso(networkdata, ks_url, pri_mac, self.build, self.vlan)
        hostiso_dict.update({"status": "created", "hostiso_url": host_url})
        log_my_msg(f"immutable: {hostiso_dict}")
        return {"immutable": hostiso_dict}

    def make_windows_iso(self):
        """Method: make_windows_iso for windows"""
        log_my_msg("(Immutable) make_windows_iso")
        hostiso_dict = make_windows_iso(self.networkdata, self.osname, self.build)
        return {"immutable": hostiso_dict}


###
### Helper Functions
###
def check_pub():
    """Fn: check_pub check /pub mounted"""
    return bool(os.path.ismount("/pub"))


def check_free_space():
    """Fn: check_free_space"""
    log_my_msg(f"Fn: check_free_space {PUBDIR}")
    total, used, free = shutil.disk_usage(PUBDIR)
    free_gb = free / (1024 * 1024 * 1024)
    log_my_msg(f" - {PUBDIR} have {free_gb} GB free space")
    log_my_msg(f"total:{total}, used:{used}, free{free}")
    return free_gb


def get_iso(osname):
    """Fn: get_iso"""
    log_my_msg("Fn: get_iso")
    source_iso = f"{osname}.iso"
    if os.path.isdir(PUBDIR) is False:
        raise Exception(
            f"fail: {PUBDIR} doesn't exist on the server , it is required for creating immutable iso images!"
        )
    os.chdir(PUBDIR)
    if os.path.exists(f"{PUBDIR}/{source_iso}") is True:
        log_my_msg(f" pass: {PUBDIR}/{source_iso} exists... Nothing to do!")
    else:
        # primaryos = source_iso.split("-")[0].lower()
        # if primaryos == "esxi":
        #     url = f"https://repo1.example.com/artifactory/docker/company-component/ESXi/{source_iso}"
        # elif primaryos in ("rhel", "centos"):
        #     url = f"http://sat-cap-elr-a.example.com/pub/iso/{source_iso}"
        # else:
        raise Exception(f" fail: unknow iso requested - {source_iso} ")

        # log_my_msg(f" {source_iso} iso image for os does not exist! \n downloading it from {url}")
        # try:
        #     log_my_msg(url)
        #     wget.download(url)
        # except Exception as error:
        #     log_my_msg(f" fail: download {source_iso} failed with \n {error}")
        #     raise
    return {source_iso: "{PUBDIR}"}


def prepare_iso_workspace(osname, servername):
    """Fn: prepare_iso_workspace"""
    log_my_msg("Fn: prepare_iso_workspace")
    os_iso_mnt = f"/mnt/{osname}"
    cp_iso_path = f"{PUBDIR}/{osname}"
    if os.path.isdir(cp_iso_path) and len(os.listdir(cp_iso_path)) > 0:
        log_my_msg(f"{cp_iso_path} appears to be ready for use")
    else:
        os.system(f"rm -rf {cp_iso_path}")
        if os.path.ismount(os_iso_mnt):
            log_my_msg(f" pass: {os_iso_mnt} mounted")
        else:
            log_my_msg(f" warning: {os_iso_mnt} not mounted, try mounting it.")
            if not os.path.exists(os_iso_mnt):
                os.system(f"sudo mkdir -p {os_iso_mnt}")
            mount = os.system(f"sudo mount {PUBDIR}/{osname}.iso {os_iso_mnt}")
            if mount != 0:
                raise Exception(f" fail: mount {PUBDIR}/{osname}.iso {os_iso_mnt}")
        try:
            log_my_msg(f"Copy files from {os_iso_mnt} to {cp_iso_path}.")
            shutil.copytree(os_iso_mnt, cp_iso_path)
            log_my_msg(f" pass: iso content copied to {cp_iso_path} successfully")
        except Exception as error:
            log_my_msg(f" fail: copying {os_iso_mnt} in {cp_iso_path} \n {error}")
            raise
    mk_custom_iso(osname, servername)
    if os.path.ismount(os_iso_mnt):
        mount = os.system(f"sudo umount {PUBDIR}/{osname}.iso {os_iso_mnt}")


def mk_custom_iso(osname, servername):
    """Fn: Make custom iso"""
    log_my_msg("Fn: copying iso content to customise")
    custom_iso = f"{HOSTDIR}/{servername}"
    if os.path.isdir(custom_iso):
        log_my_msg(f" - {custom_iso} directory exist. Removing it before copying iso data over to new directory")
        os.system(f"rm -rf {custom_iso}")
    try:
        shutil.copytree(f"{PUBDIR}/{osname}", custom_iso, ignore=shutil.ignore_patterns("*.rpm"))
        log_my_msg(" pass: iso content copied successfully")
    except Exception as error:
        log_my_msg(f" fail: copying {PUBDIR}/{osname} in {custom_iso} \n {error}")
        raise
    os.system(f"chmod -R ugo+rwx {custom_iso}")
    return custom_iso


def make_esxi_iso(networkdata: dict, ks_url: str, mac: str, build: dict, vlanid=""):
    """Fn: make_esxi_iso - make iso image for esxi"""
    log_my_msg("Fn: make esxi hostiso image")
    servername = networkdata["SERVERNAME"]
    gateway = networkdata["GATEWAY"]
    ip = networkdata["IP"]
    netmask = networkdata["NETMASK"]
    short_name = networkdata["SHORT_NAME"]
    dns1 = networkdata["DNS1"]
    dns2 = networkdata["DNS2"]

    iso_cust_dir = f"{HOSTDIR}/{short_name}"
    host_iso_file = f"{ISODIR}/{short_name}.iso"
    override = build["build_details"]["override"]

    if "standards_branch" in override.keys():
        standards_branch_update = override["standards_branch"]
        log_my_msg(f"*** override linux stanadard branch {standards_branch_update} ***")
    else:
        standards_branch_update = "master"
    if ks_url[:4] == "http":
        resp = no_token_sessobj.get(ks_url)
        if not resp.ok:
            raise Exception(f"Kickstart error opening file {ks_url}\n{resp.text}")
        ks_data = resp.text
    else:
        try:
            with open(ks_url, "r") as f:
                ks_data = f.read()
        except Exception as err:
            raise Exception(f"Kickstart error opening file {ks_url}\n {err}")

    root_disk_line = ""
    if "hp" in networkdata["HARDWARE"]:
        root_disk_line = 'install --firstdisk="LOGICAL VOLUME",local --overwritevmfs'
    if networkdata["HARDWARE"] == "dell":
        if "R760" in build["serverinfo"]["MODEL"]:
            root_disk_line = "install --firstdisk=DELL\ BOSS-N1 --overwritevmfs"
        else:
            root_disk_line = "install --firstdisk=lsi_mr3,local --overwritevmfs"

    if vlanid == "":
        network_line = f"network --bootproto=static --ip={ip} --netmask={netmask} --gateway={gateway} --nameserver={dns1},{dns2} --hostname={servername} --device={mac} --addvmportgroup=0"
    else:
        network_line = f"network --bootproto=static --ip={ip} --netmask={netmask} --vlanid={vlanid} --gateway={gateway} --nameserver={dns1},{dns2} --hostname={servername} --device={mac} --addvmportgroup=0"
    ks_txt = (
        ks_data.replace("<NETWORK>", network_line)
        .replace("<INSTALL_DISK>", root_disk_line)
        .replace("<DOMAIN>", networkdata["DOMAIN"])
        .replace("<SERVERNAME>", networkdata["SERVERNAME"])
        .replace("<DNS1>", networkdata["DNS1"])
        .replace("<DNS2>", networkdata["DNS2"])
    )
    os.chdir(iso_cust_dir)
    with open("KS.CFG", "w") as file:
        file.write(ks_txt)

    bootcfg = f"{iso_cust_dir}/efi/boot/boot.cfg"
    log_my_msg(f"boot.cfg... {bootcfg}")
    kernel_line = "kernelopt=runweasel ks=cdrom:/KS.CFG\n"

    with fileinput.FileInput(bootcfg, inplace=True, backup=".bak") as file:
        for line in file:
            if "kernelopt=" in line:
                line = kernel_line
            print(line, end="")

    if shutil.which("genisoimage") is None:
        raise Exception(" fail: genisoimage command not found")
    log_my_msg(" generate custom iso image for host")
    genisoimage = f"genisoimage -relaxed-filenames -J -R -o {host_iso_file}  -b isolinux.bin -c boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table -eltorito-alt-boot -e efiboot.img -no-emul-boot {iso_cust_dir}"
    log_my_msg(f"{genisoimage}")
    genisoimage_result = os.system(genisoimage)
    
    if genisoimage_result != 0:
        log_my_msg(" genisoimage command failed, retrying after 10 seconds...")
        time.sleep(10)
        genisoimage_result = os.system(genisoimage)
        if genisoimage_result != 0:
            raise Exception(" fail: genisoimage command failed to execute after retry")

    os.system(f"chmod ugo+rwx {host_iso_file}")
    iso_host_server = socket.gethostbyname(socket.gethostname())
    iso_url = f"http://{iso_host_server}{host_iso_file}"

    return iso_url


def make_rhel_iso(networkdata: dict, ks_url: str, mac: str, osname: str, build: dict):
    """Fn:make_rhel_iso Make iso image for rhel and centos"""
    log_my_msg("Fn: make_rhel_iso - make rhel hostiso image")
    servername = networkdata["SERVERNAME"]
    domain = networkdata["DOMAIN"]
    gateway = networkdata["GATEWAY"]
    ip = networkdata["IP"]
    netmask = networkdata["NETMASK"]
    short_name = networkdata["SHORT_NAME"]
    dns1 = networkdata["DNS1"]
    dns2 = networkdata["DNS2"]
    dc = networkdata["DC"].lower()
    hardware = networkdata["HARDWARE"].lower()
    generation = networkdata.get("GENERATION", "none")
    iso_cust_dir = f"{HOSTDIR}/{short_name}"
    host_iso_file = f"{ISODIR}/{short_name}.iso"
    cidr = networkdata["CIDR"]
    vlanid = networkdata.get("VLANID")
    role = build["build_details"]["attributes"]["role"]
    os_ver = build["build_details"]["os"]
    data_raid = build["build_details"]["attributes"]["data_raid"]
    override = build["build_details"]["override"]

    if "standards_branch" in override.keys():
        standards_branch_update = override["standards_branch"]
        log_my_msg(f"*** override linux stanadard branch {standards_branch_update} ***")
    else:
        standards_branch_update = "master"
    ### sanity check
    log_my_msg("checking to make sure primary ip is not pinging over the network!")
    if check_if_host_ping(ip):
        raise ServerPingsException

    ### kickstart config
    if ks_url[:4] == "http":
        resp = no_token_sessobj.get(ks_url)
        if not resp.ok:
            raise Exception(f"Kickstart error opening file {ks_url}\n{resp.text}")
        ks_data = resp.text
    else:
        try:
            with open(ks_url, "r") as f:
                ks_data = f.read()
        except Exception as err:
            raise Exception(f"Kickstart error opening file {ks_url}\n {err}")

    media_server = socket.gethostbyname(socket.gethostname())
    if networkdata["ZONE"] == "NZ-INTER":
        if networkdata["DC"] == "SITE_A":
            log_my_msg("media server lab-media-01.example.com (198.51.100.47) SITE_A DMZ")
            media_server = "198.51.100.47"
        else:
            log_my_msg("media server lab-media-02.example.com (198.51.100.55) SITE_B DMZ")
            media_server = "198.51.100.55"

    if osname.split(".")[0][-1] == "9":
        install = "#install"
        repo_url = f"url --url=http://{media_server}{PUBDIR}/{osname}"
        keyboard = "keyboard --xlayouts='us'"
    else:
        install = "install"
        repo_url = f"url --url http://{media_server}{PUBDIR}/{osname}"
        keyboard = "keyboard us"

    log_my_msg(f"media share {repo_url}")

    ### BMI testing servers with vlan configured, it will be removed in future
    tnt_server_list = [
        "lab-dc1-r1-s18",
        "lab-dc1-r1-s19",
        "lab-dc1-r1-s02",
        "lab-dc1-r1-s16",
        "lab-dc1-r1-s17",
        "lab-dc1-r1-s01",
        "lab-dc1-r1-s15",
        "lab-dc1-r1-s14",
    ]
    if short_name in tnt_server_list:
        vlanid = "3020"
        log_my_msg(f"Note: Assigning VLAN {vlanid} for TnT server")
    elif override.get("vlan") is not None:
        vlanid = override["vlan"]
        log_my_msg(f"*** override vlan {vlanid} ***")
    else:
        vlanid = ""

    if vlanid == "":
        network_line = f"network --bootproto static --ip={ip} --netmask={netmask} --gateway={gateway} --nameserver={dns1},{dns2} --hostname={servername} --device={mac}"
    else:
        network_line = f"network --bootproto static --ip={ip} --netmask={netmask} --gateway={gateway} --nameserver={dns1},{dns2} --hostname={servername} --device={mac} --vlanid='3020'"

    ks_txt = (
        ks_data.replace("<INSTALL>", install)
        .replace("<KEYBOARD>", keyboard)
        .replace("<REPO_URL>", repo_url)
        .replace("<NETWORK>", network_line)
        .replace("<DC>", dc)
        .replace("<IP>", ip)
        .replace("<SERVERNAME>", servername)
        .replace("<NETMASK>", netmask)
        .replace("<GATEWAY>", gateway)
        .replace("<CIDR>", cidr)
        .replace("<VLAN>", vlanid)
        .replace("<DOMAIN>", domain)
        .replace("<MAC>", mac)
        .replace("<DNS1>", dns1)
        .replace("<DNS2>", dns2)
        .replace("<HARDWARE>", hardware)
        .replace("<GENERATION>", generation.lower())
        .replace("<VENDOR>", hardware)
        .replace("<ROLE>", role)
        .replace("<DATA_RAID>", data_raid)
        .replace("<OS_VER>", os_ver)
        .replace("<BRANCH>", standards_branch_update)
    )

    os.chdir(iso_cust_dir)
    with open("build.json", "w") as file:
        file.write(json.dumps(build, indent=4))

    os.chdir(iso_cust_dir)
    with open("KS.CFG", "w") as file:
        file.write(ks_txt)

    # UEFI boot update
    bootcfg = f"{iso_cust_dir}/EFI/BOOT/grub.cfg"
    os.remove(bootcfg)
    # resp = no_token_sessobj.get("http://bmi-prod.example.com/pub/tools/build_files/grub.cfg")
    # grub_data = resp.text
    resp = resources.files(templates) / "grub.cfg"
    grub_file = str(resp)
    try:
        with open(grub_file, "r") as f:
            grub_data = f.read()
    except Exception as err:
        raise Exception(f"Kickstart error opening file {ks_url}\n {err}")

    with open(bootcfg, "w") as file:
        file.write(grub_data)

    with open(bootcfg, "r") as file:
        for line in file:
            search = re.findall(r"search", line)
            if search:
                label = line.split("'")[1]
                log_my_msg(f" found label {label} it will be replace with {short_name}")

    # Legacy boot update
    iso_linux = f"{iso_cust_dir}/isolinux/isolinux.cfg"
    os.remove(iso_linux)
    # resp = no_token_sessobj.get("http://bmi-prod.example.com/pub/tools/build_files/isolinux.cfg")
    # iso_linux_data = resp.text
    resp = resources.files(templates) / "isolinux.cfg"
    isolinux_file = str(resp)
    try:
        with open(isolinux_file, "r") as f:
            isolinux_data = f.read()
    except Exception as err:
        raise Exception(f"Kickstart error opening file {ks_url}\n {err}")

    with open(iso_linux, "w") as file:
        file.write(isolinux_data)

    # Add ilorest, python3 and preztp_hpe script
    pre_dir = f"{iso_cust_dir}/prekickstart/"
    pub_pre_dir = "/pub/tools/prekickstart/"
    os.mkdir(pre_dir)
    os.chdir(pre_dir)
    cwd = os.getcwd()
    os.chmod(pre_dir, 0o777)
    log_my_msg(f"pwd = {cwd} and pre_dir = {iso_cust_dir}")

    ssl._create_default_https_context = ssl._create_unverified_context

    # copy rpms for pre install tasks
    rpms = []
    urls = [
        "http://capsule-ctc-dmz-lb-c-prod.example.com/pub/hpe/spp/{generation}/packages/hponcfg-6.0.0-0.x86_64.rpm",
        "http://capsule-ctc-dmz-lb-c-prod.example.com/pub/hpe/spp/{generation}/packages/ssacli-6.25-9.0.x86_64.rpm",
    ]
    for url in urls:
        os.chdir(pub_pre_dir)
        file = os.path.basename(url)
        if not os.path.isfile(file):
            log_my_msg(f"Copy file {file}")
            wget.download(url)
            os.chmod(file, 0o777)

    rpms = ["ssacli-6.25-9.0.x86_64.rpm", "hponcfg-6.0.0-0.x86_64.rpm", "ilorest-6.0.0.0-29.x86_64.rpm"]
    if "-9" in os_ver:
        files = ["libxcrypt-compat-4.4.18-3.el9.x86_64.rpm"]
        rpms.extend(iter(files))
    for i in rpms:
        shutil.copy2(f"{pub_pre_dir}{i}", pre_dir)

    # copy postbuild scripts
    pub_pre_dir = "/pub/tools/github/standards/company-bmi-infra/scripts/postbuild/"
    postbuild_scripts = ["bmi_postbuild_config.sh", "firstboot.sh", "hpe_nic_teaming.sh", "ansible_play.sh"]
    for i in postbuild_scripts:
        shutil.copy2(f"{pub_pre_dir}{i}", pre_dir)

    os.chdir(iso_cust_dir)

    log_my_msg(f"generate custom iso image for host {servername}")
    if shutil.which("mkisofs") is None:
        raise Exception("mkisofs not found!")
    log_my_msg(
        f'mkisofs -o {host_iso_file} -b isolinux/isolinux.bin -J -R -l -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table -eltorito-alt-boot -e images/efiboot.img -no-emul-boot -graft-points -V "{label}" {iso_cust_dir}'
    )
    mkisofs_cmd = f'mkisofs -o {host_iso_file} -b isolinux/isolinux.bin -J -R -l -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table -eltorito-alt-boot -e images/efiboot.img -no-emul-boot -graft-points -V "{label}" {iso_cust_dir}'
    mkisofs = os.system(mkisofs_cmd)
    
    if mkisofs != 0:
        log_my_msg(" mkisofs command failed, retrying after 10 seconds...")
        time.sleep(10)
        mkisofs = os.system(mkisofs_cmd)
        if mkisofs != 0:
            raise Exception(" fail: mkisofs command failed to execute after retry")

    isohybrid_cmd = f"isohybrid --uefi {host_iso_file}"
    isohybrid = os.system(isohybrid_cmd)
    if isohybrid != 0:
        raise Exception(" fail: isohybrid command failed to execute")

    os.system(f"chmod 777 {host_iso_file}")

    socket.gethostbyname(socket.gethostname())
    return f"http://{media_server}{host_iso_file}"


def make_windows_iso(networkdata: dict, osname: str, build: dict):
    """Fn: make_windows_iso - make iso image for Windows"""
    log_my_msg("Fn: make_windows_iso - make windows hostiso image")
    short_name = networkdata["SHORT_NAME"]
    iso_cust_dir = f"{HOSTDIR}/{short_name}"

    if not os.path.exists(iso_cust_dir):
        os.mkdir(iso_cust_dir)
    os.chdir(iso_cust_dir)
    with open("build.json", "w") as file:
        file.write(json.dumps(build, indent=4))

    host_iso_file = f"{ISODIR}/{short_name}.iso"
    powershell_dir = "/pub/tools/github/standards/company-bmi-infra/scripts/powershell"
    winpe_dir = f"/pub/windows_build/winpe/media"
    os.chdir(iso_cust_dir)
    genisoimage_cmd = f"genisoimage -b boot_images/etfsboot.com -iso-level 4 -rock -disable-deep-relocation -untranslated-filenames -no-emul-boot -boot-load-size 8 -eltorito-alt-boot -b boot_images/efisys_noprompt.bin -graft-points -o {host_iso_file} {winpe_dir} PostBuildScripts={powershell_dir}/PostBuildScripts/ WinpeScripts={powershell_dir}/WinpeScripts/ {iso_cust_dir}/build.json"
    log_my_msg(f"Running command: {genisoimage_cmd}")
    genisoimage = os.system(genisoimage_cmd)
    if genisoimage != 0:
        raise Exception("genisoimage command failed to execute")
    os.system(f"chmod 777 {host_iso_file}")
    # Remove the temporary build.json file after ISO creation
    os.remove(f"{iso_cust_dir}/build.json")
    iso_host_server = socket.gethostbyname(socket.gethostname())
    iso_url = f"http://{iso_host_server}{host_iso_file}"
    log_my_msg(f"Windows ISO created at {iso_url}")
    return iso_url
