import requests
from bs4 import BeautifulSoup
import json
import os
import sys
from tqdm import tqdm

# jsontom3u kütüphanesi ana dizinde olduğu varsayılmıştır
try:
    from jsontom3u import create_single_m3u, create_m3us
except ImportError:
    print("HATA: 'jsontom3u.py' dosyası bulunamadı. Lütfen ana dizine ekleyin.")
    sys.exit(1)

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

def get_soup(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
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
            
            # M3U8 linkini al
            if "media" in video_data and "m3u8" in video_data["media"]:
                # Genellikle ilk kaynak standart olandır
                return video_data["media"]["m3u8"][0]["src"]
    except Exception as e:
        print(f"Video kaynağı çözülemedi: {url} - Hata: {e}")
    
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
                # Dizi/Program bölümleri ItemList tipindedir
                if data.get("@type") == "ItemList" and "itemListElement" in data:
                    items = data["itemListElement"]
                    # Bölümleri tersten sırala (Eskiden yeniye veya tam tersi mantığı)
                    # Genelde JSON-LD sıralı gelir, biz listeye ekleriz.
                    for item in items:
                        episode_url = BASE_URL + item["url"] if not item["url"].startswith("http") else item["url"]
                        episode_list.append({
                            "url": episode_url,
                            # İsim verisi JSON-LD'de bazen eksik olabilir, URL'den türetilebilir veya detaydan alınabilir
                            # Şimdilik URL'den basit bir isim çıkarımı yapalım veya boş bırakalım detayda dolsun
                            "name_temp": "Bölüm" 
                        })
            except:
                continue
    except Exception as e:
        print(f"JSON-LD Parsing Hatası: {e}")
    
    return episode_list

def process_category(category_name, category_url, output_folder):
    print(f"\n--- {category_name.upper()} TARANIYOR ---")
    soup = get_soup(category_url)
    if not soup: return []

    items_data = []
    
    # Listeleme sayfasındaki kutuları bul (box-type6)
    content_boxes = soup.find_all("div", attrs={"data-name": "box-type6"})
    
    for box in tqdm(content_boxes, desc=f"{category_name} Listesi"):
        try:
            link_tag = box.find("a")
            img_tag = box.find("img")
            title_tag = box.find("figcaption").find("span") # Başlık genelde figcaption içindeki ilk span

            if not link_tag: continue

            item_name = title_tag.get_text(strip=True) if title_tag else "Bilinmiyor"
            item_url = BASE_URL + link_tag.get("href")
            item_img = img_tag.get("data-src") or img_tag.get("src")
            
            # Logo/Placeholder kontrolü
            if "transparent.gif" in item_img and img_tag.get("data-src"):
                item_img = img_tag.get("data-src")

            # Ana Veri Objesi
            main_item = {
                "name": item_name,
                "img": item_img,
                "url": item_url,
                "episodes": []
            }

            # Detay Sayfasına Git (Bölümleri Al)
            detail_soup = get_soup(item_url)
            if detail_soup:
                # Bölüm listesini JSON-LD'den çek
                raw_episodes = get_episodes_from_json_ld(detail_soup)
                
                # Eğer JSON-LD boşsa manuel (HTML parsing) denenebilir ama 
                # ShowTV yapısında JSON-LD oldukça tutarlı.
                
                # Her bir bölümün içine girip videoyu bul
                # (API yükünü azaltmak için sadece ilk 1-2 bölümü test edebilirsin istersen)
                # Aşağıdaki kod TÜM bölümleri tarar.
                
                print(f"  > {item_name}: {len(raw_episodes)} içerik bulundu. Video linkleri taranıyor...")
                
                for ep in tqdm(raw_episodes, desc="    Videolar", leave=False):
                    stream_url = get_video_source(ep["url"])
                    if stream_url:
                        # Bölüm adını ve resmini video sayfasından daha net alabiliriz
                        ep_name = ep["name_temp"]
                        ep_img = item_img # Varsayılan olarak dizi kapağı
                        
                        # Bölüm sayfasından daha iyi veri çekme denemesi (opsiyonel)
                        # ep_soup = get_soup(ep["url"]) ... (Hız düşüreceği için atlandı, stream varsa yeterli)
                        
                        main_item["episodes"].append({
                            "name": f"{item_name} - {ep['url'].split('/')[-2].replace('-', ' ').title()}", # URL'den okunabilir isim
                            "img": item_img,
                            "stream_url": stream_url
                        })
            
            if main_item["episodes"]:
                # 1. Bu dizi/program için özel JSON oluştur
                safe_name = item_url.split("/")[-2] # URL slug'ını dosya adı yap
                json_path = os.path.join(output_folder, f"{safe_name}.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(main_item, f, ensure_ascii=False, indent=4)
                
                # 2. Bu dizi/program için özel M3U oluştur
                # jsontom3u kütüphanesindeki create_single_m3u kullanımı:
                # create_single_m3u(path_without_extension, [data_list], prefix_name)
                create_single_m3u(os.path.join(output_folder, safe_name), [main_item])
                
                items_data.append(main_item)

        except Exception as e:
            print(f"Hata oluştu ({item_name}): {e}")
            continue

    return items_data

def main():
    # 1. Dizileri Tara
    dizi_data = process_category("Diziler", f"{BASE_URL}/diziler", DIRS["dizi"])
    
    # 2. Programları Tara
    program_data = process_category("Programlar", f"{BASE_URL}/programlar", DIRS["program"])

    # 3. Genel Listeleri Oluştur (Show TV Klasörü içine)
    
    # Tüm Diziler Tek Dosyada
    if dizi_data:
        print("\nGenel Dizi Listesi Oluşturuluyor...")
        with open(f"{DIRS['root']}/showtv_diziler.json", "w", encoding="utf-8") as f:
            json.dump(dizi_data, f, ensure_ascii=False, indent=4)
        create_single_m3u(f"{DIRS['root']}/showtv_diziler", dizi_data)

    # Tüm Programlar Tek Dosyada
    if program_data:
        print("Genel Program Listesi Oluşturuluyor...")
        with open(f"{DIRS['root']}/showtv_programlar.json", "w", encoding="utf-8") as f:
            json.dump(program_data, f, ensure_ascii=False, indent=4)
        create_single_m3u(f"{DIRS['root']}/showtv_programlar", program_data)

    print("\nİşlem Tamamlandı.")

if __name__ == "__main__":
    main()
