import gspread
from google.oauth2.service_account import Credentials
import json
import os
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class GoogleSheetsClient:
    def __init__(self, service_account_path: str = "service_account.json"):
        """Initialize Google Sheets client with service account credentials"""
        try:
            # Define the scope for Google Sheets API
            scope = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Load credentials from service account file
            credentials = Credentials.from_service_account_file(
                service_account_path, 
                scopes=scope
            )
            
            # Initialize the gspread client
            self.client = gspread.authorize(credentials)
            logger.info("Successfully connected to Google Sheets API")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}")
            raise
    
    def get_spreadsheet_by_url(self, url: str):
        """Get spreadsheet by URL"""
        try:
            return self.client.open_by_url(url)
        except Exception as e:
            logger.error(f"Failed to open spreadsheet: {e}")
            raise
    
    def get_worksheet_data(self, spreadsheet_url: str, worksheet_name: str = None, gid: str = None) -> List[List[str]]:
        """Get all data from a specific worksheet"""
        try:
            spreadsheet = self.get_spreadsheet_by_url(spreadsheet_url)
            
            if gid:
                # Find worksheet by gid
                worksheet = None
                for ws in spreadsheet.worksheets():
                    if str(ws.id) == str(gid):
                        worksheet = ws
                        break
                if not worksheet:
                    raise ValueError(f"Worksheet with gid {gid} not found")
            elif worksheet_name:
                worksheet = spreadsheet.worksheet(worksheet_name)
            else:
                worksheet = spreadsheet.sheet1  # Default to first sheet
            
            return worksheet.get_all_values()
            
        except Exception as e:
            logger.error(f"Failed to get worksheet data: {e}")
            raise
    
    def get_worksheet_records(self, spreadsheet_url: str, worksheet_name: str = None, gid: str = None) -> List[Dict]:
        """Get worksheet data as list of dictionaries (using first row as headers)"""
        try:
            spreadsheet = self.get_spreadsheet_by_url(spreadsheet_url)
            
            if gid:
                worksheet = None
                for ws in spreadsheet.worksheets():
                    if str(ws.id) == str(gid):
                        worksheet = ws
                        break
                if not worksheet:
                    raise ValueError(f"Worksheet with gid {gid} not found")
            elif worksheet_name:
                worksheet = spreadsheet.worksheet(worksheet_name)
            else:
                worksheet = spreadsheet.sheet1
            
            return worksheet.get_all_records()
            
        except Exception as e:
            logger.error(f"Failed to get worksheet records: {e}")
            raise
    
    def update_cell(self, spreadsheet_url: str, worksheet_name: str, cell: str, value: str):
        """Update a specific cell"""
        try:
            spreadsheet = self.get_spreadsheet_by_url(spreadsheet_url)
            worksheet = spreadsheet.worksheet(worksheet_name)
            worksheet.update(cell, value)
            logger.info(f"Updated cell {cell} with value: {value}")
            
        except Exception as e:
            logger.error(f"Failed to update cell: {e}")
            raise
    
    def append_row(self, spreadsheet_url: str, worksheet_name: str, values: List[str]):
        """Append a new row to the worksheet"""
        try:
            spreadsheet = self.get_spreadsheet_by_url(spreadsheet_url)
            worksheet = spreadsheet.worksheet(worksheet_name)
            worksheet.append_row(values)
            logger.info(f"Appended row with {len(values)} values")
            
        except Exception as e:
            logger.error(f"Failed to append row: {e}")
            raise

    def get_templates_from_sheet(self, spreadsheet_url: str, worksheet_name: str = "Templates") -> List[Dict[str, str]]:
        """Get templates from the Templates worksheet"""
        try:
            logger.info(f"Fetching templates from worksheet: {worksheet_name}")
            data = self.get_worksheet_records(spreadsheet_url, worksheet_name=worksheet_name)
            
            logger.info(f"Raw data from sheet: {len(data)} rows")
            for i, row in enumerate(data[:3]):  # Log first 3 rows for debugging
                logger.info(f"Row {i}: {row}")
            
            # Process the data to extract templates
            templates = []
            for i, row in enumerate(data):
                if not row:
                    logger.debug(f"Skipping empty row {i}")
                    continue
                
                style = row.get('Style', '').strip() if row.get('Style') else ''
                prompt = row.get('Prompt', '').strip() if row.get('Prompt') else ''
                description = row.get('Description', '').strip() if row.get('Description') else ''
                
                logger.debug(f"Row {i}: Style='{style}', Prompt='{prompt[:50]}...', Description='{description[:50]}...'")
                
                # Only require Style and Prompt, Description is optional
                if style and prompt:
                    template = {
                        'id': style,
                        'name': style,
                        'prompt': prompt,
                        'description': description if description else 'No description provided'
                    }
                    templates.append(template)
                    logger.info(f"Added template: {template['name']}")
                else:
                    logger.warning(f"Skipping row {i}: missing Style ('{style}') or Prompt ('{prompt[:20]}...')")
            
            logger.info(f"Successfully processed {len(templates)} templates")
            return templates
            
        except Exception as e:
            logger.error(f"Failed to get templates from sheet: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
