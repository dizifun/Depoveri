import cloudscraper
import re
import json
import time
import os

# --- AYARLAR ---
BASE_URL = "https://yabancidizibox.com"
OUTPUT_FOLDER = "yabancidizibox"
MAX_MOVIE_PAGES = 1  # Kaç sayfa film taransın? (Test için 1, gerçekte artır)
MAX_SERIES_PAGES = 1 # Kaç sayfa dizi taransın? (Diziler uzun sürer, dikkat!)

# Klasörü oluştur (yoksa yaratır)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

scraper = cloudscraper.create_scraper()

def extract_vidmody_link(url):
    """Verilen URL'den Vidmody izleme linkini çeker."""
    try:
        response = scraper.get(url, timeout=10)
        if response.status_code != 200: return None
        html = response.text

        # IMDB ID Bulma
        imdb_match = re.search(r'\"imdb_id\"\s*:\s*\"(tt\d+)\"', html) or re.search(r'(tt\d+)', html)
        if not imdb_match: return None
        imdb_id = imdb_match.group(1)

        # Link oluşturma
        if "/dizi/" in url:
            url_match = re.search(r'sezon-(\d+)/bolum-(\d+)', url)
            if not url_match: return None
            s, e = url_match.group(1), url_match.group(2)
            return f"https://vidmody.com/vs/{imdb_id}/s{int(s)}/e{int(e):02d}"
        else:
            return f"https://vidmody.com/vs/{imdb_id}"
    except Exception:
        return None

def save_m3u(data_list, filename):
    """Listeyi M3U formatında dosyaya yazar."""
    filepath = os.path.join(OUTPUT_FOLDER, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for item in data_list:
            # Grup başlığı (Filmler veya Diziler)
            group = item.get('category', 'Genel')
            name = item.get('title', 'Bilinmeyen')
            img = item.get('image', '')
            link = item.get('stream_url', '')
            
            f.write(f'#EXTINF:-1 tvg-logo="{img}" group-title="{group}", {name}\n')
            f.write(f'{link}\n')
    print(f"Dosya oluşturuldu: {filepath}")

def crawl_movies():
    print(f"\n--- Filmler Taranıyor ({MAX_MOVIE_PAGES} Sayfa) ---")
    movies_data = []
    
    for page in range(1, MAX_MOVIE_PAGES + 1):
        api_url = f"{BASE_URL}/api/discover?contentType=movie&limit=20&page={page}"
        try:
            resp = scraper.get(api_url)
            if resp.status_code != 200: continue
            items = resp.json().get('movies', [])

            for item in items:
                title = item.get('title')
                slug = item.get('slug')
                poster = item.get('poster_path', '')
                img_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else ""
                
                if not slug: continue
                
                full_url = f"{BASE_URL}/film/{slug}"
                print(f"Film: {title}")
                
                link = extract_vidmody_link(full_url)
                if link:
                    movies_data.append({
                        "title": title,
                        "image": img_url,
                        "stream_url": link,
                        "category": "Filmler"
                    })
                time.sleep(0.5)
        except Exception as e:
            print(f"Film hatası: {e}")
            
    return movies_data

def crawl_series():
    print(f"\n--- Diziler Taranıyor ({MAX_SERIES_PAGES} Sayfa) ---")
    series_data = []

    for page in range(1, MAX_SERIES_PAGES + 1):
        api_url = f"{BASE_URL}/api/discover?contentType=series&limit=12&page={page}" # Limit düşürüldü
        try:
            resp = scraper.get(api_url)
            items = resp.json().get('movies', []) # API diziler için de 'movies' keyini kullanıyor

            for item in items:
                series_name = item.get('title') or item.get('name')
                slug = item.get('slug')
                poster = item.get('poster_path', '')
                img_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else ""
                
                if not slug: continue
                
                series_url = f"{BASE_URL}/dizi/{slug}"
                print(f" >> Dizi Analiz Ediliyor: {series_name}")
                
                # Dizi sayfasına girip sezonları bul
                try:
                    s_resp = scraper.get(series_url)
                    season_paths = list(set(re.findall(r'href=\"(/dizi/[^/]+/sezon-\d+)\"', s_resp.text)))
                    
                    for s_path in season_paths:
                        # Sezon sayfasına girip bölümleri bul
                        full_s_url = BASE_URL + s_path
                        se_resp = scraper.get(full_s_url)
                        ep_paths = list(set(re.findall(r'href=\"(/dizi/[^/]+/sezon-\d+/bolum-\d+)\"', se_resp.text)))
                        
                        for ep_path in ep_paths:
                            ep_url = BASE_URL + ep_path
                            link = extract_vidmody_link(ep_url)
                            
                            # URL'den Sezon/Bölüm bilgisini alıp başlığa ekle
                            match = re.search(r'sezon-(\d+)/bolum-(\d+)', ep_path)
                            s_num = match.group(1) if match else "?"
                            e_num = match.group(2) if match else "?"
                            
                            full_title = f"{series_name} S{s_num} E{e_num}"
                            
                            if link:
                                series_data.append({
                                    "title": full_title,
                                    "image": img_url,
                                    "stream_url": link,
                                    "category": "Diziler"
                                })
                                print(f"    + Eklendi: {full_title}")
                            time.sleep(0.2)
                except Exception as e:
                    print(f"    Dizi içi hata: {e}")

        except Exception as e:
            print(f"Dizi sayfa hatası: {e}")
            
    return series_data

if __name__ == "__main__":
    # 1. Filmleri Çek
    movies = crawl_movies()
    save_m3u(movies, "filmler.m3u")
    
    # 2. Dizileri Çek
    series = crawl_series()
    save_m3u(series, "diziler.m3u")
    
    # 3. Hepsini Birleştir
    all_content = movies + series
    save_m3u(all_content, "hepsi.m3u")
    
    # 4. JSON Olarak da Kaydet (Yedek)
    json_path = os.path.join(OUTPUT_FOLDER, "data.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(all_content, f, ensure_ascii=False, indent=4)
        
    print("\n--- Tüm işlemler tamamlandı. ---")
