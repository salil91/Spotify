@echo OFF
rem This example searches for "bachata" tracks released in the last 10 days

rem Define the path to your conda installation
set MAMBAPATH=C:\Users\salil\miniforge3
rem Define the name of the environment
set ENVNAME=spotify

rem Define the path to the yaml file with the spotify API parameters
set SPOTIFY_YAML=spotify.yaml

rem Define the genre and the number of days
set GENRE=bachata
set DAYS=10

rem Activate the conda environment
if %ENVNAME%==base (set ENVPATH=%MAMBAPATH%) else (set ENVPATH=%MAMBAPATH%\envs\%ENVNAME%)
call %MAMBAPATH%\Scripts\activate.bat %ENVPATH%

rem Run the python script 
python new_tracks.py -s %SPOTIFY_YAML% -g %GENRE% -d %DAYS%
pause

rem Deactivate the environment
call mamba deactivate
