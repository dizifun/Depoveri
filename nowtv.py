import requests
from bs4 import BeautifulSoup
import json
import os
import re
from tqdm import tqdm
import time

# --- AYARLAR ---
BASE_URL = "https://www.nowtv.com.tr"
ROOT_DIR = "now"
DIRS = {
    "series": os.path.join(ROOT_DIR, "dizi"),
    "programs": os.path.join(ROOT_DIR, "program")
}

# Session başlat (Cookie'leri tutmak için)
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE_URL
})

def get_csrf_token():
    """
    Ana sayfaya gidip CSRF token alır. Bu token POST istekleri için zorunludur.
    """
    print("Siteye bağlanılıyor ve Token alınıyor...")
    try:
        # Normal bir browser gibi ana sayfaya git
        r = session.get(BASE_URL)
        soup = BeautifulSoup(r.text, 'html.parser')
        token = soup.find('meta', {'name': 'csrf-token'})
        if token and token.get('content'):
            csrf = token['content']
            # Session header'larına ekle
            session.headers.update({'X-CSRF-TOKEN': csrf})
            print(f"Token alındı: {csrf[:10]}...")
            return True
        else:
            print("HATA: CSRF Token bulunamadı!")
            return False
    except Exception as e:
        print(f"Bağlantı hatası: {e}")
        return False

def get_real_m3u8(episode_url):
    """
    Bölüm sayfasından gerçek m3u8 linkini regex ile çeker.
    """
    if not episode_url: return ""
    full_url = episode_url if episode_url.startswith("http") else BASE_URL + episode_url
    
    try:
        # HTML isteği at (Headerlar session'dan gelir)
        r = session.get(full_url, timeout=10)
        
        # 1. Yöntem: source: '...' içinde ara
        match = re.search(r"source:\s*['\"](https:\/\/[^'\"]*?\.m3u8[^'\"]*?)['\"]", r.text)
        if match:
            return match.group(1)
        
        # 2. Yöntem: JSON data içinde ara (ADMPlayer)
        match_json = re.search(r"ADMPlayer\.init\(\{(.*?)\}\);", r.text, re.DOTALL)
        if match_json:
            # Source parametresini bulmaya çalış
            src_match = re.search(r"source:\s*['\"](https:\/\/.*?)['\"]", match_json.group(1))
            if src_match:
                return src_match.group(1)
                
        return ""
    except:
        return ""

def get_episodes(program_id, show_name):
    """
    Program ID'sine göre bölümleri çeker.
    """
    url = f"{BASE_URL}/ajax/videos"
    episode_list = []
    
    # Döngü ayarları
    payload = {
        'filter': 'season',
        'season': 1,
        'program_id': program_id,
        'page': 0,
        'type': 2,
        'count': 50,
        'orderBy': 'id',
        'sorting': 'asc'
    }

    # Max 15 sezon dener
    while payload['season'] < 15:
        try:
            r = session.post(url, data=payload)
            data = r.json()
            html = data.get('data', '')
            total_count = int(data.get('count', 0))
            
            # Veri yoksa sezon bitti mi kontrol et
            if not html:
                # Eğer ilk sayfada ve veri yoksa, sonraki sezona geç
                if payload['page'] == 0:
                    payload['season'] += 1
                    continue
                else:
                    # Sayfa bittiyse sonraki sezona geç
                    payload['season'] += 1
                    payload['page'] = 0
                    continue

            soup = BeautifulSoup(html, 'html.parser')
            items = soup.find_all("div", {"class": "list-item"})
            
            if not items:
                payload['season'] += 1
                payload['page'] = 0
                continue

            for item in items:
                try:
                    name_tag = item.find("strong")
                    ep_name = name_tag.text.strip() if name_tag else "Bölüm"
                    full_name = f"{show_name} - {ep_name}"
                    
                    link_tag = item.find("a")
                    page_url = link_tag['href'] if link_tag else ""
                    
                    img_tag = item.find("img")
                    img_url = img_tag['src'] if img_tag else ""

                    # M3U8 linkini çek (Opsiyonel: Çok yavaşlatırsa burayı kapat)
                    stream_url = get_real_m3u8(page_url)
                    
                    # Eğer stream linki bulamazsa sayfa linkini ver
                    if not stream_url:
                        stream_url = BASE_URL + page_url if not page_url.startswith("http") else page_url

                    episode_list.append({
                        "name": full_name,
                        "url": page_url,
                        "img": img_url,
                        "stream_url": stream_url
                    })
                except:
                    continue

            # Sayfalama
            if len(items) < payload['count']:
                # Bu sayfada az veri varsa demek ki sezon sonu
                payload['season'] += 1
                payload['page'] = 0
            else:
                payload['page'] += 1
                
        except Exception as e:
            # print(f"Hata: {e}")
            break
            
    return episode_list

