from gevent.pywsgi import WSGIServer
from flask import (Flask, send_from_directory, request, Response,
                   abort, stream_with_context)
import requests
import subprocess

from . import fHDHRdevice
from fHDHR.fHDHRerrors import TunerError


class HDHR_Hub():

    def __init__(self):
        pass

    def hubprep(self, settings, origserv, epghandling):
        self.config = settings

        self.devicexml = fHDHRdevice.Device_XML(settings)
        self.discoverjson = fHDHRdevice.Discover_JSON(settings)
        self.lineupxml = fHDHRdevice.Lineup_XML(settings, origserv)
        self.lineupjson = fHDHRdevice.Lineup_JSON(settings, origserv)
        self.lineupstatusjson = fHDHRdevice.Lineup_Status_JSON(settings, origserv)
        self.images = fHDHRdevice.imageHandler(settings, epghandling)
        self.tuners = fHDHRdevice.Tuners(settings)
        self.station_scan = fHDHRdevice.Station_Scan(settings, origserv)
        self.xmltv = fHDHRdevice.xmlTV_XML(settings, epghandling)
        self.htmlerror = fHDHRdevice.HTMLerror(settings)

        self.debug = fHDHRdevice.Debug_JSON(settings, origserv, epghandling)

        self.origserv = origserv
        self.epghandling = epghandling

    def tuner_grab(self):
        self.tuners.tuner_grab()

    def tuner_close(self):
        self.tuners.tuner_close()

    def get_xmltv(self, base_url):
        return self.xmltv.get_xmltv_xml(base_url)

    def get_device_xml(self, base_url):
        return self.devicexml.get_device_xml(base_url)

    def get_discover_json(self, base_url):
        return self.discoverjson.get_discover_json(base_url)

    def get_lineup_status_json(self):
        return self.lineupstatusjson.get_lineup_json(self.station_scan.scanning())

    def get_lineup_xml(self, base_url):
        return self.lineupxml.get_lineup_xml(base_url)

    def get_lineup_json(self, base_url):
        return self.lineupjson.get_lineup_json(base_url)

    def get_debug_json(self, base_url):
        return self.debug.get_debug_json(base_url, self.tuners.tuners)

    def get_html_error(self, message):
        return self.htmlerror.get_html_error(message)

    def post_lineup_scan_start(self):
        self.station_scan.scan()


hdhr = HDHR_Hub()


