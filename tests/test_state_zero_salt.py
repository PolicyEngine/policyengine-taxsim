"""State-0 records deduct no state or local income or sales tax federally.

TAXSIM state 0 means "no state tax": taxsimtest runs no state calculation for
the record, so its federal return deducts no state or local income or sales
tax. PolicyEngine simulates state 0 in Texas (NO_STATE_TAX_PROXY), and in
Texas both engines take a sales-tax deduction. Until this fix, state-0
itemizers therefore got a federal deduction that TAXSIM does not give them.

Every expected value in this file is taxsimtest output: build cd2026081819
(resources/taxsimtest/taxsimtest-osx.exe, sha256
4a17af9c2adbea27b1e6cce240610aede264e008bcdf64b131e0c81220f62b8c), run with
idtl=2 on exactly the GRID inputs below. Columns not listed (swages
and the rest) were 0. Each case runs at state 0 and at state 44 (Texas).
The state-44 rows show the deduction TAXSIM takes in Texas and does not take
at state 0; for example, mfj_item_2024 itemizes 33,000.00 (property tax plus
mortgage) at state 0 and 35,277.92 at state 44.

Profiles: nonitem (wages only); item (property tax and mortgage above the
standard deduction); tip (property tax and mortgage $500 under the standard
deduction, so only a sales-tax deduction makes the filer itemize); niit
(investment income over the NIIT threshold); item_niit (both); kids_item
(two dependents, ages 5 and 10). Single filers are 40; joint filers are both
45.

Two differences unrelated to SALT are excluded from the fiitax checks:
- 2021-2023: taxsimtest folds the Additional Medicare Tax (`addmed`) into
  `fiitax`; the emulator reports it separately. `v28` (tax before credits)
  excludes it in both and is checked on every record.
- single_kids_item_2024: at taxable income 88,100.00 (equal in both engines),
  taxsimtest's regular tax is 12,739.00 and the emulator's is 12,741.00. The
  $2 gap appears at state 44 too.
"""

import io

import numpy as np
import pandas as pd
import pytest

from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner

