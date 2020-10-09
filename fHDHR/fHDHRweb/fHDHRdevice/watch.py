import subprocess

from fHDHR.fHDHRerrors import TunerError
import fHDHR.tools


class WatchStream():

    def __init__(self, settings, origserv, tuners):
        self.config = settings
        self.origserv = origserv
        self.tuners = tuners
        self.web = fHDHR.tools.WebReq()

    def direct_stream(self, channelUri):
        chunksize = int(self.tuners.config.dict["direct_stream"]['chunksize'])

        req = self.web.session.get(channelUri, stream=True)

        def generate():
            try:
                for chunk in req.iter_content(chunk_size=chunksize):
                    yield chunk
            except GeneratorExit:
                req.close()
                print("Connection Closed.")
                self.tuners.tuner_close()

        return generate()

    def ffmpeg_stream(self, channelUri):
        bytes_per_read = int(self.config.dict["ffmpeg"]["bytes_per_read"])

        ffmpeg_command = [self.config.dict["ffmpeg"]["ffmpeg_path"],
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
                self.tuners.tuner_close()
        return generate()

    def get_stream(self, request_args):

        method = str(request_args["method"])
        channel_id = str(request_args["channel"])

        try:
            self.tuners.tuner_grab()
        except TunerError:
            print("A " + method + " stream request for channel " +
                  str(channel_id) + " was rejected do to a lack of available tuners.")
            return

        print("Attempting a " + method + " stream request for channel " + str(channel_id))

        channelUri = self.origserv.get_channel_stream(channel_id)
        # print("Proxy URL determined as " + str(channelUri))

        if method == "ffmpeg":
            return self.ffmpeg_stream(channelUri)
        elif method == "direct":
            return self.direct_stream(channelUri)
