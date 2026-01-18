import os

def create_single_m3u(path, data, name):
    """
    Tüm içerikleri tek bir M3U dosyasında toplar.
    Örn: KanalD/arsiv-diziler.m3u
    """
    if not os.path.exists(path):
        os.makedirs(path)
        
    m3u_content = "#EXTM3U\n"
    
    for category in data:
        cat_name = category.get("name", "Genel")
        for episode in category.get("episodes", []):
            title = episode.get("name", "Bilinmeyen")
            url = episode.get("stream_url", "")
            img = episode.get("img", "")
            
            if url and url.strip() != "":
                m3u_content += f'#EXTINF:-1 group-title="{cat_name}" tvg-logo="{img}",{title}\n'
                m3u_content += f"{url}\n"

    filename = os.path.join(path, f"{name}.m3u")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(m3u_content)

def create_m3us(base_path, data):
    """
    Her dizi/program için ayrı klasör ve içinde playlist.m3u oluşturur.
    Örn: KanalD/arsiv-diziler/Arka Sokaklar/playlist.m3u
    """
    if not os.path.exists(base_path):
        os.makedirs(base_path)

    for serie in data:
        serie_name = serie.get("name", "Bilinmeyen").replace("/", "-").replace(":", "")
        serie_path = os.path.join(base_path, serie_name)
        
        if not os.path.exists(serie_path):
            os.makedirs(serie_path)
            
        m3u_content = "#EXTM3U\n"
        for episode in serie.get("episodes", []):
            title = episode.get("name", "Bölüm")
            url = episode.get("stream_url", "")
            img = episode.get("img", "")
            
            if url and url.strip() != "":
                m3u_content += f'#EXTINF:-1 tvg-logo="{img}",{title}\n'
                m3u_content += f"{url}\n"
        
        with open(os.path.join(serie_path, "playlist.m3u"), "w", encoding="utf-8") as f:
            f.write(m3u_content)
