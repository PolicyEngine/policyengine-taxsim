#' Set up PolicyEngine Python environment
#'
#' Installs Python (via Miniconda if needed) and the required Python packages
#' for running PolicyEngine tax calculations. This function only needs to be
#' run once after installing the package.
#'
#' @param envname Name of the virtual environment to create. Default is
#'   "policyengine-taxsim".
#' @param force If TRUE, will reinstall even if environment already exists.
#'   Default is FALSE.
#' @param policyengine_us_version Optional. Pin policyengine-us to a specific
#'   version (e.g., "1.555.0"). If NULL (default), uses whatever version pip
#'   resolves. Use this for reproducible results across model runs.
#'
#' @return Invisibly returns TRUE if setup was successful.
#'
#' @examples
#' \dontrun{
#' # First-time setup (run once after installing package)
#' setup_policyengine()
#'
#' # Force reinstall if something went wrong
#' setup_policyengine(force = TRUE)
#'
#' # Pin to a specific policyengine-us version for reproducibility
#' setup_policyengine(force = TRUE, policyengine_us_version = "1.555.0")
#' }
#'
#' @export
setup_policyengine <- function(envname = "policyengine-taxsim", force = FALSE,
                               policyengine_us_version = NULL) {

  # Check if already set up (unless forcing)
  if (!force && check_policyengine_setup(quiet = TRUE)) {
    message("PolicyEngine is already set up. Use force = TRUE to reinstall.")
    return(invisible(TRUE))
  }

  # Step 1: Ensure Python is available
  message("Checking for Python installation...")

  if (!reticulate::py_available(initialize = FALSE)) {
    message("Python not found. Installing Miniconda...")
    message("This may take a few minutes...")

    tryCatch({
      reticulate::install_miniconda()
      message("Miniconda installed successfully.")
    }, error = function(e) {
      stop(
        "Failed to install Miniconda. Error: ", e$message, "\n",
        "You may need to install Python manually from https://www.python.org/",
        call. = FALSE
      )
    })
  } else {
    message("Python found.")
  }

  # Step 2: Create virtual environment
  message("Creating virtual environment '", envname, "'...")

  # Check if virtualenv exists
  existing_envs <- tryCatch(
    reticulate::virtualenv_list(),
    error = function(e) character(0)
  )

  if (envname %in% existing_envs) {
    if (force) {
      message("Removing existing environment...")
      reticulate::virtualenv_remove(envname, confirm = FALSE)
    } else {
      message("Virtual environment already exists.")
    }
  }

  if (!(envname %in% existing_envs) || force) {
    tryCatch({
      reticulate::virtualenv_create(envname)
      message("Virtual environment created.")
    }, error = function(e) {
      stop(
        "Failed to create virtual environment. Error: ", e$message,
        call. = FALSE
      )
    })
  }

  # Step 3: Install Python packages
  message("Installing Python packages (this may take several minutes)...")
  message("  - policyengine-taxsim (includes policyengine-us)")

  tryCatch({
    # Install policyengine-taxsim from GitHub
    # This includes policyengine-us as a dependency
    reticulate::virtualenv_install(
      envname = envname,
      packages = c("policyengine-taxsim @ git+https://github.com/PolicyEngine/policyengine-taxsim.git"),
      pip_options = "--upgrade"
    )

    # Pin policyengine-us to a specific version if requested
    if (!is.null(policyengine_us_version)) {
      message("  - Pinning policyengine-us to version ", policyengine_us_version, "...")
      reticulate::virtualenv_install(
        envname = envname,
        packages = c(paste0("policyengine-us==", policyengine_us_version))
      )
    }

    message("Python packages installed successfully.")
  }, error = function(e) {
    stop(
      "Failed to install Python packages. Error: ", e$message, "\n",
      "You may need to install manually:\n",
      "  pip install git+https://github.com/PolicyEngine/policyengine-taxsim.git",
      call. = FALSE
    )
  })

  # Step 4: Verify installation
  message("Verifying installation...")
  reticulate::use_virtualenv(envname, required = TRUE)

  tryCatch({
    pe_taxsim <- reticulate::import("policyengine_taxsim")
    runners <- reticulate::import("policyengine_taxsim.runners")
    message("policyengine-taxsim imported successfully")
    message("PolicyEngineRunner available: ", !is.null(runners$PolicyEngineRunner))
  }, error = function(e) {
    stop(
      "Installation verification failed. Error: ", e$message,
      call. = FALSE
    )
  })

  message("\nSetup complete! You can now use policyengine_calculate_taxes()")
  invisible(TRUE)
}


#' Check if PolicyEngine is properly set up
#'
#' Verifies that Python and all required packages are installed and accessible.
#'
#' @param quiet If TRUE, suppresses messages. Default is FALSE.
#' @param envname Name of the virtual environment to check. Default is
#'   "policyengine-taxsim".
#'
#' @return TRUE if setup is complete, FALSE otherwise.
#'
#' @examples
#' \dontrun{
#' if (check_policyengine_setup()) {
#'   results <- policyengine_calculate_taxes(my_data)
#' } else {
#'   setup_policyengine()
#' }
#' }
#'
#' @export
check_policyengine_setup <- function(quiet = FALSE, envname = "policyengine-taxsim") {

  # Check 1: Virtual environment exists
  existing_envs <- tryCatch(
    reticulate::virtualenv_list(),
    error = function(e) character(0)
  )

  if (!(envname %in% existing_envs)) {
    if (!quiet) message("Virtual environment '", envname, "' not found.")
    return(FALSE)
  }

  # Check 2: Can activate and import required packages
  tryCatch({
    reticulate::use_virtualenv(envname, required = TRUE)
    reticulate::import("policyengine_taxsim")
    reticulate::import("policyengine_us")
    reticulate::import("pandas")

    if (!quiet) message("PolicyEngine setup verified successfully.")
    return(TRUE)
  }, error = function(e) {
    if (!quiet) message("Required Python packages not found: ", e$message)
    return(FALSE)
  })
}


#' Get the PolicyEngine virtual environment name
#'
#' @return The name of the virtual environment used by this package.
#' @keywords internal
.get_pe_envname <- function() {
  getOption("policyenginetaxsim.envname", default = "policyengine-taxsim")
}


#' Show installed PolicyEngine package versions
#'
#' Reports the versions of policyengine-taxsim and policyengine-us installed
#' in the Python virtual environment. Useful for debugging and ensuring
#' reproducibility.
#'
#' @param envname Name of the virtual environment. Default is
#'   "policyengine-taxsim".
#'
#' @return A named list with version strings, returned invisibly.
#'
#' @examples
#' \dontrun{
#' policyengine_versions()
#' }
#'
#' @export
policyengine_versions <- function(envname = "policyengine-taxsim") {
  if (!check_policyengine_setup(quiet = TRUE, envname = envname)) {
    stop("PolicyEngine is not set up. Run setup_policyengine() first.",
         call. = FALSE)
  }

  reticulate::use_virtualenv(envname, required = TRUE)

  taxsim_ver <- tryCatch({
    pkg <- reticulate::import("importlib.metadata")
    pkg$version("policyengine-taxsim")
  }, error = function(e) "unknown")

  us_ver <- tryCatch({
    pkg <- reticulate::import("importlib.metadata")
    pkg$version("policyengine-us")
  }, error = function(e) "unknown")

  message("policyengine-taxsim: ", taxsim_ver)
  message("policyengine-us:     ", us_ver)

  invisible(list(
    policyengine_taxsim = taxsim_ver,
    policyengine_us = us_ver
  ))
}
