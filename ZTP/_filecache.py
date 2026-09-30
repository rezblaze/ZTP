# -*- coding: utf-8 -*-

""" _common.py
"""

__author__ = "David Blasing, Chirag Patel"
__email__ = "david_m_blasing@example.com, chirag_patel@example.com"

import json
import time
import wget
import os
from ._common import log_my_msg
CACHE = {}


def copy_files():
    pub_build_files = {}
    github_build_files = {
            "gen10_standards": "https://github.example.com/raw/Platform-Standards/HPE-Standard/master/json/gen10_full.json",
            "gen9_standards": "https://github.example.com/raw/Platform-Standards/HPE-Standard/master/json/gen9_full.json",
            "hpe_vars": "https://github.example.com/raw/Platform-Standards/HPE-Standard/master/json/hpe_variables.json",
            "hpe_lom_key": "https://github.example.com/raw/BareMetal/Standards/master/scripts/key.key",
            "hpe_lom_json": "https://github.example.com/raw/BareMetal/Standards/master/lomkey/new_lom.json",
            "R740XD": "https://github.example.com/raw/Platform-Standards/Dell_Standards/master/json/R740XD.BIOS.json",
            "R740": "https://github.example.com/raw/Platform-Standards/Dell_Standards/master/json/R740XD.BIOS.json",
            "R6515": "https://github.example.com/raw/Platform-Standards/Dell_Standards/master/json/R6515.bios.standard.json",
            "R7525": "https://github.example.com/raw/Platform-Standards/Dell_Standards/master/json/R7525.bios.standard.json",
            "R750": "https://github.example.com/raw/Platform-Standards/Dell_Standards/master/json/R750.bios.standard.json",
            "R740XD_iDRAC": "https://github.example.com/raw/Platform-Standards/Dell_Standards/master/json/R740XD_iDRAC.json",
            "R740XD_secure_boot": "https://github.example.com/raw/Platform-Standards/Dell_Standards/master/json/R740XD.BIOS.SecureBoot.json",
            "dell_ctlr_encryption": "https://github.example.com/raw/Platform-Standards/Dell_Standards/master/json/SedKey.json",   
        }
    pub_build_files_dir = "/pub/tools/build_files/"
    if not os.path.isdir(pub_build_files_dir):
        raise Exception(f"{pub_build_files_dir} not found or inaccessable!")
    for key, value in github_build_files.items():
        os.chdir(pub_build_files_dir)
        file = os.path.basename(value)
        pub_build_files[key] = f"{pub_build_files_dir}{file}"
        if not os.path.isfile(file):
            log_my_msg(f"Copying file {file} to /pub/tools/build_files/")
            try:
                wget.download(value)
                os.chmod(file, 0o777)
            except Exception as e:
                log_my_msg(f"Failed to get file {file}!")    
    return pub_build_files              
            

def build_config_files():
    global CACHE
    files_dict = copy_files()
    log_my_msg("getting HPE vars file")
    with open(files_dict['hpe_vars'], 'r', encoding="utf-8") as file:
        vars_file = json.load(file)
    gen_list = ["gen9", "gen10"]
    dc_list = ["SITE_B", "SITE_A", "DMZ"]
    for gen in gen_list:
        gen_file = f"{gen}_standards"
        with open(files_dict[gen_file], 'r', encoding="utf-8") as org_file:
            content = org_file.read()
            for DC in dc_list:
                content_update = (
                        content.replace("<DNS1>", vars_file[DC]["DNS1"])
                        .replace("<DNS2>", vars_file[DC]["DNS2"])
                        .replace("<DNS3>", vars_file[DC]["DNS3"])
                        .replace("<eskm_pri>", vars_file[DC]["eskm_pri"])
                        .replace("<eskm_secondary>", vars_file[DC]["eskm_secondary"])
                        .replace("<timezone>", vars_file[DC]["eskm_secondary"])
                        .replace("<eskm_group>", vars_file[gen]["eskm_group"])
                        .replace("<eskm_key>", vars_file[gen]["eskm_key"])
                        .replace("<time1>", vars_file["Global"]["time1"])
                        .replace("<time2>", vars_file["Global"]["time2"])
                        .replace("<eskm_loginname>", vars_file["Global"]["EskmUser"])
                        .replace("<eskm_password>", vars_file["Global"]["EskmPass"])
                        .replace("<hostname>", "testlo")
                        .replace("<fqdn>", "fqdn")
                        .replace("<domainname>", "example.com")
                        .replace("LegacyBios", "Uefi")
                        .replace("\n", "")
                    )
                file = f"{gen_file}_{DC}.json"
                with open(file, 'w', encoding="utf-8") as f:
                    f.write(content_update)
                CACHE[file]=content_update

# if __name__ == '__main__':
#     #print(copy_files())
#     print(build_config_files())
# print("Printing my cache")
# print(CACHE)