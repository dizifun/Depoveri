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

# Oturum Başlat
session = requests.Session()
# Daha güncel bir User-Agent ve ek headerlar
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE_URL,
    "Origin": BASE_URL,
    "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"'
})

def get_csrf_token():
    """Siteye girip güvenlik tokenını (CSRF) alır."""
    print("🔑 Siteye bağlanılıyor ve Token alınıyor...")
    try:
        r = session.get(BASE_URL, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        token_tag = soup.find('meta', {'name': 'csrf-token'})
        if token_tag and token_tag.get('content'):
            token = token_tag['content']
            session.headers.update({'X-CSRF-TOKEN': token})
            print(f"✅ Token alındı: {token[:10]}...")
            return True
        else:
            print("❌ HATA: CSRF Token bulunamadı! Sayfa içeriği değişmiş veya engellenmiş olabilir.")
            # Debug için sayfa başlığını yazdır
            print(f"Sayfa Başlığı: {soup.title.string if soup.title else 'Yok'}")
            return False
    except Exception as e:
        print(f"❌ Bağlantı hatası: {e}")
        return False

def get_real_stream_url(episode_url):
    if not episode_url: return ""
    full_url = episode_url if episode_url.startswith("http") else BASE_URL + episode_url
    try:
        r = session.get(full_url, timeout=10)
        match = re.search(r"source:\s*['\"](https:\/\/[^'\"]*?\.m3u8[^'\"]*?)['\"]", r.text)
        if match:
            return match.group(1)
        return ""
    except:
        return ""

def get_episodes(program_id, show_name):
    url = f"{BASE_URL}/ajax/videos"
    episode_list = []
    
    # Payload
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

    while payload['season'] < 10:
        try:
            r = session.post(url, data=payload, timeout=10)
            try:
                resp_json = r.json()
            except:
                break 

            html = resp_json.get('data', '')
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
                    
                    stream_url = get_real_stream_url(page_url)
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
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            if isinstance(data, list):
                for show in data:
                    if "episodes" in show:
                        for ep in show["episodes"]:
                            f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}" group-title="{show["name"]}",{ep["name"]}\n')
                            f.write(f'{ep["stream_url"]}\n')
            elif isinstance(data, dict) and "episodes" in data:
                 for ep in data["episodes"]:
                    f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}",{ep["name"]}\n')
                    f.write(f'{ep["stream_url"]}\n')
    except:
        pass

def main():
    if not get_csrf_token():
        return

    for d in DIRS.values():
        os.makedirs(d, exist_ok=True)

    configs = [
        {"type": "series", "url": f"{BASE_URL}/ajax/series", "name": "Diziler"},
        {"type": "programs", "url": f"{BASE_URL}/ajax/programs", "name": "Programlar"},
    ]

    all_series = []
    all_programs = []

    for conf in configs:
        print(f"\n--- {conf['name']} Taranıyor ---")
        page = 0
        has_next = True

        while has_next:
            try:
                # Type'ı payload'dan çıkarıyoruz, çünkü endpoint zaten /ajax/series
                # veya API'nin beklediği spesifik değeri gönderiyoruz.
                payload = {
                    'page': page,
                    'count': 50,
                    'orderBy': 'id',
                    'sorting': 'desc'
                }
                # Eski koddaki gibi type göndermek gerekirse buraya ekle ama genelde endpoint yeterlidir.
                # Eğer type zorunluysa '1' (dizi) veya '2' (program) gibi int değerler denenmeli.
                # Şimdilik orijinal mantığı koruyup type'ı string olarak ekliyorum ama debug basacağız.
                payload['type'] = conf['type'] 

                r = session.post(conf['url'], data=payload, timeout=20)

                resp = None
                try:
                    resp = r.json()
                except json.JSONDecodeError:
                    print(f"⚠️ JSON Ayrıştırma Hatası! Status Code: {r.status_code}")
                    print(f"📄 Gelen Veri (İlk 200 karakter): {r.text[:200]}")
                    has_next = False
                    break

                html = resp.get('data', '')
                if not html:
                    print(f"⚠️ API 'data' alanı boş döndü. (Sayfa: {page})")
                    # Eğer count 0 ise veya boşsa
                    if 'count' in resp:
                         print(f"ℹ️ Sunucudan gelen count: {resp['count']}")
                    else:
                         print(f"ℹ️ Sunucu tamamen boş data döndü. Muhtemel Geo-Block.")
                    has_next = False
                    break

                soup = BeautifulSoup(html, 'html.parser')
                items = soup.find_all("div", {"class": "list-item"})

                if not items:
                    print(f"⚠️ HTML parse edildi ama 'list-item' bulunamadı.")
                    has_next = False
                    break

                print(f">> Sayfa {page+1}: {len(items)} içerik bulundu.")

                for item in tqdm(items):
                    try:
                        show_name = item.find("strong").text.strip()
                        img_tag = item.find("img")
                        show_img = img_tag['src'] if img_tag else ""
                        
                        show_id = "0"
                        if show_img:
                            show_id = show_img.split("/")[-1].split(".")[0]

                        episodes = get_episodes(show_id, show_name)

                        if episodes:
                            show_data = {
                                "id": show_id,
                                "name": show_name,
                                "img": show_img,
                                "episodes": episodes
                            }
                            slug = show_name.lower().replace(" ", "-").replace("ç","c").replace("ğ","g").replace("ı","i").replace("ö","o").replace("ş","s").replace("ü","u")
                            slug = re.sub(r'[^a-z0-9-]', '', slug)

                            is_serie = conf['type'] == 'series'
                            target_dir = DIRS["series"] if is_serie else DIRS["programs"]

                            with open(os.path.join(target_dir, f"{slug}.json"), "w", encoding="utf-8") as f:
                                json.dump(show_data, f, ensure_ascii=False, indent=4)
                            create_m3u(os.path.join(target_dir, f"{slug}.m3u"), show_data)

                            if is_serie:
                                all_series.append(show_data)
                            else:
                                all_programs.append(show_data)
                    except:
                        pass
                page += 1
            except Exception as e:
                print(f"Liste döngüsü hatası: {e}")
                has_next = False

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
