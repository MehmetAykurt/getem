# Güncelleme Motoru
# Telif Hakkı (C) 2026 Mehmet Aykurt

import urllib.request
import json
import threading
import wx
import webbrowser
import gui
import globalPluginHandler

MEVCUT_SURUM = "1.0.0"
GUNCELLEME_LINKI = "https://raw.githubusercontent.com/MehmetAykurt/getem/main/update.json"

def surumleri_karsilastir(sunucu_surum, mevcut_surum):
    try:
        return float(sunucu_surum) > float(mevcut_surum)
    except:
        return sunucu_surum != mevcut_surum

def gizlice_kontrol_et():
    try:
        req = urllib.request.Request(GUNCELLEME_LINKI, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            veri = json.loads(response.read().decode('utf-8'))
            
            sunucu_surum = veri.get("surum")
            indirme_linki = veri.get("link")
            aciklama = veri.get("aciklama", "Yeni bir sürüm mevcut ve sizi bekliyor!")

            if sunucu_surum and surumleri_karsilastir(sunucu_surum, MEVCUT_SURUM):
                wx.CallAfter(guncelleme_penceresi_goster, sunucu_surum, indirme_linki, aciklama)
    except Exception:
        pass

def guncelleme_penceresi_goster(yeni_surum, link, aciklama):
    cevap = gui.messageBox(
        f"Getem E-Kütüphane\n\n({yeni_surum})\n\nYenilikler:\n{aciklama}\n\nŞimdi güncellemek ister misiniz?",
        "Yeni Güncelleme Uyarısı!",
        wx.YES_NO | wx.ICON_INFORMATION
    )
    if cevap == wx.YES:
        webbrowser.open(link)

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super(GlobalPlugin, self).__init__()
        threading.Thread(target=gizlice_kontrol_et).start()