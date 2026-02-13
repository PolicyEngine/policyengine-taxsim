#' Calculate US Income Taxes using PolicyEngine
#'
#' Calculates federal and state income taxes for US tax units using the
#' PolicyEngine microsimulation model. This function provides a TAXSIM-compatible
#' interface, accepting the same input variables and returning similar output.
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
#'
#' @return A tibble with tax calculation results. Each row corresponds to a row
#'   in `.data`, linked by `taxsimid`. Basic output includes:
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
#' @details
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
#'   \item{mstat}{Marital status: 1 = single, 2 = married filing jointly}
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
                                          show_progress = TRUE) {

  # Validate setup
  if (!check_policyengine_setup(quiet = TRUE)) {
    stop(
      "PolicyEngine is not set up. Please run setup_policyengine() first.",
      call. = FALSE
    )
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
  if (show_progress) {
    message("Running PolicyEngine tax calculations...")
  }

  runner <- runners$PolicyEngineRunner(py_df)
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
    df$state <- toupper(df$state)
    df$state <- ifelse(
      df$state %in% names(state_map),
      state_map[df$state],
      as.integer(df$state)
    )
  }

  df$state <- as.integer(df$state)
  df
}
