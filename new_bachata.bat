@echo OFF

:: Define the parameters for the search
set DAYS=9
set ARTISTS_LIST="Bachata Artists (Manual).csv"
set GENRE=bachata  &:: only used to name the playlist, since artist list is given

:: Define the path to the yaml file with the spotify API parameters
set SPOTIFY_YAML=spotify.yaml

:: Set the working directory
cd /home/salil.bavdekar/GitHub/Spotify/

:: Define the path to your conda installation
set MAMBAPATH=%USERPROFILE%\miniforge3
:: Define the name of the environment
set ENVNAME=spotify

:: Activate the conda environment
if %ENVNAME%==base (set ENVPATH=%MAMBAPATH%) else (set ENVPATH=%MAMBAPATH%\envs\%ENVNAME%)
call %MAMBAPATH%\Scripts\activate.bat %ENVPATH%

:: Run the python script 
python new_tracks.py -s %SPOTIFY_YAML% -g %GENRE% -a %ARTISTS_LIST% -d %DAYS%
pause

:: Deactivate the environment
call mamba deactivate
