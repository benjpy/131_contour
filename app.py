import streamlit as st
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
import pandas as pd
import time
from bs4 import BeautifulSoup

# --- Helper Functions ---
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
    """
    links = []
    try:
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code != 200:
            return []

        root = ET.fromstring(response.content)
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        if root.tag.endswith('sitemapindex'):
             for sitemap in root.findall('ns:sitemap', namespace):
                 loc = sitemap.find('ns:loc', namespace)
                 if loc is not None:
                     links.extend(extract_links_from_sitemap(loc.text))
        else:
             for url in root.findall('ns:url', namespace):
                 loc = url.find('ns:loc', namespace)
                 if loc is not None:
                     links.append(loc.text)
                     
    except (requests.RequestException, ET.ParseError):
        return []
        
    return links

def count_internal_links(page_url, target_domain):
    """
    Fetches a page and counts unique internal links to the target domain.
    """
    try:
        response = requests.get(page_url, timeout=5)
        if response.status_code != 200:
            return 0
            
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a', href=True)
        
        internal_links = set()
        for link in links:
            href = link['href']
            full_url = urljoin(page_url, href)
            parsed_href = urlparse(full_url)
            
            # Check if link belongs to the same domain
            if parsed_href.netloc == target_domain:
                internal_links.add(full_url)
                
        return len(internal_links)
    except Exception:
        return 0

# --- Streamlit UI ---
st.set_page_config(page_title="Sitemap SEO Analyzer", page_icon="🕷️", layout="wide")

st.title("🕷️ Sitemap SEO Analyzer")
st.markdown("Extract all links from a sitemap and analyze their internal cross-linking structure.")

# Initialize session state for data persistence
if "sitemap_links" not in st.session_state:
    st.session_state.sitemap_links = []
if "analyzed_data" not in st.session_state:
    st.session_state.analyzed_data = None

url_input = st.text_input("Website URL", placeholder="https://example.com")

if st.button("1. Find Sitemap & Extract Links", type="primary"):
    if not url_input:
        st.error("Please enter a URL.")
    else:
        if not url_input.startswith(('http://', 'https://')):
            url_input = 'https://' + url_input
            
        with st.status("Finding Sitemap...", expanded=True) as status:
            st.write("🔍 Looking for sitemap...")
            sitemap_url = get_sitemap_url(url_input)
            
            if sitemap_url:
                st.write(f"✅ Found sitemap: `{sitemap_url}`")
                st.write("⏳ Extracting links...")
                
                links = extract_links_from_sitemap(sitemap_url)
                
                if links:
                    st.session_state.sitemap_links = links
                    st.session_state.analyzed_data = None # Reset analysis
                    status.update(label="Extraction Complete!", state="complete", expanded=False)
                    st.success(f"🎉 Found {len(links)} links!")
                else:
                    status.update(label="Failed", state="error")
                    st.error("❌ Found sitemap but failed to extract links.")
            else:
                status.update(label="Failed", state="error")
                st.error("❌ Could not find a sitemap.")

# Step 2: Analysis
if st.session_state.sitemap_links:
    st.divider()
    st.subheader("Step 2: Cross-Linking Analysis")
    st.markdown(f"Ready to analyze **{len(st.session_state.sitemap_links)}** pages. This will count internal links on each page.")
    
    if st.button("2. Analyze Internal Links"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        total_links = len(st.session_state.sitemap_links)
        domain = urlparse(url_input if url_input.startswith('http') else 'https://' + url_input).netloc

        
        for i, link in enumerate(st.session_state.sitemap_links):
            # Update progress
            progress = (i + 1) / total_links
            progress_bar.progress(progress)
            status_text.text(f"Analyzing {i+1}/{total_links}: {link}")
            
            internal_count = count_internal_links(link, domain)
            results.append({"URL": link, "Internal Links": internal_count})
            
            # Small delay to be polite to the server
            time.sleep(0.1)
            
        st.session_state.analyzed_data = pd.DataFrame(results)
        status_text.empty()
        progress_bar.empty()
        st.success("✅ Analysis Complete!")

# Display Results
if st.session_state.analyzed_data is not None:
    df = st.session_state.analyzed_data
    
    st.divider()
    st.subheader("Results")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Pages", len(df))
    with col2:
        st.metric("Avg. Internal Links", f"{df['Internal Links'].mean():.1f}")
    
    st.dataframe(
        df, 
        use_container_width=True,
        column_config={
            "URL": st.column_config.LinkColumn("Page URL"),
            "Internal Links": st.column_config.NumberColumn("Internal Links", format="%d 🔗")
        }
    )
    
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Analyzed CSV",
        data=csv,
        file_name="sitemap_seo_analysis.csv",
        mime="text/csv",
    )
    
elif st.session_state.sitemap_links:
    # Show preview of just links if analysis hasn't happened yet
    with st.expander("Preview Extracted Links"):
        st.write(st.session_state.sitemap_links)

