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
    choco install git -y --params "/NoGitLFS /SChannel /NoShellIntegration";                      `
    choco install vcbuildtools -y --version 2015.4

## -- Install polyswarm-client -----------
WORKDIR C:\polyswarm\polyswarm-client
COPY . .
RUN pip install --no-cache-dir -U pip wheel; pip install --no-cache-dir -r requirements.txt Cython .

## -- Cleanup ----------------------------
RUN choco optimize; Remove-Item -Force -Recurse ${Env:TEMP}\*;

CMD ["powershell"]
