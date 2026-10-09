# Unit tests run without Python. Integration tests run against the
# "policyengine-taxsim" virtual environment and skip when it is not set up.

COLLECTED <- list(
  policyengineTaxsimVersion = "3.0.1",
  policyengineUsVersion = "2.25.2",
  policyengineCoreVersion = "3.32.21",
  taxsimBinary = "taxsimtest-osx.exe",
  taxsimBinaryPath = "/env/share/policyengine_taxsim/taxsimtest/taxsimtest-osx.exe",
  taxsimBinaryBuild = "cd2026081819",
  taxsimBinarySha256 = strrep("a", 64),
  pythonVersion = "3.11.15",
  platform = "macOS-15.0-arm64"
)

LEGACY_FIELDS <- c("policyengine_taxsim", "policyengine_us", "policyengine_core")

test_that("version list keeps the original fields first, then adds the build", {
  versions <- .versions_list(COLLECTED)
  expect_identical(names(versions)[1:3], LEGACY_FIELDS)
  expect_identical(
    versions,
    list(
      policyengine_taxsim = "3.0.1",
      policyengine_us = "2.25.2",
      policyengine_core = "3.32.21",
      taxsim_binary = "taxsimtest-osx.exe",
      taxsim_binary_build = "cd2026081819",
      taxsim_binary_path = COLLECTED$taxsimBinaryPath,
      taxsim_binary_sha256 = strrep("a", 64),
      python_version = "3.11.15",
      platform = "macOS-15.0-arm64"
    )
  )
})

test_that("missing values are 'unknown' in the original fields and NA after", {
  # collect_versions() returns None, converted to NULL, for anything missing.
  collected <- COLLECTED
  collected["policyengineCoreVersion"] <- list(NULL)
  collected["taxsimBinaryBuild"] <- list(NULL)
  collected$taxsimBinaryPath <- NULL
  versions <- .versions_list(collected)
  expect_identical(versions$policyengine_core, "unknown")
  expect_identical(versions$taxsim_binary_build, NA_character_)
  expect_identical(versions$taxsim_binary_path, NA_character_)
  expect_true(all(vapply(versions, is.character, logical(1))))
  expect_true(all(lengths(versions) == 1))
})

test_that("policyengine_versions prints the CLI report and returns the list", {
  fake <- list(
    collect_versions = function() COLLECTED,
    format_version_report = function(versions) {
      paste0("TAXSIM binary:       ", versions$taxsimBinaryBuild)
    }
  )
  local_mocked_bindings(
    check_policyengine_setup = function(...) TRUE,
    .provenance_module = function(...) fake
  )
  local_mocked_bindings(use_virtualenv = function(...) NULL, .package = "reticulate")
  expect_message(
    versions <- policyengine_versions(),
    "TAXSIM binary:       cd2026081819",
    fixed = TRUE
  )
  expect_identical(versions, .versions_list(COLLECTED))
})

test_that("an older policyengine-taxsim still reports its package versions", {
  metadata <- list(version = function(name) {
    if (name == "policyengine-core") stop("PackageNotFoundError")
    c("policyengine-taxsim" = "2.13.0", "policyengine-us" = "1.555.0")[[name]]
  })
  legacy <- .legacy_versions(metadata)
  expect_identical(
    legacy$versions[LEGACY_FIELDS],
    list(
      policyengine_taxsim = "2.13.0",
      policyengine_us = "1.555.0",
      policyengine_core = "unknown"
    )
  )
  expect_true(all(is.na(unlist(legacy$versions[-(1:3)]))))
  lines <- strsplit(legacy$report, "\n", fixed = TRUE)[[1]]
  expect_identical(
    lines[1:3],
    c(
      "policyengine-taxsim: 2.13.0",
      "policyengine-us:     1.555.0",
      "policyengine-core:   unknown"
    )
  )
  expect_match(lines[4], "^TAXSIM binary:       unknown .*setup_policyengine\\(force = TRUE\\)")
})

