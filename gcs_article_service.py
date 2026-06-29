"""
GCS Article Service - Fetch article data from Google Cloud Storage
Based on Stage 1 script with optimizations for Flask web app
"""

import os
import json
import re
import time
import logging
from typing import Optional, Dict, Any
from google.cloud import storage
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

class GCSArticleService:
    """Service to fetch article data from Google Cloud Storage"""
    
    def __init__(self, credentials_file: str = 'service_account.json', 
                 bucket_name: str = 'your-gcs-bucket', 
                 folder_name: str = 'articles2025'):
        """Initialize GCS service"""
        self.credentials_file = credentials_file
        self.bucket_name = bucket_name
        self.folder_name = folder_name
        self.cache = {}
        self.gcs_file_list_cache = None
        self.gcs_file_list_cache_time = 0
        self.cache_ttl = 300  # 5 minutes cache
        self.setup_gcs()
    
    def setup_gcs(self):
        """Setup Google Cloud Storage client"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            gcs_credentials_path = os.path.join(script_dir, self.credentials_file)
            
            if not os.path.exists(gcs_credentials_path):
                raise FileNotFoundError(f"GCS credentials not found: {gcs_credentials_path}")
            
            logger.info(f"Loading GCS credentials from: {gcs_credentials_path}")
            self.gcs_creds = service_account.Credentials.from_service_account_file(
                gcs_credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            
            self.storage_client = storage.Client(credentials=self.gcs_creds)
            self.bucket = self.storage_client.bucket(self.bucket_name)
            logger.info(f"✅ GCS connection established - Bucket: {self.bucket_name}")
            
        except Exception as e:
            logger.error(f"❌ Error setting up GCS: {str(e)}")
            raise
    
    def get_article_data_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get article data from GCS by URL pattern matching"""
        if not url or not url.startswith("http"):
            return None
        
        try:
            # Check cache first
            cache_key = f"gcs_{url}"
            if cache_key in self.cache:
                logger.debug(f"📋 GCS cache hit for: {url}")
                return self.cache[cache_key]
            
            # Apply domain substitutions
            lookup_url = self.apply_domain_substitutions(url)
            url_filename = self.url_to_filename(lookup_url)
            
            logger.info(f"🔍 GCS lookup for: {url}")
            logger.debug(f"   Pattern: {url_filename[:100]}...")
            
            # Get or refresh file list cache
            current_time = time.time()
            if (self.gcs_file_list_cache is None or 
                current_time - self.gcs_file_list_cache_time > self.cache_ttl):
                
                logger.info(f"🔄 Refreshing GCS file list from {self.folder_name}/...")
                blobs = list(self.bucket.list_blobs(prefix=f"{self.folder_name}/"))
                self.gcs_file_list_cache = blobs
                self.gcs_file_list_cache_time = current_time
                logger.info(f"📋 Cached {len(blobs)} files from GCS")
            else:
                blobs = self.gcs_file_list_cache
            
            # Find matching file (prefer highest version)
            matched_file = None
            highest_version = 0
            
            for blob in blobs:
                filename = blob.name.split('/')[-1]
                
                if url_filename in filename:
                    logger.debug(f"   Found potential match: {filename}")
                    
                    # Extract version number
                    version_match = re.search(r'_v(\d+)\.json$', filename)
                    if version_match:
                        version = int(version_match.group(1))
                        if version > highest_version:
                            highest_version = version
                            matched_file = blob
                    elif matched_file is None:
                        matched_file = blob
            
            if matched_file:
                logger.info(f"✅ GCS: Reading {matched_file.name}")
                
                # Download and parse
                json_content = matched_file.download_as_text()
                file_data = json.loads(json_content)
                
                # Cache the result
                self.cache[cache_key] = file_data
                
                logger.info(f"✅ GCS: Successfully retrieved data for {url}")
                return file_data
            
            logger.info(f"❌ GCS: No file found for {url}")
            # Cache negative result
            self.cache[cache_key] = None
            return None
            
        except Exception as e:
            logger.error(f"❌ GCS error for {url}: {str(e)}")
            return None
    
    def apply_domain_substitutions(self, url: str) -> str:
        """Apply domain substitutions for legacy URLs"""
        if not url:
            return url
        
        substitutions = {
            "legacy-site-1.example.com": "current-site-a.example.com",
            "legacy-site-2.example.com": "current-site-a.example.com",
            "legacy-site-3.example.com": "current-site-b.example.com",
            "legacy-site-4.example.com": "current-site-b.example.com",
            "legacy-site-5.example.com": "current-site-b.example.com"
        }
        
        for old, new in substitutions.items():
            url = url.replace(old, new)
        return url
    
    def url_to_filename(self, url: str) -> str:
        """Convert URL to filename pattern"""
        if not url:
            return ""
        
        sanitized = str(url).strip()
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', sanitized)
        sanitized = re.sub(r'\s+', '_', sanitized)
        sanitized = re.sub(r'_+', '_', sanitized)
        return sanitized.strip('_')

