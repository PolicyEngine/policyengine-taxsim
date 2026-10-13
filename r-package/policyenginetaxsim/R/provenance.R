# Version reports and provenance sidecars, from the Python package's
# policyengine_taxsim.core.provenance module: the same facts
# `policyengine-taxsim --version` prints and `--provenance PATH` records.

.PROVENANCE_MODULE <- "policyengine_taxsim.core.provenance"


#' Import the Python provenance module
#'
#' @param required If TRUE, stop when the installed policyengine-taxsim has
#'   no provenance module; if FALSE, return NULL.
#' @return The module, imported with `convert = FALSE`, or NULL.
#' @keywords internal
.provenance_module <- function(required = TRUE) {
  tryCatch(
    reticulate::import(.PROVENANCE_MODULE, convert = FALSE),
    error = function(e) {
      if (!required) {
        return(NULL)
      }
      stop(
        "Could not import ", .PROVENANCE_MODULE, " (", conditionMessage(e),
        "). policyengine-taxsim releases before it do not record ",
        "provenance; update with setup_policyengine(force = TRUE).",
        call. = FALSE
      )
    }
  )
}


#' Convert `collect_versions()` output to the list `policyengine_versions()`
#' returns
#'
#' The first three fields keep their names and their "unknown" value for a
#' package that is not installed. The others are NA when unavailable.
#'
#' @param versions A named list converted from `collect_versions()`.
#' @keywords internal
.versions_list <- function(versions) {
  value <- function(key, missing = NA_character_) {
    x <- versions[[key]]
    if (is.null(x)) missing else as.character(x)
  }
  list(
    policyengine_taxsim = value("policyengineTaxsimVersion", "unknown"),
    policyengine_us = value("policyengineUsVersion", "unknown"),
    policyengine_core = value("policyengineCoreVersion", "unknown"),
    taxsim_binary = value("taxsimBinary"),
    taxsim_binary_build = value("taxsimBinaryBuild"),
    taxsim_binary_path = value("taxsimBinaryPath"),
    taxsim_binary_sha256 = value("taxsimBinarySha256"),
    python_version = value("pythonVersion"),
    platform = value("platform")
  )
}


#' Versions from importlib.metadata, for a policyengine-taxsim without the
#' provenance module
#'
#' @param metadata Python's importlib.metadata module.
#' @return A list: `versions`, shaped like `.versions_list()` output, and the
#'   `report` lines to print.
#' @keywords internal
.legacy_versions <- function(metadata = reticulate::import("importlib.metadata")) {
  version <- function(name) {
    tryCatch(metadata$version(name), error = function(e) "unknown")
  }
  versions <- .versions_list(list(
    policyengineTaxsimVersion = version("policyengine-taxsim"),
    policyengineUsVersion = version("policyengine-us"),
    policyengineCoreVersion = version("policyengine-core")
  ))
  rows <- c(
    "policyengine-taxsim" = versions$policyengine_taxsim,
    "policyengine-us" = versions$policyengine_us,
    "policyengine-core" = versions$policyengine_core,
    "TAXSIM binary" = paste(
      "unknown (this policyengine-taxsim predates the build report;",
      "update with setup_policyengine(force = TRUE))"
    )
  )
  width <- max(nchar(names(rows))) + 1
  list(
    versions = versions,
    report = paste(
      sprintf("%-*s %s", width, paste0(names(rows), ":"), rows),
      collapse = "\n"
    )
  )
}


#' Check a provenance path before a run
#'
#' Fails before a long run, not after it, when the file cannot be written.
#'
#' @param path The `provenance` argument.
#' @return The path with `~` expanded.
#' @keywords internal
.check_provenance_path <- function(path) {
  if (!is.character(path) || length(path) != 1 || is.na(path) ||
      !nzchar(trimws(path))) {
    stop("`provenance` must be a file path for the provenance JSON.",
         call. = FALSE)
  }
  path <- path.expand(path)
  if (dir.exists(path)) {
    stop("`provenance` is a directory (", path, "); give a file path.",
         call. = FALSE)
  }
  directory <- dirname(path)
  dir.create(directory, recursive = TRUE, showWarnings = FALSE)
  probe <- tempfile("provenance-check-", tmpdir = directory)
  writable <- suppressWarnings(file.create(probe))
  unlink(probe)
  if (!writable || (file.exists(path) && file.access(path, 2) != 0)) {
    stop("Cannot write the provenance file ", path, ".", call. = FALSE)
  }
  path
}


#' Describe a table for a provenance record
#'
#' @param prov The provenance module.
#' @param frame A pandas DataFrame, as a Python object without automatic
#'   conversion (`r_to_py(x, convert = FALSE)`).
#' @param label What the table is, recorded as its path.
#' @return A list with `path`, the SHA-256 of the table written as CSV by
#'   pandas (no index, "\\n" line endings) and its row count in `records`.
#' @keywords internal
.table_info <- function(prov, frame, label) {
  csv <- frame$to_csv(index = FALSE, lineterminator = "\n")
  list(
    path = label,
    sha256 = reticulate::py_to_r(prov$sha256_bytes(csv$encode("utf-8"))),
    records = reticulate::py_len(frame)
  )
}


#' Write a provenance sidecar for an R run
#'
#' Builds the record with the Python package's `build_provenance()`, the
#' function behind the CLI's `--provenance`, and adds the R package and R
#' versions.
#'
#' @param prov The provenance module.
#' @param path Where to write the JSON, checked by `.check_provenance_path()`.
#' @param command The R function that ran.
#' @param options A named list of the options the run used.
#' @param input,output pandas DataFrames, as Python objects.
#' @param engines A named list: records computed by policyengine and taxsim.
#' @param taxsim_path The TAXSIM binary the run used, or NULL for the
#'   bundled one.
#' @keywords internal
.write_provenance <- function(prov, path, command, options, input, output,
                              engines, taxsim_path = NULL) {
  record <- prov$build_provenance(
    command,
    options,
    .table_info(prov, input, "<R data frame>"),
    .table_info(prov, output, "<R data frame>"),
    lapply(engines, as.integer),
    taxsim_path
  )
  reticulate::py_set_item(
    record, "rPackageVersion",
    as.character(utils::packageVersion("policyenginetaxsim"))
  )
  reticulate::py_set_item(
    record, "rVersion", paste(R.version$major, R.version$minor, sep = ".")
  )
  prov$write_provenance(path, record)
  invisible(path)
}
