# RFID brand sync pro CANVAS, displej a Elegoo Slicer

Tento patch rozšiřuje firmware CC1 aplikace ve verzi `1.4.46`, na které stojí aktuální OpenCentauri `0.4.0`.

## Co patch mění

- Originální ELEGOO RFID tagy zůstávají zachované přes původní kód `EEEEEEEE`.
- Vlastní EPC RFID tagy mohou mít čtyřbajtový manufacturer code pro značku filamentu.
- Firmware z tohoto kódu vytvoří interní brand ID.
- Displej i SDCP odpověď pro slicer používají stejný resolver značky.
- Materiálové teploty a typy zůstávají z původní tabulky firmware, aby se neměnila bezpečnostní logika materiálů.

Import do Elegoo Sliceru nejde přes HTTP adresu typu `/user-resource/filament_info`. Slicer si data tahá přes SDCP WebSocket na portu `3030`, konkrétně příkazem `324` s popisem `material info get`.

## Podporované značky

Manufacturer code je nutné zapisovat jako raw EPC bajty, ne jako NDEF text v mobilu.

| Značka | Kód pro tag |
| --- | --- |
| ELEGOO | `EEEEEEEE` |
| Generic | `47454E52` (`GENR`) |
| Prusament | `50525553` (`PRUS`) |
| Bambu Lab | `424D424C` (`BMBL`) |
| Plasty Mladec | `504C4D44` (`PLMD`) |
| eSUN | `4553554E` (`ESUN`) |
| Polymaker | `504F4C59` (`POLY`) |
| SUNLU | `53554E4C` (`SUNL`) |
| Overture | `4F565452` (`OVTR`) |
| Spectrum | `53504543` (`SPEC`) |
| Creality | `43524541` (`CREA`) |

Patch přijímá i opačné pořadí těchto čtyř bajtů, protože některé mobilní zapisovače ukazují EPC slova opačně.

## Technická mapa pro `1.4.46`

- `/app/app` stock SHA-256: `ae693f7dc096da1f734c2972694963286cba20dc8f6afac79f8468139b613129`
- SDCP material command: `Cmd 324`, handler `0x0036cd18`, text `material info get`
- Interní soubor s filamenty: `/user-resource/filament_info`
- Resolver brand ID -> text: hook `0x00291c90`
- Resolver manufacturer code -> brand ID: hook `0x00292014`
- Nový code cave: `0x00450c40` až nejvýše `0x00450fff`
- Stavba JSON položky pro slicer: `0x0036e184`, klíče `brand`, `filament_name`, `filament_code`, `filament_color`, `min_nozzle_temp`, `max_nozzle_temp`

## Ověření

Statická kontrola:

```bash
python3 oc-patches/cc1-app/rfid-brand-sync/analyze_app.py unpacked/squashfs-root/app/app
```

Build patchnutého firmware musí projít přes `patch_planner.py`. Patch při aplikaci odmítne pokračovat, pokud nesedí původní bajty hooků nebo pokud už někdo používá stejnou code cave oblast.

Lokální dry-run plánu bez přepisování `patch_config`:

```powershell
$lines = Get-Content firmware-editions\patched | Where-Object { $_ -match '^[A-Za-z_][A-Za-z0-9_]*=(true|false)$' }
foreach ($line in $lines) { $parts = $line -split '=', 2; Set-Item -Path "env:$($parts[0])" -Value $parts[1] }
python oc-patches\patch_planner.py 1.4.46 --dry-run
```

Po nahrání do tiskárny je potřeba živě ověřit:

- Originální ELEGOO tag zobrazí ELEGOO a původní materiál.
- Vlastní tag s `PRUS` zobrazí Prusament.
- Vlastní tag s `BMBL` zobrazí Bambu Lab.
- Elegoo Slicer po `request_mms_info` dostane přes SDCP `Cmd 324` stejný text v poli `brand`.
- Materiálové teploty zůstávají podle typu filamentu z tagu.
