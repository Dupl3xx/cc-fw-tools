# Oprava identity firmware pro Elegoo Slicer (CC1 1.4.46)

[Česky](README-CZ.md) | [English](README.md)

## Proč je patch potřeba

Elegoo Slicer před načtením filamentů z CANVAS kontroluje SDCP pole
`FirmwareVersion`. OpenCentauri hodnota `V0.4.0-d` nebyla v Elegoo Sliceru
`1.5.2.2` přijata jako podporovaná verze, takže synchronizace filamentů nebyla
dostupná.

Nejde o uživatelský název tiskárny. Jméno `Centauri Carbon` zůstává beze
změny. Patch upravuje pouze verzi odeslanou Sliceru.

## Výsledek

Slicer ve všech třech komunikačních cestách obdrží:

```text
FirmwareVersion=V1.4.46
```

Upravují se:

| Cesta | Adresa instrukce | Použití |
| --- | --- | --- |
| UDP discovery | `0x0036859c` | nalezení tiskárny v síti |
| WebSocket attributes | `0x0036a98c` | atributy po připojení |
| SDCP `Cmd 1` | `0x0037e80c` | přímý požadavek na atributy |

Skutečný řetězec OpenCentauri na `0x00409a38` zůstává nedotčený. Lokální
displej, logy a OTA proto nadále používají skutečnou verzi.

## Binární implementace

Patch uloží řetězec `1.4.46\0` do volného prostoru na VA `0x00451048` a tři
dvojice instrukcí `movw/movt` přesměruje z původní adresy `0x00409a38` na
novou adresu.

Použité bajty:

```text
původní: 38 3A 09 E3 40 30 40 E3
nové:    48 30 01 E3 45 30 40 E3
řetězec: 31 2E 34 2E 34 36 00
```

Patcher před zápisem kontroluje původní instrukce i prázdný cílový prostor.
Při jiném firmware nebo kolizi skončí bez částečné změny aplikace.

## Zapnutí v sestavení

Oprava je zapnutá v `firmware-editions/patched`:

```text
RFID_BRAND_SYNC=true
SPOOF_SLICER_FIRMWARE_VERSION=true
```

Soubor `patch.toml` obsahuje:

```toml
after = ["rfid_brand_sync"]
compatible_versions = ["1.4.46"]
```

Pořadí je důležité, protože tabulka RFID končí na `0x00451043` a řetězec
verze začíná na `0x00451048`.

## Ověření

Regresní test kontroluje:

- zapnutí obou patchů ve výsledné edici;
- správné pořadí a kompatibilní firmware;
- čtení hodnoty `FirmwareVersion` živým verifierem;
- změnu všech tří pointerů;
- přesný řetězec `1.4.46\0`;
- nepřekrytí tabulky RFID;
- odmítnutí obsazeného cílového prostoru bez částečného zápisu.

Živě ověřený výsledek v Elegoo Sliceru `1.5.2.2`:

```text
Centauri Carbon V1.4.46
A1 -> ELEGOO PLA
A2 -> Prusament PLA
A3 -> Generic PETG
```

Patch podporuje pouze základní ELEGOO firmware `1.4.46`. Na firmware `1.4.49`
se nesmí použít.
