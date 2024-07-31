#!/bin/bash

# Define the parameters for the search
DAYS=7
ARTISTS_LIST="Bachata Artists (Manual).csv"
GENRE=bachata  # only used to name the playlist, since artist list is given

# Define the path to the yaml file with the spotify API parameters
SPOTIFY_YAML=spotify.yaml

# Set the working directory
cd /home/$USER/GitHub/Spotify/

# Define the path to your conda installation
export PATH=/blue/subhash/salil.bavdekar/.conda/envs/spotify/bin/:$PATH

# Run the python script
python new_tracks.py -s $SPOTIFY_YAML -g $GENRE -a "$ARTISTS_LIST" -d $DAYS --no-progress
