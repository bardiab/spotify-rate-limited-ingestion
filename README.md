# Spotify Rate Limited Ingestion 🎵✨🎶

## Objective:
Scrape all artists from the Spotify API as quickly as possible, while also designing
around Spotify's rate limit in order to compute as fast as possible.

## How to run: 
* Create Spotify developer account and [create an app](https://developer.spotify.com/dashboard/applications) 
* set `CLIENT_ID` and `CLIENT_SECRET` from spotify developer account in .env file
* Activate virtual environment `source venv/bin/activate`
* Install package dependencies `pip install -r requirements.txt`
* Run with `python3 main.py`

## Spotify API Notes:
* Spotify supports multiple authorization flows, and since this is a script that doesn't
need to communicate with end users, I chose to use the Client Credentials Flow. Another
advantage of this is that it allows us to obtain a higher rate limit compared to the 
Authorization Code flow.
* Since Spotify's rate limit is calculated based on the number of requests made in a rolling 30 
second window and they don't disclose how many requests are allowed in that window, I
figured we would at least need a backoff-retry strategy coupled with sleeping the script for 
a small period of time to provide some buffer before hitting a 429 error.

## Functions 
### get_auth_token
Grabs a Spotify access token with the client secret and client id which are both stored as
environment variables. Retries on failure.

### get_auth_header
Header variables for Spotify API requests

### get_data_from_spotify_api
Calls Spotify API and raises exceptions if our access token expired or we've hit the rate limit. 
Increments our global counter `requests_sent` and returns json data from endpoint. 
Retries on failure. 

### get_several_artists
Request data for 50 artists at a time from one endpoint call. If we haven't seen this artist yet,
then we add it to our dictionary storing all artists and print data for each artist.

### get_related_artists
Used to explore deeper from the artists we've already seen. Grabs 20 related artists, and if we
haven't explored from these artists already, adds them to our set `artist_ids_to_visit`. If we
haven't seen one of these related artists, add them to our dictionary and print data for each
new artist. 

### get_featured_playlists
Grabs playlist ids of top featured playlists from spotify.

### get_artist_ids_from_playlists
For each playlist id, grabs all tracks in that playlist. From that data we then extract
artist ids from each playlist. Returns a list of unique artist ids from playlists. 

## Script Overview
* There are three things we keep track of globally: 
  * `requests_sent` int - how many requests we've sent to Spotify API
  * `artists` dict - maps `artist_id` to data about that artist
  * `artist_ids_to_visit` set - keeps track of which artist ids we have yet to explore from
* To start, we used `get_featured_playlists` to get Spotify's featured playlists
and then from there we grabbed artists ids from tracks in those playlists.
* These initial ids are what we use to start the scraping process. However, we still need some more
info about each artist like genre, popularity, etc. so we used `get_several_artists` to batch 
get this artist info with as few requests as possible.
* With some IDs to start exploring, from each ID, we call `get_related_artists` which prints data
for each unique new artist we haven't seen before, and stores which artists we have yet to explore. We
keep looping as long as we have artists we haven't explored. 
* In order to not hit the rate limit, we use `requests_sent` to sleep the script for 30 seconds 
for every 1500 requests we send. 
  * I did a few rounds of estimation to come up with this number, and chose a more conservative sleep
  time to avoid hitting a 429 error.
* We catch two exceptions: 
  * If we hit the rate limit, we use a backoff-retry strategy where we wait the amount of seconds
  specified by the retry-after header variable sent in the 429 response. 
  * If our access token expires, we set a new one. 


## Things to improve: 
* Investigate if using [Spotipy](https://spotipy.readthedocs.io/en/2.21.0/), a python client for Spotify's api,
makes our script cleaner. I didn't use it at first in case I needed data the client could not provide. 
* With more time, I would expand on the backoff-retry logic and use a token bucket algorithm to 
monitor outgoing requests to ensure we don't violate a threshold. However, we would need to know the rate 
limit in order to maximize efficiency of using the algorithm. Since spotify doesn't provide an
exact number of requests allowed per 30-second window, additional experimentation is required in order
to estimate this number. Due to time constraints and rate limit constraints, I didn't pursue this option since
I couldn't run enough experiments to get an accurate estimation of what our rate limit is.
we wouldn't maximize efficiency from using the token bucket algorithm. 