# RFID značky pro CANVAS, displej a Elegoo Slicer

[Česky](README-CZ.md) | [English](README-EN.md)

Kompletní postup pro novou tiskárnu, nový počítač, zápis tagu a obnovu je v
[end-to-end návodu](../../../docs/RFID-END-TO-END-CZ.md).

Patch je určený pro Centauri Carbon 1, stock firmware `1.4.46` a OpenCentauri
`0.4.0`. Přidává 68 vlastních názvů značek k původním položkám ELEGOO a
Generic. Nemění typy materiálu ani teplotní tabulky tiskárny.

## Kompatibilita

| Součást | Podporovaný stav |
| --- | --- |
| Tiskárna | ELEGOO Centauri Carbon 1 |
| Základní firmware | `1.4.46` |
| OpenCentauri | `0.4.0` |
| RFID tag | NTAG213, raw zápis stránek `0x10` až `0x18` |
| ELEGOO firmware `1.4.49` | Nepodporován tímto patchem |

Patcher kontroluje původní instrukce a volné code cave oblasti. Na jiné
binárce se odmítne spustit, místo aby zapsal data na neověřené adresy.

## Co bylo upraveno

- nový resolver manufacturer ID na interní brand ID;
- nový resolver brand ID na název pro displej a SDCP;
- 68 vlastních značek, celkem 70 položek včetně ELEGOO a Generic;
- zachování originálního ELEGOO manufacturer ID `EEEEEEEE`;
- fallback neznámých kódů na Generic;
- přesná mapa 15 materiálů a 50 podtypů včetně teplot z firmware `1.4.46`;
- generátor kompletního devítistránkového obsahu NTAG213;
- statické audity aplikace a CANVAS MCU firmware;
- živý read-only verifier používající SDCP `Cmd 324`;
- kompatibilní integrace upstream patche `spoof-slicer-firmware-version`,
  který Elegoo Sliceru hlásí podporovanou verzi `V1.4.46`;
- 17 regresních testů včetně kontroly překryvu obou code caves a aktivace
  opravy identity Sliceru ve výsledné edici;
- oprava pořadí podpisu v `pack.sh`, aby `cpio_item_md5` obsahoval hash
  finálního `sw-description.sig`.

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

Příkazy v této kapitole se spouštějí z adresáře
`oc-patches/cc1-app/rfid-brand-sync`.

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

## Sestavení firmware

Nejprve nainstalovat závislosti repozitáře:

```bash
python3 -m pip install -r requirements.txt
```

Kompletní sestavení podporované varianty:

```bash
sudo ./build.sh 1.4.46
```

Výsledkem je:

```text
update/update.swu
```

`oc-patches/patch_config` je v Gitu symbolický odkaz na
`firmware-editions/patched`. Na Windows je nejspolehlivější klonovat a
sestavovat repozitář uvnitř WSL, aby Git symbolický odkaz zachoval.

## Instalace

Tiskárna už musí důvěřovat OpenCentauri podpisovému klíči. Před instalací musí
být nečinná a nesmí se během zápisu vypnout napájení.

Bezpečnější dvoukrokový postup nejprve pouze nahraje soubor a porovná MD5:

```bash
./install.sh --stage IP_TISKARNY
```

Teprve po kontrole se spustí zápis do neaktivního A/B oddílu:

```bash
./install.sh --flash IP_TISKARNY
```

Oba kroky lze spojit:

```bash
./install.sh --sendit IP_TISKARNY
```

Před flashem lze balíček na tiskárně ověřit bez instalace:

```bash
swupdate -c \
  -i /user-resource/update.swu \
  -k /etc/swupdate_public.pem \
  -e stable,now_A_next_B
```

Režim `now_A_next_B` platí pouze tehdy, když tiskárna právě běží z `bootA`.
`install.sh` aktivní oddíl zjistí automaticky a při běhu z B použije opačný
režim.

## Datový tok do displeje a sliceru

1. CANVAS přijme tag, protože stránka `0x10` zůstává `36EEEEEE`.
2. Hlavní aplikace sestaví 32bitový manufacturer ID.
3. Hook `0x00292014` převede manufacturer ID na interní brand ID.
4. Hook `0x00291c90` převede brand ID na text.
5. Stejný resolver používá obrazovka, RFID dialog a SDCP odpověď pro slicer.

