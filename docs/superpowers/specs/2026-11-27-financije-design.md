# Aplikacija za osobne financije — dizajn

Datum: 2026-11-27 · Kolegij: Programiranje: skriptni jezici · Autor: Bojan Ivanović

## 1. Namjera i zašto

Lokalna aplikacija za osobne financije u Pythonu (podaci ostaju na korisnikovu računalu).
Prijedlog projekta je prihvaćen, a profesor je tražio pomak težišta:

> Uvoz izvoda i razvrstavanje s pamćenjem preklapa se s projektom kolege. Težište je na
> **ponavljajućim stavkama i projekciji stanja**, i te dvije cjeline treba **povezati**.

Zato je središnji tok aplikacije:

1. **Očekivano** — korisnik unese što očekuje: plaću zadnji radni dan u mjesecu, najam 5. u
   mjesecu, pretplate…
2. **Stvarno** — korisnik uveze bankovni izvod.
3. **Usklađivanje** — alat sam prepoznaje koje su se očekivane stavke dogodile, upozori kad
   datum ili iznos odstupa i kad očekivana stavka izostane („plaća za listopad još nije
   stigla”, „najam za studeni nije plaćen”).
4. **Projekcija** — kreće od **stvarnog stanja** s izvoda, dodaje ponavljajuće stavke koje tek
   dolaze (i one koje kasne) te procjenu promjenjivih troškova (hrana, gorivo…) izračunatu iz
   dosadašnjih izvoda.

Uvoz i razvrstavanje postoje samo koliko trebaju ovom toku (ulaz za usklađivanje i za
procjenu promjenjivih troškova). Nisu cilj sami po sebi.

## 2. Ciljevi, ne-ciljevi, anti-ciljevi

**Ciljevi**
- Ponavljajuće stavke s pravilima: N-ti dan u mjesecu, zadnji radni dan u mjesecu, svakih N
  tjedana, godišnje, uz ispravno rukovanje kraćim mjesecima, vikendima i hrvatskim praznicima.
- Uvoz izvoda (CSV, Excel) u jasno definiranom formatu, bez duplikata pri ponovnom uvozu.
- Automatsko usklađivanje očekivanih stavki s transakcijama i upozorenja (odstupanje datuma,
  odstupanje iznosa, izostanak).
- Projekcija stanja od stvarnog stanja + ponavljajuće stavke + procjena promjenjivih troškova.
- Terminalsko sučelje (od II. KT) i lokalna web aplikacija u Streamlitu (IV. KT).
- Automatski testovi za svu ključnu logiku; projekcija se poklapa s ručno izračunatim primjerima.

**Ne-ciljevi**
- Pamćenje korisnikovih ispravaka kategorija (strojno učenje, napredna pravila) — preklapa se
  s kolegom. Razvrstavanje je samo jednostavna pravila po ključnim riječima.
- Više računa, više valuta, više korisnika, prijava, sinkronizacija, poslužitelj.
- Izravno spajanje na banku (API). Samo uvoz datoteke.
- Mobilna aplikacija (Streamlit se može otvoriti u pregledniku mobitela na istoj mreži; ništa više).

**Anti-ciljevi** (aplikacija „radi”, ali je promašaj)
- Usklađivanje i projekcija koji žive odvojeno — projekcija koja ignorira izvod ili upozorenja
  koja ne utječu na projekciju.
- Lažna upozorenja: najam plaćen 6. umjesto 5. jer je 5. nedjelja ne smije se javljati kao
  odstupanje.
- Ponovni uvoz istog izvoda koji udvostruči transakcije.
- Logika koja živi u sučelju (Streamlit/CLI) i ne može se testirati bez njega.

## 3. Ograničenja

- Jezik: isključivo Python (dopušteni su i Bash, PowerShell, Lua, Perl, JS, Ruby, ali se ne koriste).
- Python 3.12, lokalna pohrana u SQLite (`sqlite3` iz standardne biblioteke, bez ORM-a).
- Rokovi: II. KT 27.11.2026. (danas), III. KT 18.12.2026., IV. KT 22.01.2027.
  Za svaku KT barem dva smislena commita (milestonea).
