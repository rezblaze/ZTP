# -*- coding: utf-8 -*-

# pylint: disable=C0301
# pylint: disable=E1101
# pylint: disable=R0902

"""
NetworkData is  the ipv4/ipv6 information of a servername.
NetworkData contains valuable metadata/standards from external
sources.

If there is a failure in any of the external service calls, the
class will set default values of 127.0.0.1. The developer can
use this for error handling.
"""

import json
import logging
import os
import socket
import stat

import urllib3

from ._common import if_resp_not_ok, log_my_msg
from ._hardware import get_hardware_vendor, get_hpe_model
from ._session import create_requests_retry_no_token_auth
from .exception import ServerNotInDNSException
from .sanitycheck import check_if_host_in_dns

__author__ = "David Blasing, Chirag Patel, Joel E Carlson"
__email__ = "support@example.com"

logger = logging.getLogger(__name__)

no_token_sessobj = create_requests_retry_no_token_auth()


class NetworkData:
    """
    NetworkData class

    :param servername: str
    :return: :class:`NetworkData`
    """

    def __init__(self, servername):
        log_my_msg("*** ZTP NetworkData module ***")
        if not check_if_host_in_dns(servername):
            raise ServerNotInDNSException
        self.server_name = set_servername(servername)
        self.server_shortname = get_short_name(self.server_name)
        self.server_ip = get_host_ip(self.server_name)
        self.server_domain = get_domain(self.server_name)
        self.lom = self.server_shortname + "lo"
        self.lom_fqdn = self.lom + ".example.com"
        if not check_if_host_in_dns(self.lom_fqdn):
            log_my_msg(f"{self.lom_fqdn} not found in DNS using {self.lom}.{self.server_domain}.")
            self.lom_fqdn = self.lom + "." + self.server_domain
        self.lom_ip = get_lom_ip(self.lom_fqdn)
        self.vendor = get_hardware_vendor(self.lom_ip)
        self.ea = get_ea(self.server_name)
        self.datacenter = get_datacenter(self.ea["SiteCode"])
        self.zone = self.ea["Zone"]
        self.subnet = self.ea["Mask"]
        self.network = self.ea["Subnet"]
        self.gateway = self.ea["Gateway"]
        if self.vendor == "hpe":
            data = get_hpe_model(self.lom_ip)
            self.generation = data.split()[2]
            self.model = data.split()[1]
        elif self.vendor == "hp":
            self.generation = "gen9"
        elif self.vendor == "dell":
            self.generation = None
        self.standard = get_hpe_standards(self.datacenter, self.generation, self.zone)
        self.bu_servername = self.server_shortname + "bu" + "." + self.server_domain
        if check_if_host_in_dns(self.bu_servername) is True:
            self.bu_server_shortname = self.server_shortname + "bu"
            self.bu_server_ip = get_host_ip(self.bu_servername)
            self.ea = get_ea(self.bu_servername)
            self.bu_subnet = self.ea["Mask"]
            self.bu_gateway = self.ea["Gateway"]
        else:
            self.bu_servername = False

    def __repr__(self):
        return (
            f"NetworkData({self.server_name!r}"
            f", {self.server_ip!r}"
            f", {self.ea!r}"
            f", {self.datacenter!r}"
            f", {self.standard!r}"
            f")"
        )

    def get_lom_ip(self):
        """
        get_lom_ip

        example.com is domain for DC

        :return: str
        """
        if self.server_name in ["localhost.localdomain", "localhost"]:
            return "127.0.0.1"
        short_name = get_short_name(self.server_name) + "lo"
        domain_name = get_domain(self.server_name)
        domain_name = "example.com"
        lom_name = short_name + "." + domain_name
        lom_ip = get_host_ip(lom_name)
        return lom_ip

    def get_bu_ip(self):
        """
        get_bu_ip

        :return: str
        """
        if self.server_name in ["localhost.localdomain", "localhost"]:
            return "127.0.0.1"
        short_name = get_short_name(self.server_name) + "bu"
        domain_name = get_domain(self.server_name)
        bu_name = short_name + "." + domain_name
        bu_ip = get_host_ip(bu_name)
        return bu_ip

    def all_networkdata(self):
        """
        all_networkdata

        :return: allnetworkdata for server
        """
        data_upper = {
            "HARDWARE": self.vendor,
            "SERVERNAME": self.server_name,
            "SHORT_NAME": self.server_shortname,
            "DOMAIN": self.server_domain,
            "LOM": self.lom,
            "LOM_FQDN": self.lom_fqdn,
            "LOMIP": self.lom_ip,
            "DC": self.datacenter,
            "ZONE": self.zone,
            "IP": self.server_ip,
            "NETMASK": self.subnet,
            "GATEWAY": self.gateway,
            "BU_SERVERNAME": None if not self.bu_servername else self.bu_servername,
            "BU_IP": None if not self.bu_servername else self.bu_server_ip,
            "BU_NETMASK": None if not self.bu_servername else self.bu_subnet,
            "BU_GATEWAY": None if not self.bu_servername else self.bu_gateway,
        }
        if self.vendor == "hpe":
            generation = {"GENERATION": self.generation}
            data_upper.update(generation)
            model = {"MODEL": self.model}
            data_upper.update(model)

        data_upper.update(self.standard)

        # data = {}
        # for k, v in data_upper.items():
        #     if v is not None:
        #         newval = v.lower()
        #     data.update({k.lower(): v})
        # data.update(data_upper)

        return data_upper

    @classmethod
    def localhost_localdomain(cls):
        """:return: :class:`NetworkData`"""
        return cls("localhost.localdomain")

    @classmethod
    def localhost(cls):
        """:return: :class:`NetworkData`"""
        return cls("localhost")

    @staticmethod
    def cidr(netmask):
        """
        cidr calc

        :param netmask: str
        :return: int
        """
        return cidr(netmask)

    @staticmethod
    def standards(location):
        """
        Platform Standards

        :param location: str
        :return: dict
        """
        return get_hpe_standards(location, "gen10")


