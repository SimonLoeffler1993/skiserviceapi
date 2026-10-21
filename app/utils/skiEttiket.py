
from PIL import Image, ImageDraw, ImageFont
import os
from brother_ql import BrotherQLRaster, create_label
from brother_ql.backends.helpers import send
import logging

import qrcode

from app.services import einstellungen

logger = logging.getLogger(__name__) 

# Github
# https://github.com/pklaus/brother_ql

def px2mm(px, dpi=300):
    return px * 25.4 / dpi

def mm2px(mm, dpi=300):
    return mm * dpi / 25.4

def korektur(gesamt, teil):
    return teil * 72 / gesamt


DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def lade_schrift(groesse: int, fett: bool = False):
    """
    Lädt Arial aus dem fonts Ordner, sonst DejaVu (im Docker Container vorhanden),
    sonst die Pillow Standard-Schrift in der gewünschten Größe.
    """
    kandidaten = [
        os.path.join("fonts", "arialbd.ttf" if fett else "arial.ttf"),
        DEJAVU_BOLD if fett else DEJAVU,
    ]
    for pfad in kandidaten:
        try:
            return ImageFont.truetype(pfad, groesse)
        except OSError:
            continue
    logger.warning("Keine TrueType Schrift gefunden, Standard-Schriftart wird verwendet.")
    return ImageFont.load_default(groesse)

# Warum 18px? vermutlich Weil 3mm Rand auf 300dpi = 18px
# Diese wurden mit mehren Test herausgefunden
def labelmm2px(hoehe, breite, randpx=18):
    neuhoehe = mm2px(hoehe) - randpx *4
    neubreite = mm2px(breite) - randpx * 2
    return round(neuhoehe), round(neubreite)

# TODO: #11 Ettiketen Breite auf LabelSize
class SkiEttiket:
    def __init__(self, labelSize: str | None = None, printerModel: str | None = None, printerIdentifier: str | None = None):
        # Einstellungen erst beim Erstellen lesen, damit Änderungen im Center ohne Neustart greifen
        self.labelSize = labelSize or einstellungen.hole("LABELSIZE")
        self.printerModel = printerModel or einstellungen.hole("LABELPRINTERMODEL")
        self.printerIdentifier = printerIdentifier or einstellungen.hole("LABELPRINTERIDENT")
        self.qlr = BrotherQLRaster(self.printerModel)
        self.qlr.exception_on_warning = True

    def saisonFahererName(self,name, hoehe=20, schriftgroesse=72):
        # Bild für Label vorbereiten
        labelpxhoehe, labelpxbreite = labelmm2px(hoehe, 62)
        img = Image.new("RGB", (labelpxbreite, labelpxhoehe), "white")
        draw = ImageDraw.Draw(img)

        font = lade_schrift(schriftgroesse)

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

        font7 = lade_schrift(24)
        font7_bold = lade_schrift(24, fett=True)
        font9_bold = lade_schrift(28, fett=True)
        font20 = lade_schrift(45)
        font28 = lade_schrift(75, fett=True)

        # Textposition links, oben
        txt = "Leihschuh von:"
        neuehoehe = mm2px(0) - korektur(20, 0)
        textposition = (mm2px(1.5),neuehoehe)
        draw.text(textposition, txt, fill="black", font=font7)

        txt = einstellungen.hole("FIRMA_NAME")
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
    
    def skiAuftragEttiket(self, name: str, skiName: str, url: str, service: str, bindung: bool, fertig_datum: str | None = None, bindung_text: str | None = None):
        ettiket_laenge = 57

        if bindung:
            ettiket_laenge +=4
            # Zeile mit den Bindungsdaten
            if bindung_text:
                ettiket_laenge +=4

        if fertig_datum:
            ettiket_laenge +=4
        logger.info("Auftrag Ettiket wird erstellt")

        labelpxhoehe, labelpxbreite = labelmm2px(ettiket_laenge, 62)
        img = Image.new("RGB", (labelpxbreite, labelpxhoehe), "white")
        draw = ImageDraw.Draw(img)

        font_name  = lade_schrift(48, fett=True)
        font_label = lade_schrift(48, fett=True)
        font_date  = lade_schrift(44, fett=True)

        RAND = 8
        Y = RAND +2 # laufende Y-Position

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

            if bindung_text:
                # Schrift verkleinern, bis die Zeile auf das Etikett passt
                groesse = 36
                font_daten = lade_schrift(groesse, fett=True)
                while groesse > 20 and draw.textlength(bindung_text, font=font_daten) > labelpxbreite - 2 * RAND - 10:
                    groesse -= 2
                    font_daten = lade_schrift(groesse, fett=True)
                daten_bbox = draw.textbbox((0, 0), bindung_text, font=font_daten)
                daten_x = (labelpxbreite - (daten_bbox[2] - daten_bbox[0])) // 2
                draw.text((daten_x, Y), bindung_text, fill="black", font=font_daten)
                Y += daten_bbox[3] - daten_bbox[1] + 12

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


    def drucken(self) -> bool:
        try:
            send(
                instructions=self.qlr.data,
                printer_identifier=self.printerIdentifier,
            )
            return True
        except Exception as e:
            logger.error("Fehler beim Ettiket Drucken: %s", e, exc_info=True)
            return False

if __name__ == "__main__":
    skiEttiket = SkiEttiket()
    # skiEttiket.saisonFahererName("Max Mustermann")
    # skiEttiket.saisonFahererName("Simon")
    # skiEttiket.saisonFahererName("Emma")
    # skiEttiket.SchuhEttiket("Atomic", "HAWX KIDS 4", "24.5", "590")
    skiEttiket.skiAuftragEttiket("Simon","25/26S-4","ms-skiservice","kleiner Service",False,"sfas")
    # skiEttiket.drucken()

    print(labelmm2px(62, 62))
