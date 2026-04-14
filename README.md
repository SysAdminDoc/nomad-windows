<div align="center">
<img src="nomad-mark.png" width="140" height="140"/>

# NOMAD Field Desk v7.14.0

### Your Personal Intelligence & Preparedness Command Center

**One app. Everything you need. Nothing leaves your machine.**

[![Release](https://img.shields.io/github/v/release/SysAdminDoc/project-nomad-desktop?include_prereleases&label=Download&color=blue)](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2)](https://discord.com/invite/crosstalksolutions)

</div>

---

## Why NOMAD?

Most people piece together their preparedness across a dozen apps, bookmarks, and spreadsheets. When you actually need it, nothing talks to each other and half of it requires internet you might not have.

NOMAD puts everything in one place -live global intelligence, private AI, offline maps, supply tracking, medical references, communications tools, and more -in a single portable app that runs on your desktop. Your data never touches a cloud server. When the internet is available, you get live feeds. When it's not, everything you've cached still works.

**Download it. Run it. That's it.** No accounts, no subscriptions, no setup wizards that take an hour.

---

## What You Get

### See what's happening everywhere
The **Situation Room** pulls in live data from 36 sources -earthquakes, severe weather, armed conflicts, cyber threats, disease outbreaks, wildfires, markets, crypto, and more -and lays it all out on a single dashboard with 108+ intelligence cards and a full interactive world map with 45 data layers. It runs in the background and caches everything locally so you always have a recent snapshot.

### Track military and VIP aircraft in real time
**VIPTrack** monitors global military aviation using live ADS-B data feeds. 11,000+ military and 12,000+ government/VIP aircraft with watchlists, alerts, photos, and altitude-colored trails.

### Simulate nuclear scenarios
**NukeMap** lets you model detonation effects for 32 real warheads -blast radius, thermal burns, fallout, shelter survival odds, and full WW3 exchange simulations with 418 verified targets. Built on published physics (Glasstone & Dolan).

### Ask an AI that knows your situation
A **local AI assistant** runs entirely on your hardware. It knows your actual inventory levels, contacts, weather, medical data, and incidents -so it gives answers that are relevant to *your* situation, not generic advice. It can generate military-format SITREPs, execute actions, and remember context across conversations.

### Manage supplies like a pro
Track everything you own with **barcode scanning, receipt OCR, burn rate projections, and expiration alerts**. Five pre-built templates cover 72-hour kits, bug-out bags, vehicle kits, medical bags, and 30-day family supplies. The system tells you what you're burning through and what to restock before you run out.

### Medical reference that's always there
Patient tracking with **vital signs trending, wound documentation with photo comparison, drug interaction checking, TCCC protocols, triage boards**, and a printable pocket-sized medical flipbook. No cell signal required.

### Maps that work without internet
Download regional map tiles once and they're yours forever. **Waypoints, routes, elevation profiles, perimeter zones, GPX import/export** -all powered by MapLibre with 50+ tile sources.

### Stay connected when infrastructure fails
**LAN chat** with encryption across your local network. **DTMF tones, NATO phonetic trainer, antenna calculators, HF propagation charts**, and a Meshtastic mesh radio bridge for when cell towers go down.

### Print what you need for the field
Generate a complete **operations binder, laminated wallet cards, signal operating instructions, frequency reference cards**, and a medical flipbook -all from your data, formatted for print.

---

## At a Glance

| | |
|---|---|
| **Tabs** | Situation Room, Home, AI Chat, Library, Maps, Notes, Media, Tools, NukeMap, VIPTrack, Preparedness, Settings |
| **Services** | Ollama (AI), Kiwix (Wikipedia), CyberChef, Kolibri, Qdrant, Stirling PDF, FlatNotes, BitTorrent |
| **Intelligence** | 36 data sources, 435+ feeds, 45 map layers, 1,275 infrastructure points, 108+ cards |
| **Preparedness** | Inventory, medical, garden, power, security, radio, 42 calculators, 21 guides, 56 reference cards |
| **Backend** | 600+ API routes across 26 blueprints, 95+ DB tables, 210+ indexes, 775+ automated tests |
| **Platform** | Windows, Linux, macOS -single portable executable per platform |
| **Themes** | Desert, Night Ops, Cyber, Red Light, E-Ink |
| **Privacy** | All data stored locally. No accounts. No telemetry. No cloud. |

---

## Get Started

### Windows
Download **NOMADFieldDesk-Windows.exe** (portable) or **NOMAD-Setup.exe** (installer) from [Releases](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest) and double-click. No install needed -runs from USB, desktop, anywhere.

### Linux
Download **NOMADFieldDesk-Linux** from [Releases](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest), `chmod +x`, and run. Requires GTK WebKit (`sudo apt install python3-gi gir1.2-webkit2-4.1`).

### macOS
Download **NOMADFieldDesk-macOS** from [Releases](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest). Uses native WebKit -no extra dependencies.

### From source
```bash
git clone https://github.com/SysAdminDoc/project-nomad-desktop.git
cd project-nomad-desktop
pip install -r requirements.txt
python nomad.py
```

### Build your own
```bash
pip install pyinstaller
pyinstaller build.spec
```

---

## Requirements

| Platform | What you need |
|----------|--------------|
| Windows 10/11 | WebView2 Runtime (already included in Windows 11) |
| Linux | Python 3.10+, GTK WebKit (`python3-gi gir1.2-webkit2-4.1`) |
| macOS | Python 3.10+ (uses native WebKit) |

---

## Credits

Based on [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions. Desktop edition by [SysAdminDoc](https://github.com/SysAdminDoc).