###
### Helper Functions
###

# GLOBALS
LOOP = "127.0.0.1"
NET = "127.0.0.0"
MASK = "255.0.0.0"
LOCALHOST = "localhost.localdomain"

urllib3.disable_warnings()


def _range(*args, **kwargs):
    """
    _range helper function

    :param *args: (int)
    :param **kwargs: (int)
    :return: [int]
    """
    return list(range(*args, **kwargs))


def bytes_to_bits():
    """
    bytes_to_bits

    :return: str
    """
    lookup = []
    bits_per_byte = _range(7, -1, -1)
    for num in range(256):
        bits = 8 * [None]
        for i in bits_per_byte:
            bits[i] = "01"[num & 1]
            num >>= 1
        lookup.append("".join(bits))
    return lookup


BYTES_TO_BITS = bytes_to_bits()


def cidr(netmask=MASK):
    """
    calculate cidr

    :param netmask: str
    :return: int
    """
    numbits = 0
    for i in netmask.split("."):
        part = int_to_bits(int(i), 8, 1)
        for j in list(part):
            numbits += int(j)
    return numbits


def error_on_none(status):
    """
    error_on_none exit if no value

    :params status: dict
    """
    for key, value in status.items():
        if value is None:
            logger.critical(" - FAIL: %s:%s has no value.", key, value)
            raise Exception()


def get_domain(hostname):
    """
    get_domain

    :param hostname: str
    :return: str
    """
    if hostname in ["localhost", "localhost.localdomain"]:
        return "localdomain"
    return hostname.split(".", 1)[1]


def get_gateway(network, netmask):
    """
    get_gateway

    :param network: str
    :param netmask: str
    :return: str
    """
    gateway = [0, 0, 0, 0]
    net = network.split(".")
    mask = netmask.split(".")
    for i in range(4):
        gateway[i] = int(net[i]) & int(mask[i])
    gateway[3] = gateway[3] + 1
    return "%d.%d.%d.%d" % (gateway[0], gateway[1], gateway[2], gateway[3])


def get_host_ip(hostname):
    """
    get_host_ip

    :param hostname: str
    :return: str
    """
    ip_address = "127.0.0.1"
    if hostname in ["localhost", "localhost.localdomain"]:
        return ip_address
    try:
        ip_address = socket.gethostbyname(hostname)
    except socket.error as err:
        log_my_msg(f"get_host_ip error: {err}")
    return ip_address


def get_ea(hostname):
    """eaws.example.com standards"""
    header = {"Content-Type": "application/xml"}
    ip_address = get_host_ip(hostname)
    # url = "http://eaws.example.com/HardwareReadinessService/Hardware.svc/v1/ipam/GetIpInfo/ip=%s" % (ip_address)
    # print(url)
    url = "http://it-capacity-ws.example.com/HardwareReadinessService/Hardware.svc/v1/ipam/GetIpInfo/ip=%s" % (ip_address)
    resp = no_token_sessobj.get(url)
    if_resp_not_ok(resp)
    data = resp.json()
    ea_data = next(iter(data))
    if "bu." in hostname:
        return ea_data
    zone = get_dmz(hostname, ea_data["Subnet"])
    ea_data.update(Zone=zone)
    return ea_data


