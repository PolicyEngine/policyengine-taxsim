# Turn a survey extract into TAXSIM input, compute taxes, and merge them back.
# Run from this directory:  Rscript crosswalk.R
# survey_extract.csv is made up; swap in your own file and column names.
# Needs only base R and the policyengine-taxsim command on the PATH.

survey <- read.csv("survey_extract.csv")

# 1. Blank amounts mean "none". TAXSIM input has no missing values.
amounts <- c(
  "wages_head", "wages_spouse", "self_emp_head", "interest", "dividends",
  "pension", "social_security", "unemployment", "rent_paid",
  "property_tax", "mortgage_interest", "charity", "childcare_cost"
)
survey[amounts][is.na(survey[amounts])] <- 0

# 2. Map each survey concept to a TAXSIM column. This survey codes married
#    as 1; everyone else files as unmarried.
married <- survey$marital_status == 1
taxsim <- data.frame(
  taxsimid = survey$hh_id,
  year = survey$tax_year,
  statefip = survey$state_fips,  # FIPS codes; SOI codes go in `state`
  mstat = ifelse(married, 2, 1),
  page = survey$age_head,
  sage = ifelse(married & !is.na(survey$age_spouse), survey$age_spouse, 0),
  depx = ifelse(is.na(survey$num_children), 0, survey$num_children),
  pwages = survey$wages_head,
  swages = ifelse(married, survey$wages_spouse, 0),
  psemp = survey$self_emp_head,
  intrec = survey$interest,
  dividends = survey$dividends,
  pensions = survey$pension,
  gssi = survey$social_security,
  pui = survey$unemployment,
  rentpaid = survey$rent_paid,
  proptax = survey$property_tax,
  # Mortgage interest and charity are both non-AMT-preference itemized
  # deductions, so both go in `mortgage`.
  mortgage = survey$mortgage_interest + survey$charity,
  childcare = survey$childcare_cost,
  idtl = 2
)

# 3. Dependent ages: 0 reads as "not given" (age 10), so code infants as 1.
for (slot in 1:3) {
  age <- survey[[paste0("child_age_", slot)]]
  age[!is.na(age) & age == 0] <- 1
  age[is.na(age)] <- 0
  taxsim[[paste0("age", slot)]] <- age
}

# 4. Check before running: the emulator does not reject most bad values.
stopifnot(!anyNA(taxsim), all(taxsim$mstat %in% c(1, 2, 6)))
stopifnot(!anyDuplicated(taxsim$taxsimid))

# 5. Write the TAXSIM input, run the emulator, and read the results.
write.csv(taxsim, "taxsim_input.csv", row.names = FALSE)
status <- system2(
  "policyengine-taxsim",
  c("policyengine", "taxsim_input.csv", "-o", "taxsim_results.csv")
)
stopifnot(status == 0)
results <- read.csv("taxsim_results.csv")

# 6. Merge back on taxsimid and round amounts to cents. Leave taxsimid alone:
#    it is an identifier.
tax_columns <- c("fiitax", "siitax", "fica", "v10")
taxes <- results[c("taxsimid", tax_columns)]
taxes[tax_columns] <- round(taxes[tax_columns], 2)
merged <- merge(survey, taxes, by.x = "hh_id", by.y = "taxsimid", all.x = TRUE)
write.csv(merged, "survey_with_taxes.csv", row.names = FALSE)
print(merged[c("hh_id", "tax_year", "fiitax", "siitax", "fica", "v10")])
