#' @keywords internal
.onLoad <- function(libname, pkgname) {
  # Set default options
  op <- options()
  op.policyenginetaxsim <- list(
    policyenginetaxsim.envname = "policyengine-taxsim"
  )

  toset <- !(names(op.policyenginetaxsim) %in% names(op))
  if (any(toset)) options(op.policyenginetaxsim[toset])

  invisible()
}


#' @keywords internal
.onAttach <- function(libname, pkgname) {
  # Check if PolicyEngine is set up and provide helpful message if not
  if (!check_policyengine_setup(quiet = TRUE)) {
    packageStartupMessage(
      "PolicyEngine Python environment not found.\n",
      "Run setup_policyengine() to install required dependencies.\n",
      "This only needs to be done once."
    )
  }
}
