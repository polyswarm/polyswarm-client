# escape=`
FROM python:3.7-windowsservercore-1809
LABEL maintainer="PolySwarm Developers <info@polyswarm.io>"
SHELL ["powershell", "-ExecutionPolicy bypass", "-NoProfile", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]
ENV DOTNET_RUNNING_IN_CONTAINER=true `
    CFLAGS="/Os /favor:INTEL64"      `
    CXXFLAGS="/Os /favor:INTEL64"    `
    chocolateyUseWindowsCompression=true

## -- Install Choco -----------------------
RUN iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1')); `
    choco install git vim -y;
    choco install vcbuildtools -y --version 2015.4

## -- Cleanup ----------------------------
RUN choco optimize; Remove-Item -Force -Recurse ${Env:TEMP}\*;