# fmt: off
GRID = """\
case,taxsimid,year,state,mstat,page,sage,depx,age1,age2,pwages,dividends,intrec,ltcg,proptax,mortgage,fiitax,v17,v18,v26,v28,niit,addmed
single_nonitem_2021,1,2021,0,1,40,0,0,0,0,60000,0,0,0,0,0,4787.50,0.00,47450.00,60000.00,6187.50,0.00,0.00
single_nonitem_2021,2,2021,44,1,40,0,0,0,0,60000,0,0,0,0,0,4787.50,0.00,47450.00,60000.00,6187.50,0.00,0.00
single_nonitem_2022,3,2022,0,1,40,0,0,0,0,60000,0,0,0,0,0,5968.00,0.00,47050.00,60000.00,5968.00,0.00,0.00
single_nonitem_2022,4,2022,44,1,40,0,0,0,0,60000,0,0,0,0,0,5968.00,0.00,47050.00,60000.00,5968.00,0.00,0.00
single_nonitem_2023,5,2023,0,1,40,0,0,0,0,60000,0,0,0,0,0,5460.50,0.00,46150.00,60000.00,5460.50,0.00,0.00
single_nonitem_2023,6,2023,44,1,40,0,0,0,0,60000,0,0,0,0,0,5460.50,0.00,46150.00,60000.00,5460.50,0.00,0.00
single_nonitem_2024,7,2024,0,1,40,0,0,0,0,60000,0,0,0,0,0,5216.00,0.00,45400.00,60000.00,5216.00,0.00,0.00
single_nonitem_2024,8,2024,44,1,40,0,0,0,0,60000,0,0,0,0,0,5216.00,0.00,45400.00,60000.00,5216.00,0.00,0.00
single_nonitem_2025,9,2025,0,1,40,0,0,0,0,60000,0,0,0,0,0,5071.50,0.00,44250.00,60000.00,5071.50,0.00,0.00
single_nonitem_2025,10,2025,44,1,40,0,0,0,0,60000,0,0,0,0,0,5071.50,0.00,44250.00,60000.00,5071.50,0.00,0.00
single_item_2021,11,2021,0,1,40,0,0,0,0,150000,0,0,0,4000,15000,25461.00,19000.00,131000.00,135000.00,25461.00,0.00,0.00
single_item_2021,12,2021,44,1,40,0,0,0,0,150000,0,0,0,4000,15000,25154.71,20276.23,129723.77,135000.00,25154.71,0.00,0.00
single_item_2022,13,2022,0,1,40,0,0,0,0,150000,0,0,0,4000,15000,25275.50,19000.00,131000.00,135000.00,25275.50,0.00,0.00
single_item_2022,14,2022,44,1,40,0,0,0,0,150000,0,0,0,4000,15000,24965.28,20292.59,129707.41,135000.00,24965.28,0.00,0.00
single_item_2023,15,2023,0,1,40,0,0,0,0,150000,0,0,0,4000,15000,24840.00,19000.00,131000.00,135000.00,24840.00,0.00,0.00
single_item_2023,16,2023,44,1,40,0,0,0,0,150000,0,0,0,4000,15000,24520.83,20329.87,129670.13,135000.00,24520.83,0.00,0.00
single_item_2024,17,2024,0,1,40,0,0,0,0,150000,0,0,0,4000,15000,24482.50,19000.00,131000.00,135000.00,24482.50,0.00,0.00
single_item_2024,18,2024,44,1,40,0,0,0,0,150000,0,0,0,4000,15000,24156.28,20359.25,129640.75,135000.00,24156.28,0.00,0.00
single_item_2025,19,2025,0,1,40,0,0,0,0,150000,0,0,0,4000,15000,24287.00,19000.00,131000.00,135000.00,24287.00,0.00,0.00
single_item_2025,20,2025,44,1,40,0,0,0,0,150000,0,0,0,4000,15000,23956.75,20376.05,129623.95,135000.00,23956.75,0.00,0.00
single_tip_2021,21,2021,0,1,40,0,0,0,0,90000,0,0,0,2000,10050,12787.50,0.00,77450.00,90000.00,12787.50,0.00,0.00
single_tip_2021,22,2021,44,1,40,0,0,0,0,90000,0,0,0,2000,10050,12689.19,12996.85,77003.15,79950.00,12689.19,0.00,0.00
single_tip_2022,23,2022,0,1,40,0,0,0,0,90000,0,0,0,2000,10450,12568.00,0.00,77050.00,90000.00,12568.00,0.00,0.00
single_tip_2022,24,2022,44,1,40,0,0,0,0,90000,0,0,0,2000,10450,12467.02,13408.99,76591.01,79550.00,12467.02,0.00,0.00
single_tip_2023,25,2023,0,1,40,0,0,0,0,90000,0,0,0,2000,11350,12060.50,0.00,76150.00,90000.00,12060.50,0.00,0.00
single_tip_2023,26,2023,44,1,40,0,0,0,0,90000,0,0,0,2000,11350,11953.44,14336.64,75663.36,78650.00,11953.44,0.00,0.00
single_tip_2024,27,2024,0,1,40,0,0,0,0,90000,0,0,0,2000,12100,11641.00,0.00,75400.00,90000.00,11641.00,0.00,0.00
single_tip_2024,28,2024,44,1,40,0,0,0,0,90000,0,0,0,2000,12100,11529.14,15108.44,74891.56,77900.00,11529.14,0.00,0.00
single_tip_2025,29,2025,0,1,40,0,0,0,0,90000,0,0,0,2000,13250,11249.00,0.00,74250.00,90000.00,11249.00,0.00,0.00
single_tip_2025,30,2025,44,1,40,0,0,0,0,90000,0,0,0,2000,13250,11134.40,16270.91,73729.09,76750.00,11134.40,0.00,0.00
single_niit_2021,31,2021,0,1,40,0,0,0,0,250000,0,20000,30000,0,0,71501.75,0.00,287450.00,300000.00,69151.75,1900.00,450.00
single_niit_2021,32,2021,44,1,40,0,0,0,0,250000,0,20000,30000,0,0,71489.63,0.00,287450.00,300000.00,69151.75,1887.88,450.00
single_niit_2022,33,2022,0,1,40,0,0,0,0,250000,0,20000,30000,0,0,70570.50,0.00,287050.00,300000.00,68220.50,1900.00,450.00
single_niit_2022,34,2022,44,1,40,0,0,0,0,250000,0,20000,30000,0,0,70558.23,0.00,287050.00,300000.00,68220.50,1887.73,450.00
single_niit_2023,35,2023,0,1,40,0,0,0,0,250000,0,20000,30000,0,0,68397.00,0.00,286150.00,300000.00,66047.00,1900.00,450.00
single_niit_2023,36,2023,44,1,40,0,0,0,0,250000,0,20000,30000,0,0,68384.37,0.00,286150.00,300000.00,66047.00,1887.37,450.00
single_niit_2024,37,2024,0,1,40,0,0,0,0,250000,0,20000,30000,0,0,66164.75,0.00,285400.00,300000.00,64264.75,1900.00,450.00
single_niit_2024,38,2024,44,1,40,0,0,0,0,250000,0,20000,30000,0,0,66151.84,0.00,285400.00,300000.00,64264.75,1887.09,450.00
single_niit_2025,39,2025,0,1,40,0,0,0,0,250000,0,20000,30000,0,0,64934.75,0.00,284250.00,300000.00,63034.75,1900.00,450.00
single_niit_2025,40,2025,44,1,40,0,0,0,0,250000,0,20000,30000,0,0,64921.68,0.00,284250.00,300000.00,63034.75,1886.93,450.00
single_item_niit_2021,41,2021,0,1,40,0,0,0,0,250000,0,20000,30000,4000,15000,69244.25,19000.00,281000.00,285000.00,66894.25,1900.00,450.00
single_item_niit_2021,42,2021,44,1,40,0,0,0,0,250000,0,20000,30000,4000,15000,68562.37,20913.60,279086.40,285000.00,66224.49,1887.88,450.00
single_item_niit_2022,43,2022,0,1,40,0,0,0,0,250000,0,20000,30000,4000,15000,68453.00,19000.00,281000.00,285000.00,66103.00,1900.00,450.00
single_item_niit_2022,44,2022,44,1,40,0,0,0,0,250000,0,20000,30000,4000,15000,67762.38,20938.13,279061.87,285000.00,65424.65,1887.73,450.00
single_item_niit_2023,45,2023,0,1,40,0,0,0,0,250000,0,20000,30000,4000,15000,66594.50,19000.00,281000.00,285000.00,64244.50,1900.00,450.00
single_item_niit_2023,46,2023,44,1,40,0,0,0,0,250000,0,20000,30000,4000,15000,65883.96,20994.02,279005.98,285000.00,63546.59,1887.37,450.00
single_item_niit_2024,47,2024,0,1,40,0,0,0,0,250000,0,20000,30000,4000,15000,64624.75,19000.00,281000.00,285000.00,62724.75,1900.00,450.00
single_item_niit_2024,48,2024,44,1,40,0,0,0,0,250000,0,20000,30000,4000,15000,63898.51,21038.09,278961.92,285000.00,62011.42,1887.09,450.00
single_item_niit_2025,49,2025,0,1,40,0,0,0,0,250000,0,20000,30000,4000,15000,63797.25,19000.00,281000.00,285000.00,61897.25,1900.00,450.00
single_item_niit_2025,50,2025,44,1,40,0,0,0,0,250000,0,20000,30000,4000,15000,63109.69,21063.27,278936.73,285000.00,61222.75,1886.93,450.00
single_kids_item_2021,51,2021,0,1,40,0,2,5,10,110000,0,0,0,5000,12000,3657.00,0.00,91200.00,110000.00,14457.00,0.00,0.00
single_kids_item_2021,52,2021,44,1,40,0,2,5,10,110000,0,0,0,5000,12000,3657.00,0.00,91200.00,110000.00,14457.00,0.00,0.00
single_kids_item_2022,53,2022,0,1,40,0,2,5,10,110000,0,0,0,5000,12000,10080.00,0.00,90600.00,110000.00,14080.00,0.00,0.00
single_kids_item_2022,54,2022,44,1,40,0,2,5,10,110000,0,0,0,5000,12000,10080.00,0.00,90600.00,110000.00,14080.00,0.00,0.00
single_kids_item_2023,55,2023,0,1,40,0,2,5,10,110000,0,0,0,5000,12000,9325.00,0.00,89200.00,110000.00,13325.00,0.00,0.00
single_kids_item_2023,56,2023,44,1,40,0,2,5,10,110000,0,0,0,5000,12000,9325.00,0.00,89200.00,110000.00,13325.00,0.00,0.00
single_kids_item_2024,57,2024,0,1,40,0,2,5,10,110000,0,0,0,5000,12000,8739.00,0.00,88100.00,110000.00,12739.00,0.00,0.00
single_kids_item_2024,58,2024,44,1,40,0,2,5,10,110000,0,0,0,5000,12000,8739.00,0.00,88100.00,110000.00,12739.00,0.00,0.00
single_kids_item_2025,59,2025,0,1,40,0,2,5,10,110000,0,0,0,5000,12000,7777.50,0.00,86375.00,110000.00,12177.50,0.00,0.00
single_kids_item_2025,60,2025,44,1,40,0,2,5,10,110000,0,0,0,5000,12000,7777.50,0.00,86375.00,110000.00,12177.50,0.00,0.00
mfj_nonitem_2021,61,2021,0,2,45,45,0,0,0,120000,0,0,0,0,0,9575.00,0.00,94900.00,120000.00,12375.00,0.00,0.00
mfj_nonitem_2021,62,2021,44,2,45,45,0,0,0,120000,0,0,0,0,0,9575.00,0.00,94900.00,120000.00,12375.00,0.00,0.00
mfj_nonitem_2022,63,2022,0,2,45,45,0,0,0,120000,0,0,0,0,0,11936.00,0.00,94100.00,120000.00,11936.00,0.00,0.00
mfj_nonitem_2022,64,2022,44,2,45,45,0,0,0,120000,0,0,0,0,0,11936.00,0.00,94100.00,120000.00,11936.00,0.00,0.00
mfj_nonitem_2023,65,2023,0,2,45,45,0,0,0,120000,0,0,0,0,0,10921.00,0.00,92300.00,120000.00,10921.00,0.00,0.00
mfj_nonitem_2023,66,2023,44,2,45,45,0,0,0,120000,0,0,0,0,0,10921.00,0.00,92300.00,120000.00,10921.00,0.00,0.00
mfj_nonitem_2024,67,2024,0,2,45,45,0,0,0,120000,0,0,0,0,0,10432.00,0.00,90800.00,120000.00,10432.00,0.00,0.00
mfj_nonitem_2024,68,2024,44,2,45,45,0,0,0,120000,0,0,0,0,0,10432.00,0.00,90800.00,120000.00,10432.00,0.00,0.00
mfj_nonitem_2025,69,2025,0,2,45,45,0,0,0,120000,0,0,0,0,0,10143.00,0.00,88500.00,120000.00,10143.00,0.00,0.00
mfj_nonitem_2025,70,2025,44,2,45,45,0,0,0,120000,0,0,0,0,0,10143.00,0.00,88500.00,120000.00,10143.00,0.00,0.00
mfj_item_2021,71,2021,0,2,45,45,0,0,0,300000,0,0,0,3000,30000,52572.00,33000.00,267000.00,270000.00,52122.00,0.00,450.00
mfj_item_2021,72,2021,44,2,45,45,0,0,0,300000,0,0,0,3000,30000,52058.69,35138.78,264861.22,270000.00,51608.69,0.00,450.00
mfj_item_2022,73,2022,0,2,45,45,0,0,0,300000,0,0,0,3000,30000,52201.00,33000.00,267000.00,270000.00,51751.00,0.00,450.00
mfj_item_2022,74,2022,44,2,45,45,0,0,0,300000,0,0,0,3000,30000,51681.11,35166.20,264833.80,270000.00,51231.11,0.00,450.00
mfj_item_2023,75,2023,0,2,45,45,0,0,0,300000,0,0,0,3000,30000,51330.00,33000.00,267000.00,270000.00,50880.00,0.00,450.00
mfj_item_2023,76,2023,44,2,45,45,0,0,0,300000,0,0,0,3000,30000,50795.12,35228.67,264771.33,270000.00,50345.12,0.00,450.00
mfj_item_2024,77,2024,0,2,45,45,0,0,0,300000,0,0,0,3000,30000,50165.00,33000.00,267000.00,270000.00,50165.00,0.00,450.00
mfj_item_2024,78,2024,44,2,45,45,0,0,0,300000,0,0,0,3000,30000,49618.30,35277.92,264722.08,270000.00,49618.30,0.00,450.00
mfj_item_2025,79,2025,0,2,45,45,0,0,0,300000,0,0,0,3000,30000,49774.00,33000.00,267000.00,270000.00,49774.00,0.00,450.00
mfj_item_2025,80,2025,44,2,45,45,0,0,0,300000,0,0,0,3000,30000,49220.54,35306.07,264693.93,270000.00,49220.54,0.00,450.00
mfj_tip_2021,81,2021,0,2,45,45,0,0,0,180000,0,0,0,2000,22600,25575.00,0.00,154900.00,180000.00,25575.00,0.00,0.00
mfj_tip_2021,82,2021,44,2,45,45,0,0,0,180000,0,0,0,2000,22600,25335.91,26186.78,153813.22,157400.00,25335.91,0.00,0.00
mfj_tip_2022,83,2022,0,2,45,45,0,0,0,180000,0,0,0,2000,23400,25136.00,0.00,154100.00,180000.00,25136.00,0.00,0.00
mfj_tip_2022,84,2022,44,2,45,45,0,0,0,180000,0,0,0,2000,23400,24892.43,27007.13,152992.87,156600.00,24892.43,0.00,0.00
mfj_tip_2023,85,2023,0,2,45,45,0,0,0,180000,0,0,0,2000,25200,24121.00,0.00,152300.00,180000.00,24121.00,0.00,0.00
mfj_tip_2023,86,2023,44,2,45,45,0,0,0,180000,0,0,0,2000,25200,23867.24,28853.47,151146.53,154800.00,23867.24,0.00,0.00
mfj_tip_2024,87,2024,0,2,45,45,0,0,0,180000,0,0,0,2000,26700,23282.00,0.00,150800.00,180000.00,23282.00,0.00,0.00
mfj_tip_2024,88,2024,44,2,45,45,0,0,0,180000,0,0,0,2000,26700,23020.20,30390.01,149609.99,153300.00,23020.20,0.00,0.00
mfj_tip_2025,89,2025,0,2,45,45,0,0,0,180000,0,0,0,2000,29000,22498.00,0.00,148500.00,180000.00,22498.00,0.00,0.00
mfj_tip_2025,90,2025,44,2,45,45,0,0,0,180000,0,0,0,2000,29000,22231.60,32710.90,147289.10,151000.00,22231.60,0.00,0.00
mfj_niit_2021,91,2021,0,2,45,45,0,0,0,300000,50000,0,0,0,0,63868.00,0.00,324900.00,350000.00,61518.00,1900.00,450.00
mfj_niit_2021,92,2021,44,2,45,45,0,0,0,300000,50000,0,0,0,0,63855.30,0.00,324900.00,350000.00,61518.00,1887.29,450.00
mfj_niit_2022,93,2022,0,2,45,45,0,0,0,300000,50000,0,0,0,0,63305.00,0.00,324100.00,350000.00,60955.00,1900.00,450.00
mfj_niit_2022,94,2022,44,2,45,45,0,0,0,300000,50000,0,0,0,0,63292.13,0.00,324100.00,350000.00,60955.00,1887.13,450.00
mfj_niit_2023,95,2023,0,2,45,45,0,0,0,300000,50000,0,0,0,0,62002.00,0.00,322300.00,350000.00,59652.00,1900.00,450.00
mfj_niit_2023,96,2023,44,2,45,45,0,0,0,300000,50000,0,0,0,0,61988.76,0.00,322300.00,350000.00,59652.00,1886.76,450.00
mfj_niit_2024,97,2024,0,2,45,45,0,0,0,300000,50000,0,0,0,0,60477.00,0.00,320800.00,350000.00,58577.00,1900.00,450.00
mfj_niit_2024,98,2024,44,2,45,45,0,0,0,300000,50000,0,0,0,0,60463.47,0.00,320800.00,350000.00,58577.00,1886.47,450.00
mfj_niit_2025,99,2025,0,2,45,45,0,0,0,300000,50000,0,0,0,0,59534.00,0.00,318500.00,350000.00,57634.00,1900.00,450.00
mfj_niit_2025,100,2025,44,2,45,45,0,0,0,300000,50000,0,0,0,0,59520.30,0.00,318500.00,350000.00,57634.00,1886.30,450.00
mfj_item_niit_2021,101,2021,0,2,45,45,0,0,0,300000,50000,0,0,3000,30000,61972.00,33000.00,317000.00,320000.00,59622.00,1900.00,450.00
mfj_item_niit_2021,102,2021,44,2,45,45,0,0,0,300000,50000,0,0,3000,30000,61397.60,35340.40,314659.60,320000.00,59060.30,1887.29,450.00
mfj_item_niit_2022,103,2022,0,2,45,45,0,0,0,300000,50000,0,0,3000,30000,61601.00,33000.00,317000.00,320000.00,59251.00,1900.00,450.00
mfj_item_niit_2022,104,2022,44,2,45,45,0,0,0,300000,50000,0,0,3000,30000,61019.24,35370.40,314629.60,320000.00,58682.10,1887.13,450.00
mfj_item_niit_2023,105,2023,0,2,45,45,0,0,0,300000,50000,0,0,3000,30000,60730.00,33000.00,317000.00,320000.00,58380.00,1900.00,450.00
mfj_item_niit_2023,106,2023,44,2,45,45,0,0,0,300000,50000,0,0,3000,30000,60131.46,35438.76,314561.24,320000.00,57794.70,1886.76,450.00
mfj_item_niit_2024,107,2024,0,2,45,45,0,0,0,300000,50000,0,0,3000,30000,59565.00,33000.00,317000.00,320000.00,57665.00,1900.00,450.00
mfj_item_niit_2024,108,2024,44,2,45,45,0,0,0,300000,50000,0,0,3000,30000,58953.23,35492.65,314507.35,320000.00,57066.76,1886.47,450.00
mfj_item_niit_2025,109,2025,0,2,45,45,0,0,0,300000,50000,0,0,3000,30000,59174.00,33000.00,317000.00,320000.00,57274.00,1900.00,450.00
mfj_item_niit_2025,110,2025,44,2,45,45,0,0,0,300000,50000,0,0,3000,30000,58554.67,35523.46,314476.54,320000.00,56668.37,1886.30,450.00
mfj_kids_item_2021,111,2021,0,2,45,45,2,5,10,150000,0,0,0,5000,22000,6357.00,27000.00,123000.00,128000.00,18557.00,0.00,0.00
mfj_kids_item_2021,112,2021,44,2,45,45,2,5,10,150000,0,0,0,5000,22000,6006.26,28594.26,121405.74,128000.00,18206.26,0.00,0.00
mfj_kids_item_2022,113,2022,0,2,45,45,2,5,10,150000,0,0,0,5000,22000,14294.00,27000.00,123000.00,128000.00,18294.00,0.00,0.00
mfj_kids_item_2022,114,2022,44,2,45,45,2,5,10,150000,0,0,0,5000,22000,13938.77,28614.70,121385.30,128000.00,17938.77,0.00,0.00
mfj_kids_item_2023,115,2023,0,2,45,45,2,5,10,150000,0,0,0,5000,22000,13521.00,0.00,122300.00,150000.00,17521.00,0.00,0.00
mfj_kids_item_2023,116,2023,44,2,45,45,2,5,10,150000,0,0,0,5000,22000,13309.52,28661.26,121338.74,128000.00,17309.52,0.00,0.00
mfj_kids_item_2024,117,2024,0,2,45,45,2,5,10,150000,0,0,0,5000,22000,12682.00,0.00,120800.00,150000.00,16682.00,0.00,0.00
mfj_kids_item_2024,118,2024,44,2,45,45,2,5,10,150000,0,0,0,5000,22000,12682.00,0.00,120800.00,150000.00,16682.00,0.00,0.00
mfj_kids_item_2025,119,2025,0,2,45,45,2,5,10,150000,0,0,0,5000,22000,11498.00,0.00,118500.00,150000.00,15898.00,0.00,0.00
mfj_kids_item_2025,120,2025,44,2,45,45,2,5,10,150000,0,0,0,5000,22000,11498.00,0.00,118500.00,150000.00,15898.00,0.00,0.00
"""
# fmt: on

