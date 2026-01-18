import requests
import json
import os
import re
import time
import concurrent.futures # <-- HIZ İÇİN EKLENEN SİHİRLİ KÜTÜPHANE

# --- AYARLAR ---
API_KEY = "6fabef7bd74e01efcd81d35c39c4a049"
BASE_URL = "https://api.themoviedb.org/3"
VIDMODY_BASE = "https://vidmody.com/vs"
IMG_URL = "https://image.tmdb.org/t/p/w500"

# Hızlandığı için sayfa sayısını artırabilirsin. Şimdilik 5 kalsın, test et.
MAX_PAGES = 5
# Aynı anda kaç link kontrol edilsin? (Çok artırma, site engelleyebilir)
MAX_WORKERS = 20 

os.makedirs("output/filmler", exist_ok=True)
os.makedirs("output/diziler", exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def check_single_url(url):
    """Tek bir linki kontrol eder (Paralel işlem içinde kullanılır)"""
    try:
        # Timeout süresini kısalttık (2 saniye), cevap vermiyorsa geçsin.
        response = requests.head(url, headers=HEADERS, timeout=2, allow_redirects=True)
        if response.status_code == 200:
            return url
    except:
        pass
    return None

def batch_check_urls(url_list):
    """
    Listeki URL'leri aynı anda (Paralel) kontrol eder.
    Geriye sadece ÇALIŞAN linkleri döndürür.
    """
    valid_urls = set()
    # ThreadPoolExecutor ile aynı anda birden fazla işçi çalıştırıyoruz
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Tüm linkleri işçilere dağıt
        future_to_url = {executor.submit(check_single_url, url): url for url in url_list}
        
        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            if result:
                valid_urls.add(result)
    return valid_urls

def get_imdb_id(tmdb_id, media_type):
    try:
        url = f"{BASE_URL}/{media_type}/{tmdb_id}/external_ids?api_key={API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json().get("imdb_id")
    except:
        return None
    return None

def save_m3u(filename, content_list):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in content_list:
            f.write(f'#EXTINF:-1 group-title="{item["group"]}" tvg-logo="{item["logo"]}", {item["name"]}\n')
            f.write(f'{item["url"]}\n')

def process_movies():
    print(f"--- FİLMLER BAŞLIYOR (Paralel Kontrol: {MAX_WORKERS} Thread) ---")
    movies_data = []
    m3u_entries = []

    for page in range(1, MAX_PAGES + 1):
        print(f"Film Sayfası: {page}/{MAX_PAGES}")
        try:
            url = f"{BASE_URL}/movie/popular?api_key={API_KEY}&language=tr-TR&page={page}"
            data = requests.get(url).json()
            results = data.get('results', [])
            
            # 1. Önce bu sayfadaki tüm filmlerin potansiyel linklerini oluştur
            pending_checks = []
            movie_map = {} # Link -> Film Bilgisi eşleşmesi

            for item in results:
                imdb_id = get_imdb_id(item['id'], 'movie')
                if imdb_id:
                    link = f"{VIDMODY_BASE}/{imdb_id}"
                    pending_checks.append(link)
                    movie_map[link] = {
                        "id": imdb_id,
                        "title": item['title'],
                        "poster": f"{IMG_URL}{item['poster_path']}" if item.get('poster_path') else ""
                    }
            
            # 2. Hepsini TOPLU ve PARALEL kontrol et
            if pending_checks:
                print(f"  -> {len(pending_checks)} film kontrol ediliyor...")
                active_links = batch_check_urls(pending_checks)
                print(f"  -> {len(active_links)} tanesi çalışıyor.")

                # 3. Sadece çalışanları kaydet
                for link in active_links:
                    info = movie_map[link]
                    
                    movies_data.append({
                        "id": info['id'],
                        "title": info['title'],
                        "poster": info['poster'],
                        "link": link
                    })
                    
                    m3u_entries.append({
                        "group": "Filmler",
                        "logo": info['poster'],
                        "name": info['title'],
                        "url": link
                    })

        except Exception as e:
            print(f"Hata (Film Sayfa {page}): {e}")

    with open("output/movies_all.json", "w", encoding="utf-8") as f:
        json.dump(movies_data, f, ensure_ascii=False, indent=4)
    save_m3u("output/movies_all.m3u", m3u_entries)
    
    return movies_data, m3u_entries

def process_series():
    print(f"--- DİZİLER BAŞLIYOR (Paralel Kontrol: {MAX_WORKERS} Thread) ---")
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
                    
                    # 1. Dizinin tüm bölümlerini bir listeye doldur
                    all_episode_links = []
                    episode_info_map = {} # Link -> Bölüm Bilgisi

                    for season in details.get('seasons', []):
                        s_num = season['season_number']
                        ep_count = season['episode_count']
                        if s_num > 0:
                            for ep in range(1, ep_count + 1):
                                link = f"{VIDMODY_BASE}/{imdb_id}/s{s_num}/e{ep:02d}"
                                all_episode_links.append(link)
                                episode_info_map[link] = {"season": s_num, "episode": ep}

                    # 2. Tüm bölümleri PARALEL kontrol et (Hız burada!)
                    if all_episode_links:
                        # print(f"  -> {raw_name}: {len(all_episode_links)} bölüm taranıyor...") 
                        # Çok log basmasın diye kapattım, istersen açabilirsin.
                        active_links = batch_check_urls(all_episode_links)
                        
                        if active_links:
                            print(f"  [OK] {raw_name}: {len(active_links)} aktif bölüm bulundu.")
                            
                            series_obj = {
                                "id": imdb_id,
                                "name": raw_name,
                                "poster": poster,
                                "episodes": []
                            }
                            series_m3u_local = []
                            
                            # Çalışan linkleri sıraya dizerek kaydet (s1e1, s1e2...)
                            # Set sırasız olduğu için tekrar sıralamamız lazım
                            sorted_links = sorted(list(active_links), key=lambda x: (episode_info_map[x]['season'], episode_info_map[x]['episode']))

                            for link in sorted_links:
                                info = episode_info_map[link]
                                
                                series_obj["episodes"].append({
                                    "season": info['season'],
                                    "episode": info['episode'],
                                    "link": link
                                })
                                
                                m3u_entry = {
                                    "group": raw_name,
                                    "logo": poster,
                                    "name": f"{raw_name} - S{info['season']} B{info['episode']}",
                                    "url": link
                                }
                                series_m3u_local.append(m3u_entry)
                                m3u_entries_all.append(m3u_entry)

                            # Dosyaları kaydet
                            with open(f"output/diziler/{file_name}.json", "w", encoding="utf-8") as f:
                                json.dump(series_obj, f, ensure_ascii=False, indent=4)
                            save_m3u(f"output/diziler/{file_name}.m3u", series_m3u_local)
                            
                            series_data_all.append(series_obj)
                        else:
                            # Hiçbir bölüm çalışmıyorsa
                            print(f"  [X] {raw_name}: Hiçbir bölüm aktif değil.")

        except Exception as e:
            print(f"Hata (Dizi Sayfa {page}): {e}")

    with open("output/series_all.json", "w", encoding="utf-8") as f:
        json.dump(series_data_all, f, ensure_ascii=False, indent=4)
    save_m3u("output/series_all.m3u", m3u_entries_all)
    
    return series_data_all, m3u_entries_all

if __name__ == "__main__":
    start_time = time.time()
    
    all_movies, movies_m3u = process_movies()
    all_series, series_m3u = process_series()
    
    print("--- GENEL DOSYALAR OLUŞTURULUYOR ---")
    
    full_db = {"movies": all_movies, "series": all_series}
    with open("output/everything.json", "w", encoding="utf-8") as f:
        json.dump(full_db, f, ensure_ascii=False, indent=4)
        
    save_m3u("output/everything.m3u", movies_m3u + series_m3u)
    
    end_time = time.time()
    print(f"BİTTİ. Toplam Süre: {int(end_time - start_time)} saniye.")
