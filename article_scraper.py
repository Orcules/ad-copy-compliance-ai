import requests
from bs4 import BeautifulSoup
import re
from typing import Dict, Optional
import logging
from urllib.parse import urlparse
import langdetect
from langdetect import detect

logger = logging.getLogger(__name__)

class ArticleScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def scrape_article(self, url: str) -> Dict[str, str]:
        """Scrape article content and detect language"""
        try:
            logger.info(f"Starting to scrape URL: {url}")
            
            # Validate URL
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValueError("Invalid URL provided - missing scheme or domain")
            
            logger.info(f"URL validation passed: {parsed_url.netloc}")
            
            # Fetch the page with better error handling
            try:
                response = self.session.get(url, timeout=8, allow_redirects=True)
                response.raise_for_status()
                logger.info(f"Successfully fetched page: {response.status_code}, Content-Type: {response.headers.get('content-type', 'unknown')}")
            except requests.exceptions.Timeout:
                raise ValueError("Request timeout - the website took too long to respond")
            except requests.exceptions.ConnectionError:
                raise ValueError("Connection error - could not connect to the website")
            except requests.exceptions.HTTPError as e:
                raise ValueError(f"HTTP error {response.status_code} - {str(e)}")
            except requests.exceptions.RequestException as e:
                raise ValueError(f"Request failed: {str(e)}")
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type and 'text/plain' not in content_type:
                logger.warning(f"Unexpected content type: {content_type}")
            
            # Parse HTML
            try:
                soup = BeautifulSoup(response.content, 'html.parser')
                logger.info("HTML parsing successful")
            except Exception as e:
                raise ValueError(f"Failed to parse HTML content: {str(e)}")
            
            # Extract title
            title = self._extract_title(soup)
            logger.info(f"Extracted title: {title[:100]}...")
            
            # Extract content
            content = self._extract_content(soup)
            logger.info(f"Extracted content: {len(content)} characters")
            
            if len(content) < 50:
                logger.warning("Very short content extracted, might indicate scraping issues")
                # Try alternative extraction
                content = soup.get_text(separator=' ', strip=True)
                logger.info(f"Alternative extraction: {len(content)} characters")
            
            # Detect language
            language = self._detect_language(title + " " + content)
            logger.info(f"Detected language: {language}")
            
            # Try to detect country from URL
            country = self._detect_country_from_url(url)
            
            # Fallback: detect country from language if URL detection failed
            if not country:
                country = self._detect_country_from_language(language)
            
            if country:
                logger.info(f"Detected country: {country}")
            
            # Get GEO code from country name
            country_geo = ''
            if country:
                # Map country name to GEO code
                country_to_geo = {
                    'Israel': 'IL', 'United States': 'US', 'Sweden': 'SE', 'Germany': 'DE',
                    'France': 'FR', 'Spain': 'ES', 'Italy': 'IT', 'Russia': 'RU',
                    'Saudi Arabia': 'SA', 'Brazil': 'BR', 'Japan': 'JP', 'South Korea': 'KR',
                    'China': 'CN', 'Denmark': 'DK', 'Norway': 'NO', 'Finland': 'FI',
                    'Poland': 'PL', 'Netherlands': 'NL', 'Czech Republic': 'CZ',
                    'Hungary': 'HU', 'Romania': 'RO', 'Bulgaria': 'BG', 'Greece': 'GR',
                    'Turkey': 'TR', 'Ukraine': 'UA', 'Croatia': 'HR', 'Serbia': 'RS',
                    'Austria': 'AT', 'Belgium': 'BE', 'Switzerland': 'CH', 'Portugal': 'PT',
                    'United Kingdom': 'UK', 'Canada': 'CA', 'Australia': 'AU',
                    'India': 'IN', 'Mexico': 'MX', 'Argentina': 'AR', 'Chile': 'CL',
                    'Colombia': 'CO', 'Peru': 'PE', 'Thailand': 'TH', 'Vietnam': 'VN',
                    'Indonesia': 'ID', 'Malaysia': 'MY', 'Bangladesh': 'BD', 'Pakistan': 'PK',
                    'Iran': 'IR', 'Taiwan': 'TW', 'Estonia': 'EE', 'Latvia': 'LV',
                    'Lithuania': 'LT', 'Slovenia': 'SI', 'Slovakia': 'SK', 'Ireland': 'IE'
                }
                country_geo = country_to_geo.get(country, '')
                if country_geo:
                    logger.info(f"Mapped country '{country}' to GEO code: {country_geo}")
            
            result = {
                'url': url,
                'title': title,
                'content': content,
                'language': language,
                'language_code': self._get_language_code(language),
                'detected_country': country,
                'detected_country_geo': country_geo
            }
            
            logger.info("Article scraping completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Failed to scrape article from {url}: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            raise
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract article title from various possible locations"""
        # Try different title selectors
        title_selectors = [
            'h1',
            'title',
            '[property="og:title"]',
            '[name="twitter:title"]',
            '.article-title',
            '.post-title',
            '.entry-title'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get('content') if element.get('content') else element.get_text()
                if title and len(title.strip()) > 5:
                    return title.strip()
        
        return "No title found"
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main article content"""
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement']):
            element.decompose()
        
        # Try different content selectors
        content_selectors = [
            'article',
            '.article-content',
            '.post-content',
            '.entry-content',
            '.content',
            'main',
            '.main-content'
        ]
        
        content = ""
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                content = element.get_text(separator=' ', strip=True)
                if len(content) > 100:  # Minimum content length
                    break
        
        # Fallback: get all paragraph text
        if len(content) < 100:
            paragraphs = soup.find_all('p')
            content = ' '.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
        
        # Clean up content
        content = re.sub(r'\s+', ' ', content)  # Multiple spaces to single space
        content = re.sub(r'\n+', '\n', content)  # Multiple newlines to single newline
        
        return content.strip()
    
    def _detect_language(self, text: str) -> str:
        """Detect language of the text"""
        try:
            if not text or len(text.strip()) < 10:
                return "unknown"
            
            # Use langdetect library
            detected = detect(text)
            return detected
            
        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return "unknown"
    
    def _get_language_code(self, language: str) -> str:
        """Convert language detection result to our supported language codes"""
        # Support all major languages that langdetect can identify
        return language if language else 'en'  # Return detected language or default to English
    
    def get_language_name(self, language_code: str) -> str:
        """Get full language name from code"""
        language_names = {
            'he': 'Hebrew',
            'en': 'English',
            'ar': 'Arabic',
            'ru': 'Russian',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese'
        }
        
        return language_names.get(language_code, 'English')
    
    def _detect_country_from_language(self, language_code: str) -> str:
        """Detect likely country based on language code"""
        # Map languages to their primary country
        language_to_country = {
            'he': 'Israel',
            'ar': 'Saudi Arabia',
            'pt': 'Brazil',
            'ko': 'South Korea',
            'ja': 'Japan',
            'zh-cn': 'China',
            'zh-tw': 'Taiwan',
            'th': 'Thailand',
            'vi': 'Vietnam',
            'id': 'Indonesia',
            'tr': 'Turkey',
            'pl': 'Poland',
            'nl': 'Netherlands',
            'sv': 'Sweden',
            'no': 'Norway',
            'da': 'Denmark',
            'fi': 'Finland',
            'cs': 'Czech Republic',
            'hu': 'Hungary',
            'ro': 'Romania',
            'el': 'Greece'
        }
        
        return language_to_country.get(language_code, '')
    
    def _detect_country_from_url(self, url: str) -> str:
        """Try to detect country from URL domain or path"""
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            path = parsed_url.path.lower()
            
            # Common country-specific domains
            country_domains = {
                '.co.uk': 'United Kingdom',
                '.co.il': 'Israel',
                '.de': 'Germany',
                '.fr': 'France',
                '.es': 'Spain',
                '.it': 'Italy',
                '.ru': 'Russia',
                '.ca': 'Canada',
                '.au': 'Australia',
                '.jp': 'Japan',
                '.kr': 'South Korea',
                '.cn': 'China',
                '.in': 'India',
                '.br': 'Brazil',
                '.mx': 'Mexico',
                '.ar': 'Argentina',
                '.ch': 'Switzerland',
                '.at': 'Austria',
                '.be': 'Belgium',
                '.nl': 'Netherlands',
                '.se': 'Sweden',
                '.no': 'Norway',
                '.dk': 'Denmark',
                '.fi': 'Finland',
                '.pl': 'Poland',
                '.cz': 'Czech Republic',
                '.hu': 'Hungary',
                '.ro': 'Romania',
                '.bg': 'Bulgaria',
                '.hr': 'Croatia',
                '.si': 'Slovenia',
                '.sk': 'Slovakia',
                '.ee': 'Estonia',
                '.lv': 'Latvia',
                '.lt': 'Lithuania',
                '.gr': 'Greece',
                '.tr': 'Turkey',
                '.pt': 'Portugal',
                '.ie': 'Ireland'
            }
            
            # Check domain endings
            for domain_ending, country in country_domains.items():
                if domain.endswith(domain_ending):
                    return country
            
            # Check for country codes in subdomain or path
            country_codes = {
                'uk': 'United Kingdom',
                'il': 'Israel', 
                'de': 'Germany',
                'fr': 'France',
                'es': 'Spain',
                'it': 'Italy',
                'ru': 'Russia',
                'ca': 'Canada',
                'au': 'Australia',
                'jp': 'Japan',
                'kr': 'South Korea',
                'ko': 'South Korea',
                'cn': 'China',
                'in': 'India',
                'br': 'Brazil',
                'mx': 'Mexico',
                'us': 'United States',
                'ar': 'Argentina',
                'cl': 'Chile',
                'co': 'Colombia',
                'pe': 'Peru',
                'nl': 'Netherlands',
                'be': 'Belgium',
                'ch': 'Switzerland',
                'at': 'Austria',
                'se': 'Sweden',
                'no': 'Norway',
                'dk': 'Denmark',
                'fi': 'Finland',
                'pl': 'Poland',
                'pt': 'Portugal'
            }
            
            # Check subdomains (e.g., de.example.com)
            domain_parts = domain.split('.')
            if len(domain_parts) > 2:
                subdomain = domain_parts[0]
                if subdomain in country_codes:
                    return country_codes[subdomain]
            
            # Check path (e.g., example.com/de/article)
            path_parts = [p for p in path.split('/') if p]
            if path_parts:
                first_path = path_parts[0]
                if first_path in country_codes:
                    return country_codes[first_path]
            
            # NEW: Check for country code at the END of the path (e.g., example.com/article-title-it)
            # This handles URLs like magicmoments.com/current-trends-in-w-49318-it
            if path:
                # Get last part of path and check if it ends with a country code
                path_segments = [p for p in path.split('/') if p]
                if path_segments:
                    last_segment = path_segments[-1]
                    # Check if last segment ends with dash followed by 2-letter country code
                    import re
                    match = re.search(r'-([a-z]{2})$', last_segment)
                    if match:
                        potential_code = match.group(1)
                        if potential_code in country_codes:
                            logger.info(f"Detected country code '{potential_code}' from URL ending")
                            return country_codes[potential_code]
            
            # Default: couldn't detect
            return ''
            
        except Exception as e:
            logger.warning(f"Country detection from URL failed: {e}")
            return ''
