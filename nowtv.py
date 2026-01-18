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

# Oturum Başlat (Cookie'leri tutmak için şart)
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE_URL,
    "Origin": BASE_URL
})

def get_csrf_token():
    """Siteye girip güvenlik tokenını (CSRF) alır."""
    print("🔑 Siteye bağlanılıyor ve Token alınıyor...")
    try:
        # Ana sayfaya normal istek at (HTML al)
        r = session.get(BASE_URL)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Meta tag'den token'ı bul
        token_tag = soup.find('meta', {'name': 'csrf-token'})
        if token_tag and token_tag.get('content'):
            token = token_tag['content']
            # Token'ı header'a ekle (Artık tüm isteklerde bu kullanılacak)
            session.headers.update({'X-CSRF-TOKEN': token})
            print(f"✅ Token alındı: {token[:10]}...")
            return True
        else:
            print("❌ HATA: CSRF Token bulunamadı!")
            return False
    except Exception as e:
        print(f"❌ Bağlantı hatası: {e}")
        return False

def get_real_stream_url(episode_url):
    """Bölüm sayfasına girip nowtv-vod.ercdn.net linkini regex ile çeker."""
    if not episode_url: return ""
    
    full_url = episode_url if episode_url.startswith("http") else BASE_URL + episode_url
    
    try:
        # Sayfaya git
        r = session.get(full_url, timeout=10)
        
        # HTML içindeki ADMPlayer.init ayarlarında 'source' kısmını ara
        # Örnek: source: 'https://nowtv-vod.ercdn.net/...'
        match = re.search(r"source:\s*['\"](https:\/\/[^'\"]*?\.m3u8[^'\"]*?)['\"]", r.text)
        if match:
            return match.group(1)
        return ""
    except:
        return ""

def get_episodes(program_id, show_name):
    """Verilen program ID'sine ait tüm bölümleri çeker."""
    url = f"{BASE_URL}/ajax/videos"
    episode_list = []
    
    # İlk sayfa parametreleri
    payload = {
        'filter': 'season',
        'season': 1,
        'program_id': program_id,
        'page': 0,
        'type': 2, # Video tipi
        'count': 50,
        'orderBy': 'id',
        'sorting': 'asc'
    }

    # Max 10 sezon dener
    while payload['season'] < 10:
        try:
            # Token yüklü session ile POST isteği at
            r = session.post(url, data=payload)
            
            # JSON yanıtını kontrol et
            try:
                resp_json = r.json()
            except:
                break # JSON dönmezse çık
                
            html = resp_json.get('data', '')
            total_count_api = int(resp_json.get('count', 0))
            
            # Veri yoksa diğer sezona geç veya bitir
            if not html:
                if payload['page'] == 0:
                    payload['season'] += 1
                    continue
                else:
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

                    # Stream Linkini Al
                    stream_url = get_real_stream_url(page_url)
                    
                    # Eğer m3u8 bulamazsa, sayfa linkini koy
                    if not stream_url:
                        stream_url = BASE_URL + page_url if not page_url.startswith("http") else page_url

                    episode_list.append({
                        "name": full_name,
                        "img": img_url,
                        "url": page_url,
                        "stream_url": stream_url
                    })
                except:
                    continue

            # Sayfalama Kontrolü
            # Eğer gelen eleman sayısı istenenden azsa, bu sezonun son sayfasıdır.
            if len(items) < payload['count']:
                payload['season'] += 1
                payload['page'] = 0
            else:
                payload['page'] += 1
                
        except Exception as e:
            print(f"Bölüm çekme hatası: {e}")
            break
            
    return episode_list

