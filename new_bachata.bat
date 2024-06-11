rem This example searches for "bachata" tracks released in the last 10 days

rem Define the path to your conda installation
set MAMBAPATH=C:\Users\salil\miniforge3
rem Define the name of the environment
set ENVNAME=spotify

rem Activate the conda environment
if %ENVNAME%==base (set ENVPATH=%MAMBAPATH%) else (set ENVPATH=%MAMBAPATH%\envs\%ENVNAME%)
call %MAMBAPATH%\Scripts\activate.bat %ENVPATH%

rem Run the python script 
python new_tracks.py -s spotify.yaml -g bachata -d 10

rem Deactivate the environment
call mamba deactivate
