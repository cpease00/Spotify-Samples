import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import json
from spotipy.util import prompt_for_user_token
from spotipy import util
from whosampled_scrape import *
from config import *

def call_api(username, scope='playlist-modify-public'):
    token = util.prompt_for_user_token(username, scope, client_id=client, client_secret=secret, redirect_uri='http://localhost:8889')
    return token

def make_description(spot_dict):
    unfound=spot_dict['unfound']
    rate=spot_dict['rate']
    summary = 'Samples Not on Spotify: {} \nPercentage of Samples Added: {}%'.format(unfound, round(rate, 3))
    return summary

def read_playlist(uri, sp, link=None):
    username = uri.split(':')[2]
    playlist_id = uri.split(':')[4]
    og_tracks = []
    results = sp.user_playlist(username, playlist_id)
    for i in results['tracks']['items']:
        artists = [j['name'] for j in i['track']['artists']]
        og_tracks.append({'artist' : artists, 'track':i['track']['name'].replace('Instrumental', '')})
    return og_tracks

def get_sample_data(uri, sp):
    loaded_playlist = read_playlist(uri, sp)
    new_playlist_tracks = get_whosampled_playlist(loaded_playlist)
    return new_playlist_tracks

def get_spotify_ids(whosampled_playlist, sp):
    id_list = []
    unfound_list= []
    for i in whosampled_playlist:
        sub_list = []
        artist = i['artist'].lower()
#         print('NEW SAMPLE: {} by {}'.format(i['title'], artist))
        result = sp.search(i['title'], limit=50)['tracks']['items']
        for j in result:
            if j['artists'][0]['name'].lower() == artist:
                sub_list.append(j['id'])
                break
        if sub_list:
#             print('FOUND ON SPOTIFY')
            id_list.append(sub_list[0])
        else:
#             print('NO ID FOUND FOR {} by {}'.format(i['title'], artist))
            unfound_list.append((i['title']+' by '+artist))
    location_rate=1 - len(unfound_list)/len(whosampled_playlist)
    return {'ids': id_list, 'unfound': unfound_list, 'rate': location_rate}

def create_and_populate(username, new_playlist_name, spotify_dict, sp):
    playlist = sp.user_playlist_create(username, new_playlist_name)
    newest_id = sp.user_playlists(username)['items'][0]['id'] #get ID of playlist just created
    sp.user_playlist_add_tracks(username, newest_id, spotify_dict['ids'], None) #populate playlist with all samples
    pass

def get_new_sample_playlist(uri, new_playlist_name, user):
    token = call_api(user, 'playlist-modify-public')
    sp2 = spotipy.Spotify(auth=token)
    new_playlist_tracks = get_sample_data(uri, sp2)
    print('\nChecking Spotify for Samples:\n')
    for i in new_playlist_tracks:
        print(i['title']+' by '+ i['artist'])
    spotify_dict = get_spotify_ids(new_playlist_tracks, sp2)
#     descript = make_description(spotify_dict)
    new_playlist = create_and_populate(user, new_playlist_name, spotify_dict, sp2)
    print('\nNew playlist "{}" created!'.format(new_playlist_name))
#     sp2.user_playlist_change_details(username, playlist_id, name=new_playlist_name, public=None, collaborative=None,description=description)
    pass

def run_program():
    uri = input('Please enter the Spotify URI of your playlist. \nThis can be found by clicking "Share" on your playlist and then selecting "Copy Spotify URI":\n')
    name = input('Please enter the name of your new sample playlist\n')
    username = uri.split(':')[2]
    playlist_id = uri.split(':')[4]
    get_new_sample_playlist(uri, name, username)
    pass

run_program()
