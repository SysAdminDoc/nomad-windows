// NukeMap - WW3 Simulation Module
// Full-scale nuclear war simulation with phased escalation, missile arcs, and target databases
window.NM = window.NM || {};

// ---- TARGET DATABASES ----

// Auto-generated target database from verified research data

// US targets (175 targets)
NM.WW3_TARGETS_US = [
  {name:'Malmstrom AFB',lat:47.5050,lng:-111.1872,type:'icbm',warheads:8,yieldKt:800,cat:'341st Missile Wing, 150 Minuteman III silos across central M'},
  {name:'Minot AFB',lat:48.4159,lng:-101.3306,type:'icbm',warheads:8,yieldKt:800,cat:'91st Missile Wing, 150 Minuteman III silos across North Dako'},
  {name:'F.E. Warren AFB',lat:41.1265,lng:-104.8668,type:'icbm',warheads:8,yieldKt:800,cat:'90th Missile Wing, 150 Minuteman III silos across WY/CO/NE'},
  {name:'Malmstrom MAF Alpha (A-01)',lat:47.2817,lng:-110.8008,type:'icbm',warheads:2,yieldKt:455,cat:'Launch Control Center, 341st MW, SE of Belt, MT'},
  {name:'Malmstrom MAF Foxtrot (F-01)',lat:47.6047,lng:-112.3106,type:'icbm',warheads:2,yieldKt:455,cat:'Launch Control Center, 341st MW, NNE of Augusta, MT'},
  {name:'Malmstrom MAF Kilo (K-01)',lat:46.4453,lng:-109.8014,type:'icbm',warheads:2,yieldKt:455,cat:'Launch Control Center, 341st MW, near Harlowton, MT'},
  {name:'Malmstrom MAF Papa (P-00)',lat:48.2050,lng:-111.9086,type:'icbm',warheads:2,yieldKt:455,cat:'Launch Control Center, 341st MW, NE of Conrad, MT'},
  {name:'Whiteman AFB',lat:38.7289,lng:-93.5605,type:'bomber',warheads:2,yieldKt:455,cat:'509th Bomb Wing, all 19 B-2 Spirit stealth bombers, nuclear-'},
  {name:'Barksdale AFB',lat:32.5019,lng:-93.6626,type:'bomber',warheads:2,yieldKt:455,cat:'2nd Bomb Wing, ~44 B-52H Stratofortress bombers, AFGSC HQ'},
  {name:'Dyess AFB',lat:32.4185,lng:-99.8565,type:'bomber',warheads:2,yieldKt:455,cat:'7th Bomb Wing, ~33 B-1B Lancers, sole B-1B training unit'},
  {name:'Ellsworth AFB',lat:44.1453,lng:-103.1022,type:'bomber',warheads:2,yieldKt:455,cat:'28th Bomb Wing, B-1B Lancers, future B-21 Raider base'},
  {name:'Naval Base Kitsap-Bangor',lat:47.7195,lng:-122.7191,type:'sub',warheads:3,yieldKt:800,cat:'Pacific Fleet Trident base, 8 Ohio-class SSBNs, SWFPAC nucle'},
  {name:'Naval Submarine Base Kings Bay',lat:30.7968,lng:-81.5328,type:'sub',warheads:3,yieldKt:800,cat:'Atlantic Fleet Trident base, 6 Ohio-class SSBNs, SWFLANT nuc'},
  {name:'Cheyenne Mountain Complex',lat:38.7443,lng:-104.8468,type:'c2',warheads:2,yieldKt:455,cat:'NORAD/USNORTHCOM alternate command center, deep underground '},
  {name:'Peterson Space Force Base',lat:38.8236,lng:-104.6950,type:'c2',warheads:2,yieldKt:455,cat:'NORAD & USNORTHCOM headquarters, Space Force operations'},
  {name:'Offutt AFB',lat:41.1243,lng:-95.9146,type:'c2',warheads:2,yieldKt:455,cat:'US Strategic Command (USSTRATCOM) headquarters, E-4B Nightwa'},
  {name:'The Pentagon',lat:38.8719,lng:-77.0563,type:'c2',warheads:3,yieldKt:800,cat:'Department of Defense headquarters, National Military Comman'},
  {name:'The White House',lat:38.8977,lng:-77.0366,type:'c2',warheads:2,yieldKt:455,cat:'President/Commander-in-Chief residence, Situation Room'},
  {name:'US Capitol Building',lat:38.8898,lng:-77.0091,type:'c2',warheads:2,yieldKt:455,cat:'Seat of Congress, legislative branch headquarters'},
  {name:'Raven Rock Mountain Complex (Site R)',lat:39.7340,lng:-77.4190,type:'c2',warheads:2,yieldKt:455,cat:'Alternate National Military Command Center, underground Pent'},
  {name:'Mount Weather EOC',lat:39.0645,lng:-77.8899,type:'c2',warheads:2,yieldKt:455,cat:'FEMA continuity of government facility, presidential fallout'},
  {name:'Camp David',lat:39.6483,lng:-77.4650,type:'c2',warheads:2,yieldKt:455,cat:'Presidential retreat, near Raven Rock, hardened communicatio'},
  {name:'Tinker AFB',lat:35.4148,lng:-97.3866,type:'c2',warheads:2,yieldKt:455,cat:'E-6B Mercury TACAMO base, nuclear communications relay to su'},
  {name:'Joint Base Andrews',lat:38.8108,lng:-76.8674,type:'c2',warheads:2,yieldKt:455,cat:'Air Force One base, National Capital Region defense'},
  {name:'Schriever Space Force Base',lat:38.8033,lng:-104.5256,type:'c2',warheads:2,yieldKt:455,cat:'Satellite command & control for 170+ DoD satellites, missile'},
  {name:'Buckley Space Force Base',lat:39.7010,lng:-104.7510,type:'c2',warheads:2,yieldKt:455,cat:'Space-based infrared missile warning, intelligence processin'},
  {name:'Pantex Plant',lat:35.3116,lng:-101.5597,type:'nuclear',warheads:1,yieldKt:300,cat:'Only US nuclear weapons assembly/disassembly facility, Amari'},
  {name:'Y-12 National Security Complex',lat:35.9863,lng:-84.2528,type:'nuclear',warheads:1,yieldKt:300,cat:'Enriched uranium weapons components, Oak Ridge TN'},
  {name:'Los Alamos National Laboratory',lat:35.8757,lng:-106.2923,type:'nuclear',warheads:1,yieldKt:300,cat:'Nuclear weapons design & plutonium science, Los Alamos NM'},
  {name:'Lawrence Livermore National Lab',lat:37.6858,lng:-121.7055,type:'nuclear',warheads:1,yieldKt:300,cat:'Nuclear weapons research & design, Livermore CA'},
  {name:'Sandia National Laboratories (NM)',lat:35.0507,lng:-106.5431,type:'nuclear',warheads:1,yieldKt:300,cat:'Non-nuclear weapons components R&D, Kirtland AFB, Albuquerqu'},
  {name:'Sandia National Laboratories (CA)',lat:37.6744,lng:-121.7066,type:'nuclear',warheads:1,yieldKt:300,cat:'California branch, adjacent to LLNL, Livermore CA'},
  {name:'Savannah River Site',lat:33.2464,lng:-81.6679,type:'nuclear',warheads:1,yieldKt:300,cat:'Tritium supply & processing for nuclear weapons, Aiken SC'},
  {name:'Kansas City National Security Campus',lat:38.9581,lng:-94.5689,type:'nuclear',warheads:1,yieldKt:300,cat:'Electronic, mechanical & material components for nuclear wea'},
  {name:'Nevada National Security Site',lat:37.1167,lng:-116.0500,type:'nuclear',warheads:1,yieldKt:300,cat:'Former nuclear test site, subcritical experiments, stockpile'},
  {name:'Kirtland AFB',lat:35.0403,lng:-106.6092,type:'nuclear',warheads:1,yieldKt:300,cat:'Largest nuclear weapons storage area in US (Manzano/Coyote C'},
  {name:'Oak Ridge National Laboratory',lat:35.9310,lng:-84.3100,type:'nuclear',warheads:1,yieldKt:300,cat:'DOE multipurpose research lab, Oak Ridge TN'},
  {name:'MacDill AFB (CENTCOM/SOCOM)',lat:27.8493,lng:-82.5212,type:'military',warheads:1,yieldKt:300,cat:'US Central Command & Special Operations Command headquarters'},
  {name:'Fort Bragg',lat:35.1392,lng:-78.9992,type:'military',warheads:1,yieldKt:300,cat:'XVIII Airborne Corps, Army Special Operations Command, 52,00'},
  {name:'Fort Hood (Fort Cavazos)',lat:31.1363,lng:-97.7797,type:'military',warheads:1,yieldKt:300,cat:'III Corps, 1st Cavalry Division, largest active-duty armored'},
  {name:'Camp Pendleton',lat:33.3000,lng:-117.3500,type:'military',warheads:1,yieldKt:300,cat:'I Marine Expeditionary Force, major West Coast Marine base'},
  {name:'Camp Lejeune',lat:34.5890,lng:-77.3388,type:'military',warheads:1,yieldKt:300,cat:'II Marine Expeditionary Force, major East Coast Marine base'},
  {name:'Naval Station Norfolk',lat:36.9474,lng:-76.3169,type:'military',warheads:1,yieldKt:300,cat:'World\'s largest naval station, Fleet Forces Command HQ, 75+'},
  {name:'Naval Base San Diego',lat:32.6756,lng:-117.1199,type:'military',warheads:1,yieldKt:300,cat:'Principal Pacific Fleet homeport, 50+ ships'},
  {name:'Joint Base Pearl Harbor-Hickam',lat:21.3489,lng:-157.9436,type:'military',warheads:1,yieldKt:300,cat:'US Pacific Fleet HQ, US Indo-Pacific Command nearby'},
  {name:'NSA - Fort Meade',lat:39.1090,lng:-76.7700,type:'military',warheads:1,yieldKt:300,cat:'National Security Agency & US Cyber Command headquarters'},
  {name:'CIA - Langley',lat:38.9518,lng:-77.1466,type:'military',warheads:1,yieldKt:300,cat:'Central Intelligence Agency headquarters, Fairfax County VA'},
  {name:'DIA - Anacostia-Bolling',lat:38.8463,lng:-77.0132,type:'military',warheads:1,yieldKt:300,cat:'Defense Intelligence Agency headquarters, Washington DC'},
  {name:'Fort Meade',lat:39.1082,lng:-76.7432,type:'military',warheads:1,yieldKt:300,cat:'US Army Cyber Command, NSA co-located'},
  {name:'Nellis AFB',lat:36.2414,lng:-115.0508,type:'military',warheads:1,yieldKt:300,cat:'USAF Warfare Center, largest air combat training range (NTTR'},
  {name:'Travis AFB',lat:38.2721,lng:-121.9399,type:'military',warheads:1,yieldKt:300,cat:'Largest Air Mobility Command base on West Coast, strategic a'},
  {name:'Fairchild AFB',lat:47.6188,lng:-117.6483,type:'military',warheads:1,yieldKt:300,cat:'KC-135 tanker base, survival school, strategic refueling sup'},
  {name:'Beale AFB',lat:39.1388,lng:-121.4389,type:'military',warheads:1,yieldKt:300,cat:'ISR hub, U-2 Dragon Lady, Global Hawk operations'},
  {name:'Creech AFB',lat:36.5863,lng:-115.6774,type:'military',warheads:1,yieldKt:300,cat:'MQ-9 Reaper drone operations center, combat UAV hub'},
  {name:'Fort Eisenhower (formerly Gordon)',lat:33.4170,lng:-82.1350,type:'military',warheads:1,yieldKt:300,cat:'US Army Cyber Center of Excellence, signals intelligence tra'},
  {name:'Redstone Arsenal',lat:34.6849,lng:-86.6530,type:'military',warheads:1,yieldKt:300,cat:'Army missile/aviation, Space & Missile Defense Command, Hunt'},
  {name:'Wright-Patterson AFB',lat:39.8261,lng:-84.0483,type:'military',warheads:1,yieldKt:300,cat:'Air Force Materiel Command HQ, National Air & Space Intel Ce'},
  {name:'Port of Los Angeles',lat:33.7292,lng:-118.2620,type:'infra',warheads:1,yieldKt:300,cat:'Largest container port in Western Hemisphere'},
  {name:'Port of Long Beach',lat:33.7542,lng:-118.2165,type:'infra',warheads:1,yieldKt:300,cat:'Second busiest US port, adjacent to Port of LA'},
  {name:'Port of Houston',lat:29.6111,lng:-95.0217,type:'infra',warheads:1,yieldKt:300,cat:'Largest US port by tonnage, 25-mile ship channel complex'},
  {name:'Port of Savannah',lat:32.0809,lng:-81.0912,type:'infra',warheads:1,yieldKt:300,cat:'Fastest-growing major US container port'},
  {name:'Port of New York/New Jersey',lat:40.6683,lng:-74.0364,type:'infra',warheads:6,yieldKt:800,cat:'Largest East Coast port, Newark-Elizabeth complex'},
  {name:'Port of Norfolk/Hampton Roads',lat:36.8508,lng:-76.2859,type:'infra',warheads:1,yieldKt:300,cat:'Deep-water port, coal export, naval operations'},
  {name:'Port of Seattle/Tacoma',lat:47.5815,lng:-122.3480,type:'infra',warheads:1,yieldKt:300,cat:'Northwest Seaport Alliance, major Pacific trade hub'},
  {name:'Port of Charleston',lat:32.7876,lng:-79.9249,type:'infra',warheads:1,yieldKt:300,cat:'Major East Coast container port, deep water'},
  {name:'Houston Ship Channel Refinery Complex',lat:29.7500,lng:-95.0800,type:'infra',warheads:1,yieldKt:300,cat:'Multiple refineries, 2.6M bbl/day capacity, Baytown/Deer Par'},
  {name:'Port Arthur Refinery Complex',lat:29.9000,lng:-93.9300,type:'infra',warheads:1,yieldKt:300,cat:'Motiva (607K bbl/day), Valero (435K bbl/day), TotalEnergies '},
  {name:'Texas City/Galveston Bay Refinery',lat:29.3800,lng:-94.9000,type:'infra',warheads:1,yieldKt:300,cat:'Marathon Galveston Bay, largest US refinery at 631K bbl/day'},
  {name:'Beaumont Refinery Complex',lat:30.0800,lng:-94.1000,type:'infra',warheads:1,yieldKt:300,cat:'ExxonMobil Beaumont (609K bbl/day) and other refineries'},
  {name:'Baton Rouge Refinery Complex',lat:30.4515,lng:-91.1871,type:'infra',warheads:1,yieldKt:300,cat:'ExxonMobil Baton Rouge, second largest US refinery'},
  {name:'Whiting Refinery (Chicago area)',lat:41.6792,lng:-87.4946,type:'infra',warheads:1,yieldKt:300,cat:'BP Whiting, largest inland refinery, 435K bbl/day'},
  {name:'Philadelphia/Delaware Valley Refineries',lat:39.8750,lng:-75.2400,type:'infra',warheads:1,yieldKt:300,cat:'PBF Energy, Monroe Energy, East Coast refining hub'},
  {name:'Los Angeles Basin Refineries',lat:33.8900,lng:-118.2400,type:'infra',warheads:4,yieldKt:800,cat:'Multiple refineries, Marathon, Valero, Phillips 66, Torrance'},
  {name:'San Francisco Bay Refineries',lat:38.0200,lng:-122.2300,type:'infra',warheads:1,yieldKt:300,cat:'Chevron Richmond, Marathon Martinez, PBF Martinez, Valero Be'},
  {name:'New York-Newark-Jersey City',lat:40.7128,lng:-74.0060,type:'city',warheads:6,yieldKt:800,cat:'Pop ~19.9M, largest US metro, financial capital'},
  {name:'Los Angeles-Long Beach-Anaheim',lat:34.0522,lng:-118.2437,type:'city',warheads:4,yieldKt:800,cat:'Pop ~13.2M, second largest metro'},
  {name:'Chicago-Naperville-Elgin',lat:41.8781,lng:-87.6298,type:'city',warheads:4,yieldKt:800,cat:'Pop ~9.5M, major transportation hub'},
  {name:'Dallas-Fort Worth-Arlington',lat:32.7767,lng:-96.7970,type:'city',warheads:4,yieldKt:800,cat:'Pop ~8.1M, major economic center'},
  {name:'Houston-Pasadena-The Woodlands',lat:29.7604,lng:-95.3698,type:'city',warheads:4,yieldKt:800,cat:'Pop ~7.5M, energy capital, major refining center'},
  {name:'Washington-Arlington-Alexandria',lat:38.9072,lng:-77.0369,type:'city',warheads:4,yieldKt:800,cat:'Pop ~6.4M, national capital, federal government center'},
  {name:'Philadelphia-Camden-Wilmington',lat:39.9526,lng:-75.1652,type:'city',warheads:4,yieldKt:800,cat:'Pop ~6.3M, major East Coast metro'},
  {name:'Miami-Fort Lauderdale-West Palm Beach',lat:25.7617,lng:-80.1918,type:'city',warheads:4,yieldKt:800,cat:'Pop ~6.2M, SOUTHCOM nearby'},
  {name:'Atlanta-Sandy Springs-Roswell',lat:33.7490,lng:-84.3880,type:'city',warheads:4,yieldKt:800,cat:'Pop ~6.3M, major transportation/logistics hub, CDC HQ'},
  {name:'Boston-Cambridge-Newton',lat:42.3601,lng:-71.0589,type:'city',warheads:3,yieldKt:800,cat:'Pop ~5.0M, major biotech/education center'},
  {name:'Phoenix-Mesa-Chandler',lat:33.4484,lng:-112.0740,type:'city',warheads:4,yieldKt:800,cat:'Pop ~5.1M, Luke AFB nearby'},
  {name:'San Francisco-Oakland-Berkeley',lat:37.7749,lng:-122.4194,type:'city',warheads:3,yieldKt:800,cat:'Pop ~4.7M, tech capital, major port'},
  {name:'Riverside-San Bernardino-Ontario',lat:33.9533,lng:-117.3962,type:'city',warheads:3,yieldKt:800,cat:'Pop ~4.7M, Inland Empire, March ARB'},
  {name:'Detroit-Warren-Dearborn',lat:42.3314,lng:-83.0458,type:'city',warheads:3,yieldKt:800,cat:'Pop ~4.3M, major manufacturing/auto center'},
  {name:'Seattle-Tacoma-Bellevue',lat:47.6062,lng:-122.3321,type:'city',warheads:3,yieldKt:800,cat:'Pop ~4.1M, Boeing, major tech hub, near Bangor SSBN base'},
  {name:'Minneapolis-St. Paul-Bloomington',lat:44.9778,lng:-93.2650,type:'city',warheads:3,yieldKt:800,cat:'Pop ~3.7M, major Midwest metro'},
  {name:'San Diego-Chula Vista-Carlsbad',lat:32.7157,lng:-117.1611,type:'city',warheads:3,yieldKt:800,cat:'Pop ~3.3M, major military complex, Naval Base San Diego'},
  {name:'Tampa-St. Petersburg-Clearwater',lat:27.9506,lng:-82.4572,type:'city',warheads:3,yieldKt:800,cat:'Pop ~3.3M, MacDill AFB/CENTCOM/SOCOM'},
  {name:'Denver-Aurora-Lakewood',lat:39.7392,lng:-104.9903,type:'city',warheads:3,yieldKt:800,cat:'Pop ~3.0M, near Buckley SFB, Schriever SFB, Cheyenne Mountai'},
  {name:'St. Louis, MO-IL',lat:38.6270,lng:-90.1994,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.8M, major river/transportation hub'},
  {name:'Baltimore-Columbia-Towson',lat:39.2904,lng:-76.6122,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.8M, NSA/Fort Meade, major port'},
  {name:'Orlando-Kissimmee-Sanford',lat:28.5383,lng:-81.3792,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.8M'},
  {name:'Charlotte-Concord-Gastonia',lat:35.2271,lng:-80.8431,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.8M, major banking center'},
  {name:'San Antonio-New Braunfels',lat:29.4241,lng:-98.4936,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.7M, Lackland AFB, Fort Sam Houston, JBSA'},
  {name:'Portland-Vancouver-Hillsboro',lat:45.5152,lng:-122.6784,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.5M, major West Coast metro'},
  {name:'Sacramento-Roseville-Folsom',lat:38.5816,lng:-121.4944,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.4M, state capital, Beale AFB nearby'},
  {name:'Pittsburgh',lat:40.4406,lng:-79.9959,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.4M, major industrial center'},
  {name:'Austin-Round Rock-Georgetown',lat:30.2672,lng:-97.7431,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.4M, fast-growing tech hub'},
  {name:'Las Vegas-Henderson-North Las Vegas',lat:36.1699,lng:-115.1398,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.3M, Nellis AFB, Creech AFB, NNSS nearby'},
  {name:'Cincinnati, OH-KY-IN',lat:39.1031,lng:-84.5120,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.3M'},
  {name:'Kansas City, MO-KS',lat:39.0997,lng:-94.5786,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.2M, KC National Security Campus'},
  {name:'Columbus, OH',lat:39.9612,lng:-82.9988,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.2M, Defense Supply Center Columbus'},
  {name:'Indianapolis-Carmel-Anderson',lat:39.7684,lng:-86.1581,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.1M'},
  {name:'Cleveland-Elyria',lat:41.4993,lng:-81.6944,type:'city',warheads:3,yieldKt:800,cat:'Pop ~2.1M, NASA Glenn Research Center'},
  {name:'San Jose-Sunnyvale-Santa Clara',lat:37.3382,lng:-121.8863,type:'city',warheads:2,yieldKt:800,cat:'Pop ~2.0M, Silicon Valley, major tech/defense industry'},
  {name:'Nashville-Davidson-Murfreesboro-Franklin',lat:36.1627,lng:-86.7816,type:'city',warheads:2,yieldKt:800,cat:'Pop ~2.0M'},
  {name:'Virginia Beach-Norfolk-Newport News',lat:36.8529,lng:-75.9780,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.8M, Naval Station Norfolk, Langley AFB, shipbuilding'},
  {name:'Raleigh-Cary',lat:35.7796,lng:-78.6382,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.5M, Research Triangle'},
  {name:'Milwaukee-Waukesha',lat:43.0389,lng:-87.9065,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.6M'},
  {name:'Jacksonville, FL',lat:30.3322,lng:-81.6557,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.7M, Naval Station Mayport'},
  {name:'Oklahoma City',lat:35.4676,lng:-97.5164,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.5M, Tinker AFB'},
  {name:'Memphis, TN-MS-AR',lat:35.1495,lng:-90.0490,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.3M, FedEx hub, major logistics'},
  {name:'Richmond, VA',lat:37.5407,lng:-77.4360,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.3M, Defense Supply Center Richmond'},
  {name:'Louisville/Jefferson County, KY-IN',lat:38.2527,lng:-85.7585,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.3M, Fort Knox nearby'},
  {name:'New Orleans-Metairie',lat:29.9511,lng:-90.0715,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.3M, major port, Naval Air Station JRB'},
  {name:'Salt Lake City, UT',lat:40.7608,lng:-111.8910,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.3M, Hill AFB, Tooele Army Depot'},
  {name:'Hartford-East Hartford-Middletown',lat:41.7658,lng:-72.6734,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.2M, Pratt & Whitney (jet engines), submarine parts ma'},
  {name:'Buffalo-Cheektowaga',lat:42.8864,lng:-78.8784,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.1M'},
  {name:'Birmingham-Hoover, AL',lat:33.5186,lng:-86.8104,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.1M'},
  {name:'Rochester, NY',lat:43.1566,lng:-77.6088,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.1M'},
  {name:'Grand Rapids-Kentwood, MI',lat:42.9634,lng:-85.6681,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.1M'},
  {name:'Tucson, AZ',lat:32.2226,lng:-110.9747,type:'city',warheads:2,yieldKt:800,cat:'Pop ~1.1M, Davis-Monthan AFB, AMARG boneyard'},
  {name:'Tulsa, OK',lat:36.1540,lng:-95.9928,type:'city',warheads:1,yieldKt:300,cat:'Pop ~1.0M'},
  {name:'Fresno, CA',lat:36.7378,lng:-119.7871,type:'city',warheads:1,yieldKt:300,cat:'Pop ~1.0M'},
  {name:'Urban Honolulu, HI',lat:21.3069,lng:-157.8583,type:'city',warheads:1,yieldKt:300,cat:'Pop ~1.0M, JBPHH, Indo-Pacific Command'},
  {name:'Bridgeport-Stamford-Norwalk, CT',lat:41.1865,lng:-73.1952,type:'city',warheads:1,yieldKt:300,cat:'Pop ~950K'},
  {name:'Worcester, MA-CT',lat:42.2626,lng:-71.8023,type:'city',warheads:1,yieldKt:300,cat:'Pop ~950K'},
  {name:'Omaha-Council Bluffs, NE-IA',lat:41.2565,lng:-95.9345,type:'c2',warheads:2,yieldKt:455,cat:'Pop ~970K, Offutt AFB/STRATCOM'},
  {name:'Albuquerque, NM',lat:35.0844,lng:-106.6504,type:'city',warheads:1,yieldKt:300,cat:'Pop ~920K, Kirtland AFB, Sandia Labs, major nuclear weapons '},
  {name:'New Haven-Milford, CT',lat:41.3083,lng:-72.9279,type:'city',warheads:1,yieldKt:300,cat:'Pop ~870K, Electric Boat submarine manufacturing (Groton nea'},
  {name:'Albany-Schenectady-Troy, NY',lat:42.6526,lng:-73.7562,type:'city',warheads:1,yieldKt:300,cat:'Pop ~890K'},
  {name:'Bakersfield, CA',lat:35.3733,lng:-119.0187,type:'city',warheads:1,yieldKt:300,cat:'Pop ~910K, Edwards AFB nearby'},
  {name:'Knoxville, TN',lat:35.9606,lng:-83.9207,type:'city',warheads:1,yieldKt:300,cat:'Pop ~900K, Y-12/ORNL 15 miles away'},
  {name:'McAllen-Edinburg-Mission, TX',lat:26.2034,lng:-98.2300,type:'city',warheads:1,yieldKt:300,cat:'Pop ~880K'},
  {name:'Boise City, ID',lat:43.6150,lng:-116.2023,type:'city',warheads:1,yieldKt:300,cat:'Pop ~830K, Mountain Home AFB nearby'},
  {name:'El Paso, TX',lat:31.7619,lng:-106.4850,type:'city',warheads:1,yieldKt:300,cat:'Pop ~870K, Fort Bliss, White Sands nearby'},
  {name:'Oxnard-Thousand Oaks-Ventura, CA',lat:34.1975,lng:-119.1771,type:'city',warheads:1,yieldKt:300,cat:'Pop ~840K, Naval Base Ventura County/Point Mugu'},
  {name:'Greenville-Anderson, SC',lat:34.8526,lng:-82.3940,type:'city',warheads:1,yieldKt:300,cat:'Pop ~950K'},
  {name:'North Port-Sarasota-Bradenton, FL',lat:27.3364,lng:-82.5307,type:'city',warheads:1,yieldKt:300,cat:'Pop ~890K'},
  {name:'Columbia, SC',lat:34.0007,lng:-81.0348,type:'city',warheads:1,yieldKt:300,cat:'Pop ~870K, Fort Jackson, Shaw AFB nearby'},
  {name:'Provo-Orem, UT',lat:40.2338,lng:-111.6585,type:'city',warheads:1,yieldKt:300,cat:'Pop ~700K'},
  {name:'Colorado Springs, CO',lat:38.8339,lng:-104.8214,type:'city',warheads:1,yieldKt:300,cat:'Pop ~780K, NORAD, Peterson SFB, Schriever SFB, Fort Carson'},
  {name:'Dayton-Kettering, OH',lat:39.7589,lng:-84.1916,type:'city',warheads:1,yieldKt:300,cat:'Pop ~810K, Wright-Patterson AFB'},
  {name:'Greensboro-High Point, NC',lat:36.0726,lng:-79.7920,type:'city',warheads:1,yieldKt:300,cat:'Pop ~780K'},
  {name:'Des Moines-West Des Moines, IA',lat:41.5868,lng:-93.6250,type:'city',warheads:1,yieldKt:300,cat:'Pop ~710K'},
  {name:'Little Rock-North Little Rock-Conway, AR',lat:34.7465,lng:-92.2896,type:'city',warheads:1,yieldKt:300,cat:'Pop ~750K, Little Rock AFB'},
  {name:'Cape Coral-Fort Myers, FL',lat:26.6449,lng:-81.8613,type:'city',warheads:1,yieldKt:300,cat:'Pop ~840K'},
  {name:'Charleston-North Charleston, SC',lat:32.7765,lng:-79.9311,type:'city',warheads:1,yieldKt:300,cat:'Pop ~850K, Joint Base Charleston'},
  {name:'Ogden-Clearfield, UT',lat:41.2230,lng:-111.9738,type:'city',warheads:1,yieldKt:300,cat:'Pop ~720K, Hill AFB'},
  {name:'Palm Bay-Melbourne-Titusville, FL',lat:28.0345,lng:-80.5887,type:'city',warheads:1,yieldKt:300,cat:'Pop ~640K, Patrick SFB, Cape Canaveral'},
  {name:'Deltona-Daytona Beach-Ormond Beach, FL',lat:29.2108,lng:-81.0229,type:'city',warheads:1,yieldKt:300,cat:'Pop ~700K'},
  {name:'Wichita, KS',lat:37.6872,lng:-97.3301,type:'city',warheads:1,yieldKt:300,cat:'Pop ~650K, McConnell AFB, aircraft manufacturing'},
  {name:'Madison, WI',lat:43.0731,lng:-89.4012,type:'city',warheads:1,yieldKt:300,cat:'Pop ~680K'},
  {name:'Lakeland-Winter Haven, FL',lat:28.0395,lng:-81.9498,type:'city',warheads:1,yieldKt:300,cat:'Pop ~760K'},
  {name:'Harrisburg-Carlisle, PA',lat:40.2732,lng:-76.8867,type:'city',warheads:1,yieldKt:300,cat:'Pop ~610K'},
  {name:'Chattanooga, TN-GA',lat:35.0456,lng:-85.3097,type:'city',warheads:1,yieldKt:300,cat:'Pop ~580K'},
  {name:'Spokane-Spokane Valley, WA',lat:47.6588,lng:-117.4260,type:'city',warheads:1,yieldKt:300,cat:'Pop ~600K, Fairchild AFB'},
  {name:'Durham-Chapel Hill, NC',lat:35.9940,lng:-78.8986,type:'city',warheads:1,yieldKt:300,cat:'Pop ~590K, Research Triangle'},
  {name:'Stockton, CA',lat:37.9577,lng:-121.2908,type:'city',warheads:1,yieldKt:300,cat:'Pop ~780K'},
  {name:'Fayetteville-Springdale-Rogers, AR',lat:36.0626,lng:-94.1574,type:'city',warheads:1,yieldKt:300,cat:'Pop ~580K'},
  {name:'Scranton-Wilkes-Barre, PA',lat:41.4090,lng:-75.6624,type:'city',warheads:1,yieldKt:300,cat:'Pop ~570K, Tobyhanna Army Depot'},
  {name:'Akron, OH',lat:41.0814,lng:-81.5190,type:'city',warheads:1,yieldKt:300,cat:'Pop ~700K'},
  {name:'Reno, NV',lat:39.5296,lng:-119.8138,type:'city',warheads:1,yieldKt:300,cat:'Pop ~510K'},
  {name:'Lexington-Fayette, KY',lat:38.0406,lng:-84.5037,type:'city',warheads:1,yieldKt:300,cat:'Pop ~530K, Bluegrass Army Depot'},
  {name:'Pensacola-Ferry Pass-Brent, FL',lat:30.4213,lng:-87.2169,type:'city',warheads:1,yieldKt:300,cat:'Pop ~520K, NAS Pensacola'},
  {name:'Modesto, CA',lat:37.6391,lng:-120.9969,type:'city',warheads:1,yieldKt:300,cat:'Pop ~570K'},
  {name:'Port St. Lucie, FL',lat:27.2730,lng:-80.3582,type:'city',warheads:1,yieldKt:300,cat:'Pop ~520K'},
  {name:'Winston-Salem, NC',lat:36.0999,lng:-80.2442,type:'city',warheads:1,yieldKt:300,cat:'Pop ~680K'},
  {name:'Augusta-Richmond County, GA-SC',lat:33.4735,lng:-81.9748,type:'city',warheads:1,yieldKt:300,cat:'Pop ~620K, Fort Eisenhower (Army Cyber), near Savannah River'},
  {name:'Huntsville, AL',lat:34.7304,lng:-86.5861,type:'city',warheads:1,yieldKt:300,cat:'Pop ~530K, Redstone Arsenal, NASA Marshall, missile defense'},
  {name:'Lancaster, PA',lat:40.0379,lng:-76.3055,type:'city',warheads:1,yieldKt:300,cat:'Pop ~560K'},
];

// Russian targets (103 targets)
NM.WW3_TARGETS_RU = [
  {name:'Kozelsk - 28th Guards Missile Division',lat:53.9433,lng:35.8194,type:'icbm',warheads:2,yieldKt:455,cat:'RS-24 Yars silo field, 3 regiments (~30 silos), 240km SW of '},
  {name:'Tatishchevo - 60th Missile Division',lat:51.8792,lng:45.3368,type:'icbm',warheads:2,yieldKt:455,cat:'60 SS-27 Mod 1 (Topol-M) silo-based ICBMs, 6 regiments, Sara'},
  {name:'Tatishchevo - 104th Regiment',lat:51.6108,lng:45.4970,type:'icbm',warheads:2,yieldKt:455,cat:'Silo regiment of 60th Missile Division'},
  {name:'Tatishchevo - 122nd Regiment',lat:52.1589,lng:45.6404,type:'icbm',warheads:2,yieldKt:455,cat:'Silo regiment of 60th Missile Division'},
  {name:'Tatishchevo - 165th Regiment',lat:51.8062,lng:45.6550,type:'icbm',warheads:2,yieldKt:455,cat:'Silo regiment of 60th Missile Division'},
  {name:'Tatishchevo - 322nd Regiment',lat:52.0449,lng:45.4458,type:'icbm',warheads:2,yieldKt:455,cat:'Silo regiment of 60th Missile Division'},
  {name:'Tatishchevo - 626th Regiment',lat:51.7146,lng:45.2278,type:'icbm',warheads:2,yieldKt:455,cat:'Silo regiment of 60th Missile Division'},
  {name:'Dombarovsky - 13th Missile Division',lat:51.0489,lng:59.8533,type:'icbm',warheads:2,yieldKt:455,cat:'SS-18/Avangard HGV silos, Orenburg Oblast. Up to 64 silos at'},
  {name:'Uzhur - 62nd Missile Division (229th Regiment)',lat:55.2453,lng:89.9194,type:'icbm',warheads:2,yieldKt:455,cat:'SS-18 silos being upgraded to RS-28 Sarmat, Krasnoyarsk Krai'},
  {name:'Uzhur - 269th Regiment',lat:55.2077,lng:90.2526,type:'icbm',warheads:2,yieldKt:455,cat:'Silo regiment of 62nd Missile Division'},
  {name:'Uzhur - 302nd Regiment',lat:55.1147,lng:89.6311,type:'icbm',warheads:2,yieldKt:455,cat:'Silo regiment of 62nd Missile Division'},
  {name:'Uzhur - 735th Regiment',lat:55.2720,lng:89.5783,type:'icbm',warheads:2,yieldKt:455,cat:'Silo regiment of 62nd Missile Division'},
  {name:'Kartaly (decommissioned)',lat:53.9667,lng:57.8333,type:'icbm',warheads:2,yieldKt:455,cat:'Former SS-18 deployment site, Chelyabinsk Oblast. Division l'},
  {name:'Aleysk (decommissioned)',lat:52.5000,lng:82.7500,type:'icbm',warheads:2,yieldKt:455,cat:'Former 41st Guards Missile Division, 30 SS-18 silos destroye'},
  {name:'Teykovo - 54th Guards Missile Division (235th Regiment)',lat:56.7041,lng:40.4403,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile SS-27 Mod 1/Mod 2 (Yars), Ivanovo Oblast'},
  {name:'Teykovo - 285th Regiment',lat:56.8091,lng:40.1710,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 54th Guards Missile Division'},
  {name:'Teykovo - 321st Regiment',lat:56.9324,lng:40.5440,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 54th Guards Missile Division'},
  {name:'Teykovo - 773rd Regiment',lat:56.9167,lng:40.3087,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 54th Guards Missile Division'},
  {name:'Yoshkar-Ola - 14th Missile Division (290th Regiment)',lat:56.8328,lng:48.2370,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile RS-24 Yars, Mari El Republic'},
  {name:'Yoshkar-Ola - 697th Regiment',lat:56.5601,lng:48.2144,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 14th Missile Division'},
  {name:'Yoshkar-Ola - 779th Regiment',lat:56.5821,lng:48.1550,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 14th Missile Division'},
  {name:'Novosibirsk - 39th Guards Missile Division (382nd Regiment)',lat:55.3175,lng:83.1684,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile RS-24 Yars, Novosibirsk Oblast (Paskino)'},
  {name:'Novosibirsk - 357th Regiment',lat:55.3255,lng:82.9422,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 39th Guards Missile Division'},
  {name:'Nizhny Tagil - 42nd Missile Division (308th Regiment)',lat:58.2298,lng:60.6773,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile RS-24 Yars, Sverdlovsk Oblast'},
  {name:'Nizhny Tagil - 433rd Regiment',lat:58.1015,lng:60.3592,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 42nd Missile Division'},
  {name:'Nizhny Tagil - 804th Regiment',lat:58.1372,lng:60.5366,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 42nd Missile Division'},
  {name:'Irkutsk - 29th Guards Missile Division (92nd Regiment)',lat:52.5085,lng:104.3933,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile RS-24 Yars, Irkutsk Oblast'},
  {name:'Irkutsk - 344th Regiment',lat:52.6694,lng:104.5199,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 29th Guards Missile Division'},
  {name:'Irkutsk - 586th Regiment',lat:52.5505,lng:104.1584,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 29th Guards Missile Division'},
  {name:'Barnaul - 35th Missile Division (479th Guards Regiment)',lat:53.7699,lng:83.9592,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile RS-24 Yars, Altai Krai (ZATO Sibirsky)'},
  {name:'Barnaul - 480th Regiment',lat:53.3059,lng:84.1462,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 35th Missile Division'},
  {name:'Barnaul - 867th Regiment',lat:53.2247,lng:84.6695,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 35th Missile Division'},
  {name:'Barnaul - 307th Regiment',lat:53.3131,lng:84.5075,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 35th Missile Division'},
  {name:'Vypolzovo/Bologoye - 7th Guards Missile Division (41st Regiment)',lat:57.8631,lng:33.6517,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile RS-24 Yars, Tver Oblast. Westernmost RVSN divisi'},
  {name:'Vypolzovo/Bologoye - 510th Regiment',lat:57.7883,lng:33.8654,type:'icbm',warheads:2,yieldKt:455,cat:'Road-mobile regiment, 7th Guards Missile Division'},
  {name:'Gadzhiyevo (Yagelnaya Bay) - Northern Fleet SSBN Base',lat:69.2614,lng:33.3322,type:'sub',warheads:3,yieldKt:455,cat:'Home port for Borei and Delta-IV class SSBNs. Kola Peninsula'},
  {name:'Vilyuchinsk (Rybachiy) - Pacific Fleet SSBN Base',lat:52.9200,lng:158.4900,type:'sub',warheads:3,yieldKt:455,cat:'Borei-class SSBNs, Kamchatka Peninsula. Russia\'s largest su'},
  {name:'Severodvinsk - Sevmash Shipyard',lat:64.5817,lng:39.8307,type:'sub',warheads:3,yieldKt:455,cat:'Russia\'s only nuclear submarine construction facility. 30,0'},
  {name:'Engels-2 Air Base',lat:51.4753,lng:46.2063,type:'bomber',warheads:2,yieldKt:455,cat:'Russia\'s sole Tu-160 base + Tu-95MS. 22nd Guards Heavy Bomb'},
  {name:'Ukrainka Air Base',lat:51.1700,lng:128.4450,type:'bomber',warheads:2,yieldKt:455,cat:'Tu-95MS strategic bombers, 326th Heavy Bomber Division, Amur'},
  {name:'Moscow Kremlin - Presidential Command',lat:55.7520,lng:37.6175,type:'c2',warheads:2,yieldKt:455,cat:'Russian President\'s official residence and office, supreme '},
  {name:'Russian General Staff HQ - Znamenka Street',lat:55.7506,lng:37.6028,type:'c2',warheads:2,yieldKt:455,cat:'General Staff of Russian Armed Forces, Arbat District, Mosco'},
  {name:'Vlasikha - Strategic Rocket Forces HQ',lat:55.6869,lng:37.1833,type:'c2',warheads:2,yieldKt:455,cat:'RVSN headquarters, closed town west of Moscow. 12-tier under'},
  {name:'Kosvinsky Kamen - Alternate Strategic Command Post',lat:59.5168,lng:59.0611,type:'c2',warheads:2,yieldKt:455,cat:'Deep underground bunker under 300m of granite. Perimeter/Dea'},
  {name:'Mount Yamantau - Nuclear War Bunker',lat:54.2553,lng:58.1019,type:'c2',warheads:2,yieldKt:455,cat:'Massive underground facility, 1640m mountain. Leadership rel'},
  {name:'National Defense Management Center - Moscow',lat:55.7430,lng:37.5850,type:'c2',warheads:2,yieldKt:455,cat:'Founded 2014, central C2 node for Russian Armed Forces, Frun'},
  {name:'Sarov (Arzamas-16) - VNIIEF',lat:54.8167,lng:43.3667,type:'nuclear',warheads:1,yieldKt:300,cat:'Russia\'s primary nuclear warhead design institute + Avangar'},
  {name:'Snezhinsk (Chelyabinsk-70) - VNIITF',lat:56.0833,lng:60.7333,type:'nuclear',warheads:1,yieldKt:300,cat:'Second nuclear warhead design center, Chelyabinsk Oblast'},
  {name:'Zheleznogorsk (Krasnoyarsk-26) - Mining & Chemical Combine',lat:56.2511,lng:93.5314,type:'nuclear',warheads:1,yieldKt:300,cat:'Underground plutonium production complex (200-250m deep), la'},
  {name:'Seversk (Tomsk-7) - Siberian Chemical Combine',lat:56.6167,lng:84.8333,type:'nuclear',warheads:1,yieldKt:300,cat:'Russia\'s largest plutonium production & fissile material co'},
  {name:'Ozersk (Chelyabinsk-65) - Mayak Production Association',lat:55.7500,lng:60.7500,type:'nuclear',warheads:1,yieldKt:300,cat:'Plutonium production, reprocessing, weapons-grade material s'},
  {name:'Novouralsk (Sverdlovsk-44) - Uranium Enrichment',lat:57.2500,lng:60.0833,type:'nuclear',warheads:1,yieldKt:300,cat:'Uranium enrichment plant, Sverdlovsk Oblast'},
  {name:'Lesnoy (Sverdlovsk-45) - Warhead Assembly',lat:58.6333,lng:59.7833,type:'nuclear',warheads:1,yieldKt:300,cat:'Nuclear warhead serial production plant, Sverdlovsk Oblast'},
  {name:'Trekhgornyy (Zlatoust-36) - Instrument Making Plant',lat:54.8167,lng:58.4500,type:'nuclear',warheads:1,yieldKt:300,cat:'Nuclear warhead component manufacturing, Chelyabinsk Oblast'},
  {name:'Zarechnyy (Penza-19) - Start Production Association',lat:53.2000,lng:45.1667,type:'nuclear',warheads:1,yieldKt:300,cat:'Nuclear warhead final assembly/disassembly, Penza Oblast'},
  {name:'Zelenogorsk (Krasnoyarsk-45) - Electrochemical Plant',lat:56.1167,lng:94.5833,type:'nuclear',warheads:1,yieldKt:300,cat:'Uranium enrichment facility, Krasnoyarsk Krai'},
  {name:'Severomorsk - Northern Fleet HQ',lat:69.0667,lng:33.4167,type:'military',warheads:1,yieldKt:300,cat:'Northern Fleet headquarters, Kola Peninsula, Barents Sea. Ru'},
  {name:'Vladivostok - Pacific Fleet HQ',lat:43.0778,lng:131.9222,type:'military',warheads:1,yieldKt:300,cat:'Pacific Fleet headquarters, Ulysses Bay, Primorsky Krai'},
  {name:'Baltiysk - Baltic Fleet Main Base',lat:54.6347,lng:19.8809,type:'military',warheads:1,yieldKt:300,cat:'Baltic Fleet principal seaward base, Kaliningrad Oblast'},
  {name:'Kaliningrad - Baltic Fleet HQ',lat:54.7208,lng:20.4950,type:'military',warheads:1,yieldKt:300,cat:'Baltic Fleet headquarters city, Kaliningrad Oblast exclave'},
  {name:'Sevastopol - Black Sea Fleet HQ',lat:44.6167,lng:33.5167,type:'military',warheads:1,yieldKt:300,cat:'Black Sea Fleet headquarters, Crimea (annexed 2014)'},
  {name:'Polyarny - Northern Fleet Submarine Base',lat:69.2000,lng:33.4833,type:'military',warheads:1,yieldKt:300,cat:'Attack submarine base, Kola Peninsula'},
  {name:'Vidyayevo - Northern Fleet Submarine Base',lat:69.3167,lng:32.7500,type:'military',warheads:1,yieldKt:300,cat:'Attack submarine base (Ura Bay), Kola Peninsula'},
  {name:'Olenya Bay - Northern Fleet Air Base',lat:68.1500,lng:33.4333,type:'military',warheads:1,yieldKt:300,cat:'Tu-22M3 Backfire bomber base, Kola Peninsula'},
  {name:'Moscow',lat:55.7512,lng:37.6184,type:'c2',warheads:2,yieldKt:455,cat:'Capital, 13M+ pop. Political/economic center, national comma'},
  {name:'Saint Petersburg',lat:59.9375,lng:30.3086,type:'city',warheads:4,yieldKt:800,cat:'5.6M pop. Cultural capital, major naval/military industry, B'},
  {name:'Novosibirsk',lat:55.0188,lng:82.9340,type:'city',warheads:2,yieldKt:800,cat:'1.6M pop. Largest Siberian city, major rail/industrial hub'},
  {name:'Yekaterinburg',lat:56.8333,lng:60.5833,type:'city',warheads:2,yieldKt:800,cat:'1.5M pop. Urals industrial center, military-industrial compl'},
  {name:'Kazan',lat:55.7964,lng:49.1089,type:'city',warheads:2,yieldKt:800,cat:'1.3M pop. Tatarstan capital, aerospace/defense industry'},
  {name:'Nizhny Novgorod',lat:56.3275,lng:44.0007,type:'city',warheads:2,yieldKt:800,cat:'1.3M pop. Major defense industry center, Volga region'},
  {name:'Chelyabinsk',lat:55.1644,lng:61.4368,type:'city',warheads:2,yieldKt:800,cat:'1.2M pop. Urals heavy industry, tank/vehicle manufacturing'},
  {name:'Samara',lat:53.2415,lng:50.2212,type:'city',warheads:2,yieldKt:800,cat:'1.2M pop. Aerospace center (Progress rocket factory), Volga '},
  {name:'Omsk',lat:54.9833,lng:73.3667,type:'city',warheads:2,yieldKt:800,cat:'1.1M pop. Major Siberian industrial city, oil refining'},
  {name:'Rostov-on-Don',lat:47.2333,lng:39.7000,type:'city',warheads:2,yieldKt:800,cat:'1.1M pop. Southern Military District HQ, major transport hub'},
  {name:'Ufa',lat:54.7333,lng:56.0000,type:'city',warheads:2,yieldKt:800,cat:'1.1M pop. Bashkortostan capital, oil/petrochemical industry'},
  {name:'Krasnoyarsk',lat:56.0153,lng:92.8932,type:'city',warheads:2,yieldKt:800,cat:'1.1M pop. Major Siberian city, aluminum/defense industry'},
  {name:'Voronezh',lat:51.6720,lng:39.1843,type:'city',warheads:1,yieldKt:300,cat:'1.0M pop. Aerospace/electronics industry, Central Russia'},
  {name:'Perm',lat:58.0105,lng:56.2502,type:'city',warheads:1,yieldKt:300,cat:'1.0M pop. Urals industrial center, rocket engine manufacturi'},
  {name:'Volgograd',lat:48.7138,lng:44.4976,type:'city',warheads:1,yieldKt:300,cat:'1.0M pop. Major Volga city, heavy industry'},
  {name:'Krasnodar',lat:45.0448,lng:38.9760,type:'city',warheads:1,yieldKt:300,cat:'950K+ pop. Southern Russia economic center'},
  {name:'Saratov',lat:51.5406,lng:46.0086,type:'city',warheads:1,yieldKt:300,cat:'900K+ pop. Volga region, near Engels-2 bomber base'},
  {name:'Tyumen',lat:57.1522,lng:65.5272,type:'city',warheads:1,yieldKt:300,cat:'850K+ pop. Oil industry capital of Western Siberia'},
  {name:'Tolyatti',lat:53.5303,lng:49.3461,type:'city',warheads:1,yieldKt:300,cat:'700K+ pop. Volga automotive industry center (AvtoVAZ/Lada)'},
  {name:'Izhevsk',lat:56.8498,lng:53.2045,type:'city',warheads:1,yieldKt:300,cat:'650K+ pop. Udmurt Republic, Kalashnikov weapons manufacturin'},
  {name:'Barnaul',lat:53.3606,lng:83.7636,type:'city',warheads:1,yieldKt:300,cat:'630K+ pop. Altai Krai capital, near 35th Missile Division'},
  {name:'Ulyanovsk',lat:54.3300,lng:48.3900,type:'city',warheads:1,yieldKt:300,cat:'630K+ pop. Aviastar aircraft factory (Il-76, An-124)'},
  {name:'Irkutsk',lat:52.2978,lng:104.2964,type:'city',warheads:1,yieldKt:300,cat:'617K+ pop. Major Siberian city, near 29th Guards Missile Div'},
  {name:'Khabarovsk',lat:48.4803,lng:135.0882,type:'city',warheads:1,yieldKt:300,cat:'617K+ pop. Eastern Military District HQ, Far East major city'},
  {name:'Vladivostok',lat:43.1198,lng:131.8869,type:'city',warheads:1,yieldKt:300,cat:'604K+ pop. Pacific Fleet HQ, major Far East port'},
  {name:'Yaroslavl',lat:57.6299,lng:39.8737,type:'city',warheads:1,yieldKt:300,cat:'577K+ pop. Central Russia, diesel engine manufacturing'},
  {name:'Makhachkala',lat:42.9833,lng:47.5000,type:'city',warheads:1,yieldKt:300,cat:'600K+ pop. Dagestan capital, Caspian Sea port'},
  {name:'Kemerovo',lat:55.3450,lng:86.0623,type:'city',warheads:1,yieldKt:300,cat:'557K+ pop. Kuzbass coal mining region center'},
  {name:'Tomsk',lat:56.5003,lng:84.9820,type:'city',warheads:1,yieldKt:300,cat:'556K+ pop. Major Siberian university/science city, near Seve'},
  {name:'Orenburg',lat:51.7727,lng:55.0988,type:'city',warheads:1,yieldKt:300,cat:'550K+ pop. Southern Urals, 31st Rocket Army HQ city'},
  {name:'Naberezhnye Chelny',lat:55.7254,lng:52.4112,type:'city',warheads:1,yieldKt:300,cat:'548K+ pop. Tatarstan, KAMAZ truck manufacturing'},
  {name:'Novokuznetsk',lat:53.7600,lng:87.1100,type:'city',warheads:1,yieldKt:300,cat:'540K+ pop. Kemerovo Oblast, steel/metallurgy center'},
  {name:'Ryazan',lat:54.6095,lng:39.7126,type:'city',warheads:1,yieldKt:300,cat:'520K+ pop. Central Russia, airborne forces training center'},
  {name:'Lipetsk',lat:52.6000,lng:39.5700,type:'city',warheads:1,yieldKt:300,cat:'510K+ pop. Steel industry, combat pilot training center'},
  {name:'Astrakhan',lat:46.3497,lng:48.0408,type:'city',warheads:1,yieldKt:300,cat:'502K+ pop. Caspian Flotilla base, Volga delta'},
  {name:'Kirov',lat:58.6000,lng:49.6600,type:'city',warheads:1,yieldKt:300,cat:'500K+ pop. Volga-Ural region, defense industry'},
  {name:'Penza',lat:53.2000,lng:45.0000,type:'nuclear',warheads:1,yieldKt:300,cat:'520K+ pop. Near Zarechnyy nuclear warhead assembly plant'},
  {name:'Cheboksary',lat:56.1300,lng:47.2500,type:'city',warheads:1,yieldKt:300,cat:'500K+ pop. Chuvash Republic capital, electronics industry'},
  {name:'Tula',lat:54.2000,lng:37.6200,type:'city',warheads:1,yieldKt:300,cat:'500K+ pop. Historic arms manufacturing center (Tula Arms Pla'},
];

// NATO Europe targets (74 targets)
NM.WW3_TARGETS_NATO = [
  {name:'Buchel Air Base',lat:50.1762,lng:7.0640,type:'nuclear',warheads:2,yieldKt:300,cat:'German Tornado wing, 10-15 B61-12 bombs. F-35A arriving 2027'},
  {name:'Kleine Brogel Air Base',lat:51.1682,lng:5.4690,type:'nuclear',warheads:2,yieldKt:300,cat:'Belgian 10th Tactical Wing F-16s, ~20 B61 nuclear bombs.'},
  {name:'Volkel Air Base',lat:51.6564,lng:5.7086,type:'nuclear',warheads:2,yieldKt:300,cat:'Dutch F-35A squadrons (312 & 313), ~22 B61 bombs. 703rd MUNS'},
  {name:'Aviano Air Base',lat:46.0313,lng:12.5968,type:'nuclear',warheads:2,yieldKt:300,cat:'USAF 31st FW, 20-30 B61-12 bombs for US F-16C/D delivery.'},
  {name:'Ghedi Air Base',lat:45.4319,lng:10.2670,type:'nuclear',warheads:2,yieldKt:300,cat:'Italian PA-200 Tornados, 10-15 B61-12 bombs. F-35A transitio'},
  {name:'Incirlik Air Base',lat:37.0025,lng:35.4267,type:'nuclear',warheads:2,yieldKt:300,cat:'USAF/Turkish joint base, 20-30 B61-12 bombs. Strategic easte'},
  {name:'RAF Lakenheath',lat:52.4082,lng:0.5587,type:'nuclear',warheads:2,yieldKt:300,cat:'USAF 48th FW F-15E/F-35A. Nuclear mission reactivated, vault'},
  {name:'SHAPE (Supreme HQ Allied Powers Europe)',lat:50.5050,lng:3.9700,type:'c2',warheads:2,yieldKt:300,cat:'NATO\'s military HQ at Casteau near Mons. SACEUR commands al'},
  {name:'NATO HQ Brussels',lat:50.8724,lng:4.4199,type:'c2',warheads:2,yieldKt:300,cat:'NATO political headquarters, North Atlantic Council.'},
  {name:'JFC Brunssum',lat:50.9450,lng:5.9700,type:'c2',warheads:2,yieldKt:300,cat:'Allied Joint Force Command Brunssum. Operational-level HQ.'},
  {name:'JFC Naples (Lago Patria)',lat:40.9258,lng:14.0358,type:'c2',warheads:2,yieldKt:300,cat:'Allied Joint Force Command Naples. Southern flank operations'},
  {name:'MARCOM Northwood',lat:51.6130,lng:-0.4140,type:'c2',warheads:2,yieldKt:300,cat:'Allied Maritime Command. NATO\'s one-stop shop for maritime '},
  {name:'AIRCOM Ramstein',lat:49.4369,lng:7.6003,type:'c2',warheads:2,yieldKt:300,cat:'Allied Air Command. Prime air/space advisor to the Alliance.'},
  {name:'NATO Joint Warfare Centre Stavanger',lat:58.9700,lng:5.7331,type:'c2',warheads:2,yieldKt:300,cat:'JWC Jatta, subordinate to HQ SACT. Training and exercises.'},
  {name:'HMNB Clyde (Faslane)',lat:56.0609,lng:-4.8211,type:'nuclear',warheads:2,yieldKt:300,cat:'Home of UK Vanguard-class Trident SSBNs. Britain\'s continuo'},
  {name:'RNAD Coulport',lat:56.0500,lng:-4.8833,type:'nuclear',warheads:2,yieldKt:300,cat:'Trident warhead storage/loading facility. 16 hillside bunker'},
  {name:'AWE Aldermaston',lat:51.3688,lng:-1.1415,type:'nuclear',warheads:2,yieldKt:300,cat:'Nuclear warhead research, design & manufacturing. 750-acre s'},
  {name:'AWE Burghfield',lat:51.4068,lng:-1.0213,type:'nuclear',warheads:2,yieldKt:300,cat:'Warhead assembly, maintenance & decommissioning. 225-acre si'},
  {name:'HMNB Devonport',lat:50.3830,lng:-4.1830,type:'nuclear',warheads:2,yieldKt:300,cat:'Largest naval base in Western Europe. Sole UK nuclear sub re'},
  {name:'Ile Longue Submarine Base',lat:48.3064,lng:-4.5067,type:'nuclear',warheads:2,yieldKt:300,cat:'Base of 4 Triomphant-class SSBNs (FOST). France\'s sea-based'},
  {name:'Saint-Dizier Air Base (BA 113)',lat:48.6360,lng:4.8994,type:'nuclear',warheads:2,yieldKt:300,cat:'Nuclear-capable Rafale BF3 squadrons (Gascogne & La Fayette)'},
  {name:'Istres-Le Tube Air Base (BA 125)',lat:43.5213,lng:4.9383,type:'nuclear',warheads:2,yieldKt:300,cat:'Large multi-role base. Nuclear weapon dispersal/storage site'},
  {name:'CEA Valduc',lat:47.5822,lng:4.8704,type:'nuclear',warheads:2,yieldKt:300,cat:'Nuclear warhead production, maintenance, storage & dismantle'},
  {name:'CEA Bruyeres-le-Chatel (DAM-DIF)',lat:48.5887,lng:2.1899,type:'nuclear',warheads:2,yieldKt:300,cat:'Warhead design & simulation. Houses Tera 1000 supercomputer,'},
  {name:'CEA CESTA (Le Barp)',lat:44.6655,lng:-0.7961,type:'nuclear',warheads:2,yieldKt:300,cat:'Nuclear weapon/reentry vehicle design. Hosts Laser Megajoule'},
  {name:'Toulon Naval Base',lat:43.1183,lng:5.9098,type:'nuclear',warheads:2,yieldKt:300,cat:'Principal French Navy base. Charles de Gaulle carrier, nucle'},
  {name:'Arsenal de Brest',lat:48.3867,lng:-4.4967,type:'nuclear',warheads:2,yieldKt:300,cat:'Major French naval facility near Ile Longue. Submarine suppo'},
  {name:'Ramstein Air Base',lat:49.4397,lng:7.6014,type:'military',warheads:1,yieldKt:300,cat:'Largest US air base in Europe. USAFE-AFAFRICA HQ. 54,000 per'},
  {name:'Spangdahlem Air Base',lat:49.9833,lng:6.6833,type:'military',warheads:1,yieldKt:300,cat:'USAF 52nd FW. SEAD missions, nuclear security ops across 4 c'},
  {name:'RAF Mildenhall',lat:52.3613,lng:0.4864,type:'military',warheads:1,yieldKt:300,cat:'USAF 100th ARW aerial refueling. Strategic airlift hub.'},
  {name:'RAF Fairford',lat:51.6822,lng:-1.7900,type:'military',warheads:1,yieldKt:300,cat:'USAF forward operating base. B-52/B-2 bomber deployments.'},
  {name:'Lajes Field (Azores)',lat:38.7570,lng:-27.0877,type:'military',warheads:1,yieldKt:300,cat:'Mid-Atlantic staging base. Strategic between North America a'},
  {name:'NAS Sigonella',lat:37.4010,lng:14.9200,type:'military',warheads:1,yieldKt:300,cat:'Hub of the Med. Global Hawk UAVs, maritime patrol. US 6th Fl'},
  {name:'Naval Station Rota',lat:36.6208,lng:-6.3316,type:'military',warheads:1,yieldKt:300,cat:'Largest US military community in Spain. Aegis BMD destroyers'},
  {name:'Souda Bay NATO Base',lat:35.4867,lng:24.0831,type:'military',warheads:1,yieldKt:300,cat:'Largest NATO naval base in eastern Mediterranean. Greek/US/N'},
  {name:'Naval Base Kiel',lat:54.3569,lng:10.1439,type:'military',warheads:1,yieldKt:300,cat:'German Navy base. Baltic Sea operations.'},
  {name:'Rygge Air Station',lat:59.3783,lng:10.7853,type:'military',warheads:1,yieldKt:300,cat:'Royal Norwegian Air Force. F-35A operations.'},
  {name:'Amari Air Base',lat:59.2603,lng:24.2086,type:'military',warheads:1,yieldKt:300,cat:'Estonian AF base. NATO Baltic Air Policing.'},
  {name:'Siauliai Air Base',lat:55.8939,lng:23.3950,type:'military',warheads:1,yieldKt:300,cat:'Lithuanian AF base. NATO Baltic Air Policing primary.'},
  {name:'Lask Air Base',lat:51.5517,lng:19.1792,type:'military',warheads:1,yieldKt:300,cat:'Polish AF base. F-16 operations, NATO enhanced presence.'},
  {name:'Deveselu Aegis Ashore',lat:43.7653,lng:24.3922,type:'military',warheads:1,yieldKt:300,cat:'US Aegis Ashore BMD site. SM-3 interceptors.'},
  {name:'Redzikowo Aegis Ashore',lat:54.4781,lng:17.1006,type:'military',warheads:1,yieldKt:300,cat:'US Aegis Ashore BMD site. Activated 2024. SM-3 interceptors.'},
  {name:'Grafenwohr Training Area',lat:49.6983,lng:11.9250,type:'military',warheads:1,yieldKt:300,cat:'Largest US Army training area in Europe. Major troop concent'},
  {name:'Mihail Kogalniceanu Air Base',lat:44.3622,lng:28.4883,type:'military',warheads:1,yieldKt:300,cat:'Major US/NATO rotational force hub on Black Sea.'},
  {name:'London',lat:51.5074,lng:-0.1278,type:'city',warheads:4,yieldKt:800,cat:'UK capital. Global financial center.'},
  {name:'Paris',lat:48.8566,lng:2.3522,type:'city',warheads:3,yieldKt:800,cat:'French capital. EU\'s largest metro area.'},
  {name:'Berlin',lat:52.5200,lng:13.4050,type:'city',warheads:2,yieldKt:800,cat:'German capital. Largest city in EU by population.'},
  {name:'Rome',lat:41.9028,lng:12.4964,type:'city',warheads:2,yieldKt:800,cat:'Italian capital. Historical center.'},
  {name:'Madrid',lat:40.4168,lng:-3.7038,type:'city',warheads:2,yieldKt:800,cat:'Spanish capital. Largest city in Spain.'},
  {name:'Ankara',lat:39.9334,lng:32.8597,type:'city',warheads:1,yieldKt:300,cat:'Turkish capital. Central Anatolia.'},
  {name:'Warsaw',lat:52.2297,lng:21.0122,type:'city',warheads:2,yieldKt:800,cat:'Polish capital. NATO eastern flank anchor.'},
  {name:'Bucharest',lat:44.4268,lng:26.1025,type:'city',warheads:1,yieldKt:300,cat:'Romanian capital. Black Sea region anchor.'},
  {name:'Budapest',lat:47.4979,lng:19.0402,type:'city',warheads:1,yieldKt:300,cat:'Hungarian capital. Danube strategic crossing.'},
  {name:'Prague',lat:50.0755,lng:14.4378,type:'city',warheads:1,yieldKt:300,cat:'Czech capital. Central European hub.'},
  {name:'Lisbon',lat:38.7223,lng:-9.1393,type:'city',warheads:1,yieldKt:300,cat:'Portuguese capital. Atlantic gateway.'},
  {name:'Athens',lat:37.9838,lng:23.7275,type:'city',warheads:1,yieldKt:300,cat:'Greek capital. Eastern Mediterranean.'},
  {name:'Brussels',lat:50.8503,lng:4.3517,type:'city',warheads:1,yieldKt:300,cat:'Belgian capital. NATO and EU headquarters city.'},
  {name:'Amsterdam',lat:52.3676,lng:4.9041,type:'city',warheads:1,yieldKt:300,cat:'Dutch capital (constitutional). Major port city.'},
  {name:'Copenhagen',lat:55.6761,lng:12.5683,type:'city',warheads:1,yieldKt:300,cat:'Danish capital. Baltic approaches.'},
  {name:'Oslo',lat:59.9139,lng:10.7522,type:'city',warheads:1,yieldKt:300,cat:'Norwegian capital. Arctic/North Sea gateway.'},
  {name:'Stockholm',lat:59.3293,lng:18.0686,type:'city',warheads:1,yieldKt:300,cat:'Swedish capital. Baltic Sea control.'},
  {name:'Helsinki',lat:60.1699,lng:24.9384,type:'city',warheads:1,yieldKt:300,cat:'Finnish capital. 280km from Russia.'},
  {name:'Tallinn',lat:59.4370,lng:24.7536,type:'city',warheads:1,yieldKt:300,cat:'Estonian capital. NATO Baltic frontline.'},
  {name:'Riga',lat:56.9496,lng:24.1052,type:'city',warheads:1,yieldKt:300,cat:'Latvian capital. Baltic region.'},
  {name:'Vilnius',lat:54.6872,lng:25.2797,type:'city',warheads:1,yieldKt:300,cat:'Lithuanian capital. Near Suwalki Gap.'},
  {name:'Sofia',lat:42.6977,lng:23.3219,type:'city',warheads:1,yieldKt:300,cat:'Bulgarian capital. Black Sea region.'},
  {name:'Zagreb',lat:45.8150,lng:15.9819,type:'city',warheads:1,yieldKt:300,cat:'Croatian capital.'},
  {name:'Bratislava',lat:48.1486,lng:17.1077,type:'city',warheads:1,yieldKt:300,cat:'Slovak capital. On the Danube.'},
  {name:'Ljubljana',lat:46.0569,lng:14.5058,type:'city',warheads:1,yieldKt:300,cat:'Slovenian capital. Alpine crossroads.'},
  {name:'Tirana',lat:41.3275,lng:19.8187,type:'city',warheads:1,yieldKt:300,cat:'Albanian capital.'},
  {name:'Skopje',lat:41.9973,lng:21.4280,type:'city',warheads:1,yieldKt:300,cat:'North Macedonian capital.'},
  {name:'Podgorica',lat:42.4304,lng:19.2594,type:'city',warheads:1,yieldKt:300,cat:'Montenegrin capital.'},
  {name:'Luxembourg City',lat:49.6116,lng:6.1300,type:'city',warheads:1,yieldKt:300,cat:'Luxembourg capital. EU institutions.'},
  {name:'Reykjavik',lat:64.1466,lng:-21.9426,type:'city',warheads:1,yieldKt:300,cat:'Icelandic capital. GIUK gap monitoring.'},
];

// Chinese targets (66 targets)
NM.WW3_TARGETS_CN = [
  {name:'Yumen Silo Field (Base 64)',lat:40.1449,lng:96.5518,type:'icbm',warheads:4,yieldKt:455,cat:'120 silos for solid-fuel ICBMs. 1,110 km2 area. Construction'},
  {name:'Hami Silo Field (Base 64)',lat:42.3500,lng:92.5500,type:'icbm',warheads:4,yieldKt:455,cat:'110 silos. 1,028 km2 area. Eastern Xinjiang. Security gates '},
  {name:'Hanggin Banner/Ordos Silo Field (Base 65)',lat:40.1130,lng:108.1040,type:'icbm',warheads:4,yieldKt:455,cat:'90 silos. 832 km2. Inner Mongolia, Northern Theater. Differe'},
  {name:'Jilantai Training Area',lat:39.7000,lng:105.4164,type:'icbm',warheads:4,yieldKt:455,cat:'PLARF training site. 16 silos, 2,090 km2. 5 missile types tr'},
  {name:'Sundian/Checunzhen (DF-5 silos, Base 66)',lat:33.8500,lng:112.0000,type:'icbm',warheads:4,yieldKt:455,cat:'Legacy DF-5 silo area, Henan Province. Additional silos unde'},
  {name:'Jingxian (DF-5 expansion)',lat:30.7200,lng:116.5500,type:'icbm',warheads:4,yieldKt:455,cat:'New DF-5 silos constructed since 2017. Anhui Province.'},
  {name:'Yueyang (DF-5 expansion)',lat:29.3700,lng:113.0900,type:'icbm',warheads:4,yieldKt:455,cat:'New DF-5 silos since 2017. Hunan Province.'},
  {name:'Luanchuan (662 Brigade, Base 66)',lat:33.7883,lng:111.5925,type:'icbm',warheads:4,yieldKt:455,cat:'DF-4/DF-5A/B silo site. Potentially upgrading to DF-41.'},
  {name:'Nanyang (663 Brigade, Base 66)',lat:33.0117,lng:112.4145,type:'icbm',warheads:2,yieldKt:455,cat:'First DF-31A brigade. Road-mobile ICBM. Henan Province.'},
  {name:'Yiyang (664 Brigade, Base 66)',lat:34.5435,lng:112.1470,type:'icbm',warheads:2,yieldKt:455,cat:'Possibly upgrading to DF-31AG. Henan Province.'},
  {name:'Tonghua (655 Brigade)',lat:41.7649,lng:125.9857,type:'icbm',warheads:2,yieldKt:455,cat:'Rumored new brigade base area. Jilin Province, near North Ko'},
  {name:'Hanzhong (Base 63 area)',lat:33.0674,lng:107.0230,type:'icbm',warheads:2,yieldKt:455,cat:'PLARF base area in Shaanxi. DF-31/DF-41 units. Mountain terr'},
  {name:'Luoyang (Base 66 HQ)',lat:34.6405,lng:112.3823,type:'icbm',warheads:2,yieldKt:455,cat:'Headquarters of Base 66. Commands multiple ICBM brigades in '},
  {name:'Yulin/Longpo Naval Base',lat:18.2028,lng:109.6944,type:'sub',warheads:3,yieldKt:455,cat:'South Sea Fleet. Underground pens for 20 subs. 6 Type 094 Ji'},
  {name:'Jianggezhuang Naval Base',lat:36.1108,lng:120.5758,type:'sub',warheads:3,yieldKt:455,cat:'Submarine Base No.1. Underground tunnel complex. Near Qingda'},
  {name:'Qingdao Naval Base (North Sea Fleet HQ)',lat:36.0661,lng:120.3694,type:'sub',warheads:3,yieldKt:455,cat:'North Sea Fleet headquarters. Major surface/submarine fleet '},
  {name:'Neixiang Air Base (106th Air Brigade)',lat:32.9767,lng:111.8832,type:'bomber',warheads:2,yieldKt:455,cat:'Only H-6N nuclear bomber base. 20 H-6K/N bombers. ALBM-capab'},
  {name:'Xi\'an Yanliang (XAC/CFTE)',lat:34.6446,lng:109.2430,type:'bomber',warheads:2,yieldKt:455,cat:'H-6 manufacturing/test facility. Xi\'an Aircraft Industrial '},
  {name:'Mianyang/CAEP (Science City)',lat:31.4674,lng:104.6790,type:'nuclear',warheads:1,yieldKt:300,cat:'China Academy of Engineering Physics. Primary nuclear warhea'},
  {name:'CAEP 903 Factory (Pingwu County)',lat:32.4200,lng:104.5300,type:'nuclear',warheads:1,yieldKt:300,cat:'Nuclear warhead fabrication facility. ~100km NW of Mianyang '},
  {name:'Lanzhou Enrichment Plant (Plant 504)',lat:36.1481,lng:103.5235,type:'nuclear',warheads:1,yieldKt:300,cat:'China\'s largest uranium enrichment facility. GDP operationa'},
  {name:'Guangyuan Nuclear Complex (Plant 821)',lat:32.4300,lng:105.8400,type:'nuclear',warheads:1,yieldKt:300,cat:'Plutonium production reactor complex. Northern Sichuan. Part'},
  {name:'Heping GDP (Plant 814, Jinkouhe)',lat:29.2500,lng:103.5900,type:'nuclear',warheads:1,yieldKt:300,cat:'Second HEU production facility. Leshan area, Sichuan. Operat'},
  {name:'Baotou Nuclear Fuel Plant (Plant 202)',lat:40.6563,lng:109.8422,type:'nuclear',warheads:1,yieldKt:300,cat:'Nuclear fuel component fabrication. Inner Mongolia. Uranium/'},
  {name:'Jiuquan Atomic Energy Complex (Plant 404)',lat:40.1200,lng:97.6400,type:'nuclear',warheads:1,yieldKt:300,cat:'Plutonium production & reprocessing. Near Yumen. Part of ori'},
  {name:'Taibai County Warhead Storage (Baoji)',lat:33.9700,lng:107.3200,type:'nuclear',warheads:1,yieldKt:300,cat:'PLARF central warhead handling and storage facility. Shaanxi'},
  {name:'Shanghai',lat:31.2304,lng:121.4737,type:'city',warheads:1,yieldKt:300,cat:'Financial center. Largest city proper. Jiangnan Shipyard.'},
  {name:'Beijing',lat:39.9042,lng:116.4074,type:'city',warheads:1,yieldKt:300,cat:'National capital. PLA command centers. Central government.'},
  {name:'Chongqing',lat:29.4316,lng:106.9123,type:'city',warheads:1,yieldKt:300,cat:'Largest municipality. Southwestern industrial hub. Defense m'},
  {name:'Chengdu',lat:30.5728,lng:104.0668,type:'city',warheads:1,yieldKt:300,cat:'Western Theater Command HQ. Chengdu J-20 production. CAEP ne'},
  {name:'Guangzhou',lat:23.1291,lng:113.2644,type:'city',warheads:1,yieldKt:300,cat:'Southern Theater Command HQ. Pearl River Delta manufacturing'},
  {name:'Shenzhen',lat:22.5431,lng:114.0579,type:'city',warheads:1,yieldKt:300,cat:'Tech capital. Adjacent to Hong Kong. Major electronics/semic'},
  {name:'Wuhan',lat:30.5928,lng:114.3055,type:'city',warheads:1,yieldKt:300,cat:'Central China hub. Major rail/river junction. Heavy industry'},
  {name:'Tianjin',lat:39.3434,lng:117.3616,type:'city',warheads:1,yieldKt:300,cat:'Beijing\'s port city. Major industrial/petrochemical center.'},
  {name:'Xi\'an',lat:34.3416,lng:108.9398,type:'city',warheads:1,yieldKt:300,cat:'Aerospace/defense center. XAC H-6 production. AVIC headquart'},
  {name:'Suzhou',lat:31.2990,lng:120.5853,type:'city',warheads:1,yieldKt:300,cat:'Major manufacturing center. Electronics and semiconductors.'},
  {name:'Zhengzhou',lat:34.7466,lng:113.6253,type:'city',warheads:1,yieldKt:300,cat:'Henan capital. Central rail hub. Near PLARF Base 66 units.'},
  {name:'Hangzhou',lat:30.2741,lng:120.1551,type:'city',warheads:1,yieldKt:300,cat:'Zhejiang capital. Tech hub (Alibaba). Eastern Theater.'},
  {name:'Shijiazhuang',lat:38.0428,lng:114.5149,type:'city',warheads:1,yieldKt:300,cat:'Hebei capital. Near Beijing military support zone.'},
  {name:'Dongguan',lat:23.0208,lng:113.7518,type:'city',warheads:1,yieldKt:300,cat:'Pearl River Delta manufacturing powerhouse.'},
  {name:'Changsha',lat:28.2282,lng:112.9388,type:'city',warheads:1,yieldKt:300,cat:'Hunan capital. Defense industry and education center.'},
  {name:'Hefei',lat:31.8206,lng:117.2272,type:'city',warheads:1,yieldKt:300,cat:'Anhui capital. Growing tech/semiconductor hub.'},
  {name:'Nanjing',lat:32.0603,lng:118.7969,type:'city',warheads:1,yieldKt:300,cat:'Eastern Theater Command HQ. Major military/political signifi'},
  {name:'Jinan',lat:36.6512,lng:116.9969,type:'city',warheads:1,yieldKt:300,cat:'Shandong capital. Northern Theater support.'},
  {name:'Shenyang',lat:41.8057,lng:123.4315,type:'city',warheads:1,yieldKt:300,cat:'Northern Theater Command HQ. Shenyang Aircraft Corp (J-11/J-'},
  {name:'Foshan',lat:23.0218,lng:113.1216,type:'city',warheads:1,yieldKt:300,cat:'Pearl River Delta manufacturing. Adjacent to Guangzhou.'},
  {name:'Wenzhou',lat:28.0000,lng:120.6722,type:'city',warheads:1,yieldKt:300,cat:'Zhejiang coast. Light manufacturing hub.'},
  {name:'Ningbo',lat:29.8683,lng:121.5440,type:'city',warheads:1,yieldKt:300,cat:'Major deep-water port. Eastern coast logistics hub.'},
  {name:'Nanning',lat:22.8170,lng:108.3665,type:'city',warheads:1,yieldKt:300,cat:'Guangxi capital. Near Vietnam border.'},
  {name:'Harbin',lat:45.8038,lng:126.5350,type:'city',warheads:1,yieldKt:300,cat:'Heilongjiang capital. Near Russia. Heavy industry and aerosp'},
  {name:'Kunming',lat:25.0389,lng:102.7183,type:'city',warheads:1,yieldKt:300,cat:'Yunnan capital. Southern Theater air operations hub.'},
  {name:'Changchun',lat:43.8171,lng:125.3235,type:'city',warheads:1,yieldKt:300,cat:'Jilin capital. Automotive and satellite manufacturing.'},
  {name:'Fuzhou',lat:26.0745,lng:119.2965,type:'city',warheads:1,yieldKt:300,cat:'Fujian capital. Taiwan Strait frontline logistics.'},
  {name:'Dalian',lat:38.9140,lng:121.6147,type:'city',warheads:1,yieldKt:300,cat:'Major naval port. Dalian Shipbuilding (aircraft carriers, de'},
  {name:'Nanchang',lat:28.6820,lng:115.8579,type:'city',warheads:1,yieldKt:300,cat:'Jiangxi capital. AVIC Hongdu Aviation (L-15, CJ-6 trainers).'},
  {name:'Guiyang',lat:26.6470,lng:106.6302,type:'city',warheads:1,yieldKt:300,cat:'Guizhou capital. Defense electronics and aerospace.'},
  {name:'Lanzhou',lat:36.0611,lng:103.8343,type:'nuclear',warheads:1,yieldKt:300,cat:'Gansu capital. Uranium enrichment plant. Western logistics h'},
  {name:'Urumqi',lat:43.8256,lng:87.6168,type:'city',warheads:1,yieldKt:300,cat:'Xinjiang capital. Western military staging. Near Hami silo f'},
  {name:'Taiyuan',lat:37.8706,lng:112.5489,type:'city',warheads:1,yieldKt:300,cat:'Shanxi capital. Taiyuan Satellite Launch Center nearby.'},
  {name:'Wuxi',lat:31.4912,lng:120.3119,type:'city',warheads:1,yieldKt:300,cat:'Major semiconductor and electronics manufacturing hub.'},
  {name:'Xuzhou',lat:34.2616,lng:117.1859,type:'city',warheads:1,yieldKt:300,cat:'Major rail junction. Strategic crossroads in Jiangsu.'},
  {name:'Tangshan',lat:39.6307,lng:118.1802,type:'city',warheads:1,yieldKt:300,cat:'Steel production capital. North China industry.'},
  {name:'Xiamen',lat:24.4798,lng:118.0894,type:'city',warheads:1,yieldKt:300,cat:'Fujian coast. Directly across from Taiwan-held Kinmen island'},
  {name:'Zhuhai',lat:22.2710,lng:113.5767,type:'city',warheads:1,yieldKt:300,cat:'Adjacent to Macau. China Airshow host. Defense industry show'},
  {name:'Haikou',lat:20.0174,lng:110.3492,type:'city',warheads:1,yieldKt:300,cat:'Hainan capital. Southern military infrastructure support.'},
  {name:'Lhasa',lat:29.6500,lng:91.1000,type:'city',warheads:1,yieldKt:300,cat:'Tibet capital. Growing PLARF missile presence on Tibetan Pla'},
];

// Launch origins (for missile arcs)
NM.WW3_LAUNCHERS = {
  us_icbm: [{lat:47.506,lng:-111.183,name:'Malmstrom'},{lat:48.416,lng:-101.358,name:'Minot'},{lat:41.145,lng:-104.862,name:'Warren'}],
  us_slbm: [{lat:58.0,lng:-30.0,name:'Atlantic SSBN'},{lat:40.0,lng:-155.0,name:'Pacific SSBN'},{lat:32.0,lng:-65.0,name:'Atlantic Patrol'}],
  ru_icbm: [{lat:54.035,lng:36.013,name:'Kozelsk'},{lat:51.700,lng:45.537,name:'Tatishchevo'},{lat:51.049,lng:59.853,name:'Dombarovsky'},{lat:55.114,lng:89.634,name:'Uzhur'},{lat:56.883,lng:40.517,name:'Teykovo'},{lat:57.863,lng:33.652,name:'Vypolzovo'}],
  ru_slbm: [{lat:72.0,lng:35.0,name:'Barents SSBN'},{lat:55.0,lng:150.0,name:'Okhotsk SSBN'},{lat:68.0,lng:40.0,name:'White Sea SSBN'}],
  cn_icbm: [{lat:40.283,lng:97.033,name:'Yumen'},{lat:42.800,lng:93.500,name:'Hami'},{lat:40.500,lng:107.000,name:'Hanggin Banner'}],
  // NATO retaliatory launchers (UK Trident + French M51)
  uk_slbm: [{lat:56.0,lng:-10.0,name:'UK Trident Patrol'},{lat:50.0,lng:-15.0,name:'UK Trident South'}],
  fr_slbm: [{lat:46.0,lng:-8.0,name:'French SSBN Patrol'}],
  fr_air: [{lat:43.521,lng:4.938,name:'Istres BA125'},{lat:48.636,lng:4.900,name:'Saint-Dizier BA113'}],
};

// Side colors for missile arcs
const SIDE_COLORS = {us:'#89b4fa', ru:'#f38ba8', cn:'#f9e2af', uk:'#a6e3a1', fr:'#cba6f7'};

// ---- SCENARIO DEFINITIONS ----
NM.WW3_SCENARIOS = [
  {
    id: 'us_ru_full', name: 'US vs Russia (Full Exchange)',
    desc: 'Princeton Plan A-style escalation: counterforce then countervalue. ~495 warheads.',
    phases: [
      {name:'Phase 1: Counterforce',delay:0,duration:25000,filter:t=>t.type!=='city'&&t.type!=='infra'},
      {name:'Phase 2: Cities & Infrastructure',delay:40000,duration:30000,filter:t=>t.type==='city'||t.type==='infra'},
    ],
    targetSets: {us: NM.WW3_TARGETS_US, ru: NM.WW3_TARGETS_RU},
    launchSets: {us: ['us_icbm','us_slbm'], ru: ['ru_icbm','ru_slbm']},
    zoom: [40, 0, 3],
  },
  {
    id: 'ru_nato', name: 'Russia vs NATO + UK/FR Retaliation',
    desc: 'Russian strike on NATO; UK Trident & French M51 fire back at Russia.',
    phases: [
      {name:'Phase 1: Russian strike on NATO',delay:0,duration:20000,filter:t=>t.type!=='city'},
      {name:'Phase 2: UK/FR retaliation on Russia',delay:25000,duration:15000,filter:t=>t.type!=='city'},
      {name:'Phase 3: All cities',delay:42000,duration:25000,filter:t=>t.type==='city'},
    ],
    targetSets: {nato: NM.WW3_TARGETS_NATO, ru: NM.WW3_TARGETS_RU},
    launchSets: {ru: ['ru_icbm','ru_slbm'], uk: ['uk_slbm'], fr: ['fr_slbm','fr_air']},
    zoom: [52, 10, 3],
  },
  {
    id: 'us_cn', name: 'US vs China',
    desc: 'Bilateral exchange: US strikes Chinese nuclear forces + cities, China retaliates.',
    phases: [
      {name:'Phase 1: Counterforce',delay:0,duration:20000,filter:t=>t.type!=='city'},
      {name:'Phase 2: Countervalue',delay:32000,duration:22000,filter:t=>t.type==='city'},
    ],
    targetSets: {us: NM.WW3_TARGETS_US, cn: NM.WW3_TARGETS_CN},
    launchSets: {us: ['us_icbm','us_slbm'], cn: ['cn_icbm']},
    zoom: [30, 160, 3],
  },
  {
    id: 'counterforce_only', name: 'Counterforce Only (US-Russia)',
    desc: 'Military/nuclear targets only - no cities struck. "Limited" exchange.',
    phases: [
      {name:'Counterforce exchange',delay:0,duration:30000,filter:t=>t.type!=='city'&&t.type!=='infra'},
    ],
    targetSets: {us: NM.WW3_TARGETS_US, ru: NM.WW3_TARGETS_RU},
    launchSets: {us: ['us_icbm','us_slbm'], ru: ['ru_icbm','ru_slbm']},
    zoom: [50, -20, 3],
  },
  {
    id: 'global', name: 'Global Thermonuclear War',
    desc: 'US + NATO + UK + France vs Russia + China. Every warhead flies. ~708 total.',
    phases: [
      {name:'Phase 1: Counterforce',delay:0,duration:30000,filter:t=>t.type!=='city'&&t.type!=='infra'},
      {name:'Phase 2: All cities & infrastructure',delay:45000,duration:35000,filter:t=>t.type==='city'||t.type==='infra'},
    ],
    targetSets: {us: NM.WW3_TARGETS_US, ru: NM.WW3_TARGETS_RU, nato: NM.WW3_TARGETS_NATO, cn: NM.WW3_TARGETS_CN},
    launchSets: {us: ['us_icbm','us_slbm'], ru: ['ru_icbm','ru_slbm'], cn: ['cn_icbm'], uk: ['uk_slbm'], fr: ['fr_slbm','fr_air']},
    zoom: [35, 0, 3],
  },
  {
    id: 'first_strike_ru', name: 'Russian First Strike on US',
    desc: 'Russia launches surprise counterforce strike. US has no time to launch on warning.',
    phases: [
      {name:'Russian first strike',delay:0,duration:25000,filter:()=>true},
    ],
    targetSets: {us: NM.WW3_TARGETS_US},
    launchSets: {ru: ['ru_icbm','ru_slbm']},
    zoom: [39, -98, 4],
  },
  {
    id: 'first_strike_us', name: 'US First Strike on Russia',
    desc: 'US launches surprise counterforce strike on Russian nuclear forces.',
    phases: [
      {name:'US first strike',delay:0,duration:25000,filter:()=>true},
    ],
    targetSets: {ru: NM.WW3_TARGETS_RU},
    launchSets: {us: ['us_icbm','us_slbm']},
    zoom: [55, 50, 3],
  },
];

// ---- GREAT CIRCLE MATH ----
function gcInterpolate(lat1, lng1, lat2, lng2, steps) {
  const toRad = d => d * Math.PI / 180, toDeg = r => r * 180 / Math.PI;
  const f1 = toRad(lat1), l1 = toRad(lng1), f2 = toRad(lat2), l2 = toRad(lng2);
  const d = 2 * Math.asin(Math.sqrt(
    Math.pow(Math.sin((f2 - f1) / 2), 2) + Math.cos(f1) * Math.cos(f2) * Math.pow(Math.sin((l2 - l1) / 2), 2)
  ));
  if (d < 0.0001) return [[lat1, lng1], [lat2, lng2]];
  const pts = [];
  let prevLng = null;
  for (let i = 0; i <= steps; i++) {
    const f = i / steps;
    const a = Math.sin((1 - f) * d) / Math.sin(d);
    const b = Math.sin(f * d) / Math.sin(d);
    const x = a * Math.cos(f1) * Math.cos(l1) + b * Math.cos(f2) * Math.cos(l2);
    const y = a * Math.cos(f1) * Math.sin(l1) + b * Math.cos(f2) * Math.sin(l2);
    const z = a * Math.sin(f1) + b * Math.sin(f2);
    let lng = toDeg(Math.atan2(y, x));
    if (prevLng !== null) {
      while (lng - prevLng > 180) lng -= 360;
      while (lng - prevLng < -180) lng += 360;
    }
    prevLng = lng;
    pts.push([toDeg(Math.atan2(z, Math.sqrt(x * x + y * y))), lng]);
  }
  return pts;
}

function gcDistance(lat1, lng1, lat2, lng2) {
  const R = 6371, toRad = d => d * Math.PI / 180;
  const dF = toRad(lat2 - lat1), dL = toRad(lng2 - lng1);
  const a = Math.sin(dF / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dL / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ---- PROCEDURAL SOUNDS ----
function playRocketSound(ctx) {
  if (!ctx) return;
  if (ctx.state === 'suspended') ctx.resume();
  const now = ctx.currentTime;
  const dur = 0.6 + Math.random() * 0.3;
  const buf = ctx.createBuffer(1, ctx.sampleRate * dur, ctx.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < data.length; i++) {
    const t = i / ctx.sampleRate;
    data[i] = (Math.random() * 2 - 1) * (0.3 + 0.7 * Math.min(1, t / 0.1)) * Math.exp(-t / (dur * 0.5));
  }
  const src = ctx.createBufferSource(); src.buffer = buf;
  const flt = ctx.createBiquadFilter(); flt.type = 'bandpass';
  flt.frequency.setValueAtTime(300, now);
  flt.frequency.exponentialRampToValueAtTime(1200, now + dur * 0.4);
  flt.frequency.exponentialRampToValueAtTime(400, now + dur);
  flt.Q.value = 1.5;
  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0.06, now);
  gain.gain.linearRampToValueAtTime(0.12, now + 0.05);
  gain.gain.exponentialRampToValueAtTime(0.001, now + dur);
  src.connect(flt).connect(gain).connect(ctx.destination);
  src.start(now);
}

function playAirRaidSiren(ctx, duration) {
  if (!ctx) return;
  if (ctx.state === 'suspended') ctx.resume();
  const now = ctx.currentTime;
  const osc = ctx.createOscillator();
  osc.type = 'sawtooth';
  // Rising and falling siren
  osc.frequency.setValueAtTime(380, now);
  const cycles = Math.floor(duration / 2);
  for (let i = 0; i < cycles; i++) {
    osc.frequency.linearRampToValueAtTime(780, now + i * 2 + 1);
    osc.frequency.linearRampToValueAtTime(380, now + i * 2 + 2);
  }
  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0.001, now);
  gain.gain.linearRampToValueAtTime(0.15, now + 0.5);
  gain.gain.setValueAtTime(0.15, now + duration - 1);
  gain.gain.exponentialRampToValueAtTime(0.001, now + duration);
  const filter = ctx.createBiquadFilter();
  filter.type = 'bandpass'; filter.frequency.value = 600; filter.Q.value = 2;
  osc.connect(filter).connect(gain).connect(ctx.destination);
  osc.start(now); osc.stop(now + duration);
}

function playPhaseRumble(ctx) {
  if (!ctx) return;
  if (ctx.state === 'suspended') ctx.resume();
  const now = ctx.currentTime;
  const dur = 2;
  const buf = ctx.createBuffer(1, ctx.sampleRate * dur, ctx.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < data.length; i++) {
    const t = i / ctx.sampleRate;
    data[i] = (Math.random() * 2 - 1) * Math.sin(t * Math.PI / dur) * 0.5;
  }
  const src = ctx.createBufferSource(); src.buffer = buf;
  const flt = ctx.createBiquadFilter(); flt.type = 'lowpass'; flt.frequency.value = 80;
  const gain = ctx.createGain(); gain.gain.value = 0.2;
  src.connect(flt).connect(gain).connect(ctx.destination);
  src.start(now);
}

// ---- SIMULATION ENGINE ----
NM.WW3 = {
  active: false,
  layers: [],
  markers: [],
  timers: [],
  casualties: {deaths: 0, injuries: 0, warheadsLanded: 0, megatons: 0},
  startTime: 0,
  statsInterval: null,
  _scenario: null,
  _lastSoundTime: 0,
  _lastFlashTime: 0,
  _lastShakeTime: 0,
  _hudEl: null,
  _winterEl: null,
  speed: 1, // speed multiplier (1x, 2x, 5x)

  start(map, scenarioId) {
    this.stop(map);
    const scenario = NM.WW3_SCENARIOS.find(s => s.id === scenarioId);
    if (!scenario) return;
    this._scenario = scenario;
    this.active = true;
    this.casualties = {deaths: 0, injuries: 0, warheadsLanded: 0, megatons: 0};
    this.startTime = performance.now();
    this._lastSoundTime = 0;
    this._lastFlashTime = 0;
    this._lastShakeTime = 0;

    // Read speed from UI
    const speedEl = document.getElementById('ww3-speed');
    this.speed = speedEl ? +speedEl.value : 1;

    // Place target markers
    this._placeTargetMarkers(map, scenario);

    // Set view from scenario
    const z = scenario.zoom || [35, 0, 3];
    map.setView([z[0], z[1]], z[2]);

    // Create HUD overlay on map
    this._createHUD();

    // Create nuclear winter overlay
    this._createWinterOverlay();

    // Create map legend
    this._createLegend();

    // Create DEFCON indicator
    let defcon = document.getElementById('ww3-defcon');
    if (!defcon) { defcon = document.createElement('div'); defcon.id = 'ww3-defcon'; document.body.appendChild(defcon); }
    defcon.style.display = 'block'; defcon.textContent = 'DEFCON 3';
    this._defcon = 3;

    // Create impact toast container
    let toasts = document.getElementById('ww3-toasts');
    if (!toasts) { toasts = document.createElement('div'); toasts.id = 'ww3-toasts'; document.body.appendChild(toasts); }
    toasts.innerHTML = '';

    // Air raid siren
    const sirenDur = 3 / this.speed;
    if (NM.Sound.enabled && NM.Sound.ctx) {
      NM.Sound.resume();
      playAirRaidSiren(NM.Sound.ctx, Math.max(1, sirenDur));
    }

    // Start phases after siren
    const sirenMs = sirenDur * 1000;
    for (const phase of scenario.phases) {
      const tid = setTimeout(() => {
        if (!this.active) return;
        if (NM.Sound.enabled && NM.Sound.ctx && phase.delay > 0) playPhaseRumble(NM.Sound.ctx);
        this._executePhase(map, scenario, phase);
      }, (phase.delay / this.speed) + sirenMs);
      this.timers.push(tid);
    }

    // Schedule end summary
    const lastPhase = scenario.phases[scenario.phases.length - 1];
    const endTime = (lastPhase.delay + lastPhase.duration + 18000) / this.speed + sirenMs;
    this.timers.push(setTimeout(() => { if (this.active) this._showSummary(); }, endTime));

    // Live stats update
    this.statsInterval = setInterval(() => this._updateHUD(), 200);
    this._updateStatus('Air raid sirens sounding...');
    this.timers.push(setTimeout(() => { if (this.active) this._updateStatus(scenario.phases[0].name); }, sirenMs));
  },

  _createHUD() {
    // Floating HUD on the map
    let hud = document.getElementById('ww3-hud');
    if (!hud) {
      hud = document.createElement('div');
      hud.id = 'ww3-hud';
      document.body.appendChild(hud);
    }
    hud.style.display = 'flex';
    hud.innerHTML = '';
    this._hudEl = hud;
  },

  _createWinterOverlay() {
    let el = document.getElementById('ww3-winter');
    if (!el) {
      el = document.createElement('div');
      el.id = 'ww3-winter';
      document.getElementById('map').parentElement.appendChild(el);
    }
    el.style.opacity = '0';
    el.style.display = 'block';
    this._winterEl = el;
  },

  _createLegend() {
    let leg = document.getElementById('ww3-legend');
    if (!leg) {
      leg = document.createElement('div');
      leg.id = 'ww3-legend';
      document.body.appendChild(leg);
    }
    const scenario = this._scenario;
    const sides = Object.keys(scenario.launchSets);
    const sideNames = {us:'US',ru:'Russia',cn:'China',uk:'UK',fr:'France'};
    leg.innerHTML = '<div class="ww3-leg-title">Missile Arcs</div>' +
      sides.map(s => `<div class="ww3-leg-row"><span class="ww3-leg-dot" style="background:${SIDE_COLORS[s]||'#cdd6f4'}"></span>${sideNames[s]||s}</div>`).join('') +
      '<div class="ww3-leg-title" style="margin-top:4px">Targets</div>' +
      '<div class="ww3-leg-row"><span class="ww3-leg-dot" style="background:#f38ba8"></span>ICBM</div>' +
      '<div class="ww3-leg-row"><span class="ww3-leg-dot" style="background:#89b4fa"></span>Submarine</div>' +
      '<div class="ww3-leg-row"><span class="ww3-leg-dot" style="background:#cba6f7"></span>Bomber</div>' +
      '<div class="ww3-leg-row"><span class="ww3-leg-dot" style="background:#f9e2af"></span>Command</div>' +
      '<div class="ww3-leg-row"><span class="ww3-leg-dot" style="background:#fab387"></span>Nuclear</div>' +
      '<div class="ww3-leg-row"><span class="ww3-leg-dot" style="background:#94e2d5"></span>Military</div>' +
      '<div class="ww3-leg-row"><span class="ww3-leg-dot" style="background:#f5c2e7"></span>City</div>';
    leg.style.display = 'block';
  },

  _placeTargetMarkers(map, scenario) {
    const typeIcons = {icbm:'#f38ba8',sub:'#89b4fa',bomber:'#cba6f7',c2:'#f9e2af',nuclear:'#fab387',military:'#94e2d5',city:'#f5c2e7'};
    for (const [, targets] of Object.entries(scenario.targetSets)) {
      for (const t of targets) {
        const r = t.type === 'city' ? 5 : 3;
        const color = typeIcons[t.type] || '#cdd6f4';
        const m = L.circleMarker([t.lat, t.lng], {
          radius: r, color, fillColor: color, fillOpacity: 0.25, weight: 1, opacity: 0.4,
        }).bindTooltip(`<b>${t.name}</b><br>${t.cat}<br>${t.warheads}x ${NM.fmtYield(t.yieldKt)}`, {
          className: 'test-tooltip'
        }).addTo(map);
        this.markers.push(m);
      }
    }
  },

  _executePhase(map, scenario, phase) {
    if (!this.active) return;
    this._updateStatus(phase.name);

    const allTargets = [];
    for (const [side, targets] of Object.entries(scenario.targetSets)) {
      const filtered = targets.filter(phase.filter);
      // Determine who attacks this target set - enemies of the target's country
      let attackerKeys;
      if (side === 'us') {
        attackerKeys = ['ru','cn'].filter(k => scenario.launchSets[k]);
      } else if (side === 'ru') {
        attackerKeys = ['us','uk','fr'].filter(k => scenario.launchSets[k]);
      } else if (side === 'nato') {
        attackerKeys = ['ru'].filter(k => scenario.launchSets[k]);
      } else if (side === 'cn') {
        attackerKeys = ['us'].filter(k => scenario.launchSets[k]);
      } else {
        attackerKeys = Object.keys(scenario.launchSets);
      }
      if (!attackerKeys.length) continue;

      for (const t of filtered) {
        const attackerKey = attackerKeys[Math.floor(Math.random() * attackerKeys.length)];
        const launcherSets = scenario.launchSets[attackerKey];
        if (!launcherSets) continue;
        const launcherSetKey = launcherSets[Math.floor(Math.random() * launcherSets.length)];
        const launchers = NM.WW3_LAUNCHERS[launcherSetKey];
        if (!launchers || !launchers.length) continue;
        const launcher = launchers[Math.floor(Math.random() * launchers.length)];

        for (let w = 0; w < t.warheads; w++) {
          const off = t.warheads > 1 ? 0.1 : 0;
          allTargets.push({
            target: t, launcher, attackerKey,
            tLat: t.lat + (Math.random() - 0.5) * off,
            tLng: t.lng + (Math.random() - 0.5) * off,
            yieldKt: t.yieldKt
          });
        }
      }
    }

    // Shuffle for simultaneous launch
    for (let i = allTargets.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [allTargets[i], allTargets[j]] = [allTargets[j], allTargets[i]];
    }

    const launchWindow = (phase.duration * 0.4) / this.speed;
    allTargets.forEach((at, i) => {
      const delay = (i / allTargets.length) * launchWindow + Math.random() * (600 / this.speed);
      const tid = setTimeout(() => {
        if (!this.active) return;
        this._launchMissile(map, at);
      }, delay);
      this.timers.push(tid);
    });
    // Update DEFCON based on phase
    const phaseIdx = scenario.phases.indexOf(phase);
    const defcon = Math.max(1, 5 - phaseIdx * 2 - (scenario.phases.length > 1 ? 0 : 2));
    this._setDefcon(defcon);
  },

  _setDefcon(level) {
    this._defcon = level;
    const el = document.getElementById('ww3-defcon');
    if (!el) return;
    const colors = {1:'#f38ba8',2:'#fab387',3:'#f9e2af',4:'#89b4fa',5:'#a6e3a1'};
    el.style.color = colors[level] || '#cdd6f4';
    el.textContent = 'DEFCON ' + level;
    el.style.display = 'block';
    // Flash it
    el.classList.remove('ww3-defcon-flash');
    void el.offsetWidth;
    el.classList.add('ww3-defcon-flash');
  },

  _showImpactToast(name, isCity) {
    if (!isCity) return;
    const container = document.getElementById('ww3-toasts');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'ww3-toast';
    toast.textContent = name.toUpperCase() + ' HIT';
    container.appendChild(toast);
    // Remove after animation
    setTimeout(() => { try { container.removeChild(toast); } catch(e) {} }, 3500);
  },

  _launchMissile(map, at) {
    const color = SIDE_COLORS[at.attackerKey] || '#cdd6f4';
    const dist = gcDistance(at.launcher.lat, at.launcher.lng, at.tLat, at.tLng);
    const isSlbm = at.launcher.name.includes('SSBN') || at.launcher.name.includes('Atlantic') || at.launcher.name.includes('Okhotsk') || at.launcher.name.includes('Trident') || at.launcher.name.includes('French');
    const flightMs = (isSlbm ? 7000 + Math.min(dist / 2, 3000) : 10000 + Math.min(dist / 2, 4000)) / this.speed;
    const steps = 60;
    const pts = gcInterpolate(at.launcher.lat, at.launcher.lng, at.tLat, at.tLng, steps);
    const bulgeFactor = Math.min(4, dist / 3000);
    const arcPts = pts.map((p, i) => {
      const f = i / steps;
      return [p[0] + Math.sin(f * Math.PI) * bulgeFactor, p[1]];
    });

    // Launch flash at origin
    const now = performance.now();
    if (now - this._lastSoundTime > 200) {
      this._lastSoundTime = now;
      if (NM.Sound.enabled && NM.Sound.ctx) playRocketSound(NM.Sound.ctx);
    }

    // Launch site flash
    const launchFlash = L.circleMarker([at.launcher.lat, at.launcher.lng], {
      radius: 6, color: '#fff', fillColor: color, fillOpacity: 0.9, weight: 2, opacity: 1
    }).addTo(map);
    this.layers.push(launchFlash);
    setTimeout(() => { try { map.removeLayer(launchFlash); } catch(e) {} }, 800);

    // Trail
    const trail = L.polyline([], {color, weight: 1.5, opacity: 0.5, className: 'ww3-arc'}).addTo(map);
    this.layers.push(trail);

    // Warhead dot
    const dot = L.circleMarker(arcPts[0], {
      radius: 3.5, color: '#fff', fillColor: color, fillOpacity: 1, weight: 2, opacity: 1, className: 'ww3-warhead'
    }).addTo(map);
    this.layers.push(dot);

    let start = performance.now();
    let pausedAt = 0;
    const tick = (now2) => {
      if (!this.active) return;
      if (this.paused) { if (!pausedAt) pausedAt = now2; requestAnimationFrame(tick); return; }
      if (pausedAt) { start += now2 - pausedAt; pausedAt = 0; }
      const p = Math.min(1, (now2 - start) / flightMs);
      const eased = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
      const idx = Math.floor(eased * steps);
      dot.setLatLng(arcPts[Math.min(idx, steps)]);
      trail.setLatLngs(arcPts.slice(0, idx + 1));
      trail.setStyle({opacity: Math.max(0.1, 0.5 - p * 0.3)});

      if (p < 1) requestAnimationFrame(tick);
      else {
        map.removeLayer(dot);
        // Fade trail
        const fs = performance.now();
        const ft = (n) => {
          const fp = Math.min(1, (n - fs) / 2500);
          trail.setStyle({opacity: 0.15 * (1 - fp)});
          if (fp < 1 && this.active) requestAnimationFrame(ft);
          else { try { map.removeLayer(trail); } catch(e) {} }
        };
        requestAnimationFrame(ft);
        this._detonate(map, at.tLat, at.tLng, at.yieldKt, at.target.type === 'city', at.target.name);
      }
    };
    requestAnimationFrame(tick);
  },

  _detonate(map, lat, lng, yieldKt, isCity, targetName) {
    if (!this.active) return;
    const now = performance.now();
    this.casualties.warheadsLanded++;

    const effects = NM.calcEffects(yieldKt, 'airburst', 0, 50);

    // Only draw full effect rings for cities (performance)
    if (isCity) {
      const det = {id: Date.now()+Math.random(), lat, lng, yieldKt, burstType:'airburst', heightM:0, fission:50, effects, casualties:{deaths:0,injuries:0}, layers:[]};
      NM.Effects.drawRings(map, det).forEach(l => this.layers.push(l));
    }

    // Screen flash (throttled)
    if (now - this._lastFlashTime > 600) {
      this._lastFlashTime = now;
      NM.Animation.flash(Math.min(1, 0.3 + Math.log10(Math.max(yieldKt, 1)) * 0.15));
    }

    // Camera shake (throttled)
    if (now - this._lastShakeTime > 500) {
      this._lastShakeTime = now;
      NM.Animation.shake(map, Math.min(4, 1 + Math.log10(Math.max(yieldKt, 1)) * 0.7), 400);
    }

    // Explosion sound (throttled)
    if (NM.Sound.enabled && now - this._lastSoundTime > 350) {
      this._lastSoundTime = now;
      NM.Sound.detonate(yieldKt);
    }

    // Animated fireball
    const flashR = Math.max(effects.fireball * 1000, 800);
    const flash = L.circle([lat, lng], {
      radius: flashR * 0.3, color:'#fff', fillColor:'#fff', fillOpacity:0.9, weight:0, opacity:0
    }).addTo(map);
    this.layers.push(flash);

    const fs = performance.now();
    const ft = (n) => {
      const p = Math.min(1, (n - fs) / 1800);
      flash.setRadius(flashR * (0.3 + p * 1.5));
      flash.setStyle({
        fillOpacity: Math.max(0, 0.9 * (1 - p * p)),
        fillColor: p < 0.15 ? '#fff' : p < 0.4 ? '#f9e2af' : p < 0.7 ? '#fab387' : '#f38ba8',
      });
      if (p < 1 && this.active) requestAnimationFrame(ft);
      else { try { map.removeLayer(flash); } catch(e) {} }
    };
    requestAnimationFrame(ft);

    // Permanent GZ marker (pulsing for cities)
    const gzSize = isCity ? 10 : 6;
    const gzIcon = L.divIcon({
      className: '', iconSize: [gzSize, gzSize], iconAnchor: [gzSize/2, gzSize/2],
      html: `<div class="ww3-gz${isCity ? ' ww3-gz-city' : ''}" style="width:${gzSize}px;height:${gzSize}px"></div>`
    });
    this.layers.push(L.marker([lat, lng], {icon: gzIcon, interactive: false}).addTo(map));

    // City burn scar (persistent dark circle showing destroyed area)
    if (isCity) {
      const burnR = Math.max(effects.psi5 * 1000, 2000);
      const burnScar = L.circle([lat, lng], {
        radius: burnR, color: 'transparent', fillColor: '#1e1e2e', fillOpacity: 0.35, weight: 0
      }).addTo(map);
      this.layers.push(burnScar);
    }

    // Impact toast for cities
    if (targetName) this._showImpactToast(targetName, isCity);

    // Nuclear winter darkening
    if (this._winterEl) {
      const totalWh = this._scenario ? this.countWarheads(this._scenario.id) : 400;
      const darkness = Math.min(0.45, (this.casualties.warheadsLanded / totalWh) * 0.5);
      this._winterEl.style.opacity = String(darkness);
    }

    // Casualties + megatonnage
    const cas = NM.estimateCasualties(lat, lng, effects);
    this.casualties.deaths += cas.deaths;
    this.casualties.injuries += cas.injuries;
    this.casualties.megatons += yieldKt / 1000;
  },

  _updateHUD() {
    if (!this._hudEl || !this.active) return;
    const totalWh = this._scenario ? this.countWarheads(this._scenario.id) : 0;
    const elapsed = ((performance.now() - this.startTime) / 1000).toFixed(0);
    // Simulated real-world minutes (~30 min ICBM flight compressed)
    const simMin = Math.floor(elapsed * 2.5);

    this._hudEl.innerHTML = `
      <div class="ww3-hud-item"><span class="ww3-hud-val" style="color:#f38ba8">${NM.fmtNum(this.casualties.deaths)}</span><span class="ww3-hud-lbl">Dead</span></div>
      <div class="ww3-hud-sep"></div>
      <div class="ww3-hud-item"><span class="ww3-hud-val" style="color:#fab387">${NM.fmtNum(this.casualties.injuries)}</span><span class="ww3-hud-lbl">Injured</span></div>
      <div class="ww3-hud-sep"></div>
      <div class="ww3-hud-item"><span class="ww3-hud-val" style="color:#f9e2af">${NM.fmtNum(this.casualties.deaths + this.casualties.injuries)}</span><span class="ww3-hud-lbl">Total</span></div>
      <div class="ww3-hud-sep"></div>
      <div class="ww3-hud-item"><span class="ww3-hud-val" style="color:#cba6f7">${this.casualties.warheadsLanded}<span style="opacity:0.5">/${totalWh}</span></span><span class="ww3-hud-lbl">Warheads</span></div>
      <div class="ww3-hud-sep"></div>
      <div class="ww3-hud-item"><span class="ww3-hud-val" style="color:#94e2d5">${this.casualties.megatons.toFixed(0)} MT</span><span class="ww3-hud-lbl">Yield</span></div>`;

    // Also update panel stats
    const el = document.getElementById('ww3-stats');
    if (el) el.innerHTML = this._hudEl.innerHTML;
  },

  _updateStatus(text) {
    const el = document.getElementById('ww3-phase');
    if (el) el.textContent = text;
    // Also update HUD phase if exists
    if (this._hudEl) this._hudEl.dataset.phase = text;
  },

  _showSummary() {
    if (!this.active) return;
    this._updateStatus('Simulation complete');
    const c = this.casualties;
    const totalWh = this._scenario ? this.countWarheads(this._scenario.id) : 0;
    const el = document.getElementById('ww3-stats');
    // Long-term estimate: 3-5x immediate for total deaths over months/years
    const longTermLow = c.deaths * 3;
    const longTermHigh = c.deaths * 5;
    const hiroshimaEquiv = Math.round(c.megatons * 1000 / 15); // 15kT = Hiroshima
    if (el) {
      el.innerHTML = `<div class="ww3-summary">
        <div class="ww3-sum-title">SIMULATION COMPLETE</div>
        <div class="ww3-sum-row"><span>Warheads detonated</span><span style="color:var(--mauve)">${c.warheadsLanded} of ${totalWh}</span></div>
        <div class="ww3-sum-row"><span>Total yield</span><span style="color:var(--teal)">${c.megatons.toFixed(0)} MT (${NM.fmtNum(hiroshimaEquiv)} Hiroshimas)</span></div>
        <div class="ww3-sum-row"><span>Immediate fatalities</span><span style="color:var(--red)">${NM.fmtNum(c.deaths)}</span></div>
        <div class="ww3-sum-row"><span>Immediate injuries</span><span style="color:var(--peach)">${NM.fmtNum(c.injuries)}</span></div>
        <div class="ww3-sum-row"><span>Total immediate</span><span style="color:var(--yellow)">${NM.fmtNum(c.deaths + c.injuries)}</span></div>
        <div class="ww3-sum-row" style="border-top:1px solid var(--surface1);padding-top:4px;margin-top:2px"><span>Est. long-term deaths</span><span style="color:var(--red);opacity:0.7">${NM.fmtNum(longTermLow)} - ${NM.fmtNum(longTermHigh)}</span></div>
        <div class="ww3-sum-note">Long-term estimate includes fallout, firestorms, nuclear winter (Toon et al.), infrastructure collapse, medical system failure, and radiation-induced cancers. Based on peer-reviewed models from Princeton SGS, ICAN, and Bulletin of the Atomic Scientists.</div>
      </div>`;
    }
    // Set DEFCON 1
    this._setDefcon(1);
    if (this.statsInterval) { clearInterval(this.statsInterval); this.statsInterval = null; }
  },

  stop(map) {
    this.active = false;
    this.timers.forEach(t => clearTimeout(t));
    this.timers = [];
    if (this.statsInterval) { clearInterval(this.statsInterval); this.statsInterval = null; }
    this.layers.forEach(l => { try { map.removeLayer(l); } catch(e) {} });
    this.markers.forEach(m => { try { map.removeLayer(m); } catch(e) {} });
    this.layers = [];
    this.markers = [];
    this.casualties = {deaths: 0, injuries: 0, warheadsLanded: 0, megatons: 0};
    this._scenario = null;
    // Remove HUD
    const hud = document.getElementById('ww3-hud');
    if (hud) hud.style.display = 'none';
    // Remove legend
    const leg = document.getElementById('ww3-legend');
    if (leg) leg.style.display = 'none';
    // Remove DEFCON
    const defcon = document.getElementById('ww3-defcon');
    if (defcon) defcon.style.display = 'none';
    // Remove toasts
    const toasts = document.getElementById('ww3-toasts');
    if (toasts) toasts.innerHTML = '';
    // Remove winter overlay
    const winter = document.getElementById('ww3-winter');
    if (winter) { winter.style.opacity = '0'; winter.style.display = 'none'; }
    const el = document.getElementById('ww3-stats');
    if (el) el.innerHTML = '';
    const ph = document.getElementById('ww3-phase');
    if (ph) ph.textContent = 'Simulation idle';
  },

  countWarheads(scenarioId) {
    const scenario = NM.WW3_SCENARIOS.find(s => s.id === scenarioId);
    if (!scenario) return 0;
    let total = 0;
    for (const targets of Object.values(scenario.targetSets)) {
      for (const t of targets) total += t.warheads;
    }
    return total;
  }
};
