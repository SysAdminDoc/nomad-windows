"""Kiwix service — offline Wikipedia and reference libraries."""

import os
import subprocess
import time
import logging
import requests
from services.manager import (
    get_services_dir, download_file, start_process, stop_process,
    is_running, check_port, _download_progress
)
from db import get_db

log = logging.getLogger('nomad.kiwix')

SERVICE_ID = 'kiwix'
KIWIX_PORT = 8888
def _get_kiwix_url():
    from platform_utils import get_kiwix_url
    return get_kiwix_url()
STARTER_ZIM_URL = 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_100_mini_2026-01.zim'

# Curated ZIM catalog — comprehensive offline knowledge library
# 13 categories, 3 tiers each (Essential/Standard/Comprehensive)
ZIM_CATALOG = [
    {
        'category': 'Wikipedia',
        'tiers': {
            'essential': [
                {'name': 'Wikipedia Mini (Top 100)', 'filename': 'wikipedia_en_100_mini_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_100_mini_2026-01.zim',
                 'size': '1.2 MB', 'desc': 'Top 100 articles — quick reference'},
            ],
            'standard': [
                {'name': 'Wikipedia Top (No Pics)', 'filename': 'wikipedia_en_top_nopic_2026-03.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_top_nopic_2026-03.zim',
                 'size': '~3 GB', 'desc': 'Top 100,000 articles without images'},
                {'name': 'Wikipedia Top (With Pics)', 'filename': 'wikipedia_en_top_maxi_2026-03.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_top_maxi_2026-03.zim',
                 'size': '~7.7 GB', 'desc': 'Top articles with images'},
            ],
            'comprehensive': [
                {'name': 'Wikipedia Full (With Pics)', 'filename': 'wikipedia_en_all_maxi_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_all_maxi_2026-02.zim',
                 'size': '~115 GB', 'desc': 'Complete English Wikipedia with all images (includes everything from nopic version)'},
            ],
        },
    },
    {
        'category': 'Medicine & Health',
        'tiers': {
            'essential': [
                {'name': 'WikiMed Medical Encyclopedia', 'filename': 'wikipedia_en_medicine_nopic_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_medicine_nopic_2026-01.zim',
                 'size': '~800 MB', 'desc': 'Medical articles from Wikipedia'},
                {'name': 'NHS Medicines A-Z', 'filename': 'nhs.uk_en_medicines_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/nhs.uk_en_medicines_2025-12.zim',
                 'size': '16 MB', 'desc': 'UK medication reference'},
            ],
            'standard': [
                {'name': 'WikiMed Full (With Images)', 'filename': 'mdwiki_en_all_2025-11.zim',
                 'url': 'https://download.kiwix.org/zim/other/mdwiki_en_all_2025-11.zim',
                 'size': '~10 GB', 'desc': '73,000+ medical articles curated by WikiProject Medicine'},
                {'name': 'MedlinePlus Health Topics', 'filename': 'medlineplus.gov_en_all_2025-01.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/medlineplus.gov_en_all_2025-01.zim',
                 'size': '~1.8 GB', 'desc': 'NIH consumer health information'},
                {'name': 'NHS Medicines A-Z', 'filename': 'nhs.uk_en_medicines_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/nhs.uk_en_medicines_2025-12.zim',
                 'size': '16 MB', 'desc': 'UK medication reference'},
                {'name': 'Military Medicine', 'filename': 'fas-military-medicine_en_2025-06.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/fas-military-medicine_en_2025-06.zim',
                 'size': '78 MB', 'desc': 'Military medicine field manuals'},
            ],
            'comprehensive': [
                {'name': 'WikiMed Full (With Images)', 'filename': 'mdwiki_en_all_2025-11.zim',
                 'url': 'https://download.kiwix.org/zim/other/mdwiki_en_all_2025-11.zim',
                 'size': '~10 GB', 'desc': '73,000+ medical articles'},
                {'name': 'MedlinePlus Health Topics', 'filename': 'medlineplus.gov_en_all_2025-01.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/medlineplus.gov_en_all_2025-01.zim',
                 'size': '~1.8 GB', 'desc': 'NIH consumer health information'},
                {'name': 'CDC Reference', 'filename': 'wwwnc.cdc.gov_en_all_2024-11.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/wwwnc.cdc.gov_en_all_2024-11.zim',
                 'size': '170 MB', 'desc': 'CDC disease reference and travelers health'},
                {'name': 'Military Medicine', 'filename': 'fas-military-medicine_en_2025-06.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/fas-military-medicine_en_2025-06.zim',
                 'size': '78 MB', 'desc': 'Military medicine field manuals'},
                {'name': 'NHS Medicines A-Z', 'filename': 'nhs.uk_en_medicines_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/nhs.uk_en_medicines_2025-12.zim',
                 'size': '16 MB', 'desc': 'UK medication reference'},
                {'name': 'Medical Sciences SE', 'filename': 'medicalsciences.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/medicalsciences.stackexchange.com_en_all_2025-12.zim',
                 'size': '58 MB', 'desc': 'Medical sciences Q&A'},
            ],
        },
    },
    {
        'category': 'Survival & Preparedness',
        'tiers': {
            'essential': [
                {'name': 'Post-Disaster Guide', 'filename': 'zimgit-post-disaster_en_2024-05.zim',
                 'url': 'https://download.kiwix.org/zim/other/zimgit-post-disaster_en_2024-05.zim',
                 'size': '615 MB', 'desc': 'Comprehensive post-disaster response and recovery guide'},
                {'name': 'Water Treatment Guide', 'filename': 'zimgit-water_en_2024-08.zim',
                 'url': 'https://download.kiwix.org/zim/other/zimgit-water_en_2024-08.zim',
                 'size': '20 MB', 'desc': 'Water purification, treatment, and sourcing guide'},
                {'name': 'FEMA Ready.gov', 'filename': 'www.ready.gov_en_2024-12.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/www.ready.gov_en_2024-12.zim',
                 'size': '~2.3 GB', 'desc': 'FEMA disaster preparedness guides'},
                {'name': 'Wikibooks (Guides & Manuals)', 'filename': 'wikibooks_en_all_nopic_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikibooks/wikibooks_en_all_nopic_2026-01.zim',
                 'size': '~400 MB', 'desc': 'How-to guides, textbooks, field manuals'},
            ],
            'standard': [
                {'name': 'Post-Disaster Guide', 'filename': 'zimgit-post-disaster_en_2024-05.zim',
                 'url': 'https://download.kiwix.org/zim/other/zimgit-post-disaster_en_2024-05.zim',
                 'size': '615 MB', 'desc': 'Comprehensive post-disaster response and recovery guide'},
                {'name': 'Water Treatment Guide', 'filename': 'zimgit-water_en_2024-08.zim',
                 'url': 'https://download.kiwix.org/zim/other/zimgit-water_en_2024-08.zim',
                 'size': '20 MB', 'desc': 'Water purification, treatment, and sourcing guide'},
                {'name': 'Food Preparation Guide', 'filename': 'zimgit-food-preparation_en_2025-04.zim',
                 'url': 'https://download.kiwix.org/zim/other/zimgit-food-preparation_en_2025-04.zim',
                 'size': '93 MB', 'desc': 'Food preparation, preservation, and safety guide'},
                {'name': 'Knots Guide', 'filename': 'zimgit-knots_en_2024-08.zim',
                 'url': 'https://download.kiwix.org/zim/other/zimgit-knots_en_2024-08.zim',
                 'size': '27 MB', 'desc': 'Knot tying guide with illustrations'},
                {'name': 'Survivors Guide', 'filename': 'survivors_en_all_maxi_2026-03.zim',
                 'url': 'https://download.kiwix.org/zim/other/survivors_en_all_maxi_2026-03.zim',
                 'size': '118 MB', 'desc': 'Survival skills and emergency preparedness content'},
                {'name': 'FEMA Ready.gov', 'filename': 'www.ready.gov_en_2024-12.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/www.ready.gov_en_2024-12.zim',
                 'size': '~2.3 GB', 'desc': 'FEMA disaster preparedness guides'},
                {'name': 'Wikibooks (Guides & Manuals)', 'filename': 'wikibooks_en_all_nopic_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikibooks/wikibooks_en_all_nopic_2026-01.zim',
                 'size': '~400 MB', 'desc': 'How-to guides, textbooks, field manuals'},
                {'name': 'Wikivoyage Travel Guide', 'filename': 'wikivoyage_en_all_nopic_2026-03.zim',
                 'url': 'https://download.kiwix.org/zim/wikivoyage/wikivoyage_en_all_nopic_2026-03.zim',
                 'size': '~600 MB', 'desc': 'Worldwide travel and survival information'},
                {'name': 'Outdoors SE', 'filename': 'outdoors.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/outdoors.stackexchange.com_en_all_2025-12.zim',
                 'size': '135 MB', 'desc': 'Wilderness and outdoors Q&A'},
                {'name': 'Appropedia (Sustainability Wiki)', 'filename': 'appropedia_en_all_maxi_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/other/appropedia_en_all_maxi_2026-02.zim',
                 'size': '555 MB', 'desc': 'Appropriate technology, DIY solutions, sustainable living'},
            ],
            'comprehensive': [
                {'name': 'Post-Disaster Guide', 'filename': 'zimgit-post-disaster_en_2024-05.zim',
                 'url': 'https://download.kiwix.org/zim/other/zimgit-post-disaster_en_2024-05.zim',
                 'size': '615 MB', 'desc': 'Comprehensive post-disaster response and recovery guide'},
                {'name': 'Medicine Reference', 'filename': 'zimgit-medicine_en_2024-08.zim',
                 'url': 'https://download.kiwix.org/zim/other/zimgit-medicine_en_2024-08.zim',
                 'size': '67 MB', 'desc': 'Medical reference and treatment guide'},
                {'name': 'Water Treatment Guide', 'filename': 'zimgit-water_en_2024-08.zim',
                 'url': 'https://download.kiwix.org/zim/other/zimgit-water_en_2024-08.zim',
                 'size': '20 MB', 'desc': 'Water purification, treatment, and sourcing guide'},
                {'name': 'Food Preparation Guide', 'filename': 'zimgit-food-preparation_en_2025-04.zim',
                 'url': 'https://download.kiwix.org/zim/other/zimgit-food-preparation_en_2025-04.zim',
                 'size': '93 MB', 'desc': 'Food preparation, preservation, and safety guide'},
                {'name': 'Knots Guide', 'filename': 'zimgit-knots_en_2024-08.zim',
                 'url': 'https://download.kiwix.org/zim/other/zimgit-knots_en_2024-08.zim',
                 'size': '27 MB', 'desc': 'Knot tying guide with illustrations'},
                {'name': 'Survivors Guide', 'filename': 'survivors_en_all_maxi_2026-03.zim',
                 'url': 'https://download.kiwix.org/zim/other/survivors_en_all_maxi_2026-03.zim',
                 'size': '118 MB', 'desc': 'Survival skills and emergency preparedness content'},
                {'name': 'Appropedia (Sustainability Wiki)', 'filename': 'appropedia_en_all_maxi_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/other/appropedia_en_all_maxi_2026-02.zim',
                 'size': '555 MB', 'desc': 'Appropriate technology, DIY solutions, sustainable living'},
                {'name': 'Energypedia', 'filename': 'energypedia_en_all_maxi_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/other/energypedia_en_all_maxi_2025-12.zim',
                 'size': '762 MB', 'desc': 'Renewable energy, off-grid power, appropriate technology'},
                {'name': 'FEMA Ready.gov', 'filename': 'www.ready.gov_en_2024-12.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/www.ready.gov_en_2024-12.zim',
                 'size': '~2.3 GB', 'desc': 'FEMA disaster preparedness guides'},
                {'name': 'Survivor Library', 'filename': 'survivorlibrary.com_en_all_2026-03.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/survivorlibrary.com_en_all_2026-03.zim',
                 'size': '~2.7 GB', 'desc': 'Pre-industrial skills: blacksmithing, farming, medicine, crafts'},
                {'name': 'Wikibooks (Guides & Manuals)', 'filename': 'wikibooks_en_all_nopic_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikibooks/wikibooks_en_all_nopic_2026-01.zim',
                 'size': '~400 MB', 'desc': 'How-to guides, textbooks, field manuals'},
                {'name': 'Wikivoyage Travel Guide', 'filename': 'wikivoyage_en_all_nopic_2026-03.zim',
                 'url': 'https://download.kiwix.org/zim/wikivoyage/wikivoyage_en_all_nopic_2026-03.zim',
                 'size': '~600 MB', 'desc': 'Worldwide travel and survival information'},
                {'name': 'Outdoors SE', 'filename': 'outdoors.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/outdoors.stackexchange.com_en_all_2025-12.zim',
                 'size': '135 MB', 'desc': 'Wilderness and outdoors Q&A'},
                {'name': 'US Army Field Manuals', 'filename': 'armypubs_en_all_2024-12.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/armypubs_en_all_2024-12.zim',
                 'size': '~7.7 GB', 'desc': 'Complete US Army field manuals — survival, engineering, medical, comms'},
            ],
        },
    },
    {
        'category': 'Repair & How-To',
        'tiers': {
            'essential': [
                {'name': 'iFixit Repair Guides', 'filename': 'ifixit_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/ifixit/ifixit_en_all_2025-12.zim',
                 'size': '~2.5 GB', 'desc': '44,000+ repair guides with 456,000 images'},
            ],
            'standard': [
                {'name': 'iFixit Repair Guides', 'filename': 'ifixit_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/ifixit/ifixit_en_all_2025-12.zim',
                 'size': '~2.5 GB', 'desc': '44,000+ repair guides with 456,000 images'},
                {'name': 'DIY Home Improvement SE', 'filename': 'diy.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/diy.stackexchange.com_en_all_2025-12.zim',
                 'size': '~1.9 GB', 'desc': 'Home improvement and repair Q&A'},
                {'name': 'Cooking SE', 'filename': 'cooking.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/cooking.stackexchange.com_en_all_2025-12.zim',
                 'size': '225 MB', 'desc': 'Cooking and food preparation Q&A'},
            ],
            'comprehensive': [
                {'name': 'iFixit Repair Guides', 'filename': 'ifixit_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/ifixit/ifixit_en_all_2025-12.zim',
                 'size': '~2.5 GB', 'desc': '44,000+ repair guides with 456,000 images'},
                {'name': 'DIY Home Improvement SE', 'filename': 'diy.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/diy.stackexchange.com_en_all_2025-12.zim',
                 'size': '~1.9 GB', 'desc': 'Home improvement and repair Q&A'},
                {'name': 'Cooking SE', 'filename': 'cooking.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/cooking.stackexchange.com_en_all_2025-12.zim',
                 'size': '225 MB', 'desc': 'Cooking and food preparation Q&A'},
                {'name': 'Gardening SE', 'filename': 'gardening.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/gardening.stackexchange.com_en_all_2025-12.zim',
                 'size': '881 MB', 'desc': 'Gardening, landscaping, and plant care Q&A'},
                {'name': 'Cheatography', 'filename': 'cheatography.com_en_all_2025-07.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/cheatography.com_en_all_2025-07.zim',
                 'size': '~11 GB', 'desc': 'Thousands of cheat sheets on every topic'},
            ],
        },
    },
    {
        'category': 'Computing & Technology',
        'tiers': {
            'essential': [
                {'name': 'DevHints Cheat Sheets', 'filename': 'devhints.io_en_all_2026-03.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/devhints.io_en_all_2026-03.zim',
                 'size': '3.8 MB', 'desc': 'Quick-reference developer cheat sheets'},
            ],
            'standard': [
                {'name': 'Stack Overflow', 'filename': 'stackoverflow.com_en_all_2023-11.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/stackoverflow.com_en_all_2023-11.zim',
                 'size': '~55 GB', 'desc': 'Full Stack Overflow Q&A archive'},
                {'name': 'DevHints Cheat Sheets', 'filename': 'devhints.io_en_all_2026-03.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/devhints.io_en_all_2026-03.zim',
                 'size': '3.8 MB', 'desc': 'Quick-reference developer cheat sheets'},
                {'name': 'Super User', 'filename': 'superuser.com_en_all_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/superuser.com_en_all_2026-02.zim',
                 'size': '~5 GB', 'desc': 'Computer power user Q&A'},
            ],
            'comprehensive': [
                {'name': 'Stack Overflow', 'filename': 'stackoverflow.com_en_all_2023-11.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/stackoverflow.com_en_all_2023-11.zim',
                 'size': '~55 GB', 'desc': 'Full Stack Overflow Q&A archive'},
                {'name': 'DevHints Cheat Sheets', 'filename': 'devhints.io_en_all_2026-03.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/devhints.io_en_all_2026-03.zim',
                 'size': '3.8 MB', 'desc': 'Quick-reference developer cheat sheets'},
                {'name': 'Super User', 'filename': 'superuser.com_en_all_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/superuser.com_en_all_2026-02.zim',
                 'size': '~5 GB', 'desc': 'Computer power user Q&A'},
                {'name': 'Python Documentation', 'filename': 'docs.python.org_en_2025-09.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/docs.python.org_en_2025-09.zim',
                 'size': '~2.3 GB', 'desc': 'Python official documentation'},
                {'name': 'Server Fault', 'filename': 'serverfault.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/serverfault.com_en_all_2025-12.zim',
                 'size': '~4 GB', 'desc': 'System administration Q&A'},
            ],
        },
    },
    {
        'category': 'Science & Engineering',
        'tiers': {
            'essential': [
                {'name': 'PhET Simulations', 'filename': 'phet_en_all_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/phet/phet_en_all_2026-02.zim',
                 'size': '~500 MB', 'desc': '150+ interactive science simulations'},
            ],
            'standard': [
                {'name': 'PhET Simulations', 'filename': 'phet_en_all_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/phet/phet_en_all_2026-02.zim',
                 'size': '~500 MB', 'desc': '150+ interactive science simulations'},
                {'name': 'Physics SE', 'filename': 'physics.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/physics.stackexchange.com_en_all_2025-12.zim',
                 'size': '~1.7 GB', 'desc': 'Physics Q&A'},
                {'name': 'Biology SE', 'filename': 'biology.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/biology.stackexchange.com_en_all_2025-12.zim',
                 'size': '401 MB', 'desc': 'Biology Q&A'},
                {'name': 'Wiktionary', 'filename': 'wiktionary_en_all_nopic_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/wiktionary/wiktionary_en_all_nopic_2026-02.zim',
                 'size': '~5 GB', 'desc': 'Complete English dictionary'},
            ],
            'comprehensive': [
                {'name': 'PhET Simulations', 'filename': 'phet_en_all_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/phet/phet_en_all_2026-02.zim',
                 'size': '~500 MB', 'desc': '150+ interactive science simulations'},
                {'name': 'Physics SE', 'filename': 'physics.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/physics.stackexchange.com_en_all_2025-12.zim',
                 'size': '~1.7 GB', 'desc': 'Physics Q&A'},
                {'name': 'Chemistry SE', 'filename': 'chemistry.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/chemistry.stackexchange.com_en_all_2025-12.zim',
                 'size': '395 MB', 'desc': 'Chemistry Q&A'},
                {'name': 'Biology SE', 'filename': 'biology.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/biology.stackexchange.com_en_all_2025-12.zim',
                 'size': '401 MB', 'desc': 'Biology Q&A'},
                {'name': 'Mathematics SE', 'filename': 'math.stackexchange.com_en_all_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/math.stackexchange.com_en_all_2026-02.zim',
                 'size': '~8 GB', 'desc': 'Mathematics Q&A'},
                {'name': 'Engineering SE', 'filename': 'engineering.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/engineering.stackexchange.com_en_all_2025-12.zim',
                 'size': '241 MB', 'desc': 'Engineering Q&A'},
                {'name': 'Wiktionary', 'filename': 'wiktionary_en_all_nopic_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/wiktionary/wiktionary_en_all_nopic_2026-02.zim',
                 'size': '~5 GB', 'desc': 'Complete English dictionary'},
            ],
        },
    },
    {
        'category': 'Education',
        'tiers': {
            'essential': [
                {'name': 'GCFGlobal Digital Literacy', 'filename': 'edu.gcfglobal.org_en_all_2025-03.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/edu.gcfglobal.org_en_all_2025-03.zim',
                 'size': '515 MB', 'desc': 'Digital literacy, life skills, career training'},
            ],
            'standard': [
                {'name': 'GCFGlobal Digital Literacy', 'filename': 'edu.gcfglobal.org_en_all_2025-03.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/edu.gcfglobal.org_en_all_2025-03.zim',
                 'size': '515 MB', 'desc': 'Digital literacy, life skills, career training'},
                {'name': 'CrashCourse Videos', 'filename': 'crashcourse_en_all_2025-11.zim',
                 'url': 'https://download.kiwix.org/zim/other/crashcourse_en_all_2025-11.zim',
                 'size': '~21 GB', 'desc': 'CrashCourse educational video series'},
                {'name': 'Milne Open Textbooks', 'filename': 'milneopentextbooks.org_en_all_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/milneopentextbooks.org_en_all_2026-02.zim',
                 'size': '703 MB', 'desc': 'Free college textbooks'},
            ],
            'comprehensive': [
                {'name': 'Khan Academy (Full)', 'filename': 'khanacademy_en_all_2023-03.zim',
                 'url': 'https://download.kiwix.org/zim/other/khanacademy_en_all_2023-03.zim',
                 'size': '~168 GB', 'desc': 'Complete Khan Academy with videos'},
                {'name': 'CrashCourse Videos', 'filename': 'crashcourse_en_all_2025-11.zim',
                 'url': 'https://download.kiwix.org/zim/other/crashcourse_en_all_2025-11.zim',
                 'size': '~21 GB', 'desc': 'CrashCourse educational video series'},
                {'name': 'GCFGlobal Digital Literacy', 'filename': 'edu.gcfglobal.org_en_all_2025-03.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/edu.gcfglobal.org_en_all_2025-03.zim',
                 'size': '515 MB', 'desc': 'Digital literacy, life skills, career training'},
                {'name': 'Milne Open Textbooks', 'filename': 'milneopentextbooks.org_en_all_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/milneopentextbooks.org_en_all_2026-02.zim',
                 'size': '703 MB', 'desc': 'Free college textbooks'},
                {'name': 'Wikiversity', 'filename': 'wikiversity_en_all_nopic_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/wikiversity/wikiversity_en_all_nopic_2026-02.zim',
                 'size': '~500 MB', 'desc': 'University-level learning resources'},
            ],
        },
    },
    {
        'category': 'Books & Literature',
        'tiers': {
            'essential': [
                {'name': 'Project Gutenberg (Top)', 'filename': 'gutenberg_en_all_2025-11.zim',
                 'url': 'https://download.kiwix.org/zim/gutenberg/gutenberg_en_all_2025-11.zim',
                 'size': '~2 GB', 'desc': 'Most popular free eBooks'},
            ],
            'standard': [
                {'name': 'Project Gutenberg (All)', 'filename': 'gutenberg_en_all_2025-11.zim',
                 'url': 'https://download.kiwix.org/zim/gutenberg/gutenberg_en_all_2025-11.zim',
                 'size': '~60 GB', 'desc': '78,000+ free eBooks'},
                {'name': 'Wikiquote', 'filename': 'wikiquote_en_all_nopic_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikiquote/wikiquote_en_all_nopic_2026-01.zim',
                 'size': '~200 MB', 'desc': 'Quotation collection'},
            ],
            'comprehensive': [
                {'name': 'Project Gutenberg (All)', 'filename': 'gutenberg_en_all_2025-11.zim',
                 'url': 'https://download.kiwix.org/zim/gutenberg/gutenberg_en_all_2025-11.zim',
                 'size': '~60 GB', 'desc': '78,000+ free eBooks'},
                {'name': 'Wikiquote', 'filename': 'wikiquote_en_all_nopic_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikiquote/wikiquote_en_all_nopic_2026-01.zim',
                 'size': '~200 MB', 'desc': 'Quotation collection'},
                {'name': 'Wikisource', 'filename': 'wikisource_en_all_nopic_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/wikisource/wikisource_en_all_nopic_2026-02.zim',
                 'size': '~4 GB', 'desc': 'Free source texts and documents'},
            ],
        },
    },
    {
        'category': 'Ham Radio & Communications',
        'tiers': {
            'essential': [
                {'name': 'Ham Radio SE', 'filename': 'ham.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/ham.stackexchange.com_en_all_2025-12.zim',
                 'size': '72 MB', 'desc': 'Amateur radio Q&A'},
            ],
            'standard': [
                {'name': 'Ham Radio SE', 'filename': 'ham.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/ham.stackexchange.com_en_all_2025-12.zim',
                 'size': '72 MB', 'desc': 'Amateur radio Q&A'},
                {'name': 'Electronics SE', 'filename': 'electronics.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/electronics.stackexchange.com_en_all_2025-12.zim',
                 'size': '~2 GB', 'desc': 'Electronics design and repair Q&A'},
            ],
            'comprehensive': [
                {'name': 'Ham Radio SE', 'filename': 'ham.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/ham.stackexchange.com_en_all_2025-12.zim',
                 'size': '72 MB', 'desc': 'Amateur radio Q&A'},
                {'name': 'Electronics SE', 'filename': 'electronics.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/electronics.stackexchange.com_en_all_2025-12.zim',
                 'size': '~2 GB', 'desc': 'Electronics design and repair Q&A'},
                {'name': 'Signal Processing SE', 'filename': 'dsp.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/dsp.stackexchange.com_en_all_2025-12.zim',
                 'size': '~300 MB', 'desc': 'Signal processing Q&A'},
            ],
        },
    },
    {
        'category': 'TED Talks & Videos',
        'tiers': {
            'essential': [
                {'name': 'TED Talks (Science)', 'filename': 'ted_mul_science_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/ted/ted_mul_science_2026-02.zim',
                 'size': '~3 GB', 'desc': 'TED science talks'},
            ],
            'standard': [
                {'name': 'TED Talks (Technology)', 'filename': 'ted_mul_technology_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/ted/ted_mul_technology_2026-01.zim',
                 'size': '~20 GB', 'desc': 'TED technology talks'},
            ],
            'comprehensive': [
                {'name': 'TED Talks (All 6,658)', 'filename': 'ted_mul_all_2025-08.zim',
                 'url': 'https://download.kiwix.org/zim/ted/ted_mul_all_2025-08.zim',
                 'size': '~80 GB', 'desc': 'All TED talks (multilingual)'},
            ],
        },
    },
    {
        'category': 'Reference & Dictionaries',
        'tiers': {
            'essential': [
                {'name': 'Wiktionary', 'filename': 'wiktionary_en_all_nopic_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/wiktionary/wiktionary_en_all_nopic_2026-02.zim',
                 'size': '~5 GB', 'desc': 'Complete English dictionary and thesaurus'},
            ],
            'standard': [
                {'name': 'Wiktionary', 'filename': 'wiktionary_en_all_nopic_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/wiktionary/wiktionary_en_all_nopic_2026-02.zim',
                 'size': '~5 GB', 'desc': 'Complete English dictionary and thesaurus'},
                {'name': 'Wikiquote', 'filename': 'wikiquote_en_all_nopic_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikiquote/wikiquote_en_all_nopic_2026-01.zim',
                 'size': '~200 MB', 'desc': 'Quotation collection'},
                {'name': 'Cheatography', 'filename': 'cheatography.com_en_all_2025-07.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/cheatography.com_en_all_2025-07.zim',
                 'size': '~11 GB', 'desc': 'Thousands of cheat sheets on every topic'},
            ],
            'comprehensive': [
                {'name': 'Wiktionary', 'filename': 'wiktionary_en_all_nopic_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/wiktionary/wiktionary_en_all_nopic_2026-02.zim',
                 'size': '~5 GB', 'desc': 'Complete English dictionary and thesaurus'},
                {'name': 'Wikiquote', 'filename': 'wikiquote_en_all_nopic_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikiquote/wikiquote_en_all_nopic_2026-01.zim',
                 'size': '~200 MB', 'desc': 'Quotation collection'},
                {'name': 'Cheatography', 'filename': 'cheatography.com_en_all_2025-07.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/cheatography.com_en_all_2025-07.zim',
                 'size': '~11 GB', 'desc': 'Thousands of cheat sheets on every topic'},
                {'name': 'Wikinews', 'filename': 'wikinews_en_all_nopic_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikinews/wikinews_en_all_nopic_2026-01.zim',
                 'size': '~200 MB', 'desc': 'Free news content archive'},
            ],
        },
    },
    {
        'category': 'Homesteading & Agriculture',
        'tiers': {
            'essential': [
                {'name': 'Gardening SE', 'filename': 'gardening.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/gardening.stackexchange.com_en_all_2025-12.zim',
                 'size': '881 MB', 'desc': 'Gardening, landscaping, and plant care Q&A'},
            ],
            'standard': [
                {'name': 'Gardening SE', 'filename': 'gardening.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/gardening.stackexchange.com_en_all_2025-12.zim',
                 'size': '881 MB', 'desc': 'Gardening, landscaping, and plant care Q&A'},
                {'name': 'Cooking SE', 'filename': 'cooking.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/cooking.stackexchange.com_en_all_2025-12.zim',
                 'size': '225 MB', 'desc': 'Cooking and food preservation Q&A'},
                {'name': 'Sustainability SE', 'filename': 'sustainability.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/sustainability.stackexchange.com_en_all_2025-12.zim',
                 'size': '~50 MB', 'desc': 'Sustainable living Q&A'},
            ],
            'comprehensive': [
                {'name': 'Gardening SE', 'filename': 'gardening.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/gardening.stackexchange.com_en_all_2025-12.zim',
                 'size': '881 MB', 'desc': 'Gardening, landscaping, and plant care Q&A'},
                {'name': 'Cooking SE', 'filename': 'cooking.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/cooking.stackexchange.com_en_all_2025-12.zim',
                 'size': '225 MB', 'desc': 'Cooking and food preservation Q&A'},
                {'name': 'Sustainability SE', 'filename': 'sustainability.stackexchange.com_en_all_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/sustainability.stackexchange.com_en_all_2025-12.zim',
                 'size': '~50 MB', 'desc': 'Sustainable living Q&A'},
                {'name': 'Survivor Library', 'filename': 'survivorlibrary.com_en_all_2026-03.zim',
                 'url': 'https://download.kiwix.org/zim/zimit/survivorlibrary.com_en_all_2026-03.zim',
                 'size': '~2.7 GB', 'desc': 'Pre-industrial agriculture, animal husbandry, food preservation'},
            ],
        },
    },
    {
        'category': 'Multi-Language',
        'tiers': {
            'essential': [
                {'name': 'Wikipedia Espanol (Top)', 'filename': 'wikipedia_es_top_maxi_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_es_top_maxi_2026-01.zim',
                 'size': '~5 GB', 'desc': 'Spanish Wikipedia — top articles with images'},
                {'name': 'Wikipedia Francais (Top)', 'filename': 'wikipedia_fr_top_maxi_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_fr_top_maxi_2026-01.zim',
                 'size': '~5 GB', 'desc': 'French Wikipedia — top articles with images'},
            ],
            'standard': [
                {'name': 'Wikipedia Espanol (Top)', 'filename': 'wikipedia_es_top_maxi_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_es_top_maxi_2026-01.zim',
                 'size': '~5 GB', 'desc': 'Spanish Wikipedia — top articles with images'},
                {'name': 'Wikipedia Francais (Top)', 'filename': 'wikipedia_fr_top_maxi_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_fr_top_maxi_2026-01.zim',
                 'size': '~5 GB', 'desc': 'French Wikipedia — top articles with images'},
                {'name': 'Wikipedia Deutsch (Top)', 'filename': 'wikipedia_de_top_maxi_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_de_top_maxi_2026-01.zim',
                 'size': '~6 GB', 'desc': 'German Wikipedia — top articles with images'},
                {'name': 'Wiktionary Espanol', 'filename': 'wiktionary_es_all_nopic_2025-12.zim',
                 'url': 'https://download.kiwix.org/zim/wiktionary/wiktionary_es_all_nopic_2025-12.zim',
                 'size': '~1 GB', 'desc': 'Spanish dictionary'},
            ],
            'comprehensive': [
                {'name': 'Wikipedia Espanol (Full)', 'filename': 'wikipedia_es_all_maxi_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_es_all_maxi_2026-02.zim',
                 'size': '~30 GB', 'desc': 'Complete Spanish Wikipedia'},
                {'name': 'Wikipedia Francais (Full)', 'filename': 'wikipedia_fr_all_maxi_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_fr_all_maxi_2026-02.zim',
                 'size': '~40 GB', 'desc': 'Complete French Wikipedia'},
                {'name': 'Wikipedia Deutsch (Full)', 'filename': 'wikipedia_de_all_maxi_2026-01.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_de_all_maxi_2026-01.zim',
                 'size': '~45 GB', 'desc': 'Complete German Wikipedia'},
                {'name': 'Wikipedia Portugues (Full)', 'filename': 'wikipedia_pt_all_maxi_2026-02.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_pt_all_maxi_2026-02.zim',
                 'size': '~15 GB', 'desc': 'Complete Portuguese Wikipedia'},
            ],
        },
    },
]


