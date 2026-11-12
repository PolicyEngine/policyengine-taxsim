# Which engine computes each record. The first tests need no Python; the
# integration tests at the end run against the "policyengine-taxsim" virtual
# environment (see helper-python.R).

test_that("every record is counted for exactly one engine", {
  set.seed(20261009)
  for (i in 1:200) {
    years <- sample(1960:2030, sample(1:40, 1), replace = TRUE)
    cutoff <- sample(1990:2030, 1)

    by_year <- .engine_counts(years, cutoff)
    expect_identical(by_year$policyengine + by_year$taxsim, length(years))
    expect_identical(by_year$policyengine, sum(years >= cutoff))
    expect_identical(by_year$taxsim, sum(years < cutoff))
    # A later cutoff never sends more records to PolicyEngine.
    expect_lte(.engine_counts(years, cutoff + 1L)$policyengine, by_year$policyengine)

    forced <- .engine_counts(years, cutoff, "policyengine")
    expect_identical(forced, list(policyengine = length(years), taxsim = 0L))
  }
  expect_identical(
    .engine_counts(c(2020L, 2021L), 2021L), list(policyengine = 1L, taxsim = 1L)
  )
})

test_that("tax years are whole numbers, whatever type the column has", {
  expect_identical(.tax_years(c(2019, 2023)), c(2019L, 2023L))
  expect_identical(.tax_years(c(2019L, 2023L)), c(2019L, 2023L))
  expect_identical(.tax_years(c("2019", " 2023 ")), c(2019L, 2023L))
  expect_identical(.tax_years(factor(c("2023", "2019"))), c(2023L, 2019L))
  # A fractional year counts as the year it is in, as in Python's int().
  expect_identical(.tax_years(c(2021.0, 2020.9)), c(2021L, 2020L))

  for (bad in list(c(2023, NA), c("2023", "twenty"), c(2023, NaN), c(2023, Inf),
                   NA, c(TRUE, FALSE))) {
    expect_error(.tax_years(bad), "Every record needs a tax year")
  }
  expect_error(.tax_years(c(NA, 2023, NA)), "in 2 record(s)", fixed = TRUE)
})

test_that("the progress message says which engine computes the records", {
  expect_identical(
    .engine_message(c(2019L, 2023L, 2024L), 2021L),
    paste0("Calculating taxes: 2 records with PolicyEngine (tax years from ",
           "2021 on), 1 with TAXSIM-35 (earlier years)...")
  )
  expect_identical(
    .engine_message(2023L, 2021L),
    "Calculating taxes for 1 record with PolicyEngine..."
  )
  expect_identical(
    .engine_message(c(2015L, 2019L), 2021L),
    "Calculating taxes for 2 records with TAXSIM-35 (tax years before 2021)..."
  )
  expect_identical(
    .engine_message(c(2023L, 2024L), 2021L, "policyengine"),
    "Calculating taxes for 2 records with PolicyEngine (engine = \"policyengine\")..."
  )
  expect_identical(
    .engine_message(c(2019L, 2023L), 2021L, "policyengine"),
    paste0("Calculating taxes for 2 records with PolicyEngine (engine = ",
           "\"policyengine\"); 1 of them is for tax years before 2021, which ",
           "engine = \"auto\" computes with TAXSIM-35...")
  )
})


# policyengine_calculate_taxes() with Python recorded ---------------------------

# Replaces Python with a recorder: StitchedRunner returns one row per record.
local_recorded_runners <- function(has_stitched_runner = TRUE,
                                   env = parent.frame()) {
  calls <- new.env()
  calls$log <- character(0)
  runner <- function(name) {
    function(df, ...) {
      calls$log <- c(calls$log, name)
      calls$df <- df
      calls$arguments <- list(...)
      list(run = function(show_progress = TRUE) {
        calls$show_progress <- show_progress
        data.frame(taxsimid = df$taxsimid, year = df$year, fiitax = 0)
      })
    }
  }
  runners <- list(PolicyEngineRunner = runner("PolicyEngineRunner"))
  if (has_stitched_runner) {
    runners$StitchedRunner <- runner("StitchedRunner")
  }
  local_mocked_bindings(
    check_policyengine_setup = function(...) TRUE,
    .pe_min_year = function() 2021L,
    .env = env
  )
  local_mocked_bindings(
    use_virtualenv = function(...) NULL,
    import = function(module, ...) if (module == "pandas") list() else runners,
    r_to_py = function(x, ...) x,
    py_to_r = function(x, ...) x,
    py_has_attr = function(x, name) name %in% names(x),
    .package = "reticulate",
    .env = env
  )
  calls
}

