import requests
from bs4 import BeautifulSoup
import json
import os
import sys
from tqdm import tqdm

# --- AYARLAR ---
BASE_URL = "https://www.showtv.com.tr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Klasör Ayarları
DIRS = {
    "root": "showtv",
    "dizi": "showtv/dizi",
    "program": "showtv/program"
}

# Klasörleri oluştur
for d in DIRS.values():
    os.makedirs(d, exist_ok=True)

# --- YARDIMCI FONKSİYONLAR ---

def save_json(file_path, data):
    """JSON kaydetme fonksiyonu"""
    if not file_path.endswith(".json"): file_path += ".json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def create_m3u(file_path, data_list, is_single=False):
    """M3U oluşturma fonksiyonu (Hem tekil hem genel için)"""
    if not file_path.endswith(".m3u"): file_path += ".m3u"
    
    content = "#EXTM3U\n"
    
    # Veri listesini normalize et
    items = data_list if isinstance(data_list, list) else [data_list]
    
    for item in items:
        group_title = item.get("name", "Show TV")
        for episode in item.get("episodes", []):
            name = episode.get("name", "Bilinmeyen Bölüm")
            img = episode.get("img", "")
            url = episode.get("stream_url", "")
            
            if url:
                # M3U Formatı
                content += f'#EXTINF:-1 tvg-logo="{img}" group-title="{group_title}", {name}\n'
                content += f'{url}\n'
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

def get_soup(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return BeautifulSoup(r.content, "html.parser")
    except Exception as e:
        print(f"Hata ({url}): {e}")
        return None

def get_video_source(url):
    """Player içindeki data-hope-video json verisinden m3u8 çeker."""
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
    """JSON-LD verisinden bölümleri çeker."""
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
    print(f"\n>>> {category_name.upper()} İŞLENİYOR...")
    soup = get_soup(category_url)
    if not soup: return []

    items_data = []
    
    # ShowTV'de kutu tipleri değişebiliyor (box-type6, box-type3 vs.)
    # "box-type" ile başlayan tüm divleri alıyoruz.
    content_boxes = soup.find_all("div", attrs={"data-name": lambda x: x and x.startswith("box-type")})
    
    print(f"   Bulunan içerik sayısı: {len(content_boxes)}")

    for box in tqdm(content_boxes, desc=f"{category_name}"):
        try:
            link_tag = box.find("a")
            img_tag = box.find("img")
            
            # Başlık bulma (farklı yapılara karşı önlem)
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
            
            # Placeholder (şeffaf resim) kontrolü
            if "transparent" in item_img and img_tag.get("data-src"):
                item_img = img_tag.get("data-src")

            main_item = {
                "name": title_text,
                "img": item_img,
                "url": item_url,
                "episodes": []
            }

            # Detay Sayfası Analizi
            detail_soup = get_soup(item_url)
            if detail_soup:
                # Son 30 bölümü al (GitHub süresi yetmesi için)
                raw_episodes = get_episodes_from_json_ld(detail_soup)[:30]
                
                for ep in raw_episodes:
                    stream_url = get_video_source(ep["url"])
                    if stream_url:
                        # Bölüm adını URL'den türet
                        slug = ep['url'].split('/')[-2].replace('-', ' ').title()
                        ep_name = f"{title_text} - {slug}"
                        
                        main_item["episodes"].append({
                            "name": ep_name,
                            "img": item_img,
                            "stream_url": stream_url
                        })
            
            # Eğer en az 1 bölüm/video bulunduysa kaydet
            if main_item["episodes"]:
                # Dosya ismi oluştur
                safe_filename = item_url.split("/")[-2]
                if safe_filename.isdigit(): safe_filename = item_url.split("/")[-3]
                
                # 1. Bireysel Dosyaları Kaydet (Örn: showtv/dizi/kizilcik-serbeti.m3u)
                json_path = os.path.join(output_folder, safe_filename)
                save_json(json_path, main_item)
                
                m3u_path = os.path.join(output_folder, safe_filename)
                create_m3u(m3u_path, main_item, is_single=True)
                
                items_data.append(main_item)

        except Exception as e:
            continue

    return items_data

def main():
    # 1. Dizileri Tara ve Kaydet
    dizi_data = process_category("Diziler", f"{BASE_URL}/diziler", DIRS["dizi"])
    if dizi_data:
        print(f"   [+] {len(dizi_data)} dizi başarıyla işlendi.")
        # Ana Dizi Listesi (showtv/showtv_diziler.json)
        save_json(f"{DIRS['root']}/showtv_diziler", dizi_data)
        create_m3u(f"{DIRS['root']}/showtv_diziler", dizi_data)

    # 2. Programları Tara ve Kaydet
    program_data = process_category("Programlar", f"{BASE_URL}/programlar", DIRS["program"])
    if program_data:
        print(f"   [+] {len(program_data)} program başarıyla işlendi.")
        # Ana Program Listesi (showtv/showtv_programlar.json)
        save_json(f"{DIRS['root']}/showtv_programlar", program_data)
        create_m3u(f"{DIRS['root']}/showtv_programlar", program_data)

    print("\n>>> TÜM İŞLEMLER TAMAMLANDI.")

if __name__ == "__main__":
    main()
