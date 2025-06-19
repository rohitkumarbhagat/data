#!/usr/bin/env python3
"""Extract Data Commons IDs from place search results - Version 4.

Enhanced version with browser restart logic, resume capability, and smart filtering.
Uses Selenium browser automation to navigate Data Commons search and extract IDs from redirects.

How to Run:
===========

Basic Usage:
    cd tools/misc
    python3 datacommons_id_extractor_v4.py --input places.txt --output results.csv --verbose

Installation:
    pip install -r requirements.txt

Common Commands:
    # Process places with verbose logging
    python3 datacommons_id_extractor_v4.py -i places.txt -o places_datacommons_ids_v4.csv -v
    
    # Faster processing with reduced delay and restart interval
    python3 datacommons_id_extractor_v4.py -i places.txt -o results.csv --delay 1.0 --restart-interval 50
    
    # Run in non-headless mode (show browser)
    python3 datacommons_id_extractor_v4.py -i places.txt -o results.csv --no-headless
    
    # Retry failed places from previous run
    python3 datacommons_id_extractor_v4.py -i places.txt -o results.csv --retry-failed
    
    # Process without creating backups
    python3 datacommons_id_extractor_v4.py -i places.txt -o results.csv --no-backup-existing

Input Format:
    - Text file with one place name per line, or
    - CSV file with place names in the first column
    
Output Format:
    CSV with columns: place_name, datacommons_id, status
    - datacommons_id: Data Commons identifier extracted from URL redirect (e.g., geoId/05, country/USA)
    - status: "success" or "not_found"

Browser Management:
    - Automatic browser restarts every 25 requests (configurable)
    - Resume capability from existing output files
    - Progress tracking with ETA calculations
    - Built-in delays to avoid rate limiting
    - Headless mode by default (can be disabled for debugging)

Note: This version uses browser automation and may be slower than v5 API approach.
Requires ChromeDriver and Selenium dependencies.
"""

import argparse
import csv
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from typing import List, Tuple, Optional, Dict
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager


