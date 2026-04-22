## 30. Medical Module In Depth

The Medical tab in Preparedness is a full field-hospital record system. Here is how to use it effectively:

### Setting Up Patients
1. Go to Preparedness > Medical and click **Add Patient**
2. If the person is already in your Contacts, click **Import from Contacts** instead — it copies their name, blood type, and medical notes automatically
3. Fill in: age, weight (kg), sex, blood type, allergies, current medications, and existing conditions
4. Use JSON array format for allergies/medications/conditions: `["Penicillin", "Latex"]`

### Recording Vitals

Click on a patient, then click **Add Vitals**. Enter any or all of:

| Vital | Normal Range (Adult) | Color Coding |
| --- | --- | --- |
| Blood Pressure | 90-140 / 60-90 | Red if systolic >180 or <80 |
| Pulse | 60-100 bpm | Red if >120 or <50 |
| Respiration | 12-20 breaths/min | Red if >30 or <8 |
| Temperature | 97.0-99.5 °F | Red if >103 or <95 |
| SpO2 | 95-100% | Red if <90%, orange if <94% |
| Pain Level | 0 (none) to 10 (worst) | Red if 8+, orange if 5-7 |
| GCS (Glasgow Coma Scale) | 15 (alert) to 3 (unresponsive) | Red if <9 |

> **Tip:** Record vitals every 15-30 minutes during an active medical situation. The trend over time is often more important than any single reading. NOMAD tracks the history so you can see if a patient is improving or declining.

### Drug Interaction Checker

Before giving medications, check for dangerous interactions. The checker covers 26 common interaction pairs including:
- NSAIDs (ibuprofen, aspirin, naproxen) with blood thinners
- Acetaminophen (Tylenol) with alcohol or liver medications
- SSRIs with other serotonergic drugs (serotonin syndrome risk)
- Opioids with benzodiazepines (respiratory depression risk)
- ACE inhibitors with potassium supplements (hyperkalemia risk)

> **Warning:** The drug interaction checker is a reference tool, not a replacement for professional medical advice. In a true emergency, use your best judgment and seek professional care as soon as possible.

### Wound Documentation

The wound log supports 8 wound types (laceration, puncture, abrasion, burn, fracture, crush, bite, other) and 4 severity levels (minor, moderate, severe, critical). Record the body location, description, and treatment given. This creates a timeline that is invaluable if the patient later reaches professional medical care.
