#' Calculate US Income Taxes using PolicyEngine
#'
#' Calculates federal and state income taxes for US tax units. This function
#' provides a TAXSIM-compatible interface, accepting the same input variables
#' and returning similar output. Like the `policyengine-taxsim` command line,
#' it computes tax years from 2021 on with the PolicyEngine microsimulation
#' model and earlier years with the TAXSIM-35 program bundled with the Python
#' package. See Details.
#'
#' @param .data A data frame containing tax unit information. See Details for
#'   required and optional columns.
#' @param return_all_information Logical. If TRUE, returns detailed tax
#'   calculation information (44+ variables). If FALSE (default), returns only
#'   basic tax amounts (federal, state, FICA).
#' @param year Optional. Override the tax year for all records. If NULL (default),
#'   uses the 'year' column from the data.
#' @param show_progress Logical. If TRUE (default), shows progress messages
#'   during calculation.
#' @param engine Which program computes each record. `"auto"` (default) uses
#'   PolicyEngine for tax years from 2021 on and TAXSIM-35 for earlier years,
#'   as the command line does. `"policyengine"` uses PolicyEngine for every
#'   year, as this function did before version 0.2.0. See Details.
#'
#' @return A tibble with tax calculation results, one row for each row of
#'   `.data`, in the same order and linked by `taxsimid`. Basic output includes:
#'   \describe{
#'     \item{taxsimid}{Record identifier from input}
#'     \item{year}{Tax year}
#'     \item{state}{State code}
#'     \item{fiitax}{Federal income tax liability}
#'     \item{siitax}{State income tax liability}
#'     \item{fica}{Total FICA (Social Security + Medicare)}
#'     \item{tfica}{Total FICA (same as fica)}
#'   }
#'
#'   When `return_all_information = TRUE`, additional variables are returned
#'   including AGI, deductions, credits, and state-specific calculations.
#'
#'   Data that mix years before 2021 with later years have the columns of both
#'   engines; a cell is `NA` where the engine that computed the row does not
#'   produce that column. TAXSIM-35 also adds a column named for its build,
#'   such as `cd2026081819`.
#'
#' @details
#'
#' ## Which engine computes each record
#'
#' With `engine = "auto"`, each record goes by its `year` to one of two
#' engines, as it does on the `policyengine-taxsim` command line: PolicyEngine
#' US for 2021 and later, and for earlier years the TAXSIM-35 program from
#' NBER that is bundled with the policyengine-taxsim Python package and runs
#' on this machine. The progress message reports how many records each engine
#' computed.
#'
#' Before version 0.2.0 this function computed every year with PolicyEngine.
#' Results for records before 2021 therefore change: they now come from
#' TAXSIM-35. This project compares PolicyEngine with TAXSIM-35 only for 2021
#' and later. To keep computing every year with PolicyEngine, pass
#' `engine = "policyengine"`.
#'
#' The function sets the TAXSIM `idtl` option itself, from
#' `return_all_information` (0 for basic output, 2 for all information), and
#' ignores an `idtl` column in `.data`.
#'
#' ## Input Data Format
#'
#' The input data frame should contain columns matching the TAXSIM 35 input
#' specification. At minimum, you typically need:
#'
#' **Required columns:**
#' \describe{
#'   \item{year}{Tax year (e.g., 2023)}
#'   \item{state}{State code (1-51, or two-letter abbreviation)}
#'   \item{mstat}{Marital status: 1 = single (or head of household with
#'     dependents), 2 = married filing jointly, 6 = married filing separately}
#' }
#'
#' **Common income columns:**
#' \describe{
#'   \item{pwages}{Primary taxpayer wages}
#'   \item{swages}{Spouse wages (if married)}
#'   \item{dividends}{Dividend income}
#'   \item{intrec}{Interest income}
#'   \item{ltcg}{Long-term capital gains}
#'   \item{stcg}{Short-term capital gains}
#'   \item{pensions}{Pension/retirement income}
#'   \item{gssi}{Social Security benefits}
#' }
#'
#' **Dependent information:**
#' \describe{
#'   \item{depx}{Number of dependents}
#'   \item{age1, age2, ...}{Ages of dependents}
#' }
#'
#' See the TAXSIM 35 documentation for the full list of supported variables.
#'
#' @examples
#' \dontrun{
#' # Basic example: Single filer with wage income
#' my_data <- data.frame(
#'   year = 2023,
#'   state = 6,        # California
#'   mstat = 1,        # Single
#'   pwages = 50000    # $50,000 wages
#' )
#'
#' results <- policyengine_calculate_taxes(my_data)
#' print(results)
#'
#' # Records before 2021 are computed by TAXSIM-35, later ones by PolicyEngine
#' panel <- data.frame(
#'   year = c(2019, 2023),
#'   state = "CA",
#'   mstat = 1,
#'   pwages = 50000
#' )
#' results <- policyengine_calculate_taxes(panel)
#'
#' # Compute every year with PolicyEngine instead
#' results <- policyengine_calculate_taxes(panel, engine = "policyengine")
#'
#' # Married couple with multiple income sources
#' couple_data <- data.frame(
#'   year = 2023,
#'   state = 36,       # New York
#'   mstat = 2,        # Married filing jointly
#'   pwages = 75000,   # Primary earner wages
#'   swages = 50000,   # Spouse wages
#'   dividends = 5000, # Dividend income
#'   depx = 2,         # Two dependents
#'   age1 = 10,        # First child age
#'   age2 = 7          # Second child age
#' )
#'
#' results <- policyengine_calculate_taxes(couple_data,
#'                                          return_all_information = TRUE)
#' }
#'
#' @seealso [setup_policyengine()] for initial setup.
#'
#' @export
policyengine_calculate_taxes <- function(.data,
                                          return_all_information = FALSE,
                                          year = NULL,
                                          show_progress = TRUE,
                                          engine = c("auto", "policyengine")) {

  engine <- match.arg(engine)

  # Auto-setup on first use
  if (!check_policyengine_setup(quiet = TRUE)) {
    message("PolicyEngine not yet set up. Running one-time setup...")
    setup_policyengine()
  }

  # Activate the virtual environment
  reticulate::use_virtualenv(.get_pe_envname(), required = TRUE)

  # Validate input
  if (!is.data.frame(.data)) {
    stop("`.data` must be a data frame.", call. = FALSE)
  }

  if (nrow(.data) == 0) {
    stop("`.data` cannot be empty.", call. = FALSE)
  }

  # Convert to standard data frame (in case it's a tibble or data.table)
  input_df <- as.data.frame(.data)

  # Add taxsimid if not present
  if (!"taxsimid" %in% names(input_df)) {
    input_df$taxsimid <- seq_len(nrow(input_df))
  }

  # Override year if specified
  if (!is.null(year)) {
    input_df$year <- year
  }

  # Validate required column
  if (!"year" %in% names(input_df)) {
    stop("Input data must contain a 'year' column.", call. = FALSE)
  }

  # The year decides which engine computes a record, so every record needs one
  input_df$year <- .tax_years(input_df$year)

  # Convert state abbreviations to codes if needed
  input_df <- .convert_state_codes(input_df)

  # Set idtl based on return_all_information
  input_df$idtl <- if (return_all_information) 2L else 0L

  # Import Python modules
  pd <- reticulate::import("pandas")
  runners <- reticulate::import("policyengine_taxsim.runners")

  # Convert R data frame to pandas DataFrame
  py_df <- reticulate::r_to_py(input_df)

  # Create runner and execute
  runner <- .make_runner(runners, py_df, engine)
  if (show_progress) {
    message(.engine_message(input_df$year, .pe_min_year(), engine))
  }

  py_results <- runner$run(show_progress = show_progress)

  # Convert results back to R
  results_df <- reticulate::py_to_r(py_results)

  # Convert to tibble for nicer printing
  results <- tibble::as_tibble(results_df)

  if (show_progress) {
    message("Done. Calculated taxes for ", nrow(results), " records.")
  }

  results
}