def create_m3u(path, data):
    """JSON verisinden M3U dosyası oluşturur."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            # Liste ise (Toplu dosya)
            if isinstance(data, list):
                for show in data:
                    if "episodes" in show:
                        for ep in show["episodes"]:
                            f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}" group-title="{show["name"]}",{ep["name"]}\n')
                            f.write(f'{ep["stream_url"]}\n')
            # Sözlük ise (Tekil dosya)
            elif isinstance(data, dict) and "episodes" in data:
                 for ep in data["episodes"]:
                    f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}",{ep["name"]}\n')
                    f.write(f'{ep["stream_url"]}\n')
    except:
        pass

def main():
    # 1. Token Al (Çok Önemli)
    if not get_csrf_token():
        return

    # 2. Klasörleri Oluştur
    for d in DIRS.values():
        os.makedirs(d, exist_ok=True)

    configs = [
        {"type": "series", "url": f"{BASE_URL}/ajax/series", "name": "Diziler"},
        {"type": "programs", "url": f"{BASE_URL}/ajax/programs", "name": "Programlar"},
        # Arşivleri istersen açabilirsin, süreyi uzatır.
        # {"type": "series", "url": f"{BASE_URL}/ajax/archive", "name": "Arşiv Diziler"}, 
        # {"type": "programs", "url": f"{BASE_URL}/ajax/archive", "name": "Arşiv Programlar"}
    ]

    all_series = []
    all_programs = []

    for conf in configs:
        print(f"\n--- {conf['name']} Taranıyor ---")
        
        page = 0
        has_next = True
        
        while has_next:
            try:
                # Liste çekmek için POST isteği (Token gerekli)
                r = session.post(conf['url'], data={
                    'page': page,
                    'type': conf['type'],
                    'count': 50,
                    'orderBy': 'id',
                    'sorting': 'desc'
                })
                
                # JSON kontrol
                try:
                    resp = r.json()
                except:
                    has_next = False
                    break

                html = resp.get('data', '')
                if not html:
                    has_next = False
                    break
                
                soup = BeautifulSoup(html, 'html.parser')
                items = soup.find_all("div", {"class": "list-item"})
                
                if not items:
                    has_next = False
                    break
                
                print(f">> Sayfa {page+1}: {len(items)} içerik bulundu.")
                
                for item in tqdm(items):
                    try:
                        show_name = item.find("strong").text.strip()
                        img_tag = item.find("img")
                        show_img = img_tag['src'] if img_tag else ""
                        
                        # ID Al (Resim yolundan)
                        show_id = "0"
                        if show_img:
                            show_id = show_img.split("/")[-1].split(".")[0]
                        
                        # Bölümleri Çek
                        episodes = get_episodes(show_id, show_name)
                        
                        if episodes:
                            show_data = {
                                "id": show_id,
                                "name": show_name,
                                "img": show_img,
                                "episodes": episodes
                            }
                            
                            # Dosya ismi (slug)
                            slug = show_name.lower().replace(" ", "-").replace("ç","c").replace("ğ","g").replace("ı","i").replace("ö","o").replace("ş","s").replace("ü","u")
                            slug = re.sub(r'[^a-z0-9-]', '', slug)
                            
                            # Kayıt Klasörü
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
                                
                    except:
                        pass

                page += 1
                
            except Exception as e:
                print(f"Liste hatası: {e}")
                has_next = False

    # 3. Ana Dosyaları Kaydet
    print("\n📦 Ana dosyalar oluşturuluyor...")
    
    with open(os.path.join(ROOT_DIR, "now-diziler.json"), "w", encoding="utf-8") as f:
        json.dump(all_series, f, ensure_ascii=False, indent=4)
    create_m3u(os.path.join(ROOT_DIR, "now-diziler.m3u"), all_series)
    
    with open(os.path.join(ROOT_DIR, "now-programlar.json"), "w", encoding="utf-8") as f:
        json.dump(all_programs, f, ensure_ascii=False, indent=4)
    create_m3u(os.path.join(ROOT_DIR, "now-programlar.m3u"), all_programs)
    
    print(f"✅ Bitti! {len(all_series)} dizi ve {len(all_programs)} program kaydedildi.")

if __name__ == "__main__":
    main()
