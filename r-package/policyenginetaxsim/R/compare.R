#' Compare PolicyEngine results with TAXSIM
#'
#' Runs both PolicyEngine (via this package) and TAXSIM (via usincometaxes)
#' on the same input data and returns a side-by-side comparison.
#'
#' @param .data A data frame containing tax unit information in TAXSIM format.
#' @param tolerance Numeric. Maximum dollar difference to consider a "match".
#'   Default is 15.
#' @param show_progress Logical. Show progress messages. Default is TRUE.
#'
#' @return A tibble with columns for both calculations and comparison metrics:
#'   \describe{
#'     \item{taxsimid}{Record identifier}
#'     \item{year, state, mstat}{Input parameters}
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
#' @details
#' This function requires the `usincometaxes` package to be installed.
#' Install it with: `install.packages("usincometaxes")`
#'
#' The comparison uses a tolerance (default $15) to account for minor
#' rounding differences between the two calculators.
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


  # Check if usincometaxes is installed

if (!requireNamespace("usincometaxes", quietly = TRUE)) {
    stop(
      "The 'usincometaxes' package is required for comparison.\n",
      "Install it with: install.packages(\"usincometaxes\")",
      call. = FALSE
    )
  }

  # Validate input
  if (!is.data.frame(.data)) {
    stop("`.data` must be a data frame.", call. = FALSE)
  }

  if (nrow(.data) == 0) {
    stop("`.data` cannot be empty.", call. = FALSE)
  }

  # Ensure taxsimid exists
  input_df <- as.data.frame(.data)
  if (!"taxsimid" %in% names(input_df)) {
    input_df$taxsimid <- seq_len(nrow(input_df))
  }

  # Run TAXSIM via usincometaxes
  if (show_progress) message("Running TAXSIM (via usincometaxes)...")
  taxsim_results <- usincometaxes::taxsim_calculate_taxes(input_df)

  # Run PolicyEngine via our package
  if (show_progress) message("Running PolicyEngine...")
  pe_results <- policyengine_calculate_taxes(
    input_df,
    show_progress = show_progress
  )

  # Merge results
  if (show_progress) message("Comparing results...")

  # usincometaxes only returns tax columns, not input columns
  # So we merge both results with the input data
  comparison <- merge(
    input_df[, c("taxsimid", "year", "state", "mstat")],
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
