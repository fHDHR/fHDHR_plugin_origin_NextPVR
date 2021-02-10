import xmltodict
import json
import hashlib

import fHDHR.tools
import fHDHR.exceptions


class Plugin_OBJ():

    def __init__(self, plugin_utils):
        self.plugin_utils = plugin_utils

        self.login()

    @property
    def tuners(self):
        return self.plugin_utils.config.dict["nextpvr"]["tuners"]

    @property
    def stream_method(self):
        return self.plugin_utils.config.dict["nextpvr"]["stream_method"]

    @property
    def sid(self):
        return self.plugin_utils.config.dict["nextpvr"]["sid"]

    @property
    def pin(self):
        return self.plugin_utils.config.dict["nextpvr"]["pin"]

    @property
    def address(self):
        return self.plugin_utils.config.dict["nextpvr"]["address"]

    @property
    def port(self):
        return self.plugin_utils.config.dict["nextpvr"]["port"]

    @property
    def proto(self):
        return "https://" if self.plugin_utils.config.dict['nextpvr']["ssl"] else "http://"

    @property
    def address_without_creds(self):
        return '%s%s:%s' % (self.proto, self.address, str(self.port))

    def login(self):
        self.plugin_utils.logger.info("Logging into NextPVR")
        sid = self.get_sid()
        if not sid:
            raise fHDHR.exceptions.OriginSetupError("NextPVR Login Failed")
        else:
            self.plugin_utils.logger.info("NextPVR Login Success")
            self.plugin_utils.config.write('sid', sid, self.plugin_utils.namespace)

    def get_sid(self):
        if self.sid:
            return self.sid

        initiate_url = '%s/service?method=session.initiate&ver=1.0&device=fhdhr' % self.nextpvr_address

        initiate_req = self.plugin_utils.web.session.get(initiate_url)
        initiate_dict = xmltodict.parse(initiate_req.content)

        sid = initiate_dict['rsp']['sid']
        salt = initiate_dict['rsp']['salt']
        md5PIN = hashlib.md5(str(self.pin).encode('utf-8')).hexdigest()
        string = ':%s:%s' % (md5PIN, salt)
        clientKey = hashlib.md5(string.encode('utf-8')).hexdigest()

        login_url = ('%s/service?method=session.login&sid=%s&md5=%s' %
                     (self.nextpvr_address, sid, clientKey))
        login_req = self.plugin_utils.web.session.get(login_url)
        login_dict = xmltodict.parse(login_req.content)

        loginsuccess = None
        if login_dict['rsp']['@stat'] == "ok":
            if login_dict['rsp']['allow_watch'] == "true":
                loginsuccess = sid

        return loginsuccess

    def get_channel_thumbnail(self, channel_id):
        channel_thumb_url = "%s/service?method=channel.icon&channel_id=%s" % (self.address_without_creds, channel_id)
        return channel_thumb_url

    def get_channels(self):

        data_url = '%s/service?method=channel.list&sid=%s' % (self.address_without_creds, self.sid)

        data_req = self.plugin_utils.web.session.get(data_url)
        data_dict = xmltodict.parse(data_req.content)

        if 'channels' not in list(data_dict['rsp'].keys()):
            self.plugin_utils.logger.error("Could not retrieve channel list")
            return []

        channel_o_list = data_dict['rsp']['channels']['channel']

        channel_list = []
        for c in channel_o_list:
            dString = json.dumps(c)
            channel_dict = eval(dString)

            clean_station_item = {
                                 "name": channel_dict["name"],
                                 "callsign": channel_dict["name"],
                                 "number": channel_dict["formatted-number"],
                                 "id": channel_dict["id"],
                                 "thumbnail": self.get_channel_thumbnail(channel_dict["id"])
                                 }
            channel_list.append(clean_station_item)
        return channel_list

    def get_channel_stream(self, chandict, stream_args):
        streamurl = ('%s/live?channel_id=%s&client=%s' % (self.address_without_creds, chandict["origin_id"], "fhdhr_%s" % chandict["origin_number"]))

        stream_info = {"url": streamurl}

        return stream_info