def get_loran(hostname, network_ip):
    """eaws.example.com standards"""
    ip = get_host_ip(hostname)
    if network_ip is None:
        network_ip = ".".join(ip.split(".")[0:-1]) + ".0"
    # print(f"get_loran: {network_ip}")
    url = f"https://loran-core-stage.example.com/config/subnet/{network_ip}"
    try:
        resp = no_token_sessobj.get(url)
        data = resp.json()
    except:
        log_my_msg("network_zone_code key not found setting it to INTRA")
        data = {
            "network_zone_code": "NONE-INTRA",
        }
    return data


def int_to_words(int_val, word_size, num_words):
    """
    int_to_wordss

    :param int_val: int
    :param word_size: int
    :param num_words: int
    :return: str
    """
    max_int = 2 ** (num_words * word_size) - 1
    max_word = 2**word_size - 1
    words = []
    if int_val > max_int:
        return 0
    for _ in range(num_words):
        word = int_val & max_word
        words.append(int(word))
        int_val >>= word_size
    return tuple(reversed(words))


def int_to_bits(int_val, word_size, num_words, word_sep=""):
    """
    int_to_bits

    :param int_val: int
    :param word_size: int
    :param num_words: int
    :param word_sep: str
    :return: str
    """
    bit_words = []
    for word in int_to_words(int_val, word_size, num_words):
        bits = []
        while word:
            bits.append(BYTES_TO_BITS[word & 255])
            word >>= 8
        bits.reverse()
        bit_str = "".join(bits) or "0" * word_size
        bits = ("0" * word_size + bit_str)[-word_size:]
        bit_words.append(bits)
    return word_sep.join(bit_words)


def get_datacenter(loc):
    """
    get_datacenter

    :param mailcode: str
    :return: str
    """
    if loc == "site_a":
        return "SITE_A"
    else:
        return "SITE_B"


def set_servername(servername):
    """
    set_servername

    :param servername: str
    :return: str
    """
    return socket.getfqdn(servername)


def get_short_name(hostname):
    """
    get_short_name

    :param hostname: str
    :return: str
    """
    if hostname in ["localhost", "localhost.localdomain"]:
        return "localhost"
    return hostname.split(".", 1)[0]


def get_hpe_standards(location, generation, zone):
    """
    HW/OS Standards

    :param location: str
    :return: dict
    """
    header = {"Content-Type": "application/json"}
    url = "http://bmi-prod.example.com/pub/tools/build_files/hpe_variables.json"
    resp = no_token_sessobj.get(url)
    if_resp_not_ok(resp)
    filename = "/var/tmp/hpe_variables.json"
    if os.name == "nt":
        filename = "hpe_variables.json"
    write_file(filename, resp.text)
    return parse_json(filename, location, generation, zone)


def get_dmz(hostname, network):
    data = get_loran(hostname, network)
    # print(f"fn:get_dmz: {data}")
    # if "INTER" in data.get("network_zone_code", "null"):
    return data.get("network_zone_code", "null")


def parse_json(filename, location, generation, zone):
    """
    parse_json

    :param filename: str
    :param locations: str
    :param generation: str
    :return: dict
    """
    if "INTER" in zone:
        location = "DMZ"
    standard = {}
    with open(filename) as stream:
        data = json.load(stream)
    log_my_msg(data) 
    if generation is None:
        for key, value in data[location].items():
            if key in ["DNS1", "DNS2", "DNS3"]:
                standard.update({key.upper(): value})
    else:
        for key, value in data["Global"].items():
            if key in ["time1", "time2", "SiteAEskm", "SiteBEskm", "EskmUser", "EskmPass"]:
                standard.update({key.upper(): value})
        for key, value in data[location].items():
            if key in [
                "DNS1",
                "DNS2",
                "DNS3",
                "eskm_pri",
                "eskm_secondary",
                "timezone",
            ]:
                standard.update({key.upper(): value})
        for key, value in data[generation].items():
            if key in ["eskm_group", "eskm_key"]:
                standard.update({key.upper(): value})
    return standard


def write_file(filename, contents):
    """
    write_file

    :param filename: str
    :param contents: [str]
    """
    with open(filename, "w") as stream:
        stream.write(contents)
    set_perms(filename)


def get_lom_ip(lom):
    """
    function to get lom ip

    :param server: str
    :return: str
    """
    return socket.gethostbyname(lom)


def set_perms(filename):
    """
    set_perms

    :param filename: str
    """
    status = os.stat(filename)
    os.chmod(filename, status.st_mode | stat.S_IROTH)
