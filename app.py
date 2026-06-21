import os
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
