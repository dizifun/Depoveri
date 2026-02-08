import asyncio
import re
from playwright.async_api import async_playwright

# Hedef URL (Senin verdiğin örnek)
# Not: ID dinamik olarak değiştirilebilir.
BASE_URL = "https://vidsrc-embed.ru/embed/movie?imdb=tt18382850"

async def get_stream_link():
    async with async_playwright() as p:
        # Tarayıcıyı başlat (headless=True arka planda çalışır, False yaparsan tarayıcıyı görürsün)
        browser = await p.chromium.launch(headless=True)
        
        # Mobil cihaz taklidi yapmak bazen daha temiz linkler verir
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = await context.new_page()

        print(f"Siteye gidiliyor: {BASE_URL}")

        # M3U8 linklerini yakalamak için bir değişken
        found_streams = []

        # Ağ trafiğini dinle (Network Interception)
        page.on("request", lambda request: check_request(request, found_streams))

        try:
            # Sayfaya git ve yüklenmesini bekle
            await page.goto(BASE_URL, timeout=60000)
            
            # Sayfa içinde videonun tetiklenmesi için tıklama gerekebilir
            # Çoğu embed player'da "Play" butonuna basmak gerekir
            # Burada iframe veya play butonunu bulup tıklatmayı deneyebiliriz:
            try:
                # Örnek: Play butonuna tıkla (Seçici siteye göre değişebilir)
                await page.click("div#player", timeout=5000) 
            except:
                print("Otomatik oynatma veya play butonu bulunamadı, trafik dinleniyor...")

            # Videonun yüklenmesi ve m3u8 isteğinin ağa düşmesi için biraz bekle
            await page.wait_for_timeout(10000) 

        except Exception as e:
            print(f"Bir hata oluştu: {e}")
        
        finally:
            await browser.close()

        return found_streams

def check_request(request, streams_list):
    # Eğer istek URL'si .m3u8 içeriyorsa listeye ekle
    if ".m3u8" in request.url:
        print(f"[YAKALANDI] {request.url}")
        streams_list.append(request.url)

if __name__ == "__main__":
    links = asyncio.run(get_stream_link())
    
    print("\n--- SONUÇLAR ---")
    if links:
        print("Bulunan M3U8 Linkleri:")
        for link in links:
            print(link)
            # İstersen burada linki bir dosyaya kaydedebilirsin
            with open("streams.txt", "a") as f:
                f.write(f"{link}\n")
    else:
        print("M3U8 linki yakalanamadı. Site koruması tarayıcıyı algılamış olabilir.")
