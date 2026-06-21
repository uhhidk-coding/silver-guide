import os
import time
import socket
import re
import requests
from datetime import datetime
from threading import Thread
from urllib.parse import urljoin, quote, unquote
from flask import Flask, Response, render_template_string, request, redirect, url_for

app = Flask(__name__)

# Global variables controlled dynamically via the UI
TARGET_WEBPAGE = ""
LIVE_STREAM_URL = ""

DESKTOP_FOLDER = os.path.join(os.path.expanduser("~"), "Desktop", "stream")
LOG_FILE_PATH = os.path.join(DESKTOP_FOLDER, "stream_history.log")

if not os.path.exists(DESKTOP_FOLDER):
    try:
        os.makedirs(DESKTOP_FOLDER)
    except Exception:
        pass # Fallback safe for cloud environments without desktop filesystems

def log_token_to_file(url):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] Found Target: {url}\n")
    except Exception:
        pass

def stream_scraper_loop():
    global LIVE_STREAM_URL, TARGET_WEBPAGE
    print(f"[*] Background Scraper Active.")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://koora24.sbs/",
    }
    
    session = requests.Session()
    
    while True:
        # Only scrape if a URL has been supplied through the web dashboard
        if TARGET_WEBPAGE:
            try:
                response = session.get(TARGET_WEBPAGE, headers=headers, timeout=15)
                iframe_srcs = re.findall(r'<iframe\s+[^>]*src="([^"]+)"', response.text, re.IGNORECASE)
                
                if iframe_srcs:
                    iframe_url = iframe_srcs[0]
                    if iframe_url.startswith('//'):
                        iframe_url = 'https:' + iframe_url
                    
                    iframe_headers = headers.copy()
                    iframe_headers["Referer"] = TARGET_WEBPAGE
                    
                    iframe_response = session.get(iframe_url, headers=iframe_headers, timeout=15)
                    m3u8_matches = re.findall(r'(https://[^\s"\']+\.m3u8[^\s"\']*)', iframe_response.text)
                    
                    if m3u8_matches:
                        detected_url = m3u8_matches[0]
                        if detected_url != LIVE_STREAM_URL:
                            LIVE_STREAM_URL = detected_url
                            print(f"[+] Scraper caught master link: {LIVE_STREAM_URL}")
                            log_token_to_file(LIVE_STREAM_URL)
            except Exception as e:
                print(f"[-] Scraper cycle update notice: {e}")
        else:
            # Clear previous target values if no stream URL is actively configured
            LIVE_STREAM_URL = ""
            
        time.sleep(30)

