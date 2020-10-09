import xmltodict
import json
import hashlib
import datetime

import fHDHR.tools


class fHDHRservice():
    def __init__(self, settings):
        self.config = settings

        self.web = fHDHR.tools.WebReq()

    def login(self):
        print("Logging into NextPVR")
        self.sid = self.get_sid()
        if not self.sid:
            return False
        else:
            print("NextPVR Login Success")
            self.config.write(self.config.dict["main"]["dictpopname"], 'sid', self.sid)
            return True

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

    def get_channel_thumbnail(self, channel_id):
        channel_thumb_url = ("%s%s:%s/service?method=channel.icon&channel_id=%s" %
                             ("https://" if self.config.dict["origin"]["ssl"] else "http://",
                              self.config.dict["origin"]["address"],
                              str(self.config.dict["origin"]["port"]),
                              str(channel_id)
                              ))
        return channel_thumb_url

    def get_content_thumbnail(self, content_id):
        item_thumb_url = ("%s%s:%s/service?method=channel.show.artwork&sid=%s&event_id=%s" %
                          ("https://" if self.config.dict["origin"]["ssl"] else "http://",
                           self.config.dict["origin"]["address"],
                           str(self.config.dict["origin"]["port"]),
                           self.config.dict["origin"]["sid"],
                           str(content_id)
                           ))
        return item_thumb_url

    def update_epg(self):
        programguide = {}

        for c in self.get_channels():

            cdict = fHDHR.tools.xmldictmaker(c, ["callsign", "name", "number", "id"])

            if str(cdict['number']) not in list(programguide.keys()):

                programguide[str(cdict['number'])] = {
                                                    "callsign": cdict["callsign"],
                                                    "name": cdict["name"] or cdict["callsign"],
                                                    "number": cdict["number"],
                                                    "id": str(cdict["id"]),
                                                    "thumbnail": self.get_channel_thumbnail(cdict['id']),
                                                    "listing": [],
                                                    }

            epg_url = ('%s%s:%s/service?method=channel.listings&channel_id=%s' %
                       ("https://" if self.config.dict["origin"]["ssl"] else "http://",
                        self.config.dict["origin"]["address"],
                        str(self.config.dict["origin"]["port"]),
                        str(cdict["id"]),
                        ))
            epg_req = self.web.session.get(epg_url)
            epg_dict = xmltodict.parse(epg_req.content)

            for program_listing in epg_dict["rsp"]["listings"]:
                for program_item in epg_dict["rsp"]["listings"][program_listing]:
                    if not isinstance(program_item, str):

                        progdict = fHDHR.tools.xmldictmaker(program_item, ["start", "end", "title", "name", "subtitle", "rating", "description", "season", "episode", "id", "episodeTitle"])

                        clean_prog_dict = {
                                            "time_start": self.xmltimestamp_nextpvr(progdict["start"]),
                                            "time_end": self.xmltimestamp_nextpvr(progdict["end"]),
                                            "duration_minutes": self.duration_nextpvr_minutes(progdict["start"], progdict["end"]),
                                            "thumbnail": self.get_content_thumbnail(progdict['id']),
                                            "title": progdict['name'] or "Unavailable",
                                            "sub-title": progdict['subtitle'] or "Unavailable",
                                            "description": progdict['description'] or "Unavailable",
                                            "rating": progdict['rating'] or "N/A",
                                            "episodetitle": progdict['episodeTitle'],
                                            "releaseyear": None,
                                            "genres": [],
                                            "seasonnumber": progdict['season'],
                                            "episodenumber": progdict['episode'],
                                            "isnew": False,
                                            "id": str(progdict['id'] or self.xmltimestamp_nextpvr(progdict["start"])),
                                            }

                        if 'genre' in list(progdict.keys()):
                            clean_prog_dict["genres"] = progdict['genre'].split(",")

                        if clean_prog_dict['sub-title'].startswith("Movie:"):
                            clean_prog_dict['releaseyear'] = clean_prog_dict['sub-title'].split("Movie: ")[-1]
                            clean_prog_dict['sub-title'] = "Unavailable"
                            clean_prog_dict["genres"].append("Movie")

                        # TODO isNEW

                        programguide[str(cdict["number"])]["listing"].append(clean_prog_dict)

        return programguide

    def xmltimestamp_nextpvr(self, epochtime):
        xmltime = datetime.datetime.fromtimestamp(int(epochtime)/1000)
        xmltime = str(xmltime.strftime('%Y%m%d%H%M%S')) + " +0000"
        return xmltime

    def duration_nextpvr_minutes(self, starttime, endtime):
        return ((int(endtime) - int(starttime))/1000/60)