#' Check the tax years and return them as integers
#'
#' @param year The `year` column.
#' @return The years as an integer vector.
#' @keywords internal
.tax_years <- function(year) {
  years <- if (is.numeric(year)) {
    as.numeric(year)
  } else {
    suppressWarnings(as.numeric(as.character(year)))
  }
  if (!all(is.finite(years))) {
    stop(
      "`year` is missing or not a number in ", sum(!is.finite(years)),
      " record(s). Every record needs a tax year.",
      call. = FALSE
    )
  }
  # A fractional year such as 2021.0 or 2020.5 counts as the year it is in.
  as.integer(trunc(years))
}


#' The first tax year PolicyEngine computes when records go by year
#'
#' @return `StitchedRunner.PE_MIN_YEAR` from the installed policyengine-taxsim.
#' @keywords internal
.pe_min_year <- function() {
  runners <- reticulate::import("policyengine_taxsim.runners")
  as.integer(runners$StitchedRunner$PE_MIN_YEAR)
}


#' Count the records each engine computes
#'
#' @param years Integer tax years, one per record.
#' @param pe_min_year First tax year PolicyEngine computes.
#' @param engine The `engine` argument.
#' @return A list of two record counts, `policyengine` and `taxsim`.
#' @keywords internal
.engine_counts <- function(years, pe_min_year, engine = "auto") {
  policyengine <- if (engine == "policyengine") {
    length(years)
  } else {
    sum(years >= pe_min_year)
  }
  list(policyengine = policyengine, taxsim = length(years) - policyengine)
}


