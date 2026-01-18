import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
import json
import os
import re

# jsontom3u kontrolü
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
    "Referer": "https://www.kanald.com.tr/"
}

def clean_title(text):
    """Metin içindeki gereksiz buton yazılarını ve boşlukları temizler."""
    if not text: return "Bilinmeyen Başlık"
    
    # Gereksiz ifadeleri sil
    text = text.replace("Daha Sonra İzle", "")
    text = text.replace("Şimdi İzle", "")
    text = text.replace("Listeme Ekle", "")
    
    # Satır sonlarını ve çoklu boşlukları temizle
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(' +', ' ', text) # Çift boşlukları teke indir
    
    return text.strip()

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
    # Hem ana sayfa hem bölümler sayfasını kontrol et
    urls_to_check = [url, url + "/bolumler"]
    seen_urls = set()

    for check_url in urls_to_check:
        if check_url in seen_urls: continue
        seen_urls.add(check_url)
        
        try:
            r = requests.get(check_url, headers=HEADERS, timeout=10)
            if r.status_code != 200: continue
            
            soup = BeautifulSoup(r.content, "html.parser")
            items = soup.find_all("div", {"class": "item"})
            
            for item in items:
                a_tag = item.find("a")
                # Başlığı bul (Hata veren satır burasıydı, düzeltildi)
                title_tag = item.find("h3") or item.find("div", {"class": "title"}) or item.find("span", {"class": "title"})
                img_tag = item.find("img")

                if a_tag:
                    href = a_tag.get("href")
                    if href and ("/bolumler/" in href or "/klipler/" in href):
                        full_link = site_base_url + href if href.startswith("/") else href
                        
                        raw_name = ""
                        if title_tag:
                            raw_name = title_tag.get_text()
                        elif a_tag.get("title"):
                            raw_name = a_tag.get("title")
                        
                        # İSMİ TEMİZLE
                        final_name = clean_title(raw_name)
                        
                        # Eğer isim boşsa linkten üret
                        if not final_name or len(final_name) < 3:
                            final_name = href.split("/")[-1].replace("-", " ").title()

                        img = ""
                        if img_tag:
                            img = img_tag.get("data-src") or img_tag.get("src")
                        
                        all_items.append({"name": final_name, "img": img or "", "url": full_link})
        except:
            pass
            
    unique_items = {v['url']: v for v in all_items}.values()
    return list(unique_items)

def get_archive_list(start_url):
    all_series = []
    print(f"--- ARŞİV BAŞLIYOR: {start_url} ---")
    
    try:
        r = requests.get(start_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")
        
        # Sayfalama Mantığı
        page_links = [start_url]
        pagination = soup.find("ul", {"class": "pagination"})
        
        if pagination:
            for li in pagination.find_all("li"):
                a = li.find("a")
                if a and a.get("href"):
                    href = a.get("href")
                    if href.startswith("?"):
                        base = start_url.split("?")[0]
                        full_link = base + href
                    elif href.startswith("/"):
                        full_link = site_base_url + href
                    else:
                        full_link = href
                    
                    if full_link not in page_links:
                        page_links.append(full_link)
        
        page_links = sorted(list(set(page_links)))
        print(f"Toplam {len(page_links)} sayfa arşiv taranacak.")
        
        # Sayfaları Gez
        for page_url in page_links:
            try:
                r_page = requests.get(page_url, headers=HEADERS, timeout=10)
                s_page = BeautifulSoup(r_page.content, "html.parser")
                
                items = s_page.find_all("div", {"class": "item"})
                
                for item in items:
                    a_tag = item.find("a")
                    t_tag = item.find("h3") or item.find("div", {"class": "title"})
                    i_tag = item.find("img")
                    
                    if a_tag:
                        link = a_tag.get("href")
                        # Sadece ana dizi linklerini al
                        if link and (link.startswith("/diziler/") or link.startswith("/programlar/")):
                            # Bölüm linklerini hariç tut (sadece ana sayfa)
                            clean_link = link.split("?")[0]
                            parts = clean_link.strip("/").split("/")
                            
                            # /diziler/arka-sokaklar (Doğru) vs /diziler/arka-sokaklar/bolumler (Yanlış)
                            if len(parts) == 2:
                                full_url = site_base_url + link
                                
                                raw_name = ""
                                if t_tag:
                                    raw_name = t_tag.get_text()
                                else:
                                    raw_name = a_tag.get("title") or parts[-1].replace("-", " ").title()
                                
                                name = clean_title(raw_name)
                                img = i_tag.get("data-src") or i_tag.get("src") if i_tag else ""
                                
                                all_series.append({"name": name, "img": img, "url": full_url})
            except:
                continue
                
    except Exception as e:
        print(f"Arşiv tarama hatası: {e}")
        return []

    unique_series = {v['url']: v for v in all_series}.values()
    return list(unique_series)

def main(url, name):
    data = []
    series_list = get_archive_list(url)
    
    print(f"--> {name} için {len(series_list)} içerik bulundu. Bölümler taranıyor...")
    
    # Her bir diziyi tara
    for serie in tqdm(series_list, desc=name):
        episodes = get_bolumler_page(serie["url"])
        
        if episodes:
            temp_serie = serie.copy()
            temp_serie["episodes"] = []
            
            for episode in episodes:
                media_url = parse_bolum_page(episode["url"])
                if media_url:
                    stream_url = get_stream_url(media_url)
                    if stream_url:
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
        print(f"=== {name} TAMAMLANDI ({len(data)} adet) ===")
    else:
        print(f"=== {name} İÇİN VERİ ÇIKMADI ===")

if __name__ == "__main__":
    print("--- DİZİ ARŞİVİ ---")
    main("https://www.kanald.com.tr/diziler/arsiv", "arsiv-diziler")
    
    print("\n--- PROGRAM ARŞİVİ ---")
    main("https://www.kanald.com.tr/programlar/arsiv", "arsiv-programlar")
