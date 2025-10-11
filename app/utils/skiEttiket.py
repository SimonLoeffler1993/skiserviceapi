
from PIL import Image, ImageDraw, ImageFont
import os
from brother_ql import BrotherQLRaster, create_label
from brother_ql.backends.helpers import send

import qrcode

from app.core.config import EttikettierSettings

# Github
# https://github.com/pklaus/brother_ql

def px2mm(px, dpi=300):
    return px * 25.4 / dpi

def mm2px(mm, dpi=300):
    return mm * dpi / 25.4

def korektur(gesamt, teil):
    return teil * 72 / gesamt


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

    def SchuhEttiket(self, hersteller: str, modell: str, groesse: str, qrdata: str):
        labelpxhoehe, labelpxbreite = labelmm2px(20, 62)
        img = Image.new("RGB", (labelpxbreite, labelpxhoehe), "white")
        draw = ImageDraw.Draw(img)

        try:
            font_path = os.path.join("fonts", "arial.ttf")
            font_bold_path = os.path.join("fonts", "arialbd.ttf")
            font7 = ImageFont.truetype(font_path, 24)
            font7_bold = ImageFont.truetype(font_bold_path, 24)
            font9_bold = ImageFont.truetype(font_bold_path, 28)
            font20 = ImageFont.truetype(font_path, 45)
            font28 = ImageFont.truetype(font_bold_path, 75)
        except:
            font = ImageFont.load_default()
            print("Warnung: Arial.ttf nicht gefunden, Standard-Schriftart wird verwendet.")

        # Textposition links, oben
        txt = "Leihschuh von:"
        neuehoehe = mm2px(0) - korektur(20, 0)
        textposition = (mm2px(1.5),neuehoehe)
        draw.text(textposition, txt, fill="black", font=font7)

        txt = "Simons Skiservice"
        neuehoehe = mm2px(2.5) - korektur(20, 2.5)
        textposition = (mm2px(1.5),neuehoehe)
        draw.text(textposition, txt, fill="black", font=font9_bold)

        # txt = "Atomic HAWX KIDS 4"
        neuehoehe = mm2px(6.5) - korektur(20, 6.5)
        textposition = (mm2px(1.5),neuehoehe)
        draw.text(textposition, hersteller + " " + modell, fill="black", font=font20)

        txt = groesse
        neuehoehe = mm2px(11) - korektur(20, 11)
        textposition = (mm2px(1.5),neuehoehe)
        box = draw.textbbox(textposition, txt, font=font28)
        # Textposition zentriert
        textbreite = box[2] - box[0]
        textposition = ((labelpxbreite - textbreite) // 2, neuehoehe)
        draw.text(textposition, txt, fill="black", font=font28)

        # QR-Code erstellen
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=5,
            border=2,
        )
        qr.add_data(qrdata)
        qr.make(fit=True)
        
        qrgroesse = labelpxhoehe - 8

        qrimg = qr.make_image(fill_color="black", back_color="white")
        qrimg = qrimg.resize((qrgroesse, qrgroesse))

        img.paste(qrimg, (labelpxbreite - qrimg.size[0], 12))

        # ID Beschriften
        textposition = (labelpxbreite - qrgroesse + 8,0)
        draw.text(textposition, "#: " + qrdata, fill="black", font=font7_bold)

        # img.show()

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
    # skiEttiket.saisonFahererName("Max Mustermann")
    # skiEttiket.saisonFahererName("Simon")
    # skiEttiket.saisonFahererName("Emma")
    skiEttiket.SchuhEttiket("Atomic", "HAWX KIDS 4", "24.5", "590")
    skiEttiket.drucken()

    print(labelmm2px(62, 62))
