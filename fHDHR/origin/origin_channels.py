import xmltodict
import json
import hashlib

import fHDHR.tools
import fHDHR.exceptions


class OriginService():

    def __init__(self, settings):
        self.config = settings

        self.web = fHDHR.tools.WebReq()
        self.login()

    def login(self):
        print("Logging into NextPVR")
        self.sid = self.get_sid()
        if not self.sid:
            raise fHDHR.exceptions.OriginSetupError("NextPVR Login Failed")
        else:
            print("NextPVR Login Success")
            self.config.write(self.config.dict["main"]["dictpopname"], 'sid', self.sid)

    def get_sid(self):
        if self.config.dict["origin"]["sid"]:
            return self.config.dict["origin"]["sid"]

        initiate_url = ('%s%s:%s/service?method=session.initiate&ver=1.0&device=fhdhr' %
                        ("https://" if self.config.dict["origin"]["ssl"] else "http://",
                         self.config.dict["origin"]["address"],
                         str(self.config.dict["origin"]["port"]),
                         ))

        initiate_req = self.web.session.get(initiate_url)
        initiate_dict = xmltodict.parse(initiate_req.content)

        sid = initiate_dict['rsp']['sid']
        salt = initiate_dict['rsp']['salt']
        md5PIN = hashlib.md5(str(self.config.dict["origin"]['pin']).encode('utf-8')).hexdigest()
        string = ':%s:%s' % (md5PIN, salt)
        clientKey = hashlib.md5(string.encode('utf-8')).hexdigest()

        login_url = ('%s%s:%s/service?method=session.login&sid=%s&md5=%s' %
                     ("https://" if self.config.dict["origin"]["ssl"] else "http://",
                      self.config.dict["origin"]["address"],
                      str(self.config.dict["origin"]["port"]),
                      sid,
                      clientKey
                      ))
        login_req = self.web.session.get(login_url)
        login_dict = xmltodict.parse(login_req.content)

        loginsuccess = None
        if login_dict['rsp']['@stat'] == "ok":
            if login_dict['rsp']['allow_watch'] == "true":
                loginsuccess = sid

        return loginsuccess

    def get_status_dict(self):
        ret_status_dict = {}
        return ret_status_dict

    def get_channels(self):

        data_url = ('%s%s:%s/service?method=channel.list&sid=%s' %
                    ("https://" if self.config.dict["origin"]["ssl"] else "http://",
                     self.config.dict["origin"]["address"],
                     str(self.config.dict["origin"]["port"]),
                     self.sid
                     ))

        data_req = self.web.session.get(data_url)
        data_dict = xmltodict.parse(data_req.content)

        if 'channels' not in list(data_dict['rsp'].keys()):
            print("Could not retrieve channel list")
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
                                 }
            channel_list.append(clean_station_item)
        return channel_list

    def get_channel_stream(self, chandict, allchandict):
        caching = True
        streamlist = []
        streamdict = {}
        streamurl = ('%s%s:%s/live?channel=%s&client=%s' %
                     ("https://" if self.config.dict["origin"]["ssl"] else "http://",
                      self.config.dict["origin"]["address"],
                      str(self.config.dict["origin"]["port"]),
                      str(chandict["number"]),
                      str(chandict["number"]),
                      ))
        streamdict = {"number": chandict["number"], "stream_url": streamurl}
        streamlist.append(streamdict)
        return streamlist, caching
