import os
import xmltodict
import json
import hashlib
import datetime
import urllib.error
import urllib.parse
import urllib.request


class NextPVR_Auth():
    config = {
            'npvrURL': '',
            'npvrSID': '',
            'npvrPIN': '',
            }
    sidfile = None

    def __init__(self, config):
        self.sidfile = config.config["nextpvr"]["sidfile"]
        self.config["npvrPIN"] = config.config["nextpvr"]["pin"]
        self.config["npvrURL"] = ('%s%s:%s' %
                                  ("https://" if config.config["nextpvr"]["ssl"] else "http://",
                                   config.config["nextpvr"]["address"],
                                   str(config.config["nextpvr"]["port"]),
                                   ))

    def _check_sid(self):
        if 'sid' not in self.config:
            if os.path.isfile(self.sidfile):
                with open(self.sidfile, 'r') as text_file:
                    self.config['sid'] = text_file.read()
                print('Read SID from file.')
            else:
                self._get_sid()

        return True

    def _get_sid(self):
        sid = ''
        salt = ''
        clientKey = ''

        initiate_url = "%s/service?method=session.initiate&ver=1.0&device=fhdhr" % self.config['npvrURL']

        initiate_req = urllib.request.urlopen(initiate_url)
        initiate_dict = xmltodict.parse(initiate_req)

        sid = initiate_dict['rsp']['sid']
        salt = initiate_dict['rsp']['salt']
        md5PIN = hashlib.md5(self.config['npvrPIN'].encode('utf-8')).hexdigest()
        string = ':%s:%s' % (md5PIN, salt)
        clientKey = hashlib.md5(string.encode('utf-8')).hexdigest()

        login_url = '%s/service?method=session.login&sid=%s&md5=%s' % (self.config['npvrURL'], sid, clientKey)
        login_req = urllib.request.urlopen(login_url)
        login_dict = xmltodict.parse(login_req)

        if login_dict['rsp']['allow_watch'] == "true":
            self.config['sid'] = sid
            with open(self.sidfile, 'w') as text_file:
                text_file.write(self.config['sid'])
            print('Wrote SID to file.')
        else:
            print("NextPVR Login Failed")
            self.config['sid'] = ''


def xmltimestamp_nextpvr(epochtime):
    xmltime = datetime.datetime.fromtimestamp(int(epochtime)/1000)
    xmltime = str(xmltime.strftime('%Y%m%d%H%M%S')) + " +0000"
    return xmltime


def duration_nextpvr_minutes(starttime, endtime):
    return ((int(endtime) - int(starttime))/1000/60)


