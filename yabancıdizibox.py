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

# Sayfa sayılarını test için düşük tutabilirsin, tamamı için yükselt.
MAX_MOVIE_PAGES = 50 
MAX_SERIES_PAGES = 10 

scraper = cloudscraper.create_scraper()

def setup_directories():
    if os.path.exists(ROOT_DIR):
        # Temiz başlangıç için eski bozuk dosyaları silmek istersen burayı açabilirsin
        pass
    os.makedirs(MOVIE_DIR, exist_ok=True)
    os.makedirs(SERIES_DIR, exist_ok=True)

def sanitize_filename(name):
    """Dosya isimlerini okunabilir ve temiz hale getirir (ID kullanmaz)."""
    if not name: return "Bilinmeyen"
    name = str(name).lower()
    # Türkçe karakterleri İngilizce karşılığına çevir (ş -> s, ı -> i)
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    # Sadece harf, rakam ve tire kalsın
    name = re.sub(r'[^\w\s-]', '', name).strip()
    name = re.sub(r'[-\s]+', '-', name)
    return name.capitalize() if name else "Genel"

def extract_vidmody_link(url):
    try:
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

def append_to_m3u(filepath, item, group_name):
    """Veriyi M3U formatında ekler. group_name parametresi kategoriyi belirler."""
    mode = 'a' if os.path.exists(filepath) else 'w'
    with open(filepath, mode, encoding='utf-8') as f:
        if mode == 'w': f.write("#EXTM3U\n")
        # BURASI ÖNEMLİ: group-title düzgün yazılıyor
        f.write(f'#EXTINF:-1 tvg-logo="{item["image"]}" group-title="{group_name}", {item["title"]}\n')
        f.write(f'{item["stream_url"]}\n')

# --- FİLMLER ---
def crawl_movies():
    print(f"\n=== FİLMLER İŞLENİYOR ===")
    
    # Ana dosya yolunu belirle
    main_movie_m3u = os.path.join(ROOT_DIR, "filmler.m3u")
    # Dosyayı sıfırla
    with open(main_movie_m3u, 'w', encoding='utf-8') as f: f.write("#EXTM3U\n")

    for page in range(1, MAX_MOVIE_PAGES + 1):
        api_url = f"{BASE_URL}/api/discover?contentType=movie&limit=24&page={page}"
        print(f" >> Film Sayfası {page} taranıyor...")
        
        try:
            resp = scraper.get(api_url)
            if resp.status_code != 200: break
            movies = resp.json().get('movies', [])
            if not movies: break

            for m in movies:
                title = m.get('title')
                slug = m.get('slug')
                genres = m.get('genres', [])
                
                # Kategori belirleme (Yoksa 'Genel' yap)
                category_name = genres[0] if genres else "Genel"
                
                # Dosya ismi için temizle (Örn: Aksiyon -> aksiyon.m3u)
                safe_cat_filename = sanitize_filename(category_name) + ".m3u"
                
                poster = m.get('poster_path', '')
                img_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else ""

                if not slug: continue
                
                full_url = f"{BASE_URL}/film/{slug}"
                link = extract_vidmody_link(full_url)

                if link:
                    movie_obj = {
                        "title": title,
                        "image": img_url,
                        "stream_url": link
                    }
                    
                    # 1. Ana film dosyasına ekle (group-title=Kategori olacak)
                    append_to_m3u(main_movie_m3u, movie_obj, group_name=category_name)
                    
                    # 2. Kategorisine özel dosyaya ekle (Örn: filmler/aksiyon.m3u)
                    cat_path = os.path.join(MOVIE_DIR, safe_cat_filename)
                    append_to_m3u(cat_path, movie_obj, group_name=category_name)
                    
                    print(f"    + {title} -> {category_name}")

                time.sleep(0.1)
                
        except Exception as e:
            print(f"Hata: {e}")

# --- DİZİLER ---
def crawl_series():
    print(f"\n=== DİZİLER İŞLENİYOR ===")
    
    # Ana dizi dosyası
    main_series_m3u = os.path.join(ROOT_DIR, "diziler.m3u")
    with open(main_series_m3u, 'w', encoding='utf-8') as f: f.write("#EXTM3U\n")

    for page in range(1, MAX_SERIES_PAGES + 1):
        api_url = f"{BASE_URL}/api/discover?contentType=series&limit=12&page={page}"
        print(f" >> Dizi Sayfası {page} taranıyor...")

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
                
                if not s_slug or not s_title: continue
                
                # Dizi ismini dosya adı yap (Örn: La Casa De Papel -> La-casa-de-papel.m3u)
                safe_s_name = sanitize_filename(s_title) + ".m3u"
                series_file_path = os.path.join(SERIES_DIR, safe_s_name)
                
                print(f"  [*] Dizi: {s_title}")
                
                try:
                    s_resp = scraper.get(f"{BASE_URL}/dizi/{s_slug}")
                    season_paths = sorted(list(set(re.findall(r'href=\"(/dizi/[^/]+/sezon-\d+)\"', s_resp.text))))
                    
                    for season_path in season_paths:
                        ep_resp = scraper.get(BASE_URL + season_path)
                        ep_paths = sorted(list(set(re.findall(r'href=\"(/dizi/[^/]+/sezon-\d+/bolum-\d+)\"', ep_resp.text))))
                        
                        for ep_path in ep_paths:
                            link = extract_vidmody_link(BASE_URL + ep_path)
                            
                            match = re.search(r'sezon-(\d+)/bolum-(\d+)', ep_path)
                            if match:
                                s_num, e_num = match.group(1), match.group(2)
                                # Başlık: S1 B1
                                ep_display_title = f"S{s_num} B{e_num}"
                                # Full Başlık: Vikingler S1 B1 (Ana liste için)
                                full_display_title = f"{s_title} - S{s_num} B{e_num}"
                            else:
                                ep_display_title = "Bölüm"
                                full_display_title = f"{s_title} - Bölüm"

                            if link:
                                ep_obj = {"image": img_url, "stream_url": link, "title": full_display_title}
                                
                                # 1. Ana Dizi Listesine Ekle (Grup ismi Dizi Adı olacak)
                                # Böylece listede 'Game of Thrones' klasörü gibi görünür
                                append_to_m3u(main_series_m3u, ep_obj, group_name=s_title)
                                
                                # 2. Sadece O Diziye Ait Dosyaya Ekle
                                # Buraya sadece bölüm adını yazıyoruz (Zaten dizinin kendi dosyası)
                                specific_obj = {"image": img_url, "stream_url": link, "title": ep_display_title}
                                append_to_m3u(series_file_path, specific_obj, group_name=s_title)
                                
                            time.sleep(0.1)
                except Exception as e:
                    print(f"    Dizi hatası ({s_title}): {e}")

        except Exception as e:
            print(f"Genel Hata: {e}")

if __name__ == "__main__":
    setup_directories()
    crawl_movies()
    crawl_series()
    print("\nTÜM İŞLEMLER BAŞARIYLA TAMAMLANDI.")
