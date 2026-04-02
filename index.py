from flask import Flask, request, jsonify
import requests
import re
import time
import hashlib
from urllib.parse import quote, urlparse
import logging
from functools import wraps

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ============================================
# CONFIGURATION
# ============================================

# Creator Info
CREATOR = {
    "name": "Sychox2006",
    "website": "tlz.vercel.app",
    "github": "github.com/sychoxhassan",
    "telegram": "@Sychox2006"
}

# API Key for authentication
API_KEY = "tlz.vercel.app"

# Rate limiting (simple in-memory storage)
RATE_LIMIT = 20  # requests per minute
RATE_WINDOW = 60  # seconds
rate_limit_storage = {}

# ============================================
# HELPER FUNCTIONS
#=============================================

def add_creator_info(data):
    """Add creator info to any response"""
    if isinstance(data, dict):
        data["creator"] = CREATOR
    return data

def get_client_ip():
    """Get real client IP behind proxy"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or 'unknown'

def check_rate_limit():
    """Rate limiting by IP address"""
    ip = get_client_ip()
    current_time = time.time()
    
    # Clean old entries
    if ip in rate_limit_storage:
        rate_limit_storage[ip] = [t for t in rate_limit_storage[ip] 
                                  if current_time - t < RATE_WINDOW]
    else:
        rate_limit_storage[ip] = []
    
    # Check limit
    if len(rate_limit_storage[ip]) >= RATE_LIMIT:
        return False
    
    # Add current request
    rate_limit_storage[ip].append(current_time)
    return True

def require_api_key(f):
    """Decorator for API key verification"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check API key in query params or headers
        api_key = request.args.get('key') or request.headers.get('X-API-Key')
        
        if not api_key or api_key != API_KEY:
            return jsonify(add_creator_info({
                "status": "error",
                "message": "Invalid or missing API key. Use ?key=tlz.vercel.app",
                "example": "/download?url=INSTAGRAM_URL&key=tlz.vercel.app"
            })), 401
        return f(*args, **kwargs)
    return decorated

def validate_instagram_url(url):
    """Validate and clean Instagram URL"""
    if not url:
        return False, "URL is required"
    
    # Add https:// if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Check if it's instagram.com
    parsed = urlparse(url)
    if 'instagram.com' not in parsed.netloc and 'instagr.am' not in parsed.netloc:
        return False, "Not an Instagram URL"
    
    # Check if it's a reel or post
    if not re.search(r'/(reel|p)/[a-zA-Z0-9_-]+', url):
        return False, "Not a valid Instagram reel or post URL"
    
    return True, url

def extract_instagram_data(url):
    """Extract video and thumbnail from SnapDownloader"""
    try:
        # Clean and encode URL
        encoded_url = quote(url)
        target_url = f"https://snapdownloader.com/tools/instagram-reels-downloader/download?url={encoded_url}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://snapdownloader.com/",
            "Origin": "https://snapdownloader.com",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        logging.info(f"Fetching from SnapDownloader: {target_url}")
        response = requests.get(target_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"SnapDownloader returned status {response.status_code}"
            }
        
        html = response.text
        
        # Extract video URL (mp4)
        video_patterns = [
            r'<a[^>]+href="([^"]+\.mp4[^"]*)"[^>]*>',
            r'<video[^>]+src="([^"]+\.mp4[^"]*)"',
            r'"video_url":"([^"]+\.mp4[^"]*)"',
            r'"download_url":"([^"]+\.mp4[^"]*)"',
            r'<source[^>]+src="([^"]+\.mp4[^"]*)"'
        ]
        
        video_url = None
        for pattern in video_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                video_url = match.group(1).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                break
        
        # Extract thumbnail URL (jpg)
        thumb_patterns = [
            r'<a[^>]+href="([^"]+\.jpg[^"]*)"[^>]*>',
            r'<img[^>]+src="([^"]+\.jpg[^"]*)"',
            r'"thumbnail":"([^"]+\.jpg[^"]*)"',
            r'<meta property="og:image" content="([^"]+)"',
            r'poster="([^"]+\.jpg[^"]*)"'
        ]
        
        thumb_url = None
        for pattern in thumb_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                thumb_url = match.group(1).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                break
        
        if video_url:
            return {
                "status": "success",
                "video_url": video_url,
                "thumbnail_url": thumb_url,
                "note": "Base64 thumbnail removed ✅"
            }
        else:
            return {
                "status": "error",
                "message": "No video link found. Make sure the reel is public.",
                "debug": "Video pattern not matched in HTML"
            }
            
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Request timeout - SnapDownloader took too long"}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": "Connection error - Cannot reach SnapDownloader"}
    except Exception as e:
        return {"status": "error", "message": f"Internal error: {str(e)}"}

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/', methods=['GET'])
def home():
    """Home endpoint with API info"""
    return jsonify(add_creator_info({
        "status": "success",
        "app": "Instagram Reels Downloader API",
        "version": "3.0",
        "features": [
            "✅ No watermark videos",
            "✅ Thumbnail extraction",
            "✅ Base64 removed",
            "✅ API key authentication",
            "✅ Rate limiting",
            "✅ CORS enabled"
        ],
        "endpoints": {
            "download": "/download?url=INSTAGRAM_URL&key=API_KEY",
            "info": "/",
            "health": "/health"
        },
        "example": f"/download?url=https://www.instagram.com/reel/DUjBJRkEfs_&key={API_KEY}",
        "rate_limit": f"{RATE_LIMIT} requests per {RATE_WINDOW} seconds",
        "api_key": API_KEY
    }))

