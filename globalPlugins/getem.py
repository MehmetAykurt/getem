# -*- coding: utf-8 -*-
# GETEM E-Kütüphane NVDA Eklentisi
# Telif hakkı (C) 2026 Mehmet Aykurt
# Geliştirici: Mehmet Aykurt <m.aykurt38@gmail.com>

import html
import json
import os
import re
import shutil
import threading
import urllib.parse
import urllib.request
import webbrowser

import globalPluginHandler
import globalVars
import gui
import ui
import wx
from scriptHandler import script


EKLENTI_KATEGORISI = "GETEM E-Kütüphane"
GETEM_TEMEL_ADRESI = "https://getem.boun.edu.tr"
GETEM_KATALOG_ADRESI = "https://getem.boun.edu.tr/?q=katalog"
KULLANICI_ARACISI = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "NVDA-Getem/1.0.0"
)
SECENEK_ZAMAN_ASIMI = 8
ARAMA_ZAMAN_ASIMI = 12
LISTE_METNI_UZUNLUK_SINIRI = 180

_favori_gecisi_yapildi = False


def kullanici_veri_klasorunu_al():
    config_yolu = getattr(getattr(globalVars, "appArgs", None), "configPath", None)

    if not config_yolu:
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        config_yolu = os.path.join(appdata, "nvda")

    veri_klasoru = os.path.join(config_yolu, "getem")
    os.makedirs(veri_klasoru, exist_ok=True)
    return veri_klasoru


def eski_favoriler_dosyasini_al():
    return os.path.join(os.path.dirname(__file__), "getem_favoriler.json")


FAVORILER_DOSYASI = os.path.join(kullanici_veri_klasorunu_al(), "favoriler.json")
ESKI_FAVORILER_DOSYASI = eski_favoriler_dosyasini_al()


def metni_temizle(metin):
    if metin is None:
        return ""

    metin = str(metin)
    metin = metin.replace("<br>", "\n")
    metin = metin.replace("<br/>", "\n")
    metin = metin.replace("<br />", "\n")
    metin = re.sub(r"<[^>]+>", "", metin)
    metin = html.unescape(metin)
    metin = metin.replace("\r\n", "\n").replace("\r", "\n")
    metin = re.sub(r"[ \t]+", " ", metin)
    metin = re.sub(r"\n[ \t]+", "\n", metin)
    metin = re.sub(r"\n{3,}", "\n\n", metin)
    return metin.strip()


def liste_metnini_kisalt(metin):
    metin = metni_temizle(metin).replace("\n", " ")

    if len(metin) <= LISTE_METNI_UZUNLUK_SINIRI:
        return metin

    return metin[:LISTE_METNI_UZUNLUK_SINIRI].rstrip() + "..."


def kitap_linkini_duzenle(link):
    link = str(link or "").strip()

    if not link:
        return ""

    if link.startswith("http://") or link.startswith("https://"):
        return link

    if link.startswith("/"):
        return GETEM_TEMEL_ADRESI + link

    return GETEM_TEMEL_ADRESI + "/" + link


def json_liste_oku(dosya_yolu):
    try:
        if not os.path.exists(dosya_yolu):
            return []

        with open(dosya_yolu, "r", encoding="utf-8") as dosya:
            veri = json.load(dosya)

        if not isinstance(veri, list):
            return []

        return [kayit for kayit in veri if isinstance(kayit, dict)]

    except Exception:
        return []


def favori_anahtari_al(kayit):
    link = str(kayit.get("link", "")).strip()

    if link:
        return "link:" + link

    return "kitap:" + str(kayit.get("isim", "")).strip().casefold()


def favori_listelerini_birlestir(eski_liste, yeni_liste):
    sonuc = []
    gorulenler = set()

    for kayit in yeni_liste + eski_liste:
        anahtar = favori_anahtari_al(kayit)

        if anahtar in gorulenler:
            continue

        gorulenler.add(anahtar)
        sonuc.append(kayit)

    return sonuc


def favorileri_kaydet(liste):
    try:
        os.makedirs(os.path.dirname(FAVORILER_DOSYASI), exist_ok=True)
        gecici_dosya = FAVORILER_DOSYASI + ".tmp"

        with open(gecici_dosya, "w", encoding="utf-8") as dosya:
            json.dump(liste, dosya, ensure_ascii=False, indent=4)

        os.replace(gecici_dosya, FAVORILER_DOSYASI)
        return True

    except Exception:
        return False