def get_content_tiers():
    """Return content tier definitions derived from ZIM_CATALOG for the wizard."""
    tiers = {
        'essential': {'name': 'Essential', 'desc': 'Core survival knowledge — medical, preparedness, repair guides',
                      'services': ['ollama', 'kiwix', 'cyberchef', 'stirling'], 'zims': [], 'models': ['qwen3:4b'],
                      'est_size': '~10 GB'},
        'standard': {'name': 'Standard', 'desc': 'Comprehensive offline library — Wikipedia, Stack Overflow, education',
                     'services': ['ollama', 'kiwix', 'cyberchef', 'kolibri', 'qdrant', 'stirling'], 'zims': [], 'models': ['qwen3:4b'],
                     'est_size': '~80 GB'},
        'maximum': {'name': 'Maximum', 'desc': 'Download EVERYTHING — complete archives, all references, all models',
                    'services': ['ollama', 'kiwix', 'cyberchef', 'kolibri', 'qdrant', 'stirling'], 'zims': [],
                    'models': ['qwen3:4b', 'qwen3:8b', 'alibayram/medgemma', 'deepseek-r1:8b'],
                    'est_size': '~500+ GB'},
    }

    for cat in ZIM_CATALOG:
        for tier_name, tier_items in cat.get('tiers', {}).items():
            for item in tier_items:
                entry = {'url': item['url'], 'filename': item['filename'], 'name': item['name'],
                         'size': item['size'], 'desc': item.get('desc', ''), 'category': cat['category']}
                if tier_name == 'essential':
                    tiers['essential']['zims'].append(entry)
                    tiers['standard']['zims'].append(entry)
                    tiers['maximum']['zims'].append(entry)
                elif tier_name == 'standard':
                    tiers['standard']['zims'].append(entry)
                    tiers['maximum']['zims'].append(entry)
                elif tier_name == 'comprehensive':
                    tiers['maximum']['zims'].append(entry)

    # Deduplicate zims by filename, and remove nopic when maxi exists for same content
    for tier in tiers.values():
        seen = set()
        deduped = []
        for z in tier['zims']:
            if z['filename'] not in seen:
                seen.add(z['filename'])
                deduped.append(z)
        # Smart dedup: if "all_maxi" exists, remove "all_nopic" and "all_mini" and "top_*" for same language
        # If "top_maxi" exists, remove "top_nopic" for same language
        import re as _re
        maxi_bases = set()
        for z in deduped:
            m = _re.match(r'(wikipedia_\w+)_all_maxi', z['filename'])
            if m:
                maxi_bases.add(m.group(1))
            m = _re.match(r'(wikipedia_\w+)_top_maxi', z['filename'])
            if m:
                maxi_bases.add(m.group(1) + '_top')
        if maxi_bases:
            filtered = []
            for z in deduped:
                fn = z['filename']
                # Skip nopic/mini if maxi of same scope exists
                skip = False
                for base in maxi_bases:
                    if base.endswith('_top'):
                        lang = base[:-4]
                        if fn.startswith(lang + '_top_nopic'):
                            skip = True
                    else:
                        if fn.startswith(base + '_all_nopic') or fn.startswith(base + '_all_mini') or fn.startswith(base + '_top_'):
                            skip = True
                if not skip:
                    filtered.append(z)
            deduped = filtered
        tier['zims'] = deduped
        tier['zim_count'] = len(deduped)

    return tiers


