import xmltodict
import json


class OriginChannels():

    def __init__(self, settings, origin, logger, web):
        self.config = settings
        self.origin = origin
        self.logger = logger
        self.web = web

    def get_channels(self):

        data_url = ('%s%s:%s/service?method=channel.list&sid=%s' %
                    ("https://" if self.config.dict["origin"]["ssl"] else "http://",
                     self.config.dict["origin"]["address"],
                     str(self.config.dict["origin"]["port"]),
                     self.origin.sid
                     ))

        data_req = self.origin.web.session.get(data_url)
        data_dict = xmltodict.parse(data_req.content)

        if 'channels' not in list(data_dict['rsp'].keys()):
            self.logger.error("Could not retrieve channel list")
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
