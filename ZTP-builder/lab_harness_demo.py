# -*- coding: utf-8 -*-
import logging
from textwrap import indent
import app.ZTP as ZTP
import urllib3

from app.ZTP import dell
from app.ZTP.dell import DellServer
from app.build_service.cache import CREDS

urllib3.disable_warnings()

logging.basicConfig(
    filename="lab_harness_demo.log",
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)
logging.getLogger(__name__)
logging.getLogger().addHandler(logging.StreamHandler())

dell_R740XD_server = ["lab-dc1-r1-s18.example.com", "lab-dc1-r1-s19.example.com"]
dell_R750_server = "lab-dc1-r1-s02.example.com"
dell_7625_server = "lab-dc1-r1-s16.example.com"
dell_7625_servers = ["lab-dc1-r1-s10.example.com", "lab-dc1-r1-s11.example.com"]
dell_R760_server = ["lab-dc1-r1-s06.example.com", "lab-dc1-r1-s07.example.com"]
dell_R6615_server = ["lab-dc1-r1-s08.example.com","lab-dc1-r1-s09.example.com"]


hpe_dl385_g10_server = "lab-dc1-r1-s17.example.com"
hpe_dl345_g11_server = "lab-dc1-r1-s15.example.com"
hpe_dl380_g11_server = "lab-dc1-r1-s14.example.com"
hpe_dl385_g11_server = "lab-dc1-r1-s01.example.com"

# import json
# lab-build-01 = "lab-build-01.example.com"
# ztpaction = ZTP.Actions(lab-build-01)
# ztpaction.ztp_get_iml()


obj = ZTP.HpHpeServer("lab-dc1-r1-s06-lom.example.com", "AdminLO", CREDS['hpe']['AdminLO'])
obj.get_storage_info()
# obj.setup_NS204_controller()