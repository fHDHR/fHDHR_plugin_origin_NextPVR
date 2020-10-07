import os
import json
from collections import OrderedDict

from fHDHR.epghandler.epgtypes import blocks, zap2it


class EPGTypes():

    def __init__(self, settings, origserv):
        self.config = settings
        self.origin = origserv

        self.blocks = blocks.BlocksEPG(settings, origserv)
        self.zap2it = zap2it.ZapEPG(settings, origserv)

        self.epg_method = self.config.dict["fhdhr"]["epg_method"]
        if self.epg_method:
            self.epg_cache_file = self.config.dict["filedir"]["epg_cache"][self.epg_method]["epg_json"]

            self.epgtypename = self.epg_method
            if self.epg_method == self.config.dict["main"]["dictpopname"] or self.epg_method == "origin":
                self.epgtypename = self.config.dict["main"]["dictpopname"]

    def get_epg(self):
        epgdict = None
        if os.path.isfile(self.epg_cache_file):
            with open(self.epg_cache_file, 'r') as epgfile:
                epgdict = json.load(epgfile)
        return epgdict

    def get_thumbnail(self, itemtype, itemid):
        epgdict = self.get_epg()
        if itemtype == "channel":
            for channel in list(epgdict.keys()):
                if epgdict[channel]["id"] == itemid:
                    return epgdict[channel]["thumbnail"]
        elif itemtype == "content":
            for channel in list(epgdict.keys()):
                for progitem in epgdict[channel]["listing"]:
                    if progitem["id"] == itemid:
                        return progitem["thumbnail"]
        return None

    def update(self):

        print("Updating " + self.epgtypename + " EPG cache file.")
        method_to_call = getattr(self, self.epg_method)
        func_to_call = getattr(method_to_call, 'update_epg')
        programguide = func_to_call()

        programguide = OrderedDict(sorted(programguide.items()))
        for cnum in programguide:
            programguide[cnum]["listing"] = sorted(programguide[cnum]["listing"], key=lambda i: i['time_start'])

        with open(self.epg_cache_file, 'w') as epgfile:
            epgfile.write(json.dumps(programguide, indent=4))
        print("Wrote " + self.epgtypename + " EPG cache file.")
