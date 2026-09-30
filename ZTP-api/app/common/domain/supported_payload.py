from enum import Enum


class SupportedLinuxOs(str, Enum):
    RHEL96 = "rhel-9.6"
    RHEL95 = "rhel-9.5"
    RHEL94 = "rhel-9.4"
    RHEL93 = "rhel-9.3"
    RHEL92 = "rhel-9.2"
    RHEL91 = "rhel-9.1"
    RHEL90 = "rhel-9.0"
    RHEL810 = "rhel-8.10"
    RHEL88 = "rhel-8.8"
    RHEL87 = "rhel-8.7"
    RHEL86 = "rhel-8.6"
    RHEL85 = "rhel-8.5"
    RHEL84 = "rhel-8.4"
    RHEL83 = "rhel-8.3"
    RHEL82 = "rhel-8.2"
    RHEL79 = "rhel-7.9"
    RHEL78 = "rhel-7.8"
    RHEL76 = "rhel-7.6"
    RHEL74 = "rhel-7.4"
    # CENTOS79 = "centos-7.9"
    # CENTOS78 = "centos-7.8"
    ROCKY810 = "rocky-8.10"
    ROCKY84 = "rocky-8.4"
    ROCKY83 = "rocky-8.3"
    ROCKY89 = "rocky-8.9"
    ROCKY94 = "rocky-9.4"
    ROCKY95 = "rocky-9.5"
    ROCKY96 = "rocky-9.6"
    # ALMA810 = "alma-8.10"
    # ALMA89 = "alma-8.9"
    # ALMA94 = "alma-9.4"
    # ALMA95 = "alma-9.5"

    def get_iso_name(os):
        bmi_os_map = {
            "rhel-9.6": "rhel-9.6-x86_64-dvd",
            "rhel-9.5": "rhel-9.5-x86_64-dvd",
            "rhel-9.4": "rhel-9.4-x86_64-dvd",
            "rhel-9.3": "rhel-9.3-x86_64-dvd",
            "rhel-9.2": "rhel-9.2-x86_64-dvd",
            "rhel-9.1": "rhel-baseos-9.1-x86_64-dvd",
            "rhel-9.0": "rhel-baseos-9.0-x86_64-dvd",
            "rhel-8.10": "rhel-8.10-x86_64-dvd",
            "rhel-8.9": "rhel-8.9-x86_64-dvd",
            "rhel-8.8": "rhel-8.8-x86_64-dvd",
            "rhel-8.7": "rhel-8.7-x86_64-dvd",
            "rhel-8.6": "rhel-8.6-x86_64-dvd",
            "rhel-8.5": "rhel-8.5-x86_64-dvd",
            "rhel-8.4": "rhel-8.4-x86_64-dvd",
            "rhel-8.3": "rhel-8.3-x86_64-dvd",
            "rhel-8.2": "rhel-8.2-x86_64-dvd",
            "rhel-7.9": "rhel-server-7.9-x86_64-dvd",
            "rhel-7.8": "rhel-server-7.8-x86_64-dvd",
            "rhel-7.6": "rhel-server-7.6-x86_64-dvd",
            "centos-7.9": "CentOS-7-x86_64-DVD-2009",
            "centos-7.8": "CentOS-7-x86_64-DVD-2003",
            "rocky-8.10": "Rocky-8.10-x86_64-dvd1",
            "rocky-8.4": "Rocky-8.4-x86_64-dvd1",
            "rocky-8.3": "Rocky-8.3-x86_64-dvd1",
            "rocky-8.9": "Rocky-8.9-x86_64-dvd1",
            "rocky-9.4": "Rocky-9.4-x86_64-dvd",
            "rocky-9.5": "Rocky-9.5-x86_64-dvd",
            "rocky-9.6": "Rocky-9.6-x86_64-dvd",
            "alma-8.10": "AlmaLinux-8.10-x86_64-dvd",
            "alma-8.9": "AlmaLinux-8-latest-x86_64-dvd",
            "alma-9.4": "AlmaLinux-9.4-x86_64-dvd",
            "alma-9.5": "AlmaLinux-9.5-x86_64-dvd",
        }
        return bmi_os_map[os]


class SupportedDataRaid(str, Enum):
    NORAID = ""
    RAID0 = "0"
    RAID1 = "1"
    RAID5 = "5"
    RAID6 = "6"
    RAID10 = "10"


class SupportedLinuxRole(str, Enum):
    ANTHOS = "anthos"
    HCC = "hcc"
    SPLUNK = "splunk"
    BDPAAS = "bdpaas"
    EMB = "emb"
    BASE = "base"
    PEPECE = "pep-ece"
    SHOPADMIN = "shop_admin"


class SupportedWindowsOs(str, Enum):
    # WINDOWS2016 = "win2016"
    # WINDOWS2012 = "win2012r2"
    WINDOWS2019 = "win2019"
    WINDOWS2022 = "win2022"
    WINDOWS2022core = "win2022core"


class SupportedWindowsEnv(str, Enum):
    PRD = "prod"
    STG = "stage"
    TEST = "test"
    DEV = "dev"


class SupportedEsxiOs(str, Enum):
    # HPE
    # ESXI670202111001HPE = "ESXi-6.70-202111001-HPE"
    # ESXI70015843807HPE = "ESXi-7.0.0-15843807-HPE"
    # ESXI70016324942HPE = "ESXi-7.0.0-16324942-HPE"
    # ESXI70116850804HPE = "ESXi-7.0.1-16850804-HPE"
    # ESXI70117551050HPE = "ESXi-7.0.1-17551050-HPE"
    # ESXI70319482537HPE = "ESXi-7.0.3-19482537-HPE"
    # ESXI70321686933HPE = "ESXi-7.0.3-21686933-HPE"
    # ESXI80022380479HPE = "ESXi-8.0.0-22380479-HPE"
    ESXI70323307199HPE = "ESXi-7.0.3-23307199-HPE"
    ESXI80223305546HPE = "ESXi-8.0.2-23305546-HPE"
    # ESXI80324414501HPE = "ESXi-8.0.3-24414501-HPE"
    ESXI80324585383HPE = "ESXi-8.0.3-24585383-HPE"
    ESXI80324674464HPE = "ESXi-8.0.3-24674464-HPE"
    ESXI80324784735HPE = "ESXi-8.0.3-24784735-HPE"

    # DELL
    # ESXI67017700523DELL = "ESXi-6.7.0-17700523-Dell"
    # ESXI70015843807DELL = "ESXi-7.0.0-15843807-Dell"
    # ESXI70116850804DELL = "ESXi-7.0.1-16850804-Dell"
    # ESXI70117551050DELL = "ESXi-7.0.1-17551050-Dell"
    # ESXI70319482537DELL = "ESXi-7.0.3-19482537-DELL"
    # ESXI703G20328353DELL = "ESXi-703g-20328353-Dell"
    ESXI70323307199DELL = "ESXi-7.0.3-23307199-DELL"
    # ESXI80022380479DELL = "ESXi-8.0.0-22380479-Dell"
    ESXI80223305546DELL = "ESXi-8.0.2-23305546-Dell"
    # ESXI80324414501DELL = "ESXi-8.0.3-24414501-Dell"
    ESXI80324585383DELL = "ESXi-8.0.3-24585383-Dell"
    ESXI80324674464DELL = "ESXi-8.0.3-24674464-Dell"
    ESXI80324784735DELL = "ESXi-8.0.3-24784735-Dell"
