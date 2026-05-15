# VM-tipset 2026

En privat webbaserad MVP för gruppspelstips under VM 2026.

## MVP-scope

- Deltagare får privata länkar
- Deltagare tippar 1/X/2 och över/under 2,5 mål
- Tips kan ändras fram till deadline
- Admin kan lägga in matcher och resultat
- Poängtabell räknas automatiskt

## Teknik

- Python
- Streamlit
- Supabase/Postgres
- GitHub

---

## Launch-checklista

Denna checklista används innan VM-tipset skickas ut till riktiga deltagare.

### 1. Kontrollera deployad app

Öppna den deployade Streamlit-appen och kontrollera adminöversikten.

Launch-checklistan i admin bör visa:

- 72 matcher finns i databasen
- Deadline är satt
- Deadline ligger i framtiden
- Base URL pekar på deployad Streamlit-app
- Inga testresultat finns
- Alla riktiga deltagare har privata länkar

Lokalt kan `base_url` visa `localhost`, men i den deployade appen ska den peka på Streamlit-appen.

---

### 2. Rensa testdata

Kör detta i Supabase SQL Editor innan riktiga deltagare skapas.

```sql
delete from public.predictions;
delete from public.participants;

update public.matches
set
    home_goals = null,
    away_goals = null,
    status = 'scheduled';
```

Detta gör:

- tar bort alla testtips
- tar bort alla testdeltagare
- rensar alla testresultat
- behåller matcherna
- behåller app settings, till exempel deadline

Viktigt: kör inte detta efter att riktiga deltagare har börjat lägga tips.

---

### 3. Kontrollera matcher

Efter rensning, kontrollera att matcherna fortfarande finns kvar.

I admin:

- öppna fliken `Matcher`
- kontrollera att det finns 72 matcher
- kontrollera att tider visas i svensk tid
- kontrollera att lagen och grupperna ser rimliga ut

Om matcher behöver importeras igen, använd CSV-importen i admin.

---

### 4. Sätt riktig deadline

I adminöversikten:

- sätt deadline till korrekt datum och tid
- kontrollera att deadline ligger i framtiden
- kontrollera från en deltagarlänk att tipsen är öppna

Rekommenderat exempel:

```text
10 juni 2026, 20:00 svensk tid
```

Det exakta valet beror på när du vill låsa tävlingen.

---

### 5. Skapa riktiga deltagare

Skapa riktiga deltagare från den deployade admin-sidan.

Viktigt: skapa eller kopiera länkar från deployad app, inte från lokal app.

Varje deltagare får en privat länk i formatet:

```text
https://din-app.streamlit.app?token=...
```

---

### 6. Exportera deltagarlänkar

I admin:

- öppna `Deltagare & länkar`
- kontrollera att alla deltagare har sparad länk
- ladda ner CSV med deltagarlänkar
- skicka rätt länk till rätt person

Deltagarlänkar kan skickas via valfri kanal, till exempel Messenger, Discord, SMS eller liknande.

---

### 7. Gör sista testet

Skapa gärna en sista testdeltagare innan riktiga länkar skickas.

Testa:

- öppna länken på mobil
- lägg några tips
- spara
- ladda om sidan
- kontrollera att tipsen ligger kvar
- kontrollera att deltagarstatus i admin uppdateras

Ta sedan bort testdeltagaren innan riktiga länkar skickas, eller kör cleanup igen.

---

### 8. När länkar är skickade

Efter att riktiga deltagare fått sina länkar:

- ändra inte matchlistan om det inte är absolut nödvändigt
- kör inte breda delete-kommandon i Supabase
- kontrollera deltagarstatus inför deadline
- påminn deltagare som inte är klara

Admin kan fortfarande:

- justera deadline om det behövs
- lägga till nya deltagare
- exportera deltagarstatus
- fylla i resultat efter matcher

---

## Under turneringen

När matcher spelas:

1. Gå till admin.
2. Öppna fliken `Resultat`.
3. Välj match.
4. Fyll i resultat.
5. Kontrollera poängtabellen.
6. Exportera backup vid behov.

Poäng räknas automatiskt:

- 1 poäng för rätt 1/X/2
- 1 poäng för rätt över/under 2,5 mål

---

## Backup

Admin kan exportera CSV-filer från fliken `Export`.

Rekommenderade exporter under turneringen:

- matcher och resultat
- poängtabell
- deltagarstatus

Export av alla tips är låst fram till deadline.