- Jezgra ne zna ništa o sučelju (arhitektura iz izvješća za I. KT).

## 4. Razmotreni pristupi (sučelje)

Sva tri pristupa dijele istu jezgru i počinju terminalskim sučeljem.

| Pristup | Za | Protiv |
|---|---|---|
| 1. Samo terminal (Typer + Rich) | najmanje posla, sigurno u roku | nema pravog sučelja; upozorenja i grafovi samo kao tekst / HTML datoteka |
| **2. Terminal sada, Streamlit za IV. KT** | sve u Pythonu; tablice, grafovi i upload izvoda gotovi; na mobitelu kroz preglednik | manja kontrola izgleda; skripta se ponovno izvodi na svaki klik (ovdje ne smeta) |
| 3. Terminal sada, Flet desktop za IV. KT | prava aplikacija, put prema mobitelu | puno više koda za tablice i grafove, sporiji razvoj |

**Odabrano: pristup 2** (odluka korisnika), jer daje najviše vidljivog rezultata za najmanje
koda, a sve ostaje u Pythonu.

## 5. Arhitektura

```
financije/
  core/                # sva logika, bez ikakvog I/O sučelja
    models.py          # dataclassovi: Category, RecurringItem, Rule, Transaction, Occurrence, Alert…
    money.py           # iznosi kao cijeli broj centi; parsiranje "1.234,56" i formatiranje
    calendar_hr.py     # radni dani: vikend + hrvatski praznici
    recurrence.py      # pravila ponavljanja → datumi pojavljivanja
    storage.py         # SQLite: shema, migracija verzijom, CRUD
    importer.py        # čitanje CSV/XLSX izvoda → Transaction, deduplikacija
    categorize.py      # pravila ključnih riječi → kategorija
    reconcile.py       # usklađivanje očekivano ↔ stvarno, upozorenja
    variable.py        # procjena promjenjivih troškova
    projection.py      # projekcija stanja
    sample_data.py     # generator probnih podataka i izvoda
  cli.py               # Typer + Rich, tanki sloj nad core
  ui/app.py            # Streamlit, tanki sloj nad core (IV. KT)
tests/                 # pytest, jedan modul po modulu jezgre
data/                  # probni izvodi (generirani), primjer formata
pyproject.toml         # ovisnosti, naredba `fin`
```

Ovisnosti: `typer`, `rich`, `openpyxl` (čitanje .xlsx), `streamlit` + `pandas` + `altair`
(samo za UI, IV. KT), `pytest`. Praznici se računaju vlastitim kodom (vidi 6.2) — nema
vanjske ovisnosti, a algoritam za Uskrs je zanimljiv za izvješće.

Baza: jedna datoteka, zadano `~/.financije/financije.db`, može se promijeniti opcijom
`--db` / varijablom `FINANCIJE_DB`. Svi iznosi u **centima (int)**, prihodi pozitivni,
troškovi negativni.

## 6. Jezgra — kako radi

### 6.1 Model podataka (SQLite)

- `category(id, name, kind)` — `kind ∈ {fixed, variable, income, other}`. Promjenjive
  kategorije (`variable`, npr. Hrana, Gorivo, Izlasci) ulaze u procjenu troškova.
- `recurring_item(id, name, amount_cents, category_id, rule_json, match_pattern,
  amount_tolerance_cents, amount_tolerance_pct, date_window_days, start_date, end_date, active, note)`
  - `match_pattern`: tekst (bez razlike velikih/malih slova, podniz) po kojem se stavka
    prepoznaje u opisu transakcije, npr. `NETFLIX`, `ACME D.O.O.`, `NAJAM`.
    Može biti i regex ako počinje s `re:`.
  - `amount_tolerance_*`: koliko iznos smije odstupati prije upozorenja (zadano 0 € i 0 %;
    za račune za struju korisnik postavi npr. 20 %). Vrijedi veće od dvoje.
  - `date_window_days`: koliko dana prije/poslije očekivanog datuma transakcija još može biti
    ta stavka (zadano 7). Unutar prozora: prepoznato; ako datum ≠ očekivani → upozorenje
    o datumu.
