import os
import requests
from urllib.parse import urljoin, quote, unquote
from flask import Flask, Response, render_template_string, request

app = Flask(__name__)

# The direct stream URL
STREAM_URL = "http://hls01-04.az.myvideo.az/hls-live/livepkgr/sport2/sport2/sport2.m3u8?rRb545vJBB5tYzB7vVP"

@app.route('/')
def live_player():
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>jstream hd</title>
            <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
            <style>
                body { background: #000; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
                video { width: 90%; max-width: 850px; border-radius: 8px; background: #000; }
            </style>
        </head>
        <body>
            <video id="video" controls autoplay></video>
            <script>
                var video = document.getElementById('video');
                var hls = new Hls();
                hls.loadSource('/stream.m3u8');
                hls.attachMedia(video);
                video.muted = true;
                video.play().catch(e => console.log("Click to play"));
            </script>
        </body>
        </html>
    ''')

@app.route('/stream.m3u8')
def proxy_playlist():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0"}
    try:
        # Increased timeout to 15s to prevent 500 errors on slow connections
        res = requests.get(STREAM_URL, headers=headers, timeout=15)
        res.raise_for_status() 
        base_url = STREAM_URL.rsplit('/', 1)[0] + '/'
        
        lines = []
        for line in res.text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                lines.append(line)
            else:
                abs_url = urljoin(base_url, line)
                lines.append(f"/proxy?url={quote(abs_url)}")
                
        return Response("\n".join(lines), content_type='application/x-mpegURL')
    except Exception as e:
        # This will show the actual error in your Render logs instead of a silent 500
        print(f"Error fetching playlist: {e}")
        return f"Playlist Error: {str(e)}", 500

@app.route('/proxy')
def proxy_handler():
    target_url = unquote(request.args.get('url', ''))
    if not target_url: return "Missing URL", 400
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Referer": "http://www.myvideo.az/"
    }
    
    try:
        res = requests.get(target_url, headers=headers, timeout=15)
        return Response(res.content, status=res.status_code, headers={
            "Access-Control-Allow-Origin": "*",
            "Content-Type": res.headers.get('Content-Type', 'video/MP2T')
        })
    except Exception as e:
        print(f"Error proxying segment: {e}")
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