@app.route('/')
def live_player():
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>jstream hd</title>
            <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
            <style>
                body { background: #0f0f0f; margin: 0; display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 100vh; color: white; font-family: sans-serif; padding: 20px; box-sizing: border-box; }
                .container { text-align: center; width: 100%; max-width: 850px; }
                video { width: 100%; border-radius: 8px; border: 2px solid #333; background: #000; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
                h2 { margin-bottom: 5px; font-size: 2em; letter-spacing: 0.5px; }
                .credits { color: #888; font-size: 0.9em; margin-bottom: 20px; font-style: italic; }
                #status { color: #ffaa00; margin-top: 15px; font-weight: bold; font-size: 1.1em; margin-bottom: 30px; }
                
                .admin-panel { background: #1a1a1a; padding: 20px; border-radius: 8px; border: 1px solid #333; text-align: left; margin-top: 20px; }
                .admin-panel h3 { margin-top: 0; color: #00ff00; font-size: 1.2em; }
                .admin-panel label { display: block; margin-bottom: 8px; color: #bbb; font-size: 0.9em; }
                .input-group { display: flex; gap: 10px; }
                input[type="text"] { flex: 1; padding: 10px; background: #2a2a2a; border: 1px solid #444; border-radius: 4px; color: white; font-size: 1em; }
                input[type="text"]:focus { border-color: #00ff00; outline: none; }
                button { padding: 10px 20px; background: #00ff00; border: none; border-radius: 4px; color: black; font-weight: bold; cursor: pointer; font-size: 1em; }
                button:hover { background: #00cc00; }
                .current-url { font-size: 0.85em; color: #888; margin-top: 10px; word-break: break-all; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>jstream hd</h2>
                <div class="credits">coded by jonathan</div>
                <video id="video" controls autoplay></video>
                <div id="status">⏳ Awaiting target live stream link execution pipeline...</div>
                
                <div class="admin-panel">
                    <h3>Stream Configuration Interface</h3>
                    <form action="/set_target" method="POST">
                        <label for="url">Paste Target Match Webpage URL:</label>
                        <div class="input-group">
                            <input type="text" id="url" name="url" placeholder="https://a1.koora24.sbs/.../..." required>
                            <button type="submit">Set Source</button>
                        </div>
                    </form>
                    {% if current_target %}
                        <div class="current-url"><strong>Active Scraper Target:</strong> {{ current_target }}</div>
                    {% endif %}
                </div>
            </div>
            <script>
                var video = document.getElementById('video');
                var statusText = document.getElementById('status');
                var hls;

                function loadStream() {
                    if (Hls.isSupported()) {
                        if (hls) { hls.destroy(); }
                        hls = new Hls({ 
                            manifestLoadingTimeOut: 20000,
                            maxBufferLength: 30,
                            maxMaxBufferLength: 60,
                            abrEwmaDefaultEstimate: 50000000 
                        });
                        
                        hls.loadSource('/master.m3u8'); 
                        hls.attachMedia(video);
                        
                        hls.on(Hls.Events.MANIFEST_PARSED, function(event, data) {
                            statusText.style.color = "#00ff00";
                            statusText.innerText = "🟢 Stream Connected!";
                            if (hls.levels && hls.levels.length > 0) {
                                hls.currentLevel = hls.levels.length - 1;
                                hls.loadLevel = hls.levels.length - 1;
                            }
                            video.play();
                        });

                        hls.on(Hls.Events.LEVEL_SWITCHED, function(event, data) {
                            statusText.innerText = "🟢 hd";
                        });

                        hls.on(Hls.Events.ERROR, function(e, data) {
                            if (data.details === 'manifestLoadError') {
                                statusText.style.color = "#ffaa00";
                                statusText.innerText = "⏳ Awaiting fresh background token authorization...";
                                setTimeout(loadStream, 3000);
                            }
                        });
                    }
                }
                {% if target_set %}
                    loadStream();
                {% endif %}
            </script>
        </body>
        </html>
    ''', current_target=TARGET_WEBPAGE, target_set=bool(TARGET_WEBPAGE))

@app.route('/set_target', methods=['POST'])
def set_target():
    global TARGET_WEBPAGE, LIVE_STREAM_URL
    new_url = request.form.get('url', '').strip()
    if new_url:
        TARGET_WEBPAGE = new_url
        LIVE_STREAM_URL = "" # Reset the old token stream so the loop fetches a fresh one
    return redirect(url_for('live_player'))

@app.route('/master.m3u8')
def master_playlist():
    if not LIVE_STREAM_URL:
        return "Not found yet", 404
    return rewrite_m3u8(LIVE_STREAM_URL)

@app.route('/proxy')
def proxy_handler():
    target_url = unquote(request.args.get('url', ''))
    if not target_url:
        return "Missing URL parameter", 400

    if ".m3u8" in target_url:
        return rewrite_m3u8(target_url)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": TARGET_WEBPAGE if TARGET_WEBPAGE else "https://a1.koora24.sbs/",
        "Origin": "https://a1.koora24.sbs"
    }
    
    try:
        res = requests.get(target_url, headers=headers, timeout=10)
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": res.headers.get('Content-Type', 'application/octet-stream')
        }
        return Response(res.content, status=res.status_code, headers=response_headers)
    except Exception as e:
        return str(e), 500

def rewrite_m3u8(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": TARGET_WEBPAGE if TARGET_WEBPAGE else "https://a1.koora24.sbs/",
        "Origin": "https://a1.koora24.sbs"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        base_url = url.rsplit('/', 1)[0] + '/'
        rewritten_lines = []
        
        for line in res.text.splitlines():
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('#EXT-X-KEY:'):
                if 'URI="' in line:
                    start = line.find('URI="') + 5
                    end = line.find('"', start)
                    old_uri = line[start:end]
                    abs_uri = urljoin(base_url, old_uri)
                    proxied_uri = f"/proxy?url={quote(abs_uri)}"
                    line = line.replace(old_uri, proxied_uri)
                rewritten_lines.append(line)
            elif not line.startswith('#'):
                abs_url = urljoin(base_url, line)
                proxied_url = f"/proxy?url={quote(abs_url)}"
                rewritten_lines.append(proxied_url)
            else:
                rewritten_lines.append(line)
                
        return Response("\n".join(rewritten_lines), content_type='application/x-mpegURL', headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        return f"Error modifying stream schema: {e}", 500

if __name__ == '__main__':
    scraper_thread = Thread(target=stream_scraper_loop, daemon=True)
    scraper_thread.start()
    
    port = int(os.environ.get("PORT", 5000))
    
    print("\n" + "="*70)
    print("          jstream hd - RUNNING CLOUD PRODUCTION INSTANCE")
    print("                  (coded by jonathan)")
    print("="*70)
    print("⚠️  NOTICE: Private software deployment wrapper.")
    print("   DO NOT REDISTRIBUTE WITHOUT GIVEN PERMISSION.")
    print("="*70 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)