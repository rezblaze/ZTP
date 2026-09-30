from typing import Optional

from pydantic import BaseModel

from app.common.domain.supported_payload import (
    SupportedDataRaid,
    SupportedEsxiOs,
    SupportedLinuxOs,
    SupportedLinuxRole,
    SupportedWindowsOs,
)


class LinuxHostAttribute(BaseModel):
    role: SupportedLinuxRole = SupportedLinuxRole.BASE.value
    data_raid: Optional[SupportedDataRaid] = SupportedDataRaid.NORAID.value


class LinuxBuildDto(BaseModel):
    host: str = ""
    os: SupportedLinuxOs = ""
    attributes: LinuxHostAttribute
    deploy_only: Optional[bool] = False
    override: Optional[dict] = {}


class WindowsBuildDto(BaseModel):
    host: str = ""
    os: SupportedWindowsOs = ""
    attributes: dict = {"env": "", "computerdomain": "", "chef": True}
    deploy_only: Optional[bool] = False


class HpeIloBaselineDto(BaseModel):
    host: str = ""
    apply_ilo_baseline: Optional[bool] = False
    apply_ilo_firmware: Optional[bool] = False


class HpeBiosBaselineDto(BaseModel):
    host: str = ""
    apply_hpe_bios_baseline: Optional[bool] = False


class HpeTpmBaselineDto(BaseModel):
    host: str = ""
    apply_tpm_baseline: Optional[bool] = False


class EsxiHostAttribute(BaseModel):
    vlan: Optional[str] = "3020"


class EsxiBuildDto(BaseModel):
    host: str = ""
    os: SupportedEsxiOs = ""
    attributes: EsxiHostAttribute
    deploy_only: Optional[bool] = False
    override: Optional[dict] = {}


class ServerNameOnlyDto(BaseModel):
    host: str = ""


class ESKMPayload(BaseModel):
    PrimaryKeyServerAddress: str = "203.0.113.121"
    PrimaryKeyServerPort: int = 9000
    KeyManagerConfig: dict = {"ESKMLocalCACertificateName": "company-eskm-local-ca", "AccountGroup": "gen10servers"}
    KeyServerRedundancyReq: bool = True
    SecondaryKeyServerPort: int = 9000
    SecondaryKeyServerAddress: str = "203.0.113.26"
