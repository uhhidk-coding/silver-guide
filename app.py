import os
import time
import requests
from datetime import datetime
from threading import Thread
from urllib.parse import urljoin, quote, unquote
from flask import Flask, Response, render_template_string, request
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By

app = Flask(__name__)

# ====================================================================
# CONFIGURATION
# ====================================================================
TARGET_WEBPAGE = "https://a1.koora24.sbs/read/63/%D8%B1%D9%8A%D8%A7%D9%86-%D8%B4%D8%B1%D9%82%D9%8A-%D9%85%D9%81%D8%AA%D8%A7%D8%AD-%D8%BA%D9%88%D8%A7%D8%B1%D8%AF%D9%8A%D9%88%D9%84%D8%A7-%D9%84%D8%AD%D8%B3%D9%85-%D9%84%D9%82%D8%A8"
# ====================================================================

DESKTOP_FOLDER = os.path.join(os.path.expanduser("~"), "Desktop", "stream")
LOG_FILE_PATH = os.path.join(DESKTOP_FOLDER, "stream_history.log")

if not os.path.exists(DESKTOP_FOLDER):
    os.makedirs(DESKTOP_FOLDER)

LIVE_STREAM_URL = ""

def log_token_to_file(url):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] Found Target: {url}\n")
    except Exception as e:
        print(f"[-] Failed writing to history file: {e}")

def stream_scraper_loop():
    global LIVE_STREAM_URL
    print(f"[*] Background Scraper Active. Logging trail to: {LOG_FILE_PATH}")
    options = Options()
    options.add_argument("--headless")
    
    while True:
        driver = None
        try:
            driver = webdriver.Firefox(options=options)
            driver.get(TARGET_WEBPAGE)
            time.sleep(15)
            
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                driver.switch_to.frame(iframes[0])
                time.sleep(5)

            resources = driver.execute_script("return window.performance.getEntriesByType('resource');")
            for resource in resources:
                url = resource.get('name', '')
                if "max2.m3u8" in url:
                    if url != LIVE_STREAM_URL: 
                        LIVE_STREAM_URL = url
                        print(f"[+] Scraper caught stream: {LIVE_STREAM_URL}")
                        log_token_to_file(url)
                    break
        except Exception as e:
            print(f"[-] Scraper routine cycle notice: {e}")
        finally:
            if driver:
                driver.quit()
        time.sleep(60) 