class HDHR_HTTP_Server():
    app = Flask(__name__,)

    @app.route('/')
    def root_path():
        return hdhr.config.dict["fhdhr"]["friendlyname"]

    @app.route('/favicon.ico', methods=['GET'])
    def favicon():
        return send_from_directory(hdhr.config.dict["filedir"]["www_dir"],
                                   'favicon.ico',
                                   mimetype='image/vnd.microsoft.icon')

    @app.route('/device.xml', methods=['GET'])
    def device_xml():
        base_url = request.headers["host"]
        device_xml = hdhr.get_device_xml(base_url)
        return Response(status=200,
                        response=device_xml,
                        mimetype='application/xml')

    @app.route('/discover.json', methods=['GET'])
    def discover_json():
        base_url = request.headers["host"]
        discover_json = hdhr.get_discover_json(base_url)
        return Response(status=200,
                        response=discover_json,
                        mimetype='application/json')

    @app.route('/lineup_status.json', methods=['GET'])
    def lineup_status_json():
        linup_status_json = hdhr.get_lineup_status_json()
        return Response(status=200,
                        response=linup_status_json,
                        mimetype='application/json')

    @app.route('/lineup.xml', methods=['GET'])
    def lineup_xml():
        base_url = request.headers["host"]
        lineupxml = hdhr.get_lineup_xml(base_url)
        return Response(status=200,
                        response=lineupxml,
                        mimetype='application/xml')

    @app.route('/lineup.json', methods=['GET'])
    def lineup_json():
        base_url = request.headers["host"]
        station_list = hdhr.get_lineup_json(base_url)
        return Response(status=200,
                        response=station_list,
                        mimetype='application/json')

    @app.route('/xmltv.xml', methods=['GET'])
    def xmltv_xml():
        base_url = request.headers["host"]
        xmltv = hdhr.get_xmltv(base_url)
        return Response(status=200,
                        response=xmltv,
                        mimetype='application/xml')

    @app.route('/debug.json', methods=['GET'])
    def debug_json():
        base_url = request.headers["host"]
        debugreport = hdhr.get_debug_json(base_url)
        return Response(status=200,
                        response=debugreport,
                        mimetype='application/json')

    @app.route('/images', methods=['GET'])
    def images():

        if 'source' not in list(request.args.keys()):
            image = hdhr.images.generate_image("content", "Unknown Request")
        else:

            itemtype = 'content'
            if 'type' in list(request.args.keys()):
                itemtype = request.args["type"]

            if request.args['source'] == 'epg':
                if 'id' in list(request.args.keys()):
                    req_dict = {
                                "source": request.args["source"],
                                "type": request.args["type"],
                                "id": request.args["id"],
                                }
                    image = hdhr.images.get_image(req_dict)
                else:
                    itemmessage = "Unknown Request"
                    image = hdhr.images.generate_image(itemtype, itemmessage)
            elif request.args['source'] == 'generate':
                itemmessage = "Unknown Request"
                if 'message' in list(request.args.keys()):
                    itemmessage = request.args["message"]
                image = hdhr.images.generate_image(itemtype, itemmessage)
            else:
                itemmessage = "Unknown Request"
                image = hdhr.images.generate_image(itemtype, itemmessage)
        return Response(image, content_type=hdhr.images.get_image_type(image), direct_passthrough=True)

    @app.route('/watch', methods=['GET'])
    def watch():

        if 'method' in list(request.args.keys()) and 'channel' in list(request.args.keys()):

            method = str(request.args["method"])
            channel_id = str(request.args["channel"])

            try:
                hdhr.tuner_grab()
            except TunerError:
                print("A " + method + " stream request for channel " +
                      str(channel_id) + " was rejected do to a lack of available tuners.")
                abort(503)

            print("Attempting a " + method + " stream request for channel " + str(channel_id))

            channelUri = hdhr.origserv.get_channel_stream(channel_id)
            # print("Proxy URL determined as " + str(channelUri))

            if method == "direct":
                chunksize = int(hdhr.config.dict["direct_stream"]['chunksize'])

                req = requests.get(channelUri, stream=True)

                def generate():
                    try:
                        for chunk in req.iter_content(chunk_size=chunksize):
                            yield chunk
                    except GeneratorExit:
                        req.close()
                        print("Connection Closed.")
                        hdhr.tuner_close()

                return Response(generate(), content_type=req.headers['content-type'], direct_passthrough=True)

            elif method == "ffmpeg":

                bytes_per_read = int(hdhr.config.dict["ffmpeg"]["bytes_per_read"])

                ffmpeg_command = [hdhr.config.dict["ffmpeg"]["ffmpeg_path"],
                                  "-i", channelUri,
                                  "-c", "copy",
                                  "-f", "mpegts",
                                  "-nostats", "-hide_banner",
                                  "-loglevel", "warning",
                                  "pipe:stdout"
                                  ]

                ffmpeg_proc = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE)

                def generate():
                    try:
                        while True:
                            videoData = ffmpeg_proc.stdout.read(bytes_per_read)
                            if not videoData:
                                break
                            try:
                                yield videoData
                            except Exception as e:
                                ffmpeg_proc.terminate()
                                ffmpeg_proc.communicate()
                                print("Connection Closed: " + str(e))
                    except GeneratorExit:
                        ffmpeg_proc.terminate()
                        ffmpeg_proc.communicate()
                        print("Connection Closed.")
                        hdhr.tuner_close()

                return Response(stream_with_context(generate()), mimetype="audio/mpeg")

    @app.route('/lineup.post', methods=['POST'])
    def lineup_post():
        if 'scan' in list(request.args.keys()):
            if request.args['scan'] == 'start':
                hdhr.post_lineup_scan_start()
                return Response(status=200, mimetype='text/html')
            elif request.args['scan'] == 'abort':
                return Response(status=200, mimetype='text/html')
            else:
                print("Unknown scan command " + request.args['scan'])
                currenthtmlerror = hdhr.get_html_error("501 - " + request.args['scan'] + " is not a valid scan command")
                return Response(status=200, response=currenthtmlerror, mimetype='text/html')
        else:
            currenthtmlerror = hdhr.get_html_error("501 - not a valid command")
            return Response(status=200, response=currenthtmlerror, mimetype='text/html')

    def __init__(self, settings):
        self.config = settings

    def run(self):
        self.http = WSGIServer((
                            self.config.dict["fhdhr"]["address"],
                            int(self.config.dict["fhdhr"]["port"])
                            ), self.app.wsgi_app)
        try:
            self.http.serve_forever()
        except KeyboardInterrupt:
            self.http.stop()


def interface_start(settings, origserv, epghandling):
    print("Starting fHDHR Web Interface")
    hdhr.hubprep(settings, origserv, epghandling)
    fakhdhrserver = HDHR_HTTP_Server(settings)
    fakhdhrserver.run()
