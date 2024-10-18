# """
# Testing framework for taxsim package
# """

# import policyengine_taxsim.core as core
# import pickle

# # Test 1 input
# situation_1 = {
#     "people": {
#         "you": {"age": {"2024": 40}, "employment_income": {"2024": 100000}},
#         "your first dependent": {
#             "age": {"2024": 10},
#             "employment_income": {"2024": 0},
#         },
#         "your second dependent": {
#             "age": {"2024": 10},
#             "employment_income": {"2024": 0},
#         },
#     },
#     "families": {
#         "your family": {
#             "members": ["you", "your first dependent", "your second dependent"]
#         }
#     },
#     "marital_units": {
#         "your marital unit": {"members": ["you"]},
#         "your first dependent's marital unit": {
#             "members": ["your first dependent"],
#             "marital_unit_id": {"2024": 1},
#         },
#         "your second dependent's marital unit": {
#             "members": ["your second dependent"],
#             "marital_unit_id": {"2024": 2},
#         },
#     },
#     "tax_units": {
#         "your tax unit": {
#             "members": ["you", "your first dependent", "your second dependent"]
#         }
#     },
#     "spm_units": {
#         "your household": {
#             "members": ["you", "your first dependent", "your second dependent"]
#         }
#     },
#     "households": {
#         "your household": {
#             "members": [
#                 "you",
#                 "your first dependent",
#                 "your second dependent",
#             ],
#             "state_name": {"2024": "CA"},
#         }
#     },
# }

# # Test 2 input
# situation_2 = {
#     "people": {
#         "you": {"age": {"2024": 40}, "employment_income": {"2024": 100000}},
#         "your first dependent": {
#             "age": {"2024": 10},
#             "employment_income": {"2024": 0},
#         },
#         "your second dependent": {
#             "age": {"2024": 10},
#             "employment_income": {"2024": 0},
#         },
#     },
#     "families": {
#         "your family": {
#             "members": ["you", "your first dependent", "your second dependent"]
#         }
#     },
#     "marital_units": {
#         "your marital unit": {"members": ["you"]},
#         "your first dependent's marital unit": {
#             "members": ["your first dependent"],
#             "marital_unit_id": {"2024": 1},
#         },
#         "your second dependent's marital unit": {
#             "members": ["your second dependent"],
#             "marital_unit_id": {"2024": 2},
#         },
#     },
#     "tax_units": {
#         "your tax unit": {
#             "members": ["you", "your first dependent", "your second dependent"]
#         }
#     },
#     "spm_units": {
#         "your household": {
#             "members": ["you", "your first dependent", "your second dependent"]
#         }
#     },
#     "households": {
#         "your household": {
#             "members": [
#                 "you",
#                 "your first dependent",
#                 "your second dependent",
#             ],
#             "state_name": {"2024": "PA"},
#         }
#     },
# }


# tests = {
#     "test1": {"taxsim_vars": dict(), "situation": situation_1},
#     "test2": {"taxsim_vars": dict(), "situation": situation_2},
# }
# tests_filename = "saved_tests.pickle"


# def reset_tests(testname: str = None) -> None:
#     """
#     Runs converter and saves to pickle file names saved_tests.pickle
#     Args:
#       testname    : identifier of test to reset, or None for all

#     Returns:
#       None, but overwrites test saving file
#     """
#     # TBD:
#     if testname != None:
#         raise (NotImplementedError("Not working for individual tests yet."))
#     else:
#         print("[INFO] Resetting all tests.")

#     # Run the tests and save results
#     for name, test_items in tests.items():
#         # TBD: Do import step and save that output
#         # i.e. situation = taxsim.import_single_household( taxsim_vars )
#         # For now using 'situation' vars
#         situation = test_items["situation"]

#         test_items["taxsim_results"] = core.export_single_household(situation)
#         print(f"[INFO] Finished test: {name}")

