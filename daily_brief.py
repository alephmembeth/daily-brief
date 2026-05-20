##########
# IMPORT #
##########

# Import standard libraries
import datetime
import glob
import io
import math
import os
import random
import subprocess
import textwrap
import xml.etree.ElementTree as ET

# Import third-party libraries
# import IPython.display
from icalevents.icalevents import events
from PIL import Image, ImageDraw, ImageFont
import requests
import resvg_py


#################
# CONFIGURATION #
#################

# Set mode
PREVIEW_MODE = True

# Set folder
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Set layout constants
WIDTH = 512
TIMELINE_X = 70
MAX_NEWS = 7
MAX_TASKS = 12
CHAR_WIDTH = 35

# Set temperature range
T_MIN, T_MAX = -10, 40

# Set calendars
ICAL_URLS = {
    "Kalender 1": "KALENDER 1 URL",
    "Kalender 2": "KALENDER 2 URL"
}

# Set logo
LOGO_URL = "https://cdn.prod.website-files.com/655bb8af26f2a1957ef8b0c9/67883e1b340fe8d60b9e6822_Risorsa%2012.svg"

# Set vault path
OBSIDIAN_VAULT = "VAULT PATH"

# Calculate target date
target_date = datetime.date.today()
if PREVIEW_MODE:
    target_date += datetime.timedelta(days = 1)


#############
# FUNCTIONS #
#############
def get_logo(url, target_width = 160):
    """Downloads and converts logo."""
    try:
        
        # Send request
        res = requests.get(url, timeout = 5)
        
        # Check if request was successful
        if res.status_code == 200:
            
            # Convert SVG to PNG
            png_data = resvg_py.svg_to_bytes(res.text)
            
            # Open PNG
            img_original = Image.open(io.BytesIO(png_data))
            
            # Check if image has transparency
            if img_original.mode == 'RGBA':
                
                # Create white background
                background = Image.new('RGB', img_original.size, (255, 255, 255))
                
                # Paste image on white background
                background.paste(img_original, (0, 0), img_original)
                
                # Convert to grayscale
                img_l = background.convert('L')
            else:
                
                # Convert to grayscale
                img_l = img_original.convert('L')
            
            # Calculate scaling factor
            w_percent = (target_width / float(img_l.size[0]))
            
            # Calculate height
            h_size = int((float(img_l.size[1]) * float(w_percent)))
            
            # Resize image
            return img_l.resize((target_width, h_size), Image.Resampling.LANCZOS)
    except Exception:
        pass
    return None

def draw_weather_icon(draw, x, y, condition_code):
    """Draws weather icons."""
    
    # Convert condition code to lowercase
    c = str(condition_code).lower()
    
    # (1) Sun
    # Check for codes or keywords related to sunny weather
    if any(word in c for word in ["113", "sun", "clear"]):
        
        # Draw sun body
        draw.ellipse([x + 15, y + 15, x + 65, y + 65], outline = 0, width = 2)
        
        # Draw sun rays
        for i in range(0, 360, 45):
            rad = math.radians(i)
            draw.line([
                x + 40 + math.cos(rad) * 30, y + 40 + math.sin(rad) * 30,
                x + 40 + math.cos(rad) * 45, y + 40 + math.sin(rad) * 45
            ], fill = 0, width = 3)
    
    # (2) Rain
    # Check for codes or keywords related to rainy weather
    elif any(word in c for word in ["rain", "showers", "176", "296", "302", "308"]):
        
        # Draw cloud
        draw.chord([x + 10, y + 10, x + 70, y + 50], 180, 0, outline = 0, width = 2)
        
        # Draw rain
        for i in range(20, 70, 15):
            draw.line([x + i, y + 40, x + i - 5, y + 60], fill = 0, width = 2)
    
    # (3) Clouds
    else:
        
        # Draw left part
        draw.ellipse([x + 10, y + 35, x + 40, y + 65], fill = 255, outline = 0, width = 2)
        
        # Draw middle part
        draw.ellipse([x + 25, y + 20, x + 65, y + 65], fill = 255, outline = 0, width = 2)
        
        # Draw right part
        draw.ellipse([x + 45, y + 35, x + 75, y + 65], fill = 255, outline = 0, width = 3)

