import streamlit as st
import json
import folium
from streamlit_folium import st_folium
import requests

# Load mood data
with open("assets/moods.json", "r", encoding="utf-8") as f:
    mood_data = json.load(f)

# Initialize session state
if "question_index" not in st.session_state:
    st.session_state.question_index = 0
if "mood_answers" not in st.session_state:
    st.session_state.mood_answers = []
if "user_details" not in st.session_state:
    st.session_state.user_details = {}
if "mood" not in st.session_state:
    st.session_state.mood = None

# Splash screen
def splash_screen():
    st.markdown("""
    <div style='text-align:center;'>
        <h1>🧭 MapMuse</h1>
        <p style='font-size:18px;'>Let your feelings guide your food</p>
    </div>
    """, unsafe_allow_html=True)

# Get all cities
def list_all_cities():
    cities = set()
    for mood in mood_data.values():
        cities.update(mood.get("places", {}).keys())
    return sorted(cities)

# User form with reset logic
def user_intro():
    name = st.text_input("Your name")
    city = st.selectbox("Select your city", list_all_cities())

    prev = st.session_state.user_details
    if name and city:
        if name != prev.get("name") or city != prev.get("city"):
            st.session_state.user_details = {"name": name, "city": city}
            st.session_state.question_index = 0
            st.session_state.mood_answers = []
            st.session_state.mood = None
        return True
    return False

# Mood quiz (one question at a time)
def mood_quiz():
    st.subheader("🧠 How are you feeling today?")

    questions = [
        ("What's been weighing on your mind?", ["Deadlines", "Relationships", "Uncertainty", "Nothing much"]),
        ("Which word resonates most?", ["Overwhelmed", "Curious", "Content", "Restless"]),
        ("Your physical energy feels...", ["Tense", "Energized", "Relaxed", "Sluggish"]),
        ("Given a day off, you'd rather...", ["Stay in bed", "Take a walk", "Meet friends", "Try something new"]),
        ("Your mental clarity is...", ["Foggy", "Focused", "Distracted", "Inspired"]),
        ("Socially, you're feeling...", ["Withdrawn", "Exploratory", "Chatty", "Creative"]),
        ("You crave...", ["Comfort", "Excitement", "Belonging", "Sweetness"]),
        ("Your thoughts are...", ["Heavy", "Expansive", "Scattered", "Vivid"]),
        ("If emotions were weather...", ["Cloudy", "Windy", "Sunny", "Drizzling"]),
        ("You secretly wish for...", ["Stillness", "Adventure", "Connection", "Indulgence"])
    ]

    q_index = st.session_state.question_index
    if q_index < len(questions):
        q_text, options = questions[q_index]
        st.markdown(f"**Q{q_index+1}: {q_text}**")
        answer = st.radio("Choose one:", options, key=q_index)
        if st.button("Next"):
            st.session_state.mood_answers.append(answer)
            st.session_state.question_index += 1
    else:
        mood = classify_mood(st.session_state.mood_answers)
        st.session_state.mood = mood
        show_mood_result(mood)
        show_map(mood)
        show_restaurants(mood)

# Classify mood
def classify_mood(answers):
    score = {mood: 0 for mood in mood_data.keys()}
    for answer in answers:
        for mood, info in mood_data.items():
            if answer.lower() in " ".join(info.get("cues", [])).lower():
                score[mood] += 1
    return max(score, key=score.get)

# Personalized mood summary
def show_mood_result(mood):
    info = mood_data[mood]
    name = st.session_state.user_details["name"]
    city = st.session_state.user_details["city"]
    cuisine = ", ".join(info.get("cuisine_tags", [])[:2])
    spot = info.get("places", {}).get(city, [{}])[0].get("name", "a vibe-friendly place")

    st.markdown(f"### 👋 Hi {name}!")
    st.markdown(f"You're feeling **{mood}** {info['icon']} and seem to be craving `{cuisine}`.")
    st.markdown(f"In **{city}**, here's a place that matches your mood: 🗺️ **{spot}**")
    st.markdown("---")

# Map rendering
def show_map(mood):
    city = st.session_state.user_details["city"]
    places = mood_data[mood].get("places", {}).get(city, [])
    if places:
        folium_map = folium.Map(location=[places[0]["lat"], places[0]["lon"]], zoom_start=13)
        for p in places:
            folium.Marker([p["lat"], p["lon"]], tooltip=p["name"], popup=mood).add_to(folium_map)
        st.subheader("📍 Vibe-Matched Spot")
        st_folium(folium_map, width=700)
    else:
        st.info("No curated places found for your mood in this city.")

# Restaurant results from Overpass
def show_restaurants(mood):
    city = st.session_state.user_details["city"]
    tags = mood_data[mood].get("cuisine_tags", [])

    query = f"""
    [out:json][timeout:25];
    area["name"="{city}"]->.searchArea;
    (
      node["amenity"="restaurant"](area.searchArea);
      way["amenity"="restaurant"](area.searchArea);
    );
    out center;
    """
    response = requests.post("https://overpass-api.de/api/interpreter", data={"data": query})
    if response.status_code != 200:
        st.error("Could not fetch restaurant data.")
        return

    elements = response.json().get("elements", [])
    matches, fallback = [], []
    for el in elements:
        tags_dict = el.get("tags", {})
        name = tags_dict.get("name", "")
        cuisine = tags_dict.get("cuisine", "")
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if not name or not lat or not lon:
            continue
        rating = (len(name) % 5) + 1
        if any(tag in cuisine.lower() for tag in tags) or any(tag in name.lower() for tag in tags):
            matches.append((name, cuisine, lat, lon, rating))
        elif any(k in cuisine.lower() for k in ["biryani", "chettinad", "veg", "south_indian"]):
            fallback.append((name, cuisine, lat, lon, rating))

    if matches:
        st.subheader("🍛 Mood-Matched Restaurants")
        for name, cuisine, lat, lon, rating in sorted(matches, key=lambda x: x[4], reverse=True)[:10]:
            link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}"
            st.markdown(f"- **{name}** ({cuisine}) — {rating}⭐ → [View ↗]({link})")
    elif fallback:
        st.warning("No exact mood match. Here are popular alternatives:")
        for name, cuisine, lat, lon, rating in fallback[:5]:
            link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}"
            st.markdown(f"- **{name}** ({cuisine}) — {rating}⭐ → [View ↗]({link})")
    else:
        st.info("No restaurants found nearby. Try changing city or mood.")

# Run the app
splash_screen()
if user_intro():
    mood_quiz()