test_that("a missing provenance module stops with how to update", {
  local_mocked_bindings(
    import = function(...) stop("No module named 'policyengine_taxsim.core.provenance'"),
    .package = "reticulate"
  )
  expect_null(.provenance_module(required = FALSE))
  expect_error(.provenance_module(), "setup_policyengine\\(force = TRUE\\)")
  expect_error(.provenance_module(), "No module named", fixed = TRUE)
})

test_that("provenance paths are checked before a run", {
  for (bad in list(1, TRUE, NA_character_, "", "  ", c("a.json", "b.json"))) {
    expect_error(.check_provenance_path(bad), "must be a file path")
  }
  dir <- withr::local_tempdir()
  expect_error(.check_provenance_path(dir), "is a directory")
  nested <- file.path(dir, "new", "folder", "run.json")
  expect_identical(.check_provenance_path(nested), nested)
  expect_true(dir.exists(dirname(nested)))
  # The check leaves nothing behind.
  expect_identical(list.files(dirname(nested), all.files = TRUE, no.. = TRUE), character(0))
  expect_identical(.check_provenance_path("~/run.json"), path.expand("~/run.json"))
})

test_that("an unwritable provenance folder is rejected", {
  skip_on_os("windows")
  skip_if(Sys.info()[["user"]] == "root", "root can write to read-only folders")
  dir <- withr::local_tempdir()
  Sys.chmod(dir, "0555")
  withr::defer(Sys.chmod(dir, "0755"))
  expect_error(.check_provenance_path(file.path(dir, "run.json")), "Cannot write")
})


# Integration tests ---------------------------------------------------------

skip_without_provenance <- function() {
  ready <- check_policyengine_setup(quiet = TRUE) &&
    reticulate::py_module_available("policyengine_taxsim.core.provenance")
  # CI sets this, so a missing environment fails there instead of skipping.
  if (!ready && identical(Sys.getenv("POLICYENGINETAXSIM_REQUIRE_PYTHON"), "true")) {
    stop("The policyengine-taxsim virtual environment with the provenance ",
         "module is required (POLICYENGINETAXSIM_REQUIRE_PYTHON=true).")
  }
  skip_on_cran()
  skip_if_not(
    ready,
    "no policyengine-taxsim virtual environment with the provenance module"
  )
}

read_record <- function(path) jsonlite::fromJSON(path, simplifyVector = FALSE)

frame_sha256 <- function(frame) {
  csv <- frame$to_csv(index = FALSE, lineterminator = "\n")
  hashlib <- reticulate::import("hashlib", convert = FALSE)
  reticulate::py_to_r(hashlib$sha256(csv$encode("utf-8"))$hexdigest())
}

test_that("policyengine_versions matches the Python package's report", {
  skip_without_provenance()
  prov <- reticulate::import("policyengine_taxsim.core.provenance", convert = FALSE)
  collected <- prov$collect_versions()
  expect_message(
    versions <- policyengine_versions(),
    reticulate::py_to_r(prov$format_version_report(collected)),
    fixed = TRUE
  )
  expected <- reticulate::py_to_r(collected)
  expect_identical(names(versions)[1:3], LEGACY_FIELDS)
  expect_identical(versions$policyengine_taxsim, expected$policyengineTaxsimVersion)
  expect_identical(versions$policyengine_us, expected$policyengineUsVersion)
  expect_identical(versions$taxsim_binary_build, expected$taxsimBinaryBuild)
  # A cd2026081819-style stamp, or the date in an older build's cdate-2025Dec24.
  expect_match(versions$taxsim_binary_build, "^(cd[0-9]{10}|[0-9]{4}[A-Za-z]{3}[0-9]{2})$")
  expect_identical(versions$taxsim_binary_sha256, expected$taxsimBinarySha256)
  # The importlib.metadata versions policyengine_versions() reported before.
  metadata <- reticulate::import("importlib.metadata")
  expect_identical(versions$policyengine_us, metadata$version("policyengine-us"))
  expect_identical(versions$policyengine_core, metadata$version("policyengine-core"))
})