INPUT_COLUMNS = [
    "taxsimid", "year", "state", "mstat", "page", "sage", "depx", "age1",
    "age2", "pwages", "dividends", "intrec", "ltcg", "proptax", "mortgage",
]  # fmt: skip
TAXSIM = pd.read_csv(io.StringIO(GRID)).set_index("taxsimid", drop=False)
STATE_0 = TAXSIM[TAXSIM["state"] == 0]
TEXAS = TAXSIM[TAXSIM["state"] == 44]
UNRELATED_FIITAX_GAPS = {"single_kids_item_2024"}


def _inputs(rows):
    records = rows[INPUT_COLUMNS].copy()
    records["idtl"] = 2
    return records.reset_index(drop=True)


@pytest.fixture(scope="module")
def microsim():
    """The whole grid in one batch, so state-0 and Texas rows share chunks."""
    output = PolicyEngineRunner(_inputs(TAXSIM)).run(show_progress=False)
    return output


def _fiitax_comparable(rows):
    """Records whose taxsimtest `fiitax` excludes the Additional Medicare Tax."""
    keep = (rows["addmed"] == 0) | (rows["year"] >= 2024)
    return rows[keep & ~rows["case"].isin(UNRELATED_FIITAX_GAPS)]


def test_grid_documents_the_texas_deduction():
    """In the recorded output, every state-0 itemizer deducts exactly its
    property tax and mortgage, and the same record at state 44 deducts more."""
    itemizers = STATE_0[STATE_0["v17"] > 0]
    assert len(itemizers) == 22
    np.testing.assert_allclose(
        itemizers["v17"], itemizers["proptax"] + itemizers["mortgage"]
    )
    texas = TEXAS.set_index("case").loc[itemizers["case"], "v17"].to_numpy()
    assert (texas > itemizers["v17"].to_numpy()).all()


