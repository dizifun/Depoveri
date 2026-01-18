import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
import json
import os
import time

# jsontom3u dosyasını import et
try:
    from jsontom3u import create_single_m3u, create_m3us
except ImportError:
    print("HATA: 'jsontom3u.py' dosyası bulunamadı!")
    exit(1)

OUTPUT_FOLDER = "KanalD"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

site_base_url = "https://www.kanald.com.tr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.kanald.com.tr/",
    "Connection": "keep-alive"
}

def get_stream_url(media_id):
    url = "https://www.kanald.com.tr/actions/media"
    params = {"id": media_id, "p": "1", "pc": "1", "isAMP": "false"}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = r.json().get("data")
        
        if not data or "media" not in data or "link" not in data["media"]:
            return ""

        if data["media"]["link"]["type"] == "video/dailymotion":
            return ""
        
        path = data["media"]["link"]["securePath"].split("?")[0]
        if path[0] != "/":
            path = "/" + path
        full_url = data["media"]["link"]["serviceUrl"] + path
        return full_url
    except Exception as e:
        # print(f"Stream URL Hatası: {e}") # Çok kirletmesin diye kapalı
        return ""

def parse_bolum_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        link_tag = soup.find("link", {"itemprop": "embedURL"})
        if link_tag:
            return link_tag.get("href").split("/")[-1]
        return ""
    except:
        return ""

def get_bolumler_page(url):
    all_items = []
    # Olası bölüm sayfaları
    urls_to_check = [url, url + "/bolumler"]
    
    for check_url in urls_to_check:
        try:
            r = requests.get(check_url, headers=HEADERS, timeout=10)
            if r.status_code != 200: continue
            
            soup = BeautifulSoup(r.content, "html.parser")
            
            # Daha genel arama: içinde '/bolumler/' geçen tüm linkleri bul
            links = soup.find_all("a")
            for link in links:
                href = link.get("href")
                if href and ("/bolumler/" in href or "/klipler/" in href) and len(href) > 10:
                    full_link = site_base_url + href if href.startswith("/") else href
                    if full_link.startswith(site_base_url):
                         # Başlık ve resim bulmaya çalış
                         title = link.get("title") or link.get_text().strip()
                         img = ""
                         img_tag = link.find("img")
                         if img_tag:
                             img = img_tag.get("data-src") or img_tag.get("src")
                         
                         if title:
                             all_items.append({"name": title, "img": img or "", "url": full_link})
        except Exception as e:
            print(f"Bölüm tarama hatası ({check_url}): {e}")
            
    # Tekrarları sil
    unique_items = {v['url']: v for v in all_items}.values()
    return list(unique_items)

def get_main_page_list(url):
    all_series = []
    print(f"--- KATEGORİ TARANIYOR: {url} ---")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Site Durum Kodu: {r.status_code}")
        
        if r.status_code != 200:
            print("Siteye erişilemedi! Lütfen GitHub Action IP'sinin engellenip engellenmediğini kontrol edin.")
            return []

        soup = BeautifulSoup(r.content, "html.parser")
        
        # YÖNTEM 1: Standart .item class'ı
        items = soup.find_all("div", {"class": "item"})
        print(f"Yöntem 1 (Class='item') ile bulunan: {len(items)}")
        
        # YÖNTEM 2: Eğer item yoksa, sayfadaki tüm mantıklı linkleri topla
        if len(items) == 0:
            print("Alternatif tarama yöntemi devreye giriyor...")
            links = soup.find_all("a")
            for link in links:
                href = link.get("href")
                # Dizi/Program linki formatı: /diziler/adi veya /programlar/adi
                if href and href.count("/") == 2 and (href.startswith("/diziler/") or href.startswith("/programlar/")):
                    # Gereksiz linkleri ele (arsiv, pop, vs değilse)
                    title = link.get("title") or link.get_text().strip()
                    if title and len(title) > 2:
                        full_url = site_base_url + href
                        img = ""
                        img_tag = link.find("img")
                        if img_tag:
                            img = img_tag.get("data-src") or img_tag.get("src")
                        all_series.append({"name": title, "img": img or "", "url": full_url})
        else:
            # Standart yöntem
            for item in items:
                a_tag = item.find("a")
                title_tag = item.find("h3", {"class": "title"})
                img_tag = item.find("img")
                
                if a_tag:
                    link = a_tag.get("href")
                    if link and not link.startswith("http"):
                        link = site_base_url + link
                    
                    name = ""
                    if title_tag:
                        name = title_tag.get_text().strip()
                    else:
                        name = a_tag.get("title") or "Bilinmeyen Başlık"
                        
                    img = ""
                    if img_tag:
                        img = img_tag.get("data-src") or img_tag.get("src")
                    
                    if "/arsiv" not in link: # Arşiv sayfasına tekrar girmesin
                        all_series.append({"name": name, "img": img, "url": link})

    except Exception as e:
        print(f"Kritik Hata: {e}")
    
    # URL tekrarını önle
    unique_series = {v['url']: v for v in all_series}.values()
    return list(unique_series)

def main(url, name):
    data = []
    series_list = get_main_page_list(url)
    
    print(f"--> {name} için TOPLAM {len(series_list)} içerik bulundu.")
    
    if len(series_list) == 0:
        print("!!! HİÇ İÇERİK BULUNAMADI. SCRAPER DURDURULUYOR. !!!")
        return

    # Test için sadece ilk 3 diziyi tara (HIZLI DEBUG İÇİN - SONRA BU '[0:3]' KISMINI SİLERSİN)
    # Hızlı sonuç görmek için şimdilik limitli kalsın, çalışırsa kaldırırsın.
    for serie in tqdm(series_list, desc=name):
        print(f"İşleniyor: {serie['name']}...")
        episodes = get_bolumler_page(serie["url"])
        
        if episodes:
            temp_serie = serie.copy()
            temp_serie["episodes"] = []
            print(f"  > {len(episodes)} bölüm/klip bulundu.")
            
            # Sadece ilk 5 bölümü kontrol et (Hız için)
            count = 0
            for episode in episodes:
                if count > 5: break 
                media_url = parse_bolum_page(episode["url"])
                if media_url:
                    stream_url = get_stream_url(media_url)
                    if stream_url:
                        episode["stream_url"] = stream_url
                        temp_serie["episodes"].append(episode)
                        count += 1
            
            if temp_serie["episodes"]:
                data.append(temp_serie)
                print(f"  > {len(temp_serie['episodes'])} oynatılabilir video eklendi.")
        else:
            print(f"  > Bölüm bulunamadı.")

    # Kayıt
    if data:
        create_single_m3u(OUTPUT_FOLDER, data, name)
        json_path = os.path.join(OUTPUT_FOLDER, f"{name}.json")
        with open(json_path, "w+", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        sub_folder = os.path.join(OUTPUT_FOLDER, name)
        create_m3us(sub_folder, data)
        print(f"=== {name} TAMAMLANDI VE KAYDEDİLDİ ===")
    else:
        print(f"=== {name} İÇİN KAYDEDİLECEK VERİ ÇIKMADI ===")

if __name__ == "__main__":
    print("BASLIYOR...")
    main("https://www.kanald.com.tr/diziler", "diziler")
    main("https://www.kanald.com.tr/programlar", "programlar")