def create_m3u(path, data):
    """M3U dosyası oluşturur"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            # Data bir liste ise (toplu dosya)
            if isinstance(data, list):
                for show in data:
                    if "episodes" in show:
                        for ep in show["episodes"]:
                            f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}" group-title="{show["name"]}",{ep["name"]}\n')
                            f.write(f'{ep["stream_url"]}\n')
            # Data tekil bir sözlük ise (tekil dosya)
            elif isinstance(data, dict) and "episodes" in data:
                 for ep in data["episodes"]:
                    f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}",{ep["name"]}\n')
                    f.write(f'{ep["stream_url"]}\n')
    except:
        pass

def main():
    # Token Al
    if not get_csrf_token():
        print("Token alınamadığı için işlem durduruluyor.")
        return

    # Klasörleri temizle/oluştur
    for d in DIRS.values():
        os.makedirs(d, exist_ok=True)

    configs = [
        {"type": "series", "url": f"{BASE_URL}/ajax/series", "name": "Diziler"},
        {"type": "programs", "url": f"{BASE_URL}/ajax/programs", "name": "Programlar"},
        # Arşivleri de ekleyebilirsin ama süre uzar
        {"type": "series", "url": f"{BASE_URL}/ajax/archive", "name": "Arşiv Diziler"}, 
        {"type": "programs", "url": f"{BASE_URL}/ajax/archive", "name": "Arşiv Programlar"}
    ]

    all_series = []
    all_programs = []

    for conf in configs:
        print(f"\n--- {conf['name']} Taranıyor ---")
        
        # Listeyi çek
        page = 0
        has_next = True
        
        while has_next:
            try:
                # AJAX isteği
                r = session.post(conf['url'], data={
                    'page': page,
                    'type': conf['type'],
                    'count': 50,
                    'orderBy': 'id',
                    'sorting': 'desc'
                })
                
                resp = r.json()
                html = resp.get('data', '')
                
                if not html:
                    has_next = False
                    break
                
                soup = BeautifulSoup(html, 'html.parser')
                items = soup.find_all("div", {"class": "list-item"})
                
                if not items:
                    has_next = False
                    break
                
                print(f"Sayfa {page+1}: {len(items)} içerik bulundu.")
                
                for item in tqdm(items):
                    try:
                        show_name = item.find("strong").text.strip()
                        img_tag = item.find("img")
                        show_img = img_tag['src'] if img_tag else ""
                        
                        # ID al
                        # Örnek img: .../thumbnail/1819 -> ID: 1819
                        show_id = "0"
                        if show_img:
                            show_id = show_img.split("/")[-1].split(".")[0]
                        
                        # Bölümleri çek
                        episodes = get_episodes(show_id, show_name)
                        
                        if episodes:
                            show_data = {
                                "id": show_id,
                                "name": show_name,
                                "img": show_img,
                                "episodes": episodes
                            }
                            
                            # Slug (Dosya adı)
                            slug = show_name.lower().replace(" ", "-").replace("ç","c").replace("ğ","g").replace("ı","i").replace("ö","o").replace("ş","s").replace("ü","u")
                            slug = re.sub(r'[^a-z0-9-]', '', slug)
                            
                            # Kayıt Yeri
                            is_serie = conf['type'] == 'series'
                            target_dir = DIRS["series"] if is_serie else DIRS["programs"]
                            
                            # Tekil Dosyaları Kaydet
                            with open(os.path.join(target_dir, f"{slug}.json"), "w", encoding="utf-8") as f:
                                json.dump(show_data, f, ensure_ascii=False, indent=4)
                            create_m3u(os.path.join(target_dir, f"{slug}.m3u"), show_data)
                            
                            # Ana listeye ekle
                            if is_serie:
                                all_series.append(show_data)
                            else:
                                all_programs.append(show_data)
                                
                    except Exception as e:
                        # print(f"İçerik hatası: {e}")
                        pass

                page += 1
                
            except Exception as e:
                print(f"Liste çekme hatası: {e}")
                has_next = False

    # Ana Dosyaları Kaydet
    print("\nAna dosyalar kaydediliyor...")
    
    with open(os.path.join(ROOT_DIR, "now-diziler.json"), "w", encoding="utf-8") as f:
        json.dump(all_series, f, ensure_ascii=False, indent=4)
    create_m3u(os.path.join(ROOT_DIR, "now-diziler.m3u"), all_series)
    
    with open(os.path.join(ROOT_DIR, "now-programlar.json"), "w", encoding="utf-8") as f:
        json.dump(all_programs, f, ensure_ascii=False, indent=4)
    create_m3u(os.path.join(ROOT_DIR, "now-programlar.m3u"), all_programs)
    
    print(f"Toplam {len(all_series)} dizi ve {len(all_programs)} program kaydedildi.")

if __name__ == "__main__":
    main()
