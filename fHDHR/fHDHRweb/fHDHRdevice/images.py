from io import BytesIO
import requests
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont


class imageHandler():

    def __init__(self, settings, epghandling):
        self.config = settings
        self.epghandling = epghandling

    def getSize(self, txt, font):
        testImg = PIL.Image.new('RGB', (1, 1))
        testDraw = PIL.ImageDraw.Draw(testImg)
        return testDraw.textsize(txt, font)

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
        text_width, text_height = self.getSize(message, font)
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
