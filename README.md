<img src="brand/icon.png" alt="Varsom-ikon" width="128" align="right">

# Varsom for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Validate](https://github.com/Jrgenl/ha-varsom/actions/workflows/validate.yml/badge.svg)](https://github.com/Jrgenl/ha-varsom/actions/workflows/validate.yml)

Flom-, jordskred- og snøskredvarsler fra [Varsom.no](https://www.varsom.no/) (NVE) i Home Assistant.

*English summary below.*

## Hva du får

Integrasjonen bruker koordinatene til stedet du velger. Den slår opp kommunen hos Kartverket og henter varslene for kommunen og snøskredregionen fra NVE. Du trenger ingen API-nøkkel.

For hver varseltype du slår på:

| Entitet | Type | Innhold |
|---|---|---|
| *Flomfare i dag* / *i morgen* | sensor | Farenivå 1–4 (grønn, gul, oransje, rød) |
| *Jordskredfare i dag* / *i morgen* | sensor | Farenivå 1–4 |
| *Snøskredfare i dag* / *i morgen* | sensor | Faregrad 0–5 (0 = ikke vurdert) |
| *Flomvarsel* / *Jordskredvarsel* / *Snøskredvarsel* | binærsensor | På når varselet gjelder nå |
| *Farevarsel* | binærsensor | På når minst én av varseltypene er aktiv |

Binærsensorene slår seg på ved **gult nivå (2)** for flom og jordskred, og ved **faregrad 3 (betydelig)** for snøskred. Vil du ha en annen grense, lager du automasjonen mot nivåsensoren i stedet.

Sensorene har disse attributtene: `level_name` (for eksempel `yellow` eller `considerable`), `main_text`, `warning_text`, `advice`, `consequence`, `danger_type`, `causes`, `valid_from`, `valid_to`, `region` og `url`.

Flom og jordskred varsles i perioder fra kl. 07 til kl. 07. «I dag» er perioden som gjelder nå, og «i morgen» er neste periode. Dataene oppdateres hvert 30. minutt.

Varseltekstene er på norsk når Home Assistant er satt til norsk (bokmål eller nynorsk), ellers på engelsk.

## Installasjon

### HACS

1. HACS → ⋮ → **Custom repositories** → legg til `https://github.com/Jrgenl/ha-varsom` med kategori **Integration**.
2. Søk opp **Varsom** og last den ned.
3. Start Home Assistant på nytt.

### Manuelt

Kopier `custom_components/varsom` til `config/custom_components/` og start Home Assistant på nytt.

## Oppsett

**Innstillinger → Enheter og tjenester → Legg til integrasjon → Varsom.**

1. Velg et sted på kartet. Hjemmet ditt er valgt på forhånd, og stedet må ligge i Norge.
2. Velg varseltyper. Snøskred er slått på fra start bare hvis stedet ligger i en region der NVE lager daglige snøskredvarsler.

Du kan endre varseltypene senere under **Konfigurer**. Vil du følge flere steder, legger du til integrasjonen én gang per sted.

## Eksempel på automasjon

```yaml
automation:
  - alias: "Varsle om farevarsel fra Varsom"
    triggers:
      - trigger: state
        entity_id: binary_sensor.varsom_bergen_farevarsel
        to: "on"
    actions:
      - action: notify.mobile_app_telefon
        data:
          title: "Farevarsel"
          message: >
            {% for w in state_attr('binary_sensor.varsom_bergen_farevarsel', 'active_warnings') %}
            {{ w.main_text }}
            {% endfor %}
```

Entitets-ID-ene avhenger av språket og kommunenavnet. Finn dem under enheten *Varsom <kommune>*.

## Datakilder

- NVE sine API-er for [flom](https://api01.nve.no/hydrology/forecast/flood/v1.0.10/swagger/ui/index), [jordskred](https://api01.nve.no/hydrology/forecast/landslide/v1.0.10/swagger/ui/index) og [snøskred](https://api01.nve.no/hydrology/forecast/avalanche/v6.3.0/swagger/ui/index). Dataene er lisensiert under [NLOD](https://data.norge.no/nlod/no/2.0).
- [Kartverket kommuneinfo](https://api.kartverket.no/kommuneinfo/v1/), som brukes til å finne kommunen ut fra koordinatene.

Integrasjonen er ikke laget av eller tilknyttet NVE. Ved fare skal du alltid følge rådene på varsom.no og fra lokale myndigheter.

## Ikon

Ikonet ligger i [`brand/`](brand/): `icon.png` (256×256), `icon@2x.png` (512×512) og kildefilen `icon.svg`. Det er laget for dette prosjektet og er ikke NVE eller Varsom sin logo.

## Utvikling

```bash
pip install -r requirements_test.txt ruff
pytest
ruff check custom_components tests
```

---

## English

A Home Assistant integration for flood, landslide and snow avalanche warnings from [Varsom.no](https://www.varsom.no/) (Norwegian Water Resources and Energy Directorate). Pick a location in Norway. The integration then provides sensors with today's and tomorrow's warning level for each warning type, plus binary sensors that turn on when a warning is in force: yellow or higher for flood and landslide, and level 3 or higher for avalanche. No API key is needed. Install it through HACS as a custom repository and add it from **Settings → Devices & services**.

## License

MIT © Jrgenl
