# Real installations with setup_policyengine(). They create a virtual
# environment and install about 90 Python packages, so they run only when
# POLICYENGINETAXSIM_TEST_INSTALL names one of them (CI's r-package-install
# job does):
#
#   pypi            The first policyengine_calculate_taxes() call sets up the
#                   default release from PyPI.
#   offline         Installs from the folder of wheels in
#                   POLICYENGINETAXSIM_TEST_WHEEL_DIR, using the Python in
#                   POLICYENGINETAXSIM_TEST_PYTHON. Run it with no network
#                   access: the test checks that there is none.
#   offline-pinned  The same, pinning both packages to the versions in the
#                   folder.
#
# Run each in its own R process, since reticulate uses one Python per
# session, with RETICULATE_VIRTUALENV_ROOT (and WORKON_HOME) pointing at an
# empty folder so no existing environment is touched.

INSTALL_TEST <- Sys.getenv("POLICYENGINETAXSIM_TEST_INSTALL")

skip_unless_install_test <- function(name) {
  skip_if_not(
    identical(INSTALL_TEST, name),
    paste0("POLICYENGINETAXSIM_TEST_INSTALL is not \"", name, "\"")
  )
  # A fresh environment root, or the test would pass on an old installation.
  expect_identical(reticulate::virtualenv_list(), character(0))
}

# A record for each engine, the earlier year first.
TWO_YEARS <- data.frame(
  year = c(2019, 2023), state = "CA", mstat = 1, pwages = 50000
)

# Both engines ran, in input order: TAXSIM-35's build column has a value for
# the 2019 record only.
expect_both_engines <- function(results) {
  expect_identical(nrow(results), 2L)
  expect_equal(results$year, c(2019, 2023))
  expect_false(anyNA(results$fiitax))
  build <- taxsim_build_column(results)
  expect_length(build, 1)
  expect_identical(!is.na(results[[build]]), c(TRUE, FALSE))
}

# The one version of a package among the wheels in a folder.
wheel_version <- function(wheel_dir, package) {
  files <- list.files(wheel_dir, pattern = paste0("^", package, "-.*\\.whl$"))
  expect_length(files, 1)
  strsplit(files, "-", fixed = TRUE)[[1]][2]
}

expect_no_network <- function() {
  reached <- tryCatch(
    {
      suppressWarnings(readLines("https://pypi.org/simple/pip/", n = 1L))
      TRUE
    },
    error = function(e) FALSE
  )
  expect_false(reached, label = "this test must run without network access; PyPI reachable")
}

test_that("the first calculation installs the default release from PyPI", {
  skip_unless_install_test("pypi")
  messages <- capture_messages(results <- policyengine_calculate_taxes(TWO_YEARS))

  expect_match(messages, "Running one-time setup", all = FALSE)
  expect_match(
    messages,
    paste0("policyengine-taxsim==", .PE_TAXSIM_VERSION, " from PyPI"),
    fixed = TRUE, all = FALSE
  )
  expect_both_engines(results)

  versions <- suppressMessages(policyengine_versions())
  expect_identical(versions$policyengine_taxsim, .PE_TAXSIM_VERSION)
  # The setup reported these versions and how to install them again.
  expect_match(
    messages,
    .reinstall_call(versions$policyengine_taxsim, versions$policyengine_us),
    fixed = TRUE, all = FALSE
  )
  # Asking for other versions now installs nothing, and says so.
  expect_message(
    setup_policyengine(policyengine_us_version = "2.25.2"),
    "nothing was installed"
  )
  expect_identical(
    suppressMessages(policyengine_versions())$policyengine_us,
    versions$policyengine_us
  )
})

test_that("a folder of wheels installs and computes with no network access", {
  skip_unless_install_test("offline")
  wheel_dir <- Sys.getenv("POLICYENGINETAXSIM_TEST_WHEEL_DIR")
  expect_no_network()

  messages <- capture_messages(
    setup_policyengine(
      wheel_dir = wheel_dir,
      python = Sys.getenv("POLICYENGINETAXSIM_TEST_PYTHON")
    )
  )
  expect_match(messages, "policyengine-taxsim from ", fixed = TRUE, all = FALSE)

  # The folder decided the versions.
  versions <- suppressMessages(policyengine_versions())
  expect_identical(
    versions$policyengine_taxsim, wheel_version(wheel_dir, "policyengine_taxsim")
  )
  expect_identical(
    versions$policyengine_us, wheel_version(wheel_dir, "policyengine_us")
  )
  # Calculations need no network either, for either engine.
  expect_both_engines(policyengine_calculate_taxes(TWO_YEARS, show_progress = FALSE))
  expect_no_network()
})

test_that("both packages can be pinned to versions in a folder of wheels", {
  skip_unless_install_test("offline-pinned")
  wheel_dir <- Sys.getenv("POLICYENGINETAXSIM_TEST_WHEEL_DIR")
  taxsim_version <- wheel_version(wheel_dir, "policyengine_taxsim")
  us_version <- wheel_version(wheel_dir, "policyengine_us")
  expect_no_network()

  messages <- capture_messages(
    setup_policyengine(
      policyengine_taxsim_version = taxsim_version,
      policyengine_us_version = us_version,
      wheel_dir = wheel_dir,
      python = Sys.getenv("POLICYENGINETAXSIM_TEST_PYTHON")
    )
  )
  expect_match(
    messages,
    paste0("policyengine-taxsim==", taxsim_version, ", policyengine-us==", us_version),
    fixed = TRUE, all = FALSE
  )
  versions <- suppressMessages(policyengine_versions())
  expect_identical(versions$policyengine_taxsim, taxsim_version)
  expect_identical(versions$policyengine_us, us_version)

  # A version that is not in the folder stops before anything is removed.
  expect_error(
    setup_policyengine(force = TRUE, policyengine_taxsim_version = "0.0.1",
                       wheel_dir = wheel_dir),
    "has no policyengine-taxsim 0.0.1 wheel"
  )
  expect_true(check_policyengine_setup(quiet = TRUE))
})
