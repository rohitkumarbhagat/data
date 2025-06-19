#!/usr/bin/env python3
"""Extract Data Commons IDs using autocomplete API - Version 5.

Fast, reliable approach using direct API calls instead of browser automation.

How to Run:
===========

Basic Usage:
    cd tools/misc
    python3 datacommons_id_extractor_v5.py --input places.txt --output results.csv --verbose

Installation:
    pip install -r requirements.txt

Common Commands:
    # Process places with verbose logging
    python3 datacommons_id_extractor_v5.py -i places.txt -o places_datacommons_ids_v5.csv -v
    
    # Faster processing with reduced delay
    python3 datacommons_id_extractor_v5.py -i places.txt -o results.csv --delay 0.2
    
    # Retry failed places from previous run
    python3 datacommons_id_extractor_v5.py -i places.txt -o results.csv --retry-failed
    
    # Process without creating backups
    python3 datacommons_id_extractor_v5.py -i places.txt -o results.csv --no-backup-existing

Input Format:
    - Text file with one place name per line, or
    - CSV file with place names in the first column
    
Output Format:
    CSV with columns: place_name, dcid, matched_query, name, status
    - dcid: Data Commons identifier (e.g., geoId/05, country/USA)
    - matched_query: Search term that matched
    - name: Display name from Data Commons
    - status: "success" or "not_found"

Special Features:
    - USA State Processing: Automatically extracts state names from patterns like 
      "arkansas united states of america" -> searches for "arkansas"
    - Resume Capability: Automatically resumes from existing output file
    - Progress Tracking: Shows ETA and completion percentage
    - API Rate Limiting: Built-in delays to respect API limits
"""

import argparse
import csv
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from typing import List, Tuple, Optional, Dict
from urllib.parse import quote
import requests
import re


