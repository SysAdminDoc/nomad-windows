## 33. Security Module Guide

### Camera Setup

NOMAD can display live feeds from IP cameras on your network. Three stream types are supported:
- **MJPEG** — Continuous video stream. Most common for budget cameras. Example URL: `http://192.168.1.100/cgi-bin/mjpg/video.cgi`
- **Snapshot** — Still image that auto-refreshes every 5 seconds. Lower bandwidth. Example: `http://192.168.1.100/snap.cgi`
- **HLS** — High-quality video stream. Used by newer cameras. Example: `http://192.168.1.100/live/stream.m3u8`

Common camera brands and typical URLs:

| Brand | Typical MJPEG URL |
| --- | --- |
| Reolink | `http://IP/cgi-bin/api.cgi?cmd=Snap` |
| Amcrest | `http://IP/cgi-bin/mjpg/video.cgi?channel=1` |
| Wyze (with firmware) | `rtsp://IP/live` (requires bridge) |
| Generic ONVIF | `http://IP/onvif-http/snapshot?Profile_1` |

### Access Logging

The access log tracks who comes and goes from your location. Log entries include: person name, direction (entry, exit, or patrol), location (front gate, back door, perimeter), method (visual, camera, sensor, radio report), and notes. Use this during heightened security situations to maintain awareness of all movements.

### Security Dashboard

The dashboard aggregates: current threat level (from your situation board), number of active cameras, access events in the last 24 hours, and incidents in the last 48 hours. This gives you a single-glance security overview.
