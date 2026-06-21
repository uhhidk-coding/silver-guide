import os
import requests
from urllib.parse import urljoin, quote, unquote
from flask import Flask, Response, render_template_string, request

app = Flask(__name__)

# The direct stream URL
STREAM_URL = "http://eypv0ag4.siauliairsavlt.pw/iptv/NW3M9M6N2H4NYM/19065/index.m3u8"

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
                video { width: 90%; max-width: 850px; border-radius: 8px; }
            </style>
        </head>
        <body>
            <video id="video" controls autoplay></video>
            <script>
                var video = document.getElementById('video');
                var hls = new Hls();
                // We load the stream directly from our proxy route
                hls.loadSource('/stream.m3u8');
                hls.attachMedia(video);
                video.muted = true;
                video.play().catch(e => console.log("Play clicked required"));
            </script>
        </body>
        </html>
    ''')

@app.route('/stream.m3u8')
def proxy_playlist():
    # Fetch the master playlist directly
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(STREAM_URL, headers=headers)
    base_url = STREAM_URL.rsplit('/', 1)[0] + '/'
    
    lines = []
    for line in res.text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            lines.append(line)
        else:
            # Proxy every segment or key found in the playlist
            abs_url = urljoin(base_url, line)
            lines.append(f"/proxy?url={quote(abs_url)}")
            
    return Response("\n".join(lines), content_type='application/x-mpegURL')

@app.route('/proxy')
def proxy_handler():
    target_url = unquote(request.args.get('url', ''))
    if not target_url: return "Missing URL", 400
    
    try:
        res = requests.get(target_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        return Response(res.content, status=res.status_code, headers={
            "Access-Control-Allow-Origin": "*",
            "Content-Type": res.headers.get('Content-Type', 'application/octet-stream')
        })
    except Exception as e: return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
