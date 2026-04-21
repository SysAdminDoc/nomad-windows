"""Media library routes — video, audio, books, yt-dlp, torrents, channels."""

import json
import os
import sys
import time
import threading
import subprocess
import logging
import shutil

from flask import Blueprint, request, jsonify, Response
from werkzeug.utils import secure_filename

from web.blueprints import error_response
from db import db_session, log_activity
from services import ollama
from services.manager import format_size, get_services_dir
from config import get_data_dir
from web.state import _ytdlp_downloads, _ytdlp_dl_lock, _ytdlp_install_state
from web.validation import validate_json
from web.sql_safety import safe_table, safe_columns, build_update
import web.state as _state
from web.utils import clone_json_fallback as _clone_json_fallback, safe_json_list as _safe_json_list, validate_download_url as _validate_download_url
import posixpath as _posixpath


def _sanitize_folder(raw):
    """Sanitize a user-supplied folder path for media organization.

    Collapses traversal sequences, rejects anything that escapes the root,
    and strips leading/trailing slashes. Returns a clean relative path or ''.
    """
    if not raw:
        return ''
    # Normalize using posixpath to collapse .. and . regardless of OS
    normed = _posixpath.normpath(raw.replace('\\', '/'))
    # Reject any path that escapes root (starts with .. or is absolute)
    if normed.startswith('..') or normed.startswith('/'):
        return ''
    # Strip surrounding slashes and dots for safety
    return normed.strip('/').strip('.')

try:
    from web.catalog import CHANNEL_CATALOG, CHANNEL_CATEGORIES
except Exception:
    try:
        from catalog import CHANNEL_CATALOG, CHANNEL_CATEGORIES
    except Exception:
        CHANNEL_CATALOG = []
        CHANNEL_CATEGORIES = []

log = logging.getLogger('nomad.web')

_CREATION_FLAGS = {'creationflags': 0x08000000} if sys.platform == 'win32' else {}
_state_lock = threading.Lock()


def _safe_string_list(value):
    cleaned = []
    for item in _safe_json_list(value, []):
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _load_json_line(line, fallback=None):
    if fallback is None:
        fallback = {}
    if not isinstance(line, str):
        return _clone_json_fallback(fallback)
    text = line.strip()
    if not text:
        return _clone_json_fallback(fallback)
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return _clone_json_fallback(fallback)
    if isinstance(parsed, (dict, list)):
        return parsed
    return _clone_json_fallback(fallback)


def _safe_response_json(response, fallback=None):
    if fallback is None:
        fallback = {}
    try:
        parsed = response.json()
    except Exception:
        return _clone_json_fallback(fallback)
    if isinstance(parsed, (dict, list)):
        return parsed
    return _clone_json_fallback(fallback)


media_bp = Blueprint('media', __name__)

@media_bp.route('/api/media/video/<int:vid>/thumbnail', methods=['POST'])
def api_video_thumbnail(vid):
    """Generate a thumbnail for a video using FFmpeg."""
    with db_session() as db:
        row = db.execute('SELECT filename, folder FROM videos WHERE id = ?', (vid,)).fetchone()
        if not row:
            return error_response('Video not found', 404)

        videos_dir = os.path.join(get_data_dir(), 'videos')
        video_path = os.path.normpath(os.path.join(videos_dir, row['folder'] or '', row['filename']))
        if not os.path.normcase(video_path).startswith(os.path.normcase(videos_dir) + os.sep) or not os.path.isfile(video_path):
            return error_response('Video file not found on disk', 404)

        thumb_dir = os.path.join(get_data_dir(), 'thumbnails')
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_file = f'thumb_{vid}.jpg'
        thumb_path = os.path.join(thumb_dir, thumb_file)

        # Try FFmpeg
        ffmpeg = os.path.join(get_services_dir(), 'ffmpeg', 'ffmpeg.exe') if sys.platform == 'win32' else 'ffmpeg'
        try:
            subprocess.run([
                ffmpeg, '-i', video_path, '-ss', '5', '-vframes', '1',
                '-vf', 'scale=320:-1', '-y', thumb_path
            ], capture_output=True, timeout=15, **_CREATION_FLAGS)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return error_response('FFmpeg not available', 500)

        if os.path.isfile(thumb_path):
            db.execute('UPDATE videos SET thumbnail = ? WHERE id = ?', (f'/api/media/thumbnail/{thumb_file}', vid))
            db.commit()
            return jsonify({'status': 'ok', 'thumbnail': f'/api/media/thumbnail/{thumb_file}'})
        return error_response('Thumbnail generation failed', 500)
@media_bp.route('/api/media/thumbnail/<filename>')
def api_media_thumbnail_serve(filename):
    """Serve a generated thumbnail."""
    safe = secure_filename(filename)
    thumb_dir = os.path.join(get_data_dir(), 'thumbnails')
    full = os.path.join(thumb_dir, safe)
    if not os.path.normcase(os.path.normpath(full)).startswith(os.path.normcase(os.path.normpath(thumb_dir)) + os.sep):
        return jsonify({'error': 'Invalid path'}), 400
    if not os.path.isfile(full):
        return jsonify({'error': 'Not found'}), 404
    from flask import send_file
    return send_file(full, mimetype='image/jpeg')

def get_video_dir():
    path = os.path.join(get_data_dir(), 'videos')
    os.makedirs(path, exist_ok=True)
    return path

def _ytdlp_standalone_path():
    """Path to the standalone yt-dlp binary (downloaded/updated separately)."""
    from platform_utils import IS_WINDOWS, IS_MACOS
    if IS_WINDOWS:
        name = 'yt-dlp.exe'
    elif IS_MACOS:
        name = 'yt-dlp_macos'
    else:
        name = 'yt-dlp_linux'
    return os.path.join(get_services_dir(), 'yt-dlp', name)


def _ytdlp_bundled_available():
    """Check if yt-dlp is available as a bundled Python module."""
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        return False


def get_ytdlp_path():
    """Return the yt-dlp executable path.

    Priority:
    1. Standalone binary (services/yt-dlp/) — allows independent updates
    2. Bundled Python module — writes a wrapper script so subprocess calls work unchanged
    """
    standalone = _ytdlp_standalone_path()
    if os.path.isfile(standalone):
        return standalone
    if _ytdlp_bundled_available():
        return _ensure_bundled_wrapper()
    return standalone  # Not installed yet — return expected standalone path


def _ensure_bundled_wrapper():
    """Create a small wrapper script that invokes the bundled yt_dlp module.

    This lets all existing subprocess.run([exe, ...]) calls work without changes.
    """
    from platform_utils import IS_WINDOWS
    wrapper_dir = os.path.join(get_services_dir(), 'yt-dlp')
    os.makedirs(wrapper_dir, exist_ok=True)
    if IS_WINDOWS:
        wrapper = os.path.join(wrapper_dir, 'yt-dlp-bundled.cmd')
        if not os.path.isfile(wrapper):
            with open(wrapper, 'w') as f:
                f.write(f'@"{sys.executable}" -m yt_dlp %*\n')
    else:
        wrapper = os.path.join(wrapper_dir, 'yt-dlp-bundled')
        if not os.path.isfile(wrapper):
            with open(wrapper, 'w') as f:
                f.write(f'#!/bin/sh\nexec "{sys.executable}" -m yt_dlp "$@"\n')
            os.chmod(wrapper, 0o755)
    return wrapper


def _ytdlp_installed():
    """Check if yt-dlp is available (bundled or standalone)."""
    standalone = _ytdlp_standalone_path()
    return os.path.isfile(standalone) or _ytdlp_bundled_available()


VIDEO_CATEGORIES = ['survival', 'medical', 'repair', 'bushcraft', 'cooking', 'radio', 'farming', 'defense', 'general']

def _get_ytdlp_url():
    from platform_utils import IS_WINDOWS, IS_MACOS
    base = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/'
    if IS_WINDOWS:
        return base + 'yt-dlp.exe'
    elif IS_MACOS:
        return base + 'yt-dlp_macos'
    return base + 'yt-dlp_linux'

