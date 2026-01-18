import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
import json
import os

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

# Tarayıcı gibi görünmek için Header
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
}

def get_stream_url(media_id):
    url = "https://www.kanald.com.tr/actions/media"
    params = {"id": media_id, "p": "1", "pc": "1", "isAMP": "false"}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = r.json()["data"]
        
        if "media" not in data or "link" not in data["media"]:
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

def parse_bolumler_page(url):
    item_list = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Sayfadaki tüm .item class'lı öğeleri ara (Daha geniş kapsamlı)
        items = soup.find_all("div", {"class": "item"})
        
        for item in items:
            a_tag = item.find("a")
            title_tag = item.find("h3", {"class": "title"})
            img_tag = item.find("img")
            
            if a_tag and title_tag:
                item_url = site_base_url + a_tag.get("href")
                item_name = title_tag.get_text().strip()
                item_img = ""
                if img_tag:
                    item_img = img_tag.get("data-src") or img_tag.get("src") or ""
                
                # Sadece geçerli linkleri ekle
                if "/bolumler/" in item_url or "/klipler/" in item_url or "/fragmanlar/" in item_url:
                     # Sadece video sayfalarını almaya çalışalım
                     pass # Bölüm listesi olduğu için hepsini alıyoruz
                
                item_list.append({"name": item_name, "img": item_img, "url": item_url})
    except:
        pass
    return item_list

def get_bolumler_page(url):
    all_items = []
    # Genellikle bölümler /bolumler altındadır
    bolumler_urls = [url + "/bolumler", url] # Hem ana sayfayı hem bölümler sayfasını dene
    
    visited_urls = set()

    for b_url in bolumler_urls:
        if b_url in visited_urls: continue
        visited_urls.add(b_url)

        try:
            r = requests.get(b_url, headers=HEADERS, allow_redirects=True, timeout=10)
            if r.status_code != 200: continue
            
            soup = BeautifulSoup(r.content, "html.parser")
            
            # Sayfalama
            pagination = soup.find("ul", {"class": "pagination"})
            if pagination:
                pages = pagination.find_all("li")
                for page in pages:
                    a_tag = page.find("a")
                    if a_tag:
                        href = a_tag.get("href")
                        if href:
                            full_link = site_base_url + href if href.startswith("/") else r.url.split("?")[0] + href
                            if full_link not in visited_urls:
                                visited_urls.add(full_link)
                                all_items += parse_bolumler_page(full_link)
            
            # Mevcut sayfayı da oku
            all_items += parse_bolumler_page(b_url)

        except:
            pass
            
    # Tekrarları temizle
    unique_items = {v['url']: v for v in all_items}.values()
    return list(unique_items)

def get_main_page_list(url):
    all_series = []
    print(f"Ana Kategori Taranıyor: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Sayfadaki tüm potansiyel dizi/program kartlarını bul
        # Kanal D yapısında genellikle 'item' classı kullanılır
        items = soup.find_all("div", {"class": "item"})
        
        print(f"Bulunan potansiyel içerik sayısı: {len(items)}")

        for item in items:
            a_tag = item.find("a")
            title_tag = item.find("h3", {"class": "title"})
            img_tag = item.find("img")
            
            if a_tag and title_tag:
                link = a_tag.get("href")
                # Gereksiz linkleri filtrele (video, galeri vs değil, ana dizi sayfası olmalı)
                # Genellikle /diziler/arka-sokaklar gibi olur.
                if link.startswith("/"):
                    full_url = site_base_url + link
                    name = title_tag.get_text().strip()
                    img = img_tag.get("data-src") or img_tag.get("src") or "" if img_tag else ""
                    
                    all_series.append({"name": name, "img": img, "url": full_url})

    except Exception as e:
        print(f"Hata: {e}")
    
    # URL tekrarını önle
    unique_series = {v['url']: v for v in all_series}.values()
    return list(unique_series)

def main(url, name):
    data = []
    series_list = get_main_page_list(url)
    
    if not series_list:
        print(f"UYARI: {name} kategorisinde hiç içerik bulunamadı!")
        return

    print(f"{name} için {len(series_list)} adet içerik bulundu. Bölümler taranıyor...")
    
    for serie in tqdm(series_list, desc=name):
        episodes = get_bolumler_page(serie["url"])
        if episodes:
            temp_serie = serie.copy()
            temp_serie["episodes"] = []
            
            # İlk 10 bölümü kontrol et (Çok uzun sürmemesi için sınırlandırılabilir, tümü için kaldır)
            for episode in episodes: 
                media_url = parse_bolum_page(episode["url"])
                if media_url:
                    stream_url = get_stream_url(media_url)
                    if stream_url and stream_url != " ":
                        episode["stream_url"] = stream_url
                        temp_serie["episodes"].append(episode)
            
            if temp_serie["episodes"]:
                data.append(temp_serie)

    if data:
        create_single_m3u(OUTPUT_FOLDER, data, name)
        
        json_path = os.path.join(OUTPUT_FOLDER, f"{name}.json")
        with open(json_path, "w+", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        sub_folder = os.path.join(OUTPUT_FOLDER, name)
        create_m3us(sub_folder, data)
        print(f"Tamamlandı: {name}")

if __name__ == "__main__":
    # YENİ LİNKLER
    print("--- DİZİLER ---")
    main("https://www.kanald.com.tr/diziler", "diziler")
    
    print("\n--- PROGRAMLAR ---")
    main("https://www.kanald.com.tr/programlar", "programlar")