#' The progress message saying which engine computes the records
#'
#' @inheritParams .engine_counts
#' @keywords internal
.engine_message <- function(years, pe_min_year, engine = "auto") {
  counts <- .engine_counts(years, pe_min_year, engine)
  records <- function(n) paste(n, if (n == 1) "record" else "records")
  if (engine == "policyengine") {
    before <- sum(years < pe_min_year)
    return(paste0(
      "Calculating taxes for ", records(length(years)),
      " with PolicyEngine (engine = \"policyengine\")",
      if (before > 0) {
        paste0(
          "; ", before, " of them ", if (before == 1) "is" else "are",
          " for tax years before ", pe_min_year,
          ", which engine = \"auto\" computes with TAXSIM-35"
        )
      },
      "..."
    ))
  }
  if (counts$taxsim == 0) {
    return(paste0(
      "Calculating taxes for ", records(counts$policyengine),
      " with PolicyEngine..."
    ))
  }
  if (counts$policyengine == 0) {
    return(paste0(
      "Calculating taxes for ", records(counts$taxsim),
      " with TAXSIM-35 (tax years before ", pe_min_year, ")..."
    ))
  }
  paste0(
    "Calculating taxes: ", records(counts$policyengine),
    " with PolicyEngine (tax years from ", pe_min_year, " on), ",
    counts$taxsim, " with TAXSIM-35 (earlier years)..."
  )
}


#' Create the Python runner for the chosen engine
#'
#' @param runners The `policyengine_taxsim.runners` module.
#' @param py_df The input as a pandas DataFrame.
#' @param engine The `engine` argument.
#' @return A runner with a `run()` method.
#' @keywords internal
.make_runner <- function(runners, py_df, engine = "auto") {
  if (!reticulate::py_has_attr(runners, "StitchedRunner")) {
    stop(
      "The installed policyengine-taxsim has no StitchedRunner, which this ",
      "version of the R package needs. Update it with ",
      "setup_policyengine(force = TRUE).",
      call. = FALSE
    )
  }
  if (engine == "policyengine") {
    # A first PolicyEngine year of 0 sends every record to PolicyEngine;
    # StitchedRunner still returns the rows in input order.
    return(runners$StitchedRunner(py_df, pe_min_year = 0L))
  }
  runners$StitchedRunner(py_df)
}


#' Convert state abbreviations to TAXSIM state codes
#'
#' @param df Data frame with potential state column
#' @return Data frame with state codes as integers
#' @keywords internal
.convert_state_codes <- function(df) {
  if (!"state" %in% names(df)) {
    return(df)
  }

  # State abbreviation to TAXSIM code mapping
  state_map <- c(
    "AL" = 1,  "AK" = 2,  "AZ" = 3,  "AR" = 4,  "CA" = 5,
    "CO" = 6,  "CT" = 7,  "DE" = 8,  "DC" = 9,  "FL" = 10,
    "GA" = 11, "HI" = 12, "ID" = 13, "IL" = 14, "IN" = 15,
    "IA" = 16, "KS" = 17, "KY" = 18, "LA" = 19, "ME" = 20,
    "MD" = 21, "MA" = 22, "MI" = 23, "MN" = 24, "MS" = 25,
    "MO" = 26, "MT" = 27, "NE" = 28, "NV" = 29, "NH" = 30,
    "NJ" = 31, "NM" = 32, "NY" = 33, "NC" = 34, "ND" = 35,
    "OH" = 36, "OK" = 37, "OR" = 38, "PA" = 39, "RI" = 40,
    "SC" = 41, "SD" = 42, "TN" = 43, "TX" = 44, "UT" = 45,
    "VT" = 46, "VA" = 47, "WA" = 48, "WV" = 49, "WI" = 50,
    "WY" = 51
  )

  # Check if state column contains characters (abbreviations)
  if (is.character(df$state)) {
    codes <- toupper(trimws(df$state))
    df$state <- ifelse(
      codes %in% names(state_map),
      state_map[codes],
      suppressWarnings(as.integer(codes))
    )
    # An unknown code would become NA; stop with a clear error instead.
    unknown <- is.na(df$state) & !is.na(codes) & codes != ""
    if (any(unknown)) {
      stop(
        "Unknown state code(s): ", paste(unique(codes[unknown]), collapse = ", "),
        ". Use a two-letter abbreviation or a TAXSIM SOI code (0 = no state tax).",
        call. = FALSE
      )
    }
  }

  df$state <- as.integer(df$state)
  # A missing state is TAXSIM state 0 (no state tax). Set it here: by default
  # reticulate passes an integer NA to pandas as its raw sentinel value.
  df$state[is.na(df$state)] <- 0L
  df
}
