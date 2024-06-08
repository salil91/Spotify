"""
Usage: new_tracks.py [OPTIONS]

  Find new tracks from artists in the list. If the list is not provided, search
  for artists in the specified genre. The list must be provided in a CSV file
  with the first column containing the artist names and the second column
  containing the artist IDs.

Options:
  -s, --spotify_client FILE  YAML file with Spotify API client ID, secret, and
                             redirect URI.  [required]
  -g, --genre TEXT           Search for artists in this genre. Search is only
                             performed if artists CSV file is not
                             provided/found. Otherwise, it is only used in
                             naming the playlist.  [required]
  -a, --artists FILE         CSV file with artist names and IDs.
  -d, --days INTEGER         Number of days to search back for new tracks. If
                             0, search for tracks released after the previous
                             Friday.  [default: 0]
  --help                     Show this message and exit.
"""

import click
import csv
from datetime import datetime, timedelta
import logging
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from tqdm import tqdm
import yaml


@click.command()
@click.option(
    "--spotify_client",
    "-s",
    help="YAML file with Spotify API client ID, secret, and redirect URI.",
    default="./spotify.yaml",
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, resolve_path=True, path_type=Path
    ),
    required=True,
)
@click.option(
    "--genre",
    "-g",
    default=None,
    required=True,
    help="Search for artists in this genre. Search is only performed if artists CSV file is not provided/found. Otherwise, it is only used in naming the playlist.",
)
@click.option(
    "--artists",
    "-a",
    help="CSV file with artist names and IDs.",
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, resolve_path=True, path_type=Path
    ),
)
@click.option(
    "--days",
    "-d",
    default=0,
    show_default=True,
    help="Number of days to search back for new tracks. If 0, search for tracks released after the previous Friday.",
)
def main(spotify_client, genre, artists, days):
    """
    Find new tracks from artists in the list. If the list is not provided, search for artists in the specified genre.
    The list must be provided in a CSV file with the first column containing the artist names and the second column containing the artist IDs.
    """
    # Set up logging
    script_name = Path(__file__).stem
    log_path = f"{script_name}.log"
    Path(log_path).unlink(missing_ok=True)
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        filename=log_path,
        filemode="w",
        level=logging.INFO,
    )

    # Configure Spotipy
    logging.info("Reading Spotify parameters")
    with open(spotify_client, "r") as f:
        params = yaml.safe_load(f)
    scope = "user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public"
    logging.info("Initiating Spotify Client")
    auth_manager = SpotifyOAuth(
        client_id=params["client_id"],
        client_secret=params["client_secret"],
        redirect_uri=params["redirect_uri"],
        scope=scope,
    )
    sp = spotipy.Spotify(auth_manager=auth_manager)

    # Load artists
    if artists:
        try:
            logging.info(f"Reading list of artists from {artists.resolve()}")
            with open(artists, "r") as f:
                reader = csv.reader(f)
                artists = list(reader)
            logging.info(f"Done. {len(artists)} in list.")
        except FileNotFoundError:
            logging.error("Error reading artists file!")
            artists = get_artists(sp, genre)
    else:
        artists = get_artists(sp, genre)

    # Get new tracks
    today = datetime.today().date()
    if days == 0:
        days = ((today.weekday() - 4) % 7) + 7  # Days since second to last Friday
    threshold_date = today - timedelta(days=days)
    logging.info(f"Threshold date - {threshold_date}")
    new_tracks = get_new_tracks(sp, artists, threshold_date)
    track_ids = [track["id"] for track in new_tracks]
    track_ids = list(set(track_ids))  # Remove duplicates
    logging.info(f"Found {len(new_tracks)} new tracks.")

    # Save new tracks to CSV
    playlist_name = f"Automated New {genre.title()}: {threshold_date.month:2d}-{threshold_date.day:02d} to {today.month:2d}-{today.day:02d}"
    playlist_csv = Path.cwd() / f"{playlist_name}.csv"
    with open(playlist_csv, "w", newline="") as f:
        dict_writer = csv.DictWriter(f, new_tracks[0].keys())
        dict_writer.writeheader()
        dict_writer.writerows(new_tracks)

    logging.info(f"Track list saved to {playlist_csv.resolve()}")

    # Update playlist
    if "playlist_id" not in params:
        logging.error("No playlist ID provided!")
        return

    if len(new_tracks) == 0:
        logging.info("No new tracks found. Playlist not updated.")
    else:
        playlist_id = params["playlist_id"]
        sp.playlist_replace_items(playlist_id, track_ids)
        sp.playlist_change_details(
            playlist_id,
            name=playlist_name,
            description=f"Automated playlist created with Spotipy.",
        )
        logging.info("Spotify playlist updated!")


