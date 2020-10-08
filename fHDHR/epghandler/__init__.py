import time

from fHDHR.epghandler import epgtypes, xmltv


class EPGhandler():

    def __init__(self, settings, origserv):
        self.config = settings

        self.epg_method = self.config.dict["fhdhr"]["epg_method"]
        if self.epg_method:
            self.sleeptime = self.config.dict[self.epg_method]["epg_update_frequency"]

        self.epgtypes = epgtypes.EPGTypes(settings, origserv)
        self.xmltv = xmltv.xmlTV(settings)

    def get_xmltv(self, base_url):
        epgdict = self.epgtypes.get_epg()
        return self.xmltv.create_xmltv(base_url, epgdict)

    def get_thumbnail(self, itemtype, itemid):
        return self.epgtypes.get_thumbnail(itemtype, itemid)


def epgServerProcess(settings, epghandling):
    print("Starting EPG thread...")
    try:

        while True:
            epghandling.epgtypes.update()
            time.sleep(epghandling.sleeptime)

    except KeyboardInterrupt:
        pass
