import json
import logging

import app.build_service.loran_service as loran_service
import app.ZTP as ZTP

logger = logging.getLogger(__name__)


def baseline_dell_idrac(build):
    hostname = build["build_details"]["host"]
    logger.info(f"fn:baseline_dell_idrac: {json.dumps(build, indent=4)}")
    server_action = ZTP.Actions(build)
    loran_service.add_hostdata_loran(hostname, build)
    idracdata = server_action.ztp_idrac_config_check()
    logger.info(f"\n\n {idracdata} \n\n")
    loran_service.update_loran_hostdata(hostname, idracdata)