#     with open(tests_filename, "wb") as f:
#         pickle.dump(tests, f)

#     print(f"[INFO] Saved all tests to {tests_filename}")


# def check_tests(testname: str = None) -> bool:
#     """
#     Runs converter and checks results against saved_tests.pickle
#     Args:
#       testname    : identifier of test to reset, or None for all

#     Returns:
#       True if tests match
#     """
#     # TBD:
#     if testname != None:
#         raise (NotImplementedError("Not working for individual tests yet."))
#     else:
#         print("[INFO] Checking all tests.")

#     # Load the old tests
#     with open(tests_filename, "rb") as f:
#         old_tests = pickle.load(f)

#     # Run the tests and save results
#     is_different = False
#     for name, test_results in tests.items():
#         # TBD: Do import step and save that output
#         # i.e. situation = taxsim.import_single_household( taxsim_vars )
#         # For now using 'situation' vars
#         situation = test_results["situation"]
#         test_results["taxsim_results"] = core.export_single_household(
#             situation
#         )
#         print(f"[INFO] Finished running test: {name}")

#         # Compare top-level dictionaries
#         differences = _compare_nested_dicts(test_results, old_tests[name])

#         # Print differences if any
#         if differences:
#             print(f"Differences found between dictionaries:")
#             _compare_dicts(
#                 test_results, old_tests[name], print_details=True
#             )  # Recursive call for detailed output
#             is_different = True
#         print(f"[INFO] Finished checking test: {name}")

#     print(f"[INFO] Completed checks.")
#     return is_different


# def _compare_nested_dicts(dict1_val, dict2_val):
#     """
#     Compare two dictionaries by drilling down into each
#     Args:
#       dict1_val   : one dictionary
#       dict2_val   : other dictionary
#     Returns:
#       set of differences or None if none
#     """
#     # Base case: If both values are not dictionaries, compare directly
#     if not isinstance(dict1_val, dict) or not isinstance(dict2_val, dict):
#         return dict1_val != dict2_val

#     # Recursive case: Compare nested dictionaries
#     missing_keys = set(dict2_val.keys()) - set(dict1_val.keys())
#     extra_keys = set(dict1_val.keys()) - set(dict2_val.keys())
#     value_diffs = {
#         key: dict2_val.get(key, None)
#         for key in dict1_val.keys()
#         if _compare_nested_dicts(dict1_val[key], dict2_val.get(key, None))
#     }
#     return any(missing_keys or extra_keys or value_diffs)


# def _compare_dicts(newdict, olddict, print_details: bool = False):
#     """
#     Show differences between the new and old dictionaries
#     Args:
#       newdict   : new values
#       olddict   : old values
#       print_details : whether to print the differences True/False
#     """
#     # Identify missing and extra keys
#     missing_keys = set(olddict.keys()) - set(newdict.keys())
#     extra_keys = set(newdict.keys()) - set(olddict.keys())

#     # Print top-level missing/extra keys
#     if print_details and (missing_keys or extra_keys):
#         if missing_keys:
#             print(f"\tMissing keys: {missing_keys}")
#         if extra_keys:
#             print(f"\tExtra keys: {extra_keys}")

#     # Compare values for existing keys
#     value_diffs = {
#         key: olddict.get(key, None)
#         for key in newdict.keys()
#         if newdict[key] != olddict.get(key, None)
#     }
#     if print_details and value_diffs:
#         print(f"\tKeys with different values:")
#         for key, value in value_diffs.items():
#             print(f"\t\t- {key}: New value = {newdict[key]}")
#             print(f"\t\t  \t   : Old value = {value}")
#     # Recursively compare nested dictionaries
#     for key, val in newdict.items():
#         if isinstance(val, dict) and key in olddict:
#             _compare_dicts(
#                 val, olddict[key], print_details=True
#             )  # Recursive call with details


# # Run to check
# if __name__ == "__main__":
#     reset_tests()
#     check_tests()
