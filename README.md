# Praćenje izbornih rezultata sa mreže X

Ovaj projekat čuva objave izabranih X naloga i njihove fotografije, a zatim poredi objavljene procene sa konačnim zvaničnim rezultatima parlamentarnih izbora u Srbiji. Trenutno su obuhvaćene 2020, 2022. i 2023. godina.

Postoje dva odvojena koraka: **prikupljanje objava** i **provera tačnosti procena**. Prikupljanje koristi X API i može da troši kredit. Provera već sačuvanih podataka radi na računaru, bez tokena, interneta i trošenja X kredita.

## Šta pokazuju sadašnji rezultati

Evaluacija je završena 24. oktobra 2026. Obrađene su **244 objave i 102 fotografije**, uključujući ranije pregledane podatke. Postoji i **12 video-priloga koji nisu preuzeti ni transkribovani**; njihov sadržaj nije ocenjen.

| Nalog | Preseci sa potpunom procenom, od ukupno 12 | Ocena podrške / 100 |
| --- | ---: | ---: |
| CeSIDBeograd | 11 | 67 |
| crtars | 5 | 50 |
| miikialeksic | 0 | 1 |
| milos_vucevic | 0 | 1 |
| narodnipokrets | 0 | 1 |
| slobodaipravda | 0 | 1 |
| sns_srbija | 0 | 1 |

**Ocena nije procenat tačnosti.** Broj 67 ne znači „67% objava je tačno“. Ocena uzima u obzir odstupanje procena i to koliko rano i za koliko izbora imamo upotrebljive podatke. Broj **1 znači da nema dovoljno odgovarajućih brojčanih procena za ocenjivanje**, a ne da je nalog nepouzdan.

CeSID u ovom uzorku češće ima potpunu procenu dostupnu ranije tokom noći. CRTA ima korisne kasnije procene. Za poređenje njihove preciznosti gledaj **istu godinu i isti vremenski presek**, a ne samo ukupnu ocenu.

Prosečno odstupanje za šest najvećih izbornih lista, u procentnim poenima, posle svođenja procenata na važeće glasove:

| Godina / nalog | 22:00 | Prva ponoć | 02:00 | Ponoć na kraju narednog dana |
| --- | ---: | ---: | ---: | ---: |
| 2020 / CeSID | 0,234 | 0,200 | 0,200 | 0,200 |
| 2020 / CRTA | — | — | — | 0,092 |
| 2022 / CeSID | — | 0,168 | 0,080 | 0,080 |
| 2022 / CRTA | — | — | 0,360 | 0,273 |
| 2023 / CeSID | 0,227 | 0,156 | 0,156 | 0,156 |
| 2023 / CRTA | — | — | 0,179 | 0,116 |

**Manji broj znači manje odstupanje.** Crtica znači da do tog trenutka nemamo odgovarajuću potpunu procenu. Ista procena može da važi u više preseka ako nalog nije objavio noviju. CRTA je 2020. ranije objavila raspone za pojedine liste; oni su provereni odvojeno i nisu pretvoreni u izmišljene precizne procente.

U poslednjem CRTA prikazu mandata za 2023. raspodela se potpuno poklapa sa konačnom raspodelom. Poslednja CeSID projekcija zahteva premeštanje jednog od 250 mandata. Mandati se proveravaju odvojeno od procenata glasova.

**Prikupljanje još nije završeno za `slobodaipravda`, 2023. godinu.** Ostalih 20 kombinacija naloga i godine ima završenu pretragu za zadati period. Ovo ne garantuje dostupnost obrisanih objava ili sadržaja sa spoljnih linkova.

## Koji period se prikuplja

Periodi se nalaze u `election_windows.json`. Sva vremena ispod su po vremenu u Beogradu.

| Izbori | Početak | Kraj, koji se ne uključuje |
| --- | --- | --- |
| 2020 | 21. jun, 20:00 | 23. jun, 00:00 |
| 2022 | 3. april, 20:00 | 5. april, 00:00 |
| 2023 | 17. decembar, 20:00 | 19. decembar, 00:00 |

