# Project N.O.M.A.D. — Data Sources Reference

> **Purpose:** Catalog of freely available, downloadable datasets that can be bundled with or connected to NOMAD to power its modules. Every source listed is **offline-compatible** — downloadable as flat files, no API key required for the bundled data.
> **Generated:** 2026-04-13 | **Updated:** 2026-04-13 (enrichment pass + §54-§63 expansion — regional, transportation, permaculture, performance, governance data sources)
> **Organized by:** Module area → data source → format, size, license, fields, integration notes

---

## Table of Contents

1. [Food, Nutrition & Product Identification](#1-food-nutrition--product-identification)
2. [Medical, Pharmaceutical & Toxicology](#2-medical-pharmaceutical--toxicology)
3. [Geography, Maps & Elevation](#3-geography-maps--elevation)
4. [Weather, Climate & Solar](#4-weather-climate--solar)
5. [Radio, Communications & Frequencies](#5-radio-communications--frequencies)
6. [Agriculture, Garden & Soil](#6-agriculture-garden--soil)
7. [Wildlife, Foraging & Hunting](#7-wildlife-foraging--hunting)
8. [Hazards, Threats & Emergency Management](#8-hazards-threats--emergency-management)
9. [Military, Tactical & Reference](#9-military-tactical--reference)
10. [Astronomy, Navigation & Timekeeping](#10-astronomy-navigation--timekeeping)
11. [Energy, Solar & Wind](#11-energy-solar--wind)
12. [Financial & Precious Metals](#12-financial--precious-metals)
13. [Offline Knowledge Libraries (ZIM/Kiwix)](#13-offline-knowledge-libraries-zimkiwix)
14. [3D Printing & Fabrication](#14-3d-printing--fabrication)
15. [Vehicle & Equipment](#15-vehicle--equipment)
16. [Demographic & Infrastructure](#16-demographic--infrastructure)
17. [Localization, Regional & Property Assessment](#17-localization-regional--property-assessment)
18. [Alternative Transportation & Pack Animals](#18-alternative-transportation--pack-animals)
19. [Permaculture, Mycology & Long-Term Agriculture](#19-permaculture-mycology--long-term-agriculture)
20. [Human Performance & Sleep Science](#20-human-performance--sleep-science)
21. [Dispute Resolution & Group Governance](#21-dispute-resolution--group-governance)
22. [Integration Priority Matrix](#22-integration-priority-matrix)

---

## 1. Food, Nutrition & Product Identification

### 1.1 USDA FoodData Central (FDC)
- **Source:** U.S. Department of Agriculture
- **URL:** https://fdc.nal.usda.gov/download-datasets
- **Format:** CSV and JSON bulk downloads
- **Size:** ~500 MB (Foundation Foods + SR Legacy combined)
- **License:** Public domain (US Government work)
- **Key datasets:**
  - **SR Legacy** — 7,793 foods with full nutrient profiles (150+ nutrients per food)
  - **Foundation Foods** — 2,195 analytically-determined foods with enhanced metadata
  - **Branded Foods** — 2M+ branded products with UPC codes, serving sizes, nutrients
- **Fields:** food_name, fdc_id, brand_owner, gtin_upc, serving_size, calories, protein, fat, carbs, fiber, sugars, sodium, vitamin_a, vitamin_c, vitamin_d, calcium, iron, potassium, zinc, plus 140+ other nutrients
- **Integration:** Merge with existing UPC database. Enable nutritional gap analysis (§51.1), calorie tracking (§2.1), and micronutrient deficiency prediction. The Branded Foods dataset maps UPC → nutritional data directly.
- **Bundle strategy:** Ship SR Legacy (~25 MB compressed) for offline nutrition lookup. Branded Foods is too large (2GB+) but can be offered as downloadable expansion.

### 1.2 Open Food Facts
- **Source:** Open Food Facts (community-maintained)
- **URL:** https://world.openfoodfacts.org/data
- **Format:** CSV, JSONL, MongoDB dump
- **Size:** ~7 GB uncompressed (CSV), ~2 GB compressed
- **License:** Open Database License (ODbL)
- **Fields:** barcode, product_name, brands, categories, quantity, serving_size, energy_kcal, fat, saturated_fat, carbohydrates, sugars, fiber, proteins, salt, sodium, plus nutri-score, nova_group, ecoscore
- **Coverage:** 3M+ products globally, strongest in US/EU
- **Integration:** Barcode scan → auto-populate inventory item name, brand, category, nutrition, serving size. Power the "Due Score" recipe prioritization from Grocy.
- **Bundle strategy:** Extract US-only products (~800K items, ~400 MB compressed) for offline use.

### 1.3 Open Product Data (UPC Database)
- **Source:** Open Product Data / UPCitemdb.com / barcodelookup.com
- **URL:** https://openproductdata.net (community), or https://www.upcitemdb.com/wp/docs/main/
- **Format:** CSV, JSON API (for building local cache)
- **License:** Varies — Open Product Data is CC0, commercial databases require API key
- **Fields:** upc/ean, title, brand, description, category, images
- **Integration:** Fallback UPC lookup when Open Food Facts doesn't have a match. Fill product name/brand even for non-food items (batteries, gear, tools).

### 1.4 Food Shelf Life Database
- **Source:** USDA FoodKeeper (via FoodSafety.gov / FSIS)
- **URL (direct JSON):** https://www.fsis.usda.gov/shared/data/EN/foodkeeper.json
- **URL (app page):** https://www.foodsafety.gov/keep-food-safe/foodkeeper-app
- **Format:** JSON (single file, ready to parse — no API key needed)
- **Size:** ~500 KB
- **License:** Public domain / CC0 (US Government)
- **Fields:** product_name, category_id, pantry_min_days, pantry_max_days, pantry_metric, pantry_tips, refrigerate_min_days, refrigerate_max_days, refrigerate_metric, freeze_min_days, freeze_max_days, freeze_metric, dop_pantry_min, dop_pantry_max, dop_refrigerate_min, dop_refrigerate_max, cooking_tips
- **Coverage:** 650+ food products with storage duration by method (pantry, refrigerator, freezer), both unopened and after-opening
- **Integration:** Auto-set shelf life when adding inventory items. Power expiration predictions. Generate "use soon" alerts based on storage method. Direct JSON download makes this trivial to bundle — single fetch, parse, and seed into SQLite.

### 1.5 USDA Canning Guidelines
- **Source:** USDA Complete Guide to Home Canning (National Center for Home Food Preservation)
- **URL:** https://nchfp.uga.edu/publications/publications_usda.html
- **Format:** PDF (would need to extract into structured JSON)
- **License:** Public domain (US Government)
- **Content:** Pressure canning times/pressures by altitude, water bath processing times, tested recipes, safety guidelines
- **Integration:** Power the Food Preservation Batch Tracker (§1.7). Auto-calculate processing time based on altitude, jar size, and food type.

### 1.6 Seed Viability & Germination Data
- **Source:** Oregon State University Extension / various cooperative extensions
- **URL:** Multiple cooperative extension publications
- **Format:** Tables (need to structure as JSON)
- **Fields:** species, viability_years, optimal_storage_temp, optimal_humidity, germination_rate_by_age, days_to_germination
- **Coverage:** ~80 common garden species
- **Integration:** Expand existing SEED_VIABILITY constant in garden.py. Add germination rate degradation curves. Alert when stored seeds are past peak viability.
- **Already in project:** Basic seed viability dict in web/blueprints/garden.py (line 24) — 20 species. Can be expanded 4x with extension data.

### 1.7 Kew Seed Information Database (SID)
- **Source:** Royal Botanic Gardens, Kew
- **URL:** https://data.kew.org/sid/
- **Format:** CSV export (searchable online, downloadable subsets)
- **Size:** ~20 MB
- **License:** Free for non-commercial use (Creative Commons)
- **Fields:** species, family, seed_weight_mg, dispersal_type, storage_behavior (orthodox/recalcitrant/intermediate), germination_requirements, germination_temperature_C, dormancy_class, longevity_index
- **Coverage:** 42,000+ species with seed storage and germination data
- **Integration:** Dramatically expand seed viability modeling. Orthodox vs recalcitrant classification determines whether seeds can be stored long-term at all. Longevity index gives science-backed viability curves beyond the simple years in current SEED_VIABILITY. Germination temperature requirements for season planning.

### 1.8 PRISM Hardiness Zone by ZIP Code
- **Source:** PRISM Climate Group, Oregon State University
- **URL:** https://prism.oregonstate.edu/projects/plant_hardiness_zones.php
- **Format:** CSV (ZIP code → zone mapping)
- **Size:** ~3 MB
- **License:** Free for non-commercial use
- **Fields:** zip_code, hardiness_zone, min_temp_f, max_temp_f
- **Coverage:** All US ZIP codes mapped to USDA hardiness zones
- **Integration:** Lightweight alternative to full GIS shapefile (§6.1). User enters ZIP code → instant hardiness zone lookup without needing GIS libraries. Much simpler to bundle than the 50 MB shapefile.

---

## 2. Medical, Pharmaceutical & Toxicology

### 2.1 FDA National Drug Code (NDC) Directory
- **Source:** U.S. Food and Drug Administration
- **URL:** https://www.fda.gov/drugs/drug-approvals-and-databases/national-drug-code-directory
- **Format:** CSV (two files: Products + Packages)
- **Size:** ~50 MB
- **License:** Public domain (US Government)
- **Fields:** product_ndc, product_name, labeler_name, active_ingredients, strength, dosage_form, route, dea_schedule, package_ndc, package_description
- **Coverage:** 150,000+ marketed drug products
- **Integration:** Drug identification by NDC code. Medication inventory with proper categorization. Controlled substance awareness flagging.

### 2.2 RxNorm (Drug Nomenclature)
- **Source:** National Library of Medicine (NLM)
- **URL:** https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html
- **Format:** RRF (pipe-delimited text files)
- **Size:** ~300 MB uncompressed
- **License:** UMLS license (free, requires registration)
- **Fields:** rxcui, name, tty (term type), rxaui, sab (source), suppress, generic_name, brand_name, ingredient, dose_form, strength
- **Integration:** Map between brand names and generic equivalents. "You're running low on Advil — generic ibuprofen 200mg is the same thing."

### 2.3 DailyMed Drug Label Database
- **Source:** National Library of Medicine
- **URL:** https://dailymed.nlm.nih.gov/dailymed/spl-resources-all-drug-labels.cfm
- **Format:** XML (SPL format), also JSON via API
- **Size:** ~50 GB full (massive), but indexable subsets available
- **License:** Public domain
- **Fields:** drug_name, active_ingredients, inactive_ingredients, indications, dosage_administration, warnings, contraindications, adverse_reactions, drug_interactions, storage_conditions
- **Integration:** Full drug information lookup. Power the drug interactions checker (expand beyond current 20-pair DRUG_INTERACTIONS constant). Extract storage conditions for medical supply shelf life.
- **Bundle strategy:** Extract essential fields for top 500 OTC and common prescription drugs (~10 MB).

### 2.4 Drug Interaction Databases
- **Source:** DrugBank Open Data / NLM Drug Interaction API
- **URL:** https://go.drugbank.com/releases/latest#open-data
- **Format:** CSV (drug_interactions.csv in the open data release)
- **Size:** ~50 MB (open subset — drug_interactions.csv alone is ~40 MB with 2.5M+ rows)
- **License:** CC BY-NC 4.0 (non-commercial) for DrugBank Open
- **Key files in open release:**
  - `drugbank_vocabulary.csv` — Drug names, CAS numbers, UNII codes
  - `drug_interactions.csv` — 2.5M+ interaction pairs with descriptions
  - `drug_target_identifiers.csv` — Drug-target mappings
- **Fields:** drugbank_id, name, drug_1, drug_2, interaction_description
- **Integration:** Massive expansion of existing drug_interactions table. Currently 20 pairs in medical.py — DrugBank Open has 2.5M+ interaction pairs. Even extracting just the top 500 OTC/common drugs yields ~50K interaction pairs vs current 20.

### 2.5 ICD-10-CM Codes
- **Source:** Centers for Medicare & Medicaid Services (CMS)
- **URL:** https://www.cms.gov/medicare/coding-billing/icd-10-codes
- **Format:** XML, CSV, PDF
- **Size:** ~20 MB
- **License:** Public domain (US Government)
- **Fields:** code, description, chapter, category, subcategory, laterality, extension
- **Coverage:** 72,000+ diagnosis codes
- **Integration:** Standardized condition coding for patient records. Searchable condition database. Power the medical reference search.

### 2.6 Poisonous Plants Database (USDA)
- **Source:** USDA Animal and Plant Health Inspection Service / various poison control references
- **URL:** https://www.fs.usda.gov/wildflowers/ethnobotany/Mind_and_Spirit/poisonous.shtml
- **Format:** Need to compile from multiple sources into structured JSON
- **Fields:** common_name, scientific_name, toxic_parts, toxin_type, symptoms, treatment, severity, region, image_reference
- **Integration:** Power the poisonous plant database (§22.3). Cross-reference with foraging module — warn when a foraged plant has a toxic look-alike.

### 2.7 CDC Vaccine Schedules & Disease Reference
- **Source:** Centers for Disease Control and Prevention
- **URL:** https://www.cdc.gov/vaccines/schedules/
- **Format:** PDF, HTML (needs structuring)
- **License:** Public domain
- **Content:** Recommended immunization schedules by age, catch-up schedules, disease symptoms/treatment/prevention
- **Integration:** Vaccination record tracking per person. Outbreak preparedness reference.

### 2.8 FEMA ICS Forms
- **Source:** FEMA
- **URL:** https://training.fema.gov/emiweb/is/icsresource/icsforms.htm
- **Format:** PDF fillable forms, Word templates
- **License:** Public domain (US Government)
- **Forms available:** ICS-201 through ICS-225 (all standard forms)
- **Integration:** Generate filled ICS forms from NOMAD data (§44). Auto-populate ICS-205 from freq_database, ICS-206 from medical module, ICS-214 from journal entries.

### 2.9 NIOSH Pocket Guide to Chemical Hazards
- **Source:** National Institute for Occupational Safety and Health (CDC/NIOSH)
- **URL:** https://www.cdc.gov/niosh/npg/default.html (also available as mobile app data)
- **Format:** HTML tables (structured, scrapeable), PDF
- **Size:** ~10 MB (structured extraction)
- **License:** Public domain (US Government)
- **Fields:** chemical_name, cas_number, formula, synonyms, exposure_limits (REL/PEL/IDLH), physical_description, incompatibilities, personal_protection, first_aid, symptoms_of_exposure, target_organs, routes_of_exposure
- **Coverage:** 677 chemical hazards with complete safety profiles
- **Integration:** Chemical hazard identification for EPA RMP facilities (§8.5). First aid by chemical exposure. PPE recommendations. IDLH (Immediately Dangerous to Life or Health) thresholds for evacuation decisions. Cross-reference with industrial facility proximity.

### 2.10 ATSDR Toxic Substance Profiles (ToxProfiles)
- **Source:** Agency for Toxic Substances and Disease Registry (CDC/ATSDR)
- **URL:** https://www.atsdr.cdc.gov/toxprofiles/index.asp
- **Format:** PDF (detailed), HTML summaries (ToxFAQs)
- **Size:** ~500 MB (all profiles), ~5 MB (ToxFAQs summaries only)
- **License:** Public domain (US Government)
- **Content:** Comprehensive toxicological profiles for 300+ hazardous substances — health effects, exposure routes, environmental fate, medical management
- **Fields (ToxFAQs subset):** substance, cas_number, what_is_it, exposure_routes, health_effects, how_to_reduce_exposure, medical_tests, environmental_fate
- **Integration:** Water contamination hazard reference. Post-industrial disaster health guidance. Complement NIOSH data with longer-term health effects. Link to nearby Superfund/RMP sites.

### 2.11 DDInter — Drug-Drug Interaction Database
- **Source:** Xiangya School of Pharmaceutical Sciences (open academic database)
- **URL:** https://ddinter.scbdd.com/
- **Format:** CSV/TSV download
- **Size:** ~30 MB
- **License:** Free for academic/non-commercial use
- **Fields:** drug_1, drug_2, interaction_level (major/moderate/minor/unknown), interaction_description, mechanism, management_recommendation
- **Coverage:** 240,000+ interaction pairs for 2,300+ FDA-approved drugs
- **Integration:** Alternative/complement to DrugBank interactions. Includes severity levels and management recommendations that DrugBank Open lacks. Smaller and more curated than DrugBank's 2.5M pairs — easier to bundle.

### 2.12 SIDER — Side Effects Resource
- **Source:** EMBL (European Molecular Biology Laboratory)
- **URL:** http://sideeffects.embl.de/
- **Format:** TSV download
- **Size:** ~200 MB
- **License:** CC BY-NC-SA 4.0
- **Fields:** drug_name, stitch_id, umls_cui, side_effect_name, meddra_type, frequency (if available)
- **Coverage:** 1,430 drugs with 140,000+ drug–side effect pairs extracted from package inserts
- **Integration:** Medication side effect lookup. "You're taking X — watch for these symptoms." Differentiate expected side effects from new medical conditions. Frequency data helps prioritize warnings.

### 2.13 EPA Acute Exposure Guideline Levels (AEGLs)
- **Source:** U.S. Environmental Protection Agency
- **URL:** https://www.epa.gov/aegl
- **Format:** PDF tables (structured extraction available)
- **Size:** ~5 MB (structured)
- **License:** Public domain (US Government)
- **Fields:** chemical_name, cas_number, aegl_1_10min through aegl_3_8hr (concentration thresholds at 10min, 30min, 60min, 4hr, 8hr for three severity tiers)
- **Coverage:** 300+ chemicals with time-dependent exposure thresholds
- **AEGL tiers:**
  - **AEGL-1:** Notable discomfort, non-disabling
  - **AEGL-2:** Irreversible or serious long-lasting health effects, impaired ability to escape
  - **AEGL-3:** Life-threatening or lethal effects
- **Integration:** Chemical incident shelter-in-place duration decisions. "At X ppm, you can safely shelter for Y minutes." Pairs with EPA RMP facility data (§8.5) for exposure scenario modeling.

---

## 3. Geography, Maps & Elevation

### 3.1 OpenStreetMap (OSM) Data
- **Source:** OpenStreetMap Foundation
- **URL:** https://download.geofabrik.de/ (regional extracts)
- **Format:** PBF (Protocolbuffer Binary Format), also .osm.bz2
- **Size:** US-only: ~10 GB PBF; Single state: 50 MB–2 GB
- **License:** Open Data Commons Open Database License (ODbL)
- **Content:** Roads, buildings, POIs (water sources, shelters, hospitals, fire stations, police, fuel stations, grocery stores), boundaries, land use, waterways, terrain features
- **Integration:** Offline map tiles via mbtiles generation. POI database for resource identification. Address search. Routing. Already used via Kiwix but can be expanded with OSM-specific tooling.
- **Tools:** osmium (extract/filter), tilemaker (PBF → mbtiles), Nominatim (offline geocoding)

### 3.2 SRTM Elevation Data
- **Source:** NASA Shuttle Radar Topography Mission
- **URL:** https://dwtkns.com/srtm30m/ (SRTM 1-arc-second) or https://earthexplorer.usgs.gov/
- **Format:** HGT (raw binary), GeoTIFF
- **Size:** ~30 MB per 1°×1° tile (US is ~700 tiles = ~20 GB total)
- **Resolution:** 30m (1-arc-second) globally, available at 1m in US via 3DEP
- **License:** Public domain (NASA/USGS)
- **Integration:** Elevation profiles between waypoints (§16.6). Line-of-sight analysis. Terrain difficulty for route planning. Viewshed analysis. Contour line generation for offline topo maps.
- **Bundle strategy:** Ship local area tiles (~100 MB) or let user download their region.

### 3.3 USGS 3D Elevation Program (3DEP)
- **Source:** U.S. Geological Survey
- **URL:** https://apps.nationalmap.gov/downloader/
- **Format:** GeoTIFF, IMG, LAS (lidar point clouds)
- **Size:** 1m resolution — extremely large; 10m resolution more practical
- **License:** Public domain (US Government)
- **Integration:** High-resolution terrain analysis for property-level planning. Flood modeling. Defensive position analysis. Much higher resolution than SRTM for US locations.

### 3.4 National Hydrography Dataset (NHD)
- **Source:** USGS
- **URL:** https://www.usgs.gov/national-hydrography/access-national-hydrography-products
- **Format:** Shapefile, FileGDB, GeoPackage
- **Size:** ~15 GB (US complete)
- **License:** Public domain
- **Content:** Rivers, streams, lakes, ponds, springs, wells, watersheds, canals, ditches, coastline
- **Integration:** Water source identification and mapping (§1.4). Watershed delineation for water-seeking SAR subjects. Water crossing route planning. Populate water source waypoints.

### 3.5 TIGER/Line Shapefiles (Census Bureau)
- **Source:** U.S. Census Bureau
- **URL:** https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html
- **Format:** Shapefile
- **Size:** ~25 GB (US complete, all layers)
- **License:** Public domain
- **Content:** Roads (with names/classifications), railroads, addresses, county/state/ZIP boundaries, landmarks, water features, military installations
- **Integration:** Road network for offline routing. Address ranges for geocoding. County boundaries for jurisdiction identification. Military installation locations.

### 3.6 National Land Cover Database (NLCD)
- **Source:** USGS Multi-Resolution Land Characteristics Consortium
- **URL:** https://www.mrlc.gov/data
- **Format:** GeoTIFF (raster)
- **Size:** ~15 GB (30m resolution, CONUS)
- **License:** Public domain
- **Content:** Land cover classification — developed, forest, shrub, grass, crops, wetlands, water, barren — at 30m resolution
- **Integration:** Terrain passability assessment. Concealment analysis (forest vs open). Agriculture potential assessment. Fire fuel load estimation.

### 3.7 Magnetic Declination Data (World Magnetic Model)
- **Source:** NOAA National Centers for Environmental Information / British Geological Survey
- **URL:** https://www.ncei.noaa.gov/products/world-magnetic-model
- **Format:** COF (coefficient file), also available as lookup tables
- **Size:** <1 MB
- **License:** Public domain
- **Content:** Magnetic declination, inclination, and field strength at any point on Earth, valid for 5-year epochs
- **Integration:** Compass correction for map navigation. Auto-calculate true north from magnetic bearing at any waypoint. Essential for land navigation (§6).
- **Note:** IGRF-14 (International Geomagnetic Reference Field, 14th generation) provides historical magnetic field models back to 1900 and forward prediction to 2030. Useful for correcting old maps with outdated declination annotations.

### 3.8 ESA WorldCover Land Cover Map
- **Source:** European Space Agency (Copernicus)
- **URL:** https://esa-worldcover.org/en
- **Format:** GeoTIFF (Cloud Optimized)
- **Size:** ~300 GB global (regional tiles ~500 MB–2 GB)
- **Resolution:** 10m (3x better than NLCD's 30m)
- **License:** CC BY 4.0
- **Content:** 11 land cover classes — tree cover, shrubland, grassland, cropland, built-up, bare/sparse, snow/ice, water, wetlands, mangroves, moss/lichen
- **Integration:** Higher resolution alternative to NLCD (§3.6) for precise concealment analysis, terrain passability, and fire fuel mapping. 10m resolution distinguishes individual tree stands. Global coverage extends beyond US.

### 3.9 ETOPO Global Relief Model
- **Source:** NOAA National Centers for Environmental Information
- **URL:** https://www.ncei.noaa.gov/products/etopo-global-relief-model
- **Format:** NetCDF, GeoTIFF
- **Size:** ~2 GB (1-arc-minute global), ~8 GB (15-arc-second)
- **License:** Public domain
- **Content:** Integrated topographic and bathymetric elevation data — land + ocean floor
- **Integration:** Bathymetric data for coastal/riverine operations. Submarine cable and shelf identification. Tsunami wave propagation estimation. Global elevation coverage beyond SRTM's ±60° latitude limit.

---

## 4. Weather, Climate & Solar

### 4.1 NOAA Climate Normals
- **Source:** NOAA National Centers for Environmental Information
- **URL:** https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals
- **Format:** CSV
- **Size:** ~500 MB (all stations, all variables)
- **License:** Public domain
- **Content:** 30-year climate averages for 8,700+ US stations — monthly/daily normals for temperature (avg/max/min), precipitation, snowfall, frost/freeze dates, heating/cooling degree days, growing degree days
- **Fields:** station_id, station_name, lat, lon, elevation, month, temp_avg, temp_max, temp_min, precip_avg, snow_avg, first_frost_date (10%/50%/90% probability), last_frost_date, growing_degree_days
- **Integration:** Power frost date calculations for garden module (replace simplified latitude-based lookup). Seasonal checklist triggers. Weather baseline for anomaly detection. Heating fuel estimation. Solar panel sizing (cloud cover normals).
- **Bundle strategy:** Extract station nearest to user's location (~5 KB per station). Ship complete frost date dataset (~2 MB) for all US stations.

### 4.2 NOAA Storm Events Database
- **Source:** NOAA National Weather Service
- **URL:** https://www.ncdc.noaa.gov/stormevents/
- **Format:** CSV bulk download
- **Size:** ~3 GB (complete history)
- **License:** Public domain
- **Content:** Every severe weather event since 1950 — type, location, county, date, injuries, deaths, property damage, crop damage, narrative
- **Fields:** event_type (tornado, hail, flood, etc.), begin_date, end_date, state, county_fips, lat, lon, injuries_direct, deaths_direct, damage_property, damage_crops, narrative
- **Integration:** Historical threat assessment by location. "Your county has had 23 tornadoes in the last 20 years." Power threat probability calculations for scenario planning. Identify seasonal risk patterns.

### 4.3 NOAA Weather Radio (NWR) Station Database
- **Source:** NOAA
- **URL:** https://www.weather.gov/nwr/station_listing
- **Format:** CSV/HTML (needs scraping into structured data)
- **Size:** ~200 KB
- **Content:** All 1,000+ NOAA Weather Radio transmitter sites — frequency, call sign, location, coverage area, SAME code
- **Fields:** callsign, frequency_mhz, state, county, city, lat, lon, power_watts, same_code
- **Integration:** Auto-configure weather radio by location. Display nearest NWR station on map. Populate freq_database with weather frequencies. SAME code lookup for programming weather radios.

### 4.4 Sunrise/Sunset/Moonrise Algorithm Data
- **Source:** USNO (US Naval Observatory) / Jean Meeus astronomical algorithms
- **URL:** Algorithmic (no download needed — pure math from published algorithms)
- **Format:** Embedded algorithm
- **License:** Public domain (published algorithms)
- **Content:** Precise sunrise, sunset, civil/nautical/astronomical twilight, moonrise, moonset, moon phase, moon illumination for any date and location
- **Integration:** Already partially implemented (api_sun in app.py). Expand with moonrise/set, illumination %, twilight phases for night operations planning (§28).

### 4.5 XTide Harmonics Database
- **Source:** David Flater / NOAA harmonic constants
- **URL:** https://flaterco.com/xtide/files.html
- **Format:** TCD (Tide Constituent Database) binary
- **Size:** ~15 MB
- **License:** Public domain (data is NOAA; XTide software is GPL)
- **Content:** Tidal harmonic constituents for 5,000+ stations worldwide — enables prediction of tide heights and times for any future date, fully offline
- **Fields:** station_name, lat, lon, time_zone, datum, harmonic_constituents (amplitude, phase, speed for each constituent)
- **Integration:** Tide prediction for coastal operations and fishing. Boat launch planning. River crossing timing (tidal rivers). Evacuation route planning (coastal flood timing). Pairs with NHD water data (§3.4) for tidal river identification.

### 4.6 NOAA Integrated Surface Database (ISD)
- **Source:** NOAA National Centers for Environmental Information
- **URL:** https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database
- **Format:** Fixed-width text, also CSV via API
- **Size:** ~600 GB (complete history), ~10 GB (latest year, all stations), ~50 MB (single station 30-year history)
- **License:** Public domain
- **Fields:** station_id, datetime, lat, lon, elevation, wind_direction, wind_speed, ceiling_height, visibility, temperature, dewpoint, sea_level_pressure, precipitation, snow_depth, weather_type
- **Coverage:** 35,000+ stations globally, hourly observations back to 1901
- **Integration:** Historical weather pattern analysis beyond climate normals. Specific "what was weather like on this date in past years" for event planning. Power extended Zambretti barometric prediction with baseline pressure data by station/season.
- **Bundle strategy:** Ship nearest-station 10-year hourly history (~5 MB per station) for local pattern analysis.

### 4.7 NREL Solar Position Algorithm (SPA)
- **Source:** National Renewable Energy Laboratory
- **URL:** https://midcdmz.nrel.gov/spa/ (algorithm + C source code)
- **Format:** C source code (portable, easily adapted to Python)
- **Size:** ~50 KB (source)
- **License:** Public domain (US Government)
- **Content:** High-precision algorithm for solar position (azimuth/zenith) accurate to ±0.0003° for years -2000 to 6000. Uncertainty of ±0.0003° vs ~0.01° for typical implementations
- **Integration:** Replace/validate existing sunrise/sunset calculations with NREL's reference implementation. Solar panel optimal angle calculation. Shadow analysis for garden plot planning. Solar oven aiming. More accurate than Meeus algorithms for extreme latitudes.

---

## 5. Radio, Communications & Frequencies

### 5.1 FCC Universal Licensing System (ULS)
- **Source:** Federal Communications Commission
- **URL:** https://www.fcc.gov/wireless/data/public-access-files-database-downloads
- **Format:** Pipe-delimited text files
- **Size:** ~5 GB (complete amateur + GMRS + commercial)
- **License:** Public domain (US Government)
- **Content:** Every licensed radio station in the US — callsign, licensee, frequencies, power, antenna location, license class, expiration
- **Integration:** Amateur radio callsign lookup. Identify nearby licensed stations. Verify callsigns heard on scanner. GMRS license verification for group members.

### 5.2 RepeaterBook Database
- **Source:** RepeaterBook (community-maintained)
- **URL:** https://www.repeaterbook.com/repeaters/downloads/
- **Format:** CSV export
- **Size:** ~10 MB (US)
- **License:** Free for personal use
- **Fields:** frequency, offset, pl_tone, callsign, city, state, county, lat, lon, use (open/closed), operational_status, notes
- **Coverage:** 40,000+ amateur radio repeaters in the US
- **Integration:** Populate freq_database with local repeaters. Display repeaters on map. Auto-generate CHIRP programming files. Identify nearest operational repeaters for emergency comms.

### 5.3 RadioReference.com Frequency Database
- **Source:** RadioReference (community-maintained)
- **URL:** https://www.radioreference.com/db/ (premium for bulk export)
- **Format:** API, CSV export (premium)
- **Content:** Public safety, federal, commercial, amateur frequencies by county/city
- **Fields:** frequency, mode, pl_tone, agency, description, county, state, system_type
- **Integration:** Populate scanner frequency database for local police, fire, EMS. Critical for situational awareness monitoring.
- **Note:** Premium subscription needed for bulk data. Consider manual entry UI for free tier.

### 5.4 ITU/FCC Band Allocation Charts
- **Source:** FCC / ARRL
- **URL:** https://www.ntia.gov/page/2011/united-states-frequency-allocation-chart
- **Format:** PDF, can be structured into JSON
- **License:** Public domain
- **Content:** Complete frequency allocation from 3 kHz to 300 GHz — which services operate on which bands
- **Integration:** Reference tool for radio planning. "What can I transmit on at 446 MHz?" → FRS/GMRS. Band plan reference for comms module.

### 5.5 Amateur Radio Band Plans
- **Source:** ARRL
- **URL:** https://www.arrl.org/band-plan
- **Format:** Structured tables
- **Content:** Detailed sub-band allocations for each amateur band (160m through 23cm) — CW, digital, SSB, FM, repeater input/output, satellite
- **Integration:** Frequency planning for HF/VHF/UHF amateur operations. Auto-suggest appropriate frequencies for different modes. Reference for comms planning.

### 5.6 FRS/GMRS/MURS Channel Reference
- **Source:** FCC Part 95 rules
- **Format:** Structured table (small, can be embedded)
- **Size:** <10 KB
- **Content:** FRS channels 1-22 (frequencies, power limits, bandwidth), GMRS channels and repeater pairs, MURS channels
- **Integration:** Already partially in use. Embed as reference data. Auto-populate radio profiles. Channel assignment for group comms planning.

---

## 6. Agriculture, Garden & Soil

### 6.1 USDA Plant Hardiness Zone Map (GIS Data)
- **Source:** USDA Agricultural Research Service
- **URL:** https://planthardiness.ars.usda.gov/
- **Format:** GIS Shapefile, GeoTIFF
- **Size:** ~50 MB (shapefile), ~200 MB (raster)
- **License:** Public domain
- **Content:** Plant hardiness zones (1a through 13b) at 0.5-mile resolution for entire US
- **Integration:** Replace simplified latitude-based zone lookup in garden.py with precise GIS lookup. User's exact hardiness zone from GPS coordinates. Automatic planting calendar adjustment.

### 6.2 USDA PLANTS Database
- **Source:** USDA Natural Resources Conservation Service
- **URL:** https://plants.usda.gov/
- **Format:** CSV download
- **Size:** ~50 MB
- **License:** Public domain
- **Fields:** symbol, scientific_name, common_name, family, growth_habit, native_status, duration (annual/perennial), toxicity, bloom_period, fruit_seed_period, growth_rate, drought_tolerance, fire_tolerance, moisture_use, shade_tolerance
- **Coverage:** 95,000+ plant species in the US
- **Integration:** Plant identification reference. Toxicity flagging for foraging. Companion planting data. Native vs invasive identification. Fire-resistant plant identification for defensible space.

### 6.3 SSURGO Soil Survey Data
- **Source:** USDA Natural Resources Conservation Service
- **URL:** https://websoilsurvey.nrcs.usda.gov/
- **Format:** Shapefile + tabular data (Access MDB or CSV)
- **Size:** Varies by county, ~50 MB–500 MB per state
- **License:** Public domain
- **Fields:** soil_type, texture, drainage_class, depth_to_water_table, permeability, pH, organic_matter, flooding_frequency, farmland_classification, engineering_properties
- **Integration:** Garden plot soil analysis. Septic system suitability. Building foundation assessment. Latrine siting (§15.2). Well drilling feasibility. Crop selection based on soil type.

### 6.4 Companion Planting Database
- **Source:** Various cooperative extension services / Garden.org
- **Format:** Need to compile into structured JSON (matrix format)
- **Size:** ~50 KB
- **Content:** Plant-to-plant relationships: companion (mutual benefit), antagonist (harmful), neutral
- **Coverage:** 60+ common garden vegetables, herbs, and flowers
- **Integration:** Expand existing companion_plants table in db.py. Currently seeded with basic data — can be expanded 3-4x with comprehensive extension data.

### 6.5 Crop Nutritional Yield Data
- **Source:** USDA FoodData Central + cooperative extension yield data
- **Format:** Compiled JSON
- **Fields:** crop, calories_per_lb, protein_per_lb, yield_per_sqft, days_to_harvest, water_needs_gal_per_week, nitrogen_needs, companion_crops
- **Integration:** Expand existing planting_calendar data. Power caloric yield analysis in garden module. Optimize garden layout for maximum nutrition per square foot.

---

## 7. Wildlife, Foraging & Hunting

### 7.1 USDA PLANTS Database — Edible Species Subset
- **Source:** USDA (same as 6.2, filtered)
- **Integration:** Filter PLANTS database for species with food_use=yes. Cross-reference with ethnobotany data. Build edible plant identification reference.

### 7.2 Plants For A Future (PFAF) Database
- **Source:** Plants For A Future (charity)
- **URL:** https://pfaf.org/user/Default.aspx
- **Format:** HTML (needs scraping), or available as structured XML for bulk requests. Community-maintained CSV exports exist on GitHub
- **License:** Free for non-commercial use
- **Fields:** latin_name, common_name, family, known_hazards, habitats, edibility_rating (0-5 scale: 0=unknown, 1=not recommended, 5=excellent), medicinal_rating (0-5), edible_parts, edible_uses, medicinal_uses, other_uses, cultivation_details, propagation, range, habitat, height, width, hardiness_zone, soil_type, soil_pH, shade_tolerance, moisture, growth_rate, pollinators
- **Coverage:** 7,000+ useful plants with full cultivation and use data
- **Integration:** Power the wild edible plant catalog (§23.3). Medicinal plant reference (§52.4). Foraging spot species identification. The 0-5 edibility/medicinal rating system enables "traffic light" confidence indicators for foraging decisions. Known_hazards field critical for safety warnings.

### 7.3 MushroomExpert.com / MycoPortal
- **Source:** Various mycological databases
- **URL:** https://mycoportal.org/portal/
- **Format:** Darwin Core CSV exports
- **License:** Varies by collection
- **Content:** Mushroom species with identification features, distribution maps, toxicity information
- **Integration:** Mushroom identification guide (§22.3). Toxicity warnings. Spore print references. Regional distribution data.

### 7.4 USGS Biodiversity Information Serving Our Nation (BISON)
- **Source:** USGS
- **URL:** https://bison.usgs.gov/
- **Format:** CSV, JSON API
- **License:** Public domain
- **Content:** Species occurrence records — what species have been observed where in the US
- **Integration:** Regional wildlife identification. "What game animals are in your area?" Answer from actual observation records.

### 7.5 State Wildlife Agency Season Data
- **Source:** Individual state fish & game departments
- **Format:** Varies (PDF, HTML — need manual structuring)
- **Content:** Hunting/fishing season dates, bag limits, license requirements, legal methods by species and zone
- **Integration:** Hunting/fishing season calendar (§27.2). Auto-remind when seasons open. Track tag usage against limits.
- **Note:** This data changes annually and varies by state. Best approach: provide a template schema and let users enter their state's data, or compile the top 10 most-populated hunting states.

### 7.6 Venomous Species Reference Data
- **Source:** CDC / WHO / Regional poison control centers
- **Format:** Compiled JSON from published references
- **Fields:** species, common_name, geographic_range_states, habitat, venom_type, symptoms, first_aid, antivenom_notes, danger_level, image_reference
- **Coverage:** All venomous snakes (20+ species), spiders (2 medically significant), scorpions, insects in North America
- **Integration:** Snake/spider identification guide (§19.3). First aid protocols by species. Regional filtering — "show me venomous species in my state."

### 7.7 Firewood BTU Ratings
- **Source:** Various forestry extension services
- **Format:** Structured table (small, embeddable)
- **Size:** <10 KB
- **Fields:** tree_species, btu_per_cord, splitting_ease, smoke_level, spark_level, coaling_quality, seasoning_time_months, density_lbs_per_cord
- **Coverage:** 50+ common firewood species in North America
- **Integration:** Firewood inventory valuation. Heating calculation (BTU needed ÷ BTU per cord = cords needed). Optimal species selection. Seasoning time tracking.

### 7.8 FishBase — Global Fish Species Database
- **Source:** FishBase Consortium (WorldFish Center / FAO)
- **URL:** https://www.fishbase.se/search.php (web), bulk data via rfishbase R package or API
- **Format:** SQL dump (upon request), CSV via API, R package
- **Size:** ~2 GB (full SQL dump)
- **License:** CC BY-NC 3.0
- **Fields:** species, common_name, family, habitat, freshwater/saltwater, max_length_cm, max_weight_kg, biology, diet, food_items, depth_range, distribution, dangerous_to_humans, used_in_fisheries, game_fish, nutritional_data (calories, protein, fat per 100g)
- **Coverage:** 35,000+ fish species globally, 350,000+ common names in multiple languages
- **Integration:** Fishing module species identification (§23.2). Nutritional value of catch for calorie planning. Dangerous species warnings. Habitat requirements → which water bodies yield which species. Link fish species to NHD water features (§3.4).
- **Bundle strategy:** Extract freshwater game fish for user's state/region (~500 species, ~2 MB).

### 7.9 Mushroom Observer Database
- **Source:** Mushroom Observer (community citizen science)
- **URL:** https://mushroomobserver.org/ (API available, bulk downloads on request)
- **Format:** CSV export, JSON API
- **License:** CC BY-NC-SA 3.0
- **Fields:** species_name, date_observed, location, lat, lon, habitat, confidence_level, images, notes, identification_consensus
- **Coverage:** 500,000+ observations of 15,000+ species, heavily North America
- **Integration:** Regional mushroom distribution data — "which edible mushrooms have been found within 50 miles of here." Seasonal fruiting patterns. Complement MycoPortal (§7.3) with citizen-science observation density.

### 7.10 iNaturalist / GBIF Species Occurrence Data
- **Source:** iNaturalist (via GBIF — Global Biodiversity Information Facility)
- **URL:** https://www.gbif.org/dataset/50c9509d-22c7-4a22-a47d-8c48425ef4a7
- **Format:** Darwin Core Archive (CSV + metadata)
- **Size:** ~80 GB (full iNaturalist export), regional subsets ~500 MB–2 GB
- **License:** CC0 / CC BY / CC BY-NC (varies per observation)
- **Fields:** species, date_observed, lat, lon, coordinate_uncertainty_m, quality_grade (research/needs_id/casual), taxon_kingdom/phylum/class/order/family
- **Coverage:** 180M+ observations, 400K+ species globally, strongest in North America
- **Integration:** Most comprehensive "what species live near me" dataset. Filter for edible plants, game animals, venomous species within user's radius. Seasonal occurrence patterns (when are morels fruiting in my county?). Research-grade observations only for reliability.
- **Bundle strategy:** Extract state-level subsets filtered to survival-relevant taxa (edible plants, game, venomous species) — ~50 MB per state.

---

## 8. Hazards, Threats & Emergency Management

### 8.1 FEMA National Risk Index
- **Source:** FEMA
- **URL:** https://hazards.fema.gov/nri/
- **Format:** CSV download, GIS shapefile
- **Size:** ~100 MB
- **License:** Public domain
- **Fields:** county_fips, state, county, risk_score, expected_annual_loss, social_vulnerability, community_resilience, plus per-hazard scores for 18 natural hazard types (earthquake, hurricane, tornado, flood, wildfire, etc.)
- **Integration:** Location-based threat assessment. Automatic disaster-specific module recommendations (§39). "Your county has HIGH tornado risk, MODERATE flood risk, LOW earthquake risk." Priority ranking for preparedness activities.

### 8.2 USGS Earthquake Hazard Data
- **Source:** USGS Earthquake Hazards Program
- **URL:** https://earthquake.usgs.gov/data/
- **Format:** GeoJSON (realtime), Shapefile (hazard maps), CSV (catalog)
- **Size:** Varies — hazard maps ~500 MB, complete catalog ~2 GB
- **License:** Public domain
- **Content:**
  - **Earthquake catalog** — every recorded earthquake (magnitude, depth, location, time)
  - **Fault line shapefiles** — mapped quaternary faults
  - **Seismic hazard maps** — PGA (Peak Ground Acceleration) probability maps
- **Integration:** Earthquake risk overlay on map. Fault line display. Historical earthquake search. Shake intensity estimation for your location.

### 8.3 FEMA National Flood Hazard Layer (NFHL)
- **Source:** FEMA
- **URL:** https://www.fema.gov/flood-maps/national-flood-hazard-layer
- **Format:** Shapefile, FileGDB
- **Size:** ~20 GB (US complete), downloadable by state/county
- **License:** Public domain
- **Content:** Flood zones (A, AE, AH, AO, V, VE, X), base flood elevations, floodways, cross-sections
- **Integration:** Flood zone overlay on map. Property flood risk assessment. Evacuation route planning (avoid flood zones). Cache location suitability.

### 8.4 NRC Nuclear Facility Locations
- **Source:** Nuclear Regulatory Commission
- **URL:** https://www.nrc.gov/info-finder/reactor/
- **Format:** CSV/JSON (from NRC open data)
- **Size:** <1 MB
- **License:** Public domain
- **Fields:** facility_name, type (power/research), lat, lon, status (operating/decommissioned), unit_type, capacity_mw, licensee
- **Coverage:** 93 operating commercial reactors + 31 research reactors in the US
- **Integration:** Nuclear facility overlay on NukeMap. Distance calculation from user's location. Fallout modeling based on prevailing winds. Evacuation zone reference (10-mile EPZ, 50-mile IPZ).

### 8.5 EPA Risk Management Plan (RMP) Facilities
- **Source:** EPA
- **URL:** https://www.epa.gov/rmp
- **Format:** CSV (via EPA Envirofacts)
- **Size:** ~50 MB
- **License:** Public domain
- **Fields:** facility_name, lat, lon, chemical_stored, quantity_lbs, naics_code, worst_case_scenario, distance_to_endpoint_miles
- **Coverage:** 12,000+ facilities storing hazardous chemicals above threshold quantities
- **Integration:** Chemical hazard overlay on map. Identify nearby facilities with dangerous chemicals. Shelter-in-place vs. evacuation planning based on chemical type and wind direction.

### 8.6 NIFC Wildfire History & LANDFIRE
- **Source:** National Interagency Fire Center / USGS LANDFIRE
- **URL:** https://data-nifc.opendata.arcgis.com/ and https://landfire.gov/
- **Format:** Shapefile, GeoTIFF
- **Size:** Historical perimeters: ~2 GB; LANDFIRE fuel models: ~50 GB
- **License:** Public domain
- **Content:** Historical wildfire perimeters (every mapped fire since 1980), plus LANDFIRE vegetation and fuel models for fire behavior prediction
- **Integration:** Wildfire history overlay. Fire risk assessment for property. Defensible space planning. Fuel load assessment around structures.

### 8.7 NOAA Space Weather Data
- **Source:** NOAA Space Weather Prediction Center
- **URL:** https://www.swpc.noaa.gov/products-and-data
- **Format:** JSON/CSV (real-time, cacheable)
- **Size:** <1 MB per data pull
- **License:** Public domain
- **Content:** Kp index (geomagnetic activity), solar flare alerts, coronal mass ejection tracking, radio blackout warnings, geomagnetic storm scale (G1-G5)
- **Integration:** EMP/solar event monitoring (§39.7). Cache latest data during internet windows. Alert on elevated geomagnetic activity. HF radio propagation prediction.

---

## 9. Military, Tactical & Reference

### 9.1 US Army Field Manuals (Public Domain)
- **Source:** US Army Publishing Directorate
- **URL:** https://armypubs.army.mil/
- **Format:** PDF
- **License:** Public domain (US Government)
- **Key manuals:**
  - **FM 3-05.70** (FM 21-76) — Survival (432 pages)
  - **ATP 4-25.13** — Casualty Evacuation / First Aid
  - **FM 5-34** — Engineer Field Data
  - **STP 31-18-SM-TG** — Special Forces Medical Handbook
  - **TC 3-21.76** — Ranger Handbook
  - **ATP 3-21.8** — Infantry Platoon and Squad
  - **FM 3-34.471** — Plumbing, Pipe Fitting, Sewerage
  - **FM 5-430-00-1** — Planning and Design of Roads
  - **FM 4-25.11** — First Aid
- **Integration:** Already available via Kiwix ZIM (armypubs). Index specific sections into searchable reference. Link relevant manual sections to NOMAD features (e.g., FM 4-25.11 linked from medical module).

### 9.2 MIL-STD-2525 Military Symbology
- **Source:** Department of Defense
- **URL:** Available through defense.gov / various open implementations
- **Format:** SVG icon sets (open-source implementations available on GitHub)
- **Size:** ~5 MB for complete icon set
- **License:** Public domain (government standard), open-source implementations
- **Content:** Standard military map symbols for units, equipment, installations, activities, control measures
- **Integration:** Optional military symbology for map markers (§ Competitor Gaps - ATAK). Toggle between civilian and military icon sets.

### 9.3 NATO Phonetic Alphabet & Prowords
- **Source:** NATO standardization documents
- **Format:** Embedded lookup table (<5 KB)
- **Content:** A=Alpha through Z=Zulu, plus radio prowords (WILCO, ROGER, SAY AGAIN, BREAK, OUT, OVER)
- **Integration:** Radio procedure reference. Phonetic alphabet drill trainer (§19.3). Auto-convert text to phonetic spelling for radio transmission.

### 9.4 9-Line MEDEVAC / SALUTE / SPOT Report Formats
- **Source:** US Army doctrine
- **Format:** Structured templates (embedded)
- **Content:** Standard military report formats adapted for civilian use
- **Integration:** Template library for comms module (§16.3). Auto-populate from NOMAD data where possible (e.g., 9-line MEDEVAC pulls patient location and condition).

### 9.5 ICS Resource Typing Definitions
- **Source:** FEMA
- **URL:** https://rtlt.preptoolkit.fema.gov/
- **Format:** PDF/Excel
- **License:** Public domain
- **Content:** Standardized definitions for 120+ resource types across fire, law enforcement, EMS, search & rescue, public works, medical
- **Fields:** resource_type, category, kind, type (1-4), minimum_capabilities, component_requirements
- **Integration:** Standardized resource categorization for ICS module (§44). Resource request standardization. Personnel qualification matching.

---

## 10. Astronomy, Navigation & Timekeeping

### 10.1 JPL Planetary Ephemeris
- **Source:** NASA Jet Propulsion Laboratory
- **URL:** https://ssd.jpl.nasa.gov/planets/eph_export.html
- **Format:** Binary (DE440/DE441), also ASCII
- **Size:** ~100 MB for DE440 (covers 1550-2650 CE)
- **License:** Public domain (NASA)
- **Content:** Precise positions of Sun, Moon, and planets for any date — enables exact sunrise, sunset, moonrise, moonset, and celestial navigation calculations
- **Integration:** Replace/validate existing sun calculation algorithm. Add moon phase, moonrise/set, illumination. Power celestial navigation reference (§19.3).

### 10.2 Bright Star Catalog (Yale BSC) / HYG Star Database
- **Source:** Yale University (BSC) / astronexus.com (HYG — merged Hipparcos/Yale/Gliese)
- **URL (BSC):** http://tdc-www.harvard.edu/catalogs/bsc5.html
- **URL (HYG):** https://github.com/astronexus/HYG-Database
- **Format:** BSC: fixed-width text; HYG: CSV (ready to use)
- **Size:** BSC: ~2 MB; HYG: ~5 MB
- **License:** Public domain (both)
- **Content:**
  - **Yale BSC** — 9,110 stars visible to naked eye
  - **HYG v3.7** — 119,614 stars merging Hipparcos, Yale, and Gliese catalogs. Includes all BSC stars plus fainter objects with consistent formatting
- **Fields (HYG):** id, hip, hd, hr, gl, bf (Bayer/Flamsteed designation), proper_name, ra, dec, distance_pc, mag, abs_mag, spectral_type, color_index, x/y/z cartesian
- **Integration:** Star chart for celestial navigation (§19.3). HYG's CSV format is directly loadable — no parsing gymnastics. The `proper_name` field gives common star names (Polaris, Sirius, Vega). Filter to mag < 4.0 for ~500 navigational stars, or mag < 6.5 for all naked-eye stars (~9,000). Compute star positions for any date/time/location with JPL ephemeris (§10.1).

### 10.3 IANA Time Zone Database
- **Source:** IANA
- **URL:** https://www.iana.org/time-zones
- **Format:** Text rules
- **Size:** <1 MB
- **License:** Public domain
- **Content:** Complete time zone rules for every jurisdiction worldwide, including historical DST changes
- **Integration:** Time zone conversion (§19.3). Federation peer time coordination. Correct local time display for any waypoint.

---

## 11. Energy, Solar & Wind

### 11.1 NREL National Solar Radiation Database (NSRDB)
- **Source:** National Renewable Energy Laboratory
- **URL:** https://nsrdb.nrel.gov/
- **Format:** CSV (via API with free key, or bulk download)
- **Size:** ~1 GB for US typical meteorological year data
- **License:** Public domain (US Government)
- **Fields:** lat, lon, year, month, day, hour, ghi (Global Horizontal Irradiance), dni (Direct Normal Irradiance), dhi (Diffuse Horizontal Irradiance), temperature, wind_speed, cloud_type
- **Integration:** Solar panel sizing calculator (§19.1). Estimate daily/monthly solar production by location. Size battery bank for autonomy days. Seasonal production variation.
- **Bundle strategy:** Extract monthly average GHI for US at county level (~500 KB).

### 11.2 NREL Wind Resource Data
- **Source:** National Renewable Energy Laboratory
- **URL:** https://www.nrel.gov/gis/wind-resource-maps.html
- **Format:** GeoTIFF, CSV
- **Size:** ~500 MB
- **License:** Public domain
- **Content:** Average annual wind speed at 30m, 80m, 100m hub heights for entire US
- **Integration:** Wind turbine production estimation (§15.6). Site assessment for wind power. Combine with terrain data for micro-siting.

### 11.3 Global Wind Atlas
- **Source:** World Bank / Technical University of Denmark (DTU)
- **URL:** https://globalwindatlas.info/
- **Format:** GeoTIFF (downloadable raster tiles)
- **Size:** ~10 GB (global at 250m resolution), ~100 MB (single country/state)
- **Resolution:** 250m (120x finer than NREL's Wind Resource at 30km)
- **License:** CC BY 4.0
- **Content:** Mean wind speed, wind power density, Weibull parameters (A and k shape factors) at 10m, 50m, 100m, 150m, 200m heights
- **Integration:** High-resolution wind turbine site assessment — 250m resolution can differentiate ridgelines from valleys. Weibull parameters enable proper energy yield estimation (mean speed alone overpredicts by ~20%). Supplement NREL data (§11.2) with global coverage and higher resolution.
- **Bundle strategy:** Extract user's state at 250m resolution (~20 MB per state).

### 11.4 Utility Rate Database (OpenEI)
- **Source:** Open Energy Information (NREL)
- **URL:** https://openei.org/wiki/Utility_Rate_Database
- **Format:** JSON
- **Size:** ~200 MB
- **License:** CC BY 4.0
- **Content:** Electricity rate structures for 3,800+ US utilities — rate schedules, tiers, time-of-use, demand charges
- **Integration:** Cost savings calculation for solar/battery systems. Grid vs. off-grid cost comparison. "Going off-grid saves you $X/month."

---

## 12. Financial & Precious Metals

### 12.1 Pre-1965 US Coin Silver & Gold Content
- **Source:** US Mint specifications (historical, codified in Coinage Acts)
- **Format:** Embedded lookup table (<10 KB)
- **Content — Silver Coins (90% silver, 10% copper unless noted):**
  - Dimes (1892–1964, Barber/Mercury/Roosevelt): 2.50g total, 2.25g silver = **0.0723 troy oz**
  - Quarters (1892–1964, Barber/Washington): 6.25g total, 5.625g silver = **0.1808 troy oz**
  - Half dollars (1892–1964, Barber/Walking Liberty/Franklin): 12.50g total, 11.25g silver = **0.3617 troy oz**
  - Half dollars (1965–1970, Kennedy 40%): 11.50g total, 4.60g silver = **0.1479 troy oz**
  - Morgan dollars (1878–1921): 26.73g total, 24.06g silver = **0.7734 troy oz**
  - Peace dollars (1921–1935): 26.73g total, 24.06g silver = **0.7734 troy oz**
  - War Nickels (1942–1945, 35% silver): 5.00g total, 1.75g silver = **0.0563 troy oz**
  - Silver Eagles (1986–present, .999 fine): **1.0000 troy oz**
- **Content — Gold Coins:**
  - $5 Half Eagle (1838–1929): **0.2419 troy oz** gold
  - $10 Eagle (1838–1933): **0.4838 troy oz** gold
  - $20 Double Eagle (1849–1933): **0.9675 troy oz** gold
  - American Gold Eagle 1 oz (1986–present): **1.0000 troy oz** gold
  - American Gold Buffalo (2006–present, .9999 fine): **1.0000 troy oz** gold
- **Integration:** Junk silver / gold melt value calculator. Barter value estimation based on metal content × cached spot price. Precious metals inventory valuation. Identify coins by type in inventory and auto-calculate melt value. "$20 face value in pre-1964 quarters = 3.617 troy oz silver × $X/oz = $Y melt value."

### 12.2 Gold/Silver Spot Price (Cached)
- **Source:** Kitco, GoldAPI, MetalsAPI (various free-tier APIs)
- **Format:** JSON (real-time, cache when connected)
- **Content:** Current gold, silver, platinum, palladium prices per troy ounce in USD
- **Integration:** Cache latest prices during internet windows. Auto-update precious metals inventory valuation. Price history tracking. Barter goods valuation baseline.

### 12.3 Ammunition Price Index
- **Source:** AmmoSeek, WikiArms (aggregators)
- **Format:** JSON (API-based, cache locally)
- **Content:** Current retail prices per round by caliber
- **Integration:** Ammunition inventory valuation. Barter value estimation. Price trend tracking for procurement timing.

---

## 13. Offline Knowledge Libraries (ZIM/Kiwix)

> Already integrated via services/kiwix.py ZIM_CATALOG. Documenting additional ZIM files not yet in the catalog that would add value.

### 13.1 Additional High-Value ZIM Files
| ZIM File | Size | Content | Module Value |
|---|---|---|---|
| `wikihow_en_all_maxi_*.zim` | ~55 GB | WikiHow complete — 200K+ how-to articles with images | Massive survival/repair/skills reference |
| `ted_en_all_*.zim` | ~30 GB | TED talks (video) | Morale/education |
| `khan_en_all_*.zim` | ~100 GB+ | Khan Academy complete | Education module (Kolibri alternative) |
| `phet_en_all_*.zim` | ~500 MB | PhET interactive science simulations | Education/training |
| `openstreetmap-wiki_en_all_*.zim` | ~800 MB | OSM wiki — mapping techniques and standards | Map/navigation reference |
| `gardening.stackexchange.com_*.zim` | ~250 MB | Gardening Q&A | Garden module reference |
| `diy.stackexchange.com_*.zim` | ~500 MB | Home improvement Q&A | Repair/construction reference |
| `electronics.stackexchange.com_*.zim` | ~1.2 GB | Electronics Q&A | Electronics repair reference |
| `cooking.stackexchange.com_*.zim` | ~300 MB | Cooking Q&A | Grid-down cooking reference |
| `ham.stackexchange.com_*.zim` | ~100 MB | Amateur radio Q&A | Comms module reference |

### 13.2 ZIM Bundles by Prep Category
Curated ZIM collections for specific scenarios:
- **Medical bundle** (~12 GB): WikiMed + MedlinePlus + NHS + CDC + Military Medicine
- **Survival bundle** (~7 GB): Post-Disaster + Survivors + Knots + Food Prep + Water + Army FMs
- **Homestead bundle** (~3 GB): Appropedia + Energypedia + Gardening SE + Cooking SE
- **Technical bundle** (~5 GB): iFixit + DIY SE + Electronics SE
- **Complete bundle** (~50 GB): All of the above + Wikipedia Top

---

## 14. 3D Printing & Fabrication

### 14.1 NIH 3D Print Exchange
- **Source:** National Institutes of Health
- **URL:** https://3d.nih.gov/
- **Format:** STL, OBJ
- **License:** Public domain (US Government)
- **Content:** Medical devices, anatomical models, lab equipment — many suitable for field medical use (splints, medical devices, prosthetics)
- **Integration:** Curated medical STL library for §50.1.

### 14.2 Thingiverse / Printables Open Models
- **Source:** Community repositories
- **URL:** https://www.thingiverse.com/ and https://www.printables.com/
- **License:** Varies (CC BY, CC BY-SA, GPL — check per model)
- **Content:** Millions of printable models — tools, replacement parts, household items, camping gear, survival tools
- **Integration:** Curate a NOMAD-specific collection of high-value survival/repair prints. Ship as categorized STL library.

### 14.3 GrabCAD Community Library
- **Source:** GrabCAD (Stratasys)
- **URL:** https://grabcad.com/library
- **Format:** STL, STEP, various CAD formats
- **License:** Free download, various licenses
- **Content:** 8M+ CAD models including mechanical parts, tools, fixtures
- **Integration:** Source for replacement parts STL files. Particularly strong in mechanical/engineering parts.

---

## 15. Vehicle & Equipment

### 15.1 NHTSA Vehicle Database
- **Source:** National Highway Traffic Safety Administration
- **URL:** https://vpic.nhtsa.dot.gov/api/
- **Format:** JSON API (cacheable)
- **License:** Public domain
- **Fields:** VIN decode → make, model, year, engine, fuel_type, drive_type, body_class, plant_country, gross_vehicle_weight
- **Integration:** VIN lookup for vehicle profiles (§1.2). Auto-populate vehicle specs from VIN. Fuel type determination for bug-out planning.

### 15.2 EPA Fuel Economy Data
- **Source:** EPA / fueleconomy.gov
- **URL:** https://www.fueleconomy.gov/feg/download.shtml
- **Format:** CSV
- **Size:** ~5 MB
- **License:** Public domain
- **Fields:** year, make, model, fuel_type, city_mpg, highway_mpg, combined_mpg, fuel_tank_capacity_gal, annual_fuel_cost
- **Coverage:** Every vehicle sold in the US since 1984
- **Integration:** Auto-populate MPG for vehicle profiles. Fuel range calculator (tank × MPG = range). Convoy fuel planning. Fleet fuel consumption estimation.

---

## 16. Demographic & Infrastructure

### 16.1 Census Bureau Population Data
- **Source:** US Census Bureau
- **URL:** https://data.census.gov/
- **Format:** CSV, API
- **License:** Public domain
- **Content:** Population by county/ZIP/tract, demographics, housing units, median income
- **Integration:** Community preparedness assessment. Population density for evacuation planning. Resource scaling (population × per-capita needs).

### 16.2 HIFLD Open Data (Homeland Infrastructure Foundation-Level Data)
- **Source:** Department of Homeland Security / HIFLD
- **URL:** https://hifld-geoplatform.opendata.arcgis.com/
- **Format:** Shapefile, GeoJSON, CSV
- **License:** Public domain
- **Content:** Critical infrastructure locations — hospitals, fire stations, police stations, schools, prisons, power plants, substations, water treatment plants, dams, airports, cell towers, broadcast towers
- **Integration:** Critical infrastructure overlay on map. Identify nearest hospital, fire station, shelter. Infrastructure vulnerability assessment. Cell tower locations for communications planning. Dam locations for flood risk.

### 16.3 FCC Broadband Map / Cell Tower Data
- **Source:** FCC
- **URL:** https://broadbandmap.fcc.gov/data-download
- **Format:** CSV, Shapefile
- **License:** Public domain
- **Content:** Cell tower locations, broadband availability, coverage areas
- **Integration:** Communication dead zone mapping. Cell coverage assessment for bug-out routes. Identify areas where only radio/mesh comms will work.

---

## 17. Localization, Regional & Property Assessment

> *Supports features.md §54 (Localization & Regional Profiles), §63 (Land & Property Assessment), §39.9-39.10 (Volcanic Ashfall, Drought)*

### 17.1 FEMA National Risk Index (NRI)
- **Source:** Federal Emergency Management Agency
- **URL:** https://hazards.fema.gov/nri/data-resources
- **Format:** CSV, Shapefile, GeoJSON
- **Size:** ~100 MB (full county-level dataset)
- **License:** Public domain (US Government work)
- **Key datasets:**
  - **County-level risk scores** for 18 natural hazard types (earthquake, hurricane, tornado, flood, wildfire, winter storm, drought, volcanic, tsunami, landslide, lightning, hail, wind, heat wave, cold wave, ice storm, avalanche, coastal flooding)
  - **Expected Annual Loss** (EAL) in dollars per hazard per county
  - **Social Vulnerability Index** and **Community Resilience** scores per county
  - **Historical loss ratio** — actual losses relative to exposure
- **Fields:** county_fips, state, hazard_type, risk_score, eal_value, social_vulnerability, community_resilience, expected_building_loss, expected_population_loss, historic_loss_ratio
- **Integration:** Core dataset for §54 regional profiles. On setup wizard, user enters ZIP → map to county FIPS → auto-populate regional threat profile with ranked hazards. Drive readiness scoring weights (earthquake prep matters 8x more in Napa County than in Iowa). Power regional checklists (show hurricane prep in coastal counties, wildfire in WUI counties).
- **Bundle strategy:** Ship full dataset (~100 MB compressed to ~20 MB). Small enough to bundle. Critical for personalization.

### 17.2 US Census Population Density
- **Source:** U.S. Census Bureau
- **URL:** https://data.census.gov/
- **Format:** CSV (ACS 5-year estimates), Shapefile (TIGER)
- **Size:** ~50 MB (tract-level population + TIGER boundaries)
- **License:** Public domain
- **Key datasets:**
  - **Census tract population** — total population, households, density per square mile
  - **TIGER/Line shapefiles** — geographic boundaries for tracts, counties, places
- **Fields:** tract_fips, total_population, housing_units, area_sq_miles, population_density, state, county
- **Integration:** BOL comparison tool (§63.4) — score neighbor density. Bug-out route analysis — identify high-population chokepoints. Multi-household pod management (§56) — assess pod geographic spread relative to population centers.
- **Bundle strategy:** Tier 2 downloadable pack. Offer state-level subsets (~5 MB each).

### 17.3 USGS 3DEP LiDAR Elevation Data
- **Source:** U.S. Geological Survey — 3D Elevation Program
- **URL:** https://apps.nationalmap.gov/downloader/
- **Format:** GeoTIFF (DEM), LAZ (point cloud)
- **Size:** ~100 MB–2 GB per county (1/3 arc-second DEM)
- **License:** Public domain
- **Key datasets:**
  - **1/3 arc-second DEM** (~10m resolution) — nationwide coverage
  - **1-meter DEM** — available for most of CONUS (very large files)
- **Fields:** elevation (meters), lat, lng — raster grid
- **Integration:** Property terrain profiling (§63.2), sight line analysis (§63.2), defensive position assessment (§63.1), gravity-fed water system head calculation (§19 expansion), swale/berm contour planning (§58.2). Can compute line-of-sight between any two points on user's property.
- **Bundle strategy:** Tier 3 — user downloads their local area DEM tiles. Provide tile picker in Data Packs manager.

### 17.4 SSURGO Soil Survey
- **Source:** USDA Natural Resources Conservation Service
- **URL:** https://nrcs.app.box.com/v/soils/ (state downloads)
- **Format:** SQLite (gSSURGO), Shapefile, CSV
- **Size:** ~200-800 MB per state
- **License:** Public domain
- **Key datasets:**
  - **Soil map units** with spatial boundaries
  - **Component data** — soil texture, drainage class, depth to water table, depth to bedrock
  - **Interpretive data** — agricultural capability class, septic suitability, building suitability, flood frequency
- **Fields:** musym, muname, texture, drainage_class, depth_bedrock, ksat (permeability), slope, capability_class, hydric_rating, flood_frequency
- **Integration:** Garden site selection (§63.3), soil quality scoring (§63.1), septic system planning (§12.3), well siting (§63.3), building site assessment (§63.3). The capability class alone (I through VIII) tells you if land is farmable.
- **Bundle strategy:** Tier 3. Offer state-level downloads through Data Packs.

### 17.5 USGS National Hydrography Dataset (NHD)
- **Source:** U.S. Geological Survey
- **URL:** https://www.usgs.gov/national-hydrography/access-national-hydrography-products
- **Format:** GeoPackage, Shapefile
- **Size:** ~200-800 MB per state (NHDPlus HR)
- **License:** Public domain
- **Content:** Stream/river network, waterbodies, springs, wells, watersheds, flow direction, stream order
- **Integration:** Water source mapping for property assessment (§63.2), watercraft route planning (§62.3), watershed delineation for water supply analysis, spring development identification (§1.4 Water Management).
- **Bundle strategy:** Tier 3 — state subsets. Already listed as Tier 2 item #30 in existing matrix; promote to dedicated entry here for §63 integration.

### 17.6 Smithsonian GVP Eruption Database
- **Source:** Smithsonian Institution — Global Volcanism Program
- **URL:** https://volcano.si.edu/database/search_eruption_results.cfm
- **Format:** CSV, KML
- **Size:** ~5 MB
- **License:** Creative Commons BY
- **Content:** 12,000+ eruptions, 1,500+ volcanoes, eruption dates, VEI (Volcanic Explosivity Index), eruption type, tephra volume
- **Integration:** §39.9 Volcanic Ashfall — identify volcanoes within ashfall range of user location, historical eruption frequency and VEI, prevailing wind direction → ashfall probability zones. Combined with NRI data for volcanic hazard scoring.
- **Bundle strategy:** Tier 1 — small enough to bundle (~5 MB). High value for Pacific Northwest, Alaska, Hawaii users.

### 17.7 US Drought Monitor
- **Source:** University of Nebraska-Lincoln / USDA / NOAA
- **URL:** https://droughtmonitor.unl.edu/DmData/DataDownload.aspx
- **Format:** CSV, Shapefile, GeoJSON
- **Size:** ~50 MB (historical archive), ~500 KB (current week)
- **License:** Public domain
- **Content:** Weekly drought severity classification (D0-D4) by county, historical drought duration, drought impact types
- **Integration:** §39.10 Drought & Water Crisis — auto-alert when user's county enters D2+ drought, trigger water conservation protocols, historical drought frequency for BOL assessment (§63.4).
- **Bundle strategy:** Tier 2 — download historical archive for user's state. Current conditions via periodic API fetch (when online).

---

## 18. Alternative Transportation & Pack Animals

> *Supports features.md §62 (Alternative Transportation)*

### 18.1 USGS National Transportation Dataset
- **Source:** U.S. Geological Survey
- **URL:** https://www.sciencebase.gov/catalog/item/4f70b1f4e4b058caae3f8e16
- **Format:** Shapefile, GeoPackage
- **Size:** ~2 GB (national)
- **License:** Public domain
- **Content:** Roads classified by type (interstate, US highway, state highway, county road, local road, trail, 4WD), railroads, airports, ferry terminals
- **Integration:** Multi-modal route planning (§62.4) — identify which roads are passable by bike vs vehicle vs foot. Trail network for horse/foot routes. Ferry crossings for watercraft planning. 4WD road identification for ATV routes.
- **Bundle strategy:** Tier 3 — state subsets available. Most useful data overlaps with OpenStreetMap which is already in the Tier 3 matrix.

### 18.2 USDA Horse & Pack Animal Reference Data
- **Source:** Various USDA/Extension Service publications (public domain)
- **Format:** Structured text/JSON (manually compiled from public domain sources)
- **Size:** ~100 KB
- **License:** Public domain
- **Content:**
  - Load capacity by species (horse, mule, donkey, llama, goat) × body weight percentage × terrain factor
  - Daily feed requirements by species × body weight × workload (idle/light/moderate/heavy)
  - Daily water requirements by species × body weight × temperature × workload
  - Hoof care intervals, common ailments, emergency veterinary reference
  - Pack saddle fitting guide
- **Integration:** §62.2 — auto-calculate load plans and feed requirements per animal. Generate trip supply lists (animal feed + water) for route planning.
- **Bundle strategy:** Tier 1 — tiny dataset, manually curated from public domain extension service publications.

### 18.3 American Whitewater River Database
- **Source:** American Whitewater
- **URL:** https://www.americanwhitewater.org/content/River/view/ (database accessible via site)
- **Format:** Structured data (scrape-to-JSON)
- **Size:** ~10 MB
- **License:** Community-contributed, check terms
- **Content:** 6,000+ river sections with difficulty class (I-VI), put-in/take-out GPS, length, gradient, optimal flow ranges, hazard notes
- **Integration:** §62.3 Watercraft route planning — identify navigable waterway sections, difficulty assessment, portage points. Combined with NHD for complete water route planning.
- **Bundle strategy:** Tier 2 — state subsets. May need to compile from public-domain sources instead if licensing is restrictive.

---

## 19. Permaculture, Mycology & Long-Term Agriculture

> *Supports features.md §58 (Permaculture & Long-Term Food Systems), §23 expansions (Mycology)*

### 19.1 USDA PLANTS Database — Perennial Food Species
- **Source:** USDA Natural Resources Conservation Service
- **URL:** https://plants.usda.gov/home/downloads
- **Format:** CSV
- **Size:** ~50 MB (full database)
- **License:** Public domain
- **Content:** 100,000+ plant species with native range, growth habit, duration (annual/perennial/biennial), edibility notes, nitrogen fixation, bloom period, moisture requirements, shade tolerance, hardiness zones
- **Fields:** symbol, scientific_name, common_name, growth_habit, duration, native_status, edible, n_fixer, bloom_period, moisture_use, shade_tolerance, min_zone, max_zone
- **Integration:** Food forest design (§58.1) — filter for perennial + edible + user's hardiness zone → species recommendations per layer. Guild planting (§58.1) — identify nitrogen fixers for each guild. Pollinator habitat (§58.3) — bloom period calendar. Already listed in datasources.md Tier 2 #33; this entry adds the §58-specific integration notes.

### 19.2 PFAF Plants For A Future Database
- **Source:** Plants For A Future (UK charity)
- **URL:** https://pfaf.org/user/DatabaseSeeds.aspx
- **Format:** Downloadable database (access database / CSV export)
- **Size:** ~20 MB
- **License:** Creative Commons (check specific terms)
- **Content:** 8,000+ useful plant species with edibility rating (1-5), medicinal rating (1-5), cultivation details, habitat, propagation, uses (food, medicine, material, fuel, etc.)
- **Fields:** latin_name, common_name, edibility_rating, medicinal_rating, hardiness_zone, habitat, height, width, soil_preference, light_preference, moisture, propagation_method, uses
- **Integration:** Food forest layer planning (§58.1) — edibility-rated species for each layer, medicinal plants for herb spiral (§58.3). Material substitution (§57) — which plants produce cordage, dye, soap, insecticide.
- **Bundle strategy:** Tier 2 — curated subset of highest-rated edible perennials for North America (~2 MB).

### 19.3 Mushroom Observer / MycoPortal
- **Source:** Mushroom Observer (community science) / MycoPortal (mycological herbaria)
- **URL:** https://mushroomobserver.org/articles/api2 / https://mycoportal.org/portal/
- **Format:** CSV export, Darwin Core format
- **Size:** ~50 MB (North America edible/medicinal subset)
- **License:** CC BY-NC (Mushroom Observer), varies (MycoPortal)
- **Content:** Species occurrence records with GPS, habitat, substrate, season, photos, identification confidence
- **Integration:** §23 expansion (Mycology) — which edible/medicinal mushrooms occur in user's region, seasonal fruiting calendar, habitat association (oak forest = chanterelles, dead hardwood = shiitake/oyster). WARNING: mushroom ID must include prominent "expert verification required" warnings — misidentification can be fatal.
- **Bundle strategy:** Tier 2 — curated edible/medicinal subset for user's state. Include safety disclaimer and "never eat without expert confirmation" warnings on every screen.

### 19.4 Companion Planting & Guild Databases
- **Source:** Multiple public-domain extension service publications
- **Format:** JSON (manually compiled)
- **Size:** ~200 KB
- **License:** Public domain
- **Content:**
  - Companion/antagonist plant pairings (500+ pairs) — extends NOMAD's existing 20 pairs
  - Permaculture guild definitions (apple guild, cherry guild, nut tree guild — 15+ pre-built guilds)
  - Nitrogen fixation rates by species (lbs N per acre per year)
  - Dynamic accumulator species (comfrey, yarrow, dandelion — which minerals they mine)
  - Pollinator attraction ratings by species
- **Integration:** §58.1 Guild planting designer — pre-built guild templates. §58.3 Nitrogen-fixer inventory — quantified N contribution. Extends existing companion_plants table.
- **Bundle strategy:** Tier 1 — small, high-impact, directly extends existing data.

---

## 20. Human Performance & Sleep Science

> *Supports features.md §59 (Sleep, Rest & Human Performance)*

### 20.1 Military Work-Rest Guidelines
- **Source:** U.S. Army / NIOSH / OSHA (public domain publications)
- **Format:** JSON (manually compiled from TB MED 507, NIOSH criteria documents)
- **Size:** ~50 KB
- **License:** Public domain (US Government works)
- **Content:**
  - **WBGT-based work-rest tables** — at each heat category (I-V), maximum continuous work time and minimum rest time by exertion level (easy/moderate/hard)
  - **Cold weather work schedules** — wind chill exposure limits, mandatory warming break intervals
  - **Water intake requirements** — quarts per hour by heat category and exertion level
  - **Sleep debt performance curves** — cognitive and physical performance degradation by hours of sleep lost (from Walter Reed Army Institute research)
  - **Altitude acclimatization schedule** — activity restrictions by day at elevation
  - **Load-bearing endurance tables** — max march distance by load weight and terrain type
- **Fields:** heat_category, exertion_level, work_minutes, rest_minutes, water_qt_per_hr, wind_chill_threshold, sleep_debt_hours, cognitive_performance_pct, physical_performance_pct
- **Integration:** Core dataset for §59. Auto-generate work-rest schedules from current temperature + task type. Warn when sleep debt crosses dangerous thresholds. Calculate water requirements for planned activities.
- **Bundle strategy:** Tier 1 — tiny, critical, directly sourced from public domain military technical bulletins.

### 20.2 NASA Task Load Index (TLX) Reference
- **Source:** NASA Human Systems Integration Division
- **URL:** https://humansystems.arc.nasa.gov/groups/TLX/
- **Format:** Reference methodology (manually compiled into JSON)
- **Size:** ~10 KB
- **License:** Public domain (NASA)
- **Content:** Standardized workload assessment dimensions (mental demand, physical demand, temporal demand, performance, effort, frustration) with rating scales
- **Integration:** §59.3 Group Performance Monitoring — standardized self-assessment tool for task difficulty, feeds into task assignment optimizer.
- **Bundle strategy:** Tier 1 — reference methodology, almost zero storage.

---

## 21. Dispute Resolution & Group Governance

> *Supports features.md §61 (Dispute Resolution & Group Dynamics), §15.10 (Group Governance)*

### 21.1 FEMA CERT Training Materials
- **Source:** FEMA Emergency Management Institute
- **URL:** https://www.fema.gov/emergency-managers/individuals-communities/preparedness-activities-webinars/community-emergency-response-team
- **Format:** PDF, structured content
- **Size:** ~50 MB (full CERT curriculum)
- **License:** Public domain (US Government work)
- **Content:**
  - CERT Basic Training curriculum (disaster preparedness, fire safety, medical operations, light SAR, team organization, disaster psychology)
  - ICS-100 and IS-700 introductory materials
  - CERT organizational structure templates
  - Damage assessment forms
  - Search and rescue marking system
  - Team leader checklists
- **Integration:** §44 expansion (CERT integration) — pre-built forms, training checklists, organizational templates. §22 Training — structured CERT curriculum import. §61 — team organization and leadership succession templates derived from CERT structure.
- **Bundle strategy:** Tier 1 — essential training reference. Curate key forms and checklists (~5 MB subset). Full curriculum as Tier 2 expansion.

### 21.2 Robert's Rules of Order (Simplified Reference)
- **Source:** Public domain (original 1876 edition), modern adaptations under various licenses
- **Format:** JSON (manually compiled simplified reference)
- **Size:** ~50 KB
- **License:** Public domain (original text); simplified reference compiled from public domain sources
- **Content:**
  - Meeting procedure templates (call to order, quorum check, agenda, motions, voting, adjournment)
  - Motion types and precedence (main motion, amend, table, previous question, adjourn)
  - Voting methods (voice, show of hands, roll call, secret ballot — when to use each)
  - Common procedural scenarios (tie vote, no quorum, contested election, emergency meeting)
- **Integration:** §61.2 Decision-Making Systems — structured meeting facilitation. §15.10 Group Governance — formal decision-making procedures. §60 Knowledge Preservation — documented decision-making process.
- **Bundle strategy:** Tier 1 — tiny reference dataset.

---

## 22. Integration Priority Matrix

### Tier 1: Bundle with NOMAD (small, high-impact, offline)
| # | Data Source | Size | Impact |
|---|---|---|---|
| 1 | USDA FoodData Central (SR Legacy) | ~25 MB | Nutritional gap analysis, calorie tracking |
| 2 | FDA NDC Drug Directory | ~50 MB | Medication identification, inventory enhancement |
| 3 | FEMA National Risk Index | ~100 MB | Location-based threat assessment, auto-recommendations |
| 4 | NOAA Climate Normals (frost dates) | ~2 MB | Precise garden planning, seasonal checklists |
| 5 | NOAA Weather Radio stations | ~200 KB | Auto-configure weather radio by location |
| 6 | NRC Nuclear facility locations | ~100 KB | NukeMap enhancement, fallout risk assessment |
| 7 | USDA FoodKeeper shelf life JSON | ~500 KB | Auto-set shelf life on inventory items |
| 8 | Pre-1965 coin silver/gold content | ~10 KB | Barter value calculator |
| 9 | FRS/GMRS/MURS channel reference | ~10 KB | Radio programming, comms planning |
| 10 | Firewood BTU ratings | ~10 KB | Heating fuel calculations |
| 11 | World Magnetic Model + IGRF-14 | ~1 MB | Compass correction for navigation |
| 12 | Venomous species reference | ~500 KB | First aid by species, regional awareness |
| 13 | MIL-STD-2525 SVG icons | ~5 MB | Military map symbology option |
| 14 | ICS Resource Typing definitions | ~2 MB | Standardized emergency resource categories |
| 15 | EPA fuel economy data | ~5 MB | Vehicle range calculations |
| 16 | PRISM hardiness zone by ZIP code | ~3 MB | Instant zone lookup without GIS |
| 17 | NREL Solar Position Algorithm (SPA) | ~50 KB | Reference-grade sun position calculations |
| 18 | HYG star database (navigational subset) | ~500 KB | Celestial navigation star chart |
| 19 | DDInter drug interactions | ~30 MB | 240K interaction pairs with severity levels |
| 20 | NIOSH Pocket Guide (677 chemicals) | ~10 MB | Chemical hazard identification & first aid |
| 21 | EPA AEGLs (acute exposure levels) | ~5 MB | Chemical shelter-in-place duration decisions |
| 22 | XTide harmonics database | ~15 MB | Offline tide prediction, 5000+ stations |
| 23 | Kew Seed Information Database (subset) | ~5 MB | Science-backed seed viability/germination data |
| 24 | FEMA National Risk Index (NRI) | ~20 MB | Regional threat profiles, hazard scoring, localization |
| 25 | Military work-rest tables (TB MED 507) | ~50 KB | Heat/cold work schedules, sleep debt curves |
| 26 | Smithsonian GVP eruption database | ~5 MB | Volcanic hazard assessment, ashfall risk |
| 27 | Companion planting & guild database | ~200 KB | 500+ plant pairings, 15+ permaculture guilds |
| 28 | USDA pack animal reference data | ~100 KB | Load capacity, feed, water by species |
| 29 | NASA TLX workload assessment | ~10 KB | Standardized task difficulty self-assessment |
| 30 | Robert's Rules simplified reference | ~50 KB | Meeting procedures, voting methods, governance |
| 31 | FEMA CERT training materials (subset) | ~5 MB | CERT forms, checklists, curriculum |

### Tier 2: Downloadable Expansion Packs (~100 MB–1 GB each)
| # | Data Source | Size | Impact |
|---|---|---|---|
| 24 | Open Food Facts (US subset) | ~400 MB | Barcode scanning auto-populate |
| 25 | RepeaterBook amateur repeaters | ~10 MB | Local repeater discovery |
| 26 | USGS Earthquake catalog + faults | ~500 MB | Seismic risk mapping |
| 27 | SRTM elevation tiles (local area) | ~100 MB | Terrain analysis, LOS, elevation profiles |
| 28 | NOAA Storm Events (state subset) | ~100 MB | Historical threat analysis |
| 29 | USDA Plant Hardiness Zone GIS | ~50 MB | Precise zone lookup (full GIS) |
| 30 | National Hydrography Dataset (state) | ~500 MB | Water source mapping |
| 31 | NREL solar irradiance by county | ~500 KB | Solar panel sizing |
| 32 | HIFLD critical infrastructure | ~200 MB | Infrastructure overlay on map |
| 33 | USDA PLANTS database | ~50 MB | Plant identification, edibility, toxicity |
| 34 | SIDER side effects database | ~200 MB | 140K drug–side effect pairs |
| 35 | ATSDR ToxFAQs summaries | ~5 MB | 300+ hazardous substance quick-ref profiles |
| 36 | NOAA ISD (nearest station, 10yr) | ~5 MB | Historical hourly weather patterns |
| 37 | iNaturalist/GBIF (state, survival taxa) | ~50 MB | Regional species occurrence data |
| 38 | FishBase (state freshwater subset) | ~2 MB | Fish species ID, nutrition, habitat |
| 39 | Global Wind Atlas (state, 250m) | ~20 MB | High-res wind turbine siting |
| 40 | US Census population density (tract) | ~50 MB | BOL neighbor density, route chokepoints |
| 41 | US Drought Monitor (state archive) | ~50 MB | Historical drought frequency, water crisis alerts |
| 42 | PFAF edible perennials (NA subset) | ~2 MB | Food forest species selection, edibility ratings |
| 43 | Mushroom Observer (state edible subset) | ~50 MB | Regional edible mushroom occurrence, season |
| 44 | American Whitewater river sections | ~10 MB | Navigable waterway database, difficulty class |

### Tier 3: Large Datasets for Power Users (~1 GB+)
| # | Data Source | Size | Impact |
|---|---|---|---|
| 40 | OpenStreetMap state extract | 1–10 GB | Full offline mapping + routing |
| 41 | FEMA National Flood Hazard Layer | ~20 GB | Flood zone overlay |
| 42 | SSURGO soil data | ~500 MB/state | Soil analysis, gardening, septic |
| 43 | Open Food Facts (global) | ~7 GB | Complete barcode database |
| 44 | DailyMed drug labels (top 500) | ~500 MB | Complete drug information |
| 45 | DrugBank Open (full interactions) | ~50 MB | 2.5M drug interaction pairs |
| 46 | ESA WorldCover (state, 10m) | ~500 MB–2 GB | High-res land cover / concealment analysis |
| 47 | ETOPO global relief model | ~2 GB | Land + ocean bathymetry |
| 48 | FishBase full database | ~2 GB | 35K+ fish species worldwide |
| 49 | iNaturalist/GBIF (full state export) | ~2 GB | Complete biodiversity occurrence records |
| 50 | USGS 3DEP LiDAR DEM (county) | ~100 MB-2 GB | Property terrain analysis, sight lines, water head |
| 51 | SSURGO soil survey (state) | ~200-800 MB | Soil quality, ag capability, septic, building suitability |
| 52 | NHD hydrography (state) | ~200-800 MB | Stream network, springs, watersheds, water routes |
| 53 | USGS transportation dataset (state) | ~200 MB | Road classification, trails, multi-modal routing |

---

## Existing Data in NOMAD (Already Bundled)

For reference, NOMAD already ships with:
- **UPC database** — 76 pre-seeded survival/prep items across 6 categories (db.py line 1349)
- **USDA Hardiness Zones** — Simplified latitude-based lookup for 13 zones (garden.py line 12)
- **Seed Viability** — 20 common species with viability in years (garden.py line 24)
- **Companion Plants** — Plant relationship database (companion_plants table)
- **Pest Guide** — Garden pest reference (pest_guide table)
- **Drug Interactions** — 20 common drug interaction pairs (medical.py line 22)
- **Dosage Guide** — 10 emergency drug dosages for adult/pediatric (medical.py line 53)
- **TCCC/MARCH Protocol** — 5-step tactical combat casualty care reference (medical.py line 82)
- **Medical Reference** — Vital signs, triage (START), burns, bleeding, fractures, environmental (medical.py line 639)
- **Planting Calendar** — Zone 7 default with 25+ crops, calories per pound (garden.py line 221)
- **YouTube Catalog** — 210 channels across 26 prepping categories (catalog.py)
- **ZIM Catalog** — 30+ curated offline knowledge resources across 6 categories (kiwix.py line 25)
- **NukeMap** — Nuclear target database, compiled targets list (nukemap/data/compiled_targets.js)

---

## Data Integration Architecture Notes

### Storage Strategy
- **Tier 1 data** → Bundled in `data/` directory, loaded into SQLite at first run
- **Tier 2 data** → Downloadable via in-app "Data Packs" manager, stored in user data directory
- **Tier 3 data** → Optional download, external storage support (USB drive, NAS)

### Update Strategy
- Cache internet-dependent data (spot prices, space weather, news feeds) during internet windows
- Provide `data pack version` tracking — user can update bundled datasets when connected
- All data must degrade gracefully — if a dataset isn't downloaded, the feature works with reduced capability, never crashes

### Privacy Considerations
- No dataset should require user account creation or API key for the bundled portion
- Downloaded datasets should be stored locally, never phoned home
- Location-based data filtering should happen locally, not via server-side API
