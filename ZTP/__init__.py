""" ZTP module
"""

from setuptools import setup

from .__version__ import (
    __author__,
    __author_email__,
    __description__,
    __license__,
    __title__,
    __url__,
    __version__,
)
from .action import Actions
from .dell import DellServer
from .hphpe import HpHpeServer
from .idrac import DellidracActions
from .ilo import HpeiloActions
from .immutable import Immutable
from .networkdata import NetworkData
from .sanitycheck import check_if_host_in_dns, check_if_host_ping
from .secrets import get_lom_creds
from .serverhealth import esxi_server_health, rhel_server_health