class DataCommonsExtractor:
    """Enhanced Data Commons ID extractor with session management and resume capability."""
    
    def __init__(self, config):
        self.restart_interval = config.restart_interval
        self.driver = None
        self.request_count = 0
        self.total_requests = 0
        self.browser_restarts = 0
        self.headless = config.headless
        self.timeout = config.timeout
        self.delay = config.delay
        
    def setup_driver(self) -> webdriver.Chrome:
        """Setup Chrome WebDriver with appropriate options."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
        
    def restart_browser_if_needed(self, force: bool = False):
        """Restart browser if request count exceeds interval or if forced."""
        if force or self.request_count >= self.restart_interval:
            logging.info(f"🔄 Restarting browser (requests: {self.request_count}, restarts: {self.browser_restarts})")
            
            if self.driver:
                try:
                    self.driver.quit()
                except Exception as e:
                    logging.debug(f"Error closing driver: {e}")
            
            self.driver = self.setup_driver()
            self.request_count = 0
            self.browser_restarts += 1
            time.sleep(2)  # Brief pause after restart
            
    def extract_datacommons_id(self, place_name: str) -> Optional[str]:
        """Extract Data Commons ID for a given place name."""
        try:
            # Ensure we have a valid driver
            if not self.driver:
                self.restart_browser_if_needed(force=True)
                
            # Navigate to search page
            escaped_place = quote(place_name)
            search_url = f"https://datacommons.org/explore?q={escaped_place}"
            logging.debug(f"Searching: {place_name} -> {search_url}")
            
            self.driver.get(search_url)
            self.request_count += 1
            self.total_requests += 1
            
            # Wait for redirect
            time.sleep(2)
            
            # Get final URL after redirect
            final_url = self.driver.current_url
            logging.debug(f"Final URL: {final_url}")
            
            # Extract Data Commons ID from URL
            if '/place/' in final_url:
                place_part = final_url.split('/place/')[1]
                if '?' in place_part:
                    dc_id = place_part.split('?')[0]
                else:
                    dc_id = place_part
                dc_id = dc_id.rstrip('/')
                
                if dc_id and '/' in dc_id:
                    logging.info(f"✅ {place_name} -> {dc_id}")
                    return dc_id
            
            logging.warning(f"❌ No redirect found for: {place_name}")
            return None
            
        except WebDriverException as e:
            logging.error(f"🚫 WebDriver error for {place_name}: {e}")
            # Try to restart browser on WebDriver errors
            try:
                self.restart_browser_if_needed(force=True)
            except Exception as restart_error:
                logging.error(f"Failed to restart browser: {restart_error}")
            return None
        except Exception as e:
            logging.error(f"🚫 Error extracting ID for {place_name}: {e}")
            return None
    
    def load_existing_results(self, output_file: str) -> Dict[str, Tuple[Optional[str], str]]:
        """Load existing results from CSV file."""
        existing_results = {}
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        place_name = row['place_name']
                        dc_id = row['datacommons_id'] if row['datacommons_id'] else None
                        status = row['status']
                        existing_results[place_name] = (dc_id, status)
                logging.info(f"📂 Loaded {len(existing_results)} existing results from {output_file}")
            except Exception as e:
                logging.error(f"Error reading existing results: {e}")
        return existing_results
    
    def filter_places_to_process(self, all_places: List[str], existing_results: Dict[str, Tuple[Optional[str], str]], 
                                config) -> List[str]:
        """Filter places based on configuration options."""
        places_to_process = []
        
        for place in all_places:
            if place in existing_results:
                _, status = existing_results[place]
                
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
    
    def save_intermediate_results(self, results: List[Tuple[str, Optional[str], str]], 
                                 existing_results: Dict[str, Tuple[Optional[str], str]], 
                                 output_file: str):
        """Save intermediate results, merging with existing ones."""
        try:
            # Combine existing and new results
            all_results = dict(existing_results)
            for place_name, dc_id, status in results:
                all_results[place_name] = (dc_id, status)
            
            # Write to file
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['place_name', 'datacommons_id', 'status'])
                for place_name, (dc_id, status) in all_results.items():
                    writer.writerow([place_name, dc_id or '', status])
            
            logging.debug(f"💾 Saved intermediate results ({len(all_results)} total)")
        except Exception as e:
            logging.error(f"Error saving intermediate results: {e}")
    
    def process_places(self, places: List[str], existing_results: Dict[str, Tuple[Optional[str], str]], 
                      output_file: str) -> List[Tuple[str, Optional[str], str]]:
        """Process list of places with periodic browser restarts and saves."""
        results = []
        start_time = time.time()
        
        try:
            # Initialize browser
            self.restart_browser_if_needed(force=True)
            
            for i, place in enumerate(places, 1):
                # Restart browser if needed
                self.restart_browser_if_needed()
                
                # Progress indicator
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                eta = (len(places) - i) / rate if rate > 0 else 0
                
                logging.info(f"🔄 {i}/{len(places)} ({i/len(places)*100:.1f}%) - "
                           f"Restarts: {self.browser_restarts} - "
                           f"ETA: {eta/60:.1f}m - {place}")
                
                # Extract ID
                dc_id = self.extract_datacommons_id(place)
                status = "success" if dc_id else "not_found"
                results.append((place, dc_id, status))
                
                # Save intermediate results every 10 places
                if i % 10 == 0:
                    self.save_intermediate_results(results, existing_results, output_file)
                
                # Delay between requests
                if i < len(places):
                    time.sleep(self.delay)
        
        finally:
            # Cleanup
            if self.driver:
                try:
                    self.driver.quit()
                except Exception as e:
                    logging.debug(f"Error closing driver: {e}")
        
        return results
    
    def get_processing_stats(self, results: List[Tuple[str, Optional[str], str]]) -> str:
        """Generate processing statistics."""
        successful = sum(1 for _, dc_id, _ in results if dc_id)
        total = len(results)
        success_rate = successful / total * 100 if total > 0 else 0
        
        return (f"📊 Completed: {successful}/{total} ({success_rate:.1f}% success) - "
               f"Browser restarts: {self.browser_restarts} - "
               f"Total requests: {self.total_requests}")


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
    parser = argparse.ArgumentParser(description='Extract Data Commons IDs - Enhanced v4')
    parser.add_argument('--input', '-i', required=True, help='Input file with place names')
    parser.add_argument('--output', '-o', required=True, help='Output CSV file')
    parser.add_argument('--delay', '-d', type=float, default=1.5, 
                       help='Delay between requests in seconds (default: 1.5)')
    parser.add_argument('--timeout', '-t', type=int, default=15,
                       help='Timeout for page loading in seconds (default: 15)')
    parser.add_argument('--restart-interval', type=int, default=25,
                       help='Restart browser every N requests (default: 25)')
    parser.add_argument('--resume', action='store_true', default=True,
                       help='Resume from existing output file (default: True)')
    parser.add_argument('--skip-successful', action='store_true', default=True,
                       help='Skip places that already have successful results (default: True)')
    parser.add_argument('--retry-failed', action='store_true',
                       help='Retry places that failed in previous runs')
    parser.add_argument('--backup-existing', action='store_true', default=True,
                       help='Backup existing output file (default: True)')
    parser.add_argument('--headless', action='store_true', default=True,
                       help='Run browser in headless mode (default: True)')
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
    
    logging.info(f"🚀 Starting Data Commons ID extraction v4")
    logging.info(f"📍 Input: {args.input} ({len(all_places)} places)")
    logging.info(f"📁 Output: {args.output}")
    logging.info(f"⚙️  Config: restart_interval={args.restart_interval}, delay={args.delay}s, resume={args.resume}, skip_successful={args.skip_successful}")
    
    # Always load existing results to enable smart processing
    extractor = DataCommonsExtractor(args)
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