@pytest.mark.parametrize("column", ["v18", "v26", "v28", "niit"])
def test_microsim_state_zero_matches_taxsim(microsim, column):
    """Taxable income, AMT income, tax before credits and NIIT."""
    out = microsim.set_index("taxsimid").loc[STATE_0.index]
    rows = STATE_0
    if column == "v28":
        rows = rows[~rows["case"].isin(UNRELATED_FIITAX_GAPS)]
        out = out.loc[rows.index]
    np.testing.assert_allclose(out[column], rows[column], atol=1)


def test_microsim_state_zero_fiitax_matches_taxsim(microsim):
    rows = _fiitax_comparable(STATE_0)
    assert len(rows) == 44
    out = microsim.set_index("taxsimid").loc[rows.index]
    np.testing.assert_allclose(out["fiitax"], rows["fiitax"], atol=1)


def test_microsim_state_zero_itemized_deductions_match_taxsim(microsim):
    itemizers = STATE_0[STATE_0["v17"] > 0]
    out = microsim.set_index("taxsimid").loc[itemizers.index]
    np.testing.assert_allclose(out["v17"], itemizers["v17"], atol=1)


def test_microsim_keeps_input_order(microsim):
    """The runner groups output by year; within a year, state-0 and Texas
    records stay interleaved in input order."""
    expected = TAXSIM.sort_values("year", kind="stable")
    assert microsim["taxsimid"].tolist() == expected["taxsimid"].tolist()
    assert microsim["state"].tolist() == expected["state"].tolist()