def eski_favorileri_yeni_konuma_tasi():
    global _favori_gecisi_yapildi

    if _favori_gecisi_yapildi:
        return

    _favori_gecisi_yapildi = True

    try:
        if not os.path.exists(ESKI_FAVORILER_DOSYASI):
            return

        eski_liste = json_liste_oku(ESKI_FAVORILER_DOSYASI)

        if not eski_liste:
            return

        yeni_liste = json_liste_oku(FAVORILER_DOSYASI)
        birlesik_liste = favori_listelerini_birlestir(eski_liste, yeni_liste)

        if favorileri_kaydet(birlesik_liste):
            yedek_yolu = ESKI_FAVORILER_DOSYASI + ".bak"

            if not os.path.exists(yedek_yolu):
                try:
                    shutil.copy2(ESKI_FAVORILER_DOSYASI, yedek_yolu)
                except Exception:
                    pass

    except Exception:
        pass


def favorileri_yukle():
    eski_favorileri_yeni_konuma_tasi()
    return json_liste_oku(FAVORILER_DOSYASI)


class DetayPenceresi(wx.Dialog):
    def __init__(self, parent, kitap):
        eser_adi = kitap.get("isim") or "Kitap"
        super().__init__(parent, title="Kitap Ayrıntısı - " + eser_adi)

        self.kitap = kitap
        self.kitap_linki = kitap_linkini_duzenle(kitap.get("link"))

        ana_duzen = wx.BoxSizer(wx.VERTICAL)

        self.bilgi_metni = self.bilgi_metnini_hazirla(kitap)
        self.metin_kutusu = wx.TextCtrl(
            self,
            value=self.bilgi_metni,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        ana_duzen.Add(self.metin_kutusu, 1, wx.ALL | wx.EXPAND, 5)

        buton_duzeni = wx.BoxSizer(wx.HORIZONTAL)

        tarayici_butonu = wx.Button(self, label="Tarayıcıda &Aç")
        tarayici_butonu.Bind(wx.EVT_BUTTON, self.tarayicida_ac)
        buton_duzeni.Add(tarayici_butonu, 0, wx.ALL, 5)

        kopyala_butonu = wx.Button(self, label="Bilgileri &Kopyala")
        kopyala_butonu.Bind(wx.EVT_BUTTON, self.bilgileri_kopyala)
        buton_duzeni.Add(kopyala_butonu, 0, wx.ALL, 5)

        favoriye_ekle_butonu = wx.Button(self, label="Favorilere &Ekle")
        favoriye_ekle_butonu.Bind(wx.EVT_BUTTON, self.favoriye_ekle)
        buton_duzeni.Add(favoriye_ekle_butonu, 0, wx.ALL, 5)

        kapat_butonu = wx.Button(self, wx.ID_CANCEL, label="Kapa&t")
        buton_duzeni.Add(kapat_butonu, 0, wx.ALL, 5)

        ana_duzen.Add(buton_duzeni, 0, wx.CENTER)

        self.SetSizer(ana_duzen)
        self.SetSize((700, 500))
        self.CenterOnParent()
        self.metin_kutusu.SetFocus()

    def bilgi_metnini_hazirla(self, kitap):
        return (
            "Eser adı: " + kitap.get("isim", "Bilinmiyor") + "\n"
            "Yazar: " + kitap.get("yazar", "Bilinmiyor") + "\n"
            "Seslendiren: " + kitap.get("seslendiren", "Bilinmiyor") + "\n"
            "Biçim: " + kitap.get("format", "Bilinmiyor") + "\n\n"
            "Konu / Açıklama:\n" + kitap.get("aciklama", "Açıklama bulunamadı.")
        )

    def tarayicida_ac(self, _event):
        if not self.kitap_linki:
            ui.message("Kitap bağlantısı bulunamadı.")
            return

        webbrowser.open(self.kitap_linki)

    def bilgileri_kopyala(self, _event):
        if not wx.TheClipboard.Open():
            ui.message("Pano açılamadı.")
            return

        try:
            wx.TheClipboard.SetData(wx.TextDataObject(self.bilgi_metni))
            ui.message("Kitap bilgileri panoya kopyalandı.")
        finally:
            wx.TheClipboard.Close()

    def favoriye_ekle(self, _event):
        favoriler = favorileri_yukle()
        kitap_linki = self.kitap.get("link", "")

        if any(kayit.get("link") == kitap_linki for kayit in favoriler):
            ui.message("Bu kitap zaten favorilerinizde kayıtlı.")
            return

        favoriler.append(self.kitap)

        if favorileri_kaydet(favoriler):
            ui.message("Kitap favorilerinize eklendi.")
        else:
            ui.message("Favoriler kaydedilemedi.")


class FavorilerPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Favorilerim ve Okuma Listem")
        self.favoriler = favorileri_yukle()

        self.ana_duzen = wx.BoxSizer(wx.VERTICAL)

        etiket_liste = wx.StaticText(self, label="Favori kitaplarınız:")
        self.ana_duzen.Add(etiket_liste, 0, wx.ALL, 5)

        self.sonuclar_listesi = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.sonuclar_listesi.InsertColumn(0, "Eser adı", width=350)
        self.sonuclar_listesi.InsertColumn(1, "Yazar", width=200)
        self.sonuclar_listesi.InsertColumn(2, "Seslendiren", width=200)
        self.sonuclar_listesi.InsertColumn(3, "Biçim", width=150)
        self.ana_duzen.Add(self.sonuclar_listesi, 1, wx.ALL | wx.EXPAND, 5)

        self.listeyi_doldur()
        self.sonuclar_listesi.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.kitap_secildi)

        butonlar_duzeni = wx.BoxSizer(wx.HORIZONTAL)

        sil_butonu = wx.Button(self, label="Favorilerden &Sil")
        sil_butonu.Bind(wx.EVT_BUTTON, self.favoriden_sil)
        butonlar_duzeni.Add(sil_butonu, 0, wx.ALL, 5)

        kapat_butonu = wx.Button(self, wx.ID_CANCEL, label="&Kapat")
        butonlar_duzeni.Add(kapat_butonu, 0, wx.ALL, 5)

        self.ana_duzen.Add(butonlar_duzeni, 0, wx.CENTER)

        self.SetSizer(self.ana_duzen)
        self.SetSize((800, 500))
        self.CenterOnParent()
        self.sonuclar_listesi.SetFocus()

    def listeyi_doldur(self):
        self.sonuclar_listesi.DeleteAllItems()

        if not self.favoriler:
            self.sonuclar_listesi.InsertItem(0, "Favori listeniz şu anda boş.")
            self.sonuclar_listesi.SetItemState(
                0,
                wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
                wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
            )
            return

        for index, kitap in enumerate(self.favoriler):
            self.sonuclar_listesi.InsertItem(index, liste_metnini_kisalt(kitap.get("isim", "Bilinmiyor")))
            self.sonuclar_listesi.SetItem(index, 1, liste_metnini_kisalt(kitap.get("yazar", "Bilinmiyor")))
            self.sonuclar_listesi.SetItem(index, 2, liste_metnini_kisalt(kitap.get("seslendiren", "Bilinmiyor")))
            self.sonuclar_listesi.SetItem(index, 3, liste_metnini_kisalt(kitap.get("format", "Bilinmiyor")))

        self.sonuclar_listesi.SetItemState(
            0,
            wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
            wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
        )

    def kitap_secildi(self, event):
        index = event.GetIndex()

        if self.favoriler and index < len(self.favoriler):
            detay_penceresi = DetayPenceresi(self, self.favoriler[index])
            detay_penceresi.ShowModal()
            detay_penceresi.Destroy()

    def favoriden_sil(self, _event):
        secili = self.sonuclar_listesi.GetFirstSelected()

        if not self.favoriler or secili == -1 or secili >= len(self.favoriler):
            ui.message("Silinecek favori seçilmedi.")
            return

        cevap = gui.messageBox(
            "Seçili kitap favorilerinizden silinsin mi?",
            "Favorilerden Sil",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )

        if cevap != wx.YES:
            return

        del self.favoriler[secili]

        if favorileri_kaydet(self.favoriler):
            self.listeyi_doldur()
            ui.message("Kitap favorilerden silindi.")
        else:
            ui.message("Favoriler kaydedilemedi.")


class GetemPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="GETEM E-Kütüphane - Veriler yükleniyor...")

        self.arama_sonuclari = []
        self.siralama_yonu = {"isim": False, "yazar": False}
        self.arama_devam_ediyor = False
        self.arama_kimligi = 0
        self.pencere_kapaniyor = False

        self.ana_duzen = wx.BoxSizer(wx.VERTICAL)

        etiket_eser_adi = wx.StaticText(self, label="&Eser adı:")
        self.ana_duzen.Add(etiket_eser_adi, 0, wx.ALL, 5)
        self.eser_adi_kutusu = wx.TextCtrl(self)
        self.ana_duzen.Add(self.eser_adi_kutusu, 0, wx.ALL | wx.EXPAND, 5)

        etiket_yazar = wx.StaticText(self, label="&Yazar:")
        self.ana_duzen.Add(etiket_yazar, 0, wx.ALL, 5)
        self.yazar_kutusu = wx.TextCtrl(self)
        self.ana_duzen.Add(self.yazar_kutusu, 0, wx.ALL | wx.EXPAND, 5)

        etiket_seslendiren = wx.StaticText(self, label="&Seslendiren:")
        self.ana_duzen.Add(etiket_seslendiren, 0, wx.ALL, 5)
        self.seslendiren_kutusu = wx.TextCtrl(self)
        self.ana_duzen.Add(self.seslendiren_kutusu, 0, wx.ALL | wx.EXPAND, 5)

        etiket_konu = wx.StaticText(self, label="K&onu:")
        self.ana_duzen.Add(etiket_konu, 0, wx.ALL, 5)
        self.konu_kutusu = wx.TextCtrl(self)
        self.ana_duzen.Add(self.konu_kutusu, 0, wx.ALL | wx.EXPAND, 5)

        etiket_yayinevi = wx.StaticText(self, label="Yayıne&vi:")
        self.ana_duzen.Add(etiket_yayinevi, 0, wx.ALL, 5)
        self.yayinevi_kutusu = wx.TextCtrl(self)
        self.ana_duzen.Add(self.yayinevi_kutusu, 0, wx.ALL | wx.EXPAND, 5)

        etiket_format = wx.StaticText(self, label="Eser biçimi (&F):")
        self.ana_duzen.Add(etiket_format, 0, wx.ALL, 5)
        self.format_kutusu = wx.Choice(self, choices=["Yükleniyor..."])
        self.ana_duzen.Add(self.format_kutusu, 0, wx.ALL | wx.EXPAND, 5)

        etiket_dil = wx.StaticText(self, label="&Dil:")
        self.ana_duzen.Add(etiket_dil, 0, wx.ALL, 5)
        self.dil_kutusu = wx.Choice(self, choices=["Yükleniyor..."])
        self.ana_duzen.Add(self.dil_kutusu, 0, wx.ALL | wx.EXPAND, 5)

        etiket_tur = wx.StaticText(self, label="&Tür:")
        self.ana_duzen.Add(etiket_tur, 0, wx.ALL, 5)
        self.tur_kutusu = wx.Choice(self, choices=["Yükleniyor..."])
        self.ana_duzen.Add(self.tur_kutusu, 0, wx.ALL | wx.EXPAND, 5)

        etiket_alt_tur = wx.StaticText(self, label="Kitap alt türü (&L):")
        self.ana_duzen.Add(etiket_alt_tur, 0, wx.ALL, 5)
        self.alt_tur_kutusu = wx.Choice(self, choices=["Yükleniyor..."])
        self.ana_duzen.Add(self.alt_tur_kutusu, 0, wx.ALL | wx.EXPAND, 5)

        etiket_kurum = wx.StaticText(self, label="Alındığı kurum (&M):")
        self.ana_duzen.Add(etiket_kurum, 0, wx.ALL, 5)
        self.kurum_kutusu = wx.Choice(self, choices=["Yükleniyor..."])
        self.ana_duzen.Add(self.kurum_kutusu, 0, wx.ALL | wx.EXPAND, 5)

        butonlar_duzeni = wx.BoxSizer(wx.HORIZONTAL)

        self.ara_butonu = wx.Button(self, label="&Ara")
        self.ara_butonu.Bind(wx.EVT_BUTTON, self.arama_yap)
        butonlar_duzeni.Add(self.ara_butonu, 1, wx.ALL | wx.EXPAND, 5)

        self.temizle_butonu = wx.Button(self, label="Temi&zle")
        self.temizle_butonu.Bind(wx.EVT_BUTTON, self.formu_temizle)
        butonlar_duzeni.Add(self.temizle_butonu, 1, wx.ALL | wx.EXPAND, 5)

        self.favoriler_butonu = wx.Button(self, label="Favo&rilerim")
        self.favoriler_butonu.Bind(wx.EVT_BUTTON, self.favorileri_ac)
        butonlar_duzeni.Add(self.favoriler_butonu, 1, wx.ALL | wx.EXPAND, 5)

        self.ana_duzen.Add(butonlar_duzeni, 0, wx.ALL | wx.EXPAND, 0)

        etiket_liste = wx.StaticText(
            self,
            label="Arama sonuçları. A: eser adına, Y: yazara göre sıralar.",
        )
        self.ana_duzen.Add(etiket_liste, 0, wx.ALL, 5)

        self.sonuclar_listesi = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.sonuclar_listesi.InsertColumn(0, "Eser adı", width=350)
        self.sonuclar_listesi.InsertColumn(1, "Yazar", width=200)
        self.sonuclar_listesi.InsertColumn(2, "Seslendiren", width=200)
        self.sonuclar_listesi.InsertColumn(3, "Biçim", width=150)
        self.sonuclar_listesi.InsertItem(0, "Arama yapmak için Ara düğmesine basınız.")
        self.sonuclar_listesi.SetItemState(
            0,
            wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
            wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
        )
        self.ana_duzen.Add(self.sonuclar_listesi, 1, wx.ALL | wx.EXPAND, 5)

        self.sonuclar_listesi.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.kitap_secildi)
        self.sonuclar_listesi.Bind(wx.EVT_KEY_DOWN, self.listede_tusa_basildi)

        etiket_sayfa = wx.StaticText(self, label="Sayfa (&P):")
        self.ana_duzen.Add(etiket_sayfa, 0, wx.ALL, 5)

        self.sayfa_kutusu = wx.SpinCtrl(self, value="1", min=1, max=1000)
        self.ana_duzen.Add(self.sayfa_kutusu, 0, wx.ALL | wx.EXPAND, 5)
        self.sayfa_kutusu.Bind(wx.EVT_SPINCTRL, self.sayfa_degistirildi)

        self.kapat_butonu = wx.Button(self, wx.ID_CANCEL, label="&Kapat")
        self.kapat_butonu.Bind(wx.EVT_BUTTON, self.pencereyi_kapat)
        self.ana_duzen.Add(self.kapat_butonu, 0, wx.ALL | wx.CENTER, 5)

        self.Bind(wx.EVT_CLOSE, self.pencere_kapatiliyor)
        self.SetSizerAndFit(self.ana_duzen)
        self.eser_adi_kutusu.SetFocus()

        threading.Thread(target=self.verileri_cek, daemon=True).start()

    def pencere_kapatiliyor(self, event):
        self.pencere_kapaniyor = True
        event.Skip()

    def pencereyi_kapat(self, _event):
        self.pencere_kapaniyor = True
        self.EndModal(wx.ID_CANCEL)

    def pencere_kullanilabilir_mi(self):
        return not self.pencere_kapaniyor

    def arama_durumunu_ayarla(self, devam_ediyor):
        if not self.pencere_kullanilabilir_mi():
            return

        self.arama_devam_ediyor = bool(devam_ediyor)

        try:
            self.ara_butonu.Enable(not self.arama_devam_ediyor)
        except Exception:
            pass

    def formu_temizle(self, _event):
        self.arama_kimligi += 1
        self.arama_durumunu_ayarla(False)

        self.eser_adi_kutusu.Clear()
        self.yazar_kutusu.Clear()
        self.seslendiren_kutusu.Clear()
        self.konu_kutusu.Clear()
        self.yayinevi_kutusu.Clear()

        for kutu in (
            self.format_kutusu,
            self.dil_kutusu,
            self.tur_kutusu,
            self.alt_tur_kutusu,
            self.kurum_kutusu,
        ):
            if kutu.GetCount() > 0:
                kutu.SetSelection(0)

        self.sayfa_kutusu.SetValue(1)
        self.arama_sonuclari.clear()
        self.sonuclar_listesi.DeleteAllItems()
        self.sonuclar_listesi.InsertItem(0, "Arama yapmak için Ara düğmesine basınız.")
        self.sonuclar_listesi.SetItemState(
            0,
            wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
            wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
        )
        self.eser_adi_kutusu.SetFocus()
        ui.message("Form temizlendi.")

    def favorileri_ac(self, _event):
        pencere = FavorilerPenceresi(self)
        pencere.ShowModal()
        pencere.Destroy()

    def listede_tusa_basildi(self, event):
        tus = event.GetKeyCode()

        if tus in (ord("A"), ord("a")):
            self.listeyi_sirala("isim")
        elif tus in (ord("Y"), ord("y")):
            self.listeyi_sirala("yazar")
        else:
            event.Skip()

    def listeyi_sirala(self, kriter):
        if not self.arama_sonuclari:
            return

        self.siralama_yonu[kriter] = not self.siralama_yonu[kriter]
        ters_mi = not self.siralama_yonu[kriter]
        self.arama_sonuclari.sort(
            key=lambda kitap: kitap.get(kriter, "").casefold(),
            reverse=ters_mi,
        )
        self.sonuclari_listeye_yaz(self.arama_sonuclari)

        mesaj = "Eser adına" if kriter == "isim" else "Yazara"
        ui.message(f"{mesaj} göre sıralandı.")

    def secenekleri_ayikla(self, html_icerik, select_id):
        secenekler_listesi = []
        hedef = 'id="' + select_id + '"'
        baslangic = html_icerik.find(hedef)

        if baslangic != -1:
            bitis = html_icerik.find("</select>", baslangic)

            if bitis != -1:
                secenek_blogu = html_icerik[baslangic:bitis]
                secenek_deseni = r'<option\s+[^>]*value=["\']([^"\']*)["\'][^>]*>(.*?)</option>'
                secenekler = re.findall(secenek_deseni, secenek_blogu, re.DOTALL | re.IGNORECASE)

                for deger, gorunen_ad in secenekler:
                    secenekler_listesi.append((metni_temizle(gorunen_ad), html.unescape(deger)))

        if not secenekler_listesi:
            secenekler_listesi = [("Seçenek bulunamadı", "")]

        return secenekler_listesi

    def verileri_cek(self):
        try:
            html_icerik = self.adresten_html_oku(GETEM_KATALOG_ADRESI, SECENEK_ZAMAN_ASIMI)
            formatlar = self.secenekleri_ayikla(html_icerik, "edit-field-formati-value")
            diller = self.secenekleri_ayikla(html_icerik, "edit-field-dil-value")
            turler = self.secenekleri_ayikla(html_icerik, "edit-type")
            alt_turler = self.secenekleri_ayikla(html_icerik, "edit-field-alt-tur-kitap-value")
            kurumlar = self.secenekleri_ayikla(html_icerik, "edit-field-alindigikurum-value")
            wx.CallAfter(self.arayuzu_guncelle, formatlar, diller, turler, alt_turler, kurumlar, "tamam")

        except Exception:
            hata_listesi = [("Bağlantı hatası", "")]
            wx.CallAfter(
                self.arayuzu_guncelle,
                hata_listesi,
                hata_listesi,
                hata_listesi,
                hata_listesi,
                hata_listesi,
                "baglanti_hatasi",
            )

    def adresten_html_oku(self, adres, zaman_asimi):
        istek = urllib.request.Request(adres, headers={"User-Agent": KULLANICI_ARACISI})
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)

        with opener.open(istek, timeout=zaman_asimi) as yanit:
            return yanit.read().decode("utf-8", errors="replace")

    def kutuyu_doldur(self, kutu, veri_listesi):
        kutu.Freeze()

        try:
            kutu.Clear()

            for gorunen_ad, deger in veri_listesi:
                kutu.Append(gorunen_ad, deger)

            if kutu.GetCount() > 0:
                kutu.SetSelection(0)

        finally:
            kutu.Thaw()

    def arayuzu_guncelle(self, formatlar, diller, turler, alt_turler, kurumlar, durum="tamam"):
        if not self.pencere_kullanilabilir_mi():
            return

        self.SetTitle("GETEM E-Kütüphane")
        self.kutuyu_doldur(self.format_kutusu, formatlar)
        self.kutuyu_doldur(self.dil_kutusu, diller)
        self.kutuyu_doldur(self.tur_kutusu, turler)
        self.kutuyu_doldur(self.alt_tur_kutusu, alt_turler)
        self.kutuyu_doldur(self.kurum_kutusu, kurumlar)

        if durum == "baglanti_hatasi":
            self.sonuclar_listesi.DeleteAllItems()
            self.sonuclar_listesi.InsertItem(0, "GETEM sitesine bağlanılamadı. Lütfen internet bağlantınızı denetleyiniz.")
            self.sonuclar_listesi.SetItemState(
                0,
                wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
                wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
            )
            self.sonuclar_listesi.SetFocus()
            return

        self.eser_adi_kutusu.SetFocus()

    def sayfa_degistirildi(self, _event):
        self.arama_tetikle(sifirla=False)

    def arama_yap(self, _event):
        self.arama_tetikle(sifirla=True)

    def secili_degeri_al(self, kutu):
        secili = kutu.GetSelection()

        if secili == wx.NOT_FOUND:
            return ""

        deger = kutu.GetClientData(secili)
        return deger if deger is not None else ""

    def arama_tetikle(self, sifirla=True):
        if self.arama_devam_ediyor:
            ui.message("Arama devam ediyor. Lütfen bekleyiniz.")
            return

        if sifirla:
            self.sayfa_kutusu.SetValue(1)

        self.arama_kimligi += 1
        aktif_arama_kimligi = self.arama_kimligi
        sayfa_no = self.sayfa_kutusu.GetValue() - 1
        self.arama_durumunu_ayarla(True)

        self.sonuclar_listesi.DeleteAllItems()
        self.sonuclar_listesi.InsertItem(0, "Arama yapılıyor, lütfen bekleyiniz...")
        self.sonuclar_listesi.SetItemState(
            0,
            wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
            wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
        )
        self.sonuclar_listesi.SetFocus()

        arama_bilgileri = {
            "eser_adi": self.eser_adi_kutusu.GetValue(),
            "yazar": self.yazar_kutusu.GetValue(),
            "seslendiren": self.seslendiren_kutusu.GetValue(),
            "konu": self.konu_kutusu.GetValue(),
            "yayinevi": self.yayinevi_kutusu.GetValue(),
            "format": self.secili_degeri_al(self.format_kutusu),
            "dil": self.secili_degeri_al(self.dil_kutusu),
            "tur": self.secili_degeri_al(self.tur_kutusu),
            "alt_tur": self.secili_degeri_al(self.alt_tur_kutusu),
            "kurum": self.secili_degeri_al(self.kurum_kutusu),
            "sayfa": sayfa_no,
        }

        threading.Thread(
            target=self.sonuclari_cek,
            args=(arama_bilgileri, aktif_arama_kimligi),
            daemon=True,
        ).start()

    def sonuclari_cek(self, arama_bilgileri, arama_kimligi):
        parametreler = {
            "title": arama_bilgileri["eser_adi"],
            "field_yazar_value": arama_bilgileri["yazar"],
            "field_seslendiren_value": arama_bilgileri["seslendiren"],
            "body_value": arama_bilgileri["konu"],
            "field_yayinevi_value": arama_bilgileri["yayinevi"],
            "field_formati_value": arama_bilgileri["format"],
            "field_dil_value": arama_bilgileri["dil"],
            "type": arama_bilgileri["tur"],
            "field_alt_tur_kitap_value": arama_bilgileri["alt_tur"],
            "field_alindigikurum_value": arama_bilgileri["kurum"],
            "page": str(arama_bilgileri["sayfa"]),
        }

        sorgu = urllib.parse.urlencode(parametreler)
        tam_adres = GETEM_KATALOG_ADRESI + "&" + sorgu

        try:
            html_icerik = self.adresten_html_oku(tam_adres, ARAMA_ZAMAN_ASIMI)
        except Exception:
            wx.CallAfter(self.sonuclari_goster, arama_kimligi, [], "baglanti_hatasi")
            return

        try:
            kitaplar = self.kitaplari_ayikla(html_icerik)
            wx.CallAfter(self.sonuclari_goster, arama_kimligi, kitaplar, "tamam")
        except Exception:
            wx.CallAfter(self.sonuclari_goster, arama_kimligi, [], "cozumleme_hatasi")

    def kitaplari_ayikla(self, html_icerik):
        satirlar = html_icerik.split('<div class="views-row')
        kitaplar = []

        for satir in satirlar[1:]:
            link_isim_match = re.search(
                r'<div class="views-field views-field-title">\s*'
                r'<span class="field-content"><a href="([^"]*)">(.*?)</a>',
                satir,
                re.DOTALL | re.IGNORECASE,
            )

            if not link_isim_match:
                continue

            link = metni_temizle(link_isim_match.group(1))
            isim = metni_temizle(link_isim_match.group(2)) or "Bilinmiyor"

            yazar = self.alan_metnini_al(
                satir,
                r'<div class="views-field views-field-field-yazar">\s*'
                r'<div class="field-content">(.*?)</div>',
                "Bilinmiyor",
            )
            seslendiren = self.alan_metnini_al(
                satir,
                r'<div class="views-field views-field-field-seslendiren">\s*'
                r'<div class="field-content">(?:Seslendiren:\s*)?(.*?)</div>',
                "Bilinmiyor",
            )
            formati = self.alan_metnini_al(
                satir,
                r'<span class="views-field views-field-field-formati">\s*'
                r'<span class="field-content">(.*?)</span>',
                "Bilinmiyor",
            )
            aciklama = self.alan_metnini_al(
                satir,
                r'<div class="views-field views-field-body">\s*'
                r'<div class="field-content">(.*?)</div>\s*</div>',
                "Açıklama bulunamadı.",
            )

            kitaplar.append(
                {
                    "isim": isim,
                    "yazar": yazar,
                    "seslendiren": seslendiren,
                    "format": formati,
                    "aciklama": aciklama,
                    "link": link,
                }
            )

        return kitaplar

    def alan_metnini_al(self, metin, desen, varsayilan):
        sonuc = re.search(desen, metin, re.DOTALL | re.IGNORECASE)

        if not sonuc:
            return varsayilan

        temiz_metin = metni_temizle(sonuc.group(1))
        return temiz_metin if temiz_metin else varsayilan

    def sonuclari_goster(self, arama_kimligi, kitap_listesi, durum="tamam"):
        if not self.pencere_kullanilabilir_mi():
            return

        if arama_kimligi != self.arama_kimligi:
            return

        self.arama_durumunu_ayarla(False)
        self.sonuclar_listesi.DeleteAllItems()
        self.arama_sonuclari.clear()

        if durum == "baglanti_hatasi":
            self.sonuclar_listesi.InsertItem(0, "GETEM sitesine bağlanılamadı. Lütfen internet bağlantınızı denetleyiniz.")
        elif durum == "cozumleme_hatasi":
            self.sonuclar_listesi.InsertItem(0, "GETEM sayfası okunamadı veya beklenen yapıda değil.")
        elif not kitap_listesi:
            self.sonuclar_listesi.InsertItem(0, "Aradığınız ölçütlere veya sayfaya uygun eser bulunamadı.")
        else:
            self.arama_sonuclari = kitap_listesi
            self.sonuclari_listeye_yaz(kitap_listesi)
            return

        self.sonuclar_listesi.SetItemState(
            0,
            wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
            wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
        )
        self.sonuclar_listesi.SetFocus()

    def sonuclari_listeye_yaz(self, kitap_listesi):
        self.sonuclar_listesi.DeleteAllItems()

        for index, kitap in enumerate(kitap_listesi):
            self.sonuclar_listesi.InsertItem(index, liste_metnini_kisalt(kitap.get("isim", "Bilinmiyor")))
            self.sonuclar_listesi.SetItem(index, 1, liste_metnini_kisalt(kitap.get("yazar", "Bilinmiyor")))
            self.sonuclar_listesi.SetItem(index, 2, liste_metnini_kisalt(kitap.get("seslendiren", "Bilinmiyor")))
            self.sonuclar_listesi.SetItem(index, 3, liste_metnini_kisalt(kitap.get("format", "Bilinmiyor")))

        if kitap_listesi:
            self.sonuclar_listesi.SetItemState(
                0,
                wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
                wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
            )

        self.sonuclar_listesi.SetFocus()

    def kitap_secildi(self, event):
        index = event.GetIndex()

        if self.arama_sonuclari and index < len(self.arama_sonuclari):
            detay_penceresi = DetayPenceresi(self, self.arama_sonuclari[index])
            detay_penceresi.ShowModal()
            detay_penceresi.Destroy()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super().__init__()
        self.getem_penceresi_acik = False
        self.menu_olustur()

    def menu_olustur(self):
        self.tools_menu = gui.mainFrame.sysTrayIcon.toolsMenu
        self.getem_menu = wx.Menu()

        self.item_getem = self.getem_menu.Append(
            wx.ID_ANY,
            "&GETEM",
            "GETEM arama penceresini açar.",
        )
        gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.menu_getem_ac, self.item_getem)

        self.item_yardim = self.getem_menu.Append(
            wx.ID_ANY,
            "&Yardım",
            "Eklenti yardım dosyasını açar.",
        )
        gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.menu_yardim_ac, self.item_yardim)

        self.getem_menu_item = self.tools_menu.AppendSubMenu(
            self.getem_menu,
            "GETEM E-&Kütüphane",
        )

    def terminate(self):
        try:
            gui.mainFrame.sysTrayIcon.Unbind(wx.EVT_MENU, id=self.item_getem.GetId())
            gui.mainFrame.sysTrayIcon.Unbind(wx.EVT_MENU, id=self.item_yardim.GetId())
            self.tools_menu.Remove(self.getem_menu_item)
        except Exception:
            pass

        super().terminate()

    def menu_getem_ac(self, _event):
        self.getem_pencereyi_baslat()

    def menu_yardim_ac(self, _event):
        kok_klasor = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        yardim_yolu = os.path.join(kok_klasor, "doc/tr", "readme.html")

        if not os.path.exists(yardim_yolu):
            ui.message("Yardım dosyası bulunamadı.")
            return

        try:
            os.startfile(yardim_yolu)
        except Exception:
            ui.message("Yardım dosyası açılamadı.")

    @script(
        description="GETEM arama penceresini açar.",
        category=EKLENTI_KATEGORISI,
        gesture="kb:control+shift+g",
    )
    def script_getemAc(self, _gesture):
        self.getem_pencereyi_baslat()

    def getem_pencereyi_baslat(self):
        if self.getem_penceresi_acik:
            ui.message("GETEM penceresi zaten açık.")
            return

        def calistir():
            if self.getem_penceresi_acik:
                ui.message("GETEM penceresi zaten açık.")
                return

            self.getem_penceresi_acik = True
            pencere = None

            try:
                pencere = GetemPenceresi(gui.mainFrame)
                pencere.Raise()
                pencere.SetFocus()
                pencere.ShowModal()
            finally:
                if pencere is not None:
                    pencere.pencere_kapaniyor = True
                    pencere.Destroy()
                self.getem_penceresi_acik = False

        wx.CallAfter(calistir)
