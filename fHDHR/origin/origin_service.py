import xmltodict
import hashlib

import fHDHR.tools
import fHDHR.exceptions


class OriginService():

    def __init__(self, settings, logger, web):
        self.config = settings
        self.logger = logger
        self.web = web
        self.login()

    def login(self):
        self.logger.info("Logging into NextPVR")
        self.sid = self.get_sid()
        if not self.sid:
            raise fHDHR.exceptions.OriginSetupError("NextPVR Login Failed")
        else:
            self.logger.info("NextPVR Login Success")
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
        nextpvr_address = ('%s%s:%s' %
                           ("https://" if self.config.dict["origin"]["ssl"] else "http://",
                            self.config.dict["origin"]["address"],
                            str(self.config.dict["origin"]["port"]),
                            ))
        ret_status_dict = {
                            "Login": "Success",
                            "Address": nextpvr_address,
                            }
        return ret_status_dict