- `transaction(id, date, amount_cents, description, counterparty, category_id, import_id,
  fingerprint, balance_after_cents NULL, note)` — `fingerprint` = hash(datum, iznos,
  normalizirani opis, redni broj među istima u izvodu), `UNIQUE` → deduplikacija.
  Ručno unesene jednokratne stavke su također `transaction` (s `import_id NULL`).
- `import_batch(id, file_name, imported_at, period_from, period_to, closing_balance_cents, closing_balance_date)`
- `balance_checkpoint(date, balance_cents, source)` — poznata stvarna stanja (iz izvoda ili
  ručno unesena). Projekcija kreće od zadnjeg.
- `occurrence_link(recurring_item_id, due_date, transaction_id NULL, status, confirmed_by_user)`
  — rezultat usklađivanja po pojavljivanju; `status ∈ {matched, skipped}`. Korisnik može ručno
  povezati/odvezati transakciju ili označiti pojavljivanje kao „preskočeno” (npr. pretplata
  pauzirana taj mjesec). Ručne odluke usklađivanje nikad ne gazi.
- `category_rule(id, pattern, category_id, priority)` — jednostavna pravila razvrstavanja.
- `meta(key, value)` — verzija sheme.

### 6.2 Pravila ponavljanja i kalendar

Pravilo se sprema kao JSON, npr. `{"type": "monthly_day", "day": 5, "shift": "next_workday"}`.

| `type` | Parametri | Primjer |
|---|---|---|
| `monthly_day` | `day` (1–31) | najam 5. u mjesecu; `day: 31` → zadnji dan kraćih mjeseci |
| `last_workday` | — | plaća zadnji radni dan |
| `nth_workday` | `n` (1 = prvi radni dan) | |
| `weekly` | `every` (tjedana), `anchor` (datum) | svakih 2 tjedna od 2026-01-09 |
| `yearly` | `month`, `day` | godišnja pretplata 14.3.; 29.2. → 28.2. u neprijestupnoj |

`shift ∈ {none, next_workday, prev_workday}` — što ako datum padne na neradni dan
(zadano `none`; za najam/račune tipično `next_workday`). Radni dan = nije subota/nedjelja
ni hrvatski državni praznik (Nova godina, Sveta tri kralja, Uskrs i Uskrsni ponedjeljak,
Praznik rada, Dan državnosti 30.5., Tijelovo, Dan antifašističke borbe, Dan pobjede,
Velika Gospa, Svi sveti, Dan sjećanja 18.11., Božić, Sveti Stjepan). Uskrs se računa
algoritmom (anonimni gregorijanski / Meeus), Tijelovo = Uskrs + 60.

Funkcija: `occurrences(item, start, end) -> list[date]` (već pomaknuti datumi), uz
`nominal_date` (prije pomaka) za ispis „očekivano 5.12. (pomaknuto na 7.12.)”.

### 6.3 Uvoz izvoda

**Vlastiti definirani format** (CSV, `;` odvojeno, UTF-8, decimalni zarez — kako ga daju
hrvatske banke), stupci: `datum;opis;iznos;stanje` (`stanje` neobavezan). Datum `DD.MM.YYYY.`
ili ISO. Excel (`.xlsx`) s istim stupcima u prvom listu.

**Mapiranje stupaca** u `data/formats/*.toml` (ime stupca u datoteci → polje), tako da se
izvod stvarne banke uveze dodavanjem jedne datoteke, bez promjene koda. Isporučuje se format
`default.toml`; konkretna banka je proširenje.

Postupak uvoza: pročitaj → normaliziraj (iznosi u centima, datumi) → izračunaj `fingerprint`
→ preskoči postojeće → razvrstaj po pravilima → spremi `import_batch` → ako izvod ima stupac
`stanje`, zadnje stanje postaje `balance_checkpoint`; ako nema, CLI/UI pita završno stanje
(može se preskočiti). Nakon uvoza automatski se pokreće usklađivanje i prikazuju upozorenja.

### 6.4 Razvrstavanje (namjerno jednostavno)

