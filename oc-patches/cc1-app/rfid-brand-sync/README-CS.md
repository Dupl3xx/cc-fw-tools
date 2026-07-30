# RFID značky pro CANVAS, displej a Elegoo Slicer

Patch je určený pro Centauri Carbon 1, stock firmware `1.4.46` a OpenCentauri
`0.4.0`. Přidává 68 vlastních názvů značek k původním položkám ELEGOO a
Generic. Nemění typy materiálu ani teplotní tabulky tiskárny.

## Proč běžný kód značky nefunguje

CANVAS nečte každý NTAG213 bezpodmínečně. Firmware modulu AMS Lite nastavuje
hardwarový identifikační filtr:

```text
stránka 0x10 = 36 EE EE EE
```

To je důvod, proč tag s těmito příkazy pípne:

```text
A2:10:36EEEEEE
A2:11:EE000000
```

Když se změní některý z prvních tří bajtů manufacturer ID na stránce `0x10`,
RFID modul tag zahodí ještě před odesláním dat do hlavní aplikace. Samotný
patch resolveru značky by proto nestačil.

Tento patch používá CANVAS-safe protokol:

- stránka `0x10` zůstává u všech značek přesně `36EEEEEE`;
- ID značky je pouze poslední bajt manufacturer ID, tedy první bajt stránky
  `0x11`;
- ELEGOO zůstává `EEEEEEEE`;
- neznámé ID bezpečně spadne na Generic.

Příklad:

| Značka | Manufacturer ID | Stránka `0x10` | Stránka `0x11` |
| --- | --- | --- | --- |
| ELEGOO | `EEEEEEEE` | `36EEEEEE` | `EE000000` |
| Generic | `EEEEEE01` | `36EEEEEE` | `01000000` |
| Prusament | `EEEEEE02` | `36EEEEEE` | `02000000` |
| Bambu Lab | `EEEEEE03` | `36EEEEEE` | `03000000` |
| Plasty Mladec | `EEEEEE04` | `36EEEEEE` | `04000000` |
| eSUN | `EEEEEE05` | `36EEEEEE` | `05000000` |
| Polymaker | `EEEEEE06` | `36EEEEEE` | `06000000` |
| SUNLU | `EEEEEE07` | `36EEEEEE` | `07000000` |
| Overture | `EEEEEE08` | `36EEEEEE` | `08000000` |
| Spectrum | `EEEEEE09` | `36EEEEEE` | `09000000` |
| Creality | `EEEEEE0A` | `36EEEEEE` | `0A000000` |

Úplný seznam je v `brand_map.json` nebo ho vypíše:

```bash
python3 generate_tag.py --list-brands
```

## Formát tagu

Tiskárna používá devět stránek NTAG213, `0x10` až `0x18`:

| Stránka | Obsah |
| --- | --- |
| `0x10` | hlavička `36` + první tři bajty manufacturer ID |
| `0x11` | čtvrtý bajt manufacturer ID + 3 rezervované bajty |
| `0x12` | 32bitový kód hlavního materiálu |
| `0x13` | 16bitový kód podtypu + 2 rezervované bajty |
| `0x14` | RGB + color modifier |
| `0x15` | minimální a maximální teplota trysky |
| `0x16` | rezervováno |
| `0x17` | průměr ve setinách mm + hmotnost v gramech |
| `0x18` | výrobní kód |

Patch obsahuje přesnou tabulku 15 hlavních materiálů a 50 podtypů vytaženou
z binárky `1.4.46`. Generátor nepoužívá chybné ASCII příklady z původního
veřejného návodu ELEGOO.

## Vygenerování tagu

Prusament PLA, černá, 1 kg:

```bash
python3 generate_tag.py \
  --brand Prusament \
  --subtype PLA \
  --color 000000 \
  --weight 1000
```

Výstup začíná:

```text
A2 10 36 EE EE EE
A2 11 02 00 00 00
A2 12 00 80 76 65
```

