#' Compare PolicyEngine results with TAXSIM
#'
#' Runs both PolicyEngine and the embedded TAXSIM executable on the same
#' input data and returns a side-by-side comparison.
#'
#' @param .data A data frame containing tax unit information in TAXSIM format.
#' @param tolerance Numeric. Maximum dollar difference to consider a "match".
#'   Default is 15.
#' @param show_progress Logical. Show progress messages. Default is TRUE.
#'
#' @return A tibble with columns for both calculations and comparison metrics:
#'   \describe{
#'     \item{taxsimid}{Record identifier}
#'     \item{year, state}{Input parameters}
#'     \item{fiitax_taxsim}{Federal tax from TAXSIM}
#'     \item{fiitax_pe}{Federal tax from PolicyEngine}
#'     \item{fiitax_diff}{Difference (PolicyEngine - TAXSIM)}
#'     \item{fiitax_match}{TRUE if difference <= tolerance}
#'     \item{siitax_taxsim}{State tax from TAXSIM}
#'     \item{siitax_pe}{State tax from PolicyEngine}
#'     \item{siitax_diff}{Difference (PolicyEngine - TAXSIM)}
#'     \item{siitax_match}{TRUE if difference <= tolerance}
#'   }
#'
#' @examples
#' \dontrun{
#' my_data <- data.frame(
#'   year = 2023,
#'   state = "CA",
#'   mstat = 1,
#'   pwages = 50000
#' )
#'
#' comparison <- compare_with_taxsim(my_data)
#' print(comparison)
#'
#' # Check match rates
#' mean(comparison$fiitax_match)  # Federal match rate
#' mean(comparison$siitax_match)  # State match rate
#' }
#'
#' @export
compare_with_taxsim <- function(.data, tolerance = 15, show_progress = TRUE) {

  # Auto-setup on first use
  if (!check_policyengine_setup(quiet = TRUE)) {
    message("PolicyEngine not yet set up. Running one-time setup...")
    setup_policyengine()
  }

  # Validate input
  if (!is.data.frame(.data)) {
    stop("`.data` must be a data frame.", call. = FALSE)
  }

  if (nrow(.data) == 0) {
    stop("`.data` cannot be empty.", call. = FALSE)
  }

  # Prepare input
  input_df <- as.data.frame(.data)
  if (!"taxsimid" %in% names(input_df)) {
    input_df$taxsimid <- seq_len(nrow(input_df))
  }

  # Convert state codes
  input_df <- .convert_state_codes(input_df)

  # Set idtl for basic output
  if (!"idtl" %in% names(input_df)) {
    input_df$idtl <- 0L
  }

  # Activate Python environment
  reticulate::use_virtualenv("policyengine-taxsim", required = TRUE)

  # Import runners
  runners <- reticulate::import("policyengine_taxsim.runners")
  pd <- reticulate::import("pandas")

  # Convert to Python DataFrame
  py_df <- pd$DataFrame(input_df)

  # Run TAXSIM
  if (show_progress) message("Running TAXSIM...")
  taxsim_runner <- runners$TaxsimRunner(py_df)
  taxsim_results <- reticulate::py_to_r(taxsim_runner$run(show_progress = FALSE))

  # Run PolicyEngine
  if (show_progress) message("Running PolicyEngine...")
  pe_runner <- runners$PolicyEngineRunner(py_df)
  pe_results <- reticulate::py_to_r(pe_runner$run(show_progress = FALSE))

  # Merge results
  if (show_progress) message("Comparing results...")

  comparison <- merge(
    input_df[, c("taxsimid", "year", "state")],
    taxsim_results[, c("taxsimid", "fiitax", "siitax")],
    by = "taxsimid"
  )
  names(comparison)[names(comparison) == "fiitax"] <- "fiitax_taxsim"
  names(comparison)[names(comparison) == "siitax"] <- "siitax_taxsim"

  comparison <- merge(
    comparison,
    pe_results[, c("taxsimid", "fiitax", "siitax")],
    by = "taxsimid"
  )
  names(comparison)[names(comparison) == "fiitax"] <- "fiitax_pe"
  names(comparison)[names(comparison) == "siitax"] <- "siitax_pe"

  # Calculate differences
  comparison$fiitax_diff <- comparison$fiitax_pe - comparison$fiitax_taxsim
  comparison$siitax_diff <- comparison$siitax_pe - comparison$siitax_taxsim

  # Determine matches based on tolerance
  comparison$fiitax_match <- abs(comparison$fiitax_diff) <= tolerance
  comparison$siitax_match <- abs(comparison$siitax_diff) <= tolerance

  # Reorder columns
  comparison <- comparison[, c(
    "taxsimid", "year", "state",
    "fiitax_taxsim", "fiitax_pe", "fiitax_diff", "fiitax_match",
    "siitax_taxsim", "siitax_pe", "siitax_diff", "siitax_match"
  )]

  # Print summary if showing progress
  if (show_progress) {
    n <- nrow(comparison)
    fed_matches <- sum(comparison$fiitax_match)
    state_matches <- sum(comparison$siitax_match)

    message("\n--- Comparison Summary ---")
    message("Records compared: ", n)
    message("Federal tax match rate: ", round(fed_matches / n * 100, 1),
            "% (", fed_matches, "/", n, ")")
    message("State tax match rate: ", round(state_matches / n * 100, 1),
            "% (", state_matches, "/", n, ")")
    message("Tolerance: $", tolerance)
  }

  tibble::as_tibble(comparison)
}


#' Summarize comparison results
#'
#' Provides summary statistics for a comparison data frame from
#' `compare_with_taxsim()`.
#'
#' @param comparison A data frame returned by `compare_with_taxsim()`.
#'
#' @return A list with summary statistics.
#'
#' @examples
#' \dontrun{
#' comparison <- compare_with_taxsim(my_data)
#' summary_comparison(comparison)
#' }
#'
#' @export
summary_comparison <- function(comparison) {

  n <- nrow(comparison)

  list(
    n_records = n,
    federal = list(
      match_rate = mean(comparison$fiitax_match),
      matches = sum(comparison$fiitax_match),
      mismatches = sum(!comparison$fiitax_match),
      mean_diff = mean(comparison$fiitax_diff),
      median_diff = median(comparison$fiitax_diff),
      max_diff = max(abs(comparison$fiitax_diff))
    ),
    state = list(
      match_rate = mean(comparison$siitax_match),
      matches = sum(comparison$siitax_match),
      mismatches = sum(!comparison$siitax_match),
      mean_diff = mean(comparison$siitax_diff),
      median_diff = median(comparison$siitax_diff),
      max_diff = max(abs(comparison$siitax_diff))
    )
  )
}
