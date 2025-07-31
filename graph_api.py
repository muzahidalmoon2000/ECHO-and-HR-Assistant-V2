import requests
import os
import time
import logging
import re
from semantic_search import rank_files_by_similarity, build_faiss_index
from msal_auth import load_token_cache, save_token_cache, build_msal_app
from extractor import extract_text_from_scanned_pdf, extract_text_from_pdf, extract_text_from_image

logging.basicConfig(level=logging.INFO)

def refresh_token(account_id):
    cache = load_token_cache(account_id)
    app = build_msal_app(cache)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(os.getenv("SCOPE").split(), account=accounts[0])
        if "access_token" in result:
            save_token_cache(account_id, cache)
            return result["access_token"]
    return None

def retry_request(url, headers, method="get", json=None, max_retries=2, account_id=None):
    for i in range(max_retries + 1):
        try:
            res = requests.request(method, url, headers=headers, json=json)
            if res.status_code == 401 and account_id:
                logging.warning("Received 401 Unauthorized. Attempting token refresh...")
                token = refresh_token(account_id)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    continue
            elif res.status_code == 429:
                retry_after = int(res.headers.get("Retry-After", 5))
                logging.warning(f"Rate limited on {url}. Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
            else:
                logging.info(f"Request to {url} returned status {res.status_code}")
                return res
        except Exception as e:
            logging.error(f"Request error on {url}: {e}")
    logging.error(f"Max retries exceeded for {url}")
    return res

def get_file_with_download_url(drive_id, item_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}"
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return res.json()
    else:
        logging.warning(f"⚠️ Failed to fetch full metadata for item {item_id}")
        return None

def get_user_email(account_id):
    token = refresh_token(account_id)
    if not token:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    res = retry_request("https://graph.microsoft.com/v1.0/me", headers)
    if res.status_code == 200:
        return res.json().get("mail") or res.json().get("userPrincipalName")
    return None

def discover_all_sites(token):
    headers = {"Authorization": f"Bearer {token}"}
    sites = []
    url = "https://graph.microsoft.com/v1.0/sites?search=*"
    while url:
        res = retry_request(url, headers)
        if res.status_code == 200:
            data = res.json()
            sites.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
        else:
            break
    return sites

def search_all_files(token, query):
    headers = {"Authorization": f"Bearer {token}"}
    all_results = []
    seen_ids = set()

    year_match = re.search(r'\b(19|20)\d{2}\b', query)
    year = year_match.group() if year_match else None

    words = query.split()
    if year:
        words.remove(year)

    core = " ".join(words).strip().lower()
    query_batch = [core]

    for q in query_batch:
        me_url = f"https://graph.microsoft.com/v1.0/me/drive/root/search(q='{q}')"
        me_res = retry_request(me_url, headers)
        if me_res.status_code == 200:
            for item in me_res.json().get("value", []):
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    meta = get_file_with_download_url(item["parentReference"]["driveId"], item["id"], token)
                    if meta:
                        all_results.append(meta)

    sites = discover_all_sites(token)
    for site in sites:
        site_id = site.get("id")
        if not site_id:
            continue
        drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
        drives_res = retry_request(drives_url, headers)
        if drives_res.status_code != 200:
            continue
        for drive in drives_res.json().get("value", []):
            for q in query_batch:
                search_url = f"https://graph.microsoft.com/v1.0/drives/{drive['id']}/search(q='{q}')"
                search_res = retry_request(search_url, headers)
                if search_res.status_code == 200:
                    for item in search_res.json().get("value", []):
                        if item["id"] not in seen_ids:
                            seen_ids.add(item["id"])
                            meta = get_file_with_download_url(item["parentReference"]["driveId"], item["id"], token)
                            if meta:
                                all_results.append(tag_site_id([meta], site_id)[0])

    if not all_results:
        logging.info("No results from batch search. Using recent files.")
        all_results = fetch_recent_files(token)

    files = [f for f in all_results if "folder" not in f]

    def process_file(file):
        download_url = file.get('@microsoft.graph.downloadUrl')
        if not download_url:
            logging.warning(f"⚠️ Skipping {file.get('name')}: no download URL.")
            return ""
        mime = file.get("file", {}).get("mimeType", "")
        image_types = ["image/png", "image/jpeg", "image/jpg", "image/gif", "image/bmp"]
        if mime in image_types:
            return extract_text_from_image(download_url)
        elif 'pdf' in mime:
            text = extract_text_from_pdf(download_url)
            return text if text.strip() else extract_text_from_scanned_pdf(download_url)
        return ""

    for file in files:
        text = process_file(file)
        if text:
            file['extracted_text'] = text

    # Build FAISS index only for file searching
    build_faiss_index(files, index_name="file")

    # Use FAISS for semantic ranking
    ranked_files = rank_files_by_similarity(query, top_k=None, index_name="file")
    return ranked_files

def fetch_recent_files(token):
    headers = {"Authorization": f"Bearer {token}"}
    res = retry_request("https://graph.microsoft.com/v1.0/me/drive/recent", headers)
    if res.status_code == 200:
        return tag_site_id(res.json().get("value", []), "personal")
    return []

def tag_site_id(items, site_id):
    for item in items:
        if "parentReference" not in item:
            item["parentReference"] = {}
        item["parentReference"]["siteId"] = site_id
    return items

def check_file_access(token, item_id, user_email, site_id=None):
    if os.getenv("PERFORM_ACCESS_CHECK", "false").lower() != "true":
        return True
    headers = {"Authorization": f"Bearer {token}"}
    if site_id and site_id != "personal":
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{item_id}/permissions"
        try:
            res = retry_request(url, headers)
            if res.status_code == 200:
                return True
        except Exception as e:
            logging.warning(f"⚠️ SharePoint access check failed: {e}")
    return False

def send_notification_email(token, to_email, file_name, file_url):
    return send_email(token, to_email, f"Here is the file: {file_name}", f"<p><a href='{file_url}'>{file_name}</a></p>")

def send_multiple_file_email(token, to_email, files):
    links = "".join(f"<p><a href='{f['webUrl']}'>{f['name']}</a></p>" for f in files)
    return send_email(token, to_email, "Your requested files", f"<p>Here are the files you requested:</p>{links}")

def send_email(token, to_email, subject, html_content):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    message = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": html_content
            },
            "toRecipients": [{"emailAddress": {"address": to_email}}]
        },
        "saveToSentItems": True
    }

    try:
        res = retry_request(
            "https://graph.microsoft.com/v1.0/me/sendMail",
            headers,
            method="post",
            json=message
        )
        if res.status_code == 202:
            logging.info(f"✅ Email sent to {to_email}")
            return True
        else:
            logging.error(f"❌ Failed to send email to {to_email}: {res.status_code} - {res.text}")
            return False
    except Exception as e:
        logging.error(f"Email send failed: {e}")
        return False
