import streamlit as st
import requests
import base64
import urllib.parse
import os
from dotenv import load_dotenv
load_dotenv()

# ==== CONFIG ====
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:8501"
SCOPE = "playlist-read-private playlist-read-collaborative"


# ==== FUNCTIONS ====

def build_auth_url():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE
    }
    return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)


def exchange_code_for_token(code: str):
    url = "https://accounts.spotify.com/api/token"

    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }

    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    r = requests.post(url, data=data, headers=headers)
    return r.json()

def get_all_playlists(access_token):
    url = "https://api.spotify.com/v1/me/playlists"
    headers = {"Authorization": f"Bearer {access_token}"}

    playlists = []
    while url:
        r = requests.get(url, headers=headers)
        data = r.json()

        playlists.extend(data.get("items", []))
        url = data.get("next")  # follow pagination

    return playlists


def get_user_playlists(access_token):
    url = "https://api.spotify.com/v1/me/playlists"
    headers = {"Authorization": f"Bearer {access_token}"}

    r = requests.get(url, headers=headers)
    return r.json().get("items", [])

def get_all_tracks(access_token, playlist_id):
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {"Authorization": f"Bearer {access_token}"}

    tracks = []
    while url:
        r = requests.get(url, headers=headers)
        data = r.json()

        tracks.extend(data.get("items", []))
        url = data.get("next")

    return tracks


# ==== STREAMLIT UI ====

st.title("🎧 Spotify OAuth Demo")

# Check if Spotify redirected back with ?code=
query_params = st.query_params
auth_code = query_params.get("code", None)

# If we received a code, exchange for token
if auth_code and "access_token" not in st.session_state:
    token_data = exchange_code_for_token(auth_code)
    st.session_state["access_token"] = token_data.get("access_token")
    st.session_state["refresh_token"] = token_data.get("refresh_token")

# If we have no token yet: show login button
if "access_token" not in st.session_state:
    auth_url = build_auth_url()
    st.markdown(f"[➡️ Login with Spotify]({auth_url})")
    st.stop()

# If we DO have a token:
st.success("Logged in with Spotify!")

# Fetch playlists
playlists = get_user_playlists(st.session_state["access_token"])

st.header("Your Playlists")

for p in playlists:
    st.write(f"- **{p['name']}**")