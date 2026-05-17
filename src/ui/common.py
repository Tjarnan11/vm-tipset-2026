# src/ui/common.py
#
# Gemensamma små UI-/routing-hjälpare.

import streamlit as st

def get_query_param(name: str) -> str | None:
    """
    Hämtar en query-parameter från URL:en.

    Exempel:
        http://localhost:8501?token=abc123

    Då ger:
        get_query_param("token")

    värdet:
        "abc123"

    st.query_params är Streamlits sätt att läsa URL-parametrar.
    """

    value = st.query_params.get(name)

    if value is None:
        return None

    return str(value)