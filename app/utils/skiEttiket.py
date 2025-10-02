
from PIL import Image, ImageDraw, ImageFont
import os
from brother_ql import BrotherQLRaster, create_label
from brother_ql.backends.helpers import send

from app.core.config import EttikettierSettings

# Github
# https://github.com/pklaus/brother_ql

def px2mm(px, dpi=300):
    return px * 25.4 / dpi

def mm2px(mm, dpi=300):
    return mm * dpi / 25.4


# Warum 18px? vermutlich Weil 3mm Rand auf 300dpi = 18px
# Diese wurden mit mehren Test herausgefunden
def labelmm2px(hoehe, breite, randpx=18):
    neuhoehe = mm2px(hoehe) - randpx *4
    neubreite = mm2px(breite) - randpx * 2
    return round(neuhoehe), round(neubreite)

class SkiEttiket:
    def __init__(self, labelSize=EttikettierSettings.labelSize, printerModel=EttikettierSettings.printerModel, printerIdentifier=EttikettierSettings.printerIdent):
        self.labelSize = labelSize
        self.printerModel = printerModel
        self.printerIdentifier = printerIdentifier
        self.qlr = BrotherQLRaster(self.printerModel)
        self.qlr.exception_on_warning = True

    def saisonFahererName(self,name, hoehe=20, schriftgroesse=72):
        # Bild für Label vorbereiten
        labelpxhoehe, labelpxbreite = labelmm2px(hoehe, 62)
        img = Image.new("RGB", (labelpxbreite, labelpxhoehe), "white")
        draw = ImageDraw.Draw(img)

        try:
            font_path = os.path.join("fonts", "arial.ttf")
            font = ImageFont.truetype(font_path, schriftgroesse)
        except:
            font = ImageFont.load_default()
            print("Warnung: Arial.ttf nicht gefunden, Standard-Schriftart wird verwendet.")

        textbbox = draw.textbbox((0, 0), name, font=font)
        textbreite = textbbox[2] - textbbox[0]
        texthoehe = textbbox[3] - textbbox[1]

        textposition = ((labelpxbreite - textbreite) // 2, (labelpxhoehe - texthoehe) // 2)
        draw.text(textposition, name, fill="black", font=font)

        # img.save("saisonFahererName.png")

        # Label erstellen
        create_label(
            qlr=self.qlr,
            image=img,            
            label_size=self.labelSize,   
            rotate=0,
            threshold=70,
            dither=False,
            compress=True,
            red=True,
            dpi_600=False,
            hq=True,
            cut=True
        )

        return True

    def drucken(self):
        send(
            instructions=self.qlr.data,
            printer_identifier=self.printerIdentifier,
        )

if __name__ == "__main__":
    skiEttiket = SkiEttiket()
    skiEttiket.saisonFahererName("Max Mustermann")
    skiEttiket.saisonFahererName("Simon")
    skiEttiket.saisonFahererName("Emma")
    skiEttiket.drucken()

    print(labelmm2px(62, 62))
