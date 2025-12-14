import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

def normalize_domain(domain):
    if not domain:
        return ""
    return domain.lower().replace('www.', '')

def count_internal_links_debug(page_url, target_domains):
    print(f"Analyzing: {page_url}")
    print(f"Target Domains: {target_domains}")
    
    try:
        response = requests.get(page_url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Heuristic: Find main content
        content_area = None
        
        article = soup.find('article')
        if article:
            print("Found <article>")
            content_area = article
        
        if not content_area:
            main = soup.find('main')
            if main:
                print("Found <main>")
                content_area = main
                
        if not content_area:
            print("Fallback to <body>")
            content_area = soup.find('body')
            
        if not content_area:
             print("No content area found")
             return 0

        # Exclude tags
        exclude_tags = ['nav', 'header', 'footer', 'aside', 'form', 'script', 'style']
        for tag in content_area.find_all(exclude_tags):
            tag.decompose()
            
        links = content_area.find_all('a', href=True)
        print(f"Found {len(links)} candidate links in content area")
        
        internal_count = 0
        for link in links:
            href = link['href']
            full_url = urljoin(page_url, href)
            parsed_href = urlparse(full_url)
            
            link_domain = normalize_domain(parsed_href.netloc)
            
            # Debug specific links
            if "contournement" in str(href):
                print(f"Checking link: {href} -> Domain: {link_domain}")
            
            if link_domain in target_domains:
                 if full_url.split('#')[0] != page_url.split('#')[0]:
                    internal_count += 1
                
        print(f"Final Count: {internal_count}")
        return internal_count

    except Exception as e:
        print(f"Error: {e}")
        return 0

if __name__ == "__main__":
    url = "https://www.contournement.io/discernement/les-agents-ia-debarquent-chez-contournement-avec-zapier-agents"
    domains = {"contournement.io"}
    count_internal_links_debug(url, domains)
