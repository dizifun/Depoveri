import requests
from bs4 import BeautifulSoup
import json
import os
import sys
from tqdm import tqdm
import time

# --- AYARLAR ---
BASE_URL = "https://www.showtv.com.tr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Klasör Yapısını Oluştur
DIRS = {
    "root": "showtv",
    "dizi": "showtv/dizi",
    "program": "showtv/program"
}

for d in DIRS.values():
    os.makedirs(d, exist_ok=True)

# --- M3U OLUŞTURMA FONKSİYONLARI (İçeri Gömüldü) ---
def create_single_m3u(file_path, data_list):
    """Tekil içerik için M3U oluşturur (Örn: Sadece Rüya Gibi dizisi)"""
    content = "#EXTM3U\n"
    for item in data_list:
        for episode in item.get("episodes", []):
            name = episode.get("name", "Bilinmeyen Bölüm")
            img = episode.get("img", "")
            url = episode.get("stream_url", "")
            
            if url:
                content += f'#EXTINF:-1 tvg-logo="{img}" group-title="{item["name"]}", {name}\n'
                content += f'{url}\n'
    
    # Dosya uzantısı kontrolü
    if not file_path.endswith(".m3u"):
        file_path += ".m3u"
        
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

def create_general_m3u(file_path, data_list, group_name="Genel"):
    """Genel liste için M3U oluşturur (Tüm diziler tek dosyada)"""
    content = "#EXTM3U\n"
    for item in data_list:
        serie_name = item.get("name", "Genel")
        for episode in item.get("episodes", []):
            name = episode.get("name", "Bilinmeyen Bölüm")
            img = episode.get("img", "")
            url = episode.get("stream_url", "")
            
            if url:
                content += f'#EXTINF:-1 tvg-logo="{img}" group-title="{group_name}", {name}\n'
                content += f'{url}\n'

    if not file_path.endswith(".m3u"):
        file_path += ".m3u"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

# --- SCRAPER FONKSİYONLARI ---
def get_soup(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return BeautifulSoup(r.content, "html.parser")
    except Exception as e:
        print(f"Hata ({url}): {e}")
        return None

def get_video_source(url):
    """Video oynatma sayfasındaki data-hope-video json verisinden m3u8 çeker."""
    soup = get_soup(url)
    if not soup: return None
    
    try:
        # Player div'ini bul
        player_div = soup.find("div", attrs={"data-hope-video": True})
        if player_div:
            video_data_raw = player_div.get("data-hope-video")
            video_data = json.loads(video_data_raw)
            
            if "media" in video_data and "m3u8" in video_data["media"]:
                return video_data["media"]["m3u8"][0]["src"]
    except Exception as e:
        print(f"Video kaynağı çözülemedi: {url}")
    
    return None

def get_episodes_from_json_ld(soup):
    """Sayfa kaynağındaki JSON-LD verisinden bölüm listesini çeker."""
    episode_list = []
    try:
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            if not script.string: continue
            try:
                data = json.loads(script.string)
                if data.get("@type") == "ItemList" and "itemListElement" in data:
                    items = data["itemListElement"]
                    for item in items:
                        episode_url = BASE_URL + item["url"] if not item["url"].startswith("http") else item["url"]
                        episode_list.append({
                            "url": episode_url,
                            "temp_name": "Bölüm"
                        })
            except:
                continue
    except:
        pass
    
    return episode_list

def process_category(category_name, category_url, output_folder):
    print(f"\n--- {category_name.upper()} TARANIYOR ---")
    soup = get_soup(category_url)
    if not soup: return []

    items_data = []
    
    # Kapsayıcıları bul (box-type6 ShowTV'nin yeni yapısı)
    content_boxes = soup.find_all("div", attrs={"data-name": "box-type6"})
    
    # Hızlı test için [:3] koyabilirsin, tümü için kaldır. Şimdilik tümünü tarıyoruz.
    for box in tqdm(content_boxes, desc=f"{category_name}"):
        try:
            link_tag = box.find("a")
            img_tag = box.find("img")
            title_tag = box.find("figcaption").find("span")

            if not link_tag: continue

            item_name = title_tag.get_text(strip=True) if title_tag else "Bilinmiyor"
            item_url = BASE_URL + link_tag.get("href")
            
            # Resim alma (Lazy load kontrolü)
            item_img = ""
            if img_tag:
                item_img = img_tag.get("data-src") or img_tag.get("src") or ""

            # Ana Veri Objesi
            main_item = {
                "name": item_name,
                "img": item_img,
                "url": item_url,
                "episodes": []
            }

            # Detay Sayfası
            detail_soup = get_soup(item_url)
            if detail_soup:
                raw_episodes = get_episodes_from_json_ld(detail_soup)
                
                # Bölüm sayısını sınırlayalım (GitHub Actions timeout yememesi için)
                # Eğer çok eski diziler varsa her gün hepsini taramak 6 saati bulabilir.
                # Şimdilik son 20 bölümü al diyelim. İstersen bu [:20] kısmını kaldır.
                for ep in raw_episodes[:20]: 
                    stream_url = get_video_source(ep["url"])
                    if stream_url:
                        # Bölüm ismini URL'den çıkaralım
                        slug = ep['url'].split('/')[-2].replace('-', ' ').title()
                        ep_full_name = f"{item_name} - {slug}"
                        
                        main_item["episodes"].append({
                            "name": ep_full_name,
                            "img": item_img,
                            "stream_url": stream_url
                        })
            
            if main_item["episodes"]:
                # Dosya ismi oluştur
                safe_filename = item_url.split("/")[-1]
                if not safe_filename or safe_filename.isdigit(): 
                    safe_filename = item_url.split("/")[-2]
                
                # 1. JSON Kaydet
                json_path = os.path.join(output_folder, f"{safe_filename}.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(main_item, f, ensure_ascii=False, indent=4)
                
                # 2. M3U Kaydet (Diziye özel)
                m3u_path = os.path.join(output_folder, safe_filename)
                create_single_m3u(m3u_path, [main_item])
                
                items_data.append(main_item)

        except Exception as e:
            print(f"Atlandı: {e}")
            continue

    return items_data

def main():
    # 1. Dizileri Tara
    dizi_data = process_category("Diziler", f"{BASE_URL}/diziler", DIRS["dizi"])
    
    # 2. Programları Tara
    program_data = process_category("Programlar", f"{BASE_URL}/programlar", DIRS["program"])

    # 3. Genel Listeleri Oluştur (Ana Klasöre)
    if dizi_data:
        create_general_m3u(f"{DIRS['root']}/showtv_diziler_genel", dizi_data, "Diziler")
        
    if program_data:
        create_general_m3u(f"{DIRS['root']}/showtv_programlar_genel", program_data, "Programlar")

    print("\nİşlem Tamamlandı.")

if __name__ == "__main__":
    main()