class DataCommonsAPIExtractor:
    """Data Commons ID extractor using autocomplete API."""
    
    def __init__(self, config):
        self.delay = config.delay
        self.timeout = config.timeout
        self.total_requests = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
    def preprocess_place_name(self, place_name: str) -> str:
        """Preprocess place name to handle USA state/territory patterns.
        
        If place name contains 'united states of america' and has other words,
        extract the state/territory name by removing the country suffix.
        """
        # Pattern: {state_name} united states of america
        usa_pattern = r'^(.+?)\s+united states of america$'
        match = re.match(usa_pattern, place_name.lower())
        
        if match:
            state_name = match.group(1).strip()
            if state_name:  # Ensure we have a non-empty state name
                logging.debug(f"Preprocessing USA place: '{place_name}' -> '{state_name}'")
                return state_name
        
        return place_name
        
    def extract_datacommons_info(self, place_name: str) -> Optional[Tuple[str, str, str]]:
        """Extract Data Commons info for a given place name.
        
        Returns:
            Tuple of (dcid, matched_query, name) or None if not found
        """
        # Try with preprocessed name first
        preprocessed_name = self.preprocess_place_name(place_name)
        
        # Try preprocessed name if different from original
        if preprocessed_name != place_name:
            result = self._search_api(preprocessed_name, place_name)
            if result:
                return result
            
            # Log that we're trying fallback
            logging.debug(f"Preprocessed search failed for '{place_name}', trying original name")
        
        # Fallback to original name
        return self._search_api(place_name, place_name)
    
    def _search_api(self, search_name: str, original_name: str) -> Optional[Tuple[str, str, str]]:
        """Make API request for given search name.
        
        Args:
            search_name: Name to search for in API
            original_name: Original place name for logging
        """
        try:
            # Make API request
            api_url = f"https://datacommons.org/api/autocomplete?query={quote(search_name)}"
            logging.debug(f"API request: {original_name} (searching: {search_name}) -> {api_url}")
            
            response = self.session.get(api_url, timeout=self.timeout)
            response.raise_for_status()
            self.total_requests += 1
            
            # Parse JSON response
            data = response.json()
            
            if 'predictions' in data and data['predictions']:
                # Get first prediction
                first_prediction = data['predictions'][0]
                
                dcid = first_prediction.get('dcid', '')
                matched_query = first_prediction.get('matched_query', '')
                name = first_prediction.get('name', '')
                
                if dcid:
                    if search_name != original_name:
                        logging.info(f"✅ {original_name} (searched: {search_name}) -> {dcid} ({name})")
                    else:
                        logging.info(f"✅ {original_name} -> {dcid} ({name})")
                    return (dcid, matched_query, name)
            
            logging.warning(f"❌ No predictions found for: {original_name} (searched: {search_name})")
            return None
            
        except requests.exceptions.RequestException as e:
            logging.error(f"🚫 API error for {original_name}: {e}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"🚫 JSON decode error for {original_name}: {e}")
            return None
        except Exception as e:
            logging.error(f"🚫 Error extracting info for {original_name}: {e}")
            return None
    
    def load_existing_results(self, output_file: str) -> Dict[str, Tuple[Optional[str], Optional[str], Optional[str], str]]:
        """Load existing results from CSV file.
        
        Returns:
            Dict mapping place_name to (dcid, matched_query, name, status)
        """
        existing_results = {}
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        place_name = row['place_name']
                        dcid = row['dcid'] if row['dcid'] else None
                        matched_query = row['matched_query'] if row['matched_query'] else None
                        name = row['name'] if row['name'] else None
                        status = row['status']
                        existing_results[place_name] = (dcid, matched_query, name, status)
                logging.info(f"📂 Loaded {len(existing_results)} existing results from {output_file}")
            except Exception as e:
                logging.error(f"Error reading existing results: {e}")
        return existing_results
    
    def filter_places_to_process(self, all_places: List[str], 
                                existing_results: Dict[str, Tuple[Optional[str], Optional[str], Optional[str], str]], 
                                config) -> List[str]:
        """Filter places based on configuration options."""
        places_to_process = []
        
        for place in all_places:
            if place in existing_results:
                _, _, _, status = existing_results[place]
                
                if config.skip_successful and status == "success":
                    logging.debug(f"⏭️  Skipping successful: {place}")
                    continue
                elif not config.retry_failed and status == "not_found":
                    logging.debug(f"⏭️  Skipping failed: {place}")
                    continue
            
            places_to_process.append(place)
        
        skipped = len(all_places) - len(places_to_process)
        logging.info(f"📋 Processing {len(places_to_process)} places (skipping {skipped})")
        return places_to_process
    
    def backup_existing_file(self, output_file: str):
        """Create backup of existing output file."""
        if os.path.exists(output_file):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{output_file}.backup_{timestamp}"
            shutil.copy2(output_file, backup_file)
            logging.info(f"💾 Backup created: {backup_file}")
    
    def save_intermediate_results(self, results: List[Tuple[str, Optional[str], Optional[str], Optional[str], str]], 
                                 existing_results: Dict[str, Tuple[Optional[str], Optional[str], Optional[str], str]], 
                                 output_file: str):
        """Save intermediate results, merging with existing ones."""
        try:
            # Combine existing and new results
            all_results = dict(existing_results)
            for place_name, dcid, matched_query, name, status in results:
                all_results[place_name] = (dcid, matched_query, name, status)
            
            # Write to file
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['place_name', 'dcid', 'matched_query', 'name', 'status'])
                for place_name, (dcid, matched_query, name, status) in all_results.items():
                    writer.writerow([
                        place_name, 
                        dcid or '', 
                        matched_query or '', 
                        name or '', 
                        status
                    ])
            
            logging.debug(f"💾 Saved intermediate results ({len(all_results)} total)")
        except Exception as e:
            logging.error(f"Error saving intermediate results: {e}")
    
    def process_places(self, places: List[str], 
                      existing_results: Dict[str, Tuple[Optional[str], Optional[str], Optional[str], str]], 
                      output_file: str) -> List[Tuple[str, Optional[str], Optional[str], Optional[str], str]]:
        """Process list of places with periodic saves."""
        results = []
        start_time = time.time()
        
        for i, place in enumerate(places, 1):
            # Progress indicator
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(places) - i) / rate if rate > 0 else 0
            
            logging.info(f"🔄 {i}/{len(places)} ({i/len(places)*100:.1f}%) - "
                       f"ETA: {eta/60:.1f}m - {place}")
            
            # Extract info
            info = self.extract_datacommons_info(place)
            if info:
                dcid, matched_query, name = info
                status = "success"
            else:
                dcid, matched_query, name = None, None, None
                status = "not_found"
            
            results.append((place, dcid, matched_query, name, status))
            
            # Save intermediate results every 10 places
            if i % 10 == 0:
                self.save_intermediate_results(results, existing_results, output_file)
            
            # Delay between requests
            if i < len(places):
                time.sleep(self.delay)
        
        return results
    
    def get_processing_stats(self, results: List[Tuple[str, Optional[str], Optional[str], Optional[str], str]]) -> str:
        """Generate processing statistics."""
        successful = sum(1 for _, dcid, _, _, _ in results if dcid)
        total = len(results)
        success_rate = successful / total * 100 if total > 0 else 0
        
        return (f"📊 Completed: {successful}/{total} ({success_rate:.1f}% success) - "
               f"Total API requests: {self.total_requests}")