def get_weather(is_preview):
    """Fetches weather data."""
    try:
        
        # Send request
        res = requests.get("https://wttr.in/Oldenburg?format=j1&lang=de", timeout = 5).json()
        
        # Decide whether to look at today or tomorrow
        day_idx = 1 if is_preview else 0
        w_data = res['weather'][day_idx]
        
        # Get hourly data
        hourly = w_data['hourly']
        
        # Extract midday forecast description
        desc = hourly[4]['lang_de'][0]['value'] if 'lang_de' in hourly[4] else hourly[4]['weatherDesc'][0]['value']
        
        # Return dictionary
        return {
            "temp":    hourly[4]['tempC'],                         # Midday temperature
            "code":    hourly[4]['weatherCode'],                   # Icon code
            "desc":    desc,                                       # Description
            "temps":   [int(h['tempC']) for h in hourly],          # Temperatures
            "rain":    [int(h['chanceofrain']) for h in hourly],   # Rain probabilities
            "abs_min": w_data['mintempC'],                         # Minimum temperature
            "abs_max": w_data['maxtempC']                          # Maximum temperature
        }
    except Exception:
        return None

def get_events(urls_dict, target_date):
    """Fetches calendar entries."""
    all_ev = []
    
    # Loop through calendars
    for label, url in urls_dict.items():
        try:
            
            # Query ical file for events on target_date
            found = events(url, start = target_date, end = target_date + datetime.timedelta(days = 1))
            
            # Extract start time, end time, and summary
            for e in found:
                all_ev.append({
                    'start': e.start.replace(tzinfo = None),
                    'end': e.end.replace(tzinfo = None),
                    'summary': e.summary
                })
        except Exception:
            pass
    
    # Return events sorted by start time
    return sorted(all_ev, key = lambda x: x['start'])

def get_tasks():
    """Fetches tasks."""
    
    # Set tag
    target_tag = "Aktuell"
    
    # Set AppleScript
    script = f'set output to "" \n tell application "Things3" \n repeat with t in (to dos of list "Heute" whose tag names contains "{target_tag}") \n if status of t is not completed then \n set tName to (name of t) as string \n set pName to "" \n try \n set pName to (name of project of t) as string \n end try \n set output to output & tName & ":::" & pName & "|||" \n end if \n end repeat \n end tell \n return output'
    try:
        
        # Execute AppleScript
        proc = subprocess.run(['osascript', '-e', script], capture_output = True, text = True)
        raw = proc.stdout.strip()
        
        # Parse string into list of dicts
        all_tasks = [{"name": i.split(":::")[0], "project": i.split(":::")[1]} for i in raw.split("|||") if ":::" in i]
        
        # Return tasks
        return all_tasks[:MAX_TASKS]
    except Exception:
        return []

def get_news():
    """Fetches headlines."""
    try:
        
        # Send request
        res = requests.get("https://www.tagesschau.de/infoservices/alle-meldungen-100~rss2.xml", timeout = 5)
        
        # Parse XML into ElementTree root object
        root = ET.fromstring(res.content)
        
        # Return headlines
        return [textwrap.wrap(item.find('title').text, width = CHAR_WIDTH) for item in root.findall('./channel/item')[:MAX_NEWS]]
    except Exception:
        return [["Nachrichten nicht verfügbar"]]

def get_fact():
    """Fetches a random fact."""
    try:
        
        # Send request
        r = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=de", timeout = 5)
        
        # Raise exception if request failed
        r.raise_for_status()
        
        # Return fact
        return textwrap.wrap(f"{r.json()['text']}", width = CHAR_WIDTH)
    except Exception:
        return []

