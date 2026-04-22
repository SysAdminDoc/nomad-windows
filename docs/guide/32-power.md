## 32. Power Management Guide

The Power tab helps you track your energy infrastructure and project how long you can sustain operations.

### Device Registry

Register every power device you own. Each type has specific fields:

| Device Type | Key Specs to Record |
| --- | --- |
| Solar Panel | Wattage, voltage, type (monocrystalline, polycrystalline, thin-film) |
| Battery | Capacity (Ah), voltage, type (lead-acid, LiFePO4, lithium-ion, AGM) |
| Charge Controller | Amperage, type (MPPT, PWM), max voltage |
| Inverter | Wattage (continuous and peak), input voltage, output (120V/240V) |
| Generator | Wattage, fuel type, fuel capacity, runtime per tank |

### Power Logging

Log daily readings: battery voltage, state of charge (SOC%), solar watts produced, solar watt-hours today, load watts consumed, load watt-hours today, and whether the generator is running. Over time, this builds a picture of your energy balance.

### Autonomy Dashboard

The dashboard calculates your **net daily energy balance** (solar production minus consumption) and projects how many days your batteries will last:
- **Green gauge** — More than 7 days of autonomy. You are energy-sustainable.
- **Orange gauge** — 3-7 days. Start reducing consumption or increasing production.
- **Red gauge** — Less than 3 days. Critical — activate generator or drastically cut loads.
