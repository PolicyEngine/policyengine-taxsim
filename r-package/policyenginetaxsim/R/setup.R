# Python version constraint matching policyengine-us requirements.
# policyengine-us requires Python >=3.10,<3.14 (as of Feb 2026).
# Without this, setup_policyengine() fails on machines with only Python 3.14+.
.PE_PYTHON_VERSION <- ">=3.10,<3.14"

# The policyengine-taxsim release setup_policyengine() installs by default.
# The release step (.github/bump_version.py) rewrites this line together with
# the version in pyproject.toml, and tests/test_r_package_pin.py fails when
# the two differ. Do not edit it by hand.
.PE_TAXSIM_VERSION <- "3.1.1"

#' Set up PolicyEngine Python environment
#'
#' Creates a Python virtual environment and installs policyengine-taxsim and
#' its dependencies, including policyengine-us, into it. This function only
#' needs to be run once after installing the package;
#' [policyengine_calculate_taxes()] runs it with the defaults when no
#' environment exists.
#'
#' @details
#'
#' ## What is installed
#'
#' By default the function installs one released version of
#' policyengine-taxsim from PyPI: the release that was current at the commit
#' this R package was installed from. One copy of the R package therefore
#' installs the same policyengine-taxsim on any day. Versions of this package
#' before 0.2.0 installed the `main` branch from GitHub, so what they
#' installed depended on the day of the first run.
#'
#' policyengine-us, which holds the tax rules, is a dependency: unless
#' `policyengine_us_version` is given, pip installs the newest release that
#' fits the Python version, so results for the same data can still differ
#' between machines set up on different days. To get the same results
#' everywhere, pin both versions, or install from a folder of wheels with
#' `wheel_dir`. The function prints the versions it installed and the call
#' that installs them again. PyPI does not keep every policyengine-us
#' release, so a version pinned today may not be installable later; a folder
#' of wheels is.
#'
#' ## Network access
#'
#' The default installation downloads from PyPI (or the package index pip is
#' configured to use). When no compatible Python is found, the function also
#' downloads Miniconda with `reticulate::install_miniconda()`.
#'
#' With `wheel_dir`, the function downloads nothing: pip runs with
#' `--no-index --find-links <wheel_dir>`, and the function stops instead of
#' downloading Miniconda when no compatible Python is found. Build the folder
#' on a machine with internet access and the same operating system, processor
#' type and Python version as the target. This downloads the newest
#' policyengine-taxsim release and its dependencies; add `==<version>` to
#' choose another:
#'
#' ```
#' python -m pip download --only-binary=:all: --dest policyengine-wheels policyengine-taxsim
#' ```
#'
#' @param envname Name of the virtual environment to create. Default is
#'   "policyengine-taxsim".
#' @param force If TRUE, will reinstall even if environment already exists.
#'   Default is FALSE.
#' @param policyengine_us_version Optional. Pin policyengine-us to a specific
#'   version (e.g., "2.25.2"). If NULL (default), uses whatever version pip
#'   resolves. Use this for reproducible results across model runs.
#' @param policyengine_taxsim_version Optional. The policyengine-taxsim
#'   version to install (e.g., "3.1.1"). If NULL (default), installs the
#'   release this version of the R package was published with, or, with
#'   `wheel_dir`, the newest version in that folder.
#' @param wheel_dir Optional. Path of a folder of Python wheels holding
#'   policyengine-taxsim and all of its dependencies. When given, packages are
#'   installed only from this folder and nothing is downloaded. See Details.
#' @param python Optional. Path of the Python interpreter (3.10 to 3.13) to
#'   build the virtual environment from. If NULL (default), reticulate picks
#'   an installed one. Give it when a machine has several Pythons: the
#'   wheels in `wheel_dir` fit one Python version, and current policyengine-us
#'   releases need Python 3.11 or later.
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
#' # Pin both packages for reproducible results
#' setup_policyengine(force = TRUE, policyengine_taxsim_version = "3.1.1",
#'                    policyengine_us_version = "2.38.0")
#'
#' # Install without internet access, from a folder of wheels
#' setup_policyengine(wheel_dir = "policyengine-wheels")
#' }
#'
#' @export
setup_policyengine <- function(envname = "policyengine-taxsim", force = FALSE,
                               policyengine_us_version = NULL,
                               policyengine_taxsim_version = NULL,
                               wheel_dir = NULL,
                               python = NULL) {

  # Check the arguments before anything is removed or installed
  wheel_dir <- .check_wheel_dir(wheel_dir, policyengine_taxsim_version)
  requirements <- .pip_requirements(
    policyengine_taxsim_version = policyengine_taxsim_version,
    policyengine_us_version = policyengine_us_version,
    wheel_dir = wheel_dir
  )
  if (!is.null(python)) {
    if (!is.character(python) || length(python) != 1 || is.na(python) ||
        !file.exists(python)) {
      stop("`python` must be the path of a Python interpreter.", call. = FALSE)
    }
  }

  # Check if already set up (unless forcing)
  if (!force && check_policyengine_setup(quiet = TRUE, envname = envname)) {
    if (is.null(policyengine_us_version) &&
        is.null(policyengine_taxsim_version) && is.null(wheel_dir) &&
        is.null(python)) {
      message("PolicyEngine is already set up. Use force = TRUE to reinstall.")
    } else {
      message(
        "PolicyEngine is already set up, so nothing was installed. ",
        "Use force = TRUE to reinstall with the versions you asked for."
      )
    }
    return(invisible(TRUE))
  }

  # Step 1: Ensure a compatible Python is available
  # policyengine-us requires Python >=3.10,<3.14
  if (is.null(python)) {
    message("Checking for compatible Python installation (requires ", .PE_PYTHON_VERSION, ")...")

    # Check if a compatible Python exists among available starters
    compatible_python <- tryCatch(
      reticulate::virtualenv_starter(version = .PE_PYTHON_VERSION, all = FALSE),
      error = function(e) NULL
    )

    if (is.null(compatible_python) || length(compatible_python) == 0) {
      if (!is.null(wheel_dir)) {
        # Installing from a folder of wheels must not use the network.
        stop(
          "No compatible Python found (requires ", .PE_PYTHON_VERSION, "), ",
          "and Miniconda is not downloaded when `wheel_dir` is given.\n",
          "Install Python first, or pass its path as `python`.",
          call. = FALSE
        )
      }
      message("No compatible Python found. Installing Miniconda with Python 3.12...")
      message("This may take a few minutes...")

      tryCatch({
        reticulate::install_miniconda()
        message("Miniconda installed successfully.")
      }, error = function(e) {
        stop(
          "Failed to install Miniconda. Error: ", e$message, "\n",
          "policyengine-us requires Python ", .PE_PYTHON_VERSION, ".\n",
          "Please install Python 3.12 from https://www.python.org/downloads/\n",
          "or via Homebrew: brew install python@3.12",
          call. = FALSE
        )
      })
    } else {
      message("Compatible Python found.")
    }
  }

  # Step 2: Create virtual environment with compatible Python version
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
      # packages = FALSE: by default reticulate upgrades pip, wheel and
      # setuptools and installs numpy from the package index here. Everything
      # is installed in step 3 instead, from the index or from `wheel_dir`.
      if (is.null(python)) {
        reticulate::virtualenv_create(
          envname, version = .PE_PYTHON_VERSION, packages = FALSE
        )
      } else {
        reticulate::virtualenv_create(envname, python = python, packages = FALSE)
      }
      message("Virtual environment created.")
    }, error = function(e) {
      stop(
        "Failed to create virtual environment. Error: ", e$message, "\n",
        "policyengine-us requires Python ", .PE_PYTHON_VERSION, ".\n",
        "Please install Python 3.12 from https://www.python.org/downloads/\n",
        "or via Homebrew: brew install python@3.12",
        call. = FALSE
      )
    })
  }

  # Step 3: Install Python packages
  message("Installing Python packages (this may take several minutes)...")
  if (is.null(wheel_dir)) {
    message("  - ", paste(requirements, collapse = ", "), " from PyPI")
  } else {
    message("  - ", paste(requirements, collapse = ", "), " from ", wheel_dir)
  }

  # One pip call, so pip resolves the pinned versions and their dependencies
  # together. pip is called directly because reticulate::virtualenv_install()
  # always adds --upgrade.
  pip_args <- .pip_install_args(requirements, wheel_dir)
  status <- .run_pip(reticulate::virtualenv_python(envname), pip_args)
  if (!identical(as.integer(status), 0L)) {
    stop(.pip_failure_message(pip_args, wheel_dir), call. = FALSE)
  }
  message("Python packages installed successfully.")

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

  # Report what was installed and how to install it again
  versions <- policyengine_versions(envname)
  message(
    "\nSetup complete! You can now use policyengine_calculate_taxes()\n",
    "To install these versions again:\n  ",
    .reinstall_call(versions$policyengine_taxsim, versions$policyengine_us)
  )
  invisible(TRUE)
}