def _valid_state_rows(records, other_state):
    """Outputs for records whose state is not 0, from a batch where every
    state-0 record is moved to ``other_state``."""
    records = records.copy()
    moved = records["state"] == 0
    records.loc[moved, "state"] = other_state
    output = PolicyEngineRunner(records).run(show_progress=False)
    return output[~output["taxsimid"].isin(records.loc[moved, "taxsimid"])]


def test_texas_records_ignore_state_zero_batch_mates(microsim):
    """Texas records match the same batch with the state-0 records moved to
    Texas too, and still take the sales-tax deduction taxsimtest takes."""
    reference = _valid_state_rows(_inputs(TAXSIM), 44).reset_index(drop=True)
    mixed = microsim[microsim["state"] == 44].reset_index(drop=True)
    pd.testing.assert_frame_equal(mixed, reference[mixed.columns])
    itemizers = TEXAS[TEXAS["v17"] > TEXAS["proptax"] + TEXAS["mortgage"]]
    out = mixed.set_index("taxsimid").loc[itemizers.index]
    assert (out["v17"] > itemizers["proptax"] + itemizers["mortgage"]).all()


def test_valid_state_dependents_ignore_state_zero_batch_mates():
    """Dataset generation decides TAXSIM-32 dependent conversion for the
    whole batch (it is skipped if any record gives a dependent age). A
    California record with dep18=1 but depx=0 therefore gains a dependent
    only if no batch-mate gives an age. A version of this fix that simulated
    state-0 records separately changed its fiitax from 2,816.00 to
    -1,610.66; its results must not depend on a batch-mate's state."""
    ages = {f"age{i}": np.nan for i in range(1, 11)}
    counts = dict(dep13=1, dep17=1, dep18=1)
    common = dict(year=2024, mstat=1, page=35, pwages=40000, idtl=2, **counts)
    records = pd.DataFrame(
        [
            dict(common, taxsimid=1, state=0, depx=1, **{**ages, "age1": 5}),
            dict(common, taxsimid=2, state=5, depx=0, **ages),
        ]
    )
    mixed = PolicyEngineRunner(records.copy()).run(show_progress=False)
    mixed = mixed[mixed["taxsimid"] == 2].reset_index(drop=True)
    reference = _valid_state_rows(records, 44).reset_index(drop=True)
    pd.testing.assert_frame_equal(mixed, reference[mixed.columns])


