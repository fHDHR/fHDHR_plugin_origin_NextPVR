import xmltodict
import hashlib

import fHDHR.tools
import fHDHR.exceptions


class OriginService():

    def __init__(self, fhdhr):
        self.fhdhr = fhdhr

        self.nextpvr_address = ('%s%s:%s' %
                                ("https://" if self.fhdhr.config.dict["origin"]["ssl"] else "http://",
                                 self.fhdhr.config.dict["origin"]["address"],
                                 str(self.fhdhr.config.dict["origin"]["port"]),
                                 ))

        self.login()

    def login(self):
        self.fhdhr.logger.info("Logging into NextPVR")
        self.sid = self.get_sid()
        if not self.sid:
            raise fHDHR.exceptions.OriginSetupError("NextPVR Login Failed")
        else:
            self.fhdhr.logger.info("NextPVR Login Success")
            self.fhdhr.config.write(self.fhdhr.config.dict["main"]["dictpopname"], 'sid', self.sid)

    def get_sid(self):
        if self.fhdhr.config.dict["origin"]["sid"]:
            return self.fhdhr.config.dict["origin"]["sid"]

        initiate_url = '%s/service?method=session.initiate&ver=1.0&device=fhdhr' % self.nextpvr_address

        initiate_req = self.fhdhr.web.session.get(initiate_url)
        initiate_dict = xmltodict.parse(initiate_req.content)

        sid = initiate_dict['rsp']['sid']
        salt = initiate_dict['rsp']['salt']
        md5PIN = hashlib.md5(str(self.fhdhr.config.dict["origin"]['pin']).encode('utf-8')).hexdigest()
        string = ':%s:%s' % (md5PIN, salt)
        clientKey = hashlib.md5(string.encode('utf-8')).hexdigest()

        login_url = ('%s/service?method=session.login&sid=%s&md5=%s' %
                     (self.nextpvr_address, sid, clientKey))
        login_req = self.fhdhr.web.session.get(login_url)
        login_dict = xmltodict.parse(login_req.content)

        loginsuccess = None
        if login_dict['rsp']['@stat'] == "ok":
            if login_dict['rsp']['allow_watch'] == "true":
                loginsuccess = sid

        return loginsuccess