RECORDS <- data.frame(
  year = c(2023, 2019, 2021),
  state = c("CA", "TX", "NY"),
  mstat = 1,
  pwages = c(50000, 80000, 60000)
)

test_that("records go to StitchedRunner, as on the command line", {
  calls <- local_recorded_runners()
  expect_message(
    results <- policyengine_calculate_taxes(RECORDS),
    paste0("Calculating taxes: 2 records with PolicyEngine (tax years from ",
           "2021 on), 1 with TAXSIM-35 (earlier years)..."),
    fixed = TRUE
  )
  # StitchedRunner with its own cutoff year; PolicyEngineRunner is not called.
  expect_identical(calls$log, "StitchedRunner")
  expect_identical(calls$arguments, list())
  expect_identical(calls$df$year, c(2023L, 2019L, 2021L))
  expect_identical(calls$df$state, c(5L, 44L, 33L))
  expect_identical(calls$df$idtl, c(0L, 0L, 0L))
  expect_s3_class(results, "tbl_df")
  expect_identical(results$taxsimid, 1:3)
})

test_that("engine = 'policyengine' computes every year with PolicyEngine", {
  calls <- local_recorded_runners()
  expect_message(
    policyengine_calculate_taxes(RECORDS, engine = "policyengine"),
    "3 records with PolicyEngine (engine = \"policyengine\"); 1 of them is",
    fixed = TRUE
  )
  # A first PolicyEngine year of 0: no record is early enough for TAXSIM-35.
  expect_identical(calls$log, "StitchedRunner")
  expect_identical(calls$arguments, list(pe_min_year = 0L))
})

test_that("idtl comes from return_all_information, not from the data", {
  calls <- local_recorded_runners()
  records <- cbind(RECORDS, idtl = 5)
  suppressMessages(policyengine_calculate_taxes(records))
  expect_identical(calls$df$idtl, c(0L, 0L, 0L))
  suppressMessages(policyengine_calculate_taxes(records, return_all_information = TRUE))
  expect_identical(calls$df$idtl, c(2L, 2L, 2L))
})

test_that("show_progress = FALSE is silent and passed to the runner", {
  calls <- local_recorded_runners()
  expect_no_message(policyengine_calculate_taxes(RECORDS, show_progress = FALSE))
  expect_identical(calls$show_progress, FALSE)
})

test_that("the year argument decides the engine when it overrides the data", {
  calls <- local_recorded_runners()
  expect_message(
    policyengine_calculate_taxes(RECORDS, year = 2018),
    "Calculating taxes for 3 records with TAXSIM-35 (tax years before 2021)...",
    fixed = TRUE
  )
  expect_identical(calls$df$year, c(2018L, 2018L, 2018L))
})

test_that("bad arguments stop before anything is computed", {
  calls <- local_recorded_runners()
  expect_error(policyengine_calculate_taxes(RECORDS, engine = "taxsim"),
               "should be one of")
  records <- RECORDS
  records$year[2] <- NA
  expect_error(policyengine_calculate_taxes(records), "Every record needs a tax year")
  expect_identical(calls$log, character(0))
})

test_that("an installed policyengine-taxsim without StitchedRunner says to update", {
  calls <- local_recorded_runners(has_stitched_runner = FALSE)
  for (engine in c("auto", "policyengine")) {
    expect_error(
      policyengine_calculate_taxes(RECORDS, engine = engine),
      "has no StitchedRunner.*setup_policyengine\\(force = TRUE\\)"
    )
  }
  expect_identical(calls$log, character(0))
})


# Integration tests ---------------------------------------------------------------