Prvo pravilo (po prioritetu) čiji se `pattern` nalazi u opisu određuje kategoriju; inače
„Nerazvrstano”. Transakcija povezana s ponavljajućom stavkom dobiva kategoriju te stavke.
Kad korisnik ručno promijeni kategoriju, CLI/UI nudi (ne nameće) da se doda pravilo — to je
sve od „pamćenja”. Bez mjerenja točnosti na skupu (to je kolegin projekt).

### 6.5 Usklađivanje (srce projekta)

Ulaz: sve aktivne ponavljajuće stavke, sve transakcije, ručne odluke (`occurrence_link`),
`as_of` = zadnji dan pokriven izvodima (najkasniji `period_to`).

Usklađuju se samo datumi koje pokriva barem jedan uvezeni izvod (unija razdoblja
`period_from`–`period_to` svih `import_batch`), i ne prije `start_date` stavke — prije prvog
izvoda nema podataka, pa ni upozorenja o izostanku.

Za to razdoblje do `as_of`:
1. Generiraj pojavljivanja svake stavke (6.2).
2. Ručne odluke imaju prednost i uklanjaju te parove iz daljnjeg razmatranja.
3. Kandidati za pojavljivanje: neiskorištene transakcije istog predznaka, čiji opis odgovara
   `match_pattern`, s datumom unutar `± date_window_days`.
4. Dodjela je pohlepna po kvaliteti: parovi se sortiraju po (|razlika datuma|, |razlika
   iznosa|) i dodjeljuju dok se ne iscrpe; jedna transakcija ide najviše jednom
   pojavljivanju i obrnuto. (Dovoljno za realne slučajeve; dvije Netflix naplate u istom
   mjesecu rješavaju se jedna po jedna.)
5. Rezultat po pojavljivanju:
   - **U redu** — pronađeno, datum = očekivani (nakon pomaka), iznos u toleranciji.
   - **Odstupa datum** — pronađeno, ali datum ≠ očekivani. „Plaća stigla 3 dana kasnije.”
   - **Odstupa iznos** — iznos izvan tolerancije. „Netflix 13,99 € umjesto 11,99 €.”
     (Može i oboje.)
   - **Izostalo** — nije pronađeno, a `očekivani datum + date_window_days ≤ as_of`.
     „Plaća za listopad nije stigla (očekivano 30.10.).” / „Najam za studeni nije plaćen.”
   - **Kasni / još čeka** — nije pronađeno, rok prošao, ali prozor još nije istekao
     (`očekivani datum < as_of < očekivani + prozor`). Blaže upozorenje.
   - **Predstoji** — očekivani datum > `as_of`. Nije upozorenje; ide u projekciju.
6. Spremaju se samo automatski pronađeni parovi (`matched`, `confirmed_by_user = 0`) da bi
   UI mogao prikazati povezanu transakciju; pri svakom pokretanju automatski parovi se
   preračunavaju, ručni ostaju.

Upozorenja se uvijek računaju iz podataka (nisu spremljena) — uvijek odgovaraju trenutnom
stanju baze.

Poruke su na hrvatskom i spominju mjesec obračuna (`listopad`, `studeni`…), ne samo datum.

### 6.6 Procjena promjenjivih troškova

Za svaku kategoriju vrste `variable`: zbroj troškova po kalendarskom mjesecu za zadnjih
`N` **potpunih** mjeseci pokrivenih izvodima (zadano N = 3), isključujući transakcije
povezane s ponavljajućim stavkama. Procjena mjesečnog troška = **medijan** (otporan na
jedan skup mjesec); raspon = min/max tih mjeseci. Ako je dostupno manje od 1 potpunog
mjeseca, procjena se ne radi i projekcija to jasno kaže. Dnevni iznos = mjesečna procjena /
broj dana u mjesecu, raspoređen jednoliko.

### 6.7 Projekcija stanja

Ulaz: zadnji `balance_checkpoint` (datum D, stanje S), horizont (zadano 3 mjeseca), rezultat
usklađivanja, procjena promjenjivih troškova.