#' Check a version argument
#'
#' @param version NULL or a version string such as "3.1.1".
#' @param arg The argument's name, for the error message.
#' @return `version`, unchanged.
#' @keywords internal
.check_version <- function(version, arg) {
  if (is.null(version)) {
    return(NULL)
  }
  if (!is.character(version) || length(version) != 1 || is.na(version) ||
      !grepl("^[0-9]+(\\.[0-9A-Za-z]+)*$", version)) {
    stop(
      "`", arg, "` must be one version number, such as \"3.1.1\".",
      call. = FALSE
    )
  }
  version
}


#' Check a folder of wheels before anything is removed or installed
#'
#' @param wheel_dir NULL or the `wheel_dir` argument.
#' @param policyengine_taxsim_version NULL or the version asked for.
#' @return NULL, or the folder's absolute path.
#' @keywords internal
.check_wheel_dir <- function(wheel_dir, policyengine_taxsim_version = NULL) {
  if (is.null(wheel_dir)) {
    return(NULL)
  }
  if (!is.character(wheel_dir) || length(wheel_dir) != 1 || is.na(wheel_dir) ||
      !dir.exists(wheel_dir)) {
    stop("`wheel_dir` must be the path of an existing folder of wheels.",
         call. = FALSE)
  }
  wheel_dir <- normalizePath(wheel_dir, winslash = "/", mustWork = TRUE)
  version <- .check_version(policyengine_taxsim_version,
                            "policyengine_taxsim_version")
  # Wheel file names spell the package policyengine_taxsim, then the version.
  files <- tolower(list.files(wheel_dir))
  prefix <- paste0("policyengine_taxsim-", version, if (!is.null(version)) "-")
  found <- startsWith(files, tolower(prefix)) & endsWith(files, ".whl")
  if (!any(found)) {
    stop(
      "`wheel_dir` (", wheel_dir, ") has no policyengine-taxsim ",
      if (!is.null(version)) paste0(version, " "), "wheel.",
      call. = FALSE
    )
  }
  wheel_dir
}


