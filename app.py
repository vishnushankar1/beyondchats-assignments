import streamlit as st
import os, sys
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import praw
from langchain_groq import ChatGroq
from langchain.callbacks import StreamlitCallbackHandler

# UTF-8 encoding
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding='utf-8')

# Load .env
load_dotenv()

# PRAW Reddit Scraper
def fetch_reddit_data(username):
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")

    if not client_id or not client_secret:
        return [], [], "❌ Missing Reddit API credentials."

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent="reddit_persona_app"
    )

    try:
        user = reddit.redditor(username)
        _ = user.created_utc  # test if user exists
    except Exception as e:
        return [], [], f"❌ Error: {str(e)}"

    posts, comments = [], []

    try:
        for submission in user.submissions.new(limit=50):
            if submission.selftext:
                posts.append(f"{submission.title}\n{submission.selftext}")

        for comment in user.comments.new(limit=50):
            if len(comment.body) > 10:
                comments.append(comment.body)
    except Exception as e:
        return [], [], f"❌ Error fetching posts/comments: {str(e)}"

    return posts, comments, None

import re

def extract_username_from_url(url_or_username):
    """
    Extract the Reddit username from a full URL or just return the username.
    Supports formats like:
    - https://www.reddit.com/user/username/
    - https://reddit.com/u/username/
    - u/username
    - username
    """
    # Patterns to match known URL formats
    patterns = [
        r'reddit\.com/user/([^/]+)',
        r'reddit\.com/u/([^/]+)',
        r'u/([^/]+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_username, re.IGNORECASE)
        if match:
            return match.group(1)

    # If none of the patterns matched, assume it's already a username
    return url_or_username.strip().replace('/', '')

# Prompt Builder
def build_prompt(posts, comments, username):
    text = "\n\n".join([f"POST: {p}" for p in posts] + [f"COMMENT: {c}" for c in comments])

    return f"""
You are a behavioral analyst. Analyze the following Reddit user activity and generate a detailed user persona.

🧠 Please follow this **strict formatting rule**:
- Each section title (e.g., Name, Age) must be on a separate line.
- The explanation or content should start **from the next line**, not on the same line.
- Use markdown formatting: headings like `**Name:**` followed by the answer on the next line.
- Do not combine title and content in one line.

🎯 Example Format:
**Name:**
Koji Ed (derived from the username “kojied”)

**Estimated Age:**
Late 20s to early 30s

**Occupation:**
Software Developer / Entrepreneur

**Location:**
New York City, USA

...and so on for all sections.

🧩 Sections to include:
- Name  
- Estimated Age  
- Occupation  
- Location  
- Personality Traits (MBTI)  
- Archetype (Explorer, Creator, etc.)  
- Digital Behavior (posting habits, subreddits)  
- Motivations  
- Frustrations  
- Quotes or phrases that support each insight

Reddit user: u/{username}

Reddit Activity:
{text}
"""

from PIL import Image, ImageDraw, ImageFont
import textwrap
import re

def persona_text_to_image(text, filename="persona_output.png"):
    try:
        # Setup canvas
        img_width, img_height = 1400, 3000
        margin = 60
        spacing = 40
        section_padding = 30
        background_color = (255, 255, 255)
        box_fill = (245, 245, 245)
        border_color = (200, 200, 200)
        header_color = (255, 102, 0)  # orange

        img = Image.new("RGB", (img_width, img_height), background_color)
        draw = ImageDraw.Draw(img)

        try:
            header_font = ImageFont.truetype("arialbd.ttf", 26)
            body_font = ImageFont.truetype("arial.ttf", 22)
        except:
            header_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        y = margin
        lines = text.split("\n")

        section_title = ""
        section_content = []

        def wrap_text_lines(content_lines, font, max_width):
            wrapped_lines = []
            for line in content_lines:
                if not line.strip():
                    continue
                wrapped_lines += textwrap.wrap(line, width=95)
            return wrapped_lines

        def render_section(title, content_lines):
            nonlocal y
            wrapped_lines = wrap_text_lines(content_lines, body_font, img_width - 2 * margin)
            total_height = (len(wrapped_lines) * 32) + section_padding * 2 + 30

            # Draw box
            draw.rectangle(
                [margin, y, img_width - margin, y + total_height],
                fill=box_fill,
                outline=border_color,
                width=2
            )

            # Draw header
            draw.text((margin + 20, y + section_padding - 10), title, font=header_font, fill=header_color)

            # Draw content
            text_y = y + section_padding + 25
            for wline in wrapped_lines:
                draw.text((margin + 20, text_y), wline, font=body_font, fill=(0, 0, 0))
                text_y += 32

            y += total_height + spacing

        for line in lines:
            if re.match(r"^\*\*(.+)\*\*$", line.strip()):
                # Draw previous section
                if section_title:
                    render_section(section_title, section_content)
                section_title = re.sub(r"\*\*(.+?)\*\*", r"\1", line.strip())
                section_content = []
            else:
                section_content.append(line)

        if section_title and section_content:
            render_section(section_title, section_content)

        img = img.crop((0, 0, img_width, y + 40))  # Crop unused bottom
        img.save(filename)
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False





# UI
st.set_page_config(page_title="Reddit User Persona", layout="wide")
st.title("🧠 Reddit User Persona Generator")

api_key = st.sidebar.text_input("🔐 Enter Groq API Key", type="password")

user_input = st.text_input("Enter Reddit username or profile URL:", 
                          placeholder="e.g., kojied or https://www.reddit.com/user/kojied/")

if st.button("Generate Persona") and user_input and api_key:
    with st.spinner("Fetching Reddit data..."):
        username = extract_username_from_url(user_input)
        posts, comments, error = fetch_reddit_data(username)

    if error:
        st.error(error)
    elif not posts and not comments:
        st.warning("❌ No activity found.")
    else:
        with st.spinner("Generating persona..."):
            llm = ChatGroq(
                model="llama3-70b-8192",
                groq_api_key=api_key,
                streaming=True
            )
            prompt = build_prompt(posts, comments, username)
            callback = StreamlitCallbackHandler(st.container())
            response = llm.invoke(prompt, config={"callbacks": [callback]})
            result = response.content

            # Show text
            st.subheader("📝 Persona Result")
            st.text_area("Persona", value=result, height=500)

            # Save Image
            persona_text_to_image(result)
            st.subheader("🖼️ Persona Image")
            st.image("persona_output.png")

            # Downloads
            st.download_button("📄 Download Text", data=result, file_name=f"persona_{username}.txt")
            st.download_button("🖼️ Download Image", data=open("persona_output.png", "rb"),
                               file_name=f"persona_{username}.png")
