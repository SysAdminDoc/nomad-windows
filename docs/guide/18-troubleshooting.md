## 18. Troubleshooting

### AI Chat says "Could not reach the AI"

The AI Chat service needs to be running. Go to the Home page and check if AI Chat shows a green "Running" badge. If not, click Start. If it is not installed yet, click Install first (~310 MB download).

### Service won't start

Check the Application Log in Settings for error details. Common causes: another program is using the same port, antivirus is blocking the executable, or the service files are corrupted (try uninstalling and reinstalling).

### Map downloads fail with "permission denied"

Your antivirus may be blocking the map download tool. Try adding the NOMAD data folder to your antivirus exclusions, or run as Administrator.

### Content packs are stuck downloading

Check your internet connection. Downloads resume where they left off if interrupted. If a download is truly stuck, restart the application.

### Everything appears frozen / buttons do nothing

Try pressing <kbd>Ctrl+Shift+R</kbd> to force-reload the page. If running from the portable exe, make sure you are running the latest version from the releases page.

### LAN access from other devices

Other devices on your network can access NOMAD by opening a browser and going to `http://YOUR_IP:8080`. Your LAN address is shown in the Settings tab. Make sure your firewall allows port 8080.

### Need more help?

[[Visit the GitHub Issues](https://github.com/SysAdminDoc/project-nomad-desktop/issues) page or join the Crosstalk Solutions Discord](https://discord.com/invite/crosstalksolutions) community.