def get_artists(sp, search_genre):
    """
    Get artists in the specified genre.

    Args:
        sp: Spotipy object.
        search_genre: Genre to search for.

    Returns:
        List of artists in the specified genre.
    """
    if search_genre is None:
        logging.error("No genre specified!")
        return

    logging.info(f"Searching for artists in the genre - {search_genre}")
    artists_list = []

    # Fetch in batches
    batch_size = 50  # max=50
    offset = 0
    while True:
        results = sp.search(
            q=f"genre:{search_genre}", type="artist", limit=batch_size, offset=offset
        )
        artists_batch = results["artists"]["items"]
        for artist_item in artists_batch:
            artist_dict = {
                "name": artist_item["name"],
                "id": artist_item["id"],
            }
            artists_list.append(artist_dict)

        if len(artists_batch) < batch_size:  # No more results to fetch
            break

        offset += batch_size

    logging.info(f"Artist search comlepted. Found {len(artists_list)} artists.")

    artists_csv = Path.cwd() / f"{search_genre}_artists.csv"
    with open(artists_csv, "w", newline="") as f:
        dict_writer = csv.DictWriter(f, artists_list[0].keys())
        dict_writer.writeheader()
        dict_writer.writerows(artists_list)
    logging.info(f"Artist list saved to {artists_csv.resolve()}")

    return artists_list


def get_new_tracks(sp, search_artists, threshold_date):
    """
    Get new tracks from the specified artists.

    Args:
        sp: Spotipy object.
        search_artists: List of artists to search for.
        threshold_date: Date to search back to.

    Returns:
        List of new tracks.
    """

    new_tracks, searched_ids = [], []
    for idx, artist in tqdm(
        enumerate(search_artists, start=1), total=len(search_artists)
    ):
        logging.info(
            f"Searching artist {idx} / {len(search_artists)} - {artist['name']}"
        )
        results = sp.artist_albums(artist["id"])
        albums = results["items"]
        logging.info(f"Found {len(albums)} albums")
        for album in albums:
            if album["album_type"] == "compilation":
                continue
            album_id = album["id"]
            if album_id not in searched_ids:
                searched_ids.append(album_id)

                release_date_str = album["release_date"]
                release_date_precision = album["release_date_precision"]
                if release_date_precision == "day":
                    release_date = datetime.strptime(
                        release_date_str, "%Y-%m-%d"
                    ).date()
                elif release_date_precision == "month":
                    release_date = datetime.strptime(release_date_str, "%Y-%m").date()
                elif release_date_precision == "year":
                    release_date = datetime.strptime(release_date_str, "%Y").date()

                if release_date >= threshold_date:
                    logging.info(f"Found new album - {album['name']}")
                    album_details = sp.album(album_id)
                    tracks = album_details["tracks"]["items"]
                    for track in tracks:
                        song_dict = {
                            "song": track["name"],
                            "artist": track["artists"][0]["name"],
                            "album": album["name"],
                            "album_type": album["album_type"],
                            "release_date": str(release_date),
                            "id": track["id"],
                        }
                        new_tracks.append(song_dict)
                    logging.info(f"Added {len(tracks)} tracks to list.")

    logging.info(f"Search completed.")

    return new_tracks


if __name__ == "__main__":
    main()
