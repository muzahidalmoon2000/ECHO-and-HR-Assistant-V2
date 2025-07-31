import pytesseract
import numpy as np
import fitz  # PyMuPDF
from PIL import Image
from io import BytesIO
import requests

print(pytesseract.get_tesseract_version())

# OCR for images using Tesseract
def extract_text_from_image(image_url):
    try:
        response = requests.get(image_url)
        img = Image.open(BytesIO(response.content)).convert("L")  # grayscale
        img = img.resize((img.width * 2, img.height * 2))  # upscale for better OCR
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        print(f"❌ Tesseract OCR failed: {e}")
        return ""

# Extract text from scanned PDFs using Tesseract OCR
def extract_text_from_scanned_pdf(pdf_url):
    try:
        response = requests.get(pdf_url)
        if response.status_code != 200 or "pdf" not in response.headers.get("Content-Type", "").lower():
            print(f"⚠️ Invalid scanned PDF response: {pdf_url}")
            return ""

        pdf_file = fitz.open(stream=response.content, filetype="pdf")
        text = ""
        for page_num in range(pdf_file.page_count):
            page = pdf_file.load_page(page_num)
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("L")
            img = img.resize((img.width * 2, img.height * 2))
            text += pytesseract.image_to_string(img) + "\n"
        return text.strip()
    except Exception as e:
        print(f"❌ Tesseract PDF OCR failed: {e}")
        return ""

# Text extraction from PDFs (non-scanned)
def extract_text_from_pdf(pdf_url):
    try:
        response = requests.get(pdf_url)
        content_type = response.headers.get("Content-Type", "")
        if response.status_code != 200 or "pdf" not in content_type.lower():
            print(f"⚠️ Invalid PDF response from {pdf_url} — Content-Type: {content_type}")
            return ""

        pdf_file = fitz.open(stream=response.content, filetype="pdf")
        text = ""
        for page_num in range(pdf_file.page_count):
            page = pdf_file.load_page(page_num)
            text += page.get_text()
        return text.strip()
    except Exception as e:
        print(f"❌ PyMuPDF failed to open PDF: {e}")
        return ""