def get_install_dir():
    return os.path.join(get_services_dir(), 'kiwix')


def get_library_dir():
    path = os.path.join(get_install_dir(), 'library')
    os.makedirs(path, exist_ok=True)
    return path


def get_exe_path():
    """Find kiwix-serve executable (may be in a subdirectory after extraction)."""
    from platform_utils import exe_name
    binary = exe_name('kiwix-serve')
    install_dir = get_install_dir()
    exe = os.path.join(install_dir, binary)
    if os.path.isfile(exe):
        return exe
    for root, dirs, files in os.walk(install_dir):
        if binary in files:
            return os.path.join(root, binary)
    return exe


def is_installed():
    return os.path.isfile(get_exe_path())


def install(callback=None):
    """Download and install kiwix-tools."""
    install_dir = get_install_dir()
    os.makedirs(install_dir, exist_ok=True)
    from platform_utils import IS_WINDOWS, extract_archive, make_executable
    arc_ext = '.zip' if IS_WINDOWS else '.tar.gz'
    arc_path = os.path.join(install_dir, 'kiwix-tools' + arc_ext)

    _download_progress[SERVICE_ID] = {
        'percent': 0, 'status': 'downloading kiwix-tools', 'error': None,
        'speed': '', 'downloaded': 0, 'total': 0,
    }

    try:
        download_file(_get_kiwix_url(), arc_path, SERVICE_ID)

        _download_progress[SERVICE_ID]['status'] = 'extracting'
        extract_archive(arc_path, install_dir)
        make_executable(get_exe_path())

        db = get_db()
        try:
            db.execute('''
                INSERT OR REPLACE INTO services (id, name, description, icon, category, installed, port, install_path, exe_path, url)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            ''', (
                SERVICE_ID, 'Kiwix (Information Library)',
                'Offline Wikipedia, medical references, survival guides, and ebooks',
                'book', 'knowledge', KIWIX_PORT, install_dir, get_exe_path(),
                f'http://localhost:{KIWIX_PORT}'
            ))
            db.commit()
        finally:
            db.close()

        _download_progress[SERVICE_ID] = {
            'percent': 100, 'status': 'complete', 'error': None,
            'speed': '', 'downloaded': 0, 'total': 0,
        }
        log.info('Kiwix installed successfully')

    except Exception as e:
        _download_progress[SERVICE_ID] = {
            'percent': 0, 'status': 'error', 'error': str(e),
            'speed': '', 'downloaded': 0, 'total': 0,
        }
        log.error(f'Kiwix install failed: {e}')
        raise


