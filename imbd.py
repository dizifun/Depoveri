import requests
import json
import os
import re
import time

# --- AYARLAR ---
API_KEY = "6fabef7bd74e01efcd81d35c39c4a049"
BASE_URL = "https://api.themoviedb.org/3"
VIDMODY_BASE = "https://vidmody.com/vs"
IMG_URL = "https://image.tmdb.org/t/p/w500"

# Link kontrolü uzun sürdüğü için şimdilik 3 sayfa (60 içerik) ile test et.
# Hız sorunu yoksa arttırabilirsin.
MAX_PAGES = 3

# Klasörleri oluştur
os.makedirs("output/filmler", exist_ok=True)
os.makedirs("output/diziler", exist_ok=True)

# Tarayıcı gibi görünmek için başlık (Site bot olduğumuzu anlamasın)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def sanitize_filename(name):
    """Dosya ismindeki yasaklı karakterleri temizler."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def check_link_active(url):
    """
    Linkin çalışıp çalışmadığını kontrol eder.
    HEAD isteği atar, sadece başlığı okur (videoyu indirmez, hızlıdır).
    """
    try:
        response = requests.head(url, headers=HEADERS, timeout=3, allow_redirects=True)
        # 200 = Başarılı, Site var.
        if response.status_code == 200:
            return True
        return False
    except:
        return False

def get_imdb_id(tmdb_id, media_type):
    """TMDB ID'den IMDb ID'yi bulur."""
    try:
        url = f"{BASE_URL}/{media_type}/{tmdb_id}/external_ids?api_key={API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json().get("imdb_id")
    except:
        return None
    return None

def save_m3u(filename, content_list):
    """M3U listesi oluşturur."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in content_list:
            f.write(f'#EXTINF:-1 group-title="{item["group"]}" tvg-logo="{item["logo"]}", {item["name"]}\n')
            f.write(f'{item["url"]}\n')

def process_movies():
    print(f"--- FİLMLER BAŞLIYOR (Link Kontrollü) ---")
    movies_data = []
    m3u_entries = []

    for page in range(1, MAX_PAGES + 1):
        print(f"Film Sayfası: {page}/{MAX_PAGES}")
        try:
            url = f"{BASE_URL}/movie/popular?api_key={API_KEY}&language=tr-TR&page={page}"
            data = requests.get(url).json()
            
            for item in data.get('results', []):
                imdb_id = get_imdb_id(item['id'], 'movie')
                
                if imdb_id:
                    link = f"{VIDMODY_BASE}/{imdb_id}"
                    
                    # --- KRİTİK NOKTA: Link Kontrolü ---
                    # Eğer link çalışıyorsa listeye ekle, çalışmıyorsa atla.
                    if check_link_active(link):
                        print(f"[OK] Film Eklendi: {item['title']}")
                        
                        title = item['title']
                        poster = f"{IMG_URL}{item['poster_path']}" if item.get('poster_path') else ""
                        
                        movie_obj = {
                            "id": imdb_id,
                            "title": title,
                            "poster": poster,
                            "link": link
                        }
                        movies_data.append(movie_obj)
                        
                        m3u_entries.append({
                            "group": "Filmler",
                            "logo": poster,
                            "name": title,
                            "url": link
                        })
                    else:
                        print(f"[X] Link Çalışmıyor (Atlandı): {item['title']}")
                        
                    # Sitenin bizi engellememesi için çok kısa bekleme
                    time.sleep(0.2)
                    
        except Exception as e:
            print(f"Hata (Film Sayfa {page}): {e}")

    # Çıktılar
    with open("output/movies_all.json", "w", encoding="utf-8") as f:
        json.dump(movies_data, f, ensure_ascii=False, indent=4)
    save_m3u("output/movies_all.m3u", m3u_entries)
    
    return movies_data, m3u_entries

def process_series():
    print(f"--- DİZİLER BAŞLIYOR (Link Kontrollü - Yavaş Olabilir) ---")
    series_data_all = []
    m3u_entries_all = []

    for page in range(1, MAX_PAGES + 1):
        print(f"Dizi Sayfası: {page}/{MAX_PAGES}")
        try:
            url = f"{BASE_URL}/tv/popular?api_key={API_KEY}&language=tr-TR&page={page}"
            data = requests.get(url).json()
            
            for item in data.get('results', []):
                tmdb_id = item['id']
                imdb_id = get_imdb_id(tmdb_id, 'tv')
                
                if imdb_id:
                    raw_name = item['name']
                    file_name = sanitize_filename(raw_name)
                    poster = f"{IMG_URL}{item['poster_path']}" if item.get('poster_path') else ""
                    
                    details_url = f"{BASE_URL}/tv/{tmdb_id}?api_key={API_KEY}"
                    details = requests.get(details_url).json()
                    
                    series_obj = {
                        "id": imdb_id,
                        "name": raw_name,
                        "poster": poster,
                        "episodes": []
                    }
                    
                    series_m3u_local = []
                    has_active_episode = False # Hiç çalışan bölüm var mı?

                    for season in details.get('seasons', []):
                        s_num = season['season_number']
                        ep_count = season['episode_count']
                        
                        if s_num > 0: 
                            for ep in range(1, ep_count + 1):
                                link = f"{VIDMODY_BASE}/{imdb_id}/s{s_num}/e{ep:02d}"
                                
                                # --- KRİTİK NOKTA: Bölüm Kontrolü ---
                                if check_link_active(link):
                                    print(f"  -> [OK] {raw_name} S{s_num} B{ep}")
                                    has_active_episode = True
                                    
                                    series_obj["episodes"].append({
                                        "season": s_num,
                                        "episode": ep,
                                        "link": link
                                    })
                                    
                                    m3u_entry = {
                                        "group": raw_name,
                                        "logo": poster,
                                        "name": f"{raw_name} - S{s_num} B{ep}",
                                        "url": link
                                    }
                                    series_m3u_local.append(m3u_entry)
                                    m3u_entries_all.append(m3u_entry)
                                else:
                                    # Çalışmayan bölümü sessizce atla
                                    pass
                                
                                # Seri isteklerde bekleme (Ban yememek için)
                                time.sleep(0.1)

                    # Eğer dizinin HİÇBİR bölümü sitede yoksa, dosyayı oluşturma!
                    if has_active_episode:
                        with open(f"output/diziler/{file_name}.json", "w", encoding="utf-8") as f:
                            json.dump(series_obj, f, ensure_ascii=False, indent=4)
                        
                        save_m3u(f"output/diziler/{file_name}.m3u", series_m3u_local)
                        series_data_all.append(series_obj)
                    else:
                        print(f"[BOŞ] {raw_name} için aktif bölüm bulunamadı, dosya oluşturulmadı.")
                    
        except Exception as e:
            print(f"Hata (Dizi Sayfa {page}): {e}")

    with open("output/series_all.json", "w", encoding="utf-8") as f:
        json.dump(series_data_all, f, ensure_ascii=False, indent=4)
    save_m3u("output/series_all.m3u", m3u_entries_all)
    
    return series_data_all, m3u_entries_all

if __name__ == "__main__":
    all_movies, movies_m3u = process_movies()
    all_series, series_m3u = process_series()
    
    print("--- GENEL DOSYALAR OLUŞTURULUYOR ---")
    
    full_db = {"movies": all_movies, "series": all_series}
    with open("output/everything.json", "w", encoding="utf-8") as f:
        json.dump(full_db, f, ensure_ascii=False, indent=4)
        
    save_m3u("output/everything.m3u", movies_m3u + series_m3u)
    
    print("BİTTİ. Sadece çalışan linkler kaydedildi.")
