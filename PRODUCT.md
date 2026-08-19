# Confdence

Working name for the Quebec patient-owned health record.

You hold the facts. You hand them to a doctor. The clinic does not become the source of truth.

The blood type example is the product, not a metaphor: a stable fact, checked once, forgotten by every new door you walk through.

## What this is

A record the patient owns. Durable facts first — blood type, allergies, meds, conditions — plus a way to show a doctor those facts on purpose, for a limited time.

Same ownership idea as a personal finance ledger: the institution has a copy for its job. You have the original.

## Why Quebec

Two systems, neither of them yours:

- **Dossier Santé Québec (DSQ / QHR)** — the provincial chart. Providers can open it. You cannot.
- **Carnet Santé Québec** — labs, meds, imaging, fee-for-service visits, RAMQ reimbursements, who looked at your file. View in a government portal. Not a thing you carry into a walk-in and hand over.

Law 5 (in force July 2024) even says health information should follow the person, not the building. The portals did not catch up.

So you get your blood typed again. And again.

## What this is not

- Not a replacement for DSQ or Carnet Santé
- Not a hospital chart
- Not a transfusion authority. A hospital will still type-and-screen before giving blood. That is correct practice. The app is for every other door that currently shrugs.
- Not a maternity / birthing product. Separate app at `/Users/apawinski/dev/welcome`. Do not merge them.

## First slice (what is in this folder)

Your record, on a device, no server required:

1. Open `confdence.html` (or `static/index.html` from the folder)
2. Name is Alexander Pawinski. Blood type, allergies, meds start empty — do not invent them
3. Edit the facts — blood type, allergies, meds, hospitals, clinicians. They stay in this browser
4. **Montrer à un médecin** — hold the phone out
5. **Imprimer / PDF** — one page, Safari “Save as PDF”
6. **Enregistrer la carte** — a standalone HTML file you can AirDrop / keep in Files
7. **Déclarer un incident** — Grafana-style: severity, commander, a timeline of notes and steps. Notify opens Messages; it does not send by itself.

French-first. English toggle. Nothing is sent.

The optional FastAPI share-link path still exists. It is not how you show a doctor.

**Production** is the `static/` folder on HTTPS (manifest + service worker). Facts still live in the phone’s browser. Do not deploy the SQLite API with real health information.

## Risks (do not sand these off)

- **Law 5 + Law 25.** Hosting real Quebec health information is a regulated activity, not a side project. Local dogfood only until this is a real decision.
- **Self-reported blood type can be wrong.** UI must say so. Source + date stay visible.
- **No public DSQ/Carnet API** to import from. Anything that looks like a government sync is fake until it is not.
- **Full RAMQ number (NAM) is an identifier.** Do not collect it in v0.

## Open readings

"Patients should own their financial data" landed two ways:

1. The CashSnap sentence applied to health: you own the record.
2. Also own the money side — RAMQ claims, reimbursements, out-of-pocket.

First slice is (1). (2) is a later surface if you want it. Carnet already lists reimbursements; it does not give you the file.

## Later (not started)

- Import a lab PDF / photo and file the fact under the patient's name
- Family record (Goku) with a parent as holder
- Real auth, Quebec data residency, audit log of who saw a share
- FHIR export for a clinic that can take it
