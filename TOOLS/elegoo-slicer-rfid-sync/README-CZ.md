# Elegoo Slicer: synchronizace RFID značek

[Česky](README-CZ.md) | [English](README-EN.md)

Tento doplněk opravuje import vlastních RFID značek z CANVAS do Elegoo
Sliceru. Je ověřený s Elegoo Slicerem `1.5.2.2`, tiskárnou Centauri Carbon
`1.4.46` a OpenCentauri `0.4.0`.

Celý postup včetně firmware a zápisu NFC je v
[kompletním českém návodu](../../docs/RFID-END-TO-END-CZ.md).

## Proč samotný profil nestačí

Slicer přijme při synchronizaci MMS pouze kompatibilní systémový základní
profil se stejným interním `filament_id` a přesným názvem. Běžný uživatelský
profil `Prusament PLA @ECC` zdědí ID rodiče, a proto jej synchronizace neumí
automaticky vybrat.

Instalátor:

- přidá systémový profil `Prusament PLA @ECC` s ID `PRSPLA00`;
- mapuje CANVAS vendor `Prusament` + typ `PLA` na tento profil;
- mapuje `Generic` + `PETG` na kompatibilní `Generic PETG @Elegoo`;
- doplní kompatibilitu Generic PETG s Centauri Carbon 0.4 mm;
- odstraní pouze konfliktní uživatelskou kopii Prusament profilu;
- před změnou vytvoří úplnou zálohu dotčených souborů.

Originální ELEGOO RFID tagy ani jejich profily se nemění.

## Instalace

1. Zavřete všechny instance Elegoo Sliceru.
2. Spusťte PowerShell.
3. V kořeni repozitáře spusťte:

```powershell
powershell -ExecutionPolicy Bypass -File `
  .\TOOLS\elegoo-slicer-rfid-sync\Install-ElegooSlicerRfidSync.ps1
```

Windows zobrazí UAC. Potvrďte **Ano**, protože instalační profil a webová
mapovací logika leží v `C:\Program Files\ElegooSlicer`.

Potom otevřete Elegoo Slicer, zvolte **Synchronizovat filamenty s MMS** a
potvrďte **Sync**. Pro aktuální testovací sestavu má výsledek být:

| Pozice | Profil |
| --- | --- |
| A1 | ELEGOO PLA |
| A2 | Prusament PLA |
| A3 | Generic PETG |

Zálohy jsou v:

```text
%APPDATA%\ElegooSlicer\rfid-sync-backups\
```

Aktualizace Elegoo Sliceru může soubory v `Program Files` přepsat. Po
aktualizaci spusťte instalátor znovu. Pro jinou verzi než `1.5.2.2` instalátor
z bezpečnostních důvodů skončí bez změn.

## Kontrola

Po instalaci spusťte read-only kontrolu:

```powershell
powershell -ExecutionPolicy Bypass -File `
  .\TOOLS\elegoo-slicer-rfid-sync\Test-ElegooSlicerRfidSync.ps1
```

Kontroluje oba indexy, oba profily, interní ID, kompatibilitu Generic PETG a
JavaScriptové mapování MMS.

## Obnova stavu před instalací

Zavřete slicer a obnovte stav před posledním během instalátoru:

```powershell
powershell -ExecutionPolicy Bypass -File `
  .\TOOLS\elegoo-slicer-rfid-sync\Uninstall-ElegooSlicerRfidSync.ps1
```

Konkrétní starší zálohu lze vybrat parametrem `-BackupPath`.

## Ověřený přenos

Vstup z tiskárny přes SDCP `Cmd 324`:

```text
A2: vendor=Prusament, filamentType=PLA, 190-230 C
```

Data odeslaná synchronizačním dialogem:

```text
filamentId=PRSPLA00
settingId=PRSPLA00
filamentPresetName=Prusament PLA @ECC
```

Po synchronizaci nesmí log obsahovat:

```text
PresetBundle::sync_ams_list: filament_id ... not found
```
