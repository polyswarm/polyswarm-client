# polyswarmclient-wine

Years of interaction with Windows have culminated in _this_ - a dozen used nibs
of the cheapest vodka the corner store will sell you while you slur the words
"docker IPAM".

Jeez, you're a mess.  You're an intellectual with taste and class!

That's right, it's time to imbibe a fine glass of `polyswarmclient-wine`, the
solution to your problems in the form of a cute little container which extends
`polyswarmclient` with WINEv5.9, tooling for interaction with GUI elements, a
preset `WINEARCH` & `WINEPREFIX`, a `WINESERVER` wrapper scripts for both
permanent and transient daemons, a .NET runtime and whatever else was needed to
make it drinkable.

## Building

You can build this repository with the dockerfile contained in `docker/Dockerfile`. 

You can also specify the `PLATFORM` build argument of `win32` to support only
32-bit applications, or to `win64` (support both 64-bit applications and
32-bit ones through WoW).

(Most engines are delivered as 32-bit executables, so by default this field is
set to `win32`)

```console
zv@ps:wine$ docker build --build-arg PLATFORM=win32 -f docker/Dockerfile -t polyswarmclient-wine
```

## `WINESERVER`

`wine` spawns target executables under another non-child pid called `winesever`, 
a daemon which provides services roughly analogous to those the Windows kernel.

`wineserver` is automatically launched each time `wine` loads a new binary **and**
no *existing* `wineserver` already exists, along with
several other processes which are *NOT* subprocesses of `wine`. Docker, only
waiting for `wine` to exit, kills these auxillary services before they've had
time enough to complete, which often results in corrupt files.

You have three options:

1. Sleep. `wineserver`, by default, will die after 3 seconds and if you spawn
   it with `WINESERVER=/usr/local/bin/wineserver-transient`, it's
   instantaneous.  This **DOES NOT** mean that it is ready to die instantly
   however, `wineserver` itself takes some time to needs to clean up it's own
   children (`explorer.exe`, `services.exe`, etc.)

2. Check for `wineserver`'s continued existence yourself. `wineserver` isn't a
   child of the shell you're running the command from so you won't be able to
   wait for it. Still, you can poll with the pseudo-signal `0` to `kill`, which
   just checks for the exitence of the PID:

    ```sh
    pids="$(pidof wineserver)"
    if [[ "$pids" ]]; then
        kill -INT ${pids[*]}
        # if wineserver hasn't died after 10 seconds, send sigterm
        ( sleep 10 && kill -TERM ${pids[*]} )&
        while kill -0 ${pids[*]} >/dev/null 2>&1; do sleep 1; done
    fi
    ```

   You can find the script above in `/usr/local/bin/wineserver-wait` if you'd
   like to use it in a `Dockerfile`

### Alternative `WINESERVER` options

Wine provides an environment variable (`WINESERVER`) for setting the
`wineserver` to be used, which, if you're happy with the default of
`wineserver` sticking around 3 seconds (by default), you won't need to change.

If this doesn't sit well with you, this image provides two wrapper scripts
which set "every so often" to 0 and 30 seconds respectively:

- /usr/local/bin/wineserver-transient
- /usr/local/bin/wineserver-persistent

## Simulating activity

There's lots of GUI interaction steps that require attendence in Windows. 

Lucky for you, you can spawn nonconsole applications inside a virtual
framebuffer and interact with it programmatically with two preinstalled tools:

**interact**:

```Dockerfile
RUN xvfb-run wine setup.exe & /usr/local/bin/interact steps/1.bmp steps/2.bmp
```

[**`xdotool`**](http://man.cx/xdotool)

```Dockerfile
RUN Xvfb $DISPLAY & \
    ( watch -n 3 xdotools search --onlyvisible --classname "setup.exe" type "SECRET LICENSE KEY" )& \
    wine setup.exe
```

### `interact`

This repo comes with a C++ program `interact`, which can be used to trigger
clicks during a GUI application's lifecycle.

Unlike `xdotool`, `interact` is driven by editing screen captures of the window
you'd like to driver throughout it's lifecycle, indicating with a transparent
dot / circle where a right-click event should be triggered when that window
is seen in the framebuffer (ignoring window decorations, etc.)

#### Example

It operation is pretty simple:


1. Read each argv elt as a file path to a 32-bit BMP
2. When the X11 framebuffer renders a window with the same contents as the nth BMP file given
3. Find the largest transparent circle within the BMP and issue a right-click button event at the center (in the corresponding X11 display)

This is my workflow:

```console
zv@ps:wine$ docker run -ti --rm --env DISPLAY --volume="${XAUTHORITY?ERR}:/root/.Xauthority:ro" zv/secureage-engine setup.exe # run the application that needs handholding
zv@ps:wine$ xwininfo -wm # find the window id of said applicaiton
zv@ps:wine$ xwd -nobdrs -id 0x5e00006 -out 1.xwd # step through each 'screen' of the application that needs interaction
zv@ps:wine$ gimp *.xwd # edit each of those screencaptures with a transparent circle indicating where to click, exporting as 32-bit BMP w/ transparency
zv@ps:wine$ make interact
zv@ps:wine$ ./interact 1.bmp 2.bmp ...
```

### [`xdotool`](http://man.cx/xdotool)
[`xdotool`](http://man.cx/xdotool) comes preinstalled with the image, it's
an extremely powerful tool to programmatically simulate keyboard or mouse
activity.

This README can't summarize everything there is to know about it, but it's
pretty straightforward to use:

1. Spawn an application inside a virtual framebuffer (`Xfvb :1`)
2. Use `xdotool search $NAME` suffixed with your action
3. ???
4. Profit


#### Example 

You might realize this in a Dockerfile (the following is untested)

```Dockerfile
RUN Xvfb $DISPLAY & \
    ( watch -n 3 xdotools search --onlyvisible --classname "setup.exe" type "SECRET LICENSE KEY" )& \
    setup.exe
```
