import streamlit as st
import requests
import base64
import urllib.parse
import os
from dotenv import load_dotenv

# ------------------------
# Config
# ------------------------
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

REDIRECT_URI = "http://127.0.0.1:8501/callback"  # must match Spotify dashboard
SCOPE = "playlist-read-private playlist-read-collaborative user-modify-playback-state user-read-playback-state"

# ------------------------
# OAuth helpers
# ------------------------
def build_auth_url():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
    }
    return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)

def exchange_code_for_token(code):
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
    )
    return r.json()

# ------------------------
# Spotify API
# ------------------------
def get_all_playlists(token):
    headers = {"Authorization": f"Bearer {token}"}
    url = "https://api.spotify.com/v1/me/playlists?limit=50"
    playlists = []
    while url:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            st.error(f"Failed to fetch playlists: {r.status_code} {r.text}")
            break
        data = r.json()
        playlists.extend(data.get("items", []))
        url = data.get("next")
    return playlists

# ------------------------
# Streamlit UI
# ------------------------
st.set_page_config(page_title="Spotify Playback App", layout="wide")
st.title("🎧 Personal Spotify Playback")

# --- OAuth ---
if "access_token" not in st.session_state:
    code = st.query_params.get("code")
    if code:
        code_val = code[0] if isinstance(code, list) else code
        token_data = exchange_code_for_token(code_val)
        if "access_token" in token_data:
            st.session_state["access_token"] = token_data["access_token"]
            st.session_state["refresh_token"] = token_data.get("refresh_token")
            st.success("Logged in!")
            # Remove code from URL
            st.markdown(
                """<script>
                   window.history.replaceState({}, document.title, "/");
                   </script>""",
                unsafe_allow_html=True,
            )
        else:
            st.error(f"Token exchange failed: {token_data}")
            st.stop()
    else:
        auth_url = build_auth_url()
        st.markdown(f"[➡️ Login with Spotify]({auth_url})")
        st.stop()

token = st.session_state["access_token"]

# --- Fetch playlists ---
if "playlists" not in st.session_state:
    with st.spinner("Fetching your playlists..."):
        st.session_state["playlists"] = get_all_playlists(token)

playlists = st.session_state["playlists"]
if not playlists:
    st.warning("No playlists found.")
    st.stop()

playlist_map = {p["name"]: p["uri"] for p in playlists}

# --- Playback UI ---
st.subheader("Select a playlist to play")
selected_playlist = st.selectbox("Your playlists", list(playlist_map.keys()))

if st.button("Play playlist on Spotify"):
    playlist_uri = playlist_map[selected_playlist]
    url = "https://api.spotify.com/v1/me/player/play"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"context_uri": playlist_uri}

    r = requests.put(url, headers=headers, json=data)
    if r.status_code == 204:
        st.success(f"Playback started: {selected_playlist}")
    elif r.status_code == 404:
        st.error("No active Spotify device found. Open Spotify on one of your devices.")
    else:
        st.error(f"Playback failed: {r.status_code} {r.text}")
