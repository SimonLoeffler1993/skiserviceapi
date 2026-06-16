
from PIL import Image, ImageDraw, ImageFont
import os
from brother_ql import BrotherQLRaster, create_label
from brother_ql.backends.helpers import send
import logging

import qrcode

from app.core.config import EttikettierSettings

logger = logging.getLogger(__name__) 

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

        # TODO Schriftarten, Fehler im Docker Container
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

        # TODO: #8 Fima in Einstellungen
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

        img.show()

        # Label erstellen
        create_label(
            qlr=self.qlr,
            image=img,            
            label_size=self.labelSize,   
            rotate=0,
            threshold=70,
            dither=False,
            compress=True,
            red=False,
            dpi_600=False,
            hq=True,
            cut=True
        )

        return True
    
    def skiAuftragEttiket(self, name: str, skiName: str, url: str, service: str, bindung: bool, fertig_datum: str | None = None):
        ettiket_laenge = 57

        if bindung:
            ettiket_laenge +=4

        if fertig_datum:
            ettiket_laenge +=4
        logger.info("Auftrag Ettiket wird erstellt")

        labelpxhoehe, labelpxbreite = labelmm2px(ettiket_laenge, 62)
        img = Image.new("RGB", (labelpxbreite, labelpxhoehe), "white")
        draw = ImageDraw.Draw(img)

        font_path      = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_bold_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_name  = ImageFont.truetype(font_bold_path, 48)
        font_label = ImageFont.truetype(font_bold_path, 48)
        font_date  = ImageFont.truetype(font_bold_path, 44)

        RAND = 8
        Y = RAND  # laufende Y-Position

        # --- Rahmen ---
        draw.rectangle(
            [(2, 2), (labelpxbreite - 3, labelpxhoehe - 3)],
            outline="black",
            width=5
        )

        # --- 1. Name (zentriert, oben) ---
        name_bbox = draw.textbbox((0, 0), name, font=font_name)
        name_breite = name_bbox[2] - name_bbox[0]
        name_hoehe  = name_bbox[3] - name_bbox[1]
        name_x = (labelpxbreite - name_breite) // 2
        draw.text((name_x, Y), name, fill="black", font=font_name)
        Y += name_hoehe + 10

        # --- 2. QR-Code (zentriert) ---
        qr_groesse = round(labelpxbreite * 0.60)

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)
        qrimg = qr.make_image(fill_color="black", back_color="white")
        qrimg = qrimg.resize((qr_groesse, qr_groesse))

        qr_x = (labelpxbreite - qr_groesse) // 2
        img.paste(qrimg, (qr_x, Y))
        Y += qr_groesse + 6

        # --- 3. Service (zentriert) ---
        skiName_bbox = draw.textbbox((0, 0), skiName, font=font_label)
        skiName_breite = skiName_bbox[2] - skiName_bbox[0]
        skiName_hoehe  = skiName_bbox[3] - skiName_bbox[1]
        skiName_x = (labelpxbreite - skiName_breite) // 2
        draw.text((skiName_x, Y), skiName, fill="black", font=font_label)
        Y += skiName_hoehe + 11

        # --- 3. Service (zentriert) ---
        service_bbox = draw.textbbox((0, 0), service, font=font_label)
        service_breite = service_bbox[2] - service_bbox[0]
        service_hoehe  = service_bbox[3] - service_bbox[1]
        service_x = (labelpxbreite - service_breite) // 2
        draw.text((service_x, Y), service, fill="black", font=font_label)
        Y += service_hoehe + 12

        if bindung:
            # --- 3. Service (zentriert) ---
            bindung_bbox = draw.textbbox((0, 0), "BINDUNG", font=font_label)
            bindung_breite = bindung_bbox[2] - bindung_bbox[0]
            bindung_hoehe  = bindung_bbox[3] - bindung_bbox[1]
            service_x = (labelpxbreite - bindung_breite) // 2
            draw.text((service_x, Y), "BINDUNG", fill="black", font=font_label)
            Y += bindung_hoehe + 12

        # --- 4. Fertig-Datum (optional, zentriert) ---
        if fertig_datum:
            datum_text = f"Fertig bis: {fertig_datum}"
            datum_bbox = draw.textbbox((0, 0), datum_text, font=font_date)
            datum_breite = datum_bbox[2] - datum_bbox[0]
            datum_x = (labelpxbreite - datum_breite) // 2
            draw.text((datum_x, Y), datum_text, fill="black", font=font_date)

        # img.save("skiAuftragEttiket.png")
        # img.show()

        try:
            create_label(
                qlr=self.qlr,
                image=img,
                label_size=self.labelSize,
                rotate=0,
                threshold=70,
                dither=False,
                compress=True,
                red=False,
                dpi_600=False,
                hq=True,
                cut=True
            )
        except Exception as e:
            logger.error("Fehler beim vorbereiten zum Ettiket Drucken: %s", e, exc_info=True)

        return True


    def drucken(self):
        try:
            send(
                instructions=self.qlr.data,
                printer_identifier=self.printerIdentifier,
            )
        except Exception as e:
            logger.error("Fehler beim Ettiket Drucken: %s", e, exc_info=True)

if __name__ == "__main__":
    skiEttiket = SkiEttiket()
    # skiEttiket.saisonFahererName("Max Mustermann")
    # skiEttiket.saisonFahererName("Simon")
    # skiEttiket.saisonFahererName("Emma")
    # skiEttiket.SchuhEttiket("Atomic", "HAWX KIDS 4", "24.5", "590")
    skiEttiket.skiAuftragEttiket("Simon","25/26S-4","ms-skiservice","kleiner Service",False,"sfas")
    # skiEttiket.drucken()

    print(labelmm2px(62, 62))
