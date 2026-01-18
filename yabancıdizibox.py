import cloudscraper
import re
import json
import time
import os
import unicodedata

# --- AYARLAR ---
BASE_URL = "https://yabancidizibox.com"
ROOT_DIR = "yabancidizibox"
MOVIE_DIR = os.path.join(ROOT_DIR, "filmler")
SERIES_DIR = os.path.join(ROOT_DIR, "diziler")

# HEPSİNİ ÇEKMEK İSTİYORSAN BU SAYILARI YÜKSELT (Örn: 500)
# DİKKAT: Diziler çok uzun sürer, çok yüksek yaparsan GitHub zaman aşımına uğrar.
MAX_MOVIE_PAGES = 50 
MAX_SERIES_PAGES = 10 

scraper = cloudscraper.create_scraper()

# --- YARDIMCI FONKSİYONLAR ---
def setup_directories():
    os.makedirs(MOVIE_DIR, exist_ok=True)
    os.makedirs(SERIES_DIR, exist_ok=True)

def sanitize_filename(name):
    """Dosya isimleri için Türkçe karakterleri ve geçersiz işaretleri temizler."""
    name = str(name).lower()
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    name = re.sub(r'[^\w\s-]', '', name).strip()
    name = re.sub(r'[-\s]+', '-', name)
    return name if name else "diger"

def extract_vidmody_link(url):
    try:
        # Hızlı olması için timeout ekledik
        response = scraper.get(url, timeout=10)
        if response.status_code != 200: return None
        html = response.text

        imdb_match = re.search(r'\"imdb_id\"\s*:\s*\"(tt\d+)\"', html) or re.search(r'(tt\d+)', html)
        if not imdb_match: return None
        imdb_id = imdb_match.group(1)

        if "/dizi/" in url:
            url_match = re.search(r'sezon-(\d+)/bolum-(\d+)', url)
            if not url_match: return None
            s, e = url_match.group(1), url_match.group(2)
            return f"https://vidmody.com/vs/{imdb_id}/s{int(s)}/e{int(e):02d}"
        else:
            return f"https://vidmody.com/vs/{imdb_id}"
    except:
        return None

def append_to_m3u(filepath, item):
    """Veriyi ilgili M3U dosyasının sonuna ekler (Dosya yoksa oluşturur)."""
    mode = 'a' if os.path.exists(filepath) else 'w'
    with open(filepath, mode, encoding='utf-8') as f:
        if mode == 'w': f.write("#EXTM3U\n")
        f.write(f'#EXTINF:-1 tvg-logo="{item["image"]}" group-title="{item["category"]}", {item["title"]}\n')
        f.write(f'{item["stream_url"]}\n')

# --- FİLM TARAMA VE KATEGORİLENDİRME ---
def crawl_movies():
    print(f"\n=== FİLMLER TARANIYOR (Max: {MAX_MOVIE_PAGES} Sayfa) ===")
    all_movies = []

    for page in range(1, MAX_MOVIE_PAGES + 1):
        api_url = f"{BASE_URL}/api/discover?contentType=movie&limit=24&page={page}"
        print(f" >> Sayfa {page} işleniyor...")
        
        try:
            resp = scraper.get(api_url)
            if resp.status_code != 200: break
            data = resp.json()
            movies = data.get('movies', [])
            
            if not movies: break # Film kalmadıysa dur

            for m in movies:
                title = m.get('title')
                slug = m.get('slug')
                # Türleri al (API genellikle genres: ["Aksiyon", "Dram"] döner)
                genres = m.get('genres', []) 
                
                # İlk türü kategori olarak belirle, yoksa 'Genel' yap
                main_genre = genres[0] if genres else "Genel"
                safe_genre_filename = sanitize_filename(main_genre) + ".m3u"
                
                poster = m.get('poster_path', '')
                img_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else ""

                if not slug: continue
                
                full_url = f"{BASE_URL}/film/{slug}"
                link = extract_vidmody_link(full_url)

                if link:
                    movie_obj = {
                        "title": title,
                        "image": img_url,
                        "stream_url": link,
                        "category": main_genre,
                        "genres": genres
                    }
                    all_movies.append(movie_obj)

                    # 1. İlgili kategori M3U dosyasına ekle (örn: filmler/aksiyon.m3u)
                    m3u_path = os.path.join(MOVIE_DIR, safe_genre_filename)
                    append_to_m3u(m3u_path, movie_obj)
                    
                    print(f"    [+] {title} -> {main_genre}")

                time.sleep(0.2) # Hızlandırmak için süreyi kısalttım
                
        except Exception as e:
            print(f"Sayfa hatası: {e}")
            
    return all_movies

