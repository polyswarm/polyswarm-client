# escape=`
FROM 005789955001.dkr.ecr.us-east-1.amazonaws.com/python37-windowsservercore-1809

## -- Install polyswarm-client -----------
WORKDIR C:\polyswarm\polyswarm-client
COPY . .
RUN pip3 install --no-cache-dir     `
  cytools[cython]                   `
  -r requirements.txt               `
  -r requirements-test.txt          `
  . ;                               `
