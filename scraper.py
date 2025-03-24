import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

import tqdm
import time

# Base API URL
BASE_URL = "http://www.legislation.gov.uk"
UNAVAILABLE_TEXT = "This item of legislation isn’t available on this site as it isn’t currently available in a web-publishable format. This could be because the new legislation item hasn’t published yet."
COULDNT_FIND_TEXT = "The page you requested could not be found."
INVALID_TEXT = "Your request is not recognised."
DATA_DIR = "legislation_data"

# Legislation Types and Abbreviations
LEGISLATION_TYPES = {
    "Primary Legislation": ["ukpga", "ukla", "ukppa", "gbla", "apgb", "gbppa", "aep", "aosp", "asp", "aip", "apni", "mnia", "nia", "ukcm", "mwa", "anaw", "asc"],
    "Secondary Legislation": ["uksi", "ssi", "wsi", "nisr", "ukci", "nisi", "ukmo", "nisro"],
    "Draft Legislation": ["ukdsi", "sdsi", "nidsr", "nidsi", "wdsi"]
}

def fetchHTML(url):
    """
    Fetches the HTML content of the legislation type page.
    
    Args:
        legislation_type (str): The type of legislation (e.g., 'ukpga', 'uksi')
    
    Returns:
        str: HTML content of the page if successful, None otherwise
    """
    time.sleep(1)  # Sleep for 5 seconds between requests
    try:
        response = requests.get(url, timeout=5)
        if UNAVAILABLE_TEXT in response.text or response.status_code == 500 or response.status_code != 200 or COULDNT_FIND_TEXT in response.text:   
            raise ValueError(f"Error fetching {url}: unavailable")
        if INVALID_TEXT in response.text:
            raise ValueError(f"Error fetching {url}: invalid text")
        return response.text
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Error fetching {url}: something else")

def fetchAvailableYears(legislation_type):
    html = fetchHTML(f"{BASE_URL}/{legislation_type}")
    soup = BeautifulSoup(html, 'html.parser')
    timeline_div = soup.find('div', id='timelineData')
    hrefs = [a['href'] for a in timeline_div.find_all('a', href=True)]
    yearURLs = [f"{BASE_URL}{href}" for href in hrefs if '-' not in href]
    return yearURLs

def extract_table_hrefs(soup):
    """Extract all hrefs from the <td> elements in the table."""
    table_div = soup.find('div', id='content')
    hrefs = []
    if table_div:
        hrefs = [a['href'] for td in table_div.find_all('td') for a in td.find_all('a', href=True)]
    return hrefs

def extract_pagination_links(soup):
    """Extract all pagination URLs from the pagination nav."""
    nav_div = soup.find('div', class_='prevPagesNextNav')
    if not nav_div:
        return []

    links = []
    for a in nav_div.find_all('a', href=True):
        full_url = urljoin(BASE_URL, a['href'])
        if full_url not in links:
            links.append(full_url)
    return list(set(links))  # De-duplicate

def fetchAvailablePages(start_url):
    all_hrefs = set()

    # Fetch and parse the first page
    response = requests.get(start_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract hrefs from the first page
    all_hrefs.update(extract_table_hrefs(soup))

    # Get all pagination URLs
    page_urls = extract_pagination_links(soup)

    # Loop through the remaining pages and repeat
    for url in page_urls:
        page = requests.get(url)
        page_soup = BeautifulSoup(page.text, 'html.parser')
        all_hrefs.update(extract_table_hrefs(page_soup))

    urls = [f"{BASE_URL}{href}/data.html" for href in sorted(all_hrefs)]
    return urls

def main():
    print("Fetching all legislation data...")
    for legislation_category, types in LEGISLATION_TYPES.items():
        print(f"==========={legislation_category}===========")
        for legislation_type in types:
            print(f"Processing {legislation_type}...")
            yearURLs = fetchAvailableYears(legislation_type)
            errorURLs = []
            for yearURL in tqdm.tqdm(yearURLs):
                pageURLs = fetchAvailablePages(yearURL)
                year = yearURL.split('/')[-1]
                dir_path = os.path.join(DATA_DIR, f"{legislation_category}/{legislation_type}")
                os.makedirs(dir_path, exist_ok=True)
                for pageURL in pageURLs:
                    file_path = os.path.join(dir_path, f"{year}-{'-'.join(pageURL.split('/')[4:7])}.html")
                    if os.path.exists(file_path):
                        continue
                    try:
                        html = fetchHTML(pageURL)
                        with open(file_path, "w") as f:
                            f.write(html)
                    except ValueError:
                        errorURLs.append(pageURL)
            if errorURLs:
                error_dir_path = os.path.join(DATA_DIR, f"{legislation_category}/{legislation_type}")
                with open(os.path.join(error_dir_path, f"errorURL.txt"), "w") as f:
                    f.write("\n".join(errorURLs))

if __name__ == "__main__":
    main()