@app.route('/')
def live_player():
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>jstream hd</title>
            <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
            <style>
                body { background: #0f0f0f; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: white; font-family: sans-serif; }
                .container { text-align: center; width: 90%; max-width: 850px; }
                video { width: 100%; border-radius: 8px; border: 2px solid #333; background: #000; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
                #status { color: #ffaa00; margin-top: 15px; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>jstream hd</h2>
                <video id="video" controls autoplay></video>
                <div id="status">⏳ Instantiating stream...</div>
            </div>
            <script>
                var video = document.getElementById('video');
                var statusText = document.getElementById('status');
                var hls;

                function loadStream() {
                    if (Hls.isSupported()) {
                        hls = new Hls();
                        hls.loadSource('/max2.m3u8'); 
                        hls.attachMedia(video);
                        hls.on(Hls.Events.MANIFEST_PARSED, () => {
                            statusText.innerText = "🟢 Connected";
                            video.muted = true;
                            video.play().catch(e => statusText.innerText = "⚠️ Click video to play");
                        });
                    }
                }
                loadStream();
            </script>
        </body>
        </html>
    ''')

@app.route('/max2.m3u8')
def master_playlist():
    if not LIVE_STREAM_URL:
        return "Not found yet", 404
    return rewrite_m3u8(LIVE_STREAM_URL)

@app.route('/proxy')
def proxy_handler():
    target_url = unquote(request.args.get('url', ''))
    if not target_url: return "Missing URL", 400
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://a1.koora24.sbs/"}
    try:
        res = requests.get(target_url, headers=headers, timeout=10)
        return Response(res.content, status=res.status_code, headers={
            "Access-Control-Allow-Origin": "*",
            "Content-Type": res.headers.get('Content-Type', 'application/octet-stream')
        })
    except Exception as e: return str(e), 500

def rewrite_m3u8(url):
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://a1.koora24.sbs/"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        base_url = url.rsplit('/', 1)[0] + '/'
        lines = []
        for line in res.text.splitlines():
            line = line.strip()
            if not line: continue
            
            if line.startswith('#EXT-X-KEY:'):
                # Ensure the URI inside the tag is proxied
                if 'URI="' in line:
                    start = line.find('URI="') + 5
                    end = line.find('"', start)
                    old_uri = line[start:end]
                    abs_uri = urljoin(base_url, old_uri)
                    line = line.replace(old_uri, f"/proxy?url={quote(abs_uri)}")
                lines.append(line)
            elif line.startswith('#'):
                lines.append(line)
            else:
                abs_url = urljoin(base_url, line)
                lines.append(f"/proxy?url={quote(abs_url)}")
        
        return Response("\n".join(lines), content_type='application/x-mpegURL', headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        return f"Error: {e}", 500

if __name__ == '__main__':
    Thread(target=stream_scraper_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False)import os
import time
import re
import requests
from threading import Thread
from flask import Flask, Response, render_template_string

app = Flask(__name__)

# Global variable for the stream
LIVE_STREAM_URL = ""

def stream_scraper_loop():
    global LIVE_STREAM_URL
    # Get the URL from Render Environment Variables
    target_webpage = os.environ.get("TARGET_URL", "").strip()
    
    if not target_webpage:
        print("[-] No TARGET_URL set in environment variables.")
        return

    print(f"[*] Scraper initialized for: {target_webpage}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://koora24.sbs/",
    }
    
    session = requests.Session()
    
    while True:
        try:
            response = session.get(target_webpage, headers=headers, timeout=15)
            iframe_srcs = re.findall(r'<iframe\s+[^>]*src="([^"]+)"', response.text, re.IGNORECASE)
            
            if iframe_srcs:
                iframe_url = iframe_srcs[0]
                if iframe_url.startswith('//'): iframe_url = 'https:' + iframe_url
                
                iframe_headers = headers.copy()
                iframe_headers["Referer"] = target_webpage
                
                iframe_response = session.get(iframe_url, headers=iframe_headers, timeout=15)
                m3u8_matches = re.findall(r'(https://[^\s"\']+\.m3u8[^\s"\']*)', iframe_response.text)
                
                if m3u8_matches and m3u8_matches[0] != LIVE_STREAM_URL:
                    LIVE_STREAM_URL = m3u8_matches[0]
                    print(f"\n[+] Master link updated: {LIVE_STREAM_URL}")
        except Exception as e:
            print(f"[-] Scraper cycle notice: {e}")
        time.sleep(30)

@app.route('/')
def live_player():
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <body style="background:#000; color:#fff; display:flex; justify-content:center; align-items:center; height:100vh; margin:0;">
            <div style="text-align:center;">
                <h2>jstream hd</h2>
                <video id="video" controls autoplay style="width:80vw; max-width:800px;"></video>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
            <script>
                var video = document.getElementById('video');
                var hls = new Hls();
                hls.loadSource('/master.m3u8');
                hls.attachMedia(video);
                hls.on(Hls.Events.MANIFEST_PARSED, () => video.play());
            </script>
        </body>
        </html>
    ''')

@app.route('/master.m3u8')
def master_playlist():
    if not LIVE_STREAM_URL: return "Not found yet", 404
    return rewrite_m3u8(LIVE_STREAM_URL)

@app.route('/proxy')
def proxy_handler():
    target_url = request.args.get('url', '')
    target_webpage = os.environ.get("TARGET_URL", "")
    try:
        res = requests.get(target_url, headers={"Referer": target_webpage}, timeout=10)
        return Response(res.content, content_type=res.headers.get('Content-Type'))
    except: return "Proxy Error", 500

def rewrite_m3u8(url):
    target_webpage = os.environ.get("TARGET_URL", "")
    res = requests.get(url, headers={"Referer": target_webpage}, timeout=10)
    base = url.rsplit('/', 1)[0] + '/'
    lines = res.text.replace(base, "/proxy?url=" + base)
    return Response(lines, content_type='application/x-mpegURL')

if __name__ == '__main__':
    Thread(target=stream_scraper_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
