# Money-Manager

Lokalna aplikacija za osobne financije u Pythonu. Korisnik upiše što očekuje
(plaća zadnji radni dan u mjesecu, najam 5. u mjesecu, pretplate). Aplikacija
iz uvezenog bankovnog izvoda prepoznaje što se stvarno dogodilo i upozori kad
datum ili iznos odstupa ili kad očekivana stavka izostane. Projekcija stanja kreće
od stvarnog stanja računa, a dodaje stavke koje tek dolaze i procjenu promjenjivih
troškova. Svi podaci ostaju na korisnikovu računalu (SQLite).

Kolegij *Programiranje: skriptni jezici*, Tehnički fakultet u Rijeci, 2026./27.

## Instalacija

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

## Korištenje

Nakon instalacije dostupna je naredba `fin` (iz virtualnog okruženja:
`.venv/bin/fin` ili nakon `source .venv/bin/activate` samo `fin`).
Podaci se spremaju u `~/.financije/financije.db`. Drugu bazu odabireš
opcijom `--db` ili varijablom `FINANCIJE_DB`.

```bash
# očekivane ponavljajuće stavke
fin stavka dodaj Plaća 1500 --pravilo last_workday --kategorija Plaća
fin stavka dodaj Najam -400 --pravilo monthly_day:5 --pomak next --kategorija Stanovanje
fin stavka dodaj Netflix -11,99 --pravilo monthly_day:15 --kategorija Pretplate
fin stavka dodaj "Osiguranje auta" -280 --pravilo yearly:3-14 --pomak next
fin stavka popis
fin stavka uredi 3 --iznos -13,99          # ili --neaktivna, --pravilo, --pomak...
fin stavka obrisi 3

# planirani jednokratni trošak
fin transakcija dodaj 20.12.2026. -120 "Božićni pokloni"

# stvarno stanje računa i projekcija
fin stanje 230,50
fin raspored --mjeseci 2                    # što dolazi i kada
fin projekcija --mjeseci 3                  # stanje po danima, kraj mjeseca, najniže stanje
fin projekcija --stanje 500 --od 1.12.2026  # bez upisanog stanja
```

Zapis pravila: `monthly_day:5`, `last_workday`, `nth_workday:1`,
`weekly:2:2026-01-09` (svaka 2 tjedna od datuma), `yearly:3-14` (14.3.).
Pomak za neradne dane: `--pomak none|next|prev`.

Pomoć za svaku naredbu: `fin --help`, `fin stavka dodaj --help`...

## Testovi

```bash
.venv/bin/pytest
```

Ako je u ljusci učitan ROS (varijabla `PYTHONPATH` pokazuje na `/opt/ros/...`),
njegovi pytest dodaci ruše pokretanje. Testove tada pokreni s
`env -u PYTHONPATH .venv/bin/pytest`.

## Struktura

```
financije/core/      jezgra, sva logika, ne ovisi o sučelju
  money.py           iznosi u centima, hrvatski zapis (1.234,56 €)
  calendar_hr.py     hrvatski praznici (i Uskrs), radni dani
  models.py          model podataka
  recurrence.py      pravila ponavljanja → datumi pojavljivanja
  storage.py         SQLite pohrana
  projection.py      projekcija stanja
financije/cli.py     terminalsko sučelje `fin` (Typer + Rich)
tests/               pytest testovi za svaki modul jezgre
docs/superpowers/    dizajn aplikacije i planovi rada
```

## Stanje po milestoneima

| KT | Milestone | Stanje |
|---|---|---|
| II. | **M1** Jezgra: model podataka, pohrana, pravila ponavljanja | ✅ |
| II. | **M2** Osnovna projekcija stanja i terminalsko sučelje `fin` | ✅ |
| III. | **M3** Uvoz izvoda, generator probnih podataka, razvrstavanje | planirano |
| III. | **M4** Usklađivanje očekivanog i stvarnog, upozorenja | planirano |
| III. | **M5** Projekcija od stvarnog stanja s procjenom promjenjivih troškova | planirano |
| IV. | **M6** Sučelje u Streamlitu | planirano |
| IV. | **M7** Izvještaji s grafovima, izvoz, dokumentacija | planirano |

Detaljan dizajn: [`docs/superpowers/specs/2026-11-27-financije-design.md`](docs/superpowers/specs/2026-11-27-financije-design.md)

### Pravila ponavljanja (M1)

| Pravilo | Primjer |
|---|---|
| N-ti dan u mjesecu | najam 5. u mjesecu; „31.” u veljači postaje 28./29. |
| zadnji radni dan u mjesecu | plaća |
| N-ti radni dan u mjesecu | |
| svakih N tjedana od datuma | dvotjedna plaća |
| godišnje | osiguranje 14.3.; 29.2. u neprijestupnoj godini postaje 28.2. |

Ako datum padne na vikend ili praznik, stavka se može pomaknuti na sljedeći ili
prethodni radni dan (npr. najam za 5.12.2026., subota, dospijeva 7.12.).