Svaki period traje **28 sati**: izborna noć i ceo naredni dan. Na primer, kraj perioda za 2023. je ponoć između 18. i 19. decembra. Ovaj kraj je granica prikupljanja, a ne vreme objavljivanja rezultata RIK-a.

Za ocenjivanje koristimo četiri preseka: **22:00 na dan izbora, prvu ponoć, 02:00 narednog dana i ponoć na kraju narednog dana**. Presek u 06:00 nije uključen.

Za svaki presek uzima se poslednja sopstvena potpuna procena objavljena do tog trenutka. Objava iz 00:18 može da uđe u presek u 02:00, ali ne u prethodnu ponoć. Ako je grafikon objavljen u više delova, potpuna procena postaje dostupna tek posle poslednjeg dela.

## Kako pokrenuti program

Za **praćenje uživo naloga CeSIDBeograd i crtars svakog minuta, od 12:00 do ponoći**, koristi novi `watch_x.py`. Windows obaveštenja, izbor datuma, pokretanje jednom komandom i podešavanje Task Scheduler-a opisani su u [WATCH_X.md](WATCH_X.md). Postojeće komande ispod služe za istorijsko prikupljanje.

Otvori projekat u VS Code-u, zatim otvori terminal i izaberi PowerShell. Nalepi sledeće komande. Tekst `(.venv) PS ...>` koji vidiš u terminalu nije deo komande i ne kopira se.

```powershell
Set-Location "D:\VSCode\Folders\election"
.\.venv\Scripts\Activate.ps1
```

Ako je okruženje već aktivno, dovoljno je da budeš u folderu projekta. Ako aktivacija ne uspe, umesto reči `python` u komandama ispod možeš da koristiš `.\.venv\Scripts\python.exe`.

Za prikupljanje je potreban bearer token. Sačuvaj ga u fajl `.env` u glavnom folderu, u jednom redu:

```dotenv
X_BEARER_TOKEN=OVDE_NALEPI_SVOJ_TOKEN
```

Token je tajna pristupna šifra: ne deli ga i ne stavljaj ga u README. Program ga sam čita. Ako je token već podešen u aktivnom terminalu, ta vrednost ima prednost nad `.env` fajlom.

### Probni prikaz bez preuzimanja

Ova komanda samo prikazuje šta bi program pretražio. Ne troši kredit i ne menja fajlove.

```powershell
$account = "CeSIDBeograd"
python .\collect_x.py --account $account --years 2020 2022 2023 --max-posts 10
```

### Prikupljanje: po jedna komanda za svaki nalog

Opcija `--fetch` uključuje pravo preuzimanje. Ograničenje `--max-posts 10` važi **za svaku godinu pojedinačno u jednom pokretanju**: najviše 30 vraćenih objava za nalog kroz tri godine. Prikazana cena je procena iz programa; stvarnu naplatu proveravaš na X developerskom nalogu.

```powershell
$account = "CeSIDBeograd"
python .\collect_x.py --account $account --years 2020 2022 2023 --fetch --max-posts 10
```

```powershell
$account = "crtars"
python .\collect_x.py --account $account --years 2020 2022 2023 --fetch --max-posts 10
```

```powershell
$account = "miikialeksic"
python .\collect_x.py --account $account --years 2020 2022 2023 --fetch --max-posts 10
```

```powershell
$account = "milos_vucevic"
python .\collect_x.py --account $account --years 2020 2022 2023 --fetch --max-posts 10
```

```powershell
$account = "narodnipokrets"
python .\collect_x.py --account $account --years 2020 2022 2023 --fetch --max-posts 10
```

```powershell
$account = "slobodaipravda"
python .\collect_x.py --account $account --years 2020 2022 2023 --fetch --max-posts 10
```

```powershell
$account = "sns_srbija"
python .\collect_x.py --account $account --years 2020 2022 2023 --fetch --max-posts 10
```

