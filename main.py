import time
import json
from datetime import datetime
from typing import List

import requests
from retry import retry
from decouple import config
from base64 import b64encode

fmt = "%Y-%m-d %H:%M:%S"

SPOTIFY_CLIENT_ID = config('CLIENT_ID')
SPOTIFY_CLIENT_SECRET = config('CLIENT_SECRET')

AUTH_TOKEN = None

requests_sent = 0
artists = dict()
artist_ids_to_visit = set()


class SpotifyRateLimitError(Exception):
    pass


class SpotifyAccessTokenExpired(Exception):
    pass


@retry(delay=5, tries=2)
def get_auth_token():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise KeyError("Missing Spotify developer credentials")
    client_str = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode('ascii')
    client_str = b64encode(client_str)
    client_str = client_str.decode('ascii')
    headers = {
        'Authorization': f"Basic {client_str}"
    }
    data = {
        "grant_type": "client_credentials",
    }
    req = requests.post(
        "https://accounts.spotify.com/api/token",
        headers=headers,
        data=data
    )
    global requests_sent
    requests_sent += 1
    content = req.content.decode('ascii')
    json_data = json.loads(content)
    access_token = json_data['access_token']
    return access_token


def get_auth_header():
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    global AUTH_TOKEN
    if not AUTH_TOKEN:
        AUTH_TOKEN = get_auth_token()
    headers["Authorization"] = f"Bearer {AUTH_TOKEN}"

    return headers


@retry(delay=5, tries=2)
def get_data_from_spotify_api(url):
    headers = get_auth_header()

    req = requests.get(url, headers=headers)
    global requests_sent
    requests_sent += 1
    if req.status_code == 429:
        wait = req.headers['retry-after']
        raise SpotifyRateLimitError(f"Rate limit hit, retry-after:{wait}")
    if req.status_code == 401:
        raise SpotifyAccessTokenExpired(f"Refreshing access token")

    json_data = json.loads(req.content)
    return json_data


def get_several_artists(a_ids):
    artist_ids_str = ','.join(a_ids)
    # ids must be value separated string ex: 434,234,243,423
    url = f'https://api.spotify.com/v1/artists/?ids={artist_ids_str}'
    json_data = get_data_from_spotify_api(url)

    global artists
    for artist in json_data['artists']:
        a_id = artist.get('id')
        if a_id not in artists:
            artists[a_id] = {
                "id": artist.get('id'),
                "name": artist.get('name'),
                "genres": artist.get('genres'),
                "popularity": artist.get('popularity'),
            }
            print(artists[a_id])


def get_related_artists(artist_id: str):
    # Note - this returns max 20 artists at a time
    url = f'https://api.spotify.com/v1/artists/{artist_id}/related-artists'
    json_data = get_data_from_spotify_api(url)

    global artists
    for artist in json_data['artists']:
        a_id = artist.get('id')

        if a_id not in artists:
            artist_ids_to_visit.add(a_id)
            artists[a_id] = {
                "id": artist.get('id'),
                "name": artist.get('name'),
                "genres": artist.get('genres'),
                "popularity": artist.get('popularity'),
            }
            print(artists[a_id])


def get_featured_playlists():
    url = f'https://api.spotify.com/v1/browse/featured-playlists/?limit=50'
    json_data = get_data_from_spotify_api(url)

    playlists = json_data.get('playlists').get('items')
    pl_ids = set()
    for p in playlists:
        playlist_id = p.get('id')
        pl_ids.add(playlist_id)

    return pl_ids


def get_artist_ids_from_playlists(pl_ids) -> List[str]:
    a_ids = set()
    for p_id in pl_ids:
        url = f'https://api.spotify.com/v1/playlists/{p_id}/tracks'
        json_data = get_data_from_spotify_api(url)
        if json_data:
            playlist_data = json_data.get('items')
            for tr in playlist_data:
                track = tr.get('track')
                if track:
                    track_artists = track.get('artists')
                    for artist in track_artists:
                        artist_id = artist.get('id')
                        a_ids.add(artist_id)

    return list(a_ids)


if __name__ == '__main__':
    start = time.strftime(fmt)

    playlist_ids = get_featured_playlists()
    initial_ids = get_artist_ids_from_playlists(pl_ids=list(playlist_ids))

    print(f"{len(initial_ids)} initial artists to start exploring from")
    artist_ids_to_visit.update(initial_ids)

    while artist_ids_to_visit:
        try:
            while initial_ids:
                get_several_artists(a_ids=initial_ids[:50])
                initial_ids = initial_ids[50:]

            if requests_sent % 1500 == 0:
                current_time = time.strftime(fmt)
                print("~~ Delaying 30 seconds ~~")
                print(datetime.strptime(current_time, fmt)
                      - datetime.strptime(start, fmt), f'time elapsed')
                print(f"Requests sent: {requests_sent}")
                print(f'Artist total - ', len(artists))
                time.sleep(30)

            next_id = artist_ids_to_visit.pop()
            get_related_artists(artist_id=next_id)

        except SpotifyRateLimitError as e:
            wait_time = e.args[0].split(':')[1]
            print(f"Spotify Rate Limit hit, sleeping for {wait_time} seconds")
            time.sleep(int(wait_time))
        except SpotifyAccessTokenExpired:
            print("Refreshing access token")
            AUTH_TOKEN = get_auth_token()
