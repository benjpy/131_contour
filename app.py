import streamlit as st
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
import pandas as pd
import time

# --- Helper Functions (Adapted from sitemap_extractor.py) ---
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
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code != 200:
            return []

        root = ET.fromstring(response.content)
        
        # XML namespaces
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # Look for <sitemap> entries (sitemap index)
        if root.tag.endswith('sitemapindex'):
             for sitemap in root.findall('ns:sitemap', namespace):
                 loc = sitemap.find('ns:loc', namespace)
                 if loc is not None:
                     # Recursive call for sitemap index
                     links.extend(extract_links_from_sitemap(loc.text))
        else:
             # Standard sitemap with <url> entries
             for url in root.findall('ns:url', namespace):
                 loc = url.find('ns:loc', namespace)
                 if loc is not None:
                     links.append(loc.text)
                     
    except (requests.RequestException, ET.ParseError):
        return []
        
    return links

# --- Streamlit UI ---
st.set_page_config(page_title="Sitemap Extractor", page_icon="🕷️")

st.title("🕷️ Sitemap Link Extractor")
st.markdown("Enter a website URL to automatically find its sitemap and extract all links into a CSV.")

url_input = st.text_input("Website URL", placeholder="https://example.com")

if st.button("Extract Links", type="primary"):
    if not url_input:
        st.error("Please enter a URL.")
    else:
        if not url_input.startswith(('http://', 'https://')):
            url_input = 'https://' + url_input
            
        with st.status("Processing...", expanded=True) as status:
            st.write("🔍 Looking for sitemap...")
            sitemap_url = get_sitemap_url(url_input)
            
            if sitemap_url:
                st.write(f"✅ Found sitemap: `{sitemap_url}`")
                st.write("⏳ Extracting links (this may take a moment)...")
                
                links = extract_links_from_sitemap(sitemap_url)
                
                if links:
                    status.update(label="Extraction Complete!", state="complete", expanded=False)
                    st.success(f"🎉 Found {len(links)} links!")
                    
                    # Create DataFrame for display and download
                    df = pd.DataFrame(links, columns=["URL"])
                    
                    # Preview
                    with st.expander("Preview Links"):
                        st.dataframe(df, use_container_width=True)
                    
                    # Download
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name="sitemap_links.csv",
                        mime="text/csv",
                    )
                else:
                    status.update(label="Failed", state="error")
                    st.error("❌ Found sitemap but failed to extract links. It might be empty or malformed.")
            else:
                status.update(label="Failed", state="error")
                st.error("❌ Could not find a sitemap.Checked `robots.txt` and `/sitemap.xml`.")

st.markdown("---")
st.caption("Built with Streamlit • Checks robots.txt & standard sitemap locations")
