import logging

from fastapi import APIRouter, Depends

from app.common.domain.build_types import BuildTypes
from app.dto.server_build_dto import (
    HpeBiosBaselineDto,
    HpeTpmBaselineDto,
    HpeIloBaselineDto,
    ServerNameOnlyDto,
)
from app.dto.status_response import StatusUriResponse
from app.security import auth_service
from app.service import build_service
from app.modules import servercheck

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/baseline/hpe/ilo", tags=["HPE Server Standards Baseline"])
async def baseline_hpe_ilo(
    build: HpeIloBaselineDto,
    requestor: dict = Depends(auth_service.validate_and_get_username),
):
    """
    <h2><b>check and/or apply hpe ilo baseline configuration and firmware</b></h2>
    - *payload*
        - **host**: fully qualified domain name of server/host
        - **apply_ilo_baseline**:
            - false: just check ilo config against baseline
            -  true: check and apply ilo config changes if necessary
        - **apply_ilo_firmware**:
            - false: just check firmware version against baseline
            -  true: check and apply firmware if necessary
    - *Ilo firmware standard document*
        - Gen10 [ilo5_version](https://github.com/company-org/HPE-Standard/blob/master/json/hpe_variables.json)**
        - Gen9 [ilo4_version](https://github.com/company-org/HPE-Standard/blob/master/json/hpe_variables.json)**
    """
    build_details_dict = await build_service.validate_build(build.dict())
    build_id = await build_service.create_build(BuildTypes.BASELNE_HPE_ILO.value, build_details_dict, requestor)
    return StatusUriResponse(status=f"/builds/status/{build_id}")


@router.post("/baseline/hpe/bios", tags=["HPE Server Standards Baseline"])
async def baseline_hpe_bios(
    build: HpeBiosBaselineDto,
    requestor: dict = Depends(auth_service.validate_and_get_username),
):
    """
    <h2></b>check and/or apply hpe bios baseline</h2></b>
    - *payload*
        - **host**: fully qualified domain name of server/host
        - **apply_hpe_bios_baseline**:
            - false : just check bios settings against baseline
            -  true : check and apply bios settings if necessary
    """
    build_details_dict = await build_service.validate_build(build.dict())
    build_id = await build_service.create_build(BuildTypes.BASELINE_HPE_BIOS.value, build_details_dict, requestor)
    return StatusUriResponse(status=f"/builds/status/{build_id}")

@router.post("/baseline/hpe/tpm", tags=["HPE Server Standards Baseline"])
async def baseline_hpe_tpm(
    build: HpeTpmBaselineDto,
    requestor: dict = Depends(auth_service.validate_and_get_username),
):
    """
    <h2></b>check and/or apply hpe TPM baseline setting</h2></b>
    - *payload*
        - **host**: fully qualified domain name of server/host
        - **apply_tpm_baseline**:
            - false : check TPM settings is visible or hidden, no changes applied
            -  true : check TPM settings is visible or hidden, if hidden apply baseline to make it visible
    """
    build_details_dict = await build_service.validate_build(build.dict())
    resp = await servercheck.check_ilo_tpm_visibility(build_details_dict["host"])
    if resp["TpmVisibility"] == "Hidden" and build.apply_tpm_baseline == True:
        build_id = await build_service.create_build(BuildTypes.BASELINE_HPE_TPM.value, build_details_dict, requestor)
        return StatusUriResponse(status=f"/builds/status/{build_id}")
    else:
        return resp


@router.post("/baseline/hpe/prep", tags=["HPE Server Standards Baseline"])
async def baseline_hpe_prep(
    build: ServerNameOnlyDto,
    requestor: dict = Depends(auth_service.validate_and_get_username),
):
    """
    <h2></b>check and/or apply hpe bios baseline</h2></b>
    - *payload*
        - **host**: fully qualified domain name of server/host
    """
    build_details_dict = await build_service.validate_build(build.dict())
    build_id = await build_service.create_build(BuildTypes.BASELINE_HPE_PREP.value, build_details_dict, requestor)
    return StatusUriResponse(status=f"/builds/status/{build_id}")


@router.post("/baseline/hp/spp", tags=["HPE Server Standards Baseline"])
async def baseline_hp_spp(build: ServerNameOnlyDto, requestor: dict = Depends(auth_service.validate_and_get_username)):
    """
    <h2></b>Apply Gen 9 / 10 SPP</h2></b>
    - This is the first release of the ability to apply the SPP Gen 9 / 10 physical server.
        - **host**: fully qualified domain name of server/host
    """
    build_details_dict = await build_service.validate_build(build.dict())
    build_id = await build_service.create_build(BuildTypes.BASELINE_HP_SPP.value, build_details_dict, requestor)
    return StatusUriResponse(status=f"/builds/status/{build_id}")


@router.post("/baseline/hp/checkfirmware", tags=["HPE Server Standards Baseline"])
async def baseline_hp_checkfirmware(
    build: ServerNameOnlyDto, requestor: dict = Depends(auth_service.validate_and_get_username)
):
    """
    <h2></b>Check firmware of hpe server</h2></b>
    - check firmware of hpe server agaisnt baseline current SPP version
        - **host**: fully qualified domain name of server/host
    """
    build_details_dict = await build_service.validate_build(build.dict())
    build_id = await build_service.create_build(
        BuildTypes.BASELINE_HP_CHECKFIRMWARE.value, build_details_dict, requestor
    )
    return StatusUriResponse(status=f"/builds/status/{build_id}")


@router.post("/baseline/dell/idrac", tags=["Dell Server Standards Baseline"])
async def baseline_dell_idrac(
    build: ServerNameOnlyDto,
    requestor: dict = Depends(auth_service.validate_and_get_username),
):
    """
    <h2><b>check dell idrac baseline configuration</b></h2>
    - *payload*
        - **host**: fully qualified domain name of server/host
    """
    build_details_dict = await build_service.validate_build(build.dict())
    build_id = await build_service.create_build(BuildTypes.BASELINE_DELL_IDRAC.value, build_details_dict, requestor)
    return StatusUriResponse(status=f"/builds/status/{build_id}")