#' The pip requirements setup_policyengine() installs
#'
#' @param policyengine_taxsim_version,policyengine_us_version NULL or a
#'   version string.
#' @param wheel_dir NULL or a folder of wheels.
#' @return A character vector of pip requirement specifiers.
#' @keywords internal
.pip_requirements <- function(policyengine_taxsim_version = NULL,
                              policyengine_us_version = NULL,
                              wheel_dir = NULL) {
  taxsim_version <- .check_version(policyengine_taxsim_version,
                                   "policyengine_taxsim_version")
  us_version <- .check_version(policyengine_us_version,
                               "policyengine_us_version")
  if (is.null(taxsim_version) && is.null(wheel_dir)) {
    taxsim_version <- .PE_TAXSIM_VERSION
  }
  c(
    # With a folder of wheels and no version, pip takes the newest
    # policyengine-taxsim in the folder.
    if (is.null(taxsim_version)) {
      "policyengine-taxsim"
    } else {
      paste0("policyengine-taxsim==", taxsim_version)
    },
    if (!is.null(us_version)) paste0("policyengine-us==", us_version)
  )
}


#' The arguments of the pip command setup_policyengine() runs
#'
#' @param requirements Requirement specifiers from `.pip_requirements()`.
#' @param wheel_dir NULL or a folder of wheels.
#' @return A character vector of arguments for `python`.
#' @keywords internal
.pip_install_args <- function(requirements, wheel_dir = NULL) {
  c(
    "-m", "pip", "install",
    if (!is.null(wheel_dir)) c("--no-index", "--find-links", wheel_dir),
    requirements
  )
}


#' Run pip in the virtual environment
#'
#' @param python The environment's Python interpreter.
#' @param args Arguments from `.pip_install_args()`.
#' @return pip's exit status.
#' @keywords internal
.run_pip <- function(python, args) {
  system2(python, shQuote(args))
}


#' The error message for a failed installation
#'
#' @param pip_args The arguments pip was run with.
#' @param wheel_dir NULL or a folder of wheels.
#' @keywords internal
.pip_failure_message <- function(pip_args, wheel_dir = NULL) {
  paste0(
    "Failed to install Python packages. The command was:\n",
    "  python ", paste(pip_args, collapse = " "), "\n",
    if (is.null(wheel_dir)) {
      paste0(
        "Check the pip output above. This step needs access to PyPI (or the ",
        "package index pip is configured to use), and the version asked for ",
        "must still be there: PyPI does not keep every release.\n",
        "To install without internet access, see `wheel_dir` in ",
        "?setup_policyengine."
      )
    } else {
      paste0(
        "Check the pip output above. The folder must hold wheels for ",
        "policyengine-taxsim and every dependency, built for this operating ",
        "system and the Python version of the environment (see `python` in ",
        "?setup_policyengine)."
      )
    }
  )
}


#' The call that installs given versions again
#'
#' @param policyengine_taxsim_version,policyengine_us_version Installed
#'   versions, as `policyengine_versions()` reports them.
#' @keywords internal
.reinstall_call <- function(policyengine_taxsim_version,
                            policyengine_us_version) {
  paste0(
    "setup_policyengine(force = TRUE, policyengine_taxsim_version = \"",
    policyengine_taxsim_version, "\", policyengine_us_version = \"",
    policyengine_us_version, "\")"
  )
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

  core_ver <- tryCatch({
    pkg <- reticulate::import("importlib.metadata")
    pkg$version("policyengine-core")
  }, error = function(e) "unknown")

  message("policyengine-taxsim: ", taxsim_ver)
  message("policyengine-us:     ", us_ver)
  message("policyengine-core:   ", core_ver)

  invisible(list(
    policyengine_taxsim = taxsim_ver,
    policyengine_us = us_ver,
    policyengine_core = core_ver
  ))
}