# --- DİZİ TARAMA (DİZİYE ÖZEL M3U) ---
def crawl_series():
    print(f"\n=== DİZİLER TARANIYOR (Max: {MAX_SERIES_PAGES} Sayfa) ===")
    all_series_episodes = []

    for page in range(1, MAX_SERIES_PAGES + 1):
        api_url = f"{BASE_URL}/api/discover?contentType=series&limit=12&page={page}"
        print(f" >> Dizi Sayfası {page} işleniyor...")

        try:
            resp = scraper.get(api_url)
            if resp.status_code != 200: break
            series_list = resp.json().get('movies', [])
            
            if not series_list: break

            for s in series_list:
                s_title = s.get('title') or s.get('name')
                s_slug = s.get('slug')
                poster = s.get('poster_path', '')
                img_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else ""
                
                if not s_slug: continue
                
                # Diziye özel dosya adı (örn: diziler/vikingler.m3u)
                safe_s_name = sanitize_filename(s_title) + ".m3u"
                series_m3u_path = os.path.join(SERIES_DIR, safe_s_name)
                
                print(f"  [*] Dizi Taranıyor: {s_title}")
                
                # Sezonları bul
                s_url = f"{BASE_URL}/dizi/{s_slug}"
                try:
                    s_resp = scraper.get(s_url)
                    # Sadece Sezon linklerini al
                    season_paths = sorted(list(set(re.findall(r'href=\"(/dizi/[^/]+/sezon-\d+)\"', s_resp.text))))
                    
                    for season_path in season_paths:
                        # Bölümleri bul
                        full_season_url = BASE_URL + season_path
                        ep_resp = scraper.get(full_season_url)
                        ep_paths = sorted(list(set(re.findall(r'href=\"(/dizi/[^/]+/sezon-\d+/bolum-\d+)\"', ep_resp.text))))
                        
                        for ep_path in ep_paths:
                            full_ep_url = BASE_URL + ep_path
                            link = extract_vidmody_link(full_ep_url)
                            
                            # Sezon/Bölüm no parse et
                            match = re.search(r'sezon-(\d+)/bolum-(\d+)', ep_path)
                            if match:
                                s_num, e_num = match.group(1), match.group(2)
                                ep_full_title = f"{s_title} S{s_num} B{e_num}"
                            else:
                                ep_full_title = f"{s_title} - Bölüm"

                            if link:
                                ep_obj = {
                                    "title": ep_full_title,
                                    "image": img_url,
                                    "stream_url": link,
                                    "category": s_title
                                }
                                all_series_episodes.append(ep_obj)
                                
                                # Diziye ait M3U dosyasına yaz
                                append_to_m3u(series_m3u_path, ep_obj)
                                print(f"      -> Eklendi: {ep_full_title}")
                            
                            # Çok seri istek atınca site kilitler, minik bekleme
                            time.sleep(0.1) 

                except Exception as e:
                    print(f"    Dizi içi hata ({s_title}): {e}")

        except Exception as e:
            print(f"Dizi sayfa hatası: {e}")
            
    return all_series_episodes

if __name__ == "__main__":
    setup_directories()
    
    # 1. Filmleri Tarat ve Kaydet
    movies_data = crawl_movies()
    with open(os.path.join(ROOT_DIR, "filmler.json"), 'w', encoding='utf-8') as f:
        json.dump(movies_data, f, ensure_ascii=False, indent=4)
        
    # 2. Dizileri Tarat ve Kaydet
    series_data = crawl_series()
    with open(os.path.join(ROOT_DIR, "diziler.json"), 'w', encoding='utf-8') as f:
        json.dump(series_data, f, ensure_ascii=False, indent=4)

    print("\nTÜM İŞLEMLER TAMAMLANDI.")
