import streamlit as st
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
import pandas as pd
import time
from bs4 import BeautifulSoup

# --- Helper Functions ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

def normalize_domain(domain):
    """
    Normalizes a domain by removing 'www.' and converting to lowercase.
    """
    if not domain:
        return ""
    return domain.lower().replace('www.', '')

def get_sitemap_url(base_url):
    """
    Attempts to find the sitemap URL by checking robots.txt or common paths.
    """
    parsed_url = urlparse(base_url)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    # Check robots.txt
    robots_url = urljoin(domain, '/robots.txt')
    try:
        response = requests.get(robots_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            for line in response.text.splitlines():
                if line.lower().startswith('sitemap:'):
                    return line.split(':', 1)[1].strip()
    except requests.RequestException:
        pass
    
    # Fallback to standard sitemap locations
    common_paths = ['/sitemap.xml', '/sitemap_index.xml', '/wp-sitemap.xml']
    for path in common_paths:
        try:
            sitemap_candidate = urljoin(domain, path)
            # Use HEAD request to check availability without downloading full content
            response = requests.head(sitemap_candidate, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                return sitemap_candidate
        except requests.RequestException:
            continue
            
    return None

def extract_links_from_sitemap(sitemap_url):
    """
    Fetches and parses the sitemap XML to extract URLs.
    """
    links = []
    try:
        response = requests.get(sitemap_url, headers=HEADERS, timeout=15)
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

def count_internal_links(page_url, target_domains):
    """
    Fetches a page and counts unique internal links to any of the target domains,
    heuristically excluding navigation, footer, and sidebars.
    target_domains: A set of normalized domain strings.
    """
    try:
        response = requests.get(page_url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            # Maybe add logging here?
            return 0
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Heuristic: Find main content to avoid counting nav/footer links
        content_area = None
        
        # Priority 1: <article> tag
        article = soup.find('article')
        if article:
            content_area = article
        
        # Priority 2: <main> tag
        if not content_area:
            main = soup.find('main')
            if main:
                content_area = main
                
        # Priority 3: Fallback to body
        if not content_area:
            content_area = soup.find('body')
            
        if not content_area:
             return 0

        # Create a copy or work directly? Modifying soup modifies the tree.
        # We can just decompose the unwanted tags within the content_area
        exclude_tags = ['nav', 'header', 'footer', 'aside', 'form', 'script', 'style']
        for tag in content_area.find_all(exclude_tags):
            tag.decompose()
            
        links = content_area.find_all('a', href=True)
        
        internal_links = set()
        for link in links:
            href = link['href']
            # handle relative URLs
            full_url = urljoin(page_url, href)
            parsed_href = urlparse(full_url)
            
            # Normalize the link's domain
            link_domain = normalize_domain(parsed_href.netloc)
            
            # Check if link belongs to any of the target domains
            # If netloc is empty (relative link), it's internal to the page_url's domain
            if not parsed_href.netloc:
                # Relative link, assume internal if counting base domain
                # But we need valid full URL
                pass # already handled by urljoin, netloc should be present in full_url check
            
            if link_domain in target_domains:
                 # Exclude anchor links to the same page
                 if full_url.split('#')[0] != page_url.split('#')[0]:
                    internal_links.add(full_url)
                
        return len(internal_links)
    except Exception:
        return 0

def extract_category(url):
    """
    Extracts the first directory from the URL path to use as a category.
    Example: example.com/blog/post-1 -> 'blog'
    """
    path = urlparse(url).path.strip('/')
    if not path:
        return "root"
    
    segments = path.split('/')
    return segments[0] if segments else "root"


# --- Streamlit UI ---
st.set_page_config(page_title="Sitemap SEO Analyzer", page_icon="🕷️", layout="wide")

st.title("🕷️ Sitemap SEO Analyzer")
st.markdown("Extract all links from a sitemap and analyze their internal cross-linking structure.")

# Initialize session state for data persistence
if "sitemap_links" not in st.session_state:
    st.session_state.sitemap_links = []
if "analyzed_data" not in st.session_state:
    st.session_state.analyzed_data = None

col_input1, col_input2 = st.columns(2)
with col_input1:
    url_input = st.text_input("Website URL", placeholder="https://example.com")
with col_input2:
    related_domains_input = st.text_input("Additional Related Domains (comma-separated)", placeholder="example.university, other-site.com")

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

import concurrent.futures

# ... imports ...

# Step 2: Analysis
if st.session_state.sitemap_links:
    st.divider()
    st.subheader("Step 2: Cross-Linking Analysis")
    st.markdown(f"Ready to analyze **{len(st.session_state.sitemap_links)}** pages. This will count internal links on each page.")
    
    # Speed control
    max_workers = st.slider("Concurrency (Workers)", min_value=1, max_value=20, value=4, help="Higher values are faster but might get blocked by some servers.")
    
    if st.button("2. Analyze Internal Links"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        total_links = len(st.session_state.sitemap_links)
        
        # Prepare Target Domains
        main_domain = normalize_domain(urlparse(url_input if url_input.startswith('http') else 'https://' + url_input).netloc)
        target_domains = {main_domain}
        
        if related_domains_input:
            others = [normalize_domain(d.strip()) for d in related_domains_input.split(',')]
            target_domains.update(others)
            
        st.info(f"Counting links to: {', '.join(target_domains)}")

        start_time = time.time()
        
        # Parallel Execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks. Pass the set of target_domains
            future_to_url = {executor.submit(count_internal_links, url, target_domains): url for url in st.session_state.sitemap_links}
            
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    internal_count = future.result()
                    results.append({"URL": url, "Internal Links": internal_count})
                except Exception as e:
                    results.append({"URL": url, "Internal Links": 0}) # Fail safe
                
                # Update progress
                completed_count += 1
                progress = completed_count / total_links
                progress_bar.progress(progress)
                status_text.text(f"Analyzing {completed_count}/{total_links}...")

        elapsed_time = time.time() - start_time
        st.session_state.analyzed_data = pd.DataFrame(results)
        
        status_text.empty()
        progress_bar.empty()
        st.success(f"✅ Analysis Complete in {elapsed_time:.2f} seconds!")

# Display Results
if st.session_state.analyzed_data is not None:
    df = st.session_state.analyzed_data
    
    # Calculate Categories
    df['Category'] = df['URL'].apply(extract_category)
    
    st.divider()
    st.subheader("Results")
    
    # 1. Overall Metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Pages", len(df))
    with col2:
        st.metric("Avg. Internal Links", f"{df['Internal Links'].mean():.1f}")
    
    # 2. Category Analysis
    st.subheader("📂 Category Analysis")
    st.markdown("Average internal links per sub-folder.")
    
    category_stats = df.groupby('Category').agg({
        'URL': 'count',
        'Internal Links': 'mean'
    }).reset_index()
    
    category_stats.columns = ['Category', 'Page Count', 'Avg. Internal Links']
    category_stats['Avg. Internal Links'] = category_stats['Avg. Internal Links'].round(1)
    
    # Sort by page count by default
    category_stats = category_stats.sort_values('Page Count', ascending=False)
    
    st.dataframe(
        category_stats,
        use_container_width=True,
        column_config={
            "Category": st.column_config.TextColumn("Sub-Folder", help="The root folder of the URL path"),
            "Page Count": st.column_config.NumberColumn("Pages"),
            "Avg. Internal Links": st.column_config.ProgressColumn("Avg. Cross-Links", format="%.1f", min_value=0, max_value=max(category_stats['Avg. Internal Links'].max(), 10))
        },
        hide_index=True
    )
    
    st.divider()
    st.subheader("📄 Page Details")
    st.dataframe(
        df, 
        use_container_width=True,
        column_config={
            "URL": st.column_config.LinkColumn("Page URL"),
            "Internal Links": st.column_config.NumberColumn("Internal Links", format="%d 🔗"),
            "Category": st.column_config.TextColumn("Category")
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

