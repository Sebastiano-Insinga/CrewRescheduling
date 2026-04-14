
@echo off
set PATH=%PATH%;C:\Users\sebastiano insinga\DownloadDirector\cplex\bin\x64_win64
cd "C:\Users\sebastiano insinga\Desktop\Tesi\BartvanRossum\bin"
java -verbose -cp ".;scripts;C:\Users\sebastiano insinga\DownloadDirector\cplex\lib\cplex.jar" scripts.Main
echo Programma terminato.
pause
