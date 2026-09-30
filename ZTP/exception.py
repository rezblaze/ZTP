# -*- coding: utf-8 -*-
""" Custom Exception
"""
__author__ = "David Blasing, Chirag Patel, Joel Carlson"
__email__ = "support@example.com"


class PowerOnException(Exception):
    """ZTP Exception"""

    def __init__(self):
        message = "ZTPException: server is power on, power it off to execute ZTP automation"
        super().__init__(message)


class ServerPingsException(Exception):
    """ZTP Exception"""

    def __init__(self):
        message = "ZTPException: server/host primary network ip address pings over network"
        super().__init__(message)


class ServerNotInDNSException(Exception):
    """ZTP Exception"""

    def __init__(self):
        message = "ZTPException: server/host name is not in corporate dns"
        super().__init__(message)


class UnsupportedByZTP(Exception):
    """ZTP Exception"""

    def __init__(self):
        message = "ZTPException: not supported by ZTP package at this moment"
        super().__init__(message)


class UnsupportedHardware(Exception):
    """ZTP Exception"""

    def __init__(self):
        message = "ZTPException: unsupported hardware type found"
        super().__init__(message)


class PrimaryNetworkGWUnreachable(Exception):
    """ZTP Exception"""

    def __init__(self):
        message = "ZTPException: unable reach gateway on primary network adapter"
        super().__init__(message)


class UnsupportedFirmware(Exception):
    """ZTP Exception"""

    def __init__(self):
        message = "ZTPException: unsupported firmware type found"
        super().__init__(message)


class PrimaryMacNotFound(Exception):
    """ZTP Exception"""

    def __init__(self):
        message = "ZTPException: primary network adapter mac address not found and/or not provided"
        super().__init__(message)


class HpGen9ilo4EskmBug(Exception):
    """ZTP Exception"""

    def __init__(self):
        message = "ZTPException: known bug with HP Gen9/ilo4 while applying ESKM settings \nBug: if ilo at some point was connected to ESKM server and iLO Account name was generated and action to ESKM api call returns exception\nSolution: manually add one eskm server ip and port in ilo Key Manager Servers and run automation again! "
        super().__init__(message)