# taxsimtest, idtl=2, state 0: the mfj_item_2024 record owes 50,165.00 at
# $300,000 of wages and 50,189.00 at $300,100, a marginal rate of 24%.
MFJ_ITEM_2024 = dict(
    taxsimid=1, year=2024, state=0, mstat=2, page=45, sage=45,
    pwages=300000, proptax=3000, mortgage=30000, idtl=2,
)  # fmt: skip
TAXSIM_FIITAX_AT_300100 = 50189.00


def test_state_zero_frate_keeps_the_zeroed_deduction():
    """The marginal-rate perturbation must also deduct no sales tax."""
    base = STATE_0[STATE_0["case"] == "mfj_item_2024"].iloc[0]
    wage_delta = 100.0
    expected = 100 * (TAXSIM_FIITAX_AT_300100 - base["fiitax"]) / wage_delta
    out = PolicyEngineRunner(pd.DataFrame([MFJ_ITEM_2024])).run(show_progress=False)
    assert out["fiitax"].iloc[0] == pytest.approx(base["fiitax"], abs=1)
    assert out["frate"].iloc[0] == pytest.approx(expected, abs=0.01)


def test_disable_salt_frate_keeps_the_zeroed_deduction():
    """--disable-salt zeroes the same deduction for a Texas record, which
    then owes what taxsimtest computes at state 0. The perturbation used to
    drop the override, giving frate = -825.15."""
    record = dict(MFJ_ITEM_2024, state=44)
    out = PolicyEngineRunner(pd.DataFrame([record]), disable_salt=True).run(
        show_progress=False
    )
    assert out["fiitax"].iloc[0] == pytest.approx(50165.00, abs=1)
    assert out["frate"].iloc[0] == pytest.approx(24.0, abs=0.01)


SINGLE_HOUSEHOLD_CASES = STATE_0[
    (STATE_0["year"] == 2024) & ~STATE_0["case"].isin(UNRELATED_FIITAX_GAPS)
]


@pytest.mark.parametrize("taxsimid", SINGLE_HOUSEHOLD_CASES.index)
def test_single_household_state_zero_matches_taxsim(taxsimid):
    row = TAXSIM.loc[taxsimid]
    record = {c: int(row[c]) for c in INPUT_COLUMNS}
    record["idtl"] = 2
    out = export_household(dict(record), generate_household(dict(record)), False, False)
    for column in ["fiitax", "v18", "v26", "v28", "niit"]:
        assert out[column] == pytest.approx(row[column], abs=1), column


def test_generate_household_pins_the_deduction_only_at_state_zero():
    variable = "state_and_local_sales_or_income_tax"
    for state, pinned in [(0, True), (44, False), (5, False)]:
        situation = generate_household(dict(MFJ_ITEM_2024, state=state))
        tax_unit = situation["tax_units"]["your tax unit"]
        assert (variable in tax_unit) is pinned
        if pinned:
            assert tax_unit[variable] == {"2024": 0}
