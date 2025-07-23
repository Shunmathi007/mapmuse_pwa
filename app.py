import streamlit as st
import json
import folium
from streamlit_folium import st_folium
import requests

# Load mood data
with open("assets/moods.json", "r", encoding="utf-8") as f:
    mood_data = json.load(f)

# Session state init
if "question_index" not in st.session_state:
    st.session_state.question_index = 0
if "mood_answers" not in st.session_state:
    st.session_state.mood_answers = []
if "user_details" not in st.session_state:
    st.session_state.user_details = {}
if "mood" not in st.session_state:
    st.session_state.mood = None

def splash_screen():
    st.markdown("## 🧭 MapMuse\nLet your feelings guide your food")

def list_all_cities():
    cities = set()
    for mood in mood_data.values():
        cities.update(mood.get("places", {}).keys())
    return sorted(cities)

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

def mood_quiz():
    questions = [
        ("How does your energy feel today?", ["Relaxed", "Energized", "Sluggish", "Restless"]),
        ("Which emotion fits your vibe?", ["Content", "Curious", "Tired", "Playful"]),
        ("What are you craving?", ["Comfort", "Spice", "Sweetness", "Excitement"]),
        ("Your ideal company right now is...", ["Alone", "Friends", "Partner", "Crowd"]),
        ("What's your mental clarity like?", ["Foggy", "Focused", "Inspired", "Scattered"]),
        ("What's your weather mood?", ["Cloudy", "Sunny", "Windy", "Drizzling"])
    ]

    q_index = st.session_state.question_index
    if q_index < len(questions):
        q_text, options = questions[q_index]
        st.markdown(f"*Q{q_index+1}: {q_text}*")
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

def classify_mood(answers):
    score = {mood: 0 for mood in mood_data.keys()}
    for answer in answers:
        answer = answer.lower().strip()
        for mood, info in mood_data.items():
            cues = [c.lower() for c in info.get("cues", [])]
            for cue in cues:
                if answer == cue:
                    score[mood] += 1
                elif answer in cue or cue in answer:
                    score[mood] += 0.5
    return max(score, key=score.get)

def show_mood_result(mood):
    info = mood_data[mood]
    name = st.session_state.user_details["name"]
    city = st.session_state.user_details["city"]
    cuisine = ", ".join(info.get("cuisine_tags", [])[:2])
    spot = info.get("places", {}).get(city, [{}])[0].get("name", "a cozy spot")
    st.markdown(f"### 👋 Hi {name}!")
    st.markdown(f"You’re feeling *{mood}* {info['icon']} and might be craving {cuisine}.")
    st.markdown(f"In *{city}, you should check out 🗺 **{spot}*")
    st.markdown("---")

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
        st.info("No curated places found for this mood.")

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
    matches = []
    for el in elements:
        tags_dict = el.get("tags", {})
        name = tags_dict.get("name", "")
        cuisine = tags_dict.get("cuisine", "")
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if not name or not lat or not lon:
            continue
        if any(tag in cuisine.lower() for tag in tags):
            matches.append((name, cuisine, lat, lon))
    st.subheader("🍛 Recommended Restaurants")
    if matches:
        for name, cuisine, lat, lon in matches[:5]:
            link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}"
            st.markdown(f"- *{name}* ({cuisine}) → [View ↗]({link})")
    else:
        st.info("No matching restaurants found. Try exploring nearby hotspots!")

# App Runner
splash_screen()
if user_intro():
    mood_quiz()
