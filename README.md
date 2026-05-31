# VM-tipset 2026

En privat webbaserad app för VM-tipset 2026.

Appen är byggd som ett kompisprojekt där deltagare får privata länkar, lägger sina tips via mobil/webb och där admin kan hantera matcher, resultat, deadlines och poängtabeller.

## Nuvarande scope

### Gruppspel

Gruppspelstipset är den första färdiga tävlingsdelen.

- Deltagare får privata länkar
- Deltagare tippar 1/X/2 och över/under 2,5 mål för alla gruppspelsmatcher
- Deltagare väljer även en utslagsfråga: skyttekung i gruppspelet
- Tips kan ändras fram till deadline
- Efter deadline låses tipsen
- Efter deadline kan deltagare se allas tips
- Admin kan importera matcher via CSV
- Admin kan lägga in matchresultat
- Poängtabell räknas automatiskt
- Gruppställningar räknas automatiskt
- Admin kan exportera data som CSV
- Appen har launch-checklista inför riktig användning

### Slutspel

Slutspelstipset är planerat som en separat tävlingsdel i samma app.

Planerat upplägg:

- Separat poängtabell för slutspelet
- Deadlines per slutspelsrunda
- Admin lägger in faktiska slutspelsmatcher manuellt
- Deltagare tippar match för match när rundor öppnar
- Tips kan inkludera exakt resultat, över/under 2,5 mål och första målskytt
- Finalister och finalvinnare kan tippas före slutspelet
- Poänglogik och UI byggs i senare steg

Design finns i:

```text
docs/knockout_design.md
```

## Teknik

- Python
- Streamlit
- Supabase/Postgres
- GitHub
- pytest

## Launch-checklista

Denna checklista används innan VM-tipset skickas ut till riktiga deltagare.

Rekommenderat arbetssätt:

1. Kör först en generalrepetition med testdeltagare.
2. Kontrollera att cleanup, länkar, sparning och adminstatus fungerar.
3. Kör cleanup igen.
4. Skapa riktiga deltagare.
5. Skicka riktiga länkar.

Viktigt: kör inte cleanup efter att riktiga deltagare har börjat lägga tips.

---

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

### 2. Rensa gruppspels-testdata

Kör detta i Supabase SQL Editor innan riktiga deltagare skapas.

```sql
delete from public.predictions;
delete from public.bonus_predictions;
delete from public.bonus_scorer_results;
delete from public.participants;

update public.matches
set
    home_goals = null,
    away_goals = null,
    status = 'scheduled';
```

Detta gör:

- tar bort alla gruppspelstips
- tar bort alla gruppspels-bonusval
- tar bort gamla bonusmål för utslagsfrågan
- tar bort alla testdeltagare
- rensar alla gruppspelsresultat
- behåller gruppspelsmatcherna
- behåller app settings, till exempel deadline

Viktigt: kör inte detta efter att riktiga deltagare har börjat lägga tips.

---

### 3. Kontrollera databasen efter cleanup

Kör dessa kontroller i Supabase SQL Editor:

```sql
select count(*) as predictions_count from public.predictions;
select count(*) as bonus_predictions_count from public.bonus_predictions;
select count(*) as bonus_scorer_results_count from public.bonus_scorer_results;
select count(*) as participants_count from public.participants;
```

Efter cleanup bör alla dessa vara `0`.

Kontrollera sedan att matcherna finns kvar:

```sql
select count(*) as matches_count
from public.matches;
```

Det ska vara `72`.

Kontrollera också att inga resultat finns kvar:

```sql
select count(*) as finished_matches_count
from public.matches
where status = 'finished'
   or home_goals is not null
   or away_goals is not null;
```

Det ska vara `0`.

---

### 4. Kontrollera matcher

Efter rensning, kontrollera att matcherna fortfarande finns kvar.

I admin:

- öppna `Matcher`
- kontrollera att det finns 72 matcher
- kontrollera att tider visas i svensk tid
- kontrollera att lagen och grupperna ser rimliga ut

Om matcher behöver importeras igen, använd CSV-importen i admin.

---

### 5. Sätt riktig deadline

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

### 6. Skapa testdeltagare för generalrepetition

Innan riktiga länkar skickas, skapa gärna 1–2 testdeltagare från den deployade admin-sidan.

Kontrollera:

- länken använder deployad Streamlit-URL, inte localhost
- deltagaren syns i deltagarstatus
- deltagaren har `0/72` tippade matcher
- bonusfråga visas som saknas/ej ifylld

Exempel på deployad deltagarlänk:

```text
https://din-app.streamlit.app?token=...
```

---

### 7. Testa deltagarflödet från deployad app

Öppna testdeltagarens länk på mobil eller i inkognito.

Testa:

- sidan öppnas utan admin-alternativ
- deadline visas rätt
- tipsen är öppna
- lägg 2–5 tips
- lägg bonusfråga
- tryck spara
- ladda om sidan
- kontrollera att tipsen ligger kvar
- kontrollera att status visar rätt antal, till exempel `5/72`

Kontrollera också i Supabase:

```sql
select *
from public.predictions
order by updated_at desc
limit 20;
```

Efter sparning ska tips finnas i tabellen.

---