# Years on both sides of 2021, single and joint filers, with and without
# dependents, not in year order.
MIXED <- data.frame(
  taxsimid = c(11, 12, 13, 14, 15),
  year = c(2023, 2019, 2021, 2015, 2023),
  state = c("CA", "TX", "NY", "CA", "TX"),
  mstat = c(1, 2, 1, 1, 2),
  page = c(40, 45, 30, 35, 38),
  sage = c(0, 43, 0, 0, 36),
  pwages = c(50000, 80000, 60000, 30000, 120000),
  swages = c(0, 40000, 0, 0, 30000),
  depx = c(0, 2, 0, 1, 1),
  age1 = c(0, 8, 0, 4, 3),
  age2 = c(0, 5, 0, 0, 0)
)
BEFORE_2021 <- MIXED$year < 2021

# The same records through the command line: written to CSV with the state
# codes and idtl the R function sets, run with the `policyengine` subcommand.
command_line_results <- function(records, idtl) {
  dir <- withr::local_tempdir()
  input <- file.path(dir, "input.csv")
  output <- file.path(dir, "output.csv")
  records <- .convert_state_codes(records)
  records$idtl <- idtl
  utils::write.csv(records, input, row.names = FALSE)
  status <- system2(
    reticulate::virtualenv_python(.get_pe_envname()),
    c("-m", "policyengine_taxsim.cli", "policyengine", shQuote(input),
      "-o", shQuote(output)),
    stdout = FALSE, stderr = FALSE
  )
  expect_identical(status, 0L)
  utils::read.csv(output, check.names = FALSE)
}

# The command line writes numbers as text, so compare to that precision.
expect_same_results <- function(results, expected) {
  results <- as.data.frame(results)
  expect_identical(names(results), names(expected))
  expect_identical(nrow(results), nrow(expected))
  for (column in names(expected)) {
    expect_equal(
      as.numeric(results[[column]]), as.numeric(expected[[column]]),
      tolerance = 1e-6, label = column
    )
  }
}

test_that("R returns what the command line returns for the same records", {
  skip_without_policyengine()
  basic <- policyengine_calculate_taxes(MIXED, show_progress = FALSE)
  expect_same_results(basic, command_line_results(MIXED, idtl = 0))

  full <- policyengine_calculate_taxes(
    MIXED, return_all_information = TRUE, show_progress = FALSE
  )
  expect_same_results(full, command_line_results(MIXED, idtl = 2))
  expect_gt(ncol(full), ncol(basic))
})

test_that("TAXSIM-35 computes records before 2021 and PolicyEngine the rest", {
  skip_without_policyengine()
  by_year <- as.data.frame(policyengine_calculate_taxes(MIXED, show_progress = FALSE))
  forced <- as.data.frame(
    policyengine_calculate_taxes(MIXED, engine = "policyengine", show_progress = FALSE)
  )

  # One row for each record, in input order, for both engines.
  expect_equal(by_year$taxsimid, MIXED$taxsimid)
  expect_equal(by_year$year, MIXED$year)
  expect_equal(forced$taxsimid, MIXED$taxsimid)
  expect_equal(forced$year, MIXED$year)

  # TAXSIM-35's build column has a value exactly for the records before 2021;
  # with engine = "policyengine" no record reaches TAXSIM-35.
  build <- taxsim_build_column(by_year)
  expect_length(build, 1)
  expect_identical(!is.na(by_year[[build]]), BEFORE_2021)
  expect_length(taxsim_build_column(forced), 0)

  # The default does not change results for 2021 and later.
  expect_equal(by_year[!BEFORE_2021, names(forced)], forced[!BEFORE_2021, ],
               ignore_attr = TRUE)

  # engine = "policyengine" returns what this function returned before it
  # routed by year: PolicyEngineRunner's results for the same records.
  records <- .convert_state_codes(MIXED)
  records$idtl <- 0L
  runners <- reticulate::import("policyengine_taxsim.runners")
  direct <- runners$PolicyEngineRunner(reticulate::r_to_py(records))$run(
    show_progress = FALSE
  )
  direct <- direct[match(MIXED$taxsimid, direct$taxsimid), ]
  expect_equal(forced, direct, ignore_attr = TRUE)
})
