# GETEM E-Kütüphane NVDA Eklentisi
# Telif Hakkı (C) 2026 Mehmet Aykurt
# Tarih: 1 Mayıs 2026
# Geliştirici: Mehmet Aykurt <m.aykurt38@gmail.com>
#
# Bu eklenti, görme engelli bireylerin GETEM e-katalog sistemine NVDA üzerinden
# hızlı ve erişilebilir bir şekilde ulaşabilmesi amacıyla büyük bir özenle geliştirilmiştir.
# Özgür Yazılım Vakfı tarafından yayımlanan GNU Genel Kamu Lisansı (GPL) koşulları 
# altında açık kaynak kodlu olarak dağıtılmaktadır.

import globalPluginHandler
import wx
import gui
import urllib.request
import urllib.parse
import re
import threading
import webbrowser
import ui
import json
import os

FAVORILER_DOSYASI = os.path.join(os.path.dirname(__file__), "getem_favoriler.json")

def favorileri_yukle():
    if os.path.exists(FAVORILER_DOSYASI):
        try:
            with open(FAVORILER_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def favorileri_kaydet(liste):
    try:
        with open(FAVORILER_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(liste, f, ensure_ascii=False, indent=4)
    except:
        pass

class DetayPenceresi(wx.Dialog):
    def __init__(self, parent, kitap):
        super(DetayPenceresi, self).__init__(parent, title="Kitap Detayı - " + kitap["isim"])
        self.kitap = kitap
        
        link = kitap["link"]
        if link.startswith("/"):
            self.kitap_linki = "https://getem.boun.edu.tr" + link
        elif not link.startswith("http"):
            self.kitap_linki = "https://getem.boun.edu.tr/" + link
        else:
            self.kitap_linki = link
            
        duzen = wx.BoxSizer(wx.VERTICAL)
        
        self.bilgi_metni = "Eser Adı: " + kitap["isim"] + "\n"
        self.bilgi_metni += "Yazar: " + kitap["yazar"] + "\n"
        self.bilgi_metni += "Seslendiren: " + kitap["seslendiren"] + "\n"
        self.bilgi_metni += "Format: " + kitap["format"] + "\n\n"
        self.bilgi_metni += "Konusu / Açıklama:\n" + kitap["aciklama"]
        
        self.metin_kutusu = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, value=self.bilgi_metni)
        duzen.Add(self.metin_kutusu, 1, wx.ALL | wx.EXPAND, 5)
        
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
        
        duzen.Add(buton_duzeni, 0, wx.CENTER)
        
        self.SetSizer(duzen)
        self.SetSize((700, 500))
        self.CenterOnParent()
        self.metin_kutusu.SetFocus()

    def tarayicida_ac(self, event):
        webbrowser.open(self.kitap_linki)

    def bilgileri_kopyala(self, event):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(self.bilgi_metni))
            wx.TheClipboard.Close()
            ui.message("Kitap bilgileri panoya kopyalandı.")

    def favoriye_ekle(self, event):
        favoriler = favorileri_yukle()
        if not any(f["link"] == self.kitap["link"] for f in favoriler):
            favoriler.append(self.kitap)
            favorileri_kaydet(favoriler)
            ui.message("Kitap favorilerinize eklendi.")
        else:
            ui.message("Bu kitap zaten favorilerinizde ekli.")

