import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
import json
import sys
import re
import os

# --- AYARLAR ---
# Utilities klasörünün yolu (Senin yapına göre)
sys.path.insert(0, '../../utilities')

# Eğer jsontom3u kütüphanesi yoksa hata vermemesi için dummy fonksiyonlar (Test için)
try:
    from jsontom3u import create_single_m3u, create_m3us
except ImportError:
    def create_single_m3u(path, data, name): pass
    def create_m3us(path, data): pass

base_url = "https://www.startv.com.tr"
img_base_url = "https://media.startv.com.tr/star-tv"
base_output_path = "../../lists/video/sources/startv"

# Kategoriler ve Linkleri
categories = {
    "dizi": "https://www.startv.com.tr/dizi",
    "program": "https://www.startv.com.tr/program"
}

# Next.js Veri Regexi
episode_pattern = re.compile(r'referenceId\\":\\"(.*?)\\",.*?title\\":\\"(.*?)\\"', re.DOTALL)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def get_items_page(url):
    item_list = []
    try:
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.content, "html.parser")
        items = soup.find_all("div", class_="poster-card")
        
        for item in items:
            try:
                link_tag = item.find("a")
                if not link_tag: continue
                
                item_href = link_tag.get("href")
                item_url = base_url + item_href
                # Slug'ı URL'den alıyoruz (örn: /dizi/yali-capkini -> yali-capkini)
                item_slug = item_href.strip("/").split("/")[-1]

                img_tag = item.find("img")
                if img_tag:
                    item_img = img_tag.get("src")
                    item_name = img_tag.get("alt") or img_tag.get("title") or item_slug
                else:
                    item_img = ""
                    item_name = item_slug

                temp_item = {
                    "name": item_name.strip(), 
                    "slug": item_slug,
                    "img": item_img,
                    "url": item_url
                }
                item_list.append(temp_item)
            except:
                continue
    except Exception as e:
        print(f"Hata ({url}): {e}")
    return item_list

def get_episodes(url):
    episode_list = []
    target_url = url + "/bolumler" if not url.endswith("/bolumler") else url
    
    try:
        r = requests.get(target_url, headers=headers)
        matches = episode_pattern.findall(r.text)
        seen_ids = set()

        for ref_id, title in matches:
            if ref_id in seen_ids: continue
            seen_ids.add(ref_id)
            
            try:
                clean_title = title.encode('utf-8').decode('unicode_escape')
            except:
                clean_title = title
            
            stream_url = "https://dygvideo.dygdigital.com/api/redirect?PublisherId=1&ReferenceId=StarTV_{}&SecretKey=NtvApiSecret2014*&.m3u8".format(ref_id)
            
            episode_list.append({
                "name": clean_title,
                "stream_url": stream_url,
                "img": ""
            })
    except:
        pass
    return episode_list

def main():
    print("--- Star TV Tarayıcı Başlatılıyor ---")

    # Her kategori için döngü (Dizi ve Program)
    for cat_name, cat_url in categories.items():
        print(f"\nKategori İşleniyor: {cat_name.upper()}")
        
        # 1. Ana liste çekiliyor
        items = get_items_page(cat_url)
        print(f"  > {len(items)} içerik bulundu.")
        
        # Kategori için ana veri listesi
        category_data = []

        # Kategori klasörü oluşturuluyor (örn: .../startv/dizi)
        cat_folder = os.path.join(base_output_path, cat_name)
        os.makedirs(cat_folder, exist_ok=True)

        for show in tqdm(items):
            # Bölümleri çek
            episodes = get_episodes(show["url"])
            
            # Show objesine bölümleri ekle
            show_data = show.copy()
            show_data["episodes"] = episodes
            
            # --- 2. TEKİL DOSYA KAYDETME ---
            # Her dizi/program için kendi json ve m3u dosyasını oluştur
            # Dosya adı slug olacak (örn: yali-capkini.json)
            if episodes:
                # Bireysel JSON
                json_path = os.path.join(cat_folder, f"{show['slug']}.json")
                with open(json_path, "w+", encoding='utf-8') as f:
                    json.dump([show_data], f, ensure_ascii=False, indent=4)
                
                # Bireysel M3U (jsontom3u kütüphanesi kullanarak)
                # create_single_m3u genelde bir liste bekler, bu yüzden [show_data] gönderiyoruz
                create_single_m3u(cat_folder, [show_data], show['slug'])
            
            # Ana listeye ekle
            category_data.append(show_data)

        # --- 3. TOPLU DOSYA KAYDETME (Kategori Bazlı) ---
        # startv/dizi.json ve startv/dizi.m3u oluşturur
        if category_data:
            # Toplu JSON
            master_json_path = os.path.join(base_output_path, f"{cat_name}.json")
            with open(master_json_path, "w+", encoding='utf-8') as f:
                json.dump(category_data, f, ensure_ascii=False, indent=4)
            
            # Toplu M3U
            create_single_m3u(base_output_path, category_data, cat_name)

    print("\nİşlem Tamamlandı.")

if __name__=="__main__": 
    main()