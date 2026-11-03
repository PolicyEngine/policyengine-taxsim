# What setup_policyengine() installs and from where. These tests need no
# Python: pip and reticulate are replaced with recorders. test-install.R runs
# the real installations.

PIN <- .PE_TAXSIM_VERSION

# A folder holding wheels with the given file names.
local_wheel_dir <- function(files = "policyengine_taxsim-3.1.1-py3-none-any.whl",
                            env = parent.frame()) {
  dir <- withr::local_tempdir(.local_envir = env)
  file.create(file.path(dir, files))
  normalizePath(dir, winslash = "/")
}

test_that("the default is one released version from PyPI", {
  expect_match(PIN, "^[0-9]+\\.[0-9]+\\.[0-9]+$")
  expect_identical(.pip_requirements(), paste0("policyengine-taxsim==", PIN))
  expect_identical(
    .pip_install_args(.pip_requirements()),
    c("-m", "pip", "install", paste0("policyengine-taxsim==", PIN))
  )
})

test_that("both packages can be pinned", {
  expect_identical(
    .pip_requirements(policyengine_taxsim_version = "3.0.1",
                      policyengine_us_version = "2.25.2"),
    c("policyengine-taxsim==3.0.1", "policyengine-us==2.25.2")
  )
  expect_identical(
    .pip_requirements(policyengine_us_version = "2.25.2"),
    c(paste0("policyengine-taxsim==", PIN), "policyengine-us==2.25.2")
  )
})

test_that("a folder of wheels is the only source when given", {
  dir <- local_wheel_dir()
  # Without a version, the folder decides which policyengine-taxsim.
  expect_identical(.pip_requirements(wheel_dir = dir), "policyengine-taxsim")
  expect_identical(
    .pip_requirements(policyengine_taxsim_version = "3.1.1", wheel_dir = dir),
    "policyengine-taxsim==3.1.1"
  )
  expect_identical(
    .pip_install_args("policyengine-taxsim", dir),
    c("-m", "pip", "install", "--no-index", "--find-links", dir,
      "policyengine-taxsim")
  )
})

test_that("no combination of arguments upgrades or installs from GitHub", {
  dir <- local_wheel_dir()
  for (taxsim in list(NULL, "3.1.1", "2.33.0")) {
    for (us in list(NULL, "2.38.0", "1.783.0")) {
      for (wheel_dir in list(NULL, dir)) {
        requirements <- .pip_requirements(taxsim, us, wheel_dir)
        args <- .pip_install_args(requirements, wheel_dir)
        label <- paste(c(taxsim, us, wheel_dir), collapse = " ")

        expect_false(any(c("--upgrade", "-U") %in% args), label = label)
        expect_false(any(grepl("git\\+|github", args)), label = label)
        # Offline flags exactly when a folder is given, before the packages.
        expect_identical("--no-index" %in% args, !is.null(wheel_dir), label = label)
        expect_identical("--find-links" %in% args, !is.null(wheel_dir), label = label)
        expect_identical(utils::tail(args, length(requirements)), requirements)
        # policyengine-taxsim is always installed, at one version unless a
        # folder decides it; policyengine-us only when pinned.
        expect_match(requirements[1], "^policyengine-taxsim(==[0-9.]+)?$")
        expect_identical(
          grepl("==", requirements[1], fixed = TRUE),
          !is.null(taxsim) || is.null(wheel_dir),
          label = label
        )
        expect_identical(
          requirements[-1],
          if (is.null(us)) character(0) else paste0("policyengine-us==", us)
        )
      }
    }
  }
})

test_that("versions must be single version numbers", {
  bad <- list(
    "", "latest", ">=2.0", "==3.1.1", "3.1.1 ", "3.1.1 --index-url http://x",
    "git+https://github.com/PolicyEngine/policyengine-taxsim.git", "-r",
    NA_character_, 3.1, c("3.1.1", "3.1.2"), TRUE
  )
  for (version in bad) {
    expect_error(
      .pip_requirements(policyengine_taxsim_version = version),
      "`policyengine_taxsim_version` must be one version number"
    )
    expect_error(
      .pip_requirements(policyengine_us_version = version),
      "`policyengine_us_version` must be one version number"
    )
  }
  for (version in c("3.1.1", "2.38.0", "1.783.0", "10.0", "2.0.0rc1")) {
    expect_identical(.check_version(version, "x"), version)
  }
  expect_null(.check_version(NULL, "x"))
})