class FavorilerPenceresi(wx.Dialog):
    def __init__(self, parent):
        super(FavorilerPenceresi, self).__init__(parent, title="Favorilerim / Okuma Listem")
        self.favoriler = favorileri_yukle()
        
        self.ana_duzen = wx.BoxSizer(wx.VERTICAL)
        
        etiket_liste = wx.StaticText(self, label="Favori Kitaplarınız:")
        self.ana_duzen.Add(etiket_liste, 0, wx.ALL, 5)
        
        self.sonuclar_listesi = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.sonuclar_listesi.InsertColumn(0, "Eser Adı", width=350)
        self.sonuclar_listesi.InsertColumn(1, "Yazar", width=200)
        self.sonuclar_listesi.InsertColumn(2, "Seslendiren", width=200)
        self.sonuclar_listesi.InsertColumn(3, "Format", width=150)
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
        if self.favoriler:
            self.sonuclar_listesi.SetFocus()

    def listeyi_doldur(self):
        self.sonuclar_listesi.DeleteAllItems()
        if not self.favoriler:
            self.sonuclar_listesi.InsertItem(0, "Favori listeniz şu an boş.")
            self.sonuclar_listesi.SetItemState(0, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)
        else:
            for index, kitap in enumerate(self.favoriler):
                self.sonuclar_listesi.InsertItem(index, kitap["isim"])
                self.sonuclar_listesi.SetItem(index, 1, kitap["yazar"])
                self.sonuclar_listesi.SetItem(index, 2, kitap["seslendiren"])
                self.sonuclar_listesi.SetItem(index, 3, kitap["format"])
            self.sonuclar_listesi.SetItemState(0, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)

    def kitap_secildi(self, event):
        index = event.GetIndex()
        if self.favoriler and index < len(self.favoriler):
            kitap = self.favoriler[index]
            detay_penceresi = DetayPenceresi(self, kitap)
            detay_penceresi.ShowModal()
            detay_penceresi.Destroy()

    def favoriden_sil(self, event):
        secili = self.sonuclar_listesi.GetFirstSelected()
        if self.favoriler and secili != -1 and secili < len(self.favoriler):
            del self.favoriler[secili]
            favorileri_kaydet(self.favoriler)
            self.listeyi_doldur()
            ui.message("Kitap favorilerden silindi.")