Ako piše **`PARTIAL`**, ponovi isti blok. Ako piše **`Search exhausted`**, pretraga je završena za taj nalog, godinu i period. Završena pretraga se preskače pri sledećem pokretanju. Možeš da zatvoriš terminal ili računar: mesto nastavka je sačuvano na disku.

Sačuvane objave se spajaju po jedinstvenom broju objave, pa nema duplih zapisa u `posts.jsonl`. Promena perioda pravi novu pretragu; ponovo vraćene stare objave mogu da budu naplaćene iako se ne dupliraju u konačnom fajlu. Pokreći komande redom.

### Ponovno računanje evaluacije

Za trenutno pregledane podatke pokreni:

```powershell
python .\evaluate_accounts.py
```

Komanda ponovo pravi `executive_decision.json`, detaljne proračune i izveštaj. Ne preuzima objave i ne troši X kredit.

**Nove objave i slike prvo moraju da se pregledaju.** Ovaj program sam ne čita nove grafikone sa slika. Ako posle novog prikupljanja prijavi da su podaci promenjeni ili da je potreban pregled, prvo treba proveriti nove brojeve i dopuniti pregledane podatke. Nemoj samo menjati kontrolne vrednosti da bi preskočio ovu proveru.

## Gde su podaci

Osnovni raspored je `data / godina / ime_naloga`. Na primer, fotografije naloga CeSID za 2023. su neposredno u folderu `data/2023/cesidbeograd/`.

| Fajl ili folder | Šta sadrži |
| --- | --- |
| `collect_x.py` | Program za prikupljanje objava i fotografija. |
| `election_windows.json` | Godine i vremenske periode za pretragu. |
| `data/2023/cesidbeograd/posts.jsonl` | Sve sačuvane objave tog naloga i godine; jedna objava u svakom redu. |
| `candidates.jsonl` u istom folderu | Izdvojene moguće relevantne objave, prema tekstu, brojevima ili slikama. |
| Slike `.jpg` i `.png` u istom folderu | Fotografije u originalnoj dostupnoj rezoluciji; ime povezuje sliku sa objavom. |
| `search_...json` u istom folderu | Dokle je stigla određena pretraga i da li je završena. Ne briši ako želiš nastavak. |
| `raw/` u istom folderu | Izvorni odgovori API-ja, radi provere i oporavka posle prekida. |
| `data/2020_official/`, `data/2022_official/`, `data/2023_official/` | Zvanični rezultati u Excel/PDF fajlovima. |
| `analysis/accounts/reviewed_claims.json` | Pregledane objave, pročitani brojevi sa slika i razlozi uključivanja ili izostavljanja. |
| `analysis/accounts/official_reference.json` | Provereni zvanični brojevi korišćeni za poređenje. |
| `analysis/accounts/comparisons.json` | Detaljni proračuni za svaku proverenu tvrdnju i listu. |
| `analysis/accounts/report.md` | Detaljniji izveštaj na engleskom. |
| `executive_decision.json` | Glavni pregled po nalogu, godini i vremenskom preseku. |

Ključne reči na srpskom i engleskom samo izdvajaju kandidate; **ne sprečavaju čuvanje ostalih vraćenih objava**. Evaluacija koristi sve sačuvane objave, ne samo kandidate. Automatski se preuzimaju fotografije; video-snimci i stranice sa spoljnih linkova nisu transkribovani. Deset ranije nedostajućih slika ima i pregledanu kopiju u `analysis/accounts/recovered_media/`.

## Kako čitati executive_decision.json

JSON je tekstualni fajl sa podacima raspoređenim po imenovanim poljima. Možeš ga otvoriti u VS Code-u. Polje `accounts` sadrži sedam naloga. Svaki nalog ima svoje `account`, `years` i **`confidence_score` izvan dela sa godinama**.

