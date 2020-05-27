# escape=`
FROM mcr.microsoft.com/windows/servercore:1809
LABEL description="Base image for Polyswarm Windows Microengines"
SHELL ["powershell", "-ExecutionPolicy bypass", "-NoProfile", "-command"]

## -- Install Choco -----------------------
# Can not do multiple installations with one command at the moment
# https://chocolatey.org/docs/commands-reference#how-to-pass-options--switches
RUN iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1')); `
    ## -- Microengine Dependencies ------------
    ## Needed to build native extensions
    choco install -y git; `
    choco install -y vcbuildtools --version 2015.4; `
    ## Install python3
    choco install -y python --version 3.6.7; `
    ## -- Utilities ---------------------------
    choco install -y vim-console

## -- Install polyswarm-client -----------
COPY . C:/polyswarm/polyswarm-client
RUN python -m pip install -U pip wheel; `
    pip install                                       `
    --no-warn-script-location                         `
    -r C:/polyswarm/polyswarm-client/requirements.txt `
    C:/polyswarm/polyswarm-client/; `
    ## -- Remove Various Caches --------------
    Remove-Item -Path "$env:TMP\*","$env:LocalAppData\pip\*" -Recurse -Force

## ---------------------------------------
CMD ["powershell"]