Než Slicer požádá o filamenty, ověřuje identitu a verzi tiskárny. Původní
OpenCentauri hodnota `V0.4.0-d` nebyla v Elegoo Sliceru přijata jako
kompatibilní firmware a import CANVAS proto nebyl dostupný. Kombinovaný build
ve všech třech slicerových cestách hlásí `V1.4.46`:

- UDP discovery;
- WebSocket attributes;
- přímá SDCP odpověď na `Cmd 1` (`request attribute`).

Skutečná OpenCentauri verze používaná lokálním UI, logy a OTA zůstává
nezměněná. Patch mění pouze hodnotu odesílanou Sliceru.

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

Elegoo Slicer `1.5.2.2` navíc při MMS synchronizaci přijímá pouze systémové
základní profily s přesným interním ID. Pro Prusament PLA je proto součástí
repozitáře samostatný [instalátor profilů pro Windows](../../../TOOLS/elegoo-slicer-rfid-sync/README-CZ.md).
Přidá profil `Prusament PLA @ECC` s ID `PRSPLA00` a opraví také kompatibilitu
Generic PETG pro Centauri Carbon.

Na displeji se po načtení RFID zobrazí nový název v aktuálně vybrané položce.
Ručně otevřený stock dropdown má nadále fyzicky vytvořené jen dvě původní
položky ELEGOO a Generic. Výběr jiné položky v něm by načtenou značku přepsal.

To znamená:

- po načtení RFID se na displeji zobrazí například Prusament nebo Bambu Lab;
- stejný text odejde do Elegoo Sliceru;
- všech 70 značek se nezobrazí jako ručně volitelné položky dropdownu;
- firmware patch sám tiskové profily nemění; doprovodný Windows instalátor
  aktuálně přidává ověřený profil Prusament PLA.

## Soubory patche

| Soubor | Účel |
| --- | --- |
| `patch_app.py` | bezpečný binární patch obou resolverů |
| `brand_map.json` | autoritativní mapa 70 značek |
| `material_map.json` | 15 materiálů a 50 podtypů s teplotami |
| `tag_codec.py` | kódování a dekódování devíti RFID stránek |
| `generate_tag.py` | CLI generátor příkazů pro NFC Tools |
| `analyze_app.py` | audit aplikace, SDCP a materiálových tabulek |
| `analyze_canvas_filter.py` | audit hardwarového filtru AMS Lite |
| `live_verify.py` | živé read-only čtení stejného JSON jako Slicer |
| `test_rfid_brand_sync.py` | regresní testy protokolu a patcheru |
| `../spoof-slicer-firmware-version/` | kompatibilní handshake `V1.4.46` pro Slicer |

## Binární mapa

- stock `/app/app` SHA-256:
  `ae693f7dc096da1f734c2972694963286cba20dc8f6afac79f8468139b613129`
- manufacturer resolver: `0x00292014` -> cave `0x00450300`
- brand resolver: `0x00291c90` -> cave `0x00450c40`
- slicerová verze `1.4.46`: cave `0x00451048`
- slicerové pointery: `0x0036859c`, `0x0036a98c`, `0x0037e80c`
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

Živá kontrola používá stejné SDCP discovery a `Cmd 324` jako Elegoo Slicer,
ale nic v tiskárně nemění:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/live_verify.py 192.168.1.18
```

Po načtení testovacího tagu lze konkrétní tray ověřit automaticky:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/live_verify.py \
  192.168.1.18 \
  --tray 0 \
  --expect-brand Prusament \
  --expect-firmware-version V1.4.46
```

Ověřený testovací build má tyto hodnoty:

| Artefakt | Hodnota |
| --- | --- |
| `update.swu` velikost | `116045824` bajtů |
| `update.swu` SHA-256 | `f8d3e126134eedf9fe3201c44c2deea581dbe4547faacfd0165fc1d4fa87b7d2` |
| výsledný `/app/app` SHA-256 | `50714d6cab202bbbb5a1ea7468dc4f8188091272c2ec737e444c7147b938be6f` |
| AMS Lite firmware SHA-256 | `998ba6955f1279b2360069a5e6599c01a03151f837022c79a186f4048d98a5d3` |

U tohoto balíčku prošlo všech 17 testů, audit finální aplikace, audit AMS Lite,
všechny položky `cpio_item_md5`, kontrola podpisu a nezávislé rozbalení SWU.
Konkrétní tiskárna navíc přijala stejný soubor v read-only režimu
`swupdate -c` s návratovým kódem 0.

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
