from gevent.pywsgi import WSGIServer
from flask import (Flask, send_from_directory, request, Response,
                   abort, stream_with_context)
from io import BytesIO
import xml.etree.ElementTree as ET
import json
import requests
import subprocess
import threading
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont


def sub_el(parent, name, text=None, **kwargs):
    el = ET.SubElement(parent, name, **kwargs)
    if text:
        el.text = text
    return el


def getSize(txt, font):
    testImg = PIL.Image.new('RGB', (1, 1))
    testDraw = PIL.ImageDraw.Draw(testImg)
    return testDraw.textsize(txt, font)


class HDHR_Hub():
    config = None
    origserv = None
    epghandling = None
    station_scan = False
    station_list = []
    http = None

    def __init__(self):
        self.tuner_lock = threading.Lock()
        self.tuners = 0

    def hubprep(self, config, origserv, epghandling):
        self.config = config
        self.max_tuners = int(self.config.dict["fhdhr"]["tuner_count"])
        self.station_scan = False
        self.origserv = origserv
        self.epghandling = epghandling

    def tuner_usage(self, number):
        self.tuner_lock.acquire()
        self.tuners += number
        if self.tuners < 0:
            self.tuners = 0
        elif self.tuners > self.max_tuners:
            self.tuners = self.max_tuners
        self.tuner_lock.release()

    def get_tuner(self):
        if self.tuners <= self.max_tuners:
            return True
        return False

    def get_xmltv(self, base_url):
        return self.epghandling.get_xmltv(base_url)

    def generate_image(self, messagetype, message):
        if messagetype == "channel":
            width = 360
            height = 270
            fontsize = 72
        elif messagetype == "content":
            width = 1080
            height = 1440
            fontsize = 100

        colorBackground = "#228822"
        colorText = "#717D7E"
        colorOutline = "#717D7E"
        fontname = str(self.config.dict["filedir"]["font"])

        font = PIL.ImageFont.truetype(fontname, fontsize)
        text_width, text_height = getSize(message, font)
        img = PIL.Image.new('RGBA', (width+4, height+4), colorBackground)
        d = PIL.ImageDraw.Draw(img)
        d.text(((width-text_width)/2, (height-text_height)/2), message, fill=colorText, font=font)
        d.rectangle((0, 0, width+3, height+3), outline=colorOutline)

        s = BytesIO()
        img.save(s, 'png')
        return s.getvalue()

    def get_image(self, req_args):

        imageUri = self.epghandling.get_thumbnail(req_args["type"], req_args["id"])
        if not imageUri:
            return self.generate_image(req_args["type"], req_args["id"])

        try:
            req = requests.get(imageUri)
            return req.content
        except Exception as e:
            print(e)
            return self.generate_image(req_args["type"], req_args["id"])

    def get_image_type(self, image_data):
        header_byte = image_data[0:3].hex().lower()
        if header_byte == '474946':
            return "image/gif"
        elif header_byte == '89504e':
            return "image/png"
        elif header_byte == 'ffd8ff':
            return "image/jpeg"
        else:
            return "image/jpeg"

    def get_xmldiscover(self, base_url):
        out = ET.Element('root')
        out.set('xmlns', "urn:schemas-upnp-org:device-1-0")

        sub_el(out, 'URLBase', "http://" + base_url)

        specVersion_out = sub_el(out, 'specVersion')
        sub_el(specVersion_out, 'major', "1")
        sub_el(specVersion_out, 'minor', "0")

        device_out = sub_el(out, 'device')
        sub_el(device_out, 'deviceType', "urn:schemas-upnp-org:device:MediaServer:1")
        sub_el(device_out, 'friendlyName', self.config.dict["fhdhr"]["friendlyname"])
        sub_el(device_out, 'manufacturer', self.config.dict["dev"]["reporting_manufacturer"])
        sub_el(device_out, 'modelName', self.config.dict["dev"]["reporting_model"])
        sub_el(device_out, 'modelNumber', self.config.dict["dev"]["reporting_model"])
        sub_el(device_out, 'serialNumber')
        sub_el(device_out, 'UDN', "uuid:" + self.config.dict["main"]["uuid"])

        fakefile = BytesIO()
        fakefile.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        fakefile.write(ET.tostring(out, encoding='UTF-8'))
        return fakefile.getvalue()

    def get_discover_json(self, base_url):
        jsondiscover = {
                            "FriendlyName": self.config.dict["fhdhr"]["friendlyname"],
                            "Manufacturer": "Borondust",
                            "ModelNumber": self.config.dict["dev"]["reporting_model"],
                            "FirmwareName": self.config.dict["dev"]["reporting_firmware_name"],
                            "TunerCount": self.config.dict["fhdhr"]["tuner_count"],
                            "FirmwareVersion": self.config.dict["dev"]["reporting_firmware_ver"],
                            "DeviceID": self.config.dict["main"]["uuid"],
                            "DeviceAuth": "fHDHR",
                            "BaseURL": "http://" + base_url,
                            "LineupURL": "http://" + base_url + "/lineup.json"
                        }
        return jsondiscover

    def get_lineup_status(self):
        if self.station_scan:
            channel_count = self.origserv.get_station_total()
            jsonlineup = {
                          "ScanInProgress": "true",
                          "Progress": 99,
                          "Found": channel_count
                          }
        else:
            jsonlineup = {
                          "ScanInProgress": "false",
                          "ScanPossible": "true",
                          "Source": self.config.dict["dev"]["reporting_tuner_type"],
                          "SourceList": [self.config.dict["dev"]["reporting_tuner_type"]],
                          }
        return jsonlineup

    def get_lineup_xml(self, base_url):
        out = ET.Element('Lineup')
        station_list = self.origserv.get_station_list(base_url)
        for station_item in station_list:
            program_out = sub_el(out, 'Program')
            sub_el(program_out, 'GuideNumber', station_item['GuideNumber'])
            sub_el(program_out, 'GuideName', station_item['GuideName'])
            sub_el(program_out, 'URL', station_item['URL'])

        fakefile = BytesIO()
        fakefile.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        fakefile.write(ET.tostring(out, encoding='UTF-8'))
        return fakefile.getvalue()

    def get_debug(self, base_url):
        debugjson = {
                    "base_url": base_url,
                    }
        return debugjson

    def get_html_error(self, message):
        htmlerror = """<html>
                        <head></head>
                        <body>
                            <h2>{}</h2>
                        </body>
                        </html>"""
        return htmlerror.format(message)

    def station_scan_change(self, enablement):
        self.station_scan = enablement


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
        devicexml = hdhr.get_xmldiscover(base_url)
        return Response(status=200,
                        response=devicexml,
                        mimetype='application/xml')

    @app.route('/discover.json', methods=['GET'])
    def discover_json():
        base_url = request.headers["host"]
        jsondiscover = hdhr.get_discover_json(base_url)
        return Response(status=200,
                        response=json.dumps(jsondiscover, indent=4),
                        mimetype='application/json')

    @app.route('/lineup_status.json', methods=['GET'])
    def lineup_status_json():
        linup_status_json = hdhr.get_lineup_status()
        return Response(status=200,
                        response=json.dumps(linup_status_json, indent=4),
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
        station_list = hdhr.origserv.get_station_list(base_url)
        return Response(status=200,
                        response=json.dumps(station_list, indent=4),
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
        debugreport = hdhr.get_debug(base_url)
        return Response(status=200,
                        response=json.dumps(debugreport, indent=4),
                        mimetype='application/json')

    @app.route('/images', methods=['GET'])
    def images():

        if 'source' not in list(request.args.keys()):
            image = hdhr.generate_image("content", "Unknown Request")
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
                    image = hdhr.get_image(req_dict)
                else:
                    itemmessage = "Unknown Request"
                    image = hdhr.generate_image(itemtype, itemmessage)
            elif request.args['source'] == 'generate':
                itemmessage = "Unknown Request"
                if 'message' in list(request.args.keys()):
                    itemmessage = request.args["message"]
                image = hdhr.generate_image(itemtype, itemmessage)
            else:
                itemmessage = "Unknown Request"
                image = hdhr.generate_image(itemtype, itemmessage)
        return Response(image, content_type=hdhr.get_image_type(image), direct_passthrough=True)

    @app.route('/watch', methods=['GET'])
    def watch():

        if 'method' in list(request.args.keys()) and 'channel' in list(request.args.keys()):

            method = str(request.args["method"])
            channel_id = str(request.args["channel"])

            tuner = hdhr.get_tuner()
            if not tuner:
                print("A " + method + " stream request for channel " +
                      str(channel_id) + " was rejected do to a lack of available tuners.")
                abort(503)

            print("Attempting a " + method + " stream request for channel " + str(channel_id))
            hdhr.tuner_usage(1)

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
                        hdhr.tuner_usage(-1)

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
                                hdhr.tuner_usage(-1)
                    except GeneratorExit:
                        ffmpeg_proc.terminate()
                        ffmpeg_proc.communicate()
                        print("Connection Closed.")
                        hdhr.tuner_usage(-1)

                return Response(stream_with_context(generate()), mimetype="audio/mpeg")

    @app.route('/lineup.post', methods=['POST'])
    def lineup_post():
        if 'scan' in list(request.args.keys()):
            if request.args['scan'] == 'start':
                hdhr.station_scan_change(True)
                hdhr.station_list = []
                hdhr.station_scan_change(False)
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

    def __init__(self, config):
        self.config = config

    def run(self):
        self.http = WSGIServer((
                            self.config.dict["fhdhr"]["address"],
                            int(self.config.dict["fhdhr"]["port"])
                            ), self.app.wsgi_app)
        try:
            self.http.serve_forever()
        except KeyboardInterrupt:
            self.http.stop()


def interface_start(config, origserv, epghandling):
    print("Starting fHDHR Web Interface")
    hdhr.hubprep(config, origserv, epghandling)
    fakhdhrserver = HDHR_HTTP_Server(config)
    fakhdhrserver.run()
