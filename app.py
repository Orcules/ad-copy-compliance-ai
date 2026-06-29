import os
import json
import logging
from flask import Flask, request, jsonify, send_from_directory
from openai_client import OpenAIClient
from compliance import ComplianceChecker
from google_sheets_client import GoogleSheetsClient
from article_scraper import ArticleScraper
from gcs_article_service import GCSArticleService
import pandas as pd
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize clients
openai_client = OpenAIClient()
compliance_checker = ComplianceChecker()
article_scraper = ArticleScraper()

# Initialize Google Sheets client (optional - will fallback if not available)
try:
    sheets_client = GoogleSheetsClient(os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json"))
    logger.info("✅ Google Sheets client initialized")
except Exception as e:
    logger.warning(f"⚠️ Google Sheets client not available: {e}")
    logger.info("Will use fallback templates and languages")
    sheets_client = None

# Initialize GCS service (optional - will fallback to scraping if not available)
try:
    gcs_service = GCSArticleService(
        credentials_file=os.environ.get('GOOGLE_SERVICE_ACCOUNT_FILE', 'service_account.json'),
        bucket_name=os.environ.get('GCS_BUCKET_NAME', 'your-gcs-bucket'),
        folder_name=os.environ.get('GCS_FOLDER_NAME', 'articles2025')
    )
    logger.info("✅ GCS Article Service initialized")
except Exception as e:
    logger.warning(f"⚠️ GCS service not available: {e}")
    logger.info("Will use web scraping and manual text input only")
    gcs_service = None

# Google Sheets URLs
TEMPLATES_SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit?gid=2132390472#gid=2132390472"
LANGUAGES_SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit?gid=2044055963#gid=2044055963"

# Cached data loaded from Google Sheets
_LANG_CACHE = None
_LANG_BY_GEO = None
_GEOS = None
_LOADING_IN_PROGRESS = False

def ensure_data_loaded():
    """Ensure countries and languages data is loaded (with caching to prevent quota issues)"""
    global _LANG_CACHE, _LOADING_IN_PROGRESS
    
    if _LANG_CACHE is not None:
        return True  # Already loaded
    
    if _LOADING_IN_PROGRESS:
        return False  # Loading in progress, don't retry
    
    try:
        _LOADING_IN_PROGRESS = True
        load_countries_languages_from_sheets()
        logger.info("✅ Countries and languages loaded successfully")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Failed to load countries/languages: {e}")
        return False
    finally:
        _LOADING_IN_PROGRESS = False

# Try to load data on startup (after variables are defined)
try:
    if sheets_client:
        ensure_data_loaded()
except Exception as e:
    logger.warning(f"⚠️ Failed to load data on startup: {e}")

def _normalize_lang_code_name(value: str) -> dict:
    """Normalize language code/name using data from Google Sheets if available"""
    if not value:
        return {"code": "", "name": ""}
    
    # Ensure data is loaded (with caching)
    ensure_data_loaded()
    
    # If we have loaded language data from Google Sheets, use it
    if _LANG_CACHE and 'languages' in _LANG_CACHE:
        value_lower = str(value).strip().lower()
        
        # Try to find exact match by code
        for lang in _LANG_CACHE['languages']:
            if lang['code'].lower() == value_lower:
                return {"code": lang['code'], "name": lang['name']}
        
        # Try to find match by name
        for lang in _LANG_CACHE['languages']:
            if lang['name'].lower() == value_lower:
                return {"code": lang['code'], "name": lang['name']}
    
    # Fallback to static mapping if Google Sheets data not available
    mapping = {
        'english': ('en', 'English'), 'en': ('en','English'),
        'hebrew': ('he', 'Hebrew'), 'he': ('he','Hebrew'),
        'arabic': ('ar', 'Arabic'), 'ar': ('ar','Arabic'),
        'russian': ('ru', 'Russian'), 'ru': ('ru','Russian'),
        'spanish': ('es', 'Spanish'), 'es': ('es','Spanish'),
        'french': ('fr', 'French'), 'fr': ('fr','French'),
        'german': ('de', 'German'), 'de': ('de','German'),
        'italian': ('it', 'Italian'), 'it': ('it','Italian'),
        'portuguese': ('pt', 'Portuguese'), 'pt': ('pt','Portuguese'),
        'dutch': ('nl', 'Dutch'), 'nl': ('nl','Dutch'),
        'swedish': ('sv', 'Swedish'), 'sv': ('sv','Swedish'),
        'danish': ('da', 'Danish'), 'da': ('da','Danish'),
        'norwegian': ('no', 'Norwegian'), 'no': ('no','Norwegian'),
        'finnish': ('fi', 'Finnish'), 'fi': ('fi','Finnish'),
        'polish': ('pl', 'Polish'), 'pl': ('pl','Polish'),
        'czech': ('cs', 'Czech'), 'cs': ('cs','Czech'),
        'hungarian': ('hu', 'Hungarian'), 'hu': ('hu','Hungarian'),
        'romanian': ('ro', 'Romanian'), 'ro': ('ro','Romanian'),
        'bulgarian': ('bg', 'Bulgarian'), 'bg': ('bg','Bulgarian'),
        'greek': ('el', 'Greek'), 'el': ('el','Greek'),
        'turkish': ('tr', 'Turkish'), 'tr': ('tr','Turkish'),
        'ukrainian': ('uk', 'Ukrainian'), 'uk': ('uk','Ukrainian'),
        'croatian': ('hr', 'Croatian'), 'hr': ('hr','Croatian'),
        'serbian': ('sr', 'Serbian'), 'sr': ('sr','Serbian'),
        'slovenian': ('sl', 'Slovenian'), 'sl': ('sl','Slovenian'),
        'slovak': ('sk', 'Slovak'), 'sk': ('sk','Slovak'),
        'lithuanian': ('lt', 'Lithuanian'), 'lt': ('lt','Lithuanian'),
        'latvian': ('lv', 'Latvian'), 'lv': ('lv','Latvian'),
        'estonian': ('et', 'Estonian'), 'et': ('et','Estonian'),
        'chinese': ('zh', 'Chinese'), 'zh': ('zh','Chinese'),
        'japanese': ('ja', 'Japanese'), 'ja': ('ja','Japanese'),
        'korean': ('ko', 'Korean'), 'ko': ('ko','Korean'),
        'thai': ('th', 'Thai'), 'th': ('th','Thai'),
        'vietnamese': ('vi', 'Vietnamese'), 'vi': ('vi','Vietnamese'),
        'hindi': ('hi', 'Hindi'), 'hi': ('hi','Hindi'),
        'bengali': ('bn', 'Bengali'), 'bn': ('bn','Bengali'),
        'urdu': ('ur', 'Urdu'), 'ur': ('ur','Urdu'),
        'persian': ('fa', 'Persian'), 'fa': ('fa','Persian'),
        'indonesian': ('id', 'Indonesian'), 'id': ('id','Indonesian'),
        'malay': ('ms', 'Malay'), 'ms': ('ms','Malay')
    }
    key = str(value).strip().lower()
    if key in mapping:
        code, name = mapping[key]
        return {"code": code, "name": name}
    # Final fallback: use the value as-is
    return {"code": value.lower()[:2], "name": value.title()}

def detect_country_from_language(language_code: str) -> str:
    """Detect most likely country/GEO from language code using the loaded data"""
    # Ensure data is loaded (with caching)
    ensure_data_loaded()
    
    if not _LANG_BY_GEO or not language_code:
        return ''
    
    # Language to primary country mapping
    primary_countries = {
        'he': 'IL',  # Hebrew -> Israel
        'ar': 'SA',  # Arabic -> Saudi Arabia (most common)
        'en': 'US',  # English -> United States
        'ru': 'RU',  # Russian -> Russia
        'es': 'ES',  # Spanish -> Spain
        'fr': 'FR',  # French -> France
        'de': 'DE',  # German -> Germany
        'it': 'IT',  # Italian -> Italy
        'pt': 'BR',  # Portuguese -> Brazil
        'ja': 'JP',  # Japanese -> Japan
        'ko': 'KR',  # Korean -> South Korea
        'zh': 'CN',  # Chinese -> China
        'sv': 'SE',  # Swedish -> Sweden
        'da': 'DK',  # Danish -> Denmark
        'no': 'NO',  # Norwegian -> Norway
        'fi': 'FI',  # Finnish -> Finland
        'pl': 'PL',  # Polish -> Poland
        'nl': 'NL',  # Dutch -> Netherlands
        'cs': 'CZ',  # Czech -> Czech Republic
        'hu': 'HU',  # Hungarian -> Hungary
        'ro': 'RO',  # Romanian -> Romania
        'bg': 'BG',  # Bulgarian -> Bulgaria
        'el': 'GR',  # Greek -> Greece
        'tr': 'TR',  # Turkish -> Turkey
        'uk': 'UA',  # Ukrainian -> Ukraine
        'hr': 'HR',  # Croatian -> Croatia
        'sr': 'RS',  # Serbian -> Serbia
        'sl': 'SI',  # Slovenian -> Slovenia
        'sk': 'SK',  # Slovak -> Slovakia
        'lt': 'LT',  # Lithuanian -> Lithuania
        'lv': 'LV',  # Latvian -> Latvia
        'et': 'EE',  # Estonian -> Estonia
        'th': 'TH',  # Thai -> Thailand
        'vi': 'VN',  # Vietnamese -> Vietnam
        'hi': 'IN',  # Hindi -> India
        'bn': 'BD',  # Bengali -> Bangladesh
        'ur': 'PK',  # Urdu -> Pakistan
        'fa': 'IR',  # Persian -> Iran
        'id': 'ID',  # Indonesian -> Indonesia
        'ms': 'MY',  # Malay -> Malaysia
    }
    
    lang_code = language_code.lower().strip()
    
    # Always use direct mapping first (more accurate than Google Sheets search)
    if lang_code in primary_countries:
        return primary_countries[lang_code]
    
    # If not in primary mapping, search through Google Sheets data
    if _LANG_BY_GEO:
        for geo_code, geo_data in _LANG_BY_GEO.items():
            if lang_code in geo_data:
                return geo_code
    
    return ''  # No country found

def get_country_name_from_geo(geo_code: str) -> str:
    """Get country name from GEO code using loaded data"""
    # Ensure data is loaded (with caching)
    ensure_data_loaded()
    
    # Always use fallback mapping first, then try Google Sheets data
    fallback_countries = {
        'IL': 'Israel', 'US': 'United States', 'SE': 'Sweden', 'DE': 'Germany',
        'FR': 'France', 'ES': 'Spain', 'IT': 'Italy', 'RU': 'Russia',
        'SA': 'Saudi Arabia', 'BR': 'Brazil', 'JP': 'Japan', 'KR': 'South Korea',
        'CN': 'China', 'DK': 'Denmark', 'NO': 'Norway', 'FI': 'Finland',
        'PL': 'Poland', 'NL': 'Netherlands', 'CZ': 'Czech Republic',
        'HU': 'Hungary', 'RO': 'Romania', 'BG': 'Bulgaria', 'GR': 'Greece',
        'TR': 'Turkey', 'UA': 'Ukraine', 'HR': 'Croatia', 'RS': 'Serbia',
        'AT': 'Austria', 'BE': 'Belgium', 'CH': 'Switzerland', 'PT': 'Portugal'
    }
    
    # Try fallback first
    if geo_code and geo_code.upper() in fallback_countries:
        return fallback_countries[geo_code.upper()]
    
    if not _LANG_BY_GEO or not geo_code:
        return geo_code  # Return GEO code if no mapping available
    
    geo_data = _LANG_BY_GEO.get(geo_code.upper(), {})
    return geo_data.get('_country_name', geo_code)

def load_countries_languages_from_sheets():
    """Load countries and languages from Google Sheets or offline backup"""
    global _LANG_CACHE, _LANG_BY_GEO, _GEOS
    try:
        # Try Google Sheets first
        if sheets_client:
            try:
                data = sheets_client.get_worksheet_data(LANGUAGES_SPREADSHEET_URL, gid="2044055963")
                logger.info("✅ Loaded languages from Google Sheets")
            except Exception as sheets_error:
                logger.warning(f"Google Sheets failed, using offline backup: {sheets_error}")
                # Load from offline backup
                with open('offline_languages.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info("✅ Loaded languages from offline backup")
        else:
            # Load from offline backup
            with open('offline_languages.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info("✅ Loaded languages from offline backup (no Google Sheets client)")
        
        geos = []
        countries = []
        _LANG_BY_GEO = {}
        all_langs_map = {}
        
        # Skip header row if exists
        for i, row in enumerate(data):
            if i == 0 or not row or len(row) < 3:  # Skip header or incomplete rows
                continue
                
            # Get GEO from column A (index 0), Country from column B (index 1)
            geo_code = row[0].strip() if len(row) > 0 and row[0] else ''
            country_name = row[1].strip() if len(row) > 1 and row[1] else ''
            
            if not geo_code or not country_name:
                continue
            
            # Get all languages from column C (index 2) onwards
            languages = []
            for col_idx in range(2, len(row)):  # From column C onwards
                if row[col_idx] and str(row[col_idx]).strip():
                    lang_value = str(row[col_idx]).strip()
                    # Handle comma-separated languages in a single cell
                    if ',' in lang_value:
                        languages.extend([lang.strip() for lang in lang_value.split(',') if lang.strip()])
                    else:
                        languages.append(lang_value)
            
            if not languages:
                continue
            
            geos.append(geo_code)
            countries.append(country_name)
            geo_key = geo_code.strip().upper()
            _LANG_BY_GEO.setdefault(geo_key, {})
            
            # Add country name to geo mapping for easier lookup
            _LANG_BY_GEO[geo_key]['_country_name'] = country_name
            
            # Process each language for this geo
            for language in languages:
                lang_norm = _normalize_lang_code_name(language)
                _LANG_BY_GEO[geo_key][lang_norm['code']] = {
                    "code": lang_norm['code'],
                    "name": lang_norm['name']
                }
                
                if lang_norm['code'] not in all_langs_map:
                    all_langs_map[lang_norm['code']] = {"code": lang_norm['code'], "name": lang_norm['name']}
        
        # Deduplicate geos preserving order
        seen = set()
        _GEOS = [g for g in geos if not (g in seen or seen.add(g))]
        _LANG_CACHE = {"languages": list(all_langs_map.values())}
        
        logger.info(f"Loaded {len(_GEOS)} GEO codes, {len(set(countries))} countries and {len(all_langs_map)} languages from Google Sheets")
        logger.info(f"GEO codes: {_GEOS[:10]}{'...' if len(_GEOS) > 10 else ''}")
        return _LANG_CACHE
        
    except Exception as e:
        logger.error(f"Failed to load countries/languages from Google Sheets: {e}")
        # Fallback to default languages
        _LANG_CACHE = {"languages": [
            {"code": "en", "name": "English"},
            {"code": "he", "name": "Hebrew"},
            {"code": "ar", "name": "Arabic"},
            {"code": "ru", "name": "Russian"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"}
        ]}
        _LANG_BY_GEO = {}
        _GEOS = []
        return _LANG_CACHE

def load_languages_from_excel():
    """Deprecated: Use load_countries_languages_from_sheets() instead"""
    return load_countries_languages_from_sheets()

@app.route('/api/languages', methods=['GET'])
def get_languages():
    """Return languages; if geo is provided, filter to languages for that Country."""
    try:
        if _LANG_CACHE is None:
            load_countries_languages_from_sheets()
        
        geo = request.args.get('geo')
        logger.info(f"Languages request for geo: {geo}")
        
        if geo and _LANG_BY_GEO:
            langs_map = _LANG_BY_GEO.get(str(geo).upper(), {})
            logger.info(f"Found {len(langs_map)} entries for {geo}: {list(langs_map.keys())}")
            
            if langs_map:
                geo_languages = []
                for key, value in langs_map.items():
                    if not isinstance(value, dict):
                        logger.debug(f"Skipping non-language entry for {geo}: key={key}, value={value}")
                        continue
                    
                    code = value.get('code')
                    name = value.get('name') or code
                    
                    if not code:
                        logger.debug(f"Skipping language entry without code for {geo}: {value}")
                        continue
                    
                    geo_languages.append({
                        "code": code,
                        "name": name
                    })
                
                if geo_languages:
                    return jsonify({"ok": True, "languages": geo_languages})
        
        # Return all languages if no geo specified or no specific languages found
        all_languages = _LANG_CACHE.get('languages', []) if _LANG_CACHE else []
        logger.info(f"Returning all {len(all_languages)} languages")
        return jsonify({"ok": True, "languages": all_languages})
        
    except Exception as e:
        logger.error(f"Error fetching languages: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/geos', methods=['GET'])
def get_geos():
    """Return ordered unique Country list from Google Sheets with country names."""
    try:
        ensure_data_loaded()
        
        # Build list of countries with GEO codes and names
        countries_list = []
        if _LANG_BY_GEO and _GEOS:
            for geo_code in _GEOS:
                geo_data = _LANG_BY_GEO.get(geo_code.upper(), {})
                country_name = geo_data.get('_country_name', geo_code)
                countries_list.append({
                    "geo": geo_code,
                    "name": country_name,
                    "display": f"{country_name} ({geo_code})"
                })
        else:
            # Fallback list of common countries if Google Sheets unavailable
            fallback_countries = [
                {"geo": "IL", "name": "Israel", "display": "Israel (IL)"},
                {"geo": "US", "name": "United States", "display": "United States (US)"},
                {"geo": "SE", "name": "Sweden", "display": "Sweden (SE)"},
                {"geo": "DE", "name": "Germany", "display": "Germany (DE)"},
                {"geo": "FR", "name": "France", "display": "France (FR)"},
                {"geo": "ES", "name": "Spain", "display": "Spain (ES)"},
                {"geo": "IT", "name": "Italy", "display": "Italy (IT)"},
                {"geo": "NL", "name": "Netherlands", "display": "Netherlands (NL)"},
                {"geo": "DK", "name": "Denmark", "display": "Denmark (DK)"},
                {"geo": "NO", "name": "Norway", "display": "Norway (NO)"},
                {"geo": "FI", "name": "Finland", "display": "Finland (FI)"}
            ]
            countries_list = fallback_countries
            logger.warning("Using fallback countries list due to Google Sheets quota issues")
        
        logger.info(f"Returning {len(countries_list)} countries")
        return jsonify({"ok": True, "countries": countries_list})
    except Exception as e:
        logger.error(f"Error fetching countries: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

def get_notes_for_geo_lang(geo: str, lang_code: str) -> str:
    if _LANG_CACHE is None:
        load_languages_from_excel()
    if not geo or not lang_code or not _LANG_BY_GEO:
        return ''
    entry = _LANG_BY_GEO.get(str(geo).upper(), {}).get(str(lang_code).lower())
    return entry.get('notes','') if entry else ''

@app.route('/')
def serve_ui():
    """Serve the main UI page"""
    return send_from_directory('static', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

@app.route('/api/generate', methods=['POST'])
def generate_ads():
    """Generate ad copy using OpenAI and run compliance checks"""
    try:
        # Parse request
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No JSON data provided"}), 400
        
        # Validate required fields
        required_fields = ['platform', 'geo', 'language', 'tone', 'keywords', 'constraints', 'n_variants']
        for field in required_fields:
            if field not in data:
                return jsonify({"ok": False, "error": f"Missing required field: {field}"}), 400
        
        # Generate ads using OpenAI
        logger.info(f"Generating {data['n_variants']} ads for {data['platform']} in {data['language']}")
        # Localization notes from Sheet6 column L for selected (geo, language)
        localization_notes = get_notes_for_geo_lang(data['geo'], data['language'])
        openai_response = openai_client.generate_ads(
            platform=data['platform'],
            geo=data['geo'],
            language=data['language'],
            tone=data['tone'],
            keywords=data['keywords'],
            constraints=data['constraints'],
            n_variants=data['n_variants'],
            localization_notes=localization_notes
        )
        
        if not openai_response.get('ok'):
            return jsonify(openai_response), 500
        
        # Process each ad through compliance checks
        items = []
        for ad_asset in openai_response['ad_assets']:
            # Run moderation check
            moderation_result = openai_client.check_moderation(ad_asset)
            
            # Run compliance check
            compliance_result = compliance_checker.check_compliance(
                ad_asset=ad_asset,
                platform=data['platform'],
                geo=data['geo'],
                language=data['language']
            )
            
            items.append({
                "asset": ad_asset,
                "moderation": moderation_result,
                "compliance": compliance_result
            })
        
        # Return normalized response
        response = {
            "ok": True,
            "platform": data['platform'],
            "geo": data['geo'],
            "language": data['language'],
            "tone": data['tone'],
            "n": data['n_variants'],
            "items": items
        }
        
        logger.info(f"Successfully generated {len(items)} ads")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error generating ads: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/templates', methods=['GET'])
def get_templates():
    """Get available templates from Google Sheets"""
    try:
        logger.info("Fetching templates from Google Sheets...")
        logger.info(f"Templates URL: {TEMPLATES_SPREADSHEET_URL}")
        
        if not sheets_client:
            raise Exception("Google Sheets client not available")
        
        try:
            templates = sheets_client.get_templates_from_sheet(TEMPLATES_SPREADSHEET_URL, "Templates")
            logger.info("✅ Loaded templates from Google Sheets")
        except Exception as sheets_error:
            logger.warning(f"Google Sheets failed, using offline backup: {sheets_error}")
            # Load from offline backup
            try:
                with open('offline_templates.json', 'r', encoding='utf-8') as f:
                    templates = json.load(f)
                logger.info(f"✅ Loaded {len(templates)} templates from offline backup")
            except Exception as file_error:
                logger.error(f"Failed to load offline templates: {file_error}")
                # Final fallback
                templates = [
                    {"id": "1", "name": "Question-Based", "description": "Creates curiosity through questions", "prompt": "Create a compelling question-based headline"},
                    {"id": "2", "name": "Curiosity Gap", "description": "Creates knowledge gaps to drive clicks", "prompt": "Create a curiosity-driven headline"},
                    {"id": "3", "name": "Time & Trends", "description": "Focuses on current trends and timing", "prompt": "Create a trend-focused headline"},
                    {"id": "4", "name": "Benefit & Impact", "description": "Highlights benefits and outcomes", "prompt": "Create a benefit-focused headline"},
                    {"id": "5", "name": "Guide & Overview", "description": "Comprehensive guide format", "prompt": "Create a guide-style headline"}
                ]
                logger.info(f"Using {len(templates)} basic fallback templates")
        
        logger.info(f"Successfully fetched {len(templates)} templates")
        for i, template in enumerate(templates):
            logger.info(f"Template {i}: {template.get('name', 'No name')} - {template.get('id', 'No ID')}")
        
        # If no templates found, provide fallback templates
        if not templates:
            logger.warning("No templates found in Google Sheets, using fallback templates")
            templates = [
                {
                    'id': 'guide_overview',
                    'name': 'Guide & Overview',
                    'prompt': 'Create comprehensive guides and general overviews that promise complete information and full guidance to the reader',
                    'description': 'Comprehensive guides and general overviews'
                },
                {
                    'id': 'how_to',
                    'name': 'How To',
                    'prompt': 'Create step-by-step instructional headlines that promise to teach the reader how to accomplish something',
                    'description': 'Step-by-step instructional content'
                },
                {
                    'id': 'news_update',
                    'name': 'News & Updates',
                    'prompt': 'Create news-style headlines that highlight recent developments, changes, or important updates',
                    'description': 'Current news and recent updates'
                }
            ]
        
        return jsonify({"ok": True, "templates": templates})
    except Exception as e:
        logger.error(f"Error fetching templates: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Return fallback templates on error
        fallback_templates = [
            {
                'id': 'guide_overview',
                'name': 'Guide & Overview',
                'prompt': 'Create comprehensive guides and general overviews',
                'description': 'Comprehensive guides and general overviews'
            },
            {
                'id': 'how_to',
                'name': 'How To',
                'prompt': 'Create step-by-step instructional headlines',
                'description': 'Step-by-step instructional content'
            }
        ]
        
        logger.info("Returning fallback templates due to error")
        return jsonify({"ok": True, "templates": fallback_templates, "warning": "Using fallback templates due to connection issue"})

@app.route('/api/scrape-article', methods=['POST'])
def scrape_article():
    """Enhanced: Try GCS database first, then web scraping, then manual text"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "Request data is required"}), 400
        
        url = data.get('url', '').strip()
        text_content = data.get('text', '').strip()
        
        # Check if we have either URL or text
        if not url and not text_content:
            return jsonify({"ok": False, "error": "Either URL or text content is required"}), 400
        
        article_data = {}
        data_source = ""
        
        # PRIORITY 3: Manual text input (if provided)
        if text_content:
            logger.info("📝 Using manual text input")
            logger.info(f"📝 Text content length: {len(text_content)} characters")
            
            try:
                from langdetect import detect
                detected_lang = detect(text_content)
                logger.info(f"✅ Detected language: {detected_lang}")
            except Exception as lang_error:
                logger.warning(f"⚠️ Language detection failed: {str(lang_error)}, defaulting to English")
                detected_lang = 'en'
            
            # Extract title from first line
            lines = text_content.split('\n')
            title = lines[0][:100].strip() if lines else text_content[:100].strip()
            if not title:
                title = "Manual Input"
            
            logger.info(f"📝 Extracted title: {title[:50]}...")
            
            # Detect country from language using our improved function
            country_geo = detect_country_from_language(detected_lang)
            country_name = get_country_name_from_geo(country_geo) if country_geo else ''
            
            logger.info(f"📝 Detected country: {country_name} ({country_geo})")
            
            article_data = {
                'title': title,
                'content': text_content,
                'language': _normalize_lang_code_name(detected_lang)['name'],
                'language_code': detected_lang,
                'url': 'manual_input',
                'detected_country': country_name,
                'detected_country_geo': country_geo,
                'source': 'manual_text'
            }
            data_source = "manual text"
            logger.info(f"✅ Manual text processed successfully")
        
        # PRIORITY 1: Try GCS database first (if URL provided)
        elif url and gcs_service:
            logger.info(f"🗄️ Trying GCS database for: {url}")
            gcs_data = gcs_service.get_article_data_by_url(url)
            
            if gcs_data:
                # Convert GCS format to our format
                content = (gcs_data.get('1stp', '') + '\n\n' + gcs_data.get('Rest of Content', '')).strip()
                
                # Detect language from content
                try:
                    from langdetect import detect
                    detected_lang = detect(content[:500])  # Use first 500 chars for detection
                except:
                    detected_lang = gcs_data.get('language', 'en')
                
                # Get country from GCS data or detect from language
                country_geo = gcs_data.get('country', '') or detect_country_from_language(detected_lang)
                country_name = get_country_name_from_geo(country_geo) if country_geo else ''
                
                article_data = {
                    'url': url,
                    'title': gcs_data.get('Title', 'No title'),
                    'content': content,
                    'language': _normalize_lang_code_name(detected_lang)['name'],
                    'language_code': detected_lang,
                    'detected_country': country_name,
                    'detected_country_geo': country_geo,
                    'source': 'gcs_database'
                }
                data_source = "GCS database"
                logger.info(f"✅ GCS: Found article in database!")
        
        # PRIORITY 2: Try web scraping (if GCS didn't work and URL provided)
        if url and not article_data:
            logger.info(f"🌐 Trying web scraping for: {url}")
            try:
                article_data = article_scraper.scrape_article(url)
                article_data['source'] = 'web_scraping'
                data_source = "web scraping"
                
                # Ensure we have detected_country_geo if we have detected_country
                if article_data.get('detected_country') and not article_data.get('detected_country_geo'):
                    # Try to find GEO code from country name
                    country_name = article_data['detected_country']
                    # First try exact language detection if we have it
                    if article_data.get('language_code'):
                        detected_geo = detect_country_from_language(article_data['language_code'])
                        if detected_geo:
                            article_data['detected_country_geo'] = detected_geo
                            logger.info(f"✅ Mapped country '{country_name}' to GEO: {detected_geo}")
                
                logger.info(f"✅ Scraping: Success!")
            except Exception as scrape_error:
                logger.warning(f"⚠️ Scraping failed: {str(scrape_error)}")
                return jsonify({
                    "ok": False, 
                    "error": "Failed to scrape article. This might be due to network restrictions. Please try copying and pasting the article text directly instead.",
                    "suggestion": "Switch to 'Free Text' mode and paste the article content."
                }), 400
        
        logger.info(f"✅ Article processed via {data_source}")
        logger.info(f"   Title: {article_data.get('title', 'No title')[:80]}")
        logger.info(f"   Language: {article_data.get('language_code', 'unknown')}")
        logger.info(f"   Country: {article_data.get('detected_country', 'Not detected')} (GEO: {article_data.get('detected_country_geo', 'N/A')})")
        logger.info(f"   Content: {len(article_data.get('content', ''))} characters")
        
        return jsonify({"ok": True, "article": article_data})
        
    except Exception as e:
        logger.error(f"Error processing article: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/generate-headlines', methods=['POST'])
def generate_headlines():
    """Generate headlines using templates and article data"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No JSON data provided"}), 400
        
        # Validate required fields
        required_fields = ['template_ids', 'n_variants']
        for field in required_fields:
            if field not in data:
                return jsonify({"ok": False, "error": f"Missing required field: {field}"}), 400
        
        # Validate that we have article data
        if 'article_data' not in data and 'article_url' not in data:
            return jsonify({"ok": False, "error": "Either article_data or article_url is required"}), 400
        
        # Get article data - either from provided data or scrape from URL
        article_data = None
        if 'article_data' in data:
            # Use provided article data (from previous scrape/text analysis)
            article_data = data['article_data']
            logger.info("Using provided article data")
        elif 'article_url' in data and data['article_url'] != 'manual_input':
            # Scrape from URL if provided and not manual input
            logger.info(f"Scraping article from URL: {data['article_url']}")
            article_data = article_scraper.scrape_article(data['article_url'])
        else:
            return jsonify({"ok": False, "error": "No article data provided. Please analyze an article first."}), 400
        
        # Apply language override if provided
        if data.get('language_override'):
            article_data['language_code'] = data['language_override']
            # Get language name from our normalized mapping
            lang_info = _normalize_lang_code_name(data['language_override'])
            article_data['language'] = lang_info['name']
            logger.info(f"Language overridden to: {data['language_override']} ({article_data['language']})")
            
            # Update detected country based on new language
            new_country_geo = detect_country_from_language(data['language_override'])
            article_data['detected_country'] = get_country_name_from_geo(new_country_geo) if new_country_geo else ''
            article_data['detected_country_geo'] = new_country_geo
        
        # Get templates
        if not sheets_client:
            return jsonify({"ok": False, "error": "Google Sheets client not available. Cannot load templates."}), 500
        
        try:
            all_templates = sheets_client.get_templates_from_sheet(TEMPLATES_SPREADSHEET_URL, "Templates")
        except Exception as sheets_error:
            logger.warning(f"Google Sheets error in generate_headlines: {sheets_error}")
            # Use fallback templates
            all_templates = [
                {"id": "1", "name": "Question-Based", "description": "Creates curiosity through questions", "prompt": "Create a compelling question-based headline"},
                {"id": "2", "name": "Curiosity Gap", "description": "Creates knowledge gaps to drive clicks", "prompt": "Create a curiosity-driven headline"},
                {"id": "3", "name": "Time & Trends", "description": "Focuses on current trends and timing", "prompt": "Create a trend-focused headline"},
                {"id": "4", "name": "Benefit & Impact", "description": "Highlights benefits and outcomes", "prompt": "Create a benefit-focused headline"},
                {"id": "5", "name": "Guide & Overview", "description": "Comprehensive guide format", "prompt": "Create a guide-style headline"}
            ]
        selected_templates = [t for t in all_templates if t['id'] in data['template_ids']]
        
        if not selected_templates:
            return jsonify({"ok": False, "error": "No valid templates selected"}), 400
        
        # Generate headlines
        result = openai_client.generate_headlines(
            templates=selected_templates,
            article_data=article_data,
            n_variants=data['n_variants']
        )
        
        if not result.get('ok'):
            return jsonify(result), 500
        
        # Run compliance checks on headlines
        processed_headlines = []
        for headline_data in result['headlines']:
            # Create ad_asset format for compliance check
            ad_asset = {
                'headline': headline_data['headline'],
                'primary_text': '',
                'description': '',
                'cta': '',
                'language_code': headline_data['language_code']
            }
            
            # Run moderation check
            moderation_result = openai_client.check_moderation(ad_asset)
            
            # Run compliance check
            compliance_result = compliance_checker.check_compliance(
                ad_asset=ad_asset,
                platform="General",  # Generic platform for headlines
                geo="IL",  # Default geo
                language=headline_data['language_code']
            )
            
            processed_headlines.append({
                **headline_data,
                'moderation': moderation_result,
                'compliance': compliance_result
            })
        
        response = {
            "ok": True,
            "headlines": processed_headlines,
            "article_title": result.get('article_title', ''),
            "article_language": result.get('article_language', ''),
            "templates_used": result.get('templates_used', []),
            "total_headlines": len(processed_headlines)
        }
        
        logger.info(f"Successfully generated {len(processed_headlines)} headlines")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error generating headlines: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/test-url', methods=['POST'])
def test_url():
    """Test if a URL is accessible"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({"ok": False, "error": "URL is required"}), 400
        
        url = data['url']
        logger.info(f"Testing URL accessibility: {url}")
        
        # Simple connectivity test
        import requests
        response = requests.head(url, timeout=10, allow_redirects=True)
        
        return jsonify({
            "ok": True, 
            "status_code": response.status_code,
            "content_type": response.headers.get('content-type', 'unknown'),
            "accessible": response.status_code < 400
        })
        
    except Exception as e:
        logger.error(f"URL test failed: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

