from enum import Enum


class BuildTypes(str, Enum):
    BUILDS_LINUX = "builds_linux"
    BUILDS_WINDOWS = "builds_windows"
    BUILDS_ESXI = "builds_esxi"
    BASELNE_HPE_ILO = "baseline_hpe_ilo"
    BASELINE_HPE_BIOS = "baseline_hpe_bios"
    BASELINE_HPE_PREP = "baseline_hpe_prep"
    BASELINE_HP_SPP = "baseline_hp_spp"
    BASELINE_HPE_TPM = "baseline_hpe_tpm"
    BASELINE_HP_CHECKFIRMWARE = "baseline_hp_checkfirmware"
    BASELINE_DELL_IDRAC = "baseline_dell_idrac"
    BUILDS_TEST = "builds_test"