class proxyserviceFetcher():

    def __init__(self, config):
        self.config = config.config

        self.epg_cache = None
        self.epg_cache_file = config.config["nextpvr"]["epg_cache"]

        self.servicename = "NextPVRProxy"

        self.urls = {}
        self.url_assembler()

        self.auth = NextPVR_Auth(config)

        self.epg_cache = self.epg_cache_open()

    def epg_cache_open(self):
        epg_cache = None
        if os.path.isfile(self.epg_cache_file):
            with open(self.epg_cache_file, 'r') as epgfile:
                epg_cache = json.load(epgfile)
        return epg_cache

    def url_assembler(self):
        pass

    def get_channels(self):
        self.auth._check_sid()

        url = ('%s%s:%s/service?method=channel.list&sid=%s' %
               ("https://" if self.config["nextpvr"]["ssl"] else "http://",
                self.config["nextpvr"]["address"],
                str(self.config["nextpvr"]["port"]),
                self.auth.config['sid']
                ))

        r = urllib.request.urlopen(url)
        data_dict = xmltodict.parse(r)

        if 'channels' not in list(data_dict['rsp'].keys()):
            print("could not retrieve channel list")
            return []

        channel_o_list = data_dict['rsp']['channels']['channel']

        channel_list = []
        for c in channel_o_list:
            dString = json.dumps(c)
            channel_dict = eval(dString)
            clean_station_item = {
                                 "name": channel_dict["name"],
                                 "number": channel_dict["formatted-number"],
                                 "id": channel_dict["id"],
                                 }
            channel_list.append(clean_station_item)
        return channel_list

    def get_station_list(self, base_url):
        station_list = []

        for c in self.get_channels():
            if self.config["fakehdhr"]["stream_type"] == "ffmpeg":
                watchtype = "ffmpeg"
            else:
                watchtype = "direct"
            url = ('%s%s/watch?method=%s&channel=%s' %
                   ("http://",
                    base_url,
                    watchtype,
                    c['number']
                    ))
            station_list.append(
                                {
                                 'GuideNumber': str(c['number']),
                                 'GuideName': c['name'],
                                 'URL': url
                                })
        return station_list

    def get_station_total(self):
        total_channels = 0
        for c in self.get_channels():
            total_channels += 1
        return total_channels

    def get_channel_streams(self):
        streamdict = {}
        for c in self.get_channels():
            url = ('%s%s:%s/live?channel=%s&client=%s' %
                   ("https://" if self.config["nextpvr"]["ssl"] else "http://",
                    self.config["nextpvr"]["address"],
                    str(self.config["nextpvr"]["port"]),
                    str(c["number"]),
                    str(c["number"]),
                    ))
            streamdict[str(c["number"])] = url
        return streamdict

    def get_channel_thumbnail(self, channel_id):
        channel_thumb_url = ("%s%s:%s/service?method=channel.icon&channel_id=%s" %
                             ("https://" if self.config["nextpvr"]["ssl"] else "http://",
                              self.config["nextpvr"]["address"],
                              str(self.config["nextpvr"]["port"]),
                              str(channel_id)
                              ))
        return channel_thumb_url

    def get_content_thumbnail(self, content_id):
        self.auth._check_sid()
        item_thumb_url = ("%s%s:%s/service?method=channel.show.artwork&sid=%s&event_id=%s" %
                          ("https://" if self.config["nextpvr"]["ssl"] else "http://",
                           self.config["nextpvr"]["address"],
                           str(self.config["nextpvr"]["port"]),
                           self.auth.config['sid'],
                           str(content_id)
                           ))
        return item_thumb_url

    def update_epg(self):
        print('Updating NextPVR EPG cache file.')
        self.auth._check_sid()

        programguide = {}

        for c in self.get_channels():
            if str(c["number"]) not in list(programguide.keys()):
                programguide[str(c["number"])] = {}

            channel_thumb_path = ("/images?source=proxy&type=channel&id=%s" % (str(c['id'])))
            programguide[str(c["number"])]["thumbnail"] = channel_thumb_path

            if "name" not in list(programguide[str(c["number"])].keys()):
                programguide[str(c["number"])]["name"] = c["name"]

            if "callsign" not in list(programguide[str(c["number"])].keys()):
                programguide[str(c["number"])]["callsign"] = c["name"]

            if "id" not in list(programguide[str(c["number"])].keys()):
                programguide[str(c["number"])]["id"] = c["id"]

            if "number" not in list(programguide[str(c["number"])].keys()):
                programguide[str(c["number"])]["number"] = c["number"]

            if "listing" not in list(programguide[str(c["number"])].keys()):
                programguide[str(c["number"])]["listing"] = []

            epg_url = ('%s%s:%s/service?method=channel.listings&channel_id=%s' %
                       ("https://" if self.config["nextpvr"]["ssl"] else "http://",
                        self.config["nextpvr"]["address"],
                        str(self.config["nextpvr"]["port"]),
                        str(c["id"]),
                        ))
            epg_req = urllib.request.urlopen(epg_url)
            epg_dict = xmltodict.parse(epg_req)

            for program_listing in epg_dict["rsp"]["listings"]:
                for program_item in epg_dict["rsp"]["listings"][program_listing]:
                    if not isinstance(program_item, str):
                        dirty_prog_dict = {}
                        for programkey in list(program_item.keys()):
                            dirty_prog_dict[programkey] = program_item[programkey]

                        clean_prog_dict = {}

                        clean_prog_dict["time_start"] = xmltimestamp_nextpvr(dirty_prog_dict["start"])
                        clean_prog_dict["time_end"] = xmltimestamp_nextpvr(dirty_prog_dict["end"])
                        clean_prog_dict["duration_minutes"] = duration_nextpvr_minutes(dirty_prog_dict["start"], dirty_prog_dict["end"])

                        item_thumb_path = ("/images?source=proxy&type=content&id=%s" % (str(dirty_prog_dict['id'])))
                        clean_prog_dict["thumbnail"] = item_thumb_path

                        if 'name' not in list(dirty_prog_dict.keys()):
                            dirty_prog_dict["name"] = "Unavailable"
                        elif not dirty_prog_dict["name"]:
                            dirty_prog_dict["name"] = "Unavailable"
                        clean_prog_dict["title"] = dirty_prog_dict["name"]

                        if 'genre' not in list(dirty_prog_dict.keys()):
                            clean_prog_dict["genres"] = []
                        else:
                            clean_prog_dict["genres"] = dirty_prog_dict['genre'].split(",")

                        if 'subtitle' not in list(dirty_prog_dict.keys()):
                            dirty_prog_dict["subtitle"] = "Unavailable"
                        clean_prog_dict["sub-title"] = dirty_prog_dict["subtitle"]

                        if dirty_prog_dict['subtitle'].startswith("Movie:"):
                            clean_prog_dict['releaseyear'] = dirty_prog_dict['subtitle'].split("Movie:")[-1]
                        else:
                            clean_prog_dict['releaseyear'] = None

                        if 'description' not in list(dirty_prog_dict.keys()):
                            dirty_prog_dict["description"] = "Unavailable"
                        elif dirty_prog_dict['description']:
                            dirty_prog_dict["description"] = "Unavailable"
                        clean_prog_dict["description"] = dirty_prog_dict["description"]

                        if 'rating' not in list(dirty_prog_dict.keys()):
                            dirty_prog_dict['rating'] = "N/A"
                        clean_prog_dict['rating'] = dirty_prog_dict['rating']

                        if 'season' in list(dirty_prog_dict.keys()) and 'episode' in list(dirty_prog_dict.keys()):
                            clean_prog_dict["seasonnumber"] = dirty_prog_dict['season']
                            clean_prog_dict["episodenumber"] = dirty_prog_dict['episode']
                            clean_prog_dict["episodetitle"] = clean_prog_dict["sub-title"]
                        else:
                            if "movie" not in clean_prog_dict["genres"]:
                                clean_prog_dict["episodetitle"] = clean_prog_dict["sub-title"]

                        # TODO isNEW

                        programguide[str(c["number"])]["listing"].append(clean_prog_dict)

        self.epg_cache = programguide
        with open(self.epg_cache_file, 'w') as epgfile:
            epgfile.write(json.dumps(programguide, indent=4))
        print('Wrote updated NextPVR EPG cache file.')
        return programguide
