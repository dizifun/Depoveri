import requests
import json
import os
import re # Dosya isimlerini düzeltmek için
import time

# --- AYARLAR ---
API_KEY = "6fabef7bd74e01efcd81d35c39c4a049"
BASE_URL = "https://api.themoviedb.org/3"
VIDMODY_BASE = "https://vidmody.com/vs"
IMG_URL = "https://image.tmdb.org/t/p/w500"

# 10.000 içerik için (500 sayfa x 20 = 10.000)
MAX_PAGES = 500

# Klasörleri oluştur
os.makedirs("output/filmler", exist_ok=True)
os.makedirs("output/diziler", exist_ok=True)

def sanitize_filename(name):
    """
    Dosya ismindeki yasaklı karakterleri temizler.
    Örn: 'Face/Off' -> 'FaceOff'
    """
    # Windows/Linux dosya sisteminde yasaklı karakterleri siler
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def get_imdb_id(tmdb_id, media_type):
    """TMDB ID'den IMDb ID'yi bulur"""
    try:
        url = f"{BASE_URL}/{media_type}/{tmdb_id}/external_ids?api_key={API_KEY}"
        # Hata almamak için kısa bir bekleme (opsiyonel)
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json().get("imdb_id")
    except:
        return None
    return None

def save_m3u(filename, content_list):
    """M3U listesi oluşturur"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in content_list:
            f.write(f'#EXTINF:-1 group-title="{item["group"]}" tvg-logo="{item["logo"]}", {item["name"]}\n')
            f.write(f'{item["url"]}\n')

def process_movies():
    print("--- FİLMLER BAŞLIYOR (Hedef: 10.000) ---")
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
                    title = item['title']
                    link = f"{VIDMODY_BASE}/{imdb_id}"
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
        except Exception as e:
            print(f"Hata (Film Sayfa {page}): {e}")

    # Film Çıktıları
    with open("output/movies_all.json", "w", encoding="utf-8") as f:
        json.dump(movies_data, f, ensure_ascii=False, indent=4)
    
    save_m3u("output/movies_all.m3u", m3u_entries)
    
    return movies_data, m3u_entries

def process_series():
    print("--- DİZİLER BAŞLIYOR (İsim Bazlı) ---")
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
                    # İsimdeki yasaklı karakterleri temizle
                    file_name = sanitize_filename(raw_name) 
                    poster = f"{IMG_URL}{item['poster_path']}" if item.get('poster_path') else ""
                    
                    # Dizi detaylarını (sezonlar) çek
                    details_url = f"{BASE_URL}/tv/{tmdb_id}?api_key={API_KEY}"
                    details = requests.get(details_url).json()
                    
                    series_obj = {
                        "id": imdb_id,
                        "name": raw_name,
                        "poster": poster,
                        "episodes": []
                    }
                    
                    series_m3u_local = []

                    # Sezonları dön
                    for season in details.get('seasons', []):
                        s_num = season['season_number']
                        ep_count = season['episode_count']
                        
                        if s_num > 0: # 0. sezonu atla
                            for ep in range(1, ep_count + 1):
                                # s1/e07 formatı
                                link = f"{VIDMODY_BASE}/{imdb_id}/s{s_num}/e{ep:02d}"
                                
                                # JSON verisi
                                series_obj["episodes"].append({
                                    "season": s_num,
                                    "episode": ep,
                                    "link": link
                                })
                                
                                # M3U verisi
                                m3u_entry = {
                                    "group": raw_name,
                                    "logo": poster,
                                    "name": f"{raw_name} - S{s_num} B{ep}",
                                    "url": link
                                }
                                series_m3u_local.append(m3u_entry)
                                m3u_entries_all.append(m3u_entry)

                    # --- DİZİ İÇİN ÖZEL DOSYALAR (İSMİYLE) ---
                    # Örn: output/diziler/Breaking Bad.json
                    with open(f"output/diziler/{file_name}.json", "w", encoding="utf-8") as f:
                        json.dump(series_obj, f, ensure_ascii=False, indent=4)
                    
                    # Örn: output/diziler/Breaking Bad.m3u
                    save_m3u(f"output/diziler/{file_name}.m3u", series_m3u_local)

                    series_data_all.append(series_obj)
                    
        except Exception as e:
            print(f"Hata (Dizi Sayfa {page}): {e}")

    # Toplu Dizi Dosyaları
    with open("output/series_all.json", "w", encoding="utf-8") as f:
        json.dump(series_data_all, f, ensure_ascii=False, indent=4)
        
    save_m3u("output/series_all.m3u", m3u_entries_all)
    
    return series_data_all, m3u_entries_all

if __name__ == "__main__":
    all_movies, movies_m3u = process_movies()
    all_series, series_m3u = process_series()
    
    print("--- GENEL TOPLU DOSYALAR YAZILIYOR ---")
    
    # Her şeyin olduğu tek JSON
    full_db = {"movies": all_movies, "series": all_series}
    with open("output/everything.json", "w", encoding="utf-8") as f:
        json.dump(full_db, f, ensure_ascii=False, indent=4)
        
    # Her şeyin olduğu tek M3U
    save_m3u("output/everything.m3u", movies_m3u + series_m3u)
    
    print("BİTTİ.")
