import os
import csv
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin

def get_sitemap_url(base_url):
    """
    Attempts to find the sitemap URL by checking robots.txt or common paths.
    """
    parsed_url = urlparse(base_url)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    # Check robots.txt
    robots_url = urljoin(domain, '/robots.txt')
    try:
        response = requests.get(robots_url, timeout=5)
        if response.status_code == 200:
            for line in response.text.splitlines():
                if line.lower().startswith('sitemap:'):
                    return line.split(':', 1)[1].strip()
    except requests.RequestException:
        pass
    
    # Fallback to standard sitemap.xml
    return urljoin(domain, '/sitemap.xml')

def extract_links_from_sitemap(sitemap_url):
    """
    Fetches and parses the sitemap XML to extract URLs.
    Handles standard sitemap and sitemap index files.
    """
    links = []
    try:
        print(f"Fetching sitemap: {sitemap_url}")
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch sitemap: {response.status_code}")
            return []

        root = ET.fromstring(response.content)
        
        # Check if it's a sitemap index
        # XML namespaces can be tricky, usually http://www.sitemaps.org/schemas/sitemap/0.9
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # Look for <sitemap> entries (sitemap index)
        if root.tag.endswith('sitemapindex'):
             for sitemap in root.findall('ns:sitemap', namespace):
                 loc = sitemap.find('ns:loc', namespace)
                 if loc is not None:
                     links.extend(extract_links_from_sitemap(loc.text))
        else:
             # Standard sitemap with <url> entries
             for url in root.findall('ns:url', namespace):
                 loc = url.find('ns:loc', namespace)
                 if loc is not None:
                     links.append(loc.text)
                     
    except requests.RequestException as e:
        print(f"Error fetching sitemap: {e}")
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        
    return links

def main():
    url = input("Enter the website URL: ")
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    parsed_url = urlparse(url)
    domain_name = parsed_url.netloc
    
    if not domain_name:
        print("Invalid URL.")
        return

    # Create folder for the website
    if not os.path.exists(domain_name):
        os.makedirs(domain_name)
        print(f"Created directory: {domain_name}")
    else:
        print(f"Directory already exists: {domain_name}")

    # Find sitemap
    sitemap_url = get_sitemap_url(url)
    print(f"Looking for sitemap at: {sitemap_url}")
    
    # Extract links
    links = extract_links_from_sitemap(sitemap_url)
    
    if not links:
        print("No links found or failed to process sitemap.")
        return

    print(f"Found {len(links)} links.")

    # Save to CSV
    csv_file_path = os.path.join(domain_name, 'links.csv')
    try:
        with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['URL'])
            for link in links:
                writer.writerow([link])
        print(f"Successfully saved links to {csv_file_path}")
    except IOError as e:
        print(f"Error saving CSV: {e}")

if __name__ == "__main__":
    main()
