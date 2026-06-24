import streamlit as st
import requests
import base64
import urllib.parse
import os
import pandas as pd
from dotenv import load_dotenv

print("Running new app.py")

# --- Config ---
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:8501/callback"
SCOPE = (
    "playlist-read-private playlist-read-collaborative "
    "user-modify-playback-state user-read-playback-state"
)

# --- OAuth helpers ---
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

# --- Spotify API ---
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

def get_tracks_for_playlist(token, playlist_id):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?fields=items(track(id,name,uri)),next&limit=100"
    tracks = []
    while url:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            st.error(f"Failed to fetch tracks: {r.status_code} {r.text}")
            break
        data = r.json()
        for item in data.get("items", []):
            track = item.get("track")
            if track:
                tracks.append({"id": track.get("id"), "name": track.get("name"), "uri": track.get("uri")})
        url = data.get("next")
    return tracks

def play_uri(token, uri):
    url = "https://api.spotify.com/v1/me/player/play"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"uris": [uri]} if "track" in uri else {"context_uri": uri}
    r = requests.put(url, headers=headers, json=data)
    return r.status_code, r.text

st.session_state.clear()
# --- Streamlit UI ---
st.set_page_config(page_title="Spotify Playlist Explorer", layout="wide")
st.title("🎧 Spotify Playlist Explorer")

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
            # clear the URL using the new API
            st.query_params = {}
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

# --- Display all playlists in a DataFrame ---
playlist_data = [{"Name": p["name"], "Track Count": p["tracks"]["total"], "URI": p["uri"]} for p in playlists]
df_playlists = pd.DataFrame(playlist_data).sort_values("Track Count", ascending=False)
st.subheader("Your Playlists")
st.dataframe(
    df_playlists[["Name","Track Count"]],
    width="stretch",  # replaced deprecated use_container_width
)


# --- Select a playlist to explore tracks ---
selected_playlist_name = st.selectbox("Select a playlist to fetch tracks", df_playlists["Name"].tolist())
selected_playlist_uri = df_playlists.loc[df_playlists["Name"] == selected_playlist_name, "URI"].values[0]
selected_playlist_id = selected_playlist_uri.split(":")[-1]

# --- Fetch tracks for selected playlist only ---
if "tracks_cache" not in st.session_state:
    st.session_state["tracks_cache"] = {}

if selected_playlist_id not in st.session_state["tracks_cache"]:
    with st.spinner(f"Fetching tracks for {selected_playlist_name}..."):
        st.session_state["tracks_cache"][selected_playlist_id] = get_tracks_for_playlist(token, selected_playlist_id)

tracks = st.session_state["tracks_cache"][selected_playlist_id]

# --- Display tracks DataFrame ---
if tracks:
    st.subheader(f"Tracks in {selected_playlist_name}")
    df_tracks = pd.DataFrame(tracks)[["name","id","uri"]].rename(columns={"name":"Track Name","id":"Track ID"})
    st.dataframe(
        df_tracks,
        width="stretch",  # replaced deprecated use_container_width
    )

    # --- Play buttons per track ---
    st.subheader("▶️ Play Individual Tracks")
    for idx, row in df_tracks.iterrows():
        cols = st.columns([4,1])
        cols[0].write(row["Track Name"])
        unique_key = f"{row['Track ID']}_{idx}"
        if cols[1].button("Play", key=unique_key):
            status, text = play_uri(token, row["uri"])
            if status == 204:
                st.success(f"Playing: {row['Track Name']}")
            elif status == 404:
                st.error("No active Spotify device found.")
            else:
                st.error(f"Playback failed: {status} {text}")
