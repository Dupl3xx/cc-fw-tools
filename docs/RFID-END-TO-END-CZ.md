# Kompletní RFID řešení pro CANVAS a Elegoo Slicer

[Česky](RFID-END-TO-END-CZ.md) | [English](RFID-END-TO-END-EN.md)

Tento návod popisuje celý ověřený řetězec od zápisu vlastního NFC tagu přes
CANVAS a displej Centauri Carbon až po automatický výběr profilu v Elegoo
Sliceru.

## Ověřená sestava

| Součást | Ověřená verze |
| --- | --- |
| Tiskárna | ELEGOO Centauri Carbon 1 |
| Zásobník | CANVAS |
| Základní ELEGOO firmware | `1.4.46` |
| OpenCentauri | `0.4.0` |
| Elegoo Slicer | `1.5.2.2` |
| RFID tag | NTAG213 |
| Přenos do sliceru | WebSocket, SDCP `Cmd 324` |

Firmware `1.4.49` není tímto binárním patchem podporovaný. Patcher kontroluje
hash a původní instrukce aplikace a neznámý firmware odmítne.

## Co je součástí repozitáře

### Firmware

- resolver 70 názvů značek;
- zachování všech originálních ELEGOO RFID tagů;
- bezpečný fallback neznámého kódu na Generic;
- 15 hlavních materiálů a 50 podtypů s teplotami z firmware `1.4.46`;
- generátor devíti NTAG213 stránek;
- read-only kontrola dat CANVAS přes SDCP;
- hlášení kompatibilní verze `V1.4.46` Elegoo Sliceru.

### Elegoo Slicer

- systémový profil `Prusament PLA @ECC`;
- interní `filament_id` a `setting_id` `PRSPLA00`;
- mapování `vendor=Prusament` a `filamentType=PLA`;
- oprava kompatibility `Generic PETG @Elegoo` s Centauri Carbon 0.4 mm;
- instalátor, kontrolní skript a obnova ze zálohy;
- česká a anglická dokumentace.

## Počet značek a limity

Firmware nyní obsahuje 70 položek:

- 2 původní: ELEGOO a Generic;
- 68 nových výrobců;
- ID jsou `0x00` až `0x45`.

Nové značky jsou:

```text
Prusament, Bambu Lab, Plasty Mladec, eSUN, Polymaker, SUNLU, Overture,
Spectrum, Creality, Anycubic, Eryone, FormFutura, Hatchbox, Kingroon,
QIDI, Raise3D, Flashforge, Snapmaker, ColorFabb, Fillamentum, Fiberlogy,
Filament PM, BASF Ultrafuse, AzureFilm, Atomic Filament, COEX 3D,
FILL3D, FDplast, GreenGate3D, Numakers, Yumi, MatterHackers, Proto-pasta,
Rosa3D, SainSmart, Siraya Tech, The Filament, ZIRO, Zyltech, JAYO,
Geeetech, iSANMATE, AMOLEN, Duramic 3D, Voxelab, Sovol, Tiertime,
Volumic, Peopoly, Co Print, Afinia, Artillery, CoLiDo, Cubicon,
DeltaMaker, FusRock, Valment, Eolas Prints, Aliz, Extrudr, 3DJake,
Recreus, NinjaTek, taulman3D, Kimya, Verbatim, AddNorth a Noctuo.
```

Aktuální kombinovaný binární build je prakticky zaplněný na 70 značkách:
resolver končí na `0x00451043` a od `0x00451048` je uložená verze pro slicer.
Další značka vyžaduje přemístění tabulky nebo version spoof patche.

Formát používá jeden bajt ID. Současný návrh může po přestavbě resolveru
teoreticky obsahovat 238 položek celkem, tedy ID `0x00` až `0xED`. Hodnota
`0xEE` je rezervovaná původním kódem ELEGOO `EEEEEEEE`.

Autoritativní seznam je v
[`brand_map.json`](../oc-patches/cc1-app/rfid-brand-sync/brand_map.json).

## RFID ID není profilové ID

RFID tag neobsahuje text `PRSPLA00`.

Pro Prusament používá:

```text
stránka 0x10: 36 EE EE EE
stránka 0x11: 02 00 00 00
```

Poslední bajt manufacturer ID `02` znamená Prusament. Hodnota `PRSPLA00`
existuje pouze v Elegoo Sliceru a identifikuje jeho systémový tiskový profil.

Datový tok:

```text
RFID EEEEEE02
  -> firmware: Prusament
  -> displej: Prusament / PLA
  -> SDCP Cmd 324: vendor=Prusament, filamentType=PLA
  -> mapování sliceru: PRSPLA00
  -> profil: Prusament PLA @ECC
```

## Instalace na novou tiskárnu

Tiskárna musí před instalací důvěřovat podpisovému klíči OpenCentauri.
Nahrazení klíče je bezpečnostně citlivý servisní zásah. Nevypínejte tiskárnu
během zápisu a neinstalujte tento build na jiný model nebo firmware.

Ve WSL nebo Linuxu:

