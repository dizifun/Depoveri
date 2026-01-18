import requests
from bs4 import BeautifulSoup
import json
import os
import re
from tqdm import tqdm
import time
from datetime import datetime

# --- AYARLAR ---
BASE_URL = "https://www.nowtv.com.tr"
ROOT_DIR = "now"
DIRS = {
    "series": os.path.join(ROOT_DIR, "dizi"),
    "programs": os.path.join(ROOT_DIR, "program")
}

# --- TARAYICI AYARLARI ---
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": BASE_URL,
    "Origin": BASE_URL
})

def get_real_stream_url(episode_url):
    if not episode_url: return ""
    full_url = episode_url if episode_url.startswith("http") else BASE_URL + episode_url
    try:
        r = session.get(full_url, timeout=10)
        match = re.search(r"source:\s*['\"](https:\/\/[^'\"]*?\.m3u8[^'\"]*?)['\"]", r.text)
        return match.group(1) if match else ""
    except: return ""

def get_episodes(program_id, show_name):
    url = f"{BASE_URL}/ajax/videos"
    episode_list = []
    payload = {'filter': 'season', 'season': 1, 'program_id': program_id, 'page': 0, 'type': '2', 'count': '50', 'orderBy': 'id', 'sorting': 'asc'}

    if 'X-CSRF-TOKEN' not in session.headers:
        try:
            r = session.get(BASE_URL)
            meta = re.search(r'name="csrf-token"\s+content="([^"]+)"', r.text)
            if meta: session.headers['X-CSRF-TOKEN'] = meta.group(1)
        except: pass

    while payload['season'] < 15:
        try:
            r = session.post(url, data=payload, timeout=10)
            try: resp = r.json()
            except: break 

            html = resp.get('data', '')
            if not html:
                if payload['page'] == 0: payload['season'] += 1; continue
                else: payload['season'] += 1; payload['page'] = 0; continue

            soup = BeautifulSoup(html, 'html.parser')
            items = soup.find_all("div", {"class": "list-item"})
            if not items: payload['season'] += 1; payload['page'] = 0; continue

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

                    episode_list.append({"name": full_name, "img": img_url, "url": page_url, "stream_url": stream_url})
                except: continue

            if len(items) < int(payload['count']): payload['season'] += 1; payload['page'] = 0
            else: payload['page'] += 1
        except: break
    return episode_list

def extract_id_from_img(img_url):
    if not img_url: return None
    match = re.search(r'/(?:thumbnail|program|smart-crop)/(\d+)', img_url)
    if match: return match.group(1)
    return None

def collect_items_from_page(url):
    print(f"🌍 Taranıyor: {url}")
    found = []
    seen_ids = set()
    try:
        r = session.get(url, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        links = soup.find_all("a", href=True)
        for link in links:
            href = link['href']
            if any(x in href for x in ["/giris", "/uye-ol", "facebook", "twitter", "instagram", "javascript"]): continue
            img = link.find("img")
            if not img: continue
            img_src = img.get('data-src') or img.get('src')
            if not img_src: continue
            pid = extract_id_from_img(img_src)
            if not pid or pid in seen_ids: continue
            title = img.get('alt') or link.get('title') or link.text.strip()
            if not title: continue
            seen_ids.add(pid)
            found.append({"id": pid, "name": title, "img": img_src, "url": BASE_URL + href if not href.startswith("http") else href})
    except Exception as e: print(f"❌ Hata: {e}")
    return found

def main():
    for d in DIRS.values(): os.makedirs(d, exist_ok=True)
    targets = [
        {"url": f"{BASE_URL}/dizi-arsivi", "type": "series"},
        {"url": f"{BASE_URL}/program-izle", "type": "programs"},
        {"url": f"{BASE_URL}/program-arsivi", "type": "programs"}
    ]
    all_data = {"series": [], "programs": []}

    for t in targets:
        items = collect_items_from_page(t['url'])
        print(f"✅ {len(items)} içerik bulundu. Bölümler çekiliyor...")
        for item in tqdm(items):
            episodes = get_episodes(item['id'], item['name'])
            if episodes:
                show_data = {"id": item['id'], "name": item['name'], "img": item['img'], "episodes": episodes}
                slug = re.sub(r'[^a-z0-9-]', '', item['name'].lower().replace(" ", "-").replace("ç","c").replace("ğ","g").replace("ı","i").replace("ö","o").replace("ş","s").replace("ü","u"))
                target_dir = DIRS["series"] if t['type'] == "series" else DIRS["programs"]
                with open(os.path.join(target_dir, f"{slug}.json"), "w", encoding="utf-8") as f: json.dump(show_data, f, ensure_ascii=False, indent=4)
                try:
                    with open(os.path.join(target_dir, f"{slug}.m3u"), "w", encoding="utf-8") as f:
                        f.write("#EXTM3U\n")
                        for ep in episodes: f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}",{ep["name"]}\n{ep["stream_url"]}\n')
                except: pass
                all_data[t['type']].append(show_data)

    print("\n📦 Ana Dosyalar oluşturuluyor...")
    with open(os.path.join(ROOT_DIR, "now-diziler.json"), "w", encoding="utf-8") as f: json.dump(all_data["series"], f, ensure_ascii=False, indent=4)
    with open(os.path.join(ROOT_DIR, "now-diziler.m3u"), "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for show in all_data["series"]:
             for ep in show.get("episodes", []): f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}" group-title="{show["name"]}",{ep["name"]}\n{ep["stream_url"]}\n')

    with open(os.path.join(ROOT_DIR, "now-programlar.json"), "w", encoding="utf-8") as f: json.dump(all_data["programs"], f, ensure_ascii=False, indent=4)
    with open(os.path.join(ROOT_DIR, "now-programlar.m3u"), "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for show in all_data["programs"]:
             for ep in show.get("episodes", []): f.write(f'#EXTINF:-1 tvg-logo="{ep["img"]}" group-title="{show["name"]}",{ep["name"]}\n{ep["stream_url"]}\n')

    # --- OTOMATİK GITHUB GÖNDERİMİ (ZORLANMIŞ) ---
    print("\n🚀 GitHub'a yükleniyor (Otomatik)...")
    try:
        # Önce 'now' klasörünü zorla ekle
        os.system("git add now/") 
        # Sonra diğer her şeyi ekle
        os.system("git add .")
        
        tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
        # Commit mesajı
        os.system(f'git commit -m "İçerik güncellemesi: {tarih}"')
        
        # Gönder
        push_result = os.system("git push")
        
        if push_result == 0:
            print("✅ BAŞARILI: Veriler GitHub'a yüklendi!")
        else:
            print("⚠️ UYARI: Push işlemi bir hata kodu döndürdü. Bağlantıyı kontrol et.")
            
    except Exception as e:
        print(f"❌ Git hatası: {e}")

if __name__ == "__main__":
    main()

