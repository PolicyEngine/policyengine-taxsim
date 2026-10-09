* Turn a survey extract into TAXSIM input, compute taxes, and merge them back.
* Run from this directory:  do crosswalk.do
* survey_extract.csv is made up; swap in your own file and variable names.
* Stata's shell must find the policyengine-taxsim command (see the guide).

import delimited using "survey_extract.csv", clear asdouble

* 1. Blank amounts mean "none". TAXSIM input has no missing values.
foreach v of varlist wages_head wages_spouse self_emp_head interest dividends ///
    pension social_security unemployment rent_paid property_tax ///
    mortgage_interest charity childcare_cost {
    replace `v' = 0 if missing(`v')
}

* 2. Map each survey concept to a TAXSIM variable. This survey codes married
*    as 1; everyone else files as unmarried. (dividends already has its
*    TAXSIM name.)
generate taxsimid = hh_id
generate year = tax_year
generate statefip = state_fips
generate mstat = cond(marital_status == 1, 2, 1)
generate page = age_head
generate sage = cond(mstat == 2, age_spouse, 0)
replace sage = 0 if missing(sage)
generate depx = cond(missing(num_children), 0, num_children)
generate pwages = wages_head
generate swages = cond(mstat == 2, wages_spouse, 0)
generate psemp = self_emp_head
generate intrec = interest
generate pensions = pension
generate gssi = social_security
generate pui = unemployment
generate rentpaid = rent_paid
generate proptax = property_tax
* Mortgage interest and charity are both non-AMT-preference itemized deductions.
generate mortgage = mortgage_interest + charity
generate childcare = childcare_cost
generate idtl = 2

* 3. Dependent ages: 0 reads as "not given" (age 10), so code infants as 1.
forvalues i = 1/3 {
    generate age`i' = child_age_`i'
    replace age`i' = 1 if age`i' == 0
    replace age`i' = 0 if missing(age`i')
}

* 4. Write the TAXSIM input and run the emulator on it. The policyengine
*    subcommand reads and writes Stata files directly.
preserve
keep taxsimid year statefip mstat page sage depx age1 age2 age3 pwages ///
    swages psemp intrec dividends pensions gssi pui rentpaid proptax ///
    mortgage childcare idtl
save "taxsim_input.dta", replace
! policyengine-taxsim policyengine taxsim_input.dta -o taxsim_results.dta
restore

* 5. Merge the results back on taxsimid and round amounts to cents.
merge 1:1 taxsimid using "taxsim_results.dta", ///
    keepusing(fiitax siitax fica v10) nogenerate
foreach v of varlist fiitax siitax fica v10 {
    replace `v' = round(`v', 0.01)
}
save "survey_with_taxes.dta", replace
list hh_id tax_year fiitax siitax fica v10
