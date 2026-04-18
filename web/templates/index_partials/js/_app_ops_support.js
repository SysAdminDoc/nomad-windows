/* ─── Help / Guide ─── */
function showHelp(section) {
  const palette = getThemePalette();
  const bg = palette.bg;
  const text = palette.text;
  const muted = palette.textMuted;
  const surface = palette.surface;
  const border = palette.border;
  const accent = palette.accent;
  const green = palette.green;
  const orange = palette.orange;
  const red = palette.red;
  const textInverse = palette.textInverse;
  openAppFrameHTML('Help Guide', `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>NOMAD Field Guide</title>
  <style>body{font-family:'Segoe UI',sans-serif;background:${bg};color:${text};padding:24px 40px 60px;line-height:1.8;max-width:880px;margin:0 auto;font-size:14px;}
  h1{color:${accent};border-bottom:3px solid ${accent};padding-bottom:8px;font-size:22px;}
  h2{color:${green};margin-top:32px;border-bottom:1px solid ${border};padding-bottom:4px;font-size:17px;}
  h3{color:${orange};margin-top:18px;font-size:14px;}
  .toc{background:${surface};border:1px solid ${border};border-radius:8px;padding:16px 24px;margin:16px 0;columns:2;column-gap:24px;}
  .toc a{display:block;padding:2px 0;color:${text};text-decoration:none;font-size:13px;}.toc a:hover{color:${accent};}
  .tip{background:${surface};border-left:3px solid ${accent};padding:8px 14px;margin:10px 0;border-radius:0 6px 6px 0;font-size:13px;}
  .warn{background:${surface};border-left:3px solid ${orange};padding:8px 14px;margin:10px 0;border-radius:0 6px 6px 0;font-size:13px;}
  kbd{background:${surface};padding:2px 6px;border-radius:4px;font-size:12px;border:1px solid ${border};}
  table{border-collapse:collapse;width:100%;margin:8px 0;}th,td{border:1px solid ${border};padding:6px 10px;text-align:left;font-size:13px;}th{background:${surface};}
  code{background:${surface};padding:1px 4px;border-radius:3px;font-size:12px;}
  ul,ol{margin:6px 0 6px 20px;}li{margin:2px 0;}
  .step{display:flex;align-items:flex-start;gap:12px;margin:8px 0;}
  .step-num{width:28px;height:28px;border-radius:50%;background:${accent};color:${textInverse};display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;flex-shrink:0;}
  .step-text{flex:1;padding-top:3px;}
  .section-icon{margin-right:6px;}
  .guide-lead{font-size:15px;color:${muted};}
  .toc-title{display:block;margin-bottom:6px;column-span:all;}
  .guide-status-green{color:${green};font-weight:700;}
  .guide-status-orange{color:${orange};font-weight:700;}
  .guide-status-red{color:${red};font-weight:700;}
  .guide-footer{margin-top:40px;padding-top:16px;border-top:2px solid ${border};color:${muted};font-size:12px;text-align:center;}
  </style></head><body>
  <h1>NOMAD Field Guide</h1>
  <p class="guide-lead">Version ${VERSION} &mdash; Desktop-first preparedness, reference, and local operations workspace</p>
  <p>Everything in this software works <strong>completely offline</strong> after initial setup. No cloud accounts, no subscriptions, no data leaves your computer. This guide covers every feature and how to get the most out of it.</p>

  <div class="toc">
    <strong class="toc-title">Table of Contents</strong>
    <a href="#getting-started">1. Getting Started</a>
    <a href="#home">2. Home Dashboard</a>
    <a href="#readiness">3. Readiness Score</a>
    <a href="#ai">4. AI Assistant</a>
    <a href="#library">5. Information Library</a>
    <a href="#maps">6. Offline Maps</a>
    <a href="#notes">7. Notes</a>
    <a href="#tools">8. Tools</a>
    <a href="#prep">9. Preparedness (25 Sub-Tabs)</a>
    <a href="#alerts">10. Proactive Alerts</a>
    <a href="#sync">11. Connecting Multiple Systems</a>
    <a href="#scenarios">12. Training Scenarios</a>
    <a href="#themes">13. Themes</a>
    <a href="#settings">14. Settings &amp; Backup</a>
    <a href="#benchmark">15. Diagnostics</a>
    <a href="#keyboard">16. Keyboard Shortcuts</a>
    <a href="#data">17. Data &amp; Privacy</a>
    <a href="#troubleshooting">18. Troubleshooting</a>
    <a href="#day-one">19. Day One Checklist</a>
    <a href="#models-guide">20. Choosing an AI Model</a>
    <a href="#inventory-guide">21. Inventory Best Practices</a>
    <a href="#printable">22. Printable Reports</a>
    <a href="#lan">23. LAN &amp; Multi-Device</a>
    <a href="#services-guide">24. Understanding Services</a>
    <a href="#use-cases">25. Common Use Cases</a>
    <a href="#calculators-guide">26. Calculators Reference</a>
    <a href="#nukemap-guide">27. NukeMap Guide</a>
    <a href="#notes-guide">28. Notes &amp; Documentation</a>
    <a href="#faq">29. FAQ</a>
    <a href="#medical-guide">30. Medical Module In Depth</a>
    <a href="#garden-guide">31. Food Production Guide</a>
    <a href="#power-guide">32. Power Management Guide</a>
    <a href="#security-guide">33. Security Module Guide</a>
    <a href="#weather-guide">34. Weather Tracking Guide</a>
    <a href="#comms-guide">35. Communications &amp; Radio</a>
    <a href="#vault-guide">36. Secure Vault Guide</a>
    <a href="#scenarios-deep">37. Training Scenarios In Depth</a>
    <a href="#task-scheduler-guide">38. Task Scheduler</a>
    <a href="#ai-memory-guide">39. AI Memory System</a>
    <a href="#print-guide">40. Printable Field Documents</a>
    <a href="#glossary">41. Glossary</a>
  </div>

  <h2 id="guide-getting-started">1. Getting Started</h2>
  <p>When you first open NOMAD, the Setup Wizard walks you through picking a storage drive and choosing what to download. You can re-run it anytime from <strong>Settings &gt; Re-run Setup Wizard</strong>.</p>
  <h3>Recommended First Steps</h3>
  <div class="step"><div class="step-num">1</div><div class="step-text"><strong>Install AI Chat</strong> &mdash; Click "Install AI Chat" on the Home page. This downloads the AI engine (~310 MB). Takes 2-5 minutes.</div></div>
  <div class="step"><div class="step-num">2</div><div class="step-text"><strong>Download an AI Model</strong> &mdash; Go to AI Assistant in the sidebar, click "+ Download AI Model." Pick a small model like <strong>Llama 3.2 3B</strong> (2 GB) to start. Larger models give better answers but need more disk space and RAM.</div></div>
  <div class="step"><div class="step-num">3</div><div class="step-text"><strong>Install the Information Library</strong> &mdash; Click "Install Encyclopedia" on the Home page. Then go to the Library tab and click <strong>Download All Essentials</strong> to get offline Wikipedia, medical references, and survival guides.</div></div>
  <div class="step"><div class="step-num">4</div><div class="step-text"><strong>Start Using Preparedness Tools</strong> &mdash; Click Preparedness in the sidebar. Start by adding your family members to <strong>Contacts</strong>, then add your supplies to <strong>Inventory</strong>.</div></div>
  <div class="step"><div class="step-num">5</div><div class="step-text"><strong>Try the Interactive Guides</strong> &mdash; Go to Preparedness &gt; <strong>Guides</strong>. These step-by-step decision trees help you through real situations (water purification, wound care, fire starting, etc.) &mdash; no AI needed.</div></div>
  <div class="tip"><strong>Tip:</strong> The entire setup takes about 10-15 minutes on a decent internet connection. After that, everything works offline forever.</div>

  <h2 id="home">2. Home Dashboard</h2>
  <p>The Home page is your command center overview. It shows:</p>
  <ul>
    <li><strong>Status indicator</strong> &mdash; Overall threat level based on your situation board (green = all clear, yellow = caution, red = critical)</li>
    <li><strong>Low stock &amp; expiring items</strong> &mdash; Click these to jump directly to your inventory</li>
    <li><strong>Incidents (24h)</strong> &mdash; Recent security or safety events you have logged</li>
    <li><strong>Readiness Score</strong> &mdash; Your overall preparedness grade (see below)</li>
    <li><strong>Feature cards</strong> &mdash; Quick access to each major section</li>
    <li><strong>Service status</strong> &mdash; Which tools are installed and running</li>
    <li><strong>Activity feed</strong> &mdash; Recent events (services started, items added, alerts triggered)</li>
  </ul>
  <div class="tip"><strong>Tip:</strong> Use the search bar at the top to find anything &mdash; supplies, contacts, notes, checklists, conversations, and documents.</div>

  <h2 id="readiness">3. Readiness Score</h2>
  <p>The Readiness Score is a letter grade (A through F) that measures how prepared you are across 7 categories:</p>
  <table><tr><th>Category</th><th>Max Points</th><th>What Improves It</th></tr>
  <tr><td>Water</td><td>20</td><td>Adding water supplies to your inventory</td></tr>
  <tr><td>Food</td><td>20</td><td>Adding food items, tracking daily usage, removing expired items</td></tr>
  <tr><td>Medical</td><td>15</td><td>Adding medical supplies, registering patients, recording blood types</td></tr>
  <tr><td>Security</td><td>10</td><td>Adding cameras, logging access events, resolving incidents</td></tr>
  <tr><td>Communications</td><td>10</td><td>Adding contacts, logging radio communications</td></tr>
  <tr><td>Power &amp; Land</td><td>10</td><td>Registering power devices, adding garden plots, saving map waypoints</td></tr>
  <tr><td>Plans &amp; Knowledge</td><td>15</td><td>Completing checklists, writing notes, uploading documents, running drills</td></tr>
  </table>
  <p><strong>Click any category</strong> to jump directly to the relevant Preparedness section where you can improve that score.</p>

  <h2 id="ai">4. AI Assistant</h2>
  <p>The AI runs <strong>entirely on your computer</strong> &mdash; nothing is sent to the internet. It can answer questions about survival, medical care, homesteading, radio communications, and more.</p>
  <h3>How to Use It</h3>
  <ol>
    <li>Make sure the AI Chat service is running (green status on Home page)</li>
    <li>Select an AI model from the dropdown (top-left of the chat area)</li>
    <li>Choose a <strong>conversation mode</strong> from the dropdown &mdash; this tells the AI what kind of expert to be (Medical Advisor, Survival Expert, Homesteading, etc.)</li>
    <li>Type your question and press Enter or click Send</li>
  </ol>
  <h3>Include My Prep Data</h3>
  <p>Toggle <strong>"Include My Prep Data"</strong> to let the AI see your inventory levels, contacts, weather logs, power status, and alerts. This means it can give advice based on YOUR actual situation rather than generic answers. Your data stays on your computer.</p>
  <h3>Document Intelligence</h3>
  <p>Upload PDFs, text files, or other documents in the Library tab. The AI can:</p>
  <ul>
    <li>Automatically classify documents (medical, property, financial, etc.)</li>
    <li>Generate a 2-3 sentence summary</li>
    <li>Extract key information (names, dates, medications, addresses)</li>
    <li>Cross-reference extracted names against your contacts</li>
  </ul>
  <div class="tip"><strong>Tip:</strong> The AI models are downloaded once and work forever offline. Larger models (like Mistral 7B or Llama 3.1 8B) give much better answers than small ones. If you have a GPU, the AI will automatically use it for faster responses.</div>

  <h2 id="library">5. Information Library</h2>
  <p>The Library contains 100+ downloadable content packs organized into 14 categories. Content is available in 3 tiers:</p>
  <ul>
    <li><strong>Essential</strong> &mdash; Core references: Wikipedia, emergency guides, survival skills (~2-5 GB)</li>
    <li><strong>Standard</strong> &mdash; Adds medical databases, repair guides, cooking, agriculture</li>
    <li><strong>Everything</strong> &mdash; Complete collection including history, science, fiction, technical docs</li>
  </ul>
  <p>Use the <strong>Download All Essentials</strong> button to get started quickly. You can also upload your own PDFs and documents for offline reading.</p>

  <h2 id="maps">6. Offline Maps</h2>
  <p>Download maps for your region so you can navigate without cell service or internet. Select from 22 worldwide regions.</p>
  <h3>10 Map Tools</h3>
  <table><tr><th>Tool</th><th>What It Does</th></tr>
  <tr><td>Drop Pin</td><td>Mark a point on the map with a label</td></tr>
  <tr><td>Measure</td><td>Measure distance between two points</td></tr>
  <tr><td>Save Waypoint</td><td>Save a named location to your database</td></tr>
  <tr><td>Draw Zone</td><td>Draw a colored area on the map</td></tr>
  <tr><td>Property Boundary</td><td>Draw a polygon and calculate area (acres) and perimeter (feet/miles)</td></tr>
  <tr><td>Clear Pins</td><td>Remove all temporary markers</td></tr>
  <tr><td>Print Layout</td><td>Generate a printable map page with title, compass, and scale</td></tr>
  <tr><td>Bookmark</td><td>Save and recall specific map views</td></tr>
  <tr><td>Bearing &amp; Distance</td><td>Calculate direction (degrees + cardinal) and distance between two points</td></tr>
  <tr><td>Export GPX</td><td>Export all saved waypoints to a GPS-compatible file</td></tr>
  </table>
  <div class="tip"><strong>Tip:</strong> Enter coordinates directly (like "38.8977, -77.0365") in the search box to jump to a specific location.</div>

  <h2 id="notes">7. Notes</h2>
  <p>Write and organize notes, plans, SOPs, and logs. Notes auto-save as you type. Features include:</p>
  <ul>
    <li><strong>Tags</strong> &mdash; Add comma-separated tags to organize notes</li>
    <li><strong>Pinning</strong> &mdash; Pin important notes to the top of the list</li>
    <li><strong>Live preview</strong> &mdash; See formatted output as you type</li>
    <li><strong>Export</strong> &mdash; Export individual notes as .md files or all notes as a ZIP</li>
  </ul>

  <h2 id="tools">8. Tools</h2>
  <h3>NukeMap v3.2.0</h3>
  <p>Nuclear effects simulator with 418 real-world targets, 708 warheads, and 7 conflict scenarios. Visualize blast radius, thermal radiation, fallout patterns, and shelter requirements for any location.</p>
  <h3>Training Drills</h3>
  <p>6 timed drill scenarios with step-by-step checklists: 72-Hour Kit Check, Evacuation Drill, Blackout Drill, Communication Test, Shelter-in-Place, and First Aid. Results are saved to your drill history.</p>
  <h3>Off-Grid Radio Messaging</h3>
  <p>Connect a Meshtastic radio device via USB to send and receive text messages without cell towers or internet. Range: 1-10+ miles depending on terrain. Buy a Meshtastic radio, plug it in, and click "Scan for Devices."</p>
  <h3>Barcode Scanner</h3>
  <p>Use your camera to scan barcodes and quickly add items to your inventory. Requires camera permission.</p>
  <h3>Video Library</h3>
  <p>Upload and organize instructional videos (survival, medical, repair, cooking, etc.) for offline viewing.</p>

  <h2 id="prep">9. Preparedness (25 Sub-Tabs)</h2>
  <p>The Preparedness section is the heart of NOMAD. It contains 25 sub-tabs ordered by emergency priority:</p>
  <table><tr><th>Tab</th><th>What It Does</th><th>Key Features</th></tr>
  <tr><td><strong>Inventory</strong></td><td>Track all your supplies</td><td>Quantities, expiration dates, daily usage tracking, "Days Left" projections, low-stock alerts, shopping list generator, CSV import/export, quick +/- buttons, one-click Daily Consume</td></tr>
  <tr><td><strong>Contacts</strong></td><td>Emergency people directory</td><td>Names, callsigns, roles, skills, blood types, rally points, medical notes. Skills matrix shows coverage gaps. CSV import/export. Quick-add 7 standard emergency numbers.</td></tr>
  <tr><td><strong>Checklists</strong></td><td>Readiness checklists</td><td>15 built-in templates (72hr kit, bug-out bag, vehicle kit, winter storm, CBRN shelter, infant kit, etc.). Create custom checklists. JSON import/export for sharing.</td></tr>
  <tr><td><strong>Medical</strong></td><td>Health tracking</td><td>Patient profiles linked to contacts. Vital signs (BP, pulse, respiration, temperature, SpO2, pain 0-10, GCS 3-15) with color-coded abnormals. Wound documentation (8 types, 4 severities). 26-pair drug interaction checker. Printable patient care cards. Import patients from contacts with one click.</td></tr>
  <tr><td><strong>Incidents</strong></td><td>Event log</td><td>Record security, medical, infrastructure, weather, and supply events with severity levels and category tags. Filter and search history.</td></tr>
  <tr><td><strong>Family Plan</strong></td><td>Emergency family plan</td><td>FEMA-style plan: 3 meeting locations, 3 evacuation routes, household member cards (medical info, blood types), insurance and utility account numbers. Auto-saves as you type. Print emergency card.</td></tr>
  <tr><td><strong>Security</strong></td><td>Physical security</td><td>Camera viewer (MJPEG live feeds, snapshot auto-refresh, HLS streams). Access log (entry/exit/patrol tracking). Security dashboard with threat level, camera count, and incident summary.</td></tr>
  <tr><td><strong>Power</strong></td><td>Energy management</td><td>Device registry for solar panels, batteries, charge controllers, inverters, and generators with specs. Power log (voltage, SOC%, solar/load watts). Autonomy projection dashboard with color-coded gauges (green &gt;7d, orange &gt;3d, red &lt;3d).</td></tr>
  <tr><td><strong>Garden</strong></td><td>Food production</td><td>Garden plots with dimensions and area calculation. Seed inventory with automatic viability tracking (25 species). Harvest log that automatically adds produce to your inventory. Livestock records (10 species) with health event logging. USDA hardiness zone lookup by latitude.</td></tr>
  <tr><td><strong>Weather</strong></td><td>Weather tracking</td><td>Manual weather observations: pressure, temperature, wind, clouds, visibility. Barometric pressure trend analysis for storm prediction. Pressure drops &gt;4 hPa trigger alerts.</td></tr>
  <tr><td><strong>Guides</strong></td><td>Step-by-step decision trees</td><td>13 interactive guides with 300+ decision nodes: water purification, wound assessment, fire starting, shelter construction, radio setup, food preservation, START triage, power outage response, vehicle emergency, bug-out vs shelter decision, antibiotic selection (symptom-to-treatment), water source assessment (source-to-purification method), and food safety assessment (is this safe to eat?). "Ask AI" button at any step. Works fully offline.</td></tr>
  <tr><td><strong>Calculators</strong></td><td>Survival math</td><td>Water storage, food storage (LDS/FEMA), generator fuel, rainwater harvest, radio range (12 radio types), medication dosage, solar panel sizing, bug-out bag weight, resource planning, travel time, battery life, and bleach dosing calculators.</td></tr>
  <tr><td><strong>Procedures</strong></td><td>Emergency procedures</td><td>17 step-by-step protocols: CPR, bleeding control, water purification, shelter building, fire starting, choking, hypothermia, wound closure, burns, fractures, snake bite, anaphylaxis, dental emergency, psychological first aid, CERT, and natural disaster procedures. Search and expand-all. Printable wallet card.</td></tr>
  <tr><td><strong>Radio</strong></td><td>Frequency reference</td><td>Complete radio frequency table: NOAA weather (7 channels), FRS (22 channels), GMRS, MURS, CB (40 channels), HAM bands (2m, 70cm, HF), and shortwave stations.</td></tr>
  <tr><td><strong>Quick Ref</strong></td><td>Reference cards</td><td>30+ quick reference topics: NATO phonetic alphabet, Morse code with audio trainer, unit converter, triage protocols, companion planting chart, calorie database, livestock care, WHO essential medicines, knots, navigation, sanitation, wild edibles, CBRN decontamination guide, water purification method comparison, antibiotic field reference, PACE communications planning, EMP/CME hardening guide, wound care &amp; closure field guide, agricultural calorie &amp; storage guide, and vehicle bug-out preparedness.</td></tr>
  <tr><td><strong>Signals</strong></td><td>Emergency signals</td><td>Ground-to-air visual signals, sound signal patterns, smoke signal guide for rescue communication.</td></tr>
  <tr><td><strong>Command Post</strong></td><td>Tactical operations</td><td>Situation Report (SITREP) generator with military format. Message cipher (Caesar, Reverse, Atbash). Infrastructure status tracker (12 utilities). Vehicle readiness board. Threat assessment matrix. After-event review form. Emergency broadcast to all LAN devices. 35-item home security hardening assessment with scoring.</td></tr>
  <tr><td><strong>Journal</strong></td><td>Daily log</td><td>Daily journal entries with mood tracking (5 moods), tag system, chronological timeline, and full export.</td></tr>
  <tr><td><strong>Secure Vault</strong></td><td>Encrypted storage</td><td>AES-256-GCM encrypted entries for sensitive information (passwords, coordinates, account numbers, legal documents). Master password required to unlock. Password generator with strength indicator. Legal document templates.</td></tr>
  <tr><td><strong>Skills</strong></td><td>Survival skill tracking</td><td>Self-assessment for 60 survival skills across 10 categories: Fire, Water, Shelter, Food, Navigation, Medical, Communications, Security, Mechanical, Homesteading. Proficiency levels: None, Basic, Intermediate, Expert. Category summary dashboard showing coverage. Seed-defaults button to load all 60 skills at once. Skill proficiency counts toward your Readiness Score.</td></tr>
  <tr><td><strong>Ammo</strong></td><td>Ammunition inventory</td><td>Track ammunition by caliber, brand, bullet weight, bullet type, quantity, and storage location. Caliber-grouped summary cards showing total rounds per caliber. Full CRUD table with search. Ammo reserve contributes to your Security readiness score.</td></tr>
  <tr><td><strong>Community</strong></td><td>Mutual aid network</td><td>Registry of community members, neighbors, and local resources for mutual aid planning. Track name, distance, skills, equipment, contact info, and trust level (Unknown / Acquaintance / Trusted / Inner-Circle). Trusted community members improve your Planning & Knowledge score.</td></tr>
  <tr><td><strong>Radiation</strong></td><td>Radiation dose tracking</td><td>Log radiation dose rate readings (R/hr or rem/hr) with cumulative dose calculation. Dashboard shows total accumulated dose, last reading, and time since first reading. Reference table of dose effects. 7-10 Rule explanation for fallout decay. Uses the nuclear 7-10 Rule: fallout drops 90% for every 7x time elapsed since detonation.</td></tr>
  <tr><td><strong>Fuel</strong></td><td>Fuel storage management</td><td>Track stored gasoline, diesel, propane, kerosene, and other fuels by type, quantity, container, storage location, and expiration date. Stabilizer tracking (extends gasoline shelf life to 2 years). Shelf life reference table. Fuel reserves contribute to your Shelter & Power readiness score. Color-coded expiration warnings.</td></tr>
  <tr><td><strong>Equipment</strong></td><td>Maintenance log</td><td>Track critical equipment: generators, vehicles, power tools, communications gear, medical devices, and water filtration. Log last service date, next service due, service notes, and operational status. One-click "Mark Serviced" button. Status dashboard shows operational vs. needs-service counts. Color-coded overdue service warnings.</td></tr>
  </table>

  <h2 id="alerts">10. Proactive Alerts</h2>
  <p>A background engine automatically checks every 5 minutes for conditions that need your attention:</p>
  <ul>
    <li><strong>Supply consumption warnings</strong> &mdash; Items with less than 7 days supply remaining</li>
    <li><strong>Expiring items</strong> &mdash; Supplies expiring within the next 14 days</li>
    <li><strong>Barometric pressure drops</strong> &mdash; Pressure falling more than 4 hPa (storm indicator)</li>
    <li><strong>Incident clusters</strong> &mdash; 3 or more incidents logged within 48 hours</li>
    <li><strong>Low stock</strong> &mdash; Items that have fallen below their minimum quantity</li>
  </ul>
  <p>Alerts appear as a badge on the bell icon in the sidebar. Click to see details. Click <strong>AI Summary</strong> for a natural-language situation report. Critical alerts trigger browser notifications and an alert sound.</p>
  <div class="tip"><strong>Tip:</strong> Set daily usage rates on your inventory items (the "Daily Usage" field) to get accurate "Days Left" projections and timely low-supply alerts.</div>

  <h2 id="sync">11. Connecting Multiple Systems</h2>
  <p>If you have NOMAD running on multiple computers (e.g., your home PC and a cabin laptop), you can sync data between them:</p>
  <h3>Network Sync (same network)</h3>
  <ol>
    <li>Go to <strong>Settings &gt; Connect Multiple Systems</strong></li>
    <li>Give this system a name (e.g., "Base Camp")</li>
  <li>Click <strong>Scan for Nodes</strong> to find other NOMAD systems on your network</li>
    <li>Click <strong>Push Data</strong> to send your inventory, contacts, checklists, notes, incidents, and waypoints</li>
    <li>Or click <strong>Pull Data</strong> to receive data from another system</li>
  </ol>
  <h3>USB / Offline Transfer (no network needed)</h3>
  <p>In Settings, use <strong>USB / Offline Transfer</strong> to export a portable ZIP file. Copy it to a USB drive, carry it to the other system, and import it there. Data is always merged &mdash; nothing gets overwritten.</p>

  <h2 id="scenarios">12. Training Scenarios</h2>
  <p>Practice your emergency response with 4 realistic multi-phase simulations in the <strong>Tools</strong> tab:</p>
  <table><tr><th>Scenario</th><th>Phases</th><th>Description</th></tr>
  <tr><td>Grid Down &mdash; 7 Days</td><td>7</td><td>Progressive power failure: water loss, food decisions, security, medical, communications, recovery</td></tr>
  <tr><td>Medical Crisis</td><td>5</td><td>Trauma response: assessment, bleeding control, pain management, monitoring, complications</td></tr>
  <tr><td>Evacuation Under Threat</td><td>5</td><td>Emergency departure: warning, packing, route decisions, roadblocks, arrival</td></tr>
  <tr><td>Winter Storm Survival</td><td>5</td><td>Cold weather: heating crisis, fuel rationing, pipe burst, neighbor aid, rescue</td></tr>
  </table>
  <p>If the AI is running, it generates realistic complications between phases based on your actual inventory and contacts data. Each run is scored 0-100 with an after-event review that identifies what you did well and what to improve.</p>

  <h2 id="themes">13. Themes</h2>
  <p>Five themes available (use the quick theme controls in the sidebar footer or the full settings workspace):</p>
  <ul>
  <li><strong>Atlas</strong> &mdash; Warm daylight workspace with soft surfaces and calm contrast</li>
    <li><strong>Midnight</strong> &mdash; Deep neutral dark theme for long operating sessions</li>
    <li><strong>Cobalt</strong> &mdash; Blue-steel dark theme with cooler accents for analysis-heavy work</li>
    <li><strong>Ember</strong> &mdash; Warm dark theme with stronger urgency and night-operations character</li>
    <li><strong>Paper</strong> &mdash; Quiet low-distraction mode for reading, printing, and e-ink style use</li>
  </ul>

  <h2 id="settings">14. Settings &amp; Backup</h2>
  <ul>
    <li><strong>System Monitoring</strong> &mdash; Live CPU, RAM, and disk usage gauges</li>
    <li><strong>AI Models</strong> &mdash; Manage downloaded models. Click "Download All Recommended" to get all suggested models.</li>
    <li><strong>Preferences</strong> &mdash; Theme, AI assistant name, external AI host, dashboard password, auto-backup interval, browser notifications</li>
    <li><strong>Full Backup / Restore</strong> &mdash; Download a ZIP of your entire database, or restore from a previous backup</li>
    <li><strong>Data Summary</strong> &mdash; See how many records you have across all tables</li>
    <li><strong>Application Log</strong> &mdash; View and filter system events for troubleshooting</li>
    <li><strong>Start with Windows</strong> &mdash; Toggle to have NOMAD launch automatically at startup</li>
  </ul>
  <div class="warn"><strong>Important:</strong> Back up regularly! Use <strong>Settings &gt; Full Backup</strong> to download a ZIP file. Store copies on USB drives in multiple locations. The "Last Backup" indicator turns orange after 30 days and red after that.</div>

  <h2 id="benchmark">15. Diagnostics</h2>
  <p>Test your system's CPU, memory, disk, and AI performance. Results are scored 0-100 (NOMAD Score). Run it periodically to confirm your hardware is performing well. Trend arrows show whether performance improved or declined since the last run.</p>

  <h2 id="keyboard">16. Keyboard Shortcuts</h2>
  <table><tr><th>Shortcut</th><th>Action</th></tr>
  <tr><td><kbd>Alt+1</kbd> through <kbd>Alt+9</kbd></td><td>Switch between the primary workspaces</td></tr>
  <tr><td><kbd>Alt+T</kbd></td><td>Open/close the timer widget</td></tr>
  <tr><td><kbd>Alt+C</kbd></td><td>Open/close LAN chat</td></tr>
  <tr><td><kbd>Alt+N</kbd></td><td>Create a new note</td></tr>
  <tr><td><kbd>Ctrl+K</kbd></td><td>Open the command palette</td></tr>
  <tr><td><kbd>Escape</kbd></td><td>Close any open overlay, panel, or dialog</td></tr></table>

  <h2 id="data">17. Data &amp; Privacy</h2>
  <p><strong>All data stays on your computer.</strong> NOMAD has zero telemetry, zero cloud connections, and zero tracking. The only time it connects to the internet is when YOU choose to download services, content packs, or AI models.</p>
  <p>Data is stored in <code>%APPDATA%\\\\NOMADFieldDesk\\\\</code> on new installs (or the custom location you chose during setup). Upgraded systems may still use the legacy <code>%APPDATA%\\\\ProjectNOMAD\\\\</code> folder. This includes:</p>
  <ul>
    <li><code>nomad.db</code> &mdash; SQLite database with all your data (32 tables)</li>
    <li><code>logs/</code> &mdash; Application logs</li>
    <li><code>backups/</code> &mdash; Automatic database backups (keeps last 5)</li>
    <li><code>services/</code> &mdash; Downloaded service binaries and AI models</li>
    <li><code>maps/</code> &mdash; Downloaded offline map data</li>
    <li><code>videos/</code> &mdash; Your uploaded video library</li>
    <li><code>kb_uploads/</code> &mdash; Uploaded documents for AI analysis</li>
  </ul>

  <h2 id="troubleshooting">18. Troubleshooting</h2>
  <h3>AI Chat says "Could not reach the AI"</h3>
  <p>The AI Chat service needs to be running. Go to the Home page and check if AI Chat shows a green "Running" badge. If not, click Start. If it is not installed yet, click Install first (~310 MB download).</p>
  <h3>Service won't start</h3>
  <p>Check the Application Log in Settings for error details. Common causes: another program is using the same port, antivirus is blocking the executable, or the service files are corrupted (try uninstalling and reinstalling).</p>
  <h3>Map downloads fail with "permission denied"</h3>
  <p>Your antivirus may be blocking the map download tool. Try adding the NOMAD data folder to your antivirus exclusions, or run as Administrator.</p>
  <h3>Content packs are stuck downloading</h3>
  <p>Check your internet connection. Downloads resume where they left off if interrupted. If a download is truly stuck, restart the application.</p>
  <h3>Everything appears frozen / buttons do nothing</h3>
  <p>Try pressing <kbd>Ctrl+Shift+R</kbd> to force-reload the page. If running from the portable exe, make sure you are running the latest version from the releases page.</p>
  <h3>LAN access from other devices</h3>
  <p>Other devices on your network can access NOMAD by opening a browser and going to <code>http://YOUR_IP:8080</code>. Your LAN address is shown in the Settings tab. Make sure your firewall allows port 8080.</p>
  <h3>Need more help?</h3>
  <p>Visit the <a href="https://github.com/SysAdminDoc/project-nomad-desktop/issues">GitHub Issues</a> page or join the <a href="https://discord.com/invite/crosstalksolutions">Crosstalk Solutions Discord</a> community.</p>

  <h2 id="day-one">19. Day One Checklist</h2>
  <p>If you just installed NOMAD and want to be operational as fast as possible, follow this checklist:</p>
  <table><tr><th>Priority</th><th>Task</th><th>Time</th></tr>
  <tr><td class="text-status-green-strong">1</td><td>Run the Setup Wizard &mdash; choose your storage drive and Essential content</td><td>2 min</td></tr>
  <tr><td class="text-status-green-strong">2</td><td>Install AI Chat from the Home page</td><td>3 min</td></tr>
  <tr><td class="text-status-green-strong">3</td><td>Download a small AI model (Llama 3.2 3B or Phi 3 Mini)</td><td>5 min</td></tr>
  <tr><td class="text-status-green-strong">4</td><td>Add your household members to Contacts (name, phone, blood type)</td><td>5 min</td></tr>
  <tr><td class="text-status-amber-strong">5</td><td>Add your critical supplies to Inventory (water, food, medical, batteries)</td><td>15 min</td></tr>
  <tr><td class="text-status-amber-strong">6</td><td>Set daily usage rates on consumable items (water, food staples)</td><td>5 min</td></tr>
  <tr><td class="text-status-amber-strong">7</td><td>Fill out the Family Emergency Plan (meeting points, evacuation routes)</td><td>10 min</td></tr>
  <tr><td class="text-status-blue-strong">8</td><td>Download your regional map for offline navigation</td><td>5 min</td></tr>
  <tr><td class="text-status-blue-strong">9</td><td>Complete at least one built-in Checklist (72-Hour Kit recommended)</td><td>10 min</td></tr>
  <tr><td class="text-status-blue-strong">10</td><td>Run through one Interactive Guide (Water Purification is a good start)</td><td>5 min</td></tr>
  </table>
  <div class="tip"><strong>Result:</strong> After completing these 10 steps (~65 minutes), you will have a functional offline command center with AI chat, offline maps, supply tracking with automated alerts, and a family emergency plan. Your Readiness Score should jump to at least a C or B grade.</div>

  <h2 id="models-guide">20. Choosing the Right AI Model</h2>
  <p>AI models vary in size, speed, and quality. Here is a guide to help you choose:</p>
  <table><tr><th>Model</th><th>Size</th><th>RAM Needed</th><th>Best For</th><th>Speed</th></tr>
  <tr><td><strong>Phi 3 Mini</strong></td><td>2.3 GB</td><td>4 GB</td><td>Quick answers, older PCs, limited RAM</td><td>Fast</td></tr>
  <tr><td><strong>Llama 3.2 3B</strong></td><td>2.0 GB</td><td>4 GB</td><td>General questions, good balance of speed and quality</td><td>Fast</td></tr>
  <tr><td><strong>Gemma 3 4B</strong></td><td>3.3 GB</td><td>6 GB</td><td>Better reasoning, multilingual support</td><td>Medium</td></tr>
  <tr><td><strong>Mistral 7B</strong></td><td>4.1 GB</td><td>8 GB</td><td>High-quality answers, good for medical and technical questions</td><td>Medium</td></tr>
  <tr><td><strong>Llama 3.1 8B</strong></td><td>4.7 GB</td><td>8 GB</td><td>Best overall quality for 8GB systems</td><td>Medium</td></tr>
  <tr><td><strong>Qwen3 8B</strong></td><td>4.9 GB</td><td>8 GB</td><td>Latest generation, strong reasoning and coding</td><td>Medium</td></tr>
  <tr><td><strong>MedGemma</strong></td><td>5.0 GB</td><td>8 GB</td><td>Medical-specific: symptoms, medications, conditions</td><td>Medium</td></tr>
  <tr><td><strong>DeepSeek-R1 14B</strong></td><td>9.0 GB</td><td>16 GB</td><td>Complex reasoning, detailed analysis, planning</td><td>Slower</td></tr>
  </table>
  <div class="tip"><strong>Recommendation:</strong> Start with <strong>Llama 3.2 3B</strong> (works on any PC). If you have 8+ GB RAM, upgrade to <strong>Mistral 7B</strong> for much better answers. If you have a GPU (NVIDIA/AMD), models run 5-10x faster.</div>
  <div class="warn"><strong>Note:</strong> Models are downloaded once and stored permanently. You can have multiple models installed and switch between them in the AI Chat dropdown. Unused models can be deleted from Settings to free disk space.</div>

  <h2 id="inventory-guide">21. Inventory Management Best Practices</h2>
  <p>Your inventory is the backbone of your preparedness. Here is how to get the most out of it:</p>
  <h3>Setting Up Your Inventory</h3>
  <ol>
    <li><strong>Start with critical categories:</strong> Water, Food, Medical, and Batteries/Power. These are what you need in the first 72 hours.</li>
    <li><strong>Use specific names:</strong> "Canned black beans 15oz" is better than "beans." You will thank yourself later.</li>
    <li><strong>Set minimum quantities:</strong> This triggers low-stock alerts. For water, a good minimum is 7 gallons per person.</li>
<li><strong>Set daily usage rates:</strong> Even rough estimates help. If your family drinks 2 gallons of water per day, enter 2.0. NOMAD will calculate exactly how many days of supply you have left.</li>
<li><strong>Add expiration dates:</strong> NOMAD alerts you 14 days before items expire, so you can rotate stock.</li>
    <li><strong>Use locations:</strong> "Garage shelf 2", "Kitchen pantry", "Bug-out bag." This helps during an actual emergency when seconds count.</li>
  </ol>
  <h3>Daily Use</h3>
  <ul>
    <li><strong>Daily Consume button:</strong> Click this once per day to automatically subtract daily usage from all tracked items. One click updates everything.</li>
    <li><strong>Quick +/- buttons:</strong> Use the arrow buttons on each row to adjust quantities without opening the edit form.</li>
    <li><strong>Shopping List:</strong> Click "Shopping List" to auto-generate a list of items that are low, expiring, or running out based on burn rates.</li>
  </ul>
  <h3>Recommended Categories</h3>
  <table><tr><th>Category</th><th>Example Items</th><th>Daily Usage Tip</th></tr>
  <tr><td>Water</td><td>Stored water jugs, water filters, purification tablets</td><td>1 gallon per person per day (minimum)</td></tr>
  <tr><td>Food</td><td>Canned goods, rice, beans, freeze-dried meals, MREs</td><td>2,000 calories per person per day</td></tr>
  <tr><td>Medical</td><td>First aid kits, prescription meds, OTC meds, bandages</td><td>Track daily medications individually</td></tr>
  <tr><td>Fuel</td><td>Gasoline, propane, firewood, charcoal, lamp oil</td><td>Generator: 0.5-1.5 gal/hour depending on load</td></tr>
  <tr><td>Batteries</td><td>AA, AAA, D, 9V, CR123A, rechargeable packs</td><td>Flashlight: ~1 set per 20 hours of use</td></tr>
  <tr><td>Hygiene</td><td>Toilet paper, soap, toothpaste, trash bags, bleach</td><td>Toilet paper: ~1 roll per person per week</td></tr>
  <tr><td>Tools</td><td>Multi-tool, duct tape, rope, tarps, fire starters</td><td>Usually no daily usage (set to 0)</td></tr>
  <tr><td>Communications</td><td>Radios, batteries for radios, antenna cables, solar chargers</td><td>Radio batteries: depends on usage</td></tr>
  </table>

  <h2 id="printable">22. Printable Reports &amp; Emergency Cards</h2>
<p>NOMAD can generate several printable documents. Print these and keep physical copies in your go-bag, vehicle, and at rally points:</p>
  <ul>
    <li><strong>Inventory Report</strong> &mdash; Preparedness &gt; Inventory &gt; click <strong>Print</strong>. Full supply list with quantities, locations, and expiration dates.</li>
    <li><strong>Contact Directory</strong> &mdash; Preparedness &gt; Contacts &gt; click <strong>Print</strong>. All emergency contacts with phone numbers, callsigns, rally points, and medical notes.</li>
    <li><strong>Patient Care Card</strong> &mdash; Preparedness &gt; Medical &gt; select a patient &gt; click <strong>Print Card</strong>. Individual medical info including allergies, medications, conditions, and recent vitals.</li>
    <li><strong>Emergency Reference Sheet</strong> &mdash; Home page &gt; scroll to services &gt; <strong>Emergency Sheet</strong> button. One-page comprehensive sheet with critical contacts, inventory summary, weather, waypoints, and quick-reference information.</li>
    <li><strong>Family Emergency Card</strong> &mdash; Preparedness &gt; Family Plan &gt; click <strong>Print Emergency Card</strong>. Wallet-size card with meeting locations, evacuation routes, and emergency contacts.</li>
    <li><strong>Decision Guide Procedure Card</strong> &mdash; Preparedness &gt; Guides &gt; complete a guide &gt; click <strong>Print</strong>. Shows the decision path you followed with the final recommendation.</li>
    <li><strong>Emergency Procedures Wallet Card</strong> &mdash; Preparedness &gt; Procedures &gt; click <strong>Wallet Card</strong>. Condensed quick-reference for CPR, bleeding, choking, and other critical procedures.</li>
  </ul>
  <div class="warn"><strong>Important:</strong> Digital tools can fail. Always keep printed copies of your most critical information. Laminate cards that go in your bag or vehicle. Update and reprint whenever your information changes significantly.</div>

  <h2 id="lan">23. LAN Access &amp; Multi-Device Use</h2>
<p>NOMAD is accessible from any device on your local network &mdash; phones, tablets, laptops &mdash; not just the computer it is installed on.</p>
  <h3>How to Access from Other Devices</h3>
  <div class="step"><div class="step-num">1</div><div class="step-text">Find your LAN address in <strong>Settings</strong> (shown at the top, looks like <code>http://192.168.1.50:8080</code>)</div></div>
  <div class="step"><div class="step-num">2</div><div class="step-text">Open a browser on your phone, tablet, or other computer</div></div>
  <div class="step"><div class="step-num">3</div><div class="step-text">Type that address into the browser and press Enter</div></div>
  <p>Everyone on your network gets the same full interface. Changes made on any device are saved to the central database immediately.</p>
  <h3>LAN Chat</h3>
<p>The chat bubble in the bottom-left corner is a <strong>local network messenger</strong>. Anyone accessing NOMAD from any device can send messages to each other &mdash; no internet or cell service needed. Useful for coordinating during an emergency when phones are down but your local network (router/Wi-Fi) is still running.</p>
  <h3>Dashboard Password</h3>
<p>If you want to restrict who can access NOMAD on your network, set a dashboard password in <strong>Settings &gt; Dashboard Password</strong>. Anyone accessing from outside localhost will need to enter the password.</p>

  <h2 id="services-guide">24. Understanding the 6 Services</h2>
<p>NOMAD manages 6 separate tools. Each one is optional &mdash; install only what you need:</p>
  <table><tr><th>Service</th><th>What It Does</th><th>Size</th><th>Who Needs It</th></tr>
  <tr><td><strong>AI Chat</strong></td><td>Private AI assistant that answers questions offline</td><td>~310 MB + models</td><td>Everyone &mdash; this is the core feature</td></tr>
  <tr><td><strong>Information Library</strong></td><td>Offline Wikipedia, medical references, survival guides</td><td>~60 MB + content packs</td><td>Everyone &mdash; essential reference material</td></tr>
  <tr><td><strong>CyberChef</strong></td><td>Data encoding, encryption, decryption, hashing, file analysis</td><td>~30 MB</td><td>Technical users who need encryption/encoding tools</td></tr>
  <tr><td><strong>Education Platform</strong></td><td>Khan Academy courses, textbooks, progress tracking</td><td>~200 MB + courses</td><td>Families with children, long-term learning</td></tr>
  <tr><td><strong>Vector Search</strong></td><td>AI-powered document search for uploaded files</td><td>~80 MB</td><td>Users who upload many documents for AI analysis</td></tr>
  <tr><td><strong>PDF Tools</strong></td><td>Merge, split, compress, convert, OCR PDFs</td><td>~100 MB + Java</td><td>Users who work with PDF documents frequently</td></tr>
  </table>
  <div class="tip"><strong>Minimal setup:</strong> Install just AI Chat + Information Library for a powerful offline knowledge base. Add others as needed.</div>

  <h2 id="use-cases">25. Common Use Cases</h2>
  <h3>Power Outage (first 24 hours)</h3>
  <ol>
<li>Open NOMAD on your laptop (it runs on battery)</li>
    <li>Check Inventory &gt; filter by "Food" &mdash; see what is perishable and eat that first</li>
    <li>Use the Guides &gt; <strong>Power Outage Response</strong> for step-by-step instructions</li>
    <li>Log an incident (Preparedness &gt; Incidents) so you have a record</li>
    <li>If extended, use the Calculators &gt; <strong>Generator Fuel</strong> to plan fuel usage</li>
    <li>Check the Weather tab &mdash; is a storm causing this? Monitor pressure trends</li>
  </ol>
  <h3>Medical Emergency</h3>
  <ol>
    <li>Open Preparedness &gt; Procedures &gt; search for the relevant procedure (CPR, bleeding, burns, etc.)</li>
    <li>If treating someone: go to Medical tab, find or add the patient, record vitals</li>
    <li>Check Drug Interactions before giving any medications</li>
    <li>Ask the AI (set to "Field Medic" mode) for advice specific to the situation</li>
    <li>Log the incident for your records</li>
  </ol>
  <h3>Evacuation</h3>
  <ol>
    <li>Pull up your Family Plan &mdash; confirm meeting locations and routes with everyone</li>
    <li>Check Inventory &gt; filter by location "Bug-out bag" to verify what is packed</li>
    <li>Use Maps to review your evacuation routes offline</li>
    <li>Print your Contact Directory and Emergency Card (take physical copies)</li>
    <li>If you have time: click "Daily Consume" to update your inventory as you grab items</li>
  </ol>
  <h3>Long-Term Off-Grid Living</h3>
  <ul>
    <li><strong>Daily:</strong> Click "Daily Consume" to track supply burn rates. Log weather observations. Write a journal entry.</li>
    <li><strong>Weekly:</strong> Check the Shopping List for items running low. Review alerts. Run a checklist audit.</li>
    <li><strong>Monthly:</strong> Run a Benchmark to confirm system health. Back up your database to USB. Review and rotate expiring inventory. Update garden records with harvest data.</li>
<li><strong>Quarterly:</strong> Run a Training Scenario. Update your Family Plan. Review and update checklists. Sync with other NOMAD systems if applicable.</li>
  </ul>

  <h2 id="calculators-guide">26. Calculators Reference</h2>
  <p>The Preparedness &gt; Calculators tab contains survival math tools. Here is what each one does:</p>
  <table><tr><th>Calculator</th><th>Inputs</th><th>What It Calculates</th></tr>
  <tr><td><strong>Water Storage</strong></td><td>People, days, climate</td><td>Total gallons needed. Hot climate adds 50%. Includes drinking, cooking, and hygiene water.</td></tr>
  <tr><td><strong>Food Storage</strong></td><td>People, days, calories/person/day</td><td>Total calories needed. Compares your answer to LDS (2,000 cal) and FEMA (2,400 cal) standards.</td></tr>
  <tr><td><strong>Power / Solar Sizing</strong></td><td>Load watts, hours/day, days, sun hours</td><td>Total watt-hours, recommended battery capacity (Ah), minimum solar panel wattage. Accounts for 80% depth of discharge and system efficiency.</td></tr>
  <tr><td><strong>Watch Schedule</strong></td><td>Team members, shift length, days</td><td>Full rotation schedule showing who is on watch when. Ensures equal rest periods.</td></tr>
  <tr><td><strong>Solar Position</strong></td><td>Latitude, longitude, date</td><td>Sunrise, sunset, solar noon, day length. Useful for planning activities and solar panel orientation.</td></tr>
  <tr><td><strong>Moon Phase</strong></td><td>Date</td><td>Current moon phase and illumination. A full moon means better visibility at night but also means you are more visible.</td></tr>
  <tr><td><strong>Coordinate Converter</strong></td><td>Latitude, longitude</td><td>Converts between decimal degrees (38.8977) and degrees-minutes-seconds (38&deg;53\'51.7&quot;N). Useful for radio communication and map reading.</td></tr>
  <tr><td><strong>Travel Time</strong></td><td>Distance, mode, terrain</td><td>Estimated travel time by foot, bicycle, horse, or vehicle across flat, hilly, mountain, or swamp terrain. Accounts for reduced speed on difficult ground.</td></tr>
  <tr><td><strong>Battery Life</strong></td><td>Capacity (mAh), voltage</td><td>Watt-hours available and estimated runtime for common devices (flashlight, radio, phone, laptop).</td></tr>
  <tr><td><strong>Bleach Calculator</strong></td><td>Bleach %, water clarity, gallons</td><td>Exact drops or teaspoons of bleach needed to purify water. Adjusts for cloudy water (double dose). Includes surface disinfection ratios.</td></tr>
  <tr><td><strong>Resource Planner</strong></td><td>People, days, activity level</td><td>Comprehensive resource needs: water, food (calories), fuel, medical supplies. Cross-references with your actual inventory to show gaps.</td></tr>
  </table>
  <div class="tip"><strong>Tip:</strong> The Resource Planner is the most powerful calculator &mdash; it pulls your real inventory data and shows exactly what you have vs. what you need for a given scenario.</div>

  <h2 id="nukemap-guide">27. NukeMap Guide</h2>
<p>NukeMap v3.2.0 is a nuclear effects simulator bundled with NOMAD. It runs entirely offline.</p>
  <h3>What It Can Do</h3>
  <ul>
    <li><strong>Blast Radius Visualization</strong> &mdash; Shows concentric rings for fireball, severe damage, moderate damage, and light damage zones for any weapon yield</li>
    <li><strong>Thermal Radiation</strong> &mdash; Shows how far burns and fire ignition extend from ground zero</li>
    <li><strong>Fallout Plume</strong> &mdash; Models fallout patterns based on wind direction and weapon yield</li>
    <li><strong>Shelter Analysis</strong> &mdash; Calculates radiation exposure based on shelter type and distance</li>
    <li><strong>Multiple Detonation Scenarios</strong> &mdash; 7 pre-built WW3 scenarios with 708 warheads across 418 real-world targets</li>
    <li><strong>EMP/HEMP Burst</strong> &mdash; Visualize electromagnetic pulse effects from high-altitude detonations</li>
  </ul>
  <h3>How to Use It</h3>
  <ol>
    <li>Click <strong>Launch NukeMap</strong> in the Tools tab</li>
    <li>Select a weapon from the sidebar or enter a custom yield</li>
    <li>Click anywhere on the map to place the detonation point</li>
    <li>Examine the colored rings to understand the blast effects at different distances</li>
    <li>Use the scenarios panel to load pre-built conflict simulations</li>
  </ol>
  <div class="warn"><strong>Purpose:</strong> NukeMap is an educational and planning tool. Understanding blast effects helps you evaluate whether your location is within risk zones and plan appropriate shelter and evacuation routes. This is not a toy &mdash; it is a serious planning tool used by emergency management professionals.</div>

  <h2 id="notes-guide">28. Notes &amp; Documentation</h2>
  <p>The Notes tab is your digital notebook for plans, procedures, observations, and logs.</p>
  <h3>Markdown Support</h3>
  <p>Notes support Markdown formatting. Some examples:</p>
  <table><tr><th>Type This</th><th>To Get This</th></tr>
  <tr><td><code># Heading</code></td><td>Large heading</td></tr>
  <tr><td><code>## Subheading</code></td><td>Smaller heading</td></tr>
  <tr><td><code>**bold text**</code></td><td><strong>bold text</strong></td></tr>
  <tr><td><code>*italic text*</code></td><td><em>italic text</em></td></tr>
  <tr><td><code>- item</code></td><td>Bullet point</td></tr>
  <tr><td><code>1. item</code></td><td>Numbered list</td></tr>
  <tr><td><code>[link text](url)</code></td><td>Clickable link</td></tr>
  </table>
  <h3>Organizing Notes</h3>
  <ul>
    <li><strong>Tags</strong> &mdash; Add comma-separated tags (e.g., "medical, procedures, first-aid") to categorize. Use the search to filter by tag.</li>
    <li><strong>Pinning</strong> &mdash; Pin critical notes (SOPs, emergency contacts, rally point coordinates) so they always appear at the top.</li>
    <li><strong>Export</strong> &mdash; Export a single note as a .md file or all notes as a ZIP archive. Print important notes and keep physical copies.</li>
  </ul>
  <h3>Recommended Notes to Create</h3>
  <ul>
    <li>Standard Operating Procedures (SOPs) for your household</li>
    <li>Rally point coordinates and descriptions</li>
    <li>Neighborhood contact list and skills inventory</li>
    <li>Water source locations and purification notes</li>
    <li>Generator maintenance schedule and fuel rotation log</li>
    <li>Garden planting schedule and crop rotation plan</li>
    <li>Radio communication protocols and check-in schedules</li>
  </ul>

  <h2 id="faq">29. Frequently Asked Questions</h2>
<h3>Does NOMAD need the internet to work?</h3>
  <p>No. After you download services, AI models, and content packs, everything works completely offline forever. The only time it connects to the internet is when YOU choose to download something new.</p>
  <h3>Is my data sent to any server or cloud?</h3>
  <p>No. Zero telemetry, zero cloud, zero tracking. All data stays on your computer in a local database file. The AI runs on your hardware &mdash; your conversations are never sent anywhere.</p>
<h3>Can I run NOMAD from a USB drive?</h3>
  <p>Yes. Download the portable <strong>NOMADFieldDesk.exe</strong> and put it on a USB drive. Run it from there. You can choose to store data on the USB drive as well during the setup wizard.</p>
  <h3>How much disk space do I need?</h3>
  <p>The base application is ~25 MB. With essential content and a small AI model: ~5 GB. With everything downloaded: 50-200 GB depending on how many content packs and AI models you install. You control what you download.</p>
  <h3>Can my family use it from another computer on the network?</h3>
<p>Yes. As long as the other computer is on the same Wi-Fi or LAN, it can open a browser and go to your NOMAD address shown in Settings. Remote access is intended for desktop-class browsers on your local network.</p>
  <h3>What happens if my computer breaks?</h3>
  <p>If you have been backing up (Settings &gt; Full Backup), you can restore your entire database on another computer. Keep backup ZIPs on a USB drive in a separate location. The portable exe runs on any Windows 10/11 PC with no installation.</p>
<h3>Can I share my checklists with friends who also use NOMAD?</h3>
  <p>Yes. Go to Preparedness &gt; Checklists, click a checklist, then click <strong>Export JSON</strong>. Send the file to your friend and they can click <strong>Import</strong> to add it to their system. You can also use the sync features to share all data at once.</p>
<h3>How do I update NOMAD?</h3>
  <p>Download the latest version from the <a href="https://github.com/SysAdminDoc/project-nomad-desktop/releases">releases page</a>. If using the portable exe, just replace the old file with the new one. If using the installer, run the new installer &mdash; it updates in place. Your data is stored separately and is preserved across updates.</p>
  <h3>Why do some features say "Install" before I can use them?</h3>
<p>NOMAD manages several separate tools (AI Chat, Information Library, etc.). Each needs to be downloaded once before use. This keeps the base application small and lets you choose what you need. Most features in the Preparedness tab work immediately with no installation required.</p>
  <h3>The AI gives wrong or unhelpful answers. What should I do?</h3>
  <p>Try a larger AI model (see the AI Model guide above). Smaller models are fast but less accurate. Also try changing the conversation mode &mdash; "Medical Advisor" gives better medical answers than "General Assistant." Enable "Include My Prep Data" so the AI has context about your specific situation.</p>

  <h2 id="medical-guide">30. Medical Module In Depth</h2>
  <p>The Medical tab in Preparedness is a full field-hospital record system. Here is how to use it effectively:</p>
  <h3>Setting Up Patients</h3>
  <ol>
    <li>Go to Preparedness &gt; Medical and click <strong>Add Patient</strong></li>
    <li>If the person is already in your Contacts, click <strong>Import from Contacts</strong> instead &mdash; it copies their name, blood type, and medical notes automatically</li>
    <li>Fill in: age, weight (kg), sex, blood type, allergies, current medications, and existing conditions</li>
    <li>Use JSON array format for allergies/medications/conditions: <code>["Penicillin", "Latex"]</code></li>
  </ol>
  <h3>Recording Vitals</h3>
  <p>Click on a patient, then click <strong>Add Vitals</strong>. Enter any or all of:</p>
  <table><tr><th>Vital</th><th>Normal Range (Adult)</th><th>Color Coding</th></tr>
  <tr><td>Blood Pressure</td><td>90-140 / 60-90</td><td>Red if systolic &gt;180 or &lt;80</td></tr>
  <tr><td>Pulse</td><td>60-100 bpm</td><td>Red if &gt;120 or &lt;50</td></tr>
  <tr><td>Respiration</td><td>12-20 breaths/min</td><td>Red if &gt;30 or &lt;8</td></tr>
  <tr><td>Temperature</td><td>97.0-99.5 &deg;F</td><td>Red if &gt;103 or &lt;95</td></tr>
  <tr><td>SpO2</td><td>95-100%</td><td>Red if &lt;90%, orange if &lt;94%</td></tr>
  <tr><td>Pain Level</td><td>0 (none) to 10 (worst)</td><td>Red if 8+, orange if 5-7</td></tr>
  <tr><td>GCS (Glasgow Coma Scale)</td><td>15 (alert) to 3 (unresponsive)</td><td>Red if &lt;9</td></tr>
  </table>
<div class="tip"><strong>Tip:</strong> Record vitals every 15-30 minutes during an active medical situation. The trend over time is often more important than any single reading. NOMAD tracks the history so you can see if a patient is improving or declining.</div>
  <h3>Drug Interaction Checker</h3>
  <p>Before giving medications, check for dangerous interactions. The checker covers 26 common interaction pairs including:</p>
  <ul>
    <li>NSAIDs (ibuprofen, aspirin, naproxen) with blood thinners</li>
    <li>Acetaminophen (Tylenol) with alcohol or liver medications</li>
    <li>SSRIs with other serotonergic drugs (serotonin syndrome risk)</li>
    <li>Opioids with benzodiazepines (respiratory depression risk)</li>
    <li>ACE inhibitors with potassium supplements (hyperkalemia risk)</li>
  </ul>
  <div class="warn"><strong>Warning:</strong> The drug interaction checker is a reference tool, not a replacement for professional medical advice. In a true emergency, use your best judgment and seek professional care as soon as possible.</div>
  <h3>Wound Documentation</h3>
  <p>The wound log supports 8 wound types (laceration, puncture, abrasion, burn, fracture, crush, bite, other) and 4 severity levels (minor, moderate, severe, critical). Record the body location, description, and treatment given. This creates a timeline that is invaluable if the patient later reaches professional medical care.</p>

  <h2 id="garden-guide">31. Food Production Guide</h2>
  <p>The Garden tab helps you track everything related to growing and raising your own food.</p>
  <h3>Garden Plots</h3>
<p>Add each growing area with its dimensions (width x length in feet), sun exposure (full sun, partial shade, full shade), and soil type. NOMAD calculates total square footage automatically. This helps you plan how much you can grow.</p>
  <h3>Seed Inventory &amp; Viability</h3>
<p>Seeds lose viability over time. NOMAD tracks 25 species with species-specific shelf life data:</p>
  <table><tr><th>Species</th><th>Years Viable</th><th>Notes</th></tr>
  <tr><td>Onion, Parsnip, Parsley</td><td>1-2 years</td><td>Use quickly; short shelf life</td></tr>
  <tr><td>Corn, Pepper, Beans</td><td>2-3 years</td><td>Moderate shelf life</td></tr>
  <tr><td>Tomato, Squash, Carrot</td><td>3-5 years</td><td>Good keepers if stored dry and cool</td></tr>
  <tr><td>Cucumber, Lettuce, Radish</td><td>5+ years</td><td>Longest viable; excellent for stockpiling</td></tr>
  </table>
<p>Enter the year each seed was harvested and NOMAD calculates current viability. If seeds show less than 50% viability, plant extra to compensate for lower germination rates.</p>
  <h3>Harvest Logging</h3>
  <p>When you harvest produce, log it in the Harvest tab. Specify the crop, quantity, unit (lbs, heads, bunches), and which plot it came from. <strong>Harvests automatically create or update items in your Inventory</strong> &mdash; so your supply counts stay accurate without duplicate entry.</p>
  <h3>Livestock</h3>
  <p>Track animals by species (chicken, goat, cattle, pig, rabbit, sheep, duck, turkey, horse, bee), with individual names or tag numbers, date of birth, sex, weight, and status (active, sold, deceased). Log health events (vaccinations, illnesses, treatments) on each animal with timestamps.</p>
  <h3>USDA Hardiness Zone</h3>
<p>Enter your latitude and NOMAD estimates your USDA plant hardiness zone (3a through 11a+). This tells you which plants can survive your winters and when to plant. The lookup works offline using latitude-based approximation.</p>

  <h2 id="power-guide">32. Power Management Guide</h2>
  <p>The Power tab helps you track your energy infrastructure and project how long you can sustain operations.</p>
  <h3>Device Registry</h3>
  <p>Register every power device you own. Each type has specific fields:</p>
  <table><tr><th>Device Type</th><th>Key Specs to Record</th></tr>
  <tr><td>Solar Panel</td><td>Wattage, voltage, type (monocrystalline, polycrystalline, thin-film)</td></tr>
  <tr><td>Battery</td><td>Capacity (Ah), voltage, type (lead-acid, LiFePO4, lithium-ion, AGM)</td></tr>
  <tr><td>Charge Controller</td><td>Amperage, type (MPPT, PWM), max voltage</td></tr>
  <tr><td>Inverter</td><td>Wattage (continuous and peak), input voltage, output (120V/240V)</td></tr>
  <tr><td>Generator</td><td>Wattage, fuel type, fuel capacity, runtime per tank</td></tr>
  </table>
  <h3>Power Logging</h3>
  <p>Log daily readings: battery voltage, state of charge (SOC%), solar watts produced, solar watt-hours today, load watts consumed, load watt-hours today, and whether the generator is running. Over time, this builds a picture of your energy balance.</p>
  <h3>Autonomy Dashboard</h3>
  <p>The dashboard calculates your <strong>net daily energy balance</strong> (solar production minus consumption) and projects how many days your batteries will last:</p>
  <ul>
    <li><strong class="guide-status-green">Green gauge</strong> &mdash; More than 7 days of autonomy. You are energy-sustainable.</li>
    <li><strong class="guide-status-orange">Orange gauge</strong> &mdash; 3-7 days. Start reducing consumption or increasing production.</li>
    <li><strong class="guide-status-red">Red gauge</strong> &mdash; Less than 3 days. Critical &mdash; activate generator or drastically cut loads.</li>
  </ul>

  <h2 id="security-guide">33. Security Module Guide</h2>
  <h3>Camera Setup</h3>
<p>NOMAD can display live feeds from IP cameras on your network. Three stream types are supported:</p>
  <ul>
    <li><strong>MJPEG</strong> &mdash; Continuous video stream. Most common for budget cameras. Example URL: <code>http://192.168.1.100/cgi-bin/mjpg/video.cgi</code></li>
    <li><strong>Snapshot</strong> &mdash; Still image that auto-refreshes every 5 seconds. Lower bandwidth. Example: <code>http://192.168.1.100/snap.cgi</code></li>
    <li><strong>HLS</strong> &mdash; High-quality video stream. Used by newer cameras. Example: <code>http://192.168.1.100/live/stream.m3u8</code></li>
  </ul>
  <p>Common camera brands and typical URLs:</p>
  <table><tr><th>Brand</th><th>Typical MJPEG URL</th></tr>
  <tr><td>Reolink</td><td><code>http://IP/cgi-bin/api.cgi?cmd=Snap</code></td></tr>
  <tr><td>Amcrest</td><td><code>http://IP/cgi-bin/mjpg/video.cgi?channel=1</code></td></tr>
  <tr><td>Wyze (with firmware)</td><td><code>rtsp://IP/live</code> (requires bridge)</td></tr>
  <tr><td>Generic ONVIF</td><td><code>http://IP/onvif-http/snapshot?Profile_1</code></td></tr>
  </table>
  <h3>Access Logging</h3>
  <p>The access log tracks who comes and goes from your location. Log entries include: person name, direction (entry, exit, or patrol), location (front gate, back door, perimeter), method (visual, camera, sensor, radio report), and notes. Use this during heightened security situations to maintain awareness of all movements.</p>
  <h3>Security Dashboard</h3>
  <p>The dashboard aggregates: current threat level (from your situation board), number of active cameras, access events in the last 24 hours, and incidents in the last 48 hours. This gives you a single-glance security overview.</p>

  <h2 id="weather-guide">34. Weather Tracking Guide</h2>
  <p>The Weather tab lets you record manual weather observations. This is crucial when you are offline and cannot check weather forecasts.</p>
  <h3>What to Record</h3>
  <ul>
    <li><strong>Barometric Pressure (hPa)</strong> &mdash; The most important reading. Falling pressure predicts storms. Rising pressure indicates clearing weather. A drop of more than 4 hPa in a few hours is a strong storm warning. <em>Requires a barometer &mdash; many outdoor thermometers include one.</em></li>
    <li><strong>Temperature (&deg;F)</strong> &mdash; Current reading. Track trends to anticipate heating/cooling needs.</li>
    <li><strong>Wind Direction &amp; Speed</strong> &mdash; Note where wind is coming from (N, NE, E, etc.) and estimated speed. Shifting winds often precede weather changes.</li>
    <li><strong>Cloud Cover</strong> &mdash; Clear, partly cloudy, overcast, threatening. Cloud types can indicate approaching weather.</li>
    <li><strong>Precipitation</strong> &mdash; Rain, snow, sleet, hail, fog, or none. Note intensity (light, moderate, heavy).</li>
    <li><strong>Visibility</strong> &mdash; Good, reduced, poor. Important for travel decisions.</li>
  </ul>
  <h3>Reading the Trends</h3>
<p>NOMAD automatically analyzes your pressure readings over time:</p>
  <ul>
    <li><strong>Steady (change &lt; 1 hPa)</strong> &mdash; Current weather likely to continue</li>
    <li><strong>Slowly falling (1-3 hPa)</strong> &mdash; Weather may deteriorate in 12-24 hours</li>
<li><strong>Rapidly falling (&gt; 4 hPa)</strong> &mdash; Storm approaching. NOMAD generates an automatic alert.</li>
    <li><strong>Rising</strong> &mdash; Weather improving. If rising rapidly after a storm, clearing is imminent.</li>
  </ul>
  <div class="tip"><strong>Tip:</strong> Record weather at the same times each day (e.g., morning and evening) for the most useful trend data. Even without instruments, noting cloud patterns and wind changes has value.</div>

  <h2 id="comms-guide">35. Communications &amp; Radio Guide</h2>
<p>NOMAD includes several tools for emergency communications:</p>
  <h3>Radio Reference Table</h3>
  <p>Preparedness &gt; Radio has a complete frequency reference:</p>
  <table><tr><th>Service</th><th>Channels</th><th>Range</th><th>License Needed</th></tr>
  <tr><td>FRS (Family Radio Service)</td><td>22</td><td>0.5-2 miles</td><td>No</td></tr>
  <tr><td>GMRS (General Mobile Radio)</td><td>30</td><td>1-25 miles</td><td>Yes ($35, covers family)</td></tr>
  <tr><td>MURS (Multi-Use Radio)</td><td>5</td><td>1-5 miles</td><td>No</td></tr>
  <tr><td>CB (Citizens Band)</td><td>40</td><td>2-15 miles</td><td>No</td></tr>
  <tr><td>HAM (Amateur Radio)</td><td>Many</td><td>Local to worldwide</td><td>Yes (exam required)</td></tr>
  </table>
  <h3>Key Emergency Frequencies</h3>
  <ul>
    <li><strong>FRS Channel 1</strong> &mdash; Common rally/meeting channel</li>
    <li><strong>FRS Channel 3</strong> &mdash; Widely used emergency channel</li>
    <li><strong>GMRS Channel 20</strong> &mdash; Emergency/travel channel</li>
    <li><strong>HAM 146.520 MHz</strong> &mdash; 2-meter calling frequency (most popular)</li>
    <li><strong>HAM 446.000 MHz</strong> &mdash; 70cm calling frequency</li>
    <li><strong>NOAA Weather</strong> &mdash; 162.400-162.550 MHz (7 channels, listen-only)</li>
    <li><strong>CB Channel 9</strong> &mdash; Official emergency channel</li>
    <li><strong>CB Channel 19</strong> &mdash; Highway/trucker channel (road conditions)</li>
  </ul>
  <h3>LAN Chat</h3>
  <p>The chat bubble in the bottom-left corner lets anyone on your local network send messages to each other. This works when cell phones are down but your Wi-Fi router is still running (even on generator or battery power). Set your name in the chat window so others know who is messaging.</p>
  <h3>Emergency Broadcast</h3>
<p>In the Command Post tab, the <strong>Emergency Broadcast</strong> feature sends a high-priority message to every device currently connected to NOMAD. It appears as a banner at the top of the screen with an alert sound. Use this for urgent group notifications like &ldquo;Evacuate now&rdquo; or &ldquo;Shelter in place.&rdquo;</p>

  <h2 id="vault-guide">36. Secure Vault Guide</h2>
  <p>The Secure Vault encrypts sensitive information with AES-256-GCM &mdash; the same encryption standard used by banks and the military.</p>
  <h3>How It Works</h3>
  <ol>
    <li>Set a master password the first time you open the Vault</li>
    <li>Enter this password each time you want to view or add entries</li>
<li>All data is encrypted <strong>in your browser</strong> before being stored &mdash; even NOMAD itself cannot read your vault without the password</li>
    <li>If you forget your password, <strong>there is no recovery</strong> &mdash; the encryption is real and cannot be bypassed</li>
  </ol>
  <h3>What to Store</h3>
  <ul>
    <li>Account passwords and PINs</li>
    <li>Safe combinations and lock codes</li>
    <li>GPS coordinates of caches, rally points, or sensitive locations</li>
    <li>Insurance policy numbers and account details</li>
    <li>Legal document references (will locations, power of attorney details)</li>
    <li>Medical record numbers</li>
    <li>Cryptocurrency wallet seeds or recovery phrases</li>
  </ul>
  <div class="warn"><strong>Critical:</strong> Write your vault password on paper and store it in a physically secure location (fireproof safe, safety deposit box). If you lose the password, your vault entries are permanently unrecoverable.</div>
  <h3>Password Generator</h3>
  <p>The built-in password generator creates strong random passwords. Adjust the length and click Generate. Use the show/hide toggle to verify the password before saving it.</p>

  <h2 id="scenarios-deep">37. Training Scenarios In Depth</h2>
  <p>The 4 training scenarios are designed to test your decision-making under pressure. Here is what to expect:</p>
  <h3>Grid Down &mdash; 7 Days</h3>
  <p>The longest and most comprehensive scenario. You will face decisions about:</p>
  <ul>
    <li><strong>Phase 1:</strong> Initial power loss &mdash; immediate actions, device protection</li>
    <li><strong>Phase 2:</strong> Water supply &mdash; municipal water may fail, alternative sources</li>
    <li><strong>Phase 3:</strong> Food management &mdash; refrigeration lost, prioritize perishables</li>
    <li><strong>Phase 4:</strong> Security &mdash; darkness increases vulnerability, neighbor coordination</li>
    <li><strong>Phase 5:</strong> Medical &mdash; managing without electric medical devices</li>
    <li><strong>Phase 6:</strong> Communications &mdash; establishing contact with outside world</li>
    <li><strong>Phase 7:</strong> Recovery &mdash; power restored, damage assessment, after-action review</li>
  </ul>
  <h3>How AI Complications Work</h3>
  <p>Between phases, the AI has a 50% chance of injecting a complication based on your actual data. For example:</p>
  <ul>
    <li>If your water inventory is low, it might say: &ldquo;Your water supply has dropped to 4 gallons. A neighbor asks to share.&rdquo;</li>
    <li>If you have a patient registered, it might say: &ldquo;[Patient name] is showing signs of dehydration.&rdquo;</li>
    <li>If you have no generator in your power devices, it might say: &ldquo;The family next door has a generator and offers to let you charge devices &mdash; but they want something in trade.&rdquo;</li>
  </ul>
<p>This makes every run unique and realistic. The more data you put into NOMAD, the more personalized the scenarios become.</p>
  <h3>Scoring</h3>
  <p>After completing all phases, the AI grades your performance 0-100 based on:</p>
  <ul>
    <li>Did you address immediate threats first?</li>
    <li>Did you conserve resources appropriately?</li>
    <li>Did you consider the needs of all household members?</li>
    <li>Did you maintain communications and security?</li>
    <li>Were your decisions consistent and logical?</li>
  </ul>
  <p>Scores are saved to your history so you can track improvement over time. Aim for 80+ on all four scenarios.</p>

  <h2 id="task-scheduler-guide">38. Task Scheduler</h2>
  <p>The Task Scheduler (Settings tab) lets you create recurring tasks for maintenance, medical, patrol, garden, and inventory activities.</p>
  <table>
    <tr><th>Feature</th><th>Description</th></tr>
    <tr><td><strong>Recurring Tasks</strong></td><td>Set tasks to repeat daily, weekly, or monthly. When completed, the next due date auto-calculates.</td></tr>
    <tr><td><strong>Categories</strong></td><td>Maintenance, Medical, Patrol, Garden, Inventory, Custom — color-coded in the task list.</td></tr>
    <tr><td><strong>Assignment</strong></td><td>Assign tasks to team members from your Contacts list.</td></tr>
    <tr><td><strong>Overdue Alerts</strong></td><td>Overdue tasks appear as predictive alerts in the alert bar with a "PREDICTED" badge.</td></tr>
    <tr><td><strong>Sunrise/Sunset</strong></td><td>The dashboard sun widget shows sunrise, sunset, and day length for solar panel and patrol planning.</td></tr>
  </table>
  <p><strong>Examples:</strong> "Check water filter" (weekly), "Generator oil change" (monthly), "Medication dose" (daily), "Patrol north fence" (daily).</p>

  <h2 id="ai-memory-guide">39. AI Memory System</h2>
  <p>AI Memory lets you store persistent facts that the AI remembers across all conversations and copilot queries.</p>
  <table>
    <tr><th>Feature</th><th>Description</th></tr>
    <tr><td><strong>Memory Panel</strong></td><td>Click the "Memory" button in the AI Chat header to view, add, or delete facts.</td></tr>
    <tr><td><strong>Persistent Context</strong></td><td>Facts are injected into every AI interaction — chat, copilot quick-query, and SITREP generation.</td></tr>
    <tr><td><strong>What to Store</strong></td><td>Location, group size, medical conditions, equipment specs, key concerns, ongoing situations, preferences.</td></tr>
    <tr><td><strong>Emergency Sheet</strong></td><td>AI memory facts appear on the printable Emergency Reference Sheet under "Operator Notes."</td></tr>
  </table>
  <p><strong>Examples:</strong> "Family of 4, two children ages 5 and 8", "Solar array is 5kW with 10kWh battery", "Well water requires UV treatment", "Bug-out location is the cabin at waypoint 'Safe House'".</p>

  <h2 id="print-guide">40. Printable Field Documents</h2>
<p>NOMAD generates 9 printable documents for when screens aren't available. Access from the Home tab "Printable Field Documents" section or Settings tab.</p>
  <table>
    <tr><th>Document</th><th>Contents</th><th>Best For</th></tr>
    <tr><td><strong>Operations Binder</strong></td><td>Complete reference: TOC, contacts, frequencies, medical cards, inventory, checklists, waypoints, procedures, family plan</td><td>Keep in go-bag or command post. Replace monthly.</td></tr>
    <tr><td><strong>Wallet Cards</strong></td><td>5 credit-card-sized cards: ICE, blood type, medications, rally points, frequencies</td><td>Laminate and carry on person at all times.</td></tr>
    <tr><td><strong>SOI</strong></td><td>Signal Operating Instructions: frequency assignments, call sign matrix, radio profiles, net schedule</td><td>Issue to all radio operators. Destroy when outdated.</td></tr>
    <tr><td><strong>Emergency Sheet</strong></td><td>One-page critical data aggregate with contacts, supplies, patients, waypoints, weather, tasks, AI notes</td><td>Post on wall at base camp. Update weekly.</td></tr>
    <tr><td><strong>Medical Cards</strong></td><td>Per-patient vital signs, medications, conditions</td><td>Give to each patient's caregiver.</td></tr>
    <tr><td><strong>Bug-Out List</strong></td><td>Grab-and-go checklist with rally points</td><td>Post near exit doors.</td></tr>
    <tr><td><strong>Inventory Report</strong></td><td>Full supply list with quantities, locations, expiration dates</td><td>Physical inventory verification.</td></tr>
    <tr><td><strong>Contact Directory</strong></td><td>Complete personnel directory with all details</td><td>Keep copy at each rally point.</td></tr>
    <tr><td><strong>Frequency Card</strong></td><td>Standard emergency frequencies + team contacts</td><td>Laminate pocket-sized for each radio operator.</td></tr>
  </table>

  <h2 id="glossary">41. Glossary</h2>
  <table><tr><th>Term</th><th>Definition</th></tr>
  <tr><td>AI Model</td><td>A downloadable file that gives the AI its knowledge and reasoning ability. Larger models = better answers but more storage and RAM required.</td></tr>
  <tr><td>BOB (Bug-Out Bag)</td><td>A pre-packed bag with essentials for a 72-hour evacuation. Also called a go-bag, GOOD bag, or INCH bag.</td></tr>
<tr><td>Burn Rate</td><td>How fast you are consuming a supply. Measured in daily usage. NOMAD uses this to calculate "Days Left."</td></tr>
  <tr><td>CBRN</td><td>Chemical, Biological, Radiological, Nuclear. A category of threats requiring specialized protective measures.</td></tr>
  <tr><td>Content Pack</td><td>A downloadable file containing offline reference material (Wikipedia articles, medical databases, survival guides, etc.).</td></tr>
  <tr><td>GCS (Glasgow Coma Scale)</td><td>A 3-15 score measuring consciousness. 15 = fully alert, &lt;9 = severe impairment, 3 = unresponsive.</td></tr>
  <tr><td>GPX</td><td>GPS Exchange Format. A standard file format for sharing waypoints and tracks between GPS devices and mapping software.</td></tr>
  <tr><td>hPa (hectopascal)</td><td>Unit of barometric pressure. Standard sea-level pressure is 1013 hPa. Falling pressure indicates approaching storms.</td></tr>
<tr><td>LAN</td><td>Local Area Network. Your home Wi-Fi network. NOMAD is accessible from any device on your LAN.</td></tr>
  <tr><td>Meshtastic</td><td>An open-source project for long-range, low-power mesh networking using inexpensive radio hardware. No cell towers needed.</td></tr>
<tr><td>Node</td><td>A single NOMAD installation. When syncing between multiple computers, each is called a "node."</td></tr>
  <tr><td>OPSEC</td><td>Operations Security. Practices to prevent adversaries from learning about your plans, capabilities, and vulnerabilities.</td></tr>
  <tr><td>Rally Point</td><td>A pre-designated meeting location for your family or group during an emergency.</td></tr>
  <tr><td>SITREP</td><td>Situation Report. A standardized format for summarizing the current state of an emergency or operation.</td></tr>
  <tr><td>SOC (State of Charge)</td><td>How full a battery is, expressed as a percentage (0-100%). Similar to your phone battery percentage.</td></tr>
  <tr><td>SpO2</td><td>Blood oxygen saturation level. Normal is 95-100%. Below 90% is a medical emergency.</td></tr>
  <tr><td>START Triage</td><td>Simple Triage and Rapid Treatment. A system for prioritizing multiple casualties: walk &rarr; breathe &rarr; pulse &rarr; mental status.</td></tr>
  <tr><td>Waypoint</td><td>A saved location on the map with coordinates, name, and optional notes.</td></tr>
  </table>

  <div class="guide-footer">
<strong>NOMAD Field Desk v${VERSION}</strong><br>
    <a href="https://www.projectnomad.us">Official site</a> &mdash;
    <a href="https://github.com/SysAdminDoc/project-nomad-desktop">GitHub</a> &mdash;
    <a href="https://discord.com/invite/crosstalksolutions">Discord Community</a><br><br>
    Built on the original Project N.O.M.A.D. foundation by Crosstalk Solutions. Desktop edition and ongoing expansion by SysAdminDoc.<br>
    <em>Knowledge that never goes offline.</em>
  </div>
  </body></html>`, section);
}

/* ─── Auto Backup ─── */
let _autoBackupTimer = null;
function saveAutoBackup() {
  const intervalInput = document.getElementById('auto-backup-interval');
  if (!intervalInput) return;
  const interval = parseInt(intervalInput.value);
  localStorage.setItem('nomad-auto-backup', interval);
  setupAutoBackup(interval);
}
function setupAutoBackup(interval) {
  if (_autoBackupTimer) { clearInterval(_autoBackupTimer); _autoBackupTimer = null; }
  window.NomadShellRuntime?.stopInterval('shell.auto-backup');
  if (interval > 0) {
    const runner = async () => {
      if (document.hidden) return;
      try {
        const resp = await apiFetch('/api/export-config');
        if (resp instanceof Response) toast('Auto backup completed', 'info');
      } catch(e) {}
    };
    if (window.NomadShellRuntime) {
      _autoBackupTimer = window.NomadShellRuntime.startInterval('shell.auto-backup', runner, interval * 1000, {
        requireVisible: true,
      });
      return;
    }
    _autoBackupTimer = setInterval(runner, interval * 1000);
  }
}
(function() {
  const interval = parseInt(localStorage.getItem('nomad-auto-backup') || '0');
  if (interval > 0) setupAutoBackup(interval);
  const el = document.getElementById('auto-backup-interval');
  if (el) el.value = interval;
})();

/* ─── AI Conversation Starters ─── */
function useStarter(text) {
  const chatInput = document.getElementById('chat-input');
  if (!chatInput) return;
  chatInput.value = text;
  sendChat();
}

/* ─── Note Pin/Tags ─── */
async function toggleNotePin() {
  if (!currentNoteId) return;
  const n = allNotes.find(n => n.id === currentNoteId);
  if (!n) return;
  const pinBtn = document.getElementById('note-pin-btn');
  if (!pinBtn) return;
  const newPinned = !n.pinned;
  try {
    await apiPost(`/api/notes/${currentNoteId}/pin`, {pinned:newPinned});
    n.pinned = newPinned;
    pinBtn.textContent = newPinned ? 'Unpin' : 'Pin';
    toast(newPinned ? 'Note pinned' : 'Note unpinned', 'success');
    await loadNotes();
  } catch(e) { console.error(e); toast(e?.data?.error || 'Failed to update note', 'error'); }
}

let _tagSaveTimer;
function autoSaveNoteTags() {
  clearTimeout(_tagSaveTimer);
  _tagSaveTimer = setTimeout(async () => {
    if (!currentNoteId) return;
    const tagsInput = document.getElementById('note-tags');
    if (!tagsInput) return;
    const tags = tagsInput.value;
    try {
      await apiPut('/api/notes/' + currentNoteId + '/tags', {tags});
      const n = allNotes.find(n => n.id === currentNoteId);
      if (n) n.tags = tags;
      renderNotesList();
    } catch(e) { toast('Failed to save tags', 'error'); }
  }, 500);
}

/* ─── Emergency Broadcast ─── */
async function sendBroadcast() {
  const messageInput = document.getElementById('bcast-msg');
  const severityInput = document.getElementById('bcast-severity');
  if (!messageInput || !severityInput) return;
  const msg = messageInput.value.trim();
  if (!msg) { toast('Enter a message', 'warning'); return; }
  const severity = severityInput.value;
  try {
    await apiPost('/api/broadcast', {message: msg, severity});
    toast('Broadcast sent to all LAN devices', 'warning');
    messageInput.value = '';
  } catch(e) { toast('Failed to send broadcast', 'error'); }
}

async function clearBroadcast() {
  try {
    await apiPost('/api/broadcast/clear');
    toast('Broadcast cleared');
    const banner = document.getElementById('broadcast-banner');
    if (banner) banner.style.display = 'none';
  } catch(e) { toast('Failed to clear broadcast', 'error'); }
}

let _dismissedBroadcastTs = null;
function dismissBroadcast() {
  _dismissedBroadcastTs = window._lastBroadcastTs;
  const banner = document.getElementById('broadcast-banner');
  if (banner) banner.style.display = 'none';
}

async function pollBroadcast() {
  const banner = document.getElementById('broadcast-banner');
  if (!banner) return;
  try {
    const b = await safeFetch('/api/broadcast', {}, null);
    if (!b) throw new Error('broadcast unavailable');
    if (b.active && b.message) {
      // Don't re-show a dismissed broadcast
      if (_dismissedBroadcastTs === b.timestamp) return;
      banner.classList.remove('severity-info', 'severity-warning', 'severity-critical');
      const sev = b.severity === 'warning' || b.severity === 'critical' ? b.severity : 'info';
      banner.classList.add('severity-' + sev);
      banner.style.display = 'block';
      banner.textContent = b.message;
      banner.title = 'Click to dismiss | ' + b.timestamp;
      // Play alert sound once per broadcast
      if (!window._lastBroadcastTs || window._lastBroadcastTs !== b.timestamp) {
        window._lastBroadcastTs = b.timestamp;
        playAlertSound('broadcast');
        sendNotification('Emergency Broadcast', b.message);
      }
    } else {
      banner.style.display = 'none';
      _dismissedBroadcastTs = null;
    }
  } catch(e) {
    banner?.classList.add('is-empty');
  }
}

/* ─── Resource Allocation Planner ─── */
async function calcPlan() {
  const peopleInput = document.getElementById('plan-people');
  const daysInput = document.getElementById('plan-days');
  const activityInput = document.getElementById('plan-activity');
  const resultEl = document.getElementById('plan-result');
  if (!peopleInput || !daysInput || !activityInput || !resultEl) return;
  const people = parseInt(peopleInput.value) || 4;
  const days = parseInt(daysInput.value) || 14;
  const activity = activityInput.value;
  try {
    const r = await safeFetch('/api/planner/calculate', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({people, days, activity})}, null);
    if (!r || !r.needs || !r.current_inventory) throw new Error('planner unavailable');
    const n = r.needs;
    const inv = r.current_inventory;
    resultEl.innerHTML = `
      <div class="planner-result-head">${people} people x ${days} days (${activity})</div>
      <div class="planner-result-grid">
        <div class="planner-result-item"><strong class="planner-result-label">Water:</strong> ${n.water_gal} gallons ${inv.water ? `<span class="planner-result-meta">(have: ${inv.water})</span>` : ''}</div>
        <div class="planner-result-item"><strong class="planner-result-label">Food:</strong> ${n.food_cal.toLocaleString()} total calories</div>
        <div class="planner-result-item"><strong class="planner-result-label">Rice/beans:</strong> ${n.food_lbs_rice} lbs dry staples</div>
        <div class="planner-result-item"><strong class="planner-result-label">Canned food:</strong> ~${n.food_cans} cans</div>
        <div class="planner-result-item"><strong class="planner-result-label">Toilet paper:</strong> ${n.tp_rolls} rolls</div>
        <div class="planner-result-item"><strong class="planner-result-label">Bleach:</strong> ${n.bleach_oz} oz (water treatment)</div>
        <div class="planner-result-item"><strong class="planner-result-label">Batteries (AA):</strong> ~${n.batteries_aa}</div>
        <div class="planner-result-item"><strong class="planner-result-label">Trash bags:</strong> ${n.trash_bags}</div>
        <div class="planner-result-item"><strong class="planner-result-label">First aid kits:</strong> ${n.first_aid_kits}</div>
      </div>`;
  } catch(e) { resultEl.innerHTML = 'Calculation failed.'; }
}

function calcFoodStorage() {
  const peopleInput = document.getElementById('fs-people');
  const monthsInput = document.getElementById('fs-months');
  const resultEl = document.getElementById('fs-result');
  if (!peopleInput || !monthsInput || !resultEl) return;
  const people = parseInt(peopleInput.value) || 4;
  const months = parseInt(monthsInput.value) || 3;
  const days = months * 30;
  // LDS/FEMA recommended quantities per adult per year, scaled
  const scale = days / 365;
  const items = [
    {name: 'Wheat/Flour', lbs: Math.round(300 * scale * people), note: 'Bread, tortillas, baking'},
    {name: 'Rice', lbs: Math.round(100 * scale * people), note: 'Staple grain, long shelf life'},
    {name: 'Corn/Cornmeal', lbs: Math.round(50 * scale * people), note: 'Cornbread, polenta, tortillas'},
    {name: 'Oats', lbs: Math.round(50 * scale * people), note: 'Breakfast, baking, thickener'},
    {name: 'Pasta', lbs: Math.round(40 * scale * people), note: 'Quick cooking, morale food'},
    {name: 'Dried Beans/Legumes', lbs: Math.round(60 * scale * people), note: 'Protein + fiber'},
    {name: 'Sugar', lbs: Math.round(60 * scale * people), note: 'Energy, preserving, baking'},
    {name: 'Honey', lbs: Math.round(12 * scale * people), note: 'Indefinite shelf life, medicine'},
    {name: 'Powdered Milk', lbs: Math.round(16 * scale * people), note: 'Calcium, protein'},
    {name: 'Cooking Oil', gal: Math.round(10 * scale * people * 10) / 10, note: 'Essential fats, cooking'},
    {name: 'Salt', lbs: Math.round(8 * scale * people), note: 'Seasoning, preservation'},
    {name: 'Peanut Butter', lbs: Math.round(12 * scale * people), note: 'Dense calories + protein'},
    {name: 'Canned Meat', cans: Math.round(120 * scale * people), note: 'Protein variety'},
    {name: 'Canned Vegetables', cans: Math.round(180 * scale * people), note: 'Vitamins, fiber'},
    {name: 'Canned Fruit', cans: Math.round(90 * scale * people), note: 'Vitamins, morale'},
    {name: 'Multivitamins', count: Math.round(days * people), note: '1 per person per day'},
    {name: 'Water', gal: Math.round(days * people * 1), note: '1 gal/person/day minimum'},
  ];
  const totalCal = Math.round(2000 * days * people);
  let html = `<div class="prep-calc-result-head">${people} people x ${months} months (${days} days) = ~${totalCal.toLocaleString()} total calories needed</div>`;
  html += '<div class="prep-table-wrap"><table class="ref-table prep-data-table prep-reference-table-compact"><thead><tr><th>Item</th><th>Amount</th><th>Notes</th></tr></thead><tbody>';
  for (const item of items) {
    const amt = item.lbs ? `${item.lbs} lbs` : item.gal ? `${item.gal} gal` : item.cans ? `${item.cans} cans` : `${item.count}`;
    html += `<tr><td><strong>${item.name}</strong></td><td><span class="prep-result-accent">${amt}</span></td><td><span class="prep-result-note-text">${item.note}</span></td></tr>`;
  }
  html += '</tbody></table></div>';
  html += '<div class="prep-reference-note prep-reference-note-tight">Based on LDS/FEMA long-term storage guidelines. Store in Mylar bags with O2 absorbers in 5-gallon buckets for 25+ year shelf life.</div>';
  resultEl.innerHTML = html;
}

function calcGenFuel() {
  const wattsInput = document.getElementById('gen-size');
  const fuelInput = document.getElementById('gen-fuel');
  const hoursInput = document.getElementById('gen-hours');
  const daysInput = document.getElementById('gen-days');
  const loadInput = document.getElementById('gen-load');
  const resultEl = document.getElementById('gen-result');
  if (!wattsInput || !fuelInput || !hoursInput || !daysInput || !loadInput || !resultEl) return;
  const watts = parseInt(wattsInput.value);
  const fuel = fuelInput.value;
  const hours = parseInt(hoursInput.value) || 8;
  const days = parseInt(daysInput.value) || 7;
  const load = parseInt(loadInput.value) || 50;
  // Fuel consumption rates (gal/hr at full load per 1000W)
  const rates = {
    gasoline: {per1kw: 0.75, unit: 'gallons', shelf: '3-6 months (1-2 yr w/ stabilizer)', weight: 6.3, container: '5-gal jerry cans'},
    diesel: {per1kw: 0.5, unit: 'gallons', shelf: '6-12 months (2+ yr w/ treatment)', weight: 7.1, container: '5-gal diesel cans'},
    propane: {per1kw: 1.0, unit: 'gallons', shelf: 'Indefinite (tank inspection needed)', weight: 4.2, container: '20-lb tanks (4.7 gal each)'},
    natgas: {per1kw: 130, unit: 'cubic feet', shelf: 'Continuous supply (utility dependent)', weight: 0, container: 'Utility line'}
  };
  const r = rates[fuel];
  const loadFactor = load / 100;
  const kw = watts / 1000;
  const totalHours = hours * days;
  let consumption, totalFuel;
  if (fuel === 'natgas') {
    consumption = r.per1kw * kw * loadFactor;
    totalFuel = Math.round(consumption * totalHours);
  } else {
    consumption = r.per1kw * kw * loadFactor;
    totalFuel = Math.round(consumption * totalHours * 10) / 10;
  }
  const perDay = fuel === 'natgas' ? Math.round(consumption * hours) : Math.round(consumption * hours * 10) / 10;
  const cards = [
    {label: 'Per Hour', value: `${fuel === 'natgas' ? Math.round(consumption) : Math.round(consumption*100)/100} ${r.unit}`},
    {label: `Per Day (${hours}h)`, value: `${perDay} ${r.unit}`},
    {label: `Total (${days} days)`, value: `${totalFuel} ${r.unit}`},
  ];
  if (fuel !== 'natgas') {
    const weight = Math.round(totalFuel * r.weight);
    cards.push({label: 'Weight', value: `~${weight} lbs`});
    if (fuel === 'propane') {
      const tanks = Math.ceil(totalFuel / 4.7);
      cards.push({label: '20-lb Tanks', value: `${tanks} tanks`});
    } else {
      const cans = Math.ceil(totalFuel / 5);
      cards.push({label: '5-gal Cans', value: `${cans} cans`});
    }
  }
  cards.push({label: 'Fuel Shelf Life', value: r.shelf});
  let html = `<div class="prep-calc-result-head">${watts.toLocaleString()}W Generator — ${fuel.charAt(0).toUpperCase()+fuel.slice(1)} @ ${load}% load</div>`;
  html += `<div class="utility-summary-result utility-summary-grid">${cards.map(card => `<div class="prep-summary-card utility-summary-card"><div class="prep-summary-label">${card.label}</div><div class="prep-summary-value prep-summary-value-compact">${card.value}</div></div>`).join('')}</div>`;
  html += `<div class="prep-reference-note">
    <strong>Common loads:</strong> Refrigerator 600W, Freezer 500W, Well Pump 1000W, Sump Pump 800W, Space Heater 1500W, Lights (LED) 10-15W each, Phone charger 5W, CPAP 30-60W, Window AC 500-1500W, Microwave 1000-1500W, TV 100-200W.
    <br><strong>Tip:</strong> Run generator 2-4 hours at a time to cycle fridge/freezer. A freezer stays frozen 24-48 hrs if kept closed. Cycle loads to reduce generator wear.
  </div>`;
  resultEl.innerHTML = html;
}

function calcRainwater() {
  const areaInput = document.getElementById('rw-area');
  const rainInput = document.getElementById('rw-rain');
  const efficiencyInput = document.getElementById('rw-roof');
  const peopleInput = document.getElementById('rw-people');
  const resultEl = document.getElementById('rw-result');
  if (!areaInput || !rainInput || !efficiencyInput || !peopleInput || !resultEl) return;
  const area = parseFloat(areaInput.value) || 1500;
  const rain = parseFloat(rainInput.value) || 1;
  const eff = parseFloat(efficiencyInput.value) || 0.9;
  const people = parseInt(peopleInput.value) || 4;
  // 1 inch of rain on 1 sq ft = 0.623 gallons
  const gallons = Math.round(area * rain * 0.623 * eff * 10) / 10;
  const liters = Math.round(gallons * 3.785 * 10) / 10;
  const personDays = Math.round(gallons / people * 10) / 10; // 1 gal/person/day
  // Annual estimate (US avg ~38" rainfall)
  const annualGal = Math.round(area * 38 * 0.623 * eff);
  const annualPersonDays = Math.round(annualGal / people);
  let html = `<div class="utility-summary-result utility-summary-grid">
    <div class="prep-summary-card utility-summary-card"><div class="prep-summary-label">Per ${rain}" rain</div><div class="prep-summary-value prep-summary-value-compact">${gallons} gallons (${liters} L)</div></div>
    <div class="prep-summary-card utility-summary-card"><div class="prep-summary-label">Days supply</div><div class="prep-summary-value prep-summary-value-compact">${personDays} days for ${people} people</div></div>
    <div class="prep-summary-card utility-summary-card"><div class="prep-summary-label">Annual est (38")</div><div class="prep-summary-value prep-summary-value-compact">${annualGal.toLocaleString()} gallons</div></div>
    <div class="prep-summary-card utility-summary-card"><div class="prep-summary-label">Annual supply</div><div class="prep-summary-value prep-summary-value-compact">${annualPersonDays} person-days</div></div>
  </div>`;
  html += `<div class="prep-reference-note prep-reference-note-tight">
    <strong>Storage:</strong> 55-gal drums ($15-30), IBC totes 275-gal ($50-100), cistern 500-5000 gal. First flush diverter recommended (discard first 10 gal after dry spell).
    <strong>Purification:</strong> Roof water must be filtered + disinfected. Ceramic filter → UV or bleach (8 drops/gal). First-flush diverter discards debris.
    <strong>Legal:</strong> Rainwater harvesting is legal in most US states but some have restrictions — check local laws.
  </div>`;
  resultEl.innerHTML = html;
}

function calcRadioRange() {
  const typeInput = document.getElementById('rr-type');
  const terrainInput = document.getElementById('rr-terrain');
  const heightInput = document.getElementById('rr-height');
  const resultEl = document.getElementById('rr-result');
  if (!typeInput || !terrainInput || !heightInput || !resultEl) return;
  const type = typeInput.value;
  const terrain = terrainInput.value;
  const height = parseInt(heightInput.value) || 6;
  // Base ranges in miles (ideal conditions)
  const bases = {
    'frs': {base: 1, band: 'UHF 462 MHz', license: 'None', note: 'Bubble-pack radios. Very limited.'},
    'gmrs': {base: 5, band: 'UHF 462 MHz', license: 'FCC GMRS ($35, 10yr)', note: 'Good family/group radio. Repeater-capable.'},
    'gmrs-mobile': {base: 15, band: 'UHF 462 MHz', license: 'FCC GMRS ($35, 10yr)', note: 'Vehicle-mount with better antenna.'},
    '2m-ht': {base: 7, band: 'VHF 144 MHz', license: 'Ham Technician', note: 'Most popular prepper radio. Repeater access.'},
    '2m-mobile': {base: 25, band: 'VHF 144 MHz', license: 'Ham Technician', note: 'Vehicle-mount. Great simplex range.'},
    '2m-base': {base: 50, band: 'VHF 144 MHz', license: 'Ham Technician', note: 'Directional antenna. Point-to-point.'},
    'hf-20m': {base: 2000, band: 'HF 14 MHz', license: 'Ham General', note: 'Worldwide daytime. Skip zone 100-500mi.'},
    'hf-40m': {base: 1000, band: 'HF 7 MHz', license: 'Ham General', note: 'Regional day, continental night. Most versatile HF.'},
    'hf-80m': {base: 300, band: 'HF 3.5 MHz', license: 'Ham General', note: 'Night-only effective. Regional comms. NVIS capable.'},
    'cb': {base: 3, band: 'HF 27 MHz', license: 'None', note: 'Truckers, Channel 9 emergency, Channel 19 highway.'},
    'murs': {base: 3, band: 'VHF 151 MHz', license: 'None', note: 'Better building penetration than FRS. Low profile.'},
    'meshtastic': {base: 5, band: '915 MHz LoRa', license: 'None', note: 'Encrypted text mesh. Nodes relay messages. Solar-powered.'}
  };
  const terrainMult = {urban: 0.3, suburban: 0.5, rural: 1.0, mountains: 0.4, forest: 0.5, water: 1.5, hilltop: 2.0};
  const r = bases[type];
  const mult = terrainMult[terrain] || 1;
  // Height bonus (VHF/UHF benefit from height, HF not so much)
  const isHF = type.startsWith('hf-');
  const heightMult = isHF ? 1 : Math.min(1 + (height - 6) * 0.01, 3);
  const range = Math.round(r.base * mult * heightMult * 10) / 10;
  let html = `<div class="utility-summary-result utility-summary-grid">
    <div class="prep-summary-card utility-summary-card"><div class="prep-summary-label">Est. Range</div><div class="prep-summary-value prep-summary-value-compact">${range >= 100 ? Math.round(range) : range} miles</div></div>
    <div class="prep-summary-card utility-summary-card"><div class="prep-summary-label">Band</div><div class="prep-summary-value prep-summary-value-compact">${r.band}</div></div>
    <div class="prep-summary-card utility-summary-card"><div class="prep-summary-label">License</div><div class="prep-summary-value prep-summary-value-compact">${r.license}</div></div>
    <div class="prep-summary-card utility-summary-card"><div class="prep-summary-label">Notes</div><div class="prep-summary-value prep-summary-value-compact">${r.note}</div></div>
  </div>`;
  html += `<div class="prep-reference-note prep-reference-note-tight">
    Range is estimated. Actual range depends on terrain, weather, antenna quality, and interference. <strong>Repeaters</strong> can extend VHF/UHF range to 50-100+ miles. <strong>NVIS</strong> (Near Vertical Incidence Skywave) on 40m/80m gives 0-300 mile coverage with horizontal antenna — fills the HF skip zone. In emergencies, you may transmit on any frequency (FCC §97.405).
  </div>`;
  resultEl.innerHTML = html;
}

function calcMedDose() {
  const weightInput = document.getElementById('md-weight');
  const unitInput = document.getElementById('md-unit');
  const ageInput = document.getElementById('md-age');
  const resultEl = document.getElementById('md-result');
  if (!weightInput || !unitInput || !ageInput || !resultEl) return;
  const weight = parseFloat(weightInput.value) || 150;
  const unit = unitInput.value;
  const age = ageInput.value;
  const kg = unit === 'kg' ? weight : weight / 2.205;
  const lbs = unit === 'lbs' ? weight : weight * 2.205;

  const meds = [];
  if (age === 'adult') {
    meds.push({name: 'Ibuprofen', dose: '200-400mg', freq: 'Every 6-8 hours', max: '1,200mg/day OTC (3,200mg Rx)', warn: 'Take with food. Avoid if kidney disease or GI bleeding.'});
    meds.push({name: 'Acetaminophen', dose: '500-1,000mg', freq: 'Every 6 hours', max: '3,000mg/day', warn: 'Liver toxic in overdose. No alcohol. Check combo products (NyQuil etc).'});
    meds.push({name: 'Aspirin', dose: '325-650mg', freq: 'Every 4-6 hours', max: '4,000mg/day', warn: 'Heart attack: chew 325mg immediately. Blood thinner — avoid before surgery.'});
    meds.push({name: 'Diphenhydramine', dose: '25-50mg', freq: 'Every 6-8 hours', max: '300mg/day', warn: 'Causes drowsiness. Anticholinergic — avoid in elderly.'});
    meds.push({name: 'Loperamide', dose: '4mg initial, then 2mg', freq: 'After each loose stool', max: '8mg/day OTC', warn: 'Do NOT use if bloody diarrhea or fever (may be infectious).'});
    meds.push({name: 'Epinephrine (auto)', dose: '0.3mg IM', freq: 'Repeat in 5-15 min if needed', max: 'No max in anaphylaxis', warn: 'Mid-outer thigh, through clothing OK. Call for help immediately.'});
    meds.push({name: 'Amoxicillin', dose: '500mg', freq: 'Every 8 hours', max: '1,500mg/day', warn: 'Complete full course (7-10 days). Rash ≠ always allergy (but stop if hives/swelling).'});
    meds.push({name: 'Ivermectin', dose: `${Math.round(kg * 0.2 * 10) / 10}mg (0.2mg/kg)`, freq: 'Single dose', max: 'Repeat in 2 weeks for parasites', warn: `Based on ${Math.round(kg)}kg body weight.`});
  } else if (age === 'child') {
    const ibuDose = Math.round(kg * 10); // 10mg/kg
    const acetDose = Math.round(kg * 15); // 15mg/kg
    const benadrylDose = Math.round(kg * 1.25 * 10) / 10; // 1.25mg/kg
    meds.push({name: 'Ibuprofen (Children\'s)', dose: `${ibuDose}mg (10mg/kg)`, freq: 'Every 6-8 hours', max: `${Math.round(kg * 40)}mg/day`, warn: `Based on ${Math.round(kg)}kg. Use liquid form for accuracy.`});
    meds.push({name: 'Acetaminophen (Children\'s)', dose: `${acetDose}mg (15mg/kg)`, freq: 'Every 4-6 hours', max: `${Math.round(kg * 75)}mg/day (5 doses)`, warn: 'Use dosing syringe, not kitchen spoons.'});
    meds.push({name: 'Diphenhydramine', dose: `${benadrylDose}mg (1.25mg/kg)`, freq: 'Every 6-8 hours', max: `${Math.round(benadrylDose * 4)}mg/day`, warn: 'May cause excitability in children. Liquid preferred.'});
    meds.push({name: 'Amoxicillin (Peds)', dose: `${Math.round(kg * 25)}mg (25mg/kg)`, freq: 'Every 8 hours', max: `${Math.round(kg * 75)}mg/day`, warn: 'Use suspension. Shake well. Complete full course.'});
    meds.push({name: 'ORS (Oral Rehydration)', dose: '50-100ml', freq: 'After each loose stool', max: 'As needed', warn: 'DIY: 1L water + 6 tsp sugar + 0.5 tsp salt. Sip slowly.'});
  } else {
    meds.push({name: 'Acetaminophen Infant Drops', dose: `${Math.round(kg * 15)}mg (15mg/kg)`, freq: 'Every 4-6 hours', max: `${Math.round(kg * 75)}mg/day`, warn: 'Use infant concentration + dosing syringe only.'});
    meds.push({name: 'Ibuprofen (6+ months only)', dose: `${Math.round(kg * 10)}mg (10mg/kg)`, freq: 'Every 6-8 hours', max: `${Math.round(kg * 40)}mg/day`, warn: 'NOT for infants under 6 months. Use with food.'});
    meds.push({name: 'ORS (Oral Rehydration)', dose: '50ml', freq: 'After each loose stool', max: 'As needed', warn: 'Teaspoon at a time if vomiting. Pedialyte or DIY recipe.'});
    meds.push({name: 'Epinephrine (infant auto)', dose: '0.15mg IM', freq: 'Repeat in 5-15 min', max: 'No max in anaphylaxis', warn: 'EpiPen Jr for <30kg. Mid-outer thigh.'});
  }

  let html = `<div class="prep-calc-result-head"><strong>Patient:</strong> ${Math.round(lbs)} lbs / ${Math.round(kg)} kg — ${age === 'adult' ? 'Adult' : age === 'child' ? 'Child (2-11)' : 'Infant (6mo-2yr)'}</div>`;
  html += '<div class="prep-table-wrap"><table class="ref-table prep-data-table prep-reference-table-compact"><thead><tr><th>Medication</th><th>Dose</th><th>Frequency</th><th>Max Daily</th><th>Warning</th></tr></thead><tbody>';
  for (const m of meds) {
    html += `<tr><td><strong>${m.name}</strong></td><td><span class="prep-result-accent">${m.dose}</span></td><td>${m.freq}</td><td>${m.max}</td><td><span class="prep-result-note-text">${m.warn}</span></td></tr>`;
  }
  html += '</tbody></table></div>';
  html += '<div class="prep-reference-note prep-reference-note-tight"><strong>DISCLAIMER:</strong> For reference only. Consult a medical professional when possible. Doses may vary based on individual health conditions, allergies, and other medications.</div>';
  resultEl.innerHTML = html;
}

function calcSolarSize() {
  const dailyWhInput = document.getElementById('sol-wh');
  const sunHoursInput = document.getElementById('sol-sun');
  const batteryTypeInput = document.getElementById('sol-batt');
  const autonomyInput = document.getElementById('sol-days');
  const resultEl = document.getElementById('sol-size-result');
  if (!dailyWhInput || !sunHoursInput || !batteryTypeInput || !autonomyInput || !resultEl) return;
  const dailyWh = parseInt(dailyWhInput.value) || 3000;
  const sunHrs = parseInt(sunHoursInput.value) || 4;
  const battType = batteryTypeInput.value;
  const autoDays = parseInt(autonomyInput.value) || 2;

  const battInfo = {lifepo4: {dod: 0.8, volt: 12.8, life: '10+ years', cost: '$$$$'}, agm: {dod: 0.5, volt: 12, life: '3-5 years', cost: '$$'}, flooded: {dod: 0.5, volt: 12, life: '3-7 years', cost: '$'}};
  const b = battInfo[battType];
  const panelWatts = Math.ceil((dailyWh / sunHrs) * 1.25);
  const numPanels = Math.ceil(panelWatts / 400);
  const actualPanelW = numPanels * 400;
  const battWh = Math.ceil((dailyWh * autoDays) / b.dod);
  const battAh = Math.ceil(battWh / b.volt);
  const num100Ah = Math.ceil(battAh / 100);
  const inverterW = Math.ceil(dailyWh / 8 * 1.5 / 100) * 100;
  const ccAmps = Math.ceil(actualPanelW / b.volt * 1.25);

  let html = `<div class="utility-summary-result utility-summary-grid">`;
  html += `<div class="prep-summary-card utility-summary-card">
    <div class="prep-summary-meta">Solar Panels</div>
    <div class="prep-summary-value prep-summary-value-compact">${actualPanelW}W</div>
    <div class="prep-summary-label">${numPanels}x 400W panels</div>
  </div>`;
  html += `<div class="prep-summary-card utility-summary-card">
    <div class="prep-summary-meta">Battery Bank</div>
    <div class="prep-summary-value prep-summary-value-compact">${battWh}Wh</div>
    <div class="prep-summary-label">${battAh}Ah (${num100Ah}x 100Ah ${battType.toUpperCase()})</div>
  </div>`;
  html += `<div class="prep-summary-card utility-summary-card">
    <div class="prep-summary-meta">Inverter</div>
    <div class="prep-summary-value prep-summary-value-compact">${inverterW}W+</div>
    <div class="prep-summary-label">Pure sine wave recommended</div>
  </div>`;
  html += `<div class="prep-summary-card utility-summary-card">
    <div class="prep-summary-meta">Charge Controller</div>
    <div class="prep-summary-value prep-summary-value-compact">${ccAmps}A</div>
    <div class="prep-summary-label">MPPT recommended</div>
  </div>`;
  html += `<div class="prep-summary-card utility-summary-card">
    <div class="prep-summary-meta">Battery Life</div>
    <div class="prep-summary-value prep-summary-value-compact">${escapeHtml(b.life)}</div>
    <div class="prep-summary-label">Expected service window</div>
  </div>`;
  html += `<div class="prep-summary-card utility-summary-card">
    <div class="prep-summary-meta">Autonomy</div>
    <div class="prep-summary-value prep-summary-value-compact">${autoDays} day${autoDays === 1 ? '' : 's'}</div>
    <div class="prep-summary-label">Without sun</div>
  </div>`;
  html += `</div>`;
  html += `<div class="prep-reference-note prep-reference-note-tight">
    <strong>Common loads:</strong> Fridge 150Wh/hr x 8hr = 1,200Wh/day | Lights (LED) 10W x 5hr = 50Wh | Laptop 50W x 4hr = 200Wh | Phone 20Wh | Well pump 1000W x 1hr = 1,000Wh | CPAP 40W x 8hr = 320Wh
    <br><strong>Tips:</strong> MPPT controllers 20-30% more efficient than PWM. LiFePO4 costs more but lasts 3x longer. Tilt panels to latitude angle.
  </div>`;
  resultEl.innerHTML = html;
}

const BOB_ITEMS = [
  {cat:'Water',items:[{n:'Water bottles (2L)',w:4.4},{n:'Water filter (Sawyer)',w:0.2},{n:'Purification tabs',w:0.1}]},
  {cat:'Shelter',items:[{n:'Tarp (8x10)',w:1.5},{n:'Paracord (100ft)',w:0.6},{n:'Emergency bivy',w:0.7},{n:'Sleeping bag',w:2.5}]},
  {cat:'Fire',items:[{n:'Ferro rod + striker',w:0.2},{n:'Bic lighters (x2)',w:0.1},{n:'Tinder (cotton+vaseline)',w:0.2},{n:'Stormproof matches',w:0.1}]},
  {cat:'Food',items:[{n:'MREs/freeze-dried (3 day)',w:4.0},{n:'Energy bars (x6)',w:1.2},{n:'Trail mix (1 lb)',w:1.0},{n:'Coffee/tea',w:0.3}]},
  {cat:'First Aid',items:[{n:'IFAK (trauma kit)',w:1.5},{n:'Personal meds',w:0.5},{n:'Tourniquet (CAT)',w:0.2},{n:'SAM splint',w:0.3}]},
  {cat:'Tools',items:[{n:'Fixed-blade knife',w:0.8},{n:'Multi-tool',w:0.5},{n:'Headlamp + batteries',w:0.3},{n:'Duct tape (mini)',w:0.3},{n:'Compass + map',w:0.3}]},
  {cat:'Clothing',items:[{n:'Rain jacket',w:0.8},{n:'Warm layer (fleece)',w:1.0},{n:'Extra socks (x2)',w:0.4},{n:'Gloves + hat',w:0.3},{n:'Bandana/shemagh',w:0.2}]},
  {cat:'Comms',items:[{n:'Ham radio HT',w:0.8},{n:'Phone+charger+bank',w:1.0},{n:'Whistle',w:0.05},{n:'Signal mirror',w:0.1},{n:'Notebook+pencil',w:0.2}]},
  {cat:'Defense',items:[{n:'Pepper spray',w:0.3},{n:'Firearm + ammo',w:3.5}]},
  {cat:'Docs',items:[{n:'ID/insurance copies',w:0.2},{n:'Cash (small bills)',w:0.1},{n:'USB drive (encrypted)',w:0.05}]},
];

function renderBOBChecklist() {
  const el = document.getElementById('bob-checklist');
  if (!el) return;
  el.innerHTML = BOB_ITEMS.map(cat => `
    <div class="prep-calc-checklist-card">
      <div class="prep-calc-checklist-head">${cat.cat}</div>
      ${cat.items.map(item => `
        <label class="prep-calc-checklist-entry">
          <input type="checkbox" class="bob-item" data-weight="${item.w}" data-change-action="calc-bob">
          <span>${item.n}</span>
          <span class="prep-calc-checklist-weight">${item.w}lb</span>
        </label>
      `).join('')}
    </div>
  `).join('');
}

function calcBOB() {
  if (!document.querySelector('.bob-item')) renderBOBChecklist();
  if (!document.querySelector('.bob-item')) return;
  const bodyWeightInput = document.getElementById('bob-bodyweight');
  const resultEl = document.getElementById('bob-result');
  if (!bodyWeightInput || !resultEl) return;
  const bodyWeight = parseInt(bodyWeightInput.value) || 180;
  let totalWeight = 0, checkedCount = 0;
  document.querySelectorAll('.bob-item').forEach(cb => {
    if (cb.checked) { totalWeight += parseFloat(cb.dataset.weight); checkedCount++; }
  });
  totalWeight = Math.round(totalWeight * 10) / 10;
  const pct = Math.round(totalWeight / bodyWeight * 100);
  const target15 = Math.round(bodyWeight * 0.15);
  const target25 = Math.round(bodyWeight * 0.25);
  const toneClass = pct <= 15 ? 'prep-summary-card-ok' : pct <= 25 ? 'prep-summary-card-warn' : 'prep-summary-card-danger';
  let html = `<div class="utility-summary-result utility-summary-grid">`;
  html += `<div class="prep-summary-card utility-summary-card ${toneClass}">
    <div class="prep-summary-meta">Pack Weight</div>
    <div class="prep-summary-value prep-summary-value-compact">${totalWeight} lbs</div>
    <div class="prep-summary-label">${pct}% body weight</div>
  </div>`;
  html += `<div class="prep-summary-card utility-summary-card">
    <div class="prep-summary-meta">Target Range</div>
    <div class="prep-summary-value prep-summary-value-compact">${target15}-${target25} lbs</div>
    <div class="prep-summary-label">15-25% of body weight</div>
  </div>`;
  html += `<div class="prep-summary-card utility-summary-card">
    <div class="prep-summary-meta">Items Checked</div>
    <div class="prep-summary-value prep-summary-value-compact">${checkedCount}</div>
    <div class="prep-summary-label">Selected from current checklist</div>
  </div>`;
  html += `</div>`;
  if (pct > 25) html += `<div class="prep-reference-callout prep-reference-callout-danger">Pack too heavy for sustained travel. Remove non-essentials or reduce quantities.</div>`;
  resultEl.innerHTML = html;
}

/* ─── Quick Actions ─── */
let _qaOpen = false;
function toggleQuickActions() {
  _qaOpen = !_qaOpen;
  const menu = document.getElementById('quick-actions-menu');
  const button = document.getElementById('copilot-utility-actions-btn');
  if (_qaOpen) {
    _lanChatOpen = false;
    setShellVisibility(document.getElementById('lan-chat-panel'), false);
    setUtilityDockButtonExpanded('chat', false);
    if (typeof stopLanMessagePolling === 'function') stopLanMessagePolling();
    else if (_lanPoll) { clearInterval(_lanPoll); _lanPoll = null; }
    if (typeof stopLanPresencePolling === 'function') stopLanPresencePolling();
    _timerPanelOpen = false;
    setShellVisibility(document.getElementById('timer-panel'), false);
    setUtilityDockButtonExpanded('timer', false);
    if (typeof stopTimerPolling === 'function') stopTimerPolling();
    else if (_timerPoll) { clearInterval(_timerPoll); _timerPoll = null; }
  }
  setShellVisibility(menu, _qaOpen);
  if (button) button.setAttribute('aria-expanded', _qaOpen ? 'true' : 'false');
}
function quickLogIncident() {
  toggleQuickActions();
  document.querySelector('[data-tab="preparedness"]')?.click();
  setTimeout(() => switchPrepSub('incidents'), 200);
}
function quickAddInventory() {
  toggleQuickActions();
  document.querySelector('[data-tab="preparedness"]')?.click();
  setTimeout(() => { switchPrepSub('inventory'); showInvForm(); }, 200);
}
function quickWeatherObs() {
  toggleQuickActions();
  document.querySelector('[data-tab="preparedness"]')?.click();
  setTimeout(() => switchPrepSub('weather'), 200);
}
function quickNewNote() {
  toggleQuickActions();
  document.querySelector('[data-tab="notes"]')?.click();
  setTimeout(createNote, 200);
}

/* ─── Password Generator ─── */
function generatePassword() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%&*';
  const arr = new Uint32Array(20);
  crypto.getRandomValues(arr);
  const pw = Array.from(arr).map(n => chars[n % chars.length]).join('');
  navigator.clipboard.writeText(pw).then(() => toast('Password copied to clipboard: ' + pw.slice(0,8) + '...', 'success')).catch(e => { console.error(e); toast('Failed to copy password to clipboard', 'error'); });
  // Also put it in the vault content if form is open
  const content = document.getElementById('vault-content');
  if (content && document.getElementById('vault-form').style.display !== 'none') {
    content.value = (content.value ? content.value + '\n\n' : '') + 'Generated Password: ' + pw;
  }
}

/* ─── Shareable Data Display ─── */
function generateQR(text) {
  const body = `<div class="shareable-data-block">${escapeHtml(text)}</div>
    <div class="modal-footer">
      <button type="button" class="btn btn-sm btn-primary" data-shell-action="copy-text" data-copy-text="${escapeAttr(text)}">Copy</button>
      <button type="button" class="btn btn-sm" data-shell-action="close-modal-overlay">Close</button>
    </div>`;
  showModal(body, {title: 'Shareable Data', size: 'sm'});
}

/* ─── Waypoint Distance Matrix UI ─── */
async function loadWPDistances() {
  try {
    const d = await apiFetch('/api/waypoints/distances');
    const el = document.getElementById('wp-distance-matrix');
    if (!d.points.length) { el.innerHTML = '<div class="workspace-empty-copy runtime-empty-note"><strong>No Waypoints Yet</strong><span>Save at least two waypoints from the live map to compare travel distance across your key locations.</span></div>'; return; }
    let html = '<table class="freq-table"><thead><tr><th></th>';
    d.points.forEach(p => html += `<th class="runtime-table-head-compact" title="${escapeHtml(p.name)}">${escapeHtml(p.name.slice(0,8))}</th>`);
    html += '</tr></thead><tbody>';
    d.points.forEach((p, i) => {
      html += `<tr><td class="runtime-table-label-compact">${escapeHtml(p.name)}</td>`;
      d.matrix[i].forEach((dist, j) => {
        const toneClass = i === j ? '' : dist < 1 ? ' text-green' : dist < 5 ? '' : dist < 20 ? ' text-orange' : ' text-red';
        html += `<td class="runtime-table-cell-compact runtime-table-cell-center${toneClass}">${i === j ? '-' : dist + 'mi'}</td>`;
      });
      html += '</tr>';
    });
    html += '</tbody></table>';
    el.innerHTML = html;
  } catch(e) {
    block?.classList.add('is-empty');
  }
}

/* ─── Service Quick Links ─── */
async function loadServiceQuickLinks(servicesData = null) {
  const el = document.getElementById('svc-quicklinks');
  if (!el) return;
  const block = el.closest('.services-console-block');
  try {
    const services = Array.isArray(servicesData)
      ? servicesData
      : await apiFetch('/api/services');
    const running = services.filter(s => s.running && s.port);
    if (!running.length) {
      el.innerHTML = '';
      block?.classList.add('is-empty');
      return;
    }
    block?.classList.remove('is-empty');
    const names = {ollama:'AI Chat',kiwix:'Library',cyberchef:'CyberChef',kolibri:'Kolibri',stirling:'PDF Tools'};
    el.innerHTML = running.filter(s => s.id !== 'qdrant').map(s => {
      if (s.id === 'ollama') return `<button class="btn btn-sm btn-open-svc btn-open-svc-compact" data-tab-target="ai-chat">Open AI Chat</button>`;
      return `<button class="btn btn-sm btn-open-svc btn-open-svc-compact" data-app-frame-title="${names[s.id]||s.id}" data-app-frame-url="http://localhost:${s.port}">Open ${names[s.id]||s.id}</button>`;
    }).join('');
  } catch(e) {}
}

/* ─── Dashboard Checklist Progress ─── */
async function loadCmdChecklists() {
  const el = document.getElementById('cmd-checklists');
  if (!el) return;
  const block = el.closest('.services-console-block');
  try {
    const cls = await safeFetch('/api/dashboard/checklists', {}, []);
    if (!cls.length) {
      el.innerHTML = '';
      block?.classList.add('is-empty');
      return;
    }
    block?.classList.remove('is-empty');
    el.innerHTML = '<div class="cmd-checklist-list">' + cls.map(c => {
      const color = c.pct === 100 ? 'var(--green)' : c.pct >= 50 ? 'var(--accent)' : 'var(--orange)';
      return `<div class="cmd-checklist-shortcut cmd-checklist-card" role="button" tabindex="0" data-tab-target="preparedness" data-prep-sub="checklists" data-checklist-focus="${c.id}" style="--checklist-pct:${c.pct}%;--checklist-tone:${color};">
        <div class="cmd-checklist-title">${escapeHtml(c.name)}</div>
        <div class="cmd-checklist-progress"><div class="cmd-checklist-progress-bar"></div></div>
        <div class="cmd-checklist-meta">${c.checked}/${c.total} (${c.pct}%)</div>
      </div>`;
    }).join('') + '</div>';
  } catch(e) {}
}

/* ─── Keyboard Shortcuts (Alt combos) ─── */
document.addEventListener('keydown', (e) => {
  // Only if not typing in an input/textarea
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
  if (e.altKey) {
      const shortcuts = {'1':'services','2':'readiness','3':'preparedness','4':'ai-chat','5':'kiwix-library','6':'maps','7':'notes','8':'media','9':'settings'};
    const tab = shortcuts[e.key];
    if (tab) { e.preventDefault(); document.querySelector(`[data-tab="${tab}"]`)?.click(); }
    if (e.key === 't') { e.preventDefault(); toggleTimerPanel(); }
    if (e.key === 'c') { e.preventDefault(); toggleLanChat(); }
    if (e.key === 'n') { e.preventDefault(); document.querySelector('[data-tab="notes"]')?.click(); setTimeout(createNote, 200); }
  }
  if (e.key === '?' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) {
    toggleShortcutsHelp();
  }
});

let _shortcutsReturnFocus = null;

function toggleShortcutsHelp(force) {
  const el = document.getElementById('shortcuts-overlay');
  if (!el) return;
  const show = typeof force === 'boolean' ? force : !isShellVisible(el);
  if (show) {
    _shortcutsReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setShellVisibility(el, true);
    requestAnimationFrame(() => el.querySelector('.shortcuts-close')?.focus());
    return;
  }
  setShellVisibility(el, false);
  const returnFocus = _shortcutsReturnFocus;
  _shortcutsReturnFocus = null;
  if (returnFocus && returnFocus.isConnected && typeof returnFocus.focus === 'function') {
    requestAnimationFrame(() => returnFocus.focus());
  }
}

/* ─── Daily Journal ─── */
async function loadJournal() {
  const el = document.getElementById('journal-list');
  if (!el) return;
  try {
    const entries = await safeFetch('/api/journal', {}, null);
    if (!Array.isArray(entries)) throw new Error('journal unavailable');
    if (!entries.length) {
      el.innerHTML = '<div class="settings-empty-state journal-empty-state">No journal entries yet. Start recording your daily observations above.</div>';
      return;
    }
    el.innerHTML = entries.map(e => {
      const t = new Date(e.created_at);
      const date = t.toLocaleDateString([], {weekday:'short', month:'short', day:'numeric'});
      const time = t.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
      const moodColors = {good:'var(--green)',okay:'var(--accent)',stressed:'var(--orange)',alert:'var(--red)',tired:'var(--text-muted)',motivated:'var(--accent)'};
      const moodBadge = e.mood ? `<span class="journal-mood-badge" style="--journal-mood-tone:${moodColors[e.mood]||'var(--text-dim)'};">${e.mood}</span>` : '';
      const tagBadges = e.tags ? e.tags.split(',').map(t => t.trim()).filter(Boolean).map(t => `<span class="journal-tag-badge">${escapeHtml(t)}</span>`).join('') : '';
      return `<div class="contact-card journal-card">
        <div class="journal-card-head">
          <div class="journal-card-meta">
            <span class="journal-card-date">${date}</span>
            <span class="journal-card-time">${time}</span>
            ${moodBadge}
            <span class="journal-card-tags">${tagBadges}</span>
          </div>
          <button type="button" class="incident-del" data-prep-action="delete-journal-entry" data-journal-entry-id="${e.id}" aria-label="Delete journal entry">x</button>
        </div>
        <div class="journal-entry-copy">${escapeHtml(e.entry)}</div>
      </div>`;
    }).join('');
  } catch(e) {
    el.innerHTML = '<div class="journal-error">Failed to load journal</div>';
  }
}

async function submitJournal() {
  const entryInput = document.getElementById('journal-entry');
  const moodInput = document.getElementById('journal-mood');
  const tagsInput = document.getElementById('journal-tags');
  if (!entryInput || !moodInput || !tagsInput) return;
  const entry = entryInput.value.trim();
  if (!entry) { toast('Write something first', 'warning'); return; }
  const mood = moodInput.value;
  const tags = tagsInput.value.trim();
  try {
    await apiPost('/api/journal', {entry, mood, tags});
    entryInput.value = '';
    moodInput.value = '';
    tagsInput.value = '';
    toast('Journal entry logged', 'success');
    loadJournal();
  } catch(e) { toast('Failed to save entry', 'error'); }
}

function exportJournal() {
  window.location = '/api/journal/export';
}

async function deleteJournalEntry(id) {
  if (!confirm('Delete this journal entry?')) return;
  try {
    await apiDelete(`/api/journal/${id}`);
    toast('Entry deleted', 'warning');
    loadJournal();
  } catch(e) { toast(e?.data?.error || 'Failed to delete entry', 'error'); }
}

/* ─── Security Module ─── */
function prepMetricCard(label, value, tone = 'var(--accent)', meta = '') {
  return `<div class="prep-metric-card" style="--prep-tone:${tone};">
    <div class="prep-metric-label">${label}</div>
    <div class="prep-metric-value">${value}</div>
    ${meta ? `<div class="prep-metric-meta">${meta}</div>` : ''}
  </div>`;
}

function prepEmptyBlock(message) {
  return `<div class="prep-table-empty prep-empty-block">${message}</div>`;
}

let _cameraRefreshTimers = {};
let _cameraSnapshotCameras = [];

function isSecurityCameraPanelActive() {
  const prepRoot = document.getElementById('tab-preparedness');
  const cameraPanel = document.getElementById('security-cameras-panel');
  if (!cameraPanel) return false;
  const prepVisible = !prepRoot || prepRoot.classList.contains('active');
  return prepVisible && getComputedStyle(cameraPanel).display !== 'none';
}

function refreshSnapshotCameraFeeds() {
  if (!isSecurityCameraPanelActive()) return;
  _cameraSnapshotCameras.forEach(c => {
    const img = document.getElementById(`cam-feed-${c.id}`);
    if (img) img.src = `${c.url}?t=${Date.now()}`;
  });
}

function stopCameraSnapshotRefresh() {
  Object.values(_cameraRefreshTimers).forEach(t => clearInterval(t));
  _cameraRefreshTimers = {};
  window.NomadShellRuntime?.stopInterval('preparedness.camera-snapshots');
}

function startCameraSnapshotRefresh(cameras) {
  stopCameraSnapshotRefresh();
  _cameraSnapshotCameras = Array.isArray(cameras)
    ? cameras.filter(c => c.stream_type === 'snapshot')
    : [];
  if (!_cameraSnapshotCameras.length) return;
  if (window.NomadShellRuntime) {
    _cameraRefreshTimers.runtime = window.NomadShellRuntime.startInterval('preparedness.camera-snapshots', refreshSnapshotCameraFeeds, 5000, {
      tabId: 'preparedness',
      requireVisible: true,
    });
    return;
  }
  _cameraRefreshTimers.fallback = setInterval(refreshSnapshotCameraFeeds, 5000);
}

function showSecurityTab(tab) {
  ['cameras','access'].forEach(t => {
    const panel = document.getElementById(`security-${t}-panel`);
    const tabBtn = document.getElementById(`sec-tab-${t}`);
    if (!panel || !tabBtn) return;
    panel.style.display = t === tab ? 'block' : 'none';
    tabBtn.className = t === tab ? 'btn btn-sm prep-utility-tab prep-utility-tab-active' : 'btn btn-sm prep-utility-tab';
  });
  if (tab === 'cameras') { loadCameras(); loadMotionStatus(); _startMotionPolling(); }
  else { _stopMotionPolling(); stopCameraSnapshotRefresh(); }
  if (tab === 'access') loadAccessLog();
}

function _startMotionPolling() {
  _stopMotionPolling();
  const runner = () => { if (isSecurityCameraPanelActive()) loadMotionStatus(); };
  if (window.NomadShellRuntime) {
    _motionStatusInterval = window.NomadShellRuntime.startInterval('preparedness.motion-status', runner, 10000, {
      tabId: 'preparedness',
      requireVisible: true,
    });
    return;
  }
  _motionStatusInterval = setInterval(runner, 10000);
}
function _stopMotionPolling() {
  if (_motionStatusInterval) { clearInterval(_motionStatusInterval); _motionStatusInterval = null; }
  window.NomadShellRuntime?.stopInterval('preparedness.motion-status');
}

async function loadSecurityDashboard() {
  const el = document.getElementById('security-dashboard');
  if (!el) return;
  try {
    const d = await safeFetch('/api/security/dashboard', {}, null);
    if (!d) throw new Error('security dashboard unavailable');
const secColors = {green:'var(--green)',yellow:'var(--warning)',orange:'var(--orange)',red:'var(--red)'};
    const secLabels = {green:'SECURE',yellow:'CAUTION',orange:'ELEVATED',red:'CRITICAL'};
    el.innerHTML =
      prepMetricCard('Threat Level', secLabels[d.security_level] || 'UNKNOWN', secColors[d.security_level] || 'var(--green)') +
      prepMetricCard('Cameras Active', d.cameras_active, d.cameras_active > 0 ? 'var(--green)' : 'var(--text-muted)') +
      prepMetricCard('Access (24h)', d.access_24h, 'var(--accent)') +
      prepMetricCard('Incidents (48h)', d.security_incidents_48h, d.security_incidents_48h > 0 ? 'var(--red)' : 'var(--green)');
  } catch(e) {
    el.innerHTML = prepEmptyBlock('Security dashboard unavailable right now.');
  }
}

async function loadCameras() {
  const el = document.getElementById('camera-grid');
  try {
    const cameras = await safeFetch('/api/security/cameras', {}, null);
    if (!Array.isArray(cameras)) throw new Error('camera list unavailable');
    stopCameraSnapshotRefresh();
    if (!cameras.length) {
      el.innerHTML = `<div class="prep-camera-empty">${prepEmptyBlock('No cameras registered. Add IP cameras above to view live feeds.')}</div>`;
      return;
    }
    el.innerHTML = cameras.map(c => {
      let feedHtml = '';
      if (c.stream_type === 'mjpeg') {
        feedHtml = `<img id="cam-feed-${c.id}" class="prep-camera-feed" src="${escapeAttr(c.url)}" onerror="this.alt='Camera offline';" alt="Live feed">`;
      } else if (c.stream_type === 'snapshot') {
        feedHtml = `<img id="cam-feed-${c.id}" class="prep-camera-feed" src="${escapeAttr(c.url)}?t=${Date.now()}" onerror="this.alt='Camera offline';" alt="Snapshot">`;
      } else {
        feedHtml = `<div class="prep-camera-feed prep-camera-feed-placeholder">HLS - open in new tab</div>`;
      }
      return `<div class="prep-camera-card">
        ${feedHtml}
        <div class="prep-camera-body">
          <div class="prep-camera-header">
            <div>
              <div class="prep-camera-title">${escapeHtml(c.name)}</div>
              <div class="prep-camera-meta">${escapeHtml(c.location || 'No location')} | ${c.stream_type.toUpperCase()}</div>
            </div>
            <div class="prep-camera-actions">
              <button type="button" class="btn btn-sm prep-camera-motion-btn" id="motion-btn-${c.id}" data-prep-action="toggle-motion-detection" data-camera-id="${c.id}" title="Toggle motion detection">Motion</button>
              <a class="btn btn-sm" href="${escapeAttr(c.url)}" target="_blank" rel="noopener noreferrer" title="Open in new tab">Fullscreen</a>
              <button class="prep-record-delete" type="button" data-prep-action="delete-camera" data-camera-id="${c.id}" aria-label="Delete camera">x</button>
            </div>
          </div>
        </div>
      </div>`;
    }).join('');

    startCameraSnapshotRefresh(cameras);
  } catch(e) {
    stopCameraSnapshotRefresh();
    if (el) el.innerHTML = `<div class="prep-camera-empty">${prepEmptyBlock('Could not load camera feeds right now.')}</div>`;
  }
}

async function addCamera() {
  const nameInput = document.getElementById('cam-name');
  const urlInput = document.getElementById('cam-url');
  const typeInput = document.getElementById('cam-type');
  const locationInput = document.getElementById('cam-location');
  if (!nameInput || !urlInput || !typeInput || !locationInput) return;
  const name = nameInput.value.trim();
  const url = urlInput.value.trim();
  if (!name || !url) { toast('Enter camera name and URL', 'warning'); return; }
  try {
    await apiPost('/api/security/cameras', {
      name, url, stream_type: typeInput.value,
      location: locationInput.value.trim()});
    nameInput.value = '';
    urlInput.value = '';
    locationInput.value = '';
    toast('Camera "' + name + '" added', 'success');
    loadCameras();
    loadSecurityDashboard();
  } catch(e) { console.error(e); toast('Failed to add camera', 'error'); }
}

async function deleteCamera(id) {
  if (!confirm('Remove this camera?')) return;
  try {
    await apiDelete(`/api/security/cameras/${id}`);
    toast('Camera removed', 'warning');
    loadCameras();
    loadSecurityDashboard();
  } catch(e) { console.error(e); toast(e?.data?.error || 'Failed to remove camera', 'error'); }
}

/* ─── Motion Detection ─── */
let _motionStatusInterval = null;

async function toggleMotionDetection(cameraId) {
  const status = await safeFetch('/api/security/motion/status');
  const isRunning = status && status.detectors && status.detectors[cameraId] && status.detectors[cameraId].running;
  if (isRunning) {
    await stopMotionDetection(cameraId);
  } else {
    await startMotionDetection(cameraId);
  }
}

async function startMotionDetection(cameraId) {
  const resp = await safeFetch(`/api/security/motion/start/${cameraId}`, {method:'POST', headers:{'Content-Type':'application/json'}});
  if (!resp) return;
  if (resp.error) {
    toast(resp.error + (resp.instructions ? ' — ' + resp.instructions : ''), 'error');
    return;
  }
  toast(`Motion detection started on camera ${cameraId}`, 'success');
  loadMotionStatus();
}

async function stopMotionDetection(cameraId) {
  const resp = await safeFetch(`/api/security/motion/stop/${cameraId}`, {method:'POST', headers:{'Content-Type':'application/json'}});
  if (!resp) return;
  toast(`Motion detection stopped on camera ${cameraId}`, 'info');
  loadMotionStatus();
}

async function loadMotionStatus() {
  const data = await safeFetch('/api/security/motion/status');
  if (!data) return;
  const el = document.getElementById('motion-status-card');
  if (!el) return;

  const detectors = data.detectors || {};
  const config = data.config || {};
  const keys = Object.keys(detectors);

  // Update settings inputs
  const threshEl = document.getElementById('motion-threshold');
  const intervalEl = document.getElementById('motion-interval');
  const cooldownEl = document.getElementById('motion-cooldown');
  if (threshEl && config.threshold) threshEl.value = config.threshold;
  if (intervalEl && config.check_interval) intervalEl.value = config.check_interval;
  if (cooldownEl && config.cooldown) cooldownEl.value = config.cooldown;

  if (keys.length === 0) {
    el.innerHTML = prepEmptyBlock('No motion detectors active. Click "Motion" on a camera to start.');
  } else {
    el.innerHTML = '<div class="prep-table-wrap prep-inline-table-shell"><table class="freq-table prep-inline-table"><thead><tr><th>Camera</th><th>Status</th><th>Detections</th><th>Last Detection</th><th>Last Check</th></tr></thead><tbody>' +
      keys.map(cid => {
        const d = detectors[cid];
        const statusColor = d.running ? 'var(--green)' : 'var(--text-muted)';
        const statusText = d.running ? 'ACTIVE' : (d.error ? 'ERROR' : 'STOPPED');
        return `<tr>
          <td><strong>${escapeHtml(d.camera_name || 'Camera ' + cid)}</strong></td>
          <td><span class="prep-inline-pill" style="--prep-pill-tone:${statusColor};">${statusText}</span></td>
          <td>${d.detections_count || 0}</td>
          <td>${d.last_detection_time || 'None'}</td>
          <td>${d.last_check || '-'}</td>
        </tr>`;
      }).join('') + '</tbody></table></div>';
  }

  // Update per-camera motion buttons
  keys.forEach(cid => {
    const btn = document.getElementById(`motion-btn-${cid}`);
    if (btn) {
      btn.classList.toggle('prep-camera-motion-active', !!detectors[cid].running);
    }
  });
}

function toggleMotionSettingsPanel() {
  const panel = document.getElementById('motion-settings-panel');
  if (panel) panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

async function configureMotionDetection() {
  const thresholdInput = document.getElementById('motion-threshold');
  const intervalInput = document.getElementById('motion-interval');
  const cooldownInput = document.getElementById('motion-cooldown');
  if (!thresholdInput || !intervalInput || !cooldownInput) return;
  const threshold = parseInt(thresholdInput.value) || 25;
  const check_interval = parseInt(intervalInput.value) || 2;
  const cooldown = parseInt(cooldownInput.value) || 60;
  const resp = await safeFetch('/api/security/motion/configure', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({threshold, check_interval, cooldown})
  });
  if (resp && resp.status === 'configured') {
    toast('Motion detection settings updated', 'success');
  } else {
    toast('Failed to update motion settings', 'error');
  }
}

async function logAccess() {
  const personInput = document.getElementById('al-person');
  const directionInput = document.getElementById('al-direction');
  const locationInput = document.getElementById('al-location');
  const methodInput = document.getElementById('al-method');
  const notesInput = document.getElementById('al-notes');
  if (!personInput || !directionInput || !locationInput || !methodInput || !notesInput) return;
  const person = personInput.value.trim();
  if (!person) { toast('Enter person name', 'warning'); return; }
  try {
    await apiPost('/api/security/access-log', {
      person, direction: directionInput.value,
      location: locationInput.value.trim(),
      method: methodInput.value,
      notes: notesInput.value.trim()});
    personInput.value = '';
    notesInput.value = '';
    toast('Access logged', 'success');
    loadAccessLog();
    loadSecurityDashboard();
  } catch(e) { console.error(e); toast('Failed to log access', 'error'); }
}

async function loadAccessLog() {
  const el = document.getElementById('access-log-list');
  if (!el) return;
  try {
    const logs = await safeFetch('/api/security/access-log', {}, null);
    if (!Array.isArray(logs)) throw new Error('access log unavailable');
    if (!logs.length) { el.innerHTML = prepEmptyBlock('No access events logged.'); return; }
    el.innerHTML = '<table class="freq-table prep-inline-table"><thead><tr><th>Time</th><th>Person</th><th>Dir</th><th>Location</th><th>Method</th><th>Notes</th></tr></thead><tbody>' +
      logs.map(l => {
        const t = new Date(l.created_at);
        const ts = t.toLocaleDateString([],{month:'short',day:'numeric'}) + ' ' + t.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
        const dirColor = l.direction === 'entry' ? 'var(--green)' : l.direction === 'exit' ? 'var(--text-muted)' : l.direction === 'unknown' ? 'var(--red)' : 'var(--accent)';
        return `<tr><td>${ts}</td><td><strong>${escapeHtml(l.person)}</strong></td><td><span class="prep-inline-pill" style="--prep-pill-tone:${dirColor};">${l.direction}</span></td><td>${escapeHtml(l.location||'-')}</td><td>${l.method}</td><td>${escapeHtml(l.notes||'')}</td></tr>`;
      }).join('') + '</tbody></table>';
  } catch(e) { el.innerHTML = prepEmptyBlock('Could not load access log right now.'); }
}

async function clearAccessLog() {
  const btn = event.target;
  if (!btn.dataset.confirm) {
    btn.dataset.confirm = '1'; btn.textContent = 'Confirm clear?';
        btn.classList.add('is-confirming');
    setTimeout(() => { btn.textContent = 'Clear Log'; btn.classList.remove('is-confirming'); delete btn.dataset.confirm; }, 3000);
    return;
  }
  try {
    await apiPost('/api/security/access-log/clear');
    toast('Access log cleared', 'warning');
    loadAccessLog();
  } catch(e) { toast('Failed to clear access log', 'error'); }
}

/* ─── Power Management ─── */
function showPowerTab(tab) {
  ['devices','log'].forEach(t => {
    const panel = document.getElementById(`power-${t}-panel`);
    const tabBtn = document.getElementById(`pwr-tab-${t}`);
    if (!panel || !tabBtn) return;
    panel.style.display = t === tab ? 'block' : 'none';
    tabBtn.className = t === tab ? 'btn btn-sm prep-utility-tab prep-utility-tab-active' : 'btn btn-sm prep-utility-tab';
  });
  if (tab === 'devices') { loadPowerDevices(); updatePowerSpecFields(); }
  if (tab === 'log') loadPowerLog();
}

async function loadPowerDashboard() {
  const el = document.getElementById('power-dashboard');
  if (!el) return;
  try {
    const d = await safeFetch('/api/power/dashboard', {}, null);
    if (!d) throw new Error('power dashboard unavailable');
    const autoColor = d.autonomy_days > 7 ? 'var(--green)' : d.autonomy_days > 3 ? 'var(--orange)' : 'var(--red)';
    const socColor = d.latest_soc > 50 ? 'var(--green)' : d.latest_soc > 20 ? 'var(--orange)' : 'var(--red)';
    const netColor = d.net_daily_wh >= 0 ? 'var(--green)' : 'var(--red)';
    el.innerHTML =
      prepMetricCard('Autonomy', d.autonomy_days >= 999 ? 'Unlimited' : d.autonomy_days + 'd', autoColor) +
      (d.latest_soc !== null ? prepMetricCard('Battery SOC', `${d.latest_soc}%`, socColor, d.latest_voltage ? `${d.latest_voltage}V` : '') : '') +
      prepMetricCard('Solar Capacity', `${d.total_solar_w}W`, 'var(--accent)', `Avg: ${d.avg_solar_w}W`) +
      prepMetricCard('Battery Bank', `${d.total_battery_wh}Wh`, 'var(--accent)') +
      prepMetricCard('Avg Load', `${d.avg_load_w}W`, 'var(--orange)', `${d.daily_consumption_wh} Wh/day`) +
      prepMetricCard('Net Daily', `${d.net_daily_wh >= 0 ? '+' : ''}${d.net_daily_wh}Wh`, netColor, d.net_daily_wh >= 0 ? 'Surplus' : 'Deficit');
  } catch(e) {
    el.innerHTML = prepEmptyBlock('Add power devices and log readings to see your power dashboard.');
  }
}

function updatePowerSpecFields() {
  const type = document.getElementById('pd-type').value;
  const el = document.getElementById('pd-spec-fields');
  const field = (label, control) => `<label class="prep-field"><span class="prep-field-label">${label}</span>${control}</label>`;
  if (type === 'solar_panel') {
    el.innerHTML = field('Watts', '<input id="pd-watts" class="prep-field-control" type="number" placeholder="200">') +
      field('Count', '<input id="pd-count" class="prep-field-control" type="number" value="1" min="1">');
  } else if (type === 'battery') {
    el.innerHTML = field('Capacity Wh', '<input id="pd-wh" class="prep-field-control" type="number" placeholder="1280">') +
      field('Voltage', '<input id="pd-volts" class="prep-field-control" type="number" step="0.1" placeholder="12.8">') +
      field('Type', '<select id="pd-btype" class="prep-field-control"><option>LiFePO4</option><option>AGM</option><option>Flooded</option><option>Li-ion</option></select>') +
      field('Count', '<input id="pd-count" class="prep-field-control" type="number" value="1" min="1">');
  } else if (type === 'inverter') {
    el.innerHTML = field('Watts', '<input id="pd-watts" class="prep-field-control" type="number" placeholder="2000">') +
      field('Type', '<select id="pd-itype" class="prep-field-control"><option>Pure Sine</option><option>Modified Sine</option></select>');
  } else if (type === 'charge_controller') {
    el.innerHTML = field('Amps', '<input id="pd-amps" class="prep-field-control" type="number" placeholder="30">') +
      field('Type', '<select id="pd-ctype" class="prep-field-control"><option>MPPT</option><option>PWM</option></select>');
  } else if (type === 'generator') {
    el.innerHTML = field('Watts', '<input id="pd-watts" class="prep-field-control" type="number" placeholder="3500">') +
      field('Fuel', '<select id="pd-fuel" class="prep-field-control"><option>Gasoline</option><option>Diesel</option><option>Propane</option><option>Dual Fuel</option></select>');
  }
}

async function addPowerDevice() {
  const typeInput = document.getElementById('pd-type');
  const nameInput = document.getElementById('pd-name');
  if (!typeInput || !nameInput) return;
  const type = typeInput.value;
  const name = nameInput.value.trim();
  if (!name) { toast('Enter device name', 'warning'); return; }
  const specs = {};
  const wattsInput = document.getElementById('pd-watts');
  const countInput = document.getElementById('pd-count');
  const whInput = document.getElementById('pd-wh');
  const voltsInput = document.getElementById('pd-volts');
  const batteryTypeInput = document.getElementById('pd-btype');
  const inverterTypeInput = document.getElementById('pd-itype');
  const controllerTypeInput = document.getElementById('pd-ctype');
  const ampsInput = document.getElementById('pd-amps');
  const fuelInput = document.getElementById('pd-fuel');
  if (wattsInput) specs.watts = parseInt(wattsInput.value) || 0;
  if (countInput) specs.count = parseInt(countInput.value) || 1;
  if (whInput) specs.capacity_wh = parseInt(whInput.value) || 0;
  if (voltsInput) specs.voltage = parseFloat(voltsInput.value) || 0;
  if (batteryTypeInput) specs.battery_type = batteryTypeInput.value;
  if (inverterTypeInput) specs.inverter_type = inverterTypeInput.value;
  if (controllerTypeInput) specs.controller_type = controllerTypeInput.value;
  if (ampsInput) specs.amps = parseInt(ampsInput.value) || 0;
  if (fuelInput) specs.fuel = fuelInput.value;
  try {
    await apiPost('/api/power/devices', {device_type: type, name, specs});
    ['pd-type','pd-name','pd-watts','pd-count','pd-wh','pd-volts','pd-btype','pd-itype','pd-ctype','pd-amps','pd-fuel'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    toast(name + ' added', 'success');
    loadPowerDevices();
    loadPowerDashboard();
  } catch(e) { console.error(e); toast('Failed to add device', 'error'); }
}

async function loadPowerDevices() {
  const el = document.getElementById('power-devices-list');
  if (!el) return;
  try {
    const devices = await safeFetch('/api/power/devices', {}, null);
    if (!Array.isArray(devices)) throw new Error('power devices unavailable');
    if (!devices.length) { el.innerHTML = prepEmptyBlock('No power devices registered. Add your solar panels, batteries, and other equipment above.'); return; }
    const icons = {solar_panel:'&#9728;', battery:'&#128267;', charge_controller:'&#9889;', inverter:'&#128268;', generator:'&#9981;'};
    el.innerHTML = devices.map(d => {
      const specs = d.specs || {};
      let specStr = '';
      if (d.device_type === 'solar_panel') specStr = `${specs.watts||0}W x ${specs.count||1} = ${(specs.watts||0)*(specs.count||1)}W`;
      else if (d.device_type === 'battery') specStr = `${specs.capacity_wh||0}Wh ${specs.battery_type||''} ${specs.voltage||''}V x ${specs.count||1}`;
      else if (d.device_type === 'inverter') specStr = `${specs.watts||0}W ${specs.inverter_type||''}`;
      else if (d.device_type === 'charge_controller') specStr = `${specs.amps||0}A ${specs.controller_type||''}`;
      else if (d.device_type === 'generator') specStr = `${specs.watts||0}W ${specs.fuel||''}`;
      return `<div class="prep-record-item prep-power-device-item">
        <div class="prep-record-main"><span class="prep-record-icon">${icons[d.device_type]||''}</span><strong>${escapeHtml(d.name)}</strong> <span class="prep-record-meta">- ${specStr}</span></div>
        <button class="prep-record-delete" type="button" data-prep-action="delete-power-device" data-power-device-id="${d.id}" aria-label="Delete power device">x</button>
      </div>`;
    }).join('');
  } catch(e) { el.innerHTML = prepEmptyBlock('Could not load power devices right now.'); }
}

async function deletePowerDevice(id) {
  if (!confirm('Remove this power device?')) return;
  try {
    await apiDelete(`/api/power/devices/${id}`);
    toast('Device removed', 'warning');
    loadPowerDevices();
    loadPowerDashboard();
  } catch(e) { console.error(e); toast(e?.data?.error || 'Failed to remove device', 'error'); }
}

async function logPowerReading() {
  const voltageInput = document.getElementById('pl-voltage');
  const socInput = document.getElementById('pl-soc');
  const solarInput = document.getElementById('pl-solar');
  const solarWhInput = document.getElementById('pl-solar-wh');
  const loadInput = document.getElementById('pl-load');
  const loadWhInput = document.getElementById('pl-load-wh');
  const generatorInput = document.getElementById('pl-gen');
  if (!voltageInput || !socInput || !solarInput || !solarWhInput || !loadInput || !loadWhInput || !generatorInput) return;
  const data = {
    battery_voltage: parseFloat(voltageInput.value) || null,
    battery_soc: parseInt(socInput.value) || null,
    solar_watts: parseFloat(solarInput.value) || null,
    solar_wh_today: parseFloat(solarWhInput.value) || null,
    load_watts: parseFloat(loadInput.value) || null,
    load_wh_today: parseFloat(loadWhInput.value) || null,
    generator_running: generatorInput.value === '1',
  };
  if (!data.battery_voltage && !data.solar_watts && !data.load_watts) { toast('Enter at least one reading', 'warning'); return; }
  try {
    await apiPost('/api/power/log', data);
    toast('Power reading logged', 'success');
    [voltageInput, socInput, solarInput, solarWhInput, loadInput, loadWhInput].forEach(input => { input.value = ''; });
    loadPowerLog();
    loadPowerDashboard();
  } catch(e) { toast('Failed to log reading', 'error'); }
}

async function loadPowerLog() {
  const el = document.getElementById('power-log-list');
  if (!el) return;
  try {
    const logs = await safeFetch('/api/power/log', {}, null);
    if (!Array.isArray(logs)) throw new Error('power log unavailable');
    if (!logs.length) { el.innerHTML = prepEmptyBlock('No readings logged yet.'); return; }
    el.innerHTML = '<table class="freq-table prep-inline-table"><thead><tr><th>Time</th><th>Battery V</th><th>SOC</th><th>Solar W</th><th>Solar Wh</th><th>Load W</th><th>Load Wh</th><th>Gen</th></tr></thead><tbody>' +
      logs.map(l => {
        const t = new Date(l.created_at);
        const ts = t.toLocaleDateString([],{month:'short',day:'numeric'}) + ' ' + t.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
        const socColor = l.battery_soc > 50 ? 'var(--green)' : l.battery_soc > 20 ? 'var(--orange)' : 'var(--red)';
        return `<tr><td>${ts}</td><td>${l.battery_voltage||'-'}</td><td>${l.battery_soc != null ? `<span class="prep-inline-pill" style="--prep-pill-tone:${socColor};">${l.battery_soc}%</span>` : '-'}</td><td>${l.solar_watts||'-'}</td><td>${l.solar_wh_today||'-'}</td><td>${l.load_watts||'-'}</td><td>${l.load_wh_today||'-'}</td><td>${l.generator_running ? '<span class="prep-inline-pill" style="--prep-pill-tone:var(--green);">ON</span>' : '-'}</td></tr>`;
      }).join('') + '</tbody></table>';
  } catch(e) { el.innerHTML = prepEmptyBlock('Could not load power log right now.'); }
}


/* --- Solar Forecast --- */
async function updateSolarConfig() {
  try {
    const settings = await safeFetch('/api/settings', {}, {});
    const latInput = document.getElementById('sf-lat');
    const lngInput = document.getElementById('sf-lng');
    if (!latInput || !lngInput) return;
    let lat = null, lng = null;
    if (settings.map_center) {
      const parts = safeJsonParse(settings.map_center, null);
      if (Array.isArray(parts) && parts.length >= 2) { lat = parts[0]; lng = parts[1]; }
      else if (parts?.lat != null) { lat = parts.lat; lng = parts.lng; }
    }
    if (lat && lng) {
      latInput.value = parseFloat(lat).toFixed(3);
      lngInput.value = parseFloat(lng).toFixed(3);
      toast('Location loaded from settings', 'success');
      loadSolarForecast();
    } else {
      toast('No location found in settings \u2014 set map center or add a waypoint', 'warning');
    }
  } catch(e) { toast('Could not load settings', 'error'); }
}

async function loadSolarForecast() {
  const latInput = document.getElementById('sf-lat');
  const lngInput = document.getElementById('sf-lng');
  const wattsInput = document.getElementById('sf-watts');
  const countInput = document.getElementById('sf-count');
  const efficiencyInput = document.getElementById('sf-eff');
  const el = document.getElementById('solar-forecast-today');
  const cloudIndicator = document.getElementById('solar-cloud-indicator');
  if (!latInput || !lngInput || !wattsInput || !countInput || !efficiencyInput || !el || !cloudIndicator) return;
  const lat = latInput.value;
  const lng = lngInput.value;
  const watts = wattsInput.value || 100;
  const count = countInput.value || 1;
  const eff = efficiencyInput.value || 0.85;
  if (!lat || !lng) { toast('Enter latitude and longitude', 'warning'); return; }
  const params = new URLSearchParams({lat, lng, panel_watts: watts, panel_count: count, efficiency: eff});
  const data = await safeFetch(`/api/power/solar-forecast?${params}`, {}, null);
  if (!data || data.error) { toast(data?.error || 'Solar forecast failed', 'error'); return; }

  const t = data.today;
  const cfColor = t.cloud_factor >= 0.8 ? 'var(--green)' : t.cloud_factor >= 0.5 ? 'var(--orange)' : 'var(--red)';
  el.innerHTML = prepMetricCard('Est. kWh', t.estimated_kwh, 'var(--green)') +
    prepMetricCard('Clear Sky', t.clear_sky_kwh + ' kWh', 'var(--accent)') +
    prepMetricCard('Peak Sun', t.peak_sun_hours + 'h', 'var(--accent)') +
    prepMetricCard('Day Length', t.day_length_hours + 'h', 'var(--accent)') +
    prepMetricCard('Sunrise', t.sunrise, 'var(--accent)') +
    prepMetricCard('Sunset', t.sunset, 'var(--accent)') +
    prepMetricCard('Max Alt', t.max_altitude_degrees + '\u00B0', 'var(--accent)') +
    prepMetricCard('Cloud Factor', (t.cloud_factor * 100).toFixed(0) + '%', cfColor);

  if (t.cloud_factor < 1.0) {
    cloudIndicator.style.display = 'block';
    cloudIndicator.innerHTML = 'Cloud cover impact: <strong class="live-widget-value-toned" style="--widget-tone:' + cfColor + ';">' + ((1-t.cloud_factor)*100).toFixed(0) + '% reduction</strong> based on recent weather observations. Clear sky would yield ' + escapeHtml(String(t.clear_sky_kwh)) + ' kWh.';
  } else {
    cloudIndicator.style.display = 'none';
  }

  renderSolarChart(data.daily);
}

function renderSolarChart(daily) {
  const canvas = document.getElementById('solar-7day-chart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  if (!daily || !daily.length) return;
  const maxKwh = Math.max(...daily.map(d => d.clear_sky_kwh), 0.1);
  const barW = Math.min(50, (w - 40) / daily.length - 8);
  const pad = {top: 10, bottom: 30, left: 35, right: 10};
  const chartH = h - pad.top - pad.bottom;
  const gap = (w - pad.left - pad.right) / daily.length;

  ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--border').trim() || '#ccc';
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + chartH - (chartH * i / 4);
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(w - pad.right, y); ctx.stroke();
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#888';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText((maxKwh * i / 4).toFixed(1), pad.left - 4, y + 3);
  }

  daily.forEach((d, i) => {
    const x = pad.left + gap * i + (gap - barW) / 2;
    const clearH = (d.clear_sky_kwh / maxKwh) * chartH;
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--accent-dim').trim() || 'rgba(74,77,36,0.15)';
    ctx.fillRect(x, pad.top + chartH - clearH, barW, clearH);
    const estH = (d.estimated_kwh / maxKwh) * chartH;
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#4a4d24';
    ctx.fillRect(x, pad.top + chartH - estH, barW, estH);
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text').trim() || '#333';
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(d.estimated_kwh.toFixed(1), x + barW/2, pad.top + chartH - estH - 3);
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-dim').trim() || '#666';
    ctx.font = '10px sans-serif';
    ctx.fillText(d.date.slice(5), x + barW/2, h - pad.bottom + 14);
  });
}

/* --- Backup & Restore --- */
async function createBackup() {
  const encrypt = document.getElementById('ab-encrypt')?.checked || false;
  const password = document.getElementById('ab-password')?.value || '';
  if (encrypt && !password) { toast('Enter encryption password', 'warning'); return; }
  toast('Creating backup...', 'info');
  const r = await safeFetch('/api/system/backup/create', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({encrypt, password})
  }, null);
  if (r && r.status === 'ok') {
    toast('Backup created: ' + r.filename + ' (' + formatBytes(r.size_bytes) + ')' + (r.encrypted ? ' [encrypted]' : ''), 'success');
    loadBackups();
  } else {
    toast(r?.error || 'Backup failed', 'error');
  }
}

async function loadBackups() {
  const backups = await safeFetch('/api/system/backup/list', {}, []);
  const el = document.getElementById('backup-list');
  if (!el) return;
  if (!backups.length) {
    el.innerHTML = '<div class="settings-empty-state settings-backup-list-empty">No backups yet. Click "Backup Now" to create one.</div>';
    return;
  }
  el.innerHTML = backups.map(b => {
    const dt = new Date(b.created_at);
    const ts = dt.toLocaleDateString([], {month:'short', day:'numeric', year:'numeric'}) + ' ' + dt.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
    const size = b.size_bytes >= 1048576 ? (b.size_bytes/1048576).toFixed(1)+' MB' : (b.size_bytes/1024).toFixed(0)+' KB';
    return `<div class="settings-backup-item">
      <div class="settings-backup-main">
        <strong class="settings-backup-name">${escapeHtml(b.filename)}</strong>
        <span class="settings-backup-meta">${size}</span>
        ${b.encrypted ? '<span class="settings-backup-flag">encrypted</span>' : ''}
        <div class="settings-backup-time">${ts}</div>
      </div>
      <div class="settings-backup-actions">
        <button class="btn btn-sm" type="button" data-shell-action="restore-backup" data-backup-filename="${escapeAttr(b.filename)}" data-backup-encrypted="${b.encrypted ? 'true' : 'false'}">Restore</button>
        <button class="btn btn-sm btn-danger" type="button" data-shell-action="delete-backup" data-backup-filename="${escapeAttr(b.filename)}">Delete</button>
      </div>
    </div>`;
  }).join('');
}

async function restoreScheduledBackup(filename, encrypted) {
  if (!confirm('Restore database from ' + filename + '? A safety backup will be created first.')) return;
  let password = '';
  if (encrypted) {
    password = prompt('Enter decryption password:');
    if (!password) return;
  }
  toast('Restoring...', 'info');
  const r = await safeFetch('/api/system/backup/restore', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({filename, password})
  }, null);
  if (r && r.status === 'ok') {
    toast(r.message || 'Restore successful', 'success');
    loadBackups();
  } else {
    toast(r?.error || 'Restore failed', 'error');
  }
}

async function deleteBackup(filename) {
  if (!confirm('Delete backup ' + filename + '?')) return;
  const r = await safeFetch('/api/system/backup/' + encodeURIComponent(filename), {method: 'DELETE'}, null);
  if (r && r.status === 'deleted') {
    toast('Backup deleted', 'success');
    loadBackups();
  } else {
    toast(r?.error || 'Delete failed', 'error');
  }
}

async function configureAutoBackup() {
  const enabledInput = document.getElementById('ab-enabled');
  const intervalInput = document.getElementById('ab-interval');
  const keepInput = document.getElementById('ab-keep');
  const encryptInput = document.getElementById('ab-encrypt');
  const passwordInput = document.getElementById('ab-password');
  if (!enabledInput || !intervalInput || !keepInput || !encryptInput || !passwordInput) return;
  const config = {
    enabled: enabledInput.checked,
    interval: intervalInput.value,
    keep_count: parseInt(keepInput.value) || 7,
    encrypt: encryptInput.checked,
    password: passwordInput.value,
  };
  const r = await safeFetch('/api/system/backup/configure', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(config)
  }, null);
  if (r && r.status === 'configured') {
    toast('Auto-backup ' + (config.enabled ? 'enabled' : 'disabled') + ' (' + config.interval + ')', 'success');
  }
}

async function loadBackupConfig() {
  const cfg = await safeFetch('/api/system/backup/config', {}, null);
  if (!cfg) return;
  const enEl = document.getElementById('ab-enabled');
  const intEl = document.getElementById('ab-interval');
  const keepEl = document.getElementById('ab-keep');
  const keepValEl = document.getElementById('ab-keep-val');
  const encEl = document.getElementById('ab-encrypt');
  const pwWrapEl = document.getElementById('ab-pw-wrap');
  if (enEl) enEl.checked = cfg.enabled;
  if (intEl) intEl.value = cfg.interval || 'daily';
  if (keepEl) keepEl.value = cfg.keep_count || 7;
  if (keepValEl) keepValEl.textContent = cfg.keep_count || 7;
  if (encEl) {
    encEl.checked = cfg.encrypt;
    if (pwWrapEl) pwWrapEl.style.display = cfg.encrypt ? 'block' : 'none';
  }
}

function restoreFromUpload() {
  const input = document.getElementById('backup-upload-file');
  if (!input || !input.files || !input.files.length) return;
  toast('Upload restore: place .db files in the backups directory and use the list to restore', 'warning');
  input.value = '';
}

/* ─── Food Production Module ─── */
function showGardenTab(tab) {
  ['plots','seeds','harvest','livestock','calendar','yield','preservation'].forEach(t => {
    const panel = document.getElementById(`garden-${t}-panel`);
    const btn = document.getElementById(`garden-tab-${t}`);
    if (panel) panel.style.display = t === tab ? 'block' : 'none';
    if (btn) btn.className = t === tab
      ? 'btn btn-sm prep-utility-tab prep-utility-tab-active'
      : 'btn btn-sm prep-utility-tab';
  });
  if (tab === 'plots') loadPlots();
  if (tab === 'seeds') loadSeeds();
  if (tab === 'harvest') loadHarvests();
  if (tab === 'livestock') loadLivestockList();
  if (tab === 'calendar') loadPlantingCalendar();
  if (tab === 'yield') loadYieldAnalysis();
  if (tab === 'preservation') loadPreservationLog();
}

async function loadPlantingCalendar() {
  const data = await safeFetch('/api/garden/calendar', {}, []);
  const el = document.getElementById('planting-calendar-grid');
  const label = document.getElementById('calendar-zone-label');
  if (!el) return;
  if (label && data.length && data[0].zone) {
    label.textContent = `Zone ${data[0].zone}`;
    label.style.display = 'inline-flex';
  } else if (label) {
    label.textContent = '';
    label.style.display = 'none';
  }
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const actionColors = {start_indoor:'#7b1fa2',transplant:'#2e7d32',direct_sow:'#1565c0',plant:'#e65100',harvest:'#c62828'};
  const actionLabels = {start_indoor:'START INDOOR',transplant:'TRANSPLANT',direct_sow:'DIRECT SOW',plant:'PLANT',harvest:'HARVEST'};
  const byMonth = {};
  data.forEach(e => { if (!byMonth[e.month]) byMonth[e.month] = []; byMonth[e.month].push(e); });
  el.innerHTML = months.map((m, i) => {
    const entries = byMonth[i + 1] || [];
    return `<div class="prep-garden-month-card">
      <div class="prep-garden-month-title">${m}</div>
      ${entries.map(e => `<div class="prep-garden-calendar-entry" style="--prep-garden-tone:${actionColors[e.action]||'var(--text-muted)'};">
        <strong>${escapeHtml(e.crop)}</strong>
        <span>${actionLabels[e.action]||e.action}</span>
      </div>`).join('')}
      ${!entries.length ? '<div class="prep-garden-calendar-empty">No activity scheduled</div>' : ''}
    </div>`;
  }).join('');
}

async function loadYieldAnalysis() {
  const data = await safeFetch('/api/garden/yield-analysis', {}, {crops:[], total_calories:0, person_days:0, total_sqft:0});
  const summary = document.getElementById('yield-summary');
  const crops = document.getElementById('yield-crops');
  if (!summary || !crops) return;
  summary.innerHTML = `
    ${prepMetricCard('Total calories', (data.total_calories||0).toLocaleString(), 'var(--accent)', 'Estimated edible energy')}
    ${prepMetricCard('Person-days', data.person_days||0, 'var(--green)', 'At 2,000 cal/day')}
    ${prepMetricCard('Total area', data.total_sqft||0, 'var(--orange)', 'Sq ft in tracked plots')}`;
  if (!data.crops.length) {
    crops.innerHTML = prepEmptyBlock('No harvests logged yet. Log harvests from the Harvest Log tab to see yield analysis.');
    return;
  }
  crops.innerHTML = '<div class="prep-table-wrap"><table class="freq-table prep-data-table"><thead><tr><th>Crop</th><th>Total lbs</th><th>Harvests</th><th>Yield/sqft</th><th>Calories</th></tr></thead><tbody>' +
    data.crops.map(c => `<tr><td><strong>${escapeHtml(c.crop)}</strong></td><td>${c.total_lbs}</td><td>${c.harvests}</td><td>${c.avg_yield_sqft}</td><td><strong>${c.calories.toLocaleString()}</strong></td></tr>`).join('') +
    '</tbody></table></div>';
}

async function loadPreservationLog() {
  const data = await safeFetch('/api/garden/preservation', {}, []);
  const el = document.getElementById('preservation-list');
  if (!el) return;
  if (!data.length) {
    el.innerHTML = prepEmptyBlock('No preservation batches logged. Click "+ Log Batch" to track canned, dried, or frozen food.');
    return;
  }
  const methodColors = {canning:'#c62828',drying:'#e65100',freezing:'#1565c0',fermenting:'#7b1fa2',smoking:'#795548'};
  el.innerHTML = '<div class="prep-table-wrap"><table class="freq-table prep-data-table"><thead><tr><th>Crop</th><th>Method</th><th>Qty</th><th>Batch date</th><th>Shelf life</th><th></th></tr></thead><tbody>' +
    data.map(p => `<tr>
      <td><strong>${escapeHtml(p.crop)}</strong></td>
      <td><span class="prep-inline-pill" style="--prep-pill-tone:${methodColors[p.method]||'var(--text-dim)'};">${escapeHtml(p.method)}</span></td>
      <td>${p.quantity} ${escapeHtml(p.unit)}</td>
      <td>${escapeHtml(p.batch_date||'—')}</td>
      <td>${p.shelf_life_months} months</td>
      <td><button type="button" class="prep-record-delete" data-prep-action="delete-preservation" data-preservation-id="${p.id}" title="Delete batch" aria-label="Delete batch">&#10005;</button></td>
    </tr>`).join('') + '</tbody></table></div>';
}

function showAddPreservationForm() {
  const existing = document.getElementById('add-pres-form');
  if (existing) { existing.remove(); return; }
  const form = document.createElement('div');
  form.id = 'add-pres-form';
  form.className = 'prep-form-shell prep-data-shell prep-inline-form prep-garden-inline-form';
  form.innerHTML = `
    <div class="prep-form-grid prep-garden-inline-grid">
      <label class="prep-field"><span class="prep-field-label">Crop</span><input id="ap-crop" class="prep-field-control" placeholder="Tomatoes"></label>
      <label class="prep-field"><span class="prep-field-label">Method</span><select id="ap-method" class="prep-field-control"><option>canning</option><option>drying</option><option>freezing</option><option>fermenting</option><option>smoking</option></select></label>
      <label class="prep-field"><span class="prep-field-label">Qty</span><input id="ap-qty" class="prep-field-control" type="number" value="1" min="0"></label>
      <label class="prep-field"><span class="prep-field-label">Unit</span><select id="ap-unit" class="prep-field-control"><option>quarts</option><option>pints</option><option>lbs</option><option>gallons</option><option>bags</option></select></label>
      <label class="prep-field"><span class="prep-field-label">Date</span><input id="ap-date" class="prep-field-control" type="date" value="${new Date().toISOString().slice(0,10)}"></label>
      <label class="prep-field"><span class="prep-field-label">Shelf Life (mo)</span><input id="ap-shelf" class="prep-field-control" type="number" value="12" min="1"></label>
    </div>
    <div class="prep-form-actions">
      <button type="button" class="btn btn-sm btn-primary" data-prep-action="submit-preservation">Log Batch</button>
      <button type="button" class="btn btn-sm" data-shell-action="close-preservation-form">Cancel</button>
    </div>`;
  document.getElementById('preservation-list').parentElement.insertBefore(form, document.getElementById('preservation-list'));
}

async function submitPreservation() {
  const cropInput = document.getElementById('ap-crop');
  const methodInput = document.getElementById('ap-method');
  const qtyInput = document.getElementById('ap-qty');
  const unitInput = document.getElementById('ap-unit');
  const dateInput = document.getElementById('ap-date');
  const shelfInput = document.getElementById('ap-shelf');
  if (!cropInput || !methodInput || !qtyInput || !unitInput || !dateInput || !shelfInput) return;
  const data = {
    crop: cropInput.value, method: methodInput.value,
    quantity: parseFloat(qtyInput.value) || 0, unit: unitInput.value,
    batch_date: dateInput.value, shelf_life_months: parseInt(shelfInput.value) || 12,
  };
  if (!data.crop) { toast('Crop name required', 'warning'); return; }
  try {
    await apiPost('/api/garden/preservation', data);
    document.getElementById('add-pres-form')?.remove();
    loadPreservationLog();
    toast('Preservation batch logged', 'success');
  } catch(e) { toast('Failed to log preservation batch', 'error'); }
}

async function deletePreservation(id) {
  if (!confirm('Delete this preservation entry?')) return;
  try {
    await apiDelete('/api/garden/preservation/' + id);
    loadPreservationLog();
  } catch(e) { toast('Delete failed', 'error'); }
}

async function lookupZone() {
  const latInput = document.getElementById('garden-lat');
  if (!latInput) return;
  const lat = parseFloat(latInput.value);
  if (isNaN(lat)) return;
  const result = document.getElementById('zone-result');
  if (!result) return;
  try {
    const z = await apiFetch(`/api/garden/zone?lat=${lat}`);
    result.style.display = 'block';
    result.innerHTML = `<strong>Zone ${escapeHtml(String(z.zone))}</strong> with last frost around ${escapeHtml(z.last_frost || 'unknown')} and first frost around ${escapeHtml(z.first_frost || 'unknown')}.`;
  } catch(e) {
    result.style.display = 'block';
    result.textContent = 'Zone lookup unavailable right now.';
  }
}

async function loadPlots() {
  const el = document.getElementById('plots-list');
  if (el) el.innerHTML = Array(3).fill('<div class="skeleton skeleton-card prep-garden-skeleton"></div>').join('');
  try {
    const plots = await apiFetch('/api/garden/plots');
    const sel = document.getElementById('gh-plot');
    if (!el || !sel) return;
    sel.innerHTML = '<option value="">-- Any --</option>' + plots.map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');
    if (!plots.length) { el.innerHTML = prepEmptyBlock('No garden plots yet. Add one above to start planning beds and harvests.'); return; }
    const totalSqFt = plots.reduce((s, p) => s + (p.width_ft * p.length_ft), 0);
    el.innerHTML = `<div class="prep-garden-summary-note">Total garden area: ${totalSqFt.toLocaleString()} sq ft (${(totalSqFt/43560).toFixed(2)} acres)</div>` +
      plots.map(p => `<div class="prep-record-item">
        <div>
          <div class="prep-record-main"><strong>${escapeHtml(p.name)}</strong> <span class="prep-inline-pill" style="--prep-pill-tone:var(--accent);">${escapeHtml(p.sun_exposure)} sun</span></div>
          <div class="prep-record-meta">${p.width_ft}x${p.length_ft} ft · ${p.width_ft * p.length_ft} sq ft${p.soil_type ? ' · ' + escapeHtml(p.soil_type) : ''}</div>
        </div>
        <button type="button" class="prep-record-delete" data-prep-action="delete-plot" data-plot-id="${p.id}" title="Delete plot" aria-label="Delete plot">&#10005;</button>
      </div>`).join('');
  } catch(e) {}
}

async function addPlot() {
  const nameInput = document.getElementById('gp-name');
  const widthInput = document.getElementById('gp-width');
  const lengthInput = document.getElementById('gp-length');
  const sunInput = document.getElementById('gp-sun');
  if (!nameInput || !widthInput || !lengthInput || !sunInput) return;
  const name = nameInput.value.trim();
  if (!name) { toast('Enter plot name', 'warning'); return; }
  try {
    await apiPost('/api/garden/plots', {
      name, width_ft: parseFloat(widthInput.value) || 10,
      length_ft: parseFloat(lengthInput.value) || 20,
      sun_exposure: sunInput.value});
    ['gp-name','gp-width','gp-length','gp-sun'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    toast('Plot added', 'success');
    loadPlots();
  } catch(e) { toast('Failed to add plot', 'error'); }
}

async function deletePlot(id) {
  if (!confirm('Remove this garden plot?')) return;
  try {
    await apiDelete('/api/garden/plots/' + id);
    toast('Plot removed', 'warning');
    loadPlots();
  } catch(e) { toast('Failed to remove plot', 'error'); }
}

async function loadSeeds() {
  try {
    const seeds = await apiFetch('/api/garden/seeds');
    const el = document.getElementById('seeds-list');
    if (!seeds.length) { el.innerHTML = prepEmptyBlock('No seeds in inventory yet. Add seeds above to build your library.'); return; }
    el.innerHTML = '<div class="prep-table-wrap"><table class="freq-table prep-data-table"><thead><tr><th>Species</th><th>Variety</th><th>Qty</th><th>Year</th><th>Viability</th><th>Season</th><th>Days</th><th></th></tr></thead><tbody>' +
      seeds.map(s => {
        const viabTone = s.viability_pct === null ? 'var(--text-dim)' : s.viability_pct > 70 ? 'var(--green)' : s.viability_pct > 30 ? 'var(--orange)' : 'var(--red)';
        const viabLabel = s.viability_pct !== null ? s.viability_pct + '%' : 'Unknown';
        return `<tr><td><strong>${escapeHtml(s.species)}</strong></td><td>${escapeHtml(s.variety||'')}</td><td>${s.quantity}</td><td>${s.year_harvested||'-'}</td><td><span class="prep-inline-pill" style="--prep-pill-tone:${viabTone};">${viabLabel}</span></td><td>${s.planting_season}</td><td>${s.days_to_maturity||'-'}</td><td><button type="button" class="prep-record-delete" data-prep-action="delete-seed" data-seed-id="${s.id}" title="Delete seed" aria-label="Delete seed">&#10005;</button></td></tr>`;
      }).join('') + '</tbody></table></div>';
  } catch(e) {}
}

async function addSeed() {
  const speciesInput = document.getElementById('gs-species');
  const varietyInput = document.getElementById('gs-variety');
  const quantityInput = document.getElementById('gs-qty');
  const yearInput = document.getElementById('gs-year');
  const maturityInput = document.getElementById('gs-dtm');
  const seasonInput = document.getElementById('gs-season');
  if (!speciesInput || !varietyInput || !quantityInput || !yearInput || !maturityInput || !seasonInput) return;
  const species = speciesInput.value.trim();
  if (!species) { toast('Enter species name', 'warning'); return; }
  try {
    await apiPost('/api/garden/seeds', {
      species, variety: varietyInput.value.trim(),
      quantity: parseInt(quantityInput.value) || 50,
      year_harvested: parseInt(yearInput.value) || null,
      days_to_maturity: parseInt(maturityInput.value) || null,
      planting_season: seasonInput.value});
    ['gs-species','gs-variety','gs-qty','gs-year','gs-dtm','gs-season'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    toast('Seed added', 'success');
    loadSeeds();
  } catch(e) { toast('Failed to add seed', 'error'); }
}

async function deleteSeed(id) {
  if (!confirm('Remove this seed entry?')) return;
  try {
    await apiDelete('/api/garden/seeds/' + id);
    toast('Seed removed', 'warning');
    loadSeeds();
  } catch(e) { toast('Failed to remove seed', 'error'); }
}

let _companionData = [];
async function loadCompanions() {
  const el = document.getElementById('companion-grid');
  if (!el) return;
  _companionData = await safeFetch('/api/garden/companions', {}, []);
  renderCompanions(_companionData);
}
function renderCompanions(data) {
  const el = document.getElementById('companion-grid');
  if (!el) return;
  if (!data.length) {
    el.innerHTML = prepEmptyBlock('No companion matches for this search.');
    return;
  }
  el.innerHTML = data.map(c => {
    const isGood = c.relationship === 'companion';
    const color = isGood ? 'var(--green)' : 'var(--red)';
    const icon = isGood ? '\u2713' : '\u2717';
    return `<div class="prep-companion-card" style="--prep-companion-tone:${color};">
      <span class="prep-companion-icon">${icon}</span>
      <div class="prep-companion-body">
        <strong>${escapeHtml(c.plant_a)}</strong> + <strong>${escapeHtml(c.plant_b)}</strong>
        <div class="prep-companion-meta">${escapeHtml(c.notes||'')}</div>
      </div>
      <span class="prep-inline-pill" style="--prep-pill-tone:${color};">${c.relationship}</span>
    </div>`;
  }).join('');
}
function filterCompanions() {
  const q = (document.getElementById('companion-search')?.value||'').toLowerCase();
  if (!q) { renderCompanions(_companionData); return; }
  renderCompanions(_companionData.filter(c => c.plant_a.toLowerCase().includes(q) || c.plant_b.toLowerCase().includes(q)));
}

async function loadPestGuide() {
  const el = document.getElementById('pest-guide-grid');
  if (!el) return;
  const pests = await safeFetch('/api/garden/pests', {}, []);
  if (!pests.length) {
    el.innerHTML = prepEmptyBlock('No pest or disease guidance is available yet.');
    return;
  }
  el.innerHTML = pests.map(p => `
    <div class="prep-pest-card">
      <div class="prep-pest-head">
        <h4>${escapeHtml(p.name)}</h4>
        <span class="prep-inline-pill" style="--prep-pill-tone:var(--text-dim);">${escapeHtml(p.pest_type)}</span>
      </div>
      <div class="prep-pest-row"><span>Affects</span><strong>${escapeHtml(p.affects)}</strong></div>
      <div class="prep-pest-row"><span>Symptoms</span><strong>${escapeHtml(p.symptoms)}</strong></div>
      <div class="prep-pest-row"><span>Treatment</span><strong>${escapeHtml(p.treatment)}</strong></div>
      <div class="prep-pest-row"><span>Prevention</span><strong>${escapeHtml(p.prevention)}</strong></div>
    </div>
  `).join('');
}

async function loadHarvests() {
  try {
    const harvests = await apiFetch('/api/garden/harvests');
    const el = document.getElementById('harvest-list');
    if (!harvests.length) { el.innerHTML = prepEmptyBlock('No harvests logged yet. Record output as beds start producing.'); return; }
    const totalLbs = harvests.filter(h => h.unit === 'lbs').reduce((s, h) => s + h.quantity, 0);
    el.innerHTML = `<div class="prep-garden-summary-note">Total harvested: ${totalLbs.toFixed(1)} lbs across ${harvests.length} entries</div>` +
      '<div class="prep-table-wrap"><table class="freq-table prep-data-table"><thead><tr><th>Date</th><th>Crop</th><th>Quantity</th><th>Plot</th><th>Notes</th></tr></thead><tbody>' +
      harvests.map(h => `<tr><td>${new Date(h.created_at).toLocaleDateString()}</td><td><strong>${escapeHtml(h.crop)}</strong></td><td>${h.quantity} ${h.unit}</td><td>${escapeHtml(h.plot_name||'-')}</td><td>${escapeHtml(h.notes||'')}</td></tr>`).join('') +
      '</tbody></table></div>';
  } catch(e) {}
}

async function logHarvest() {
  const cropInput = document.getElementById('gh-crop');
  const quantityInput = document.getElementById('gh-qty');
  const unitInput = document.getElementById('gh-unit');
  const plotInput = document.getElementById('gh-plot');
  if (!cropInput || !quantityInput || !unitInput || !plotInput) return;
  const crop = cropInput.value.trim();
  if (!crop) { toast('Enter crop name', 'warning'); return; }
  try {
    await apiPost('/api/garden/harvests', {
      crop, quantity: parseFloat(quantityInput.value) || 0,
      unit: unitInput.value,
      plot_id: plotInput.value || null,
      notes: ''});
    cropInput.value = '';
    toast('Harvest logged and added to inventory!', 'success');
    loadHarvests();
  } catch(e) { console.error(e); toast('Failed to log harvest', 'error'); }
}

async function loadLivestockList() {
  try {
    const animals = await apiFetch('/api/livestock');
    const el = document.getElementById('livestock-list');
    if (!animals.length) { el.innerHTML = prepEmptyBlock('No livestock registered yet. Add animals above to track the herd.'); return; }
    const bySpecies = {};
    animals.forEach(a => { if (!bySpecies[a.species]) bySpecies[a.species] = []; bySpecies[a.species].push(a); });
    el.innerHTML = Object.entries(bySpecies).map(([species, list]) =>
      `<div class="prep-livestock-group">
        <div class="prep-livestock-heading">${escapeHtml(species)} (${list.length})</div>
        ${list.map(a => `<div class="prep-record-item">
          <div>
            <div class="prep-record-main"><strong>${escapeHtml(a.name || a.tag || '#' + a.id)}</strong> <span class="prep-inline-pill" style="--prep-pill-tone:${a.status === 'active' ? 'var(--green)' : 'var(--text-dim)'};">${escapeHtml(a.status)}</span></div>
            <div class="prep-record-meta">${[a.sex, a.weight_lbs ? `${a.weight_lbs} lbs` : '', a.dob ? `Born ${a.dob}` : ''].filter(Boolean).map(escapeHtml).join(' · ') || 'No extra details logged'}</div>
          </div>
          <div class="prep-camera-actions">
            <button type="button" class="btn btn-sm" data-prep-action="log-health-event" data-livestock-id="${a.id}" title="Log health event">Health</button>
            <button type="button" class="prep-record-delete" data-prep-action="delete-livestock" data-livestock-id="${a.id}" title="Delete animal" aria-label="Delete animal">&#10005;</button>
          </div>
        </div>`).join('')}
      </div>`
    ).join('');
  } catch(e) {}
}

async function addLivestock() {
  const speciesInput = document.getElementById('gl-species');
  const nameInput = document.getElementById('gl-name');
  const sexInput = document.getElementById('gl-sex');
  const dobInput = document.getElementById('gl-dob');
  const weightInput = document.getElementById('gl-weight');
  if (!speciesInput || !nameInput || !sexInput || !dobInput || !weightInput) return;
  const species = speciesInput.value;
  try {
    await apiPost('/api/livestock', {
      species, name: nameInput.value.trim(),
      sex: sexInput.value, dob: dobInput.value,
      weight_lbs: parseFloat(weightInput.value) || null});
    ['gl-species','gl-name','gl-sex','gl-dob','gl-weight'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    toast(species + ' added', 'success');
    loadLivestockList();
  } catch(e) { toast('Failed to add livestock', 'error'); }
}

async function deleteLivestock(id) {
  if (!confirm('Remove this animal?')) return;
  try {
    await apiDelete('/api/livestock/' + id);
    toast('Animal removed', 'warning');
    loadLivestockList();
  } catch(e) { toast('Failed to remove animal', 'error'); }
}

async function logHealthEvent(id) {
  const el = event.target.parentElement.parentElement;
  if (el.querySelector('.health-form')) return;
  const form = document.createElement('div');
  form.className = 'health-form prep-inline-form prep-garden-health-form';
    form.innerHTML = `<input id="he-${id}" class="prep-field-control" placeholder="Health event (e.g., dewormed, vaccinated, limping...)">
    <button type="button" class="btn btn-sm btn-primary" data-prep-action="submit-health-event" data-livestock-id="${id}">Log</button>`;
  el.appendChild(form);
  document.getElementById(`he-${id}`).focus();
}

async function submitHealthEvent(id) {
  const inp = document.getElementById(`he-${id}`);
  const event_text = inp?.value?.trim();
  if (!event_text) return;
  try {
    await apiPost(`/api/livestock/${id}/health`, {event: event_text});
    toast('Health event logged', 'success');
    loadLivestockList();
  } catch(e) { console.error(e); toast(e?.data?.error || 'Failed to log health event', 'error'); }
}

/* ─── Immersive Training Scenarios ─── */
const SCENARIOS = [
  { id:'grid_down', title:'Grid Down — 7 Days', icon:'&#9889;', desc:'Power grid fails. No electricity, no internet, limited fuel. Survive 7 days with your current supplies.',
    phases:[
      {title:'Day 1: The Blackout', desc:'Power went out 2 hours ago. Cell towers are down. Radio reports suggest a widespread grid failure affecting multiple states. No estimated restoration time.', choices:['Assess supplies and create inventory','Focus on securing the home first','Try to gather information via radio']},
      {title:'Day 2: Water Pressure Drops', desc:'Municipal water pressure is dropping. Your toilets flush weakly. Neighbors are panicking. You hear distant sirens.', choices:['Fill every container with water NOW','Start rationing existing water supply','Go to a store to buy bottled water']},
      {title:'Day 3: Food Decisions', desc:'Your refrigerator food is warming up. Freezer has maybe 24 more hours. Neighbors are asking if you have food to share.', choices:['Cook all perishables today and share with neighbors','Strict rationing — feed only your household','Cook perishables but keep it quiet']},
      {title:'Day 4: Security Concern', desc:'There was a break-in two streets over last night. No police response. Someone knocked on your door at 3 AM.', choices:['Organize a neighborhood watch','Increase home security and stay armed','Bug out to a safer location']},
      {title:'Day 5: Medical Issue', desc:'A family member develops a fever and stomach pain. Your antibiotics are limited. The nearest hospital is overwhelmed.', choices:['Treat with available medications and monitor','Try to reach the hospital','Ask neighbors if anyone has medical training']},
      {title:'Day 6: Communication', desc:'You make contact with someone via HAM/FRS radio who says power may return in 48 hours. But they also mention reports of violence in the next town.', choices:['Share info with neighbors and plan together','Keep the info to yourself and prepare quietly','Organize an armed patrol of your street']},
      {title:'Day 7: Resolution', desc:'Power flickers on, then off, then on again. Services are slowly restoring. What is your priority?', choices:['Restock and prepare for the next event','Document lessons learned and update plans','Help neighbors who struggled through the week']},
    ]},
  { id:'medical_crisis', title:'Medical Crisis', icon:'&#127973;', desc:'A family member has a serious injury. Professional medical help is hours away. You are the first responder.',
    phases:[
      {title:'The Injury', desc:'Someone fell from a ladder while repairing a roof. They are conscious but in severe pain. Their left forearm is visibly deformed — likely a fracture. There is a 3-inch laceration on their forehead bleeding steadily.', choices:['Address the bleeding first — head wounds bleed heavily','Immobilize the arm fracture first','Call 911 / send someone for help immediately']},
      {title:'Bleeding Control', desc:'The head wound is bleeding through your first gauze pad. The patient is pale and says they feel dizzy. Their pulse is rapid.', choices:['Apply direct pressure with a fresh pad on top','Pack the wound and wrap tightly with a pressure bandage','Elevate the head and apply a hemostatic agent']},
      {title:'Pain Management', desc:'The arm fracture is causing intense pain. The patient is shaking and having trouble staying calm. You have OTC medications available.', choices:['Administer ibuprofen 400mg for pain and inflammation','Give acetaminophen to avoid blood-thinning effects','Create an improvised splint before giving any meds']},
      {title:'Monitoring', desc:'It has been 2 hours. The head wound bleeding has stopped but the patient is drowsy. The splinted arm is swollen. Help is still 90+ minutes away.', choices:['Keep the patient awake and talking — monitor for concussion','Let them rest but check pupils and consciousness every 15 minutes','Begin transport yourself rather than wait for help']},
      {title:'Complication', desc:'The patient vomits and complains of increasing headache. Their pupils appear slightly unequal in size.', choices:['Assume concussion — keep them still, monitor airway','Begin immediate transport — this could be serious brain injury','Radio for emergency helicopter evacuation']},
    ]},
  { id:'evacuation', title:'Evacuation Under Threat', icon:'&#128663;', desc:'A wildfire / flood / civil unrest is approaching. You have 2 hours to evacuate with your family.',
    phases:[
      {title:'The Warning', desc:'Emergency alert: mandatory evacuation order for your area. Estimated 2 hours before conditions become dangerous. Roads are getting congested.', choices:['Execute your pre-planned evacuation route immediately','Take 30 minutes to pack essentials, then go','Wait for more information before deciding']},
      {title:'Packing', desc:'You need to load the vehicle. You can fit about 200 lbs of gear beyond the go-bags. What is your priority?', choices:['Water, food, and medical supplies','Important documents, cash, and electronics','Weapons, ammo, and security equipment']},
      {title:'Route Decision', desc:'Your primary route (highway) has heavy traffic — reports say it is near standstill. Your secondary route (back roads) is clear but 40 miles longer.', choices:['Take the highway — it moves slowly but is the shortest path','Take the back roads — less traffic, more distance','Wait 30 minutes to see if highway clears']},
      {title:'Roadblock', desc:'You encounter a road closure. Emergency vehicles are blocking the road. A detour adds 1 hour. You can see another route on the map that cuts through a rural area.', choices:['Follow the official detour','Take the unmarked rural route','Turn back and try a completely different direction']},
      {title:'Arrival', desc:'You reach your destination (rally point / family / shelter). But you realize you forgot something important.', choices:['Accept the loss and focus on setting up at the destination','Send someone back for the forgotten item','Use the radio to ask neighbors to grab it if they are still in the area']},
    ]},
  { id:'winter_storm', title:'Winter Storm Survival', icon:'&#10052;', desc:'A severe winter storm traps you at home. Power is out, roads impassable, temperatures dropping to -10F.',
    phases:[
      {title:'Storm Hits', desc:'Blizzard conditions. 2 feet of snow, wind gusts to 50 mph, temperature dropping fast. Power just went out. It was 68F inside — it will drop quickly.', choices:['Move everyone to one room and seal it for heat retention','Start the generator immediately','Light the fireplace/wood stove and gather all blankets']},
      {title:'Heating Crisis', desc:'4 hours in. Inside temperature is now 45F and dropping. Your heating fuel (wood/gas/propane) is limited. Outside is -5F with windchill of -25F.', choices:['Ration fuel — heat only during sleeping hours','Use all fuel to maintain minimum temperature','Build an insulated shelter-within-a-shelter in one room']},
      {title:'Water Pipes', desc:'You hear a pipe burst in the bathroom. Water is spraying. The shutoff valve is in the basement which is already below freezing.', choices:['Rush to shut off the main water valve before more damage','Let it freeze — it will stop on its own','Collect the spraying water in containers before shutting off']},
      {title:'Day 3: Running Low', desc:'Storm continues. Food is holding up but water is a problem — pipes are frozen, snow melt is slow. A neighbor comes to your door asking for help — their house has no heat at all.', choices:['Take them in — more body heat and shared resources','Give them blankets and some supplies but keep your space','Invite the whole neighborhood to consolidate in your house']},
      {title:'Rescue', desc:'Day 5. Storm is finally clearing. Plows are working but your road is not priority. You can see the main road from your house. A neighbor\'s elderly parent needs medication.', choices:['Attempt to walk to the main road for help','Wait for plows — could be hours more','Use a vehicle to push through the snow to the road']},
    ]},
];

let _activeScenario = null;
let _scenarioDbId = null;
let _scenarioDecisions = [];
let _scenarioComplications = [];

function getScenarioToneClass(score) {
  if (score >= 80) return 'scenario-tone-good';
  if (score >= 60) return 'scenario-tone-watch';
  return 'scenario-tone-risk';
}

function renderScenarioSelector() {
  document.getElementById('scenario-selector').innerHTML = SCENARIOS.map(s => `
    <button type="button" class="guide-tile" data-prep-action="start-scenario" data-scenario-id="${s.id}">
      <h4><span class="layout-margin-right-6">${s.icon}</span>${s.title}</h4>
      <p>${s.desc}</p>
      <div class="runtime-progress-count">${s.phases.length} phases</div>
    </button>
  `).join('');
}

async function startScenario(id) {
  _activeScenario = SCENARIOS.find(s => s.id === id);
  if (!_activeScenario) return;
  _scenarioDecisions = [];
  _scenarioComplications = [];
  // Create DB record
  try {
    const r = await apiPost('/api/scenarios', {type: id, title: _activeScenario.title});
    _scenarioDbId = r.id;
  } catch(e) { _scenarioDbId = null; }
  document.getElementById('scenario-selector').style.display = 'none';
  document.getElementById('scenario-active').style.display = 'block';
  document.getElementById('scenario-active').classList.remove('is-hidden');
  renderScenarioPhase(0);
  toast(`Scenario started: ${_activeScenario.title}`, 'info');
}

function renderScenarioPhase(phaseIdx) {
  if (!_activeScenario || phaseIdx >= _activeScenario.phases.length) {
    completeScenario();
    return;
  }
  const phase = _activeScenario.phases[phaseIdx];
  const el = document.getElementById('scenario-active');
  const progress = Math.round((phaseIdx / _activeScenario.phases.length) * 100);
  el.innerHTML = `
    <div class="scenario-phase-header">
      <span class="scenario-phase-title">${_activeScenario.icon} ${escapeHtml(_activeScenario.title)}</span>
      <div class="scenario-phase-toolbar">
        <span class="scenario-phase-meta">Phase ${phaseIdx + 1} of ${_activeScenario.phases.length}</span>
        <button type="button" class="btn btn-sm btn-danger" data-prep-action="abandon-scenario">Abandon</button>
      </div>
    </div>
    <div class="scenario-phase-overview">
      <div class="scenario-phase-stat">
        <span class="scenario-phase-stat-kicker">Phase</span>
        <strong class="scenario-phase-stat-value">${phaseIdx + 1}/${_activeScenario.phases.length}</strong>
        <span class="scenario-phase-stat-note">${Math.max(_activeScenario.phases.length - (phaseIdx + 1), 0)} remaining after this one</span>
      </div>
      <div class="scenario-phase-stat">
        <span class="scenario-phase-stat-kicker">Decisions logged</span>
        <strong class="scenario-phase-stat-value">${_scenarioDecisions.length}</strong>
        <span class="scenario-phase-stat-note">Your choices shape the review.</span>
      </div>
      <div class="scenario-phase-stat">
        <span class="scenario-phase-stat-kicker">Complications</span>
        <strong class="scenario-phase-stat-value">${_scenarioComplications.length}</strong>
        <span class="scenario-phase-stat-note">Unexpected events already introduced.</span>
      </div>
    </div>
    <div class="progress-bar scenario-phase-progress"><div class="fill scenario-phase-fill" style="width:${progress}%;"></div></div>
    <div class="scenario-phase-card">
      <h4 class="scenario-phase-name">${escapeHtml(phase.title)}</h4>
      <p class="scenario-phase-copy">${escapeHtml(phase.desc)}</p>
      <div class="scenario-phase-prompt">What do you do?</div>
      <div class="scenario-choice-list">
        ${phase.choices.map((c, i) => `
          <button type="button" class="guide-option scenario-option" data-prep-action="scenario-choose" data-scenario-phase="${phaseIdx}" data-scenario-choice-index="${i}" data-scenario-choice-label="${escapeAttr(c)}">${escapeHtml(c)}</button>
        `).join('')}
      </div>
    </div>
  `;
}

async function scenarioChoose(phaseIdx, choiceIdx, choiceLabel) {
  const phase = _activeScenario.phases[phaseIdx];
  _scenarioDecisions.push({phase: phaseIdx, label: phase.title, choice: choiceLabel, time: new Date().toISOString()});

  // Save to DB
  if (_scenarioDbId) {
    apiPut(`/api/scenarios/${_scenarioDbId}`,
      {current_phase: phaseIdx + 1, decisions: _scenarioDecisions, complications: _scenarioComplications})
      .catch(e => console.warn('[Scenario] save failed:', e.message));
  }

  // 50% chance of AI complication between phases (not on last phase)
  const nextPhase = phaseIdx + 1;
  if (nextPhase < _activeScenario.phases.length && Math.random() < 0.5) {
    await showComplication(phaseIdx);
  } else {
    renderScenarioPhase(nextPhase);
  }
}

async function showComplication(afterPhase) {
  const el = document.getElementById('scenario-active');
  el.innerHTML = `
    <div class="scenario-loading-state">
      <div class="scenario-loading-icon">&#9888;</div>
      <div class="scenario-loading-copy">Generating complication...</div>
    </div>`;

  try {
    const phase = _activeScenario.phases[afterPhase];
    const comp = await apiPost(`/api/scenarios/${_scenarioDbId || 0}/complication`, {
      phase_description: phase.title + ': ' + phase.desc,
      decisions: _scenarioDecisions
    });
    if (comp?.error) throw new Error(comp.error);

    _scenarioComplications.push({...comp, response: '', phase: afterPhase});

    el.innerHTML = `
      <div class="scenario-complication-card">
        <div class="scenario-phase-overview scenario-phase-overview-alert">
          <div class="scenario-phase-stat">
            <span class="scenario-phase-stat-kicker">Complication</span>
            <strong class="scenario-phase-stat-value">${_scenarioComplications.length}</strong>
            <span class="scenario-phase-stat-note">Unexpected pressure inserted between phases.</span>
          </div>
          <div class="scenario-phase-stat">
            <span class="scenario-phase-stat-kicker">Decision trail</span>
            <strong class="scenario-phase-stat-value">${_scenarioDecisions.length}</strong>
            <span class="scenario-phase-stat-note">Choices already recorded in this run.</span>
          </div>
        </div>
        <div class="scenario-complication-label">&#9888; Complication</div>
        <h4 class="scenario-complication-title">${escapeHtml(comp.title || 'Unexpected Event')}</h4>
        <p class="scenario-complication-copy">${escapeHtml(comp.description || '')}</p>
        <div class="scenario-phase-prompt">How do you respond?</div>
        <div class="scenario-choice-list">
        ${(comp.choices || ['Deal with it','Ignore it','Adapt']).map((c, i) => `
          <button type="button" class="guide-option scenario-option scenario-option-alert" data-prep-action="scenario-complication-respond" data-scenario-after-phase="${afterPhase}" data-scenario-choice-index="${i}" data-scenario-choice-label="${escapeAttr(c)}">${escapeHtml(c)}</button>
        `).join('')}
        </div>
      </div>`;
    playAlertSound('broadcast');
  } catch(e) {
    toast(e?.data?.error || e.message || 'Failed to generate complication', 'error');
    renderScenarioPhase(afterPhase + 1);
  }
}

function complicationRespond(afterPhase, choiceIdx, choiceLabel) {
  const lastComp = _scenarioComplications[_scenarioComplications.length - 1];
  if (lastComp) lastComp.response = choiceLabel;
  toast('Complication handled', 'info');
  renderScenarioPhase(afterPhase + 1);
}

async function completeScenario() {
  const el = document.getElementById('scenario-active');
  el.innerHTML = `
    <div class="scenario-complete-state">
      <div class="scenario-complete-icon">&#127942;</div>
      <div class="scenario-complete-title">Scenario Complete!</div>
      <div class="scenario-complete-copy">Generating After-Action Review...</div>
      <div class="utility-progress scenario-complete-progress">
        <div class="utility-progress-bar scenario-complete-progress-bar"></div>
      </div>
    </div>`;

  try {
    const aar = await apiPost(`/api/scenarios/${_scenarioDbId || 0}/aar`, {
      decisions: _scenarioDecisions,
      complications: _scenarioComplications
    });
    if (aar?.error) throw new Error(aar.error);
    const score = aar.score || 50;
    const scoreToneClass = getScenarioToneClass(score);

    // Save final state
    if (_scenarioDbId) {
      apiPut(`/api/scenarios/${_scenarioDbId}`,
        {status:'complete', current_phase: _activeScenario.phases.length,
          decisions: _scenarioDecisions, complications: _scenarioComplications,
          score, aar_text: aar.aar, completed_at: new Date().toISOString()})
        .catch(e => console.warn('[Scenario] final save failed:', e.message));
    }

    el.innerHTML = `
      <div class="scenario-phase-card scenario-result-card">
        <div class="scenario-phase-overview scenario-result-overview">
          <div class="scenario-phase-stat">
            <span class="scenario-phase-stat-kicker">Decisions</span>
            <strong class="scenario-phase-stat-value">${_scenarioDecisions.length}</strong>
            <span class="scenario-phase-stat-note">Phase choices captured.</span>
          </div>
          <div class="scenario-phase-stat">
            <span class="scenario-phase-stat-kicker">Complications handled</span>
            <strong class="scenario-phase-stat-value">${_scenarioComplications.length}</strong>
            <span class="scenario-phase-stat-note">Pressure points logged for review.</span>
          </div>
          <div class="scenario-phase-stat">
            <span class="scenario-phase-stat-kicker">Result</span>
            <strong class="scenario-phase-stat-value">${score}/100</strong>
            <span class="scenario-phase-stat-note">Your overall run score.</span>
          </div>
        </div>
        <div class="scenario-score-wrap">
          <div class="scenario-score-value ${scoreToneClass}">${score}<span class="scenario-score-total">/100</span></div>
<div class="scenario-score-label">NOMAD Score</div>
        </div>
        <h4 class="scenario-section-title">After-Action Review</h4>
        <div class="scenario-aar-copy">${escapeHtml(aar.aar || 'No review available.')}</div>
        <h4 class="scenario-section-title-small">Your Decisions (${_scenarioDecisions.length} phases, ${_scenarioComplications.length} complications):</h4>
        <div class="scenario-decision-list">
          ${_scenarioDecisions.map(d => `<div class="scenario-decision-item"><strong>${escapeHtml(d.label)}:</strong> ${escapeHtml(d.choice)}</div>`).join('')}
          ${_scenarioComplications.filter(c=>c.response).map(c => `<div class="scenario-decision-item scenario-decision-item-alert"><strong>&#9888; ${escapeHtml(c.title||'')}:</strong> ${escapeHtml(c.response)}</div>`).join('')}
        </div>
        <div class="scenario-actions">
          <button type="button" class="btn btn-sm btn-primary" data-prep-action="start-scenario" data-scenario-id="${_activeScenario.id}">Run Again</button>
          <button type="button" class="btn btn-sm" data-prep-action="close-scenario">Back to Scenarios</button>
        </div>
      </div>`;
      sendNotification('Scenario Complete', `${_activeScenario.title}: ${score}/100`);
  } catch(e) {
    toast(e?.data?.error || e.message || 'Failed to generate after-action review', 'error');
    el.innerHTML = `<div class="scenario-error-state">Failed to generate review. <button type="button" class="btn btn-sm" data-prep-action="close-scenario">Back</button></div>`;
  }
}

function abandonScenario() {
  if (_scenarioDbId) {
    apiPut(`/api/scenarios/${_scenarioDbId}`,
      {status:'abandoned', decisions: _scenarioDecisions, complications: _scenarioComplications})
      .catch(e => console.warn('[Scenario] abandon save failed:', e.message));
  }
  closeScenario();
  toast('Scenario abandoned', 'warning');
}

function closeScenario() {
  _activeScenario = null;
  _scenarioDbId = null;
  _scenarioDecisions = [];
  _scenarioComplications = [];
  document.getElementById('scenario-active').style.display = 'none';
  document.getElementById('scenario-active').classList.add('is-hidden');
  document.getElementById('scenario-selector').style.display = 'grid';
  renderScenarioSelector();
}

async function loadScenarioHistory() {
  const el = document.getElementById('scenario-history');
  try {
    const scenarios = await safeFetch('/api/scenarios', {}, []);
    const completed = scenarios.filter(s => s.status === 'complete');
    if (!completed.length) {
      el.style.display = 'block';
      el.classList.remove('is-hidden');
      el.innerHTML = '<div class="scenario-history-empty">No completed scenarios yet.</div>';
      return;
    }
    const ordered = [...completed].sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
    const avgScore = Math.round(ordered.reduce((sum, scenario) => sum + (scenario.score || 0), 0) / ordered.length);
    const highestScore = Math.max(...ordered.map(scenario => scenario.score || 0));
    el.style.display = 'block';
    el.classList.remove('is-hidden');
    el.innerHTML = `
      <div class="scenario-history-summary">
        <div class="scenario-history-stat">
          <span class="scenario-history-kicker">Completed runs</span>
          <strong class="scenario-history-value">${ordered.length}</strong>
          <span class="scenario-history-note">Use repeat runs to sharpen decisions under pressure.</span>
        </div>
        <div class="scenario-history-stat">
          <span class="scenario-history-kicker">Average score</span>
          <strong class="scenario-history-value">${avgScore}/100</strong>
          <span class="scenario-history-note">Across all completed simulations.</span>
        </div>
        <div class="scenario-history-stat">
          <span class="scenario-history-kicker">Best result</span>
          <strong class="scenario-history-value">${highestScore}/100</strong>
          <span class="scenario-history-note">Your cleanest run so far.</span>
        </div>
      </div>
      <div class="scenario-history-grid">
        ${ordered.map(s => {
          const toneClass = getScenarioToneClass(s.score || 0);
          return `
            <article class="scenario-history-record">
              <div class="scenario-history-record-head">
                <div>
                  <div class="scenario-history-date">${new Date(s.started_at).toLocaleDateString([], {month:'short', day:'numeric'})}</div>
                  <h4 class="scenario-history-title">${escapeHtml(s.title)}</h4>
                </div>
                <span class="scenario-history-score ${toneClass}">${s.score}/100</span>
              </div>
              <div class="scenario-history-meta">
                <span class="scenario-history-detail">${s.decisions.length} phase decision${s.decisions.length === 1 ? '' : 's'}</span>
                <span class="scenario-history-detail">${s.complications.length} complication${s.complications.length === 1 ? '' : 's'}</span>
              </div>
            </article>
          `;
        }).join('')}
      </div>
    `;
  } catch(e) {
    el.style.display = 'block';
    el.classList.remove('is-hidden');
    el.innerHTML = '<div class="scenario-error-state">Failed to load history</div>';
  }
}

// Init scenario selector when tools tab loads
(function() {
  const origToolsLoad = document.querySelector('[data-tab="tools"]');
  if (origToolsLoad) {
    const origClick = origToolsLoad.onclick;
    // Selector will render on first view
  }
})();

/* ─── Medical Module ─── */
let _activePatientId = null;
let _patients = [];

async function loadPatients() {
  try {
    _patients = await apiFetch('/api/patients');
    const el = document.getElementById('patient-list');
    if (!_patients.length) {
      el.innerHTML = prepEmptyBlock('No patients registered. Click "+ Add Patient" or "Import from Contacts" to start.');
      return;
    }
    el.innerHTML = _patients.map(p => {
      const allergies = (p.allergies || []).join(', ') || 'NKDA';
      const meds = (p.medications || []).join(', ') || 'None';
      const allergyWarn = p.allergies?.length > 0;
      return `<div class="contact-card">
        <div class="cc-name">${escapeHtml(p.name)}</div>
        <div class="cc-role">${p.age ? p.age + ' yr' : ''} ${p.sex || ''} ${p.weight_kg ? '| ' + p.weight_kg + ' kg' : ''} ${p.blood_type ? '| ' + p.blood_type : ''}</div>
        ${allergyWarn ? `<div><span class="prep-inline-pill" style="--prep-pill-tone:var(--red);">Allergies</span> <span class="prep-record-meta">${escapeHtml(allergies)}</span></div>` : '<div><span class="prep-inline-pill" style="--prep-pill-tone:var(--green);">NKDA</span></div>'}
        <div class="cc-field"><strong>Meds:</strong> ${escapeHtml(meds)}</div>
        ${p.conditions?.length ? `<div class="cc-field"><strong>Conditions:</strong> ${escapeHtml(p.conditions.join(', '))}</div>` : ''}
        <div class="cc-actions runtime-wrap-actions">
          <button type="button" class="btn btn-sm btn-primary" data-prep-action="open-vitals-panel" data-patient-id="${p.id}">Vitals</button>
          <button type="button" class="btn btn-sm btn-danger" data-prep-action="start-tccc" data-patient-id="${p.id}">TCCC</button>
          <button type="button" class="btn btn-sm" data-prep-action="generate-handoff" data-patient-id="${p.id}">Handoff</button>
          <button type="button" class="btn btn-sm" data-prep-action="edit-patient" data-patient-id="${p.id}">Edit</button>
          <button type="button" class="btn btn-sm" data-app-frame-title="Patient Card" data-app-frame-url="/api/patients/${p.id}/card">Card</button>
          <button type="button" class="btn btn-sm btn-danger" data-prep-action="delete-patient" data-patient-id="${p.id}">Del</button>
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    document.getElementById('patient-list').innerHTML = '<div class="prep-error-state prep-empty-block">Failed to load patients.</div>';
  }
}

const _ptFields = {name:'pt-name', age:'pt-age', weight:'pt-weight', sex:'pt-sex', blood:'pt-blood', allergies:'pt-allergies', meds:'pt-meds', conditions:'pt-conditions', notes:'pt-notes'};
let _ptRecoveryAttached = false;
function showPatientForm(patient) {
  const form = document.getElementById('patient-form');
  const nameInput = document.getElementById('pt-name');
  const ageInput = document.getElementById('pt-age');
  const weightInput = document.getElementById('pt-weight');
  const sexInput = document.getElementById('pt-sex');
  const bloodInput = document.getElementById('pt-blood');
  const allergiesInput = document.getElementById('pt-allergies');
  const medsInput = document.getElementById('pt-meds');
  const conditionsInput = document.getElementById('pt-conditions');
  const notesInput = document.getElementById('pt-notes');
  const editIdInput = document.getElementById('pt-edit-id');
  const interactionResults = document.getElementById('interaction-results');
  if (!form || !nameInput || !ageInput || !weightInput || !sexInput || !bloodInput || !allergiesInput || !medsInput || !conditionsInput || !notesInput || !editIdInput || !interactionResults) return;
  form.style.display = 'block';
  nameInput.value = patient?.name || '';
  ageInput.value = patient?.age || '';
  weightInput.value = patient?.weight_kg || '';
  sexInput.value = patient?.sex || '';
  bloodInput.value = patient?.blood_type || '';
  allergiesInput.value = (patient?.allergies || []).join(', ');
  medsInput.value = (patient?.medications || []).join(', ');
  conditionsInput.value = (patient?.conditions || []).join(', ');
  notesInput.value = patient?.notes || '';
  editIdInput.value = patient?.id || '';
  interactionResults.style.display = 'none';
  if (!patient) {
    if (FormStateRecovery.restore('patient', _ptFields)) {
      toast('Recovered unsaved patient data', 'info');
    }
  }
  if (!_ptRecoveryAttached) { FormStateRecovery.attach('patient', _ptFields); _ptRecoveryAttached = true; }
}
function hidePatientForm() {
  const form = document.getElementById('patient-form');
  if (!form) return;
  form.style.display = 'none';
  FormStateRecovery.clear('patient');
}

async function savePatient() {
  const nameInput = document.getElementById('pt-name');
  const ageInput = document.getElementById('pt-age');
  const weightInput = document.getElementById('pt-weight');
  const sexInput = document.getElementById('pt-sex');
  const bloodInput = document.getElementById('pt-blood');
  const allergiesInput = document.getElementById('pt-allergies');
  const medsInput = document.getElementById('pt-meds');
  const conditionsInput = document.getElementById('pt-conditions');
  const notesInput = document.getElementById('pt-notes');
  const editIdInput = document.getElementById('pt-edit-id');
  if (!nameInput || !ageInput || !weightInput || !sexInput || !bloodInput || !allergiesInput || !medsInput || !conditionsInput || !notesInput || !editIdInput) return;
  const name = nameInput.value.trim();
  if (!name) { toast('Patient name required', 'warning'); return; }
  const data = {
    name, age: parseInt(ageInput.value) || null,
    weight_kg: parseFloat(weightInput.value) || null,
    sex: sexInput.value,
    blood_type: bloodInput.value,
    allergies: allergiesInput.value.split(',').map(s => s.trim()).filter(Boolean),
    medications: medsInput.value.split(',').map(s => s.trim()).filter(Boolean),
    conditions: conditionsInput.value.split(',').map(s => s.trim()).filter(Boolean),
    notes: notesInput.value.trim(),
  };
  const editId = editIdInput.value;
  try {
    let resp;
    if (editId) {
      await apiPut('/api/patients/' + editId, data);
      toast('Patient updated', 'success');
    } else {
      await apiPost('/api/patients', data);
      toast('Patient added', 'success');
    }
    FormStateRecovery.clear('patient');
    hidePatientForm();
    loadPatients();
  } catch(e) { console.error(e); toast('Failed to save patient', 'error'); }
}

function editPatient(id) {
  const p = _patients.find(x => x.id === id);
  if (p) showPatientForm(p);
}

async function deletePatient(id) {
  const btn = event.target;
  if (!btn.dataset.confirm) {
    btn.dataset.confirm = '1'; btn.textContent = 'Confirm?';
      btn.classList.add('is-confirming');
    setTimeout(() => { btn.textContent = 'Delete'; btn.classList.remove('is-confirming'); delete btn.dataset.confirm; }, 3000);
    return;
  }
  try {
    await apiDelete('/api/patients/' + id);
    toast('Patient removed', 'warning');
    if (_activePatientId === id) closeVitalsPanel();
    loadPatients();
  } catch(e) { toast('Failed to remove patient', 'error'); }
}

async function addPatientFromContacts() {
  try {
    const contacts = await safeFetch('/api/contacts', {}, []);
    if (!contacts.length) { toast('No contacts found. Add contacts first.', 'warning'); return; }
    const newContacts = contacts.filter(c => !_patients.some(p => p.name === c.name));
    await Promise.all(newContacts.map(c =>
      apiPost('/api/patients', {name: c.name, contact_id: c.id, blood_type: c.blood_type || '', notes: c.medical_notes || ''})
        .catch(e => console.warn('[Medical] patient import failed:', e.message))
    ));
    toast('Contacts imported as patients', 'success');
    loadPatients();
  } catch(e) { toast('Import failed', 'error'); }
}

async function checkDrugInteractions() {
  const el = document.getElementById('interaction-results');
  const medsInput = document.getElementById('pt-meds');
  if (!el || !medsInput) return;
  const meds = medsInput.value.split(',').map(s => s.trim()).filter(Boolean);
  if (meds.length < 2) { el.style.display = 'block'; el.innerHTML = '<div class="prep-status-copy">Enter 2+ medications to check interactions.</div>'; return; }
  try {
    const interactions = await safeFetch('/api/medical/interactions', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({medications: meds})}, null);
    if (!Array.isArray(interactions)) throw new Error('interaction lookup unavailable');
    el.style.display = 'block';
    if (!interactions.length) {
      el.innerHTML = '<div class="prep-med-result-card prep-med-result-card-success">No known interactions found between these medications.</div>';
    } else {
      el.innerHTML = `<div class="prep-med-result-stack">` + interactions.map(i => {
        const color = i.severity === 'major' ? 'var(--red)' : 'var(--orange)';
        const toneClass = i.severity === 'major' ? 'prep-med-result-card-danger' : 'prep-med-result-card-warning';
        return `<div class="prep-med-result-card ${toneClass}">
          <strong class="prep-med-result-title" style="--prep-med-tone:${color};">${i.severity.toUpperCase()}: ${escapeHtml(i.drug1)} + ${escapeHtml(i.drug2)}</strong>
          <div class="prep-med-result-copy">${escapeHtml(i.detail)}</div>
        </div>`;
      }).join('') + `</div>`;
    }
  } catch(e) { el.style.display = 'block'; el.innerHTML = '<div class="prep-med-result-card prep-med-result-card-danger">Interaction check failed.</div>'; }
}

async function loadDosageDrugs() {
  const drugs = await safeFetch('/api/medical/dosage-drugs', {}, []);
  const sel = document.getElementById('dc-drug');
  if (!sel) return;
  sel.innerHTML = '<option value="">Select drug...</option>';
  drugs.forEach(d => {
    const opt = document.createElement('option');
    opt.value = d.drug;
    opt.textContent = `${d.drug} (${d['class']})`;
    sel.appendChild(opt);
  });
}

function loadDosageCalculator() {
  loadDosageDrugs();
  // Populate patient dropdown from existing _patients list
  const pSel = document.getElementById('dc-patient');
  const ageInput = document.getElementById('dc-age');
  const weightInput = document.getElementById('dc-weight');
  if (!pSel || !ageInput || !weightInput) return;
  pSel.innerHTML = '<option value="">Manual entry</option>';
  if (typeof _patients !== 'undefined' && _patients.length) {
    _patients.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.name}${p.age ? ' (age ' + p.age + ')' : ''}`;
      pSel.appendChild(opt);
    });
  }
  // When patient selected, auto-fill age/weight
  pSel.onchange = function() {
    if (!this.value || typeof _patients === 'undefined') return;
    const p = _patients.find(x => x.id == this.value);
    if (p) {
      if (p.age) ageInput.value = p.age;
      if (p.weight_kg) weightInput.value = p.weight_kg;
    }
  };
}

async function calculateDosage() {
  const drugSelect = document.getElementById('dc-drug');
  const patientSelect = document.getElementById('dc-patient');
  const ageInput = document.getElementById('dc-age');
  const weightInput = document.getElementById('dc-weight');
  const el = document.getElementById('dosage-results');
  if (!drugSelect || !patientSelect || !ageInput || !weightInput || !el) return;
  const drug = drugSelect.value;
  if (!drug) { toast('Select a drug first', 'warning'); return; }

  const patientId = patientSelect.value || null;
  const age = ageInput.value ? parseInt(ageInput.value) : null;
  const weightKg = weightInput.value ? parseFloat(weightInput.value) : null;

  const body = { drug, patient_id: patientId ? parseInt(patientId) : null, age, weight_kg: weightKg };
  try {
    const data = await apiPost('/api/medical/dosage-calculator', body);
    el.style.display = 'block';

    if (data.error) {
      el.innerHTML = `<div class="prep-med-result-card prep-med-result-card-danger">${escapeHtml(data.error)}</div>`;
      return;
    }

    let html = '';

    if (data.blocked) {
      html += `<div class="prep-med-result-card prep-med-result-card-danger prep-med-dose-blocked">
        <strong class="prep-med-dose-blocked-title">Contraindicated</strong>
        <div class="prep-med-result-copy">Do not administer this drug. See warnings below.</div>
      </div>`;
    }

    if (data.warnings && data.warnings.length) {
      html += data.warnings.map(w => {
        const isBlock = w.type === 'ALLERGY_BLOCK' || w.type === 'AGE_BLOCK';
        const isMajor = w.type.includes('MAJOR');
        const color = isBlock || isMajor ? 'var(--red)' : 'var(--orange)';
        return `<div class="prep-med-result-card ${isBlock || isMajor ? 'prep-med-result-card-danger' : 'prep-med-result-card-warning'}">
          <strong class="prep-med-result-title" style="--prep-med-tone:${color};">${escapeHtml(w.type)}</strong>
          <div class="prep-med-result-copy">${escapeHtml(w.message)}</div>
        </div>`;
      }).join('');
    }

    html += `<div class="prep-med-dose-card">
      <div class="prep-med-dose-grid">
        <div><strong>Drug:</strong> ${escapeHtml(data.drug)}</div>
        <div><strong>Class:</strong> ${escapeHtml(data.drug_class)}</div>
        <div><strong>Dose:</strong> ${escapeHtml(data.dose)}</div>
        <div><strong>Max Dose:</strong> ${escapeHtml(data.max_dose)}</div>
        ${data.calculated_mg ? `<div class="prep-med-dose-highlight"><strong>Calculated Dose:</strong> <span>${data.calculated_mg}mg</span> (for ${data.weight_kg}kg)</div>` : ''}
        <div><strong>Patient Type:</strong> ${data.is_pediatric ? 'Pediatric' : 'Adult'}${data.age != null ? ' (age ' + data.age + ')' : ''}</div>
      </div>
      <div class="prep-med-dose-note">
        <strong>Notes:</strong> ${escapeHtml(data.notes)}
      </div>
    </div>`;

    el.innerHTML = html;
  } catch(e) { el.style.display = 'block'; el.innerHTML = '<div class="prep-med-result-card prep-med-result-card-danger">Dosage calculation failed.</div>'; }
}

async function openVitalsPanel(patientId) {
  _activePatientId = patientId;
  const p = _patients.find(x => x.id === patientId);
  if (!p) return;
  const panel = document.getElementById('vitals-panel');
  const woundForm = document.getElementById('wound-form');
  const titleEl = document.getElementById('vitals-patient-name');
  const banner = document.getElementById('vitals-allergy-banner');
  if (!panel || !woundForm || !titleEl || !banner) return;
  panel.style.display = 'block';
  woundForm.style.display = 'none';
  titleEl.textContent = `${p.name} — Vitals & Wounds`;
  if (p.allergies?.length) {
    banner.style.display = 'block';
    banner.textContent = 'ALLERGIES: ' + p.allergies.join(', ');
  } else { banner.style.display = 'none'; }
  await loadVitals(patientId);
  await loadWounds(patientId);
  loadVitalsTrend(patientId);
}

function closeVitalsPanel() {
  _activePatientId = null;
  hideWoundForm();
  const panel = document.getElementById('vitals-panel');
  if (!panel) return;
  panel.style.display = 'none';
}

async function logVitals() {
  if (!_activePatientId) return;
  const systolicInput = document.getElementById('v-bps');
  const diastolicInput = document.getElementById('v-bpd');
  const pulseInput = document.getElementById('v-pulse');
  const respInput = document.getElementById('v-resp');
  const tempInput = document.getElementById('v-temp');
  const spo2Input = document.getElementById('v-spo2');
  const painInput = document.getElementById('v-pain');
  const gcsInput = document.getElementById('v-gcs');
  const notesInput = document.getElementById('v-notes');
  if (!systolicInput || !diastolicInput || !pulseInput || !respInput || !tempInput || !spo2Input || !painInput || !gcsInput || !notesInput) return;
  const data = {
    bp_systolic: parseInt(systolicInput.value) || null,
    bp_diastolic: parseInt(diastolicInput.value) || null,
    pulse: parseInt(pulseInput.value) || null,
    resp_rate: parseInt(respInput.value) || null,
    temp_f: parseFloat(tempInput.value) || null,
    spo2: parseInt(spo2Input.value) || null,
    pain_level: parseInt(painInput.value) || null,
    gcs: parseInt(gcsInput.value) || null,
    notes: notesInput.value.trim(),
  };
  if (!data.bp_systolic && !data.pulse && !data.temp_f && !data.spo2) { toast('Enter at least one vital sign', 'warning'); return; }
  try {
    await apiPost(`/api/patients/${_activePatientId}/vitals`, data);
    toast('Vitals logged', 'success');
    [systolicInput, diastolicInput, pulseInput, respInput, tempInput, spo2Input, painInput, gcsInput, notesInput].forEach(input => { input.value = ''; });
    await loadVitals(_activePatientId);
    await loadVitalsTrend(_activePatientId);
  } catch(e) { console.error(e); toast(e?.data?.error || 'Failed to log vitals', 'error'); }
}

async function loadVitals(pid) {
  try {
    const vitals = await apiFetch(`/api/patients/${pid}/vitals`);
    const tbody = document.getElementById('vitals-tbody');
    if (!tbody) return;
    if (!vitals.length) { tbody.innerHTML = '<tr><td colspan="9" class="prep-table-empty">No vitals recorded. Use the form above to log.</td></tr>'; return; }
    tbody.innerHTML = vitals.map(v => {
      const bp = v.bp_systolic ? `${v.bp_systolic}/${v.bp_diastolic}` : '-';
      const t = new Date(v.created_at);
      const ts = t.toLocaleDateString([], {month:'short',day:'numeric'}) + ' ' + t.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
      const pulseTone = v.pulse > 100 ? 'var(--red)' : v.pulse < 50 ? 'var(--orange)' : '';
      const spo2Tone = v.spo2 && v.spo2 < 92 ? 'var(--red)' : '';
      const tempTone = v.temp_f && v.temp_f > 101 ? 'var(--red)' : v.temp_f && v.temp_f < 96 ? 'var(--orange)' : '';
      const pulse = v.pulse == null ? '-' : pulseTone ? `<span class="prep-inline-pill" style="--prep-pill-tone:${pulseTone};">${v.pulse}</span>` : v.pulse;
      const temp = v.temp_f == null ? '-' : tempTone ? `<span class="prep-inline-pill" style="--prep-pill-tone:${tempTone};">${v.temp_f}</span>` : v.temp_f;
      const spo2 = v.spo2 == null ? '-' : spo2Tone ? `<span class="prep-inline-pill" style="--prep-pill-tone:${spo2Tone};">${v.spo2}%</span>` : `${v.spo2}%`;
      return `<tr><td>${ts}</td><td>${bp}</td><td>${pulse}</td><td>${v.resp_rate||'-'}</td><td>${temp}</td><td>${spo2}</td><td>${v.pain_level!=null ? v.pain_level+'/10' : '-'}</td><td>${v.gcs||'-'}</td><td>${escapeHtml(v.notes||'')}</td></tr>`;
    }).join('');
  } catch(e) {}
}

function showWoundForm() {
  const form = document.getElementById('wound-form');
  if (!form) return;
  form.style.display = 'block';
}

function hideWoundForm() {
  const form = document.getElementById('wound-form');
  if (!form) return;
  form.style.display = 'none';
}

async function logWound() {
  if (!_activePatientId) return;
  const locationInput = document.getElementById('w-loc');
  const typeInput = document.getElementById('w-type');
  const severityInput = document.getElementById('w-sev');
  const descriptionInput = document.getElementById('w-desc');
  const treatmentInput = document.getElementById('w-treat');
  const photoInput = document.getElementById('wound-photo-input');
  if (!locationInput || !typeInput || !severityInput || !descriptionInput || !treatmentInput || !photoInput) return;
  const data = {
    location: locationInput.value.trim(),
    wound_type: typeInput.value,
    severity: severityInput.value,
    description: descriptionInput.value.trim(),
    treatment: treatmentInput.value.trim(),
  };
  if (!data.location) { toast('Enter wound location', 'warning'); return; }
  try {
    const result = await apiPost(`/api/patients/${_activePatientId}/wounds`, data);
    toast('Wound logged', 'success');

    // Upload photo if one was selected
    if (photoInput.files.length > 0 && result.id) {
      await uploadWoundPhoto(_activePatientId, result.id, photoInput.files[0]);
    }

    hideWoundForm();
    [locationInput, descriptionInput, treatmentInput].forEach(input => { input.value = ''; });
    photoInput.value = '';
    await loadWounds(_activePatientId);
  } catch(e) { toast(e.message || 'Failed to log wound', 'error'); }
}

async function loadWounds(pid) {
  try {
    const wounds = await safeFetch(`/api/patients/${pid}/wounds`, {}, []);
    if (!Array.isArray(wounds)) throw new Error('invalid wounds payload');
    const el = document.getElementById('wound-list');
    if (!wounds.length) { el.innerHTML = prepEmptyBlock('No wounds logged yet. Add injuries here to keep treatment history together.'); return; }
    el.innerHTML = wounds.map(w => {
      const t = new Date(w.created_at);
      const ts = t.toLocaleDateString([], {month:'short',day:'numeric'}) + ' ' + t.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
      const sevColor = {minor:'var(--green)',moderate:'var(--orange)',severe:'var(--red)',critical:'var(--red)'}[w.severity] || 'var(--text)';
      let photoCount = 0;
      const pp = w.photo_path ? (typeof w.photo_path === 'string' ? safeJsonParse(w.photo_path, []) : w.photo_path) : [];
      photoCount = Array.isArray(pp) ? pp.length : (pp ? 1 : 0);
      const photoBadge = `<button type="button" class="btn btn-sm prep-utility-tab prep-med-photo-btn" data-prep-action="${photoCount > 0 ? 'view-wound-photos' : 'prompt-wound-photo'}" data-patient-id="${pid}" data-wound-id="${w.id}" title="${photoCount > 0 ? 'View photos' : 'Add photo'}">&#128247; ${photoCount > 0 ? photoCount : 'Add'}</button>`;
      const addPhotoBtn = photoCount > 0 ? `<button type="button" class="btn btn-sm prep-utility-tab prep-med-photo-btn" data-prep-action="prompt-wound-photo" data-patient-id="${pid}" data-wound-id="${w.id}" title="Add photo">+ Photo</button>` : '';
      return `<div class="prep-med-wound-card">
        <div class="prep-med-wound-head">
          <div>
            <div class="prep-record-main"><strong>${escapeHtml(w.location)}</strong> <span class="prep-record-meta">${escapeHtml(w.wound_type)}</span></div>
            <div class="prep-record-meta">${ts}</div>
          </div>
          <div class="prep-command-actions prep-med-wound-actions">
            <span class="prep-inline-pill" style="--prep-pill-tone:${sevColor};">${escapeHtml(w.severity)}</span>
            ${photoBadge}
            ${addPhotoBtn}
          </div>
        </div>
        ${w.description ? `<div class="prep-med-note">${escapeHtml(w.description)}</div>` : ''}
        ${w.treatment ? `<div class="prep-med-treatment">Tx: ${escapeHtml(w.treatment)}</div>` : ''}
      </div>`;
    }).join('');
  } catch(e) {}
}

async function uploadWoundPhoto(pid, wid, file) {
  if (!file) return;
  const allowed = ['.jpg','.jpeg','.png','.webp','.gif'];
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
  if (!allowed.includes(ext)) { toast(`File type ${ext} not allowed`, 'warning'); return; }
  const fd = new FormData();
  fd.append('photo', file);
  try {
    const res = await apiFetch(`/api/patients/${pid}/wounds/${wid}/photo`, { method: 'POST', body: fd });
    toast('Photo uploaded', 'success');
    return res;
  } catch(e) { toast(e.message || 'Photo upload failed', 'error'); }
}

function promptWoundPhoto(pid, wid) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.capture = 'environment';
  input.onchange = async () => {
    if (input.files.length > 0) {
      await uploadWoundPhoto(pid, wid, input.files[0]);
      if (_activePatientId) await loadWounds(_activePatientId);
    }
  };
  input.click();
}

function closeWoundPhotoModal() {
  document.getElementById('wound-photo-modal')?.remove();
}

async function viewWoundPhotos(pid, wid) {
  try {
    const data = await safeFetch(`/api/patients/${pid}/wounds/${wid}/photos`, {}, null);
    if (!Array.isArray(data?.photos) || !data.photos.length) { toast('No photos found', 'info'); return; }
    const photos = data.photos;
    const existing = document.getElementById('wound-photo-modal');
    if (existing) existing.remove();

    const photoLabel = (fname) => {
      const m = fname.match(/wound_\d+_\d+_(\d+)/);
      return m ? new Date(parseInt(m[1]) * 1000).toLocaleString() : fname;
    };

    const modal = document.createElement('div');
    modal.id = 'wound-photo-modal';
    modal.className = 'modal-overlay prep-photo-modal';
    modal.onclick = (e) => { if (e.target === modal) closeWoundPhotoModal(); };
    modal.innerHTML = `
      <div class="modal-card modal-card-lg prep-photo-card">
        <div class="modal-header prep-photo-header">
          <div>
            <h3>Wound Photos</h3>
            <div class="prep-photo-title">Visual progression (${photos.length})</div>
            <div class="prep-photo-subtitle">Compare healing over time or review the latest image in full scale.</div>
          </div>
          <div class="prep-photo-toolbar">
            <button type="button" class="btn btn-sm btn-primary" data-prep-action="add-wound-photo-close" data-patient-id="${pid}" data-wound-id="${wid}">+ Add Photo</button>
            <button type="button" class="btn btn-sm modal-close prep-photo-close" data-shell-action="close-wound-photo-modal" aria-label="Close wound photo viewer">&#10005;</button>
          </div>
        </div>
        <div class="modal-body prep-photo-body">
          ${photos.length === 1 ? `
            <div class="prep-photo-stage prep-photo-stage-single">
              <img src="/api/wound-photos/${photos[0]}" alt="Wound photo" class="prep-photo-image">
              <div class="prep-photo-caption">${photoLabel(photos[0])}</div>
            </div>
          ` : `
            <div class="prep-photo-select-row">
              <span class="prep-photo-select-label">Compare</span>
              <select id="wound-photo-left" class="prep-photo-select"></select>
              <span class="prep-photo-select-label">vs</span>
              <select id="wound-photo-right" class="prep-photo-select"></select>
            </div>
            <div id="wound-photo-compare" class="prep-photo-compare">
              <div class="prep-photo-pane">
                <img id="wound-photo-img-l" alt="Earlier wound photo" class="prep-photo-image" />
                <div id="wound-photo-ts-l" class="prep-photo-caption"></div>
              </div>
              <div class="prep-photo-divider"></div>
              <div class="prep-photo-pane">
                <img id="wound-photo-img-r" alt="Later wound photo" class="prep-photo-image" />
                <div id="wound-photo-ts-r" class="prep-photo-caption"></div>
              </div>
            </div>
          `}
        </div>
      </div>`;
    document.body.appendChild(modal);
    if (typeof NomadModal !== 'undefined') NomadModal.open(modal, {
      onClose: () => { if (modal.parentNode) modal.remove(); },
    });

    if (photos.length > 1) {
      const leftSel = document.getElementById('wound-photo-left');
      const rightSel = document.getElementById('wound-photo-right');
      photos.forEach((p, i) => {
        const opt1 = new Option(photoLabel(p), i);
        const opt2 = new Option(photoLabel(p), i);
        leftSel.add(opt1);
        rightSel.add(opt2);
      });
      leftSel.value = 0;
      rightSel.value = photos.length - 1;

      function updateCompare() {
        const li = parseInt(leftSel.value), ri = parseInt(rightSel.value);
        document.getElementById('wound-photo-img-l').src = `/api/wound-photos/${photos[li]}`;
        document.getElementById('wound-photo-img-r').src = `/api/wound-photos/${photos[ri]}`;
        document.getElementById('wound-photo-ts-l').textContent = photoLabel(photos[li]);
        document.getElementById('wound-photo-ts-r').textContent = photoLabel(photos[ri]);
      }
      leftSel.onchange = updateCompare;
      rightSel.onchange = updateCompare;
      updateCompare();
    }
  } catch(e) { toast('Failed to load photos', 'error'); }
}

/* ─── Interactive Decision Guide Engine ─── */
const DECISION_GUIDES = [
  {
    id: 'water_purify', title: 'Water Purification', icon: '&#128167;',
    desc: 'Find the right purification method based on your water source, equipment, and situation.',
    nodes: {
      start: {type:'question', text:'What is your water source?', options:[
        {label:'Tap water (municipal, well)', next:'tap'},
        {label:'Clear stream, river, or lake', next:'clear_surface'},
        {label:'Murky/muddy water', next:'murky'},
        {label:'Rainwater collection', next:'rain'},
        {label:'Saltwater / ocean', next:'salt'},
        {label:'Unknown / possibly contaminated', next:'unknown'},
      ]},
      tap: {type:'question', text:'Is the municipal supply compromised (boil advisory, disaster)?', options:[
        {label:'No — normal supply', next:'tap_ok'},
        {label:'Yes — boil advisory or disaster', next:'clear_surface'},
      ]},
      tap_ok: {type:'result', style:'success', text:'Tap water is generally safe.\n\nFor extra protection, fill containers and add 2 drops of unscented bleach per quart. Wait 30 minutes.\n\nStore in clean, food-grade containers away from chemicals.'},
      clear_surface: {type:'question', text:'What equipment do you have?', options:[
        {label:'Portable water filter (Sawyer, Katadyn, LifeStraw)', next:'has_filter'},
        {label:'Pot and heat source (can boil)', next:'boil_method'},
        {label:'Bleach (unscented household, 8.25%)', next:'bleach_method'},
        {label:'Iodine or purification tablets', next:'iodine_method'},
        {label:'UV pen (SteriPEN)', next:'uv_method'},
        {label:'Nothing — improvise', next:'improvise'},
      ]},
      murky: {type:'result', style:'warning', text:'Murky water must be PRE-FILTERED before treatment.\n\n1. Let water settle in a container for 30+ minutes\n2. Pour through a cloth (bandana, t-shirt, coffee filter) into a clean container\n3. Repeat if still cloudy\n4. THEN treat with one of these methods:\n   - Boil for 1 minute (3 min above 6500 ft)\n   - Add bleach: 4 drops per quart (double normal dose for cloudy water)\n   - Use a ceramic filter if available\n\nNever drink murky water untreated — sediment harbors parasites.'},
      rain: {type:'result', style:'info', text:'Rainwater is generally clean but may contain debris from collection surfaces.\n\n1. Use a "first flush" diverter — discard the first 10 gallons after a dry spell\n2. Filter through cloth to remove debris\n3. For drinking, add 2 drops bleach per quart as a precaution\n4. Store in covered, opaque containers to prevent algae growth\n\nRoof material matters: Metal roofs are cleanest. Avoid asphalt shingles for drinking water (chemicals).'},
      salt: {type:'result', style:'danger', text:'Saltwater CANNOT be made drinkable by filtering or chemicals. You need DISTILLATION.\n\n1. Boil saltwater in a pot\n2. Angle a clean lid or sheet over the pot to collect steam\n3. Drip condensation into a separate clean container\n4. The collected water is fresh — the salt stays behind\n\nSolar still alternative: Dig a hole, place a container in the center, cover with clear plastic, place a rock to create a drip point. Very slow but works.'},
      unknown: {type:'result', style:'danger', text:'Treat unknown water as contaminated. Use the STRONGEST method available:\n\n1. BEST: Boil for 3 minutes + let cool\n2. GOOD: Ceramic filter + bleach (double treatment)\n3. OK: Bleach alone — 4 drops per quart, wait 30 min\n4. LAST RESORT: Solar disinfection (SODIS) — clear bottle in full sun for 6+ hours\n\nNever drink untreated water from an unknown source. Waterborne illness can be fatal when medical care is unavailable.\n\nYour water supplies: {inv:water}'},
      has_filter: {type:'result', style:'success', text:'Portable filters are the best field option.\n\n1. Collect water from the cleanest part of the source (upstream, away from shore)\n2. Pre-filter through cloth if water is turbid\n3. Filter through your device per manufacturer instructions\n4. For extra safety, add 2 drops bleach per quart after filtering\n\nMaintenance: Backflush your filter regularly. Replace cartridge per manufacturer specs. A clogged filter can push contaminants through.\n\nYour water supplies: {inv:water}'},
      boil_method: {type:'result', style:'success', text:'Boiling is the MOST RELIABLE purification method.\n\n1. Bring water to a rolling boil\n2. Boil for 1 minute (3 minutes above 6,500 ft elevation)\n3. Let cool naturally — do not add ice\n4. Pour between containers to improve taste (adds oxygen)\n\nKills: bacteria, viruses, parasites, protozoa.\nDoes NOT remove: chemicals, heavy metals, sediment (pre-filter if needed).'},
      bleach_method: {type:'result', style:'info', text:'Household bleach (unscented, 8.25% sodium hypochlorite):\n\n1. Pre-filter if cloudy (cloth, coffee filter)\n2. Add bleach:\n   - Clear water: 2 drops per quart / 8 drops per gallon\n   - Cloudy water: 4 drops per quart / 16 drops per gallon\n3. Stir and wait 30 minutes\n4. Should smell faintly of chlorine — if not, add another dose and wait 15 more min\n\nShelf life: Bleach loses potency over time. Use within 1 year of manufacture.'},
      iodine_method: {type:'result', style:'info', text:'Iodine purification tablets:\n\n1. Follow package directions (typically 1-2 tablets per quart)\n2. Wait 30 minutes minimum (longer in cold water)\n3. Use vitamin C tablet after treatment to improve taste\n\nWarnings:\n- NOT safe for pregnant women\n- NOT safe for people with thyroid conditions\n- Less effective against Cryptosporidium\n- Bad taste (vitamin C helps)\n- Good backup method when filter/boiling unavailable'},
      uv_method: {type:'result', style:'success', text:'UV treatment (SteriPEN or similar):\n\n1. Water MUST be clear — pre-filter if turbid (UV cannot penetrate murky water)\n2. Insert UV pen, stir for 90 seconds\n3. Water is safe to drink immediately\n\nPros: Fast, effective against all microorganisms\nCons: Requires batteries/charging, water must be clear, no chemical removal\n\nCarry backup batteries. Pair with a pre-filter for best results.'},
      improvise: {type:'result', style:'danger', text:'No equipment — emergency methods:\n\n1. SOLAR DISINFECTION (SODIS): Fill a clear PET plastic bottle, lay in direct sun for 6 hours (48 hours if cloudy). Kills most pathogens.\n\n2. SAND FILTER: Layer (bottom to top): gravel, coarse sand, fine sand, charcoal (from fire), fine sand, cloth. Pour water through. STILL needs chemical treatment after.\n\n3. BOILING: Even a tin can over a fire works. Any container that holds water over heat.\n\n4. LAST RESORT: Dig a seep well 10+ feet from a water source. Ground naturally filters water. Still risky.\n\nDehydration kills faster than most waterborne illness. In a true emergency, any water is better than none.\n\nYour water supplies: {inv:water}'},
    }
  },
  {
    id: 'wound_assess', title: 'Wound Assessment', icon: '&#129657;',
    desc: 'Assess wound severity and get step-by-step treatment instructions.',
    nodes: {
      start: {type:'question', text:'What type of wound?', options:[
        {label:'Cut or laceration (sharp edge)', next:'cut'},
        {label:'Puncture wound (nail, knife, animal bite)', next:'puncture'},
        {label:'Burn (heat, chemical, electrical)', next:'burn'},
        {label:'Blunt force / crush injury', next:'blunt'},
        {label:'Gunshot wound', next:'gsw'},
        {label:'Abrasion / scrape', next:'abrasion'},
      ]},
      cut: {type:'question', text:'How severe is the bleeding?', options:[
        {label:'Minor — oozing, small cut', next:'cut_minor'},
        {label:'Moderate — steady flow, deep cut', next:'cut_moderate'},
        {label:'Severe — spurting or soaking through bandages', next:'cut_severe'},
      ]},
      cut_minor: {type:'result', style:'success', text:'Minor cut treatment:\n\n1. Wash hands (or glove up)\n2. Clean wound with clean water — flush out debris\n3. Apply antibiotic ointment if available\n4. Cover with adhesive bandage or sterile gauze\n5. Change dressing daily or when wet/dirty\n\nWatch for infection (next 48h): increasing redness, swelling, warmth, red streaks, pus, fever. If any appear, wound needs antibiotics.'},
      cut_moderate: {type:'result', style:'warning', text:'Moderate laceration treatment:\n\n1. Apply DIRECT PRESSURE with clean cloth/gauze — hold firmly for 10 minutes minimum\n2. Do NOT lift to check — this restarts clotting\n3. Once bleeding stops, clean wound with clean water\n4. If wound edges can be pulled together: use butterfly bandages or Steri-Strips across the cut\n5. Apply antibiotic ointment\n6. Cover with sterile gauze, secure with medical tape\n7. Elevate injured area above heart level\n8. Change dressing every 12-24 hours\n\nSeek medical care if: wound is >1 inch, on face/hands/joints, or won\'t stop bleeding in 20 min.'},
      cut_severe: {type:'result', style:'danger', text:'SEVERE BLEEDING — ACT IMMEDIATELY:\n\n1. Call 911 if available\n2. Apply DIRECT PRESSURE — hard, with both hands if needed\n3. If blood soaks through, ADD more gauze ON TOP (don\'t remove soaked layer)\n4. If on a limb and direct pressure fails: TOURNIQUET\n   - Place 2-3 inches above wound (between wound and heart)\n   - Tighten until bleeding stops\n   - Note the TIME applied\n   - Do NOT remove once applied\n5. If no tourniquet: pack wound tightly with gauze or clean cloth, maintain pressure\n6. Keep patient lying down, legs elevated\n7. Keep patient warm (shock prevention)\n\nA tourniquet that saves a life is never wrong. Limb loss from tourniquet is extremely rare.\n\nYour assigned medic: {medic_name}\nMedical supplies: {inv:medical}'},
      puncture: {type:'result', style:'warning', text:'Puncture wound treatment:\n\n1. Do NOT remove large embedded objects — stabilize in place with bulky dressing\n2. For small punctures: let wound bleed briefly (flushes bacteria)\n3. Clean around wound with clean water and soap\n4. Apply antibiotic ointment\n5. Cover with sterile dressing\n6. TETANUS RISK: If no tetanus shot in past 5 years, seek medical care within 72 hours\n\nAnimal bites: Wash aggressively with soap and water for 5+ minutes. High infection risk. Seek medical care — may need antibiotics and rabies evaluation.\n\nWatch for: redness spreading, fever, swelling — signs of serious infection requiring antibiotics.'},
      burn: {type:'question', text:'What degree burn?', options:[
        {label:'Red, painful, no blisters (1st degree / sunburn)', next:'burn_1st'},
        {label:'Blisters, very painful, red/white (2nd degree)', next:'burn_2nd'},
        {label:'White/charred, may not hurt (3rd degree)', next:'burn_3rd'},
        {label:'Chemical burn', next:'burn_chem'},
      ]},
      burn_1st: {type:'result', style:'success', text:'First degree burn (superficial):\n\n1. Cool under running water for 10-20 minutes\n2. Do NOT use ice (causes more damage)\n3. Apply aloe vera gel or burn cream\n4. Take ibuprofen for pain\n5. Cover loosely if needed\n\nHeals in 3-7 days. No scarring expected.'},
      burn_2nd: {type:'result', style:'warning', text:'Second degree burn:\n\n1. Cool under running water for 20 minutes\n2. Do NOT pop blisters (protective barrier against infection)\n3. If blisters break: clean gently, apply antibiotic ointment\n4. Cover with non-stick sterile dressing (Telfa pad)\n5. Wrap loosely with gauze\n6. Change dressing daily\n7. Take ibuprofen/acetaminophen for pain\n\nSeek medical care if: burn is larger than your palm, on face/hands/feet/genitals/joints, or shows signs of infection.\n\nHealing: 2-3 weeks. May scar. Keep clean and moist.'},
      burn_3rd: {type:'result', style:'danger', text:'Third degree burn — MEDICAL EMERGENCY:\n\n1. Call 911 if available\n2. Do NOT run cold water on large 3rd degree burns (shock risk)\n3. Cover with clean, dry, non-stick dressing\n4. Elevate burned area if possible\n5. Watch for shock: pale, rapid pulse, confusion → lay flat, elevate legs\n6. Do NOT apply ointments, butter, or home remedies\n7. Do NOT remove clothing stuck to the burn\n8. Give small sips of water if patient is conscious\n\nThis burn has destroyed nerve endings (may not hurt despite severity). Requires professional medical care — skin grafting likely needed.'},
      burn_chem: {type:'result', style:'danger', text:'Chemical burn:\n\n1. Remove contaminated clothing (use gloves if possible)\n2. FLUSH with large amounts of water for 20+ minutes\n3. For dry chemicals: brush off powder BEFORE flushing with water\n4. Do NOT neutralize (acid with base or vice versa) — water only\n5. Cover with loose, dry, sterile dressing\n6. Identify the chemical if possible (for medical team)\n\nEye exposure: Flush eyes with clean water for 15+ minutes. Hold eyelids open. Seek immediate medical care.'},
      blunt: {type:'result', style:'warning', text:'Blunt force / crush injury:\n\n1. Check for deformity (possible fracture) — if present, immobilize\n2. Apply ice/cold compress: 20 minutes on, 20 minutes off\n3. Compress with elastic bandage (not too tight)\n4. Elevate above heart level\n5. Take ibuprofen for pain and swelling\n\nRed flags requiring emergency care:\n- Inability to move the limb\n- Numbness or tingling below injury\n- Visible bone or severe deformity\n- Crush injury to torso/abdomen (internal bleeding risk)\n- Compartment syndrome signs: severe pain, tight/shiny skin, pain on passive stretch'},
      gsw: {type:'result', style:'danger', text:'Gunshot wound — LIFE THREAT:\n\n1. Scene safety FIRST — ensure no ongoing threat\n2. Call 911 if available\n3. Apply direct pressure to wound with cloth/gauze\n4. If on limb with severe bleeding: apply TOURNIQUET high and tight\n5. If torso wound: pack wound cavity with gauze, apply pressure\n6. Check for EXIT wound (treat both holes)\n7. Chest wound with sucking sound: seal 3 sides with plastic/tape (allows air out, not in)\n8. Keep patient still, warm, legs elevated\n9. Do NOT give food/water (surgery likely needed)\n\nMost survivable if bleeding is controlled quickly. Every second counts.\n\nYour assigned medic: {medic_name}\nMedical supplies: {inv:medical}'},
      abrasion: {type:'result', style:'success', text:'Abrasion / scrape:\n\n1. Clean thoroughly — this is the most important step for abrasions\n2. Use clean water and mild soap, gently scrub out all debris\n3. Embedded dirt/gravel must be removed (infection risk)\n4. Apply thin layer of antibiotic ointment\n5. Cover with non-stick bandage\n6. Change dressing daily\n\nLarge abrasions (road rash): Keep moist with ointment to minimize scarring. Do NOT let large abrasions dry out and scab — moist healing is faster and scars less.'},
    }
  },
  {
    id: 'fire_start', title: 'Fire Starting', icon: '&#128293;',
    desc: 'Choose the right fire-starting method based on conditions and available materials.',
    nodes: {
      start: {type:'question', text:'What fire-starting tools do you have?', options:[
        {label:'Lighter or matches', next:'has_lighter'},
        {label:'Ferro rod / fire steel', next:'ferro'},
        {label:'Magnifying glass / lens', next:'lens'},
        {label:'Nothing — need to improvise', next:'primitive'},
      ]},
      has_lighter: {type:'question', text:'What are the weather conditions?', options:[
        {label:'Dry conditions', next:'dry_easy'},
        {label:'Wet / raining', next:'wet_fire'},
        {label:'Windy', next:'windy_fire'},
        {label:'Snow / freezing', next:'cold_fire'},
      ]},
      dry_easy: {type:'result', style:'success', text:'Dry conditions with lighter/matches — easiest scenario.\n\n1. TINDER: Gather dry material that catches a spark — dryer lint, birch bark, dry grass, pine needles, cotton balls (with vaseline = best), char cloth\n2. KINDLING: Pencil-thin dry sticks, split wood shavings\n3. FUEL: Wrist-thick to arm-thick dry wood\n\nBuild method (teepee):\n1. Place tinder bundle in center\n2. Lean kindling sticks in a cone shape over tinder\n3. Light tinder from the upwind side\n4. Add kindling as fire grows\n5. Gradually add larger fuel wood\n\nFeed gradually. Don\'t smother with too much wood too fast.'},
      wet_fire: {type:'result', style:'warning', text:'Wet conditions — hardest but possible.\n\n1. Find DRY tinder (look INSIDE dead standing trees, under bark, inside coat pockets for lint)\n2. Feather sticks: Shave thin curls on a stick without detaching — these catch fire even when damp\n3. Birch bark burns even when wet (natural oils)\n4. Split wet wood to get dry inner wood — the inside is always drier\n5. Build a platform of sticks to keep fire off wet ground\n6. Start small — build up slowly\n7. Create a windbreak/rain shelter over your fire spot\n\nPine resin/sap is a natural fire accelerant — collect from wounds on pine trees.'},
      windy_fire: {type:'result', style:'info', text:'Windy conditions:\n\n1. Find or create a windbreak (rocks, log, dirt bank, your body)\n2. Dig a small pit if possible — below-ground fire is wind-resistant\n3. Light tinder on the downwind side (wind blows flame INTO the fire)\n4. Use a "log cabin" structure instead of teepee — more stable in wind\n5. Shield your lighter/match with cupped hands\n\nDakota fire hole (best for wind):\n1. Dig a main hole 1 ft deep, 1 ft wide\n2. Dig a tunnel from upwind side into the bottom of the hole\n3. Build fire in the hole — tunnel provides air, hole blocks wind\n4. Very efficient, low smoke, wind-resistant.'},
      cold_fire: {type:'result', style:'warning', text:'Snow/freezing conditions:\n\n1. Create a platform of green logs or rocks — fire on snow melts through and dies\n2. Standing dead wood is drier than fallen wood (off the wet ground)\n3. Use a candle stub or fuel tablet to extend your flame time while kindling catches\n4. Break branches — if they snap, they\'re dry enough. If they bend, too wet.\n5. Build a reflector wall behind the fire (stacked logs) to direct heat toward you\n6. Position yourself between fire and reflector for maximum warmth\n\nPrioritize: shelter from wind first, then fire. A good shelter retains more heat than an exposed fire.'},
      ferro: {type:'result', style:'info', text:'Ferro rod / fire steel:\n\n1. Prepare tinder FIRST — you need very fine, dry material\n   - Best: char cloth, cotton ball + vaseline, birch bark, dry grass bundle\n   - Good: fine wood shavings, dryer lint, jute twine (pulled apart)\n2. Hold ferro rod close to tinder (1-2 inches)\n3. Strike AWAY from tinder with the scraper (rod stays still, scraper moves)\n4. Aim sparks into the tinder bundle\n5. Once tinder glows, gently blow to flame\n6. Transfer burning tinder to your prepared fire lay\n\nPractice at home before you need it in the field. Ferro rods work when wet — wipe dry and strike.'},
      lens: {type:'result', style:'info', text:'Magnifying glass / lens method:\n\n1. ONLY works with direct sunlight (no clouds)\n2. Need very fine, dark-colored tinder (char cloth is ideal)\n3. Focus the light to the smallest possible point on the tinder\n4. Hold steady — do not move the focal point\n5. Takes 30-60 seconds for tinder to begin smoking\n6. Once smoking, gently blow to create flame\n7. Transfer to prepared fire lay\n\nLens sources: reading glasses, binocular lens, camera lens, bottom of a polished soda can, clear ice shaped into a lens, water-filled clear plastic bag shaped into a sphere.'},
      primitive: {type:'result', style:'danger', text:'No tools — primitive methods (extremely difficult, practice first):\n\nBOW DRILL (most reliable primitive method):\n1. Fireboard: flat piece of dry softwood (cedar, willow, cottonwood)\n2. Spindle: straight, dry, round stick (same wood)\n3. Bearing block: hardwood or stone with socket (lubricate with lip balm)\n4. Bow: curved branch with cordage (shoelace, paracord, strip of clothing)\n5. Notch: cut V-notch in fireboard, place tinder bundle under it\n6. Wrap cordage around spindle, press into fireboard with bearing block\n7. Saw bow back and forth — spindle spins and creates friction\n8. Dark powder falls into notch → ember forms\n9. Transfer ember to tinder bundle, blow gently to flame\n\nThis is the hardest skill in survival. Practice when your life doesn\'t depend on it.'},
    }
  },
  {
    id: 'shelter_build', title: 'Shelter Construction', icon: '&#127968;',
    desc: 'Build emergency shelter based on your environment, materials, and timeframe.',
    nodes: {
      start: {type:'question', text:'What environment are you in?', options:[
        {label:'Forest / wooded area', next:'forest'},
        {label:'Open field / grassland', next:'open'},
        {label:'Snow / winter conditions', next:'snow'},
        {label:'Desert / arid', next:'desert'},
        {label:'Urban / suburban (disaster)', next:'urban'},
      ]},
      forest: {type:'question', text:'How much time do you have?', options:[
        {label:'Under 1 hour (emergency)', next:'debris_hut'},
        {label:'A few hours', next:'lean_to'},
        {label:'Longer term (days+)', next:'a_frame'},
      ]},
      debris_hut: {type:'result', style:'warning', text:'DEBRIS HUT — fastest forest shelter (30-60 min):\n\n1. Find a ridgepole: straight branch, body length + 2 feet\n2. Prop one end on a stump/rock at sitting height, other end on ground\n3. Lean sticks along both sides (ribbing) — close together\n4. Pile leaves, pine needles, grass thickly over the ribbing (2-3 feet deep)\n5. Stuff the inside with dry leaves for insulation (your body heats the trapped air)\n6. Block the entrance with a backpack or pile of debris\n\nKey: make it SMALL — just big enough to fit you. Smaller = warmer. Body heat is your furnace.\n\nInsulation on the ground is MORE important than overhead. Cold ground steals heat 25x faster than cold air.'},
      lean_to: {type:'result', style:'info', text:'LEAN-TO — good forest shelter (2-3 hours):\n\n1. Find or lash a horizontal ridge pole between two trees (chest height)\n2. Lean long branches at 45-60 degrees against the ridge pole\n3. Weave smaller branches horizontally between the leaning poles\n4. Layer debris (leaves, bark, pine boughs) thickly from bottom up — like shingles\n5. Build a reflector fire 4-6 feet in front of the opening\n\nAdvantages: open front for fire warmth, easy to build, room for gear\nDisadvantages: open to wind from one side — position opening away from prevailing wind\n\nImprovement: build a log reflector wall behind the fire to bounce heat back toward you.'},
      a_frame: {type:'result', style:'success', text:'A-FRAME — best long-term forest shelter:\n\n1. Ridge pole: strong branch, 9-12 feet long\n2. Prop between two trees or on forked sticks at both ends\n3. Lean branches on both sides creating an A shape\n4. Weave horizontal branches for structure\n5. Layer debris thickly (leaves, bark, pine boughs) — minimum 1 foot thick for rain protection\n6. Create a raised bed inside with logs and pine boughs\n\nFor rain protection: add a layer of bark shingles or plastic sheeting if available.\n\nLong-term improvements: add a door flap, dig a drainage trench around the perimeter, build a stone-ring fire pit nearby, create a drying rack for wet clothes.'},
      open: {type:'result', style:'warning', text:'Open field — limited materials:\n\n1. FIRST: look for ANY natural windbreak (rock outcrop, hill, tree line)\n2. Dig a body-length trench, 2 feet deep if soil allows\n3. Cover with branches, grass, tarp, or whatever is available\n4. Pile excavated dirt on the windward side as a wall\n\nIf you have a tarp/poncho:\n- Stake one edge to ground with rocks\n- Angle the other side up with sticks or trekking poles\n- Ensure opening faces away from wind\n\nGrass/reed shelter: bundle tall grass into thick mats, lean against a ridge pole. Grass is an excellent insulator when packed thick.'},
      snow: {type:'result', style:'danger', text:'SNOW SHELTER — life-saving in winter:\n\nQUINZHEE (easiest, 2-3 hours):\n1. Pile snow into a mound 6+ feet tall, 8 feet wide\n2. Wait 1-2 hours for snow to sinter (bond together)\n3. Hollow out the inside — walls should be 1-1.5 feet thick\n4. Poke a ventilation hole in the top (CRITICAL — CO2 buildup kills)\n5. Sleeping platform should be higher than entrance (warm air rises)\n6. Block entrance partially with a backpack\n\nSNOW TRENCH (fastest, 30 min):\n1. Dig a trench body-width, body-length, 3 feet deep\n2. Cover with branches/tarp and snow\n3. Insulate floor with pine boughs\n\nNEVER seal a snow shelter completely — always maintain ventilation.'},
      desert: {type:'result', style:'warning', text:'Desert shelter — shade is survival:\n\n1. Priority is SHADE, not insulation\n2. If you have a tarp/blanket: create a double-layer shade\n   - First layer 1 foot above ground (air gap underneath)\n   - Second layer 1 foot above first (air gap between layers = cooler)\n3. Dig a shallow trench and cover with fabric for a cooler microclimate\n4. Desert temps can swing 40+ degrees at night — build insulation for nighttime cold too\n\nNatural shelters: rock overhangs, dry washes (NOT during rain — flash flood risk), north-facing cliff faces (shadier in Northern Hemisphere)\n\nTravel and work during dawn/dusk. Rest in shade during peak heat (10am-4pm).'},
      urban: {type:'result', style:'info', text:'Urban/suburban disaster shelter:\n\n1. FIRST: assess building safety — look for cracks, lean, gas smell, structural damage\n2. Interior rooms on lowest floors are safest (away from exterior walls and windows)\n3. Avoid rooms with large unsupported ceilings\n4. Use mattresses, couch cushions for insulation and ground padding\n5. Seal windows with plastic sheeting and tape (cold/contamination)\n6. Vehicles make decent short-term shelters (run engine 10 min/hour for heat — crack window to prevent CO poisoning)\n\nAbandoned buildings: check for other occupants first, avoid structures with fire/water damage, test floors before trusting them.\n\nBest urban resources: hardware stores, home improvement centers (tarps, insulation, tools).'},
    }
  },
  {
    id: 'radio_setup', title: 'Radio Communications', icon: '&#128225;',
    desc: 'Set up emergency radio communications based on your equipment and range needs.',
    nodes: {
      start: {type:'question', text:'What radio equipment do you have?', options:[
        {label:'No radio — need to buy one', next:'buy'},
        {label:'FRS walkie-talkies (Motorola, Midland, etc.)', next:'frs'},
        {label:'GMRS radio (need license)', next:'gmrs'},
        {label:'HAM / amateur radio (need license)', next:'ham'},
        {label:'CB radio', next:'cb'},
        {label:'Meshtastic / LoRa device', next:'mesh'},
      ]},
      buy: {type:'result', style:'info', text:'Recommended first radio purchases:\n\n1. IMMEDIATE (no license): Midland X-Talker T77VP5 FRS ($60/pair) — 2-mile range, weather alerts, rechargeable\n\n2. BETTER (easy license, $35, no exam): Midland MXT275 GMRS mobile ($200) + Midland GXT1000VP4 handhelds ($70/pair) — 5-25 mile range, repeater capable\n\n3. BEST (exam required): Baofeng UV-5R HAM handheld ($25) for Technician license + Icom IC-7300 HF ($1100) for General license — local to worldwide range\n\n4. OFF-GRID: Heltec LoRa 32 V3 ($20) with Meshtastic firmware — mesh networking, no license, 1-10+ mile range\n\nStart with FRS (zero barrier) then get GMRS license ($35, covers whole family, no exam).'},
      frs: {type:'result', style:'info', text:'FRS Radio Setup:\n\n1. Channel 1 is the common prepper rally channel\n2. Channel 3 is the unofficial emergency channel\n3. Agree on a PRIMARY and BACKUP channel with your group\n4. Set CTCSS/privacy codes to reduce crosstalk (not encryption — anyone can hear you)\n5. Use channel 1 for initial contact, then move to a pre-agreed channel\n\nRange: 0.5-2 miles typical (terrain dependent)\nPower: 2W maximum (channels 1-7, 15-22), 0.5W (channels 8-14)\nNo license required\n\nTips:\n- Higher ground = better range\n- Hold radio vertically (antenna straight up)\n- Speak across the mic, not into it\n- Use NATO phonetic alphabet for clarity'},
      gmrs: {type:'result', style:'success', text:'GMRS Radio Setup:\n\n1. Get your license: $35 at fcc.gov, no exam, covers your whole family, valid 10 years\n2. Channel 20 (462.675 MHz) is the national GMRS emergency calling frequency\n3. GMRS allows repeater use — greatly extends range (10-50+ miles through repeaters)\n4. Find local repeaters: mygmrs.com/repeaters\n\nSetup for your group:\n1. Program a primary simplex channel (direct radio-to-radio)\n2. Program a backup simplex channel\n3. Program your nearest GMRS repeater (input/output freqs + tone)\n4. Schedule check-in times (e.g., top of every hour)\n\nRange: 2-5 miles handheld simplex, 10-50+ miles through repeaters\nPower: up to 50W mobile\n\nBest GMRS radios: Midland MXT275/MXT500 (mobile), Wouxun KG-805G (handheld)'},
      ham: {type:'question', text:'What HAM license level?', options:[
        {label:'Technician (VHF/UHF local)', next:'ham_tech'},
        {label:'General (HF worldwide)', next:'ham_gen'},
        {label:'No license yet', next:'ham_study'},
      ]},
      ham_tech: {type:'result', style:'success', text:'HAM Technician — Local Communications:\n\nKey frequencies:\n- 146.520 MHz FM — National simplex calling frequency (start here)\n- 146.550 MHz FM — Simplex emergency\n- 446.000 MHz FM — UHF calling frequency\n\nSetup:\n1. Program your local repeaters (repeaterbook.com)\n2. Program simplex calling frequencies\n3. Join your local ARES/RACES emergency communications group\n4. Practice weekly nets\n\nEquipment: Baofeng UV-5R ($25) for start, Yaesu FT-65R ($90) for better quality, Kenwood TM-V71A ($350) for mobile\n\nRange: 5-15 miles simplex, 30-100+ miles through repeaters\n\nIn an emergency, any person may use any frequency to call for help — license rules are suspended for life-threatening situations.'},
      ham_gen: {type:'result', style:'success', text:'HAM General — Regional & Worldwide:\n\nKey HF frequencies:\n- 7.260 MHz (40m) — Regional, day+night, 100-1000 miles\n- 14.300 MHz (20m) — Worldwide daytime, emergency net\n- 3.860 MHz (80m) — Regional nighttime, ARES nets\n\nSetup:\n1. HF radio (Icom IC-7300 recommended — $1100)\n2. Antenna: end-fed half-wave (EFHW) is easiest to deploy in the field\n3. Power: 12V battery + solar panel for off-grid operation\n4. Tuner: built into most modern HF rigs\n\nEmergency nets to know:\n- 14.300 MHz — Intercon Net (worldwide emergency)\n- 7.290 MHz — SATERN (Salvation Army)\n- 3.860 MHz — Regional ARES nets (check your state)\n\nHF can reach anywhere on Earth with the right conditions. Practice NVIS (Near Vertical Incidence Skywave) for reliable 0-300 mile coverage.'},
      ham_study: {type:'result', style:'info', text:'Getting your HAM license:\n\n1. TECHNICIAN (easiest, 2-3 weeks study):\n   - Study at hamstudy.org (free)\n   - 35 multiple choice questions, need 26 correct\n   - Find an exam session: arrl.org/find-an-amateur-radio-license-exam-session\n   - Cost: ~$15 exam fee\n   - Gives access to VHF/UHF (local comms, repeaters)\n\n2. GENERAL (4-6 weeks additional study):\n   - Can take same day as Technician\n   - 35 more questions\n   - Gives access to HF bands (regional + worldwide)\n\nMost people pass Technician with 1-2 weeks of casual study using hamstudy.org. The questions are public — you\'re studying the actual test pool.\n\nIn a true emergency, license is not required to transmit a distress call.'},
      cb: {type:'result', style:'info', text:'CB Radio Setup:\n\nKey channels:\n- Channel 9 — Official emergency channel\n- Channel 19 — Trucker/highway channel (most monitored)\n\nSetup:\n1. Mount antenna as high as possible (magnetic mount on vehicle roof)\n2. Set to channel 9 or 19 for monitoring\n3. No license required\n4. Squelch: turn up until static just disappears\n\nRange: 2-5 miles typical, up to 15-20 with good antenna\nPower: 4W AM, 12W SSB\n\nLimitations: Short range, crowded in some areas, no repeater access\nAdvantage: No license, ubiquitous, truckers monitor ch19 24/7\n\nBest for: vehicle convoys, short-range base-to-vehicle, highway travel monitoring'},
mesh: {type:'result', style:'success', text:'Meshtastic / LoRa Mesh Setup:\n\n1. Hardware: Heltec LoRa 32 V3 (~$20) or LILYGO T-Beam ($35)\n2. Flash Meshtastic firmware: flasher.meshtastic.org (one click)\n3. Configure via Meshtastic app (Android/iOS) or web interface\n4. No license required (ISM band)\n\nRange: 1-10+ miles depending on antenna and terrain\nPower: runs on small battery for days\n\nKey advantages:\n- Mesh networking: messages hop through other nodes automatically\n- Works without any internet or cell infrastructure\n- GPS position sharing between nodes\n- Encrypted by default\n- Solar + battery = indefinite operation\n\nSetup for your group:\n1. Flash all devices with same firmware version\n2. Set same region and channel\n3. Share encryption key\n4. Place one node at highest elevation for relay\n\nNOMAD has built-in Meshtastic support in the Tools tab.'},
    }
  },
  {
    id: 'food_preserve', title: 'Food Preservation', icon: '&#127858;',
    desc: 'Choose the right preservation method based on what food you have and your available equipment.',
    nodes: {
      start: {type:'question', text:'What type of food do you need to preserve?', options:[
        {label:'Meat / fish / poultry', next:'meat'},
        {label:'Vegetables', next:'veg'},
        {label:'Fruit', next:'fruit'},
        {label:'Dairy / eggs', next:'dairy'},
        {label:'Herbs', next:'herbs'},
      ]},
      meat: {type:'question', text:'What equipment/method do you prefer?', options:[
        {label:'Salt curing / jerky (no electricity needed)', next:'meat_salt'},
        {label:'Smoking', next:'meat_smoke'},
        {label:'Canning (pressure canner required)', next:'meat_can'},
        {label:'Freezing', next:'meat_freeze'},
      ]},
      meat_salt: {type:'result', style:'info', text:'Salt curing / jerky:\n\nJERKY (cooked, shelf-stable):\n1. Slice meat thin (1/4 inch) against the grain\n2. Marinate in salt + spices 4-24 hours\n3. Dehydrate at 160F for 4-6 hours (oven on lowest setting with door cracked, or dehydrator)\n4. Done when it bends and cracks but doesn\'t snap\n5. Store in airtight container — lasts 1-2 months at room temp\n\nSALT CURE (traditional, no electricity):\n1. Cover meat completely in salt (1 lb salt per 5 lbs meat)\n2. Store in cool place (under 40F ideal)\n3. After 7 days per inch of thickness, rinse salt\n4. Hang in cool, dry, ventilated area to dry further\n5. Properly salt-cured meat lasts months without refrigeration'},
      meat_smoke: {type:'result', style:'info', text:'Smoking meat:\n\nHOT SMOKING (cooked, eat within 1-2 weeks):\n1. Cure meat with salt first (24-48 hours)\n2. Smoke at 225-275F for 2-8 hours depending on thickness\n3. Internal temp must reach 145F (whole cuts) or 165F (ground)\n4. Refrigerate — lasts 1-2 weeks\n\nCOLD SMOKING (preserved, longer storage):\n1. Salt cure meat thoroughly first (7+ days)\n2. Smoke at 68-86F for 12-48 hours (smoke only, no cooking)\n3. This is a preservation method, NOT cooking\n4. Hang in cool, dry place — lasts months\n\nWood: Use hardwoods (hickory, oak, apple, cherry, mesquite). NEVER softwood (pine, cedar) — toxic resin.\n\nImprovised smoker: metal trash can with holes, clay pot, or even a hole in the ground with a fire tunnel.'},
      meat_can: {type:'result', style:'warning', text:'Pressure canning meat (safest long-term method):\n\nREQUIRED: Pressure canner (NOT a water bath canner — meat is low-acid)\n\n1. Cut meat into chunks, brown in pan (optional but improves flavor)\n2. Pack hot meat into sterilized jars, leave 1-inch headspace\n3. Add 1 tsp salt per quart (optional)\n4. Add hot broth or water to cover meat, maintain 1-inch headspace\n5. Remove air bubbles, wipe rims, apply lids\n6. Process in pressure canner:\n   - Pints: 75 minutes at 10 PSI\n   - Quarts: 90 minutes at 10 PSI\n   - Adjust PSI for altitude (15 PSI above 1000 ft)\n7. Let canner depressurize naturally\n\nProperly canned meat lasts 2-5+ years. NEVER water-bath can meat — botulism risk.'},
      meat_freeze: {type:'result', style:'success', text:'Freezing meat:\n\n1. Wrap tightly in plastic wrap, then aluminum foil, then freezer bag\n2. Remove as much air as possible (vacuum seal is best)\n3. Label with date and contents\n4. Freeze at 0F or below\n\nStorage times at 0F:\n- Ground meat: 3-4 months\n- Steaks/roasts: 6-12 months\n- Poultry: 9-12 months\n- Fish: 3-6 months\n\nThawing: refrigerator (safest), cold water bath (faster), microwave (fastest)\nNEVER thaw on counter — bacterial growth in the danger zone (40-140F)\n\nPower outage: a full freezer stays frozen 48 hours if kept closed. Half-full: 24 hours. Blankets on top help.'},
      veg: {type:'question', text:'What method?', options:[
        {label:'Canning (water bath or pressure)', next:'veg_can'},
        {label:'Dehydrating', next:'veg_dry'},
        {label:'Fermenting (sauerkraut, kimchi)', next:'veg_ferment'},
        {label:'Root cellar / cold storage', next:'veg_cellar'},
      ]},
      veg_can: {type:'result', style:'warning', text:'Canning vegetables:\n\nLOW-ACID vegetables (most veggies) REQUIRE pressure canning:\n- Green beans, corn, peas, carrots, potatoes, etc.\n- Process per USDA guidelines (times vary by vegetable)\n\nHIGH-ACID vegetables can use water bath canning:\n- Tomatoes (add 1 tbsp lemon juice per pint to ensure acidity)\n- Pickled vegetables (vinegar provides the acid)\n- Salsa (tested recipes only)\n\nBasic steps:\n1. Sterilize jars and lids\n2. Pack prepared vegetables into hot jars\n3. Add liquid (water, brine, or syrup)\n4. Remove bubbles, wipe rims, seal\n5. Process for required time at correct pressure\n\nALWAYS use tested recipes from USDA, Ball, or your state extension service. Improvised canning recipes risk botulism.'},
      veg_dry: {type:'result', style:'success', text:'Dehydrating vegetables:\n\n1. Wash, peel, slice uniformly thin (1/4 inch)\n2. Blanch most vegetables first (1-3 min in boiling water, then ice bath)\n   - Skip blanching for: onions, peppers, mushrooms, herbs\n3. Arrange on dehydrator trays (no overlap)\n4. Dry at 125-135F until brittle:\n   - Beans: 8-14 hours\n   - Carrots: 6-12 hours\n   - Tomatoes: 8-14 hours\n   - Peppers: 8-12 hours\n5. Condition: place in sealed jar for 1 week, shake daily. Any moisture = dry longer.\n6. Store in airtight containers with oxygen absorbers\n\nShelf life: 6-12 months (2+ years with oxygen absorbers in Mylar bags)\n\nNo-electricity method: sun drying works in hot, dry climates. Use screens elevated off ground with cheesecloth cover.'},
      veg_ferment: {type:'result', style:'success', text:'Fermenting vegetables (no equipment needed):\n\nBASIC SAUERKRAUT:\n1. Shred cabbage finely\n2. Add 2% salt by weight (1 tbsp per pound of cabbage)\n3. Massage/squeeze until liquid is released (10 min)\n4. Pack tightly into clean jar, submerge under liquid\n5. Weight down (small jar filled with water on top works)\n6. Cover loosely (gas must escape)\n7. Ferment at room temp 1-4 weeks\n8. Taste weekly — move to fridge when you like the sourness\n\nFermentation works with almost any vegetable: carrots, radishes, green beans, peppers, beets.\n\nThe 2% salt rule works for everything. Measure by weight, not volume.\n\nProperly fermented food lasts months refrigerated and is more nutritious than fresh (probiotics, increased vitamins).'},
      veg_cellar: {type:'result', style:'info', text:'Root cellar / cold storage (no electricity):\n\nIdeal conditions: 32-40F, 85-95% humidity, dark, ventilated\n\nStorage life at optimal conditions:\n- Potatoes: 4-6 months (cure 2 weeks first, no light)\n- Carrots: 4-6 months (in damp sand)\n- Onions: 3-6 months (cure 2 weeks, need DRY storage)\n- Apples: 2-4 months (store separately — ethylene gas spoils other produce)\n- Winter squash: 3-6 months (cure 2 weeks at 80F first)\n- Cabbage: 3-4 months (wrap in newspaper)\n- Beets: 3-5 months (in damp sand, cut tops to 1 inch)\n- Garlic: 6-8 months (braid and hang)\n\nImprovised root cellar: buried garbage can with lid, straw insulation. North-facing basement corner. Buried cooler.'},
      fruit: {type:'result', style:'info', text:'Fruit preservation methods:\n\n1. CANNING (water bath — fruit is high-acid):\n   - Pack in light syrup, juice, or water\n   - Process 15-25 minutes depending on fruit and jar size\n   - Lasts 1-2+ years\n\n2. DEHYDRATING: Slice thin, dry at 135F until leathery\n   - Fruit leather: puree, spread thin on tray, dry 6-12 hours\n   - Lasts 6-12 months\n\n3. JAM/JELLY: Cook with sugar + pectin, water-bath can\n   - Lasts 1-2 years\n\n4. FREEZING: Spread on tray first (IQF), then bag\n   - Lasts 8-12 months\n\n5. FERMENTATION: Fruit wines, vinegars, kvass\n\nBest no-electricity: drying and jam. Sun-dried fruit has been preserved for thousands of years.'},
      dairy: {type:'result', style:'warning', text:'Dairy & egg preservation:\n\nEGGS:\n- Water glass method: dissolve 1 oz sodium silicate in 1 quart water. Submerge clean, unwashed eggs. Lasts 12-18 months unrefrigerated.\n- Mineral oil: coat each egg — seals pores. Lasts 6-9 months refrigerated.\n- Freeze: crack into muffin tin, freeze, bag. Lasts 12 months.\n- Dehydrate: scramble, dry, powder. Lasts 6-12 months.\n\nBUTTER:\n- Clarified/ghee: heat butter, skim foam, pour clear fat. Lasts months at room temp.\n- Canning: melt butter, pour into hot jars, water-bath 60 min. Controversial but traditional.\n\nCHEESE:\n- Hard cheese: wax-sealed whole wheels last months in cool storage.\n- Soft cheese: freeze (texture changes but fine for cooking).\n\nMILK:\n- Powdered milk stores 20+ years in sealed Mylar with O2 absorbers.'},
      herbs: {type:'result', style:'success', text:'Herb preservation:\n\n1. AIR DRYING (easiest):\n   - Bundle 5-6 stems, hang upside down in warm, dry, dark area\n   - 1-2 weeks until crispy\n   - Strip leaves, store in airtight jars\n   - Lasts 1-3 years\n\n2. DEHYDRATOR: 95-105F for 2-4 hours. Fastest method.\n\n3. FREEZING:\n   - Chop herbs, pack into ice cube trays with water or olive oil\n   - Pop out frozen cubes, bag them\n   - Drop directly into cooking\n\n4. HERB-INFUSED OIL:\n   - Pack jar with dried herbs (MUST be dried — fresh in oil risks botulism)\n   - Cover with oil, seal, store in cool dark place\n   - Ready in 2-4 weeks\n\n5. SALT PRESERVATION:\n   - Layer fresh herbs with coarse salt in jar\n   - 1:4 ratio herb to salt\n   - Lasts indefinitely'},
    }
  },
  {
    id: 'triage_start', title: 'START Triage', icon: '&#9878;',
    desc: 'Interactive mass casualty triage — rapidly categorize patients using the START system.',
    nodes: {
      start: {type:'question', text:'Can the patient WALK?', options:[
        {label:'Yes — they can walk', next:'green'},
        {label:'No — they cannot walk', next:'breathing'},
      ]},
      green: {type:'result', style:'success', text:'GREEN — MINOR\n\nDirect this patient to the collection point for walking wounded.\n\nThey will be treated LAST. Reassess periodically — conditions can change.\n\nTag: GREEN'},
      breathing: {type:'question', text:'Is the patient BREATHING?', options:[
        {label:'Yes — they are breathing', next:'resp_rate'},
        {label:'No — not breathing', next:'reposition'},
      ]},
      reposition: {type:'question', text:'Reposition the airway (head-tilt, chin-lift). Are they breathing NOW?', options:[
        {label:'Yes — started breathing after repositioning', next:'red_airway'},
        {label:'No — still not breathing', next:'black'},
      ]},
      black: {type:'result', style:'danger', text:'BLACK — DEAD / EXPECTANT\n\nThis patient is not breathing even after airway repositioning.\n\nTag BLACK and move to the next patient. In a mass casualty event, resources must go to salvageable patients.\n\nTag: BLACK\n\nThis is the hardest decision in triage. You are saving others by moving on.'},
      red_airway: {type:'result', style:'danger', text:'RED — IMMEDIATE\n\nPatient is breathing only with airway intervention. They need immediate care.\n\n1. Maintain airway position (recovery position if possible)\n2. Tag RED\n3. Move to next patient\n\nTag: RED — Treat first'},
      resp_rate: {type:'question', text:'Count their respiratory rate. Is it above 30 breaths per minute?', options:[
        {label:'Yes — breathing fast (>30/min)', next:'red_resp'},
        {label:'No — breathing rate is normal (<30/min)', next:'perfusion'},
      ]},
      red_resp: {type:'result', style:'danger', text:'RED — IMMEDIATE\n\nRespiratory rate over 30/minute indicates respiratory distress or shock.\n\nTag RED — this patient needs immediate treatment.\n\nTag: RED — Treat first'},
      perfusion: {type:'question', text:'Check PERFUSION: Feel for a radial pulse (wrist) OR press fingernail and release — does color return in under 2 seconds?', options:[
        {label:'No radial pulse OR cap refill > 2 seconds', next:'red_perf'},
        {label:'Radial pulse present AND cap refill < 2 seconds', next:'mental'},
      ]},
      red_perf: {type:'result', style:'danger', text:'RED — IMMEDIATE\n\nNo radial pulse or slow capillary refill indicates poor perfusion (shock/major bleeding).\n\n1. Control any visible bleeding (direct pressure, tourniquet if limb)\n2. Tag RED\n3. Move to next patient\n\nTag: RED — Treat first'},
      mental: {type:'question', text:'Check MENTAL STATUS: Can the patient follow simple commands? ("Squeeze my hand", "Open your eyes")', options:[
        {label:'No — cannot follow commands', next:'red_mental'},
        {label:'Yes — follows commands', next:'yellow'},
      ]},
      red_mental: {type:'result', style:'danger', text:'RED — IMMEDIATE\n\nAltered mental status with normal breathing and perfusion indicates head injury or other serious condition.\n\nTag RED — this patient needs immediate treatment.\n\nTag: RED — Treat first'},
      yellow: {type:'result', style:'warning', text:'YELLOW — DELAYED\n\nThis patient:\n- Cannot walk\n- Is breathing normally (<30/min)\n- Has adequate perfusion (radial pulse present, good cap refill)\n- Can follow simple commands\n\nThey have serious injuries but can wait for treatment while IMMEDIATE (RED) patients are treated first.\n\nTag: YELLOW — Treat second\n\nReassess periodically — conditions can deteriorate.'},
    }
  },
  {
    id: 'power_outage', title: 'Power Outage Response', icon: '&#9889;',
    desc: 'Step-by-step response when the power goes out — from the first minute to long-term grid-down.',
    nodes: {
      start: {type:'question', text:'How long has the power been out?', options:[
        {label:'Just happened (minutes ago)', next:'immediate'},
        {label:'A few hours', next:'hours'},
        {label:'12+ hours / overnight', next:'extended'},
        {label:'Days — grid may be down long-term', next:'longterm'},
      ]},
      immediate: {type:'question', text:'Do you know the cause?', options:[
        {label:'Storm / weather event', next:'storm'},
        {label:'Transformer blew / local outage', next:'local'},
        {label:'Widespread / unknown cause', next:'unknown'},
        {label:'I tripped my breaker / internal issue', next:'breaker'},
      ]},
      breaker: {type:'result', style:'success', text:'Internal electrical issue:\n\n1. Check your main breaker panel — look for a tripped breaker (halfway position)\n2. Turn the tripped breaker fully OFF, then back ON\n3. If it trips again immediately: you have a short circuit. Unplug everything on that circuit.\n4. Plug devices back in one at a time to find the culprit\n5. If the main breaker is tripped: call an electrician — could be a serious issue\n\nIf your WHOLE panel is dead and breakers are fine, call your power company — the issue is at the meter or transformer.'},
      storm: {type:'result', style:'warning', text:'Storm-related outage:\n\n1. STAY INSIDE during active storm\n2. Unplug sensitive electronics (TV, computer, modem) to protect from surge when power returns\n3. Leave one light ON so you know when power returns\n4. Move perishable food to coolers with ice if available\n5. Check on neighbors, especially elderly\n6. If you have a generator: run it OUTSIDE only (CO kills), use heavy-duty extension cords\n7. Report outage to your power company via phone (not app — cell towers may be down too)\n\nExpect 4-24 hours for storm restoration. Keep flashlights and battery radio handy.'},
      local: {type:'result', style:'info', text:'Local outage (transformer/line down):\n\n1. Check if neighbors also lost power — confirms it is not just you\n2. Report to power company\n3. Stay away from downed power lines (assume ALL are live)\n4. If you see sparking or fire near a transformer: call 911\n5. Expected restoration: 2-8 hours for transformer replacement\n\nWhile waiting:\n- Use flashlights (not candles — fire risk)\n- Keep fridge/freezer CLOSED (stays cold 4h fridge, 24-48h freezer if full)\n- Charge phones from car if needed (engine running, in open air)'},
      unknown: {type:'question', text:'Is your cell phone working?', options:[
        {label:'Yes — I have cell service', next:'cells_up'},
        {label:'No — cell service is also down', next:'cells_down'},
      ]},
      cells_up: {type:'result', style:'warning', text:'Widespread outage, cells working:\n\n1. Check power company website/app for outage map and estimates\n2. Monitor local news/social media for cause\n3. This is likely a grid equipment failure — usually restored in 4-12 hours\n\nActions:\n- Unplug sensitive electronics\n- Fill bathtubs and large containers with water (water pressure may drop if pumping stations lose power)\n- Consolidate perishable food; eat most perishable items first\n- Check on neighbors\n- Get cash — ATMs and card readers won\'t work without power\n- Fill vehicle gas tanks (pumps need electricity)'},
      cells_down: {type:'result', style:'danger', text:'Power AND cell service down — potential major event:\n\nThis could be: major infrastructure failure, EMP, cyber attack, or catastrophic weather.\n\n1. Switch to battery-powered AM/FM radio for information\n2. If you have HAM/GMRS radio: monitor emergency frequencies\n3. Fill ALL water containers immediately (municipal water may fail soon)\n4. Secure your home — lock doors, close curtains\n5. Account for all household members\n6. DO NOT drive unless necessary (traffic lights out, chaos likely)\n7. Start your emergency plan:\n   - Review your go-bag readiness\n   - Check fuel levels in vehicles\n   - Inventory food and water supply\n   - Establish communication plan with family\n\nIf power is not restored within 24 hours, shift to grid-down protocols.'},
      hours: {type:'question', text:'What is your biggest concern right now?', options:[
        {label:'Food spoiling in fridge/freezer', next:'food_concern'},
        {label:'Heating or cooling (extreme temperature)', next:'temp_concern'},
        {label:'Medical devices that need power', next:'medical_power'},
        {label:'General preparedness / what to do next', next:'hours_general'},
      ]},
      food_concern: {type:'result', style:'info', text:'Protecting food during outage:\n\n1. KEEP DOORS CLOSED — every opening costs 30 minutes of cold\n2. Refrigerator: safe for 4 hours if unopened\n3. Freezer: safe for 24 hours (half-full) to 48 hours (completely full)\n4. After 4 hours fridge: move critical items to cooler with ice\n5. Eat perishable items in this order:\n   - Leftovers and open deli items (first)\n   - Dairy, eggs, meat (within 4-6 hours)\n   - Condiments and hard cheese (last — more resilient)\n\nWhen in doubt: If food has been above 40F for more than 2 hours, throw it out.\n\nFreeze water bottles now — they serve double duty as ice packs and drinking water.'},
      temp_concern: {type:'question', text:'Is it extremely hot or cold?', options:[
        {label:'Extreme heat (90F+ / no AC)', next:'heat'},
        {label:'Extreme cold (below freezing / no heat)', next:'cold'},
      ]},
      heat: {type:'result', style:'warning', text:'Surviving without AC:\n\n1. Close blinds/curtains on sun-facing windows\n2. Open windows on shaded side for cross-ventilation (only if outdoor air is cooler)\n3. Go to the lowest floor (heat rises)\n4. Wet towels on neck and wrists — major cooling points\n5. Drink water constantly — dehydration is the real killer\n6. If you have a generator: run ONE fan, not the AC (uses far less power)\n7. Avoid cooking (adds heat) — eat cold foods\n8. Check on elderly and young children frequently\n9. If it becomes dangerous (105F+, confusion, no sweating): go to a public cooling center\n\nHeat kills more people than any other weather event. Take it seriously.'},
      cold: {type:'result', style:'danger', text:'Surviving without heat:\n\n1. Consolidate everyone into ONE room — close doors to unused rooms\n2. Seal window gaps with towels or blankets\n3. Layer clothing: base layer (wicking), insulation (fleece/wool), outer (wind block)\n4. Stay off cold floors — use rugs, cardboard, sleeping pads\n5. If you have a fireplace/wood stove: use it. Open the flue.\n6. DO NOT use gas oven/stove for heating — carbon monoxide risk\n7. DO NOT run a generator indoors — EVER\n8. Body heat: huddle together under blankets\n9. Eat high-calorie foods — your body burns calories to stay warm\n10. If pipes are at risk: let faucets drip (moving water resists freezing)\n\nIf indoor temp drops below 50F and you cannot heat: go to a warming shelter or a neighbor with heat.'},
      medical_power: {type:'result', style:'danger', text:'Medical devices during outage — CRITICAL:\n\n1. CPAP: Most have battery backup options. Car inverter works. Prioritize this.\n2. Oxygen concentrator: Switch to backup O2 tanks immediately. Call your DME provider.\n3. Ventilator: Call 911 if battery backup is running low. This is life-threatening.\n4. Insulin (refrigerated): Place in a cooler with ice. Insulin is safe at room temp for up to 28 days.\n5. Nebulizer: Use a metered-dose inhaler (MDI) as backup.\n6. Electric wheelchair: Charge from car (inverter) while engine is running.\n\nPROACTIVE:\n- Register with your power company as a medical priority customer\n- Keep a UPS (battery backup) on critical medical devices\n- Have a written medical emergency plan posted on the fridge\n- Know your nearest hospital with generator power'},
      hours_general: {type:'result', style:'info', text:'Power out for several hours — action checklist:\n\n1. Confirm it is not just your house (check neighbors/power company)\n2. Unplug sensitive electronics (surge protection when power returns)\n3. Keep ONE light switch ON to know when power returns\n4. Inventory your resources:\n   - Water: how many gallons on hand?\n   - Food: what needs to be eaten first (perishable)?\n   - Light: flashlights, lanterns, candles (use carefully)\n   - Communication: battery radio, charged phone, HAM/FRS radio\n   - Power: generator, solar panel, battery banks, car inverter\n5. Conserve phone battery — lower brightness, close apps, airplane mode when not needed\n6. If you have a car: it is a charging station (run engine briefly in OPEN AIR)\n7. Start a simple log: time, temperature, actions taken — helps with insurance claims and after-action review'},
      extended: {type:'result', style:'warning', text:'12+ hours without power:\n\nYou are now in sustained outage territory. Shift from "waiting it out" to "managing the situation."\n\n1. FOOD: Cook and eat all thawed meat today. Prioritize perishables.\n2. WATER: If municipal, fill every container (water treatment plants have limited generator fuel). If well, you have no water without power — use stored supply.\n3. SANITATION: If water pressure fails, fill toilet tanks manually to flush. Or use 5-gallon buckets lined with trash bags + kitty litter.\n4. SECURITY: Darkness = vulnerability. Plan lighting and lock-up before sunset.\n5. MORALE: Establish a routine. Assign tasks. Play card games. Routine prevents panic.\n6. COMMUNICATION: Check in with neighbors. Establish a signal system (flag, whistle).\n7. FUEL: Calculate generator fuel burn rate. Ration run time (2 hours on, 4 hours off).\n\nIf no restoration estimate: begin preparing for multi-day grid-down.'},
longterm: {type:'result', style:'danger', text:'Multi-day grid down — survival mode:\n\nThis is a sustained emergency. Your priorities are: Water, Security, Food, Shelter, Communication.\n\n1. WATER: You need 1 gallon per person per day. Identify backup sources (rain, creek, pool). Purify everything.\n2. FOOD: Shift to shelf-stable supplies. Start a rationing plan. Cook with camp stove, grill, or fire.\n3. SECURITY: Establish a watch schedule. Lock everything. Know your neighbors.\n4. CASH: Have small bills. Electronic payments are dead.\n5. FUEL: Gas stations are closed. Whatever is in your tank is what you have. Drive only when critical.\n6. MEDICAL: Inventory all medications. Calculate how many days of supply remain.\n7. COMMUNICATION: Battery radio for news. HAM/FRS for local coordination. Establish a daily check-in schedule with neighbors.\n8. INFORMATION: Track your situation in NOMAD — log incidents, update inventory burn rates, adjust threat levels.\n\nMost grid-down events resolve within 3-7 days. But prepare as if it won\'t.'},
    }
  },
  {
    id: 'vehicle_emergency', title: 'Vehicle Emergency', icon: '&#128663;',
    desc: 'What to do when your vehicle breaks down, gets stuck, or you are in an accident.',
    nodes: {
      start: {type:'question', text:'What is the situation?', options:[
        {label:'Vehicle broke down / won\'t start', next:'breakdown'},
        {label:'Flat tire', next:'flat'},
        {label:'Accident / collision', next:'accident'},
        {label:'Stuck (mud, snow, ditch)', next:'stuck'},
        {label:'Overheating', next:'overheat'},
        {label:'Stranded in remote area', next:'stranded'},
      ]},
      breakdown: {type:'question', text:'Where are you?', options:[
        {label:'Highway / busy road', next:'breakdown_highway'},
        {label:'Side street / parking lot', next:'breakdown_safe'},
        {label:'Remote / rural area', next:'stranded'},
      ]},
      breakdown_highway: {type:'result', style:'danger', text:'Highway breakdown — SAFETY FIRST:\n\n1. Turn on hazard lights IMMEDIATELY\n2. Try to coast to the shoulder — as far right as possible\n3. If you cannot move: stay IN the vehicle with seatbelt ON\n4. Set flares or reflective triangles 50-100 feet behind the vehicle\n5. Exit on the PASSENGER side (away from traffic) if you must get out\n6. Stand well behind the guardrail, never between your car and traffic\n7. Call for help (roadside assistance, 911 if unsafe)\n\nAt night: interior dome light ON so approaching cars see you.\n\nDO NOT try to cross highway lanes on foot. Wait for help.'},
      breakdown_safe: {type:'result', style:'info', text:'Safe-location breakdown:\n\n1. Turn on hazard lights\n2. Try to diagnose:\n   - Won\'t crank at all: dead battery. Try jump start.\n   - Cranks but won\'t start: fuel problem, ignition, or sensor\n   - Starts then dies: fuel delivery or idle control\n   - Check engine light + rough running: sensor failure\n3. Basic checks you can do:\n   - Battery terminals tight and clean? (White corrosion = clean with baking soda + water)\n   - Gas tank not empty?\n   - Any visible leaks under the vehicle?\n   - Any burning smell?\n4. If you have jumper cables: flag down another car or use a jump pack\n5. If you have tools: check fuses (owner\'s manual has fuse box location)\n6. Call roadside assistance or a trusted mechanic'},
      flat: {type:'result', style:'info', text:'Flat tire — change it yourself:\n\n1. Pull to a flat, firm surface away from traffic. Hazards on.\n2. Apply parking brake. Put transmission in Park (auto) or gear (manual).\n3. Get spare tire, jack, and lug wrench from trunk.\n4. Loosen lug nuts BEFORE jacking up (1/4 turn each, star pattern)\n5. Place jack under the vehicle frame (check manual for jack points)\n6. Jack up until flat tire is 1 inch off ground\n7. Remove lug nuts completely, pull off flat tire\n8. Mount spare tire, hand-tighten lug nuts in star pattern\n9. Lower vehicle, then fully tighten lug nuts (star pattern, firm)\n10. Check spare tire pressure — most spares are limited to 50 mph and 50 miles\n\nNo spare? Use a tire sealant can (Fix-a-Flat). Drive slowly to the nearest tire shop.\n\nIf you don\'t have tools: call roadside assistance.'},
      accident: {type:'result', style:'danger', text:'Vehicle accident response:\n\n1. CHECK YOURSELF for injuries first. Are you bleeding? Can you move?\n2. Check passengers. If anyone is seriously injured: call 911 FIRST.\n3. Turn off the engine. Hazard lights on.\n4. If the vehicle is on fire or you smell gas: GET OUT and move 100+ feet away.\n5. If safe to stay: keep seatbelt on until emergency services arrive.\n6. DO NOT move seriously injured people unless there\'s immediate danger (fire, water).\n7. Exchange info with other driver: name, license, insurance, plate number, phone.\n8. Take photos: damage to all vehicles, license plates, intersection, traffic signs, road conditions.\n9. File a police report — even for minor accidents.\n10. Do NOT admit fault at the scene.\n\nCall your insurance company within 24 hours. Get a copy of the police report for your records.'},
      stuck: {type:'result', style:'warning', text:'Vehicle stuck (mud/snow/ditch):\n\n1. STOP spinning wheels immediately — you are digging deeper.\n2. Straighten the steering wheel.\n3. Clear mud/snow from around the tires (as much as you can reach).\n4. Place traction material under the drive wheels:\n   - Floor mats (rubber side up)\n   - Branches, boards, gravel, sand\n   - Cat litter (absorbs moisture, adds traction)\n   - Cardboard in a pinch\n5. Rock the vehicle: alternate Drive and Reverse gently. Do NOT floor it.\n6. Let some air out of tires (lowers to ~20 PSI) — wider contact patch. Re-inflate ASAP after.\n7. If you have a winch or tow strap: attach to a solid tree/anchor point.\n8. If truly stuck: call a tow truck. Don\'t damage your transmission.\n\nPrevention: carry a traction mat, tow strap, and small shovel in your vehicle kit.'},
      overheat: {type:'result', style:'warning', text:'Engine overheating:\n\n1. Turn OFF the AC immediately.\n2. Turn the heater to MAX HOT and fan to HIGH — this pulls heat from the engine.\n3. Pull over as soon as safely possible. Turn off the engine.\n4. DO NOT open the radiator cap while hot — pressurized steam will burn you severely.\n5. Wait at least 30 minutes for the engine to cool.\n6. Check coolant level (only when cool): if low, add water or coolant.\n7. Check for visible leaks: under the car, around hoses, at the radiator.\n8. If you must drive: go slowly with heater on max. Stop every 5 minutes if temp rises.\n\nCommon causes: coolant leak, broken fan belt, failed water pump, stuck thermostat, blocked radiator.\n\nIf coolant is spraying or there\'s steam from under the hood: DO NOT drive. Tow it.'},
      stranded: {type:'result', style:'danger', text:'Stranded in a remote area:\n\n1. STAY WITH YOUR VEHICLE — it is shelter, signaling device, and easier to find than a person on foot.\n2. Turn on hazard lights. At night, dome light on periodically.\n3. If you have cell signal: call for help. Share your GPS coordinates.\n4. If no cell signal: try driving to higher ground for signal.\n5. Conserve fuel — run engine 10 minutes per hour for heat. Crack a window to prevent CO buildup.\n6. Make yourself visible: bright cloth on antenna, hood up, flares if available.\n7. If you must walk: ONLY if you can see a building or know the exact distance. Leave a note on dashboard with direction you went + time.\n\nSurvival priorities:\n- Shelter (your car)\n- Water (carry at least 1 gallon in your vehicle always)\n- Signaling (mirror, horn, lights)\n- Food (keep granola bars in your vehicle kit)\n\nMost stranded motorists are found within 24 hours if they stay with their vehicle.'},
    }
  },
  {
    id: 'bugout_decision', title: 'Bug-Out vs Shelter-In-Place', icon: '&#127970;',
    desc: 'The hardest decision in an emergency — should you stay or go? This guide helps you decide.',
    nodes: {
      start: {type:'question', text:'What type of threat are you facing?', options:[
        {label:'Natural disaster (storm, flood, fire, earthquake)', next:'natural'},
        {label:'Infrastructure failure (grid down, water contamination)', next:'infra'},
        {label:'Civil unrest / social breakdown', next:'civil'},
        {label:'Chemical / nuclear / biological event', next:'cbrn'},
        {label:'Personal threat (home invasion, stalker)', next:'personal'},
      ]},
      natural: {type:'question', text:'Is your home directly threatened?', options:[
        {label:'Yes — flood water rising, fire approaching, building damaged', next:'evacuate_now'},
        {label:'Maybe — in warning zone but not immediate danger', next:'natural_maybe'},
        {label:'No — we are outside the danger zone', next:'shelter_natural'},
      ]},
      evacuate_now: {type:'result', style:'danger', text:'EVACUATE NOW — your home is directly threatened.\n\n1. Grab your go-bag (you have 15 minutes or less)\n2. Take: IDs, medications, phone + charger, cash, keys\n3. Take: important documents if within arm\'s reach (passports, insurance)\n4. Load family + pets into vehicle\n5. Drive your PRIMARY evacuation route\n6. If primary is blocked: switch to ALTERNATE route immediately\n7. DO NOT go back for anything\n8. Notify family/contacts of your destination\n9. Head to your pre-designated rally point\n\nIf you have NO plan:\n- Drive perpendicular to the threat (away from flood path, away from fire front)\n- Head toward a major highway\n- Go to the nearest public shelter (school, community center)\n\nYour life is worth more than anything in that house.'},
      natural_maybe: {type:'question', text:'How prepared is your home?', options:[
        {label:'Well-prepared (supplies, sturdy construction, elevated)', next:'shelter_natural'},
        {label:'Somewhat prepared (some supplies, average construction)', next:'prepare_or_go'},
        {label:'Not prepared (no supplies, vulnerable structure)', next:'go_soon'},
      ]},
      shelter_natural: {type:'result', style:'success', text:'SHELTER IN PLACE — monitor and prepare to leave.\n\n1. Your home is your best shelter IF it is not directly threatened\n2. Monitor the situation: NOAA radio, local news, emergency alerts\n3. Set a TRIGGER — a specific condition that means you leave:\n   - Water reaches X street\n   - Fire is within X miles\n   - Wind exceeds X mph\n4. Pre-load vehicle with go-bags and essentials NOW\n5. Top off vehicle fuel\n6. Identify what you would grab in a 5-minute evacuation\n7. Keep shoes and clothes by the bed if sleeping\n\nAdvantages of sheltering: you have all your supplies, you know the space, you have power/water (for now).\n\nBut be READY to go. Don\'t let comfort turn into a death trap.'},
      prepare_or_go: {type:'result', style:'warning', text:'PREPARE NOW — you have a window of time.\n\nYou are in the decision zone. Use the next 1-2 hours wisely:\n\n1. Fill bathtubs and containers with water\n2. Charge all devices\n3. Secure outdoor items (flying debris in storms)\n4. Move to interior room / upper floor (flood) / lowest floor (tornado)\n5. Load vehicle with essentials in case you need to leave quickly\n\nDecision framework — LEAVE if any of these become true:\n- Mandatory evacuation order issued\n- You can see/smell the threat approaching\n- Utilities fail (water/power/gas)\n- You feel unsafe for ANY reason\n\nTrust your instincts. If your gut says go — GO. You can always come back.'},
      go_soon: {type:'result', style:'danger', text:'LEAVE SOON — your situation is vulnerable.\n\nYou don\'t have the supplies or structure to ride this out safely.\n\n1. Pack what you can in 30 minutes\n2. Essentials: water, food (non-perishable), medications, IDs, cash, phone, charger, warm clothes, blankets\n3. Head to:\n   - Family or friends outside the danger zone\n   - Public emergency shelter\n   - Hotel/motel in a safe area\n4. Bring your pets\n5. Tell someone where you\'re going\n6. Take photos of your home interior for insurance before you leave\n\nLeaving early is ALWAYS better than leaving late. Traffic, panic, and road closures get worse every hour you wait.'},
      infra: {type:'question', text:'How long do you think services will be out?', options:[
        {label:'Hours to 1-2 days', next:'shelter_infra_short'},
        {label:'Days to a week', next:'shelter_infra_week'},
        {label:'Unknown / could be weeks+', next:'infra_long'},
      ]},
      shelter_infra_short: {type:'result', style:'success', text:'SHELTER IN PLACE — short-term infrastructure outage.\n\nYou are safer at home for 1-2 day outages.\n\n1. Use your stored water and food\n2. Conserve: minimize fridge openings, ration fuel, reduce water use\n3. Stay informed: battery radio, check on neighbors\n4. Keep your vehicle fueled and ready as a backup plan\n\nDon\'t panic-drive to the store. You will burn fuel and encounter chaos. Use what you have.'},
shelter_infra_week: {type:'result', style:'warning', text:'SHELTER IN PLACE — but actively manage resources.\n\nFor a week-long outage, home is still likely your best option IF you have supplies.\n\nDaily management:\n- Track water consumption (1 gal/person/day minimum)\n- Track food inventory and plan meals around perishables\n- Manage generator fuel (2h on / 4h off cycle)\n- Maintain security (lock up, neighborhood watch)\n- Log everything in NOMAD.\n\nConsider leaving IF:\n- Water supply drops below 3 days\n- Medical needs cannot be met\n- Security situation deteriorates\n- You have a fully-supplied bug-out location available'},
      infra_long: {type:'result', style:'danger', text:'CRITICAL DECISION — stay or relocate.\n\nWeeks-long infrastructure failure is a survival situation.\n\nSTAY if:\n- You have 30+ days of water and food\n- You have a sustainable water source (well, spring, rain collection)\n- Your community is organized and cooperative\n- You have renewable power (solar)\n- Your home is defensible\n\nGO if:\n- You have a pre-planned bug-out location with supplies\n- Your neighborhood is becoming unsafe\n- Water or food will run out before services return\n- You have family/group at a better-supplied location\n- Roads are still passable (this window closes fast)\n\nIf you GO: travel during daylight, avoid highways (checkpoints, bottlenecks), take back roads, travel in convoy if possible, be armed and vigilant.'},
      civil: {type:'question', text:'How close is the unrest to your location?', options:[
        {label:'In my neighborhood / within blocks', next:'civil_close'},
        {label:'In my city but not my area yet', next:'civil_city'},
        {label:'In my region but not my city', next:'shelter_civil'},
      ]},
      civil_close: {type:'result', style:'danger', text:'IMMEDIATE THREAT — unrest in your neighborhood.\n\n1. Lock all doors and windows. Close blinds/curtains.\n2. Move family to an interior room on an upper floor\n3. Stay away from windows (stray bullets, thrown objects)\n4. DO NOT engage with crowds or confront anyone\n5. Have go-bags ready by the door\n6. If your home is being specifically targeted: LEAVE via back exit\n7. If leaving: drive calmly, do not draw attention, avoid main roads\n8. Head to a pre-planned safe location outside the affected area\n\nDO NOT:\n- Stand on your porch or roof to watch\n- Post your location on social media\n- Open the door for anyone you don\'t know\n- Fire warning shots (escalates the situation and reveals you\'re armed)'},
      civil_city: {type:'result', style:'warning', text:'SHELTER IN PLACE — prepare to leave.\n\nUnrest in your city but not your area yet. You have time.\n\n1. Lock down your home. Arm security if you have it.\n2. Fill vehicle with fuel, pack go-bags, load essentials\n3. Monitor situation: local news, scanner apps, social media (carefully)\n4. Set a TRIGGER point: if unrest reaches [specific street/landmark], you leave\n5. Identify your evacuation route OUT of the city\n6. Contact friends/family outside the area — arrange a place to stay\n7. Keep a low profile: no political signs, flags, or bumper stickers visible\n8. Be a "gray man" — blend in, don\'t attract attention\n\nMost civil unrest is localized and burns out in 3-7 days. But it can spread unpredictably.'},
      shelter_civil: {type:'result', style:'success', text:'SHELTER IN PLACE — monitor from a distance.\n\nUnrest in your region but not your city. Lowest risk.\n\n1. Increase situational awareness — monitor news, local scanner\n2. Top off fuel, water, and supplies as a precaution\n3. Avoid traveling to affected areas\n4. Review your emergency plans and rally points\n5. Consider: would you be cut off if roads in/out are blocked?\n6. If you commute through affected areas: work from home or take alternate routes\n\nThis is a good time to do a full supply check and ensure your go-bags are current.'},
      cbrn: {type:'result', style:'danger', text:'Chemical / Nuclear / Biological event:\n\nSHELTER IN PLACE for the initial event. Do NOT evacuate during a chemical/radiological release.\n\n1. Get INSIDE immediately — a sealed building is your best protection\n2. Close all windows and doors\n3. Turn OFF HVAC / air conditioning (stops pulling contaminated air in)\n4. Seal gaps: wet towels under doors, tape over vents if available\n5. Move to an interior room, preferably above ground (chemicals settle, radiation doesn\'t rise)\n6. Cover nose and mouth with wet cloth if air quality is poor\n7. Monitor emergency broadcasts (NOAA radio, TV if available)\n8. DO NOT go outside to "check the situation"\n\nEvacuate ONLY when authorities say it is safe, OR if your shelter is compromised.\n\nNuclear: shelter for minimum 24 hours (fallout decay). Ideal: 48-72 hours.\nChemical: shelter until all-clear is given.\nBiological: follow quarantine protocols. Limit contact with others.'},
      personal: {type:'result', style:'danger', text:'Personal threat — leave if you can.\n\n1. If someone is actively threatening you: call 911 first\n2. Do NOT confront — leave the area\n3. Go to a safe person\'s house, police station, or public place\n4. Take your phone, ID, keys, wallet, medications\n5. If children are involved: take them with you\n6. Do NOT announce your destination on social media\n\nIf you cannot leave safely:\n- Lock yourself in a room with a phone\n- Call 911 and stay on the line\n- Barricade the door\n- Identify an alternate exit (window)\n\nAfter the immediate threat:\n- File a police report\n- Document everything (photos, messages, dates)\n- Consider a protective order\n- Change locks and security codes\n- Tell trusted neighbors to watch for the person'},
    }
  },

  // ─────────────────────────────────────────────────────────────────────────
  {
    id: 'antibiotic_selection',
    icon: '💊',
    title: 'Antibiotic Selection Guide',
    desc: 'Match symptoms to infection type and identify appropriate antibiotic treatment for grid-down medical care.',
    start: 'start',
    nodes: {
      start: {type:'question', text:'What is the primary symptom or infection site?', options:[
        {label:'Skin: redness, swelling, warmth, possible pus', next:'skin_q1'},
        {label:'Respiratory: cough, fever, difficulty breathing', next:'resp_q1'},
        {label:'Urinary: painful urination, frequency, urgency', next:'uti_q1'},
        {label:'GI: diarrhea, nausea, vomiting, abdominal pain', next:'gi_q1'},
        {label:'Dental: tooth pain, swollen jaw/gum, abscess', next:'dental_result'},
        {label:'Wound infection: after injury or surgery', next:'wound_q1'},
        {label:'Tick bite or rash (bullseye or spreading)', next:'tick_result'},
      ]},
      skin_q1: {type:'question', text:'Is there an abscess or pus collection that could be drained?', options:[
        {label:'Yes — localized pocket of pus', next:'abscess_result'},
        {label:'No — spreading redness (cellulitis)', next:'skin_q2'},
      ]},
      skin_q2: {type:'question', text:'Was there an animal bite or puncture wound involved?', options:[
        {label:'Yes — animal bite or deep puncture', next:'bite_result'},
        {label:'No — normal skin/soft tissue', next:'cellulitis_result'},
      ]},
      abscess_result: {type:'result', style:'warning', text:'ABSCESS — Drainage is the primary treatment.\n\nStep 1: DRAIN the abscess if possible. Antibiotics alone will not cure a closed abscess.\n- Clean the area with betadine or chlorhexidine\n- Lance with a sterile blade at the most fluctuant (softest) point\n- Express the contents, irrigate the cavity with saline\n- Pack loosely with gauze, change daily\n\nStep 2: Antibiotics (add if spreading/fever):\n- Amoxicillin-Clavulanate 875mg twice daily × 7 days\n- Alternative: Clindamycin 300–450mg three times daily × 7 days\n\nMonitor for red streaking (lymphangitis) → urgent antibiotics if present.\nMonitor for fever, rigors (sepsis) → add antibiotics immediately.'},
      bite_result: {type:'result', style:'warning', text:'ANIMAL BITE INFECTION\n\nImmediate irrigation is critical — within 30 minutes, copious saline flushing significantly reduces infection risk.\n\nAntibiotics (start within 8 hours of bite, prophylactically):\n- Amoxicillin-Clavulanate 875mg twice daily × 5–7 days\n- Alternative (PCN allergy): Doxycycline 100mg + Metronidazole 500mg, both twice daily\n\nRabies risk: Wild animal (raccoon, bat, fox, skunk) = HIGH. Domestic animal, unknown vaccination = MODERATE.\nIf rabies suspected: RIG + vaccine series is definitive. Field: clean wound thoroughly, begin antibiotics.\n\nTetanus: Update if >5 years since last booster.'},
      cellulitis_result: {type:'result', style:'success', text:'CELLULITIS (skin/soft tissue infection)\n\nAntibiotics:\n- Amoxicillin-Clavulanate 875mg twice daily × 5–7 days (covers strep and staph)\n- Alternative: Cephalexin 500mg four times daily\n- MRSA suspected (failed 48h treatment, healthcare exposure): Clindamycin 300–450mg TID or TMP/SMX DS twice daily\n\nActions:\n1. Draw margin of redness with pen — reassess every 6–12 hours\n2. Elevate affected limb\n3. Watch for: red streaks, worsening fever, rapidly expanding margins\n4. If no improvement at 48h: change antibiotic class or reassess diagnosis\n\nDo NOT dismiss — untreated cellulitis → sepsis rapidly in immunocompromised.'},
      resp_q1: {type:'question', text:'How severe is the respiratory illness?', options:[
        {label:'Mild — productive cough, no high fever', next:'resp_mild'},
        {label:'Moderate — fever >38.5°C, shortness of breath at rest', next:'resp_mod'},
        {label:'Severe — cannot lie flat, lips/nails blue, very rapid breathing', next:'resp_severe'},
      ]},
      resp_mild: {type:'result', style:'success', text:'MILD RESPIRATORY INFECTION\n\nMost mild respiratory illnesses are VIRAL (colds, flu) — antibiotics will NOT help.\n\nTreat symptoms:\n- Rest, hydration (hot liquids help)\n- Ibuprofen or acetaminophen for fever/body aches\n- Honey + lemon for cough (evidence-based)\n- Steam inhalation for congestion\n\nStart antibiotics ONLY if:\n- Symptoms worsening after 7 days (suggests secondary bacterial infection)\n- Productive cough with green/yellow sputum + fever >38°C\n- Known exposure to bacterial pneumonia\n\nIf antibiotics indicated:\n- Azithromycin 500mg Day 1, then 250mg × 4 days (Z-Pak)\n- Alternative: Doxycycline 100mg twice daily × 7 days'},
      resp_mod: {type:'result', style:'warning', text:'MODERATE PNEUMONIA — Begin antibiotics.\n\nFirst-line:\n- Azithromycin 500mg Day 1, then 250mg × 4 more days\n- Alternative: Doxycycline 100mg twice daily × 7–10 days\n- For more severe CAP: Amoxicillin-Clavulanate 875mg BID + Azithromycin\n\nSupportive care:\n- Elevate head of bed (30–45°)\n- Encourage deep breathing and coughing every 2 hours\n- Adequate hydration (helps thin secretions)\n- Fever management with antipyretics\n\nWARNING signs requiring urgent escalation:\n- O2 sat <94% (if pulse ox available)\n- Confusion or altered mental status\n- Cyanosis\n- Unable to maintain oral hydration\n- Rapidly worsening over hours'},
      resp_severe: {type:'result', style:'danger', text:'SEVERE RESPIRATORY DISTRESS — Life-threatening.\n\nThis is beyond field antibiotic management alone.\n\nImmediate actions:\n1. Position: upright, sitting forward (tripod position)\n2. Oxygen if available — high flow\n3. Albuterol inhaler if wheezing (bronchospasm component)\n4. Clear airway — suction if secretions\n\nAntibiotics — start immediately (dual coverage):\n- Azithromycin 500mg + Amoxicillin-Clavulanate 875mg\n- Or: Doxycycline 100mg + Amoxicillin-Clavulanate\n\nFear: Tension pneumothorax (no breath sounds one side), pulmonary edema (frothy pink sputum), severe anaphylaxis — each requires specific immediate intervention.\n\nEvacuate if ANY means available. This patient needs a hospital.'},
      uti_q1: {type:'question', text:'Does the patient have back/flank pain or fever?', options:[
        {label:'No — just urinary symptoms (uncomplicated UTI)', next:'uti_result'},
        {label:'Yes — flank pain and/or fever (kidney involvement)', next:'pyelo_result'},
      ]},
      uti_result: {type:'result', style:'success', text:'UNCOMPLICATED UTI\n\nAntibiotics (3-day course):\n- Ciprofloxacin 500mg twice daily × 3 days\n- Alternative: TMP/SMX DS (160/800mg) twice daily × 3 days\n- Alternative: Nitrofurantoin 100mg twice daily × 5 days (not for kidney involvement)\n\nSupportive:\n- Increase water intake to 2–3L/day\n- Phenazopyridine (AZO) 200mg three times daily × 2 days for burning symptom relief (turns urine orange — normal)\n- Avoid caffeine and alcohol during treatment\n\nNo improvement at 48 hours: extend to 7 days or switch antibiotic class.\nNote: Recurrent UTIs in women — consider post-coital prophylaxis.'},
      pyelo_result: {type:'result', style:'warning', text:'PYELONEPHRITIS (Kidney Infection)\n\nThis is a serious infection requiring full antibiotic course.\n\nAntibiotics (14-day course):\n- Ciprofloxacin 500mg twice daily × 14 days\n- Alternative: TMP/SMX DS twice daily × 14 days\n- Severe: if available, IV Ceftriaxone 1–2g daily for first 3 days then switch to oral\n\nSupportive:\n- Aggressive hydration (3+ liters/day)\n- Ibuprofen or acetaminophen for fever and flank pain\n- Bed rest while febrile\n\nWARNING: If not improving at 72 hours, or if the patient develops low BP, confusion, or rigors — this may be urosepsis. Evacuate if any means available.'},
      gi_q1: {type:'question', text:'Is there blood in the stool or fever above 38.5°C?', options:[
        {label:'Yes — bloody diarrhea and/or high fever', next:'gi_severe'},
        {label:'No — watery diarrhea, cramping, no blood', next:'gi_mild'},
      ]},
      gi_mild: {type:'result', style:'success', text:'TRAVELER\'S DIARRHEA / MILD GI INFECTION\n\nMost cases resolve without antibiotics.\n\nPrimary treatment: ORAL REHYDRATION THERAPY (ORT)\n- WHO formula: 1L water + 6 tsp sugar + 1/2 tsp salt\n- Or: Pedialyte, Gatorade diluted 1:1 with water\n- Goal: replace what is lost. Drink 200mL after each loose stool.\n\nAnti-motility (use only without bloody stool/fever):\n- Loperamide (Imodium) 4mg then 2mg after each loose stool (max 16mg/day)\n\nAntibiotics — consider if not improving at 48h:\n- Azithromycin 1g single dose (most effective for traveler\'s diarrhea)\n- Alternative: Ciprofloxacin 500mg twice daily × 3 days\n\nWARN: Avoid antibiotics for E. coli O157:H7 (STEC) if suspected — increases HUS risk.'},
      gi_severe: {type:'result', style:'danger', text:'SEVERE GI INFECTION — dysentery, invasive bacteria\n\nBloody diarrhea + fever = bacterial dysentery (Salmonella, Shigella, Campylobacter, etc.)\n\nDo NOT use anti-motility agents (loperamide) — can cause toxic megacolon.\n\nOral Rehydration Therapy — aggressive:\n- 1L water + 6 tsp sugar + 1/2 tsp salt every hour until improving\n\nAntibiotics (start immediately):\n- Azithromycin 500mg once daily × 3–5 days\n- Alternative: Ciprofloxacin 500mg twice daily × 3–5 days\n- Giardia/amoeba suspected (cysts, prolonged course): Metronidazole 500mg three times daily × 7–10 days\n\nWARNING — evacuate if:\n- Signs of severe dehydration (no urination 8+ hours, dry mouth, confusion)\n- High fever >39.5°C not responding to antipyretics\n- Abdominal rigidity (peritonitis)\n- Patient cannot maintain oral hydration'},
      wound_q1: {type:'question', text:'How old is the wound?', options:[
        {label:'<6 hours old — fresh wound', next:'wound_fresh'},
        {label:'6–24 hours old, contaminated or high-risk', next:'wound_contam'},
        {label:'>24 hours with signs of infection (redness, pus, fever)', next:'wound_infected'},
      ]},
      wound_fresh: {type:'result', style:'success', text:'FRESH WOUND — Infection prevention.\n\n1. Irrigate aggressively: 100–300mL saline per cm wound length under pressure\n2. Explore and remove all debris\n3. Assess: can be closed? (clean + <6h + not bite/puncture = usually yes)\n\nProphylactic antibiotics: NOT routinely needed for clean wounds.\n\nGive antibiotics for high-risk wounds:\n- Bites (animal or human), punctures, crush injuries, heavily contaminated\n- Amoxicillin-Clavulanate 875mg twice daily × 5–7 days\n\nTetanus: update if >5 years for contaminated, >10 years for clean wounds.\n\nMonitor for infection signs: redness beyond wound margins at 24–48h, warmth, pus, fever.'},
      wound_contam: {type:'result', style:'warning', text:'CONTAMINATED WOUND (6–24h old)\n\nIrrigation is still effective but more important than ever:\n- Copious saline irrigation, explore and debride\n- Do NOT close primarily — leave open or use delayed primary closure (3–5 days)\n- Pack with moist dressing, change twice daily\n\nStart antibiotics:\n- Amoxicillin-Clavulanate 875mg twice daily × 7–10 days\n- Alternative (PCN allergy): Clindamycin 300mg + Ciprofloxacin 500mg, both twice daily\n\nHuman bite: add Metronidazole 500mg three times daily (anaerobic coverage).\n\nWATCH FOR: Gas gangrene signs (crepitus, rapidly spreading necrosis, extreme pain) → surgical emergency.'},
      wound_infected: {type:'result', style:'danger', text:'ESTABLISHED WOUND INFECTION\n\nThe window for simple treatment may be closing. Act decisively.\n\nStep 1: Assess depth and severity\n- Superficial (skin only): treat with oral antibiotics\n- Deep / tracking along tissue planes: may need debridement\n- Red streaking (lymphangitis): URGENT — start IV-equivalent doses immediately\n- Crepitus under skin: gas gangrene — life-threatening, needs aggressive debridement\n\nStep 2: Antibiotics\n- Amoxicillin-Clavulanate 875mg twice daily × 10–14 days\n- Add Metronidazole 500mg TID if anaerobic infection suspected (smell, necrosis)\n- MRSA suspected: Clindamycin 450mg TID or TMP/SMX DS BID\n\nWound care:\n- Debride necrotic tissue (anything brown/black/non-bleeding)\n- Irrigate daily, pack open\n- Do NOT close infected wounds\n\nEvacuate if: sepsis signs (fever >39°, fast heart rate, confusion), rapidly spreading despite antibiotics.'},
      dental_result: {type:'result', style:'warning', text:'DENTAL INFECTION / ABSCESS\n\nDefinitive treatment: dental extraction or root canal. Field care buys time.\n\nAnalgesia (pain control — priority):\n- Ibuprofen 600mg every 6–8 hours (reduces inflammation)\n- Combine with Acetaminophen 1000mg for stronger effect\n- Clove oil (eugenol) — apply to tooth/gum with cotton ball (topical anesthetic)\n\nAntibiotics (start if spreading, fever, or swelling in face/neck):\n- Amoxicillin 500mg three times daily × 7 days\n- PCN allergy: Clindamycin 300mg four times daily × 7 days\n- Can add Metronidazole 500mg TID for additional anaerobic coverage\n\n⚠ DANGER SIGNS — evacuate immediately:\n- Swelling spreading to jaw, neck, or floor of mouth\n- Difficulty swallowing or opening mouth (Ludwig\'s angina)\n- High fever + confusion\nLudwig\'s angina is a life-threatening space infection that can close the airway.'},
      tick_result: {type:'result', style:'warning', text:'TICK-BORNE ILLNESS / LYME DISEASE\n\nRemove tick properly:\n- Fine-tipped tweezers, grasp as close to skin as possible\n- Pull straight up, no twisting\n- Clean with rubbing alcohol or soap/water\n- Do NOT: burn, petroleum jelly, or twist the tick\n\nBullseye rash (erythema migrans) = Lyme disease, begin treatment immediately:\n- Doxycycline 100mg twice daily × 21 days\n- Alternative (children <8, pregnancy): Amoxicillin 500mg TID × 21 days\n\nRocky Mountain Spotted Fever (RMSF) — fever + rash spreading from wrists/ankles:\n- START DOXYCYCLINE IMMEDIATELY. Do NOT wait for lab confirmation.\n- Doxycycline 100mg twice daily × 7 days (adults and children — risk outweighs dental staining)\n- Delay >5 days dramatically increases mortality\n\nSave tick in sealed bag/container for identification if possible.'},
    }
  },

  // ─────────────────────────────────────────────────────────────────────────
  {
    id: 'water_source_assessment',
    icon: '💧',
    title: 'Water Source Assessment',
    desc: 'Assess your water source and determine the appropriate purification method for safe drinking water.',
    start: 'start',
    nodes: {
      start: {type:'question', text:'What is your water source?', options:[
        {label:'Municipal tap water (grid still up)', next:'tap'},
        {label:'Well water (your own well)', next:'well_q1'},
        {label:'Surface water — stream, river, pond, lake', next:'surface_q1'},
        {label:'Rainwater / roof collection', next:'rain_q1'},
        {label:'Standing water — puddle, flood water, barrel', next:'standing'},
        {label:'Unknown or mixed source', next:'unknown'},
      ]},
      tap: {type:'result', style:'success', text:'MUNICIPAL TAP WATER — Normally safe, but verify.\n\nIn normal conditions: Drink as-is. Municipalities treat to EPA standards.\n\nIn a crisis/boil advisory:\n- Boil: rolling boil for 1 minute (3 minutes above 6,500 ft) — kills all pathogens\n- Or: Chemical treatment if boiling not possible\n\nPre-treat concerns:\n- Chlorine taste: activated carbon filter (Brita, etc.) removes it\n- Known contamination event (industrial spill, PFAS): bottled water until cleared\n- Infrastructure damaged: treat as surface water until service restored\n\nFor storage: tap water stays safe 6–12 months in sealed clean containers.\nRefill containers every 6 months to maintain freshness.'},
      well_q1: {type:'question', text:'Is the well protected from surface contamination?', options:[
        {label:'Yes — sealed casing, no flooding, no nearby septic', next:'well_good'},
        {label:'Uncertain or no — old well, recent flooding, nearby animals', next:'well_risk'},
      ]},
      well_good: {type:'result', style:'success', text:'PROTECTED WELL — Generally safe with basic treatment.\n\nFor a well in good condition:\n- Filter: sediment pre-filter to remove particulates\n- Chemical: small dose of unscented bleach (1/4 tsp per 55 gallons for chlorination)\n- Or: UV treatment for final step\n\nTest annually for: coliform bacteria, nitrates, pH, hardness. More often after flooding.\n\nShock chlorination (after flooding or contamination):\n- Mix 1 cup bleach per 100 gallons of well volume\n- Pour down well, run all taps until bleach smell, let sit 24 hours\n- Flush until chlorine smell gone, then test before drinking\n\nWell pump fails? Manual pitcher pump or rope-bucket for shallow wells (<25 ft). Hand-dug well: minimum 10 ft diameter clay-sealed cap.'},
      well_risk: {type:'result', style:'warning', text:'WELL — CONTAMINATION RISK. Treat before drinking.\n\nIf well has been flooded or is unprotected:\n1. Do NOT drink without treatment\n2. Collect sample — visual inspection (color, odor, particulates)\n3. Let sediment settle (30 min) then decant or pre-filter\n\nTreatment chain (use all steps for maximum safety):\n1. Pre-filter: coffee filter, cloth, or commercial sediment filter\n2. Boil: 1 minute rolling boil OR\n3. Chemical: 8 drops unscented 6% bleach per gallon, wait 30 min\n4. If available: activated carbon filter for taste\n\nFor flooding contamination (fecal coliform, farm runoff, chemical):\n- Boiling handles pathogens but NOT heavy metals or agricultural chemicals\n- Activated carbon + boiling together covers most scenarios\n- Arsenic/nitrates: requires RO or specific exchange filters'},
      surface_q1: {type:'question', text:'What is the visual clarity and flow of the water?', options:[
        {label:'Clear, flowing stream or spring', next:'surface_clear'},
        {label:'Murky, brown, or slow-moving', next:'surface_murky'},
        {label:'Green, foul-smelling, algae present', next:'surface_algae'},
      ]},
      surface_clear: {type:'result', style:'warning', text:'CLEAR SURFACE WATER — Still requires treatment.\n\nClear does not mean safe. Invisible pathogens (Giardia, Cryptosporidium, bacteria, viruses) are always present in surface water.\n\nRecommended treatment chain:\n1. Pre-filter: coffee filter or cloth (remove particulates)\n2. Filter: 0.1–0.2 micron hollow fiber filter (Sawyer Squeeze, LifeStraw) — removes bacteria and protozoa\n3. Chemical/UV: 8 drops bleach per gallon OR UV pen (60 sec) — handles viruses\n\nFor backcountry streams above human/animal activity: hollow fiber filter alone may be sufficient.\nFor streams near farms, towns, or with wildlife: full chemical + filter treatment recommended.\n\nSprings: generally cleaner but still treat. True springs emerge from ground (not surface runoff).'},
      surface_murky: {type:'result', style:'warning', text:'MURKY/TURBID SURFACE WATER — Extended treatment needed.\n\nTurbidity blocks UV light and reduces chemical effectiveness. Must clear water first.\n\nStep 1 — Settling:\n- Pour into clean container, let settle 30–60 minutes\n- Gently decant the clear top portion into treatment container\n- Or: coagulation (pinch of alum powder or cactus mucilage per gallon — stirs particles together)\n\nStep 2 — Pre-filter:\n- Multiple layers of cloth, sand, gravel in sequence (improvised sand filter)\n- Or commercial sediment filter cartridge\n\nStep 3 — Purify:\n- Boil 1 minute (most reliable for turbid sources)\n- Or: double chemical dose if boiling not possible (16 drops bleach/gal)\n- UV pen ONLY after water is visually clear\n\nImprovised sand filter: layers (top to bottom): fine sand → coarse sand → gravel → charcoal → output. Slow but effective pre-filter.'},
      surface_algae: {type:'result', style:'danger', text:'ALGAE / FOUL-SMELLING WATER — Special risks.\n\n⚠ CYANOBACTERIA (blue-green algae) produces CYANOTOXINS.\nBoiling does NOT neutralize cyanotoxins — it INCREASES concentration.\n\nIf water is green, smells musty/earthy, or has surface scum:\n- Do NOT use if any alternative exists\n- Activated carbon filter (charcoal) can remove some cyanotoxins\n- Charcoal + coagulation + settling is best available field method\n- RO membranes remove cyanotoxins (if available)\n\nOther foul odors:\n- Sulfur smell (rotten eggs): usually hydrogen sulfide — aerate by pouring between containers, then treat normally\n- Chemical/petroleum smell: do NOT drink. Activated carbon + multiple-stage treatment only reduces, not eliminates petroleum contamination.\n\nFor genuine survival use: settle, coagulate, filter through activated charcoal, then boil. Better than dehydration.'},
      rain_q1: {type:'question', text:'What surface was the rainwater collected from?', options:[
        {label:'Clean tarp, food-grade barrel — first rain discarded', next:'rain_clean'},
        {label:'Roof — metal or asphalt shingles', next:'rain_roof'},
      ]},
      rain_clean: {type:'result', style:'success', text:'RAIN COLLECTION — Clean collection, minimal treatment needed.\n\nClean collection (first-flush discarded, food-grade containers):\n- Filter: coffee filter or cloth to remove particulates and insects\n- Chemically treat: 8 drops bleach per gallon (standard dose)\n- Or UV pen treatment\n\nRainwater is generally soft (low minerals) and free of many contaminants at collection point.\n\nStore in food-grade, opaque containers (prevents algae growth).\nTreat before drinking — especially if collected during or after industrial/agricultural activity.\nConsider activated carbon filter if in industrial area.'},
      rain_roof: {type:'result', style:'warning', text:'ROOF COLLECTION — Requires full treatment.\n\nRoof water picks up:\n- Asphalt shingles: PAHs (polycyclic aromatic hydrocarbons), not fully removed by boiling\n- Bird/animal droppings: Salmonella, Cryptosporidium, E. coli\n- Metal roofs: copper/zinc leaching\n- Atmospheric pollutants, lead paint (old homes)\n\nTreatment chain:\n1. First-flush diverter: discard first 10–15 min of rain\n2. Pre-filter: coarse screen, then coffee filter\n3. Activated carbon filter: reduces organics and metals\n4. Boil or chemical treatment: final pathogen kill\n\nBest use of roof water for long-term: irrigation, not drinking.\nFor drinking: only if truly no alternative, use full treatment chain.'},
      standing: {type:'result', style:'danger', text:'STANDING / FLOOD WATER — Extremely high risk.\n\nFlood water contains: sewage, agricultural runoff, industrial chemicals, decomposing organic matter, and often gasoline/oil.\n\nBoiling handles pathogens but NOT: heavy metals, agricultural chemicals, PFAS, petroleum products.\n\nUse only as LAST RESORT:\n1. Collect in container — let settle minimum 2 hours\n2. Filter through multiple cloth layers\n3. Filter through improvised charcoal filter if possible\n4. Add double dose bleach (16 drops/gallon) — wait 30 min\n5. Boil — 1 minute rolling boil\n\nDo NOT use flood water from near farms, industrial sites, or cities for drinking if any alternative exists.\nStanding water from rain (clean tarp/container) is much safer than flood water.\n\nDehydration vs. risk: if your only choice is flood water or severe dehydration, treat aggressively and drink.'},
      unknown: {type:'result', style:'warning', text:'UNKNOWN WATER SOURCE — Maximum treatment protocol.\n\nWhen source is unknown, use full treatment chain:\n\n1. Visual inspection: color, odor, floating material, sheen (oil), wildlife (if animals avoid it, be cautious)\n2. Sediment filter: cloth, coffee filter, or commercial filter\n3. Settling: 30 min if turbid\n4. Boil: 1 minute rolling boil — handles all biological threats\n5. Carbon filter: reduces chemical contamination if available\n\nImprovised test:\n- Iodine test: if water turns pink/red → may indicate organic contamination\n- Smell test: petroleum → do not use; sulfur → aerate first; bleach → safe to drink\n- Taste test (only after boiling): metallic, bitter, unusual → only drink if dying of thirst\n\nRemember: almost anything biological is killed by boiling. The bigger risk in the field is dehydration. When in doubt — boil it.'},
    }
  },

  // ─────────────────────────────────────────────────────────────────────────
  {
    id: 'food_safety_assessment',
    icon: '🥫',
    title: 'Food Safety Assessment',
    desc: 'Determine whether stored food, power-out refrigerator items, or foraged/hunted food is safe to eat.',
    start: 'start',
    nodes: {
      start: {type:'question', text:'What type of food are you assessing?', options:[
        {label:'Canned goods — commercial or home-canned', next:'canned_q1'},
        {label:'Refrigerated / frozen food (power outage)', next:'fridge_q1'},
        {label:'Dried / shelf-stable stored food', next:'dry_q1'},
        {label:'Foraged plants', next:'forage_q1'},
        {label:'Wild-caught meat / fish', next:'wildmeat_q1'},
      ]},
      canned_q1: {type:'question', text:'What does the can or jar look like?', options:[
        {label:'Normal — no swelling, rust, or damage', next:'canned_check'},
        {label:'Swollen, leaking, deeply dented (seam/end dent), or spurts liquid on opening', next:'canned_discard'},
        {label:'Home-canned jar — checking safety', next:'homecanned_q1'},
      ]},
      canned_check: {type:'result', style:'success', text:'CANNED GOODS — Likely safe, do a final check.\n\nSigns of safe canned food:\n- Can is not swollen, no leaks, no seam damage\n- No spurting when opened (pressure release = danger)\n- Odor: normal for that food. Sour/fermented smell without pickling intent = discard\n- Color: normal. Unusual colors (pink beans, blue meat) may be safe but verify\n- Texture: normal. Unusual sliminess = discard\n\nIf it passes all checks: heat to 165°F (simmering) before eating — extra insurance.\n\nDate concerns:\n- "Best by" dates on commercial cans = quality, not safety\n- Most commercial canned goods safe 5–10 years past date if stored properly\n- High-acid foods (tomatoes, fruit): 1.5–2 years optimal, still safe beyond\n- Low-acid foods (meat, vegetables): 3–5+ years\n\n"When in doubt, throw it out" applies — but don\'t waste good food on unfounded fear.'},
      canned_discard: {type:'result', style:'danger', text:'DISCARD — High botulism risk.\n\nSwollen, spurting, or leaking cans indicate gas production — the hallmark of Clostridium botulinum contamination.\n\nBotulism is odorless, tasteless, and extremely lethal. There is NO reliable way to detect it by smell/taste.\n\nDisposal:\n- Do NOT taste to test\n- Do NOT open further — spores can aerosolize\n- Seal entire can in plastic bag, then in another bag\n- Dispose outside — do NOT put in compost\n- Decontaminate any surfaces the can touched with bleach solution (1 tbsp per gallon)\n\nSymptoms of botulism (12–36h post-ingestion):\n- Double vision, drooping eyelids, difficulty speaking/swallowing\n- Descending paralysis\n- EMERGENCY — antitoxin must be given early\n\nNever risk botulism. Never heat to "make safe" — toxin is destroyed at 185°F for 5 min, but the risk of incomplete heating is too high.'},
      homecanned_q1: {type:'question', text:'How was it canned?', options:[
        {label:'Pressure canner — vegetables, meat, beans', next:'homecanned_pressure'},
        {label:'Water bath / steam — high-acid (fruit, tomatoes, pickles, jam)', next:'homecanned_waterbath'},
        {label:'Unsure of method', next:'homecanned_unknown'},
      ]},
      homecanned_pressure: {type:'result', style:'success', text:'HOME PRESSURE-CANNED — Safer method for low-acid foods.\n\nPressure canning reaches 240°F — sufficient to kill botulism spores.\n\nSafety check:\n- Lid sealed firmly (center does not flex when pressed)\n- No unusual odor when opened\n- No spurting, foam, or bubbling\n- Normal color and texture\n\nHeat before eating: bring to a boil for 10 minutes before serving (destroys any toxin if spores somehow survived)\n\nStorage: 1–5 years optimal. Beyond 5 years: inspect carefully and heat-process before eating.'},
      homecanned_waterbath: {type:'result', style:'warning', text:'HOME WATER-BATH CANNED — Safe for HIGH-ACID foods only.\n\nWater bath reaches only 212°F — cannot kill botulism spores.\nTherefore: ONLY safe for high-acid foods (pH <4.6): fruits, tomatoes (with added acid), pickles, jams.\n\nNEVER water-bath can: green beans, corn, meat, beans, potatoes, pumpkin — these are low-acid and require pressure canning.\n\nFor water-bath canned HIGH-ACID foods:\n- Lid sealed, no unusual odor → safe to eat cold or warm\n\nFor water-bath canned LOW-ACID foods:\n- Do NOT eat regardless of appearance\n- Discard safely (see botulism disposal guidance)\n\nSafety test: press lid center — if it flexes up/down, seal is broken → discard.'},
      homecanned_unknown: {type:'result', style:'danger', text:'HOME-CANNED, METHOD UNKNOWN — Do not eat low-acid foods.\n\nWithout knowing the method, you cannot verify botulism safety for low-acid foods.\n\nHigh-acid only (fruit, tomatoes with lemon juice, pickles, jam):\n- Check seal (lid does not flex)\n- Check odor (normal for that food)\n- If both pass: likely safe to eat\n\nLow-acid foods (vegetables, meat, beans, corn):\n- Cannot safely eat without pressure canning confirmation\n- Discard if uncertain\n\nWhen in true survival hunger situation:\n- Boil vigorously 10–15 minutes before eating (destroys toxin but not spores)\n- This is an emergency measure, not a safety guarantee'},
      fridge_q1: {type:'question', text:'How long has the power been out?', options:[
        {label:'Less than 4 hours', next:'fridge_safe'},
        {label:'4–24 hours', next:'fridge_check'},
        {label:'More than 24 hours', next:'fridge_risky'},
      ]},
      fridge_safe: {type:'result', style:'success', text:'POWER OUT <4 HOURS — Refrigerator food still safe.\n\nUnopened refrigerator holds 40°F for about 4 hours.\n\nActions:\n- Keep refrigerator CLOSED as much as possible\n- Use perishables in recommended order: meat/seafood first, then dairy/eggs, then produce\n- Consume or cook all meat within 2 hours of opening\n\nFreezer: stays frozen 24–48h unopened (1–2 days full, half-full = 24h). Do not open.\n\nSafety threshold: "40°F or below" — at 40°F+, bacteria multiply rapidly.\nIf you have a thermometer: check before eating. If >40°F for >2 hours = discard perishables.\n\nPriority for cooking first: raw chicken, seafood, ground meat, cut melons.'},
      fridge_check: {type:'result', style:'warning', text:'POWER OUT 4–24 HOURS — Use judgment.\n\nRefrigerator may have exceeded 40°F. Use temperature as guide:\n- If you have a fridge thermometer and it reads <40°F: still safe\n- Above 40°F for >2 hours: discard perishables\n\nHigh-risk (discard if uncertain):\n- Raw/cooked meat, poultry, seafood\n- Milk, soft cheeses, yogurt, eggs (cracked or room temp)\n- Cut fruits/vegetables, cooked pasta/rice, casseroles\n- Mayo-based salads (potato salad, coleslaw)\n\nGenerally safe even without refrigeration:\n- Hard cheeses (whole block, uncut)\n- Fruits and vegetables (intact, uncut)\n- Butter and margarine\n- Opened fruit juices\n- Peanut butter, jelly, ketchup, mustard, relish\n\n"When in doubt, throw it out" — food poisoning in a grid-down scenario is far worse than hunger.'},
      fridge_risky: {type:'result', style:'danger', text:'POWER OUT >24 HOURS — Assume perishables unsafe.\n\nRefrigerator contents should be treated as compromised.\n\nDISCARD without smelling/tasting:\n- All raw meat, poultry, seafood, eggs\n- All dairy (milk, soft cheese, sour cream, yogurt)\n- All cooked leftovers\n- All cut fruits/vegetables\n\nMay be SAFE (inspect individually):\n- Whole uncut fruits/vegetables (smell and visually check)\n- Hard cheeses in original wax or sealed packaging\n- Butter (if no obvious mold)\n- Commercial condiments in sealed bottles (ketchup, mustard, etc.)\n\nFreezer: items still containing ice crystals may be refrozen or cooked immediately.\nFreezer items that have thawed completely: cook and eat immediately or discard.\n\nDo NOT rely on smell test for meat — many pathogens (Salmonella, E. coli) are odorless.'},
      dry_q1: {type:'question', text:'What type of dried/shelf-stable food?', options:[
        {label:'Commercial sealed (mylar, #10 can, vacuum sealed)', next:'dry_commercial'},
        {label:'Opened bag/container, been stored for a while', next:'dry_opened'},
        {label:'Grains, rice, beans from bulk storage', next:'dry_grain'},
      ]},
      dry_commercial: {type:'result', style:'success', text:'COMMERCIALLY SEALED DRY FOOD — Long shelf life.\n\nMylar bags with oxygen absorbers, #10 cans: properly stored = 5–25+ years\n\nInspect before opening:\n- Mylar/sealed bag: no holes, tears, or punctures. Bag should be rigid (vacuum) or show slight inward pressure (O2 absorber working)\n- #10 can: check for rust through the can wall, severe dents at seams\n\nAfter opening:\n- Smell: should smell normal for that food type\n- Inspect for insects: weevils, flour beetles — check for movement or webbing\n- Check for moisture damage: clumping, off-color, mold\n\nIf insects present: sift out (food still edible, extra protein), or freeze for 3 days to kill larvae.\nIf mold present on grain/legumes: discard entire batch — mold produces mycotoxins that survive cooking.\nRancid fat smell (in whole grains, nuts): still edible but reduced nutrition and poor taste.'},
      dry_opened: {type:'result', style:'warning', text:'OPENED DRY STORAGE — Check carefully.\n\nOnce opened, dry storage is vulnerable to:\n- Moisture → mold\n- Oxygen → rancidity in fats\n- Pests → weevils, mice, moths\n\nInspect:\n1. Look for webbing, insects, or droppings\n2. Smell: musty or sour = mold risk; rancid/paint-thinner = oxidized fats\n3. Check for clumping (moisture ingress)\n\nDecision:\n- Insects only (no mold): sift and use — insects and larvae are edible protein\n- Light mold on surface of grain pile: discard top layer, inspect deeper — if mold throughout, discard all\n- Mouse/rodent contamination: discard entire container (hantavirus risk from droppings)\n- Rancid: safe to eat but unpalatable; cook with strong spices\n\nFor prevention: Mylar bags + oxygen absorbers, bay leaves deter insects, keep dry and cool.'},
      dry_grain: {type:'result', style:'success', text:'BULK GRAIN/RICE/BEAN STORAGE — Assess by inspection.\n\nStorage indicators:\n- Properly stored (cool, dry, sealed): wheat 25+ yrs, white rice 25–30 yrs, beans 25+ yrs, oats 4 yrs, cornmeal 1–2 yrs\n- White rice outlasts brown rice (brown has oils that go rancid)\n\nInspect:\n1. Pour small amount, spread on white surface\n2. Look for: insects, webbing, droppings, clumping\n3. Smell: earthy is ok; musty, sour, or ammonia = problem\n4. Look for grain discoloration: pink/red = mold toxin (discard)\n\nIf good after inspection: rinse, soak 8–24h for legumes, then cook thoroughly.\n\nNixtamalization for corn: boil in lime water (calcium hydroxide or wood ash water) — activates B vitamins, prevents pellagra. Critical for corn-heavy diets.'},
      forage_q1: {type:'question', text:'How confident are you in the plant identification?', options:[
        {label:'100% positive ID — multiple cross-referenced sources', next:'forage_sure'},
        {label:'Mostly sure but some uncertainty', next:'forage_unsure'},
        {label:'Unknown plant or learning to identify', next:'forage_unknown'},
      ]},
      forage_sure: {type:'result', style:'success', text:'KNOWN EDIBLE PLANT — Safe if prepared correctly.\n\nFor confidently identified wild edibles:\n\nPreparation reminders by type:\n- Acorns: leach tannins (soak, change water 3–5x, or boil with multiple water changes) — raw = very bitter and toxic\n- Pokeweed: leaves ONLY when very young and small, boil with 3 water changes — roots/berries lethal\n- Elderberries: cook before eating — raw seeds contain cyanogenic glycosides\n- Fiddlehead ferns: boil 10+ minutes — raw can cause GI illness\n- Nettles: cook, dry, or blend — heat neutralizes sting\n- Dandelion, plantain, lamb\'s quarters, wood sorrel: generally safe raw\n\nHarvesting rules:\n- 100+ feet from roads (lead/petroleum accumulation)\n- Avoid areas with pesticide/herbicide use\n- Away from waterways in flood-prone areas (contamination)\n- Don\'t over-harvest — leave 2/3 for regrowth and wildlife'},
      forage_unsure: {type:'result', style:'warning', text:'UNCERTAIN IDENTIFICATION — Do not eat without confirmation.\n\nRules for uncertain plants:\n1. Do NOT eat — misidentification kills\n2. Cross-reference at least 3 sources: field guide + regional app + expert confirmation\n3. Look for complete plant: root, stem, leaf, flower, fruit, smell, habitat, season\n\nDeadly lookalikes to know:\n- Wild carrot (Queen Anne\'s Lace) vs. Poison hemlock — one kills; hemlock has purple spots on stem, no carrot smell\n- Wild garlic vs. Death camas — garlic smell is definitive\n- Elderberry vs. Water hemlock — always check habitat and stem cross-section\n- Morels vs. False morels — morel cap is fully attached; false morel has saddle shape\n- Chanterelle vs. Jack-o\'lantern — chanterelle has forking ridges, grows from soil; jack-o\'lantern has gills, grows from wood\n\nIn doubt: starve one more day. Starvation takes weeks; plant toxin can kill in hours.'},
      forage_unknown: {type:'result', style:'danger', text:'UNKNOWN PLANT — Do not eat.\n\nAlways rule when foraging: "When in doubt, don\'t."\n\nUniversal edibility test (last resort, takes 8 hours):\n1. Separate plant into parts (root, stem, leaf, flower, fruit)\n2. Test ONE part, ONE at a time\n3. Rub on wrist, wait 15 min — if rash, burning, numbness: discard\n4. Hold small piece to lips, wait 3 min — if reaction: discard\n5. Chew pea-sized piece, hold in mouth 15 min, spit — if reaction: discard\n6. Swallow pea-sized piece, wait 8 hours (eat nothing else, drink only water)\n7. If no reaction: that part of that plant may be safe in limited quantities\n\nThis test does NOT work for: mushrooms (skip mushroom edibility tests — use a field guide or don\'t eat them).\n\nEat a small portion first. Wait 24 hours before eating more.\nCaloric return rarely worth the risk of misidentification.'},
      wildmeat_q1: {type:'question', text:'What type of wild animal?', options:[
        {label:'Large game (deer, elk, wild boar)', next:'game_large'},
        {label:'Small game (rabbit, squirrel, fowl)', next:'game_small'},
        {label:'Fish or freshwater shellfish', next:'fish_q1'},
      ]},
      game_large: {type:'result', style:'warning', text:'LARGE GAME — Assess and prepare correctly.\n\nField assessment:\n- Healthy-appearing at time of kill (alert, normal movement)\n- No visible tumors, lesions, spots on organs, or unusual organ color\n- Stomach/intestinal contents not ruptured during field dressing (contaminates meat)\n\nChronic Wasting Disease (CWD) — deer/elk/moose:\n- No evidence of transmission to humans, but precaution advised\n- Wear gloves when field dressing\n- Avoid eating brain, spinal cord, eyes, lymph nodes, spleen\n- Bone-in cuts: bone marrow may contain prions — remove before cooking\n\nWild boar / feral pig:\n- HIGH trichinosis risk — must cook to 160°F internal (no pink meat)\n- Wear gloves: brucellosis transmission through cuts during field dressing\n- Do NOT eat raw or undercooked\n\nCooking temperature: 160°F for game (well-done) kills most pathogens. 165°F for poultry.\nField cooling: gut and cool to <40°F within 2–4 hours to prevent bacterial growth.'},
      game_small: {type:'result', style:'warning', text:'SMALL GAME — Specific disease risks.\n\nRabbit / Hare:\n- Tularemia risk (Francisella tularensis): wear gloves when field dressing\n- Avoid during late summer (hot weather = higher parasite load)\n- Do NOT eat rabbit with visible spots/lesions on liver\n- Cook thoroughly to 165°F — no pink meat\n- "Rabbit starvation" (protein poisoning): supplement with fat/carbs if rabbit is primary calorie source\n\nSquirrel:\n- Generally safe; same tularemia precautions\n- Botfly larvae (warbles): gross but harmless — remove, cook remaining meat\n\nWild Fowl / Birds:\n- Avian influenza risk: wear mask if handling visibly sick birds\n- Cook to 165°F internal — thoroughly\n- Do NOT eat scavenger birds (vultures, crows) — concentrate toxins\n\nAll small game:\n- Intestinal parasites: thorough cooking (165°F) destroys all\n- Trichinella in some species — 160°F minimum'},
      fish_q1: {type:'question', text:'Where was the fish/shellfish caught?', options:[
        {label:'Open clean water — river, lake, ocean, away from industry', next:'fish_clean'},
        {label:'Near town, downstream from industry, or under advisory', next:'fish_polluted'},
      ]},
      fish_clean: {type:'result', style:'success', text:'FISH FROM CLEAN WATER — Safe with standard cooking.\n\nField assessment:\n- Fresh fish: clear eyes, bright red gills, firm flesh, mild ocean/river smell\n- Avoid: cloudy eyes, grey/brown gills, soft mushy flesh, strong ammonia smell\n\nPreparation:\n- Cook to 145°F internal (flesh flakes and is opaque)\n- Anisakis worms: common in many ocean fish — kill by cooking to 145°F or freezing at -4°F for 7 days\n- Filleting: inspect fillets for worms (small white/translucent coils) — remove if found, rest is safe\n\nFreshwater fish (no cooking):\n- Tapeworms in pike, perch, walleye — thorough cooking eliminates risk\n- Raw freshwater fish has high parasite risk — always cook\n\nFreshwater shellfish (mussels, clams in rivers):\n- Much higher contamination risk than ocean shellfish\n- Cook thoroughly: steam until open (>165°F)\n- Do NOT eat those that do not open during cooking'},
      fish_polluted: {type:'result', style:'danger', text:'FISH FROM POLLUTED WATER — High bioaccumulation risk.\n\nFish bioaccumulate: mercury, PCBs, lead, PFAS, pesticides — cooking does NOT remove these.\n\nAvoid eating if water is:\n- Under consumption advisory (posted at boat ramps, fish advisory websites)\n- Downstream from mines, factories, agriculture\n- Known for algae blooms (cyanotoxins — especially in mussels/shellfish)\n\nIf you must eat (survival):\n- Remove skin and visible fat (bioaccumulation concentrates in fat)\n- Smaller fish accumulate fewer toxins than large predators\n- Avoid bottom-feeders (catfish, carp) from polluted water\n- Do NOT eat shellfish from polluted or closed waters\n\nParalytic Shellfish Poisoning (PSP/red tide):\n- Shellfish during algae bloom can be toxic regardless of cooking\n- Numbness of lips/tongue within 30 min = PSP — no antidote, supportive care only'},
    }
  },

  // ─────────────────────────────────────────────────────────────────────────
  {
    id: 'hypothermia_response',
    icon: '🥶',
    title: 'Hypothermia Response',
    desc: 'Assess cold exposure and guide treatment from mild shivering through severe hypothermia.',
    start: 'start',
    nodes: {
      start: {type:'question', text:'Is the patient conscious and responding?', options:[
        {label:'Yes — alert, shivering, able to speak', next:'conscious_q1'},
        {label:'Confused, slow to respond, or combative', next:'altered_q1'},
        {label:'Unresponsive — difficult to rouse', next:'severe_q1'},
        {label:'No pulse detectable', next:'pulseless'},
      ]},
      conscious_q1: {type:'question', text:'Is the patient actively shivering?', options:[
        {label:'Yes — shivering vigorously (good sign)', next:'mild_result'},
        {label:'Shivering has stopped — patient feels warm/numb', next:'shiver_stop'},
      ]},
      mild_result: {type:'result', style:'success', text:'MILD HYPOTHERMIA — Core temp 32–35°C (89.6–95°F)\n\nActive shivering is good — the body is still generating heat.\n\nImmediate actions:\n1. Move to shelter — stop all heat loss FIRST\n2. Remove ALL wet clothing (wet clothes conduct heat away from body 25× faster)\n3. Insulate from cold ground (critical — ground conducts heat away rapidly)\n4. Wrap in dry blankets or sleeping bag\n5. Apply chemical heat packs to armpits, groin, back of neck (high blood flow areas)\n   — DO NOT apply directly to skin; use cloth barrier\n6. Warm sweet drinks if patient is fully conscious and swallowing safely\n7. High-calorie food (shivering burns enormous calories)\n8. Dry hat — 20–30% of heat loss from an uncovered head\n\nDo NOT:\n- Massage extremities (drives cold blood to core)\n- Give alcohol (causes vasodilation, accelerates heat loss)\n- Have patient exercise (can trigger cardiac arrest)\n\nMonitor: reassess every 15 min. If shivering stops and patient improves → good. If shivering stops and patient worsens → see moderate protocol.'},
      shiver_stop: {type:'result', style:'danger', text:'SHIVERING STOPPED — DANGER SIGN\n\nWhen shivering stops WITHOUT recovery, it means the body can no longer generate heat. Core temp is likely below 32°C (89.6°F).\n\nThis is now MODERATE or SEVERE hypothermia. Do NOT assume the patient is "warming up."\n\nSigns confirming worsening: rigidity, confusion, slurred speech, ataxia, very slow pulse.\n\nSee MODERATE HYPOTHERMIA protocol:\n1. Handle GENTLY — cardiac arrest risk from rough movement\n2. Keep HORIZONTAL — do NOT sit up or stand patient\n3. Remove wet clothing carefully, insulate fully\n4. Passive rewarming only — do NOT apply heat directly\n5. Warm humidified O2 if available\n6. Monitor pulse (may be very slow — check for 60 full seconds before declaring absent)\n7. EVACUATE as highest priority\n\nDo NOT attempt active rewarming (hot water, heating pad directly on skin) — can cause vasodilation and core temperature drop.'},
      altered_q1: {type:'question', text:'Is the patient able to walk with assistance?', options:[
        {label:'Can walk with support, coherent but confused', next:'moderate_result'},
        {label:'Cannot walk, incoherent, or combative', next:'severe_q1'},
      ]},
      moderate_result: {type:'result', style:'warning', text:'MODERATE HYPOTHERMIA — Core temp 28–32°C (82–89.6°F)\n\nThis is a medical emergency. The heart is at serious risk of arrhythmia.\n\nCritical rules:\n1. HANDLE WITH EXTREME CARE — any rough movement can cause ventricular fibrillation\n2. Horizontal position ONLY — do NOT allow to stand or walk\n3. Remove wet clothing gently, one piece at a time\n4. Passive external rewarming: dry blankets, insulation, vapor barrier\n5. Warm humidified oxygen if available\n6. Warm IV saline (42°C) if IV access and hospital-grade equipment available\n7. Cardiac monitoring if available — watch for J-wave (Osborn wave), AF, bradycardia\n\nDo NOT:\n- Apply external heat directly (rewarming shock)\n- Give anything by mouth (aspiration risk)\n- Rub or massage\n- Allow to sit up\n\nEvacuation: This patient MUST reach hospital with ECMO/cardiopulmonary bypass capability for definitive treatment. Do not delay transport for field rewarming.'},
      severe_q1: {type:'question', text:'Can you detect any pulse (check for 60 full seconds at carotid)?', options:[
        {label:'Yes — slow, faint pulse present', next:'severe_pulse'},
        {label:'No pulse detected after 60 seconds', next:'pulseless'},
      ]},
      severe_pulse: {type:'result', style:'danger', text:'SEVERE HYPOTHERMIA WITH PULSE — Core temp <28°C\n\nExtremely fragile state. The heart is maintaining a rhythm but any disturbance can cause cardiac arrest.\n\nImmediate actions:\n1. ABSOLUTE MINIMAL MOVEMENT — every touch is a potential arrhythmia trigger\n2. Do NOT initiate CPR (pulse is present — even if very slow)\n3. Horizontal position at all times\n4. Full insulation, vapor barrier\n5. Warm humidified O2 if available\n6. Keep airway open — recovery position if at all possible without movement\n7. Monitor pulse continuously\n8. If pulse stops — begin CPR immediately (see pulseless protocol)\n\nField rewarming is NOT appropriate — it can vasodilate peripheral vessels and cause core temp to DROP further (afterdrop).\n\nThis patient requires ECMO or cardiopulmonary bypass for safe rewarming. Evacuate immediately by most available means.'},
      pulseless: {type:'result', style:'danger', text:'PULSELESS HYPOTHERMIC PATIENT — BEGIN CPR\n\n"No one is dead until they are warm and dead."\n\nHypothermic cardiac arrest can survive after HOURS of CPR and normal-looking rigor mortis due to cold preservation of brain cells.\n\nCPR protocol:\n1. Begin CPR immediately — 30:2 compressions:breaths\n2. Do NOT stop for any reason until:\n   a. Core temperature reaches ≥32°C (89.6°F), OR\n   b. Patient is obviously dead (decapitation, lividity, frozen solid), OR\n   c. Personnel are exhausted\n3. Continue at least 60+ minutes — longer if resources allow\n4. AED/defibrillation: ONE shock attempt. If no response, continue CPR — heart may not respond until warmer\n5. Epinephrine: withhold or double interval (give every 6–10 min instead of 3–5 min) — less effective in hypothermia\n\nRewarming during CPR:\n- Warm humidified O2 if ventilating\n- Warm IV saline (42°C) through IO/IV access\n- Warm water immersion (if no trauma) at 40–42°C\n- Hospital: ECMO is only definitive rewarming for cardiac arrest\n\nDo not give up. Documented survival after 6+ hours CPR in hypothermia.'},
    }
  },

  // ─────────────────────────────────────────────────────────────────────────
  {
    id: 'chest_trauma',
    icon: '🫁',
    title: 'Chest Trauma Assessment',
    desc: 'Evaluate penetrating or blunt chest injuries and identify life-threatening conditions requiring immediate intervention.',
    start: 'start',
    nodes: {
      start: {type:'question', text:'What type of chest trauma occurred?', options:[
        {label:'Penetrating — gunshot, stabbing, impalement', next:'penetrating_q1'},
        {label:'Blunt — crash, fall, crushing force', next:'blunt_q1'},
        {label:'Patient is deteriorating rapidly — any mechanism', next:'rapid_deterirate'},
      ]},
      rapid_deterirate: {type:'question', text:'Which life threat best describes the current state?', options:[
        {label:'Absent or markedly decreased breath sounds one side + shock', next:'tension_ptx'},
        {label:'Open wound in chest "sucking" air', next:'open_ptx'},
        {label:'Muffled heart sounds + distended neck veins + shock (Beck\'s triad)', next:'tamponade'},
        {label:'Massive bleeding + shock + normal breath sounds', next:'hemothorax'},
      ]},
      penetrating_q1: {type:'question', text:'Is there an open wound / hole in the chest wall?', options:[
        {label:'Yes — visible wound, possibly sucking air', next:'open_ptx'},
        {label:'No open wound but decreasing breath sounds / shock', next:'tension_ptx'},
        {label:'Near midline — concern for heart or great vessels', next:'cardiac_q1'},
      ]},
      open_ptx: {type:'result', style:'danger', text:'OPEN PNEUMOTHORAX (Sucking Chest Wound)\n\nAir is entering the pleural space directly through the chest wall, collapsing the lung.\n\nImmediate treatment:\n1. Seal wound with a vented chest seal (Hyfin, HyFin, or NarrowCo) — apply over wound during EXHALATION\n2. If no chest seal: improvise with plastic bag, glove, or foil — tape 3 sides, leave 1 open (flutter valve effect)\n3. Do NOT use non-vented occlusive dressing — can convert to tension pneumothorax\n4. Position: sitting upright if possible, injured side down\n5. O2 if available\n6. Monitor continuously for tension pneumothorax — if deteriorates after sealing (hypotension, absent breath sounds on that side) → needle decompression immediately\n\nFor large defects (>3cm): air preferentially enters through the wound rather than trachea. Priority to seal.\n\nNeedle decompression site (if tension develops):\n- 14g × 3.25" needle\n- 2nd ICS mid-clavicular line OR 4th–5th ICS anterior axillary line'},
      tension_ptx: {type:'result', style:'danger', text:'TENSION PNEUMOTHORAX — IMMEDIATELY LIFE-THREATENING\n\nAir accumulates under pressure in pleural space, compressing the mediastinum and great vessels.\n\nClassic signs (may not all be present):\n- Absent or markedly decreased breath sounds (one side)\n- Hypotension / shock\n- Distended neck veins (JVD)\n- Tracheal deviation AWAY from affected side (late sign)\n- Respiratory distress, hypoxia\n\nNeedle Decompression — DO IT NOW:\n1. Identify landmark: 2nd intercostal space, mid-clavicular line (preferred), OR\n   4th–5th ICS, anterior axillary line (avoids breast tissue, obese patients)\n2. Use 14-gauge × 3.25" needle-over-catheter\n3. Insert OVER the TOP of the lower rib (avoid neurovascular bundle)\n4. Advance until rush of air, remove needle, leave catheter\n5. Reassess: improvement = improved breath sounds, BP stabilizes\n6. Finger thoracostomy if needle decompression fails (small incision + finger sweep)\n\nDefinitive treatment: chest tube (24–28 Fr) — hospital required.\nAnticipate repeat decompression — catheters kink within 2 hours.'},
      blunt_q1: {type:'question', text:'What is the primary concern with the blunt trauma?', options:[
        {label:'Rib fractures — pain with breathing, point tenderness', next:'rib_q1'},
        {label:'Sternal fracture or chest-wide pain — cardiac concern', next:'cardiac_contusion'},
        {label:'Decreasing breath sounds + shock after blunt trauma', next:'hemothorax'},
        {label:'Normal breath sounds but worsening respiratory distress', next:'flail_q1'},
      ]},
      rib_q1: {type:'question', text:'How many ribs appear to be fractured (by palpation)?', options:[
        {label:'1–2 ribs — isolated fractures', next:'rib_simple'},
        {label:'3+ ribs OR rib fractures in 2+ places (segment moves paradoxically)', next:'flail_q1'},
        {label:'Elderly patient with even 1–2 rib fractures', next:'rib_elderly'},
      ]},
      rib_simple: {type:'result', style:'success', text:'SIMPLE RIB FRACTURES (1–2 ribs)\n\nManagement:\n1. Analgesia is the most important treatment — pain causes splinting → atelectasis → pneumonia\n   - Ibuprofen 600mg q6–8h + Acetaminophen 1000mg q6h (alternating)\n   - Consider rib belt / elastic bandage if helps pain (controversial — can restrict breathing)\n2. Deep breathing exercises every 1–2 hours (prevents pneumonia)\n3. Incentive spirometry if available\n4. No chest binding tightly — restricts tidal volume\n\nWARNING signs requiring re-evaluation:\n- Worsening shortness of breath\n- O2 sat dropping\n- Fever after 48h (pneumonia)\n- Increased pain spreading\n\nRibs 1–3: High energy injury — suspect great vessel injury. Ribs 9–12: Lower ribs — suspect liver (right), spleen (left) injury with blunt trauma.'},
      rib_elderly: {type:'result', style:'warning', text:'RIB FRACTURES IN ELDERLY — Higher Risk\n\nElderly patients have 5× higher mortality from rib fractures due to:\n- Reduced pulmonary reserve\n- Underlying lung disease (COPD)\n- Brittle ribs — fractures more likely to be multiple\n- Poor pain tolerance causing splinting → rapid pneumonia\n\nManagement:\n1. Aggressive analgesia — pain control is paramount\n   - NSAID + Acetaminophen alternating schedule\n   - Opioids if available (morphine 2–4mg IV) — closely monitor respiratory rate\n2. Supplemental O2 to maintain sat >94% if available\n3. Elevate head of bed 30–45°\n4. Deep breathing q1–2h — coach the patient\n5. AVOID sedating medications that reduce respiratory drive (benzodiazepines)\n\nEvacuate: elderly patients with 3+ rib fractures have 30% mortality without hospital care. These patients should be evacuated at first opportunity regardless of stable appearance.'},
      flail_q1: {type:'result', style:'danger', text:'FLAIL CHEST — Life-Threatening\n\nWhen 3+ adjacent ribs are fractured in 2+ places, a free-floating segment moves PARADOXICALLY — inward with breathing, outward with exhalation.\n\nThis impairs ventilation and causes severe underlying lung contusion.\n\nSigns:\n- Paradoxical chest wall movement (segment moves opposite to rest of chest)\n- Crepitus over large area\n- Severe respiratory distress, hypoxia\n- Severe pain\n\nTreatment:\n1. Position: injured side DOWN (splits the flail segment)\n2. O2 — high flow, target sat >94%\n3. Positive pressure ventilation if available (BVM or ventilator)\n4. Analgesia — aggressive (can use opioids — ketamine preferred if available)\n5. DO NOT: splint the chest wall externally — restricts movement\n6. IV access, fluid resuscitation\n\nDefinitive: mechanical ventilation (intubation) is the standard of care. Field management is supportive only. EVACUATE urgently.'},
      cardiac_q1: {type:'question', text:'Is there shock (hypotension, rapid pulse) with muffled heart sounds or distended neck veins?', options:[
        {label:'Yes — Beck\'s triad: hypotension + muffled sounds + JVD', next:'tamponade'},
        {label:'No — penetrating near heart, hemodynamically stable', next:'cardiac_obs'},
      ]},
      cardiac_obs: {type:'result', style:'warning', text:'PENETRATING WOUND NEAR HEART — Observe Closely\n\nAll penetrating wounds to the "cardiac box" (clavicles to costal margins, nipple line to nipple line) must be assumed to have cardiac involvement until proven otherwise.\n\nImmediate actions:\n1. IV access × 2, cardiac monitoring if available\n2. Serial assessment every 5–10 minutes: BP, pulse, breath sounds, neck veins\n3. Do NOT probe the wound\n4. Treat any tension pneumothorax or hemothorax if signs develop\n5. Gentle fluid resuscitation (250mL boluses, avoid over-resuscitation)\n\nDeveloping tamponade signs (worsening JVD, muffled heart sounds, dropping BP):\n→ See Cardiac Tamponade protocol\n\nSurgical repair is the only definitive treatment for cardiac laceration. Evacuate immediately — transport time is critical.'},
      tamponade: {type:'result', style:'danger', text:'CARDIAC TAMPONADE — IMMEDIATELY LIFE-THREATENING\n\nBlood accumulating in the pericardial sac compresses the heart, preventing filling.\n\nBeck\'s Triad (classic signs):\n- Hypotension (falling BP)\n- Distended neck veins (JVD)\n- Muffled / distant heart sounds\n\nOther signs: pulsus paradoxus (BP drops >10 mmHg with inspiration), tachycardia, narrowed pulse pressure.\n\nField treatment — Pericardiocentesis (last resort if no other option):\n1. 18g × 3.5" spinal needle + large syringe\n2. Insert at 45° angle at left xiphocostal angle, aiming toward left shoulder\n3. Advance while aspirating — blood indicates pericardial space\n4. Aspirate 10–20mL (even small amount provides significant relief)\n5. NOTE: if blood re-clots in syringe = pericardial blood (defibrinated). Freely flowing blood may be cardiac chamber.\n\nDefinitive: open surgical drainage. Pericardiocentesis is a bridge only.\n\nFluid resuscitation: 250–500mL bolus may temporize by increasing filling pressure.\nEvacuate immediately — this patient needs an OR.'},
      hemothorax: {type:'result', style:'warning', text:'HEMOTHORAX — Blood in Pleural Space\n\nBlood accumulating in the pleural cavity compresses the lung and causes blood loss.\n\nSmall hemothorax (<300mL): Often resolves spontaneously. Monitor.\nModerate (300–1500mL): May need drainage.\nMassive (>1500mL or ongoing): Life-threatening hemorrhagic shock.\n\nSigns:\n- Decreased breath sounds (usually at the BASE of the lung)\n- Dullness to percussion (vs resonance in pneumothorax)\n- Hypotension, tachycardia (blood loss)\n- Decreased O2 sat\n\nField treatment:\n1. IV access × 2 large bore\n2. Fluid resuscitation — permissive hypotension (SBP 80–90): do not over-resuscitate\n3. Supplemental O2\n4. Position: head elevated 30–45° if tolerated\n\nDefinitive: chest tube (32–36 Fr) to drain blood — hospital/surgical setting.\nField chest tube: only if trained and supplies available — risk of infection, re-bleeding.\n\nMassive hemothorax: source is likely a major vessel or pulmonary hilar structure — surgical hemorrhage control required. Evacuate IMMEDIATELY.'},
      cardiac_contusion: {type:'result', style:'warning', text:'MYOCARDIAL CONTUSION / STERNAL FRACTURE\n\nBlunt force to the sternum or anterior chest can bruise the heart muscle, causing arrhythmias and pump failure.\n\nClinical picture:\n- Sternal fracture: point tenderness over sternum, crepitus, step deformity\n- Chest wall bruising (seat belt sign, steering wheel imprint)\n- New arrhythmias (most common: PVCs, right bundle branch block)\n- Chest pain disproportionate to external injuries\n- Hypotension without blood loss explanation\n\nManagement:\n1. Cardiac monitoring — watch for ventricular arrhythmias for 24–48h\n2. Rest, gentle fluid resuscitation\n3. Analgesia (avoid NSAIDs in suspected cardiac injury — can worsen)\n4. 12-lead ECG if available; troponin if lab available\n\nHigh suspicion cases: sternal fracture + hypotension + new ECG changes = consider right ventricular failure.\n\nField: supportive care, monitoring, pain control. Hospital required for imaging, monitoring, and management of significant contusion.'},
    }
  },

  // ── SNAKEBITE / ANIMAL ENVENOMATION ──────────────────────────────
  {
    id: 'envenomation',
    title: 'Snakebite / Envenomation',
    icon: '🐍',
    description: 'Snakebite and venomous animal sting management',
    nodes: {
      start: {type:'question', text:'What type of envenomation?', options:[
        {label:'Snake bite — identified or suspected venomous', next:'snake_q1'},
        {label:'Scorpion sting', next:'scorpion_q1'},
        {label:'Spider bite (black widow / brown recluse)', next:'spider_q1'},
        {label:'Marine envenomation (jellyfish, stingray, sea urchin)', next:'marine_q1'},
      ]},

      // SNAKE
      snake_q1: {type:'question', text:'Is the patient showing systemic signs of envenomation? (facial swelling, difficulty breathing, chest tightness, severe swelling progressing up limb, altered consciousness, excessive bleeding from bite site)', options:[
        {label:'Yes — systemic symptoms present', next:'snake_severe'},
        {label:'No systemic symptoms — local swelling/pain only', next:'snake_local'},
        {label:'Dry bite — no symptoms at all', next:'snake_dry'},
      ]},
      snake_severe: {type:'result', style:'danger', text:'SEVERE SNAKEBITE ENVENOMATION — Antivenom Required\n\nImmediate actions (first 15 minutes):\n1. Lay patient flat — do NOT elevate the bitten limb (worsens systemic spread)\n2. Immobilize the bitten limb with a splint or sling — keep it at heart level\n3. Remove all jewelry, rings, watches from the bitten extremity\n4. IV access — 2 large-bore lines if possible\n5. Mark advancing edge of swelling with pen + time every 15 minutes\n\nDO NOT:\n- Cut and suck the wound (ineffective, causes infection)\n- Apply a tourniquet (causes tissue death)\n- Apply ice (causes ischemia)\n- Give alcohol\n- Use electric shock "therapy"\n\nPressure immobilization bandage (PIB):\n- USE ONLY for neurotoxic snakes (coral snakes, mambas, sea snakes)\n- DO NOT use for hemotoxic/cytotoxic snakes (rattlesnakes, copperheads) — traps tissue-destroying venom\n\nAntivenom: This patient requires antivenom. Transport to hospital URGENTLY.\n- Take a photo of the snake from a safe distance if possible — DO NOT attempt to catch it\n- Onset of respiratory failure or anaphylaxis: epinephrine 0.3–0.5mg IM (EpiPen) if available\n\nMonitor: airway, breathing, circulation, neurologic status, urine output (dark urine = hemolysis/rhabdomyolysis)'},
      snake_local: {type:'result', style:'warning', text:'LOCAL ENVENOMATION — Monitor for Progression\n\nLocal envenomation (pain, swelling, bruising at bite site without systemic spread) can progress to severe within hours.\n\nImmediate care:\n1. Immobilize bitten limb at heart level — do NOT elevate\n2. Remove constrictive jewelry/clothing from bitten limb\n3. Mark swelling edge with pen every 15–30 minutes\n4. IV access if available\n5. Analgesia: acetaminophen or ibuprofen (avoid aspirin — may worsen bleeding)\n\nDO NOT apply tourniquet, cut/suck, apply ice.\n\nWatch for progression to severe (see severe protocol if ANY develop):\n- Swelling advancing beyond the bite site rapidly\n- Facial/tongue swelling\n- Chest tightness, difficulty breathing\n- Nausea/vomiting, dizziness\n- Bleeding from bite site or elsewhere\n\nEvacuation:\n- All venomous snakebites require medical evaluation even if symptoms appear mild\n- Symptoms may be delayed up to 12 hours\n- Copperhead (USA): often local only, rarely requires antivenom — still evacuate\n- Rattlesnake/Water moccasin: higher risk of hemotoxicity — evacuate promptly'},
      snake_dry: {type:'result', style:'success', text:'DRY BITE — No Venom Injected\n\nApproximately 20–30% of venomous snakebites are "dry bites" where no venom is injected.\n\nHowever, you CANNOT confirm a dry bite in the field. Symptoms may be delayed up to 12 hours.\n\nManagement:\n1. Treat as potential envenomation for at least 6–8 hours\n2. Immobilize the limb, remove jewelry\n3. Mark bite site and monitor for swelling progression\n4. Watch for ANY systemic symptoms\n5. Do NOT discharge or allow patient to sleep unsupervised for 6+ hours\n\nAll snakebites require medical evaluation regardless of initial symptom absence.\nEvacuate for observation and possible antivenom.'},

      // SCORPION
      scorpion_q1: {type:'question', text:'Are systemic symptoms present? (muscle twitching, difficulty swallowing, blurred vision, excessive salivation, hypertension, respiratory distress)', options:[
        {label:'Yes — systemic/neurological symptoms', next:'scorpion_severe'},
        {label:'No — local pain, redness only', next:'scorpion_local'},
      ]},
      scorpion_severe: {type:'result', style:'danger', text:'SEVERE SCORPION ENVENOMATION — Antivenom / ICU\n\nBark scorpion (USA Southwest) and many tropical species can cause life-threatening neurotoxicity.\n\nSystemic signs: uncontrolled muscle twitching, roving eye movements, drooling, difficulty swallowing, airway compromise, hypertensive crisis, respiratory failure.\n\nRisk: Highest in children <6 years and elderly.\n\nField management:\n1. Airway management — positioning, jaw thrust if needed; prepare for intubation\n2. Benzodiazepines for seizures/muscle twitching: midazolam 0.05–0.1mg/kg IV or diazepam 0.1–0.2mg/kg IV if available\n3. IV access, monitoring\n4. Keep patient calm and still — agitation worsens symptoms\n5. Analgesia (opioids IV)\n\nAntivenom is available for Centruroides (bark scorpion) in the USA — hospital/ED only.\nEvacuate IMMEDIATELY — pediatric and elderly patients can die within hours.'},
      scorpion_local: {type:'result', style:'success', text:'LOCAL SCORPION STING — Symptomatic Care\n\nLocal pain without systemic symptoms: self-limiting, resolves in hours to days.\n\nCare:\n1. Wash the sting site with soap and water\n2. Apply cool (NOT ice-cold) compress for 15–20 minutes\n3. Analgesia: ibuprofen 400–600mg, or acetaminophen 1000mg\n4. Elevate the extremity\n5. Observe for 4–6 hours for systemic symptoms\n\nWatch for systemic signs (see severe protocol if they develop).\n\nChildren: lower threshold — a bark scorpion sting in a child under 6 is potentially severe even without initial systemic signs. Evacuate.'},

      // SPIDER
      spider_q1: {type:'question', text:'What type of spider?', options:[
        {label:'Black widow (shiny black, red/orange hourglass)', next:'black_widow'},
        {label:'Brown recluse (violin-shaped marking, USA Midwest/South)', next:'brown_recluse'},
        {label:'Unknown spider — local wound with possible necrosis', next:'brown_recluse'},
      ]},
      black_widow: {type:'result', style:'warning', text:'BLACK WIDOW SPIDER BITE\n\nVenom is a neurotoxin (alpha-latrotoxin) causing massive neurotransmitter release → muscle cramping.\n\nSigns (may be delayed 30–60 min):\n- Bite mark: small, often barely visible\n- Severe muscle cramping, especially abdomen and back\n- Rigidity — may mimic acute abdomen\n- Sweating, hypertension, tachycardia\n- Rarely: respiratory compromise (elderly/children)\n\nManagement:\n1. Wound care — clean with soap and water\n2. Analgesia: opioids for severe pain if available\n3. Muscle relaxants: methocarbamol 1–1.5g IV or diazepam 5–10mg IV for muscle cramps\n4. Calcium gluconate 10mL IV (10%) — controversial, some benefit for cramping\n5. Monitor vital signs, respiratory status\n\nAntivenom: available but rarely needed in healthy adults — reserved for severe cases, children, elderly.\n\nEvacuate: all symptomatic black widow bites warrant medical evaluation.'},
      brown_recluse: {type:'result', style:'warning', text:'BROWN RECLUSE SPIDER BITE\n\nVenom is cytotoxic/necrotizing — can cause severe tissue destruction (necrotic arachnidism).\n\nClinical course:\n- Initial: painless or mild stinging bite\n- 2–8 hours: localized pain, redness, central white blister\n- 24–72 hours: "blue-gray halo" — classic central necrosis developing\n- 1–2 weeks: eschar (black scab) forms, tissue death underneath\n- Rarely: systemic (hemolytic anemia, renal failure, DIC) — more common in children\n\nField management:\n1. Clean wound thoroughly with soap and water\n2. Immobilize and elevate affected limb\n3. Cool compress — 20 min on, 20 min off (reduces inflammation)\n4. Analgesia: ibuprofen + acetaminophen alternating\n5. Mark wound borders daily to track necrosis progression\n6. Do NOT excise or debride wound in the field — surgical timing is critical (2–6 weeks)\n7. No proven field antidote\n\nAntibiotics: ONLY if secondary infection develops (redness expanding with warmth, pus, fever).\n\nEvacuate: significant necrosis, systemic signs, or wounds on the face/genitals require surgical evaluation.'},

      // MARINE
      marine_q1: {type:'question', text:'What type of marine injury?', options:[
        {label:'Jellyfish sting', next:'jellyfish'},
        {label:'Stingray or catfish spine wound', next:'stingray'},
        {label:'Sea urchin puncture', next:'sea_urchin'},
      ]},
      jellyfish: {type:'result', style:'success', text:'JELLYFISH STING — Deactivate Nematocysts First\n\nWARNING: Do NOT rub the sting site — this activates unfired nematocysts (stinging cells).\n\nTreatment by species:\n\nMost jellyfish (moon jelly, sea nettle):\n1. Rinse with seawater (NOT fresh water — fresh water triggers remaining nematocysts)\n2. Remove visible tentacles with card/stick — do NOT use bare hands\n3. Apply vinegar (5% acetic acid) for 30 seconds\n4. Heat immersion: water as hot as tolerable (45°C/113°F) for 20–45 minutes\n5. Analgesia: ibuprofen or acetaminophen\n\nBox jellyfish (Indo-Pacific, highly dangerous):\n- Vinegar first — CRITICAL to deactivate nematocysts\n- Antivenom exists but is hospital-only\n- Respiratory and cardiac arrest possible — maintain airway, CPR if needed\n- Evacuate IMMEDIATELY\n\nPortuguese Man-o-War (technically a siphonophore):\n- Vinegar is controversial — use seawater rinse\n- Heat immersion is beneficial\n- More painful than dangerous to healthy adults\n\nWatch for: allergic reaction, anaphylaxis. Epinephrine 0.3mg IM if severe allergic response.'},
      stingray: {type:'result', style:'warning', text:'STINGRAY / CATFISH WOUND — Heat Immersion Critical\n\nStingray barb is retroserrated (barbed backward) with a protein-based venom that is heat-labile (destroyed by heat).\n\nImmediate treatment:\n1. HEAT IMMERSION — this is the most important step:\n   - Water as hot as tolerable without burning (45°C/113°F)\n   - Immerse for 30–90 minutes until pain resolves\n   - Reheat water as needed\n2. Remove the barb/spine if visible and easily accessible — do NOT probe deeply\n3. Irrigate wound copiously with clean water\n4. Inspect for retained foreign body (barbs break off)\n5. Analgesia: opioids may be needed for initial severe pain\n\nWound care after heat treatment:\n- Clean, explore gently, remove visible barb fragments\n- Leave open (puncture wounds have high infection rate)\n- Antibiotics (if available): ciprofloxacin 500mg BID × 5 days (covers marine Vibrio)\n\nWARNING: Stingray wounds to the thorax or abdomen are rare but can be FATAL — cardiac penetration. Treat as penetrating trauma + envenomation.'},
      sea_urchin: {type:'result', style:'success', text:'SEA URCHIN PUNCTURE\n\nSpines break off easily and are very brittle — retained spines are the primary concern.\n\nImmediate care:\n1. Remove visible spines with tweezers (fine-tipped)\n2. Heat immersion (45°C/113°F × 30–90 min) — reduces pain from protein venom\n3. Inspect carefully for retained fragments — spines are calcified and may be visible on X-ray\n\nDo NOT try to crush spines in the wound — causes further fragmentation.\n\nSmall retained spines will dissolve over 1–2 weeks without treatment.\nDeep retained spines near joints require surgical removal.\n\nWound care:\n- Clean thoroughly, leave open\n- Watch for infection signs (increasing pain, redness, warmth after 24–48h)\n- Antibiotics if infection develops\n\nSome urchins (crown-of-thorns, flower urchin) can cause more serious systemic effects — nausea, dizziness. Observe for 4–6 hours.'},
    }
  },

  // ── MISSING PERSON SEARCH PROTOCOL ───────────────────────────────
  {
    id: 'missing_person',
    title: 'Missing Person Search',
    icon: '🔍',
    description: 'Search and rescue protocol for a missing person',
    nodes: {
      start: {type:'question', text:'What is the missing person\'s profile? (Select closest match)', options:[
        {label:'Child under 12', next:'child_q1'},
        {label:'Person with dementia or cognitive impairment', next:'dementia_q1'},
        {label:'Hiker / outdoorsman — failed to return', next:'hiker_q1'},
        {label:'Adult — possible despondent or self-harm risk', next:'despondent_q1'},
        {label:'Adult — unknown circumstances', next:'unknown_adult'},
      ]},

      // CHILD
      child_q1: {type:'question', text:'How long has the child been missing?', options:[
        {label:'Under 30 minutes — just noticed', next:'child_recent'},
        {label:'30 minutes to 4 hours', next:'child_medium'},
        {label:'Over 4 hours or overnight', next:'child_extended'},
      ]},
      child_recent: {type:'result', style:'warning', text:'CHILD MISSING — IMMEDIATE ACTIONS (First 30 Minutes)\n\nThe first 30 minutes are critical for child abduction cases.\n\n1. IMMEDIATELY secure the area — stop people from leaving without being identified\n2. Search the immediate vicinity THOROUGHLY:\n   - All hiding spots: under beds, in closets, in vehicles, sheds, dumpsters\n   - Children often hide and don\'t respond when called (scared of getting in trouble)\n3. Call all phone numbers where child might be (friends, family)\n4. Alert all household members and neighbors\n5. Notify law enforcement NOW — do not wait\n\nDescription to provide law enforcement:\n- Age, height, weight, hair/eye color\n- Last known clothing (be specific: color, brand)\n- Last known location and time\n- Medical conditions requiring medication\n- Any known or suspected contacts/threats\n\nChild Amber Alert criteria: abduction + risk of serious harm + sufficient description to ID child or suspect.\n\nAssign someone to stay by phone/radio at base at all times.'},
      child_medium: {type:'result', style:'warning', text:'CHILD MISSING 30 MINUTES–4 HOURS\n\nStatistics: Most missing children are runaways or lost locally. Child abductions are rare but highest-risk.\n\nSEARCH ORGANIZATION:\n1. Establish a command post — do NOT let it collapse\n2. Assign a scribe to document all actions + times\n3. Expand search in concentric circles from last known point (LKP)\n4. Search based on child\'s known patterns, favorite spots, friends\n5. Broadcast description to all available radios/people\n\nSearch areas for children:\n- Attraction points: parks, pools, playgrounds, friends\' houses\n- Hazard points: bodies of water, drainage ditches, roads, construction\n- Children do NOT always move in straight lines — check all structures\n\nGrid search — assign sectors to individuals or teams, document cleared areas.\n\nDON\'T: let well-meaning volunteers search without coordination — they contaminate the scene, miss areas, create duplicate coverage.\n\nNotify: law enforcement, school, coach, known family members, neighbors within 1 block radius.'},
      child_extended: {type:'result', style:'danger', text:'CHILD MISSING OVER 4 HOURS — Major Search Operation\n\nAt 4+ hours, law enforcement SAR and possibly FBI involvement is warranted.\n\nOrganize a sustained search operation:\n\n1. COMMAND STRUCTURE:\n   - Incident Commander (one person)\n   - Operations Section: search teams\n   - Logistics: food, water, equipment for searchers\n   - Planning: map management, cleared areas, next sectors\n\n2. SEARCH METHODS:\n   - Hasty search: fast sweep of high-probability areas (roads, water, structures)\n   - Grid search: methodical coverage of areas not yet cleared\n   - Attraction search: broadcast sound (child\'s favorite music, parent calling)\n   - K9 teams: critical if available — start from LKP with unwashed clothing item\n\n3. DOCUMENTATION:\n   - Mark all searched areas on map with time/team\n   - Record all found items in place (photograph before moving)\n   - Keep a clue log\n\n4. FAMILY MANAGEMENT:\n   - Assign a liaison to keep family informed and away from active search\n   - Get a current photo for flyers (JPEG, recent)\n\nRestored children statistics: ~75% found within first hour; 95% within 24 hours. Probability of alive decreases sharply after 72 hours in abduction scenarios.'},

      // DEMENTIA
      dementia_q1: {type:'question', text:'Does the person have a known destination or behavioral pattern? (e.g., trying to "go home" to a former address, visiting family)', options:[
        {label:'Yes — known destination pattern', next:'dementia_pattern'},
        {label:'No — no known pattern, wandering at random', next:'dementia_no_pattern'},
      ]},
      dementia_pattern: {type:'result', style:'warning', text:'MISSING DEMENTIA PATIENT — Known Destination Pattern\n\nDementia patients who wander often travel toward a "home" they remember from decades past.\n\nSearch strategy:\n1. Identify ALL former addresses, workplaces, schools — check these first\n2. Check routes between current location and known destinations\n3. Check bus stops, taxi stands (dementia patients have been found blocks away using transit)\n4. Search in a STRAIGHT LINE toward the destination — dementia patients often follow roads\n5. Check churches, schools, familiar landmarks from their past\n\nBehavioral traits of wandering dementia patients:\n- Often found within 1 mile of departure point\n- Tend to follow paths of least resistance (sidewalks, roads, hallways)\n- May not respond to their name being called — approach calmly with familiar words\n- May be frightened — approach slowly, introduce yourself, avoid sudden movements\n\nMedical urgency: Dementia patients are at HIGH risk of injury, hypothermia, and dehydration within hours.\n\nBring with you: patient\'s photo, a familiar object or food they like, a familiar caregiver\'s voice on phone if possible.\n\nNotify law enforcement immediately — Silver Alert in many jurisdictions.'},
      dementia_no_pattern: {type:'result', style:'danger', text:'MISSING DEMENTIA PATIENT — No Pattern\n\nWithout a known destination, search is high-priority — dementia patients have rapidly fatal outcomes when lost.\n\nStatistics: ~50% of missing dementia patients die if not found within 24 hours in outdoor environments.\n\nSearch strategy:\n1. Expand from LKP in all directions — concentric search pattern\n2. Check ALL bodies of water within 1 mile — drowning is leading cause of death\n3. Check ALL structures: sheds, outbuildings, vehicles (including under/inside)\n4. Dementia patients tend to hide in enclosed spaces when frightened\n5. Approach gently — they may resist "rescue" and flee if startled\n\nHigh-probability locations:\n- Near roads (following paths of least resistance)\n- Near water\n- Dense vegetation edges (seeking shelter)\n- Vehicles — check ALL unlocked vehicles in area\n\nK9 teams extremely valuable — dementia patients often do not respond to calling.\n\nNotify law enforcement, Silver Alert, local medical facilities and emergency departments.\n\nWeather is critical: hypothermia in elderly begins at higher temperatures. Any weather below 60°F is an urgent factor.'},

      // HIKER
      hiker_q1: {type:'question', text:'What is the overdue hiker\'s skill level and the terrain?', options:[
        {label:'Experienced hiker / known route — overdue <6 hours', next:'hiker_experienced'},
        {label:'Inexperienced or casual hiker — any overdue time', next:'hiker_inexperienced'},
        {label:'Any hiker — overdue overnight or >12 hours', next:'hiker_extended'},
      ]},
      hiker_experienced: {type:'result', style:'warning', text:'OVERDUE EXPERIENCED HIKER\n\nMost likely explanations: minor injury, equipment failure, weather delay, navigation error.\n\nInitial actions:\n1. Attempt contact — cell phone, satellite communicator (SPOT/Garmin), radio\n2. Verify last known route plan, trailhead, and estimated return time\n3. Check if vehicle is still at trailhead\n4. Alert park service / forest service of overdue party\n5. Gather: last known waypoint, experience level, gear carried, physical condition\n\nIf no contact within 2 hours of overdue time:\n- Mobilize SAR team with the planned route information\n- Experienced hikers tend to stay on trail — trail search first\n- Check decision points (forks, summits, water sources) on the route\n\nEquipment matters:\n- Experienced hikers with bivy gear/shelter can survive 48–72h in most conditions\n- Factor in weather, terrain, water sources along route\n\nHasty team: Send 2–4 fast-moving experienced searchers along the planned route. They can cover ground quickly and may find the subject or rescue tracks.'},
      hiker_inexperienced: {type:'result', style:'danger', text:'OVERDUE INEXPERIENCED HIKER — URGENT\n\nInexperienced hikers have higher mortality from secondary injuries and poor decision-making when lost.\n\nLost hiker behavior:\n- Often keep moving (worsen situation) rather than staying put\n- Tend to move downhill toward water\n- May not follow trails — can enter thick terrain\n- LOST PERSON BEHAVIOR: 90% found within 3 miles of LKP; median distance 1.2 miles\n\nImmediate actions:\n1. Contact law enforcement / SAR immediately — do not wait\n2. Search trailhead and obvious access points first\n3. Trail heads — check for gear left behind, any written notes\n4. Medical considerations: dehydration, hypothermia, injury from falls\n\nSearch priorities:\n1. Trailhead and parking area (may have returned)\n2. Planned destination\n3. Drainage routes — "drainage syndrome" — lost people follow water downhill\n4. Any visible high ground with cell signal (people often seek high ground to get signal)\n5. Road edges — lost people often seek roads\n\nMake noise: whistles, vehicle horns, airhorn every 5 minutes at search boundaries — give 2 minutes of silence to listen for response.\n\nDo not send untrained volunteers into dangerous terrain.'},
      hiker_extended: {type:'result', style:'danger', text:'HIKER OVERDUE OVERNIGHT / 12+ HOURS — Major SAR Operation\n\nAt 12+ hours, the probability of a serious injury or medical emergency increases significantly.\n\nActivate full SAR:\n1. Notify local SAR / Sheriff / Park Service immediately if not already done\n2. Establish formal Incident Command System\n3. LKP confirmation — last known position (GPS track if available, cell tower ping, photos)\n4. Weather history since departure — factor in hypothermia risk\n5. Gather full subject profile: photo, description, gear list, medical conditions, medications\n\nSearch resources:\n- Helicopter search: first light, covering open areas and ridges\n- K9 teams: high probability rapid area coverage\n- Ground teams: systematic grid of high-probability areas\n- Cell phone: request carrier location data through law enforcement\n\nMedical planning:\n- Pre-position rescue with IV fluids, hypothermia blankets, litter\n- Coordinate receiving hospital for trauma/hypothermia\n\nProbability of survival in wilderness:\n- >90% if found in first 24 hours in temperate conditions\n- Drops significantly with hypothermia, dehydration, injury\n\nFamily management: assign dedicated liaison; keep searchers focused on search, not family support.'},

      // DESPONDENT
      despondent_q1: {type:'result', style:'danger', text:'MISSING DESPONDENT / SELF-HARM RISK — Crisis Response\n\nA despondent missing person has a higher risk of self-harm. This is a MEDICAL EMERGENCY, not just a missing person case.\n\nImmediate actions:\n1. Notify law enforcement IMMEDIATELY — they have authority to enter private property, initiate welfare checks, and coordinate mental health crisis response\n2. Gather recent communications (texts, social media, notes) — do NOT distribute widely but share with law enforcement\n3. Identify most likely locations:\n   - Places with personal significance (former home, a favorite place, location of past trauma)\n   - Remote or private areas where person feels safe or alone\n   - Locations mentioned in any communications\n4. Access to means: if person expressed suicidal intent, identify what access they had (firearms, medications, locations)\n\nFor community search:\n1. Send trusted individuals to known locations (home, friends, familiar spots)\n2. Have someone available by phone at all times in case person calls\n3. Do NOT overwhelm public social media with extreme alarm — this can escalate someone in crisis\n\nWhen found: do NOT confront or block escape. Speak calmly, do not make sudden movements. Focus on connection, not control. Do NOT leave them alone until professional help arrives.\n\nCrisis line resources: 988 Suicide & Crisis Lifeline (USA). In a grid-down situation, identify your community mental health resources in advance.'},

      // UNKNOWN ADULT
      unknown_adult: {type:'result', style:'warning', text:'MISSING ADULT — UNKNOWN CIRCUMSTANCES\n\nNote: In the USA, there is NO mandatory waiting period to report a missing adult. Report immediately if circumstances are suspicious or the person is vulnerable.\n\nInitial assessment checklist:\n1. Is this person at risk? (medical condition, age, recent trauma, suicidal statements, threats made against them)\n2. Was the disappearance voluntary? (history of leaving, relationship conflict, debt issues)\n3. Was there any sign of struggle, unusual vehicles, or suspicious activity at last known location?\n4. Check all obvious locations first: workplace, other family, friends, favorite spots\n5. Check social media — may have posted recent location\n6. Cell phone: is it going to voicemail? Is last text/call pattern normal?\n7. Was their vehicle taken? (check if vehicle present at residence)\n\nIf any red flags (suspicious circumstances, vulnerable person, threat risk):\n- Notify law enforcement immediately\n- Preserve the last known location as a potential crime scene\n- Document all known information in writing\n\nSearch organization (if conducting community search):\n1. Establish central communication point\n2. Assign sectors based on last known location\n3. Document all searched areas\n4. Do not allow searchers to go alone — pairs minimum\n5. Maintain searcher safety — search groups should check in at regular intervals'},
    }
  },

  // ── WOUND INFECTION ASSESSMENT ────────────────────────────────
  {
    id: 'wound_infection',
    title: 'Wound Infection Assessment',
    icon: '🩹',
    description: 'Assess wound healing vs infection and guide treatment decisions',
    nodes: {
      start: {type:'question', text:'How old is the wound?', options:[
        {label:'Less than 6 hours — fresh wound', next:'fresh_q1'},
        {label:'6–24 hours — several hours old', next:'older_q1'},
        {label:'1–3 days old', next:'day13_q1'},
        {label:'4+ days old', next:'day4plus_q1'},
      ]},

      // FRESH WOUND
      fresh_q1: {type:'question', text:'What type of wound is it?', options:[
        {label:'Clean cut (knife, glass) — minimal contamination', next:'fresh_clean'},
        {label:'Puncture wound (nail, bite, thorn)', next:'fresh_puncture'},
        {label:'Crush / laceration with embedded debris', next:'fresh_crush'},
        {label:'Animal or human bite', next:'bite_q1'},
      ]},
      fresh_clean: {type:'result', style:'success', text:'FRESH CLEAN WOUND — Primary Care\n\nGoal: Close cleanly and prevent infection.\n\nWound care protocol:\n1. Bleeding control: Direct pressure 10–15 minutes without lifting. If arterial (bright red, pulsing): tourniquet above wound.\n2. Irrigation: Flush vigorously with 200–500mL clean water or saline. Use a 35mL syringe + 18g needle (improvise with water bottle and pinhole) for high-pressure irrigation. This is the single most important infection prevention step.\n3. Debridement: Remove visible debris with tweezers, cut away only clearly dead tissue.\n4. Closure: Butterfly strips, steri-strips, or sutures (if trained). Close within 6 hours. Do NOT close animal bites, punctures, or heavily contaminated wounds.\n5. Dressing: Cover with clean non-adherent dressing. Change daily.\n\nAntibiotics: NOT needed for clean wounds in healthy individuals.\n\nTetanus: Update booster if >5 years since last (clean wound) or >10 years for contaminated.\n\nMonitor daily for infection signs (see 1–3 day protocol).'},
      fresh_puncture: {type:'result', style:'warning', text:'PUNCTURE WOUND — Higher Infection Risk\n\nPuncture wounds are HIGH-risk for deep tissue infection because:\n- Deep tract traps bacteria with minimal oxygen (anaerobic infection, gas gangrene)\n- Difficult to irrigate effectively\n- Often contain foreign material\n\nCare:\n1. Allow wound to bleed freely 1–2 minutes (flushes tract)\n2. DO NOT close a puncture wound\n3. Irrigate as much as possible with a syringe/bulb syringe\n4. Explore for retained foreign body if accessible\n5. Soak in warm clean water for 20 minutes if possible\n6. Open wound dressing — pack loosely with gauze, change twice daily\n\nAntibiotics: CONSIDER prophylactic antibiotics for:\n- Punctures on feet (Pseudomonas risk)\n- Deep hand punctures (risk to tendons, joints)\n- Immunocompromised patients\n- Contaminated punctures (manure, soil)\nAmoxicillin-clavulanate (Augmentin) 875mg BID × 5 days if available.\n\nWatch closely for Streptococcal soft tissue infection (rapid spread of redness within 12–24h) — requires aggressive antibiotics.\n\nGas gangrene warning: Severe deep pain + swelling + skin discoloration (gray/bronze) + crepitus (crackling under skin) = LIFE-THREATENING emergency.'},
      fresh_crush: {type:'result', style:'warning', text:'CRUSH WOUND / LACERATION WITH DEBRIS — High Risk\n\nCrush injuries have damaged tissue that is more susceptible to infection.\n\n1. Hemorrhage control: Pressure dressing. Elevation.\n2. Extensive irrigation — 500mL+ minimum. Remove all visible debris.\n3. Debridement: Remove crushed, devitalized tissue. Healthy tissue bleeds when cut; dead tissue does not.\n4. DO NOT close contaminated crush wounds primarily — leave open or loosely closed.\n   - Exception: face wounds (excellent blood supply, cosmetic importance)\n5. Delayed primary closure: If wound looks clean after 3–4 days, may close at that time.\n6. Dressing: Moist saline gauze packing, changed twice daily.\n\nAntibiotics: Strongly consider for crush injuries:\n- Amoxicillin-clavulanate 875mg BID × 5–7 days, OR\n- Doxycycline 100mg BID (if allergy to penicillin)\n\nTetanus prophylaxis: Required — contaminated wound.\n\nMonitor for compartment syndrome: 5 Ps — Pain (disproportionate), Pressure, Paresthesia, Paralysis, Pallor. If tight swollen compartment with these signs: definitive treatment is surgical fasciotomy.'},
      bite_q1: {type:'question', text:'What type of bite?', options:[
        {label:'Dog or cat bite', next:'dog_cat_bite'},
        {label:'Human bite', next:'human_bite'},
        {label:'Wild animal — possible rabies exposure', next:'rabies_bite'},
      ]},
      dog_cat_bite: {type:'result', style:'warning', text:'DOG / CAT BITE — Infection Risk\n\nDog bites: 10–15% infection rate. Cat bites: 30–50% infection rate (Pasteurella multocida from cat teeth can cause rapid cellulitis within hours).\n\nCare:\n1. Irrigate copiously with clean water immediately\n2. DO NOT close bite wounds (exception: facial bites where cosmesis is critical)\n3. Debride visibly damaged tissue\n\nAntibiotics: STRONGLY RECOMMENDED for all cat bites and moderate-severe dog bites:\n- Amoxicillin-clavulanate (Augmentin) 875mg BID × 5–7 days (first choice)\n- If penicillin allergy: doxycycline 100mg BID + metronidazole 500mg TID\n\nRabies consideration:\n- Dog bites: vaccinated pet = low risk. Unvaccinated or unknown = consider rabies\n- In USA: bats, raccoons, skunks, foxes have highest rabies prevalence\n- If animal can be observed for 10 days and remains healthy = low risk\n- Cannot observe animal: requires post-exposure prophylaxis (PEP) — hospital only\n\nTetanus: Update if >5 years.'},
      human_bite: {type:'result', style:'danger', text:'HUMAN BITE — Highest Infection Risk\n\nHuman bites have the HIGHEST infection rate of any bite wound. The human mouth contains >600 bacterial species including Eikenella corrodens (unique to humans, resistant to many antibiotics).\n\nSpecial concern — "Fight bite" (knuckle laceration against teeth): The hand flexed over teeth drives bacteria deep into the joint space. An infection in a hand joint rapidly destroys it.\n\nCare:\n1. Irrigate copiously and immediately\n2. DO NOT close human bite wounds\n3. Pack open with gauze\n\nAntibiotics: REQUIRED for ALL human bites:\n- Amoxicillin-clavulanate (Augmentin) 875mg BID × 5–7 days (first choice — covers Eikenella)\n- Alternative: doxycycline 100mg BID (covers Eikenella but inferior anaerobic coverage)\n\nBloodborne pathogen exposure (if blood-to-blood contact): Consider HIV/Hepatitis B/C risk — requires medical evaluation.\n\nSigns of joint space infection (fight bite): Marked swelling, restricted motion, pain on passive extension, warmth. This is an emergency requiring surgical washout.\n\nEvacuate: All hand fight bites, all bites with signs of infection developing within hours.'},
      rabies_bite: {type:'result', style:'danger', text:'WILD ANIMAL BITE — RABIES RISK\n\nRabies is almost universally fatal once symptomatic. Post-exposure prophylaxis (PEP) is highly effective if started before symptoms begin.\n\nHigh-risk animals in USA: Bats (highest!), raccoons, skunks, foxes, coyotes. Low risk: rabbits, squirrels, mice, rats.\n\nPEP requirement:\n- Any bat exposure (including finding bat in room where person slept — bat bites may not be felt)\n- Bite from high-risk wild animal\n- Bite from domestic animal that cannot be quarantined/tested\n\nField wound care:\n1. Immediate and thorough wound washing with soap and water for 15 minutes — this is the single most effective rabies prevention step\n2. Apply betadine/iodine if available\n3. DO NOT suture closed if rabies is a concern\n\nPEP must be administered at a medical facility:\n- Rabies immune globulin (RIG) — day 0, infiltrated into wound\n- Rabies vaccine series — 4 doses over 14 days (days 0, 3, 7, 14)\n\nNo PEP available in grid-down scenario: Focus on thorough wound cleansing. Incubation period is 20–90 days (sometimes longer). Any possibility of evacuation for PEP should be prioritized.'},

      // OLDER WOUND - 6-24h
      older_q1: {type:'question', text:'Has wound been treated or cleaned yet?', options:[
        {label:'Yes — properly irrigated and dressed', next:'older_clean'},
        {label:'No — untreated since injury', next:'older_dirty'},
      ]},
      older_clean: {type:'result', style:'success', text:'WOUND 6–24 HOURS — TREATED — Monitor Protocol\n\nAt this age, healing is underway. Normal wound healing progression:\n- 0–12h: Hemostasis (clotting)\n- 12–24h: Inflammation begins (redness, warmth, mild swelling — NORMAL at wound edges)\n- 24–72h: Active inflammation phase — swelling and redness at wound margins is EXPECTED\n\nNormal signs (do NOT treat as infection):\n- Mild redness immediately around wound edges (<1cm)\n- Mild swelling at wound site\n- Clear/pale yellow serous drainage\n- Mild warmth at wound site\n- Some discomfort/tenderness\n\nWARNING signs requiring antibiotic treatment:\n- Redness EXPANDING beyond wound edges (advancing cellulitis)\n- Thick yellow/green purulent drainage\n- Increasing pain after the first 48h (not improving)\n- Red streaks extending away from wound (lymphangitis = URGENT)\n- Fever >38.5°C / 101.3°F\n- Foul odor\n\nContinue: daily irrigation + non-adherent dressing change. Watch 3× daily for warning signs.'},
      older_dirty: {type:'result', style:'danger', text:'WOUND 6–24 HOURS — UNTREATED — Late Irrigation\n\nWounds untreated for 6+ hours are at significantly higher infection risk but irrigation and debridement remain worthwhile.\n\nAct now:\n1. Irrigate aggressively — 500mL+ clean water/saline under pressure\n2. Debride visible contamination and devitalized tissue\n3. DO NOT close primarily — increased infection risk at this age\n4. Pack open with gauze, change twice daily\n\nAntibiotics: Strongly recommended for untreated wounds >6 hours:\n- Amoxicillin-clavulanate 875mg BID × 5 days, OR\n- Doxycycline 100mg BID × 5 days\n\nMonitor closely for rapid progression (see 1–3 day protocol for warning signs).\n\nNOTE on delayed primary closure: If wound is clean at 3–4 days (no infection signs), you may consider closing at that time. This is called "delayed primary closure" — the wound has lower infection risk once the initial bacterial burden clears.'},

      // 1-3 DAYS
      day13_q1: {type:'question', text:'Assess the wound: What do you see?', options:[
        {label:'Healing normally — mild redness at edges, no spread, wound closing', next:'day13_normal'},
        {label:'Concerning — expanding redness, increasing pain, or pus', next:'day13_infected'},
        {label:'Red streaks extending away from wound', next:'lymphangitis'},
      ]},
      day13_normal: {type:'result', style:'success', text:'WOUND DAY 1–3 — NORMAL HEALING\n\nContinue standard wound care:\n1. Gentle cleaning with clean water or saline\n2. Non-adherent dressing, changed daily\n3. Keep wound moist but not wet\n4. Elevation reduces swelling\n\nAt day 3–5: Granulation tissue (red, beefy tissue) is a POSITIVE sign of healing.\n\nContinue monitoring twice daily. If any warning signs develop, reassess immediately.'},
      day13_infected: {type:'result', style:'warning', text:'WOUND DAY 1–3 — EARLY INFECTION\n\nEarly wound infection is treatable. Act promptly.\n\nWound care:\n1. Open the wound — remove sutures/closure if present. An infected wound MUST drain.\n2. Irrigate with clean water or dilute betadine (1 part betadine : 10 parts water)\n3. Pack loosely with gauze (do not pack tightly — prevents drainage)\n4. Change dressing twice daily with irrigation each time\n\nAntibiotics (start immediately):\n- Amoxicillin-clavulanate (Augmentin) 875mg BID × 7 days, OR\n- Cefalexin 500mg QID × 7 days (good gram-positive coverage)\n- For penicillin allergy: doxycycline 100mg BID × 7 days\n\nMRSA consideration: If no improvement in 48–72h on standard antibiotics, consider MRSA:\n- Trimethoprim-sulfamethoxazole (TMP-SMX/Bactrim) 1–2 DS tablets BID\n\nMonitor for red streak progression (lymphangitis) — see lymphangitis node.'},
      lymphangitis: {type:'result', style:'danger', text:'LYMPHANGITIS — RED STREAKS — URGENT\n\nRed streaks extending away from a wound follow the lymphatic vessels and indicate spreading infection moving toward the bloodstream (septicemia).\n\nThis is a medical EMERGENCY.\n\nImmediate actions:\n1. Mark the leading edge of red streaks with pen + time every 30–60 minutes\n2. Start antibiotics IMMEDIATELY (do not wait)\n3. Rest the affected limb completely — elevation\n\nAntibiotics (start within minutes):\n- Amoxicillin-clavulanate 875mg BID OR cefalexin 500mg QID\n- If streaks are rapidly advancing OR patient has fever/chills: use both and prepare for potential sepsis\n- Most commonly caused by Streptococcus pyogenes (Group A Strep) — highly penicillin-sensitive\n\nIf streaks stop advancing and begin to fade within 24–48h on antibiotics: good sign.\n\nIf streaks CONTINUE to advance or patient develops fever, chills, hypotension, confusion = SEPSIS. Evacuate immediately — this can be fatal within hours.\n\nSepsis treatment: IV antibiotics, fluid resuscitation. Field management is supportive only.'},

      // 4+ DAYS
      day4plus_q1: {type:'question', text:'Assess the wound at 4+ days:', options:[
        {label:'Healing well — granulation tissue forming, no infection signs', next:'day4_healing'},
        {label:'Obvious infection — pus, spreading redness, pain', next:'day4_infected'},
        {label:'Wound not healing — edges dry, no granulation, static appearance', next:'day4_nonhealing'},
      ]},
      day4_healing: {type:'result', style:'success', text:'WOUND 4+ DAYS — HEALING WELL\n\nGranulation tissue (moist, red, slightly bumpy) is the foundation of wound healing. Epithelialization (new skin) grows across from the edges at 1mm/day.\n\nAt this stage:\n- Continue gentle moist dressing changes every 1–2 days\n- Avoid disturbing granulation tissue\n- Keep wound covered — open-air drying is counterproductive\n- Honey (medical-grade Manuka if available) is an excellent natural wound dressing for granulating wounds — antimicrobial + moist environment\n\nFor larger wounds without closure: Consider secondary closure (skin edges pulled together) at 4–5 days if clean.\n\nScarring: Expect significant scarring without surgical closure. Wounds heal — accept imperfect cosmesis in field conditions.'},
      day4_infected: {type:'result', style:'danger', text:'WOUND 4+ DAYS — ESTABLISHED INFECTION\n\nA 4-day-old infected wound requires aggressive management.\n\n1. Open and drain: Remove any closure. Pus MUST exit. Gently express pus with pressure.\n2. Explore for abscess pocket: A fluctuant (soft, fluid-filled) area that does not drain on its own may need incision.\n   - Incision and drainage (I&D): Make incision at point of maximum fluctuance, drain pus, break up any loculations, pack open with gauze wick.\n3. Irrigate copiously after drainage\n4. Pack open, change dressing twice daily with irrigation\n\nAntibiotics — start now:\n- Cefalexin 500mg QID × 7–10 days, OR\n- Amoxicillin-clavulanate 875mg BID × 7–10 days\n- MRSA cover: add TMP-SMX DS 1 tablet BID if no improvement in 48–72h\n\nSigns of systemic infection (sepsis): Fever >38.5°C, chills, rapid heart rate, confusion — requires IV antibiotics and supportive care. Evacuate if possible.'},
      day4_nonhealing: {type:'result', style:'warning', text:'NON-HEALING WOUND — Investigate Cause\n\nA wound not healing after 4 days may have an underlying cause.\n\nCommon causes:\n1. Retained foreign body (glass, wood, fabric) — feels firm under tissue, X-ray may show metallic FBs\n2. Ongoing contamination — wound keeps getting dirty/contaminated\n3. Ischemia — inadequate blood supply (peripheral vascular disease, tight dressing)\n4. Infection — low-grade infection preventing healing\n5. Nutritional deficiency — protein/vitamin C deficiency impairs healing\n6. Diabetes — significantly impairs wound healing\n\nActions:\n1. Explore wound gently for foreign body\n2. Review dressing technique — ensure moisture balance\n3. Increase protein intake — wound healing requires 1.5g/kg/day protein\n4. Debride any black/gray eschar to expose healthy tissue underneath\n5. Consider dilute betadine washes (1:10) for 3 days then switch to saline\n6. Add zinc (220mg daily) and vitamin C (500mg daily) supplementation if available'},
    }
  },

  // ── ALLERGIC REACTION / ANAPHYLAXIS ──────────────────────────────
  {
    id: 'anaphylaxis',
    title: 'Allergic Reaction / Anaphylaxis',
    icon: '💉',
    description: 'Assess and treat allergic reactions from mild to anaphylactic shock',
    nodes: {
      start: {type:'question', text:'What symptoms are present? (Select the most severe)', options:[
        {label:'Skin only — hives, itching, redness, mild swelling', next:'mild_q1'},
        {label:'Moderate — significant swelling, widespread hives, mild breathing change', next:'moderate_q1'},
        {label:'Severe — difficulty breathing, throat tightening, voice change, wheezing', next:'severe_airway'},
        {label:'Shock — pale, weak rapid pulse, confusion, loss of consciousness', next:'anaphylactic_shock'},
      ]},

      mild_q1: {type:'question', text:'Is the patient KNOWN to have a severe allergy (bee sting, food, medication)?', options:[
        {label:'Yes — known severe allergy, even if currently mild symptoms', next:'mild_known_allergy'},
        {label:'No known severe allergy — this appears to be first reaction', next:'mild_no_history'},
      ]},
      mild_known_allergy: {type:'result', style:'warning', text:'MILD REACTION — KNOWN SEVERE ALLERGY — High Alert\n\nEven though current symptoms are mild, in a patient with known severe allergy the reaction can progress rapidly to anaphylaxis within minutes.\n\nImmediate actions:\n1. GIVE EPINEPHRINE NOW if patient has EpiPen prescribed — do not wait for symptoms to worsen\n   - EpiPen/Auvi-Q: Outer thigh, through clothing if necessary. Hold 10 seconds.\n2. Position: Have patient sit upright (if breathing difficulty) or lie flat with legs elevated (if dizzy/lightheaded)\n3. Remove or discontinue trigger if identifiable (stop food, remove stinger)\n4. IV/oral antihistamine: Diphenhydramine (Benadryl) 25–50mg PO or IM\n\nAfter epinephrine:\n- Watch for biphasic reaction — symptoms can return 4–8 hours after initial episode\n- Observe minimum 4 hours after epinephrine\n- Corticosteroids if available: Prednisone 40–60mg PO (or equivalent) reduces biphasic risk\n\nEpinephrine auto-injectors expire — check dates annually and replace.'},
      mild_no_history: {type:'result', style:'success', text:'MILD ALLERGIC REACTION — No Known Severe Allergy\n\nContact dermatitis, mild urticaria, or food intolerance reaction.\n\nManagement:\n1. Remove trigger if known (food, plant, chemical)\n2. Wash affected skin with soap and water\n3. Antihistamine: Diphenhydramine (Benadryl) 25–50mg PO every 6–8h\n   OR cetirizine (Zyrtec) 10mg once daily (less sedating)\n4. Hydrocortisone cream 1% topically for skin rash — apply 3× daily\n5. Cool compress for localized swelling or itching\n\nNOTE on bee/wasp sting — First reaction:\n- First sting reaction is almost always mild — subsequent stings can cause severe allergy\n- Remove stinger (scrape with card — do NOT squeeze with tweezers, injects more venom)\n- Watch for 30 minutes for any sign of systemic reaction\n- Subsequent stings: see allergist if possible, obtain EpiPen\n\nWatch for: any spread of symptoms beyond skin, any throat/breathing involvement. If these develop, upgrade to severe protocol immediately.'},

      moderate_q1: {type:'question', text:'Are there any airway symptoms? (hoarse voice, throat tightness, difficulty swallowing, stridor)', options:[
        {label:'No airway symptoms — swelling and hives only', next:'moderate_no_airway'},
        {label:'YES — any throat/voice/swallowing change', next:'severe_airway'},
      ]},
      moderate_no_airway: {type:'result', style:'warning', text:'MODERATE ALLERGIC REACTION — No Airway Involvement\n\nModerate reaction requires active treatment. Watch for progression.\n\nImmediate treatment:\n1. Epinephrine: GIVE if patient has prescribed EpiPen, or if symptoms are worsening\n   - If not prescribed: use only if reaction is clearly progressing toward severe\n   - Epinephrine IM dose: 0.3mg (adult), 0.15mg (child 15–30kg)\n2. Diphenhydramine 50mg IM or PO\n3. Corticosteroids if available: Prednisone 40–60mg PO or methylprednisolone 125mg IM/IV\n4. IV access if possible — prepare for rapid deterioration\n\nPosition:\n- Breathing difficulty: sitting upright (tripod position)\n- Hives/swelling without breathing symptoms: comfortable position\n- If lightheaded: lie flat, elevate legs\n\nObserve continuously — moderate reactions can progress to severe within 5–15 minutes.\n\nTrigger identification: Food (especially peanuts, shellfish, tree nuts, milk, eggs, wheat), medications (penicillin, NSAIDs), latex, insect stings. Knowing the trigger prevents recurrence.'},

      severe_airway: {type:'result', style:'danger', text:'SEVERE ANAPHYLAXIS — AIRWAY INVOLVEMENT — EPINEPHRINE NOW\n\nAirway compromise in anaphylaxis can cause death within minutes from asphyxiation.\n\n⚡ EPINEPHRINE — IMMEDIATE — This is the treatment. Nothing else works fast enough.\n\nEpinephrine dosing:\n- EpiPen Jr (0.15mg): Children 15–30kg\n- EpiPen (0.3mg): Adults and children >30kg\n- Injection: Outer thigh, mid-third, perpendicular to skin. Through clothing is acceptable.\n- Hold for 10 seconds\n- May repeat in 5–15 minutes if symptoms not improving\n\nIf no EpiPen — improvised epinephrine injection:\n- 1:1000 epinephrine (1mg/mL): 0.3–0.5mg (0.3–0.5mL) IM lateral thigh\n- NEVER IV push (causes cardiac arrhythmia)\n\nAfter epinephrine:\n1. Position: Sit upright for breathing difficulty. Do NOT allow patient to stand suddenly (orthostatic collapse after epinephrine)\n2. Supplemental O2 if available: high-flow via non-rebreather mask\n3. Diphenhydramine 50mg IM/IV\n4. Corticosteroids: methylprednisolone 125mg IV or prednisone 40mg PO\n5. Bronchodilator: albuterol inhaler (2 puffs) if wheeze present\n\nAirway management:\n- Stridor (high-pitched inspiratory sound) = upper airway edema — may need surgical airway if epi fails\n- If voice becomes muffled or stops completely: prepare for needle cricothyrotomy (last resort)\n\nEvacuate immediately — biphasic reaction risk. Patient needs 24h observation minimum.'},

      anaphylactic_shock: {type:'result', style:'danger', text:'ANAPHYLACTIC SHOCK — LIFE-THREATENING — ACT IMMEDIATELY\n\nAnaphylactic shock: profound vasodilation + airway compromise. Fatal in minutes without epinephrine.\n\n⚡ EPINEPHRINE — FIRST AND NOW\n1. EpiPen to lateral thigh, hold 10 seconds. If unconscious, you may still inject.\n2. Lay patient FLAT — do NOT sit up (shock position: legs elevated 30° unless airway compromised)\n3. Second epinephrine in 5–15 minutes if no response\n\nIf IV access available:\n- Large bore IV × 2\n- Aggressive fluid bolus: 1–2L normal saline (30mL/kg) rapidly — anaphylactic shock has a HUGE volume deficit\n- Epinephrine IV drip if cardiac arrest: 1mg in 1L NS (1mcg/mL), titrate to BP\n\nAirway management:\n- Chin lift / jaw thrust, recovery position if unconscious and breathing\n- BVM ventilation if not breathing\n- If no pulse: CPR — cardiac arrest from anaphylaxis is highly reversible with early epinephrine\n\nSecondary medications (only AFTER epinephrine + fluids):\n- Diphenhydramine 50mg IM/IV\n- Corticosteroids: methylprednisolone 125mg IV\n- For refractory bronchospasm: albuterol 2.5mg nebulized\n\nCPR note: In anaphylactic arrest, epinephrine is the critical medication. Continue CPR continuously while giving epinephrine.\n\nEvacuate: All anaphylactic shock patients require hospital care — biphasic reactions, rebound shock, and myocardial injury are all possible in the hours following.'},
    }
  },

  // ── ELECTRICAL HAZARD RESPONSE ───────────────────────────────
  {
    id: 'electrical_hazard',
    title: 'Electrical Hazard Response',
    icon: '⚡',
    description: 'Downed power lines, electrocution rescue, and electrical burns',
    nodes: {
      start: {type:'question', text:'What is the electrical emergency?', options:[
        {label:'Person in contact with electricity / electrocution in progress', next:'active_contact'},
        {label:'Downed power line — no person in contact', next:'downed_line'},
        {label:'Person released from electricity — now unconscious or injured', next:'post_shock_q1'},
        {label:'Electrical fire', next:'elec_fire'},
        {label:'Lightning strike victim', next:'lightning_q1'},
      ]},

      active_contact: {type:'result', style:'danger', text:'ACTIVE ELECTROCUTION — DO NOT TOUCH THE VICTIM\n\nThe #1 cause of multiple electrocution deaths is rescuers touching the victim while current is still flowing.\n\nSTEP 1 — ISOLATE THE POWER SOURCE:\n1. If possible: Turn off the circuit breaker, unplug the device, or cut power at the main panel\n2. NEVER touch the victim until you are certain power is off\n3. Do NOT use water or metal objects to separate victim from source\n\nIf power CANNOT be turned off (downed power line, stuck switch):\n- Call 911 immediately — only utility workers can de-energize lines\n- Keep everyone 30+ feet (9m) away — step-and-touch voltage can kill bystanders\n- If you MUST separate victim from an indoor source with power still on:\n  • Use a DRY non-conducting object ONLY: wooden board, wooden chair, dry rope, rubber mat\n  • Stand on dry surface (rubber mat, dry wood)\n  • Push/pull with dry non-conducting item — DO NOT TOUCH VICTIM\n\nOnce power is confirmed off:\n- Approach victim carefully\n- Begin assessment (see post-shock protocol)\n- CPR if no pulse or not breathing — electrical victims have reversible cardiac arrest\n\nAssume: all downed lines are live. All wires near fallen trees after storms are live.'},

      downed_line: {type:'result', style:'danger', text:'DOWNED POWER LINE — Perimeter Safety\n\nA downed power line can energize the ground in a circle around it — walking near it can cause a fatal shock through your feet (step potential).\n\nSafe distance: minimum 30 feet (9m) from any downed line. Energized ground extends further.\n\nIf you are NEAR a downed line and feel tingling in your feet:\n- DO NOT run — running with large stride crosses voltage gradient zones\n- Shuffle away with small steps, keeping both feet together at all times, until clear\n- OR hop away on one foot\n\nIf a downed line lands on your vehicle:\n1. Stay inside — the car body dissipates voltage; exiting makes you the ground path\n2. Honk horn to alert others\n3. Only exit if fire/smoke forces you to — if you must exit:\n   - Jump clear (do NOT step down and touch car simultaneously)\n   - Land with both feet together\n   - Shuffle or hop away (never large steps)\n\nActions:\n1. Mark the area and keep everyone back\n2. Call utility emergency line immediately\n3. Assume all lines are live — even if they appear dead or are attached to a "telephone pole"\n4. Wet ground greatly increases conductivity — rains/puddles increase danger zone\n\nNever drive over a downed line. Never move a line with any object.'},

      post_shock_q1: {type:'question', text:'What is the victim\'s condition after release from electricity?', options:[
        {label:'Unresponsive and not breathing (cardiac arrest)', next:'elec_arrest'},
        {label:'Unresponsive but breathing', next:'elec_unconscious'},
        {label:'Conscious but confused, disoriented, or weak', next:'elec_altered'},
        {label:'Conscious and alert — entry/exit burn wounds visible', next:'elec_burns'},
      ]},
      elec_arrest: {type:'result', style:'danger', text:'ELECTRICAL CARDIAC ARREST — HIGHLY REVERSIBLE WITH CPR\n\nElectricity causes ventricular fibrillation. Unlike most cardiac arrests, electrical arrest has excellent outcomes with immediate CPR — cardiac and brain damage are often absent if CPR starts within minutes.\n\nImmediate actions:\n1. Confirm scene is safe — power is OFF\n2. Start CPR immediately — 30 compressions : 2 breaths\n3. AED: Apply and follow prompts as soon as available — electrical arrest is highly shockable\n4. Do NOT stop for at least 30 minutes — electrical arrest victims have been successfully resuscitated after extended CPR\n5. Assume spinal injury: minimize neck movement during airway management\n\nWhy electrical arrest differs:\n- Heart is otherwise healthy (no atherosclerosis)\n- Brain was not deprived of O2 before arrest (was breathing until shock)\n- Ventricular fibrillation is the most defibrillatable rhythm\n\nPost-resuscitation: All electrical victims need hospital monitoring — delayed arrhythmias can occur hours later. Even those who appear fully recovered need cardiac monitoring for 24h.'},
      elec_unconscious: {type:'result', style:'warning', text:'ELECTRICAL INJURY — UNCONSCIOUS BUT BREATHING\n\nElectrical current through the brain can cause prolonged unconsciousness.\n\nCare:\n1. Recovery position — on side, airway open, monitor breathing continuously\n2. Assume SPINAL INJURY — log-roll to recovery position using spinal precautions if possible (electrical entry/exit often involves spine pathway)\n3. Monitor breathing closely — respiratory arrest can follow\n4. Do NOT give anything by mouth\n5. IV access if available — electrolytes and fluid management are needed\n6. Check for entry/exit burn wounds (may be small and easily missed)\n\nElectrical injuries to be aware of:\n- Internal burns along current path (entry to exit) — often far worse than skin burns suggest\n- Cardiac arrhythmias can develop later — continuous cardiac monitoring needed\n- Rhabdomyolysis (muscle breakdown) — dark urine = myoglobin in urine — requires aggressive IV hydration\n- Compartment syndrome — current causes deep muscle swelling in extremities\n\nEvacuate IMMEDIATELY — spinal injury + internal burns + arrhythmia risk = hospital required.'},
      elec_altered: {type:'result', style:'warning', text:'ELECTRICAL INJURY — CONSCIOUS BUT ALTERED\n\nEven conscious electrical victims have significant injury risk.\n\nAssessment:\n1. Entry and exit wounds: look at all extremities. Entry is often a small charred puncture. Exit is where current left the body — may be larger.\n2. Assess each limb motor/sensory: "Can you squeeze my hand? Can you feel this?"\n3. Check pulse in all extremities — vascular injury can cause loss of distal pulse\n4. Ask about chest pain, palpitations (cardiac involvement)\n5. Ask about back or neck pain (spinal involvement)\n\nFind the path: If entry is on the hand and exit is on the foot, the current path traversed the arm, chest (heart), abdomen, and leg — all of these can be injured.\n\nImmediate care:\n1. Lay patient flat, minimize movement\n2. IV fluids if available — wide-open for first 30 minutes to protect kidneys from myoglobin\n3. Cardiac monitoring if available\n4. Wound dressing for burns\n5. Do NOT leave patient alone — delayed deterioration occurs\n\nAll electrical injuries — even "minor" — require hospital evaluation.'},
      elec_burns: {type:'result', style:'warning', text:'ELECTRICAL BURNS — Entry/Exit Wounds\n\nElectrical burns look small on the outside but the internal damage can be extensive.\n\nCharacteristics:\n- Entry wound: small, gray-white or charred, depressed center (tissue coagulation)\n- Exit wound: may be larger, "blowout" appearance from explosive steam expansion\n- Internal burns along current path — fat, muscle, vessels, nerves along the route\n\nWound care:\n1. Cover entry and exit wounds with clean non-adherent dressing\n2. Do NOT debride or explore wounds in the field\n3. Elevate burned extremity\n4. Do NOT use ice — electrical burn tissue is ischemic and very fragile\n\nCritical concerns:\n1. Internal injury is far worse than skin appearance suggests — treat aggressively regardless of small wound size\n2. Myoglobinuria: dark/cola-colored urine = muscle breakdown products in kidneys. Requires IV fluids 1–2 mL/kg/hr until urine clears\n3. Compartment syndrome: tense/rigid muscles, pain on passive stretch, loss of distal pulse\n4. Eye involvement: cataracts can develop months later from current through head/face\n\nAll electrical burns require hospital care.'},

      elec_fire: {type:'result', style:'danger', text:'ELECTRICAL FIRE — Class C Fire\n\nDO NOT use water on an electrical fire — water conducts electricity and can cause electrocution.\n\nFire extinguisher class:\n- Class C extinguisher (in USA) — CO2 or dry chemical, specifically rated for electrical fires\n- ABC dry chemical extinguisher — safe for electrical fires\n- Never use: water, foam (Class A), or wet chemical extinguishers on live electrical fires\n\nIf electrical fire is small and you have a Class C/ABC extinguisher:\n1. Cut power to the circuit or building if you can safely do so first\n2. PASS technique: Pull pin → Aim at base → Squeeze handle → Sweep side to side\n3. Stay near exit; keep your back to the exit\n4. 1 attempt only — if fire not extinguished immediately, evacuate\n\nIf fire is in a wall or panel:\n- Electrical fires inside walls grow rapidly and are invisible\n- Cut power, evacuate, call fire department\n- Do NOT open the wall panel — rush of oxygen feeds the fire\n\nSmell of burning wiring/plastic without visible flames:\n- This is a smoldering electrical fire inside walls or panels — evacuate and call fire department immediately\n- Do NOT ignore it'},

      lightning_q1: {type:'question', text:'Lightning strike victim assessment:', options:[
        {label:'No pulse / not breathing — cardiac arrest', next:'lightning_arrest'},
        {label:'Pulse present — conscious or unconscious', next:'lightning_stable'},
      ]},
      lightning_arrest: {type:'result', style:'danger', text:'LIGHTNING STRIKE — CARDIAC ARREST\n\nLightning causes cardiac arrest by direct current (DC) shock — very different from AC household current.\n\nKey fact: Lightning strike survivors rarely have ongoing electrical hazard — the lightning has passed. It is SAFE to touch a lightning victim immediately — they carry no electrical charge.\n\nStart CPR immediately:\n1. The lightning-caused arrest is highly reversible — immediate CPR is critical\n2. AED if available — apply and follow prompts\n3. 30:2 compression-to-breath ratio\n4. Continue for minimum 30 minutes — lightning arrests respond to prolonged CPR\n\nPost-resuscitation concerns:\n- Tympanic membrane rupture (ruptured eardrums from thunder) — examine ear canals\n- Eye injury — flash blindness or retinal detachment\n- Burns at entry (top of body) and exit (feet)\n- Spinal injury — violent muscle spasm from lightning can cause spinal fractures\n- Delayed neurological changes — confusion, amnesia, personality changes\n\n"Reverse triage" for lightning mass casualty: Treat apparently dead first — lightning arrests are far more survivable than other cardiac arrests.'},
      lightning_stable: {type:'result', style:'warning', text:'LIGHTNING STRIKE — PULSE PRESENT\n\nLightning survivors who have a pulse have a good prognosis but need careful monitoring.\n\nCommon lightning injury patterns:\n1. "Flashover" — lightning current traveled across skin surface (most common, least severe)\n2. Direct strike — highest severity, usually cardiac arrest\n3. Side splash — lightning jumped to victim from nearby object\n4. Ground current — lightning spread along ground, victim stepped in it\n\nAssessment and care:\n1. Move to shelter — victim may be standing in an open area still at risk\n2. Assess for: burns (entry at top, exit at feet), hearing loss, vision changes, confusion\n3. Remove metal jewelry/belt buckles (secondary skin burns from heated metal)\n4. If unconscious but breathing: recovery position, spinal precautions\n5. IV fluids if available — rhabdomyolysis risk\n\nKeraunoparalysis: Lightning-specific syndrome — temporary paralysis with mottled, pulseless extremities that resolves over hours. Mimics spinal injury. Usually resolves — do not amputate based on this finding.\n\nAll lightning strike survivors require hospital evaluation regardless of how well they appear — delayed arrhythmia, intracranial hemorrhage, and renal failure are possible hours later.'},
    }
  },

  // ── DROWNING / NEAR-DROWNING ──────────────────────────────────
  {
    id: 'drowning',
    title: 'Drowning / Near-Drowning',
    icon: '🌊',
    description: 'Water rescue, resuscitation, and near-drowning management',
    nodes: {
      start: {type:'question', text:'What is the drowning situation?', options:[
        {label:'Active drowning — victim still in water, in distress', next:'rescue_q1'},
        {label:'Victim removed from water — not breathing or unconscious', next:'out_not_breathing'},
        {label:'Victim removed from water — conscious but symptomatic', next:'out_conscious'},
        {label:'Victim submerged in cold water (&lt;50°F/10°C) — unknown time', next:'cold_water'},
      ]},

      rescue_q1: {type:'question', text:'What is your ability to reach the victim?', options:[
        {label:'I have a flotation device (life ring, rope, cooler, board)', next:'reach_throw'},
        {label:'I can reach from shore with an object (branch, clothing rope)', next:'reach_extend'},
        {label:'No equipment — considering swimming rescue', next:'swim_rescue_warn'},
      ]},
      reach_throw: {type:'result', style:'warning', text:'WATER RESCUE — REACH OR THROW\n\nRule: REACH — THROW — ROW — GO (in order of rescuer safety)\n\nThrow technique:\n1. Yell to the victim to stop struggling and look at you\n2. Throw flotation PAST the victim — let them grab it as it passes, or pull it to them\n3. Use: life ring on rope, empty cooler, life jacket, plastic bottle on rope\n4. Once victim grabs flotation: tow to shore at a safe angle, not straight back\n\nIf victim is calm and floating: "Reach" with a long object — branch, belt, tied clothing, paddle\n\nCalling for help: Shout for help first. Call 911 if available.\n\nOnce victim is on shore:\n- Assess: breathing, pulse, level of consciousness\n- Begin resuscitation if not breathing (see non-breathing protocol)\n- Keep warm — drowning victims are hypothermic\n- Lay flat, elevate legs slightly if conscious and no spinal concern\n\nDo NOT: Jump in after a drowning victim unless you are trained in water rescue — panic-stricken drowning victims will climb on top of you, pushing you under. Untrained swimming rescues cause multiple fatalities every year.'},
      reach_extend: {type:'result', style:'warning', text:'WATER RESCUE — EXTENDING REACH\n\n1. Get low to the ground (reduces your risk of being pulled in)\n2. Brace yourself — hold onto a fixed object or have a helper hold your ankles\n3. Extend the longest object you have:\n   - Rope/belt/clothing tied together\n   - Tree branch\n   - Paddle, fishing pole, ladder section\n4. Tell the victim: "Grab the end and hold tight — don\'t let go"\n5. Pull victim toward shore with a steady, smooth pull\n6. Do NOT let victim grab your hands if you are not anchored — they will pull you in\n\nIf you have no rope/object:\n- Use multiple people as a chain — each person holds the ankles of the person in front, forming a human chain extending into the water (everyone must be firmly anchored)\n\nOnce out of water:\n- Assess for breathing immediately\n- Cold/hypothermia management\n- Begin CPR if not breathing'},
      swim_rescue_warn: {type:'result', style:'danger', text:'SWIMMING RESCUE — HIGH RESCUER RISK\n\nA drowning victim in active panic is one of the most dangerous situations for a rescuer.\n\nDrowning physiology:\n- An actively drowning person cannot call for help (they are silent, mouth barely above water)\n- They are in an instinctive climbing response — they will push ANYTHING down to get above water\n- An untrained swimming rescuer will be pushed under and drowned by the victim\n\nIf you MUST enter the water (imminent loss of the victim, no other option):\n1. Take a flotation device — push it to victim, do NOT let them grab you\n2. Approach from behind if possible — victim grabs the flotation, not you\n3. Talk to them continuously — if they respond and calm down, risk decreases\n4. If victim grabs you: take a breath, go underwater — they will release to stay above water. Resurface and re-approach from behind.\n\nIf victim is passive/unconscious in water (has stopped struggling):\n- Safer to approach — no grabbing response\n- Support head, keep airway above water\n- Begin rescue breaths in water if trained\n\nSelf-rescue if YOU are drowning: Roll onto back, float. Tilt head back, ears in water. Stay calm — panic causes sinking. Signal for help.'},

      out_not_breathing: {type:'result', style:'danger', text:'DROWNING VICTIM — NOT BREATHING — RESUSCITATION PROTOCOL\n\nDrowning is an ASPHYXIA arrest (oxygen deprivation), NOT a cardiac arrest. The priority is BREATHING, not chest compressions first.\n\n⚡ MODIFIED CPR FOR DROWNING:\n1. Position victim flat on back\n2. Head tilt / chin lift — clear airway, look for obstruction\n3. DO NOT use abdominal thrusts (Heimlich) — drowning water is absorbed by lungs, not a true obstruction\n4. Give 5 RESCUE BREATHS first (before compressions)\n   - Tilt head back, pinch nose, give 1 second breaths, watch chest rise\n5. Check pulse: 10 seconds (carotid)\n6. If no pulse OR no breathing: Begin full CPR — 30:2 ratio\n7. Continue CPR until spontaneous breathing resumes, AED/help arrives, or 30+ minutes\n\nSpinal injury consideration:\n- Assume spinal injury if victim was diving, surfing, cliff-jumping, or fell from height into water\n- In-line spinal precautions during all airway maneuvers if spinal injury suspected\n- If spinal injury: modified jaw thrust instead of head-tilt chin-lift\n\nDo NOT attempt to drain water from lungs — it does not work and wastes time. The water in drowning lungs is minimal and absorbed by the body.\n\nRecovery: All drowning victims with any loss of consciousness, difficulty breathing, or CPR performed must be evacuated — secondary drowning (delayed pulmonary edema) can be fatal 4–72 hours later.'},

      out_conscious: {type:'result', style:'warning', text:'DROWNING VICTIM — CONSCIOUS AND BREATHING\n\n"Secondary drowning" or delayed pulmonary edema can develop 1–72 hours after submersion, even in victims who appear well.\n\nAll conscious drowning victims must be observed for at least 6 hours and ideally evacuated.\n\nImmediate care:\n1. Move to warmth — drowning victims are hypothermic; wind causes rapid heat loss\n2. Remove wet clothing, replace with dry blankets\n3. Supplemental O2 if available — even if SpO2 seems OK\n4. Lay flat initially, elevate head slightly if breathing is difficult\n5. Warm fluids if fully alert and not vomiting\n6. Do NOT offer alcohol "to warm up" — causes vasodilation and heat loss\n\nDischarge criteria (all must be met):\n- GCS 15 (fully alert, oriented)\n- Normal breathing and O2 sat\n- No cough, chest tightness, or frothy sputum\n- Asymptomatic for 6 hours after submersion\n\nWarning signs of secondary drowning (EVACUATE if any develop):\n- Increasing shortness of breath\n- Persistent cough, especially with frothy or pink-tinged sputum\n- Chest tightness\n- Fatigue, confusion, irritability (especially in children)\n- Falling O2 saturation\n\nChildren are at higher risk for secondary drowning than adults.'},

      cold_water: {type:'result', style:'danger', text:'COLD WATER SUBMERSION — "Cold Water Drowning"\n\nCold water dramatically changes drowning outcomes — both positively and negatively.\n\nThe "cold water diving reflex" (Mammalian Diving Reflex):\n- Submersion in cold water triggers powerful reflex vasoconstriction and bradycardia\n- Oxygen demand of organs drops dramatically\n- Brain can survive much longer periods of submersion in cold water\n- Children have stronger reflex than adults\n\nRule: "No one is dead until they are warm and dead"\n- Victims submerged in very cold water (below 50°F/10°C) for up to 30+ minutes have survived with full neurological recovery after CPR and rewarming\n- Do NOT stop resuscitation until core temperature reaches 35°C (95°F)\n\nManagement:\n1. Remove from water, lay flat\n2. Begin CPR if no pulse/not breathing (modified protocol: 5 rescue breaths first)\n3. Minimize movement — cold myocardium is irritable, rough handling can trigger VFib\n4. Remove wet clothing gently\n5. Wrap in blankets — insulate from ground (ground steals heat rapidly)\n6. Warm center first: torso, not extremities (rewarming extremities first causes cold blood to rush to core — "rewarming shock")\n7. Warm moist oxygen if available; warm IV fluids if available\n\nCore temperature thresholds:\n- 32–35°C: Mild — shivering, alert\n- 28–32°C: Moderate — no shivering, confusion\n- &lt;28°C: Severe — potentially cardiac arrest; all cardiac interventions may fail until rewarmed\n- &lt;24°C: Critical\n\nEvacuate: All cold-water submersion victims need hospital care for rewarming and cardiac monitoring.'},
    }
  },
];

let _guideContext = null;

async function loadGuideContext() {
  try {
    _guideContext = await safeFetch('/api/guides/context', {}, null);
  } catch(e) {}
}

function enrichGuideText(text) {
  if (!_guideContext) return text;
  const ctx = _guideContext;
  const s = ctx.summary;
  // Replace inventory placeholders
  text = text.replace(/\{water_count\}/g, s.water_items || 0);
  text = text.replace(/\{medical_count\}/g, s.medical_items || 0);
  text = text.replace(/\{food_count\}/g, s.food_items || 0);
  text = text.replace(/\{total_contacts\}/g, s.total_contacts || 0);
  text = text.replace(/\{medic_name\}/g, s.medic || 'No medic assigned');
  text = text.replace(/\{comms_officer\}/g, s.comms_officer || 'No comms officer assigned');

  // Generate inventory snippet for a category
  text = text.replace(/\{inv:([\w]+)\}/g, (_, cat) => {
    const items = (ctx.inventory[cat] || []).slice(0, 5);
    if (!items.length) return `No ${cat} items in inventory`;
    return items.map(i => `${i.name}: ${i.qty} ${i.unit}`).join(', ');
  });

  // Generate contact snippet for a role
  text = text.replace(/\{contact:([\w]+)\}/g, (_, role) => {
    const people = (ctx.contacts[role.toLowerCase()] || []);
    if (!people.length) return `No ${role} contacts`;
    return people.map(c => c.name + (c.callsign ? ` (${c.callsign})` : '')).join(', ');
  });

  return text;
}

let _guideHistory = [];
let _currentGuide = null;
let _currentNode = null;

function renderGuideSelector() {
  const el = document.getElementById('guide-selector');
  el.innerHTML = DECISION_GUIDES.map(g => `
    <button type="button" class="guide-tile" data-prep-action="start-guide" data-guide-id="${g.id}">
      <span class="guide-tile-title">
        <span class="guide-tile-icon" aria-hidden="true">${g.icon}</span>
        <span class="guide-tile-title-text">${g.title}</span>
      </span>
      <span class="guide-tile-copy">${g.desc}</span>
    </button>
  `).join('');
  document.getElementById('guide-active').style.display = 'none';
  document.getElementById('guide-selector').style.display = 'grid';
}

async function startGuide(id) {
  _currentGuide = DECISION_GUIDES.find(g => g.id === id);
  if (!_currentGuide) return;
  _guideHistory = [];
  _currentNode = 'start';
  document.getElementById('guide-selector').style.display = 'none';
  document.getElementById('guide-active').style.display = 'block';
  await loadGuideContext();
  renderGuideNode();
}

function renderGuideNode() {
  const node = _currentGuide.nodes[_currentNode];
  if (!node) return;
  const card = document.getElementById('guide-card');
  const backBtn = document.getElementById('guide-back-btn');
  backBtn.style.display = _guideHistory.length > 0 ? 'inline-flex' : 'none';

  // Breadcrumb
  const crumb = document.getElementById('guide-breadcrumb');
  const trail = [_currentGuide.title, ..._guideHistory.map(h => {
    const n = _currentGuide.nodes[h.from];
    const opt = n?.options?.find(o => o.next === h.to);
    return opt?.label?.slice(0, 30) || '…';
  })];
  crumb.innerHTML = trail.map((t, i) => `<span class="guide-crumb${i === trail.length-1 ? ' guide-crumb-active' : ''}">${escapeHtml(t)}</span>`).join(' <span class="guide-crumb-sep">&#8250;</span> ');

  // Context strip
  const ctxStrip = document.getElementById('guide-context-strip');
  if (_guideContext && _guideContext.summary) {
    const s = _guideContext.summary;
    const parts = [];
    if (s.water_items) parts.push(`${s.water_items} water items`);
    if (s.medical_items) parts.push(`${s.medical_items} medical items`);
    if (s.medic) parts.push(`Medic: ${escapeHtml(s.medic)}`);
    if (s.comms_officer) parts.push(`Comms: ${escapeHtml(s.comms_officer)}`);
    if (parts.length) {
      ctxStrip.innerHTML = `\u{1F4CB} Your resources: ${parts.join(' \u2022 ')}`;
      ctxStrip.style.display = 'block';
    } else {
      ctxStrip.style.display = 'none';
    }
  }

  if (node.type === 'question') {
    card.innerHTML = `
      <div class="guide-question-title">${escapeHtml(enrichGuideText(node.text))}</div>
      <div>${node.options.map(opt => `
        <button type="button" class="guide-option" data-prep-action="choose-guide-node" data-guide-node="${opt.next}">${escapeHtml(opt.label)}</button>
      `).join('')}</div>
    `;
  } else if (node.type === 'result') {
    const lines = enrichGuideText(node.text).split('\n').map(l => escapeHtml(l)).join('<br>');
    card.innerHTML = `
      <div class="guide-result ${node.style || 'info'}">
        <div class="guide-result-title">${escapeHtml(_currentGuide.title)} — Result</div>
        <div class="guide-result-copy">${lines}</div>
      </div>
      <div class="guide-result-actions">
        <button type="button" class="btn btn-sm btn-primary" data-prep-action="guide-start-over">Start Over</button>
        <button type="button" class="btn btn-sm" data-prep-action="guide-close">Back to Guides</button>
      </div>
    `;
  }
}

function guideChoose(nextNode) {
  _guideHistory.push({from: _currentNode, to: nextNode});
  _currentNode = nextNode;
  renderGuideNode();
}

function guideBack() {
  if (!_guideHistory.length) return;
  const prev = _guideHistory.pop();
  _currentNode = prev.from;
  renderGuideNode();
}

function guideClose() {
  _currentGuide = null;
  _currentNode = null;
  _guideHistory = [];
  renderGuideSelector();
}

function guideAskAI() {
  if (!_currentGuide || !_currentNode) return;
  const node = _currentGuide.nodes[_currentNode];
  const context = node.type === 'result' ? node.text : node.text;
  const msg = `I'm using the "${_currentGuide.title}" guide and I'm at this step: "${context.slice(0, 200)}..."\n\nGive me more detail and practical advice for this specific situation.`;
  document.querySelector('[data-tab="ai-chat"]')?.click();
  setTimeout(() => {
    document.getElementById('chat-input').value = msg;
    sendChat();
  }, 300);
}

function guidePrint() {
  if (!_currentGuide) return;
  // Build the full path taken
  let html = `<h2>${_currentGuide.title}</h2>`;
  let nodeId = 'start';
  for (const step of _guideHistory) {
    const node = _currentGuide.nodes[step.from];
    if (node.type === 'question') {
      const chosen = node.options.find(o => o.next === step.to);
      html += `<p><strong>Q:</strong> ${node.text}</p><p><strong>A:</strong> ${chosen?.label || '?'}</p><hr>`;
    }
    nodeId = step.to;
  }
  const finalNode = _currentGuide.nodes[nodeId];
  if (finalNode?.type === 'result') {
    html += `<div class="guide-print-result"><strong>Result:</strong><br>${finalNode.text.replace(/\n/g, '<br>')}</div>`;
  }
openAppFrameHTML(`${_currentGuide.title} — Decision Path`, `<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{font-family:'Segoe UI',sans-serif;padding:20px 40px;max-width:800px;margin:0 auto;line-height:1.7;font-size:13px;}h2{border-bottom:1px solid #ccc;padding-bottom:8px;}hr{border:none;border-top:1px solid #ddd;margin:12px 0;}.guide-print-result{background:#f0f0f0;padding:12px;border-radius:8px;margin-top:12px;}.guide-print-footer{margin-top:20px;font-size:10px;color:#999;}@media print{body{padding:10px;}}</style></head><body>${html}<p class="guide-print-footer">Generated by NOMAD Field Desk — ${new Date().toLocaleString()}</p></body></html>`);
}

/* ─── Proactive Alert System ─── */
let _alertBarVisible = false;
let _lastAlertCount = 0;

async function loadAlerts() {
  const badge = document.getElementById('alert-badge');
  const bar = document.getElementById('alert-bar');
  const items = document.getElementById('alert-items');
  const count = document.getElementById('alert-count');
  if (!badge && !bar && !items && !count) return;
  try {
    const alerts = await safeFetch('/api/alerts', {}, null);
    if (!Array.isArray(alerts)) return;

    if (!alerts.length) {
      if (badge) badge.style.display = 'none';
      if (_alertBarVisible && items && !items.innerHTML.includes('All clear')) {
        items.innerHTML = '<div class="alert-clear-state">All clear. No active alerts.</div>';
      }
      if (count) count.textContent = '';
      return;
    }

    // Update badge
    if (badge) {
      badge.style.display = 'block';
      badge.textContent = alerts.length;
    }
    if (count) count.textContent = `(${alerts.length})`;

    // Notify on NEW alerts (ones we haven't seen before)
    if (alerts.length > _lastAlertCount && _lastAlertCount > 0) {
      const newest = alerts[0];
      toast(`Alert: ${newest.title}`, newest.severity === 'critical' ? 'error' : 'warning');
sendNotification('NOMAD Alert', newest.title);
      if (newest.severity === 'critical') playAlertSound('broadcast');
    }
    _lastAlertCount = alerts.length;

    // Auto-show bar on first critical alert
    if (bar && !_alertBarVisible && alerts.some(a => a.severity === 'critical')) {
      _alertBarVisible = true;
      bar.style.display = 'block';
    }

    // Render alert items
    const sevOrder = {critical: 0, warning: 1, info: 2};
    alerts.sort((a, b) => (sevOrder[a.severity] || 9) - (sevOrder[b.severity] || 9));
    if (items) {
      items.innerHTML = alerts.map(a => `
        <div class="alert-item">
          <span class="alert-sev ${a.severity}">${a.severity}</span>
          <div class="alert-body">
            <div class="alert-title">${escapeHtml(a.title)}</div>
            <div class="alert-msg">${escapeHtml(a.message)}</div>
          </div>
          <button type="button" class="alert-dismiss alert-dismiss-link" data-shell-action="snooze-alert" data-alert-id="${a.id}" title="Snooze 1hr">snooze</button>
          <button type="button" class="alert-dismiss" data-shell-action="dismiss-alert" data-alert-id="${a.id}" title="Dismiss" aria-label="Dismiss alert">x</button>
        </div>
      `).join('');
    }
    // Append predictive alerts
    if (items) loadPredictiveAlerts();
  } catch(e) {}
}

function toggleAlertBar() {
  const bar = document.getElementById('alert-bar');
  if (!bar) return;
  _alertBarVisible = !_alertBarVisible;
  bar.style.display = _alertBarVisible ? 'block' : 'none';
  if (_alertBarVisible) loadAlerts();
}

async function snoozeAlert(id) {
  try {
    await apiPost(`/api/alerts/${id}/dismiss`, {});
    toast('Alert snoozed for 1 hour', 'info');
    loadAlerts();
  } catch(e) {
    toast(e?.data?.error || 'Failed to snooze alert', 'error');
  }
}

async function dismissAlert(id) {
  try {
    await apiPost(`/api/alerts/${id}/dismiss`, {});
    loadAlerts();
  } catch(e) {
    toast(e?.data?.error || 'Failed to dismiss alert', 'error');
  }
}

async function dismissAllAlerts() {
  try {
    await apiPost('/api/alerts/dismiss-all');
    const panel = document.getElementById('alert-summary-panel');
    if (panel) panel.style.display = 'none';
    loadAlerts();
    toast('All alerts dismissed', 'info');
  } catch(e) { toast('Failed to dismiss alerts', 'error'); }
}

async function generateAlertSummary() {
  const btn = document.getElementById('alert-summary-btn');
  const panel = document.getElementById('alert-summary-panel');
  btn.setAttribute('aria-busy', 'true');
  btn.disabled = true;
  panel.style.display = 'block';
  panel.textContent = 'Generating AI situation summary...';
  try {
    const d = await apiPost('/api/alerts/generate-summary');
    panel.innerHTML = '<strong class="text-accent">AI Situation Summary:</strong><br>' + escapeHtml(d.summary);
  } catch(e) {
    panel.textContent = 'Failed to generate summary';
  }
  btn.removeAttribute('aria-busy');
  btn.disabled = false;
}

/* ─── Status Strip ─── */
async function updateStatusStrip() {
  const hasVisibleStrip = Array.from(document.querySelectorAll('.status-strip'))
    .some(candidate => candidate && !candidate.hidden && getComputedStyle(candidate).display !== 'none');
  if (!hasVisibleStrip) return;
  try {
    const results = await Promise.allSettled([
      safeFetch('/api/services', {}, []),
      safeFetch('/api/inventory/summary', {}, {total:0}),
      safeFetch('/api/contacts', {}, []),
      safeFetch('/api/alerts', {}, []),
    ]);
    const [svcs, inv, contacts, alerts] = results.map(r => r.value);
    const running = svcs.filter(s=>s.running).length;
    const installed = svcs.filter(s=>s.installed).length;
    const dotCls = (tone) => tone ? ` ss-dot--${tone}` : '';
    const el = (id,html) => { const e = document.getElementById(id); if(e) e.innerHTML = html; };
    el('ss-services', `<span class="ss-dot${dotCls(running>0?'green':'muted')}"></span>Services: <strong>${running}/${installed}</strong>`);
    el('ss-inventory', `<span class="ss-dot${dotCls(inv.low_stock>0?'red':'accent')}"></span>Supplies: <strong>${inv.total||0}</strong>${inv.low_stock>0?` <span class="text-danger">(${inv.low_stock} low)</span>`:''}`);
    el('ss-contacts', `<span class="ss-dot${dotCls(contacts.length>0?'green':'muted')}"></span>Contacts: <strong>${contacts.length||0}</strong>`);
    el('ss-alerts', `<span class="ss-dot${dotCls(alerts.length>0?'orange':'green')}"></span>Alerts: <strong>${alerts.length}</strong>`);
  } catch(e) {}
  // Update situation board status
  try {
    const allSettings = await safeFetch('/api/settings', {}, {});
    const sitRaw = allSettings['sit_board'];
    if (sitRaw) {
      const sit = safeJsonParse(sitRaw, {});
      const levels = Object.values(sit || {});
      const worst = levels.includes('red') ? 'red' : levels.includes('yellow') ? 'yellow' : 'green';
      const labels = {red:'Alert',yellow:'Caution',green:'Normal'};
      const dotClasses = {red:'ss-dot--red',yellow:'ss-dot--orange',green:'ss-dot--green'};
      const el2 = document.getElementById('ss-situation');
      if (el2) { el2.innerHTML = `<span class="ss-dot ${dotClasses[worst]}"></span>Status: <strong>${labels[worst]}</strong>`; }
    }
  } catch(e) {}
  // Update clock
  const now = new Date();
  const timeEl = document.getElementById('ss-time');
  if (timeEl) {
    const h = String(now.getHours()).padStart(2,'0');
    const m = String(now.getMinutes()).padStart(2,'0');
    const dateStr = now.toLocaleDateString([], {weekday:'short',month:'short',day:'numeric'});
    timeEl.textContent = `${dateStr} ${h}${m}L`;
  }
}

/* ─── Tab Badges ─── */
function updateTabBadges() {
  const preparednessBadge = document.getElementById('badge-preparedness');
  const mapsBadge = document.getElementById('badge-maps');
  const mediaBadge = document.getElementById('badge-media');
  const aiBadge = document.getElementById('badge-ai-chat');
  if (!preparednessBadge && !mapsBadge && !mediaBadge && !aiBadge) return;

  // Use live dashboard data if available (avoids extra API calls)
  const d = _liveDashData;

  // Preparedness badge: low stock + expiring + active alerts
  if (d && (preparednessBadge || mapsBadge || mediaBadge)) {
    const inv = d.inventory || {};
    const alerts = d.alerts || {};
    const lowCount = (inv.low_stock || 0) + (inv.expiring_30d || 0) + (alerts.active || 0);
    if (preparednessBadge) {
      if (lowCount > 0) { preparednessBadge.textContent = lowCount; preparednessBadge.style.display = ''; preparednessBadge.className = 'tab-badge' + (alerts.critical > 0 ? ' red' : ''); }
      else { preparednessBadge.style.display = 'none'; }
    }
    // Maps badge: waypoint count
    if (mapsBadge) { mapsBadge.style.display = 'none'; }
    // Media badge: hidden (no count needed)
    if (mediaBadge) { mediaBadge.style.display = 'none'; }
  } else if (preparednessBadge) {
    // Fallback: fetch from individual endpoints
    Promise.all([
      safeFetch('/api/inventory/summary', {}, {}),
      safeFetch('/api/alerts', {}, []),
    ]).then(([inv, alerts]) => {
      const lowCount = (inv.low_stock || 0) + (inv.expired || 0) + (Array.isArray(alerts) ? alerts.length : 0);
      if (lowCount > 0) { preparednessBadge.textContent = lowCount; preparednessBadge.style.display = ''; preparednessBadge.className = 'tab-badge'; }
      else { preparednessBadge.style.display = 'none'; }
    });
  }

  // AI Chat badge: green dot if Ollama running, red dot if not
  if (!aiBadge) return;
  const applyAiBadge = (svcs) => {
    if (!Array.isArray(svcs)) return;
    const ollama = svcs.find(s => s.id === 'ollama');
    aiBadge.style.display = '';
    aiBadge.innerHTML = '&#9679;';
    aiBadge.className = 'tab-badge ' + (ollama && ollama.running ? 'green' : 'red');
  };
  if (typeof _lastServicesData !== 'undefined' && Array.isArray(_lastServicesData) && _lastServicesData.length) {
    applyAiBadge(_lastServicesData);
    return;
  }
  safeFetch('/api/services', {}, []).then(applyAiBadge);
}

/* ─── Customize Panel ─── */
const CUSTOMIZE_SECTION_ALIASES = {
  'search-bar': 'services-launch',
  'services-grid': 'services-console',
  'copilot-dock': null,
};

function normalizeCustomizeSectionId(sectionId) {
  if (Object.prototype.hasOwnProperty.call(CUSTOMIZE_SECTION_ALIASES, sectionId)) {
    return CUSTOMIZE_SECTION_ALIASES[sectionId];
  }
  return sectionId;
}

function normalizeCustomizeState(state) {
  const hiddenTabs = Array.isArray(state?.hiddenTabs)
    ? state.hiddenTabs.filter(Boolean)
    : [];
  const hiddenSections = Array.isArray(state?.hiddenSections)
    ? state.hiddenSections
      .map(normalizeCustomizeSectionId)
      .filter(Boolean)
    : [];
  return {
    hiddenTabs: Array.from(new Set(hiddenTabs)),
    hiddenSections: Array.from(new Set(hiddenSections)),
  };
}

function getStoredCustomizeState() {
  return normalizeCustomizeState(readJsonStorage(localStorage, 'nomad-customize', {}));
}

function setCustomizeTabVisibility(tabId, visible) {
  const tabBtn = document.querySelector(`.tab[data-tab="${tabId}"]`);
  if (tabBtn) tabBtn.style.display = visible ? '' : 'none';
  const subMenu = document.querySelector(`.sidebar-sub[data-parent="${tabId}"]`);
  if (subMenu) subMenu.style.display = visible ? '' : 'none';
}

function setCustomizeSectionVisibility(sectionId, visible) {
  const resolvedId = normalizeCustomizeSectionId(sectionId);
  if (!resolvedId) return;
  const el = document.getElementById(resolvedId);
  if (el) el.style.display = visible ? '' : 'none';
  if (typeof syncViewportChrome === 'function') {
    requestAnimationFrame(syncViewportChrome);
  }
}

function applyCustomizeState(state) {
  const normalized = normalizeCustomizeState(state);
  document.querySelectorAll('[data-cust-tab]').forEach(cb => {
    const hidden = normalized.hiddenTabs.includes(cb.dataset.custTab);
    cb.checked = !hidden;
    setCustomizeTabVisibility(cb.dataset.custTab, !hidden);
  });
  document.querySelectorAll('[data-cust-section]').forEach(cb => {
    const hidden = normalized.hiddenSections.includes(cb.dataset.custSection);
    cb.checked = !hidden;
    setCustomizeSectionVisibility(cb.dataset.custSection, !hidden);
  });
}

function toggleCustomizePanel() {
  const panel = document.getElementById('customize-panel');
  const overlay = document.getElementById('customize-overlay');
  if (!panel || !overlay) return;
  const isOpen = panel.classList.contains('open');
  if (isOpen) {
    panel.classList.remove('open');
    overlay.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    overlay.setAttribute('aria-hidden', 'true');
    setTimeout(() => {
      if (!panel.classList.contains('open')) panel.style.display = 'none';
    }, 300);
  } else {
    panel.style.display = 'block';
    panel.setAttribute('aria-hidden', 'false');
    overlay.setAttribute('aria-hidden', 'false');
    overlay.classList.add('open');
    requestAnimationFrame(() => {
      panel.classList.add('open');
      const closeBtn = panel.querySelector('.customize-close-btn');
      if (closeBtn) closeBtn.focus();
    });
    updateCustomizeTheme();
    updateCustomizeZoom();
    updateCustomizeDensity();
    updateCustomizeMode();
    loadCustomizeState();
  }
}

function updateCustomizeTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'nomad';
  document.querySelectorAll('.customize-theme-card').forEach(c => c.classList.toggle('active', c.dataset.theme === current));
}

function updateCustomizeZoom() {
  const current = localStorage.getItem('nomad-ui-zoom') || 'default';
  ['small','default','large','xlarge'].forEach(z => {
    const btn = document.getElementById('cust-zoom-' + z);
    if (btn) btn.className = current === z ? 'btn btn-sm btn-primary' : 'btn btn-sm';
  });
}

function updateCustomizeDensity() {
  const current = localStorage.getItem('nomad-density') || 'compact';
  ['ultra', 'compact', 'comfortable'].forEach(level => {
    const btn = document.getElementById('cust-density-' + level);
    if (btn) btn.className = current === level ? 'btn btn-sm btn-primary' : 'btn btn-sm';
  });
}

function updateCustomizeMode() {
  const current = localStorage.getItem('nomad-mode') || 'command';
  document.querySelectorAll('[data-cust-mode]').forEach(el => {
    const isActive = el.dataset.custMode === current;
    const check = el.querySelector('.cust-mode-check');
    if (check) check.style.display = isActive ? 'inline' : 'none';
    el.classList.toggle('is-active', isActive);
  });
}

function toggleSidebarItem(checkbox) {
  const tabId = checkbox.dataset.custTab;
  const visible = checkbox.checked;
  setCustomizeTabVisibility(tabId, visible);
  saveCustomizeState();
}

function toggleHomeSection(checkbox) {
  const sectionId = checkbox.dataset.custSection;
  const visible = checkbox.checked;
  setCustomizeSectionVisibility(sectionId, visible);
  saveCustomizeState();
}

function saveCustomizeState() {
  const state = normalizeCustomizeState({
    hiddenTabs: [],
    hiddenSections: [],
  });
  document.querySelectorAll('[data-cust-tab]').forEach(cb => {
    if (!cb.checked) state.hiddenTabs.push(cb.dataset.custTab);
  });
  document.querySelectorAll('[data-cust-section]').forEach(cb => {
    if (!cb.checked) state.hiddenSections.push(cb.dataset.custSection);
  });
  localStorage.setItem('nomad-customize', JSON.stringify(normalizeCustomizeState(state)));
}

function loadCustomizeState() {
  applyCustomizeState(getStoredCustomizeState());
}

function resetCustomization() {
  localStorage.removeItem('nomad-customize');
  applyCustomizeState({});
  // Reset theme and zoom
  setTheme('nomad');
  setUIZoom('default');
  setDensity('compact');
  setMode('command');
  updateCustomizeTheme();
  updateCustomizeZoom();
  updateCustomizeDensity();
  updateCustomizeMode();
  toast('All customizations reset to defaults', 'success');
}

// Keyboard shortcut: Escape closes customize panel
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const panel = document.getElementById('customize-panel');
    if (panel && panel.classList.contains('open')) { toggleCustomizePanel(); e.preventDefault(); }
  }
});

// Apply saved customization on page load
document.addEventListener('DOMContentLoaded', () => {
  applyCustomizeState(getStoredCustomizeState());
});
