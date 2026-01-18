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
    "Referer": "https://www.kanald.com.tr/"
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
    except:
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
    # Bölümler ve Klipler sayfalarını dene
    possible_urls = [url + "/bolumler", url]
    
    seen_urls = set()

    for p_url in possible_urls:
        if p_url in seen_urls: continue
        seen_urls.add(p_url)

        try:
            r = requests.get(p_url, headers=HEADERS, timeout=10)
            if r.status_code != 200: continue
            
            soup = BeautifulSoup(r.content, "html.parser")
            
            # Kartları bul
            # Genellikle 'card-item' veya 'item' class'ı kullanılır
            items = soup.find_all("div", {"class": "item"}) # Genel yapı
            
            for item in items:
                a_tag = item.find("a")
                title_tag = item.find("h3") or item.find("div", {"class": "title"})
                img_tag = item.find("img")

                if a_tag:
                    href = a_tag.get("href")
                    if href and ("/bolumler/" in href or "/klipler/" in href):
                        full_link = site_base_url + href if href.startswith("/") else href
                        
                        name = "Bölüm"
                        if title_tag:
                            name = title_tag.get_text().strip()
                        elif a_tag.get("title"):
                            name = a_tag.get("title")
                            
                        img = ""
                        if img_tag:
                            img = img_tag.get("data-src") or img_tag.get("src")
                        
                        all_items.append({"name": name, "img": img or "", "url": full_link})
        except:
            pass
            
    # Tekrarları temizle
    unique_items = {v['url']: v for v in all_items}.values()
    return list(unique_items)

def get_archive_list(start_url):
    all_series = []
    print(f"--- ARŞİV TARANIYOR: {start_url} ---")
    
    # İlk sayfayı çek
    try:
        r = requests.get(start_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Sayfalama linklerini bul
        page_links = [start_url] # İlk sayfa
        pagination = soup.find("ul", {"class": "pagination"})
        if pagination:
            for li in pagination.find_all("li"):
                a = li.find("a")
                if a and a.get("href"):
                    href = a.get("href")
                    full_link = site_base_url + href if href.startswith("/") else start_url.split("?")[0] + href
                    if full_link not in page_links:
                        page_links.append(full_link)
        
        print(f"Toplam {len(page_links)} arşiv sayfası bulundu.")
        
        # Tüm sayfaları gez
        for page_url in page_links:
            try:
                # print(f"Sayfa taranıyor: {page_url}")
                r_page = requests.get(page_url, headers=HEADERS, timeout=10)
                s_page = BeautifulSoup(r_page.content, "html.parser")
                
                # Arşivdeki öğeleri bul
                items = s_page.find_all("div", {"class": "item"})
                
                for item in items:
                    a_tag = item.find("a")
                    t_tag = item.find("h3", {"class": "title"})
                    i_tag = item.find("img")
                    
                    if a_tag:
                        link = a_tag.get("href")
                        # Sadece ana dizi/program linklerini al (bölüm veya klip linklerini alma)
                        # Arşiv listesinde linkler genelde /diziler/adi şeklindedir
                        if link.count("/") == 2 and (link.startswith("/diziler/") or link.startswith("/programlar/")):
                            full_url = site_base_url + link
                            name = t_tag.get_text().strip() if t_tag else a_tag.get("title") or "Bilinmeyen"
                            img = i_tag.get("data-src") or i_tag.get("src") if i_tag else ""
                            
                            all_series.append({"name": name, "img": img, "url": full_url})
            except:
                continue
                
    except Exception as e:
        print(f"Arşiv hatası: {e}")
        return []

    # Tekrarları sil
    unique_series = {v['url']: v for v in all_series}.values()
    return list(unique_series)

def main(url, name):
    data = []
    series_list = get_archive_list(url)
    
    print(f"--> {name} için TOPLAM {len(series_list)} içerik bulundu. Bölümler taranıyor...")
    
    # Hepsini tara
    for serie in tqdm(series_list, desc=name):
        episodes = get_bolumler_page(serie["url"])
        
        if episodes:
            temp_serie = serie.copy()
            temp_serie["episodes"] = []
            
            # Şimdilik hız için ilk 10 bölümü kontrol edelim (Limiti kaldırabilirsin)
            # count = 0
            for episode in episodes:
                # if count > 10: break
                media_url = parse_bolum_page(episode["url"])
                if media_url:
                    stream_url = get_stream_url(media_url)
                    if stream_url:
                        episode["stream_url"] = stream_url
                        temp_serie["episodes"].append(episode)
                        # count += 1
            
            if temp_serie["episodes"]:
                data.append(temp_serie)

    # Kayıt
    if data:
        create_single_m3u(OUTPUT_FOLDER, data, name)
        json_path = os.path.join(OUTPUT_FOLDER, f"{name}.json")
        with open(json_path, "w+", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        sub_folder = os.path.join(OUTPUT_FOLDER, name)
        create_m3us(sub_folder, data)
        print(f"=== {name} KAYDEDİLDİ ({len(data)} dizi/program) ===")
    else:
        print(f"=== {name} İÇİN OYNATILABİLİR VERİ BULUNAMADI ===")

if __name__ == "__main__":
    print("--- DİZİ ARŞİVİ ---")
    main("https://www.kanald.com.tr/diziler/arsiv", "arsiv-diziler")
    
    print("\n--- PROGRAM ARŞİVİ ---")
    main("https://www.kanald.com.tr/programlar/arsiv", "arsiv-programlar")
