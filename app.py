import streamlit as st
import requests
import base64
import urllib.parse
import pandas as pd
import os
from dotenv import load_dotenv
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import webbrowser
import queue
from concurrent.futures import ThreadPoolExecutor

# ======================
# Config
# ======================
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "playlist-read-private playlist-read-collaborative"

# ======================
# OAuth helpers
# ======================
def build_auth_url():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
    }
    return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)

def exchange_code_for_token(code: str):
    auth_header = base64.b64encode(
        f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
    ).decode()

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

# ======================
# Spotify API helpers
# ======================
@st.cache_data(ttl=3600)
def fetch_playlists(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    url = "https://api.spotify.com/v1/me/playlists?limit=50"

    playlists = []
    while url:
        r = requests.get(url, headers=headers)
        data = r.json()
        playlists.extend(data.get("items", []))
        url = data.get("next")

    return playlists

@st.cache_data(ttl=3600)
def fetch_tracks(access_token, playlist_id):
    headers = {"Authorization": f"Bearer {access_token}"}
    url = (
        f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        "?limit=100&fields=items(track(id,name,artists(name),album(name))),next"
    )

    rows = []
    while url:
        r = requests.get(url, headers=headers)
        data = r.json()

        for item in data.get("items", []):
            track = item.get("track")
            if not track:
                continue

            rows.append(
                {
                    "track_id": track["id"],
                    "track_name": track["name"],
                    "artist": ", ".join(a["name"] for a in track["artists"]),
                    "album": track["album"]["name"],
                }
            )

        url = data.get("next")

    return rows

# ======================
# OAuth loopback server
# ======================
code_queue = queue.Queue()

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            code_queue.put(params["code"][0])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"You may close this window.")
        else:
            self.send_response(400)
            self.end_headers()

def start_server():
    HTTPServer(("127.0.0.1", 8888), OAuthHandler).handle_request()

# ======================
# Streamlit UI
# ======================
st.set_page_config(page_title="Spotify Playlist Explorer", layout="wide")
st.title("🎧 Spotify Playlist Explorer")

# ---- Auth stage ----
if "access_token" not in st.session_state:
    if st.button("Login with Spotify"):
        threading.Thread(target=start_server, daemon=True).start()
        webbrowser.open(build_auth_url())

        with st.spinner("Waiting for Spotify authorization..."):
            code = code_queue.get()

        token = exchange_code_for_token(code)
        st.session_state["access_token"] = token["access_token"]

st.stop() if "access_token" not in st.session_state else None

access_token = st.session_state["access_token"]

# ---- Playlists stage ----
playlists = fetch_playlists(access_token)

playlist_df = pd.DataFrame(
    [
        {
            "playlist": p["name"],
            "playlist_id": p["id"],
            "tracks": p["tracks"]["total"],
            "owner": p["owner"]["display_name"],
        }
        for p in playlists
    ]
).sort_values("tracks", ascending=False)

st.subheader("Your playlists")

selected = st.data_editor(
    playlist_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "playlist_id": None,
    },
)

# ---- Fetch tracks stage ----
if st.button("Fetch songs for selected playlists"):
    selected_ids = selected["playlist_id"].tolist()

    if not selected_ids:
        st.warning("Select at least one playlist.")
        st.stop()

    rows = []

    with st.spinner("Fetching songs..."):
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(fetch_tracks, access_token, pid): pid
                for pid in selected_ids
            }

            for future in futures:
                pid = futures[future]
                playlist_name = playlist_df.loc[
                    playlist_df["playlist_id"] == pid, "playlist"
                ].values[0]

                for row in future.result():
                    row["playlist"] = playlist_name
                    rows.append(row)

    tracks_df = pd.DataFrame(rows)

    st.subheader("Songs")
    st.dataframe(
        tracks_df.sort_values(["playlist", "track_name"]),
        use_container_width=True,
    )