test_that("a folder of wheels is checked before anything is installed", {
  expect_null(.check_wheel_dir(NULL))
  expect_error(.check_wheel_dir(file.path(tempdir(), "no-such-folder")),
               "existing folder")
  for (bad in list(1, NA_character_, c("a", "b"))) {
    expect_error(.check_wheel_dir(bad), "existing folder")
  }

  empty <- local_wheel_dir(character(0))
  expect_error(.check_wheel_dir(empty), "has no policyengine-taxsim wheel")
  # Dependencies alone are not enough, nor is a source archive.
  others <- local_wheel_dir(c("policyengine_us-2.38.0-py3-none-any.whl",
                              "policyengine_taxsim-3.1.1.tar.gz"))
  expect_error(.check_wheel_dir(others), "has no policyengine-taxsim wheel")

  dir <- local_wheel_dir(c("policyengine_taxsim-3.1.1-py3-none-any.whl",
                           "policyengine_us-2.38.0-py3-none-any.whl"))
  expect_identical(.check_wheel_dir(dir), dir)
  expect_identical(.check_wheel_dir(dir, "3.1.1"), dir)
  # 3.1.1 is there; 3.1 and 3.1.10 are not.
  expect_error(.check_wheel_dir(dir, "3.1"), "has no policyengine-taxsim 3.1 wheel")
  expect_error(.check_wheel_dir(dir, "3.1.10"),
               "has no policyengine-taxsim 3.1.10 wheel")
})


# setup_policyengine() with pip and reticulate recorded -----------------------

# Replaces everything setup_policyengine() calls outside itself and returns
# the environment the calls are recorded in.
local_recorded_setup <- function(already_set_up = FALSE,
                                 starter = "/usr/bin/python3.12",
                                 existing = character(0),
                                 pip_status = 0L,
                                 env = parent.frame()) {
  calls <- new.env()
  calls$log <- character(0)
  record <- function(what) calls$log <- c(calls$log, what)
  local_mocked_bindings(
    check_policyengine_setup = function(...) already_set_up,
    policyengine_versions = function(envname = "policyengine-taxsim") {
      list(policyengine_taxsim = "3.1.1", policyengine_us = "2.38.0",
           policyengine_core = "3.32.29")
    },
    .run_pip = function(python, args) {
      record("pip")
      calls$pip_python <- python
      calls$pip_args <- args
      pip_status
    },
    .env = env
  )
  local_mocked_bindings(
    virtualenv_starter = function(...) starter,
    install_miniconda = function(...) record("miniconda"),
    virtualenv_list = function() existing,
    virtualenv_remove = function(envname, ...) record("remove"),
    virtualenv_create = function(envname, ...) {
      record("create")
      calls$create <- list(envname = envname, ...)
    },
    virtualenv_python = function(envname) file.path("/envs", envname, "bin/python"),
    use_virtualenv = function(...) NULL,
    import = function(...) list(PolicyEngineRunner = function(...) NULL),
    .package = "reticulate",
    .env = env
  )
  calls
}

test_that("setup installs the pinned release with one pip call", {
  calls <- local_recorded_setup()
  messages <- capture_messages(expect_true(setup_policyengine()))

  expect_identical(calls$log, c("create", "pip"))
  expect_identical(calls$pip_python, "/envs/policyengine-taxsim/bin/python")
  expect_identical(
    calls$pip_args,
    c("-m", "pip", "install", paste0("policyengine-taxsim==", PIN))
  )
  # The environment is created without reticulate's own installs from the
  # package index (pip, wheel, setuptools and numpy).
  expect_identical(
    calls$create,
    list(envname = "policyengine-taxsim", version = .PE_PYTHON_VERSION,
         packages = FALSE)
  )
  expect_match(messages, paste0("policyengine-taxsim==", PIN, " from PyPI"),
               fixed = TRUE, all = FALSE)
  # It reports the versions installed and the call that installs them again.
  expect_match(
    messages,
    paste0('setup_policyengine(force = TRUE, policyengine_taxsim_version = ',
           '"3.1.1", policyengine_us_version = "2.38.0")'),
    fixed = TRUE, all = FALSE
  )
})