V mobilní aplikaci NFC Tools otevřít `Other` -> `Advanced NFC commands`.
Nezapisovat data jako NDEF text. Příkazy `A2` zapisují přímo jednotlivé
čtyřbajtové stránky tagu.

Seznam materiálů a teplot:

```bash
python3 generate_tag.py --list-subtypes
```

Strojově čitelný JSON:

```bash
python3 generate_tag.py \
  --brand "Bambu Lab" \
  --subtype PETG-CF \
  --color 123ABC \
  --weight 750 \
  --json
```

## Datový tok do displeje a sliceru

1. CANVAS přijme tag, protože stránka `0x10` zůstává `36EEEEEE`.
2. Hlavní aplikace sestaví 32bitový manufacturer ID.
3. Hook `0x00292014` převede manufacturer ID na interní brand ID.
4. Hook `0x00291c90` převede brand ID na text.
5. Stejný resolver používá obrazovka, RFID dialog a SDCP odpověď pro slicer.

Elegoo Slicer nečte filament přes HTTP adresu
`/user-resource/filament_info`. Připojuje se na:

```text
ws://IP_TISKARNY:3030/websocket
```

Materiály načítá příkazem SDCP `Cmd 324` (`material info get`). Tiskárna
odesílá mimo jiné:

```json
{
  "tray_id": 0,
  "brand": "Prusament",
  "filament_name": "PLA",
  "filament_code": "PLA",
  "filament_color": "#000000",
  "min_nozzle_temp": 190,
  "max_nozzle_temp": 230
}
```

Slicer přebírá `brand` jako vendor zásobníku. Automatický výběr tiskového
profilu se v Elegoo Sliceru rozhoduje hlavně podle názvu a typu filamentu;
značka je až pomocné kritérium. To je chování sliceru, nikoli omezení přenosu
z tiskárny.

Na displeji se po načtení RFID zobrazí nový název v aktuálně vybrané položce.
Ručně otevřený stock dropdown má nadále fyzicky vytvořené jen dvě původní
položky ELEGOO a Generic. Výběr jiné položky v něm by načtenou značku přepsal.

## Binární mapa

- stock `/app/app` SHA-256:
  `ae693f7dc096da1f734c2972694963286cba20dc8f6afac79f8468139b613129`
- manufacturer resolver: `0x00292014` -> cave `0x00450300`
- brand resolver: `0x00291c90` -> cave `0x00450c40`
- displej používá resolver na `0x0031ed3c`
- RFID dialog používá resolver na `0x00321ca0`
- SDCP JSON používá resolver na `0x0036e744`
- SDCP registrace: `Cmd 324`, dispatcher `0x0036cd18`, callback `0x00371598`

## Ověření

Jednotkové testy:

```bash
python3 -m unittest discover \
  -s oc-patches/cc1-app/rfid-brand-sync \
  -p "test_*.py" \
  -v
```

Audit hlavní aplikace:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/analyze_app.py \
  unpacked/squashfs-root/app/app
```

Audit identifikačního filtru CANVAS:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/analyze_canvas_filter.py \
  unpacked/squashfs-root/app/resources/firmware/upgrade_ams_lite_full_pack.bin
```

Živý test po instalaci musí ověřit:

1. Originální ELEGOO tag stále pípne a zobrazí ELEGOO.
2. Tag `EEEEEE02` pípne a zobrazí Prusament.
3. Tag `EEEEEE03` pípne a zobrazí Bambu Lab.
4. Tag `EEEEEE04` pípne a zobrazí Plasty Mladec.
5. Typ, barva a teploty odpovídají obsahu tagu.
6. Elegoo Slicer po obnovení CANVAS zobrazí stejnou značku a materiál.

Statická analýza a build dokazují konzistenci firmware. Poslední bod, fyzický
RFID dosah, pípnutí a živý přenos do konkrétní tiskárny, lze definitivně
potvrdit pouze tímto testem na hardware.