def get_vocabs(vault_path, count = 5):
    """Fetches random vocabularies."""
    all_cards = []
    
    # Search for markdown files starting with "Vokabeln"
    search_path = os.path.join(vault_path, "**", "Vokabeln*.md")
    files = glob.glob(search_path, recursive = True)
    for file_path in files:
        try:
            with open(file_path, "r", encoding = "utf-8") as f:
                content = f.read()
            
            # Check if the file contains the tag "Vokabeln_Altgriechisch"
            if "Vokabeln_Altgriechisch" not in content:
                continue
            
            # Clean and split content into non-empty lines
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            
            # Parse flashcards based on the separator "?"
            for i in range(1, len(lines) - 1):
                if lines[i] == "?":
                    front = lines[i-1]
                    back = lines[i+1]
                    
                    # Ignore headers and navigation
                    if "|" in front or ">>" in front or "tags:" in front:
                        continue
                    all_cards.append({"front": front, "back": back})
        except Exception:
            pass
    if not all_cards:
        return []
    
    # Return random selection
    return random.sample(all_cards, min(count, len(all_cards)))


########################################
# DATA LOADING  AND HEIGHT CALCULATION #
########################################

# Execute functions and store results in variables
logo_img = get_logo(LOGO_URL, target_width = 160)
w        = get_weather(PREVIEW_MODE)
evs      = get_events(ICAL_URLS, target_date)
tasks    = get_tasks()
news     = get_news()
fact     = get_fact()
vocabs   = get_vocabs(OBSIDIAN_VAULT, count = 5)

# Calculate canvas height
# (1) Header
header_h = (logo_img.size[1] + 40 if logo_img else 0) + 150

# (2) Weather
weather_h = 480 if w else 0

# (3) Calendar
calendar_h = (len(evs) * 70 + 80) if evs else 125

# (4) Tasks
task_h = sum([55 if t['project'] else 40 for t in tasks]) + 100 if tasks else 0

# (5) News
news_h = sum(len(h) for h in news) * 32 + (len(news) * 15) + 100

# (6) Fact
fact_h = (len(fact) * 30 + 110) if fact else 0

# (7) Vocabs
vocabs_h = (len(vocabs) * 65 + 100) if vocab else 0

# Total height
total_h = header_h + weather_h + calendar_h + task_h + news_h + fact_h + vocabs_h + 200


###########
# DRAWING #
###########

# Create image with calculated height and white background
img = Image.new('L', (WIDTH, int(total_h)), 255)
draw = ImageDraw.Draw(img)

# Load system fonts or fall back to a default font
try:
    f_title = ImageFont.truetype("/Library/Fonts/Arial Bold.ttf", 40)
    f_bold  = ImageFont.truetype("/Library/Fonts/Arial Bold.ttf", 26)
    f_reg   = ImageFont.truetype("/Library/Fonts/Arial.ttf", 24)
    f_small = ImageFont.truetype("/Library/Fonts/Arial.ttf", 18)
    f_time  = ImageFont.truetype("/Library/Fonts/Arial.ttf", 20)
    f_mono  = ImageFont.truetype("/Library/Fonts/Constants/Courier.ttc", 16)
except:
    f_title = f_bold = f_reg = f_small = f_time = ImageFont.load_default()

# Set y_cursor and MARGIN
y_cursor = 20
MARGIN = 40