test_that("policyengine_calculate_taxes records provenance without changing results", {
  skip_without_provenance()
  households <- data.frame(
    year = 2023, state = c("CA", "TX"), mstat = 1, pwages = c(50000, 80000)
  )
  path <- file.path(withr::local_tempdir(), "runs", "run.json")
  plain <- policyengine_calculate_taxes(households, show_progress = FALSE)
  recorded <- policyengine_calculate_taxes(
    households, show_progress = FALSE, provenance = path
  )
  # reticulate attaches each run's own pandas index object.
  expect_equal(recorded, plain, ignore_attr = "pandas.index")

  record <- read_record(path)
  expect_identical(record$schemaVersion, 1L)
  expect_identical(record$command, "policyenginetaxsim::policyengine_calculate_taxes")
  expect_identical(record$options$return_all_information, FALSE)
  expect_null(record$options$year)
  expect_type(record$options$scorp_treatment, "character")
  expect_identical(record$engines, list(policyengine = 2L, taxsim = 0L))
  expect_identical(record$input$records, 2L)
  expect_identical(record$output$records, 2L)
  expect_identical(record$input$path, "<R data frame>")
  expect_match(record$input$sha256, "^[0-9a-f]{64}$")
  expect_match(record$output$sha256, "^[0-9a-f]{64}$")
  versions <- policyengine_versions()
  expect_identical(record$policyengineTaxsimVersion, versions$policyengine_taxsim)
  expect_identical(record$policyengineUsVersion, versions$policyengine_us)
  expect_identical(record$taxsimBinaryBuild, versions$taxsim_binary_build)
  expect_identical(
    record$rPackageVersion,
    as.character(utils::packageVersion("policyenginetaxsim"))
  )
  expect_identical(record$rVersion, paste(R.version$major, R.version$minor, sep = "."))
})

test_that("the input hash identifies the data passed to PolicyEngine", {
  skip_without_provenance()
  prov <- .provenance_module()
  dir <- withr::local_tempdir()
  frame <- reticulate::r_to_py(
    data.frame(taxsimid = 1:2, year = 2023L, pwages = c(50000, 1.5)),
    convert = FALSE
  )
  changed <- reticulate::r_to_py(
    data.frame(taxsimid = 1:2, year = 2023L, pwages = c(50000, 2.5)),
    convert = FALSE
  )
  info <- .table_info(prov, frame, "<R data frame>")
  expect_identical(info$sha256, frame_sha256(frame))
  expect_identical(info$records, 2L)
  expect_identical(.table_info(prov, frame, "x")$sha256, info$sha256)
  expect_false(identical(.table_info(prov, changed, "x")$sha256, info$sha256))

  path <- file.path(dir, "record.json")
  .write_provenance(
    prov, path, "test", list(year = NULL, tolerance = 15),
    frame, changed, list(policyengine = 2, taxsim = 0)
  )
  record <- read_record(path)
  expect_identical(record$input$sha256, info$sha256)
  expect_identical(record$engines, list(policyengine = 2L, taxsim = 0L))
  expect_identical(record$options, list(year = NULL, tolerance = 15))
})

test_that("compare_with_taxsim records the TAXSIM binary it ran", {
  skip_without_provenance()
  households <- data.frame(year = 2023, state = "CA", mstat = 1, pwages = 50000)
  path <- file.path(withr::local_tempdir(), "compare.json")
  comparison <- compare_with_taxsim(
    households, show_progress = FALSE, provenance = path
  )
  record <- read_record(path)
  expect_identical(record$command, "policyenginetaxsim::compare_with_taxsim")
  expect_identical(record$options$tolerance, 15)
  expect_identical(record$engines, list(policyengine = 1L, taxsim = 1L))
  expect_identical(record$output$records, nrow(comparison))
  expect_false(is.null(record$taxsimBinaryPath))
  prov <- reticulate::import("policyengine_taxsim.core.provenance")
  expect_identical(
    record$taxsimBinaryBuild, prov$read_binary_build(record$taxsimBinaryPath)
  )
  expect_identical(record$taxsimBinarySha256, prov$sha256_file(record$taxsimBinaryPath))
})
