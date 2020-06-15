 # escape=`
FROM python:3.7-windowsservercore-1809
LABEL maintainer="PolySwarm Developers <info@polyswarm.io>"
SHELL ["powershell", "-ExecutionPolicy bypass", "-NoLogo", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]
ENV DOTNET_RUNNING_IN_CONTAINER=true                        `
    CL="/O1 /Os /favor:INTEL64" CFLAGS="$CL" CXXFLAGS="$CL" `
    chocolateyUseWindowsCompression=true

## -- Download polyswarm-transaction ------
RUN Invoke-WebRequest 'https://github.com/polyswarm/polyswarm-transaction/archive/master.zip' -Outfile ${Env:TEMP}\pstr.zip; `
    Expand-Archive -Path ${Env:TEMP}\pstr.zip -DestinationPath ${Env:TEMP}\polyswarm-transaction; `
## -- Install Choco -----------------------
    iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1')); `
    choco install git -y --params "/NoGitLFS /SChannel /NoShellIntegration";                      `
    choco install vcbuildtools -y --version 2015.4

## -- Install polyswarm-client -----------
WORKDIR C:\polyswarm\polyswarm-client
COPY . .
RUN pip install --no-cache-dir -U wheel setuptools;                      `
    pip install --no-cache-dir                                           `
                  cytoolz[cython]                                        `
                  ${Env:TEMP}\polyswarm-transaction                      `
                  -r C:\polyswarm\polyswarm-client\requirements.txt      `
                  -r C:\polyswarm\polyswarm-client\requirements-test.txt `
                  C:\polyswarm\polyswarm-client;                         `
## -- Cleanup ----------------------------
  choco optimize;                                                        `
  Remove-Item -Force -Recurse -Path ${Env:TEMP}\*, , "${Env:ProgramData}\Package Cache"