def list_zim_files():
    """List available ZIM files in the library directory."""
    library_dir = get_library_dir()
    zims = []
    for f in os.listdir(library_dir):
        if f.endswith('.zim'):
            path = os.path.join(library_dir, f)
            try:
                zims.append({
                    'filename': f,
                    'path': path,
                    'size_mb': round(os.path.getsize(path) / (1024 * 1024), 1),
                })
            except OSError:
                pass  # Broken symlink or file deleted between listdir and getsize
    return zims


def get_catalog():
    """Return the curated ZIM catalog."""
    return ZIM_CATALOG


def get_catalog_flat():
    """Return a flat list of all ZIM items across all tiers (for backward compat)."""
    items = []
    seen = set()
    for cat in ZIM_CATALOG:
        for tier_name, tier_items in cat.get('tiers', {}).items():
            for item in tier_items:
                if item['filename'] not in seen:
                    seen.add(item['filename'])
                    items.append({**item, 'category': cat['category'], 'tier': tier_name})
    return items


def download_zim(url: str, filename: str = None):
    """Download a ZIM file to the library directory."""
    if not url.startswith(('http://', 'https://')):
        raise ValueError('Only HTTP/HTTPS URLs are supported')
    if not filename:
        filename = url.split('/')[-1]
    # Sanitize filename to prevent path traversal
    filename = os.path.basename(filename)
    if not filename or '..' in filename:
        raise ValueError(f'Invalid ZIM filename: {filename}')
    lib_dir = os.path.abspath(get_library_dir())
    dest = os.path.abspath(os.path.join(lib_dir, filename))
    if not dest.startswith(lib_dir + os.sep):
        raise ValueError(f'Path traversal detected in filename: {filename}')
    download_file(url, dest, f'kiwix-zim-{filename}')
    return dest