# Curated prepper video catalog — top offline survival content
PREPPER_CATALOG = [
    # Water & Sanitation
    {'title': 'How to Purify Water in a Survival Situation', 'url': 'https://www.youtube.com/watch?v=wEBYmeVwCeA', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Water & Sanitation'},
    {'title': 'DIY Water Filter - How to Make a Homemade Water Filter', 'url': 'https://www.youtube.com/watch?v=z4yBzMKxH_A', 'channel': 'Practical Engineering', 'category': 'survival', 'folder': 'Water & Sanitation'},
    {'title': 'How to Find and Purify Water | Survival Skills', 'url': 'https://www.youtube.com/watch?v=mV3L6w0n1jI', 'channel': 'Coalcracker Bushcraft', 'category': 'bushcraft', 'folder': 'Water & Sanitation'},
    # Food & Foraging
    {'title': 'Long Term Food Storage - A Beginners Guide', 'url': 'https://www.youtube.com/watch?v=OGkRUHl-dbw', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Food & Storage'},
    {'title': 'Canning 101: Start Here', 'url': 'https://www.youtube.com/watch?v=EqkXsVBjPJA', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Food & Storage'},
    {'title': '37 Survival Foods Every Prepper Should Stockpile', 'url': 'https://www.youtube.com/watch?v=jLIWqg5Cjhc', 'channel': 'Canadian Prepper', 'category': 'survival', 'folder': 'Food & Storage'},
    {'title': '20 Wild Edibles You Can Forage for Survival', 'url': 'https://www.youtube.com/watch?v=ZPJPONHGf-0', 'channel': 'Black Scout Survival', 'category': 'bushcraft', 'folder': 'Food & Storage'},
    # First Aid & Medical
    {'title': 'Wilderness First Aid Basics', 'url': 'https://www.youtube.com/watch?v=JR2IABjLJBY', 'channel': 'Corporals Corner', 'category': 'medical', 'folder': 'First Aid & Medical'},
    {'title': 'Stop the Bleed - Tourniquet Application', 'url': 'https://www.youtube.com/watch?v=CSiuSIFDcuI', 'channel': 'Tactical Rifleman', 'category': 'medical', 'folder': 'First Aid & Medical'},
    {'title': 'Trauma Bag Essentials — Building an IFAK for Field Use', 'url': 'https://www.youtube.com/watch?v=VBuF3QKsN7o', 'channel': 'Skinny Medic', 'category': 'medical', 'folder': 'First Aid & Medical'},
    {'title': 'The Ultimate First Aid Kit Build', 'url': 'https://www.youtube.com/watch?v=MX0kB-x_XPg', 'channel': 'The Urban Prepper', 'category': 'medical', 'folder': 'First Aid & Medical'},
    # Shelter & Construction
    {'title': 'How to Build a Survival Shelter', 'url': 'https://www.youtube.com/watch?v=jfOC1ywRY3M', 'channel': 'Corporals Corner', 'category': 'bushcraft', 'folder': 'Shelter & Construction'},
    {'title': '5 Shelters Everyone Should Know How to Build', 'url': 'https://www.youtube.com/watch?v=wZjKQwjdGF0', 'channel': 'Coalcracker Bushcraft', 'category': 'bushcraft', 'folder': 'Shelter & Construction'},
    {'title': 'Off Grid Cabin Build - Start to Finish', 'url': 'https://www.youtube.com/watch?v=YOJCRvjFpgQ', 'channel': 'My Self Reliance', 'category': 'repair', 'folder': 'Shelter & Construction'},
    # Fire & Energy
    {'title': '5 Ways to Start a Fire Without Matches', 'url': 'https://www.youtube.com/watch?v=lR-LrU0zA0Y', 'channel': 'Sensible Prepper', 'category': 'bushcraft', 'folder': 'Fire & Energy'},
    {'title': 'Solar Power for Beginners', 'url': 'https://www.youtube.com/watch?v=W0Miu0mihVE', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Fire & Energy'},
    {'title': 'DIY Solar Generator Build', 'url': 'https://www.youtube.com/watch?v=k_jVk2Q2sJY', 'channel': 'Full Spectrum Survival', 'category': 'repair', 'folder': 'Fire & Energy'},
    # Navigation & Communication
    {'title': 'Land Navigation with Map and Compass', 'url': 'https://www.youtube.com/watch?v=0cF0ovA3FtY', 'channel': 'Black Scout Survival', 'category': 'survival', 'folder': 'Navigation & Comms'},
    {'title': 'Ham Radio for Beginners - Get Your License', 'url': 'https://www.youtube.com/watch?v=WIsBdMdNfNI', 'channel': 'Tin Hat Ranch', 'category': 'radio', 'folder': 'Navigation & Comms'},
    {'title': 'GMRS vs Ham Radio - Which is Better for Preppers', 'url': 'https://www.youtube.com/watch?v=uK3cMvEpnqg', 'channel': 'Magic Prepper', 'category': 'radio', 'folder': 'Navigation & Comms'},
    # Security & Defense
    {'title': 'Home Security on a Budget', 'url': 'https://www.youtube.com/watch?v=AUxTRyqp5qg', 'channel': 'City Prepping', 'category': 'defense', 'folder': 'Security & Defense'},
    {'title': 'Perimeter Security for Your Property', 'url': 'https://www.youtube.com/watch?v=bNJYjw7VSzM', 'channel': 'Bear Independent', 'category': 'defense', 'folder': 'Security & Defense'},
    {'title': 'Night Vision on a Budget for Home Defense', 'url': 'https://www.youtube.com/watch?v=f8l2E7kk654', 'channel': 'Angry Prepper', 'category': 'defense', 'folder': 'Security & Defense'},
    # Farming & Homesteading
    {'title': 'Start a Survival Garden in 30 Days', 'url': 'https://www.youtube.com/watch?v=u3x0JPCHDOQ', 'channel': 'City Prepping', 'category': 'farming', 'folder': 'Farming & Homestead'},
    {'title': 'Raising Chickens 101 - Everything You Need to Know', 'url': 'https://www.youtube.com/watch?v=jbHhEsEJ99g', 'channel': 'Homesteading Family', 'category': 'farming', 'folder': 'Farming & Homestead'},
    {'title': 'Seed Saving for Beginners', 'url': 'https://www.youtube.com/watch?v=LtH7lkP8bAU', 'channel': 'Epic Gardening', 'category': 'farming', 'folder': 'Farming & Homestead'},
    # General Preparedness
    {'title': 'The Ultimate Prepper Guide for Beginners', 'url': 'https://www.youtube.com/watch?v=JVuxCgo8mWM', 'channel': 'Canadian Prepper', 'category': 'survival', 'folder': 'Getting Started'},
    {'title': 'Bug Out Bag Essentials - 2024 Build', 'url': 'https://www.youtube.com/watch?v=HSTrM0pXnCA', 'channel': 'The Urban Prepper', 'category': 'survival', 'folder': 'Getting Started'},
    {'title': 'Get Home Bag: The Most Important Bag You Can Have', 'url': 'https://www.youtube.com/watch?v=a_L4ilHQFPQ', 'channel': 'Sensible Prepper', 'category': 'survival', 'folder': 'Getting Started'},
    {'title': 'EMP Attack - How to Prepare and Protect Electronics', 'url': 'https://www.youtube.com/watch?v=bJh1yd1yRes', 'channel': 'Canadian Prepper', 'category': 'survival', 'folder': 'Threats & Scenarios'},
    {'title': 'Economic Collapse: How to Prepare', 'url': 'https://www.youtube.com/watch?v=xhmReScCzE4', 'channel': 'Full Spectrum Survival', 'category': 'survival', 'folder': 'Threats & Scenarios'},
    {'title': 'Nuclear War Survival - What You Need to Know', 'url': 'https://www.youtube.com/watch?v=_GNh3p1GFAI', 'channel': 'Canadian Prepper', 'category': 'defense', 'folder': 'Threats & Scenarios'},
    # Bushcraft & Wilderness Skills
    {'title': 'Top 10 Knots You Need to Know', 'url': 'https://www.youtube.com/watch?v=VrSBsqe23Qk', 'channel': 'Coalcracker Bushcraft', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
    {'title': 'Trapping for Survival - Basics and Techniques', 'url': 'https://www.youtube.com/watch?v=vAjl4IpYZXk', 'channel': 'Reality Survival', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
    {'title': 'Knife Sharpening - How to Get a Razor Edge', 'url': 'https://www.youtube.com/watch?v=tRfBA-lBs-4', 'channel': 'Corporals Corner', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
    # Repair & Tools
    {'title': 'Basic Automotive Repair Everyone Should Know', 'url': 'https://www.youtube.com/watch?v=MbyJjkpgNBU', 'channel': 'ChrisFix', 'category': 'repair', 'folder': 'Repair & Tools'},
    {'title': 'Essential Hand Tools for Survival', 'url': 'https://www.youtube.com/watch?v=9XUsqYoSzxo', 'channel': 'Sensible Prepper', 'category': 'repair', 'folder': 'Repair & Tools'},
    # Water — Advanced
    {'title': 'Rainwater Harvesting System Build', 'url': 'https://www.youtube.com/watch?v=OSDP3DTHXKA', 'channel': 'Homesteading Family', 'category': 'survival', 'folder': 'Water & Sanitation'},
    {'title': 'How to Test Your Water for Contaminants', 'url': 'https://www.youtube.com/watch?v=3R2SHZPC8Hs', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Water & Sanitation'},
    {'title': 'Building a Berkey-Style Gravity Water Filter', 'url': 'https://www.youtube.com/watch?v=PeK1c1M9woo', 'channel': 'Engineer775', 'category': 'survival', 'folder': 'Water & Sanitation'},
    {'title': 'How to Find Water in the Wild', 'url': 'https://www.youtube.com/watch?v=nE0qnpJKj-E', 'channel': 'Corporals Corner', 'category': 'bushcraft', 'folder': 'Water & Sanitation'},
    # Food — Fermentation & Preservation
    {'title': 'Fermenting Vegetables at Home — Complete Beginner Guide', 'url': 'https://www.youtube.com/watch?v=Ng4gMB5ZOAM', 'channel': "Mary's Nest", 'category': 'cooking', 'folder': 'Food & Storage'},
    {'title': 'Sourdough Bread from Scratch — No Yeast', 'url': 'https://www.youtube.com/watch?v=sTAiDki_ABA', 'channel': "Mary's Nest", 'category': 'cooking', 'folder': 'Food & Storage'},
    {'title': 'Dehydrating Food for Long-Term Storage', 'url': 'https://www.youtube.com/watch?v=nZWNkFjJgqM', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Food & Storage'},
    {'title': 'Making Jerky — Beef, Venison, or Any Meat', 'url': 'https://www.youtube.com/watch?v=hmWGRPh5Ew8', 'channel': 'Survival Russia', 'category': 'cooking', 'folder': 'Food & Storage'},
    {'title': 'Salt Curing Meat — Preservation Without Refrigeration', 'url': 'https://www.youtube.com/watch?v=CQyJBfUiXi4', 'channel': 'Townsends', 'category': 'cooking', 'folder': 'Food & Storage'},
    {'title': 'Freeze Drying at Home — What You Need to Know', 'url': 'https://www.youtube.com/watch?v=6FPFNuVGfzk', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Food & Storage'},
    {'title': 'Smoking Meat for Preservation', 'url': 'https://www.youtube.com/watch?v=0lAj1MQH_NU', 'channel': 'Survival Dispatch', 'category': 'cooking', 'folder': 'Food & Storage'},
    # Medical — Advanced
    {'title': 'Wound Closure: When to Suture vs. Leave Open', 'url': 'https://www.youtube.com/watch?v=mfWahyERGBo', 'channel': 'Skinny Medic', 'category': 'medical', 'folder': 'First Aid & Medical'},
    {'title': 'Improvised Splinting and Fracture Management', 'url': 'https://www.youtube.com/watch?v=3zT5K35EbcU', 'channel': 'PrepMedic', 'category': 'medical', 'folder': 'First Aid & Medical'},
    {'title': 'CPR and AED Training — Full Course', 'url': 'https://www.youtube.com/watch?v=cosVBV96E2g', 'channel': 'Survival Dispatch', 'category': 'medical', 'folder': 'First Aid & Medical'},
    {'title': 'Dental Emergencies Without a Dentist', 'url': 'https://www.youtube.com/watch?v=7yWpLuQcYaE', 'channel': 'DrBones NurseAmy', 'category': 'medical', 'folder': 'First Aid & Medical'},
    {'title': 'TCCC — Care Under Fire and Tactical Field Care', 'url': 'https://www.youtube.com/watch?v=J6-nFr-pn4A', 'channel': 'Skinny Medic', 'category': 'medical', 'folder': 'First Aid & Medical'},
    {'title': 'Managing Infection Without Antibiotics', 'url': 'https://www.youtube.com/watch?v=1hpEL7Jy_HI', 'channel': 'DrBones NurseAmy', 'category': 'medical', 'folder': 'First Aid & Medical'},
    {'title': 'Herbal Medicine — Making Tinctures, Salves, and Poultices', 'url': 'https://www.youtube.com/watch?v=HQdXn_bDiIs', 'channel': 'HerbMentor', 'category': 'medical', 'folder': 'First Aid & Medical'},
    # Hunting, Trapping & Fishing
    {'title': 'Primitive Fish Traps — Weirs, Basket Traps, and Gill Nets', 'url': 'https://www.youtube.com/watch?v=K6uimXgxsHE', 'channel': 'Shawn Woods', 'category': 'bushcraft', 'folder': 'Hunting & Trapping'},
    {'title': 'Field Dressing a Deer — Complete Walkthrough', 'url': 'https://www.youtube.com/watch?v=VwFADTGiXWw', 'channel': 'deermeatfordinner', 'category': 'bushcraft', 'folder': 'Hunting & Trapping'},
    {'title': 'Ice Fishing for Survival — Gear-Free Methods', 'url': 'https://www.youtube.com/watch?v=qNP5qI1DRbM', 'channel': 'Survival Russia', 'category': 'bushcraft', 'folder': 'Hunting & Trapping'},
    {'title': 'Trotlines and Limb Lines — Passive Fish Catching', 'url': 'https://www.youtube.com/watch?v=pEGAg0E2p1w', 'channel': 'Reality Survival', 'category': 'bushcraft', 'folder': 'Hunting & Trapping'},
    # Farming & Homesteading
    {'title': 'Vermicomposting — Red Wigglers for Year-Round Fertilizer Production', 'url': 'https://www.youtube.com/watch?v=D5lSFrJd6xY', 'channel': 'Epic Gardening', 'category': 'farming', 'folder': 'Farming & Homestead'},
    {'title': 'Composting 101 — Building Soil from Scratch', 'url': 'https://www.youtube.com/watch?v=egyNJ9HKMeo', 'channel': 'Epic Gardening', 'category': 'farming', 'folder': 'Farming & Homestead'},
    {'title': 'Root Cellaring — No-Electricity Food Storage', 'url': 'https://www.youtube.com/watch?v=jnFGLUeOiTQ', 'channel': 'Homesteading Family', 'category': 'farming', 'folder': 'Farming & Homestead'},
    {'title': 'Building a Simple Greenhouse from Scratch', 'url': 'https://www.youtube.com/watch?v=ZSWInr7PpTs', 'channel': 'Arms Family Homestead', 'category': 'farming', 'folder': 'Farming & Homestead'},
    {'title': 'Backyard Beekeeping for Beginners', 'url': 'https://www.youtube.com/watch?v=MmLeKkEa7J0', 'channel': 'Stoney Ridge Farmer', 'category': 'farming', 'folder': 'Farming & Homestead'},
    # Energy & Power
    {'title': 'Whole House Backup Power — Generator Sizing Guide', 'url': 'https://www.youtube.com/watch?v=g4smHKnZMRU', 'channel': 'City Prepping', 'category': 'repair', 'folder': 'Fire & Energy'},
    {'title': 'DIY Battery Bank — LiFePO4 Build', 'url': 'https://www.youtube.com/watch?v=S3E1KfFUpA4', 'channel': 'DIY Solar Power (Will Prowse)', 'category': 'repair', 'folder': 'Fire & Energy'},
    {'title': 'Wind Turbine Build from Scratch', 'url': 'https://www.youtube.com/watch?v=Yw4oqaEyFq8', 'channel': 'Engineer775', 'category': 'repair', 'folder': 'Fire & Energy'},
    {'title': 'Propane Generator Conversion — Dual-Fuel for Grid-Down Reliability', 'url': 'https://www.youtube.com/watch?v=hMt-DXMFkBk', 'channel': 'Engineer775', 'category': 'repair', 'folder': 'Fire & Energy'},
    {'title': 'How to Split Firewood Efficiently', 'url': 'https://www.youtube.com/watch?v=wn4EbVaFsUE', 'channel': 'My Self Reliance', 'category': 'bushcraft', 'folder': 'Fire & Energy'},
    # Security & Defense
    {'title': 'Home Hardening — Making Your Home Harder to Break Into', 'url': 'https://www.youtube.com/watch?v=J5MBTS4VXBI', 'channel': 'City Prepping', 'category': 'defense', 'folder': 'Security & Defense'},
    {'title': 'Improvised Alarm Systems and Trip Wires', 'url': 'https://www.youtube.com/watch?v=mEXGD7bxCIQ', 'channel': 'Black Scout Survival', 'category': 'defense', 'folder': 'Security & Defense'},
    # Repair & Fabrication
    {'title': 'Basic Welding for Survival Repairs', 'url': 'https://www.youtube.com/watch?v=u4PMqS3JNXY', 'channel': 'ChrisFix', 'category': 'repair', 'folder': 'Repair & Tools'},
    {'title': 'Blacksmithing 101 — Fire Welding and Basic Forging', 'url': 'https://www.youtube.com/watch?v=f8T7P7EFuWY', 'channel': 'Black Bear Forge', 'category': 'repair', 'folder': 'Repair & Tools'},
    {'title': 'Small Engine Repair — Carburetors, Fuel, and Ignition', 'url': 'https://www.youtube.com/watch?v=NTRpXFgPBEo', 'channel': 'EricTheCarGuy', 'category': 'repair', 'folder': 'Repair & Tools'},
    {'title': 'Chainsaw Maintenance and Safe Operation', 'url': 'https://www.youtube.com/watch?v=LFe5vvCFqAE', 'channel': 'My Self Reliance', 'category': 'repair', 'folder': 'Repair & Tools'},
    # Navigation & Communications
    {'title': 'Celestial Navigation — Finding North by Stars', 'url': 'https://www.youtube.com/watch?v=LXiYW2CKVLQ', 'channel': 'Black Scout Survival', 'category': 'survival', 'folder': 'Navigation & Comms'},
    {'title': 'Building a Faraday Cage — EMP Protection for Electronics', 'url': 'https://www.youtube.com/watch?v=P5VT1q-kM7I', 'channel': 'Tin Hat Ranch', 'category': 'survival', 'folder': 'Navigation & Comms'},
    {'title': 'GMRS Radio Setup for Family and Community Comms', 'url': 'https://www.youtube.com/watch?v=HxbCHJ0XLGY', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Navigation & Comms'},
    # Mental / Psychological Preparedness
    {'title': 'SHTF Psychology — Managing Panic and Decision-Making Under Stress', 'url': 'https://www.youtube.com/watch?v=qxNjJPHzN-o', 'channel': 'Canadian Prepper', 'category': 'survival', 'folder': 'Getting Started'},
    {'title': 'Gray Man Concept — Avoiding Attention During Emergencies', 'url': 'https://www.youtube.com/watch?v=_sRjSR_B2Bc', 'channel': 'City Prepping', 'category': 'defense', 'folder': 'Security & Defense'},
    # Weather Reading & Meteorology
    {'title': 'How to Read a Barometer for Weather Forecasting', 'url': 'https://www.youtube.com/watch?v=sPklvTR5K8Y', 'channel': 'NWS Headquarters', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'Cloud Identification — Forecasting Weather Without a Phone', 'url': 'https://www.youtube.com/watch?v=0k2bfJIr6gQ', 'channel': 'The COMET Program', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'Understanding Doppler Radar for Preppers', 'url': 'https://www.youtube.com/watch?v=4M8HJRsn8Lc', 'channel': 'Ryan Hall Y\'all', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'Tornado Safety — What to Do When There\'s No Shelter', 'url': 'https://www.youtube.com/watch?v=X8TBpYOzBnY', 'channel': 'NWS Headquarters', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'NOAA Weather Radio Setup and Programming', 'url': 'https://www.youtube.com/watch?v=8cGZ1lFlZjQ', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Weather & Climate'},
    {'title': 'Reading NWS Forecast Discussions Like a Meteorologist', 'url': 'https://www.youtube.com/watch?v=PqVTcUnRFSM', 'channel': 'The COMET Program', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'Flash Flood Recognition and Escape Routes', 'url': 'https://www.youtube.com/watch?v=kFdCsKm-fgg', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'Hurricane Season Preparation Timeline — Month by Month', 'url': 'https://www.youtube.com/watch?v=kV0Y1tPMjbs', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'Winter Storm Survival — Blizzard, Ice Storm, Power Outage', 'url': 'https://www.youtube.com/watch?v=1MYy2yGX3sg', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'Lightning Safety — Distance Calculation and Shelter Protocol', 'url': 'https://www.youtube.com/watch?v=Hd_O8Xiu4hM', 'channel': 'NWS Headquarters', 'category': 'survival', 'folder': 'Weather & Climate'},
    # Maps & Geospatial
    {'title': 'How to Read a Topographic Map — Contour Lines Explained', 'url': 'https://www.youtube.com/watch?v=CoVcn2LT56k', 'channel': 'REI', 'category': 'survival', 'folder': 'Navigation & Comms'},
    {'title': 'Download and Use Free Offline Maps with QGIS', 'url': 'https://www.youtube.com/watch?v=RTjAp6dqvsM', 'channel': 'GIS Geography', 'category': 'survival', 'folder': 'Navigation & Comms'},
    {'title': 'USGS Topographic Maps — Where to Download and How to Use', 'url': 'https://www.youtube.com/watch?v=BpFCOeR02SU', 'channel': 'USGS (US Geological Survey)', 'category': 'survival', 'folder': 'Navigation & Comms'},
    {'title': 'Reading FEMA Flood Maps — Know Your Risk Before It Floods', 'url': 'https://www.youtube.com/watch?v=kCr-b8NfLFo', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Navigation & Comms'},
    {'title': 'Geologic Maps — Identifying Water Sources, Soil, and Hazards', 'url': 'https://www.youtube.com/watch?v=G87c5b9bHXs', 'channel': 'USGS (US Geological Survey)', 'category': 'survival', 'folder': 'Navigation & Comms'},
    {'title': 'OpenStreetMap for Offline Survival — Download Any Region', 'url': 'https://www.youtube.com/watch?v=7oRvtRaKFYs', 'channel': 'geodesign', 'category': 'survival', 'folder': 'Navigation & Comms'},
    {'title': 'MGRS Grid Coordinates — Military Map Reading Explained', 'url': 'https://www.youtube.com/watch?v=mjdG-oBi4Mc', 'channel': 'Black Scout Survival', 'category': 'survival', 'folder': 'Navigation & Comms'},
    {'title': 'Terrain Analysis for Survival — Reading Land Features From a Map', 'url': 'https://www.youtube.com/watch?v=FDKf5pGNxuA', 'channel': 'Black Scout Survival', 'category': 'survival', 'folder': 'Navigation & Comms'},
    # Radio Skills Deep Dive
    {'title': 'Winlink Over HF Radio — Email Without Internet', 'url': 'https://www.youtube.com/watch?v=Vf3rD-5sHtc', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Navigation & Comms'},
    {'title': 'JS8Call Setup — Resilient Digital Messaging for Grid-Down', 'url': 'https://www.youtube.com/watch?v=xnVBSHoqE3Y', 'channel': 'KM4ACK (Jason Oleham)', 'category': 'radio', 'folder': 'Navigation & Comms'},
    {'title': 'SDR Basics — Receive Weather Satellites with a $25 Dongle', 'url': 'https://www.youtube.com/watch?v=5q3MWBQm9t4', 'channel': 'Signals Everywhere', 'category': 'radio', 'folder': 'Navigation & Comms'},
    {'title': 'APRS Tracking and Messaging — Automatic Packet Reporting System', 'url': 'https://www.youtube.com/watch?v=YGNi1PN4kIw', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Navigation & Comms'},
    {'title': 'Off-Grid Solar Powered Radio Station — HF on 10W', 'url': 'https://www.youtube.com/watch?v=BKJFhKBOIaA', 'channel': 'OH8STN Julian OH8STN', 'category': 'radio', 'folder': 'Navigation & Comms'},
    {'title': 'LoRa Meshtastic — Off-Grid Text Messaging With No License', 'url': 'https://www.youtube.com/watch?v=d_h38X4_pqY', 'channel': 'Andreas Spiess', 'category': 'radio', 'folder': 'Navigation & Comms'},
    # Advanced Homesteading & Aquaponics
    {'title': 'Aquaponics for Self-Sufficiency — Growing Fish and Vegetables Together', 'url': 'https://www.youtube.com/watch?v=aOBHVCeBfqI', 'channel': 'Bright Agrotech', 'category': 'farming', 'folder': 'Farming & Homestead'},
    {'title': 'Underground Rainwater Cistern Build — 2,500 Gallon Tank', 'url': 'https://www.youtube.com/watch?v=Fg1d8S9TwPc', 'channel': 'An American Homestead', 'category': 'survival', 'folder': 'Water & Sanitation'},
    {'title': 'Rocket Stove Build — 80% More Efficient Than an Open Fire', 'url': 'https://www.youtube.com/watch?v=Qr4y5TXtGPQ', 'channel': 'Paul Wheaton (Permies)', 'category': 'repair', 'folder': 'Fire & Energy'},
    {'title': 'Hand Drilling a Water Well — No Equipment Required', 'url': 'https://www.youtube.com/watch?v=2TM_HVvnEn4', 'channel': 'Practical Engineering', 'category': 'survival', 'folder': 'Water & Sanitation'},
    {'title': 'Foraging Wild Mushrooms — Safe Identification Framework', 'url': 'https://www.youtube.com/watch?v=wMwBGqPFmv0', 'channel': 'Learn Your Land', 'category': 'bushcraft', 'folder': 'Food & Storage'},
    {'title': 'Emergency Pet Evacuation — Bug Out With Dogs, Cats, and Livestock', 'url': 'https://www.youtube.com/watch?v=wQIj3v4ySXs', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Getting Started'},
    {'title': 'Grid-Down Cooking Methods — Dutch Oven, Solar Oven, Rocket Stove', 'url': 'https://www.youtube.com/watch?v=bMpRqT5zLXw', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Food & Storage'},
    {'title': 'Tanning Deer Hide — Brain Tanning Method Step by Step', 'url': 'https://www.youtube.com/watch?v=nAWfIMOuLrs', 'channel': 'Far North Bushcraft And Survival', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
    {'title': 'Hand Tool Woodworking — Joinery Without Power Tools', 'url': 'https://www.youtube.com/watch?v=rZ8bXUGN4WQ', 'channel': 'Paul Sellers', 'category': 'repair', 'folder': 'Shelter & Construction'},
    {'title': 'Security Communication Plan — Family Radio Protocols for SHTF', 'url': 'https://www.youtube.com/watch?v=wIsBdMdNfNI', 'channel': 'Tin Hat Ranch', 'category': 'radio', 'folder': 'Navigation & Comms'},
    # Veterinary & Animal Health
    {'title': 'Goat Health and Disease Prevention — Common Ailments Without a Vet', 'url': 'https://www.youtube.com/watch?v=qT2vLpHrNkE', 'channel': 'Becky\'s Homestead', 'category': 'farming', 'folder': 'Farming & Homestead'},
    {'title': 'Wound Care for Livestock — Suturing, Bandaging, and Infection Control', 'url': 'https://www.youtube.com/watch?v=yP8tJnF3xQs', 'channel': 'The Holistic Hen', 'category': 'medical', 'folder': 'First Aid & Medical'},
    # Nuclear & CBRN Response
    {'title': 'Fallout Shelter Improvisation — Using What You Have at Home', 'url': 'https://www.youtube.com/watch?v=nX4b7Lp8KrM', 'channel': 'Canadian Prepper', 'category': 'defense', 'folder': 'Threats & Scenarios'},
    {'title': 'KI Tablets and Thyroid Protection After Nuclear Event', 'url': 'https://www.youtube.com/watch?v=Wz9qRsLmpVk', 'channel': 'City Prepping', 'category': 'medical', 'folder': 'First Aid & Medical'},
    # Textiles & Clothing
    {'title': 'Hand Sewing Essentials — Repair Clothing Without a Machine', 'url': 'https://www.youtube.com/watch?v=eKq7vFNhgL8', 'channel': 'Make It and Love It', 'category': 'repair', 'folder': 'Repair & Tools'},
    {'title': 'Wool Processing — Shearing, Carding, Spinning, and Weaving', 'url': 'https://www.youtube.com/watch?v=uYFxJkMmCbQ', 'channel': 'Jas Townsend and Son', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
    # Grid-Down Sanitation & Hygiene
    {'title': 'Emergency Sanitation Without Running Water — Composting Toilets and Latrines', 'url': 'https://www.youtube.com/watch?v=cZ6q3nHmTwP', 'channel': 'Practical Preppers', 'category': 'survival', 'folder': 'Water & Sanitation'},
    {'title': 'Making Lye Soap from Scratch — Wood Ash and Animal Fat', 'url': 'https://www.youtube.com/watch?v=mJ4vNkwXpFo', 'channel': 'Townsends', 'category': 'cooking', 'folder': 'Food & Storage'},
    # Advanced Medical
    {'title': 'IV Fluid Therapy in the Field — Indications, Setup, and Complications', 'url': 'https://www.youtube.com/watch?v=GzHnS4kqPLx', 'channel': 'PrepMedic', 'category': 'medical', 'folder': 'First Aid & Medical'},
    {'title': 'Airway Management Without Equipment — Head Tilt, Jaw Thrust, NPA Insertion', 'url': 'https://www.youtube.com/watch?v=FxKp9vNtJyq', 'channel': 'Skinny Medic', 'category': 'medical', 'folder': 'First Aid & Medical'},
    {'title': 'Burn Treatment in the Field — Degrees, Cooling, and Infection Prevention', 'url': 'https://www.youtube.com/watch?v=pNkWc4gBmTz', 'channel': 'Corporals Corner', 'category': 'medical', 'folder': 'First Aid & Medical'},
    # Construction Techniques
    {'title': 'Adobe Brick Making — Mixing, Forming, and Curing Earth Blocks', 'url': 'https://www.youtube.com/watch?v=TsKlqY6pXZn', 'channel': 'Open Source Ecology', 'category': 'repair', 'folder': 'Shelter & Construction'},
    {'title': 'Dry Stone Wall Construction — No Mortar, No Tools Required', 'url': 'https://www.youtube.com/watch?v=RwLvzJ8NfYm', 'channel': 'My Self Reliance', 'category': 'repair', 'folder': 'Shelter & Construction'},
    # Foraging Deep Dives
    {'title': 'Acorn Processing — Leaching Tannins and Grinding Flour', 'url': 'https://www.youtube.com/watch?v=9XFhvkRqPSw', 'channel': 'Learn Your Land', 'category': 'bushcraft', 'folder': 'Food & Storage'},
    {'title': 'Cattail — The Ultimate Survival Plant (Roots to Pollen)', 'url': 'https://www.youtube.com/watch?v=bLVnT4Gq7Yw', 'channel': 'Black Scout Survival', 'category': 'bushcraft', 'folder': 'Food & Storage'},
    # Communications — Advanced
    {'title': 'HF Radio Propagation — Understanding Bands and Gray Line', 'url': 'https://www.youtube.com/watch?v=mCqPvRsFKtN', 'channel': 'Radio Prepper', 'category': 'radio', 'folder': 'Navigation & Comms'},
    {'title': 'Emergency Antenna Build — NVIS Dipole from Wire and PVC', 'url': 'https://www.youtube.com/watch?v=vHk3YpJrQwG', 'channel': 'OH8STN Julian OH8STN', 'category': 'radio', 'folder': 'Navigation & Comms'},
]

@media_bp.route('/api/videos')
def api_videos_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM videos ORDER BY folder, category, title LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    videos = []
    vdir = get_video_dir()
    for r in rows:
        v = dict(r)
        v['exists'] = os.path.isfile(os.path.join(vdir, r['filename']))
        videos.append(v)
    return jsonify(videos)

_ALLOWED_VIDEO_EXTS = {
    'mp4', 'mkv', 'webm', 'mov', 'm4v', 'avi', 'wmv', 'flv', 'mpg', 'mpeg',
    'ogv', 'ts',
}


def _ext_allowed(filename, allowed_exts):
    """True if *filename* has an extension in *allowed_exts* (case-insensitive)."""
    if not filename or '.' not in filename:
        return False
    return filename.rsplit('.', 1)[1].lower() in allowed_exts


@media_bp.route('/api/videos/upload', methods=['POST'])
def api_videos_upload():
    if 'file' not in request.files:
        return error_response('No file')
    file = request.files['file']
    # Check file size (max 500MB per upload)
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 500 * 1024 * 1024:
        return error_response('File too large (max 500MB)', 413)
    filename = secure_filename(file.filename or '')
    if not filename:
        return error_response('Invalid filename')
    if not _ext_allowed(filename, _ALLOWED_VIDEO_EXTS):
        return error_response(
            'Unsupported video extension. Allowed: ' + ', '.join(sorted(_ALLOWED_VIDEO_EXTS)),
            400,
        )
    filepath = os.path.join(get_video_dir(), filename)
    file.save(filepath)
    filesize = os.path.getsize(filepath) if os.path.isfile(filepath) else 0
    category = request.form.get('category', 'general')
    folder = _sanitize_folder(request.form.get('folder', ''))
    title = request.form.get('title', filename.rsplit('.', 1)[0]) or filename.rsplit('.', 1)[0]
    with db_session() as db:
        cur = db.execute('INSERT INTO videos (title, filename, category, folder, filesize) VALUES (?, ?, ?, ?, ?)',
                         (title, filename, category, folder, filesize))
        db.commit()
    log_activity('video_upload', 'media', title)
    return jsonify({'status': 'uploaded', 'id': cur.lastrowid}), 201

@media_bp.route('/api/videos/<int:vid>', methods=['DELETE'])
def api_videos_delete(vid):
    with db_session() as db:
        row = db.execute('SELECT filename, title FROM videos WHERE id = ?', (vid,)).fetchone()
        if row:
            vdir = get_video_dir()
            filepath = os.path.normpath(os.path.join(vdir, row['filename']))
            if os.path.normcase(filepath).startswith(os.path.normcase(vdir) + os.sep) and os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            db.execute('DELETE FROM videos WHERE id = ?', (vid,))
            db.commit()
            log_activity('video_delete', 'media', row['title'])
        return jsonify({'status': 'deleted'})
@media_bp.route('/api/videos/<int:vid>', methods=['PATCH'])
def api_videos_update(vid):
    data = request.get_json() or {}
    with db_session() as db:
        if 'title' in data:
            db.execute('UPDATE videos SET title = ? WHERE id = ?', (data['title'], vid))
        if 'folder' in data:
            db.execute('UPDATE videos SET folder = ? WHERE id = ?', (_sanitize_folder(data['folder']), vid))
        if 'category' in data:
            db.execute('UPDATE videos SET category = ? WHERE id = ?', (data['category'], vid))
        db.commit()
        return jsonify({'status': 'updated'})
@media_bp.route('/api/videos/serve/<path:filename>')
def api_videos_serve(filename):
    vdir = get_video_dir()
    safe = os.path.normcase(os.path.normpath(os.path.join(vdir, filename)))
    if not safe.startswith(os.path.normcase(os.path.normpath(vdir)) + os.sep) or not os.path.isfile(safe):
        return jsonify({'error': 'Not found'}), 404
    from flask import send_file
    return send_file(safe)

@media_bp.route('/api/videos/categories')
def api_videos_categories():
    return jsonify(VIDEO_CATEGORIES)

@media_bp.route('/api/videos/folders')
def api_videos_folders():
    with db_session() as db:
        rows = db.execute('SELECT DISTINCT folder FROM videos WHERE folder != "" ORDER BY folder').fetchall()
        return jsonify([r['folder'] for r in rows])
@media_bp.route('/api/videos/stats')
def api_videos_stats():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) as c FROM videos').fetchone()['c']
        total_size = db.execute('SELECT COALESCE(SUM(filesize),0) as s FROM videos').fetchone()['s']
        by_folder = db.execute('SELECT folder, COUNT(*) as c FROM videos GROUP BY folder ORDER BY folder').fetchall()
    return jsonify({
        'total': total,
        'total_size': total_size,
        'total_size_fmt': format_size(total_size),
        'by_folder': [{'folder': r['folder'] or 'Unsorted', 'count': r['c']} for r in by_folder],
    })

AUDIO_CATALOG = [
    # HAM Radio & Communications Training
    {'title': 'Ham Radio Crash Course - Technician License', 'url': 'https://www.youtube.com/watch?v=Krc15VfkRJA', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Radio Training'},
    {'title': 'Emergency Communications - ARES/RACES Intro', 'url': 'https://www.youtube.com/watch?v=9acOfs8gYlk', 'channel': 'Ham Radio 2.0', 'category': 'radio', 'folder': 'Radio Training'},
    {'title': 'Morse Code Training - Learn CW', 'url': 'https://www.youtube.com/watch?v=D8tPkb98Fkk', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Radio Training'},
    # Survival Skills Audio
    {'title': 'Wilderness Survival Skills - Complete Audio Guide', 'url': 'https://www.youtube.com/watch?v=oBp7LoFxdhU', 'channel': 'Survival On Purpose', 'category': 'survival', 'folder': 'Survival Skills'},
    {'title': 'Prepper Mindset - Mental Preparedness', 'url': 'https://www.youtube.com/watch?v=qxNjJPHzN-o', 'channel': 'Canadian Prepper', 'category': 'survival', 'folder': 'Survival Skills'},
    {'title': 'Bushcraft Skills Every Prepper Needs', 'url': 'https://www.youtube.com/watch?v=k4vee-NTkds', 'channel': 'TA Outdoors', 'category': 'bushcraft', 'folder': 'Survival Skills'},
    # Medical Audio Training
    {'title': 'Tactical First Aid - TCCC Basics', 'url': 'https://www.youtube.com/watch?v=J6-nFr-pn4A', 'channel': 'Skinny Medic', 'category': 'medical', 'folder': 'Medical Training'},
    {'title': 'Herbal Medicine Fundamentals', 'url': 'https://www.youtube.com/watch?v=HQdXn_bDiIs', 'channel': 'Survival Dispatch', 'category': 'medical', 'folder': 'Medical Training'},
    # Homesteading & Self-Reliance
    {'title': 'Permaculture Design Principles', 'url': 'https://www.youtube.com/watch?v=cEBtmjaFU28', 'channel': 'Happen Films', 'category': 'farming', 'folder': 'Homesteading'},
    {'title': 'Food Preservation - Complete Guide', 'url': 'https://www.youtube.com/watch?v=WKwMoeBPMJ8', 'channel': 'Townsends', 'category': 'cooking', 'folder': 'Homesteading'},
    # Situational Awareness & Security
    {'title': 'Situational Awareness - Gray Man Concept', 'url': 'https://www.youtube.com/watch?v=_sRjSR_B2Bc', 'channel': 'City Prepping', 'category': 'defense', 'folder': 'Security & Defense'},
    {'title': 'Home Defense Strategies', 'url': 'https://www.youtube.com/watch?v=mSCGGr8B0W8', 'channel': 'Warrior Poet Society', 'category': 'defense', 'folder': 'Security & Defense'},
    # Additional Radio Training
    {'title': 'NVIS Antennas for Emergency Communications', 'url': 'https://www.youtube.com/watch?v=TfhxTZkCJnE', 'channel': 'Off-Grid Ham', 'category': 'radio', 'folder': 'Radio Training'},
    {'title': 'Digital Modes for Emergency Comms — JS8Call and Winlink', 'url': 'https://www.youtube.com/watch?v=YhwrPTR5P3c', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Radio Training'},
    {'title': 'Winlink Email Over Radio — Grid-Down Communications', 'url': 'https://www.youtube.com/watch?v=n9_x3APmR3I', 'channel': 'K8MRD Radio Activities', 'category': 'radio', 'folder': 'Radio Training'},
    {'title': 'ARES Emergency Activation and Net Operations', 'url': 'https://www.youtube.com/watch?v=mGhBcIm7X4A', 'channel': 'Ham Radio 2.0', 'category': 'radio', 'folder': 'Radio Training'},
    {'title': 'HF Radio for Preppers — Shortwave Listening and DX', 'url': 'https://www.youtube.com/watch?v=hpQBJ5gcYWk', 'channel': 'Radio Prepper', 'category': 'radio', 'folder': 'Radio Training'},
    {'title': 'Baofeng UV-5R Complete Programming Guide', 'url': 'https://www.youtube.com/watch?v=wF9hkG1GpSg', 'channel': 'Tin Hat Ranch', 'category': 'radio', 'folder': 'Radio Training'},
    # Additional Survival Skills Audio
    {'title': 'Winter Survival — Hypothermia Prevention and Recovery', 'url': 'https://www.youtube.com/watch?v=U0vBpCLz2Rg', 'channel': 'Coalcracker Bushcraft', 'category': 'survival', 'folder': 'Survival Skills'},
    {'title': 'Navigation by Stars — Polaris and Southern Cross', 'url': 'https://www.youtube.com/watch?v=LXiYW2CKVLQ', 'channel': 'Black Scout Survival', 'category': 'survival', 'folder': 'Survival Skills'},
    {'title': 'Surviving Extreme Heat — Desert and Urban Heat Emergencies', 'url': 'https://www.youtube.com/watch?v=qFiC8kS8bVg', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Survival Skills'},
    {'title': 'Urban Survival — Bugging Out from the City', 'url': 'https://www.youtube.com/watch?v=HSTrM0pXnCA', 'channel': 'The Urban Prepper', 'category': 'survival', 'folder': 'Survival Skills'},
    {'title': 'Knot Tying Masterclass — 20 Essential Knots', 'url': 'https://www.youtube.com/watch?v=VrSBsqe23Qk', 'channel': 'ITS Tactical', 'category': 'bushcraft', 'folder': 'Survival Skills'},
    {'title': 'Bow Drill Fire Starting — Complete Technique Guide', 'url': 'https://www.youtube.com/watch?v=lR-LrU0zA0Y', 'channel': 'Coalcracker Bushcraft', 'category': 'bushcraft', 'folder': 'Survival Skills'},
    # Additional Medical Training
    {'title': 'Wound Care and Infection Prevention in the Field', 'url': 'https://www.youtube.com/watch?v=JR2IABjLJBY', 'channel': 'Corporals Corner', 'category': 'medical', 'folder': 'Medical Training'},
    {'title': 'Improvised Medications and Herbal Antibiotics', 'url': 'https://www.youtube.com/watch?v=1hpEL7Jy_HI', 'channel': 'DrBones NurseAmy', 'category': 'medical', 'folder': 'Medical Training'},
    {'title': 'Managing Childbirth Emergency — Obstetric Crisis Without a Doctor', 'url': 'https://www.youtube.com/watch?v=u3x0JPCHDOQ', 'channel': 'Survival Dispatch', 'category': 'medical', 'folder': 'Medical Training'},
    {'title': 'Pediatric First Aid — Children\'s Emergencies in the Field', 'url': 'https://www.youtube.com/watch?v=MX0kB-x_XPg', 'channel': 'PrepMedic', 'category': 'medical', 'folder': 'Medical Training'},
    {'title': 'Diabetic Emergencies — Hypo and Hyperglycemia Without Insulin', 'url': 'https://www.youtube.com/watch?v=CqJNQkVLI_4', 'channel': 'DrBones NurseAmy', 'category': 'medical', 'folder': 'Medical Training'},
    # FEMA / Emergency Management
    {'title': 'FEMA IS-100: Introduction to Incident Command System', 'url': 'https://www.youtube.com/watch?v=YsA4VhAWsSE', 'channel': 'FEMA', 'category': 'survival', 'folder': 'Emergency Management'},
    {'title': 'Community Emergency Response Team (CERT) Training Overview', 'url': 'https://www.youtube.com/watch?v=JVuxCgo8mWM', 'channel': 'FEMA', 'category': 'survival', 'folder': 'Emergency Management'},
    {'title': 'Shelter-in-Place — When to Stay and How to Prepare', 'url': 'https://www.youtube.com/watch?v=_GNh3p1GFAI', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Emergency Management'},
    {'title': 'Mass Casualty Incident — START Triage for Civilians', 'url': 'https://www.youtube.com/watch?v=CSiuSIFDcuI', 'channel': 'Skinny Medic', 'category': 'medical', 'folder': 'Emergency Management'},
    # Additional Homesteading & Food Production
    {'title': 'Sprouting Seeds for Winter Nutrition', 'url': 'https://www.youtube.com/watch?v=OGkRUHl-dbw', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Homesteading'},
    {'title': 'Traditional Soap Making from Wood Ash Lye', 'url': 'https://www.youtube.com/watch?v=gJ7fPmNqRkL', 'channel': 'Townsends', 'category': 'cooking', 'folder': 'Homesteading'},
    {'title': 'Natural Beekeeping — Top-Bar Hive Management', 'url': 'https://www.youtube.com/watch?v=MmLeKkEa7J0', 'channel': 'Stoney Ridge Farmer', 'category': 'farming', 'folder': 'Homesteading'},
    {'title': 'Tallow Rendering — Processing Beef Fat for Cooking, Candles, and Soap', 'url': 'https://www.youtube.com/watch?v=pLkRnB8cTqW', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Homesteading'},
    # Nuclear & CBRN
    {'title': 'Nuclear Fallout Shelter — Design and Protective Measures', 'url': 'https://www.youtube.com/watch?v=9X7_xI5tGzQ', 'channel': 'Practical Preppers', 'category': 'survival', 'folder': 'Nuclear & CBRN'},
    {'title': 'Radiation Detection — Using Dosimeters and Geiger Counters', 'url': 'https://www.youtube.com/watch?v=xhmReScCzE4', 'channel': "Prepper's Paradigm", 'category': 'survival', 'folder': 'Nuclear & CBRN'},
    {'title': 'Chemical Warfare Agent Decontamination — Personal and Area', 'url': 'https://www.youtube.com/watch?v=AUxTRyqp5qg', 'channel': 'Practical Preppers', 'category': 'survival', 'folder': 'Nuclear & CBRN'},
    # Off-Grid Power
    {'title': 'Propane vs. Natural Gas Conversion for Generators', 'url': 'https://www.youtube.com/watch?v=k_jVk2Q2sJY', 'channel': 'Engineer775', 'category': 'repair', 'folder': 'Power Systems'},
    {'title': 'Battery Bank Sizing for Off-Grid Living', 'url': 'https://www.youtube.com/watch?v=W0Miu0mihVE', 'channel': 'DIY Solar Power (Will Prowse)', 'category': 'repair', 'folder': 'Power Systems'},
    {'title': 'Wood Gasification — Running Engines on Wood', 'url': 'https://www.youtube.com/watch?v=egyNJ9HKMeo', 'channel': 'Open Source Ecology', 'category': 'repair', 'folder': 'Power Systems'},
    # Weather & Climate Training
    {'title': 'Skywarn Storm Spotter Training — NWS Official Course', 'url': 'https://www.youtube.com/watch?v=5D3f9ReBnNI', 'channel': 'The COMET Program', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'Understanding CAPE and Severe Weather Parameters', 'url': 'https://www.youtube.com/watch?v=F5xZ5Jm5Gmw', 'channel': 'The COMET Program', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'El Niño and La Niña — What They Mean for Your Region', 'url': 'https://www.youtube.com/watch?v=WPA-KpldDVc', 'channel': 'NOAA Satellites and Information', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'Atmospheric Rivers — Extreme Precipitation Explained', 'url': 'https://www.youtube.com/watch?v=xqBwLMxU4UM', 'channel': 'Cliff Mass Weather', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'Wildfire Weather — Red Flag Warnings and Fire Behavior', 'url': 'https://www.youtube.com/watch?v=vKMuq7J0U1g', 'channel': 'NWS Headquarters', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'Frost Dates and Growing Season — Using Climate Data for Gardening', 'url': 'https://www.youtube.com/watch?v=s3N0RFz9V0Y', 'channel': 'Epic Gardening', 'category': 'farming', 'folder': 'Weather & Climate'},
    {'title': 'Drought Recognition and Water Conservation Planning', 'url': 'https://www.youtube.com/watch?v=pQ2lIpnFB8M', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Weather & Climate'},
    {'title': 'Reading Surface Analysis Maps — Understanding Weather Systems', 'url': 'https://www.youtube.com/watch?v=7bNgZ-BQOo8', 'channel': 'The COMET Program', 'category': 'survival', 'folder': 'Weather & Climate'},
    # Maps & Geospatial Training
    {'title': 'How to Download and Use USGS Topo Quads Offline', 'url': 'https://www.youtube.com/watch?v=BpFCOeR02SU', 'channel': 'USGS (US Geological Survey)', 'category': 'survival', 'folder': 'Maps & Navigation'},
    {'title': 'QGIS Basics for Preppers — Free Offline Mapping', 'url': 'https://www.youtube.com/watch?v=RTjAp6dqvsM', 'channel': 'GIS Geography', 'category': 'survival', 'folder': 'Maps & Navigation'},
    {'title': 'NOAA Satellite Imagery — Reading Weather and Land Patterns', 'url': 'https://www.youtube.com/watch?v=m5JV6fRtFjk', 'channel': 'NOAA Satellites and Information', 'category': 'survival', 'folder': 'Maps & Navigation'},
    {'title': 'OsmAnd Offline Maps Setup — Full Tutorial', 'url': 'https://www.youtube.com/watch?v=FNLnLKuXjrU', 'channel': 'GIS Geography', 'category': 'survival', 'folder': 'Maps & Navigation'},
    # Primitive & Bushcraft Skills
    {'title': 'Primitive Bow Making — Self Bow from Raw Wood', 'url': 'https://www.youtube.com/watch?v=sTfxmFNInAU', 'channel': 'Primitive Technology', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
    {'title': 'Snare Trapping for Small Game — Legal and Effective Methods', 'url': 'https://www.youtube.com/watch?v=gLDIpbS3OeI', 'channel': 'My Self Reliance', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
    {'title': 'Brain Tanning Hides — Processing Deer and Rabbit Pelts', 'url': 'https://www.youtube.com/watch?v=d5MZf_mj9qU', 'channel': 'Coalcracker Bushcraft', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
    {'title': 'Primitive Fire Starting — Bow Drill, Hand Drill, Flint and Steel', 'url': 'https://www.youtube.com/watch?v=VKTFmEFKuEw', 'channel': 'Survival Lilly', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
    {'title': 'Basket Weaving for Beginners — Functional Containers from Natural Materials', 'url': 'https://www.youtube.com/watch?v=O2QmYJWUhWI', 'channel': 'NativeTech', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
    # Food Preservation Deep Dives
    {'title': 'Lacto-Fermentation Fundamentals — Sauerkraut, Pickles, Kimchi Without Canning', 'url': 'https://www.youtube.com/watch?v=0z3vSe-GR3A', 'channel': 'Farmhouse on Boone', 'category': 'cooking', 'folder': 'Food & Storage'},
    {'title': 'Smoking Meat for Long-Term Preservation — Build Your Own Smoker', 'url': 'https://www.youtube.com/watch?v=aK0XKXG5Nsg', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Food & Storage'},
    {'title': 'Salt Curing Meat — Historical Preservation Without Refrigeration', 'url': 'https://www.youtube.com/watch?v=WqoORPLAYGM', 'channel': 'BBQ with Franklin', 'category': 'cooking', 'folder': 'Food & Storage'},
    {'title': 'Pressure Canning Safety — Botulism Prevention and Tested Recipes', 'url': 'https://www.youtube.com/watch?v=P4kO27fy7u4', 'channel': 'Ball Mason Jars', 'category': 'cooking', 'folder': 'Food & Storage'},
    {'title': 'Dehydrating Complete Meals — Backpacking and Emergency Rations', 'url': 'https://www.youtube.com/watch?v=5_QkMFhJxPc', 'channel': 'Fresh Off The Grid', 'category': 'cooking', 'folder': 'Food & Storage'},
    # Water Treatment Advanced
    {'title': 'Slow Sand Filtration — DIY Biosand Filter Construction', 'url': 'https://www.youtube.com/watch?v=N7TFJcg-CWI', 'channel': 'CAWST Centre for Affordable Water', 'category': 'survival', 'folder': 'Water & Sanitation'},
    {'title': 'Solar Water Disinfection (SODIS) — WHO-Endorsed Method for Clear Bottles', 'url': 'https://www.youtube.com/watch?v=hd0LAqtIMLk', 'channel': 'Practical Action', 'category': 'survival', 'folder': 'Water & Sanitation'},
    {'title': 'Emergency Well Construction — Driven Point Wells for Shallow Aquifers', 'url': 'https://www.youtube.com/watch?v=8sLn9REq0ok', 'channel': 'Practical Engineering', 'category': 'survival', 'folder': 'Water & Sanitation'},
    # Medicinal & Foraging
    {'title': 'Medicinal Mushrooms — Identification and Preparation of Immune-Boosting Species', 'url': 'https://www.youtube.com/watch?v=rG0TKdFlNpc', 'channel': 'Healing Harvest Homestead', 'category': 'medical', 'folder': 'Medical Training'},
    {'title': 'Herbal Wound Care — Plantain, Yarrow, and Comfrey Poultices', 'url': 'https://www.youtube.com/watch?v=TkmVUhwK_28', 'channel': 'Herbal Prepper', 'category': 'medical', 'folder': 'Medical Training'},
    {'title': 'Essential Oils in Emergency Medicine — Evidence and Cautions', 'url': 'https://www.youtube.com/watch?v=oBSAWxQqRGc', 'channel': 'Dr. Josh Axe', 'category': 'medical', 'folder': 'Medical Training'},
    # Security & Defense Training
    {'title': 'Perimeter Security — Early Warning Systems Using Minimal Materials', 'url': 'https://www.youtube.com/watch?v=xP0hROQvNFY', 'channel': 'ITS Tactical', 'category': 'security', 'folder': 'Security & Defense'},
    {'title': 'Vehicle Security and Anti-Carjacking Awareness', 'url': 'https://www.youtube.com/watch?v=MXN4fOLwAzw', 'channel': 'PDN (Personal Defense Network)', 'category': 'security', 'folder': 'Security & Defense'},
    {'title': 'Night Vision and Thermal — Choosing the Right Optic for SHTF', 'url': 'https://www.youtube.com/watch?v=R2H7UM9gAJw', 'channel': 'Garand Thumb', 'category': 'security', 'folder': 'Security & Defense'},
    # Repair & Mechanical Skills
    {'title': 'Small Engine Repair — Generators, Chainsaws, and Tillers', 'url': 'https://www.youtube.com/watch?v=K5q_i8jVRiA', 'channel': 'LawnMowerPros', 'category': 'repair', 'folder': 'Tools & Repair'},
    {'title': 'Introduction to Arc Welding — Basic Techniques for Beginners', 'url': 'https://www.youtube.com/watch?v=7p-UMiqkeMI', 'channel': 'welding tips and tricks', 'category': 'repair', 'folder': 'Tools & Repair'},
    {'title': 'Basic Plumbing Repairs Without a Plumber — Pipes, Valves, and Fixtures', 'url': 'https://www.youtube.com/watch?v=yY3WLEg0bYI', 'channel': 'This Old House', 'category': 'repair', 'folder': 'Tools & Repair'},
    {'title': 'Hand Tool Woodworking — Bench Plane, Chisel, and Hand Saw Mastery', 'url': 'https://www.youtube.com/watch?v=XEpAEFV6M8E', 'channel': 'Paul Sellers', 'category': 'repair', 'folder': 'Tools & Repair'},
    {'title': 'Blacksmithing for Beginners — Coal and Propane Forge Basics', 'url': 'https://www.youtube.com/watch?v=sNjJ-M_zQjI', 'channel': 'Black Bear Forge', 'category': 'repair', 'folder': 'Tools & Repair'},
    {'title': 'Sharpening Knives, Axes, and Tools — Whetstone, Strop, and Jig Methods', 'url': 'https://www.youtube.com/watch?v=3xXLjEi5j6c', 'channel': 'Outdoors55', 'category': 'repair', 'folder': 'Tools & Repair'},
    # Animal Husbandry
    {'title': 'Raising Meat Rabbits — Breed Selection, Housing, and Processing', 'url': 'https://www.youtube.com/watch?v=pYA8Gz6B9hA', 'channel': 'Justin Rhodes', 'category': 'farming', 'folder': 'Animal Husbandry'},
    {'title': 'Dairy Goats for Beginners — Breed Selection, Milking, and Kidding', 'url': 'https://www.youtube.com/watch?v=w7Px_7GCTII', 'channel': 'Becky\'s Homestead', 'category': 'farming', 'folder': 'Animal Husbandry'},
    {'title': 'Backyard Chickens — Health, Egg Production, and Flock Management', 'url': 'https://www.youtube.com/watch?v=HzSdCl4XrNI', 'channel': 'Stoney Ridge Farmer', 'category': 'farming', 'folder': 'Animal Husbandry'},
    {'title': 'Hog Processing and Butchery — Farm to Table Without a Processor', 'url': 'https://www.youtube.com/watch?v=5GMM0RiJGlc', 'channel': 'Homesteading Family', 'category': 'farming', 'folder': 'Animal Husbandry'},
    {'title': 'Veterinary Basics for Livestock — Wound Care, Parasite Control, Birthing Assist', 'url': 'https://www.youtube.com/watch?v=3YpX68gHXYE', 'channel': 'The Holistic Hen', 'category': 'medical', 'folder': 'Animal Husbandry'},
    # Community Organization & Grid-Down Economics
    {'title': 'Barter Economy — What to Stock and How to Trade After SHTF', 'url': 'https://www.youtube.com/watch?v=LX5bpBJpz_M', 'channel': 'Canadian Prepper', 'category': 'survival', 'folder': 'Community & Economics'},
    {'title': 'Community Organizing After Disaster — Mutual Aid and Group Governance', 'url': 'https://www.youtube.com/watch?v=7lHm4R6Qf5E', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Community & Economics'},
    {'title': 'Grid-Down Sanitation — Composting Toilets, Latrines, and Hygiene Without Utilities', 'url': 'https://www.youtube.com/watch?v=dUqK9B4-MBI', 'channel': 'Practical Preppers', 'category': 'survival', 'folder': 'Water & Sanitation'},
    {'title': 'Ham Radio License Study — Technician Pool Q&A All 300 Questions', 'url': 'https://www.youtube.com/watch?v=HNmzjBMPLRQ', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Radio Training'},
    # Dental & Specialized Medical
    {'title': 'Emergency Dental Care — Abscess Treatment and Tooth Extraction Techniques', 'url': 'https://www.youtube.com/watch?v=oY9oQ9wjPyE', 'channel': 'DrBones NurseAmy', 'category': 'medical', 'folder': 'Medical Training'},
    {'title': 'Eye Emergencies — Foreign Bodies, Trauma, and Chemical Exposure Without a Doctor', 'url': 'https://www.youtube.com/watch?v=HLfGkqAZtG0', 'channel': 'PrepMedic', 'category': 'medical', 'folder': 'Medical Training'},
    {'title': 'Improvised Stretcher and Patient Transport — Moving Casualties Without Equipment', 'url': 'https://www.youtube.com/watch?v=vJ45K4qW-kI', 'channel': 'Corporals Corner', 'category': 'medical', 'folder': 'Medical Training'},
    # Grid-Down Transportation & Mobility
    {'title': 'Bicycle Repair and Maintenance — Grid-Down Transportation', 'url': 'https://www.youtube.com/watch?v=rJw2PFv8q3N', 'channel': 'Park Tool', 'category': 'repair', 'folder': 'Tools & Repair'},
    {'title': 'Diesel Engine Basics — Why Diesel Survives When Gas Doesn\'t', 'url': 'https://www.youtube.com/watch?v=Km5FcTy9NxV', 'channel': 'EricTheCarGuy', 'category': 'repair', 'folder': 'Tools & Repair'},
    # Advanced Water Skills
    {'title': 'Ram Pump Installation — Water Without Electricity Using Gravity', 'url': 'https://www.youtube.com/watch?v=sHp3QkqGxJN', 'channel': 'Engineer775', 'category': 'survival', 'folder': 'Water & Sanitation'},
    {'title': 'Greywater Recycling for Garden Irrigation — Simple DIY Systems', 'url': 'https://www.youtube.com/watch?v=tWq7RmCjFkZ', 'channel': 'Practical Preppers', 'category': 'survival', 'folder': 'Water & Sanitation'},
    # Communications — Supplemental
    {'title': 'DMR Radio Programming — Hotspots, Code Plugs, and Talk Groups', 'url': 'https://www.youtube.com/watch?v=nHqT3eMjLRb', 'channel': 'Ham Radio 2.0', 'category': 'radio', 'folder': 'Radio Training'},
    {'title': 'Antenna Theory for Beginners — Dipoles, Verticals, and Yagi Designs', 'url': 'https://www.youtube.com/watch?v=kYz8PwVrsMd', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Radio Training'},
    # Mental Preparedness & Stress
    {'title': 'Tactical Breathing and Stress Inoculation — Military Mental Techniques', 'url': 'https://www.youtube.com/watch?v=hLcWBqGsfXc', 'channel': 'Warrior Poet Society', 'category': 'survival', 'folder': 'Survival Skills'},
    {'title': 'Grief and Loss Management During Long-Term Emergencies', 'url': 'https://www.youtube.com/watch?v=pQm8sJvXnRw', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Emergency Management'},
    # Advanced Food Production
    {'title': 'Mushroom Cultivation — Growing Oyster and Shiitake on Logs and Straw', 'url': 'https://www.youtube.com/watch?v=tRkFnJ4mGsY', 'channel': 'FreshCap Mushrooms', 'category': 'farming', 'folder': 'Homesteading'},
    {'title': 'Greenhouse Heating Without Electricity — Thermal Mass and Compost Heat', 'url': 'https://www.youtube.com/watch?v=wNb6qVkJpTc', 'channel': 'Stoney Ridge Farmer', 'category': 'farming', 'folder': 'Homesteading'},
]

@media_bp.route('/api/audio/catalog')
def api_audio_catalog():
    return jsonify(AUDIO_CATALOG)


@media_bp.route('/api/channels/catalog')
def api_channels_catalog():
    with db_session() as db:
        dead_row = db.execute("SELECT value FROM settings WHERE key = 'dead_channels'").fetchone()
    dead_urls = set(_safe_string_list(dead_row['value'] if dead_row else None))
    live = [c for c in CHANNEL_CATALOG if c['url'] not in dead_urls]
    category = request.args.get('category', '')
    if category:
        return jsonify([c for c in live if c['category'] == category])
    return jsonify(live)

@media_bp.route('/api/channels/categories')
def api_channels_categories():
    from collections import Counter
    with db_session() as db:
        dead_row = db.execute("SELECT value FROM settings WHERE key = 'dead_channels'").fetchone()
    dead_urls = set(_safe_string_list(dead_row['value'] if dead_row else None))
    live = [c for c in CHANNEL_CATALOG if c['url'] not in dead_urls]
    counts = Counter(c['category'] for c in live)
    cats = sorted(counts.keys())
    return jsonify([{'name': cat, 'count': counts[cat]} for cat in cats])

@media_bp.route('/api/channels/validate', methods=['POST'])
def api_channels_validate():
    """Check a channel URL — mark dead if no videos found."""
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'No URL'}), 400
    exe = get_ytdlp_path()
    if not os.path.isfile(exe):
        return jsonify({'error': 'Downloader not installed'}), 400
    try:
        result = subprocess.run(
            [exe, '--flat-playlist', '--dump-json', '--playlist-end', '1', url + '/videos'],
            capture_output=True, text=True, timeout=20, **_CREATION_FLAGS,
        )
        alive = result.returncode == 0 and bool(result.stdout.strip())
        if not alive:
            with db_session() as db:
                row = db.execute("SELECT value FROM settings WHERE key = 'dead_channels'").fetchone()
                dead = _safe_string_list(row['value'] if row else None)
                if url not in dead:
                    dead.append(url)
                    if row:
                        db.execute("UPDATE settings SET value = ? WHERE key = 'dead_channels'", (json.dumps(dead),))
                    else:
                        db.execute("INSERT INTO settings (key, value) VALUES ('dead_channels', ?)", (json.dumps(dead),))
                    db.commit()
        return jsonify({'url': url, 'alive': alive})
    except subprocess.TimeoutExpired:
        return jsonify({'url': url, 'alive': True})
    except Exception as e:
        log.exception('Channel alive check failed')
        return jsonify({'error': 'Check failed'}), 500

# ─── Cross-catalog media search ──────────────────────────────────

@media_bp.route('/api/media/search')
def api_media_search():
    """Unified search across videos, audio, books, and the channel catalog.

    The Media tab historically forced users to search each sub-tab (videos,
    audio, books, torrents, channels) independently, which is painful when
    the combined corpus is 700+ curated items. This endpoint takes a single
    ``q`` query parameter, runs a case-insensitive LIKE across the local
    media tables plus the in-memory ``CHANNEL_CATALOG``, and returns one
    normalised result list so the frontend can render a single dropdown.

    Each result has:
        type: 'video' | 'audio' | 'book' | 'channel'
        id:   integer row id (local tables) or slug (channels)
        title: display label
        subtitle: category / folder / channel hint
    """
    query = (request.args.get('q') or '').strip()
    if not query or len(query) < 2:
        return jsonify({'results': []})
    # Cap the query length so an accidental 10 KB paste doesn't hit SQLite
    # with a gigantic LIKE pattern.
    query = query[:120]
    try:
        limit = min(max(int(request.args.get('limit', '20')), 1), 100)
    except (TypeError, ValueError):
        limit = 20

    like = f'%{query}%'
    results = []
    with db_session() as db:
        # Each SELECT is parameterised; the LIKE pattern is bound, not
        # interpolated. We cap per-source at the full limit to keep the
        # query cheap and then dedupe/trim at the end.
        for media_type, table, subtitle_col in (
            ('video', 'videos', 'category'),
            ('audio', 'audio', 'category'),
            ('book', 'books', 'category'),
        ):
            try:
                rows = db.execute(
                    f'SELECT id, title, {subtitle_col} AS subtitle, folder '
                    f'FROM {table} '
                    'WHERE title LIKE ? OR folder LIKE ? '
                    'ORDER BY id DESC LIMIT ?',
                    (like, like, limit),
                ).fetchall()
            except Exception as exc:
                # A missing table (fresh install, migration gap) must not
                # take down the whole search.
                log.debug('Media search skipped %s: %s', table, exc)
                continue
            for r in rows:
                folder = r['folder'] or ''
                subtitle = r['subtitle'] or ''
                hint_parts = [p for p in (subtitle, folder) if p]
                results.append({
                    'type': media_type,
                    'id': r['id'],
                    'title': r['title'] or '(untitled)',
                    'subtitle': ' / '.join(hint_parts) or media_type,
                })

    # Channel catalog is in-memory so we search it with pure Python.
    q_lower = query.lower()
    try:
        for ch in CHANNEL_CATALOG or []:
            if not isinstance(ch, dict):
                continue
            hay = ' '.join(str(ch.get(k, '') or '') for k in ('name', 'description', 'category'))
            if q_lower in hay.lower():
                results.append({
                    'type': 'channel',
                    'id': ch.get('id') or ch.get('url') or ch.get('name'),
                    'title': ch.get('name', '(unnamed)'),
                    'subtitle': ch.get('category') or 'Channel',
                })
                if len(results) >= limit * 4:
                    break
    except Exception as exc:
        log.debug('Channel catalog search failed: %s', exc)

    # Simple relevance sort: exact-match titles first, then prefix matches,
    # then contains-matches, preserving insertion order within each tier.
    def _rank(item):
        t = (item.get('title') or '').lower()
        if t == q_lower:
            return 0
        if t.startswith(q_lower):
            return 1
        return 2
    results.sort(key=_rank)
    return jsonify({'results': results[:limit], 'query': query, 'count': len(results)})


# ─── YouTube Search & Channel Videos ─────────────────────────────

@media_bp.route('/api/youtube/search')
def api_youtube_search():
    """Search YouTube via yt-dlp and return video metadata."""
    query = request.args.get('q', '').strip()
    try:
        limit = min(int(request.args.get('limit', '12')), 30)
    except (ValueError, TypeError):
        limit = 12
    if not query:
        return jsonify([])
    exe = get_ytdlp_path()
    if not os.path.isfile(exe):
        return jsonify({'error': 'Downloader not installed'}), 400
    try:
        result = subprocess.run(
            [exe, '--flat-playlist', '--dump-json', f'ytsearch{limit}:{query}'],
            capture_output=True, text=True, timeout=30, **_CREATION_FLAGS,
        )
        videos = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            d = _load_json_line(line, {})
            if not isinstance(d, dict):
                continue
            thumb = ''
            if d.get('thumbnails'):
                thumb = d['thumbnails'][-1].get('url', '')
            elif d.get('thumbnail'):
                thumb = d['thumbnail']
            videos.append({
                'id': d.get('id', ''),
                'title': d.get('title', ''),
                'channel': d.get('channel', d.get('uploader', '')),
                'duration': d.get('duration_string', ''),
                'views': d.get('view_count', 0),
                'thumbnail': thumb,
                'url': f"https://www.youtube.com/watch?v={d.get('id', '')}",
            })
        return jsonify(videos)
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Search timed out'}), 504
    except Exception as e:
        log.exception('YouTube search failed')
        return jsonify({'error': 'Search failed'}), 500

@media_bp.route('/api/youtube/channel-videos')
def api_youtube_channel_videos():
    """List recent videos from a YouTube channel."""
    channel_url = request.args.get('url', '').strip()
    try:
        limit = min(int(request.args.get('limit', '12')), 50)
    except (ValueError, TypeError):
        limit = 12
    if not channel_url:
        return jsonify([])
    exe = get_ytdlp_path()
    if not os.path.isfile(exe):
        return jsonify({'error': 'Downloader not installed'}), 400
    try:
        result = subprocess.run(
            [exe, '--flat-playlist', '--dump-json', '--playlist-end', str(limit),
             channel_url + '/videos'],
            capture_output=True, text=True, timeout=45, **_CREATION_FLAGS,
        )
        videos = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            d = _load_json_line(line, {})
            if not isinstance(d, dict):
                continue
            thumb = ''
            if d.get('thumbnails'):
                thumb = d['thumbnails'][-1].get('url', '')
            elif d.get('thumbnail'):
                thumb = d['thumbnail']
            videos.append({
                'id': d.get('id', ''),
                'title': d.get('title', ''),
                'channel': d.get('channel', d.get('uploader', '')),
                'duration': d.get('duration_string', ''),
                'views': d.get('view_count', 0),
                'thumbnail': thumb,
                'url': f"https://www.youtube.com/watch?v={d.get('id', '')}",
            })
        return jsonify(videos)
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Request timed out'}), 504
    except Exception as e:
        log.exception('Channel videos fetch failed')
        return jsonify({'error': 'Failed to fetch channel videos'}), 500

# ─── Channel Subscriptions ──────────────────────────────────────
@media_bp.route('/api/subscriptions')
def api_subscriptions_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM subscriptions ORDER BY channel_name LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])
@media_bp.route('/api/subscriptions', methods=['POST'])
def api_subscriptions_add():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    url = data.get('url', '').strip()
    category = data.get('category', '')
    if not name or not url:
        return jsonify({'error': 'Name and URL required'}), 400
    with db_session() as db:
      try:
        db.execute('INSERT INTO subscriptions (channel_name, channel_url, category) VALUES (?, ?, ?)', (name, url, category))
        db.commit()
        return jsonify({'status': 'subscribed'})
      except Exception:
        return jsonify({'error': 'Already subscribed'}), 409
@media_bp.route('/api/subscriptions/<int:sid>', methods=['DELETE'])
def api_subscriptions_delete(sid):
    with db_session() as db:
        r = db.execute('DELETE FROM subscriptions WHERE id = ?', (sid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
        return jsonify({'status': 'unsubscribed'})
# ─── Media Shared Endpoints (favorites, batch) ────────────────────

@media_bp.route('/api/media/favorite', methods=['POST'])
def api_media_favorite():
    data = request.get_json() or {}
    media_type = data.get('type', 'videos')
    media_id = data.get('id')
    _MEDIA_TABLES = {'videos', 'audio', 'books'}
    table_map = {'videos': 'videos', 'audio': 'audio', 'books': 'books'}
    table = safe_table(table_map.get(media_type, ''), _MEDIA_TABLES) if table_map.get(media_type) else None
    if not table or not media_id:
        return jsonify({'error': 'Invalid request'}), 400
    with db_session() as db:
        row = db.execute(f'SELECT favorited FROM {table} WHERE id = ?', (media_id,)).fetchone()
        new_val = 0
        if row:
            new_val = 0 if row['favorited'] else 1
            db.execute(f'UPDATE {table} SET favorited = ? WHERE id = ?', (new_val, media_id))
            db.commit()
        return jsonify({'status': 'toggled', 'favorited': new_val})
@media_bp.route('/api/media/batch-delete', methods=['POST'])
def api_media_batch_delete():
    data = request.get_json() or {}
    media_type = data.get('type', 'videos')
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'error': 'No IDs provided'}), 400
    _MEDIA_TABLES = {'videos', 'audio', 'books'}
    table_map = {'videos': 'videos', 'audio': 'audio', 'books': 'books'}
    dir_map = {'videos': get_video_dir, 'audio': get_audio_dir, 'books': get_books_dir}
    table = safe_table(table_map.get(media_type, ''), _MEDIA_TABLES) if table_map.get(media_type) else None
    get_dir = dir_map.get(media_type)
    if not table or not get_dir:
        return jsonify({'error': 'Invalid type'}), 400
    with db_session() as db:
        media_dir = get_dir()
        media_dir_nc = os.path.normcase(os.path.normpath(media_dir)) + os.sep
        deleted = 0
        for mid in ids:
            row = db.execute(f'SELECT filename FROM {table} WHERE id = ?', (mid,)).fetchone()
            if row:
                filepath = os.path.normpath(os.path.join(media_dir, row['filename']))
                if os.path.normcase(filepath).startswith(media_dir_nc) and os.path.isfile(filepath):
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
                db.execute(f'DELETE FROM {table} WHERE id = ?', (mid,))
                deleted += 1
        db.commit()
        return jsonify({'status': 'deleted', 'count': deleted})
@media_bp.route('/api/media/batch-move', methods=['POST'])
def api_media_batch_move():
    data = request.get_json() or {}
    media_type = data.get('type', 'videos')
    ids = data.get('ids', [])
    folder = data.get('folder', '')
    _MEDIA_TABLES = {'videos', 'audio', 'books'}
    table_map = {'videos': 'videos', 'audio': 'audio', 'books': 'books'}
    table = safe_table(table_map.get(media_type, ''), _MEDIA_TABLES) if table_map.get(media_type) else None
    if not table or not ids:
        return jsonify({'error': 'Invalid request'}), 400
    with db_session() as db:
        for mid in ids:
            db.execute(f'UPDATE {table} SET folder = ? WHERE id = ?', (folder, mid))
        db.commit()
        return jsonify({'status': 'moved', 'count': len(ids)})
# ─── yt-dlp Integration ──────────────────────────────────────────

@media_bp.route('/api/ytdlp/status')
def api_ytdlp_status():
    installed = _ytdlp_installed()
    version = ''
    source = 'none'
    standalone = _ytdlp_standalone_path()
    if os.path.isfile(standalone):
        source = 'standalone'
        try:
            result = subprocess.run([standalone, '--version'], capture_output=True, text=True, timeout=5,
                                    **_CREATION_FLAGS)
            version = result.stdout.strip()
        except Exception:
            pass
    elif _ytdlp_bundled_available():
        source = 'bundled'
        try:
            result = subprocess.run([sys.executable, '-m', 'yt_dlp', '--version'],
                                    capture_output=True, text=True, timeout=5, **_CREATION_FLAGS)
            version = result.stdout.strip()
        except Exception:
            pass
    return jsonify({'installed': installed, 'version': version, 'source': source, 'path': standalone})

@media_bp.route('/api/ytdlp/check-update')
def api_ytdlp_check_update():
    """Check if a newer yt-dlp version is available on GitHub."""
    current = ''
    exe = get_ytdlp_path()
    if exe and os.path.isfile(exe):
        try:
            result = subprocess.run([exe, '--version'], capture_output=True, text=True, timeout=5,
                                    **_CREATION_FLAGS)
            current = result.stdout.strip()
        except Exception:
            pass
    elif _ytdlp_bundled_available():
        try:
            result = subprocess.run([sys.executable, '-m', 'yt_dlp', '--version'],
                                    capture_output=True, text=True, timeout=5, **_CREATION_FLAGS)
            current = result.stdout.strip()
        except Exception:
            pass
    latest = ''
    try:
        import requests as req
        resp = req.get('https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest',
                       timeout=10, headers={'Accept': 'application/vnd.github+json'})
        if resp.ok:
            release = _safe_response_json(resp, {})
            latest = str(release.get('tag_name', '') or '').lstrip('v') if isinstance(release, dict) else ''
    except Exception:
        pass
    update_available = bool(latest and current and latest != current)
    return jsonify({'current': current, 'latest': latest, 'update_available': update_available})

@media_bp.route('/api/ytdlp/update', methods=['POST'])
def api_ytdlp_update():
    """Download the latest standalone yt-dlp binary, replacing bundled or older version."""
    exe = _ytdlp_standalone_path()
    ytdlp_dir = os.path.dirname(exe)
    os.makedirs(ytdlp_dir, exist_ok=True)

    def do_update():
        try:
            _ytdlp_install_state.update({'status': 'downloading', 'percent': 10, 'error': None})
            import requests as req
            resp = req.get(_get_ytdlp_url(), stream=True, timeout=120, allow_redirects=True)
            resp.raise_for_status()
            total = int(resp.headers.get('content-length', 0))
            downloaded = 0
            tmp = exe + '.tmp'
            with open(tmp, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        _ytdlp_install_state['percent'] = int(downloaded / total * 90) + 10
            # Atomic replace
            try:
                os.replace(tmp, exe)
            except PermissionError:
                # Windows: retry with backoff if AV locks the file
                import time as _t
                for attempt in range(3):
                    _t.sleep(0.2 * (attempt + 1))
                    try:
                        os.replace(tmp, exe)
                        break
                    except PermissionError:
                        if attempt == 2:
                            raise
            from platform_utils import make_executable
            make_executable(exe)
            _ytdlp_install_state.update({'status': 'complete', 'percent': 100, 'error': None})
            log.info('yt-dlp updated to latest')
        except Exception as e:
            log.exception('yt-dlp update failed')
            _ytdlp_install_state.update({'status': 'error', 'percent': 0, 'error': 'Update failed. Check logs for details.'})

    threading.Thread(target=do_update, daemon=True).start()
    return jsonify({'status': 'updating'})

@media_bp.route('/api/ytdlp/install', methods=['POST'])
def api_ytdlp_install():
    if _ytdlp_installed():
        return jsonify({'status': 'already_installed'})
    exe = _ytdlp_standalone_path()
    ytdlp_dir = os.path.dirname(exe)
    os.makedirs(ytdlp_dir, exist_ok=True)

    def do_install():
        try:
            _ytdlp_install_state.update({'status': 'downloading', 'percent': 10, 'error': None})
            import requests as req
            resp = req.get(_get_ytdlp_url(), stream=True, timeout=120, allow_redirects=True)
            resp.raise_for_status()
            total = int(resp.headers.get('content-length', 0))
            downloaded = 0
            with open(exe, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        _ytdlp_install_state['percent'] = int(downloaded / total * 90) + 10
            from platform_utils import make_executable
            make_executable(exe)
            _ytdlp_install_state.update({'status': 'complete', 'percent': 100, 'error': None})
            log.info('yt-dlp installed')
        except Exception as e:
            log.exception('yt-dlp install failed')
            _ytdlp_install_state.update({'status': 'error', 'percent': 0, 'error': 'Install failed. Check logs for details.'})

    threading.Thread(target=do_install, daemon=True).start()
    return jsonify({'status': 'installing'})

@media_bp.route('/api/ytdlp/install-progress')
def api_ytdlp_install_progress():
    return jsonify(_ytdlp_install_state)

@media_bp.route('/api/ytdlp/download', methods=['POST'])
def api_ytdlp_download():

    exe = get_ytdlp_path()
    if not os.path.isfile(exe):
        return jsonify({'error': 'yt-dlp is not installed. Click "Setup Video Downloader" first.'}), 400

    data = request.get_json() or {}
    url = data.get('url', '').strip()
    folder = data.get('folder', '')
    category = data.get('category', 'general')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    # Check for duplicate
    with db_session() as db:
        existing = db.execute('SELECT id FROM videos WHERE url = ?', (url,)).fetchone()
        if existing:
            return jsonify({'status': 'already_exists', 'id': existing['id']})
    with _ytdlp_dl_lock:
        _state._ytdlp_dl_counter += 1
        dl_id = str(_state._ytdlp_dl_counter)

    # Clean up completed/failed entries if too many accumulate
    with _ytdlp_dl_lock:
        if len(_ytdlp_downloads) > 100:
            to_remove = [k for k, v in _ytdlp_downloads.items() if v.get('status') in ('complete', 'error')]
            for k in to_remove:
                del _ytdlp_downloads[k]

    _ytdlp_downloads[dl_id] = {'status': 'starting', 'percent': 0, 'title': '', 'speed': '', 'error': ''}

    # Persist to download queue
    with db_session() as db:
        db.execute('INSERT INTO download_queue (url, category, folder, status) VALUES (?, ?, ?, ?)',
                   (url, category, folder, 'queued'))
        db.commit()
        queue_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    def do_download():
        vdir = get_video_dir()
        dl_url = url
        # Update queue status to downloading
        with db_session() as _db:
            _db.execute('UPDATE download_queue SET status = "downloading" WHERE id = ?', (queue_id,))
            _db.commit()
        try:
            # Get video info first
            _ytdlp_downloads[dl_id]['status'] = 'fetching info'
            info_result = subprocess.run(
                [exe, '--no-download', '--print', '%(title)s|||%(duration_string)s|||%(filesize_approx)s', dl_url],
                capture_output=True, text=True, timeout=30, **_CREATION_FLAGS,
            )
            if info_result.returncode != 0:
                # Video unavailable — report error with clear message
                _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0,
                    'title': 'Video unavailable', 'speed': '',
                    'error': 'This video is unavailable on YouTube. Try searching for it by name.'}
                with db_session() as _db:
                    _db.execute('UPDATE download_queue SET status = "failed", error = "Video unavailable", retries = retries + 1 WHERE id = ?', (queue_id,))
                    _db.commit()
                return
            parts = info_result.stdout.strip().split('|||')
            video_title = parts[0] if parts else dl_url
            video_duration = parts[1] if len(parts) > 1 else ''
            _ytdlp_downloads[dl_id]['title'] = video_title

            # Disk space pre-check — reject if approximate file size exceeds
            # free space minus a 500MB safety margin (merge/convert overhead).
            try:
                size_str = parts[2] if len(parts) > 2 else ''
                approx_size = int(size_str) if size_str and size_str != 'NA' else 0
            except (ValueError, TypeError):
                approx_size = 0
            try:
                free_bytes = shutil.disk_usage(vdir).free
            except OSError:
                free_bytes = 0
            safety_margin = 500 * 1024 * 1024
            required = (approx_size * 2 if approx_size else safety_margin) + safety_margin
            if free_bytes and required > free_bytes:
                err_msg = 'Insufficient disk space: need ~%s, have %s free' % (
                    format_size(required), format_size(free_bytes))
                _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0,
                    'title': video_title, 'speed': '', 'error': err_msg}
                with db_session() as _db:
                    _db.execute('UPDATE download_queue SET status = "failed", error = ?, retries = retries + 1 WHERE id = ?', (err_msg, queue_id))
                    _db.commit()
                return

            # Download with progress — include thumbnail + subtitles
            _ytdlp_downloads[dl_id]['status'] = 'downloading'
            output_tmpl = os.path.join(vdir, '%(title)s.%(ext)s')
            proc = subprocess.Popen(
                [exe, '-f', 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
                 '--merge-output-format', 'mp4', '--newline', '--no-playlist',
                 '--write-thumbnail', '--convert-thumbnails', 'jpg',
                 '--write-subs', '--write-auto-subs', '--sub-langs', 'en', '--convert-subs', 'srt',
                 '-o', output_tmpl, dl_url],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                **_CREATION_FLAGS,
            )

            try:
                for line in proc.stdout:
                    line = line.strip()
                    if '[download]' in line and '%' in line:
                        try:
                            pct_str = line.split('%')[0].split()[-1]
                            pct = float(pct_str)
                            _ytdlp_downloads[dl_id]['percent'] = min(int(pct), 99)
                            if 'at' in line:
                                speed_part = line.split('at')[-1].strip().split('ETA')[0].strip()
                                _ytdlp_downloads[dl_id]['speed'] = speed_part
                        except (ValueError, IndexError):
                            pass
                    elif '[Merger]' in line or '[ExtractAudio]' in line:
                        _ytdlp_downloads[dl_id].update({'status': 'merging', 'percent': 95})
            except Exception:
                try:
                    proc.terminate()
                except OSError:
                    pass

            proc.wait(timeout=3600)

            if proc.returncode != 0:
                # Capture stderr for error details
                err_detail = 'Download failed (exit code %d)' % proc.returncode
                _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': video_title, 'speed': '', 'error': err_detail}
                with db_session() as _db:
                    _db.execute('UPDATE download_queue SET status = "failed", error = ?, retries = retries + 1 WHERE id = ?', (err_detail, queue_id))
                    _db.commit()
                return

            # Find the downloaded file
            safe_title = secure_filename(video_title + '.mp4') if video_title else None
            downloaded_file = None
            for f in os.listdir(vdir):
                fpath = os.path.join(vdir, f)
                if os.path.isfile(fpath) and f.endswith('.mp4'):
                    # Find recently modified files (within last 60s)
                    if time.time() - os.path.getmtime(fpath) < 60:
                        downloaded_file = f
                        break

            if not downloaded_file:
                # Try matching by title
                for f in os.listdir(vdir):
                    if video_title and video_title.lower()[:30] in f.lower():
                        downloaded_file = f
                        break

            if downloaded_file:
                filesize = os.path.getsize(os.path.join(vdir, downloaded_file))
                # Find thumbnail (jpg/webp next to the video)
                base_name = os.path.splitext(downloaded_file)[0]
                thumb_file = ''
                for ext in ('.jpg', '.webp', '.png'):
                    candidate = base_name + ext
                    if os.path.isfile(os.path.join(vdir, candidate)):
                        thumb_file = candidate
                        break
                # Find subtitle file
                srt_file = ''
                for f2 in os.listdir(vdir):
                    if f2.startswith(base_name) and f2.endswith('.srt'):
                        srt_file = f2
                        break
                with db_session() as db:
                    db.execute('INSERT INTO videos (title, filename, category, folder, duration, url, filesize, thumbnail) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                               (video_title, downloaded_file, category, folder, video_duration, dl_url, filesize, thumb_file))
                    db.commit()
                log_activity('video_download', 'media', video_title)
                _ytdlp_downloads[dl_id] = {'status': 'complete', 'percent': 100, 'title': video_title, 'speed': '', 'error': ''}
                # Update queue status to completed
                with db_session() as _db:
                    _db.execute('UPDATE download_queue SET status = "completed", title = ? WHERE id = ?', (video_title, queue_id))
                    _db.commit()
            else:
                _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': video_title, 'speed': '', 'error': 'File not found after download'}
                with db_session() as _db:
                    _db.execute('UPDATE download_queue SET status = "failed", error = "File not found after download", retries = retries + 1 WHERE id = ?', (queue_id,))
                    _db.commit()
        except subprocess.TimeoutExpired:
            _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': '', 'speed': '', 'error': 'Download timed out'}
            with db_session() as _db:
                _db.execute('UPDATE download_queue SET status = "failed", error = "Download timed out", retries = retries + 1 WHERE id = ?', (queue_id,))
                _db.commit()
        except Exception as e:
            log.exception('Video download failed for %s', dl_id)
            err_msg = 'Download failed'
            _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': '', 'speed': '', 'error': err_msg}
            with db_session() as _db:
                _db.execute('UPDATE download_queue SET status = "failed", error = ?, retries = retries + 1 WHERE id = ?', (err_msg, queue_id))
                _db.commit()
    threading.Thread(target=do_download, daemon=True).start()
    return jsonify({'status': 'started', 'id': dl_id})

@media_bp.route('/api/ytdlp/progress')
def api_ytdlp_progress():
    with _state_lock:
        snapshot = dict(_ytdlp_downloads)
    return jsonify(snapshot)

@media_bp.route('/api/ytdlp/progress/<dl_id>')
def api_ytdlp_progress_single(dl_id):
    with _state_lock:
        entry = _ytdlp_downloads.get(dl_id, {'status': 'unknown'})
    return jsonify(entry)

@media_bp.route('/api/videos/catalog')
def api_videos_catalog():
    return jsonify(PREPPER_CATALOG)

@media_bp.route('/api/ytdlp/download-catalog', methods=['POST'])
def api_ytdlp_download_catalog():
    """Download multiple catalog videos sequentially."""

    exe = get_ytdlp_path()
    if not os.path.isfile(exe):
        return jsonify({'error': 'yt-dlp is not installed'}), 400

    data = request.get_json() or {}
    items = data.get('items', [])
    if not items:
        return jsonify({'error': 'No items selected'}), 400

    # Check which are already downloaded
    with db_session() as db:
        existing_urls = set(r['url'] for r in db.execute('SELECT url FROM videos WHERE url != ""').fetchall())
    to_download = [it for it in items if it.get('url') not in existing_urls]
    if not to_download:
        return jsonify({'status': 'all_downloaded', 'count': 0})

    with _ytdlp_dl_lock:
        _state._ytdlp_dl_counter += 1
        queue_id = str(_state._ytdlp_dl_counter)

    _ytdlp_downloads[queue_id] = {'status': 'queued', 'percent': 0, 'title': f'Queue: 0/{len(to_download)}',
                                   'speed': '', 'error': '', 'queue_total': len(to_download), 'queue_pos': 0}

    def do_queue():
        vdir = get_video_dir()
        succeeded = 0
        failed = 0
        for i, item in enumerate(to_download):
            title = item.get('title', '...')
            _ytdlp_downloads[queue_id].update({
                'status': 'downloading', 'percent': 0, 'queue_pos': i + 1,
                'title': f'[{i+1}/{len(to_download)}] {title}', 'speed': '',
            })

            # Try direct URL first, then search fallback if unavailable
            url = item['url']
            use_search = False
            try:
                check = subprocess.run(
                    [exe, '--simulate', '--no-playlist', url],
                    capture_output=True, text=True, timeout=15, **_CREATION_FLAGS,
                )
                if check.returncode != 0:
                    # URL is dead — search for the video by title instead
                    use_search = True
                    _ytdlp_downloads[queue_id]['title'] = f'[{i+1}/{len(to_download)}] Searching: {title}'
                    search_result = subprocess.run(
                        [exe, '--flat-playlist', '--dump-json', f'ytsearch1:{title}'],
                        capture_output=True, text=True, timeout=20, **_CREATION_FLAGS,
                    )
                    if search_result.returncode == 0 and search_result.stdout.strip():
                        found = _load_json_line(search_result.stdout.strip().split('\n')[0], {})
                        if not isinstance(found, dict) or not found.get('id'):
                            log.warning(f'Video search returned malformed data for: {item.get("title")}')
                            failed += 1
                            continue
                        url = f"https://www.youtube.com/watch?v={found['id']}"
                        title = found.get('title', title)
                        _ytdlp_downloads[queue_id]['title'] = f'[{i+1}/{len(to_download)}] {title}'
                    else:
                        log.warning(f'Video unavailable and search failed: {item.get("title")}')
                        failed += 1
                        continue
            except Exception:
                pass  # If check fails, try downloading anyway

            try:
                output_tmpl = os.path.join(vdir, '%(title)s.%(ext)s')
                proc = subprocess.Popen(
                    [exe, '-f', 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
                     '--merge-output-format', 'mp4', '--newline', '--no-playlist',
                     '--write-thumbnail', '--convert-thumbnails', 'jpg',
                     '--write-subs', '--write-auto-subs', '--sub-langs', 'en', '--convert-subs', 'srt',
                     '-o', output_tmpl, url],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    **_CREATION_FLAGS,
                )
                try:
                    for line in proc.stdout:
                        line = line.strip()
                        if '[download]' in line and '%' in line:
                            try:
                                pct = float(line.split('%')[0].split()[-1])
                                _ytdlp_downloads[queue_id]['percent'] = min(int(pct), 99)
                                if 'at' in line:
                                    _ytdlp_downloads[queue_id]['speed'] = line.split('at')[-1].strip().split('ETA')[0].strip()
                            except (ValueError, IndexError):
                                pass
                except Exception:
                    try:
                        proc.terminate()
                    except OSError:
                        pass
                proc.wait(timeout=3600)

                if proc.returncode == 0:
                    succeeded += 1
                    # Find the file + thumbnail
                    for f in sorted(os.listdir(vdir), key=lambda x: os.path.getmtime(os.path.join(vdir, x)), reverse=True):
                        fpath = os.path.join(vdir, f)
                        if os.path.isfile(fpath) and f.endswith('.mp4') and time.time() - os.path.getmtime(fpath) < 120:
                            filesize = os.path.getsize(fpath)
                            base = os.path.splitext(f)[0]
                            thumb = ''
                            for tx in ('.jpg', '.webp', '.png'):
                                if os.path.isfile(os.path.join(vdir, base + tx)):
                                    thumb = base + tx
                                    break
                            with db_session() as db:
                                db.execute('INSERT INTO videos (title, filename, category, folder, url, filesize, thumbnail) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                           (title, f, item.get('category', 'general'), item.get('folder', ''), url, filesize, thumb))
                                db.commit()
                            break
            except Exception as e:
                log.error(f'Catalog download failed for {item.get("title")}: {e}')

        summary = f'Done — {succeeded} downloaded'
        if failed:
            summary += f', {failed} unavailable'
        _ytdlp_downloads[queue_id] = {'status': 'complete', 'percent': 100, 'title': summary,
                                       'speed': '', 'error': '', 'queue_total': len(to_download), 'queue_pos': len(to_download)}

    threading.Thread(target=do_queue, daemon=True).start()
    return jsonify({'status': 'queued', 'id': queue_id, 'count': len(to_download)})


# ─── Audio Library API ─────────────────────────────────────────────

def get_audio_dir():
    path = os.path.join(get_data_dir(), 'audio')
    os.makedirs(path, exist_ok=True)
    return path

AUDIO_CATEGORIES = ['general', 'survival', 'medical', 'radio', 'podcast', 'audiobook', 'music', 'training']

def _get_ffmpeg_url():
    from platform_utils import IS_WINDOWS, IS_MACOS
    if IS_MACOS:
        return 'https://evermeet.cx/ffmpeg/getrelease/zip'
    elif IS_WINDOWS:
        return 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'
    return 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz'

def get_ffmpeg_path():
    from platform_utils import exe_name
    return os.path.join(get_services_dir(), 'ffmpeg', exe_name('ffmpeg'))

@media_bp.route('/api/audio')
def api_audio_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM audio ORDER BY folder, title LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    adir = get_audio_dir()
    return jsonify([{**dict(r), 'exists': os.path.isfile(os.path.join(adir, r['filename']))} for r in rows])

@media_bp.route('/api/audio/upload', methods=['POST'])
def api_audio_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    # Check file size (max 500MB per upload)
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 500 * 1024 * 1024:
        return jsonify({'error': 'File too large (max 500MB)'}), 413
    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400
    filepath = os.path.join(get_audio_dir(), filename)
    file.save(filepath)
    filesize = os.path.getsize(filepath) if os.path.isfile(filepath) else 0
    title = request.form.get('title', filename.rsplit('.', 1)[0])
    category = request.form.get('category', 'general')
    folder = _sanitize_folder(request.form.get('folder', ''))
    artist = request.form.get('artist', '')
    with db_session() as db:
        cur = db.execute('INSERT INTO audio (title, filename, category, folder, artist, filesize) VALUES (?, ?, ?, ?, ?, ?)',
                         (title, filename, category, folder, artist, filesize))
        db.commit()
    log_activity('audio_upload', 'media', title)
    return jsonify({'status': 'uploaded', 'id': cur.lastrowid}), 201

@media_bp.route('/api/audio/<int:aid>', methods=['DELETE'])
def api_audio_delete(aid):
    with db_session() as db:
        row = db.execute('SELECT filename, title FROM audio WHERE id = ?', (aid,)).fetchone()
        if row:
            adir = get_audio_dir()
            filepath = os.path.normpath(os.path.join(adir, row['filename']))
            if os.path.normcase(filepath).startswith(os.path.normcase(adir) + os.sep) and os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            db.execute('DELETE FROM audio WHERE id = ?', (aid,))
            db.commit()
        return jsonify({'status': 'deleted'})
@media_bp.route('/api/audio/<int:aid>', methods=['PATCH'])
def api_audio_update(aid):
    data = request.get_json() or {}
    if 'folder' in data:
        data['folder'] = _sanitize_folder(data['folder'])
    ALLOWED_COLS = ['title', 'folder', 'category', 'artist', 'album']
    filtered = safe_columns(data, ALLOWED_COLS)
    if not filtered:
        return jsonify({'status': 'no changes'})
    sql, params = build_update('audio', filtered, ALLOWED_COLS, where_val=aid)
    with db_session() as db:
        db.execute(sql, params)
        db.commit()
        return jsonify({'status': 'updated'})
@media_bp.route('/api/audio/serve/<path:filename>')
def api_audio_serve(filename):
    adir = get_audio_dir()
    safe = os.path.normcase(os.path.normpath(os.path.join(adir, filename)))
    if not safe.startswith(os.path.normcase(os.path.normpath(adir)) + os.sep) or not os.path.isfile(safe):
        return jsonify({'error': 'Not found'}), 404
    from flask import send_file
    return send_file(safe)

@media_bp.route('/api/audio/stats')
def api_audio_stats():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) as c FROM audio').fetchone()['c']
        total_size = db.execute('SELECT COALESCE(SUM(filesize),0) as s FROM audio').fetchone()['s']
        by_folder = db.execute('SELECT folder, COUNT(*) as c FROM audio GROUP BY folder ORDER BY folder').fetchall()
    return jsonify({'total': total, 'total_size': total_size, 'total_size_fmt': format_size(total_size),
                    'by_folder': [{'folder': r['folder'] or 'Unsorted', 'count': r['c']} for r in by_folder]})

@media_bp.route('/api/audio/folders')
def api_audio_folders():
    with db_session() as db:
        rows = db.execute('SELECT DISTINCT folder FROM audio WHERE folder != "" ORDER BY folder').fetchall()
        return jsonify([r['folder'] for r in rows])
@media_bp.route('/api/ytdlp/download-audio', methods=['POST'])
def api_ytdlp_download_audio():
    """Download audio-only from a URL via yt-dlp."""

    exe = get_ytdlp_path()
    if not os.path.isfile(exe):
        return jsonify({'error': 'yt-dlp is not installed'}), 400

    data = request.get_json() or {}
    url = data.get('url', '').strip()
    folder = data.get('folder', '')
    category = data.get('category', 'general')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    with _ytdlp_dl_lock:
        _state._ytdlp_dl_counter += 1
        dl_id = str(_state._ytdlp_dl_counter)

    _ytdlp_downloads[dl_id] = {'status': 'starting', 'percent': 0, 'title': '', 'speed': '', 'error': ''}

    def do_audio_dl():
        adir = get_audio_dir()
        try:
            _ytdlp_downloads[dl_id]['status'] = 'fetching info'
            info_result = subprocess.run(
                [exe, '--no-download', '--print', '%(title)s|||%(duration_string)s|||%(uploader)s', url],
                capture_output=True, text=True, timeout=30, **_CREATION_FLAGS,
            )
            parts = info_result.stdout.strip().split('|||')
            audio_title = parts[0] if parts else url
            audio_duration = parts[1] if len(parts) > 1 else ''
            audio_artist = parts[2] if len(parts) > 2 else ''
            _ytdlp_downloads[dl_id]['title'] = audio_title

            _ytdlp_downloads[dl_id]['status'] = 'downloading'
            output_tmpl = os.path.join(adir, '%(title)s.%(ext)s')
            ffmpeg = get_ffmpeg_path()
            if os.path.isfile(ffmpeg):
                # FFmpeg available — convert to MP3
                cmd = [exe, '-x', '--audio-format', 'mp3', '--audio-quality', '0',
                       '--newline', '--no-playlist', '--ffmpeg-location', os.path.dirname(ffmpeg),
                       '-o', output_tmpl, url]
            else:
                # No FFmpeg — download best audio as-is (m4a/opus/webm)
                cmd = [exe, '-f', 'bestaudio[ext=m4a]/bestaudio',
                       '--newline', '--no-playlist',
                       '-o', output_tmpl, url]

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, **_CREATION_FLAGS)
            try:
                for line in proc.stdout:
                    line = line.strip()
                    if '[download]' in line and '%' in line:
                        try:
                            pct = float(line.split('%')[0].split()[-1])
                            _ytdlp_downloads[dl_id]['percent'] = min(int(pct), 99)
                            if 'at' in line:
                                _ytdlp_downloads[dl_id]['speed'] = line.split('at')[-1].strip().split('ETA')[0].strip()
                        except (ValueError, IndexError):
                            pass
            except Exception:
                try:
                    proc.terminate()
                except OSError:
                    pass
            proc.wait(timeout=1800)

            if proc.returncode == 0:
                for f in sorted(os.listdir(adir), key=lambda x: os.path.getmtime(os.path.join(adir, x)), reverse=True):
                    fpath = os.path.join(adir, f)
                    if os.path.isfile(fpath) and time.time() - os.path.getmtime(fpath) < 120:
                        filesize = os.path.getsize(fpath)
                        with db_session() as db:
                            db.execute('INSERT INTO audio (title, filename, category, folder, artist, duration, url, filesize) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                       (audio_title, f, category, folder, audio_artist, audio_duration, url, filesize))
                            db.commit()
                        _ytdlp_downloads[dl_id] = {'status': 'complete', 'percent': 100, 'title': audio_title, 'speed': '', 'error': ''}
                        return
            _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': audio_title, 'speed': '', 'error': f'Download failed (exit code {proc.returncode})'}
        except Exception as e:
            log.exception('Audio download failed for %s', dl_id)
            _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': '', 'speed': '', 'error': 'Download failed'}

    threading.Thread(target=do_audio_dl, daemon=True).start()
    return jsonify({'status': 'started', 'id': dl_id})

@media_bp.route('/api/ffmpeg/status')
def api_ffmpeg_status():
    return jsonify({'installed': os.path.isfile(get_ffmpeg_path())})

@media_bp.route('/api/ffmpeg/install', methods=['POST'])
def api_ffmpeg_install():
    ffmpeg = get_ffmpeg_path()
    if os.path.isfile(ffmpeg):
        return jsonify({'status': 'already_installed'})
    ffmpeg_dir = os.path.dirname(ffmpeg)
    os.makedirs(ffmpeg_dir, exist_ok=True)

    _ffmpeg_install = {'status': 'downloading', 'percent': 0}

    def do_install():
        try:
            import requests as req
            from platform_utils import exe_name, IS_WINDOWS, make_executable
            url = _get_ffmpeg_url()
            arc_ext = '.zip' if IS_WINDOWS else ('.tar.xz' if 'tar.xz' in url or 'static' in url else '.zip')
            arc_path = os.path.join(ffmpeg_dir, 'ffmpeg' + arc_ext)
            resp = req.get(url, stream=True, timeout=300, allow_redirects=True)
            resp.raise_for_status()
            total = int(resp.headers.get('content-length', 0))
            downloaded = 0
            with open(arc_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=131072):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        _ffmpeg_install['percent'] = int(downloaded / total * 80)
            _ffmpeg_install.update({'status': 'extracting', 'percent': 85})
            ffmpeg_name = exe_name('ffmpeg')
            ffprobe_name = exe_name('ffprobe')
            if arc_path.endswith('.zip'):
                import zipfile
                with zipfile.ZipFile(arc_path, 'r') as zf:
                    for member in zf.namelist():
                        basename = os.path.basename(member)
                        if basename in (ffmpeg_name, ffprobe_name):
                            data = zf.read(member)
                            dest = os.path.join(ffmpeg_dir, basename)
                            with open(dest, 'wb') as out:
                                out.write(data)
                            make_executable(dest)
            else:
                import tarfile
                mode = 'r:xz' if arc_path.endswith('.tar.xz') else 'r:gz'
                with tarfile.open(arc_path, mode) as tf:
                    for member in tf.getnames():
                        basename = os.path.basename(member)
                        if basename in (ffmpeg_name, ffprobe_name, 'ffmpeg', 'ffprobe'):
                            # Path traversal protection
                            target = os.path.normcase(os.path.normpath(os.path.join(ffmpeg_dir, member)))
                            if not target.startswith(os.path.normcase(os.path.normpath(ffmpeg_dir)) + os.sep):
                                continue
                            tf.extract(member, ffmpeg_dir)
                            extracted = os.path.join(ffmpeg_dir, member)
                            dest = os.path.join(ffmpeg_dir, exe_name(basename.split('.')[0]))
                            if extracted != dest:
                                shutil.move(extracted, dest)
                            make_executable(dest)
            os.remove(arc_path)
            _ffmpeg_install.update({'status': 'complete', 'percent': 100})
            log.info('FFmpeg installed')
        except Exception as e:
            log.exception('FFmpeg install failed')
            _ffmpeg_install.update({'status': 'error', 'percent': 0, 'error': 'Install failed. Check logs for details.'})

    threading.Thread(target=do_install, daemon=True).start()
    return jsonify({'status': 'installing', '_ref': id(_ffmpeg_install)})

# ─── Books / Reference Library API ────────────────────────────────

def get_books_dir():
    path = os.path.join(get_data_dir(), 'books')
    os.makedirs(path, exist_ok=True)
    return path

BOOK_CATEGORIES = ['survival', 'medical', 'farming', 'repair', 'radio', 'cooking', 'defense', 'reference', 'fiction', 'general']

REFERENCE_CATALOG = [
    # Army Field Manuals (Public Domain)
    {'title': 'FM 3-05.70 Survival (Army Survival Manual)', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/Fm21-76SurvivalManual/FM%2021-76%20-%20Survival%20Manual.pdf', 'description': 'The definitive military survival guide — shelter, water, food, navigation, signaling. 676 pages.'},
    {'title': 'FM 21-11 First Aid for Soldiers', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'medical', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/fm-21-11-first-aid-for-soldiers/FM%2021-11%20First%20Aid%20for%20Soldiers.pdf', 'description': 'Military first aid — bleeding control, fractures, burns, shock, CPR, field hygiene.'},
    {'title': 'FM 21-76-1 Survival, Evasion, and Recovery', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/FM21-76-1/FM%2021-76-1.pdf', 'description': 'Pocket survival guide — evasion, signaling, water procurement, shelter, fire.'},
    {'title': 'FM 5-34 Engineer Field Data', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'repair', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/FM5-34/FM5-34.pdf', 'description': 'Construction, demolition, water supply, power generation, rope and rigging.'},
    # FEMA Guides (Public Domain)
    {'title': 'FEMA: Are You Ready? Emergency Preparedness Guide', 'author': 'FEMA', 'format': 'pdf', 'category': 'survival', 'folder': 'FEMA Guides',
     'url': 'https://www.fema.gov/pdf/areyouready/areyouready_full.pdf', 'description': '204-page comprehensive emergency preparedness guide covering all major disaster types.'},
    # Medical References
    {'title': 'Where There Is No Doctor', 'author': 'David Werner', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
     'url': 'https://archive.org/download/WTINDen2011/WTIND%20en%202011.pdf', 'description': 'Village health care handbook — the standard off-grid medical reference. CC-licensed.'},
    {'title': 'Where There Is No Dentist', 'author': 'Murray Dickson', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
     'url': 'https://archive.org/download/WhereThereIsNoDentist/WhereThereIsNoDentist.pdf', 'description': 'Dental care in remote areas — tooth extraction, fillings, oral health.'},
    # Practical Skills
    {'title': 'The SAS Survival Handbook', 'author': 'John Wiseman', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
     'url': 'https://archive.org/download/sas-survival-guide/SAS%20Survival%20Guide.pdf', 'description': 'Comprehensive wilderness survival — climate, terrain, shelter, food, navigation.'},
    {'title': 'Bushcraft 101: Field Guide to Wilderness Survival', 'author': 'Dave Canterbury', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
     'url': 'https://archive.org/download/bushcraft-101/Bushcraft%20101.pdf', 'description': 'Modern bushcraft essentials — 5 Cs of survivability, tools, shelter, fire, water.'},
    {'title': 'US Army Ranger Handbook', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'defense', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/ranger-handbook-2017/Ranger%20Handbook%202017.pdf', 'description': 'Ranger operations — leadership, planning, patrols, demolitions, comms, first aid.'},
    # Radio & Communications
    {'title': 'ARRL Ham Radio License Manual', 'author': 'ARRL', 'format': 'pdf', 'category': 'radio', 'folder': 'Radio & Communications',
     'url': 'https://archive.org/download/arrl-ham-radio-license-manual/ARRL%20Ham%20Radio%20License%20Manual.pdf', 'description': 'Study guide for amateur radio Technician license — FCC rules, electronics, operations.'},
    # Homesteading & Food
    {'title': 'Ball Complete Book of Home Preserving', 'author': 'Judi Kingry', 'format': 'pdf', 'category': 'cooking', 'folder': 'Homesteading',
     'url': 'https://archive.org/download/ball-complete-book-home-preserving/Ball%20Complete%20Book%20of%20Home%20Preserving.pdf', 'description': '400 recipes for canning, preserving, pickling — long-term food storage.'},
    {'title': 'Square Foot Gardening', 'author': 'Mel Bartholomew', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
     'url': 'https://archive.org/download/square-foot-gardening/Square%20Foot%20Gardening.pdf', 'description': 'Revolutionary approach to small-space gardening — grow more in less space.'},
    # Nuclear / CBRN (Public Domain)
    {'title': 'Nuclear War Survival Skills', 'author': 'Cresson Kearny / ORNL', 'format': 'pdf', 'category': 'survival', 'folder': 'Nuclear & CBRN',
     'url': 'https://archive.org/download/NuclearWarSurvivalSkillsCressonKearny1987/Nuclear%20War%20Survival%20Skills%20Cresson%20Kearny%201987.pdf', 'description': 'Uncopyrighted Oak Ridge National Laboratory guide — shelters, ventilation, KFM fallout meter construction, radiation protection, food/water. 18 chapters.'},
    {'title': 'Planning Guide for Response to Nuclear Detonation', 'author': 'FEMA / DHHS', 'format': 'pdf', 'category': 'survival', 'folder': 'Nuclear & CBRN',
     'url': 'https://www.ready.gov/sites/default/files/2022-09/planning-guidance-for-response-to-nuclear-detonation.pdf', 'description': 'FEMA 2022 edition — blast zones, fallout shelter-in-place timing, evacuation decisions, decontamination, mass care.'},
    {'title': 'FM 3-11 NBC Defense Operations', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Nuclear & CBRN',
     'url': 'https://irp.fas.org/doddir/army/fm3_11.pdf', 'description': 'Nuclear, biological, and chemical defense — contamination avoidance, protection, decontamination, collective protection.'},
    # Advanced Military Medical
    {'title': 'Emergency War Surgery (5th US Revision)', 'author': 'U.S. Army / Borden Institute', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
     'url': 'https://apps.dtic.mil/sti/tr/pdf/ADA305002.pdf', 'description': 'NATO handbook, free from Borden Institute. Ballistic wound care, burns, blast, cold injury, mass casualties, field surgery. The definitive austere medicine surgical reference.'},
    {'title': 'Special Forces Medical Handbook (ST 31-91B)', 'author': 'U.S. Army Special Forces', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
     'url': 'https://archive.org/download/SpecialForcesMedicalHandbook/Special%20Forces%20Medical%20Handbook%20ST%2031-91B.pdf', 'description': 'Gold standard field medicine reference — clinical diagnosis, tropical medicine, trauma, anesthesia, field pharmacy, lab procedures.'},
    {'title': 'ATP 4-02.5 Casualty Care', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
     'url': 'https://archive.org/download/ATP4-25x13/ATP%204-02.5%20Casualty%20Care.pdf', 'description': 'Current Army casualty care doctrine — TCCC protocols, point-of-injury care, blood products, CBRN patient treatment.'},
    # Navigation & Land Nav
    {'title': 'FM 3-25.26 Map Reading and Land Navigation', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/fm-3-25.26-map-reading-and-land-navigation/FM%203-25.26%20Map%20Reading%20and%20Land%20Navigation.pdf', 'description': 'Definitive military land navigation — topographic maps, UTM/MGRS coordinates, compass, GPS, field sketching, night navigation.'},
    # Emergency Management
    {'title': 'CERT Basic Training Participant Manual', 'author': 'FEMA / Ready.gov', 'format': 'pdf', 'category': 'survival', 'folder': 'FEMA Guides',
     'url': 'https://www.ready.gov/sites/default/files/2019-12/cert_pm_unit-1.pdf', 'description': 'Community Emergency Response Team curriculum — disaster preparedness, fire suppression, medical operations, light search and rescue, ICS, disaster psychology.'},
    {'title': 'LDS Preparedness Manual', 'author': 'LDS Church (via ThesurvivalMom)', 'format': 'pdf', 'category': 'survival', 'folder': 'FEMA Guides',
     'url': 'https://thesurvivalmom.com/wp-content/uploads/2010/08/LDS-Preparedness-Manual.pdf', 'description': 'Comprehensive LDS preparedness guide — 72-hour kits, 3-month food supply, long-term storage (wheat, rice, beans), water, medical, communications, financial.'},
    # Homesteading & Food Production
    {'title': 'USDA Complete Guide to Home Canning (2015)', 'author': 'USDA', 'format': 'pdf', 'category': 'cooking', 'folder': 'Homesteading',
     'url': 'https://archive.org/download/usda-complete-guide-to-home-canning-2015-revision/USDA%20Complete%20Guide%20to%20Home%20Canning%202015%20Revision.pdf', 'description': 'Official USDA safe canning reference — water bath and pressure canning for fruits, vegetables, meats, pickles, jams. Processing times and altitude adjustments.'},
    # Security & Tactics
    {'title': 'FM 3-19.30 Physical Security', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'defense', 'folder': 'Army Field Manuals',
     'url': 'https://irp.fas.org/doddir/army/fm3-19-30.pdf', 'description': 'Physical security planning — threat assessment, perimeter design, access control, barriers, alarms, guard operations.'},
    {'title': 'FM 20-3 Camouflage, Concealment, and Decoys', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'defense', 'folder': 'Army Field Manuals',
     'url': 'https://irp.fas.org/doddir/army/fm20-3.pdf', 'description': 'Military camouflage techniques — individual camouflage, vehicle/equipment concealment, decoys, light and noise discipline, thermal signature management.'},
    # Additional Army Field Manuals
    {'title': 'FM 21-60 Visual Signals', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/FM21-60VisualSignals/FM%2021-60%20Visual%20Signals.pdf', 'description': 'Military visual signaling — arm and hand signals, panel signals, pyrotechnics, mirrors, smoke, and air-ground signals. Essential for rescue signaling and unit communications.'},
    {'title': 'FM 5-125 Rigging Techniques, Procedures, and Applications', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'repair', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/FM5-125RiggingTechniques/FM%205-125.pdf', 'description': 'Complete rigging manual — rope construction, knots, blocks and tackles, hoisting, slings, wire rope, load calculation, rope bridges, expedient rigging for heavy loads.'},
    {'title': 'FM 5-426 Carpentry', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'repair', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/FM5-426Carpentry/FM%205-426.pdf', 'description': 'Military carpentry — framing, roofing, floors, doors, windows, concrete forms, scaffolding, and rough construction techniques for field-expedient buildings.'},
    {'title': 'FM 31-70 Basic Cold Weather Manual', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/FM31-70BasicColdWeatherManual/FM%2031-70.pdf', 'description': 'Cold weather survival — hypothermia/frostbite prevention and treatment, snow shelters (quinzhee, snow trench, igloo), movement on ice and snow, cold-weather equipment.'},
    {'title': 'FM 90-3 Desert Operations', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/FM90-3DesertOperations/FM%2090-3.pdf', 'description': 'Desert survival — heat casualties and prevention, water procurement in arid environments, navigation in featureless terrain, desert shelter, camouflage, and vehicle operations.'},
    {'title': 'FM 10-52 Water Supply in Theaters of Operations', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/FM10-52WaterSupply/FM%2010-52.pdf', 'description': 'Large-scale water supply — source reconnaissance, purification systems (reverse osmosis, chlorination), quality testing, storage, distribution networks, decontamination.'},
    {'title': 'FM 21-150 Combatives', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'defense', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/FM21-150Combatives/FM%2021-150%20Combatives.pdf', 'description': 'Hand-to-hand combat — unarmed defense, disarming techniques, bayonet fighting, improvised weapon use, prisoner control, ground fighting, fighting in close quarters.'},
    {'title': 'TC 31-29/A Special Forces Operational Techniques', 'author': 'U.S. Army Special Forces', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/TC31-29SpecialForcesOperationalTechniques/TC-31-29.pdf', 'description': 'SF field craft — cover and concealment, movement techniques, base camp operations, cache construction, improvised equipment, surveillance, counter-tracking.'},
    {'title': 'FM 3-11.9 Potential Military Chemical/Biological Agents', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Nuclear & CBRN',
     'url': 'https://irp.fas.org/doddir/army/fm3-11-9.pdf', 'description': 'CBRN agent recognition — nerve agents (GA/GB/GD/VX), blister agents, blood agents, choking agents, biological threats. Detection, medical management, decontamination protocols.'},
    # Foxfire Series — Appalachian Traditional Skills (essential offline library)
    {'title': 'Foxfire 1 — Hog Dressing, Log Cabin Building, Mountain Crafts', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'survival', 'folder': 'Foxfire Series',
     'url': 'https://archive.org/download/foxfireup00foxf/foxfireup00foxf.pdf', 'description': 'Volume 1 of the landmark Foxfire series — log cabin building, hog dressing, mountain crafts, planting by signs, snake lore, hunting, wild plant foods. Appalachian traditional knowledge from elders.'},
    {'title': 'Foxfire 2 — Ghost Stories, Spinning and Weaving, Midwifery, Burial Customs', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'survival', 'folder': 'Foxfire Series',
     'url': 'https://archive.org/download/foxfireup02foxf/foxfireup02foxf.pdf', 'description': 'Volume 2 — spinning and weaving, midwifery and childbirth, burial customs, corn shucking, wagon making, butter churning, and Appalachian ghost stories.'},
    {'title': 'Foxfire 3 — Animal Care, Hide Tanning, Summer and Fall Wild Plant Foods', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'farming', 'folder': 'Foxfire Series',
     'url': 'https://archive.org/download/foxfire3foxfire3/foxfire3.pdf', 'description': 'Volume 3 — animal care (mules, sheep, hogs), hide tanning, summer/fall wild plant foods, preserving vegetables, banjos and dulcimers, water systems.'},
    {'title': 'Foxfire 4 — Fiddle Making, Springhouses, Horse Trading', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'repair', 'folder': 'Foxfire Series',
     'url': 'https://archive.org/download/foxfire4foxfire/foxfire4.pdf', 'description': 'Volume 4 — fiddle making, springhouses and wet-weather springs, horse trading, sassafras tea, wood carving, basket making, blacksmithing.'},
    {'title': 'Foxfire 5 — Ironmaking, Blacksmithing, Flintlock Rifles, Bear Hunting', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'repair', 'folder': 'Foxfire Series',
     'url': 'https://archive.org/download/foxfire5foxfire5/foxfire5.pdf', 'description': 'Volume 5 — ironmaking, blacksmithing, flintlock rifles, bear hunting with dogs, ginseng harvesting, faith healing, mountain voices.'},
    {'title': 'Foxfire 6 — Shoemaking, Gourd Banjos, Sorghum, Wine Making', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'cooking', 'folder': 'Foxfire Series',
     'url': 'https://archive.org/download/foxfire6foxfire6/foxfire6.pdf', 'description': 'Volume 6 — shoemaking and cobbling, gourd banjos and dulcimers, sorghum syrup making, wine making, dyes, furniture making, log cabin restoration.'},
    # Homesteading Classics
    {'title': 'The Encyclopedia of Country Living', 'author': 'Carla Emery', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
     'url': 'https://archive.org/download/encyclopediaofcountryliving/Encyclopedia_of_Country_Living.pdf', 'description': 'THE bible of self-sufficient living — 900+ pages covering gardening, grain growing, animal husbandry, food preservation, soap making, butchering, foraging, beekeeping, and more.'},
    {'title': 'Root Cellaring: Natural Cold Storage of Fruits and Vegetables', 'author': 'Mike & Nancy Bubel', 'format': 'pdf', 'category': 'cooking', 'folder': 'Homesteading',
     'url': 'https://archive.org/download/rootcellaringnaturalcoldstorage/Root_Cellaring.pdf', 'description': 'Complete guide to root cellaring — cellar design, temperature zones, what to store (70+ crops), how long each lasts, troubleshooting spoilage without electricity.'},
    {'title': 'Small-Scale Grain Raising', 'author': 'Gene Logsdon', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
     'url': 'https://archive.org/download/smallscalegraing00logs/small-scale-grain-raising.pdf', 'description': 'Growing grain on 1–5 acres — wheat, corn, oats, barley, rye, sorghum. Hand tools, threshing, milling, storing. The missing link between garden and farm-scale food production.'},
    {'title': 'Storey\'s Guide to Raising Chickens', 'author': 'Gail Damerow', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
     'url': 'https://archive.org/download/storeysguidetoraising/Storeys_Guide_Raising_Chickens.pdf', 'description': 'Complete chicken keeping — breeds, housing, feeding, health care, egg production, meat birds, incubation, butchering. The definitive backyard poultry reference.'},
    {'title': 'Keeping Bees', 'author': 'John Vivian', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
     'url': 'https://archive.org/download/keepingbees00vivi/keeping_bees.pdf', 'description': 'Practical beekeeping — hive management, swarm control, disease, honey extraction, wax processing, winter preparation. Bees provide pollination AND calories for the homestead.'},
    {'title': 'Four-Season Harvest', 'author': 'Eliot Coleman', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
     'url': 'https://archive.org/download/fourseasonharvest/Four_Season_Harvest.pdf', 'description': 'Year-round vegetable growing without electricity — cold frames, low tunnels, unheated greenhouses, variety selection. Harvest fresh food in snow with minimal infrastructure.'},
    {'title': 'Postharvest Technology of Fruits and Vegetables', 'author': 'FAO', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
     'url': 'https://www.fao.org/3/x5056e/x5056e.pdf', 'description': 'FAO guide to extending the life of harvested crops — storage, cooling, packaging, grading, transport. Prevents post-harvest losses critical when food production is your lifeline.'},
    # Water & Sanitation
    {'title': 'Slow Sand Filtration — Technical Brief', 'author': 'WEDC / Loughborough University', 'format': 'pdf', 'category': 'survival', 'folder': 'Water & Sanitation',
     'url': 'https://www.ircwash.org/sites/default/files/Visscher-1990-Slow.pdf', 'description': 'Design and construction of slow sand filters — low-tech, highly effective water purification requiring no chemicals or electricity. Proven technology for village-scale clean water.'},
    {'title': 'Emergency Water Supply Manual', 'author': 'AWWA / FEMA', 'format': 'pdf', 'category': 'survival', 'folder': 'Water & Sanitation',
     'url': 'https://www.fema.gov/pdf/plan/prevent/rms/154/fema154.pdf', 'description': 'Emergency water supply planning — source assessment, treatment, storage, distribution. Covers contingency planning for utilities and improvised community water supply after disasters.'},
    {'title': 'Solar Water Disinfection (SODIS) — A Guide', 'author': 'Eawag/Sandec', 'format': 'pdf', 'category': 'survival', 'folder': 'Water & Sanitation',
     'url': 'https://www.sodis.ch/methode/anwendung/ausbildungsmaterial/dokumente_material/mannual_e.pdf', 'description': 'Using sunlight to disinfect drinking water — PET bottles, exposure times by season and turbidity, verification. Works anywhere with sunlight, costs nothing.'},
    {'title': 'Small Community Water Supplies', 'author': 'IRC International Water and Sanitation Centre', 'format': 'pdf', 'category': 'survival', 'folder': 'Water & Sanitation',
     'url': 'https://www.ircwash.org/sites/default/files/211.1-82SC-15055.pdf', 'description': 'Complete guide to small-community water supply systems — springs, wells, rainwater, pumps, piping, treatment, management. Everything needed for village-scale water infrastructure.'},
    {'title': 'Rainwater Collection for the Mechanically Challenged', 'author': 'Suzy Banks & Richard Heinichen', 'format': 'pdf', 'category': 'survival', 'folder': 'Water & Sanitation',
     'url': 'https://archive.org/download/rainwatercollection00bank/rainwater_collection.pdf', 'description': 'Practical rainwater harvesting — catchment areas, first-flush diverters, storage tanks, filtration, legality by state. Building systems for Texas and drought-prone regions.'},
    # Energy / Power
    {'title': 'Biogas Technology — FAO Agricultural Services Bulletin', 'author': 'FAO', 'format': 'pdf', 'category': 'repair', 'folder': 'Energy & Power',
     'url': 'https://www.fao.org/3/w7046e/w7046e.pdf', 'description': 'Building and operating biogas digesters — generating cooking and lighting gas from animal manure and organic waste. Complete construction plans for family-scale biogas plants.'},
    {'title': 'Micro-Hydropower Systems: A Handbook', 'author': 'Natural Resources Canada', 'format': 'pdf', 'category': 'repair', 'folder': 'Energy & Power',
     'url': 'https://www.nrcan.gc.ca/sites/www.nrcan.gc.ca/files/canmetenergy/files/pubs/Micro-HydropowerSystemsHandbook.pdf', 'description': 'Complete guide to small hydroelectric systems — site assessment, flow measurement, head calculation, turbine selection, penstock design, electrical systems. 24/7 renewable power from streams.'},
    {'title': 'Wind Power Workshop', 'author': 'Hugh Piggott', 'format': 'pdf', 'category': 'repair', 'folder': 'Energy & Power',
     'url': 'https://archive.org/download/windpowerworkshop/Wind_Power_Workshop.pdf', 'description': 'Build your own wind turbine from scratch — blade carving, alternator winding, tower construction. The classic DIY wind power manual from the off-grid community.'},
    {'title': 'Solar Photovoltaic Systems Technical Training Manual', 'author': 'USAID / IT Power', 'format': 'pdf', 'category': 'repair', 'folder': 'Energy & Power',
     'url': 'https://archive.org/download/solarpvsystems/Solar_PV_Technical_Training.pdf', 'description': 'Complete PV system design — site analysis, load calculation, panel sizing, battery banks, charge controllers, inverters, wiring, troubleshooting. From theory to field installation.'},
    # Additional Medical References
    {'title': 'The Ship Captain\'s Medical Guide (22nd Edition)', 'author': 'UK Maritime & Coastguard Agency', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
     'url': 'https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/915232/Ship_captains_medical_guide.pdf', 'description': 'Medical care at sea with no physician — diagnosis and treatment for 200+ conditions, surgical procedures, childbirth, medications, resuscitation. Free from UK government. Excellent austere-environment reference.'},
    {'title': 'Medical Management of Radiological Casualties', 'author': 'Armed Forces Radiobiology Research Institute', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
     'url': 'https://www.usuhs.edu/sites/default/files/media/afrri/pdf/4edmmrchandbook.pdf', 'description': 'AFRRI handbook — radiation injury diagnosis, ARS staging, treatment protocols, contamination decontamination, combined injuries (blast+radiation), triage criteria.'},
    {'title': 'Psychological First Aid Field Operations Guide (2nd Ed.)', 'author': 'National Child Traumatic Stress Network / NCPTSD', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
     'url': 'https://www.ptsd.va.gov/professional/treat/type/PFA/PFA_2ndEditionwithappendices.pdf', 'description': 'Mental health first aid for disaster survivors — Listen, Protect, Connect model. Practical, evidence-based psychological support for acute traumatic stress without professional resources.'},
    {'title': 'Merck Manual of Medical Information (1899 Edition — Public Domain)', 'author': 'Merck & Co.', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
     'url': 'https://archive.org/download/merckmanualmedic00merc/merck_manual_1899.pdf', 'description': 'The original Merck Manual — fully public domain. Diseases, symptoms, treatments, pharmacology from the late 1800s. Historical perspective on medicine without modern supplies.'},
    {'title': 'Hand to Hand Health Care — A Primary Health Care Manual', 'author': 'Peace Corps', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
     'url': 'https://files.peacecorps.gov/multimedia/pdf/library/M0006_handtohandhealth.pdf', 'description': 'Peace Corps community health manual — nutrition, water sanitation, maternal/child health, common diseases, oral rehydration, immunization, first aid. Designed for non-medical community health workers.'},
    {'title': 'Management of Dead Bodies After Disasters', 'author': 'PAHO / WHO', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
     'url': 'https://iris.paho.org/bitstream/handle/10665.2/721/9789275116227_eng.pdf', 'description': 'Critical but overlooked disaster skill — field identification, proper handling, mass fatality management, preventing disease. PAHO/WHO guide for mass casualty incidents.'},
    # Construction & Infrastructure
    {'title': 'The Owner-Built Home', 'author': 'Ken Kern', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
     'url': 'https://archive.org/download/theownerbuilthome/The_Owner_Built_Home.pdf', 'description': 'Classic owner-builder guide — site selection, foundation types, adobe, rammed earth, cob, stone, timber frame. Philosophy of building your own home with available materials and hand tools.'},
    {'title': 'USDA Wood Handbook — Wood as an Engineering Material', 'author': 'USDA Forest Products Laboratory', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
     'url': 'https://www.fpl.fs.fed.us/documnts/fplgtr/fplgtr282.pdf', 'description': 'Complete wood properties reference — species characteristics, moisture effects, mechanical properties, fasteners, joints, gluing, wood composites. Essential for building with locally-sourced timber.'},
    {'title': 'Village Technology Handbook', 'author': 'VITA (Volunteers in Technical Assistance)', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
     'url': 'https://archive.org/download/villagetechnology/Village_Technology_Handbook.pdf', 'description': 'VITA\'s classic — building construction, water supply, sanitation, small-scale food processing, appropriate technology for self-sufficient villages. Practical guides for post-grid scenarios.'},
    {'title': 'Earthbag Construction — The Tools, Tricks, and Techniques', 'author': 'Kaki Hunter & Donald Kiffmeyer', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
     'url': 'https://archive.org/download/earthbagconstruction/earthbag_construction.pdf', 'description': 'Build strong, low-cost structures from polypropylene bags filled with earth — foundations, domes, walls, arches. Minimal tools, locally available materials, earthquake/hurricane resistant.'},
    # Navigation & Communications
    {'title': 'National Interoperability Field Operations Guide (NIFOG)', 'author': 'DHS / FEMA', 'format': 'pdf', 'category': 'radio', 'folder': 'Radio & Communications',
     'url': 'https://www.dhs.gov/sites/default/files/publications/nifog.pdf', 'description': 'Emergency communications interoperability guide — NIMS radio channels, frequencies, ICS communications, plain language, common protocols for multi-agency disasters. Every prepper\'s communications reference.'},
    {'title': 'Emergency Response Guidebook (ERG 2020)', 'author': 'DOT / Transport Canada', 'format': 'pdf', 'category': 'survival', 'folder': 'FEMA Guides',
     'url': 'https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/2020ERG.pdf', 'description': 'First responder guide to 3,000+ hazardous materials — identification, safe distances, protective action zones, fire/spill response. Essential for CBRN incidents from vehicle accidents or industrial disasters.'},
    {'title': 'ICS 100: Introduction to the Incident Command System', 'author': 'FEMA Emergency Management Institute', 'format': 'pdf', 'category': 'survival', 'folder': 'FEMA Guides',
     'url': 'https://training.fema.gov/is/courseoverview.aspx?code=is-100.c', 'description': 'FEMA free ICS course — unified command structure, span of control, communication, resource management. The organizational system used to manage any disaster response effectively.'},
    {'title': 'ARRL Antenna Book for Radio Communications (older edition)', 'author': 'ARRL', 'format': 'pdf', 'category': 'radio', 'folder': 'Radio & Communications',
     'url': 'https://archive.org/download/ARRLAntennaBook/ARRL_Antenna_Book.pdf', 'description': 'ARRL\'s definitive antenna reference — dipoles, verticals, Yagis, loops, wire antennas, propagation, feedlines, construction. Build effective communications antennas with available materials.'},
    # Agricultural Extension / USDA
    {'title': 'USDA Farmers Bulletin: Canning and Preserving (No. 1762)', 'author': 'USDA', 'format': 'pdf', 'category': 'cooking', 'folder': 'USDA Publications',
     'url': 'https://archive.org/download/CAT87206536/CAT87206536.pdf', 'description': 'USDA classic canning bulletin — water bath and pressure canning, acidity, processing times, spoilage indicators. Public domain from the era of kitchen self-sufficiency.'},
    {'title': 'USDA Farmers Bulletin: Poultry Keeping (No. 2009)', 'author': 'USDA', 'format': 'pdf', 'category': 'farming', 'folder': 'USDA Publications',
     'url': 'https://archive.org/download/farmersbulletin2009/farmers_bulletin_2009.pdf', 'description': 'USDA guide to small-flock chicken and turkey keeping — housing, feeding, breeding, disease management, egg and meat production on a small scale.'},
    {'title': 'USDA Farmers Bulletin: Beekeeping for Beginners', 'author': 'USDA', 'format': 'pdf', 'category': 'farming', 'folder': 'USDA Publications',
     'url': 'https://archive.org/download/usda-beekeeping-beginners/usda_beekeeping.pdf', 'description': 'Classic USDA beekeeping introduction — hive types, bees biology, seasonal management, honey extraction, disease recognition. Essential for honey production and crop pollination.'},
    {'title': 'USDA Farmers Bulletin: Home Drying of Fruits and Vegetables', 'author': 'USDA', 'format': 'pdf', 'category': 'cooking', 'folder': 'USDA Publications',
     'url': 'https://archive.org/download/usda-home-drying/home_drying_fruits_vegetables.pdf', 'description': 'Sun drying, air drying, and oven drying fruits, vegetables, herbs, and meat. Traditional dehydration methods requiring no electricity for 1-2 year shelf life.'},
    # Additional Survival / General
    {'title': 'How to Survive the End of the World as We Know It', 'author': 'James Wesley Rawles', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
     'url': 'https://archive.org/download/howtosurvivetend00rawl/how_to_survive.pdf', 'description': 'Comprehensive prepper reference — food storage, water, medical, weapons, communications, financial preparedness, retreat location selection, community building. From SurvivalBlog founder.'},
    {'title': 'Wilderness Navigation (2nd Ed.)', 'author': 'Bob Burns & Mike Burns', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
     'url': 'https://archive.org/download/wildernessnavigation/Wilderness_Navigation.pdf', 'description': 'Navigation beyond GPS — compass use, map reading, triangulation, altimeter navigation, GPS backup, route-finding by terrain features. For hiking, hunting, and when GPS fails.'},
    {'title': 'Tom Brown\'s Field Guide to Wilderness Survival', 'author': 'Tom Brown Jr.', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
     'url': 'https://archive.org/download/tombrownssurvival/Tom_Browns_Survival.pdf', 'description': 'Tom Brown\'s Tracker School teachings — tracking, fire by friction, water finding, shelter construction, plant foods, primitive trapping. Apache-tradition wilderness survival philosophy.'},
    {'title': 'Primitive Wilderness Living and Survival Skills', 'author': 'John & Geri McPherson', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
     'url': 'https://archive.org/download/primitivewilderness/Primitive_Wilderness_Survival.pdf', 'description': 'Deep wilderness living — tanning hides, making buckskin, bone and stone tools, primitive pottery, atlatl construction, hide glue, traditional fire craft.'},
    {'title': 'The Disaster Preparedness Handbook', 'author': 'Arthur Bradley, PhD', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
     'url': 'https://archive.org/download/disasterpreparedness/Disaster_Preparedness_Handbook.pdf', 'description': 'Systematic preparedness planning — threat analysis, supplies prioritization, financial preparedness, communication planning, home hardening, community resilience. Engineer\'s approach to prepping.'},
    # Chemical/Industrial Safety
    {'title': 'NIOSH Pocket Guide to Chemical Hazards', 'author': 'CDC / NIOSH', 'format': 'pdf', 'category': 'survival', 'folder': 'Nuclear & CBRN',
     'url': 'https://www.cdc.gov/niosh/npg/pdfs/npg.pdf', 'description': '729 chemicals — exposure limits, health hazards, protective equipment, emergency response, physical properties. Identify and respond to industrial chemical exposures from accidents or CBRN incidents.'},
    {'title': 'Recognition and Management of Pesticide Poisonings', 'author': 'EPA', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
     'url': 'https://www.epa.gov/sites/default/files/documents/rmpp_6thed_final_lowresopt.pdf', 'description': 'EPA guide for clinicians — organophosphates, carbamates, pyrethroids, herbicides, fumigants. Toxidrome recognition, antidotes (atropine, pralidoxime), decontamination, supportive care.'},
    # Weather & Meteorology
    {'title': 'Aviation Weather (AC 00-6B)', 'author': 'FAA', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
     'url': 'https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_00-6B.pdf', 'description': 'Definitive FAA weather guide — cloud types and formation, pressure systems, fronts, thunderstorm lifecycle, turbulence, wind shear, icing, fog. Best plain-English meteorology reference for non-pilots too.'},
    {'title': 'NOAA Skywarn Storm Spotter Training Manual', 'author': 'NOAA / NWS', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
     'url': 'https://www.weather.gov/media/owlie/spottershome0916.pdf', 'description': 'Official NWS severe weather spotter training — supercell identification, tornado signatures, wall clouds, shelf clouds, hail shafts, flooding, winter storms. Report severe weather accurately to NWS.'},
    {'title': 'The AMS Glossary of Meteorology (3rd Ed.)', 'author': 'American Meteorological Society', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
     'url': 'https://archive.org/download/glossaryofmeteor00hube/glossaryofmeteor00hube.pdf', 'description': '12,000 weather terms defined — pressure gradients, lapse rates, vorticity, hodographs, orographic lift, CAPE. The complete reference for understanding NWS forecast discussions and meteorology literature.'},
    {'title': 'NWS Training Manual — Observing and Forecasting', 'author': 'NOAA / NWS', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
     'url': 'https://www.weather.gov/media/training/nwstm_a32.pdf', 'description': 'Official NWS observer training — measuring temperature, precipitation, visibility, cloud cover, pressure. How to set up and run a personal weather station and contribute to COCORAHS network.'},
    {'title': 'Mariner\'s Weather Handbook', 'author': 'Steve and Linda Dashew', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
     'url': 'https://archive.org/download/marinersweatherh00dash/marinersweatherh00dash.pdf', 'description': 'Offshore weather prediction — reading barometer, interpreting GRIB files, squall lines, gale avoidance, tropical weather, storm tactics. Critical for coastal survival and maritime emergency operations.'},
    {'title': 'Understanding Weather and Climate (2nd Ed.)', 'author': 'Aguado & Burt', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
     'url': 'https://archive.org/download/understandingwea00agua/understandingwea00agua.pdf', 'description': 'College-level meteorology textbook — atmosphere composition, solar radiation, humidity, clouds, precipitation, pressure, wind, air masses, fronts, storms. Complete meteorological education.'},
    {'title': 'Weather Analysis and Forecasting Handbook', 'author': 'Tim Vasquez', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
     'url': 'https://archive.org/download/weatheranalysisf00vasq/weatheranalysisf00vasq.pdf', 'description': 'Forecaster\'s reference — surface analysis, upper-air charts, satellite interpretation, radar patterns, model output statistics, sounding analysis, severe weather parameters (CAPE, SRH, STP).'},
    {'title': 'NOAA Weather Radio — Complete User Guide', 'author': 'NOAA', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
     'url': 'https://www.weather.gov/nwr/nwrbrochure.pdf', 'description': 'Programming and using NOAA Weather Radio All Hazards — SAME codes, specific alert types, tone alert frequencies, portable unit selection, backup power operation. Your lifeline when internet is down.'},
    {'title': 'Field Guide to the Atmosphere', 'author': 'Vincent Schaefer & John Day', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
     'url': 'https://archive.org/download/fieldguidetoatmo00scha/fieldguidetoatmo00scha.pdf', 'description': 'Peterson Field Guide — identify clouds, precipitation types, optical phenomena (halos, rainbows, coronas), lightning, dust and sand features. Read the sky to forecast weather without instruments.'},
    {'title': 'Tornado Preparedness and Response (FEMA 431)', 'author': 'FEMA', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
     'url': 'https://www.fema.gov/sites/default/files/2020-07/fema_tornado-preparedness-and-response_431.pdf', 'description': 'Comprehensive tornado preparedness — shelter construction standards, mobile home risks, warning systems, search and rescue, mass casualty planning. Includes safe room design specifications.'},
    {'title': 'Hurricane Preparedness Guide (FEMA)', 'author': 'FEMA / NOAA', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
     'url': 'https://www.fema.gov/sites/default/files/2020-07/fema_hurricane-preparedness.pdf', 'description': 'Complete hurricane readiness — Saffir-Simpson scale, storm surge risk, evacuation zones, shelter-in-place criteria, post-storm hazards (floodwater, mold, CO). Applicable to any major storm scenario.'},
    # Maps & Navigation Guides
    {'title': 'USGS Topographic Map Symbols', 'author': 'USGS', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
     'url': 'https://pubs.usgs.gov/gip/TopographicMapSymbols/topomapsymbols.pdf', 'description': 'Official guide to USGS topo map symbols — contours, water features, vegetation, structures, roads, boundaries, survey markers. Read any 7.5-minute USGS quad map accurately for land navigation.'},
    {'title': 'FAA Aeronautical Chart User\'s Guide', 'author': 'FAA', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
     'url': 'https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/aero_guide/media/cug-complete.pdf', 'description': 'Complete guide to reading FAA sectional and IFR enroute charts — terrain symbols, obstruction towers, airspace boundaries, VORs, emergency landing strips, restricted areas. Understand all aviation charts.'},
    {'title': 'FEMA Flood Map Reading Guide', 'author': 'FEMA', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
     'url': 'https://www.fema.gov/sites/default/files/2020-07/howto1.pdf', 'description': 'How to read FIRM flood maps — identify your flood zone, base flood elevation, floodway vs. flood fringe, LOMA process. Know if your property floods before you buy or before the water rises.'},
    {'title': 'Map and Compass (Orienteering Handbook)', 'author': 'Kjellström', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
     'url': 'https://archive.org/download/beorienteering00kjel/beorienteering00kjel.pdf', 'description': 'The definitive orienteering reference — magnetic declination, bearings, resection, night navigation, contour interpretation, pace counting, terrain association. From Sweden\'s orienteering master.'},
    {'title': 'Land Navigation (TC 3-25.26)', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
     'url': 'https://archive.org/download/tc-3-25.26-land-navigation/TC_3-25.26_Land_Navigation.pdf', 'description': 'Updated Army land navigation manual — MGRS/UTM coordinates, GPS receiver operation, terrain association, route planning, night navigation, map overlays. Supersedes FM 3-25.26.'},
    {'title': 'USGS Introduction to GIS and Spatial Analysis', 'author': 'USGS / ESRI', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
     'url': 'https://archive.org/download/introductiontogi00usgs/introductiontogi00usgs.pdf', 'description': 'Using GIS for spatial analysis — loading topo maps, elevation analysis, watershed delineation, route optimization. Applicable to QGIS (free) for creating custom offline maps and terrain analysis.'},
    {'title': 'Geologic Hazards — USGS Field Guide', 'author': 'USGS', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
     'url': 'https://pubs.usgs.gov/fs/2013/3094/pdf/fs2013-3094.pdf', 'description': 'Reading geologic maps for hazard identification — landslide susceptibility, earthquake fault zones, volcanic hazards, ground subsidence, debris flows. Identify dangerous terrain from published maps.'},
    {'title': 'Nautical Chart User\'s Guide (NOAA)', 'author': 'NOAA', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
     'url': 'https://nauticalcharts.noaa.gov/publications/docs/chart-users-guide.pdf', 'description': 'Reading NOAA nautical charts — depth soundings, hazard symbols, anchorage areas, aids to navigation, tidal datum, bridge clearances. Navigate coastal and inland waterways without GPS.'},
    # Amateur Radio & Communications
    {'title': 'ARRL Handbook for Radio Communications', 'author': 'ARRL', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
     'url': 'https://archive.org/download/arrl-handbook-1964/arrl_handbook_1964.pdf', 'description': 'The bible of amateur radio — antenna theory, propagation, transmitter/receiver design, digital modes, emergency communication. Public domain 1964 edition; principles unchanged for HF/VHF survival comms.'},
    {'title': 'NIFOG — National Interoperability Field Operations Guide', 'author': 'DHS / SAFECOM', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
     'url': 'https://www.dhs.gov/sites/default/files/publications/NIFOG_v1.7.pdf', 'description': 'Standardized radio channels for multi-agency emergency operations — NPSPAC, VCALL, interoperability channels, programming codes. Know what channels first responders and emergency managers use.'},
    {'title': 'ARRL Emergency Communication Handbook (2nd Ed.)', 'author': 'ARRL', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
     'url': 'https://archive.org/download/arrl-emergency-comm/arrl_emergency_comm_handbook.pdf', 'description': 'ARES/RACES emergency communication protocols — net operations, traffic handling, ICS integration, shelter and EOC setup, disaster communication planning. For serious emergency preparedness.'},
    {'title': 'Introduction to Radio Frequency (RF) Propagation', 'author': 'John Volakis', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
     'url': 'https://archive.org/download/intro-rf-propagation/rf_propagation_intro.pdf', 'description': 'Understanding how radio waves travel — ground wave, sky wave, NVIS, troposcatter, ducting, ionospheric layers. Know when HF will reach across the continent vs. when it won\'t.'},
    {'title': 'Winlink Emergency Digital Radio Email — User Guide', 'author': 'Winlink.org', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
     'url': 'https://winlink.org/sites/default/files/UserGuide/Winlink_Manual.pdf', 'description': 'Email without internet — Winlink 2000 global radio email system. Setup, routing, message templates, ICS forms, peer-to-peer mode (RMS Express/Vara). Works from solar-powered HF radio anywhere on Earth.'},
    {'title': 'JS8Call Digital Messaging — User Manual', 'author': 'Jordan Sherer KN4CRD', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
     'url': 'https://js8call.com/docs/JS8Call_User_Manual.pdf', 'description': 'Store-and-forward text messaging over radio — no repeaters, no internet. JS8Call heartbeat beaconing, directed messages, group messaging, relay through other stations. Designed for off-grid emergency communication.'},
    {'title': 'FCC Part 97 Amateur Radio Rules — Complete Annotated Text', 'author': 'FCC', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
     'url': 'https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-97', 'description': 'Complete FCC Part 97 amateur radio regulations — station identification rules, third-party traffic, emergency communications exemptions, power limits by band, prohibited transmissions, RACES and ARES authorization. Know what you can legally transmit in an emergency.'},
    # Legal & Governance (Post-Disaster)
    {'title': 'FEMA Comprehensive Preparedness Guide CPG 101 (v2.0)', 'author': 'FEMA', 'format': 'pdf', 'category': 'survival', 'folder': 'Legal & Governance',
     'url': 'https://www.fema.gov/sites/default/files/2020-04/CPG_101_V2_30NOV2010_FINAL.pdf', 'description': 'Official emergency operations planning guide — threat/hazard identification, capability assessment, plan development, training and exercise framework. How governments organize emergency response.'},
    {'title': 'Incident Command System (ICS) Reference Guide', 'author': 'FEMA / NIMS', 'format': 'pdf', 'category': 'survival', 'folder': 'Legal & Governance',
     'url': 'https://training.fema.gov/emiweb/is/icsresource/assets/ics%20forms/ics%20form%20201,%20incident%20briefing%20(v3).pdf', 'description': 'ICS organizational structure — command, operations, planning, logistics, finance. ICS forms 201-225. Integrate with any municipal emergency response as a volunteer or team leader.'},
    {'title': 'FEMA Emergency Operations Center (EOC) Reference Guide', 'author': 'FEMA', 'format': 'pdf', 'category': 'survival', 'folder': 'Legal & Governance',
     'url': 'https://www.fema.gov/sites/default/files/2020-07/NIMS_EOC_Reference_Guide.pdf', 'description': 'How Emergency Operations Centers work — staffing, coordination with field teams, resource ordering, situation reports, WebEOC-style status boards. Blueprint for setting up a community command post.'},
    {'title': 'Extreme Heat: A Prevention Guide (CDC)', 'author': 'CDC', 'format': 'pdf', 'category': 'medical', 'folder': 'Legal & Governance',
     'url': 'https://www.cdc.gov/disasters/extremeheat/pdf/extremeheat.pdf', 'description': 'Comprehensive heat emergency guide — heat index thresholds, cooling center setup, identifying heat exhaustion vs. heat stroke, at-risk populations, community notification systems.'},
    # Energy & Power (additional)
    {'title': 'Micro-Hydro Power Systems: Design, Installation and Operation', 'author': 'ITDG / Practical Action', 'format': 'pdf', 'category': 'survival', 'folder': 'Energy & Power',
     'url': 'https://archive.org/download/micro-hydro-power-systems/micro_hydro_power_design.pdf', 'description': 'Generating electricity from streams and rivers — head and flow calculations, turbine selection (Pelton, Turgo, crossflow), penstock sizing, generator wiring, governor control, battery charging integration. Works at any scale from 100W to 10kW.'},
    {'title': 'Wind Energy Basics: A Guide to Home and Community-Scale Wind Energy Systems', 'author': 'Paul Gipe', 'format': 'pdf', 'category': 'survival', 'folder': 'Energy & Power',
     'url': 'https://archive.org/download/wind-energy-basics-gipe/wind_energy_basics.pdf', 'description': 'Small wind turbine fundamentals — site assessment with anemometer, tower height vs. output, horizontal vs. vertical axis designs, battery bank integration, grid-tie vs. off-grid. Covers DIY turbine builds from salvaged alternators.'},
    {'title': 'Battery Storage for Renewable Energy Systems — Lead-Acid and Lithium Compared', 'author': 'NREL / Sandia National Labs', 'format': 'pdf', 'category': 'survival', 'folder': 'Energy & Power',
     'url': 'https://www.nrel.gov/docs/fy19osti/74426.pdf', 'description': 'Practical battery technology comparison — flooded lead-acid vs AGM vs LiFePO4 vs NMC, cycle life at different depths of discharge, temperature effects, BMS requirements, safety and thermal runaway risks, true cost per kWh over lifespan.'},
    # Construction (additional)
    {'title': 'Timber Framing for the Rest of Us: A Guide to Contemporary Post and Beam Construction', 'author': 'Rob Roy', 'format': 'pdf', 'category': 'survival', 'folder': 'Construction',
     'url': 'https://archive.org/download/timber-framing-rest-of-us/timber_framing_rest_of_us.pdf', 'description': 'Traditional timber joinery without modern fasteners — mortise and tenon, dovetail, and scarf joints; timber selection and curing; raising techniques for small crews; structural calculations for simple bents. Build a permanent shelter from standing dead timber.'},
    {'title': 'Adobe and Rammed Earth Buildings: Design and Construction', 'author': 'Paul Graham McHenry', 'format': 'pdf', 'category': 'survival', 'folder': 'Construction',
     'url': 'https://archive.org/download/adobe-rammed-earth-buildings/adobe_rammed_earth.pdf', 'description': 'Building with earth — adobe brick mixing and firing, wall thickness for thermal mass, rammed earth forms and compaction, foundation requirements, weatherproofing, seismic reinforcement, and finish plasters. Build a permanent blast-resistant structure from dirt.'},
    {'title': 'Stone Masonry: A Guide to Dry-Stack, Mortar, and Foundation Construction', 'author': 'Charles McRaven', 'format': 'pdf', 'category': 'survival', 'folder': 'Construction',
     'url': 'https://archive.org/download/stone-masonry-mcraven/stone_masonry_guide.pdf', 'description': 'Building with natural stone — selecting and shaping fieldstone, dry-stack wall techniques, lime and Portland mortar mixes, rubble trench foundations, arch construction, fireplace and chimney building. No quarrying equipment required.'},
    # Radio & Communications (additional)
    {'title': 'APRS — Automatic Packet Reporting System: The Complete Guide', 'author': 'Bob Bruninga WB4APR', 'format': 'pdf', 'category': 'radio', 'folder': 'Radio & Communications',
     'url': 'https://archive.org/download/aprs-complete-guide/aprs_complete_guide.pdf', 'description': 'Real-time digital position and data reporting over amateur radio — iGate setup, digipeater configuration, mobile tracking, weather station integration, message passing, and tactical use during disasters. Works without internet infrastructure.'},
    {'title': 'Emergency Communications with NVIS Antennas', 'author': 'Jerry Sevick W2FMI', 'format': 'pdf', 'category': 'radio', 'folder': 'Radio & Communications',
     'url': 'https://archive.org/download/nvis-antenna-emergency-comms/nvis_emergency_communications.pdf', 'description': 'Near Vertical Incidence Skywave — the emergency communicator\'s most important antenna concept. Explains why low HF antennas (dipoles 10-15 ft high) provide reliable regional coverage 100-400 miles, while high antennas skip over nearby stations. Essential for ARES/RACES net control.'},
    {'title': 'DMR Digital Mobile Radio — Complete Hotspot and Programming Guide', 'author': 'F5UII / DMR-MARC Community', 'format': 'pdf', 'category': 'radio', 'folder': 'Radio & Communications',
     'url': 'https://archive.org/download/dmr-digital-radio-guide/dmr_hotspot_programming_guide.pdf', 'description': 'Digital Mobile Radio from the ground up — Pi-Star hotspot setup, Brandmeister and DMR-MARC network configuration, talk group management, radio programming with CHIRP and CPS, TDMA time slots, color codes, and roaming. Includes Pi-Star offline configuration.'},
    # Legal & Governance (additional)
    {'title': 'FEMA Voluntary Agency Coordination Field Guide', 'author': 'FEMA / National VOAD', 'format': 'pdf', 'category': 'survival', 'folder': 'Legal & Governance',
     'url': 'https://www.nvoad.org/wp-content/uploads/2014/04/long_term_recovery_guide.pdf', 'description': 'Coordinating volunteer organizations during disaster recovery — National VOAD long-term recovery framework, case management, unmet needs assessment, donations management, integration with government EOC. How to work effectively with Red Cross, Salvation Army, and faith-based organizations.'},
    {'title': 'Individual and Family Preparedness Legal Guide — Insurance, Wills, and Documents', 'author': 'FEMA / Ready.gov', 'format': 'pdf', 'category': 'survival', 'folder': 'Legal & Governance',
     'url': 'https://www.ready.gov/sites/default/files/2020-03/ready_family-emergency-plan_2020.pdf', 'description': 'Legal preparedness — which documents to protect (birth certificates, deeds, insurance), power of attorney for emergencies, accessing financial accounts when banks close, insurance claim documentation, and establishing out-of-area contacts for family reunification.'},
    # Aquaponics & Hydroponics
    {'title': 'Aquaponics — Integration of Hydroponics with Aquaculture', 'author': 'FAO', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
     'url': 'https://www.fao.org/3/i4021e/i4021e.pdf', 'description': 'Combined fish and plant production system — system design, fish species selection (tilapia, catfish, carp), nutrient cycling, pH management, media beds vs. NFT vs. DWC, troubleshooting. High-yield food production in small footprints with minimal water.'},
    {'title': 'Small-Scale Aquaponic Food Production — Integrated Fish and Plant Farming', 'author': 'FAO', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
     'url': 'https://www.fao.org/3/i4021e/i4021e00.htm', 'description': 'Practical aquaponics manual — system sizing for family food production, species pairing, seasonal management, pest control in a closed system, water quality testing, emergency protocols for fish illness. Build and maintain a productive year-round food source.'},
    # Blacksmithing & Metalworking
    {'title': 'The Backyard Blacksmith — Traditional Techniques for the Modern Smith', 'author': 'Lorelei Sims', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
     'url': 'https://archive.org/download/backyard-blacksmith-sims/backyard_blacksmith.pdf', 'description': 'Forge setup and coal/propane selection, anvil and hammer techniques, basic forging operations (drawing, upsetting, bending, punching), tool making (tongs, chisels, punches), blade and knife forging, forge welding. Essential skills for repairing and fabricating metal tools.'},
    {'title': 'FM 3-34.343 Military Nonstandard Fixed Bridging — Welding and Metal Fabrication', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'repair', 'folder': 'Army Field Manuals',
     'url': 'https://armypubs.army.mil/epubs/DR_pubs/DR_a/pdf/web/fm3_34x343.pdf', 'description': 'Military field welding — SMAW (stick), MIG setup, cutting torches, metal identification, joint design, welding defects and inspection, underwater cutting, field expedient equipment. Practical metal joining without an ideal shop environment.'},
    # Additional Army Field Manuals
    {'title': 'FM 4-25.11 First Aid (Soldiers Manual of Common Tasks)', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'medical', 'folder': 'Army Field Manuals',
     'url': 'https://armypubs.army.mil/epubs/DR_pubs/DR_a/pdf/web/fm4_25x11.pdf', 'description': 'Comprehensive soldier first aid — controlling hemorrhage with pressure, tourniquet, and packing; airway management; treating burns, fractures, shock, heat and cold injuries; buddy aid and self-aid; litter construction. Updated TCCC-aligned procedures.'},
    {'title': 'FM 7-22.7 The NCO Guide — Leadership, Training, and Discipline', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
     'url': 'https://armypubs.army.mil/epubs/DR_pubs/DR_a/pdf/web/fm7_22x7.pdf', 'description': 'Small-unit leadership principles — conducting training, counseling, establishing standards, enforcing discipline, managing stress, after-action review process. Directly applicable to organizing and leading a survival group under stress.'},
    {'title': 'TC 21-3 Soldier\'s Guide for Field Expedient Methods', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
     'url': 'https://archive.org/download/tc-21-3-soldiers-guide/tc_21_3_field_expedient.pdf', 'description': 'Field-expedient construction and improvisation — rope bridges, water crossing aids, improvised shelters, material recovery and re-use, tools from natural materials, expedient stoves and heating. How to do more with less in field conditions.'},
    # Sanitation & Waste Management
    {'title': 'Sanitation Manual for Isolated Regions — Latrines, Composting, and Grey Water', 'author': 'WHO / UNICEF', 'format': 'pdf', 'category': 'survival', 'folder': 'Water & Sanitation',
     'url': 'https://www.who.int/water_sanitation_health/hygiene/emergencies/emergencychap3.pdf', 'description': 'Emergency sanitation without utilities — simple pit latrines (depth, siting, cover), ventilated improved pit (VIP) design, pour-flush toilets, handwashing station construction, grey water disposal, solid waste management, and preventing cholera and diarrheal disease outbreaks.'},
    # Foraging & Wild Plants
    {'title': 'A Field Guide to Edible Wild Plants: Eastern and Central North America', 'author': 'Lee Allen Peterson', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
     'url': 'https://archive.org/download/field-guide-edible-wild-plants-peterson/peterson_edible_wild_plants.pdf', 'description': 'Comprehensive edible plant identification — 370 species with descriptions, range maps, and preparation notes; poisonous look-alike warnings for each; seasonal availability; roots, berries, leaves, and fungi. Essential for emergency foraging in eastern North America.'},
    {'title': 'Identifying and Harvesting Edible and Medicinal Plants in Wild (and Not So Wild) Places', 'author': 'Steve Brill', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
     'url': 'https://archive.org/download/identifying-harvesting-edible-medicinal-brill/brill_edible_medicinal.pdf', 'description': 'Foraging field guide with strong medicinal focus — over 500 wild species by habitat and season; detailed identification features; cooking and preparation methods; medicinal uses backed by ethnobotany; legal considerations for collecting. Covers urban, suburban, and wilderness environments.'},
    # Community Resilience
    {'title': 'Building Community Resilience — A Neighborhood Preparedness Toolkit', 'author': 'FEMA / Citizen Corps', 'format': 'pdf', 'category': 'survival', 'folder': 'FEMA Guides',
     'url': 'https://www.citizencorps.gov/downloads/pdf/ready/neighbor_toolkit.pdf', 'description': 'Organizing your neighborhood for disaster — block captain roles, neighborhood needs assessments, skill and resource inventories, communication trees, mutual aid agreements, working with first responders. Step-by-step guide to building a prepared community from scratch.'},
    # Veterinary & Animal Medicine
    {'title': 'Where There Is No Animal Doctor', 'author': 'Peter Quesenberry / Christian Veterinary Mission', 'format': 'pdf', 'category': 'farming', 'folder': 'Medical References',
     'url': 'https://archive.org/download/where-no-animal-doctor/where_there_is_no_animal_doctor.pdf', 'description': 'Tropical and rural livestock health without a vet — common diseases by species (cattle, goats, sheep, chickens, pigs), vaccinations, internal parasites, wound care, birthing complications, hoof problems. Illustrated with clear diagnostic flowcharts for non-veterinarians.'},
    {'title': 'The Merck Veterinary Manual — Home Edition', 'author': 'Merck & Co.', 'format': 'pdf', 'category': 'farming', 'folder': 'Medical References',
     'url': 'https://archive.org/download/merck-vet-manual-home/merck_vet_manual_home_ed.pdf', 'description': 'Comprehensive veterinary reference covering all common domesticated species — dogs, cats, horses, cattle, sheep, goats, poultry, swine, rabbits. Disease identification, treatment protocols, drug dosages, nutrition, zoonotic diseases (diseases transmissible to humans).'},
    # Mechanics & Repair
    {'title': 'Audel Millwrights and Mechanics Guide', 'author': 'Thomas Davis', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
     'url': 'https://archive.org/download/audel-millwrights-mechanics-guide/audel_millwrights_mechanics.pdf', 'description': 'Complete mechanical reference — bearings, gears, pumps, motors, rigging, alignment, belts and chains, hydraulics, pneumatics, welding, pipe fitting, concrete work. The one book a community mechanic needs for maintaining equipment without parts suppliers.'},
    {'title': 'FM 5-412 Project Management for Field Construction', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'repair', 'folder': 'Army Field Manuals',
     'url': 'https://armypubs.army.mil/epubs/DR_pubs/DR_a/pdf/web/fm5_412.pdf', 'description': 'Planning and executing construction projects with limited resources — site layout, earthwork calculations, concrete mixing and curing, masonry, basic electrical and plumbing, safety, material estimation, work scheduling. Applicable to building community infrastructure post-disaster.'},
    # Traditional Skills & Crafts
    {'title': 'Foxfire 7 — Plowing, Groundhog Day, Snake Lore, Hunting Tales, Moonshining', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'survival', 'folder': 'Foxfire Series',
     'url': 'https://archive.org/download/foxfire-7/foxfire_7.pdf', 'description': 'Appalachian traditional knowledge — horse-drawn plowing techniques, moonshine distillation (for fuel and medicine), traditional weather forecasting, hunting with dogs, building pole barns. Living history that preserves skills largely lost to industrialization.'},
    {'title': 'Foxfire 8 — Pickles, Churning, Wood Carving, Pig Skinning', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'cooking', 'folder': 'Foxfire Series',
     'url': 'https://archive.org/download/foxfire-8/foxfire_8.pdf', 'description': 'Food preservation and handcraft — traditional pickling without vinegar, butter churning and cheese making, wood carving tools and techniques, hog processing from slaughter to sausage. Essential old-time skills for food security and self-sufficiency.'},
    # Textiles & Fiber
    {'title': 'Handspinning: A Complete Guide to the Craft of Spinning', 'author': 'Eliza Leadbeater', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
     'url': 'https://archive.org/download/handspinning-complete-guide/handspinning_leadbeater.pdf', 'description': 'Fiber processing without industrial equipment — preparing raw wool, cotton, and plant fibers; drop spindle and spinning wheel operation; plying; dyeing with natural materials. Make rope, cord, thread, and yarn from raw materials for clothing repair and net making.'},
    # Navigation — Advanced
    {'title': 'Dutton\'s Nautical Navigation (Abridged)', 'author': 'Maloney / Cutler', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
     'url': 'https://archive.org/download/duttons-navigation-abridged/duttons_navigation.pdf', 'description': 'Celestial navigation — determining position from sun, moon, stars, and planets using sextant; dead reckoning; current corrections; piloting techniques; chart work. Complete position-finding method that works with zero electronics.'},
]

@media_bp.route('/api/books')
def api_books_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM books ORDER BY folder, title LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    bdir = get_books_dir()
    return jsonify([{**dict(r), 'exists': os.path.isfile(os.path.join(bdir, r['filename']))} for r in rows])

@media_bp.route('/api/books/upload', methods=['POST'])
def api_books_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    # Check file size (max 500MB per upload)
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 500 * 1024 * 1024:
        return jsonify({'error': 'File too large (max 500MB)'}), 413
    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400
    filepath = os.path.join(get_books_dir(), filename)
    file.save(filepath)
    filesize = os.path.getsize(filepath) if os.path.isfile(filepath) else 0
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'pdf'
    fmt = ext if ext in ('pdf', 'epub', 'mobi', 'txt') else 'pdf'
    title = request.form.get('title', filename.rsplit('.', 1)[0])
    author = request.form.get('author', '')
    category = request.form.get('category', 'general')
    folder = _sanitize_folder(request.form.get('folder', ''))
    with db_session() as db:
        cur = db.execute('INSERT INTO books (title, author, filename, format, category, folder, filesize) VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (title, author, filename, fmt, category, folder, filesize))
        db.commit()
    log_activity('book_upload', 'media', title)
    return jsonify({'status': 'uploaded', 'id': cur.lastrowid}), 201

@media_bp.route('/api/books/<int:bid>', methods=['DELETE'])
def api_books_delete(bid):
    with db_session() as db:
        row = db.execute('SELECT filename FROM books WHERE id = ?', (bid,)).fetchone()
        if row:
            bdir = get_books_dir()
            filepath = os.path.normpath(os.path.join(bdir, row['filename']))
            if os.path.normcase(filepath).startswith(os.path.normcase(bdir) + os.sep) and os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            db.execute('DELETE FROM books WHERE id = ?', (bid,))
            db.commit()
        return jsonify({'status': 'deleted'})
@media_bp.route('/api/books/<int:bid>', methods=['PATCH'])
def api_books_update(bid):
    data = request.get_json() or {}
    if 'folder' in data:
        data['folder'] = _sanitize_folder(data['folder'])
    ALLOWED_COLS = ['title', 'folder', 'category', 'author', 'last_position']
    filtered = safe_columns(data, ALLOWED_COLS)
    if not filtered:
        return jsonify({'status': 'no changes'})
    sql, params = build_update('books', filtered, ALLOWED_COLS, where_val=bid)
    with db_session() as db:
        db.execute(sql, params)
        db.commit()
        return jsonify({'status': 'updated'})
@media_bp.route('/api/books/serve/<path:filename>')
def api_books_serve(filename):
    bdir = get_books_dir()
    safe = os.path.normcase(os.path.normpath(os.path.join(bdir, filename)))
    if not safe.startswith(os.path.normcase(os.path.normpath(bdir)) + os.sep) or not os.path.isfile(safe):
        return jsonify({'error': 'Not found'}), 404
    from flask import send_file
    return send_file(safe)

@media_bp.route('/api/books/stats')
def api_books_stats():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) as c FROM books').fetchone()['c']
        total_size = db.execute('SELECT COALESCE(SUM(filesize),0) as s FROM books').fetchone()['s']
        by_folder = db.execute('SELECT folder, COUNT(*) as c FROM books GROUP BY folder ORDER BY folder').fetchall()
    return jsonify({'total': total, 'total_size': total_size, 'total_size_fmt': format_size(total_size),
                    'by_folder': [{'folder': r['folder'] or 'Unsorted', 'count': r['c']} for r in by_folder]})

@media_bp.route('/api/books/catalog')
def api_books_catalog():
    return jsonify(REFERENCE_CATALOG)

@media_bp.route('/api/books/download-ref', methods=['POST'])
def api_books_download_ref():
    """Download a reference book from the catalog."""

    data = request.get_json() or {}
    url = data.get('url', '').strip()
    title = data.get('title', '')
    author = data.get('author', '')
    folder = data.get('folder', '')
    category = data.get('category', 'reference')
    fmt = data.get('format', 'pdf')
    if not url:
        return jsonify({'error': 'No URL'}), 400

    # Check if already downloaded
    with db_session() as db:
        existing = db.execute('SELECT id FROM books WHERE url = ?', (url,)).fetchone()
    if existing:
        return jsonify({'status': 'already_downloaded'})

    with _ytdlp_dl_lock:
        _state._ytdlp_dl_counter += 1
        dl_id = str(_state._ytdlp_dl_counter)

    _ytdlp_downloads[dl_id] = {'status': 'downloading', 'percent': 0, 'title': title, 'speed': '', 'error': ''}

    def do_dl():
        bdir = get_books_dir()
        try:
            filename = secure_filename(f'{title}.{fmt}') or f'book_{dl_id}.{fmt}'
            filepath = os.path.join(bdir, filename)
            import requests as req
            resp = req.get(url, stream=True, timeout=120, allow_redirects=True)
            resp.raise_for_status()
            total = int(resp.headers.get('content-length', 0))
            downloaded = 0
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        _ytdlp_downloads[dl_id]['percent'] = int(downloaded / total * 100)
            filesize = os.path.getsize(filepath)
            with db_session() as db:
                db.execute('INSERT INTO books (title, author, filename, format, category, folder, url, filesize) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                           (title, author, filename, fmt, category, folder, url, filesize))
                db.commit()
            _ytdlp_downloads[dl_id] = {'status': 'complete', 'percent': 100, 'title': title, 'speed': '', 'error': ''}
            log_activity('book_download', 'media', title)
        except Exception as e:
            log.exception('Book download failed for %s', dl_id)
            _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': title, 'speed': '', 'error': 'Download failed'}

    threading.Thread(target=do_dl, daemon=True).start()
    return jsonify({'status': 'started', 'id': dl_id})

@media_bp.route('/api/books/download-all-refs', methods=['POST'])
def api_books_download_all_refs():
    """Download all reference catalog books sequentially."""

    with db_session() as db:
        existing_urls = set(r['url'] for r in db.execute('SELECT url FROM books WHERE url != ""').fetchall())
    to_download = [b for b in REFERENCE_CATALOG if b['url'] not in existing_urls]
    if not to_download:
        return jsonify({'status': 'all_downloaded', 'count': 0})

    with _ytdlp_dl_lock:
        _state._ytdlp_dl_counter += 1
        queue_id = str(_state._ytdlp_dl_counter)

    _ytdlp_downloads[queue_id] = {'status': 'queued', 'percent': 0, 'title': f'Queue: 0/{len(to_download)}',
                                   'speed': '', 'error': '', 'queue_total': len(to_download), 'queue_pos': 0}

    def do_queue():
        bdir = get_books_dir()
        for i, item in enumerate(to_download):
            _ytdlp_downloads[queue_id].update({
                'status': 'downloading', 'percent': 0, 'queue_pos': i + 1,
                'title': f'[{i+1}/{len(to_download)}] {item["title"]}',
            })
            try:
                filename = secure_filename(f'{item["title"]}.{item.get("format","pdf")}')
                filepath = os.path.join(bdir, filename)
                # SSRF protection on download URL
                try:
                    _validate_download_url(item['url'])
                except ValueError as ve:
                    log.warning(f'Blocked unsafe book URL: {ve}')
                    continue
                import requests as req
                resp = req.get(item['url'], stream=True, timeout=120, allow_redirects=True)
                resp.raise_for_status()
                total = int(resp.headers.get('content-length', 0))
                downloaded = 0
                with open(filepath, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            _ytdlp_downloads[queue_id]['percent'] = int(downloaded / total * 100)
                filesize = os.path.getsize(filepath)
                with db_session() as db:
                    db.execute('INSERT INTO books (title, author, filename, format, category, folder, url, filesize) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                               (item['title'], item.get('author',''), filename, item.get('format','pdf'),
                                item.get('category','reference'), item.get('folder',''), item['url'], filesize))
                    db.commit()
            except Exception as e:
                log.error(f'Reference download failed for {item["title"]}: {e}')

        _ytdlp_downloads[queue_id] = {'status': 'complete', 'percent': 100, 'title': f'Done — {len(to_download)} books',
                                       'speed': '', 'error': '', 'queue_total': len(to_download), 'queue_pos': len(to_download)}

    threading.Thread(target=do_queue, daemon=True).start()
    return jsonify({'status': 'queued', 'id': queue_id, 'count': len(to_download)})

@media_bp.route('/api/media/stats')
def api_media_stats():
    """Combined stats for all media types."""
    with db_session() as db:
        v_count = db.execute('SELECT COUNT(*) as c FROM videos').fetchone()['c']
        v_size = db.execute('SELECT COALESCE(SUM(filesize),0) as s FROM videos').fetchone()['s']
        a_count = db.execute('SELECT COUNT(*) as c FROM audio').fetchone()['c']
        a_size = db.execute('SELECT COALESCE(SUM(filesize),0) as s FROM audio').fetchone()['s']
        b_count = db.execute('SELECT COUNT(*) as c FROM books').fetchone()['c']
        b_size = db.execute('SELECT COALESCE(SUM(filesize),0) as s FROM books').fetchone()['s']
    total_size = v_size + a_size + b_size
    return jsonify({
        'videos': {'count': v_count, 'size': v_size, 'size_fmt': format_size(v_size)},
        'audio': {'count': a_count, 'size': a_size, 'size_fmt': format_size(a_size)},
        'books': {'count': b_count, 'size': b_size, 'size_fmt': format_size(b_size)},
        'total_size': total_size, 'total_size_fmt': format_size(total_size),
    })

# ─── Media Enhancements (v5.0 Phase 6) ──────────────────────────

@media_bp.route('/api/media/progress/<media_type>/<int:media_id>', methods=['GET'])
def api_media_progress_get(media_type, media_id):
    """Get playback progress for a media item."""
    if media_type not in ('video', 'audio', 'book'):
        return jsonify({'error': 'Invalid media type'}), 400
    with db_session() as db:
        row = db.execute('SELECT * FROM media_progress WHERE media_type = ? AND media_id = ?', (media_type, media_id)).fetchone()
        return jsonify(dict(row) if row else {'position_sec': 0, 'duration_sec': 0, 'completed': 0})
@media_bp.route('/api/media/progress/<media_type>/<int:media_id>', methods=['PUT'])
def api_media_progress_update(media_type, media_id):
    """Update playback progress for a media item."""
    if media_type not in ('video', 'audio', 'book'):
        return jsonify({'error': 'Invalid media type'}), 400
    d = request.json or {}
    with db_session() as db:
        db.execute(
            '''INSERT INTO media_progress (media_type, media_id, position_sec, duration_sec, completed, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(media_type, media_id) DO UPDATE SET
               position_sec = excluded.position_sec, duration_sec = excluded.duration_sec,
               completed = excluded.completed, updated_at = CURRENT_TIMESTAMP''',
            (media_type, media_id, d.get('position_sec', 0), d.get('duration_sec', 0), d.get('completed', 0))
        )
        db.commit()
        return jsonify({'status': 'ok'})
@media_bp.route('/api/media/resume')
def api_media_resume_list():
    """Get all in-progress media for 'Continue Watching/Listening' section."""
    with db_session() as db:
        rows = db.execute(
            '''SELECT mp.*,
               CASE mp.media_type
                 WHEN 'video' THEN (SELECT title FROM videos WHERE id = mp.media_id)
                 WHEN 'audio' THEN (SELECT title FROM audio WHERE id = mp.media_id)
                 WHEN 'book' THEN (SELECT title FROM books WHERE id = mp.media_id)
               END as title
               FROM media_progress mp
               WHERE mp.completed = 0 AND mp.position_sec > 10
               ORDER BY mp.updated_at DESC LIMIT 20'''
        ).fetchall()
        return jsonify([dict(r) for r in rows])
@media_bp.route('/api/playlists', methods=['GET'])
def api_playlists():
    """List all playlists."""
    media_type = request.args.get('type', '')
    with db_session() as db:
        if media_type:
            rows = db.execute('SELECT * FROM playlists WHERE media_type = ? ORDER BY updated_at DESC LIMIT 500', (media_type,)).fetchall()
        else:
            rows = db.execute('SELECT * FROM playlists ORDER BY updated_at DESC LIMIT 500').fetchall()
        return jsonify([dict(r) for r in rows])
@media_bp.route('/api/playlists', methods=['POST'])
def api_playlist_create():
    """Create a new playlist."""
    d = request.json or {}
    name = d.get('name', 'New Playlist').strip()
    media_type = d.get('media_type', 'audio')
    with db_session() as db:
        db.execute('INSERT INTO playlists (name, media_type, items) VALUES (?, ?, ?)',
                   (name, media_type, json.dumps(d.get('items', []))))
        db.commit()
        pid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        return jsonify({'id': pid, 'status': 'ok'})
@media_bp.route('/api/playlists/<int:pid>', methods=['PUT'])
def api_playlist_update(pid):
    """Update a playlist."""
    d = request.json or {}
    with db_session() as db:
        update_data = {}
        for field in ('name', 'items'):
            if field in d:
                update_data[field] = json.dumps(d[field]) if field == 'items' else d[field]
        filtered = safe_columns(update_data, ['name', 'items'])
        if filtered:
            set_clause = ', '.join(f'{col} = ?' for col in filtered)
            params = list(filtered.values())
            params.append(pid)
            r = db.execute(f'UPDATE playlists SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', params)
            if r.rowcount == 0:
                return jsonify({'error': 'not found'}), 404
            db.commit()
        return jsonify({'status': 'ok'})
@media_bp.route('/api/playlists/<int:pid>', methods=['DELETE'])
def api_playlist_delete(pid):
    """Delete a playlist."""
    with db_session() as db:
        r = db.execute('DELETE FROM playlists WHERE id = ?', (pid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
        return jsonify({'status': 'ok'})
@media_bp.route('/api/media/<media_type>/<int:media_id>/metadata', methods=['PUT'])
def api_media_metadata_update(media_type, media_id):
    """Update metadata for a media item."""
    _MEDIA_META_TABLES = {'videos', 'audio', 'books'}
    table_map = {'video': 'videos', 'audio': 'audio', 'book': 'books'}
    table = safe_table(table_map.get(media_type, ''), _MEDIA_META_TABLES) if table_map.get(media_type) else None
    if not table:
        return jsonify({'error': 'Invalid media type'}), 400
    d = request.json or {}
    allowed = {'title', 'category', 'notes', 'description'}
    if media_type == 'audio':
        allowed.update({'artist', 'album'})
    if media_type == 'book':
        allowed.update({'author', 'description'})
    filtered = safe_columns(d, allowed)
    if not filtered:
        return jsonify({'error': 'No valid fields'}), 400
    sql, params = build_update(table, filtered, allowed, where_val=media_id)
    with db_session() as db:
        db.execute(sql, params)
        db.commit()
        return jsonify({'status': 'ok'})
# [EXTRACTED to blueprint] Medical vitals trend + expiring meds + reference


# ─── Network Throughput Benchmark (v5.0 Phase 12) ────────────────


# ─── Built-in BitTorrent Client ───────────────────────────────────

from services.torrent import get_manager as _torrent_mgr, is_available as _torrent_avail

@media_bp.route('/api/torrent/available')
def api_torrent_available():
    return jsonify({'available': _torrent_avail()})

@media_bp.route('/api/torrent/add', methods=['POST'])
def api_torrent_add():
    d = request.json or {}
    magnet = (d.get('magnet') or '').strip()
    name = d.get('name', '')
    torrent_id = d.get('torrent_id', '')
    if not magnet.startswith('magnet:'):
        return jsonify({'error': 'Invalid magnet link'}), 400
    try:
        h = _torrent_mgr().add_magnet(magnet, name, torrent_id)
        return jsonify({'hash': h})
    except RuntimeError as e:
        return jsonify({'error': str(e), 'unavailable': True}), 503
    except Exception as e:
        log.exception('Torrent add failed')
        return jsonify({'error': 'Failed to add torrent'}), 500

@media_bp.route('/api/torrent/status')
def api_torrent_status_all():
    try:
        return jsonify(_torrent_mgr().get_all_status())
    except Exception:
        return jsonify([])

@media_bp.route('/api/torrent/status/<ih>')
def api_torrent_status_one(ih):
    try:
        return jsonify(_torrent_mgr().get_status(ih))
    except Exception as e:
        log.exception('Torrent status failed')
        return jsonify({'error': 'Failed to get status'}), 500

@media_bp.route('/api/torrent/pause/<ih>', methods=['POST'])
def api_torrent_pause(ih):
    _torrent_mgr().pause(ih)
    return jsonify({'ok': True})

@media_bp.route('/api/torrent/resume/<ih>', methods=['POST'])
def api_torrent_resume(ih):
    _torrent_mgr().resume(ih)
    return jsonify({'ok': True})

@media_bp.route('/api/torrent/remove/<ih>', methods=['DELETE'])
def api_torrent_remove(ih):
    delete_files = request.args.get('delete_files', 'false').lower() == 'true'
    _torrent_mgr().remove(ih, delete_files)
    return jsonify({'ok': True})

@media_bp.route('/api/torrent/open-folder/<ih>', methods=['POST'])
def api_torrent_open_folder(ih):
    try:
        _torrent_mgr().open_save_folder(ih)
        return jsonify({'ok': True})
    except Exception as e:
        log.exception('Torrent open folder failed')
        return jsonify({'error': 'Failed to open folder'}), 500

@media_bp.route('/api/torrent/dir')
def api_torrent_dir():
    d = os.path.join(get_data_dir(), 'torrents')
    return jsonify({'path': d})

# ─── Unified Download Queue ──────────────────────────────────────

@media_bp.route('/api/downloads/queue', methods=['GET'])
def api_download_queue():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM download_queue ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])
@media_bp.route('/api/downloads/retry/<int:did>', methods=['POST'])
def api_download_retry(did):
    with db_session() as db:
        row = db.execute('SELECT * FROM download_queue WHERE id = ? AND status = "failed"', (did,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found or not failed'}), 404
        if row['retries'] >= 3:
            return jsonify({'error': 'Max retries exceeded'}), 400
        db.execute('UPDATE download_queue SET status = "queued", error = NULL WHERE id = ?', (did,))
        db.commit()
        # Re-trigger download
        return jsonify({'requeued': True})
