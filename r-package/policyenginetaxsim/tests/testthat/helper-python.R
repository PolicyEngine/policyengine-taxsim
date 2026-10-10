# Tests that call Python run against the "policyengine-taxsim" virtual
# environment and skip when it is not set up. CI sets
# POLICYENGINETAXSIM_REQUIRE_PYTHON, so a missing environment fails there
# instead of skipping.
skip_without_policyengine <- function() {
  ready <- check_policyengine_setup(quiet = TRUE)
  if (!ready && identical(Sys.getenv("POLICYENGINETAXSIM_REQUIRE_PYTHON"), "true")) {
    stop("The policyengine-taxsim virtual environment is required ",
         "(POLICYENGINETAXSIM_REQUIRE_PYTHON=true).")
  }
  testthat::skip_on_cran()
  testthat::skip_if_not(ready, "no policyengine-taxsim virtual environment")
}

# The column TAXSIM-35 names for its build, such as "cd2026081819" (or
# "cdate-2025Dec24" in builds before June 2026). Only records TAXSIM-35
# computed have a value in it.
taxsim_build_column <- function(results) {
  grep("^(cd[0-9]{10}|cdate-.*)$", names(results), value = TRUE)
}