### 8. Kontrollera adminstatus efter deltagartest

Tillbaka i admin:

- deltagarstatus visar rätt antal tippade matcher
- utslagsfråga visas som ifylld
- admin ska inte se vald bonusspelare före deadline
- poängtabellen ska inte visa poäng om inga resultat är inlagda
- bonusmål ska inte innehålla gamla testvärden

Om bonusmål ser fel ut, kontrollera att denna tabell är rensad:

```sql
select *
from public.bonus_scorer_results;
```

---

### 9. Testa deadline-låsning

Sätt deadline till dåtid tillfälligt.

Kontrollera från deltagarlänk:

- tipsen kan inte ändras
- låsta matchkort visas i stället för dropdowns
- poängtabell visas
- allas tips visas

Kontrollera från admin:

- bonusval kan visas efter deadline
- bonusmål kan uppdateras
- export av alla tips blir tillgänglig

Sätt deadline tillbaka till framtid om du ska fortsätta testa.

---

### 10. Testa resultat och poäng

Med deadline i dåtid:

- fyll i resultat på 1–2 matcher
- kontrollera att deltagarens poäng uppdateras
- kontrollera `Matcher & resultat`
- kontrollera `Allas tips`
- kontrollera poängtabellen
- rensa resultat igen och kontrollera att poängen försvinner

Poäng räknas automatiskt:

- 1 poäng för rätt 1/X/2
- 1 poäng för rätt över/under 2,5 mål

---

### 11. Testa exporter

Testa minst:

- deltagarlänkar-export
- deltagarstatus-export
- poängtabell-export
- matcher/resultat-export
- alla tips-export efter deadline

Du behöver inte granska varje CSV i detalj, men kontrollera att filerna laddas ner och inte kraschar.

Export av alla tips är låst fram till deadline.

---

### 12. Kör cleanup igen efter generalrepetition

När generalrepetitionen är klar, kör gruppspels-cleanup igen innan riktiga deltagare skapas:

```sql
delete from public.predictions;
delete from public.bonus_predictions;
delete from public.bonus_scorer_results;
delete from public.participants;

update public.matches
set
    home_goals = null,
    away_goals = null,
    status = 'scheduled';
```

Kontrollera sedan igen:

```sql
select count(*) as predictions_count from public.predictions;
select count(*) as bonus_predictions_count from public.bonus_predictions;
select count(*) as bonus_scorer_results_count from public.bonus_scorer_results;
select count(*) as participants_count from public.participants;

select count(*) as matches_count
from public.matches;

select count(*) as finished_matches_count
from public.matches
where status = 'finished'
   or home_goals is not null
   or away_goals is not null;
```

---

### 13. Skapa riktiga deltagare

Skapa riktiga deltagare från den deployade admin-sidan.

Viktigt:

- skapa eller kopiera länkar från deployad app
- inte från lokal app
- kontrollera att varje deltagare får rätt länk

Varje deltagare får en privat länk i formatet:

```text
https://din-app.streamlit.app?token=...
```

---

### 14. Exportera deltagarlänkar

I admin:

- öppna `Deltagare & länkar`
- kontrollera att alla deltagare har sparad länk
- ladda ner CSV med deltagarlänkar
- skicka rätt länk till rätt person

Deltagarlänkar kan skickas via valfri kanal, till exempel Messenger, Discord, SMS eller liknande.

---

### 15. När riktiga länkar är skickade

Efter att riktiga deltagare fått sina länkar:

- kör inte cleanup
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

## Slutspelstestdata

Slutspelstipset är separat från gruppspelstipset.

Om du vill rensa slutspels-testdata men behålla importerade slutspelsmatcher/placeholders, kör:

```sql
delete from public.knockout_predictions;
delete from public.knockout_final_predictions;

update public.knockout_matches
set
    home_goals_ft = null,
    away_goals_ft = null,
    first_scorer = null,
    status = 'scheduled';

update public.knockout_rounds
set
    deadline_at = null,
    status = 'not_started';

update public.knockout_final_result
set
    finalist_1 = null,
    finalist_2 = null,
    winner = null,
    updated_at = now()
where id = 1;
```

Detta rensar:

- slutspelstips
- finaltips
- slutspelsresultat
- slutspelsrundors deadlines/status
- faktiskt finalutfall

Det behåller:

- slutspelsrundor
- slutspelsmatcher
- placeholders/importerad slutspelsstruktur

---

## Under turneringen

När matcher spelas:

1. Gå till admin.
2. Öppna `Resultat`.
3. Välj match.
4. Fyll i resultat.
5. Kontrollera poängtabellen.
6. Exportera backup vid behov.

När gruppspelet är färdigt:

1. Kontrollera slutlig gruppspelstabell.
2. Fyll i bonusmål för valda utslagsfråga-spelare.
3. Kontrollera slutlig poängtabell.
4. Exportera backup.

---

## Backup

Admin kan exportera CSV-filer från `Export`.

Rekommenderade exporter under turneringen:

- matcher och resultat
- poängtabell
- deltagarstatus
- alla tips efter deadline

Exportera gärna backup:

- direkt efter deadline
- efter större resultatuppdateringar
- när gruppspelet är färdigspelat