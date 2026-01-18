import requests
from bs4 import BeautifulSoup
import json
import os
import re
from tqdm import tqdm
import time

# --- AYARLAR ---
BASE_URL = "https://www.nowtv.com.tr"
# NowTV istekleri için gerekli Header bilgileri
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

# Klasör Yapılandırması
ROOT_DIR = "now"
DIRS = {
    "series": os.path.join(ROOT_DIR, "dizi"),
    "programs": os.path.join(ROOT_DIR, "program")
}

# Kategori Konfigürasyonu
CATEGORIES = [
    {"type": "series", "api_url": f"{BASE_URL}/ajax/series", "name": "Guncel Diziler"},
    {"type": "programs", "api_url": f"{BASE_URL}/ajax/programs", "name": "Guncel Programlar"},
    {"type": "series", "api_url": f"{BASE_URL}/ajax/archive", "name": "Arsiv Diziler"},
    {"type": "programs", "api_url": f"{BASE_URL}/ajax/archive", "name": "Arsiv Programlar"}
]

def create_m3u(file_path, data):
    """Verilen JSON verisinden M3U dosyası oluşturur."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for item in data:
                # Eğer item bir dizi/program ise ve içinde bölümler varsa
                if "episodes" in item:
                    for ep in item["episodes"]:
                        name = ep.get("name", "Bilinmeyen")
                        img = ep.get("img", "")
                        url = ep.get("stream_url", "")
                        # Eğer stream url boşsa veya hatalıysa, sayfa linkini koy (fallback)
                        if not url:
                            url = ep.get("url", "")
                            if url and not url.startswith("http"):
                                url = BASE_URL + url
                        
                        if url:
                            f.write(f'#EXTINF:-1 tvg-logo="{img}" group-title="{item["name"]}",{name}\n')
                            f.write(f'{url}\n')
    except Exception as e:
        print(f"M3U oluşturma hatası ({file_path}): {e}")

def get_real_m3u8_from_page(episode_url):
    """
    Bölüm sayfasına gidip kaynak kodundaki source: '...' kısmından
    ercdn.net uzantılı gerçek m3u8 linkini çeker.
    """
    if not episode_url:
        return ""
        
    full_url = episode_url if episode_url.startswith("http") else BASE_URL + episode_url
    
    try:
        # Sayfaya normal bir tarayıcı gibi istek atıyoruz (X-Requested-With olmadan)
        page_headers = HEADERS.copy()
        if "X-Requested-With" in page_headers:
            del page_headers["X-Requested-With"]
            
        r = requests.get(full_url, headers=page_headers, timeout=10)
        
        # HTML içinden source: 'https://....m3u8...' yapısını arıyoruz
        # NowTV player yapısı genellikle: source: 'LINK', şeklindedir.
        match = re.search(r"source:\s*['\"](https:\/\/[^'\"]*?\.m3u8[^'\"]*?)['\"]", r.text)
        
        if match:
            return match.group(1)
        else:
            return ""
    except Exception:
        return ""

def get_episodes(program_id, serie_name):
    """
    API üzerinden bölümleri çeker.
    """
    video_url = f"{BASE_URL}/ajax/videos"
    body = {
        'filter': 'season',
        'season': 1,
        'program_id': program_id,
        'page': 0,
        'type': 2, # Full Bölüm Tipi
        'count': 100,
        'orderBy': "id",
        "sorting": "asc"
    }
    
    episode_list = []
    flag = True
    
    while flag:
        try:
            r = requests.post(video_url, body, headers=HEADERS)
            data = r.json()
            html = data.get('data', '')
            total_count = int(data.get('count', 0))
            
            if not html:
                if body['season'] < 15: # Maksimum sezon kontrolü
                    body['season'] += 1
                    body['page'] = 0
                    continue
                else:
                    break

            soup = BeautifulSoup(html, "html.parser")
            items = soup.find_all("div", {"class": "list-item"})
            
            if not items:
                flag = False
                break

            for item in items:
                try:
                    title_tag = item.find("strong")
                    ep_title = title_tag.get_text().strip() if title_tag else "Bölüm"
                    full_name = f"{serie_name} - {ep_title}"
                    
                    img_tag = item.find("img")
                    img = img_tag.get("src") if img_tag else ""
                    
                    a_tag = item.find("a")
                    page_url = a_tag.get("href") if a_tag else ""
                    
                    # Gerçek M3U8 linkini çekmeye çalış
                    stream_url = get_real_m3u8_from_page(page_url)
                    
                    # Eğer çekemezse sayfa linkini kullan
                    if not stream_url:
                        stream_url = BASE_URL + page_url if not page_url.startswith("http") else page_url

                    episode_list.append({
                        "name": full_name,
                        "img": img,
                        "url": page_url,
                        "stream_url": stream_url
                    })
                except:
                    continue
            
            # Sayfalama kontrolü
            if len(items) < body['count'] and body['season'] < 15:
                 body['season'] += 1
                 body['page'] = 0
            elif len(items) == body['count']:
                body['page'] += 1
            else:
                flag = False
                
        except Exception as e:
            print(f"Bölüm çekme hatası: {e}")
            flag = False

    return episode_list

def get_program_list(config):
    """Dizi veya Program listesini ana sayfadan çeker"""
    body = {
        'page': 0,
        'type': config['type'],
        'count': '50',
        'orderBy': 'id',
        "sorting": 'desc'
    }
    
    results = []
    flag = True
    
    while flag:
        try:
            r = requests.post(config['api_url'], body, headers=HEADERS)
            res_json = r.json()
            html = res_json.get("data", "")
            
            if not html:
                break
                
            soup = BeautifulSoup(html, "html.parser")
            items = soup.find_all("div", {"class": "list-item"})
            
            if items:
                body['page'] += 1
                for item in items:
                    try:
                        name = item.find("strong").get_text().strip()
                        img_tag = item.find("img")
                        img = img_tag.get("src") if img_tag else ""
                        
                        # ID parse etme
                        content_id = "0"
                        if img:
                            content_id = img.split("/")[-1].split(".")[0]
                        
                        results.append({
                            "id": content_id,
                            "name": name,
                            "img": img
                        })
                    except:
                        pass
            else:
                flag = False
        except:
            flag = False
    return results

def main():
    # 1. Klasörleri Oluştur
    os.makedirs(DIRS["series"], exist_ok=True)
    os.makedirs(DIRS["programs"], exist_ok=True)

    all_series_data = []
    all_programs_data = []

    for cat in CATEGORIES:
        print(f"--- {cat['name']} taranıyor ---")
        items = get_program_list(cat)
        
        # Her bir dizi/program için
        for item in tqdm(items):
            episodes = get_episodes(item['id'], item['name'])
            
            if episodes:
                item_data = item.copy()
                item_data["episodes"] = episodes
                
                # Dosya ismi için slug oluştur
                slug = item['name'].lower().replace(" ", "-").replace("ı","i").replace("ğ","g").replace("ü","u").replace("ş","s").replace("ö","o").replace("ç","c")
                slug = re.sub(r'[^a-z0-9-]', '', slug)
                
                # Kayıt Yeri
                is_serie = cat['type'] == 'series'
                target_dir = DIRS["series"] if is_serie else DIRS["programs"]
                
                # JSON ve M3U Kaydet (Tekil)
                with open(os.path.join(target_dir, f"{slug}.json"), "w", encoding="utf-8") as f:
                    json.dump(item_data, f, ensure_ascii=False, indent=4)
                
                create_m3u(os.path.join(target_dir, f"{slug}.m3u"), [item_data])
                
                # Ana listeye ekle
                if is_serie:
                    all_series_data.append(item_data)
                else:
                    all_programs_data.append(item_data)

    # 2. Ana Dosyaları Oluştur (now klasörü içine)
    print("Ana dosyalar oluşturuluyor...")
    
    # Diziler Toplu
    with open(os.path.join(ROOT_DIR, "now-diziler.json"), "w", encoding="utf-8") as f:
        json.dump(all_series_data, f, ensure_ascii=False, indent=4)
    create_m3u(os.path.join(ROOT_DIR, "now-diziler.m3u"), all_series_data)
    
    # Programlar Toplu
    with open(os.path.join(ROOT_DIR, "now-programlar.json"), "w", encoding="utf-8") as f:
        json.dump(all_programs_data, f, ensure_ascii=False, indent=4)
    create_m3u(os.path.join(ROOT_DIR, "now-programlar.m3u"), all_programs_data)

    print("İşlem Başarılı.")

if __name__ == "__main__":
    main()
