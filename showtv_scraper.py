import requests
from bs4 import BeautifulSoup
import json
import os
import time
from tqdm import tqdm

# --- AYARLAR ---
BASE_URL = "https://www.showtv.com.tr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Klasör Ayarları
DIRS = {
    "root": "showtv",
    "dizi": "showtv/dizi",
    "program": "showtv/program"
}

# Klasörleri oluştur
for d in DIRS.values():
    os.makedirs(d, exist_ok=True)

# --- M3U VE JSON KAYDETME FONKSİYONLARI ---
def save_json(file_path, data):
    """JSON kaydeder."""
    if not file_path.endswith(".json"): file_path += ".json"
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        # print(f"    [OK] JSON Kaydedildi: {file_path}")
    except Exception as e:
        print(f"    [HATA] JSON Kaydedilemedi: {e}")

def create_m3u(file_path, data_list, is_single=False):
    """M3U dosyası oluşturur."""
    if not file_path.endswith(".m3u"): file_path += ".m3u"
    
    content = "#EXTM3U\n"
    items = data_list if isinstance(data_list, list) else [data_list]
    
    for item in items:
        group_title = item.get("name", "Show TV")
        for episode in item.get("episodes", []):
            name = episode.get("name", "Bilinmeyen Bölüm")
            img = episode.get("img", "")
            url = episode.get("stream_url", "")
            
            if url:
                content += f'#EXTINF:-1 tvg-logo="{img}" group-title="{group_title}", {name}\n'
                content += f'{url}\n'
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"    [HATA] M3U Kaydedilemedi: {e}")

# --- İÇERİK ÇEKME FONKSİYONLARI ---
def get_soup(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return BeautifulSoup(r.content, "html.parser")
    except Exception as e:
        # print(f"    URL Erişim Hatası ({url}): {e}")
        return None

def get_video_source(url):
    """Player içindeki data-hope-video json verisinden m3u8 çeker."""
    soup = get_soup(url)
    if not soup: return None
    
    try:
        player_div = soup.find("div", attrs={"data-hope-video": True})
        if player_div:
            video_data = json.loads(player_div.get("data-hope-video"))
            # M3U8 linkini al
            if "media" in video_data and "m3u8" in video_data["media"]:
                return video_data["media"]["m3u8"][0]["src"]
    except:
        pass
    return None

def get_episodes_from_json_ld(soup):
    """JSON-LD verisinden bölümleri çeker."""
    episode_list = []
    try:
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            if not script.string: continue
            try:
                data = json.loads(script.string)
                if data.get("@type") == "ItemList" and "itemListElement" in data:
                    for item in data["itemListElement"]:
                        url = item["url"]
                        if not url.startswith("http"): url = BASE_URL + url
                        episode_list.append({"url": url})
            except: continue
    except: pass
    return episode_list

def process_category(category_name, category_url, output_folder, link_pattern):
    """
    Belirtilen kategoriyi tarar.
    link_pattern: Linklerin içinde geçen kelime (örn: '/dizi/tanitim' veya '/programlar/tanitim')
    """
    print(f"\n>>> {category_name.upper()} TARANIYOR...")
    soup = get_soup(category_url)
    if not soup: return []

    items_data = []
    seen_urls = set() # Tekrar eden linkleri engellemek için

    # Sayfadaki TÜM linkleri bul ve filtrele
    all_links = soup.find_all("a", href=True)
    target_links = []
    
    for link in all_links:
        href = link.get("href")
        # Eğer link pattern'e uyuyorsa ve daha önce eklenmediyse
        if link_pattern in href and href not in seen_urls:
            # Görseli bulmaya çalış (Linkin içinde img var mı?)
            img_tag = link.find("img")
            if not img_tag:
                # Bazen a etiketi img'yi kapsamaz, ebeveynine bakılır ama ShowTV yapısında genelde kapsar.
                # Kapsamıyorsa o linki atlayabiliriz ya da resimsiz ekleriz.
                continue 
            
            # Başlık bulma
            title = link.get("title")
            if not title and img_tag: title = img_tag.get("alt")
            
            # Resim Linki
            img_src = img_tag.get("data-src") or img_tag.get("src") or ""
            if "transparent" in img_src and img_tag.get("data-src"):
                img_src = img_tag.get("data-src")

            full_url = BASE_URL + href if not href.startswith("http") else href
            
            target_links.append({
                "name": title if title else "Bilinmiyor",
                "url": full_url,
                "img": img_src
            })
            seen_urls.add(href)

    print(f"   {len(target_links)} adet {category_name} bulundu.")

    # Bulunan içerikleri işle
    for item in tqdm(target_links, desc=f"{category_name} İşleniyor"):
        try:
            main_item = {
                "name": item["name"],
                "img": item["img"],
                "url": item["url"],
                "episodes": []
            }

            # Detay Sayfasına Git
            detail_soup = get_soup(main_item["url"])
            if detail_soup:
                # Bölümleri çek (Son 30 bölüm limiti - GitHub süresi için)
                raw_episodes = get_episodes_from_json_ld(detail_soup)[:30]
                
                for ep in raw_episodes:
                    stream_url = get_video_source(ep["url"])
                    if stream_url:
                        # Bölüm ismini URL'den temizle
                        slug = ep['url'].split('/')[-2].replace('-', ' ').title()
                        ep_name = f"{main_item['name']} - {slug}"
                        
                        main_item["episodes"].append({
                            "name": ep_name,
                            "img": main_item["img"],
                            "stream_url": stream_url
                        })
            
            # Eğer bölüm bulunduysa kaydet
            if main_item["episodes"]:
                # Dosya ismi oluştur
                safe_filename = main_item["url"].split("/")[-2]
                if safe_filename.isdigit(): safe_filename = main_item["url"].split("/")[-3]
                
                # Bireysel Kayıtlar
                save_json(os.path.join(output_folder, safe_filename), main_item)
                create_m3u(os.path.join(output_folder, safe_filename), main_item, is_single=True)
                
                items_data.append(main_item)

        except Exception as e:
            # print(f"   Hata ({item['name']}): {e}")
            continue

    return items_data

def main():
    # 1. DİZİLERİ TARA
    # Link içinde '/dizi/tanitim' geçenleri bulur
    dizi_data = process_category("Diziler", f"{BASE_URL}/diziler", DIRS["dizi"], "/dizi/tanitim")
    
    # Dizi Ana Dosyalarını HEMEN Kaydet (Programlarda hata olsa bile bunlar garanti olsun)
    if dizi_data:
        print("   > Ana Dizi Dosyaları Kaydediliyor...")
        save_json(f"{DIRS['root']}/showtv_diziler", dizi_data)
        create_m3u(f"{DIRS['root']}/showtv_diziler", dizi_data) # create_general_m3u yerine create_m3u kullanıyoruz artık

    # 2. PROGRAMLARI TARA
    # Link içinde '/programlar/tanitim' geçenleri bulur (box-type ne olursa olsun yakalar)
    program_data = process_category("Programlar", f"{BASE_URL}/programlar", DIRS["program"], "/programlar/tanitim")
    
    # Program Ana Dosyalarını Kaydet
    if program_data:
        print("   > Ana Program Dosyaları Kaydediliyor...")
        save_json(f"{DIRS['root']}/showtv_programlar", program_data)
        create_m3u(f"{DIRS['root']}/showtv_programlar", program_data)

    print("\n>>> TÜM İŞLEMLER TAMAMLANDI.")

if __name__ == "__main__":
    main()
