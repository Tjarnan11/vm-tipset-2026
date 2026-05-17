# src/ui/rules.py
#
# Regelflik för deltagare.

import streamlit as st

from src.deadline import format_deadline_swedish
from src.repositories.settings_repo import get_group_stage_deadline


def render_rules_section() -> None:
    """
    Visar reglerna för VM-tipset.

    Den här sektionen är publik för deltagaren och kan visas både före
    och efter deadline.
    """

    deadline_value = get_group_stage_deadline()

    st.header("Regler")

    st.info(
        "Du tippar alla gruppspelsmatcher i VM 2026. "
        "För varje match gör du två val: matchens 1/X/2-resultat och "
        "om matchen går över eller under 2,5 mål."
    )

    st.subheader("Deadline")

    st.warning(
        "Du kan ändra dina tips fram till deadline. "
        "Efter deadline låses tipsen och kan inte längre ändras."
    )

    st.markdown(
        f"""
        **Nuvarande deadline:**

        `{format_deadline_swedish(deadline_value)} svensk tid`
        """
    )

    st.subheader("Vad ska du tippa?")

    st.markdown(
        """
        För varje gruppspelsmatch tippar du två saker:

        **1. 1/X/2**

        - `1` = första laget i matchen vinner
        - `X` = matchen slutar oavgjort
        - `2` = andra laget i matchen vinner

        Exempel:

        Om matchen är **Tyskland – Skottland**:

        - Tyskland vinner = `1`
        - Matchen slutar oavgjort = `X`
        - Skottland vinner = `2`

        **2. Över/under 2,5 mål**

        Detta gäller det totala antalet mål i matchen, alltså båda lagens mål tillsammans.

        - **Över 2,5 mål** = matchen får 3 mål eller fler
        - **Under 2,5 mål** = matchen får 0, 1 eller 2 mål

        Exempel:

        - 3–1 = 4 mål totalt = **Över 2,5 mål**
        - 1–0 = 1 mål totalt = **Under 2,5 mål**
        - 1–1 = 2 mål totalt = **Under 2,5 mål**
        """
    )

    st.subheader("Poäng")

    st.markdown(
        """
        Du kan få max **2 poäng per match**:

        - **1 poäng** för rätt 1/X/2
        - **1 poäng** för rätt över/under 2,5 mål

        Det betyder att du kan få poäng för över/under även om du har fel på 1/X/2, och tvärtom.

        Eftersom gruppspelet har **72 matcher** finns det totalt:

        **72 × 2 = 144 möjliga poäng**
        """
    )

    st.subheader("Exempel på poäng")

    st.markdown(
        """
        Om matchen **Tyskland – Skottland** slutar **2–1** är rätt rad:

        - 1/X/2: `1`
        - Över/under: **Över 2,5 mål**

        Exempel på poäng:

        - Du tippade `1` + **Över 2,5 mål** → **2 poäng**
        - Du tippade `X` + **Över 2,5 mål** → **1 poäng**
        - Du tippade `1` + **Under 2,5 mål** → **1 poäng**
        - Du tippade `2` + **Under 2,5 mål** → **0 poäng**
        """
    )

    st.subheader("Efter deadline")

    st.markdown(
        """
        När deadline har passerat:

        - dina tips låses
        - poängtabellen visas
        - allas tips blir synliga
        - du kan se resultat och poäng per match
        - admin kan börja fylla i matchresultat
        """
    )

    st.subheader("Utslagsfråga")

    st.markdown(
        """
        Som utslagsfråga väljer du en spelare som du tror gör flest mål i gruppspelet.

        Utslagsfrågan ger inga extra poäng.

        Den används bara om flera deltagare hamnar på samma totalpoäng.
        Då hamnar den deltagare vars valda spelare gjort flest gruppspelsmål före.
        """
    )

    st.subheader("Poängtabell och sortering")

    st.markdown(
        """
        Poängtabellen sorteras så här:

        1. Totalpoäng
        2. Flest mål av vald utslagsfråga-spelare
        3. Flest rätt 1/X/2
        4. Delad placering om deltagarna fortfarande är lika

        Om deltagare fortfarande är lika efter dessa steg får de samma placering.
        """
    )

    st.subheader("Prispott")

    st.markdown(
        """
        Om tävlingen spelas med insats gäller följande princip:

        - Om en deltagare är ensam 1:a får vinnaren prispotten minus en insats.
        - Den som är ensam 2:a får tillbaka en insats.
        - Om flera deltagare delar 1:a plats delar de på hela prispotten.
        - Om en deltagare är ensam 1:a men flera deltagare delar 2:a plats, delar 2:orna på en insats.

        Exempel:

        Om 10 deltagare betalar 100 kr var är prispotten 1000 kr.

        - Ensam 1:a och ensam 2:a
            - 1:a får 900 kr
            - 2:a får 100 kr
            

        - Två deltagare delar 1:a
            -  de delar på hela prispotten, 500 kr var
            - ingen separat 2:a-pris delas ut


        - Ensam 1:a och två deltagare delar 2:a
            - 1:a får 900 kr
            - 2:orna får 50 kr var
        """
    )

    st.subheader("Admin och rättvisa")

    st.markdown(
        """
        Admin sköter deltagare, deadline och resultat.

        Appen är byggd så att deltagarnas tips inte visas för andra deltagare före deadline.
        Export av alla tips är också låst fram till deadline.

        Efter deadline kan alla deltagare se varandras tips.
        """
    )
