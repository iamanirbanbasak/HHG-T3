"""facechain package.

Deliberately near-empty except for one process-wide guard that has to run before anything
imports onnxruntime.
"""

import os

# The macOS onnxruntime wheel embeds Microsoft's 1DS telemetry SDK: importing it starts a
# background uploader thread plus a CFNetwork loader thread that post to
# https://mobile.events.data.microsoft.com/OneCollector/1.0. Turned off here for two reasons:
#
#   1. Privacy. This tool runs face recognition over local photos and holds API keys in process;
#      it should not be phoning anything home as a side effect of loading a model.
#   2. Exit codes. At interpreter shutdown a static destructor tears the telemetry LogManager
#      down while that uploader thread is still handling an HTTP response. The thread then locks
#      a destroyed mutex, throws, and aborts the process -- SIGABRT, exit 134, *after* all work
#      has finished and the real exit code was chosen. It is a race, so it is intermittent.
#
# Timing is the whole point of putting this in the package __init__: the telemetry Env is built
# when the onnxruntime pybind module is imported. Setting the variable after that import, or
# calling onnxruntime.disable_telemetry_events(), leaves the uploader thread running (verified).
#
# setdefault, and the value is checked rather than merely present: exporting
# ORT_DISABLE_TELEMETRY=0 restores stock onnxruntime behaviour.
os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")