| Polje | Značenje |
| --- | --- |
| `coverage` | Koliko objava, fotografija, naloga i godina je obrađeno. |
| `methodology` | Pravila izbora procena i računanja ocene. |
| `accounts` → `account` | Ime naloga. |
| `years` → `2020`, `2022`, `2023` | Rezultati za svaku godinu. |
| `collection_exhausted` | `true`: pretraga aktuelnog perioda je završena; `false`: postoji praznina u prikupljanju. |
| `cutoffs` | Četiri vremenska preseka za tu godinu. |
| `forecast` | Koja objava je izabrana, kada je objavljena i odakle potiču brojevi. |
| `normalized_top_six_mae_pp` | Prosečno odstupanje za šest najvećih lista, u procentnim poenima, na uporedivoj osnovi. |
| `age_minutes` | Koliko je minuta izabrana procena bila stara u trenutku preseka. |
| `reused_from_previous_cutoff` | `true` znači da se koristi ista objava kao u prethodnom preseku. |
| `confidence_score` | Zbirna ocena podrške od 1 do 100, za ceo nalog. |
| `confidence_components` | Brojevi iz kojih je izvedena zbirna ocena. |
| `decision` i `decision_reason` | Preporuka za upotrebu naloga i objašnjenje. |
| `matched_time_comparisons` | Poređenje naloga grupisano po istoj godini i istom preseku. |
| `limitations` | Ograničenja podataka i zaključaka. |

Oznake četiri preseka su `election_day_22_00`, `next_day_00_00`, `next_day_02_00` i `end_next_day_00_00`. Svaki ima i pun datum i vreme. Vrednost **`null` znači da nema odgovarajućeg podatka**, a ne nula procenata ili savršena procena.

## Kako se meri odstupanje i računa ocena

Ako je procena 23%, a zvaničan rezultat 23,5%, odstupanje je **0,5 procentnih poena**. MAE je prosek takvih apsolutnih odstupanja za šest lista koje su na kraju dobile najviše glasova. Procenti iz kompletnog grafikona prvo se svode na važeće glasove, da se ne mešaju procenti koji uključuju i isključuju nevažeće listiće. Izvorni procenti i druge osnove poređenja ostaju u detaljnim proračunima.

Unutar godine svi dostupni preseci imaju jednaku težinu. Ako procena nedostaje u nekom preseku, ne upisuje se nulta greška, nego se smanjuje količina dokaza za tu godinu. Jedna godina nosi najviše težinu 1; ako postoji podatak u samo jednom od četiri preseka, težina je 0,25. Nepotpuna pretraga dodatno množi težinu sa 0,75. Više objava iste večeri ne predstavlja više nezavisnih izbora.

Za proveru formule: `N` je zbir tih težina, a `E` prosečno odstupanje godina ponderisano tim težinama. Ocena je `100 × max(0, 1 − E/2) × N/(N+1)`, zaokružena i ograničena na 1–100. Parametri su jednostavno, oprezno pravilo ovog projekta; nisu statistički dokazana verovatnoća. Nova ocena koristi vremenske preseke, pa nije direktno uporediva sa starom ocenom koja je koristila sve objave.

Preneti zvanični podaci RIK-a ne podižu ocenu sopstvenih prognoza naloga. Posebno se čuvaju procene mandata, izlaznost i rasponi. Predsednički, pokrajinski i gradski rezultati ne porede se sa nacionalnim parlamentarnim rezultatima.

CRTA uzorak ne obuhvata birače sa Kosova, iz inostranstva i iz zatvora, dok nacionalni konačni rezultat obuhvata širu populaciju i ponovljena glasanja. Zato prikazano odstupanje nije samo greška procene za potpuno istu populaciju. U poslednjem CRTA grafikonu za 2022. jedna mala lista ima ispisano samo „0“; ta vrednost je sačuvana bez nagađanja. Izlaznost bez odgovarajuće teritorijalne osnove ostaje neocenjena. Ova evaluacija ne proverava navode o izbornim nepravilnostima i ne daje opštu ocenu istinitosti naloga.