def delete_zim(filename: str) -> bool:
    """Delete a ZIM file from the library."""
    if not filename or '..' in filename or '/' in filename or '\\' in filename:
        log.warning(f'Rejected ZIM delete with unsafe filename: {filename}')
        return False
    lib_dir = os.path.abspath(get_library_dir())
    path = os.path.abspath(os.path.join(lib_dir, filename))
    if not path.startswith(lib_dir + os.sep):
        log.warning(f'Rejected ZIM delete with path traversal: {path}')
        return False
    try:
        if os.path.isfile(path):
            os.remove(path)
            return True
    except Exception as e:
        log.error(f'Failed to delete ZIM {filename}: {e}')
    return False


def start():
    """Start kiwix-serve with all ZIM files in the library."""
    if not is_installed():
        raise RuntimeError('Kiwix is not installed')

    zims = list_zim_files()
    zim_paths = [z['path'] for z in zims]

    if not zim_paths:
        log.warning('No ZIM files found — kiwix-serve needs content to run. Download a ZIM from the Library tab first.')
        raise RuntimeError('No content downloaded yet — add content from the Library tab before starting Kiwix')

    from config import Config
    args = ['--port', str(KIWIX_PORT), '--address', Config.APP_HOST] + zim_paths
    exe = get_exe_path()

    from platform_utils import popen_kwargs
    proc = subprocess.Popen(
        [exe] + args,
        **popen_kwargs(cwd=os.path.dirname(exe)),
    )

    from services.manager import register_process, unregister_process
    register_process(SERVICE_ID, proc)

    db = get_db()
    try:
        db.execute('UPDATE services SET running = 1, pid = ? WHERE id = ?', (proc.pid, SERVICE_ID))
        db.commit()
    except Exception as e:
        log.error(f'DB update failed for {SERVICE_ID}: {e} — killing orphaned process')
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        unregister_process(SERVICE_ID)
        raise
    finally:
        db.close()

    for _ in range(15):
        if check_port(KIWIX_PORT):
            log.info(f'Kiwix running on port {KIWIX_PORT} (PID {proc.pid})')
            return proc.pid
        time.sleep(1)

    log.warning('Kiwix started but port %d not yet responding (PID %d)', KIWIX_PORT, proc.pid)
    return proc.pid


def stop():
    return stop_process(SERVICE_ID)


def running():
    return is_running(SERVICE_ID) and check_port(KIWIX_PORT)
