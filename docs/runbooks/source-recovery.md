# Recovering camera and microphone capture

Start only the sensors you explicitly permit in the dashboard. On native camera start, Tobi
checks camera indices 0–4 in order and chooses the first that opens and returns a frame; this can
skip an unavailable Continuity Camera and reach a local webcam. In the dashboard you can choose
Automatic or a specific camera index (0–4); OpenCV does not provide stable friendly names, so
use the live preview to identify the webcam. Manual selection is fixed for that session. A failed session clears private
buffers, tracks, transcript and preview. The error identifies the failed stage and gives checks
for device connection, permissions for the program running the core and competing applications.
An opening error does not establish which of those caused it.

While workers are still closing, new starts are disabled; Stop remains available. Once the
workers end, correct the device/permission issue and explicitly start again. Tobi does not
retry or reopen sensors automatically. An unknown connection state blocks starts and allows
Stop; restore the connection and wait for status before trying a new start.

A release warning means the driver did not confirm cleanup. Temporary data is cleared, but
device release is not proven. Check the device/core before retrying. If a worker is unresponsive,
Stop waits at most five seconds; the live worker still prevents a second session. Resolve the
device issue before a deliberate core restart. Never bypass the OS permission prompt or the
separate camera/microphone consent checks.

Replay failures concern fixture availability/decoding or frame format. Normal end after valid
frames is not an error; an unreadable/empty video is. Diagnostics contain fixed codes and state,
not raw driver messages, device names, paths or media. Synthetic fixtures do not verify hardware.