Dnevni niz od D+1 do kraja horizonta:
- **Predstojeće** ponavljajuće stavke na svoj datum.
- Stavke koje **kasne ili su izostale** (nisu plaćene/primljene, a nisu „preskočene") ulaze
  na dan D+1 s oznakom „zaostalo”, jer je novac i dalje dužan/očekivan. Opcija
  `--bez-zaostalih` / prekidač u UI ih isključuje. Ulaze sve neriješene zaostale stavke,
  bez obzira na starost; korisnik ih rješava ručnim povezivanjem ili „preskoči”.
- Promjenjivi troškovi kao dnevni iznos (medijan) od D+1 nadalje (ono što je u tekućem
  mjesecu već potrošeno do D sadržano je u stvarnom stanju), uz donju/gornju granicu iz raspona —
  projekcija ima tri linije: očekivano, optimistično, pesimistično.
- Ručno unesene jednokratne buduće stavke (planirani trošak, npr. registracija auta) na
  svoj datum. Ako postoje transakcije nakon D (ručni checkpoint stariji od izvoda),
  projekcija ih dodaje stanju prije nego što krene u budućnost.

Izlaz: niz (datum, stanje, stavke tog dana), stanje na kraju svakog mjeseca, **najniže
stanje i datum** („najniže 23,40 € dana 4.1. — prije plaće”), upozorenje ako stanje padne
ispod 0 (ili praga koji korisnik zada).

Ako nema nijednog checkpointa (II. KT, prije uvoza), projekcija uzima stanje i datum iz
argumenata (`fin projekcija --stanje 1200 --od 2026-11-27`).

### 6.8 Generator probnih podataka

`fin demo` stvara bazu s ~8 ponavljajućih stavki i generira izvode za zadnjih 6 mjeseci u
definiranom formatu: plaća zadnji radni dan, najam 5. s pomakom, Netflix/Spotify/teretana,
struja promjenjivog iznosa, kupovine hrane s nasumičnim iznosima, gorivo. **Namjerno ubačene
anomalije** (s fiksnim `seed`-om, ponovljivo): plaća kasni 3 dana jedan mjesec, poskupljenje
pretplate, izostao najam jedan mjesec, izostala plaća u zadnjem mjesecu. Isti generator
koriste testovi i demonstracija na KT.

## 7. Sučelja

### 7.1 Terminal (`fin`, Typer + Rich) — od II. KT

```
fin stavka dodaj "Najam" -400 --pravilo "monthly_day:5" --pomak next --kategorija Stanovanje --prepoznaj NAJAM
fin stavka popis | uredi ID | obrisi ID
fin raspored --mjeseci 2            # nadolazeća pojavljivanja
fin transakcija dodaj 2026-12-01 -35,50 "Konzum" [--kategorija Hrana]
fin stanje 1240,00 [--datum 2026-11-27]   # ručni checkpoint
fin projekcija [--mjeseci 3] [--bez-zaostalih]
fin uvoz izvod.csv [--format default]
fin uskladi                         # tablica: stavka, mjesec, očekivano, stvarno, status
fin upozorenja
fin povezi ID_STAVKE DATUM ID_TRANSAKCIJE | preskoci ID_STAVKE DATUM
fin kategorija ... | pravilo ...
fin demo [--db demo.db]
```
Skraćeni zapis pravila u CLI-u (`monthly_day:5`, `last_workday`, `weekly:2:2026-01-09`,
`yearly:3-14`) parsira se u JSON iz 6.2.

### 7.2 Streamlit (`fin ui` → `streamlit run financije/ui/app.py`) — IV. KT

Stranice (višestranična aplikacija):
1. **Pregled** — trenutno stanje (datum izvoda), upozorenja (crveno izostalo, žuto
   odstupanja/kasni), graf projekcije s tri linije i oznakom najnižeg stanja.
2. **Očekivano** — tablica ponavljajućih stavki, obrazac za dodavanje/uređivanje, prikaz
   sljedećih datuma uživo dok se pravilo mijenja.
3. **Izvodi** — upload CSV/XLSX, pregled uvezenog, rezultat usklađivanja odmah nakon uvoza.
4. **Usklađivanje** — mreža stavka × mjesec sa statusima (✓ / ⚠ / ✗ / •), klik → ručno
   povezivanje ili „preskoči”.
5. **Izvještaji** — mjesečni troškovi po kategorijama, očekivano vs. stvarno po mjesecu,
   promjenjivi troškovi kroz vrijeme; izvoz izvještaja u HTML.

## 8. Milestonei po kontrolnim točkama

Svaki milestone = jedan commit (ili mala serija commitova koji završavaju njime), s
prolaznim testovima.

### II. KT — 27.11.2026. (danas)

**M1 — Jezgra: model, pohrana i pravila ponavljanja**
Struktura projekta, `pyproject.toml`, `money`, `calendar_hr` (praznici + Uskrs),
`recurrence` (sva pravila iz 6.2 s pomacima), `storage` (shema, CRUD za kategorije,
ponavljajuće stavke, transakcije, checkpointe). Testovi: kraći mjeseci, 31. → 30./28.,
prijestupna godina, plaća zadnji radni dan kad je zadnji dan nedjelja ili praznik
(npr. 25.–26.12.), Uskrs za više godina.

**M2 — Projekcija (osnovna) i terminalsko sučelje**
`projection` za slučaj bez izvoda (ručno stanje + ponavljajuće + ručne jednokratne),
najniže stanje, kraj-mjeseca stanja. `cli.py`: `stavka`, `raspored`, `transakcija`,
`stanje`, `projekcija`. Testovi: projekcija se poklapa s ručno izračunatim primjerom
(dokumentiran u testu). README s uputama za pokretanje.

### III. KT — 18.12.2026.

**M3 — Uvoz izvoda, generator probnih podataka i razvrstavanje**
`importer` (CSV + XLSX, format iz TOML-a, deduplikacija, checkpoint iz stupca stanja),
`categorize`, `sample_data` + `fin demo`, `fin uvoz`. Testovi: ponovni uvoz ne dodaje
ništa, decimalni zarez, različiti formati datuma, izvod bez stupca stanja.

**M4 — Usklađivanje i upozorenja**
`reconcile` (6.5), `occurrence_link`, `fin uskladi`, `fin upozorenja`, `fin povezi`,
`fin preskoci`; uvoz automatski pokreće usklađivanje. Testovi na demo podacima: svaka
ubačena anomalija iz generatora prepoznata je točno jednom, bez lažnih upozorenja za
pomaknuti najam.

**M5 — Povezana projekcija**
Projekcija kreće od zadnjeg stvarnog stanja iz izvoda, uključuje zaostale stavke, `variable`
procjena (6.6) s rasponom. Testovi: ručno izračunati primjer s promjenjivim troškovima;
izostala plaća vidljivo mijenja projekciju.

### IV. KT — 22.01.2027.

**M6 — Streamlit sučelje**
Stranice Pregled, Očekivano, Izvodi, Usklađivanje (7.2), `fin ui`. Sučelje zove samo
funkcije jezgre.

**M7 — Izvještaji, izvoz i završno poliranje**
Stranica Izvještaji s grafovima, izvoz izvještaja u HTML, izvoz/uvoz podataka u JSON/CSV
(iz izvješća za I. KT), dopuna testova, README/dokumentacija.

Proširenja ako ostane vremena (redom): prijedlog novih ponavljajućih stavki iz izvoda
(otkrivanje transakcija koje se ponavljaju), proračuni po kategorijama s upozorenjima,
format izvoda jedne stvarne hrvatske banke.

## 9. Odluke prepuštene graditelju

- Točan izgled tablica u terminalu i stranica u Streamlitu, unutar opisanog sadržaja.
- Imena funkcija i unutarnja struktura modula, uz poštivanje podjele iz 5.
- Kako se točno računa `fingerprint`, uz uvjet da ponovni uvoz istog/preklapajućeg izvoda
  ne stvara duplikate, a dvije stvarno iste kupovine istog dana se ne spoje u jednu.
- Imena u kodu na engleskom, tekst sučelja i poruke na hrvatskom.
