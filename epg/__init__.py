import xmltodict

import fHDHR.tools


class Plugin_OBJ():

    def __init__(self, channels, plugin_utils):
        self.plugin_utils = plugin_utils

        self.channels = channels

        self.origin = plugin_utils.origin

    def get_content_thumbnail(self, content_id):
        item_thumb_url = ("%s%s:%s/service?method=channel.show.artwork&sid=%s&event_id=%s" %
                          ("https://" if self.fhdhr.config.dict["nextpvr"]["ssl"] else "http://",
                           self.fhdhr.config.dict["nextpvr"]["address"],
                           str(self.fhdhr.config.dict["nextpvr"]["port"]),
                           self.fhdhr.config.dict["nextpvr"]["sid"],
                           str(content_id)
                           ))
        return item_thumb_url

    def duration_nextpvr_minutes(self, starttime, endtime):
        return ((int(endtime) - int(starttime))/1000/60)

    def update_epg(self):
        programguide = {}

        for fhdhr_channel_id in list(self.channels.list.keys()):
            chan_obj = self.channels.list[fhdhr_channel_id]

            if str(chan_obj.number) not in list(programguide.keys()):

                programguide[str(chan_obj.number)] = chan_obj.epgdict

            epg_url = ('%s%s:%s/service?method=channel.listings&channel_id=%s' %
                       ("https://" if self.fhdhr.config.dict["nextpvr"]["ssl"] else "http://",
                        self.fhdhr.config.dict["nextpvr"]["address"],
                        str(self.fhdhr.config.dict["nextpvr"]["port"]),
                        str(chan_obj.dict["origin_id"]),
                        ))
            epg_req = self.fhdhr.web.session.get(epg_url)
            epg_dict = xmltodict.parse(epg_req.content)

            for program_listing in epg_dict["rsp"]["listings"]:
                for program_item in epg_dict["rsp"]["listings"][program_listing]:
                    if not isinstance(program_item, str):

                        progdict = fHDHR.tools.xmldictmaker(program_item, ["start", "end", "title", "name", "subtitle", "rating", "description", "season", "episode", "id", "episodeTitle"])

                        clean_prog_dict = {
                                            "time_start": (int(progdict["start"]) / 1000),
                                            "time_end": (int(progdict["end"]) / 1000),
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
                                            "id": str(progdict['id'] or "%s_%s" % (chan_obj.dict['origin_id'], progdict["start"])),
                                            }

                        if 'genre' in list(progdict.keys()):
                            clean_prog_dict["genres"] = progdict['genre'].split(",")

                        if clean_prog_dict['sub-title'].startswith("Movie:"):
                            clean_prog_dict['releaseyear'] = clean_prog_dict['sub-title'].split("Movie: ")[-1]
                            clean_prog_dict['sub-title'] = "Unavailable"
                            clean_prog_dict["genres"].append("Movie")

                        # TODO isNEW

                        if not any((d['time_start'] == clean_prog_dict['time_start'] and d['id'] == clean_prog_dict['id']) for d in programguide[chan_obj.number]["listing"]):
                            programguide[str(chan_obj.number)]["listing"].append(clean_prog_dict)

        return programguide
