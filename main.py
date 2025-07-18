from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import sys
import time
import subprocess

app = Flask(__name__)

def scrape_gong_transcript(url):
    """Scrape transcript from Gong URL and return as list of lines"""
    # Get system paths for Chrome and Chromedriver
    try:
        chromium_path = subprocess.check_output(['which', 'chromium']).decode().strip()
        chromedriver_path = subprocess.check_output(['which', 'chromedriver']).decode().strip()
    except subprocess.CalledProcessError:
        raise Exception("Chrome or Chromedriver not found in system PATH")
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    # Set Chrome binary location to system path
    chrome_options.binary_location = chromium_path

    # Setup Chrome driver with system path
    service = Service(executable_path=chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Get the page
        driver.get(url)
        
        # Wait for the transcript section to load
        wait = WebDriverWait(driver, 30)
        transcript_section = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "section.CallTranscript-moduleCLO4Fw[aria-label='Call transcript']"))
        )
        
        # Get page source after JavaScript execution
        page_source = driver.page_source
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(page_source, "html.parser")

    except Exception as e:
        driver.quit()
        raise Exception(f"Failed to load page: {str(e)}")
    finally:
        driver.quit()

    # Parse transcript section
    transcript_section = soup.select_one("section.CallTranscript-moduleCLO4Fw[aria-label='Call transcript']")
    if not transcript_section:
        raise Exception("Transcript section not found in page source")

    transcript_blocks = transcript_section.select('div.monologue-wrapper')
    if not transcript_blocks:
        raise Exception("No transcript blocks found")

    output_lines = []
    for block in transcript_blocks:
        # timestamp
        timestamp_tag = block.select_one('span.timestamp')
        timestamp = timestamp_tag.get_text(strip=True) if timestamp_tag else ''

        # speaker name: first try only-speaker-visible class span, else empty
        speaker_tag = block.select_one('span.only-speaker-visible')
        speaker = speaker_tag.get_text(strip=True) if speaker_tag else ''

        # utterance text (words are in spans with monologue-word class)
        utterance = ""
        monologue_text = block.select_one('div.monologue-text')
        if monologue_text:
            word_spans = monologue_text.select('span.monologue-word')
            if word_spans:
                utterance = " ".join([w.get_text(strip=True) for w in word_spans])
            else:
                utterance = monologue_text.get_text(" ", strip=True)

        # Compose line if utterance exists
        if utterance:
            line = f"{timestamp} {speaker} {utterance}".strip()
            output_lines.append(line)

    return output_lines

@app.route('/')
def index():
    return '''
    <h1>Gong Transcript API</h1>
    <p>Use GET /transcript?url=YOUR_GONG_URL to get transcript</p>
    <p>Example: /transcript?url=https://us-57974.app.gong.io/e/c-share/?tkn=9mkbb97t5cx84wzsygwvsie9</p>
    '''

@app.route('/transcript')
def get_transcript():
    """API endpoint to get transcript from Gong URL"""
    gong_url = request.args.get('url')

    if not gong_url:
        return jsonify({
            'error': 'Missing required parameter: url',
            'usage': 'GET /transcript?url=YOUR_GONG_URL'
        }), 400

    # Basic validation for Gong URL
    if 'gong.io' not in gong_url:
        return jsonify({
            'error': 'Invalid URL: Must be a Gong URL containing "gong.io"'
        }), 400

    try:
        transcript_lines = scrape_gong_transcript(gong_url)

        return jsonify({
            'success': True,
            'url': gong_url,
            'transcript': transcript_lines,
            'total_lines': len(transcript_lines)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'url': gong_url
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)