# (1) Header
if logo_img:
    
    # Center logo horizontally
    img.paste(logo_img, ((WIDTH - logo_img.size[0]) // 2, y_cursor))
    y_cursor += logo_img.size[1] + 20
    
    # Define pseudo logs
    logs = [
        "SYSTEM: initializing daily brief ...",
        "FETCH:  weather ... OK",
        f"FETCH:  events ... OK ({len(evs)} found)",
        f"FETCH:  tasks ... OK ({len(tasks)} found)",
        "FETCH:  news ... OK",
        "FETCH:  fact ... OK",
        "FETCH:  vocabularies ... OK",
        "STATUS: daily brief complete"
    ]
    
    # Draw pseudo logs
    for log in logs:
        draw.text((MARGIN, y_cursor), log, font = f_mono, fill = 0)
        y_cursor += 22
    
    # Draw divider line
    y_cursor += 15
    draw.line((MARGIN, y_cursor, WIDTH - MARGIN, y_cursor), fill = 0, width = 3)
    y_cursor += 35

# Draw weekday and date
days = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
draw.text((MARGIN, y_cursor), days[target_date.weekday()], font = f_title, fill = 0)
y_cursor += 50
draw.text((MARGIN, y_cursor), target_date.strftime('%d.%m.%Y'), font = f_reg, fill = 0)

# (2) Weather
if w:
    
    # Draw icon and midday temperature
    draw_weather_icon(draw, WIDTH - 110, y_cursor - 70, w['code'])
    draw.text((WIDTH - 70, y_cursor + 25), f"{w['temp']}°C", font = f_bold, fill = 0, anchor = "ms")
    
    # Draw temperature line graph
    gy, gw, gh = y_cursor + 90, 360, 80
    draw.text((MARGIN + 40, gy - 25), f"Temperatur • {w['abs_min']}°C – {w['abs_max']}°C", font = f_small, fill = 0)
    
    # Draw aid lines
    for t_line in [0, 20, 40]:
        if T_MIN <= t_line <= T_MAX:
            y_pos = gy + gh - ((t_line - T_MIN) / (T_MAX - T_MIN) * gh)
            for x_dash in range(MARGIN + 40, MARGIN + 40 + gw, 8):
                draw.line([x_dash, y_pos, x_dash + 4, y_pos], fill = 0, width = 1)
            draw.text((MARGIN + 35, y_pos), f"{t_line}°C", font = f_small, fill = 0, anchor = "rm")
    
    # Draw lines
    pts = []
    for i, t in enumerate(w['temps']):
        px = (MARGIN + 40) + (i * (gw / (len(w['temps']) - 1)))
        py = gy + gh - ((t - T_MIN) / (T_MAX - T_MIN) * gh)
        pts.append((px, py))
        draw.text((px, gy + gh + 5), f"{i * 3:02d}", font = f_small, fill = 0, anchor = "mt")
    draw.line(pts, fill = 0, width = 3)
    for p in pts: draw.ellipse([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3], fill = 0)
    
    # Draw rain bar chart
    ry = gy + 160
    draw.text((MARGIN + 40, ry - 25), f"Regen • {w['desc']}", font = f_small, fill = 0)
    
    # Draw aid lines
    for prob_line in [0, 50, 100]:
        y_pos = ry + gh - ((prob_line / 100) * gh)
        for x_dash in range(MARGIN + 40, MARGIN + 40 + gw, 8):
            draw.line([x_dash, y_pos, x_dash + 4, y_pos], fill = 0, width = 1)
        draw.text((MARGIN + 35, y_pos), f"{prob_line}%", font = f_small, fill = 0, anchor = "rm")
    
    # Draw bars
    for i, prob in enumerate(w['rain']):
        px = (MARGIN + 40) + (i * (gw / (len(w['rain']) - 1)))
        bar_h = (prob / 100) * gh
        if prob > 0:
            draw.rectangle([px - 8, ry + gh - bar_h, px + 8, ry + gh], fill = 0)
        draw.text((px, ry + gh + 5), f"{i * 3:02d}", font = f_small, fill = 0, anchor = "mt")
    y_cursor = ry + 130

# (3) Calendar
if evs:
    
    # Draw section header and divider line
    draw.line((MARGIN, y_cursor, WIDTH - MARGIN, y_cursor), fill = 0, width = 3)
    draw.text((MARGIN, y_cursor + 20), "TERMINE", font = f_bold, fill = 0)
    y_cursor += 65
    
    # Draw events
    for e in evs:
        time_str = f"{e['start'].strftime('%H:%M')}"
        draw.text((MARGIN, y_cursor), time_str, font = f_small, fill = 0)
        wrapped_summary = textwrap.wrap(e['summary'], width = 24)
        for i, line in enumerate(wrapped_summary):
            draw.text((MARGIN + 80, y_cursor - 4), line, font = f_bold, fill = 0)
            y_cursor += 32
        y_cursor += 15
    y_cursor += 20
else:
    
    # Draw section header and divider line
    draw.line((MARGIN, y_cursor, WIDTH - MARGIN, y_cursor), fill = 0, width = 3)
    draw.text((MARGIN, y_cursor + 20), "TERMINE", font = f_bold, fill = 0)
    y_cursor += 65
    
    # Draw fallback text
    draw.text((MARGIN, y_cursor), "• Heute keine Termine", font = f_reg, fill = 0)
    y_cursor += 45
    y_cursor += 20

# (4) Vocabs
if vocabs:
    
    # Draw section header and divider line
    draw.line((MARGIN, y_cursor, WIDTH - MARGIN, y_cursor), fill = 0, width = 3)
    draw.text((MARGIN, y_cursor + 20), "VOKABELN", font = f_bold, fill = 0)
    y_cursor += 65
    
    # Draw vocabularies
    for card in vocabs:
        
        # Draw original
        draw.text((MARGIN, y_cursor), f"• {card['front']}", font = f_bold, fill = 0)
        y_cursor += 30
        
        # Draw translation
        draw.text((MARGIN + 25, y_cursor), f"= {card['back']}", font = f_reg, fill = 0)
        y_cursor += 35
    
    # Add spacing
    y_cursor += 20

# (5) Tasks, (6) News, and (7) Fact
for title, data in [("AUFGABEN", tasks), ("NACHRICHTEN", news), ("WUSSTEST DU SCHON?", [fact] if fact else [])]:
    
    # Skip news and fact if empty
    if not data and title != "AUFGABEN":
        continue
    
    # Draw section header and divider line
    draw.line((MARGIN, y_cursor, WIDTH - MARGIN, y_cursor), fill = 0, width = 3)
    draw.text((MARGIN, y_cursor + 20), title, font = f_bold, fill = 0)
    y_cursor += 65
    
    if data:
        for item in data:
            
            # Draw tasks
            if title == "AUFGABEN":
                draw.rectangle([MARGIN, y_cursor, MARGIN + 20, y_cursor + 20], outline = 0, width = 2)
                wrapped_task = textwrap.wrap(item['name'], width = 30)
                for line in wrapped_task:
                    draw.text((MARGIN + 35, y_cursor - 2), line, font = f_reg, fill = 0)
                    y_cursor += 32
                if item['project']:
                    wrapped_project = textwrap.wrap(item['project'].upper(), width = 35)
                    for line in wrapped_project:
                        draw.text((MARGIN + 35, y_cursor - 6), line, font = f_small, fill = 0)
                        y_cursor += 24
                    y_cursor += 15
                else:
                    y_cursor += 10
            
            # Draw news and fact
            else:
                for i, line in enumerate(item):
                    draw.text((MARGIN, y_cursor), f"{'• ' if i == 0 else '  '}{line}", font = f_reg, fill = 0)
                    y_cursor += 30
                y_cursor += 10
    
    # Draw fallback text
    else:
        if title == "AUFGABEN":
            draw.text((MARGIN, y_cursor), "• Heute keine Aufgaben", font = f_reg, fill = 0)
            y_cursor += 45
    
    # Add spacing
    y_cursor += 20

# Convert image to 1-bit
final_img = img.convert('1')
# IPython.display.display(final_img)


############
# PRINTING #
############

# Set PRINTER_NAME and FILENAME
PRINTER_NAME = "Printer_POS_80"
FILENAME     = os.path.join(SCRIPT_DIR, "daily_brief.png")

# Save image
final_img.save(FILENAME)

# Print image
try:
    subprocess.run(["lp", "-d", PRINTER_NAME, "-o", "media=Custom.80x2000mm", FILENAME], check = True)
    print("Druck gesendet")
except Exception as e:
    print(f"Fehler beim Drucken: {e}")
