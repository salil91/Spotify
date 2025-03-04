"""
Usage: new_tracks.py [OPTIONS]

  Find tracks from artists in a specified genre released within the last n
  days. A CSV file containing a list tracks or artists can be provided to
  bypass the respective search. Any number of columns can be included in the
  CSV file, but it must contain an "id" column with the respective Spotify
  IDs.

Options:
  -s, --spotify_client FILE       YAML file with Spotify API client ID,
                                  secret, and redirect URI.  [required]
  -g, --genre TEXT                Search for artists in this genre. Search is
                                  only performed if tracks/artists CSV file is
                                  not provided/found. Otherwise, it is only
                                  used in naming the playlist.  [required]
  -d, --days INTEGER              Number of days to search back for new
                                  tracks. If 0, search for tracks released
                                  after the previous Friday.  [default: 0]
  -t, --tracks FILE               CSV file containing track IDs.
  -a, --artists FILE              CSV file containing artist IDs.
  -o, --sort-order [ascending|descending]
                                  Choose the order to sort tracks by release
                                  date. Singles are always at the top, and
                                  albums are always at the bottom. 
                                  [default: descending]
  --dry-run                       Do not update the playlist. CSV files will
                                  be created.
  --no-progress                   Do not display the progress bar.
  --help                          Show this message and exit.
"""

import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path

