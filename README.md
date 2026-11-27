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
tests/               pytest testovi za svaki modul jezgre
docs/superpowers/    dizajn aplikacije i planovi rada
```

## Stanje po milestoneima

| KT | Milestone | Stanje |
|---|---|---|
| II. | **M1** Jezgra: model podataka, pohrana, pravila ponavljanja | ✅ |
| II. | **M2** Osnovna projekcija stanja i terminalsko sučelje `fin` | u izradi |
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
