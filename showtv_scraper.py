import requests
from bs4 import BeautifulSoup
import json
import os
import time
from tqdm import tqdm

# --- AYARLAR ---
BASE_URL = "https://www.showtv.com.tr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Klasör Yapısını Oluştur (showtv/dizi ve showtv/program)
DIRS = {
    "root": "showtv",
    "dizi": "showtv/dizi",
    "program": "showtv/program"
}

for d in DIRS.values():
    os.makedirs(d, exist_ok=True)

# --- M3U OLUŞTURMA FONKSİYONLARI (İçine Gömüldü) ---
def create_single_m3u(file_path, data_list):
    """Tekil içerik için M3U oluşturur (Örn: Sadece Rüya Gibi dizisi)"""
    if not file_path.endswith(".m3u"): file_path += ".m3u"
    
    content = "#EXTM3U\n"
    # data_list aslında tek bir obje içeren liste olabilir, kontrol edelim
    items = data_list if isinstance(data_list, list) else [data_list]
    
    for item in items:
        for episode in item.get("episodes", []):
            name = episode.get("name", "Bilinmeyen Bölüm")
            img = episode.get("img", "")
            url = episode.get("stream_url", "")
            if url:
                content += f'#EXTINF:-1 tvg-logo="{img}" group-title="{item["name"]}", {name}\n{url}\n'
        
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

def create_general_m3u(file_path, data_list, group_name="Genel"):
    """Genel liste için M3U oluşturur (Tüm diziler/programlar tek dosyada)"""
    if not file_path.endswith(".m3u"): file_path += ".m3u"

    content = "#EXTM3U\n"
    for item in data_list:
        clean_group_name = item.get("name", group_name)
        for episode in item.get("episodes", []):
            name = episode.get("name", "Bilinmeyen Bölüm")
            img = episode.get("img", "")
            url = episode.get("stream_url", "")
            if url:
                content += f'#EXTINF:-1 tvg-logo="{img}" group-title="{clean_group_name}", {name}\n{url}\n'

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
        player_div = soup.find("div", attrs={"data-hope-video": True})
        if player_div:
            video_data = json.loads(player_div.get("data-hope-video"))
            if "media" in video_data and "m3u8" in video_data["media"]:
                return video_data["media"]["m3u8"][0]["src"]
    except:
        pass
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
                    for item in data["itemListElement"]:
                        url = item["url"]
                        if not url.startswith("http"): url = BASE_URL + url
                        episode_list.append({"url": url})
            except: continue
    except: pass
    return episode_list

def process_category(category_name, category_url, output_folder):
    print(f"\n--- {category_name.upper()} TARANIYOR ---")
    soup = get_soup(category_url)
    if not soup: return []

    items_data = []
    
    # Kapsayıcıları bul: box-type ile başlayan her şeyi al (box-type6, box-type2 vs.)
    # ShowTV bazen diziler için farklı, programlar için farklı kutu tipi kullanıyor.
    content_boxes = soup.find_all("div", attrs={"data-name": lambda x: x and x.startswith("box-type")})
    
    print(f"Toplam {len(content_boxes)} içerik bulundu.")

    for box in tqdm(content_boxes, desc=f"{category_name} İşleniyor"):
        try:
            link_tag = box.find("a")
            img_tag = box.find("img")
            
            # Başlık bazen img alt'ında, bazen figcaption içinde olur
            title_text = "Bilinmiyor"
            caption = box.find("figcaption")
            if caption:
                span = caption.find("span")
                if span: title_text = span.get_text(strip=True)
            elif img_tag and img_tag.get("alt"):
                title_text = img_tag.get("alt")

            if not link_tag: continue

            item_url = BASE_URL + link_tag.get("href")
            item_img = ""
            if img_tag:
                item_img = img_tag.get("data-src") or img_tag.get("src") or ""
            
            # Placeholder resim kontrolü
            if "transparent" in item_img and img_tag.get("data-src"):
                item_img = img_tag.get("data-src")

            main_item = {
                "name": title_text,
                "img": item_img,
                "url": item_url,
                "episodes": []
            }

            # Detay Sayfasına Git
            detail_soup = get_soup(item_url)
            if detail_soup:
                # Bölümleri çek (En son 50 bölümle sınırladık ki işlem bitmeden kapanmasın)
                raw_episodes = get_episodes_from_json_ld(detail_soup)[:50]
                
                for ep in raw_episodes:
                    stream_url = get_video_source(ep["url"])
                    if stream_url:
                        # Bölüm ismini URL'den insanin okuyacağı hale getir
                        slug = ep['url'].split('/')[-2].replace('-', ' ').title()
                        ep_name = f"{title_text} - {slug}"
                        
                        main_item["episodes"].append({
                            "name": ep_name,
                            "img": item_img,
                            "stream_url": stream_url
                        })
            
            if main_item["episodes"]:
                # Dosya ismi (URL sonundaki ID veya isim)
                safe_filename = item_url.split("/")[-2]
                if safe_filename.isdigit(): safe_filename = item_url.split("/")[-3]
                
                # 1. Bireysel JSON Kaydet
                json_path = os.path.join(output_folder, f"{safe_filename}.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(main_item, f, ensure_ascii=False, indent=4)
                
                # 2. Bireysel M3U Kaydet
                m3u_path = os.path.join(output_folder, safe_filename)
                create_single_m3u(m3u_path, [main_item])
                
                items_data.append(main_item)

        except Exception as e:
            continue

    return items_data

def main():
    # 1. DİZİLER
    dizi_data = process_category("Diziler", f"{BASE_URL}/diziler", DIRS["dizi"])
    
    # 2. PROGRAMLAR
    program_data = process_category("Programlar", f"{BASE_URL}/programlar", DIRS["program"])

    # 3. ANA DOSYALARI OLUŞTUR (Show TV Klasörü içine)
    
    # Diziler Ana JSON ve M3U
    if dizi_data:
        print("Ana Dizi Dosyaları Oluşturuluyor...")
        with open(f"{DIRS['root']}/showtv_diziler.json", "w", encoding="utf-8") as f:
            json.dump(dizi_data, f, ensure_ascii=False, indent=4)
        create_general_m3u(f"{DIRS['root']}/showtv_diziler", dizi_data, "Show TV Dizileri")

    # Programlar Ana JSON ve M3U
    if program_data:
        print("Ana Program Dosyaları Oluşturuluyor...")
        with open(f"{DIRS['root']}/showtv_programlar.json", "w", encoding="utf-8") as f:
            json.dump(program_data, f, ensure_ascii=False, indent=4)
        create_general_m3u(f"{DIRS['root']}/showtv_programlar", program_data, "Show TV Programları")

    print("\nİşlem Tamamlandı.")

if __name__ == "__main__":
    main()