class GetemPenceresi(wx.Dialog):
    def __init__(self, parent):
        super(GetemPenceresi, self).__init__(parent, title="GETEM E-Kütüphane - Veriler Yükleniyor...")
        
        self.arama_sonuclari = []
        self.siralama_yonu = {"isim": False, "yazar": False}
        
        self.ana_duzen = wx.BoxSizer(wx.VERTICAL)
        
        etiket_eser_adi = wx.StaticText(self, label="&Eser Adı:")
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
        
        etiket_konusu = wx.StaticText(self, label="K&onusu:")
        self.ana_duzen.Add(etiket_konusu, 0, wx.ALL, 5)
        self.konusu_kutusu = wx.TextCtrl(self)
        self.ana_duzen.Add(self.konusu_kutusu, 0, wx.ALL | wx.EXPAND, 5)
        
        etiket_yayinevi = wx.StaticText(self, label="Yayıne&vi:")
        self.ana_duzen.Add(etiket_yayinevi, 0, wx.ALL, 5)
        self.yayinevi_kutusu = wx.TextCtrl(self)
        self.ana_duzen.Add(self.yayinevi_kutusu, 0, wx.ALL | wx.EXPAND, 5)
        
        etiket_format = wx.StaticText(self, label="Eser &Formatı:")
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
        
        etiket_alt_tur = wx.StaticText(self, label="Kitap A&lt Türü:")
        self.ana_duzen.Add(etiket_alt_tur, 0, wx.ALL, 5)
        self.alt_tur_kutusu = wx.Choice(self, choices=["Yükleniyor..."])
        self.ana_duzen.Add(self.alt_tur_kutusu, 0, wx.ALL | wx.EXPAND, 5)
        
        etiket_kurum = wx.StaticText(self, label="Alındığı Kuru&m:")
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
        
        etiket_liste = wx.StaticText(self, label="Arama Sonuçları (A: Eser Adına, Y: Yazara göre sıralar):")
        self.ana_duzen.Add(etiket_liste, 0, wx.ALL, 5)
        
        self.sonuclar_listesi = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.sonuclar_listesi.InsertColumn(0, "Eser Adı", width=350)
        self.sonuclar_listesi.InsertColumn(1, "Yazar", width=200)
        self.sonuclar_listesi.InsertColumn(2, "Seslendiren", width=200)
        self.sonuclar_listesi.InsertColumn(3, "Format", width=150)
        self.sonuclar_listesi.InsertItem(0, "Arama yapmak için Ara butonuna basınız.")
        self.sonuclar_listesi.SetItemState(0, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)
        self.ana_duzen.Add(self.sonuclar_listesi, 1, wx.ALL | wx.EXPAND, 5)
        
        self.sonuclar_listesi.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.kitap_secildi)
        self.sonuclar_listesi.Bind(wx.EVT_KEY_DOWN, self.listede_tusa_basildi)
        
        etiket_sayfa = wx.StaticText(self, label="Sayfa (&P):")
        self.ana_duzen.Add(etiket_sayfa, 0, wx.ALL, 5)
        
        self.sayfa_kutusu = wx.SpinCtrl(self, value="1", min=1, max=1000)
        self.ana_duzen.Add(self.sayfa_kutusu, 0, wx.ALL | wx.EXPAND, 5)
        self.sayfa_kutusu.Bind(wx.EVT_SPINCTRL, self.sayfa_degistirildi)
        
        self.kapat_butonu = wx.Button(self, wx.ID_CANCEL, label="&Kapat")
        self.ana_duzen.Add(self.kapat_butonu, 0, wx.ALL | wx.CENTER, 5)
        
        self.SetSizerAndFit(self.ana_duzen)
        self.eser_adi_kutusu.SetFocus()

        threading.Thread(target=self.verileri_cek).start()

    def formu_temizle(self, event):
        self.eser_adi_kutusu.Clear()
        self.yazar_kutusu.Clear()
        self.seslendiren_kutusu.Clear()
        self.konusu_kutusu.Clear()
        self.yayinevi_kutusu.Clear()
        
        if self.format_kutusu.GetCount() > 0:
            self.format_kutusu.SetSelection(0)
        if self.dil_kutusu.GetCount() > 0:
            self.dil_kutusu.SetSelection(0)
        if self.tur_kutusu.GetCount() > 0:
            self.tur_kutusu.SetSelection(0)
        if self.alt_tur_kutusu.GetCount() > 0:
            self.alt_tur_kutusu.SetSelection(0)
        if self.kurum_kutusu.GetCount() > 0:
            self.kurum_kutusu.SetSelection(0)
            
        self.sayfa_kutusu.SetValue(1)
        
        self.sonuclar_listesi.DeleteAllItems()
        self.arama_sonuclari.clear()
        self.sonuclar_listesi.InsertItem(0, "Arama yapmak için Ara butonuna basınız.")
        self.sonuclar_listesi.SetItemState(0, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)
        
        self.eser_adi_kutusu.SetFocus()

    def favorileri_ac(self, event):
        pencere = FavorilerPenceresi(self)
        pencere.ShowModal()
        pencere.Destroy()

    def listede_tusa_basildi(self, event):
        tus = event.GetKeyCode()
        if tus == ord('A') or tus == ord('a'):
            self.listeyi_sirala("isim")
        elif tus == ord('Y') or tus == ord('y'):
            self.listeyi_sirala("yazar")
        else:
            event.Skip()

    def listeyi_sirala(self, kriter):
        if not self.arama_sonuclari:
            return
            
        self.siralama_yonu[kriter] = not self.siralama_yonu[kriter]
        ters_mi = not self.siralama_yonu[kriter]
        
        self.arama_sonuclari.sort(key=lambda x: x[kriter].lower(), reverse=ters_mi)
        
        self.sonuclar_listesi.DeleteAllItems()
        
        for index, kitap in enumerate(self.arama_sonuclari):
            self.sonuclar_listesi.InsertItem(index, kitap["isim"])
            self.sonuclar_listesi.SetItem(index, 1, kitap["yazar"])
            self.sonuclar_listesi.SetItem(index, 2, kitap["seslendiren"])
            self.sonuclar_listesi.SetItem(index, 3, kitap["format"])
            
        self.sonuclar_listesi.SetItemState(0, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)
        
        mesaj = "Eser adına" if kriter == "isim" else "Yazara"
        ui.message(f"{mesaj} göre sıralandı.")

    def secenekleri_ayikla(self, html, select_id):
        secenekler_listesi = []
        hedef_id = 'id="' + select_id + '"'
        baslangic = html.find(hedef_id)
        
        if baslangic != -1:
            bitis = html.find('</select>', baslangic)
            if bitis != -1:
                options_blogu = html[baslangic:bitis]
                option_deseni = r'<option value="([^"]*)".*?>(.*?)</option>'
                secenekler = re.findall(option_deseni, options_blogu)
                
                for deger, gorunen_isim in secenekler:
                    gorunen_isim = gorunen_isim.replace("&#039;", "'").replace("&amp;", "&").strip()
                    secenekler_listesi.append((gorunen_isim, deger))
                    
        if not secenekler_listesi:
            secenekler_listesi = [("Seçenekler bulunamadı", "")]
            
        return secenekler_listesi

    def verileri_cek(self):
        url = "https://getem.boun.edu.tr/?q=katalog"
        try:
            istek = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            
            with opener.open(istek, timeout=8) as yanit:
                html_icerik = yanit.read().decode('utf-8')
            
            formatlar = self.secenekleri_ayikla(html_icerik, "edit-field-formati-value")
            diller = self.secenekleri_ayikla(html_icerik, "edit-field-dil-value")
            turler = self.secenekleri_ayikla(html_icerik, "edit-type")
            altturler = self.secenekleri_ayikla(html_icerik, "edit-field-alt-tur-kitap-value")
            kurumlar = self.secenekleri_ayikla(html_icerik, "edit-field-alindigikurum-value")
            
            wx.CallAfter(self.arayuzu_guncelle, formatlar, diller, turler, altturler, kurumlar)
            
        except Exception:
            hata_listesi = [("Bağlantı hatası!", "")]
            wx.CallAfter(self.arayuzu_guncelle, hata_listesi, hata_listesi, hata_listesi, hata_listesi, hata_listesi)

    def kutuyu_doldur(self, kutu, veri_listesi):
        kutu.Freeze() 
        kutu.Clear()
        for gorunen_isim, deger in veri_listesi:
            kutu.Append(gorunen_isim, deger)
        kutu.SetSelection(0)
        kutu.Thaw()

    def arayuzu_guncelle(self, formatlar, diller, turler, altturler, kurumlar):
        self.SetTitle("GETEM E-Kütüphane")
        
        self.kutuyu_doldur(self.format_kutusu, formatlar)
        self.kutuyu_doldur(self.dil_kutusu, diller)
        self.kutuyu_doldur(self.tur_kutusu, turler)
        self.kutuyu_doldur(self.alt_tur_kutusu, altturler)
        self.kutuyu_doldur(self.kurum_kutusu, kurumlar)
        
        self.eser_adi_kutusu.SetFocus()

    def sayfa_degistirildi(self, event):
        self.arama_tetikle(sifirla=False)

    def arama_yap(self, event):
        self.arama_tetikle(sifirla=True)

    def arama_tetikle(self, sifirla=True):
        if sifirla:
            self.sayfa_kutusu.SetValue(1)
        
        sayfa_no = self.sayfa_kutusu.GetValue() - 1
        
        self.sonuclar_listesi.DeleteAllItems()
        self.sonuclar_listesi.InsertItem(0, "Arama yapılıyor, lütfen bekleyin...")
        self.sonuclar_listesi.SetItemState(0, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)
        self.sonuclar_listesi.SetFocus()
        
        secilen_eser_adi = self.eser_adi_kutusu.GetValue()
        secilen_yazar = self.yazar_kutusu.GetValue()
        secilen_seslendiren = self.seslendiren_kutusu.GetValue()
        secilen_konusu = self.konusu_kutusu.GetValue()
        secilen_yayinevi = self.yayinevi_kutusu.GetValue()
        
        secilen_format = self.format_kutusu.GetClientData(self.format_kutusu.GetSelection())
        secilen_dil = self.dil_kutusu.GetClientData(self.dil_kutusu.GetSelection())
        secilen_tur = self.tur_kutusu.GetClientData(self.tur_kutusu.GetSelection())
        secilen_alt_tur = self.alt_tur_kutusu.GetClientData(self.alt_tur_kutusu.GetSelection())
        secilen_kurum = self.kurum_kutusu.GetClientData(self.kurum_kutusu.GetSelection())
        
        threading.Thread(target=self.sonuclari_cek, args=(
            secilen_eser_adi, secilen_yazar, secilen_seslendiren, secilen_konusu, secilen_yayinevi,
            secilen_format, secilen_dil, secilen_tur, secilen_alt_tur, secilen_kurum, sayfa_no
        )).start()

    def sonuclari_cek(self, sec_eser_adi, sec_yazar, sec_seslendiren, sec_konusu, sec_yayinevi, sec_format, sec_dil, sec_tur, sec_alttur, sec_kurum, sayfa_no):
        temel_url = "https://getem.boun.edu.tr/?q=katalog"
        
        parametreler = {
            'title': sec_eser_adi,
            'field_yazar_value': sec_yazar,
            'field_seslendiren_value': sec_seslendiren,
            'body_value': sec_konusu,
            'field_yayinevi_value': sec_yayinevi,
            'field_formati_value': sec_format,
            'field_dil_value': sec_dil,
            'type': sec_tur,
            'field_alt_tur_kitap_value': sec_alttur,
            'field_alindigikurum_value': sec_kurum,
            'page': str(sayfa_no)
        }
        
        sorgu = urllib.parse.urlencode(parametreler)
        tam_url = temel_url + "&" + sorgu
        
        try:
            istek = urllib.request.Request(tam_url, headers={'User-Agent': 'Mozilla/5.0'})
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            
            with opener.open(istek, timeout=12) as yanit:
                html_icerik = yanit.read().decode('utf-8')
            
            satirlar = html_icerik.split('<div class="views-row')
            kitaplar = []
            
            for satir in satirlar[1:]:
                link_isim_match = re.search(r'<div class="views-field views-field-title">\s*<span class="field-content"><a href="([^"]*)">(.*?)</a>', satir, re.DOTALL | re.IGNORECASE)
                if not link_isim_match:
                    continue
                
                isim = link_isim_match.group(2).replace("&#039;", "'").replace("&amp;", "&").strip()
                link = link_isim_match.group(1).strip()
                
                yazar_match = re.search(r'<div class="views-field views-field-field-yazar">\s*<div class="field-content">(.*?)</div>', satir, re.DOTALL | re.IGNORECASE)
                yazar = yazar_match.group(1).replace("&#039;", "'").replace("&amp;", "&").strip() if yazar_match else "Bilinmiyor"
                
                seslendiren_match = re.search(r'<div class="views-field views-field-field-seslendiren">\s*<div class="field-content">(?:Seslendiren:\s*)?(.*?)</div>', satir, re.DOTALL | re.IGNORECASE)
                seslendiren = seslendiren_match.group(1).replace("&#039;", "'").replace("&amp;", "&").strip() if seslendiren_match else "Bilinmiyor"
                
                format_match = re.search(r'<span class="views-field views-field-field-formati">\s*<span class="field-content">(.*?)</span>', satir, re.DOTALL | re.IGNORECASE)
                formati = format_match.group(1).replace("&#039;", "'").replace("&amp;", "&").strip() if format_match else "Bilinmiyor"
                
                aciklama_match = re.search(r'<div class="views-field views-field-body">\s*<div class="field-content">(.*?)</div>\s*</div>', satir, re.DOTALL | re.IGNORECASE)
                if aciklama_match:
                    aciklama = aciklama_match.group(1)
                    aciklama = aciklama.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
                    aciklama = re.sub(r'<[^>]+>', '', aciklama)
                    aciklama = aciklama.replace("&#039;", "'").replace("&amp;", "&").replace("&quot;", '"').strip()
                else:
                    aciklama = "Açıklama bulunamadı."
                
                kitaplar.append({
                    "isim": isim,
                    "yazar": yazar,
                    "seslendiren": seslendiren,
                    "format": formati,
                    "aciklama": aciklama,
                    "link": link
                })
            
            wx.CallAfter(self.sonuclari_goster, kitaplar)
            
        except Exception:
            wx.CallAfter(self.sonuclari_goster, [])

    def sonuclari_goster(self, kitap_listesi):
        self.sonuclar_listesi.DeleteAllItems()
        self.arama_sonuclari.clear()
        
        if not kitap_listesi:
            self.sonuclar_listesi.InsertItem(0, "Aradığınız kriterlere veya sayfaya uygun eser bulunamadı.")
        else:
            self.arama_sonuclari = kitap_listesi
            for index, kitap in enumerate(kitap_listesi):
                self.sonuclar_listesi.InsertItem(index, kitap["isim"])
                self.sonuclar_listesi.SetItem(index, 1, kitap["yazar"])
                self.sonuclar_listesi.SetItem(index, 2, kitap["seslendiren"])
                self.sonuclar_listesi.SetItem(index, 3, kitap["format"])
        
        self.sonuclar_listesi.SetItemState(0, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)
        self.sonuclar_listesi.SetFocus()

    def kitap_secildi(self, event):
        index = event.GetIndex()
        if self.arama_sonuclari and index < len(self.arama_sonuclari):
            kitap = self.arama_sonuclari[index]
            detay_penceresi = DetayPenceresi(self, kitap)
            detay_penceresi.ShowModal()
            detay_penceresi.Destroy()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    
    def __init__(self):
        super(GlobalPlugin, self).__init__()
        self.menu_olustur()
        
    def menu_olustur(self):
        self.tools_menu = gui.mainFrame.sysTrayIcon.toolsMenu
        self.getem_menu = wx.Menu()
        
        self.item_getem = self.getem_menu.Append(wx.ID_ANY, "&GETEM", "GETEM arama penceresini açar")
        gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.menu_getem_ac, self.item_getem)
        
        self.item_yardim = self.getem_menu.Append(wx.ID_ANY, "&Yardım", "Eklenti yardım dosyasını açar")
        gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.menu_yardim_ac, self.item_yardim)
        
        self.getem_menu_item = self.tools_menu.AppendSubMenu(self.getem_menu, "GETEM E-&Kütüphane")

    def terminate(self):
        try:
            gui.mainFrame.sysTrayIcon.Unbind(wx.EVT_MENU, id=self.item_getem.GetId())
            gui.mainFrame.sysTrayIcon.Unbind(wx.EVT_MENU, id=self.item_yardim.GetId())
            self.tools_menu.Remove(self.getem_menu_item)
        except Exception:
            pass
        super(GlobalPlugin, self).terminate()

    def menu_getem_ac(self, event):
        self.getem_pencereyi_baslat()

    def menu_yardim_ac(self, event):
        kok_klasor = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        yardim_yolu = os.path.join(kok_klasor, "doc", "readme.html")
        
        if os.path.exists(yardim_yolu):
            try:
                os.startfile(yardim_yolu)
            except Exception:
                ui.message("Yardım dosyası tarayıcıda açılamadı.")
        else:
            ui.message("Yardım dosyası bulunamadı.")

    def script_getemAc(self, gesture):
        self.getem_pencereyi_baslat()
        
    script_getemAc.__doc__ = "GETEM arama penceresini açar."
    script_getemAc.category = "GETEM E-Kütüphane"
    
    def getem_pencereyi_baslat(self):
        def calistir():
            pencere = GetemPenceresi(gui.mainFrame)
            pencere.Raise()
            pencere.SetFocus()
            pencere.ShowModal()
            pencere.Destroy()
        wx.CallAfter(calistir)
        
    __gestures = {
        "kb:control+shift+g": "getemAc"
    }