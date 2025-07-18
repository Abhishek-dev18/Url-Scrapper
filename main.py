from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup

app = Flask(__name__)

def scrape_gong_transcript(url):
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
    chrome_options.binary_location = "/usr/bin/chromium"

    driver = webdriver.Chrome(
        service=Service("/usr/bin/chromedriver"),
        options=chrome_options
    )

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 30)
        transcript_section = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "section.CallTranscript-moduleCLO4Fw[aria-label='Call transcript']"))
        )
        soup = BeautifulSoup(driver.page_source, "html.parser")
    finally:
        driver.quit()

    transcript_section = soup.select_one("section.CallTranscript-moduleCLO4Fw[aria-label='Call transcript']")
    if not transcript_section:
        raise Exception("Transcript section not found in page source")

    transcript_blocks = transcript_section.select('div.monologue-wrapper')
    if not transcript_blocks:
        raise Exception("No transcript blocks found")

    output_lines = []
    for block in transcript_blocks:
        timestamp = block.select_one('span.timestamp')
        speaker = block.select_one('span.only-speaker-visible')
        monologue_text = block.select_one('div.monologue-text')

        timestamp = timestamp.get_text(strip=True) if timestamp else ''
        speaker = speaker.get_text(strip=True) if speaker else ''

        utterance = ""
        if monologue_text:
            word_spans = monologue_text.select('span.monologue-word')
            if word_spans:
                utterance = " ".join([w.get_text(strip=True) for w in word_spans])
            else:
                utterance = monologue_text.get_text(" ", strip=True)

        if utterance:
            line = f"{timestamp} {speaker} {utterance}".strip()
            output_lines.append(line)

    return output_lines

@app.route('/')
def index():
    return '''
    <h1>Gong Transcript API</h1>
    <p>Use GET /transcript?url=YOUR_GONG_URL to get transcript</p>
    '''

@app.route('/transcript')
def get_transcript():
    gong_url = request.args.get('url')
    if not gong_url:
        return jsonify({'error': 'Missing required parameter: url'}), 400
    if 'gong.io' not in gong_url:
        return jsonify({'error': 'Invalid URL: Must contain "gong.io"'}), 400

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
