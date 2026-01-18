import cloudscraper
import re
import os
import time
import unicodedata

# --- AYARLAR ---
BASE_URL = "https://yabancidizibox.com"
ROOT_DIR = "yabancidizibox"
MOVIE_DIR = os.path.join(ROOT_DIR, "filmler")
SERIES_DIR = os.path.join(ROOT_DIR, "diziler")

# Sayfa sayıları (Daha fazla veri için arttırabilirsin)
MAX_MOVIE_PAGES = 50 
MAX_SERIES_PAGES = 10

scraper = cloudscraper.create_scraper()

def setup_directories():
    os.makedirs(MOVIE_DIR, exist_ok=True)
    os.makedirs(SERIES_DIR, exist_ok=True)

def sanitize_filename(name):
    """Dosya ismini temizler: 'Hızlı ve Öfkeli' -> 'Hizli-ve-ofkeli.m3u'"""
    if not name: return "Genel"
    name = str(name).lower()
    # Türkçe karakterleri İngilizce yap (ş -> s, ı -> i)
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    # Sadece harf ve rakam bırak
    name = re.sub(r'[^\w\s-]', '', name).strip()
    name = re.sub(r'[-\s]+', '-', name)
    return name.capitalize()

def extract_vidmody_link(url):
    try:
        response = scraper.get(url, timeout=10)
        if response.status_code != 200: return None
        html = response.text

        imdb_match = re.search(r'\"imdb_id\"\s*:\s*\"(tt\d+)\"', html) or re.search(r'(tt\d+)', html)
        if not imdb_match: return None
        imdb_id = imdb_match.group(1)

        if "/dizi/" in url:
            match = re.search(r'sezon-(\d+)/bolum-(\d+)', url)
            if match:
                return f"https://vidmody.com/vs/{imdb_id}/s{int(match.group(1))}/e{int(match.group(2)):02d}"
        else:
            return f"https://vidmody.com/vs/{imdb_id}"
    except:
        return None

def append_to_m3u(filepath, item, group_name):
    mode = 'a' if os.path.exists(filepath) else 'w'
    with open(filepath, mode, encoding='utf-8') as f:
        if mode == 'w': f.write("#EXTM3U\n")
        f.write(f'#EXTINF:-1 tvg-logo="{item["image"]}" group-title="{group_name}", {item["title"]}\n')
        f.write(f'{item["stream_url"]}\n')

def crawl_movies():
    print("--- FİLMLER BAŞLIYOR ---")
    main_m3u = os.path.join(ROOT_DIR, "filmler.m3u")
    # Dosyayı sıfırla
    with open(main_m3u, 'w', encoding='utf-8') as f: f.write("#EXTM3U\n")

    for page in range(1, MAX_MOVIE_PAGES + 1):
        try:
            url = f"{BASE_URL}/api/discover?contentType=movie&limit=24&page={page}"
            resp = scraper.get(url).json()
            movies = resp.get('movies', [])
            if not movies: break

            for m in movies:
                title = m.get('title')
                slug = m.get('slug')
                genres = m.get('genres', [])
                category = genres[0] if genres else "Genel" # İlk türü kategori yap
                
                # Dosya ismi oluştur (Örn: Korku.m3u)
                cat_filename = sanitize_filename(category) + ".m3u"
                cat_path = os.path.join(MOVIE_DIR, cat_filename)

                if slug:
                    link = extract_vidmody_link(f"{BASE_URL}/film/{slug}")
                    if link:
                        obj = {
                            "title": title,
                            "image": f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}",
                            "stream_url": link
                        }
                        # 1. Ana dosyaya ekle
                        append_to_m3u(main_m3u, obj, category)
                        # 2. Kategori dosyasına ekle
                        append_to_m3u(cat_path, obj, category)
                        print(f"Film Eklendi: {title} ({category})")
                time.sleep(0.1)
        except Exception as e:
            print(f"Hata: {e}")

def crawl_series():
    print("--- DİZİLER BAŞLIYOR ---")
    main_m3u = os.path.join(ROOT_DIR, "diziler.m3u")
    with open(main_m3u, 'w', encoding='utf-8') as f: f.write("#EXTM3U\n")

    for page in range(1, MAX_SERIES_PAGES + 1):
        try:
            url = f"{BASE_URL}/api/discover?contentType=series&limit=12&page={page}"
            resp = scraper.get(url).json()
            series = resp.get('movies', [])
            if not series: break

            for s in series:
                title = s.get('title') or s.get('name')
                slug = s.get('slug')
                if not slug: continue
                
                # Dosya ismi: Vikingler.m3u
                series_filename = sanitize_filename(title) + ".m3u"
                series_path = os.path.join(SERIES_DIR, series_filename)
                
                print(f"Dizi Taranıyor: {title}")
                
                s_page = scraper.get(f"{BASE_URL}/dizi/{slug}").text
                seasons = sorted(list(set(re.findall(r'href=\"(/dizi/[^/]+/sezon-\d+)\"', s_page))))
                
                for sea in seasons:
                    ep_page = scraper.get(BASE_URL + sea).text
                    episodes = sorted(list(set(re.findall(r'href=\"(/dizi/[^/]+/sezon-\d+/bolum-\d+)\"', ep_page))))
                    
                    for ep in episodes:
                        link = extract_vidmody_link(BASE_URL + ep)
                        match = re.search(r'sezon-(\d+)/bolum-(\d+)', ep)
                        
                        if link and match:
                            full_title = f"{title} - S{match.group(1)} B{match.group(2)}"
                            short_title = f"S{match.group(1)} B{match.group(2)}"
                            
                            obj = {
                                "title": full_title, # Ana liste için uzun isim
                                "image": f"https://image.tmdb.org/t/p/w500{s.get('poster_path')}",
                                "stream_url": link
                            }
                            
                            # Ana dizi listesine ekle
                            append_to_m3u(main_m3u, obj, title)
                            
                            # Sadece dizinin kendi dosyasına kısa isimle ekle
                            obj["title"] = short_title
                            append_to_m3u(series_path, obj, title)
                        time.sleep(0.1)

        except Exception as e:
            print(f"Hata: {e}")

if __name__ == "__main__":
    setup_directories()
    crawl_movies()
    crawl_series()
