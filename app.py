# app.py
#
# Entry point för VM-tipset 2026.
#
# Den här filen ska vara tunn:
# - sätta Streamlit-konfiguration
# - läsa URL-parametrar
# - skicka användaren till rätt vy
#
# Den faktiska UI-logiken ligger i src/ui/.

import streamlit as st

from src.ui.admin_page import render_admin_page
from src.ui.common import get_query_param
from src.ui.participant_page import render_participant_page
from src.ui.start_page import (
    render_dev_match_preview,
    render_start_page,
)


# ------------------------------------------------------------
# Sidinställningar
# ------------------------------------------------------------

st.set_page_config(
    page_title="VM-tipset 2026",
    page_icon="⚽",
    layout="centered",
)


# ------------------------------------------------------------
# Routing
# ------------------------------------------------------------
#
# Stödda URL-lägen:
#
# 1. Admin:
#       ?admin=1
#
# 2. Deltagare:
#       ?token=...
#
# 3. Startsida:
#       ingen query parameter
#
# Exempel lokalt:
#       http://localhost:8501?admin=1
#       http://localhost:8501?token=abc123
#
# Exempel deployad app:
#       https://din-app.streamlit.app?token=abc123
#

admin_mode = get_query_param("admin")
participant_token = get_query_param("token")

if admin_mode == "1":
    render_admin_page()

elif participant_token:
    render_participant_page(participant_token)

else:
    render_start_page()
    render_dev_match_preview()