import click
import spotipy
import yaml
from spotipy.oauth2 import SpotifyOAuth
from tqdm import tqdm


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
    help="Search for artists in this genre. Search is only performed if tracks/artists CSV file is not provided/found. Otherwise, it is only used in naming the playlist.",
)
@click.option(
    "--days",
    "-d",
    default=0,
    show_default=True,
    help="Number of days to search back for new tracks. If 0, search for tracks released after the previous Friday.",
)
@click.option(
    "--tracks",
    "-t",
    help="CSV file containing track IDs.",
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, resolve_path=True, path_type=Path
    ),
)
@click.option(
    "--artists",
    "-a",
    help="CSV file containing artist IDs.",
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, resolve_path=True, path_type=Path
    ),
)
@click.option(
    "--sort-order",
    "-o",
    type=click.Choice(["ascending", "descending", "none"], case_sensitive=False),
    default="descending",
    show_default=True,
    help="Choose the order to sort tracks by release date. Singles are always at the top, and albums are always at the bottom.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Do not update the playlist. CSV files will be created.",
    default=False,
)
@click.option(
    "--no-progress",
    is_flag=True,
    help="Do not display the progress bar.",
    default=False,
)
def main(
    spotify_client, genre, days, tracks, artists, sort_order, dry_run, no_progress
):
    """
    Find tracks from artists in a specified genre released within the last n days.
    A CSV file containing a list tracks or artists can be provided to bypass the respective search.
    Any number of columns can be included in the CSV file, but it must contain an "id" column with the respective Spotify IDs.
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

    if dry_run:
        logging.info("Dry run. Playlist will not be updated.")
        print("Dry run. Playlist will not be updated.")

    # Initialize Spotipy object and client
    rr = ReleaseRadar(
        spotify_client, genre, days, tracks, artists, sort_order, dry_run, no_progress
    )
    rr.initialize_spotipy_client()

    # Load tracks
    if tracks:
        try:
            logging.info(f"Reading list of tracks from {tracks.resolve()}")
            with open(tracks, "r") as f:
                reader = csv.reader(f)
                new_tracks = list(reader)
            logging.info(f"Done. {len(new_tracks)} in list.")
        except FileNotFoundError:
            logging.error("Error reading tracks file!")
            new_tracks = rr.get_new_tracks()
    else:
        new_tracks = rr.get_new_tracks()
    rr.track_list = rr.sort_tracks(new_tracks)

    # Update CSV and playlist
    if len(rr.track_list) == 0:
        logging.info("No new tracks found. Playlist not updated.")
    else:
        rr.update_csv()
        if not rr.dry_run:
            rr.update_playlist()


class ReleaseRadar:
    """
    A playlist generator for new tracks from artists in a specified genre or from a list of tracks/artists.
    """

    def __init__(
        self,
        spotify_yaml,
        genre,
        days=0,
        tracks=None,
        artists=None,
        sort_order="ascending",
        dry_run=False,
        no_progress=False,
    ):
        self.spotify_yaml = spotify_yaml
        self.genre = genre.title()
        self.days = days
        self.tracks = tracks
        self.artists = artists
        self.sort_order = sort_order
        self.dry_run = dry_run
        self.no_progress = no_progress

    def initialize_spotipy_client(self):
        """
        Get a Spotipy object.

        Returns:
            Spotipy object.
        """
        logging.info("Reading Spotify parameters")
        with open(self.spotify_yaml, "r") as f:
            self.params = yaml.safe_load(f)
        scope = "user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public"
        logging.info("Initiating Spotify Client")
        auth_manager = SpotifyOAuth(
            client_id=self.params["client_id"],
            client_secret=self.params["client_secret"],
            redirect_uri=self.params["redirect_uri"],
            scope=scope,
        )
        self.sp = spotipy.Spotify(auth_manager=auth_manager)

        return self.sp

    def get_threshold_date(self):
        """
        Get the threshold date for searching new tracks.

        Returns:
            Date to search back to.
        """
        self.today = datetime.today().date()
        if self.days == 0:
            self.days = (
                (self.today.weekday() - 4) % 7
            ) + 7  # Days since second to last Friday
            logging.info(f"Searching for tracks released after the previous Friday.")
        else:
            logging.info(
                f"Searching for tracks released within the last {self.days} days."
            )
        self.threshold_date = self.today - timedelta(days=self.days)
        logging.info(f"Threshold date: {self.threshold_date}")

        self.playlist_name = f"New {self.genre} from {self.threshold_date.month:d}-{self.threshold_date.day:02d} to {self.today.month:d}-{self.today.day:02d}"

        return self.threshold_date

    def get_artists(self):
        """
        Get artists in the specified genre.

        Returns:
            List of artists in the specified genre.
        """
        if self.genre is None:
            logging.error("No genre specified!")
            return

        logging.info(f"Searching for artists in the following genre: {self.genre}")
        self.artist_list = []

        # Fetch in batches
        batch_size = 50  # max=50
        offset = 0
        while True:
            results = self.sp.search(
                q=f"genre:{self.genre}", type="artist", limit=batch_size, offset=offset
            )
            artists_batch = results["artists"]["items"]
            for artist_item in artists_batch:
                artist_dict = {
                    "name": artist_item["name"].replace('"', ""),
                    "url": artist_item["external_urls"]["spotify"],
                    "id": artist_item["id"],
                }
                self.artist_list.append(artist_dict)

            if len(artists_batch) < batch_size:  # No more results to fetch
                break

            offset += batch_size

        logging.info(f"Artist search comlepted. Found {len(self.artist_list)} artists.")

        # Save artists to CSV
        self.artist_list = sorted(self.artist_list, key=lambda x: x["name"].lower())
        artists_csv = Path.cwd() / f"{self.genre} Artists (Auto).csv"
        with open(artists_csv, "w", newline="", encoding="latin-1") as f:
            dict_writer = csv.DictWriter(f, self.artist_list[0].keys())
            dict_writer.writeheader()
            dict_writer.writerows(self.artist_list)
        logging.info(f"Artist list saved to {artists_csv.resolve()}")

        return self.artist_list

    def get_new_tracks(self):
        """
        Get new tracks from artists in a specified genre or from a list of specified artists.

        Returns:
            List of new tracks.
        """
        self.get_threshold_date()
        print(
            f"Searching for new '{self.genre}' tracks within the last {self.days} days..."
        )

        # Load artists
        if self.artists:  # Load artists from CSV
            try:
                logging.info(f"Reading list of artists from {self.artists.resolve()}")
                with open(self.artists, "r", encoding="latin-1") as f:
                    self.artist_list = [
                        {k.strip(): v.strip() for k, v in row.items()}
                        for row in csv.DictReader(f, skipinitialspace=True)
                    ]
                logging.info(f"Done. {len(self.artist_list)} in list.")
            except FileNotFoundError:  # Search for artists
                logging.error("Error reading artists file!")
                self.artist_list = self.get_artists()
        else:  # Search for artists
            self.artist_list = self.get_artists()

        batch_size = 50
        new_tracks, searched_ids, added_ids = [], [], []
        # TODO: See if tqdm can be turned off with an argument
        for idx, artist in tqdm(
            enumerate(self.artist_list, start=1),
            total=len(self.artist_list),
            disable=self.no_progress,
        ):
            logging.info(
                f"Searching artist {idx} / {len(self.artist_list)} - {artist['name']}"
            )
            results = self.sp.artist_albums(artist["id"], limit=batch_size)
            albums = results["items"]
            if len(albums) == 0:
                continue
            elif len(albums) == batch_size:
                while True:
                    results = self.sp.next(results)
                    if results is None:  # No more results
                        break
                    albums.extend(results["items"])
                    if (
                        len(results["items"]) < batch_size
                    ):  # This was the final batch of results
                        break
            logging.info(f"Found {len(albums)} albums")

            for album in albums:
                if album["album_type"] == "compilation":
                    logging.info(f"Skipping compilation album - {album['name']}")
                    continue
                if "navid" in album["name"].lower():
                    logging.info(f"Skipping Christmas album - {album['name']}")
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
                        release_date = datetime.strptime(
                            release_date_str, "%Y-%m"
                        ).date()
                    elif release_date_precision == "year":
                        release_date = datetime.strptime(release_date_str, "%Y").date()

                    if release_date >= self.threshold_date:
                        logging.info(f"Found new album - {album['name']}")
                        album_details = self.sp.album(album_id)
                        tracks = album_details["tracks"]["items"]
                        for track in tracks:
                            # TODO: Check if track is bachata
                            track_id = track["id"]
                            if track_id not in added_ids:
                                added_ids.append(track_id)
                            song_dict = {
                                "title": track["name"].replace('"', ""),
                                "artist": track["artists"][0]["name"].replace('"', ""),
                                "album": album["name"].replace('"', ""),
                                "album_type": album["album_type"],
                                "release_date": release_date,
                                "url": track["external_urls"]["spotify"],
                                "id": track_id,
                            }
                            new_tracks.append(song_dict)
                        logging.info(f"Added {len(tracks)} tracks to list.")

        logging.info(f"Search completed. Found {len(new_tracks)} new tracks.")
        print(f"Found {len(new_tracks)} new tracks.")

        return new_tracks

    def sort_tracks(self, tracks="ascending"):
        """
        Sort the tracks by release date using the provided order. In addition, all singles are placed at the top, and all albums are placed at the bottom.
        """
        if self.sort_order.lower() == "ascending":
            logging.info(
                "Sorting tracks. Most recently released tracks will be at the bottom of the playlist."
            )
            sort_reverse = False
        elif self.sort_order.lower() == "descending":
            logging.info(
                "Sorting tracks. Most recently released tracks will be at the top of the playlist."
            )
            sort_reverse = True
        else:
            logging.warning(
                f"Sorting order - {self.sort_order} - is not 'ascending' or 'descending'. Tracks will not be sorted."
            )
            return tracks

        sorted_tracks = sorted(
            tracks,
            key=lambda x: (x["release_date"], x["artist"].lower()),
            reverse=sort_reverse,
        )
        sorted_tracks = sorted(
            sorted_tracks,
            key=lambda x: x["album_type"].lower(),
            reverse=True,
        )

        return sorted_tracks

    def update_csv(self):
        """
        Delete the existing CSV file and write the new tracks to it.

        Returns:
            Path to the updated CSV file.
        """
        # Delete old playlists
        old_playlists = Path.cwd().glob(f"New {self.genre} from*")
        for old_playlist in old_playlists:
            old_playlist.unlink()
            logging.info(f"Deleted old track list: {old_playlist.resolve()}")

        # Save new tracks to CSV
        self.playlist_csv = Path.cwd() / f"{self.playlist_name}.csv"
        with open(self.playlist_csv, "w", newline="", encoding="utf-8") as f:
            dict_writer = csv.DictWriter(f, self.track_list[0].keys())
            dict_writer.writeheader()
            dict_writer.writerows(self.track_list)

        logging.info(f"Track list saved to {self.playlist_csv.resolve()}")

        return self.playlist_csv

    def update_playlist(self):
        """
        Update the playlist with the new tracks.

        Returns:
            URL to the updated playlist.
        """
        # Update playlist
        if "playlist_id" not in self.params:
            logging.error("No playlist ID provided!")
            return

        playlist_id = self.params["playlist_id"]
        track_ids = [track["id"] for track in self.track_list]
        self.sp.playlist_replace_items(playlist_id, track_ids)
        self.sp.playlist_change_details(
            playlist_id,
            name=self.playlist_name,
            description=f"Automated playlist created with Spotipy.",
        )
        logging.info(f"Spotify playlist updated: {self.playlist_name}")
        print(f"Spotify playlist updated: {self.playlist_name}")

        self.playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"
        logging.info(f"Playlist URL: {self.playlist_url}")
        print(f"Playlist URL: {self.playlist_url}")

        return self.playlist_url


if __name__ == "__main__":
    main()
