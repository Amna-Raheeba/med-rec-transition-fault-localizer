Patient 9: home -> admission -> transfer -> discharge

Charted lists:
  home:
    - apixaban 5, 2x/day
    - losartan 50, 1x/day
    - atenolol 100, 1x/day
    - omeprazole 20, 1x/day
    - spironolactone 50, 1x/day
  admission:
    - apixaban 5, 2x/day
    - atenolol 100, 1x/day
    - spironolactone 25, 1x/day
    - salbutamol 200, 3x/day
  transfer:
    - atenolol 100, 1x/day
    - spironolactone 25, 1x/day
    - salbutamol 200, 3x/day
    - warfarin 2, 1x/day
    - losartan 50, 1x/day
  discharge:
    - atenolol 100, 1x/day
    - spironolactone 25, 1x/day
    - salbutamol 200, 3x/day
    - warfarin 2, 1x/day
    - sertraline 100, 1x/day
    - amlodipine 10, 1x/day

Reason ledger (intentional changes):
  - [home -> admission] dose_change spironolactone -> dose 25 (dose reduced -- target now met)
  - [home -> admission] stop losartan (adverse effect suspected)
  - [transfer -> discharge] start sertraline at dose 100 (started -- guideline-directed therapy)

Ground truth (planted discrepancies):
  - omeprazole: omission, born at home -> admission, present in steps [1, 2, 3] -- survives to discharge
  - salbutamol: addition, born at home -> admission, present in steps [1, 2, 3] -- survives to discharge
  - apixaban: substitution, born at admission -> transfer, present in steps [2, 3] -- survives to discharge (incoming: warfarin)
  - losartan: resurrection, born at admission -> transfer, present in steps [2] -- corrected before discharge
  - amlodipine: addition, born at transfer -> discharge, present in steps [3] -- survives to discharge

Localizer genealogy (lists + ledger only):
  - omeprazole: omission, born at home -> admission -- survives to discharge
  - salbutamol: addition, born at home -> admission -- survives to discharge
  - apixaban: substitution, born at admission -> transfer -- survives to discharge
  - losartan: resurrection, born at admission -> transfer -- gone by discharge
  - amlodipine: addition, born at transfer -> discharge -- survives to discharge