def read_place_names(input_file: str) -> List[str]:
    """Read place names from input file."""
    places = []
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            if input_file.endswith('.csv'):
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        places.append(row[0].strip())
            else:
                places = [line.strip() for line in f if line.strip()]
    except Exception as e:
        logging.error(f"Error reading input file: {e}")
        sys.exit(1)
    return places


def main():
    parser = argparse.ArgumentParser(description='Extract Data Commons IDs using API - v5')
    parser.add_argument('--input', '-i', required=True, help='Input file with place names')
    parser.add_argument('--output', '-o', required=True, help='Output CSV file')
    parser.add_argument('--delay', '-d', type=float, default=0.5, 
                       help='Delay between requests in seconds (default: 0.5)')
    parser.add_argument('--timeout', '-t', type=int, default=10,
                       help='Timeout for API requests in seconds (default: 10)')
    parser.add_argument('--resume', action='store_true', default=True,
                       help='Resume from existing output file (default: True)')
    parser.add_argument('--skip-successful', action='store_true', default=True,
                       help='Skip places that already have successful results (default: True)')
    parser.add_argument('--retry-failed', action='store_true',
                       help='Retry places that failed in previous runs')
    parser.add_argument('--backup-existing', action='store_true', default=True,
                       help='Backup existing output file (default: True)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level, 
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{args.output}.log")
        ]
    )
    
    # Read input places
    all_places = read_place_names(args.input)
    if not all_places:
        logging.error("No places found in input file")
        sys.exit(1)
    
    logging.info(f"🚀 Starting Data Commons ID extraction v5 (API-based)")
    logging.info(f"📍 Input: {args.input} ({len(all_places)} places)")
    logging.info(f"📁 Output: {args.output}")
    logging.info(f"⚙️  Config: delay={args.delay}s, timeout={args.timeout}s, resume={args.resume}, skip_successful={args.skip_successful}")
    
    # Initialize extractor and load existing results
    extractor = DataCommonsAPIExtractor(args)
    existing_results = extractor.load_existing_results(args.output)
    
    # Create backup if we have existing results and backup is enabled
    if args.backup_existing and existing_results:
        extractor.backup_existing_file(args.output)
    
    # Filter places to process
    places_to_process = extractor.filter_places_to_process(all_places, existing_results, args)
    
    if not places_to_process:
        logging.info("🎉 All places already processed!")
        return
    
    # Process places
    logging.info(f"🔄 Processing {len(places_to_process)} places...")
    new_results = extractor.process_places(places_to_process, existing_results, args.output)
    
    # Final save
    extractor.save_intermediate_results(new_results, existing_results, args.output)
    
    # Statistics
    stats = extractor.get_processing_stats(new_results)
    logging.info(stats)
    print(f"\n{stats}")
    print(f"📁 Results written to: {args.output}")
    print(f"📄 Log file: {args.output}.log")


if __name__ == '__main__':
    main()