```bash
git clone -b codex/rfid-brand-sync \
  https://github.com/Dupl3xx/cc-fw-tools.git
cd cc-fw-tools
git lfs pull
python3 -m pip install -r requirements.txt
sudo ./build.sh 1.4.46
```

Výsledkem je:

```text
update/update.swu
```

Nejdříve pouze nahrát a ověřit:

```bash
./install.sh --stage IP_TISKARNY
```

Potom zapsat neaktivní A/B oddíl:

```bash
./install.sh --flash IP_TISKARNY
```

`install.sh` zjistí aktivní oddíl a vybere opačný oddíl pro nový systém.

## Instalace na nový počítač

1. Nainstalujte Elegoo Slicer `1.5.2.2`.
2. Spusťte jej alespoň jednou a nakonfigurujte Centauri Carbon 0.4 mm.
3. Slicer úplně zavřete.
4. Z kořene repozitáře spusťte:

```powershell
powershell -ExecutionPolicy Bypass -File `
  .\TOOLS\elegoo-slicer-rfid-sync\Install-ElegooSlicerRfidSync.ps1
```

Potvrďte UAC. Instalátor před změnami vytvoří zálohu v:

```text
%APPDATA%\ElegooSlicer\rfid-sync-backups\
```

Ověření instalace:

```powershell
powershell -ExecutionPolicy Bypass -File `
  .\TOOLS\elegoo-slicer-rfid-sync\Test-ElegooSlicerRfidSync.ps1
```

Obnova poslední zálohy:

```powershell
powershell -ExecutionPolicy Bypass -File `
  .\TOOLS\elegoo-slicer-rfid-sync\Uninstall-ElegooSlicerRfidSync.ps1
```

Aktualizace Elegoo Sliceru může upravené soubory v `Program Files` přepsat.
Po aktualizaci spusťte instalátor a kontrolní skript znovu.

## Zápis vlastního RFID tagu

Příklad černého Prusament PLA, 1 kg:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/generate_tag.py \
  --brand Prusament \
  --subtype PLA \
  --color 000000 \
  --weight 1000
```

Příkazy `A2` zapisují raw NTAG213 stránky `0x10` až `0x18`. V NFC Tools
použijte **Other -> Advanced NFC commands**. Data nezapisujte jako NDEF text.

Seznam všech značek:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/generate_tag.py --list-brands
```

Seznam 50 podtypů a jejich teplot:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/generate_tag.py --list-subtypes
```

## Ověření

Kontrola tiskárny bez změny jejího stavu:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/live_verify.py \
  IP_TISKARNY \
  --tray 1 \
  --expect-brand Prusament
```

V Elegoo Sliceru otevřete **Synchronizovat filamenty s MMS** a potvrďte
**Sync**. Ověřený výsledek:

```text
A1 -> ELEGOO PLA
A2 -> Prusament PLA
A3 -> Generic PETG
```

Log sliceru nesmí obsahovat:

```text
PresetBundle::sync_ams_list: filament_id ... not found
```

## Důležité omezení profilů sliceru

Firmware umí přečíst a odeslat všech 70 značek. Doprovodný Windows instalátor
zatím přidává přesný systémový profil pouze pro `Prusament PLA`. Ostatní
značky se zobrazí na tiskárně a odešlou přes SDCP, ale bez dalšího systémového
profilu mohou být ve sliceru namapované na Generic.

Pro každý další přesný profil je potřeba:

1. vytvořit kompatibilní systémový JSON profil;
2. přiřadit unikátní slicerové `filament_id`;
3. přidat profil do `Elegoo.json`;
4. doplnit mapování kombinace výrobce a materiálu;
5. ověřit synchronizaci proti Centauri Carbon 0.4 mm.

To nijak nemění strukturu RFID tagu ani firmware manufacturer ID.

## Soubory

| Cesta | Účel |
| --- | --- |
| `oc-patches/cc1-app/rfid-brand-sync/brand_map.json` | 70 značek a RFID kódy |
| `oc-patches/cc1-app/rfid-brand-sync/material_map.json` | materiály, podtypy a teploty |
| `oc-patches/cc1-app/rfid-brand-sync/generate_tag.py` | generátor NFC příkazů |
| `oc-patches/cc1-app/rfid-brand-sync/live_verify.py` | kontrola SDCP `Cmd 324` |
| `TOOLS/elegoo-slicer-rfid-sync/profiles/Prusament PLA @ECC.json` | profil sliceru |
| `TOOLS/elegoo-slicer-rfid-sync/Install-ElegooSlicerRfidSync.ps1` | instalace |
| `TOOLS/elegoo-slicer-rfid-sync/Test-ElegooSlicerRfidSync.ps1` | kontrola |
| `TOOLS/elegoo-slicer-rfid-sync/Uninstall-ElegooSlicerRfidSync.ps1` | obnova |

## Stav ověření

- 15 regresních testů firmware patche: úspěšné;
- JSON a PowerShell syntaxe: úspěšné;
- opakovaná instalace: idempotentní;
- skutečný RFID scan Prusamentu na tiskárně: úspěšný;
- přenos A2 do Elegoo Sliceru jako Prusament PLA: úspěšný;
- původní ELEGOO tagy: zachované.
