from faust import Record


class ServerBuild(Record, serializer="json"):
    bmi_env: str
    id: str
    host: str
    build_details: dict
    time: str
    requestor: dict
    build_type: str
    networkdata: dict = {}
    serverinfo: dict = {}

    def as_dict(self):
        return {
            "bmi_env": self.bmi_env,
            "id": self.id,
            "host": self.host,
            "build_details": self.build_details,
            "time": self.time,
            "requestor": self.requestor,
            "build_type": self.build_type,
            "networkdata": self.networkdata,
            "serverinfo": self.serverinfo,
        }
