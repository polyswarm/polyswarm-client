# escape=`
FROM 005789955001.dkr.ecr.us-east-1.amazonaws.com/python37-windowsservercore-1809
FROM 005789955001.dkr.ecr.us-east-1.amazonaws.com/polyswarm-transaction AS transaction

## -- Install polyswarm-client -----------
WORKDIR C:\polyswarm\polyswarm-client
COPY --from=transaction /usr/src/app ${env:TEMP}\polyswarm-transaction
COPY . .
RUN pip3 install --no-cache-dir     `
  cytoolz[cython]                   `
  ${env:TEMP}\polyswarm-transaction `
  -r requirements.txt               `
  -r requirements-test.txt          `
  . ;                               `
  Remove-Item -Force -Recurse ${env:TEMP}\polyswarm-transaction\*