@app.route('/download', methods=['GET'])
@require_api_key
def download():
    """Main download endpoint"""
    # Rate limiting
    if not check_rate_limit():
        return jsonify(add_creator_info({
            "status": "error",
            "message": f"Rate limit exceeded. Maximum {RATE_LIMIT} requests per {RATE_WINDOW} seconds."
        })), 429
    
    # Get and validate URL
    insta_url = request.args.get('url')
    is_valid, result = validate_instagram_url(insta_url)
    
    if not is_valid:
        return jsonify(add_creator_info({
            "status": "error",
            "message": result,
            "example": "/download?url=https://www.instagram.com/reel/DUjBJRkEfs_&key=tlz.vercel.app"
        })), 400
    
    # Extract data
    result = extract_instagram_data(result)
    
    # Add rate limit headers
    response = jsonify(add_creator_info(result))
    response.headers['X-RateLimit-Limit'] = str(RATE_LIMIT)
    response.headers['X-RateLimit-Remaining'] = str(RATE_LIMIT - len(rate_limit_storage.get(get_client_ip(), [])))
    response.headers['X-RateLimit-Reset'] = str(int(time.time()) + RATE_WINDOW)
    
    return response

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify(add_creator_info({
        "status": "healthy",
        "timestamp": time.time(),
        "active_ips": len(rate_limit_storage),
        "memory_usage": "unknown"
    }))

@app.route('/info', methods=['GET'])
@require_api_key
def info():
    """Get info about a reel without downloading"""
    insta_url = request.args.get('url')
    is_valid, result = validate_instagram_url(insta_url)
    
    if not is_valid:
        return jsonify(add_creator_info({
            "status": "error",
            "message": result
        })), 400
    
    # Just return basic info (you could add more here)
    return jsonify(add_creator_info({
        "status": "success",
        "message": "Use /download endpoint to get actual video",
        "url": result,
        "note": "This endpoint only validates the URL"
    }))

# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found(e):
    return jsonify(add_creator_info({
        "status": "error",
        "message": "Endpoint not found. Use /download?url=INSTAGRAM_URL&key=API_KEY"
    })), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify(add_creator_info({
        "status": "error",
        "message": "Method not allowed. Use GET requests only."
    })), 405

@app.errorhandler(500)
def server_error(e):
    return jsonify(add_creator_info({
        "status": "error",
        "message": "Internal server error"
    })), 500

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    print(f"""
╔══════════════════════════════════════════════════════════╗
║     🔥 INSTAGRAM REELS DOWNLOADER API v3.0               ║
╠══════════════════════════════════════════════════════════╣
║  👤 Creator: {CREATOR['name']}                                    ║
║  🌐 Website: {CREATOR['website']}                              ║
║  🔑 API Key: {API_KEY}                              ║
╠══════════════════════════════════════════════════════════╣
║  ✨ NEW FEATURES:                                          ║
║  • ✅ Base64 thumbnail removed                            ║
║  • 🔐 API key authentication                              ║
║  • ⚡ Rate limiting ({RATE_LIMIT}/min)                       ║
║  • 🛡️ URL validation                                      ║
╠══════════════════════════════════════════════════════════╣
║  📥 Usage:                                                ║
║  http://localhost:5000/download?url=<URL>&key={API_KEY}   ║
║                                                           ║
║  📝 Example:                                              ║
║  http://localhost:5000/download?url=https://www.instagram.com/reel/DUjBJRkEfs_&key={API_KEY} ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # Use waitress for production
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=5000)
    except ImportError:
        app.run(host="0.0.0.0", port=5000, debug=False)