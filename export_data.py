#!/usr/bin/env python3
"""
Export Google Sheets data to offline JSON files
"""

import json
from app import sheets_client, TEMPLATES_SPREADSHEET_URL, LANGUAGES_SPREADSHEET_URL

def export_templates():
    """Export templates to JSON file"""
    try:
        print("Exporting templates...")
        templates = sheets_client.get_templates_from_sheet(TEMPLATES_SPREADSHEET_URL, "Templates")
        
        with open('offline_templates.json', 'w', encoding='utf-8') as f:
            json.dump(templates, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(templates)} templates to offline_templates.json")
        return templates
    except Exception as e:
        print(f"Error exporting templates: {e}")
        return []

def export_languages():
    """Export languages data to JSON file"""
    try:
        print("Exporting languages...")
        languages_raw = sheets_client.get_worksheet_data(LANGUAGES_SPREADSHEET_URL, gid="2044055963")
        
        with open('offline_languages.json', 'w', encoding='utf-8') as f:
            json.dump(languages_raw, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(languages_raw)} language rows to offline_languages.json")
        return languages_raw
    except Exception as e:
        print(f"Error exporting languages: {e}")
        return []

if __name__ == "__main__":
    print("Starting data export...")
    templates = export_templates()
    languages = export_languages()
    print("Export completed!")
