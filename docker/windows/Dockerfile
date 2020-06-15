 # escape=`
FROM python:3.7-windowsservercore-1809
FROM polyswarm/polyswarm-transaction as transaction
LABEL maintainer="PolySwarm Developers <info@polyswarm.io>"
SHELL ["powershell", "-ExecutionPolicy bypass", "-NoLogo", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]
ENV DOTNET_RUNNING_IN_CONTAINER=true                        `
    CL="/O1 /Os /favor:INTEL64" CFLAGS="$CL" CXXFLAGS="$CL" `
    chocolateyUseWindowsCompression=true

## -- Install Choco -----------------------
RUN iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1')); `
    choco install git -y --params "/NoGitLFS /SChannel /NoShellIntegration";                      `
    choco install vcbuildtools -y --version 2015.4

## -- Install polyswarm-client -----------
WORKDIR C:\polyswarm\polyswarm-client
COPY --from=transaction /usr/src/app C:\temp\polyswarm-transaction
COPY . .

RUN pip3 install --no-cache-dir -U wheel setuptools;                     `
    pip3 install --no-cache-dir                                          `
                  cytoolz[cython]                                        `
                  C:\temp\polyswarm-transaction                          `
                  -r C:\polyswarm\polyswarm-client\requirements.txt      `
                  -r C:\polyswarm\polyswarm-client\requirements-test.txt `
                  C:\polyswarm\polyswarm-client

## -- Cleanup ----------------------------
RUN choco optimize; `
  Remove-Item -Force -Recurse -Path ${Env:TEMP}\*, 'C:\Temp\polyswarm-transaction', "${Env:ProgramData}\Package Cache"