test_that("setup passes pins and a folder of wheels to pip", {
  dir <- local_wheel_dir(c("policyengine_taxsim-3.0.1-py3-none-any.whl"))
  calls <- local_recorded_setup()
  suppressMessages(setup_policyengine(
    policyengine_taxsim_version = "3.0.1", policyengine_us_version = "2.25.2",
    wheel_dir = dir
  ))
  expect_identical(
    calls$pip_args,
    c("-m", "pip", "install", "--no-index", "--find-links", dir,
      "policyengine-taxsim==3.0.1", "policyengine-us==2.25.2")
  )
})

test_that("with a folder of wheels, setup never downloads Miniconda", {
  dir <- local_wheel_dir()
  calls <- local_recorded_setup(starter = NULL)
  expect_error(
    suppressMessages(setup_policyengine(wheel_dir = dir)),
    "Miniconda is not downloaded when `wheel_dir` is given"
  )
  expect_identical(calls$log, character(0))

  # Without a folder, a machine with no compatible Python still gets Miniconda.
  calls <- local_recorded_setup(starter = NULL)
  suppressMessages(setup_policyengine())
  expect_identical(calls$log, c("miniconda", "create", "pip"))
})

test_that("a given Python builds the environment, with no search", {
  python <- withr::local_tempfile()
  file.create(python)
  calls <- local_recorded_setup(starter = NULL)
  suppressMessages(setup_policyengine(python = python))
  expect_identical(calls$log, c("create", "pip"))
  expect_identical(
    calls$create,
    list(envname = "policyengine-taxsim", python = python, packages = FALSE)
  )
  expect_error(setup_policyengine(python = file.path(tempdir(), "no-python")),
               "`python` must be the path of a Python interpreter")
})

test_that("bad arguments stop before an existing environment is removed", {
  calls <- local_recorded_setup(existing = "policyengine-taxsim")
  expect_error(
    setup_policyengine(force = TRUE, policyengine_us_version = "latest"),
    "must be one version number"
  )
  expect_error(
    setup_policyengine(force = TRUE, wheel_dir = local_wheel_dir(character(0))),
    "has no policyengine-taxsim wheel"
  )
  expect_identical(calls$log, character(0))

  # With good arguments, force replaces the environment.
  suppressMessages(setup_policyengine(force = TRUE))
  expect_identical(calls$log, c("remove", "create", "pip"))
})

test_that("an existing setup is left alone, and says so when pins were asked for", {
  calls <- local_recorded_setup(already_set_up = TRUE)
  expect_message(setup_policyengine(), "already set up. Use force = TRUE to reinstall")
  expect_message(
    setup_policyengine(policyengine_us_version = "2.25.2"),
    "nothing was installed. Use force = TRUE to reinstall with the versions"
  )
  expect_identical(calls$log, character(0))
})

test_that("a failed installation shows the command and what to check", {
  calls <- local_recorded_setup(pip_status = 1L)
  expect_error(
    suppressMessages(setup_policyengine(policyengine_us_version = "2.25.2")),
    paste0("python -m pip install policyengine-taxsim==", PIN,
           " policyengine-us==2.25.2"),
    fixed = TRUE
  )
  expect_error(suppressMessages(setup_policyengine()), "PyPI does not keep every release")
  expect_error(suppressMessages(setup_policyengine()), "wheel_dir")

  dir <- local_wheel_dir()
  expect_error(
    suppressMessages(setup_policyengine(wheel_dir = dir)),
    "The folder must hold wheels for policyengine-taxsim and every dependency"
  )
})
